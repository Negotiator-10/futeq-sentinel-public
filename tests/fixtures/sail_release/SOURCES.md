# Provenance for `tests/fixtures/sail_release/`

Built by `scripts/build_sail_fixture.py` from the files in `data/`, which is gitignored. Derived
data: rerun the builder, never edit by hand. The same hashes are in `docs/READING.md`.

SAIL's walk out of the ban, 2 to 6 Nov 2026. `combineoi_rows.csv` holds **SAIL's row only** from
each of five `combineoi` files - one row selected per file, copied as NSE published the strings.
The ban lists are copied byte for byte: 2 Nov is the seed for the first close, and 8 Nov is the
answer for the 6 Nov close, because the Muhurat session on Sunday 8 Nov chains (`DECISIONS.md`
#013 addendum).

The two in-band cases are both here, on one stock: the 4 Nov close (80.51%, in ban, held) and the
6 Nov close (82.79%, not in ban, stays out).

| file | role | source bytes | source sha256 |
|---|---|---|---|
| `fo_secban_02112026.csv` | copied verbatim from data/ | 62 | `c793e59f34230c54c5eafae90a0d5c5e0174cdfc68b5b2e551fa3f8a5d2c3af2` |
| `fo_secban_03112026.csv` | copied verbatim from data/ | 62 | `9abe24b292ff44b806c698dfd21b73e11d2ea07062f2f40e02e17ba3c5c9bc7f` |
| `fo_secban_04112026.csv` | copied verbatim from data/ | 62 | `2300055b6835841bb8413346df37d631efb298fc89e85ee82d4dc7811f24fb4e` |
| `fo_secban_05112026.csv` | copied verbatim from data/ | 62 | `d06b6b64082f0d12562423b3ce6a765af614c28b38e995d5d00a1b3a6ba3e519` |
| `fo_secban_06112026.csv` | copied verbatim from data/ | 55 | `97eb2de4aa066b5923d5a79530ddf8095d4dfcb4b0b97ff81363398b48bea72d` |
| `fo_secban_08112026.csv` | copied verbatim from data/ | 55 | `34b68cb999f6c66dd77274242ab8a478532e4133b17d39b0d083da2bcd2ce042` |
| `combineoi_02112026.zip` | SAIL's row only | 22,219 | `853823d6981505551cda3f57b3d5c59e27ed69678732f2fd58df7ff569f79889` |
| `combineoi_03112026.zip` | SAIL's row only | 22,197 | `a3d4684b259f70ca7f3221e9df228f8527262dbb055dca7c951ef37db7f8a9be` |
| `combineoi_04112026.zip` | SAIL's row only | 22,230 | `e30c75145054f23b23f67a1ce054197b697ef9eadd9fbfc0680c9842d5e692a0` |
| `combineoi_05112026.zip` | SAIL's row only | 22,227 | `9a29fff3a287f474511061be17893e3c933fb2e1875fd34bf8a1f6c5265e5656` |
| `combineoi_06112026.zip` | SAIL's row only | 22,285 | `f3be2b174de74e48e641618719c496cff3d5fde6e49f386a56a181683316ea84` |
