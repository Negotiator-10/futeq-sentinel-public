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

## Next task (now)
Read paragraph 5.2 of SEBI circular 2025/79 (link in `docs/READING.md`) and fix the Q2 row of `docs/notes_faq.md`: both quantities that set MWPL, the floor, and the reset frequency. Then work out one stock's MWPL and utilisation by hand in Excel. That is D2's work, and it closes the biggest gap in the notes at the same time.
