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
    """One day's positions, validated, with no two records for the same contract and UCC.

    A day can be in three conditions, and they must stay distinguishable:

        positions were held          PropBook([...])
        verified: nothing was held   PropBook.flat(trade_date)
        the file never arrived       no PropBook at all - the caller's lookup fails

    The last two used to share a representation (`None`), and once two facts share a value
    nothing downstream can separate them again: a missing today-file read as every holder
    having closed out, which hid a real breach. So `PropBook([])` still refuses - an empty list
    is what a missing file produces by accident - and a flat day can only be built by saying so,
    with a date. The constructor's name is the assertion. See `DECISIONS.md` #015.
    """

    @classmethod
    def flat(cls, trade_date: dt.date) -> PropBook:
        """A day on which it is VERIFIED that nothing was held.

        Carries its date so a flat yesterday can still be checked against the trading calendar -
        under a `None` representation that check was impossible on exactly the days it mattered.
        Built by `load_books()` from an explicit FLAT marker row, never from an absence.
        """
        book = cls.__new__(cls)
        book.positions = ()
        book.trade_date = trade_date
        return book

    @property
    def is_flat(self) -> bool:
        return not self.positions

    def __init__(self, positions: Iterable[Position]) -> None:
        rows = tuple(positions)
        if not rows:
            raise BookError(
                "an empty book is not a day's positions; it is what a missing file looks like. "
                "A day on which nothing was held is PropBook.flat(trade_date)."
            )

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

    def __init__(self, trade_date: dt.date, factors: Mapping[tuple, Decimal]) -> None:
        # A float factor is refused rather than converted, because converting is the bug.
        # Decimal(0.35) is 0.34999999999999997779553950749686919152736663818359375, so
        # accepting a float here would reintroduce exactly the inexactness Decimal is used to
        # avoid - while looking like it had been fixed. A str or an int is converted, since
        # both are exact.
        clean: dict[tuple, Decimal] = {}
        for key, value in factors.items():
            if isinstance(value, float):
                raise BookError(
                    f"delta factor for {key[0]} is a float ({value!r}). Pass a Decimal or the "
                    f"string NSE published - Decimal(float) carries the float's binary error, "
                    f"so converting here would hide it rather than fix it."
                )
            clean[key] = value if isinstance(value, Decimal) else Decimal(value)
        self.trade_date = trade_date
        self._factors = clean

    def __len__(self) -> int:
        return len(self._factors)

    def __repr__(self) -> str:
        return f"<DeltaFactors {self.trade_date} {len(self._factors)} contract(s)>"

    def factor(self, symbol: str, instrument: Instrument, expiry: dt.date,
               strike: Decimal | None) -> Decimal:
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


def live_on(positions: Iterable[Position], day: dt.date) -> tuple[Position, ...]:
    """The positions whose contract has not expired before `day`.

    Selection only - it decides nothing about limits. It exists because the ban-period baseline
    revalues **yesterday's** holdings at **today's** factors, and NSE publishes no factor for a
    contract that has already expired, so a lookup for one refuses. Expiry is the single case
    where a missing factor is expected rather than a finding, which is why it is filtered here
    instead of by weakening `DeltaFactors.factor()`.

    `expiry < day` is strict: on its expiry day a contract is still live and NSE still publishes
    its factor. The comparison uses the contract's own `expiry` field rather than a computed
    "last Thursday", because NSE moves an expiry earlier when it would fall on a holiday - as
    November 2026 shows, where the 24th is Guru Nanak Jayanti.

    The rule this serves is recorded in `DECISIONS.md`: an expired contract contributes zero to
    the baseline, because its delta disappeared without the holder doing anything. Indian stock
    derivatives are physically settled, so at expiry the position stops being an F&O position
    and becomes a delivery obligation in the cash market; either way its F&O delta is gone.
    """
    return tuple(p for p in positions if p.expiry >= day)


def futeq_delta(
    positions: Iterable[Position],
    factors: DeltaFactors,
    symbol_for_isin: Mapping[str, str],
) -> Decimal:
    """FutEq delta in **shares** for a set of positions, netted as 5.1.1 defines it.

    `sum( delta_factor x quantity_lots x lot_size )`. Netting happens naturally because
    `quantity_lots` is signed; 5.1.2's gross addition across UCCs is the caller's job, since
    whether to net or gross-add depends on which limit is being checked.
    """
    # Decimal, not float. When nothing was traded, a day's delta and the same holdings
    # revalued must come out EXACTLY equal, because the ban-period band compares them with
    # <=. Two float sums over the same values in a different order can differ by about 1e-12,
    # and that difference reads as an entity having created delta it never created. NSE writes
    # its factors as short decimal strings, so Decimal holds them exactly.
    #
    # This is not the opposite of the reconciliation decision, where float was right: there the
    # residual is never near zero, so nothing rested on exact equality. Here everything does.
    total = Decimal(0)
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
#
# Every reader here follows the rule stated in `parsers.py`: **skip what carries no
# information, refuse what carries information you cannot read.** A row with every field blank
# is trailing whitespace in a CSV and carries nothing. A row with a quantity and no ISIN is a
# real position whose key is missing, and dropping it would understate that UCC's delta - which
# is the direction that hides a breach rather than inventing one.
#
# All four loaders went out skipping on one blank field instead, which is why the check is a
# named function used by all of them rather than a condition written four times.


def _is_blank_row(rec: Mapping[str, str | None]) -> bool:
    """True only when every field is empty. Anything else has to parse or fail."""
    return all(not (value or "").strip() for value in rec.values())


def _require_columns(reader: csv.DictReader, expected: set[str], path: str | Path) -> None:
    """A renamed column means the format changed - see the 7 Dec 2026 cutover in READING.md."""
    missing = expected - set(reader.fieldnames or [])
    if missing:
        raise BookError(f"{path}: missing column(s) {sorted(missing)}")


def _parse_strike(text: str, instrument: Instrument) -> Decimal | None:
    """Turn the strike column into a value, deciding by instrument rather than by spelling.

    NSE writes a futures row with a strike of 0, which can arrive as `0`, `0.00` or blank. The
    earlier version special-cased the literal string `"0"`, so `0.00` on a futures row raised
    "a future has no strike" and `0` on an option raised "an option needs a strike" rather than
    the accurate complaint. Parsing first and deciding by instrument fixes both.

    An option carrying a genuine zero is passed through, so `Position.__post_init__` can say the
    useful thing: a zero strike is how NSE writes futures, so the row is probably mis-parsed.
    """
    text = text.strip()
    if text == "":
        return None
    value = Decimal(text)
    if value == 0 and instrument is Instrument.FUT:
        return None
    return value


_POSITION_COLUMNS = {
    "trade_date", "ucc", "isin", "instrument", "expiry", "strike", "lot_size", "quantity_lots",
}


def _parse_position(rec: Mapping[str, str], path: str | Path, lineno: int) -> Position:
    """One row to one Position. The single place a position row is understood.

    `load_book()` and `load_books()` both go through here, because two copies of this is how
    one of them gets fixed and the other does not.
    """
    try:
        instrument = Instrument.from_nse(rec["instrument"])
        return Position(
            trade_date=dt.date.fromisoformat(rec["trade_date"].strip()),
            ucc=rec["ucc"].strip(),
            isin=rec["isin"].strip(),
            instrument=instrument,
            expiry=dt.date.fromisoformat(rec["expiry"].strip()),
            strike=_parse_strike(rec["strike"], instrument),
            lot_size=int(rec["lot_size"]),
            quantity_lots=int(rec["quantity_lots"]),
        )
    except BookError as exc:
        raise BookError(f"{path} line {lineno}: {exc}") from exc
    except (ValueError, KeyError, ArithmeticError) as exc:
        raise BookError(f"{path} line {lineno}: {exc}") from exc


def load_books(path: str | Path) -> dict[dt.date, PropBook]:
    """Read a positions CSV into one `PropBook` per date.

    A `PropBook` is deliberately one day, because the ban-period check compares two of them.
    This is the reader for a file holding several - a scenario fixture, or a replay.

    Read with the `csv` module rather than pandas on purpose: pandas' default missing-value list
    includes the literal string "NA", which once silently disarmed the index guard in
    `parse_mwpl_file()`.
    """
    by_date: dict[dt.date, list[Position]] = {}
    flat_dates: dict[dt.date, int] = {}
    with Path(path).open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        _require_columns(reader, _POSITION_COLUMNS, path)
        for lineno, rec in enumerate(reader, start=2):
            if _is_blank_row(rec):
                continue
            if (rec.get("instrument") or "").strip().upper() == _FLAT_MARKER:
                day = _parse_flat_row(rec, path, lineno)
                if day in flat_dates:
                    raise BookError(
                        f"{path} line {lineno}: a second FLAT row for {day} (the first is on line "
                        f"{flat_dates[day]}). One marker per day; two means the file was "
                        f"assembled carelessly, and that is worth a person's attention."
                    )
                flat_dates[day] = lineno
                continue
            position = _parse_position(rec, path, lineno)
            by_date.setdefault(position.trade_date, []).append(position)

    both = sorted(set(flat_dates) & set(by_date))
    if both:
        day = both[0]
        raise BookError(
            f"{path} line {flat_dates[day]}: {day} is marked FLAT and also has "
            f"{len(by_date[day])} position row(s). The file contradicts itself about that day, "
            f"so neither statement can be trusted."
        )

    if not by_date and not flat_dates:
        raise BookError(
            f"{path}: a header and no rows. That is what a truncated or failed write looks like, "
            f"so it is refused rather than read as a flat day. A day on which nothing was held "
            f"is written as one FLAT marker row: '<date>,,,FLAT,,,,'."
        )

    books = {day: PropBook(rows) for day, rows in by_date.items()}
    books.update({day: PropBook.flat(day) for day in flat_dates})
    return dict(sorted(books.items()))


#: The `instrument` value that marks a verified flat day. The marker is the COMBINATION of this
#: value and every other field except the date being blank - see `_parse_flat_row()`.
_FLAT_MARKER = "FLAT"


def _parse_flat_row(rec: Mapping[str, str], path: str | Path, lineno: int) -> dt.date:
    """A FLAT marker row: a date, the word FLAT, and nothing else.

    Overloading the `instrument` column is safe only because every other field must be blank.
    That refusal is what stops a half-written position row - one that happens to carry FLAT in
    the wrong column - from passing as an assertion that nothing was held.
    """
    filled = sorted(
        k for k, v in rec.items()
        if k not in ("trade_date", "instrument") and (v or "").strip()
    )
    if filled:
        raise BookError(
            f"{path} line {lineno}: a FLAT row must carry only a date, but {', '.join(filled)} "
            f"{'is' if len(filled) == 1 else 'are'} filled. A marker that also looks like a "
            f"position is neither."
        )
    try:
        return dt.date.fromisoformat((rec.get("trade_date") or "").strip())
    except ValueError as exc:
        raise BookError(
            f"{path} line {lineno}: a FLAT row's date {rec.get('trade_date')!r} is not "
            f"YYYY-MM-DD. The marker exists to state the date, so it has to be readable."
        ) from exc


def load_book(path: str | Path) -> PropBook:
    """Read a single day's positions. Refuses a file holding more than one date."""
    books = load_books(path)
    if len(books) > 1:
        raise BookError(
            f"{path}: more than one trade date "
            f"({', '.join(str(d) for d in sorted(books))}). A PropBook is one day; use "
            f"load_books() for a file holding several."
        )
    return next(iter(books.values()))


_DELTA_COLUMNS = {
    "Date", "Symbol", "Expiry day", "Strike Price", "Option Type", "Delta Factor",
}


def _delta_key_and_factor(
    rec: Mapping[str, str], path: str | Path, lineno: int
) -> tuple[dt.date, tuple, Decimal]:
    """One `Contract_Delta` row to a date, a contract key and a factor.

    The factor is a `Decimal` parsed from NSE's text, not a float. NSE writes short decimal
    strings - `1.00000000`, `-0.40000000` - so `Decimal` holds them exactly, which matters
    because the ban-period check compares a day's delta against the same holdings revalued and
    those two must come out EXACTLY equal when nothing was traded. Two float sums over the same
    values in a different order can differ by about 1e-12, and that difference reads as an
    entity having created delta it never created.
    """
    symbol = rec["Symbol"].strip().upper()
    if not symbol:
        raise BookError(
            f"{path} line {lineno}: no symbol, but the row carries a delta factor "
            f"({rec['Delta Factor']!r}). Dropping it would leave a position in that contract "
            f"with no factor, which refuses later and points at the wrong file."
        )
    instrument = Instrument.from_nse(rec["Option Type"])
    key = (
        symbol,
        instrument,
        _parse_nse_date(rec["Expiry day"], path, lineno),
        Decimal(rec["Strike Price"].strip() or "0"),
    )
    try:
        factor = Decimal(rec["Delta Factor"].strip())
    except ArithmeticError as exc:
        raise BookError(
            f"{path} line {lineno}: delta factor {rec['Delta Factor']!r} is not a number"
        ) from exc
    return _parse_nse_date(rec["Date"], path, lineno), key, factor


def load_delta_factors(path: str | Path) -> DeltaFactors:
    """Read NSE's `Contract_Delta_<ddmmyyyy>.csv`, which holds exactly one trade date.

    Columns: `Date, Symbol, Expiry day, Strike Price, Option Type, Delta Factor`. Futures rows
    carry an `Option Type` of `FF`, a strike of 0 and a factor of exactly 1.00000000.
    """
    by_date = load_delta_factors_by_date(path)
    if len(by_date) > 1:
        raise BookError(
            f"{path}: more than one trade date "
            f"({', '.join(str(d) for d in sorted(by_date))}). NSE publishes one file per day, "
            f"so this reader expects one; use load_delta_factors_by_date() for a file holding "
            f"several."
        )
    return next(iter(by_date.values()))


def load_delta_factors_by_date(path: str | Path) -> dict[dt.date, DeltaFactors]:
    """Read a multi-day delta file into one `DeltaFactors` per date.

    NSE publishes one file per day, so `load_delta_factors()` requiring a single date is the
    faithful reader. This is for a scenario fixture or a replay that holds several.
    """
    buckets: dict[dt.date, dict[tuple, Decimal]] = {}
    with Path(path).open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        _require_columns(reader, _DELTA_COLUMNS, path)
        for lineno, rec in enumerate(reader, start=2):
            if _is_blank_row(rec):
                continue
            day, key, factor = _delta_key_and_factor(rec, path, lineno)
            bucket = buckets.setdefault(day, {})
            if key in bucket:
                raise BookError(
                    f"{path} line {lineno}: {key[0]} {key[1].value} expiring {key[2]} listed "
                    f"twice for {day}"
                )
            bucket[key] = factor

    if not buckets:
        raise BookError(f"{path}: no delta factors")
    return {day: DeltaFactors(day, factors) for day, factors in sorted(buckets.items())}


def _parse_nse_date(text: str, path: str | Path, lineno: int) -> dt.date:
    """NSE writes `30-10-2026` in this file - day first, numeric month."""
    try:
        return dt.datetime.strptime(text.strip(), "%d-%m-%Y").date()
    except ValueError as exc:
        raise BookError(f"{path} line {lineno}: {text!r} is not a d-m-Y date") from exc
