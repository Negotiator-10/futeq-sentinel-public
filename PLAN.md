# Five-week plan

About 30 hours a week: 5 hours a day, Monday to Saturday, with Sunday off. Job-search time (about 3 hours a week) is separate.

If the plan slips, cut in this order: first the live public page, then the OTR module (both move to week 6). Never cut understanding.

**Daily rhythm (about 5 hours):**
1. 1 hour reading the source or working the example by hand.
2. 2.5 hours building.
3. 30 minutes of review and fixes.
4. 30 minutes on the learning log and an interview-question drill.
5. 30 minutes of buffer.

## Week 0: setup (Thu 29 to Sat 31 Oct)
- [x] Folder, git repo, conda env `sentinel`, project files (done by Claude on 28 Oct).
- [ ] Read the NSE Clearing FAQ on the new position limits and write a one-page summary in your own words in `docs/notes_faq.md` (link in `docs/READING.md`).
- [ ] Look over the NSE holiday list for Nov and Dec 2026 in `progress.md`.

## Week 1 (Mon 2 to Sat 7 Nov): rules, spec, data in
| Day | Work |
|---|---|
| Mon | Read SEBI circular 2025/79. By hand in Excel: one stock's MWPL and utilisation. |
| Tue | Read SEBI 2025/122 and NSE SURV70553. By hand: one book's FutEq exposure, and a ban entry and exit. These become the first test cases. |
| Wed | Write `SPEC.md`, mapping each rule clause to a function. **Automation 5:** create `config/rules.yaml` and a validated loader. |
| Thu | Feasibility: which NSE files download without login (bhavcopy, OI/MWPL, ban list, contract delta)? Decide Path A (NSE deltas) or Path B (own Black-76 deltas) and log it. Build a polite downloader with checksums. |
| Fri | Parsers for bhavcopy and OI files, with fixtures. **Automation 9a:** GitHub Actions runs the tests on every push. |
| Sat | **Automation 2:** file and deadline watcher (new, late and missing files; holiday-aware). Teach-back. |

Interview questions: What is FutEq OI? How is MWPL calculated? Why does an existing position in a banned stock still matter?

## Week 2 (Mon 9 to Sat 14 Nov): reliable data, reconciliation, runner, v0.1
Diwali falls this week: check NSE's holiday and Muhurat dates.

| Day | Work |
|---|---|
| Mon | Data contracts that fail loudly on renamed columns or wrong types. Point-in-time store with a hash manifest. |
| Tue | Reference-data change detector: lot sizes, new and expired contracts, quarterly MWPL resets, new bans. |
| Wed | End-of-day reconciliation (your logic): synthetic internal positions against exchange data, with break types and ageing. |
| Thu | **Automation 8:** break workflow (open, investigating, resolved), with notes and an audit trail in SQLite. |
| Fri | **Automation 1:** pipeline runner from scratch. Dependencies, retries with backoff, safe re-runs, run log, one command. |
| Sat | **Release v0.1.** README, tag, make the repo public, use it in the Citco, JPMorgan and Anand Rathi applications. Teach-back. |

Interview questions: How do you find and classify a break? Why must a pipeline be safe to re-run? What changed with the UDiFF format?

## Week 3 (Mon 16 to Sat 21 Nov): limit engine, data quality, circular watcher
| Day | Work |
|---|---|
| Mon | Deltas. Path A, or Path B: Black-76 with implied volatility from settlement prices, plus error against any published figures. |
| Tue | FutEq OI per underlying, MWPL and utilisation. |
| Wed | Ban logic: 95% entry and 80% exit (hysteresis). Next-day ban forecast. Property tests. |
| Thu | **Automation 6:** data-quality monitors (impossible OI jumps, bad prices, missing contracts), quarantining bad records. |
| Fri | **Automation 7:** circular watcher. Scan the NSE and SEBI circular lists daily for keywords and log matches against the affected rules. |
| Sat | Wire everything into the runner. Teach-back. |

Interview questions: What is delta, and why is delta-based exposure better than counting contracts? Why do the 95/80 thresholds create hysteresis? How would you catch a bad print?

## Week 4 (Mon 23 to Sat 28 Nov): validation against NSE, entity limits, alerts
| Day | Work |
|---|---|
| Mon | Replay every trading day since 1 Oct 2025. Score ban forecasts against NSE's published ban list (precision and recall) and the utilisation error. |
| Tue | Explain every mismatch and write it up. This is the headline result. |
| Wed | Synthetic prop book. Entity limits: 10% of MWPL for a client, 20% for the member's own book, 30% combined. |
| Thu | Intraday index-option limits (Rs 5,000 cr net, Rs 10,000 cr gross, Rs 1,500 cr end of day) with at least 4 random snapshots. Ban-period checker (an increase or a sign flip against the base). |
| Fri | Penalty calculator with edge-case tests. **Automation 3:** Telegram alerts for forecast bans, breaches, breaks older than 2 days, and late or failed files. |
| Sat | Teach-back. Draft the headline: "matched NSE's ban list on X of Y days". |

Interview questions: Your forecast missed a ban, so how did you find out why? How do random snapshots change the way a firm must monitor itself? Walk me through a ban-period violation.

## Week 5 (Mon 30 Nov to Sat 5 Dec): OTR, reports, live page, v1.0
| Day | Work |
|---|---|
| Mon | **OTR module.** 2026 exemption bands in config, marked unverified until checked; old-rules vs new-rules comparison on synthetic order logs. |
| Tue | **Automation 4:** evening HTML/PDF morning report, including a section in NSE's SOP column layout. |
| Wed | **Automation 9b:** scheduled run and a live GitHub Pages forecast page. If NSE blocks cloud downloads, run locally and push the results. |
| Thu | README that leads with results, plus the spec and a diagram. CLI `sentinel replay --from 2025-10-01`. Byte-reproducibility check. |
| Fri | Technical note (6 to 10 pages): what it does, how it was validated, what it cannot see. Verify every fact in the regulatory table against SEBI and NSE. |
| Sat | **Release v1.0.** Send it to NK, Qode, Graviton and iRage as a follow-up. Full mock interview. |

## Week 6 (Mon 7 to Sat 12 Dec): buffer and format cutover
- Mon 7 Dec: NSE retires the older file formats. The contract tests should catch it; record it for the README.
- Catch up on anything that slipped (live page, then OTR), fix bugs, polish.
- Final pass on `LEARNING.md` to turn it into an interview story sheet.

## Checklist
All 9 automations:
- [ ] 1. Pipeline runner (W2)
- [ ] 2. File and deadline watcher (W1)
- [ ] 3. Alerts (W4)
- [ ] 4. Morning report (W5)
- [ ] 5. Rules in a config file (W1)
- [ ] 6. Data-quality monitors (W3)
- [ ] 7. Circular watcher (W3)
- [ ] 8. Break workflow (W2)
- [ ] 9a. Automatic tests on every push (W1)
- [ ] 9b. Scheduled run and live page (W5)

Engine:
- [ ] Spec
- [ ] Downloader
- [ ] Parsers and data contracts
- [ ] Point-in-time store
- [ ] Reference-data change detector
- [ ] Reconciliation
- [ ] Deltas
- [ ] FutEq, MWPL and ban forecast
- [ ] Validation against NSE
- [ ] Entity and intraday limits
- [ ] Ban-period checker
- [ ] Penalties
- [ ] OTR module
- [ ] NSE-format daily report

Releases:
- [ ] v0.1 (14 Nov)
- [ ] v1.0 (5 Dec)
- [ ] Technical note
- [ ] README

Learning:
- [ ] Daily `LEARNING.md` entries
- [ ] 6 weekly teach-backs
- [ ] Interview drills
- [ ] Final mock interview

Verify before going public (see `docs/READING.md`):
- [ ] OTR bands and dates
- [ ] MWPL formula and the 10/20/30% limits
- [ ] Intraday limits start date
- [ ] Whether the delta files are public
- [ ] Expiry-day changes
