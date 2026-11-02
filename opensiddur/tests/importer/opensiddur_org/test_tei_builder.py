import re
import unittest

from lxml import etree

from opensiddur.importer.opensiddur_org.contributors import Contributors, post_credits
from opensiddur.importer.opensiddur_org.licences import LICENCES, LicenceDecision
from opensiddur.importer.opensiddur_org.parse_post import node_text, parse_post
from opensiddur.importer.opensiddur_org.post_decisions import NO_DECISIONS, PostDecisions
from opensiddur.importer.opensiddur_org.scope import project_columns
from opensiddur.importer.opensiddur_org.tei_builder import (
    build_project,
    front_language,
    iso_date,
    text_file_stem,
)
from opensiddur.importer.opensiddur_org.urns import PostUrns
from opensiddur.importer.util.prettify import prettify_xml
from opensiddur.importer.util.validation import validate
from opensiddur.tests.importer.opensiddur_org.support import (
    FIXTURES,
    PRINT_TRANSLATOR,
    TRANSCRIBER,
    TRANSLATOR,
    cell,
    make_post,
    table,
    two_column_content,
)

NS = {"tei": "http://www.tei-c.org/ns/1.0", "j": "http://jewishliturgy.org/ns/jlptei/2"}
URN = "urn:x-opensiddur:text:prayer:a_song"
ALLOW = LicenceDecision("allow", LICENCES["cc-by-sa-4.0"])


def project_id(lang: str) -> str:
    return f"a_song-poet-2020-{lang.lower()}"


def build(post_data=None, *, urns: PostUrns | None = None, licence: LicenceDecision = ALLOW, with_front=None,
          decisions: PostDecisions = NO_DECISIONS, with_essay: str = "en"):
    post = parse_post(post_data or make_post(), decisions)
    contributors = Contributors.load(FIXTURES / "contributors_by_id.json")
    credits = post_credits(post, contributors)
    urns = urns or PostUrns(post.post_id, "new", URN)
    out = {}
    for column in project_columns(post):
        files = build_project(
            post, column, urns=urns, credits=credits, licence=licence,
            upstream_commit="0123456789abcdef", upstream_commit_date="2026-10-01",
            with_front=column.lang == "en" if with_front is None else with_front,
            project_id=project_id(column.key.replace("/", "-")),
            with_essay=column.key == with_essay,
        )
        out[column.key] = files
    return post, out


def compact(document: str) -> str:
    return re.sub(r">\s*\n\s*<", "><", document)


def tree(document: str):
    return etree.fromstring(prettify_xml(compact(document), keep_blank_text=True).encode("utf-8"))


class TestDocuments(unittest.TestCase):
    def setUp(self) -> None:
        self.post, self.projects = build()

    def text_of(self, lang: str):
        files = self.projects[lang].files
        return tree(files[text_file_stem(URN)])

    def test_project_per_language(self) -> None:
        self.assertEqual(sorted(self.projects), ["en", "he"])
        self.assertEqual(self.projects["en"].project_id, "a_song-poet-2020-en")
        self.assertEqual(sorted(self.projects["en"].files), ["a_song", "index"])

    def test_text_file_is_named_from_the_urn(self) -> None:
        self.assertEqual(text_file_stem(URN), "a_song")
        self.assertEqual(text_file_stem("urn:x-opensiddur:text:poem:maoz_tzur/1@p-he#x"), "maoz_tzur_1")

    def test_every_document_validates(self) -> None:
        for lang, files in self.projects.items():
            for name, document in files.files.items():
                valid, errors = validate(prettify_xml(compact(document), remove_xml_declaration=True, keep_blank_text=True))
                self.assertTrue(valid, f"{lang}/{name}: {errors}")

    def test_rows_align_across_languages(self) -> None:
        def milestones(lang):
            return [m.get("corresp") for m in self.text_of(lang).iterfind(".//tei:milestone", NS)]

        self.assertEqual(milestones("he"), [f"{URN}/1", f"{URN}/2"])
        self.assertEqual(milestones("he"), milestones("en"))

    def test_stanza_gap_splits_line_groups(self) -> None:
        self.assertEqual(len(self.text_of("he").findall(".//tei:lg", NS)), 3)

    def test_inline_markup(self) -> None:
        english = self.text_of("en")
        self.assertEqual([d.text for d in english.iterfind(".//j:divineName", NS)], ["Adonai", "our God"])
        # The space between two adjacent names survives pretty-printing.
        line = english.find(".//tei:l[2]", NS)
        self.assertEqual("".join(line.itertext()), "Adonai our God")
        self.assertEqual(english.find(".//tei:hi[@rend='italic']", NS).text, "sing")
        self.assertEqual(english.find(".//tei:body//tei:bibl", NS).text, "(Psalms 1:1)")
        self.assertEqual(self.text_of("he").find(".//tei:seg[@type='acrostic']", NS).text, "א")

    def test_header_points_at_the_index(self) -> None:
        ptr = self.text_of("en").find(".//tei:sourceDesc/tei:bibl/tei:ptr", NS)
        self.assertEqual(ptr.get("target"), "/a_song-poet-2020-en/index#project_source_bibl")

    def test_index_bibl(self) -> None:
        index = tree(self.projects["en"].files["index"])
        bibl = index.find(".//tei:bibl[@{http://www.w3.org/XML/1998/namespace}id='project_source_bibl']", NS)
        self.assertEqual(bibl.find("tei:author", NS).text, "Yehudah Poet")
        # Cited by post ID first, so the bibliography's link survives a category move.
        self.assertEqual(bibl.find("tei:idno[@type='url']", NS).text, "https://opensiddur.org/?p=101")
        self.assertEqual(bibl.find("tei:idno[@type='opensiddur.org']", NS).text, "101")
        # The permalink changes when the post moves category, so it is not kept.
        self.assertIsNone(bibl.find("tei:idno[@type='permalink']", NS))
        self.assertEqual(len(bibl.findall("tei:idno[@type='url']", NS)), 1)
        self.assertEqual(bibl.find("tei:date[@type='accessed']", NS).get("when"), "2026-10-01")
        transclude = index.find(".//j:transclude", NS)
        self.assertEqual(transclude.get("target"), URN)

    def test_titles(self) -> None:
        titles = tree(self.projects["en"].files["index"]).findall(".//tei:titleStmt/tei:title", NS)
        self.assertEqual([(t.get("type"), t.text) for t in titles], [("alt", "שִׁירָה"), ("main", "A Song")])

    def test_front_matter_is_gated_paratext(self) -> None:
        index = tree(self.projects["en"].files["index"])
        condition = index.find(".//tei:front/j:conditional//tei:fs", NS)
        self.assertEqual(condition.get("type"), "opensiddur:paratext")
        self.assertIsNone(tree(self.projects["he"].files["index"]).find(".//tei:front", NS))

    def test_the_posts_own_words_are_a_colophon(self) -> None:
        post, projects = build(make_post(content=two_column_content(notes="<p>First published in 1842.</p>")))
        divs = tree(projects["en"].files["index"]).findall(".//tei:front/tei:div", NS)
        self.assertEqual([(d.get("type"), d.get("subtype")) for d in divs],
                         [("colophon", "introduction"), ("colophon", "notes")])


class TestCredits(unittest.TestCase):
    def resp(self, files):
        return [(r.find("tei:resp", NS).get("key"), r.find("tei:name", NS).get("ref"))
                for r in tree(files.files["index"]).findall(".//tei:titleStmt/tei:respStmt", NS)]

    def test_credits_by_column(self) -> None:
        _, projects = build(make_post(coauthors=[TRANSLATOR, TRANSCRIBER]))
        person = "urn:x-opensiddur:contributor:opensiddur.org/rivka-translator"
        self.assertEqual(self.resp(projects["en"]), [("trl", person)])
        self.assertEqual(self.resp(projects["he"]), [("trc", person)])

    def test_print_translator_is_credited_in_the_bibl(self) -> None:
        _, projects = build(make_post(coauthors=[PRINT_TRANSLATOR]))
        index = tree(projects["en"].files["index"])
        self.assertEqual(self.resp(projects["en"]), [])
        self.assertEqual(index.find(".//tei:sourceDesc//tei:respStmt/tei:name", NS).text, "Old Print Translator")


class TestOther(unittest.TestCase):
    def test_existing_urns(self) -> None:
        urns = PostUrns(101, "existing", "urn:x-opensiddur:text:poem:song",
                        {1: "urn:x-opensiddur:text:poem:song/1", 2: "urn:x-opensiddur:text:poem:song/2"})
        post, projects = build(urns=urns)
        text = tree(projects["he"].files["song"])
        self.assertEqual(text.find(".//tei:div", NS).get("corresp"), "urn:x-opensiddur:text:poem:song")
        self.assertEqual([m.get("corresp") for m in text.iterfind(".//tei:milestone", NS)],
                         ["urn:x-opensiddur:text:poem:song/1", "urn:x-opensiddur:text:poem:song/2"])

    def test_footnotes_are_standoff(self) -> None:
        body = 'You<span class="footnote_referrer"><a><sup>[1]</sup></a><span class="footnote_tooltip">A note.</span></span>'
        post, projects = build(make_post(content=table(["Translation (English)"], [[cell("eng-Latn", "english", body)]])))
        text = tree(projects["en"].files[text_file_stem(URN)])
        self.assertIsNotNone(text.find(".//tei:l/tei:anchor[@{http://www.w3.org/XML/1998/namespace}id='note_1']", NS))
        note = text.find("tei:standOff[@type='notes']/tei:note", NS)
        self.assertEqual((note.get("target"), note.find("tei:p", NS).text), ("#note_1", "A note."))

    def test_heading_rows_open_sections(self) -> None:
        rows = [[cell("eng-Latn", "english", "<h3>Part One</h3>")], [cell("eng-Latn", "english", "Text")]]
        post, projects = build(make_post(content=table(["Source (English)"], rows)))
        text = tree(projects["en"].files[text_file_stem(URN)])
        self.assertEqual(text.find(".//tei:div/tei:div/tei:head", NS).text, "Part One")
        self.assertEqual([m.get("corresp") for m in text.iterfind(".//tei:milestone", NS)], [f"{URN}/1"])

    def test_prose_uses_paragraph_milestones(self) -> None:
        rows = [[cell("eng-Latn", "english", "<p>One.</p>")]]
        post, projects = build(make_post(content=table(["Source (English)"], rows)))
        text = tree(projects["en"].files[text_file_stem(URN)])
        self.assertEqual(text.find(".//tei:milestone", NS).get("unit"), "paragraph")

    def test_licence_basis(self) -> None:
        decision = LicenceDecision("allow", LICENCES["pd-mark-1.0"], "United States Government work")
        _, projects = build(licence=decision)
        availability = tree(projects["he"].files["index"]).find(".//tei:availability", NS)
        self.assertEqual(availability.find("tei:licence", NS).get("target"), LICENCES["pd-mark-1.0"].url)
        self.assertEqual(availability.find("tei:p", NS).text, "United States Government work")

    def test_partial_dates(self) -> None:
        self.assertEqual(iso_date("1440-00-00"), "1440")
        self.assertEqual(iso_date("1834-05-00"), "1834-05")
        self.assertEqual(iso_date("2013-08-07"), "2013-08-07")
        self.assertEqual(iso_date(""), "")

    def test_front_language(self) -> None:
        post = parse_post(make_post())
        self.assertEqual(front_language(post, ["he", "en"]), "en")
        self.assertEqual(front_language(post, ["he"]), "he")

    def test_output_is_deterministic(self) -> None:
        _, first = build()
        _, second = build()
        self.assertEqual({k: v.files for k, v in first.items()}, {k: v.files for k, v in second.items()})



def assert_valid(case: unittest.TestCase, projects) -> None:
    for project in projects.values():
        for stem, document in project.files.items():
            valid, errors = validate(prettify_xml(compact(document), remove_xml_declaration=True, keep_blank_text=True))
            case.assertTrue(valid, f"{project.project_id}/{stem}: {errors}")


class TestRules(unittest.TestCase):
    """The rules of specs/OPENSIDDUR_ORG_IMPORT.md, "Columns the converter resolves"."""

    def test_a_heading_inside_a_cell_opens_a_section_in_its_language(self) -> None:
        rows = [[cell("heb-Hebr", "liturgy", "שורה"), cell("eng-Latn", "english", "<h3>Part One</h3><p>A line.</p>")],
                [cell("heb-Hebr", "liturgy", "עוד"), cell("eng-Latn", "english", "<p>More.</p>")]]
        _, projects = build(make_post(content=table(["Source (Hebrew)", "Translation (English)"], rows)))
        english = tree(projects["en"].files[text_file_stem(URN)])
        self.assertEqual(english.find(".//tei:div/tei:div/tei:head", NS).text, "Part One")
        self.assertEqual([m.get("corresp") for m in english.iterfind(".//tei:milestone", NS)], [f"{URN}/1", f"{URN}/2"])
        self.assertIsNone(tree(projects["he"].files[text_file_stem(URN)]).find(".//tei:div/tei:div", NS))
        assert_valid(self, projects)

    def test_verse_and_prose_in_one_column(self) -> None:
        rows = [[cell("eng-Latn", "english", "A line<br />another")], [cell("eng-Latn", "english", "<p>Prose.</p>")]]
        _, projects = build(make_post(content=table(["Source (English)"], rows)))
        text = tree(projects["en"].files[text_file_stem(URN)])
        self.assertIsNotNone(text.find(".//tei:lg", NS))
        self.assertIsNotNone(text.find(".//tei:p", NS))
        assert_valid(self, projects)

    def test_commentary_and_description_are_notes(self) -> None:
        rows = [[cell("eng-Latn", "english", "Reader:"), cell("eng-Latn", "english", "I sing"),
                 cell("eng-Latn", "english", "A gloss")]]
        _, projects = build(make_post(content=table(
            ["Description (English)", "Translation (English)", "Commentary (English)"], rows)))
        self.assertEqual(list(projects), ["en"])
        text = tree(projects["en"].files[text_file_stem(URN)])
        notes = [(n.get("type"), "".join(n.itertext()).strip()) for n in text.iterfind(".//tei:body//tei:note", NS)]
        self.assertEqual(notes, [("description", "Reader:"), ("commentary", "A gloss")])
        assert_valid(self, projects)

    def test_two_columns_in_one_language_are_two_projects(self) -> None:
        rows = [[cell("eng-Latn", "english", "Literal"), cell("eng-Latn", "english", "Singable")]]
        _, projects = build(make_post(content=table(
            ["Translation (English, literal)", "Translation (English, singable)"], rows)))
        self.assertEqual(list(projects), ["en", "en/singable"])
        assert_valid(self, projects)

    def test_each_table_is_a_file(self) -> None:
        first = table(["Source (Hebrew)", "Translation (English)"], [[cell("heb-Hebr", "liturgy", "א"), cell("eng-Latn", "english", "A")]])
        second = table(["Source (Hebrew)", "Translation (English)"], [[cell("heb-Hebr", "liturgy", "ב"), cell("eng-Latn", "english", "B")]])
        _, projects = build(make_post(content=first + second))
        files = projects["he"].files
        self.assertEqual(sorted(files), ["a_song_1", "a_song_2", "index"])
        targets = [t.get("target") for t in tree(files["index"]).iterfind(".//j:transclude", NS)]
        self.assertEqual(targets, [f"{URN}/1", f"{URN}/2"])
        self.assertEqual([m.get("corresp") for m in tree(files["a_song_2"]).iterfind(".//tei:milestone", NS)],
                         [f"{URN}/2/1"])
        assert_valid(self, projects)

    def test_a_version_departs_from_its_original(self) -> None:
        song = "urn:x-opensiddur:text:poem:song"
        rows = [[cell("heb-Hebr", "liturgy", f"שורה {n}"), cell("eng-Latn", "english", f"Line {n}")] for n in range(4)]
        urns = PostUrns(101, "existing", song, {1: f"{song}/1", 2: None, 3: None, 4: None},
                        spans={2: f"{song}/2-3", 3: f"{song}/2-3", 4: ""})
        _, projects = build(make_post(content=table(["Source (Hebrew)", "Translation (English)"], rows)), urns=urns)
        for lang in ("he", "en"):
            text = tree(projects[lang].files["song"])
            self.assertEqual([m.get("corresp") for m in text.iterfind(".//tei:milestone", NS)],
                             [f"{song}/1", f"{song}/2-3", None])
        assert_valid(self, projects)

    def test_a_departing_row_holding_only_a_heading(self) -> None:
        song = "urn:x-opensiddur:text:poem:song"
        rows = [[cell("heb-Hebr", "liturgy", "א"), cell("eng-Latn", "english", "A")],
                [cell("heb-Hebr", "liturgy", "ב"), cell("eng-Latn", "english", "<h3>Heading B</h3>")],
                [cell("heb-Hebr", "liturgy", "ג"), cell("eng-Latn", "english", "C")]]
        urns = PostUrns(101, "existing", song, {1: f"{song}/1", 2: None, 3: None},
                        spans={2: f"{song}/2-3", 3: f"{song}/2-3"})
        _, projects = build(make_post(content=table(["Source (Hebrew)", "Translation (English)"], rows)), urns=urns)
        english = tree(projects["en"].files["song"])
        self.assertEqual([m.get("corresp") for m in english.iterfind(".//tei:milestone", NS)],
                         [f"{song}/1", f"{song}/2-3"])
        assert_valid(self, projects)

    def test_tables_holding_different_works_are_different_projects(self) -> None:
        first = table(["Source (Hebrew)", "Translation (English)"], [[cell("heb-Hebr", "liturgy", "א"), cell("eng-Latn", "english", "A")]])
        second = table(["Source (Hebrew)", "Translation (English, Talmud, adapted)"],
                       [[cell("heb-Hebr", "liturgy", "ב"), cell("eng-Latn", "english", "B")]])
        post, projects = build(make_post(content=first + second))
        self.assertEqual(sorted(projects), ["en", "en/talmud_adapted", "he"])
        self.assertEqual(sorted(projects["en"].files), ["a_song_1", "index"])
        self.assertEqual(sorted(projects["en/talmud_adapted"].files), ["a_song_2", "index"])
        self.assertEqual(sorted(projects["he"].files), ["a_song_1", "a_song_2", "index"])


class TestColours(unittest.TestCase):
    """Colours mean what each post's decision says (post_decisions.yaml)."""

    def english(self, body: str, colours: dict[str, str]):
        rows = [[cell("eng-Latn", "english", body)]]
        _, projects = build(make_post(content=table(["Source (English)"], rows)),
                            decisions=PostDecisions(colours={101: colours}))
        assert_valid(self, projects)
        return tree(projects["en"].files[text_file_stem(URN)])

    def test_an_amendment_is_a_variant_of_the_text(self) -> None:
        text = self.english('Our <span style="color: green">Mother</span> | Father in heaven', {"green": "amendment"})
        conditions = text.findall(".//j:conditional", NS)
        names = [(c.get("type"), c.find(".//tei:f", NS).get("name"), c.find(".//tei:binary", NS).get("value"))
                 for c in conditions]
        base = "urn:x-opensiddur:condition:prayer:a_song/amended"
        self.assertEqual(names, [("marked", base, "true"), ("marked", base, "false")])
        self.assertEqual("".join(text.find(".//tei:l", NS).itertext()), "Our Mother Father in heaven")

    def test_a_whole_coloured_cell(self) -> None:
        rows = [[cell("eng-Latn", "english", "One line")],
                [f'<td><div class="english" lang="eng-Latn" style="color:green;">Added<br />lines</div></td>']]
        _, projects = build(make_post(content=table(["Source (English)"], rows)),
                            decisions=PostDecisions(colours={101: {"green": "amendment"}}))
        assert_valid(self, projects)
        text = tree(projects["en"].files[text_file_stem(URN)])
        self.assertEqual(len(text.findall(".//tei:l/j:conditional", NS)), 2)

    def test_alternatives_by_gender_and_rite(self) -> None:
        text = self.english('to the <span style="color:blue">man</span><span style="color:red">woman</span> '
                            '<span style="color:dodgerblue">A</span><span style="color:crimson">S</span>',
                            {"blue": "alternative male", "red": "alternative female",
                             "dodgerblue": "alternative ashkenaz", "crimson": "alternative sepharad"})
        fs = [(f.getparent().get("type"), f.get("name")) for f in text.iterfind(".//j:conditional//tei:f", NS)]
        self.assertEqual(fs, [("opensiddur:person", "gender"), ("opensiddur:person", "gender"),
                              ("opensiddur:rite", "ashkenaz"), ("opensiddur:rite", "sepharad")])

    def test_marks_that_are_not_conditions(self) -> None:
        text = self.english('<span style="color:red">shuqa</span> <span style="color:blue">a verse</span> '
                            '<span style="color:gray">filled</span> <span style="color:purple">sung</span> '
                            '<span style="color:pink">loud</span>',
                            {"red": "language arc", "blue": "quotation", "gray": "supplied scholars",
                             "purple": "cantillation job", "pink": "none"})
        self.assertEqual(text.find(".//tei:seg[@{http://www.w3.org/XML/1998/namespace}lang='arc']", NS).text, "shuqa")
        self.assertEqual(text.find(".//tei:seg[@type='quotation']", NS).text, "a verse")
        self.assertEqual(text.find(".//tei:seg[@type='supplied']", NS).get("subtype"), "scholars")
        self.assertEqual(text.find(".//tei:seg[@type='cantillation']", NS).get("subtype"), "job")
        self.assertIsNone(text.find(".//j:conditional", NS))
        self.assertTrue("".join(text.find(".//tei:l", NS).itertext()).endswith("loud"))

    def test_a_ketiv_takes_the_word_before_it_as_its_reading(self) -> None:
        text = self.english('return our captivity <span style="color:gray">captivities</span> like streams', {"gray": "ketiv"})
        choice = text.find(".//tei:choice", NS)
        self.assertEqual((choice.find("j:written", NS).text, choice.find("j:read", NS).text), ("captivities", "captivity"))

    def test_a_ketiv_before_its_reading(self) -> None:
        text = self.english('<font color="brown">plaiah</font> <font color="blue">pliah</font> for me',
                            {"brown": "ketiv first", "blue": "qere"})
        choice = text.find(".//tei:choice", NS)
        self.assertEqual((choice.find("j:written", NS).text, choice.find("j:read", NS).text), ("plaiah", "pliah"))
        text = self.english('his <font color="brown">shirah</font> shiro with me', {"brown": "ketiv first"})
        choice = text.find(".//tei:choice", NS)
        self.assertEqual((choice.find("j:written", NS).text, choice.find("j:read", NS).text), ("shirah", "shiro"))
        self.assertEqual("".join(text.find(".//tei:l", NS).itertext()), "his shirahshiro with me")

    def test_a_colour_in_a_footnote(self) -> None:
        body = ('You<span class="footnote_referrer"><a><sup>[1]</sup></a><span class="footnote_tooltip">'
                'The <span style="color:red">shuqa</span>.</span></span>')
        text = self.english(body, {"red": "language arc"})
        self.assertIsNotNone(text.find(".//tei:standOff//tei:seg", NS))

    def test_a_colour_in_the_posts_own_words_is_dropped(self) -> None:
        content = '<p>Adapted text in <span style="color:green">GREEN</span>.</p>' + table(
            ["Source (English)"], [[cell("eng-Latn", "english", '<span style="color:green">new</span>')]])
        _, projects = build(make_post(content=content), decisions=PostDecisions(colours={101: {"green": "amendment"}}))
        assert_valid(self, projects)

    def test_hidden_text_is_kept_behind_a_condition(self) -> None:
        text = self.english('Write <span style="color: white">a spell</span>.', {"white": "hidden"})
        f = text.find(".//j:conditional//tei:f", NS)
        self.assertEqual(f.get("name"), "urn:x-opensiddur:condition:prayer:a_song/concealed")


class TestEssay(unittest.TestCase):
    """An essay about the passages it quotes (post_decisions.yaml, ``essays``)."""

    CONTENT = ("<p>Why we rise at midnight.</p>"
               '<blockquote><div lang="heb-Hebr">קוּמִי רֹנִּי בַלַּיְלָה</div><div lang="eng-Latn">Arise, cry out in the night</div></blockquote>'
               "<p>And the psalm says:</p>"
               '<blockquote><div lang="heb-Hebr">חֲצוֹת לַיְלָה אָקוּם</div></blockquote>'
               "<p>So the vigil began.</p><hr /><p>Transcribed by a friend.</p>")

    def setUp(self) -> None:
        decisions = PostDecisions(essays={101: "an essay"})
        self.post, self.projects = build(make_post(content=self.CONTENT), decisions=decisions)

    def test_the_passages_are_rows_of_a_table(self) -> None:
        self.assertEqual(self.post.essay[1], 1)
        self.assertEqual(self.post.essay[3], 2)
        self.assertEqual([c.lang for c in self.post.columns], ["he", "en"])
        self.assertEqual(len(self.post.rows), 2)
        self.assertEqual([node_text(line) for line in self.post.notes], ["Transcribed by a friend."])

    def test_the_essay_transcludes_each_passage(self) -> None:
        english = self.projects["en"].files
        self.assertEqual(sorted(english), ["a_song", "a_song_quoted", "index"])
        essay = tree(english["a_song"])
        self.assertEqual([t.get("target") for t in essay.iterfind(".//j:transclude", NS)],
                         [f"{URN}/quoted/1", f"{URN}/quoted/2"])
        self.assertEqual([t.get("target") for t in tree(english["index"]).iterfind(".//j:transclude", NS)], [URN])
        hebrew = self.projects["he"].files
        self.assertEqual(sorted(hebrew), ["a_song_quoted", "index"])
        self.assertEqual([t.get("target") for t in tree(hebrew["index"]).iterfind(".//j:transclude", NS)],
                         [f"{URN}/quoted"])
        assert_valid(self, self.projects)


class TestReviewRegressions(unittest.TestCase):
    def test_title_scripts(self) -> None:
        from opensiddur.importer.opensiddur_org.tei_builder import titles_by_language

        post = parse_post(make_post(title="يَا حَنُكَّة | Ya Hanukkah"))
        self.assertEqual([lang for lang, _ in titles_by_language(post)], ["und-Arab", "en"])

    def test_front_matter_in_a_latin_language_other_than_english(self) -> None:
        post = parse_post(make_post())
        self.assertEqual(front_language(post, ["he", "de"]), "de")

    def test_footnote_inside_an_instruction_is_anchored_after_it(self) -> None:
        body = ('<span class="instruction">Stand<span class="footnote_referrer"><a><sup>[1]</sup></a>'
                '<span class="footnote_tooltip">Why.</span></span></span> and pray')
        post, projects = build(make_post(content=table(["Translation (English)"], [[cell("eng-Latn", "english", body)]])))
        text = tree(projects["en"].files[text_file_stem(URN)])
        line = text.find(".//tei:l", NS)
        self.assertEqual([etree.QName(c).localname for c in line], ["note", "anchor"])
        self.assertIsNotNone(text.find("tei:standOff/tei:note[@target='#note_1']", NS))

    def test_heading_keeps_every_line(self) -> None:
        rows = [[cell("eng-Latn", "english", "<h3>Part One<br />The Beginning</h3>")], [cell("eng-Latn", "english", "Text")]]
        post, projects = build(make_post(content=table(["Source (English)"], rows)))
        head = tree(projects["en"].files[text_file_stem(URN)]).find(".//tei:div/tei:div/tei:head", NS)
        self.assertEqual("".join(head.itertext()), "Part One The Beginning")


if __name__ == "__main__":
    unittest.main()
