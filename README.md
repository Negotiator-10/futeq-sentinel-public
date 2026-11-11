# FutEq Sentinel

[![tests](https://github.com/Negotiator-10/futeq-sentinel-public/actions/workflows/tests.yml/badge.svg)](https://github.com/Negotiator-10/futeq-sentinel-public/actions/workflows/tests.yml)

I read SEBI's and NSE's rules on F&O position limits and ban periods, worked out the
calculations by hand from the circulars, implemented them, and then checked the result against
NSE's own published output.

The checking is the point. Anyone can write a script that reads an exchange file. What I wanted
to know was whether my reading of the regulation was right, and the only honest way to find out
was to reproduce numbers NSE publishes independently and see where I disagreed.

Status: v0.1, and a replay of every session since 1 Oct 2025. One command runs a trading day end
to end and a second renders that day's report from what the run stored. "What it does not do yet", below, is the accurate summary of the rest.
Release dates live in `PLAN.md` and I have deliberately not repeated them here — a date in two
files is a date that goes stale in one of them, which has already happened once in this one.

The prop book is a test harness: synthetic positions that exist only to check the compliance
logic against the rules. It is not a trading or simulation system and holds no one's real
positions. Nothing here is investment advice, and no orders are sent anywhere.

## What it reproduces, and how closely

**A year of NSE's ban decisions, reproduced.** For every session from 1 Oct 2025 to 9 Nov 2026,
the engine takes NSE's published ban list for that day as the prior state, that day's utilisation
as the measurement, and forecasts the next session's list. The answer is NSE's published list for
that session. It never reads NSE's own next-day flag, which would be the answer fed in.

| 1 Oct 2025 to 9 Nov 2026 | |
|---|---|
| Sessions | 273, two of them Muhurat sessions; 272 forecasts scored (the last answer is not published yet) |
| Scrip-days agreeing | **56,997 of 56,997** |
| Ban transitions forecast correctly | **90 of 90**: 45 entries and 45 releases |
| Scrip-days inside the 80–95% band | **1,130**: 342 held, 788 stayed out, all correct |
| Ban episodes | 46, across 11 stocks; 428 banned scrip-days |

**Read the last three rows, not the first.** Almost every scrip-day is a security nowhere near
either line staying there, so a model answering "never banned" would score 99.25% on the same
data. What tests the logic is the 90 days a scrip actually entered or left a ban, and the 1,130
scrip-days that closed inside the band, where the right answer depends only on whether the scrip
was in ban the day before. A single line at 95% would get the 342 held ones wrong; a single line
at 80% would get the 788 that stayed out wrong.

SAIL shows both in one week. It closed at 80.51% on 4 November while in ban and was held; it
closed at 82.79% on 6 November, higher, after its release, and stayed out. It was also the year's
most-banned stock - in ban for 133 of the 273 sessions, over 10 episodes - and held the longest
single ban, 29 sessions from 27 August to 8 October 2026.

**SAIL on 15 October is the row I would put in front of anyone.** At the previous close its
futures-equivalent open interest was 95.0135% of its MWPL: **29,360 shares** past the line on a
limit of 217 million, one part in seven thousand. NSE banned it. Paragraph 5.2.6 of SEBI 2025/79
says a ban applies when open interest *exceeds* 95%, so the comparison is strictly greater and a
scrip sitting exactly on 95% is not in ban. I wrote that down on 1 November because of one word
in a circular. In a year of real data, nothing came closer to testing it.

**Ban-period headroom, reconciled every session.** NSE publishes a `Limit for Next Day` figure
per security. I derived `0.95 × MWPL − FutEq OI` by hand from paragraphs 5.2.3 and 5.2.6, four
days before I had the file. Over the year it matches NSE's figure on **56,786 of 56,787** rows.
Against notional open interest it matches 22, which is coincidence: NSE computes on the
futures-equivalent basis.

The test is that my exact figure minus NSE's lies in `[0, 1)`. That is not a tolerance - it is
the same statement as "truncating mine gives theirs", so it is an exact test of a truncation
hypothesis. It is signed rather than absolute on purpose: NSE publishing *more* headroom than the
formula allows is a trading risk, publishing less only costs opportunity, and an absolute test
would not notice the difference.

**The one disagreement: TRENT, 3 June 2026.** NSE published one share *less* headroom than
truncating the formula gives. It is in the safe direction, and its cause cannot be determined
from the published file. I record it as a known exception and keep the check failing on it;
widening `[0, 1)` to make it pass would throw away the one real finding. One disagreement in
56,787 rows, named, is the result.

**The replay also found a bug of mine.** On five rows the exact headroom is a whole number and NSE
publishes exactly it. On one of them, float arithmetic put mine four billionths of a share below,
which fails `[0, 1)` on a correct row. FutEq OI is now kept as the exact published decimal from the parser
onwards, and a float is refused.

**MWPL resets, observed in the data.** The limits change overnight on the first trading day of
each quarter - 1 January, 1 April, 1 July and 1 October 2026 - for about three-quarters of
scrips, and hold still in between. The circular says only "quarterly", so `config/rules.yaml`
still marks the reset months as an assumption; recording this observation there, with the eight
files either side of each reset as its source, is the next step.

## What it does not do yet

Stated plainly, because the thing above is the only claim I want read as finished.

* **The prop book is checked against one rule of four.** The book itself exists - positions
  keyed on the account `(tm, ucc)`, with a written-down marker for a flat day - and SPEC row 6,
  that trading in a banned scrip must reduce FutEq OI, is checked and reproduces SEBI's own
  worked example. It has run on synthetic books only, never a real one. Row 7, the entity
  limits, has its holder and account reference tables but not the check itself.
* **Not covered, by decision (`DECISIONS.md` #020).** The index-derivative limits - SPEC rows 8,
  9, 10, 13, 14 and 16, for index options and futures at end of day and intraday - are specified
  in `SPEC.md` and `config/rules.yaml` and not written. Row 15, intraday MWPL monitoring for
  single stocks, is out too: it needs intraday positions, and every file here is end of day. The
  order-to-trade ratio module and a live forecast page are cut as well. The time went to a
  replay of every trading day since 1 Oct 2025.
* **It is a reconciliation, not a forecast with a time advantage.** NSE publishes its own
  next-day ban determination in the same file the engine computes from, so there is no lead of
  any size. What this does is reproduce the exchange's determination independently and reconcile
  against it. That is narrower than "forecasting", and it is deliberately the word I use.
* **Neither boundary has been tested at the boundary on real data.** In a year, no real row sat
  exactly on 95% or 80%. The closest to entry was SAIL, 0.0135 points over 95%; the closest
  banned scrip to the exit was 0.14 points above 80%, and held; the closest release came from
  0.21 points below. The inclusivity — strict at entry, inclusive at exit — is tested end to end
  on synthetic files with made-up scrips placed exactly on each line, through the same parsers,
  engine and runner. That is a test of my code, not evidence from NSE, and the real data may
  never provide it.
* **A missing prior state has only been run on synthetic files.** Every real scored day had its
  seed. The runner's handling of a missing ban list — refusing only the in-band forecasts, D-1's
  score and row 6 — is tested on the synthetic window, not on a real gap.
* **Row 6 has never run inside a real day.** The runner has run every one of the 273 sessions,
  and on each row 6 refuses: there is no prop book and no `Contract_Delta` file. The report says
  "Refused", not "0 breaches".
* **Acquisition is manual, and will stay manual.** NSE's terms of use (para 9) prohibit systematic
  or automated data collection, and the main site offers no consent route, so I download every
  file by hand and record its checksum. v1.0 adds an importer that checks what I download; there
  will be no downloader (`DECISIONS.md` #010 addendum). NSE's files never enter this repository,
  not even as test fixtures.
* **Special sessions chain only on evidence.** Muhurat trading on Sunday 8 November 2026 is a
  session on a day that is not a normal trading day. The calendar refused to chain through it
  until 9 November, when NSE's own Sunday files showed a full end-of-day cycle; it is now
  recorded as chaining, sourced to those files and their checksums rather than to a circular
  (#013 addendum). Any other special session refuses until it has a verdict of its own.

## Running it

Python 3.12.

```
pip install -e ".[dev]"
pytest                        # 475 tests; 34 skip without NSE's files in data/
python scripts/score_bans.py  # reproduces the full score from the files in data/
```

The install is for the dependencies and for `pytest`; neither command needs the package
installed to import it, because `pyproject.toml` puts `src` on the path for `pytest` and the
script adds it itself.

`score_bans.py` exits 0 and explains itself when `data/` is absent, since the raw files are
gitignored. NSE's files are never committed, not even as test fixtures (`DECISIONS.md` #010
addendum). On every push, CI runs the ban rule end to end on synthetic files in NSE's layouts,
`tests/test_synthetic_window.py`: made-up scrips placed exactly on each boundary and inside the
band in both states. The real-data tests - all eight transitions, and SAIL's walk out of the ban
from 2 to 6 November with both in-band cases on one stock (held at 80.51%, kept out at 82.79%) -
build their fixtures from `data/` with `scripts/build_nse_fixtures.py`, check every file against
`tests/fixtures/nse_built.sha256`, and skip when the files are absent.

**Commits before 10 Nov 2026 won't run their tests.** The public repository's history was
filtered to remove NSE's files, so those commits refer to fixtures that are no longer in it.
Filtering also rewrote every commit hash, so a hash quoted inside a file - in `progress.md`, for
instance - is the private record's, not the public repository's.

## Running a day

```
python -m sentinel.runner 2026-11-04    # exit 0 COMPLETED, 2 REFUSED, 1 FAILED
python -m sentinel.report 2026-11-04    # writes reports/2026-11-04.md from the store
```

The runner reads that day's files from `data/`, computes the whole day in memory and writes it to
the store in one transaction: NSE's measurements, the reconciliation, the day's official ban
state, the forecast for the next trading day, and row 6. A crash leaves nothing of the day
behind. A run log outside that transaction records every run — its input checksums, the commit
and whether the working tree was clean, the rules and calendar checksums, and which rules it used
on an assumption — so even a failed run says what it was and why it failed.

It refuses rather than guesses. The whole run refuses on a holiday, an unknown date, an unverified
special session, a missing `combineoi` file, or a banned symbol it cannot resolve. A missing ban
list refuses only what depends on it, and the rest of the day still runs. Every refusal is stored
with its reason, so "refused" and "not run" are never the same record.

The report is rendered from the store and the run log alone, in a fixed order: refusals, where
the engine disagrees with NSE's own flag, row 6 breaches, tomorrow's ban, the 80–95% watchlist
with each scrip's distance to the line that applies to it, the checks that passed, and an audit
footer. A refused section says "Refused" and why. A run from uncommitted code is marked "not
reproducible".

Two sample reports are in `docs/sample_reports/`: an ordinary day, and a day whose ban list is
missing. Both are rendered from the synthetic window by `scripts/render_sample_reports.py`, never
from a real day, because a real report quotes NSE's own figures and NSE's content stays out of
this repository.

## How it is put together

| | |
|---|---|
| `src/sentinel/parsers.py` | reads NSE's files, computes nothing |
| `src/sentinel/rules.py` | loads every threshold with its source, and refuses the ones the circulars leave to the exchange |
| `src/sentinel/calendar.py` | which dates NSE traded on, with `UNKNOWN` as a state rather than an assumption |
| `src/sentinel/engine.py` | utilisation, headroom, ban state, reconciliation |
| `src/sentinel/store.py` | point-in-time ban state, keyed on ISIN and date |
| `src/sentinel/ingest.py` | loads published files into the store; a re-run is a no-op |
| `src/sentinel/book.py` | the synthetic prop book: positions keyed on `(tm, ucc)`, and a flat day as a marker row |
| `src/sentinel/entities.py` | who holds which account, date-effective, for the entity limits |
| `src/sentinel/runlock.py` | one run at a time, with a lock the operating system releases if the run dies |
| `src/sentinel/runner.py` | one trading day end to end, in one transaction, refusing per stage |
| `src/sentinel/report.py` | the day's report, rendered from the store and the run log only |

Two conventions run through all of it.

**No threshold is written in the code.** Every number and every comparison direction comes from
`config/rules.yaml`, where each entry carries its circular, paragraph and the date I read it.
Three states rather than two: verified, assumed, and unverified — and the loader refuses to
evaluate an unverified one rather than supplying a plausible number. The ban entry threshold is
`0.95` with operator `>`; the exit is `0.80` with operator `<=`; neither direction appears in a
Python file.

**The engine's own output is never read back as an input.** Ban status is a latching state, not a
measurement: a wrongly seeded flag does not decay toward the truth. Replaying the same
utilisation path from two different seeds, the two disagree on 20 of 20 days. So the store keeps
the engine's forecast and NSE's published state side by side and only the published one is ever
read forward — enforced by the API, which has no method that returns a forecast as a prior state.

## Where the reasoning is written down

* `SPEC.md` — sixteen rule rows, each with its circular, paragraph, function name and named test
  case. Rows marked `UNVERIFIED` are ones I could not confirm against a primary source.
* `DECISIONS.md` — nineteen decisions, each with what, why, evidence, the alternatives rejected
  and the outcome. #011 is why ban state needs yesterday's answer; #012 is the store; #013 is the
  calendar; #019 is the runner; the #010 addendum is why acquisition stays manual.
* `docs/READING.md` — every source, every downloaded file with its sha256, and the file-format
  traps.
* `LEARNING.md` — what I got wrong and what it taught me, including the first version of the
  score above, which agreed with NSE on all 218 scrips and was worthless because the seed came
  from the column being predicted.
