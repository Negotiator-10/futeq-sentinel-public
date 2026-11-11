"""The parser and engine checks on NSE's real files. Local only: they skip without `data/`.

Until 10 Nov 2026 these numbers were literals in `test_engine.py` and `test_parsers.py`, copied
from NSE's files. NSE's content stays out of the repository (`DECISIONS.md` #010 addendum), so
those tests now use synthetic numbers with the same properties, and the real-file versions live
here, reading from NSE's files through the `nse_built` fixture in `conftest.py`. Nothing below
is a copied row: every input is read from `data/` at test time.
"""

from __future__ import annotations

import datetime as dt

import pytest
from decimal import Decimal

from sentinel.engine import headroom_shares, is_in_ban, reconcile, utilisation
from sentinel.parsers import parse_ban_list, parse_mwpl_file
from sentinel.rules import load_rules

OCT30 = dt.date(2026, 10, 30)


@pytest.fixture(scope="module")
def rules():
    return load_rules(warn=False)


@pytest.fixture(scope="module")
def samples(nse_built):
    return nse_built / "samples"


@pytest.fixture(scope="module")
def oct30(nse_built):
    """The whole 30 Oct file. `nse_built` has already checked data/ holds it."""
    from tests.conftest import _builder
    return {r.symbol: r for r in parse_mwpl_file(_builder().DATA / "combineoi_30102026.zip")}


# -- the parsers on real files -----------------------------------------------------------


def test_the_real_2_nov_ban_list(samples):
    result = parse_ban_list(samples / "fo_secban_02112026.csv")
    assert result.trade_date == dt.date(2026, 11, 2)
    assert result.symbols == frozenset({"KAYNES", "SAIL"})


def test_the_real_sample_rows(samples):
    rows = {r.symbol: r for r in parse_mwpl_file(samples / "combineoi_sample.csv")}
    assert set(rows) == {"KAYNES", "SAIL", "360ONE"}
    assert all(r.trade_date == OCT30 for r in rows.values())

    kaynes = rows["KAYNES"]
    assert kaynes.no_fresh_positions is True and kaynes.headroom_shares is None
    assert Decimal("0.95") * kaynes.mwpl - kaynes.futeq_oi > 0      # the formula would still give a number
    assert kaynes.futeq_oi % 1 != 0

    one = rows["360ONE"]
    assert one.no_fresh_positions is False
    assert 0 <= (Decimal("0.95") * one.mwpl - one.futeq_oi) - one.headroom_shares < 1


# -- the engine on real rows -------------------------------------------------------------


def test_sail_held_at_84_93_while_bandhanbnk_free_at_85_98(oct30, rules):
    """SPEC row 5 on the real file: the higher utilisation is the free one."""
    sail, bandhan = oct30["SAIL"], oct30["BANDHANBNK"]
    assert float(round(utilisation(sail.futeq_oi, sail.mwpl), 4)) == 0.8493
    assert float(round(utilisation(bandhan.futeq_oi, bandhan.mwpl), 4)) == 0.8598
    assert is_in_ban(sail.futeq_oi, sail.mwpl, was_in_ban_yesterday=True, rules=rules) is True
    assert is_in_ban(bandhan.futeq_oi, bandhan.mwpl, was_in_ban_yesterday=False, rules=rules) is False


def test_360one_headroom_is_nses_figure_untruncated(oct30, rules):
    row = oct30["360ONE"]
    got = headroom_shares(row, rules)
    assert got != int(got)
    assert 0 <= got - row.headroom_shares < 1


def test_the_tracked_files_hold_no_nse_content(nse_built):
    """The full scan, against every NSE file in data/, over what the next commit would publish.

    CI runs only the shape rules (`--ci`), because it has no data/ to compare against. This is
    the comparison itself: a copied row, a quoted MWPL or a real ban list anywhere in a tracked
    file fails here, whatever the file is called."""
    from tests.conftest import REPO, _builder
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "check_public_history", REPO / "scripts" / "check_public_history.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    hits = checker.worktree_hits(REPO, _builder().DATA)
    assert not hits, "\n".join(hits)


def test_the_replay_reconciles_with_one_known_exception(nse_built, rules):
    """Every combineoi file in data/, reconciled. Two days failed when FutEq OI was a float:

    - 7 Apr 2026, NAM-INDIA: the exact headroom was a whole number and NSE published exactly it;
      float arithmetic put ours 4e-9 below. Our bug, fixed by keeping FutEq OI as a Decimal.
    - 3 Jun 2026, TRENT: NSE published one share LESS than truncating the exact formula gives.
      A genuine disagreement, in the safe direction (less headroom, not more), whose cause cannot
      be determined from the published file. Kept failing on purpose: widening [0, 1) to hide it
      would throw away the one real finding. Recorded as a known exception.
    """
    from tests.conftest import _builder
    files = sorted(_builder().DATA.glob("combineoi_*.zip"))
    failing = {}
    for p in files:
        rows = parse_mwpl_file(p)
        rec = reconcile(rows, rules)
        if not rec.ok:
            failing[rows[0].trade_date] = rec.failures
    if len(files) < 200:
        pytest.skip(f"the replay needs the year of files in data/; found {len(files)}")
    assert list(failing) == [dt.date(2026, 6, 3)], failing
    (only,) = failing[dt.date(2026, 6, 3)]
    assert only.startswith("TRENT") and "+1.3137" in only


def test_the_whole_30_oct_file_reconciles(oct30, rules):
    rec = reconcile(tuple(oct30.values()), rules)
    assert rec.ok, rec.failures
    assert {b.symbol for b in rec.barred} == {"KAYNES", "SAIL"}
    assert all(b.held for b in rec.barred)
