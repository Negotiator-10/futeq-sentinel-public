"""Shared fixtures.

`nse_built` builds the real-data fixtures from NSE's files in `data/` into a temporary directory,
once per session, and checks every file against `tests/fixtures/nse_built.sha256`. NSE's content
is never committed (`DECISIONS.md` #010 addendum), so:

* with none of the NSE files in `data/` - CI, or a fresh clone - the tests that need them skip;
* with some but not all, they fail: a half-downloaded `data/` is a mistake to be told about;
* with all of them, a build that differs from a recorded hash fails rather than being used.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _builder():
    spec = importlib.util.spec_from_file_location(
        "build_nse_fixtures", REPO / "scripts" / "build_nse_fixtures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def nse_built(tmp_path_factory) -> Path:
    b = _builder()
    present = [n for n in b.required_files() if (b.DATA / n).is_file()]
    if not present:
        pytest.skip("needs NSE's files in data/, which are downloaded by hand and never "
                    "committed (DECISIONS.md #010 addendum)")
    out = b.build_all(tmp_path_factory.mktemp("nse_built"))
    got, want = b.built_hashes(out), b.recorded_hashes()
    bad = sorted(n for n in set(got) | set(want) if got.get(n) != want.get(n))
    assert not bad, f"built fixtures differ from tests/fixtures/nse_built.sha256: {bad}"
    return out
