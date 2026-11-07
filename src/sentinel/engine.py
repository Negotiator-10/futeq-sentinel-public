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

from dataclasses import dataclass
from datetime import date

from sentinel.book import Position
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
# YOURS TO WRITE. Two limit checks, and everything they rest on is settled.
#
# SPEC.md row 6 and row 7. The plumbing is in `sentinel.book`: Position with its invariants,
# PropBook for one day, DeltaFactors for NSE's published per-contract factors, and
# futeq_delta() which turns holdings plus factors into a FutEq delta in shares.
#
# WHAT IS ALREADY DECIDED, so you do not have to re-derive it:
#
#   * FutEq OI is in SHARES, not rupees. Para 5.1.1 defines delta as a multiple of the notional
#     position, Table 1 shows 300 long futures as FutEq OI 300, and the headroom reconciliation
#     matches NSE's column on 216 of 216 rows - impossible if one side were rupees.
#
#   * No prices are needed. NSE's Contract_Delta factors are per unit with the pricing done:
#     exactly 1.0 for futures, [0, 1] for calls, [-1, 0] for puts. A signed quantity_lots gives
#     the right sign for short positions without special-casing.
#
#   * The decomposition, decided 7 Nov. Each day's delta change splits into
#         passive = baseline - yesterday's actual delta
#         active  = today's actual delta - baseline
#     where  baseline = futeq_delta(YESTERDAY's positions, TODAY's factors).
#     Only the active part can breach. This needs two consecutive days of per-contract holdings
#     and nothing else - NOT trade fills, which was the earlier recorded finding and was
#     stronger than the rule requires.
#
#   * The permitted band, from para 5.3.2 and Table 2:
#         permitted if  delta_today * baseline >= 0  and  |delta_today| <= |baseline|
#     Worked against all six cases in the circular. Note what falls out of it: a baseline of
#     zero forces delta_today to zero, so "No Fresh Positions" is a CONSEQUENCE of this one
#     expression rather than a separate rule.
#
#   * Zero is inclusive. 5.3.2 says delta "could be reduced till 0"; Table 2 day 4 says "above
#     0". Closing out completely cannot sensibly be a breach, so the floor is >= 0. The wording
#     difference is recorded next to the threshold in config/rules.yaml.
#
# WHAT YOU STILL DECIDE:
#
#   1. The signature. Row 6's check needs yesterday's positions, today's positions, today's
#      factors, the ISIN-to-symbol map and `rules`. Which of those are positional, which are
#      keyword-only, and in what order - you made that call well on is_in_ban().
#
#   2. What it returns. A bool loses the reason, and a desk needs to be told which scrip, which
#      direction, and by how much. You chose the shape of Reconciliation yourself and it was
#      better than the scaffold I gave you; do the same here.
#
#   3. Expiry and rolls. A contract expiring is not a trade; rolling into the next month closes
#      one position and opens another. Your passive/active split already implies an answer -
#      check whether it is the one you want, and whether para 5.3.2 cares about the act or
#      about the resulting delta.
#
#   4. The unit of the check. Row 6 says "entities", and 5.1.2 nets within a UCC then
#      gross-adds across UCCs. Is the ban-period test per UCC, or per entity above it? The
#      answer decides whether one client can offset another's position.
#
# The fixture is SEBI's own Table 2, in tests/fixtures/book/, with a seventh day that shows the
# genuine passive increase the circular's day 2 reaches for and cannot produce:
#
#   day  date        holdings             FutEq delta  baseline   expected
#    1   2026-10-12  +1 FUT                    1000.0      n/a    (entry day)
#    2   2026-10-13  +1 FUT                    1000.0   1000.0    permitted
#    3   2026-10-14  +1 FUT +1 PE               600.0   1000.0    permitted
#    4   2026-10-15  +1 FUT +1 PE -1 CE         250.0    600.0    permitted
#    5   2026-10-16  +2 FUT +1 PE -1 CE        1250.0    250.0    BREACH
#    6   2026-10-19  +2 FUT +1 PE -1 CE        1250.0   1250.0    permitted
#    7   2026-10-21  +2 FUT +1 PE -1 CE        1450.0   1450.0    permitted, rose 200 passively
#
# Row 7 is the simpler of the two and the percentages are already in config/rules.yaml under
# single_stock.entity_limits. Its sting is in the fifth category: FPI Category II splits at 10%
# or 20% depending on whether the holder is an individual, family office or corporate, so
# collapsing Cat II to one number is the likely bug - which is why SPEC row 7 names a test for
# exactly that.
# ===========================================================================


def check_ban_period_reduction(*args, **kwargs):
    """Whether a day's trading reduced FutEq OI as para 5.3.2 requires. Signature yours."""
    raise NotImplementedError("mine to write")


def check_entity_limit(category: str, futeq_oi: float, mwpl: int, rules: Rules):
    """Whether an entity's FutEq OI is inside its category's share of MWPL (SPEC row 7).

    The signature is the one SPEC row 7 names, with `rules` added because the percentages come
    from config/rules.yaml and not from a literal here. The return type is yours.
    """
    raise NotImplementedError("mine to write")
