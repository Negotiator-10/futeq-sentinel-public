# FutEq Sentinel

[![tests](https://github.com/Negotiator-10/futeq-sentinel-public/actions/workflows/tests.yml/badge.svg)](https://github.com/Negotiator-10/futeq-sentinel-public/actions/workflows/tests.yml)

I read SEBI's and NSE's rules on F&O position limits and ban periods, worked out the
calculations by hand from the circulars, implemented them, and then checked the result against
NSE's own published output.

The checking is the point. Anyone can write a script that reads an exchange file. What I wanted
to know was whether my reading of the regulation was right, and the only honest way to find out
was to reproduce numbers NSE publishes independently and see where I disagreed.

Status: in progress. "What it does not do yet", below, is the accurate summary. Release dates
live in `PLAN.md` and I have deliberately not repeated them here — a date in two files is a date
that goes stale in one of them, which has already happened once in this one.

All positions are synthetic. Nothing here is investment advice, and no orders are sent anywhere.

## What it reproduces, and how closely

**Ban-period forecasts, scored against NSE's own published ban list.** For each trading day the
engine takes NSE's published ban list for that day as the prior state, that day's utilisation as
the measurement, and forecasts the next trading day's ban list. The answer is NSE's published
list for that day.

| | |
|---|---|
| Scrip-days agreeing, 12 Oct to 9 Nov 2026 | **3241 of 3241** |
| False positives | 0 |
| False negatives | 0 |
| Ban transitions in the sample | **8** — 3 entries, 5 releases |
| Transitions forecast correctly | 8 |
| Scrip-days inside the 80–95% band | **101** — 27 held, 74 stayed out, all correct |

**Read the last two numbers, not the first.** Almost all of those 3241 scrip-days are a security
nowhere near either threshold staying nowhere near it, so a model answering "never banned" would
score 99.04% on the same data. The numbers that test the logic are the **eight** days a scrip
actually entered or left a ban, and the **101** scrip-days that closed inside the band, where the
right answer depends only on whether the scrip was in ban the day before. A single line at 95%
would get the 27 held ones wrong; a single line at 80% would get the 74 that stayed out wrong.

SAIL shows both in one week. It closed at 80.51% on 4 November while in ban and was held; it
closed at 82.79% on 6 November, higher, after its release, and stayed out.

The eight transitions, with the utilisation at the prior close:

| Effective | Symbol | Direction | Utilisation |
|---|---|---|---|
| 13 Oct 2026 | KAYNES | entry | 97.98% |
| 14 Oct 2026 | BANDHANBNK | release | 79.41% |
| 14 Oct 2026 | LICHSGFIN | release | 78.82% |
| 15 Oct 2026 | SAIL | entry | 95.01% |
| 28 Oct 2026 | AMBUJACEM | release | 70.02% |
| 28 Oct 2026 | KAYNES | release | 66.96% |
| 29 Oct 2026 | KAYNES | entry | 95.67% |
| 6 Nov 2026 | SAIL | release | 79.52% |

Three entries all just above the 95% line, five releases all at or below 80%, and nothing in the
fifteen points between — the hysteresis band, empty of transitions.

**SAIL on 15 October is the row I would put in front of anyone.** At the previous close its
futures-equivalent open interest was 95.0135% of its MWPL: **29,360 shares** past the line on a limit of 217 million, one part in seven
thousand. NSE banned it. Paragraph 5.2.6 of SEBI 2025/79 says a ban applies when open interest
*exceeds* 95%, so the comparison is strictly greater and a scrip sitting exactly on 95% is not in
ban. I wrote that down on 1 November because of one word in a circular; two weeks of real data
put a stock 0.0135 of a percentage point from testing it.

**Ban-period headroom, reconciled against NSE's published column.** NSE publishes a
`Limit for Next Day` figure per security. I derived `0.95 × MWPL − FutEq OI` by hand from
paragraphs 5.2.3 and 5.2.6, four days before I had the file, and it matches on **216 of 216**
rows. Against notional open interest it matches 0 of 216, which settles that NSE computes on the
futures-equivalent basis.

Exact equality matches on **zero** of 216 rows, because NSE truncates to whole shares and the
engine keeps the decimals. The test is that the residual lies in `[0, 1)`, which is not a
tolerance — it is the same statement as "truncating mine gives theirs", so it is an exact test of
a truncation hypothesis. It is signed rather than absolute on purpose: NSE publishing *more*
headroom than the formula allows is a trading risk, publishing less only costs opportunity, and
an absolute test would not notice the difference.

## What it does not do yet

Stated plainly, because the thing above is the only claim I want read as finished.

* **The prop book is checked against one rule of four.** The book itself exists - positions
  keyed on the account `(tm, ucc)`, with a written-down marker for a flat day - and SPEC row 6,
  that trading in a banned scrip must reduce FutEq OI, is checked and reproduces SEBI's own
  worked example. It has run on synthetic books only, never a real one. Row 7, the entity
  limits, has its holder and account reference tables but not the check itself. Rows 8 to 10,
  the index-option limits at end of day and intraday, are specified in `config/rules.yaml` and
  not written.
* **It is a reconciliation, not a forecast with a time advantage.** NSE publishes its own
  next-day ban determination in the same file the engine computes from, so there is no lead of
  any size. What this does is reproduce the exchange's determination independently and reconcile
  against it. That is narrower than "forecasting", and it is deliberately the word I use.
* **Neither boundary has been tested at the boundary.** 95.01% is not 95.00%, and no row in the
  sample has sat exactly on 95% or 80%. The inclusivity — strict at entry, inclusive at exit — is
  proven by unit tests, not by data, and may never be provable by data.
* **No run has been made with a missing prior state.** Every scored day had its seed.
* **Acquisition is manual.** NSE returns 403 to a plain HTTP client and tarpits its archive
  paths, so every file in this repository's `data/` was downloaded by hand with its checksum
  recorded. There is no downloader yet (`DECISIONS.md` #010).
* **Special sessions chain only on evidence.** Muhurat trading on Sunday 8 November 2026 is a
  session on a day that is not a normal trading day. The calendar refused to chain through it
  until 9 November, when NSE's own Sunday files showed a full end-of-day cycle; it is now
  recorded as chaining, sourced to those files and their checksums rather than to a circular
  (#013 addendum). Any other special session refuses until it has a verdict of its own.

## Running it

Python 3.12.

```
pip install -e ".[dev]"
pytest                        # 410 tests; 32 skip without NSE's files in data/
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

## How it is put together

| | |
|---|---|
| `src/sentinel/parsers.py` | reads NSE's files, computes nothing |
| `src/sentinel/rules.py` | loads every threshold with its source, and refuses the ones the circulars leave to the exchange |
| `src/sentinel/calendar.py` | which dates NSE traded on, with `UNKNOWN` as a state rather than an assumption |
| `src/sentinel/engine.py` | utilisation, headroom, ban state, reconciliation |
| `src/sentinel/store.py` | point-in-time ban state, keyed on ISIN and date |
| `src/sentinel/ingest.py` | loads published files into the store; a re-run is a no-op |

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
* `DECISIONS.md` — thirteen decisions, each with what, why, evidence, the alternatives rejected
  and the outcome. #011 is why ban state needs yesterday's answer; #012 is the store; #013 is the
  calendar.
* `docs/READING.md` — every source, every downloaded file with its sha256, and the file-format
  traps.
* `LEARNING.md` — what I got wrong and what it taught me, including the first version of the
  score above, which agreed with NSE on all 218 scrips and was worthless because the seed came
  from the column being predicted.
