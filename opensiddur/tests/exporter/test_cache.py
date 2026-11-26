"""Tests for the XMLCache class."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from lxml import etree

from opensiddur.exporter.cache import XMLCache


class TestXMLCache(unittest.TestCase):
    """Test the XMLCache class."""

    def setUp(self):
        """Set up test fixtures."""
        self.base_path = Path("/test/base/path")
        self.cache = XMLCache(base_path=self.base_path)

    def test_init_with_default_base_path(self):
        """Test that XMLCache initializes with default PROJECT_DIRECTORY."""
        from opensiddur.common.constants import PROJECT_DIRECTORY
        cache = XMLCache()
        self.assertEqual(cache.base_path, PROJECT_DIRECTORY)
        self.assertEqual(cache.cache, {})

    def test_init_with_custom_base_path(self):
        """Test that XMLCache initializes with custom base path."""
        custom_path = Path("/custom/path")
        cache = XMLCache(base_path=custom_path)
        self.assertEqual(cache.base_path, custom_path)
        self.assertEqual(cache.cache, {})

    def test_path_of_file(self):
        """Test that _path_of_file constructs correct paths."""
        path = self.cache._path_of_file("wlc", "genesis.xml")
        expected = self.base_path / "wlc" / "genesis.xml"
        self.assertEqual(path, expected)

    def test_parse_xml_file_not_found(self):
        """Test that parse_xml raises FileNotFoundError when file doesn't exist."""
        with patch.object(Path, 'exists', return_value=False):
            with self.assertRaises(FileNotFoundError) as context:
                self.cache.parse_xml("wlc", "genesis.xml")
            
            self.assertIn("not found", str(context.exception))

    @patch('lxml.etree.parse')
    @patch.object(Path, 'exists', return_value=True)
    def test_parse_xml_success(self, mock_exists, mock_parse):
        """Test that parse_xml successfully parses XML and adds to cache."""
        # Create a mock ElementTree
        mock_tree = etree.ElementTree(etree.fromstring(b'<root><child>text</child></root>'))
        mock_parse.return_value = mock_tree
        
        result = self.cache.parse_xml("wlc", "genesis.xml")
        
        # Verify etree.parse was called with the correct path (as string)
        expected_path = str(self.base_path / "wlc" / "genesis.xml")
        mock_parse.assert_called_once_with(expected_path)
        
        # Verify result is the mock tree
        self.assertIsNotNone(result)
        self.assertIs(result, mock_tree)
        
        # Verify root element
        root = result.getroot()
        self.assertEqual(root.tag, "root")
        self.assertEqual(len(root), 1)
        self.assertEqual(root[0].tag, "child")
        self.assertEqual(root[0].text, "text")
        
        # Verify it was added to cache
        self.assertIn((self.base_path, "wlc", "genesis.xml"), self.cache.cache)
        self.assertEqual(self.cache.cache[(self.base_path, "wlc", "genesis.xml")], result)

    @patch('lxml.etree.parse')
    @patch.object(Path, 'exists', return_value=True)
    def test_parse_xml_uses_cache(self, mock_exists, mock_parse):
        """Test that parse_xml returns cached result on second call."""
        # Create a mock ElementTree
        mock_tree = etree.ElementTree(etree.fromstring(b'<root><child>text</child></root>'))
        mock_parse.return_value = mock_tree
        
        # First call - should parse and cache
        result1 = self.cache.parse_xml("wlc", "genesis.xml")
        
        # Verify etree.parse was called once
        self.assertEqual(mock_parse.call_count, 1)
        
        # Second call - should use cache
        result2 = self.cache.parse_xml("wlc", "genesis.xml")
        
        # Verify etree.parse was NOT called again
        self.assertEqual(mock_parse.call_count, 1)
        
        # Verify same object is returned
        self.assertIs(result1, result2)

    @patch('lxml.etree.parse')
    @patch.object(Path, 'exists', return_value=True)
    def test_parse_xml_different_files_not_cached_together(self, mock_exists, mock_parse):
        """Test that different files have separate cache entries."""
        # Set up different XML for each file
        def side_effect(path):
            path_str = str(path)
            if "genesis.xml" in path_str:
                return etree.ElementTree(etree.fromstring(b'<genesis>Genesis content</genesis>'))
            elif "exodus.xml" in path_str:
                return etree.ElementTree(etree.fromstring(b'<exodus>Exodus content</exodus>'))
            return etree.ElementTree(etree.fromstring(b'<root/>'))
        
        mock_parse.side_effect = side_effect
        
        # Parse two different files
        result1 = self.cache.parse_xml("wlc", "genesis.xml")
        result2 = self.cache.parse_xml("wlc", "exodus.xml")
        
        # Verify both were parsed
        self.assertEqual(mock_parse.call_count, 2)
        
        # Verify both are in cache
        self.assertIn((self.base_path, "wlc", "genesis.xml"), self.cache.cache)
        self.assertIn((self.base_path, "wlc", "exodus.xml"), self.cache.cache)
        
        # Verify they are different objects
        self.assertIsNot(result1, result2)
        
        # Verify content is correct
        self.assertEqual(result1.getroot().tag, "genesis")
        self.assertEqual(result2.getroot().tag, "exodus")

    @patch('lxml.etree.parse')
    @patch.object(Path, 'exists', return_value=True)
    def test_parse_xml_different_projects_not_cached_together(self, mock_exists, mock_parse):
        """Test that same file from different projects have separate cache entries."""
        # Set up different XML for each project
        def side_effect(path):
            path_str = str(path)
            if "wlc" in path_str:
                return etree.ElementTree(etree.fromstring(b'<wlc>WLC version</wlc>'))
            elif "jps1917" in path_str:
                return etree.ElementTree(etree.fromstring(b'<jps>JPS version</jps>'))
            return etree.ElementTree(etree.fromstring(b'<root/>'))
        
        mock_parse.side_effect = side_effect
        
        # Parse same file from two different projects
        result1 = self.cache.parse_xml("wlc", "genesis.xml")
        result2 = self.cache.parse_xml("jps1917", "genesis.xml")
        
        # Verify both were parsed
        self.assertEqual(mock_parse.call_count, 2)
        
        # Verify both are in cache with different keys
        self.assertIn((self.base_path, "wlc", "genesis.xml"), self.cache.cache)
        self.assertIn((self.base_path, "jps1917", "genesis.xml"), self.cache.cache)
        
        # Verify they are different objects
        self.assertIsNot(result1, result2)
        
        # Verify content is correct
        self.assertEqual(result1.getroot().tag, "wlc")
        self.assertEqual(result2.getroot().tag, "jps")

    @patch('lxml.etree.parse')
    @patch.object(Path, 'exists', return_value=True)
    def test_cache_persists_across_calls(self, mock_exists, mock_parse):
        """Test that cache persists across multiple parse_xml calls."""
        # Mock parse to return different trees
        def side_effect(path):
            return etree.ElementTree(etree.fromstring(b'<root><child>text</child></root>'))
        
        mock_parse.side_effect = side_effect
        
        # Parse first file
        self.cache.parse_xml("wlc", "genesis.xml")
        
        # Manually add another entry to cache
        mock_doc = MagicMock()
        self.cache.cache[(self.base_path, "jps1917", "exodus.xml")] = mock_doc
        
        # Parse another file
        self.cache.parse_xml("wlc", "leviticus.xml")
        
        # Verify all cache entries still exist
        self.assertEqual(len(self.cache.cache), 3)
        self.assertIn((self.base_path, "wlc", "genesis.xml"), self.cache.cache)
        self.assertIn((self.base_path, "jps1917", "exodus.xml"), self.cache.cache)
        self.assertIn((self.base_path, "wlc", "leviticus.xml"), self.cache.cache)

    def test_cache_empty_initially(self):
        """Test that cache is empty when XMLCache is initialized."""
        cache = XMLCache(base_path=Path("/test"))
        self.assertEqual(len(cache.cache), 0)
        self.assertEqual(cache.cache, {})

    @patch('lxml.etree.parse')
    @patch.object(Path, 'exists', return_value=True)
    def test_parse_xml_with_namespaces(self, mock_exists, mock_parse):
        """Test that parse_xml correctly handles XML with namespaces."""
        # Create a mock tree with namespaces
        mock_tree = etree.ElementTree(etree.fromstring(b'<root xmlns="http://example.com/ns"><child>text</child></root>'))
        mock_parse.return_value = mock_tree
        
        result = self.cache.parse_xml("wlc", "genesis.xml")
        
        # Verify result is parsed correctly
        self.assertIsNotNone(result)
        root = result.getroot()
        self.assertEqual(root.tag, "{http://example.com/ns}root")
        
        # Verify it's cached
        self.assertIn((self.base_path, "wlc", "genesis.xml"), self.cache.cache)

    @patch('lxml.etree.parse')
    @patch.object(Path, 'exists', return_value=True)
    def test_parse_xml_invalid_xml(self, mock_exists, mock_parse):
        """Test that parse_xml raises an exception for invalid XML."""
        # Mock parse to raise XMLSyntaxError
        mock_parse.side_effect = etree.XMLSyntaxError("Invalid XML", 1, 1, 1)
        
        with self.assertRaises(etree.XMLSyntaxError):
            self.cache.parse_xml("wlc", "invalid.xml")
        
        # Verify nothing was added to cache
        self.assertNotIn((self.base_path, "wlc", "invalid.xml"), self.cache.cache)

    @patch('lxml.etree.parse')
    @patch.object(Path, 'exists', return_value=True)
    def test_cache_key_is_tuple(self, mock_exists, mock_parse):
        """Test that cache key is a tuple of (base path, project, file_name)."""
        # Mock parse to return a tree
        mock_tree = etree.ElementTree(etree.fromstring(b'<root><child>first</child></root>'))
        mock_parse.return_value = mock_tree
        
        self.cache.parse_xml("wlc", "genesis.xml")
        
        # Verify the key is a tuple
        keys = list(self.cache.cache.keys())
        self.assertEqual(len(keys), 1)
        self.assertIsInstance(keys[0], tuple)
        self.assertEqual(keys[0], (self.base_path, "wlc", "genesis.xml"))




class TestXMLCacheBasePath(unittest.TestCase):
    def test_a_new_base_path_reads_the_new_file(self):
        """The same project and file name under another base path is another file."""
        import tempfile
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            for base, text in ((first, "first"), (second, "second")):
                (Path(base) / "p").mkdir()
                (Path(base) / "p" / "a.xml").write_text(f"<r>{text}</r>")
            cache = XMLCache(base_path=Path(first))
            self.assertEqual(cache.parse_xml("p", "a.xml").getroot().text, "first")
            cache.base_path = Path(second)
            self.assertEqual(cache.parse_xml("p", "a.xml").getroot().text, "second")


if __name__ == '__main__':
    unittest.main()
