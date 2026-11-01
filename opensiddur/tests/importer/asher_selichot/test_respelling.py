"""The Asher book's names are respelled once built, while its readings keep their own."""
import unittest
from pathlib import Path
from unittest.mock import patch

from lxml import etree

from opensiddur.common.validate_names import Spellings
from opensiddur.importer.asher_selichot import build

#: Spelling lists of the tests' own, so that these do not change with the real ones.
SHARED = Spellings(frozenset(), {"rahamekha": "rachamekha", "tsom": "tzom"})
BOOK = Spellings(frozenset(), {"selah": "selach"})
#: The book's list as a file, for its renames; its variants are read through ``lists``.
BOOK_FILE = Path(__file__).with_name("book_spellings.yaml")


def lists(path=None):
    return BOOK if path == build.BOOK_SPELLINGS else SHARED
TEI = "http://www.tei-c.org/ns/1.0"
J = "http://jewishliturgy.org/ns/jlptei/2"
URN = "urn:x-opensiddur:text:prayer:"


def document(body):
    return etree.fromstring(f'<tei:TEI xmlns:tei="{TEI}" xmlns:j="{J}">{body}</tei:TEI>')


class RespelledTestCase(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(build, "load_spellings", side_effect=lists)
        patcher.start()
        self.addCleanup(patcher.stop)
        reader = patch.object(build, "BOOK_SPELLINGS", BOOK_FILE)
        reader.start()
        self.addCleanup(reader.stop)
        build._book.cache_clear()
        self.addCleanup(build._book.cache_clear)

    def test_file_names_and_urns_are_respelled_and_renames_reported(self):
        project = Path("/projects/selichoth-asher-1912-he")
        root = document(
            f'<tei:idno type="urn">{URN}ki_al_rahamekha@selichoth-asher-1912-he</tei:idno>'
            f'<tei:div corresp="{URN}ki_al_rahamekha"><j:transclude target="{URN}tsom/opening"/>'
            '<tei:p>rahamekha stays in the text</tei:p></tei:div>')
        unchanged = document(f'<tei:div corresp="{URN}ashrei"/>')
        documents, renamed = build.respelled([
            (project / "ki_al_rahamekha.xml", root), (project / "ashrei.xml", unchanged)])
        self.assertEqual([p.name for p, _ in documents], ["ki_al_rachamekha.xml", "ashrei.xml"])
        self.assertEqual(renamed, [project / "ki_al_rahamekha.xml"])
        text = etree.tostring(documents[0][1], encoding="unicode")
        self.assertIn(f"{URN}ki_al_rachamekha@selichoth-asher-1912-he<", text)
        self.assertIn(f'corresp="{URN}ki_al_rachamekha"', text)
        self.assertIn(f'target="{URN}tzom/opening"', text)
        self.assertIn("rahamekha stays in the text", text)

    def test_the_verifiers_look_names_up_the_same_way(self):
        self.assertEqual(build.spelled_name("ki_al_rahamekha"), "ki_al_rachamekha")
        self.assertEqual(build.spelled_urn(f"{URN}tsom@selichoth-asher-1912-he"),
                         f"{URN}tzom@selichoth-asher-1912-he")

    def test_the_books_own_list_is_applied_with_the_shared_one(self):
        project = Path("/projects/selichoth-asher-1912-he")
        documents, _ = build.respelled(
            [(project / "selah_na.xml", document(f'<tei:div corresp="{URN}selah_na/tsom"/>'))])
        path, root = documents[0]
        self.assertEqual(path.name, "selach_na.xml")
        self.assertIn(f'corresp="{URN}selach_na/tzom"', etree.tostring(root, encoding="unicode"))
        self.assertEqual(build.spelled_name("selah_na"), "selach_na")

    def test_a_whole_name_is_renamed_after_its_words_are_respelled(self):
        self.assertEqual(build.spelled_name("al_tsom_tachanun"), "al_tzom_techinnah")
        self.assertEqual(build.spelled_name("tachanun"), "tachanun")
        self.assertEqual(build.spelled_urn(f"{URN}al_tsom_tachanun/stanza_1@selichoth-asher-1912-he"),
                         f"{URN}al_tzom_techinnah/stanza_1@selichoth-asher-1912-he")
        documents, renamed = build.respelled([(Path("/p/al_tsom_tachanun.xml"), document(""))])
        self.assertEqual(documents[0][0].name, "al_tzom_techinnah.xml")

    def test_the_books_list_may_not_repeat_or_contradict_the_shared_one(self):
        # a shared variant, a shared variant as the book's standard, a shared standard
        for book in ({"tsom": "tzom"}, {"tzom": "tsom"}, {"tzom": "x"}):
            with self.subTest(book=book), patch.object(
                    build, "load_spellings",
                    side_effect=lambda path=None, book=book: Spellings(frozenset(), book)
                    if path == build.BOOK_SPELLINGS else SHARED):
                build._book.cache_clear()
                with self.assertRaises(ValueError):
                    build.book_spellings()


if __name__ == "__main__":
    unittest.main()
