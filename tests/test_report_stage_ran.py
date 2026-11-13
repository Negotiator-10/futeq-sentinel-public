"""Sections 3 and 4 read the stage markers (#023 items 7 and 8). Layout, by Claude, 13 Nov 2026.

Written before the report change and before `Row6Outcome`, so this file fails at import until
both land. Every day is rendered through the runner; a contradiction is made by editing the
store by raw SQL afterwards, since no code path may write one.

The report's rule, from item 8: for a stage with a marker, the stored rows are rebuilt into
`Row6Outcome` or `Row7Outcome`, and if `__post_init__` refuses, its message is the
"Inconsistent:" text. The rebuild passes the marker's status, the stage's own refusals, and
its rows as they are, except that a REFUSED marker with no rows passes None, which is what a
refused outcome holds. So each expected message below is made by building the same outcome
here, and the test does not depend on how the outcome words it.

The wording the report adds (layout, mine):

    no marker, no rows         Not run: no record that this stage ran.
    row 6 FLAT                 Nothing held: the book was flat yesterday and today.
    row 7 FLAT                 Nothing held: the book was flat today.
    row 6 CHECKED, no checks   None: no account held a banned scrip yesterday or today, so
                               there was nothing to check.
"""

from __future__ import annotations

import pytest

from sentinel import report
from sentinel.engine import EntityLimitResult
from sentinel.runner import Row6Outcome, Row7Outcome, StageStatus
from sentinel.store import RefusalStage
from tests.test_report import stand_ins  # noqa: F401  (a fixture, used by name)
from tests.test_runner import open_store
from tests.test_runner_row6 import CLOSE_OUT, FLAT_BOTH, paths_for
from tests.test_runner_row7 import D13, run

NOT_RUN = "Not run: no record that this stage ran."
ROW6_FLAT = "Nothing held: the book was flat yesterday and today."
ROW7_FLAT = "Nothing held: the book was flat today."
ROW6_NONE_HELD = ("None: no account held a banned scrip yesterday or today, so there was "
                  "nothing to check.")
TOMORROW = "Forecast for 2026-10-14: ENTRYCO, STICKYCO."


def rendered(tmp_path, book=None, *, missing_book=False, sql=()):
    paths = paths_for(tmp_path, book=book)
    if missing_book:
        paths.book.unlink()
    run(paths, D13)
    with open_store(paths) as store:
        for statement in sql:
            store._conn.execute(statement)
    return paths, report.render(D13, paths)


def section(text, number):
    heading = {1: "## 1. Refusals", 3: "## 3. Row 6 breaches", 4: "## 4. Row 7: entity limits",
               5: "## 5. Tomorrow's ban"}[number]
    return text.split(heading)[1].split("\n## ")[0]


def refused_message(make) -> str:
    with pytest.raises(ValueError) as err:
        make()
    return str(err.value)


# SQL that removes a stage's marker and rows, leaving a day that looks as if the stage never ran.
FORGET_ROW6 = ("DELETE FROM stage_ran WHERE stage = 'row6'", "DELETE FROM row6_check",
               "DELETE FROM refusal WHERE stage = 'row6'")
FORGET_ROW7 = ("DELETE FROM stage_ran WHERE stage = 'row7'", "DELETE FROM row7_check",
               "DELETE FROM row7_not_checked", "DELETE FROM refusal WHERE stage = 'row7'")


# -- not run (item 7) ----------------------------------------------------------------------

def test_no_marker_and_no_rows_is_not_run_in_both_sections(tmp_path, stand_ins):
    _, text = rendered(tmp_path, sql=FORGET_ROW6 + FORGET_ROW7)
    assert NOT_RUN in section(text, 3) and NOT_RUN in section(text, 4)
    for n in (3, 4):
        assert "None" not in section(text, n) and "Nothing held" not in section(text, n)


def test_a_stage_not_run_is_named_at_the_top_and_every_stage_ran_is_not_claimed(tmp_path,
                                                                               stand_ins):
    _, text = rendered(tmp_path, sql=FORGET_ROW6)
    top = section(text, 1)
    assert "**row6** not run" in top
    assert "Every stage ran" not in top
    assert "**row7**" not in top                          # row 7 ran and is consistent


def test_with_both_markers_and_no_refusals_every_stage_ran(tmp_path, stand_ins):
    _, text = rendered(tmp_path)                          # QUIETCO only: row 6 has zero checks
    assert "None. Every stage ran." in section(text, 1)


# -- what each marker says (items 3 and 4) -----------------------------------------------

def test_a_flat_marker_says_nothing_held_in_both_sections(tmp_path, stand_ins):
    _, text = rendered(tmp_path, FLAT_BOTH)
    assert ROW6_FLAT in section(text, 3)
    assert ROW7_FLAT in section(text, 4)
    for n in (3, 4):
        assert "None:" not in section(text, n) and "Not run" not in section(text, n)


def test_row_6_checked_with_no_checks_says_none_was_held_not_nothing_held(tmp_path, stand_ins):
    _, text = rendered(tmp_path)
    row6 = section(text, 3)
    assert ROW6_NONE_HELD in row6
    assert "Nothing held" not in row6 and "0 account-scrip" not in row6


def test_a_close_out_is_counted_in_row_6_while_row_7_is_flat(tmp_path, stand_ins):
    _, text = rendered(tmp_path, CLOSE_OUT)
    assert "None: 1 account-scrip check(s), every one permitted." in section(text, 3)
    assert ROW7_FLAT in section(text, 4)


def test_a_refused_marker_still_says_refused_and_why(tmp_path, stand_ins):
    _, text = rendered(tmp_path, missing_book=True)
    assert "Refused: missing: positions.csv." in section(text, 3)
    assert "Refused: missing: positions.csv" in section(text, 4)


# -- inconsistent (items 7 and 8): shown, never resolved, and the report goes on ---------

def assert_inconsistent(text, number, stage, message):
    body = section(text, number)
    assert f"Inconsistent: {message}" in body
    assert "None" not in body and "Nothing held" not in body and "Refused" not in body
    assert "|---" not in body                             # no side picked: no table of rows
    assert f"**{stage}** inconsistent: {message}" in section(text, 1)
    assert TOMORROW in section(text, 5)                   # the report does not stop


def test_row_6_rows_with_no_marker_are_inconsistent_not_old(tmp_path, stand_ins):
    _, text = rendered(tmp_path, CLOSE_OUT, sql=["DELETE FROM stage_ran WHERE stage = 'row6'"])
    assert_inconsistent(text, 3, "row6",
                        "no stage_ran marker, but 1 check row(s) and 0 refusal(s) are stored")


def test_row_7_rows_with_no_marker_are_inconsistent(tmp_path, stand_ins):
    _, text = rendered(tmp_path, sql=["DELETE FROM stage_ran WHERE stage = 'row7'"])
    assert_inconsistent(text, 4, "row7",
                        "no stage_ran marker, but 3 check row(s) and 0 refusal(s) are stored")


def test_a_refusal_with_no_marker_is_inconsistent(tmp_path, stand_ins):
    _, text = rendered(tmp_path, missing_book=True,
                       sql=["DELETE FROM stage_ran WHERE stage = 'row6'"])
    assert_inconsistent(text, 3, "row6",
                        "no stage_ran marker, but 0 check row(s) and 1 refusal(s) are stored")


def test_a_flat_row_6_marker_with_a_check_row_is_inconsistent(tmp_path, stand_ins):
    paths, text = rendered(tmp_path, CLOSE_OUT,
                           sql=["UPDATE stage_ran SET status = 'flat' WHERE stage = 'row6'"])
    with open_store(paths) as store:
        checks = store.row6_checks(D13)
    message = refused_message(lambda: Row6Outcome(D13, StageStatus.FLAT, checks))
    assert_inconsistent(text, 3, "row6", message)


def test_a_refused_row_6_marker_with_no_refusal_is_inconsistent(tmp_path, stand_ins):
    _, text = rendered(tmp_path, sql=["UPDATE stage_ran SET status = 'refused' WHERE stage = 'row6'"])
    message = refused_message(lambda: Row6Outcome(D13, StageStatus.REFUSED, None))
    assert_inconsistent(text, 3, "row6", message)


def test_a_checked_row_6_marker_with_a_whole_stage_refusal_is_inconsistent(tmp_path, stand_ins):
    paths, text = rendered(tmp_path, missing_book=True,
                           sql=["UPDATE stage_ran SET status = 'checked' WHERE stage = 'row6'"])
    with open_store(paths) as store:
        refusals = tuple(r for r in store.refusals(D13) if r.stage is RefusalStage.ROW6)
    message = refused_message(lambda: Row6Outcome(D13, StageStatus.CHECKED, (), refusals))
    assert_inconsistent(text, 3, "row6", message)


def test_a_checked_row_7_marker_with_no_rows_is_inconsistent(tmp_path, stand_ins):
    _, text = rendered(tmp_path, sql=["DELETE FROM row7_check"])
    message = refused_message(
        lambda: Row7Outcome(D13, StageStatus.CHECKED, EntityLimitResult(()), ()))
    assert_inconsistent(text, 4, "row7", message)


def test_a_flat_row_7_marker_with_check_rows_is_inconsistent(tmp_path, stand_ins):
    paths, text = rendered(tmp_path,
                           sql=["UPDATE stage_ran SET status = 'flat' WHERE stage = 'row7'"])
    with open_store(paths) as store:
        result = store.row7_result(D13)
    message = refused_message(lambda: Row7Outcome(D13, StageStatus.FLAT, result))
    assert_inconsistent(text, 4, "row7", message)


def test_one_stage_inconsistent_leaves_the_other_reported(tmp_path, stand_ins):
    _, text = rendered(tmp_path, CLOSE_OUT, sql=["DELETE FROM stage_ran WHERE stage = 'row6'"])
    assert ROW7_FLAT in section(text, 4)
