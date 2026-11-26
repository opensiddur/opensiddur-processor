"""Tests for the CompilerProcessor class."""

import re
from typing import Optional
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from lxml import etree
from opensiddur.exporter.compiler import CompilerProcessor, JLPTEI_NAMESPACE
from opensiddur.exporter.external_compiler import ExternalCompilerProcessor
from opensiddur.exporter.inline_compiler import InlineCompilerProcessor
from opensiddur.exporter.linear import LinearData, reset_linear_data, get_linear_data
from opensiddur.exporter.refdb import Reference, ReferenceDatabase, UrnMapping
from opensiddur.exporter.urn import ResolvedUrn, ResolvedUrnRange, split_range


class TestCompilerProcessorWithFiles(unittest.TestCase):
    """Test CompilerProcessor with file-based input (no transclusions, no start/end)."""

    def setUp(self):
        """Set up test fixtures and reset linear data."""
        reset_linear_data()
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_project_dir = Path(self.temp_dir.name) / "test_project"
        self.test_project_dir.mkdir(parents=True)
        
        # Patch the xml_cache base_path to use our temp directory
        linear_data = get_linear_data()
        linear_data.xml_cache.base_path = Path(self.temp_dir.name)

    def _create_test_file(self, file_name: str, content: bytes) -> tuple[str, str]:
        """Create a test XML file and return (project, file_name) tuple."""
        file_path = self.test_project_dir / file_name
        with open(file_path, 'wb') as f:
            f.write(content)
        return "test_project", file_name

    def test_process_simple_xml_file(self):
        """Test processing a simple XML file with no transclusions."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:div>
        <tei:p>Simple text content</tei:p>
    </tei:div>
</root>'''
        
        project, file_name = self._create_test_file("simple.xml", xml_content)
        
        processor = CompilerProcessor(project, file_name)
        result = processor.process()
        
        # Convert to string for comparison
        result_str = etree.tostring(result, encoding='unicode')
        
        # Should preserve namespace prefixes
        self.assertIn('xmlns:tei="http://www.tei-c.org/ns/1.0"', result_str)
        self.assertIn('<tei:div>', result_str)
        self.assertIn('<tei:p>', result_str)
        self.assertIn('Simple text content', result_str)
        
        # Should add processing namespace
        self.assertIn('xmlns:p="http://jewishliturgy.org/ns/processing"', result_str)
        
        # Verify structure is preserved
        self.assertIn('<tei:div>', result_str)
        self.assertIn('</tei:div>', result_str)

    def test_process_preserves_multiple_namespaces(self):
        """Test that processing preserves multiple namespace prefixes."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    <tei:text>
        <tei:body>
            <tei:div>
                <tei:p>TEI content</tei:p>
                <j:milestone unit="verse"/>
            </tei:div>
        </tei:body>
    </tei:text>
</root>'''
        
        project, file_name = self._create_test_file("multi_ns.xml", xml_content)
        
        processor = CompilerProcessor(project, file_name)
        result = processor.process()
        
        result_str = etree.tostring(result, encoding='unicode')
        
        # Should preserve both namespace prefixes
        self.assertIn('xmlns:tei="http://www.tei-c.org/ns/1.0"', result_str)
        self.assertIn('xmlns:j="http://jewishliturgy.org/ns/jlptei/2"', result_str)
        self.assertIn('<tei:text>', result_str)
        self.assertIn('<tei:body>', result_str)
        self.assertIn('<j:milestone', result_str)
        
        # Verify content is preserved
        self.assertIn('TEI content', result_str)

    def test_process_preserves_attributes(self):
        """Test that processing preserves element attributes."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:div type="chapter" n="1" xml:id="ch1">
        <tei:p rend="italic">Italic text</tei:p>
    </tei:div>
</root>'''
        
        project, file_name = self._create_test_file("attributes.xml", xml_content)
        
        processor = CompilerProcessor(project, file_name)
        result = processor.process()
        
        result_str = etree.tostring(result, encoding='unicode')
        
        # Should preserve all attributes
        self.assertIn('type="chapter"', result_str)
        self.assertIn('n="1"', result_str)
        # xml:id should be rewritten with hash
        self.assertTrue('xml:id="ch1_' in result_str, f"Expected rewritten xml:id, got: {result_str}")
        self.assertIn('rend="italic"', result_str)

    def test_process_preserves_tail_text(self):
        """Test that processing preserves tail text."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:div>Content</tei:div>Tail text after div
    <tei:p>Paragraph</tei:p>More tail
</root>'''
        
        project, file_name = self._create_test_file("tail.xml", xml_content)
        
        processor = CompilerProcessor(project, file_name)
        result = processor.process()
        
        result_str = etree.tostring(result, encoding='unicode')
        
        # Should preserve tail text
        self.assertIn('Tail text after div', result_str)
        self.assertIn('More tail', result_str)

    def test_process_empty_elements(self):
        """Test that processing preserves empty elements."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:div/>
    <tei:pb n="1"/>
    <tei:br/>
</root>'''
        
        project, file_name = self._create_test_file("empty.xml", xml_content)
        
        processor = CompilerProcessor(project, file_name)
        result = processor.process()
        
        result_str = etree.tostring(result, encoding='unicode')
        
        # Should preserve empty/self-closing elements
        self.assertIn('<tei:div/>', result_str)
        self.assertIn('<tei:pb', result_str)
        self.assertIn('n="1"', result_str)
        self.assertIn('<tei:br/>', result_str)

    def test_process_complex_structure(self):
        """Test processing a complex XML structure."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    <tei:teiHeader>
        <tei:fileDesc>
            <tei:titleStmt>
                <tei:title>Test Document</tei:title>
            </tei:titleStmt>
        </tei:fileDesc>
    </tei:teiHeader>
    <tei:text>
        <tei:body>
            <tei:div type="chapter" n="1">
                <tei:p>First paragraph</tei:p>
                <j:milestone unit="verse" n="1"/>
                <tei:p>Second paragraph</tei:p>
            </tei:div>
        </tei:body>
    </tei:text>
</root>'''
        
        project, file_name = self._create_test_file("complex.xml", xml_content)
        
        processor = CompilerProcessor(project, file_name)
        result = processor.process()
        
        result_str = etree.tostring(result, encoding='unicode')
        
        # Should preserve all structure
        self.assertIn('<tei:teiHeader>', result_str)
        self.assertIn('<tei:fileDesc>', result_str)
        self.assertIn('<tei:titleStmt>', result_str)
        self.assertIn('<tei:title>', result_str)
        self.assertIn('Test Document', result_str)
        self.assertIn('<tei:text>', result_str)
        self.assertIn('<tei:body>', result_str)
        self.assertIn('<tei:div', result_str)
        self.assertIn('type="chapter"', result_str)
        self.assertIn('<j:milestone', result_str)
        self.assertIn('unit="verse"', result_str)
        self.assertIn('First paragraph', result_str)
        self.assertIn('Second paragraph', result_str)

    def test_process_namespace_declarations_only_at_root(self):
        """Test that namespace declarations are only at root, not duplicated."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    <tei:div>
        <tei:p>Content</tei:p>
        <j:milestone unit="verse"/>
    </tei:div>
    <tei:div>
        <tei:note>Note</tei:note>
    </tei:div>
</root>'''
        
        project, file_name = self._create_test_file("ns_decl.xml", xml_content)
        
        processor = CompilerProcessor(project, file_name)
        result = processor.process()
        
        result_str = etree.tostring(result, encoding='unicode')
        
        # Count namespace declarations - should only be at root
        tei_ns_count = result_str.count('xmlns:tei="http://www.tei-c.org/ns/1.0"')
        j_ns_count = result_str.count('xmlns:j="http://jewishliturgy.org/ns/jlptei/2"')
        
        self.assertEqual(tei_ns_count, 1, f"Expected exactly 1 TEI namespace declaration, found {tei_ns_count}")
        self.assertEqual(j_ns_count, 1, f"Expected exactly 1 J namespace declaration, found {j_ns_count}")
        
        # Verify child elements don't have namespace declarations
        self.assertNotIn('<tei:div xmlns:', result_str)
        self.assertNotIn('<tei:p xmlns:', result_str)
        self.assertNotIn('<j:milestone xmlns:', result_str)

    def test_process_with_unicode_content(self):
        """Test processing XML with Unicode content."""
        xml_content = '''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:div xml:lang="he">
        <tei:p>עברית Hebrew text</tei:p>
    </tei:div>
    <tei:div xml:lang="zh">
        <tei:p>中文 Chinese text</tei:p>
    </tei:div>
</root>'''.encode('utf-8')
        
        project, file_name = self._create_test_file("unicode.xml", xml_content)
        
        processor = CompilerProcessor(project, file_name)
        result = processor.process()
        
        result_str = etree.tostring(result, encoding='unicode')
        
        # Should preserve Unicode content
        self.assertIn('עברית', result_str)
        self.assertIn('中文', result_str)
        self.assertIn('Hebrew text', result_str)
        self.assertIn('Chinese text', result_str)

    def test_process_adds_processing_namespace(self):
        """Test that processing adds the processing namespace to root."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:div>
        <tei:p>Content</tei:p>
    </tei:div>
</root>'''
        
        project, file_name = self._create_test_file("processing_ns.xml", xml_content)
        
        processor = CompilerProcessor(project, file_name)
        result = processor.process()
        
        result_str = etree.tostring(result, encoding='unicode')
        
        # Should add processing namespace
        self.assertIn('xmlns:p="http://jewishliturgy.org/ns/processing"', result_str)

    def test_internal_transclusion_calls_inline_processor(self):
        """Test that CompilerProcessor calls InlineCompilerProcessor for inline transclusions."""
        from unittest.mock import patch, MagicMock
        
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" 
                               xmlns:jlp="http://jewishliturgy.org/ns/jlptei/2">
    <tei:div>
        <tei:p>Before transclusion</tei:p>
        <jlp:transclude target="#start" targetEnd="#end" type="inline"/>
        <tei:p>After transclusion</tei:p>
    </tei:div>
</root>'''
        
        project, file_name = self._create_test_file("inline_transclude.xml", xml_content)
        
        # Mock InlineCompilerProcessor
        with patch('opensiddur.exporter.inline_compiler.InlineCompilerProcessor') as MockInlineProcessor:
            # Create a mock instance and mock process() to return a simple element
            mock_instance = MagicMock()
            mock_result = etree.Element("{http://jewishliturgy.org/ns/processing}transcludeInline")
            mock_result.text = "transcluded content"
            mock_instance.process.return_value = mock_result
            # Mock _mark_file_source to return the element unchanged
            mock_instance._mark_file_source.return_value = mock_result
            mock_instance.project = "transcluded_project"
            mock_instance.file_name = "transcluded.xml"
            mock_instance.root_language = "xx"
            MockInlineProcessor.return_value = mock_instance
            
            # Mock UrnResolver methods to return resolved URNs
            from opensiddur.exporter.urn import ResolvedUrn, ResolvedUrnRange
            
            def mock_resolve_range(urn):
                return [ResolvedUrn(urn=urn, project=project, file_name=file_name, element_path="/TEI/div[1]")]
            
            def mock_prioritize_range(urns, priority_list, return_all=False):
                return urns[0] if urns else None
            
            with patch('opensiddur.exporter.compiler.UrnResolver.resolve_range', side_effect=mock_resolve_range):
                with patch('opensiddur.exporter.compiler.UrnResolver.prioritize_range', side_effect=mock_prioritize_range):
                    processor = CompilerProcessor(project, file_name)
                    processor.process()
            
            # Verify InlineCompilerProcessor was instantiated
            MockInlineProcessor.assert_called_once()
            call_args = MockInlineProcessor.call_args
            
            # Check the positional arguments: project, file_name
            self.assertEqual(call_args[0][0], project)  # project
            self.assertEqual(call_args[0][1], file_name)  # file_name
            
            # Check keyword arguments: from_start, to_end (now element paths from ResolvedUrn)
            self.assertEqual(call_args[1]['from_start'], "/TEI/div[1]")
            self.assertEqual(call_args[1]['to_end'], "/TEI/div[1]")
            self.assertIn('linear_data', call_args[1])

            # Verify process() was called
            mock_instance.process.assert_called_once()

    def test_external_transclusion_calls_external_processor(self):
        """Test that CompilerProcessor calls ExternalCompilerProcessor for external transclusions."""
        from unittest.mock import patch, MagicMock
        
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" 
                               xmlns:jlp="http://jewishliturgy.org/ns/jlptei/2">
    <tei:div>
        <tei:p>Before transclusion</tei:p>
        <jlp:transclude target="#start" targetEnd="#end" type="external"/>
        <tei:p>After transclusion</tei:p>
    </tei:div>
</root>'''
        
        project, file_name = self._create_test_file("external_transclude.xml", xml_content)
        
        # Mock ExternalCompilerProcessor
        with patch('opensiddur.exporter.external_compiler.ExternalCompilerProcessor') as MockExternalProcessor:
            # Create a mock instance and mock process() to return a list of elements
            mock_instance = MagicMock()
            mock_elem = etree.Element("{http://www.tei-c.org/ns/1.0}p")
            mock_elem.text = "transcluded content"
            mock_instance.process.return_value = [mock_elem]
            # Mock _mark_file_source to act like a passthrough
            def mock_mark_file_source(elem, **_):
                return elem
            mock_instance._mark_file_source.side_effect = mock_mark_file_source
            mock_instance.project = "transcluded_project"
            mock_instance.file_name = "transcluded.xml"
            mock_instance.root_language = "xx"
            MockExternalProcessor.return_value = mock_instance
            
            # Mock UrnResolver methods to return resolved URNs
            from opensiddur.exporter.urn import ResolvedUrn
            
            def mock_resolve_range(urn):
                return [ResolvedUrn(urn=urn, project=project, file_name=file_name, element_path="/TEI/div[1]")]
            
            def mock_prioritize_range(urns, priority_list, return_all=False):
                return urns[0] if urns else None
            
            with patch('opensiddur.exporter.compiler.UrnResolver.resolve_range', side_effect=mock_resolve_range):
                with patch('opensiddur.exporter.compiler.UrnResolver.prioritize_range', side_effect=mock_prioritize_range):
                    processor = CompilerProcessor(project, file_name)
                    processor.process()
            
            # Verify ExternalCompilerProcessor was instantiated
            MockExternalProcessor.assert_called_once()
            call_args = MockExternalProcessor.call_args
            
            # Check the positional arguments: project, file_name
            self.assertEqual(call_args[0][0], project)  # project
            self.assertEqual(call_args[0][1], file_name)  # file_name
            
            # Check keyword arguments: from_start, to_end (now element paths from ResolvedUrn)
            self.assertEqual(call_args[1]['from_start'], "/TEI/div[1]")
            self.assertEqual(call_args[1]['to_end'], "/TEI/div[1]")
            self.assertIn('linear_data', call_args[1])

            # Verify process() was called
            mock_instance.process.assert_called_once()

    def test_external_transclusion_defaults_type_to_external_when_missing(self):
        """Regression: j:transclude without @type must behave as external, not crash setting type=None."""
        from unittest.mock import patch, MagicMock

        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0"
                               xmlns:jlp="http://jewishliturgy.org/ns/jlptei/2">
    <tei:div>
        <tei:p>Before</tei:p>
        <jlp:transclude target="#start" targetEnd="#end"/>
        <tei:p>After</tei:p>
    </tei:div>
</root>'''

        project, file_name = self._create_test_file("external_transclude_default_type.xml", xml_content)

        with patch('opensiddur.exporter.external_compiler.ExternalCompilerProcessor') as MockExternalProcessor:
            mock_instance = MagicMock()
            mock_elem = etree.Element("{http://www.tei-c.org/ns/1.0}p")
            mock_elem.text = "transcluded content"
            mock_instance.process.return_value = [mock_elem]
            mock_instance._mark_file_source.side_effect = lambda e, **_: e
            mock_instance.project = "transcluded_project"
            mock_instance.file_name = "transcluded.xml"
            mock_instance.root_language = "xx"
            MockExternalProcessor.return_value = mock_instance

            from opensiddur.exporter.urn import ResolvedUrn

            def mock_resolve_range(urn):
                return [ResolvedUrn(urn=urn, project=project, file_name=file_name, element_path="/TEI/div[1]")]

            def mock_prioritize_range(urns, priority_list, return_all=False):
                return urns[0] if urns else None

            with patch('opensiddur.exporter.compiler.UrnResolver.resolve_range', side_effect=mock_resolve_range):
                with patch('opensiddur.exporter.compiler.UrnResolver.prioritize_range', side_effect=mock_prioritize_range):
                    processor = CompilerProcessor(project, file_name)
                    result = processor.process()

            # Ensure ExternalCompilerProcessor was used (i.e., treated as external)
            MockExternalProcessor.assert_called_once()
            # Ensure p:transclude exists and has type="external"
            ns = {"p": "http://jewishliturgy.org/ns/processing"}
            transclude_elem = result.xpath('.//p:transclude', namespaces=ns)
            self.assertEqual(len(transclude_elem), 1)
            self.assertEqual(transclude_elem[0].get('type'), 'external')

    def test_transclusion_with_urn_resolves_correctly(self):
        """Test that CompilerProcessor correctly resolves URNs and passes them to processors."""
        from unittest.mock import patch, MagicMock
        
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" 
                               xmlns:jlp="http://jewishliturgy.org/ns/jlptei/2">
    <tei:div>
        <jlp:transclude target="urn:external:file#fragment1" 
                        targetEnd="urn:external:file#fragment2" 
                        type="external"/>
    </tei:div>
</root>'''
        
        project, file_name = self._create_test_file("urn_transclude.xml", xml_content)
        
        # Mock ExternalCompilerProcessor
        with patch('opensiddur.exporter.external_compiler.ExternalCompilerProcessor') as MockExternalProcessor:
            mock_instance = MagicMock()
            mock_elem = etree.Element("{http://www.tei-c.org/ns/1.0}p")
            mock_instance.process.return_value = [mock_elem]
            # Mock _mark_file_source to act like a passthrough
            def mock_mark_file_source(elem, **_):
                return elem
            mock_instance._mark_file_source.side_effect = mock_mark_file_source
            mock_instance.project = "external_project"
            mock_instance.file_name = "external.xml"
            mock_instance.root_language = "xx"
            MockExternalProcessor.return_value = mock_instance
            
            # Mock UrnResolver methods to return resolved URNs pointing to external file
            from opensiddur.exporter.urn import ResolvedUrn
            
            def mock_resolve_range(urn):
                if "fragment1" in urn:
                    return [ResolvedUrn(urn="#fragment1", project="external_project", file_name="external.xml", element_path="/TEI/div[1]")]
                elif "fragment2" in urn:
                    return [ResolvedUrn(urn="#fragment2", project="external_project", file_name="external.xml", element_path="/TEI/div[1]")]
                return []
            
            def mock_prioritize_range(urns, priority_list, return_all=False):
                return urns[0] if urns else None
            
            with patch('opensiddur.exporter.compiler.UrnResolver.resolve_range', side_effect=mock_resolve_range):
                with patch('opensiddur.exporter.compiler.UrnResolver.prioritize_range', side_effect=mock_prioritize_range):
                    processor = CompilerProcessor(project, file_name)
                    processor.process()
            
            # Verify ExternalCompilerProcessor was called with resolved URNs
            MockExternalProcessor.assert_called_once()
            call_args = MockExternalProcessor.call_args
            
            # Should be called with external project and file (positional args)
            self.assertEqual(call_args[0][0], "external_project")  # project
            self.assertEqual(call_args[0][1], "external.xml")  # file_name
            
            # Check keyword arguments: from_start, to_end (now element paths from ResolvedUrn)
            self.assertEqual(call_args[1]['from_start'], "/TEI/div[1]")
            self.assertEqual(call_args[1]['to_end'], "/TEI/div[1]")

    def test_inline_transclusion_with_metadata(self):
        """Test CompilerProcessor with inline transclusion that includes teiHeader metadata."""
        from unittest.mock import patch, MagicMock
        
        # Main file
        main_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" 
                                     xmlns:jlp="http://jewishliturgy.org/ns/jlptei/2"
                                     xmlns:xml="http://www.w3.org/XML/1998/namespace">
    <tei:teiHeader>
        <tei:fileDesc>
            <tei:titleStmt><tei:title>Main File</tei:title></tei:titleStmt>
        </tei:fileDesc>
    </tei:teiHeader>
    <tei:text>
        <tei:div>Main text
            <tei:p xml:id="before">Before (excluded)</tei:p> Tail before
            <tei:p xml:id="start">Start</tei:p> Tail after start
            <jlp:transclude target="#transclude-start" targetEnd="#transclude-end" type="inline"/>
            <tei:p xml:id="end">End</tei:p> Tail after end
            <tei:p xml:id="after">After (excluded)</tei:p> Tail after
        </tei:div>
    </tei:text>
</root>'''
        
        # File to be transcluded (inline)
        transcluded_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xml="http://www.w3.org/XML/1998/namespace">
    <tei:teiHeader>
        <tei:fileDesc>
            <tei:titleStmt><tei:title>Transcluded File</tei:title></tei:titleStmt>
            <tei:publicationStmt><tei:p>Publication info</tei:p></tei:publicationStmt>
            <tei:sourceDesc><tei:p>Source description</tei:p></tei:sourceDesc>
        </tei:fileDesc>
    </tei:teiHeader>
    <tei:text>
        <tei:div>Transcluded div text
            <tei:p xml:id="transclude-start">Transcluded start</tei:p> Transcluded tail 1
            <tei:p xml:id="transclude-middle">Transcluded middle</tei:p> Transcluded tail 2
            <tei:p xml:id="transclude-end">Transcluded end</tei:p> Transcluded tail 3
        </tei:div>
    </tei:text>
</root>'''
        
        project, file_name = self._create_test_file("main_inline.xml", main_xml_content)
        
        # Parse the transcluded XML into a real tree so XPath lookups work
        transcluded_tree_root = etree.fromstring(transcluded_xml_content)
        transcluded_tree = transcluded_tree_root.getroottree()

        # Compute actual element paths for start/end within the transcluded tree
        trans_start_elem = transcluded_tree_root.xpath(
            "//*[@xml:id='transclude-start']",
            namespaces={'xml': 'http://www.w3.org/XML/1998/namespace'})[0]
        trans_end_elem = transcluded_tree_root.xpath(
            "//*[@xml:id='transclude-end']",
            namespaces={'xml': 'http://www.w3.org/XML/1998/namespace'})[0]
        trans_start_path = transcluded_tree.getpath(trans_start_elem)
        trans_end_path = transcluded_tree.getpath(trans_end_elem)

        # Mock XMLCache.parse_xml
        from opensiddur.exporter.linear import get_linear_data
        linear_data = get_linear_data()
        original_parse_xml = linear_data.xml_cache.parse_xml

        def mock_parse_xml(*args, **kwargs):
            if len(args) == 2 and args[0] == project and args[1] == file_name:
                return original_parse_xml(*args, **kwargs)
            else:
                return transcluded_tree

        # Mock UrnResolver methods
        from opensiddur.exporter.urn import ResolvedUrn

        def mock_resolve_range(urn):
            return [ResolvedUrn(
                urn=urn,
                project="transcluded_project",
                file_name="transcluded.xml",
                element_path=trans_start_path,
                end_element_path=trans_end_path,
                end_includes_tail=False,
            )]

        def mock_prioritize_range(urns, priority_list, return_all=False):
            return urns[0] if urns else None

        with patch.object(linear_data.xml_cache, 'parse_xml', side_effect=mock_parse_xml):
            with patch('opensiddur.exporter.compiler.UrnResolver.resolve_range', side_effect=mock_resolve_range):
                with patch('opensiddur.exporter.compiler.UrnResolver.prioritize_range', side_effect=mock_prioritize_range):
                    processor = CompilerProcessor(project, file_name)
                    result = processor.process()
        
        result_str = etree.tostring(result, encoding='unicode')
        
        # Verify the transclusion element is created
        self.assertIn('p:transclude', result_str)
        
        # Find the p:transclude element
        ns = {'p': 'http://jewishliturgy.org/ns/processing', 'tei': 'http://www.tei-c.org/ns/1.0'}
        transclude_elem = result.xpath('.//p:transclude', namespaces=ns)
        self.assertEqual(len(transclude_elem), 1)
        
        # Verify that p:transclude has project and file_name attributes (in processing namespace)
        self.assertEqual(transclude_elem[0].get('{http://jewishliturgy.org/ns/processing}project'), 'transcluded_project')
        self.assertEqual(transclude_elem[0].get('{http://jewishliturgy.org/ns/processing}file_name'), 'transcluded.xml')
        
        # Verify the root element has project and file_name attributes (in processing namespace)
        self.assertEqual(result.get('{http://jewishliturgy.org/ns/processing}project'), project)
        self.assertEqual(result.get('{http://jewishliturgy.org/ns/processing}file_name'), file_name)
        
        # Verify that metadata is NOT inserted as a child element
        transclude_children = list(transclude_elem[0])
        # Children should be the transcluded text content, not metadata
        has_file_desc = any('fileDesc' in child.tag for child in transclude_children)
        self.assertFalse(has_file_desc, "fileDesc should not be inserted as a child element")
        
        # Verify the transcluded text content is present
        self.assertIn('Transcluded start', result_str)
        self.assertIn('Transcluded middle', result_str)
        self.assertIn('Transcluded end', result_str)

    def test_external_transclusion_with_metadata(self):
        """Test CompilerProcessor with external transclusion that includes teiHeader metadata."""
        from unittest.mock import patch, MagicMock
        
        # Main file
        main_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" 
                                     xmlns:jlp="http://jewishliturgy.org/ns/jlptei/2"
                                     xmlns:xml="http://www.w3.org/XML/1998/namespace">
    <tei:teiHeader>
        <tei:fileDesc>
            <tei:titleStmt><tei:title>Main File</tei:title></tei:titleStmt>
        </tei:fileDesc>
    </tei:teiHeader>
    <tei:text>
        <tei:div>Main text
            <tei:p xml:id="before">Before (excluded)</tei:p> Tail before
            <tei:p xml:id="start">Start</tei:p> Tail after start
            <jlp:transclude target="#transclude-start" targetEnd="#transclude-end" type="external"/>
            <tei:p xml:id="end">End</tei:p> Tail after end
            <tei:p xml:id="after">After (excluded)</tei:p> Tail after
        </tei:div>
    </tei:text>
</root>'''
        
        # External file to be transcluded
        external_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xml="http://www.w3.org/XML/1998/namespace">
    <tei:teiHeader>
        <tei:fileDesc>
            <tei:titleStmt><tei:title>External File</tei:title></tei:titleStmt>
            <tei:publicationStmt><tei:p>External publication</tei:p></tei:publicationStmt>
            <tei:sourceDesc><tei:p>External source</tei:p></tei:sourceDesc>
        </tei:fileDesc>
    </tei:teiHeader>
    <tei:text>
        <tei:div>External div text
            <tei:p xml:id="transclude-start">External start</tei:p> External tail 1
            <tei:p xml:id="transclude-middle">External middle</tei:p> External tail 2
            <tei:p xml:id="transclude-end">External end</tei:p> External tail 3
        </tei:div>
    </tei:text>
</root>'''
        
        project, file_name = self._create_test_file("main_external.xml", main_xml_content)

        # Parse the external XML into a real tree so XPath lookups work
        external_tree_root = etree.fromstring(external_xml_content)
        external_tree = external_tree_root.getroottree()

        # Compute actual element paths for start/end within the external tree
        xml_id_ns = {'xml': 'http://www.w3.org/XML/1998/namespace'}
        ext_start_elem = external_tree_root.xpath(
            "//*[@xml:id='transclude-start']", namespaces=xml_id_ns)[0]
        ext_end_elem = external_tree_root.xpath(
            "//*[@xml:id='transclude-end']", namespaces=xml_id_ns)[0]
        ext_start_path = external_tree.getpath(ext_start_elem)
        ext_end_path = external_tree.getpath(ext_end_elem)

        # Mock XMLCache.parse_xml
        from opensiddur.exporter.linear import get_linear_data
        linear_data = get_linear_data()
        original_parse_xml = linear_data.xml_cache.parse_xml

        def mock_parse_xml(*args, **kwargs):
            if len(args) == 2 and args[0] == project and args[1] == file_name:
                return original_parse_xml(*args, **kwargs)
            else:
                return external_tree

        # Mock UrnResolver methods
        from opensiddur.exporter.urn import ResolvedUrn

        def mock_resolve_range(urn):
            if urn.startswith("#transclude"):
                return [ResolvedUrn(
                    urn=urn,
                    project="external_project",
                    file_name="external.xml",
                    element_path=ext_start_path,
                    end_element_path=ext_end_path,
                    end_includes_tail=False,
                )]
            return []

        def mock_prioritize_range(urns, priority_list, return_all=False):
            return urns[0] if urns else None

        with patch.object(linear_data.xml_cache, 'parse_xml', side_effect=mock_parse_xml):
            with patch('opensiddur.exporter.compiler.UrnResolver.resolve_range', side_effect=mock_resolve_range):
                with patch('opensiddur.exporter.compiler.UrnResolver.prioritize_range', side_effect=mock_prioritize_range):
                    processor = CompilerProcessor(project, file_name)
                    result = processor.process()
        
        result_str = etree.tostring(result, encoding='unicode')
        
        # Verify the transclusion element is created
        self.assertIn('p:transclude', result_str)
        
        # Find the p:transclude element
        ns = {'p': 'http://jewishliturgy.org/ns/processing', 'tei': 'http://www.tei-c.org/ns/1.0'}
        transclude_elem = result.xpath('.//p:transclude', namespaces=ns)
        self.assertEqual(len(transclude_elem), 1)
        
        # Verify that p:transclude has project and file_name attributes (in processing namespace)
        self.assertEqual(transclude_elem[0].get('{http://jewishliturgy.org/ns/processing}project'), 'external_project')
        self.assertEqual(transclude_elem[0].get('{http://jewishliturgy.org/ns/processing}file_name'), 'external.xml')
        
        # Verify the root element has project and file_name attributes (in processing namespace)
        self.assertEqual(result.get('{http://jewishliturgy.org/ns/processing}project'), project)
        self.assertEqual(result.get('{http://jewishliturgy.org/ns/processing}file_name'), file_name)
        
        # Verify that metadata is NOT inserted as a child element
        transclude_children = list(transclude_elem[0])
        # Children should be the transcluded text content, not metadata
        has_file_desc = any('fileDesc' in child.tag for child in transclude_children)
        self.assertFalse(has_file_desc, "fileDesc should not be inserted as a child element")
        
        # Verify the transcluded text content is present
        self.assertIn('External start', result_str)
        self.assertIn('External middle', result_str)
        self.assertIn('External end', result_str)
        
        # Verify tail text is preserved
        self.assertIn('External tail 1', result_str)
        self.assertIn('External tail 2', result_str)
        
        # Verify that project and file_name are ONLY on root and p:transclude elements
        # Count occurrences of p:project attribute in the output (with namespace prefix)
        project_attr_count = len(re.findall(r'p:project="', result_str))
        # Should be exactly 2: one on root, one on p:transclude
        self.assertEqual(project_attr_count, 2, "p:project attribute should only appear on root and p:transclude")

    def test_metadata_extraction_preserves_structure(self):
        """Test that metadata extraction preserves the full fileDesc structure including nested elements."""
        from unittest.mock import patch, MagicMock
        
        # Main file
        main_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" 
                                     xmlns:jlp="http://jewishliturgy.org/ns/jlptei/2">
    <tei:text>
        <tei:div>
            <jlp:transclude target="#fragment" type="inline"/>
        </tei:div>
    </tei:text>
</root>'''
        
        # Complex metadata structure
        transcluded_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xml="http://www.w3.org/XML/1998/namespace">
    <tei:teiHeader>
        <tei:fileDesc>
            <tei:titleStmt>
                <tei:title type="main">Main Title</tei:title>
                <tei:title type="sub">Subtitle</tei:title>
                <tei:author>Author Name</tei:author>
            </tei:titleStmt>
            <tei:publicationStmt>
                <tei:publisher>Publisher Name</tei:publisher>
                <tei:pubPlace>City</tei:pubPlace>
                <tei:date>2025</tei:date>
            </tei:publicationStmt>
            <tei:sourceDesc>
                <tei:bibl>
                    <tei:title>Source Title</tei:title>
                    <tei:author>Source Author</tei:author>
                </tei:bibl>
            </tei:sourceDesc>
        </tei:fileDesc>
    </tei:teiHeader>
    <tei:text>
        <tei:div>
            <tei:p xml:id="fragment">Fragment text</tei:p>
        </tei:div>
    </tei:text>
</root>'''
        
        project, file_name = self._create_test_file("metadata_test.xml", main_xml_content)

        # Parse the transcluded XML tree and compute actual element paths
        transcluded_tree_root = etree.fromstring(transcluded_xml_content)
        transcluded_tree = transcluded_tree_root.getroottree()
        fragment_elem = transcluded_tree_root.xpath(
            "//*[@xml:id='fragment']",
            namespaces={'xml': 'http://www.w3.org/XML/1998/namespace'})[0]
        fragment_path = transcluded_tree.getpath(fragment_elem)

        # Mock XMLCache.parse_xml
        from opensiddur.exporter.linear import get_linear_data
        linear_data = get_linear_data()
        original_parse_xml = linear_data.xml_cache.parse_xml

        def mock_parse_xml(*args, **kwargs):
            if len(args) == 2 and args[0] == project and args[1] == file_name:
                return original_parse_xml(*args, **kwargs)
            else:
                mock_tree = MagicMock()
                mock_tree.getroot.return_value = transcluded_tree_root
                return mock_tree

        # Mock UrnResolver methods
        from opensiddur.exporter.urn import ResolvedUrn

        def mock_resolve_range(urn):
            # Return a different project/file to avoid infinite recursion
            return [ResolvedUrn(urn=urn, project="transcluded_project", file_name="transcluded.xml",
                               element_path=fragment_path, end_element_path=fragment_path)]
        
        def mock_prioritize_range(urns, priority_list, return_all=False):
            return urns[0] if urns else None
        
        with patch.object(linear_data.xml_cache, 'parse_xml', side_effect=mock_parse_xml):
            with patch('opensiddur.exporter.compiler.UrnResolver.resolve_range', side_effect=mock_resolve_range):
                with patch('opensiddur.exporter.compiler.UrnResolver.prioritize_range', side_effect=mock_prioritize_range):
                    processor = CompilerProcessor(project, file_name)
                    result = processor.process()
        
        result_str = etree.tostring(result, encoding='unicode')
        
        # Find the p:transclude element
        ns = {'p': 'http://jewishliturgy.org/ns/processing', 'tei': 'http://www.tei-c.org/ns/1.0'}
        transclude_elem = result.xpath('.//p:transclude', namespaces=ns)
        self.assertEqual(len(transclude_elem), 1)
        
        # Verify that p:transclude has project and file_name attributes (in processing namespace)
        self.assertEqual(transclude_elem[0].get('{http://jewishliturgy.org/ns/processing}project'), 'transcluded_project')
        self.assertEqual(transclude_elem[0].get('{http://jewishliturgy.org/ns/processing}file_name'), 'transcluded.xml')
        
        # Verify the root element has project and file_name attributes (in processing namespace)
        self.assertEqual(result.get('{http://jewishliturgy.org/ns/processing}project'), project)
        self.assertEqual(result.get('{http://jewishliturgy.org/ns/processing}file_name'), file_name)
        
        # Verify that metadata is NOT inserted as a child element
        transclude_children = list(transclude_elem[0])
        has_file_desc = any('fileDesc' in child.tag for child in transclude_children)
        self.assertFalse(has_file_desc, "fileDesc should not be inserted as a child element")
        
        # Verify that metadata is NOT present in the output
        # (it should be referenced via attributes, not included inline)
        self.assertNotIn('Main Title', result_str)
        self.assertNotIn('Subtitle', result_str)
        self.assertNotIn('Author Name', result_str)
        self.assertNotIn('Publisher Name', result_str)
        
        # Verify the fragment text IS present
        self.assertIn('Fragment text', result_str)
        
        # Verify that project and file_name are ONLY on root and p:transclude elements
        project_attr_count = len(re.findall(r'p:project="', result_str))
        # Should be exactly 2: one on root, one on p:transclude
        self.assertEqual(project_attr_count, 2, "p:project attribute should only appear on root and p:transclude")

    def test_language_handling_in_transclusions(self):
        """Test that language differences are correctly handled in transclusions."""
        from unittest.mock import patch, MagicMock
        
        # Main file with English as default
        main_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:jlp="http://jewishliturgy.org/ns/jlptei/2" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="en">
    <tei:text>
        <tei:div xml:id="start">
            <tei:p>Before transclusion</tei:p>
            <jlp:transclude target="#ext_frag" targetEnd="#ext_frag" type="external"/>
            <tei:p>After transclusion</tei:p>
        </tei:div>
    </tei:text>
</root>'''
        
        # External transcluded file with Hebrew
        transcluded_xml_content = '''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="he">
    <tei:text>
        <tei:div>
            <tei:p xml:id="ext_frag">טקסט בעברית</tei:p>
        </tei:div>
    </tei:text>
</root>'''
        
        project, file_name = self._create_test_file("main_lang_test.xml", main_xml_content)

        # Parse the transcluded XML tree and compute actual element paths
        transcluded_tree_root = etree.fromstring(transcluded_xml_content.encode())
        transcluded_tree = transcluded_tree_root.getroottree()
        ext_frag_elem = transcluded_tree_root.xpath(
            "//*[@xml:id='ext_frag']",
            namespaces={'xml': 'http://www.w3.org/XML/1998/namespace'})[0]
        ext_frag_path = transcluded_tree.getpath(ext_frag_elem)

        # Mock XMLCache.parse_xml
        from opensiddur.exporter.linear import get_linear_data
        linear_data = get_linear_data()
        original_parse_xml = linear_data.xml_cache.parse_xml

        def mock_parse_xml(*args, **kwargs):
            if len(args) == 2:
                if args[0] == project and args[1] == file_name:
                    return original_parse_xml(*args, **kwargs)
                else:
                    mock_tree = MagicMock()
                    mock_tree.getroot.return_value = transcluded_tree_root
                    return mock_tree
            return original_parse_xml(*args, **kwargs)

        # Mock UrnResolver methods
        from opensiddur.exporter.urn import ResolvedUrn

        def mock_resolve_range(urn):
            if "ext_frag" in urn:
                return [ResolvedUrn(urn="#ext_frag", project="external_project", file_name="external.xml",
                                   element_path=ext_frag_path, end_element_path=ext_frag_path)]
            return []
        
        def mock_prioritize_range(urns, priority_list, return_all=False):
            if not urns:
                return None
            if return_all:
                return urns
            return urns[0] if urns else None
        
        with patch.object(linear_data.xml_cache, 'parse_xml', side_effect=mock_parse_xml):
            with patch('opensiddur.exporter.compiler.UrnResolver.resolve_range', side_effect=mock_resolve_range):
                with patch('opensiddur.exporter.compiler.UrnResolver.prioritize_range', side_effect=mock_prioritize_range):
                    processor = CompilerProcessor(project, file_name)
                    result = processor.process()
        
        
        # Check that external transclusion has correct language
        transclude_elem = result.xpath('.//p:transclude', namespaces={'p': 'http://jewishliturgy.org/ns/processing', 'tei': 'http://www.tei-c.org/ns/1.0'})
        self.assertEqual(len(transclude_elem), 1, "Should have exactly one transclude element")
        
        # The p:transclude element should have xml:lang="he" because the transcluded content is Hebrew
        transclude_lang = transclude_elem[0].get('{http://www.w3.org/XML/1998/namespace}lang')
        self.assertEqual(transclude_lang, 'he', "Transclude element should have xml:lang='he'")
        
        # Verify the root element has xml:lang="en" (from main file)
        root_lang = result.get('{http://www.w3.org/XML/1998/namespace}lang')
        self.assertEqual(root_lang, 'en', "Root element should have xml:lang='en'")

    def test_language_handling_in_instructional_annotations(self):
        """Test that language differences are correctly handled in instructional annotations."""
        from unittest.mock import patch, MagicMock
        
        # Main file with English as default
        main_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:jlp="http://jewishliturgy.org/ns/jlptei/2" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="en">
    <tei:text>
        <tei:body>
            <tei:div>
                <tei:p>Element before note</tei:p>
                <tei:note type="instruction" corresp="urn:test:instruction:lang"/>
                <tei:p>Element after note</tei:p>
            </tei:div>
        </tei:body>
    </tei:text>
</root>'''
        
        # Instructional note file with Hebrew
        instruction_xml_content = '''<TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:jlp="http://jewishliturgy.org/ns/jlptei/2" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="he">
    <tei:teiHeader>
        <tei:fileDesc>
            <tei:titleStmt>
                <tei:title>Instruction Document</tei:title>
            </tei:titleStmt>
        </tei:fileDesc>
    </tei:teiHeader>
    <tei:text>
        <tei:body>
            <tei:div>
                <tei:note type="instruction" corresp="urn:test:instruction:lang">
                    <tei:p>הוראה בעברית</tei:p>
                </tei:note>
            </tei:div>
        </tei:body>
    </tei:text>
</TEI>'''
        
        project, file_name = self._create_test_file("main_inst_test.xml", main_xml_content)
        
        # Parse the instruction XML tree
        instruction_tree_root = etree.fromstring(instruction_xml_content)
        
        # Get the actual element path from the parsed tree
        lxml_note_element = instruction_tree_root.xpath("//tei:note[@type='instruction']", 
            namespaces={"tei": "http://www.tei-c.org/ns/1.0"})[0]
        lxml_note_element_path = lxml_note_element.getroottree().getpath(lxml_note_element)
        
        # Mock XMLCache.parse_xml
        from opensiddur.exporter.linear import LinearData
        from opensiddur.exporter.refdb import ReferenceDatabase
        linear_data = LinearData(
            instruction_priority=["instructions_project", "test_project"],
            annotation_projects=["notes_project", "test_project"],
            project_priority=["test_project", "notes_project"]
        )
        linear_data.xml_cache.base_path = Path(self.temp_dir.name)
        refdb = MagicMock(spec=ReferenceDatabase)
        
        # Mock get_urn_mappings to return the instruction note mapping
        from opensiddur.exporter.refdb import UrnMapping
        refdb.get_urn_mappings.return_value = [
            UrnMapping(
                urn="urn:test:instruction:lang",
                project="instructions_project",
                file_name="instruction.xml",
                element_path=lxml_note_element_path,
                element_tag="{http://www.tei-c.org/ns/1.0}note",
                element_type="instruction"
            )
        ]
        refdb.get_references_to.return_value = []
        
        original_parse_xml = linear_data.xml_cache.parse_xml
        
        def mock_parse_xml(*args, **kwargs):
            if len(args) == 2:
                if args[0] == project and args[1] == file_name:
                    return original_parse_xml(*args, **kwargs)
                else:
                    mock_tree = MagicMock()
                    mock_tree.getroot.return_value = instruction_tree_root
                    return mock_tree
            return original_parse_xml(*args, **kwargs)
        
        # Mock UrnResolver methods
        from opensiddur.exporter.urn import ResolvedUrn
        
        def mock_resolve(urn):
            if urn == "urn:test:instruction:lang":
                return [ResolvedUrn(urn="urn:test:instruction:lang", project="instructions_project", file_name="instruction.xml", element_path=lxml_note_element_path)]
            return []
        
        def mock_prioritize_range(urns, priority_list, return_all=False):
            if not urns:
                return None
            if return_all:
                return urns
            return urns[0] if urns else None
        
        with patch.object(linear_data.xml_cache, 'parse_xml', side_effect=mock_parse_xml):
            with patch('opensiddur.exporter.compiler.UrnResolver.resolve', side_effect=mock_resolve):
                with patch('opensiddur.exporter.compiler.UrnResolver.prioritize_range', side_effect=mock_prioritize_range):
                    processor = CompilerProcessor(project, file_name, linear_data=linear_data, reference_database=refdb)
                    result = processor.process()
        
        
        # Check that instructional note has correct language
        instructional_notes = result.xpath('.//tei:note[@type="instruction"]', namespaces={'tei': 'http://www.tei-c.org/ns/1.0'})
        self.assertEqual(len(instructional_notes), 1, "Should have exactly one instructional note")
        
        # The instructional note should have xml:lang="he" because the note content is Hebrew
        inst_note_lang = instructional_notes[0].get('{http://www.w3.org/XML/1998/namespace}lang')
        self.assertEqual(inst_note_lang, 'he', "Instructional note should have xml:lang='he'")
        
        # Verify the root element has xml:lang="en" (from main file)
        root_lang = result.get('{http://www.w3.org/XML/1998/namespace}lang')
        self.assertEqual(root_lang, 'en', "Root element should have xml:lang='en'")

    def test_language_handling_in_editorial_annotations(self):
        """Test that language differences are correctly handled in editorial annotations."""
        from unittest.mock import patch, MagicMock
        
        # Main file with English as default
        main_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:jlp="http://jewishliturgy.org/ns/jlptei/2" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="en">
    <tei:text>
        <tei:body>
            <tei:div>
                <tei:p xml:id="target1">This element is targeted by the note</tei:p>
            </tei:div>
        </tei:body>
    </tei:text>
</root>'''
        
        # Editorial note file with Hebrew
        editorial_xml_content = '''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:jlp="http://jewishliturgy.org/ns/jlptei/2" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="he">
    <tei:teiHeader>
        <tei:fileDesc>
            <tei:titleStmt>
                <tei:title>Editorial Note Document</tei:title>
            </tei:titleStmt>
        </tei:fileDesc>
    </tei:teiHeader>
    <tei:standOff>
        <tei:note type="editorial" target="#target1">
            <tei:p>הערה בעברית</tei:p>
        </tei:note>
    </tei:standOff>
</root>'''
        
        project, file_name = self._create_test_file("main_edit_test.xml", main_xml_content)
        
        # Parse the editorial note XML tree
        editorial_tree_root = etree.fromstring(editorial_xml_content)
        
        # Mock XMLCache.parse_xml
        from opensiddur.exporter.linear import LinearData
        from opensiddur.exporter.refdb import ReferenceDatabase
        linear_data = LinearData(
            instruction_priority=["notes_project", "test_project"],
            annotation_projects=["notes_project", "test_project"],
            project_priority=["test_project", "notes_project"]
        )
        linear_data.xml_cache.base_path = Path(self.temp_dir.name)
        refdb = MagicMock(spec=ReferenceDatabase)
        
        # Mock get_references_to to return the editorial note reference
        from opensiddur.exporter.refdb import Reference
        import xml.etree.ElementTree as ET
        # Get the note element from the parsed XML to get its path
        note_elem = editorial_tree_root.xpath('//tei:note[@type="editorial"]', namespaces={'tei': 'http://www.tei-c.org/ns/1.0'})[0]
        note_path = note_elem.getroottree().getpath(note_elem)
        
        refdb.get_references_to.return_value = [
            Reference(
                element_path=note_path,
                element_tag="{http://www.tei-c.org/ns/1.0}note",
                element_type="editorial",
                target_start="#target1",
                target_end=None,
                target_is_id=True,
                corresponding_urn=None,
                project="notes_project",
                file_name="editorial.xml"
            )
        ]
        refdb.get_urn_mappings.return_value = []
        
        original_parse_xml = linear_data.xml_cache.parse_xml
        
        def mock_parse_xml(*args, **kwargs):
            if len(args) == 2:
                if args[0] == project and args[1] == file_name:
                    return original_parse_xml(*args, **kwargs)
                else:
                    mock_tree = MagicMock()
                    mock_tree.getroot.return_value = editorial_tree_root
                    return mock_tree
            return original_parse_xml(*args, **kwargs)
        
        # Mock UrnResolver methods
        def mock_prioritize_range(urns, priority_list, return_all=False):
            if not urns:
                return None
            if return_all:
                return urns
            return urns[0] if urns else None
        
        with patch.object(linear_data.xml_cache, 'parse_xml', side_effect=mock_parse_xml):
            with patch('opensiddur.exporter.compiler.UrnResolver.prioritize_range', side_effect=mock_prioritize_range):
                processor = CompilerProcessor(project, file_name, linear_data=linear_data, reference_database=refdb)
                result = processor.process()
        
        
        # Check that editorial note has correct language
        editorial_notes = result.xpath('.//tei:note[@type="editorial"]', namespaces={'tei': 'http://www.tei-c.org/ns/1.0'})
        self.assertEqual(len(editorial_notes), 1, "Should have exactly one editorial note")
        
        # The editorial note should have xml:lang="he" because the note content is Hebrew
        edit_note_lang = editorial_notes[0].get('{http://www.w3.org/XML/1998/namespace}lang')
        self.assertEqual(edit_note_lang, 'he', "Editorial note should have xml:lang='he'")
        
        # Verify the root element has xml:lang="en" (from main file)
        root_lang = result.get('{http://www.w3.org/XML/1998/namespace}lang')
        self.assertEqual(root_lang, 'en', "Root element should have xml:lang='en'")


class TestCompilerProcessorCommentsAndPIs(unittest.TestCase):
    """Comments and processing instructions must be dropped, not crash the compiler (#41)."""

    def setUp(self):
        reset_linear_data()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_project_dir = Path(self.temp_dir.name) / "test_project"
        self.test_project_dir.mkdir(parents=True)
        get_linear_data().xml_cache.base_path = Path(self.temp_dir.name)

    def _compile(self, file_name: str, content: bytes):
        file_path = self.test_project_dir / file_name
        with open(file_path, 'wb') as f:
            f.write(content)
        return CompilerProcessor("test_project", file_name).process()

    def test_comment_between_siblings_is_dropped(self):
        """A comment between elements compiles and does not reach the output."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:text>
        <tei:p>First</tei:p>
        <!-- an editorial remark -->
        <tei:p>Second</tei:p>
    </tei:text>
</root>'''

        result = self._compile("comment_siblings.xml", xml_content)
        result_str = etree.tostring(result, encoding='unicode')

        self.assertNotIn('<!--', result_str)
        self.assertNotIn('an editorial remark', result_str)
        self.assertIn('First', result_str)
        self.assertIn('Second', result_str)

    def test_comment_tail_text_is_preserved(self):
        """The text following a dropped comment is document text and must survive."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:text><tei:p>a<!-- why -->b</tei:p></tei:text>
</root>'''

        result = self._compile("comment_tail.xml", xml_content)
        paragraphs = result.findall(f'.//{{{"http://www.tei-c.org/ns/1.0"}}}p')

        self.assertEqual(len(paragraphs), 1)
        self.assertEqual(''.join(paragraphs[0].itertext()), 'ab')

    def test_comment_tail_after_element_child_is_preserved(self):
        """A comment following a child element hands its tail to that child."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:text><tei:p><tei:hi>emphasis</tei:hi><!-- why --> trailing</tei:p></tei:text>
</root>'''

        result = self._compile("comment_tail_after_child.xml", xml_content)
        paragraphs = result.findall(f'.//{{{"http://www.tei-c.org/ns/1.0"}}}p')

        self.assertEqual(len(paragraphs), 1)
        self.assertEqual(''.join(paragraphs[0].itertext()), 'emphasis trailing')

    def test_comment_as_only_child(self):
        """An element whose only child is a comment survives as an empty element."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:text><tei:p><!-- nothing but a comment --></tei:p></tei:text>
</root>'''

        result = self._compile("comment_only_child.xml", xml_content)
        paragraphs = result.findall(f'.//{{{"http://www.tei-c.org/ns/1.0"}}}p')

        self.assertEqual(len(paragraphs), 1)
        self.assertEqual(len(paragraphs[0]), 0)
        self.assertNotIn('nothing but a comment', etree.tostring(result, encoding='unicode'))

    def test_processing_instruction_is_dropped(self):
        """A PI takes the same code path as a comment: etree.PI as its tag."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0">
    <tei:text>
        <tei:p>First</tei:p>
        <?some-target some data?>
        <tei:p>Second</tei:p>
    </tei:text>
</root>'''

        result = self._compile("pi.xml", xml_content)
        result_str = etree.tostring(result, encoding='unicode')

        self.assertNotIn('some-target', result_str)
        self.assertIn('First', result_str)
        self.assertIn('Second', result_str)

    def test_comment_inside_conditional_definition(self):
        """A comment among the condition children is not parsed as a condition."""
        xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    <tei:text>
        <j:declare xml:id="d">
            <tei:fs type="t:fs"><tei:f name="x"><tei:binary value="true"/></tei:f></tei:fs>
        </j:declare>
        <j:conditional xml:id="c">
            <!-- included only when x is true -->
            <tei:fs type="t:fs"><tei:f name="x"><tei:binary value="true"/></tei:f></tei:fs>
        </j:conditional>
        <tei:p>included</tei:p>
        <j:endConditional target="#c"/>
        <j:endDeclare target="#d"/>
    </tei:text>
</root>'''

        result = self._compile("comment_in_conditional.xml", xml_content)
        result_str = etree.tostring(result, encoding='unicode')

        self.assertIn('included', result_str)
        self.assertNotIn('<!--', result_str)


class TestCompilerProcessorIdRewriting(unittest.TestCase):
    """Test ID rewriting functionality in CompilerProcessor."""

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
        
        # Reset linear data
        reset_linear_data()
        self.linear_data = get_linear_data()

    def _create_test_file(self, file_name: str, content: bytes) -> tuple[str, str]:
        """Create a test XML file and return (project, file_name) tuple."""
        file_path = self.test_project_dir / file_name
        with open(file_path, 'wb') as f:
            f.write(content)
        return "test_project", file_name

    def test_id_rewriting_consistency_within_transclusion(self):
        """Test that ID rewriting uses the same hash within the same transclusion path."""
        # Main file with two transclusions to the same external file
        main_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" 
                                     xmlns:jlp="http://jewishliturgy.org/ns/jlptei/2"
                                     xmlns:xml="http://www.w3.org/XML/1998/namespace">
    <tei:div>
        <tei:p xml:id="main1">Main content 1</tei:p>
        <jlp:transclude target="#external1" type="external"/>
        <tei:p xml:id="main2">Main content 2</tei:p>
        <jlp:transclude target="#external2" type="external"/>
        <tei:p xml:id="main3">Main content 3</tei:p>
    </tei:div>
</root>'''
        
        # External file with elements that have IDs
        external_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xml="http://www.w3.org/XML/1998/namespace">
    <tei:div>
        <tei:p xml:id="external1">External content 1</tei:p>
        <tei:p xml:id="external2">External content 2</tei:p>
        <tei:p xml:id="external3" target="#external1">Reference to external1</tei:p>
        <tei:p xml:id="external4" target="#external2">Reference to external2</tei:p>
    </tei:div>
</root>'''
        
        project, file_name = self._create_test_file("main.xml", main_xml_content)

        # Parse the external XML tree and compute actual element paths
        external_tree_root = etree.fromstring(external_xml_content)
        external_tree = external_tree_root.getroottree()
        xml_ns = 'http://www.w3.org/XML/1998/namespace'
        external1_elem = external_tree_root.xpath(
            "//*[@xml:id='external1']", namespaces={'xml': xml_ns})[0]
        external2_elem = external_tree_root.xpath(
            "//*[@xml:id='external2']", namespaces={'xml': xml_ns})[0]
        external1_path = external_tree.getpath(external1_elem)
        external2_path = external_tree.getpath(external2_elem)

        # Mock XMLCache.parse_xml
        from opensiddur.exporter.linear import get_linear_data
        linear_data = get_linear_data()
        original_parse_xml = linear_data.xml_cache.parse_xml

        def mock_parse_xml(*args, **kwargs):
            if len(args) == 2 and args[0] == project and args[1] == file_name:
                # Main file - create a mock tree for the main file
                main_tree = MagicMock()
                main_tree.getroot.return_value = etree.fromstring(main_xml_content)
                return main_tree
            elif len(args) == 2 and args[0] == "external_project":
                # External file
                mock_tree = MagicMock()
                mock_tree.getroot.return_value = external_tree_root
                return mock_tree
            else:
                return original_parse_xml(*args, **kwargs)

        # Mock UrnResolver methods
        from opensiddur.exporter.urn import ResolvedUrn

        def mock_resolve_range(urn):
            if urn.startswith("#external1"):
                return [ResolvedUrn(urn=urn, project="external_project", file_name="external.xml",
                                   element_path=external1_path, end_element_path=external1_path)]
            elif urn.startswith("#external2"):
                return [ResolvedUrn(urn=urn, project="external_project", file_name="external.xml",
                                   element_path=external2_path, end_element_path=external2_path)]
            return []
        
        def mock_prioritize_range(urns, priority_list, return_all=False):
            return urns[0] if urns else None
        
        def mock_get_path_from_urn(resolved_urn):
            from pathlib import Path
            return Path(self.temp_dir.name) / "external_project" / "external.xml"
        
        with patch.object(linear_data.xml_cache, 'parse_xml', side_effect=mock_parse_xml):
            with patch('opensiddur.exporter.compiler.UrnResolver.resolve_range', side_effect=mock_resolve_range):
                with patch('opensiddur.exporter.compiler.UrnResolver.prioritize_range', side_effect=mock_prioritize_range):
                    with patch('opensiddur.exporter.compiler.UrnResolver.get_path_from_urn', side_effect=mock_get_path_from_urn):
                        processor = CompilerProcessor(project, file_name)
                        result = processor.process()
        
        # Find the transclude elements (they use the processing namespace p:)
        transclude_elements = result.xpath(".//p:transclude", namespaces={"p": "http://jewishliturgy.org/ns/processing"})
        self.assertEqual(len(transclude_elements), 2, "Should have 2 transclude elements")
        
        # Get the transcluded content from each transclude element
        transclude1_children = list(transclude_elements[0])
        transclude2_children = list(transclude_elements[1])
        
        # Both transclusions should have content
        self.assertGreater(len(transclude1_children), 0, "First transclude should have content")
        self.assertGreater(len(transclude2_children), 0, "Second transclude should have content")
        
        # Extract all xml:id attributes from both transclusions
        all_ids_transclude1 = []
        all_ids_transclude2 = []
        
        for child in transclude1_children:
            xml_id = child.get("{http://www.w3.org/XML/1998/namespace}id")
            if xml_id:
                all_ids_transclude1.append(xml_id)
        
        for child in transclude2_children:
            xml_id = child.get("{http://www.w3.org/XML/1998/namespace}id")
            if xml_id:
                all_ids_transclude2.append(xml_id)
        
        # Both transclusions should have rewritten IDs
        self.assertGreater(len(all_ids_transclude1), 0, "First transclude should have rewritten IDs")
        self.assertGreater(len(all_ids_transclude2), 0, "Second transclude should have rewritten IDs")
        
        # Extract hash suffixes from the IDs
        def extract_hash_suffix(xml_id):
            if '_' in xml_id:
                return xml_id.split('_', 1)[1]
            return ""
        
        hash_suffixes_1 = [extract_hash_suffix(xml_id) for xml_id in all_ids_transclude1 if '_' in xml_id]
        hash_suffixes_2 = [extract_hash_suffix(xml_id) for xml_id in all_ids_transclude2 if '_' in xml_id]
        
        # All IDs within the same transclusion should have the same hash suffix
        if hash_suffixes_1:
            first_hash_1 = hash_suffixes_1[0]
            for hash_suffix in hash_suffixes_1:
                self.assertEqual(hash_suffix, first_hash_1, 
                               f"All IDs in first transclude should have same hash: {hash_suffixes_1}")
        
        if hash_suffixes_2:
            first_hash_2 = hash_suffixes_2[0]
            for hash_suffix in hash_suffixes_2:
                self.assertEqual(hash_suffix, first_hash_2, 
                               f"All IDs in second transclude should have same hash: {hash_suffixes_2}")
        
        # The two transclusions should have different hash suffixes (different processing paths)
        if hash_suffixes_1 and hash_suffixes_2:
            self.assertNotEqual(first_hash_1, first_hash_2, 
                              f"Different transclusions should have different hashes: {first_hash_1} vs {first_hash_2}")
        
        # Check that target attributes are also rewritten consistently
        all_targets_transclude1 = []
        all_targets_transclude2 = []
        
        for child in transclude1_children:
            target = child.get("target")
            if target:
                all_targets_transclude1.append(target)
        
        for child in transclude2_children:
            target = child.get("target")
            if target:
                all_targets_transclude2.append(target)
        
        # Targets should be rewritten with the same hash as their corresponding IDs
        for target in all_targets_transclude1:
            if target.startswith("#"):
                target_id = target[1:]  # Remove the #
                # Find the corresponding xml:id in the same transclude
                for xml_id in all_ids_transclude1:
                    if xml_id.startswith(target_id.split('_')[0] + '_'):  # Match base ID + hash
                        expected_hash = xml_id.split('_', 1)[1]
                        self.assertTrue(target.endswith('_' + expected_hash), 
                                      f"Target {target} should end with same hash as ID {xml_id}")

    def test_id_rewriting_different_hashes_for_same_entity_transcluded_twice(self):
        """Test that the same entity transcluded twice gets different rewritten xml:ids."""
        # Main file with two transclusions to the same external entity
        main_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" 
                                     xmlns:jlp="http://jewishliturgy.org/ns/jlptei/2"
                                     xmlns:xml="http://www.w3.org/XML/1998/namespace">
    <tei:div>
        <tei:p xml:id="main1">Main content 1</tei:p>
        <jlp:transclude target="#external1" type="external"/>
        <tei:p xml:id="main2">Main content 2</tei:p>
        <jlp:transclude target="#external1" type="external"/>
        <tei:p xml:id="main3">Main content 3</tei:p>
    </tei:div>
</root>'''
        
        # External file with a single entity that will be transcluded twice
        external_xml_content = b'''<root xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xml="http://www.w3.org/XML/1998/namespace">
    <tei:div>
        <tei:p xml:id="external1">External content 1</tei:p>
        <tei:p xml:id="external2">External content 2</tei:p>
        <tei:p xml:id="external3" target="#external1">Reference to external1</tei:p>
    </tei:div>
</root>'''
        
        project, file_name = self._create_test_file("main.xml", main_xml_content)

        # Parse the external XML tree and compute actual element paths
        external_tree_root = etree.fromstring(external_xml_content)
        external_tree = external_tree_root.getroottree()
        xml_ns = 'http://www.w3.org/XML/1998/namespace'
        external1_elem = external_tree_root.xpath(
            "//*[@xml:id='external1']", namespaces={'xml': xml_ns})[0]
        external1_path = external_tree.getpath(external1_elem)

        # Mock XMLCache.parse_xml
        from opensiddur.exporter.linear import get_linear_data
        linear_data = get_linear_data()
        original_parse_xml = linear_data.xml_cache.parse_xml

        def mock_parse_xml(*args, **kwargs):
            if len(args) == 2 and args[0] == project and args[1] == file_name:
                # Main file - create a mock tree for the main file
                main_tree = MagicMock()
                main_tree.getroot.return_value = etree.fromstring(main_xml_content)
                return main_tree
            elif len(args) == 2 and args[0] == "external_project":
                # External file
                mock_tree = MagicMock()
                mock_tree.getroot.return_value = external_tree_root
                return mock_tree
            else:
                return original_parse_xml(*args, **kwargs)

        # Mock UrnResolver methods
        from opensiddur.exporter.urn import ResolvedUrn

        def mock_resolve_range(urn):
            if urn.startswith("#external1"):
                return [ResolvedUrn(urn=urn, project="external_project", file_name="external.xml",
                                   element_path=external1_path, end_element_path=external1_path)]
            return []

        def mock_prioritize_range(urns, priority_list, return_all=False):
            return urns[0] if urns else None

        def mock_get_path_from_urn(resolved_urn):
            from pathlib import Path
            return Path(self.temp_dir.name) / "external_project" / "external.xml"

        with patch.object(linear_data.xml_cache, 'parse_xml', side_effect=mock_parse_xml):
            with patch('opensiddur.exporter.compiler.UrnResolver.resolve_range', side_effect=mock_resolve_range):
                with patch('opensiddur.exporter.compiler.UrnResolver.prioritize_range', side_effect=mock_prioritize_range):
                    with patch('opensiddur.exporter.compiler.UrnResolver.get_path_from_urn', side_effect=mock_get_path_from_urn):
                        processor = CompilerProcessor(project, file_name)
                        result = processor.process()

        # Find the transclude elements (they use the processing namespace p:)
        transclude_elements = result.xpath(".//p:transclude", namespaces={"p": "http://jewishliturgy.org/ns/processing"})
        self.assertEqual(len(transclude_elements), 2, "Should have 2 transclude elements")
        
        # Get the transcluded content from each transclude element
        transclude1_children = list(transclude_elements[0])
        transclude2_children = list(transclude_elements[1])
        
        # Both transclusions should have content
        self.assertGreater(len(transclude1_children), 0, "First transclude should have content")
        self.assertGreater(len(transclude2_children), 0, "Second transclude should have content")
        
        # Extract all xml:id attributes from both transclusions
        all_ids_transclude1 = []
        all_ids_transclude2 = []
        
        for child in transclude1_children:
            xml_id = child.get("{http://www.w3.org/XML/1998/namespace}id")
            if xml_id:
                all_ids_transclude1.append(xml_id)
        
        for child in transclude2_children:
            xml_id = child.get("{http://www.w3.org/XML/1998/namespace}id")
            if xml_id:
                all_ids_transclude2.append(xml_id)
        
        # Both transclusions should have rewritten IDs
        self.assertGreater(len(all_ids_transclude1), 0, "First transclude should have rewritten IDs")
        self.assertGreater(len(all_ids_transclude2), 0, "Second transclude should have rewritten IDs")
        
        # Extract hash suffixes from the IDs
        def extract_hash_suffix(xml_id):
            if '_' in xml_id:
                return xml_id.split('_', 1)[1]
            return ""
        
        hash_suffixes_1 = [extract_hash_suffix(xml_id) for xml_id in all_ids_transclude1 if '_' in xml_id]
        hash_suffixes_2 = [extract_hash_suffix(xml_id) for xml_id in all_ids_transclude2 if '_' in xml_id]
        
        # All IDs within the same transclusion should have the same hash suffix
        if hash_suffixes_1:
            first_hash_1 = hash_suffixes_1[0]
            for hash_suffix in hash_suffixes_1:
                self.assertEqual(hash_suffix, first_hash_1, 
                               f"All IDs in first transclude should have same hash: {hash_suffixes_1}")
        
        if hash_suffixes_2:
            first_hash_2 = hash_suffixes_2[0]
            for hash_suffix in hash_suffixes_2:
                self.assertEqual(hash_suffix, first_hash_2, 
                               f"All IDs in second transclude should have same hash: {hash_suffixes_2}")
        
        # The two transclusions should have different hash suffixes (different processing paths)
        if hash_suffixes_1 and hash_suffixes_2:
            self.assertNotEqual(first_hash_1, first_hash_2, 
                              f"Same entity transcluded twice should have different hashes: {first_hash_1} vs {first_hash_2}")
        
        # Verify that the same base IDs exist in both transclusions but with different hashes
        def extract_base_id(xml_id):
            if '_' in xml_id:
                return xml_id.split('_')[0]
            return xml_id
        
        base_ids_1 = [extract_base_id(xml_id) for xml_id in all_ids_transclude1]
        base_ids_2 = [extract_base_id(xml_id) for xml_id in all_ids_transclude2]
        
        # The same base IDs should appear in both transclusions
        self.assertEqual(set(base_ids_1), set(base_ids_2), 
                        f"Both transclusions should have the same base IDs: {base_ids_1} vs {base_ids_2}")
        
        # But the full IDs (with hashes) should be different
        self.assertNotEqual(set(all_ids_transclude1), set(all_ids_transclude2), 
                           f"Full IDs with hashes should be different: {all_ids_transclude1} vs {all_ids_transclude2}")


class TestCompilerProcessorAnnotations(unittest.TestCase):
    """Test annotation inclusion functionality in CompilerProcessor."""

    def setUp(self):
        """Set up test fixtures and reset linear data."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_project_dir = Path(self.temp_dir.name) / "test_project"
        self.test_project_dir.mkdir(parents=True)
        
        # Patch the xml_cache base_path to use our temp directory
        # This creates coupling in the test, which is not good.
        self.linear_data = LinearData(
            instruction_priority=["priority_project", "test_project"],
            annotation_projects=["priority_project", "test_project"]
        )
        self.linear_data.xml_cache.base_path = Path(self.temp_dir.name)

        self.refdb = MagicMock(spec=ReferenceDatabase)
        # each test needs to set its own refdb results

    def _create_test_file(self, project: str, file_name: str, content: bytes) -> tuple[str, str]:
        """Create a test XML file and return (project, file_name) tuple."""
        project_dir = Path(self.temp_dir.name) / project
        project_dir.mkdir(parents=True, exist_ok=True)
        file_path = project_dir / file_name
        with open(file_path, 'wb') as f:
            f.write(content)
        xml = etree.parse(file_path)
        return project, file_name, xml

    def _create_instructional_note_file(self, project: str, 
        file_name: str, title: str, 
        urn: Optional[str], 
        content: str,
        xml_id: Optional[str]) -> tuple[str, str]:
        """Create a test file with an instructional note."""
        corresp = f"corresp='{urn}'" if urn else f"xml:id='{xml_id}'" if xml_id else ""
        xml_content = f'''<TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    <tei:teiHeader>
        <tei:fileDesc>
            <tei:titleStmt>
                <tei:title>{title}</tei:title>
            </tei:titleStmt>
        </tei:fileDesc>
    </tei:teiHeader>
    <tei:text>
        <tei:body>
            <tei:div>
                <tei:p>Element before note</tei:p>
                Text before note
                <tei:note type="instruction" {corresp}>
                    {content}
                </tei:note>
                Text after note
                <tei:p>Element after note</tei:p>
            </tei:div>
        </tei:body>
    </tei:text>
</TEI>'''.encode('utf-8')
        return self._create_test_file(project, file_name, xml_content)

    def _create_editorial_note_file(self, project: str, file_name: str, title: str, urn: str, content: str) -> tuple[str, str]:
        """Create a test file with an editorial note."""
        xml_content = f'''<TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    <tei:teiHeader>
        <tei:fileDesc>
            <tei:titleStmt>
                <tei:title>{title}</tei:title>
            </tei:titleStmt>
        </tei:fileDesc>
    </tei:teiHeader>
    <tei:standOff>
        <tei:note type="editorial" target="{urn}">
            {content}
        </tei:note>
    </tei:standOff>
</TEI>'''.encode('utf-8')
        return self._create_test_file(project, file_name, xml_content)

    def _create_targeted_note_file(self, project: str, 
        file_name: str, title: str, 
        urn: Optional[str],
        xml_id: Optional[str],
        internal_note: str = "") -> tuple[str, str]:
        """Create a test file with a target for a note."""
        corresp = f"corresp='{urn}'" if urn else f"xml:id='{xml_id}'" if xml_id else ""
        xml_content = f'''<TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    <tei:teiHeader>
        <tei:fileDesc>
            <tei:titleStmt>
                <tei:title>{title}</tei:title>
            </tei:titleStmt>
        </tei:fileDesc>
    </tei:teiHeader>
    <tei:text>
        <tei:body>
            <tei:div>
                <tei:p>Element before note</tei:p>
                Text before note
                <tei:p {corresp}>This element is targeted by the note <tei:hi>Child element</tei:hi></tei:p>
                Text after note
                <tei:p>Element after note</tei:p>
            </tei:div>
        </tei:body>
    </tei:text>
    <tei:standOff>
        {internal_note}
    </tei:standOff>
</TEI>'''.encode('utf-8')
        return self._create_test_file(project, file_name, xml_content)

    def test_instructional_note_with_urn_not_found_in_database(self):
        """Test that an instructional note with URN that is not found elsewhere is included as-is."""
        urn = "urn:test:instruction:nonexistent"
        
        # Create main file with instructional note with URN that won't be found in database
        project, file_name, _ = self._create_instructional_note_file("test_project", "main.xml", "Main Document", urn, "This is a local instruction", None)
        
        # all references will return nothing
        self.refdb.get_references_to.return_value = []
        self.refdb.get_urn_mappings.return_value = []
        
        processor = CompilerProcessor(project, file_name, self.linear_data, self.refdb)
        result = processor.process()
        
        # Find the note element
        notes = result.xpath(".//tei:note[@type='instruction']", namespaces=processor.ns_map)
        self.assertEqual(len(notes), 1)
        
        # Should contain the original text
        self.assertIn("This is a local instruction", notes[0].text.strip())
        
        # The instructional note itself should NOT have p:project and p:file_name attributes
        # since it's not transcluded from another file
        self.assertIsNone(notes[0].get(f"{{{processor.ns_map['p']}}}project"))
        self.assertIsNone(notes[0].get(f"{{{processor.ns_map['p']}}}file_name"))

    def test_instructional_note_with_no_corresp(self):
        """Test that an instructional note with no corresp or xml:id is included as-is."""
        urn = None
        xid= "wo_corresp"
        
        # Create main file with instructional note with URN that won't be found in database
        project, file_name, _ = self._create_instructional_note_file("test_project", "main.xml", "Main Document", urn, "This is a no corresp instruction", xid)
        
        # all references will return nothing
        self.refdb.get_references_to.return_value = []
        self.refdb.get_urn_mappings.return_value = []
        
        processor = CompilerProcessor(project, file_name, self.linear_data, self.refdb)
        result = processor.process()
        
        # Find the note element
        notes = result.xpath(".//tei:note[@type='instruction']", namespaces=processor.ns_map)
        self.assertEqual(len(notes), 1)
        
        # Should contain the original text
        self.assertIn("This is a no corresp instruction", notes[0].text.strip())
        
        # The instructional note itself should NOT have p:project and p:file_name attributes
        # since it's not transcluded from another file
        self.assertIsNone(notes[0].get(f"{{{processor.ns_map['p']}}}project"))
        self.assertIsNone(notes[0].get(f"{{{processor.ns_map['p']}}}file_name"))

    def test_instructional_note_with_no_corresp_or_xml_id(self):
        """Test that an instructional note with no corresp or xml:id is included as-is."""
        urn = None
        xid = None
        
        # Create main file with instructional note with URN that won't be found in database
        project, file_name, _ = self._create_instructional_note_file("test_project", "main.xml", "Main Document", urn, "This is a no corresp instruction", xid)
        
        # all references will return nothing
        self.refdb.get_references_to.return_value = []
        self.refdb.get_urn_mappings.return_value = []
        
        processor = CompilerProcessor(project, file_name, self.linear_data, self.refdb)
        result = processor.process()
        
        # Find the note element
        notes = result.xpath(".//tei:note[@type='instruction']", namespaces=processor.ns_map)
        self.assertEqual(len(notes), 1)
        
        # Should contain the original text
        self.assertIn("This is a no corresp instruction", notes[0].text.strip())
        
        # The instructional note itself should NOT have p:project and p:file_name attributes
        # since it's not transcluded from another file
        self.assertIsNone(notes[0].get(f"{{{processor.ns_map['p']}}}project"))
        self.assertIsNone(notes[0].get(f"{{{processor.ns_map['p']}}}file_name"))

    def test_instructional_note_with_alternative_urn_in_database(self):
        """Test that an instructional note with URN that is not found elsewhere is included as-is."""
        urn = "urn:test:instruction:alternative"
        
        # Create main file with instructional note with URN that won't be found in database
        project, file_name, xml = self._create_instructional_note_file("test_project", "main.xml", "Main Document", urn, "This is a local instruction", None)
        priority_project, priority_file_name, priority_xml = self._create_instructional_note_file("priority_project", "priority.xml", "Priority Document", urn, "This is a priority instruction", None)
        lxml_note_element = priority_xml.xpath("//tei:note[@type='instruction']", 
            namespaces={"tei": "http://www.tei-c.org/ns/1.0"})[0]
        lxml_note_element_path = lxml_note_element.getroottree().getpath(lxml_note_element)
        # all references will return nothing
        self.refdb.get_references_to.return_value = []
        self.refdb.get_urn_mappings.return_value = [
            UrnMapping(
                project=priority_project, 
                file_name=priority_file_name, 
                urn=urn, 
                element_path=lxml_note_element_path,
                element_tag="{http://www.tei-c.org/ns/1.0}note",
                element_type="instruction"
            )
        ]
        
        processor = CompilerProcessor(project, file_name, self.linear_data, self.refdb)
        result = processor.process()
        
        # Find the note element
        notes = result.xpath(".//tei:note[@type='instruction']", namespaces=processor.ns_map)
        self.assertEqual(len(notes), 1)
        
        # Should contain the priority instruction text
        self.assertIn("This is a priority instruction", notes[0].text.strip())
        
        # The instructional note itself should have p:project and p:file_name attributes
        self.assertEqual(notes[0].get(f"{{{processor.ns_map['p']}}}project"), priority_project)
        self.assertEqual(notes[0].get(f"{{{processor.ns_map['p']}}}file_name"), priority_file_name)

    def test_editorial_note_with_urn_in_database(self):
        """Test that an editorial note that targets the URN of an element."""
        urn = "urn:test:editorial:note"
        
        # Create main file with instructional note with URN that won't be found in database
        project, file_name, xml = self._create_targeted_note_file("test_project", "main.xml", "Main Document", urn, None)
        priority_project, priority_file_name, priority_xml = self._create_editorial_note_file("priority_project", "priority.xml", "Priority Document", urn, "Editorial note")
        lxml_note_element = priority_xml.xpath("//tei:note[@type='editorial']", 
            namespaces={"tei": "http://www.tei-c.org/ns/1.0"})[0]
        lxml_note_element_path = lxml_note_element.getroottree().getpath(lxml_note_element)
        # all references will return nothing
        self.refdb.get_references_to.reset_mock()
        self.refdb.get_references_to.return_value = [
            Reference(element_path=lxml_note_element_path, 
                element_tag="{http://www.tei-c.org/ns/1.0}note", 
                element_type="editorial",
                project=priority_project,
                file_name=priority_file_name,
                target_start=urn,
                target_end=None,
                target_is_id=False,
                corresponding_urn=None
            ),
            Reference(element_path=lxml_note_element_path, 
                element_tag="{http://www.tei-c.org/ns/1.0}something_else", 
                element_type="another",
                project=priority_project,
                file_name=priority_file_name,
                target_start=urn,
                target_end=None,
                target_is_id=False,
                corresponding_urn=None
            )
        ]
        
        
        processor = CompilerProcessor(project, file_name, self.linear_data, self.refdb)
        result = processor.process()
        
        # make sure refdb was called with the correct arguments
        self.refdb.get_references_to.assert_called_once_with(urn, None, None, None, element_tag="{http://www.tei-c.org/ns/1.0}note")

        # Find the note element
        notes = result.xpath(".//tei:note[@type='editorial']", namespaces=processor.ns_map)
        self.assertEqual(len(notes), 1)
        
        # Should contain the priority editorial note text
        self.assertIn("Editorial note", notes[0].text.strip())
        
        # The editorial note itself should have p:project and p:file_name attributes
        self.assertEqual(notes[0].get(f"{{{processor.ns_map['p']}}}project"), priority_project)
        self.assertEqual(notes[0].get(f"{{{processor.ns_map['p']}}}file_name"), priority_file_name)

        self.assertEqual(notes[0].getparent().tag, "{http://www.tei-c.org/ns/1.0}p")
        self.assertIn(notes[0].tail.strip(), "This element is targeted by the note <tei:hi>Child element</tei:hi>")
        self.assertIs(notes[0].getparent().getchildren()[0], notes[0])

    def test_editorial_note_with_xml_id_in_database(self):
        """Test that an editorial note that targets the xml:id of an element."""
        
        # Create main file with instructional note with URN that won't be found in database
        project, file_name, xml = self._create_targeted_note_file("test_project", "main.xml", "Main Document", None, "note_id", 
            '<tei:note target="#note_id" type="editorial">Editorial note</tei:note>')
        lxml_note_element = xml.xpath("//tei:note[@type='editorial']", 
            namespaces={"tei": "http://www.tei-c.org/ns/1.0"})[0]
        lxml_note_element_path = lxml_note_element.getroottree().getpath(lxml_note_element)
        self.refdb.get_references_to.reset_mock()
        self.refdb.get_references_to.return_value = [
            Reference(element_path=lxml_note_element_path, 
                element_tag="{http://www.tei-c.org/ns/1.0}note", 
                element_type="editorial",
                project=project,
                file_name=file_name,
                target_start="#note_id",
                target_end=None,
                target_is_id=True,
                corresponding_urn=None
            )
        ]
        
        
        processor = CompilerProcessor(project, file_name, self.linear_data, self.refdb)
        result = processor.process()
        
        # make sure refdb was called with the correct arguments
        self.refdb.get_references_to.assert_called_once_with(None, "note_id", project, file_name, element_tag="{http://www.tei-c.org/ns/1.0}note")

        # Find the new note element
        notes = result.xpath(".//tei:body//tei:note[@type='editorial']", namespaces=processor.ns_map)
        self.assertEqual(len(notes), 1)
        
        # Should contain the priority editorial note text
        self.assertIn("Editorial note", notes[0].text.strip())
        
        # The editorial note itself should NOT have p:project and p:file_name attributes
        self.assertIsNone(notes[0].get(f"{{{processor.ns_map['p']}}}project"))
        self.assertIsNone(notes[0].get(f"{{{processor.ns_map['p']}}}file_name"))

        self.assertEqual(notes[0].getparent().tag, "{http://www.tei-c.org/ns/1.0}p")
        self.assertIn(notes[0].tail.strip(), "This element is targeted by the note <tei:hi>Child element</tei:hi>")
        self.assertIs(notes[0].getparent().getchildren()[0], notes[0])


def _linear_data_with_root(root: etree._Element):
    class _XmlCache:
        @staticmethod
        def parse_xml(project: str, file_name: str):
            return etree.ElementTree(root)

    class _LD:
        xml_cache = _XmlCache()
        processing_context = [{"project": "ctx", "file_name": "ctx.xml"}]
        parallel_projects = []
        project_priority = ["p"]
        instruction_priority = ["p"]
        transclusion_chain = []
        index_checked = set()
        credits = []

    return _LD()


class TestCompilerTranscludeTextOnly(unittest.TestCase):
    """Targeted tests for external transclusion text extraction (compiler.py 276–290)."""

    TEI_NS = "http://www.tei-c.org/ns/1.0"

    def _make_processor(self):
        root = etree.Element(f"{{{self.TEI_NS}}}TEI", nsmap={"tei": self.TEI_NS, "j": JLPTEI_NAMESPACE})
        return CompilerProcessor("p", "root.xml", linear_data=_linear_data_with_root(root))

    @staticmethod
    def _fake_range():
        return ResolvedUrnRange(
            start=ResolvedUrn(project="p", file_name="x.xml", urn="u", element_path="/a"),
            end=ResolvedUrn(project="p", file_name="x.xml", urn="u", element_path="/b", end_includes_tail=False),
        )

    def test_external_transclude_extracts_text_children(self):
        proc = self._make_processor()
        transclude_el = etree.Element(f"{{{JLPTEI_NAMESPACE}}}transclude", nsmap=proc.ns_map)
        transclude_el.set("target", "urn:test")

        tei = etree.Element(f"{{{self.TEI_NS}}}TEI", nsmap={"tei": self.TEI_NS})
        tei_header = etree.SubElement(tei, f"{{{self.TEI_NS}}}teiHeader")
        etree.SubElement(tei_header, f"{{{self.TEI_NS}}}fileDesc")
        text = etree.SubElement(tei, f"{{{self.TEI_NS}}}text")
        body = etree.SubElement(text, f"{{{self.TEI_NS}}}body")
        p = etree.SubElement(body, f"{{{self.TEI_NS}}}p")
        p.text = "hello"

        class FakeExternal:
            def __init__(self, *args, **kwargs):
                self.root_language = None

            def process(self):
                return [tei]

            def _mark_file_source(self, element, **_):
                return element

        with (
            patch.object(proc, "_get_start_and_end_from_ranges", return_value=self._fake_range()),
            patch("opensiddur.exporter.external_compiler.ExternalCompilerProcessor", FakeExternal),
        ):
            out = proc._transclude(transclude_el)

        self.assertIsNotNone(out)
        children_tags = [c.tag for c in list(out)]
        self.assertIn(f"{{{self.TEI_NS}}}body", children_tags)
        self.assertNotIn(f"{{{self.TEI_NS}}}TEI", children_tags)

    def test_external_transclude_falls_back_to_body_when_text_missing(self):
        proc = self._make_processor()
        transclude_el = etree.Element(f"{{{JLPTEI_NAMESPACE}}}transclude", nsmap=proc.ns_map)
        transclude_el.set("target", "urn:test")

        tei = etree.Element(f"{{{self.TEI_NS}}}TEI", nsmap={"tei": self.TEI_NS})
        body = etree.SubElement(tei, f"{{{self.TEI_NS}}}body")
        p = etree.SubElement(body, f"{{{self.TEI_NS}}}p")
        p.text = "fallback"

        class FakeExternal:
            def __init__(self, *args, **kwargs):
                self.root_language = None

            def process(self):
                return [tei]

            def _mark_file_source(self, element, **_):
                return element

        with (
            patch.object(proc, "_get_start_and_end_from_ranges", return_value=self._fake_range()),
            patch("opensiddur.exporter.external_compiler.ExternalCompilerProcessor", FakeExternal),
        ):
            out = proc._transclude(transclude_el)

        self.assertIsNotNone(out)
        children_tags = [c.tag for c in list(out)]
        self.assertIn(f"{{{self.TEI_NS}}}p", [gc.tag for c in list(out) for gc in list(c.iter())])
        self.assertNotIn(f"{{{self.TEI_NS}}}TEI", children_tags)


class TestSubverseCoarsening(unittest.TestCase):
    """A reference below the verse falls back on the verse where no project divides finer."""

    TEI_NS = "http://www.tei-c.org/ns/1.0"
    VERSE = "urn:x-opensiddur:text:bible:genesis/1/31"

    def _processor(self):
        root = etree.Element(f"{{{self.TEI_NS}}}TEI", nsmap={"tei": self.TEI_NS, "j": JLPTEI_NAMESPACE})
        return CompilerProcessor("p", "root.xml", linear_data=_linear_data_with_root(root))

    def _resolver_carrying(self, *urns):
        """A resolver that knows only `urns`, all in project 'p'."""
        known = set(urns)

        def resolve(urn):
            actual = urn.rsplit("@", 1)[0] if "@" in urn else urn
            if actual not in known:
                return []
            return [ResolvedUrn(project="p", file_name="genesis.xml", urn=actual,
                                element_path="/a", end_element_path="/b")]

        resolver = Mock()
        resolver.resolve_range.side_effect = lambda urn: (
            resolve(urn) if split_range(urn) is None else self._resolve_range(urn, resolve)
        )
        return resolver

    @staticmethod
    def _resolve_range(urn, resolve):
        start_urn, end_urn = split_range(urn)
        start, end = resolve(start_urn), resolve(end_urn)
        if not start or not end:
            return []
        return [ResolvedUrnRange(start=start[0], end=end[0])]

    def test_falls_back_to_the_verse_when_no_project_has_the_half(self):
        proc = self._processor()
        proc._urn_resolver = self._resolver_carrying(self.VERSE)

        with self.assertLogs("opensiddur.exporter.compiler", level="WARNING") as logs:
            result = proc._get_start_and_end_from_ranges(f"{self.VERSE}/b")

        self.assertEqual(result.start.urn, self.VERSE)
        self.assertIn(f"{self.VERSE}/b", "".join(logs.output))
        self.assertIn("more text than the reference asks for", "".join(logs.output))

    def test_uses_the_half_when_a_project_has_it(self):
        proc = self._processor()
        proc._urn_resolver = self._resolver_carrying(self.VERSE, f"{self.VERSE}/b")

        result = proc._get_start_and_end_from_ranges(f"{self.VERSE}/b")

        self.assertEqual(result.start.urn, f"{self.VERSE}/b")

    def test_a_range_below_the_verse_coarsens_at_both_ends(self):
        proc = self._processor()
        proc._urn_resolver = self._resolver_carrying(
            "urn:x-opensiddur:text:bible:nahum/2/2", "urn:x-opensiddur:text:bible:nahum/2/3")

        with self.assertLogs("opensiddur.exporter.compiler", level="WARNING"):
            result = proc._get_start_and_end_from_ranges(
                "urn:x-opensiddur:text:bible:nahum/2/2/b-2/3/a")

        self.assertEqual(result.start.urn, "urn:x-opensiddur:text:bible:nahum/2/2")
        self.assertEqual(result.end.urn, "urn:x-opensiddur:text:bible:nahum/2/3")

    def test_a_reference_to_nothing_at_all_still_raises(self):
        """Coarsening is for a division a project lacks, not for a URN that does not exist."""
        proc = self._processor()
        proc._urn_resolver = self._resolver_carrying("urn:x-opensiddur:text:bible:exodus/1/1")

        with self.assertRaises(ValueError):
            proc._get_start_and_end_from_ranges(f"{self.VERSE}/b")


class TestCompilerMain(unittest.TestCase):
    """Tests for compiler CLI main()."""

    @patch("opensiddur.exporter.external_compiler.ExternalCompilerProcessor")
    @patch("opensiddur.exporter.settings.load_default_settings")
    @patch("opensiddur.exporter.compiler.reset_linear_data")
    def test_main_uses_project_directory(
        self,
        mock_reset_linear_data,
        mock_load_default_settings,
        mock_processor_class,
    ):
        from opensiddur.exporter.compiler import main as compiler_main

        mock_linear_data = MagicMock()
        mock_load_default_settings.return_value = mock_linear_data
        mock_processor = MagicMock()
        mock_processor.process.return_value = [etree.Element("root")]
        mock_processor_class.return_value = mock_processor

        project_dir = Path("/custom/project")
        with tempfile.TemporaryDirectory() as td:
            output_file = Path(td) / "out.xml"
            compiler_main([
                "--project", "wlc",
                "--file_name", "genesis.xml",
                "--output_file", str(output_file),
                "--project-directory", str(project_dir),
            ])

        mock_load_default_settings.assert_called_once()
        _, kwargs = mock_load_default_settings.call_args
        self.assertEqual(kwargs["project_directory"], project_dir.resolve())
        mock_processor_class.assert_called_once_with(
            "wlc",
            "genesis.xml",
            linear_data=mock_linear_data,
        )



class TestGatherCredits(unittest.TestCase):
    """Whoever digitised a text is credited for it, wherever the text came from.

    A transcluded document contributes its words and not its header, so its credits are
    taken at the moment the header is dropped. Without that, a document built out of two
    dozen files names the contributors of whichever one happened to be the root.
    """

    TEI = "http://www.tei-c.org/ns/1.0"

    def document(self, *names):
        from lxml import etree as _etree

        stmts = "".join(
            f'<tei:respStmt><tei:resp key="trc">Transcribed by</tei:resp>'
            f'<tei:name ref="urn:x-opensiddur:contributor:he.wikisource.org/{name}">'
            f"{name}</tei:name></tei:respStmt>" for name in names)
        return _etree.fromstring(
            f'<tei:TEI xmlns:tei="{self.TEI}"><tei:teiHeader><tei:fileDesc>'
            f"<tei:titleStmt><tei:title>t</tei:title>{stmts}</tei:titleStmt>"
            "</tei:fileDesc></tei:teiHeader><tei:text><tei:body/></tei:text></tei:TEI>")

    def credited(self, root):
        return [name.text for name in root.iter(f"{{{self.TEI}}}name")]

    def setUp(self):
        from opensiddur.exporter.linear import LinearData

        self.linear_data = LinearData()

    def test_a_transcluded_documents_contributors_reach_the_compiled_text(self):
        from opensiddur.exporter.compiler import gather_credits, merge_credits

        root = self.document("Dovi")
        gather_credits(self.document("Neriah"), self.linear_data)
        merge_credits(root, self.linear_data)
        self.assertEqual(self.credited(root), ["Dovi", "Neriah"])

    def test_the_same_person_is_credited_once(self):
        from opensiddur.exporter.compiler import gather_credits, merge_credits

        root = self.document("Dovi")
        gather_credits(self.document("Nahum", "Dovi"), self.linear_data)
        merge_credits(root, self.linear_data)
        self.assertEqual(self.credited(root), ["Dovi", "Nahum"])

    def test_the_roots_own_contributors_are_kept(self):
        from opensiddur.exporter.compiler import merge_credits

        root = self.document("Dovi")
        merge_credits(root, self.linear_data)
        self.assertEqual(self.credited(root), ["Dovi"])

    def test_what_each_person_did_travels_with_their_name(self):
        from opensiddur.exporter.compiler import gather_credits, merge_credits

        root = self.document("Dovi")
        gather_credits(self.document("Neriah"), self.linear_data)
        merge_credits(root, self.linear_data)
        added = root.findall(f".//{{{self.TEI}}}respStmt")[-1]
        self.assertEqual(added.find(f"{{{self.TEI}}}resp").get("key"), "trc")
        self.assertEqual(added.find(f"{{{self.TEI}}}name").get("ref"),
                         "urn:x-opensiddur:contributor:he.wikisource.org/Neriah")

    def test_contributors_without_a_urn_are_told_apart_by_name(self):
        from lxml import etree as _etree

        from opensiddur.exporter.compiler import gather_credits, merge_credits

        def unreferenced(*names):
            stmts = "".join(
                f'<tei:respStmt><tei:resp key="trc">Transcribed by</tei:resp>'
                f"<tei:name>{name}</tei:name></tei:respStmt>" for name in names)
            return _etree.fromstring(
                f'<tei:TEI xmlns:tei="{self.TEI}"><tei:teiHeader><tei:fileDesc>'
                f"<tei:titleStmt><tei:title>t</tei:title>{stmts}</tei:titleStmt>"
                "</tei:fileDesc></tei:teiHeader><tei:text><tei:body/></tei:text></tei:TEI>")

        root = unreferenced("Avigail")
        gather_credits(unreferenced("Batya", "Avigail"), self.linear_data)
        merge_credits(root, self.linear_data)
        self.assertEqual(self.credited(root), ["Avigail", "Batya"])

    def test_a_document_with_no_title_statement_is_left_alone(self):
        from lxml import etree as _etree

        from opensiddur.exporter.compiler import gather_credits, merge_credits

        gather_credits(self.document("Neriah"), self.linear_data)
        bare = _etree.fromstring(f'<tei:TEI xmlns:tei="{self.TEI}"><tei:text/></tei:TEI>')
        merge_credits(bare, self.linear_data)
        self.assertEqual(self.credited(bare), [])
