"""Row 7's result types: the invariants they hold, so the check cannot report something impossible.

`check_entity_limit()` itself is Chintamani's (#016); its tests will go beside these. These pin
the plumbing it returns into: a cause exactly on a breach, an excess that is exactly G minus the
limit, no limit outside the config, and no (holder, scrip, limit) reported twice - the double
count a trading member's own limit and its 20% would make.

Written by Claude, as plumbing, 12 Nov 2026.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from sentinel.book import BookError, NoPriorDay
from sentinel.engine import (
    ENTITY_LIMIT_KEYS, EntityLimitCheck, EntityLimitResult, LimitCause, NotChecked,
)
from sentinel.entities import TM_COMBINED_LIMIT_KEY, Category

DAY = dt.date(2026, 10, 13)
ISIN = "INE000H01027"
CLIENT = Category.CLIENT_NRI.limit_key
TM20 = Category.TM_PROPRIETARY.limit_key


def check(**overrides) -> EntityLimitCheck:
    """A permitted client check: G 80,000 against a 10% limit on an MWPL of 1,000,000."""
    kw = dict(trade_date=DAY, holder_id="H001", isin=ISIN, limit_key=CLIENT,
              accounts=(("TMA", "C001"),), gross_futeq=Decimal("80000"), mwpl=1_000_000,
              limit_shares=Decimal("100000"), excess_shares=Decimal("0"), permitted=True,
              cause=None, reason="inside the 10% limit")
    kw.update(overrides)
    return EntityLimitCheck(**kw)


def breach(**overrides) -> EntityLimitCheck:
    """The same holder at G 120,000: 20,000 shares over."""
    kw = dict(gross_futeq=Decimal("120000"), excess_shares=Decimal("20000"), permitted=False,
              cause=LimitCause.ACTIVE, reason="over the 10% limit")
    kw.update(overrides)
    return check(**kw)


# -- the limits ---------------------------------------------------------------------------


def test_every_category_and_the_tm_combined_limit_are_valid_keys():
    assert ENTITY_LIMIT_KEYS == {c.limit_key for c in Category} | {TM_COMBINED_LIMIT_KEY}
    assert len(ENTITY_LIMIT_KEYS) == 7


def test_a_limit_outside_the_config_is_refused():
    with pytest.raises(ValueError, match="not an entity limit"):
        check(limit_key="single_stock.entity_limits.fpi_cat_2")     # the FAQ's single Cat II


# -- a check ------------------------------------------------------------------------------


def test_a_pass_and_a_breach_are_both_valid():
    assert check().permitted and check().cause is None
    b = breach()
    assert not b.permitted and b.cause is LimitCause.ACTIVE and b.excess_shares == 20_000


@pytest.mark.parametrize("overrides,match", [
    ({"cause": LimitCause.PASSIVE}, "cause is set exactly"),                       # pass with a cause
    ({"excess_shares": Decimal("1")}, "permitted, but excess"),                    # pass with excess
    ({"gross_futeq": Decimal("-1")}, "cannot be negative"),
    ({"mwpl": 0}, "MWPL is 0"),
    ({"accounts": ()}, "no accounts"),
    ({"reason": "  "}, "no reason"),
    ({"gross_futeq": 80000.0}, "must be a Decimal"),                               # a float slips in
])
def test_an_impossible_pass_is_refused(overrides, match):
    with pytest.raises((ValueError, TypeError), match=match):
        check(**overrides)


@pytest.mark.parametrize("overrides,match", [
    ({"cause": None}, "cause is set exactly"),                                      # breach, no cause
    ({"excess_shares": Decimal("19999")}, "not G - limit"),                         # the penalty base, wrong
    ({"excess_shares": Decimal("0"), "gross_futeq": Decimal("100000")}, "breached, but excess"),
])
def test_an_impossible_breach_is_refused(overrides, match):
    with pytest.raises(ValueError, match=match):
        breach(**overrides)


def test_unknown_is_a_valid_cause_for_a_breach_with_no_yesterday():
    assert breach(cause=LimitCause.UNKNOWN).cause is LimitCause.UNKNOWN


# -- not checked, and the result ----------------------------------------------------------


def test_not_checked_needs_a_reason_and_a_real_limit():
    nc = NotChecked(DAY, "H001", ISIN, CLIENT, "no MWPL for this scrip today")
    assert nc.key == ("H001", ISIN, CLIENT)
    with pytest.raises(ValueError, match="no reason"):
        NotChecked(DAY, "H001", ISIN, CLIENT, "")
    with pytest.raises(ValueError, match="not an entity limit"):
        NotChecked(DAY, "H001", ISIN, "single_stock.ban.entry_utilisation", "x")


def test_the_result_holds_checks_and_not_checked_and_lists_breaches():
    ok = check(holder_id="H001")
    bad = breach(holder_id="H002", accounts=(("TMA", "C002"),))
    nc = NotChecked(DAY, "H003", "INE000Q01016", CLIENT, "no MWPL for this scrip today")
    result = EntityLimitResult((ok, bad), (nc,))
    assert result.breaches == (bad,)
    assert result.not_checked == (nc,)


def test_a_trading_members_own_limit_reported_twice_is_refused():
    """The double count: TMA's own-limit check and its 20% check are the same check."""
    own = check(holder_id="TMA", limit_key=TM20, accounts=(("TMA", "PRO"),))
    as_tm = check(holder_id="TMA", limit_key=TM20, accounts=(("TMA", "PRO"),),
                  reason="its proprietary book against 20%")
    with pytest.raises(ValueError, match="should skip trading members"):
        EntityLimitResult((own, as_tm))


def test_a_check_and_a_not_checked_for_the_same_thing_is_refused():
    with pytest.raises(ValueError, match="appears twice"):
        EntityLimitResult((check(),), (NotChecked(DAY, "H001", ISIN, CLIENT, "no MWPL"),))


def test_a_tms_twenty_and_thirty_on_the_same_scrip_are_two_checks():
    twenty = check(holder_id="TMA", limit_key=TM20, accounts=(("TMA", "PRO"),))
    thirty = check(holder_id="TMA", limit_key=TM_COMBINED_LIMIT_KEY, accounts=(("TMA", "PRO"),))
    assert len(EntityLimitResult((twenty, thirty)).checks) == 2


def test_one_day_at_a_time():
    other = check(holder_id="H009", trade_date=DAY + dt.timedelta(days=1))
    with pytest.raises(ValueError, match="one day at a time"):
        EntityLimitResult((check(), other))


def test_lists_are_refused_so_the_result_stays_frozen():
    with pytest.raises(TypeError, match="must be tuples"):
        EntityLimitResult([check()])


# -- NoPriorDay ---------------------------------------------------------------------------


def test_no_prior_day_must_say_why():
    npd = NoPriorDay(DAY, "first run: no book before 13 Oct 2026")
    assert npd.trade_date == DAY
    with pytest.raises(BookError, match="no reason"):
        NoPriorDay(DAY, " ")
