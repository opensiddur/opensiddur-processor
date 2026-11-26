"""Canonical verse numbering for the ``urn:x-opensiddur:text:bible:`` URN space.

A verse URN is the only join key between projects: the parallel compiler pairs two
documents' text by exact ``@corresp`` equality, and the reference database resolves
transclusion ranges by it. That only works if ``exodus/20/13`` denotes the same stretch of
text in every project, which is not true of the editions' own numbering.

**The canonical division.** A canonical verse boundary is any point that is a verse boundary
under *either* ta'am elyon or ta'am tachton. In the Decalogue the two cantillations divide
differently -- ta'am tachton merges the four short commandments into one verse and splits
אנכי from לא יהיה לך, ta'am elyon does the reverse -- so their union is finer than either.
That union is what the Leningrad Codex numbers, giving Exodus 20 = 26 verses and
Deuteronomy 5 = 33. Every edition's own division is a coarsening of it, so an edition verse
is always a whole number of consecutive canonical verses.

Outside the Decalogue the editions still disagree in a handful of places, for reasons that
have nothing to do with cantillation. Those are recorded in :data:`DIVERGENCES` below.

**What this module is not.** It does not map the Decalogue. MAM ships both cantillation
strands, so its importer derives the canonical boundaries from its own source rather than
from a table here (see ``importer/miqra_al_pi_hamasorah``); a table would be a second,
divergent statement of the same fact. The Decalogue entries here exist only so that
references *stated* in an edition's numbering -- hebcal aliyah boundaries, a cross-reference
in a translation -- can be resolved to canonical.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from typing import NamedTuple

# Verse numbering conventions, and the project that follows each.
NUMBERING_MASORAH = "masorah"       # Miqra al pi ha-Masorah
NUMBERING_LENINGRAD = "leningrad"   # Westminster Leningrad Codex -- the canonical numbering
NUMBERING_COMMON = "common"         # common printed editions, which hebcal and jps1917 follow

NUMBERINGS = (NUMBERING_MASORAH, NUMBERING_LENINGRAD, NUMBERING_COMMON)

#: The numbering the canonical URN space uses. ``wlc`` needs no mapping at all.
CANONICAL_NUMBERING = NUMBERING_LENINGRAD

#: The Tanakh projects (specs/NAMING_SCHEME.md): the only place they are named.
MIQRA_PROJECT = "tanakh-miqra_al_pi_hamasorah-he"
WLC_PROJECT = "tanakh-wlc-he"
JPS_PROJECT = "tanakh-jps-1917-en"

#: The project that follows each numbering.
NUMBERING_PROJECT = {
    NUMBERING_MASORAH: MIQRA_PROJECT,
    NUMBERING_LENINGRAD: WLC_PROJECT,
    NUMBERING_COMMON: JPS_PROJECT,
}

PROJECT_NUMBERING = {project: numbering for numbering, project in NUMBERING_PROJECT.items()}


class VerseRef(NamedTuple):
    """A chapter and verse within a book."""

    chapter: int
    verse: int

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.chapter}:{self.verse}"


class UnknownVerse(KeyError):
    """Raised when a verse does not exist in the requested numbering."""


@dataclass(frozen=True)
class ChapterVersification:
    """How one edition numbers one chapter, relative to the canonical division.

    The four fields cover the four kinds of divergence actually present in the sources.
    They compose: the spans are built by walking the canonical verses of the chapter in
    order, so an edition may both merge and omit within one chapter.

    Attributes:
        canonical_verses: canonical verse count of this chapter.
        merges: canonical spans ``(first, last)`` that the edition reads as a single verse.
            The Decalogue case.
        omits: canonical verses the edition does not contain at all. A witness difference
            rather than a numbering one -- Joshua 21:36-37 are absent from MAM.
        absorbs_next_chapter: canonical verses taken from the *start of the next chapter*
            and numbered as the tail of this one. The edition's chapter is longer than the
            canonical one and the next chapter is renumbered throughout.
        merges_previous_chapter_tail: canonical verses at the *end of the previous chapter*
            that this edition reads as part of its own verse 1. Numbers 26:1 in MAM, which
            carries canonical 25:19 ahead of canonical 26:1 with a mid-verse parashah break.
    """

    canonical_verses: int
    merges: tuple[tuple[int, int], ...] = ()
    omits: tuple[int, ...] = ()
    absorbs_next_chapter: int = 0
    merges_previous_chapter_tail: int = 0

    def __post_init__(self) -> None:
        seen: set[int] = set()
        for first, last in self.merges:
            if last < first:
                raise ValueError(f"merge span {first}-{last} is reversed")
            span = set(range(first, last + 1))
            if span & seen:
                raise ValueError(f"merge span {first}-{last} overlaps another")
            seen |= span
        if set(self.omits) & seen:
            raise ValueError("a canonical verse cannot be both merged and omitted")


# Chapters an edition numbers differently from the canonical division.
#
# Derived from the raw sources rather than the generated projects: the MAM importer had a
# known shortfall in Numbers 10 that is absent from MAM itself, and encoding that here would
# bake an importer defect into the URN space. Verified by aligning MAM's TSV against the WLC
# XML verse by verse; every other chapter of the Tanakh agrees.
DIVERGENCES: dict[tuple[str, str, int], ChapterVersification] = {
    # --- The Decalogue: ta'am elyon vs ta'am tachton -------------------------------------
    # MAM numbers by ta'am tachton, which merges אנכי with לא יהיה לך and reads the four
    # short commandments as one verse.
    (NUMBERING_MASORAH, "exodus", 20): ChapterVersification(26, merges=((2, 3), (13, 16))),
    (NUMBERING_MASORAH, "deuteronomy", 5): ChapterVersification(33, merges=((6, 7), (17, 20))),
    # The common printed editions split אנכי but still merge the four short commandments.
    (NUMBERING_COMMON, "exodus", 20): ChapterVersification(26, merges=((13, 16),)),
    (NUMBERING_COMMON, "deuteronomy", 5): ChapterVersification(33, merges=((17, 20),)),

    # --- Divergences unrelated to cantillation -------------------------------------------
    # MAM reads canonical 25:19 ("ויהי אחרי המגפה") as the head of its own 26:1, separated
    # from canonical 26:1 by a parashah break in the middle of the verse.
    (NUMBERING_MASORAH, "numbers", 25): ChapterVersification(19, omits=(19,)),
    (NUMBERING_MASORAH, "numbers", 26): ChapterVersification(65, merges_previous_chapter_tail=1),
    # Joshua 21:36-37 are absent from MAM, so its numbering runs two short from verse 36 on.
    (NUMBERING_MASORAH, "joshua", 21): ChapterVersification(45, omits=(36, 37)),
    # MAM ends Jeremiah 30 and 1 Samuel 23 one verse later than the Leningrad Codex, which
    # renumbers the whole of the following chapter.
    (NUMBERING_MASORAH, "jeremiah", 30): ChapterVersification(24, absorbs_next_chapter=1),
    (NUMBERING_MASORAH, "samuel_1", 23): ChapterVersification(28, absorbs_next_chapter=1),
}

#: Canonical verse counts for the divergent chapters, so callers can validate a chapter
#: without reconstructing the spans. Chapters absent here are numbered identically by every
#: edition, and their canonical count is whatever the sources say.
CANONICAL_VERSE_COUNTS: dict[tuple[str, int], int] = {
    (book, chapter): spec.canonical_verses
    for (_numbering, book, chapter), spec in DIVERGENCES.items()
}


def divergent_chapters(numbering: str | None = None) -> set[tuple[str, int]]:
    """The ``(book, chapter)`` pairs some edition numbers differently from canonical."""
    return {
        (book, chapter)
        for (numbering_key, book, chapter) in DIVERGENCES
        if numbering is None or numbering_key == numbering
    }


@cache
def _spans(numbering: str, book: str, chapter: int) -> tuple[tuple[VerseRef, VerseRef], ...]:
    """The canonical span of every verse of ``chapter`` in ``numbering``, in edition order.

    Index ``n - 1`` holds the ``(first, last)`` canonical refs covered by the edition's
    verse ``n``. Both ends are inclusive, and are equal for the ordinary one-to-one case.
    """
    spec = DIVERGENCES.get((numbering, book, chapter))
    if spec is None:
        raise UnknownVerse(f"{book} {chapter} is not divergent in {numbering!r}")

    merge_start = {first: last for first, last in spec.merges}
    omitted = set(spec.omits)
    spans: list[tuple[VerseRef, VerseRef]] = []

    # A verse borrowed from the tail of the previous chapter heads this chapter's verse 1.
    lead_in: list[VerseRef] = []
    if spec.merges_previous_chapter_tail:
        previous = _canonical_verse_count(book, chapter - 1)
        borrowed = spec.merges_previous_chapter_tail
        lead_in = [VerseRef(chapter - 1, previous - borrowed + n + 1) for n in range(borrowed)]

    canonical = 1
    while canonical <= spec.canonical_verses:
        if canonical in omitted:
            canonical += 1
            continue
        last = merge_start.get(canonical, canonical)
        start_ref, end_ref = VerseRef(chapter, canonical), VerseRef(chapter, last)
        if lead_in and not spans:
            start_ref = lead_in[0]
        spans.append((start_ref, end_ref))
        canonical = last + 1

    for n in range(spec.absorbs_next_chapter):
        spans.append((VerseRef(chapter + 1, n + 1), VerseRef(chapter + 1, n + 1)))

    return tuple(spans)


def _canonical_verse_count(book: str, chapter: int) -> int:
    count = CANONICAL_VERSE_COUNTS.get((book, chapter))
    if count is None:
        raise UnknownVerse(
            f"no canonical verse count recorded for {book} {chapter}; it is only needed for "
            "chapters adjacent to a divergent one"
        )
    return count


def _borrowed_by_previous_chapter(numbering: str, book: str, chapter: int) -> int:
    """How many of this chapter's leading canonical verses the previous chapter absorbed."""
    previous = DIVERGENCES.get((numbering, book, chapter - 1))
    return previous.absorbs_next_chapter if previous else 0


def to_canonical(numbering: str, book: str, chapter: int, verse: int) -> tuple[VerseRef, VerseRef]:
    """Map a verse stated in ``numbering`` to the canonical verses it covers.

    Returns the inclusive ``(first, last)`` canonical refs. They are equal unless the
    edition merges several canonical verses into one, as it does in the Decalogue.

    Raises:
        UnknownVerse: if the verse does not exist in that numbering.
    """
    if numbering == CANONICAL_NUMBERING:
        return VerseRef(chapter, verse), VerseRef(chapter, verse)
    if verse < 1:
        raise UnknownVerse(f"{book} {chapter}:{verse} is not a verse")

    if (numbering, book, chapter) in DIVERGENCES:
        spans = _spans(numbering, book, chapter)
        if verse > len(spans):
            raise UnknownVerse(f"{book} {chapter}:{verse} does not exist in {numbering!r}")
        return spans[verse - 1]

    # A chapter whose predecessor absorbed its opening verses is renumbered throughout even
    # though the chapter itself has no entry of its own.
    offset = _borrowed_by_previous_chapter(numbering, book, chapter)
    shifted = VerseRef(chapter, verse + offset)
    return shifted, shifted


def from_canonical(numbering: str, book: str, chapter: int, verse: int) -> VerseRef:
    """Map a canonical verse to the verse that contains it in ``numbering``.

    Raises:
        UnknownVerse: if the edition omits the verse entirely.
    """
    if numbering == CANONICAL_NUMBERING:
        return VerseRef(chapter, verse)

    # The verse may be numbered as the tail of the previous chapter (Jeremiah 31:1, which MAM
    # reads as 30:25), within this chapter, or as the head of the next (Numbers 25:19, which
    # MAM reads as the first half of 26:1).
    for candidate_chapter in (chapter - 1, chapter, chapter + 1):
        if (numbering, book, candidate_chapter) not in DIVERGENCES:
            continue
        for index, (first, last) in enumerate(_spans(numbering, book, candidate_chapter), start=1):
            if first <= VerseRef(chapter, verse) <= last:
                return VerseRef(candidate_chapter, index)

    offset = _borrowed_by_previous_chapter(numbering, book, chapter)
    if offset:
        if verse <= offset:
            raise UnknownVerse(
                f"canonical {book} {chapter}:{verse} is numbered in the previous chapter"
            )
        return VerseRef(chapter, verse - offset)

    if (numbering, book, chapter) in DIVERGENCES:
        raise UnknownVerse(f"{book} {chapter}:{verse} is absent from {numbering!r}")
    return VerseRef(chapter, verse)


def edition_verse_count(numbering: str, book: str, chapter: int, canonical_verses: int) -> int:
    """How many verses ``numbering`` reads in a chapter of ``canonical_verses`` verses."""
    if (numbering, book, chapter) in DIVERGENCES:
        return len(_spans(numbering, book, chapter))
    return canonical_verses - _borrowed_by_previous_chapter(numbering, book, chapter)


def iter_canonical(numbering: str, book: str, chapter: int) -> Iterator[tuple[int, VerseRef, VerseRef]]:
    """Yield ``(edition_verse, first_canonical, last_canonical)`` for a divergent chapter."""
    for index, (first, last) in enumerate(_spans(numbering, book, chapter), start=1):
        yield index, first, last
