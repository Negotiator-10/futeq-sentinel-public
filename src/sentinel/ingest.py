"""Load NSE's published files into the ban-state store, and write forecasts beside them.

These are the functions a pipeline runner calls. They do not orchestrate anything: no retries,
no dependency graph, no run log. That is `PLAN.md` D5's Automation 1 and it is Chintamani's to
write; this module is the part it stands on.

Three things worth knowing before reading the signatures.

**A ban list cannot be loaded on its own.** `fo_secban` is 62 bytes of symbols with no ISIN in
it, and the store is keyed on ISIN because symbols get renamed and reused (#011 Q2). So the
symbols have to be resolved through the same day's `combineoi`, which carries both. A symbol
that will not resolve stops the run rather than being skipped: a banned scrip that cannot be
identified is the worst thing to drop silently, because it under-reports a real ban and that is
the direction that gets a desk fined.

**The forecast for day D is written into day D's row, and computed from D-1's close.** The
engine runs after the close on day D-1: it reads D-1's measurement and D-1's official state,
and concludes something about D. So `record_forecast_day()` takes the measurement day and
writes into the *next* trading day's row, where NSE's own published answer for that day will
later land beside it. Both halves of a scored pair end up in one record.

**Nothing here reads a forecast.** The seed is always `official`, from the store, for the
previous trading day as the calendar defines it. That is #012 decision 2, and the store has no
method that would let this module do otherwise.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass
from pathlib import Path

from sentinel.calendar import TradingCalendar
from sentinel.engine import is_in_ban
from sentinel.parsers import parse_ban_list, parse_mwpl_file
from sentinel.rules import Rules
from sentinel.store import BanStateStore, Source, StoreError, WriteResult

__all__ = [
    "IngestError",
    "sha256_of",
    "load_official_day",
    "record_forecast_day",
    "ForecastSummary",
]


class IngestError(Exception):
    """A file could not be loaded in a way the store can be trusted to hold."""


def sha256_of(path: str | Path) -> str:
    """The hash recorded on every row, so a stored day can be traced back to its bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_official_day(
    store: BanStateStore,
    ban_list_path: str | Path,
    combineoi_path: str | Path,
    *,
    replace: bool = False,
) -> WriteResult:
    """Load NSE's published ban list for a day as that day's `official` state.

    `combineoi_path` is not optional and not a convenience: it is the only file that carries
    both symbol and ISIN, so it is how the ban list's symbols become storable keys. Both files
    must be for the same date - a mismatch is a mis-named download, which is exactly the shape
    of mistake that produced `combineoi_13102026 (1).zip`.

    Every scrip in the `combineoi` gets a record, not only the banned ones. "Not in ban" is a
    fact worth storing: without it, a missing row and a scrip that was free would be
    indistinguishable, and `was_in_ban()` would have to guess.
    """
    ban_list = parse_ban_list(ban_list_path)
    rows = parse_mwpl_file(combineoi_path)
    measurement_date = rows[0].trade_date

    if measurement_date != ban_list.trade_date:
        raise IngestError(
            f"date mismatch: the ban list is for {ban_list.trade_date} and the combineoi is for "
            f"{measurement_date}. The combineoi is here only to resolve that day's symbols to "
            f"ISINs, so they have to be the same day. Check the filenames."
        )

    by_symbol = {r.symbol: r for r in rows}
    unresolved = sorted(s for s in ban_list.symbols if s not in by_symbol)
    if unresolved:
        raise IngestError(
            f"{ban_list.trade_date}: {len(unresolved)} banned symbol(s) do not appear in that "
            f"day's combineoi, so they cannot be resolved to an ISIN: "
            f"{', '.join(unresolved)}. Not skipped - a banned scrip that cannot be identified "
            f"under-reports a real ban, which is the error direction that gets a desk fined."
        )

    values = {r.isin: (r.symbol, r.symbol in ban_list.symbols) for r in rows}
    return store.record_official(
        ban_list.trade_date, values,
        input_sha256=sha256_of(ban_list_path), source=Source.NSE, replace=replace,
    )


@dataclass(frozen=True)
class ForecastSummary:
    """What a day's forecast run concluded, and what it declined to conclude."""

    measurement_date: dt.date
    effective_date: dt.date
    write: WriteResult
    forecast_banned: tuple[str, ...]
    refused: tuple[tuple[str, str], ...]

    @property
    def refused_count(self) -> int:
        return len(self.refused)

    def __str__(self) -> str:
        line = (
            f"{self.measurement_date} -> {self.effective_date}: "
            f"{len(self.forecast_banned)} forecast in ban"
        )
        if self.refused:
            line += f", {len(self.refused)} refused"
        return line + f" [{self.write}]"


def record_forecast_day(
    store: BanStateStore,
    combineoi_path: str | Path,
    rules: Rules,
    *,
    replace: bool = False,
) -> ForecastSummary:
    """Forecast the next trading day's ban state from one day's measurement, and store it.

    The seed is the **previous** state as the store holds it, which for the measurement day D
    means D's own `official` record - NSE's published list for D, loaded by
    `load_official_day()`. The result is written into the next trading day's row, because that
    is the day it is about.

    Where a scrip's prior state is not stored, the decision from #012 applies rather than a
    guess: outside the 80-95% band the state cannot change the answer, so those scrips are
    forecast normally; inside it they are refused by name and the rest of the day completes.
    """
    rows = parse_mwpl_file(combineoi_path)
    measurement_date = rows[0].trade_date
    effective_date = store.calendar.next_trading_day(measurement_date)

    # Raises if the measurement day has no stored state at all, which is a different failure
    # from an individual scrip having none - and a day-level one, so it stops the run.
    store.official_ban_set(measurement_date)

    entry = rules.get("single_stock.ban.entry_utilisation")
    exit_ = rules.get("single_stock.ban.exit_utilisation")

    values: dict[str, tuple[str, bool]] = {}
    refused: list[tuple[str, str]] = []

    for row in rows:
        known = _prior_state_known(store, row.isin, measurement_date)
        if known is None:
            if _in_band(row, entry, exit_):
                refused.append((row.symbol, "no prior state and inside the 80-95% band"))
                continue
            known = False       # outside the band the seed cannot change the answer
        values[row.isin] = (
            row.symbol,
            is_in_ban(row.futeq_oi, row.mwpl, was_in_ban_yesterday=known, rules=rules),
        )

    write = store.record_forecast(
        effective_date, values,
        input_sha256=sha256_of(combineoi_path), source=Source.COMPUTED, replace=replace,
    )
    return ForecastSummary(
        measurement_date=measurement_date,
        effective_date=effective_date,
        write=write,
        forecast_banned=tuple(sorted(sym for _, (sym, banned) in values.items() if banned)),
        refused=tuple(refused),
    )


def _prior_state_known(store: BanStateStore, isin: str, day: dt.date) -> bool | None:
    """Whether the scrip was officially in ban on `day`, or None when the store does not say.

    `None` covers two cases the store distinguishes and this function deliberately does not: a
    scrip with no record for that day at all - a newly listed one, which is not hypothetical,
    since the universe moved 213 to 219 to 218 inside three weeks of real data - and a record
    whose `official` value was never filled in because NSE's list for that day was not loaded.
    Both mean the same thing here: the prior state is not known, so #012's rule applies.
    """
    try:
        return store.was_in_ban(isin, day)
    except StoreError:
        return None


def _in_band(row: MwplRow, entry, exit_) -> bool:
    u = row.futeq_oi / row.mwpl
    return not entry.compare(u) and not exit_.compare(u)
