"""A hand-download checklist for the replay, and a check of each finished month.

NSE's files are downloaded by hand (DECISIONS.md #010 addendum), so this script never fetches
anything. It writes a page of links for a person to click, and checks what that person saved.

    python -I scripts/download_checklist.py pages [FROM] [TO]
        One Markdown page, reports/downloads/checklist.md (gitignored), listing only the files
        not yet in data/: newest month first, a heading per month with its count and its check
        command, newest date first within the month. Both daily files per session date:
        combineoi (MWPL, OI, FutEq OI) and fo_secban (the ban list). Holidays have no files and
        are left out. Rerun it to drop what has landed. FROM and TO default to 2025-10-01 and
        yesterday.

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
    sections, total_want, total_missing = [], 0, 0
    for year, month in sorted(_months(first, last), reverse=True):
        missing, unknown = [], set()
        days = sorted(_days(calendar, year, month, first, last), reverse=True)
        for day, kind in days:
            if kind is DayKind.HOLIDAY:
                continue
            for name, url in _expected(day):
                total_want += 1
                if not (DATA / name).is_file():
                    missing.append((day, kind, name, url))
                    if kind is DayKind.UNKNOWN:
                        unknown.add(day)
        if not missing:
            continue
        total_missing += len(missing)
        title = dt.date(year, month, 1).strftime("%B %Y")
        lines = [f"## {title}: {len(missing)} file(s)", "",
                 f"When this section is done: `python -I scripts/download_checklist.py check "
                 f"{year}-{month:02d}`", ""]
        if unknown:
            lines += [f"**{len(unknown)} date(s) in this month are not in the calendar.** Some of "
                      f"these weekdays are holidays and have no files, and the runner refuses all of "
                      f"them until the calendar is extended from NSE's holiday circular for {year}. "
                      f"Extend it before downloading this month, then rerun `pages`.", ""]
        for day, kind, name, url in missing:
            note = {"special_session": " (special session)",
                    "unknown": " (not in calendar)"}.get(kind.value, "")
            lines.append(f"- [ ] {day:%a} {day}{note}: [{name}]({url})")
        sections.append("\n".join(lines))

    head = [f"# Replay downloads still to do, {first} to {last}", "",
            f"{total_missing} of {total_want} files to download; files already in data/ are left "
            f"out, and holidays have none. Newest month first.", "", ROUTE, ""]
    page = OUT / "checklist.md"
    page.write_text("\n".join(head) + "\n" + "\n\n".join(sections) + "\n",
                    encoding="utf-8", newline="\n")
    for old in OUT.glob("*.md"):                    # the per-month pages this replaced
        if old.name != page.name:
            old.unlink()
    print(f"wrote {page.relative_to(REPO).as_posix()}: {total_missing} of {total_want} files "
          f"still to download, in {len(sections)} month section(s)")
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
