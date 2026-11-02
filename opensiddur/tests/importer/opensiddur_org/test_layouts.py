"""Posts that set their text outside the site's toggleable tables (``layouts`` in
``post_decisions.yaml``)."""

import tempfile
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.importer.opensiddur_org.contributors import Contributors, post_credits
from opensiddur.importer.opensiddur_org.licences import LICENCES, LicenceDecision
from opensiddur.importer.opensiddur_org.parse_post import node_text, parse_post, transcluded_urn
from opensiddur.importer.opensiddur_org.post_decisions import Layout, PostDecisions, load_post_decisions
from opensiddur.importer.opensiddur_org.scope import irregularities, project_columns
from opensiddur.importer.opensiddur_org.tei_builder import build_project
from opensiddur.importer.opensiddur_org.urns import PostUrns
from opensiddur.tests.importer.opensiddur_org.support import FIXTURES, make_post

NS = {"tei": "http://www.tei-c.org/ns/1.0", "j": "http://jewishliturgy.org/ns/jlptei/2"}
URN = "urn:x-opensiddur:text:prayer:a_song"
MICAH = "urn:x-opensiddur:text:bible:micah/7/19"

# An essay in two languages side by side, then the text: Hebrew beside an English cell of a
# number, an explanation, a translation and a transliteration; then a line crediting where it
# was first published.
BLESSINGS = (
    '<table><tr>'
    '<td><div class="english" lang="eng-Latn">Why we wrote it.<p>And how.</p></div></td>'
    '<td><div class="commentary" lang="heb-Hebr">למה כתבנו.<p>ואיך.</p></div></td>'
    '</tr></table>'
    '<table><tbody>'
    '<tr><td><div class="liturgy" lang="heb-Hebr">ברוך אתה</div></td>'
    '<td><div class="english" lang="eng-Latn">1— א<p>Why this one.</p><p>Blessed are You.</p>'
    '<p>Barukh atah</p></div></td></tr>'
    '<tr><td><div class="liturgy" lang="heb-Hebr">שהכל ברא</div></td>'
    '<td><div class="english" lang="eng-Latn">2— ב<p>Why that one.</p><p>Who created all.</p>'
    '<p>Shehakol bara</p></div></td></tr>'
    '</tbody></table>'
    '<p>First published on <a href="https://example.org/first post">a blog</a>.</p>'
)
BLESSINGS_LAYOUT = Layout(
    text=("(//table)[2]",),
    introduction="(//table)[1]",
    split={2: (None, "Commentary (English)", "Translation (English)", "Transliteration (romanized Hebrew)")},
    credit_after=True,
)

# A practice in one language, then notes quoting a verse.
PRACTICE = (
    '<div class="english" lang="eng-Latn">Think of it.<br />Write it down.<br />Let it go.</div>'
    '<p>It comes from Micah:</p>'
    '<table><tr><td><div lang="heb-Hebr">ותשליך</div></td><td><div lang="eng-Latn">And cast</div></td></tr></table>'
    '<p>And so on.</p>'
)
PRACTICE_LAYOUT = Layout(text=("(//div[@lang])[1]",), transclusions={"(//table)[1]": MICAH})


def parse(content: str, layout: Layout):
    return parse_post(make_post(101, content=content), PostDecisions(layouts={101: layout}))


def text_lines(cell) -> list[str]:
    return [node_text(line) for block in cell.blocks for line in block.lines]


class TestLoading(unittest.TestCase):
    def test_layouts_load_from_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "post_decisions.yaml"
            path.write_text(
                "layouts:\n"
                "  11906:\n"
                "    introduction: (//table)[1]\n"
                "    text: ['(//table)[2]']\n"
                "    split: {2: [null, Commentary (English)]}\n"
                "    credit_after: true\n"
                "    transclusions: {'(//table)[3]': urn:x-opensiddur:text:bible:micah/7/19}\n",
                encoding="utf-8",
            )
            layout = load_post_decisions(path).layouts[11906]
        self.assertEqual(layout, Layout(
            text=("(//table)[2]",), introduction="(//table)[1]", split={2: (None, "Commentary (English)")},
            credit_after=True, transclusions={"(//table)[3]": MICAH},
        ))


class TestParsing(unittest.TestCase):
    def test_a_split_column_becomes_a_column_per_part(self) -> None:
        post = parse(BLESSINGS, BLESSINGS_LAYOUT)
        self.assertEqual(irregularities(post), [])
        self.assertEqual(len(post.tables), 1)
        self.assertEqual([(c.role, c.lang) for c in post.columns], [
            ("source", "he"), ("commentary", "en"), ("translation", "en"), ("transliteration", "he-Latn")])
        self.assertEqual([text_lines(c) for c in post.rows[1].cells],
                         [["שהכל ברא"], ["Why that one."], ["Who created all."], ["Shehakol bara"]])

    def test_the_introduction_is_kept_by_language(self) -> None:
        post = parse(BLESSINGS, BLESSINGS_LAYOUT)
        self.assertEqual(post.intro, [])
        self.assertEqual({lang: [node_text(line) for line in lines] for lang, lines in post.intros_by_language.items()},
                         {"en": ["Why we wrote it.", "And how."], "he": ["למה כתבנו.", "ואיך."]})

    def test_the_credit_after_the_text_is_a_source(self) -> None:
        post = parse(BLESSINGS, BLESSINGS_LAYOUT)
        self.assertEqual(post.notes, [])
        self.assertEqual([(s.caption, s.url) for s in post.sources],
                         [("First published on a blog.", "https://example.org/first%20post")])

    def test_a_language_block_is_a_text(self) -> None:
        post = parse(PRACTICE, PRACTICE_LAYOUT)
        self.assertEqual([(c.role, c.lang) for c in post.columns], [("source", "en")])
        self.assertEqual(text_lines(post.rows[0].cells[0]), ["Think of it.", "Write it down.", "Let it go."])

    def test_a_quoted_text_is_transcluded_in_the_notes(self) -> None:
        post = parse(PRACTICE, PRACTICE_LAYOUT)
        self.assertEqual([transcluded_urn(line) or node_text(line) for line in post.notes],
                         ["It comes from Micah:", MICAH, "And so on."])

    def test_paths_are_read_before_the_layout_changes_the_post(self) -> None:
        # Wrapping the block in a table must not make "(//table)[1]" find the wrapper.
        layout = Layout(text=("(//div[@lang])[1]", "(//table)[1]"))
        post = parse(PRACTICE, layout)
        self.assertEqual([[c.lang for c in t.columns] for t in post.tables], [["en"], ["he", "en"]])

    def test_a_path_must_find_one_element(self) -> None:
        with self.assertRaisesRegex(ValueError, "finds 0 elements"):
            parse(PRACTICE, Layout(text=("//ol",)))

    def test_a_split_cell_must_have_every_part(self) -> None:
        layout = Layout(text=("(//table)[2]",), split={2: (None, "Translation (English)")})
        with self.assertRaisesRegex(ValueError, "has 4 parts, not 2"):
            parse(BLESSINGS, layout)


class TestBuilding(unittest.TestCase):
    def build(self, content: str, layout: Layout, urns: PostUrns, **flags) -> dict:
        post = parse(content, layout)
        credits = post_credits(post, Contributors.load(FIXTURES / "contributors_by_id.json"))
        out = {}
        for column in project_columns(post):
            files = build_project(
                post, column, urns=urns, credits=credits,
                licence=LicenceDecision("allow", LICENCES["cc-by-sa-4.0"]),
                upstream_commit="0123456789abcdef", upstream_commit_date="2026-10-01",
                project_id=f"a_song-{column.key.lower().replace('/', '-')}",
                **{name: flag(column) for name, flag in flags.items()},
            )
            out[column.key] = etree.fromstring(files.files["index"].encode("utf-8"))
        return out

    def test_each_language_has_its_own_introduction(self) -> None:
        indexes = self.build(BLESSINGS, BLESSINGS_LAYOUT, PostUrns(101, "new", URN),
                             with_front=lambda c: False, with_own_introduction=lambda c: c.key in ("en", "he"))
        intro = './/tei:front/tei:div[@subtype="introduction"]/tei:p'
        self.assertEqual([p.text for p in indexes["en"].iterfind(intro, NS)], ["Why we wrote it.", "And how."])
        self.assertEqual([p.text for p in indexes["he"].iterfind(intro, NS)], ["למה כתבנו.", "ואיך."])
        self.assertIsNone(indexes["he-Latn"].find(".//tei:front", NS))

    def test_a_transclusion_stands_in_the_notes(self) -> None:
        indexes = self.build(PRACTICE, PRACTICE_LAYOUT, PostUrns(101, "new", URN),
                             with_front=lambda c: True)
        notes = indexes["en"].find('.//tei:front/tei:div[@subtype="notes"]', NS)
        self.assertEqual([etree.QName(child).localname for child in notes], ["p", "transclude", "p"])
        self.assertEqual(notes[1].get("target"), MICAH)


if __name__ == "__main__":
    unittest.main()
