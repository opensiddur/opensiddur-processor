"""Pair a leaf's Hebrew segments with its English ones.

In the Metsudah linear volumes Hebrew segment *n* is translated by English segment *n*, and an
English rubric stands opposite an empty Hebrew segment. Where the two versions have the same
number of segments, that is the alignment. Where they do not, it is decided:

- **Trailing extras.** When the longer version's extra segments all come at the end of the
  leaf -- English rubrics after the last Hebrew ("Mourner's Kaddish is said here:"), or Hebrew
  the English leaves untranslated -- they stand alone and the rest pair one to one. This is
  accepted without a decision when every extra English segment is a rubric (printed whole in
  small or italic), or when there are at most :data:`MAX_UNTRANSLATED` extra Hebrew segments,
  and reported for review.
- **A recorded decision** (``alignment_decisions.yaml``) names, by 1-based index, the Hebrew
  segments with no English (``he_only``) and the English with no Hebrew (``en_only``); the rest
  pair in order. A decision records the hashes of the leaf it was made for (``as_of``) and
  lapses when either version of the leaf changes: it is then an error until decided again.
  It may also name the Hebrew segments that open a new text (``opens``): untranslated texts
  the book prints after a translated one, with no bold opening to mark where each begins.

Any other mismatch is an error that names the leaf, for a decision to be recorded.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import yaml

from opensiddur.importer.sefaria.markup import (
    EnglishKind,
    HebrewKind,
    Node,
    english_kind,
    hebrew_kind,
    parse_segment,
)
from opensiddur.importer.sefaria.source import Leaf, segments_hash

DECISIONS_FILE = Path(__file__).with_name("alignment_decisions.yaml")
#: The most Hebrew segments the trailing rule leaves untranslated without a decision. Unlike an
#: English rubric, untranslated Hebrew looks like any other Hebrew, so a version that dropped one
#: English segment mid-leaf would pass as a trailing run if the run could be long.
MAX_UNTRANSLATED = 3


class AlignmentError(ValueError):
    pass


@dataclass(frozen=True)
class Pair:
    """A Hebrew segment and its English, either possibly absent. Indexes are 1-based."""

    he_index: int | None
    en_index: int | None
    he: tuple[Node, ...]
    en: tuple[Node, ...]

    @cached_property
    def he_kind(self) -> HebrewKind:
        return hebrew_kind(self.he)

    @cached_property
    def en_kind(self) -> EnglishKind:
        return english_kind(self.en)


@dataclass(frozen=True)
class LeafDecision:
    he_hash: str
    en_hash: str
    he_only: frozenset[int]
    en_only: frozenset[int]
    note: str = ""
    #: Hebrew segments that open a new text although nothing in the markup says so
    opens: frozenset[int] = frozenset()


def load_decisions(path: Path = DECISIONS_FILE) -> dict[str, dict[str, LeafDecision]]:
    """``{work: {leaf path: decision}}``."""
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    decisions: dict[str, dict[str, LeafDecision]] = {}
    for work, leaves in data.items():
        for leaf_path, entry in (leaves or {}).items():
            as_of = entry.get("as_of") or {}
            decisions.setdefault(work, {})[leaf_path] = LeafDecision(
                he_hash=as_of.get("he", ""),
                en_hash=as_of.get("en", ""),
                he_only=frozenset(entry.get("he_only") or ()),
                en_only=frozenset(entry.get("en_only") or ()),
                note=entry.get("note", ""),
                opens=frozenset(entry.get("opens") or ()),
            )
    return decisions


@dataclass(frozen=True)
class Alignment:
    leaf: Leaf
    pairs: tuple[Pair, ...]
    #: how it was decided: "equal", "trailing" or "decision"
    policy: str
    #: Hebrew segments a decision says open a new text
    opens: frozenset[int] = frozenset()


def _merge(leaf: Leaf, he_only: frozenset[int], en_only: frozenset[int]) -> Iterator[Pair]:
    he_count, en_count = len(leaf.he), len(leaf.en)
    for index in he_only:
        if not 1 <= index <= he_count:
            raise AlignmentError(f"{leaf.path}: he_only names segment {index} of {he_count}")
    for index in en_only:
        if not 1 <= index <= en_count:
            raise AlignmentError(f"{leaf.path}: en_only names segment {index} of {en_count}")
    if he_count - len(he_only) != en_count - len(en_only):
        raise AlignmentError(
            f"{leaf.path}: after setting aside {len(he_only)} Hebrew and {len(en_only)} English "
            f"segment(s), {he_count - len(he_only)} Hebrew and {en_count - len(en_only)} English "
            "remain to pair")
    h = e = 1
    while h <= he_count or e <= en_count:
        if h <= he_count and h in he_only:
            yield Pair(h, None, parse_segment(leaf.he[h - 1]), ())
            h += 1
        elif e <= en_count and e in en_only:
            yield Pair(None, e, (), parse_segment(leaf.en[e - 1]))
            e += 1
        else:
            yield Pair(h, e, parse_segment(leaf.he[h - 1]), parse_segment(leaf.en[e - 1]))
            h += 1
            e += 1


def _trailing(leaf: Leaf) -> tuple[frozenset[int], frozenset[int]] | None:
    """The trailing extras, when they are of a kind that can stand alone without review."""
    he_count, en_count = len(leaf.he), len(leaf.en)
    if en_count > he_count:
        extras = range(he_count + 1, en_count + 1)
        if all(english_kind(parse_segment(leaf.en[i - 1])) is EnglishKind.RUBRIC for i in extras):
            return frozenset(), frozenset(extras)
    elif 0 < he_count - en_count <= MAX_UNTRANSLATED:
        extras = range(en_count + 1, he_count + 1)
        if all(hebrew_kind(parse_segment(leaf.he[i - 1])) is not HebrewKind.EMPTY for i in extras):
            return frozenset(extras), frozenset()
    return None


def align_leaf(leaf: Leaf, decision: LeafDecision | None = None) -> Alignment:
    if decision is not None:
        if (decision.he_hash, decision.en_hash) != (segments_hash(leaf.he), segments_hash(leaf.en)):
            raise AlignmentError(
                f"{leaf.path}: the alignment decision was made for an earlier version of this leaf; "
                "review it and record its new as_of hashes")
        for index in decision.opens:
            if not 1 <= index <= len(leaf.he):
                raise AlignmentError(f"{leaf.path}: opens names segment {index} of {len(leaf.he)}")
        return Alignment(leaf, tuple(_merge(leaf, decision.he_only, decision.en_only)), "decision",
                         decision.opens)
    if len(leaf.he) == len(leaf.en):
        return Alignment(leaf, tuple(_merge(leaf, frozenset(), frozenset())), "equal")
    trailing = _trailing(leaf)
    if trailing is None:
        raise AlignmentError(
            f"{leaf.path}: {len(leaf.he)} Hebrew and {len(leaf.en)} English segments, and the "
            "difference is not a run of trailing rubrics or untranslated Hebrew; record a decision "
            f"in {DECISIONS_FILE.name}")
    return Alignment(leaf, tuple(_merge(leaf, *trailing)), "trailing")


def align_work(work_key: str, leaves: tuple[Leaf, ...],
               decisions: dict[str, dict[str, LeafDecision]] | None = None) -> list[Alignment]:
    """Every leaf's alignment; all the leaves that cannot be aligned are reported together."""
    work_decisions = (decisions or {}).get(work_key, {})
    alignments: list[Alignment] = []
    errors: list[str] = []
    for leaf in leaves:
        try:
            alignments.append(align_leaf(leaf, work_decisions.get(leaf.path)))
        except AlignmentError as exc:
            errors.append(str(exc))
    unknown = set(work_decisions) - {leaf.path for leaf in leaves}
    errors.extend(f"{path}: a decision for a leaf the work no longer has" for path in sorted(unknown))
    if errors:
        raise AlignmentError("\n".join(errors))
    return alignments
