"""Turn overlapping reading divisions into a linear sequence of milestones and transclusions.

The humash contributes structure over text it does not hold: every word is transcluded from
the Tanakh projects by URN. The problem this module solves is that the divisions overlap, in
two different ways, which need two different answers.

**Between unit-spaces.** The maftir begins inside the seventh aliyah, the weekday aliyot
subdivide the Shabbat ones, and the triennial breaks cut across the annual ones. Here the text
is read once and marked several ways, so the spans are cut at the *union* of all their
boundaries and the text emitted once, with every milestone that falls at a point placed
before the segment starting there. A printed humash marks maftir in the margin of the seventh
aliyah; it does not print those verses twice.

**Within one unit-space.** On weekday Rosh Hodesh, Numbers 28:1-15 divides kohen 28:1-3, levi
28:3-5, yisrael 28:6-10, revi'i 28:11-15 — 28:3 belongs to both kohen and levi and really is
read twice. Cutting at the union cannot express that, so a unit-space whose own spans overlap
is emitted span by span and the shared verses are transcluded twice.

A festival reading may also leave one stretch of a book for another: on the sixth day of
Hanukkah the Rosh Hodesh aliyot, Numbers 28:1-15, are followed by Numbers 7:42-47. Cut at the
union, the verses between the two would be printed as though they were read, so
build.festival_file cuts such a reading into runs, each read without a break, segments each run
by itself in the order it is read, and `mark_repeats` then decides over the whole reading which
text is read again.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from opensiddur.importer.humash.refs import (
    UNIT_MAFTIR,
    ReadingSpan,
    VerseRef,
    previous_verse,
    verses_in_chapter,
)


@dataclass
class Segment:
    """A stretch of text to transclude, and the milestones that open at its start."""

    start: VerseRef
    end: VerseRef
    opening: list[ReadingSpan] = field(default_factory=list)
    # Set when this segment repeats text already emitted: by `segment_by_span` where two spans
    # of one unit-space overlap, and by `mark_repeats` over a whole festival reading.
    duplicate: bool = False

    @property
    def target(self) -> str:
        return self.start.range_urn(self.end)


def next_verse(
    ref: VerseRef,
    sourcetexts_root: Path | None = None,
) -> VerseRef:
    """The verse after `ref`, stepping into the next chapter at a chapter end."""
    if ref.verse < verses_in_chapter(ref.book, ref.chapter, sourcetexts_root):
        return VerseRef(ref.book, ref.chapter, ref.verse + 1)
    return VerseRef(ref.book, ref.chapter + 1, 1)


def has_internal_overlap(spans: list[ReadingSpan]) -> bool:
    """Whether any two spans of the same unit-space overlap each other."""
    by_unit: dict[str, list[ReadingSpan]] = {}
    for span in spans:
        by_unit.setdefault(span.unit, []).append(span)
    for unit_spans in by_unit.values():
        ordered = sorted(unit_spans, key=lambda span: (span.start, span.end))
        for earlier, later in zip(ordered, ordered[1:]):
            if later.start <= earlier.end:
                return True
    return False


def segment_by_union(
    spans: list[ReadingSpan],
    start: VerseRef,
    end: VerseRef,
    sourcetexts_root: Path | None = None,
) -> list[Segment]:
    """Cut `start`-`end` at every span boundary, emitting the text once.

    Each span's start opens a segment; each span's end closes one, so that a span which ends
    before the next one begins does not swallow the gap.
    """
    if end < start:
        raise ValueError(f"Cannot segment an empty range: {start} to {end}")

    boundaries: set[VerseRef] = {start}
    for span in spans:
        if start <= span.start <= end:
            boundaries.add(span.start)
        if start <= span.end < end:
            boundaries.add(next_verse(span.end, sourcetexts_root))

    ordered = sorted(boundaries)
    segments: list[Segment] = []
    for index, boundary in enumerate(ordered):
        segment_end = (
            previous_verse(ordered[index + 1], sourcetexts_root)
            if index + 1 < len(ordered)
            else end
        )
        if segment_end < boundary:
            continue
        segments.append(Segment(
            start=boundary,
            end=segment_end,
            opening=[span for span in spans if span.start == boundary],
        ))
    return segments


def segment_by_span(spans: list[ReadingSpan]) -> list[Segment]:
    """Emit each span as its own segment, in reading order, duplicating shared text.

    Used where a unit-space's own spans overlap and the shared verses genuinely are read
    twice, so cutting at the union would lose a verse from the second reading.
    """
    segments: list[Segment] = []
    covered: list[tuple[VerseRef, VerseRef]] = []
    for span in spans:
        duplicate = any(
            span.start <= seen_end and seen_start <= span.end
            for seen_start, seen_end in covered
        )
        segments.append(Segment(
            start=span.start, end=span.end, opening=[span], duplicate=duplicate
        ))
        covered.append((span.start, span.end))
    return segments


def overlapping_units(spans: list[ReadingSpan]) -> list[str]:
    """The unit-spaces whose own spans overlap each other."""
    by_unit: dict[str, list[ReadingSpan]] = {}
    for span in spans:
        by_unit.setdefault(span.unit, []).append(span)
    overlapping: list[str] = []
    for unit, unit_spans in by_unit.items():
        ordered = sorted(unit_spans, key=lambda span: (span.start, span.end))
        if any(later.start <= earlier.end for earlier, later in zip(ordered, ordered[1:])):
            overlapping.append(unit)
    return overlapping


def segment_reading(
    spans: list[ReadingSpan],
    start: VerseRef | None = None,
    end: VerseRef | None = None,
    sourcetexts_root: Path | None = None,
    allow_duplication: bool = True,
) -> list[Segment]:
    """Segment a reading, choosing the strategy its spans call for.

    With `allow_duplication`, spans that overlap inside one unit-space are emitted one by one
    so that the repeated verses survive — right for a short festival reading, where the whole
    of it is a handful of verses and the kohen and levi of weekday Rosh Hodesh really do share
    Numbers 28:3.

    Without it the text is always emitted once. A continuous reading passes False: a single
    overlapping pair anywhere would otherwise duplicate the entire parshah, and one triennial
    aliyah whose marked scope stops early is a far smaller loss than a parshah printed three
    times over.
    """
    if not spans:
        return []
    if allow_duplication and has_internal_overlap(spans):
        return segment_by_span(spans)
    start = start if start is not None else min(span.start for span in spans)
    end = end if end is not None else max(span.end for span in spans)
    return segment_by_union(spans, start, end, sourcetexts_root)


# readings.festival_readings labels the maftirs that hebcal keys by day, "M-day1" to "M-day5",
# maftir_day1 to maftir_day5.
DAY_MAFTIR_PREFIX = "maftir_day"


def are_alternatives(first: ReadingSpan, second: ReadingSpan) -> bool:
    """Whether two spans are alternatives for one place in a reading, only one of them read.

    The maftir of Shabbat Chol HaMoed Sukkot depends on which intermediate day the Shabbat falls
    on, and hebcal gives all five. Their verses overlap, but a congregation reads one of them,
    so none of them reads another again.
    """
    return (
        first.unit == second.unit == UNIT_MAFTIR
        and first.label != second.label
        and first.label.startswith(DAY_MAFTIR_PREFIX)
        and second.label.startswith(DAY_MAFTIR_PREFIX)
    )


def mark_repeats(segments: list[Segment]) -> list[Segment]:
    """Flag each of `segments`, given in reading order, that reads again text emitted before it.

    `segment_by_span` flags the repeats among the spans it is given. A festival reading is
    segmented a run at a time (build._reading_runs), and a later run may read again what an
    earlier one read, so the flag is decided here over the whole reading. Segments opened by
    spans that are alternatives to one another (`are_alternatives`) do not repeat each other.
    """
    for index, segment in enumerate(segments):
        segment.duplicate = any(
            earlier.start.book == segment.start.book
            and earlier.start <= segment.end
            and segment.start <= earlier.end
            and not any(
                are_alternatives(mine, theirs)
                for mine in segment.opening
                for theirs in earlier.opening
            )
            for earlier in segments[:index]
        )
    return segments
