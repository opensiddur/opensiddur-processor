import unittest
from pathlib import Path
from unittest.mock import patch
import tempfile


from opensiddur.importer.miqra_al_pi_hamasorah.convert import (
    _book_name_he,
    front_matter,
    load_source,
    main,
    read_attributions,
    read_credits,
)
from opensiddur.importer.miqra_al_pi_hamasorah.miqra_plus import PlusFormatError
from opensiddur.tests.importer.miqra_al_pi_hamasorah.support import (
    COMMIT,
    book39,
    verse,
    with_other_books,
    write_source,
)


def _convert(sourcetexts_root: Path, project_dir: Path, *args: str) -> int:
    return main(["--sourcetexts-root", str(sourcetexts_root), "--project-dir", str(project_dir), *args])


class TestMiqraConvert(unittest.TestCase):
    def _run(self, files: dict[str, list[dict]], book: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sourcetexts_root = tmp_path / "sources"
            write_source(sourcetexts_root, with_other_books(files))
            project_dir = tmp_path / "project"
            rc = main(
                [
                    "--sourcetexts-root",
                    str(sourcetexts_root),
                    "--project-dir",
                    str(project_dir),
                    "--only-book",
                    book,
                ]
            )
            self.assertEqual(rc, 0)
            return (project_dir / f"{book}.xml").read_text(encoding="utf-8")

    @patch("opensiddur.importer.miqra_al_pi_hamasorah.convert.validate")
    def test_only_book_writes_output(self, mock_validate):
        mock_validate.return_value = (True, [])
        large_bet = {
            "tmpl_name": "מ:אות-מיוחדת-במילה",
            "tmpl_params": {
                "1": [{"tmpl_name": "מ:אות-ג", "tmpl_params": {"1": "בְּ"}}, "רֵאשִׁ֖ית"],
                "2": "בְּרֵאשִׁ֖ית",
                "3": "ב.....",
                "4": "ג",
                "5": "ב/ג",
            },
        }
        genesis = book39("ספר בראשית", {
            "1": {
                # Parashah in column C, a documented word with a large letter, then a second verse.
                "1": verse(
                    [{"tmpl_name": "נוסח", "tmpl_params": {"1": large_bet, "2": "test note"}}],
                    nav=[{"tmpl_name": "פפ"}],
                ),
                "2": verse(["וְהָאָ֗רֶץ הָיְתָ֥ה תֹ֙הוּ֙ וָבֹ֔הוּ"]),
            }
        })
        xml = self._run({"A1-Genesis.json": [genesis]}, "genesis")
        self.assertIn("<tei:TEI", xml)
        self.assertIn('unit="verse"', xml)
        self.assertIn('n="1"', xml)
        self.assertIn("urn:x-opensiddur:text:bible:genesis/1/1", xml)
        self.assertNotIn("<tei:ab>", xml)
        self.assertIn('<tei:p type="open-1">', xml)
        self.assertIn("וְהָאָ֗רֶץ", xml)
        self.assertIn('<tei:head xml:lang="en">', xml)
        self.assertIn("Genesis", xml)
        self.assertIn('rend="large"', xml)
        self.assertIn("בְּ", xml)
        self.assertIn("tei:standOff", xml)
        self.assertIn("test note", xml)
        # Standoff notes must link to the in-text marker for annotation resolution
        self.assertIn('target="#miqra-note-1-ref', xml)
        # A book's header names the source but not its commit, which only the index does.
        self.assertIn("MAM-parsed/plus in https://github.com/bdenckla/MAM-basics, which", xml)
        self.assertNotIn(COMMIT, xml)

    @patch("opensiddur.importer.miqra_al_pi_hamasorah.convert.validate")
    def test_good_ending_is_not_rendered(self, mock_validate):
        # As the sheet's good-ending rows were not: plus keeps it beside the chapters.
        mock_validate.return_value = (True, [])
        isaiah = book39("ספר ישעיהו", {"1": {"1": verse(["חֲז֗וֹן"])}})
        isaiah["good_ending_plus"] = {
            "last_chapnver": ["1", "1"],
            "wikitext_element": {
                "tmpl_name": "נוסח",
                "tmpl_params": {
                    "1": {"tmpl_name": "מ:סיום בטוב", "tmpl_params": {"1": "סיום טוב"}},
                    "2": "הערה",
                },
            },
        }
        xml = self._run({"C1-Isaiah.json": [isaiah]}, "isaiah")
        self.assertIn("urn:x-opensiddur:text:bible:isaiah/1/1", xml)
        self.assertNotIn("סיום טוב", xml)
        self.assertNotIn("tei:standOff", xml)

    @patch("opensiddur.importer.miqra_al_pi_hamasorah.convert.validate")
    def test_sub_book_writes_samuel_1(self, mock_validate):
        # BA-Samuel.json holds both books of Samuel, each named by its abbreviation (שמ"א).
        mock_validate.return_value = (True, [])
        samuel = [
            book39("ספר שמואל", {"1": {"1": verse(["וַיְהִי אִישׁ אֶחָד"])}}, 'שמ"א'),
            book39("ספר שמואל", {"1": {"1": verse(["וַיְהִ֗י אַחֲרֵי֙"])}}, 'שמ"ב'),
        ]
        xml = self._run({"BA-Samuel.json": samuel}, "samuel_1")
        self.assertIn("urn:x-opensiddur:text:bible:samuel_1/1/1", xml)
        self.assertIn("וַיְהִי אִישׁ אֶחָד", xml)
        self.assertNotIn("אַחֲרֵי֙", xml)

    @patch("opensiddur.importer.miqra_al_pi_hamasorah.convert.validate")
    def test_twelve_writes_hosea(self, mock_validate):
        # The Twelve are one book of the 24, each prophet a sub-book named in full (הושע).
        mock_validate.return_value = (True, [])
        twelve = [book39("ספר תרי עשר", {"1": {"1": verse(["דְּבַר יְהוָה"])}}, "הושע")]
        xml = self._run({"CA-The-12-Minor-Prophets.json": twelve}, "hosea")
        self.assertIn("urn:x-opensiddur:text:bible:hosea/1/1", xml)
        self.assertIn("דְּבַר יְהוָה", xml)

    @patch("opensiddur.importer.miqra_al_pi_hamasorah.convert.validate")
    def test_megillah_writes_ruth(self, mock_validate):
        # The megillot are named with "מגילת " instead of "ספר ".
        mock_validate.return_value = (True, [])
        ruth = [book39("מגילת רות", {"1": {"1": verse(["וַיְהִי בִּימֵי"])}})]
        xml = self._run({"E2-Ruth.json": ruth}, "ruth")
        self.assertIn("urn:x-opensiddur:text:bible:ruth/1/1", xml)
        self.assertIn("וַיְהִי בִּימֵי", xml)

    @patch("opensiddur.importer.miqra_al_pi_hamasorah.convert.validate")
    def test_only_book_numbers_the_notes_as_a_full_run_does(self, mock_validate):
        # Exodus's note follows Genesis's, whether Exodus is written alone or with every book.
        mock_validate.return_value = (True, [])
        note = {"tmpl_name": "נוסח", "tmpl_params": {"1": "א", "2": "הערה"}}
        genesis = book39("ספר בראשית", {"1": {"1": verse([note])}})
        exodus = book39("ספר שמות", {"1": {"1": verse([note])}})
        with tempfile.TemporaryDirectory() as tmp:
            sourcetexts_root = Path(tmp) / "sources"
            write_source(
                sourcetexts_root,
                with_other_books({"A1-Genesis.json": [genesis], "A2-Exodus.json": [exodus]}),
            )
            self.assertEqual(_convert(sourcetexts_root, Path(tmp) / "full"), 0)
            self.assertEqual(_convert(sourcetexts_root, Path(tmp) / "one", "--only-book", "exodus"), 0)
            full = (Path(tmp) / "full" / "exodus.xml").read_bytes()
            one = (Path(tmp) / "one" / "exodus.xml").read_bytes()
        self.assertEqual(one, full)
        self.assertIn(b"miqra-note-2", one)
        self.assertNotIn(b'xml:id="miqra-note-1"', one)

    @patch("opensiddur.importer.miqra_al_pi_hamasorah.convert.validate")
    def test_a_missing_book_stops_the_run_before_it_writes(self, mock_validate):
        mock_validate.return_value = (True, [])
        genesis = book39("ספר בראשית", {"1": {"1": verse(["א"])}})
        with tempfile.TemporaryDirectory() as tmp:
            sourcetexts_root = Path(tmp) / "sources"
            write_source(sourcetexts_root, {"A1-Genesis.json": [genesis]})
            project_dir = Path(tmp) / "project"
            with self.assertRaisesRegex(PlusFormatError, "have no Exodus"):
                _convert(sourcetexts_root, project_dir)
            self.assertFalse(project_dir.exists())

    @patch("opensiddur.importer.miqra_al_pi_hamasorah.convert.validate")
    def test_check_converts_and_writes_nothing(self, mock_validate):
        mock_validate.return_value = (True, [])
        with tempfile.TemporaryDirectory() as tmp:
            sourcetexts_root = Path(tmp) / "sources"
            write_source(sourcetexts_root, with_other_books({}))
            project_dir = Path(tmp) / "project"
            self.assertEqual(_convert(sourcetexts_root, project_dir, "--check"), 0)
            self.assertFalse(project_dir.exists())

    def test_check_refuses_an_unknown_template(self):
        genesis = book39("ספר בראשית", {"1": {"1": verse([{"tmpl_name": "גלגל"}])}})
        with tempfile.TemporaryDirectory() as tmp:
            sourcetexts_root = Path(tmp) / "sources"
            write_source(sourcetexts_root, with_other_books({"A1-Genesis.json": [genesis]}))
            with self.assertRaisesRegex(PlusFormatError, "unknown template"):
                _convert(sourcetexts_root, Path(tmp) / "project", "--check")

    def test_book_names_resolve_sub_book_abbreviations(self):
        self.assertEqual(_book_name_he(book39("ספר שמואל", {}, 'שמ"א')), "שמואל א")
        self.assertEqual(_book_name_he(book39("ספר מלכים", {}, 'מל"ב')), "מלכים ב")
        self.assertEqual(_book_name_he(book39("ספר דברי הימים", {}, 'דה"א')), "דברי הימים א")

    def test_book_names_keep_full_sub_book_names(self):
        self.assertEqual(_book_name_he(book39("ספר תרי עשר", {}, "הושע")), "הושע")
        self.assertEqual(_book_name_he(book39("ספר עזרא", {}, "נחמיה")), "נחמיה")

    def test_book_names_strip_the_book_prefix(self):
        self.assertEqual(_book_name_he(book39("ספר בראשית", {})), "בראשית")
        self.assertEqual(_book_name_he(book39("מגילת איכה", {})), "איכה")


class TestFrontMatter(unittest.TestCase):
    def test_the_index_names_the_commit_and_quotes_the_attributions(self):
        with tempfile.TemporaryDirectory() as tmp:
            sourcetexts_root = Path(tmp)
            write_source(sourcetexts_root, {})
            source = load_source(sourcetexts_root)
        front = front_matter(source)
        self.assertIn(f"at commit {COMMIT}", front)
        self.assertIn("https://en.wikisource.org/wiki/User:Dovi/Miqra_according_to_the_Masorah#beginning", front)
        self.assertIn('shall be to &quot;Hebrew Wikisource&quot;', front)
        self.assertIn("הייחוס בעברית", front)
        self.assertIn(f"at commit {COMMIT}", source.note(with_commit=True))
        self.assertNotIn(COMMIT, source.note())

    def test_the_index_quotes_the_credit_to_mams_editors(self):
        with tempfile.TemporaryDirectory() as tmp:
            sourcetexts_root = Path(tmp)
            write_source(sourcetexts_root, {})
            source = load_source(sourcetexts_root)
        front = front_matter(source)
        self.assertIn(
            '<tei:p xml:lang="en">&quot;Miqra according to the Masorah&quot; as found in this '
            "spreadsheet was prepared by Seth (Avi) Kadish from materials that he originally "
            "developed at Hebrew Wikisource, with major technical assistance from Erel "
            "Segal-Halevi and Benjamin Denckla. All of the material is available under the "
            "CC-BY-SA 4.0 license, which is found at the following link: "
            '<tei:ref target="https://creativecommons.org/licenses/by-sa/4.0/">CC-BY-SA 4.0'
            "</tei:ref></tei:p>",
            front,
        )
        self.assertIn("ובעזרת תמיכה טכנית מכרעת מאת אראל סגל-הלוי ובנימין דנקלה", front)
        # Each language's credit comes before its attribution.
        self.assertLess(front.index("Seth (Avi) Kadish"), front.index("Attribution in English"))
        self.assertLess(front.index("אבי קדיש"), front.index("הייחוס בעברית"))

    def test_a_licence_without_the_credits_is_refused(self):
        with self.assertRaises(ValueError):
            read_credits("Attribution: Hebrew Wikisource\n")

    def test_a_licence_without_the_attributions_is_refused(self):
        with self.assertRaises(ValueError):
            read_attributions("License: CC-BY-SA 4.0\n")


class TestLoadSource(unittest.TestCase):
    """load_source reads the files the manifest lists, only if they are the files it lists."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sourcetexts_root = Path(self.tmp.name)
        ruth = book39("מגילת רות", {"1": {"1": verse(["ויהי בימי"])}})
        self.data_dir = write_source(self.sourcetexts_root, {"E2-Ruth.json": [ruth]})

    def test_the_listed_files_load(self):
        self.assertEqual(list(load_source(self.sourcetexts_root).book39s), ["רות"])

    def test_a_file_that_differs_from_the_manifest_is_refused(self):
        for name in ("plus/E2-Ruth.json", "LICENSE.md"):
            path = self.data_dir / name
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            with self.subTest(name=name), self.assertRaisesRegex(PlusFormatError, "is not the file"):
                load_source(self.sourcetexts_root)
            path.write_bytes(original)

    def test_a_missing_file_is_refused(self):
        (self.data_dir / "plus" / "E2-Ruth.json").unlink()
        with self.assertRaisesRegex(PlusFormatError, "is missing"):
            load_source(self.sourcetexts_root)

    def test_a_json_file_the_manifest_does_not_list_is_refused(self):
        (self.data_dir / "plus" / "E3-Lamentations.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(PlusFormatError, "does not list"):
            load_source(self.sourcetexts_root)

    def test_a_book39_with_an_unknown_key_is_refused(self):
        ruth = {**book39("מגילת רות", {"1": {"1": verse(["ויהי"])}}), "extra": 1}
        write_source(self.sourcetexts_root, {"E2-Ruth.json": [ruth]})
        with self.assertRaisesRegex(PlusFormatError, "book39"):
            load_source(self.sourcetexts_root)


class TestIndexUrnName(unittest.TestCase):
    def test_the_canon_is_tanakh_and_other_indexes_their_file(self):
        from opensiddur.importer.miqra_al_pi_hamasorah.convert import index_urn_name
        self.assertEqual(index_urn_name("index"), "tanakh")
        self.assertEqual(index_urn_name("the_prophets"), "the_prophets")


class TestHeaderUrn(unittest.TestCase):
    def test_the_header_names_its_entrypoint(self):
        from opensiddur.importer.miqra_al_pi_hamasorah.convert import MIQRA_PROJECT, header
        self.assertIn(f">urn:x-opensiddur:text:bible:amos@{MIQRA_PROJECT}<",
                      header(None, "Amos", entrypoint="amos", source_note="note"))
        self.assertIn(f">urn:x-opensiddur:text:bible:tanakh@{MIQRA_PROJECT}<",
                      header(None, "Tanakh", source_note="note"))

if __name__ == "__main__":
    unittest.main()
