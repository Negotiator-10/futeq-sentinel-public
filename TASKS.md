# Daily task list

Every day's tasks, broken small enough to tick. `PLAN.md` is the strategy, `progress.md` is the narrative, this file is the checklist. Claude ticks items as they're finished; anything still unticked on a past day is carried over and comes first.

Items marked **(Claude)** are plumbing I don't do myself. Everything else is mine.

**Do next:** Sun 1 Nov — working the scheduled day off to pull back the slip. Doing D4's work
(`SPEC.md` and `config/rules.yaml`), with the leftover D1 items folded in. See the D4 block below.

---

## Week 1 (Thu 29 Oct to Wed 4 Nov): rules, spec, data in

### D1 — Thu 29 Oct
- [x] Create the private GitHub repo **(Claude)**
- [x] Read the NSE Clearing FAQ
- [x] Draft `docs/notes_faq.md`, all 7 questions in my own words
- [ ] Q1 second pass: why a delta-based measure beats counting contracts
- [ ] Q2 second pass: both quantities that set MWPL, the floor, the reset frequency
- [ ] Q3 second pass: the ban entry threshold (the number I wrote is wrong)
- [ ] Q4 second pass: the base position a breach is measured against, and which day's delta
- [ ] Q6 second pass: what the penalty is counted per (three dimensions)
- [ ] Q7 second pass: name the actual NSE files
- [ ] Rewrite the one-line summary as the mechanism, not a description of the document
- [ ] First `LEARNING.md` entry
- [ ] Teach-back: six beats, Why / Count / Cap / Cross / Clear / Cost

### D2 — Fri 30 Oct
- [x] Read paragraph 5.2 of SEBI 2025/79
- [ ] Fix the Q2 row of `docs/notes_faq.md` from that paragraph — still unchanged on disk as of 31 Oct
- [x] Mark the MWPL row verified: `SEBI 2025/79 para 5.2.3 and 5.2.4, read 31 Oct 2026`
- [x] Put the rows not covered by para 5.2 back to `unverified`
- [x] Settle the floor: **10% of free float** (para 5.2.3). It binds in the worked example and
  triples MWPL, so Claude's first answer sheet was wrong by 3x
- [ ] New doubt for `docs/doubts.md`: para 5.2.3 compares 15% of free float (shares) with 65x ADDV
  (rupees) but does not say which price to convert at. The engine needs an answer
- [x] New open row: the 80% ban exit is **not** in 2025/79 para 5.2 or 5.3. Find where it is set.
  **Closed 2 Nov:** Master Circular 30 Dec 2024, Ch 5, cl 3.3.2.1.2.3, and the boundary is
  inclusive — "80% or below"
- [x] Settle the 90 vs 95 conflict: entry is 95%, exit 80%. I had written 90% and caught it myself.
- [ ] Correct the 90% in `notes_faq.md` Q3 to 95%, in my own words
- [x] Fill the inputs and calculation blocks of `docs/handcalcs/mwpl_by_hand.xlsx` for a liquid stock
- [x] Work out that stock's utilisation by hand (market FutEq OI / MWPL)
- [x] Solve backwards: the FutEq OI at the ban entry threshold, at release, and today's headroom in lots
- [ ] Repeat for an illiquid stock and note which quantity binds
- [x] Copy the final numbers into `docs/handcalcs/mwpl_by_hand.md` as the engine's first test case

### D3 — Sat 31 Oct
- [ ] Read SEBI 2025/122 (intraday limits for index derivatives)
- [ ] Read NSE SURV70553 (snapshot monitoring, SOP report layout)
- [ ] Work out one book's FutEq exposure by hand
- [ ] Work out a ban entry by hand
- [ ] Work out a ban exit by hand
- [ ] Record all three as test cases

### D4 — brought forward to Sun 1 Nov

**First, clear the two Day 1 leftovers (30 min)**
- [ ] Write the first `LEARNING.md` entry. Four lessons, all from mistakes: catching my own 90/95
  error; "verified" means source + paragraph + date, not a feeling; the floor tripled MWPL so a
  summary is not a source; units break engines, not formulas
- [ ] Fix `notes_faq.md` Q3: 90% to 95%, in my own words
- [ ] Fix `notes_faq.md` Q1 using the para 6 table in `READING.md`: exactly three things started on
  1 Oct 2025 (MWPL definition, ban-period position creation, entity limits). FutEq OI was already
  in force, so "they introduced FutEq OI" is the wrong answer

**Then the main job: `SPEC.md` (about 90 min)**
- [ ] One row per rule: the clause, its citation, the function that will implement it, and the
  test that proves it. Every citation is already in `docs/READING.md`
- [ ] Cover: FutEq OI (5.1), MWPL and the floor (5.2.3), quarterly reset (5.2.4), ban entry at 95%
  (5.2.6, 5.3.1), ban-period reduction with the sign rule and passive-increase carve-out (5.3.2),
  entity limits all five categories (5.8.1), intraday limits and the 15-minute cure period
  (2025/122 para 4, SURV70553 3.9-3.13), delta (SURV70553 Annexure 2)
- [ ] Where a rule has no source yet, write the row anyway and mark it `UNVERIFIED`. The two known
  gaps are the single-stock penalty and the 80% ban exit
- [ ] While writing the ban section, work a ban entry and a ban exit by hand. That is D3's
  hand-calculation, folded in here instead of done separately

**Then `config/rules.yaml` (about 60 min)**
- [ ] Every threshold with its citation as a sibling field. No number without a source
- [ ] Automation 5: a validated loader **(Claude)**

**Then (30 min)**
- [ ] Teach-back, using the six-beat spine
- [ ] Decide whether to amend `PLAN.md` W3 D1: NSE publishes Black-Scholes N(d1) with historical
  volatility, not the Black-76-with-implied-vol that Path B assumed

**Done, 1 Nov, from memory.** Rebuilt the sheet from scratch in a browser spreadsheet, because
Excel on this laptop wants activation.
- [x] The two quantities from para 5.2.3, as formulas referencing the input cells
- [x] The units, and the conversion that makes them comparable
- [x] The lower of the two, the floor, MWPL
- [x] Utilisation, then headroom in lots
- [x] All eleven numbers correct, every cell a formula, every unit labelled
- [ ] The three CHECKS rows are still blank. "Which quantity binds, and why" is the interview
  question in this sheet; answer it in one line before the teach-back
- [ ] Log the open doubt in `docs/doubts.md`: para 5.2.3 does not say which price to convert
  65 x ADDV at

Hand-calculations now live in the repo as `.xlsx` **and** `.csv`. Git can diff a CSV and pytest can
read one; neither is true of a spreadsheet. The `.md` companion holds the reasoning.

**Knowingly deferred:** D3's reading of 2025/122 and SURV70553. Claude has read and indexed both,
but I have not read them myself, and that debt is mine to clear before week 3.

### D5 — Tue 3 Nov
- [ ] Check which NSE files download without a login: bhavcopy, OI/MWPL, ban list, contract delta
  - Evidence from 31 Oct: fetching the FAQ PDF stalled once for 120s with 0 bytes received, then
    succeeded in 0.5s on retry, same URL and user-agent. So NSE's hosts stall intermittently rather
    than block outright. The downloader needs a connect timeout, a total timeout, and retries with
    backoff; "it worked once" proves nothing about tomorrow.
- [ ] Choose Path A or Path B and log the decision in `DECISIONS.md`
- [ ] A polite downloader, rate-limited, with a user-agent and checksums **(Claude)**

### D6 — Wed 4 Nov
- [ ] Bhavcopy parser, with a fixture
- [ ] OI file parser, with a fixture
- [ ] Automation 9a: GitHub Actions runs the tests on every push **(Claude)**
- [ ] Teach-back
- [ ] Week 1 interview questions: What is FutEq OI? How is MWPL calculated? Why does a position in a banned stock still matter?

---

## Weeks 2 to 6
Expanded here one week at a time, when we get to it. See `PLAN.md` for the outline.

- [ ] Week 2 (Thu 5 to Wed 11 Nov): reliable data, reconciliation, runner, **v0.1**
- [ ] Week 3 (Thu 12 to Wed 18 Nov): limit engine, data quality, circular watcher
- [ ] Week 4 (Thu 19 to Wed 25 Nov): validation against NSE, entity limits, alerts
- [ ] Week 5 (Thu 26 Nov to Wed 2 Dec): OTR, reports, live page, **v1.0**
- [ ] Week 6 (Thu 3 to Wed 9 Dec): buffer and the 7 Dec format cutover
