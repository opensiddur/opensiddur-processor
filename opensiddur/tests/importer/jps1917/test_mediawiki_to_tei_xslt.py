"""Tests for the JPS 1917 MediaWiki → JLPTEI stylesheet
(``opensiddur/importer/jps1917/mediawiki_to_tei.xslt``), focused on the
``__link__`` template that resolves wikilinks to ``urn:x-opensiddur:text:bible:``
targets.

These run the transformation directly over hand-written intermediate XML, so
they exercise the stylesheet without depending on real Wikisource pages.
"""

import unittest
from pathlib import Path

from lxml import etree

from opensiddur.common.xslt import xslt_transform_string

TEI_NS = "http://www.tei-c.org/ns/1.0"
NS = {"tei": TEI_NS}

MEDIAWIKI_TO_TEI_XSLT = (
    Path(__file__).parents[3] / "importer" / "jps1917" / "mediawiki_to_tei.xslt"
)


def _transform(link_xml: str, book_name: str) -> etree._Element:
    xml = f"<mediawikis>{link_xml}</mediawikis>"
    outputs = xslt_transform_string(
        MEDIAWIKI_TO_TEI_XSLT,
        xml,
        multiple_results=True,
        xslt_params={"book_name": book_name, "is_section": False},
    )
    return etree.fromstring(f"<root xmlns:tei='{TEI_NS}'>{outputs['']}</root>")


def _ref_target(link_xml: str, book_name: str = "genesis") -> str:
    root = _transform(link_xml, book_name)
    refs = root.findall(".//tei:ref", NS)
    return refs[0].get("target")


class TestLinkResolution(unittest.TestCase):
    """Test resolution of __link__ wikilinks to bible URNs"""

    def test_page_and_anchor(self):
        """A link naming a page and a chapter:verse anchor resolves both."""
        target = _ref_target(
            '<__link__ title="Bible (Jewish Publication Society 1917)/Exodus#3:14">Exodus</__link__>'
        )
        self.assertEqual(target, "urn:x-opensiddur:text:bible:exodus/3/14")

    def test_same_page_anchor_only(self):
        """A same-page anchor (no page name) resolves against the book being
        converted rather than producing an empty book segment. Regression
        test for issue #50."""
        target = _ref_target(
            '<__link__ title="#19:20">verse 20</__link__>', book_name="genesis"
        )
        self.assertEqual(target, "urn:x-opensiddur:text:bible:genesis/19/20")

    def test_same_page_anchor_roman_numeral_book(self):
        """The book-name normalization (I/II -> _1/_2) is a no-op for an
        already-normalized $book_name used on a same-page anchor."""
        target = _ref_target(
            '<__link__ title="#4:5">verse 5</__link__>', book_name="kings_1"
        )
        self.assertEqual(target, "urn:x-opensiddur:text:bible:kings_1/4/5")

    def test_page_without_anchor(self):
        """A link naming a page but no anchor (table-of-contents links)
        degrades to a book-level URN instead of empty chapter/verse
        segments."""
        target = _ref_target(
            '<__link__ title="Bible (Jewish Publication Society 1917)/Zephaniah">Zephaniah</__link__>'
        )
        self.assertEqual(target, "urn:x-opensiddur:text:bible:zephaniah")

    def test_page_with_roman_numeral_book(self):
        """Book normalization still applies for the page+anchor case."""
        target = _ref_target(
            '<__link__ title="Bible (Jewish Publication Society 1917)/I Kings#4:5">I Kings</__link__>'
        )
        self.assertEqual(target, "urn:x-opensiddur:text:bible:kings_1/4/5")



class TestRepeatedVerse(unittest.TestCase):
    """A liturgically repeated verse, set in smaller type at the end of a book."""

    def test_its_lines_are_kept_as_lines(self):
        """{{gap}} opens each line and <br /> ends it, as in Malachi's repetition of 3:23."""
        root = _transform(
            '<span style="font-size: 83%;">\n<gap/>Behold, I will send you<br/>\n'
            '<gap/>Elijah the prophet<br/>\n<gap/>Before the coming<br/>\n'
            '<gap/>Of the great and terrible day of the <sc>Lord</sc>.\n</span>',
            "malachi")
        repetition = root.find(".//tei:ab[@type='repetition']", NS)
        self.assertIsNotNone(repetition)
        self.assertIsNone(repetition.find("tei:list", NS))
        self.assertEqual(4, len(repetition.findall("tei:lb", NS)))
        text = " ".join("".join(repetition.itertext()).split())
        self.assertEqual("Behold, I will send you Elijah the prophet Before the coming "
                         "Of the great and terrible day of the Lord.", text)


if __name__ == "__main__":
    unittest.main()


class TestPageBreaks(unittest.TestCase):
    """A page break records its printed number and links to its page of the scan."""

    def _breaks(self, pages: str, **params) -> list:
        outputs = xslt_transform_string(
            MEDIAWIKI_TO_TEI_XSLT, f"<mediawikis>{pages}</mediawikis>",
            multiple_results=True,
            xslt_params={"book_name": "genesis", "is_section": False, **params})
        root = etree.fromstring(f"<root xmlns:tei='{TEI_NS}'>{outputs['']}</root>")
        return root.findall(".//tei:pb", NS)

    _PAGE = '<mediawiki scan="25">Text<noinclude><c>3</c></noinclude></mediawiki>'

    def test_a_page_links_to_its_scan(self):
        pb, = self._breaks(self._PAGE, facs_prefix="https://scan.example/Page:Book/")
        self.assertEqual("3", pb.get("n"))
        self.assertEqual("1917", pb.get("ed"))
        self.assertEqual("https://scan.example/Page:Book/25", pb.get("facs"))

    def test_without_a_prefix_there_is_no_link(self):
        pb, = self._breaks(self._PAGE)
        self.assertIsNone(pb.get("facs"))

    def test_a_page_with_no_scan_number_has_no_link(self):
        pb, = self._breaks('<mediawiki>Text<noinclude><c>3</c></noinclude></mediawiki>',
                           facs_prefix="https://scan.example/Page:Book/")
        self.assertIsNone(pb.get("facs"))
