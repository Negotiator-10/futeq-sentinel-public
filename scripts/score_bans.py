"""Score the ban rule against NSE's published lists, over every file in `data/`.

`tests/test_transitions.py` locks the result on eight scrips, because `CLAUDE.md` keeps
fixtures small. This reproduces the whole figure - every scrip in every `combineoi` on disk -
from the raw files, which are gitignored. It is the runnable version of the result written up
in `docs/READING.md`, so the claim there is reproducible by anyone who downloads the files and
checks them against the sha256s recorded alongside it.

For each measurement day:

    seed   = THAT day's published ban list, symbols resolved to ISINs through that day's
             combineoi (DECISIONS.md #011 Q2 - fo_secban carries no ISIN of its own)
    input  = that day's utilisation
    answer = the NEXT day present on disk

Nothing reads the `No Fresh Positions` flag. That flag is NSE's own declaration for the next
trading day (#012 decision 5), so a seed drawn from it would be the answer going in and coming
back out - which is what made the first version of this score worthless.

    python scripts/score_bans.py [--data DIR]

Exits 1 if any scrip-day disagrees, so it can be run as a check and not just a report.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sentinel.calendar import (  # noqa: E402
    ChainUnverifiedError,
    UnknownDateError,
    load_calendar,
)
from sentinel.engine import is_in_ban, utilisation  # noqa: E402
from sentinel.parsers import parse_ban_list, parse_mwpl_file  # noqa: E402
from sentinel.rules import load_rules  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=ROOT / "data",
                    help="directory holding the raw NSE files (default: ./data)")
    args = ap.parse_args(argv)

    if not args.data.is_dir():
        print(f"no such directory: {args.data}")
        print("Nothing to score. The raw files are gitignored; see docs/READING.md for what to")
        print("download and the sha256 of each. The eight-scrip version runs in CI as")
        print("tests/test_transitions.py.")
        return 0

    rules = load_rules(warn=False)
    calendar = load_calendar()
    print(f"calendar: {calendar!r}")

    bans: dict[dt.date, frozenset[str]] = {}
    for p in sorted(args.data.glob("fo_secban_*.csv")):
        bl = parse_ban_list(p)
        bans[bl.trade_date] = bl.symbols

    days: dict[dt.date, tuple] = {}
    for p in sorted(args.data.glob("combineoi_*.zip")):
        rows = parse_mwpl_file(p)
        days[rows[0].trade_date] = rows

    if not bans or not days:
        print(f"found {len(bans)} ban list(s) and {len(days)} combineoi file(s) in {args.data};")
        print("scoring needs at least one of each, plus a ban list for a later date.")
        return 0

    ban_dates = sorted(bans)
    print(f"{len(days)} measurement day(s), {len(bans)} ban list(s), from {args.data}")
    print()
    print("  measurement  forecast for  agree       FP  FN")
    print("  " + "-" * 48)

    total = agreed = fp_all = fn_all = 0
    transitions: list[tuple] = []
    skipped: list[str] = []

    for day in sorted(days):
        if day not in bans:
            skipped.append(f"{day}: no ban list for the measurement day, so no seed")
            continue

        # The next trading day comes from the verified calendar, never from "the next date
        # with a file". Conflating the two was a real bug: hide one ban list and this scored
        # 14 Oct's forecast against 16 Oct's published answer, skipped the 15th entirely, and
        # still reported 1502 of 1502 with exit 0. The calendar refuses rather than skipping.
        try:
            nxt = calendar.next_trading_day(day)
        except ChainUnverifiedError as exc:
            skipped.append(f"{day}: {exc}")
            continue
        except UnknownDateError as exc:
            skipped.append(f"{day}: {exc}")
            continue

        if nxt not in bans:
            skipped.append(
                f"{day}: the next trading day is {nxt} and its ban list is not on disk, so "
                f"there is nothing to score against. NOT scored against a later list - that "
                f"would answer the wrong day's question."
            )
            continue

        rows = days[day]

        by_symbol = {r.symbol: r for r in rows}
        unresolved = sorted(s for s in bans[day] if s not in by_symbol)
        seed = {by_symbol[s].isin for s in bans[day] if s in by_symbol}

        forecast = {
            r.symbol for r in rows
            if is_in_ban(r.futeq_oi, r.mwpl, was_in_ban_yesterday=r.isin in seed, rules=rules)
        }
        universe = {r.symbol for r in rows}
        answer = bans[nxt] & universe

        fp = sorted(forecast - answer)
        fn = sorted(answer - forecast)
        ok = sum(1 for s in universe if (s in forecast) == (s in answer))

        total += len(universe)
        agreed += ok
        fp_all += len(fp)
        fn_all += len(fn)

        changed = set(answer) ^ (bans[day] & universe)
        print("  %s   %s    %4d/%-4d   %2d  %2d%s"
              % (day, nxt, ok, len(universe), len(fp), len(fn),
                 "   <- transition" if changed else ""))
        if unresolved:
            print(f"        ban-list symbols absent from this day's combineoi: {unresolved}")
        if fp:
            print(f"        FALSE POSITIVES (claimed banned, NSE did not): {fp}")
        if fn:
            print(f"        FALSE NEGATIVES (claimed free, NSE banned):    {fn}")

        for sym in sorted(changed):
            r = by_symbol.get(sym)
            u = None if r is None else utilisation(r.futeq_oi, r.mwpl)
            transitions.append((nxt, sym, "entry" if sym in answer else "release", u,
                                (sym in forecast) == (sym in answer)))

    print("  " + "-" * 48)
    print("  TOTAL                    %4d/%-4d   %2d  %2d" % (agreed, total, fp_all, fn_all))

    for note in skipped:
        print(f"  skipped {note}")

    if transitions:
        print()
        print("  TRANSITIONS")
        print("  effective   symbol        direction  utilisation  right?")
        print("  " + "-" * 56)
        for eff, sym, direction, u, right in transitions:
            print("  %s  %-12s  %-8s   %s     %s"
                  % (eff, sym, direction,
                     "   n/a " if u is None else "%6.2f%%" % (u * 100),
                     "yes" if right else "NO"))

    print()
    entries = sum(1 for t in transitions if t[2] == "entry")
    releases = len(transitions) - entries
    if total == 0:
        print("  nothing scored.")
        return 0
    print("  %d of %d scrip-days agree. %d entries and %d releases, %d forecast correctly."
          % (agreed, total, entries, releases, sum(1 for t in transitions if t[4])))
    print()
    print("  Read the second number, not the first: most scrip-days are a security nowhere near")
    print("  a threshold staying there, so a model answering \"never banned\" scores about 99%.")
    print("  The transition count is the sample that tests the logic.")

    return 0 if agreed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
