"""A flat day: verified-nothing-held, kept distinct from a file that never arrived.

`DECISIONS.md` #015. The first version of `check_ban_period_reduction()` took `PropBook | None`,
with `None` meaning "verified flat". The natural way to fetch a book - `books.get(day)` - also
returns `None` when the file is missing, so the two facts shared a value, and on the real day-5
breach a missing today-file came back `permitted=True` with the reason "held or reduced toward
zero". Every holder looked as though they had closed out.

The fix keeps three conditions as three representations:

    positions were held          PropBook([...])
    verified: nothing was held   PropBook.flat(trade_date), built from a FLAT marker row
    the file never arrived       no PropBook - and `books[day]` raises KeyError

A flat day is written into the positions file itself as one marker row, so the file is the
authority for its own date - not the filename, which `combineoi_13102026 (1).zip` showed can be
mangled, and not a date the caller states, which nothing in the file could contradict.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from sentinel.book import BookError, Instrument, Position, PropBook, futeq_delta, load_book, load_books

HEADER = "trade_date,tm,ucc,isin,instrument,expiry,strike,lot_size,quantity_lots\n"
DAY = dt.date(2026, 10, 30)


def write(tmp_path, body: str):
    p = tmp_path / "positions.csv"
    p.write_text(HEADER + body, encoding="utf-8")
    return p


# -- the three conditions stay three ------------------------------------------------------


def test_a_flat_marker_row_becomes_a_dated_empty_book(tmp_path):
    book = load_book(write(tmp_path, "2026-10-30,,,,FLAT,,,,\n"))
    assert book.is_flat
    assert len(book) == 0
    assert book.trade_date == DAY


def test_an_empty_list_is_still_refused():
    """What a missing file produces by accident. Only `.flat(date)` makes an empty book."""
    with pytest.raises(BookError, match="PropBook.flat"):
        PropBook([])


def test_a_missing_day_is_a_key_error_not_a_flat_book(tmp_path):
    """The point of the whole change: the natural lookup now fails loudly.

    Under the old signature `books.get(day)` returned None and the check read it as flat. With
    non-optional parameters the caller has to write `books[day]`, and a missing day raises.
    """
    books = load_books(write(tmp_path, "2026-10-30,,,,FLAT,,,,\n"))
    assert DAY in books
    with pytest.raises(KeyError):
        books[dt.date(2026, 10, 29)]


def test_a_flat_book_behaves_like_an_empty_one_everywhere_downstream(tmp_path):
    """So the `if book else ()` branches in the check can go."""
    book = load_book(write(tmp_path, "2026-10-30,,,,FLAT,,,,\n"))
    assert book.for_account("TMA", "UCC001", "INE114A01011") == ()
    assert list(book) == []
    assert book.accounts == () and book.isins == ()

    from sentinel.book import DeltaFactors
    assert futeq_delta(book, DeltaFactors(DAY, {}), {}) == Decimal(0)


def test_a_flat_yesterday_still_has_a_date_to_check(tmp_path):
    """Why the date matters: the previous-trading-day check needs two dates even when
    yesterday was flat, and under `None` there was nothing to compare."""
    yesterday = load_book(write(tmp_path, "2026-10-29,,,,FLAT,,,,\n"))
    assert yesterday.trade_date == dt.date(2026, 10, 29)


def test_flat_and_held_days_can_share_a_multi_day_file(tmp_path):
    books = load_books(write(
        tmp_path,
        "2026-10-29,,,,FLAT,,,,\n"
        "2026-10-30,TMA,UCC001,INE114A01011,FF,2026-11-23,0,1000,1\n",
    ))
    assert books[dt.date(2026, 10, 29)].is_flat
    assert not books[DAY].is_flat
    assert list(books) == [dt.date(2026, 10, 29), DAY]


# -- the four refusals ---------------------------------------------------------------------


def test_a_flat_row_beside_positions_for_the_same_day_is_refused(tmp_path):
    """The file contradicts itself about that day, so neither statement can be trusted.
    Checked after reading, because the position row may come after the marker."""
    with pytest.raises(BookError, match="contradicts itself"):
        load_books(write(
            tmp_path,
            "2026-10-30,,,,FLAT,,,,\n"
            "2026-10-30,TMA,UCC001,INE114A01011,FF,2026-11-23,0,1000,1\n",
        ))


def test_a_second_flat_row_for_one_day_is_refused(tmp_path):
    with pytest.raises(BookError, match="second FLAT row"):
        load_books(write(tmp_path, "2026-10-30,,,,FLAT,,,,\n2026-10-30,,,,FLAT,,,,\n"))


@pytest.mark.parametrize("row", [
    "2026-10-30,,UCC001,,FLAT,,,,\n",
    "2026-10-30,,,INE114A01011,FLAT,,,,\n",
    "2026-10-30,,,,FLAT,,,,1\n",
    "2026-10-30,,,,FLAT,2026-11-23,,,\n",
    "2026-10-30,TMA,,,FLAT,,,,\n",          # the tm column, added 8 Nov, must be blank too
])
def test_a_flat_row_with_any_other_field_filled_is_refused(tmp_path, row):
    """Overloading the instrument column is safe only because of this refusal. A half-written
    position row carrying FLAT in the wrong column must not pass as "nothing was held"."""
    with pytest.raises(BookError, match="must carry only a date"):
        load_books(write(tmp_path, row))


def test_a_header_with_no_rows_is_refused(tmp_path):
    """A truncated or failed write looks exactly like this, so it is not a flat day."""
    with pytest.raises(BookError, match="header and no rows"):
        load_books(write(tmp_path, ""))


def test_a_flat_row_with_an_unreadable_date_is_refused(tmp_path):
    with pytest.raises(BookError, match="is not YYYY-MM-DD"):
        load_books(write(tmp_path, "30-10-2026,,,,FLAT,,,,\n"))


def test_the_marker_is_case_insensitive_but_nothing_else_is_loosened(tmp_path):
    assert load_book(write(tmp_path, "2026-10-30,,,,flat,,,,\n")).is_flat
