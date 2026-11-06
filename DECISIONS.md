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

- **5. T versus T+1 for the `combineoi` flag is unresolved, and no longer matters.**

  Does `is_in_ban()` computed from 30 Oct's file answer "banned on 30 Oct" or "banned on the
  next trading day, 2 Nov"? The column is titled **`Limit for Next Day`** and NSE writes
  `No Fresh Positions` into the cell where its number would go, which argues T+1; `SPEC.md`
  row 4's end-of-day test argues the same. But the files cannot prove it. On 6 Nov I
  downloaded `fo_secban_30102026.csv` to settle it and all three sets came back identical:

      30 Oct combineoi flag : KAYNES, SAIL
      30 Oct ban list       : KAYNES, SAIL
      02 Nov ban list       : KAYNES, SAIL

  A ban that persists across both days looks the same under either reading, so no diff of
  these three files can distinguish them.

  **It stops mattering because of where the seed comes from.** `was_in_ban_yesterday` is read
  from the previous day's published **ban list**, never from the `combineoi` flag. The flag is
  then only ever an input to the reconciliation in `engine.py`, which compares headroom and
  does not care which date the suppression refers to. So the ambiguity is quarantined: it
  cannot reach the forecast, and the forecast is the thing being scored.

  This is also what makes the score non-circular, which is the point. Seeded from the flag,
  both banned scrips sit inside the dead zone where the forecast IS the seed, so the agreement
  was a tautology. Seeded from the 30 Oct ban list, the seed, the measurement and the answer
  come from three different files and none of them is the column being predicted.

  Revisit only if a reconciliation break appears that the T/T+1 reading would explain, or if
  a ban is ever observed starting and ending inside one day. `docs/READING.md` previously
  asserted T+1 as established, reasoning from the very coincidence shown above to be
  non-identifying; corrected on 6 Nov.

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

- **Outcome:** accepted, 6 Nov 2026, and the five decisions are closed. Nothing implemented
  yet. The forecast is scored and non-circular, but it has exercised one of three branches, so
  the next step is a hunt rather than a build: download `fo_secban` for consecutive trading
  days, diff them to find the dates where a symbol appeared (an entry) or disappeared (a
  release), and pull the `combineoi` only for the day before each change. Ban lists are 62
  bytes and `combineoi` is 22 KB, so the cheap file finds the expensive one. The diff needs the
  trading calendar in `progress.md`, since a holiday read as a change is a phantom transition.
  Also outstanding from #011's own Outcome and still not done:
  `SPEC.md` rows 4 and 5 still carry a three-argument `is_in_ban()` with no `rules`, and
  `PLAN.md` W2 still has no state store in the runner's design.
