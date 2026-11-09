"""Tests for `check_ban_period_reduction()` - SPEC row 6, SEBI 2025/79 para 5.3.

Until 8 Nov the oracle tested the permitted band in isolation, because the function did not
exist. These call the function itself, so the oracle now checks the code rather than the
arithmetic beside it.

Grouped by what each defends:

* SEBI's own Table 2, plus the two days that show the passive increase Table 2 cannot;
* the reason strings, because a person reads them at 18:40 and the same event must always read
  the same way;
* the three holes found by running the first draft: a missing file passing as flat, a stale
  yesterday, and a chain through an unverified special session - all now refused;
* the per-UCC scope, including the counterexample that shows it is a scope decision rather than
  a dominance claim.

All positions are synthetic.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from sentinel.book import (
    BookError,
    DeltaFactors,
    Instrument,
    Position,
    PropBook,
    load_books,
    load_delta_factors_by_date,
)
from sentinel.calendar import DEFAULT_CALENDAR_PATH, ChainUnverifiedError, load_calendar
from sentinel.engine import ReductionCheck, check_ban_period_reduction
from sentinel.rules import load_rules
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "book"
ISIN = "INE114A01011"
SYMBOL = {ISIN: "SAIL"}
BANNED = frozenset({ISIN})
NOV = dt.date(2026, 11, 23)                 # a real monthly expiry: Monday, off the 24th
ONE = Decimal("1.00000000")


@pytest.fixture(scope="module")
def rules():
    return load_rules(warn=False)


@pytest.fixture(scope="module")
def calendar():
    return load_calendar()


@pytest.fixture(scope="module")
def books():
    return load_books(FIXTURES / "table2_positions.csv")


@pytest.fixture(scope="module")
def deltas():
    return load_delta_factors_by_date(FIXTURES / "table2_deltas.csv")


def fut(day, ucc, lots, isin=ISIN, expiry=NOV, tm="TMA"):
    return Position(trade_date=day, tm=tm, ucc=ucc, isin=isin, instrument=Instrument.FUT,
                    expiry=expiry, strike=None, lot_size=1000, quantity_lots=lots)


def fac(day, *expiries):
    return DeltaFactors(day, {("SAIL", Instrument.FUT, e, Decimal(0)): ONE
                              for e in expiries if e >= day})


def run(today, yesterday, f_today, f_yesterday, rules, calendar, banned=BANNED):
    return check_ban_period_reduction(today, yesterday, f_today, f_yesterday,
                                      SYMBOL, banned, calendar, rules)


MON, TUE = dt.date(2026, 11, 2), dt.date(2026, 11, 3)


# -- SEBI Table 2, through the function --------------------------------------------------


TABLE_2 = [
    # date                   permitted  reason
    (dt.date(2026, 10, 13), True,  "no net change from trading"),
    (dt.date(2026, 10, 14), True,  "reduced by 400"),
    (dt.date(2026, 10, 15), True,  "reduced by 350"),
    (dt.date(2026, 10, 16), False, "increased by 1000 from 250"),
    (dt.date(2026, 10, 19), True,  "no net change from trading"),
    (dt.date(2026, 10, 21), True,  "no net change from trading (passive move 200)"),
]


@pytest.mark.parametrize("day,permitted,reason", TABLE_2)
def test_table_2_through_the_function(books, deltas, rules, calendar, day, permitted, reason):
    """The verdicts come from the circular; the last day is the passive rise Table 2 cannot show."""
    previous = calendar.previous_trading_day(day)
    (check,) = run(books[day], books[previous], deltas[day], deltas[previous], rules, calendar)
    assert check.permitted is permitted
    assert check.reason == reason


def test_only_table_2_day_5_is_a_breach(books, deltas, rules, calendar):
    days = sorted(books)
    breaches = [
        day for previous, day in zip(days, days[1:])
        if not run(books[day], books[previous], deltas[day], deltas[previous],
                   rules, calendar)[0].permitted
    ]
    assert breaches == [dt.date(2026, 10, 16)]


def test_the_passive_day_splits_exactly(books, deltas, rules, calendar):
    """21 Oct: identical holdings, the put's factor moved. Passive 200, active exactly zero."""
    day, previous = dt.date(2026, 10, 21), dt.date(2026, 10, 19)
    (check,) = run(books[day], books[previous], deltas[day], deltas[previous], rules, calendar)
    assert check.passive == Decimal(200)
    assert check.active == 0
    assert check.today_delta > check.yesterday_delta and check.permitted


# -- reasons a person can read ------------------------------------------------------------


def test_a_fresh_long_and_a_fresh_short_read_the_same_way(rules, calendar):
    """The first draft called a fresh short "crossed zero: baseline 0" - same event, two labels,
    and nothing had crossed."""
    reasons = [
        run(PropBook([fut(TUE, "A", lots)]), PropBook.flat(MON), fac(TUE, NOV), fac(MON, NOV),
            rules, calendar)[0].reason
        for lots in (1, -1)
    ]
    assert reasons == ["fresh position of 1000 in a banned scrip",
                       "fresh position of -1000 in a banned scrip"]


def test_crossing_zero_is_labelled_as_crossing(rules, calendar):
    (c,) = run(PropBook([fut(TUE, "A", -1)]), PropBook([fut(MON, "A", 2)]),
               fac(TUE, NOV), fac(MON, NOV), rules, calendar)
    assert not c.permitted
    assert c.reason == "crossed zero: baseline 2000, today -1000"


def test_closing_out_completely_is_permitted_and_says_so(rules, calendar):
    """Zero is inclusive - 5.3.2 'reduced till 0'."""
    (c,) = run(PropBook.flat(TUE), PropBook([fut(MON, "A", 3)]),
               fac(TUE, NOV), fac(MON, NOV), rules, calendar)
    assert c.permitted
    assert c.reason == "closed out from 3000"


def test_a_same_day_roll_is_trading_that_nets_to_zero(rules, calendar):
    """Not "no change from trading", which reads as "did not trade". A roll is trading."""
    oct27 = dt.date(2026, 10, 27)
    (c,) = run(PropBook([fut(oct27, "A", 1)]), PropBook([fut(dt.date(2026, 10, 26), "A", 1, expiry=oct27)]),
               fac(oct27, oct27, NOV), fac(dt.date(2026, 10, 26), oct27, NOV), rules, calendar)
    assert c.permitted
    assert c.reason == "no net change from trading"


def test_reasons_carry_no_exponent_noise(books, deltas, rules, calendar):
    """Decimal prints a zero with eight places as 0E-8; the reasons normalise it."""
    for previous, day in zip(sorted(books), sorted(books)[1:]):
        (c,) = run(books[day], books[previous], deltas[day], deltas[previous], rules, calendar)
        assert "E-" not in c.reason and "E+" not in c.reason


# -- the three holes from the first draft, refused --------------------------------------


def test_a_missing_file_cannot_pass_as_flat(books):
    """The first draft took `PropBook | None`, and `books.get(day)` on a missing day returned
    None, which read as every holder having closed out - on the real day-5 breach it came back
    permitted. Books are non-optional now, so the natural lookup raises instead."""
    with pytest.raises(KeyError):
        books[dt.date(2026, 10, 17)]


def test_none_is_not_accepted_for_a_book(books, deltas, rules, calendar):
    with pytest.raises(AttributeError):
        run(None, books[dt.date(2026, 10, 15)], deltas[dt.date(2026, 10, 16)],
            deltas[dt.date(2026, 10, 15)], rules, calendar)


def test_a_stale_yesterday_is_refused(books, deltas, rules, calendar):
    """21 Oct against 14 Oct: score_bans.py's "next file on disk" bug, refused here."""
    with pytest.raises(BookError, match="previous trading day before 2026-10-21 is 2026-10-19"):
        run(books[dt.date(2026, 10, 21)], books[dt.date(2026, 10, 14)],
            deltas[dt.date(2026, 10, 21)], deltas[dt.date(2026, 10, 14)], rules, calendar)


def test_a_flat_yesterday_is_still_date_checked(rules, calendar):
    """The reason flat books carry a date: a flat stale yesterday is refused too."""
    with pytest.raises(BookError, match="previous trading day"):
        run(PropBook([fut(TUE, "A", 1)]), PropBook.flat(dt.date(2026, 10, 30)),
            fac(TUE, NOV), fac(dt.date(2026, 10, 30), NOV), rules, calendar)


def test_an_unverified_special_session_fails_closed(rules, tmp_path):
    """Monday 9 Nov's previous trading day runs through the special session; without the
    calendar's verdict row the run refuses rather than guessing."""
    stripped = tmp_path / "calendar_no_verdicts.csv"
    text = DEFAULT_CALENDAR_PATH.read_text(encoding="utf-8")
    stripped.write_text("".join(ln for ln in text.splitlines(keepends=True)
                                if not ln.startswith("chaining_")), encoding="utf-8")
    mon, fri = dt.date(2026, 11, 9), dt.date(2026, 11, 6)
    with pytest.raises(ChainUnverifiedError, match="special session"):
        run(PropBook([fut(mon, "A", 1)]), PropBook([fut(fri, "A", 1)]),
            fac(mon, NOV), fac(fri, NOV), rules, load_calendar(stripped))


def test_with_muhurat_verified_monday_needs_sundays_book(rules, calendar):
    """The consequence of #013 closing: Sunday chains, so Monday's yesterday is Sunday.

    Friday's book handed in on Monday is now a stale yesterday and is refused - before the
    verdict it was refused for a different reason (chain unverified). Sunday's book is accepted.
    """
    mon, sun, fri = dt.date(2026, 11, 9), dt.date(2026, 11, 8), dt.date(2026, 11, 6)
    with pytest.raises(BookError, match="previous trading day"):
        run(PropBook([fut(mon, "A", 1)]), PropBook([fut(fri, "A", 1)]),
            fac(mon, NOV), fac(fri, NOV), rules, calendar)
    (check,) = run(PropBook([fut(mon, "A", 1)]), PropBook([fut(sun, "A", 1)]),
                   fac(mon, NOV), fac(sun, NOV), rules, calendar)
    assert check.permitted and check.reason == "no net change from trading"


def test_factors_for_the_wrong_day_are_refused(rules, calendar):
    with pytest.raises(BookError, match="today's factors"):
        run(PropBook([fut(TUE, "A", 1)]), PropBook([fut(MON, "A", 1)]),
            fac(MON, NOV), fac(MON, NOV), rules, calendar)
    with pytest.raises(BookError, match="its factors"):
        run(PropBook([fut(TUE, "A", 1)]), PropBook([fut(MON, "A", 1)]),
            fac(TUE, NOV), fac(TUE, NOV), rules, calendar)


def test_swapped_books_are_refused(rules, calendar):
    """All eight parameters are positional, so a transposition has to be caught by the dates."""
    with pytest.raises(BookError):
        run(PropBook([fut(MON, "A", 1)]), PropBook([fut(TUE, "A", 1)]),
            fac(TUE, NOV), fac(MON, NOV), rules, calendar)


# -- scope: per UCC, per banned scrip ----------------------------------------------------


def test_the_same_ucc_at_two_brokers_is_checked_as_two_accounts(rules, calendar):
    """The collision the `tm` field exists for.

    Two different clients both carry the code C001 - one at broker TMA, one at TMB, because each
    broker numbers its own clients. The TMA client opens a fresh position in the banned scrip;
    the TMB client holds steady. Keyed on the UCC alone, the two would merge into one check:
    yesterday 2000, today 3000 - an "increase" belonging to nobody. Keyed on the account, the
    breach lands on the right client and the other is permitted.
    """
    checks = run(PropBook([fut(TUE, "C001", 1, tm="TMA"), fut(TUE, "C001", 2, tm="TMB")]),
                 PropBook([fut(MON, "C001", 2, tm="TMB")]),
                 fac(TUE, NOV), fac(MON, NOV), rules, calendar)
    by_account = {(c.tm, c.ucc): c for c in checks}
    assert set(by_account) == {("TMA", "C001"), ("TMB", "C001")}
    assert not by_account[("TMA", "C001")].permitted
    assert by_account[("TMA", "C001")].reason == "fresh position of 1000 in a banned scrip"
    assert by_account[("TMB", "C001")].permitted


def test_one_ucc_cannot_offset_another(rules, calendar):
    """UCC A opens +10 while B cuts -10 in the same scrip: A is flagged, B is permitted."""
    checks = run(PropBook([fut(TUE, "A", 10), fut(TUE, "B", 5)]),     # B: 15 -> 5 lots
                 PropBook([fut(MON, "B", 15)]),
                 fac(TUE, NOV), fac(MON, NOV), rules, calendar)
    by_ucc = {c.ucc: c for c in checks}
    assert not by_ucc["A"].permitted
    assert by_ucc["A"].reason == "fresh position of 10000 in a banned scrip"
    assert by_ucc["B"].permitted


def test_the_entity_counterexample_passes_per_ucc(rules, calendar):
    """Recorded rather than fixed: per-UCC and per-entity checks are incomparable.

    Each leg reduces, so both UCCs pass, while the entity's net goes 0 -> +3,000. An entity check
    belongs ALONGSIDE this one, not instead of it - docs/doubts.md entry 7. This test exists so
    that adding the entity check later is a deliberate change to a known result.
    """
    checks = run(PropBook([fut(TUE, "A", 5), fut(TUE, "B", -2)]),
                 PropBook([fut(MON, "A", 10), fut(MON, "B", -10)]),
                 fac(TUE, NOV), fac(MON, NOV), rules, calendar)
    assert all(c.permitted for c in checks)
    assert sum(c.today_delta for c in checks) == 3000
    assert sum(c.baseline for c in checks) == 0


def test_a_scrip_not_in_ban_produces_no_check(rules, calendar):
    other = "INE000OTHER01"
    checks = run(PropBook([fut(TUE, "A", 5, isin=other)]), PropBook([fut(MON, "A", 1, isin=other)]),
                 fac(TUE, NOV), fac(MON, NOV), rules, calendar)
    assert checks == ()


def test_every_check_is_returned_not_only_breaches(rules, calendar):
    """So "nothing checked" and "everything passed" stay distinguishable - the same reason
    reconcile() reports all 218 rows."""
    checks = run(PropBook([fut(TUE, "A", 1), fut(TUE, "B", 1)]),
                 PropBook([fut(MON, "A", 1), fut(MON, "B", 2)]),
                 fac(TUE, NOV), fac(MON, NOV), rules, calendar)
    assert len(checks) == 2 and all(isinstance(c, ReductionCheck) for c in checks)
    assert all(c.permitted for c in checks)


def test_a_ucc_present_only_yesterday_is_still_checked(rules, calendar):
    checks = run(PropBook([fut(TUE, "A", 1)]), PropBook([fut(MON, "A", 1), fut(MON, "B", 4)]),
                 fac(TUE, NOV), fac(MON, NOV), rules, calendar)
    assert {c.ucc for c in checks} == {"A", "B"}
    b = next(c for c in checks if c.ucc == "B")
    assert b.permitted and b.reason == "closed out from 4000"


def test_both_halves_of_the_band_come_from_config(rules, calendar):
    """Make the ceiling strict in config and an unchanged position becomes a breach - proving the
    `<=` is read from rules.yaml, not written in the function."""
    import dataclasses
    strict = dataclasses.replace(rules.describe("single_stock.ban.reduction_ceiling"), operator="<")
    patched = type(rules)({**{p: rules.describe(p) for p in rules},
                           "single_stock.ban.reduction_ceiling": strict},
                          rules.unverified, rules.meta, rules.path)
    args = (PropBook([fut(TUE, "A", 1)]), PropBook([fut(MON, "A", 1)]), fac(TUE, NOV), fac(MON, NOV))
    assert run(*args, rules, calendar)[0].permitted
    assert not run(*args, patched, calendar)[0].permitted
