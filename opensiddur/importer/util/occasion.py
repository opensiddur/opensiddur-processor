"""Occasion conditions for a book's running order.

A section said only on some days -- the weekday services, the Sabbath services, Hallel, the
festival services -- is conditioned where its running order transcludes it: the outermost point
at which the condition can be stated, so that one condition governs the whole section. Such a
condition is a direction to the processor, not to the reader, so it carries no instruction and
is not ``type="marked"``: an edition that cannot decide it prints the section with nothing around
it (``schema/JLPTEI-3.md``, *Conditions on a running order*).

Conditions are written here as data -- :class:`Feature` literals combined with :func:`all_of`,
:func:`any_of` and :func:`none_of` -- so that the same data renders the markup and says which
features a condition fixes to one value. Those are declared inside the conditional, so that
the section's own conditions on them are decided even where the date is not.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

HOLIDAY = "opensiddur:holiday"
AGGREGATE = "opensiddur:holiday-aggregate"
SERVICE_TIME = "opensiddur:service-time"
HEBREW_DATE = "opensiddur:hebrew-date"
DAY_OF_WEEK = "opensiddur:day-of-week"
ISRAEL = "opensiddur:israel"
#: Matter of the book's that is neither prayer nor commentary on it. Not an occasion, but gated
#: the same way: a direction to the processor, with nothing said to the reader
#: (``schema/JLPTEI-3.md``, *Setting attribute values*).
PARATEXT = "opensiddur:paratext"

#: The feature structures a gate may declare. The others are what the calendar derives *from* --
#: a date, a place, a day of the week -- and declaring part of one would recompute everything
#: downstream of it from a date with a piece missing.
DECLARABLE = frozenset({HOLIDAY, AGGREGATE, SERVICE_TIME})


@dataclass(frozen=True)
class Feature:
    """One feature compared with one value: a binary, a number, or a range of numbers."""

    fs: str
    name: str
    value: bool | int = True
    max: int | None = None

    def f_markup(self) -> str:
        if isinstance(self.value, bool):
            value = f'<tei:binary value="{str(self.value).lower()}"/>'
        elif self.max is not None:
            value = f'<tei:numeric value="{self.value}" max="{self.max}"/>'
        else:
            value = f'<tei:numeric value="{self.value}"/>'
        return f'<tei:f name="{self.name}">{value}</tei:f>'

    def markup(self) -> str:
        return f'<tei:fs type="{self.fs}">{self.f_markup()}</tei:fs>'

    @property
    def single(self) -> bool:
        """Whether the comparison names exactly one value."""
        return self.max is None or self.max == self.value


@dataclass(frozen=True)
class Combination:
    op: Literal["all", "any", "none"]
    args: tuple[Condition, ...]

    def markup(self) -> str:
        return f"<j:{self.op}>" + "".join(arg.markup() for arg in self.args) + f"</j:{self.op}>"


Condition = Feature | Combination


def all_of(*args: Condition) -> Combination:
    return Combination("all", args)


def any_of(*args: Condition) -> Combination:
    return Combination("any", args)


def none_of(*args: Condition) -> Combination:
    return Combination("none", args)


def holiday(name: str, first: int = 1, last: int | None = None) -> Feature:
    """A holiday on day ``first`` (through ``last``, if given) of it."""
    return Feature(HOLIDAY, name, first, last)


def aggregate(name: str, value: bool = True) -> Feature:
    return Feature(AGGREGATE, name, value)


def service(name: str) -> Feature:
    return Feature(SERVICE_TIME, name)


def paratext() -> Feature:
    """A preface, dedication, introduction, epilogue or other prose that is not liturgy."""
    return Feature(PARATEXT, "include")


def title_page() -> Feature:
    """A transcribed title leaf, its copyright verso included."""
    return Feature(PARATEXT, "title-page")


def fixed(condition: Condition) -> list[Feature]:
    """The features ``condition`` fixes to one value wherever it holds, as declarable values.

    A comparison with one value fixes it; ``all`` fixes whatever any of its parts fix; ``none``
    of a binary fixes it to the other value; and ``any`` of one alternative is that alternative.
    Only the structures in :data:`DECLARABLE` are returned.
    """
    found: list[Feature] = []
    if isinstance(condition, Feature):
        if condition.single:
            found.append(Feature(condition.fs, condition.name, condition.value))
    elif condition.op == "all" or (condition.op == "any" and len(condition.args) == 1):
        for arg in condition.args:
            found.extend(fixed(arg))
    elif condition.op == "none":
        found.extend(Feature(arg.fs, arg.name, not arg.value) for arg in condition.args
                     if isinstance(arg, Feature) and isinstance(arg.value, bool))
    unique: dict[tuple[str, str], Feature] = {}
    for feature in found:
        if feature.fs in DECLARABLE:
            unique.setdefault((feature.fs, feature.name), feature)
    return list(unique.values())


def declaration(xml_id: str, features: list[Feature]) -> str:
    """A ``j:declare`` of ``features``, grouped by feature structure."""
    by_fs: dict[str, list[Feature]] = {}
    for feature in features:
        by_fs.setdefault(feature.fs, []).append(feature)
    structures = "".join(
        f'<tei:fs type="{fs}">' + "".join(f.f_markup() for f in group) + "</tei:fs>"
        for fs, group in by_fs.items())
    return f'<j:declare xml:id="{xml_id}">{structures}</j:declare>'


def gate(xml_id: str, condition: Condition) -> tuple[str, str]:
    """The markup that opens and closes an occasion's gate around a running order's entries.

    The opening is a ``j:conditional`` with no instruction, followed by a ``j:declare`` of what
    the condition fixes, if anything; the closing ends both.
    """
    opening = f'<j:conditional xml:id="{xml_id}">{condition.markup()}</j:conditional>'
    closing = f'<j:endConditional target="#{xml_id}"/>'
    features = fixed(condition)
    if features:
        declare_id = f"{xml_id}_declare"
        opening += declaration(declare_id, features)
        closing = f'<j:endDeclare target="#{declare_id}"/>' + closing
    return opening, closing


def gated(xml_id: str, condition: Condition | None, content: str) -> str:
    """``content`` inside an occasion's gate, or as it is if ``condition`` is None."""
    if condition is None:
        return content
    opening, closing = gate(xml_id, condition)
    return opening + content + closing
