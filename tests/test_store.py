"""Tests for `sentinel.calendar` and `sentinel.store`.

Grouped by what each defends:

* the calendar's three states, and that an empty one refuses rather than assuming weekdays;
* that walking the calendar never steps over an unknown date - the bug this module exists for;
* the store's invariants, enforced by the schema where possible so no caller has to remember;
* that there is no way to read a forecast forward as a prior state;
* two tests that document a limitation rather than a guarantee, including the Muhurat session
  on 8 Nov 2026, which is a decision still open.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

import pytest

from sentinel.calendar import (
    CalendarError,
    ChainUnverifiedError,
    DayKind,
    TradingCalendar,
    load_calendar,
    UnknownDateError,
)
from sentinel.store import BanStateStore, Source, StateRecord, StoreError

SHA = "a" * 64

# A verified week: Mon 12 to Fri 16 Oct 2026 trading, the weekend a holiday, Tue 20 Oct a
# holiday (Dussehra), and Mon 19 / Wed 21 Oct trading. 20 Oct is a holiday HERE because the
# test says so; in the project it is UNKNOWN until NSE's own list is in the repo.
MON12 = dt.date(2026, 10, 12)
TUE13 = dt.date(2026, 10, 13)
FRI16 = dt.date(2026, 10, 16)
MON19 = dt.date(2026, 10, 19)
TUE20 = dt.date(2026, 10, 20)
WED21 = dt.date(2026, 10, 21)


@pytest.fixture
def cal() -> TradingCalendar:
    trading = [MON12, TUE13, dt.date(2026, 10, 14), dt.date(2026, 10, 15), FRI16, MON19, WED21]
    holidays = [dt.date(2026, 10, 17), dt.date(2026, 10, 18), TUE20]
    return TradingCalendar.from_sessions(trading, holidays, source="test fixture")


@pytest.fixture
def store(tmp_path, cal) -> BanStateStore:
    with BanStateStore(tmp_path / "state.sqlite", cal) as s:
        yield s


def rec(isin="INE000000001", day=TUE13, symbol="TESTCO", *, official=False,
        forecast=None, source=Source.NSE, sha=SHA, note="") -> StateRecord:
    return StateRecord(isin=isin, trade_date=day, symbol=symbol, official=official,
                       forecast=forecast, source=source, input_sha256=sha, note=note)


# -- the calendar's three states ----------------------------------------------------------


def test_an_empty_calendar_knows_nothing_and_says_so():
    """It does not default to "weekdays are trading days", which is inference in a better coat."""
    empty = TradingCalendar({})
    assert len(empty) == 0
    assert empty.covered is None
    assert empty.kind(TUE13) is DayKind.UNKNOWN
    with pytest.raises(UnknownDateError):
        empty.is_trading_day(TUE13)
    with pytest.raises(UnknownDateError, match="calendar is empty"):
        empty.next_trading_day(TUE13)


def test_kind_never_raises_but_is_trading_day_does(cal):
    # Two doors, the same shape as Rules.describe() versus Rules.get(): one to ask safely for a
    # report, one that refuses so the engine cannot proceed on a guess.
    far_future = dt.date(2027, 1, 1)
    assert cal.kind(far_future) is DayKind.UNKNOWN
    with pytest.raises(UnknownDateError):
        cal.is_trading_day(far_future)


def test_the_three_states_are_distinguishable(cal):
    assert cal.kind(MON12) is DayKind.TRADING
    assert cal.kind(TUE20) is DayKind.HOLIDAY
    assert cal.kind(dt.date(2026, 11, 30)) is DayKind.UNKNOWN


def test_unknown_cannot_be_written_down():
    """UNKNOWN is the absence of a record, not a record.

    Storing it would make an unverified date look verified, which is the whole failure this
    three-state design prevents.
    """
    with pytest.raises(CalendarError, match="absence of a record"):
        TradingCalendar({TUE13: DayKind.UNKNOWN})


def test_a_date_in_both_lists_is_a_contradiction_not_a_precedence_rule():
    with pytest.raises(CalendarError, match="both a trading day and a holiday"):
        TradingCalendar.from_sessions([MON12], [MON12])


# -- walking it: the bug this module exists for -------------------------------------------


def test_the_weekend_is_stepped_over_because_it_is_verified(cal):
    assert cal.next_trading_day(FRI16) == MON19
    assert cal.previous_trading_day(MON19) == FRI16


def test_a_verified_holiday_is_stepped_over(cal):
    # 20 Oct is a holiday in this fixture, so Monday's next trading day is Wednesday.
    assert cal.next_trading_day(MON19) == WED21
    assert cal.previous_trading_day(WED21) == MON19


def test_an_unknown_date_is_never_stepped_over():
    """The bug in one test.

    `scripts/score_bans.py` originally took "next trading day" to mean "next date with a file".
    Hide one ban list and it scored 14 Oct's forecast against 16 Oct's published answer, skipped
    the 15th, and still reported zero errors. Here the unknown date refuses instead.
    """
    cal = TradingCalendar.from_sessions([MON19, WED21], [])  # nothing said about 20 Oct
    assert cal.kind(TUE20) is DayKind.UNKNOWN
    with pytest.raises(UnknownDateError, match="not in the verified calendar"):
        cal.next_trading_day(MON19)
    with pytest.raises(UnknownDateError, match="silently move the answer"):
        cal.previous_trading_day(WED21)


def test_running_off_the_end_of_the_calendar_refuses(cal):
    with pytest.raises(UnknownDateError, match="ran off the end"):
        cal.next_trading_day(WED21)
    with pytest.raises(UnknownDateError, match="ran off the start"):
        cal.previous_trading_day(MON12)


# -- the store's invariants ---------------------------------------------------------------


def test_a_day_is_written_and_read_back(store):
    n = store.record_day((rec(official=True), rec(isin="INE000000002", symbol="OTHER")))
    assert n == 2
    assert store.has_day(TUE13)
    assert store.dates() == (TUE13,)
    assert store.was_in_ban("INE000000001", TUE13) is True
    assert store.was_in_ban("INE000000002", TUE13) is False


def test_the_primary_key_makes_a_duplicate_day_impossible(store):
    store.record_day((rec(),))
    with pytest.raises(StoreError, match="already exists"):
        store.record_day((rec(official=True),))
    # and the original survives: the failed write changed nothing
    assert store.was_in_ban("INE000000001", TUE13) is False


def test_a_duplicate_inside_one_batch_names_the_symbol(store):
    with pytest.raises(StoreError, match="appears twice"):
        store.record_day((rec(symbol="FIRST"), rec(symbol="SECOND")))


def test_a_day_is_written_all_or_nothing(store):
    """One transaction, so a crash part-way cannot leave half a day behind."""
    good = rec(isin="INE000000001")
    clash = rec(isin="INE000000001", symbol="CLASH")
    with pytest.raises(StoreError):
        store.record_day((good, clash))
    assert not store.has_day(TUE13)


def test_two_dates_in_one_batch_are_refused(store):
    with pytest.raises(StoreError, match="given 2 dates"):
        store.record_day((rec(day=TUE13), rec(day=MON12, isin="INE000000002")))


def test_a_holiday_with_data_is_refused(store):
    """Your four-case matrix: holiday plus a file is a contradiction, so the run stops."""
    with pytest.raises(StoreError, match="holiday"):
        store.record_day((rec(day=TUE20),))


def test_an_unknown_date_is_refused(store):
    with pytest.raises(UnknownDateError, match="no verified calendar"):
        store.record_day((rec(day=dt.date(2026, 12, 1)),))


def test_the_schema_rejects_a_bad_source_even_by_raw_sql(store):
    """The CHECK constraint, not just the enum.

    The enum stops a caller passing nonsense through the API; the constraint stops anything
    else - a migration, a repair script, a person with a database client.
    """
    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            "INSERT INTO ban_state (isin, trade_date, symbol, official, forecast, source, "
            "input_sha256, note, written_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("INE000000009", TUE13.isoformat(), "X", 1, None, "guess", SHA, "", "now"),
        )


def test_a_record_with_nothing_in_it_is_refused():
    with pytest.raises(StoreError, match="says nothing"):
        rec(official=None, forecast=None)


def test_an_nse_record_must_carry_an_official_value():
    with pytest.raises(StoreError, match="published fact with no value"):
        rec(official=None, forecast=True, source=Source.NSE)


def test_an_index_row_is_refused():
    # #011 Q2: indices carry ISIN "NA" and MWPL does not apply to them.
    for bad in ("NA", "nan", "-", ""):
        with pytest.raises(StoreError, match="Index rows"):
            rec(isin=bad)


def test_a_record_without_a_file_hash_is_refused():
    with pytest.raises(StoreError, match="names the file it came from"):
        rec(sha="deadbeef")


# -- the forecast cannot be read forward --------------------------------------------------


def test_there_is_no_way_to_read_a_forecast_as_a_prior_state(store):
    """#012 decision 2, enforced by the API rather than by documentation.

    A wrong ban flag latches instead of decaying - two seeds on a flat path at SAIL's
    utilisation agreed on 0 of 20 days - so the unsafe call does not exist. The only reader
    that returns a single boolean is `was_in_ban()`, and it reads `official`.
    """
    store.record_day((rec(official=False, forecast=True, source=Source.COMPUTED),))

    assert store.was_in_ban("INE000000001", TUE13) is False  # official, not the forecast

    single_value_readers = [
        name for name in dir(store)
        if not name.startswith("_") and "forecast" in name.lower()
    ]
    assert single_value_readers == ["scored_forecasts"], (
        f"a new forecast reader appeared: {single_value_readers}. If it returns a bare bool it "
        f"can be used as a seed, which is the feedback loop #012 forbids."
    )


def test_a_missing_official_value_refuses_rather_than_falling_back(store):
    store.record_day((rec(official=None, forecast=True, source=Source.COMPUTED),))
    with pytest.raises(StoreError, match="never loaded"):
        store.was_in_ban("INE000000001", TUE13)


def test_a_missing_day_refuses_rather_than_answering_free(store):
    with pytest.raises(StoreError, match="not 'free'"):
        store.was_in_ban("INE000000001", TUE13)


def test_no_bans_and_nothing_stored_are_different(store):
    with pytest.raises(StoreError, match="not the same as no bans"):
        store.official_ban_set(TUE13)
    store.record_day((rec(official=False),))
    assert store.official_ban_set(TUE13) == frozenset()


def test_the_seed_comes_from_the_previous_trading_day_not_the_last_day_with_rows(store):
    """Mon 19 Oct's seed is Fri 16 Oct's official set, even with rows for Mon 12 present."""
    store.record_day((rec(day=MON12, official=True),))
    store.record_day((rec(day=FRI16, official=False),))
    assert store.seed_for(MON19) == frozenset()

    # and with 16 Oct absent it refuses, rather than reaching back to the 12th
    fresh_cal = store.calendar
    with BanStateStore(store.path.parent / "other.sqlite", fresh_cal) as s2:
        s2.record_day((rec(day=MON12, official=True),))
        with pytest.raises(StoreError, match="no state stored for 2026-10-16"):
            s2.seed_for(MON19)


# -- inspection ---------------------------------------------------------------------------


def test_a_day_dumps_to_csv_because_sqlite_is_opaque_to_a_person(store, tmp_path):
    store.record_day((rec(official=True, forecast=True, source=Source.COMPUTED, note="held"),))
    out = store.dump_csv(TUE13, tmp_path / "day.csv")
    text = out.read_text(encoding="utf-8")
    assert "TESTCO" in text and "computed" in text and "held" in text
    assert SHA in text


def test_scored_forecasts_returns_both_columns_together(store):
    store.record_day((rec(official=True, forecast=False, source=Source.COMPUTED),))
    rows = list(store.scored_forecasts(TUE13))
    assert rows == [("INE000000001", "TESTCO", False, True)]


# -- limitations, recorded rather than guaranteed -----------------------------------------


MUHURAT = dt.date(2026, 11, 8)


def test_a_special_session_is_a_state_not_a_flag():
    """Muhurat trading, Sun 8 Nov 2026, from NSE/FAOP/71777.

    The circular lists it as a Sunday holiday and says in the same breath that "Muhurat Trading
    will be conducted" that day. Three states could not express that: whichever way the date was
    classified, it came out as "non-trading day with data" and the run stopped.
    """
    cal = load_calendar()
    assert cal.kind(MUHURAT) is DayKind.SPECIAL_SESSION
    assert cal.special_sessions == (MUHURAT,)

    # a session happened, so its files are real - but it is not a normal trading day
    assert cal.has_session(MUHURAT) is True
    assert cal.is_trading_day(MUHURAT) is False


def test_a_special_sessions_data_is_stored(tmp_path):
    cal = load_calendar()
    with BanStateStore(tmp_path / "s.sqlite", cal) as s:
        s.record_day((rec(day=MUHURAT, official=True),))
        assert s.has_day(MUHURAT)
        assert s.was_in_ban("INE000000001", MUHURAT) is True


def test_chaining_through_an_unverified_special_session_refuses():
    """The decision: accept the files, refuse to chain until the chaining is verified.

    A flag on a trading day would have answered "yes, it chains" by default. The open question
    is whether 8 Nov counts as the previous trading day for the 9th, and nothing has established
    that yet - so both directions refuse, and Monday's run fails closed rather than resting on
    a guess.
    """
    cal = load_calendar()
    with pytest.raises(ChainUnverifiedError, match="place in the chain is not verified"):
        cal.previous_trading_day(dt.date(2026, 11, 9))
    with pytest.raises(ChainUnverifiedError, match="undecided"):
        cal.next_trading_day(dt.date(2026, 11, 6))


def test_a_verified_special_session_chains_normally():
    """Once observation settles it, the date is passed in and the walk resolves."""
    cal = load_calendar(chaining_verified=[MUHURAT])
    assert cal.previous_trading_day(dt.date(2026, 11, 9)) == MUHURAT
    assert cal.next_trading_day(dt.date(2026, 11, 6)) == MUHURAT


def test_chaining_verified_cannot_name_an_ordinary_day():
    # Only a special session has chaining to verify; naming a Tuesday would be meaningless and
    # would quietly suggest the mechanism applies more widely than it does.
    with pytest.raises(CalendarError, match="not special sessions"):
        load_calendar(chaining_verified=[dt.date(2026, 11, 9)])


def test_the_store_refuses_a_special_session_whose_seed_would_need_chaining(tmp_path):
    """The two halves together: the data goes in, the seed for the next day does not come out."""
    cal = load_calendar()
    with BanStateStore(tmp_path / "s.sqlite", cal) as s:
        s.record_day((rec(day=MUHURAT, official=True),))
        with pytest.raises(ChainUnverifiedError):
            s.seed_for(dt.date(2026, 11, 9))


# -- the real calendar, loaded from the circular -------------------------------------------


def test_the_loaded_calendar_covers_the_whole_year():
    cal = load_calendar()
    assert len(cal) == 365
    assert cal.covered == (dt.date(2026, 1, 1), dt.date(2026, 12, 31))


def test_twenty_october_is_a_verified_holiday_now():
    """It was UNKNOWN on 6 Nov, and I wrongly called it a holiday from a 404.

    NSE/FAOP/71777 item 12 says Dussehra. So the walk across it is now a deduction from the
    circular rather than an inference from a failed download.
    """
    cal = load_calendar()
    assert cal.kind(dt.date(2026, 10, 20)) is DayKind.HOLIDAY
    assert cal.next_trading_day(dt.date(2026, 10, 19)) == dt.date(2026, 10, 21)
    assert cal.previous_trading_day(dt.date(2026, 10, 21)) == dt.date(2026, 10, 19)


def test_the_weekend_gap_the_score_script_had_to_assume():
    """30 Oct -> 2 Nov, the one row in the real data resting on an inference. Now verified."""
    cal = load_calendar()
    assert cal.next_trading_day(dt.date(2026, 10, 30)) == dt.date(2026, 11, 2)


def test_a_date_outside_the_covered_year_is_unknown():
    cal = load_calendar()
    assert cal.kind(dt.date(2027, 1, 4)) is DayKind.UNKNOWN
    with pytest.raises(UnknownDateError):
        cal.is_trading_day(dt.date(2027, 1, 4))


def test_every_calendar_row_must_name_its_source(tmp_path):
    # Same rule as config/rules.yaml (#007): a date that cannot say where it came from is not
    # usable, because an unsourced holiday is indistinguishable from a typed guess.
    bad = tmp_path / "cal.csv"
    bad.write_text(
        "\n".join([
            "date,kind,description,source",
            "year_covered,holiday,2026,circular",
            "2026-01-26,holiday,Republic Day,",
        ]) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(CalendarError, match="no source"):
        load_calendar(bad)


def test_a_calendar_without_a_covered_year_is_refused(tmp_path):
    """Without a boundary the complement has no edge, and 2030 would look like trading days."""
    bad = tmp_path / "cal.csv"
    bad.write_text(
        "\n".join([
            "date,kind,description,source",
            "2026-01-26,holiday,Republic Day,circular",
        ]) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(CalendarError, match="year_covered"):
        load_calendar(bad)


def test_the_store_cannot_tell_you_why_a_scrip_is_banned(store):
    """A limitation inherited from `is_in_ban()` returning a bare bool, noted in #011 Q1.

    A scrip banned tonight for the first time and one still banned and holding above 80% both
    store `official = True`, and the alert text for those is not the same sentence. Revisit
    with the alerting work in Week 4.
    """
    store.record_day((rec(official=True),))
    assert store.was_in_ban("INE000000001", TUE13) is True
    # there is no "why", and nothing in the record distinguishes entry from hold
    rows = list(store.scored_forecasts(TUE13))
    assert rows[0][3] is True
