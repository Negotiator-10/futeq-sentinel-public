"""Who holds a position, for the entity-level limits in SPEC row 7.

SEBI 2025/79 para 5.8.1 sets each limit as a share of MWPL by category of holder. This module
names the categories and maps each to its threshold in `config/rules.yaml`. It decides nothing
about limits - `check_entity_limit()` in `engine.py` does that.

**FPI Category II is two members and never one.** Para 5.8.1.4 gives Cat II FPIs 20% of MWPL
*other than* those in the sub-category of individuals, family offices and corporates; para
5.8.1.5 gives that sub-category 10%. NSE's own Clearing FAQ, question 15, summarises the split as
individuals versus "non-individuals" - which files Cat II corporates and family offices at 20%,
double what SEBI allows them. So there is no bare Cat II member, and a Cat II holder can only be
categorised through `for_fpi_cat_ii()`, which places corporates and family offices with
individuals as SEBI does. `DECISIONS.md` #016, `docs/doubts.md` entry 8.

**TM (proprietary + client) is not a category of any single UCC.** It is a limit on an
aggregate: a trading member's own book plus its clients' books. So it is not an enum member here;
the limit is applied by the function that aggregates, which is decision 3 of #016.
"""

from __future__ import annotations

import csv
import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

__all__ = [
    "Category",
    "TM_COMBINED_LIMIT_KEY",
    "CategoryError",
    "Holder",
    "Account",
    "ReferenceDataError",
    "Snapshot",
    "ReferenceData",
    "load_reference",
]

_LIMITS = "single_stock.entity_limits."

#: The limit on a trading member's proprietary and client positions together - para 5.8.1.3.
TM_COMBINED_LIMIT_KEY = _LIMITS + "tm_prop_plus_client"

#: The three Cat II sub-categories para 5.8.1.5 names, and only those. At module level rather
#: than inside `Category`, because any plain attribute in an Enum body becomes a member - this
#: would have been a frozenset-valued seventh category.
_FPI_CAT_II_IFC = frozenset({"individual", "family_office", "corporate"})


class CategoryError(Exception):
    """A holder whose category cannot be established. Refused rather than defaulted."""


class Category(Enum):
    """The category one UCC's holder falls in. Values are the keys in `config/rules.yaml`."""

    CLIENT_NRI = "client_nri"                                   # 5.8.1.1, 10%
    TM_PROPRIETARY = "tm_proprietary"                           # 5.8.1.2, 20%
    FPI_CAT_I = "fpi_cat_1"                                     # 5.8.1.3, 30%
    MUTUAL_FUND = "mutual_fund"                                 # 5.8.1.3, 30%
    FPI_CAT_II_OTHER = "fpi_cat_2_other"                        # 5.8.1.4, 20%
    FPI_CAT_II_IFC = "fpi_cat_2_individual_family_corporate"    # 5.8.1.5, 10%

    @property
    def limit_key(self) -> str:
        """The dotted path of this category's limit in `config/rules.yaml`."""
        return _LIMITS + self.value

    @classmethod
    def for_fpi_cat_ii(cls, sub_category: str) -> Category:
        """Place a Category II FPI by its sub-category, the way SEBI does and NSE's FAQ does not.

        Individuals, family offices and corporates go to the 10% group. Anything else has to be
        stated as `"other"` explicitly. An unrecognised sub-category is refused rather than
        defaulted, because the only available default is 20%, which is the lenient direction -
        exactly the error the FAQ's wording would produce for a corporate.
        """
        key = sub_category.strip().lower().replace(" ", "_")
        if key in _FPI_CAT_II_IFC:
            return cls.FPI_CAT_II_IFC
        if key == "other":
            return cls.FPI_CAT_II_OTHER
        raise CategoryError(
            f"FPI Category II sub-category {sub_category!r} is not one SEBI 2025/79 para 5.8.1.5 "
            f"names. Use 'individual', 'family_office' or 'corporate' for the 10% group, or "
            f"'other' for 20%. Not defaulted - the default would be the lenient 20%, and that is "
            f"how NSE FAQ 15's 'non-individuals' wording misfiles a corporate."
        )


# -- reference data: who holds which account -----------------------------------------------
#
# Two date-effective tables, decided in #016's addendum:
#
#     holders   (effective_from, holder_id, category, sub_category)
#     accounts  (effective_from, tm, ucc, holder_id, is_proprietary)
#
# Accounts are keyed on (tm, ucc), not ucc, because a UCC is a code a trading member assigns:
# the same string can exist under two brokers and belong to two different holders.
#
# The trading member is a property of the ACCOUNT, not of the holder. A client can hold UCCs at
# two brokers; the client's own 10% gross-adds both, while each broker's 30% counts only the UCC
# registered under it. So the aggregates are:
#
#     a holder's own limit      all of the holder's accounts, across every TM
#     a TM's 20%                that TM's proprietary accounts
#     a TM's 30%                that TM's proprietary accounts, plus CLIENT/NRI accounts
#                               registered under it - NOT FPI or MF accounts, which SEBI treats
#                               as trading members in their own right (Master Circular cl
#                               1.3.3.3, imported for stocks by 4.3.3.3)
#
# "Date-effective" means each row applies from its effective_from until a later row for the same
# key replaces it. There is no end-dating: an account that has closed simply carries no
# positions, and contributes zero to every aggregate, so leaving its row in place is harmless.


class ReferenceDataError(Exception):
    """Reference data that cannot be trusted to aggregate positions correctly."""


@dataclass(frozen=True)
class Holder:
    """One beneficial holder and the category its limit comes from."""

    holder_id: str
    category: Category
    effective_from: dt.date


@dataclass(frozen=True)
class Account:
    """One UCC under one trading member, and who holds it."""

    tm: str
    ucc: str
    holder_id: str
    is_proprietary: bool
    effective_from: dt.date

    @property
    def key(self) -> tuple[str, str]:
        return (self.tm, self.ucc)


class Snapshot:
    """The reference data as it stood on one date, with its invariants already checked."""

    def __init__(self, day: dt.date, holders: Mapping[str, Holder],
                 accounts: Mapping[tuple[str, str], Account]) -> None:
        self.day = day
        self._holders = dict(holders)
        self._accounts = dict(accounts)
        self._validate()

    def _validate(self) -> None:
        for account in self._accounts.values():
            holder = self._holders.get(account.holder_id)
            if holder is None:
                raise ReferenceDataError(
                    f"{self.day}: account {account.tm}/{account.ucc} belongs to holder "
                    f"{account.holder_id!r}, which has no holders row effective by then. An "
                    f"account whose holder is unknown has no limit to be checked against."
                )
            is_tm_holder = holder.category is Category.TM_PROPRIETARY
            if account.is_proprietary != is_tm_holder:
                raise ReferenceDataError(
                    f"{self.day}: account {account.tm}/{account.ucc} is "
                    f"{'' if account.is_proprietary else 'not '}marked proprietary, but its "
                    f"holder {holder.holder_id} is {holder.category.value}. The two fields say "
                    f"the same thing, so they must agree - a proprietary account belongs to a "
                    f"trading member's own book and nothing else does."
                )
            # A TM's holder_id IS its member code - a convention, enforced here rather than
            # stated in prose. NSE's member code already identifies the TM uniquely, so it serves
            # as the holder id instead of a second `tm` column on holders that could disagree
            # with it. Without this, TMB's book could be filed as TMA's proprietary account and
            # TMA's 20% computed on positions TMA does not own. It also makes a TM's proprietary
            # book single-owned by construction, which an earlier check had to test separately.
            if account.is_proprietary and account.holder_id != account.tm:
                raise ReferenceDataError(
                    f"{self.day}: proprietary account {account.tm}/{account.ucc} is owned by "
                    f"{account.holder_id}; a TM's proprietary book must be owned by that TM. "
                    f"A trading member's holder_id is its member code."
                )

    def __repr__(self) -> str:
        return (f"<Snapshot {self.day} {len(self._holders)} holder(s), "
                f"{len(self._accounts)} account(s)>")

    # -- lookups --------------------------------------------------------------------------

    def holder(self, holder_id: str) -> Holder:
        try:
            return self._holders[holder_id]
        except KeyError:
            raise ReferenceDataError(f"{self.day}: no holder {holder_id!r}") from None

    def account(self, tm: str, ucc: str) -> Account:
        """Refuses an unknown account rather than guessing whose it is. A position in an account
        with no reference row cannot be attributed to any limit, which needs a person."""
        try:
            return self._accounts[(tm, ucc)]
        except KeyError:
            raise ReferenceDataError(
                f"{self.day}: no account {tm}/{ucc}. A position in an unknown account cannot be "
                f"attributed to any holder's limit."
            ) from None

    @property
    def holders(self) -> tuple[Holder, ...]:
        return tuple(sorted(self._holders.values(), key=lambda h: h.holder_id))

    @property
    def trading_members(self) -> tuple[str, ...]:
        return tuple(sorted({a.tm for a in self._accounts.values()}))

    def accounts_of(self, holder_id: str) -> tuple[Account, ...]:
        """Every account of one holder, across every trading member - a holder's own limit."""
        return tuple(sorted((a for a in self._accounts.values() if a.holder_id == holder_id),
                            key=lambda a: a.key))

    def proprietary_accounts_of(self, tm: str) -> tuple[Account, ...]:
        """A trading member's own book - its 20%."""
        return tuple(sorted((a for a in self._accounts.values()
                             if a.tm == tm and a.is_proprietary), key=lambda a: a.key))

    def combined_accounts_of(self, tm: str) -> tuple[Account, ...]:
        """A trading member's 30%: its proprietary accounts plus CLIENT/NRI accounts under it.

        FPI and MF accounts registered under the TM are excluded, because SEBI treats FPIs and
        MFs as trading members in their own right for position limits.
        """
        return tuple(sorted(
            (a for a in self._accounts.values()
             if a.tm == tm and (a.is_proprietary
                                or self._holders[a.holder_id].category is Category.CLIENT_NRI)),
            key=lambda a: a.key))


class ReferenceData:
    """Every holders and accounts row ever loaded, resolvable to any date."""

    def __init__(self, holders: list[Holder], accounts: list[Account]) -> None:
        self._holders = holders
        self._accounts = accounts

    def as_of(self, day: dt.date) -> Snapshot:
        """The latest row for each key with effective_from on or before `day`."""
        holders: dict[str, Holder] = {}
        for h in sorted(self._holders, key=lambda h: h.effective_from):
            if h.effective_from <= day:
                holders[h.holder_id] = h
        accounts: dict[tuple[str, str], Account] = {}
        for a in sorted(self._accounts, key=lambda a: a.effective_from):
            if a.effective_from <= day:
                accounts[a.key] = a
        return Snapshot(day, holders, accounts)


def _blank(rec: Mapping[str, str | None]) -> bool:
    return all(not (v or "").strip() for v in rec.values())


def _require(reader: csv.DictReader, expected: set[str], path: Path) -> None:
    missing = expected - set(reader.fieldnames or [])
    if missing:
        raise ReferenceDataError(f"{path}: missing column(s) {sorted(missing)}")


def _date(text: str, path: Path, lineno: int) -> dt.date:
    try:
        return dt.date.fromisoformat((text or "").strip())
    except ValueError as exc:
        raise ReferenceDataError(f"{path} line {lineno}: effective_from {text!r} is not YYYY-MM-DD") from exc


def _parse_holder(rec: Mapping[str, str], path: Path, lineno: int) -> Holder:
    holder_id = (rec["holder_id"] or "").strip()
    if not holder_id:
        raise ReferenceDataError(f"{path} line {lineno}: no holder_id")
    raw = (rec["category"] or "").strip().lower()
    try:
        category = Category(raw)
    except ValueError:
        raise ReferenceDataError(
            f"{path} line {lineno}: category {rec['category']!r} is not one of "
            f"{', '.join(c.value for c in Category)}. In particular there is no bare FPI "
            f"Category II - it is two categories (#016 decision 1)."
        ) from None

    sub = (rec.get("sub_category") or "").strip()
    is_cat_ii = category in (Category.FPI_CAT_II_IFC, Category.FPI_CAT_II_OTHER)
    if is_cat_ii:
        # Decision 1: a Cat II holder is categorised only through for_fpi_cat_ii(). Storing the
        # final category alone would let a corporate be typed in as `fpi_cat_2_other` - NSE FAQ
        # 15's error, entered by hand. So the sub-category is required and must agree.
        if not sub:
            raise ReferenceDataError(
                f"{path} line {lineno}: {holder_id} is FPI Category II but has no sub_category. "
                f"Cat II needs one - 'individual', 'family_office', 'corporate' or 'other' - so "
                f"the 10%/20% split is derived, not typed."
            )
        try:
            derived = Category.for_fpi_cat_ii(sub)
        except CategoryError as exc:
            raise ReferenceDataError(f"{path} line {lineno}: {exc}") from exc
        if derived is not category:
            raise ReferenceDataError(
                f"{path} line {lineno}: {holder_id} is filed as {category.value} but its "
                f"sub_category {sub!r} places it in {derived.value}. SEBI para 5.8.1.5 puts "
                f"individuals, family offices and corporates at 10%; the row contradicts itself."
            )
    elif sub:
        raise ReferenceDataError(
            f"{path} line {lineno}: {holder_id} is {category.value} and carries sub_category "
            f"{sub!r}. Only FPI Category II has a sub-category."
        )
    return Holder(holder_id, category, _date(rec["effective_from"], path, lineno))


def _parse_account(rec: Mapping[str, str], path: Path, lineno: int) -> Account:
    tm, ucc, holder_id = ((rec[k] or "").strip() for k in ("tm", "ucc", "holder_id"))
    for name, value in (("tm", tm), ("ucc", ucc), ("holder_id", holder_id)):
        if not value:
            raise ReferenceDataError(f"{path} line {lineno}: no {name}")
    flag = (rec["is_proprietary"] or "").strip().lower()
    if flag not in ("true", "false"):
        raise ReferenceDataError(
            f"{path} line {lineno}: is_proprietary is {rec['is_proprietary']!r}. Write true or "
            f"false - a blank here is not 'no', it is a row nobody finished."
        )
    return Account(tm, ucc, holder_id, flag == "true", _date(rec["effective_from"], path, lineno))


def load_reference(holders_path: str | Path, accounts_path: str | Path) -> ReferenceData:
    """Load both tables. Invariants that span them are checked per date, by `as_of()`."""
    hp, ap = Path(holders_path), Path(accounts_path)

    holders: list[Holder] = []
    seen_h: dict[tuple[dt.date, str], int] = {}
    with hp.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        _require(reader, {"effective_from", "holder_id", "category", "sub_category"}, hp)
        for lineno, rec in enumerate(reader, start=2):
            if _blank(rec):
                continue
            h = _parse_holder(rec, hp, lineno)
            key = (h.effective_from, h.holder_id)
            if key in seen_h:
                raise ReferenceDataError(
                    f"{hp} line {lineno}: {h.holder_id} has two rows effective "
                    f"{h.effective_from} (the first on line {seen_h[key]}). Which applies?"
                )
            seen_h[key] = lineno
            holders.append(h)

    accounts: list[Account] = []
    seen_a: dict[tuple[dt.date, str, str], int] = {}
    with ap.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        _require(reader, {"effective_from", "tm", "ucc", "holder_id", "is_proprietary"}, ap)
        for lineno, rec in enumerate(reader, start=2):
            if _blank(rec):
                continue
            a = _parse_account(rec, ap, lineno)
            key = (a.effective_from, a.tm, a.ucc)
            if key in seen_a:
                raise ReferenceDataError(
                    f"{ap} line {lineno}: {a.tm}/{a.ucc} has two rows effective "
                    f"{a.effective_from} (the first on line {seen_a[key]}). Which applies?"
                )
            seen_a[key] = lineno
            accounts.append(a)

    if not holders or not accounts:
        raise ReferenceDataError(
            f"{hp if not holders else ap}: no rows. An empty reference table attributes every "
            f"position to nobody, which is a missing file rather than an empty book."
        )
    return ReferenceData(holders, accounts)
