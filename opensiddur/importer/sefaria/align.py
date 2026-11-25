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

import dataclasses
import re
from collections.abc import Callable, Collection, Iterator
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

import yaml

from opensiddur.importer.sefaria.markup import (
    EnglishKind,
    HebrewKind,
    Break,
    Node,
    Styled,
    Text,
    english_kind,
    hebrew_kind,
    is_pointed,
    leading_label,
    parse_segment,
    plain_text,
    split_leading,
)
from opensiddur.importer.sefaria.source import PATH_SEPARATOR, Leaf, segments_hash
from opensiddur.importer.util.incipit import words

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
    #: a label set apart from the head of its paragraph (split_leading_labels): it governs the
    #: rest of that paragraph, not the passage
    paragraph_label: bool = False
    #: a blessing's ending that another, after a label, replaces (``Conditions`` ``ending``):
    #: the condition under which it is *not* said
    otherwise: Any = None

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


def _label_at(nodes: tuple[Node, ...], position: int, is_label: Callable[[str], bool]) -> bool:
    node = nodes[position]
    return (isinstance(node, Styled) and node.style == "small"
            and not is_pointed(plain_text(node.children)) and is_label(plain_text(node.children))
            and is_pointed(plain_text(nodes[position + 1:])))


def _mid_label(nodes: tuple[Node, ...], is_label: Callable[[str], bool], *, at_start: bool = False) -> int | None:
    """Where a known condition label stands inside a paragraph's words (``מַשִּׁיב הָרֽוּחַ
    וּמוֹרִיד הַגֶּֽשֶׁם: <small>בקיץ:</small> מוֹרִיד הַטָּל``), after words of its own -- or,
    ``at_start``, after nothing but space."""
    for position in range(len(nodes)):
        before = plain_text(nodes[:position])
        if _label_at(nodes, position, is_label) and (
                is_pointed(before) or (at_start and not before.strip())):
            return position
    return None


def _through_colon(nodes: tuple[Node, ...]) -> tuple[tuple[Node, ...], tuple[Node, ...]]:
    """The words up to and with the first sof pasuq (a colon), and the rest."""
    for position, node in enumerate(nodes):
        text = node.text if isinstance(node, Text) else (
            plain_text(node.children) if isinstance(node, Styled) else "")
        if ":" not in text:
            continue
        if not isinstance(node, Text):
            return nodes[:position + 1], nodes[position + 1:]
        at = text.index(":") + 1
        head, tail = Text(text[:at]), Text(text[at:])
        return nodes[:position] + (head,), ((tail,) if tail.text.strip() else ()) + nodes[position + 1:]
    return nodes, ()


def _instruction_break(nodes: tuple[Node, ...]) -> tuple[int, int] | None:
    """Where an English paragraph goes on with an instruction of its own, after words of its own
    (``... the Holy One. <i>During the Ten Days of Penitence:</i> Blessed are You``), on a new
    line or not: the end of the words before it, and where it begins."""
    for position in range(1, len(nodes)):
        node = nodes[position]
        if (isinstance(node, Styled) and node.style == "italic"
                and plain_text(node.children).rstrip().endswith(":")):
            broken = isinstance(nodes[position - 1], Break)
            end = position - 1 if broken else position
            # (not a name in roman type inside an instruction: <i>From the Musaf of </i>Shemini
            # Atzeres<i> until ... you should say:</i>)
            if plain_text(nodes[:end]).strip() and (
                    broken or plain_text(nodes[:end]).rstrip().endswith((".", ";", ")", "!", "?", "”"))):
                return end, position
    return None


def _alternatives(he_index: int | None, en_index: int | None, words: tuple[Node, ...],
                  en: tuple[Node, ...], is_label: Callable[[str], bool], *, at_start: bool) -> list[Pair] | None:
    """A paragraph of alternatives, each after its condition label (``בְּיוֹם <small>לר"ח:</small>
    רֹאשׁ הַחֹֽדֶשׁ הַזֶּה: <small>לפסח:</small> חַג הַמַּצּוֹת הַזֶּה: ... זָכְרֵֽנוּ``): a pair for
    each label with its words up to the next sof pasuq -- a label at the head of a phrase governs
    that phrase -- and pairs for the words around them; None when it has no label inside it.

    The English goes with the words before the first label, except: an instruction of its own on
    a new line goes with its label's words; and a run of italic alternatives
    (``<i>Rosh Chodesh/Festival of Matzos/Festival of Sukkos</i>``) is shared out among the
    labels when there is one for each, the English after it going with the words after them."""
    pieces: list[list] = []  # [Hebrew, English, labelled]
    position = _mid_label(words, is_label, at_start=at_start)
    if position is None:
        return None
    while position is not None:
        if plain_text(words[:position]).strip():
            pieces.append([words[:position], (), False])
        label = words[position]
        governed, words = _through_colon(words[position + 1:])
        pieces.append([(label,) + governed, (), True])
        position = _mid_label(words, is_label, at_start=True)
    if plain_text(words).strip():
        pieces.append([words, (), False])
    labelled = [piece for piece in pieces if piece[2]]
    # Instructions on lines of their own: each goes with the last labels' words, in order.
    segments = [en]
    while (brk := _instruction_break(segments[-1])) is not None:
        segments[-1:] = [segments[-1][:brk[0]], segments[-1][brk[1]:]]
    if 1 < len(segments) <= len(labelled) + 1:
        pieces[0][1] = segments[0]
        for piece, segment in zip(labelled[len(labelled) - len(segments) + 1:], segments[1:]):
            piece[1] = segment
        return [Pair(he_index, en_index, he, english) for he, english, _ in pieces]
    # Italic alternatives, one for each label.
    italic = [k for k, node in enumerate(en) if isinstance(node, Styled) and node.style == "italic"
              and "/" in plain_text(node.children)]
    trailing = pieces[-1] if not pieces[-1][2] else None
    if italic and not pieces[0][2]:
        k = italic[-1]
        before, after = en[:k], en[k + 1:]
        punctuation = ""
        if after and isinstance(after[0], Text):
            stripped = after[0].text.lstrip(" .,;")
            punctuation = after[0].text[:len(after[0].text) - len(stripped)].strip()
            after = ((Text(stripped),) if stripped.strip() else ()) + after[1:]
        choices = [choice.strip() for choice in plain_text(en[k].children).split("/")]
        if len(choices) == len(labelled):
            pieces[0][1] = before
            for piece, choice in zip(labelled, choices):
                piece[1] = (Styled("italic", (Text(choice),)), Text(punctuation)) if punctuation else (
                    Styled("italic", (Text(choice),)),)
        else:
            pieces[0][1] = en[:k + 1] + ((Text(punctuation),) if punctuation else ())
        if trailing is not None and trailing is not pieces[0]:
            trailing[1] = after
        else:
            pieces[0][1] = pieces[0][1] + after
    else:
        pieces[0][1] = en
    return [Pair(he_index, en_index, he, english) for he, english, _ in pieces]


def _unfold_labels(nodes: tuple[Node, ...], is_label: Callable[[str], bool]) -> tuple[Node, ...]:
    """A known condition label and the words it governs printed in one run of small type
    (``<small>בעשי"ת מסיים: בָּרוּךְ אַתָּה יְהֹוָה הַמֶּֽלֶךְ הַקָּדוֹשׁ:</small>``), as the label
    printed apart: a run of its own."""
    unfolded: list[Node] = []
    for node in nodes:
        opening = node.children[0] if isinstance(node, Styled) and node.style == "small" and node.children else None
        if isinstance(opening, Text) and ":" in opening.text:
            at = opening.text.index(":") + 1
            label, words = opening.text[:at], opening.text[at:]
            rest = ((Text(words),) if words.strip() else ()) + node.children[1:]
            if not is_pointed(label) and is_label(label) and is_pointed(plain_text(rest)):
                unfolded += [Styled("small", (Text(label.strip()),)), Text(" "), Styled("small", rest)]
                continue
        unfolded.append(node)
    return tuple(unfolded)


#: the words a blessing's ending opens with
BLESSING_OPENING = tuple(words("בָּרוּךְ אַתָּה יְהֹוָה"))
_ENGLISH_BLESSING = re.compile(r"Blessed are You,? Adonoy,?\s*")


def _split_ending(nodes: tuple[Node, ...], keep_opening: bool) -> tuple[tuple[Node, ...], tuple[Node, ...]] | None:
    """A paragraph's words before its last blessing's ending, and the ending: from ``בָּרוּךְ
    אַתָּה יְהֹוָה``, or after it (``keep_opening``). A paragraph that is all ending has nothing
    before it."""
    for k in range(len(nodes) - 1, -1, -1):
        node = nodes[k]
        if not isinstance(node, Text):
            continue
        tokens = re.split(r"(\s+)", node.text)
        positions = [i for i, token in enumerate(tokens) if token.strip()]
        normal = [tuple(words(tokens[i])) for i in positions]
        for j in range(len(positions) - len(BLESSING_OPENING), -1, -1):
            if all(normal[j + m] == (BLESSING_OPENING[m],) for m in range(len(BLESSING_OPENING))):
                at = j + len(BLESSING_OPENING) if keep_opening else j
                cut = positions[at] if at < len(positions) else len(tokens)
                head, tail = "".join(tokens[:cut]), "".join(tokens[cut:])
                before = nodes[:k] + ((Text(head),) if head.strip() else ())
                ending = ((Text(tail),) if tail.strip() else ()) + nodes[k + 1:]
                if not plain_text(ending).strip():
                    return None
                return (before if plain_text(before).strip() else ()), ending
    return None


def _split_english_ending(nodes: tuple[Node, ...], keep_opening: bool) -> tuple[tuple[Node, ...], tuple[Node, ...]]:
    """The English of ``_split_ending``: split at its last "Blessed are You, Adonoy", or kept whole."""
    for k in range(len(nodes) - 1, -1, -1):
        node = nodes[k]
        if isinstance(node, Text) and (found := list(_ENGLISH_BLESSING.finditer(node.text))):
            cut = found[-1].end() if keep_opening else found[-1].start()
            head, tail = node.text[:cut], node.text[cut:]
            return (nodes[:k] + ((Text(head),) if head.strip() else ()),
                    ((Text(tail),) if tail.strip() else ()) + nodes[k + 1:])
    return nodes, ()


def _replaced_endings(pairs: list[Pair], ending: Callable[[str], Any]) -> list[Pair]:
    """Each phrase that opens with an ending label (``Conditions`` ``ending``) replaces the ending
    of the blessing before it: that ending is set apart, and said otherwise."""
    out: list[Pair] = []
    for pair in pairs:
        label, rest = leading_label(pair.he)
        when = ending(plain_text(label.children)) if isinstance(label, Styled) else None
        previous = next((k for k in range(len(out) - 1, -1, -1) if is_pointed(plain_text(out[k].he))), None)
        if when is not None and previous is not None:
            keep = tuple(words(plain_text(rest)))[:len(BLESSING_OPENING)] != BLESSING_OPENING
            split = _split_ending(out[previous].he, keep)
            if split is not None:
                was = out[previous]
                if not split[0]:
                    out[previous] = dataclasses.replace(was, otherwise=when)
                else:
                    # The English keeps its opening as its own replacement does: "During the
                    # Ten Days: Blessed are You, Adonoy, the King of Justice" replaces the whole
                    # English ending, where the Hebrew label replaces only הַמֶּֽלֶךְ הַמִּשְׁפָּט.
                    replacing = split_leading(pair.en, {"italic", "small"}, hebrew=False)
                    replacing_en = plain_text(replacing[1] if replacing is not None else pair.en)
                    keep_en = _ENGLISH_BLESSING.match(replacing_en.strip()) is None
                    before_en, ending_en = _split_english_ending(was.en, keep_en)
                    out[previous:previous + 1] = [dataclasses.replace(was, he=split[0], en=before_en),
                                                  Pair(was.he_index, was.en_index, split[1], ending_en,
                                                       otherwise=when)]
        out.append(pair)
    return out


def split_leading_labels(alignment: Alignment, is_label: Callable[[str], bool] = lambda text: False,
                         ending: Callable[[str], Any] = lambda text: None) -> Alignment:
    """A paragraph-layout leaf with its labels and instructions set apart (``Work.layout``): a
    pair whose Hebrew opens with an unpointed small label before pointed words becomes a pair for
    the label -- with the English's leading italic run, if it has one -- and a pair for the words.
    The linear volumes print such a label as a segment of its own, and so it is read the same way.
    A label set apart, or a condition label that is a segment of its own, is a
    ``paragraph_label``: it governs one paragraph. A paragraph of alternatives, each after its
    condition label, is divided as ``_alternatives`` says; a label for another ending of the
    blessing before it (``ending``, the condition it gives, if it is one) stays with its words, and
    the ending it replaces is set apart (``_replaced_endings``)."""
    pairs: list[Pair] = []
    for pair in alignment.pairs:
        unfolded = _unfold_labels(pair.he, is_label)
        if unfolded != pair.he:
            pair = dataclasses.replace(pair, he=unfolded)
        he = split_leading(pair.he, {"small"}, hebrew=True)
        if he is None and pair.he_kind is HebrewKind.LABEL and is_label(plain_text(pair.he)):
            # A condition label that is a segment of its own governs the paragraph after it.
            pairs.append(dataclasses.replace(pair, paragraph_label=True))
            continue
        head, _ = leading_label(pair.he)
        head_text = plain_text(head.children) if isinstance(head, Styled) else ""
        if he is not None and head is not None and is_label(head_text):
            if _mid_label(he[1], is_label) is not None:
                # A short label at the head of a paragraph of alternatives is the first of them.
                split = _alternatives(pair.he_index, pair.en_index, pair.he, pair.en, is_label, at_start=True)
                if split is not None:
                    pairs.extend(split)
                    continue
            if ending(head_text) is not None:
                pairs.append(pair)  # the label governs its own words: the phrase they make
                continue
        if he is None:
            words_, en_rest = pair.he, pair.en
        else:
            en = split_leading(pair.en, {"italic", "small"}, hebrew=False)
            en_label, en_rest = en if en is not None else ((), pair.en)
            label, words_ = he
            pairs.append(Pair(pair.he_index, pair.en_index, label, en_label, paragraph_label=True))
        split = _alternatives(pair.he_index, pair.en_index, words_, en_rest, is_label, at_start=False)
        if split is not None:
            pairs.extend(split)
        elif he is None:
            pairs.append(pair)
        else:
            pairs.append(Pair(pair.he_index, pair.en_index, words_, en_rest))
    return Alignment(alignment.leaf, tuple(_replaced_endings(pairs, ending)), alignment.policy, alignment.opens)


def join_chapters(leaves: tuple[Leaf, ...], alignments: list[Alignment],
                  joined_paths: Collection[str]) -> tuple[tuple[Leaf, ...], list[Alignment]]:
    """The chapters of each leaf of depth 2 (``Leaf.chapter``) whose path is in ``joined_paths``
    -- the structure table places the leaf, not its chapters -- aligned one by one, joined into
    one leaf and one alignment: the segments numbered on through the leaf, and each chapter
    opening a text at its first phrase. Every other leaf passes through as it is (the Song of
    Songs, whose chapters the Shabbat siddur places one by one)."""
    from opensiddur.importer.sefaria.blocks import is_phrase  # blocks imports this module

    by_leaf = {a.leaf: a for a in alignments}
    joined_leaves: list[Leaf] = []
    joined: list[Alignment] = []
    position = 0
    while position < len(leaves):
        leaf = leaves[position]
        if not leaf.chapter or PATH_SEPARATOR.join(leaf.keys[:-1]) not in joined_paths:
            joined_leaves.append(leaf)
            if leaf in by_leaf:
                joined.append(by_leaf[leaf])
            position += 1
            continue
        chapters: list[Leaf] = []
        while (position < len(leaves) and leaves[position].chapter
               and leaves[position].keys[:-1] == leaf.keys[:-1]):
            chapters.append(leaves[position])
            position += 1
        he: list[str] = []
        en: list[str] = []
        pairs: list[Pair] = []
        opens: set[int] = set()
        for chapter in chapters:
            he_offset, en_offset = len(he), len(en)
            alignment = by_leaf[chapter]
            opening = True
            for pair in alignment.pairs:
                moved = dataclasses.replace(
                    pair, he_index=None if pair.he_index is None else pair.he_index + he_offset,
                    en_index=None if pair.en_index is None else pair.en_index + en_offset)
                if opening and moved.he_index is not None:
                    opens.add(moved.he_index)
                if is_phrase(pair):
                    opening = False
                pairs.append(moved)
            opens.update(index + he_offset for index in alignment.opens)
            he.extend(chapter.he)
            en.extend(chapter.en)
        day = Leaf(leaf.keys[:-1], leaf.titles[:-1], tuple(he), tuple(en))
        joined_leaves.append(day)
        policies = {by_leaf[c].policy for c in chapters}
        joined.append(Alignment(day, tuple(pairs), policies.pop() if len(policies) == 1 else "joined",
                                frozenset(opens)))
    return tuple(joined_leaves), joined
