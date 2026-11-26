"""Read the weekly parshiyot and their aliyot out of Miqra al pi ha-Masorah.

MAM marks the *start* of every reading division in the label of the verse it starts at: a
``מ:עלייה`` template in the ``עלייה`` parameter of the verse label ``מ:פסוק``. In MAM-parsed
plus the label is column D of the verse, sometimes as the target of a documentation note
(``נוסח``). In MAM's wikitext:

    {{מ:פסוק|בראשית|א|א|סדר=א|עלייה={{מ:עלייה|א=בראשית|ב0=בראשית|ב1=ראשון|ב2=כהן}}}}

The parameters are:

==== ================================================================================
א    the label as printed in the margin
ב0   the weekly parshah this reading belongs to
ב1   the Shabbat aliyah — ראשון through שביעי
ב2   the weekday honour — כהן, לוי, ישראל, or ע"כ ישראל
ב3   מפטיר
ג0   the parshah name when this week is combined with the next, e.g. ויקהל–פקודי
ג1/ג2/ג3 the Shabbat aliyah, weekday honour or maftir of that combined reading
==== ================================================================================

The ``ג`` parameters are a second, independent division of the same text: the combined
reading's fourth aliyah runs through the point where the second parshah begins, so it is read
into its own unit-spaces rather than as a subdivision of either single.

Ends are not marked and must be inferred, separately within each unit-space, from the next
start in that same space — which is why the maftir, whose start falls inside the seventh
aliyah, does not shorten it. The one explicit end marker is ``ע"כ ישראל`` (עד כאן ישראל,
"thus far Yisrael"), which closes the weekday reading rather than opening a fourth aliyah.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from opensiddur.importer.miqra_al_pi_hamasorah.convert import load_source
from opensiddur.importer.miqra_al_pi_hamasorah.miqra_plus import (
    DOCUMENTATION_NOTE,
    VERSE_LABEL,
    PlusFormatError,
    check_aliyah,
    template_params,
)
from opensiddur.importer.humash.names import (
    PAIR_MEMBERS,
    slug_for_combined_hebrew,
    slug_for_hebrew,
)
from opensiddur.importer.humash.refs import (
    HEBREW_BOOK_TO_SLUG,
    UNIT_ALIYAH,
    UNIT_ALIYAH_COMBINED,
    UNIT_MAFTIR,
    UNIT_MAFTIR_COMBINED,
    UNIT_PARSHA,
    UNIT_PARSHA_COMBINED,
    UNIT_WEEKDAY,
    UNIT_WEEKDAY_COMBINED,
    NUMBERING_MASORAH,
    ReadingSpan,
    VerseRef,
    canonical_ref,
    chapters_in_book,
    previous_verse,
    verses_in_chapter,
)

logger = logging.getLogger(__name__)

# The seven Shabbat aliyot, in order, as MAM spells them.
SHABBAT_ALIYOT = ("ראשון", "שני", "שלישי", "רביעי", "חמישי", "ששי", "שביעי")
ALIYAH_NUMBER = {name: str(index + 1) for index, name in enumerate(SHABBAT_ALIYOT)}

# The weekday honours. ע"כ ישראל closes the reading instead of opening an aliyah.
WEEKDAY_HONOURS = ("כהן", "לוי", "ישראל")
WEEKDAY_END = 'ע"כ ישראל'
WEEKDAY_NUMBER = {name: str(index + 1) for index, name in enumerate(WEEKDAY_HONOURS)}

MAFTIR = "מפטיר"


@dataclass
class Parsha:
    """One weekly reading, with every division that begins inside it."""

    slug: str
    hebrew_name: str
    book: str
    start: VerseRef
    end: VerseRef | None = None
    spans: list[ReadingSpan] = field(default_factory=list)

    @property
    def parsha_span(self) -> ReadingSpan:
        return ReadingSpan(UNIT_PARSHA, self.slug, self.start, self.end)

    def spans_in(self, unit: str) -> list[ReadingSpan]:
        return [span for span in self.spans if span.unit == unit]


@dataclass
class CombinedParsha:
    """A pair read together on one Shabbat, with the divisions of that combined reading.

    It covers exactly the two singles' text end to end; those keep their own divisions, which
    are what is read on a year the pair is read apart.
    """

    slug: str
    hebrew_name: str
    book: str
    members: tuple[str, str]
    start: VerseRef
    end: VerseRef
    spans: list[ReadingSpan] = field(default_factory=list)

    @property
    def parsha_span(self) -> ReadingSpan:
        return ReadingSpan(UNIT_PARSHA_COMBINED, self.slug, self.start, self.end)

    def spans_in(self, unit: str) -> list[ReadingSpan]:
        return [span for span in self.spans if span.unit == unit]


@dataclass(frozen=True)
class _Division:
    """One of the two divisions a marker may carry: the single reading or the combined one."""

    aliyah_key: str
    weekday_key: str
    maftir_key: str
    aliyah_unit: str
    weekday_unit: str
    maftir_unit: str


SINGLE_DIVISION = _Division("ב1", "ב2", "ב3", UNIT_ALIYAH, UNIT_WEEKDAY, UNIT_MAFTIR)
COMBINED_DIVISION = _Division(
    "ג1", "ג2", "ג3", UNIT_ALIYAH_COMBINED, UNIT_WEEKDAY_COMBINED, UNIT_MAFTIR_COMBINED
)


@dataclass
class _Marker:
    """One ``{{מ:עלייה}}`` occurrence, before ends have been worked out."""

    ref: VerseRef
    params: dict[str, str]


def _verse_label_aliyah(label_column: Any, where: str) -> dict[str, str] | None:
    """The parameters of the aliyah marker in a verse's label column (column D), if any.

    The column is empty, or holds one ``מ:פסוק``, bare or as the target of a ``נוסח``.
    """
    if not isinstance(label_column, list) or len(label_column) > 1:
        raise PlusFormatError(f"{where}: unexpected verse label column {label_column!r}")
    if not label_column:
        return None
    name, params = template_params(label_column[0])
    if name == DOCUMENTATION_NOTE:
        name, params = template_params(params["1"])
    if name != VERSE_LABEL:
        raise PlusFormatError(f"{where}: the verse label column holds {name}")
    if "עלייה" not in params:
        return None
    return {key: value.strip() for key, value in check_aliyah(params["עלייה"]).items()}


def read_markers(sourcetexts_root: Path | None = None) -> list[_Marker]:
    """Every aliyah marker in MAM's Torah, in reading order.

    The download is read through the converter's ``load_source``, with its checks: each file
    against the manifest's SHA-256, no file that the manifest does not list, and the keys of
    every plus file.
    """
    source = load_source(sourcetexts_root)
    markers: list[_Marker] = []
    for name, book in HEBREW_BOOK_TO_SLUG.items():
        book39 = source.book39s.get(name)
        if book39 is None:
            raise PlusFormatError(f"the MAM-parsed plus files have no {book}")
        for chapter, verses in book39["chapters"].items():
            for verse, columns in verses.items():
                params = _verse_label_aliyah(columns[1], f"{book} {chapter}:{verse}")
                if params is None:
                    continue
                # MAM's own numbering, which the canonical URN space does not share in the
                # Decalogue and a few other chapters. A marker names where an aliyah begins,
                # so where MAM reads several canonical verses as one, the aliyah begins at
                # the first of them.
                ref = canonical_ref(
                    NUMBERING_MASORAH, VerseRef(book, int(chapter), int(verse))
                )
                markers.append(_Marker(ref=ref, params=params))
    return markers


def _end_of_book(book: str, sourcetexts_root: Path | None) -> VerseRef:
    last_chapter = chapters_in_book(book, sourcetexts_root)
    return VerseRef(book, last_chapter, verses_in_chapter(book, last_chapter, sourcetexts_root))


def _close_spans(
    starts: list[tuple[str, VerseRef, str | None]],
    unit: str,
    final_end: VerseRef,
    sourcetexts_root: Path | None,
) -> list[ReadingSpan]:
    """Turn a unit-space's start points into spans, each ending before the next start.

    Only starts within the same unit-space are considered, so that a division belonging to
    another space cannot cut one of these short.
    """
    spans: list[ReadingSpan] = []
    for index, (label, start, note) in enumerate(starts):
        if index + 1 < len(starts):
            end = previous_verse(starts[index + 1][1], sourcetexts_root)
        else:
            end = final_end
        spans.append(ReadingSpan(unit=unit, label=label, start=start, end=end, note=note))
    return spans


def parse_parshiyot(sourcetexts_root: Path | None = None) -> list[Parsha]:
    """Build the 54 weekly parshiyot, each with its aliyot, weekday aliyot and maftir."""
    return parse_readings(sourcetexts_root)[0]


def parse_readings(
    sourcetexts_root: Path | None = None,
) -> tuple[list[Parsha], list[CombinedParsha]]:
    """The 54 weekly parshiyot and the seven combined readings, from one pass over MAM's Torah."""
    markers = read_markers(sourcetexts_root)
    parshiyot = _parse_parshiyot(markers, sourcetexts_root)
    return parshiyot, _parse_combined(markers, parshiyot, sourcetexts_root)


def _parse_parshiyot(
    markers: list[_Marker],
    sourcetexts_root: Path | None = None,
) -> list[Parsha]:

    # Group markers by parshah, in the order the parshiyot appear.
    parshiyot: list[Parsha] = []
    by_slug: dict[str, Parsha] = {}
    grouped: dict[str, list[_Marker]] = {}
    for marker in markers:
        name = marker.params.get("ב0")
        if not name:
            continue
        slug = slug_for_hebrew(name)
        parsha = by_slug.get(slug)
        if parsha is None:
            parsha = Parsha(slug=slug, hebrew_name=name, book=marker.ref.book, start=marker.ref)
            by_slug[slug] = parsha
            parshiyot.append(parsha)
            grouped[slug] = []
        grouped[slug].append(marker)

    # A parshah runs to the verse before the next one starts, or to the end of its book.
    for index, parsha in enumerate(parshiyot):
        following = parshiyot[index + 1] if index + 1 < len(parshiyot) else None
        if following is not None and following.book == parsha.book:
            parsha.end = previous_verse(following.start, sourcetexts_root)
        else:
            parsha.end = _end_of_book(parsha.book, sourcetexts_root)

    for parsha in parshiyot:
        parsha.spans = _spans_for(
            grouped[parsha.slug], parsha.end, SINGLE_DIVISION, sourcetexts_root
        )
    return parshiyot


def _parse_combined(
    markers: list[_Marker],
    parshiyot: list[Parsha],
    sourcetexts_root: Path | None = None,
) -> list[CombinedParsha]:
    """Build the combined readings out of the ``ג`` parameters of the same markers.

    The pair's extent is taken from its two members rather than from the markers, so that it
    ends where the second parshah ends even though the last marker falls before that.
    """
    by_slug = {parsha.slug: parsha for parsha in parshiyot}
    grouped: dict[str, list[_Marker]] = {}
    order: list[str] = []
    for marker in markers:
        name = marker.params.get("ג0")
        if not name:
            continue
        slug = slug_for_combined_hebrew(name)
        if slug not in grouped:
            grouped[slug] = []
            order.append(slug)
        grouped[slug].append(marker)

    combined: list[CombinedParsha] = []
    for slug in order:
        first_slug, second_slug = PAIR_MEMBERS[slug]
        first, second = by_slug[first_slug], by_slug[second_slug]
        pair = CombinedParsha(
            slug=slug,
            hebrew_name=grouped[slug][0].params["ג0"],
            book=first.book,
            members=(first_slug, second_slug),
            start=first.start,
            end=second.end,
        )
        pair.spans = _spans_for(grouped[slug], pair.end, COMBINED_DIVISION, sourcetexts_root)
        combined.append(pair)
    return combined


def _spans_for(
    markers: list[_Marker],
    reading_end: VerseRef,
    division: _Division,
    sourcetexts_root: Path | None,
) -> list[ReadingSpan]:
    """Close each unit-space's markers into spans independently of the others."""
    aliyah_starts: list[tuple[str, VerseRef, str | None]] = []
    weekday_starts: list[tuple[str, VerseRef, str | None]] = []
    weekday_end: VerseRef | None = None
    maftir_start: VerseRef | None = None

    for marker in markers:
        params = marker.params
        aliyah = params.get(division.aliyah_key)
        if aliyah in ALIYAH_NUMBER:
            aliyah_starts.append((ALIYAH_NUMBER[aliyah], marker.ref, None))
        honour = params.get(division.weekday_key)
        if honour in WEEKDAY_NUMBER:
            weekday_starts.append((WEEKDAY_NUMBER[honour], marker.ref, None))
        elif honour == WEEKDAY_END:
            # "Thus far Yisrael" marks where the weekday reading stops, so the last weekday
            # aliyah ends at the preceding verse rather than running on to the reading's end.
            weekday_end = previous_verse(marker.ref, sourcetexts_root)
        if params.get(division.maftir_key) == MAFTIR:
            maftir_start = marker.ref

    spans = _close_spans(aliyah_starts, division.aliyah_unit, reading_end, sourcetexts_root)
    spans += _close_spans(
        weekday_starts, division.weekday_unit, weekday_end or reading_end, sourcetexts_root
    )
    if maftir_start is not None:
        # The maftir runs to the end of the reading, overlapping the seventh aliyah.
        spans.append(
            ReadingSpan(division.maftir_unit, MAFTIR, maftir_start, reading_end)
        )
    return spans
