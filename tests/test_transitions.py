"""The project's headline result, enforced on every push.

Until now "1502 of 1502 scrip-days, seven transitions, zero errors" lived in a scratchpad
script and two markdown files. Nothing in the repo proved it, which means a clone of this
repository could pass all its tests while the one thing the project exists to do was broken.

These tests score `is_in_ban()` against NSE's own published ban lists on the five scrips that
transitioned between 12 Oct and 2 Nov 2026, plus three controls. For each measurement day the
chain is:

    seed   = THAT day's published ban list, resolved to ISINs through that day's combineoi rows
    input  = that day's utilisation, from MWPL and FutEq OI as published
    answer = the NEXT day's published ban list

Nothing reads the `no_fresh_positions` flag, which is NSE's own T+1 declaration and therefore
the answer. A chain that used it would be predicting the answer from itself - see
`DECISIONS.md` #012 decision 5, and the 7 Nov entry in `LEARNING.md`.

The fixture holds selected rows, not whole files; `tests/fixtures/transitions/SOURCES.md`
records which file each row came from and its checksum. The full 1502-row figure needs the
gitignored files in `data/` and is reproduced by `scripts/score_bans.py`.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import re
from pathlib import Path

import pytest

from sentinel.engine import is_in_ban, utilisation
from sentinel.parsers import MwplRow, parse_ban_list
from sentinel.rules import load_rules

FIXTURES = Path(__file__).parent / "fixtures" / "transitions"

#: The five that transition, the two in-band controls that never do, and one quiet scrip.
TRANSITION_SCRIPS = {"KAYNES", "SAIL", "BANDHANBNK", "LICHSGFIN", "AMBUJACEM"}
BAND_CONTROLS = {"MANAPPURAM", "INOXWIND"}
QUIET_CONTROL = "KARURVYSYA"


@pytest.fixture(scope="module")
def rules():
    return load_rules(warn=False)


@pytest.fixture(scope="module")
def rows_by_day() -> dict[dt.date, dict[str, MwplRow]]:
    """The fixture rows, as real `MwplRow` objects so their invariants are exercised too.

    Read with the `csv` module rather than pandas on purpose: pandas' default missing-value
    list includes the literal string "NA", which is what NSE writes for an index ISIN, and that
    silently disarmed the index guard once already.
    """
    out: dict[dt.date, dict[str, MwplRow]] = {}
    with (FIXTURES / "combineoi_rows.csv").open(encoding="utf-8", newline="") as fh:
        for rec in csv.DictReader(fh):
            row = MwplRow(
                trade_date=dt.date.fromisoformat(rec["trade_date"]),
                isin=rec["isin"],
                scrip_name=rec["scrip_name"],
                symbol=rec["symbol"],
                mwpl=int(rec["mwpl"]),
                notional_oi=int(rec["notional_oi"]),
                futeq_oi=float(rec["futeq_oi"]),
                no_fresh_positions=rec["no_fresh_positions"] == "True",
                headroom_shares=None if rec["headroom_shares"] == "" else int(rec["headroom_shares"]),
            )
            out.setdefault(row.trade_date, {})[row.symbol] = row
    return out


@pytest.fixture(scope="module")
def bans() -> dict[dt.date, frozenset[str]]:
    out = {}
    for p in sorted(FIXTURES.glob("fo_secban_*.csv")):
        bl = parse_ban_list(p)
        out[bl.trade_date] = bl.symbols
    return out


def forecast(day, rows_by_day, bans, rules) -> set[str]:
    """What the engine says about the next day, for the scrips in the fixture."""
    rows = rows_by_day[day]
    seed_isins = {rows[s].isin for s in bans[day] if s in rows}
    return {
        sym for sym, r in rows.items()
        if is_in_ban(r.futeq_oi, r.mwpl, was_in_ban_yesterday=r.isin in seed_isins, rules=rules)
    }


def next_ban_day(day, bans):
    later = sorted(d for d in bans if d > day)
    return later[0] if later else None


# -- the score ----------------------------------------------------------------------------


def test_every_measurement_day_agrees_with_nse(rows_by_day, bans, rules):
    """The whole result in one test: no scrip-day disagrees, on any of the seven days."""
    checked = 0
    for day in sorted(rows_by_day):
        nxt = next_ban_day(day, bans)
        assert nxt is not None, day
        got = forecast(day, rows_by_day, bans, rules)
        want = bans[nxt] & set(rows_by_day[day])
        assert got == set(want), (
            f"{day} -> {nxt}: forecast {sorted(got)} but NSE published {sorted(want)}"
        )
        checked += len(rows_by_day[day])
    assert checked == 51, f"expected 51 scrip-days in the fixture, got {checked}"


def test_all_seven_transitions_are_forecast_correctly(rows_by_day, bans, rules):
    """Three entries and four releases, each identified by date, symbol and direction."""
    expected = {
        (dt.date(2026, 10, 13), "KAYNES", "entry"),
        (dt.date(2026, 10, 14), "BANDHANBNK", "release"),
        (dt.date(2026, 10, 14), "LICHSGFIN", "release"),
        (dt.date(2026, 10, 15), "SAIL", "entry"),
        (dt.date(2026, 10, 28), "AMBUJACEM", "release"),
        (dt.date(2026, 10, 28), "KAYNES", "release"),
        (dt.date(2026, 10, 29), "KAYNES", "entry"),
    }

    seen = set()
    for day in sorted(rows_by_day):
        nxt = next_ban_day(day, bans)
        got = forecast(day, rows_by_day, bans, rules)
        for sym in set(rows_by_day[day]):
            was, will = sym in bans[day], sym in bans[nxt]
            if was == will:
                continue
            direction = "entry" if will else "release"
            seen.add((nxt, sym, direction))
            assert (sym in got) == will, f"{nxt} {sym} {direction} forecast wrongly"

    assert seen == expected, (
        f"missing {sorted(expected - seen)}, unexpected {sorted(seen - expected)}"
    )


@pytest.mark.parametrize(
    "day,symbol,expected_utilisation",
    [
        (dt.date(2026, 10, 12), "KAYNES", 0.9798),
        (dt.date(2026, 10, 13), "BANDHANBNK", 0.7941),
        (dt.date(2026, 10, 13), "LICHSGFIN", 0.7882),
        (dt.date(2026, 10, 14), "SAIL", 0.9501),
        (dt.date(2026, 10, 27), "AMBUJACEM", 0.7002),
        (dt.date(2026, 10, 27), "KAYNES", 0.6696),
        (dt.date(2026, 10, 28), "KAYNES", 0.9567),
    ],
)
def test_the_utilisation_behind_each_transition(rows_by_day, day, symbol, expected_utilisation):
    """Entries above 95%, releases at or below 80%, and nothing in between.

    Locking the measured value, not just the verdict: if a future change to the FutEq basis
    moved these, the verdict could stay right for the wrong reason.
    """
    r = rows_by_day[day][symbol]
    assert round(utilisation(r.futeq_oi, r.mwpl), 4) == expected_utilisation


# -- both kinds of in-band row, on every day ----------------------------------------------


def test_every_day_has_a_banned_scrip_in_the_band_that_stays_banned(rows_by_day, bans, rules):
    """The exit threshold holding. Without this an engine could release everything."""
    for day in sorted(rows_by_day):
        nxt = next_ban_day(day, bans)
        held = [
            s for s, r in rows_by_day[day].items()
            if s in bans[day] and s in bans[nxt] and in_band(r, rules)
        ]
        assert held, f"{day} has no banned-and-held scrip in the band"
        got = forecast(day, rows_by_day, bans, rules)
        for s in held:
            assert s in got, f"{day}: {s} was banned and stayed banned, forecast says free"


def test_every_day_has_a_free_scrip_in_the_band_that_stays_free(rows_by_day, bans, rules):
    """The other half, and the one that matters more.

    Inside the band `is_in_ban()` returns yesterday's state, so an engine that simply answered
    "banned" for everything in the band would pass the test above and fail this one. Either
    half alone lets a lazy engine through.
    """
    for day in sorted(rows_by_day):
        nxt = next_ban_day(day, bans)
        free = [
            s for s, r in rows_by_day[day].items()
            if s not in bans[day] and s not in bans[nxt] and in_band(r, rules)
        ]
        assert free, f"{day} has no free-and-stayed-free scrip in the band"
        got = forecast(day, rows_by_day, bans, rules)
        for s in free:
            assert s not in got, f"{day}: {s} was free and stayed free, forecast says banned"


def in_band(row: MwplRow, rules) -> bool:
    """Above the exit threshold and at or below the entry one - where state decides."""
    u = utilisation(row.futeq_oi, row.mwpl)
    return not rules.compare("single_stock.ban.entry_utilisation", u) and not rules.compare(
        "single_stock.ban.exit_utilisation", u
    )


def test_two_scrips_0_41_points_apart_with_opposite_states(rows_by_day, bans, rules):
    """12 Oct, same day, same file: the tightest pair in the window.

    SAIL at 92.50% was free and stayed free; AMBUJACEM at 92.91% was banned and stayed banned.
    Four-tenths of a percentage point apart, opposite answers, and the higher one is the free
    one. Tighter than the SAIL/BANDHANBNK pair in `SPEC.md` row 5, which is 1.05 points apart.
    """
    day = dt.date(2026, 10, 12)
    sail = rows_by_day[day]["SAIL"]
    ambuja = rows_by_day[day]["AMBUJACEM"]

    u_sail = utilisation(sail.futeq_oi, sail.mwpl)
    u_ambuja = utilisation(ambuja.futeq_oi, ambuja.mwpl)
    assert round(u_sail, 4) == 0.9250
    assert round(u_ambuja, 4) == 0.9291
    assert u_ambuja - u_sail < 0.005

    got = forecast(day, rows_by_day, bans, rules)
    assert "SAIL" not in got
    assert "AMBUJACEM" in got


def test_a_scrip_two_thirds_of_a_point_below_the_entry_line_stays_free(rows_by_day, bans, rules):
    """13 Oct: SAIL at 94.35%, not banned. Any "high utilisation means banned" shortcut dies here."""
    day = dt.date(2026, 10, 13)
    r = rows_by_day[day]["SAIL"]
    assert round(utilisation(r.futeq_oi, r.mwpl), 4) == 0.9435
    assert "SAIL" not in forecast(day, rows_by_day, bans, rules)


def test_a_scrip_just_above_the_exit_line_is_held(rows_by_day, bans, rules):
    """26 Oct: KAYNES at 80.42%, four-tenths of a point above the 80% release, stays banned."""
    day = dt.date(2026, 10, 26)
    r = rows_by_day[day]["KAYNES"]
    assert round(utilisation(r.futeq_oi, r.mwpl), 4) == 0.8042
    assert "KAYNES" in forecast(day, rows_by_day, bans, rules)


def test_the_quiet_control_is_never_banned(rows_by_day, bans, rules):
    for day in sorted(rows_by_day):
        if QUIET_CONTROL not in rows_by_day[day]:
            continue
        r = rows_by_day[day][QUIET_CONTROL]
        assert utilisation(r.futeq_oi, r.mwpl) < 0.80
        assert QUIET_CONTROL not in forecast(day, rows_by_day, bans, rules)


# -- the boundary row ---------------------------------------------------------------------


def test_sail_entered_on_29360_shares_past_the_line(rows_by_day, rules):
    """The row that earns para 5.2.6's "exceeds" and the strict `>` in the config.

    At the 14 Oct close SAIL's FutEq OI was 206,047,699.58 against an MWPL of REDACTED:
    95.0135% utilisation, 29,360 shares past the 95% line on a limit of 217 million - one part
    in seven thousand. NSE banned it the next day. Had it closed 0.0135 of a percentage point
    lower, "exceeds" says no ban and `>=` says ban, and this project would have been wrong.
    """
    r = rows_by_day[dt.date(2026, 10, 14)]["SAIL"]
    entry = rules.value("single_stock.ban.entry_utilisation")

    past = r.futeq_oi - entry * r.mwpl
    assert 29_000 < past < 30_000
    assert round(past) == 29_360

    u = utilisation(r.futeq_oi, r.mwpl)
    assert u > entry
    assert u - entry < 0.0002
    assert is_in_ban(r.futeq_oi, r.mwpl, was_in_ban_yesterday=False, rules=rules) is True


# -- the flag is NSE's own T+1 declaration, and the chain above never reads it -------------


def test_the_no_fresh_positions_flag_is_a_next_day_declaration(rows_by_day, bans):
    """#012 decision 5, on the days where the two candidate dates differ.

    This is the finding that makes the chain above non-circular: the flag IS the answer, so a
    seed taken from it would predict the answer from itself.
    """
    discriminating = 0
    for day in sorted(rows_by_day):
        nxt = next_ban_day(day, bans)
        rows = rows_by_day[day]
        flagged = {s for s, r in rows.items() if r.no_fresh_positions}
        today = bans[day] & set(rows)
        tomorrow = bans[nxt] & set(rows)

        assert flagged == set(tomorrow), f"{day}: flag {sorted(flagged)} != {nxt} list {sorted(tomorrow)}"
        if set(today) != set(tomorrow):
            discriminating += 1

    assert discriminating >= 5, (
        f"only {discriminating} day(s) distinguish T from T+1; the finding needs several"
    )


# -- provenance ---------------------------------------------------------------------------


def test_the_ban_list_fixtures_match_their_recorded_checksums():
    """A selected fixture without provenance is data with no origin.

    SOURCES.md records the sha256 of every input. The ban lists were copied byte-for-byte, so
    their recorded hash must still match - if one is edited by hand, this fails.
    """
    doc = (FIXTURES / "SOURCES.md").read_text(encoding="utf-8")
    recorded = dict(re.findall(r"\| \`(fo_secban_\d+\.csv)\` \|[^|]*\|[^|]*\| \`([0-9a-f]{64})\` \|", doc))
    assert len(recorded) == 15, f"expected 15 ban lists in SOURCES.md, found {len(recorded)}"

    for name, digest in recorded.items():
        actual = hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest()
        assert actual == digest, f"{name} does not match the hash in SOURCES.md"


def test_the_selected_rows_are_documented_as_selected():
    doc = (FIXTURES / "SOURCES.md").read_text(encoding="utf-8")
    assert "rows selected" in doc
    assert "combineoi_rows.csv" in doc
