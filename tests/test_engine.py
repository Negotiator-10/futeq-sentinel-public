"""Tests for `sentinel.engine`.

Grouped by what each one defends:

* **the arithmetic** - that utilisation and headroom are the formulas the circulars state,
  on numbers taken from real NSE rows rather than invented ones;
* **the boundaries** - that 95% and 80% keep their opposite inclusivity, and that neither
  direction is written in Python;
* **what reconcile() refuses** - the inputs it will not silently accept;
* **the holes** - two tests that document a limitation rather than a guarantee, so the
  limitation fails loudly if the representation ever changes.

The real-number fixtures below are from `combineoi_30102026`, recorded in `DECISIONS.md`
#011 and in the comment block at the top of `engine.py`. They are kept as literals here
rather than read from `data/` because `data/` is gitignored and CI has no copy of it.
"""

from __future__ import annotations

import datetime as dt
import warnings

import pandas as pd
import pytest

from sentinel.engine import (
    BarredCheck,
    Reconciliation,
    Residual,
    headroom_shares,
    reconcile,
    utilisation,
)
from sentinel.parsers import MwplRow
from sentinel.rules import load_rules

TRADE_DATE = dt.date(2026, 10, 30)


@pytest.fixture(scope="module")
def rules():
    return load_rules(warn=False)


def make_row(
    symbol: str = "TESTCO",
    *,
    mwpl: int = 1_000_000,
    notional_oi: int = 500_000,
    futeq_oi: float = 400_000.0,
    no_fresh_positions: bool = False,
    headroom_shares: int | None = 550_000,
    trade_date: dt.date = TRADE_DATE,
    isin: str | None = None,
) -> MwplRow:
    """An MwplRow with every field defaulted, so each test names only what it is about."""
    return MwplRow(
        trade_date=trade_date,
        isin=isin or f"INE000{abs(hash(symbol)) % 10000:04d}01",
        scrip_name=symbol.title(),
        symbol=symbol,
        mwpl=mwpl,
        notional_oi=notional_oi,
        futeq_oi=futeq_oi,
        no_fresh_positions=no_fresh_positions,
        headroom_shares=headroom_shares,
    )


# -- the arithmetic -----------------------------------------------------------------------


def test_utilisation_is_a_fraction_not_a_percentage():
    # 0.8493, not 84.93. The whole point is that it can go straight into Threshold.compare()
    # without a scaling step that someone applies on one side of a comparison and not the other.
    assert utilisation(500_000.0, 1_000_000) == 0.5


def test_utilisation_matches_the_real_sail_row():
    # SAIL on 30 Oct: the row that proved ban status is a state, not a measurement.
    u = utilisation(REDACTED, REDACTED)
    assert round(u, 4) == 0.8493


def test_utilisation_matches_the_real_bandhanbnk_row():
    # Higher utilisation than SAIL on the same day, and NOT barred. Kept beside the SAIL
    # test because the pair is the evidence for the three-argument is_in_ban() in #011.
    u = utilisation(REDACTED, REDACTED)
    assert round(u, 4) == 0.8598
    assert u > utilisation(REDACTED, REDACTED)


def test_headroom_is_the_published_formula_on_the_real_360one_row(rules):
    # 360ONE on 30 Oct. NSE published REDACTED; the exact figure is REDACTED.2195.
    row = make_row("360ONE", mwpl=REDACTED, futeq_oi=REDACTED, headroom_shares=REDACTED)
    assert round(headroom_shares(row, rules), 4) == REDACTED.2195


def test_headroom_is_not_truncated(rules):
    # Truncating to match NSE would drive every residual to zero and destroy the one thing
    # reconcile() measures. The fractional part IS the measurement.
    row = make_row("360ONE", mwpl=REDACTED, futeq_oi=REDACTED, headroom_shares=REDACTED)
    got = headroom_shares(row, rules)
    assert got != int(got)


def test_headroom_multiplies_rather_than_dividing(rules):
    # NSE's published column is 0.95 * MWPL - FutEq OI. Matching that arithmetic shape keeps a
    # floating-point difference out of the residual. This asserts the shape, not just the value.
    row = make_row(mwpl=REDACTED, futeq_oi=REDACTED)
    entry = rules.value("single_stock.ban.entry_utilisation")
    assert headroom_shares(row, rules) == entry * row.mwpl - row.futeq_oi


def test_headroom_reads_the_threshold_from_the_config_not_a_literal(rules):
    # If 0.95 were typed into engine.py, this would still pass against the real config - so the
    # test moves the config instead and checks the function followed it.
    import dataclasses

    row = make_row(mwpl=1_000_000, futeq_oi=0.0)
    assert headroom_shares(row, rules) == 950_000.0

    moved = dataclasses.replace(
        rules.describe("single_stock.ban.entry_utilisation"), value=0.90
    )
    patched = type(rules)(
        {**{p: rules.describe(p) for p in rules}, "single_stock.ban.entry_utilisation": moved},
        rules.unverified,
        rules.meta,
        rules.path,
    )
    assert headroom_shares(row, patched) == 900_000.0


def test_headroom_is_exactly_zero_at_the_entry_boundary(rules):
    # Entry is "exceeds 95%", so a scrip sitting exactly on 95% is NOT barred and its headroom
    # is exactly 0. MwplRow allows a zero headroom for this reason; `<= 0` there would be wrong.
    row = make_row(mwpl=1_000_000, futeq_oi=950_000.0, headroom_shares=0)
    assert headroom_shares(row, rules) == 0.0


# -- the boundaries, in opposite directions -----------------------------------------------


def test_exactly_95_percent_is_not_a_ban(rules):
    # SEBI 2025/79 para 5.2.6: "exceeds". Strict.
    assert rules.compare("single_stock.ban.entry_utilisation", utilisation(950_000.0, 1_000_000)) is False


def test_a_hair_over_95_percent_is_a_ban(rules):
    assert rules.compare("single_stock.ban.entry_utilisation", utilisation(950_001.0, 1_000_000)) is True


def test_exactly_80_percent_is_a_release(rules):
    # Master Circular 30 Dec 2024, cl 3.3.2.1.2.3: "80% or below". Inclusive - the opposite
    # inclusivity to entry, which is why neither is written as a comparison in engine.py.
    assert rules.compare("single_stock.ban.exit_utilisation", utilisation(800_000.0, 1_000_000)) is True


def test_a_barred_scrip_at_exactly_80_percent_is_released_not_held(rules):
    # The row that distinguishes `not rules.compare(...)` from `u > 0.80`: they agree on every
    # other input and this is the one where the config's operator has to be the authority.
    row = make_row("ONTHELINE", mwpl=1_000_000, futeq_oi=800_000.0,
                   no_fresh_positions=True, headroom_shares=None)
    other = make_row("NORMAL", mwpl=1_000_000, futeq_oi=400_000.0, headroom_shares=550_000)
    rec = reconcile((row, other), rules)

    assert rec.barred[0].held is False
    assert not rec.ok
    assert "at or below the 80% exit" in rec.failures[0]


# -- reconcile on good data ---------------------------------------------------------------


def test_reconcile_agrees_on_a_truncated_row(rules):
    # NSE truncates down, so its figure is at or below ours and the residual lands in [0, 1).
    row = make_row("360ONE", mwpl=REDACTED, futeq_oi=REDACTED, headroom_shares=REDACTED)
    rec = reconcile((row,), rules)

    assert rec.ok
    assert rec.rows_total == 1
    assert len(rec.residuals) == 1
    assert 0 <= rec.residuals[0].residual < 1


def test_reconcile_splits_barred_rows_from_comparable_ones(rules):
    rows = (
        make_row("A", headroom_shares=550_000),
        make_row("KAYNES", mwpl=REDACTED, futeq_oi=REDACTED,
                 no_fresh_positions=True, headroom_shares=None),
        make_row("B", headroom_shares=550_000),
        make_row("SAIL", mwpl=REDACTED, futeq_oi=REDACTED,
                 no_fresh_positions=True, headroom_shares=None),
    )
    rec = reconcile(rows, rules)

    assert rec.rows_total == 4
    assert rec.rows_total == len(rec.residuals) + len(rec.barred)
    assert [b.symbol for b in rec.barred] == ["KAYNES", "SAIL"]
    assert all(b.held for b in rec.barred)
    assert rec.ok


def test_both_real_barred_rows_are_held_by_the_exit_threshold_not_the_entry_one(rules):
    # KAYNES 92.17% and SAIL 84.93% on 30 Oct. Both barred, NEITHER above 95%. An
    # entry-threshold check here would fail on both, which is the SAIL finding in one test.
    rows = (
        make_row("KAYNES", mwpl=REDACTED, futeq_oi=REDACTED,
                 no_fresh_positions=True, headroom_shares=None),
        make_row("SAIL", mwpl=REDACTED, futeq_oi=REDACTED,
                 no_fresh_positions=True, headroom_shares=None),
        make_row("ACOMPARABLEROW", headroom_shares=550_000),
    )
    rec = reconcile(rows, rules)

    assert all(b.held for b in rec.barred)
    for b in rec.barred:
        assert not rules.compare("single_stock.ban.entry_utilisation", b.utilisation)


def test_min_and_max_residual_pick_the_extremes_by_value(rules):
    rows = (
        make_row("MID", mwpl=1_000_000, futeq_oi=400_000.50, headroom_shares=549_999),
        make_row("LOW", mwpl=1_000_000, futeq_oi=400_000.99, headroom_shares=549_999),
        make_row("HIGH", mwpl=1_000_000, futeq_oi=400_000.01, headroom_shares=549_999),
    )
    rec = reconcile(rows, rules)

    # All three agree; min and max are about picking extremes, not about failing.
    assert rec.ok
    assert rec.min_residual.symbol == "LOW"
    assert rec.max_residual.symbol == "HIGH"
    assert rec.min_residual.residual < rec.max_residual.residual


# -- what reconcile() refuses -------------------------------------------------------------


def test_no_rows_is_refused(rules):
    with pytest.raises(ValueError, match="no rows"):
        reconcile((), rules)


def test_two_trade_dates_are_refused(rules):
    # parse_mwpl_file() already enforces one date per file, but reconcile() takes a tuple and
    # nothing stops a caller concatenating two days. The function guards its own contract.
    rows = (
        make_row("A", trade_date=dt.date(2026, 10, 30), headroom_shares=550_000),
        make_row("B", trade_date=dt.date(2026, 10, 29), headroom_shares=550_000),
    )
    with pytest.raises(ValueError, match="more than one trade date"):
        reconcile(rows, rules)


def test_a_negative_residual_fails_and_says_so(rules):
    # NSE publishing MORE headroom than the formula allows is the dangerous direction: a desk
    # acting on it takes a position it is not entitled to. |residual| < 1 would not notice.
    row = make_row("TOOGENEROUS", mwpl=1_000_000, futeq_oi=400_000.0, headroom_shares=550_001)
    rec = reconcile((row,), rules)

    assert not rec.ok
    assert rec.residuals[0].residual < 0
    assert "outside [0, 1)" in rec.failures[0]


def test_a_residual_of_one_or_more_fails(rules):
    # More than a whole share out is not truncation, it is a different formula.
    row = make_row("TOOSTINGY", mwpl=1_000_000, futeq_oi=400_000.0, headroom_shares=549_998)
    rec = reconcile((row,), rules)

    assert not rec.ok
    assert rec.residuals[0].residual >= 1


def test_a_file_with_nothing_to_compare_is_a_failure_not_a_pass(rules):
    # `ok` means "no failures", and no comparisons produce no failures. A file where NSE
    # suppressed every headroom figure must not reconcile clean.
    rows = (
        make_row("A", no_fresh_positions=True, headroom_shares=None),
        make_row("B", no_fresh_positions=True, headroom_shares=None),
    )
    rec = reconcile(rows, rules)

    assert rec.residuals == ()
    assert not rec.ok
    assert "nothing was reconciled" in rec.failures[-1]


def test_every_failure_names_the_symbol_it_is_about(rules):
    # A reconciliation report at 18:40 is useless if it says "3 rows failed" without saying
    # which. The only failure allowed not to name a symbol is the nothing-to-compare one.
    rows = (
        make_row("BADONE", mwpl=1_000_000, futeq_oi=400_000.0, headroom_shares=550_001),
        make_row("ALSOBAD", mwpl=1_000_000, futeq_oi=400_000.0, headroom_shares=549_990),
        make_row("FINE", mwpl=1_000_000, futeq_oi=400_000.5, headroom_shares=549_999),
    )
    rec = reconcile(rows, rules)

    assert len(rec.failures) == 2
    assert all(any(f.startswith(s) for s in ("BADONE", "ALSOBAD")) for f in rec.failures)


def test_one_bad_row_does_not_hide_the_others(rules):
    # Failures are collected rather than raised, so the first problem does not mask the rest.
    rows = tuple(
        make_row(f"BAD{i}", mwpl=1_000_000, futeq_oi=400_000.0, headroom_shares=550_001)
        for i in range(5)
    )
    rec = reconcile(rows, rules)

    assert len(rec.failures) == 5


def test_the_result_is_frozen(rules):
    # Same reason Threshold and MwplRow are frozen: nothing downstream should be able to edit
    # a reconciliation into agreeing.
    rec = reconcile((make_row(),), rules)
    with pytest.raises(Exception):
        rec.failures = ()  # type: ignore[misc]
    for frozen in (Residual("X", 0.5), BarredCheck("X", 0.9, True)):
        with pytest.raises(Exception):
            frozen.symbol = "Y"  # type: ignore[misc]


# -- the holes, documented rather than guaranteed -----------------------------------------


def test_utilisation_over_a_pandas_column_returns_inf_with_no_warning():
    """A limitation, not a guarantee.

    `utilisation()` takes two numbers rather than an MwplRow, so it does not carry the row's
    `mwpl > 0` invariant. On scalars a zero MWPL raises ZeroDivisionError, which is loud and
    fine. Over a pandas column - which `as_dataframe()` invites - the same zero yields `inf`
    with NO warning of any kind, and `inf` poisons every aggregate downstream.

    `filterwarnings = ["error::UserWarning"]` does not catch it because pandas raises nothing
    to catch. This is lesson 8 from the other side: MwplRow's protection does not survive the
    DataFrame boundary, and neither does this function's failure mode.
    """
    with pytest.raises(ZeroDivisionError):
        utilisation(5_000_000.0, 0)

    oi = pd.Series([5_000_000.0, 1_234.0])
    mwpl = pd.Series([REDACTED, 0])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = utilisation(oi, mwpl)

    assert caught == []
    assert out.iloc[1] == float("inf")
    assert out.mean() == float("inf")


def test_reconcile_cannot_say_how_many_residuals_agreed(rules):
    """A thin spot in the report shape, recorded so a change to it is deliberate.

    `failures` merges both paths, so from the returned object you cannot say "216 of 216
    residuals agreed" without re-applying the predicate. Derivable, so it is a judgement call
    rather than a bug - but if the report ever needs that count, it belongs in Reconciliation.
    """
    rows = (
        make_row("GOOD", mwpl=1_000_000, futeq_oi=400_000.5, headroom_shares=549_999),
        make_row("BARRED", no_fresh_positions=True, headroom_shares=None),
    )
    rec = reconcile(rows, rules)

    assert not hasattr(rec, "agreed")
    agreed = sum(1 for r in rec.residuals if 0 <= r.residual < 1)
    assert agreed == 1


def test_reconciliation_carries_the_trade_date_it_was_given(rules):
    # So a stored reconciliation can never be read as being about the wrong day - the same
    # reason MwplRow carries it rather than the filename being trusted.
    rec = reconcile((make_row(),), rules)
    assert isinstance(rec, Reconciliation)
    assert rec.trade_date == TRADE_DATE
