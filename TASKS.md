# Daily task list

Every day's tasks, broken small enough to tick. `PLAN.md` is the strategy, `progress.md` is the narrative, this file is the checklist. Claude ticks items as they're finished; anything still unticked on a past day is carried over and comes first.

Items marked **(Claude)** are plumbing I don't do myself. Everything else is mine.

**Do next:** D4 is closed. `config/rules.yaml` holds 50 thresholds and the loader enforces them,
so D5's feasibility check is the next real task. Before it, the one thing I still owe D4 is the
review of `SPEC.md` rows 6 to 16 — the config now depends on those citations being right, so a
wrong row is a wrong threshold with a test asserting it.

**Still owed from Day 1,** and now with good material from 1-2 Nov: the first `LEARNING.md` entry,
three entries in `docs/doubts.md`, the `notes_faq.md` second passes, and the teach-back.

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
- [x] Read SEBI 2025/122 (intraday limits for index derivatives). Read it myself, 2 Nov
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
- [x] One row per rule: the clause, its citation, the function that will implement it, and the
  test that proves it
- [x] Sixteen rows, not twelve. Reading the paragraphs turned up four rules with no row at all:
  para 5.4 (intraday MWPL monitoring for single stocks), 5.5.2 (index futures limits), 5.5.2.5
  (the second passive-breach carve-out) and 5.5.3 (the hedge exemption)
- [x] Rows marked `UNVERIFIED` where there is no source: the penalty rate (row 12), the ASM
  trigger (row 15), and whether the delta convention covers single stocks (row 11)
- [ ] **Review rows 6 to 16.** I wrote rows 1 to 5; Claude drafted 6 to 16 from the primary text at
  my request, against the tutor rule in `CLAUDE.md`. Reviewing them is the first job next session,
  and the row most worth arguing about is 7 — whether one function with a category argument is
  right, or whether FPI Cat II deserves its own
- [ ] Work a ban entry and a ban exit by hand. Still not done; rows 4 and 5 give the numbers to
  check against

**Then `config/rules.yaml` (about 60 min)**
- [x] File created with the `value` / `operator` / `source` / `verified` / `note` shape, the MWPL
  block filled as a worked example, and a stub for every other threshold **(Claude)**
- [x] Fill the stubs. I filled all of them myself from the sixteen spec rows. The regulatory facts
  came out largely right and the encoding came out wrong in five repeated ways — see the note at
  the top of `rules.yaml`. **Claude then rewrote the file at my instruction,** which is the third
  departure from the tutor rule this week and the one I should least have asked for, because these
  numbers are the core of the project
- [x] Add `operator` wherever the wording makes a boundary inclusive or exclusive
- [x] Leave the three `meta.unverified` entries null, each with its reason
- [x] Automation 5: a validated loader. `src/sentinel/rules.py`, 50 thresholds loaded, 34 tests,
  all passing. Also `pyproject.toml`, so `pytest` works from the root with no install **(Claude)**
- [ ] **Re-derive five thresholds from memory, into a blank file, and diff against `rules.yaml`.**
  Entry, exit, the three index futures shares and the Rs 500 cr floor. This replaces the writing
  Claude did for me. If I cannot reproduce them, I do not know them
- [ ] Read `src/sentinel/rules.py` and answer two questions: why does `Threshold.compare()` raise
  when no operator is declared, instead of defaulting to `>`? And why is `verified: "2026-11-02"`
  in quotes an error rather than a convenience?

**What the config exercise actually taught me, 2 Nov**
- [ ] Add to `LEARNING.md`: the five encoding classes, and specifically that
  `minutes_in_year: 8,670` would not have crashed. Every other mistake in that file broke loudly.
  That one would have corrupted every option delta by about sixty times and produced output that
  looked exactly like correct output. The lesson is not "be careful with YAML" — it is that the
  dangerous errors are the ones that still run

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

**Knowingly deferred:** NSE SURV70553. I read SEBI 2025/122 myself on 2 Nov; SURV70553 Claude has
read and indexed but I have not, and that debt is mine to clear before week 3. It is the source
for the 15-minute cure period, the snapshot schedule and the whole delta convention in Annexure 2,
so it sits behind four rows of `SPEC.md` and the entire `mechanics` block of `config/rules.yaml`.

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

### D5 — brought forward to Mon 2 Nov
- [x] Check which NSE files download without a login. **All five are public in a browser and none
  fetch from a script**: 403 on the homepage, tarpit on the archive paths, SEBI fine from the same
  machine in the same second. `DECISIONS.md` #010 **(Claude probed; the finding corrects my
  31 Oct reading of the same symptom as an intermittent stall)**
- [x] Five files downloaded by hand, checksums and column maps in `docs/READING.md`
- [x] **A contract-delta file exists**: `Contract_Delta_30102026.csv`, 133,620 rows, every
  contract every day, with Delta Factor exactly 1.0 for futures. Path A is nearly free
- [x] **`Limit for Next Day` = 0.95 x MWPL - FutEq OI**, exact on 216/216 rows. That is cell B21
  of the sheet I rebuilt from memory on 1 Nov. It reconciles only against FutEq OI, never
  notional (0/216), which settles which basis NSE uses
- [ ] **Decide Path A or Path B and log it.** Still mine. The ground has moved: both a
  per-contract delta file and a published FutEq OI file exist, so A and B are no longer
  alternatives - B becomes a validation layer over A, with two independent scoring keys at
  different levels of aggregation
- [x] **Log the ban-state design decision in `DECISIONS.md`.** Done 4 Nov as #011, four
  questions answered: the signature, what state is keyed on, how day one seeds and recovers
  from a gap, and what the engine does when state is unavailable. The reasoning is mine;
  Claude transcribed it and corrected two answers that were sound but aimed at the wrong
  system - a warm-up replay from my VaR engine, and an order-blocking scope from an RMS.
  That pattern is the day's real lesson and is owed to `LEARNING.md`
- [ ] **Repayment for #011:** re-derive all four answers from memory into a blank file and
  diff against the entry, then rewrite the Decision paragraph myself without reading Claude's.
  Four specific tests are listed at the bottom of #011. First job next session
- [ ] **Update `SPEC.md` rows 4 and 5:** `is_in_ban()` now takes three arguments, not two.
  The rows still describe a two-argument function
- [ ] **Update `PLAN.md` W2:** the runner needs a dated, ISIN-keyed ban-state store, and the
  synthetic prop book needs trades, not just end-of-day holdings (the row 6 finding). Both are
  the same point: a breach needs a reason, not a boolean
- [ ] **Confirm the hysteresis explanation with data, not reasoning.** Download
  `combineoi_<date>.zip` for 29 Oct and the days before, and find the day SAIL's FutEq
  utilisation exceeded 95%. Until then the mechanism is inferred from the clause, not observed
- [ ] Parser note for D6: `fo_secban` has a prose first line, not a header row, and the XML
  inside `combineoi.zip` is not well-formed (spaces in an element name). Use the CSV
