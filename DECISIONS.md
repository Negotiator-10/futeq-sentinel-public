# Decision log

Append only. Each entry: the decision, why, the evidence, and the outcome.

## #001: Project choice, 28 Oct 2026
- **Decision:** build FutEq Sentinel, an automated NSE F&O position-limit, ban-period and OTR replay engine.
- **Why:**
  - It addresses a new burden on Indian prop and HFT desks: SEBI 2025/79 and 2025/122, effective 1 Oct 2025, with 10+ new or changed member files, random intraday snapshots and per-day penalties.
  - No open replay tool was found.
  - NSE's published ban list gives an external referee to validate against.
  - It fits the trade-monitoring roles at NK, Qode, Graviton and iRage.
- **Evidence:** `docs/research_report.md` (deep research, 28 Oct 2026), where it ranked 1 of 12 ideas.
- **Alternatives rejected:**
  - Model-validation report generator: too close to my VaR engine.
  - Point-in-time NIFTY constituents: data risk, and it overlaps my NSE project.
  - PMS, wealth and tax engines: weak signal to prop-firm recruiters.
- **Outcome:** accepted.

## #002: Tutor mode, 28 Oct 2026
- **Decision:** I write the core logic myself. Claude gives hints, reviews my code and handles the plumbing.
- **Why:** in my NSE project Claude wrote most of the code. For interviews I must be able to explain and re-derive every rule without notes.
- **Outcome:** accepted; written into `CLAUDE.md`.

## #003: Schedule and scope, 28 Oct 2026
- **Decision:** 5 weeks at about 30 hours a week (Mon to Sat, Sunday off), with week 6 as a buffer.
- **Scope:** all 9 automation pieces plus the full engine and the OTR module.
- **Releases:** v0.1 on 14 Nov for middle-office applications, v1.0 on 5 Dec for prop firms.
- **If the plan slips:** cut the live page first, then OTR.
- **Outcome:** accepted.

## #004: No C++ for now, 28 Oct 2026
- **Decision:** skip the optional C++ port of the snapshot hot path.
- **Why:** my target roles (trade monitoring, middle office) value domain fluency and data correctness more than C++.
- **Revisit if:** I start aiming at core HFT developer roles.
- **Outcome:** accepted.

## #005: Environment, 28 Oct 2026
- **Decision:** dedicated conda env `sentinel` (Python 3.12, 64-bit).
- **Why:** the default Python on PATH is a 32-bit 3.13 without pandas wheels.
- **Outcome:** accepted.

## #006: Start today, 29 Oct 2026
- **Decision:** start Week 1 on Thu 29 Oct instead of Mon 2 Nov. Weeks run Thursday to Wednesday (six working days, Sunday off). Week 0 reading moves into Week 1 Day 1.
- **New release dates:**
  - v0.1 on Wed 11 Nov
  - v1.0 on Wed 2 Dec
  - Buffer from Thu 3 to Wed 9 Dec, which still includes the 7 Dec format cutover
- **Why:** I want to start immediately.
- **Outcome:** accepted; `PLAN.md` rewritten with the new dates.
