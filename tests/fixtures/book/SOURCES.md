# Provenance for `tests/fixtures/book/`

**These positions are synthetic.** They are SEBI's own illustration, not a real book, and
nothing in this repository reflects anyone's actual holdings.

`table2_positions.csv` and `table2_deltas.csv` reproduce **Table 2 of SEBI circular
SEBI/HO/MRD/TPD-1/P/CIR/2025/79, paragraph 5.3.3** — "Illustration of position creation during
ban period". The circular gives the positions and the verdicts but no numbers, so the lot size,
strikes, expiry and delta factors here are chosen to be legible: one scrip, a 1,000-share lot, a
single expiry, and factors that make the arithmetic readable by eye.

Dates are real trading days from `config/calendar_2026.csv`, so the fixture can be walked with
`TradingCalendar.next_trading_day()`.

| Day | Date | Holdings | FutEq delta | Baseline | Circular's verdict |
|---|---|---|---|---|---|
| 1 | 12 Oct 2026 | +1 FUT | 1000 | — | entry day; any decrease to 0 permitted |
| 2 | 13 Oct 2026 | +1 FUT | 1000 | 1000 | permitted (passive) |
| 3 | 14 Oct 2026 | +1 FUT, +1 PE | 600 | 1000 | permitted (long put reduces delta) |
| 4 | 15 Oct 2026 | +1 FUT, +1 PE, −1 CE | 250 | 600 | permitted (short call reduces further) |
| 5 | 16 Oct 2026 | +2 FUT, +1 PE, −1 CE | 1250 | 250 | **not permitted** (delta created) |

Baseline is yesterday's holdings valued at today's delta factors, which is the comparison para
5.3.2 implies: the passive part of a day's change is the market moving positions already held,
and only the active part can breach.

## Two days that are not in the circular

**19 and 21 October are mine, not SEBI's.** They hold exactly the positions of day 5 and differ
only in the put's delta factor, which moves from −0.40 to −0.20 between them because the
underlying rose. FutEq delta goes from 1250 to 1450 — up 200 shares with no trade at all, so the
passive part is 200 and the active part is exactly zero.

They exist because **Table 2's day 2 does not reproduce.** The circular says a long futures
position shows a "passive increase in EoD delta by 5%" when the underlying appreciates 5%. In
share terms it shows nothing: para 5.1.1 gives futures a delta factor of exactly 1.0, and NSE's
own `Contract_Delta` file confirms it — `FF` rows carry `1.00000000` without exception. A price
move cannot change the FutEq delta of an unchanged futures position measured in shares.

The provision is real and matters; it just cannot be illustrated with futures. Option factors do
move with the underlying (`CE` spans [0, 1] and `PE` spans [−1, 0] in the same file), so days 19
and 21 are the case day 2 was reaching for, done with an instrument where it works.

`tests/test_book.py::test_table_2_day_2_does_not_reproduce` asserts the non-reproduction, so
anyone later "correcting" the fixture to make day 2 rise 5% has to come here and read why it
does not. The underlying doubt is logged in `docs/doubts.md`.

## What the fixture is for

It is the oracle `check_ban_period_reduction()` will be written against: five days whose verdicts
come from the circular itself, and two whose verdicts follow from the decomposition recorded with
SPEC row 6. A check that gets day 5 wrong, or that calls day 21 a breach, is wrong against a
primary source rather than against my own expectations.
