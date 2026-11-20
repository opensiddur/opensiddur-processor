"""Metsudah's phrases, and the ``metsudah:`` URNs that align them.

``urn:x-opensiddur:text:metsudah:<text path>/<n>`` names the *n*th phrase of the linear
layout within the text whose URN path is ``<text path>`` -- ``metsudah:modeh_ani/2`` is the
second phrase of ``prayer:modeh_ani``. It never names a volume, so a text Metsudah prints in
several volumes (Ashrei in the Weekday and the Shabbat Siddur and in the machzorim) has its
phrases named once, and the volumes align with each other as well as Hebrew with English.
A path the registry has in two namespaces keeps the namespace of the text that is not
``prayer:`` (``metsudah:poem/hamavdil_bein_qodesh_lechol/1``); see :func:`text_path`.

The number is Metsudah's own division (``specs/SIDDUR_URN_SCHEME.md``, "Sub-division
numbering"): it pairs Metsudah's Hebrew with Metsudah's English, and a text whose phrases were
named in an earlier volume keeps those numbers. A later printing of the text is matched to the
recorded phrases by :func:`map_phrases`: a phrase that is functionally the same and mostly the
same in wording keeps its number, even across rites; a phrase added or truly different is
numbered after the last one recorded.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Sequence
from difflib import SequenceMatcher
from pathlib import Path

from lxml import etree

from opensiddur.importer.util.incipit import TEXT_PREFIX, words

NAMESPACE = "metsudah"
PREFIX = f"{TEXT_PREFIX}{NAMESPACE}:"
TEI = "http://www.tei-c.org/ns/1.0"
#: Namespaces whose texts' phrases may be named, and so whose paths share ``metsudah:``.
TEXT_NAMESPACES = ("prayer", "poem", "bible")
#: Similarity (0..1, on the consonant skeleton) above which two printings of a phrase are the
#: same phrase.
SAME_PHRASE = 0.75


def _split(text_urn: str) -> tuple[str, str]:
    if not text_urn.startswith(TEXT_PREFIX):
        raise ValueError(f"{text_urn} is not a text URN")
    namespace, _, path = text_urn[len(TEXT_PREFIX):].partition(":")
    if namespace not in TEXT_NAMESPACES or not path:
        raise ValueError(f"{text_urn}: phrases are named only in {TEXT_NAMESPACES}")
    return namespace, path.split("@", 1)[0]


def clashing_paths(urns: Iterable[str]) -> frozenset[str]:
    """The paths that more than one of :data:`TEXT_NAMESPACES` uses (``prayer:`` and ``poem:``
    both have ``hamavdil_bein_qodesh_lechol``), from the URNs given -- the registry's."""
    namespaces: dict[str, set[str]] = {}
    for urn in urns:
        try:
            namespace, path = _split(urn)
        except ValueError:
            continue
        namespaces.setdefault(path, set()).add(namespace)
    return frozenset(path for path, found in namespaces.items() if len(found) > 1)


def text_path(text_urn: str, clashes: Collection[str] = frozenset()) -> str:
    """``urn:x-opensiddur:text:prayer:amidah/avot`` -> ``amidah/avot``.

    A path in ``clashes`` (:func:`clashing_paths`) is kept by ``prayer:``; the other namespace's
    text has its namespace before it: ``poem:hamavdil_bein_qodesh_lechol`` ->
    ``poem/hamavdil_bein_qodesh_lechol``.

    A run of verses is spelled with ``_``, not ``-``: in a URN path ``-`` is a range, and
    ``metsudah:proverbs/31/10-31/2`` would read as one (``bible:proverbs/31/10-31`` ->
    ``proverbs/31/10_31``)."""
    namespace, path = _split(text_urn)
    path = path.replace("-", "_")
    if path in clashes and namespace != "prayer":
        return f"{namespace}/{path}"
    return path


def phrase_urn(text_urn: str, number: int, clashes: Collection[str] = frozenset()) -> str:
    return f"{PREFIX}{text_path(text_urn, clashes)}/{number}"


def split_phrase_urn(urn: str) -> tuple[str, int]:
    """``metsudah:amidah/avot/3`` -> (``amidah/avot``, 3)."""
    if not urn.startswith(PREFIX):
        raise ValueError(f"{urn} is not a {NAMESPACE}: URN")
    path, _, number = urn[len(PREFIX):].split("@", 1)[0].rpartition("/")
    if not path or not number.isdigit():
        raise ValueError(f"{urn}: expected {NAMESPACE}:<text path>/<n>")
    return path, int(number)


def skeleton(text: str) -> str:
    return " ".join(words(text))


def similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def map_phrases(new: Sequence[str], recorded: dict[int, str]) -> list[int]:
    """Numbers for the phrases ``new`` (skeletons, in order), given the phrases already
    recorded for the text (number -> skeleton). The best order-keeping pairing of the same
    phrases keeps their numbers; the rest are numbered after the highest recorded."""
    if not recorded:
        return list(range(1, len(new) + 1))
    old_numbers = sorted(recorded)
    old = [recorded[n] for n in old_numbers]
    rows, cols = len(new), len(old)
    # Longest order-keeping pairing of same phrases, weighted by similarity.
    score = [[0.0] * (cols + 1) for _ in range(rows + 1)]
    for i in range(rows - 1, -1, -1):
        for j in range(cols - 1, -1, -1):
            best = max(score[i + 1][j], score[i][j + 1])
            s = similarity(new[i], old[j])
            if s >= SAME_PHRASE:
                best = max(best, score[i + 1][j + 1] + 1 + s)
            score[i][j] = best
    numbers: list[int | None] = [None] * rows
    i = j = 0
    while i < rows and j < cols:
        s = similarity(new[i], old[j])
        if s >= SAME_PHRASE and score[i][j] == score[i + 1][j + 1] + 1 + s:
            numbers[i] = old_numbers[j]
            i += 1
            j += 1
        elif score[i + 1][j] >= score[i][j + 1]:
            i += 1
        else:
            j += 1
    next_number = max(old_numbers) + 1
    out: list[int] = []
    for number in numbers:
        if number is None:
            number = next_number
            next_number += 1
        out.append(number)
    return out


def recorded_phrases(project_dirs: Iterable[Path]) -> dict[str, dict[int, str]]:
    """The phrases already named in the Hebrew projects ``project_dirs``: text path ->
    {number: skeleton of the phrase's words}."""
    found: dict[str, dict[int, str]] = {}
    for project in project_dirs:
        for xml_file in sorted(project.glob("*.xml")):
            for path, number, text in _phrases_in(etree.parse(str(xml_file)).getroot()):
                found.setdefault(path, {}).setdefault(number, skeleton(text))
    return found


def _phrases_in(root: etree._Element) -> list[tuple[str, int, str]]:
    """Each phrase milestone in a document, with the words up to the next phrase milestone
    (notes are not the phrase's words)."""
    out: list[tuple[str, int, str]] = []
    current: list = [None, []]  # (text path, number) or None; words collected

    def close() -> None:
        if current[0] is not None:
            out.append((current[0][0], current[0][1], " ".join(current[1])))

    def feed(text: str | None) -> None:
        if text and current[0] is not None:
            current[1].append(text)

    def visit(element: etree._Element) -> None:
        if not isinstance(element.tag, str):
            feed(element.tail)
            return
        local = etree.QName(element).localname
        if local in ("teiHeader", "standOff", "note"):
            feed(element.tail)
            return
        if local == "milestone" and element.get("unit") == "phrase":
            close()
            corresp = element.get("corresp", "")
            current[0] = split_phrase_urn(corresp) if corresp.startswith(PREFIX) else None
            current[1] = []
        feed(element.text)
        for child in element:
            visit(child)
        feed(element.tail)

    visit(root)
    close()
    return out
