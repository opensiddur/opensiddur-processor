"""The settings registry: which `opensiddur:*` features exist and what values they take.

The registry itself is ``features.yaml``, beside this module, which says what each entry
means. This module reads it and checks a setting against it, in the three places a setting
is written or tested: a settings file's ``declarations``, a ``j:declare``, and a
``j:conditional`` or ``j:condition``. A misspelt feature name is not an error anywhere else
— it is a feature nobody sets, so a condition on it is quietly undecided — which is how a
text could be dropped for a feature the calendar computes under another name.

Only the ``opensiddur:`` namespace is checked. A feature structure type in any other
namespace belongs to whoever named it.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from lxml.etree import ElementBase

from opensiddur.exporter.constants import TEI_NS
from opensiddur.exporter.linear import Undefined, parse_numeric_literal

REGISTRY_FILE = Path(__file__).parent / "features.yaml"

#: The namespace the registry governs.
NAMESPACE = "opensiddur:"

KINDS = ("binary", "numeric", "symbol", "string")
SUPPLIERS = ("input", "derived", "declared")

_TEI_F = f"{{{TEI_NS}}}f"
_TEI_NUMERIC = f"{{{TEI_NS}}}numeric"
_TEI_BINARY = f"{{{TEI_NS}}}binary"
_TEI_STRING = f"{{{TEI_NS}}}string"
_TEI_SYMBOL = f"{{{TEI_NS}}}symbol"
_TEI_DEFAULT = f"{{{TEI_NS}}}default"
_TEI_VALT = f"{{{TEI_NS}}}vAlt"
_TEI_VNOT = f"{{{TEI_NS}}}vNot"

_ELEMENT_KINDS = {
    _TEI_BINARY: "binary",
    _TEI_NUMERIC: "numeric",
    _TEI_SYMBOL: "symbol",
    _TEI_STRING: "string",
}


@dataclass(frozen=True)
class ValueKind:
    """The kind of value a feature takes, and the constraints on it."""

    kind: str
    minimum: float | None = None
    maximum: float | None = None
    integer: bool = True
    values: frozenset[str] | None = None
    pattern: re.Pattern | None = None

    def describe(self) -> str:
        if self.kind == "numeric":
            low = "" if self.minimum is None else _format_number(self.minimum)
            high = "" if self.maximum is None else _format_number(self.maximum)
            bounds = f" {low}..{high}" if low or high else ""
            return ("an integer" if self.integer else "a number") + bounds
        if self.kind == "symbol" and self.values:
            return "a symbol, one of " + ", ".join(sorted(self.values))
        if self.kind == "string" and self.pattern is not None:
            return f"a string matching {self.pattern.pattern}"
        return {"binary": "binary", "symbol": "a symbol", "string": "a string"}[self.kind]

    def number_problem(self, number: float) -> str | None:
        """Why ``number`` is not a value of this numeric kind, or None if it is."""
        if not math.isfinite(number):
            return f"{number} is not a finite number"
        if self.integer and number != int(number):
            return f"{_format_number(number)} is not an integer"
        if self.minimum is not None and number < self.minimum:
            return f"{_format_number(number)} is below {_format_number(self.minimum)}"
        if self.maximum is not None and number > self.maximum:
            return f"{_format_number(number)} is above {_format_number(self.maximum)}"
        return None


@dataclass(frozen=True)
class FeatureType:
    """One registered feature structure type."""

    name: str
    common: bool
    supplied: str
    features: dict[str, ValueKind]
    open_name: re.Pattern | None = None
    open_value: ValueKind | None = None

    def feature(self, name: str) -> ValueKind | None:
        if name in self.features:
            return self.features[name]
        if self.open_name is not None and self.open_name.fullmatch(name):
            return self.open_value
        return None


def _format_number(number: float) -> str:
    return str(int(number)) if number == int(number) else str(number)


def _value_kind(spec: Any, where: str) -> ValueKind:
    """A value kind from its YAML form: ``binary``, or ``{kind: {constraints}}``."""
    if spec == "binary":
        return ValueKind("binary")
    if not isinstance(spec, dict) or len(spec) != 1:
        raise ValueError(f"{where}: a value kind is `binary` or a one-key mapping, not {spec!r}")
    (kind, constraints), = spec.items()
    constraints = constraints or {}
    allowed = {"numeric": {"min", "max", "integer"}, "symbol": {"values"},
               "string": {"pattern"}}.get(kind)
    if allowed is None:
        raise ValueError(f"{where}: unknown value kind {kind!r}; known: {', '.join(KINDS)}")
    unknown = set(constraints) - allowed
    if unknown:
        raise ValueError(f"{where}: {kind} takes no {', '.join(sorted(unknown))}")
    if kind == "numeric":
        return ValueKind("numeric", minimum=constraints.get("min"),
                         maximum=constraints.get("max"),
                         integer=constraints.get("integer", True))
    if kind == "symbol":
        values = constraints.get("values")
        return ValueKind("symbol", values=frozenset(values) if values else None)
    pattern = constraints.get("pattern")
    return ValueKind("string", pattern=re.compile(pattern) if pattern else None)


def _feature_type(name: str, spec: dict[str, Any]) -> FeatureType:
    unknown = set(spec) - {"common", "supplied", "features", "open"}
    if unknown:
        raise ValueError(f"{name}: unknown keys {', '.join(sorted(unknown))}")
    if not name.startswith(NAMESPACE):
        raise ValueError(f"{name}: a registered type is in the {NAMESPACE} namespace")
    if not isinstance(spec.get("common"), bool):
        raise ValueError(f"{name}: `common` is true or false")
    if spec.get("supplied") not in SUPPLIERS:
        raise ValueError(f"{name}: `supplied` is one of {', '.join(SUPPLIERS)}")
    features = {
        feature: _value_kind(kind, f"{name}/{feature}")
        for feature, kind in (spec.get("features") or {}).items()
    }
    open_spec = spec.get("open")
    if open_spec is not None and (not isinstance(open_spec, dict)
                                  or set(open_spec) != {"name", "value"}):
        raise ValueError(f"{name}: `open` has a `name` pattern and a `value` kind, and nothing else")
    if open_spec is None and not features:
        raise ValueError(f"{name}: lists no features and is not open")
    return FeatureType(
        name=name,
        common=spec["common"],
        supplied=spec["supplied"],
        features=features,
        open_name=re.compile(open_spec["name"]) if open_spec else None,
        open_value=_value_kind(open_spec["value"], f"{name} (open)") if open_spec else None,
    )


@cache
def load_registry(path: Path = REGISTRY_FILE) -> dict[str, FeatureType]:
    """Every registered type, by name."""
    with open(path, encoding="utf-8") as registry_file:
        data = yaml.safe_load(registry_file) or {}
    return {name: _feature_type(name, spec) for name, spec in data.items()}


def is_governed(fs_type: str) -> bool:
    """Whether the registry speaks for this type: whether it is in its namespace."""
    return fs_type.startswith(NAMESPACE)


def _lookup(fs_type: str, feature: str,
            registry: dict[str, FeatureType]) -> tuple[ValueKind | None, str | None]:
    """A feature's kind, or why there is none."""
    registered = registry.get(fs_type)
    if registered is None:
        return None, f"{fs_type} is not a registered settings type"
    kind = registered.feature(feature)
    if kind is None:
        return None, f"{fs_type} has no feature {feature!r}"
    return kind, None


# ── Values as YAML gives them ────────────────────────────────────────────────


def check_yaml_value(fs_type: str, feature: str, value: Any,
                     registry: dict[str, FeatureType] | None = None) -> list[str]:
    """What is wrong with declaring ``value`` for a feature in a settings file, if anything."""
    if not is_governed(fs_type):
        return []
    kind, problem = _lookup(fs_type, feature,
                            load_registry() if registry is None else registry)
    if problem:
        return [problem]
    if value is None or value is Undefined:
        return []  # undefined is a value of every feature
    where = f"{fs_type}/{feature}"
    if kind.kind == "binary":
        return [] if isinstance(value, bool) else [
            f"{where} is binary (true or false), not {value!r}"]
    if kind.kind == "numeric":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return [f"{where} is {kind.describe()}, not {value!r}"]
        problem = kind.number_problem(value)
        return [f"{where}: {problem}"] if problem else []
    if not isinstance(value, str):
        return [f"{where} is {kind.describe()}, not {value!r}"]
    return _text_problems(where, kind, value)


def _text_problems(where: str, kind: ValueKind, text: str) -> list[str]:
    if kind.values is not None and text not in kind.values:
        return [f"{where} is {kind.describe()}, not {text!r}"]
    if kind.pattern is not None and not kind.pattern.fullmatch(text):
        return [f"{where} is {kind.describe()}, not {text!r}"]
    return []


# ── Values as JLPTEI gives them ──────────────────────────────────────────────


def check_fs_element(fs_element: ElementBase, *, in_condition: bool,
                     registry: dict[str, FeatureType] | None = None) -> list[str]:
    """What is wrong with a declared or tested ``tei:fs``, if anything.

    Only the registry's own questions: the type, the feature names and the kinds of their
    values. Whether the structure is well formed is the parser's business.
    """
    fs_type = fs_element.get("type") or ""
    if not is_governed(fs_type):
        return []
    if registry is None:
        registry = load_registry()
    if fs_type not in registry:
        return [f"{fs_type} is not a registered settings type"]
    problems: list[str] = []
    for f_element in fs_element:
        if f_element.tag != _TEI_F:
            continue
        feature = f_element.get("name") or ""
        kind, problem = _lookup(fs_type, feature, registry)
        if problem:
            problems.append(problem)
            continue
        for value in f_element.iter(*_ELEMENT_KINDS):
            problems.extend(_element_problems(
                f"{fs_type}/{feature}", kind, value, in_condition=in_condition))
    return problems


def _element_problems(where: str, kind: ValueKind, value: ElementBase, *,
                      in_condition: bool) -> list[str]:
    given = _ELEMENT_KINDS[value.tag]
    if given == "symbol" and value.get("value") == "undefined":
        return []
    if given == "binary" and kind.kind == "numeric" and in_condition:
        # A condition may ask whether a number is true: zero or not.
        return []
    if given != kind.kind:
        return [f"{where} is {kind.describe()}, not tei:{given}"]
    if given == "numeric":
        problems = []
        for attribute in ("value", "max"):
            raw = value.get(attribute)
            if raw is None:
                continue
            try:
                number = parse_numeric_literal(raw)
            except ValueError:
                continue  # a malformed number is the parser's to report
            problem = kind.number_problem(number)
            if problem:
                problems.append(f"{where}: @{attribute} {problem}")
        return problems
    if given == "symbol":
        return _text_problems(where, kind, value.get("value") or "")
    if given == "string":
        return _text_problems(where, kind, value.text or "")
    return []


def require_valid_fs(fs_element: ElementBase, *, in_condition: bool) -> None:
    """Raise if a declared or tested ``tei:fs`` breaks the registry."""
    problems = check_fs_element(fs_element, in_condition=in_condition)
    if problems:
        where = fs_element.base or "a setting"
        if fs_element.sourceline:
            where += f":{fs_element.sourceline}"
        raise ValueError(f"{where}: " + "; ".join(problems))
