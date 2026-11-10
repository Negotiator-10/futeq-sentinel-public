"""Write the inputs for `git filter-repo` that turn this repository's history into the public one.

`DECISIONS.md` #010 addendum: the public repository is built from this one's history with NSE's
content removed. Two kinds of removal, because NSE's content sits in two kinds of place:

* **whole files** - the fixtures that were copies or selections of NSE's files. These paths are
  removed from every commit (`paths.txt`, for `--paths-from-file` with `--invert-paths`).
* **values inside files that stay** - NSE figures quoted in tests, docstrings, docs and commit
  messages before 10 Nov 2026. Each becomes `REDACTED` in every commit and message
  (`replacements.txt`, for `--replace-text` and `--replace-message`). `REDACTED` keeps an old
  Python file parseable and reads plainly in prose; those commits still will not run.

The values come from `check_public_history.py` itself: every number it flags anywhere in this
repository's history is replaced, in any of the spellings it matched (123456789, 123,456,789,
123_456_789). The filtered result is then checked again by `check_public_history.py`, which is
what decides whether it is clean - not this script.

Usage:  python -I scripts/make_public_filter.py <repo> <data_dir> <out_dir>
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

REMOVED_PATHS = (
    "tests/fixtures/combineoi_sample.csv",
    "tests/fixtures/fo_secban_02112026.csv",
    "glob:tests/fixtures/transitions/*.csv",
    "glob:tests/fixtures/sail_release/*.csv",
)


def _checker():
    here = Path(__file__).resolve().parent / "check_public_history.py"
    spec = importlib.util.spec_from_file_location("check_public_history", here)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def value_regex(digits: str) -> str:
    """123456789 -> 1[,_]?2[,_]?3... so every separator spelling of the same number matches,
    anchored so it cannot match inside a longer number."""
    whole, _, frac = digits.partition(".")
    body = "[,_]?".join(re.escape(c) for c in whole)
    if frac:
        body += r"\." + re.escape(frac)
    return rf"(?<![0-9A-Za-z._]){body}(?![0-9A-Za-z_])"


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__.strip().splitlines()[-1])
        return 2
    repo, data, out = Path(argv[1]), Path(argv[2]), Path(argv[3])
    c = _checker()
    blobs, lines, values, symbols = c.build_oracle(data)

    flagged: set[str] = set()
    hits: list[str] = []
    for _oid, _path, raw in c.repo_blobs(repo):
        if b"\0" not in raw[:8000]:
            c.scan_text("", raw.decode("utf-8", errors="replace"), lines, values, symbols, hits)
    for _h, msg in c.commit_messages(repo):
        c.scan_text("", msg, lines, values, symbols, hits)
    for h in hits:
        m = re.match(r"value\s+\S*\s+(\S+) is in ", h)
        if m:
            flagged.add(m.group(1))

    out.mkdir(parents=True, exist_ok=True)
    (out / "paths.txt").write_text("\n".join(REMOVED_PATHS) + "\n", encoding="utf-8")
    (out / "replacements.txt").write_text(
        "".join(f"regex:{value_regex(v)}==>REDACTED\n" for v in sorted(flagged)), encoding="utf-8")
    print(f"{len(REMOVED_PATHS)} path rules and {len(flagged)} values written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
