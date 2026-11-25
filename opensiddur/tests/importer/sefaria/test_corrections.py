import tempfile
import unittest
from pathlib import Path

from opensiddur.importer.sefaria.align import Alignment, Pair
from opensiddur.importer.sefaria.corrections import (
    CorrectionError,
    SegmentCorrection,
    apply_corrections,
    load_corrections,
)
from opensiddur.importer.sefaria.markup import Correction, Styled, Text, parse_segment, plain_text
from opensiddur.importer.sefaria.source import Leaf
from opensiddur.importer.sefaria.tei_builder import render

LEAF = Leaf(("Day", "1"), (("Day", "יום"), ("1", "1")), ("אָבִינוּ",), ("our <i>Fother</i> King",), chapter=1)


def alignment(en="our <i>Fother</i> King"):
    return [Alignment(LEAF, (Pair(1, 1, parse_segment("אָבִינוּ"), parse_segment(en)),), "equal")]


def fix(sic="Fother", corr="Father", segment=1, leaf="Day / 1"):
    return SegmentCorrection(leaf, "en", segment, sic, corr)


class TestApplyCorrections(unittest.TestCase):
    def test_the_misprint_is_marked_where_it_stands(self):
        [corrected] = apply_corrections(alignment(), [fix()])
        en = corrected.pairs[0].en
        self.assertEqual(en, (Text("our "), Styled("italic", (Correction("Fother", "Father"),)), Text(" King")))
        self.assertEqual(plain_text(en), "our Father King")
        self.assertEqual(render(en, "en", None),
                         'our <tei:hi rend="italic"><tei:choice><tei:sic>Fother</tei:sic>'
                         '<tei:corr>Father</tei:corr></tei:choice></tei:hi> King')

    def test_words_no_longer_in_the_segment_are_an_error(self):
        with self.assertRaisesRegex(CorrectionError, "not in the segment once"):
            apply_corrections(alignment("our Father King"), [fix()])

    def test_words_printed_twice_are_an_error(self):
        with self.assertRaisesRegex(CorrectionError, "not in the segment once"):
            apply_corrections(alignment("Fother, Fother"), [fix()])

    def test_words_inside_a_longer_word_are_not_the_misprint(self):
        with self.assertRaisesRegex(CorrectionError, "not in the segment once"):
            apply_corrections(alignment("our Fothers King"), [fix()])

    def test_a_segment_the_leaf_does_not_have_is_an_error(self):
        for correction in (fix(segment=2), fix(leaf="Day / 2")):
            with self.subTest(correction=correction), self.assertRaisesRegex(CorrectionError, "no such segment"):
                apply_corrections(alignment(), [correction])


class TestLoadCorrections(unittest.TestCase):
    def load(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corrections.yaml"
            path.write_text(text, encoding="utf-8")
            return load_corrections(path)

    def test_entries_by_work(self):
        self.assertEqual(self.load("w:\n  - {leaf: Day / 1, lang: en, segment: 3, sic: a, corr: b}\n"),
                         {"w": [SegmentCorrection("Day / 1", "en", 3, "a", "b")]})

    def test_a_file_not_shaped_as_works_and_lists_is_an_error(self):
        for text in ("- a\n", "w: {leaf: x}\n"):
            with self.subTest(text=text), self.assertRaises(CorrectionError):
                self.load(text)

    def test_no_file_is_no_corrections(self):
        self.assertEqual(load_corrections(Path(tempfile.gettempdir()) / "no-such-corrections.yaml"), {})

    def test_an_incomplete_or_empty_entry_is_an_error(self):
        for entry in ("{leaf: Day / 1, lang: en, sic: a, corr: b}",
                      "{leaf: Day / 1, lang: fr, segment: 1, sic: a, corr: b}",
                      "{leaf: Day / 1, lang: en, segment: 1, sic: a, corr: a}",
                      "{leaf: Day / 1, lang: en, segment: 1, sic: a, corr: }",
                      "{leaf: Day / 1, lang: en, segment: 1, sic: 12, corr: b}"):
            with self.subTest(entry=entry), self.assertRaises(CorrectionError):
                self.load(f"w:\n  - {entry}\n")


if __name__ == "__main__":
    unittest.main()
