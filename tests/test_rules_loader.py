"""Tests for the rules loader.

Two halves. The first checks the real `config/rules.yaml` and the numbers in it, so that a
typo in a threshold fails a test rather than quietly changing what the engine enforces. The
second feeds the loader deliberately broken configs, one per failure mode, because a validator
that has never been shown a bad file is not known to validate anything.

Every broken config below is a mistake that was actually made in `config/rules.yaml` on
2 Nov 2026, or one that the same hand would make next.
"""

from __future__ import annotations

import datetime as dt
import textwrap
import warnings

import pytest

from sentinel.rules import (
    DEFAULT_CONFIG_PATH,
    RuleConfigError,
    Threshold,
    UnverifiedRuleError,
    load_rules,
)


@pytest.fixture(scope="module")
def rules():
    """The real config. `warn=False` because the assumed-threshold warning has its own test."""
    return load_rules(warn=False)


def write_config(tmp_path, body: str):
    path = tmp_path / "rules.yaml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The real config
# ---------------------------------------------------------------------------


def test_the_real_config_loads(rules):
    assert len(rules) > 30
    assert DEFAULT_CONFIG_PATH.is_file()


def test_every_threshold_has_provenance(rules):
    """The point of the whole module. No threshold without a source."""
    for path in rules:
        threshold = rules.describe(path)
        assert threshold.source.strip(), path
        assert threshold.verified is not None or threshold.assumed or path in rules.unverified


def test_ban_entry_is_strictly_greater(rules):
    """SPEC.md row 4. "Exceeds 95%", so exactly 95% is not a ban."""
    entry = rules.get("single_stock.ban.entry_utilisation")
    assert entry.value == 0.95
    assert entry.operator == ">"

    assert entry.compare(0.96) is True
    assert entry.compare(0.95) is False
    assert entry.compare(0.94) is False


def test_ban_exit_is_inclusive(rules):
    """SPEC.md row 5. "80% or below", so exactly 80% is a release.

    Together with the test above, this is the one thing in the config that is most likely to be
    implemented backwards, and the one thing the `operator` field exists to prevent.
    """
    exit_ = rules.get("single_stock.ban.exit_utilisation")
    assert exit_.value == 0.80
    assert exit_.operator == "<="

    assert exit_.compare(0.80) is True
    assert exit_.compare(0.7999) is True
    assert exit_.compare(0.8001) is False


def test_the_two_boundaries_are_inclusive_in_opposite_directions(rules):
    """The asymmetry itself, stated as one assertion.

    A scrip exactly on its entry threshold is not banned; a scrip exactly on its exit threshold
    is released. Both edges favour the trader, and they do so by different wording in two
    different circulars.
    """
    assert rules.compare("single_stock.ban.entry_utilisation", 0.95) is False
    assert rules.compare("single_stock.ban.exit_utilisation", 0.80) is True


def test_minutes_in_year_is_the_denominator(rules):
    """The error that would not have crashed.

    8,670 is the minutes-to-expiry in NSE's worked example - the numerator of T. Putting it here
    makes T come out at 1.0 instead of 0.0165, which corrupts every option delta by about sixty
    times without raising anything.
    """
    minutes = rules.value("mechanics.delta.minutes_in_year")
    assert minutes == 525_600
    assert minutes == 365 * 24 * 60

    # NSE's published worked example: 15:00:05 on 24 Sep 2025, expiry 30 Sep 2025.
    assert round(8_670 / minutes, 4) == 0.0165


def test_index_futures_floor_is_500_crore(rules):
    """SPEC.md row 13. The floor binds below Rs 3,333 cr of index futures OI."""
    floor = rules.value("index.futures.floor_cr")
    share = rules.value("index.futures.fpi_cat_1_mf_tm_prop_client_share")
    assert floor == 500
    assert share == 0.15

    # At 2,000 cr of OI, 15% is 300 cr, so the limit is the floor and not the percentage.
    assert max(0.15 * 2_000, floor) == 500


def test_index_futures_declares_no_operator(rules):
    """"Higher of X or Y" is a MAX, not a comparison. Asking it to compare is an error."""
    threshold = rules.get("index.futures.fpi_cat_1_mf_tm_prop_client_share")
    assert threshold.operator is None
    with pytest.raises(RuleConfigError, match="no operator declared"):
        threshold.compare(0.20)


def test_entity_limits_are_seven_distinct_categories(rules):
    """SPEC.md row 7. Collapsing FPI Cat II to one number is the likely bug."""
    assert rules.value("single_stock.entity_limits.fpi_cat_2_other") == 0.20
    assert rules.value("single_stock.entity_limits.fpi_cat_2_individual_family_corporate") == 0.10

    # The same position, 15% of MWPL, breaches for one sub-category and not the other.
    assert rules.compare("single_stock.entity_limits.fpi_cat_2_individual_family_corporate", 0.15)
    assert not rules.compare("single_stock.entity_limits.fpi_cat_2_other", 0.15)


def test_eod_and_intraday_index_option_limits_are_separate(rules):
    """SPEC.md rows 8 and 9. The gross limits coincide; the net limits do not."""
    assert rules.value("index.options_eod.net_futeq_oi_cr") == 1_500
    assert rules.value("index.options_intraday.net_futeq_oi_cr") == 5_000
    assert rules.value("index.options_eod.gross_futeq_oi_cr") == 10_000
    assert rules.value("index.options_intraday.gross_futeq_oi_cr") == 10_000


def test_rupee_figures_are_numbers_not_strings(rules):
    """`1,500` with a comma parses as the string '1,500' and silently breaks all arithmetic."""
    for path in rules:
        if path.endswith("_cr"):
            assert isinstance(rules.describe(path).value, (int, float)), path


def test_the_closing_window_has_two_ends(rules):
    """An unquoted 15:30 is the integer 930 in YAML. A window also needs a start."""
    window = rules.value("index.options_intraday.closing_snapshot_window")
    assert window == ["14:45", "15:30"]
    assert all(isinstance(end, str) for end in window)


def test_passive_increases_are_not_breaches(rules):
    """SPEC.md rows 6 and 14. Same arithmetic, two causes, opposite answers."""
    assert rules.value("single_stock.ban.passive_increase_is_breach") is False
    assert rules.value("single_stock.ban.active_increase_is_breach") is True
    assert rules.value("index.passive_breach.oi_drop_is_violation") is False
    assert rules.value("index.passive_breach.measured_against_previous_day_oi") is True


def test_sign_change_is_not_an_acceptable_reduction(rules):
    """+10 to 0 is permitted; +10 to -5 is not, although the magnitude fell."""
    assert rules.value("single_stock.ban.sign_change_allowed") is False


def test_no_cure_period_at_the_close(rules):
    """SPEC.md row 10."""
    assert rules.value("mechanics.cure_period.minutes") == 15
    assert rules.value("mechanics.cure_period.applies_to_closing_snapshot") is False


def test_verified_dates_are_dates(rules):
    for path in rules:
        verified = rules.describe(path).verified
        assert verified is None or isinstance(verified, dt.date), path


# ---------------------------------------------------------------------------
# Unverified and assumed thresholds
# ---------------------------------------------------------------------------


def test_the_three_unverified_rules_refuse_to_be_evaluated(rules):
    assert set(rules.unverified) == {
        "single_stock.ban.penalty_rate",
        "single_stock.intraday_mwpl.asm_trigger",
        "mechanics.delta.single_stock_convention",
    }
    for path in rules.unverified:
        with pytest.raises(UnverifiedRuleError):
            rules.get(path)
        with pytest.raises(UnverifiedRuleError):
            rules.value(path)


def test_an_unverified_rule_can_still_be_described(rules):
    """Reports need to say "unknown, and here is why" without being able to evaluate it."""
    threshold = rules.describe("single_stock.ban.penalty_rate")
    assert threshold.value is None
    assert "Exchange" in threshold.source


def test_the_reset_calendar_is_observed_not_assumed(rules):
    """An assumption until 11 Nov 2026; then seen in all four quarters by the year's replay. It
    is sourced as an observation, the way the calendar's Muhurat verdicts are, not as a citation."""
    assert rules.assumed == ()
    threshold = rules.describe("single_stock.mwpl.reset_calendar")
    assert threshold.verified == dt.date(2026, 11, 11)
    assert threshold.value == [1, 4, 7, 10]
    assert threshold.source.startswith("observed (not a circular)")
    for f in ("combineoi_31122025.zip", "combineoi_01012026.zip", "combineoi_30032026.zip",
              "combineoi_01042026.zip", "combineoi_30062026.zip", "combineoi_01072026.zip",
              "combineoi_30092026.zip", "combineoi_01102026.zip"):
        assert f in threshold.source


def test_the_real_config_loads_with_no_assumption_warning():
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        load_rules()


def test_loading_warns_about_assumed_thresholds(tmp_path):
    """An assumption must announce itself at least once per run. The real config has none left,
    so the warning is tested on one built for it."""
    path = write_config(
        tmp_path,
        """
        single_stock:
          made_up:
            threshold:
              value: 3
              source: "ASSUMPTION - a test of the warning"
              verified: null
        """,
    )
    with pytest.warns(UserWarning, match="rest on an assumption"):
        rules = load_rules(path)
    assert rules.assumed == ("single_stock.made_up.threshold",)


# ---------------------------------------------------------------------------
# What the loader refuses
# ---------------------------------------------------------------------------


def test_a_bare_value_is_refused(tmp_path):
    """The entity_limits mistake: seven reasonable-looking numbers and no provenance at all."""
    path = write_config(
        tmp_path,
        """
        single_stock:
          entity_limits:
            client_nri: 0.10
        """,
    )
    with pytest.raises(RuleConfigError, match="expected a mapping"):
        load_rules(path, warn=False)


def test_a_missing_source_is_refused(tmp_path):
    path = write_config(
        tmp_path,
        """
        single_stock:
          ban:
            entry_utilisation:
              value: 0.95
              verified: 2026-11-02
        """,
    )
    with pytest.raises(RuleConfigError, match="missing source"):
        load_rules(path, warn=False)


def test_a_missing_verified_is_refused(tmp_path):
    path = write_config(
        tmp_path,
        """
        single_stock:
          ban:
            entry_utilisation:
              value: 0.95
              source: "SEBI 2025/79 para 5.2.6"
        """,
    )
    with pytest.raises(RuleConfigError, match="missing verified"):
        load_rules(path, warn=False)


def test_a_null_verified_with_no_excuse_is_refused(tmp_path):
    """The honest states are a date, an ASSUMPTION, or a listing. Blank is not one of them."""
    path = write_config(
        tmp_path,
        """
        single_stock:
          ban:
            entry_utilisation:
              value: 0.95
              source: "SEBI 2025/79 para 5.2.6"
              verified: null
        """,
    )
    with pytest.raises(RuleConfigError, match="neither an"):
        load_rules(path, warn=False)


def test_a_misspelled_key_is_refused(tmp_path):
    """`operatro` would be ignored by a plain YAML load, leaving the comparison undeclared."""
    path = write_config(
        tmp_path,
        """
        single_stock:
          ban:
            entry_utilisation:
              value: 0.95
              operatro: ">"
              source: "SEBI 2025/79 para 5.2.6"
              verified: 2026-11-02
        """,
    )
    with pytest.raises(RuleConfigError, match="unknown key"):
        load_rules(path, warn=False)


def test_an_operator_inside_the_value_is_refused(tmp_path):
    """`">0.15"` is a string. It will never compare as a number."""
    path = write_config(
        tmp_path,
        """
        index:
          futures:
            share:
              value: 0.15
              operator: ">0.15"
              source: "SEBI 2025/79 para 5.5.2.1"
              verified: 2026-11-02
        """,
    )
    with pytest.raises(RuleConfigError, match="is not one of"):
        load_rules(path, warn=False)


def test_a_quoted_date_is_refused(tmp_path):
    path = write_config(
        tmp_path,
        """
        single_stock:
          ban:
            entry_utilisation:
              value: 0.95
              source: "SEBI 2025/79 para 5.2.6"
              verified: "2026-11-02"
        """,
    )
    with pytest.raises(RuleConfigError, match="plain YYYY-MM-DD date"):
        load_rules(path, warn=False)


def test_an_unverified_rule_carrying_a_value_is_refused(tmp_path):
    """The liability this config exists to prevent: a plausible number under an unknown rule."""
    path = write_config(
        tmp_path,
        """
        meta:
          unverified:
            - single_stock.ban.penalty_rate
        single_stock:
          ban:
            penalty_rate:
              value: 0.01
              source: "UNVERIFIED. The rate is set by the exchange"
              verified: null
        """,
    )
    with pytest.raises(RuleConfigError, match="must be null"):
        load_rules(path, warn=False)


def test_a_stale_unverified_list_is_refused(tmp_path):
    """A listed path that no longer exists means the rule quietly became evaluable.

    The threshold below is independently valid - it has a date - so the only fault in this
    config is the list naming something that is not there. Anything else in the fixture would
    trip a different check first and prove nothing about this one.
    """
    path = write_config(
        tmp_path,
        """
        meta:
          unverified:
            - single_stock.ban.penalty_rate_renamed
        single_stock:
          ban:
            penalty_rate:
              value: 0.01
              source: "NSE circular, para 1"
              verified: 2026-11-02
        """,
    )
    with pytest.raises(RuleConfigError, match="do not exist"):
        load_rules(path, warn=False)


def test_a_listed_rule_that_is_now_verified_is_refused(tmp_path):
    """The opposite drift: the source was found but the list was not updated."""
    path = write_config(
        tmp_path,
        """
        meta:
          unverified:
            - single_stock.ban.penalty_rate
        single_stock:
          ban:
            penalty_rate:
              value: 0.01
              source: "NSE circular, para 1"
              verified: 2026-11-02
        """,
    )
    with pytest.raises(RuleConfigError, match="Remove it from the list"):
        load_rules(path, warn=False)


def test_an_empty_block_is_refused(tmp_path):
    """`minutes:` with nothing after it. A blank is not a statement."""
    path = write_config(
        tmp_path,
        """
        mechanics:
          cure_period: {}
        """,
    )
    with pytest.raises(RuleConfigError, match="empty block"):
        load_rules(path, warn=False)


def test_unparseable_yaml_is_refused(tmp_path):
    """What the file looked like at 11:00 on 2 Nov: `key:"value"` with no space."""
    path = tmp_path / "rules.yaml"
    path.write_text('single_stock:\n  ban:\n    tested_at:"end_of_day"\n    source: x\n', "utf-8")
    with pytest.raises(RuleConfigError, match="not valid YAML"):
        load_rules(path, warn=False)


def test_a_missing_file_is_refused(tmp_path):
    with pytest.raises(RuleConfigError, match="no rules config"):
        load_rules(tmp_path / "nope.yaml", warn=False)


# ---------------------------------------------------------------------------
# Threshold itself
# ---------------------------------------------------------------------------


def test_threshold_is_immutable():
    """A threshold handed to the engine must not be adjustable by the engine."""
    threshold = Threshold(
        path="x.y",
        value=0.95,
        source="SEBI 2025/79 para 5.2.6",
        verified=dt.date(2026, 11, 2),
        operator=">",
    )
    with pytest.raises(AttributeError):
        threshold.value = 0.90  # type: ignore[misc]
