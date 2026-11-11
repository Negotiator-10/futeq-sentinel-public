"""Validated loader for `config/rules.yaml`.

Every regulatory threshold the engine applies comes from here, and this module is the only way
in. It exists because a threshold can be wrong in two very different ways:

* **Loudly.** A missing key, a string where a number belongs, a block that does not parse. The
  engine crashes, someone looks, the bug is fixed in ten minutes.
* **Silently.** A plausible number with no source behind it, or an assumption nobody wrote down.
  The engine runs, produces answers that look exactly like correct answers, and nobody looks.

Only the second kind matters. So this loader refuses, at load time, to hand over any threshold
that cannot say where it came from, and refuses at every access to evaluate one the config
itself admits is unknown. A null with a reason is a finding; a plausible number is a liability.

Three states, from the header of `config/rules.yaml`:

    verified: <date>            usable
    verified: null + an         usable, but tagged `assumed` and warned about once at load
      "ASSUMPTION" source
    listed in meta.unverified   value is null; `get()` raises UnverifiedRuleError

Typical use::

    rules = load_rules()
    entry = rules.get("single_stock.ban.entry_utilisation")
    if entry.compare(utilisation):          # applies the ">" from the config
        ...                                 # 0.95 is NOT a ban; 0.950001 is

    rules.get("single_stock.ban.penalty_rate")      # raises UnverifiedRuleError
    rules.describe("single_stock.ban.penalty_rate") # returns it, for a report
"""

from __future__ import annotations

import datetime as _dt
import operator as _operator
import warnings
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator, Mapping

import yaml

__all__ = [
    "Threshold",
    "Rules",
    "RuleConfigError",
    "UnverifiedRuleError",
    "load_rules",
    "DEFAULT_CONFIG_PATH",
]

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "rules.yaml"

#: Keys a threshold mapping may carry. Anything else is a typo, and a typo in a config of
#: regulatory limits is exactly the silent failure this module exists to prevent: a misspelled
#: `operatro` would leave the comparison direction at its default and nothing would complain.
_REQUIRED_KEYS = frozenset({"value", "source", "verified"})
_OPTIONAL_KEYS = frozenset({"operator", "note"})
_ALLOWED_KEYS = _REQUIRED_KEYS | _OPTIONAL_KEYS

#: The only comparison directions a threshold may declare. `operator` encodes which side of a
#: boundary counts, nothing more. "Higher of X or Y" is not an operator - it is two limbs and a
#: MAX, and belongs in the function that implements the rule.
_OPERATORS: Mapping[str, Any] = {
    ">": _operator.gt,
    ">=": _operator.ge,
    "<": _operator.lt,
    "<=": _operator.le,
    "==": _operator.eq,
}

#: A `verified: null` is only honest if the source says so in as many words.
_ASSUMPTION_PREFIX = "ASSUMPTION"
_UNVERIFIED_PREFIX = "UNVERIFIED"

#: Top-level keys that are configuration about the config, not thresholds.
_META_KEY = "meta"


class RuleConfigError(Exception):
    """The config file is unusable. Raised at load time, never later.

    Every message names the dotted path of the offending threshold, because the alternative is
    a stack trace that says "KeyError: 'source'" about one of two hundred entries.
    """


class UnverifiedRuleError(Exception):
    """A threshold was requested that the config itself marks as unknown.

    This is not a bug in the caller and not a bug in the config. It is the config refusing to
    let the engine invent a number. The fix is to find the circular, not to catch this.
    """


@dataclass(frozen=True)
class Threshold:
    """One regulatory threshold, with the provenance that makes it usable."""

    path: str
    value: Any
    source: str
    verified: _dt.date | None
    operator: str | None = None
    note: str = ""
    assumed: bool = False

    def compare(self, observed: Any) -> bool:
        """True when `observed` stands in the relation `operator` to `value`.

        This is how the entry/exit asymmetry stays out of the code. Ban entry carries ``">"``,
        so utilisation of exactly 0.95 compares False and is not a ban. Ban exit carries
        ``"<="``, so exactly 0.80 compares True and is a release. Neither direction is written
        down anywhere in the engine.
        """
        if self.operator is None:
            raise RuleConfigError(
                f"{self.path}: no operator declared, so there is no comparison to make. "
                f"Use .value and write the rule explicitly."
            )
        value = self.value
        if isinstance(observed, Decimal) and isinstance(value, float):
            # Compare a Decimal against the threshold as written, not as a binary float. The
            # float 0.95 is 0.94999999999999995559, so Decimal("0.95") > 0.95 is True: without
            # this, a scrip exactly on 95% would be banned - entry is "exceeds", strictly.
            value = Decimal(str(value))
        return bool(_OPERATORS[self.operator](observed, value))


class Rules:
    """A loaded, validated set of thresholds, addressed by dotted path."""

    def __init__(
        self,
        thresholds: Mapping[str, Threshold],
        unverified: tuple[str, ...],
        meta: Mapping[str, Any],
        path: Path,
    ) -> None:
        self._thresholds = dict(thresholds)
        self.unverified = unverified
        self.meta = dict(meta)
        self.path = path

    # -- access ---------------------------------------------------------------

    def get(self, dotted_path: str) -> Threshold:
        """The threshold at `dotted_path`.

        Raises `UnverifiedRuleError` if the config lists it under `meta.unverified`, and
        `KeyError` if there is no such threshold.
        """
        if dotted_path in self.unverified:
            threshold = self._thresholds[dotted_path]
            raise UnverifiedRuleError(
                f"{dotted_path} is listed in meta.unverified and may not be evaluated.\n"
                f"  source: {threshold.source}\n"
                f"  note:   {threshold.note}"
            )
        return self._thresholds[dotted_path]

    def value(self, dotted_path: str) -> Any:
        """Shorthand for ``get(path).value``, with the same refusals."""
        return self.get(dotted_path).value

    def compare(self, dotted_path: str, observed: Any) -> bool:
        """Shorthand for ``get(path).compare(observed)``, with the same refusals."""
        return self.get(dotted_path).compare(observed)

    def describe(self, dotted_path: str) -> Threshold:
        """The threshold at `dotted_path`, **without** refusing an unverified one.

        For reports and the circular watcher, which need to say "this rule is still unknown,
        and here is why" rather than evaluate it.
        """
        return self._thresholds[dotted_path]

    # -- introspection --------------------------------------------------------

    @property
    def assumed(self) -> tuple[str, ...]:
        """Paths that load and work, but rest on an assumption rather than a citation."""
        return tuple(p for p, t in sorted(self._thresholds.items()) if t.assumed)

    def __contains__(self, dotted_path: object) -> bool:
        return dotted_path in self._thresholds

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self._thresholds))

    def __len__(self) -> int:
        return len(self._thresholds)

    def __repr__(self) -> str:
        return (
            f"<Rules {len(self._thresholds)} thresholds, "
            f"{len(self.assumed)} assumed, {len(self.unverified)} unverified, "
            f"from {self.path.name}>"
        )


# -- loading ------------------------------------------------------------------


def load_rules(path: str | Path | None = None, *, warn: bool = True) -> Rules:
    """Parse and validate the rules config.

    Raises `RuleConfigError` on anything that would let a threshold through without provenance.
    Emits one `UserWarning` naming every assumed threshold, unless `warn` is False.
    """
    path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not path.is_file():
        raise RuleConfigError(f"no rules config at {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RuleConfigError(f"{path} is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise RuleConfigError(f"{path}: top level must be a mapping, got {type(raw).__name__}")

    meta = raw.get(_META_KEY) or {}
    if not isinstance(meta, dict):
        raise RuleConfigError(f"{path}: `{_META_KEY}` must be a mapping")

    unverified = _read_unverified_list(meta, path)

    thresholds: dict[str, Threshold] = {}
    for top_key, subtree in raw.items():
        if top_key == _META_KEY:
            continue
        _walk(subtree, [top_key], unverified, thresholds)

    if not thresholds:
        raise RuleConfigError(f"{path}: no thresholds found outside `{_META_KEY}`")

    # The list and the tree must agree. A path listed as unverified that no longer exists means
    # the list is stale, and a stale list is how a rule quietly becomes evaluable again.
    missing = [p for p in unverified if p not in thresholds]
    if missing:
        raise RuleConfigError(
            f"{path}: {_META_KEY}.unverified names thresholds that do not exist: "
            f"{', '.join(missing)}. Either the path is misspelled or the threshold was renamed."
        )

    rules = Rules(thresholds, unverified, meta, path)

    if warn and rules.assumed:
        warnings.warn(
            f"{path.name}: {len(rules.assumed)} threshold(s) rest on an assumption, not a "
            f"citation: {', '.join(rules.assumed)}. They will be used as if verified.",
            UserWarning,
            stacklevel=2,
        )

    return rules


def _read_unverified_list(meta: Mapping[str, Any], path: Path) -> tuple[str, ...]:
    listed = meta.get("unverified") or []
    if not isinstance(listed, list) or not all(isinstance(p, str) for p in listed):
        raise RuleConfigError(f"{path}: {_META_KEY}.unverified must be a list of dotted paths")
    duplicates = {p for p in listed if listed.count(p) > 1}
    if duplicates:
        raise RuleConfigError(
            f"{path}: {_META_KEY}.unverified lists the same path twice: {', '.join(sorted(duplicates))}"
        )
    return tuple(listed)


def _walk(
    node: Any,
    trail: list[str],
    unverified: tuple[str, ...],
    out: dict[str, Threshold],
) -> None:
    """Recurse the tree, turning every threshold mapping into a `Threshold`."""
    dotted = ".".join(trail)

    if not isinstance(node, dict):
        # A bare `client_nri: 0.10` lands here. It is the commonest way to lose provenance,
        # because it looks completely reasonable and reads correctly to a human.
        raise RuleConfigError(
            f"{dotted}: expected a mapping, got {type(node).__name__} ({node!r}). "
            f"Every threshold needs value/source/verified as sibling keys, not a bare value."
        )

    if "value" in node:
        out[dotted] = _build_threshold(node, dotted, unverified)
        return

    if not node:
        raise RuleConfigError(f"{dotted}: empty block. Remove it or fill it in.")

    for key, child in node.items():
        _walk(child, trail + [str(key)], unverified, out)


def _build_threshold(
    node: Mapping[str, Any], dotted: str, unverified: tuple[str, ...]
) -> Threshold:
    keys = set(node)

    unknown = keys - _ALLOWED_KEYS
    if unknown:
        raise RuleConfigError(
            f"{dotted}: unknown key(s) {', '.join(sorted(unknown))}. "
            f"Allowed: {', '.join(sorted(_ALLOWED_KEYS))}. A misspelled key is silently ignored "
            f"by a plain YAML load, which is why this is an error."
        )

    missing = _REQUIRED_KEYS - keys
    if missing:
        raise RuleConfigError(
            f"{dotted}: missing {', '.join(sorted(missing))}. A threshold that cannot say where "
            f"it came from is not usable."
        )

    source = node["source"]
    if not isinstance(source, str) or not source.strip():
        raise RuleConfigError(f"{dotted}: `source` must be a non-empty string")

    operator_symbol = node.get("operator")
    if operator_symbol is not None:
        if not isinstance(operator_symbol, str) or operator_symbol not in _OPERATORS:
            raise RuleConfigError(
                f"{dotted}: operator {operator_symbol!r} is not one of "
                f"{', '.join(sorted(_OPERATORS))}. An operator embedded in the value, such as "
                f'">0.15", is a string and will never compare as a number.'
            )

    note = node.get("note") or ""
    if not isinstance(note, str):
        raise RuleConfigError(f"{dotted}: `note` must be a string")

    verified = node["verified"]
    is_listed_unverified = dotted in unverified
    assumed = False

    if verified is None:
        stated = source.strip().upper()
        if is_listed_unverified:
            if not stated.startswith(_UNVERIFIED_PREFIX):
                raise RuleConfigError(
                    f"{dotted}: listed in {_META_KEY}.unverified, so its `source` must begin "
                    f'with "{_UNVERIFIED_PREFIX}" and say what is missing. Got: {source!r}'
                )
            if node["value"] is not None:
                raise RuleConfigError(
                    f"{dotted}: listed in {_META_KEY}.unverified but carries a value "
                    f"({node['value']!r}). An unverified threshold must be null - a plausible "
                    f"number here is exactly the failure this config is built to prevent."
                )
        elif stated.startswith(_ASSUMPTION_PREFIX):
            assumed = True
        else:
            raise RuleConfigError(
                f"{dotted}: `verified` is null but the source is neither an "
                f'"{_ASSUMPTION_PREFIX}" nor listed in {_META_KEY}.unverified. '
                f"Give the date you read the paragraph, mark it as an assumption, or list it."
            )
    else:
        if not isinstance(verified, _dt.date) or isinstance(verified, _dt.datetime):
            raise RuleConfigError(
                f"{dotted}: `verified` must be a plain YYYY-MM-DD date, got {verified!r}. "
                f"Quoting it makes it a string, which cannot be compared against a circular's date."
            )
        if is_listed_unverified:
            raise RuleConfigError(
                f"{dotted}: carries verified: {verified} but is still listed in "
                f"{_META_KEY}.unverified. Remove it from the list."
            )

    return Threshold(
        path=dotted,
        value=node["value"],
        source=source,
        verified=verified,
        operator=operator_symbol,
        note=note,
        assumed=assumed,
    )
