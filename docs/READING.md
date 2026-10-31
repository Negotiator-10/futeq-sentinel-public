# Reading list and facts to verify

Read the primary source before coding each rule. Background: `docs/research_report.md`.

## Week 0
- **NSE Clearing FAQ on the new position limits, limit monitoring and ban period** (near-primary). [PDF](https://www.nseclearing.in/sites/default/files/2025-10/Recent%20changes%20in%20Equity%20Derivative%20segment%20focusing%20on%20position%20limits%2C%20Limit%20Monitoring%2C%20and%20Securities%20in%20Ban%20Period.pdf)
  Write a one-page summary in your own words in `docs/notes_faq.md`.

## Week 1
- **SEBI circular 2025/79 (29 May 2025):** FutEq OI, MWPL, entity limits, ban period. Full reference `SEBI/HO/MRD/TPD-1/P/CIR/2025/79`. [SEBI page](https://www.sebi.gov.in/legal/circulars/may-2025/measures-for-enhancing-trading-convenience-and-strengthening-risk-monitoring-in-equity-derivatives_94293.html) (title: "Measures for Enhancing Trading Convenience and Strengthening Risk Monitoring in Equity Derivatives"). The MWPL definition is in paragraph 5.2; paragraph 6 has the phased implementation dates.
- **SEBI circular 2025/122 (Sep 2025):** intraday position-limit monitoring for index derivatives. [SEBI page](https://www.sebi.gov.in/legal/circulars/sep-2025/framework-for-intraday-position-limits-monitoring-for-equity-index-derivatives_96376.html)
- **NSE circular SURV70553:** snapshot monitoring and the SOP report layout. [PDF](https://nsearchives.nseindia.com/content/circulars/SURV70553.pdf)
- **NSE MSD76877:** retirement of the older file formats on 7 Dec 2026. [PDF](https://nsearchives.nseindia.com/content/circulars/MSD76877.pdf)
- **NSE All Reports page:** where the public daily files live. [Link](https://www.nseindia.com/all-reports)

## Week 5
- **SEBI OTR framework revision (4 Feb 2026).** [SEBI page](https://www.sebi.gov.in/legal/circulars/feb-2026/revision-of-order-to-trade-ratio-otr-framework_99501.html)

## Facts to verify before stating them publicly
Mark each one verified, with the exact source, once checked.

| Claim | Status | Primary source to check |
|---|---|---|
| MWPL is the lower of 15% of free float and 65x average daily delivery value, with a 10% floor, reset quarterly | unverified (from the NSE FAQ) | SEBI 2025/79 |
| Ban entry at 95% of MWPL, exit at 80% | unverified (from the NSE FAQ) | SEBI 2025/79 |
| Entity limits of 10% (client), 20% (proprietary) and 30% (combined) of MWPL | unverified (from the NSE FAQ) | SEBI 2025/79 |
| Penalty is the lower of 1% of the violating value and Rs 1 lakh, with a Rs 5,000 floor, per entity per stock per day | unverified | SEBI 2025/79, NSE circulars |
| Intraday index-option limits of Rs 5,000 cr net and Rs 10,000 cr gross, checked by at least 4 random snapshots; effective date | unverified (date from secondary reporting) | SEBI 2025/122, NSE SURV70553 |
| `Contract_Delta`, combined OI and MWPL files are public without login | unknown | NSE All Reports (Week 1 Thursday) |
| OTR exemption bands: within ±0.75% of LTP; options within ±40% of premium or Rs 20 | unverified (news reports) | SEBI OTR circular, 4 Feb 2026 |
| OTR effective 6 Apr 2026, market makers excluded | unverified (social media) | SEBI and NSE circulars |
| 2025 weekly expiry-day changes (Tuesday/Thursday) | unverified | NSE and BSE circulars |
| Older bhavcopy formats (.MS/.MD) end on 7 Dec 2026 | from NSE MSD76877; re-check | NSE circular |
