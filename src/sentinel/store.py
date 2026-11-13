"""The point-in-time ban-state store. SQLite, keyed on `(isin, trade_date)`.

Designed in `DECISIONS.md` #012. The decisions this module implements, and the reason each one
is in the storage layer rather than in a comment:

**One record per `(isin, trade_date)`, enforced by a primary key.** Duplicate state for the
same scrip on the same day is impossible to write, not merely discouraged. Same principle as
`MwplRow.__post_init__`: the invariant lives at the boundary where data enters, so no caller
has to remember it. ISIN rather than symbol because symbols get renamed and reused (#011 Q2).

**Two fields, and only one of them can be read forward.** Each record holds the engine's
`forecast` and NSE's `official` state. A wrong ban flag latches rather than decaying - two
seeds on a flat path at SAIL's utilisation agreed on 0 of 20 days - so if the engine's own
output fed back in, one bad night would corrupt an open-ended run of nights, self-consistently.

That rule is enforced by the API, not by documentation: `was_in_ban()` returns the **official**
state and there is no method that returns a forecast as a prior state. Reading a forecast
forward is not discouraged here, it is unavailable. `scored_forecasts()` exists for reporting
and returns both columns together, which is a shape nothing can mistake for a seed.

**A date the calendar cannot vouch for refuses.** The store takes a `TradingCalendar` and asks
it, rather than inferring the calendar from which rows happen to exist - which is the bug that
`scripts/score_bans.py` shipped with, where hiding one ban list silently scored a forecast
against the wrong day and still reported zero errors.

**Every record names its source and the file behind it.** `seed` is an assertion from an
observation, `computed` is the engine's own work, `nse` is published fact. Three values rather
than two for the same reason `rules.yaml` has three threshold states, and the input hash is
what lets any day be traced back to the bytes it came from.

The store lives in `data/`, which is gitignored, because it is derived data rebuilt from
checksummed NSE files - so it never needs to be diffed in git. `dump_csv()` exists for the
times a person wants to read a day by eye.

**The runner's tables (#019).** A run on D writes its results through `day_transaction()`, one
SQLite transaction that every writer joins, so a crash part-way leaves nothing of D behind
(decision 3). Seven result tables accept writes *only* inside it - `measurement`, `reconciliation`,
`row6_check`, `row7_check`, `row7_not_checked`, `refusal`, and `stage_ran`, the marker that row 6
or row 7 reached an outcome (#023) - and each row carries the `run_id` that wrote it. Inside the
transaction
for D, `ban_state` takes D's `official` state and the *next trading day's* `forecast` and nothing
else: the two writes #011 says a run on D makes.

`run_log` is the opposite: it is written *outside* any day transaction and refuses to be written
inside one (decision 4), because a log entry that rolls back with the day cannot say the day
failed. Starting a run requires the crash-released `RunLock`; holding it proves no other run is
alive, so any `RUNNING` row left for D is a crashed run and is marked `ABANDONED` (decision 6).

"Missing" and "not run" are told apart by records, never by a NULL (decision 5): a missing input
is a `refusal` row inside the day's transaction, and "not run" is the absence of a `COMPLETED`
row in `run_log`.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
import sqlite3
import uuid
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from pathlib import Path

from sentinel.calendar import DayKind, TradingCalendar, UnknownDateError
from sentinel.engine import (
    EntityLimitCheck, EntityLimitResult, LimitCause, NotChecked, Reconciliation, ReductionCheck,
)
from sentinel.parsers import MwplRow
from sentinel.runlock import RunLock

__all__ = [
    "Source", "StateRecord", "WriteResult", "BanStateStore", "StoreError",
    "RunOutcome", "RunRecord", "RefusalStage", "Refusal", "ReconciliationSummary",
    "StageStatus", "MARKED_STAGES",
]

_SHA256 = re.compile(r"[0-9a-f]{64}")


class Source(Enum):
    """Where a record's `official` value came from. Not interchangeable."""

    SEED = "seed"
    COMPUTED = "computed"
    NSE = "nse"


class StoreError(Exception):
    """The store was asked to do something that would make its contents untrustworthy."""


@dataclass(frozen=True)
class StateRecord:
    """One scrip's ban state on one trading date."""

    isin: str
    trade_date: dt.date
    symbol: str
    official: bool | None
    forecast: bool | None
    source: Source
    input_sha256: str
    note: str = ""

    def __post_init__(self) -> None:
        if self.official is None and self.forecast is None:
            raise StoreError(
                f"{self.symbol} ({self.isin}) on {self.trade_date}: both official and forecast "
                f"are None, so the record says nothing. Write one or neither."
            )
        if self.source is Source.NSE and self.official is None:
            raise StoreError(
                f"{self.symbol} ({self.isin}) on {self.trade_date}: source is 'nse' but no "
                f"official state is recorded. A published fact with no value is not a fact."
            )
        _check_isin(self.isin, self.symbol, self.trade_date)
        if len(self.input_sha256) != 64:
            raise StoreError(
                f"{self.symbol} ({self.isin}) on {self.trade_date}: input_sha256 is "
                f"{self.input_sha256!r}. Every record names the file it came from, so a day can "
                f"be traced back to the bytes behind it."
            )


def _check_isin(isin: str, symbol: str, day: dt.date) -> None:
    if not isin or isin.strip().upper() in {"NA", "NAN", "-"}:
        raise StoreError(
            f"{symbol} on {day}: ISIN is {isin!r}. Index rows carry "
            f"no ISIN and are not stored - MWPL does not apply to them (#011 Q2)."
        )


class RunOutcome(Enum):
    """A run's state in `run_log`. Only RUNNING is not final."""

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    REFUSED = "REFUSED"          # the whole run refused: combineoi_D missing, or D unknown
    FAILED = "FAILED"            # it crashed and said so; the day's transaction rolled back
    ABANDONED = "ABANDONED"      # it crashed without saying so; found later with no lock held


@dataclass(frozen=True)
class RunRecord:
    """One row of `run_log`."""

    run_id: str
    trade_date: dt.date
    started_at: str
    finished_at: str | None
    outcome: RunOutcome
    reason: str
    input_checksums: dict[str, str]
    code_version: str
    dirty: bool
    rules_checksum: str
    calendar_checksum: str
    #: The rules file's keys by state, as the run read it: {"assumed": (...), "unverified": (...)}.
    #: Recorded, not re-derived, because only the exact file the run read can re-derive it.
    rules_status: dict[str, tuple[str, ...]]
    superseded_by: str | None


class RefusalStage(Enum):
    """Which consumer of D's inputs refused (#019 decision 1)."""

    OFFICIAL_STATE = "official_state"
    FORECAST = "forecast"
    SCORE = "score"
    RECONCILIATION = "reconciliation"
    ROW6 = "row6"
    ROW7 = "row7"            # entity limits (#016); added 12 Nov 2026


class StageStatus(Enum):
    """The outcome a stage reached on D, stored as its `stage_ran` marker (#023).

    "Not run" is not a status: it is no marker in the store, and None in `DayResults.row6` or
    `DayResults.row7`. Defined here beside `RefusalStage`, not in the runner, because the
    marker's table holds these values and the store cannot import the runner.
    """

    CHECKED = "checked"    # the stage ran its check; row 6's may hold zero checks, row 7's not
    FLAT = "flat"          # every book the stage checks is PropBook.flat(): nothing was held
    REFUSED = "refused"    # the whole stage refused; there is no result


#: The stages that write a `stage_ran` marker (#023). The table's CHECK lists exactly these.
MARKED_STAGES = (RefusalStage.ROW6, RefusalStage.ROW7)


@dataclass(frozen=True)
class Refusal:
    """A stated refusal: a result, not a failure (#019 decision 3).

    `subject` names what was refused - an ISIN for one scrip's forecast, or "" when the whole
    stage refused - so "SAIL's forecast refused" and "row 6 refused" are different rows.
    """

    trade_date: dt.date
    stage: RefusalStage
    subject: str
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise StoreError(
                f"{self.trade_date} {self.stage.value} {self.subject!r}: a refusal with no reason "
                f"is the silence it exists to replace."
            )


@dataclass(frozen=True)
class ReconciliationSummary:
    """What `reconciliation` stores: the count the report shows, and the range it does not."""

    trade_date: dt.date
    rows_total: int
    residual_count: int
    residual_min: float | None
    residual_min_symbol: str | None
    residual_max: float | None
    residual_max_symbol: str | None
    barred_count: int
    barred_held: int
    failures: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.failures


@dataclass(frozen=True)
class WriteResult:
    """What a targeted write actually did, so a re-run can be reported rather than guessed at."""

    day: dt.date
    column: str
    written: int
    unchanged: int

    @property
    def was_a_no_op(self) -> bool:
        """True when every value was already stored and identical - a safe, idempotent re-run."""
        return self.written == 0 and self.unchanged > 0

    def __str__(self) -> str:
        if self.was_a_no_op:
            return f"{self.day} {self.column}: already current, {self.unchanged} row(s) unchanged"
        return (
            f"{self.day} {self.column}: {self.written} written"
            + (f", {self.unchanged} already current" if self.unchanged else "")
        )


_SCHEMA = """
CREATE TABLE IF NOT EXISTS ban_state (
    isin          TEXT    NOT NULL,
    trade_date    TEXT    NOT NULL,
    symbol        TEXT    NOT NULL,
    official      INTEGER,
    forecast      INTEGER,
    source        TEXT    NOT NULL CHECK (source IN ('seed', 'computed', 'nse')),
    input_sha256  TEXT    NOT NULL CHECK (length(input_sha256) = 64),
    note          TEXT    NOT NULL DEFAULT '',
    written_at    TEXT    NOT NULL,
    PRIMARY KEY (isin, trade_date)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS ban_state_by_date ON ban_state (trade_date);
CREATE INDEX IF NOT EXISTS ban_state_by_symbol ON ban_state (symbol, trade_date);

-- #019 decision 4. Written outside the day's transaction, so it survives the day rolling back.
CREATE TABLE IF NOT EXISTS run_log (
    run_id             TEXT    PRIMARY KEY,
    trade_date         TEXT    NOT NULL,
    started_at         TEXT    NOT NULL,
    finished_at        TEXT,
    outcome            TEXT    NOT NULL
                       CHECK (outcome IN ('RUNNING','COMPLETED','REFUSED','FAILED','ABANDONED')),
    reason             TEXT    NOT NULL DEFAULT '',
    input_checksums    TEXT    NOT NULL,          -- JSON object, file name -> sha256
    code_version       TEXT    NOT NULL CHECK (length(code_version) > 0),
    dirty              INTEGER NOT NULL CHECK (dirty IN (0, 1)),
    rules_checksum     TEXT    NOT NULL CHECK (length(rules_checksum) = 64),
    calendar_checksum  TEXT    NOT NULL CHECK (length(calendar_checksum) = 64),
    rules_status       TEXT    NOT NULL          -- JSON {"assumed": [keys], "unverified": [keys]}
                       CHECK (json_type(rules_status, '$.assumed') IS 'array'
                              AND json_type(rules_status, '$.unverified') IS 'array'),  -- IS: a NULL must fail
    superseded_by      TEXT    REFERENCES run_log (run_id),
    CHECK ((outcome = 'RUNNING') = (finished_at IS NULL)),
    CHECK ((outcome = 'ABANDONED') = (superseded_by IS NOT NULL)),
    CHECK (outcome IN ('RUNNING', 'COMPLETED') OR length(reason) > 0)
);
CREATE INDEX IF NOT EXISTS run_log_by_date ON run_log (trade_date, started_at);

-- The inputs as published, not utilisation: nothing derived is stored beside its inputs.
CREATE TABLE IF NOT EXISTS measurement (
    isin               TEXT    NOT NULL,
    trade_date         TEXT    NOT NULL,
    symbol             TEXT    NOT NULL,
    scrip_name         TEXT    NOT NULL,
    mwpl               INTEGER NOT NULL CHECK (mwpl > 0),
    notional_oi        INTEGER NOT NULL CHECK (notional_oi >= 0),
    futeq_oi           TEXT    NOT NULL CHECK (CAST(futeq_oi AS REAL) >= 0),  -- exact, as published
    no_fresh_positions INTEGER NOT NULL CHECK (no_fresh_positions IN (0, 1)),
    headroom_shares    INTEGER,
    input_sha256       TEXT    NOT NULL CHECK (length(input_sha256) = 64),
    run_id             TEXT    NOT NULL REFERENCES run_log (run_id),
    written_at         TEXT    NOT NULL,
    PRIMARY KEY (isin, trade_date)
) WITHOUT ROWID;

-- Decision 7: the count is what the report shows; the range stays here.
CREATE TABLE IF NOT EXISTS reconciliation (
    trade_date          TEXT    PRIMARY KEY,
    rows_total          INTEGER NOT NULL CHECK (rows_total >= 0),
    residual_count      INTEGER NOT NULL CHECK (residual_count >= 0),
    residual_min        REAL,
    residual_min_symbol TEXT,
    residual_max        REAL,
    residual_max_symbol TEXT,
    barred_count        INTEGER NOT NULL CHECK (barred_count >= 0),
    barred_held         INTEGER NOT NULL CHECK (barred_held >= 0 AND barred_held <= barred_count),
    failures            TEXT    NOT NULL,          -- JSON array of strings; empty means ok
    input_sha256        TEXT    NOT NULL CHECK (length(input_sha256) = 64),
    run_id              TEXT    NOT NULL REFERENCES run_log (run_id),
    written_at          TEXT    NOT NULL,
    CHECK ((residual_count = 0) = (residual_min IS NULL)),
    CHECK ((residual_count = 0) = (residual_max IS NULL))
);

-- Row 6, one row per account per banned scrip. Decimals as text, so they come back exact.
CREATE TABLE IF NOT EXISTS row6_check (
    trade_date       TEXT    NOT NULL,
    tm               TEXT    NOT NULL CHECK (length(tm) > 0),
    ucc              TEXT    NOT NULL CHECK (length(ucc) > 0),
    isin             TEXT    NOT NULL,
    yesterday_delta  TEXT    NOT NULL,
    baseline         TEXT    NOT NULL,
    today_delta      TEXT    NOT NULL,
    permitted        INTEGER NOT NULL CHECK (permitted IN (0, 1)),
    reason           TEXT    NOT NULL CHECK (length(reason) > 0),
    run_id           TEXT    NOT NULL REFERENCES run_log (run_id),
    written_at       TEXT    NOT NULL,
    PRIMARY KEY (trade_date, tm, ucc, isin)
) WITHOUT ROWID;

-- Row 7, one row per (holder, scrip, limit) checked (#016). `accounts` is the JSON list of
-- [tm, ucc] pairs the gross was summed over. `cause` is NULL exactly on a pass, where there is
-- no breach to explain - that is "not applicable", enforced below, never "missing".
CREATE TABLE IF NOT EXISTS row7_check (
    trade_date     TEXT    NOT NULL,
    holder_id      TEXT    NOT NULL CHECK (length(holder_id) > 0),
    isin           TEXT    NOT NULL,
    limit_key      TEXT    NOT NULL CHECK (length(limit_key) > 0),
    accounts       TEXT    NOT NULL,
    gross_futeq    TEXT    NOT NULL,
    mwpl           INTEGER NOT NULL CHECK (mwpl > 0),
    limit_shares   TEXT    NOT NULL,
    excess_shares  TEXT    NOT NULL,
    permitted      INTEGER NOT NULL CHECK (permitted IN (0, 1)),
    cause          TEXT    CHECK (cause IN ('active', 'passive', 'unknown')),
    reason         TEXT    NOT NULL CHECK (length(reason) > 0),
    run_id         TEXT    NOT NULL REFERENCES run_log (run_id),
    written_at     TEXT    NOT NULL,
    PRIMARY KEY (trade_date, holder_id, isin, limit_key),
    CHECK ((permitted = 1) = (cause IS NULL))
) WITHOUT ROWID;

-- Row 7's checks that could not be made, one per (holder, scrip, limit): who a scrip's
-- refusal affected. The refusal itself - what could not be done, and why - is in `refusal`.
CREATE TABLE IF NOT EXISTS row7_not_checked (
    trade_date  TEXT    NOT NULL,
    holder_id   TEXT    NOT NULL CHECK (length(holder_id) > 0),
    isin        TEXT    NOT NULL,
    limit_key   TEXT    NOT NULL CHECK (length(limit_key) > 0),
    reason      TEXT    NOT NULL CHECK (length(reason) > 0),
    run_id      TEXT    NOT NULL REFERENCES run_log (run_id),
    written_at  TEXT    NOT NULL,
    PRIMARY KEY (trade_date, holder_id, isin, limit_key)
) WITHOUT ROWID;

-- Decision 5: a missing input is stated here, never left as a NULL somewhere else.
CREATE TABLE IF NOT EXISTS refusal (
    trade_date  TEXT    NOT NULL,
    stage       TEXT    NOT NULL
                CHECK (stage IN ('official_state','forecast','score','reconciliation','row6',
                                 'row7')),
    subject     TEXT    NOT NULL,                  -- an ISIN, or '' for the whole stage
    reason      TEXT    NOT NULL CHECK (length(reason) > 0),
    run_id      TEXT    NOT NULL REFERENCES run_log (run_id),
    written_at  TEXT    NOT NULL,
    PRIMARY KEY (trade_date, stage, subject)
) WITHOUT ROWID;

-- #023: one marker per stage per day, from the stage's own outcome. No marker = not run.
CREATE TABLE IF NOT EXISTS stage_ran (
    trade_date  TEXT    NOT NULL,
    stage       TEXT    NOT NULL CHECK (stage IN ('row6','row7')),
    status      TEXT    NOT NULL CHECK (status IN ('checked','flat','refused')),
    run_id      TEXT    NOT NULL REFERENCES run_log (run_id),
    written_at  TEXT    NOT NULL,
    PRIMARY KEY (trade_date, stage)
) WITHOUT ROWID;
"""


class BanStateStore:
    """Point-in-time ban state. Open it, write days into it, ask it about one date at a time."""

    def __init__(self, path: str | Path, calendar: TradingCalendar) -> None:
        self.path = Path(path)
        self.calendar = calendar
        self._conn = sqlite3.connect(self.path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._refuse_a_store_without_markers()
        self._conn.executescript(_SCHEMA)
        self._refuse_an_old_format()
        #: The open day transaction, as (trade_date, run_id), or None.
        self._txn: tuple[dt.date, str] | None = None

    def _refuse_a_store_without_markers(self) -> None:
        """A store whose runs predate `stage_ran` (#023) is refused, before the schema runs.

        Its days hold row 6 and row 7 rows with no marker, which #023 item 7 reads as
        inconsistent, so every one of them would report that way. Checked before
        CREATE TABLE IF NOT EXISTS, because once that has run the table exists, empty, and the
        next open could not tell this store from a new one. The remedy is the other two old
        formats': move it aside and re-run its days."""
        tables = {r["name"] for r in self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "run_log" in tables and "stage_ran" not in tables:
            self._conn.close()
            raise StoreError(
                f"{self.path}: this store has a run log but no stage_ran table, so its runs "
                f"predate stage markers (#023, 13 Nov 2026) and every row 6 and row 7 result in "
                f"it would read as inconsistent. Move it aside and re-run its days to rebuild it."
            )

    def _refuse_an_old_format(self) -> None:
        """A store created before 11 Nov 2026 keeps `measurement.futeq_oi` as REAL, because the
        schema is CREATE TABLE IF NOT EXISTS. SQLite's REAL affinity would then turn the exact
        text written now back into a float, silently - the bug the Decimal change fixed. So such a
        store is refused, and rebuilt by re-running its days, rather than opened.

        For the same reason a store created before 12 Nov 2026 has a `refusal` CHECK that does not
        list 'row7', and the first row 7 refusal would fail inside the day transaction, rolling
        the whole day back. It is refused at open instead, with the same remedy."""
        declared = {r["name"]: r["type"].upper()
                    for r in self._conn.execute("PRAGMA table_info(measurement)")}
        if declared.get("futeq_oi") != "TEXT":
            self._conn.close()
            raise StoreError(
                f"{self.path}: measurement.futeq_oi is {declared.get('futeq_oi')!r}, not TEXT. "
                f"This store predates exact FutEq OI (11 Nov 2026), and SQLite would round every "
                f"new figure back to a float. Move it aside and re-run its days to rebuild it."
            )
        refusal_sql = self._conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'refusal'"
        ).fetchone()["sql"]
        missing = [s.value for s in RefusalStage if f"'{s.value}'" not in refusal_sql]
        if missing:
            self._conn.close()
            raise StoreError(
                f"{self.path}: the refusal table does not accept stage(s) {', '.join(missing)}. "
                f"This store predates them, so their first refusal would roll back the whole day. "
                f"Move it aside and re-run its days to rebuild it."
            )
        # The same trap for stage_ran's CHECKs, the day a stage or a status is added.
        marker_sql = self._conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'stage_ran'"
        ).fetchone()["sql"]
        missing = [v for v in (*(s.value for s in MARKED_STAGES), *(s.value for s in StageStatus))
                   if f"'{v}'" not in marker_sql]
        if missing:
            self._conn.close()
            raise StoreError(
                f"{self.path}: the stage_ran table does not accept {', '.join(missing)}. This "
                f"store predates them, so their first marker would roll back the whole day. "
                f"Move it aside and re-run its days to rebuild it."
            )

    # -- transactions -----------------------------------------------------------------------

    @contextmanager
    def _write(self) -> Iterator[None]:
        """One write. Joins an open day transaction; otherwise is its own transaction.

        Without this, the `with self._conn:` each writer used to open would COMMIT an enclosing
        day transaction on its way out - the first stage's write would make every later stage's
        crash leave half a day behind, which is what #019 decision 3 forbids.
        """
        if self._txn is not None:
            yield
            return
        with self._conn:
            self._conn.execute("BEGIN")
            yield

    @contextmanager
    def day_transaction(self, day: dt.date, run_id: str) -> Iterator[BanStateStore]:
        """Everything run `run_id` writes for `day`, committed together or not at all.

        Refuses to nest, refuses a date the calendar cannot vouch for, and refuses a run that is
        not RUNNING for this same date - so results can only ever be attributed to the run that
        is alive and computing them.
        """
        if self._txn is not None:
            raise StoreError(
                f"a day transaction for {self._txn[0]} is already open; one day at a time"
            )
        self._check_session(day)
        run = self.run(run_id)
        if run.outcome is not RunOutcome.RUNNING or run.trade_date != day:
            raise StoreError(
                f"run {run_id} is {run.outcome.value} for {run.trade_date}; results for {day} can "
                f"only be written by a RUNNING run for {day}"
            )
        self._conn.execute("BEGIN IMMEDIATE")
        self._txn = (day, run_id)
        try:
            yield self
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        else:
            self._conn.execute("COMMIT")
        finally:
            self._txn = None

    @property
    def in_day_transaction(self) -> bool:
        return self._txn is not None

    def _check_session(self, day: dt.date) -> None:
        kind = self.calendar.kind(day)
        if kind is DayKind.UNKNOWN:
            raise UnknownDateError(
                f"refusing to store state for {day}: no verified calendar covers it. The "
                f"calendar is loaded from config/calendar_2026.csv."
            )
        if not kind.has_session:
            raise StoreError(
                f"refusing to store state for {day}: the verified calendar says it is a "
                f"{kind.value}. A non-trading day with data is a contradiction - either the "
                f"calendar is wrong or the file is for another date, and both need a person."
            )

    def _guard_ban_state(self, day: dt.date, column: str) -> None:
        """Inside run D's transaction, only D's official state and D+1's forecast may be written."""
        if self._txn is None:
            return
        run_day = self._txn[0]
        # Walk the calendar only for a forecast. D's own official state does not depend on
        # D's next trading day, so an unverified next day (#019 item 13) must not block it.
        allowed = (self.calendar.next_trading_day(run_day) if column == "forecast"
                   else run_day)
        if allowed != day:
            raise StoreError(
                f"the run for {run_day} may write {column} for {allowed} only, not "
                f"{day}. A run on D stores D's official state and the next trading day's "
                f"forecast (#011); anything else would be another day's result."
            )

    def _require_txn(self, day: dt.date) -> str:
        """Result tables take writes only inside the day transaction for that day."""
        if self._txn is None:
            raise StoreError(
                f"results for {day} are written only inside day_transaction(), so that a crash "
                f"leaves none of them behind (#019 decision 3)"
            )
        if self._txn[0] != day:
            raise StoreError(
                f"the open day transaction is for {self._txn[0]}, not {day}"
            )
        return self._txn[1]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> BanStateStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- writing --------------------------------------------------------------------------

    def record_day(self, records: tuple[StateRecord, ...], *, replace: bool = False) -> int:
        """Write one trading day's records, all or nothing.

        A single transaction, so a crash part-way through cannot leave half a day behind - the
        day is either there or it is not. Refuses a batch spanning more than one date, because
        "one day's state" is the unit the engine reads and a partial write of two days is a
        state nothing can interpret.
        """
        if not records:
            return 0

        dates = {r.trade_date for r in records}
        if len(dates) > 1:
            raise StoreError(
                f"record_day() given {len(dates)} dates ({min(dates)}..{max(dates)}). "
                f"Write one day at a time so that a failure leaves whole days behind, not parts."
            )
        day = dates.pop()

        # A special session's data is real and is stored; whether it CHAINS is a separate
        # question the calendar refuses until verified. That is the whole point of
        # SPECIAL_SESSION being a state rather than a flag.
        self._check_session(day)
        self._guard_ban_state(day, "record")

        seen: set[str] = set()
        for r in records:
            if r.isin in seen:
                raise StoreError(
                    f"{day}: ISIN {r.isin} appears twice in one batch ({r.symbol}). The primary "
                    f"key would reject it, but catching it here names the symbol."
                )
            seen.add(r.isin)

        verb = "INSERT OR REPLACE" if replace else "INSERT"
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        rows = [
            (r.isin, r.trade_date.isoformat(), r.symbol,
             None if r.official is None else int(r.official),
             None if r.forecast is None else int(r.forecast),
             r.source.value, r.input_sha256, r.note, now)
            for r in records
        ]
        try:
            with self._write():
                self._conn.executemany(
                    f"{verb} INTO ban_state "
                    "(isin, trade_date, symbol, official, forecast, source, input_sha256, "
                    " note, written_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    rows,
                )
        except sqlite3.IntegrityError as exc:
            raise StoreError(
                f"{day}: {exc}. State for that scrip and date already exists; pass "
                f"replace=True only when you mean to overwrite a day, which is a decision, "
                f"not a retry."
            ) from exc
        return len(rows)

    # -- targeted writes, one column at a time --------------------------------------------
    #
    # A record for (isin, D) holds NSE's `official` state for D and the engine's `forecast`
    # for D, and those two arrive at different times from different files: the forecast is
    # computed after D-1's close, the official state is published for D itself. So each
    # writer fills in its own column and leaves the other alone, rather than the whole row
    # being written once.
    #
    # Re-running with the same input is a no-op, which is what makes a re-run safe. Re-running
    # with a DIFFERENT value for a column already written is a conflict and is reported with
    # both values: it means the input file changed under us, and that is a finding rather than
    # something to overwrite. `replace=True` exists for when overwriting is the intention.

    def record_official(
        self, day: dt.date, values: Mapping[str, tuple[str, bool]], *,
        input_sha256: str, source: Source = Source.NSE, replace: bool = False,
    ) -> WriteResult:
        """Write NSE's published state for `day`. `values` maps ISIN to `(symbol, in_ban)`."""
        return self._write_column(day, "official", values, input_sha256, source, replace)

    def record_forecast(
        self, day: dt.date, values: Mapping[str, tuple[str, bool]], *,
        input_sha256: str, source: Source = Source.COMPUTED, replace: bool = False,
    ) -> WriteResult:
        """Write the engine's forecast for `day`. Never read back as a seed - see `was_in_ban`."""
        return self._write_column(day, "forecast", values, input_sha256, source, replace)

    def _write_column(
        self, day: dt.date, column: str, values: Mapping[str, tuple[str, bool]],
        input_sha256: str, source: Source, replace: bool,
    ) -> WriteResult:
        if column not in ("official", "forecast"):
            raise StoreError(f"unknown column {column!r}")
        if len(input_sha256) != 64:
            raise StoreError(
                f"input_sha256 is {input_sha256!r}. Every record names the file it came from, "
                f"so a day can be traced back to the bytes behind it."
            )

        self._check_session(day)
        self._guard_ban_state(day, column)

        existing = {
            r["isin"]: r[column]
            for r in self._conn.execute(
                f"SELECT isin, {column} FROM ban_state WHERE trade_date = ?", (day.isoformat(),)
            )
        }

        to_write: list[tuple] = []
        unchanged = 0
        conflicts: list[tuple[str, str, bool, bool]] = []
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

        for isin, (symbol, value) in values.items():
            StateRecord(                      # reuse the invariants rather than repeat them
                isin=isin, trade_date=day, symbol=symbol,
                official=value if column == "official" else None,
                forecast=value if column == "forecast" else None,
                source=source, input_sha256=input_sha256,
            )
            prior = existing.get(isin, "absent")
            if prior is not None and prior != "absent" and bool(prior) != value and not replace:
                conflicts.append((isin, symbol, bool(prior), value))
                continue
            if prior is not None and prior != "absent" and bool(prior) == value:
                unchanged += 1
                continue
            to_write.append((isin, day.isoformat(), symbol, int(value), source.value,
                             input_sha256, now))

        if conflicts:
            lines = "\n".join(
                f"    {sym} ({isin}): stored {was}, now given {now_}"
                for isin, sym, was, now_ in conflicts[:10]
            )
            raise StoreError(
                f"{day}: {len(conflicts)} scrip(s) already have a different {column} value. "
                f"The input file has changed since it was loaded, which is a finding rather "
                f"than something to overwrite. Pass replace=True only when that is the "
                f"intention.\n{lines}"
            )

        if to_write:
            other = "forecast" if column == "official" else "official"
            with self._write():
                self._conn.executemany(
                    f"INSERT INTO ban_state "
                    f"(isin, trade_date, symbol, {column}, {other}, source, input_sha256, "
                    f" note, written_at) VALUES (?,?,?,?,NULL,?,?,'',?) "
                    f"ON CONFLICT (isin, trade_date) DO UPDATE SET "
                    f"  {column} = excluded.{column}, "
                    f"  symbol = excluded.symbol, "
                    f"  source = excluded.source, "
                    f"  input_sha256 = excluded.input_sha256, "
                    f"  written_at = excluded.written_at",
                    to_write,
                )
        return WriteResult(day=day, column=column, written=len(to_write), unchanged=unchanged)

    # -- run_log: outside every day transaction (#019 decisions 4 and 6) -------------------

    def start_run(
        self, trade_date: dt.date, *, lock: RunLock, input_checksums: Mapping[str, str],
        code_version: str, dirty: bool, rules_checksum: str, calendar_checksum: str,
        rules_status: Mapping[str, Iterable[str]],
    ) -> RunRecord:
        """Write a RUNNING row for `trade_date`, and abandon any RUNNING row it supersedes.

        Requires the run lock. Holding it proves no other run is alive, so a RUNNING row already
        there for this date belongs to a run that crashed: it is marked ABANDONED with the time
        and the new run's id, in the same write as the new row. Nothing else needs cleaning up,
        because the crashed run's day transaction rolled back with it.

        Deliberately does not ask the calendar: a run for an unknown date must still be able to
        log that it REFUSED.

        `rules_status` is the rules file's keys by state, `{"assumed": [...], "unverified": [...]}`
        - `Rules.assumed` and `Rules.unverified` - so the report footer can name the thresholds the
        run used on an assumption and the ones it refused. Keys, never the loader's warning text.
        """
        self._refuse_inside_txn("start_run")
        if not lock.held:
            raise StoreError(
                "start_run() needs the run lock held. Without it, a RUNNING row cannot be told "
                "apart from a run that is still alive (#019 decision 6)."
            )
        checksums = dict(input_checksums)
        for name, sha in checksums.items():
            if not isinstance(sha, str) or not _SHA256.fullmatch(sha):
                raise StoreError(f"input checksum for {name} is {sha!r}, not a sha256")
        for label, sha in (("rules_checksum", rules_checksum), ("calendar_checksum", calendar_checksum)):
            if not _SHA256.fullmatch(sha):
                raise StoreError(f"{label} is {sha!r}, not a sha256")
        if not code_version.strip():
            raise StoreError("code_version is blank; a run that cannot name its code is not reproducible")
        status = _check_rules_status(rules_status)

        run_id = uuid.uuid4().hex
        now = _now()
        with self._write():
            self._conn.execute(
                "INSERT INTO run_log (run_id, trade_date, started_at, finished_at, outcome, reason, "
                " input_checksums, code_version, dirty, rules_checksum, calendar_checksum, "
                " rules_status, superseded_by) VALUES (?,?,?,NULL,'RUNNING','',?,?,?,?,?,?,NULL)",
                (run_id, trade_date.isoformat(), now, json.dumps(checksums, sort_keys=True),
                 code_version, int(dirty), rules_checksum, calendar_checksum,
                 json.dumps(status, sort_keys=True)),
            )
            self._conn.execute(
                "UPDATE run_log SET outcome = 'ABANDONED', finished_at = ?, superseded_by = ?, "
                " reason = 'found RUNNING with no run lock held: the run crashed' "
                "WHERE trade_date = ? AND outcome = 'RUNNING' AND run_id != ?",
                (now, run_id, trade_date.isoformat(), run_id),
            )
        return self.run(run_id)

    def finish_run(
        self, run_id: str, outcome: RunOutcome, reason: str = "", *, lock: RunLock,
    ) -> RunRecord:
        """Close a RUNNING run as COMPLETED, REFUSED or FAILED. Called after the day commits or
        rolls back, never inside it - a FAILED that rolled back with the day would say nothing."""
        self._refuse_inside_txn("finish_run")
        if not lock.held:
            raise StoreError("finish_run() needs the run lock held, as start_run() did")
        if outcome not in (RunOutcome.COMPLETED, RunOutcome.REFUSED, RunOutcome.FAILED):
            raise StoreError(f"a run finishes as COMPLETED, REFUSED or FAILED, not {outcome.value}")
        if outcome is not RunOutcome.COMPLETED and not reason.strip():
            raise StoreError(f"a {outcome.value} run must say why")
        run = self.run(run_id)
        if run.outcome is not RunOutcome.RUNNING:
            raise StoreError(
                f"run {run_id} is already {run.outcome.value}; a run finishes once"
            )
        with self._write():
            self._conn.execute(
                "UPDATE run_log SET outcome = ?, reason = ?, finished_at = ? WHERE run_id = ?",
                (outcome.value, reason, _now(), run_id),
            )
        return self.run(run_id)

    def run(self, run_id: str) -> RunRecord:
        row = self._conn.execute("SELECT * FROM run_log WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise StoreError(f"no run {run_id} in run_log")
        return _run_record(row)

    def runs_for(self, trade_date: dt.date) -> tuple[RunRecord, ...]:
        """Every run for `trade_date`, oldest first, including abandoned and refused ones."""
        rows = self._conn.execute(
            "SELECT * FROM run_log WHERE trade_date = ? ORDER BY started_at, run_id",
            (trade_date.isoformat(),),
        ).fetchall()
        return tuple(_run_record(r) for r in rows)

    def last_completed_run(self, trade_date: dt.date) -> RunRecord | None:
        """The latest COMPLETED run for `trade_date`. None is "not run" in #019's sense."""
        completed = [r for r in self.runs_for(trade_date) if r.outcome is RunOutcome.COMPLETED]
        return completed[-1] if completed else None

    def _refuse_inside_txn(self, what: str) -> None:
        if self._txn is not None:
            raise StoreError(
                f"{what}() inside the day transaction for {self._txn[0]}: the run log is written "
                f"outside it, so that it survives the day rolling back (#019 decision 4)"
            )

    # -- the result tables: inside the day transaction only (#019 decision 3) -------------

    def record_measurements(self, rows: Iterable[MwplRow], *, input_sha256: str) -> WriteResult:
        """D's combineoi rows as published: MWPL, FutEq OI, the flag. Not utilisation."""
        rows = tuple(rows)
        day = _single_date(rows, "record_measurements")
        run_id = self._require_txn(day)
        _check_sha(input_sha256)
        values = []
        for r in rows:
            _check_isin(r.isin, r.symbol, day)
            values.append({
                "isin": r.isin, "trade_date": day.isoformat(), "symbol": r.symbol,
                "scrip_name": r.scrip_name, "mwpl": r.mwpl, "notional_oi": r.notional_oi,
                "futeq_oi": str(r.futeq_oi), "no_fresh_positions": int(r.no_fresh_positions),
                "headroom_shares": r.headroom_shares, "input_sha256": input_sha256,
            })
        return self._insert_results("measurement", ("isin", "trade_date"), values, day, run_id)

    def record_reconciliation(self, rec: Reconciliation, *, input_sha256: str) -> WriteResult:
        run_id = self._require_txn(rec.trade_date)
        _check_sha(input_sha256)
        lo = min(rec.residuals, key=lambda r: r.residual, default=None)
        hi = max(rec.residuals, key=lambda r: r.residual, default=None)
        value = {
            "trade_date": rec.trade_date.isoformat(), "rows_total": rec.rows_total,
            "residual_count": len(rec.residuals),
            "residual_min": None if lo is None else float(lo.residual),
            "residual_min_symbol": None if lo is None else lo.symbol,
            "residual_max": None if hi is None else float(hi.residual),
            "residual_max_symbol": None if hi is None else hi.symbol,
            "barred_count": len(rec.barred), "barred_held": sum(1 for b in rec.barred if b.held),
            "failures": json.dumps(list(rec.failures)), "input_sha256": input_sha256,
        }
        return self._insert_results("reconciliation", ("trade_date",), [value], rec.trade_date, run_id)

    def record_row6_checks(self, checks: Iterable[ReductionCheck]) -> WriteResult:
        checks = tuple(checks)
        day = _single_date(checks, "record_row6_checks")
        run_id = self._require_txn(day)
        values = [{
            "trade_date": day.isoformat(), "tm": c.tm, "ucc": c.ucc, "isin": c.isin,
            "yesterday_delta": str(c.yesterday_delta), "baseline": str(c.baseline),
            "today_delta": str(c.today_delta), "permitted": int(c.permitted), "reason": c.reason,
        } for c in checks]
        return self._insert_results("row6_check", ("trade_date", "tm", "ucc", "isin"), values,
                                    day, run_id)

    def record_row7(self, result: EntityLimitResult) -> tuple[WriteResult, ...]:
        """Row 7's checks and not-checked entries for one day, into their two tables.

        An empty result is refused, as every writer refuses one: a flat book writes nothing and
        the COMPLETED run with no row 7 refusal is what says so. A key may sit in only one of
        the two tables. Each table's own re-run rule cannot see that: a re-run that moved a
        (holder, scrip, limit) from checked to not checked would add a row to one table and
        leave the old row in the other, so the day would say both.
        """
        if not isinstance(result, EntityLimitResult):
            raise StoreError(f"record_row7() takes an EntityLimitResult, not {type(result).__name__}")
        day = _single_date((*result.checks, *result.not_checked), "record_row7")
        run_id = self._require_txn(day)

        for table, entries in (("row7_not_checked", result.checks),
                               ("row7_check", result.not_checked)):
            for e in entries:
                clash = self._conn.execute(
                    f"SELECT 1 FROM {table} WHERE trade_date = ? AND holder_id = ? AND isin = ? "
                    f"AND limit_key = ?", (day.isoformat(), *e.key)).fetchone()
                if clash is not None:
                    raise StoreError(
                        f"row 7 for {day}: {e.key} is already stored in {table}. A re-run that "
                        f"moves a check between checked and not checked has a changed input, "
                        f"which refuses rather than overwrites (#019 decision 11)."
                    )

        key = ("trade_date", "holder_id", "isin", "limit_key")
        written = []
        if result.checks:
            written.append(self._insert_results("row7_check", key, [{
                "trade_date": day.isoformat(), "holder_id": c.holder_id, "isin": c.isin,
                "limit_key": c.limit_key, "accounts": json.dumps([list(a) for a in c.accounts]),
                "gross_futeq": str(c.gross_futeq), "mwpl": c.mwpl,
                "limit_shares": str(c.limit_shares), "excess_shares": str(c.excess_shares),
                "permitted": int(c.permitted),
                "cause": None if c.cause is None else c.cause.value, "reason": c.reason,
            } for c in result.checks], day, run_id))
        if result.not_checked:
            written.append(self._insert_results("row7_not_checked", key, [{
                "trade_date": day.isoformat(), "holder_id": n.holder_id, "isin": n.isin,
                "limit_key": n.limit_key, "reason": n.reason,
            } for n in result.not_checked], day, run_id))
        return tuple(written)

    def record_refusals(self, refusals: Iterable[Refusal]) -> WriteResult:
        refusals = tuple(refusals)
        day = _single_date(refusals, "record_refusals")
        run_id = self._require_txn(day)
        values = [{
            "trade_date": day.isoformat(), "stage": f.stage.value, "subject": f.subject,
            "reason": f.reason,
        } for f in refusals]
        return self._insert_results("refusal", ("trade_date", "stage", "subject"), values,
                                    day, run_id)

    def record_stage_ran(self, day: dt.date, stage: RefusalStage,
                         status: StageStatus) -> WriteResult:
        """The marker that `stage` reached `status` on `day` (#023). Called by `write_day()`
        from the stage's own outcome, never unconditionally.

        An identical re-run is a no-op, as for every result table. A re-run whose status
        differs is refused here, before `_insert_results()`, so the error can say which stage
        moved and from what: the day would otherwise hold the old status's rows beside the new
        one's (#022's correction), and only v1.0's supersede may replace a day.
        """
        if not isinstance(stage, RefusalStage) or stage not in MARKED_STAGES:
            raise StoreError(
                f"stage_ran for {day}: {stage!r} is not a stage that writes a marker; "
                f"only {', '.join(s.value for s in MARKED_STAGES)} do (#023)")
        if not isinstance(status, StageStatus):
            raise StoreError(
                f"stage_ran for {day}: status must be a StageStatus, not {type(status).__name__}")
        run_id = self._require_txn(day)
        prior = self._conn.execute(
            "SELECT status FROM stage_ran WHERE trade_date = ? AND stage = ?",
            (day.isoformat(), stage.value)).fetchone()
        if prior is not None and prior["status"] != status.value:
            raise StoreError(
                f"stage_ran for {day}: {stage.value} was {prior['status']}, now {status.value}. "
                f"A re-run that changes a stage's outcome would leave both on the day. Re-run "
                f"{day} into a fresh store until v1.0's supersede exists (#023 item 6).")
        return self._insert_results(
            "stage_ran", ("trade_date", "stage"),
            [{"trade_date": day.isoformat(), "stage": stage.value, "status": status.value}],
            day, run_id)

    def _insert_results(
        self, table: str, key: tuple[str, ...], values: list[dict], day: dt.date, run_id: str,
    ) -> WriteResult:
        """Insert new rows; an identical row is a no-op; a different one is a conflict.

        The same re-run rule as `ban_state` (#019 decision 11): identical inputs give identical
        results, and a changed result is a finding to report, never something to overwrite.
        `run_id` and `written_at` are bookkeeping and are not compared - a clean re-run keeps the
        first run's attribution, whose input checksums were the same.
        """
        seen: set[tuple] = set()
        to_write, unchanged, conflicts = [], 0, []
        for v in values:
            k = tuple(v[c] for c in key)
            if k in seen:
                raise StoreError(f"{table}: {dict(zip(key, k))} appears twice in one batch")
            seen.add(k)
            prior = self._conn.execute(
                f"SELECT * FROM {table} WHERE " + " AND ".join(f"{c} = ?" for c in key), k
            ).fetchone()
            if prior is None:
                to_write.append(v)
            elif all(prior[c] == v[c] for c in v):
                unchanged += 1
            else:
                diff = {c: (prior[c], v[c]) for c in v if prior[c] != v[c]}
                conflicts.append((dict(zip(key, k)), diff))
        if conflicts:
            lines = "\n".join(f"    {k}: stored vs now {d}" for k, d in conflicts[:10])
            raise StoreError(
                f"{table} for {day}: {len(conflicts)} row(s) differ from what is stored. A changed "
                f"result means a changed input, which refuses rather than overwrites (#019 "
                f"decision 11).\n{lines}"
            )
        if to_write:
            cols = list(to_write[0]) + ["run_id", "written_at"]
            now = _now()
            with self._write():
                self._conn.executemany(
                    f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                    [tuple(v.values()) + (run_id, now) for v in to_write],
                )
        return WriteResult(day=day, column=table, written=len(to_write), unchanged=unchanged)

    # -- reading the result tables, for the report ----------------------------------------
    #
    # None or an empty tuple means only "nothing stored". Why - refused, or not run - is in
    # `refusals()` and `run_log`, which is decision 5.

    def measurements(self, day: dt.date) -> tuple[MwplRow, ...]:
        """D's stored rows, rebuilt as `MwplRow` so their invariants are checked on the way out."""
        rows = self._conn.execute(
            "SELECT * FROM measurement WHERE trade_date = ? ORDER BY symbol", (day.isoformat(),)
        ).fetchall()
        return tuple(MwplRow(
            trade_date=day, isin=r["isin"], scrip_name=r["scrip_name"], symbol=r["symbol"],
            mwpl=r["mwpl"], notional_oi=r["notional_oi"], futeq_oi=Decimal(r["futeq_oi"]),
            no_fresh_positions=bool(r["no_fresh_positions"]), headroom_shares=r["headroom_shares"],
        ) for r in rows)

    def reconciliation(self, day: dt.date) -> ReconciliationSummary | None:
        r = self._conn.execute(
            "SELECT * FROM reconciliation WHERE trade_date = ?", (day.isoformat(),)
        ).fetchone()
        if r is None:
            return None
        return ReconciliationSummary(
            trade_date=day, rows_total=r["rows_total"], residual_count=r["residual_count"],
            residual_min=r["residual_min"], residual_min_symbol=r["residual_min_symbol"],
            residual_max=r["residual_max"], residual_max_symbol=r["residual_max_symbol"],
            barred_count=r["barred_count"], barred_held=r["barred_held"],
            failures=tuple(json.loads(r["failures"])),
        )

    def row6_checks(self, day: dt.date) -> tuple[ReductionCheck, ...]:
        rows = self._conn.execute(
            "SELECT * FROM row6_check WHERE trade_date = ? ORDER BY tm, ucc, isin",
            (day.isoformat(),),
        ).fetchall()
        return tuple(ReductionCheck(
            trade_date=day, tm=r["tm"], ucc=r["ucc"], isin=r["isin"],
            yesterday_delta=Decimal(r["yesterday_delta"]), baseline=Decimal(r["baseline"]),
            today_delta=Decimal(r["today_delta"]), permitted=bool(r["permitted"]),
            reason=r["reason"],
        ) for r in rows)

    def row7_result(self, day: dt.date) -> EntityLimitResult:
        """D's row 7 checks and not-checked entries, rebuilt so their invariants are checked on
        the way out. Empty means only "nothing stored"; why is in `refusals()` and `run_log`."""
        d = day.isoformat()
        checks = tuple(EntityLimitCheck(
            trade_date=day, holder_id=r["holder_id"], isin=r["isin"], limit_key=r["limit_key"],
            accounts=tuple(tuple(a) for a in json.loads(r["accounts"])),
            gross_futeq=Decimal(r["gross_futeq"]), mwpl=r["mwpl"],
            limit_shares=Decimal(r["limit_shares"]), excess_shares=Decimal(r["excess_shares"]),
            permitted=bool(r["permitted"]),
            cause=None if r["cause"] is None else LimitCause(r["cause"]), reason=r["reason"],
        ) for r in self._conn.execute(
            "SELECT * FROM row7_check WHERE trade_date = ? ORDER BY holder_id, isin, limit_key",
            (d,)).fetchall())
        not_checked = tuple(NotChecked(
            trade_date=day, holder_id=r["holder_id"], isin=r["isin"], limit_key=r["limit_key"],
            reason=r["reason"],
        ) for r in self._conn.execute(
            "SELECT * FROM row7_not_checked WHERE trade_date = ? "
            "ORDER BY holder_id, isin, limit_key", (d,)).fetchall())
        return EntityLimitResult(checks, not_checked)

    def refusals(self, day: dt.date) -> tuple[Refusal, ...]:
        rows = self._conn.execute(
            "SELECT * FROM refusal WHERE trade_date = ? ORDER BY stage, subject",
            (day.isoformat(),),
        ).fetchall()
        return tuple(Refusal(trade_date=day, stage=RefusalStage(r["stage"]), subject=r["subject"],
                             reason=r["reason"]) for r in rows)

    def stages_ran(self, day: dt.date) -> dict[RefusalStage, StageStatus]:
        """D's stage markers (#023). A stage missing from the dict has no marker: not run.
        Whether the marker agrees with the stage's rows is the report's check, made by
        rebuilding the stage's outcome type, which the store cannot import."""
        return {RefusalStage(r["stage"]): StageStatus(r["status"]) for r in self._conn.execute(
            "SELECT stage, status FROM stage_ran WHERE trade_date = ? ORDER BY stage",
            (day.isoformat(),)).fetchall()}

    # -- reading. `official` only, by design ----------------------------------------------

    def was_in_ban(self, isin: str, day: dt.date) -> bool:
        """NSE's **official** state for `isin` on `day`. This is the only seed the engine gets.

        There is deliberately no equivalent that returns a forecast. #012 decision 2: the
        engine's own output must never feed back into the engine, so the unsafe call does not
        exist rather than being documented as unwise.
        """
        row = self._conn.execute(
            "SELECT official FROM ban_state WHERE isin = ? AND trade_date = ?",
            (isin, day.isoformat()),
        ).fetchone()
        if row is None:
            raise StoreError(
                f"no state stored for {isin} on {day}. A missing previous state is not 'free' - "
                f"see #012: answer scrips outside the 80-95% band normally and refuse the ones "
                f"inside it."
            )
        if row["official"] is None:
            raise StoreError(
                f"state for {isin} on {day} has no official value: NSE's list for that day was "
                f"never loaded. It is deliberately not filled in from the forecast, which would "
                f"be the feedback loop #012 exists to prevent."
            )
        return bool(row["official"])

    def official_ban_set(self, day: dt.date) -> frozenset[str]:
        """Every ISIN officially in ban on `day`. Empty set and 'nothing stored' are different."""
        if not self.has_day(day):
            raise StoreError(f"no state stored for {day} at all, which is not the same as no bans")
        rows = self._conn.execute(
            "SELECT isin FROM ban_state WHERE trade_date = ? AND official = 1",
            (day.isoformat(),),
        ).fetchall()
        return frozenset(r["isin"] for r in rows)

    def seed_for(self, day: dt.date) -> frozenset[str]:
        """The official ban set for the previous **trading** day, for seeding `day`'s run.

        Asks the calendar rather than looking for the most recent date with rows. "The last day
        I have data for" is the inferring answer and it is wrong exactly when a file is missing.
        """
        previous = self.calendar.previous_trading_day(day)
        return self.official_ban_set(previous)

    def has_day(self, day: dt.date) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM ban_state WHERE trade_date = ? LIMIT 1", (day.isoformat(),)
        ).fetchone()
        return row is not None

    def dates(self) -> tuple[dt.date, ...]:
        rows = self._conn.execute(
            "SELECT DISTINCT trade_date FROM ban_state ORDER BY trade_date"
        ).fetchall()
        return tuple(dt.date.fromisoformat(r["trade_date"]) for r in rows)

    def scored_forecasts(self, day: dt.date) -> Iterator[tuple[str, str, bool | None, bool | None]]:
        """`(isin, symbol, forecast, official)` for `day`, for scoring and reporting.

        Both columns together, which is a shape no caller can mistake for a seed.
        """
        for r in self._conn.execute(
            "SELECT isin, symbol, forecast, official FROM ban_state WHERE trade_date = ? "
            "ORDER BY symbol",
            (day.isoformat(),),
        ):
            yield (
                r["isin"], r["symbol"],
                None if r["forecast"] is None else bool(r["forecast"]),
                None if r["official"] is None else bool(r["official"]),
            )

    # -- inspection -----------------------------------------------------------------------

    def dump_csv(self, day: dt.date, out_path: str | Path) -> Path:
        """Write one day's state to CSV, because SQLite is opaque to a person and to git.

        The store is derived data in `data/` and never enters version control; this is how a
        day gets read by eye without a database client.
        """
        out = Path(out_path)
        rows = self._conn.execute(
            "SELECT isin, trade_date, symbol, official, forecast, source, input_sha256, note, "
            "written_at FROM ban_state WHERE trade_date = ? ORDER BY symbol",
            (day.isoformat(),),
        ).fetchall()
        with out.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["isin", "trade_date", "symbol", "official", "forecast", "source",
                        "input_sha256", "note", "written_at"])
            for r in rows:
                w.writerow([r["isin"], r["trade_date"], r["symbol"],
                            "" if r["official"] is None else bool(r["official"]),
                            "" if r["forecast"] is None else bool(r["forecast"]),
                            r["source"], r["input_sha256"], r["note"], r["written_at"]])
        return out

    def __repr__(self) -> str:
        days = self.dates()
        span = f" {days[0]}..{days[-1]}" if days else " empty"
        return f"<BanStateStore {len(days)} day(s){span} at {self.path.name}>"


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds")


def _check_sha(sha: str) -> None:
    if not _SHA256.fullmatch(sha):
        raise StoreError(
            f"input_sha256 is {sha!r}. Every record names the file it came from, so a day can be "
            f"traced back to the bytes behind it."
        )


_RULES_STATES = ("assumed", "unverified")


def _check_rules_status(status: Mapping[str, Iterable[str]]) -> dict[str, list[str]]:
    """`{"assumed": [...], "unverified": [...]}` with dotted keys only, returned sorted.

    Both lists are required, even when empty: an empty list says "none", a missing one says
    nothing. A key in both is a contradiction - an assumed threshold is used, an unverified one
    is refused - so it is refused rather than recorded.
    """
    if not isinstance(status, Mapping) or set(status) != set(_RULES_STATES):
        got = sorted(status) if isinstance(status, Mapping) else type(status).__name__
        raise StoreError(f"rules_status needs exactly the lists {list(_RULES_STATES)}, got {got}")
    out: dict[str, list[str]] = {}
    for state in _RULES_STATES:
        values = status[state]
        if isinstance(values, str):
            raise StoreError(f"rules_status[{state!r}] is one string; it must be a list of rule keys")
        keys = list(values)
        bad = [k for k in keys if not isinstance(k, str) or not k.strip() or " " in k.strip()]
        if bad:
            raise StoreError(
                f"rules_status[{state!r}] holds {bad[0]!r}, which is not a rule key. Record "
                f"Rules.{state}, not the loader's warning text."
            )
        if len(set(keys)) != len(keys):
            raise StoreError(f"rules_status[{state!r}] repeats a key")
        out[state] = sorted(keys)
    both = sorted(set(out["assumed"]) & set(out["unverified"]))
    if both:
        raise StoreError(f"{both[0]} is recorded as both assumed and unverified")
    return out


def _single_date(items: tuple, what: str) -> dt.date:
    if not items:
        raise StoreError(
            f"{what}() given nothing. An empty write says nothing; if a stage produced nothing, "
            f"record why as a refusal (#019 decision 5)."
        )
    dates = {i.trade_date for i in items}
    if len(dates) > 1:
        raise StoreError(f"{what}() given {len(dates)} dates; one day at a time")
    return dates.pop()


def _run_record(row: sqlite3.Row) -> RunRecord:
    return RunRecord(
        run_id=row["run_id"], trade_date=dt.date.fromisoformat(row["trade_date"]),
        started_at=row["started_at"], finished_at=row["finished_at"],
        outcome=RunOutcome(row["outcome"]), reason=row["reason"],
        input_checksums=json.loads(row["input_checksums"]), code_version=row["code_version"],
        dirty=bool(row["dirty"]), rules_checksum=row["rules_checksum"],
        calendar_checksum=row["calendar_checksum"],
        rules_status={k: tuple(v) for k, v in json.loads(row["rules_status"]).items()},
        superseded_by=row["superseded_by"],
    )
