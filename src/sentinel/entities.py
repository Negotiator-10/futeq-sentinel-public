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

from enum import Enum

__all__ = ["Category", "TM_COMBINED_LIMIT_KEY", "CategoryError"]

_LIMITS = "single_stock.entity_limits."

#: The limit on a trading member's proprietary and client positions together - para 5.8.1.3.
TM_COMBINED_LIMIT_KEY = _LIMITS + "tm_prop_plus_client"

#: The three Cat II sub-categories para 5.8.1.5 names, and only those. At module level rather
#: than inside `Category`, because any plain attribute in an Enum body becomes a member - this
#: would have been a frozenset-valued sixth category.
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
