"""Every festival and special-Shabbat Torah reading, read back against the aliyot it is built from.

`build.festival_file` emits a day's Torah reading as aliyah markers, repeat instructions and
transclusions. Read back in order, with each transclusion expanded into its verses, that has to
be the day's aliyot as they are read: each aliyah's marker, then the instruction if the aliyah
reads again verses read before it, then its verses, and nothing else. A verse that no aliyah
reads, an aliyah out of its place and an instruction where nothing is read again all break it.

Each citation is checked too: it names the verses printed under it, and the first citation of
a book's passage names, in order, the stretches that the citations after it open.

The checks run over hebcal's readings where the sourcetexts submodule is initialised, and over
every arrangement of a few synthetic aliyot everywhere, so that they also run without the data.
"""

import itertools
import json
import re
import tempfile
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.importer.humash import build
from opensiddur.importer.humash.readings import festival_readings
from opensiddur.importer.humash.refs import (
    SLUG_TO_HEBREW_ANY_BOOK,
    UNIT_ALIYAH,
    UNIT_MAFTIR,
    ReadingSpan,
    VerseRef,
    next_verse,
)
from opensiddur.importer.util.pages import hebcal_leyning_data_directory

TEI = "{http://www.tei-c.org/ns/1.0}"
J = "{http://jewishliturgy.org/ns/jlptei/2}"
TARGET = re.compile(r"urn:x-opensiddur:text:bible:([a-z_0-9]+)/(\d+)/(\d+)-(\d+)/(\d+)")
# One clause of a citation: "<book> 28:1–28:15", or "7:42–7:47" after the first clause.
CLAUSE = re.compile(
    r"(?:(?P<book>\S+) )?(?P<c1>\d+):(?P<v1>\d+)(?:" "\N{EN DASH}" r"(?P<c2>\d+):(?P<v2>\d+))?"
)
BOOK_BY_HEBREW = {hebrew: slug for slug, hebrew in SLUG_TO_HEBREW_ANY_BOOK.items()}


def _verses(start: VerseRef, end: VerseRef, root: Path | None) -> list[tuple]:
    """Every verse from `start` to `end`, as ("verse", book, chapter, verse)."""
    verses = []
    ref = start
    while True:
        verses.append(("verse", ref.book, ref.chapter, ref.verse))
        if ref == end:
            return verses
        if end < ref:
            raise AssertionError(f"{start}-{end} is not a range")
        ref = next_verse(ref, root)


def _read_back(document: str, root: Path | None) -> list[tuple]:
    """The Torah reading of a festival file, in document order: citations, markers,
    instructions and verses."""
    division = etree.fromstring(document.encode("utf-8")).find(f"{TEI}text/{TEI}body/{TEI}div")
    stream: list[tuple] = []
    for element in division:
        if element.tag == f"{TEI}div":
            break  # The haftarah's division, which follows the Torah reading.
        if element.tag == f"{TEI}head":
            continue
        if element.tag == f"{TEI}milestone" and element.get("unit") == "citation":
            stream.append(("citation", element.get("n")))
        elif element.tag == f"{TEI}milestone":
            unit, label = element.get("corresp").rsplit("/", 2)[-2:]
            stream.append(("marker", unit, label))
        elif element.tag == f"{TEI}note" and element.get("type") == "instruction":
            stream.append(("instruction",))
        elif element.tag == f"{J}transclude":
            match = TARGET.fullmatch(element.get("target"))
            if match is None:
                raise AssertionError(f"not a range of whole verses: {element.get('target')}")
            book, *numbers = match.groups()
            start_chapter, start_verse, end_chapter, end_verse = map(int, numbers)
            stream.extend(_verses(
                VerseRef(book, start_chapter, start_verse),
                VerseRef(book, end_chapter, end_verse),
                root,
            ))
        else:
            raise AssertionError(f"unexpected element in a Torah reading: {element.tag}")
    return stream


def _without_citations(stream: list[tuple]) -> list[tuple]:
    return [event for event in stream if event[0] != "citation"]


def _cited_ranges(citation: str) -> list[tuple]:
    """A citation's clauses as (first verse, last verse), each verse (book, chapter, verse)."""
    ranges = []
    book = None
    for clause in citation.split("; "):
        match = CLAUSE.fullmatch(clause)
        if match is None:
            raise AssertionError(f"not a citation clause: {clause!r} in {citation!r}")
        if match.group("book") is not None:
            book = BOOK_BY_HEBREW[match.group("book")]
        first = (book, int(match.group("c1")), int(match.group("v1")))
        last = (book, int(match.group("c2") or match.group("c1")),
                int(match.group("v2") or match.group("v1")))
        ranges.append((first, last))
    return ranges


def _citations_name_their_verses(test: unittest.TestCase, stream: list[tuple]) -> None:
    """Each citation spans exactly the verses printed after it, up to the next citation, and
    the first citation of a book's passage lists, in order, what the citations after it name."""
    cited: list[tuple[list[tuple], list[tuple]]] = []
    for event in stream:
        if event[0] == "citation":
            cited.append((_cited_ranges(event[1]), []))
        elif event[0] == "verse":
            test.assertTrue(cited, "verses printed before any citation")
            cited[-1][1].append(event[1:])
    listed: list[tuple] = []
    for ranges, verses in cited:
        if listed:
            test.assertEqual(ranges, [listed.pop(0)])
        else:
            listed = ranges[1:]
        test.assertTrue(verses, f"no verse printed under {ranges}")
        test.assertEqual((min(verses), max(verses)), ranges[0])
    test.assertEqual(listed, [], "an opening citation lists more than is printed")


def _alternatives(first: ReadingSpan, second: ReadingSpan) -> bool:
    """The maftirs hebcal keys by the day of Chol HaMoed, of which a congregation reads one."""
    return first.label != second.label and all(
        span.unit == UNIT_MAFTIR and span.label.startswith("maftir_day") for span in (first, second)
    )


def _as_read(spans: list[ReadingSpan], root: Path | None) -> list[tuple]:
    """What `_read_back` should find: each aliyah in turn, in the order it is read."""
    stream: list[tuple] = []
    for index, span in enumerate(spans):
        stream.append(("marker", span.unit.replace(".", "_"), span.label))
        if any(
            earlier.book == span.book
            and earlier.start <= span.end
            and span.start <= earlier.end
            and not _alternatives(earlier, span)
            for earlier in spans[:index]
        ):
            stream.append(("instruction",))
        stream.extend(_verses(span.start, span.end, root))
    return stream


def _hebcal_label(key: str) -> str:
    """The label readings.festival_readings gives one of hebcal's aliyah keys."""
    if key == "M":
        return "maftir"
    return key.replace("M-", "maftir_") if key.startswith("M-") else key


class TestHebcalReadings(unittest.TestCase):
    """hebcal's own readings, wherever the sourcetexts submodule is initialised."""

    def setUp(self):
        self.data = hebcal_leyning_data_directory() / "holiday-readings.json"
        if not self.data.is_file():
            self.skipTest("the sourcetexts submodule is not initialised")

    def test_every_reading_is_its_aliyot_in_the_order_hebcal_lists_them(self):
        hebcal = json.loads(self.data.read_text(encoding="utf-8"))
        readings = festival_readings()
        self.assertTrue(readings)
        for slug, reading in sorted(readings.items()):
            with self.subTest(reading=slug):
                spans = reading["aliyot"]
                keys = list(hebcal[reading["name"]].get("fullkriyah") or {})
                self.assertEqual([span.label for span in spans], [_hebcal_label(k) for k in keys])
                _, document = build.festival_file(slug, reading)
                stream = _read_back(document, None)
                self.assertEqual(_without_citations(stream), _as_read(spans, None))
                _citations_name_their_verses(self, stream)


# Aliyot that between them continue, overlap, skip ahead, step back and change book.
RANGES = [
    ("numbers", (28, 1), (28, 5)),
    ("numbers", (28, 6), (28, 10)),
    ("numbers", (28, 3), (28, 7)),
    ("numbers", (28, 1), (28, 3)),
    ("numbers", (29, 1), (29, 4)),
    ("numbers", (7, 1), (7, 4)),
    ("exodus", (12, 1), (12, 3)),
]
# Maftirs for one place that depend on the day, each overlapping the next.
DAY_MAFTIRS = [
    ("numbers", (29, 1), (29, 6)),
    ("numbers", (29, 4), (29, 9)),
    ("numbers", (29, 7), (29, 12)),
]


def _span(unit: str, label: str, verses: tuple) -> ReadingSpan:
    book, start, end = verses
    return ReadingSpan(
        unit=unit, label=label, start=VerseRef(book, *start), end=VerseRef(book, *end)
    )


class TestEveryArrangement(unittest.TestCase):
    """Every arrangement of up to three of the synthetic aliyot; of up to two before the
    maftirs that depend on the day; and of one aliyah and a maftir after it."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        directory = self.root / "hebcal_leyning"
        directory.mkdir(parents=True)
        (directory / "numverses.json").write_text(
            json.dumps({name: [0] + [31] * 40 for name in
                        ("Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy")}),
            encoding="utf-8",
        )

    def _check(self, spans: list[ReadingSpan]) -> None:
        reading = {"name": "Rosh Chodesh", "aliyot": spans, "haftarot": []}
        with self.subTest(aliyot="; ".join(f"{s.label}={s.start}-{s.end}" for s in spans)):
            _, document = build.festival_file("rosh_chodesh", reading, self.root)
            stream = _read_back(document, self.root)
            self.assertEqual(_without_citations(stream), _as_read(spans, self.root))
            _citations_name_their_verses(self, stream)

    def test_aliyot_in_every_order_read_as_they_are_listed(self):
        for length in (1, 2, 3):
            for chosen in itertools.product(RANGES, repeat=length):
                self._check([
                    _span(UNIT_ALIYAH, str(number), verses)
                    for number, verses in enumerate(chosen, start=1)
                ])

    def test_maftirs_that_depend_on_the_day_do_not_repeat_one_another(self):
        maftirs = [
            _span(UNIT_MAFTIR, f"maftir_day{day}", verses)
            for day, verses in enumerate(DAY_MAFTIRS, start=1)
        ]
        for length in (0, 1, 2):
            for chosen in itertools.product(RANGES, repeat=length):
                self._check([
                    _span(UNIT_ALIYAH, str(number), verses)
                    for number, verses in enumerate(chosen, start=1)
                ] + maftirs)

    def test_a_maftir_is_read_after_the_aliyah_before_it(self):
        for aliyah_verses, maftir_verses in itertools.product(RANGES, repeat=2):
            aliyah = _span(UNIT_ALIYAH, "1", aliyah_verses)
            maftir = _span(UNIT_MAFTIR, "maftir", maftir_verses)
            if aliyah.book == maftir.book and aliyah.start <= maftir.start <= aliyah.end:
                # A maftir that starts inside the aliyah shares its text, which is printed once
                # with the maftir's marker inside it, as in a parashah; `_as_read` reads it twice.
                continue
            self._check([aliyah, maftir])


if __name__ == "__main__":
    unittest.main()
