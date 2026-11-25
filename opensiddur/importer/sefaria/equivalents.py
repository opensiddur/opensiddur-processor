"""Curated URN choices: what the matcher cannot decide by the words alone.

``equivalents.yaml`` holds two lists, each entry found by the opening words of a block (compared
as :func:`util.incipit.words` compares them), optionally only in one leaf, or in any of a list
of leaves (the same text where each volume prints it):

- ``texts``: the URN a block opening so is. A text that does the same job as one the collection
  names, and is mostly its words, is that text, whatever rite it is printed in (Sefard
  ``נקדישך ונעריצך`` is Birnbaum's ``amidah/qedushah/neqaddesh``). A URN the collection does not
  hold yet is the name the text is given when it is minted: a verse collage named by its
  function (``shesh_zekhirot``), or the name shared with an opensiddur.org post.
- ``joins``: a block opening so continues the text before it in its leaf, with the headings and
  rubrics between them inside it (each of the six remembrances, after the first).

The choices apply to every Metsudah volume. They are knowledge about texts, not decisions about
one block, so they live here rather than in ``metsudah_urns.jsonl``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from opensiddur.importer.sefaria.blocks import Heading, Item, Rubric, TextBlock
from opensiddur.importer.sefaria.markup import plain_text
from opensiddur.importer.util.incipit import TEXT_PREFIX, words

EQUIVALENTS_FILE = Path(__file__).with_name("equivalents.yaml")


class EquivalentsError(ValueError):
    pass


@dataclass(frozen=True)
class Choice:
    opens: tuple[str, ...]
    urn: str
    leaf: str | tuple[str, ...] | None = None
    note: str = ""
    #: the words the text ends with: only a block that has them is the text, and one that runs
    #: on past them is cut there
    ends: tuple[str, ...] = ()
    #: words the block must also have (the full Kaddish's תתקבל), each a run of words
    having: tuple[tuple[str, ...], ...] = ()
    #: a text this one opens with, transcluded where the volume prints it in the same words (the
    #: full Kaddish opens with the half Kaddish)
    transcludes: str = ""

    def matches(self, leaf: str, block_words: list[str]) -> bool:
        return (_in_leaf(self.leaf, leaf) and tuple(block_words[:len(self.opens)]) == self.opens
                and (not self.ends or _has(block_words, self.ends))
                and all(_has(block_words, run) for run in self.having))

    def reach(self, block_words: list[str]) -> int:
        """How far into the block the text reaches: where ``ends`` last ends (-1 without it)."""
        if not self.ends:
            return -1
        n = len(self.ends)
        return max((k + n for k in range(len(block_words) - n + 1)
                    if tuple(block_words[k:k + n]) == self.ends), default=-1)

    def end(self, phrase_words: list[list[str]]) -> int | None:
        """The 0-based phrase after the last one ``ends`` closes -- a refrain closes every stanza
        -- where the block runs on past it."""
        if not self.ends:
            return None
        seen: list[str] = []
        found = None
        for count, phrase in enumerate(phrase_words, 1):
            seen.extend(phrase)
            if tuple(seen[-len(self.ends):]) == self.ends:
                found = count
        return found if found is not None and found < len(phrase_words) else None


def _has(block_words: list[str], run: tuple[str, ...]) -> bool:
    return any(tuple(block_words[k:k + len(run)]) == run for k in range(len(block_words) - len(run) + 1))


@dataclass(frozen=True)
class Join:
    opens: tuple[str, ...]
    leaf: str | tuple[str, ...] | None = None
    note: str = ""
    #: words the text before must have (a part of the Kaddish joins only a Kaddish, which may run
    #: on at the end of the block before it: Ashrei and the half Kaddish after it)
    after: tuple[str, ...] = ()

    def matches(self, leaf: str, block_words: list[str]) -> bool:
        return _in_leaf(self.leaf, leaf) and tuple(block_words[:len(self.opens)]) == self.opens


@dataclass(frozen=True)
class Equivalents:
    texts: tuple[Choice, ...] = ()
    joins: tuple[Join, ...] = ()

    def choice(self, leaf: str, block_words: list[str]) -> Choice | None:
        """The choice a block matches with the longest opening; among those, the one whose text
        reaches furthest into the block (the full Kaddish, not the half Kaddish it opens with),
        and then the one with more words it must have (the full Kaddish, not the Mourner's)."""
        found = [c for c in self.texts if c.matches(leaf, block_words)]
        return max(found, key=lambda c: (len(c.opens), c.reach(block_words), len(c.having))) if found else None

    def openings(self) -> dict[str, str]:
        """Each text that opens with another, transcluded: its URN -> the URN of that other."""
        return {c.urn: c.transcludes for c in self.texts if c.transcludes}

    def joins_previous(self, leaf: str, block_words: list[str], previous_words: list[str] | None = None) -> bool:
        return any(j.matches(leaf, block_words) and (
            not j.after or _has(previous_words or [], j.after)) for j in self.joins)


def _in_leaf(wanted: str | tuple[str, ...] | None, leaf: str) -> bool:
    if wanted is None:
        return True
    return leaf == wanted if isinstance(wanted, str) else leaf in wanted


def _leaf(entry: dict) -> str | tuple[str, ...] | None:
    leaf = entry.get("leaf")
    return tuple(str(item) for item in leaf) if isinstance(leaf, list) else leaf


def _opens(entry: dict, where: str) -> tuple[str, ...]:
    opens = tuple(words(str(entry.get("opens", ""))))
    if not opens:
        raise EquivalentsError(f"{where}: an entry needs the words it opens with (opens)")
    return opens


def load_equivalents(path: Path = EQUIVALENTS_FILE) -> Equivalents:
    if not path.exists():
        return Equivalents()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    texts: list[Choice] = []
    for n, entry in enumerate(data.get("texts") or (), start=1):
        urn = str(entry.get("urn", ""))
        if not urn.startswith(TEXT_PREFIX):
            raise EquivalentsError(f"{path.name} texts #{n}: {urn!r} is not a text URN")
        if not isinstance(entry.get("with") or [], list):
            raise EquivalentsError(f"{path.name} texts #{n}: with is a list of runs of words, not {entry['with']!r}")
        texts.append(Choice(_opens(entry, f"{path.name} texts #{n}"), urn, _leaf(entry),
                            entry.get("note", ""), tuple(words(str(entry.get("ends", "")))),
                            tuple(tuple(words(str(run))) for run in entry.get("with") or ()),
                            str(entry.get("transcludes", ""))))
        if texts[-1].transcludes and not texts[-1].transcludes.startswith(TEXT_PREFIX):
            raise EquivalentsError(f"{path.name} texts #{n}: transcludes {texts[-1].transcludes!r}, not a text URN")
    joins = [Join(_opens(entry, f"{path.name} joins #{n}"), _leaf(entry), entry.get("note", ""),
                  tuple(words(str(entry.get("after", "")))))
             for n, entry in enumerate(data.get("joins") or (), start=1)]
    return Equivalents(tuple(texts), tuple(joins))


def _block_words(block: TextBlock) -> list[str]:
    from opensiddur.importer.sefaria.match import matching_words
    return [w for pair in block.phrases for w in matching_words(pair)]


def apply_joins(leaf: str, items: list[Item], equivalents: Equivalents) -> list[Item]:
    """``items`` with every block a join names merged into the text before it in the leaf: the
    rubrics and headings between them, and its own heading, become pairs inside the text."""
    merged: list[Item] = []
    for item in items:
        k = len(merged) - 1
        while k >= 0 and isinstance(merged[k], (Rubric, Heading)):
            k -= 1
        previous = merged[k] if k >= 0 and isinstance(merged[k], TextBlock) else None
        if isinstance(item, TextBlock) and equivalents.joins_previous(
                leaf, _block_words(item), _block_words(previous) if previous is not None else None):
            if previous is not None:
                target = merged[k]
                assert isinstance(target, TextBlock)
                between: list = []
                for passed in merged[k + 1:]:
                    between.extend(passed.pairs if isinstance(passed, Rubric) else [passed.pair])
                if item.head is not None:
                    between.append(item.head)
                merged[k:] = [TextBlock(target.head, target.pairs + between + item.pairs)]
                continue
        merged.append(item)
    return merged


def block_opening(block: TextBlock) -> str:
    """A block's first Hebrew words, for reports."""
    return " ".join(" ".join(plain_text(p.he) for p in block.phrases).split()[:6])
