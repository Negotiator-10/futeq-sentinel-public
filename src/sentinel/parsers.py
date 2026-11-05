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
from dataclasses import dataclass
from pathlib import Path

__all__ = ["BanList", "parse_ban_list"]

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


# ===========================================================================
# YOURS TO WRITE NEXT: parse_mwpl_file()
#
# THE FILE. tests/fixtures/combineoi_sample.csv - four lines cut from the real 218-row file:
#
#   Date, ISIN, Scrip Name, NSE Symbol, MWPL, Open Interest, Future Equivalent Open Interest, Limit for Next Day
#   30-OCT-2026,INE918Z01012,KAYNES TECHNOLOGY IND LTD,KAYNES,REDACTED,REDACTED,REDACTED,No Fresh Positions
#   30-OCT-2026,INE114A01011,STEEL AUTHORITY OF INDIA,SAIL,REDACTED,REDACTED,REDACTED,No Fresh Positions
#   30-OCT-2026,INE466L01038,360 ONE WAM LIMITED,360ONE,REDACTED,REDACTED,REDACTED,REDACTED
#
# Unlike the ban list this is a proper CSV with a real header, so pandas.read_csv handles the
# shape. The work is in three decisions, not in the reading.
#
# DECISION 1, and it is the interesting one. LOOK AT THE LAST COLUMN.
#   Two of those rows say `No Fresh Positions`. One says `REDACTED`.
#   NSE has packed TWO different facts into one column: how much headroom is left, AND
#   whether the scrip is banned. A column that is sometimes a number and sometimes a
#   sentence cannot be used in arithmetic, and `float("No Fresh Positions")` raises.
#   So decide how your record represents those two facts. How many fields, and of what
#   types? You proved on 2 Nov that the number equals 0.95 * MWPL - FutEq OI on 216 of 216
#   rows, so you know exactly what it means when it is a number.
#
# DECISION 2. Does this parser compute utilisation?
#   You have MWPL and FutEq OI in every row, so you COULD divide them here.
#   Think about the distinction you got right with the ban list: this function reads what
#   NSE published. Utilisation is something the engine works out. Decide where the division
#   belongs and say why in the docstring - it is the same reading-versus-computing line.
#
# DECISION 3. What comes back - a list of frozen dataclasses, like BanList, or a pandas
#   DataFrame?
#   For 218 rows either works. The caller is the reconciliation step, which subtracts your
#   number from NSE's across all 218 rows at once and reports an error distribution.
#   Dataclasses are consistent with BanList and type-checked; a DataFrame makes that
#   arithmetic one line. Pick one and say what you are trading away.
#
# ALSO TRUE, AND WORTH HANDLING:
#   - The header has a space after each comma: ' ISIN', not 'ISIN'. Column names will carry
#     it unless you strip them. pandas has `skipinitialspace=True`.
#   - The date is 30-OCT-2026 here and 30-10-2026 in combineoi_deleq. Same exchange, same
#     day, two formats.
#   - This file is single stocks only - 218 of them. The nine indices are absent, because
#     MWPL does not apply to them. DECISIONS.md #011 says a row with no ISIN is refused.
#   - The real file lives inside combineoi_30102026.zip alongside a malformed XML copy.
#     Decide whether this function takes the .zip or the extracted .csv.
#
# THEN the tests in tests/test_parsers.py, alongside the ban-list ones.
# ===========================================================================
