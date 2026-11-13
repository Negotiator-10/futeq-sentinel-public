"""Row 6's outcome and the stage markers in the runner: #023, on the synthetic window.

Written by Claude on 13 Nov 2026, before `Row6Outcome` exists, so Chintamani writes it, and the
`_row6()` and `write_day()` changes, against them. The whole file fails at import until
`Row6Outcome` is in `sentinel.runner`.

Two conventions are taken from `Row7Outcome`, since #023 item 5 does not name them: a wrong
type raises TypeError, and an outcome that disagrees with itself raises ValueError. The
messages are not asserted, so the wording is free. Each invalid case breaks exactly one rule,
so a case cannot pass because some other check raised.

The setup is `test_runner_row7.py`'s: holders H1 (client, TMA/C1) and TMA (TMA/PRO), lot size
1,000, one October future at factor 1. On 12 and 13 Oct HOLDCO is banned and QUIETCO is not;
14 Oct has no ban list, by design. Row 6 on 13 Oct reads the books for 12 and 13 Oct.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from decimal import Decimal

import pytest

from sentinel import runner
from sentinel.book import BookError
from sentinel.calendar import load_calendar
from sentinel.engine import ReductionCheck
from sentinel.rules import load_rules
from sentinel.runlock import RunLock
from sentinel.runner import DayResults, Row6Outcome, StageStatus
from sentinel.store import BanStateStore, Refusal, RefusalStage, RunOutcome, StoreError
from tests.test_runner import EMPTY_STATUS, isin_of, open_store
from tests.test_runner_row7 import (
    BOOK, D12, D13, D14, EXPIRY, LOT, QUIET, assert_failed_and_rolled_back, row7_paths, run,
)

HOLD = isin_of("HOLDCO")            # banned on 12 and 13 Oct
ROW6, ROW7 = RefusalStage.ROW6, RefusalStage.ROW7
CHECKED, FLAT, REFUSED = StageStatus.CHECKED, StageStatus.FLAT, StageStatus.REFUSED

FLAT_BOTH = {D12: "FLAT", D13: "FLAT"}
# Yesterday held a banned scrip; today is flat: one real check, a close-out (#023 item 3).
CLOSE_OUT = {D12: [("TMA", "C1", QUIET, 110), ("TMA", "C1", HOLD, 5)], D13: "FLAT"}


def write_deltas_with_holdco(paths) -> None:
    """QUIETCO's and HOLDCO's October futures at exactly 1, for every window day."""
    for day in (D12, D13, D14):
        paths.delta(day).write_text(
            "Date,Symbol,Expiry day,Strike Price,Option Type,Delta Factor\n"
            f"{day:%d-%m-%Y},QUIETCO,{EXPIRY:%d-%m-%Y},0,FF,1.00000000\n"
            f"{day:%d-%m-%Y},HOLDCO,{EXPIRY:%d-%m-%Y},0,FF,1.00000000\n",
            encoding="utf-8")


def paths_for(tmp_path, book=None):
    paths = row7_paths(tmp_path, book=book)
    write_deltas_with_holdco(paths)
    return paths


def markers(paths, day):
    with open_store(paths) as store:
        return store.stages_ran(day)


def row6_refusals(paths, day):
    with open_store(paths) as store:
        return [(r.subject, r.reason) for r in store.refusals(day) if r.stage is ROW6]


def row6_checks(paths, day):
    with open_store(paths) as store:
        return store.row6_checks(day)


# -- Row6Outcome refuses what cannot be true (#023 item 5) ---------------------------------

def a_refusal(subject="", *, day=D13, stage=ROW6):
    return Refusal(day, stage, subject, "a reason")


A_CHECK = ReductionCheck(
    trade_date=D13, tm="TMA", ucc="C1", isin=HOLD, yesterday_delta=Decimal(5000),
    baseline=Decimal(5000), today_delta=Decimal(0), permitted=True,
    reason="held or reduced toward zero")


def test_the_valid_shapes_construct():
    Row6Outcome(D13, REFUSED, None, (a_refusal(),))
    Row6Outcome(D13, FLAT, ())
    Row6Outcome(D13, CHECKED, ())                       # item 4: an empty CHECKED is normal
    Row6Outcome(D13, CHECKED, (A_CHECK,))
    assert Row6Outcome(D13, FLAT, ()).refusals == ()   # refusals defaults to ()


@pytest.mark.parametrize("status,checks,refusals", [
    ("checked", (A_CHECK,), ()),                        # a status that is not a StageStatus
    (CHECKED, [A_CHECK], ()),                           # a list could still be changed
    (CHECKED, ("not a check",), ()),
    (REFUSED, None, [a_refusal()]),
    (REFUSED, None, ("not a refusal",)),
])
def test_a_wrong_type_is_refused(status, checks, refusals):
    with pytest.raises(TypeError):
        Row6Outcome(D13, status, checks, refusals)


@pytest.mark.parametrize("status,checks,refusals", [
    # every refusal is row 6's, and today's; every check is today's
    (REFUSED, None, (a_refusal(stage=ROW7),)),
    (REFUSED, None, (a_refusal(day=D12),)),
    (CHECKED, (dataclasses.replace(A_CHECK, trade_date=D12),), ()),
    # REFUSED: checks None, exactly one whole-stage refusal
    (REFUSED, (), (a_refusal(),)),
    (REFUSED, (A_CHECK,), (a_refusal(),)),
    (REFUSED, None, ()),
    (REFUSED, None, (a_refusal(HOLD),)),
    (REFUSED, None, (a_refusal(), a_refusal(HOLD))),
    # FLAT: checks (), no refusals
    (FLAT, None, ()),
    (FLAT, (A_CHECK,), ()),
    (FLAT, (), (a_refusal(),)),
    # CHECKED: a tuple, empty allowed, no refusals - row 6 has no per-scrip refusals
    (CHECKED, None, ()),
    (CHECKED, (A_CHECK,), (a_refusal(),)),
    (CHECKED, (A_CHECK,), (a_refusal(HOLD),)),
    (CHECKED, (), (a_refusal(HOLD),)),
])
def test_an_outcome_that_disagrees_with_itself_is_refused(status, checks, refusals):
    with pytest.raises(ValueError):
        Row6Outcome(D13, status, checks, refusals)


def test_day_results_carries_an_outcome_not_a_tuple():
    assert DayResults().row6 is None                    # None = not run, as for row 7
    assert not hasattr(DayResults(), "row6_checks")


# -- the stage's outcome, through the runner (#023 items 3 and 4) --------------------------

def test_positions_in_no_banned_scrip_are_checked_with_zero_checks(tmp_path):
    paths = paths_for(tmp_path)                          # QUIETCO only: never banned
    run(paths, D13)
    assert markers(paths, D13) == {ROW6: CHECKED, ROW7: CHECKED}
    assert row6_checks(paths, D13) == ()                # item 4: a marker and no check rows
    assert row6_refusals(paths, D13) == []


def test_nothing_banned_on_d_is_checked_with_zero_checks(tmp_path):
    paths = paths_for(tmp_path, book={D12: [("TMA", "C1", HOLD, 5)],
                                      D13: [("TMA", "C1", HOLD, 5)]})
    paths.ban_list(D13).write_text("Securities in Ban For Trade Date 13-OCT-2026:\n",
                                   encoding="utf-8")
    run(paths, D13)
    assert markers(paths, D13)[ROW6] is CHECKED
    assert row6_checks(paths, D13) == ()


def test_both_books_flat_is_flat(tmp_path):
    paths = paths_for(tmp_path, book=FLAT_BOTH)
    run(paths, D13)
    assert markers(paths, D13) == {ROW6: FLAT, ROW7: FLAT}
    assert row6_checks(paths, D13) == () and row6_refusals(paths, D13) == []


def test_a_flat_today_after_a_yesterday_with_no_banned_scrip_is_checked_not_flat(tmp_path):
    """Item 3's row 6 case: D-1 was not flat, so row 6 is not FLAT, and it held nothing
    banned, so there is nothing to check. Row 7 checks today only, so it is FLAT."""
    paths = paths_for(tmp_path, book={D12: BOOK[D12], D13: "FLAT"})
    run(paths, D13)
    assert markers(paths, D13) == {ROW6: CHECKED, ROW7: FLAT}
    assert row6_checks(paths, D13) == ()


def test_a_close_out_to_a_flat_today_is_checked_with_its_check(tmp_path):
    paths = paths_for(tmp_path, book=CLOSE_OUT)
    run(paths, D13)
    assert markers(paths, D13) == {ROW6: CHECKED, ROW7: FLAT}
    [check] = row6_checks(paths, D13)
    assert (check.tm, check.ucc, check.isin) == ("TMA", "C1", HOLD)
    assert check.baseline == Decimal(5 * LOT) and check.today_delta == 0
    assert check.permitted


def test_a_flat_day_with_no_ban_list_is_refused_not_flat(tmp_path):
    """Item 3: FLAT needs the stage's inputs first. 14 Oct has no ban list."""
    paths = paths_for(tmp_path, book={D13: "FLAT", D14: "FLAT"})
    run(paths, D14)
    assert markers(paths, D14) == {ROW6: REFUSED, ROW7: FLAT}
    assert row6_refusals(paths, D14) == [("", "D's official ban state is missing")]


def test_a_refused_stage_writes_a_refused_marker(tmp_path):
    paths = paths_for(tmp_path)
    paths.book.unlink()
    run(paths, D13)
    assert markers(paths, D13) == {ROW6: REFUSED, ROW7: REFUSED}
    assert row6_refusals(paths, D13) == [("", "missing: positions.csv")]


def test_on_a_flat_day_the_check_still_runs(tmp_path, monkeypatch):
    """The check's date checks (yesterday is the previous trading day, the factors are for the
    books' dates) must run on a flat day too, so FLAT is decided after the call."""
    paths = paths_for(tmp_path, book=FLAT_BOTH)
    calls = []
    real = runner.check_ban_period_reduction

    def spy(**kwargs):
        calls.append(kwargs["today"].trade_date)
        return real(**kwargs)

    monkeypatch.setattr(runner, "check_ban_period_reduction", spy)
    run(paths, D13)
    assert calls == [D13]


def test_a_flat_day_whose_check_fails_its_date_checks_fails_the_run(tmp_path, monkeypatch):
    paths = paths_for(tmp_path, book=FLAT_BOTH)

    def stale(**kwargs):
        raise BookError("yesterday's book is not the previous trading day's")

    monkeypatch.setattr(runner, "check_ban_period_reduction", stale)
    assert_failed_and_rolled_back(paths, D13, BookError)
    assert markers(paths, D13) == {}


def test_a_flat_day_whose_check_returns_a_check_fails_the_run(tmp_path, monkeypatch):
    """Item 3: a flat stage whose check returns any entry is a bug, and the run fails."""
    paths = paths_for(tmp_path, book=FLAT_BOTH)
    monkeypatch.setattr(runner, "check_ban_period_reduction", lambda **kw: (A_CHECK,))
    assert_failed_and_rolled_back(paths, D13, Exception)
    assert markers(paths, D13) == {}


# -- write_day(): the marker comes from the outcome, never unconditionally (item 2) --------

def compute(paths, day):
    calendar = load_calendar(paths.calendar)
    return calendar, runner.compute_day(paths, day, calendar, load_rules(paths.rules, warn=False))


def write(paths, day, calendar, results):
    with RunLock(paths.lock) as lock, BanStateStore(paths.store, calendar) as store:
        r = store.start_run(day, lock=lock, input_checksums={}, code_version="test",
                            dirty=False, rules_checksum="0" * 64, calendar_checksum="0" * 64,
                            rules_status=EMPTY_STATUS)
        runner.write_day(store, day, r.run_id, results)
        store.finish_run(r.run_id, RunOutcome.COMPLETED, lock=lock)


@pytest.mark.parametrize("book,status", [(None, CHECKED), (FLAT_BOTH, FLAT), ("missing", REFUSED)])
def test_compute_day_returns_row_6s_outcome(tmp_path, book, status):
    paths = paths_for(tmp_path, book=None if book == "missing" else book)
    if book == "missing":
        paths.book.unlink()
    _, results = compute(paths, D13)
    assert isinstance(results.row6, Row6Outcome)
    assert results.row6.status is status and results.row6.trade_date == D13


def test_row_6s_refusals_travel_in_its_outcome_not_the_shared_list(tmp_path):
    paths = paths_for(tmp_path)
    paths.book.unlink()
    _, results = compute(paths, D13)
    assert [r.stage for r in results.row6.refusals] == [ROW6]
    assert all(r.stage is not ROW6 for r in results.refusals)


@pytest.mark.parametrize("skipped", ["row6", "row7"])
def test_a_stage_that_did_not_run_leaves_no_marker(tmp_path, skipped):
    paths = paths_for(tmp_path, book=CLOSE_OUT)
    calendar, results = compute(paths, D13)
    setattr(results, skipped, None)
    write(paths, D13, calendar, results)
    stage = RefusalStage(skipped)
    ran = markers(paths, D13)
    assert stage not in ran and len(ran) == 1
    with open_store(paths) as store:                     # and nothing else of that stage
        assert all(r.stage is not stage for r in store.refusals(D13))
        if skipped == "row6":
            assert store.row6_checks(D13) == ()
        else:
            assert store.row7_result(D13).checks == ()


def test_a_refused_stage_stores_its_refusal_and_its_marker_together(tmp_path):
    paths = paths_for(tmp_path)
    paths.book.unlink()
    calendar, results = compute(paths, D13)
    write(paths, D13, calendar, results)
    assert markers(paths, D13)[ROW6] is REFUSED
    assert row6_refusals(paths, D13) == [("", "missing: positions.csv")]


# -- re-runs (item 6) --------------------------------------------------------------------

def test_an_identical_rerun_keeps_the_markers(tmp_path):
    paths = paths_for(tmp_path, book=CLOSE_OUT)
    run(paths, D13)
    before = markers(paths, D13)
    run(paths, D13)
    assert markers(paths, D13) == before


def test_a_rerun_from_refused_to_checked_fails_loudly_and_leaves_the_day(tmp_path):
    """#022's hole: the first run refused for a missing book; the book then arrived. Before
    #023 the re-run stored the checks beside the old refusal. Now it fails and stores nothing."""
    paths = paths_for(tmp_path, book=CLOSE_OUT)
    book_text = paths.book.read_text(encoding="utf-8")
    paths.book.unlink()
    run(paths, D13)
    assert markers(paths, D13) == {ROW6: REFUSED, ROW7: REFUSED}

    paths.book.write_text(book_text, encoding="utf-8")
    with pytest.raises(StoreError, match=r"row[67] was refused, now (checked|flat)"):
        runner.run_day(D13, paths)
    with open_store(paths) as store:
        assert store.runs_for(D13)[-1].outcome is RunOutcome.FAILED
        assert store.stages_ran(D13) == {ROW6: REFUSED, ROW7: REFUSED}
        assert store.row6_checks(D13) == ()              # the close-out was not stored
