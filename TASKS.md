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
- [x] Read paragraph 5.2 of SEBI 2025/79
- [ ] Fix the Q2 row of `docs/notes_faq.md` from that paragraph — still unchanged on disk as of 31 Oct
- [x] Mark the MWPL row verified: `SEBI 2025/79 para 5.2.3 and 5.2.4, read 31 Oct 2026`
- [x] Put the rows not covered by para 5.2 back to `unverified`
- [x] Settle the floor: **10% of free float** (para 5.2.3). It binds in the worked example and
  triples MWPL, so Claude's first answer sheet was wrong by 3x
- [ ] New doubt for `docs/doubts.md`: para 5.2.3 compares 15% of free float (shares) with 65x ADDV
  (rupees) but does not say which price to convert at. The engine needs an answer
- [ ] New open row: the 80% ban exit is **not** in 2025/79 para 5.2 or 5.3. Find where it is set
- [x] Settle the 90 vs 95 conflict: entry is 95%, exit 80%. I had written 90% and caught it myself.
- [ ] Correct the 90% in `notes_faq.md` Q3 to 95%, in my own words
- [ ] Fill the inputs and calculation blocks of `docs/handcalcs/mwpl_by_hand.xlsx` for a liquid stock
- [ ] Work out that stock's utilisation by hand (market FutEq OI / MWPL)
- [ ] Solve backwards: the FutEq OI at the ban entry threshold, at release, and today's headroom in lots
- [ ] Repeat for an illiquid stock and note which quantity binds
- [ ] Copy the final numbers into `docs/handcalcs/mwpl_by_hand.md` as the engine's first test case

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
