"""Tests for the InlineCompilerProcessor class."""

import re
from typing import Optional
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from lxml import etree
from opensiddur.exporter.inline_compiler import InlineCompilerProcessor
from opensiddur.exporter.linear import LinearData, reset_linear_data, get_linear_data
from opensiddur.exporter.refdb import Reference, ReferenceDatabase, UrnMapping, find_end_of_mapping
from opensiddur.exporter.urn import ResolvedUrn

PROCESSING_NAMESPACE = 'http://jewishliturgy.org/ns/processing'
TEI_NAMESPACE = 'http://www.tei-c.org/ns/1.0'
NS = {'tei': TEI_NAMESPACE, 'p': PROCESSING_NAMESPACE}

class TestInlineCompilerProcessor(unittest.TestCase):
    """Test InlineCompilerProcessor for extracting text content between start and end markers."""

    def setUp(self):
        """Set up test fixtures and reset linear data."""
        reset_linear_data()
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_project_dir = Path(self.temp_dir.name) / "test_project"
        self.test_project_dir.mkdir(parents=True)

        # Patch the xml_cache base_path to use our temp directory
        self.linear_data = LinearData(
            instruction_priority=["priority_project", "test_project"],
            annotation_projects=["priority_project", "test_project"],
            project_priority=["priority_project", "test_project"],
        )
        self.linear_data.xml_cache.base_path = Path(self.temp_dir.name)


    def _create_test_file(self, file_name: str, content: bytes) -> tuple[str, str]:
        """Create a test XML file and return (project, file_name) tuple."""
        file_path = self.test_project_dir / file_name
        with open(file_path, 'wb') as f:
            f.write(content)
        return "test_project", file_name

    def _get_element_path(self, xml_content: bytes, identifier: str) -> str:
        """Get the XPath path for an element identified by corresp or xml:id.

        Args:
            xml_content: The XML content as bytes
            identifier: Either a corresp value (e.g. 'urn:start') or an xml:id reference (e.g. '#target')

        Returns:
            The absolute XPath path for the element
        """
        root = etree.fromstring(xml_content)
        tree = root.getroottree()
        xml_ns = 'http://www.w3.org/XML/1998/namespace'
        if identifier.startswith('#'):
            xml_id = identifier[1:]
            elements = root.xpath(f"//*[@xml:id='{xml_id}']", namespaces={'xml': xml_ns})
        else:
            elements = root.xpath(f"//*[@corresp='{identifier}']")
        if not elements:
            raise ValueError(f"Element with identifier '{identifier}' not found in XML")
        return tree.getpath(elements[0])

    def test_start_and_end_are_siblings(self):
        """Test when start and end are sibling elements at the same level."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:div>
        <tei:p corresp="urn:start">First paragraph</tei:p>
        <tei:p>Middle paragraph</tei:p>
        <tei:p corresp="urn:end">Last paragraph</tei:p>
        <tei:p>After end paragraph</tei:p>
    </tei:div>
</root>'''

        project, file_name = self._create_test_file("siblings.xml", xml_content)

        start_path = self._get_element_path(xml_content, "urn:start")
        end_path = self._get_element_path(xml_content, "urn:end")
        processor = InlineCompilerProcessor(project, file_name, start_path, end_path, linear_data=self.linear_data)
        result = processor.process()

        # Result should be a p:transcludeInline element with the extracted text
        self.assertEqual(result.tag, "{http://jewishliturgy.org/ns/processing}transcludeInline")
        result_text = result.text

        # Should include ONLY text from start, middle, and end paragraphs with whitespace between them
        pattern = r'^\s*First paragraph\s+Middle paragraph\s+Last paragraph\s*$'
        self.assertIsNotNone(re.match(pattern, result_text, re.DOTALL),
                             f"Result text should match pattern. Got: {result_text!r}")

        # Should NOT include text after end
        self.assertNotIn("After end paragraph", result_text)

    def test_start_is_ancestor_of_end(self):
        """Test when start element is an ancestor of the end element."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:div corresp="urn:start">
        <tei:p>Outer start text</tei:p>
        <tei:div>
            <tei:p>Nested middle text</tei:p>
            <tei:p corresp="urn:end">Nested end text</tei:p>
            <tei:p>After end text</tei:p>
        </tei:div>
        <tei:p>After nested div</tei:p>
    </tei:div>
    <tei:div>
        <tei:p>After start div</tei:p>
    </tei:div>
</root>'''

        project, file_name = self._create_test_file("ancestor.xml", xml_content)

        start_path = self._get_element_path(xml_content, "urn:start")
        end_path = self._get_element_path(xml_content, "urn:end")
        processor = InlineCompilerProcessor(project, file_name, start_path, end_path, linear_data=self.linear_data)
        result = processor.process()

        self.assertEqual(result.tag, "{http://jewishliturgy.org/ns/processing}transcludeInline")
        result_text = result.text

        # Should include ONLY text from start element and up to end
        pattern = r'^\s*Outer start text\s+Nested middle text\s+Nested end text\s*$'
        self.assertIsNotNone(re.match(pattern, result_text, re.DOTALL),
                             f"Result text should match pattern. Got: {result_text!r}")

        # Should NOT include text after end
        self.assertNotIn("After end text", result_text)
        self.assertNotIn("After nested div", result_text)
        self.assertNotIn("After start div", result_text)

    def test_start_deeper_than_end(self):
        """Test when start is 3 levels deep and end is 2 levels deep."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:div>
        <tei:div>
            <tei:div>
                <tei:p corresp="urn:start">Start at level 3</tei:p>
                <tei:p>Also level 3</tei:p>
            </tei:div>
            <tei:p>Back to level 2</tei:p>
        </tei:div>
        <tei:p corresp="urn:end">End at level 2</tei:p>
        <tei:p>After end at level 2</tei:p>
    </tei:div>
</root>'''

        project, file_name = self._create_test_file("depth_diff.xml", xml_content)

        start_path = self._get_element_path(xml_content, "urn:start")
        end_path = self._get_element_path(xml_content, "urn:end")
        processor = InlineCompilerProcessor(project, file_name, start_path, end_path, linear_data=self.linear_data)
        result = processor.process()

        self.assertEqual(result.tag, "{http://jewishliturgy.org/ns/processing}transcludeInline")
        result_text = result.text

        # Should include ONLY text from start through end
        pattern = r'^\s*Start at level 3\s+Also level 3\s+Back to level 2\s+End at level 2\s*$'
        self.assertIsNotNone(re.match(pattern, result_text, re.DOTALL),
                             f"Result text should match pattern. Got: {result_text!r}")

        # Should NOT include text after end
        self.assertNotIn("After end at level 2", result_text)

    def test_start_and_end_descendants_of_different_siblings(self):
        """Test when start and end are descendants of different sibling elements."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:div>
        <tei:div type="first">
            <tei:p>Before start in first div</tei:p>
            <tei:p corresp="urn:start">Start in first div</tei:p>
            <tei:p>After start in first div</tei:p>
        </tei:div>
        <tei:div type="second">
            <tei:p>Content in second div</tei:p>
            <tei:p corresp="urn:end">End in second div</tei:p>
            <tei:p>After end in second div</tei:p>
        </tei:div>
        <tei:div type="third">
            <tei:p>Content in third div (after end)</tei:p>
        </tei:div>
    </tei:div>
</root>'''

        project, file_name = self._create_test_file("diff_siblings.xml", xml_content)

        start_path = self._get_element_path(xml_content, "urn:start")
        end_path = self._get_element_path(xml_content, "urn:end")
        processor = InlineCompilerProcessor(project, file_name, start_path, end_path, linear_data=self.linear_data)
        result = processor.process()

        self.assertEqual(result.tag, "{http://jewishliturgy.org/ns/processing}transcludeInline")
        result_text = result.text

        # Should include ONLY text from start through end across different sibling divs
        pattern = r'^\s*Start in first div\s+After start in first div\s+Content in second div\s+End in second div\s*$'
        self.assertIsNotNone(re.match(pattern, result_text, re.DOTALL),
                             f"Result text should match pattern. Got: {result_text!r}")

        # Should NOT include text before start or after end
        self.assertNotIn("Before start in first div", result_text)
        self.assertNotIn("After end in second div", result_text)
        self.assertNotIn("Content in third div", result_text)

    def test_result_is_text_element(self):
        """Test that InlineCompilerProcessor returns a p:transcludeInline element."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:p corresp="urn:start">Start</tei:p>
    <tei:p corresp="urn:end">End</tei:p>
</root>'''

        project, file_name = self._create_test_file("text_elem.xml", xml_content)

        start_path = self._get_element_path(xml_content, "urn:start")
        end_path = self._get_element_path(xml_content, "urn:end")
        processor = InlineCompilerProcessor(project, file_name, start_path, end_path, linear_data=self.linear_data)
        result = processor.process()

        # Should be a p:transcludeInline element
        self.assertEqual(result.tag, "{http://jewishliturgy.org/ns/processing}transcludeInline")
        self.assertIsInstance(result, etree._Element)

        # Should have text content
        self.assertIsNotNone(result.text)
        self.assertIn("Start", result.text)
        self.assertIn("End", result.text)

    def test_text_extraction_preserves_whitespace(self):
        """Test that whitespace in text is preserved."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:p corresp="urn:start">  Start with spaces  </tei:p>
    <tei:p>  Middle  with  spaces  </tei:p>
    <tei:p corresp="urn:end">  End with spaces  </tei:p>
</root>'''

        project, file_name = self._create_test_file("whitespace.xml", xml_content)

        start_path = self._get_element_path(xml_content, "urn:start")
        end_path = self._get_element_path(xml_content, "urn:end")
        processor = InlineCompilerProcessor(project, file_name, start_path, end_path, linear_data=self.linear_data)
        result = processor.process()

        result_text = result.text

        # Whitespace should be preserved in the extracted text
        self.assertIn("Start with spaces", result_text)
        self.assertIn("Middle", result_text)
        self.assertIn("spaces", result_text)
        self.assertIn("End with spaces", result_text)

    def test_using_xml_id_instead_of_corresp(self):
        """Test that xml:id can be used with #id notation for start/end."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:p xml:id="start_id">Start with xml:id</tei:p>
    <tei:p>Middle content</tei:p>
    <tei:p xml:id="end_id">End with xml:id</tei:p>
    <tei:p>After end</tei:p>
</root>'''

        project, file_name = self._create_test_file("xmlid.xml", xml_content)

        start_path = self._get_element_path(xml_content, "#start_id")
        end_path = self._get_element_path(xml_content, "#end_id")
        processor = InlineCompilerProcessor(project, file_name, start_path, end_path, linear_data=self.linear_data)
        result = processor.process()

        result_text = result.text

        # Should extract text using xml:id
        self.assertIn("Start with xml:id", result_text)
        self.assertIn("Middle content", result_text)
        self.assertIn("End with xml:id", result_text)

        # Should NOT include text after end
        self.assertNotIn("After end", result_text)

    def test_mixed_corresp_and_xml_id(self):
        """Test using corresp for start and xml:id for end."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:p corresp="urn:start">Start with corresp</tei:p>
    <tei:p>Middle content</tei:p>
    <tei:p xml:id="end_id">End with xml:id</tei:p>
</root>'''

        project, file_name = self._create_test_file("mixed.xml", xml_content)

        start_path = self._get_element_path(xml_content, "urn:start")
        end_path = self._get_element_path(xml_content, "#end_id")
        processor = InlineCompilerProcessor(project, file_name, start_path, end_path, linear_data=self.linear_data)
        result = processor.process()

        result_text = result.text

        # Should work with mixed identifier types
        self.assertIn("Start with corresp", result_text)
        self.assertIn("Middle content", result_text)
        self.assertIn("End with xml:id", result_text)

    def test_single_element_start_equals_end(self):
        """Test when start and end are the same element."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:p>Before</tei:p>
    <tei:p corresp="urn:target">Target content</tei:p>
    <tei:p>After</tei:p>
</root>'''

        project, file_name = self._create_test_file("single.xml", xml_content)

        target_path = self._get_element_path(xml_content, "urn:target")
        processor = InlineCompilerProcessor(project, file_name, target_path, target_path, linear_data=self.linear_data)
        result = processor.process()

        result_text = result.text

        # Should extract ONLY the target element's text
        pattern = r'^\s*Target content\s*$'
        self.assertIsNotNone(re.match(pattern, result_text, re.DOTALL),
                             f"Result text should match pattern. Got: {result_text!r}")

    def test_start_and_end_both_2_levels_deep(self):
        """Test when start and end are both at the same depth (2 levels) as siblings."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:div>
        <tei:div>
            <tei:p>Content before start</tei:p>
            <tei:p corresp="urn:start">Start at level 2</tei:p>
            <tei:p>Middle content at level 2</tei:p>
            <tei:p corresp="urn:end">End at level 2</tei:p>
            <tei:p>Content after end</tei:p>
        </tei:div>
        <tei:p>Content outside nested div</tei:p>
    </tei:div>
</root>'''

        project, file_name = self._create_test_file("both_level2.xml", xml_content)

        start_path = self._get_element_path(xml_content, "urn:start")
        end_path = self._get_element_path(xml_content, "urn:end")
        processor = InlineCompilerProcessor(project, file_name, start_path, end_path, linear_data=self.linear_data)
        result = processor.process()

        self.assertEqual(result.tag, "{http://jewishliturgy.org/ns/processing}transcludeInline")
        result_text = result.text

        # Should include ONLY text from start through end at level 2
        pattern = r'^\s*Start at level 2\s+Middle content at level 2\s+End at level 2\s*$'
        self.assertIsNotNone(re.match(pattern, result_text, re.DOTALL),
                             f"Result text should match pattern. Got: {result_text!r}")

    @patch('opensiddur.exporter.urn.UrnResolver.resolve_range')
    def test_inline_transclusion(self, mock_resolve_range):
        """Test InlineCompilerProcessor with a transclusion element."""
        # Create main file with transclusion element
        # Include text before start, after end, and tail text on elements
        main_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    <tei:p>Text before start (excluded)</tei:p> Also before start.
    <tei:p corresp="urn:main-start">Text before transclusion</tei:p> tail after start element
    <j:transclude target="urn:other:start" targetEnd="urn:other:end" type="inline"/> tail after transclude
    <tei:p corresp="urn:main-end">Text after transclusion</tei:p> tail after end element
    <tei:p>Text after end (excluded)</tei:p>
</root>'''

        # Create transcluded file with tail text before start, between elements, and after end
        transcluded_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:div>
        <tei:p>Before transcluded start (excluded)</tei:p> Tail before start (excluded)
        <tei:p corresp="urn:other:start">Transcluded start</tei:p> Tail after transcluded start
        <tei:p>Transcluded middle</tei:p> Tail after transcluded middle
        <tei:p corresp="urn:other:end">Transcluded end</tei:p> Tail of end element (included)
        <tei:p>After transcluded end (excluded)</tei:p>
    </tei:div>
</root>'''

        # Set up files
        main_project, main_file = self._create_test_file("main.xml", main_xml_content)
        trans_project, trans_file = self._create_test_file("transcluded.xml", transcluded_xml_content)

        # Parse the transcluded XML tree
        transcluded_tree_root = etree.fromstring(transcluded_xml_content)

        # Mock XMLCache.parse_xml
        original_parse_xml = self.linear_data.xml_cache.parse_xml

        def mock_parse_xml(*args, **kwargs):
            if len(args) == 2 and args[0] == main_project and args[1] == main_file:
                # Main file - call original
                return original_parse_xml(*args, **kwargs)
            elif len(args) == 2 and args[0] == trans_project and args[1] == trans_file:
                # Transcluded file - return mocked tree
                mock_tree = MagicMock()
                mock_tree.getroot.return_value = transcluded_tree_root
                return mock_tree
            else:
                return original_parse_xml(*args, **kwargs)

        # Compute the actual element paths in the transcluded file for the mock
        trans_root = etree.fromstring(transcluded_xml_content)
        trans_tree = trans_root.getroottree()
        other_start_path = trans_tree.getpath(trans_root.xpath("//*[@corresp='urn:other:start']")[0])
        other_end_path = trans_tree.getpath(trans_root.xpath("//*[@corresp='urn:other:end']")[0])

        # Mock URN resolution to return the transcluded file location
        mock_resolve_range.side_effect = [
            [ResolvedUrn(project=trans_project, file_name=trans_file, urn="urn:other:start", element_path=other_start_path)],
            [ResolvedUrn(project=trans_project, file_name=trans_file, urn="urn:other:end", element_path=other_end_path)]
        ]

        # Compute paths for the main file elements
        start_path = self._get_element_path(main_xml_content, "urn:main-start")
        end_path = self._get_element_path(main_xml_content, "urn:main-end")

        # Process the main file with mocked parse_xml
        with patch.object(self.linear_data.xml_cache, 'parse_xml', side_effect=mock_parse_xml):
            processor = InlineCompilerProcessor(main_project, main_file, start_path, end_path, linear_data=self.linear_data)
            result = processor.process()

        self.assertEqual(result.tag, "{http://jewishliturgy.org/ns/processing}transcludeInline")

        # The main text comes before and after the transclusion, in document order
        self.assertIn("Text before transclusion", result.text)
        self.assertIn("tail after start element", result.text)
        all_text = "".join(result.itertext())
        self.assertLess(all_text.index("Text before transclusion"), all_text.index("Transcluded start"))
        self.assertLess(all_text.index("Transcluded end"), all_text.index("Text after transclusion"))

        # Should NOT include text before start or after end
        self.assertNotIn("Text before start (excluded)", all_text)
        self.assertNotIn("Also before start", all_text)
        self.assertNotIn("Text after end (excluded)", all_text)

        # Verify that resolve_range was called with correct URNs
        mock_resolve_range.assert_any_call("urn:other:start")
        mock_resolve_range.assert_any_call("urn:other:end")

        # Verify the result contains a p:transclude element as a child
        # p:transclude elements are retained as children in InlineCompilerProcessor
        transclude_children = result.findall(".//{http://jewishliturgy.org/ns/processing}transclude")
        self.assertEqual(len(transclude_children), 1)

        transclude_elem = transclude_children[0]
        self.assertEqual(transclude_elem.get('target'), 'urn:other:start')
        self.assertEqual(transclude_elem.get('targetEnd'), 'urn:other:end')
        self.assertEqual(transclude_elem.get('type'), 'inline')

        # The transcluded text should be in the p:transclude element
        self.assertIn("Transcluded start", transclude_elem.text)
        self.assertIn("Transcluded middle", transclude_elem.text)
        self.assertIn("Transcluded end", transclude_elem.text)

        # Should include tail text from within the transcluded content
        self.assertIn("Tail after transcluded start", transclude_elem.text)
        self.assertIn("Tail after transcluded middle", transclude_elem.text)
        # The tail of the end element is also included (it's part of the range)
        self.assertIn("Tail of end element (included)", transclude_elem.text)

        # Should NOT include text/tails before start or after the end element's tail
        self.assertNotIn("Before transcluded start (excluded)", transclude_elem.text)
        self.assertNotIn("Tail before start (excluded)", transclude_elem.text)
        self.assertNotIn("After transcluded end (excluded)", transclude_elem.text)

        # The p:transclude element should have the tail text from the main file
        self.assertIsNotNone(transclude_elem.tail)
        self.assertIn("tail after transclude", transclude_elem.tail)

    @patch('opensiddur.exporter.urn.UrnResolver.resolve_range')
    def test_nested_transclusion(self, mock_resolve_range):
        """Test InlineCompilerProcessor with nested transclusions (transcluded file has its own transclusion)."""
        # Create main file with transclusion element
        main_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    <tei:p corresp="urn:main-start">Text before transclusion</tei:p>
    <j:transclude target="urn:level1:start" targetEnd="urn:level1:end" type="inline"/>
    <tei:p corresp="urn:main-end">Text after transclusion</tei:p>
</root>'''

        # Create first level transcluded file that itself has a transclusion (type=external)
        level1_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    <tei:div>
        <tei:p corresp="urn:level1:start">Level 1 start</tei:p>
        <j:transclude target="urn:level2:start" targetEnd="urn:level2:end" type="external"/>
        <tei:p corresp="urn:level1:end">Level 1 end</tei:p>
    </tei:div>
</root>'''

        # Create second level transcluded file
        level2_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:div>
        <tei:p corresp="urn:level2:start">Level 2 start</tei:p>
        <tei:p>Level 2 middle</tei:p>
        <tei:p corresp="urn:level2:end">Level 2 end</tei:p>
    </tei:div>
</root>'''

        # Set up files
        main_project, main_file = self._create_test_file("main.xml", main_xml_content)
        level1_project, level1_file = self._create_test_file("level1.xml", level1_xml_content)
        level2_project, level2_file = self._create_test_file("level2.xml", level2_xml_content)

        # Parse the transcluded XML trees
        level1_tree_root = etree.fromstring(level1_xml_content)
        level2_tree_root = etree.fromstring(level2_xml_content)

        # Mock XMLCache.parse_xml
        original_parse_xml = self.linear_data.xml_cache.parse_xml

        def mock_parse_xml(*args, **kwargs):
            if len(args) == 2 and args[0] == main_project and args[1] == main_file:
                # Main file - call original
                return original_parse_xml(*args, **kwargs)
            elif len(args) == 2 and args[0] == level1_project and args[1] == level1_file:
                # Level1 file - return mocked tree
                mock_tree = MagicMock()
                mock_tree.getroot.return_value = level1_tree_root
                return mock_tree
            elif len(args) == 2 and args[0] == level2_project and args[1] == level2_file:
                # Level2 file - return mocked tree
                mock_tree = MagicMock()
                mock_tree.getroot.return_value = level2_tree_root
                return mock_tree
            else:
                return original_parse_xml(*args, **kwargs)

        # Compute the actual element paths in the transcluded files for the mocks
        l1_root = etree.fromstring(level1_xml_content)
        l1_tree = l1_root.getroottree()
        l1_start_path = l1_tree.getpath(l1_root.xpath("//*[@corresp='urn:level1:start']")[0])
        l1_end_path = l1_tree.getpath(l1_root.xpath("//*[@corresp='urn:level1:end']")[0])

        l2_root = etree.fromstring(level2_xml_content)
        l2_tree = l2_root.getroottree()
        l2_start_path = l2_tree.getpath(l2_root.xpath("//*[@corresp='urn:level2:start']")[0])
        l2_end_path = l2_tree.getpath(l2_root.xpath("//*[@corresp='urn:level2:end']")[0])

        # Mock URN resolution for multiple levels
        # First two calls are for the main file's transclusion
        # Next two calls are for the level1 file's transclusion
        mock_resolve_range.side_effect = [
            [ResolvedUrn(project=level1_project, file_name=level1_file, urn="urn:level1:start", element_path=l1_start_path)],
            [ResolvedUrn(project=level1_project, file_name=level1_file, urn="urn:level1:end", element_path=l1_end_path)],
            [ResolvedUrn(project=level2_project, file_name=level2_file, urn="urn:level2:start", element_path=l2_start_path)],
            [ResolvedUrn(project=level2_project, file_name=level2_file, urn="urn:level2:end", element_path=l2_end_path)]
        ]

        # Compute paths for main file elements
        start_path = self._get_element_path(main_xml_content, "urn:main-start")
        end_path = self._get_element_path(main_xml_content, "urn:main-end")

        # Process the main file with mocked parse_xml
        with patch.object(self.linear_data.xml_cache, 'parse_xml', side_effect=mock_parse_xml):
            processor = InlineCompilerProcessor(main_project, main_file, start_path, end_path, linear_data=self.linear_data)
            result = processor.process()

        self.assertEqual(result.tag, "{http://jewishliturgy.org/ns/processing}transcludeInline")

        # The main text comes before and after the transclusion, in document order
        self.assertIn("Text before transclusion", result.text)
        all_text = "".join(result.itertext())
        self.assertLess(all_text.index("Text before transclusion"), all_text.index("Level 1 start"))
        self.assertLess(all_text.index("Level 1 end"), all_text.index("Text after transclusion"))

        # Find the top-level p:transclude element (from main file's transclusion)
        top_transclude = result.findall(".//{http://jewishliturgy.org/ns/processing}transclude")
        self.assertEqual(len(top_transclude), 2)  # One from level1, one nested from level2

        # The first p:transclude should be from the main file's transclusion to level1
        level1_transclude = top_transclude[0]
        self.assertEqual(level1_transclude.get('target'), 'urn:level1:start')
        self.assertEqual(level1_transclude.get('targetEnd'), 'urn:level1:end')
        self.assertEqual(level1_transclude.get('type'), 'inline')

        # Level 1 text should be in the first p:transclude element
        level1_text = "".join(level1_transclude.itertext())
        self.assertLess(level1_text.index("Level 1 start"), level1_text.index("Level 2 start"))
        self.assertLess(level1_text.index("Level 2 end"), level1_text.index("Level 1 end"))

        # The nested p:transclude (from level1's transclusion to level2) should also be present
        # Find it as a child of the first transclude
        nested_transclude = level1_transclude.findall(".//{http://jewishliturgy.org/ns/processing}transclude")
        self.assertEqual(len(nested_transclude), 1)

        level2_transclude = nested_transclude[0]
        self.assertEqual(level2_transclude.get('target'), 'urn:level2:start')
        self.assertEqual(level2_transclude.get('targetEnd'), 'urn:level2:end')
        # Even though the original j:transclude was type="external", InlineCompilerProcessor
        # should convert it to type="inline" because of the type_override
        self.assertEqual(level2_transclude.get('type'), 'inline')

        # Level 2 text should be in the nested p:transclude element
        self.assertIn("Level 2 start", level2_transclude.text)
        self.assertIn("Level 2 middle", level2_transclude.text)
        self.assertIn("Level 2 end", level2_transclude.text)

    @patch('opensiddur.exporter.urn.UrnResolver.resolve_range')
    def test_inline_transclusion_language_differences(self, mock_resolve_range):
        """Test that InlineCompilerProcessor adds xml:lang when transcluding text with a different language."""
        # Main file with English default
        main_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="en">
    <tei:div>
        <tei:p>English text before transclusion</tei:p>
        <j:transclude target="urn:hebrew:start" targetEnd="urn:hebrew:end" type="inline"/>
        <tei:p>English text after transclusion</tei:p>
    </tei:div>
</root>'''

        # Transcluded file with Hebrew default
        transcluded_xml_content = '''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="he">
    <tei:div>
        <tei:p>טקסט בעברית לפני</tei:p>
        <tei:p corresp="urn:hebrew:start">טקסט בעברית בהתחלה</tei:p>
        <tei:p>טקסט בעברית באמצע</tei:p>
        <tei:p corresp="urn:hebrew:end">טקסט בעברית בסוף</tei:p>
        <tei:p>טקסט בעברית אחרי</tei:p>
    </tei:div>
</root>'''

        # Set up files
        main_project, main_file = self._create_test_file("main.xml", main_xml_content)
        trans_project, trans_file = self._create_test_file("transcluded.xml", transcluded_xml_content.encode('utf-8'))

        # Parse the transcluded XML tree
        transcluded_tree_root = etree.fromstring(transcluded_xml_content.encode('utf-8'))

        # Mock XMLCache.parse_xml
        original_parse_xml = self.linear_data.xml_cache.parse_xml

        def mock_parse_xml(*args, **kwargs):
            if len(args) == 2 and args[0] == main_project and args[1] == main_file:
                # Main file - call original
                return original_parse_xml(*args, **kwargs)
            elif len(args) == 2 and args[0] == trans_project and args[1] == trans_file:
                # Transcluded file - return mocked tree
                mock_tree = MagicMock()
                mock_tree.getroot.return_value = transcluded_tree_root
                return mock_tree
            else:
                return original_parse_xml(*args, **kwargs)

        # Mock URN resolution
        mock_resolve_range.side_effect = [
            [ResolvedUrn(project=trans_project, file_name=trans_file, urn="urn:hebrew:start", element_path="/root/div[1]")],
            [ResolvedUrn(project=trans_project, file_name=trans_file, urn="urn:hebrew:end", element_path="/root/div[1]")]
        ]

        # Compute paths from the transcluded file
        transcluded_xml_bytes = transcluded_xml_content.encode('utf-8')
        start_path = self._get_element_path(transcluded_xml_bytes, "urn:hebrew:start")
        end_path = self._get_element_path(transcluded_xml_bytes, "urn:hebrew:end")

        # Process with InlineCompilerProcessor with mocked parse_xml
        with patch.object(self.linear_data.xml_cache, 'parse_xml', side_effect=mock_parse_xml):
            processor = InlineCompilerProcessor(trans_project, trans_file, start_path, end_path, linear_data=self.linear_data)
            result = processor.process()

        # Result should be a p:transcludeInline element with xml:lang="he"
        self.assertEqual(result.tag, "{http://jewishliturgy.org/ns/processing}transcludeInline")

        # Should have xml:lang="he" because the transcluded content is Hebrew
        transclude_lang = result.get('{http://www.w3.org/XML/1998/namespace}lang')
        self.assertEqual(transclude_lang, 'he', "p:transcludeInline should have xml:lang='he'")

    @patch('opensiddur.exporter.urn.UrnResolver.resolve_range')
    def test_inline_transclusion_language_change_in_middle(self, mock_resolve_range):
        """Test that InlineCompilerProcessor includes p:transcludeInline when language changes mid-text."""
        # Main file with English default
        main_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="en">
    <tei:div>
        <j:transclude target="urn:start" targetEnd="urn:end" type="inline"/>
    </tei:div>
</root>'''

        # Transcluded file with mixed languages (English default, Hebrew in middle)
        transcluded_xml_content = '''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="en">
    <tei:div>
        <tei:p corresp="urn:start">English text at start</tei:p>
        <tei:p xml:lang="he">טקסט בעברית באמצע</tei:p>
        <tei:p>English text after Hebrew</tei:p>
        <tei:p corresp="urn:end">English text at end</tei:p>
    </tei:div>
</root>'''

        # Set up files
        main_project, main_file = self._create_test_file("main.xml", main_xml_content)
        trans_project, trans_file = self._create_test_file("transcluded.xml", transcluded_xml_content.encode('utf-8'))

        # Parse the transcluded XML tree
        transcluded_tree_root = etree.fromstring(transcluded_xml_content.encode('utf-8'))

        # Mock XMLCache.parse_xml
        original_parse_xml = self.linear_data.xml_cache.parse_xml

        def mock_parse_xml(*args, **kwargs):
            if len(args) == 2 and args[0] == main_project and args[1] == main_file:
                # Main file - call original
                return original_parse_xml(*args, **kwargs)
            elif len(args) == 2 and args[0] == trans_project and args[1] == trans_file:
                # Transcluded file - return mocked tree
                mock_tree = MagicMock()
                mock_tree.getroot.return_value = transcluded_tree_root
                return mock_tree
            else:
                return original_parse_xml(*args, **kwargs)

        # Mock URN resolution
        mock_resolve_range.side_effect = [
            [ResolvedUrn(project=trans_project, file_name=trans_file, urn="urn:start", element_path="/root/div[1]")],
            [ResolvedUrn(project=trans_project, file_name=trans_file, urn="urn:end", element_path="/root/div[1]")]
        ]

        # Compute paths from the transcluded file
        transcluded_xml_bytes = transcluded_xml_content.encode('utf-8')
        start_path = self._get_element_path(transcluded_xml_bytes, "urn:start")
        end_path = self._get_element_path(transcluded_xml_bytes, "urn:end")

        # Process with InlineCompilerProcessor with mocked parse_xml
        with patch.object(self.linear_data.xml_cache, 'parse_xml', side_effect=mock_parse_xml):
            processor = InlineCompilerProcessor(trans_project, trans_file, start_path, end_path, linear_data=self.linear_data)
            result = processor.process()

        # Result should be a p:transcludeInline element
        self.assertEqual(result.tag, "{http://jewishliturgy.org/ns/processing}transcludeInline")

        # Should have a nested p:transcludeInline for the Hebrew section
        nested_transclude = result.findall(".//{http://jewishliturgy.org/ns/processing}transcludeInline")
        self.assertGreater(len(nested_transclude), 0, "Should have at least one nested p:transcludeInline for Hebrew")

        # Find the nested p:transcludeInline and check it has xml:lang="he"
        hebrew_transclude = None
        for elem in nested_transclude:
            if elem != result:  # Not the root one
                hebrew_lang = elem.get('{http://www.w3.org/XML/1998/namespace}lang')
                if hebrew_lang == 'he':
                    hebrew_transclude = elem
                    break

        self.assertIsNotNone(hebrew_transclude, "Should have a nested p:transcludeInline with xml:lang='he'")
        self.assertEqual(hebrew_transclude.get('{http://www.w3.org/XML/1998/namespace}lang'), 'he')

    @patch('opensiddur.exporter.urn.UrnResolver.resolve_range')
    def test_milestone_transclusion_includes_start_excludes_end(self, mock_resolve_range):
        """Test transclusion using milestone elements includes start milestone but not end milestone."""
        # Main file that transcludes verse 3 from external file
        main_xml_content = b'''<tei:text xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="en">
    <tei:div>
        <tei:p>Before transclusion</tei:p>
        <j:transclude target="urn:x-opensiddur:text:bible:book/1/3" type="external"/>
        <tei:p>After transclusion</tei:p>
    </tei:div>
</tei:text>'''

        # External file with milestone-style verse markers
        external_xml_content = '''<tei:text xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="he">
    <tei:div>
        Text before verse 3
        <tei:milestone type="verse" corresp="urn:x-opensiddur:text:bible:book/1/2"/>
        Verse 2 text
        <tei:milestone type="verse" corresp="urn:x-opensiddur:text:bible:book/1/3"/>
        Verse 3 text part 1
        <tei:choice>
            <tei:abbr>abbr</tei:abbr>
            <tei:expan>abbreviation</tei:expan>
        </tei:choice>
        Verse 3 text part 2
        <tei:milestone type="verse" corresp="urn:x-opensiddur:text:bible:book/1/4"/>
        Verse 4 text
        <tei:milestone type="verse" corresp="urn:x-opensiddur:text:bible:book/1/5"/>
        Verse 5 text
    </tei:div>
</tei:text>'''

        # Set up files
        main_project, main_file = self._create_test_file("main.xml", main_xml_content)
        ext_project, ext_file = self._create_test_file("external.xml", external_xml_content.encode('utf-8'))

        # Parse the external XML tree
        external_tree_root = etree.fromstring(external_xml_content.encode('utf-8'))

        # Mock XMLCache.parse_xml
        original_parse_xml = self.linear_data.xml_cache.parse_xml

        def mock_parse_xml(*args, **kwargs):
            if len(args) == 2 and args[0] == ext_project and args[1] == ext_file:
                # External file - return mocked tree
                mock_tree = MagicMock()
                mock_tree.getroot.return_value = external_tree_root
                return mock_tree
            else:
                return original_parse_xml(*args, **kwargs)

        # Mock URN resolution for milestones
        mock_resolve_range.side_effect = [
            [ResolvedUrn(project=ext_project, file_name=ext_file, urn="urn:x-opensiddur:text:bible:book/1/3", element_path="/root/div[1]/milestone[2]")],
            [ResolvedUrn(project=ext_project, file_name=ext_file, urn="urn:x-opensiddur:text:bible:book/1/3", element_path="/root/div[1]/milestone[2]")]
        ]

        # Compute paths for the milestone element and its end
        ext_xml_bytes = external_xml_content.encode('utf-8')
        ext_root = etree.fromstring(ext_xml_bytes)
        ext_tree = ext_root.getroottree()
        milestone_elem = ext_root.xpath("//*[@corresp='urn:x-opensiddur:text:bible:book/1/3']")[0]
        from_start = ext_tree.getpath(milestone_elem)
        end_element_path, include_tail = find_end_of_mapping(milestone_elem)

        # Process with InlineCompilerProcessor with mocked parse_xml
        with patch.object(self.linear_data.xml_cache, 'parse_xml', side_effect=mock_parse_xml):
            processor = InlineCompilerProcessor(ext_project, ext_file, from_start, end_element_path, include_tail_after_end=include_tail, linear_data=self.linear_data)
            result = processor.process()


        # Convert result to string for easier inspection
        result_str = etree.tostring(result, encoding='unicode')


        # Should include all text between the milestones
        self.assertIn("Verse 3 text part 1", result_str, "Should include verse 3 part 1")
        self.assertIn("Verse 3 text part 2", result_str, "Should include verse 3 part 2")
        self.assertIn("abbr", result_str, "Default reading retains the printed abbreviation")
        self.assertNotIn("abbreviation", result_str, "Default reading excludes the expansion")

        # Should not include the choice element
        # self.assertIn("<tei:choice", result_str, "Should include the choice element")

        # Should NOT include text before verse 3
        self.assertNotIn("Text before verse 3", result_str, "Should not include text before verse 3")
        self.assertNotIn("Verse 2 text", result_str, "Should not include verse 2")

        # Should NOT include text after verse 3 (including verse 4 and 5)
        self.assertNotIn("Verse 4 text", result_str, "Should not include verse 4")
        self.assertNotIn("Verse 5 text", result_str, "Should not include verse 5")

        # Should NOT include the first milestone (verse 2)
        self.assertNotIn('corresp="urn:x-opensiddur:text:bible:book/1/2"', result_str,
                        "Should not include verse 2 milestone")

        # Should NOT include the fifth milestone (verse 5)
        self.assertNotIn('corresp="urn:x-opensiddur:text:bible:book/1/5"', result_str,
                        "Should not include verse 5 milestone")


    @patch('opensiddur.exporter.urn.UrnResolver.resolve_range')
    def test_milestone_transclusion_works_even_if_there_is_no_end_milestone(self, mock_resolve_range):
        """Test transclusion using milestone elements includes start milestone but not end milestone."""
        # Main file that transcludes verse 3 from external file
        main_xml_content = b'''<tei:text xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="en">
    <tei:div>
        <tei:p>Before transclusion</tei:p>
        <j:transclude target="urn:x-opensiddur:text:bible:book/1/3" type="external"/>
        <tei:p>After transclusion</tei:p>
    </tei:div>
</tei:text>'''

        # External file with milestone-style verse markers
        external_xml_content = '''<tei:text xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="he">
    <tei:div>
        Text before verse 3
        <tei:milestone type="verse" corresp="urn:x-opensiddur:text:bible:book/1/2"/>
        Verse 2 text
        <tei:milestone type="verse" corresp="urn:x-opensiddur:text:bible:book/1/3"/>
        Verse 3 text part 1
        <tei:choice>
            <tei:abbr>abbr</tei:abbr>
            <tei:expan>abbreviation</tei:expan>
        </tei:choice>
        Verse 3 text part 2
    </tei:div>
    Higher level text
</tei:text>'''

        # Set up files
        main_project, main_file = self._create_test_file("main.xml", main_xml_content)
        ext_project, ext_file = self._create_test_file("external.xml", external_xml_content.encode('utf-8'))

        # Parse the external XML tree
        external_tree_root = etree.fromstring(external_xml_content.encode('utf-8'))

        # Mock XMLCache.parse_xml
        original_parse_xml = self.linear_data.xml_cache.parse_xml

        def mock_parse_xml(*args, **kwargs):
            if len(args) == 2 and args[0] == ext_project and args[1] == ext_file:
                # External file - return mocked tree
                mock_tree = MagicMock()
                mock_tree.getroot.return_value = external_tree_root
                return mock_tree
            else:
                return original_parse_xml(*args, **kwargs)

        # Mock URN resolution for milestones
        mock_resolve_range.side_effect = [
            [ResolvedUrn(project=ext_project, file_name=ext_file, urn="urn:x-opensiddur:text:bible:book/1/3", element_path="/root/div[1]/milestone[2]")],
        ]

        # Compute paths for the milestone element and its end
        ext_xml_bytes = external_xml_content.encode('utf-8')
        ext_root = etree.fromstring(ext_xml_bytes)
        ext_tree = ext_root.getroottree()
        milestone_elem = ext_root.xpath("//*[@corresp='urn:x-opensiddur:text:bible:book/1/3']")[0]
        from_start = ext_tree.getpath(milestone_elem)
        end_element_path, include_tail = find_end_of_mapping(milestone_elem)

        # Process with InlineCompilerProcessor with mocked parse_xml
        with patch.object(self.linear_data.xml_cache, 'parse_xml', side_effect=mock_parse_xml):
            processor = InlineCompilerProcessor(ext_project, ext_file, from_start, end_element_path, include_tail_after_end=include_tail, linear_data=self.linear_data)
            result = processor.process()

        # Convert result to string for easier inspection
        result_str = etree.tostring(result, encoding='unicode')

        # Should include all text between the milestones
        self.assertIn("Verse 3 text part 1", result_str, "Should include verse 3 part 1")
        self.assertIn("Verse 3 text part 2", result_str, "Should include verse 3 part 2")
        self.assertIn("abbr", result_str, "Default reading retains the printed abbreviation")
        self.assertNotIn("abbreviation", result_str, "Default reading excludes the expansion")

        # Should not include the choice element
        # self.assertIn("<tei:choice", result_str, "Should include the choice element")

        # Should NOT include text before verse 3
        self.assertNotIn("Text before verse 3", result_str, "Should not include text before verse 3")
        self.assertNotIn("Verse 2 text", result_str, "Should not include verse 2")

        # Should NOT include the first milestone (verse 2)
        self.assertNotIn('corresp="urn:x-opensiddur:text:bible:book/1/2"', result_str,
                        "Should not include verse 2 milestone")

        # Should NOT include the fifth milestone (verse 5)
        self.assertNotIn('Higher level', result_str,
                        "Should not include anything in higher levels")

    @patch('opensiddur.exporter.urn.UrnResolver.resolve_range')
    def test_milestone_transclusion_works_when_the_end_is_the_next_unit(self, mock_resolve_range):
        """Test transclusion using milestone elements includes start milestone but not end milestone."""
        # Main file that transcludes verse 3 from external file
        main_xml_content = b'''<tei:text xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="en">
    <tei:div>
        <tei:p>Before transclusion</tei:p>
        <j:transclude target="urn:x-opensiddur:text:bible:book/1/3" type="external"/>
        <tei:p>After transclusion</tei:p>
    </tei:div>
</tei:text>'''

        # External file with milestone-style verse markers
        external_xml_content = '''<tei:text xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="he">
    <tei:div>
        <tei:milestone type="chapter" corresp="urn:x-opensiddur:text:bible:book/1"/>
        Text before verse 3
        <tei:milestone type="verse" corresp="urn:x-opensiddur:text:bible:book/1/2"/>
        Verse 2 text
        <tei:milestone type="verse" corresp="urn:x-opensiddur:text:bible:book/1/3"/>
        Verse 3 text part 1
        <tei:choice>
            <tei:abbr>abbr</tei:abbr>
            <tei:expan>abbreviation</tei:expan>
        </tei:choice>
        Verse 3 text part 2
        <tei:milestone type="chapter" corresp="urn:x-opensiddur:text:bible:book/2"/>
        Chapter 2 text
    </tei:div>
    Higher level text
</tei:text>'''

        # Set up files
        main_project, main_file = self._create_test_file("main.xml", main_xml_content)
        ext_project, ext_file = self._create_test_file("external.xml", external_xml_content.encode('utf-8'))

        # Parse the external XML tree
        external_tree_root = etree.fromstring(external_xml_content.encode('utf-8'))

        # Mock XMLCache.parse_xml
        original_parse_xml = self.linear_data.xml_cache.parse_xml

        def mock_parse_xml(*args, **kwargs):
            if len(args) == 2 and args[0] == ext_project and args[1] == ext_file:
                # External file - return mocked tree
                mock_tree = MagicMock()
                mock_tree.getroot.return_value = external_tree_root
                return mock_tree
            else:
                return original_parse_xml(*args, **kwargs)

        # Mock URN resolution for milestones
        mock_resolve_range.side_effect = [
            [ResolvedUrn(project=ext_project, file_name=ext_file, urn="urn:x-opensiddur:text:bible:book/1/3", element_path="/root/div[1]/milestone[2]")],
        ]

        # Compute paths for the milestone element and its end
        ext_xml_bytes = external_xml_content.encode('utf-8')
        ext_root = etree.fromstring(ext_xml_bytes)
        ext_tree = ext_root.getroottree()
        milestone_elem = ext_root.xpath("//*[@corresp='urn:x-opensiddur:text:bible:book/1/3']")[0]
        from_start = ext_tree.getpath(milestone_elem)
        end_element_path, include_tail = find_end_of_mapping(milestone_elem)

        # Process with InlineCompilerProcessor with mocked parse_xml
        with patch.object(self.linear_data.xml_cache, 'parse_xml', side_effect=mock_parse_xml):
            processor = InlineCompilerProcessor(ext_project, ext_file, from_start, end_element_path, include_tail_after_end=include_tail, linear_data=self.linear_data)
            result = processor.process()

        # Convert result to string for easier inspection
        result_str = etree.tostring(result, encoding='unicode')

        # Should include all text between the milestones
        self.assertIn("Verse 3 text part 1", result_str, "Should include verse 3 part 1")
        self.assertIn("Verse 3 text part 2", result_str, "Should include verse 3 part 2")
        self.assertIn("abbr", result_str, "Default reading retains the printed abbreviation")
        self.assertNotIn("abbreviation", result_str, "Default reading excludes the expansion")

        # Should not include the choice element
        # self.assertIn("<tei:choice", result_str, "Should include the choice element")

        # Should NOT include text before verse 3
        self.assertNotIn("Text before verse 3", result_str, "Should not include text before verse 3")
        self.assertNotIn("Verse 2 text", result_str, "Should not include verse 2")

        # Should NOT include the first milestone (verse 2)
        self.assertNotIn('corresp="urn:x-opensiddur:text:bible:book/1/2"', result_str,
                        "Should not include verse 2 milestone")

        # Should NOT include the chapter milestone (chap 2)
        self.assertNotIn('corresp="urn:x-opensiddur:text:bible:book/2', result_str,
                        "Should not include the next chapter")
        # Should not include the chapter 2 text
        self.assertNotIn("Chapter 2 text", result_str, "Should not include the chapter 2 text")

    def test_comment_contributes_no_text_and_keeps_its_tail(self):
        """A comment is dropped; the text following it stays in the inline text (#41)."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:div>
        <tei:p corresp="urn:start">First<!-- an editorial remark --> paragraph</tei:p>
        <tei:p corresp="urn:end">Last paragraph</tei:p>
    </tei:div>
</root>'''

        project, file_name = self._create_test_file("comment_inline.xml", xml_content)

        start_path = self._get_element_path(xml_content, "urn:start")
        end_path = self._get_element_path(xml_content, "urn:end")
        processor = InlineCompilerProcessor(
            project, file_name, start_path, end_path, linear_data=self.linear_data)
        result = processor.process()

        result_str = etree.tostring(result, encoding='unicode')
        self.assertNotIn('an editorial remark', result_str)
        self.assertIn('First', result.text)
        self.assertIn('paragraph', result.text)
        self.assertIn('Last paragraph', result.text)


class TestInlineCompilerProcessorAnnotations(unittest.TestCase):
    """Test annotation inclusion functionality in InlineCompilerProcessor."""

    def setUp(self):
        """Set up test fixtures and reset linear data."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_project_dir = Path(self.temp_dir.name) / "test_project"
        self.test_project_dir.mkdir(parents=True)

        # Create priority project directory
        self.priority_project_dir = Path(self.temp_dir.name) / "priority_project"
        self.priority_project_dir.mkdir(parents=True)

        # Patch the xml_cache base_path to use our temp directory
        self.linear_data = LinearData(
            instruction_priority=["priority_project", "test_project"],
            annotation_projects=["priority_project", "test_project"]
        )
        self.linear_data.xml_cache.base_path = Path(self.temp_dir.name)

        self.refdb = MagicMock(spec=ReferenceDatabase)
        # Each test needs to set its own refdb results

    def _create_test_file(self, project: str, file_name: str, content: bytes) -> tuple[str, str, etree._ElementTree]:
        """Create a test XML file and return (project, file_name, tree) tuple."""
        project_dir = Path(self.temp_dir.name) / project
        project_dir.mkdir(parents=True, exist_ok=True)
        file_path = project_dir / file_name
        with open(file_path, 'wb') as f:
            f.write(content)
        xml = etree.parse(file_path)
        return project, file_name, xml

    def _get_element_path(self, xml_content: bytes, identifier: str) -> str:
        """Get the XPath path for an element identified by corresp or xml:id.

        Args:
            xml_content: The XML content as bytes
            identifier: Either a corresp value (e.g. 'urn:start') or an xml:id reference (e.g. '#target')

        Returns:
            The absolute XPath path for the element
        """
        root = etree.fromstring(xml_content)
        tree = root.getroottree()
        xml_ns = 'http://www.w3.org/XML/1998/namespace'
        if identifier.startswith('#'):
            xml_id = identifier[1:]
            elements = root.xpath(f"//*[@xml:id='{xml_id}']", namespaces={'xml': xml_ns})
        else:
            elements = root.xpath(f"//*[@corresp='{identifier}']")
        if not elements:
            raise ValueError(f"Element with identifier '{identifier}' not found in XML")
        return tree.getpath(elements[0])

    def _create_file_with_element_for_annotation(self, project: str, file_name: str,
                                                   start_urn: str, end_urn: str,
                                                   element_with_note: str = "") -> tuple[str, str]:
        """Create a file with elements that can be targeted for annotation."""
        xml_content = f'''<TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    <tei:teiHeader>
        <tei:fileDesc>
            <tei:titleStmt>
                <tei:title>Test Document</tei:title>
            </tei:titleStmt>
        </tei:fileDesc>
    </tei:teiHeader>
    <tei:text>
        <tei:body>
            <tei:div>
                <tei:p>Before start</tei:p>
                <tei:p corresp="{start_urn}">Start element</tei:p>
                Before the note.
                {element_with_note}
                After the note.
                <tei:p corresp="{end_urn}">End element</tei:p>
                <tei:p>After end</tei:p>
            </tei:div>
        </tei:body>
    </tei:text>
    <tei:standOff>
    </tei:standOff>
</TEI>'''.encode('utf-8')
        return self._create_test_file(project, file_name, xml_content)

    def _create_note_file(self, project: str, file_name: str, target_urn: str,
                          note_content: str, note_type: str = "editorial") -> tuple[str, str, etree._ElementTree]:
        """Create a file with an editorial or instructional note."""
        if note_type == "instructional":
            xml_content = f'''<TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    <tei:teiHeader>
        <tei:fileDesc>
            <tei:titleStmt>
                <tei:title>Note Document</tei:title>
            </tei:titleStmt>
        </tei:fileDesc>
    </tei:teiHeader>
    <tei:text>
        <tei:body>
            <tei:div>
                <tei:note type="instruction" corresp="{target_urn}">
                    {note_content}
                </tei:note>
            </tei:div>
        </tei:body>
    </tei:text>
</TEI>'''.encode('utf-8')
        else:  # editorial
            xml_content = f'''<TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    <tei:teiHeader>
        <tei:fileDesc>
            <tei:titleStmt>
                <tei:title>Note Document</tei:title>
            </tei:titleStmt>
        </tei:fileDesc>
    </tei:teiHeader>
    <tei:standOff>
        <tei:note type="editorial" target="{target_urn}">
            {note_content}
        </tei:note>
    </tei:standOff>
</TEI>'''.encode('utf-8')
        return self._create_test_file(project, file_name, xml_content)

    def test_editorial_note_in_range(self):
        """Test that an editorial note targeting an element within the range is included."""
        start_urn = "urn:test:start"
        end_urn = "urn:test:end"
        target_urn = "urn:test:target"

        # Create main file with element that has a corresp and falls within range
        project, file_name, _ = self._create_file_with_element_for_annotation(
            "test_project", "main.xml", start_urn, end_urn,
            f'<tei:p corresp="{target_urn}">Targeted element</tei:p>'
        )

        # Create note file with editorial note
        note_project, note_file, note_tree = self._create_note_file(
            "test_project", "notes.xml", target_urn, "This is an editorial note", "editorial"
        )

        # Get the note element from the tree
        ns = {'tei': 'http://www.tei-c.org/ns/1.0'}
        note_element = note_tree.xpath('//tei:note[@type="editorial"]', namespaces=ns)[0]
        note_path = note_element.getroottree().getpath(note_element)

        # Mock the reference database to return the note
        mock_reference = Reference(
            project=note_project,
            file_name=note_file,
            element_path=note_path,
            element_tag="{http://www.tei-c.org/ns/1.0}note",
            element_type=None,
            target_start=target_urn,
            target_end=None,
            target_is_id=False,
            corresponding_urn=target_urn
        )
        # 3 urns: start, target, end
        self.refdb.get_references_to.side_effect = [[], [mock_reference], []]

        # Read back the XML content to compute paths
        project_dir = Path(self.temp_dir.name) / project
        xml_bytes = (project_dir / file_name).read_bytes()
        start_path = self._get_element_path(xml_bytes, start_urn)
        end_path = self._get_element_path(xml_bytes, end_urn)

        # Process with InlineCompilerProcessor
        processor = InlineCompilerProcessor(
            project, file_name, start_path, end_path,
            linear_data=self.linear_data,
            reference_database=self.refdb
        )
        result = processor.process()

        # The note should be inserted before the targeted element (which is within the range)
        # In InlineCompilerProcessor, the note gets inserted into the inline text result
        # Since the targeted element is within the range, the note should appear in the result
        notes = result.xpath(".//tei:note[@type='editorial']", namespaces=ns)
        # Should find at least one editorial note (the one targeting the element in the range)
        self.assertEqual(len(notes), 1, "Should find one editorial note")
        # At least one of the notes should be the one we created
        note = notes[0]
        note_texts = note.text.strip()
        self.assertIn("This is an editorial note", note_texts)
        self.assertIn("After the note.", note.tail.strip())
        self.assertIn("Before the note.", note.getparent().text.strip())


    def test_instructional_note_in_range(self):
        """Test that an instructional note within the range is included."""
        start_urn = "urn:test:start"
        end_urn = "urn:test:end"
        ns = {'tei': 'http://www.tei-c.org/ns/1.0'}
        # Create main file with element that has a corresp and falls within range
        project, file_name, _ = self._create_file_with_element_for_annotation(
            "test_project", "main.xml", start_urn, end_urn,
            '<tei:note type="instruction">Inline instruction note</tei:note>'
        )

        self.refdb.get_references_to.return_value = []

        # Read back the XML content to compute paths
        project_dir = Path(self.temp_dir.name) / project
        xml_bytes = (project_dir / file_name).read_bytes()
        start_path = self._get_element_path(xml_bytes, start_urn)
        end_path = self._get_element_path(xml_bytes, end_urn)

        # Process with InlineCompilerProcessor
        processor = InlineCompilerProcessor(
            project, file_name, start_path, end_path,
            linear_data=self.linear_data,
            reference_database=self.refdb
        )
        result = processor.process()

        # The note should be inserted before the targeted element (which is within the range)
        # In InlineCompilerProcessor, the note gets inserted into the inline text result
        # Since the targeted element is within the range, the note should appear in the result
        notes = result.xpath(".//tei:note[@type='instruction']", namespaces=ns)
        # Should find exactly one note
        self.assertEqual(len(notes), 1, "Should find one inline instruction note")

        note = notes[0]
        note_texts = note.text.strip()
        self.assertIn("Inline instruction note", note_texts)
        self.assertIn("After the note.", note.tail.strip())
        self.assertIn("Before the note.", note.getparent().text.strip())


if __name__ == '__main__':
    unittest.main()
