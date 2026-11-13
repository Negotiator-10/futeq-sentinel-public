"""The pipeline runner: one command that runs trading day D end to end.

Follows DECISIONS #019:
  - Whole-run refusal when D is a holiday, unknown, or a special session that
    is excluded or unverified; when combineoi_D is missing; or when a banned
    symbol can't be resolved to an ISIN (matching ingest, #011 Q2). The reason
    goes in the run log; no day transaction opens.
  - Every other gap refuses only the consumers that need it:
      missing fo_secban_D     -> official state, D-1's score, in-band
                                 forecasts, row 6
      next day unverified     -> the forecast stage
      previous day unverified,
      or missing book/factors -> row 6
  - Results are computed in memory, then written in one day_transaction.
    A crash rolls the day back; the run log records FAILED.
  - Another run holding the lock is a refusal, not a crash (#019 decision 6).
  - No retries: there is no downloader (#010, #019 item 12).

Usage:  python -m sentinel.runner 2026-11-04
Exit codes: 0 COMPLETED, 2 REFUSED, 1 FAILED.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from sentinel.book import (
    DEFAULT_BOOK_CONFIG_PATH, NoPriorDay, load_book_start, load_books, load_delta_factors,
)
from sentinel.calendar import (
    ChainUnverifiedError, DayKind, UnknownDateError, load_calendar,
)
from sentinel.engine import (
    NO_MWPL_REASON, EntityLimitResult, ReductionCheck, check_ban_period_reduction,
    check_entity_limit, is_in_ban, reconcile,
)
from sentinel.entities import ReferenceDataError, load_reference
from sentinel.parsers import parse_ban_list, parse_mwpl_file
from sentinel.rules import load_rules
from sentinel.runlock import RunInProgressError, RunLock
from sentinel.store import BanStateStore, Refusal, RefusalStage, RunOutcome, StageStatus

# Anchored to the repo, like DEFAULT_CALENDAR_PATH, so the runner works from
# any working directory. runner.py lives at src/sentinel/runner.py.
REPO_ROOT = Path(__file__).resolve().parents[2]

CALENDAR_ERRORS = (UnknownDateError, ChainUnverifiedError)


# ---------------------------------------------------------------- paths

def _stamp(day: dt.date) -> str:
    """NSE file names use ddmmyyyy."""
    return day.strftime("%d%m%Y")


@dataclass(frozen=True)
class RunPaths:
    """Where one run reads and writes. Passed in so tests can point it at a
    temporary data folder built from synthetic fixtures."""

    data: Path
    rules: Path
    calendar: Path
    store: Path
    lock: Path
    book: Path
    # The declared book start (#016 addendum 2). A default, so existing callers keep working;
    # a test declares its own start by pointing this at its own file.
    book_config: Path = DEFAULT_BOOK_CONFIG_PATH

    @classmethod
    def default(cls) -> RunPaths:
        data = REPO_ROOT / "data"
        config = REPO_ROOT / "config"
        return cls(
            data=data,
            rules=config / "rules.yaml",
            calendar=config / "calendar_2026.csv",
            store=data / "store" / "sentinel.sqlite",
            lock=data / "store" / "runner.lock",
            book=data / "book" / "positions.csv",
            book_config=config / "book.yaml",
        )

    def combineoi(self, day: dt.date) -> Path:
        return self.data / f"combineoi_{_stamp(day)}.zip"

    def ban_list(self, day: dt.date) -> Path:
        return self.data / f"fo_secban_{_stamp(day)}.csv"

    def delta(self, day: dt.date) -> Path:
        return self.data / f"Contract_Delta_{_stamp(day)}.csv"

    # Row 7's reference tables (#016 addendum A) sit beside the positions file. Built from
    # `book`'s folder rather than given defaults like `book_config`: a default would point a
    # test's RunPaths at the real data/ folder, and the test would read real files unawares.
    def holders(self) -> Path:
        return self.book.parent / "holders.csv"

    def accounts(self) -> Path:
        return self.book.parent / "accounts.csv"


# ---------------------------------------------------------------- outcomes

class RunRefused(Exception):
    """The whole run cannot proceed. Carries the reason for the run log."""


# StageStatus (CHECKED, FLAT, REFUSED) lives in sentinel.store beside RefusalStage, because
# the stage_ran marker's table holds its values (#023). Imported above, so runner.StageStatus works.


@dataclass(frozen=True)
class Row6Outcome:
    """The row 6 stage's outcome for one day, carrying its own refusal (#023 item 5).

    Differs from Row7Outcome where the stages differ: the result is a tuple of ReductionCheck,
    CHECKED may be empty (no banned scrip, or none held, is an ordinary day), and row 6 has no
    per-scrip refusals. FLAT means both books were flat, because row 6 checks the change
    between them. It carries its date because a FLAT or empty CHECKED outcome has nothing else
    in it that says which day it is for (#015).
    """

    trade_date: dt.date
    status: StageStatus
    checks: tuple[ReductionCheck, ...] | None
    refusals: tuple[Refusal, ...] = ()

    def __post_init__(self) -> None:
        day = self.trade_date
        where = f"row 6 outcome for {day} ({getattr(self.status, 'value', self.status)})"

        # 1. Types. A list inside a frozen dataclass could still be changed.
        if not isinstance(self.status, StageStatus):
            raise TypeError(f"{where}: status must be a StageStatus, not {type(self.status).__name__}")
        if not isinstance(self.refusals, tuple):
            raise TypeError(f"{where}: refusals must be a tuple, not {type(self.refusals).__name__}")
        for r in self.refusals:
            if not isinstance(r, Refusal):
                raise TypeError(f"{where}: refusals holds a {type(r).__name__}, not a Refusal")
        if self.checks is not None:
            if not isinstance(self.checks, tuple):
                raise TypeError(f"{where}: checks must be a tuple or None, "
                                f"not {type(self.checks).__name__}")
            for c in self.checks:
                if not isinstance(c, ReductionCheck):
                    raise TypeError(f"{where}: checks holds a {type(c).__name__}, "
                                    f"not a ReductionCheck")

        # 2. Every refusal belongs to row 6 and to this day.
        for r in self.refusals:
            if r.stage is not RefusalStage.ROW6:
                raise ValueError(f"{where}: a {r.stage.value} refusal does not belong to row 6")
            if r.trade_date != day:
                raise ValueError(f"{where}: a refusal is dated {r.trade_date}")

        # 3. Every check is for this day.
        if self.checks is not None:
            dates = {c.trade_date for c in self.checks}
            if dates - {day}:
                raise ValueError(f"{where}: checks are dated {sorted(dates)}")

        # 4. REFUSED: no checks at all, and exactly one whole-stage refusal.
        if self.status is StageStatus.REFUSED:
            if self.checks is not None:
                raise ValueError(f"{where}: a refused stage has no checks, not even an empty tuple")
            if len(self.refusals) != 1 or self.refusals[0].subject != "":
                raise ValueError(
                    f"{where}: needs exactly one whole-stage refusal (subject \"\"), "
                    f"got {[r.subject for r in self.refusals]}")

        # 5. FLAT: an empty tuple of checks and no refusals. Both books held nothing.
        elif self.status is StageStatus.FLAT:
            if self.checks is None:
                raise ValueError(f"{where}: a flat stage ran its check; its checks are (), not None")
            if self.checks:
                raise ValueError(f"{where}: a flat day has {len(self.checks)} check(s); "
                                 f"it must have none")
            if self.refusals:
                raise ValueError(f"{where}: a flat day has {len(self.refusals)} refusal(s)")

        # 6. CHECKED: a tuple, empty allowed (#023 item 4), and no refusals: row 6 has no
        #    per-scrip refusals, and a whole-stage refusal is REFUSED.
        else:
            if self.checks is None:
                raise ValueError(f"{where}: a checked stage needs its checks, even if ()")
            if self.refusals:
                raise ValueError(f"{where}: a checked stage carries no refusals, "
                                 f"got {[r.subject for r in self.refusals]}")


@dataclass(frozen=True)
class Row7Outcome:
    """The row 7 stage's outcome for one day, carrying its own refusals.

    write_day() reads everything it needs from this one value: whether to call record_row7(),
    which refusals to store, and (#023) which stage_ran marker to write. It carries its date
    because a FLAT outcome has nothing else in it that says which day it is for (#015).
    """

    trade_date: dt.date
    status: StageStatus
    result: EntityLimitResult | None
    refusals: tuple[Refusal, ...] = ()

    def __post_init__(self) -> None:
        day = self.trade_date
        where = f"row 7 outcome for {day} ({getattr(self.status, 'value', self.status)})"

        # 1. Types. A list inside a frozen dataclass could still be changed.
        if not isinstance(self.status, StageStatus):
            raise TypeError(f"{where}: status must be a StageStatus, not {type(self.status).__name__}")
        if not isinstance(self.refusals, tuple):
            raise TypeError(f"{where}: refusals must be a tuple, not {type(self.refusals).__name__}")
        for r in self.refusals:
            if not isinstance(r, Refusal):
                raise TypeError(f"{where}: refusals holds a {type(r).__name__}, not a Refusal")
        if self.result is not None and not isinstance(self.result, EntityLimitResult):
            raise TypeError(
                f"{where}: result must be an EntityLimitResult or None, "
                f"not {type(self.result).__name__}")

        # 2. Every refusal belongs to row 7 and to this day.
        for r in self.refusals:
            if r.stage is not RefusalStage.ROW7:
                raise ValueError(f"{where}: a {r.stage.value} refusal does not belong to row 7")
            if r.trade_date != day:
                raise ValueError(f"{where}: a refusal is dated {r.trade_date}")

        # 3. Every entry is for this day. EntityLimitResult already refuses a mix of dates,
        #    so whatever single date it holds must be this one.
        if self.result is not None:
            dates = {e.trade_date for e in (*self.result.checks, *self.result.not_checked)}
            if dates - {day}:
                raise ValueError(f"{where}: the result is for {sorted(dates)}")

        whole_stage = [r for r in self.refusals if r.subject == ""]

        # 4. REFUSED: exactly one whole-stage refusal, and no result.
        if self.status is StageStatus.REFUSED:
            if self.result is not None:
                raise ValueError(f"{where}: a refused stage has no result")
            if len(self.refusals) != 1 or len(whole_stage) != 1:
                raise ValueError(
                    f"{where}: needs exactly one whole-stage refusal (subject \"\"), "
                    f"got {len(self.refusals)} refusal(s), {len(whole_stage)} whole-stage")

        # 5. FLAT: an empty result and no refusals. Nothing was held, so nothing was refused.
        elif self.status is StageStatus.FLAT:
            if self.result is None:
                raise ValueError(f"{where}: a flat day still has a result, an empty one")
            if self.result.checks or self.result.not_checked:
                raise ValueError(
                    f"{where}: a flat day has {len(self.result.checks)} check(s) and "
                    f"{len(self.result.not_checked)} not-checked; it must have none")
            if self.refusals:
                raise ValueError(f"{where}: a flat day has {len(self.refusals)} refusal(s)")

        # 6. CHECKED: a non-empty result, and one refusal per no-MWPL scrip, both directions.
        else:
            if self.result is None:
                raise ValueError(f"{where}: a checked stage needs its result")
            if not self.result.checks and not self.result.not_checked:
                raise ValueError(
                    f"{where}: the result is empty; an empty result is FLAT, and only a "
                    f"flat book can give one")
            if whole_stage:
                raise ValueError(f"{where}: a checked stage cannot carry a whole-stage refusal")
            subjects = [r.subject for r in self.refusals]
            if len(set(subjects)) != len(subjects):
                raise ValueError(f"{where}: one refusal per scrip; got duplicates in {sorted(subjects)}")
            not_checked_isins = {nc.isin for nc in self.result.not_checked}
            no_refusal = not_checked_isins - set(subjects)
            no_entries = set(subjects) - not_checked_isins
            if no_refusal or no_entries:
                raise ValueError(
                    f"{where}: refusals and not-checked scrips must match. "
                    f"Not checked but not refused: {sorted(no_refusal)}. "
                    f"Refused but nothing not checked: {sorted(no_entries)}.")


@dataclass
class DayResults:
    """Everything computed for D, held in memory until the transaction."""
    combineoi_sha256: str = ""
    ban_list_sha256: str = ""
    measurements: tuple = ()
    reconciliation: object | None = None
    official: dict[str, tuple[str, bool]] | None = None    # ISIN -> (symbol, in_ban)
    next_day: dt.date | None = None                        # None = forecast refused
    forecasts: dict[str, tuple[str, bool]] = field(default_factory=dict)
    row6: Row6Outcome | None = None                        # None = not run (#023)
    refusals: list[Refusal] = field(default_factory=list)
    row7: Row7Outcome | None = None                        # None = not run


# ---------------------------------------------------------------- audit inputs

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True, cwd=REPO_ROOT,
    ).stdout.strip()


def code_version() -> tuple[str, bool]:
    """The current commit, and whether the working tree has uncommitted changes."""
    return _git("rev-parse", "HEAD"), bool(_git("status", "--porcelain"))


def previous_day_or_none(calendar, day: dt.date) -> dt.date | None:
    """D's previous trading day, or None if the calendar can't settle it."""
    try:
        return calendar.previous_trading_day(day)
    except CALENDAR_ERRORS:
        return None


def input_checksums(paths: RunPaths, day: dt.date,
                    prev: dt.date | None) -> dict[str, str]:
    """Checksums of every input the run could read that exists. A missing file
    is left out, not recorded as None: in the run log a NULL means nothing
    (#019 item 5). Yesterday's delta file counts, because row 6 reads it.
    Yesterday's combineoi counts, because row 7 reads its MWPL to name a
    passive breach's mechanism in the stored reason. Row 7 also reads the
    declared book start and the two reference tables."""
    files = [paths.combineoi(day), paths.ban_list(day), paths.delta(day), paths.book,
             paths.holders(), paths.accounts(), paths.book_config]
    if prev is not None:
        files += [paths.combineoi(prev), paths.delta(prev)]
    return {f.name: _sha256(f) for f in files if f.exists()}


def rules_status_of(rules) -> dict[str, list[str]]:
    """The rule keys this run relies on without verification, as keys, not a
    warning sentence: rewording the warning must not change the record."""
    return {"assumed": list(rules.assumed), "unverified": list(rules.unverified)}


# ---------------------------------------------------------------- the date gate

def date_gate(calendar, day: dt.date) -> None:
    """Refuse the whole run unless D is a trading day or a verified, chaining
    special session. calendar.kind() never raises; it says what D is."""
    kind = calendar.kind(day)
    if kind is DayKind.HOLIDAY:
        raise RunRefused(f"{day} is a trading holiday")
    if kind is DayKind.UNKNOWN:
        raise RunRefused(f"{day} is not covered by a verified calendar")
    if kind is DayKind.SPECIAL_SESSION:
        if day in calendar.chaining_excluded:
            raise RunRefused(f"{day} is a special session verified not to chain")
        if day not in calendar.chaining_verified:
            raise RunRefused(f"{day} is a special session whose chaining is unverified")


# ---------------------------------------------------------------- computing the day

def compute_day(paths: RunPaths, day: dt.date, calendar, rules) -> DayResults:
    """Compute every result for D in memory. Writes nothing.

    Raises RunRefused for a missing combineoi_D or an unresolved banned symbol.
    Every other gap becomes a Refusal and the rest of the day still runs.
    """
    results = DayResults()

    # 1. combineoi_D is required: the store keys on ISIN, and ban lists carry
    #    symbols resolved only through the same day's combineoi (#019 item 2).
    if not paths.combineoi(day).exists():
        raise RunRefused(f"{paths.combineoi(day).name} is missing")
    results.combineoi_sha256 = _sha256(paths.combineoi(day))
    rows = parse_mwpl_file(paths.combineoi(day))
    results.measurements = rows
    symbol_for_isin = {r.isin: r.symbol for r in rows}
    isin_for_symbol = {r.symbol: r.isin for r in rows}

    # 2. Reconciliation needs only combineoi_D.
    results.reconciliation = reconcile(rows, rules)

    # 3. D's official state, from fo_secban_D.
    official_banned: frozenset[str] | None = None
    if not paths.ban_list(day).exists():
        missing = f"{paths.ban_list(day).name} is missing"
        results.refusals.append(
            Refusal(day, RefusalStage.OFFICIAL_STATE, "", missing))
        results.refusals.append(
            Refusal(day, RefusalStage.SCORE, "", f"{missing}; D-1's forecast unscored"))
    else:
        results.ban_list_sha256 = _sha256(paths.ban_list(day))
        ban_list = parse_ban_list(paths.ban_list(day))
        unresolved = sorted(s for s in ban_list.symbols if s not in isin_for_symbol)
        if unresolved:
            # Matches ingest.load_official_day: under-reporting a ban is the
            # worst error to make quietly (#011 Q2), so the whole run stops.
            raise RunRefused(
                f"ban list symbols not in {paths.combineoi(day).name}: {unresolved}")
        official_banned = frozenset(isin_for_symbol[s] for s in ban_list.symbols)
        results.official = {
            r.isin: (r.symbol, r.isin in official_banned) for r in rows}

    # 4. Forecast for the next trading day. Only this stage depends on the
    #    next day being settled, so an unverified next day refuses only it.
    try:
        results.next_day = calendar.next_trading_day(day)
    except CALENDAR_ERRORS as err:
        results.refusals.append(
            Refusal(day, RefusalStage.FORECAST, "", f"next trading day unsettled: {err}"))
    if results.next_day is not None:
        for r in rows:
            if official_banned is not None:
                in_ban = is_in_ban(r.futeq_oi, r.mwpl,
                                   was_in_ban_yesterday=r.isin in official_banned,
                                   rules=rules)
                results.forecasts[r.isin] = (r.symbol, in_ban)
                continue
            # No official state: it only matters inside the band (#012).
            # Ask both ways; if the answers agree, yesterday doesn't matter.
            if_banned = is_in_ban(r.futeq_oi, r.mwpl, was_in_ban_yesterday=True, rules=rules)
            if_free = is_in_ban(r.futeq_oi, r.mwpl, was_in_ban_yesterday=False, rules=rules)
            if if_banned == if_free:
                results.forecasts[r.isin] = (r.symbol, if_banned)
            else:
                results.refusals.append(Refusal(
                    day, RefusalStage.FORECAST, r.isin,
                    "in-band scrip and D's official state is missing"))

    # 5. Row 6. Its refusal travels in its outcome, as row 7's do, not in results.refusals.
    results.row6 = _row6(paths, day, calendar, rules, official_banned, symbol_for_isin)

    # 6. Row 7.
    results.row7 = _entity_limit_stage(paths, day, calendar, rules, rows, symbol_for_isin)
    return results


def _row6(paths, day, calendar, rules, official_banned, symbol_for_isin) -> Row6Outcome:
    """Run the row 6 check, or say why it can't (#023). Never raises for a gap.

    The inputs come first: a missing ban list refuses even on a flat day (item 3). FLAT is
    decided after the check runs, so its date checks (yesterday is the previous trading day,
    each book matches its factor file) still guard a flat day.
    """
    def refuse(reason: str) -> Row6Outcome:
        return Row6Outcome(day, StageStatus.REFUSED, None,
                           (Refusal(day, RefusalStage.ROW6, "", reason),))

    if official_banned is None:
        return refuse("D's official ban state is missing")
    try:
        prev = calendar.previous_trading_day(day)
    except CALENDAR_ERRORS as err:
        return refuse(f"previous trading day unsettled: {err}")

    missing = [p.name for p in (paths.delta(day), paths.delta(prev), paths.book)
               if not p.exists()]
    if missing:
        return refuse("missing: " + ", ".join(missing))

    books = load_books(paths.book)
    absent = [str(d) for d in (prev, day) if d not in books]
    if absent:
        # Never books.get(): a missing day must not pass as flat (#015).
        return refuse("no prop book for " + ", ".join(absent))
    today, yesterday = books[day], books[prev]

    checks = check_ban_period_reduction(
        today=today,
        yesterday=yesterday,
        factors_today=load_delta_factors(paths.delta(day)),
        factors_yesterday=load_delta_factors(paths.delta(prev)),
        symbol_for_isin=symbol_for_isin,
        banned_isins=official_banned,
        calendar=calendar,
        rules=rules,
    )

    # FLAT comes from the books, never from an empty result: row 6 checks the change between
    # yesterday and today, so both must be flat. A flat pair can hold no position in a banned
    # scrip, so any check returned is a bug: raise, and the run ends FAILED.
    if today.is_flat and yesterday.is_flat:
        if checks:
            raise RuntimeError(f"{day}: both books are flat, but row 6 returned "
                               f"{len(checks)} check(s)")
        return Row6Outcome(day, StageStatus.FLAT, ())

    # Not flat: CHECKED, and an empty tuple is an ordinary day (#023 item 4).
    return Row6Outcome(day, StageStatus.CHECKED, tuple(checks))


FIRST_DAY_REASON = "first day of the book"


def _entity_limit_stage(paths, day, calendar, rules, rows, symbol_for_isin) -> Row7Outcome:
    """Run the row 7 check, or say why it can't (#016 addendum 2). Never raises for a gap.

    Only ReferenceDataError is caught, at its two failure points, each with its own reason.
    Anything else is a real failure and ends the run FAILED. A gap returns REFUSED with one
    whole-stage refusal; a flat book returns FLAT; otherwise CHECKED, with one refusal per
    scrip that had no MWPL.
    """
    def refuse(reason: str) -> Row7Outcome:
        return Row7Outcome(day, StageStatus.REFUSED, None,
                           (Refusal(day, RefusalStage.ROW7, "", reason),))

    # 1. The declared start decides whether there is a yesterday (addendum 2, point 2).
    #    A malformed book.yaml raises BookError: a config fault, so the run fails loudly.
    start = load_book_start(paths.book_config, calendar=calendar).start_date
    if day < start:
        return refuse("before the book's start date")

    # 2. Files first: load_reference() would raise FileNotFoundError, which is not caught.
    missing = [p.name for p in (paths.book, paths.holders(), paths.accounts(), paths.delta(day))
               if not p.exists()]
    if missing:
        return refuse("missing: " + ", ".join(missing))

    # 3. Today's book, and yesterday's unless D is the declared start.
    prev = None
    if day > start:
        try:
            prev = calendar.previous_trading_day(day)
        except CALENDAR_ERRORS as err:
            return refuse(f"previous trading day unsettled: {err}")

    books = load_books(paths.book)
    absent = [str(d) for d in (prev, day) if d is not None and d not in books]
    if absent:
        # Never books.get(): a missing day must not pass as flat (#015).
        return refuse("no prop book for " + ", ".join(absent))
    today = books[day]
    yesterday = books[prev] if prev is not None else NoPriorDay(day, FIRST_DAY_REASON)

    # 4. Reference data. as_of() raises too, when the two tables disagree with each other:
    #    that is the data failing to load, not a position, so it carries the load reason.
    try:
        reference = load_reference(paths.holders(), paths.accounts())
        snapshot = reference.as_of(day)
    except ReferenceDataError as err:
        return refuse(f"reference data could not be loaded: {err}")

    # 5. MWPL. Yesterday's, read from combineoi(D-1) so the stored reason depends only on
    #    input files (#022). Missing, it is None: the reason gets vaguer, the cause does not.
    mwpl_today = {r.isin: r.mwpl for r in rows}
    mwpl_yesterday = None
    if prev is not None and paths.combineoi(prev).exists():
        mwpl_yesterday = {r.isin: r.mwpl for r in parse_mwpl_file(paths.combineoi(prev))}

    # 6. The check. Factors load first, outside the try: its only ReferenceDataError
    #    must be a position in an unknown account, so the reason stays honest.
    factors_today = load_delta_factors(paths.delta(day))
    try:
        result = check_entity_limit(
            today=today,
            yesterday=yesterday,
            factors_today=factors_today,
            reference=snapshot,
            mwpl_today=mwpl_today,
            mwpl_yesterday=mwpl_yesterday,
            symbol_for_isin=symbol_for_isin,
            calendar=calendar,
            rules=rules,
        )
    except ReferenceDataError as err:
        return refuse(f"position in unknown account: {err}")

    # 7. FLAT comes from the book, never from an empty result. Every position yields a check
    #    or a NotChecked, so a mismatch either way is a bug: raise, and the run ends FAILED.
    empty = not result.checks and not result.not_checked
    if today.is_flat:
        if not empty:
            raise RuntimeError(f"{day}: a flat book gave row 7 entries")
        return Row7Outcome(day, StageStatus.FLAT, result)
    if empty:
        raise RuntimeError(f"{day}: a book with positions gave row 7 no checks and no "
                           f"not-checked entries")

    # 8. One refusal per scrip with no MWPL, with the count (addendum 2, point 1). The
    #    holders it affected stay in row7_not_checked, beside the checks. Any other
    #    not-checked reason is one this stage has no wording for: fail, don't mislabel it.
    unknown = sorted({nc.reason for nc in result.not_checked} - {NO_MWPL_REASON})
    if unknown:
        raise RuntimeError(f"{day}: row 7 has no refusal wording for not-checked "
                           f"reason(s) {unknown}")
    per_scrip = Counter(nc.isin for nc in result.not_checked)
    refusals = tuple(
        Refusal(day, RefusalStage.ROW7, isin,
                f"no MWPL in today's combineoi; {n} check{'' if n == 1 else 's'} not made")
        for isin, n in sorted(per_scrip.items()))
    return Row7Outcome(day, StageStatus.CHECKED, result, refusals)


# ---------------------------------------------------------------- writing the day

def write_day(store: BanStateStore, day: dt.date, run_id: str,
              results: DayResults) -> None:
    """Write D's results in one transaction. A writer is called only when it
    has something: an empty write raises by design (#019 decision 5).

    Each stage's marker comes from its own outcome and is written only when the stage
    reached one (#023 item 2): a stage that did not run has outcome None and leaves no
    marker. Markers are written before the stages' rows, so a re-run that changed a stage's
    status fails on the marker, with its stage-and-status message, before anything else."""
    row6, row7 = results.row6, results.row7
    refusals = [*results.refusals,
                *(row6.refusals if row6 is not None else ()),
                *(row7.refusals if row7 is not None else ())]

    with store.day_transaction(day, run_id):
        # The markers first: a status that changed since the last run fails here, loudly.
        if row6 is not None:
            store.record_stage_ran(day, RefusalStage.ROW6, row6.status)
        if row7 is not None:
            store.record_stage_ran(day, RefusalStage.ROW7, row7.status)

        store.record_measurements(results.measurements,
                                  input_sha256=results.combineoi_sha256)
        store.record_reconciliation(results.reconciliation,
                                    input_sha256=results.combineoi_sha256)
        if results.official is not None:
            store.record_official(day, results.official,
                                  input_sha256=results.ban_list_sha256)
        if results.next_day is not None and results.forecasts:
            store.record_forecast(results.next_day, results.forecasts,
                                  input_sha256=results.combineoi_sha256)
        # Row 6: an empty CHECKED writes its marker and no rows; record_row6_checks()
        # refuses an empty tuple.
        if row6 is not None and row6.status is StageStatus.CHECKED and row6.checks:
            store.record_row6_checks(row6.checks)
        # Row 7: only CHECKED has a non-empty result; FLAT's is empty and record_row7()
        # refuses it.
        if row7 is not None and row7.status is StageStatus.CHECKED:
            store.record_row7(row7.result)
        if refusals:
            store.record_refusals(refusals)


# ---------------------------------------------------------------- the run

def run_day(day: dt.date, paths: RunPaths | None = None) -> RunOutcome:
    """Run trading day D. Returns COMPLETED or REFUSED; logs FAILED and re-raises.

    Raises RunInProgressError, unlogged, if another run holds the lock:
    start_run needs the lock, so main reports it as a refusal instead.
    """
    paths = paths or RunPaths.default()
    rules = load_rules(paths.rules, warn=False)
    calendar = load_calendar(paths.calendar)
    commit, dirty = code_version()

    with RunLock(paths.lock) as lock, BanStateStore(paths.store, calendar) as store:
        run = store.start_run(
            day, lock=lock,
            input_checksums=input_checksums(paths, day, previous_day_or_none(calendar, day)),
            code_version=commit, dirty=dirty,
            rules_checksum=_sha256(paths.rules),
            calendar_checksum=_sha256(paths.calendar),
            rules_status=rules_status_of(rules),
        )
        try:
            date_gate(calendar, day)
            results = compute_day(paths, day, calendar, rules)   # in memory only
            write_day(store, day, run.run_id, results)
        except RunRefused as refused:
            store.finish_run(run.run_id, RunOutcome.REFUSED, str(refused), lock=lock)
            return RunOutcome.REFUSED
        except Exception as exc:
            # The day transaction has rolled back. The run log survives.
            store.finish_run(run.run_id, RunOutcome.FAILED,
                             f"{type(exc).__name__}: {exc}", lock=lock)
            raise
        store.finish_run(run.run_id, RunOutcome.COMPLETED, "", lock=lock)
        return RunOutcome.COMPLETED


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m sentinel.runner YYYY-MM-DD", file=sys.stderr)
        return 1
    day = dt.date.fromisoformat(argv[1])
    try:
        outcome = run_day(day)
    except RunInProgressError:
        # A refusal, not a crash (#019 decision 6). Not logged: start_run
        # needs the lock, which another run holds.
        print(f"REFUSED {day}: another run in progress", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"FAILED {day}: {exc}", file=sys.stderr)
        return 1
    print(f"{outcome.name} {day}")
    return 0 if outcome is RunOutcome.COMPLETED else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
