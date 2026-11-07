"""The synthetic prop book: positions, and the FutEq delta they come to.

This module reads and models. It computes FutEq delta from holdings and NSE's own per-contract
delta factors, and it does not decide whether any limit is breached - `check_ban_period_
reduction()` and `check_entity_limit()` in `engine.py` do that, for the same reason
`parse_mwpl_file()` does not compute utilisation: if the engine ever disagrees with NSE, the
disagreement should point at the engine and not at something that both read and concluded.

All positions here are synthetic. Nothing in this repository reflects a real book.

**What a position record holds, and what it deliberately does not.** Per contract, not one
aggregate delta per scrip, because SEBI 2025/79 Table 2 shows two days where EoD delta rises
and only one is a breach - day 2 holds the same contract as day 1 while day 5 holds an extra
futures lot, and only per-contract holdings tell those apart. Excluded: delta, which is derived;
prices, which are market data; and the UCC's limit category, which is date-effective and
belongs in its own table rather than repeated on every position row where it could drift.

**No prices are needed anywhere.** FutEq OI is measured in shares - para 5.1.1 defines delta as
a multiple of the notional position, Table 1 shows 300 long futures as FutEq OI 300, and the
headroom reconciliation matches NSE's published column on 216 of 216 rows, which it could not do
if one side were rupees. NSE's `Contract_Delta` file gives the delta factor per unit with the
pricing already done: exactly 1.0 for futures, [0, 1] for calls, [-1, 0] for puts. So

    FutEq delta (shares) = sum over contracts of  delta_factor x quantity_lots x lot_size

and a signed `quantity_lots` produces the right sign without special-casing: a short call takes
factor +0.5 to a negative contribution, which is 5.1.1's "effective delta for short calls is
negative".

**A known gap in the circular, recorded rather than modelled.** Table 2 day 2 says a long
futures position shows a "passive increase in EoD delta by 5%" when the underlying appreciates
5%. In share terms it does not: the factor is exactly 1.0 and the position is unchanged, so the
FutEq delta is identical. The provision is real and bites on options, whose factors move with
the underlying; the futures illustration does not reproduce. See `docs/doubts.md`.
"""

from __future__ import annotations

import csv
import datetime as dt
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from pathlib import Path

__all__ = [
    "Instrument",
    "Position",
    "PropBook",
    "DeltaFactors",
    "BookError",
    "load_book",
    "load_books",
    "load_delta_factors",
    "load_delta_factors_by_date",
    "futeq_delta",
]


class Instrument(Enum):
    """A contract's kind. NSE writes `FF` for futures, not `FUT`; the mapping lives here."""

    FUT = "FUT"
    CE = "CE"
    PE = "PE"

    @classmethod
    def from_nse(cls, value: str) -> Instrument:
        """`FF` -> FUT, `CE` -> CE, `PE` -> PE, as NSE's `Contract_Delta` file writes them."""
        text = value.strip().upper()
        if text == "FF":
            return cls.FUT
        try:
            return cls(text)
        except ValueError as exc:
            raise BookError(
                f"unknown option type {value!r}. NSE's Contract_Delta file uses FF, CE and PE."
            ) from exc

    @property
    def is_option(self) -> bool:
        return self is not Instrument.FUT


class BookError(Exception):
    """A position or a delta lookup that cannot be trusted."""


@dataclass(frozen=True)
class Position:
    """One UCC's holding in one contract at the end of one day.

    Frozen for the same reason `MwplRow` and `Threshold` are: nothing downstream should be able
    to edit a position into compliance.
    """

    trade_date: dt.date
    ucc: str
    isin: str
    instrument: Instrument
    expiry: dt.date
    strike: Decimal | None
    lot_size: int
    #: Signed: positive long, negative short. Never zero - see `__post_init__`.
    quantity_lots: int

    def __post_init__(self) -> None:
        # A strike is exactly what distinguishes an option from a future, so the two fields
        # cannot disagree. Same XOR shape as MwplRow's headroom/flag pair.
        if self.instrument.is_option:
            if self.strike is None:
                raise BookError(
                    f"{self.ucc} {self.isin} {self.instrument.value} expiring {self.expiry}: "
                    f"an option needs a strike."
                )
            if self.strike <= 0:
                raise BookError(
                    f"{self.ucc} {self.isin} {self.instrument.value}: strike is {self.strike}. "
                    f"A strike of zero is how NSE writes a FUTURES row, not a real option."
                )
        elif self.strike is not None:
            raise BookError(
                f"{self.ucc} {self.isin} FUT expiring {self.expiry}: carries strike "
                f"{self.strike}. A future has no strike."
            )

        if self.lot_size <= 0:
            raise BookError(f"{self.ucc} {self.isin}: lot_size is {self.lot_size}.")

        # A closed position is the absence of a record, not a zero row. The two-day comparison
        # therefore has to read "absent" as zero on BOTH sides, which is where an off-by-one
        # would live: a position opened yesterday and closed today, and one opened today that
        # did not exist yesterday, are the cases to check.
        if self.quantity_lots == 0:
            raise BookError(
                f"{self.ucc} {self.isin} {self.instrument.value} expiring {self.expiry}: "
                f"quantity_lots is 0. A closed position is no record, not a zero row."
            )

        if self.expiry < self.trade_date:
            raise BookError(
                f"{self.ucc} {self.isin} {self.instrument.value}: expiry {self.expiry} is before "
                f"the trade date {self.trade_date}. An expired contract is not a holding."
            )

        if not self.isin or self.isin.strip().upper() in {"NA", "NAN", "-"}:
            raise BookError(
                f"{self.ucc} on {self.trade_date}: ISIN is {self.isin!r}. The book is keyed on "
                f"ISIN, and index derivatives carry no ISIN - they are out of scope until "
                f"SPEC rows 8 and 9 are implemented, which needs the key to widen."
            )

        if not self.ucc.strip():
            raise BookError(f"{self.isin} on {self.trade_date}: no UCC. Row 7's limit "
                            f"categories hang off the UCC, so it cannot be blank.")

    @property
    def key(self) -> tuple:
        """What makes a position unique within a day: one record per contract per UCC."""
        return (self.trade_date, self.ucc, self.isin, self.instrument, self.expiry, self.strike)

    @property
    def contract(self) -> tuple:
        """The contract alone, without the date or holder - for comparing two days."""
        return (self.isin, self.instrument, self.expiry, self.strike)

    @property
    def quantity_shares(self) -> int:
        """Signed position in shares, before any delta is applied."""
        return self.quantity_lots * self.lot_size


class PropBook:
    """One day's positions, validated, with no two records for the same contract and UCC."""

    def __init__(self, positions: Iterable[Position]) -> None:
        rows = tuple(positions)
        if not rows:
            raise BookError("an empty book is not a day's positions; it is a missing file")

        dates = {p.trade_date for p in rows}
        if len(dates) > 1:
            raise BookError(
                f"positions span {len(dates)} dates ({min(dates)}..{max(dates)}). A PropBook is "
                f"one day, because the ban-period check compares two of them."
            )

        seen: dict[tuple, Position] = {}
        for p in rows:
            if p.key in seen:
                raise BookError(
                    f"{p.ucc} holds two records for {p.isin} {p.instrument.value} expiring "
                    f"{p.expiry}. Net them before storing: two rows for one contract make the "
                    f"day's delta depend on which one is read."
                )
            seen[p.key] = p

        self.positions = rows
        self.trade_date = dates.pop()

    def __len__(self) -> int:
        return len(self.positions)

    def __iter__(self):
        return iter(self.positions)

    def __repr__(self) -> str:
        return (
            f"<PropBook {self.trade_date} {len(self.positions)} position(s), "
            f"{len(self.uccs)} UCC(s), {len(self.isins)} scrip(s)>"
        )

    @property
    def uccs(self) -> tuple[str, ...]:
        return tuple(sorted({p.ucc for p in self.positions}))

    @property
    def isins(self) -> tuple[str, ...]:
        return tuple(sorted({p.isin for p in self.positions}))

    def for_ucc(self, ucc: str, isin: str | None = None) -> tuple[Position, ...]:
        return tuple(
            p for p in self.positions
            if p.ucc == ucc and (isin is None or p.isin == isin)
        )

    def for_isin(self, isin: str) -> tuple[Position, ...]:
        return tuple(p for p in self.positions if p.isin == isin)


class DeltaFactors:
    """NSE's published per-contract delta factors for one date.

    Keyed on **symbol**, not ISIN, because that is how NSE writes the file - so using it with an
    ISIN-keyed book needs the symbol resolution through `combineoi`, which is #011 Q2's
    constraint deciding an interface for the third time.
    """

    def __init__(self, trade_date: dt.date, factors: Mapping[tuple, float]) -> None:
        self.trade_date = trade_date
        self._factors = dict(factors)

    def __len__(self) -> int:
        return len(self._factors)

    def __repr__(self) -> str:
        return f"<DeltaFactors {self.trade_date} {len(self._factors)} contract(s)>"

    def factor(self, symbol: str, instrument: Instrument, expiry: dt.date,
               strike: Decimal | None) -> float:
        """The delta factor per unit for one contract. Refuses rather than defaulting to 1.

        A missing contract is not a futures row and not a zero. It means the position is in
        something NSE did not publish a delta for that day, which needs a person.
        """
        key = (symbol.strip().upper(), instrument, expiry, Decimal(0) if strike is None else strike)
        try:
            return self._factors[key]
        except KeyError:
            raise BookError(
                f"no delta factor published for {symbol} {instrument.value} expiring {expiry}"
                + (f" strike {strike}" if strike is not None else "")
                + f" on {self.trade_date}. Not defaulted to 1.0 - a missing factor is a "
                f"position in a contract NSE did not price, which needs a person."
            ) from None


def futeq_delta(
    positions: Iterable[Position],
    factors: DeltaFactors,
    symbol_for_isin: Mapping[str, str],
) -> float:
    """FutEq delta in **shares** for a set of positions, netted as 5.1.1 defines it.

    `sum( delta_factor x quantity_lots x lot_size )`. Netting happens naturally because
    `quantity_lots` is signed; 5.1.2's gross addition across UCCs is the caller's job, since
    whether to net or gross-add depends on which limit is being checked.
    """
    total = 0.0
    for p in positions:
        try:
            symbol = symbol_for_isin[p.isin]
        except KeyError:
            raise BookError(
                f"no symbol known for {p.isin}. NSE's delta file is keyed on symbol, so the "
                f"book's ISINs have to be resolved through that day's combineoi (#011 Q2)."
            ) from None
        factor = factors.factor(symbol, p.instrument, p.expiry, p.strike)
        total += factor * p.quantity_shares
    return total


# -- loading ------------------------------------------------------------------------------


def load_book(path: str | Path) -> PropBook:
    """Read a day's synthetic positions from CSV.

    Read with the `csv` module rather than pandas on purpose: pandas' default missing-value list
    includes the literal string "NA", which once silently disarmed the index guard in
    `parse_mwpl_file()`.
    """
    rows: list[Position] = []
    with Path(path).open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        expected = {"trade_date", "ucc", "isin", "instrument", "expiry", "strike",
                    "lot_size", "quantity_lots"}
        missing = expected - set(reader.fieldnames or [])
        if missing:
            raise BookError(f"{path}: missing column(s) {sorted(missing)}")

        for lineno, rec in enumerate(reader, start=2):
            if not rec["isin"].strip():
                continue
            strike_text = rec["strike"].strip()
            try:
                rows.append(Position(
                    trade_date=dt.date.fromisoformat(rec["trade_date"].strip()),
                    ucc=rec["ucc"].strip(),
                    isin=rec["isin"].strip(),
                    instrument=Instrument.from_nse(rec["instrument"]),
                    expiry=dt.date.fromisoformat(rec["expiry"].strip()),
                    strike=None if strike_text in ("", "0") else Decimal(strike_text),
                    lot_size=int(rec["lot_size"]),
                    quantity_lots=int(rec["quantity_lots"]),
                ))
            except BookError as exc:
                raise BookError(f"{path} line {lineno}: {exc}") from exc
            except (ValueError, KeyError) as exc:
                raise BookError(f"{path} line {lineno}: {exc}") from exc
    return PropBook(rows)


def load_books(path: str | Path) -> dict[dt.date, PropBook]:
    """Read a multi-day positions CSV into one PropBook per date.

    A PropBook is deliberately one day, because the ban-period check compares two of them. This
    is the loader for a file holding several - a scenario fixture, or a replay.
    """
    by_date: dict[dt.date, list[Position]] = {}
    with Path(path).open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for lineno, rec in enumerate(reader, start=2):
            if not rec.get("isin", "").strip():
                continue
            strike_text = rec["strike"].strip()
            try:
                pos = Position(
                    trade_date=dt.date.fromisoformat(rec["trade_date"].strip()),
                    ucc=rec["ucc"].strip(),
                    isin=rec["isin"].strip(),
                    instrument=Instrument.from_nse(rec["instrument"]),
                    expiry=dt.date.fromisoformat(rec["expiry"].strip()),
                    strike=None if strike_text in ("", "0") else Decimal(strike_text),
                    lot_size=int(rec["lot_size"]),
                    quantity_lots=int(rec["quantity_lots"]),
                )
            except (BookError, ValueError, KeyError) as exc:
                raise BookError(f"{path} line {lineno}: {exc}") from exc
            by_date.setdefault(pos.trade_date, []).append(pos)
    if not by_date:
        raise BookError(f"{path}: no positions")
    return {d: PropBook(rows) for d, rows in sorted(by_date.items())}


def load_delta_factors(path: str | Path) -> DeltaFactors:
    """Read NSE's `Contract_Delta_<ddmmyyyy>.csv`.

    Columns: `Date, Symbol, Expiry day, Strike Price, Option Type, Delta Factor`. Futures rows
    carry `Option Type` of `FF`, a strike of 0 and a factor of exactly 1.0.
    """
    factors: dict[tuple, float] = {}
    dates: set[dt.date] = set()
    with Path(path).open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        expected = {"Date", "Symbol", "Expiry day", "Strike Price", "Option Type", "Delta Factor"}
        missing = expected - set(reader.fieldnames or [])
        if missing:
            raise BookError(
                f"{path}: missing column(s) {sorted(missing)}. A renamed column means the "
                f"format changed - see the 7 Dec 2026 cutover in docs/READING.md."
            )
        for lineno, rec in enumerate(reader, start=2):
            if not rec["Symbol"].strip():
                continue
            dates.add(_parse_nse_date(rec["Date"], path, lineno))
            # Checked here rather than after the loop, because the key below does not include
            # the date: a second date makes every contract look like a duplicate and the
            # error would name the wrong problem.
            if len(dates) > 1:
                raise BookError(
                    f"{path} line {lineno}: more than one trade date "
                    f"({', '.join(str(d) for d in sorted(dates))}). NSE publishes one file per "
                    f"day, so this reader expects one trade date; use "
                    f"load_delta_factors_by_date() for a file holding several."
                )
            key = (
                rec["Symbol"].strip().upper(),
                Instrument.from_nse(rec["Option Type"]),
                _parse_nse_date(rec["Expiry day"], path, lineno),
                Decimal(rec["Strike Price"].strip() or "0"),
            )
            if key in factors:
                raise BookError(f"{path} line {lineno}: contract {key[0]} listed twice")
            factors[key] = float(rec["Delta Factor"])

    if len(dates) != 1:
        raise BookError(f"{path}: expected one trade date, found {sorted(dates)}")
    return DeltaFactors(dates.pop(), factors)


def load_delta_factors_by_date(path: str | Path) -> dict[dt.date, DeltaFactors]:
    """Read a multi-day delta file into one  per date.

    NSE publishes one file per day, so  requiring a single date is the
    faithful reader. This is for a scenario fixture or a replay that holds several.
    """
    buckets: dict[dt.date, dict[tuple, float]] = {}
    with Path(path).open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        expected = {"Date", "Symbol", "Expiry day", "Strike Price", "Option Type",
                    "Delta Factor"}
        missing = expected - set(reader.fieldnames or [])
        if missing:
            raise BookError(f"{path}: missing column(s) {sorted(missing)}")
        for lineno, rec in enumerate(reader, start=2):
            if not rec["Symbol"].strip():
                continue
            day = _parse_nse_date(rec["Date"], path, lineno)
            key = (
                rec["Symbol"].strip().upper(),
                Instrument.from_nse(rec["Option Type"]),
                _parse_nse_date(rec["Expiry day"], path, lineno),
                Decimal(rec["Strike Price"].strip() or "0"),
            )
            bucket = buckets.setdefault(day, {})
            if key in bucket:
                raise BookError(f"{path} line {lineno}: {key[0]} listed twice for {day}")
            bucket[key] = float(rec["Delta Factor"])
    if not buckets:
        raise BookError(f"{path}: no delta factors")
    return {d: DeltaFactors(d, f) for d, f in sorted(buckets.items())}


def _parse_nse_date(text: str, path: str | Path, lineno: int) -> dt.date:
    """NSE writes `30-10-2026` in this file - day first, numeric month."""
    try:
        return dt.datetime.strptime(text.strip(), "%d-%m-%Y").date()
    except ValueError as exc:
        raise BookError(f"{path} line {lineno}: {text!r} is not a d-m-Y date") from exc
