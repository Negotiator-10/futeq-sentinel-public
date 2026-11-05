"""Tests for the NSE file parsers.

The cases below are the ones `parse_ban_list()` was actually checked against while it was
written, not a set invented afterwards. Each refusal corresponds to a decision recorded in
the function's docstring, so a test failing here means a decision changed.

Written by Claude from behaviour Chintamani's code already produced and we had both seen
pass. The decisions being tested are his.
"""

from __future__ import annotations

import datetime as dt

import pytest

from sentinel.parsers import BanList, parse_ban_list

REAL = "tests/fixtures/fo_secban_02112026.csv"
EMPTY_DAY = "tests/fixtures/fo_secban_empty.csv"

HEADING = "Securities in Ban For Trade Date 02-NOV-2026:"


def write(tmp_path, *lines: str, trailing_newline: bool = True):
    path = tmp_path / "fo_secban_test.csv"
    text = "\n".join(lines) + ("\n" if trailing_newline else "")
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The real files
# ---------------------------------------------------------------------------


def test_the_real_file():
    result = parse_ban_list(REAL)
    assert result.trade_date == dt.date(2026, 11, 2)
    assert result.symbols == frozenset({"KAYNES", "SAIL"})


def test_a_day_with_no_bans_is_not_an_error():
    """The case that would take the pipeline down on a quiet Tuesday."""
    result = parse_ban_list(EMPTY_DAY)
    assert result.trade_date == dt.date(2026, 11, 3)
    assert result.symbols == frozenset()


def test_the_result_is_immutable():
    """Nothing downstream may add a scrip to the ban list."""
    result = parse_ban_list(REAL)
    with pytest.raises(AttributeError):
        result.trade_date = dt.date(2026, 1, 1)  # type: ignore[misc]
    assert isinstance(result, BanList)


def test_the_date_comes_from_the_heading_not_the_filename(tmp_path):
    """A renamed or copied file still reports the day NSE said it was about."""
    path = write(tmp_path, "Securities in Ban For Trade Date 09-DEC-2026:", "1,SAIL")
    assert parse_ban_list(path).trade_date == dt.date(2026, 12, 9)


# ---------------------------------------------------------------------------
# Skipped: carries no information
# ---------------------------------------------------------------------------


def test_a_trailing_blank_line_is_skipped(tmp_path):
    path = write(tmp_path, HEADING, "1,KAYNES", "2,SAIL", "")
    assert parse_ban_list(path).symbols == frozenset({"KAYNES", "SAIL"})


def test_a_whitespace_only_line_is_skipped(tmp_path):
    path = write(tmp_path, HEADING, "1,KAYNES", "   ")
    assert parse_ban_list(path).symbols == frozenset({"KAYNES"})


def test_spaces_around_a_symbol_are_stripped(tmp_path):
    path = write(tmp_path, HEADING, "1, KAYNES ", "2,SAIL")
    assert parse_ban_list(path).symbols == frozenset({"KAYNES", "SAIL"})


def test_a_file_with_no_trailing_newline_parses(tmp_path):
    path = write(tmp_path, HEADING, "1,KAYNES", trailing_newline=False)
    assert parse_ban_list(path).symbols == frozenset({"KAYNES"})


# ---------------------------------------------------------------------------
# Refused: carries information that cannot be read
# ---------------------------------------------------------------------------


def test_a_row_with_no_comma_is_refused(tmp_path):
    """`'SAIL'` names a scrip. Skipping it would drop a possibly-banned security."""
    path = write(tmp_path, HEADING, "1,KAYNES", "SAIL")
    with pytest.raises(ValueError, match="expected 'serial,SYMBOL'"):
        parse_ban_list(path)


def test_a_blank_symbol_is_refused(tmp_path):
    """`'2,'` has two parts, so the comma check passes and only emptiness catches it."""
    path = write(tmp_path, HEADING, "1,KAYNES", "2,")
    with pytest.raises(ValueError, match="symbol empty"):
        parse_ban_list(path)


def test_a_gap_in_the_serials_is_refused(tmp_path):
    """A row lost from the middle of the file. Catches a gap, not a truncation."""
    path = write(tmp_path, HEADING, "1,KAYNES", "3,SAIL")
    with pytest.raises(ValueError, match="expected serial 2"):
        parse_ban_list(path)


def test_a_repeated_symbol_is_refused(tmp_path):
    """The one a `frozenset` would hide.

    `frozenset(["SAIL", "SAIL"])` is a one-element set, so without this check a repeated
    symbol would collapse silently and a row would vanish without trace. The check has to
    happen before the lossy conversion, on the side that still has the information.
    """
    path = write(tmp_path, HEADING, "1,SAIL", "2,SAIL")
    with pytest.raises(ValueError, match="duplicate symbol"):
        parse_ban_list(path)


def test_an_empty_file_is_refused(tmp_path):
    """Zero bytes - the likeliest artefact of a failed download.

    Without an explicit guard this raises `IndexError` from the middle of the function,
    which tells an operator nothing about which file was bad.
    """
    path = tmp_path / "fo_secban_test.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="file is empty"):
        parse_ban_list(path)


def test_an_html_error_page_is_refused(tmp_path):
    """The realistic failure, given NSE serves 403s and error pages to scripts."""
    path = write(tmp_path, "<!DOCTYPE html>", "<html><body>403 Forbidden</body></html>")
    with pytest.raises(ValueError, match="not a ban-list heading"):
        parse_ban_list(path)


def test_an_unrecognised_heading_is_refused(tmp_path):
    """Deliberately strict: if NSE rewords the heading, the parser stops.

    The alternative - extracting any date-shaped text from any first line - would accept a
    file that is not a ban list at all.
    """
    path = write(tmp_path, "F&O Securities under restriction 02-NOV-2026", "1,SAIL")
    with pytest.raises(ValueError, match="not a ban-list heading"):
        parse_ban_list(path)


def test_a_heading_with_no_date_is_refused(tmp_path):
    path = write(tmp_path, "Securities in Ban For Trade Date:", "1,SAIL")
    with pytest.raises(ValueError, match="no date of the form"):
        parse_ban_list(path)


# ---------------------------------------------------------------------------
# The known limitation, recorded as a test so it is not forgotten
# ---------------------------------------------------------------------------


def test_a_truncated_file_is_indistinguishable_from_a_no_ban_day(tmp_path):
    """Documents a hole the parser cannot close.

    A download that received the heading and then died is byte-for-byte identical to a
    legitimate day with no bans. The file carries no row count, length or checksum, so no
    parser can tell them apart - it needs the transport to record something. This test
    asserts the current, wrong-but-unavoidable behaviour so that it fails loudly if the
    downloader ever starts supplying that information. See TASKS.md and DECISIONS.md #010.
    """
    truncated = write(tmp_path, HEADING)
    assert parse_ban_list(truncated).symbols == frozenset()
    # Identical to the real no-ban day, which is the problem:
    assert parse_ban_list(EMPTY_DAY).symbols == frozenset()
