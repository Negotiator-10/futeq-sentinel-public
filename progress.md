# Progress

Start every session by reading this file, then `TASKS.md` for the tick list. `PLAN.md` is the five-week strategy.

## Status: Week 0 (setup), 28 Oct 2026
Done by Claude on 28 Oct:
- Folder `Desktop\futeq-sentinel` with a git repository (branch `main`).
- Conda env `sentinel` (Python 3.12, 64-bit) with pandas, pyarrow, pydantic, pandera, scipy, PyYAML, requests, pytest, hypothesis, jinja2, matplotlib and python-dotenv.
- `CLAUDE.md` (tutor mode), `PLAN.md`, `DECISIONS.md` (#001 to #005), `LEARNING.md`, `SPEC.md` skeleton, `README.md`, `.gitignore`, `.env.example`.
- `docs/READING.md` (reading list and facts-to-verify table) and `docs/research_report.md`.
- First local commit `d48166d`. The private GitHub repo is not created yet, because the upload needs your permission. Run this yourself from this folder:
  `gh repo create Negotiator-10/futeq-sentinel --private --source=. --remote=origin --push`

## Schedule moved forward (29 Oct)
The project starts today, Thu 29 Oct, not Mon 2 Nov. Each week is now six working days, Thursday to Wednesday, with Sunday off. The new release dates are v0.1 on Wed 11 Nov and v1.0 on Wed 2 Dec (see `PLAN.md` and `DECISIONS.md` #006).

## Today: Week 1, Day 1 (Thu 29 Oct)
- [x] Create the private GitHub repo with the command above. Done 29 Oct: https://github.com/Negotiator-10/futeq-sentinel (private, `main` tracks `origin/main`).
- [x] Read the NSE Clearing FAQ and draft `docs/notes_faq.md`. Done 30 Oct. All 7 questions answered in my own words.
- [ ] Write the first `LEARNING.md` entry.
- [ ] End-of-day check: explain the FAQ back to Claude, who will ask follow-up questions.

## Where I actually am (Sat 31 Oct)
Two days behind the plan: D1 is not closed and D2 has not started. Today is D3 on paper.

Claude reviewed the FAQ notes on 30 Oct. Right: the utilisation formula, the hysteresis reasoning, the 10/20/30% entity limits. Six rows still need a second pass against the primary source:
1. Q3, the ban entry threshold: the number I wrote does not match the FAQ.
2. Q1, why a delta-based measure beats counting contracts: not answered.
3. Q2, MWPL: I named only one of the two quantities, and no floor.
4. Q4, the base position a ban-period breach is measured against, and which day's delta.
5. Q6, what the penalty is counted per (three dimensions).
6. Q7, the actual file names. This gates the D5 feasibility check.

`docs/doubts.md` (doubts and references to follow up) and `docs/interview_answers.md` (the six-beat answer spine: Why, Count, Cap, Cross, Clear, Cost) were added on 29 and 30 Oct.

The teach-back is deliberately postponed until the numbers are right, so I don't rehearse wrong facts.

## NSE trading holidays in the project window
Checked on nseindia.com on 28 Oct 2026. The file watcher must know these dates.

| Date | Day | What happens |
|---|---|---|
| 8 Nov 2026 | Sunday | Muhurat trading (special one-hour session). Expect files on a Sunday. Timings are notified separately by NSE. |
| 10 Nov 2026 | Tuesday | Holiday (Diwali Balipratipada). No files. |
| 24 Nov 2026 | Tuesday | Holiday (Guru Nanak Jayanti). No files. |
| 25 Dec 2026 | Friday | Holiday (Christmas). After the project window. |

Other dates to watch: Mon 7 Dec 2026, when NSE retires the older file formats (see `docs/READING.md`).

## Sat 31 Oct, end of day
Verified MWPL against SEBI 2025/79 para 5.2.3: the formula has three limbs, not two, and the floor
of 10% of free float binds in the worked example, tripling MWPL. Claude read and indexed all five
Week 1 sources, which turned up NSE's published delta formula (SURV70553 Annexure 2) and a
15-minute intraday cure period. Three commits pushed. Still open from Day 1: `LEARNING.md` and the
teach-back.

Working Sun 1 Nov, the scheduled day off, to pull back the slip. Tomorrow is D4's work.

## Sun 1 to Mon 2 Nov: D4's work
Excel on this laptop wants activation, so I rebuilt the MWPL sheet from scratch in a browser
spreadsheet and worked it from memory. All eleven numbers came out right, every cell a formula
referencing an input, every unit labelled. Hand-calculations now live in the repo as `.csv`
alongside the `.xlsx`, because git can diff a CSV and pytest can read one.

`SPEC.md` is half written: six of twelve rule rows done, each with a citation, a function name and
a named test case. The three rows I worked myself each turned up a gap that the summaries had
hidden:

1. Para 5.2.3 compares shares against rupees and never says which price to convert at.
2. Para 5.2.4 names no reset months, so the quarterly calendar is configuration, not a constant.
3. Para 5.2.6 says the test is whether FutEq OI **exceeds** 95% — so a stock sitting exactly on
   95% is not in ban.

Chasing the third one closed the 80% question that had been open since 31 Oct. It is in the SEBI
Master Circular of 30 Dec 2024, Chapter 5, clause 3.3.2.1.2.3, and the wording is "80% **or
below**" — inclusive, the opposite of the 95% entry. The same chapter also reframed the penalty
question: clause 3.3.2.1.2.2 sets the base and the timing but leaves the percentage to the
exchange, so the 1% / Rs 1 lakh / Rs 5,000 figures can never be verified against SEBI. They have
to come from an NSE circular. And clause 3.3.2.1.3 describes the 6:30 PM MWPL file, per security,
with MWPL and OI both in number of shares — which answers part of Day 1's Q7 for free.

Still open from Day 1: `LEARNING.md`, the `notes_faq.md` second passes, and the teach-back.
`docs/doubts.md` is still empty, which is the discipline I keep deferring.

## Mon 2 Nov, end of day: the config, and what filling it taught me
I filled every stub in `config/rules.yaml` myself — about fifty thresholds, drawn from the
sixteen spec rows. The regulatory facts came out largely right. The encoding came out wrong in
five ways, each repeated across the file:

1. Indentation that orphaned a whole block, so my correct ban-exit entry was attached to nothing.
2. `key:"value"` with no space after the colon. The file would not parse at all.
3. Prose in the `value` slot where a boolean belonged. `sign_change_allowed` is a yes/no
   question and I answered it with a paragraph, which an engine reads as "yes".
4. Values that YAML silently reads as something else: `15:30` is the integer 930, `1,500` is a
   string. Both look right to a reader.
5. Three wrong figures, including `minutes_in_year: 8,670`.

The fifth one is the only one that matters, and it is the lesson of the day. 8,670 is the
minutes-to-expiry in NSE's worked example — the numerator of T, not the denominator. Every other
mistake in that file broke loudly: a parse error, a crash, a string where a number belonged.
That one would have run. It would have made T come out at 1.0 instead of 0.0165 and corrupted
every option delta by about sixty times, producing output indistinguishable from correct output.
I now think that is the whole argument for the config file and the loader: not tidiness, but that
the errors worth defending against are the ones that still run.

Claude rewrote the file at my instruction, which is the third time this week I have asked for
work that `CLAUDE.md` assigns to me, and the worst of the three — these numbers are the project.
Recorded at the top of `rules.yaml` and in `TASKS.md`. The debt is re-deriving five thresholds
from memory and diffing them against the file.

Automation 5 is done: `src/sentinel/rules.py` loads 50 thresholds and refuses, at load time, any
one that cannot say where it came from. Three states rather than two — verified, assumed,
unverified — because the reset calendar is a guess the engine cannot run without, while the
penalty rate is a guess it must refuse to make. 34 tests pass. Decisions #007 to #009 logged.

## Superseded: next task as at 31 Oct morning
Read paragraph 5.2 of SEBI circular 2025/79 (link in `docs/READING.md`) and fix the Q2 row of `docs/notes_faq.md`: both quantities that set MWPL, the floor, and the reset frequency. Then work out one stock's MWPL and utilisation by hand in Excel. That is D2's work, and it closes the biggest gap in the notes at the same time.

## Thu 5 Nov: Week 2 Day 1, and what Week 1 actually delivered
Week 1 closed on Wed 4 Nov. The build finished ahead of the plan; the understanding finished
behind it, and the gap is recorded rather than smoothed over.

Shipped since 2 Nov: `config/rules.yaml` with fifty thresholds, each carrying its own source and
the date I read it; a loader that refuses any threshold without provenance and refuses to
evaluate the three the circulars leave to the exchange; `DECISIONS.md` #007 to #011; two parsers
with 65 tests; and CI that fails the build if raw NSE data, a `.env`, a PDF or an archive is ever
tracked in git. The last one caught me an hour after I wrote it.

Two findings from the data are worth more than any of the code. NSE's `combineoi` file publishes
`Limit for Next Day`, and it equals `0.95 x MWPL - FutEq OI` on 216 of 216 rows - the formula I
derived by hand from para 5.2.3 and 5.2.6 four days before I had the file. It reconciles against
notional OI on 0 of 216, which settles that NSE computes on the futures-equivalent basis. And on
30 Oct SAIL was barred at 84.93% utilisation while BANDHANBNK traded freely at 85.98%, which
proves ban status is a state rather than a measurement and forced the three-argument
`is_in_ban()` in #011.

Twice in one afternoon I produced a well-argued answer aimed at the wrong system: a GARCH warm-up
from my VaR project, and an order-blocking scope from an OMS. A good design for the wrong system
reads exactly like a good design. That is the week's real lesson and it is lesson 5 in
`LEARNING.md`.

The honest ledger: 48 open against 36 done, and most of the 48 is Week 1 understanding debt, not
build work. Three pieces of core logic were written by Claude at my request - `SPEC.md` rows 6 to
16, the `rules.yaml` rewrite, and #011 Q2 - plus the first `LEARNING.md` entry. Repayment blocks
in `#011` and `TASKS.md` exist to work that off, and #011's was done from memory on 5 Nov.

Next: the reconciliation. Compute utilisation and headroom from the parsed rows and score them
against NSE's own published column. It is the first end-to-end result, the spine of v0.1 on
Wed 11 Nov, and the one function whose answer I already know.

## Fri 6 Nov: Week 2 Day 2 — the engine, and a score that means something
Yesterday's reconciliation was D3's work done a day early, so D1 and D2 were the open ones.
Today closed most of D2. Four commits, all pushed.

`src/sentinel/engine.py` now holds four functions. `utilisation()` and `headroom_shares()` are
one line each; `headroom_shares()` reads 0.95 from the config and matches the arithmetic shape
of NSE's own column, so the reconciliation residual carries no floating-point difference of my
own making. `reconcile()` walks all 218 rows down two paths and agrees with NSE on 216 of 216,
every residual inside [0, 1). I chose the signed test over `|residual| < 1` because NSE
publishing *more* headroom than the formula allows is a trading risk while publishing less only
costs opportunity, and an absolute test would not notice the first.

`is_in_ban()` is the one that mattered. Until today it existed in `SPEC.md` rows 4 and 5, in
`DECISIONS.md` #011, in `LEARNING.md` — and in no Python file anywhere. Four lines: yesterday's
state selects which single threshold is consulted, and both thresholds come from
`config/rules.yaml` so neither direction is retyped in code. 21 tests, and Claude then broke the
function five ways to check the tests would notice; all five were caught, including the two
hardcoded directions that are numerically correct today and diverge only at one boundary input.

Two things I got wrong and had corrected. I wrote `held = u > exit_threshold`, which fetches the
value from config and then retypes the direction in Python — the exact thing the `operator`
field exists to prevent. And my `reconcile()` reported `ok` as true when nothing had been
compared, so a file with every headroom suppressed would have reconciled clean.

`DECISIONS.md` #012: the point-in-time ban-state store, five decisions. The one I am most
pleased with is that state only *matters* inside the 80-95% band, so a missing previous day
refuses 7 of 218 scrips rather than losing the day. The one that matters most is that the
engine's own forecast never feeds back into the engine — only NSE's published list does — because
a wrong ban flag latches rather than decaying, and 0 of 20 replayed days agreed between two
seeds. I also had to be shown that my own #011 Q2 already ruled out re-seeding from the ban list
alone: `fo_secban` carries no ISIN.

The honest part of the day. My first score — 218 of 218 against NSE's 2 Nov ban list — was
circular. I had seeded `was_in_ban_yesterday` from the 30 Oct `combineoi` flag, which sits in a
column titled `Limit for Next Day`, and both banned scrips sit inside the dead zone where the
forecast *is* the seed. So I was predicting the answer from itself. `docs/READING.md` had made
the same mistake on 2 Nov, asserting from the identity of three sets that the flag is NSE's T+1
declaration — an inference that does not hold, because a ban persisting across both days looks
identical either way. Both are corrected.

Downloading `fo_secban_30102026.csv` fixed it: seed, measurement and answer now come from three
different files and none is the column being predicted. 218 of 218, 2 true positives and 216 true
negatives. But entry fired 0 times and exit fired 0 times, so one of three branches ran and 216
of those answers are "nothing happened" on a day whose highest free utilisation was 85.98%.

So the last thing today was a hunt rather than a build. Twelve more ban lists, downloaded by
hand, diffed: **three entries and four releases between 12 Oct and 2 Nov**, with KAYNES doing a
full entry-hold-release-re-entry cycle. Recorded in `docs/READING.md`. Five `combineoi` files
will turn "the hold branch works" into all three branches scored against NSE's own list.

Two side findings. A 404 on a ban-list URL means no trading session, since NSE publishes a list
even when nobody is banned — so the download attempt is its own calendar check. And the
checksum table in `READING.md` has outgrown being written by hand, which is what #012's hash
manifest is for.

Still open from Week 1 and before: the `SPEC.md` rows 4 and 5 signature, now stale twice;
`PLAN.md` W2's runner design with no state store in it; `LEARNING.md` rewritten in my own words
with its two blank sections filled; SURV70553 unread; and the teach-back, now scheduled five
times.

### Later the same evening: the result the project was built for

Twelve more ban lists and six more `combineoi` files, downloaded by hand. Seven ban transitions
between 12 Oct and 2 Nov - three entries, four releases - and the engine forecast every one of
them correctly. **1502 of 1502 scrip-days agree with NSE's published ban lists, zero false
positives and zero false negatives.** Entries at 97.98%, 95.67% and 95.01%, releases at 79.41%,
78.82%, 70.02% and 66.96%, and nothing in the fifteen points between. Every branch of
`is_in_ban()` has now run on real data; this morning only one had.

SAIL is the row I will use in an interview. At the 14 Oct close it was 29,360 shares past the
95% line on an MWPL of 217 million - one part in seven thousand - and NSE banned it the next
day. On 1 Nov I read para 5.2.6, noticed the word "exceeds", and wrote down that a scrip sitting
exactly on 95% is therefore not in ban. That looked like pedantry about one word. The market
traded 0.0135 of a percentage point from the case that tests it.

What the number does not mean. 1,495 of those scrip-days are a security nowhere near a
threshold staying nowhere near it, so 1502 is a statement about false alarms and **seven** is the
sample that tests the logic. Neither exact boundary has ever been hit, no scored day was missing
its seed, and no newly listed scrip has yet appeared near a line - though the universe did move
213 to 219 to 218 inside the sample.

And the claim is narrower than it looked. I proved today that the `No Fresh Positions` flag in
day T's file is NSE's declaration for T+1, which means the answer sits in the same file as the
inputs. There is no time advantage at all. What this engine does is reproduce NSE's ban
determination independently and reconcile against it - which is the job I am applying for, so
the narrowing costs nothing except the right to use the word "forecast" loosely.

Two corrections to my own work from earlier today. I concluded from a 404 that 27 Oct was not a
trading day, wrote it into `docs/READING.md` and committed it; a retry returned the file. The
404 was transient, the 28 Oct release is measured from the 27th rather than the 26th, and 20 Oct
is still unexplained rather than confirmed as a holiday. And `READING.md` had asserted T+1 on
2 Nov from three identical sets that cannot distinguish the two readings - the conclusion was
right and the reasoning was worthless, which are different things.

`PLAN.md` puts validation against NSE in Week 4. It is done, on 6 Nov, and it is the headline
result for v0.1 on Wed 11 Nov.

Still mine and still not done: `LEARNING.md` in my own words with its two blank sections, the
four interview questions from today, `SPEC.md` rows 4 and 5, `PLAN.md` W2's runner design, and
the teach-back.

## 7 Nov 2026 (Sat)

- **Trading calendar, four states** (#013). Built from NSE's F&O holiday
  circular NSE/FAOP/71777, acquired and checksummed, not typed by hand.
  States: TRADING, HOLIDAY, UNKNOWN, SPECIAL_SESSION. A missing file is
  judged against the calendar, never inferred from what's on disk.
  20 Oct confirmed as Dussehra; 27 Oct is a trading day: its first 404
  was transient, and the file is on disk.
- **Clearing-holiday check.** combineoi is published on 26 Aug, a clearing
  holiday, which settled the question from the data rather than the
  pasted list. n=1, and the ban-list half is untested.
- **Store and ingest wired.** Point-in-time store in SQLite, keyed
  (ISIN, trade_date), holding the engine's forecast and NSE's official
  state separately; only official state feeds the next day.
- **Transition fixtures (option C).** Transition scrips plus in-band
  controls (MANAPPURAM, INOXWIND): about 10 KB, 51 rows and 15 ban
  lists. (4.2 KB was the planning estimate.)
- **Expiry rule** (#014). Stock expiries fall on Tuesday, moved earlier
  for a holiday. A contract with expiry < today contributes zero to the
  baseline: physically settled, so its delta vanished passively.
  Consequence: rolling on or before expiry is permitted; re-entering the
  day after is a breach.
- **Prop book against SEBI 2025/79 Table 2.** Positions per contract;
  FutEq delta in shares from NSE's Contract_Delta factors, no prices.
  Review found six issues, all fixed: silent blank-row skips, float
  arithmetic (now Decimal, exact), lost docstring names, strike parsing,
  duplicated loaders, and the expiry-day crash.

## 8 Nov 2026 (Sun)

- **Flat day as a marker row** (#015). A FLAT row stating the date is the
  only way to get an empty book (PropBook.flat). A missing file is never
  a book, so it can't pass as flat; `books[day]` raises instead.
- **check_ban_period_reduction(), written twice.** First version got
  every Table 2 verdict right but had three faults: a false claim that
  per-UCC checks dominate entity checks, None hiding a missing file, and
  no check that yesterday was the previous trading day. Rewritten with
  required books, the calendar check, both band limits in rules.yaml,
  and readable reasons. Muhurat fails closed through the calendar.
- **Row 7 walk: five decisions** (#016). Cat II split into two named
  categories (NSE FAQ 15 files Cat II corporates at the wrong limit);
  net within UCC, gross across UCCs (inference; four sources, the fourth
  contradicted, doubts.md 12); the
  function aggregates, not the caller; an MWPL-driven breach is reported
  with cause PASSIVE; every check returned with excess in shares.
- **Reference tables.** Holders (with category) and accounts (keyed
  (tm, ucc)), date-effective, with cross-table invariants.
- **Positions keyed on (tm, ucc).** Each broker numbers its own clients,
  so C001 at two brokers is two people. Row 6 now checks per account.

## 9 Nov 2026 (Mon)

- **Muhurat chains** (#013 addendum). Sunday 8 Nov was a real session:
  FutEq OI moved on 218/218 scrips with MWPL unchanged, and NSE ran a
  full end-of-day cycle. Recorded as a calendar row sourced to the two
  Sunday files and their checksums, marked as an observation, not a
  circular. Added the "verified, does not chain" state for future use.
- **SAIL scored.** 3241/3241 scrip-days agree; 8 of 8 transitions
  correct (3 entries, 5 releases). 101 scrip-days closed inside the
  80–95% band: 27 held (already banned), 74 stayed out (already free),
  all correct. A "never banned" model would score 99.04%.
  SAIL: 80.51% on 4 Nov and held; 79.52% on 5 Nov and released for
  6 Nov; 82.79% on 6 Nov and stayed out.
- **SAIL fixtures in CI** (#017). Both in-band cases in one stock.
- **Scope decision.** Pipeline runner before row 7; v0.1 scope cut.

**Next:** close the day (LEARNING.md, interview questions), then the
runner walk; build the runner on Tue 10 Nov; tag v0.1 on Wed 11 Nov.

**Still untested on real data:** a scrip exactly on 95.00% or 80.00%,
a missing prior state, and a new scrip near a line.

## 10 Nov 2026 (Tue)

- **NSE content out of the repository** (#010 addendum). The NSE fixtures
  are replaced by a builder (`scripts/build_nse_fixtures.py`), a hash
  manifest (`tests/fixtures/nse_built.sha256`) and a synthetic window that
  CI runs instead. The real-data tests build from `data/` and skip without it.
- **The old fixtures were near-copies, not copies.** The transitions rows
  had six FutEq values that had been through a float and back: equal to
  NSE's as numbers, different in the last digit as strings. The parser
  sample ended its last line with a hand-typed LF where NSE writes CRLF.
  Both parsed to the same rows. The builder now writes NSE's exact bytes,
  and the manifest records those, so a fixture can no longer drift from
  its source without a hash failing.
- **The pipeline runner** (#019, `ee07d83`). `python -m sentinel.runner D`
  runs a day end to end and exits 0 COMPLETED, 2 REFUSED, 1 FAILED. The
  whole run refuses on a holiday, an unknown date, an excluded or
  unverified special session, a missing combineoi_D, or an unresolved
  banned symbol. Everything else refuses only the stage that needs the
  missing input. Three new rules, #019 items 13-15: an unverified next
  day refuses only the forecast; an unresolved banned symbol refuses the
  whole run, as ingest does; an excluded special session refuses the run.
  Retries are dropped, item 12: there is no downloader.
- **The store records each run's rules status** (`726d645`): the assumed
  and unverified rule keys, for the report footer. Running my runner tests
  against the store found a bug in it: the ban-state guard needed the next
  trading day even to store D's own official state, so item 13 crashed.
  The guard now asks the calendar only for a forecast.
- **Tested.** Ten runner tests, nine of them on the synthetic window in CI.
  Six mutations, all caught, after the holiday test was fixed to check why
  it refused. CI on Linux: 398 passed, 33 skipped, including the held-lock
  refusal, the first run of the lock's Linux branch through the runner.
  Locally: 431 passed, including 4 Nov on the real files and its rerun.
- **Acquisition ruled out** (#010 addendum). NSE's terms forbid automated
  collection, so v1.0 gets an importer, not a downloader. A filtered public
  copy of the repository is built and scans clean; it waits for the v0.1 tag.

- **The daily report** (`2bf2e6f`, `c61c92c`). `python -m sentinel.report D`
  renders the day from the store and the run log only, in #019's order. A
  refused section says "Refused", never zero. Claude built the layout around
  two functions I wrote: `flag_disagreements()` and `watchlist()`. Eleven
  mutations to them, all caught, after three gaps in my first tests (a
  truncated headroom, swapped flags, symbol order) were fixed.
- **v0.1 shipped, a day early.** The README leads with the score, says what
  is still untested, and calls the prop book a test harness. Two sample
  reports are rendered from the synthetic window, never a real day. Tagged
  `v0.1` privately at `726c875`.
- **Public:** github.com/Negotiator-10/futeq-sentinel-public. A filtered copy
  of this repository, with no NSE content in any commit, and my author email
  mapped to my GitHub noreply address. Its CI badge points at its own
  workflow, and the sample footers carry the public hash. The full scan is
  clean, and CI passed on its first run: 426 passed, 33 skipped.

**Next:** Wed 11 Nov, the Week 2 teach-back, and v0.1 in the Citco,
JPMorgan and Anand Rathi applications. Thu 12 Nov, before any Week 3 code:
how many days I will download by hand for the replay, and the scope cuts.

## 11 Nov 2026 (Wed)

- **Week 2 teach-back:** 5 of 7 right, 2 partly (the signed [0, 1) test, and
  MWPL as the limit, not the exposure). Q7 closes the delta gap on the gaps list.
- **The replay decision** (#020): every session from 1 Oct 2025, downloaded by
  hand. The first file is already on the FutEq basis (207 of 207). Cut: the
  live page, OTR, the index rows (SPEC 8, 9, 10, 13, 14, 16) and row 15.
- **546 files downloaded by hand,** checked month by month and recorded in
  `docs/data_manifest.csv`. The calendar now covers 2025 (NSE/FAOP/65588),
  with the 2025 Muhurat session verified as chaining from its own files, and
  15 Jan 2026 as an election holiday (NSE/FAOP/72262) - the replay found it
  first, as a weekday with no files.
- **The replay:** 56,997 of 56,997 scrip-days; 90 of 90 transitions; 1,130
  in-band scrip-days all correct; 273 of 273 runner sessions COMPLETED. MWPL
  resets observed on the first trading day of all four quarters.
- **It found a bug of mine:** FutEq OI as a float put one whole-number headroom
  4e-9 below NSE's. Fixed by keeping it as an exact Decimal from the parser on
  (`ef23129`). A second trap came with it: a Decimal compared with the float
  0.95 would have banned a scrip exactly on 95%. Both pinned by tests.
- **And one real disagreement:** TRENT on 3 Jun 2026, one share less headroom
  than the formula. Safe direction, cause not visible. Kept failing, on purpose.
- **Written up** in the README and READING.md.

**Next:** record the reset calendar in `config/rules.yaml` as observed, from
the eight files either side of each reset. Then Week 3: deltas, FutEq and MWPL
computed by me rather than read as published, and row 7.
