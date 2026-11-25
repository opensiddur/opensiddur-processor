import re
import unittest
from unittest.mock import ANY, patch, MagicMock, mock_open
import tempfile
import os
from pathlib import Path

from lxml import etree

from opensiddur.exporter.constants import TEI_NS
from opensiddur.common.versification import JPS_PROJECT
from opensiddur.importer.jps1917.convert_wikisource import (
    get_credits_pages, header, tei_file, process_mediawiki, validate_and_write_tei_file,
    book_file, index_file, Book, Index, mediawiki_xml_to_tei, main, make_project_directory,
    TITLE_PAGE, prepend_to_front, FALLBACK_DOWNLOAD_DATE, source_download_date,
)
from opensiddur.importer.util.pages import jps1917_data_directory
from opensiddur.importer.util.wikisource_book import save_manifest
from opensiddur.importer.util.parshiyot import skeleton_map_json
from opensiddur.importer.util.validation import validate_with_start, validate


class TestGetCreditsPages(unittest.TestCase):
    """Tests for get_credits_pages function."""

    @patch('opensiddur.importer.jps1917.convert_wikisource.get_credits')
    def test_normal_case(self, mock_get_credits):
        """Test normal case with different credits on each page."""
        # Mock get_credits to return different lists for each page
        mock_get_credits.side_effect = [
            ["Alice", "Bob"],
            ["Charlie"],
            ["David", "Eve"],
        ]
        
        result = get_credits_pages(1, 3)
        
        # Should be sorted and unique
        self.assertEqual(result, ["Alice", "Bob", "Charlie", "David", "Eve"])
        
        # Verify get_credits was called for each page
        self.assertEqual(mock_get_credits.call_count, 3)
        mock_get_credits.assert_any_call(1, None)
        mock_get_credits.assert_any_call(2, None)
        mock_get_credits.assert_any_call(3, None)

    @patch('opensiddur.importer.jps1917.convert_wikisource.get_credits')
    def test_repeated_strings(self, mock_get_credits):
        """Test that repeated strings across pages are deduplicated."""
        # Mock get_credits to return overlapping credits
        mock_get_credits.side_effect = [
            ["Alice", "Bob"],
            ["Bob", "Charlie"],
            ["Charlie", "Alice"],
        ]
        
        result = get_credits_pages(1, 3)
        
        # Should contain each name only once, sorted
        self.assertEqual(result, ["Alice", "Bob", "Charlie"])
        self.assertEqual(mock_get_credits.call_count, 3)

    @patch('opensiddur.importer.jps1917.convert_wikisource.get_credits')
    def test_nonexistent_pages(self, mock_get_credits):
        """Test handling of nonexistent pages (get_credits returns None)."""
        # Mock get_credits to return None for some pages
        mock_get_credits.side_effect = [
            ["Alice", "Bob"],
            None,  # Nonexistent page
            ["Charlie"],
            None,  # Another nonexistent page
        ]
        
        result = get_credits_pages(1, 4)
        
        # Should only include credits from existing pages
        self.assertEqual(result, ["Alice", "Bob", "Charlie"])
        self.assertEqual(mock_get_credits.call_count, 4)

    @patch('opensiddur.importer.jps1917.convert_wikisource.get_credits')
    def test_all_nonexistent_pages(self, mock_get_credits):
        """Test when all pages are nonexistent."""
        mock_get_credits.return_value = None
        
        result = get_credits_pages(1, 3)
        
        # Should return empty list
        self.assertEqual(result, [])
        self.assertEqual(mock_get_credits.call_count, 3)

    @patch('opensiddur.importer.jps1917.convert_wikisource.get_credits')
    def test_empty_credits(self, mock_get_credits):
        """Test when pages return empty credit lists."""
        mock_get_credits.side_effect = [
            [],
            ["Alice"],
            [],
        ]
        
        result = get_credits_pages(1, 3)
        
        # Should only include the one credit
        self.assertEqual(result, ["Alice"])
        self.assertEqual(mock_get_credits.call_count, 3)

    @patch('opensiddur.importer.jps1917.convert_wikisource.get_credits')
    def test_single_page(self, mock_get_credits):
        """Test with a single page range."""
        mock_get_credits.return_value = ["Alice", "Bob"]
        
        result = get_credits_pages(5, 5)
        
        # Should return sorted credits from single page
        self.assertEqual(result, ["Alice", "Bob"])
        self.assertEqual(mock_get_credits.call_count, 1)
        mock_get_credits.assert_called_once_with(5, None)

    @patch('opensiddur.importer.jps1917.convert_wikisource.get_credits')
    def test_sorting(self, mock_get_credits):
        """Test that results are properly sorted alphabetically."""
        mock_get_credits.side_effect = [
            ["Zebra", "Alpha"],
            ["Charlie", "Beta"],
        ]
        
        result = get_credits_pages(1, 2)
        
        # Should be alphabetically sorted
        self.assertEqual(result, ["Alpha", "Beta", "Charlie", "Zebra"])


class TestHeaderDownloadDate(unittest.TestCase):
    """The sourceDesc date reports when the Wikisource pages were actually fetched."""

    def test_uses_the_date_it_is_given(self):
        result = header(
            book_name_he="בראשית",
            book_name_en="Genesis",
            source_download_date="2026-08-22",
        )
        self.assertIn("<tei:date>2026-08-22</tei:date>", result)

    def test_falls_back_when_no_date_is_known(self):
        result = header(book_name_he="בראשית", book_name_en="Genesis")
        self.assertIn(f"<tei:date>{FALLBACK_DOWNLOAD_DATE}</tei:date>", result)

    def test_reads_the_date_out_of_the_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_manifest(
                {"downloaded_at": "2026-08-22T21:15:00+00:00"},
                jps1917_data_directory(root),
            )
            self.assertEqual(source_download_date(root), "2026-08-22")

    def test_falls_back_when_the_tree_has_no_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(source_download_date(Path(tmp)), FALLBACK_DOWNLOAD_DATE)


class TestHeader(unittest.TestCase):
    """Tests for header function."""

    def test_basic_header_without_subtitles(self):
        """Test basic header generation with required fields only."""
        result = header(
            book_name_he="בראשית",
            book_name_en="Genesis",
        )
        
        # Should contain basic elements
        self.assertIn("<tei:teiHeader>", result)
        self.assertIn("</tei:teiHeader>", result)
        self.assertIn("<tei:title type=\"main\" xml:lang=\"en\">Genesis</tei:title>", result)
        self.assertIn("<tei:title type=\"alt\" xml:lang=\"he\">בראשית</tei:title>", result)
        self.assertIn(f"urn:x-opensiddur:text:bible:tanakh@{JPS_PROJECT}", result)
        
        # Should not contain subtitle elements
        self.assertNotIn("type=\"alt-sub\"", result)
        
        # Validate XML structure (namespaces added automatically by validate_with_start)
        is_valid, errors = validate_with_start(result, "tei:teiHeader")
        self.assertTrue(is_valid, f"Header XML is invalid: {errors}")
    
    def test_header_with_subtitles(self):
        """Test header with both Hebrew and English subtitles."""
        result = header(
            book_name_he="תורה נביאים וכתובים",
            book_name_en="The Holy Scriptures",
            book_sub_he="מסורה",
            book_sub_en="According to the Masoretic Text",
        )
        
        # Should contain subtitle elements
        self.assertIn("<tei:title type=\"alt-sub\" xml:lang=\"he\">מסורה</tei:title>", result)
        self.assertIn("<tei:title type=\"alt-sub\" xml:lang=\"en\">According to the Masoretic Text</tei:title>", result)
        
        # Validate XML structure (namespaces added automatically by validate_with_start)
        is_valid, errors = validate_with_start(result, "tei:teiHeader")
        self.assertTrue(is_valid, f"Header XML is invalid: {errors}")
    
    def test_header_with_only_hebrew_subtitle(self):
        """Test header with only Hebrew subtitle."""
        result = header(
            book_name_he="תהילים",
            book_name_en="Psalms",
            book_sub_he="ספר תהילים",
        )
        
        # Should contain Hebrew subtitle
        self.assertIn("<tei:title type=\"alt-sub\" xml:lang=\"he\">ספר תהילים</tei:title>", result)
        # Should not contain English subtitle
        self.assertNotIn("type=\"alt-sub\" xml:lang=\"en\"", result)
        
        # Validate XML structure (namespaces added automatically by validate_with_start)
        is_valid, errors = validate_with_start(result, "tei:teiHeader")
        self.assertTrue(is_valid, f"Header XML is invalid: {errors}")
    
    def test_header_with_only_english_subtitle(self):
        """Test header with only English subtitle."""
        result = header(
            book_name_he="משלי",
            book_name_en="Proverbs",
            book_sub_en="Book of Proverbs",
        )
        
        # Should contain English subtitle
        self.assertIn("<tei:title type=\"alt-sub\" xml:lang=\"en\">Book of Proverbs</tei:title>", result)
        # Should not contain Hebrew subtitle
        self.assertNotIn("type=\"alt-sub\" xml:lang=\"he\"", result)
        
        # Validate XML structure (namespaces added automatically by validate_with_start)
        is_valid, errors = validate_with_start(result, "tei:teiHeader")
        self.assertTrue(is_valid, f"Header XML is invalid: {errors}")
    
    def test_header_with_single_transcription_credit(self):
        """Test header with a single transcription credit."""
        result = header(
            book_name_he="רות",
            book_name_en="Ruth",
            transcription_credits=["John Doe"],
        )
        
        # Should contain respStmt for the contributor
        self.assertIn("<tei:respStmt>", result)
        self.assertIn("<tei:resp key=\"trc\">Transcribed by</tei:resp>", result)
        self.assertIn("John Doe", result)
        self.assertIn("urn:x-opensiddur:contributor:en.wikisource.org/John%20Doe", result)
        
        # Validate XML structure (namespaces added automatically by validate_with_start)
        is_valid, errors = validate_with_start(result, "tei:teiHeader")
        self.assertTrue(is_valid, f"Header XML is invalid: {errors}")
    
    def test_header_with_multiple_transcription_credits(self):
        """Test header with multiple transcription credits."""
        result = header(
            book_name_he="אסתר",
            book_name_en="Esther",
            transcription_credits=["Alice Smith", "Bob Jones", "Charlie Brown"],
        )
        
        # Should contain respStmt for each contributor
        self.assertIn("Alice Smith", result)
        self.assertIn("Bob Jones", result)
        self.assertIn("Charlie Brown", result)
        # Count occurrences of respStmt
        self.assertEqual(result.count("<tei:respStmt>"), 3)
        
        # Validate XML structure (namespaces added automatically by validate_with_start)
        is_valid, errors = validate_with_start(result, "tei:teiHeader")
        self.assertTrue(is_valid, f"Header XML is invalid: {errors}")
    
    def test_header_filters_wikisource_bot(self):
        """Test that Wikisource-bot is filtered out from credits."""
        result = header(
            book_name_he="דניאל",
            book_name_en="Daniel",
            transcription_credits=["Alice Smith", "Wikisource-bot", "Bob Jones"],
        )
        
        # Should contain Alice and Bob
        self.assertIn("Alice Smith", result)
        self.assertIn("Bob Jones", result)
        # Should NOT contain Wikisource-bot
        self.assertNotIn("Wikisource-bot", result)
        # Should only have 2 respStmt elements (not 3)
        self.assertEqual(result.count("<tei:respStmt>"), 2)
        
        # Validate XML structure (namespaces added automatically by validate_with_start)
        is_valid, errors = validate_with_start(result, "tei:teiHeader")
        self.assertTrue(is_valid, f"Header XML is invalid: {errors}")
    
    def test_header_with_no_credits(self):
        """Test header with empty transcription credits list."""
        result = header(
            book_name_he="איוב",
            book_name_en="Job",
            transcription_credits=[],
        )
        
        # Should not contain any respStmt elements
        self.assertNotIn("<tei:respStmt>", result)
        
        # Validate XML structure (namespaces added automatically by validate_with_start)
        is_valid, errors = validate_with_start(result, "tei:teiHeader")
        self.assertTrue(is_valid, f"Header XML is invalid: {errors}")
    
    def test_header_with_custom_namespace_and_entrypoint(self):
        """Test header with custom namespace and entrypoint."""
        result = header(
            book_name_he="שיר השירים",
            book_name_en="Song of Songs",
            namespace="custom_namespace",
            entrypoint="custom_entry",
            qualifier=":subsection",
        )
        
        # Should contain custom URN
        self.assertIn(f"urn:x-opensiddur:text:custom_namespace:custom_entry:subsection@{JPS_PROJECT}", result)
        
        # Validate XML structure (namespaces added automatically by validate_with_start)
        is_valid, errors = validate_with_start(result, "tei:teiHeader")
        self.assertTrue(is_valid, f"Header XML is invalid: {errors}")
    
    def test_header_with_custom_license(self):
        """Test header with custom license information."""
        result = header(
            book_name_he="קהלת",
            book_name_en="Ecclesiastes",
            license_url="https://example.com/license",
            license_name="Custom License",
        )
        
        # Should contain custom license
        self.assertIn("https://example.com/license", result)
        self.assertIn("Custom License", result)
        
        # Validate XML structure (namespaces added automatically by validate_with_start)
        is_valid, errors = validate_with_start(result, "tei:teiHeader")
        self.assertTrue(is_valid, f"Header XML is invalid: {errors}")
    
    def test_header_url_encoding_in_contributor_names(self):
        """Test that contributor names with spaces are properly URL encoded."""
        result = header(
            book_name_he="עזרא",
            book_name_en="Ezra",
            transcription_credits=["John Doe", "Jane Smith-Brown"],
        )
        
        # Should contain URL-encoded names in URN
        self.assertIn("urn:x-opensiddur:contributor:en.wikisource.org/John%20Doe", result)
        self.assertIn("urn:x-opensiddur:contributor:en.wikisource.org/Jane%20Smith-Brown", result)
        
        # Validate XML structure (namespaces added automatically by validate_with_start)
        is_valid, errors = validate_with_start(result, "tei:teiHeader")
        self.assertTrue(is_valid, f"Header XML is invalid: {errors}")
    
    def test_header_contains_required_metadata(self):
        """Test that header contains all required metadata elements."""
        result = header(
            book_name_he="במדבר",
            book_name_en="Numbers",
        )
        
        # Check for required metadata elements
        self.assertIn("<tei:fileDesc>", result)
        self.assertIn("<tei:titleStmt>", result)
        self.assertIn("<tei:publicationStmt>", result)
        self.assertIn("<tei:distributor>", result)
        self.assertIn("Open Siddur Project", result)
        self.assertIn("<tei:availability", result)
        self.assertIn("<tei:sourceDesc>", result)
        self.assertIn("<tei:bibl>", result)
        self.assertIn("Bible (Jewish Publication Society 1917)", result)
        self.assertIn("Wikisource", result)
        self.assertIn("Jewish Publication Society of America", result)
        
        # Validate XML structure (namespaces added automatically by validate_with_start)
        is_valid, errors = validate_with_start(result, "tei:teiHeader")
        self.assertTrue(is_valid, f"Header XML is invalid: {errors}")


class TestTeiFile(unittest.TestCase):
    """Tests for tei_file function."""
    
    def test_basic_tei_file_with_header_only(self):
        """Test basic TEI file generation with just a header."""
        test_header = """<tei:teiHeader>
            <tei:fileDesc>
                <tei:titleStmt>
                    <tei:title>Test Title</tei:title>
                </tei:titleStmt>
                <tei:publicationStmt>
                    <tei:distributor>Test Distributor</tei:distributor>
                </tei:publicationStmt>
                <tei:sourceDesc>
                    <tei:p>Test source</tei:p>
                </tei:sourceDesc>
            </tei:fileDesc>
        </tei:teiHeader>"""
        
        body_content = """<tei:body>
            <tei:p>Test body</tei:p>
        </tei:body>"""
        
        result = tei_file(header=test_header, body=body_content)
        
        # Should contain root TEI element with namespaces
        self.assertIn('<tei:TEI', result)
        self.assertIn('xmlns:tei="http://www.tei-c.org/ns/1.0"', result)
        self.assertIn('xmlns:j="http://jewishliturgy.org/ns/jlptei/2"', result)
        self.assertIn('xml:lang="en"', result)
        
        # Should contain header
        self.assertIn(test_header, result)
        
        # Should contain tei:text element
        self.assertIn('<tei:text>', result)
        self.assertIn('</tei:text>', result)
        
        # Should close TEI element
        self.assertIn('</tei:TEI>', result)
        
        # Validate XML structure
        is_valid, errors = validate(result)
        self.assertTrue(is_valid, f"TEI file XML is invalid: {errors}")
    
    def test_tei_file_with_all_sections(self):
        """Test TEI file with all sections populated."""
        test_header = """<tei:teiHeader>
            <tei:fileDesc>
                <tei:titleStmt>
                    <tei:title>Test Title</tei:title>
                </tei:titleStmt>
                <tei:publicationStmt>
                    <tei:distributor>Test Distributor</tei:distributor>
                </tei:publicationStmt>
                <tei:sourceDesc>
                    <tei:p>Test source</tei:p>
                </tei:sourceDesc>
            </tei:fileDesc>
        </tei:teiHeader>"""
        
        front_content = """<tei:front>
            <tei:div>
                <tei:p>Front matter content</tei:p>
            </tei:div>
        </tei:front>"""
        
        body_content = """<tei:body>
            <tei:div>
                <tei:p>Main body content</tei:p>
            </tei:div>
        </tei:body>"""
        
        back_content = """<tei:back>
            <tei:div>
                <tei:p>Back matter content</tei:p>
            </tei:div>
        </tei:back>"""
        
        standoff_content = """<tei:standOff>
            <tei:note xml:id="note1">A note</tei:note>
        </tei:standOff>"""
        
        result = tei_file(
            header=test_header,
            front=front_content,
            body=body_content,
            back=back_content,
            standOff=standoff_content
        )
        
        # Should contain all sections
        self.assertIn(test_header, result)
        self.assertIn(front_content, result)
        self.assertIn(body_content, result)
        self.assertIn(back_content, result)
        self.assertIn(standoff_content, result)
        
        # Validate XML structure
        is_valid, errors = validate(result)
        self.assertTrue(is_valid, f"TEI file XML is invalid: {errors}")
    
    def test_tei_file_with_custom_language(self):
        """Test TEI file with custom default language."""
        test_header = """<tei:teiHeader>
            <tei:fileDesc>
                <tei:titleStmt>
                    <tei:title>Test Title</tei:title>
                </tei:titleStmt>
                <tei:publicationStmt>
                    <tei:distributor>Test Distributor</tei:distributor>
                </tei:publicationStmt>
                <tei:sourceDesc>
                    <tei:p>Test source</tei:p>
                </tei:sourceDesc>
            </tei:fileDesc>
        </tei:teiHeader>"""
        
        body_content = """<tei:body>
            <tei:p>Test body</tei:p>
        </tei:body>"""
        
        result = tei_file(header=test_header, body=body_content, default_lang="he")
        
        # Should have Hebrew as default language
        self.assertIn('xml:lang="he"', result)
        self.assertNotIn('xml:lang="en"', result)
        
        # Validate XML structure
        is_valid, errors = validate(result)
        self.assertTrue(is_valid, f"TEI file XML is invalid: {errors}")
    
    def test_tei_file_with_body_only(self):
        """Test TEI file with only body content (no front/back)."""
        test_header = """<tei:teiHeader>
            <tei:fileDesc>
                <tei:titleStmt>
                    <tei:title>Test Title</tei:title>
                </tei:titleStmt>
                <tei:publicationStmt>
                    <tei:distributor>Test Distributor</tei:distributor>
                </tei:publicationStmt>
                <tei:sourceDesc>
                    <tei:p>Test source</tei:p>
                </tei:sourceDesc>
            </tei:fileDesc>
        </tei:teiHeader>"""
        
        body_content = """<tei:body>
            <tei:div>
                <tei:p>Main content only</tei:p>
            </tei:div>
        </tei:body>"""
        
        result = tei_file(header=test_header, body=body_content)
        
        # Should contain body
        self.assertIn(body_content, result)
        
        # Should have empty front and back (just whitespace/newlines)
        self.assertIn('<tei:text>', result)
        
        # Validate XML structure
        is_valid, errors = validate(result)
        self.assertTrue(is_valid, f"TEI file XML is invalid: {errors}")
    
    def test_tei_file_standoff_outside_text(self):
        """Test that standOff content is placed outside tei:text element."""
        test_header = """<tei:teiHeader>
            <tei:fileDesc>
                <tei:titleStmt>
                    <tei:title>Test Title</tei:title>
                </tei:titleStmt>
                <tei:publicationStmt>
                    <tei:distributor>Test Distributor</tei:distributor>
                </tei:publicationStmt>
                <tei:sourceDesc>
                    <tei:p>Test source</tei:p>
                </tei:sourceDesc>
            </tei:fileDesc>
        </tei:teiHeader>"""
        
        body_content = """<tei:body>
            <tei:div>
                <tei:p>Body content</tei:p>
            </tei:div>
        </tei:body>"""
        
        standoff_content = """<tei:standOff>
            <tei:note xml:id="note1">A standoff note</tei:note>
        </tei:standOff>"""
        
        result = tei_file(
            header=test_header,
            body=body_content,
            standOff=standoff_content
        )
        
        # Find positions in the result
        text_close_pos = result.find('</tei:text>')
        standoff_pos = result.find('<tei:standOff>')
        tei_close_pos = result.find('</tei:TEI>')
        
        # Verify structure: header < text (with body) < /text < standOff < /TEI
        self.assertGreater(text_close_pos, 0, "Should have </tei:text>")
        self.assertGreater(standoff_pos, 0, "Should have <tei:standOff>")
        self.assertGreater(tei_close_pos, 0, "Should have </tei:TEI>")
        
        # standOff should come after </tei:text> but before </tei:TEI>
        self.assertGreater(standoff_pos, text_close_pos, "standOff should come after </tei:text>")
        self.assertGreater(tei_close_pos, standoff_pos, "</tei:TEI> should come after standOff")
        
        # Validate XML structure
        is_valid, errors = validate(result)
        self.assertTrue(is_valid, f"TEI file XML is invalid: {errors}")
    
    def test_tei_file_preserves_whitespace(self):
        """Test that tei_file preserves content formatting."""
        test_header = """<tei:teiHeader>
            <tei:fileDesc>
                <tei:titleStmt>
                    <tei:title>Test Title</tei:title>
                </tei:titleStmt>
                <tei:publicationStmt>
                    <tei:distributor>Test Distributor</tei:distributor>
                </tei:publicationStmt>
                <tei:sourceDesc>
                    <tei:p>Test source</tei:p>
                </tei:sourceDesc>
            </tei:fileDesc>
        </tei:teiHeader>"""
        
        body_with_formatting = """<tei:body>
            <tei:div>
                <tei:p>Line 1</tei:p>
                <tei:p>Line 2</tei:p>
            </tei:div>
        </tei:body>"""
        
        result = tei_file(header=test_header, body=body_with_formatting)
        
        # Should preserve the formatting
        self.assertIn(body_with_formatting, result)
        
        # Validate XML structure
        is_valid, errors = validate(result)
        self.assertTrue(is_valid, f"TEI file XML is invalid: {errors}")
    
    def test_tei_file_empty_strings_vs_default(self):
        """Test behavior with empty strings vs default parameters."""
        test_header = """<tei:teiHeader>
            <tei:fileDesc>
                <tei:titleStmt>
                    <tei:title>Test Title</tei:title>
                </tei:titleStmt>
                <tei:publicationStmt>
                    <tei:distributor>Test Distributor</tei:distributor>
                </tei:publicationStmt>
                <tei:sourceDesc>
                    <tei:p>Test source</tei:p>
                </tei:sourceDesc>
            </tei:fileDesc>
        </tei:teiHeader>"""
        
        body_content = """<tei:body>
            <tei:p>Test body</tei:p>
        </tei:body>"""
        
        # With explicit empty strings (but body is required)
        result1 = tei_file(header=test_header, body=body_content, front="", back="", standOff="")
        
        # With defaults and body (should be equivalent)
        result2 = tei_file(header=test_header, body=body_content)
        
        # Both should be valid
        is_valid1, errors1 = validate(result1)
        is_valid2, errors2 = validate(result2)
        
        self.assertTrue(is_valid1, f"TEI file with explicit empty strings is invalid: {errors1}")
        self.assertTrue(is_valid2, f"TEI file with defaults is invalid: {errors2}")
        
        # Should have similar structure (may differ in whitespace)
        self.assertIn('<tei:TEI', result1)
        self.assertIn('<tei:TEI', result2)
        self.assertIn('<tei:text>', result1)
        self.assertIn('<tei:text>', result2)


class TestProcessMediawiki(unittest.TestCase):
    """Tests for process_mediawiki function."""
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.mediawiki_xml_to_tei')
    @patch('opensiddur.importer.jps1917.convert_wikisource.create_processor')
    @patch('opensiddur.importer.jps1917.convert_wikisource.get_page')
    def test_process_mediawiki_single_page(self, mock_get_page, mock_create_processor, mock_mediawiki_xml_to_tei):
        """Test processing a single page."""
        # Setup mocks
        mock_page = MagicMock()
        mock_page.content = "Test page content"
        mock_get_page.return_value = mock_page
        
        mock_processor = MagicMock()
        mock_processor.process_wikitext.return_value.xml_content = "<processed>Test page content</processed>"
        mock_create_processor.return_value = mock_processor
        
        mock_mediawiki_xml_to_tei.return_value = {
            "front": "<tei:front>Front content</tei:front>",
            "body": "<tei:body>Body content</tei:body>",
            "standOff": "<tei:standOff>Standoff content</tei:standOff>"
        }
        
        # Call function
        result = process_mediawiki(1, 1, "body", book_name="test_book")
        
        # Verify get_page was called with correct page number
        mock_get_page.assert_called_once_with(1, None)
        
        # Verify processor was created and used
        mock_create_processor.assert_called_once()
        mock_processor.process_wikitext.assert_called_once_with("Test page content")
        
        # Verify mediawiki_xml_to_tei was called with correct parameters
        mock_mediawiki_xml_to_tei.assert_called_once()
        call_args = mock_mediawiki_xml_to_tei.call_args
        
        # Check the XML content passed to mediawiki_xml_to_tei
        xml_content = call_args[0][0]
        self.assertIn('<tei:body', xml_content)
        self.assertIn('xmlns:tei="http://www.tei-c.org/ns/1.0"', xml_content)
        self.assertIn('xmlns:j="http://jewishliturgy.org/ns/jlptei/2"', xml_content)
        self.assertIn('<mediawikis>', xml_content)
        self.assertIn('<processed>Test page content</processed>', xml_content)
        
        # Check kwargs passed to mediawiki_xml_to_tei
        xslt_params = call_args[1]['xslt_params']
        self.assertEqual(xslt_params['book_name'], "test_book")
        
        # Verify return value
        self.assertEqual(result, {
            "front": "<tei:front>Front content</tei:front>",
            "body": "<tei:body>Body content</tei:body>",
            "standOff": "<tei:standOff>Standoff content</tei:standOff>"
        })
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.mediawiki_xml_to_tei')
    @patch('opensiddur.importer.jps1917.convert_wikisource.create_processor')
    @patch('opensiddur.importer.jps1917.convert_wikisource.get_page')
    def test_process_mediawiki_records_each_scan_page(self, mock_get_page, mock_create_processor,
                                                      mock_mediawiki_xml_to_tei):
        """Each page is marked with its number in the scan, for its page break's link."""
        mock_get_page.return_value = MagicMock(content="text")
        mock_create_processor.return_value.process_wikitext.side_effect = [
            MagicMock(xml_content="<mediawiki>one</mediawiki>"),
            MagicMock(xml_content="<mediawiki>two</mediawiki>"),
        ]
        mock_mediawiki_xml_to_tei.return_value = {"front": "", "body": "", "standOff": ""}

        process_mediawiki(25, 26, "body")

        call_args = mock_mediawiki_xml_to_tei.call_args
        self.assertIn('<mediawiki scan="25">one</mediawiki>', call_args[0][0])
        self.assertIn('<mediawiki scan="26">two</mediawiki>', call_args[0][0])
        self.assertEqual("https://en.wikisource.org/wiki/Page:JPS-1917-Universal.djvu/",
                         call_args[1]["xslt_params"]["facs_prefix"])

    @patch('opensiddur.importer.jps1917.convert_wikisource.mediawiki_xml_to_tei')
    @patch('opensiddur.importer.jps1917.convert_wikisource.create_processor')
    @patch('opensiddur.importer.jps1917.convert_wikisource.get_page')
    def test_process_mediawiki_multiple_pages(self, mock_get_page, mock_create_processor, mock_mediawiki_xml_to_tei):
        """Test processing multiple pages."""
        # Setup mocks for multiple pages
        mock_page1 = MagicMock()
        mock_page1.content = "Page 1 content"
        mock_page2 = MagicMock()
        mock_page2.content = "Page 2 content"
        mock_page3 = MagicMock()
        mock_page3.content = "Page 3 content"
        mock_get_page.side_effect = [mock_page1, mock_page2, mock_page3]
        
        mock_processor = MagicMock()
        mock_processor.process_wikitext.side_effect = [
            MagicMock(xml_content="<processed>Page 1 content</processed>"),
            MagicMock(xml_content="<processed>Page 2 content</processed>"),
            MagicMock(xml_content="<processed>Page 3 content</processed>")
        ]
        mock_create_processor.return_value = mock_processor
        
        mock_mediawiki_xml_to_tei.return_value = {
            "front": "",
            "body": "<tei:body>Combined content</tei:body>",
            "standOff": ""
        }
        
        # Call function
        result = process_mediawiki(1, 3, "body")
        
        # Verify get_page was called for each page
        self.assertEqual(mock_get_page.call_count, 3)
        mock_get_page.assert_any_call(1, None)
        mock_get_page.assert_any_call(2, None)
        mock_get_page.assert_any_call(3, None)
        
        # Verify processor was used for each page
        self.assertEqual(mock_processor.process_wikitext.call_count, 3)
        
        # Check the combined XML content
        call_args = mock_mediawiki_xml_to_tei.call_args
        xml_content = call_args[0][0]
        self.assertIn('<processed>Page 1 content</processed>', xml_content)
        self.assertIn('<processed>Page 2 content</processed>', xml_content)
        self.assertIn('<processed>Page 3 content</processed>', xml_content)
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.mediawiki_xml_to_tei')
    @patch('opensiddur.importer.jps1917.convert_wikisource.create_processor')
    @patch('opensiddur.importer.jps1917.convert_wikisource.get_page')
    def test_process_mediawiki_with_front_wrapper(self, mock_get_page, mock_create_processor, mock_mediawiki_xml_to_tei):
        """Test processing with front wrapper element."""
        # Setup mocks
        mock_page = MagicMock()
        mock_page.content = "Front content"
        mock_get_page.return_value = mock_page
        
        mock_processor = MagicMock()
        mock_processor.process_wikitext.return_value.xml_content = "<processed>Front content</processed>"
        mock_create_processor.return_value = mock_processor
        
        mock_mediawiki_xml_to_tei.return_value = {
            "front": "<tei:front>Front result</tei:front>",
            "body": "",
            "standOff": ""
        }
        
        # Call function with front wrapper
        result = process_mediawiki(1, 1, "front", wrapper_div_type="preface")
        
        # Check the XML content passed to mediawiki_xml_to_tei
        call_args = mock_mediawiki_xml_to_tei.call_args
        xml_content = call_args[0][0]
        self.assertIn('<tei:front', xml_content)
        self.assertNotIn('<tei:body', xml_content)
        
        # Check kwargs
        xslt_params = call_args[1]['xslt_params']
        self.assertEqual(xslt_params['wrapper_div_type'], "preface")
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.mediawiki_xml_to_tei')
    @patch('opensiddur.importer.jps1917.convert_wikisource.create_processor')
    @patch('opensiddur.importer.jps1917.convert_wikisource.get_page')
    def test_process_mediawiki_with_kwargs(self, mock_get_page, mock_create_processor, mock_mediawiki_xml_to_tei):
        """Test processing with additional keyword arguments."""
        # Setup mocks
        mock_page = MagicMock()
        mock_page.content = "Test content"
        mock_get_page.return_value = mock_page
        
        mock_processor = MagicMock()
        mock_processor.process_wikitext.return_value.xml_content = "<processed>Test content</processed>"
        mock_create_processor.return_value = mock_processor
        
        mock_mediawiki_xml_to_tei.return_value = {
            "front": "",
            "body": "<tei:body>Result</tei:body>",
            "standOff": ""
        }
        
        # Call function with various kwargs
        result = process_mediawiki(
            1, 1, "body",
            book_name="genesis",
            is_section=True,
            custom_param="custom_value"
        )
        
        # Check that kwargs are passed to mediawiki_xml_to_tei
        call_args = mock_mediawiki_xml_to_tei.call_args
        xslt_params = call_args[1]['xslt_params']
        self.assertEqual(xslt_params['book_name'], "genesis")
        self.assertEqual(xslt_params['is_section'], True)
        self.assertEqual(xslt_params['custom_param'], "custom_value")
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.mediawiki_xml_to_tei')
    @patch('opensiddur.importer.jps1917.convert_wikisource.create_processor')
    @patch('opensiddur.importer.jps1917.convert_wikisource.get_page')
    def test_process_mediawiki_content_concatenation(self, mock_get_page, mock_create_processor, mock_mediawiki_xml_to_tei):
        """Test that content from multiple pages is properly concatenated."""
        # Setup mocks
        mock_page1 = MagicMock()
        mock_page1.content = "First page"
        mock_page2 = MagicMock()
        mock_page2.content = "Second page"
        mock_get_page.side_effect = [mock_page1, mock_page2]
        
        mock_processor = MagicMock()
        mock_processor.process_wikitext.side_effect = [
            MagicMock(xml_content="<p>First page</p>"),
            MagicMock(xml_content="<p>Second page</p>")
        ]
        mock_create_processor.return_value = mock_processor
        
        mock_mediawiki_xml_to_tei.return_value = {
            "front": "",
            "body": "<tei:body>Combined</tei:body>",
            "standOff": ""
        }
        
        # Call function
        process_mediawiki(1, 2, "body")
        
        # Check the XML content - should have both pages concatenated with spaces
        call_args = mock_mediawiki_xml_to_tei.call_args
        xml_content = call_args[0][0]
        
        # Should contain both processed pages
        self.assertIn('<p>First page</p>', xml_content)
        self.assertIn('<p>Second page</p>', xml_content)
        
        # Should be concatenated with spaces (as per the function logic)
        # The function does: content += " " + mw_processor.process_wikitext(page_content).xml_content
        # So first page has no leading space, subsequent pages have leading space
        self.assertIn('<p>First page</p> <p>Second page</p>', xml_content)
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.mediawiki_xml_to_tei')
    @patch('opensiddur.importer.jps1917.convert_wikisource.create_processor')
    @patch('opensiddur.importer.jps1917.convert_wikisource.get_page')
    def test_process_mediawiki_processing_flow(self, mock_get_page, mock_create_processor, mock_mediawiki_xml_to_tei):
        """Test the complete processing flow for multiple pages."""
        # Setup mocks
        mock_page = MagicMock()
        mock_page.content = "Test content"
        mock_get_page.return_value = mock_page
        
        mock_processor = MagicMock()
        mock_processor.process_wikitext.return_value.xml_content = "<processed>Test content</processed>"
        mock_create_processor.return_value = mock_processor
        
        mock_mediawiki_xml_to_tei.return_value = {
            "front": "",
            "body": "<tei:body>Result</tei:body>",
            "standOff": ""
        }
        
        # Call function
        result = process_mediawiki(1, 3, "body")
        
        # Verify all pages were processed
        self.assertEqual(mock_get_page.call_count, 3)
        self.assertEqual(mock_processor.process_wikitext.call_count, 3)
        mock_mediawiki_xml_to_tei.assert_called_once()
        
        # Verify return value
        self.assertEqual(result, {
            "front": "",
            "body": "<tei:body>Result</tei:body>",
            "standOff": ""
        })


class TestValidateAndWriteTeiFile(unittest.TestCase):
    """Tests for validate_and_write_tei_file function."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.original_project_dir = None
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Restore original PROJECT_DIRECTORY if it was patched
        if self.original_project_dir is not None:
            import opensiddur.importer.jps1917.convert_wikisource as convert_module
            convert_module.PROJECT_DIRECTORY = self.original_project_dir
        
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _patch_project_directory(self):
        """Patch PROJECT_DIRECTORY to use temp directory."""
        import opensiddur.importer.jps1917.convert_wikisource as convert_module
        self.original_project_dir = convert_module.PROJECT_DIRECTORY
        convert_module.PROJECT_DIRECTORY = Path(self.temp_dir)
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.validate')
    @patch('opensiddur.importer.jps1917.convert_wikisource.prettify_xml')
    @patch('builtins.open', new_callable=mock_open)
    def test_validate_and_write_tei_file_valid_xml(self, mock_file, mock_prettify, mock_validate):
        """Test writing valid TEI XML file."""
        # Setup mocks
        mock_prettify.return_value = "<tei:TEI>Pretty XML</tei:TEI>"
        mock_validate.return_value = (True, [])
        
        # Call function
        validate_and_write_tei_file("<tei:TEI>Raw XML</tei:TEI>", "test_file")
        
        # Verify prettify_xml was called with correct parameters
        mock_prettify.assert_called_once_with("<tei:TEI>Raw XML</tei:TEI>", remove_xml_declaration=True)
        
        # Verify validate was called with prettified XML
        mock_validate.assert_called_once_with("<tei:TEI>Pretty XML</tei:TEI>")
        
        # Verify file was opened and written
        mock_file.assert_called_once()
        mock_file().write.assert_called_once_with("<tei:TEI>Pretty XML</tei:TEI>")
        
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.validate')
    @patch('opensiddur.importer.jps1917.convert_wikisource.prettify_xml')
    @patch('builtins.open', new_callable=mock_open)
    def test_validate_and_write_tei_file_invalid_xml(self, mock_file, mock_prettify, mock_validate):
        """Test handling of invalid TEI XML file."""
        # Setup mocks
        mock_prettify.return_value = "<tei:TEI>Pretty but invalid XML</tei:TEI>"
        mock_validate.return_value = (False, ["Error: Invalid element", "Error: Missing required attribute"])
        
        # Call function and expect exception
        with self.assertRaises(Exception) as context:
            validate_and_write_tei_file("<tei:TEI>Raw XML</tei:TEI>", "test_file")
        
        # Verify exception message
        self.assertIn("Errors in test_file", str(context.exception))
        self.assertIn("Invalid element", str(context.exception))
        self.assertIn("Missing required attribute", str(context.exception))
        
        # Verify prettify and validate were called
        mock_prettify.assert_called_once()
        mock_validate.assert_called_once()
        
        # Verify file was never opened (due to validation failure)
        mock_file.assert_not_called()
        
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.validate')
    @patch('opensiddur.importer.jps1917.convert_wikisource.prettify_xml')
    @patch('builtins.open', new_callable=mock_open)
    def test_validate_and_write_tei_file_xml_syntax_error(self, mock_file, mock_prettify, mock_validate):
        """Test handling of XML syntax errors during prettification."""
        # Setup mocks - prettify_xml raises an exception for malformed XML
        from lxml.etree import XMLSyntaxError
        mock_prettify.side_effect = XMLSyntaxError("Invalid XML syntax", 1, 5, 10)
        
        # Call function and expect exception
        with self.assertRaises(XMLSyntaxError):
            validate_and_write_tei_file("<tei:TEI>Malformed XML", "test_file")
        
        # Verify prettify_xml was called
        mock_prettify.assert_called_once()
        
        # Verify validate was not called (prettification failed first)
        mock_validate.assert_not_called()
        
        # Verify file was never opened (prettification failed first)
        mock_file.assert_not_called()
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.validate')
    @patch('opensiddur.importer.jps1917.convert_wikisource.prettify_xml')
    @patch('builtins.open', new_callable=mock_open)
    def test_validate_and_write_tei_file_file_write_error(self, mock_file, mock_prettify, mock_validate):
        """Test handling of file write errors."""
        # Setup mocks
        mock_prettify.return_value = "<tei:TEI>Pretty XML</tei:TEI>"
        mock_validate.return_value = (True, [])
        mock_file.side_effect = IOError("Permission denied")
        
        # Call function and expect exception
        with self.assertRaises(IOError) as context:
            validate_and_write_tei_file("<tei:TEI>Raw XML</tei:TEI>", "test_file")
        
        # Verify exception message
        self.assertIn("Permission denied", str(context.exception))
        
        # Verify prettify and validate were called
        mock_prettify.assert_called_once()
        mock_validate.assert_called_once()
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.validate')
    @patch('opensiddur.importer.jps1917.convert_wikisource.prettify_xml')
    @patch('builtins.open', new_callable=mock_open)
    def test_validate_and_write_tei_file_correct_file_path(self, mock_file, mock_prettify, mock_validate):
        """Test that the correct file path is used."""
        # Patch PROJECT_DIRECTORY
        self._patch_project_directory()
        
        # Setup mocks
        mock_prettify.return_value = "<tei:TEI>Pretty XML</tei:TEI>"
        mock_validate.return_value = (True, [])
        
        # Call function
        validate_and_write_tei_file("<tei:TEI>Raw XML</tei:TEI>", "my_book")
        
        # Verify file was opened with correct path
        expected_path = Path(self.temp_dir) / JPS_PROJECT / "my_book.xml"
        mock_file.assert_called_once_with(expected_path, "w", encoding="utf-8")
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.validate')
    @patch('opensiddur.importer.jps1917.convert_wikisource.prettify_xml')
    @patch('builtins.open', new_callable=mock_open)
    def test_validate_and_write_tei_file_validation_error_details(self, mock_file, mock_prettify, mock_validate):
        """Test that validation error details are properly included in exception."""
        # Setup mocks
        mock_prettify.return_value = "<tei:TEI>Pretty XML</tei:TEI>"
        validation_errors = [
            "XML:5:12: error: element 'tei:div' incomplete; missing required element 'tei:p'",
            "XML:8:3: error: element 'tei:title' not allowed here; expected the element end-tag or text"
        ]
        mock_validate.return_value = (False, validation_errors)
        
        # Call function and expect exception
        with self.assertRaises(Exception) as context:
            validate_and_write_tei_file("<tei:TEI>Raw XML</tei:TEI>", "test_file")
        
        # Verify all validation errors are included in exception message
        exception_message = str(context.exception)
        self.assertIn("Errors in test_file", exception_message)
        for error in validation_errors:
            self.assertIn(error, exception_message)
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.validate')
    @patch('opensiddur.importer.jps1917.convert_wikisource.prettify_xml')
    @patch('builtins.open', new_callable=mock_open)
    def test_validate_and_write_tei_file_empty_errors_list(self, mock_file, mock_prettify, mock_validate):
        """Test handling when validation fails but returns empty errors list."""
        # Setup mocks
        mock_prettify.return_value = "<tei:TEI>Pretty XML</tei:TEI>"
        mock_validate.return_value = (False, [])  # Invalid but no specific errors
        
        # Call function and expect exception
        with self.assertRaises(Exception) as context:
            validate_and_write_tei_file("<tei:TEI>Raw XML</tei:TEI>", "test_file")
        
        # Verify exception message includes file name even with empty errors
        self.assertIn("Errors in test_file", str(context.exception))
        self.assertIn("[]", str(context.exception))  # Empty list should be shown
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.validate')
    @patch('opensiddur.importer.jps1917.convert_wikisource.prettify_xml')
    @patch('builtins.open', new_callable=mock_open)
    def test_validate_and_write_tei_file_unicode_content(self, mock_file, mock_prettify, mock_validate):
        """Test handling of Unicode content in TEI file."""
        # Setup mocks
        unicode_content = "<tei:TEI>בראשית ברא אלהים</tei:TEI>"
        mock_prettify.return_value = unicode_content
        mock_validate.return_value = (True, [])
        
        # Call function
        validate_and_write_tei_file(unicode_content, "unicode_test")
        
        # Verify prettify_xml was called with Unicode content
        mock_prettify.assert_called_once_with(unicode_content, remove_xml_declaration=True)
        
        # Verify validate was called with Unicode content
        mock_validate.assert_called_once_with(unicode_content)
        
        # Verify file was written with Unicode content
        mock_file().write.assert_called_once_with(unicode_content)
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.validate')
    @patch('opensiddur.importer.jps1917.convert_wikisource.prettify_xml')
    @patch('builtins.open', new_callable=mock_open)
    def test_validate_and_write_tei_file_large_content(self, mock_file, mock_prettify, mock_validate):
        """Test handling of large TEI content."""
        # Setup mocks
        large_content = "<tei:TEI>" + "x" * 10000 + "</tei:TEI>"
        mock_prettify.return_value = large_content
        mock_validate.return_value = (True, [])
        
        # Call function
        validate_and_write_tei_file(large_content, "large_file")
        
        # Verify all operations completed successfully
        mock_prettify.assert_called_once()
        mock_validate.assert_called_once()
        mock_file().write.assert_called_once_with(large_content)


class TestBookFile(unittest.TestCase):
    """Tests for book_file function."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_book = Book(
            book_name_he="בראשית",
            book_name_en="Genesis",
            file_name="genesis",
            start_page=1,
            end_page=5,
            is_section=False
        )
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.validate_and_write_tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.process_mediawiki')
    @patch('opensiddur.importer.jps1917.convert_wikisource.header')
    @patch('opensiddur.importer.jps1917.convert_wikisource.get_credits_pages')
    @patch('builtins.open', new_callable=mock_open)
    def test_book_file_basic_flow(self, mock_file, mock_get_credits, mock_header, 
                                  mock_process_mediawiki, mock_tei_file, mock_validate_write):
        """Test basic book_file flow."""
        # Setup mocks
        mock_get_credits.return_value = ["Credit1", "Credit2"]
        mock_header.return_value = "<tei:teiHeader>Header content</tei:teiHeader>"
        mock_process_mediawiki.return_value = {
            "front": "",
            "body": "<tei:body>Body content</tei:body>",
            "standOff": ""
        }
        mock_tei_file.return_value = "<tei:TEI>Complete TEI content</tei:TEI>"
        
        # Call function
        result = book_file(self.test_book)
        
        # Verify get_credits_pages was called with correct page range
        mock_get_credits.assert_called_once_with(1, 5, None)
        
        # Verify header was called with correct parameters
        mock_header.assert_called_once_with(
            book_name_he="בראשית",
            book_name_en="Genesis",
            entrypoint="genesis",
            transcription_credits=["Credit1", "Credit2"],
            # Read from the manifest of whatever tree is being converted, so the value
            # is not this test's business; TestHeaderDownloadDate covers it directly.
            source_download_date=ANY,
        )
        
        # Verify process_mediawiki was called with correct parameters
        mock_process_mediawiki.assert_called_once_with(
            1, 5, "body",
            sourcetexts_root=None,
            wrapper_div_type="book",
            book_name="genesis",
            is_section=False,
            parsha_names=ANY,
            first_parsha="",
        )
        
        # Verify tei_file was called with correct parameters
        mock_tei_file.assert_called_once_with(
            header="<tei:teiHeader>Header content</tei:teiHeader>",
            front="",
            body="<tei:body>Body content</tei:body>",
            standOff=""
        )
        
        
        # Verify validate_and_write_tei_file was called
        mock_validate_write.assert_called_once_with("<tei:TEI>Complete TEI content</tei:TEI>", "genesis", None)
        
        # Verify return value
        self.assertEqual(result, "<tei:TEI>Complete TEI content</tei:TEI>")
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.validate_and_write_tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.process_mediawiki')
    @patch('opensiddur.importer.jps1917.convert_wikisource.header')
    @patch('opensiddur.importer.jps1917.convert_wikisource.get_credits_pages')
    @patch('builtins.open', new_callable=mock_open)
    def test_book_file_with_section(self, mock_file, mock_get_credits, mock_header,
                                    mock_process_mediawiki, mock_tei_file, mock_validate_write):
        """Test book_file with is_section=True."""
        # Setup book with is_section=True
        section_book = Book(
            book_name_he="פרק א",
            book_name_en="Chapter 1",
            file_name="genesis_ch1",
            start_page=10,
            end_page=15,
            is_section=True
        )
        
        # Setup mocks
        mock_get_credits.return_value = []
        mock_header.return_value = "<tei:teiHeader>Section header</tei:teiHeader>"
        mock_process_mediawiki.return_value = {
            "front": "",
            "body": "<tei:body>Section body</tei:body>",
            "standOff": ""
        }
        mock_tei_file.return_value = "<tei:TEI>Section TEI</tei:TEI>"
        
        # Call function
        result = book_file(section_book)
        
        # Verify process_mediawiki was called with is_section=True
        mock_process_mediawiki.assert_called_once_with(
            10, 15, "body",
            sourcetexts_root=None,
            wrapper_div_type="book",
            book_name="genesis_ch1",
            is_section=True,
            parsha_names=ANY,
            first_parsha="",
        )
        
        # Verify return value
        self.assertEqual(result, "<tei:TEI>Section TEI</tei:TEI>")
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.validate_and_write_tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.process_mediawiki')
    @patch('opensiddur.importer.jps1917.convert_wikisource.header')
    @patch('opensiddur.importer.jps1917.convert_wikisource.get_credits_pages')
    @patch('builtins.open', new_callable=mock_open)
    def test_book_file_with_all_sections(self, mock_file, mock_get_credits, mock_header,
                                         mock_process_mediawiki, mock_tei_file, mock_validate_write):
        """Test book_file with all sections populated."""
        # Setup mocks
        mock_get_credits.return_value = ["Transcriber1", "Transcriber2"]
        mock_header.return_value = "<tei:teiHeader>Full header</tei:teiHeader>"
        mock_process_mediawiki.return_value = {
            "front": "<tei:front>Front matter</tei:front>",
            "body": "<tei:body>Main body</tei:body>",
            "standOff": "<tei:standOff>Standoff notes</tei:standOff>"
        }
        mock_tei_file.return_value = "<tei:TEI>Complete TEI with all sections</tei:TEI>"
        
        # Call function
        result = book_file(self.test_book)
        
        # Verify tei_file was called with all sections
        mock_tei_file.assert_called_once_with(
            header="<tei:teiHeader>Full header</tei:teiHeader>",
            front="<tei:front>Front matter</tei:front>",
            body="<tei:body>Main body</tei:body>",
            standOff="<tei:standOff>Standoff notes</tei:standOff>"
        )
        
        # Verify return value
        self.assertEqual(result, "<tei:TEI>Complete TEI with all sections</tei:TEI>")


class TestIndexFile(unittest.TestCase):
    """Tests for index_file function."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_book1 = Book(
            book_name_he="בראשית",
            book_name_en="Genesis",
            file_name="genesis",
            start_page=1,
            end_page=5,
            is_section=False
        )
        self.test_book2 = Book(
            book_name_he="שמות",
            book_name_en="Exodus",
            file_name="exodus",
            start_page=6,
            end_page=10,
            is_section=False
        )
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.book_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.index_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.validate_and_write_tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.process_mediawiki')
    @patch('opensiddur.importer.jps1917.convert_wikisource.header')
    @patch('opensiddur.importer.jps1917.convert_wikisource.get_credits_pages')
    @patch('builtins.open', new_callable=mock_open)
    def test_index_file_with_pages_and_transclusions(self, mock_file, mock_get_credits, mock_header,
                                                     mock_process_mediawiki, mock_tei_file, mock_validate_write, 
                                                     mock_index_file, mock_book_file):
        """Test index_file with pages and transclusions."""
        # Setup index
        test_index = Index(
            index_title_en="The Torah",
            index_title_he="תורה",
            index_sub_he="חמישה חומשי תורה",
            index_sub_en="Five Books of Moses",
            file_name="torah",
            transclusions=[self.test_book1, self.test_book2],
            start_page=1,
            end_page=3
        )
        
        # Setup mocks
        mock_get_credits.return_value = ["Index transcriber"]
        mock_header.return_value = "<tei:teiHeader>Index header</tei:teiHeader>"
        mock_process_mediawiki.return_value = {
            "front": "<tei:front>Index front</tei:front>",
            "body": "",
            "standOff": ""
        }
        mock_tei_file.return_value = "<tei:TEI>Complete index TEI</tei:TEI>"
        
        # Call function
        result = index_file(test_index)
        
        # Verify get_credits_pages was called for the index
        mock_get_credits.assert_any_call(1, 3, None)
        
        # Verify header was called with correct parameters for the index
        mock_header.assert_any_call(
            book_name_he="תורה",
            book_name_en="The Torah",
            book_sub_he="חמישה חומשי תורה",
            book_sub_en="Five Books of Moses",
            entrypoint="torah",
            transcription_credits=["Index transcriber"],
            source_download_date=ANY,
        )
        
        # Verify process_mediawiki was called for front matter
        mock_process_mediawiki.assert_called_once_with(
            1, 3, "front",
            sourcetexts_root=None,
            wrapper_div_type="",
            book_name="",
            parsha_names=ANY,
        )
        
        # Verify tei_file was called with correct body containing transclusions
        # Find the call for the index (not the recursive calls for books)
        index_calls = [call for call in mock_tei_file.call_args_list 
                      if call[1]['header'] == "<tei:teiHeader>Index header</tei:teiHeader>"]
        self.assertEqual(len(index_calls), 1)
        call_args = index_calls[0]
        self.assertEqual(call_args[1]['header'], "<tei:teiHeader>Index header</tei:teiHeader>")
        self.assertEqual(call_args[1]['front'], "<tei:front>Index front</tei:front>")
        self.assertEqual(call_args[1]['standOff'], "")
        
        # Check that body contains transclusions
        body_content = call_args[1]['body']
        self.assertIn('<tei:head>The Torah</tei:head>', body_content)
        self.assertIn('<j:transclude target="urn:x-opensiddur:text:bible:genesis"/>', body_content)
        self.assertIn('<j:transclude target="urn:x-opensiddur:text:bible:exodus"/>', body_content)
        
        # Verify validate_and_write_tei_file was called for the index
        mock_validate_write.assert_any_call("<tei:TEI>Complete index TEI</tei:TEI>", "torah", None)
        
        # Verify return value
        self.assertEqual(result, "<tei:TEI>Complete index TEI</tei:TEI>")
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.book_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.index_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.validate_and_write_tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.header')
    @patch('builtins.open', new_callable=mock_open)
    def test_index_file_without_pages(self, mock_file, mock_header, mock_tei_file, mock_validate_write, 
                                      mock_index_file, mock_book_file):
        """Test index_file without start_page and end_page."""
        # Setup index without pages
        test_index = Index(
            index_title_en="Bible Index",
            index_title_he="מפתח התנ״ך",
            file_name="bible_index",
            transclusions=[self.test_book1, self.test_book2],
            start_page=None,
            end_page=None
        )
        
        # Setup mocks
        mock_header.return_value = "<tei:teiHeader>Bible index header</tei:teiHeader>"
        mock_tei_file.return_value = "<tei:TEI>Bible index TEI</tei:TEI>"
        
        # Call function
        result = index_file(test_index)
        
        # Verify header was called with transcription_credits=None for the index
        mock_header.assert_any_call(
            book_name_he="מפתח התנ״ך",
            book_name_en="Bible Index",
            book_sub_he=None,
            book_sub_en=None,
            entrypoint="bible_index",
            transcription_credits=None,
            source_download_date=ANY,
        )
        
        # Verify tei_file was called with empty xml_dict and body with transclusions
        # Find the call for the index (not the recursive calls for books)
        index_calls = [call for call in mock_tei_file.call_args_list 
                      if call[1]['header'] == "<tei:teiHeader>Bible index header</tei:teiHeader>"]
        self.assertEqual(len(index_calls), 1)
        call_args = index_calls[0]
        self.assertEqual(call_args[1]['header'], "<tei:teiHeader>Bible index header</tei:teiHeader>")
        # Check if front and standOff are present (they might not be if xml_dict is empty)
        if 'front' in call_args[1]:
            self.assertEqual(call_args[1]['front'], "")
        if 'standOff' in call_args[1]:
            self.assertEqual(call_args[1]['standOff'], "")
        
        # Check that body contains transclusions
        body_content = call_args[1]['body']
        self.assertIn('<tei:head>Bible Index</tei:head>', body_content)
        self.assertIn('<j:transclude target="urn:x-opensiddur:text:bible:genesis"/>', body_content)
        self.assertIn('<j:transclude target="urn:x-opensiddur:text:bible:exodus"/>', body_content)
        
        # Verify return value
        self.assertEqual(result, "<tei:TEI>Bible index TEI</tei:TEI>")
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.book_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.index_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.validate_and_write_tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.header')
    @patch('opensiddur.importer.jps1917.convert_wikisource.get_credits_pages')
    @patch('builtins.open', new_callable=mock_open)
    def test_index_file_recursive_processing(self, mock_file, mock_get_credits, mock_header,
                                             mock_tei_file, mock_validate_write, mock_index_file, mock_book_file):
        """Test that index_file recursively processes its transclusions."""
        # Setup nested index structure
        nested_index = Index(
            index_title_en="Nested Index",
            file_name="nested",
            transclusions=[self.test_book1, self.test_book2],
            start_page=None,
            end_page=None
        )
        
        # Setup mocks
        mock_header.return_value = "<tei:teiHeader>Nested header</tei:teiHeader>"
        mock_tei_file.return_value = "<tei:TEI>Nested TEI</tei:TEI>"
        
        # Call function
        result = index_file(nested_index)
        
        # Verify that book_file was called for each Book transclusion
        self.assertEqual(mock_book_file.call_count, 2)
        mock_book_file.assert_any_call(self.test_book1, None, None)
        mock_book_file.assert_any_call(self.test_book2, None, None)
        
        # Verify index_file was not called recursively (no Index transclusions)
        mock_index_file.assert_not_called()
        
        # Verify return value
        self.assertEqual(result, "<tei:TEI>Nested TEI</tei:TEI>")
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.book_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.index_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.validate_and_write_tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.header')
    @patch('builtins.open', new_callable=mock_open)
    def test_index_file_with_nested_index(self, mock_file, mock_header, mock_tei_file,
                                          mock_validate_write, mock_index_file, mock_book_file):
        """Test index_file with nested Index transclusions."""
        # Setup nested index
        child_index = Index(
            index_title_en="Child Index",
            file_name="child",
            transclusions=[self.test_book1],
            start_page=None,
            end_page=None
        )
        
        parent_index = Index(
            index_title_en="Parent Index",
            file_name="parent",
            transclusions=[child_index, self.test_book2],
            start_page=None,
            end_page=None
        )
        
        # Setup mocks
        mock_header.return_value = "<tei:teiHeader>Parent header</tei:teiHeader>"
        mock_tei_file.return_value = "<tei:TEI>Parent TEI</tei:TEI>"
        
        # Call function
        result = index_file(parent_index)
        
        # Verify that book_file was called for Book transclusion
        mock_book_file.assert_called_once_with(self.test_book2, None, None)

        # Verify that index_file was called recursively for Index transclusion
        mock_index_file.assert_called_once_with(child_index, None, None)
        
        # Verify return value
        self.assertEqual(result, "<tei:TEI>Parent TEI</tei:TEI>")
    
    @patch('opensiddur.importer.jps1917.convert_wikisource.book_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.index_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.validate_and_write_tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.header')
    @patch('builtins.open', new_callable=mock_open)
    def test_index_file_transclusion_formatting(self, mock_file, mock_header, mock_tei_file, mock_validate_write,
                                                mock_index_file, mock_book_file):
        """Test that transclusions are properly formatted in the body."""
        # Setup index with multiple transclusions
        test_index = Index(
            index_title_en="Test Index",
            file_name="test",
            transclusions=[self.test_book1, self.test_book2],
            start_page=None,
            end_page=None
        )
        
        # Setup mocks
        mock_header.return_value = "<tei:teiHeader>Test header</tei:teiHeader>"
        mock_tei_file.return_value = "<tei:TEI>Test TEI</tei:TEI>"
        
        # Call function
        result = index_file(test_index)
        
        # Get the body content passed to tei_file for the index
        # Find the call for the index (not the recursive calls for books)
        index_calls = [call for call in mock_tei_file.call_args_list 
                      if call[1]['header'] == "<tei:teiHeader>Test header</tei:teiHeader>"]
        self.assertEqual(len(index_calls), 1)
        call_args = index_calls[0]
        body_content = call_args[1]['body']
        
        # Verify body structure
        self.assertIn('<tei:body>', body_content)
        self.assertIn('<tei:div corresp="urn:x-opensiddur:text:bible:test">', body_content)
        self.assertIn('<tei:head>Test Index</tei:head>', body_content)
        
        # Verify transclusions are properly formatted
        expected_transclusions = [
            '<j:transclude target="urn:x-opensiddur:text:bible:genesis"/>',
            '<j:transclude target="urn:x-opensiddur:text:bible:exodus"/>'
        ]
        for transclusion in expected_transclusions:
            self.assertIn(transclusion, body_content)
        
        # Verify transclusions are on separate lines
        self.assertIn('\n', body_content)
        lines = body_content.split('\n')
        transclusion_lines = [line.strip() for line in lines if 'j:transclude' in line]
        self.assertEqual(len(transclusion_lines), 2)
        self.assertEqual(transclusion_lines[0], expected_transclusions[0])
        self.assertEqual(transclusion_lines[1], expected_transclusions[1])


class TestMediawikiXmlToTei(unittest.TestCase):
    """Tests for mediawiki_xml_to_tei function and the underlying XSLT transformation."""
    
    def setUp(self):
        """Set up test fixtures."""
        from opensiddur.importer.jps1917.convert_wikisource import MEDIAWIKI_TO_TEI_XSLT
        from opensiddur.common.xslt import xslt_transform_string
        
        self.xslt_path = MEDIAWIKI_TO_TEI_XSLT
        # The stylesheet resolves parshah names against this table and terminates on a name it
        # does not know, so every transformation gets it unless a test overrides it.
        self.parsha_names = skeleton_map_json()
        self.transform = lambda xml, params=None: xslt_transform_string(
            self.xslt_path, xml, multiple_results=True,
            xslt_params={"parsha_names": self.parsha_names, **(params or {})},
        )

        # Simple test XML that focuses on basic functionality. Verse text is a *sibling*
        # of the verse marker, which is the shape the real intermediate XML has: the verse
        # template emits milestones only and never recurses into the element, so text
        # written inside it would silently vanish and leave the fixture textless.
        self.simple_xml = """<?xml version="1.0" encoding="UTF-8"?>
<mediawikis xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    <mediawiki>
        <noinclude><c>1</c></noinclude>
        <c><larger>Chapter 1</larger></c>
        <dropinitial>1</dropinitial>
        <verse chapter="1" verse="1"/>In the beginning God created the heaven and the earth.
        <verse chapter="1" verse="2"/>And the earth was without form, and void.
        <c><lang>ויצא</lang></c>
        <br>List item 1</br>
        <br>List item 2</br>
        <br>List item 3</br>
    </mediawiki>
    <mediawiki>
        <noinclude><c>2</c></noinclude>
        <c><larger>Chapter 2</larger></c>
        <dropinitial>2</dropinitial>
        <verse chapter="2" verse="1"/>Thus the heavens and the earth were finished.
    </mediawiki>
</mediawikis>"""
        
        # XML for testing multiple heads (Psalms-like structure)
        self.multiple_heads_xml = """<?xml version="1.0" encoding="UTF-8"?>
<mediawikis xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    <mediawiki>
        <noinclude><c>1</c></noinclude>
        <c><larger>Psalm 1</larger></c>
        <c><larger>Psalm 2</larger></c>
        <c><larger>Psalm 3</larger></c>
    </mediawiki>
</mediawikis>"""
        
        # XML for testing sectioning
        self.sectioning_xml = """<?xml version="1.0" encoding="UTF-8"?>
<mediawikis xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    <mediawiki>
        <noinclude><c>1</c></noinclude>
        <section begin="true"/>
        <c><larger>Section Title</larger></c>
        <section end="true"/>
    </mediawiki>
</mediawikis>"""
    
    def test_mediawiki_xml_to_tei_basic_transformation(self):
        """Test basic MediaWiki to TEI transformation."""
        # Test the wrapper function
        result = mediawiki_xml_to_tei(
            self.simple_xml, {"parsha_names": self.parsha_names})
        self.assertIn("front", result)
        self.assertIn("body", result)
        self.assertIn("standOff", result)
        
        # Test the XSLT transformation directly
        outputs = self.transform(self.simple_xml)
        main_output = outputs[""]
        
        # Verify main output contains expected elements
        self.assertIn('<tei:pb', main_output)
        self.assertIn('n="1"', main_output)
        self.assertIn('n="2"', main_output)
        self.assertIn('<tei:head', main_output)
        self.assertIn('Chapter 1', main_output)
        self.assertIn('Chapter 2', main_output)
    
    def test_mediawiki_xml_to_tei_with_wrapper_div(self):
        """Test transformation with wrapper div type."""
        outputs = self.transform(
            self.simple_xml,
            {"wrapper_div_type": "book", "book_name": "genesis"}
        )
        main_output = outputs[""]
        self.assertIn('type="book" n="genesis" corresp="urn:x-opensiddur:text:bible:genesis"', main_output)
    
    def test_mediawiki_xml_to_tei_with_sectioning(self):
        """Test transformation with sectioning enabled."""
        outputs = self.transform(
            self.sectioning_xml,
            {"is_section": True}
        )
        main_output = outputs[""]
        # Should only contain content within section markers
        self.assertIn('<tei:head', main_output)
        self.assertIn('Section Title', main_output)
    
    def test_mediawiki_xml_to_tei_multiple_heads(self):
        """Test transformation with multiple heads (Psalms-like structure)."""
        outputs = self.transform(
            self.multiple_heads_xml,
            {"wrapper_div_type": "book", "book_name": "psalms"}
        )
        main_output = outputs[""]
        # Should create nested divs for each head
        self.assertIn('type="book" n="psalms" corresp="urn:x-opensiddur:text:bible:psalms"', main_output)
        self.assertIn('type="book" n="psalms_1" corresp="urn:x-opensiddur:text:bible:psalms_1"', main_output)
        self.assertIn('type="book" n="psalms_2" corresp="urn:x-opensiddur:text:bible:psalms_2"', main_output)
        self.assertIn('type="book" n="psalms_3" corresp="urn:x-opensiddur:text:bible:psalms_3"', main_output)
    
    def test_mediawiki_xml_to_tei_paragraph_wrapping(self):
        """Test that content is properly wrapped in paragraphs."""
        outputs = self.transform(self.simple_xml)
        main_output = outputs[""]
        # Should contain paragraph elements
        self.assertIn('<tei:p', main_output)
    
    def test_mediawiki_xml_to_tei_milestones(self):
        """Test transformation of milestone elements."""
        outputs = self.transform(
            self.simple_xml,
            {"book_name": "genesis"}
        )
        main_output = outputs[""]
        # Test chapter milestones. Matched without the element name: a chapter milestone
        # standing between paragraphs is not wrapped in a tei:p, so with no enclosing
        # wrapper div to carry the namespace it is serialized with its own declaration.
        self.assertIn('unit="chapter" n="1"', main_output)
        # Note: Chapter 2 milestone is in the second page, so it might not be in the same output
        
        # Test verse milestones
        self.assertIn('unit="verse" n="1"', main_output)
        self.assertIn('unit="verse" n="2"', main_output)
        
        # Test parsha milestone: the canonical name and the transliterated URN path segment
        # both come from the parshah table, not from the way the source spells the name.
        self.assertIn(
            'unit="parsha" n="ויצא" corresp="urn:x-opensiddur:text:bible:genesis/vayetzei"',
            main_output,
        )

    def test_mediawiki_xml_to_tei_lists(self):
        """Test transformation of br elements to lists."""
        outputs = self.transform(self.simple_xml)
        main_output = outputs[""]
        # Should contain list structure
        self.assertIn('<tei:list', main_output)
        # Note: The XSLT processes br elements to create list structure, but content may not be captured
        # This tests that the list structure is created
        self.assertIn('<tei:item>', main_output)
    
    def test_mediawiki_xml_to_tei_ignored_elements(self):
        """Test that certain elements are ignored/removed."""
        outputs = self.transform(self.simple_xml)
        main_output = outputs[""]
        # These elements should be removed/ignored
        self.assertNotIn('<noinclude>', main_output)
    
    def test_mediawiki_xml_to_tei_empty_parameters(self):
        """Test transformation with empty or None parameters."""
        outputs = self.transform(
            self.simple_xml,
            {"wrapper_div_type": "", "book_name": "", "is_section": False}
        )
        main_output = outputs[""]
        # Should not create wrapper div when wrapper_div_type is empty
        self.assertNotIn('<tei:div type=""', main_output)
    
    def test_mediawiki_xml_to_tei_no_parameters(self):
        """Test transformation without any parameters."""
        outputs = self.transform(self.simple_xml)
        main_output = outputs[""]
        # Should contain basic elements
        self.assertIn('<tei:pb', main_output)
        self.assertIn('<tei:head', main_output)
    
    def test_mediawiki_xml_to_tei_page_boundaries(self):
        """Test that page boundaries are correctly handled."""
        outputs = self.transform(self.simple_xml)
        main_output = outputs[""]
        # Should contain page break elements in correct order
        pb_elements = [line.strip() for line in main_output.split('\n') if '<tei:pb' in line]
        self.assertTrue(any('n="1"' in pb for pb in pb_elements))
        self.assertTrue(any('n="2"' in pb for pb in pb_elements))
    
    def test_mediawiki_xml_to_tei_paragraph_structure(self):
        """Test that paragraph structure is maintained correctly."""
        outputs = self.transform(self.simple_xml)
        main_output = outputs[""]
        # Should contain properly structured paragraphs
        self.assertIn('<tei:p', main_output)
        self.assertIn('</tei:p>', main_output)
        
        # Head elements should not be wrapped in paragraphs
        head_lines = [line.strip() for line in main_output.split('\n') if '<tei:head>' in line]
        for head_line in head_lines:
            self.assertNotIn('<tei:p><tei:head>', head_line)
    
    def test_mediawiki_xml_to_tei_tei_elements_preserved(self):
        """Test that existing TEI elements are preserved."""
        tei_xml = """<?xml version="1.0" encoding="UTF-8"?>
<mediawikis xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    <mediawiki>
        <noinclude><c>1</c></noinclude>
        <tei:head>Existing TEI Head</tei:head>
        <tei:p>Existing TEI paragraph</tei:p>
        <tei:note>Existing TEI note</tei:note>
    </mediawiki>
</mediawikis>"""
        
        outputs = self.transform(tei_xml)
        main_output = outputs[""]
        # Existing TEI elements should be preserved
        self.assertIn('Existing TEI Head', main_output)
        self.assertIn('Existing TEI paragraph', main_output)
        # Note: The note element might not be in the main output due to XSLT processing


class TestParshaMilestones(unittest.TestCase):
    """A centered Hebrew word is a parshah running head; a centered Hebrew letter followed by
    its printed Latin name is a Psalm 119 acrostic stanza heading. The two look alike in the
    source and were both emitted as unit="parsha" until they collided."""

    def setUp(self):
        from opensiddur.importer.jps1917.convert_wikisource import MEDIAWIKI_TO_TEI_XSLT
        from opensiddur.common.xslt import xslt_transform_string

        self.parsha_names = skeleton_map_json()
        self.transform = lambda xml, params=None: xslt_transform_string(
            MEDIAWIKI_TO_TEI_XSLT, xml, multiple_results=True,
            xslt_params={"parsha_names": self.parsha_names, **(params or {})},
        )

    def _wrap(self, content):
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<mediawikis xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    <mediawiki>
        <noinclude><c>1</c></noinclude>
        {content}
    </mediawiki>
</mediawikis>"""

    def _transform_names(self, names, book_name="genesis", params=None):
        content = "".join(f"<c><lang>{name}</lang></c><p/>text" for name in names)
        # wrapper_div_type keeps the TEI namespace declaration on the enclosing div rather
        # than repeating it on every element, so assertions can match whole milestones.
        return self.transform(
            self._wrap(content),
            {"book_name": book_name, "wrapper_div_type": "book", **(params or {})},
        )[""]

    def test_running_head_becomes_a_parsha_milestone(self):
        output = self._transform_names(["ויצא"])
        self.assertIn(
            '<tei:milestone unit="parsha" n="ויצא" '
            'corresp="urn:x-opensiddur:text:bible:genesis/vayetzei"/>',
            output,
        )

    def test_source_spellings_are_canonicalized(self):
        # Exactly the @n values the importer used to emit, straight from the 1917 scans.
        cases = {
            "לךלך": ('n="לך־לך"', "genesis/lech_lecha"),
            "נח": ('n="נֹח"', "genesis/noach"),
            "תולדות": ('n="תולדֹת"', "genesis/toldot"),
        }
        for written, (expected_n, expected_path) in cases.items():
            with self.subTest(written=written):
                output = self._transform_names([written])
                self.assertIn(expected_n, output)
                self.assertIn(f'corresp="urn:x-opensiddur:text:bible:{expected_path}"', output)

    def test_urn_path_segments_are_transliterated(self):
        # JLPTEI-3.md requires transliterated path segments with _ for spaces; the names below
        # produced raw Hebrew URNs with literal spaces.
        output = self._transform_names(["כי תצא", "וזאת הברכה"], book_name="deuteronomy")
        self.assertIn('corresp="urn:x-opensiddur:text:bible:deuteronomy/ki_teitzei"', output)
        self.assertIn(
            'corresp="urn:x-opensiddur:text:bible:deuteronomy/vezot_haberakhah"', output)
        for corresp in re.findall(r'unit="parsha"[^/]*corresp="([^"]*)"', output):
            self.assertNotRegex(corresp, r"[֐-׿]")
            self.assertNotIn(" ", corresp)

    def test_acrostic_stanza_is_not_a_parsha(self):
        # {{c|{{lang|he|א}} ALEPH.}} — the Latin name printed beside the letter is what
        # distinguishes a Psalm 119 stanza heading from a parshah running head.
        output = self.transform(
            self._wrap("<c><lang>א</lang> ALEPH.</c><p/>Happy are they that are upright"),
            {"book_name": "psalms", "wrapper_div_type": "book"},
        )[""]
        self.assertIn('<tei:milestone unit="acrostic" n="א"/>', output)
        self.assertNotIn('unit="parsha"', output)
        self.assertNotIn("corresp", output.split('unit="acrostic"')[1])

    def test_acrostic_stanza_does_not_become_a_head(self):
        # A tei:head here would make the multiple-head grouping split Psalms into a
        # sub-book div per stanza.
        output = self.transform(
            self._wrap(
                "<c><larger>Psalm 119</larger></c>"
                "<c><lang>א</lang> ALEPH.</c><p/>one"
                "<c><lang>ב</lang> BETH.</c><p/>two"
            ),
            {"book_name": "psalms", "wrapper_div_type": "book"},
        )[""]
        self.assertEqual(2, output.count('unit="acrostic"'))
        self.assertEqual(1, output.count("<tei:head>"))
        self.assertEqual(1, output.count('type="book"'))

    def test_unknown_name_terminates(self):
        # Rather than inventing a parshah, which is how the acrostic letters became parshiyot.
        with self.assertRaises(Exception):
            self._transform_names(["שלום"])

    def test_book_opening_parsha_is_emitted_after_the_head(self):
        # The first parshah of each book of the Torah has no running head in the source, so it
        # is supplied by the Book table instead.
        output = self.transform(
            self._wrap("<c><larger>GENESIS</larger></c><p/>In the beginning"),
            {"book_name": "genesis", "wrapper_div_type": "book", "first_parsha": "בראשית"},
        )[""]
        self.assertIn(
            '<tei:milestone unit="parsha" n="בראשית" '
            'corresp="urn:x-opensiddur:text:bible:genesis/bereshit"/>',
            output,
        )
        self.assertLess(output.index("</tei:head>"), output.index('unit="parsha"'))
        self.assertEqual("div", self._parent_tag(output, 'unit="parsha"'))

    def test_a_milestone_alone_is_not_wrapped_in_a_paragraph(self):
        """A milestone standing alone marks a boundary between paragraphs — it is not
        paragraph content, and the division it opens contains the chapter and verse
        milestones that follow. The tei:p the running heads used to produce also hid the
        boundary from the PDF exporter, which only rendered milestones inside a pstart."""
        output = self._transform_names(["ויצא"])
        self.assertNotIn("<tei:p><tei:milestone", output)
        self.assertEqual("div", self._parent_tag(output, 'unit="parsha"'))

    def test_an_acrostic_milestone_alone_is_not_wrapped_either(self):
        output = self.transform(
            self._wrap("<c><lang>א</lang> ALEPH.</c><p/>Happy are they that are upright"),
            {"book_name": "psalms", "wrapper_div_type": "book"},
        )[""]
        self.assertEqual("div", self._parent_tag(output, 'unit="acrostic"'))

    def test_text_beside_a_milestone_is_still_a_paragraph(self):
        """The unwrapping must key on "nothing but milestones", not on "contains a
        milestone" — verse milestones live inside the paragraphs they number."""
        output = self._transform_names(["ויצא"])
        root = etree.fromstring(output.encode("utf-8"))
        paragraphs = root.xpath("//tei:p", namespaces={"tei": TEI_NS})
        self.assertEqual(1, len(paragraphs))
        self.assertEqual("text", paragraphs[0].text.strip())

    @staticmethod
    def _parent_tag(output, needle):
        """Local name of the element containing the first match of `needle`."""
        root = etree.fromstring(output.encode("utf-8"))
        attr, value = re.match(r'(\w+)="([^"]*)"', needle).groups()
        found = root.xpath(f"//tei:milestone[@{attr}=$v]",
                           namespaces={"tei": TEI_NS}, v=value)[0]
        return etree.QName(found.getparent()).localname

    def test_no_opening_parsha_outside_the_torah(self):
        output = self.transform(
            self._wrap("<c><larger>JOSHUA</larger></c><p/>Now it came to pass"),
            {"book_name": "joshua", "wrapper_div_type": "book", "first_parsha": ""},
        )[""]
        self.assertNotIn('unit="parsha"', output)


class TestMakeProjectDirectory(unittest.TestCase):
  """Tests for make_project_directory."""

  @patch("opensiddur.importer.jps1917.convert_wikisource.Path.mkdir")
  def test_make_project_directory_custom_path(self, mock_mkdir):
    explicit = Path("/custom/project/jps1917")
    result = make_project_directory(explicit)
    self.assertEqual(result, explicit.resolve())
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


class TestConvertWikisourceMain(unittest.TestCase):
  """Tests for convert_wikisource main()."""

  @patch("opensiddur.importer.jps1917.convert_wikisource.index_file")
  @patch("opensiddur.importer.jps1917.convert_wikisource.make_project_directory")
  def test_main_uses_project_dir(self, mock_make_project_directory, mock_index_file):
    mock_project_dir = Path("/mock/project/jps1917")
    mock_sourcetexts_root = Path("/mock/sources")
    mock_make_project_directory.return_value = mock_project_dir

    main(["--project-dir", str(mock_project_dir), "--sourcetexts-root", str(mock_sourcetexts_root)])

    mock_make_project_directory.assert_called_once_with(mock_project_dir)
    self.assertGreater(mock_index_file.call_count, 0)
    for call in mock_index_file.call_args_list:
      self.assertEqual(call.args[2], mock_project_dir)
      self.assertEqual(call.kwargs.get("project_dir"), None)
      self.assertEqual(call.args[1], mock_sourcetexts_root)


class TestTitlePage(unittest.TestCase):
    """The printed title leaf (Wikisource pages 7-8) is transcribed onto the project
    index, ahead of the preface the encoding agent produces from page 9 onwards."""

    def test_prepend_to_front_inserts_inside_existing_front(self):
        front = '<tei:front xmlns:tei="http://www.tei-c.org/ns/1.0"><tei:p>Preface</tei:p></tei:front>'
        result = prepend_to_front(front, "<tei:pb n='i'/>")
        self.assertTrue(result.startswith('<tei:front xmlns:tei='))
        self.assertLess(result.index("<tei:pb"), result.index("<tei:p>Preface"))
        self.assertTrue(result.endswith("</tei:front>"))

    def test_prepend_to_front_creates_front_when_there_is_none(self):
        result = prepend_to_front("", "<tei:pb n='i'/>")
        self.assertIn("<tei:front>", result)
        self.assertIn("<tei:pb n='i'/>", result)
        self.assertIn("</tei:front>", result)

    def test_prepend_to_front_rejects_a_non_front_fragment(self):
        with self.assertRaises(ValueError):
            prepend_to_front("<tei:body/>", "<tei:pb n='i'/>")

    def test_title_page_transcribes_the_printed_leaf(self):
        self.assertIn('<tei:titlePart type="main">THE HOLY SCRIPTURES</tei:titlePart>', TITLE_PAGE)
        self.assertIn("תורה נביאים וכתובים", TITLE_PAGE)
        self.assertIn("<tei:pubPlace>PHILADELPHIA</tei:pubPlace>", TITLE_PAGE)
        # The copyright verso is its own page and its own title page.
        self.assertEqual(TITLE_PAGE.count("<tei:titlePage"), 2)
        # Each page links to its scan: the title leaf is scan pages 7 and 8.
        self.assertIn('<tei:pb n="i" ed="1917" '
                      'facs="https://en.wikisource.org/wiki/Page:JPS-1917-Universal.djvu/7"/>',
                      TITLE_PAGE)
        self.assertIn('<tei:pb n="ii" ed="1917" '
                      'facs="https://en.wikisource.org/wiki/Page:JPS-1917-Universal.djvu/8"/>',
                      TITLE_PAGE)

    @patch('opensiddur.importer.jps1917.convert_wikisource.validate_and_write_tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.process_mediawiki')
    @patch('opensiddur.importer.jps1917.convert_wikisource.header')
    @patch('opensiddur.importer.jps1917.convert_wikisource.get_credits_pages')
    @patch('builtins.open', new_callable=mock_open)
    def test_top_level_index_carries_the_title_page(
        self, mock_file, mock_get_credits, mock_header, mock_process_mediawiki,
        mock_tei_file, mock_validate_write,
    ):
        mock_get_credits.return_value = []
        mock_header.return_value = "<tei:teiHeader/>"
        mock_process_mediawiki.return_value = {
            "front": '<tei:front xmlns:tei="http://www.tei-c.org/ns/1.0"><tei:p>Preface</tei:p></tei:front>',
            "body": "",
            "standOff": "",
        }
        mock_tei_file.return_value = "<tei:TEI/>"

        index_file(Index(
            index_title_en="The Holy Scriptures",
            index_title_he="תורה נביאים וכתובים",
            file_name="index",
            transclusions=[],
            start_page=9,
            end_page=18,
        ))

        front = mock_tei_file.call_args[1]["front"]
        self.assertIn("<tei:titlePage>", front)
        self.assertLess(front.index("<tei:titlePage>"), front.index("<tei:p>Preface"))

    @patch('opensiddur.importer.jps1917.convert_wikisource.validate_and_write_tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.tei_file')
    @patch('opensiddur.importer.jps1917.convert_wikisource.header')
    @patch('builtins.open', new_callable=mock_open)
    def test_sub_index_carries_no_title_page(
        self, mock_file, mock_header, mock_tei_file, mock_validate_write,
    ):
        """the_law/the_prophets/the_writings are structural; only the book as a whole
        has a printed title page."""
        mock_header.return_value = "<tei:teiHeader/>"
        mock_tei_file.return_value = "<tei:TEI/>"

        index_file(Index(
            index_title_en="The Law",
            index_title_he="תורה",
            file_name="the_law",
            transclusions=[],
        ))

        self.assertNotIn("front", mock_tei_file.call_args[1])


if __name__ == '__main__':
    unittest.main()

