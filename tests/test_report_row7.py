"""The report's row 7 section (section 4). Layout, by Claude, 12 Nov 2026.

The first group calls `_row7()` directly on stored-shape values and passes now. The second
renders a day through the runner, so it waits on the row 7 stage, as `test_runner_row7.py`'s
stage tests do.

The rule the section keeps is #019's: refused is never zero. A whole-stage refusal says
"Refused:" and why; a scrip refused for want of an MWPL is named, with the holders it affected;
and nothing stored with no refusal is said as that, not as "0 breaches", because the store cannot
yet tell a flat book from a run that predates row 7.
"""

from __future__ import annotations

import datetime as dt
import shutil
from decimal import Decimal

from sentinel import report
from sentinel.engine import EntityLimitCheck, EntityLimitResult, LimitCause, NotChecked
from sentinel.entities import TM_COMBINED_LIMIT_KEY, Category
from sentinel.store import Refusal, RefusalStage
from tests.test_report import stand_ins  # noqa: F401  (a fixture, used by name)
from tests.test_runner_row7 import D13, NO_MWPL, QUIET, row7_paths, run

CLIENT = Category.CLIENT_NRI.limit_key
TM = Category.TM_PROPRIETARY.limit_key
SYMBOLS = {QUIET: "QUIETCO"}


def a_check(holder, limit_key, g, limit, *, cause=None, reason="within limit"):
    g, limit = Decimal(g), Decimal(limit)
    permitted = cause is None
    return EntityLimitCheck(
        trade_date=D13, holder_id=holder, isin=QUIET, limit_key=limit_key,
        accounts=(("TMA", "C1"),), gross_futeq=g, mwpl=1_000_000, limit_shares=limit,
        excess_shares=Decimal(0) if permitted else g - limit, permitted=permitted,
        cause=cause, reason=reason)


def section(result=EntityLimitResult(()), refusals=()) -> str:
    return "\n".join(report._row7(result, tuple(refusals), SYMBOLS))


# -- the section on its own (passes now) -------------------------------------------------


def test_a_whole_stage_refusal_says_refused_and_why_never_zero():
    text = section(refusals=[Refusal(D13, RefusalStage.ROW7, "", "missing: holders.csv")])
    assert "Refused: missing: holders.csv." in text
    assert "None" not in text and "0 " not in text and "Nothing checked" not in text


def test_nothing_stored_and_no_refusal_is_said_as_that_not_as_none():
    text = section()
    assert "Nothing checked, and no refusal recorded" in text
    assert "predates row 7" in text
    assert "None:" not in text


def test_another_stages_refusal_is_not_read_as_row_7s():
    text = section(refusals=[Refusal(D13, RefusalStage.ROW6, "", "missing: positions.csv")])
    assert "Refused" not in text
    assert "Nothing checked, and no refusal recorded" in text


def test_checks_that_all_pass_give_their_count():
    result = EntityLimitResult((a_check("H1", CLIENT, 90_000, "100000.00"),
                                a_check("TMA", TM, 50_000, "200000.00")))
    assert "None: 2 check(s), every one permitted." in section(result)


def test_a_breach_shows_its_limit_excess_and_cause():
    breach = a_check("H1", CLIENT, 120_000, "100000.00", cause=LimitCause.ACTIVE,
                     reason="over by 20000 shares; holdings added 10000 to the gross position")
    text = section(EntityLimitResult((breach, a_check("TMA", TM, 50_000, "200000.00"))))
    assert "**1 breach(es).**" in text
    assert ("| H1 | QUIETCO | client_nri | 120000 | 100000 | 20000 | active | "
            "over by 20000 shares; holdings added 10000 to the gross position |") in text
    assert "1 of 2 check(s) breached." in text


def test_a_scrip_with_no_mwpl_is_named_with_the_holders_it_affected():
    result = EntityLimitResult(
        (a_check("TMA", TM, 50_000, "200000.00"),),
        (NotChecked(D13, "H1", NO_MWPL, CLIENT, "no MWPL for this scrip in today's combineoi"),
         NotChecked(D13, "TMA", NO_MWPL, TM_COMBINED_LIMIT_KEY,
                    "no MWPL for this scrip in today's combineoi")))
    refusal = Refusal(D13, RefusalStage.ROW7, NO_MWPL,
                      "no MWPL in today's combineoi; 2 checks not made")
    text = section(result, [refusal])
    assert "None: 1 check(s), every one permitted." in text
    assert (f"- {NO_MWPL}: no MWPL in today's combineoi; 2 checks not made. "
            f"Holders: H1 (client_nri), TMA (tm_prop_plus_client).") in text


def test_only_scrips_refused_and_no_checks_say_none_could_be_made():
    result = EntityLimitResult((), (NotChecked(D13, "H1", NO_MWPL, CLIENT, "no MWPL"),))
    refusal = Refusal(D13, RefusalStage.ROW7, NO_MWPL, "no MWPL in today's combineoi; 1 checks not made")
    text = section(result, [refusal])
    assert "No check could be made." in text
    assert "Nothing checked, and no refusal" not in text and "None:" not in text


# -- through the runner (waits on the row 7 stage) ---------------------------------------


def row7_of(text: str) -> str:
    return text.split("## 4. Row 7: entity limits")[1].split("## 5.")[0]


def test_a_rendered_day_shows_the_breach_from_the_store(tmp_path, stand_ins):
    paths = row7_paths(tmp_path)
    run(paths, D13)
    text = report.render(D13, paths)
    row7 = row7_of(text)
    assert "| H1 | QUIETCO | client_nri | 120000 | 100000 | 20000 | active |" in row7
    assert "1 of 3 check(s) breached." in row7
    shutil.rmtree(paths.data)                     # rendered from the store, not the files
    assert report.render(D13, paths) == text


def test_a_rendered_refusal_says_refused(tmp_path, stand_ins):
    paths = row7_paths(tmp_path)
    paths.holders().unlink()
    run(paths, D13)
    row7 = row7_of(report.render(D13, paths))
    assert "Refused: missing: holders.csv." in row7
    assert "None" not in row7 and "Nothing checked" not in row7
