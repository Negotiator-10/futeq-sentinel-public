"""The engine: what FutEq Sentinel concludes from NSE's published files.

The parsers in `parsers.py` read. This module computes. The split is deliberate and it is
recorded against decision 2 of `parse_mwpl_file()`: if the engine disagrees with NSE on some
day, a parser that only reads means the disagreement points cleanly here, where a parser that
also computed would make its own bug look like bad data.

Every threshold comes from `config/rules.yaml` through `sentinel.rules`, never from a literal
in this file. That is the rule in `CLAUDE.md`, and it is also what makes these functions
survive SEBI changing a number.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sentinel.book import BookError, DeltaFactors, PropBook, futeq_delta, live_on
from sentinel.calendar import TradingCalendar
from sentinel.parsers import MwplRow
from sentinel.rules import Rules

__all__ = [
    "utilisation",
    "headroom_shares",
    "is_in_ban",
    "Residual",
    "BarredCheck",
    "Reconciliation",
    "reconcile",
    "ReductionCheck",
    "check_ban_period_reduction",
    "check_entity_limit",
]


# ===========================================================================
# WHAT COUNTS AS AGREEMENT, AND WHY. Settled 5 Nov; the measurement behind it is kept here
# because the numbers are the whole argument and they do not survive in a commit message.
#
# Measured across all 216 rows of combineoi_30102026 that carry an NSE figure, where the
# residual is (0.95 * MWPL - FutEq OI) - NSE's published `Limit for Next Day`:
#
#     minimum residual   +0.010612
#     maximum residual   +0.993411
#     all >= 0           True        NSE always rounds DOWN
#     all  < 1           True        never more than one share out
#     any == 0           False       NOT ONE row matches exactly
#
#     exact equality          0 of 216 pass
#     |residual| < 1        216 of 216 pass
#     0 <= residual < 1     216 of 216 pass
#
# Exact equality fails on every row, so it is not a strict test, it is a broken one. Of the
# two tolerant forms the SIGNED one is used: `0 <= residual < 1`.
#
# The reason is not symmetry, it is which direction of error hurts. A residual below zero
# means NSE published MORE headroom than the formula allows - a desk acting on it takes a
# position it is not entitled to, which is a breach. A residual above one means NSE published
# less, which costs opportunity and nothing else. `|residual| < 1` would not notice the first
# one. The signed form fails on it, which is the point.
#
# Three consequences, all deliberate:
#
#   * The epsilon is a float tolerance, not Decimal. The smallest real residual is +0.0106,
#     four orders of magnitude clear of float noise at this scale, so there is nothing for
#     Decimal to rescue. And Decimal only recovers decimal text - Decimal(0.95) carries the
#     float's binary error, only Decimal("0.95") does not - so it would have to start at the
#     config, not here.
#
#   * The two barred rows carry headroom_shares=None by design (parsers.py decision 1), so
#     there is nothing to compare. They are not skipped silently: the assertion for them is
#     that utilisation is above the EXIT threshold, not the entry one, because a barred scrip
#     has already entered and is held by the 80% release. KAYNES at 92.17% and SAIL at 84.93%
#     both pass; an entry-threshold check would have failed on both, which is the SAIL finding
#     from #011 reasserting itself.
#
#   * That check is written as `not rules.compare("single_stock.ban.exit_utilisation", u)`,
#     so the direction stays in the config with the rest of them.
#
# STILL TO WRITE: reconcile(). All 218 rows, two paths, and a report a person reads at 18:40.
# What goes in it is a judgement call - a single maximum error is thin; count compared, count
# agreed, the worst offender by name and the residual spread is the shape these usually take.
# ===========================================================================


@dataclass(frozen=True)
class Residual:
    symbol: str
    residual: float          # yours - NSE's, expected in [0, 1)


@dataclass(frozen=True)
class BarredCheck:
    symbol: str
    utilisation: float
    held: bool               # True if utilisation is above the exit threshold


@dataclass(frozen=True)
class Reconciliation:
    trade_date: date
    rows_total: int
    residuals: tuple[Residual, ...]
    barred: tuple[BarredCheck, ...]
    failures: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.failures

    @property
    def min_residual(self) -> Residual | None:
        return min(self.residuals, key=lambda r: r.residual, default=None)

    @property
    def max_residual(self) -> Residual | None:
        return max(self.residuals, key=lambda r: r.residual, default=None)


def utilisation(futeq_oi: float, mwpl: int) -> float:
    """FutEq open interest as a fraction of MWPL.

    The number `SPEC.md` rows 4, 5 and 15 are all compared against. A fraction, not a
    percentage - 0.8493 for SAIL on 30 Oct - so it can go straight into
    `Threshold.compare()` without a scaling step somebody would eventually forget on one
    side of a comparison and not the other.
    """
    return futeq_oi / mwpl


def headroom_shares(row: MwplRow, rules: Rules) -> float:
    """Shares of fresh position available before the ban threshold, exactly.

    The 0.95 is read from the config rather than typed here, so it arrives carrying its
    operator, its circular and the date I read it, and moving the threshold is one YAML edit
    rather than a grep. Written as ``entry * mwpl - futeq_oi`` to match the arithmetic shape
    of NSE's own published column, which keeps a floating-point difference out of the
    reconciliation residual.

    Not truncated. NSE truncates its figure down to whole shares; truncating here too would
    drive the residual to zero and destroy the one thing `reconcile()` exists to measure.
    """
    entry = rules.value("single_stock.ban.entry_utilisation")
    return entry * row.mwpl - row.futeq_oi


def is_in_ban(
    futeq_oi: float,
    mwpl: int,
    *,
    was_in_ban_yesterday: bool,
    rules: Rules,
) -> bool:
    """Return whether the scrip is in the F&O ban period today.

    This is a state transition, not a measurement: between the exit and entry
    thresholds neither fires, so the answer depends on yesterday's state.

    Yesterday's state selects which single threshold applies:
      - already banned -> only the EXIT threshold is consulted
      - free           -> only the ENTRY threshold is consulted
    Both thresholds and their operators come from config/rules.yaml.
    """
    u = utilisation(futeq_oi, mwpl)
    if was_in_ban_yesterday:
        return not rules.compare("single_stock.ban.exit_utilisation", u)
    return rules.compare("single_stock.ban.entry_utilisation", u)


def reconcile(rows: tuple[MwplRow, ...], rules: Rules) -> Reconciliation:
    """Check the engine's arithmetic against NSE's published figures, row by row.

    Normal rows: our exact headroom minus NSE's truncated headroom must lie in
    [0, 1). Negative means NSE published more headroom than exists, the
    dangerous direction, so it fails.

    Barred rows: NSE prints no headroom, so we check consistency instead.
    A scrip already in ban is measured against the EXIT threshold, not the entry
    one, so NSE is right to keep it barred only while the config's exit rule does
    not release it. The direction comes from the config's `operator`, never from
    a comparison written here.

    Failures are collected, not raised, so one bad row doesn't hide the rest.
    The caller must check `.ok`.
    """
    if not rows:
        raise ValueError("reconcile() called with no rows")

    trade_date = rows[0].trade_date
    if any(r.trade_date != trade_date for r in rows):
        raise ValueError("reconcile() given rows from more than one trade date")

    # The Threshold object rather than its value, because this function needs both the
    # number (for the message) and the DIRECTION (for the test), and the direction is the
    # part that must not be retyped here. `u > exit.value` is identical today and stops
    # being identical the day SEBI rewords the release to "below 80%".
    exit_threshold = rules.get("single_stock.ban.exit_utilisation")

    residuals, barred, failures = [], [], []

    for row in rows:
        if row.no_fresh_positions:
            u = utilisation(row.futeq_oi, row.mwpl)
            held = not exit_threshold.compare(u)
            barred.append(BarredCheck(row.symbol, u, held))
            if not held:
                failures.append(
                    f"{row.symbol}: barred, but utilisation {u:.2%} "
                    f"is at or below the {exit_threshold.value:.0%} exit"
                )
        else:
            r = headroom_shares(row, rules) - row.headroom_shares
            residuals.append(Residual(row.symbol, r))
            if not (0 <= r < 1):
                failures.append(
                    f"{row.symbol}: residual {r:+.6f} outside [0, 1)"
                )

    # `ok` means "no failures", and no comparisons produce no failures - so a file where
    # NSE suppressed every headroom figure would otherwise reconcile clean. Recorded as a
    # failure rather than by special-casing `ok`, because a bare False with an empty
    # `failures` list tells a reader at 18:40 nothing about why.
    if not residuals:
        failures.append(
            f"{len(rows)} row(s) and not one carried a published headroom figure, "
            f"so nothing was reconciled"
        )

    return Reconciliation(
        trade_date=trade_date,
        rows_total=len(rows),
        residuals=tuple(residuals),
        barred=tuple(barred),
        failures=tuple(failures),
    )


# ===========================================================================
# SPEC ROW 6: the ban-period reduction check. Written 8 Nov.
#
# What it rests on, all recorded elsewhere so this block does not have to re-argue it:
#
#   * FutEq OI is in shares, so no prices are needed - NSE's per-contract delta factors carry
#     the pricing. `sentinel.book.futeq_delta()`.
#   * baseline = yesterday's holdings still live today, at today's factors. Only the active
#     part of a day's change (today - baseline) can breach; the passive part (baseline -
#     yesterday) is the market and the calendar.
#   * An expired contract contributes zero to the baseline - DECISIONS.md #014, confirmed from
#     the 27 Oct bhavcopy, where 13,590 contracts expiring that day still carry open interest at
#     their own close.
#   * A verified flat day is `PropBook.flat(date)`; a missing file is no PropBook at all -
#     DECISIONS.md #015.
#   * Both halves of the band come from config/rules.yaml: `reduction_floor` (same side of zero,
#     zero inclusive) and `reduction_ceiling` (no increase in magnitude). No direction is
#     written in Python.
#
# The oracle is SEBI 2025/79 Table 2 in tests/fixtures/book/, plus the seven expiry cases in
# tests/test_expiry.py. tests/test_ban_reduction.py calls this function against all of them.
# ===========================================================================


FLOOR_KEY = "single_stock.ban.reduction_floor"
CEILING_KEY = "single_stock.ban.reduction_ceiling"


def _fmt(d: Decimal) -> str:
    """Decimal without exponent noise: 0E-8 -> '0', 1000.00000000 -> '1000'."""
    return f"{d.normalize():f}"


@dataclass(frozen=True)
class ReductionCheck:
    """One UCC's position in one banned scrip, checked against SEBI 2025/79 para 5.3."""

    trade_date: dt.date
    ucc: str
    isin: str
    yesterday_delta: Decimal     # yesterday's holdings at yesterday's factors
    baseline: Decimal            # yesterday's holdings still live today, at today's factors
    today_delta: Decimal         # today's holdings at today's factors
    permitted: bool
    reason: str

    @property
    def passive(self) -> Decimal:
        """What the market and expiry did to positions already held."""
        return self.baseline - self.yesterday_delta

    @property
    def active(self) -> Decimal:
        """What the holder's change in holdings did, at constant factors."""
        return self.today_delta - self.baseline


def check_ban_period_reduction(
    today: PropBook,
    yesterday: PropBook,
    factors_today: DeltaFactors,
    factors_yesterday: DeltaFactors,
    symbol_for_isin: Mapping[str, str],
    banned_isins: frozenset[str],
    calendar: TradingCalendar,
    rules: Rules,
) -> tuple[ReductionCheck, ...]:
    """Check that no UCC increased its FutEq delta in a banned scrip.

    Scope: per UCC, per banned ISIN. This is a scope decision, not a dominance
    claim. Per-UCC and entity-level checks are incomparable: an entity whose
    offsetting legs unwind unevenly (A +10,000 -> +5,000, B -10,000 -> -2,000)
    passes per-UCC while its net goes 0 -> +3,000. An entity check will be added
    alongside this one, not instead of it. See docs/doubts.md.

    Both books are required. A day with no positions is PropBook.flat(date),
    built only from a FLAT marker row. A missing file is never a PropBook, so
    it cannot pass as flat.

    baseline = yesterday's holdings still live today (book.live_on), at
    today's factors. A contract that expired is physically settled, so its
    delta vanished without the holder acting: passive.

    Permitted iff today's delta stays on the baseline's side of zero (floor,
    zero inclusive) and is no larger in magnitude (ceiling). Both halves come
    from rules.yaml; no direction is written in this function.
    """
    trade_date = today.trade_date

    if factors_today.trade_date != trade_date:
        raise BookError(
            f"today's book is {trade_date} but today's factors are "
            f"{factors_today.trade_date}"
        )

    # Raises ChainUnverifiedError on unverified days (e.g. Muhurat), so the
    # check fails closed there with no code of its own.
    expected_yesterday = calendar.previous_trading_day(trade_date)
    if yesterday.trade_date != expected_yesterday:
        raise BookError(
            f"yesterday's book is {yesterday.trade_date}, but the previous trading "
            f"day before {trade_date} is {expected_yesterday}. Comparing against a "
            f"stale book would score several days of trading as one."
        )

    if factors_yesterday.trade_date != yesterday.trade_date:
        raise BookError(
            f"yesterday's book is {yesterday.trade_date} but its factors are "
            f"{factors_yesterday.trade_date}"
        )

    pairs = {
        (p.ucc, p.isin)
        for book in (today, yesterday)
        for p in book
        if p.isin in banned_isins
    }

    checks: list[ReductionCheck] = []

    for ucc, isin in sorted(pairs):
        y_positions = yesterday.for_ucc(ucc, isin)
        t_positions = today.for_ucc(ucc, isin)
        live = live_on(y_positions, trade_date)

        yesterday_delta = futeq_delta(y_positions, factors_yesterday, symbol_for_isin)
        baseline = futeq_delta(live, factors_today, symbol_for_isin)
        today_delta = futeq_delta(t_positions, factors_today, symbol_for_isin)

        # Express today's delta in the baseline's direction, so one floor
        # covers longs and shorts alike.
        normalised = today_delta if baseline >= 0 else -today_delta
        growth = abs(today_delta) - abs(baseline)

        same_side = rules.compare(FLOOR_KEY, normalised)
        not_larger = rules.compare(CEILING_KEY, growth)
        permitted = same_side and not_larger

        checks.append(ReductionCheck(
            trade_date=trade_date,
            ucc=ucc,
            isin=isin,
            yesterday_delta=yesterday_delta,
            baseline=baseline,
            today_delta=today_delta,
            permitted=permitted,
            reason=_reason(baseline, today_delta, yesterday_delta, permitted),
        ))

    return tuple(checks)


def _reason(baseline: Decimal, today: Decimal, yesterday: Decimal,
            permitted: bool) -> str:
    """One label per kind of event, so the same event always reads the same way."""
    passive = baseline - yesterday
    active = today - baseline
    note = f" (passive move {_fmt(passive)})" if passive != 0 else ""

    if permitted:
        if active == 0:
            return f"no net change from trading{note}"
        if today == 0:
            return f"closed out from {_fmt(baseline)}{note}"
        return f"reduced by {_fmt(abs(baseline) - abs(today))}{note}"

    if baseline == 0:
        return f"fresh position of {_fmt(today)} in a banned scrip{note}"
    if today != 0 and (baseline > 0) != (today > 0):
        return f"crossed zero: baseline {_fmt(baseline)}, today {_fmt(today)}{note}"
    return f"increased by {_fmt(abs(today) - abs(baseline))} from {_fmt(baseline)}{note}"


# ===========================================================================
# YOURS TO WRITE: SPEC row 7, the entity limits.
#
# The percentages are already in config/rules.yaml under single_stock.entity_limits, each with
# its paragraph. Its sting is in the fifth category: FPI Category II splits at 10% or 20%
# depending on whether the holder is an individual, family office or corporate, so collapsing
# Cat II to one number is the likely bug - which is why SPEC row 7 names a test for exactly that.
#
# Same two questions as row 6 before writing: what the signature is, and what it returns. A bool
# loses which entity, which category and by how much.
# ===========================================================================


def check_entity_limit(category: str, futeq_oi: float, mwpl: int, rules: Rules):
    """Whether an entity's FutEq OI is inside its category's share of MWPL (SPEC row 7).

    The signature is the one SPEC row 7 names, with `rules` added because the percentages come
    from config/rules.yaml and not from a literal here. The return type is yours.
    """
    raise NotImplementedError("mine to write")
