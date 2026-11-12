"""Row 7 in the runner: #016 addendum 2, on the synthetic window.

Written by Claude on 12 Nov 2026, before the stage exists, so Chintamani writes the stage
against them. The plumbing tests at the top pass now; the stage tests fail until the stage
lands. Every reason is asserted as text. The texts are the ones the addendum gives; where it
gives none (a missing file, a missing today-book) they follow `_row6()`'s wording. Change a
text here and in the stage together, never in only one.

The setup, on every window day (MWPL 1,000,000 for every scrip, so a client's 10% is 100,000
shares and a trading member's 20% and 30% are 200,000 and 300,000):

    holder  category         accounts
    H1      client_nri       TMA/C1
    TMA     tm_proprietary   TMA/PRO

    day      TMA/C1 QUIETCO   TMA/PRO QUIETCO   H1's 10%
    12 Oct   110 lots         50 lots           over by 10,000, cause unknown: the book start
    13 Oct   120 lots         50 lots           over by 20,000, ACTIVE: holdings added 10,000
    14 Oct   120 lots         50 lots           over by 20,000, PASSIVE: MWPL unchanged

Lot size 1,000; one October future, factor 1. TMA's two checks pass every day.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from decimal import Decimal

import pytest

from sentinel import runner
from sentinel.book import BookError
from sentinel.engine import EntityLimitCheck, EntityLimitResult, LimitCause, NotChecked
from sentinel.entities import TM_COMBINED_LIMIT_KEY, Category, ReferenceDataError
from sentinel.runner import Row7Outcome, Row7Status, RunPaths
from sentinel.store import Refusal, RefusalStage, RunOutcome
from tests.test_ingest import build_combineoi
from tests.test_runner import (
    WINDOW_START, isin_of, open_store, synthetic_paths, window_rows_by_day,
)

D12, D13, D14 = dt.date(2026, 10, 12), dt.date(2026, 10, 13), dt.date(2026, 10, 14)
QUIET = isin_of("QUIETCO")
NO_MWPL = "INE000Z01010"            # in no window combineoi: a scrip with no MWPL
EXPIRY = dt.date(2026, 10, 27)
LOT = 1000

CLIENT_LIMIT = Category.CLIENT_NRI.limit_key
TM_LIMIT = Category.TM_PROPRIETARY.limit_key

POSITIONS_HEADER = "trade_date,tm,ucc,isin,instrument,expiry,strike,lot_size,quantity_lots\n"
HOLDERS = ("effective_from,holder_id,category,sub_category\n"
           "2026-10-01,H1,client_nri,\n"
           "2026-10-01,TMA,tm_proprietary,\n")
ACCOUNTS = ("effective_from,tm,ucc,holder_id,is_proprietary\n"
            "2026-10-01,TMA,C1,H1,false\n"
            "2026-10-01,TMA,PRO,TMA,true\n")

# day -> [(tm, ucc, isin, lots)]
BOOK = {
    D12: [("TMA", "C1", QUIET, 110), ("TMA", "PRO", QUIET, 50)],
    D13: [("TMA", "C1", QUIET, 120), ("TMA", "PRO", QUIET, 50)],
    D14: [("TMA", "C1", QUIET, 120), ("TMA", "PRO", QUIET, 50)],
}


# ---------------------------------------------------------------- setup

def write_book(paths: RunPaths, book: dict) -> None:
    """One positions.csv for the whole window. A day whose value is "FLAT" gets the marker."""
    lines = []
    for day, rows in sorted(book.items()):
        if rows == "FLAT":
            lines.append(f"{day.isoformat()},,,,FLAT,,,,\n")
            continue
        lines += [f"{day.isoformat()},{tm},{ucc},{isin},FF,{EXPIRY.isoformat()},0,{LOT},{lots}\n"
                  for tm, ucc, isin, lots in rows]
    paths.book.write_text(POSITIONS_HEADER + "".join(lines), encoding="utf-8")


def write_deltas(paths: RunPaths) -> None:
    """A Contract_Delta file per window day: QUIETCO's October future at exactly 1."""
    for day in (D12, D13, D14):
        paths.delta(day).write_text(
            "Date,Symbol,Expiry day,Strike Price,Option Type,Delta Factor\n"
            f"{day:%d-%m-%Y},QUIETCO,{EXPIRY:%d-%m-%Y},0,FF,1.00000000\n",
            encoding="utf-8")


def row7_paths(tmp_path, *, book=None, holders=HOLDERS, accounts=ACCOUNTS,
               book_start=WINDOW_START, calendar=None) -> RunPaths:
    paths = synthetic_paths(tmp_path, book_start=book_start, calendar=calendar)
    paths.book.parent.mkdir(parents=True)
    write_book(paths, BOOK if book is None else book)
    paths.holders().write_text(holders, encoding="utf-8")
    paths.accounts().write_text(accounts, encoding="utf-8")
    write_deltas(paths)
    return paths


def run(paths: RunPaths, day: dt.date) -> None:
    assert runner.run_day(day, paths) is RunOutcome.COMPLETED     # row 7 never stops the run


def row7_refusals(store, day) -> list[tuple[str, str]]:
    return sorted((r.subject, r.reason) for r in store.refusals(day)
                  if r.stage is RefusalStage.ROW7)


def check(store, day, holder_id, limit_key, isin=QUIET):
    [c] = [c for c in store.row7_result(day).checks
           if (c.holder_id, c.limit_key, c.isin) == (holder_id, limit_key, isin)]
    return c


def assert_stage_refused(paths, day, reason=None, *, prefix=None) -> str:
    """Row 7 refused as a whole stage, with nothing in its tables, and the rest of D stored."""
    with open_store(paths) as store:
        refusals = row7_refusals(store, day)
        assert len(refusals) == 1, refusals
        subject, text = refusals[0]
        assert subject == ""                                      # the whole stage
        if reason is not None:
            assert text == reason
        if prefix is not None:
            assert text.startswith(prefix), text
        result = store.row7_result(day)
        assert result.checks == () and result.not_checked == ()
        assert store.measurements(day) and store.reconciliation(day)
    return text


# ---------------------------------------------------------------- plumbing (passes now)

def test_the_reference_tables_sit_beside_the_positions_file(tmp_path):
    paths = synthetic_paths(tmp_path)
    assert paths.holders() == paths.book.parent / "holders.csv"
    assert paths.accounts() == paths.book.parent / "accounts.csv"
    default = RunPaths.default()
    assert default.holders() == default.data / "book" / "holders.csv"
    assert default.accounts() == default.data / "book" / "accounts.csv"


def test_row_7s_inputs_are_checksummed(tmp_path):
    paths = row7_paths(tmp_path)
    sums = runner.input_checksums(paths, D13, D12)
    for f in (paths.book, paths.holders(), paths.accounts(), paths.book_config,
              paths.combineoi(D12), paths.combineoi(D13), paths.delta(D12), paths.delta(D13)):
        assert sums[f.name] == runner._sha256(f), f.name


def test_a_missing_input_is_left_out_of_the_checksums_not_recorded_as_none(tmp_path):
    paths = row7_paths(tmp_path)
    paths.combineoi(D12).unlink()
    paths.holders().unlink()
    sums = runner.input_checksums(paths, D13, D12)
    assert paths.combineoi(D12).name not in sums
    assert "holders.csv" not in sums
    assert None not in sums.values()


def test_with_no_previous_day_yesterdays_files_are_not_asked_for(tmp_path):
    paths = row7_paths(tmp_path)
    sums = runner.input_checksums(paths, D13, None)
    assert paths.combineoi(D12).name not in sums and paths.delta(D12).name not in sums


# ---------------------------------------------------------------- the stage: checks made

def test_the_start_date_gives_no_prior_day_and_an_unknown_cause(tmp_path):
    paths = row7_paths(tmp_path)
    run(paths, D12)
    with open_store(paths) as store:
        assert row7_refusals(store, D12) == []
        assert len(store.row7_result(D12).checks) == 3            # H1's 10%, TMA's 20% and 30%
        h1 = check(store, D12, "H1", CLIENT_LIMIT)
        assert h1.cause is LimitCause.UNKNOWN
        assert h1.excess_shares == 10_000
        assert h1.reason == "over by 10000 shares; cause unknown: first day of the book"


def test_after_the_start_a_breach_that_grew_is_active(tmp_path):
    paths = row7_paths(tmp_path)
    run(paths, D13)
    with open_store(paths) as store:
        assert row7_refusals(store, D13) == []
        h1 = check(store, D13, "H1", CLIENT_LIMIT)
        assert h1.cause is LimitCause.ACTIVE
        assert h1.reason == "over by 20000 shares; holdings added 10000 to the gross position"
        assert check(store, D13, "TMA", TM_LIMIT).permitted
        assert check(store, D13, "TMA", TM_COMBINED_LIMIT_KEY).permitted


def test_yesterdays_combineoi_names_the_passive_mechanism(tmp_path):
    paths = row7_paths(tmp_path)
    run(paths, D14)                     # 14 Oct has no ban list; row 7 does not need one
    with open_store(paths) as store:
        h1 = check(store, D14, "H1", CLIENT_LIMIT)
        assert h1.cause is LimitCause.PASSIVE
        assert h1.reason.endswith(
            "MWPL unchanged, so delta factors moved (PASSIVE does not mean no trading)")


def test_a_missing_yesterday_combineoi_makes_the_reason_vaguer_not_a_refusal(tmp_path):
    paths = row7_paths(tmp_path)
    paths.combineoi(D13).unlink()
    run(paths, D14)
    with open_store(paths) as store:
        assert row7_refusals(store, D14) == []
        h1 = check(store, D14, "H1", CLIENT_LIMIT)
        assert h1.cause is LimitCause.PASSIVE                     # the cause is unchanged
        assert h1.reason.endswith("mechanism not identified (no MWPL for yesterday)")


def test_a_flat_day_stores_nothing_and_refuses_nothing(tmp_path):
    # record_row7() refuses an empty result, so the stage must not call it on a flat day.
    # What the store then says about the day is open: DECISIONS #016 addendum 2 follow-up 4a.
    paths = row7_paths(tmp_path, book={D12: BOOK[D12], D13: "FLAT"})
    run(paths, D13)
    with open_store(paths) as store:
        assert row7_refusals(store, D13) == []
        result = store.row7_result(D13)
        assert result.checks == () and result.not_checked == ()


def test_a_rerun_with_the_same_inputs_changes_nothing(tmp_path):
    paths = row7_paths(tmp_path)
    run(paths, D13)
    with open_store(paths) as store:
        before = (store.row7_result(D13), store.refusals(D13))
    run(paths, D13)
    with open_store(paths) as store:
        assert (store.row7_result(D13), store.refusals(D13)) == before


# ---------------------------------------------------------------- the stage: refused

def test_after_the_start_a_missing_yesterday_book_refuses_row_7(tmp_path):
    paths = row7_paths(tmp_path, book={D13: BOOK[D13]})
    run(paths, D13)
    assert_stage_refused(paths, D13, "no prop book for 2026-10-12")


def test_a_missing_today_book_refuses_row_7(tmp_path):
    paths = row7_paths(tmp_path, book={D12: BOOK[D12]})
    run(paths, D13)
    assert_stage_refused(paths, D13, "no prop book for 2026-10-13")


def test_before_the_start_row_7_refuses(tmp_path):
    paths = row7_paths(tmp_path, book_start=D13)
    run(paths, D12)
    assert_stage_refused(paths, D12, "before the book's start date")


def test_a_missing_reference_file_refuses_row_7_not_the_run(tmp_path):
    # load_reference() would raise FileNotFoundError, which is not caught: the stage checks
    # that its files exist first, as _row6() does.
    paths = row7_paths(tmp_path)
    paths.holders().unlink()
    run(paths, D13)
    assert_stage_refused(paths, D13, "missing: holders.csv")


def test_reference_data_that_will_not_load_refuses_row_7(tmp_path):
    paths = row7_paths(tmp_path, holders=HOLDERS + "2026-10-01,H1,client_nri,\n")  # H1 twice
    run(paths, D13)
    text = assert_stage_refused(paths, D13, prefix="reference data could not be loaded: ")
    assert "H1 has two rows effective 2026-10-01" in text


def test_a_snapshot_that_fails_its_checks_carries_the_load_reason(tmp_path):
    # Loads cleanly, file by file; as_of() then finds an account with no holder.
    paths = row7_paths(tmp_path, accounts=ACCOUNTS + "2026-10-01,TMA,C9,NOBODY,false\n")
    run(paths, D13)
    text = assert_stage_refused(paths, D13, prefix="reference data could not be loaded: ")
    assert "NOBODY" in text


def test_a_position_in_an_unknown_account_refuses_row_7(tmp_path):
    paths = row7_paths(tmp_path, book={D12: BOOK[D12],
                                       D13: BOOK[D13] + [("TMA", "GHOST", QUIET, 1)]})
    run(paths, D13)
    text = assert_stage_refused(paths, D13, prefix="position in unknown account: ")
    assert "GHOST" in text


def test_a_scrip_with_no_mwpl_is_one_refusal_with_the_count(tmp_path):
    # TMA/C1 holds it, so H1's 10% and TMA's 30% fall on it; TMA's 20% does not.
    paths = row7_paths(tmp_path, book={D12: BOOK[D12],
                                       D13: BOOK[D13] + [("TMA", "C1", NO_MWPL, 5)]})
    run(paths, D13)
    with open_store(paths) as store:
        assert row7_refusals(store, D13) == [
            (NO_MWPL, "no MWPL in today's combineoi; 2 checks not made")]
        result = store.row7_result(D13)
        assert {n.key for n in result.not_checked} == {
            ("H1", NO_MWPL, CLIENT_LIMIT), ("TMA", NO_MWPL, TM_COMBINED_LIMIT_KEY)}
        assert len(result.checks) == 3                            # QUIETCO still checked


def test_a_day_where_every_held_scrip_lacks_mwpl_is_checked_not_flat_or_refused(tmp_path):
    # Only not-checked entries and no checks: record_row7() accepts that, so it is stored like
    # any checked day. Not a whole-stage refusal, and not read as a flat book.
    paths = row7_paths(tmp_path, book={D12: BOOK[D12], D13: [("TMA", "C1", NO_MWPL, 5)]})
    run(paths, D13)
    with open_store(paths) as store:
        assert row7_refusals(store, D13) == [
            (NO_MWPL, "no MWPL in today's combineoi; 2 checks not made")]
        result = store.row7_result(D13)
        assert result.checks == ()
        assert {n.key for n in result.not_checked} == {
            ("H1", NO_MWPL, CLIENT_LIMIT), ("TMA", NO_MWPL, TM_COMBINED_LIMIT_KEY)}


def test_only_reference_data_errors_are_caught(tmp_path, monkeypatch):
    # Assumes the runner imports check_entity_limit by name, as it imports row 6's function.
    paths = row7_paths(tmp_path)

    def boom(*args, **kwargs):
        raise ValueError("not a reference data error")

    monkeypatch.setattr(runner, "check_entity_limit", boom)
    with pytest.raises(ValueError):
        runner.run_day(D13, paths)
    with open_store(paths) as store:
        assert store.runs_for(D13)[-1].outcome is RunOutcome.FAILED
        assert store.measurements(D13) == ()                     # the whole day rolled back


# ---------------------------------------------------------------- the stage: added for review

def test_one_scrip_one_check_not_made_is_singular(tmp_path):
    # An FPI account under TMA: the FPI's own 30% falls on the scrip, and TMA's 30% does not,
    # because FPI accounts are left out of a broker's clients (#016 addendum 1a). One check.
    paths = row7_paths(
        tmp_path,
        holders=HOLDERS + "2026-10-01,FPI1,fpi_cat_1,\n",
        accounts=ACCOUNTS + "2026-10-01,TMA,F1,FPI1,false\n",
        book={D12: BOOK[D12], D13: BOOK[D13] + [("TMA", "F1", NO_MWPL, 5)]})
    run(paths, D13)
    with open_store(paths) as store:
        assert row7_refusals(store, D13) == [
            (NO_MWPL, "no MWPL in today's combineoi; 1 check not made")]


def test_a_flat_day_still_checks_the_reference_data(tmp_path):
    # A broken holders.csv shows the day it breaks, not the first day a position appears.
    paths = row7_paths(tmp_path, book={D12: BOOK[D12], D13: "FLAT"},
                       holders=HOLDERS + "2026-10-01,H1,client_nri,\n")
    run(paths, D13)
    assert_stage_refused(paths, D13, prefix="reference data could not be loaded: ")


def test_an_unsettled_previous_day_refuses_row_7(tmp_path):
    # Mon 9 Nov follows the Muhurat Sunday. With the chaining rows stripped from the calendar,
    # its previous trading day is undecided: D itself is settled, only yesterday is not.
    stripped = tmp_path / "calendar_unverified.csv"
    lines = RunPaths.default().calendar.read_text(encoding="utf-8").splitlines()
    stripped.write_text("\n".join(l for l in lines if "chaining_" not in l) + "\n",
                        encoding="utf-8")
    mon_9_nov = dt.date(2026, 11, 9)
    paths = row7_paths(tmp_path, calendar=stripped)
    build_combineoi(paths.data, mon_9_nov,
                    [dict(r, trade_date=mon_9_nov.isoformat()) for r in window_rows_by_day()[D13]])
    paths.delta(mon_9_nov).write_text(paths.delta(D13).read_text(encoding="utf-8"),
                                      encoding="utf-8")       # only has to exist
    run(paths, mon_9_nov)
    text = assert_stage_refused(paths, mon_9_nov, prefix="previous trading day unsettled: ")
    assert "2026-11-08 is a special session" in text


def assert_failed_and_rolled_back(paths, day, exc_type):
    with pytest.raises(exc_type):
        runner.run_day(day, paths)
    with open_store(paths) as store:
        assert store.runs_for(day)[-1].outcome is RunOutcome.FAILED
        assert store.measurements(day) == ()                     # the whole day rolled back
        assert store.refusals(day) == ()


def test_a_book_with_positions_and_an_empty_result_fails_the_run(tmp_path, monkeypatch):
    # Every position gives a check or a NotChecked, so an empty result here is a bug. Labelling
    # it FLAT would let #023's marker claim "ran, nothing held".
    paths = row7_paths(tmp_path)
    monkeypatch.setattr(runner, "check_entity_limit",
                        lambda *a, **kw: EntityLimitResult(checks=()))
    assert_failed_and_rolled_back(paths, D13, RuntimeError)


def test_a_flat_book_with_entries_fails_the_run(tmp_path, monkeypatch):
    paths = row7_paths(tmp_path, book={D12: BOOK[D12], D13: "FLAT"})
    entry = NotChecked(D13, "H1", QUIET, CLIENT_LIMIT, "no MWPL for this scrip in today's combineoi")
    monkeypatch.setattr(runner, "check_entity_limit",
                        lambda *a, **kw: EntityLimitResult(checks=(), not_checked=(entry,)))
    assert_failed_and_rolled_back(paths, D13, RuntimeError)


def test_a_malformed_book_config_fails_the_run_not_only_row_7(tmp_path):
    # book.yaml is configuration, like rules.yaml: a typo fails loudly rather than refusing
    # row 7 quietly every day.
    paths = row7_paths(tmp_path)
    paths.book_config.write_text("start_dat: 2026-10-12\nreason: a typo\n", encoding="utf-8")
    assert_failed_and_rolled_back(paths, D13, BookError)
    with open_store(paths) as store:
        assert store.runs_for(D13)[-1].reason.startswith("BookError: ")


def test_a_book_start_on_a_holiday_fails_the_run(tmp_path):
    paths = row7_paths(tmp_path, book_start=dt.date(2026, 10, 11))      # a Sunday
    assert_failed_and_rolled_back(paths, D13, BookError)


# ---------------------------------------------------------------- added after the mutation check

SECOND_NO_MWPL = "INE000Y01012"     # sorts before NO_MWPL


def test_two_scrips_with_no_mwpl_each_get_their_own_count(tmp_path):
    # NO_MWPL through TMA/C1 gives two checks not made; SECOND_NO_MWPL through the FPI's
    # account gives one. A count taken over all not-checked entries would say 3 for both.
    paths = row7_paths(
        tmp_path,
        holders=HOLDERS + "2026-10-01,FPI1,fpi_cat_1,\n",
        accounts=ACCOUNTS + "2026-10-01,TMA,F1,FPI1,false\n",
        book={D12: BOOK[D12], D13: BOOK[D13] + [("TMA", "C1", NO_MWPL, 5),
                                                ("TMA", "F1", SECOND_NO_MWPL, 5)]})
    run(paths, D13)
    with open_store(paths) as store:
        assert row7_refusals(store, D13) == [
            (SECOND_NO_MWPL, "no MWPL in today's combineoi; 1 check not made"),
            (NO_MWPL, "no MWPL in today's combineoi; 2 checks not made")]


def test_an_mwpl_cut_is_named_from_yesterdays_file_not_todays(tmp_path):
    # The window's MWPL is 1,000,000 every day, so only a changed D-1 file tells the two apart.
    paths = row7_paths(tmp_path)
    rows = [dict(r, mwpl="1200000") if r["symbol"] == "QUIETCO" else r
            for r in window_rows_by_day()[D13]]
    paths.combineoi(D13).unlink()
    build_combineoi(paths.data, D13, rows)
    run(paths, D14)
    with open_store(paths) as store:
        h1 = check(store, D14, "H1", CLIENT_LIMIT)
        assert h1.cause is LimitCause.PASSIVE
        assert h1.reason.endswith("MWPL cut from 1200000 to 1000000 lowered the limit")


def test_a_non_reference_error_while_loading_fails_the_run(tmp_path, monkeypatch):
    # Assumes the runner imports load_reference by name.
    paths = row7_paths(tmp_path)

    def boom(*args, **kwargs):
        raise ValueError("not a reference data error")

    monkeypatch.setattr(runner, "load_reference", boom)
    assert_failed_and_rolled_back(paths, D13, ValueError)


# -- Row7Outcome refuses what cannot be true ------------------------------------------------

def a_refusal(subject="", *, day=D13, stage=RefusalStage.ROW7):
    return Refusal(day, stage, subject, "a reason")


PASSED = EntityLimitCheck(
    trade_date=D13, holder_id="H1", isin=QUIET, limit_key=CLIENT_LIMIT, accounts=(("TMA", "C1"),),
    gross_futeq=Decimal(90_000), mwpl=1_000_000, limit_shares=Decimal("100000.00"),
    excess_shares=Decimal(0), permitted=True, cause=None, reason="within limit")
NOT_CHECKED = NotChecked(D13, "H1", NO_MWPL, CLIENT_LIMIT, "no MWPL for this scrip")
CHECKED_RESULT = EntityLimitResult((PASSED,), (NOT_CHECKED,))
EMPTY_RESULT = EntityLimitResult(())


def test_the_three_valid_shapes_construct():
    Row7Outcome(D13, Row7Status.REFUSED, None, (a_refusal(),))
    Row7Outcome(D13, Row7Status.FLAT, EMPTY_RESULT)
    Row7Outcome(D13, Row7Status.CHECKED, CHECKED_RESULT, (a_refusal(NO_MWPL),))
    Row7Outcome(D13, Row7Status.CHECKED, EntityLimitResult((PASSED,)))


@pytest.mark.parametrize("status,result,refusals,error,match", [
    # types
    ("checked", CHECKED_RESULT, [a_refusal(NO_MWPL)], TypeError, "must be a tuple"),
    ("refused", None, ("not a refusal",), TypeError, "not a Refusal"),
    ("checked", (PASSED,), (), TypeError, "must be an EntityLimitResult"),
    # every refusal is row 7's, and today's
    ("refused", None, (a_refusal(stage=RefusalStage.ROW6),), ValueError, "does not belong to row 7"),
    ("refused", None, (a_refusal(day=D12),), ValueError, "a refusal is dated 2026-10-12"),
    ("checked", EntityLimitResult((dataclasses.replace(PASSED, trade_date=D12),)), (),
     ValueError, "the result is for"),
    # REFUSED
    ("refused", EMPTY_RESULT, (a_refusal(),), ValueError, "has no result"),
    ("refused", None, (), ValueError, "exactly one whole-stage refusal"),
    ("refused", None, (a_refusal(NO_MWPL),), ValueError, "exactly one whole-stage refusal"),
    ("refused", None, (a_refusal(), a_refusal(NO_MWPL)), ValueError, "exactly one whole-stage"),
    # FLAT
    ("flat", None, (), ValueError, "still has a result"),
    ("flat", CHECKED_RESULT, (), ValueError, "a flat day has 1 check"),
    ("flat", EMPTY_RESULT, (a_refusal(),), ValueError, "a flat day has 1 refusal"),
    # CHECKED
    ("checked", None, (), ValueError, "needs its result"),
    ("checked", EMPTY_RESULT, (), ValueError, "the result is empty"),
    ("checked", CHECKED_RESULT, (a_refusal(NO_MWPL), a_refusal()), ValueError,
     "cannot carry a whole-stage refusal"),
    ("checked", CHECKED_RESULT, (a_refusal(NO_MWPL), a_refusal(NO_MWPL)), ValueError, "duplicates"),
    ("checked", CHECKED_RESULT, (), ValueError, r"Not checked but not refused: \['INE000Z01010'\]"),
    ("checked", EntityLimitResult((PASSED,)), (a_refusal(NO_MWPL),), ValueError,
     r"Refused but nothing not checked: \['INE000Z01010'\]"),
])
def test_an_outcome_that_disagrees_with_itself_is_refused(status, result, refusals, error, match):
    with pytest.raises(error, match=match):
        Row7Outcome(D13, Row7Status(status), result, refusals)


def test_a_status_that_is_not_a_row7_status_is_refused():
    with pytest.raises(TypeError, match="must be a Row7Status"):
        Row7Outcome(D13, "checked", CHECKED_RESULT, (a_refusal(NO_MWPL),))


# ---------------------------------------------------------------- added with the review fixes

def test_a_reference_error_from_the_factors_fails_the_run_not_as_an_unknown_account(
        tmp_path, monkeypatch):
    # 14 Oct has no ban list, so row 6 refuses before it loads any factors: only row 7 calls
    # load_delta_factors() here. Inside the check's try, this would be stored as "position in
    # unknown account", which would not be true.
    paths = row7_paths(tmp_path)

    def bad_factors(*args, **kwargs):
        raise ReferenceDataError("raised while reading the delta file")

    monkeypatch.setattr(runner, "load_delta_factors", bad_factors)
    assert_failed_and_rolled_back(paths, D14, ReferenceDataError)


def test_a_not_checked_reason_the_stage_has_no_wording_for_fails_the_run(tmp_path, monkeypatch):
    paths = row7_paths(tmp_path)
    entry = NotChecked(D13, "H1", QUIET, CLIENT_LIMIT, "some other reason")
    monkeypatch.setattr(runner, "check_entity_limit",
                        lambda *a, **kw: EntityLimitResult(checks=(), not_checked=(entry,)))
    assert_failed_and_rolled_back(paths, D13, RuntimeError)
