# Daily task list

Every day's tasks, broken small enough to tick. `PLAN.md` is the strategy, `progress.md` is the narrative, this file is the checklist. Claude ticks items as they're finished; anything still unticked on a past day is carried over and comes first.

Items marked **(Claude)** are plumbing I don't do myself. Everything else is mine.

**Do next:** D2's paragraph 5.2 reading, then the MWPL arithmetic by hand.

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
- [ ] Read paragraph 5.2 of SEBI 2025/79
- [ ] Fix the Q2 row of `docs/notes_faq.md` from that paragraph
- [ ] Mark the MWPL row in the `docs/READING.md` facts table as verified, citing 5.2
- [ ] Work out one stock's MWPL by hand in Excel
- [ ] Work out that stock's utilisation by hand (market FutEq OI / MWPL)
- [ ] Keep the numbers; they become the engine's first test case

### D3 — Sat 31 Oct
- [ ] Read SEBI 2025/122 (intraday limits for index derivatives)
- [ ] Read NSE SURV70553 (snapshot monitoring, SOP report layout)
- [ ] Work out one book's FutEq exposure by hand
- [ ] Work out a ban entry by hand
- [ ] Work out a ban exit by hand
- [ ] Record all three as test cases

### D4 — Mon 2 Nov
- [ ] Write `SPEC.md`, mapping each rule clause to the function that implements it
- [ ] Fill in `config/rules.yaml` with the thresholds and their citations
- [ ] Automation 5: a validated loader for `config/rules.yaml` **(Claude)**

### D5 — Tue 3 Nov
- [ ] Check which NSE files download without a login: bhavcopy, OI/MWPL, ban list, contract delta
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
