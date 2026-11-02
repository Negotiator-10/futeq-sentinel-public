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

## #007: Per-key provenance in the rules config, 2 Nov 2026
- **Decision:** every threshold in `config/rules.yaml` carries its own `source` and `verified`
  fields, with no block-level or inherited provenance anywhere in the file. The seven entity
  limits each repeat the same circular, differing only in the paragraph.
- **Why:** the alternative was one shared `source` per block, which is shorter and reads better.
  All seven entity limits do come from one paragraph range, 5.8.1.1 to 5.8.1.5, so the shared
  form is defensible. I chose repetition because the loader then has exactly one rule to enforce
  and no exceptions to it. A validator with a special case is a validator somebody has to read
  before trusting, and the whole point of this file is that a reviewer should not have to.
- **Evidence:** my own first attempt at the file. The `entity_limits` block was the one place I
  wrote bare values with no provenance at all — seven reasonable-looking numbers that a
  block-level-provenance loader might well have waved through.
- **Cost:** the file is about three times longer than it needs to be.
- **Outcome:** accepted. Revisit if a block ever appears where repeating the source would be
  actively misleading.

## #008: Three states for a threshold, not two, 2 Nov 2026
- **Decision:** a threshold is `verified` (a date), `assumed` (`verified: null` with a source
  beginning "ASSUMPTION"), or `unverified` (listed in `meta.unverified`, value null, and the
  loader refuses to evaluate it).
- **Why:** two states were not enough. `single_stock.mwpl.reset_calendar` is a guess — the
  circular names no reset months — but the engine cannot compute any MWPL at all without it, so
  listing it as unverified would stop the engine dead. The penalty rate is the opposite: unknown
  and genuinely unusable, so the engine must refuse rather than guess. Collapsing those two into
  one state means either the engine stops working or a guess gets treated as a citation.
- **How `assumed` stays honest:** the source must literally begin with "ASSUMPTION", so the
  state can never be reached by forgetting to fill in a date, and `load_rules()` emits one
  warning per run naming every assumed threshold. Tests run with `-W error::UserWarning`, so a
  new assumption fails the suite until somebody acknowledges it.
- **Outcome:** accepted. Implemented in `src/sentinel/rules.py`, 34 tests in
  `tests/test_rules_loader.py`.

## #009: The engine reads thresholds only through the loader, 2 Nov 2026
- **Decision:** no module imports `yaml` to read `config/rules.yaml`. Everything goes through
  `sentinel.rules.load_rules()`, and comparison directions come from `Threshold.compare()`
  rather than from `if` statements in the rule functions.
- **Why:** the two ban boundaries are inclusive in opposite directions — entry "exceeds 95%",
  exit "80% or below". Written as `>` and `<=` in two different functions, that asymmetry has to
  be remembered correctly by whoever writes the second one. Held in the config and applied by
  one method, it is checked once, by a test, against the wording of each circular.
- **Evidence:** 2 Nov. My first draft of the config put the operator inside the value as the
  string `">0.15"`, which would have compared as a string and never raised.
- **Outcome:** accepted. `Threshold` is frozen, so the engine cannot adjust a limit it was handed.
