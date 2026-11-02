import tempfile
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.importer.opensiddur_org.match import (
    IncipitIndex,
    Proposal,
    _words,
    bible_hint,
    build_incipit_index,
    decide,
    departure_spans,
    index_document,
    propose,
)
from opensiddur.importer.opensiddur_org.parse_post import parse_post
from opensiddur.importer.opensiddur_org.urns import PostUrns
from opensiddur.tests.importer.opensiddur_org.support import cell, make_post, table

P = "urn:x-opensiddur:text:"
TEI_NS = 'xmlns:tei="http://www.tei-c.org/ns/1.0"'

#: A synthetic poem of three stanzas and three blessings, as an existing project encodes them.
EXISTING = f"""<tei:TEI {TEI_NS} xml:lang="he"><tei:teiHeader><tei:fileDesc><tei:titleStmt>
<tei:title>ignored header words that must not be indexed</tei:title></tei:titleStmt></tei:fileDesc></tei:teiHeader>
<tei:text><tei:body><tei:div corresp="{P}poem:song">
<tei:milestone unit="stanza" corresp="{P}poem:song/1"/><tei:l>אֶרֶץ יָפָה וְהָרִים גְּבוֹהִים מְאֹד מְאֹד</tei:l>
<tei:milestone unit="stanza" corresp="{P}poem:song/2"/><tei:l>כְּרֹת עֵצִים בַּיַּעַר הַגָּדוֹל וְהָרָחָב תָּמִיד</tei:l>
<tei:milestone unit="stanza" corresp="{P}poem:song/3"/><tei:l>שִׁירוּ לְאֵל עֶלְיוֹן בְּקוֹל רָם וְנָעִים מְאֹד</tei:l>
</tei:div>
<tei:div corresp="{P}prayer:candles"><tei:p>בָּרוּךְ אַתָּה יְיָ אֱלֹהֵינוּ מֶלֶךְ הָעוֹלָם אֲשֶׁר קִדְּשָׁנוּ בְּמִצְוֹתָיו וְצִוָּנוּ לְהַדְלִיק נֵר שֶׁל חֲנֻכָּה</tei:p></tei:div>
<tei:div corresp="{P}prayer:candles_shabbat"><tei:p>בָּרוּךְ אַתָּה יְיָ אֱלֹהֵינוּ מֶלֶךְ הָעוֹלָם אֲשֶׁר קִדְּשָׁנוּ בְּמִצְוֹתָיו וְצִוָּנוּ לְהַדְלִיק נֵר שֶׁל שַׁבָּת</tei:p></tei:div>
<tei:div corresp="{P}prayer:shehecheyanu"><tei:p>בָּרוּךְ אַתָּה יְיָ אֱלֹהֵינוּ מֶלֶךְ הָעוֹלָם שֶׁהֶחֱיָנוּ וְקִיְּמָנוּ וְהִגִּיעָנוּ לַזְּמַן הַזֶּה</tei:p></tei:div>
<tei:div corresp="{P}siddur:festival/position"><tei:p>מִקּוֹם בַּסִּדּוּר שֶׁאֵינוֹ טֶקְסְט כְּלָל וּכְלָל</tei:p></tei:div>
</tei:body></tei:text></tei:TEI>"""


def index() -> IncipitIndex:
    built = IncipitIndex()
    index_document(built, etree.fromstring(EXISTING.encode("utf-8")))
    return built


def hebrew_post(*lines: str, title: str = "שיר | A Song", slug: str = "a-song"):
    rows = [[cell("heb-Hebr", "liturgy", line), cell("eng-Latn", "english", f"English {i}")]
            for i, line in enumerate(lines)]
    return parse_post(make_post(content=table(["Source (Hebrew)", "Translation (English)"], rows),
                                title=title, slug=slug))


class TestIndex(unittest.TestCase):
    def test_opening_of_each_scope(self) -> None:
        built = index()
        self.assertEqual(built.lookup(_words("אֶרֶץ יָפָה וְהָרִים גְּבוֹהִים מְאֹד מְאֹד")), {f"{P}poem:song/1"})

    def test_header_and_positions_are_not_texts(self) -> None:
        built = index()
        self.assertFalse(any(urn.startswith(f"{P}siddur:") for urn in built.incipit_of))
        self.assertFalse(built.lookup(_words("ignored header words that must")))

    def test_full_and_defective_spellings_agree(self) -> None:
        self.assertEqual(index().lookup(_words("כְּרוֹת עֵצִים בַּיַּעַר הַגָּדוֹל וְהָרָחָב תָּמִיד")), {f"{P}poem:song/2"})

    def test_blessings_are_told_apart_after_the_formula(self) -> None:
        built = index()
        # The divine name is spelled out here and abbreviated in the index.
        self.assertEqual(
            built.lookup(_words("בָּרוּךְ אַתָּה יהוה אֱלֹהֵינוּ מֶלֶךְ הָעוֹלָם אֲשֶׁר קִדְּשָׁנוּ בְּמִצְוֹתָיו וְצִוָּנוּ לְהַדְלִיק נֵר שֶׁל חֲנֻכָּה")),
            {f"{P}prayer:candles"},
        )
        self.assertEqual(
            built.lookup(_words("בָּרוּךְ אַתָּה ה׳ אֱלֹהֵינוּ מֶלֶךְ הָעוֹלָם שֶׁהֶחֱיָנוּ וְקִיְּמָנוּ וְהִגִּיעָנוּ לַזְּמַן הַזֶּה")),
            {f"{P}prayer:shehecheyanu"},
        )

    def test_the_formula_alone_matches_nothing(self) -> None:
        self.assertEqual(len(index().lookup(_words("בָּרוּךְ אַתָּה יְיָ אֱלֹהֵינוּ מֶלֶךְ הָעוֹלָם"))), 3)

    def test_json_round_trip(self) -> None:
        built = index()
        self.assertEqual(IncipitIndex.from_json(built.to_json()).incipit_of, built.incipit_of)

    def test_build_from_hebrew_projects_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, lang in (("songs_he", "he"), ("songs_en", "en")):
                (root / name).mkdir()
                (root / name / "index.xml").write_text(EXISTING.replace('xml:lang="he"', f'xml:lang="{lang}"'), encoding="utf-8")
            # A project converted from a post, whatever it is called, is not matched against.
            (root / "a_song-poet-2020-he").mkdir()
            (root / "a_song-poet-2020-he" / "index.xml").write_text(
                EXISTING.replace("<tei:fileDesc>", '<tei:fileDesc><tei:bibl xml:id="project_source_bibl">'
                                                  '<tei:idno type="opensiddur.org">1</tei:idno></tei:bibl>')
                .replace(f"{P}poem:song", f"{P}poem:imported"), encoding="utf-8")
            built = build_incipit_index(root)
        self.assertIn(f"{P}poem:song/1", built.incipit_of)
        self.assertNotIn(f"{P}poem:imported/1", built.incipit_of)


class TestProposals(unittest.TestCase):
    def test_a_version_of_an_existing_poem(self) -> None:
        post = hebrew_post("אֶרֶץ יָפָה וְהָרִים גְּבוֹהִים מְאֹד מְאֹד", "כְּרֹת עֵצִים בַּיַּעַר הַגָּדוֹל וְהָרָחָב תָּמִיד",
                           "שִׁירוּ לְאֵל עֶלְיוֹן בְּקוֹל רָם וְנָעִים מְאֹד")
        proposal = propose(post, index(), {})
        self.assertEqual(proposal.urn, f"{P}poem:song")
        self.assertEqual(proposal.rows, {1: f"{P}poem:song/1", 2: f"{P}poem:song/2", 3: f"{P}poem:song/3"})

    def test_a_row_running_into_the_next_unit_is_unmapped(self) -> None:
        post = hebrew_post("אֶרֶץ יָפָה וְהָרִים גְּבוֹהִים מְאֹד מְאֹד<br />כְּרֹת עֵצִים בַּיַּעַר הַגָּדוֹל וְהָרָחָב תָּמִיד",
                           "שִׁירוּ לְאֵל עֶלְיוֹן בְּקוֹל רָם וְנָעִים מְאֹד")
        proposal = propose(post, index(), {})
        self.assertEqual(proposal.rows, {1: None, 2: f"{P}poem:song/3"})

    def test_existing_texts_without_a_common_parent(self) -> None:
        post = hebrew_post("בָּרוּךְ אַתָּה יְיָ אֱלֹהֵינוּ מֶלֶךְ הָעוֹלָם אֲשֶׁר קִדְּשָׁנוּ בְּמִצְוֹתָיו וְצִוָּנוּ לְהַדְלִיק נֵר שֶׁל חֲנֻכָּה",
                           "בָּרוּךְ אַתָּה יְיָ אֱלֹהֵינוּ מֶלֶךְ הָעוֹלָם שֶׁהֶחֱיָנוּ וְקִיְּמָנוּ וְהִגִּיעָנוּ לַזְּמַן הַזֶּה",
                           "הַנֵּרוֹת הַלָּלוּ שֶׁאָנוּ מַדְלִיקִין עַל הַנִּסִּים")
        proposal = propose(post, index(), {})
        self.assertIsNone(proposal.urn)
        self.assertEqual(proposal.rows, {1: f"{P}prayer:candles", 2: f"{P}prayer:shehecheyanu", 3: None})
        new = proposal.as_post_urns(PostUrns(post.post_id, "new", f"{P}prayer:a_song"))
        self.assertEqual((new.kind, new.row_urn(2), new.row_urn(3)), ("new", f"{P}prayer:shehecheyanu", f"{P}prayer:a_song/3"))

    def test_a_repeated_unit_keeps_only_its_first_row(self) -> None:
        line = "אֶרֶץ יָפָה וְהָרִים גְּבוֹהִים מְאֹד מְאֹד"
        proposal = propose(hebrew_post(line, "כְּרֹת עֵצִים בַּיַּעַר הַגָּדוֹל וְהָרָחָב תָּמִיד", line), index(), {})
        self.assertEqual(proposal.rows[3], None)

    def test_nothing_matches(self) -> None:
        self.assertIsNone(propose(hebrew_post("מִלִּים חֲדָשׁוֹת לְגַמְרֵי שֶׁלֹּא נִשְׁמְעוּ מֵעוֹלָם"), index(), {}))

    def test_title_names_a_psalm(self) -> None:
        post = hebrew_post("מִלִּים חֲדָשׁוֹת לְגַמְרֵי שֶׁלֹּא נִשְׁמְעוּ מֵעוֹלָם", slug="psalms-029-a-translation")
        self.assertEqual(bible_hint(post), f"{P}bible:psalms/29")
        proposal = propose(post, index(), {})
        self.assertEqual((proposal.urn, proposal.rows), (f"{P}bible:psalms/29", {1: None}))

    def test_registry_label(self) -> None:
        post = hebrew_post("מִלִּים חֲדָשׁוֹת לְגַמְרֵי שֶׁלֹּא נִשְׁמְעוּ מֵעוֹלָם", title="שיר | Maoz Tzur")
        proposal = propose(post, index(), {"maoz tzur": {f"{P}poem:maoz_tzur"}})
        self.assertEqual(proposal.urn, f"{P}poem:maoz_tzur")

    def test_departing_rows_record_the_span_they_stand_in_for(self) -> None:
        post = hebrew_post("אֶרֶץ יָפָה וְהָרִים גְּבוֹהִים מְאֹד מְאֹד", "מִלִּים חֲדָשׁוֹת לְגַמְרֵי שֶׁלֹּא נִשְׁמְעוּ מֵעוֹלָם",
                           "שִׁירוּ לְאֵל עֶלְיוֹן בְּקוֹל רָם וְנָעִים מְאֹד", "וְעוֹד בַּיִת חָדָשׁ שֶׁהַמְּשׁוֹרֵר הוֹסִיף כָּאן")
        proposal = propose(post, index(), {})
        self.assertEqual(proposal.rows, {1: f"{P}poem:song/1", 2: None, 3: f"{P}poem:song/3", 4: None})
        self.assertEqual(proposal.spans, {2: f"{P}poem:song/2", 4: ""})
        record = proposal.as_post_urns(PostUrns(post.post_id, "new", ""))
        self.assertEqual((record.kind, record.spans), ("existing", proposal.spans))
        self.assertEqual(Proposal.from_json(proposal.to_json()), proposal)

    def test_a_run_of_departing_rows_spans_a_range(self) -> None:
        spans = departure_spans({1: f"{P}poem:song/1", 2: None, 3: None}, f"{P}poem:song", index())
        self.assertEqual(spans, {2: f"{P}poem:song/2-3", 3: f"{P}poem:song/2-3"})

    def test_a_span_never_repeats_a_mapped_part(self) -> None:
        # Rows mapped out of order: song/3 is mapped already, so nothing the runs stand in for
        # can be named without naming it again.
        spans = departure_spans({1: f"{P}poem:song/3", 2: None, 3: f"{P}poem:song/1", 4: None},
                                f"{P}poem:song", index())
        self.assertEqual(spans, {2: "", 4: ""})

    def test_the_title_names_the_text(self) -> None:
        post = hebrew_post("אֶרֶץ יָפָה וְהָרִים גְּבוֹהִים מְאֹד מְאֹד", title="שיר | Maoz Tzur")
        proposal = propose(post, index(), {"maoz tzur": {f"{P}poem:maoz_tzur"}})
        # The rows open another text: resemblances, not parts of the one the title names.
        self.assertEqual((proposal.urn, proposal.rows), (f"{P}poem:maoz_tzur", {1: None}))

    def test_decide_accepts_a_proposal_and_mints_otherwise(self) -> None:
        stanzas = ("אֶרֶץ יָפָה וְהָרִים גְּבוֹהִים מְאֹד מְאֹד", "כְּרֹת עֵצִים בַּיַּעַר הַגָּדוֹל וְהָרָחָב תָּמִיד")
        record, proposals = decide(hebrew_post(*stanzas), index(), {}, set(), {})
        self.assertEqual((record.kind, record.urn, len(proposals)), ("existing", f"{P}poem:song", 1))
        record, _ = decide(hebrew_post("מִלִּים חֲדָשׁוֹת לְגַמְרֵי שֶׁלֹּא נִשְׁמְעוּ מֵעוֹלָם"), index(), {}, set(), {})
        self.assertEqual(record.kind, "new")

    def test_each_table_is_matched_on_its_own(self) -> None:
        first = table(["Source (Hebrew)"], [[cell("heb-Hebr", "liturgy", "אֶרֶץ יָפָה וְהָרִים גְּבוֹהִים מְאֹד מְאֹד")],
                                            [cell("heb-Hebr", "liturgy", "כְּרֹת עֵצִים בַּיַּעַר הַגָּדוֹל וְהָרָחָב תָּמִיד")]])
        second = table(["Source (Hebrew)"], [[cell("heb-Hebr", "liturgy", "מִלִּים חֲדָשׁוֹת לְגַמְרֵי שֶׁלֹּא נִשְׁמְעוּ מֵעוֹלָם")]])
        post = parse_post(make_post(content=first + second))
        record, _ = decide(post, index(), {}, set(), {})
        self.assertEqual(record.kind, "new")
        self.assertEqual(record.table(1, 2).urn, f"{P}poem:song")
        self.assertEqual(record.table(2, 2).urn, f"{record.urn}/2")

    def test_the_title_names_no_single_table(self) -> None:
        # 4957: "Psalms 67 and Ana b'Khoach" -- the title's psalm is not every table's.
        first = table(["Source (Hebrew)"], [[cell("heb-Hebr", "liturgy", "מִלִּים חֲדָשׁוֹת לְגַמְרֵי שֶׁלֹּא נִשְׁמְעוּ מֵעוֹלָם")]])
        second = table(["Source (Hebrew)"], [[cell("heb-Hebr", "liturgy", "וְעוֹד בַּיִת חָדָשׁ שֶׁהַמְּשׁוֹרֵר הוֹסִיף כָּאן")]])
        post = parse_post(make_post(content=first + second, slug="psalms-067-and-ana-bkhoah"))
        record, _ = decide(post, index(), {}, set(), {})
        self.assertEqual(record.tables, {})
        self.assertEqual([record.table(n, 2).urn for n in (1, 2)], [f"{record.urn}/1", f"{record.urn}/2"])

    def test_two_tables_never_share_a_text(self) -> None:
        stanzas = [[cell("heb-Hebr", "liturgy", "אֶרֶץ יָפָה וְהָרִים גְּבוֹהִים מְאֹד מְאֹד")],
                   [cell("heb-Hebr", "liturgy", "כְּרֹת עֵצִים בַּיַּעַר הַגָּדוֹל וְהָרָחָב תָּמִיד")]]
        post = parse_post(make_post(content=table(["Source (Hebrew)"], stanzas) * 2))
        record, _ = decide(post, index(), {}, set(), {})
        self.assertEqual((record.table(1, 2).urn, record.table(2, 2).urn), (f"{P}poem:song", f"{record.urn}/2"))

    def test_proposal_json(self) -> None:
        proposal = Proposal(1, None, {1: None}, ["why"])
        self.assertIn('"urn": null', proposal.to_json())


if __name__ == "__main__":
    unittest.main()
