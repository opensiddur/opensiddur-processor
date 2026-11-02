import unittest

from opensiddur.importer.opensiddur_org.parse_post import (
    safe_uri,
    FootnoteRef,
    Span,
    Text,
    licence_url,
    node_text,
    parse_coauthor,
    parse_post,
    post_id_from_path,
    split_title,
)
from opensiddur.importer.opensiddur_org.post_decisions import NO_DECISIONS, PostDecisions
from opensiddur.tests.importer.opensiddur_org.support import (
    HEBREW_EN_ROWS,
    cell,
    make_post,
    table,
    two_column_content,
)


def kinds(nodes) -> list[str]:
    return [n.kind for n in nodes if isinstance(n, Span)]


class TestMetadata(unittest.TestCase):
    def test_title_parts_drop_emoji(self) -> None:
        self.assertEqual(split_title("&#x1F4AC; שִׁירָה | A Song"), ["שִׁירָה", "A Song"])

    def test_licence_url(self) -> None:
        self.assertEqual(
            licence_url("<a href='https://creativecommons.org/licenses/by/4.0/'>CC BY</a>"),
            "https://creativecommons.org/licenses/by/4.0/",
        )
        self.assertEqual(licence_url(""), "")
        self.assertEqual(licence_url("<a href='//creativecommons.org/x/'>x</a>"), "https://creativecommons.org/x/")

    def test_coauthor_qualifier(self) -> None:
        coauthor = parse_coauthor({"name": "Rivka (transcription &amp; naqdanut)",
                                   "profile_link": "https://opensiddur.org/profile/rivka-t"})
        self.assertEqual(coauthor.name, "Rivka")
        self.assertEqual(coauthor.qualifier, "transcription & naqdanut")
        self.assertEqual(coauthor.profile_slug, "rivka-t")

    def test_post_id_from_export_path(self) -> None:
        self.assertEqual(post_id_from_path("posts/prayers/x/some-slug_(12345).json"), 12345)
        self.assertIsNone(post_id_from_path("posts/posts.json"))

    def test_source_dates(self) -> None:
        post = parse_post(make_post(date_src=("1440-00-00", "1500-00-00")))
        self.assertEqual((post.date_src_start, post.date_src_end), ("1440-00-00", "1500-00-00"))


class TestTable(unittest.TestCase):
    def setUp(self) -> None:
        self.post = parse_post(make_post())

    def test_columns(self) -> None:
        self.assertEqual([(c.role, c.lang) for c in self.post.columns], [("source", "he"), ("translation", "en")])

    def test_lines_and_stanza_gaps(self) -> None:
        hebrew = self.post.rows[1].cells[0]
        self.assertEqual([b.kind for b in hebrew.blocks], ["stanza", "stanza"])
        self.assertEqual([node_text(line) for line in hebrew.blocks[0].lines], ["אשִׁירָה", "לְךָ"])
        self.assertEqual([node_text(line) for line in hebrew.blocks[1].lines], ["שִׁיר שֵׁנִי"])

    def test_semantic_spans(self) -> None:
        english = self.post.rows[0].cells[1].blocks[0]
        self.assertEqual(kinds(english.lines[1]), ["divine", "divine"])
        self.assertEqual(node_text(english.lines[1]), "Adonai our God")
        self.assertEqual(kinds(self.post.rows[1].cells[0].blocks[0].lines[0]), ["acrostic"])
        self.assertIn("citation", kinds(self.post.rows[1].cells[1].blocks[1].lines[0]))
        self.assertEqual(kinds(self.post.rows[1].cells[1].blocks[0].lines[0]), ["italic"])

    def test_intro(self) -> None:
        self.assertEqual([node_text(line) for line in self.post.intro], ["An introduction."])

    def test_text_is_stored_decomposed(self) -> None:
        import unicodedata

        text = node_text(self.post.rows[0].cells[0].blocks[0].lines[0])
        self.assertEqual(text, unicodedata.normalize("NFKD", text))


class TestFootnotes(unittest.TestCase):
    def test_footnote_text_comes_from_the_tooltip(self) -> None:
        body = (
            'To You<span class="footnote_referrer"><a><sup>[1]</sup></a>'
            '<span class="footnote_tooltip"> A <em>note</em>.&nbsp;</span></span>'
            "<script type=\"text/javascript\"> jQuery('#x').tooltip({ tip: '#y' });</script>"
        )
        post = parse_post(make_post(content=table(["Translation (English)"], [[cell("eng-Latn", "english", body)]])))
        line = post.rows[0].cells[0].blocks[0].lines[0]
        notes = [n for n in line if isinstance(n, FootnoteRef)]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].number, 1)
        self.assertEqual(node_text(notes[0].note), "A note.")
        self.assertEqual(node_text(line), "To You")
        self.assertNotIn("jQuery", node_text(line))


class TestIrregularLayouts(unittest.TestCase):
    def test_three_columns_with_transliteration(self) -> None:
        rows = [[cell("heb-Hebr", "liturgy", "שָׁלוֹם"),
                 cell("eng-Latn", "romanized-transliteration", "shalom"),
                 cell("eng-Latn", "english", "peace")]]
        post = parse_post(make_post(content=table(
            ["Source (Hebrew)", "Transliteration (romanized Hebrew)", "Translation (English)"], rows)))
        self.assertEqual([c.lang for c in post.columns], ["he", "he-Latn", "en"])
        # The header names a language the markup contradicts.
        self.assertTrue(post.columns[1].mismatch)

    def test_transliteration_markup_without_its_script(self) -> None:
        rows = [[cell("jrb", "romanized-transliteration", "salam")]]
        post = parse_post(make_post(content=table(["Transliteration (Judeo-Arabic)"], rows)))
        self.assertEqual(post.columns[0].lang, "jrb-Latn")
        self.assertEqual(post.columns[0].mismatch, "")

    def test_empty_contribute_column(self) -> None:
        rows = [[cell("heb-Hebr", "liturgy", ""), cell("eng-Latn", "english", "A prayer")]]
        post = parse_post(make_post(content=table(["Contribute a translation", "Source (English)"], rows)))
        self.assertEqual(post.columns[0].role, "contribute")
        self.assertTrue(post.rows[0].cells[0].is_empty)

    def test_contribute_column_with_text_is_a_source(self) -> None:
        rows = [[cell("heb-Hebr", "liturgy", "שָׁלוֹם"), cell("eng-Latn", "english", "Peace")]]
        post = parse_post(make_post(content=table(["Contribute a translation", "Source (English)"], rows)))
        self.assertEqual((post.columns[0].role, post.columns[0].lang), ("source", "he"))

    def test_paragraph_cells_are_prose(self) -> None:
        rows = [[cell("eng-Latn", "english", "<p>One paragraph.</p><p>Another.</p>")]]
        post = parse_post(make_post(content=table(["Source (English)"], rows)))
        self.assertEqual([b.kind for b in post.rows[0].cells[0].blocks], ["paragraph", "paragraph"])

    def test_heading_in_a_cell(self) -> None:
        rows = [[cell("eng-Latn", "english", "<h3>Part One</h3>")], [cell("eng-Latn", "english", "Text")]]
        post = parse_post(make_post(content=table(["Source (English)"], rows)))
        self.assertEqual(post.rows[0].cells[0].blocks[0].kind, "heading")

    def test_short_rows_are_padded(self) -> None:
        rows = [[cell("heb-Hebr", "liturgy", "שָׁלוֹם")]]
        post = parse_post(make_post(content=table(["Source (Hebrew)", "Translation (English)"], rows)))
        self.assertEqual(len(post.rows[0].cells), 2)
        self.assertTrue(post.rows[0].cells[1].is_empty)

    def test_colour_alignment_is_noticed(self) -> None:
        rows = [[cell("eng-Latn", "english", '<span style="color: #f00">red</span> words')]]
        post = parse_post(make_post(content=table(["Source (English)"], rows)))
        self.assertTrue(post.has_colour_alignment)


class TestSurroundings(unittest.TestCase):
    def test_notes_and_sources(self) -> None:
        content = two_column_content(notes="<p>Published in 1842.</p>") + (
            "<h3>Source(s)</h3>"
            '<div class="wp-caption"><a href="https://opensiddur.org/scan.jpg"><img src="t.jpg" /></a>'
            '<p class="wp-caption-text">Page 21</p></div>'
            "<style>.x{}</style><script>var x;</script>"
            '<iframe src="https://archive.org/stream/book#page/20"></iframe>'
        )
        post = parse_post(make_post(content=content))
        self.assertEqual([node_text(line) for line in post.notes], ["Published in 1842."])
        self.assertEqual([(s.caption, s.url) for s in post.sources], [
            ("Page 21", "https://opensiddur.org/scan.jpg"),
            ("", "https://archive.org/stream/book#page/20"),
        ])

    def test_prose_post_without_a_table(self) -> None:
        post = parse_post(make_post(content='<p>Intro</p><div class="english" lang="eng-Latn">A prayer<br />in lines</div><p>After</p>'))
        self.assertEqual([(c.role, c.lang) for c in post.columns], [("source", "en")])
        self.assertEqual(len(post.rows), 1)
        self.assertEqual([node_text(line) for line in post.intro], ["Intro"])
        self.assertEqual([node_text(line) for line in post.notes], ["After"])

    def test_alternating_prose_blocks_pair_into_rows(self) -> None:
        post = parse_post(make_post(content='<div lang="eng-Latn">A</div><div lang="heb-Hebr">א</div>'
                                            '<div lang="eng-Latn">B</div><div lang="heb-Hebr">ב</div>'))
        self.assertEqual([(c.role, c.lang) for c in post.columns], [("translation", "en"), ("source", "he")])
        self.assertEqual([[node_text(c.blocks[0].lines[0]) for c in row.cells] for row in post.rows],
                         [["A", "א"], ["B", "ב"]])

    def test_file_links_and_embeds(self) -> None:
        post = parse_post(make_post(content='<p><a class="mtli_attachment mtli_pdf" href="https://x/y.pdf">PDF</a></p>'))
        self.assertEqual(post.file_links, ["https://x/y.pdf"])

    def test_rows_fixture_is_unchanged(self) -> None:
        # Guards the shared fixture the other tests rely on.
        self.assertEqual(len(HEBREW_EN_ROWS), 2)
        self.assertIsInstance(parse_post(make_post()).rows[0].cells[0].blocks[0].lines[0][0], Text)



class TestReviewRegressions(unittest.TestCase):
    def english(self, body: str, *, before: str = "", after: str = ""):
        return parse_post(make_post(content=before + table(["Source (English)"], [[cell("eng-Latn", "english", body)]]) + after))

    def test_spaces_at_span_edges_survive(self) -> None:
        line = self.english("in<em> Midrash Abkir</em> and <em>dreidel </em>at").rows[0].cells[0].blocks[0].lines[0]
        self.assertEqual(node_text(line), "in Midrash Abkir and dreidel at")

    def test_space_only_span_is_just_a_space(self) -> None:
        line = self.english("a<strong> </strong>b").rows[0].cells[0].blocks[0].lines[0]
        self.assertEqual((node_text(line), kinds(line)), ("a b", []))

    def test_line_edges_are_trimmed_inside_spans(self) -> None:
        line = self.english("<em> edge </em>").rows[0].cells[0].blocks[0].lines[0]
        self.assertEqual(node_text(line), "edge")

    def test_footnote_container_is_not_notes(self) -> None:
        after = ('<hr /><p>A real note.</p><div class="speaker-mute footnotes_reference_container">'
                 '<div class="footnote_container_prepare"><p>Notes</p></div>'
                 '<table class="footnotes_table footnote-reference-container"><tr><td>1</td><td>dup</td></tr></table></div>')
        post = self.english("Text", after=after)
        self.assertEqual([node_text(line) for line in post.notes], ["A real note."])

    def test_a_sources_heading_in_the_introduction(self) -> None:
        post = self.english("Text", before="<h3>About the source</h3><p>Intro.</p>", after="<hr /><p>Afterword.</p>")
        self.assertEqual([node_text(line) for line in post.notes], ["Afterword."])

    def test_entities_are_decoded_once(self) -> None:
        line = self.english("a &amp;lt;b&amp;gt; c").rows[0].cells[0].blocks[0].lines[0]
        self.assertEqual(node_text(line), "a &lt;b&gt; c")

    def test_explicit_non_latin_script_under_a_transliteration_header(self) -> None:
        # Markup that names a script on purpose wins over the header (post 53572).
        post = parse_post(make_post(content=table(["Transliteration (Judeo-Arabic)"], [[cell("jrb-Hebr", "judeo-arabic", "שלאם")]])))
        self.assertEqual(post.columns[0].lang, "jrb")
        self.assertTrue(post.columns[0].mismatch)


class TestSafeUri(unittest.TestCase):
    def test_a_second_fragment_is_encoded(self) -> None:
        self.assertEqual(safe_uri("https://x.org/a/embed/#?secret=1#?secret=2"),
                         "https://x.org/a/embed/#?secret=1%23?secret=2")

    def test_spaces_are_encoded(self) -> None:
        self.assertEqual(safe_uri(" https://x.org/a b.pdf "), "https://x.org/a%20b.pdf")

    def test_a_stray_percent_is_encoded(self) -> None:
        self.assertEqual(safe_uri("https://x.org/a%28b%2#page/1"), "https://x.org/a%28b%252#page/1")


class TestColumnRules(unittest.TestCase):
    def lang(self, header: str, markup: str, decisions: PostDecisions = NO_DECISIONS) -> str:
        post = parse_post(make_post(content=table([header], [[cell(markup, "x", "text")]])), decisions)
        return post.columns[0].lang

    def test_default_markup_loses_to_the_header(self) -> None:
        self.assertEqual(self.lang("Source (Aramaic)", "heb-Hebr"), "arc")
        self.assertEqual(self.lang("Translation (Romanian)", "eng-Latn"), "ro")

    def test_a_jewish_variety_in_the_header_wins(self) -> None:
        self.assertEqual(self.lang("Source (Ladino)", "spa-Latn"), "lad")
        self.assertEqual(self.lang("Translation (Judeo-Italian)", "ita"), "itk")

    def test_chosen_markup_wins(self) -> None:
        self.assertEqual(self.lang("Source (Hebrew)", "yid-Hebr"), "yi")
        self.assertEqual(self.lang("Source (Arabic)", "jye"), "jye")

    def test_a_decision_wins_over_both(self) -> None:
        decisions = PostDecisions(column_languages={101: {"Source (Aramaic)": "arc"}})
        self.assertEqual(self.lang("Source (Aramaic)", "txb-Hebr", decisions), "arc")
        self.assertEqual(self.lang("Source (Aramaic)", "txb-Hebr"), "txb-Hebr")

    def test_transliteration_naming_no_language_romanizes_the_source(self) -> None:
        rows = [[cell("heb-Hebr", "liturgy", "שלום"), cell("eng-Latn", "x", "shalom")]]
        post = parse_post(make_post(content=table(["Source (Hebrew)", "Transliteration (Romanization)"], rows)))
        self.assertEqual(post.columns[1].lang, "he-Latn")

    def test_header_names(self) -> None:
        self.assertEqual(self.lang("Translation (Bukhori/Cyrillic)", "eng-Latn"), "bhh-Cyrl")
        self.assertEqual(self.lang("Translation (English, 1852)", "eng-Latn"), "en")
        self.assertEqual(self.lang("Hebraization (Judeo-Old Norse)", "heb-Hebr"), "non-Hebr")

    def test_variant_names_come_from_the_header(self) -> None:
        rows = [[cell("eng-Latn", "x", "A"), cell("eng-Latn", "x", "B"), cell("eng-Latn", "x", "C")]]
        post = parse_post(make_post(content=table(
            ["Translation, 2022 (English)", "Translation, 1852 (English)", "Translation (English)"], rows)))
        self.assertEqual([c.key for c in post.columns], ["en", "en/1852", "en/3"])

    def test_a_table_with_no_headers(self) -> None:
        headed = table(["Source (Hebrew)", "Adaptation (English)"], [[cell("heb-Hebr", "x", "א"), cell("eng-Latn", "x", "A")]])
        bare = table(["", ""], [[cell("heb-Hebr", "x", "ב"), cell("eng-Latn", "x", "B")]])
        post = parse_post(make_post(content=headed + bare))
        self.assertEqual([c.role for c in post.tables[1].columns], ["source", "adaptation"])
        post = parse_post(make_post(content=table(["", ""], [[cell("eng-Latn", "x", "B"), cell("heb-Hebr", "x", "ב")]])))
        self.assertEqual([c.role for c in post.columns], ["translation", "source"])

    def test_initials_mark_the_acrostic(self) -> None:
        rows = [[cell("heb-Hebr", "x", "א"), cell("heb-Hebr", "liturgy", "אֲשִׁירָה לְךָ")]]
        post = parse_post(make_post(content=table(["Initials (Hebrew)", "Source (Hebrew)"], rows)))
        first = post.rows[0].cells[1].blocks[0].lines[0][0]
        self.assertEqual((first.kind, node_text(first.children)), ("acrostic", "אֲ"))


if __name__ == "__main__":
    unittest.main()
