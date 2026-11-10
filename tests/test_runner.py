import csv
import datetime as dt
import shutil
from collections import defaultdict

import pytest

from sentinel import runner
from sentinel.calendar import load_calendar
from sentinel.rules import load_rules
from sentinel.runlock import RunLock
from sentinel.runner import REPO_ROOT, RunPaths
from sentinel.store import BanStateStore, RefusalStage, RunOutcome
from tests.test_ingest import build_combineoi

WINDOW = REPO_ROOT / "tests" / "fixtures" / "synthetic" / "window"
ROWS_CSV = WINDOW / "combineoi_rows.csv"
COMPLETE = dt.date(2026, 10, 13)      # has a ban list
NO_LIST = dt.date(2026, 10, 14)       # no ban list, by design
HOLIDAY = dt.date(2026, 11, 10)       # Diwali Balipratipada
FRI_6_NOV = dt.date(2026, 11, 6)      # next trading day is the Muhurat Sunday
REAL_DAY = dt.date(2026, 11, 4)

EMPTY_STATUS = {"assumed": [], "unverified": []}


def window_rows_by_day() -> dict[dt.date, list[dict]]:
    """Group the window's combineoi rows by trade date, as
    test_ingest.fixture_rows() does."""
    by_day = defaultdict(list)
    with ROWS_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            by_day[dt.date.fromisoformat(row["trade_date"])].append(row)  # ISO dates, as the window writes them
    return dict(by_day)


def isin_of(symbol: str) -> str:
    """The window's ISIN for a synthetic symbol, read from the fixture rows."""
    for rows in window_rows_by_day().values():
        for row in rows:
            if row["symbol"] == symbol:
                return row["isin"]
    raise KeyError(symbol)


def synthetic_paths(tmp_path, *, with_combineoi=True, calendar=None) -> RunPaths:
    """A temporary data/: one combineoi zip per window day, plus the
    window's ban lists copied alongside."""
    data = tmp_path / "data"
    data.mkdir()
    if with_combineoi:
        for day, rows in window_rows_by_day().items():
            build_combineoi(data, day, rows)
    for ban_list in WINDOW.glob("fo_secban_*.csv"):
        shutil.copy(ban_list, data / ban_list.name)
    base = RunPaths.default()
    return RunPaths(data=data, rules=base.rules, calendar=calendar or base.calendar,
                    store=tmp_path / "sentinel.sqlite",
                    lock=tmp_path / "runner.lock",
                    book=data / "book" / "positions.csv")


def open_store(paths):
    return BanStateStore(paths.store, load_calendar(paths.calendar))


# ---------------------------------------------------------------- CI: synthetic

def test_holiday_is_refused_and_writes_nothing(tmp_path):
    paths = synthetic_paths(tmp_path)
    assert runner.run_day(HOLIDAY, paths) is RunOutcome.REFUSED
    with open_store(paths) as store:
        assert store.measurements(HOLIDAY) == ()
        run = store.runs_for(HOLIDAY)[-1]
        assert run.outcome is RunOutcome.REFUSED
        assert "holiday" in run.reason      # refused as a holiday, not for a missing file


def test_missing_combineoi_refuses_the_whole_run(tmp_path):
    paths = synthetic_paths(tmp_path, with_combineoi=False)
    assert runner.run_day(COMPLETE, paths) is RunOutcome.REFUSED
    with open_store(paths) as store:
        assert store.measurements(COMPLETE) == ()
        assert "combineoi" in store.runs_for(COMPLETE)[-1].reason


def test_complete_day_runs_and_records_rules_status(tmp_path):
    paths = synthetic_paths(tmp_path)
    rules = load_rules(paths.rules, warn=False)
    assert runner.run_day(COMPLETE, paths) is RunOutcome.COMPLETED
    with open_store(paths) as store:
        run = store.runs_for(COMPLETE)[-1]
        assert run.rules_status["assumed"] == tuple(sorted(rules.assumed))
        assert run.rules_status["unverified"] == tuple(sorted(rules.unverified))


def test_missing_ban_list_gives_partial_refusals(tmp_path):
    paths = synthetic_paths(tmp_path)
    assert runner.run_day(NO_LIST, paths) is RunOutcome.COMPLETED
    with open_store(paths) as store:
        stages = {r.stage for r in store.refusals(NO_LIST)}
        assert {RefusalStage.OFFICIAL_STATE, RefusalStage.SCORE, RefusalStage.ROW6} <= stages
        assert store.reconciliation(NO_LIST)                  # still ran
        # #012 in the runner: exactly the in-band scrips are refused, by ISIN.
        per_scrip = {r.subject for r in store.refusals(NO_LIST)
                     if r.stage is RefusalStage.FORECAST and r.subject}
        assert per_scrip == {isin_of(s) for s in
                             ("ENTRYCO", "EDGECO", "RELEASECO", "STICKYCO", "FREECO")}


def test_unresolved_banned_symbol_refuses_the_whole_run(tmp_path):
    paths = synthetic_paths(tmp_path)
    ban_list = paths.ban_list(COMPLETE)
    text = ban_list.read_text(encoding="utf-8")
    ban_list.write_text(text.rstrip("\n") + "\n4,GHOSTCO\n", encoding="utf-8")
    assert runner.run_day(COMPLETE, paths) is RunOutcome.REFUSED
    with open_store(paths) as store:
        assert store.measurements(COMPLETE) == ()
        assert "GHOSTCO" in store.runs_for(COMPLETE)[-1].reason


def test_unverified_next_day_refuses_only_the_forecast(tmp_path):
    # A calendar with the chaining rows stripped, as test_synthetic_window does,
    # so the Muhurat Sunday after Fri 6 Nov is unverified.
    stripped = tmp_path / "calendar_unverified.csv"
    lines = runner.RunPaths.default().calendar.read_text(encoding="utf-8").splitlines()
    stripped.write_text(
        "\n".join(l for l in lines if "chaining_" not in l) + "\n", encoding="utf-8")

    paths = synthetic_paths(tmp_path, with_combineoi=False, calendar=stripped)
    # Move the window's 13 Oct day to Fri 6 Nov: its rows and its ban list.
    rows = [dict(r, trade_date=FRI_6_NOV.isoformat())
            for r in window_rows_by_day()[COMPLETE]]
    build_combineoi(paths.data, FRI_6_NOV, rows)
    list_text = (WINDOW / runner.RunPaths.default().ban_list(COMPLETE).name).read_text(
        encoding="utf-8")
    paths.ban_list(FRI_6_NOV).write_text(
        list_text.replace("13-OCT-2026", "06-NOV-2026"), encoding="utf-8")

    assert runner.run_day(FRI_6_NOV, paths) is RunOutcome.COMPLETED
    with open_store(paths) as store:
        forecast_refusals = [r for r in store.refusals(FRI_6_NOV)
                             if r.stage is RefusalStage.FORECAST]
        assert len(forecast_refusals) == 1
        assert forecast_refusals[0].subject == ""             # the whole stage
        assert store.measurements(FRI_6_NOV)                  # still stored
        assert store.reconciliation(FRI_6_NOV)


def test_crash_rolls_back_the_whole_day(tmp_path, monkeypatch):
    paths = synthetic_paths(tmp_path)

    def boom(*args, **kwargs):
        raise RuntimeError("simulated crash")

    # Runs after record_measurements, so this proves the measurements roll back.
    monkeypatch.setattr(BanStateStore, "record_reconciliation", boom)
    with pytest.raises(RuntimeError):
        runner.run_day(COMPLETE, paths)
    with open_store(paths) as store:
        assert store.measurements(COMPLETE) == ()
        assert store.runs_for(COMPLETE)[-1].outcome is RunOutcome.FAILED


def test_killed_run_is_marked_abandoned(tmp_path):
    paths = synthetic_paths(tmp_path)
    calendar = load_calendar(paths.calendar)
    # A run that starts and never finishes, then releases the lock: a kill.
    with RunLock(paths.lock) as lock, BanStateStore(paths.store, calendar) as store:
        stale = store.start_run(
            COMPLETE, lock=lock, input_checksums={}, code_version="test",
            dirty=False, rules_checksum="0" * 64, calendar_checksum="0" * 64,
            rules_status=EMPTY_STATUS)

    assert runner.run_day(COMPLETE, paths) is RunOutcome.COMPLETED
    with open_store(paths) as store:
        runs = store.runs_for(COMPLETE)
        old = next(r for r in runs if r.run_id == stale.run_id)
        new = runs[-1]
        assert old.outcome is RunOutcome.ABANDONED
        assert old.superseded_by == new.run_id


def test_lock_held_is_a_refusal_not_a_crash(tmp_path, monkeypatch, capsys):
    paths = synthetic_paths(tmp_path)
    monkeypatch.setattr(runner.RunPaths, "default", classmethod(lambda cls: paths))
    with RunLock(paths.lock):
        code = runner.main(["runner", COMPLETE.isoformat()])
    assert code == 2
    assert "another run in progress" in capsys.readouterr().err


# ---------------------------------------------------------------- local: real data

needs_data = pytest.mark.skipif(
    not RunPaths.default().combineoi(REAL_DAY).exists(),
    reason="local NSE data not present")


@needs_data
def test_4_nov_completes_and_rerun_changes_nothing(tmp_path):
    base = RunPaths.default()
    # Read the real data/ in place; only the store and lock are temporary.
    paths = RunPaths(data=base.data, rules=base.rules, calendar=base.calendar,
                     store=tmp_path / "sentinel.sqlite",
                     lock=tmp_path / "runner.lock", book=base.book)
    next_day = dt.date(2026, 11, 5)

    def snapshot(store):
        return (store.measurements(REAL_DAY), store.reconciliation(REAL_DAY),
                store.refusals(REAL_DAY), tuple(store.scored_forecasts(next_day)))

    assert runner.run_day(REAL_DAY, paths) is RunOutcome.COMPLETED
    with open_store(paths) as store:
        before = snapshot(store)
    assert runner.run_day(REAL_DAY, paths) is RunOutcome.COMPLETED
    with open_store(paths) as store:
        assert snapshot(store) == before
        completed = [r for r in store.runs_for(REAL_DAY)
                     if r.outcome is RunOutcome.COMPLETED]
        assert len(completed) == 2
