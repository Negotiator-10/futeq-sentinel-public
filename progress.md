# Progress

Start every session by reading this file, then `PLAN.md` for today's row.

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
- [ ] Create the private GitHub repo with the command above.
- [ ] Read the NSE Clearing FAQ (link in `docs/READING.md`). Write a one-page summary in your own words in `docs/notes_faq.md`, answering the guiding questions there.
- [ ] Write the first `LEARNING.md` entry.
- [ ] End-of-day check: explain the FAQ back to Claude, who will ask follow-up questions.

## NSE trading holidays in the project window
Checked on nseindia.com on 28 Oct 2026. The file watcher must know these dates.

| Date | Day | What happens |
|---|---|---|
| 8 Nov 2026 | Sunday | Muhurat trading (special one-hour session). Expect files on a Sunday. Timings are notified separately by NSE. |
| 10 Nov 2026 | Tuesday | Holiday (Diwali Balipratipada). No files. |
| 24 Nov 2026 | Tuesday | Holiday (Guru Nanak Jayanti). No files. |
| 25 Dec 2026 | Friday | Holiday (Christmas). After the project window. |

Other dates to watch: Mon 7 Dec 2026, when NSE retires the older file formats (see `docs/READING.md`).

## Next session: Week 1, Day 2 (Fri 30 Oct)
Read SEBI circular 2025/79, then work out one stock's MWPL and utilisation by hand in Excel.
