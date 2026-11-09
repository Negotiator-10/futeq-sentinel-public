"""Tests for the holder and account reference tables behind SPEC row 7.

Decided in DECISIONS.md #016's addendum. Accounts are keyed on (tm, ucc), the trading member is
a property of the account rather than the holder, and a TM's 30% counts its proprietary accounts
plus CLIENT/NRI accounts registered under it - not FPI or MF accounts, which SEBI treats as
trading members in their own right.

The reference data is synthetic.
"""

from __future__ import annotations

import datetime as dt

import pytest

from sentinel.entities import Category, ReferenceDataError, load_reference

HOLDERS_HEADER = "effective_from,holder_id,category,sub_category\n"
ACCOUNTS_HEADER = "effective_from,tm,ucc,holder_id,is_proprietary\n"
D = dt.date(2026, 11, 2)


def load(tmp_path, holders: str, accounts: str):
    h = tmp_path / "holders.csv"
    a = tmp_path / "accounts.csv"
    h.write_text(HOLDERS_HEADER + holders, encoding="utf-8")
    a.write_text(ACCOUNTS_HEADER + accounts, encoding="utf-8")
    return load_reference(h, a)


#: Two brokers, a client at both, an FPI and an MF trading through broker TMA.
HOLDERS = (
    "2026-10-01,TMA,tm_proprietary,\n"
    "2026-10-01,TMB,tm_proprietary,\n"
    "2026-10-01,ASHA,client_nri,\n"
    "2026-10-01,FPI1,fpi_cat_1,\n"
    "2026-10-01,FUNDX,mutual_fund,\n"
)
ACCOUNTS = (
    "2026-10-01,TMA,PRO1,TMA,true\n"
    "2026-10-01,TMB,PRO1,TMB,true\n"
    "2026-10-01,TMA,C001,ASHA,false\n"
    "2026-10-01,TMB,C001,ASHA,false\n"
    "2026-10-01,TMA,F001,FPI1,false\n"
    "2026-10-01,TMA,S001,FUNDX,false\n"
    "2026-10-01,TMA,S002,FUNDX,false\n"
)


@pytest.fixture
def snap(tmp_path):
    return load(tmp_path, HOLDERS, ACCOUNTS).as_of(D)


# -- the aggregates decision A defines ----------------------------------------------------


def test_the_same_ucc_under_two_brokers_is_two_accounts(snap):
    """A UCC is a code a trading member assigns, so it is only unique within one TM."""
    assert snap.account("TMA", "C001").holder_id == "ASHA"
    assert snap.account("TMB", "C001").holder_id == "ASHA"
    assert snap.account("TMA", "PRO1").holder_id == "TMA"
    assert snap.account("TMB", "PRO1").holder_id == "TMB"


def test_a_clients_own_limit_spans_every_broker(snap):
    assert [a.key for a in snap.accounts_of("ASHA")] == [("TMA", "C001"), ("TMB", "C001")]


def test_a_tms_twenty_percent_is_its_proprietary_book_only(snap):
    assert [a.key for a in snap.proprietary_accounts_of("TMA")] == [("TMA", "PRO1")]


def test_a_tms_thirty_percent_is_prop_plus_client_nri_accounts_under_it(snap):
    """FPI and MF accounts under TMA are excluded: SEBI treats both as trading members."""
    keys = [a.key for a in snap.combined_accounts_of("TMA")]
    assert keys == [("TMA", "C001"), ("TMA", "PRO1")]
    assert ("TMA", "F001") not in keys and ("TMA", "S001") not in keys


def test_a_client_at_two_brokers_counts_once_in_each_brokers_thirty_percent(snap):
    assert ("TMA", "C001") in [a.key for a in snap.combined_accounts_of("TMA")]
    assert ("TMB", "C001") in [a.key for a in snap.combined_accounts_of("TMB")]
    assert ("TMB", "C001") not in [a.key for a in snap.combined_accounts_of("TMA")]


def test_an_mf_is_its_own_level_with_its_schemes_as_accounts(snap):
    assert [a.ucc for a in snap.accounts_of("FUNDX")] == ["S001", "S002"]
    assert snap.holder("FUNDX").category is Category.MUTUAL_FUND


def test_an_unknown_account_is_refused_not_guessed(snap):
    with pytest.raises(ReferenceDataError, match="cannot be attributed"):
        snap.account("TMA", "NOPE")


# -- date-effective -----------------------------------------------------------------------


def test_the_latest_row_on_or_before_the_date_applies(tmp_path):
    ref = load(tmp_path,
               "2026-10-01,ASHA,client_nri,\n"
               "2026-11-01,ASHA,fpi_cat_2_individual_family_corporate,individual\n",
               "2026-10-01,TMA,C001,ASHA,false\n")
    assert ref.as_of(dt.date(2026, 10, 15)).holder("ASHA").category is Category.CLIENT_NRI
    assert ref.as_of(dt.date(2026, 11, 2)).holder("ASHA").category is Category.FPI_CAT_II_IFC


def test_an_account_whose_holder_is_not_yet_effective_is_refused(tmp_path):
    ref = load(tmp_path, "2026-11-01,ASHA,client_nri,\n", "2026-10-01,TMA,C001,ASHA,false\n")
    with pytest.raises(ReferenceDataError, match="no holders row effective"):
        ref.as_of(dt.date(2026, 10, 15))
    assert ref.as_of(dt.date(2026, 11, 2)).account("TMA", "C001").holder_id == "ASHA"


def test_two_rows_for_one_key_on_one_date_are_refused(tmp_path):
    with pytest.raises(ReferenceDataError, match="two rows effective"):
        load(tmp_path, "2026-10-01,ASHA,client_nri,\n2026-10-01,ASHA,client_nri,\n",
             "2026-10-01,TMA,C001,ASHA,false\n")


# -- decision 1, held at the table ------------------------------------------------------


def test_a_cat_ii_corporate_filed_as_other_is_refused(tmp_path):
    """NSE FAQ 15's error, typed in by hand. The sub-category says 10%; the row says 20%."""
    with pytest.raises(ReferenceDataError, match="contradicts itself"):
        load(tmp_path, "2026-10-01,CORP,fpi_cat_2_other,corporate\n",
             "2026-10-01,TMA,X001,CORP,false\n")


def test_a_cat_ii_holder_without_a_sub_category_is_refused(tmp_path):
    with pytest.raises(ReferenceDataError, match="has no sub_category"):
        load(tmp_path, "2026-10-01,CORP,fpi_cat_2_other,\n", "2026-10-01,TMA,X001,CORP,false\n")


def test_a_bare_cat_ii_category_is_refused(tmp_path):
    with pytest.raises(ReferenceDataError, match="no bare FPI"):
        load(tmp_path, "2026-10-01,CORP,fpi_cat_2,corporate\n", "2026-10-01,TMA,X001,CORP,false\n")


def test_a_sub_category_on_a_non_cat_ii_holder_is_refused(tmp_path):
    with pytest.raises(ReferenceDataError, match="Only FPI Category II"):
        load(tmp_path, "2026-10-01,ASHA,client_nri,individual\n", "2026-10-01,TMA,C001,ASHA,false\n")


# -- invariants that span both tables -----------------------------------------------------


def test_a_proprietary_flag_on_a_client_account_is_refused(tmp_path):
    ref = load(tmp_path, "2026-10-01,ASHA,client_nri,\n", "2026-10-01,TMA,C001,ASHA,true\n")
    with pytest.raises(ReferenceDataError, match="must agree"):
        ref.as_of(D)


def test_a_tm_account_not_marked_proprietary_is_refused(tmp_path):
    ref = load(tmp_path, "2026-10-01,TMA,tm_proprietary,\n", "2026-10-01,TMA,PRO1,TMA,false\n")
    with pytest.raises(ReferenceDataError, match="must agree"):
        ref.as_of(D)


def test_a_proprietary_account_owned_by_another_tm_is_refused(tmp_path):
    """The case review found accepted on 8 Nov: an account registered under TMA, marked
    proprietary, owned by TMB. TMA's 20% would have been computed on positions TMA does not own.
    A TM's holder_id is its member code, and that convention is enforced here."""
    ref = load(tmp_path,
               "2026-10-01,TMA,tm_proprietary,\n2026-10-01,TMB,tm_proprietary,\n",
               "2026-10-01,TMA,PRO1,TMB,true\n")
    with pytest.raises(ReferenceDataError,
                       match="TMA/PRO1 is owned by TMB; a TM's proprietary book must be owned "
                             "by that TM"):
        ref.as_of(D)


def test_one_tms_proprietary_book_cannot_have_two_owners(tmp_path):
    """Subsumed by the convention: if every proprietary account under TMA must be owned by TMA,
    two owners are impossible. Kept because the case is real, now refused by that rule."""
    ref = load(tmp_path,
               "2026-10-01,TMA,tm_proprietary,\n2026-10-01,TMB,tm_proprietary,\n",
               "2026-10-01,TMA,PRO1,TMA,true\n2026-10-01,TMA,PRO2,TMB,true\n")
    with pytest.raises(ReferenceDataError, match="TMA/PRO2 is owned by TMB"):
        ref.as_of(D)


def test_a_client_account_may_belong_to_anyone(tmp_path):
    """The convention binds proprietary accounts only. A client's holder_id is its own."""
    snap = load(tmp_path, "2026-10-01,ASHA,client_nri,\n",
                "2026-10-01,TMA,C001,ASHA,false\n").as_of(D)
    assert snap.account("TMA", "C001").holder_id == "ASHA"


@pytest.mark.parametrize("flag", ["", "yes", "1", "Y"])
def test_is_proprietary_must_be_written_true_or_false(tmp_path, flag):
    """A blank is not 'no'; it is a row nobody finished."""
    with pytest.raises(ReferenceDataError, match="Write true or"):
        load(tmp_path, "2026-10-01,ASHA,client_nri,\n", f"2026-10-01,TMA,C001,ASHA,{flag}\n")


def test_an_empty_table_is_refused(tmp_path):
    with pytest.raises(ReferenceDataError, match="no rows"):
        load(tmp_path, "", "")
