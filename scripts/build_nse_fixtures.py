"""Build the real-data test fixtures from NSE's files in `data/`. They are never committed.

`DECISIONS.md` #010 addendum: NSE's content stays out of the repository. What the repository
keeps instead is this builder and `tests/fixtures/nse_built.sha256`, the hash of every file it
must produce. A build that differs from a recorded hash fails, so a fixture cannot drift, and
the rows themselves stay in `data/` (gitignored) where NSE's terms allow a downloaded file to be.

Four sets, each in its own directory under the output root:

* `transitions/`  - 12 Oct to 2 Nov 2026: the rows of eight scrips (five that transition, two
  in-band controls, one quiet one) from seven `combineoi` files, and fifteen ban lists copied
  byte for byte. Provenance: `tests/fixtures/transitions/SOURCES.md`.
* `sail_release/` - 2 to 8 Nov 2026: SAIL's row from five `combineoi` files and six ban lists.
  Provenance: `tests/fixtures/sail_release/SOURCES.md`.
* `samples/`      - the parsers' real-file cases: three 30 Oct rows and the 2 Nov ban list.

Rows are copied as the strings NSE published, with no float round-trip.

    python -I scripts/build_nse_fixtures.py            # builds into data/fixtures/
    python -I scripts/build_nse_fixtures.py OUT_DIR    # builds somewhere else

The tests call `build_all()` themselves, into a temporary directory, so a local run never reads
a stale build; they skip when `data/` lacks the NSE files.
"""

from __future__ import annotations

import csv
import hashlib
import io
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
MANIFEST = REPO / "tests" / "fixtures" / "nse_built.sha256"

HEADER = ["Date", "ISIN", "Scrip Name", "NSE Symbol", "MWPL", "Open Interest",
          "Future Equivalent Open Interest", "Limit for Next Day"]
COLUMNS = ["trade_date", "isin", "scrip_name", "symbol", "mwpl", "notional_oi", "futeq_oi",
           "no_fresh_positions", "headroom_shares"]
NFP = "No Fresh Positions"

TRANSITION_SYMBOLS = ("KAYNES", "SAIL", "BANDHANBNK", "LICHSGFIN", "AMBUJACEM",
                      "MANAPPURAM", "INOXWIND", "KARURVYSYA")
TRANSITION_DAYS = ("12102026", "13102026", "14102026", "26102026", "27102026", "28102026",
                   "30102026")
TRANSITION_BANS = ("12102026", "13102026", "14102026", "15102026", "16102026", "19102026",
                   "21102026", "22102026", "23102026", "26102026", "27102026", "28102026",
                   "29102026", "30102026", "02112026")
SAIL_DAYS = ("02112026", "03112026", "04112026", "05112026", "06112026")
SAIL_BANS = ("02112026", "03112026", "04112026", "05112026", "06112026", "08112026")
SAMPLE_DAY, SAMPLE_SYMBOLS, SAMPLE_BAN = "30102026", ("KAYNES", "SAIL", "360ONE"), "02112026"


class MissingData(Exception):
    """`data/` does not hold an NSE file the build needs."""


def required_files() -> list[str]:
    names = {f"combineoi_{d}.zip" for d in (*TRANSITION_DAYS, *SAIL_DAYS, SAMPLE_DAY)}
    names |= {f"fo_secban_{d}.csv" for d in (*TRANSITION_BANS, *SAIL_BANS, SAMPLE_BAN)}
    return sorted(names)


def _csv_text(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as z:
        (member,) = [m for m in z.namelist() if m.lower().endswith(".csv")]
        return z.read(member).decode("utf-8")


def _source_rows(data: Path, day: str) -> list[list[str]]:
    reader = csv.reader(io.StringIO(_csv_text(data / f"combineoi_{day}.zip")))
    header = [h.strip() for h in next(reader)]
    if header != HEADER:
        raise SystemExit(f"combineoi_{day}.zip: header changed: {header}")
    return [[c.strip() for c in r] for r in reader if r]


def _as_fixture_row(src: list[str]) -> dict[str, str]:
    date, isin, name, symbol, mwpl, oi, futeq, limit = src
    return {
        "trade_date": datetime.strptime(date, "%d-%b-%Y").date().isoformat(),
        "isin": isin, "scrip_name": name, "symbol": symbol, "mwpl": mwpl, "notional_oi": oi,
        "futeq_oi": futeq, "no_fresh_positions": str(limit == NFP),
        "headroom_shares": "" if limit == NFP else limit,
    }


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _select(data: Path, day: str, symbols: tuple[str, ...], *, every: bool) -> list[dict[str, str]]:
    by_symbol = {r[3]: r for r in _source_rows(data, day)}
    if every and (missing := [s for s in symbols if s not in by_symbol]):
        raise SystemExit(f"combineoi_{day}.zip: no row for {missing}")
    return [_as_fixture_row(by_symbol[s]) for s in symbols if s in by_symbol]


def _copy_bans(data: Path, out: Path, days: tuple[str, ...]) -> None:
    for d in days:
        shutil.copyfile(data / f"fo_secban_{d}.csv", out / f"fo_secban_{d}.csv")


def build_all(out_root: Path, data: Path = DATA) -> Path:
    missing = [n for n in required_files() if not (data / n).is_file()]
    if missing:
        raise MissingData(f"{data} is missing {len(missing)} NSE file(s), e.g. {missing[:3]}; "
                          f"they are downloaded by hand (DECISIONS.md #010 addendum)")

    t = out_root / "transitions"
    t.mkdir(parents=True, exist_ok=True)
    rows = [r for d in TRANSITION_DAYS
            for r in _select(data, d, TRANSITION_SYMBOLS, every=False)]
    _write_rows(t / "combineoi_rows.csv", rows)
    _copy_bans(data, t, TRANSITION_BANS)

    s = out_root / "sail_release"
    s.mkdir(parents=True, exist_ok=True)
    _write_rows(s / "combineoi_rows.csv",
                [r for d in SAIL_DAYS for r in _select(data, d, ("SAIL",), every=True)])
    _copy_bans(data, s, SAIL_BANS)

    p = out_root / "samples"
    p.mkdir(parents=True, exist_ok=True)
    # The sample keeps NSE's bytes, CRLF line endings included: it is what the parser reads.
    head, *body = _csv_text(data / f"combineoi_{SAMPLE_DAY}.zip").split("\r\n")
    keep = [ln for ln in body if ln and ln.split(",")[3].strip() in SAMPLE_SYMBOLS]
    if len(keep) != len(SAMPLE_SYMBOLS):
        raise SystemExit(f"combineoi_{SAMPLE_DAY}.zip: found {len(keep)} of {SAMPLE_SYMBOLS}")
    (p / "combineoi_sample.csv").write_bytes(("\r\n".join([head, *keep]) + "\r\n").encode("utf-8"))
    _copy_bans(data, p, (SAMPLE_BAN,))
    return out_root


def built_hashes(out_root: Path) -> dict[str, str]:
    return {f.relative_to(out_root).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(out_root.rglob("*")) if f.is_file()}


def recorded_hashes(manifest: Path = MANIFEST) -> dict[str, str]:
    out = {}
    for ln in manifest.read_text(encoding="utf-8").splitlines():
        if ln.strip() and not ln.startswith("#"):
            digest, name = ln.split(None, 1)
            out[name.strip()] = digest
    return out


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else DATA / "fixtures"
    try:
        build_all(out)
    except MissingData as exc:
        print(exc)
        return 1
    got, want = built_hashes(out), recorded_hashes()
    bad = sorted(n for n in set(got) | set(want) if got.get(n) != want.get(n))
    for n in bad:
        print(f"MISMATCH {n}: built {got.get(n)}, recorded {want.get(n)}")
    print(f"built {len(got)} files into {out}; {'all match' if not bad else f'{len(bad)} differ'}"
          f" {MANIFEST.relative_to(REPO).as_posix()}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
