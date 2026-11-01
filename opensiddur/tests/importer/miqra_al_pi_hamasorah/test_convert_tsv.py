import csv
import io
import unittest
from pathlib import Path
from unittest.mock import patch
import tempfile


from opensiddur.importer.miqra_al_pi_hamasorah.convert_tsv import (
    _book_key_from_page_key,
    _chapter_from_page_key,
    _extract_chapter_verse_numbers,
    _split_page_key,
    main,
)


def _tsv_rows(*rows: list[str]) -> str:
    buf = io.StringIO()
    csv.writer(buf, delimiter="\t").writerows(rows)
    return buf.getvalue()


class TestMiqraConvertTsv(unittest.TestCase):
    @patch("opensiddur.importer.miqra_al_pi_hamasorah.convert_tsv.validate")
    def test_only_book_writes_output(self, mock_validate):
        mock_validate.return_value = (True, [])

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sourcetexts_root = tmp_path / "sources"
            sheets_dir = sourcetexts_root / "miqra_al_pi_hamasorah" / "sheets"
            sheets_dir.mkdir(parents=True, exist_ok=True)

            # Minimal README (front matter)
            (sheets_dir / "readme.tsv").write_text(
                "License\tCC-BY-SA 4.0\nAttribution\tHebrew Wikisource\n",
                encoding="utf-8",
            )

            # Torah TSV: parashah in nav + two verses in one paragraph
            (sheets_dir / "torah.tsv").write_text(
                "\t".join(["Page key", "Row id", "Nav", "Scaffold", "Text"])
                + "\n"
                + "\t".join(
                    [
                        "ספר בראשית/א",
                        "א",
                        "//{{פפ}}//",
                        "{{מ:פסוק|בראשית|1|1}}",
                        '{{נוסח|{{מ:אות-ג|בְּ}}רֵאשִׁ֖ית|2=test note}}',
                    ]
                )
                + "\n"
                + "\t".join(
                    [
                        "ספר בראשית/א",
                        "ב",
                        "",
                        "{{מ:פסוק|בראשית|1|2}}",
                        "וְהָאָ֗רֶץ הָיְתָ֥ה תֹ֙הוּ֙ וָבֹ֔הוּ",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            project_dir = tmp_path / "project"
            rc = main(
                [
                    "--sourcetexts-root",
                    str(sourcetexts_root),
                    "--project-dir",
                    str(project_dir),
                    "--only-book",
                    "genesis",
                ]
            )
            self.assertEqual(rc, 0)

            genesis_xml = project_dir / "genesis.xml"
            self.assertTrue(genesis_xml.exists())
            xml = genesis_xml.read_text(encoding="utf-8")
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

    def test_special_tsv_row_does_not_produce_invalid_urn_segments(self):
        # special.tsv uses a 2-column schema; must not be merged into book output.
        ch, v = _extract_chapter_verse_numbers(
            "ספר שמות/טו תתת",
            "<noinclude>{{#קטע:שירת הים/צורת השיר|צורת-השיר}}{{מ:טעמי",
            "",
        )
        self.assertEqual(ch, "")
        self.assertEqual(v, "")

    @patch("opensiddur.importer.miqra_al_pi_hamasorah.convert_tsv.validate")
    def test_special_tsv_not_merged_into_book(self, mock_validate):
        mock_validate.return_value = (True, [])

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sourcetexts_root = tmp_path / "sources"
            sheets_dir = sourcetexts_root / "miqra_al_pi_hamasorah" / "sheets"
            sheets_dir.mkdir(parents=True, exist_ok=True)

            (sheets_dir / "torah.tsv").write_text(
                "\t".join(["Page key", "Row id", "Nav", "Scaffold", "Text"])
                + "\n"
                + "\t".join(
                    [
                        "ספר שמות/טו",
                        "א",
                        "",
                        "{{מ:פסוק|שמות|15|1}}",
                        "שירה",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (sheets_dir / "special.tsv").write_text(
                "ספר שמות/טו תתת\t{{#קטע:שירת הים/צורת השיר|צורת-השיר}}{{מ:טעמי\n",
                encoding="utf-8",
            )

            project_dir = tmp_path / "project"
            main(
                [
                    "--sourcetexts-root",
                    str(sourcetexts_root),
                    "--project-dir",
                    str(project_dir),
                    "--only-book",
                    "exodus",
                ]
            )
            xml = (project_dir / "exodus.xml").read_text(encoding="utf-8")
            self.assertIn("urn:x-opensiddur:text:bible:exodus/15/1", xml)
            self.assertNotIn("צורת-השיר", xml)
            self.assertNotIn("השיר|", xml)


    @patch("opensiddur.importer.miqra_al_pi_hamasorah.convert_tsv.validate")
    def test_split_book_tab_writes_samuel_1(self, mock_validate):
        # neviim_rishonim.tsv groups Samuel under one outer "ספר שמואל" label,
        # with the sub-book abbreviation (שמ"א) embedded alongside the chapter.
        mock_validate.return_value = (True, [])

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sourcetexts_root = tmp_path / "sources"
            sheets_dir = sourcetexts_root / "miqra_al_pi_hamasorah" / "sheets"
            sheets_dir.mkdir(parents=True, exist_ok=True)

            (sheets_dir / "neviim_rishonim.tsv").write_text(
                _tsv_rows(
                    ["Page key", "Row id", "Nav", "Scaffold", "Text"],
                    [
                        'ספר שמואל/שמ"א א',
                        "א",
                        "",
                        "{{מ:פסוק|שמואל א|1|1}}",
                        "וַיְהִי אִישׁ אֶחָד",
                    ],
                ),
                encoding="utf-8",
            )

            project_dir = tmp_path / "project"
            rc = main(
                [
                    "--sourcetexts-root",
                    str(sourcetexts_root),
                    "--project-dir",
                    str(project_dir),
                    "--only-book",
                    "samuel_1",
                ]
            )
            self.assertEqual(rc, 0)

            xml = (project_dir / "samuel_1.xml").read_text(encoding="utf-8")
            self.assertIn("urn:x-opensiddur:text:bible:samuel_1/1/1", xml)
            self.assertIn("וַיְהִי אִישׁ אֶחָד", xml)

    @patch("opensiddur.importer.miqra_al_pi_hamasorah.convert_tsv.validate")
    def test_twelve_tab_writes_hosea(self, mock_validate):
        # neviim_acharonim.tsv groups the Twelve Minor Prophets under one outer
        # "ספר תרי עשר" label, with the actual book name embedded alongside
        # the chapter (e.g. "הושע א").
        mock_validate.return_value = (True, [])

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sourcetexts_root = tmp_path / "sources"
            sheets_dir = sourcetexts_root / "miqra_al_pi_hamasorah" / "sheets"
            sheets_dir.mkdir(parents=True, exist_ok=True)

            (sheets_dir / "neviim_acharonim.tsv").write_text(
                _tsv_rows(
                    ["Page key", "Row id", "Nav", "Scaffold", "Text"],
                    [
                        "ספר תרי עשר/הושע א",
                        "א",
                        "",
                        "{{מ:פסוק|הושע|1|1}}",
                        "דְּבַר יְהוָה",
                    ],
                ),
                encoding="utf-8",
            )

            project_dir = tmp_path / "project"
            rc = main(
                [
                    "--sourcetexts-root",
                    str(sourcetexts_root),
                    "--project-dir",
                    str(project_dir),
                    "--only-book",
                    "hosea",
                ]
            )
            self.assertEqual(rc, 0)

            xml = (project_dir / "hosea.xml").read_text(encoding="utf-8")
            self.assertIn("urn:x-opensiddur:text:bible:hosea/1/1", xml)
            self.assertIn("דְּבַר יְהוָה", xml)

    @patch("opensiddur.importer.miqra_al_pi_hamasorah.convert_tsv.validate")
    def test_megillot_tab_writes_ruth(self, mock_validate):
        # chamisha_megillot.tsv uses the "מגילת " prefix instead of "ספר ".
        mock_validate.return_value = (True, [])

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sourcetexts_root = tmp_path / "sources"
            sheets_dir = sourcetexts_root / "miqra_al_pi_hamasorah" / "sheets"
            sheets_dir.mkdir(parents=True, exist_ok=True)

            (sheets_dir / "chamisha_megillot.tsv").write_text(
                _tsv_rows(
                    ["Page key", "Row id", "Nav", "Scaffold", "Text"],
                    [
                        "מגילת רות/א",
                        "א",
                        "",
                        "{{מ:פסוק|רות|1|1}}",
                        "וַיְהִי בִּימֵי",
                    ],
                ),
                encoding="utf-8",
            )

            project_dir = tmp_path / "project"
            rc = main(
                [
                    "--sourcetexts-root",
                    str(sourcetexts_root),
                    "--project-dir",
                    str(project_dir),
                    "--only-book",
                    "ruth",
                ]
            )
            self.assertEqual(rc, 0)

            xml = (project_dir / "ruth.xml").read_text(encoding="utf-8")
            self.assertIn("urn:x-opensiddur:text:bible:ruth/1/1", xml)
            self.assertIn("וַיְהִי בִּימֵי", xml)

    def test_split_page_key_resolves_subbook_abbreviations(self):
        self.assertEqual(
            _split_page_key('ספר שמואל/שמ"א א'), ("שמואל א", "א")
        )
        self.assertEqual(
            _split_page_key('ספר מלכים/מל"ב יג'), ("מלכים ב", "יג")
        )
        self.assertEqual(
            _split_page_key('ספר דברי הימים/דה"א ג'), ("דברי הימים א", "ג")
        )

    def test_split_page_key_resolves_full_subbook_labels(self):
        # The Twelve and Ezra/Nehemiah sub-labels already match TANAKH_INDEX
        # names verbatim, so no abbreviation lookup is needed for them.
        self.assertEqual(_split_page_key("ספר תרי עשר/הושע א"), ("הושע", "א"))
        self.assertEqual(_split_page_key("ספר עזרא/נחמיה ה"), ("נחמיה", "ה"))
        self.assertEqual(_split_page_key("ספר עזרא/עזרא ב"), ("עזרא", "ב"))

    def test_split_page_key_strips_megillat_prefix(self):
        self.assertEqual(_split_page_key("מגילת איכה/ג"), ("איכה", "ג"))

    def test_split_page_key_ungrouped_book(self):
        self.assertEqual(_split_page_key("ספר בראשית/א"), ("בראשית", "א"))

    def test_book_and_chapter_from_page_key_wrappers(self):
        self.assertEqual(_book_key_from_page_key('ספר שמואל/שמ"א א'), "שמואל א")
        self.assertEqual(_chapter_from_page_key('ספר שמואל/שמ"א א'), "1")
        self.assertEqual(_book_key_from_page_key(""), None)
        self.assertEqual(_chapter_from_page_key(""), "")


class TestIndexUrnName(unittest.TestCase):
    def test_the_canon_is_tanakh_and_other_indexes_their_file(self):
        from opensiddur.importer.miqra_al_pi_hamasorah.convert_tsv import index_urn_name
        self.assertEqual(index_urn_name("index"), "tanakh")
        self.assertEqual(index_urn_name("the_prophets"), "the_prophets")


class TestHeaderUrn(unittest.TestCase):
    def test_the_header_names_its_entrypoint(self):
        from opensiddur.importer.miqra_al_pi_hamasorah.convert_tsv import MIQRA_PROJECT, header
        self.assertIn(f">urn:x-opensiddur:text:bible:amos@{MIQRA_PROJECT}<",
                      header(None, "Amos", entrypoint="amos"))
        self.assertIn(f">urn:x-opensiddur:text:bible:tanakh@{MIQRA_PROJECT}<",
                      header(None, "Tanakh"))

if __name__ == "__main__":
    unittest.main()
