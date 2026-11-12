"""The declared book start date (#016 addendum 2, point 2): read, never inferred.

Plumbing, by Claude, 12 Nov 2026. What the runner does with the date - NoPriorDay on it, a
refusal after it when yesterday's book is missing, a refusal before it - is Chintamani's.
"""

from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from sentinel.book import DEFAULT_BOOK_CONFIG_PATH, BookError, BookStart, load_book_start
from sentinel.calendar import load_calendar
from sentinel.runner import RunPaths

CALENDAR = load_calendar()


def write(tmp_path, text: str):
    p = tmp_path / "book.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_the_project_declares_1_oct_2025_a_trading_day():
    start = load_book_start(calendar=CALENDAR)
    assert start.start_date == dt.date(2025, 10, 1)
    assert "#020" in start.reason
    assert start.path == DEFAULT_BOOK_CONFIG_PATH


def test_runpaths_points_at_it_and_a_test_can_declare_its_own(tmp_path):
    assert RunPaths.default().book_config == DEFAULT_BOOK_CONFIG_PATH
    own = write(tmp_path, "start_date: 2026-10-12\nreason: the synthetic window's first day\n")
    paths = dataclasses.replace(RunPaths.default(), book_config=own)
    assert load_book_start(paths.book_config, calendar=CALENDAR) == BookStart(
        dt.date(2026, 10, 12), "the synthetic window's first day", own)


def test_existing_callers_get_the_default_without_naming_it(tmp_path):
    p = RunPaths(data=tmp_path, rules=tmp_path, calendar=tmp_path, store=tmp_path,
                 lock=tmp_path, book=tmp_path)
    assert p.book_config == DEFAULT_BOOK_CONFIG_PATH


def test_a_missing_file_is_refused_not_read_as_a_first_run(tmp_path):
    with pytest.raises(BookError, match="no declared book start date"):
        load_book_start(tmp_path / "absent.yaml")


@pytest.mark.parametrize("text,match", [
    ("reason: x\n", r"missing \['start_date'\]"),
    ("start_date: 2026-10-12\n", r"missing \['reason'\]"),
    ("start_dat: 2026-10-12\nreason: x\n", r"unexpected \['start_dat'\]"),       # a typo
    ("start_date: '2026-10-12'\nreason: x\n", "unquoted"),                       # a string
    ("start_date: 2026-10-12 09:15:00\nreason: x\n", "with no time"),            # a timestamp
    ("start_date: 2026-10-12\nreason: '  '\n", "no reason"),
    ("- 2026-10-12\n", "expected start_date and reason"),
])
def test_a_start_date_that_half_loads_is_refused(tmp_path, text, match):
    with pytest.raises(BookError, match=match):
        load_book_start(write(tmp_path, text))


@pytest.mark.parametrize("day,kind", [
    ("2026-10-11", "holiday"),          # a Sunday
    ("2026-11-08", "special_session"),  # the Muhurat Sunday
    ("2030-01-01", "unknown"),          # outside the verified calendar
])
def test_a_start_the_runner_could_never_see_is_refused(tmp_path, day, kind):
    with pytest.raises(BookError, match=f"is {kind}, not a trading day"):
        load_book_start(write(tmp_path, f"start_date: {day}\nreason: x\n"), calendar=CALENDAR)
