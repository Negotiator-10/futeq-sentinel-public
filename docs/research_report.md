# Replay NSE position limits before the exchange does

The best under-served project for this candidate is an **open-source NSE F&O position-limit and ban-period replay engine**. It would ingest the public UDiFF bhavcopy and open-interest files, recompute the delta-based futures-equivalent (FutEq) open-interest regime that took effect on **1 Oct 2025**, check a synthetic prop book against the entity and intraday limits, and add an order-to-trade-ratio (OTR) estimator for the Feb 2026 revision. The project has five things going for it:

- **The pain is recent and documented.** It is arguably the largest new data burden placed on Indian prop and HFT desks in 2024-2026: more than ten new or changed member files, random intraday exchange snapshots, and per-day penalties ([NSE Clearing FAQ](https://www.nseclearing.in/sites/default/files/2025-10/Recent%20changes%20in%20Equity%20Derivative%20segment%20focusing%20on%20position%20limits%2C%20Limit%20Monitoring%2C%20and%20Securities%20in%20Ban%20Period.pdf)).
- **Vendors and open source leave a gap.** Indian OMS/RMS vendors sit in the pre-trade order path, and open source stops at downloading data. Nothing public replays these calculations. This is inferred from the absence of products, not proven.
- **One person can build it in Python** on public files plus synthetic positions.
- **It can be checked against public ground truth.** NSE's own published market-wide limit utilisation and ban list give an external benchmark, which most portfolio projects lack.
- **It speaks to the roles this candidate can realistically get.** Trade-operations, developer-support, risk-tech and quant-dev (data) roles at NK Securities, iRage, AlphaGrep and similar firms. Core low-latency C++ roles remain a stretch whatever the project.

PMS, Cat III AIF and wealth-management pains are real and well evidenced: three-way reconciliation, high-water-mark fee illustrations, TWRR reporting, multi-regime capital gains. But they signal weakly to HFT recruiters, and in-house tools or casparser-style libraries already cover parts of them. Treat them as extensions, not the main project.

Many regulatory details here come from law-firm, broker and news summaries rather than circular text. The last section lists what must be checked on sebi.gov.in and nseindia.com before any of it goes into a public README.

## SEBI added five data-heavy F&O obligations in 18 months, and prop desks absorb most of them

### HFT and prop firms: the delta-based limit regime is the new daily chore

From Oct 2024 to Apr 2026, SEBI and the exchanges layered several obligations onto derivatives traders.

**The Oct 2024 F&O package.** SEBI's 1 Oct 2024 circular ([SEBI circular PDF](https://avantiscdnprodstorage.blob.core.windows.net/legalupdatedocs/35680/SEBI_issued_a_circular_regarding_the_Measures_to_Strengthen_Equity_Index_Derivatives_Framework_for_Increased_Investor_Protection_and_Market_Stability_October012024.pdf)) brought in:

- index contract sizes raised to **Rs 15-20 lakh** ([mStock](https://www.mstock.com/articles/new-f-and-o-margin-norms))
- one weekly expiry per exchange
- an extra 2% ELM on expiry day
- upfront collection of option premium

Lot sizes changed while existing contracts kept their old lots until expiry. NIFTY went from 25 to 75, so old and new lot sizes ran side by side for a while, a reference-data hazard of exactly the kind firms script around ([Zerodha](https://zerodha.com/z-connect/business-updates/sebis-new-rules-for-index-derivatives-heres-whats-changing)).

**The delta-based limit regime (largest change).** SEBI circular 2025/79 (29 May 2025) took effect on 1 Oct 2025. It changed both how open interest is measured and how limits are set and enforced ([NSE Clearing FAQ](https://www.nseclearing.in/sites/default/files/2025-10/Recent%20changes%20in%20Equity%20Derivative%20segment%20focusing%20on%20position%20limits%2C%20Limit%20Monitoring%2C%20and%20Securities%20in%20Ban%20Period.pdf)):

- **Open interest is now delta-based.** It is measured as net futures-equivalent exposure per underlying across futures and options.
- **MWPL has a new formula.** It is the lower of 15% of free float and 65 times average daily delivery value, with a floor of 10% of free float, recomputed quarterly.
- **Ban thresholds.** A stock enters the ban at 95% of MWPL and exits at 80%.
- **Single-stock entity limits:**

  | Holder | Limit |
  |---|---|
  | Client | 10% of MWPL |
  | Trading-member proprietary book | 20% of MWPL |
  | Combined | 30% of MWPL |

- **Ban-period violations.** The check stores a Day-1 base position and values the Day-2 end-of-day position at the 2 PM delta from the SPAN file. Any increase in FutEq or any sign flip counts as a violation.
- **Penalty.** The lower of 1% of the violating value and Rs 1 lakh, with a floor of Rs 5,000, charged per entity per stock per day.
- **Files.** Members must ingest more than ten new or changed files: DELOI, Contract_Delta, combineoi, MWPL base and violation files.

**Intraday index-option limits.** SEBI circular 2025/122 added an intraday net FutEq limit of **Rs 5,000 cr** and a gross limit of **Rs 10,000 cr** per entity, on top of the Rs 1,500 cr end-of-day limit. NSE checks them through at least four random snapshots a day ([NSE SURV70553](https://nsearchives.nseindia.com/content/circulars/SURV70553.pdf); [SEBI](https://www.sebi.gov.in/legal/circulars/sep-2025/framework-for-intraday-position-limits-monitoring-for-equity-index-derivatives_96376.html)). Because the snapshots are random, a single end-of-day check is no longer enough; firms need near-continuous self-monitoring. NSE's SOP even gives the column layout of a compliant monitoring report:

- Contract
- Long Qty
- Short Qty
- Delta
- FutEq Qty
- Position Value
- Limit
- Violation

That layout is, in effect, a free specification for a portfolio project.

**OTR revision.** SEBI revised the OTR framework on 4 Feb 2026 ([SEBI](https://www.sebi.gov.in/legal/circulars/feb-2026/revision-of-order-to-trade-ratio-otr-framework_99501.html)). News reports say two kinds of orders are now exempt from the high-OTR penalty:

- orders within **±0.75% of LTP** ([Moneycontrol](https://www.moneycontrol.com/news/business/markets/sebi-relaxes-otr-norms-for-equity-options-exempts-market-makers-algo-orders-13811416.html))
- equity option orders within ±40% of premium or Rs 20

NSE ran a mock session on 14 Mar 2026 so members could prepare ([NSE mock-trading circular](https://avantiscdnprodstorage.blob.core.windows.net/legalupdatedocs/53595/NSE-issued-a-circular-regarding-Mock-trading-on-Saturday-March-14-2026-Revision-of-OrdertoTrade-Ratio-OTR-framework-No-new-version-release-March132026.pdf)). An internal OTR pre-check now needs each order's price relative to LTP, not just order counts.

**Enforcement backdrop.** SEBI's interim order against Jane Street (3 Jul 2025) alleged expiry-day index manipulation and "extended marking the close", and directed an escrow of **Rs 4,843.57 cr** ([SEBI order](https://www.sebi.gov.in/enforcement/orders/jul-2025/interim-order-in-the-matter-of-index-manipulation-by-jane-street-group_95040.html)). Reuters reports the probe began from exchange surveillance alerts and that cross-geography booking complicated the investigation ([Reuters](https://www.reuters.com/sustainability/boards-policy-regulation/how-india-struggled-regulate-jane-streets-money-spinning-machine-2025-08-14/)). The order remains interim and Jane Street denies the charges. The research found no final order or Securities Appellate Tribunal outcome by Oct 2026.

**Evidence quality.** The burden itself is well documented. How firms handle it day to day is not. No Indian HFT firm has published its reconciliation or limit-monitoring workflow. The best indirect evidence is job titles: NK Securities hiring "Trade Operations Engineers" ([Indeed](https://in.indeed.com/q-hft-l-anywhere-jobs.html), listing since expired) and iRage hiring "Developer Support Engineers" ([Naukri](https://www.naukri.com/hft-jobs)). Both point to an operations layer of start-of-day checks, exchange-file processing and limit monitoring.

### PMS and Cat III AIFs: per-client calculation and reconciliation, not market data

Portfolio managers took on several new per-client calculation duties:

- **Benchmarking (from 1 Apr 2023).** Each investment approach must be tagged to one of four strategies and benchmarked against an APMI-prescribed index ([Business Standard](https://www.business-standard.com/article/markets/sebi-issues-performance-benchmarking-guidelines-for-portfolio-managers-122121600879_1.html)). Smaller firms sought an extension, citing "technological and compliance challenges" ([Business Standard](https://www.business-standard.com/article/markets/pms-benchmarking-norms-industry-players-seek-three-month-extension-123030101080_1.html)).
- **Fee tools (from 1 Oct 2024).** Each new client must receive a fee-calculation tool with high-water-mark (HWM) projections, plus 1-year and multi-year illustrations under up, flat and down scenarios ([K&S Partners](https://ksandk.com/newsletter/sebi-circular-update-enhancing-transparency-and-ease-in-portfolio-management-services/)).
- **Proposed derivative limits.** A **Portfolio Managers Regulations 2026** draft proposes derivative exposure up to 1.25x AUM, unhedged shorts up to 50% and options premium capped at 10% ([Cyril Amarchand](https://corporate.cyrilamarchandblogs.com/2026/08/sebis-proposed-overhaul-of-the-pms-regulatory-framework/)). The SEBI board reportedly approved the regulations on 24 Sep 2026, but no gazetted text was found ([Argus](https://www.argus-p.com/updates/updates/sebi-approves-new-portfolio-manager-regulations/)).

Operations work is still staffed by hand. A Head of PMS Operations posting describes daily reconciliation of WealthSpectrum against the custodian, the fund accountant and the bank, plus SEBI periodic reports and audit workpapers ([iimjobs](https://www.iimjobs.com/j/head-pms-operations-1737174)).

Cat III AIFs face their own load:

- a 2x NAV leverage cap
- monthly SEBI reporting for leveraged funds ([CDSL copy of AIF Master Circular](https://www.cdslindia.com/downloads/Publications/Communique/SEBI-CIR-Master-Circular-for-Alternative-Investment-Funds.pdf))
- demat-only holdings
- NAV reporting to depositories (Feb 2026)
- a new Annual Activity Report (Mar 2026) ([Treelife](https://treelife.in/finance/sebi-aif-circular-2024-2025/))

Administrators say managers are "overwhelmed by administrative tasks", and that custodians offer fund accounting only as an ancillary service ([IQ-EQ India](https://iqeq.com/in/insights/the-evolving-role-of-fund-administrators-in-india/)). Cost is part of the problem: one estimate puts a small PMS's minimum compliance cost at about **Rs 31.6 lakh a year** ([Greenportfolio, secondary](https://newsroom.greenportfolio.co/?p=6213)).

### Wealth managers, RIAs and MFDs: fragmented data and multi-regime tax

For advisers, the burden is consolidation and rule logic, not market microstructure.

**Adviser rules.** SEBI's Dec 2024 amendments to the investment-adviser regulations brought in ([AZB](https://www.azbpartners.com/bank/overhaul-of-the-regulatory-framework-for-investment-advisers-and-research-analysts/)):

- a Rs 1.51 lakh fixed-fee cap
- client-level segregation of advisory and distribution
- disclosure of AI use
- e-signed client agreements

**Tax complexity.** Budget 2024 changed capital-gains rates mid-year, on 23 Jul 2024 ([Business Standard](https://www.business-standard.com/amp/finance/personal-finance/budget-2024-all-the-key-changes-to-capital-gains-tax-explained-124072500330_1.html)). Together with Section 50AA for debt funds and the 2018 grandfathering of equity gains, one mutual-fund redemption can now span four or more tax regimes.

**Family offices.** Practitioners say "aggregation remains a pain point in India", with many family offices run on spreadsheets ([Hubbis](https://hubbis.com/article/family-offices-at-a-crossroads-institutionalisation-governance-and-strategic-relevance-in-india)).

**Adviser numbers.** SEBI's chair said in Mar 2026 that registered investment advisers had fallen to about 1,000 ([News On AIR](https://www.newsonair.gov.in/sebi-expresses-concern-over-decline-in-number-of-registered-investment-advisers/)), which shows a compliance-squeezed base.

### Global awareness: the US and EU lean on firm-run controls and attestation

The US market-access rule (SEC 15c3-5) requires automated pre-trade controls and immediate post-trade reports to surveillance staff ([SEC FAQ](https://www.sec.gov/rules-regulations/staff-guidance/trading-markets-frequently-asked-questions/divisionsmarketregfaq-0)). MiFID II RTS 6 requires kill switches and an annual self-assessment, and ESMA has asked whether that self-assessment format should be standardised ([ESMA](https://www.esma.europa.eu/sites/default/files/library/esma70-156-4572_mifid_ii_final_report_on_algorithmic_trading.pdf)).

India differs in one important way. Its limits are **exchange-computed and position-based**: FutEq, MWPL, random snapshots and ban periods. So Indian firms must replicate the exchange's calculations locally. That replication is the gap the recommended project fills. It also gives the project a global framing: a controls engine with an auditable evidence trail.

## Vendors own the order path and the books, leaving post-trade compliance analytics open

The commercial picture splits by layer.

**Indian broking and prop.** A handful of OMS/RMS vendors dominate. Zerodha's CEO names OmneNest, Kambala, 63 Moons and Rupeeseed, and puts OmneNest at about 70% share ([Nithin Kamath](https://nithinkamath.substack.com/p/why-most-brokers-dont-build-their)). Symphony sells an "RMS Compliance Module" for algo approvals ([Marketcalls](https://www.marketcalls.in/algo-trading/understanding-order-management-systems-india.html)). These products are pre-trade and in the order path, and they publish almost nothing about features or pricing.

**Global buy side.** Platforms are consolidating. Clearwater agreed to buy Enfusion for about US$1.5B ([TechCrunch](https://techcrunch.com/2025/01/13/clearwater-agrees-to-buy-investment-management-platform-enfusion-for-1-5b)). Yet Arcesium's own Indian operations postings still list daily street reconciliations, P&L recs and NAV preparation as staffed work ([The Muse](https://www.themuse.com/jobs/arcesium/analysttrade-accounting-and-operations-ac52ed)).

**Indian PMS and AIF.** WealthSpectrum and administrators such as KFintech, SS&C, Apex and IQ-EQ cover the core books, but operations staff still close the breaks ([iimjobs](https://www.iimjobs.com/j/head-pms-operations-1737174)).

**Surveys agree that manual work persists.** In the Dynamo survey, 61% of fund accountants named manual data entry and reconciliation as a top challenge ([BusinessWire](https://www.businesswire.com/news/home/20250220376286/en/Survey-Majority-of-Private-Equity-Venture-Capital-Fund-Accountants-Predict-Tech-Revamps-in-2025)). ACA finds AI use "widespread but shallow", with reconciliation and market-data QC the leading operations use cases ([ACA Group](https://www.acaglobal.com/news-and-announcements/ai-use-in-financial-services-compliance-and-operations-is-widespread-but-shallow-aca-group-survey-finds/)).

Open source is crowded in some areas and close to empty in others. The figures below were pulled from the GitHub API on 28 Oct 2026.

| Area | State of open source | Implication for a portfolio project |
|---|---|---|
| Backtesting / research engines | Crowded: qlib ~49.8k stars, nautilus_trader ~31k, vectorbt ~9.6k ([GitHub API](https://api.github.com/repos/microsoft/qlib)) | Another backtester does not differentiate |
| NSE data download | Served: jugaad-data (590 stars, active), nsepython (371, active); nsepy (807) last pushed Dec 2023 ([GitHub API](https://api.github.com/repos/swapniljariwala/nsepy)) | Another downloader does not differentiate |
| UDiFF format churn | Legacy bhavcopies discontinued 8 Jul 2024 broke parsers ([jugaad-data #79](https://github.com/jugaad-py/jugaad-data/issues/79)); older .MS/.MD formats end **7 Dec 2026** ([NSE MSD76877](https://nsearchives.nseindia.com/content/circulars/MSD76877.pdf)) | Schema-contract and drift detection is a live, dated need |
| Trade reconciliation | No mature library; top hits are toy repos ([GitHub search](https://api.github.com/search/repositories?q=reconciliation+trade+python&sort=stars)) | Open |
| Trade surveillance | Nothing mature for equities ([GitHub search](https://api.github.com/search/repositories?q=trade+surveillance&sort=stars)) | Open, but needs synthetic order data |
| TCA | tcapy is FX-only, last push Feb 2024 ([GitHub API](https://api.github.com/repos/cuemacro/tcapy)) | Open for India, but tick data is not free |
| SEBI circular tracking | Search and Q&A only (india-reg-mcp, ~2,775 circulars indexed ([Socket](https://socket.dev/npm/package/india-reg-mcp))); tiny RAG repos | Search is covered; impact mapping is not |
| FutEq / MWPL / ban / OTR replay | None found in this research | Clearest India-specific gap |
| CAS parsing (wealth) | Solved by casparser ([GitHub](https://github.com/codereverser/casparser)) | Build above it, not instead of it |
| Point-in-time NSE index constituents | No free official archive found; arXiv study rebuilt Smallcap 250 membership ([arXiv 2603.19380](https://arxiv.org/abs/2603.19380)) | Open, but data risk |

One caveat applies to the FutEq row in particular. "No product found" is not proof that none exists. Vendors such as Symphony or Synapsewave may ship FutEq monitors inside their RMS. Even so, their tools are closed, and a public, tested, validated replay engine would still be new in the open-source space.

## Twelve candidate projects, ranked by signal and solo feasibility

Scores run from 1 to 5. "Signal" means signal to quant and HFT recruiters for the roles this candidate can realistically get. "Gap" means how well the research shows the pain and the absence of tools. "Feasibility" means one person, Python, free or synthetic data, in roughly 8-12 weeks. "Fit" means it builds on, but stays distinct from, the candidate's existing VaR, paper-trading and reconciliation work.

| Rank | Project | Pain point and evidence | Why not already solved | Feasibility | Signal | Gap | Fit |
|---|---|---|---|---|---|---|---|
| 1 | **NSE F&O position-limit, ban-period and OTR replay engine** | FutEq/MWPL regime from 1 Oct 2025, 10+ new files, random snapshots, per-day penalties ([NSE Clearing FAQ](https://www.nseclearing.in/sites/default/files/2025-10/Recent%20changes%20in%20Equity%20Derivative%20segment%20focusing%20on%20position%20limits%2C%20Limit%20Monitoring%2C%20and%20Securities%20in%20Ban%20Period.pdf)) | Vendor RMSs are closed and pre-trade; no open replay found | 4 (delta-file access unverified; fallback exists) | 5 | 4 | 5 |
| 2 | UDiFF exchange-file data-contract and EOD reconciliation engine | UDiFF cutover broke parsers; .MS/.MD formats end 7 Dec 2026 ([NSE MSD76877](https://nsearchives.nseindia.com/content/circulars/MSD76877.pdf)) | Downloaders exist, validators do not | 5 | 3 | 4 | 3 (close to existing reconciliation work) |
| 3 | Strategy model-validation report generator (SR 26-2 style) | SR 26-2 issued 17 Apr 2026 ([Federal Reserve](https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm)) | Commercial MRM tools target banks, not trading strategies | 5 | 4 | 2 (weak India evidence) | 3 (extends VaR backtests) |
| 4 | Point-in-time NIFTY constituent dataset builder | Survivor-only backtests overstate returns by ~4.94 pp ([arXiv](https://arxiv.org/abs/2603.19380)) | No free official archive | 3 (data risk) | 4 | 4 | 2 (overlaps existing point-in-time freezing work) |
| 5 | OTR estimator plus expiry-day self-surveillance | 2026 OTR bands; Jane Street order | No open tool; order logs private | 3 (synthetic only) | 4 | 3 | 4 |
| 6 | Retail-algo pre-trade gateway (mini RMS) | Algo-IDs, static IP, order-rate thresholds by 1 Apr 2026 ([Zerodha](https://zerodha.com/z-connect/business-updates/explaining-the-latest-sebi-algo-trading-regulations)) | Vendors already ship this | 4 | 3 (best signal needs C++) | 2 | 3 |
| 7 | Cat III / SIF / PMS-2026 exposure-limit monitor | 2x NAV cap; proposed 1.25x, 50% and 10% PMS limits | PMS 2026 not yet notified | 4 | 2 | 3 | 4 |
| 8 | PMS HWM fee engine plus TWRR and Appendix 5D reporter | Oct 2024 fee-tool mandate | Firms already publish their own calculators ([Anand Rathi](https://www.anandrathipms.com/pms-fees-calculator)) | 5 | 1 | 3 | 3 |
| 9 | Multi-regime MF capital-gains and harvesting engine | 23 Jul 2024 split, Sec 50AA | Vendor platforms partly cover it | 5 | 1 | 3 | 2 |
| 10 | SEBI circular impact mapper (LLM) | Circular churn | Search and RAG exist; impact mapping is new but signals little | 4 | 2 | 3 | 2 |
| 11 | India equities/F&O TCA plus surveillance | tcapy is FX-only | Tick data is not free | 2 | 4 | 4 | 3 |
| 12 | T+0 readiness simulator | Few brokers offered T+0 because of "system limitations" ([Business Standard](https://www.business-standard.com/amp/markets/news/sebi-fires-fresh-shot-at-t-0-revival-market-players-sceptical-of-impact-124100101003_1.html)) | Policy uptake is uncertain | 4 | 1 | 2 | 2 |

The ranking turns on one asymmetry. The PMS and wealth ideas (ranks 7-9) score high on feasibility but low on signal. They show accounting care, not market-structure fluency, and HFT screeners value the latter. Ranks 2 and 5 score well but work best as modules inside rank 1 rather than as separate repos.

Rank 3 is the strongest alternative. It reuses the candidate's Kupiec and Christoffersen validation skills and reads well to quant-research teams globally. It loses on India-specific evidence, and because it sits close to the existing VaR engine it risks looking like the same project again.

Rank 4 has excellent research value but rests on data that may not be freely available after 2022. It also repeats the point-in-time story already told in the paper-trading project.

The honest steelman against rank 1: core HFT developer screens will still test C++ and data structures and algorithms ([AlphaGrep](https://job-boards.greenhouse.io/alphagrepsecurities/jobs/8041041002); [Tara Capital](https://wellfound.com/jobs/1031725-quant-developer)). No Python project changes that. Rank 1 maximises signal for the adjacent roles where Python, domain fluency and data correctness decide the hire.

## Recommendation: a FutEq limit engine validated against NSE's own ban list

### Why this one

The project would be an open-source **"FutEq Sentinel"**: a Python engine that rebuilds NSE's delta-based market-wide and entity-level position-limit calculations from public files, replays them day by day, and checks a synthetic prop book against every limit. A later module estimates OTR under the 2026 bands.

It wins on four grounds:

- **It targets a burden that is under 18 months old,** created by circulars any Indian prop recruiter will recognise.
- **It has an external referee.** The engine's market-wide limit utilisation and next-day ban predictions can be scored against what NSE actually published. Few student projects can make that claim.
- **It shows the right skills.** Options-delta mathematics, exchange file formats, regulatory reading and stateful reconciliation logic are the same skills trade-operations and risk-tech engineers use daily.
- **It reuses the candidate's strongest assets without repeating them.** The point-in-time data freezing and byte-reproducible replay from the paper-trading system become the engine's storage layer, while the subject matter (exchange compliance rather than strategy or VaR) is new.

### The data risk, and how to handle it

The main risk is data access. The member-level DELOI and MWPL base and violation files are private by definition. The research could not confirm whether `Contract_Delta_*` files under FAOCOMMON are downloadable without a member login ([NSE Clearing FAQ](https://www.nseclearing.in/sites/default/files/2025-10/Recent%20changes%20in%20Equity%20Derivative%20segment%20focusing%20on%20position%20limits%2C%20Limit%20Monitoring%2C%20and%20Securities%20in%20Ban%20Period.pdf)).

The plan therefore starts with a one-week feasibility gate and has two paths:

- **Path A:** use NSE's published deltas if they are public.
- **Path B:** compute deltas independently, by implying volatility from public F&O settlement prices and applying Black-76 or Black-Scholes. Then measure the error against whatever NSE does publish.

Path B is arguably the more impressive engineering story, because the residual between the candidate's own deltas and the exchange's figures becomes a documented model-risk finding.

### Phased build plan

The week counts below are estimates for part-time work alongside CPAIF.

| Phase | Weeks | Milestone | Data | Tests and validation |
|---|---|---|---|---|
| 0. Feasibility gate and spec | 1 | List which files are downloadable without login from [NSE All Reports](https://www.nseindia.com/all-reports) and archives: UDiFF F&O and CM bhavcopy, combined OI / MWPL, ban list, contract delta. Choose Path A or B. Write `SPEC.md` mapping each circular clause to a function. | NSE public reports; SEBI circulars 2025/79 and 2025/122; NSE SURV70553 | Every rule in the spec cites a circular paragraph; unknowns are listed explicitly |
| 1. Ingestion and data contracts | 2 | Typed UDiFF parsers (pandera or pydantic schemas), content-hashed point-in-time store, reference-data change detector (lot sizes, expiries, quarterly MWPL resets, new ban entries) | UDiFF bhavcopies since mid-2024; contract master | Schema contract tests; golden-file fixtures; a drift test that fails loudly on a renamed column; ideally demonstrated live across the 7 Dec 2026 .MS/.MD cutover |
| 2. Market-wide engine | 2 | Per-underlying FutEq OI, MWPL utilisation, ban entry at 95% and exit at 80% with hysteresis, next-day ban forecast | Public combined OI / MWPL and ban list (or Path B deltas) | Daily reconciliation of computed against published utilisation, with error distribution; precision and recall of ban forecasts over every trading day since 1 Oct 2025; property tests for hysteresis |
| 3. Entity-level limits on a synthetic book | 2 | Single-stock limits (client 10%, proprietary 20%, combined 30% of MWPL); index-option intraday net (Rs 5,000 cr) and gross (Rs 10,000 cr) limits and the end-of-day Rs 1,500 cr limit; random snapshot simulator (four or more per day); ban-period base-position checker (increase or sign flip); penalty calculator; output in NSE's SOP report columns | Synthetic prop book generated from public contracts and prices | Hand-worked golden cases taken from the FAQ's rules; property tests (for example, reducing exposure without a sign change never creates a violation); penalty-floor and cap edge cases |
| 4. OTR and self-surveillance module | 1-2 | OTR estimator with the 2026 exemption bands as configurable parameters; an expiry-day footprint report (closing-window activity and constituent-versus-index exposure for the synthetic book) | Synthetic order logs; public LTP and closing data | Bands kept in config and labelled "per news reports, pending circular check"; sensitivity table showing OTR under the old and new rules |
| 5. Packaging and write-up | 1-2 | CLI (`sentinel replay --from 2025-10-01`), GitHub Actions CI, type checks, coverage badge, daily HTML limit-utilisation report, 6-10 page technical note | All of the above | Byte-reproducible replay (hash manifest per run day), as in the candidate's earlier project |
| Optional stretch | 2+ | Port the snapshot limit-check hot path to C++ via pybind11 and benchmark it against numpy | Synthetic high-frequency position updates | Python and C++ results must match exactly; latency table in the README |

### What the finished repository shows

A recruiter opening the repo should see five things:

- **A results-first README.** For example: "replayed N trading days since 1 Oct 2025; matched NSE's published ban list on X of Y days; median MWPL-utilisation error Z%; flagged K reference-data changes, including the Dec 2026 format cutover." The numbers are whatever the replay produces, reported honestly, misses included.
- **A spec that maps circular clauses to code.**
- **A test suite that encodes the regulation as executable examples.**
- **A sample daily limit report in the exchange's own column layout.**
- **A short note** on what the engine cannot see (private member files, true intraday positions) and how synthetic data stands in for them.

That combination of domain fluency, data correctness, validation against an external referee and reproducibility is the profile trade-operations engineer and risk-tech roles describe. The optional C++ port is the one addition that would also speak to developer screens.

Natural extensions reuse the same engine:

- a Cat III, SIF or PMS-2026 exposure-limit monitor (rank 7), once the PMS regulations are notified
- a US/EU "controls evidence pack" view mapping the same checks to 15c3-5 and RTS 6 language, for global firms

## Regulatory facts to verify on sebi.gov.in and nseindia.com before stating them publicly

Several facts in this report rest on secondary sources or conflicting dates. Each must be checked against the primary text before it appears in a README, a paper or an interview answer.

| Claim | Why it needs checking | Where to check |
|---|---|---|
| OTR 2026 exemption bands (±0.75% of LTP; options ±40% of premium or Rs 20), market-maker exclusion, 6 Apr 2026 effective date | Full circular not fetched; bands come from Moneycontrol and an X post; market-maker exclusion and date come from an Instagram post | [SEBI OTR circular page](https://www.sebi.gov.in/legal/circulars/feb-2026/revision-of-order-to-trade-ratio-otr-framework_99501.html); NSE circulars |
| MWPL formula, 95%/80% ban thresholds, 10/20/30% limits, penalty slabs, file names | From the NSE Clearing FAQ (near-primary); confirm against SEBI circular 2025/79 and the latest NSE amendments | sebi.gov.in; nseclearing.in |
| Intraday index-option limits effective 1 Oct 2025 | Effective date from secondary reporting ([Oquilia](https://www.oquilia.com/news/sebi-intraday-position-limits-index-derivatives-2025)) | SEBI circular 2025/122; NSE SURV70553 |
| Public availability of Contract_Delta, combined OI and MWPL files without login | Not established in the research | nseindia.com All Reports; NSE Clearing site |
| Retail algo framework deadlines | Sources conflict: a 5 Jan 2026 onboarding bar ([SEBI PDF](https://www.sebi.gov.in/sebi_data/attachdocs/sep-2025/1759232056254.pdf)) versus full compliance on 1 Apr 2026 ([Moneycontrol](https://www.moneycontrol.com/news/business/markets/sebi-extends-timeline-to-rollout-algo-trading-framework-for-retail-with-a-glide-path-for-brokers-13591347.html)) | Latest SEBI circular |
| 2025 weekly expiry-day changes (Tuesday/Thursday) | Not verified from primary sources | NSE and BSE circulars |
| CSCRF compliance deadlines | Sources give 1 Apr 2025, 30 Jun 2025 and 31 Aug 2025 | SEBI CSCRF circulars and FAQ |
| PMS Regulations 2026 contents and status, and the MF-PMS fee cap (1% vs 2.5%) | Board-approved but not gazetted; secondary sources conflict | SEBI gazette notification |
| SIF circular date (27 Feb 2025 vs 2026) | One source dates it 2026, which looks like an error | sebi.gov.in |
| AIF circular numbers and dates (demat, due diligence, NAV reporting, Annual Activity Report) | Taken from law-firm and blog summaries | SEBI AIF Master Circular (a Sep 2026 version appears to exist, unread) |
| Jane Street case status | Interim order only; no final order or SAT outcome found | SEBI enforcement orders; SAT |

## Conclusion

The research points to a broader lesson. In India the scarce skill is not building trading infrastructure but **replicating the regulator's and exchange's arithmetic faster and more reliably than a spreadsheet**. That is because Indian limits are computed by the exchange from positions, not attested by the firm. A fresher who can show code that independently reproduces NSE's ban list, and explain where and why it disagrees, is showing the habits a prop firm's operations and risk desk needs on day one. That stays true even if the C++ screen comes later.

A practical rule follows for future project choices. Prefer problems where a public, authoritative output exists to score your code against (here, NSE's published utilisation and ban list), and where the rules changed recently enough that no polished open tool has caught up. The FutEq regime meets both tests as of late 2026. The upcoming 7 Dec 2026 retirement of the older bhavcopy formats will give a live format-drift event to catch on camera if the build starts now.
