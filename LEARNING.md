# Learning log

Write a few lines after every session, in your own words.

Template:

```
## YYYY-MM-DD (Week N, Day)
- What I learned:
- What confused me:
- Interview questions I couldn't answer well yet:
- What I'd do differently:
```

## 2026-11-05 (Week 1 D4 to Week 2 D1, written at the end of 2 to 5 Nov)

*Drafted by Claude from what actually happened over these four days, because I kept deferring
this file and the material was going stale. The facts and the lessons are observed, not
invented - every one has a commit or a file behind it. The two slots Claude cannot fill are
marked. I should rewrite this in my own words; a learning log in someone else's voice is not
a learning log.*

### What I learned

**1. The dangerous errors are the ones that still run.** I filled fifty thresholds into
`config/rules.yaml` and got the encoding wrong in five repeated ways. Four of them broke
loudly - the file would not even parse. The fifth was `minutes_in_year: 8,670`, which is the
minutes-to-expiry from NSE's worked example, the *numerator* of T, where the denominator
525,600 belongs. That one would have run. It would have made T come out at 1.0 instead of
0.0165 and corrupted every option delta by about sixty times, producing output
indistinguishable from correct output. This is the whole argument for the config file and the
validated loader - not tidiness, but that a wrong number which still computes is worse than
one that crashes.

**2. Deriving a rule from the source and having the exchange's own file agree with it.** I
worked out MWPL headroom by hand in a spreadsheet from para 5.2.3 and 5.2.6: ban entry is at
95% of MWPL, so headroom is `0.95 x MWPL - FutEq OI`. Four days later I downloaded
`combineoi_30102026.csv` and its `Limit for Next Day` column matched my formula **exactly on
216 of 216 rows**, median residual half a share. It did not reconcile against notional OI at
all - 0 of 216 - which settled a question I had not been able to answer from the circular:
NSE computes on the futures-equivalent basis, not the notional one.

**3. A rule you cannot see in today's data.** On 30 Oct, SAIL was flagged `No Fresh Positions`
at **84.93%** utilisation while BANDHANBNK traded freely at **85.98%**. Neither is near 95%.
So ban status is not a function of today's utilisation at all - and the lower one was the
banned one. Entry at 95% and exit at 80% make it a state, not a measurement, so
`is_in_ban()` needs yesterday's answer as an input. I had reasoned that from the clause the
day before and written it into `SPEC.md` row 5. The data proved it.

**4. Latching state versus decaying state, and the test that tells them apart.** My first
answer to "how does day one get its state" was to start from a fixed date and replay forward -
which is correct in my VaR engine, where a wrongly seeded GARCH variance decays toward the
truth. A wrongly seeded ban flag does not decay; it latches. Run the same utilisation path
from both seeds and the two disagree on **19 of 20 days**, agreeing on the twentieth only
because utilisation happened to fall below the 80% exit and overwrote both. The test, worth
keeping for any carried state I ever design: **run the same inputs from two different initial
states. Converge means the state decays and a warm-up is legitimate. Diverge means it latches
and must be seeded from an observation.**

**5. Sound reasoning aimed at the wrong system. Twice in one afternoon.** Question 3 of #011
got a warm-up replay from my VaR project. Question 4 got an order-blocking scope from an
OMS/RMS - and this engine never sees an order; it runs after the close on published files.
Both answers were well argued. Neither was about this system. **A good design for the wrong
system reads exactly like a good design**, which makes this the hardest class of error to
catch. Check which system you are designing for before checking whether the design is good.

**6. A library default can silently disarm a check I wrote on purpose.** `MwplRow` refuses a
row with no ISIN, which is #011's decision that indices are not stored. But `pd.read_csv`
treats the literal string `"NA"` as a missing value by default - exactly what NSE writes in the
ISIN column for an index - so `"NA"` became `NaN`, `str()` made it `"nan"`, and the guard never
fired. A test caught it, not me reading the code. Fixed with `keep_default_na=False` so the
parser reads what is in the file rather than pandas' interpretation of it.

**7. A rule enforced by a machine beats a rule I have to remember.** The CI gate I added fails
the build if anything under `data/`, any `.env`, PDF or archive is tracked in git. An hour
later it refused a zip fixture I was about to commit. I had been running that check by hand
before every commit for a week; it caught me the first time it had the chance.

**8. Validate where data enters; convert at the point of use.** `MwplRow.__post_init__`
enforces six invariants, so a contradictory row cannot be constructed. But converting to a
pandas DataFrame turns `None` into `NaN`, and pandas skips `NaN` silently - so a mean over 218
rows quietly becomes a mean over 216. The protection does not survive the boundary, which is
why the conversion is a named function carrying a warning rather than an inline comprehension.

### What confused me
<!-- MINE. Claude cannot write this one. Where did I actually get lost over these four days?
     Candidates from what happened: what a function signature is and what `->` means; what a
     parser is for; why `parse_ban_list()` is not the thing that decides whether a stock is
     banned. Say which, honestly - the point of this line is that next time I notice sooner. -->

### Interview questions I could not answer well yet
<!-- MINE. Claude cannot write this one either. Three or four, from this week's material.
     The ones I would currently struggle with are probably: why does FutEq OI beat counting
     contracts; which of MWPL's three limbs binds and why; what is the penalty counted per. -->

### What I would do differently

Ask for less. Over these four days I asked Claude to write `SPEC.md` rows 6 to 16, to rewrite
`config/rules.yaml`, to answer question 2 of #011, and to write this entry. Each request was
reasonable under time pressure and the cumulative effect is a repo ahead of plan and an owner
who has not written half of it. `CLAUDE.md` says to cut scope and never understanding, and the
debt has landed entirely in the category I wrote down as un-cuttable. The repayment blocks in
`#011` and `TASKS.md` exist to work it off.

Also: grep for the old number after every decision. Logging a decision in one file silently
rots the files that referenced the old answer. `SPEC.md` rows 4 and 5 contradicted `#011`
within a day, and `README.md` carried a release date that `DECISIONS.md` #006 had changed a
week earlier. The `rules.yaml` loader catches drift between `meta.unverified` and the tree;
nothing catches drift between the prose files.

## Gaps list
Questions from teach-backs that need more work. Strike them out once you can answer them
without notes.

- Why a delta-based measure beats counting contracts (Day 1 Q1, still unanswered)
- Which of MWPL's three limbs binds, and the single ratio that decides it (the three blank
  CHECKS rows in `docs/handcalcs/mwpl_by_hand.xlsx`)
- What the ban-period penalty is counted per, in all three dimensions (Day 1 Q6)
- Whether the Annexure 2 delta convention covers single stocks (`SPEC.md` row 11, UNVERIFIED)
