# Five-week plan (starting Thu 29 Oct 2026)

**Hours:** about 30 hours a week, 5 hours a day, 6 days a week, with Sunday off. Job-search time (about 3 hours a week) is separate. Each "week" is six working days, from Thursday to the following Wednesday.

**If the plan slips:** cut in this order: first the live public page, then the OTR module. Both move to week 6. Never cut understanding.

**Daily rhythm (about 5 hours):**
- 1 hour: reading the source and working through an example by hand.
- 2.5 hours: building.
- 30 minutes: review and fixes.
- 30 minutes: learning log and interview drill.
- 30 minutes: buffer.

**Key dates:**
- NSE holidays: Tue 10 Nov and Tue 24 Nov (no files; work as normal).
- Muhurat trading: Sun 8 Nov (files on a Sunday).
- Format cutover: Mon 7 Dec.

## Week 0: setup (done 28 Oct)
- [x] Folder, git, conda env `sentinel`, and the project files.

## Week 1 (Thu 29 Oct to Wed 4 Nov): rules, spec, data in
| Day | Work |
|---|---|
| D1 Thu 29 Oct | Create the private GitHub repo (command in `progress.md`). Read the NSE Clearing FAQ and write a one-page summary in your own words in `docs/notes_faq.md`. Write your first `LEARNING.md` entry. |
| D2 Fri 30 Oct | Read SEBI circular 2025/79. Work out by hand in Excel one stock's MWPL and its utilisation. |
| D3 Sat 31 Oct | Read SEBI 2025/122 and NSE SURV70553. Work out by hand one book's FutEq exposure, and a ban entry and exit. These become the first test cases. |
| D4 Mon 2 Nov | Write `SPEC.md`, mapping each rule clause to the function that implements it. **Automation 5:** `config/rules.yaml` and a validated loader. |
| D5 Tue 3 Nov | Feasibility check: which NSE files download without a login (bhavcopy, OI/MWPL, ban list, contract delta)? Choose Path A or Path B and log the decision. Build a polite downloader that records checksums. |
| D6 Wed 4 Nov | Parsers for the bhavcopy and OI files, with fixtures. **Automation 9a:** GitHub Actions runs the tests on every push. Teach-back. |

Interview questions:
- What is FutEq OI?
- How is MWPL calculated?
- Why does a position in a banned stock still matter?

## Week 2 (Thu 5 to Wed 11 Nov): reliable data, reconciliation, runner, v0.1
Diwali falls this week: Sun 8 is a day off (Muhurat trading), and Tue 10 is an NSE holiday. Keep the 9th and 10th lighter if you need family time.

| Day | Work |
|---|---|
| D1 Thu 5 Nov | **Automation 2:** a file and deadline watcher (new, late and missing files; knows the holidays and the Muhurat Sunday). Data contracts that fail loudly on renamed columns or wrong types. |
| D2 Fri 6 Nov | A point-in-time store with a hash manifest. A reference-data change detector for lot sizes, new and expired contracts, quarterly MWPL resets and new bans. |
| D3 Sat 7 Nov | End-of-day reconciliation (your logic): synthetic internal positions against exchange data, with break types and ageing. |
| D4 Mon 9 Nov | **Automation 8:** a break workflow (open, investigating, resolved) with notes and an audit trail in SQLite. |
| D5 Tue 10 Nov | **Automation 1:** a pipeline runner built from scratch, with dependencies, retries with backoff, safe re-runs, a run log and one command to run it all. |
| D6 Wed 11 Nov | **Release v0.1.** README, tag, make the repo public, and use it in the Citco, JPMorgan and Anand Rathi applications. Teach-back. |

Interview questions:
- How do you find and classify a break?
- Why must a pipeline be safe to re-run?
- What changed with UDiFF?

### Scope change, 9 Nov 2026

- **v0.1 (Wed 11 Nov)** now includes the pipeline runner: one command
  that runs a day end to end.
- **Row 7 (check_entity_limit)** moves to Week 3. Its design is complete
  (#016 and addendum); only the implementation waits.
- **File watcher and break workflow** move to v1.0.

Why: the trading calendar, Muhurat chaining, expiry, flat-day and
(tm, ucc) keying work took the time planned for these. That was the
right trade, because those are what make the result trustworthy.

### Scope change, 11 Nov 2026 (#020)

- **The replay is every trading day from 1 Oct 2025** (Week 4 D1, as planned), downloaded by hand
  one month at a time, newest first, from the pages `scripts/download_checklist.py` writes. About
  3.5 hours of downloads, spread over sessions. **First, the calendar is extended to 2025** from
  NSE's 2025 holiday circular; until then October to December 2025 cannot be replayed.
- **Cut:** the live page (automation 9b) and OTR, which add no evidence; and the index-derivative
  rows, SPEC 8, 9, 10, 13, 14 and 16, from Week 4 D4. The README lists them as not yet covered.
  Row 15, intraday MWPL monitoring for single stocks, is cut too: it needs intraday data, and
  every file here is end of day. The time goes to the replay and row 7.

Why: a year of real days is the only way to check the reset calendar for all four quarters and to
get real transitions, in-band days and boundary rows in numbers that mean something.

## Week 3 (Thu 12 to Wed 18 Nov): limit engine, data quality, circular watcher
| Day | Work |
|---|---|
| D1 Thu 12 Nov | Deltas. Path A, or Path B: Black-76 with implied volatility from settlement prices, plus the error against any published figures. |
| D2 Fri 13 Nov | FutEq OI per underlying, MWPL and utilisation. |
| D3 Sat 14 Nov | Ban logic: entry at 95%, exit at 80% (hysteresis). Next-day ban forecast. Property tests. |
| D4 Mon 16 Nov | **Automation 6:** data-quality monitors for impossible OI jumps, bad prices and missing contracts, with bad records quarantined. |
| D5 Tue 17 Nov | **Automation 7:** a circular watcher that scans the NSE and SEBI circular lists daily for keywords and logs the matches against the affected rules. |
| D6 Wed 18 Nov | Wire everything into the runner. Teach-back. |

Interview questions:
- What is delta?
- Why is delta-based exposure better than counting contracts?
- Why does 95/80 create hysteresis?
- How do you catch a bad print?

## Week 4 (Thu 19 to Wed 25 Nov): validation against NSE, entity limits, alerts
| Day | Work |
|---|---|
| D1 Thu 19 Nov | Replay every trading day since 1 Oct 2025. Score the ban forecasts against NSE's published ban list (precision and recall) and measure the utilisation error. |
| D2 Fri 20 Nov | Explain every mismatch and write it up. This is the headline result. |
| D3 Sat 21 Nov | A synthetic prop book. Entity limits: 10% of MWPL for a client, 20% for the member's own book, 30% combined. |
| D4 Mon 23 Nov | ~~Intraday index-option limits (Rs 5,000 cr net, Rs 10,000 cr gross, Rs 1,500 cr at end of day) with at least 4 random snapshots.~~ Cut (#020): replay and row 7 instead. A ban-period checker that flags an increase or a sign flip against the base (done: row 6). |
| D5 Tue 24 Nov | A penalty calculator with edge-case tests. **Automation 3:** Telegram alerts for forecast bans, breaches, breaks older than 2 days, and late or failed files. |
| D6 Wed 25 Nov | Teach-back. Draft the headline: "matched NSE's ban list on X of Y days". |

Interview questions:
- Your forecast missed a ban. How did you find out why?
- How do random snapshots change self-monitoring?
- Walk me through a ban-period violation.

## Week 5 (Thu 26 Nov to Wed 2 Dec): OTR, reports, live page, v1.0
| Day | Work |
|---|---|
| D1 Thu 26 Nov | ~~**OTR module.**~~ Cut (#020). |
| D2 Fri 27 Nov | **Automation 4:** an evening HTML/PDF morning report, including a section in NSE's SOP column layout. |
| D3 Sat 28 Nov | ~~**Automation 9b:** a scheduled run and a live GitHub Pages forecast page.~~ Cut (#020): no automated downloads are allowed (#010 addendum), and a live page adds no evidence. |
| D4 Mon 30 Nov | A README that leads with results, plus the spec and a diagram. A CLI command, `sentinel replay --from 2025-10-01`. A check that runs are byte-reproducible. |
| D5 Tue 1 Dec | A technical note (6 to 10 pages): what it does, how it was validated, and what it cannot see. Verify every fact in the regulatory table against SEBI and NSE. |
| D6 Wed 2 Dec | **Release v1.0.** Send it to NK, Qode, Graviton and iRage as a follow-up. Full mock interview. |

## Week 6 (Thu 3 to Wed 9 Dec): buffer and format cutover
- Mon 7 Dec: NSE retires the older file formats. The contract tests should catch it; record it for the README.
- Catch up on anything that slipped (live page first, then OTR), fix bugs and polish.
- Final pass on `LEARNING.md` to turn it into an interview story sheet.

## Checklist
All 9 automations:
- [ ] 1. Pipeline runner (W2). In progress: the run log, lock and result tables are built (#019); the runner itself is not.
- [ ] 2. File and deadline watcher (W2). Moved to v1.0.
- [ ] 3. Alerts (W4)
- [ ] 4. Morning report (W5)
- [x] 5. Rules in a config file (W1)
- [ ] 6. Data-quality monitors (W3)
- [ ] 7. Circular watcher (W3)
- [ ] 8. Break workflow (W2). Moved to v1.0.
- [x] 9a. Automatic tests on every push (W1)
- [ ] 9b. Scheduled run and live page (W5). Cut (#020).

Engine:
- [x] Spec
- [ ] Downloader. Files are still fetched by hand (#010).
- [x] Parsers and data contracts
- [x] Point-in-time store
- [ ] Reference-data detector
- [x] Reconciliation
- [ ] Deltas
- [ ] FutEq, MWPL and ban forecast. Partial: the ban forecast is done, but it reads FutEq OI and MWPL as NSE publishes them; I do not compute either yet.
- [x] Validation against NSE (ban forecasts scored against NSE's ban lists: 3241/3241 to 9 Nov)
- [ ] Entity and intraday limits. Row 7 is a stub; designed in #016, built in Week 3.
- [x] Ban-period checker (row 6)
- [ ] Penalties
- [ ] OTR module. Cut (#020).
- [ ] NSE-format daily report

Releases:
- [ ] v0.1 (Wed 11 Nov)
- [ ] v1.0 (Wed 2 Dec)
- [ ] Technical note
- [ ] README

Learning:
- [ ] Daily `LEARNING.md` entries
- [ ] 6 weekly teach-backs
- [ ] Interview drills
- [ ] Final mock interview

Verify before going public (see `docs/READING.md`):
- [ ] OTR bands and dates
- [x] MWPL formula and the 10/20/30% limits (SEBI 2025/79 paras 5.2.3, 5.2.4 and 5.8.1)
- [x] Intraday limits start date (SEBI 2025/122 para 6)
- [ ] Whether the delta files are public
- [ ] Expiry-day changes. Observed in the bhavcopies, not yet checked against a circular.
