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

## #010: NSE blocks plain HTTP clients, so acquisition is deferred, 2 Nov 2026
- **Finding:** NSE's daily report files are public in a browser but cannot be fetched by a plain
  HTTP client. Two distinct mechanisms, measured on 2 Nov:
  - `https://www.nseindia.com/` returns **403 in 0.12s** to curl with an honest user-agent.
  - Archive file paths under `nsearchives.nseindia.com` are **tarpitted**: the connection is
    accepted, zero bytes are sent, and it is never closed. Nine consecutive requests each burned
    their full timeout at 0 bytes.
  - Control, same machine and same second: `https://www.sebi.gov.in/` returned **200 in 0.27s**.
    So this is NSE policy, not a network fault.
- **This corrects an earlier reading.** `TASKS.md` recorded a 120-second zero-byte stall on
  31 Oct as an intermittent fault, to be handled with timeouts and backoff. It was not
  intermittent. It is the tarpit. A downloader built on the retry assumption would have failed
  every night and looked like a bug in my own code.
- **What I did not do:** a probe that sent a spoofed Chrome user-agent was written and then
  discarded. It was blocked by the permission layer and it also breaks the "clear user-agent"
  rule in `CLAUDE.md`. Fetching through the browser pane was also tried and fails on CORS:
  `nsearchives` is a different origin and sends no cross-origin headers.
- **Decision:** download manually for now. The automation decision moves to Week 2 D1.
- **Why defer rather than solve:** D6 needs parsers, and parsers need files on disk, not a
  scheduler. Choosing how to acquire data before knowing what the data contains is the wrong
  order - and it was the right call, because the files turned out to contain NSE's own
  next-day headroom and per-contract deltas, which changes what is worth automating.
- **Options for Week 2 D1:** drive a real browser engine (Playwright runs actual Chromium, which
  is what NSE is checking for, with no spoofing); or keep manual downloads and automate only the
  parsing. Not yet decided.
- **Outcome:** accepted. Five files downloaded by hand on 2 Nov; checksums and column maps in
  `docs/READING.md`.

## #010 addendum: automated acquisition ruled out, 10 Nov 2026

**What.** NSE files stay manually downloaded unless NSE gives written
permission. v1.0 adds an **importer**, not a downloader: I download each
file by hand into `data/`; the importer checks its heading date and
checksum, records provenance, and reports which files for day D are
still missing. The runner does not change.

NSE content is also kept out of the public repository: fixtures built
from NSE rows are replaced by checksums plus builder scripts, and CI
runs on small synthetic fixtures written by hand.

**Why.** The original #010 reasons were technical: NSE blocks scripted
requests. Re-reading NSE's terms of use shows the stronger reason is
contractual: automated collection is prohibited outright, with no
route to consent. Any workaround, including driving a real browser,
would still be automated collection, and would also defeat the block
NSE uses to enforce its terms.

**Evidence.**
- **Terms of use, para 9** (nseindia.com/static/nse-terms-of-use,
  read 10 Nov 2026): prohibits "systematic or automated data
  collection activities (including scraping". Other NSE sites' terms
  (the investor helpline and the NSE Data portal) allow automated
  access with written consent; the main site's terms offer no consent
  route.
- **Terms of use, para 8:** NSE content may not be reproduced, uploaded
  or posted without prior written permission. This affects publishing
  NSE rows in `tests/fixtures/`. Para 8 also bars use of NSE data for
  "gaming, virtual trading or simulation activities".
- **Para 8 also covers storage:** content shall not be "stored (either
  in hardcopy or in an electronic retrieval system)". Its next sentence
  begins "Unless the information or Content is available for download".
  The files used here are offered by NSE for download, which is what
  keeping local copies in `data/` and the store relies on. Those copies
  stay local and are never published.
- **Technical:** www.nseindia.com returns 403 to an honest user-agent;
  archive URLs accept a connection and send nothing (tarpitted).
  Retries against a tarpit would only fail slowly every night.
- **robots.txt allows `/`.** That is a convention for crawlers; the
  terms of use are the contract, and they prohibit automated collection.
- **Not tested:** no scripted request was made against the archive to
  check the terms, because running the test would itself break para 9.

**Consequences.**
1. v1.0 acquisition: manual download plus importer.
2. Retries are dropped entirely (#019 item 12): there is no downloader
   to retry.
3. The year-long replay is limited by how many files I download by
   hand. Scope decided Thursday.
4. Before the repo goes public, NSE content leaves the fixtures and the
   git history: the combineoi rows (three files) and the 22 fo_secban
   copies. The SEBI Table 2 book, the hand-made empty ban list and the
   illustrative hand calculations stay. Published as a fresh public
   repository built from filtered history; this repository stays private
   as the full record.
5. The README describes the prop book as a test harness with synthetic
   positions for checking compliance logic, not a trading or
   simulation system. My reading is that para 8's simulation wording
   targets paper-trading games, but the description should leave no
   doubt.
6. Optional: written permission can be requested from
   nsewebmaster@nse.co.in. Nothing depends on the answer.

**Not legal advice.** These are my reading of NSE's published terms
for a portfolio project; a commercial use would need a licence through
NSE's data vendor.

**Outcome.** Accepted, 10 Nov 2026. v0.1 tagged privately; published
once the fixtures are replaced and the filtered history is verified.

## #011: Ban state between days, 2 to 4 Nov 2026
<!-- Authorship, recorded for the same reason it is recorded in SPEC.md and rules.yaml.
     The reasoning in all four answers is mine, worked out against the data on 2 and 4 Nov.
     Claude transcribed it, and in three places did more than transcribe:
       - Q2: supplied the index answer, which I had not attempted, and corrected a factual
         error about which files carry an ISIN - an error Claude had itself introduced in
         this file's own prompt text, which I then repeated.
       - Q3: my first answer carried a warm-up replay over from my VaR engine, where it is
         correct. Claude showed with a 19-of-20 counterexample why it is impossible here.
       - Q4: my first answer was scoped to blocking orders, which this engine never sees.
         Claude remapped it to a monitoring system; the three arguments are unchanged.
     Claude also wrote the Decision paragraph as a synthesis of the four answers.
     The pattern in Q3 and Q4 is the same and is worth naming: sound reasoning aimed at
     the wrong system. The repayment is at the bottom. -->

- **1. The signature of `is_in_ban()`:**

  ```python
  def is_in_ban(futeq_oi, mwpl, was_in_ban_yesterday) -> bool:
  ```

  Three arguments, because two are provably insufficient. On 30 Oct, SAIL sat at 84.93%
  utilisation and was banned while BANDHANBNK sat at 85.98% and traded freely. A function
  given only `(futeq_oi, mwpl)` receives near-identical inputs for those two rows and must
  return opposite answers, which no implementation can do. The missing input is not extra
  information for its own sake: it is the thing that **selects which threshold applies.**
  A scrip already in ban is measured against the 80% exit; one still free is measured
  against the 95% entry. One utilisation, two thresholds, and nothing in the first two
  arguments says which to use.

  The return is `bool` because tonight's output becomes tomorrow's `was_in_ban_yesterday`.
  Output type must equal input type, which means this is not a predicate at all - it is a
  state transition, and the function is one step of a state machine.

  **Known limitation, deliberately not solved yet.** A bare `bool` discards the reason. A
  scrip banned tonight for the first time and a scrip still banned and holding above 80%
  both return `True`, and the alert text for those is not the same sentence. Revisit when
  the alerting work starts in Week 4.

  **Rejected:** `(futeq_oi, mwpl, yesterday_utilisation)` - a number is not a state. SAIL's
  utilisation yesterday was also in the eighties, as was BANDHANBNK's, so the ambiguity
  survives one day older, and resolving it needs the day before that. There is no bottom.

  **Rejected:** `(futeq_oi, mwpl, threshold)` - this does not solve the problem, it relocates
  it. Choosing between 0.95 and 0.80 requires knowing whether the scrip is in ban, which is
  the question the function exists to answer. The caller would need the answer to ask.

- **2. What the state is keyed on:**

  **Key on ISIN, never on symbol. Store the symbol alongside as a check.**

  The symbol is the field that gets renamed (ZOMATO to ETERNAL) and reused (a freed ticker
  later assigned to a different company). Those are two different bugs. A rename silently
  cold-starts the model for that scrip; a reuse silently hands one company's risk history to
  another. Neither raises an error, and both produce wrong alerts that look right. The ISIN
  is not reused, so it is the safe key.

  Every alert, report and conversation uses the symbol, so the record carries both fields.
  Keying and displaying are different decisions, and conflating them is why people end up
  keying on the readable field.

  **How the seed resolves, which is where this gets awkward.** `fo_secban` is the only file
  that can seed day one, and it carries **no ISIN** - 62 bytes, symbols only, not even a
  header row. So symbol-to-ISIN must be resolved through the same day's `combineoi`, which
  carries both. The consequence is a real constraint on question 3: **the ban-state store
  cannot be seeded from the ban list alone.** It needs the ban list and a `combineoi` for a
  date close enough to resolve every symbol in it.

  If a symbol in the ban list does not resolve, **raise and stop the run.** Do not skip the
  row. A banned scrip that cannot be identified is the worst thing to drop silently, because
  it under-reports a real ban, and that is the error direction that gets a desk fined. Same
  discipline as `src/sentinel/rules.py` refusing on `penalty_rate`: when the engine does not
  know, it says so loudly.

  **The nine indices are refused, not stored.** NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY,
  NIFTYNXT50, SENSEX, BANKEX, NIFTYFPI and FOCIT all carry `ISIN = NA` in
  `combineoi_deleq`, and they are absent from `combineoi` altogether. That absence is not an
  oversight in the file: MWPL does not apply to indices, which are governed instead by the
  index position limits of `SPEC.md` row 13. A store keyed on ISIN cannot hold a row with no
  ISIN, and a store that accepts rows it cannot key will one day return the wrong one. So
  this store rejects them. The corollary is worth stating plainly, because it will look like
  a missing feature in Week 4: **there is no such thing as ban state for an index.** Ban
  periods are a single-stock mechanism.

  **One open claim, marked `unverified`.** A security may be issued a new ISIN after a
  corporate action, in which case state has to be carried across the old-to-new mapping
  deliberately or it cold-starts anyway. I believe face-value splits can do this; I have not
  checked, and the counter-recollection is that Indian splits usually retain the ISIN while
  new ISINs come from partly-paid conversions and demergers. **What would settle it:** an NSE
  circular on ISIN assignment for corporate actions. Until then this is a flagged risk, not a
  design input, held to the same standard as every threshold in `config/rules.yaml`.

  **The date-effective symbol-to-ISIN table is buildable from files already downloaded.**
  `combineoi` gives ISIN and NSE Symbol per day, so accumulating it daily produces the
  mapping with effective dates for free. No new data source is needed.

- **3. Day one, and after a gap:**

  **Day one seeds from `fo_secban`. There is no warm-up that can replace it.**

  My first attempt at this answer said the opposite - start from a fixed date with enough
  history and replay forward, no special seed step - which I had carried over from my VaR
  engine, where it is correct. It is impossible here, and the reason is the most useful thing
  I learned today.

  A GARCH variance seeded wrongly **decays** toward the truth. Feed it correct returns and a
  10x initial error falls monotonically - 9.45x, 5.85x, 2.80x over twenty days, half-life
  about 6.6 days at beta 0.90 - with no intervention. That is what makes a warm-up window
  legitimate there.

  A ban flag seeded wrongly **latches**. Running the same utilisation path from both seeds,
  the two runs disagreed on **19 of 20 days**. They agreed only on the last day, and not
  because the system corrected itself: utilisation happened to fall below the 80% exit, which
  forces both runs to the same answer regardless of where they started. The state was not
  repaired, it was overwritten by an unrelated event. Had utilisation stayed in the eighties
  all month, the two runs would still disagree and nothing in the data could say which was
  right.

  The reason there is no restoring force: 0.95 and 0.80 form a deadband, and inside it the
  flag depends only on itself - `util > EXIT if was_in_ban else util > ENTRY`. Each day's
  answer is yesterday's answer propagated. It is a memory cell, not an estimator. Estimators
  forget their initial conditions; memory cells are built not to.

  **The test that tells the two apart,** worth keeping for any carried state I design later:
  run the same inputs from two different initial states. If they converge, the state decays
  and a warm-up is legitimate. If they diverge, the state latches and it must be seeded from
  an observation.

  So the only ground truth about ban state is NSE publishing it. Day one reads `fo_secban`,
  and - per question 2 - also needs a `combineoi` close enough in date to resolve those
  symbols to ISINs.

  **After a gap: Wednesday resumes by computing, not by re-seeding.** It sees Tuesday's state
  is missing, recomputes Tuesday from Tuesday's data, then runs Wednesday. Replay works
  *between* seeds; it cannot replace one. Re-seed only if Tuesday's input data is genuinely
  lost, and even then replay from the last good checkpoint.

  **The deciding detail: key state by date, and check that the state loaded is from the
  previous trading day.** If Wednesday simply loads the "latest" state, it uses Monday's state
  as if it were Tuesday's. That silently corrupts every day after it, because a wrong ban flag
  never decays. With the date check and the catch-up, one bad night only loses a day.

  The word *trading* is doing real work there. `progress.md` has the holiday table: 8 Nov 2026
  is a Sunday **with** Muhurat trading, and 10 Nov is a holiday. A naive previous-calendar-day
  check would reject the valid Sunday file and silently accept the gap across the holiday,
  which are the two opposite failures in one rule.

  **Falls out of this, and is question 4:** if no trustworthy seed can be established, the
  honest thing is to refuse rather than guess.

- **4. When state is unavailable:**

  **Refuse, scoped narrowly: refuse to emit a verdict for that one scrip, and complete the
  run for the other 217.** Per-scrip refusal, never per-run. The report carries 217 verdicts
  and one explicit `UNKNOWN - ban state unavailable` row with the reason attached, worded so
  it cannot be read as "compliant". The refusal is logged loudly enough that someone fixes
  the feed.

  My first draft of this answer scoped the refusal to blocking new or position-increasing
  orders. That is a pre-trade risk control, and this engine is not one - it runs every evening
  on published files and never sees an order. `docs/research_report.md` makes the point in the
  other direction: OMS and RMS vendors sit in the pre-trade order path, and the gap this
  project fills is that nobody replays these calculations afterwards. The structure of the
  answer survived the remap unchanged; only the mechanism moved.

  **Why "assume not-banned" is the dangerous one.** It fails open. If the scrip really is in
  the ban period, the engine reports a clean book while the desk is accruing a penalty under
  para 5.3.2, and the error stays silent until the exchange raises it. That is the error
  direction that costs money, and it is also the one direction a monitoring system must never
  take by default.

  **Why "assume last-known" sounds safer and is not.** Ban status changes on exactly the days
  that matter. A scrip enters when FutEq OI crosses 95% of MWPL and exits when it comes down
  to 80% or below, so yesterday's status is wrong *precisely on the transition day* - which
  is the day the penalty lands and the only day the system has any reason to exist. Carrying
  state forward is harmless on the 99% of days when nothing changes, and the days it is wrong
  are not randomly distributed: they are concentrated entirely on the transitions. An
  estimator that is accurate except when it matters is worth nothing.

  **Why refusing costs less than it sounds.** Reducing a position is permitted during a ban,
  so the safe advice under *unknown* state is identical to the safe advice under *known
  banned*: reduce only. The engine can therefore say something useful about that scrip
  without knowing its state, which is why refusing one row out of 218 is cheap. The run still
  completes, the other 217 verdicts are unaffected, and the operator at 18:40 gets a full
  report with one flagged row rather than no report at all.

  **Does the `penalty_rate` discipline apply?** Yes - `Rules.get()` raises
  `UnverifiedRuleError` rather than returning a plausible number, and this is the same call.
  But the analogy carries less weight than I first gave it: there is no last-known penalty
  rate to fall back on, because SEBI never published one and delegated the rate to the
  exchange. That is an *absent* value, not a stale one. So `penalty_rate` tests only the cost
  axis of the rule below. Ban state tests both axes.

  **The rule that decides it, kept for reuse:** how fast does the missing value change, and
  what does being wrong in the unsafe direction cost? Slow-changing with a modest cost means
  last-known is acceptable. Fast-changing with an exchange-penalty cost means refuse. Ban
  state is a daily flag whose entire purpose is to change, with a penalty attached - so it
  refuses.

- **Decision:** `is_in_ban(futeq_oi, mwpl, was_in_ban_yesterday) -> bool` is a state
  transition, not a predicate, so the engine carries ban state between days. State is stored
  per trading date, keyed on ISIN with the symbol held alongside as a check, and index rows
  are rejected because they have no ISIN and no MWPL. Day one is seeded from `fo_secban`
  together with a `combineoi` close enough in date to resolve its symbols to ISINs; no
  warm-up or replay can substitute for that seed, because a wrongly seeded ban flag never
  decays. Each run loads the state for the previous **trading** day, recomputing any missing
  intermediate day from its own files before proceeding, and re-seeding only when input data
  is genuinely lost. Where state for a scrip cannot be established, the engine refuses to
  emit a verdict for that scrip alone, marks the row `UNKNOWN` with its reason, logs loudly,
  and completes the run for every other scrip.

- **Why:** two numbers cannot answer the question. On 30 Oct SAIL was banned at 84.93%
  utilisation while BANDHANBNK traded freely at 85.98%, so the function needs the prior state
  to know which of the two thresholds applies. Everything else above follows from that one
  fact: if state is carried, it has to be keyed on something stable, seeded from an
  observation, matched to the right previous day, and refused rather than guessed when
  missing.
- **Evidence:** 30 Oct 2026, `data/extracted/combineoi_30102026/combineoi_30102026.csv`,
  218 securities. SAIL flagged `No Fresh Positions` at 84.93% FutEq utilisation; BANDHANBNK
  trading freely at 85.98%. Neither anywhere near 95%. Of 218 rows, 7 sit in the ambiguous
  80-95% band, 2 of them banned and 5 free. No row at all exceeds 95%, so the entry rule has
  **zero test cases** in this file - a test asserting it would have passed vacuously.
  Separately, a wrongly seeded flag run against the same utilisation path as a correctly
  seeded one disagreed on 19 of 20 days, and agreed on the twentieth only because utilisation
  fell below the 80% exit and overwrote both.
- **Alternatives rejected:** the two insufficient signatures (recorded under Q1); keying on
  symbol (Q2); a warm-up replay in place of a seed (Q3); failing open or carrying last-known
  state (Q4). Also rejected: refusing the whole run when one scrip's state is missing, which
  would turn one bad row into no report.
- **Outcome:** accepted, 4 Nov 2026. Nothing implemented yet. `SPEC.md` rows 4 and 5 need
  their `is_in_ban()` signature updated to three arguments, and `PLAN.md` W2 needs the state
  store added to the runner's design.

- **Repayment, owed next session.** All four answers above were reached in conversation with
  Claude rather than written cold, and Claude wrote the Decision paragraph as a synthesis of
  them. Before anything else next session, re-derive Q1 to Q4 into a blank file from memory
  and diff against this entry.
  - Q1: reproduce the signature, and say why two arguments cannot work.
  - Q2: answer "why not just use the ticker?" in two sentences without looking.
  - Q3: state the test that distinguishes a latching state from a decaying one, and say which
    of my two projects each one is.
  - Q4: state the rule that decides between refusing and falling back to last-known, and say
    why ban status fails it.
  - Then write the Decision paragraph again myself, from the four answers, without reading
    Claude's version first.

## #012: The point-in-time ban-state store, 6 Nov 2026
<!-- Authorship. The four decisions below are mine, worked out on 6 Nov after Claude walked
     the shape of `is_in_ban()` and before the store existed. Claude transcribed them,
     quantified two against the real file, and in two places did more than transcribe:
       - it pointed out that my "re-seed from NSE's ban list" contradicts my own #011 Q2,
         where I had already established that `fo_secban` carries no ISIN and cannot seed
         anything on its own;
       - it showed that my 218-of-218 score is circular under the likely reading of the
         source column, which is the open question at the end of this entry.
     Decisions 1 and 2 of my original answer are not here: they were already settled in #011
     and this entry cites them rather than restating them. -->

#011 settled the function and what carrying state means. This entry is about the store that
holds it: what a record is, what happens when an input is missing, and what feeds forward.
Everything in #011's Decision paragraph still stands - the `(ISIN, trade_date)` key, the symbol
held alongside as a label, the previous **trading** day rather than the previous calendar day,
refusing per scrip rather than per run, and the seed needing `fo_secban` plus a `combineoi`
close enough to resolve its symbols.

- **1. State only matters inside the dead zone, so a missing previous day blocks seven scrips
  and not two hundred and eighteen.**

  #011 says to refuse a scrip whose state cannot be established. That is right but broader
  than it needs to be, because for most scrips the state is irrelevant to the answer. Above
  the 95% entry the scrip is banned whatever yesterday was; at or below the 80% exit it is
  free whatever yesterday was. Only inside the band - just above 80%, up to and including 95%,
  since entry is strict - does the third argument decide anything at all.

  So a missing previous day is not a lost day. Answer every scrip outside the band normally,
  refuse only the ones inside it, and name them. On 30 Oct that is **7 of 218**: KAYNES
  92.17%, BANDHANBNK 85.98%, MANAPPURAM 85.67%, SAIL 84.93%, LICHSGFIN 84.37%, INOXWIND
  84.32%, AMBUJACEM 81.82%. Two of the seven were banned and five were free, which is the
  point: nothing in the measurement separates them.

  This is the same discipline as `rules.py` refusing on `penalty_rate` - the engine declines
  exactly where it does not know, and nowhere else. The cost of over-refusing is a report
  nobody can use; the cost of under-refusing is a guess in the one region where a guess is
  undetectable.

- **2. Two fields per record. The engine's own output never feeds back into the engine.**

  Each record carries both:

  - **`forecast`** - what the engine computed. Scored against NSE, never read as input.
  - **`official`** - NSE's published ban list for that date. This is the only thing the next
    day reads as `was_in_ban_yesterday`.

  The reason is the latch. A wrong ban flag does not decay toward the truth the way a wrongly
  seeded GARCH variance does; it stays wrong every day until utilisation leaves the band. Run
  the same flat utilisation path at SAIL's 84.93% from both seeds and they agree on **0 of 20
  days**. So if the engine's forecast fed forward, one bad night would corrupt an open-ended
  run of nights, and the run would look entirely self-consistent.

  Feeding the observation forward instead bounds the damage: an engine error costs exactly one
  scored miss. It also makes the score meaningful, because forecast and input are then
  independent - the engine is predicting something it was not told.

  **Rejected:** feed `forecast` forward and reconcile against NSE periodically. This is the
  design that latches. Between reconciliations there is no bound on how long a wrong flag
  persists, and inside the band there is no measurement that would reveal it.

  **Rejected:** store only `official` and compute the forecast on the fly for the report. It
  would work, and it throws away the scoring history - which is the project's own claim, and
  the only evidence that my reading of the rule is right rather than merely consistent.

- **3. A day with no published ban list is reported `unscored`, never `agreed`.**

  #011's missing-file rule was written for the MWPL file. The ban list is the other input and
  its absence breaks something different: `official` is the only thing that feeds forward, so
  a missing list leaves the next day with no state to read and leaves the current day with
  nothing to score against.

  The rule: the day's `official` is **unknown** and is never filled in from `forecast`, since
  that is exactly the feedback this design exists to prevent. Scrips outside the dead zone are
  still answered. Scrips inside it are refused until `official` is recovered - either the list
  arrives late, or the state is re-seeded from a later published list **together with a
  `combineoi` for a date close enough to resolve its symbols to ISINs**, per #011 Q2, as a
  logged step. The day is reported `unscored`.

  Counting it as `agreed` would be the dangerous failure. With a base rate of 2 bans in 218
  securities, a handful of silently-agreed empty days would lift the headline agreement rate
  without anyone noticing, which is the kind of number that reads as success.

- **4. Every record carries its provenance and the hash of the file it came from.**

  A `source` of `seed`, `computed` or `nse`, plus the hash of the input file. Three values
  rather than two for the same reason `rules.yaml` has three threshold states: "where did this
  come from" has more than two answers, and collapsing them loses the one that matters. A
  `seed` record is an assertion from an observation, a `computed` record is the engine's own
  work, and an `nse` record is published fact. They are not interchangeable and a reader at
  18:40 needs to know which one they are looking at.

  The hash is what makes any day traceable back to the bytes it was derived from, and it is
  the same manifest the file watcher needs, so it is written once and used twice.

- **5. The `combineoi` flag is a T+1 declaration. Settled 6 Nov, and it never mattered.**

  Does `is_in_ban()` computed from day T's file answer "banned on T" or "banned on T+1"? When I
  wrote this entry the answer was unknown and I recorded it as unknown. It is now known.

  With seven `combineoi` files and fifteen ban lists, the flag can be compared against both
  candidate dates on the days when those dates differ. It matches T+1 on all seven days, and on
  **five** of them T and T+1 differ, so those five discriminate. The two that match both are days
  with no change - which is why 30 Oct alone could never settle it, and why the three identical
  sets I first reasoned from were non-identifying.

  So the `No Fresh Positions` sentence in day T's file is NSE's ban declaration for T+1.

  **Two consequences.** The useful one: the engine's output and NSE's flag are about the same
  date, so a disagreement is a real disagreement rather than an off-by-one, and the reconciliation
  in `engine.py` compares like with like.

  The deflating one: **the answer is in the same file as the inputs.** NSE publishes the T+1 ban
  determination in the very file whose numbers the engine computes from. There is no time
  advantage of any size, so what this engine does is reproduce NSE's determination independently,
  not forecast something unpublished. The honest word is reconciliation. That is also the job
  description, so it is a narrowing of the claim rather than a loss.

  **It never mattered for the score**, which is the part worth keeping. `was_in_ban_yesterday` is
  read from the previous day's published ban list, never from this flag, so the ambiguity was
  quarantined from the forecast the whole time. Had the seed come from the flag, the agreement
  would have been circular: both banned scrips on 30 Oct sat inside the dead zone, where the
  forecast is the seed.

  `docs/READING.md` asserted T+1 on 2 Nov from the non-identifying coincidence, and I corrected it
  to "unresolved" on 6 Nov before the evidence arrived. Both the claim and the retraction are now
  superseded by the table above. The lesson is not about this flag: a conclusion can be right while
  the reasoning for it is worthless, and only the reasoning tells you whether to trust the next one.

- **Decision:** the ban-state store holds one record per `(ISIN, trade_date)` carrying both
  the engine's `forecast` and NSE's `official` state, where only `official` is ever read
  forward as `was_in_ban_yesterday`. A missing previous state refuses only the scrips inside
  the 80-95% band, because outside it the state cannot change the answer. A day with no
  published ban list is `unscored`, its `official` left unknown rather than filled from the
  forecast, and recovery is an explicit logged re-seed from a later ban list together with a
  `combineoi` that resolves its symbols. Every record names its source as `seed`, `computed`
  or `nse` and carries the hash of the file behind it.

- **Why:** a wrongly seeded ban flag latches instead of decaying, so the single most important
  property of this store is that nothing the engine computes is ever read back as an input.
  Everything else follows: if the observation feeds forward, the observation has to be present
  or the day has to say so; if the forecast is kept but never consumed, it can be scored; and
  if the two are stored side by side, a reader has to be told which is which.

- **Evidence:** 30 Oct 2026, `combineoi_30102026`, 218 securities. 7 rows sit in the 80-95%
  band - 2 banned, 5 free - and no row exceeds 95%, so 211 of 218 scrips can be answered with
  no stored state at all. A flat utilisation path at SAIL's 84.93% replayed from both seeds
  agrees on **0 of 20 days**; #011's 19-of-20 agreed on the twentieth only because that path
  eventually fell below the exit.   Forecasting 2 Nov from the 30 Oct file, seeded from the 30 Oct
  **ban list** rather than that file's own flag, reproduces NSE's published list exactly: 218
  of 218 scrips agree, 2 true positives and 216 true negatives, no false positive and no false
  negative, with both ban-list symbols resolving to ISINs on first use. The same forecast
  seeded from the `combineoi` flag gives the same number and means nothing, because both banned
  scrips sit inside the dead zone where the forecast is the seed. **What the 218 does not
  contain: a single transition.** Entry fired 0 times and exit fired 0 times, so only the
  "held in ban" branch was exercised and 216 of the answers are "nothing happened" on a day
  whose highest free utilisation was 85.98%. The entry and exit thresholds still have no real
  test case.

- **Alternatives rejected:** feeding the forecast forward and reconciling periodically, which
  is the latching design; storing only `official` and recomputing the forecast for the report,
  which discards the scoring history that is the project's own claim; refusing the whole day
  when a previous state is missing, which throws away 211 good answers to protect 7; and
  filling a missing `official` from the forecast, which is the feedback loop wearing a
  different hat.

- **Outcome:** accepted, 6 Nov 2026, all five decisions closed, decision 5 answered the same day
  it was raised. The store itself is still not implemented - what is implemented is the function
  it will feed, and the scoring that proves the function reproduces NSE's determination. The forecast is scored and non-circular, but it has exercised one of three branches, so
  the hunt was done the same day: `fo_secban` for consecutive trading days, diffed
  to find where a symbol appeared or disappeared, then `combineoi` for the day before each change
  - 62-byte files locating the 22 KB ones. Seven transitions in three weeks, three entries and
  four releases.

  **Scored the same evening: 1502 of 1502 scrip-days agree with NSE's published lists across
  seven measurement days, zero false positives and zero false negatives, and all seven
  transitions forecast correctly.** Entries at 97.98%, 95.67% and 95.01%; releases at 79.41%,
  78.82%, 70.02% and 66.96%. Every branch of `is_in_ban()` has now fired on real data. SAIL
  entered on 29,360 shares past the 95% line on an MWPL of 217 million, which is the case that
  earns para 5.2.6's "exceeds" and the strict `>` in the config.

  The honest reading of that number: 1,495 of the 1502 are a scrip nowhere near a threshold
  staying there, so 1502 measures false alarms and **seven** measures the logic. Untested still:
  either exact boundary (no row has sat on 95.00% or 80.00%), a missing prior state, and a newly
  listed scrip near a threshold - the universe moved 213 to 219 to 218 inside the sample, so new
  scrips did appear.
  Also outstanding from #011's own Outcome and still not done:
  `SPEC.md` rows 4 and 5 still carry a three-argument `is_in_ban()` with no `rules`, and
  `PLAN.md` W2 still has no state store in the runner's design.

## #013: The trading calendar, and the fourth state, 7 Nov 2026
<!-- Authorship. The four-state decision and the reasoning for it are mine, made on 7 Nov
     before the calendar existed. Claude implemented it, found the next-trading-day bug that
     made the calendar necessary in the first place, compared the two holiday lists, and wrote
     this entry from my answer. The clearing-holiday question was mine to notice: I pasted
     that second list because the download was not available, which is the only reason the
     difference came to light. -->

`#012` said the engine loads the state for the previous **trading** day. It did not say where
the calendar comes from, and that turned out to matter more than the store itself.

- **1. The calendar exists because of a bug, not a plan.**

  `scripts/score_bans.py` took "the next trading day" to mean "the next date for which a file
  happens to be on disk". Hiding one ban list made it score 14 Oct's forecast against 16 Oct's
  published answer, skip the 15th entirely, report **1502 of 1502 with zero errors**, and exit
  0. A missing file silently re-dated the answer and the result still looked perfect.

  I had the problem the wrong way round when I set the task: I thought the calendar was for
  resolving the previous trading day, and the live bug was in the next one.

- **2. A date has four states.**

      TRADING          a session happened, verified against NSE's published calendar
      SPECIAL_SESSION  a session happened on a day that is not a normal trading day
      HOLIDAY          no session, verified the same way
      UNKNOWN          no verified calendar covers this date

  The first three and `UNKNOWN` are the same move as the three threshold states in `rules.py`
  and the three `source` values in `#012`: "I do not know" gets its own state rather than being
  forced into one of the others. `UNKNOWN` cannot be written down, only inferred from absence -
  a recorded `UNKNOWN` would make an unverified date look verified.

  An empty calendar knows nothing and says so. It does not default to "weekdays are trading
  days", which is the same inference wearing a better coat.

- **3. `SPECIAL_SESSION` is a state, not a flag on `TRADING`.**

  This is the decision I was asked for and it is the one worth defending. The open question
  about Muhurat trading is **not** whether there is data on 8 Nov 2026 - there will be. It is
  whether that session counts as the previous trading day for 9 Nov's ban state. I do not know
  yet. A flag on a trading day would quietly answer "yes" by default. A fourth state forces the
  store to treat it explicitly: accept its files, decide separately how it chains, and refuse
  until that is verified.

  So `has_session()` is true for it and its data is stored, while `next_trading_day()` and
  `previous_trading_day()` raise `ChainUnverifiedError` on it - a different exception from
  `UnknownDateError`, because the date is not unknown. The calendar knows exactly what it is;
  what is unknown is its place in the chain.

  The consequence is concrete and lands in two days: **Monday 9 Nov's run will refuse to seed**
  until the chaining is settled. That is fail-closed, which is the point. After Sunday's
  session, check whether NSE's next published ban list carries 8 Nov's state forward, record the
  answer here, and pass the date in `chaining_verified`.

  NSE's own wording is why caution is right rather than fussy. Circular NSE/FAOP/71777 lists
  8 Nov as a Sunday holiday and says in the same breath that "Muhurat Trading will be conducted
  on Sunday, November 08, 2026", with timings "notified subsequently" - the exchange had not
  settled the session's shape when it published the calendar.

- **4. The calendar is reference data, not typed configuration.**

  A hand-typed date list cannot be verified, and one typo becomes a silent stale seed - which
  is the error this whole module exists to prevent. So it is generated from NSE's own published
  circular, whose checksum is recorded in `docs/READING.md`, and `config/calendar_2026.csv`
  carries **one source string per row**, the same per-key provenance as `config/rules.yaml`
  (#007). A row with no source is refused at load time.

  The file lists only the exceptions. Every other weekday in the covered year is a trading day,
  and **that complement is a deduction rather than a guess**: the circular says "the Exchange
  hereby notifies trading holidays for the calendar year 2026 as below", which is exhaustive for
  that year. It holds only inside the stated year, which is why a `year_covered` row is required
  and a calendar without one is refused - without a boundary, 2030 would silently look like
  trading days. Weekends are holidays by rule rather than by the circular, which lists only the
  weekend dates carrying a named holiday; the Muhurat Sunday is exactly why the file has to be
  able to override that rule.

- **5. Clearing holidays are a finding, not a dimension. Tested, n=1.**

  NSE publishes a separate clearing-holiday list, and it is a **superset** of the trading
  holidays: every trading holiday appears in it, plus five more in 2026 - 15 Jan (Municipal
  Corporation Election), 19 Feb (Chhatrapati Shivaji Maharaj Jayanti), 19 Mar (Gudhi Padwa),
  1 Apr (Annual Bank Closing) and 26 Aug (Id-E-Milad). On those five dates the market trades
  and the clearing corporation is shut.

  That looked load-bearing, because `combineoi` is served from the clearing corporation's own
  archive path, `/archives/nsccl/mwpl/`. If the MWPL file were not published on a clearing
  holiday, those five dates would be a trading day with no measurement file - which `#012`'s
  four-case matrix reads as "missing file, state unknown, refuse the dead zone". A false alarm:
  the file would never have been published rather than lost.

  All five dates had passed, so one download settled it. `combineoi_26082026.zip` exists, parses,
  and carries 211 rows for 26 Aug 2026 - a clearing holiday that was a trading day. So the
  calendar needs one axis, not two.

  **This rests on one observation of five dates, and on one of the two files.** A systematic
  non-publication would have shown up here, which is why I am willing to act on it, but it is
  n=1 and the entry says so rather than stating a rule. The ban list half is untested; the
  reason I expect it to hold is that `fo_secban` is served from `/archives/fo/sec_ban/` - the
  F&O segment, not the clearing corporation - and the segment was open that day. That is
  reasoning, not a file.

- **6. Twenty October closes.**

  On 6 Nov the date was `UNKNOWN`: no ban list, and I had wrongly concluded from a 404 that it
  was a holiday and written that into `docs/READING.md` and a commit. The circular settles it -
  item 12, Dussehra - so the walk across it is now a deduction from a primary source rather than
  an inference from a failed download. The two situations are worth keeping side by side: I had
  a belief and acted on it; Chintamani had a belief about the same date and refused to let the
  engine act on it until the file was in the repo.

- **Decision:** the trading calendar is loaded from `config/calendar_2026.csv`, generated from
  NSE circular NSE/FAOP/71777 with its checksum recorded, carrying one source per row and a
  required `year_covered` boundary. A date has four states, with `SPECIAL_SESSION` separate from
  `TRADING` so that a special session's data is accepted while chaining through it refuses until
  verified. Clearing holidays are recorded as a finding and not modelled. `score_bans.py` asks
  the calendar and no longer infers; where the next trading day's ban list is absent it reports
  the day as unscored rather than scoring against a later list.

- **Why:** the engine's answer is dated, so every operation that moves between dates has to be
  a fact rather than a guess. Inferring the calendar from which files exist makes a missing file
  indistinguishable from a holiday, and that difference decides which day's published answer a
  forecast is scored against.

- **Evidence:** hiding `fo_secban_15102026.csv` made the old script score 14 Oct against 16 Oct
  and still report 1502 of 1502 with exit 0. With the calendar, the same removal drops the day
  explicitly and the total falls to 1289 of 1289 - 213 fewer, exactly the one measurement day,
  named with its reason. The two holiday lists differ by five dates, and
  `combineoi_26082026.zip` (21,000 bytes, 211 rows) shows the MWPL file is published on a
  clearing holiday. 41 store and calendar tests; suite 132 to 173.

- **Alternatives rejected:** a flag on `TRADING` for the special session, which answers the
  chaining question by default; inferring trading days from file presence, which is the bug;
  a hand-typed holiday list, which cannot be verified and whose typos are silent; and modelling
  the clearing calendar as a second axis, which the 26 Aug file shows is unnecessary.

- **Outcome:** accepted, 7 Nov 2026. One thing deliberately left open and failing closed: the
  chaining of Sun 8 Nov, which Monday's run will refuse until observed. Also open: the ban-list
  half of the clearing question, and whether NSE amends the 2026 circular.

### #013 addendum: Sunday 8 Nov chains, 9 Nov 2026
<!-- Authorship. Claude ran the check against the five files and pointed out the state the
     calendar was missing. Accepting the conclusion, requiring the verdict to be sourced to the
     files rather than to a circular, and building the missing state before it is needed are
     mine. -->

- **The question point 3 left open is closed: the Muhurat session is a link in the chain.**
  Friday 6 Nov -> Sunday 8 Nov -> Monday 9 Nov. Monday's previous trading day is Sunday, and
  Sunday's is Friday.

- **The test point 3 planned did not discriminate, and I am recording that rather than quietly
  swapping it.** The plan was to see whether Monday's ban list carried Sunday's state forward.
  But the three lists are identical - KAYNES alone on 6, 8 and 9 Nov - and with no transition
  over the weekend, "Sunday chains" and "Sunday is skipped" predict exactly the same lists. They
  are consistent with chaining and are not the evidence for it.

- **The evidence is that NSE ran a full end-of-day cycle on Sunday:**
  - `combineoi_08112026.zip` and `fo_secban_08112026.csv` exist, and both are dated
    `08-NOV-2026` inside, not only in the file name;
  - FutEq OI differs from Friday's on 218 of 218 scrips, same scrip set, so Sunday was measured
    rather than copied; MWPL is unchanged on all of them;
  - "Limit for Next Day" equals floor(0.95 x MWPL - FutEq OI) on 217 of 217 scrips, computed
    from Sunday's OI, with KAYNES on "No Fresh Positions".

  A day whose close sets the next day's limits is, by definition, the previous day for the next
  one. One wording correction from the summary I first agreed: the file never names the date its
  "Limit for Next Day" applies to, so "declared for 9 Nov" was an inference from the calendar,
  not something the file says. The calendar row records what the file shows.

- **How it is recorded.** Not as a test argument, which is what point 3 said and which would
  have left the fact living nowhere the pipeline reads. It is a meta row in
  `config/calendar_2026.csv`, the same pattern as `year_covered`:

      chaining_verified,special_session,2026-11-08,observed 9 Nov 2026 (not a circular): ...

  Its source names both files with their full sha256 and the three facts above. **It must be
  distinguishable from the circular-sourced rows, and the loader enforces that**: a verdict row
  whose source does not begin `observed` and carry a sha256 is refused. A finding from data and
  a line from a circular are different kinds of authority, and the file now says which is which.
  A test checks that the two checksums the row quotes are the ones `docs/READING.md` records for
  those files, so the row cannot drift from the table.

- **The gap, closed before it is needed.** Until today the calendar could say a special session
  was unverified (refuse) or verified (stop on it). It could not say "verified, and it does
  **not** chain" - a session whose files are real but which the next day's state skips over. No
  date needs that today. But the first time one does, the only way to express it would have
  been to edit the walk under deadline, which is how a rule gets bent to fit the day. So the
  state exists now, the same way `NoPriorDay` was decided before the first run needed it: a
  `chaining_excluded` row, same source rule, which stores the session's files and steps over it
  like a holiday. A session cannot be both; that is refused rather than resolved by precedence.

- **What changes downstream.** Row 6 on Monday now needs **Sunday's** book as yesterday.
  Friday's book handed in on Monday is refused as stale - before today it was refused for a
  different reason (chain unverified). A test pins both halves.

- **Evidence:** the five files and checksums are in `docs/READING.md`. 9 new tests; three old
  ones now strip the verdict row to reproduce the pre-9-Nov state, since the real calendar no
  longer refuses. Five mutations, all caught: an excluded session treated as unverified, an
  excluded session treated as a link, the loader ignoring verdict rows, the loader accepting any
  source, and one checksum digit changed in the row. Suite 342 to 351.

- **Still open:** this is one special session observed once. It says nothing about a Muhurat
  session in another year, which gets its own row from its own files or refuses.

## #014: Expiry in the ban-period baseline, 7 Nov 2026
<!-- Authorship. The rule, the physical-settlement reasoning and all seven predicted outcomes
     are mine, worked out on 7 Nov when Claude's expiry demonstration showed the baseline
     crashes on every expiry day. Claude found the NSE FAQ answer that confirms it, and found
     that the FAQ's wording sits one day earlier than my rule triggers - which is the open
     question at the end. -->

- **1. The rule.** When building the baseline for the ban-period check, a contract whose expiry
  is **before** today's trade date contributes zero delta. A contract expiring today, or later,
  is valued normally at today's NSE delta factor.

- **2. Why.** Indian stock derivatives are physically settled. At expiry an in-the-money
  position stops being an F&O position and becomes a delivery obligation in the cash market,
  and an out-of-the-money option expires worthless. Either way its F&O delta is gone the next
  day, which is why NSE publishes no factor for it.

  And the disappearance is **passive**. Para 5.3.2 restrains changes the holder causes; the
  holder did not trade to make an expired contract vanish, the calendar did. So it belongs in
  the passive part of the day's change, which is never a breach, and treating the contract as
  zero in the baseline puts it there.

  **NSE says the same thing, in the same word.** NSE Clearing FAQ question 14, updated
  13 Oct 2025: *"Increase in FutEq open interest for a stock in ban on account of expiry of near
  month positions will be considered as a passive breach and shall not be considered as a
  violation for levy of penalty on expiry day."* I derived the rule from physical settlement and
  from 5.3.2's wording before reading that answer, which is in a document I had already summarised
  on 30 Oct and had not connected to this problem.

- **3. Where it goes, and where it does not.** The filtering happens where the baseline is
  built, not inside `DeltaFactors.factor()`. Refusing a missing factor is correct everywhere
  else - it normally means a position in a contract NSE did not price, which needs a person.
  Expiry is the one case where the absence is expected, so it is handled before the lookup
  rather than by weakening the lookup. `book.live_on()` is the selection; it decides nothing.

- **4. Read the contract's `expiry` field, never a computed "last Thursday".** NSE moves an
  expiry earlier when it would fall on a holiday. My own worked example used 24 Nov 2026 as the
  November expiry and the verified calendar refused it: 24 Nov is Guru Nanak Jayanti
  (NSE/FAOP/71777), and the last Thursday is the 26th. A rule that computed the date would have
  to know that; reading the field does not.

  Weekends need no special handling either. A contract expiring on a Friday has
  `expiry < Monday`, so Monday's comparison drops it. The calendar decides which day is
  yesterday; the expiry field decides whether the contract still counts.

- **5. What it implies, including one consequence worth saying out loud.** Rolling **before or
  on** expiry is permitted, because the old contract is still in the baseline, so closing it and
  opening the same size in the next month leaves today's delta equal to the baseline.
  Re-entering **after** expiry is a breach, because the baseline is zero and the new contract is
  a position created from nothing - which is what "no fresh positions" means. An entirely
  expired book gives a baseline of zero, so anything held the next day is a breach. Short
  positions behave identically; the band is about delta moving away from zero in either
  direction, not about sign.

- **6. Expiry alone can never cause a breach, and that needed proving.** Zeroing an expired
  contract shrinks the baseline, which **tightens** the band, so it is not obvious that the
  tightening cannot fail by itself. It cannot: with no trading, today's holdings are yesterday's
  minus whatever expired, and the baseline drops exactly the same contracts and values the
  survivors at the same factors - so today's delta equals the baseline exactly.

  This holds **only** because the baseline zeroes expired contracts. Valuing them at yesterday's
  factor instead would leave today short of the baseline on a long book and over it on a short
  one, and the expiry would read as the holder's doing. Tested across five holdings shapes,
  including ones where the expiry makes the net delta *rise* - which is precisely the case FAQ
  14 is answering.

- **7. RESOLVED, 8 Nov: `expiry < today` is right, and the expiry day itself is confirmed.**

  FAQ 14 scopes its relief to "on expiry day" while this rule triggers the day after, so the
  threshold turned on a fact about NSE's end-of-day position rather than about the circular:
  does an expiring contract still carry open interest at its own expiry-day close? If not, the
  EoD position on expiry day would already exclude it while yesterday's included it, the
  baseline would have to zero it a day earlier (`expiry <= today`), and rolling on expiry day
  would become a breach instead of being permitted.

  It does. From `BhavCopy_NSE_FO_..._20261027`, the October monthly expiry:

      contracts expiring 27 Oct, in the 27 Oct file : 16,961
      of which open interest > 0                    : 13,590
      total open interest across them               : 7,304,736,812

  So the expiring contract is in the end-of-day position on its own expiry day, the strict
  `expiry < today` is correct, and case 5's roll on expiry day is permitted. Confirmed for the
  day after as well: nothing expiring on or before 27 Oct appears in the 29 or 30 Oct bhavcopy,
  or in `Contract_Delta_30102026.csv`.

- **8. The expiry calendar is not what either of us assumed.** Claude first sent me to the
  29 Oct bhavcopy on the assumption of a last-Thursday expiry - the twenty-year Indian
  convention, and no longer true, because SEBI moved expiry days in 2025. That file contains
  **no contract expiring that day**, so it answered nothing.

  The real pattern, read out of the files rather than assumed: **expiry is Tuesday, and moves
  EARLIER to the Monday when that Tuesday is a holiday.**

      2026-11-23  Monday     because Tue 24 Nov is Guru Nanak Jayanti
      2026-12-29  Tuesday    Wed 30 Dec is a trading day, so no move
      2027-01-25  Monday     because Tue 26 Jan is Republic Day

  Two of three monthlies moved. A computed "last Tuesday" would be wrong twice in three months,
  and wrong in the direction a calculation never guesses, because the shift is earlier rather
  than later. **That is the real argument for decision 4** - read the contract's own `expiry`
  field - and it is a good deal stronger than the one first recorded here, which rested on my
  own slip in a worked example.

  Consequence for the fixtures: `tests/test_expiry.py` and the Table 2 fixture were built on
  29 Oct and 26 Nov, neither of which is an expiry date at all. Corrected to 27 Oct and 23 Nov,
  which are. The arithmetic and the verdicts never depended on it, the positions being
  synthetic, but a fixture that implies it is realistic should use dates that exist.

- **Decision:** a contract expired before today contributes zero to the ban-period baseline;
  one expiring today or later is valued at today's factor. Filtered in the caller, not in the
  factor lookup. Read from the contract's own `expiry` field.

- **Why:** the delta genuinely disappears at expiry under physical settlement, and it
  disappears without the holder acting, so it is passive and a passive change is never a breach.

- **Evidence:** NSE Clearing FAQ 14 calls an expiry-driven increase during a ban a "passive
  breach" carrying no penalty. `Contract_Delta_30102026.csv` lists no contract expiring before
  30 Oct, earliest 3 Nov, so a lookup for an expired contract refuses - which is what crashed.
  The 30 Oct bhavcopy likewise carries zero rows for any expiry on or before 29 Oct. Sixteen
  tests in `tests/test_expiry.py`, covering all seven predicted outcomes and the
  cannot-breach-alone property across five holdings shapes.

- **Alternatives rejected:** defaulting a missing factor to 1.0, which would silently treat an
  unpriced option as a futures position and weaken a check that is correct everywhere else;
  valuing an expired contract at yesterday's factor, which breaks the cannot-breach-alone
  property; and computing the expiry date rather than reading it, which my own November example
  showed to be wrong.

- **Outcome:** accepted 7 Nov 2026 and closed 8 Nov, the expiry-day scope settled by the
  27 Oct bhavcopy. `check_ban_period_reduction()` is still unwritten; this is the rule it
  will apply. One thing left open and logged in `docs/doubts.md`:
  `Contract_Delta_30102026.csv` lists Thursday expiries - 5, 12, 19 and 26 Nov, 14,076
  contracts on the 26th - that neither the 29 nor the 30 Oct bhavcopy contains. Two NSE
  files a day apart disagreeing about the contract universe, with no explanation yet.

## #015: A flat day is a marker row, never an absence, 8 Nov 2026
<!-- Authorship. The marker-row design, the reasoning for trusting the file over the filename
     or the caller, and all four refusals are mine. Claude found the failure by running my
     first draft of check_ban_period_reduction() against a missing file, walked the shape of
     the fix, and built PropBook.flat() and the loader support. -->

- **The failure.** My first `check_ban_period_reduction()` took `today: PropBook | None` and
  `yesterday: PropBook | None`, with `None` meaning "verified, nothing held". The natural way to
  fetch a book is `books.get(day)`, which also returns `None` when the file never arrived. Run
  against the real day-5 breach with today's file missing:

      permitted=True  baseline=250  today=0  reason='held or reduced toward zero'

  The breach vanished: every holder looked as though they had closed out. A missing yesterday
  failed the other way, flagging an unchanged book as a fresh position. The docstring said
  "the caller must never pass None for a missing file", which was a type that could not say
  "unknown", guarded by prose - the same shape as `was_in_ban_yesterday: bool` in #011.

- **Three conditions, three representations.**

      positions were held          PropBook([...])
      verified: nothing was held   PropBook.flat(trade_date)
      the file never arrived       no PropBook at all

  `PropBook([])` still refuses, because an empty list is what a missing file produces by
  accident. A flat book can only be built by saying so, with a date; the constructor's name is
  the assertion. With non-optional parameters the caller's lookup becomes `books[day]`, and a
  missing day raises `KeyError` - the dictionary access is the guard and nobody has to remember
  anything.

- **Where the flat day comes from: a marker row in the file itself.**

      2026-10-30,,,FLAT,,,,

  Not the filename, because filenames get renamed and copied - `combineoi_13102026 (1).zip`
  broke the parser that way. Not a date the caller states, because then nothing in the file can
  contradict a wrong date. A marker row makes the file describe itself, the same way the ban list
  carries its date in its own heading and the transition diff trusted that heading over the
  filename. And a FLAT row can only be written on purpose, where an empty or missing file can
  happen by accident.

- **The four refusals.** A FLAT row beside position rows for the same date - the file
  contradicts itself, so neither statement can be trusted. A second FLAT row for one date. A
  FLAT row with any field other than the date filled - overloading the `instrument` column is
  safe only because of this, since it stops a half-written position row carrying FLAT in the
  wrong column from passing as "nothing was held". And a file with a header and no rows, which
  is what a truncated write looks like.

- **What it fixes beyond the missing file.** Every book now carries a date, including a flat
  one, so the check can always verify `calendar.previous_trading_day(today) ==
  yesterday.trade_date`. Under `None` that comparison was impossible on exactly the days it
  mattered. The calendar also brings the Muhurat refusal with it: `previous_trading_day()`
  raises through 8 Nov 2026 until the chaining is verified (#013), so the prop book fails closed
  there without any code of its own.

  That check closes a second hole found in the same review: my draft compared 21 Oct against a
  14 Oct book without objecting, which is `score_bans.py`'s "next file on disk" bug moved into
  the prop book.

- **Decision:** a verified flat day is `PropBook.flat(date)`, loaded only from a FLAT marker row
  whose other fields are blank. `check_ban_period_reduction()` takes non-optional books and the
  trading calendar, and verifies yesterday is the previous trading day.

- **Alternatives rejected:** `None` for flat, which is the failure; the filename as the date
  source; a caller-stated date; a separate `FlatDay` type, which would make every consumer
  handle two types where one empty book iterates as nothing.

- **Outcome:** accepted, 8 Nov 2026. `PropBook.flat()` and the loader support are in, with 15
  tests. **Format note, later the same day:** a `tm` column was added to the positions file
  (#016 addendum), so the marker row shown above, `2026-10-30,,,FLAT,,,,`, now has nine
  columns - the date, a blank `tm`, and FLAT under `instrument`. The rule is unchanged: the date
  and FLAT, every other field blank, `tm` included. The signature change and both date checks belong to `check_ban_period_reduction()`,
  which is not yet in the repo.

## #016: Entity-level position limits, SPEC row 7, 8 Nov 2026
<!-- Authorship. All five decisions are mine, made on 8 Nov from the source text of SEBI
     2025/79 para 5.8, the Master Circular clauses it recalibrates, and NSE Clearing FAQ
     questions 15 and 16, which Claude laid out before I decided anything. Claude found the
     FAQ 15 error and the doubling of the Cat II limits in the history; the two consequences
     at the end are Claude's, put to me as questions. -->

The limits are in para 5.8.1, as a share of MWPL for futures and options combined on one
underlying: Client/NRI 10%; TM proprietary 20%; TM proprietary plus clients, FPI Category I and
mutual funds 30%; FPI Category II other than the sub-category of individuals, family offices and
corporates 20%; that sub-category 10%. `config/rules.yaml` already carried all seven keys.

- **1. FPI Category II is two categories and never one.** `FPI_CAT_II_IFC` at 10% and
  `FPI_CAT_II_OTHER` at 20%, with no bare Cat II member.

  The trap is sharper than "collapsing Cat II into one number". NSE's own Clearing FAQ,
  question 15, summarises the split as individuals versus "non-individuals". Under SEBI a Cat II
  corporate or family office belongs with individuals at 10%; under the FAQ's wording it is a
  non-individual at 20% - double. A Cat II holder can therefore only be categorised through
  `Category.for_fpi_cat_ii()`, which puts corporates and family offices with individuals and
  refuses an unrecognised sub-category instead of defaulting, since the only available default
  is the lenient 20%. A regression test pins it. Logged in `docs/doubts.md` entry 8.

  The FAQ answered two of my questions correctly this week - Q14 on expiry and Q16 on the
  penalty - and is wrong here. Near-primary is not primary.

- **2. The measure: net within each UCC, gross-added across an entity's UCCs, in shares.**
  Para 5.8 sets percentages and never says how a holder's position is counted, so this is an
  inference, recorded as one, from four places that all point the same way:

  * para 5.1.1 measures participants' OI as **net** delta-adjusted positions at portfolio level;
  * para 5.1.2 nets within a UCC and **gross-adds across** UCCs;
  * Master Circular cl 3.3.2.2.1, the customer-level clause 5.8.1 replaces, limited the **gross**
    open position across all contracts on a stock;
  * the FPI monitoring clause stock derivatives import (cl 4.3.3.2 into 1.3.3.2.3) computes limits
    on a **gross basis at the level of the FPI**.

  It is also the cautious direction: the sum of each UCC's absolute net is never less than the
  entity's net, so if the inference is wrong it over-reports rather than hides. A long UCC and a
  short UCC of the same entity do not cancel - the same spirit as the per-UCC ban-period check in
  SPEC row 6.

- **3. The function aggregates, not the caller.** SPEC row 7's original signature,
  `check_entity_limit(category, futeq_oi, mwpl)`, took one number, so the caller summed. But a
  trading member faces two limits on two different totals - its proprietary book against 20%,
  and its proprietary book plus all its clients against 30% - and a function given one number
  cannot know which total it was handed. So it returns one check per (entity, scrip, limit), a TM
  gets two, and the signature changes. `SPEC.md` row 7 is updated.

- **4. An MWPL cut that pushes an unchanged position over the limit is reported as over the
  limit, with cause = passive.** Whether it is exempt from penalty is unresolved: Master Circular
  cl 4.3.3.4 imports the index rule that a breach caused by falling market OI is "passive" and not
  a violation, but that rule is written about OI, not about MWPL, which is what moves a stock
  limit. Reporting it with its cause hides nothing while the exemption stays open - `doubts.md`
  entry 9.

- **5. Every check is returned, carrying `excess_shares`; the penalty amount is a separate
  step.** FAQ question 16 charges the entity-limit penalty on the "excess quantity over the
  allowed quantity", valued at the cash-market close: 1% of that value or Rs 1 lakh, whichever is
  lower, with a Rs 5,000 minimum, per entity per stock per day. So the excess in shares is what the
  report has to carry. Returning every check, not only breaches, is the same reason
  `reconcile()` and `check_ban_period_reduction()` do: "nothing checked" must not look like
  "everything passed".

  The same three figures appear in `rules.yaml` against the **ban-period** `penalty_rate`, which
  is marked unverified. Same numbers, different rule; not assumed to be the same thing.

- **The history, because it changes the numbers.** The Master Circular clauses 5.8.1 recalibrates
  (3.3.2.3 to 3.3.2.5) had brokers, FPI Cat I and MFs at 20%, Cat II other at 10%, and the Cat II
  individual / family-office / corporate group at 5%. The 2025 circular doubled both Cat II
  limits. Anything written before October 2025 gives half the current figure.

- **Out of scope: para 5.8.1.6.** A joint exchange SOP to watch concentrated positions of top
  entities at delta and notional level. Surveillance, not a limit - no threshold to test. Kept as
  a v0.2 idea, since the per-entity FutEq positions already exist. `doubts.md` entry 10.

- **Two consequences, still open and both mine to answer before the function is written.**

  * Decision 3 needs reference data that does not exist yet. "Proprietary plus clients" needs to
    know which UCCs are a TM's clients, so the date-effective `ucc -> category` table needs a
    trading-member column. And underneath it: does an FPI or a mutual fund that trades through a
    TM count as one of its "clients" for the 30%?
  * Decision 4 needs yesterday. "Unchanged or reduced, and MWPL fell" compares two days, so - like
    row 6 - the function takes yesterday's position and yesterday's MWPL as well.

- **Decision:** the five above. `sentinel.entities.Category` is built, with the two Cat II members
  and the FAQ regression test. `check_entity_limit()` is not yet written.

- **Alternatives rejected:** one Cat II member with an "is individual" flag, which is the FAQ's
  error in a different shape; netting across an entity's UCCs, which is not what any of the four
  clauses describes and is the lenient direction; the caller aggregating, which cannot serve a
  TM's two limits; silently exempting MWPL-driven breaches, which would decide an open question by
  omission.

- **Outcome:** accepted, 8 Nov 2026. The function waits on the two consequences above.

### #016 addendum: the aggregation units and the cause rule, 8 Nov 2026
<!-- Authorship. A, B, 1a, 1b and the revised citation are mine, answered on 8 Nov to questions
     Claude raised from the source text. The (tm, ucc) key and the sign-flip edge case are mine;
     Claude added the sub_category check that holds decision 1 at the table. -->

- **1a. A broker's "clients" are only CLIENT/NRI accounts.** Master Circular cl 1.3.3.3, imported
  for stock derivatives by cl 4.3.3.3, says that for position-limit monitoring mutual funds are
  treated as trading members, the same way registered FPIs are. So an FPI or MF that trades
  through a broker is not inside that broker's book: each is a top-level holder with its own limit.
  The three holders in para 5.8.1.3 share a percentage, not a pool. Recorded as an inference - the
  text never defines "client", it gets there by treating FPIs and MFs as TMs.

- **1b. A mutual fund is its own level, with its schemes as its accounts.** The same clause treats
  MF schemes as clients, and Annexure 1 of 2025/79 computes index-futures limits gross at the level
  of the MF. Whether each scheme also faces the client limit is open - `doubts.md` entry 11.

- **Decision 2's fourth citation is contradicted, and the rule stands.** I cited the FPI monitoring
  clause's "gross basis at the level of FPI". Annexure 1 of the same 2025 circular restates the
  index-futures rule as gross at the level of the MF but **net** at the level of the FPI, client,
  MF sub-scheme and proprietary position. Two caveats: that is an index-futures, gross-notional
  regime rather than single-stock FutEq; and "net at the level of the FPI" may mean netting within
  one holder, which is my rule. If it does apply to single stocks, gross-adding across an FPI's
  sub-accounts reports at least the true figure, so the error would be an overstatement - the safe
  direction. The rule keeps three supporting citations and the direction argument; it no longer
  claims the fourth cleanly. `doubts.md` entry 12.

- **A. Two date-effective tables.** `holders (effective_from, holder_id, category, sub_category)`
  and `accounts (effective_from, tm, ucc, holder_id, is_proprietary)`.

  * Accounts are keyed on **(tm, ucc)**, not ucc, because a UCC is a code a trading member assigns
    and the same string can exist under two brokers.
  * The trading member belongs to the **account**, not the holder. A client can hold UCCs at two
    brokers: the client's own 10% gross-adds both, while each broker's 30% counts only the UCC
    registered under it.
  * The aggregates: a holder's own limit spans all its accounts across every TM; a TM's 20% is its
    proprietary accounts; a TM's 30% is those plus CLIENT/NRI accounts registered under it.
  * Cat II holders carry a sub_category and the loader refuses a row where it disagrees with the
    category, so a corporate cannot be typed in as `fpi_cat_2_other`. That holds decision 1 at the
    table rather than only in code.
  * Invariants checked per date: every account's holder exists; `is_proprietary` agrees with the
    holder being `tm_proprietary`; and a proprietary account's `holder_id` equals its `tm`.
  * **A trading member's `holder_id` is its member code - a convention, enforced.** Review on 8 Nov
    found that a proprietary account registered under TMA but owned by TMB loaded without error, so
    TMA's 20% would have been computed on positions TMA does not own. Nothing linked a TM's member
    code in the accounts table to its row in the holders table. NSE's member code already identifies
    a TM uniquely, so it serves as the holder id; a separate `tm` column on holders would be a second
    copy of the same fact, blank on nearly every row, needing its own filled-exactly-when rule, and
    able to disagree with the first. The same reasoning kept delta out of `Position` and the category
    out of the accounts table. A convention stated only in prose is the risk, so the loader refuses
    any proprietary account whose `holder_id` is not its `tm`, naming both. That also makes a TM's
    proprietary book single-owned by construction, which replaced a separate two-owners check.

- **B. The cause of a breach uses row 6's baseline.** For one holder and scrip,

      G = sum over the holder's UCCs of |net FutEq of that UCC|

  which is decision 2's gross measure. **ACTIVE** if G at today's holdings exceeds G at yesterday's
  live holdings, both at today's factors; otherwise **PASSIVE**. Comparing G at constant factors
  isolates what the change in holdings did, exactly as row 6's active part does.

  "Passive" therefore covers two mechanisms, not one: an MWPL cut, and FutEq rising with unchanged
  holdings because option factors moved - row 6's 21 Oct, up 200 shares with no trade. Yesterday's
  MWPL only names which mechanism it was, in the reason string. So a missing MWPL file makes the
  reason less specific; it never makes the cause unknown.

  **The sign-flip edge case, recorded deliberately.** A UCC that goes from +100 to -100, or a holder
  that moves exposure from a long UCC to a short one, has really traded, but G is unchanged, so the
  cause is not ACTIVE. That is correct for the question G answers - did the holdings change add to
  the gross position - and it means PASSIVE does not mean "did not trade".

- **2 (revised). Yesterday is `PropBook | NoPriorDay`.** A newly listed scrip is not a gap:
  yesterday's book is the whole book and simply holds nothing in that scrip. Only the first run
  has no prior day, and that is written deliberately as `NoPriorDay`, the same lesson as
  `PropBook.flat()` in #015. The verdict is always computed; the cause is ACTIVE, PASSIVE or a
  stated UNKNOWN, and is None exactly when the check is permitted, enforced in `__post_init__`.

- **Outcome of the addendum:** the reference tables are built in `sentinel.entities`, with 22 tests.
  `Position` then had a `ucc` field and no `tm`, so a book could not tell the same UCC at two
  brokers apart - and my `check_ban_period_reduction()` keyed on `(ucc, isin)`, so it would have
  merged two brokers' clients who shared a code into one check. Fixed the same day: `Position`
  carries `tm`, the account is `(tm, ucc)`, `PropBook.uccs` and `for_ucc()` are removed because
  a UCC alone answers a question with no answer, and row 6 is keyed on `(tm, ucc, isin)`. A test
  puts C001 at two brokers, one opening a fresh position and one holding, and asserts the breach
  lands on the right client.

### #016 addendum 2: how the runner records row 7, 12 Nov 2026
<!-- Authorship. The three answers are mine, given on 12 Nov to three gaps Claude found when it
     checked my first answer against store.py and runner.py. Claude added the RefusalStage.ROW7
     plumbing, the old-store guard, and the cross-table check in record_row7(). -->

My first answer was that an unknown account is a whole-stage row 7 refusal in the `refusal`
table, inside the day's transaction, like row 6's. It is not recorded in `run_log`, because
`run_log` holds the outcome of the whole run. Row 7 stopping does not make the ban forecast,
reconciliation or row 6 wrong, so the run still ends COMPLETED. The report shows row 7 as
"Refused" with the reason, never as zero breaches. That answer had three gaps.

- **1. A scrip with no MWPL: one refusal per scrip, and the holders it affected go in row 7's
  own table.** The refusal is `(date, ROW7, isin)` with a reason such as "no MWPL in today's
  combineoi; 2 checks not made". I chose one per scrip because the cause, no MWPL, is a fact
  about the stock, not about any holder: one cause, one row, and it fits the table's existing key
  `(trade_date, stage, subject)`. With the ISIN as subject and one refusal per holder, my own
  no-MWPL test would have broken it: H1's client check and TMA's 30% both fall on scrip Y, the
  second insert would collide, and the whole day would roll back.

  I rejected a subject like `holder|isin|limit`, because it packs three fields into one string,
  a key that has to be parsed later. The split instead: the `refusal` table says what could not
  be done and why; `row7_not_checked` holds each `NotChecked(holder, isin, limit_key, reason)`
  beside the checks in `row7_check`, and says who it affected. The report says the scrip was
  refused and why, and lists the holders from row 7's table.

- **2. NoPriorDay is declared, never inferred.** The runner must not infer a first run from a
  missing book: that is the same mistake as inferring a holiday from a missing file. So the book
  gets a declared start date in config, and:

  | Situation | Result |
  |---|---|
  | D is the declared start date | `NoPriorDay`, reason "first day of the book"; causes are UNKNOWN |
  | D is later, and yesterday's book is missing | row 7 refused: "no prop book for D-1" |
  | D is earlier than the start date | row 7 refused: "before the book's start date" |

  I rejected inferring it from "no earlier date in the file", because a truncated file would look
  exactly like a first run and every cause would quietly become UNKNOWN. A declared date is a
  statement someone made on purpose, like the FLAT marker (#015).

- **3. Two failure points, two reasons.** `ReferenceDataError` is raised both by
  `load_reference()` for a malformed holders or accounts file and by `check_entity_limit()` for
  a position in an unknown account. The runner catches it in two separate places, so the reason
  says which it was: "reference data could not be loaded: [message]" and "position in unknown
  account: [message]". Both are whole-stage row 7 refusals with an empty subject, and the run
  still completes. Nothing else is caught: any other exception is a real failure.

- **Plumbing these needed.**
  * `RefusalStage.ROW7`, and `'row7'` in the `refusal` table's stage CHECK. The schema is
    CREATE TABLE IF NOT EXISTS, so an older store keeps its old CHECK and its first row 7 refusal
    would fail mid-transaction, rolling the day back. Such a store is refused when it is opened,
    the same remedy as the REAL-column guard: move it aside and re-run its days.
  * `record_row7()` refuses a (holder, scrip, limit) already stored in the *other* table. Each
    table's own re-run rule cannot see this: a re-run where a scrip lost its MWPL would add a row
    to `row7_not_checked` and leave the old one in `row7_check`, so the day would say both.
  * `cause` is NULL in `row7_check` exactly on a pass, enforced by a CHECK. That NULL means "no
    breach to explain", not a missing value, so decision 5 of #019 holds.

- **Outcome.** Accepted, 12 Nov 2026. `check_entity_limit()` landed in 8390691 with 20 tests;
  its mutation check killed 8 of 8 mutants, including a Cat II corporate given FAQ 15's 20%. The
  refusal stage and its guard are in 5738320. The two row 7 tables, their writer and reader are
  built with 8 store tests. Still to do: the book start date in config, and the runner and report
  wiring.

## #017: SAIL's release as a second fixture window, 9 Nov 2026
<!-- Authorship. What to assert - held on 3 and 4 Nov, released for 6 Nov, kept out on 6 Nov -
     and that both in-band cases belong in CI on one stock, are mine. Claude read "held on 3 and
     4 Nov" as the 3 and 4 Nov closes (the 4 Nov close is the 80.51% one), added the 2 Nov close
     since its seed was in the fixture anyway, chose the layout below, wrote the builder and the
     tests, and ran the mutations. -->

- **Decision:** SAIL's 2 to 6 Nov closes are a separate fixture directory,
  `tests/fixtures/sail_release/`, with tests in their own section of `tests/test_transitions.py`.
  The next session comes from the calendar, not from the next file in the folder. The builder,
  `scripts/build_sail_fixture.py`, is committed.
- **Why separate:** the first window's tests count exactly 51 scrip-days, 7 transitions and 15
  ban lists, and require both kinds of in-band control on every day. SAIL-only rows dropped into
  the same files would break those counts rather than extend them, and the fix would have been
  to loosen the tests that make the first window's claim. A second directory keeps both claims
  exact.
- **Why the calendar:** the 6 Nov close is answered by Sunday 8 Nov's list, because the Muhurat
  session chains (#013 addendum). "The next file on disk" is the bug #013 was written for.
  This needs one more ban list than "3 to 6 Nov" suggests at each end: 2 Nov is the seed for
  the first close, and 8 Nov is the answer for the last one. Both are copied byte for byte.
- **Why a committed builder:** the first fixture set's `SOURCES.md` says to "regenerate with the
  builder recorded in DECISIONS.md", and no builder is recorded there. This one is a script in
  the repo, it copies NSE's strings rather than round-tripping them through floats, and rerunning
  it reproduces the fixture byte for byte.
- **Evidence:** 8 tests; suite 351 to 359. Five mutations, all caught: a single line at 95%
  (fails the 2, 3 and 4 Nov closes), a single line at 80% (fails the 6 Nov close), the calendar
  saying Muhurat does not chain, SAIL added back to the 6 Nov list by hand, and one digit of a
  READING.md checksum changed. The first two are the point: each half of the band catches a
  different lazy engine, which is why both had to be fixtures.
- **Outcome:** accepted, 9 Nov 2026. Still open: the first fixture set has no builder in the repo.

## #018: v0.1 scope cut, 9 Nov 2026

- **What:** the pipeline runner moves into v0.1; row 7 (`check_entity_limit()`) moves to
  Week 3; the file watcher and the break workflow move to v1.0.
- **Why:** correctness work (calendar, Muhurat, expiry, flat days, keying) took precedence
  over features. v0.1 ships as an engine that runs a day, not a set of functions.
- **Evidence:** Week 2 as planned against what exists on 9 Nov:
  - D1 file and deadline watcher: not built.
  - D2 point-in-time store: done, with the calendar and ingest. The hash manifest is not:
    the checksum table in `docs/READING.md` is still pasted by hand.
  - D3 reconciliation of positions: partly. The prop book and row 6 are done; row 7 has its
    reference tables but not the check.
  - D4 break workflow: not built.
  - D5 pipeline runner: not built.

  The time went to work the plan did not have: the four-state calendar and Muhurat chaining
  (#013), the expiry rule (#014), the flat-day marker (#015), row 7's design and (tm, ucc)
  keying (#016), and SAIL's scoring and fixtures (#017).
- **Outcome:** accepted, 9 Nov 2026. Recorded in `PLAN.md` under Week 2. Row 7's design is
  complete, so only its implementation waits.

## #019: The pipeline runner, 9 Nov 2026

**What.** One command runs a trading day D end to end: ingest, check,
forecast D+1, reconcile, row 6, report.

1. **Per-consumer refusal.** Everything is framed from run date D.
   - Missing `combineoi_D`, or D unknown/unverified in the calendar:
     the whole run refuses.
   - Missing `fo_secban_D`: the forecast seed refuses in-band scrips
     only (#012); D's official state is stored as missing; D-1's
     forecast is reported unscored; row 6 refuses.
   - Missing positions or delta factors for D or the previous trading
     day: row 6 refuses; everything else runs.
2. **Why combineoi_D is required.** The store is keyed on ISIN; ban
   lists carry symbols, resolved only through the same day's combineoi
   (#011 Q2). An older mapping goes silently wrong on the day of a
   rename or reuse.
3. **Atomic per run.** All of D's results commit in one transaction,
   only after every stage finishes. A refusal is a stored result, not
   a failure. Inside run D's transaction the store enforces #011's
   timing: ban_state accepts D's official state and the next trading
   day's forecast, and nothing else.
4. **Run log, outside the transaction.** RUNNING before; COMPLETED,
   REFUSED or FAILED after. Columns: run_id, trade_date, started_at,
   finished_at, outcome, reason, input_checksums, code_version, dirty,
   rules_checksum, calendar_checksum, rules_status (the rules file's
   keys by state, {"assumed": [...], "unverified": [...]}, so the footer
   names the thresholds used on an assumption and the ones refused).
5. **Missing vs not run.** A missing input is a refusal record in the
   day's transaction. "Not run" is no COMPLETED row in the run log.
   A NULL alone means nothing.
6. **Stale RUNNING row.** With no lock held, mark it ABANDONED (time,
   superseding run_id) and start a new row. With the lock held, refuse.
7. **Uncommitted code.** Record commit plus dirty flag; the report
   footer says "not reproducible". README results come only from clean
   runs.
8. **Report rendered from the store** plus the run log, never from
   memory. Same store, same report; a crash after commit costs nothing.
   Order: refusals, flag disagreements, row 6 breaches, tomorrow's ban,
   watchlist, checks passed, audit footer.
9. **Watchlist is the 80–95% band**, with distance to the line that
   applies to each scrip. No new threshold.
10. **Residuals:** the report shows the count; min and max stay in the
    store.
11. **Re-runs:** identical inputs give identical results. A changed
    input refuses, naming the file and both checksums. Supersede and
    the stale-day cascade move to v1.0.
12. **No retries in the runner.** PLAN.md's "retries with backoff" is
    dropped: there is no downloader, and there will not be one,
    because NSE's terms of use prohibit automated collection (#010
    addendum). v1.0 adds an importer instead: I download each file by
    hand into `data/`, and the importer verifies its heading date and
    checksum. The runner reads `data/` either way, so it does not
    change.
13. **Unverified next trading day refuses only the forecast.** D itself is
    settled, so its official state, reconciliation, row 6 and D-1's score
    are still correct; only the forecast's target day is unknown. Recorded
    as a whole-stage FORECAST refusal (subject "").
    The store enforces it too: the ban-state guard consults the calendar
    only for forecast writes, so D's official state is stored either way.
14. **Unresolved banned symbol refuses the whole run.** Matches
    ingest.load_official_day: under-reporting a ban is the worst error to
    make quietly (#011 Q2), and one failure handled two ways in two code
    paths is worse than either choice.
15. **Excluded special session refuses the whole run.** Its official state
    is not a link in any chain, so storing it invites misuse as a seed.
    No date uses it yet; revisit if a real excluded session occurs.

**Why.** Every piece applies a rule already in the project: missing
inputs are stated, never inferred (#011, #015); nothing derived is
stored beside its inputs; results that cost money fail loudly.

**Evidence.** On 4 Nov, no prop book exists for 3 or 4 Nov, so row 6
refuses there: the per-consumer rule in a real case. ban_state.official
is nullable, so "missing" and "not run" are indistinguishable without
the refusal record and run log.

**Outcome.** Accepted, 9 Nov 2026. Store tables (run_log, measurement,
reconciliation, row6_check, refusal) built as plumbing; the runner
itself is mine, Tue 10 Nov.


## #020: The replay window, and what is cut for it, 11 Nov 2026
<!-- Authorship. The window, the reasons, the cuts and the rules.yaml approach are mine, written
     up from my 11 Nov notes. Claude checked the FutEq basis of the 1 Oct 2025 file, found that
     the calendar does not cover 2025, corrected the SPEC rows the index cut names (row 15 is not
     an index row, and I cut it separately), and filed this. -->

**What.** The replay covers every trading day from **1 Oct 2025** to now: option A of the three I
weighed. About 520 files, downloaded by hand one month at a time, newest first, each month
checked before the next is started. Cut to make room for it: the **live page** (automation 9b)
and **OTR**, since neither adds evidence; the **index-derivative rows**, SPEC 8, 9, 10, 13, 14
and 16, from Week 4; and **row 15**, intraday MWPL monitoring for single stocks, because it needs
intraday data and every file this project has is end of day. They go in the README as not
covered, and the time goes to the replay and row 7.

**Why.**
- It is the only window that can verify the MWPL reset calendar for all four quarters, not only
  October.
- It gives far more real transitions, in-band days and expiries than the current 15 sessions.
- It is the best chance of a real scrip closing exactly on 95% or 80%, which no real row has done.
- If it finds days where the engine disagrees with NSE, that is what the replay is for. I will
  record each one and why.
- 1 Oct 2025 is the right start, not earlier: it is the first day of the regime the project
  implements (2025/79 para 6 - the MWPL definition, ban-period position creation and entity
  limits all took effect that day), and FutEq OI was already the basis.

**Evidence.**
- **Archive depth,** checked by hand on 10 Nov: both daily files download for Fri 31 Jul 2026 and
  Wed 1 Oct 2025, so NSE's archive reaches at least the start of the window.
- **Timing,** by hand: five `combineoi` files (16, 19, 21, 22, 23 Oct 2026) in 2 minutes 3
  seconds, about 25 seconds a file. 508 files still to fetch is about 3.5 hours, spread over
  several sessions.
- **The FutEq basis on day one:** `combineoi_01102025.zip` has the same eight columns as today's,
  and its `Limit for Next Day` matches `0.95 x MWPL - FutEq OI` on 207 of 207 rows and the
  notional formula on 0. Checksums of all nine files in `docs/READING.md`.
- **The reset, so far:** MWPL changed for 158 of 213 scrips between 30 Sep and 1 Oct 2026 and on
  no other pair of days (READING.md). October is observed; January, April and July are not.

**Consequences.**
1. **The calendar must be extended to 2025 first.** `config/calendar_2026.csv` covers only the
   year whose NSE holiday circular it cites, so every date from 1 Oct to 31 Dec 2025 is UNKNOWN
   and the runner refuses it. It needs NSE's holiday circular for 2025, read and cited the same
   way as 2026's, before those 66 days can be replayed. Until then their checklist pages list
   every weekday and say so.
2. **`reset_calendar` stays `verified: null`,** with a note recording October as observed from
   the 30 Sep and 1 Oct files. The replay should let me observe January, April and July too.
3. **Downloads are tracked by `scripts/download_checklist.py`:** one page of links per month in
   `reports/downloads/` (gitignored), and a `check` that verifies a finished month - present,
   readable, dated as named, no stray copies - and records each file's size and sha256 in
   `docs/data_manifest.csv`. That manifest replaces hand-pasting rows into READING.md's table.
4. **Row 15 is cut on its own reason, not as an index row.** It is single-stock intraday MWPL
   monitoring - at least four random checks a session, for Additional Surveillance Margin - and
   it needs intraday positions, which no end-of-day file carries.

**Outcome.** Accepted, 11 Nov 2026. Downloads start with November 2026, newest first.
