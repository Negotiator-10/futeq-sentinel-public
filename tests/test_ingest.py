"""Tests for `sentinel.ingest` - loading NSE's files into the store and forecasting from them.

These are the functions a pipeline runner calls. The runner itself is `PLAN.md` D5 and is
Chintamani's to write, so nothing here orchestrates: no retries, no dependency graph, no run
log. What is tested is the part the runner stands on, and in particular the two properties that
make a re-run safe:

* loading the same file twice is a no-op, not a duplicate and not an error;
* loading a *different* file for a day already stored is a conflict, reported with both values,
  because an input that changed under us is a finding rather than something to overwrite.

The fixtures are the real ones in `tests/fixtures/transitions/`, so these tests exercise the
actual 12-14 Oct transition rather than invented rows.
"""

from __future__ import annotations

import csv
import datetime as dt
import zipfile
from pathlib import Path

import pytest

from sentinel.calendar import load_calendar
from sentinel.ingest import (
    IngestError,
    ForecastSummary,
    load_official_day,
    record_forecast_day,
    sha256_of,
)
from sentinel.rules import load_rules
from sentinel.store import BanStateStore, Source, StoreError

FIXTURES = Path(__file__).parent / "fixtures" / "transitions"

OCT12 = dt.date(2026, 10, 12)
OCT13 = dt.date(2026, 10, 13)
OCT14 = dt.date(2026, 10, 14)


@pytest.fixture(scope="module")
def rules():
    return load_rules(warn=False)


@pytest.fixture(scope="module")
def calendar():
    return load_calendar()


@pytest.fixture(scope="module")
def fixture_rows() -> dict[dt.date, list[dict]]:
    """The selected combineoi rows, grouped by date."""
    out: dict[dt.date, list[dict]] = {}
    with (FIXTURES / "combineoi_rows.csv").open(encoding="utf-8", newline="") as fh:
        for rec in csv.DictReader(fh):
            out.setdefault(dt.date.fromisoformat(rec["trade_date"]), []).append(rec)
    return out


def build_combineoi(tmp_path: Path, day: dt.date, rows: list[dict]) -> Path:
    """Write a real `combineoi` zip for one day from the fixture rows.

    Built here rather than committed because the CI data-hygiene gate blocks `.zip` - the same
    reason `test_parsers.py` builds its archive in `tmp_path`.
    """
    stamp = day.strftime("%d%m%Y")
    csv_name = f"combineoi_{stamp}.csv"
    header = ("Date,ISIN,Scrip Name,NSE Symbol,MWPL,Open Interest,"
              "Future Equivalent Open Interest,Limit for Next Day")
    lines = [header]
    for r in rows:
        limit = "No Fresh Positions" if r["no_fresh_positions"] == "True" else r["headroom_shares"]
        lines.append(",".join([
            day.strftime("%d-%b-%Y").upper(), r["isin"], r["scrip_name"], r["symbol"],
            r["mwpl"], r["notional_oi"], r["futeq_oi"], limit,
        ]))
    zip_path = tmp_path / f"combineoi_{stamp}.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(csv_name, "\n".join(lines) + "\n")
    return zip_path


@pytest.fixture
def store(tmp_path, calendar):
    with BanStateStore(tmp_path / "state.sqlite", calendar) as s:
        yield s


# -- loading NSE's published state --------------------------------------------------------


def test_a_days_official_state_is_loaded_for_every_scrip(store, tmp_path, fixture_rows):
    """Not only the banned ones.

    "Not in ban" is a fact worth storing: without it a missing row and a free scrip are
    indistinguishable, and `was_in_ban()` would have to guess.
    """
    oi = build_combineoi(tmp_path, OCT12, fixture_rows[OCT12])
    result = load_official_day(store, FIXTURES / "fo_secban_12102026.csv", oi)

    assert result.written == len(fixture_rows[OCT12])
    assert result.unchanged == 0
    banned = store.official_ban_set(OCT12)
    assert len(banned) == 3                      # AMBUJACEM, BANDHANBNK, LICHSGFIN
    assert len(banned) < result.written           # the free ones are stored too


def test_the_ban_list_and_the_combineoi_must_be_the_same_day(store, tmp_path, fixture_rows):
    """A mismatch is a mis-named download, which has already happened once in this project."""
    oi = build_combineoi(tmp_path, OCT13, fixture_rows[OCT13])
    with pytest.raises(IngestError, match="date mismatch"):
        load_official_day(store, FIXTURES / "fo_secban_12102026.csv", oi)


def test_a_banned_symbol_that_cannot_be_resolved_stops_the_run(store, tmp_path, fixture_rows):
    """#011 Q2: a banned scrip that cannot be identified is the worst thing to drop silently.

    It under-reports a real ban, which is the error direction that gets a desk fined. So the
    run stops rather than skipping the row.
    """
    thinned = [r for r in fixture_rows[OCT12] if r["symbol"] != "AMBUJACEM"]
    oi = build_combineoi(tmp_path, OCT12, thinned)
    with pytest.raises(IngestError, match="AMBUJACEM"):
        load_official_day(store, FIXTURES / "fo_secban_12102026.csv", oi)


def test_the_record_carries_the_hash_of_the_file_it_came_from(store, tmp_path, fixture_rows):
    oi = build_combineoi(tmp_path, OCT12, fixture_rows[OCT12])
    ban_path = FIXTURES / "fo_secban_12102026.csv"
    load_official_day(store, ban_path, oi)

    out = store.dump_csv(OCT12, tmp_path / "day.csv")
    text = out.read_text(encoding="utf-8")
    assert sha256_of(ban_path) in text
    assert "nse" in text


# -- safe re-runs -------------------------------------------------------------------------


def test_loading_the_same_day_twice_is_a_no_op(store, tmp_path, fixture_rows):
    """What makes a re-run safe. Not a duplicate, and not an error."""
    oi = build_combineoi(tmp_path, OCT12, fixture_rows[OCT12])
    first = load_official_day(store, FIXTURES / "fo_secban_12102026.csv", oi)
    second = load_official_day(store, FIXTURES / "fo_secban_12102026.csv", oi)

    assert first.written > 0 and first.was_a_no_op is False
    assert second.written == 0
    assert second.unchanged == first.written
    assert second.was_a_no_op is True


def test_a_changed_input_for_a_stored_day_is_a_conflict(store, tmp_path, fixture_rows):
    """An input that changed under us is a finding, not something to overwrite silently."""
    oi = build_combineoi(tmp_path, OCT12, fixture_rows[OCT12])
    load_official_day(store, FIXTURES / "fo_secban_12102026.csv", oi)

    # the 13 Oct list for the 12 Oct date: KAYNES is in ban on the 13th and was not on the 12th
    forged = tmp_path / "forged.csv"
    forged.write_text(
        "Securities in Ban For Trade Date 12-OCT-2026:\n1,AMBUJACEM\n2,BANDHANBNK\n"
        "3,KAYNES\n4,LICHSGFIN\n",
        encoding="utf-8",
    )
    with pytest.raises(StoreError, match="different official value"):
        load_official_day(store, forged, oi)

    # and nothing moved: the stored day is still the original
    assert "KAYNES" not in {r[1] for r in store.scored_forecasts(OCT12) if r[3]}


def test_replace_is_available_but_has_to_be_asked_for(store, tmp_path, fixture_rows):
    oi = build_combineoi(tmp_path, OCT12, fixture_rows[OCT12])
    load_official_day(store, FIXTURES / "fo_secban_12102026.csv", oi)
    forged = tmp_path / "forged.csv"
    forged.write_text(
        "Securities in Ban For Trade Date 12-OCT-2026:\n1,AMBUJACEM\n2,BANDHANBNK\n"
        "3,KAYNES\n4,LICHSGFIN\n",
        encoding="utf-8",
    )
    result = load_official_day(store, forged, oi, replace=True)
    assert result.written > 0
    assert "KAYNES" in {
        r[1] for r in store.scored_forecasts(OCT12) if r[3]
    }


# -- forecasting from a stored day --------------------------------------------------------


def test_the_forecast_is_written_into_the_next_trading_days_row(store, tmp_path, fixture_rows, rules):
    """The forecast computed after 12 Oct's close is about the 13th, so it lives in the 13th.

    NSE's own published answer for the 13th lands in that same row later, which is what makes
    a scored pair one record rather than two.
    """
    oi12 = build_combineoi(tmp_path, OCT12, fixture_rows[OCT12])
    load_official_day(store, FIXTURES / "fo_secban_12102026.csv", oi12)

    summary = record_forecast_day(store, oi12, rules)
    assert isinstance(summary, ForecastSummary)
    assert summary.measurement_date == OCT12
    assert summary.effective_date == OCT13
    assert summary.refused_count == 0
    assert "KAYNES" in summary.forecast_banned          # the 13 Oct entry, at 97.98%

    rows = {sym: (f, o) for _, sym, f, o in store.scored_forecasts(OCT13)}
    assert rows["KAYNES"] == (True, None)               # forecast present, answer not yet loaded


def test_the_forecast_and_the_answer_meet_in_one_record(store, tmp_path, fixture_rows, rules):
    oi12 = build_combineoi(tmp_path, OCT12, fixture_rows[OCT12])
    oi13 = build_combineoi(tmp_path, OCT13, fixture_rows[OCT13])
    load_official_day(store, FIXTURES / "fo_secban_12102026.csv", oi12)
    record_forecast_day(store, oi12, rules)
    load_official_day(store, FIXTURES / "fo_secban_13102026.csv", oi13)

    scored = [(s, f, o) for _, s, f, o in store.scored_forecasts(OCT13)
              if f is not None and o is not None]
    assert len(scored) == len(fixture_rows[OCT13])
    assert all(f == o for _, f, o in scored), [x for x in scored if x[1] != x[2]]


def test_forecasting_a_day_with_no_stored_state_refuses(store, tmp_path, fixture_rows, rules):
    """A day-level failure, so it stops rather than guessing a seed for every scrip."""
    oi = build_combineoi(tmp_path, OCT12, fixture_rows[OCT12])
    with pytest.raises(StoreError, match="not the same as no bans"):
        record_forecast_day(store, oi, rules)


def test_a_scrip_with_no_prior_state_is_refused_only_inside_the_band(
    store, tmp_path, fixture_rows, rules
):
    """#012's rule, applied per scrip rather than per day.

    Outside the 80-95% band the prior state cannot change the answer, so those scrips are still
    forecast. Inside it they are refused by name and the rest of the day completes - 7 of 218
    on the real file, not 218 of 218.
    """
    # Load 12 Oct's official state from a combineoi missing the two band controls, so those two
    # end up with no stored prior state while every other scrip has one. None of the three
    # banned symbols is affected, so the load still resolves.
    partial_dir = tmp_path / "partial"
    partial_dir.mkdir()
    partial = [r for r in fixture_rows[OCT12] if r["symbol"] not in ("MANAPPURAM", "INOXWIND")]
    oi_partial = build_combineoi(partial_dir, OCT12, partial)
    load_official_day(store, FIXTURES / "fo_secban_12102026.csv", oi_partial)

    # then forecast from the full file, so those two scrips are present but unseeded
    oi = build_combineoi(tmp_path, OCT12, fixture_rows[OCT12])

    summary = record_forecast_day(store, oi, rules)
    refused = {sym for sym, _ in summary.refused}

    # both are in the band on 12 Oct (86.47% and 85.54%), so both are refused
    assert refused == {"MANAPPURAM", "INOXWIND"}, refused
    # and the rest of the day still completed
    assert summary.write.written == len(fixture_rows[OCT12]) - 2


def test_a_stored_forecast_is_invisible_as_a_seed(store, tmp_path, fixture_rows, rules):
    """#012 decision 2 at the ingest layer, and the behaviour is subtler than "it raises".

    After forecasting from 12 Oct, the 13 Oct rows hold a forecast and no official value. Now
    forecast from 13 Oct. The engine does not read that stored forecast - it cannot, the store
    has no method that returns one as a prior state - so it finds no seed at all and applies
    #012's rule instead: scrips inside the 80-95% band are refused by name, scrips outside it
    are still answered because there the prior state cannot change the answer.

    The assertion that proves the forecast stayed invisible is that **every** in-band scrip is
    refused. If even one had been seeded from the stored forecast, it would have an answer.
    """
    oi12 = build_combineoi(tmp_path, OCT12, fixture_rows[OCT12])
    oi13 = build_combineoi(tmp_path, OCT13, fixture_rows[OCT13])
    load_official_day(store, FIXTURES / "fo_secban_12102026.csv", oi12)
    record_forecast_day(store, oi12, rules)

    stored_forecasts = {s: f for _, s, f, o in store.scored_forecasts(OCT13)}
    assert any(f for f in stored_forecasts.values()), "13 Oct should hold forecasts by now"
    assert all(o is None for _, _, _, o in store.scored_forecasts(OCT13))

    summary = record_forecast_day(store, oi13, rules)
    assert summary.effective_date == OCT14

    entry = rules.get("single_stock.ban.entry_utilisation")
    exit_ = rules.get("single_stock.ban.exit_utilisation")
    in_band = {
        r["symbol"] for r in fixture_rows[OCT13]
        if not entry.compare(float(r["futeq_oi"]) / int(r["mwpl"]))
        and not exit_.compare(float(r["futeq_oi"]) / int(r["mwpl"]))
    }
    assert in_band, "the 13 Oct fixture should contain in-band scrips"
    assert {sym for sym, _ in summary.refused} == in_band
    assert all("no prior state" in why for _, why in summary.refused)

    # and the scrips outside the band were still answered, so the day was not lost
    assert summary.write.written == len(fixture_rows[OCT13]) - len(in_band)
