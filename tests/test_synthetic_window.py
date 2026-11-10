"""The ban rule end to end on synthetic files, so CI checks it with no NSE content in the repo.

`DECISIONS.md` #010 addendum keeps NSE's files out of the public repository. The real-data
checks - the 3241/3241 score, the eight real transitions, SAIL's walk out of the ban - still run,
in `tests/test_transitions.py`, but only where `data/` holds NSE's files. This module is what CI
runs instead: three trading days of made-up scrips in NSE's exact file layouts, built so each
row is one of the cases below, and read through the same parsers and engine.

    case                                       row (12 Oct close -> 13 Oct list)
    entry above 95%                            ENTRYCO    97.00%, free  -> banned
    exactly 95.00% stays out                   EDGECO     95.00%, free  -> free
    a hold in the band                         HOLDCO     88.00%, banned -> banned
    a release at exactly 80.00%                RELEASECO  80.00%, banned -> free
    80.01% is held                             STICKYCO   80.01%, banned -> banned
    in-band free stays free                    FREECO     90.00%, free  -> free
                                               RELEASECO  85.00% on 13 Oct, free -> free
    reconciliation residuals 0 and 0.99 pass   QUIETCO (0), FREECO (0.99), EDGECO (0, at 95%)
    a residual of -0.01 fails                  NEGCO in reconcile_failures.csv
    a barred row at or below 80% fails         ATEXITCO (80.00%), BELOWCO (70.00%)
    a missing ban list                         14 Oct has a combineoi file and no ban list
    an unverified special session              a close whose next day runs through one
    a flat day                                 a FLAT marker book, in test_flat.py

The seed for each forecast is that day's published list, resolved to ISINs through that day's
rows; the `no_fresh_positions` flag is never read as an input (#012 decision 5).

Written by Claude to cases Chintamani chose.
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import pytest

from sentinel.calendar import ChainUnverifiedError, load_calendar
from sentinel.calendar import DEFAULT_CALENDAR_PATH
from sentinel.engine import is_in_ban, reconcile, utilisation
from sentinel.parsers import MwplRow, parse_ban_list

WINDOW = Path(__file__).parent / "fixtures" / "synthetic" / "window"
OCT12, OCT13, OCT14 = dt.date(2026, 10, 12), dt.date(2026, 10, 13), dt.date(2026, 10, 14)


@pytest.fixture(scope="module")
def rules():
    from sentinel.rules import load_rules
    return load_rules(warn=False)


def read_rows(path: Path) -> dict[dt.date, dict[str, MwplRow]]:
    """With the csv module, not pandas: pandas reads the string "NA" as missing (see
    test_transitions.read_rows)."""
    out: dict[dt.date, dict[str, MwplRow]] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for rec in csv.DictReader(fh):
            row = MwplRow(
                trade_date=dt.date.fromisoformat(rec["trade_date"]),
                isin=rec["isin"], scrip_name=rec["scrip_name"], symbol=rec["symbol"],
                mwpl=int(rec["mwpl"]), notional_oi=int(rec["notional_oi"]),
                futeq_oi=float(rec["futeq_oi"]),
                no_fresh_positions=rec["no_fresh_positions"] == "True",
                headroom_shares=None if rec["headroom_shares"] == "" else int(rec["headroom_shares"]),
            )
            out.setdefault(row.trade_date, {})[row.symbol] = row
    return out


@pytest.fixture(scope="module")
def rows():
    return read_rows(WINDOW / "combineoi_rows.csv")


@pytest.fixture(scope="module")
def bans():
    return {bl.trade_date: bl.symbols
            for bl in (parse_ban_list(p) for p in sorted(WINDOW.glob("fo_secban_*.csv")))}


def forecast(day, rows, bans, rules) -> set[str]:
    day_rows = rows[day]
    seed = {day_rows[s].isin for s in bans[day] if s in day_rows}
    return {s for s, r in day_rows.items()
            if is_in_ban(r.futeq_oi, r.mwpl, was_in_ban_yesterday=r.isin in seed, rules=rules)}


def u(row: MwplRow) -> float:
    return utilisation(row.futeq_oi, row.mwpl)


# -- the window is what it claims to be --------------------------------------------------


def test_the_window_has_three_days_of_rows_and_two_ban_lists(rows, bans):
    assert sorted(rows) == [OCT12, OCT13, OCT14]
    assert sorted(bans) == [OCT12, OCT13]
    assert all(len(r) == 7 for r in rows.values())


def test_each_forecast_is_what_the_next_list_says(rows, bans, rules):
    """12 Oct -> 13 Oct is the only scored pair; 14 Oct has no list to score against."""
    assert forecast(OCT12, rows, bans, rules) == set(bans[OCT13])


# -- the six boundary and band cases, one row each ---------------------------------------


@pytest.mark.parametrize("symbol,util,was,will", [
    ("ENTRYCO",   0.9700, False, True),    # entry above 95%
    ("EDGECO",    0.9500, False, False),   # exactly 95.00%: "exceeds" is strict
    ("HOLDCO",    0.8800, True,  True),    # held in the band
    ("RELEASECO", 0.8000, True,  False),   # exactly 80.00%: "80% or below" is inclusive
    ("STICKYCO",  0.8001, True,  True),    # one hundredth of a point above the exit: held
    ("FREECO",    0.9000, False, False),   # free in the band stays free
])
def test_each_case_on_the_12_oct_close(rows, bans, rules, symbol, util, was, will):
    r = rows[OCT12][symbol]
    assert round(u(r), 4) == util
    assert (symbol in bans[OCT12]) is was
    assert (symbol in bans[OCT13]) is will, "the fixture's answer has changed"
    assert (symbol in forecast(OCT12, rows, bans, rules)) is will


def test_the_boundary_rows_sit_exactly_on_their_lines(rows, rules):
    """Exactly, not approximately: a row at 95.00000001% would let `>=` pass this suite."""
    entry = rules.value("single_stock.ban.entry_utilisation")
    exit_ = rules.value("single_stock.ban.exit_utilisation")
    assert u(rows[OCT12]["EDGECO"]) == entry
    assert u(rows[OCT12]["RELEASECO"]) == exit_


def test_a_released_scrip_back_in_the_band_stays_free(rows, bans, rules):
    """RELEASECO on 13 Oct: back in the band at 85% the day after its release - free stays free."""
    r = rows[OCT13]["RELEASECO"]
    assert round(u(r), 4) == 0.85 and "RELEASECO" not in bans[OCT13]
    assert "RELEASECO" not in forecast(OCT13, rows, bans, rules)


def test_the_same_utilisation_band_gives_opposite_answers_by_state(rows, bans, rules):
    """FREECO at 90% stays free while HOLDCO at 88% stays banned: the higher one is the free one."""
    got = forecast(OCT12, rows, bans, rules)
    assert u(rows[OCT12]["FREECO"]) > u(rows[OCT12]["HOLDCO"])
    assert "FREECO" not in got and "HOLDCO" in got


# -- reconciliation ----------------------------------------------------------------------


def test_residuals_of_0_and_0_99_pass(rows, rules):
    rec = reconcile(tuple(rows[OCT12].values()), rules)
    assert rec.ok, rec.failures
    by = {r.symbol: r.residual for r in rec.residuals}
    assert by["QUIETCO"] == 0
    assert by["EDGECO"] == 0                         # headroom exactly 0 on the entry line
    assert by["FREECO"] == pytest.approx(0.99)
    assert {b.symbol for b in rec.barred} == {"ENTRYCO", "HOLDCO", "STICKYCO"}


def test_a_negative_residual_and_a_barred_row_at_or_below_80_fail(rules):
    failing = read_rows(WINDOW / "reconcile_failures.csv")[OCT12]
    rec = reconcile(tuple(failing.values()), rules)
    assert not rec.ok
    text = "\n".join(rec.failures)
    assert "NEGCO" in text
    assert "ATEXITCO" in text and "BELOWCO" in text
    assert "QUIETCO" not in text                     # the good row is not dragged down with them
    assert {b.symbol: b.held for b in rec.barred} == {"ATEXITCO": False, "BELOWCO": False}


# -- what is refused ---------------------------------------------------------------------


def test_a_missing_ban_list_leaves_no_seed(rows, bans):
    """14 Oct's rows arrived and its list did not. Nothing infers one: the seed is absent, not
    empty, and the 13 Oct forecast for 14 Oct has nothing to be scored against."""
    assert OCT14 in rows
    assert OCT14 not in bans
    with pytest.raises(KeyError):
        bans[OCT14]


def test_the_ingest_layer_refuses_to_forecast_from_a_day_with_no_list(rows, tmp_path, rules):
    """The same case through the store: no official state for 14 Oct is not 'no bans'."""
    from sentinel.ingest import record_forecast_day
    from sentinel.store import BanStateStore, StoreError
    from tests.test_ingest import build_combineoi

    recs = [{
        "isin": r.isin, "scrip_name": r.scrip_name, "symbol": r.symbol, "mwpl": str(r.mwpl),
        "notional_oi": str(r.notional_oi), "futeq_oi": repr(r.futeq_oi),
        "no_fresh_positions": str(r.no_fresh_positions),
        "headroom_shares": "" if r.headroom_shares is None else str(r.headroom_shares),
    } for r in rows[OCT14].values()]
    oi = build_combineoi(tmp_path, OCT14, recs)
    with BanStateStore(tmp_path / "s.sqlite", load_calendar()) as store:
        with pytest.raises(StoreError, match="not the same as no bans"):
            record_forecast_day(store, oi, rules)


def test_a_close_whose_next_day_runs_through_an_unverified_special_session_refuses(tmp_path):
    """Fri 6 Nov's next trading day depends on whether Sunday's Muhurat session chains. Without
    the calendar's verdict row, the forecast has no date to be about, and refuses."""
    text = DEFAULT_CALENDAR_PATH.read_text(encoding="utf-8")
    stripped = tmp_path / "calendar.csv"
    stripped.write_text("".join(ln for ln in text.splitlines(keepends=True)
                                if not ln.startswith("chaining_")), encoding="utf-8")
    with pytest.raises(ChainUnverifiedError):
        load_calendar(stripped).next_trading_day(dt.date(2026, 11, 6))


def test_the_window_contains_no_real_symbol():
    """The point of the module: every symbol here is made up."""
    real_looking = {"SAIL", "KAYNES", "BANDHANBNK", "LICHSGFIN", "AMBUJACEM", "MANAPPURAM",
                    "INOXWIND", "KARURVYSYA", "360ONE"}
    seen = set()
    for p in WINDOW.glob("*.csv"):
        seen |= set(p.read_text(encoding="utf-8").replace(",", " ").split())
    assert not (seen & real_looking)
