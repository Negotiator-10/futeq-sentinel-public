"""Build `tests/fixtures/sail_release/` from the raw NSE files in `data/`.

SAIL's walk out of the ban, 2 to 6 Nov 2026: held at 84.70%, 84.10% and 80.51%, released from
79.52%, and kept out at 82.79%. The fixture is derived data - rerun this, never edit it by hand.

* `combineoi_rows.csv` - SAIL's row from each of the five `combineoi` files, copied as the strings
  NSE published (no float round-trip), in the same columns as `tests/fixtures/transitions/`.
* `fo_secban_*.csv` - six ban lists copied byte for byte: 2 Nov (the seed for the first close)
  through 6 Nov, and 8 Nov (the answer for the 6 Nov close, since the Muhurat session chains).
* `SOURCES.md` - every input's size and sha256.

Run from the repo root:  python scripts/build_sail_fixture.py
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
OUT = REPO / "tests" / "fixtures" / "sail_release"
SYMBOL = "SAIL"
MEASUREMENT_DAYS = ("02112026", "03112026", "04112026", "05112026", "06112026")
BAN_LIST_DAYS = ("02112026", "03112026", "04112026", "05112026", "06112026", "08112026")
NFP = "No Fresh Positions"
COLUMNS = ["trade_date", "isin", "scrip_name", "symbol", "mwpl", "notional_oi", "futeq_oi",
           "no_fresh_positions", "headroom_shares"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sail_row(zip_path: Path) -> dict[str, str]:
    with zipfile.ZipFile(zip_path) as z:
        (member,) = [m for m in z.namelist() if m.lower().endswith(".csv")]
        text = z.read(member).decode("utf-8")
    reader = csv.reader(io.StringIO(text))
    header = [h.strip() for h in next(reader)]
    expected = ["Date", "ISIN", "Scrip Name", "NSE Symbol", "MWPL", "Open Interest",
                "Future Equivalent Open Interest", "Limit for Next Day"]
    if header != expected:
        raise SystemExit(f"{zip_path.name}: header changed: {header}")
    found = [[c.strip() for c in r] for r in reader if r and r[3].strip() == SYMBOL]
    if len(found) != 1:
        raise SystemExit(f"{zip_path.name}: {len(found)} {SYMBOL} rows, expected 1")
    date, isin, name, symbol, mwpl, oi, futeq, limit = found[0]
    return {
        "trade_date": datetime.strptime(date, "%d-%b-%Y").date().isoformat(),
        "isin": isin, "scrip_name": name, "symbol": symbol, "mwpl": mwpl, "notional_oi": oi,
        "futeq_oi": futeq,
        "no_fresh_positions": str(limit == NFP),
        "headroom_shares": "" if limit == NFP else limit,
    }


def main() -> int:
    missing = [n for n in [f"combineoi_{d}.zip" for d in MEASUREMENT_DAYS]
               + [f"fo_secban_{d}.csv" for d in BAN_LIST_DAYS] if not (DATA / n).is_file()]
    if missing:
        print(f"data/ is missing {missing}; the raw files are gitignored and downloaded by hand.")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)

    rows = [sail_row(DATA / f"combineoi_{d}.zip") for d in MEASUREMENT_DAYS]
    with (OUT / "combineoi_rows.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    table = []
    for d in BAN_LIST_DAYS:
        name = f"fo_secban_{d}.csv"
        shutil.copyfile(DATA / name, OUT / name)
        src = DATA / name
        table.append(f"| `{name}` | copied verbatim from data/ | {src.stat().st_size} | `{sha256(src)}` |")
    for d in MEASUREMENT_DAYS:
        src = DATA / f"combineoi_{d}.zip"
        table.append(f"| `{src.name}` | SAIL's row only | {src.stat().st_size:,} | `{sha256(src)}` |")

    doc = f"""# Provenance for `tests/fixtures/sail_release/`

Built by `scripts/build_sail_fixture.py` from the files in `data/`, which is gitignored. Derived
data: rerun the builder, never edit by hand. The same hashes are in `docs/READING.md`.

SAIL's walk out of the ban, 2 to 6 Nov 2026. `combineoi_rows.csv` holds **SAIL's row only** from
each of five `combineoi` files - one row selected per file, copied as NSE published the strings.
The ban lists are copied byte for byte: 2 Nov is the seed for the first close, and 8 Nov is the
answer for the 6 Nov close, because the Muhurat session on Sunday 8 Nov chains (`DECISIONS.md`
#013 addendum).

The two in-band cases are both here, on one stock: the 4 Nov close (80.51%, in ban, held) and the
6 Nov close (82.79%, not in ban, stays out).

| file | role | source bytes | source sha256 |
|---|---|---|---|
""" + "\n".join(table) + "\n"
    (OUT / "SOURCES.md").write_text(doc, encoding="utf-8", newline="\n")
    print(f"wrote {len(rows)} rows and {len(BAN_LIST_DAYS)} ban lists to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
