"""Parsers for NSE's daily files.

One function per file family. Each takes a path and returns a typed result; none of them
reach out to the network, so every one is testable from a fixture in `tests/fixtures/`.

A parser is the ONE place a file's quirks are handled. The ban list has a prose first line;
if three parts of the engine read that file directly, two of them will get it wrong. Here,
it is dealt with once and the rest of the engine never has to know.

File shapes and traps are documented in `docs/READING.md`.
"""

from __future__ import annotations

import datetime as dt
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import pandas as pd

__all__ = ["BanList", "MwplRow", "as_dataframe", "parse_ban_list", "parse_mwpl_file"]

#: The ban list's first line is prose, not a header row. Checked case-insensitively as a
#: substring, so punctuation and capitalisation can drift without breaking the parser, but a
#: file that is not a ban list at all is refused. See the docstring for why this is strict.
_BAN_LIST_HEADING = "securities in ban"

#: A date of the form 02-NOV-2026, found anywhere in the heading rather than at a fixed
#: offset, so that rewording the sentence around it does not break extraction.
_DATE_IN_HEADING = re.compile(r"\d{1,2}-[A-Za-z]{3}-\d{4}")


@dataclass(frozen=True)
class BanList:
    """What `parse_ban_list()` hands back.

    Frozen for the same reason `Threshold` is frozen in `rules.py`: nothing downstream
    should be able to add a scrip to the ban list.
    """

    trade_date: dt.date
    symbols: frozenset[str]


@dataclass(frozen=True)
class MwplRow:
    """One security's row from NSE's `combineoi` file, exactly as published.

    Nothing here is computed. Utilisation is `futeq_oi / mwpl` and the engine works that out
    for itself; see `parse_mwpl_file()` on why the division does not belong in a parser.

    `mwpl` and `notional_oi` are share counts and whole. `futeq_oi` is **not** - it is a sum
    of delta-weighted positions and deltas are `N(d1)`, so it arrives fractional
    (REDACTED). Annotating it `int` would be a lie that a type checker believes.
    """

    trade_date: dt.date
    isin: str
    scrip_name: str
    symbol: str
    mwpl: int
    notional_oi: int
    futeq_oi: float

    #: True when NSE printed `No Fresh Positions` instead of a headroom figure.
    no_fresh_positions: bool

    #: NSE's own `0.95 * MWPL - FutEq OI`, truncated by NSE to whole shares, or None when the
    #: scrip is barred. Always None exactly when `no_fresh_positions` is True - the two fields
    #: are not independent, and `__post_init__` refuses any record where they disagree.
    #:
    #: It is None rather than a number for banned rows because the formula still yields a
    #: POSITIVE figure for them - SAIL was 21,841,939 shares under the 95% line on 30 Oct and
    #: still barred - so a number here would read as permission. NSE suppresses it for that
    #: reason and so does this record. Code that cannot add None cannot sum it by accident.
    headroom_shares: int | None

    def __post_init__(self) -> None:
        if self.no_fresh_positions != (self.headroom_shares is None):
            raise ValueError(
                f"{self.symbol} ({self.isin}) on {self.trade_date}: "
                f"no_fresh_positions={self.no_fresh_positions} but "
                f"headroom_shares={self.headroom_shares!r}. "
                f"Headroom must be None exactly when fresh positions are barred."
            )
        # Zero is legitimate and must stay allowed: ban entry is "exceeds 95%", so a scrip
        # sitting at exactly 95% is not barred and its headroom is exactly 0. `<= 0` would
        # read more naturally here and would be wrong.
        #
        # Negative is not legitimate, and this is a claim from the circular rather than an
        # observation: a scrip above 95% of MWPL enters the ban period, so NSE prints the
        # sentence for it, not a number. Any row carrying a number is therefore under 95% and
        # its headroom is non-negative by construction. Checked against all 216 printed
        # numbers on 30 Oct 2026: minimum 372,386, highest utilisation 85.98%. If this ever
        # fires, either NSE has a bug or my reading of the ban rule is wrong, and both are
        # things I need to be told rather than silently ingest.
        if self.headroom_shares is not None and self.headroom_shares < 0:
            raise ValueError(
                f"{self.symbol} ({self.isin}) on {self.trade_date}: "
                f"negative headroom {self.headroom_shares}. A scrip over 95% of MWPL should "
                f"carry 'No Fresh Positions', not a number."
            )
        # Bounds on the READING, not a computation. Checked against all 218 rows on
        # 30 Oct 2026: MWPL minimum 736,885 and FutEq OI minimum 91,328.72, so neither guard
        # comes near good data. Guarding mwpl here also means the engine's own
        # futeq_oi / mwpl can never divide by zero.
        if self.mwpl <= 0:
            raise ValueError(
                f"{self.symbol} ({self.isin}) on {self.trade_date}: MWPL is {self.mwpl}. "
                f"A scrip in F&O has a positive market-wide position limit."
            )
        if self.futeq_oi < 0:
            raise ValueError(
                f"{self.symbol} ({self.isin}) on {self.trade_date}: FutEq OI is "
                f"{self.futeq_oi}. It is gross-added across UCCs, so it cannot be negative."
            )
        if not self.isin or self.isin.strip().upper() in {"NA", "NAN", "-"}:
            raise ValueError(
                f"{self.symbol} on {self.trade_date}: no ISIN. MWPL does not apply to "
                f"indices and DECISIONS.md #011 keys state on ISIN, so an index row is "
                f"refused rather than stored under a null key."
            )

def parse_ban_list(path: str | Path) -> BanList:
    """Read NSE's `fo_secban_<ddmmyyyy>.csv` and return the date and the banned symbols.

    This reads what NSE *says* is banned. It does not decide anything - that is
    `is_in_ban()`. The distinction matters because the engine computes ban status
    independently and the comparison between the two is the point of the project. This file
    has two jobs: it scores every ban forecast, and per `DECISIONS.md` #011 it seeds ban
    state on day one.

    **The date comes from the heading, not the filename.** It appears once, inside the prose
    line, as `02-NOV-2026`; the filename carries it too, as `02112026`. The heading wins
    because it is the exchange's own statement of which day the file describes, and because
    it survives the file being renamed, copied or saved from a browser. It is also present
    even on a day with no bans at all. Files genuinely disagree on dates - on 2 Nov 2026 the
    ban list was dated 2 Nov while `combineoi` was dated 30 Oct - so the caller must compare
    this date against the other file's rather than assume one date across all inputs.

    **An unrecognised heading is refused, not worked around.** The heading is verified before
    the date is extracted. This is deliberately strict: if NSE rewords the sentence, the
    parser stops and I fix it in a minute. The alternative - extracting any date-shaped text
    from any first line - would accept a file that is not a ban list, and per #011 Q4 the
    expensive error direction is concluding that nothing is banned. A loud stop beats a quiet
    wrong answer.

    **Strict by choice, in three places.** The heading must be recognisable, the serial
    numbers must run 1, 2, 3 without a gap, and no symbol may repeat. Each of those stops the
    parser on a format change that a lenient reader would shrug off. That is the right trade
    for this particular file: it is 62 bytes, it is the referee that scores every ban forecast
    the engine makes, and the cost of being wrong is reporting a banned scrip as free. A loud
    stop costs a minute. The serial check catches a row lost from the MIDDLE of the file; it
    cannot catch one lost from the END, because a truncated file still numbers consecutively.

    Raises:
        ValueError: the file is empty, its heading is not a ban-list heading, the heading
            carries no date, a row is not `serial,SYMBOL`, a serial is out of sequence, a
            symbol is blank, or a symbol repeats. An empty *ban list* - heading present, no
            rows - is a completely normal day and returns an empty `symbols`, never an error.

    Known limitation, and it cannot be fixed here. A download that received the heading and
    then died is byte-for-byte indistinguishable from a legitimate no-ban day: both are one
    valid line. The file carries no row count, length or checksum, so the information needed
    to tell them apart is not in the file. The downloader has to record it. Until then this
    parser can be fooled into reporting an empty ban list for a truncated file, which is the
    error direction #011 Q4 says must not happen. Tracked in `TASKS.md`.
    """
    lines = Path(path).read_text(encoding="utf-8").splitlines()

    if not lines:
        raise ValueError(f"{path}: file is empty, so not even a heading was received")

    heading = lines[0]
    if _BAN_LIST_HEADING not in heading.lower():
        raise ValueError(
            f"{path}: first line is not a ban-list heading. Expected it to contain "
            f"{_BAN_LIST_HEADING!r}, got {heading!r}"
        )

    match = _DATE_IN_HEADING.search(heading)
    if match is None:
        raise ValueError(f"{path}: no date of the form DD-MON-YYYY in heading {heading!r}")
    trade_date = dt.datetime.strptime(match.group(), "%d-%b-%Y").date()

    symbols: list[str] = []
    expected_serial = 1

    # `start=2` so the number in an error message is the line in the FILE: row one of the
    # data is the file's second line.
    for line_no, row in enumerate(lines[1:], start=2):
        if row.strip() == "":
            continue  # carries no information: skip

        parts = row.split(",")
        if len(parts) != 2:
            raise ValueError(f"{path} line {line_no}: expected 'serial,SYMBOL', got {row!r}")

        serial_text, symbol = parts[0].strip(), parts[1].strip()

        if not serial_text.isdigit() or int(serial_text) != expected_serial:
            raise ValueError(
                f"{path} line {line_no}: expected serial {expected_serial}, "
                f"got {serial_text!r}"
            )
        if symbol == "":
            raise ValueError(
                f"{path} line {line_no}: serial present but symbol empty: {row!r}"
            )

        symbols.append(symbol)
        expected_serial += 1

    # Checked BEFORE the frozenset, because the conversion is lossy: frozenset(["SAIL",
    # "SAIL"]) is a one-element set, so a repeated symbol would vanish without an error and
    # a row would be lost without trace. Validate on the side that still has the information.
    if len(symbols) != len(set(symbols)):
        raise ValueError(f"{path}: duplicate symbol in ban list: {symbols}")

    return BanList(trade_date=trade_date, symbols=frozenset(symbols))


#: Exactly the eight columns NSE publishes in `combineoi`, in order, after stripping the space
#: that follows each comma in the header. Checked rather than assumed: a renamed or reordered
#: column means the format changed, and the 7 Dec 2026 cutover is a known date for that.
_MWPL_COLUMNS = (
    "Date",
    "ISIN",
    "Scrip Name",
    "NSE Symbol",
    "MWPL",
    "Open Interest",
    "Future Equivalent Open Interest",
    "Limit for Next Day",
)

#: What NSE prints in `Limit for Next Day` instead of a figure when a scrip is barred.
_NO_FRESH_POSITIONS = "No Fresh Positions"

#: The CSV inside `combineoi_<ddmmyyyy>.zip`. The archive also holds an XML copy of the same
#: records which is NOT well-formed - its element name is `<Future Equivalent Open Interest>`,
#: with spaces - so no conforming parser can read it. The CSV is the only usable member.
_MWPL_CSV_IN_ZIP = "combineoi_{stem}.csv"


def parse_mwpl_file(path: str | Path) -> tuple[MwplRow, ...]:
    """Read NSE's `combineoi` file and return one validated `MwplRow` per security.

    Accepts either the `.zip` NSE publishes or the `.csv` extracted from it. The archive's
    other member is a malformed XML copy, so the CSV is selected by name rather than by
    position.

    This is the file SEBI Master Circular cl 3.3.2.1.3 requires NSE to disseminate: ISIN,
    name, symbol, MWPL in shares and OI in shares, per security, by 6:30 PM. It covers single
    stocks only - 218 of them on 30 Oct 2026 - because MWPL does not apply to indices, which
    are governed by the index position limits of `SPEC.md` row 13 instead. An index row would
    arrive with `ISIN = NA` and `MwplRow` refuses it.

    **Nothing is computed here.** Utilisation is `futeq_oi / mwpl` and the engine works it out,
    for the three reasons recorded against decision 2 in this module. The headroom figure in
    each row is NSE's own, truncated by NSE to whole shares, not a recomputation.

    **Returns a tuple, not a DataFrame.** Every row has passed `MwplRow.__post_init__`, so a
    contradictory record cannot exist in the result. Convert to a DataFrame with
    `as_dataframe()` at the point of analysis, and read that function's warning first.

    Raises:
        ValueError: the file is missing its expected columns, carries more than one trade
            date, repeats a security, or contains a row `MwplRow` refuses.
    """
    path = Path(path)

    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            wanted = _MWPL_CSV_IN_ZIP.format(stem=path.stem.replace("combineoi_", ""))
            members = [n for n in archive.namelist() if n.lower() == wanted.lower()]
            if not members:
                raise ValueError(
                    f"{path}: no member named {wanted!r}. Found {archive.namelist()}. The XML "
                    f"member is malformed and cannot be used as a fallback."
                )
            with archive.open(members[0]) as handle:
                frame = pd.read_csv(handle, skipinitialspace=True, keep_default_na=False)
    else:
        frame = pd.read_csv(path, skipinitialspace=True, keep_default_na=False)

    # `skipinitialspace` handles the values; the header needs stripping separately, because
    # NSE writes 'Date, ISIN, Scrip Name, ...' with a space after each comma.
    #
    # `keep_default_na=False` is load-bearing, not tidiness. pandas' default missing-value
    # list includes the literal string "NA", which is exactly what NSE writes in the ISIN
    # column for an index row. Without this, that "NA" silently became NaN, str() made it
    # "nan", and the index-row guard in MwplRow never fired. A test caught it.
    frame.columns = [str(c).strip() for c in frame.columns]

    missing = [c for c in _MWPL_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(
            f"{path}: missing column(s) {missing}. Got {list(frame.columns)}. A renamed column "
            f"means the format changed - see the 7 Dec 2026 cutover in docs/READING.md."
        )

    rows: list[MwplRow] = []
    for position, record in enumerate(frame.to_dict("records"), start=2):
        printed = str(record["Limit for Next Day"]).strip()
        barred = printed == _NO_FRESH_POSITIONS

        if barred:
            headroom: int | None = None
        else:
            try:
                headroom = int(printed)
            except ValueError as exc:
                raise ValueError(
                    f"{path} line {position}: 'Limit for Next Day' is {printed!r}, which is "
                    f"neither a whole number of shares nor {_NO_FRESH_POSITIONS!r}"
                ) from exc

        rows.append(
            MwplRow(
                trade_date=_parse_mwpl_date(record["Date"], path, position),
                isin=str(record["ISIN"]).strip(),
                scrip_name=str(record["Scrip Name"]).strip(),
                symbol=str(record["NSE Symbol"]).strip(),
                mwpl=int(record["MWPL"]),
                notional_oi=int(record["Open Interest"]),
                futeq_oi=float(record["Future Equivalent Open Interest"]),
                no_fresh_positions=barred,
                headroom_shares=headroom,
            )
        )

    if not rows:
        raise ValueError(f"{path}: no data rows. A trading day has securities in this file.")

    dates = {r.trade_date for r in rows}
    if len(dates) != 1:
        raise ValueError(
            f"{path}: rows carry {len(dates)} different trade dates ({sorted(dates)}). This "
            f"file describes one day."
        )

    isins = [r.isin for r in rows]
    if len(isins) != len(set(isins)):
        duplicated = sorted({i for i in isins if isins.count(i) > 1})
        raise ValueError(f"{path}: the same ISIN appears more than once: {duplicated}")

    return tuple(rows)


def _parse_mwpl_date(value: object, path: Path, line: int) -> dt.date:
    """`combineoi` writes 30-OCT-2026; `combineoi_deleq` writes 30-10-2026, same exchange and
    same day. Both are accepted so the two files can be compared without the caller caring.
    """
    text = str(value).strip()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"{path} line {line}: cannot read {text!r} as a date")


def as_dataframe(rows: Sequence[MwplRow]) -> "pd.DataFrame":
    """A read-only DataFrame view of parsed rows, for analysis only.

    **Read this before using the result.** The conversion silently weakens the guarantee that
    `MwplRow` exists to provide. `headroom_shares` is `int | None`; pandas has no integer
    column that holds `None`, so the column becomes `float64` and every `None` becomes `NaN`.
    And pandas skips `NaN` by default:

        len(df)                     218
        df.headroom_shares.sum()    the total over 216 rows, no warning
        df.headroom_shares.count()  216, not 218
        df.headroom_shares.mean()   the mean over 216, presented as the mean

    In pure Python the same sum raises `TypeError: unsupported operand type(s) for +: 'int'
    and 'NoneType'`, which is the whole reason `None` was chosen over a number for barred
    scrips - a positive headroom reads as permission, and SAIL was 21,841,939 shares under
    the 95% line on 30 Oct while barred. That protection does not survive this function.

    So: treat the result as a read-only view. Never feed it back into the engine. If data has
    to re-enter, it goes through `MwplRow` again, where the invariants are enforced. When
    aggregating `headroom_shares`, say in the output how many rows the figure covers.
    """
    return pd.DataFrame([asdict(row) for row in rows])
