"""Calendar (and other) conditions the book prints: its condition rubrics, labels and marked
alternatives, as ``j:conditional``.

``conditions.yaml`` holds the curated table:

- ``rubrics``: an English rubric that says *when* the passage after it is said ("During the Ten
  Days of Penitence add:", "From the Musaf of Shemini Atzeres until the Musaf of the first day of
  Pesach you should say:", "On Sunday:"), found by a regular expression. Such a rubric becomes the
  conditional's note (``descriptive-vs-conditional`` rubrics: a condition, dropped once true).
- ``labels``: a Hebrew label set before a phrase (``<small>לְר"ח:</small> רֹאשׁ הַחֹדֶשׁ הַזֶּה``):
  the phrase is conditional, the label its note.
- ``inline``: an abbreviation that opens a parenthesized alternative inside a phrase
  (``(בעשי"ת הַשָּׁלוֹם)``): the alternative is a marked conditional, the abbreviation its note.
- ``replacements``: an inline alternative that replaces words beside it rather than adding to
  them (``(בעשי"ת הַשָּׁלוֹם) שָׁלוֹם``): those words are conditional on the condition being false.
  The words may open the next phrase (``(בעשי"ת וּלְעֵֽלָּא מִכָּל)`` | ``מִן כָּל``).
- ``directives``: rubrics that read like conditions but are reviewed and are not -- a stage
  direction ("When the Holy Ark is opened"), or where to turn ("On regular weekdays continue,
  ...") -- so that the report does not list them again.
- ``leaves``: a work's leaf said only on some days, though the book prints no rubric before it
  (it says so at the end of the leaf before: "On days when the Torah is not read continue with
  Ashrei"): its transclusion is gated.

A rubric entry may say how far it governs: by default the next text (between texts) or the
passage to the next rubric (inside one); with ``section: true``, everything to the next heading,
or, with ``until``, to the rubric that matches it. With ``instead_of_previous: true`` (between
texts), the text before the rubric is what is said otherwise, and is conditional on the opposite.
Inside a text, ``through`` (Hebrew words) ends the passage with the phrase that ends with them.

A condition (``when``) is written in a small grammar: a mapping of feature structure type to
features (the types and features of ``opensiddur/exporter/features.yaml``, without the
``opensiddur:`` prefix), every one of which must hold; or ``any``/``all``/``none`` of a list of
conditions. A feature's value is ``true``/``false`` (binary), a number, ``[min, max]`` (a numeric
range), or a string (a symbol).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from opensiddur.importer.util.incipit import words

CONDITIONS_FILE = Path(__file__).with_name("conditions.yaml")
FEATURE_PREFIX = "opensiddur:"


class ConditionsError(ValueError):
    pass


def _attr(text: str) -> str:
    return (text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;"))


def _value_xml(value: Any, where: str) -> str:
    if isinstance(value, bool):
        return f'<tei:binary value="{"true" if value else "false"}"/>'
    if isinstance(value, int):
        return f'<tei:numeric value="{value}"/>'
    if isinstance(value, list) and len(value) == 2 and all(isinstance(v, int) for v in value):
        return f'<tei:numeric value="{value[0]}" max="{value[1]}"/>'
    if isinstance(value, str):
        return f'<tei:symbol value="{_attr(value)}"/>'
    raise ConditionsError(f"{where}: {value!r} is not a feature value")


def condition_xml(when: Any, where: str = "condition") -> str:
    """A condition in the grammar above, as the content of a ``j:conditional``."""
    if not isinstance(when, dict) or not when:
        raise ConditionsError(f"{where}: a condition is a non-empty mapping")
    parts: list[str] = []
    for key, value in when.items():
        if key in ("any", "all", "none"):
            if not isinstance(value, list) or not value:
                raise ConditionsError(f"{where}: {key} takes a list of conditions")
            inner = "".join(condition_xml(v, where) for v in value)
            parts.append(f"<j:{key}>{inner}</j:{key}>")
        else:
            if not isinstance(value, dict) or not value:
                raise ConditionsError(f"{where}: {key} takes a mapping of features")
            features = "".join(f'<tei:f name="{_attr(name)}">{_value_xml(v, where)}</tei:f>'
                               for name, v in value.items())
            parts.append(f'<tei:fs type="{FEATURE_PREFIX}{_attr(key)}">{features}</tei:fs>')
    return parts[0] if len(parts) == 1 else f"<j:all>{''.join(parts)}</j:all>"


def negated_xml(when: Any, where: str = "condition") -> str:
    return f"<j:none>{condition_xml(when, where)}</j:none>"


@dataclass(frozen=True)
class RubricCondition:
    pattern: re.Pattern[str]
    when: Any
    #: the rubric governs the section after it, to the next heading, not only the next text
    section: bool = False
    #: a section ends before a rubric this matches
    until: re.Pattern[str] | None = None
    #: the text before the rubric is what is said otherwise ("A woman says:"): it is conditional
    #: on the opposite
    instead_of_previous: bool = False
    #: inside a text, the passage ends with the phrase whose words end so (``through``)
    through: tuple[str, ...] = ()
    #: the rubric ``until`` matches is the section's last, inside its gate (each day's psalm
    #: ends "(Deliver us...; Mourner's Kaddish.)"), not the first words after it
    until_included: bool = False


@dataclass(frozen=True)
class LeafGate:
    work: str
    leaf: str
    when: Any
    #: the conditional's English note, if any
    note: str = ""


@dataclass(frozen=True)
class LabelCondition:
    label: tuple[str, ...]
    when: Any


@dataclass(frozen=True)
class Replacement:
    alternative: tuple[str, ...]
    replaces: tuple[str, ...]


@dataclass(frozen=True)
class Conditions:
    rubrics: tuple[RubricCondition, ...] = ()
    labels: tuple[LabelCondition, ...] = ()
    inline: tuple[LabelCondition, ...] = ()
    replacements: tuple[Replacement, ...] = ()
    directives: tuple[re.Pattern[str], ...] = ()
    leaves: tuple[LeafGate, ...] = ()

    def is_directive(self, english: str) -> bool:
        text = " ".join(english.split())
        return any(p.search(text) for p in self.directives)

    def leaf_gate(self, work: str, leaf: str) -> LeafGate | None:
        return next((g for g in self.leaves if g.work == work and g.leaf == leaf), None)

    def for_rubric(self, english: str) -> RubricCondition | None:
        text = " ".join(english.split())
        return next((r for r in self.rubrics if r.pattern.search(text)), None)

    def for_label(self, hebrew: str) -> LabelCondition | None:
        found = tuple(words(hebrew.rstrip(": ")))
        return next((c for c in self.labels if c.label == found), None)

    def for_inline(self, hebrew: str) -> LabelCondition | None:
        found = tuple(words(hebrew))
        return next((c for c in self.inline if found[:len(c.label)] == c.label), None)

    def replaced(self, alternative: str) -> Replacement | None:
        found = tuple(words(alternative))
        return next((r for r in self.replacements if r.alternative == found), None)


def load_conditions(path: Path = CONDITIONS_FILE) -> Conditions:
    if not path.exists():
        return Conditions()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rubrics = []
    for n, entry in enumerate(data.get("rubrics") or (), start=1):
        where = f"{path.name} rubrics #{n}"
        try:
            pattern = re.compile(entry["match"])
        except (KeyError, re.error) as exc:
            raise ConditionsError(f"{where}: a regular expression is needed in match ({exc})") from exc
        condition_xml(entry.get("when"), where)
        until = _pattern(entry["until"], where) if entry.get("until") else None
        section = bool(entry.get("section")) or until is not None
        rubrics.append(RubricCondition(pattern, entry["when"], section, until,
                                       bool(entry.get("instead_of_previous")),
                                       tuple(words(str(entry.get("through") or ""))),
                                       bool(entry.get("until_included"))))
    labels, inline = [], []
    for kind, found in (("labels", labels), ("inline", inline)):
        for n, entry in enumerate(data.get(kind) or (), start=1):
            where = f"{path.name} {kind} #{n}"
            label = tuple(words(str(entry.get("label", "")).rstrip(": ")))
            if not label:
                raise ConditionsError(f"{where}: a label is needed")
            condition_xml(entry.get("when"), where)
            found.append(LabelCondition(label, entry["when"]))
    replacements = [Replacement(tuple(words(str(e["alternative"]))), tuple(words(str(e["replaces"]))))
                    for e in data.get("replacements") or ()]
    directives = tuple(_pattern(m, f"{path.name} directives #{n}")
                       for n, m in enumerate(data.get("directives") or (), start=1))
    leaves = []
    for n, entry in enumerate(data.get("leaves") or (), start=1):
        where = f"{path.name} leaves #{n}"
        if not entry.get("work") or not entry.get("leaf"):
            raise ConditionsError(f"{where}: a work and a leaf are needed")
        condition_xml(entry.get("when"), where)
        leaves.append(LeafGate(str(entry["work"]), str(entry["leaf"]), entry["when"], str(entry.get("note") or "")))
    return Conditions(tuple(rubrics), tuple(labels), tuple(inline), tuple(replacements), directives,
                      tuple(leaves))


def _pattern(text: Any, where: str) -> re.Pattern[str]:
    try:
        return re.compile(str(text))
    except re.error as exc:
        raise ConditionsError(f"{where}: {text!r} is not a regular expression ({exc})") from exc
