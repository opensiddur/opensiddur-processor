import tempfile
import unicodedata
import unittest
from pathlib import Path

from opensiddur.importer.opensiddur_org.naming import (
    TITLE_LENGTH,
    Candidate,
    assign_project_ids,
    author_field,
    base_project_id,
    date_field,
    fold,
    imported_projects,
    join_prefixes,
    name_field,
    respelled,
    text_name,
    title_field,
)
from opensiddur.importer.opensiddur_org.parse_post import Column, parse_post
from opensiddur.tests.importer.opensiddur_org.support import make_post

SOURCE = Column(header="Source (Hebrew)", role="source", lang="he")
TRANSLATION = Column(header="Translation (English)", role="translation", lang="en")


def person(name: str, qualifier: str = "") -> dict[str, str]:
    slug = name.lower().replace(" ", "-")
    shown = f"{name} ({qualifier})" if qualifier else name
    return {"name": shown, "profile_link": f"https://opensiddur.org/profile/{slug}"}


def post(title: str = "שִׁירָה | A Song", coauthors=None, **kw):
    return parse_post(make_post(title=title, coauthors=coauthors or [], **kw))


class FoldTestCase(unittest.TestCase):
    def test_the_style_guides_letters_become_the_tables(self):
        self.assertEqual(fold("Ḥanukkah Ẓion Ḳadosh ƙ šabbat"), ["chanukkah", "tzion", "qadosh", "kh", "shabbat"])

    def test_other_diacritics_are_stripped_and_alephs_dropped(self):
        self.assertEqual(fold("Ṭevet Moïse Anzünden l’Garesh Y'qar"),
                         ["tevet", "moise", "anzunden", "lgaresh", "yqar"])

    def test_a_schwa_is_e_and_an_ayin_is_dropped(self):
        self.assertEqual(fold("Qədushah Shəvat Maʕalot"), ["qedushah", "shevat", "maalot"])

    def test_decomposed_text_folds_the_same(self):
        self.assertEqual(fold(unicodedata.normalize("NFKD", "Ḥanukkah Ẓion")), ["chanukkah", "tzion"])

    def test_capitals_and_ligatures(self):
        self.assertEqual(fold("Ḇet Œuvre Ðan"), ["vet", "oeuvre", "dan"])

    def test_punctuation_separates_words(self):
        self.assertEqual(fold("Al HaNisim: For the Banners — Neohasid·org"),
                         ["al", "hanisim", "for", "the", "banners", "neohasid", "org"])


class TitleTestCase(unittest.TestCase):
    def test_the_latin_part_up_to_the_attribution(self):
        for title, expected in (
            ("מָעוֹז צוּר | Maoz Tsur (Rock of Ages), singing translation by Rabbi Zalman", "maoz_tsur"),
            ("תהלים ל׳ | Psalms 30 by David (interpretive translation)", "psalms_30"),
            ("Al HaNisim: For the Banners, by Kohenet Ilana Joy Streit", "al_hanisim_for_the_banners"),
            ("צער | Tsaar Baalei Ḥayyim [It is forbidden to cause] suffering, a song", "tsaar_baalei_chayyim_suffering"),
            ("Great Arbiter of human fate! – a hymn for Ḥanukkah by Penina Moïse", "great_arbiter_of_human_fate"),
        ):
            with self.subTest(title=title):
                self.assertEqual(title_field(post(title)), expected)

    def test_a_long_title_is_cut_at_a_word(self):
        field = title_field(post("Prayer for the new moon of Ṭevet on Ḥanukkah occurring on the winter solstice"))
        self.assertLessEqual(len(field), TITLE_LENGTH)
        self.assertEqual(field, "prayer_for_the_new_moon_of_tevet_on_chanukkah_occurring")

    def test_a_cut_does_not_end_on_a_dangling_word(self):
        # Cut at 60, it would end "..._day_on_the".
        field = title_field(post("Prayer for the United States on Thanksgiving Day on the Twenty-eighth of November"))
        self.assertEqual(field, "prayer_for_the_united_states_on_thanksgiving_day")

    def test_a_colon_before_an_honorific_ends_the_name(self):
        self.assertEqual(title_field(post("Prayer of the Guest Chaplain: Rabbi Peter S. Berg")),
                         "prayer_of_the_guest_chaplain")
        self.assertEqual(title_field(post("Al HaNisim: For the Banners")), "al_hanisim_for_the_banners")

    def test_a_hebrew_only_title_is_named_from_the_slug(self):
        self.assertEqual(title_field(post("בָּאנוּ חֹשֶׁךְ לְגָרֵשׁ", slug="banu-hoshekh-by-sara")), "banu_hoshekh")


class TextNameTestCase(unittest.TestCase):
    """A text's name follows the table; a project's title keeps the post's romanization."""

    #: A spelling list of the tests' own, so these do not change with the real one.
    VARIANTS = {"tsur": "tzur", "shnei": "shenei"}

    def test_an_elided_shva_is_written(self):
        for title, expected in (("Banu Ḥoshekh l’Garesh", "Banu Ḥoshekh leGaresh"),
                                ("Avnei Y’qar", "Avnei Yeqar"),
                                ("Ashira l-Tsur Nora", "Ashira leTsur Nora"),
                                ("Yevanim Tsur b-Af", "Yevanim Tsur beAf")):
            with self.subTest(title=title):
                self.assertEqual(join_prefixes(title), expected)

    def test_a_hyphened_prefix_joins_its_word(self):
        self.assertEqual(join_prefixes("Hakhrazah li-Ymei ha-Hodayah"), "Hakhrazah liYmei haHodayah")
        self.assertEqual(join_prefixes("u-N’taneh Toqef"), "uNetaneh Toqef")

    def test_a_dotted_consonant_takes_its_shva(self):
        self.assertEqual(join_prefixes("Imrot ha-El Ṭ’horot"), "Imrot haEl Ṭehorot")

    def test_english_apostrophes_and_hyphens_are_left_alone(self):
        for title in ("Children's Prayer", "R' Joseph", "X-ray", "D-Day", "Schmiedl-Neuda", "Ma'oz Tsur"):
            with self.subTest(title=title):
                self.assertEqual(join_prefixes(title), title)

    def test_a_word_after_a_joined_prefix_is_respelled(self):
        self.assertEqual(respelled("letsur", self.VARIANTS), "letzur")
        self.assertEqual(respelled("tsur", self.VARIANTS), "tzur")
        self.assertEqual(respelled("leotef", self.VARIANTS), "leotef")

    def test_a_variant_that_only_doubles_is_not_found_after_a_prefix(self):
        # `sheelu` is שְׁאֵלוּ, not she + אֵלּוּ.
        self.assertEqual(respelled("sheelu", {"elu": "ellu"}), "sheelu")
        self.assertEqual(respelled("elu", {"elu": "ellu"}), "ellu")

    def test_a_french_title_is_not_joined(self):
        data = make_post(title="Prière avant l’instruction")
        data["custom_fields"]["languages_meta"] = ['[{"name":"French","code":"fra"}]']
        p = parse_post(data)
        self.assertEqual(text_name(p, self.VARIANTS).split("_")[:3], ["priere", "avant", "linstruction"])

    def test_the_text_name_joins_and_respells_but_the_project_title_does_not(self):
        p = post("אָשִׁירָה | Ashira l-Tsur Nora, a piyyuṭ")
        self.assertEqual(text_name(p, self.VARIANTS).split("_")[:3], ["ashira", "letzur", "nora"])
        self.assertEqual(title_field(p), "ashira_l_tsur_nora")


class NameTestCase(unittest.TestCase):
    def test_a_surname(self):
        for name, expected in (("Zalman Schachter-Shalomi", "schachter_shalomi"),
                               ("Rabbi Jill Hammer, Ph.D.", "hammer"),
                               ("R' Joseph H. Hertz", "hertz"),
                               ("Frederick de Sola Mendes", "mendes"),
                               ("Shlomo ibn Gabirol", "gabirol"),
                               ("Neohasid·org", "neohasid_org"),
                               # An initial is not a patronymic, nor is a hyphenated name.
                               ("Lieba B. Ruth", "ruth"),
                               ("Bat-Sheva Cohen", "cohen"),
                               ("Dan Bar-Lev", "bar_lev"),
                               # An epithet in the middle is not the end of the name.
                               ("Meïr haLevi Letteris", "letteris"),
                               ("Conan O'Brien", "obrien"),
                               # An organization's own abbreviation names it.
                               ("Central Conference of American Rabbis [CCAR]", "ccar"),
                               ("Union of American Hebrew Congregations (UAHC)", "uahc"),
                               # A bracketed year or initial is not one.
                               ("Sara Levi-Tanai (1960)", "levi_tanai"),
                               ("Moshe (M.) Cohen", "cohen")):
            with self.subTest(name=name):
                self.assertEqual(name_field(name), expected)

    def test_a_patronymic_names_the_person_by_the_first_name(self):
        for name, expected in (("Mordekhai ben Yitsḥaq ha-Levi", "mordekhai"),
                               ("Ḳalonymus b. Ḳalonymus ben Meir", "qalonymus"),
                               ("Yosef ben Shlomo of Carcassonne", "yosef"),
                               ("Avraham haLevi", "avraham")):
            with self.subTest(name=name):
                self.assertEqual(name_field(name), expected)


class AuthorTestCase(unittest.TestCase):
    def test_source_and_translation(self):
        p = post(coauthors=[person("Rivka Translator", "translation"), person("Yehudah Poet")])
        self.assertEqual(author_field(p, SOURCE), "poet")
        self.assertEqual(author_field(p, TRANSLATION), "translator")

    def test_an_unknown_translator_gives_no_author(self):
        p = post(coauthors=[person("Unknown", "translation"), person("Yehudah Poet")])
        self.assertEqual(author_field(p, TRANSLATION), "")

    def test_the_title_settles_who_is_the_author(self):
        # A congregation is credited with no role, like an author.
        p = post("Great Arbiter of human fate! – a hymn by Penina Moïse (K.K. Beth Elohim 1842)",
                 coauthors=[person("Kahal Kadosh Beth Elohim", "Charleston, South Carolina"),
                            person("Penina Moïse")])
        self.assertEqual(author_field(p, SOURCE), "moise")

    def test_the_title_settles_who_is_the_translator(self):
        # Credited with no role, but the title says "trans. by".
        p = post("מָעוֹז צוּר | Maoz Tsur (trans. by Frederick de Sola Mendes 1914)",
                 coauthors=[person("Frederick de Sola Mendes"), person("Mordekhai ben Yitsḥaq ha-Levi")])
        self.assertEqual(author_field(p, TRANSLATION), "mendes")
        self.assertEqual(author_field(p, SOURCE), "mordekhai")

    def test_a_clause_naming_a_translation_credits_its_translator(self):
        p = post("Schirm und Schutz, a German translation of Maoz Tsur by Leopold Stein",
                 coauthors=[person("Leopold Stein"), person("Mordekhai ben Yitsḥaq ha-Levi")])
        self.assertEqual(author_field(p, SOURCE), "mordekhai")
        self.assertEqual(author_field(p, TRANSLATION), "stein")

    def test_trans_without_by(self):
        p = post("Kavvanah, by Rebbe Tsvi Spira (trans. Moreh Yehudis Fishman)",
                 coauthors=[person("Yehudis Fishman"), person("Tsvi Spira")])
        self.assertEqual(author_field(p, SOURCE), "spira")
        self.assertEqual(author_field(p, TRANSLATION), "fishman")

    def test_a_shared_surname_is_not_a_match(self):
        p = post("A Hymn, by Moritz Mayer, trans. by Isaac Gantwerk Mayer",
                 coauthors=[person("Isaac Gantwerk Mayer", "translation"), person("Moritz Mayer")])
        self.assertEqual(author_field(p, SOURCE), "mayer")

    def test_transliterated_by_is_not_a_translation(self):
        p = post("A Song, transliterated by Ann Other", coauthors=[person("Ann Other")])
        self.assertEqual(author_field(p, SOURCE), "other")

    def test_a_name_in_hebrew_is_given_by_the_profile_slug(self):
        p = post(coauthors=[{"name": "צבי שפירא", "profile_link": "https://opensiddur.org/profile/tsvi-spira"}])
        self.assertEqual(author_field(p, SOURCE), "spira")

    def test_of_several_translators_the_one_the_title_names(self):
        p = post("Prayer for Kislev, by Rabbi Levi Weiman-Kelman",
                 coauthors=[person("Shaul Vardi", "translation"), person("Levi Weiman-Kelman", "translation")])
        self.assertEqual(author_field(p, TRANSLATION), "weiman_kelman")


class DateTestCase(unittest.TestCase):
    def test_the_original_year_else_the_posts(self):
        self.assertEqual(date_field(post(date_src=("1240-00-00", "1300-00-00")), SOURCE), "1240")
        self.assertEqual(date_field(post(date_src=("-0515-00-00", "-0500-00-00")), SOURCE), "515bce")
        self.assertEqual(date_field(post(date_src=("0000-00-00", "")), SOURCE), "2020")

    def test_a_translation_has_no_date(self):
        self.assertEqual(date_field(post(date_src=("1240-00-00", "")), TRANSLATION), "")

    def test_fields_left_empty_are_left_out(self):
        p = post(coauthors=[person("Unknown", "translation")], date_src=("1240-00-00", ""))
        self.assertEqual(base_project_id(p, TRANSLATION), "a_song")


class AssignTestCase(unittest.TestCase):
    def candidates(self, *post_ids: int):
        poet = [person("Yehudah Poet")]
        return [Candidate(parse_post(make_post(i, coauthors=poet)), SOURCE) for i in post_ids]

    def test_the_older_post_keeps_the_plain_name(self):
        # Given in either order, the lower post ID keeps it, so a new post never renames an old one.
        ids = assign_project_ids(reversed(self.candidates(7, 3)))
        self.assertEqual(ids, {(3, "he"): "a_song-poet-2020-he", (7, "he"): "a_song-poet-2020-7-he"})

    def test_a_post_keeps_the_name_it_has(self):
        # The newer post has the name on disk: the older one does not take it from it.
        ids = assign_project_ids(self.candidates(3, 7), held={"a_song-poet-2020-he": 7})
        self.assertEqual(ids, {(3, "he"): "a_song-poet-2020-3-he", (7, "he"): "a_song-poet-2020-he"})

    def test_a_name_held_by_a_post_that_no_longer_wants_it_is_free(self):
        ids = assign_project_ids(self.candidates(7), held={"a_song-poet-2020-he": 3})
        self.assertEqual(ids, {(7, "he"): "a_song-poet-2020-he"})

    def test_a_name_already_taken(self):
        ids = assign_project_ids(self.candidates(3), taken=["a_song-poet-2020-he"])
        self.assertEqual(ids, {(3, "he"): "a_song-poet-2020-3-he"})

    def test_the_language_is_lowercased(self):
        p = parse_post(make_post(coauthors=[person("Yehudah Poet")]))
        ids = assign_project_ids([Candidate(p, Column(header="", role="transliteration", lang="he-Latn"))])
        self.assertEqual(ids, {(101, "he-Latn"): "a_song-poet-2020-he-latn"})


class ImportedProjectsTestCase(unittest.TestCase):
    def test_found_by_the_post_id_in_the_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tei = '<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader>{}</teiHeader></TEI>'
            own = '<bibl xml:id="project_source_bibl"><idno type="opensiddur.org">{}</idno></bibl>'
            for name, header in (("a_song-poet-2020-he", own.format(101)),
                                 ("a_song-translator-en", own.format(101)),
                                 ("tanakh-wlc-he", '<idno type="url">x</idno>'),
                                 # A project citing a post among its sources is not that post's.
                                 ("cites-a-post-he", '<bibl><idno type="opensiddur.org">101</idno></bibl>')):
                (root / name).mkdir()
                (root / name / "index.xml").write_text(tei.format(header), encoding="utf-8")
            (root / "broken").mkdir()
            (root / "broken" / "index.xml").write_text("<not xml", encoding="utf-8")
            found = imported_projects(root)
        self.assertEqual({k: sorted(p.name for p in v) for k, v in found.items()},
                         {101: ["a_song-poet-2020-he", "a_song-translator-en"]})


if __name__ == "__main__":
    unittest.main()
