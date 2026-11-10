# Provenance for `tests/fixtures/transitions/`

**The fixture files are not in this directory.** They are NSE content, so they are built from
the files in `data/` (gitignored) by `scripts/build_nse_fixtures.py`, at test time by
`tests/conftest.py`, and never committed (`DECISIONS.md` #010 addendum). This file keeps what can
be published: which rows are selected, and the checksum of every input, so the derivation can be
repeated and checked. The hash of every built file is in `tests/fixtures/nse_built.sha256`. The
same input hashes are in `docs/READING.md`. First built on 7 Nov 2026.

`combineoi_rows.csv` holds **selected rows**, not whole files: the five scrips that
transition in this window, plus `MANAPPURAM` and `INOXWIND` (in the 80-95% band on every
day and never transitioning - the free-stays-free control) and `KARURVYSYA` (far below
every threshold). Both kinds of in-band row are present on all seven days; either half
alone would let an engine pass that simply answered "banned" for everything in the band.

The ban lists are copied byte for byte. The rows are copied as the strings NSE published.

| file | role | source bytes | source sha256 |
|---|---|---|---|
| `fo_secban_02112026.csv` | copied verbatim from data/ | 62 | `c793e59f34230c54c5eafae90a0d5c5e0174cdfc68b5b2e551fa3f8a5d2c3af2` |
| `fo_secban_12102026.csv` | copied verbatim from data/ | 83 | `3240f7a2a38cdf4a097c2e515f9e469eceb6bc977bd2f4bdac27a90019f43fbf` |
| `fo_secban_13102026.csv` | copied verbatim from data/ | 92 | `5ea8fa4b81beeb73ef8d9e8bd7bbe29177de40514f29ff0cccd0e28e9f2b0d58` |
| `fo_secban_14102026.csv` | copied verbatim from data/ | 67 | `13535288084d1b423b14631e9315b470d195452b40ced7e7f49b3cda86f098c3` |
| `fo_secban_15102026.csv` | copied verbatim from data/ | 74 | `553cefe582b83393a0308404540e6cf659124b15f7c0226f1bb747d31bc4e505` |
| `fo_secban_16102026.csv` | copied verbatim from data/ | 74 | `13a325bfac762665a38a96855240b19e4d1f8134c0f8d7082f312ff4426490a6` |
| `fo_secban_19102026.csv` | copied verbatim from data/ | 74 | `cfffe15162d6d18815a56e2edd7b53bb156af753589dc79559c642b1831ddc7f` |
| `fo_secban_21102026.csv` | copied verbatim from data/ | 74 | `98486c266c5069242dbcf1f05bf4a6a32196f306ee0567414e3d30b61373feb4` |
| `fo_secban_22102026.csv` | copied verbatim from data/ | 74 | `a1e02e700c8383e4cd110450cd2ddf5c735070b8f38e233eb164696295490ff8` |
| `fo_secban_23102026.csv` | copied verbatim from data/ | 74 | `c248d7e7bbd565376d6b2e03f21098f0780761860dfef31ebf79b39bc730acb3` |
| `fo_secban_26102026.csv` | copied verbatim from data/ | 74 | `315446155766b2d052e1123760de39fe4062dcdecea3fd0cb975b9e09cc73757` |
| `fo_secban_27102026.csv` | copied verbatim from data/ | 74 | `5de741a28e20b5f6f625f0c90c798319726d764f63723d9d73a52854b999408f` |
| `fo_secban_28102026.csv` | copied verbatim from data/ | 53 | `8af926d9d336ee025f59e12224987119104b1d2b3be72a8655263a6f66736662` |
| `fo_secban_29102026.csv` | copied verbatim from data/ | 62 | `4f5cd81f624529a94571e2befd5335dfde0d56454bdbd68ad683c217f8f7d699` |
| `fo_secban_30102026.csv` | copied verbatim from data/ | 62 | `657f42306413544855e0c232dc1d62b56f6814ab98ae7d806efd7d3d5f2e9859` |
| `combineoi_12102026.zip` | 7 of 213 rows selected | 21,679 | `b232e63b56f369da4194cb2385d451c6ac9c4dd8fb01275f70a9bcf259a6f135` |
| `combineoi_13102026.zip` | 7 of 213 rows selected | 21,729 | `89a1a844d76e415c58d59a80d84c0ec605aa5610d96f175c09b849ee520fccfc` |
| `combineoi_14102026.zip` | 7 of 213 rows selected | 21,750 | `01a5d0fffe4adf484ec86da508fab87ffff183f25fc43946ee7148cc580e882e` |
| `combineoi_26102026.zip` | 7 of 213 rows selected | 21,742 | `6800b35df62d6f39d3fb78d95338118d8d646e282beca9f4294d1434a2b3a256` |
| `combineoi_27102026.zip` | 7 of 213 rows selected | 21,697 | `746e1781d47a45628b957dcc49dc29775810312a98a9fc68523b143294d9460c` |
| `combineoi_28102026.zip` | 8 of 219 rows selected | 21,857 | `82532e2221a42b5b95de53402f8fc4bd20065a7db3317342e0eb0cd42e5d2303` |
| `combineoi_30102026.zip` | 8 of 218 rows selected | 22,204 | `076660e6f7452d28f497859483df13903863ec1bbfc4932b0a01737ca291211c` |

Regenerate with `scripts/build_nse_fixtures.py`; the fixture is derived data and is never
edited by hand.
