"""Which dates NSE traded on, and what the engine may conclude when it does not know.

A date has **four** states. Three of them are the decision in `DECISIONS.md` #012 - the same
move as the three threshold states in `rules.py` and the three `source` values in the store,
where "I do not know" gets its own state rather than being forced into one of the others. The
fourth arrived on 7 Nov, from NSE's own 2026 calendar:

    TRADING          a session happened, verified against NSE's published calendar
    SPECIAL_SESSION  a session happened on a day that is not a normal trading day
    HOLIDAY          no session, verified the same way
    UNKNOWN          no verified calendar covers this date

`SPECIAL_SESSION` is a state and not a flag on `TRADING`, which was a deliberate choice. The
open question about Muhurat trading is not whether there is data on 8 Nov 2026 - there will be
- but whether that session counts as the previous trading day for 9 Nov's ban state. A flag
would answer that "yes" by default. A separate state forces the decision: its files are
accepted, and any attempt to **chain** through it refuses until the chaining is verified.

NSE's own wording supports being careful. Circular NSE/FAOP/71777 lists 8 Nov as a Sunday
holiday and says in the same breath that "Muhurat Trading will be conducted" that day, with
timings "notified subsequently" - the exchange had not settled the session's shape when it
published the calendar.

Settled 9 Nov from the session's own files: 8 Nov chains. The verdict is a `chaining_verified`
row in the calendar file, sourced to those files and their checksums - an observation, kept
apart from the circular rows. A `chaining_excluded` row records the opposite verdict, which no
date needs yet.

The reason this module exists at all is a bug. `scripts/score_bans.py` originally took "the
next trading day" to mean "the next date for which a file happens to be on disk". Hide one ban
list and it scored 14 Oct's forecast against 16 Oct's published list, skipped the 15th
entirely, reported 1502 of 1502 with zero errors, and exited 0. A missing file silently
re-dated the answer and the result still looked perfect.

So the calendar is **reference data, not typed configuration**: `config/calendar_2026.csv`
carries one row per non-trading day with its own source string, the same per-key provenance as
`config/rules.yaml` (#007). An empty calendar knows nothing and says so - it does not default
to "weekdays are trading days", which is the same inference in a better coat.

**Clearing holidays are not modelled, and that is a finding rather than an omission.** NSE
publishes a separate clearing-holiday list which is a superset of the trading holidays by five
days in 2026, and `combineoi` is served from the clearing corporation's archive path
(`/archives/nsccl/mwpl/`), so it looked as though the clearing calendar might decide whether a
measurement file exists. It does not: `combineoi_26082026.zip` was downloaded on 7 Nov for
26 Aug 2026, a clearing holiday that was a trading day, and the file is there with 211 rows.
One observation, not five, and it is recorded as one in `docs/READING.md`.
"""

from __future__ import annotations

import csv
import datetime as dt
from collections.abc import Iterable, Mapping
from enum import Enum
from pathlib import Path

__all__ = [
    "DayKind",
    "TradingCalendar",
    "CalendarError",
    "UnknownDateError",
    "ChainUnverifiedError",
    "load_calendar",
    "DEFAULT_CALENDAR_PATH",
]

DEFAULT_CALENDAR_PATH = Path(__file__).resolve().parents[2] / "config" / "calendar_2026.csv"


class DayKind(Enum):
    """What the verified calendar says about one date."""

    TRADING = "trading"
    SPECIAL_SESSION = "special_session"
    HOLIDAY = "holiday"
    UNKNOWN = "unknown"

    @property
    def has_session(self) -> bool:
        """True when a session happened, whether or not it was a normal trading day."""
        return self in (DayKind.TRADING, DayKind.SPECIAL_SESSION)


class CalendarError(Exception):
    """The calendar itself is unusable."""


class UnknownDateError(Exception):
    """A date was asked about that no verified calendar covers.

    Not a bug in the caller. It is the calendar refusing to guess, and the correct response is
    to extend the verified calendar - or, for a single scrip in the dead zone, to refuse that
    scrip and carry on with the rest, per #012.
    """


class ChainUnverifiedError(Exception):
    """A walk met a `SPECIAL_SESSION` whose place in the chain has not been established.

    Deliberately distinct from `UnknownDateError`: the date is not unknown, the calendar knows
    exactly what it is. What is unknown is whether it counts as the previous or next trading
    day, and that question is settled by observing the session's own end-of-day files, not by
    picking a convenient answer. (The ban lists alone may not discriminate: on 6, 8 and 9 Nov
    2026 they were identical, so both answers predicted them. See #013 addendum.)
    """


class TradingCalendar:
    """The trading days, special sessions and holidays the project has verified.

    Constructed from an explicit mapping so the source is always a file with a checksum behind
    it. `TradingCalendar({})` knows nothing, which is the honest starting state, not an error.
    """

    def __init__(
        self,
        days: Mapping[dt.date, DayKind],
        *,
        source: str = "",
        chaining_verified: frozenset[dt.date] = frozenset(),
        chaining_excluded: frozenset[dt.date] = frozenset(),
        chaining_evidence: Mapping[dt.date, str] | None = None,
    ) -> None:
        unknown_written = [d for d, k in days.items() if k is DayKind.UNKNOWN]
        if unknown_written:
            raise CalendarError(
                f"{len(unknown_written)} date(s) recorded as UNKNOWN, starting "
                f"{min(unknown_written)}. UNKNOWN is the absence of a record, not a record - "
                f"writing it down makes an unverified date look verified."
            )
        for label, dates in (("chaining_verified", chaining_verified),
                             ("chaining_excluded", chaining_excluded)):
            stray = sorted(d for d in dates if days.get(d) is not DayKind.SPECIAL_SESSION)
            if stray:
                raise CalendarError(
                    f"{label} names {len(stray)} date(s) that are not special sessions, "
                    f"starting {stray[0]}. Only a special session has chaining to verify."
                )
        both = sorted(set(chaining_verified) & set(chaining_excluded))
        if both:
            raise CalendarError(
                f"{both[0]} is recorded both as chaining and as not chaining. One observation is "
                f"wrong, and picking a winner would hide which."
            )
        self._days = dict(days)
        self.source = source
        #: Special sessions observed to be a link in the chain: the walk stops on them.
        self.chaining_verified = frozenset(chaining_verified)
        #: Special sessions observed NOT to be a link: their files are real and stored, but the
        #: walk steps over them as it does a holiday. No date is here yet - the state exists so
        #: that the first special session that does not chain has somewhere to go other than a
        #: hand-edit to the walk, the same reason NoPriorDay was decided before the first run.
        self.chaining_excluded = frozenset(chaining_excluded)
        #: Where each of those verdicts came from - an observation, never a circular.
        self.chaining_evidence = dict(chaining_evidence or {})

    # -- what the calendar knows ----------------------------------------------------------

    def kind(self, day: dt.date) -> DayKind:
        """Never raises. `UNKNOWN` for any date not covered."""
        return self._days.get(day, DayKind.UNKNOWN)

    def has_session(self, day: dt.date) -> bool:
        """Whether a session happened, normal or special. Raises on an unknown date.

        This is what the store asks before accepting a day's files: a special session's data is
        real and is stored. Whether it *chains* is a different question - see `next_trading_day`.
        """
        k = self.kind(day)
        if k is DayKind.UNKNOWN:
            raise UnknownDateError(self._unknown_message(day))
        return k.has_session

    def is_trading_day(self, day: dt.date) -> bool:
        """True only for a normal trading day. A special session is not one; ask `has_session`."""
        k = self.kind(day)
        if k is DayKind.UNKNOWN:
            raise UnknownDateError(self._unknown_message(day))
        return k is DayKind.TRADING

    def _unknown_message(self, day: dt.date) -> str:
        where = f" (source: {self.source})" if self.source else ""
        return (
            f"{day} is not in the verified calendar{where}. Extend the calendar from NSE's "
            f"published list; do not assume."
        )

    @property
    def covered(self) -> tuple[dt.date, dt.date] | None:
        """The first and last dates the calendar has an opinion about."""
        if not self._days:
            return None
        return min(self._days), max(self._days)

    @property
    def special_sessions(self) -> tuple[dt.date, ...]:
        return tuple(sorted(d for d, k in self._days.items() if k is DayKind.SPECIAL_SESSION))

    def __len__(self) -> int:
        return len(self._days)

    def __repr__(self) -> str:
        span = self.covered
        where = f" {span[0]}..{span[1]}" if span else " empty"
        return (
            f"<TradingCalendar {len(self._days)} dates{where}, "
            f"{len(self.special_sessions)} special session(s)>"
        )

    # -- walking the calendar -------------------------------------------------------------

    def next_trading_day(self, day: dt.date) -> dt.date:
        """The first trading day strictly after `day`.

        Refuses on the first `UNKNOWN` date it meets rather than stepping over it. Stepping over
        is the bug this module was written for: an unknown date skipped silently is a forecast
        scored against the wrong day's published answer.

        Refuses on an unverified `SPECIAL_SESSION` for the same reason in a different coat -
        whether a special session is the previous trading day for the next one has to be
        established by observation, and guessing would make every ban state after it rest on
        the guess. 8 Nov 2026 was settled on 9 Nov from its own files: it chains (#013).
        A session in `chaining_excluded` is stepped over like a holiday.
        """
        return self._walk(day, +1)

    def previous_trading_day(self, day: dt.date) -> dt.date:
        """The last trading day strictly before `day`. Refuses the same way."""
        return self._walk(day, -1)

    def _walk(self, day: dt.date, step: int) -> dt.date:
        span = self.covered
        if span is None:
            raise UnknownDateError(
                "the calendar is empty, so no trading day can be identified. It is loaded from "
                "config/calendar_2026.csv; see docs/READING.md for the circular behind it."
            )
        first, last = span
        direction = "next" if step > 0 else "previous"
        cursor = day + dt.timedelta(days=step)
        while first <= cursor <= last:
            k = self.kind(cursor)
            if k is DayKind.UNKNOWN:
                raise UnknownDateError(
                    f"{cursor} is not in the verified calendar, so the {direction} trading day "
                    f"from {day} cannot be established. Skipping it would silently move the "
                    f"answer by a day."
                )
            if k is DayKind.SPECIAL_SESSION:
                if cursor in self.chaining_verified:
                    return cursor
                if cursor not in self.chaining_excluded:
                    raise ChainUnverifiedError(
                        f"{cursor} is a special session and its place in the chain is not "
                        f"verified, so the {direction} trading day from {day} is undecided. "
                        f"Settle it by observing that session's own end-of-day files, then add a "
                        f"chaining_verified or chaining_excluded row to the calendar file with "
                        f"the files and their checksums as its source (DECISIONS.md #013)."
                    )
                # verified not to chain: step over it, as over a holiday
            elif k is DayKind.TRADING:
                return cursor
            cursor += dt.timedelta(days=step)
        raise UnknownDateError(
            f"ran off the {'end' if step > 0 else 'start'} of the verified calendar "
            f"({first}..{last}) looking for the {direction} trading day from {day}."
        )

    # -- building one ---------------------------------------------------------------------

    @classmethod
    def from_sessions(
        cls,
        trading_days: Iterable[dt.date],
        holidays: Iterable[dt.date],
        *,
        special_sessions: Iterable[dt.date] = (),
        source: str = "",
        chaining_verified: Iterable[dt.date] = (),
        chaining_excluded: Iterable[dt.date] = (),
    ) -> TradingCalendar:
        """Build from explicit lists. A date in more than one list is a contradiction."""
        trading, holiday, special = set(trading_days), set(holidays), set(special_sessions)
        for a, b, label in (
            (trading, holiday, "a trading day and a holiday"),
            (trading, special, "a trading day and a special session"),
            (holiday, special, "a holiday and a special session"),
        ):
            both = sorted(a & b)
            if both:
                raise CalendarError(
                    f"{len(both)} date(s) given as both {label}, starting {both[0]}. One of the "
                    f"inputs is wrong and picking a winner would hide it."
                )
        days: dict[dt.date, DayKind] = {d: DayKind.TRADING for d in trading}
        days.update({d: DayKind.HOLIDAY for d in holiday})
        days.update({d: DayKind.SPECIAL_SESSION for d in special})
        return cls(
            days,
            source=source,
            chaining_verified=frozenset(chaining_verified),
            chaining_excluded=frozenset(chaining_excluded),
        )


def load_calendar(
    path: str | Path | None = None,
    *,
    chaining_verified: Iterable[dt.date] = (),
) -> TradingCalendar:
    """Load the calendar from a CSV of non-trading days and special sessions.

    The file lists only the exceptions, one row per date, each with its own source string - the
    same per-key provenance as `config/rules.yaml` (#007). Every other weekday inside the
    covered year is a trading day.

    **That complement is a deduction, not a guess.** NSE/FAOP/71777 says "the Exchange hereby
    notifies trading holidays for the calendar year 2026 as below", which is an exhaustive
    enumeration for that year, so the remaining weekdays are determined. It holds only inside
    the stated year, and only until NSE amends the circular - which it does occasionally, so a
    `year_amended` row would be the place to record that.

    Weekends are holidays by rule rather than by the circular, which lists only the weekend
    dates that carry a named holiday. The Muhurat Sunday is exactly why the file must be able
    to override that rule: 8 Nov 2026 is a Sunday with a session.

    **Chaining verdicts are meta rows too**, `chaining_verified` or `chaining_excluded` in the
    date column and the special session's date in the description. They are the only rows not
    sourced from a circular - no circular says whether a Muhurat session chains - so the loader
    holds them to a different rule: the source must begin `observed` and must carry a sha256,
    because an observation that cannot be re-checked against its files is not evidence. A
    source written the way the circular rows are written is refused, which keeps the two kinds of
    row apart in the file rather than only in the reader's head. (The check is on the shape of
    the source - `observed` and a checksum - not on its truth; the checksums are re-checked
    against `docs/READING.md` by a test.)

    The `chaining_verified` argument adds dates on top of the file's rows; tests use it.
    """
    path = Path(path) if path is not None else DEFAULT_CALENDAR_PATH
    if not path.is_file():
        raise CalendarError(f"no calendar at {path}")

    years: set[int] = set()
    exceptions: dict[dt.date, tuple[DayKind, str]] = {}
    verdicts: dict[str, set[dt.date]] = {"chaining_verified": set(), "chaining_excluded": set()}
    evidence: dict[dt.date, str] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for lineno, rec in enumerate(csv.DictReader(fh), start=2):
            if not rec.get("date", "").strip():
                continue
            if rec["date"].strip() == "year_covered":
                years.add(int(rec["description"].strip()))
                continue
            if rec["date"].strip() in verdicts:
                label = rec["date"].strip()
                where = f"{path} line {lineno}: {label}"
                if rec["kind"].strip() != DayKind.SPECIAL_SESSION.value:
                    raise CalendarError(f"{where} must have kind special_session")
                try:
                    session = dt.date.fromisoformat(rec["description"].strip())
                except ValueError as exc:
                    raise CalendarError(
                        f"{where}: description {rec['description']!r} is not a date"
                    ) from exc
                source = rec.get("source", "").strip()
                if not source.lower().startswith("observed") or "sha256" not in source.lower():
                    raise CalendarError(
                        f"{where} for {session}: the source must begin `observed` and name the "
                        f"files with their sha256. A chaining verdict is a finding from NSE's "
                        f"own end-of-day files, not a line from a circular, and a reader must be "
                        f"able to tell the two apart and re-check it."
                    )
                if session in evidence:
                    raise CalendarError(f"{where}: {session} already has a chaining verdict")
                verdicts[label].add(session)
                evidence[session] = source
                continue
            try:
                day = dt.date.fromisoformat(rec["date"].strip())
            except ValueError as exc:
                raise CalendarError(f"{path} line {lineno}: {rec['date']!r} is not a date") from exc
            try:
                kind = DayKind(rec["kind"].strip())
            except ValueError as exc:
                raise CalendarError(
                    f"{path} line {lineno}: kind {rec['kind']!r} is not one of "
                    f"{', '.join(k.value for k in DayKind if k is not DayKind.UNKNOWN)}"
                ) from exc
            if kind is DayKind.UNKNOWN:
                raise CalendarError(
                    f"{path} line {lineno}: UNKNOWN is the absence of a record, not a record."
                )
            if not rec.get("source", "").strip():
                raise CalendarError(
                    f"{path} line {lineno}: {day} has no source. A date that cannot say where it "
                    f"came from is not usable, the same rule as config/rules.yaml."
                )
            if day in exceptions:
                raise CalendarError(f"{path} line {lineno}: {day} listed twice")
            exceptions[day] = (kind, rec["source"].strip())

    if not years:
        raise CalendarError(
            f"{path}: no `year_covered` row. Without it the complement - every weekday that is "
            f"not listed - has no boundary, and dates outside the circular's year would be "
            f"silently treated as trading days."
        )

    days: dict[dt.date, DayKind] = {}
    for year in sorted(years):
        day = dt.date(year, 1, 1)
        end = dt.date(year, 12, 31)
        while day <= end:
            if day in exceptions:
                days[day] = exceptions[day][0]
            elif day.weekday() >= 5:
                days[day] = DayKind.HOLIDAY       # weekend, by rule; overridable by the file
            else:
                days[day] = DayKind.TRADING       # the complement of an exhaustive list
            day += dt.timedelta(days=1)

    outside = sorted(d for d in exceptions if d.year not in years)
    if outside:
        raise CalendarError(
            f"{path}: {len(outside)} date(s) outside the covered year(s) "
            f"{sorted(years)}, starting {outside[0]}."
        )

    sources = sorted({src for _, src in exceptions.values()})
    return TradingCalendar(
        days,
        source=f"{path.name} ({'; '.join(sources)})",
        chaining_verified=frozenset(verdicts["chaining_verified"] | set(chaining_verified)),
        chaining_excluded=frozenset(verdicts["chaining_excluded"]),
        chaining_evidence=evidence,
    )
