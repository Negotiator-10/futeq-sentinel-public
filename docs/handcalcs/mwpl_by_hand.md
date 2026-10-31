# MWPL and utilisation, worked by hand

Companion to `mwpl_by_hand.xlsx`. The spreadsheet is where I do the arithmetic; this file holds the
same numbers in plain text, because git cannot diff an .xlsx and pytest needs these as literals.

Source for every formula: SEBI/HO/MRD/TPD-1/P/CIR/2025/79, paragraph 5.2.

## Stock 1: a liquid large-cap

### Inputs
| Item | Value | Unit | Source |
|---|---|---|---|
| Stock | | | |
| Quantity 1 input (per 5.2) | | | assumed |
| Quantity 2 input (per 5.2) | | | assumed |
| Share price | | INR | assumed |
| Lot size | | shares | assumed |
| Market FutEq OI today | | | assumed |

### Calculation
| Step | Formula in words | Result | Unit |
|---|---|---|---|
| Quantity 1 | | | |
| Quantity 2 | | | |
| Which one binds, and why | | | |
| Floor check | | | |
| **MWPL** | | | |
| **Utilisation** | market FutEq OI / MWPL | | % |

### Ban scenarios, solved backwards
| Question | Answer | Unit |
|---|---|---|
| FutEq OI that puts the stock exactly at the ban entry threshold | | |
| FutEq OI at which it would be released | | |
| Headroom from today's OI to the entry threshold | | |
| The same headroom expressed in lots | | lots |

## Stock 2: an illiquid mid-cap
Same layout. The point of doing a second stock is to see whether the *other* quantity binds.

### Inputs
| Item | Value | Unit | Source |
|---|---|---|---|
| Stock | | | |
| Quantity 1 input (per 5.2) | | | assumed |
| Quantity 2 input (per 5.2) | | | assumed |
| Share price | | INR | assumed |
| Lot size | | shares | assumed |
| Market FutEq OI today | | | assumed |

### Calculation
| Step | Result | Unit |
|---|---|---|
| Quantity 1 | | |
| Quantity 2 | | |
| Which one binds | | |
| **MWPL** | | |
| **Utilisation** | | % |

## What I learned
- Which quantity binds for a liquid stock, and which for an illiquid one:
- The unit mistake I nearly made:
- Why the headroom figure in lots is the one a trader actually wants:

## These become test cases
On W1 D6 and W3 D2 the engine must reproduce the MWPL and utilisation figures above from the same
inputs. Any difference is a bug in the code, not in this sheet.
