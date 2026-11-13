"""The `stage_ran` table: its writer, its reader and the guard at open (#023). Plumbing, by
Claude, 13 Nov 2026. These pass on their own; they do not need Row6Outcome.

Each test defends one item of #023:

* one marker per (day, stage), only row 6 and row 7, only the three statuses (item 1);
* written only inside the day transaction, and rolled back with it (item 1, #019 decision 3);
* an identical re-run is a no-op, keeping the first run's attribution (item 1);
* a re-run that changes the status fails, naming the stage and both statuses (item 6);
* no marker reads as nothing, never as a status (items 2 and 7);
* a store whose runs predate the table is refused at open, and stays refused (item 7).
"""

from __future__ import annotations

import sqlite3

import pytest

from sentinel.calendar import load_calendar
from sentinel.store import (
    MARKED_STAGES, BanStateStore, RefusalStage, RunOutcome, StageStatus, StoreError,
)
from tests.test_runstore import WED4, WED11, lock, start, store  # noqa: F401  (fixtures by name)

ROW6, ROW7 = RefusalStage.ROW6, RefusalStage.ROW7


def mark(store, run, *markers, day=WED4):
    with store.day_transaction(day, run.run_id):
        for stage, status in markers:
            store.record_stage_ran(day, stage, status)


def test_the_marked_stages_are_row_6_and_row_7():
    assert MARKED_STAGES == (ROW6, ROW7)
    assert [s.value for s in StageStatus] == ["checked", "flat", "refused"]


@pytest.mark.parametrize("status", list(StageStatus))
def test_each_status_reads_back_for_each_stage(store, lock, status):
    run = start(store, lock)
    mark(store, run, (ROW6, status), (ROW7, status))
    assert store.stages_ran(WED4) == {ROW6: status, ROW7: status}


def test_the_two_stages_are_independent(store, lock):
    run = start(store, lock)
    mark(store, run, (ROW6, StageStatus.REFUSED), (ROW7, StageStatus.FLAT))
    assert store.stages_ran(WED4) == {ROW6: StageStatus.REFUSED, ROW7: StageStatus.FLAT}


def test_no_marker_is_an_empty_dict_not_a_status(store, lock):
    run = start(store, lock)
    mark(store, run, (ROW7, StageStatus.CHECKED))
    assert ROW6 not in store.stages_ran(WED4)            # row 6 not run: absent, not a value
    assert store.stages_ran(WED11) == {}                 # a day never run


def test_a_marker_is_written_only_inside_the_day_transaction(store, lock):
    start(store, lock)
    with pytest.raises(StoreError, match="only inside day_transaction"):
        store.record_stage_ran(WED4, ROW6, StageStatus.CHECKED)
    assert store.stages_ran(WED4) == {}


def test_a_marker_for_another_day_is_refused_inside_the_transaction(store, lock):
    run = start(store, lock)
    with store.day_transaction(WED4, run.run_id):
        with pytest.raises(StoreError, match="not 2026-11-11"):
            store.record_stage_ran(WED11, ROW6, StageStatus.CHECKED)


def test_a_marker_rolls_back_with_the_day(store, lock):
    run = start(store, lock)
    with pytest.raises(RuntimeError):
        with store.day_transaction(WED4, run.run_id):
            store.record_stage_ran(WED4, ROW6, StageStatus.FLAT)
            raise RuntimeError("simulated crash after the marker")
    assert store.stages_ran(WED4) == {}


@pytest.mark.parametrize("stage", [s for s in RefusalStage if s not in MARKED_STAGES])
def test_only_row_6_and_row_7_write_a_marker(store, lock, stage):
    run = start(store, lock)
    with store.day_transaction(WED4, run.run_id):
        with pytest.raises(StoreError, match="not a stage that writes a marker"):
            store.record_stage_ran(WED4, stage, StageStatus.CHECKED)


@pytest.mark.parametrize("stage,status,match", [
    ("row6", StageStatus.CHECKED, "not a stage that writes a marker"),
    (ROW6, "checked", "must be a StageStatus, not str"),
    (ROW6, None, "must be a StageStatus, not NoneType"),
])
def test_a_stage_or_status_of_the_wrong_type_is_refused(store, lock, stage, status, match):
    run = start(store, lock)
    with store.day_transaction(WED4, run.run_id):
        with pytest.raises(StoreError, match=match):
            store.record_stage_ran(WED4, stage, status)


def test_an_identical_rerun_is_a_no_op_and_keeps_the_first_runs_attribution(store, lock):
    first = start(store, lock)
    mark(store, first, (ROW6, StageStatus.CHECKED))
    store.finish_run(first.run_id, RunOutcome.COMPLETED, lock=lock)
    second = start(store, lock)
    with store.day_transaction(WED4, second.run_id):
        result = store.record_stage_ran(WED4, ROW6, StageStatus.CHECKED)
    assert (result.written, result.unchanged) == (0, 1)
    [row] = store._conn.execute("SELECT run_id FROM stage_ran").fetchall()
    assert row["run_id"] == first.run_id


@pytest.mark.parametrize("before,after", [
    (StageStatus.REFUSED, StageStatus.CHECKED),       # #022's hole: the missing file arrived
    (StageStatus.CHECKED, StageStatus.REFUSED),
    (StageStatus.FLAT, StageStatus.CHECKED),
    (StageStatus.REFUSED, StageStatus.FLAT),
])
def test_a_rerun_that_changes_the_status_fails_and_says_what_to_do(store, lock, before, after):
    first = start(store, lock)
    mark(store, first, (ROW7, before))
    store.finish_run(first.run_id, RunOutcome.COMPLETED, lock=lock)
    second = start(store, lock)
    with pytest.raises(StoreError) as err:
        mark(store, second, (ROW7, after))
    message = str(err.value)
    assert f"row7 was {before.value}, now {after.value}" in message
    assert "fresh store" in message and "supersede" in message
    assert store.stages_ran(WED4) == {ROW7: before}      # the day is as the first run left it


def test_the_schema_holds_the_stage_and_status_even_by_raw_sql(store, lock):
    run = start(store, lock)
    for stage, status in (("forecast", "checked"), ("row6", "skipped"), ("row6", "")):
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            store._conn.execute(
                "INSERT INTO stage_ran VALUES ('2026-11-04', ?, ?, ?, 'now')",
                (stage, status, run.run_id))


def test_one_marker_per_day_and_stage_even_by_raw_sql(store, lock):
    run = start(store, lock)
    mark(store, run, (ROW6, StageStatus.CHECKED))
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE|PRIMARY"):
        store._conn.execute(
            "INSERT INTO stage_ran VALUES ('2026-11-04', 'row6', 'flat', ?, 'now')", (run.run_id,))


def test_a_marker_names_a_run_that_exists(store):
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        store._conn.execute(
            "INSERT INTO stage_ran VALUES ('2026-11-04', 'row6', 'checked', 'no-such-run', 'now')")


# -- a store from before #023 -------------------------------------------------------------


def a_store_from_before_markers(path):
    """A current store with stage_ran dropped: what a store made on 12 Nov looks like."""
    BanStateStore(path, load_calendar()).close()
    con = sqlite3.connect(path)
    con.execute("DROP TABLE stage_ran")
    con.commit()
    con.close()


def test_a_store_whose_runs_predate_markers_is_refused_at_open(tmp_path):
    old = tmp_path / "old.sqlite"
    a_store_from_before_markers(old)
    with pytest.raises(StoreError, match="predate stage markers.*Move it aside"):
        BanStateStore(old, load_calendar())


def test_it_is_still_refused_on_the_second_open(tmp_path):
    """The guard runs before CREATE TABLE IF NOT EXISTS. Run after it, the first open would
    create an empty stage_ran, and the second would take the old store for a new one."""
    old = tmp_path / "old.sqlite"
    a_store_from_before_markers(old)
    for _ in range(2):
        with pytest.raises(StoreError, match="predate stage markers"):
            BanStateStore(old, load_calendar())
    con = sqlite3.connect(old)
    assert con.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'stage_ran'").fetchone() is None
    con.close()


def test_a_new_store_and_a_reopened_one_both_open(tmp_path):
    path = tmp_path / "new.sqlite"
    BanStateStore(path, load_calendar()).close()
    BanStateStore(path, load_calendar()).close()


def test_a_stage_ran_check_that_predates_a_stage_is_refused(tmp_path):
    """The day a third stage or a status is added, an older stage_ran CHECK would accept the
    open and fail on that stage's first marker, mid-transaction. Refused at open instead."""
    old = tmp_path / "old.sqlite"
    BanStateStore(old, load_calendar()).close()
    con = sqlite3.connect(old)
    con.executescript(
        "DROP TABLE stage_ran;"
        "CREATE TABLE stage_ran (trade_date TEXT NOT NULL, stage TEXT NOT NULL CHECK (stage IN"
        " ('row6')), status TEXT NOT NULL CHECK (status IN ('checked','flat','refused')),"
        " run_id TEXT NOT NULL, written_at TEXT NOT NULL,"
        " PRIMARY KEY (trade_date, stage)) WITHOUT ROWID;")
    con.close()
    with pytest.raises(StoreError, match="stage_ran table does not accept row7"):
        BanStateStore(old, load_calendar())
