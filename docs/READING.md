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

- **SEBI Master Circular for Stock Exchanges and Clearing Corporations (30 Dec 2024,
  SEBI/HO/MRD-PoD2/CIR/P/2024/00181).** The cover circular is only 4 pages; the substance is in
  separate chapter files, which the circular's own web page does not link. Chapter 5 is the one
  that matters.
  - Cover: [PDF](https://www.sebi.gov.in/sebi_data/attachdocs/jan-2025/1736760771912.pdf)
    Local: `data/sebi_master_circular_20241230.pdf`, 193,348 bytes, 4 pages,
    `sha256 251ede452579cb403c34bab49217a2641ec8457a7471b2197e5bd1627bdd31fe`. Read 2 Nov 2026.
  - **Chapter 5, Exchange Traded Derivatives:**
    [PDF](https://www.sebi.gov.in/sebi_data/commondocs/dec-2024/RE_Chapter%205%20-%20Exchange%20Traded%20Derivatives%20FINAL_1_p.pdf)
    Local: `data/sebi_master_circular_ch5_etd.pdf`, 2,136,907 bytes, 213 pages,
    `sha256 492e59994989604db00edec95366bb2110ac589076f6aa27a78619dc240588da`. Read 2 Nov 2026.

### Chapter 5 paragraph map (the clauses 2025/79 points back to)
| Clause | What it says |
|---|---|
| 3.3.2.1.1 | **Old** MWPL: 20% of non-promoter (free-float) shares. Superseded for MWPL purposes by 2025/79 para 5.2.3 from 1 Oct 2025 |
| 3.3.2.1.2.1 | End-of-day test: market-wide OI **exceeds** 95% of MWPL → from next day, trade only to decrease positions. Real-time disclosure of OI as a % of MWPL is required even though the action is EoD only |
| 3.3.2.1.2.2 | Ban-period breach penalty: a percentage of the **increase** in position, by notional value, recovered before trading opens next day. **The Exchange sets the percentage**, not SEBI |
| 3.3.2.1.2.3 | **Ban exit: normal trading resumes once open outstanding position comes down to "80% or below" of MWPL.** The exit boundary is inclusive; the 95% entry boundary is not |
| 3.3.2.1.3 | The MWPL dissemination timetable: by 6:30 PM each exchange publishes, per security, ISIN, name and symbol, MWPL in number of shares, and OI in number of shares; a further file at 7:00 PM. Directly relevant to the W1 D5 feasibility check and the D6 parsers |

This closes the 80% gap that was open since 31 Oct. It also shows why the engine cites two
circulars at once: the **new** one (2025/79) for the MWPL formula, the **old** Master Circular for
the ban exit, because 2025/79 never restated the exit.

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
| Ban exit at 80% of MWPL, and the boundary is **inclusive** ("80% or below") | **verified: SEBI Master Circular 30 Dec 2024, Chapter 5, cl 3.3.2.1.2.3, read 2 Nov 2026.** Not restated in 2025/79, so it survives unchanged. Note the asymmetry against entry: entry is "exceeds 95%" (exclusive), exit is "80% or below" (inclusive) | done |
| Entity limits of 10% (client/NRI), 20% (TM proprietary) and 30% (TM prop+client, FPI Cat I, MF) of MWPL | **verified: SEBI 2025/79 para 5.8.1, read 31 Oct 2026.** Incomplete as stated: 5.8.1.4 adds FPI Cat II (non-individual) at 20% and 5.8.1.5 FPI Cat II (individuals, family offices, corporates) at 10%. The engine needs all five categories, not three | done |
| Penalty is the lower of 1% of the violating value and Rs 1 lakh, with a Rs 5,000 floor, per entity per stock per day | **structure verified, rate still unverified.** Master Circular Ch 5 cl 3.3.2.1.2.2 (read 2 Nov 2026) sets the *base* — a percentage of the **increase** in position by notional value — and the *timing* — recovered before trading opens next day — but states that **the Exchange specifies the percentage**. So the 1% / Rs 1 lakh / Rs 5,000 figures cannot come from SEBI at all; they must come from an NSE circular. 2025/79 paras 5.3.4, 5.5.3.3 and 5.8.1.6 delegate likewise | NSE single-stock SOP (SURV70553 is the *index* one) |
| Intraday index-option limits of Rs 5,000 cr net and Rs 10,000 cr gross, checked by at least 4 random snapshots, effective 1 Oct 2025 | **verified: SEBI 2025/122 paras 4.1, 4.2, 4.3 and 6, read 31 Oct 2026; repeated in NSE SURV70553 Annexure 1 paras 2.1, 2.2, 3.3.** There is no conflict with the Rs 1,500 cr in 2025/79 para 5.5.1.1: 1,500 is the **end-of-day** net limit, 5,000 the **intraday** net limit. Gross is 10,000 for both. One snapshot must fall between 14:45 and 15:30, and **index options only** (2025/122 para 4.10) | done |
| A breach at an intraday snapshot gets a 15-minute cure period, except at the final 14:45-15:30 snapshot | **verified: NSE SURV70553 Annexure 1 paras 3.9 to 3.13, read 31 Oct 2026** | done |
| Delta is Black-Scholes N(d1), repo rate as Rf, T-1 higher-of-two annualised volatility, TTE in minutes / 525600 | **verified for index options: NSE SURV70553 Annexure 2, read 31 Oct 2026.** Unverified whether the same convention applies to single stocks | NSE single-stock SOP |
| `Contract_Delta`, combined OI and MWPL files are public without login | unknown | NSE All Reports (Week 1 Thursday) |
| OTR exemption bands: within ±0.75% of LTP; options within ±40% of premium or Rs 20 | unverified (news reports) | SEBI OTR circular, 4 Feb 2026 |
| OTR effective 6 Apr 2026, market makers excluded | unverified (social media) | SEBI and NSE circulars |
| 2025 weekly expiry-day changes (Tuesday/Thursday) | unverified | NSE and BSE circulars |
| Older bhavcopy formats (.MS/.MD) end on 7 Dec 2026 | **verified: NSE MSD76877, read 31 Oct 2026.** Note it was revised from 16 Nov 2026, so the date has already moved once | done |
| Penalty for a single-stock ban-period or entity-limit breach | **not found yet.** 2025/79 delegates it to a joint CC SOP (5.3.4, 5.8.1.6); SURV70553 is the *index* SOP and does not cover single stocks. There must be a separate NSE/CC circular | search NSE circulars for the single-stock FutEq SOP |

---

# NSE daily data files (first downloaded 2 Nov 2026)

All five are public daily reports from https://www.nseindia.com/all-reports-derivatives. They
cannot be fetched by a plain HTTP client — see `DECISIONS.md` on the 403/tarpit finding. Raw
files live in `data/` (gitignored); only these descriptions are tracked.

| File | Bytes | sha256 |
|---|---|---|
| `combineoi_30102026.zip` | 22,204 | `076660e6f7452d28f497859483df13903863ec1bbfc4932b0a01737ca291211c` |
| `combineoi_12102026.zip` | 21,679 | `b232e63b56f369da4194cb2385d451c6ac9c4dd8fb01275f70a9bcf259a6f135` |
| `combineoi_13102026.zip` | 21,729 | `89a1a844d76e415c58d59a80d84c0ec605aa5610d96f175c09b849ee520fccfc` |
| `combineoi_14102026.zip` | 21,750 | `01a5d0fffe4adf484ec86da508fab87ffff183f25fc43946ee7148cc580e882e` |
| `combineoi_26102026.zip` | 21,742 | `6800b35df62d6f39d3fb78d95338118d8d646e282beca9f4294d1434a2b3a256` |
| `combineoi_27102026.zip` | 21,697 | `746e1781d47a45628b957dcc49dc29775810312a98a9fc68523b143294d9460c` |
| `combineoi_28102026.zip` | 21,857 | `82532e2221a42b5b95de53402f8fc4bd20065a7db3317342e0eb0cd42e5d2303` |
| `combineoi_deleq_30102026.csv` | 17,900 | `5909af2cb4c5bcfd27ead7d316d34260add87f8f7460269baa8592e4f24c3d9d` |
| `Contract_Delta_30102026.csv` | 6,605,274 | `e061da1005e0e9a5927e2e1c633cbb0bc5a433545c7095426f85c48905230db9` |
| `fo_secban_02112026.csv` | 62 | `c793e59f34230c54c5eafae90a0d5c5e0174cdfc68b5b2e551fa3f8a5d2c3af2` |
| `fo_secban_30102026.csv` | 62 | `657f42306413544855e0c232dc1d62b56f6814ab98ae7d806efd7d3d5f2e9859` |
| `fo_secban_12102026.csv` | 83 | `3240f7a2a38cdf4a097c2e515f9e469eceb6bc977bd2f4bdac27a90019f43fbf` |
| `fo_secban_13102026.csv` | 92 | `5ea8fa4b81beeb73ef8d9e8bd7bbe29177de40514f29ff0cccd0e28e9f2b0d58` |
| `fo_secban_14102026.csv` | 67 | `13535288084d1b423b14631e9315b470d195452b40ced7e7f49b3cda86f098c3` |
| `fo_secban_15102026.csv` | 74 | `553cefe582b83393a0308404540e6cf659124b15f7c0226f1bb747d31bc4e505` |
| `fo_secban_16102026.csv` | 74 | `13a325bfac762665a38a96855240b19e4d1f8134c0f8d7082f312ff4426490a6` |
| `fo_secban_19102026.csv` | 74 | `cfffe15162d6d18815a56e2edd7b53bb156af753589dc79559c642b1831ddc7f` |
| `fo_secban_21102026.csv` | 74 | `98486c266c5069242dbcf1f05bf4a6a32196f306ee0567414e3d30b61373feb4` |
| `fo_secban_22102026.csv` | 74 | `a1e02e700c8383e4cd110450cd2ddf5c735070b8f38e233eb164696295490ff8` |
| `fo_secban_23102026.csv` | 74 | `c248d7e7bbd565376d6b2e03f21098f0780761860dfef31ebf79b39bc730acb3` |
| `fo_secban_26102026.csv` | 74 | `315446155766b2d052e1123760de39fe4062dcdecea3fd0cb975b9e09cc73757` |
| `fo_secban_27102026.csv` | 74 | `5de741a28e20b5f6f625f0c90c798319726d764f63723d9d73a52854b999408f` |
| `fo_secban_28102026.csv` | 53 | `8af926d9d336ee025f59e12224987119104b1d2b3be72a8655263a6f66736662` |
| `fo_secban_29102026.csv` | 62 | `4f5cd81f624529a94571e2befd5335dfde0d56454bdbd68ad683c217f8f7d699` |
| `BhavCopy_NSE_FO_0_0_0_20261030_F_0000.csv.zip` | 1,066,684 | `99da5162c5e18aa4f79183a0c546780d07d5c1dedfbbcb5f1a0fbf55af28158b` |
| `Trading holiday for NSE.pdf` | 176,660 | `5a2079cd78b2e6b536ef0d28300e63b645721bed22cc82a91facf5945f3296ea` |
| `combineoi_26082026.zip` | 21,000 | `5509c496379979f3142920fc07993fc1193ad7989ab3d19479106b923cc5e117` |
| `combineoi_15102026.zip` | 21,713 | `b358fb195fe7ce652bd59d31809aa3476005829ac7cdfb8e92b2c7b231a34518` |
| `combineoi_29102026.zip` | 22,193 | `cd9ef267176a03a6de0e8a51791f8bc6706f0f5a050add4394434633b2e2b31b` |
| `combineoi_02112026.zip` | 22,219 | `853823d6981505551cda3f57b3d5c59e27ed69678732f2fd58df7ff569f79889` |
| `BhavCopy_NSE_FO_0_0_0_20261027_F_0000.csv.zip` | 1,366,893 | `c086dbd47763ef7399dcb1b8dedb5c2396a04f36949fded8f42e641f0919d316` |
| `BhavCopy_NSE_FO_0_0_0_20261029_F_0000.csv.zip` | 1,030,948 | `cb2dc239fad84efa1977c4925b3f0c4882fc8e94426dc94e9bb73cc608de7054` |
| `fo_secban_06112026.csv` | 55 | `97eb2de4aa066b5923d5a79530ddf8095d4dfcb4b0b97ff81363398b48bea72d` |
| `fo_secban_08112026.csv` | 55 | `34b68cb999f6c66dd77274242ab8a478532e4133b17d39b0d083da2bcd2ce042` |
| `fo_secban_09112026.csv` | 55 | `b0aa285238c3dd954f7ab5984969bd59c3bba1316a0986e560479c97bac2b3ce` |
| `combineoi_06112026.zip` | 22,285 | `f3be2b174de74e48e641618719c496cff3d5fde6e49f386a56a181683316ea84` |
| `combineoi_08112026.zip` | 22,249 | `778bb013279b1f3356a5b60d7515369ecbe0a075d8c368d895be3344106fe1d6` |
| `fo_secban_03112026.csv` | 62 | `9abe24b292ff44b806c698dfd21b73e11d2ea07062f2f40e02e17ba3c5c9bc7f` |
| `fo_secban_04112026.csv` | 62 | `2300055b6835841bb8413346df37d631efb298fc89e85ee82d4dc7811f24fb4e` |
| `fo_secban_05112026.csv` | 62 | `d06b6b64082f0d12562423b3ce6a765af614c28b38e995d5d00a1b3a6ba3e519` |
| `combineoi_03112026.zip` | 22,197 | `a3d4684b259f70ca7f3221e9df228f8527262dbb055dca7c951ef37db7f8a9be` |
| `combineoi_04112026.zip` | 22,230 | `e30c75145054f23b23f67a1ce054197b697ef9eadd9fbfc0680c9842d5e692a0` |
| `combineoi_05112026.zip` | 22,227 | `9a29fff3a287f474511061be17893e3c933fb2e1875fd34bf8a1f6c5265e5656` |
| `combineoi_30092026.zip` | 21,721 | `677053ce0b6a4c59cfb048e28e907794231d5bae41bd89e839f020c8c482eba5` |
| `combineoi_01102026.zip` | 21,682 | `460f6a8e615bbb25c4566593ab4f4bd28127a1005e52d3e5c962f3cc511e90f5` |
| `combineoi_16102026.zip` | 21,746 | `8a4cb85b52f11982fae472822b92f40e22dd0ecb3bf0247a1d580e0e03739dda` |
| `combineoi_19102026.zip` | 21,732 | `b350102cb581e9f6e9cc0a18fc0f973e86e1f917939707b6a8eca321818c72e3` |
| `combineoi_21102026.zip` | 21,777 | `ff09be9f4da626294b7934e22c344ca62fceb87d7250c83d5caabf92dbc672d8` |
| `combineoi_22102026.zip` | 21,730 | `5dcda974583e597271390f71c74e21342ea2e287f7a9551903aa1a27c287ca99` |
| `combineoi_23102026.zip` | 21,750 | `5ea5b3e4a3ba326e57c27edc1386f7b9426614aab0129c2cf56b3a28a6deeaeb` |
| `combineoi_31072026.zip` | 20,762 | `2554c659a639fd2b5f893059cd2e0a16bf83fc6859084ad0ab3f43d2f9499790` |
| `fo_secban_31072026.csv` | 50 | `dc88eacec3c258d37f504f1cc21d8af920dde78517746ce6083393abb1ef3a01` |
| `combineoi_01102025.zip` | 20,565 | `e61487fb38d1f3c39d3a2031af1e4cfd38e2985f5b6ea20fa67a23edc5536395` |
| `fo_secban_01102025.csv` | 59 | `b1648ca604f9ded512176297d3c2f5f8e8eef6bd51c8886b7f74544584aad976` |
| `FAOP65588.pdf` | 134,297 | `e359379d4d7bc0296cea9b9bb1deda6d8460957cf49209208525da5a25ed7629` |
| `FAOP72262.pdf` | 79,468 | `f98ae37cf6a6f8c18b1064b0551599d084c4b4a27804842c487f0da43fea8f0f` |

Ban lists for 12 to 29 Oct, fetched 6 Nov 2026 through the built-in browser from NSE's same-origin
endpoint `www.nseindia.com/api/reports` (archive "F&O - Security in ban period"). That endpoint
served `fo_secban_30102026.csv` byte-identical to the copy above, so it is the same file as the
archive link. **Correction, same day:** 27 Oct first returned 404
(`{"error":"Not Found, file is unavailable"}`) and was reported missing, but a retry returned
the file. A JSON 404 from this endpoint can be transient; `combineoi_14102026.zip` did the
same. 20 Oct returned NSE's HTML "file doesn't exist" page twice; holiday not yet checked
against NSE's calendar.


This table has outgrown being written by hand. `DECISIONS.md` #012 decision 4 already says
every stored record carries the hash of the file behind it, so the next batch should generate
a tracked manifest instead of pasting rows here.

## Ban transitions, 12 Oct to 2 Nov 2026

Found on 6 Nov by diffing fourteen consecutive `fo_secban` lists. The point was to get a real
test case for the entry and exit thresholds, which had none: on 30 Oct no scrip in the whole
file exceeded 95%, so an entry test against that day would have passed vacuously.

| Date | Change | Symbol | Measurement to forecast it from |
|---|---|---|---|
| 13 Oct | entry | KAYNES | `combineoi_12102026` |
| 14 Oct | release | BANDHANBNK | `combineoi_13102026` |
| 14 Oct | release | LICHSGFIN | `combineoi_13102026` |
| 15 Oct | entry | SAIL | `combineoi_14102026` |
| 28 Oct | release | AMBUJACEM | `combineoi_27102026` |
| 28 Oct | release | KAYNES | `combineoi_27102026` |
| 29 Oct | entry | KAYNES | `combineoi_28102026` |

Three entries and four releases, from five measurement days.

**Gaps have to be explained, not skipped.** A transition that starts and ends inside a gap is
invisible to a diff, so an unexplained gap makes the list "what I happened to find" rather than
"all of it". After the 27 Oct retry the remaining gaps are 16-19 Oct and 23-26 Oct, both
weekends, and 19-21 Oct, which is the 20th. **20 Oct is still not accounted for**: it returned
NSE's HTML "file doesn't exist" page twice, which is a different failure from the transient JSON
404 that 27 Oct gave, but it has not been checked against NSE's published holiday calendar. Until
it is, a transition on 20 or 21 Oct cannot be ruled out.

**The 28 Oct release is measured from 27 Oct.** I first wrote 26 Oct here, having concluded from
a 404 that the 27th was not a trading day. It was. Correcting it moved the measurement day and
cost one more download - see the correction note above the checksum table.

**KAYNES does the full cycle**, which makes it the single most useful scrip in the sample:

    12 Oct  free
    13 Oct  BANNED      entry
    14 Oct  BANNED      held
    ...     BANNED
    26 Oct  BANNED
    28 Oct  free        release
    29 Oct  BANNED      re-entry
    30 Oct  BANNED
    02 Nov  BANNED

Entry, nine sessions of hold, release, and re-entry on the very next session. The
release-to-re-entry edge is the hysteresis boundary and the hardest part to get right, and one
symbol exercises all of it.

**The 80-95% band is populated by scrips that have been banned.** Of the seven scrips sitting
in the band on 30 Oct, five had been in ban at some point in the preceding three weeks:

| Symbol | 30 Oct utilisation | In ban 12 Oct - 2 Nov |
|---|---|---|
| KAYNES | 92.17% | yes, currently |
| BANDHANBNK | 85.98% | yes, released 14 Oct |
| MANAPPURAM | 85.67% | no |
| SAIL | 84.93% | yes, currently |
| LICHSGFIN | 84.37% | yes, released 14 Oct |
| INOXWIND | 84.32% | no |
| AMBUJACEM | 81.82% | yes, released 28 Oct |

That is what hysteresis predicts: a scrip released at or below 80% sits in the band afterwards
rather than falling away from it. I derived the mechanism from the clause on 1 Nov; this is the
distribution agreeing with it, from files I did not have at the time.

**Still to do:** download `combineoi` for 12, 13, 14, 26 and 28 Oct, then forecast each
transition from the day before it and score it. That is the test the 30 Oct run could not
provide, because only the hold branch fired there.

## Scoring the ban rule against NSE, 12 Oct to 2 Nov 2026

Run on 6 Nov across every `combineoi` on disk. For each measurement day the seed is **that
day's published ban list**, resolved to ISINs through that day's `combineoi` (per #011 Q2,
since `fo_secban` carries no ISIN); the input is that day's utilisation; the answer is the next
day's published ban list. Nothing reads the `combineoi`'s own `No Fresh Positions` flag, so no
step in the chain sees the answer.

| measurement | forecast for | agree | false pos | false neg |
|---|---|---|---|---|
| 12 Oct | 13 Oct | 213/213 | 0 | 0 |
| 13 Oct | 14 Oct | 213/213 | 0 | 0 |
| 14 Oct | 15 Oct | 213/213 | 0 | 0 |
| 15 Oct | 16 Oct | 213/213 | 0 | 0 |
| 26 Oct | 27 Oct | 213/213 | 0 | 0 |
| 27 Oct | 28 Oct | 213/213 | 0 | 0 |
| 28 Oct | 29 Oct | 219/219 | 0 | 0 |
| 29 Oct | 30 Oct | 218/218 | 0 | 0 |
| 30 Oct | 2 Nov | 218/218 | 0 | 0 |
| **total** | | **1933/1933** | **0** | **0** |

Two days are reported as unscored rather than scored against the wrong answer: 26 Aug, whose
own ban list is not downloaded, and 2 Nov, whose next trading day is 3 Nov and that ban list
is not on disk either. The scorer names both and drops them.

All seven transitions were forecast correctly, and the utilisation at the prior close shows
which branch fired:

| effective | symbol | direction | utilisation at prior close |
|---|---|---|---|
| 13 Oct | KAYNES | entry | 97.98% |
| 14 Oct | BANDHANBNK | release | 79.41% |
| 14 Oct | LICHSGFIN | release | 78.82% |
| 15 Oct | SAIL | entry | 95.01% |
| 28 Oct | AMBUJACEM | release | 70.02% |
| 28 Oct | KAYNES | release | 66.96% |
| 29 Oct | KAYNES | entry | 95.67% |

Three entries all just above 95%, four releases all at or below 80%, and nothing in the fifteen
points between - the hysteresis band, empty of transitions by construction.

**SAIL on 15 Oct is the row that justifies the wording.** At the 14 Oct close its FutEq OI was
95.0135% of its MWPL, which is **29,360 shares**
past the line on a limit of 217 million, one part in seven thousand. NSE banned it. Para 5.2.6
says "exceeds", so the config operator is `>`; I noted on 1 Nov that a scrip sitting exactly on
95% is therefore not in ban, which read as pedantry about a single word. This row is 0.0135 of a
percentage point from being the case that tests it.

**What the 1933 does and does not establish.** All but a couple of dozen of those scrip-days are a security nowhere
near either threshold staying nowhere near it, so the number is a statement about false alarms:
zero, across 1933 scrip-days. The test of the *logic* has a sample of **seven**. Still untested:
the exact boundaries (95.01% is not 95.00%, and no row has ever sat on either line), a missing or
unknown prior state (every scored day had its seed), and a newly listed scrip near a threshold -
the universe moved 213 to 219 to 218 within the sample, so new scrips did appear, none of them
close to a line.

## SAIL's release, and the score to 9 Nov 2026

Scored 9 Nov, after downloading the 3, 4 and 5 Nov ban lists and `combineoi` files (checksums
above). The SAIL check was set up to catch a release on 3 Nov; the 2 Nov file already said there
would not be one - 84.70%, inside the band, with NSE's own flag set for the next day - so the six
files cover the whole walk down instead:

| Close | SAIL utilisation | In ban that day | `No Fresh Positions` | Next list has SAIL |
|---|---|---|---|---|
| Mon 2 Nov | 84.70% | yes | set | 3 Nov: yes |
| Tue 3 Nov | 84.10% | yes | set | 4 Nov: yes |
| Wed 4 Nov | 80.51% | yes | set | 5 Nov: yes |
| Thu 5 Nov | 79.52% | yes | not set | 6 Nov: **no** - release |
| Fri 6 Nov | 82.79% | **no** | not set | 8 Nov: no |

**Both sides of the band on one stock in one week.** On 4 Nov SAIL is 0.51 points above the
exit and is held. On 6 Nov it is *higher* than on the 4th and stays out. The only thing that
differs is yesterday's state, which is the whole of the hysteresis rule, and the forecast gets
both right. Neither is a boundary test: 80.51% and 79.52% are half a point either side of the
line, not on it.

**The score, every measurement day on disk:**

| measurement | forecast for | agree | false pos | false neg |
|---|---|---|---|---|
| 12 Oct to 30 Oct | 13 Oct to 2 Nov | 1933/1933 | 0 | 0 |
| 2 Nov | 3 Nov | 218/218 | 0 | 0 |
| 3 Nov | 4 Nov | 218/218 | 0 | 0 |
| 4 Nov | 5 Nov | 218/218 | 0 | 0 |
| 5 Nov | 6 Nov | 218/218 | 0 | 0 |
| 6 Nov | 8 Nov | 218/218 | 0 | 0 |
| 8 Nov | 9 Nov | 218/218 | 0 | 0 |
| **total** | | **3241/3241** | **0** | **0** |

Eight transitions, all forecast correctly: the seven above plus **SAIL's release effective 6 Nov,
from 79.52%**. Three entries, five releases.

The last two rows are the first forecasts scored **through the Muhurat session**, which the
calendar refused until the `chaining_verified` row went in on 9 Nov (#013 addendum). They are
correct, but they do not test the chaining verdict: KAYNES is the only ban on all three days, so
the skip reading would have scored the same.

**Two better numbers than the 3241.** Of those scrip-days, 31 are banned in NSE's answer, so a
model answering "never banned" scores 99.04%. The sample that tests the band is the **101
scrip-days that closed inside it** (above 80%, at or below 95%), where the right answer depends
only on the previous day: **27 were held** because they were in ban, and **74 stayed out**
because they were not. A single threshold at 95% gets the 27 wrong; a single threshold at 80% gets
the 74 wrong. The engine gets all 101.

Still untested, unchanged from above: either line exactly, a missing prior state, and a new
scrip near a line.

## Scoring through the store rather than from the files

`scripts/score_bans.py` re-reads every file on each run, which is the right shape for a
one-off check and the wrong shape for something that runs nightly. `sentinel.ingest` loads the
same files into the point-in-time store (`DECISIONS.md` #012) and the score comes out of the
store instead:

    8 day(s) scored, 1719 of 1719 scrip-days agree

Fewer days than the script's nine, and for a reason worth recording: storing a day's `official`
state needs that day's `combineoi` as well as its ban list, because `fo_secban` carries no ISIN
and the store is keyed on ISIN (#011 Q2). So 16 Oct and 3 Nov have a stored forecast and no
answer beside them - their ban lists are on disk, their `combineoi` files are not - and 12 Oct
and 26 Oct have an answer with no forecast, being the earliest measurement day in each run.
Those four are the edges of the sample, not failures.

`load_official_day()` currently requires the ban list and the `combineoi` to be for the **same
date**, which is stricter than #011 Q2 specified ("a `combineoi` for a date close enough to
resolve every symbol in it"). The strictness cost three days of coverage on 7 Nov and was
resolved by downloading three more `combineoi` files rather than by relaxing the rule, so no
row's ISINs are resolved from a different day's file.

Two properties make the load safe to repeat, which is what `PLAN.md` D5 means by safe re-runs:

* loading the same file twice is a **no-op** - every value already stored and identical;
* loading a *different* file for a day already stored is a **conflict**, raised with both
  values and the scrips named. An input that changed under us is a finding rather than
  something to overwrite, and the `input_sha256` on every row is what makes it detectable.

## The year's replay, 1 Oct 2025 to 9 Nov 2026 (run 11 Nov 2026)

Every session from the first day of the 2025/79 regime (#020) to the last published list: 273
`combineoi` files and 273 ban lists, all downloaded by hand and recorded with their sha256 in
`docs/data_manifest.csv`. The calendar covers 2025 from NSE/FAOP/65588 and 2026 from
NSE/FAOP/71777, with 15 Jan 2026 added from NSE/FAOP/72262. Two of the 273 are Muhurat sessions,
21 Oct 2025 and 8 Nov 2026; both chain, from their own files (#013). The lists are consecutive in
the calendar, with no gap that could split a ban in two.

Reproduce it with `python scripts/score_bans.py` (the score) or by running
`python -m sentinel.runner` for each session (the whole pipeline). Both were run on 11 Nov 2026,
after the Decimal fix below.

### The score

| | |
|---|---|
| Forecasts scored | 272 (9 Nov 2026's answer, 11 Nov's list, was not yet published) |
| Scrip-days agreeing | 56,997 of 56,997 |
| Transitions forecast correctly | 90 of 90: 45 entries, 45 releases |
| Scrip-days in the 80-95% band | 1,130: 342 held, 788 stayed out, 0 wrong |
| "Never banned" baseline | 99.25% |
| Runner, all 273 sessions | 273 COMPLETED; the only refusal was row 6 (no book, no deltas), every day |
| Forecasts scored inside the store | 56,972 of 56,972 - 25 fewer than the score, the 25 times a scrip left F&O overnight and the next day has no row to pair with |

### The bans

46 episodes across 11 stocks, 428 banned scrip-days, median episode 9 sessions. One episode was
already open on the first list (SAMMAANCAP, 1 Oct 2025) and one still open on the last.

| Longest bans | From | To | Sessions |
|---|---|---|---|
| SAIL | 27 Aug 2026 | 8 Oct 2026 | 29 |
| SAMMAANCAP | 26 Feb 2026 | 25 Mar 2026 | 19 |
| KAYNES | 2 Jun 2026 | 24 Jun 2026 | 17 |
| SAIL | 5 Mar 2026 | 30 Mar 2026 | 17 |
| AMBUJACEM | 5 Oct 2026 | 27 Oct 2026 | 16 |

| Most banned | Sessions in ban | Episodes |
|---|---|---|
| SAIL | 133 | 10 |
| SAMMAANCAP | 93 | 10 |
| KAYNES | 69 | 9 |
| BANDHANBNK | 39 | 5 |
| LICHSGFIN | 20 | 3 |
| MANAPPURAM | 20 | 1 |

### How close the lines came

No real row closed exactly on either line, so the boundaries remain tested only on synthetic files.

- **Entry, 95%:** SAIL on 14 Oct 2026, 95.013539% (+0.0135 pts), banned next day. Then KAYNES on
  9 Jul 2026, 95.017405%, and SAIL on 24 Oct 2025, 95.023006%. All three were forecast correctly.
- **Exit, 80%, any scrip:** LICI on 21 Aug 2026, 80.003951% (+0.0040 pts), but LICI was free, so it
  does not test the exit's inclusivity.
- **Exit, 80%, a scrip in ban** - the case that would: BANDHANBNK on 21 Sep 2026, 80.140048%
  (+0.14 pts), held. The closest release came from LICHSGFIN at 79.79%, effective 11 Sep 2026.

### Reconciliation: one real disagreement, and one bug of mine

`0.95 x MWPL - FutEq OI` against NSE's published `Limit for Next Day`, signed, in `[0, 1)`:
56,786 of 56,787 rows. The notional formula matches 22, coincidence. All 428 rows NSE flagged
`No Fresh Positions` sat above the 80% exit.

- **TRENT, 3 Jun 2026: the one disagreement.** NSE published one share less than truncating the
  exact formula gives (residual +1.3137). The safe direction - less headroom, not more - and the
  cause is not visible in the file. Kept failing, as a known exception, in
  `tests/test_nse_local.py`; widening the test to pass it would discard the finding.
- **NAM-INDIA, 7 Apr 2026: a float bug, now fixed.** Its exact headroom was a whole number and NSE
  published exactly it; float arithmetic put ours 4e-9 below. Five rows in the year have a
  whole-number exact headroom, and this was the one where the float error went negative. FutEq OI
  is now parsed, stored and computed as an exact Decimal, and a float is refused (`ef23129`).

### MWPL resets: all four quarters observed

| Reset | MWPL changed |
|---|---|
| 31 Dec 2025 -> 1 Jan 2026 | 159 of 208 scrips |
| 30 Mar -> 1 Apr 2026 (31 Mar was a holiday) | 153 of 205 |
| 30 Jun -> 1 Jul 2026 | 153 of 210 |
| 30 Sep -> 1 Oct 2026 | 158 of 213 |

Overnight, on the first trading day of each quarter, and nowhere else at that scale. The data
now supports `reset_calendar: [1, 4, 7, 10]` for every month, but `config/rules.yaml` still
records it as an assumption until the observation is written there, sourced to these eight
files. The 1 Oct 2025 reset itself falls just before the window and is not seen.

On eight other days a single scrip's MWPL moved mid-quarter (for example 14 Nov 2025 and 13 Jan
2026): not a reset, most likely a corporate action changing the share count. That is the kind of
change the reference-data detector is for.

## NSE's expiry calendar is Tuesday, moved earlier for holidays

Read out of the bhavcopies on 8 Nov 2026, after an assumption of last-Thursday expiry sent one
download to the wrong date. SEBI moved expiry days in 2025, so the long-standing convention no
longer holds.

| Monthly expiry | Day | Why |
|---|---|---|
| 27 Oct 2026 | Tuesday | the normal day |
| 23 Nov 2026 | **Monday** | Tue 24 Nov is Guru Nanak Jayanti |
| 29 Dec 2026 | Tuesday | Wed 30 Dec is a trading day, so no move |
| 25 Jan 2027 | **Monday** | Tue 26 Jan is Republic Day |

The shift is **earlier**, not later. Two of three monthlies in the sample moved, so a computed
"last Tuesday" would be wrong twice in three months, and wrong in the direction a calculation
does not guess. That is why `DECISIONS.md` #014 reads each contract's own `expiry` field.

`BhavCopy_NSE_FO_..._20261029` is kept even though it answered nothing, because the fact that it
contains **no contract expiring 29 Oct** is what disproved the assumption.

### An expiring contract is in the end-of-day position on its own expiry day

From the 27 Oct file, the October monthly expiry:

    contracts expiring 27 Oct, in the 27 Oct file : 16,961
    of which open interest > 0                    : 13,590
    total open interest across them               : 7,304,736,812

That settles the baseline threshold at a strict `expiry < today` rather than `expiry <= today`,
and therefore that rolling on expiry day is permitted - see #014 decision 7. By the next day the
contracts are gone: nothing expiring on or before 27 Oct appears in the 29 or 30 Oct bhavcopy,
or in `Contract_Delta_30102026.csv`.

## The trading calendar, and the clearing list that is not the same thing

`config/calendar_2026.csv` is generated from **NSE circular NSE/FAOP/71777, Ref 212/2025, dated
12 Dec 2025** - the PDF above. It notifies the F&O trading holidays for calendar year 2026:
fifteen weekday holidays, four falling on a Saturday or Sunday, and one line that decided a
design question:

> *Muhurat Trading will be conducted on Sunday, November 08, 2026. Timings of Muhurat Trading
> shall be notified subsequently.*

So 8 Nov 2026 is a listed Sunday holiday **with a session on it**. That is why a date has four
states rather than three; see `DECISIONS.md` #013.

Two dates this settles that were previously guesses:

* **20 Oct 2026 is Dussehra** (item 12). It had been `UNKNOWN` - no ban list on disk - and on
  6 Nov Claude wrongly concluded from a 404 that it was a holiday and wrote that into this file
  and a commit. The circular makes it a deduction from a primary source instead.
* **The 30 Oct to 2 Nov gap** is a plain weekend, so the one row in the scoring that rested on
  an inference now rests on the circular.

### Trading holidays are not clearing holidays

NSE publishes a separate clearing-holiday list. There was no download option for it, so it is
reproduced below as pasted text and is therefore **unverified** in this project's sense - no
file, no checksum. It is used for nothing; it is recorded because the comparison matters.

It is a **superset** of the trading holidays. Every trading holiday appears in it, plus five
dates in 2026 when the market trades and the clearing corporation is shut:

| Date | Day | Description |
|---|---|---|
| 15 Jan 2026 | Thursday | Municipal Corporation Election in Maharashtra |
| 19 Feb 2026 | Thursday | Chhatrapati Shivaji Maharaj Jayanti |
| 19 Mar 2026 | Thursday | Gudhi Padwa |
| 1 Apr 2026 | Wednesday | Annual Bank Closing |
| 26 Aug 2026 | Wednesday | Id-E-Milad |

This looked load-bearing, because `combineoi` is served from the clearing corporation's own
archive path - `/archives/nsccl/mwpl/`, where `nsccl` is NSE Clearing. If the MWPL file were not
published on a clearing holiday, each of those five dates would be a trading day with no
measurement file, which #012's four-case matrix reads as "missing file, state unknown, refuse
the dead zone". That would be a false alarm: the file would never have been published rather
than lost.

**It is not load-bearing.** All five dates had passed, so one download settled it:
`combineoi_26082026.zip` exists, parses, and carries 211 rows for 26 Aug 2026 - a clearing
holiday that was a trading day. The calendar needs one axis, not two.

**That is one observation of five dates, and one of the two daily files.** A systematic
non-publication would have shown up here, which is why it is acted on, but it is n=1 and is not
a rule. The ban-list half is untested; `fo_secban` is served from `/archives/fo/sec_ban/` - the
F&O segment rather than the clearing corporation - and the segment was open that day, which is
reasoning and not a file. `fo_secban_26082026.csv` would close it for 62 bytes.

### The Muhurat session chains (observed 9 Nov 2026)

The circular says a session happens on Sunday 8 Nov; it does not say whether that session is the
previous trading day for Monday 9 Nov. I settled it from NSE's own end-of-day files for Friday
6 Nov, Sunday 8 Nov and Monday 9 Nov (the last five rows of the checksum table above):

* **The Sunday files exist, and are dated Sunday inside.** `combineoi_08112026.zip` carries
  `08-NOV-2026` on every row; `fo_secban_08112026.csv` is headed "For Trade Date 08-NOV-2026".
* **Sunday was measured, not copied.** FutEq OI differs from Friday's on 218 of 218 scrips, with
  the same scrip set. MWPL is unchanged on all of them, as it should be inside a quarter.
* **Sunday's limits were recomputed from Sunday's OI.** "Limit for Next Day" equals
  floor(0.95 x MWPL - FutEq OI) on 217 of 217 scrips, and KAYNES carries "No Fresh Positions".
  The file names no date for that limit; that the next session is 9 Nov is the calendar's
  inference, not something the file says.

**What did not discriminate:** the three ban lists are identical - KAYNES alone on 6, 8 and
9 Nov - so with no transition over the weekend, "Sunday chains" and "Sunday is skipped" predict
the same lists. The lists are consistent with chaining; they are not the evidence for it. The
evidence is that NSE ran a full end-of-day cycle on Sunday, which is what a link in the chain is.

Recorded as a `chaining_verified` row in `config/calendar_2026.csv`, sourced to these files and
their checksums, and in `DECISIONS.md` #013.

## `combineoi_<ddmmyyyy>.zip` — MWPL and utilisation, per single stock
Archive of a CSV and an XML with the same 218 records. **Use the CSV.** The XML is not
well-formed: its tag is `<Future Equivalent Open Interest>`, with spaces in the element name,
which no conforming XML parser will accept.

`Date, ISIN, Scrip Name, NSE Symbol, MWPL, Open Interest, Future Equivalent Open Interest,
Limit for Next Day`

This is the file clause 3.3.2.1.3 requires NSE to disseminate: ISIN, name, symbol, MWPL in
shares, OI in shares. MWPL and both OI columns are share counts; FutEq OI is fractional.
`Limit for Next Day` is either a number of shares or the literal `No Fresh Positions`.

- Covers **single stocks only** (218 on 30 Oct). Indices are absent, because MWPL does not apply
  to them — they are governed by the index position limits of SPEC row 13 instead.
- **`Limit for Next Day` = 0.95 x MWPL - FutEq OI**, exact on 216 of 216 numeric rows (median
  residual 0.5 share, rounding). It does **not** reconcile against notional OI: 0 of 216. So
  NSE's own headroom is computed on the futures-equivalent basis, not the notional one.

### MWPL resets on the first trading day of the quarter: October observed (10 Nov 2026)

Every scrip's MWPL compared across the 18 `combineoi` files in `data/`, 26 Aug to 8 Nov 2026:

| Files | Scrips whose MWPL changed |
|---|---|
| 26 Aug -> 30 Sep | 0 of 210 |
| **30 Sep -> 1 Oct** | **158 of 213** |
| 1 Oct -> 12 Oct, and every pair after it to 8 Nov | 0 |

So MWPL is recalculated once, overnight, effective **Thu 1 Oct 2026**, the first trading day of
the quarter (2 Oct was a holiday), and holds still between resets. The evidence is the two files
either side: `combineoi_30092026.zip` (sha256 `677053ce...eba5`) and `combineoi_01102026.zip`
(sha256 `460f6a8e...90f5`), full hashes in the table above. SEBI 2025/79 para 5.2.4 says
"quarterly" and names no months, so this is an **observation, not a circular**, and it covers
**October only**. `rules.yaml`'s `reset_calendar: [1, 4, 7, 10]` stays an assumption for January,
April and July until each is seen the same way.

Open: **55 of 213 scrips kept the same MWPL across the reset.** A recalculation on rolling
three-month ADDV would move almost every limit, so something else binds for those 55. Which of
MWPL's limbs binds is already on the gaps list in `LEARNING.md`.

Also seen in the same comparison: 3 scrips added and 1 removed between 26 Aug and 30 Sep, and 6
added on 28 Oct - changes to the F&O list itself, which the reference-data detector is for.

### The FutEq basis was already in force on 1 Oct 2025 (checked 11 Nov 2026)

The first file of the replay window, `combineoi_01102025.zip`, carries the same eight columns as
today's, including `Future Equivalent Open Interest`, and its `Limit for Next Day` matches
`0.95 x MWPL - FutEq OI` on **207 of 207** numeric rows and the notional formula on **0 of 207**.
The same test gives 208 of 208 on 31 Jul 2026 and 216 of 216 on 30 Oct 2026. That agrees with
2025/79 para 6 (table above): FutEq OI was "already implemented", and what changed on
1 Oct 2025 was the MWPL definition, position creation during the ban period, and entity limits.
So 1 Oct 2025 is the first day of the regime this project implements, and the replay starts
there, not earlier.

Archive depth, checked by hand on 10 Nov 2026: both daily files download for Fri 31 Jul 2026
and Wed 1 Oct 2025, so NSE's archive reaches at least 1 Oct 2025. Five `combineoi` files (16, 19,
21, 22, 23 Oct 2026) took 2 minutes 3 seconds by hand, about 25 seconds a file.

## `combineoi_deleq_<ddmmyyyy>.csv` — delta-equivalent OI, stocks and indices
`Date, ISIN, Scrip Name, Symbol, Notional Open Interest, Portfolio-wise Futures Equivalent Open
Interest`

227 records: the same 218 stocks plus 9 indices (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY,
NIFTYNXT50, SENSEX, BANKEX, NIFTYFPI, FOCIT), which carry no ISIN or scrip name.

The FutEq OI column is **identical** to `combineoi`'s for all 218 shared stocks — maximum
difference 0.00 shares. The word "Portfolio-wise" matches para 5.1's netting convention.

## `Contract_Delta_<ddmmyyyy>.csv` — NSE's published per-contract deltas
`Date, Symbol, Expiry day, Strike Price, Option Type, Delta Factor`

133,620 rows for 30 Oct: every contract, every strike, every expiry. `Option Type` is `FF` for a
future (Delta Factor exactly 1.0), otherwise the option type. Strike is 0.0 for futures.

## `fo_secban_<ddmmyyyy>.csv` — the ban list
Not a CSV with a header row. Line 1 is prose (`Securities in Ban For Trade Date 02-NOV-2026:`),
then one `<n>,<SYMBOL>` line per banned security. A parser that calls `read_csv` on it directly
will treat the prose line as column names.

On both 30 Oct and 2 Nov: KAYNES and SAIL. The same two are also the rows flagged
`No Fresh Positions` in the 30 Oct `combineoi` file, so all three sets are identical.

I originally read that coincidence as proof that the `combineoi` flag is NSE's T+1 ban
declaration. It was not proof: a ban persisting across both days looks the same under either
reading, so those three files could not distinguish them. **The conclusion was right and the
reasoning was not**, which is worth separating, because the first one is luck.

**Settled on 6 Nov, with evidence that discriminates.** With seven `combineoi` files and fifteen
ban lists, the flag can be compared against both candidate dates on days when they differ:

| `combineoi` date | flag set | = that day's ban list? | = next trading day's? |
|---|---|---|---|
| 12 Oct | AMBUJACEM, BANDHANBNK, KAYNES, LICHSGFIN | no | **yes** |
| 13 Oct | AMBUJACEM, KAYNES | no | **yes** |
| 14 Oct | AMBUJACEM, KAYNES, SAIL | no | **yes** |
| 26 Oct | AMBUJACEM, KAYNES, SAIL | yes | yes |
| 27 Oct | SAIL | no | **yes** |
| 28 Oct | KAYNES, SAIL | no | **yes** |
| 30 Oct | KAYNES, SAIL | yes | yes |

T+1 on all seven, and on **five** of them the two candidates differ, so those five discriminate.
The two that match both are days where nothing changed - which is why 30 Oct on its own could
never have settled it.

So the `No Fresh Positions` flag in day T's file is NSE's ban declaration for T+1. It also means
the answer to the ban question is in the same file as the inputs, so reproducing it is a
reconciliation and not a forecast with any time advantage.

Scoring a forecast against this file therefore works, but only when the seed comes from the
previous trading day's ban list. Seeded from the `combineoi` flag the agreement is circular,
because both banned scrips sit in the 80-95% band where the forecast is the seed.

## `BhavCopy_NSE_FO_..._F_0000.csv.zip` — UDiFF F&O bhavcopy
34 columns, including `TckrSymb`, `XpryDt`, `StrkPric`, `OptnTp`, `ClsPric`, `UndrlygPric`,
`SttlmPric`, `OpnIntrst`, `ChngInOpnIntrst`, `NewBrdLotQty`. This is the post-7-Dec format.
