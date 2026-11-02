# Progress

Start every session by reading this file, then `TASKS.md` for the tick list. `PLAN.md` is the five-week strategy.

## Status: Week 0 (setup), 28 Oct 2026
Done by Claude on 28 Oct:
- Folder `Desktop\futeq-sentinel` with a git repository (branch `main`).
- Conda env `sentinel` (Python 3.12, 64-bit) with pandas, pyarrow, pydantic, pandera, scipy, PyYAML, requests, pytest, hypothesis, jinja2, matplotlib and python-dotenv.
- `CLAUDE.md` (tutor mode), `PLAN.md`, `DECISIONS.md` (#001 to #005), `LEARNING.md`, `SPEC.md` skeleton, `README.md`, `.gitignore`, `.env.example`.
- `docs/READING.md` (reading list and facts-to-verify table) and `docs/research_report.md`.
- First local commit `d48166d`. The private GitHub repo is not created yet, because the upload needs your permission. Run this yourself from this folder:
  `gh repo create Negotiator-10/futeq-sentinel --private --source=. --remote=origin --push`

## Schedule moved forward (29 Oct)
The project starts today, Thu 29 Oct, not Mon 2 Nov. Each week is now six working days, Thursday to Wednesday, with Sunday off. The new release dates are v0.1 on Wed 11 Nov and v1.0 on Wed 2 Dec (see `PLAN.md` and `DECISIONS.md` #006).

## Today: Week 1, Day 1 (Thu 29 Oct)
- [x] Create the private GitHub repo with the command above. Done 29 Oct: https://github.com/Negotiator-10/futeq-sentinel (private, `main` tracks `origin/main`).
- [x] Read the NSE Clearing FAQ and draft `docs/notes_faq.md`. Done 30 Oct. All 7 questions answered in my own words.
- [ ] Write the first `LEARNING.md` entry.
- [ ] End-of-day check: explain the FAQ back to Claude, who will ask follow-up questions.

## Where I actually am (Sat 31 Oct)
Two days behind the plan: D1 is not closed and D2 has not started. Today is D3 on paper.

Claude reviewed the FAQ notes on 30 Oct. Right: the utilisation formula, the hysteresis reasoning, the 10/20/30% entity limits. Six rows still need a second pass against the primary source:
1. Q3, the ban entry threshold: the number I wrote does not match the FAQ.
2. Q1, why a delta-based measure beats counting contracts: not answered.
3. Q2, MWPL: I named only one of the two quantities, and no floor.
4. Q4, the base position a ban-period breach is measured against, and which day's delta.
5. Q6, what the penalty is counted per (three dimensions).
6. Q7, the actual file names. This gates the D5 feasibility check.

`docs/doubts.md` (doubts and references to follow up) and `docs/interview_answers.md` (the six-beat answer spine: Why, Count, Cap, Cross, Clear, Cost) were added on 29 and 30 Oct.

The teach-back is deliberately postponed until the numbers are right, so I don't rehearse wrong facts.

## NSE trading holidays in the project window
Checked on nseindia.com on 28 Oct 2026. The file watcher must know these dates.

| Date | Day | What happens |
|---|---|---|
| 8 Nov 2026 | Sunday | Muhurat trading (special one-hour session). Expect files on a Sunday. Timings are notified separately by NSE. |
| 10 Nov 2026 | Tuesday | Holiday (Diwali Balipratipada). No files. |
| 24 Nov 2026 | Tuesday | Holiday (Guru Nanak Jayanti). No files. |
| 25 Dec 2026 | Friday | Holiday (Christmas). After the project window. |

Other dates to watch: Mon 7 Dec 2026, when NSE retires the older file formats (see `docs/READING.md`).

## Sat 31 Oct, end of day
Verified MWPL against SEBI 2025/79 para 5.2.3: the formula has three limbs, not two, and the floor
of 10% of free float binds in the worked example, tripling MWPL. Claude read and indexed all five
Week 1 sources, which turned up NSE's published delta formula (SURV70553 Annexure 2) and a
15-minute intraday cure period. Three commits pushed. Still open from Day 1: `LEARNING.md` and the
teach-back.

Working Sun 1 Nov, the scheduled day off, to pull back the slip. Tomorrow is D4's work.

## Sun 1 to Mon 2 Nov: D4's work
Excel on this laptop wants activation, so I rebuilt the MWPL sheet from scratch in a browser
spreadsheet and worked it from memory. All eleven numbers came out right, every cell a formula
referencing an input, every unit labelled. Hand-calculations now live in the repo as `.csv`
alongside the `.xlsx`, because git can diff a CSV and pytest can read one.

`SPEC.md` is half written: six of twelve rule rows done, each with a citation, a function name and
a named test case. The three rows I worked myself each turned up a gap that the summaries had
hidden:

1. Para 5.2.3 compares shares against rupees and never says which price to convert at.
2. Para 5.2.4 names no reset months, so the quarterly calendar is configuration, not a constant.
3. Para 5.2.6 says the test is whether FutEq OI **exceeds** 95% — so a stock sitting exactly on
   95% is not in ban.

Chasing the third one closed the 80% question that had been open since 31 Oct. It is in the SEBI
Master Circular of 30 Dec 2024, Chapter 5, clause 3.3.2.1.2.3, and the wording is "80% **or
below**" — inclusive, the opposite of the 95% entry. The same chapter also reframed the penalty
question: clause 3.3.2.1.2.2 sets the base and the timing but leaves the percentage to the
exchange, so the 1% / Rs 1 lakh / Rs 5,000 figures can never be verified against SEBI. They have
to come from an NSE circular. And clause 3.3.2.1.3 describes the 6:30 PM MWPL file, per security,
with MWPL and OI both in number of shares — which answers part of Day 1's Q7 for free.

Still open from Day 1: `LEARNING.md`, the `notes_faq.md` second passes, and the teach-back.
`docs/doubts.md` is still empty, which is the discipline I keep deferring.

## Mon 2 Nov, end of day: the config, and what filling it taught me
I filled every stub in `config/rules.yaml` myself — about fifty thresholds, drawn from the
sixteen spec rows. The regulatory facts came out largely right. The encoding came out wrong in
five ways, each repeated across the file:

1. Indentation that orphaned a whole block, so my correct ban-exit entry was attached to nothing.
2. `key:"value"` with no space after the colon. The file would not parse at all.
3. Prose in the `value` slot where a boolean belonged. `sign_change_allowed` is a yes/no
   question and I answered it with a paragraph, which an engine reads as "yes".
4. Values that YAML silently reads as something else: `15:30` is the integer 930, `1,500` is a
   string. Both look right to a reader.
5. Three wrong figures, including `minutes_in_year: 8,670`.

The fifth one is the only one that matters, and it is the lesson of the day. 8,670 is the
minutes-to-expiry in NSE's worked example — the numerator of T, not the denominator. Every other
mistake in that file broke loudly: a parse error, a crash, a string where a number belonged.
That one would have run. It would have made T come out at 1.0 instead of 0.0165 and corrupted
every option delta by about sixty times, producing output indistinguishable from correct output.
I now think that is the whole argument for the config file and the loader: not tidiness, but that
the errors worth defending against are the ones that still run.

Claude rewrote the file at my instruction, which is the third time this week I have asked for
work that `CLAUDE.md` assigns to me, and the worst of the three — these numbers are the project.
Recorded at the top of `rules.yaml` and in `TASKS.md`. The debt is re-deriving five thresholds
from memory and diffing them against the file.

Automation 5 is done: `src/sentinel/rules.py` loads 50 thresholds and refuses, at load time, any
one that cannot say where it came from. Three states rather than two — verified, assumed,
unverified — because the reset calendar is a guess the engine cannot run without, while the
penalty rate is a guess it must refuse to make. 34 tests pass. Decisions #007 to #009 logged.

## Superseded: next task as at 31 Oct morning
Read paragraph 5.2 of SEBI circular 2025/79 (link in `docs/READING.md`) and fix the Q2 row of `docs/notes_faq.md`: both quantities that set MWPL, the floor, and the reset frequency. Then work out one stock's MWPL and utilisation by hand in Excel. That is D2's work, and it closes the biggest gap in the notes at the same time.
