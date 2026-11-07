"""Tests for `sentinel.entities` - the holder categories behind SPEC row 7.

The one that matters is the regression test for NSE Clearing FAQ question 15, which summarises
FPI Category II as individuals (10%) versus "non-individuals" (20%). SEBI 2025/79 para 5.8.1.5
puts corporates and family offices WITH individuals at 10%. A model built from the FAQ would give
a Cat II corporate double its limit, and nothing would complain.
"""

from __future__ import annotations

import pytest

from sentinel.entities import TM_COMBINED_LIMIT_KEY, Category, CategoryError
from sentinel.rules import load_rules


@pytest.fixture(scope="module")
def rules():
    return load_rules(warn=False)


# -- the FAQ 15 regression ----------------------------------------------------------------


@pytest.mark.parametrize("sub", ["corporate", "family_office", "family office", "Corporate"])
def test_a_cat_ii_corporate_or_family_office_gets_ten_percent_not_twenty(rules, sub):
    """The trap. NSE's FAQ calls these "non-individuals" and lists non-individuals at 20%."""
    category = Category.for_fpi_cat_ii(sub)
    assert category is Category.FPI_CAT_II_IFC
    assert rules.value(category.limit_key) == 0.10


def test_a_cat_ii_individual_gets_ten_percent(rules):
    assert rules.value(Category.for_fpi_cat_ii("individual").limit_key) == 0.10


def test_cat_ii_other_must_be_said_explicitly(rules):
    assert Category.for_fpi_cat_ii("other") is Category.FPI_CAT_II_OTHER
    assert rules.value(Category.FPI_CAT_II_OTHER.limit_key) == 0.20


@pytest.mark.parametrize("sub", ["non-individual", "non_individual", "company", "", "fund"])
def test_an_unrecognised_cat_ii_sub_category_is_refused_not_defaulted(sub):
    """The only available default is 20%, the lenient direction - and "non-individual" is the
    FAQ's own word, so it in particular must not quietly resolve."""
    with pytest.raises(CategoryError, match="Not defaulted"):
        Category.for_fpi_cat_ii(sub)


def test_there_is_no_bare_cat_ii_member():
    """Two members and never one. A single Cat II member is the bug."""
    cat_ii = {c for c in Category if "cat_2" in c.value}
    assert cat_ii == {Category.FPI_CAT_II_OTHER, Category.FPI_CAT_II_IFC}


def test_the_enum_has_exactly_the_six_ucc_categories():
    """And no accidental seventh - a plain attribute in an Enum body becomes a member."""
    assert len(Category) == 6


# -- every category resolves to a verified threshold --------------------------------------


@pytest.mark.parametrize("category", list(Category))
def test_every_category_has_a_verified_limit(rules, category):
    threshold = rules.get(category.limit_key)
    assert threshold.verified is not None
    assert threshold.operator == ">"
    assert "5.8.1" in threshold.source


def test_the_limits_match_para_5_8_1(rules):
    expected = {
        Category.CLIENT_NRI: 0.10,
        Category.TM_PROPRIETARY: 0.20,
        Category.FPI_CAT_I: 0.30,
        Category.MUTUAL_FUND: 0.30,
        Category.FPI_CAT_II_OTHER: 0.20,
        Category.FPI_CAT_II_IFC: 0.10,
    }
    assert {c: rules.value(c.limit_key) for c in Category} == expected


def test_the_tm_combined_limit_is_an_aggregate_not_a_category(rules):
    """TM (proprietary + client) limits a sum across UCCs, so it is not a UCC's category."""
    assert rules.value(TM_COMBINED_LIMIT_KEY) == 0.30
    assert "tm_prop_plus_client" not in {c.value for c in Category}
