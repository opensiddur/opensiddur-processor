"""A downloaded Sefaria work, read into leaves of parallel Hebrew and English segments.

Sefaria stores a liturgical work as a *complex text*: a tree of named sections (schema nodes,
each with an English ``key`` and English and Hebrew titles) whose leaves are jagged arrays of
strings. A version's ``text`` is the same tree as nested objects keyed by the English keys.
The Metsudah linear volumes have leaves of depth 1 ("Paragraph"), each string one phrase of
the linear layout, Hebrew segment *n* translated by English segment *n*. A leaf of depth 2
("Chapter", "Paragraph") is read as one leaf per chapter, each marking its ``chapter``; the
chapters are aligned one by one and then joined into one leaf (``align.join_chapters``), whose
chapters each open a text. The Metsudah Selichot is such a work: a leaf is a day, and each of
its chapters a selichah or a run of the service.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: How a leaf is named in decision files and reports: its English keys joined by this.
PATH_SEPARATOR = " / "


@dataclass(frozen=True)
class Leaf:
    """One leaf of the schema: its English keys from the root, the English and Hebrew title
    of each level, and the segments of each version."""

    keys: tuple[str, ...]
    titles: tuple[tuple[str, str], ...]
    he: tuple[str, ...]
    en: tuple[str, ...]
    #: the chapter's number, for a chapter of a leaf of depth 2; 0 for a leaf of depth 1
    chapter: int = 0
    #: the languages whose segments come from the work's supplement, not its main version
    supplied: tuple[str, ...] = ()

    @property
    def path(self) -> str:
        return PATH_SEPARATOR.join(self.keys)

    @property
    def title_en(self) -> str:
        return self.titles[-1][0]

    @property
    def title_he(self) -> str:
        return self.titles[-1][1]


@dataclass(frozen=True)
class Node:
    """An inner node: a division that holds leaves or other divisions."""

    keys: tuple[str, ...]
    titles: tuple[tuple[str, str], ...]

    @property
    def path(self) -> str:
        return PATH_SEPARATOR.join(self.keys)


@dataclass(frozen=True)
class WorkSource:
    title_en: str
    title_he: str
    nodes: tuple[Node, ...]
    leaves: tuple[Leaf, ...]
    he_meta: dict[str, Any]
    en_meta: dict[str, Any]
    index: dict[str, Any]


def _primary_title(node: dict[str, Any], lang: str) -> str:
    for title in node.get("titles", []):
        if title.get("lang") == lang and title.get("primary"):
            return title["text"]
    return node.get("title" if lang == "en" else "heTitle", "")


def _child(text: Any, key: str, title: str = "") -> Any:
    """A child of a version's text tree. A default node's text is under ``""``; a section a
    version leaves out is an empty list. Some versions key a node by its English title where
    that differs from its schema key (Siddur Ashkenaz: "Pesukei Dezimra" for the key
    "Pesukei D'Zimra")."""
    if not isinstance(text, dict):
        return []
    if key == "default":
        return text.get("", text.get("default", []))
    found = text[key] if key in text else text.get(title, []) if title else []
    # (nodes that share a title, as Musaf's three Mourner's Kaddishes do, may collapse into one
    # empty string under it)
    return [] if isinstance(found, str) else found


def _strings(value: Any, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(s, str) for s in value):
        raise ValueError(f"{where}: expected a list of strings")
    return tuple(value)


def _walk(node: dict[str, Any], he: Any, en: Any, keys: tuple[str, ...],
          titles: tuple[tuple[str, str], ...]) -> Iterator[Node | Leaf]:
    if "nodes" in node:
        if keys:
            yield Node(keys, titles)
        for child in node["nodes"]:
            key = child["key"]
            child_keys = keys if key == "default" else keys + (key,)
            child_titles = titles if key == "default" else titles + (
                (_primary_title(child, "en"), _primary_title(child, "he")),)
            title = _primary_title(child, "en")
            yield from _walk(child, _child(he, key, title), _child(en, key, title), child_keys, child_titles)
        return
    depth = node.get("depth", 1)
    where = PATH_SEPARATOR.join(keys)
    if depth == 1:
        yield Leaf(keys, titles, _strings(he, f"{where} (he)"), _strings(en, f"{where} (en)"))
    elif depth == 2:
        he_chapters = he if isinstance(he, list) else []
        en_chapters = en if isinstance(en, list) else []
        for number in range(1, max(len(he_chapters), len(en_chapters)) + 1):
            he_chapter = he_chapters[number - 1] if number <= len(he_chapters) else []
            en_chapter = en_chapters[number - 1] if number <= len(en_chapters) else []
            yield Leaf(keys + (str(number),), titles + ((str(number), str(number)),),
                       _strings(he_chapter, f"{where} {number} (he)"),
                       _strings(en_chapter, f"{where} {number} (en)"), chapter=number)
    else:
        raise ValueError(f"{where}: a leaf of depth {depth} is not supported")


def _filled(segments: tuple[str, ...]) -> bool:
    return any(s.strip() for s in segments)


def read_work_source(index: dict[str, Any], he: dict[str, Any], en: dict[str, Any],
                     supplements: dict[str, dict[str, Any]] | None = None) -> WorkSource:
    """The work's nodes and leaves. A supplement (a second version of a language) gives the
    segments of a leaf the main version leaves empty."""
    nodes: list[Node] = []
    leaves: list[Leaf] = []
    supplied: dict[str, dict[str, tuple[str, ...]]] = {}
    for lang, version in (supplements or {}).items():
        texts = (version.get("text", {}), {}) if lang == "he" else ({}, version.get("text", {}))
        supplied[lang] = {item.path: getattr(item, lang) for item in _walk(index["schema"], *texts, (), ())
                          if isinstance(item, Leaf)}
    for item in _walk(index["schema"], he.get("text", {}), en.get("text", {}), (), ()):
        if isinstance(item, Leaf):
            for lang, segments in supplied.items():
                if not _filled(getattr(item, lang)) and _filled(segments.get(item.path, ())):
                    item = dataclasses.replace(item, **{lang: segments[item.path]},
                                               supplied=item.supplied + (lang,))
        (leaves if isinstance(item, Leaf) else nodes).append(item)
    return WorkSource(
        title_en=index.get("title", ""),
        title_he=index.get("heTitle", ""),
        nodes=tuple(nodes),
        leaves=tuple(leaves),
        he_meta={k: v for k, v in he.items() if k not in ("text", "schema")},
        en_meta={k: v for k, v in en.items() if k not in ("text", "schema")},
        index={k: v for k, v in index.items() if k != "schema"},
    )


def load_work_source(directory: Path) -> WorkSource:
    def load(name: str) -> dict[str, Any]:
        return json.loads((directory / name).read_text(encoding="utf-8"))
    supplements = {lang: load(f"{lang}_supplement.json") for lang in ("he", "en")
                   if (directory / f"{lang}_supplement.json").exists()}
    return read_work_source(load("schema.json"), load("he.json"), load("en.json"), supplements)


def segments_hash(segments: tuple[str, ...]) -> str:
    return hashlib.sha256(json.dumps(list(segments), ensure_ascii=False).encode("utf-8")).hexdigest()


def leaf_hashes(source: WorkSource) -> dict[str, dict[str, Any]]:
    """Each leaf's segment counts and a hash of each version's segments: what ``update``
    compares to tell an unchanged leaf from one whose text or segmentation changed."""
    return {
        leaf.path: {
            "he": segments_hash(leaf.he),
            "en": segments_hash(leaf.en),
            "he_segments": len(leaf.he),
            "en_segments": len(leaf.en),
        }
        for leaf in source.leaves
    }
