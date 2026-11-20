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

    def matches(self, leaf: str, block_words: list[str]) -> bool:
        return _in_leaf(self.leaf, leaf) and tuple(block_words[:len(self.opens)]) == self.opens


@dataclass(frozen=True)
class Join:
    opens: tuple[str, ...]
    leaf: str | tuple[str, ...] | None = None
    note: str = ""

    def matches(self, leaf: str, block_words: list[str]) -> bool:
        return _in_leaf(self.leaf, leaf) and tuple(block_words[:len(self.opens)]) == self.opens


@dataclass(frozen=True)
class Equivalents:
    texts: tuple[Choice, ...] = ()
    joins: tuple[Join, ...] = ()

    def choice(self, leaf: str, block_words: list[str]) -> Choice | None:
        """The longest-opening choice a block matches."""
        found = [c for c in self.texts if c.matches(leaf, block_words)]
        return max(found, key=lambda c: len(c.opens)) if found else None

    def joins_previous(self, leaf: str, block_words: list[str]) -> bool:
        return any(j.matches(leaf, block_words) for j in self.joins)


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
        texts.append(Choice(_opens(entry, f"{path.name} texts #{n}"), urn, _leaf(entry),
                            entry.get("note", "")))
    joins = [Join(_opens(entry, f"{path.name} joins #{n}"), _leaf(entry), entry.get("note", ""))
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
        if isinstance(item, TextBlock) and equivalents.joins_previous(leaf, _block_words(item)):
            k = len(merged) - 1
            while k >= 0 and isinstance(merged[k], (Rubric, Heading)):
                k -= 1
            if k >= 0 and isinstance(merged[k], TextBlock):
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
