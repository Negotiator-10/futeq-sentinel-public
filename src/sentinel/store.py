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
"""

from __future__ import annotations

import csv
import datetime as dt
import sqlite3
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from sentinel.calendar import DayKind, TradingCalendar, UnknownDateError

__all__ = ["Source", "StateRecord", "WriteResult", "BanStateStore", "StoreError"]


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
        if not self.isin or self.isin.strip().upper() in {"NA", "NAN", "-"}:
            raise StoreError(
                f"{self.symbol} on {self.trade_date}: ISIN is {self.isin!r}. Index rows carry "
                f"no ISIN and are not stored - MWPL does not apply to them (#011 Q2)."
            )
        if len(self.input_sha256) != 64:
            raise StoreError(
                f"{self.symbol} ({self.isin}) on {self.trade_date}: input_sha256 is "
                f"{self.input_sha256!r}. Every record names the file it came from, so a day can "
                f"be traced back to the bytes behind it."
            )


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
"""


class BanStateStore:
    """Point-in-time ban state. Open it, write days into it, ask it about one date at a time."""

    def __init__(self, path: str | Path, calendar: TradingCalendar) -> None:
        self.path = Path(path)
        self.calendar = calendar
        self._conn = sqlite3.connect(self.path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)

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
            with self._conn:
                self._conn.execute("BEGIN")
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

        kind = self.calendar.kind(day)
        if kind is DayKind.UNKNOWN:
            raise UnknownDateError(
                f"refusing to store state for {day}: no verified calendar covers it."
            )
        if not kind.has_session:
            raise StoreError(
                f"refusing to store state for {day}: the verified calendar says it is a "
                f"{kind.value}. A non-trading day with data is a contradiction."
            )

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
            with self._conn:
                self._conn.execute("BEGIN")
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
