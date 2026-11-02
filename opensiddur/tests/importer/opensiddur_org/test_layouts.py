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
from opensiddur.importer.opensiddur_org.tei_builder import build_project, front_language
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


class TestReviewRegressions(unittest.TestCase):
    def test_a_split_part_is_in_the_language_its_header_names(self) -> None:
        post = parse(BLESSINGS, BLESSINGS_LAYOUT)
        self.assertEqual([c.lang for c in post.rows[0].cells], ["he", "en", "en", "he-Latn"])
        self.assertEqual([[b.kind for b in c.blocks] for c in post.rows[0].cells[1:]], [["paragraph"]] * 3)

    def test_a_split_keeps_markup_before_the_first_paragraph(self) -> None:
        content = ('<table><tr><td><div lang="heb-Hebr">א</div></td>'
                   '<td><div lang="eng-Latn">Tom &amp; <em>Jerry</em> 1&lt;2<p>Blessed</p></div></td></tr></table>')
        layout = Layout(text=("(//table)[1]",), split={2: ("Commentary (English)", "Translation (English)")})
        post = parse(content, layout)
        self.assertEqual(text_lines(post.rows[0].cells[1]), ["Tom & Jerry 1<2"])

    def test_a_split_keeps_the_other_columns_headers(self) -> None:
        content = ('<table><thead><tr><th>Source (Aramaic)</th><th>Translation (English)</th></tr></thead>'
                   '<tr><td><div lang="heb-Hebr">א</div></td>'
                   '<td><div lang="eng-Latn">Why<p>Blessed</p></div></td></tr></table>')
        layout = Layout(text=("(//table)[1]",), split={2: ("Commentary (English)", "Translation (English)")})
        self.assertEqual(parse(content, layout).columns[0].lang, "arc")

    def test_a_split_cell_with_more_than_its_div_is_an_error(self) -> None:
        content = ('<table><tr><td><div lang="heb-Hebr">א</div></td>'
                   '<td><div lang="eng-Latn">Why<p>Blessed</p></div>And more.</td></tr></table>')
        layout = Layout(text=("(//table)[1]",), split={2: ("Commentary (English)", "Translation (English)")})
        with self.assertRaisesRegex(ValueError, "not one div"):
            parse(content, layout)

    def test_a_note_after_the_text_without_a_link_stays_a_note(self) -> None:
        content = BLESSINGS + '<p>Sing it slowly.</p><p>DOWNLOAD: <a href="x.pdf">PDF</a></p>'
        post = parse(content, BLESSINGS_LAYOUT)
        self.assertEqual([node_text(line) for line in post.notes], ["Sing it slowly."])
        self.assertEqual([s.caption for s in post.sources], ["First published on a blog."])

    def test_a_wrapped_block_keeps_the_text_after_it(self) -> None:
        content = '<div lang="eng-Latn">Let it go.</div>Trailing words.<p>A note.</p>'
        post = parse(content, Layout(text=("(//div[@lang])[1]",)))
        self.assertEqual([node_text(line) for line in post.notes], ["Trailing words.", "A note."])

    def test_a_nested_transclusion_is_an_error(self) -> None:
        content = PRACTICE.replace("<table>", "<blockquote><table>").replace("</table>", "</table></blockquote>")
        layout = Layout(text=("(//div[@lang])[1]",), transclusions={"(//table)[1]": MICAH})
        with self.assertRaisesRegex(ValueError, "not at the post's top level"):
            parse(content, layout)

    def test_introduction_text_outside_its_languages_is_an_error(self) -> None:
        content = BLESSINGS.replace("</tr></table>", "<td>Loose words</td></tr></table>", 1)
        with self.assertRaisesRegex(ValueError, "text outside its div"):
            parse(content, BLESSINGS_LAYOUT)

    def test_an_introduction_needs_its_text(self) -> None:
        with self.assertRaisesRegex(ValueError, "beside the text"):
            parse(BLESSINGS, Layout(introduction="(//table)[1]"))

    def test_notes_of_only_a_transclusion_are_placed(self) -> None:
        content = '<div lang="eng-Latn">Let it go.</div><table><tr><td><div lang="heb-Hebr">א</div></td></tr></table>'
        post = parse(content, Layout(text=("(//div[@lang])[1]",), transclusions={"(//table)[1]": MICAH}))
        self.assertEqual(front_language(post, ["en"]), "en")


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

    def test_a_split_transliteration_is_not_marked_english(self) -> None:
        post = parse(BLESSINGS, BLESSINGS_LAYOUT)
        credits = post_credits(post, Contributors.load(FIXTURES / "contributors_by_id.json"))
        column = next(c for c in project_columns(post) if c.key == "he-Latn")
        files = build_project(
            post, column, urns=PostUrns(101, "new", URN), credits=credits,
            licence=LicenceDecision("allow", LICENCES["cc-by-sa-4.0"]),
            upstream_commit="0123456789abcdef", upstream_commit_date="2026-10-01",
            with_front=False, project_id="a_song-he-latn",
        )
        text = next(doc for stem, doc in files.files.items() if stem != "index")
        self.assertNotIn('xml:lang="en"', text.split("<tei:text>", 1)[1])

    def test_a_transclusion_stands_in_the_notes(self) -> None:
        indexes = self.build(PRACTICE, PRACTICE_LAYOUT, PostUrns(101, "new", URN),
                             with_front=lambda c: True)
        notes = indexes["en"].find('.//tei:front/tei:div[@subtype="notes"]', NS)
        self.assertEqual([etree.QName(child).localname for child in notes], ["p", "transclude", "p"])
        self.assertEqual(notes[1].get("target"), MICAH)


if __name__ == "__main__":
    unittest.main()
