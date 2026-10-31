# Reading list and facts to verify

Read the primary source before coding each rule. Background: `docs/research_report.md`.

## Week 0
- **NSE Clearing FAQ on the new position limits, limit monitoring and ban period** (near-primary). [PDF](https://www.nseclearing.in/sites/default/files/2025-10/Recent%20changes%20in%20Equity%20Derivative%20segment%20focusing%20on%20position%20limits%2C%20Limit%20Monitoring%2C%20and%20Securities%20in%20Ban%20Period.pdf)
  Write a one-page summary in your own words in `docs/notes_faq.md`.
  Local copy: `data/nse_clearing_faq.pdf` (gitignored). Downloaded 31 Oct 2026, 228,843 bytes,
  `sha256 5495136a820cb643cc49cb720dea1b354cd44b8a77adff71c0abc9b934dcfd67`.

## Week 1
- **SEBI circular 2025/79 (29 May 2025):** FutEq OI, MWPL, entity limits, ban period. Full reference `SEBI/HO/MRD/TPD-1/P/CIR/2025/79`. [SEBI page](https://www.sebi.gov.in/legal/circulars/may-2025/measures-for-enhancing-trading-convenience-and-strengthening-risk-monitoring-in-equity-derivatives_94293.html) (title: "Measures for Enhancing Trading Convenience and Strengthening Risk Monitoring in Equity Derivatives"). The MWPL definition is in paragraph 5.2; paragraph 6 has the phased implementation dates.
  Direct PDF: https://www.sebi.gov.in/sebi_data/attachdocs/may-2025/1748521484014.pdf
  Local copy: `data/sebi_2025_79.pdf` (gitignored). Downloaded 31 Oct 2026, 570,558 bytes, 21 pages,
  `sha256 44034647ee0a8eb1e5723408f5cdea27f293095c07eedb788d1e09dbcd691d88`.
  Paragraph map, read 31 Oct 2026 (pages 1-14 of 21; 15-21 are Annexure-1, index-option clauses
  from the Master Circular, not yet read):
  - **5.1** FutEq OI and delta. Long futures delta +1; long calls 0 to +1; long puts 0 to -1;
    short calls negative, short puts positive. FutEq OI for a scrip = gross addition of each UCC's
    *net* FutEq OI. Table 1, page 3, works it through for four clients.
  - **5.2** MWPL. 5.2.3 the formula and the floor; 5.2.4 quarterly on rolling 3-month ADDV;
    5.2.5 why it is tied to delivery; 5.2.6 the 95% end-of-day test.
  - **5.3** Position creation during the ban period. 5.3.2 is the one that matters: trading after
    entry must *reduce* FutEq OI end-of-day; a change in the sign of delta is not acceptable
    reduction; a passive increase from price movement is not a breach. Table 2, page 5, gives five
    worked days. 5.3.4 delegates the penalty structure to a joint CC SOP.
  - **5.4** Intraday MWPL monitoring, at least four random times a day.
  - **5.5** Index futures and index options limits. 5.5.1.1: net EoD FutEq OI for index options
    Rs 1,500 cr, gross Rs 10,000 cr. 5.5.2.5.3: passive breaches are not violations.
  - **5.6** Pre-open session for derivatives. **5.7** Non-benchmark index eligibility.
  - **5.8** Entity-level limits for single stocks (the 10/20/30 numbers).
  - **6** Phased implementation table. **Annexure-1** from page 13.

### Implementation dates, from para 6 (verified 31 Oct 2026)
| Para | Measure | Effective |
|---|---|---|
| 5.1 | FutEq OI formulation | already implemented |
| 5.2 | MWPL definition | 1 Oct 2025 |
| 5.3 | Position creation during ban period | 1 Oct 2025 |
| 5.4 | Intraday MWPL monitoring | 3 Nov 2025 |
| 5.5 | Index futures limits | 1 Jul 2025 |
| 5.5 | Index options (glide path) | 1 Jul to 5 Dec 2025 |
| 5.5 | Index options (normal) | 6 Dec 2025 |
| 5.6 | Pre-open for derivatives | 6 Dec 2025 |
| 5.7 | Non-benchmark index eligibility | 3 Nov 2025 |
| 5.8 | Entity-level limits, single stocks | 1 Oct 2025 |

So "what changed on 1 Oct 2025" is precisely three things: the MWPL definition, ban-period
position creation, and entity-level limits. FutEq OI itself was already in force.
  Note for the circular watcher (W3 D5): the SEBI circular page carries no body text. The circular
  is a PDF loaded in an `iframe`, and the HTML holds only the title, date and circular number. So
  the watcher must pull the iframe's `src` and read that PDF; scraping the page body returns nothing.
  Found 31 Oct 2026.
- **SEBI circular 2025/122 (1 Sep 2025):** intraday position-limit monitoring for equity **index**
  derivatives. Full ref `SEBI/HO/MRD/TPD/CIR/P/2025/122`.
  [SEBI page](https://www.sebi.gov.in/legal/circulars/sep-2025/framework-for-intraday-position-limits-monitoring-for-equity-index-derivatives_96376.html)
  · direct PDF https://www.sebi.gov.in/sebi_data/attachdocs/sep-2025/1756745625835.pdf
  Local: `data/sebi_2025_122.pdf`, 386,997 bytes, 4 pages,
  `sha256 869a02813b0fcc107665ba8bea17a378220823652ad8b9f6476c8b3e26b2d48f`. Read 31 Oct 2026.
  - 4.1 intraday **net** FutEq limit per entity Rs 5,000 cr · 4.2 intraday **gross** Rs 10,000 cr,
    separately long and short · 4.3 minimum four random snapshots, **including one between 14:45
    and 15:30** · 4.4 underlying price at snapshot time · 4.7 on expiry day breaches additionally
    attract penalty/ASD · **4.10 the framework is index options only** · 6 effective 1 Oct 2025,
    except 4.7 from 6 Dec 2025.

- **NSE circular SURV70553 (30 Sep 2025, ref 764/2025):** the SOP for intraday FutEq monitoring of
  **index** derivatives. [PDF](https://nsearchives.nseindia.com/content/circulars/SURV70553.pdf)
  Local: `data/nse_SURV70553.pdf`, 265,662 bytes, 6 pages,
  `sha256 aa02e0a9055463e88b6677c453d8e27c4dc74d5681ac63b70ceeb2e03cfad239`. Read 31 Oct 2026.
  - Annexure 1: 2.1-2.2 repeat the 5,000 / 10,000 cr limits · 3.3 four snapshots incl 14:45-15:30 ·
    3.5 volatility is previous-day EOD (T-1), higher of underlying and futures annualised vol ·
    **3.9-3.13 a 15-minute cure period**: a breach at a snapshot triggers another 15 minutes later,
    and only if it persists in both does it become a *provisional* breach; the cure period does
    **not** apply to the final 14:45-15:30 snapshot · 3.12 after allowing cash/holdings benefit a
    provisional breach becomes final · 3.15.1 worked example of net and gross delta with violation
    flags · 3.16 breaching long then short intraday counts as two violations.
  - **Annexure 2 is the delta computation SOP** — see the section below. This is the single most
    useful page in the whole reading list.

- **NSE MSD76877 (14 Oct 2026, ref 68/2026):** "Streamlining EOD information dissemination related
  to Bhavcopy - Update". [PDF](https://nsearchives.nseindia.com/content/circulars/MSD76877.pdf)
  Local: `data/nse_MSD76877.pdf`, 191,839 bytes, 3 pages,
  `sha256 0dda59d8cbd465f58a449cd11fcb739983657e02fa70cf3ef4f848abe5ea8ade`. Read 31 Oct 2026.
  - Extranet bhavcopy reports and the `.MS`/`.MD` NNF broadcast are both discontinued on
    **7 Dec 2026** — a date **revised from 16 Nov 2026**, so it has already slipped once and could
    slip again. The watcher should treat it as a moving deadline, not a fixed one.
  - Useful for the parsers: FO bhavcopy files are `DDMM0000.md`, `DDMM0000.ms`, `DDMMSPD0000.md`,
    `DDMMSPD0000.ms` under extranet path `/faoftp/faocommon/Bhavcopy`; CM uses
    `/cmftp/common/bhavcopy`.
  - From 16 Nov 2026 the closing price is broadcast for FO via `BCAST_ENHNCD_ONLY_MBP (17208)`.

## The delta formula is published (NSE SURV70553, Annexure 2)
Read 31 Oct 2026. This matters for W3 D1, where the plan assumed we might have to reverse-engineer
deltas. We do not — NSE publishes the exact method it uses:

- FutEq of a **futures** contract = 1
- FutEq of a **call** = `N(d1)`
- FutEq of a **put** = `N(d1) - 1`
- `d1 = { ln(S/K) + (Rf + 0.5 * Vol_Annual^2) * T } / (Vol_Annual * sqrt(T))`
  - `S` underlying price at the snapshot · `K` strike
  - `Rf` the latest **RBI repo rate**
  - `Vol_Annual` the **higher** of underlying annualised volatility and futures annualised
    volatility, taken from the **previous day's EOD (T-1)**
  - `T` time to expiry **counted in minutes**, divided by 525,600. Calendar-day basis, midnight to
    midnight; on expiry day, midnight to 15:30. A snapshot at 15:00:33 uses the TTE as at 15:00.
  - `N()` the cumulative normal distribution

So this is Black-Scholes on the spot with a repo-rate drift, not Black-76 on the futures price, and
the volatility is historical rather than implied. That is a different model from the one `PLAN.md`
sketched for Path B, and it is worth changing the plan to match.

**Caveat, unverified:** Annexure 2 is written for *index options intraday* monitoring. Whether
single-stock FutEq OI uses the same delta convention is not stated anywhere I have read. Check
before reusing it for stocks.
- **NSE All Reports page:** where the public daily files live. [Link](https://www.nseindia.com/all-reports)

## Week 5
- **SEBI OTR framework revision (4 Feb 2026).** [SEBI page](https://www.sebi.gov.in/legal/circulars/feb-2026/revision-of-order-to-trade-ratio-otr-framework_99501.html)

## Facts to verify before stating them publicly
Mark each one verified, with the exact source, once checked. The status must say *where I looked*,
in the form `verified: <circular> para <n>, read <date>`. A bare "verified" is an assertion, not a
citation: it stops anyone, including me in three weeks, from re-walking the check. Confirming a
number against the FAQ is not the same as verifying it against the circular, so those get different
statuses.

| Claim | Status | Primary source to check |
|---|---|---|
| MWPL is the lower of 15% of free float and 65x ADDV, with a floor of **10% of free float**, recalculated quarterly on rolling 3-month ADDV | **verified: SEBI 2025/79 para 5.2.3 (formula and floor) and 5.2.4 (quarterly, rolling ADDV), read 31 Oct 2026** | done |
| Ban entry at 95% of MWPL | **verified: SEBI 2025/79 para 5.2.6 and 5.3.1, read 31 Oct 2026** | done |
| Ban exit at 80% of MWPL | unverified — 80% does not appear in para 5.2 or 5.3 of 2025/79; find where it is set | NSE circulars; SEBI Master Circular 30 Dec 2024 |
| Entity limits of 10% (client/NRI), 20% (TM proprietary) and 30% (TM prop+client, FPI Cat I, MF) of MWPL | **verified: SEBI 2025/79 para 5.8.1, read 31 Oct 2026.** Incomplete as stated: 5.8.1.4 adds FPI Cat II (non-individual) at 20% and 5.8.1.5 FPI Cat II (individuals, family offices, corporates) at 10%. The engine needs all five categories, not three | done |
| Penalty is the lower of 1% of the violating value and Rs 1 lakh, with a Rs 5,000 floor, per entity per stock per day | unverified — and **2025/79 does not set it**. Paras 5.3.4, 5.5.3.3 and 5.8.1.6 each delegate the penalty structure to a joint CC/exchange SOP. So the source is the NSE SOP, not the SEBI circular | NSE SURV70553 and the joint CC SOP |
| Intraday index-option limits of Rs 5,000 cr net and Rs 10,000 cr gross, checked by at least 4 random snapshots, effective 1 Oct 2025 | **verified: SEBI 2025/122 paras 4.1, 4.2, 4.3 and 6, read 31 Oct 2026; repeated in NSE SURV70553 Annexure 1 paras 2.1, 2.2, 3.3.** There is no conflict with the Rs 1,500 cr in 2025/79 para 5.5.1.1: 1,500 is the **end-of-day** net limit, 5,000 the **intraday** net limit. Gross is 10,000 for both. One snapshot must fall between 14:45 and 15:30, and **index options only** (2025/122 para 4.10) | done |
| A breach at an intraday snapshot gets a 15-minute cure period, except at the final 14:45-15:30 snapshot | **verified: NSE SURV70553 Annexure 1 paras 3.9 to 3.13, read 31 Oct 2026** | done |
| Delta is Black-Scholes N(d1), repo rate as Rf, T-1 higher-of-two annualised volatility, TTE in minutes / 525600 | **verified for index options: NSE SURV70553 Annexure 2, read 31 Oct 2026.** Unverified whether the same convention applies to single stocks | NSE single-stock SOP |
| `Contract_Delta`, combined OI and MWPL files are public without login | unknown | NSE All Reports (Week 1 Thursday) |
| OTR exemption bands: within ±0.75% of LTP; options within ±40% of premium or Rs 20 | unverified (news reports) | SEBI OTR circular, 4 Feb 2026 |
| OTR effective 6 Apr 2026, market makers excluded | unverified (social media) | SEBI and NSE circulars |
| 2025 weekly expiry-day changes (Tuesday/Thursday) | unverified | NSE and BSE circulars |
| Older bhavcopy formats (.MS/.MD) end on 7 Dec 2026 | **verified: NSE MSD76877, read 31 Oct 2026.** Note it was revised from 16 Nov 2026, so the date has already moved once | done |
| Penalty for a single-stock ban-period or entity-limit breach | **not found yet.** 2025/79 delegates it to a joint CC SOP (5.3.4, 5.8.1.6); SURV70553 is the *index* SOP and does not cover single stocks. There must be a separate NSE/CC circular | search NSE circulars for the single-stock FutEq SOP |
