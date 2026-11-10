"""Tests for the NSE file parsers.

The cases below are the ones `parse_ban_list()` was actually checked against while it was
written, not a set invented afterwards. Each refusal corresponds to a decision recorded in
the function's docstring, so a test failing here means a decision changed.

Written by Claude from behaviour Chintamani's code already produced and we had both seen
pass. The decisions being tested are his.

The fixture files are synthetic, in NSE's exact layout: NSE's content stays out of the
repository (`DECISIONS.md` #010 addendum). The same parsers run on NSE's real files in
`tests/test_nse_local.py`, which reads them from `data/` and skips without it.
"""

from __future__ import annotations

import datetime as dt

import pytest

from sentinel.parsers import (
    BanList,
    as_dataframe,
    parse_ban_list,
    parse_mwpl_file,
)

SAMPLE_BANS = "tests/fixtures/synthetic/fo_secban_02112026.csv"
EMPTY_DAY = "tests/fixtures/fo_secban_empty.csv"

HEADING = "Securities in Ban For Trade Date 02-NOV-2026:"


def write(tmp_path, *lines: str, trailing_newline: bool = True):
    path = tmp_path / "fo_secban_test.csv"
    text = "\n".join(lines) + ("\n" if trailing_newline else "")
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Whole files
# ---------------------------------------------------------------------------


def test_a_whole_file():
    result = parse_ban_list(SAMPLE_BANS)
    assert result.trade_date == dt.date(2026, 11, 2)
    assert result.symbols == frozenset({"LATCHCO", "HELDCO"})


def test_a_day_with_no_bans_is_not_an_error():
    """The case that would take the pipeline down on a quiet Tuesday."""
    result = parse_ban_list(EMPTY_DAY)
    assert result.trade_date == dt.date(2026, 11, 3)
    assert result.symbols == frozenset()


def test_the_result_is_immutable():
    """Nothing downstream may add a scrip to the ban list."""
    result = parse_ban_list(SAMPLE_BANS)
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
    # Identical to a no-ban day, which is the problem:
    assert parse_ban_list(EMPTY_DAY).symbols == frozenset()


# ===========================================================================
# parse_mwpl_file() and as_dataframe()
# ===========================================================================

SAMPLE = "tests/fixtures/synthetic/combineoi_sample.csv"

MWPL_HEADER = (
    "Date, ISIN, Scrip Name, NSE Symbol, MWPL, Open Interest, "
    "Future Equivalent Open Interest, Limit for Next Day"
)
BARRED_ROW = (
    "30-OCT-2026,INE000L01014,LATCH COMPANY LTD,LATCHCO,"
    "5000000,6100000,4608500.5,No Fresh Positions"
)
NORMAL_ROW = (
    "30-OCT-2026,INE000D01010,HEADROOM COMPANY LTD,HEADCO,"
    "60000000,7500000,5000000.7805,51999999"
)


def write_mwpl(tmp_path, *rows: str, header: str = MWPL_HEADER):
    path = tmp_path / "combineoi_test.csv"
    path.write_text("\n".join((header, *rows)) + "\n", encoding="utf-8")
    return path


def test_the_sample_file():
    rows = parse_mwpl_file(SAMPLE)
    assert len(rows) == 3
    assert {r.symbol for r in rows} == {"LATCHCO", "HELDCO", "HEADCO"}
    assert all(r.trade_date == dt.date(2026, 10, 30) for r in rows)


def test_a_barred_row_has_no_headroom():
    """The decision-1 invariant: a barred row's headroom is None, not a number."""
    kaynes = next(r for r in parse_mwpl_file(SAMPLE) if r.symbol == "LATCHCO")
    assert kaynes.no_fresh_positions is True
    assert kaynes.headroom_shares is None
    # And the formula would still have produced a POSITIVE number for it, which is why the
    # field is None rather than that number.
    assert 0.95 * kaynes.mwpl - kaynes.futeq_oi > 0


def test_a_normal_row_carries_nses_own_headroom():
    row = next(r for r in parse_mwpl_file(SAMPLE) if r.symbol == "HEADCO")
    assert row.no_fresh_positions is False
    assert row.headroom_shares == 51_999_999
    # NSE truncates to whole shares, so its figure is just under the exact formula.
    exact = 0.95 * row.mwpl - row.futeq_oi
    assert 0 <= exact - row.headroom_shares < 1


def test_futeq_oi_is_fractional_and_mwpl_is_not():
    """FutEq OI is a sum of delta-weighted positions, so it cannot be an integer type."""
    row = next(r for r in parse_mwpl_file(SAMPLE) if r.symbol == "LATCHCO")
    assert isinstance(row.mwpl, int)
    assert isinstance(row.notional_oi, int)
    assert isinstance(row.futeq_oi, float)
    assert row.futeq_oi % 1 != 0


def test_a_zip_and_its_csv_give_the_same_rows(tmp_path):
    """NSE ships a zip holding the CSV and a malformed XML copy of the same records.

    The XML's element name is `<Future Equivalent Open Interest>`, with spaces, so no
    conforming parser can read it. The member must be chosen by name, not by position.
    """
    import zipfile

    archive = tmp_path / "combineoi_sample.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(
            "combineoi_sample.xml",
            "<MWPL_Viols><MWPL><Future Equivalent Open Interest>1"
            "</Future Equivalent Open Interest></MWPL></MWPL_Viols>",
        )
        z.write(SAMPLE, "combineoi_sample.csv")

    assert parse_mwpl_file(archive) == parse_mwpl_file(SAMPLE)


def test_a_renamed_column_is_refused(tmp_path):
    """The 7 Dec 2026 format cutover is a known date for exactly this."""
    header = MWPL_HEADER.replace("Future Equivalent Open Interest", "FutEq OI")
    path = write_mwpl(tmp_path, NORMAL_ROW, header=header)
    with pytest.raises(ValueError, match="missing column"):
        parse_mwpl_file(path)


def test_two_trade_dates_in_one_file_are_refused(tmp_path):
    path = write_mwpl(tmp_path, NORMAL_ROW, BARRED_ROW.replace("30-OCT-2026", "29-OCT-2026"))
    with pytest.raises(ValueError, match="different trade dates"):
        parse_mwpl_file(path)


def test_a_repeated_isin_is_refused(tmp_path):
    path = write_mwpl(tmp_path, NORMAL_ROW, NORMAL_ROW)
    with pytest.raises(ValueError, match="more than once"):
        parse_mwpl_file(path)


def test_an_unreadable_limit_value_is_refused(tmp_path):
    """Neither a whole number of shares nor the sentence NSE uses."""
    path = write_mwpl(tmp_path, NORMAL_ROW.replace("51999999", "Under Review"))
    with pytest.raises(ValueError, match="neither a whole number"):
        parse_mwpl_file(path)


def test_an_index_row_is_refused(tmp_path):
    """DECISIONS.md #011: state is keyed on ISIN, and indices have none.

    MWPL does not apply to them - they are governed by SPEC.md row 13's index position
    limits - so they are absent from this file. A row with `ISIN = NA` means something
    changed, and a store that accepts rows it cannot key will return the wrong one.
    """
    path = write_mwpl(tmp_path, "30-10-2026,NA,NA,BANKNIFTY,30000000,30000000,6000000.25,1")
    with pytest.raises(ValueError, match="no ISIN"):
        parse_mwpl_file(path)


def test_both_nse_date_formats_are_accepted(tmp_path):
    """`combineoi` writes 30-OCT-2026 and `combineoi_deleq` writes 30-10-2026."""
    path = write_mwpl(tmp_path, NORMAL_ROW.replace("30-OCT-2026", "30-10-2026"))
    assert parse_mwpl_file(path)[0].trade_date == dt.date(2026, 10, 30)


def test_a_file_with_no_data_rows_is_refused(tmp_path):
    path = write_mwpl(tmp_path)
    with pytest.raises(ValueError, match="no data rows"):
        parse_mwpl_file(path)


def test_the_result_is_a_tuple_of_frozen_rows():
    rows = parse_mwpl_file(SAMPLE)
    assert isinstance(rows, tuple)
    with pytest.raises(AttributeError):
        rows[0].mwpl = 1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# The DataFrame boundary, and what it gives up
# ---------------------------------------------------------------------------


def test_as_dataframe_turns_none_into_nan_and_that_is_the_risk():
    """Documents that the decision-1 protection does NOT survive the conversion.

    `headroom_shares` is `int | None`. pandas has no integer column that holds `None`, so
    the column becomes float64 and every None becomes NaN - and pandas skips NaN silently.
    A sum or mean over the column therefore covers only the unbarred rows while looking
    like it covers all of them. In pure Python the same sum raises.

    This test asserts the current behaviour so that it fails loudly if the representation
    ever changes, and so the risk is written down somewhere executable.
    """
    rows = parse_mwpl_file(SAMPLE)
    df = as_dataframe(rows)

    assert len(df) == 3
    assert df["headroom_shares"].dtype == "float64"
    assert df["headroom_shares"].isna().sum() == 2

    # pandas quietly aggregates over 1 row, not 3:
    assert df["headroom_shares"].count() == 1
    assert df["headroom_shares"].sum() == 51_999_999

    # Pure Python refuses the same thing, which is why None was chosen:
    with pytest.raises(TypeError):
        sum(r.headroom_shares for r in rows)  # type: ignore[misc]
