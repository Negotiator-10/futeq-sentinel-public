# Specification

Every rule clause mapped to the function that implements it and the test that proves it. A rule
without a cited source is not coded — it gets a row marked `UNVERIFIED` and a blocked function, so
the gap is visible instead of guessed at.

Citations come from `docs/READING.md`, which holds the paragraph map for all seven sources.

Column rules:
- **Rule** is in my own words, not the circular's. If I cannot say it without copying, I have not
  understood it.
- **Source** is circular plus paragraph. Not "SEBI", not "the circular", not "FAQ".
- **Verified** means that paragraph was read directly, with the date.
- **Function** is one function per clause. If the same function name appears on three rows, the
  clause is doing more than one thing and it needs splitting.
- **Test** names the case and the expected number, not "test it works".

> **Status, 2 Nov 2026.** Rows 1 to 5 were worked by me. Rows 6 to 16 were drafted by Claude from
> the primary text at my request, at the end of a long day, and are **pending my review**. That is
> a departure from the tutor rule in `CLAUDE.md` that I write the rule maths, and it is recorded
> here rather than hidden. Reviewing them is the first task of the next session.

## Single stocks

| # | Rule (in my words) | Source | Verified? | Function | Test |
|---|---|---|---|---|---|
| 1 | MWPL = MAX( MIN(15% of free float, 65 × ADDV), 10% of free float ). The two inner limbs are in different units — a share count and a rupee value — so one must be converted before they can be compared, and the circular does not say at which price | SEBI 2025/79 para 5.2.3 | yes, 31 Oct 2026 | `compute_mwpl()` | `test_mwpl_floor_binds`: FF 1bn shares, price 1,000, ADDV 500m → 100,000,000 shares, floor binds. From `docs/handcalcs/mwpl_by_hand.md` |
| 2 | FutEq open interest: net each UCC's delta-weighted positions, then gross-add across UCCs | 2025/79 para 5.1 | yes, 31 Oct 2026 | `compute_futeq_oi()` | `test_futeq_oi_nets_within_ucc_grosses_across`: UCC A long 100 / short 60 → net 40; UCC B long 30 → 30; market total **70**. Netting across UCCs gives 10 and grossing everything gives 130, so the number distinguishes all three implementations |
| 3 | Quarterly recalculation on rolling 3-month ADDV. The circular names no reset months | 2025/79 para 5.2.4 | yes, 31 Oct 2026 | `compute_rolling_addv(as_of_date)` | `test_mwpl_is_a_staircase`: 3 Feb and 15 Feb are in the same quarter, so both give MWPL 100,000,000. 15 Apr is after a reset, so it gives 120,000,000. Guards against recomputing from a trailing 90 days daily, which is wrong on 89 days in 90 |
| 4 | Ban entry when market-wide FutEq OI **exceeds** 95% of MWPL, tested at the **end of the day**. Real-time disclosure of utilisation is still required even though the action is EoD only | 2025/79 para 5.2.6 (test), 5.3.1 (consequence); Master Circular 30 Dec 2024 Ch 5 cl 3.3.2.1.2.1 | yes, 2 Nov 2026 | `is_in_ban(futeq_oi, mwpl, was_in_ban_yesterday)` — **three** arguments. The 95% entry threshold applies only when `was_in_ban_yesterday` is False; see row 5 and `DECISIONS.md` #011 | `test_ban_entry_is_strictly_greater`: not in ban, MWPL 100,000,000. OI 94,999,999 → no. **95,000,000 → no**, because the wording is "exceeds". 95,000,001 → yes. `test_ban_entry_is_eod_only`: an intraday peak above 95% that closes below does not trigger a ban. `test_entry_threshold_is_not_applied_when_already_banned`: in ban at 90% → still banned, although 90% is below the entry threshold |
| 5 | Normal trading resumes once the open outstanding position comes down to **80% or below** of MWPL. "Or below" makes the exit boundary inclusive — the opposite of entry's "exceeds" | Master Circular 30 Dec 2024, Ch 5, cl 3.3.2.1.2.3. Not restated in 2025/79, so it survives unchanged | yes, 2 Nov 2026 | `is_in_ban(futeq_oi, mwpl, was_in_ban_yesterday)` — same function as row 4, because entry and exit are two states of one flag and splitting them is how hysteresis bugs happen. The third argument is what **selects** which threshold applies: 80% on the way out, 95% on the way in. `DECISIONS.md` #011 | `test_ban_exit_is_inclusive`: in ban, MWPL 100,000,000. OI falls to 80,000,001 → still banned. **80,000,000 → released.** With row 4 this pins both boundaries, which are inclusive in opposite directions. `test_two_scrips_same_utilisation_opposite_state`, from real data: 30 Oct 2026, SAIL at 84.93% utilisation was banned while BANDHANBNK at 85.98% traded freely. A two-argument function cannot produce both answers, which is the proof that the third argument is required |
| 6 | Once a scrip is in ban, any trading must **reduce** FutEq OI on an end-of-day basis. A delta of +10 may be brought down to 0. A **change of sign** is not an acceptable reduction. A **passive** increase caused by movement in the scrip is not a breach | 2025/79 para 5.3.2, illustrated by Table 2 in para 5.3.3 | yes, 2 Nov 2026 | `check_ban_period_reduction()` | `test_ban_reduction_sign_rule`: EoD delta +10 on day 1. → +4 permitted. → 0 permitted. → **−5 not permitted**, although the magnitude fell, because the sign changed. `test_passive_increase_is_not_a_breach`: 1 long futures lot held with no trades, underlying +5%, EoD delta rises → permitted (Table 2 day 2). `test_active_increase_is_a_breach`: a second lot bought → not permitted (Table 2 day 5) |
| 7 | Combined futures and options limits per entity, as a percentage of MWPL, in five categories: Client/NRI 10%, TM proprietary 20%, TM (prop + client) / FPI Cat I / MF 30%, FPI Cat II other than individuals/family offices/corporates 20%, FPI Cat II individuals/family offices/corporates 10% | 2025/79 paras 5.8.1.1 to 5.8.1.5 | yes, 2 Nov 2026 | `check_entity_limit(category, futeq_oi, mwpl)` — one function with a category argument; the percentages live in `config/rules.yaml` | `test_entity_limit_by_category`: MWPL 100,000,000. 10,000,001 breaches for a Client but not for a TM proprietary. `test_fpi_cat2_subcategory_decides`: the same FPI Cat II position breaches at 10% if the holder is an individual, family office or corporate, and at 20% otherwise — the **sub**-category decides, and collapsing Cat II to one number is the likely bug |
| 15 | Intraday MWPL utilisation for single stocks is monitored at least **four random times** per session, to trigger Additional Surveillance Margin, entity concentration checks and fortnightly reporting to SEBI. Distinct from ban entry, which is EoD only | 2025/79 para 5.4.1; effective 3 Nov 2025 per para 6 | yes, 2 Nov 2026 | `monitor_intraday_mwpl_utilisation()` | `test_intraday_peak_is_reported_separately`: utilisation peaks at 97% at 11:00 and closes at 92% → **no ban** (row 4) but the day's report must still show 97%. The numeric trigger for ASM is **UNVERIFIED**: 5.4.1.1 says "certain limits" and leaves them to the exchange SOP |

## Index derivatives

| # | Rule (in my words) | Source | Verified? | Function | Test |
|---|---|---|---|---|---|
| 8 | Index **options**, PAN level, end of day: net FutEq OI limit Rs 1,500 cr, and gross FutEq OI limit Rs 10,000 cr applied **separately** to gross long and gross short | 2025/79 para 5.5.1.1 | yes, 2 Nov 2026 | `check_index_option_eod_limit()` | `test_gross_is_two_one_sided_tests`: gross long 9,900 cr and gross short 10,100 cr → **breach**, even though net is −200 cr and far inside 1,500 cr. Testing gross as a single combined number misses it |
| 9 | Index **options**, intraday: net FutEq OI Rs 5,000 cr and gross Rs 10,000 cr, monitored by at least four random snapshots including one between 14:45 and 15:30, using the underlying price at snapshot time. Limits apply **separately for each index** | SEBI 2025/122 paras 4.1 to 4.4; NSE SURV70553 Annexure 1 paras 2.1, 2.2, 3.2, 3.3 | yes, 2 Nov 2026 | `check_index_option_intraday_limit()` | `test_intraday_and_eod_limits_are_different`: net 4,900 cr at a snapshot → no breach, although it is more than triple the Rs 1,500 cr EoD limit, which applies only at EoD. `test_limits_are_per_index`: 4,000 cr on one index plus 4,000 cr on another is not an 8,000 cr breach |
| 13 | Index **futures**, gross notional: FPI Cat I / MF / TM proprietary / Clients — higher of 15% of that index's futures OI or Rs 500 cr; FPI Cat II other than individuals etc. — higher of 10% or Rs 500 cr; FPI Cat II individuals, family offices, corporates — higher of 5% or Rs 500 cr | 2025/79 paras 5.5.2.1 to 5.5.2.4 | yes, 2 Nov 2026 | `check_index_futures_limit(category, gross_notional, index_futures_oi)` | `test_the_500cr_floor_binds`: at index futures OI of Rs 2,000 cr, 15% is 300 cr, so the limit is **500 cr, not 300 cr**. Structurally the same floor as MWPL in row 1, and the same bug: implementing "higher of" as "the percentage" |
| 14 | Position limits are measured against the **previous day's** total market OI. If market OI drops, an entity whose position never changed can breach arithmetically. Such passive breaches are **not** violations | 2025/79 paras 5.5.2.5.1 to 5.5.2.5.3 | yes, 2 Nov 2026 | `is_passive_breach()` | `test_oi_drop_is_not_a_violation`: day 1 market futures OI 10,000 cr → 15% limit 1,500 cr, entity holds 1,400 cr, compliant. Day 2 market OI falls to 8,000 cr → limit 1,200 cr, entity unchanged at 1,400 cr → arithmetic breach, **not** a violation. This is the second passive carve-out, parallel to row 6's |
| 16 | Beyond the index limits, extra exposure is allowed against holdings: aggregate **short** index positions may not exceed the entity's stock holdings, and aggregate **long** positions may not exceed its cash, cash equivalents, government securities and T-bills | 2025/79 paras 5.5.3.1, 5.5.3.2; applied to intraday by SURV70553 Annexure 1 para 2.3 | yes, 2 Nov 2026 | `hedge_exemption_headroom()` | `test_holdings_absorb_the_excess`: an entity 200 cr over the gross short limit with 300 cr of stock holdings is **not** in breach; with 100 cr of holdings it is in breach by 100 cr. Interacts with row 10: a provisional breach becomes final only after this allowance (SURV70553 para 3.12) |

## Mechanics

| # | Rule (in my words) | Source | Verified? | Function | Test |
|---|---|---|---|---|---|
| 10 | A breach seen at a random snapshot gets a second snapshot 15 minutes later. If it persists in both, it is a **provisional** breach, notified to the TM/CM and client by EoD or T+1, and becomes **final** after allowing holdings. The cure period does **not** apply to the final snapshot of the day, 14:45 to 15:30 | NSE SURV70553 Annexure 1 paras 3.9 to 3.13 | yes, 31 Oct 2026 | `classify_intraday_breach()` | `test_cure_period_clears_a_breach`: breach at 11:00, clear at 11:15 → no provisional breach. `test_breach_in_both_snapshots_is_provisional`: breach at both → provisional. `test_no_cure_period_at_the_close`: breach at 15:00 → provisional immediately, with no second snapshot |
| 11 | FutEq per contract: futures = 1, call = N(d1), put = N(d1) − 1, with d1 = {ln(S/K) + (Rf + 0.5σ²)·T} / (σ·√T). Rf is the latest RBI repo rate; σ is the T-1 EOD higher of underlying and futures annualised volatility; S is the real-time underlying at the snapshot; T is minutes to expiry ÷ 525,600, counted midnight to midnight and midnight to 15:30 on expiry day, truncated to the previous whole minute | NSE SURV70553 Annexure 2 | yes for **index** options, 31 Oct 2026. Whether the same convention binds for single stocks is **UNVERIFIED** | `compute_delta()`, `time_to_expiry()` | `test_tte_matches_nse_worked_example`: snapshot 15:00:05 on 24 Sep 2025 for a 30 Sep 2025 expiry → 540 + 7,200 + 930 = **8,670 minutes**, TTE = 8,670 / 525,600 = **0.0165**. NSE published this number, so it cannot be argued with. `test_tte_truncates_to_the_minute`: 15:00:05 and 15:00:59 give the same TTE. `test_put_delta_is_negative`: N(d1) − 1 < 0 for every input |
| 12 | Penalty for increasing a position during a ban: a percentage of the **increase** in position, by notional value, recovered before trading opens the next day. The percentage is set by the **Exchange**, not by SEBI | Structure: Master Circular 30 Dec 2024, Ch 5, cl 3.3.2.1.2.2 — verified 2 Nov 2026. The rate: **UNVERIFIED** and not a SEBI number at all. 2025/79 paras 5.3.4, 5.5.3.3 and 5.8.1.6 delegate likewise | structure yes; rate no | `compute_ban_breach_penalty()` | `blocked on the rate`, but the base is testable without it — `test_penalty_base_is_the_increase`: a client holding 1,000 lots who adds 10 is penalised on the notional of **10**, not 1,010 |

## The one finding that changes the data pipeline

Row 6 cannot be implemented from open-interest files alone. Para 5.3.2 permits a passive increase
and forbids an active one, and two end-of-day delta snapshots look identical in both cases — the
difference is whether a trade happened. So `check_ban_period_reduction()` needs the entity's
**trades**, not just its positions, and a prop book's own order and fill records are the only place
that exists. The synthetic book in `PLAN.md` must therefore carry fills, not just end-of-day
holdings. Worth settling before Week 2 builds the book.

Row 14 is the same shape at market level: an arithmetic breach that is not a violation. Both
carve-outs mean the engine needs a *reason* attached to every breach, not just a boolean.

## Unknowns
- Which months the quarterly reset falls in. **Confirmed open:** para 5.2.4 says only "every three
  months based on the rolling ADDV for the preceding three month period" and names no months. So
  the reset calendar is configuration in `config/rules.yaml`, not a constant in the code. Row 3's
  test assumes calendar quarters, which is an assumption, not a citation.
- **Which MWPL definition is in force, and when.** Master Circular cl 3.3.2.1.1 defines MWPL as 20%
  of non-promoter shares. 2025/79 para 5.2.3 replaces that from 1 Oct 2025. So the engine cites the
  **new** circular for MWPL and the **old** Master Circular for the 80% exit, because 2025/79 did
  not restate the exit. That split is correct but it must be stated, or a reviewer will think one
  of the two citations is stale.
- The penalty **rate** for a ban-period breach (row 12). SEBI never sets it; it must come from an
  NSE circular.
- The ASM trigger level for intraday single-stock MWPL utilisation (row 15). Para 5.4.1.1 says
  "certain limits" and leaves them to the exchange SOP.
- Whether the Annexure 2 delta convention applies to single stocks or only to index options (row
  11). The engine covers single stocks, so this matters.
- Which price to convert 65 × ADDV at (row 1). Para 5.2.3 is silent, so `compute_mwpl()` takes the
  price as an explicit argument rather than assuming one.
- ~~Are the `Contract_Delta` files public without a member login?~~ **Closed 4 Nov 2026:**
  yes. `Contract_Delta_30102026.csv`, 133,620 rows, one per contract per day, with Delta
  Factor exactly 1.0 for futures. NSE also publishes `combineoi_deleq`, the delta-equivalent
  OI per security, which is the quantity the engine computes. So Path A is nearly free and
  Path B becomes a validation layer with two independent scoring keys at different levels of
  aggregation. Both files are public in a browser but neither fetches from a script - see
  `DECISIONS.md` #010.
- **Whether a corporate action can change a security's ISIN,** and if so which actions.
  `DECISIONS.md` #011 keys ban state on ISIN precisely because it is stable, so an ISIN that
  changes would silently cold-start that scrip's state. My recollection is that Indian splits
  usually retain the ISIN and that new ISINs come from partly-paid conversions and demergers,
  but I have not checked. **UNVERIFIED.** What would settle it: an NSE circular on ISIN
  assignment for corporate actions.
- **How ban state is seeded when `fo_secban` and `combineoi` disagree,** or when a symbol in
  the ban list does not appear in that day's `combineoi` at all. #011 says raise and stop;
  whether that has ever actually happened in the published files is untested, because I hold
  one day of data.
