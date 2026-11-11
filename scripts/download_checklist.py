"""Hand-download checklists for the replay, one page per month, and a check of each finished month.

NSE's files are downloaded by hand (DECISIONS.md #010 addendum), so this script never fetches
anything. It writes pages of links for a person to click, and checks what that person saved.

    python -I scripts/download_checklist.py pages [FROM] [TO]
        One Markdown page per month in reports/downloads/ (gitignored), newest month first in the
        index. Each page lists every date the calendar has a session on - holidays shown and
        skipped - with both daily files: combineoi (MWPL, OI, FutEq OI) and fo_secban (the ban
        list). Files already in data/ are ticked. FROM and TO default to 2025-10-01 and yesterday.

    python -I scripts/download_checklist.py check YYYY-MM
        Checks every expected file for that month in data/: present, readable by the project's
        own parsers, and dated inside as its name says. Names a stray copy such as
        "combineoi_13102026 (1).zip". For each good file it records the name, size, sha256 and
        trade date in docs/data_manifest.csv, the tracked manifest READING.md's table has outgrown.
        Exit 0 only if the month is complete and clean.

A date outside the calendar's covered years is UNKNOWN: the page lists it, every weekday, and
says the calendar must be extended from NSE's holiday circular for that year before the runner
will accept it. A holiday's files simply do not exist.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from sentinel.calendar import DayKind, load_calendar        # noqa: E402
from sentinel.parsers import parse_ban_list, parse_mwpl_file  # noqa: E402

DATA = REPO / "data"
OUT = REPO / "reports" / "downloads"
MANIFEST = REPO / "docs" / "data_manifest.csv"
DEFAULT_FROM = dt.date(2025, 10, 1)
NSE_FILES = (
    ("combineoi", "zip", "https://nsearchives.nseindia.com/archives/nsccl/mwpl/combineoi_{s}.zip"),
    ("fo_secban", "csv", "https://nsearchives.nseindia.com/archives/fo/sec_ban/fo_secban_{s}.csv"),
)
ROUTE = ("If a link hangs or says Access Denied, open https://www.nseindia.com once in the same "
         "browser, then retry. Otherwise: https://www.nseindia.com/all-reports-derivatives, "
         "Archives tab, pick the date, and download \"F&O - Combine OI across exchanges\" and "
         "\"F&O - Security in ban period\". Save into data/ unrenamed and unzipped.")
STRAY = re.compile(r"^(combineoi|fo_secban)_\d{8}.*\(\d+\)")


def _stamp(day: dt.date) -> str:
    return day.strftime("%d%m%Y")


def _months(first: dt.date, last: dt.date):
    y, m = first.year, first.month
    while (y, m) <= (last.year, last.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def _days(calendar, year: int, month: int, first: dt.date, last: dt.date):
    """(day, kind) for every weekday in the month inside [first, last], plus any special session."""
    day = max(dt.date(year, month, 1), first)
    while day.month == month and day <= last:
        kind = calendar.kind(day)
        if day.weekday() < 5 or kind is DayKind.SPECIAL_SESSION:
            yield day, kind
        day += dt.timedelta(days=1)


def _expected(day: dt.date) -> list[tuple[str, str]]:
    return [(f"{prefix}_{_stamp(day)}.{ext}", url.format(s=_stamp(day)))
            for prefix, ext, url in NSE_FILES]


def pages(first: dt.date, last: dt.date) -> int:
    calendar = load_calendar()
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for year, month in _months(first, last):
        lines, want, have, unknown = [], 0, 0, 0
        title = dt.date(year, month, 1).strftime("%B %Y")
        lines += [f"# Downloads: {title}", "", ROUTE, "",
                  f"When this month is done: `python -I scripts/download_checklist.py check "
                  f"{year}-{month:02d}`", "",
                  "| date | day | calendar | combineoi | fo_secban |", "|---|---|---|---|---|"]
        for day, kind in _days(calendar, year, month, first, last):
            if kind is DayKind.HOLIDAY:
                lines.append(f"| {day} | {day:%a} | holiday | - | - |")
                continue
            if kind is DayKind.UNKNOWN:
                unknown += 1
            cells = []
            for name, url in _expected(day):
                want += 1
                done = (DATA / name).is_file()
                have += done
                cells.append(f"{'[x]' if done else '[ ]'} [{name}]({url})")
            label = {"trading": "trading", "special_session": "special session",
                     "unknown": "**not in calendar**"}[kind.value]
            lines.append(f"| {day} | {day:%a} | {label} | {cells[0]} | {cells[1]} |")
        if unknown:
            lines += ["", f"**{unknown} date(s) here are not in the calendar.** It covers only the "
                      f"years whose NSE holiday circular is recorded in `config/calendar_2026.csv`. "
                      f"Some of these weekdays are holidays and have no files; the runner refuses "
                      f"every one of them until the calendar is extended from NSE's circular for "
                      f"{year}."]
        page = OUT / f"{year}-{month:02d}.md"
        page.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        index.append((year, month, title, want, have, unknown))

    total_want = sum(i[3] for i in index)
    total_have = sum(i[4] for i in index)
    head = [f"# Replay downloads, {first} to {last}", "",
            f"{total_have} of {total_want} files in data/; {total_want - total_have} to download.",
            "Newest month first.", "", "| month | files | in data/ | to do | note |",
            "|---|---|---|---|---|"]
    for year, month, title, want, have, unknown in sorted(index, reverse=True):
        note = f"{unknown} date(s) not in calendar" if unknown else ""
        head.append(f"| [{title}]({year}-{month:02d}.md) | {want} | {have} | {want - have} | {note} |")
    (OUT / "index.md").write_text("\n".join(head) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {len(index)} month pages and index.md to {OUT.relative_to(REPO).as_posix()}: "
          f"{total_have} of {total_want} files already in data/")
    return 0


def _read_manifest() -> dict[str, dict[str, str]]:
    if not MANIFEST.is_file():
        return {}
    with MANIFEST.open(encoding="utf-8", newline="") as fh:
        return {r["file"]: r for r in csv.DictReader(fh)}


def _write_manifest(rows: dict[str, dict[str, str]]) -> None:
    with MANIFEST.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "bytes", "sha256", "trade_date", "checked_on"],
                           lineterminator="\n")
        w.writeheader()
        for name in sorted(rows, key=lambda n: (rows[n]["trade_date"], n)):
            w.writerow(rows[name])


def check(year: int, month: int) -> int:
    calendar = load_calendar()
    last = dt.date(year + (month == 12), 1 if month == 12 else month + 1, 1) - dt.timedelta(days=1)
    first = dt.date(year, month, 1)
    yesterday = dt.date.today() - dt.timedelta(days=1)
    manifest = _read_manifest()
    problems, good, skipped = [], 0, 0
    for day, kind in _days(calendar, year, month, first, min(last, yesterday)):
        if kind is DayKind.HOLIDAY:
            continue
        for name, _url in _expected(day):
            path = DATA / name
            if not path.is_file():
                if kind is DayKind.UNKNOWN:
                    skipped += 1        # may be a holiday; the calendar cannot say yet
                    continue
                problems.append(f"missing  {name}")
                continue
            try:
                dated = (parse_mwpl_file(path)[0].trade_date if name.startswith("combineoi")
                         else parse_ban_list(path).trade_date)
            except Exception as exc:  # noqa: BLE001 - report every unreadable file, then go on
                problems.append(f"unreadable  {name}: {type(exc).__name__}: {exc}")
                continue
            if dated != day:
                problems.append(f"misdated  {name}: the file itself says {dated}")
                continue
            raw = path.read_bytes()
            manifest[name] = {"file": name, "bytes": str(len(raw)),
                              "sha256": hashlib.sha256(raw).hexdigest(),
                              "trade_date": day.isoformat(),
                              "checked_on": dt.date.today().isoformat()}
            good += 1
    stamp = f"{month:02d}{year}"
    strays = sorted(p.name for p in DATA.iterdir()
                    if STRAY.match(p.name) and p.name.split("_")[1][2:8] == stamp)
    problems += [f"stray copy  {s}: delete it or rename it over the original" for s in strays]
    _write_manifest(manifest)
    print(f"{year}-{month:02d}: {good} file(s) good and recorded in "
          f"{MANIFEST.relative_to(REPO).as_posix()}")
    if skipped:
        print(f"  {skipped} file(s) absent on dates the calendar does not cover - holidays, or "
              f"not downloaded; the calendar must be extended to tell which")
    for p in problems:
        print("  " + p)
    print("clean" if not problems else f"NOT CLEAN: {len(problems)} problem(s)")
    return 0 if not problems else 1


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "pages" and len(argv) in (2, 4):
        first = dt.date.fromisoformat(argv[2]) if len(argv) == 4 else DEFAULT_FROM
        last = (dt.date.fromisoformat(argv[3]) if len(argv) == 4
                else dt.date.today() - dt.timedelta(days=1))
        return pages(first, last)
    if len(argv) == 3 and argv[1] == "check" and re.fullmatch(r"\d{4}-\d{2}", argv[2]):
        year, month = map(int, argv[2].split("-"))
        return check(year, month)
    print(__doc__.strip().splitlines()[0])
    print("usage: download_checklist.py pages [FROM TO] | check YYYY-MM")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
