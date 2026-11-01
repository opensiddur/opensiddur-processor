"""Emit the humash project: structure over text transcluded from the Tanakh projects.

Every word of Torah, haftarah and megillah text is transcluded by URN. The only original
content is the headings and the reading instructions, so nothing here duplicates a text that
already exists in another project.

Targets carry no ``@project`` suffix, so which edition supplies the text is decided at compile
time by ``priority.transclusion``. Every range is stated in the canonical verse division that
the bible URN space uses (opensiddur.common.versification), so one range serves every edition;
the sources are converted to it as they are read.

The conditionals this emits
===========================

Four kinds, each on a feature the compiler decides from the volume's declarations. A feature
left undeclared is undefined, and undefined keeps the text it guards, so a volume that
declares nothing carries every variant. See ``doc/humash-settings.example.yaml`` for how a
volume narrows them.

``opensiddur:rite`` (binary, `_conditional`)
    The haftarah of a rite whose custom differs. **Not exclusive**: several rites may be
    declared true at once, and a volume that declares none prints them all, each under a
    heading naming whose custom it is.

``opensiddur:holiday`` (binary, `_conditional`)
    A megillah, on the festival it is read. The feature is a day number, and a binary
    condition reads it as true on any day of the festival. Exclusive per occasion — one
    date makes at most one true — but nothing stops a volume declaring several, and one
    that declares none carries all five.

``opensiddur:reading-cycle`` (binary, `_cycle_condition`)
    ``annual`` and ``triennial-year-{1,2,3}``, guarding haftarot. **Alternatives, not
    additions**: the four haftarot of one Shabbat are the same slot read four ways, so a
    volume that declares several prints several for that week. Each test is a single feature
    (see `_cycle_condition`) so that the answer is decisive rather than undefined.

``opensiddur:torah-reading`` / ``triennial-pattern-{pair}`` (string, `_pattern_conditional`)
    The triennial aliyah divisions of each single inside a pair that is sometimes read
    combined. The feature's value is one character per year of the cycle — ``T`` where the
    pair was read together, ``S`` where apart — and `readings.triennial_patterns` maps each
    such string to exactly one variation. **Exclusive for any one cycle, but not in a printed
    book**: the pattern sets guarding different variations of one pair are disjoint, so a
    volume that declares a cycle keeps exactly one variation's markers — but a volume that
    declares none keeps them all, and a printed humash declares none, so that it serves the
    whole cycle. Do not read the disjointness as licence to show only one.

    So the same division name legitimately appears at two different verses of one pair: in
    Behar–Bechukotai year A's fourth aliyah begins at 25:11 under a cycle that reads the pair
    apart in years A and C, and at 25:14 under one that reads it apart in year A alone. The
    reader has to be told which is which, and the condition cannot tell them — the exporter
    does not print it (see ``f:governs-markers-only`` in ``exporter/tex/reledmac.xslt``). The
    marker's own label carries it instead: `_cycle_qualifier` names the years that read the
    pair apart, which identifies the cycle because the set of those years and the pattern
    determine one another.

    The combined reading's own divisions are unconditioned, which is why a marker suffixed
    ``(מְחֻבָּרוֹת)`` can sit beside an unsuffixed one at the same verse: the two are the
    same aliyah of two different readings that happen to begin together.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from pathlib import Path

from opensiddur.common.versification import MIQRA_PROJECT
from opensiddur.importer.util.tei_project import validate_and_write
from opensiddur.importer.humash import model
from opensiddur.importer.humash.aliyot import CombinedParsha, Parsha, parse_readings
from opensiddur.importer.humash.festival_names import hebrew_name
from opensiddur.importer.humash.names import (
    PAIR_FOR_MEMBER,
    PAIR_MEMBERS,
    SLUG_TO_HEBREW,
    slugify_reading_name,
    vocalized_name,
)
from opensiddur.importer.humash.readings import (
    REPEATED_VERSE_INSTRUCTION,
    Passage,
    festival_readings,
    haftarot,
    triennial,
    triennial_haftarot,
    triennial_patterns,
)
from opensiddur.importer.humash.refs import (
    MEGILLOT,
    SLUG_TO_HEBREW_ANY_BOOK,
    SLUG_TO_VOCALIZED_BOOK,
    TORAH_BOOKS,
    UNIT_ALIYAH,
    UNIT_ALIYAH_COMBINED,
    UNIT_MAFTIR,
    UNIT_MAFTIR_COMBINED,
    UNIT_PARSHA,
    UNIT_PARSHA_COMBINED,
    UNIT_TRIENNIAL,
    UNIT_WEEKDAY,
    UNIT_WEEKDAY_COMBINED,
    VARIATION_COMBINED,
    ReadingSpan,
    VerseRef,
    chapters_in_book,
    next_verse,
    verses_in_chapter,
)

logger = logging.getLogger(__name__)

PROJECT = "chumash-opensiddur-he"
URN_PREFIX = "urn:x-opensiddur:text:bible"

TEI_NS = "http://www.tei-c.org/ns/1.0"
J_NS = "http://jewishliturgy.org/ns/jlptei/2"

# What each unit-space is called in the margin.
UNIT_TITLES = {
    UNIT_ALIYAH: "עלייה",
    UNIT_WEEKDAY: "עליית חול",
    UNIT_MAFTIR: "מפטיר",
    UNIT_TRIENNIAL: "מחזור תלת־שנתי",
    UNIT_ALIYAH_COMBINED: "עלייה (מחוברות)",
    UNIT_WEEKDAY_COMBINED: "עליית חול (מחוברות)",
    UNIT_MAFTIR_COMBINED: "מפטיר (מחוברות)",
}

ALIYAH_TITLES = {
    "1": "רִאשׁוֹן", "2": "שֵׁנִי", "3": "שְׁלִישִׁי", "4": "רְבִיעִי",
    "5": "חֲמִישִׁי", "6": "שִׁשִּׁי", "7": "שְׁבִיעִי", "maftir": "מַפְטִיר",
    "מפטיר": "מַפְטִיר",
}

WEEKDAY_TITLES = {"1": "כֹּהֵן", "2": "לֵוִי", "3": "יִשְׂרָאֵל"}

# Sukkot's Chol HaMoed Shabbat maftir varies by which intermediate day it falls on
# ("maftir_day1".."maftir_day5"). Latin/digits here would be reversed when set in the
# surrounding right-to-left text, same as TRIENNIAL_YEARS below, so days are spelled out
# as Hebrew letters rather than left as the raw source label.
MAFTIR_DAY_LETTERS = {1: "א׳", 2: "ב׳", 3: "ג׳", 4: "ד׳", 5: "ה׳"}


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _header(title_he: str, title_en: str, urn_suffix: str) -> str:
    """A leaf header, deferring version and source information to the project index."""
    index_urn = f"{URN_PREFIX}:chumash@{PROJECT}"
    return f"""<tei:teiHeader>
  <tei:fileDesc>
    <tei:titleStmt>
      <tei:title type="main" xml:lang="he">{_escape(title_he)}</tei:title>
      <tei:title type="alt" xml:lang="en">{_escape(title_en)}</tei:title>
    </tei:titleStmt>
    <tei:editionStmt>
      <tei:p>See <tei:ref target="{index_urn}">the humash project header for version information</tei:ref>.</tei:p>
    </tei:editionStmt>
    <tei:publicationStmt>
      <tei:distributor>
        <tei:ref target="http://opensiddur.org">Open Siddur Project</tei:ref>
      </tei:distributor>
      <tei:idno type="urn">{URN_PREFIX}:{urn_suffix}@{PROJECT}</tei:idno>
      <tei:availability status="free">
        <tei:licence target="http://www.creativecommons.org/publicdomain/zero/1.0/">Creative Commons Zero Public Domain Declaration (CC0)</tei:licence>
      </tei:availability>
    </tei:publicationStmt>
    <tei:sourceDesc>
      <tei:p>See <tei:ref target="{index_urn}">the humash project header for source information</tei:ref>.</tei:p>
    </tei:sourceDesc>
  </tei:fileDesc>
</tei:teiHeader>"""


def _document(header: str, body: str, lang: str = "he", front: str = "") -> str:
    front_element = f"<tei:front>{front}</tei:front>" if front else ""
    return (
        f'<tei:TEI xmlns:tei="{TEI_NS}" xmlns:j="{J_NS}" xml:lang="{lang}">'
        f'{header}<tei:text xml:lang="{lang}">{front_element}'
        f"<tei:body>{body}</tei:body></tei:text></tei:TEI>"
    )


# Cycle years, as the marker names them. Latin or digits here would be reversed when set in
# the surrounding right-to-left text, which is how "1.maftir" comes out as "ritfam.1".
TRIENNIAL_YEARS = {1: "א׳", 2: "ב׳", 3: "ג׳"}

# What the margin says of a division that belongs to the pair read together, so that it is not
# mistaken for the same-numbered aliyah of either single, which is beside it in the same file.
COMBINED_SUFFIX = "מְחֻבָּרוֹת"

# What the prophetic reading of a festival or special Shabbat is headed.
HAFTARAH_TITLE = "הַפְטָרָה"


# What the margin says of a division that belongs to one shape of the cycle: which years of it
# read the pair apart. Naming those years names the cycle, because the set of them and the
# combine/separate pattern determine one another.
SEPARATE_PREFIX = "נִפְרָדוֹת"
ALL_YEARS_SEPARATE = "בְּכָל הַשָּׁנִים"
# Between the shapes of the cycle that divide the parshah the same way. A comma would read as
# another year in the list of years each shape already is. Not a middle dot: Frank Ruehl CLM has
# no glyph for one, and a character the Hebrew font lacks is set as a blank.
SHAPE_SEPARATOR = "; "
# A year's divisions exist only in the shapes that read the pair apart that year, so every shape
# in play already reads it apart then. What is left to say is whether it is read apart that year
# and no other, or that year and at least one more — which is the whole distinction wherever a
# division falls in just two places, and shorter than naming three shapes to say it.
ONLY_THAT_YEAR = "בִּלְבַד"
THAT_YEAR_AND_MORE = "וְעוֹד"


def _shape_name(pattern: str) -> str:
    """One shape of the cycle, named by the years that read the pair apart.

    A pattern is one character per year, ``T`` where the pair was read together and ``S`` where
    apart, so the ``S`` positions are the years the single is read on its own and has divisions
    of its own. Naming those years names the shape, because the set of them and the pattern
    determine one another.
    """
    years = [index + 1 for index, char in enumerate(pattern) if char == "S"]
    if len(years) == len(TRIENNIAL_YEARS):
        return ALL_YEARS_SEPARATE
    named = [TRIENNIAL_YEARS.get(year, str(year)) for year in years]
    if len(named) > 1:
        # "א׳ וְג׳" — the conjunction is vocalized for the letter it precedes.
        vav = "וּ" if named[-1].startswith(("ב", "ו")) else "וְ"
        named = [*named[:-1], f"{vav}{named[-1]}"]
    return " ".join(named)


def _cycle_qualifier(patterns: set[str], year: int, universe: set[str]) -> str:
    """Every shape of the cycle that opens a division at one place, as the margin says it.

    Several shapes often divide a parshah the same way, and where they do they are one marker
    to the reader, not several: they are named together so that the label is identical and the
    exporter sets it once. Where they divide it differently the labels differ, which is the
    whole point — that is how a reader meeting the name twice knows which is theirs.

    `universe` is every shape that has this division at all, which is every shape reading the
    pair apart in `year`. Against that, a group is most often "this year alone" or its opposite,
    and saying so is much shorter than naming the three shapes the opposite covers. Groups that
    are neither are named by listing them.
    """
    alone = {
        pattern for pattern in universe
        if [index for index, char in enumerate(pattern) if char == "S"] == [year - 1]
    }
    named_year = TRIENNIAL_YEARS.get(year, str(year))
    if alone and patterns == alone:
        return f"{SEPARATE_PREFIX} {named_year} {ONLY_THAT_YEAR}"
    if alone and patterns == universe - alone:
        return f"{SEPARATE_PREFIX} {named_year} {THAT_YEAR_AND_MORE}"
    shapes = sorted({_shape_name(pattern) for pattern in patterns})
    return f"{SEPARATE_PREFIX} {SHAPE_SEPARATOR.join(shapes)}"


def _triennial_title(label: str, qualifier: str | None = None) -> str:
    """The margin text of a triennial marker.

    Labels are "<year>.<aliyah>", or "<variation>.<year>.<aliyah>" for a parshah that is
    sometimes read combined. The variation letter itself is never printed — it would say
    nothing to a reader — but where the marker is conditional on the shape of the cycle, the
    qualifier names that shape, so a reader meeting the same division name at two verses can
    tell which one is theirs. Only a volume that declares no cycle sees more than one of them.
    The combined reading is called out, because it sits beside the singles in the same file.
    """
    parts = label.split(".")
    variation = parts[0] if len(parts) == 3 else None
    year, aliyah = parts[-2], parts[-1]
    title = f"{TRIENNIAL_YEARS.get(int(year), year)} {ALIYAH_TITLES.get(aliyah, aliyah)}"
    if variation == VARIATION_COMBINED:
        return f"{title} ({COMBINED_SUFFIX})"
    if qualifier:
        return f"{title} ({qualifier})"
    return title


def _milestone_title(span: ReadingSpan, qualifier: str | None = None) -> str:
    label = span.label
    if span.unit == UNIT_ALIYAH:
        return ALIYAH_TITLES.get(label, label)
    if span.unit == UNIT_WEEKDAY:
        return WEEKDAY_TITLES.get(label, label)
    if span.unit == UNIT_MAFTIR:
        if label.startswith("maftir_day"):
            day = int(label[len("maftir_day"):])
            return f"{ALIYAH_TITLES['maftir']} לְיוֹם {MAFTIR_DAY_LETTERS[day]}"
        return ALIYAH_TITLES["maftir"]
    if span.unit in (UNIT_PARSHA, UNIT_PARSHA_COMBINED):
        return vocalized_name(label)
    if span.unit == UNIT_ALIYAH_COMBINED:
        return f"{ALIYAH_TITLES.get(label, label)} ({COMBINED_SUFFIX})"
    if span.unit == UNIT_WEEKDAY_COMBINED:
        return f"{WEEKDAY_TITLES.get(label, label)} ({COMBINED_SUFFIX})"
    if span.unit == UNIT_MAFTIR_COMBINED:
        return f"{ALIYAH_TITLES['maftir']} ({COMBINED_SUFFIX})"
    if span.unit.startswith("aliyah.triennial") or span.unit.startswith("maftir.triennial"):
        # Labels arrive as "<year>.<aliyah>" or "<variation>.<year>.<aliyah>".
        return _triennial_title(label, qualifier)
    return label


def _milestone(span: ReadingSpan, urn_base: str, qualifier: str | None = None) -> str:
    """The marker that opens a reading division. Its scope runs to the next of the same unit.

    `qualifier` names the shape of cycle this division belongs to, and is set only for a marker
    that a condition guards — the triennial divisions of a single inside a pair's file.
    """
    title = _milestone_title(span, qualifier)
    if span.unit in (UNIT_PARSHA, UNIT_PARSHA_COMBINED):
        # A parshah's own URN, not one below the file's: inside a combined file the marker for
        # each single is what makes urn:...:parsha/<slug> resolve to that single's text.
        urn = f"{URN_PREFIX}:parsha/{span.label}"
        if urn == urn_base:
            # A parshah read alone: the file's own div already carries this URN and covers
            # exactly the same text. Naming it twice maps one URN to two places, which is
            # what a text URN may not do — it is the join key the parallel compiler and the
            # reference database resolve by. The marker still opens the division; it just
            # does not claim the name.
            return f'<tei:milestone unit="{span.unit}" n="{_escape(title)}"/>'
    else:
        base = f"{URN_PREFIX}:parsha/{span.owner}" if span.owner else urn_base
        urn = f"{base}/{_division_path(span, base.rsplit('/', 1)[-1])}"
    return (
        f'<tei:milestone unit="{span.unit}" n="{_escape(title)}" corresp="{urn}"/>'
    )


def _division_path(span, parsha: str) -> str:
    """The path that names a division below its parshah or reading.

    A triennial division is named by its cycle, year and aliyah: ``triennial/2/1``,
    ``triennial/c/2/1`` (a cycle of a pair), ``triennial/combined/1/maftir``. The unit names the
    parshah again where a pair's file holds a single's divisions, and the path need not. Any
    other division is named by its unit and its number, ``aliyah_annual/1``; a maftir by
    ``maftir``, not the label it is printed with.
    """
    parts = span.unit.split(".")
    if parts[1:2] == ["triennial"]:
        rest = parts[2:]
        if len(rest) > 1 and rest[0] == parsha:
            rest = rest[1:]
        return "/".join(["triennial", *(p.lower() for p in rest), span.label.split(".")[-1]])
    label = "maftir" if span.label == "מפטיר" else slugify_reading_name(span.label)
    if not label:
        raise ValueError(f"the label {span.label!r} of {span.unit} has no name to put in a URN")
    return f"{span.unit.replace('.', '_')}/{label}"


def _transclude(target: str) -> str:
    return f'<j:transclude type="external" target="{target}"/>'


def _instruction(text: str) -> str:
    return f'<tei:note type="instruction" xml:lang="he">{_escape(text)}</tei:note>'


def _verse_citation(ref: VerseRef) -> str:
    """"<chapter>:<verse>", with the half after it where the reading names one — "2:2b"."""
    return f"{ref.chapter}:{ref.verse}{ref.half or ''}"


def _citation_range(book: str, start: VerseRef, end: VerseRef) -> str:
    """"<book> <chapter>:<verse>[–<chapter>:<verse>]" for one contiguous range."""
    book_he = SLUG_TO_HEBREW_ANY_BOOK.get(book, book)
    start_ref = _verse_citation(start)
    end_ref = _verse_citation(end)
    return f"{book_he} {start_ref if start == end else f'{start_ref}–{end_ref}'}"


def _citation(spans: list[ReadingSpan]) -> str:
    """A citation for a passage's spans, in reading order: one clause per span, joined by
    "; ". Only the first span of a run in one book states the book name; a passage that
    bridges books (readings.Passage) or backtracks within one (Mishpatim's haftarah) states
    it again wherever the book changes.
    """
    clauses: list[str] = []
    prev_book: str | None = None
    for span in spans:
        if span.book == prev_book:
            start_ref = _verse_citation(span.start)
            end_ref = _verse_citation(span.end)
            clauses.append(start_ref if span.start == span.end else f"{start_ref}–{end_ref}")
        else:
            clauses.append(_citation_range(span.book, span.start, span.end))
        prev_book = span.book
    return "; ".join(clauses)


def _citation_milestone(text: str) -> str:
    return f'<tei:milestone unit="citation" n="{_escape(text)}"/>'


def _is_contiguous(
    prev: ReadingSpan, following: ReadingSpan, sourcetexts_root: Path | None,
) -> bool:
    """Whether `following` picks up exactly where `prev` left off: same book, and its first
    verse is the one right after `prev`'s last. False for a backward jump, a skip ahead, or
    a change of book — see readings.Passage."""
    if prev.book != following.book:
        return False
    # A span that stops at the etnachta runs straight on into one that starts there.
    if prev.end.half == "a" and following.start == replace(prev.end, half="b"):
        return True
    return next_verse(prev.end.whole_verse, sourcetexts_root) == following.start


_CONDITION_INDEX = {"value": 0}


def _condition_id(prefix: str) -> str:
    _CONDITION_INDEX["value"] += 1
    return f"{prefix}_{_CONDITION_INDEX['value']}"


def _conditional(feature_type: str, feature: str, content: str, prefix: str) -> str:
    """Wrap `content` in a condition on one binary feature being true."""
    identifier = _condition_id(prefix)
    return (
        f'<j:conditional xml:id="{identifier}">'
        f'<tei:fs type="{feature_type}"><tei:f name="{feature}">'
        f'<tei:binary value="true"/></tei:f></tei:fs>'
        f"</j:conditional>{content}"
        f'<j:endConditional target="#{identifier}"/>'
    )


TRIENNIAL_PATTERN_FEATURE = "triennial-pattern-{pair}"


def _pattern_conditional(pair_slug: str, patterns: list[str], content: str) -> str:
    """Wrap `content` so it survives only in a cycle with one of these combine/separate patterns.

    ``opensiddur:torah-reading`` carries one pattern feature per pair, derived from the date.
    With no date declared the feature is undefined and every variation is kept, the way
    leaving ``opensiddur:rite`` unset keeps every rite's haftarah.
    """
    identifier = _condition_id("triennial")
    feature = TRIENNIAL_PATTERN_FEATURE.format(pair=pair_slug.replace("_", "-"))
    alternatives = "".join(
        f'<tei:fs type="opensiddur:torah-reading"><tei:f name="{feature}">'
        f"<tei:string>{pattern}</tei:string></tei:f></tei:fs>"
        for pattern in sorted(patterns)
    )
    return (
        f'<j:conditional xml:id="{identifier}"><j:any>{alternatives}</j:any></j:conditional>'
        f"{content}"
        f'<j:endConditional target="#{identifier}"/>'
    )


# Which readings the volume carries: `annual`, and one feature per year of the triennial cycle.
# All are false by default but `annual`, and several may be true at once, so one volume may be
# for a single Shabbat and another for a whole cycle. See exporter/calendar/compute.py.
CYCLE_FS = "opensiddur:reading-cycle"
ANNUAL_FEATURE = "annual"
CYCLE_YEARS = tuple(TRIENNIAL_YEARS)


def _cycle_condition(feature: str) -> str:
    """The test for one reading-cycle feature being true.

    Always a single feature, so that the answer is decisive. ``j:all`` over a false test and an
    undefined one is undefined per the truth tables, and undefined keeps the text it guards —
    which for readings that are alternatives to one another would print several at once.
    """
    return (
        f'<tei:fs type="{CYCLE_FS}"><tei:f name="{feature}">'
        f'<tei:binary value="true"/></tei:f></tei:fs>'
    )


def _triennial_year_feature(year: int) -> str:
    return f"triennial-year-{year}"


def _segment_xml(
    segment: model.Segment,
    urn_base: str,
    sourcetexts_root: Path | None,
    conditions: Conditions | None = None,
) -> str:
    """Milestones opening at this segment, then the text itself.

    `conditions` maps a unit-space to the pair and patterns its markers depend on. Each marker
    is wrapped on its own rather than the whole division at once, since the markers of a
    division are spread through the text they divide.
    """
    parts: list[str] = []
    for span in segment.opening:
        condition = (conditions or {}).get(span.unit)
        # A conditioned marker names the shapes of the cycle it is for, since a volume that
        # declares none keeps every variation and the division name alone would not tell them
        # apart. Where every shape divides alike there is nothing to tell apart and no name.
        marker = _milestone(span, urn_base, condition[2] if condition is not None else None)
        parts.append(
            _pattern_conditional(condition[0], condition[1], marker)
            if condition is not None else marker
        )
    if segment.duplicate:
        parts.append(_instruction("חוזרים על הפסוק"))
    parts.append(_transclude(segment.start.range_urn(segment.end)))
    return "".join(parts)


TriennialDivisions = dict[tuple[str | None, int], list[ReadingSpan]]

#: A marker's unit-space, the pair its condition names, the patterns that select it, and the
#: text the label adds to say which shapes of the cycle it is for (None when every shape agrees).
Conditions = dict[str, tuple[str, list[str], str | None]]


def _division_key(span: ReadingSpan) -> tuple[str | None, str, str]:
    """What makes two markers the same division to a reader: same parshah, year and aliyah,
    opening at the same verse. The variation is left out — that is what varies."""
    year, aliyah = span.label.split(".")[-2:]
    return (span.owner, f"{year}.{aliyah}", str(span.start))


def _qualifiers_by_division(
    divisions: TriennialDivisions, patterns: dict[str, str]
) -> dict[tuple[str | None, str, str], str]:
    """What each division's marker adds to say which shapes of the cycle it is for.

    Shapes often divide a parshah alike, and a reader has no use for the distinction where they
    do. Grouping by where a division actually opens lets those shapes share one label, so the
    exporter sets one marker rather than three; and a division that every shape opens in the
    same verse is left out entirely, since there is nothing there to tell apart. Only the
    divisions that really do fall in more than one place are qualified, which is where the
    reader needs it.
    """
    by_key: dict[tuple[str | None, str, str], set[str]] = {}
    places: dict[tuple[str | None, str], set[str]] = {}
    for (variation, _year), division in divisions.items():
        shapes = {pattern for pattern, name in patterns.items() if name == variation}
        if variation is None or not shapes:
            continue
        for span in division:
            key = _division_key(span)
            by_key.setdefault(key, set()).update(shapes)
            places.setdefault(key[:2], set()).add(key[2])
    universes: dict[tuple[str | None, str], set[str]] = {}
    for key, shapes in by_key.items():
        universes.setdefault(key[:2], set()).update(shapes)
    return {
        key: _cycle_qualifier(shapes, int(key[1].split(".")[0]), universes[key[:2]])
        for key, shapes in by_key.items()
        if len(places[key[:2]]) > 1
    }


def _reading_document(
    slug: str,
    hebrew: str,
    spans: list[ReadingSpan],
    start: VerseRef,
    end: VerseRef,
    conditions: Conditions | None,
    sourcetexts_root: Path | None,
) -> tuple[str, str]:
    """A parshah file: its heading, its reading divisions, and the text between them."""
    urn_base = f"{URN_PREFIX}:parsha/{slug}"

    # A parshah is one continuous reading, so it is always emitted once; see segment_reading.
    overlapping = model.overlapping_units(spans)
    if overlapping:
        logger.info(
            "%s: %s overlap themselves, so those milestones scope to the next marker rather "
            "than to their recorded end", slug, ", ".join(sorted(overlapping)),
        )

    segments = model.segment_reading(
        spans, start, end, sourcetexts_root, allow_duplication=False,
    )
    body_inner = "".join(
        _segment_xml(s, urn_base, sourcetexts_root, conditions) for s in segments
        )

    body = (
        f'<tei:div corresp="{urn_base}" n="{slug}">'
        f"<tei:head>{_escape(hebrew)}</tei:head>{body_inner}</tei:div>"
    )
    header = _header(hebrew, slug.replace("_", " ").title(), f"parsha/{slug}")
    return f"parashat_{slug}", _document(header, body)


def parsha_file(
    parsha: Parsha,
    triennial_divisions: TriennialDivisions,
    sourcetexts_root: Path | None = None,
) -> tuple[str, str]:
    """One weekly parshah, read on its own week."""
    spans = [parsha.parsha_span, *parsha.spans]
    for division in triennial_divisions.values():
        spans.extend(division)
    hebrew = vocalized_name(parsha.slug)
    return _reading_document(
        parsha.slug, hebrew, spans, parsha.start, parsha.end, None, sourcetexts_root
    )


def pair_file(
    pair: CombinedParsha,
    members: list[Parsha],
    triennial_divisions: dict[str, TriennialDivisions],
    patterns: dict[str, str],
    sourcetexts_root: Path | None = None,
) -> tuple[str, str]:
    """A pair that may be read together, holding both singles and the combined reading.

    The two are alternatives, not a whole and its parts, so they are separate unit-spaces over
    one copy of the text: the combined fourth aliyah runs through the point where the second
    parshah begins, and would be cut there if it were scoped by ``parsha.annual``.

    The combined divisions are unconditioned, so a volume carries the pair both ways. Each
    single's triennial divisions are not: which of them applies depends on how the pair fell
    in that cycle, and the condition says which cycles each is for.
    """
    spans = [pair.parsha_span]
    conditions: Conditions = {}
    for member in members:
        spans.append(member.parsha_span)
        # The singles' divisions keep their own URN space: both parshiyot have a first aliyah.
        spans.extend(replace(span, owner=member.slug) for span in member.spans)
        member_divisions = triennial_divisions.get(member.slug, {})
        qualifiers = _qualifiers_by_division(member_divisions, patterns)
        for (variation, _year), division in member_divisions.items():
            matching = sorted(
                pattern for pattern, name in patterns.items() if name == variation
            )
            if variation is not None and not matching:
                logger.warning(
                    "%s: no cycle pattern selects triennial variation %s, so its markers are "
                    "emitted unconditionally", member.slug, variation,
                )
            for span in division:
                if variation is not None and matching:
                    # Every shape that opens this division here, not just this variation's:
                    # shapes that divide alike are one marker to a reader, and giving them
                    # one label is what lets the exporter set it once. A division every shape
                    # opens in the same place needs no qualifier at all.
                    conditions[span.unit] = (
                        pair.slug, matching, qualifiers.get(_division_key(span))
                    )
            spans.extend(division)

    spans.extend(pair.spans)
    for division in triennial_divisions.get(pair.slug, {}).values():
        spans.extend(division)

    return _reading_document(
        pair.slug, vocalized_name(pair.slug), spans,
        pair.start, pair.end, conditions, sourcetexts_root,
    )


# hebcal states a few boundaries inside a verse — Emor's third year names Nachum 2:2b-2:3a —
# and a URN reaches no further than a whole verse. Every such reference in the data today is on
# an anchor verse that readings.triennial_haftarot drops, so nothing emits these yet; they are
# here because the alternative, if hebcal moves one into a span that is read, is to silently
# read half a verse too much.
HALF_VERSE_START_INSTRUCTION = "מתחילים מאמצע הפסוק"
HALF_VERSE_END_INSTRUCTION = "מסיימים באמצע הפסוק"


def _passage_xml(
    passage: Passage, urn_base: str, sourcetexts_root: Path | None = None,
) -> str:
    """A haftarah or megillah: its citation, its spans in order, then any repeated closing verse.

    A citation opens the passage, and another opens again at any span that does not pick up
    where the one before it left off — a backward jump, a skip ahead, or a change of book (see
    readings.Passage) — so the reading always states where it is even when it is discontinuous.
    """
    parts: list[str] = []
    if passage.spans:
        parts.append(_citation_milestone(_citation(passage.spans)))
    for i, span in enumerate(passage.spans):
        if i > 0 and not _is_contiguous(passage.spans[i - 1], span, sourcetexts_root):
            parts.append(_citation_milestone(_citation([span])))
        if span.start_half == "b":
            parts.append(_instruction(HALF_VERSE_START_INSTRUCTION))
        parts.append(_transclude(span.start.range_urn(span.end)))
        if span.end_half == "a":
            parts.append(_instruction(HALF_VERSE_END_INSTRUCTION))
    if passage.repeated is not None:
        parts.append(_instruction(REPEATED_VERSE_INSTRUCTION))
        parts.append(_transclude(
            passage.repeated.start.range_urn(passage.repeated.end)
        ))
    return "".join(parts)


# The heading over a triennial haftarah. Unlike the triennial Torah divisions, which are
# markers in the margin of the annual text, these are whole alternative readings.
TRIENNIAL_HAFTARAH_TITLE = "מַחֲזוֹר תְּלַת־שְׁנָתִי, שָׁנָה {year}"


def haftarah_file(
    slug: str,
    passages: list[Passage],
    triennial_passages: dict[int, Passage] | None = None,
    sourcetexts_root: Path | None = None,
) -> tuple[str, str]:
    """The haftarah of one parshah: the annual reading, and the triennial ones as alternatives.

    The annual haftarah has a division per rite where the rites differ. The triennial readings
    have none — hebcal records a single reading per cycle year — so each is one headed division
    conditioned on the volume reading that year of the cycle.

    They are alternatives for the same Shabbat, so the annual reading is kept when the volume
    asks for it and also whenever the volume's cycle year has nothing to put in its place.
    Tazria, Achrei Mot and Behar are read alone only in years 1 and 2 and so have no reading
    for year 3; a parshah with no triennial reading at all is unconditional, as are the pairs,
    which have no triennial haftarah of their own.

    This is the one place the humash decides rather than keeping every variant. A volume that
    asks for nothing gets the annual reading, not all four: they belong to one week, and
    printing four haftarot for it would be wrong however they were headed.
    """
    urn_base = f"{URN_PREFIX}:haftarah/{slug}"
    hebrew = vocalized_name(slug)
    title = f"הַפְטָרַת {hebrew}"

    annual: list[str] = []
    for passage in passages:
        content = _passage_xml(passage, urn_base, sourcetexts_root)
        if passage.rite is None:
            annual.append(content)
            continue
        variant = (
            f'<tei:div corresp="{urn_base}/{passage.rite}" n="{passage.rite}">'
            f"<tei:head>{_escape(passage.title or passage.rite)}</tei:head>"
            f"{content}</tei:div>"
        )
        annual.append(_conditional("opensiddur:rite", passage.rite, variant, "rite"))

    years = sorted(triennial_passages or {})
    inner = "".join(annual)
    if years:
        # The annual reading also stands in for the cycle years this parshah has none of, so a
        # triennial volume is never left with no haftarah at all for the week.
        missing = [year for year in CYCLE_YEARS if year not in years]
        identifier = _condition_id("annual_haftarah")
        alternatives = "".join(
            _cycle_condition(feature) for feature in
            [ANNUAL_FEATURE, *(_triennial_year_feature(year) for year in missing)]
        )
        inner = (
            f'<j:conditional xml:id="{identifier}"><j:any>{alternatives}</j:any>'
            f"</j:conditional>{inner}"
            f'<j:endConditional target="#{identifier}"/>'
        )
    for year in years:
        identifier = _condition_id("triennial_haftarah")
        year_title = TRIENNIAL_HAFTARAH_TITLE.format(year=TRIENNIAL_YEARS.get(year, year))
        division = (
            f'<tei:div corresp="{urn_base}/triennial/{year}" n="triennial_{year}">'
            f"<tei:head>{_escape(year_title)}</tei:head>"
            f"{_passage_xml(triennial_passages[year], urn_base, sourcetexts_root)}</tei:div>"
        )
        inner += (
            f'<j:conditional xml:id="{identifier}">'
            f"{_cycle_condition(_triennial_year_feature(year))}</j:conditional>"
            f"{division}"
            f'<j:endConditional target="#{identifier}"/>'
        )

    body = (
        f'<tei:div corresp="{urn_base}" n="haftarah_{slug}">'
        f"<tei:head>{_escape(title)}</tei:head>{inner}</tei:div>"
    )
    header = _header(title, f"Haftarah for {slug.replace('_', ' ').title()}", f"haftarah/{slug}")
    return f"haftarat_{slug}", _document(header, body)


def megillah_file(
    book: str,
    hebrew: str,
    holiday: str,
    sourcetexts_root: Path | None = None,
) -> tuple[str, str]:
    """One of the five megillot, read whole on its festival."""
    from opensiddur.importer.humash.readings import REPEATED_CLOSING_VERSES

    urn_base = f"{URN_PREFIX}:megillah/{book}"
    # Named as a range from the first verse to the last, not by the book's own URN. Every
    # project holding a Tanakh book claims that URN, including one that carries only the
    # book's title and no text — MAM has such a file for each of the megillot — and the book
    # URN would resolve to the first project in priority order whether or not it has the
    # words. A verse range asks for what is actually read, so it passes over an edition that
    # does not have it, which is what every other reading the humash emits already does.
    last_chapter = chapters_in_book(book, sourcetexts_root)
    whole_book = VerseRef(book, 1, 1).range_urn(
        VerseRef(book, last_chapter, verses_in_chapter(book, last_chapter, sourcetexts_root))
    )
    parts = [_transclude(whole_book)]
    repeat = REPEATED_CLOSING_VERSES.get((f"megillah:{book}", book))
    if repeat is not None:
        chapter, verse = repeat
        ref = VerseRef(book, chapter, verse)
        parts.append(_instruction(REPEATED_VERSE_INSTRUCTION))
        parts.append(_transclude(ref.range_urn(ref)))

    content = (
        f'<tei:div corresp="{urn_base}" n="megillah_{book}">'
        f"<tei:head>{_escape(hebrew)}</tei:head>{''.join(parts)}</tei:div>"
    )
    body = _conditional("opensiddur:holiday", holiday, content, "megillah")
    header = _header(hebrew, book.replace("_", " ").title(), f"megillah/{book}")
    return f"megillat_{book}", _document(header, body)


def festival_file(
    slug: str,
    reading: dict,
    sourcetexts_root: Path | None = None,
) -> tuple[str, str]:
    """One festival or special-Shabbat reading, with its haftarah."""
    urn_base = f"{URN_PREFIX}:reading/{slug}"
    name = reading["name"]
    parts: list[str] = []

    spans = reading["aliyot"]
    if spans:
        by_book: dict[str, list[ReadingSpan]] = {}
        for span in spans:
            by_book.setdefault(span.book, []).append(span)
        for book_spans in by_book.values():
            ordered = sorted(book_spans, key=lambda span: (span.start, span.end))
            book = ordered[0].book
            start = min(span.start for span in ordered)
            end = max(span.end for span in ordered)
            parts.append(_citation_milestone(_citation_range(book, start, end)))
            segments = model.segment_reading(
                ordered, sourcetexts_root=sourcetexts_root
            )
            parts.extend(_segment_xml(s, urn_base, sourcetexts_root) for s in segments)

    # The haftarah gets a division of its own, headed, rather than following the maftir inside
    # the reading's div: where a festival has one rite's haftarah and so no rite heading, the
    # prophetic reading would otherwise begin with nothing at all to announce it, running on
    # from the end of the Torah reading as though it were more of the same.
    haftarah_parts: list[str] = []
    for passage in reading["haftarot"]:
        content = _passage_xml(passage, urn_base, sourcetexts_root)
        if passage.rite is None:
            haftarah_parts.append(content)
        else:
            variant = (
                f'<tei:div corresp="{urn_base}/{passage.rite}" n="{passage.rite}">'
                f"<tei:head>{_escape(passage.title or passage.rite)}</tei:head>"
                f"{content}</tei:div>"
            )
            haftarah_parts.append(
                _conditional("opensiddur:rite", passage.rite, variant, "rite")
            )
    if haftarah_parts:
        parts.append(
            f'<tei:div corresp="{urn_base}/haftarah" n="haftarah">'
            f"<tei:head>{_escape(HAFTARAH_TITLE)}</tei:head>"
            f"{''.join(haftarah_parts)}</tei:div>"
        )

    # hebcal names its readings in English; the heading is what the page shows, and everything
    # else in the volume is titled in Hebrew. The English name is kept in the header.
    hebrew = hebrew_name(name)
    body = (
        f'<tei:div corresp="{urn_base}" n="reading_{slug}">'
        f'<tei:head>{_escape(hebrew)}</tei:head>{"".join(parts)}</tei:div>'
    )
    header = _header(hebrew, name, f"reading/{slug}")
    return f"reading_{slug}", _document(header, body, lang="he")


def book_file(book: str, parshiyot: list[Parsha]) -> tuple[str, str]:
    """One of the five books, transcluding its parshiyot in order.

    A pair is transcluded once, by the pair's own URN: its file holds both singles, so
    transcluding the members as well would print their text twice.
    """
    urn_base = f"{URN_PREFIX}:chumash/{book}"
    hebrew = SLUG_TO_VOCALIZED_BOOK[book]
    targets: list[str] = []
    for parsha in parshiyot:
        slug = PAIR_FOR_MEMBER.get(parsha.slug, parsha.slug)
        if not targets or targets[-1] != slug:
            targets.append(slug)
    inner = "".join(_transclude(f"{URN_PREFIX}:parsha/{slug}") for slug in targets)
    body = (
        f'<tei:div type="book" corresp="{urn_base}" n="{book}">'
        f"<tei:head>{_escape(hebrew)}</tei:head>{inner}</tei:div>"
    )
    header = _header(hebrew, book.title(), f"chumash/{book}")
    return book, _document(header, body)


def haftarah_order(parshiyot: list[Parsha], available: dict[str, object]) -> list[str]:
    """The haftarah slugs in the order their parshiyot are read.

    Sorting by slug would file חיי שרה between בשלח and חֻקת. A pair's haftarah follows both
    its members', since a pair is read on a week that would otherwise have read the second of
    them. Anything with no parshah of that name — hebcal has none today — keeps a place at the
    end rather than being dropped.
    """
    ordered: list[str] = []
    for parsha in parshiyot:
        if parsha.slug in available:
            ordered.append(parsha.slug)
        pair = PAIR_FOR_MEMBER.get(parsha.slug)
        # The pair goes after its second member, which is the parshah that follows its first.
        if pair is not None and pair in available and PAIR_MEMBERS[pair][1] == parsha.slug:
            ordered.append(pair)
    ordered.extend(sorted(set(available) - set(ordered)))
    return ordered


# The parts of the volume that are not the Torah itself. Each gathers its readings under one
# heading, so that they stand to their readings as a book stands to its parshiyot rather than
# lying beside the five books as 250 loose sections.
SECTIONS: tuple[tuple[str, str], ...] = (
    ("haftarot", "הַפְטָרוֹת"),
    ("megillot", "מְגִלּוֹת"),
    ("readings", "קְרִיאֵי מוֹעֵד"),
)


def index_file(sections: dict[str, list[str]]) -> tuple[str, str]:
    """The project entry point, holding the bibliography and transcluding everything."""
    urn = f"{URN_PREFIX}:chumash"
    inner = "".join(
        _transclude(f"{URN_PREFIX}:chumash/{slug}") for _, slug, _ in TORAH_BOOKS
    )
    for name, title in SECTIONS:
        targets = sections.get(name) or []
        if not targets:
            continue
        inner += (
            f'<tei:div corresp="{urn}/{name}" n="{name}">'
            f"<tei:head>{_escape(title)}</tei:head>"
            f"{''.join(_transclude(target) for target in targets)}</tei:div>"
        )
    body = (
        f'<tei:div corresp="{urn}" n="chumash">'
        f"<tei:head>{_escape('חֻמָּשׁ')}</tei:head>{inner}</tei:div>"
    )
    header = f"""<tei:teiHeader>
  <tei:fileDesc>
    <tei:titleStmt>
      <tei:title type="main" xml:lang="he">חֻמָּשׁ</tei:title>
      <tei:title type="alt" xml:lang="en">Humash</tei:title>
      <tei:respStmt>
        <tei:resp key="mrk">Markup</tei:resp>
        <tei:name ref="urn:x-opensiddur:contributor:opensiddur.org/efraim-feinstein">Efraim Feinstein</tei:name>
      </tei:respStmt>
    </tei:titleStmt>
    <tei:editionStmt>
      <tei:p>The Torah arranged by liturgical reading. This project holds no text of its own:
        every reading is transcluded by URN from a Tanakh project, and only the headings and
        instructions originate here.</tei:p>
    </tei:editionStmt>
    <tei:publicationStmt>
      <tei:distributor>
        <tei:ref target="http://opensiddur.org">Open Siddur Project</tei:ref>
      </tei:distributor>
      <tei:idno type="urn">{urn}@{PROJECT}</tei:idno>
      <tei:availability status="free">
        <tei:licence target="http://www.creativecommons.org/publicdomain/zero/1.0/">Creative Commons Zero Public Domain Declaration (CC0)</tei:licence>
      </tei:availability>
    </tei:publicationStmt>
    <tei:sourceDesc>
      <tei:bibl xml:id="source_mam">
        <tei:title>Miqra al pi ha-Masorah</tei:title>
        <tei:ptr target="{URN_PREFIX}:tanakh@{MIQRA_PROJECT}"/>
        <tei:note>Source of the weekly parshah, aliyah and maftir divisions.</tei:note>
      </tei:bibl>
      <tei:bibl xml:id="source_hebcal">
        <tei:title>hebcal leyning</tei:title>
        <tei:ptr target="https://github.com/hebcal/hebcal-leyning"/>
        <tei:note>Source of the haftarot, the festival readings and the triennial cycle.</tei:note>
      </tei:bibl>
    </tei:sourceDesc>
  </tei:fileDesc>
</tei:teiHeader>"""
    front = (
        "<tei:titlePage><tei:docTitle>"
        '<tei:titlePart type="main" xml:lang="he">חֻמָּשׁ</tei:titlePart>'
        '<tei:titlePart type="alt" xml:lang="en">Humash</tei:titlePart>'
        "</tei:docTitle></tei:titlePage>"
    )
    return "index", _document(header, body, front=front)


def build(
    project_directory: Path,
    sourcetexts_root: Path | None = None,
    validate: bool = True,
) -> list[Path]:
    """Generate the whole humash project. Returns the files written."""
    project_dir = project_directory / PROJECT
    project_dir.mkdir(parents=True, exist_ok=True)

    parshiyot, pairs = parse_readings(sourcetexts_root)
    all_haftarot = haftarot(sourcetexts_root)
    all_triennial_haftarot = triennial_haftarot(sourcetexts_root)
    all_triennial = triennial(sourcetexts_root)
    all_patterns = triennial_patterns(sourcetexts_root)
    festivals = festival_readings(sourcetexts_root)

    documents: list[tuple[str, str]] = []
    by_slug = {parsha.slug: parsha for parsha in parshiyot}
    for parsha in parshiyot:
        # The fourteen that have a partner are emitted inside their pair's file instead.
        if parsha.slug in PAIR_FOR_MEMBER:
            continue
        documents.append(parsha_file(
            parsha, all_triennial.get(parsha.slug, {}), sourcetexts_root
        ))
    for pair in pairs:
        documents.append(pair_file(
            pair, [by_slug[slug] for slug in pair.members], all_triennial,
            all_patterns.get(pair.slug, {}), sourcetexts_root,
        ))

    by_book: dict[str, list[Parsha]] = {}
    for parsha in parshiyot:
        by_book.setdefault(parsha.book, []).append(parsha)
    for _, book, _ in TORAH_BOOKS:
        documents.append(book_file(book, by_book.get(book, [])))

    sections: dict[str, list[str]] = {name: [] for name, _ in SECTIONS}
    for slug in haftarah_order(parshiyot, all_haftarot):
        documents.append(
            haftarah_file(
                slug, all_haftarot[slug], all_triennial_haftarot.get(slug, {}),
                sourcetexts_root,
            )
        )
        sections["haftarot"].append(f"{URN_PREFIX}:haftarah/{slug}")

    unplaced = sorted(set(all_triennial_haftarot) - set(all_haftarot))
    if unplaced:
        # Nothing to hang them off: a parshah with a triennial haftarah but no annual one would
        # have no file of its own, so say so rather than dropping it silently.
        logger.warning(
            "No haftarah file for %s, so their triennial haftarot were not emitted",
            ", ".join(unplaced),
        )
    for book, hebrew, holiday in MEGILLOT:
        documents.append(megillah_file(book, hebrew, holiday, sourcetexts_root))
        sections["megillot"].append(f"{URN_PREFIX}:megillah/{book}")
    for slug, reading in sorted(festivals.items()):
        documents.append(festival_file(slug, reading, sourcetexts_root))
        sections["readings"].append(f"{URN_PREFIX}:reading/{slug}")

    documents.append(index_file(sections))

    written: list[Path] = []
    for file_name, content in documents:
        if validate:
            written.append(validate_and_write(content, file_name, project_dir))
        else:
            path = project_dir / f"{file_name}.xml"
            path.write_text(content, encoding="utf-8")
            written.append(path)
    logger.info("Wrote %d files to %s", len(written), project_dir)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--sourcetexts-root", type=Path, default=None)
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip RelaxNG/Schematron validation (requires the compiled schema otherwise).",
    )
    args = parser.parse_args(argv)
    build(args.project_dir, args.sourcetexts_root, validate=not args.no_validate)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
