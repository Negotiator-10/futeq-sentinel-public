"""The report's layout, on runs of the synthetic window.

The two judgements in the report - `flag_disagreements()` and `watchlist()` - are Chintamani's
and are not written yet, so these tests replace them with stand-ins and check everything around
them: the section order, refused sections saying so, the footer, and the report refusing when
there is no run to describe. His own tests for the two functions go beside these.

Written by Claude, as the plumbing around his functions.
"""

from __future__ import annotations

import datetime as dt
import shutil

import pytest

from sentinel import report, runner
from sentinel.calendar import load_calendar
from sentinel.report import (
    Disagreement, FlagComparison, NotCompared, ReportRefused, WatchEntry, WatchState,
)
from sentinel.rules import load_rules
from sentinel.runlock import RunLock
from sentinel.store import BanStateStore, RunOutcome
from tests.test_runner import (
    COMPLETE, EMPTY_STATUS, FRI_6_NOV, HOLIDAY, NO_LIST, synthetic_paths,
)

SECTIONS = ["## 1. Refusals", "## 2. Flag disagreements with NSE", "## 3. Row 6 breaches",
            "## 4. Tomorrow's ban", "## 5. Watchlist: the 80-95% band", "## 6. Checks passed",
            "### Audit"]


def simple_flags(rows, forecasts):
    """A stand-in: compares where both exist, else not compared."""
    dis, nc, agreed = [], [], 0
    for r in rows:
        f = forecasts.get(r.isin, (r.symbol, None))[1]
        if f is None:
            nc.append(NotCompared(r.isin, r.symbol, "forecast refused"))
        elif f != r.no_fresh_positions:
            dis.append(Disagreement(r.isin, r.symbol, r.no_fresh_positions, f))
        else:
            agreed += 1
    return FlagComparison(tuple(dis), tuple(nc), agreed)


@pytest.fixture
def stand_ins(monkeypatch):
    calls = {"flags": 0, "watch": 0}

    def flags(rows, forecasts):
        calls["flags"] += 1
        return simple_flags(rows, forecasts)

    def watch(rows, official, rules):
        calls["watch"] += 1
        return ()

    monkeypatch.setattr(report, "flag_disagreements", flags)
    monkeypatch.setattr(report, "watchlist", watch)
    return calls


def ran(tmp_path, day, **kw):
    paths = synthetic_paths(tmp_path, **kw)
    runner.run_day(day, paths)
    return paths


# -- the shape ---------------------------------------------------------------------------


def test_the_sections_come_in_019s_order_and_both_judgements_are_called(tmp_path, stand_ins):
    text = report.render(COMPLETE, ran(tmp_path, COMPLETE))
    positions = [text.index(s) for s in SECTIONS]
    assert positions == sorted(positions)
    assert stand_ins == {"flags": 1, "watch": 1}


def test_the_report_is_rendered_from_the_store_not_the_files(tmp_path, stand_ins):
    """#019 item 8: delete every input after the run and the report is unchanged."""
    paths = ran(tmp_path, COMPLETE)
    before = report.render(COMPLETE, paths)
    shutil.rmtree(paths.data)
    assert report.render(COMPLETE, paths) == before


def test_a_complete_day_reports_its_checks_and_forecast(tmp_path, stand_ins):
    text = report.render(COMPLETE, ran(tmp_path, COMPLETE))
    assert "Forecast for 2026-10-14: ENTRYCO, STICKYCO." in text
    assert "Reconciliation against NSE's published headroom: passed." in text
    assert "7 agreed; 0 not compared." in text


# -- refused is never zero ---------------------------------------------------------------


def test_a_refused_row_6_says_refused_not_no_breaches(tmp_path, stand_ins):
    text = report.render(COMPLETE, ran(tmp_path, COMPLETE))
    row6 = text.split("## 3. Row 6 breaches")[1].split("## 4.")[0]
    assert "Refused:" in row6
    assert "None" not in row6 and "0 " not in row6


def test_a_missing_ban_list_shows_in_refusals_and_tomorrow(tmp_path, stand_ins):
    text = report.render(NO_LIST, ran(tmp_path, NO_LIST))
    assert "**official_state** refused" in text and "**score** refused" in text
    assert "**forecast** refused for 5 scrip(s): EDGECO, ENTRYCO, FREECO, RELEASECO, STICKYCO" in text
    tomorrow = text.split("## 4. Tomorrow's ban")[1].split("## 5.")[0]
    assert "Not forecast: EDGECO, ENTRYCO, FREECO, RELEASECO, STICKYCO" in tomorrow
    assert "5 not compared" in text        # a refused forecast is not an agreement


def test_an_unverified_next_day_refuses_flags_and_tomorrow(tmp_path, stand_ins):
    stripped = tmp_path / "calendar.csv"
    text = runner.RunPaths.default().calendar.read_text(encoding="utf-8")
    stripped.write_text("".join(ln for ln in text.splitlines(keepends=True)
                                if not ln.startswith("chaining_")), encoding="utf-8")
    paths = synthetic_paths(tmp_path, with_combineoi=False, calendar=stripped)
    from tests.test_runner import WINDOW, build_combineoi, window_rows_by_day
    build_combineoi(paths.data, FRI_6_NOV,
                    [dict(r, trade_date=FRI_6_NOV.isoformat()) for r in window_rows_by_day()[COMPLETE]])
    paths.ban_list(FRI_6_NOV).write_text(
        (WINDOW / "fo_secban_13102026.csv").read_text(encoding="utf-8")
        .replace("13-OCT-2026", "06-NOV-2026"), encoding="utf-8")
    assert runner.run_day(FRI_6_NOV, paths) is RunOutcome.COMPLETED

    out = report.render(FRI_6_NOV, paths)
    flags = out.split("## 2.")[1].split("## 3.")[0]
    tomorrow = out.split("## 4.")[1].split("## 5.")[0]
    assert "Refused: nothing to compare" in flags
    assert "Refused:" in tomorrow
    assert stand_ins["flags"] == 0                  # never asked to compare against nothing
    assert "forecast date none" in out


# -- the two judgements, as the report prints them ----------------------------------------


def test_a_disagreement_says_nse_governs(tmp_path, monkeypatch, stand_ins):
    paths = ran(tmp_path, COMPLETE)
    monkeypatch.setattr(report, "flag_disagreements", lambda rows, f: FlagComparison(
        (Disagreement("INE000E01011", "ENTRYCO", False, True),), (), 6))
    text = report.render(COMPLETE, paths)
    assert "**1 disagreement(s).** " + report.GOVERNS in text
    assert "| ENTRYCO | free | banned |" in text


def test_the_watchlist_prints_the_distance_that_applies(tmp_path, monkeypatch, stand_ins):
    paths = ran(tmp_path, COMPLETE)
    entries = (
        WatchEntry("I1", "HELDA", 0.8051, WatchState.BANNED, 0.51, 510_000.0, None, None, None),
        WatchEntry("I2", "FREEA", 0.9000001, WatchState.FREE, None, None, 4.99999, 49_999.99, 49_999),
        WatchEntry("I3", "FREEB", 0.90, WatchState.FREE, None, None, 5.0, 50_000.0, 49_000),
        WatchEntry("I4", "UNKNA", 0.85, WatchState.UNKNOWN, 5.0, 50_000.0, 10.0, 100_000.0, None),
    )
    monkeypatch.setattr(report, "watchlist", lambda rows, official, rules: entries)
    text = report.render(COMPLETE, paths)
    assert "| HELDA | 80.51% | banned | 0.51 pts above the exit; must fall by 510,000 shares |" in text
    assert "headroom 49,999.9900 shares (NSE: 49,999, within [0, 1))" in text
    assert "(NSE: 49,000, differs by 1000.0000)" in text
    assert "| UNKNA | 85.00% | unknown | 5.00 pts above the exit; must fall by 50,000 shares / " \
           "10.00 pts below the entry; headroom 100,000 shares |" in text


def test_the_watchlist_is_given_no_official_state_when_the_list_was_missing(tmp_path, monkeypatch, stand_ins):
    seen = {}

    def watch(rows, official, rules):
        seen["official"] = official
        return ()

    monkeypatch.setattr(report, "watchlist", watch)
    report.render(NO_LIST, ran(tmp_path, NO_LIST))
    assert seen["official"] is None


def test_the_watchlist_is_given_the_official_state_when_it_exists(tmp_path, monkeypatch, stand_ins):
    seen = {}

    def watch(rows, official, rules):
        seen["official"] = official
        return ()

    monkeypatch.setattr(report, "watchlist", watch)
    report.render(COMPLETE, ran(tmp_path, COMPLETE))
    banned = {i for i, b in seen["official"].items() if b}
    assert len(seen["official"]) == 7 and len(banned) == 3     # ENTRYCO, HOLDCO, STICKYCO


# -- the footer --------------------------------------------------------------------------


def test_the_footer_carries_the_run_log(tmp_path, stand_ins):
    paths = ran(tmp_path, COMPLETE)
    text = report.render(COMPLETE, paths)
    footer = text.split("### Audit")[1]
    with BanStateStore(paths.store, load_calendar(paths.calendar)) as store:
        run = store.last_completed_run(COMPLETE)
    rules = load_rules(paths.rules, warn=False)
    assert run.run_id in footer and run.started_at in footer and run.finished_at in footer
    assert run.rules_checksum in footer and run.calendar_checksum in footer
    assert "forecast date 2026-10-14" in footer
    assert ", ".join(rules.assumed) in footer
    for name, sha in run.input_checksums.items():
        assert f"`{name}` `{sha}`" in footer


def test_a_dirty_run_is_marked_not_reproducible(tmp_path, monkeypatch, stand_ins):
    monkeypatch.setattr(runner, "code_version", lambda: ("abc1234", True))
    text = report.render(COMPLETE, ran(tmp_path, COMPLETE))
    assert "code `abc1234`, **" + report.NOT_REPRODUCIBLE + "**" in text


def test_a_rules_file_changed_since_the_run_is_flagged(tmp_path, stand_ins):
    paths = synthetic_paths(tmp_path)
    rules = tmp_path / "rules.yaml"
    shutil.copy(paths.rules, rules)
    paths = runner.RunPaths(paths.data, rules, paths.calendar, paths.store, paths.lock, paths.book)
    runner.run_day(COMPLETE, paths)
    assert "has changed since this run" not in report.render(COMPLETE, paths)
    rules.write_text(rules.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    assert "**rules.yaml has changed since this run**" in report.render(COMPLETE, paths)


# -- nothing to describe -----------------------------------------------------------------


def test_a_refused_run_gets_a_short_report_with_its_footer(tmp_path, stand_ins):
    text = report.render(HOLIDAY, ran(tmp_path, HOLIDAY))
    assert "**The run for 2026-11-10 was refused:** 2026-11-10 is a trading holiday" in text
    assert "### Audit" in text and "## 1. Refusals" not in text
    assert stand_ins == {"flags": 0, "watch": 0}


def test_a_date_never_run_is_refused(tmp_path, stand_ins):
    paths = synthetic_paths(tmp_path)
    with RunLock(paths.lock), BanStateStore(paths.store, load_calendar(paths.calendar)):
        pass                                        # the store exists; the date was not run
    with pytest.raises(ReportRefused, match="has not been run"):
        report.render(COMPLETE, paths)


def test_a_date_whose_only_run_failed_is_refused(tmp_path, monkeypatch, stand_ins):
    paths = synthetic_paths(tmp_path)

    def boom(*a, **k):
        raise RuntimeError("simulated crash")

    monkeypatch.setattr(BanStateStore, "record_reconciliation", boom)
    with pytest.raises(RuntimeError):
        runner.run_day(COMPLETE, paths)
    monkeypatch.undo()
    with pytest.raises(ReportRefused, match="FAILED"):
        report.render(COMPLETE, paths)


def test_a_later_failed_run_is_named_but_the_completed_one_is_reported(tmp_path, stand_ins):
    paths = ran(tmp_path, COMPLETE)
    with RunLock(paths.lock) as lock, \
            BanStateStore(paths.store, load_calendar(paths.calendar)) as store:
        later = store.start_run(COMPLETE, lock=lock, input_checksums={}, code_version="x",
                                dirty=False, rules_checksum="0" * 64, calendar_checksum="0" * 64,
                                rules_status=EMPTY_STATUS)
        store.finish_run(later.run_id, RunOutcome.FAILED, "simulated", lock=lock)
    text = report.render(COMPLETE, paths)
    assert "COMPLETED, forecast for 2026-10-14" in text
    assert f"`{later.run_id[:8]}` FAILED" in text.split("### Audit")[1]


# -- the command -------------------------------------------------------------------------


def test_the_command_writes_the_file_and_refuses_with_exit_2(tmp_path, monkeypatch, stand_ins):
    paths = ran(tmp_path, COMPLETE)
    monkeypatch.setattr(runner.RunPaths, "default", classmethod(lambda cls: paths))
    monkeypatch.setattr(report, "REPO_ROOT", tmp_path)
    assert report.main(["report", COMPLETE.isoformat()]) == 0
    assert (tmp_path / "reports" / "2026-10-13.md").read_text(encoding="utf-8").startswith(
        "# FutEq Sentinel report: 2026-10-13")
    assert report.main(["report", "2026-10-12"]) == 2


def test_the_two_judgements_are_still_stubs():
    """Remove this when they are written: it is here so the stubs cannot be forgotten."""
    with pytest.raises(NotImplementedError):
        report.flag_disagreements((), {})
    with pytest.raises(NotImplementedError):
        report.watchlist((), None, load_rules(warn=False))
