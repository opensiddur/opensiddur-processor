"""Split MAM's verses into canonical verses.

MAM numbers by ta'am tachton, which in the Decalogue merges the four short commandments
into one verse and reads אנכי together with לא יהיה לך. The canonical URN space numbers the
union of the two cantillations' boundaries, so several canonical verses can fall inside one
MAM verse, and a project that emitted one milestone per MAM verse would give those canonical
verses no URN of their own -- or, as the importer previously did, give them all the *same*
URN, which the reference database and the parallel compiler both silently collapse.

MAM ships both cantillation strands (``{{מ:כפול|כפול=…|א=…|ב=…}}``), so the interior
boundaries are derivable from MAM's own source: wherever the ta'am elyon strand ends a verse
but MAM's own does not, a canonical verse ends. Where a merge is not cantillation-driven --
Numbers 26:1, which carries canonical 25:19 ahead of it -- the boundary is a parashah break
in the middle of the verse instead.

How many canonical verses a MAM verse covers is not inferred from the source; it comes from
:mod:`opensiddur.common.versification`, and the boundaries found here must agree with it.
A mismatch means the source and the table disagree about the text, which is an error worth
stopping for rather than papering over.
"""

from __future__ import annotations

from lxml import etree

from opensiddur.common.versification import (
    CANONICAL_VERSE_COUNTS,
    NUMBERING_MASORAH,
    UnknownVerse,
    to_canonical,
)

MIQRA_NS = "urn:x-opensiddur:miqra:intermediate"
Q = f"{{{MIQRA_NS}}}"

#: U+05C3 HEBREW PUNCTUATION SOF PASUQ -- the end-of-verse mark.
SOF_PASUQ = "׃"

#: The ta'am elyon strand. ``א`` is ta'am tachton, which is the reading MAM's own verse
#: division follows; see the strand labels MAM-parsed documents (``mpplus_dualcant.html``).
ELYON_STRAND = "ב"


class CanonicalVerseError(ValueError):
    """The boundaries found in the source disagree with the versification table."""


def _text_of(element: etree._Element) -> str:
    return "".join(element.itertext())


def _ends_verse(dual_accent: etree._Element, role: str) -> bool:
    """True when ``role``'s reading of this span ends a verse."""
    strand = dual_accent.find(f'{Q}strand[@role="{role}"]')
    if strand is None:
        return False
    return _text_of(strand).rstrip().endswith(SOF_PASUQ)


def _has_content_after(children: list[etree._Element], index: int) -> bool:
    """True when real text follows ``children[index]`` within the same verse."""
    rest = [children[index].tail or ""]
    for later in children[index + 1:]:
        rest.append(_text_of(later))
        rest.append(later.tail or "")
    return bool("".join(rest).strip())


def _elyon_boundaries(text: etree._Element) -> list[int]:
    """Indices of top-level children after which the ta'am elyon reading ends a verse."""
    children = list(text)
    return [
        index
        for index, child in enumerate(children)
        if child.tag == f"{Q}dual-accent"
        and _ends_verse(child, ELYON_STRAND)
        and _has_content_after(children, index)
    ]


def _mid_verse_parashah_boundaries(text: etree._Element) -> list[int]:
    """Indices of top-level children after which a parashah break falls mid-verse.

    Used only where a merge is not cantillation-driven -- Numbers 26:1, whose two canonical
    halves are separated by a parashah break rather than by a difference in cantillation.

    The source carries a break three ways, all of which reach the body: bare, wrapped in a
    ``{{נוסח}}`` because another witness places it differently, or inside a ``{{מ:כפול}}``
    whose strands hold nothing but the break.
    """
    children = list(text)
    boundaries = []
    for index, child in enumerate(children):
        if child.tag == f"{Q}parashah":
            has_break = True
        elif child.tag == f"{Q}variant":
            has_break = child.find(f"{Q}display/{Q}parashah") is not None
        elif child.tag == f"{Q}dual-accent":
            has_break = child.find(f".//{Q}parashah") is not None and not _text_of(child).strip()
        else:
            has_break = False
        if has_break and _has_content_after(children, index):
            boundaries.append(index)
    return boundaries


def _split_text(
    text: etree._Element, boundaries: list[int]
) -> list[tuple[str | None, list[etree._Element]]]:
    """Partition the children of ``miqra:text`` after each boundary index.

    Returns ``(leading_text, elements)`` per segment. The tail of a boundary element is the
    text that follows the verse-final word, so it opens the *next* segment rather than
    closing the one that ends at the boundary.
    """
    children = list(text)
    segments: list[tuple[str | None, list[etree._Element]]] = []
    leading = text.text
    start = 0
    for boundary in boundaries:
        segments.append((leading, children[start:boundary + 1]))
        leading = children[boundary].tail
        children[boundary].tail = None
        start = boundary + 1
    segments.append((leading, children[start:]))
    return segments


def _new_row(template: etree._Element, *, verse: int, edition_verse: int, first: bool) -> etree._Element:
    row = etree.Element(f"{Q}row", nsmap=template.nsmap)
    for name, value in template.attrib.items():
        row.set(name, value)
    row.set("verse", str(verse))
    row.set("editionVerse", str(edition_verse))
    row.set("editionVerseStart", "true" if first else "false")
    return row


def annotate_canonical_verses(intermediate_xml: str, book: str) -> str:
    """Renumber and split ``miqra:row`` elements onto the canonical verse division.

    Every emitted row carries ``@verse`` in canonical numbering and ``@editionVerse`` in
    MAM's own, so the importer can mint one canonical URN per row and still display MAM's
    numbering. Rows for chapters both editions number alike pass through with only
    ``@editionVerse`` added.

    Args:
        intermediate_xml: the ``miqra:book`` document.
        book: the book's opensiddur slug, e.g. ``"exodus"``.

    Raises:
        CanonicalVerseError: if a MAM verse is recorded as covering several canonical verses
            but the source offers the wrong number of boundaries to split it at.
    """
    root = etree.fromstring(intermediate_xml.encode("utf-8"))

    for row in list(root.findall(f"{Q}row")):
        chapter_raw, verse_raw = row.get("chapter", ""), row.get("verse", "")
        if not chapter_raw.isdigit() or not verse_raw.isdigit():
            continue
        chapter, edition_verse = int(chapter_raw), int(verse_raw)

        try:
            # A merged verse may cross a chapter boundary (Numbers 26:1), so each canonical
            # verse carries its own chapter rather than inheriting the row's.
            canonical_refs = _canonical_refs(book, chapter, edition_verse)
        except UnknownVerse as exc:
            raise CanonicalVerseError(
                f"{book} {chapter}:{edition_verse} is in the source but not in the "
                f"versification table for {NUMBERING_MASORAH!r}"
            ) from exc
        expected_segments = len(canonical_refs)

        row.set("editionVerse", str(edition_verse))
        if expected_segments == 1:
            (canonical_chapter, canonical_verse), = canonical_refs
            row.set("chapter", str(canonical_chapter))
            row.set("verse", str(canonical_verse))
            row.set("editionVerseStart", "true")
            continue

        text = row.find(f"{Q}text")
        boundaries = _elyon_boundaries(text) if text is not None else []
        if len(boundaries) != expected_segments - 1:
            boundaries = _mid_verse_parashah_boundaries(text) if text is not None else []
        if len(boundaries) != expected_segments - 1:
            raise CanonicalVerseError(
                f"{book} {chapter}:{edition_verse} covers {expected_segments} canonical "
                f"verses but the source offers {len(boundaries)} interior boundaries; the "
                "versification table and the source disagree"
            )

        segments = _split_text(text, boundaries)
        anchor = row
        for index, ((leading, elements), (canonical_chapter, canonical_verse)) in enumerate(
            zip(segments, canonical_refs)
        ):
            new_row = _new_row(
                row, verse=canonical_verse, edition_verse=edition_verse, first=index == 0
            )
            new_row.set("chapter", str(canonical_chapter))
            if index == 0:
                # Row-level navigation and scaffold anchor at the head of the MAM verse.
                for name in ("nav", "scaffold"):
                    part = row.find(f"{Q}{name}")
                    if part is not None:
                        new_row.append(part)
            new_text = etree.SubElement(new_row, f"{Q}text")
            new_text.text = leading
            for child in elements:
                new_text.append(child)
            anchor.addnext(new_row)
            anchor = new_row
        root.remove(row)

    return etree.tostring(root, encoding="unicode")


def _canonical_refs(book: str, chapter: int, edition_verse: int) -> list[tuple[int, int]]:
    """Every ``(chapter, verse)`` the MAM verse covers, in order."""
    first, last = to_canonical(NUMBERING_MASORAH, book, chapter, edition_verse)
    if first.chapter == last.chapter:
        return [(first.chapter, verse) for verse in range(first.verse, last.verse + 1)]
    # A merge across a chapter boundary: the tail of the previous chapter, then this one.
    previous_total = CANONICAL_VERSE_COUNTS[(book, first.chapter)]
    refs = [(first.chapter, verse) for verse in range(first.verse, previous_total + 1)]
    refs += [(last.chapter, verse) for verse in range(1, last.verse + 1)]
    return refs
