"""Row 7: check_entity_limit() against the entity limits in config/rules.yaml (#016 and addendum).

The tests are Chintamani's. The setup below is plumbing (Claude, 12 Nov 2026): one synthetic
reference snapshot, one-stock books and the factors to value them, and a `run()` that fills in
everything the check needs except the two books.

The world, all effective from 1 Jan 2026 and looked up on D1 (Tue 13 Oct 2026):

    holder   category                               accounts
    H1       client_nri                             TMA/C1, TMB/C2    (one client, two brokers)
    TMA      tm_proprietary (a trading member)      TMA/PRO
    TMB      tm_proprietary (a trading member)      TMB/PRO
    FPI1     fpi_cat_1                              TMA/F1            (FPI under TMA: not in its 30%)
    CORP     fpi_cat_2_individual_family_corporate  TMA/K1            (Cat II corporate: 10%)

Two stocks, X (XCO) and Y (YCO): one futures contract each expiring 27 Oct 2026, delta factor 1,
lot size 1, so a position of n lots is n shares of FutEq and G is easy to read off. MWPL defaults
to 1,000,000 for both, so 10% is 100,000 shares, 20% is 200,000 and 30% is 300,000.

Every value is synthetic; the ISINs use the INE000 block that no real issuer has.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from sentinel.book import BookError, DeltaFactors, Instrument, NoPriorDay, Position, PropBook
from sentinel.calendar import load_calendar
from sentinel.engine import EntityLimitCheck, EntityLimitResult, LimitCause, check_entity_limit
from sentinel.entities import (
    TM_COMBINED_LIMIT_KEY, Account, Category, Holder, ReferenceData, ReferenceDataError, Snapshot,
)
from sentinel.rules import load_rules

# -- the days -----------------------------------------------------------------------------

D0 = dt.date(2026, 10, 12)      # Mon: yesterday
D1 = dt.date(2026, 10, 13)      # Tue: today
EXPIRY = dt.date(2026, 10, 27)
EFFECTIVE = dt.date(2026, 1, 1)

# -- the stocks ---------------------------------------------------------------------------

X, Y = "INE000X01010", "INE000Y01018"
SYMBOL = {X: "XCO", Y: "YCO"}
MWPL = 1_000_000

# -- the limit keys, for asserting which check came back ----------------------------------

CLIENT = Category.CLIENT_NRI.limit_key
TM20 = Category.TM_PROPRIETARY.limit_key
TM30 = TM_COMBINED_LIMIT_KEY
FPI_I = Category.FPI_CAT_I.limit_key
CAT2_CORP = Category.FPI_CAT_II_IFC.limit_key

# -- the accounts, as (tm, ucc), so a book row reads as who holds it ----------------------

H1_AT_TMA = ("TMA", "C1")       # the two-account client
H1_AT_TMB = ("TMB", "C2")
TMA_PRO = ("TMA", "PRO")        # a trading member's own book
TMB_PRO = ("TMB", "PRO")
FPI_AT_TMA = ("TMA", "F1")      # an FPI account under TMA
CORP_AT_TMA = ("TMA", "K1")     # the Cat II corporate

RULES = load_rules(warn=False)
CALENDAR = load_calendar()


def reference(day: dt.date = D1) -> Snapshot:
    """The five holders and six accounts above, as they stand on `day`."""
    holders = [
        Holder("H1", Category.CLIENT_NRI, EFFECTIVE),
        Holder("TMA", Category.TM_PROPRIETARY, EFFECTIVE),
        Holder("TMB", Category.TM_PROPRIETARY, EFFECTIVE),
        Holder("FPI1", Category.FPI_CAT_I, EFFECTIVE),
        Holder("CORP", Category.FPI_CAT_II_IFC, EFFECTIVE),
    ]
    accounts = [
        Account(*H1_AT_TMA, "H1", False, EFFECTIVE),
        Account(*H1_AT_TMB, "H1", False, EFFECTIVE),
        Account(*TMA_PRO, "TMA", True, EFFECTIVE),
        Account(*TMB_PRO, "TMB", True, EFFECTIVE),
        Account(*FPI_AT_TMA, "FPI1", False, EFFECTIVE),
        Account(*CORP_AT_TMA, "CORP", False, EFFECTIVE),
    ]
    return ReferenceData(holders, accounts).as_of(day)


REFERENCE = reference()


def factors(day: dt.date, x: Decimal | int | str = 1, y: Decimal | int | str = 1) -> DeltaFactors:
    """The futures delta factor for each stock on `day`; 1 unless a test moves it. A string
    such as "1.2" is exact, as NSE publishes it; a float is refused by DeltaFactors."""
    return DeltaFactors(day, {
        ("XCO", Instrument.FUT, EXPIRY, Decimal(0)): Decimal(x),
        ("YCO", Instrument.FUT, EXPIRY, Decimal(0)): Decimal(y),
    })


def book(day: dt.date, *rows: tuple[tuple[str, str], str, int],
         expiry: dt.date = EXPIRY) -> PropBook:
    """A futures book on `day`. Each row is (account, isin, shares), lot size 1, so shares are
    lots and, at factor 1, FutEq. Negative is short. No rows gives a flat book. Every row
    shares one `expiry`, 27 Oct unless given.

        book(D1, (H1_AT_TMA, X, 60_000), (H1_AT_TMB, X, -50_000))
    """
    if not rows:
        return PropBook.flat(day)
    return PropBook(
        Position(day, tm, ucc, isin, Instrument.FUT, expiry, None, 1, shares)
        for (tm, ucc), isin, shares in rows
    )


def one_stock(account: tuple[str, str], shares: int, day: dt.date = D1, isin: str = X,
              expiry: dt.date = EXPIRY) -> PropBook:
    """The one-stock book: one account, one futures position. `expiry` defaults to 27 Oct;
    set it to D0 for a contract that expired yesterday, which today's factors do not price."""
    return book(day, (account, isin, shares), expiry=expiry)


def no_prior_day(day: dt.date = D1) -> NoPriorDay:
    return NoPriorDay(day, "first run: no book before this day")


def run(today: PropBook, yesterday: PropBook | NoPriorDay | None = None, *,
        mwpl: dict[str, int] | None = None, mwpl_yesterday: dict[str, int] | None = None,
        factors_today: DeltaFactors | None = None, ref: Snapshot | None = None,
        ) -> EntityLimitResult:
    """check_entity_limit() with the defaults above. Yesterday defaults to NoPriorDay for
    today's date; MWPL to 1,000,000 for both stocks; factors to 1 on today's date."""
    day = today.trade_date
    return check_entity_limit(
        today,
        no_prior_day(day) if yesterday is None else yesterday,
        factors(day) if factors_today is None else factors_today,
        REFERENCE if ref is None else ref,
        {X: MWPL, Y: MWPL} if mwpl is None else mwpl,
        mwpl_yesterday,
        SYMBOL,
        CALENDAR,
        RULES,
    )


def get(result: EntityLimitResult, holder_id: str, limit_key: str, isin: str = X) -> EntityLimitCheck:
    """The one check for (holder, limit, scrip); fails loudly if it is missing."""
    found = [c for c in result.checks
             if (c.holder_id, c.limit_key, c.isin) == (holder_id, limit_key, isin)]
    assert found, (f"no check for {holder_id} / {limit_key.rsplit('.', 1)[1]} / {isin}; got "
                   f"{sorted((c.holder_id, c.limit_key.rsplit('.', 1)[1]) for c in result.checks)}")
    return found[0]


# -- the setup itself (plumbing, so the tests below stand on something checked) -----------


def test_the_setup_is_what_the_docstring_says():
    assert CALENDAR.previous_trading_day(D1) == D0
    assert REFERENCE.day == D1
    assert REFERENCE.account(*H1_AT_TMB).holder_id == "H1"
    assert REFERENCE.holder("CORP").category is Category.FPI_CAT_II_IFC
    assert RULES.value(CLIENT) == pytest.approx(0.10)
    assert RULES.value(TM20) == pytest.approx(0.20)
    assert RULES.value(TM30) == pytest.approx(0.30)
    assert len(list(one_stock(TMA_PRO, 5))) == 1
    assert list(book(D1)) == []


# -- Chintamani's tests start here --------------------------------------------------------


# MWPL is 1,000,000: 10% = 100,000 shares, 20% = 200,000, 30% = 300,000.


# ---------------------------------------------------------------- the limit itself

def test_exactly_at_the_limit_is_permitted():
    check = get(run(one_stock(H1_AT_TMA, 100_000)), "H1", CLIENT)
    assert check.permitted
    assert check.cause is None
    assert check.excess_shares == 0


def test_one_share_over_is_a_breach_with_excess_of_exactly_one():
    check = get(run(one_stock(H1_AT_TMA, 100_001)), "H1", CLIENT)
    assert not check.permitted
    assert check.limit_shares == 100_000
    assert check.excess_shares == 1


def test_a_long_and_a_short_account_of_one_holder_add():
    today = book(D1, (H1_AT_TMA, X, 60_000), (H1_AT_TMB, X, -50_000))
    check = get(run(today), "H1", CLIENT)
    assert check.gross_futeq == 110_000          # not 10,000: no netting across accounts
    assert check.excess_shares == 10_000


# ---------------------------------------------------------------- who is checked

def test_a_tm_gets_two_checks_and_none_as_a_holder():
    result = run(one_stock(TMA_PRO, 250_000))
    tma = [c for c in result.checks if c.holder_id == "TMA"]
    assert sorted(c.limit_key for c in tma) == sorted([TM20, TM30])
    assert not get(result, "TMA", TM20).permitted    # 250,000 > 20%
    assert get(result, "TMA", TM30).permitted        # 250,000 <= 30%


def test_an_fpi_account_is_excluded_from_its_tms_thirty_percent():
    today = book(D1, (TMA_PRO, X, 100_000), (FPI_AT_TMA, X, 250_000))
    result = run(today)
    assert get(result, "TMA", TM30).gross_futeq == 100_000   # not 350,000
    assert get(result, "FPI1", FPI_I).gross_futeq == 250_000  # ASSUME: holder id "FPI1"


def test_a_cat_ii_corporate_gets_ten_percent():
    check = get(run(one_stock(CORP_AT_TMA, 150_000)), "CORP", CAT2_CORP)
    assert check.limit_shares == 100_000         # NSE FAQ 15 would give 200,000
    assert not check.permitted


def test_a_flat_day_gives_no_checks():
    assert run(book(D1)).checks == ()


# ---------------------------------------------------------------- the cause

def test_holdings_that_grew_are_active():
    result = run(one_stock(H1_AT_TMA, 120_000),
                 one_stock(H1_AT_TMA, 100_000, day=D0))
    assert get(result, "H1", CLIENT).cause is LimitCause.ACTIVE


def test_an_mwpl_cut_with_holdings_unchanged_is_passive():
    result = run(one_stock(H1_AT_TMA, 90_000),
                 one_stock(H1_AT_TMA, 90_000, day=D0),
                 mwpl={X: 800_000}, mwpl_yesterday={X: 1_000_000})
    check = get(result, "H1", CLIENT)
    assert check.cause is LimitCause.PASSIVE
    assert "MWPL cut" in check.reason


def test_the_reason_tells_rose_and_unchanged_apart():
    today = one_stock(H1_AT_TMA, 150_000)
    yesterday = one_stock(H1_AT_TMA, 150_000, day=D0)
    rose = get(run(today, yesterday, mwpl_yesterday={X: 900_000}), "H1", CLIENT)
    same = get(run(today, yesterday, mwpl_yesterday={X: 1_000_000}), "H1", CLIENT)
    assert "MWPL rose" in rose.reason
    assert "MWPL unchanged" in same.reason


def test_no_prior_day_gives_an_unknown_cause():
    check = get(run(one_stock(H1_AT_TMA, 120_000)), "H1", CLIENT)
    assert check.cause is LimitCause.UNKNOWN


def test_a_sign_flip_over_the_limit_is_passive():
    result = run(one_stock(H1_AT_TMA, -120_000),
                 one_stock(H1_AT_TMA, 120_000, day=D0))
    assert get(result, "H1", CLIENT).cause is LimitCause.PASSIVE


def test_the_baseline_is_valued_at_todays_factors():
    # Same holdings both days; only the factor moved. At today's factor the
    # baseline equals today's G, so the breach is PASSIVE. At yesterday's
    # factor it would look like the holder added, and read ACTIVE.
    result = run(one_stock(H1_AT_TMA, 100_000),
                 one_stock(H1_AT_TMA, 100_000, day=D0),
                 factors_today=factors(D1, x="1.2"))         # ASSUME: accepts "1.2"
    check = get(result, "H1", CLIENT)
    assert check.gross_futeq == 120_000
    assert check.cause is LimitCause.PASSIVE


def test_an_expired_holding_is_not_in_the_baseline():
    # Yesterday's contract expired on D0; today's is a new one. The baseline
    # is zero, so the breach is ACTIVE.
    result = run(one_stock(H1_AT_TMA, 120_000),
                 one_stock(H1_AT_TMA, 120_000, day=D0, expiry=D0))   # ASSUME: expiry=
    assert get(result, "H1", CLIENT).cause is LimitCause.ACTIVE


# ---------------------------------------------------------------- refusals

def test_a_scrip_with_no_mwpl_is_not_checked_and_others_still_are():
    today = book(D1, (H1_AT_TMA, X, 50_000), (H1_AT_TMA, Y, 50_000))
    result = run(today, mwpl={X: MWPL})
    # Two, not three: H1's own check and TMA's 30%. TMA's 20% covers
    # proprietary accounts only, and they hold nothing in Y.
    assert sorted((n.holder_id, n.limit_key) for n in result.not_checked) == \
        sorted([("H1", CLIENT), ("TMA", TM30)])
    assert all(n.isin == Y for n in result.not_checked)
    assert get(result, "H1", CLIENT, isin=X).permitted


def test_an_unknown_account_refuses_the_stage():
    with pytest.raises(ReferenceDataError):
        run(one_stock(("TMA", "GHOST"), 1))                  # ASSUME: accounts are (tm, ucc)


def test_a_stale_yesterday_is_refused():
    friday = dt.date(2026, 10, 9)
    with pytest.raises(BookError):
        run(one_stock(H1_AT_TMA, 1), one_stock(H1_AT_TMA, 1, day=friday))


def test_a_no_prior_day_for_another_date_is_refused():
    with pytest.raises(BookError):
        run(one_stock(H1_AT_TMA, 1), no_prior_day(D0))


def test_a_reference_snapshot_for_another_day_is_refused():
    with pytest.raises(BookError):
        run(one_stock(H1_AT_TMA, 1), ref=reference(D0))
