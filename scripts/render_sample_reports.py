"""Render the two sample reports in docs/sample_reports/ from the synthetic window.

Never from a real day: a real report quotes NSE's published figures, and NSE's content stays out
of the repository (DECISIONS.md #010 addendum). The window's scrips, ISINs and figures are all
made up (tests/fixtures/synthetic/window/); only the dates and the trading calendar are real.

Two days:
  2026-10-13  an ordinary day: a forecast for the 14th, a banned scrip held in the band,
              and free scrips with their headroom set beside NSE's
  2026-10-14  a day whose ban list is missing: the stages that need it refuse, the rest run

Each run goes into a temporary store, built the same way tests/test_runner.py builds its data.
Run from a clean checkout so the footer can say the code was committed:

    python -I scripts/render_sample_reports.py
"""

from __future__ import annotations

import datetime as dt
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO)]

from sentinel import report, runner                     # noqa: E402
from tests.test_runner import synthetic_paths           # noqa: E402

OUT = REPO / "docs" / "sample_reports"
DAYS = (dt.date(2026, 10, 13), dt.date(2026, 10, 14))
NOTE = ("> **Synthetic sample.** Rendered by `scripts/render_sample_reports.py` from the synthetic\n"
        "> window in `tests/fixtures/synthetic/window/`: every scrip, ISIN and figure is made up.\n"
        "> Only the date and the trading calendar are real.\n\n")


def main() -> int:
    # Render every day before writing any file: a sample already written into the tree would
    # make the next run's checkout dirty, and its footer would say "not reproducible".
    rendered = []
    for day in DAYS:
        with tempfile.TemporaryDirectory() as tmp:
            paths = synthetic_paths(Path(tmp))
            outcome = runner.run_day(day, paths)
            rendered.append((day, outcome, report.render(day, paths)))
    OUT.mkdir(parents=True, exist_ok=True)
    for day, outcome, text in rendered:
        out = OUT / f"{day.isoformat()}.md"
        out.write_text(NOTE + text, encoding="utf-8", newline="\n")
        print(f"{day}: run {outcome.name}, wrote {out.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
