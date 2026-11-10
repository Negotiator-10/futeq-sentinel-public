"""Tests for the runner's tables in `sentinel.store`, and for `sentinel.runlock`.

Each group defends one #019 decision:

* the run lock is released by the OS when its holder dies, which is what lets a RUNNING row with
  no lock held be read as a crash (decision 6) - tested with a real process, killed;
* the run log is written outside the day transaction and survives the day rolling back (4);
* a day's results commit together or not at all, and only through the transaction (3);
* inside run D's transaction, ban_state takes D's official state and D+1's forecast only;
* "missing", "refused" and "not run" are told apart by records, never by a NULL (5);
* an identical re-run is a no-op and a changed result refuses (11).
"""

from __future__ import annotations

import datetime as dt
import sqlite3
import subprocess
import sys
import textwrap
from decimal import Decimal
from pathlib import Path

import pytest

from sentinel.calendar import UnknownDateError, load_calendar
from sentinel.engine import ReductionCheck, reconcile
from sentinel.parsers import MwplRow
from sentinel.rules import load_rules
from sentinel.runlock import RunInProgressError, RunLock
from sentinel.store import (
    BanStateStore,
    Refusal,
    RefusalStage,
    RunOutcome,
    StoreError,
)

WED4, THU5, TUE10, WED11 = (dt.date(2026, 11, 4), dt.date(2026, 11, 5), dt.date(2026, 11, 10),
                            dt.date(2026, 11, 11))
SHA_A, SHA_B = "a" * 64, "b" * 64
HELD_ISIN = "INE000000027"
TESTCO_ISIN = "INE000000001"

# A synthetic held row, shaped like SAIL on 4 Nov: in ban, held in the band at 80.51%.
HELD_4NOV = MwplRow(trade_date=WED4, isin=HELD_ISIN, scrip_name="HELD CO", symbol="HELDCO",
                    mwpl=200_000_000, notional_oi=162_000_000, futeq_oi=161_020_000.618356,
                    no_fresh_positions=True, headroom_shares=None)
# A free scrip built so its headroom residual is exactly 0.75: 950,000 - 500,000.25 = 449,999.75.
TESTCO_4NOV = MwplRow(trade_date=WED4, isin=TESTCO_ISIN, scrip_name="TEST CO", symbol="TESTCO",
                      mwpl=1_000_000, notional_oi=600_000, futeq_oi=500_000.25,
                      no_fresh_positions=False, headroom_shares=449_999)
ROWS = (HELD_4NOV, TESTCO_4NOV)


@pytest.fixture(scope="module")
def rules():
    return load_rules(warn=False)


@pytest.fixture
def store(tmp_path):
    with BanStateStore(tmp_path / "s.sqlite", load_calendar()) as s:
        yield s


@pytest.fixture
def lock(tmp_path):
    with RunLock(tmp_path / "run.lock") as held:
        yield held


def start(store, lock, day=WED4, **overrides):
    kw = dict(lock=lock, input_checksums={"combineoi_04112026.zip": SHA_A,
                                          "fo_secban_04112026.csv": SHA_B},
              code_version="3c62801", dirty=False, rules_checksum=SHA_A, calendar_checksum=SHA_B,
              rules_status={"assumed": ["single_stock.ban.example_assumed"], "unverified": []})
    kw.update(overrides)
    return store.start_run(day, **kw)


def write_a_day(store, run, rules):
    """Everything a run on 4 Nov writes, in one transaction."""
    with store.day_transaction(WED4, run.run_id):
        store.record_official(WED4, {HELD_ISIN: ("HELDCO", True), TESTCO_ISIN: ("TESTCO", False)},
                              input_sha256=SHA_B)
        store.record_forecast(THU5, {HELD_ISIN: ("HELDCO", True), TESTCO_ISIN: ("TESTCO", False)},
                              input_sha256=SHA_A)
        store.record_measurements(ROWS, input_sha256=SHA_A)
        store.record_reconciliation(reconcile(ROWS, rules), input_sha256=SHA_A)
        store.record_row6_checks([ROW6])
        store.record_refusals([Refusal(WED4, RefusalStage.SCORE, "", "3 Nov forecast not stored")])


ROW6 = ReductionCheck(trade_date=WED4, tm="TMA", ucc="C001", isin=HELD_ISIN,
                      yesterday_delta=Decimal("1000"), baseline=Decimal("980.50000001"),
                      today_delta=Decimal("0"), permitted=True, reason="closed out from 980.5")


# -- the lock: released by the OS when its holder dies ------------------------------------


def test_a_second_lock_refuses_while_the_first_is_held(tmp_path):
    path = tmp_path / "run.lock"
    with RunLock(path):
        with pytest.raises(RunInProgressError, match="genuinely in progress"):
            RunLock(path).acquire()
    with RunLock(path) as again:          # released on exit, so it can be taken again
        assert again.held


def test_a_killed_holder_leaves_no_lock_behind(tmp_path):
    """The premise of decision 6, tested for real: kill the holder, and the lock is free.

    If this failed, a crashed run would block every later run until someone deleted a file,
    and "no lock held" could no longer be read as "the run crashed".
    """
    path = tmp_path / "run.lock"
    holder = tmp_path / "holder.py"
    holder.write_text(textwrap.dedent(f"""
        import sys, time
        sys.path.insert(0, {str(Path(__file__).parents[1] / "src")!r})
        from sentinel.runlock import RunLock
        lock = RunLock({str(path)!r}).acquire()
        print("locked", flush=True)
        time.sleep(120)
    """), encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-I", str(holder)], stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout.readline().strip() == "locked"
        with pytest.raises(RunInProgressError):
            RunLock(path).acquire()
        proc.kill()
        proc.wait(timeout=30)
        with RunLock(path) as taken:      # the kernel dropped it; nobody cleaned anything up
            assert taken.held
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=30)


# -- the run log -----------------------------------------------------------------------------


def test_starting_a_run_needs_the_lock_held(store, tmp_path):
    with pytest.raises(StoreError, match="needs the run lock held"):
        start(store, RunLock(tmp_path / "not-taken.lock"))


def test_a_run_starts_running_and_finishes_once(store, lock):
    run = start(store, lock)
    assert run.outcome is RunOutcome.RUNNING and run.finished_at is None
    assert run.input_checksums == {"combineoi_04112026.zip": SHA_A, "fo_secban_04112026.csv": SHA_B}
    done = store.finish_run(run.run_id, RunOutcome.COMPLETED, lock=lock)
    assert done.outcome is RunOutcome.COMPLETED and done.finished_at is not None
    with pytest.raises(StoreError, match="finishes once"):
        store.finish_run(run.run_id, RunOutcome.FAILED, "again", lock=lock)


def test_refused_and_failed_runs_must_say_why(store, lock):
    run = start(store, lock)
    for outcome in (RunOutcome.REFUSED, RunOutcome.FAILED):
        with pytest.raises(StoreError, match="must say why"):
            store.finish_run(run.run_id, outcome, "  ", lock=lock)
    for outcome in (RunOutcome.RUNNING, RunOutcome.ABANDONED):
        with pytest.raises(StoreError, match="COMPLETED, REFUSED or FAILED"):
            store.finish_run(run.run_id, outcome, "x", lock=lock)


def test_a_running_row_found_with_the_lock_free_is_abandoned(store, lock):
    """Decision 6: the first run 'crashed' (never finished); the next start supersedes it."""
    crashed = start(store, lock)
    other_day = start(store, lock, day=THU5)            # a different date is not touched
    fresh = start(store, lock)

    old = store.run(crashed.run_id)
    assert old.outcome is RunOutcome.ABANDONED
    assert old.superseded_by == fresh.run_id
    assert old.finished_at is not None and "crashed" in old.reason
    assert store.run(other_day.run_id).outcome is RunOutcome.RUNNING
    assert [r.outcome for r in store.runs_for(WED4)] == [RunOutcome.ABANDONED, RunOutcome.RUNNING]


def test_a_run_for_an_unknown_date_can_still_log_that_it_refused(store, lock):
    """The whole-run refusal has to be recordable, so start_run does not ask the calendar."""
    day = dt.date(2027, 1, 4)
    run = start(store, lock, day=day)
    store.finish_run(run.run_id, RunOutcome.REFUSED, "2027-01-04 is not in the verified calendar",
                     lock=lock)
    assert store.runs_for(day)[0].outcome is RunOutcome.REFUSED
    with pytest.raises(UnknownDateError):
        with store.day_transaction(day, run.run_id):
            pass


@pytest.mark.parametrize("override,match", [
    ({"input_checksums": {"combineoi_04112026.zip": "abc"}}, "not a sha256"),
    ({"rules_checksum": "x" * 64}, "rules_checksum"),
    ({"calendar_checksum": ""}, "calendar_checksum"),
    ({"code_version": " "}, "code_version is blank"),
])
def test_a_run_must_name_its_inputs_and_code(store, lock, override, match):
    with pytest.raises(StoreError, match=match):
        start(store, lock, **override)


def test_the_rules_status_is_recorded_as_keys_and_read_back(store, lock):
    """The report footer names the assumed and the refused rules from the run log."""
    run = start(store, lock, rules_status={"assumed": ["b.second", "a.first"],
                                           "unverified": ["c.refused"]})
    assert run.rules_status == {"assumed": ("a.first", "b.second"), "unverified": ("c.refused",)}
    assert store.runs_for(WED4)[0].rules_status == run.rules_status


def test_the_real_rules_status_round_trips(store, lock, rules):
    status = {"assumed": list(rules.assumed), "unverified": list(rules.unverified)}
    assert rules.assumed, "rules.yaml has assumed keys today; this test means nothing without them"
    run = start(store, lock, rules_status=status)
    assert run.rules_status["assumed"] == tuple(sorted(rules.assumed))
    assert run.rules_status["unverified"] == tuple(sorted(rules.unverified))


@pytest.mark.parametrize("status,match", [
    ({"assumed": []}, "exactly the lists"),
    ({"assumed": [], "unverified": [], "extra": []}, "exactly the lists"),
    ("assumed", "exactly the lists"),
    ({"assumed": "rules.yaml: 4 threshold(s) rest on an assumption", "unverified": []},
     "one string"),
    ({"assumed": ["rules.yaml: 4 threshold(s) rest on an assumption"], "unverified": []},
     "not a rule key"),
    ({"assumed": [""], "unverified": []}, "not a rule key"),
    ({"assumed": ["a.b", "a.b"], "unverified": []}, "repeats a key"),
    ({"assumed": ["a.b"], "unverified": ["a.b"]}, "both assumed and unverified"),
])
def test_a_rules_status_that_is_not_two_lists_of_keys_is_refused(store, lock, status, match):
    with pytest.raises(StoreError, match=match):
        start(store, lock, rules_status=status)
    assert store.runs_for(WED4) == ()                   # refused before anything was written


def test_the_dirty_flag_is_recorded_not_refused(store, lock):
    """Decision 7: uncommitted code is recorded, so the report can say 'not reproducible'."""
    assert start(store, lock, dirty=True).dirty is True


def test_the_run_log_cannot_be_written_inside_the_day_transaction(store, lock):
    run = start(store, lock)
    with store.day_transaction(WED4, run.run_id):
        with pytest.raises(StoreError, match="outside it"):
            store.finish_run(run.run_id, RunOutcome.COMPLETED, lock=lock)
        with pytest.raises(StoreError, match="outside it"):
            start(store, lock)


def test_the_schema_holds_the_run_log_rules_even_by_raw_sql(store):
    insert = ("INSERT INTO run_log (run_id, trade_date, started_at, finished_at, outcome, reason, "
              "input_checksums, code_version, dirty, rules_checksum, calendar_checksum, "
              "rules_status, superseded_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)")
    status = '{"assumed": [], "unverified": []}'
    base = ["r1", "2026-11-04", "t", None, "RUNNING", "", "{}", "c", 0, SHA_A, SHA_B, status, None]
    store._conn.execute(insert, base)              # the base row is valid, so each case below
    store._conn.execute("DELETE FROM run_log")     # fails for its own reason, not a shared one
    bad = {
        "RUNNING with a finish time": {3: "t2"},
        "ABANDONED with no successor": {4: "ABANDONED", 3: "t2", 5: "crashed"},
        "FAILED with no reason": {4: "FAILED", 3: "t2"},
        "an outcome that does not exist": {4: "DONE", 3: "t2"},
        "no rules status": {11: None},
        "rules status missing a list": {11: '{"assumed": []}'},
        "rules status as a sentence": {11: '{"assumed": "4 thresholds", "unverified": []}'},
    }
    for label, changes in bad.items():
        row = list(base)
        for i, v in changes.items():
            row[i] = v
        with pytest.raises(sqlite3.IntegrityError):
            store._conn.execute(insert, row)
            pytest.fail(label)


# -- the day transaction ---------------------------------------------------------------------


def test_a_crash_inside_the_day_leaves_nothing_of_it(store, lock, rules):
    """Decision 3, and the reason `_write()` exists: every writer joins one transaction.

    Before the refactor each writer committed on its own, so the official state written first
    would have survived a crash in a later stage - half a day, looking like a day.
    """
    run = start(store, lock)
    with pytest.raises(RuntimeError, match="stage crashed"):
        with store.day_transaction(WED4, run.run_id):
            store.record_official(WED4, {HELD_ISIN: ("HELDCO", True)}, input_sha256=SHA_B)
            store.record_forecast(THU5, {HELD_ISIN: ("HELDCO", True)}, input_sha256=SHA_A)
            store.record_measurements(ROWS, input_sha256=SHA_A)
            store.record_reconciliation(reconcile(ROWS, rules), input_sha256=SHA_A)
            store.record_row6_checks([ROW6])
            store.record_refusals([Refusal(WED4, RefusalStage.SCORE, "", "x")])
            raise RuntimeError("stage crashed")

    assert not store.has_day(WED4) and not store.has_day(THU5)
    assert store.measurements(WED4) == ()
    assert store.reconciliation(WED4) is None
    assert store.row6_checks(WED4) == () and store.refusals(WED4) == ()

    # ...and the run log, outside the transaction, can still say so
    store.finish_run(run.run_id, RunOutcome.FAILED, "stage crashed", lock=lock)
    assert store.runs_for(WED4)[-1].outcome is RunOutcome.FAILED


def test_a_committed_day_reads_back_exactly(store, lock, rules):
    run = start(store, lock)
    write_a_day(store, run, rules)

    assert store.measurements(WED4) == (HELD_4NOV, TESTCO_4NOV)   # FutEq OI to the last bit
    rec = store.reconciliation(WED4)
    assert (rec.rows_total, rec.residual_count, rec.barred_count, rec.barred_held) == (2, 1, 1, 1)
    assert rec.residual_min == rec.residual_max == pytest.approx(0.75)
    assert rec.residual_min_symbol == "TESTCO" and rec.ok
    assert store.row6_checks(WED4) == (ROW6,)                    # Decimals come back exact
    assert store.row6_checks(WED4)[0].baseline == Decimal("980.50000001")
    assert store.refusals(WED4) == (Refusal(WED4, RefusalStage.SCORE, "", "3 Nov forecast not stored"),)
    assert store.was_in_ban(HELD_ISIN, WED4) is True
    assert dict((i, f) for i, _, f, _ in store.scored_forecasts(THU5)) == {HELD_ISIN: True,
                                                                          TESTCO_ISIN: False}


def test_result_tables_take_writes_only_inside_the_day_transaction(store, rules):
    for write in (lambda: store.record_measurements(ROWS, input_sha256=SHA_A),
                  lambda: store.record_reconciliation(reconcile(ROWS, rules), input_sha256=SHA_A),
                  lambda: store.record_row6_checks([ROW6]),
                  lambda: store.record_refusals([Refusal(WED4, RefusalStage.ROW6, "", "x")])):
        with pytest.raises(StoreError, match="only inside day_transaction"):
            write()


def test_run_d_writes_only_ds_official_state_and_the_next_days_forecast(store, lock):
    run = start(store, lock)
    with store.day_transaction(WED4, run.run_id):
        with pytest.raises(StoreError, match="may write official for 2026-11-04 only"):
            store.record_official(THU5, {HELD_ISIN: ("HELDCO", True)}, input_sha256=SHA_B)
        with pytest.raises(StoreError, match="may write forecast for 2026-11-05 only"):
            store.record_forecast(WED4, {HELD_ISIN: ("HELDCO", True)}, input_sha256=SHA_A)
        with pytest.raises(StoreError, match="open day transaction is for 2026-11-04"):
            store.record_refusals([Refusal(THU5, RefusalStage.ROW6, "", "x")])


def test_an_unverified_next_day_blocks_the_forecast_but_not_ds_official_state(tmp_path):
    """#019 item 13 at the store: with the Muhurat Sunday's verdict removed, run Fri 6 Nov can
    still store 6 Nov's official state. Only a forecast needs the next trading day, so only a
    forecast write meets the calendar's refusal."""
    from sentinel.calendar import ChainUnverifiedError, DEFAULT_CALENDAR_PATH

    stripped = tmp_path / "calendar.csv"
    text = DEFAULT_CALENDAR_PATH.read_text(encoding="utf-8")
    stripped.write_text("".join(ln for ln in text.splitlines(keepends=True)
                                if not ln.startswith("chaining_")), encoding="utf-8")
    fri = dt.date(2026, 11, 6)
    with RunLock(tmp_path / "run.lock") as held, \
            BanStateStore(tmp_path / "s.sqlite", load_calendar(stripped)) as s:
        run = start(s, held, day=fri)
        with s.day_transaction(fri, run.run_id):
            s.record_official(fri, {HELD_ISIN: ("HELDCO", True)}, input_sha256=SHA_A)
            with pytest.raises(ChainUnverifiedError):
                s.record_forecast(dt.date(2026, 11, 9), {HELD_ISIN: ("HELDCO", True)},
                                  input_sha256=SHA_A)
        assert s.was_in_ban(HELD_ISIN, fri) is True


def test_the_forecast_crosses_the_muhurat_sunday(store, lock):
    """Run Fri 6 Nov forecasts Sun 8 Nov, because the special session chains (#013 addendum)."""
    fri, sun = dt.date(2026, 11, 6), dt.date(2026, 11, 8)
    run = start(store, lock, day=fri)
    with store.day_transaction(fri, run.run_id):
        store.record_forecast(sun, {HELD_ISIN: ("HELDCO", False)}, input_sha256=SHA_A)
    assert store.has_day(sun)


def test_the_day_transaction_attributes_results_to_a_live_run_for_that_day(store, lock):
    run = start(store, lock)
    with pytest.raises(StoreError, match="RUNNING run for 2026-11-05"):
        with store.day_transaction(THU5, run.run_id):
            pass
    store.finish_run(run.run_id, RunOutcome.COMPLETED, lock=lock)
    with pytest.raises(StoreError, match="is COMPLETED"):
        with store.day_transaction(WED4, run.run_id):
            pass
    with pytest.raises(StoreError, match="holiday"):
        holiday = start(store, lock, day=TUE10)
        with store.day_transaction(TUE10, holiday.run_id):
            pass


def test_day_transactions_do_not_nest(store, lock):
    run = start(store, lock)
    with store.day_transaction(WED4, run.run_id):
        with pytest.raises(StoreError, match="already open"):
            with store.day_transaction(WED4, run.run_id):
                pass


def test_every_result_row_names_a_run_that_exists(store):
    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            "INSERT INTO refusal (trade_date, stage, subject, reason, run_id, written_at) "
            "VALUES ('2026-11-04', 'row6', '', 'x', 'no-such-run', 't')")


# -- missing, refused, not run: three records, never one NULL ---------------------------------


def test_missing_ban_list_refused_and_not_run_are_three_different_records(store, lock):
    """Decision 5, the case that needed it: `official` is NULL in both of the first two."""
    # 4 Nov: ran, but its ban list was missing. Only the forecast column is filled in.
    run = start(store, lock)
    with store.day_transaction(WED4, run.run_id):
        store.record_forecast(THU5, {HELD_ISIN: ("HELDCO", True)}, input_sha256=SHA_A)
        store.record_refusals([Refusal(WED4, RefusalStage.OFFICIAL_STATE, "",
                                       "fo_secban_04112026.csv missing")])
    store.finish_run(run.run_id, RunOutcome.COMPLETED, lock=lock)

    # 5 Nov has never been run, and yet its row exists - with official NULL, from 4 Nov's forecast
    assert store.has_day(THU5)
    assert next(store.scored_forecasts(THU5))[3] is None

    # Wed 11 Nov: the whole run refused
    refused = start(store, lock, day=WED11)
    store.finish_run(refused.run_id, RunOutcome.REFUSED, "combineoi_11112026.zip missing", lock=lock)

    assert store.last_completed_run(WED4) is not None
    assert store.refusals(WED4)[0].stage is RefusalStage.OFFICIAL_STATE
    assert store.last_completed_run(THU5) is None and store.runs_for(THU5) == ()      # not run
    assert store.last_completed_run(WED11) is None
    assert store.runs_for(WED11)[0].outcome is RunOutcome.REFUSED                     # refused


def test_a_refusal_must_say_why():
    with pytest.raises(StoreError, match="no reason"):
        Refusal(WED4, RefusalStage.ROW6, "", " ")


def test_an_empty_write_is_refused_rather_than_meaning_nothing_happened(store, lock):
    run = start(store, lock)
    with store.day_transaction(WED4, run.run_id):
        with pytest.raises(StoreError, match="record why as a refusal"):
            store.record_row6_checks([])


def test_one_refusal_per_stage_and_subject(store, lock):
    run = start(store, lock)
    with store.day_transaction(WED4, run.run_id):
        store.record_refusals([
            Refusal(WED4, RefusalStage.FORECAST, HELD_ISIN, "in band and no seed"),
            Refusal(WED4, RefusalStage.ROW6, "", "no prop book for 2026-11-04"),
        ])
        with pytest.raises(StoreError, match="twice in one batch"):
            store.record_refusals([Refusal(WED4, RefusalStage.ROW6, "", "a"),
                                   Refusal(WED4, RefusalStage.ROW6, "", "b")])


# -- re-runs (decision 11) ----------------------------------------------------------------------


def test_an_identical_rerun_is_a_no_op_and_keeps_the_first_runs_attribution(store, lock, rules):
    first = start(store, lock)
    write_a_day(store, first, rules)
    store.finish_run(first.run_id, RunOutcome.COMPLETED, lock=lock)

    second = start(store, lock)
    with store.day_transaction(WED4, second.run_id):
        assert store.record_measurements(ROWS, input_sha256=SHA_A).was_a_no_op
        assert store.record_row6_checks([ROW6]).was_a_no_op
        assert store.record_reconciliation(reconcile(ROWS, rules), input_sha256=SHA_A).was_a_no_op
    owner = store._conn.execute("SELECT DISTINCT run_id FROM measurement").fetchall()
    assert [r["run_id"] for r in owner] == [first.run_id]


def test_a_changed_result_refuses_and_names_what_changed(store, lock, rules):
    first = start(store, lock)
    write_a_day(store, first, rules)
    store.finish_run(first.run_id, RunOutcome.COMPLETED, lock=lock)

    revised = MwplRow(**{**HELD_4NOV.__dict__, "futeq_oi": 161_020_001.0})
    second = start(store, lock)
    with pytest.raises(StoreError, match="decision 11") as exc:
        with store.day_transaction(WED4, second.run_id):
            store.record_measurements((revised, TESTCO_4NOV), input_sha256=SHA_A)
    assert "futeq_oi" in str(exc.value) and HELD_ISIN in str(exc.value)
    assert store.measurements(WED4)[0] == HELD_4NOV       # the stored day is untouched
