"""The NSE-content scanner's value rule, pinned on synthetic numbers so it runs in CI.

`scripts/check_public_history.py` flags a number from NSE's combineoi files when it appears in a
tracked file - unless the number is round (two significant digits or fewer), which cannot identify
any row. That exception loosens a safety check, so these tests pin both sides of it: a round
number is ignored, and a distinctive one - including one with exactly three significant digits,
the boundary - is still caught. Every number here is made up.

Written by Claude when the round-number rule was added (11 Nov 2026), at Chintamani's request.
"""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def checker():
    spec = importlib.util.spec_from_file_location(
        "check_public_history", REPO / "scripts" / "check_public_history.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("value,distinctive", [
    ("60000000", False),          # the false alarm that prompted the rule
    ("1000000", False),
    ("950000", False),            # too short as well
    ("100000000.000", False),     # trailing zeros after the point are not significant
    ("125000000", True),          # three significant digits: the boundary, still caught
    ("123456789", True),
    ("7654321", True),
    ("4321987.65432101", True),   # a FutEq-style decimal
])
def test_only_round_numbers_are_ignored(checker, value, distinctive):
    assert checker._distinctive(value) is distinctive


def test_a_distinctive_value_is_caught_and_a_round_one_is_not(checker, tmp_path):
    """End to end: build an oracle from a made-up combineoi file, then scan text quoting both."""
    data = tmp_path / "data"
    data.mkdir()
    header = ("Date, ISIN, Scrip Name, NSE Symbol, MWPL, Open Interest, "
              "Future Equivalent Open Interest, Limit for Next Day")
    row = "01-JAN-2026,INE000Z01019,MADE UP LTD,MADEUPCO,987654321,60000000,543219876.125,1"
    with zipfile.ZipFile(data / "combineoi_01012026.zip", "w") as z:
        z.writestr("combineoi_01012026.csv", header + "\r\n" + row + "\r\n")

    _blobs, lines, values, symbols = checker.build_oracle(data)
    assert "987654321" in values and "543219876.125" in values
    assert "60000000" not in values

    hits: list[str] = []
    checker.scan_text("quoted.md", "MWPL was 987,654,321 and OI was 60,000,000.",
                      lines, values, symbols, hits)
    assert len(hits) == 1 and "987654321" in hits[0]
