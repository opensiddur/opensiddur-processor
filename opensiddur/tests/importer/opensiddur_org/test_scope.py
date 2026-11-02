import json
import unittest

from opensiddur.importer.opensiddur_org.parse_post import parse_post
from opensiddur.importer.opensiddur_org.scope import (
    content_scope,
    descendant_categories,
    imported_columns,
    irregularities,
    is_heading_row,
    posts_in_categories,
    project_columns,
)
from opensiddur.importer.opensiddur_org.post_decisions import PostDecisions
from opensiddur.tests.importer.opensiddur_org.support import FIXTURES, cell, make_post, table


class TestCategories(unittest.TestCase):
    def setUp(self) -> None:
        self.categories = json.loads((FIXTURES / "categories.json").read_text(encoding="utf-8"))

    def test_descendants(self) -> None:
        self.assertEqual(descendant_categories(self.categories, {1132}), {1132, 200, 201})
        self.assertEqual(descendant_categories(self.categories, {200}), {200, 201})

    def test_posts(self) -> None:
        self.assertEqual(posts_in_categories(self.categories, {200, 201}), {101, 102, 103, 104, 105})


class TestContentScope(unittest.TestCase):
    def test_table_with_text(self) -> None:
        self.assertTrue(content_scope(parse_post(make_post())).in_scope)

    def test_index_post(self) -> None:
        scope = content_scope(parse_post(make_post(slug="list-of-prayers")))
        self.assertEqual((scope.in_scope, scope.reason), (False, "index post"))

    def test_prose_body_is_read_as_a_table(self) -> None:
        post = parse_post(make_post(content='<div class="english" lang="eng-Latn">A prayer</div>'))
        self.assertEqual(content_scope(post).reason, "table")

    def test_prose_that_is_no_table(self) -> None:
        post = parse_post(make_post(content='<div lang="heb-Hebr">א</div><div lang="heb-Hebr">ב</div>'
                                            '<div lang="eng-Latn">A</div>'))
        self.assertEqual(content_scope(post).reason, "prose")

    def test_out_of_scope_by_decision(self) -> None:
        decisions = PostDecisions(out_of_scope={101: "shiviti art"})
        scope = content_scope(parse_post(make_post(101)), decisions)
        self.assertEqual((scope.in_scope, scope.reason), (False, "shiviti art"))
        self.assertTrue(content_scope(parse_post(make_post(102)), decisions).in_scope)

    def test_file_link_only(self) -> None:
        post = parse_post(make_post(content='<p>See <a class="mtli_pdf" href="https://x/y.pdf">the PDF</a>.</p>'))
        self.assertEqual((content_scope(post).in_scope, content_scope(post).reason), (False, "file link only"))

    def test_embed_only(self) -> None:
        post = parse_post(make_post(content='<iframe src="https://archive.org/embed/x"></iframe>'))
        self.assertEqual(content_scope(post).reason, "embed only")

    def test_essay(self) -> None:
        post = parse_post(make_post(content="<p>Some thoughts on prayer.</p>"))
        self.assertEqual(content_scope(post).reason, "no prayer text")

    def test_only_an_empty_contribute_column_is_not_text(self) -> None:
        rows = [[cell("heb-Hebr", "liturgy", "")]]
        post = parse_post(make_post(content=table(["Contribute a translation"], rows)))
        self.assertFalse(content_scope(post).in_scope)


class TestIrregularities(unittest.TestCase):
    def test_standard_post(self) -> None:
        self.assertEqual(irregularities(parse_post(make_post())), [])

    def test_source_only_post_is_standard(self) -> None:
        rows = [[cell("heb-Hebr", "liturgy", ""), cell("eng-Latn", "english", "A prayer")]]
        post = parse_post(make_post(content=table(["Contribute a translation", "Source (English)"], rows)))
        self.assertEqual(irregularities(post), [])
        self.assertEqual([c.lang for _, c in imported_columns(post)], ["en"])

    def test_header_and_markup_disagree_is_resolved(self) -> None:
        rows = [[cell("heb-Hebr", "liturgy", "שלום"), cell("eng-Latn", "romanized-transliteration", "shalom")]]
        post = parse_post(make_post(content=table(["Source (Hebrew)", "Transliteration (romanized Hebrew)"], rows)))
        self.assertEqual(irregularities(post), [])
        self.assertEqual(post.columns[1].lang, "he-Latn")

    def test_two_columns_in_one_language_are_two_projects(self) -> None:
        rows = [[cell("eng-Latn", "english", "One"), cell("eng-Latn", "english", "Two")]]
        post = parse_post(make_post(content=table(["Translation (English)", "Literal Translation (English)"], rows)))
        self.assertEqual(irregularities(post), [])
        self.assertEqual([c.key for c in project_columns(post)], ["en", "en/literal"])

    def test_verse_and_prose_in_one_column(self) -> None:
        rows = [[cell("eng-Latn", "english", "A line<br />another")],
                [cell("eng-Latn", "english", "<p>A paragraph.</p>")]]
        post = parse_post(make_post(content=table(["Source (English)"], rows)))
        self.assertEqual(irregularities(post), [])

    def test_columns_that_are_not_texts(self) -> None:
        rows = [[cell("heb-Hebr", "liturgy", "א"), cell("heb-Hebr", "liturgy", "אשירה"),
                 cell("eng-Latn", "english", "I sing"), cell("eng-Latn", "english", "A note")]]
        post = parse_post(make_post(content=table(
            ["Initials (Hebrew)", "Source (Hebrew)", "Translation (English)", "Commentary (English)"], rows)))
        self.assertEqual([c.key for c in project_columns(post)], ["he", "en"])
        self.assertEqual(irregularities(post), [])

    def test_several_tables(self) -> None:
        first = table(["Source (Hebrew)", "Translation (English)"], [[cell("heb-Hebr", "liturgy", "א"), cell("eng-Latn", "english", "A")]])
        second = table(["Source (Hebrew)"], [[cell("heb-Hebr", "liturgy", "ב")]])
        post = parse_post(make_post(content=first + "<p>Between</p>" + second))
        self.assertEqual(len(post.tables), 2)
        self.assertEqual([c.key for c in project_columns(post)], ["he", "en"])
        self.assertEqual(irregularities(post), [])

    def test_heading_rows_are_sections(self) -> None:
        rows = [[cell("eng-Latn", "english", "<h3>Part One</h3>")], [cell("eng-Latn", "english", "Text")]]
        post = parse_post(make_post(content=table(["Source (English)"], rows)))
        self.assertTrue(is_heading_row(post, 0))
        self.assertEqual(irregularities(post), [])

    def test_heading_beside_text(self) -> None:
        rows = [[cell("eng-Latn", "english", "<h3>Part One</h3><p>Text</p>")]]
        post = parse_post(make_post(content=table(["Source (English)"], rows)))
        self.assertEqual(irregularities(post), [])

    def test_prose_without_a_table(self) -> None:
        post = parse_post(make_post(content='<div class="english" lang="eng-Latn">A prayer</div>'))
        self.assertEqual(irregularities(post), [])

    def test_prose_blocks_that_do_not_alternate(self) -> None:
        post = parse_post(make_post(content='<div lang="heb-Hebr">א</div><div lang="heb-Hebr">ב</div>'
                                            '<div lang="eng-Latn">A</div>'))
        self.assertEqual(irregularities(post), ["prose blocks that do not alternate languages"])

    def test_text_between_prose_blocks(self) -> None:
        post = parse_post(make_post(content='<div lang="eng-Latn">A prayer</div><p>An essay about it.</p>'
                                            '<div lang="eng-Latn">Another</div>'))
        self.assertEqual(irregularities(post), ["text between its blocks"])

    def test_colour_coded_text(self) -> None:
        rows = [[cell("eng-Latn", "english", '<span style="color: red">x</span>')]]
        post = parse_post(make_post(content=table(["Source (English)"], rows)))
        self.assertIn("colour-coded text: red", irregularities(post))

    def test_colours_with_a_meaning_are_regular(self) -> None:
        rows = [[cell("eng-Latn", "english", '<span style="color: red">x</span>')]]
        post = parse_post(make_post(content=table(["Source (English)"], rows)),
                          PostDecisions(colours={101: {"red": "none"}}))
        self.assertEqual(irregularities(post), [])


if __name__ == "__main__":
    unittest.main()
