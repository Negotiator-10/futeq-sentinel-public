# MWPL and utilisation, worked by hand

Companion to `mwpl_by_hand.xlsx` and `mwpl_by_hand.csv`. The spreadsheet is where I do the
arithmetic; this file holds the same numbers in plain text, because git cannot diff an .xlsx and
pytest needs these as literals. The CSV is the diffable export of the same sheet, formulas included.

Source for every formula: SEBI/HO/MRD/TPD-1/P/CIR/2025/79, paragraph 5.2.
Worked from memory on 1 Nov 2026 and checked against the answer sheet. Every value cell is a
formula referencing an input cell, so changing an input moves every number below it.

## Stock 1: a liquid large-cap

### Inputs
| Item | Value | Unit | Source |
|---|---|---|---|
| Stock | RELIANCE | | illustrative only, not real NSE data |
| Free float | 1,000,000,000 | shares | assumed |
| Average daily delivery value (ADDV) | 500,000,000 | INR per day | assumed |
| Share price | 1,000 | INR per share | assumed |
| Lot size | 250 | shares per lot | assumed |
| Market FutEq OI today | 19,500,000 | shares | assumed |

### Calculation
| Step | Formula in words | Result | Unit |
|---|---|---|---|
| Quantity 1 | 15% of free float | 150,000,000 | shares |
| Quantity 2 | 65 × ADDV | 32,500,000,000 | INR |
| Unit reconciliation | Quantity 2 ÷ share price | 32,500,000 | shares |
| MWPL before the floor | lower of the two, in shares | 32,500,000 | shares |
| Floor check | 10% of free float | 100,000,000 | shares |
| Which one binds, and why | the floor, because 65 × ADDV collapses to 32.5m shares — delivery is thin relative to this float | | |
| **MWPL** | higher of (lower-of-two, floor) | **100,000,000** | shares |
| **Utilisation** | market FutEq OI / MWPL | **19.5%** | % |

Miss the floor and every number below it is wrong by 3×: utilisation reads 60% instead of 19.5%,
and headroom reads 45,500 lots instead of 302,000.

### Ban scenarios, solved backwards
| Question | Answer | Unit |
|---|---|---|
| FutEq OI that puts the stock exactly at the ban entry threshold (95%) | 95,000,000 | shares |
| FutEq OI at which it would be released (80%) | 80,000,000 | shares |
| Headroom from today's OI to the entry threshold | 75,500,000 | shares |
| The same headroom expressed in lots | 302,000 | lots |

The 95% entry is cited at 2025/79 para 5.2.6 and 5.3.1. The 80% exit is **not** in para 5.2 or 5.3
and is still unverified — see the open row in `TASKS.md`.

## Open question for the engine
Para 5.2.3 compares 15% of free float (a share count) with 65 × ADDV (a rupee value) but does not
say which price to convert at. I used the current share price. The circular does not settle it, so
`compute_mwpl()` must take the price as an explicit, documented argument rather than assume one.

## Stock 2: an illiquid mid-cap
Not done yet. The point of a second stock is to see a *different* limb bind. Worth choosing the
inputs deliberately: free-float market cap divided by ADDV gives a number of days, and that single
ratio decides which of the three limbs wins. Stock 1 sits at 2,000 days.

## What I learned
- Which quantity binds for a liquid stock, and which for an illiquid one:
- The unit mistake I nearly made:
- Why the headroom figure in lots is the one a trader actually wants:

## These become test cases
On W1 D6 and W3 D2 the engine must reproduce the MWPL and utilisation figures above from the same
inputs. Any difference is a bug in the code, not in this sheet.

```
free_float = 1_000_000_000      # shares
share_price = 1_000             # INR
addv = 500_000_000              # INR per day
lot_size = 250                  # shares
market_futeq_oi = 19_500_000    # shares

assert compute_mwpl(...) == 100_000_000
assert utilisation(...) == 0.195
assert headroom_lots(...) == 302_000
```
