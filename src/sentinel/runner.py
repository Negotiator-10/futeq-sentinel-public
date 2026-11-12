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
from dataclasses import dataclass, field
from pathlib import Path

from sentinel.book import DEFAULT_BOOK_CONFIG_PATH, load_books, load_delta_factors
from sentinel.calendar import (
    ChainUnverifiedError, DayKind, UnknownDateError, load_calendar,
)
from sentinel.engine import check_ban_period_reduction, is_in_ban, reconcile
from sentinel.parsers import parse_ban_list, parse_mwpl_file
from sentinel.rules import load_rules
from sentinel.runlock import RunInProgressError, RunLock
from sentinel.store import BanStateStore, Refusal, RefusalStage, RunOutcome

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


# ---------------------------------------------------------------- outcomes

class RunRefused(Exception):
    """The whole run cannot proceed. Carries the reason for the run log."""


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
    row6_checks: tuple = ()
    refusals: list[Refusal] = field(default_factory=list)


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
    (#019 item 5). Yesterday's delta file counts, because row 6 reads it."""
    files = [paths.combineoi(day), paths.ban_list(day), paths.delta(day), paths.book]
    if prev is not None:
        files.append(paths.delta(prev))
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

    # 5. Row 6.
    results.row6_checks = _row6(paths, day, calendar, rules, official_banned,
                                symbol_for_isin, results.refusals)
    return results


def _row6(paths, day, calendar, rules, official_banned,
          symbol_for_isin, refusals) -> tuple:
    """Run the row 6 check, or record why it can't. Never raises for a gap."""
    def refuse(reason: str) -> tuple:
        refusals.append(Refusal(day, RefusalStage.ROW6, "", reason))
        return ()

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

    return check_ban_period_reduction(
        today=books[day],
        yesterday=books[prev],
        factors_today=load_delta_factors(paths.delta(day)),
        factors_yesterday=load_delta_factors(paths.delta(prev)),
        symbol_for_isin=symbol_for_isin,
        banned_isins=official_banned,
        calendar=calendar,
        rules=rules,
    )


# ---------------------------------------------------------------- writing the day

def write_day(store: BanStateStore, day: dt.date, run_id: str,
              results: DayResults) -> None:
    """Write D's results in one transaction. A writer is called only when it
    has something: an empty write raises by design (#019 decision 5)."""
    with store.day_transaction(day, run_id):
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
        if results.row6_checks:
            store.record_row6_checks(results.row6_checks)
        if results.refusals:
            store.record_refusals(results.refusals)


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
