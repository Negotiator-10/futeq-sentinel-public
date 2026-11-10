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
    assert 0.95 * kaynes.mwpl - kaynes.futeq_oi > 0      # the formula would still give a number
    assert kaynes.futeq_oi % 1 != 0

    one = rows["360ONE"]
    assert one.no_fresh_positions is False
    assert 0 <= (0.95 * one.mwpl - one.futeq_oi) - one.headroom_shares < 1


# -- the engine on real rows -------------------------------------------------------------


def test_sail_held_at_84_93_while_bandhanbnk_free_at_85_98(oct30, rules):
    """SPEC row 5 on the real file: the higher utilisation is the free one."""
    sail, bandhan = oct30["SAIL"], oct30["BANDHANBNK"]
    assert round(utilisation(sail.futeq_oi, sail.mwpl), 4) == 0.8493
    assert round(utilisation(bandhan.futeq_oi, bandhan.mwpl), 4) == 0.8598
    assert is_in_ban(sail.futeq_oi, sail.mwpl, was_in_ban_yesterday=True, rules=rules) is True
    assert is_in_ban(bandhan.futeq_oi, bandhan.mwpl, was_in_ban_yesterday=False, rules=rules) is False


def test_360one_headroom_is_nses_figure_untruncated(oct30, rules):
    row = oct30["360ONE"]
    got = headroom_shares(row, rules)
    assert got != int(got)
    assert 0 <= got - row.headroom_shares < 1


def test_the_whole_30_oct_file_reconciles(oct30, rules):
    rec = reconcile(tuple(oct30.values()), rules)
    assert rec.ok, rec.failures
    assert {b.symbol for b in rec.barred} == {"KAYNES", "SAIL"}
    assert all(b.held for b in rec.barred)
