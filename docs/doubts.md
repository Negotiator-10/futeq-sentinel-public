# Doubts log

Every doubt I raise while reading or building goes here. I write it before asking, and once it's cleared I write the answer in my own words. This feeds `LEARNING.md` and interview prep.

Status: open / cleared / check in source (needs a SEBI or NSE circular to confirm).

| # | Date | Source and page | My doubt | Answer in my own words | Status |
|---|---|---|---|---|---|
| 1 | 29 Oct | NSE FAQ p. | | | open |
| 2 | 1 Nov | SEBI 2025/79 para 5.2.3 | The MWPL formula compares 15% of free float, which is a share count, against 65x ADDV, which is rupees. The paragraph never says which price to convert at. | | check in source |
| 3 | 7 Nov | SEBI 2025/79 para 5.3.3, Table 2 day 2 | Table 2 says a long futures position shows a "passive increase in EoD delta by 5%" when the underlying appreciates 5%. In share terms it shows nothing: para 5.1.1 gives futures a delta factor of exactly 1, and NSE's Contract_Delta file confirms it - every FF row is 1.00000000. An unchanged futures position cannot change its FutEq delta when FutEq is measured in shares. | The provision is real and bites on OPTIONS, whose factors move with the underlying. The futures illustration does not reproduce. Logged as a circular inconsistency rather than a gap in my reading, since three independent sources agree the unit is shares: 5.1.1, Table 1, and my own 216-of-216 headroom reconciliation. | open |
| 4 | 7 Nov | NSE Clearing FAQ Q14 vs DECISIONS #014 | FAQ 14 says an expiry-driven increase in FutEq OI during a ban is a "passive breach" with no penalty "on expiry day". My baseline rule drops an expired contract the day AFTER expiry. Does an expiring contract still carry open interest at its own expiry-day close? | Unresolved. It decides whether rolling ON expiry day is permitted (if yes) or a breach (if no) - the two readings disagree on that one case. Settled by one download: BhavCopy_NSE_FO_..._20261029, the October expiry day. The day-after case is confirmed: no contract expiring on or before 29 Oct appears in either the 30 Oct delta file or the 30 Oct bhavcopy. | check in source |
| 5 | 7 Nov | SEBI 2025/79 para 5.3.2 vs Table 2 day 4 | 5.3.2 says delta "could be reduced till 0"; Table 2 day 4 says "as long as EoD delta above 0, permissible". Is exactly zero permitted? | Yes. Closing out completely cannot sensibly be a breach, and 5.3.2's wording is the operative one. Recorded as the reduction_floor operator in config/rules.yaml so the direction is not written in code. Same shape of ambiguity as the 95%/80% boundaries. | cleared |
| 6 | 8 Nov | Contract_Delta_30102026.csv vs the 29 and 30 Oct bhavcopies | The delta file lists Thursday expiries - 5, 12, 19 and 26 Nov, with 14,076 contracts on the 26th - and neither bhavcopy, one day either side of it, contains any of them. Two NSE files disagreeing about which contracts exist. | Unresolved, no explanation yet. It does not affect the expiry rule, which reads each position's own expiry field, but it means the two files cannot be joined on contract without first checking which universe each one covers. | open |
| 7 | 8 Nov | SEBI 2025/79 para 5.3.2 ("entities") vs para 5.1.2 | The ban-period reduction check runs per UCC. Is that the unit the circular means? 5.3.2 says trading "by entities" must reduce FutEq OI, and 5.1.2 nets within a UCC and gross-adds across UCCs - but that is the MWPL utilisation rule, not the ban-period one. The two units are incomparable rather than one being stricter: an entity whose offsetting legs unwind unevenly (UCC A +10,000 -> +5,000, UCC B -10,000 -> -2,000) passes per UCC, since both legs reduced, while the entity net goes 0 -> +3,000. Per-UCC catches a UCC opening a position that another UCC offsets; per-entity catches the uneven unwind. | Per-UCC is implemented as a scope decision, not a claim that it dominates. An entity-level check belongs ALONGSIDE it, not instead of it, using a date-effective UCC -> entity table. Needs the circular, the joint CC SOP 5.3.4 refers to, or the NSE FAQ to say what "entity" means for this rule. | check in source |

## References to follow up
Links or circulars a document points to that I didn't open while reading. Check each one against the reading list in `docs/READING.md` before opening it.

| Found in (doc and page) | What it points to | Why it matters | Already on the reading list? |
|---|---|---|---|
| NSE FAQ p. | | | |
