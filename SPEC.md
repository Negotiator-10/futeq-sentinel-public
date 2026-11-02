# Specification

Every rule clause mapped to the function that implements it and the test that proves it. A rule
without a cited source is not coded — it gets a row marked `UNVERIFIED` and a blocked function, so
the gap is visible instead of guessed at.

Citations come from `docs/READING.md`, which holds the paragraph map for all five Week 1 sources.
I should not need to reopen a PDF to fill this table.

Column rules:
- **Rule** is in my own words, not the circular's. If I cannot say it without copying, I have not
  understood it.
- **Source** is circular plus paragraph. Not "SEBI", not "the circular", not "FAQ".
- **Verified** means I read that paragraph myself, with the date.
- **Function** is one function per clause. If the same function name appears on three rows, the
  clause is doing more than one thing and it needs splitting.
- **Test** names the case and the expected number, not "test it works".

| # | Rule (in my words) | Source (circular, paragraph) | Verified on primary source? | Function | Test |
|---|---|---|---|---|---|
| 1 | MWPL = MAX( MIN(15% of free float, 65 × ADDV), 10% of free float ). The two inner limbs are in different units — a share count and a rupee value — so one must be converted before they can be compared, and the circular does not say at which price | SEBI 2025/79 para 5.2.3 | yes, read 31 Oct 2026 | `compute_mwpl()` | `test_mwpl_floor_binds`: FF 1bn shares, price 1,000, ADDV 500m → 100,000,000 shares, floor binds. From `docs/handcalcs/mwpl_by_hand.md` |
| 2 | FutEq open interest | 2025/79 para 5.1 | | | |
| 3 | Quarterly recalculation on rolling 3-month ADDV | 2025/79 para 5.2.4 | yes, read 31 Oct 2026 | `compute_rolling_addv(as_of_date)` | `test_mwpl_is_a_staircase`: 3 Feb and 15 Feb fall in the same quarter, so both give MWPL 100,000,000. 15 Apr falls after a reset, so it gives 120,000,000. Guards against code that recomputes from a trailing 90 days every day, which would be wrong on 89 days out of 90 |
| 4 | Ban entry when market-wide FutEq OI **exceeds** 95% of MWPL, tested at the end of the day | 2025/79 para 5.2.6 (test), 5.3.1 (consequence); both cite SEBI Master Circular 30 Dec 2024, Ch 5, cl 3.3.2.1.2.1 | yes, read 2 Nov 2026 | `is_in_ban()` | `test_ban_entry_is_strictly_greater`: MWPL 100,000,000. OI 94,999,999 → not in ban. OI 95,000,000 → **not** in ban, because the circular says "exceeds", not "reaches". OI 95,000,001 → in ban. Also `test_ban_entry_is_eod_only`: an intraday peak above 95% that closes below it does not trigger a ban |
| 5 | Normal trading resumes once open outstanding position comes down to **80% or below** of MWPL. Note "or below": the exit boundary is inclusive, the opposite of the entry's "exceeds" | SEBI Master Circular 30 Dec 2024, Chapter 5 (Exchange Traded Derivatives), cl 3.3.2.1.2.3. Not restated in 2025/79, so it survives that circular unchanged | yes, read 2 Nov 2026 | `is_in_ban()` — same function as row 4, because entry and exit are two states of one flag, and splitting them is how hysteresis bugs happen | `test_ban_exit_is_inclusive`: MWPL 100,000,000. Already in ban, OI falls to 80,000,001 → still banned. OI falls to 80,000,000 → released. Paired with row 4, this pins both boundaries in opposite directions |
| 6 | Position reduction during a ban, with the sign rule and the passive-increase carve-out | 2025/79 para 5.3.2 | | | |
| 7 | Entity-level limits, all five categories | 2025/79 paras 5.8.1.1 to 5.8.1.5 | | | |
| 8 | End-of-day index limits | 2025/79 para 5.5 | | | |
| 9 | Intraday index-option limits, and the minimum number of snapshots | SEBI 2025/122 paras 4.1, 4.2, 4.3, 4.10 | | | |
| 10 | The 15-minute cure period, and where it does not apply | NSE SURV70553 Annexure 1 paras 3.9 to 3.13 | | | |
| 11 | Delta for an option position | NSE SURV70553 Annexure 2 | | | |
| 12 | Penalty for increasing a position during a ban: a percentage of the **increase in position, by notional value**, recovered before trading opens the next day. The percentage is set by the Exchange, not by SEBI | Structure: Master Circular 30 Dec 2024, Ch 5, cl 3.3.2.1.2.2 — **verified, read 2 Nov 2026**. The percentage itself: **UNVERIFIED**, delegated to the exchange; 2025/79 paras 5.3.4 and 5.8.1.6 delegate likewise, and SURV70553 is the index SOP, not the single-stock one | structure yes; rate no | `compute_ban_breach_penalty()` | `blocked on the rate` — but the base is already testable: `test_penalty_base_is_the_increase_not_the_position`: a client holding 1,000 lots who adds 10 is penalised on the notional of 10, not 1,010. That is the error worth guarding against, and it does not depend on the rate |

## Unknowns
- Which months the quarterly reset falls in. **Confirmed open:** para 5.2.4 says only "every three
  months based on the rolling ADDV for the preceding three month period" and names no months. So
  the reset calendar is configuration in `config/rules.yaml`, not a constant in the code. Row 3's
  test assumes calendar quarters, which is an assumption, not a citation.
- ~~Where the 80% ban exit threshold is set.~~ **Closed 2 Nov 2026:** Master Circular 30 Dec 2024,
  Ch 5, cl 3.3.2.1.2.3. See row 5.
- **Which MWPL definition is in force, and when.** Master Circular cl 3.3.2.1.1 defines MWPL as 20%
  of non-promoter shares. 2025/79 para 5.2.3 replaces that with MAX(MIN(15% free float, 65 × ADDV),
  10% free float) from 1 Oct 2025. So the engine cites the **new** circular for MWPL and the **old**
  Master Circular for the 80% exit, because 2025/79 did not restate the exit. That split is correct
  but it must be stated, or a reviewer will think one of the two citations is stale.
- The penalty **rate** for a ban-period breach. The Master Circular sets the base and the timing but
  explicitly leaves the percentage to the exchange (cl 3.3.2.1.2.2). The "1% of the violating value,
  capped at Rs 1 lakh, floor Rs 5,000" figures in `docs/READING.md` are still unsourced and must
  come from an NSE circular, not from SEBI. It is not in 2025/79 paras 5.2 or 5.3.
  Candidates: the NSE ban-period circulars, or the SEBI Master Circular of 30 Dec 2024.
- The single-stock penalty structure. There must be a separate NSE/CC SOP; SURV70553 is the index one.
- Which price to convert 65 × ADDV at, for row 1. Para 5.2.3 is silent. `compute_mwpl()` must take
  the price as an explicit argument rather than assume one.
- Whether the Annexure 2 delta convention applies to single stocks or only to index options.
- Are the `Contract_Delta` files public without a member login? (Week 1 Thursday feasibility check.)
