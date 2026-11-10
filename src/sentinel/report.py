"""The daily report for trading day D, rendered from the store and the run log only (#019 item 8).

Nothing here recomputes a run. Every figure comes from what the run for D stored, so the same
store always renders the same report, and a crash after the run committed costs nothing. The
two judgements the report makes - which scrips disagree with NSE's flag, and how far each
in-band scrip is from the line that applies to it - are rule logic and are Chintamani's:
`flag_disagreements()` and `watchlist()` below. Everything else is layout.

Sections, in #019's order:

    1. Refusals            every refusal record for D, by stage
    2. Flag disagreements  NSE's T+1 flag on D's rows against the run's forecast for D+1
    3. Row 6 breaches      accounts that increased FutEq delta in a banned scrip
    4. Tomorrow's ban      the forecast for the next trading day
    5. Watchlist           the 80-95% band, with distance to the line that applies (item 9)
    6. Checks passed       reconciliation: the residual count, not the range (item 10)
       Audit footer        the run log: code, checksums, rules status, inputs, times

A refused section says "Refused:" and why. It is never left out and never shown as zero: row 6
refused for want of a book is not "0 breaches".

Usage:  python -m sentinel.report 2026-11-04        writes reports/2026-11-04.md
Exit codes: 0 written, 2 refused (D not run, or its run did not complete), 1 error.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from sentinel.calendar import ChainUnverifiedError, UnknownDateError, load_calendar
from sentinel.parsers import MwplRow
from sentinel.rules import Rules, load_rules
from sentinel.runner import REPO_ROOT, RunPaths
from sentinel.store import (
    BanStateStore, Refusal, RefusalStage, RunOutcome, RunRecord,
)

__all__ = [
    "FlagComparison", "Disagreement", "NotCompared", "flag_disagreements",
    "WatchState", "WatchEntry", "watchlist",
    "ReportRefused", "render", "write_report", "main",
]

GOVERNS = "NSE's determination governs; the engine's figure is under investigation."
NOT_REPRODUCIBLE = "uncommitted changes when it ran, so this report is not reproducible"


# == Chintamani's: the two judgements ======================================================


@dataclass(frozen=True)
class Disagreement:
    isin: str
    symbol: str
    nse_flag: bool        # NSE's "No Fresh Positions" on D's row: its declaration for D+1
    forecast: bool        # the run's forecast for D+1


@dataclass(frozen=True)
class NotCompared:
    isin: str
    symbol: str
    why: str              # e.g. "forecast refused", "no row in D's combineoi"


@dataclass(frozen=True)
class FlagComparison:
    disagreements: tuple[Disagreement, ...]
    not_compared: tuple[NotCompared, ...]
    agreed: int


def flag_disagreements(
    rows: tuple[MwplRow, ...],
    forecasts: Mapping[str, tuple[str, bool | None]],
) -> FlagComparison:
    """Compare NSE's flag on D's rows with the run's forecast for D+1.  CHINTAMANI'S TO WRITE.

    `rows` are D's stored combineoi rows; each row's `no_fresh_positions` is NSE's own
    declaration for D+1 (#012 decision 5). `forecasts` maps ISIN to `(symbol, forecast)` for
    D+1, as stored. A refused per-scrip forecast is never written, so a refused scrip is usually
    ABSENT from `forecasts`; `forecast` is None only where D+1 has a row with no forecast in it.
    Treat both as "no forecast".

    Agreed readings (10 Nov):
      - a disagreement is a scrip where the flag and the forecast differ;
      - a scrip whose forecast was refused is NOT COMPARED, not counted as agreeing;
      - a scrip with a forecast but no row in D's combineoi is also NOT COMPARED.
    """
    raise NotImplementedError("flag_disagreements() is Chintamani's to write")


class WatchState(Enum):
    BANNED = "banned"     # in ban on D: the 80% exit applies
    FREE = "free"         # not in ban on D: the 95% entry applies
    UNKNOWN = "unknown"   # D's official state missing: both lines shown, neither assumed


@dataclass(frozen=True)
class WatchEntry:
    isin: str
    symbol: str
    utilisation: float              # a fraction: 0.8051, not 80.51
    state: WatchState
    points_to_exit: float | None    # BANNED or UNKNOWN: percentage points above the 80% exit
    must_fall_by: float | None      # BANNED or UNKNOWN: shares OI must fall to reach the exit
    points_to_entry: float | None   # FREE or UNKNOWN: percentage points below the 95% entry
    headroom: float | None          # FREE or UNKNOWN: our exact headroom to the entry, shares
    nse_headroom: int | None        # NSE's published headroom for the row, if it has one


def watchlist(
    rows: tuple[MwplRow, ...],
    official: Mapping[str, bool] | None,
    rules: Rules,
) -> tuple[WatchEntry, ...]:
    """Every scrip in the 80-95% band, with its distance to the line that applies.  CHINTAMANI'S.

    `rows` are D's stored combineoi rows. `official` maps ISIN to D's official ban state, or is
    None when D's ban list was missing; an ISIN absent from it has no official state either.
    Thresholds come from `rules`, never literals (#009).

    Agreed readings (10 Nov), item 9 - no new threshold:
      - a banned scrip: points above the 80% exit, and the shares OI must fall to reach it,
        labelled "must fall by";
      - a free scrip: points below the 95% entry, and our exact headroom in shares, which the
        report notes against NSE's published figure (within [0, 1) when they match);
      - unknown state: both, and the state said to be unknown rather than guessed.
    Order is yours to choose; the report prints the entries in the order given.
    """
    raise NotImplementedError("watchlist() is Chintamani's to write")


# == Layout =================================================================================


class ReportRefused(Exception):
    """No report for D: it was not run, or its latest run neither completed nor refused."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pct(fraction: float) -> str:
    return f"{fraction * 100:.2f}%"


def _shares(x: float) -> str:
    return f"{x:,.0f}" if float(x).is_integer() else f"{x:,.4f}"


def _whole_stage(refusals: tuple[Refusal, ...], stage: RefusalStage) -> Refusal | None:
    return next((r for r in refusals if r.stage is stage and r.subject == ""), None)


def _report_run(store: BanStateStore, day: dt.date) -> RunRecord:
    """The run the report describes: the latest COMPLETED one, else a REFUSED one."""
    completed = store.last_completed_run(day)
    if completed is not None:
        return completed
    runs = store.runs_for(day)
    if not runs:
        raise ReportRefused(f"{day} has not been run: there is no run for it in the run log")
    latest = runs[-1]
    if latest.outcome is RunOutcome.REFUSED:
        return latest
    raise ReportRefused(
        f"{day} has no completed run; its latest run {latest.run_id[:8]} is "
        f"{latest.outcome.value}{': ' + latest.reason if latest.reason else ''}"
    )


def render(day: dt.date, paths: RunPaths | None = None) -> str:
    """The report for D, as Markdown. Raises ReportRefused when there is nothing to report."""
    paths = paths or RunPaths.default()
    calendar = load_calendar(paths.calendar)
    rules = load_rules(paths.rules, warn=False)
    with BanStateStore(paths.store, calendar) as store:
        run = _report_run(store, day)
        runs = store.runs_for(day)
        if run.outcome is RunOutcome.REFUSED:
            body = [f"**The run for {day} was refused:** {run.reason}", "",
                    "Nothing was computed or stored for this date."]
            return "\n".join(_header(day, run, None) + body + [""]
                             + _footer(run, runs, paths, None)) + "\n"

        try:
            next_day: dt.date | None = calendar.next_trading_day(day)
        except (UnknownDateError, ChainUnverifiedError):
            next_day = None
        rows = store.measurements(day)
        refusals = store.refusals(day)
        official_d = {i: o for i, _s, _f, o in store.scored_forecasts(day) if o is not None}
        official = official_d if _whole_stage(refusals, RefusalStage.OFFICIAL_STATE) is None else None
        forecasts = ({} if next_day is None else
                     {i: (s, f) for i, s, f, _o in store.scored_forecasts(next_day)})
        symbol_of = {r.isin: r.symbol for r in rows}

        lines = _header(day, run, next_day)
        lines += _refusals(refusals, symbol_of)
        lines += _flags(rows, forecasts, refusals)
        lines += _row6(store.row6_checks(day), refusals, symbol_of)
        lines += _tomorrow(next_day, forecasts, refusals, symbol_of)
        lines += _watch(rows, official, rules)
        lines += _checks(store.reconciliation(day))
        lines += _footer(run, runs, paths, next_day)
    return "\n".join(lines) + "\n"


def _header(day: dt.date, run: RunRecord, next_day: dt.date | None) -> list[str]:
    target = (f"forecast for {next_day}" if next_day else "no forecast date"
              ) if run.outcome is RunOutcome.COMPLETED else "nothing forecast"
    return [f"# FutEq Sentinel report: {day}", "",
            f"Run `{run.run_id[:8]}` {run.outcome.value}, {target}.", ""]


def _refusals(refusals: tuple[Refusal, ...], symbol_of: Mapping[str, str]) -> list[str]:
    out = ["## 1. Refusals", ""]
    if not refusals:
        return out + ["None. Every stage ran.", ""]
    for stage in RefusalStage:
        mine = [r for r in refusals if r.stage is stage]
        whole = [r for r in mine if r.subject == ""]
        each = [r for r in mine if r.subject != ""]
        for r in whole:
            out.append(f"- **{stage.value}** refused: {r.reason}")
        if each:
            names = ", ".join(sorted(symbol_of.get(r.subject, r.subject) for r in each))
            reasons = sorted({r.reason for r in each})
            out.append(f"- **{stage.value}** refused for {len(each)} scrip(s): {names} "
                       f"({'; '.join(reasons)})")
    return out + [""]


def _flags(rows, forecasts, refusals) -> list[str]:
    out = ["## 2. Flag disagreements with NSE", ""]
    stage = _whole_stage(refusals, RefusalStage.FORECAST)
    if stage is not None:
        return out + [f"Refused: nothing to compare, the forecast was refused ({stage.reason}).", ""]
    comparison = flag_disagreements(rows, forecasts)
    if comparison.disagreements:
        out += [f"**{len(comparison.disagreements)} disagreement(s).** {GOVERNS}", "",
                "| scrip | NSE's flag for D+1 | engine's forecast |", "|---|---|---|"]
        out += [f"| {d.symbol} | {'no fresh positions' if d.nse_flag else 'free'} | "
                f"{'banned' if d.forecast else 'free'} |" for d in comparison.disagreements]
        out.append("")
    else:
        out.append("None.")
    out.append(f"{comparison.agreed} agreed; {len(comparison.not_compared)} not compared.")
    if comparison.not_compared:
        out.append("")
        out += [f"- not compared: {n.symbol} ({n.why})" for n in comparison.not_compared]
    return out + [""]


def _row6(checks, refusals, symbol_of) -> list[str]:
    out = ["## 3. Row 6 breaches", ""]
    stage = _whole_stage(refusals, RefusalStage.ROW6)
    if stage is not None:
        return out + [f"Refused: {stage.reason}.", ""]
    breaches = [c for c in checks if not c.permitted]
    if not breaches:
        return out + [f"None: {len(checks)} account-scrip check(s), every one permitted.", ""]
    out += ["| account | scrip | baseline | today | reason |", "|---|---|---|---|---|"]
    out += [f"| {c.tm}/{c.ucc} | {symbol_of.get(c.isin, c.isin)} | {c.baseline} | "
            f"{c.today_delta} | {c.reason} |" for c in breaches]
    return out + ["", f"{len(breaches)} of {len(checks)} check(s) breached.", ""]


def _tomorrow(next_day, forecasts, refusals, symbol_of) -> list[str]:
    out = ["## 4. Tomorrow's ban", ""]
    stage = _whole_stage(refusals, RefusalStage.FORECAST)
    if stage is not None or next_day is None:
        why = stage.reason if stage is not None else "the next trading day is not settled"
        return out + [f"Refused: {why}.", ""]
    banned = sorted(s for s, f in forecasts.values() if f)
    out.append(f"Forecast for {next_day}: "
               + (", ".join(banned) if banned else "no scrip in ban") + ".")
    unforecast = [r for r in refusals if r.stage is RefusalStage.FORECAST and r.subject]
    if unforecast:
        names = ", ".join(sorted(symbol_of.get(r.subject, r.subject) for r in unforecast))
        out.append(f"Not forecast: {names} - in the band with no official state for today.")
    return out + [""]


def _watch(rows, official, rules) -> list[str]:
    out = ["## 5. Watchlist: the 80-95% band", ""]
    entries = watchlist(rows, official, rules)
    if not entries:
        return out + ["No scrip in the band.", ""]
    out += ["| scrip | utilisation | state | distance |", "|---|---|---|---|"]
    for e in entries:
        out.append(f"| {e.symbol} | {_pct(e.utilisation)} | {e.state.value} | {_distance(e)} |")
    return out + [""]


def _distance(e: WatchEntry) -> str:
    parts = []
    if e.points_to_exit is not None:
        part = f"{e.points_to_exit:.2f} pts above the exit"
        if e.must_fall_by is not None:
            part += f"; must fall by {_shares(e.must_fall_by)} shares"
        parts.append(part)
    if e.points_to_entry is not None:
        part = f"{e.points_to_entry:.2f} pts below the entry"
        if e.headroom is not None:
            part += f"; headroom {_shares(e.headroom)} shares"
            if e.nse_headroom is not None:
                gap = e.headroom - e.nse_headroom
                part += (f" (NSE: {e.nse_headroom:,}, within [0, 1))" if 0 <= gap < 1 else
                         f" (NSE: {e.nse_headroom:,}, differs by {gap:.4f})")
        parts.append(part)
    return " / ".join(parts) if parts else "-"


def _checks(rec) -> list[str]:
    out = ["## 6. Checks passed", ""]
    if rec is None:
        return out + ["Refused: no reconciliation was stored for this date.", ""]
    head = "Reconciliation against NSE's published headroom: "
    out.append(head + ("passed." if rec.ok else f"**FAILED** ({len(rec.failures)} failure(s))."))
    out.append(f"- {rec.rows_total} rows; {rec.residual_count} headroom residual(s) checked "
               f"in [0, 1); {rec.barred_count} barred row(s), {rec.barred_held} held above the exit.")
    out += [f"- failure: {f}" for f in rec.failures]
    return out + [""]


def _footer(run: RunRecord, runs, paths: RunPaths, next_day: dt.date | None) -> list[str]:
    out = ["---", "", "### Audit", ""]
    out.append(f"- run `{run.run_id}`, {run.outcome.value}; trade date {run.trade_date}; "
               f"forecast date {next_day if next_day else 'none'}")
    out.append(f"- started {run.started_at}, finished {run.finished_at or 'not finished'}")
    out.append(f"- code `{run.code_version}`"
               + (f", **{NOT_REPRODUCIBLE}**" if run.dirty else ", clean"))
    rules_now = _sha256(paths.rules)
    out.append(f"- rules `{run.rules_checksum}`"
               + ("" if rules_now == run.rules_checksum else
                  f" (**rules.yaml has changed since this run**: now `{rules_now}`)"))
    out.append(f"- calendar `{run.calendar_checksum}`")
    assumed = run.rules_status.get("assumed", ())
    unverified = run.rules_status.get("unverified", ())
    out.append(f"- assumed rules, used without a citation: {', '.join(assumed) if assumed else 'none'}")
    out.append(f"- unverified rules, refused: {', '.join(unverified) if unverified else 'none'}")
    if run.input_checksums:
        out.append("- inputs:")
        out += [f"  - `{name}` `{sha}`" for name, sha in sorted(run.input_checksums.items())]
    else:
        out.append("- inputs: none found")
    others = [r for r in runs if r.run_id != run.run_id]
    if others:
        out.append("- other runs for this date: " + "; ".join(
            f"`{r.run_id[:8]}` {r.outcome.value} {r.started_at}" for r in others))
    return out


def write_report(day: dt.date, paths: RunPaths | None = None, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or REPO_ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{day.isoformat()}.md"
    out.write_text(render(day, paths), encoding="utf-8", newline="\n")
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m sentinel.report YYYY-MM-DD", file=sys.stderr)
        return 1
    day = dt.date.fromisoformat(argv[1])
    try:
        out = write_report(day)
    except ReportRefused as refused:
        print(f"REFUSED {day}: {refused}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"FAILED {day}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
