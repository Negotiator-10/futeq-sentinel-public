"""The expiry rule for the ban-period baseline, and the seven cases it has to get right.

**The rule, decided 7 Nov 2026.** When building the baseline for the ban-period check, a
contract whose expiry is *before* today's trade date contributes zero delta. A contract expiring
today, or later, is valued normally at today's NSE delta factor.

**Why.** Indian stock derivatives are physically settled, so at expiry an in-the-money position
stops being an F&O position and becomes a delivery obligation in the cash market, while an
out-of-the-money option expires worthless. Either way its F&O delta is gone the next day, which
is exactly why NSE publishes no factor for it. And the disappearance is *passive*: the holder did
not trade to make it happen, the calendar did. Para 5.3.2 only restrains changes the holder
causes, so an expiry belongs in the passive part of the day's change, which is never a breach.
Treating the contract as zero in the baseline puts it there.

The filtering happens where the baseline is built, not inside `DeltaFactors.factor()`. Refusing
a missing factor is correct everywhere else - it normally means a position in a contract NSE did
not price, which needs a person. Expiry is the one case where the absence is expected.

These tests apply the permitted band directly rather than calling
`check_ban_period_reduction()`, which is not written yet. They are the oracle it will be
written against, and they check the seven predicted outcomes before any code depends on them.

All positions are synthetic.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from sentinel.book import DeltaFactors, Instrument, Position, futeq_delta, live_on

ISIN = "INE114A01011"
SYMBOL = {ISIN: "SAIL"}
LOT = 1000

#: Real NSE expiry dates, read out of the bhavcopies rather than assumed. NSE's expiry is
#: **Tuesday**, not the last Thursday - SEBI moved it in 2025 - and it shifts EARLIER to the
#: Monday when that Tuesday is a holiday. October's monthly is Tue 27 Oct; November's is
#: Mon 23 Nov, because Tue 24 Nov is Guru Nanak Jayanti.
#:
#: A computed "last Tuesday" would be wrong twice in three months here - November and January
#: both moved - and the shift is earlier, which a calculation never guesses. That is the real
#: argument for reading the contract's own `expiry` field, and it is stronger than the one this
#: file first carried: the first version of these tests used 29 Oct and 26 Nov, neither of
#: which is an expiry date at all.
OCT = dt.date(2026, 10, 27)
NOV = dt.date(2026, 11, 23)

ONE = Decimal("1.00000000")


def fut(day: dt.date, expiry: dt.date, lots: int) -> Position:
    return Position(trade_date=day, ucc="UCC001", isin=ISIN, instrument=Instrument.FUT,
                    expiry=expiry, strike=None, lot_size=LOT, quantity_lots=lots)


def factors(day: dt.date, *expiries: dt.date) -> DeltaFactors:
    """Factors for the futures contracts NSE would publish on `day` - live ones only."""
    return DeltaFactors(day, {
        ("SAIL", Instrument.FUT, e, Decimal(0)): ONE for e in expiries if e >= day
    })


def verdict(yesterday_positions, today_positions, day: dt.date, *expiries: dt.date):
    """Apply the permitted band, returning (permitted, baseline, today).

    baseline = YESTERDAY's holdings, expired contracts dropped, at TODAY's factors.
    """
    today_factors = factors(day, *expiries)
    baseline = futeq_delta(live_on(yesterday_positions, day), today_factors, SYMBOL)
    today = futeq_delta(today_positions, today_factors, SYMBOL)
    permitted = today * baseline >= 0 and abs(today) <= abs(baseline)
    return permitted, baseline, today


# -- the seven cases ----------------------------------------------------------------------


def test_1_nothing_held_after_expiry_is_permitted_and_does_not_crash():
    """The case that crashed before the rule existed: a lookup for an expired contract."""
    yesterday = dt.date(2026, 10, 27)        # October's expiry day
    today = dt.date(2026, 10, 28)
    held = [fut(yesterday, OCT, 1)]

    permitted, baseline, now = verdict(held, [], today, OCT, NOV)
    assert baseline == 0
    assert now == 0
    assert permitted


def test_2_a_roll_on_expiry_day_is_permitted():
    """October is still live on its expiry day, so the baseline carries its delta.

    Closing October and opening the same size in November leaves today's delta equal to the
    baseline, so the band permits it. Rolling before or on expiry preserves delta.
    """
    yesterday = dt.date(2026, 10, 26)
    today = dt.date(2026, 10, 27)            # October's expiry day
    held = [fut(yesterday, OCT, 1)]
    rolled = [fut(today, NOV, 1)]

    permitted, baseline, now = verdict(held, rolled, today, OCT, NOV)
    assert baseline == Decimal(LOT)          # October valued normally on its expiry day
    assert now == Decimal(LOT)
    assert permitted


def test_3_a_roll_the_day_after_expiry_is_a_breach():
    """The asymmetry with case 2, and the consequence worth stating out loud.

    October expired yesterday, so the baseline is zero. Opening November today is a position
    created from nothing - and a banned scrip admits no fresh positions.
    """
    yesterday = dt.date(2026, 10, 27)
    today = dt.date(2026, 10, 28)
    held = [fut(yesterday, OCT, 1)]
    reopened = [fut(today, NOV, 1)]

    permitted, baseline, now = verdict(held, reopened, today, OCT, NOV)
    assert baseline == 0
    assert now == Decimal(LOT)
    assert not permitted


def test_4_an_unchanged_second_contract_survives_the_first_expiring():
    yesterday = dt.date(2026, 10, 27)
    today = dt.date(2026, 10, 28)
    held = [fut(yesterday, OCT, 1), fut(yesterday, NOV, 1)]
    kept = [fut(today, NOV, 1)]

    permitted, baseline, now = verdict(held, kept, today, OCT, NOV)
    assert baseline == Decimal(LOT)          # November only
    assert now == Decimal(LOT)
    assert permitted


def test_5_adding_to_the_surviving_contract_is_a_breach():
    yesterday = dt.date(2026, 10, 27)
    today = dt.date(2026, 10, 28)
    held = [fut(yesterday, OCT, 1), fut(yesterday, NOV, 1)]
    added = [fut(today, NOV, 2)]

    permitted, baseline, now = verdict(held, added, today, OCT, NOV)
    assert baseline == Decimal(LOT)
    assert now == Decimal(2 * LOT)
    assert not permitted


def test_6_a_short_reopened_after_expiry_is_a_breach():
    """The band is about delta moving away from zero in either direction, not about sign."""
    yesterday = dt.date(2026, 10, 27)
    today = dt.date(2026, 10, 28)
    held = [fut(yesterday, OCT, -1)]
    reopened = [fut(today, NOV, -1)]

    permitted, baseline, now = verdict(held, reopened, today, OCT, NOV)
    assert baseline == 0
    assert now == Decimal(-LOT)
    assert not permitted


def test_7_a_contract_expiring_today_is_valued_not_zeroed():
    today = OCT
    held = [fut(dt.date(2026, 10, 26), OCT, 1)]
    assert live_on(held, today) == tuple(held)
    assert futeq_delta(live_on(held, today), factors(today, OCT), SYMBOL) == Decimal(LOT)


# -- the property that makes the rule safe ------------------------------------------------


@pytest.mark.parametrize("holdings", [
    [(OCT, 1)],
    [(OCT, -1)],
    [(OCT, 1), (NOV, 1)],
    [(OCT, 1), (NOV, -2)],
    [(OCT, -3), (NOV, 1)],
])
def test_expiry_alone_can_never_cause_a_breach(holdings):
    """An expiry shrinks the baseline, which tightens the band - so it is worth proving that
    tightening cannot by itself fail.

    With no trading, today's holdings are yesterday's minus whatever expired. The baseline drops
    exactly the same contracts and values the survivors at the same factors, so today's delta
    equals the baseline exactly and the band permits it. A breach still requires the holder to
    add delta.

    This only holds because the baseline **zeroes** expired contracts. Valuing them at
    yesterday's factor instead would leave today short of the baseline on a long book and over
    it on a short one, and the expiry would read as the holder's doing.
    """
    yesterday = dt.date(2026, 10, 27)
    today = dt.date(2026, 10, 28)
    held = [fut(yesterday, e, q) for e, q in holdings]
    survivors = [fut(today, e, q) for e, q in holdings if e >= today]

    permitted, baseline, now = verdict(held, survivors, today, OCT, NOV)
    assert now == baseline
    assert permitted


def test_an_entirely_expired_book_permits_nothing_new():
    """Which is correct for a banned scrip: no fresh positions."""
    yesterday = dt.date(2026, 10, 27)
    today = dt.date(2026, 10, 28)
    held = [fut(yesterday, OCT, 5)]

    assert live_on(held, today) == ()
    permitted, baseline, now = verdict(held, [fut(today, NOV, 1)], today, OCT, NOV)
    assert baseline == 0 and not permitted


# -- the selection helper itself ----------------------------------------------------------


def test_live_on_is_strict_about_the_expiry_day():
    held = [fut(dt.date(2026, 10, 26), OCT, 1)]
    assert len(live_on(held, OCT)) == 1                        # live on its expiry day
    assert live_on(held, dt.date(2026, 10, 28)) == ()          # gone the next


def test_live_on_uses_the_contract_field_not_a_computed_last_thursday():
    """November's monthly expiry is Monday the 23rd, because Tuesday the 24th is Guru Nanak
    Jayanti and NSE moves the expiry earlier. A rule computing "last Tuesday" would land on the
    24th and be wrong; reading the contract's field cannot be."""
    held = [fut(dt.date(2026, 11, 19), NOV, 1)]
    assert NOV.weekday() == 0                 # Monday, moved earlier off the holiday
    assert len(live_on(held, dt.date(2026, 11, 23))) == 1
    assert live_on(held, dt.date(2026, 11, 25)) == ()


def test_a_weekend_needs_no_special_handling():
    """A contract expiring on a Friday is expired by the Monday comparison, with nothing in the
    rule mentioning weekends. The calendar decides which day is yesterday; the expiry field
    decides whether the contract still counts."""
    friday = dt.date(2026, 10, 30)
    monday = dt.date(2026, 11, 2)
    held = [fut(dt.date(2026, 10, 28), friday, 1)]
    assert len(live_on(held, friday)) == 1
    assert live_on(held, monday) == ()
