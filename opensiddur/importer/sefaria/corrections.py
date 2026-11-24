"""Misprints in a Metsudah volume and their corrections.

``corrections.yaml`` lists, for each work, the clear misprints of its segments: a typographical
error, or a slip that makes one printing of a text differ from the book's other printings of it.
Each entry names the leaf (its path before chapters are joined, ``First Day / 1``), the version
(``he`` or ``en``), the 1-based segment, the words as printed (``sic``) and as corrected
(``corr``), and why. The words are written as both, ``tei:choice/tei:sic + tei:corr``, so the
reader's ``readings.errors`` setting chooses (corrected by default); everywhere the importer
compares words -- matching, a text's printings, the opening a larger text shares with a smaller
one -- it compares the corrected words.

An entry whose words are no longer in its segment (Sefaria corrected the text, or the
segmentation moved) is an error, to be removed or moved.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from opensiddur.importer.sefaria.align import Alignment
from opensiddur.importer.sefaria.markup import Correction, Node, Styled, Text

CORRECTIONS_FILE = Path(__file__).with_name("corrections.yaml")


class CorrectionError(ValueError):
    pass


@dataclass(frozen=True)
class SegmentCorrection:
    leaf: str
    lang: str
    segment: int
    sic: str
    corr: str


def load_corrections(path: Path = CORRECTIONS_FILE) -> dict[str, list[SegmentCorrection]]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise CorrectionError(f"{path.name}: expected a mapping of works to lists of corrections")
    out: dict[str, list[SegmentCorrection]] = {}
    for work, entries in data.items():
        if not isinstance(entries, list):
            raise CorrectionError(f"{path.name}: {work}: expected a list of corrections")
        for entry in entries:
            try:
                correction = SegmentCorrection(str(entry["leaf"]), entry["lang"], int(entry["segment"]),
                                               entry["sic"], entry["corr"])
            except (KeyError, TypeError, ValueError) as exc:
                raise CorrectionError(f"{path.name}: {work}: an entry needs leaf, lang, segment, "
                                      f"sic and corr: {entry!r}") from exc
            if (correction.lang not in ("he", "en") or not isinstance(correction.sic, str)
                    or not isinstance(correction.corr, str) or not correction.sic.strip()
                    or not correction.corr.strip() or correction.sic == correction.corr):
                raise CorrectionError(f"{path.name}: {work}: {entry!r}")
            out.setdefault(work, []).append(correction)
    return out


def _pattern(sic: str) -> re.Pattern[str]:
    """The printed words, whole: not inside a longer word."""
    return re.compile(r"(?<!\w)" + re.escape(sic) + r"(?!\w)")


def _count(nodes: tuple[Node, ...], sic: str) -> int:
    total = 0
    for node in nodes:
        if isinstance(node, Text):
            total += len(_pattern(sic).findall(node.text))
        elif isinstance(node, Styled):
            total += _count(node.children, sic)
    return total


def _replace(nodes: tuple[Node, ...], correction: SegmentCorrection) -> tuple[Node, ...]:
    out: list[Node] = []
    for node in nodes:
        if isinstance(node, Text) and _pattern(correction.sic).search(node.text):
            before, after = _pattern(correction.sic).split(node.text, 1)
            out.extend(n for n in (Text(before) if before else None,
                                   Correction(correction.sic, correction.corr),
                                   Text(after) if after else None) if n is not None)
        elif isinstance(node, Styled):
            out.append(dataclasses.replace(node, children=_replace(node.children, correction)))
        else:
            out.append(node)
    return tuple(out)


def apply_corrections(alignments: list[Alignment], corrections: list[SegmentCorrection]) -> list[Alignment]:
    """The alignments with each correction's words marked in its segment. Every correction must
    find its words once, within one run of text."""
    wanted: dict[tuple[str, str, int], list[SegmentCorrection]] = {}
    for correction in corrections:
        wanted.setdefault((correction.leaf, correction.lang, correction.segment), []).append(correction)
    found: set[tuple[str, str, int]] = set()
    errors: list[str] = []
    out: list[Alignment] = []
    for alignment in alignments:
        pairs = list(alignment.pairs)
        for position, pair in enumerate(pairs):
            for lang, index in (("he", pair.he_index), ("en", pair.en_index)):
                key = (alignment.leaf.path, lang, index)
                if index is None or key not in wanted:
                    continue
                found.add(key)
                nodes = getattr(pair, lang)
                for correction in wanted[key]:
                    if _count(nodes, correction.sic) != 1:
                        errors.append(f"{key[0]} ({lang} {index}): {correction.sic!r} is not in the "
                                      "segment once")
                        continue
                    nodes = _replace(nodes, correction)
                pair = dataclasses.replace(pair, **{lang: nodes})
                pairs[position] = pair
        out.append(dataclasses.replace(alignment, pairs=tuple(pairs)))
    errors.extend(f"{leaf} ({lang} {index}): no such segment" for leaf, lang, index in sorted(set(wanted) - found))
    if errors:
        raise CorrectionError("misprint corrections that no longer apply:\n" + "\n".join(errors))
    return out
