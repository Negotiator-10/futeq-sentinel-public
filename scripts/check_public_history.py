"""Check that a git repository holds no NSE content, in any commit, under any path.

DECISIONS.md #010 addendum: NSE's terms of use (para 8) bar republishing its content, so the public
repository is built from filtered history and must carry no NSE rows anywhere. "Anywhere" means
every blob reachable from every ref, whatever path it sat at, so a file that was renamed, moved or
copied is caught by its content and not by its name. Commit messages are checked too.

The NSE files themselves are the oracle: they live in `data/` (gitignored), so the full check runs
locally - over every commit (default), or over the tracked files as they stand (`--worktree`,
which `tests/test_nse_local.py` runs). CI has no oracle and runs `--ci`, which checks shapes
instead; see the note above `ci_hits()`. Four tests, any one of which fails the repository:

  1. blob  - a blob is byte-identical to an NSE file, or to a file inside an NSE zip.
  2. line  - a data line of an NSE file (not its header) appears verbatim, CR/LF and surrounding
             spaces ignored. Lines shorter than 20 characters are skipped as too generic.
  3. value - a number from combineoi or combineoi_deleq with at least 7 digits (MWPL, open
             interest, FutEq OI) appears as a standalone token, with any commas or underscores
             removed. This is what catches a row that was re-formatted rather than copied.
  4. ban   - a "Securities in Ban For Trade Date" block lists a symbol that is a real NSE F&O
             symbol. Synthetic ban lists use made-up symbols, so they pass.

Usage:  python -I scripts/check_public_history.py [--worktree] <repo> <data_dir>
        python -I scripts/check_public_history.py --ci <repo>
Exit 0 and "clean" only if every test finds nothing.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import subprocess
import sys
import zipfile
from pathlib import Path

MIN_LINE = 20
MIN_DIGITS = 7
NUMBER = re.compile(r"(?<![0-9A-Za-z._])(?:\d{1,3}(?:[,_]\d{3})+|\d+)(?:\.\d+)?(?![0-9A-Za-z_])")
# A thousands separator is a comma or underscore followed by exactly three digits, so
# "123,456,789" and "123_456_789" are one number but the CSV fields "1234567,7654321" are two.
BAN_HEAD = re.compile(r"Securities in Ban For Trade Date", re.IGNORECASE)
BAN_ROW = re.compile(r"^\s*\d+\s*,\s*([A-Z0-9&\-]+)\s*$")


def _texts(data: Path):
    """Yield (name, bytes) for every NSE text source: plain files and members of zips."""
    for p in sorted(data.rglob("*")):
        if not p.is_file():
            continue
        name = p.name.lower()
        if name.endswith(".zip"):
            with zipfile.ZipFile(p) as zf:
                for m in zf.namelist():
                    yield f"{p.name}!{m}", zf.read(m)
        elif name.endswith((".csv", ".txt", ".dat")):
            yield p.name, p.read_bytes()


def _lines(raw: bytes) -> list[str]:
    return [ln.strip() for ln in raw.decode("utf-8", errors="replace").splitlines()]


def _digits(tok: str) -> str:
    return tok.replace(",", "").replace("_", "")


def build_oracle(data: Path):
    blobs: dict[str, str] = {}       # git blob id -> source name
    lines: dict[str, str] = {}       # data line -> source name
    values: dict[str, str] = {}      # number -> source name
    symbols: set[str] = set()
    for name, raw in _texts(data):
        blobs[_git_blob_id(raw)] = name
        rows = _lines(raw)
        for ln in rows[1:]:
            if len(ln) >= MIN_LINE:
                lines.setdefault(ln, name)
        low = name.lower()
        if low.startswith("combineoi"):
            for tok in NUMBER.findall("\n".join(rows[1:])):
                d = _digits(tok)
                if sum(c.isdigit() for c in d) >= MIN_DIGITS:
                    values.setdefault(d, name)
            if not low.startswith("combineoi_deleq"):
                reader = csv.reader(io.StringIO("\n".join(rows)))
                head = [h.strip().lower() for h in next(reader, [])]
                if "nse symbol" in head:
                    i = head.index("nse symbol")
                    symbols.update(r[i].strip() for r in reader if len(r) > i and r[i].strip())
    if not symbols:
        raise SystemExit(f"{data}: found no combineoi symbols, so the ban test would pass vacuously")
    return blobs, lines, values, symbols


def _git_blob_id(raw: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


def repo_blobs(repo: Path):
    """Every blob reachable from any ref, with one path it was seen at."""
    out = _git(repo, "rev-list", "--all", "--objects").decode("utf-8", errors="replace")
    pairs = [ln.split(" ", 1) for ln in out.splitlines()]
    ids = [p[0] for p in pairs]
    paths = {p[0]: (p[1] if len(p) > 1 else "") for p in pairs}
    proc = subprocess.run(["git", "-C", str(repo), "cat-file", "--batch-check=%(objectname) %(objecttype)"],
                          input="\n".join(ids).encode(), check=True, capture_output=True)
    blob_ids = [ln.split()[0] for ln in proc.stdout.decode().splitlines() if ln.endswith(" blob")]
    proc = subprocess.run(["git", "-C", str(repo), "cat-file", "--batch"],
                          input="\n".join(blob_ids).encode(), check=True, capture_output=True)
    buf, pos = proc.stdout, 0
    for _ in blob_ids:
        nl = buf.index(b"\n", pos)
        oid, _kind, size = buf[pos:nl].decode().split()
        size = int(size)
        yield oid, paths.get(oid, ""), buf[nl + 1: nl + 1 + size]
        pos = nl + 1 + size + 1


def commit_messages(repo: Path):
    out = _git(repo, "log", "--all", "--format=%H%x00%B%x01").decode("utf-8", errors="replace")
    for rec in out.split("\x01"):
        if "\x00" in rec:
            h, msg = rec.split("\x00", 1)
            yield h.strip(), msg


def scan_text(where: str, text: str, lines, values, symbols, hits: list[str]) -> None:
    rows = [ln.strip() for ln in text.splitlines()]
    for n, ln in enumerate(rows, 1):
        if ln in lines:
            hits.append(f"line   {where}:{n}  matches {lines[ln]}")
    for n, ln in enumerate(rows, 1):
        for tok in NUMBER.findall(ln):
            d = _digits(tok)
            if d in values:
                hits.append(f"value  {where}:{n}  {d} is in {values[d]}")
    for n, ln in enumerate(rows, 1):
        if BAN_HEAD.search(ln):
            for k in range(n, len(rows)):
                m = BAN_ROW.match(rows[k])
                if not m:
                    if rows[k] == "":
                        continue
                    break
                if m.group(1) in symbols:
                    hits.append(f"ban    {where}:{k + 1}  lists real symbol {m.group(1)}")


def tracked_files(repo: Path):
    """(path, bytes) for every file git tracks, as it stands in the working tree."""
    out = _git(repo, "ls-files", "-z").decode("utf-8")
    for name in filter(None, out.split("\0")):
        p = repo / name
        if p.is_file():
            yield name, p.read_bytes()


def worktree_hits(repo: Path, data: Path) -> list[str]:
    """The four oracle tests over the tracked files only - what the next commit would publish."""
    blobs, lines, values, symbols = build_oracle(data)
    hits: list[str] = []
    for name, raw in tracked_files(repo):
        if _git_blob_id(raw) in blobs:
            hits.append(f"blob   {name}  is byte-identical to {blobs[_git_blob_id(raw)]}")
        if b"\0" not in raw[:8000]:
            scan_text(name, raw.decode("utf-8", errors="replace"), lines, values, symbols, hits)
    return hits


# -- CI mode: no oracle ------------------------------------------------------------------
#
# CI has no data/, so it cannot compare against NSE's files, and a hashed copy of them would not
# do either: a 7-digit number or one of 221 symbols can be recovered from its hash by trying them
# all, so publishing the hashes would publish the values. CI checks the shapes instead - the ways
# NSE content would actually come back in: a file named like NSE's, a row keyed on a real-looking
# ISIN, or a ban list naming anything but the synthetic scrips.

SYNTHETIC = "tests/fixtures/synthetic/"
ALLOWED_NAMES = {"tests/fixtures/fo_secban_empty.csv"}
NSE_NAME = re.compile(r"^(combineoi|fo_secban|contract_delta|bhavcopy)", re.IGNORECASE)
ISIN = re.compile(r"(?<![0-9A-Z])IN[EF][0-9A-Z]{9}(?![0-9A-Z])")
SYNTHETIC_ISIN = "INE000"
ROW_DIGITS = 5


def ci_hits(repo: Path) -> list[str]:
    files = dict(tracked_files(repo))
    allowed: set[str] = set()
    for name, raw in files.items():
        if name.startswith(SYNTHETIC):
            text = raw.decode("utf-8", errors="replace")
            allowed |= {m.group(1) for ln in text.splitlines() if (m := BAN_ROW.match(ln.strip()))}
            for rec in csv.reader(io.StringIO(text)):
                allowed |= {c.strip() for c in rec[3:4]}
    hits: list[str] = []
    for name, raw in files.items():
        base = name.rsplit("/", 1)[-1]
        if NSE_NAME.match(base) and not name.startswith(SYNTHETIC) and name not in ALLOWED_NAMES:
            hits.append(f"name   {name}  is named like an NSE file outside {SYNTHETIC}")
        if b"\0" in raw[:8000]:
            continue
        rows = [ln.strip() for ln in raw.decode("utf-8", errors="replace").splitlines()]
        for n, ln in enumerate(rows, 1):
            real = [i for i in ISIN.findall(ln) if not i.startswith(SYNTHETIC_ISIN)]
            big = [t for t in NUMBER.findall(ln) if sum(c.isdigit() for c in t) >= ROW_DIGITS]
            if real and len(big) >= 2:
                hits.append(f"row    {name}:{n}  a row keyed on {real[0]} with figures {big[:3]}")
        for n, ln in enumerate(rows, 1):
            if BAN_HEAD.search(ln):
                for k in range(n, len(rows)):
                    m = BAN_ROW.match(rows[k])
                    if not m:
                        if rows[k] == "":
                            continue
                        break
                    if m.group(1) not in allowed:
                        hits.append(f"ban    {name}:{k + 1}  lists {m.group(1)}, not a synthetic scrip")
    return hits


def _report(hits: list[str], scanned: str) -> int:
    print(scanned)
    for h in hits:
        print(h)
    print("clean" if not hits else f"NOT CLEAN: {len(hits)} hits")
    return 0 if not hits else 1


def main(argv: list[str]) -> int:
    args = argv[1:]
    if args[:1] == ["--ci"] and len(args) == 2:
        repo = Path(args[1])
        return _report(ci_hits(repo), f"ci: tracked files in {repo}, shape rules (no oracle)")
    if args[:1] == ["--worktree"] and len(args) == 3:
        repo, data = Path(args[1]), Path(args[2])
        return _report(worktree_hits(repo, data), f"worktree: tracked files in {repo}, against {data}")
    if len(args) != 2:
        print("usage: check_public_history.py <repo> <data_dir>        every commit and message\n"
              "       check_public_history.py --worktree <repo> <data> the tracked files now\n"
              "       check_public_history.py --ci <repo>              shape rules, no data/")
        return 2
    repo, data = Path(args[0]), Path(args[1])
    blobs, lines, values, symbols = build_oracle(data)
    hits: list[str] = []
    n_blobs = 0
    for oid, path, raw in repo_blobs(repo):
        n_blobs += 1
        where = f"{oid[:10]} {path}"
        if oid in blobs:
            hits.append(f"blob   {where}  is byte-identical to {blobs[oid]}")
        if b"\0" in raw[:8000]:
            continue                      # binary: only the blob test applies
        scan_text(where, raw.decode("utf-8", errors="replace"), lines, values, symbols, hits)
    n_msgs = 0
    for h, msg in commit_messages(repo):
        n_msgs += 1
        scan_text(f"commit {h[:10]} message", msg, lines, values, symbols, hits)
    print(f"oracle: {len(blobs)} NSE files, {len(lines)} data lines, {len(values)} values, "
          f"{len(symbols)} symbols")
    print(f"scanned: {n_blobs} blobs and {n_msgs} commit messages in {repo}")
    for h in hits:
        print(h)
    print("clean" if not hits else f"NOT CLEAN: {len(hits)} hits")
    return 0 if not hits else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
