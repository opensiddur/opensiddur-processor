"""Haftarot, festival readings and the modern triennial cycle, read from the hebcal data.

MAM records no haftarot and no festival readings at all, so these come from hebcal. Each is
modelled as a *passage*: an ordered list of spans, because a haftarah is frequently
discontinuous and occasionally moves backwards through its book — Mishpatim reads Jeremiah
34:8-22 and then 33:25-26 — and because two of them bridge books.
"""

from __future__ import annotations

import functools
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from opensiddur.importer.humash.names import (
    HEBCAL_TO_SLUG,
    PAIR_FOR_MEMBER,
    PAIR_MEMBERS,
    slugify_reading_name,
)
from opensiddur.importer.humash.refs import (
    BOOK_NUMBER_TO_SLUG,
    HEBCAL_BOOK_TO_SLUG,
    NUMBERING_COMMON,
    UNIT_ALIYAH,
    UNIT_MAFTIR,
    VARIATION_COMBINED,
    ReadingSpan,
    VerseRef,
    canonical_ref,
    parse_hebcal_ref,
    triennial_unit,
)
from opensiddur.importer.util.pages import hebcal_leyning_data_directory

logger = logging.getLogger(__name__)

# The rites hebcal distinguishes. "haft" is what it gives without qualification, which is the
# Ashkenazi reading; "seph" is the Sephardi one. Other rites are not in this data.
RITE_ASHKENAZ = "ashkenaz"
RITE_SEPHARAD = "sepharad"
HEBCAL_RITE_KEYS = {"haft": RITE_ASHKENAZ, "seph": RITE_SEPHARAD}

RITE_TITLES = {
    RITE_ASHKENAZ: "מִנְהַג אַשְׁכְּנַז",
    RITE_SEPHARAD: "מִנְהַג סְפָרַד",
}

# Readings that repeat an earlier verse after the last one, so as not to end on a verse of
# rebuke or calamity. hebcal does not record this, and it is invisible in the output if
# forgotten, so it is listed here explicitly.
#
# Keyed by (reading key, book slug) -> the verse to repeat at the end.
REPEATED_CLOSING_VERSES: dict[tuple[str, str], tuple[int, int]] = {
    # Isaiah 66:24 ends "their worm shall not die"; 66:23 is read again after it.
    ("Shabbat Rosh Chodesh", "isaiah"): (66, 23),
    # Malachi 3:24 ends with a curse, so 3:23 is repeated after it.
    ("Shabbat HaGadol", "malachi"): (3, 23),
    # The last verse of Lamentations is a lament; 5:21 is repeated after 5:22.
    ("megillah:lamentations", "lamentations"): (5, 21),
    # Ecclesiastes 12:13 is repeated after 12:14.
    ("megillah:ecclesiastes", "ecclesiastes"): (12, 13),
}

REPEATED_VERSE_INSTRUCTION = "חוזרים ואומרים את הפסוק הקודם"


@dataclass
class Passage:
    """One reading: an ordered list of spans, possibly discontinuous or across books."""

    key: str
    spans: list[ReadingSpan] = field(default_factory=list)
    rite: str | None = None
    title: str | None = None
    note: str | None = None
    # A verse repeated after the end so the reading does not close on a hard verse.
    repeated: ReadingSpan | None = None

    @property
    def books(self) -> list[str]:
        seen: list[str] = []
        for span in self.spans:
            if span.book not in seen:
                seen.append(span.book)
        return seen


# Verses hebcal names that do not exist. Corrected on the way in rather than in sourcetexts,
# which is kept a faithful copy of upstream. Each entry gives the path to the value, what
# upstream says, and what it should say, so that a fix upstream is noticed rather than
# silently overwritten.
HEBCAL_CORRECTIONS: dict[str, dict[tuple, tuple[str, str]]] = {
    "triennial-haft.json": {
        # Ki Teitzei year 3 reads Isaiah 48:12-21 and then repeats 48:20, so that the haftarah
        # does not end on 48:22, אין שלום אמר ה׳ לרשעים. Upstream writes chapter 4, which has
        # six verses.
        ("Ki Teitzei", "3", 1, "b"): ("4:20", "48:20"),
        ("Ki Teitzei", "3", 1, "e"): ("4:20", "48:20"),
    },
}


def _apply_corrections(name: str, data: dict) -> dict:
    """Replace the known bad references in one hebcal file, in place."""
    for path, (wrong, right) in HEBCAL_CORRECTIONS.get(name, {}).items():
        node = data
        try:
            for step in path[:-1]:
                node = node[step]
            found = node[path[-1]]
        except (KeyError, IndexError, TypeError):
            logger.warning("%s: %s is gone, so its correction no longer applies", name, path)
            continue
        if found == right:
            continue
        if found != wrong:
            logger.warning(
                "%s: %s reads %r, neither the %r this corrects nor the %r it corrects it to; "
                "leaving it alone", name, path, found, wrong, right,
            )
            continue
        node[path[-1]] = right
    return data


@functools.cache
def _load(name: str, sourcetexts_root: Path | None = None) -> dict:
    path = hebcal_leyning_data_directory(sourcetexts_root) / name
    return _apply_corrections(name, json.loads(path.read_text(encoding="utf-8")))


def _haftarah_spans(raw, unit: str = "haftarah") -> list[ReadingSpan]:
    """Turn hebcal's haftarah value — one object or a list of them — into spans."""
    parts = raw if isinstance(raw, list) else [raw]
    spans: list[ReadingSpan] = []
    for index, part in enumerate(parts, start=1):
        book = HEBCAL_BOOK_TO_SLUG[part["k"]]
        spans.append(ReadingSpan(
            unit=unit,
            label=str(index),
            start=parse_hebcal_ref(book, part["b"]),
            end=parse_hebcal_ref(book, part["e"], at_end=True),
            note=part.get("note"),
        ))
    return spans


def _without_anchor_verses(key: str, spans: list[ReadingSpan]) -> list[ReadingSpan]:
    """The spans actually read, dropping any that an earlier span already covers.

    Eight of the triennial haftarot end with a piece inside one already listed — Nasso
    year 1 is Joshua 6:5-14 and then 6:12, Emor year 3 is Nachum 2:1-3 and then 2:2b-3a. That
    is the verse the pairing with the parshah turns on, recorded beside the reading rather than
    appended to it: taking it as a continuation would read those verses a second time.

    A piece that merely runs backwards is left alone. The haftarot really do that — Mishpatim
    reads Jeremiah 34:12-22 and then 33:25-26 — and only containment marks an anchor.
    """
    kept: list[ReadingSpan] = []
    for span in spans:
        anchor = any(
            earlier.book == span.book
            and earlier.start <= span.start
            and span.end <= earlier.end
            for earlier in kept
        )
        if anchor:
            logger.debug(
                "%s: %s-%s lies inside an earlier span, so it is the verse the pairing turns "
                "on rather than part of the reading", key, span.start, span.end,
            )
            continue
        kept.append(span)
    return kept


def _repeated_span(key: str, spans: list[ReadingSpan]) -> ReadingSpan | None:
    """The closing verse to repeat, if this reading has one."""
    if not spans:
        return None
    book = spans[-1].end.book
    repeat = REPEATED_CLOSING_VERSES.get((key, book))
    if repeat is None:
        return None
    chapter, verse = repeat
    # Stated the way the printed editions number, like everything else taken from hebcal.
    ref = canonical_ref(NUMBERING_COMMON, VerseRef(book, chapter, verse))
    return ReadingSpan(unit="haftarah.repeated", label="repeated", start=ref, end=ref)


def haftarot(sourcetexts_root: Path | None = None) -> dict[str, list[Passage]]:
    """The haftarah of each weekly parshah, by slug, one Passage per rite."""
    data = _load("aliyot.json", sourcetexts_root)
    result: dict[str, list[Passage]] = {}
    for name, entry in data.items():
        slug = HEBCAL_TO_SLUG.get(name)
        if slug is None:
            continue
        passages: list[Passage] = []
        for hebcal_key, rite in HEBCAL_RITE_KEYS.items():
            if hebcal_key not in entry:
                continue
            spans = _haftarah_spans(entry[hebcal_key])
            passages.append(Passage(
                key=name,
                spans=spans,
                rite=rite,
                title=RITE_TITLES[rite],
                repeated=_repeated_span(name, spans),
            ))
        if passages:
            # A parshah with only one recorded haftarah has no rite variation to show.
            if len(passages) == 1:
                passages[0].rite = None
                passages[0].title = None
            result[slug] = passages
    return result


def festival_readings(sourcetexts_root: Path | None = None) -> dict[str, dict]:
    """Every festival and special-Shabbat reading, keyed by hebcal's name for the occasion.

    Each value holds the Torah spans (``aliyot``) and one Passage per rite (``haftarot``).
    The Torah reading of a festival is drawn from wherever in the Torah it belongs, so unlike
    the weekly parshiyot these spans may come from any book.
    """
    data = _load("holiday-readings.json", sourcetexts_root)
    result: dict[str, dict] = {}
    for name, entry in data.items():
        if entry.get("alias"):
            # A pointer, not a reading: hebcal names the occasion and says which reading it
            # takes. Rosh Chodesh Nisan is the Rosh Chodesh reading, Tzom Gedaliah the Fast
            # Day (Morning) one, Pesach III (CH"M) is what Israel calls Pesach Chol ha-Moed
            # Day 1. The reading itself is emitted under the name hebcal points at, so
            # following the pointer here would print the same text under thirty-one more
            # headings; which occasions fall on which day is the calendar's business, not a
            # division of the text.
            logger.debug("%s reads %s, so it is not a reading of its own", name, entry["key"])
            continue
        aliyot_spans: list[ReadingSpan] = []
        for label, value in entry.get("fullkriyah", {}).items():
            book = BOOK_NUMBER_TO_SLUG[value["k"]]
            # Most festivals have one maftir, keyed "M". Sukkot's Chol HaMoed Shabbat has a
            # different maftir per weekday of the intermediate days, keyed "M-day1".."M-day5".
            is_maftir = label == "M" or label.startswith("M-day")
            unit = UNIT_MAFTIR if is_maftir else UNIT_ALIYAH
            if label == "M":
                normalized_label = "maftir"
            elif is_maftir:
                normalized_label = f"maftir_{label[len('M-'):]}"
            else:
                normalized_label = label
            aliyot_spans.append(ReadingSpan(
                unit=unit,
                label=normalized_label,
                start=parse_hebcal_ref(book, value["b"]),
                end=parse_hebcal_ref(book, value["e"], at_end=True),
            ))
        passages: list[Passage] = []
        for hebcal_key, rite in HEBCAL_RITE_KEYS.items():
            if hebcal_key not in entry:
                continue
            spans = _haftarah_spans(entry[hebcal_key])
            passages.append(Passage(
                key=name, spans=spans, rite=rite, title=RITE_TITLES[rite],
                repeated=_repeated_span(name, spans),
            ))
        if len(passages) == 1:
            passages[0].rite = None
            passages[0].title = None
        result[slugify_reading_name(name)] = {
            "name": name,
            "aliyot": sorted(aliyot_spans, key=lambda span: (span.unit, span.label)),
            "haftarot": passages,
        }
    return result


def _division_spans(
    aliyot: dict,
    book: str,
    year: int,
    variation: str | None,
    owner: str | None,
) -> list[ReadingSpan]:
    """One year's aliyot, as spans of the unit-space that year and variation own."""
    spans: list[ReadingSpan] = []
    for label, value in (aliyot or {}).items():
        if not isinstance(value, list) or len(value) < 2:
            continue
        maftir = label == "M"
        name = "maftir" if maftir else label
        # The maftir re-reads the close of that year's seventh aliyah, so like the annual
        # maftir it needs a unit-space of its own or it would cut the aliyah short; and each
        # cycle year needs one because the years overlap each other.
        spans.append(ReadingSpan(
            unit=triennial_unit(year, maftir=maftir, variation=variation, owner=owner),
            label=f"{year}.{name}" if variation is None else f"{variation}.{year}.{name}",
            start=parse_hebcal_ref(book, value[0]),
            end=parse_hebcal_ref(book, value[1], at_end=True),
            owner=owner,
        ))
    return spans


def triennial(
    sourcetexts_root: Path | None = None,
) -> dict[str, dict[tuple[str | None, int], list[ReadingSpan]]]:
    """The modern triennial division of each reading, by slug then (variation, cycle year).

    Most parshiyot hold the three years under "years" and have no variation, so their key is
    ``(None, year)``. The twelve that may be read combined with their partner divide
    differently depending on whether they were read alone in each year of the cycle, and hold
    a "variations" object keyed ``"<variation>.<year>"`` — ``"C.2"`` is year 2 of variation C.
    Which variation a cycle uses follows from its combine/separate pattern; see
    ``triennial_patterns``. A variation may be an alias for another, written as a string
    rather than an object, and is followed here so that every key yields real aliyot.

    The seven combined readings are keyed by the pair's own slug, with variation
    ``VARIATION_COMBINED``: they are what is read on a year the pair is read together.
    """
    data = _load("triennial.json", sourcetexts_root)
    result: dict[str, dict[tuple[str | None, int], list[ReadingSpan]]] = {}
    for name, entry in data.items():
        slug = HEBCAL_TO_SLUG.get(name)
        if slug is None:
            continue
        book = BOOK_NUMBER_TO_SLUG[entry["book"]]
        combined = slug in PAIR_MEMBERS
        # A parshah with a partner shares that pair's file, so its variations carry its slug.
        # The combined reading and the 42 that stand alone own their file and do not.
        owner = slug if slug in PAIR_FOR_MEMBER else None
        divisions: dict[tuple[str | None, int], list[ReadingSpan]] = {}

        for year_key, aliyot in (entry.get("years") or {}).items():
            if not year_key.startswith("Y.") or not isinstance(aliyot, dict):
                continue
            year = int(year_key.split(".", 1)[1])
            variation = VARIATION_COMBINED if combined else None
            spans = _division_spans(aliyot, book, year, variation, owner)
            if spans:
                divisions[(variation, year)] = spans

        variations = entry.get("variations") or {}
        for variation_key, aliyot in variations.items():
            # An alias names another variation whose division is identical.
            while isinstance(aliyot, str):
                aliyot = variations.get(aliyot)
            if not isinstance(aliyot, dict):
                continue
            variation, _, year_part = variation_key.rpartition(".")
            if not year_part.isdigit():
                continue
            year = int(year_part)
            # "Y" is hebcal's name for "no variation": the fixed three years.
            variation = None if variation == "Y" else variation
            spans = _division_spans(aliyot, book, year, variation, owner)
            if spans:
                divisions[(variation, year)] = spans

        if divisions:
            result[slug] = divisions
    return result


def triennial_patterns(sourcetexts_root: Path | None = None) -> dict[str, dict[str, str]]:
    """Which variation each combine/separate pattern selects, by pair slug.

    The pattern is one character per year of the cycle — ``T`` where the pair was read
    together that year, ``S`` where apart — so ``{"TSS": "C"}`` says that a cycle which read
    the pair together only in its first year divides the two singles as variation C. The
    patterns that resolve to an Israel variation are disjoint from the diaspora ones, so the
    pattern alone identifies the variation and no separate Israel test is needed.
    """
    data = _load("triennial.json", sourcetexts_root)
    result: dict[str, dict[str, str]] = {}
    for name, entry in data.items():
        slug = HEBCAL_TO_SLUG.get(name)
        # Lech-Lecha is hyphenated but is one parshah, so the pair table decides, not the name.
        if slug not in PAIR_MEMBERS:
            continue
        patterns = entry.get("patterns")
        if patterns:
            result[slug] = dict(patterns)
    return result


def triennial_haftarot(sourcetexts_root: Path | None = None) -> dict[str, dict[int, Passage]]:
    """The triennial haftarah of each parshah, by slug then cycle year.

    These are alternatives to the annual haftarah, not additions to it, and unlike the Torah
    divisions they are keyed by plain cycle year: the reading follows the year alone, so none
    of the variation machinery of ``triennial`` applies.

    Coverage is not uniform, and the caller has to allow for it.

    * Only 51 parshiyot have any. Devarim and Vaetchanan always fall on Shabbat Hazon and
      Shabbat Nahamu, whose haftarot are fixed, and Vezot Haberakhah is read on Simhat Torah;
      those three keep their annual haftarah in every year.
    * Tazria, Achrei Mot and Behar carry years 1 and 2 only, being read alone only in those
      years, and the pairs have no triennial haftarah of their own — so on a year a pair is
      read together the annual haftarah of that week stands.
    * ``Tish'a B'Av`` is in the file but is not a parshah, and is dropped here with everything
      else the parshah table does not name.
    """
    data = _load("triennial-haft.json", sourcetexts_root)
    result: dict[str, dict[int, Passage]] = {}
    for name, entry in data.items():
        slug = HEBCAL_TO_SLUG.get(name)
        if slug is None:
            continue
        years: dict[int, Passage] = {}
        for year_key, value in entry.items():
            # A year is one reading object, or a list of them where the reading is
            # discontinuous — Toldot's third year is Judges 3:15-27 and then 3:30. The
            # mnemonic hebcal notes against each piece rides along on the span.
            parts = value if isinstance(value, list) else [value]
            if not year_key.isdigit() or not parts or not all(
                isinstance(part, dict) and "k" in part for part in parts
            ):
                continue
            passage_key = f"{name}:triennial:{year_key}"
            years[int(year_key)] = Passage(
                key=passage_key,
                spans=_without_anchor_verses(passage_key, _haftarah_spans(value)),
            )
        if years:
            result[slug] = years
    return result
