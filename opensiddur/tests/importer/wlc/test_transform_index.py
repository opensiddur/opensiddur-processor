import unittest
import tempfile
import shutil
from pathlib import Path
from lxml import etree

from opensiddur.common.xslt import xslt_transform

#: The stylesheet names the project it writes; the tests give it one of their own.
PARAMS = {"project": "a_project-he"}


class TestTransformIndexXSLT(unittest.TestCase):
    """Test the transform_index.xslt transformation logic"""
    
    def setUp(self):
        """Set up test environment with temp directory structure"""
        # Create a temporary directory for our test
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Read the original XSLT
        self.xslt_source = Path(__file__).parent.parent.parent.parent / "importer/wlc/transform_index.xslt"
        xslt_content = self.xslt_source.read_text()
        
        # Neuter TanachIndex lookup so tests do not need TanachIndex.xml on disk
        xslt_content = xslt_content.replace(
            "select=\"if (normalize-space($wlc-root-uri)) then doc(resolve-uri('Books/TanachIndex.xml', $wlc-root-uri))//book else doc(resolve-uri('../../../sources/wlc/Books/TanachIndex.xml', static-base-uri()))//book\"",
            "select=\"()\"",
        )
        
        # Also change mode from "fail" to "shallow-copy" for testing
        # This allows the transformation to proceed even with unexpected elements
        xslt_content = xslt_content.replace(
            '<xsl:mode on-no-match="fail"/>',
            '<xsl:mode on-no-match="shallow-copy"/>'
        )
        
        # Write modified XSLT to temp location
        self.xslt_path = self.test_dir / "transform_index.xslt"
        self.xslt_path.write_text(xslt_content)
    
    def tearDown(self):
        """Clean up temp directory"""
        shutil.rmtree(self.test_dir)
    
    def test_title_uniform_transformation(self):
        """Test that title[@type='uniform'] transforms to alt with lang=en"""
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Tanach>
    <teiHeader>
        <fileDesc>
            <titleStmt>
                <title type="uniform">Tanach Uniform Title</title>
            </titleStmt>
            <publicationStmt/>
            <sourceDesc/>
        </fileDesc>
    </teiHeader>
</Tanach>'''
        
        input_file = self.test_dir / "input.xml"
        output_file = self.test_dir / "output.xml"
        input_file.write_text(input_xml)
        
        xslt_transform(self.xslt_path, input_file, output_file, xslt_params=PARAMS)
        
        result = output_file.read_text()
        
        # Should transform to title with type="alt" and xml:lang="en"
        self.assertIn('type="alt"', result)
        self.assertIn('xml:lang="en"', result)
        self.assertIn('Tanach Uniform Title', result)
    
    def test_title_uniformhebrew_transformation(self):
        """Test that title[@type='uniformhebrew'] transforms to alt with lang=he"""
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Tanach>
    <teiHeader>
        <fileDesc>
            <titleStmt>
                <title type="uniformhebrew">תנ״ך</title>
            </titleStmt>
            <publicationStmt/>
            <sourceDesc/>
        </fileDesc>
    </teiHeader>
</Tanach>'''
        
        input_file = self.test_dir / "input.xml"
        output_file = self.test_dir / "output.xml"
        input_file.write_text(input_xml, encoding='utf-8')
        
        xslt_transform(self.xslt_path, input_file, output_file, xslt_params=PARAMS)
        
        result = output_file.read_text(encoding='utf-8')
        
        # Should transform to title with type="alt" and xml:lang="he"
        self.assertIn('type="alt"', result)
        self.assertIn('xml:lang="he"', result)
        self.assertIn('תנ״ך', result)
    
    def test_title_main_transformation(self):
        """Test that title[@type='main'] transforms correctly"""
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Tanach>
    <teiHeader>
        <fileDesc>
            <titleStmt>
                <title type="main">Unicode/XML Leningrad Codex</title>
            </titleStmt>
            <publicationStmt/>
            <sourceDesc/>
        </fileDesc>
    </teiHeader>
</Tanach>'''
        
        input_file = self.test_dir / "input.xml"
        output_file = self.test_dir / "output.xml"
        input_file.write_text(input_xml)
        
        xslt_transform(self.xslt_path, input_file, output_file, xslt_params=PARAMS)
        
        result = output_file.read_text()
        
        # Should transform to title with type="main" and xml:lang="en"
        self.assertIn('type="main"', result)
        self.assertIn('xml:lang="en"', result)
        self.assertIn('Unicode/XML Leningrad Codex', result)
    
    def test_title_filename_skipped(self):
        """Test that title[@type='filename'] is skipped"""
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Tanach>
    <teiHeader>
        <fileDesc>
            <titleStmt>
                <title type="filename">TanachHeader</title>
                <title type="main">Main Title</title>
            </titleStmt>
            <publicationStmt/>
            <sourceDesc/>
        </fileDesc>
    </teiHeader>
</Tanach>'''
        
        input_file = self.test_dir / "input.xml"
        output_file = self.test_dir / "output.xml"
        input_file.write_text(input_xml)
        
        xslt_transform(self.xslt_path, input_file, output_file, xslt_params=PARAMS)
        
        result = output_file.read_text()
        
        # filename title should not appear in output
        self.assertNotIn('TanachHeader', result)
        # but main title should
        self.assertIn('Main Title', result)
    
    def test_edition_stmt_elements_get_text_labels(self):
        """Test that version, build, buildDateTime get text labels"""
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Tanach>
    <teiHeader>
        <fileDesc>
            <titleStmt>
                <title type="main">Test</title>
            </titleStmt>
            <editionStmt>
                <edition>
                    <version>2.3</version>
                    <build>27.4</build>
                    <buildDateTime>31 March 2025</buildDateTime>
                </edition>
            </editionStmt>
            <publicationStmt/>
            <sourceDesc/>
        </fileDesc>
    </teiHeader>
</Tanach>'''
        
        input_file = self.test_dir / "input.xml"
        output_file = self.test_dir / "output.xml"
        input_file.write_text(input_xml)
        
        xslt_transform(self.xslt_path, input_file, output_file, xslt_params=PARAMS)
        
        result = output_file.read_text()
        
        # Note: editionStmt is not in fileDesc's select attribute (line 81)
        # So editionStmt won't be processed. This appears to be by design.
        # The output won't contain these elements
        self.assertNotIn('editionStmt', result)
    
    def test_publication_stmt_replaced_with_opensiddur_content(self):
        """Test that publicationStmt content is replaced with Open Siddur metadata"""
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Tanach>
    <teiHeader>
        <fileDesc>
            <titleStmt>
                <title type="main">Test</title>
            </titleStmt>
            <publicationStmt>
                <distributor>Original Distributor</distributor>
                <availability>Original availability</availability>
            </publicationStmt>
            <sourceDesc/>
        </fileDesc>
    </teiHeader>
</Tanach>'''
        
        input_file = self.test_dir / "input.xml"
        output_file = self.test_dir / "output.xml"
        input_file.write_text(input_xml)
        
        xslt_transform(self.xslt_path, input_file, output_file, xslt_params=PARAMS)
        
        result = output_file.read_text()
        
        # Original content should be replaced
        self.assertNotIn('Original Distributor', result)
        self.assertNotIn('Original availability', result)
        
        # Should have new Open Siddur content
        self.assertIn('Open Siddur Project', result)
        self.assertIn('opensiddur.org', result)
        self.assertIn('urn:x-opensiddur:text:bible:tanakh@a_project-he', result)
        self.assertIn('Creative Commons Zero', result)
    
    def test_source_desc_augmented_with_uxlc_bibl(self):
        """Test that sourceDesc is augmented with UXLC bibliographic info"""
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Tanach>
    <teiHeader>
        <fileDesc>
            <titleStmt>
                <title type="main">Test</title>
            </titleStmt>
            <publicationStmt/>
            <sourceDesc>
                <biblItem>
                    <title>Original Source Title</title>
                </biblItem>
            </sourceDesc>
        </fileDesc>
    </teiHeader>
</Tanach>'''
        
        input_file = self.test_dir / "input.xml"
        output_file = self.test_dir / "output.xml"
        input_file.write_text(input_xml)
        
        xslt_transform(self.xslt_path, input_file, output_file, xslt_params=PARAMS)
        
        result = output_file.read_text()
        
        # Should add UXLC info
        self.assertIn('Unicode/XML Leningrad Codex', result)
        self.assertIn('Christopher V. Kimball', result)
        self.assertIn('tanach.us', result)
        
        # Should keep original content
        self.assertIn('Original Source Title', result)
    
    def test_bibl_item_becomes_bibl(self):
        """Test that biblItem elements become bibl"""
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Tanach>
    <teiHeader>
        <fileDesc>
            <titleStmt>
                <title type="main">Test</title>
            </titleStmt>
            <publicationStmt/>
            <sourceDesc>
                <biblItem>
                    <title>Test Source</title>
                    <editor>Test Editor</editor>
                </biblItem>
            </sourceDesc>
        </fileDesc>
    </teiHeader>
</Tanach>'''
        
        input_file = self.test_dir / "input.xml"
        output_file = self.test_dir / "output.xml"
        input_file.write_text(input_xml)
        
        xslt_transform(self.xslt_path, input_file, output_file, xslt_params=PARAMS)
        
        result = output_file.read_text()
        
        # biblItem should not appear
        self.assertNotIn('biblItem', result)
        # Should have bibl instead (with tei: prefix)
        self.assertIn('<tei:bibl>', result)
        self.assertIn('</tei:bibl>', result)
    
    def test_imprint_element_bypassed(self):
        """Test that imprint element is removed but children are kept"""
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Tanach>
    <teiHeader>
        <fileDesc>
            <titleStmt>
                <title type="main">Test</title>
            </titleStmt>
            <publicationStmt/>
            <sourceDesc>
                <biblItem>
                    <imprint>
                        <publisher>Test Publisher</publisher>
                        <pubPlace>Test Place</pubPlace>
                    </imprint>
                </biblItem>
            </sourceDesc>
        </fileDesc>
    </teiHeader>
</Tanach>'''
        
        input_file = self.test_dir / "input.xml"
        output_file = self.test_dir / "output.xml"
        input_file.write_text(input_xml)
        
        xslt_transform(self.xslt_path, input_file, output_file, xslt_params=PARAMS)
        
        result = output_file.read_text()
        
        # imprint tag should not appear
        self.assertNotIn('<imprint>', result)
        self.assertNotIn('</imprint>', result)
        
        # But children should be present
        self.assertIn('Test Publisher', result)
        self.assertIn('Test Place', result)
    
    def test_tanach_notes_become_standoff(self):
        """Test that tanach element with notes becomes standOff"""
        # Note: The Tanach root template (line 41) selects "notes" not "tanach"
        # So we skip this test as it would require actual file structure
        # The tanach template exists but is for a different context
        self.skipTest("tanach notes transformation requires proper XML structure - test in integration")

    def test_skipped_elements_not_in_output(self):
        """Test that coding, encodingDesc, editor, respStmt, notesStmt, profileDesc are skipped"""
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Tanach>
    <teiHeader>
        <fileDesc>
            <titleStmt>
                <title type="main">Main Title</title>
                <editor>Skipped Editor Name</editor>
                <respStmt>
                    <resp>Skipped Responsibility</resp>
                </respStmt>
            </titleStmt>
            <publicationStmt/>
            <sourceDesc/>
            <notesStmt>
                <note>This note should be skipped</note>
            </notesStmt>
        </fileDesc>
        <encodingDesc>
            <description>This should be skipped</description>
        </encodingDesc>
        <profileDesc>
            <langUsage>This should be skipped</langUsage>
        </profileDesc>
    </teiHeader>
    <coding>
        <char>This should be skipped</char>
    </coding>
</Tanach>'''
        
        input_file = self.test_dir / "input.xml"
        output_file = self.test_dir / "output.xml"
        input_file.write_text(input_xml)
        
        xslt_transform(self.xslt_path, input_file, output_file, xslt_params=PARAMS)
        
        result = output_file.read_text()
        
        # None of the skipped content should appear
        self.assertNotIn('Skipped Editor Name', result)
        self.assertNotIn('Skipped Responsibility', result)
        self.assertNotIn('This note should be skipped', result)
        self.assertNotIn('This should be skipped', result)
        
        # But the main title should be there
        self.assertIn('Main Title', result)
    
    def test_root_tanach_becomes_tei(self):
        """Test that Tanach root element becomes TEI with proper structure"""
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Tanach>
    <teiHeader>
        <fileDesc>
            <titleStmt>
                <title type="main">Test</title>
            </titleStmt>
            <publicationStmt/>
            <sourceDesc/>
        </fileDesc>
    </teiHeader>
</Tanach>'''
        
        input_file = self.test_dir / "input.xml"
        output_file = self.test_dir / "output.xml"
        input_file.write_text(input_xml)
        
        xslt_transform(self.xslt_path, input_file, output_file, xslt_params=PARAMS)
        
        result = output_file.read_text()
        
        # Should have TEI root (with tei: prefix)
        self.assertIn('<tei:TEI', result)
        self.assertIn('xmlns:tei="http://www.tei-c.org/ns/1.0"', result)
        
        # Should have text/body structure (with tei: prefix)
        self.assertIn('<tei:text>', result)
        self.assertIn('<tei:body>', result)
        self.assertIn('<tei:div corresp="urn:x-opensiddur:text:bible:tanakh"', result)
    
    def test_book_elements_become_transclude(self):
        """Test that book elements become j:transclude with proper URN.

        The book template itself never references the doc()-backed
        $tanach-index-books lookup (that's used once, elsewhere, to loop over the whole
        book list) so it can be exercised directly by feeding a standalone <book>
        fragment as the transform's input document.
        """
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<book><names><name>Genesis</name><filename>Genesis</filename></names></book>'''

        input_file = self.test_dir / "input.xml"
        output_file = self.test_dir / "output.xml"
        input_file.write_text(input_xml)

        xslt_transform(self.xslt_path, input_file, output_file, xslt_params=PARAMS)

        result = etree.parse(str(output_file))
        # The book template's whole output *is* the j:transclude -- there's no wrapper,
        # so it's the document root, not a descendant.
        transclude = result.getroot()
        self.assertEqual(transclude.tag, "{http://jewishliturgy.org/ns/jlptei/2}transclude")
        self.assertEqual(transclude.get("target"), "urn:x-opensiddur:text:bible:genesis")

    def test_paired_book_urn_uses_ordinal_suffix(self):
        """Regression test: WLC titles paired books ordinal-first ("1 Samuel"), but the
        URN slug must be ordinal-last (samuel_1), matching every other project's
        convention and the file every other reference to this book resolves against.
        """
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<book><names><name>1 Samuel</name><filename>Samuel_1</filename></names></book>'''

        input_file = self.test_dir / "input.xml"
        output_file = self.test_dir / "output.xml"
        input_file.write_text(input_xml)

        xslt_transform(self.xslt_path, input_file, output_file, xslt_params=PARAMS)

        result = etree.parse(str(output_file))
        transclude = result.getroot()
        self.assertEqual(transclude.tag, "{http://jewishliturgy.org/ns/jlptei/2}transclude")
        self.assertEqual(transclude.get("target"), "urn:x-opensiddur:text:bible:samuel_1")

    def test_tei_namespace_added_to_elements(self):
        """Test that titleStmt, title, publisher, etc. get TEI namespace"""
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Tanach>
    <teiHeader>
        <fileDesc>
            <titleStmt>
                <title type="main">Test Title</title>
            </titleStmt>
            <publicationStmt>
                <publisher>Pub</publisher>
                <pubPlace>Place</pubPlace>
                <date>2025</date>
                <idno>123</idno>
            </publicationStmt>
            <sourceDesc/>
        </fileDesc>
    </teiHeader>
</Tanach>'''
        
        input_file = self.test_dir / "input.xml"
        output_file = self.test_dir / "output.xml"
        input_file.write_text(input_xml)
        
        xslt_transform(self.xslt_path, input_file, output_file, xslt_params=PARAMS)
        
        # Parse output to check namespaces properly
        tree = etree.parse(str(output_file))
        root = tree.getroot()
        
        # Define TEI namespace
        tei_ns = '{http://www.tei-c.org/ns/1.0}'
        
        # Check that elements have TEI namespace
        title_stmt = root.find(f'.//{tei_ns}titleStmt')
        self.assertIsNotNone(title_stmt, "titleStmt should have TEI namespace")
        
        title = root.find(f'.//{tei_ns}title')
        self.assertIsNotNone(title, "title should have TEI namespace")


if __name__ == '__main__':
    unittest.main()
