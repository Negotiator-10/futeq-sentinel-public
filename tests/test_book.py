"""Tests for `sentinel.book` - the synthetic prop book and the FutEq delta it comes to.

Grouped by what each defends:

* a position that cannot be constructed in a contradictory state, the same discipline as
  `MwplRow.__post_init__`;
* the sign handling, checked against para 5.1.1's own words rather than against intuition;
* SEBI 2025/79 Table 2, reproduced day by day from a fixture, which is the oracle
  `check_ban_period_reduction()` will be written against;
* two tests that record a limitation rather than a guarantee, including the day of Table 2 that
  does not reproduce at all.

All positions are synthetic. The fixture is SEBI's illustration, not a real book.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal
from pathlib import Path

import pytest

from sentinel.book import (
    BookError,
    DeltaFactors,
    Instrument,
    Position,
    PropBook,
    futeq_delta,
    load_book,
    load_books,
    load_delta_factors,
    load_delta_factors_by_date,
)

FIXTURES = Path(__file__).parent / "fixtures" / "book"
ISIN = "INE114A01011"
SYMBOL = {ISIN: "SAIL"}
EXPIRY = dt.date(2026, 10, 27)
DAY = dt.date(2026, 10, 12)


def pos(instrument=Instrument.FUT, *, qty=1, strike=None, day=DAY, ucc="UCC001",
        isin=ISIN, lot=1000, expiry=EXPIRY) -> Position:
    return Position(trade_date=day, ucc=ucc, isin=isin, instrument=instrument,
                    expiry=expiry, strike=strike, lot_size=lot, quantity_lots=qty)


@pytest.fixture(scope="module")
def books():
    return load_books(FIXTURES / "table2_positions.csv")


@pytest.fixture(scope="module")
def deltas():
    return load_delta_factors_by_date(FIXTURES / "table2_deltas.csv")


# -- a contradictory position cannot be constructed ---------------------------------------


def test_an_option_without_a_strike_is_refused():
    with pytest.raises(BookError, match="an option needs a strike"):
        pos(Instrument.CE)


def test_a_future_with_a_strike_is_refused():
    with pytest.raises(BookError, match="A future has no strike"):
        pos(Instrument.FUT, strike=Decimal("120"))


def test_a_zero_strike_option_is_refused():
    # Zero is how NSE writes a FUTURES row in Contract_Delta, so an option carrying it is
    # almost certainly a mis-parsed futures line rather than a real contract.
    with pytest.raises(BookError, match="how NSE writes a FUTURES row"):
        pos(Instrument.PE, strike=Decimal("0"))


def test_a_zero_quantity_is_refused():
    """A closed position is the absence of a record, not a zero row.

    Which means the two-day comparison has to read "absent" as zero on both sides - the two
    cases to get right are a position opened yesterday and closed today, and one opened today
    that did not exist yesterday.
    """
    with pytest.raises(BookError, match="no record, not a zero row"):
        pos(qty=0)


def test_an_expired_contract_is_not_a_holding():
    with pytest.raises(BookError, match="is before the trade date"):
        pos(expiry=dt.date(2026, 10, 11))


def test_a_contract_expiring_today_is_still_a_holding():
    assert pos(expiry=DAY).expiry == DAY


def test_an_index_position_is_refused():
    # Indices carry no ISIN (#011 Q2). SPEC rows 8 and 9 need them, and the key has to widen
    # before they can be represented - so refusing now is a deliberate deferral, not an
    # oversight, and this test is what makes it deliberate.
    for bad in ("NA", "nan", "-", ""):
        with pytest.raises(BookError, match="index derivatives carry no ISIN"):
            pos(isin=bad)


def test_a_blank_ucc_is_refused():
    with pytest.raises(BookError, match="limit categories hang off the UCC"):
        pos(ucc="   ")


def test_a_non_positive_lot_size_is_refused():
    with pytest.raises(BookError, match="lot_size"):
        pos(lot=0)


def test_a_position_is_frozen():
    p = pos()
    with pytest.raises(Exception):
        p.quantity_lots = 5  # type: ignore[misc]


# -- the book is one day, with one record per contract per UCC ----------------------------


def test_a_book_spanning_two_days_is_refused():
    with pytest.raises(BookError, match="A PropBook is one day"):
        PropBook([pos(), pos(day=dt.date(2026, 10, 13))])


def test_two_records_for_one_contract_and_ucc_are_refused():
    with pytest.raises(BookError, match="two records for"):
        PropBook([pos(qty=1), pos(qty=2)])


def test_the_same_contract_for_two_uccs_is_fine():
    book = PropBook([pos(ucc="UCC001"), pos(ucc="UCC002")])
    assert len(book) == 2
    assert book.uccs == ("UCC001", "UCC002")


def test_an_empty_book_is_a_missing_file_not_a_day():
    with pytest.raises(BookError, match="missing file"):
        PropBook([])


# -- NSE's vocabulary, at the boundary ----------------------------------------------------


def test_nse_writes_ff_for_futures():
    assert Instrument.from_nse("FF") is Instrument.FUT
    assert Instrument.from_nse("ff") is Instrument.FUT
    assert Instrument.from_nse("CE") is Instrument.CE
    assert Instrument.from_nse("PE") is Instrument.PE


def test_an_unknown_option_type_is_refused():
    with pytest.raises(BookError, match="uses FF, CE and PE"):
        Instrument.from_nse("FUTSTK")


# -- the signs, against para 5.1.1's own words --------------------------------------------


def test_long_futures_delta_is_the_position_itself():
    """5.1.1: "long futures have a delta of +1 times notional". In shares, so no price."""
    factors = DeltaFactors(DAY, {("SAIL", Instrument.FUT, EXPIRY, Decimal(0)): Decimal("1.00000000")})
    assert futeq_delta([pos(qty=1)], factors, SYMBOL) == 1000.0
    assert futeq_delta([pos(qty=-1)], factors, SYMBOL) == -1000.0


def test_a_short_call_contributes_negative_delta():
    """5.1.1: "effective delta for short calls is negative".

    NSE publishes the call's own factor as positive; the sign comes from `quantity_lots`, so
    nothing special-cases it.
    """
    factors = DeltaFactors(DAY, {("SAIL", Instrument.CE, EXPIRY, Decimal("140")): Decimal("0.35000000")})
    short_call = pos(Instrument.CE, qty=-1, strike=Decimal("140"))
    assert futeq_delta([short_call], factors, SYMBOL) == pytest.approx(-350.0)


def test_a_short_put_contributes_positive_delta():
    """5.1.1: "that of short put is positive". NSE's put factor is negative, the holding is
    short, and the product comes out positive without a rule being written for it."""
    factors = DeltaFactors(DAY, {("SAIL", Instrument.PE, EXPIRY, Decimal("120")): Decimal("-0.40000000")})
    short_put = pos(Instrument.PE, qty=-1, strike=Decimal("120"))
    assert futeq_delta([short_put], factors, SYMBOL) == pytest.approx(400.0)


def test_a_long_put_contributes_negative_delta():
    factors = DeltaFactors(DAY, {("SAIL", Instrument.PE, EXPIRY, Decimal("120")): Decimal("-0.40000000")})
    assert futeq_delta([pos(Instrument.PE, qty=1, strike=Decimal("120"))],
                       factors, SYMBOL) == pytest.approx(-400.0)


def test_positions_net_within_a_holder():
    """5.1.2 nets within a UCC. Gross addition ACROSS UCCs is the caller's job, because whether
    to net or gross-add depends on which limit is being checked."""
    factors = DeltaFactors(DAY, {
        ("SAIL", Instrument.FUT, EXPIRY, Decimal(0)): Decimal("1.00000000"),
        ("SAIL", Instrument.PE, EXPIRY, Decimal("120")): Decimal("-0.40000000"),
    })
    held = [pos(qty=1), pos(Instrument.PE, qty=1, strike=Decimal("120"))]
    assert futeq_delta(held, factors, SYMBOL) == pytest.approx(600.0)


# -- a missing factor refuses rather than defaulting --------------------------------------


def test_a_missing_delta_factor_is_refused_not_defaulted():
    """Defaulting to 1.0 would silently treat an unpriced option as a futures position."""
    factors = DeltaFactors(DAY, {("SAIL", Instrument.FUT, EXPIRY, Decimal(0)): Decimal("1.00000000")})
    with pytest.raises(BookError, match="Not defaulted to 1.0"):
        futeq_delta([pos(Instrument.CE, qty=1, strike=Decimal("140"))], factors, SYMBOL)


def test_an_unresolvable_isin_is_refused():
    """NSE's delta file is keyed on symbol, so the book's ISINs need resolving - #011 Q2."""
    factors = DeltaFactors(DAY, {("SAIL", Instrument.FUT, EXPIRY, Decimal(0)): Decimal("1.00000000")})
    with pytest.raises(BookError, match="keyed on symbol"):
        futeq_delta([pos()], factors, {})


# -- SEBI Table 2, day by day -------------------------------------------------------------


EXPECTED = {
    #  date                      delta   baseline (yesterday's holdings at today's factors)
    dt.date(2026, 10, 12): (1000.0, None),
    dt.date(2026, 10, 13): (1000.0, 1000.0),
    dt.date(2026, 10, 14): (600.0, 1000.0),
    dt.date(2026, 10, 15): (250.0, 600.0),
    dt.date(2026, 10, 16): (1250.0, 250.0),
    dt.date(2026, 10, 19): (1250.0, 1250.0),
    dt.date(2026, 10, 21): (1450.0, 1450.0),
}


@pytest.mark.parametrize("day", sorted(EXPECTED))
def test_table_2_reproduces_day_by_day(books, deltas, day):
    """The oracle `check_ban_period_reduction()` will be written against."""
    expected_delta, expected_baseline = EXPECTED[day]
    assert futeq_delta(books[day], deltas[day], SYMBOL) == pytest.approx(expected_delta)

    earlier = [d for d in sorted(books) if d < day]
    if not earlier:
        assert expected_baseline is None
        return
    baseline = futeq_delta(books[earlier[-1]], deltas[day], SYMBOL)
    assert baseline == pytest.approx(expected_baseline)


def test_day_5_is_the_breach_and_the_others_are_not(books, deltas):
    """Applying the permitted band to every day: only Table 2's day 5 fails.

    permitted if  delta_today * baseline >= 0  and  |delta_today| <= |baseline|
    """
    verdicts = {}
    days = sorted(books)
    for previous, day in zip(days, days[1:]):
        today = futeq_delta(books[day], deltas[day], SYMBOL)
        baseline = futeq_delta(books[previous], deltas[day], SYMBOL)
        # No epsilon. The first version of this test carried `+ 1e-9`, which was papering over
        # float sums that could differ by about 1e-12 for identical holdings. With Decimal
        # factors the two come out exactly equal, so the band can be compared exactly - and
        # having to add an epsilon here again would mean the exactness had been lost.
        verdicts[day] = today * baseline >= 0 and abs(today) <= abs(baseline)

    assert verdicts[dt.date(2026, 10, 16)] is False          # day 5: a second futures lot
    assert all(v for d, v in verdicts.items() if d != dt.date(2026, 10, 16))


def test_a_zero_baseline_permits_only_zero():
    """"No Fresh Positions" is a consequence of the band, not a separate rule.

    With no position yesterday the baseline is 0, so |delta_today| <= 0 forces delta_today to
    0 - which is exactly the prohibition on opening a position in a banned scrip.
    """
    factors = DeltaFactors(DAY, {("SAIL", Instrument.FUT, EXPIRY, Decimal(0)): Decimal("1.00000000")})
    baseline = futeq_delta([], factors, SYMBOL)
    assert baseline == 0.0

    today = futeq_delta([pos(qty=1)], factors, SYMBOL)
    assert not (today * baseline >= 0 and abs(today) <= abs(baseline))


def test_the_passive_increase_on_day_7_is_entirely_passive(books, deltas):
    """The case Table 2's day 2 reaches for and cannot produce.

    Identical holdings on 19 and 21 Oct; the put's factor moves from -0.40 to -0.20 because the
    underlying rose. Delta goes up 200 shares with no trade, so the active part is exactly zero.
    """
    before, after = dt.date(2026, 10, 19), dt.date(2026, 10, 21)
    assert {p.contract: p.quantity_lots for p in books[before]} == {
        p.contract: p.quantity_lots for p in books[after]
    }

    yesterday_actual = futeq_delta(books[before], deltas[before], SYMBOL)
    baseline = futeq_delta(books[before], deltas[after], SYMBOL)
    today_actual = futeq_delta(books[after], deltas[after], SYMBOL)

    passive = baseline - yesterday_actual
    active = today_actual - baseline

    assert passive == pytest.approx(200.0)
    assert active == pytest.approx(0.0)
    assert today_actual > yesterday_actual          # and it is still permitted


# -- loading ------------------------------------------------------------------------------


def test_a_multi_day_file_loads_one_book_per_date(books):
    assert len(books) == 7
    assert sorted(books)[0] == dt.date(2026, 10, 12)
    assert all(b.trade_date == d for d, b in books.items())


def test_the_delta_file_reader_requires_one_date_per_file():
    """NSE publishes one file per day, so the faithful reader refuses a multi-day file."""
    with pytest.raises(BookError, match="more than one trade date"):
        load_delta_factors(FIXTURES / "table2_deltas.csv")


def test_a_missing_column_in_the_delta_file_is_refused(tmp_path):
    bad = tmp_path / "d.csv"
    bad.write_text("Date,Symbol,Expiry day\n30-10-2026,SAIL,29-10-2026\n", encoding="utf-8")
    with pytest.raises(BookError, match="missing column"):
        load_delta_factors(bad)


def test_a_missing_column_in_the_book_is_refused(tmp_path):
    bad = tmp_path / "b.csv"
    bad.write_text("trade_date,ucc,isin\n2026-10-12,UCC001,INE114A01011\n", encoding="utf-8")
    with pytest.raises(BookError, match="missing column"):
        load_book(bad)


def test_a_bad_row_names_its_line_number(tmp_path):
    bad = tmp_path / "b.csv"
    bad.write_text(
        "trade_date,ucc,isin,instrument,expiry,strike,lot_size,quantity_lots\n"
        "2026-10-12,UCC001,INE114A01011,CE,2026-10-29,0,1000,1\n",
        encoding="utf-8",
    )
    with pytest.raises(BookError, match="line 2"):
        load_book(bad)


# -- limitations, recorded rather than guaranteed -----------------------------------------


def test_table_2_day_2_does_not_reproduce(books, deltas):
    """A gap in the circular, not in this code.

    Table 2 day 2 says a long futures position shows a "passive increase in EoD delta by 5%"
    when the underlying appreciates 5%. In share terms it shows nothing: the factor is exactly
    1.0, the holding is unchanged, so the FutEq delta is identical. The provision is real and
    bites on options - day 7 above is the proof - but the futures illustration does not compute.

    This test exists so that if someone later "fixes" the fixture to make day 2 rise 5%, they
    have to come here and read why it does not.
    """
    day1, day2 = dt.date(2026, 10, 12), dt.date(2026, 10, 13)
    assert {p.contract: p.quantity_lots for p in books[day1]} == {
        p.contract: p.quantity_lots for p in books[day2]
    }
    assert futeq_delta(books[day1], deltas[day1], SYMBOL) == pytest.approx(
        futeq_delta(books[day2], deltas[day2], SYMBOL)
    )
    assert deltas[day1].factor("SAIL", Instrument.FUT, EXPIRY, None) == Decimal(1)
    assert deltas[day2].factor("SAIL", Instrument.FUT, EXPIRY, None) == Decimal(1)


def test_the_book_cannot_represent_an_index_position():
    """SPEC rows 8 and 9 need index positions and this model cannot hold one.

    The key is ISIN and indices have none. Recorded so the scope limit is visible in the test
    run rather than discovered when those rows are picked up.
    """
    with pytest.raises(BookError, match="SPEC rows 8 and 9"):
        pos(isin="NA")


# -- the fixes from the 7 Nov review -----------------------------------------------------


def test_a_row_with_a_missing_isin_is_refused_not_skipped(tmp_path):
    """The rule from `parsers.py`: skip what carries no information, refuse what carries
    information you cannot read.

    A row with three lots and no ISIN is a real position whose key is missing. The first
    version of these loaders skipped it, which understates that UCC's delta - and an
    understated delta hides a breach rather than inventing one, so it is the dangerous
    direction.
    """
    bad = tmp_path / "b.csv"
    bad.write_text(
        "trade_date,ucc,isin,instrument,expiry,strike,lot_size,quantity_lots\n"
        "2026-10-12,UCC01,,FF,2026-10-29,,500,3\n",
        encoding="utf-8",
    )
    with pytest.raises(BookError, match="ISIN"):
        load_book(bad)


def test_a_delta_row_with_a_missing_symbol_is_refused_not_skipped(tmp_path):
    bad = tmp_path / "d.csv"
    bad.write_text(
        "Date,Symbol,Expiry day,Strike Price,Option Type,Delta Factor\n"
        "30-10-2026,,29-10-2026,0,FF,1.00000000\n",
        encoding="utf-8",
    )
    with pytest.raises(BookError):
        load_delta_factors(bad)


def test_a_wholly_blank_row_is_skipped(tmp_path):
    """Trailing commas in a CSV carry nothing, so they are not an error."""
    good = tmp_path / "b.csv"
    good.write_text(
        "trade_date,ucc,isin,instrument,expiry,strike,lot_size,quantity_lots\n"
        "2026-10-12,UCC01,INE114A01011,FF,2026-10-29,0,1000,1\n"
        ",,,,,,,\n",
        encoding="utf-8",
    )
    assert len(load_book(good)) == 1


@pytest.mark.parametrize("written", ["0", "0.00", "0.0000", ""])
def test_a_futures_strike_is_none_however_nse_spells_zero(tmp_path, written):
    """`"0"` and `"0.00"` used to behave differently: the literal string was special-cased, so
    a futures row written `0.00` raised "a future has no strike"."""
    good = tmp_path / "b.csv"
    good.write_text(
        "trade_date,ucc,isin,instrument,expiry,strike,lot_size,quantity_lots\n"
        f"2026-10-12,UCC01,INE114A01011,FF,2026-10-29,{written},1000,1\n",
        encoding="utf-8",
    )
    assert load_book(good).positions[0].strike is None


def test_an_option_written_with_a_zero_strike_gets_the_accurate_complaint(tmp_path):
    """Not "an option needs a strike" - the strike is there and it is zero, which is how NSE
    writes a futures row, so the row is probably mis-parsed."""
    bad = tmp_path / "b.csv"
    bad.write_text(
        "trade_date,ucc,isin,instrument,expiry,strike,lot_size,quantity_lots\n"
        "2026-10-12,UCC01,INE114A01011,CE,2026-10-29,0,1000,1\n",
        encoding="utf-8",
    )
    with pytest.raises(BookError, match="how NSE writes a FUTURES row"):
        load_book(bad)


def test_load_books_checks_its_columns(tmp_path):
    """It did not, while `load_book()` did - so a missing column surfaced as a KeyError."""
    bad = tmp_path / "b.csv"
    bad.write_text("trade_date,ucc,isin\n2026-10-12,UCC01,INE114A01011\n", encoding="utf-8")
    with pytest.raises(BookError, match="missing column"):
        load_books(bad)


def test_load_book_refuses_a_multi_day_file():
    with pytest.raises(BookError, match="more than one trade date"):
        load_book(FIXTURES / "table2_positions.csv")


def test_a_float_delta_factor_is_refused_rather_than_converted():
    """Converting is the bug. `Decimal(0.35)` is 0.34999999999999997779..., so accepting a
    float would reintroduce the inexactness while looking as though it had been fixed."""
    with pytest.raises(BookError, match=re.escape("Decimal(float) carries")):
        DeltaFactors(DAY, {("SAIL", Instrument.FUT, EXPIRY, Decimal(0)): 1.0})


def test_identical_holdings_give_exactly_equal_deltas(books, deltas):
    """Why the factors are Decimal.

    19 and 21 Oct hold the same contracts. Valued at the SAME factors they must come out
    exactly equal - not approximately - because the ban-period band compares them with `<=`
    and a difference of 1e-12 reads as delta the entity never created.
    """
    a, b = dt.date(2026, 10, 19), dt.date(2026, 10, 21)
    assert futeq_delta(books[a], deltas[b], SYMBOL) == futeq_delta(books[b], deltas[b], SYMBOL)
    assert isinstance(futeq_delta(books[a], deltas[a], SYMBOL), Decimal)
