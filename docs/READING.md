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
  Map: 5.1 FutEq OI and delta (Table 1 worked example) · 5.2 MWPL · 5.3 position creation during
  the ban period (Table 2 worked example) · 5.4 intraday MWPL monitoring · 5.5 index limits ·
  6 implementation dates.
  Note for the circular watcher (W3 D5): the SEBI circular page carries no body text. The circular
  is a PDF loaded in an `iframe`, and the HTML holds only the title, date and circular number. So
  the watcher must pull the iframe's `src` and read that PDF; scraping the page body returns nothing.
  Found 31 Oct 2026.
- **SEBI circular 2025/122 (Sep 2025):** intraday position-limit monitoring for index derivatives. [SEBI page](https://www.sebi.gov.in/legal/circulars/sep-2025/framework-for-intraday-position-limits-monitoring-for-equity-index-derivatives_96376.html)
- **NSE circular SURV70553:** snapshot monitoring and the SOP report layout. [PDF](https://nsearchives.nseindia.com/content/circulars/SURV70553.pdf)
- **NSE MSD76877:** retirement of the older file formats on 7 Dec 2026. [PDF](https://nsearchives.nseindia.com/content/circulars/MSD76877.pdf)
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
| Entity limits of 10% (client), 20% (proprietary) and 30% (combined) of MWPL | unverified (from the NSE FAQ) — not covered by para 5.2 | SEBI 2025/79 |
| Penalty is the lower of 1% of the violating value and Rs 1 lakh, with a Rs 5,000 floor, per entity per stock per day | unverified — not covered by para 5.2 | SEBI 2025/79, NSE circulars |
| Intraday index-option limits of Rs 5,000 cr net and Rs 10,000 cr gross, checked by at least 4 random snapshots; effective date | unverified (date from secondary reporting) | SEBI 2025/122, NSE SURV70553 |
| `Contract_Delta`, combined OI and MWPL files are public without login | unknown | NSE All Reports (Week 1 Thursday) |
| OTR exemption bands: within ±0.75% of LTP; options within ±40% of premium or Rs 20 | unverified (news reports) | SEBI OTR circular, 4 Feb 2026 |
| OTR effective 6 Apr 2026, market makers excluded | unverified (social media) | SEBI and NSE circulars |
| 2025 weekly expiry-day changes (Tuesday/Thursday) | unverified | NSE and BSE circulars |
| Older bhavcopy formats (.MS/.MD) end on 7 Dec 2026 | from NSE MSD76877; re-check | NSE circular |
