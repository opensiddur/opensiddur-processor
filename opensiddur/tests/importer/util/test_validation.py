import unittest
import tempfile
from pathlib import Path
from lxml import etree

from opensiddur.importer.util.validation import schematron_validate, relaxng_validate, validate, validate_with_start, _add_missing_namespaces


class TestSchematronValidate(unittest.TestCase):
    """Test the schematron_validate function"""
    
    def test_schematron_validation_success(self):
        """Test successful schematron validation (no failed asserts)"""
        # Create a simple schematron XSLT that checks for required element
        schematron_xslt = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:svrl="http://purl.oclc.org/dsdl/svrl">
    
    <xsl:output method="xml" indent="yes"/>
    
    <xsl:template match="/">
        <svrl:schematron-output>
            <!-- No failed-assert means valid -->
            <xsl:if test="not(//required)">
                <svrl:failed-assert location="root">
                    <svrl:text>Missing required element</svrl:text>
                </svrl:failed-assert>
            </xsl:if>
        </svrl:schematron-output>
    </xsl:template>
</xsl:stylesheet>'''
        
        # XML that should pass (has required element)
        valid_xml = '<root><required>present</required></root>'
        
        # Test with string input (no temp file needed)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as f:
            f.write(schematron_xslt)
            f.flush()
            
            is_valid, errors = schematron_validate(valid_xml, Path(f.name))
            
            # Should be valid with no errors
            self.assertTrue(is_valid)
            self.assertEqual(errors, [])
    
    def test_schematron_validation_failure(self):
        """Test failed schematron validation (with failed asserts)"""
        # Create a schematron XSLT that requires a specific attribute
        schematron_xslt = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:svrl="http://purl.oclc.org/dsdl/svrl">
    
    <xsl:output method="xml" indent="yes"/>
    
    <xsl:template match="/">
        <svrl:schematron-output>
            <xsl:if test="not(//item[@required='yes'])">
                <svrl:failed-assert location="/root/item">
                    <svrl:text>Item must have required='yes' attribute</svrl:text>
                </svrl:failed-assert>
            </xsl:if>
        </svrl:schematron-output>
    </xsl:template>
</xsl:stylesheet>'''
        
        # XML that should fail (missing required attribute)
        invalid_xml = '<root><item>content</item></root>'
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as f:
            f.write(schematron_xslt)
            f.flush()
            
            is_valid, errors = schematron_validate(invalid_xml, Path(f.name))
            
            # Should be invalid with errors
            self.assertFalse(is_valid)
            self.assertGreater(len(errors), 0)
            self.assertIn('/root/item', errors[0])
            self.assertIn('required', errors[0])
    
    def test_schematron_multiple_errors(self):
        """Test schematron validation with multiple failed asserts"""
        schematron_xslt = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:svrl="http://purl.oclc.org/dsdl/svrl">
    
    <xsl:output method="xml" indent="yes"/>
    
    <xsl:template match="/">
        <svrl:schematron-output>
            <xsl:if test="not(//title)">
                <svrl:failed-assert location="/root">
                    <svrl:text>Missing title element</svrl:text>
                </svrl:failed-assert>
            </xsl:if>
            <xsl:if test="not(//author)">
                <svrl:failed-assert location="/root">
                    <svrl:text>Missing author element</svrl:text>
                </svrl:failed-assert>
            </xsl:if>
        </svrl:schematron-output>
    </xsl:template>
</xsl:stylesheet>'''
        
        # XML missing both title and author
        invalid_xml = '<root><content>data</content></root>'
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as f:
            f.write(schematron_xslt)
            f.flush()
            
            is_valid, errors = schematron_validate(invalid_xml, Path(f.name))
            
            # Should have 2 errors
            self.assertFalse(is_valid)
            self.assertEqual(len(errors), 2)
            # Both errors should mention /root
            self.assertTrue(all('/root' in err for err in errors))
    
    def test_schematron_successful_report(self):
        """Test schematron with successful-report (also indicates error)"""
        schematron_xslt = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:svrl="http://purl.oclc.org/dsdl/svrl">
    
    <xsl:output method="xml" indent="yes"/>
    
    <xsl:template match="/">
        <svrl:schematron-output>
            <!-- successful-report also counts as a validation issue -->
            <xsl:if test="//deprecated">
                <svrl:successful-report location="/root/deprecated">
                    <svrl:text>Deprecated element found</svrl:text>
                </svrl:successful-report>
            </xsl:if>
        </svrl:schematron-output>
    </xsl:template>
</xsl:stylesheet>'''
        
        # XML with deprecated element
        xml_with_issue = '<root><deprecated>old stuff</deprecated></root>'
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as f:
            f.write(schematron_xslt)
            f.flush()
            
            is_valid, errors = schematron_validate(xml_with_issue, Path(f.name))
            
            # Should be invalid
            self.assertFalse(is_valid)
            self.assertGreater(len(errors), 0)
            self.assertIn('Deprecated', errors[0])


class TestRelaxNGValidate(unittest.TestCase):
    """Test the relaxng_validate function"""
    
    def test_relaxng_validation_success_with_string_schema(self):
        """Test successful RelaxNG validation with schema as string"""
        # Create a simple RelaxNG schema
        relaxng_schema = '''<?xml version="1.0" encoding="UTF-8"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
    <start>
        <element name="root">
            <element name="child">
                <text/>
            </element>
        </element>
    </start>
</grammar>'''
        
        # Valid XML according to schema
        valid_xml = '<root><child>content</child></root>'
        
        is_valid, errors = relaxng_validate(valid_xml, relaxng_schema)
        
        # Should be valid
        self.assertTrue(is_valid, f"Expected valid but got errors: {errors}")
        self.assertEqual(errors, [])
    
    def test_relaxng_validation_failure_with_string_schema(self):
        """Test failed RelaxNG validation with schema as string"""
        # Create a RelaxNG schema requiring specific structure
        relaxng_schema = '''<?xml version="1.0" encoding="UTF-8"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
    <start>
        <element name="root">
            <element name="required">
                <text/>
            </element>
        </element>
    </start>
</grammar>'''
        
        # Invalid XML (missing required element)
        invalid_xml = '<root><optional>content</optional></root>'
        
        is_valid, errors = relaxng_validate(invalid_xml, relaxng_schema)
        
        # Should be invalid with errors
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
    
    def test_relaxng_validation_success_with_etree(self):
        """Test RelaxNG validation with lxml ElementTree input"""
        relaxng_schema = '''<?xml version="1.0" encoding="UTF-8"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
    <start>
        <element name="root">
            <element name="child">
                <text/>
            </element>
        </element>
    </start>
</grammar>'''
        
        # Valid XML as ElementTree
        valid_xml = '<root><child>content</child></root>'
        xml_doc = etree.fromstring(valid_xml)
        
        is_valid, errors = relaxng_validate(xml_doc, relaxng_schema)
        
        # Should be valid
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])
    
    def test_relaxng_with_attributes(self):
        """Test RelaxNG validation with required attributes"""
        # Schema requiring specific attribute
        relaxng_schema = '''<?xml version="1.0" encoding="UTF-8"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
    <start>
        <element name="root">
            <attribute name="id"/>
            <text/>
        </element>
    </start>
</grammar>'''
        
        # Valid XML with attribute
        valid_xml = '<root id="123">content</root>'
        is_valid, errors = relaxng_validate(valid_xml, relaxng_schema)
        
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])
        
        # Invalid XML without attribute
        invalid_xml = '<root>content</root>'
        is_valid, errors = relaxng_validate(invalid_xml, relaxng_schema)
        
        # Should be invalid
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
    
    def test_relaxng_with_file_path(self):
        """Test RelaxNG validation with schema file path"""
        relaxng_schema = '''<?xml version="1.0" encoding="UTF-8"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
    <start>
        <element name="root">
            <text/>
        </element>
    </start>
</grammar>'''
        
        valid_xml = '<root>content</root>'
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.rng', delete_on_close=False) as schema_f:
            schema_f.write(relaxng_schema)
            schema_f.flush()
            
            is_valid, errors = relaxng_validate(valid_xml, Path(schema_f.name))
            
            # Should be valid
            self.assertTrue(is_valid)
            self.assertEqual(errors, [])


class TestValidateFunction(unittest.TestCase):
    """Test the main validate function that combines both validators"""
    
    def test_validate_success_both_schemas_as_strings(self):
        """Test that validate passes when both RelaxNG and Schematron pass"""
        # Simple RelaxNG schema
        relaxng_schema = '''<?xml version="1.0" encoding="UTF-8"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
    <start>
        <element name="root">
            <element name="item">
                <text/>
            </element>
        </element>
    </start>
</grammar>'''
        
        # Simple Schematron that passes if item has content
        schematron_xslt = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:svrl="http://purl.oclc.org/dsdl/svrl">
    
    <xsl:template match="/">
        <svrl:schematron-output>
            <xsl:if test="string-length(//item/text()) = 0">
                <svrl:failed-assert location="/root/item">
                    <svrl:text>Item must have content</svrl:text>
                </svrl:failed-assert>
            </xsl:if>
        </svrl:schematron-output>
    </xsl:template>
</xsl:stylesheet>'''
        
        # Valid XML
        valid_xml = '<root><item>content</item></root>'
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as sch_f:
            sch_f.write(schematron_xslt)
            sch_f.flush()
            
            is_valid, errors = validate(
                valid_xml,
                schema=relaxng_schema,
                schematron_xslt_file=Path(sch_f.name)
            )
            
            # Should be valid
            self.assertTrue(is_valid)
            self.assertEqual(errors, [])
    
    def test_validate_fails_on_relaxng_error(self):
        """Test that validate fails if RelaxNG validation fails"""
        relaxng_schema = '''<?xml version="1.0" encoding="UTF-8"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
    <start>
        <element name="root">
            <element name="required">
                <text/>
            </element>
        </element>
    </start>
</grammar>'''
        
        # Passing schematron
        schematron_xslt = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:svrl="http://purl.oclc.org/dsdl/svrl">
    
    <xsl:template match="/">
        <svrl:schematron-output/>
    </xsl:template>
</xsl:stylesheet>'''
        
        # Invalid for RelaxNG (missing required element)
        invalid_xml = '<root><optional>content</optional></root>'
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as sch_f:
            sch_f.write(schematron_xslt)
            sch_f.flush()
            
            is_valid, errors = validate(
                invalid_xml,
                schema=relaxng_schema,
                schematron_xslt_file=Path(sch_f.name)
            )
            
            # Should be invalid due to RelaxNG
            self.assertFalse(is_valid)
            self.assertGreater(len(errors), 0)
    
    def test_validate_fails_on_schematron_error(self):
        """Test that validate fails if Schematron validation fails"""
        # Simple RelaxNG that allows root with optional child
        relaxng_schema = '''<?xml version="1.0" encoding="UTF-8"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
    <start>
        <element name="root">
            <zeroOrMore>
                <element name="optional">
                    <text/>
                </element>
            </zeroOrMore>
        </element>
    </start>
</grammar>'''
        
        # Strict schematron
        schematron_xslt = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:svrl="http://purl.oclc.org/dsdl/svrl">
    
    <xsl:template match="/">
        <svrl:schematron-output>
            <xsl:if test="not(//mandatory)">
                <svrl:failed-assert location="/root">
                    <svrl:text>Missing mandatory element</svrl:text>
                </svrl:failed-assert>
            </xsl:if>
        </svrl:schematron-output>
    </xsl:template>
</xsl:stylesheet>'''
        
        # Invalid for Schematron (missing mandatory)
        invalid_xml = '<root><optional>content</optional></root>'
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as sch_f:
            sch_f.write(schematron_xslt)
            sch_f.flush()
            
            is_valid, errors = validate(
                invalid_xml,
                schema=relaxng_schema,
                schematron_xslt_file=Path(sch_f.name)
            )
            
            # Should be invalid due to Schematron
            self.assertFalse(is_valid)
            self.assertGreater(len(errors), 0)
            self.assertIn('mandatory', errors[0])
    
    def test_validate_combines_errors_from_both(self):
        """Test that validate combines errors from both validators"""
        # RelaxNG requiring 'required' element
        relaxng_schema = '''<?xml version="1.0" encoding="UTF-8"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
    <start>
        <element name="root">
            <element name="required">
                <text/>
            </element>
        </element>
    </start>
</grammar>'''
        
        # Schematron requiring 'mandatory' element
        schematron_xslt = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:svrl="http://purl.oclc.org/dsdl/svrl">
    
    <xsl:template match="/">
        <svrl:schematron-output>
            <xsl:if test="not(//mandatory)">
                <svrl:failed-assert location="/root">
                    <svrl:text>Missing mandatory</svrl:text>
                </svrl:failed-assert>
            </xsl:if>
        </svrl:schematron-output>
    </xsl:template>
</xsl:stylesheet>'''
        
        # Invalid for both validators
        invalid_xml = '<root><other>content</other></root>'
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as sch_f:
            sch_f.write(schematron_xslt)
            sch_f.flush()
            
            is_valid, errors = validate(
                invalid_xml,
                schema=relaxng_schema,
                schematron_xslt_file=Path(sch_f.name)
            )
            
            # Should be invalid with errors from both
            self.assertFalse(is_valid)
            # Should have errors from both validators
            self.assertGreater(len(errors), 1)
    
    def test_validate_with_file_path(self):
        """Test validate with XML file path instead of string"""
        # Simple schema
        relaxng_schema = '''<?xml version="1.0" encoding="UTF-8"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
    <start>
        <element name="root">
            <text/>
        </element>
    </start>
</grammar>'''
        
        schematron_xslt = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:svrl="http://purl.oclc.org/dsdl/svrl">
    
    <xsl:template match="/">
        <svrl:schematron-output/>
    </xsl:template>
</xsl:stylesheet>'''
        
        valid_xml = '<?xml version="1.0"?><root>content</root>'
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete_on_close=False) as xml_f, \
             tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as sch_f:
            
            xml_f.write(valid_xml)
            xml_f.flush()
            
            sch_f.write(schematron_xslt)
            sch_f.flush()
            
            is_valid, errors = validate(
                Path(xml_f.name),
                schema=relaxng_schema,
                schematron_xslt_file=Path(sch_f.name)
            )
            
            # Should be valid
            self.assertTrue(is_valid)
            self.assertEqual(errors, [])
    
    def test_validate_with_schema_files(self):
        """Test validate with both schemas as file paths"""
        relaxng_schema = '''<?xml version="1.0" encoding="UTF-8"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
    <start>
        <element name="root">
            <element name="item">
                <text/>
            </element>
        </element>
    </start>
</grammar>'''
        
        schematron_xslt = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:svrl="http://purl.oclc.org/dsdl/svrl">
    
    <xsl:template match="/">
        <svrl:schematron-output/>
    </xsl:template>
</xsl:stylesheet>'''
        
        valid_xml = '<root><item>content</item></root>'
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.rng', delete_on_close=False) as rng_f, \
             tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as sch_f:
            
            rng_f.write(relaxng_schema)
            rng_f.flush()
            
            sch_f.write(schematron_xslt)
            sch_f.flush()
            
            is_valid, errors = validate(
                valid_xml,
                schema_file=Path(rng_f.name),
                schematron_xslt_file=Path(sch_f.name)
            )
            
            # Should be valid
            self.assertTrue(is_valid)
            self.assertEqual(errors, [])


class TestAddMissingNamespaces(unittest.TestCase):
    """Test the _add_missing_namespaces helper function."""
    
    def test_adds_tei_namespace_when_missing(self):
        """Test that TEI namespace is added when missing."""
        xml_without_ns = '<tei:div><tei:p>Content</tei:p></tei:div>'
        result = _add_missing_namespaces(xml_without_ns)
        
        # Should have TEI namespace
        self.assertIn('xmlns:tei="http://www.tei-c.org/ns/1.0"', result)
        self.assertIn('xmlns:j="http://jewishliturgy.org/ns/jlptei/2"', result)
    
    def test_adds_j_namespace_when_missing(self):
        """Test that j namespace is added when missing."""
        xml_without_j = '<tei:div xmlns:tei="http://www.tei-c.org/ns/1.0"><tei:p>Content</tei:p></tei:div>'
        result = _add_missing_namespaces(xml_without_j)
        
        # Should have j namespace added
        self.assertIn('xmlns:j="http://jewishliturgy.org/ns/jlptei/2"', result)
        # Should still have TEI namespace
        self.assertIn('xmlns:tei="http://www.tei-c.org/ns/1.0"', result)
    
    def test_adds_tei_namespace_when_only_j_present(self):
        """Test that TEI namespace is added when only j is present."""
        xml_with_j = '<tei:div xmlns:j="http://jewishliturgy.org/ns/jlptei/2"><tei:p>Content</tei:p></tei:div>'
        result = _add_missing_namespaces(xml_with_j)
        
        # Should have TEI namespace added
        self.assertIn('xmlns:tei="http://www.tei-c.org/ns/1.0"', result)
        # Should still have j namespace
        self.assertIn('xmlns:j="http://jewishliturgy.org/ns/jlptei/2"', result)
    
    def test_preserves_existing_namespaces(self):
        """Test that existing namespaces are preserved."""
        xml_with_both = '<tei:div xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2"><tei:p>Content</tei:p></tei:div>'
        result = _add_missing_namespaces(xml_with_both)
        
        # Should be unchanged (both namespaces already present)
        self.assertEqual(xml_with_both, result)
    
    def test_preserves_existing_attributes(self):
        """Test that existing attributes are preserved."""
        xml_with_attrs = '<tei:div xml:id="test" type="section"><tei:p>Content</tei:p></tei:div>'
        result = _add_missing_namespaces(xml_with_attrs)
        
        # Should preserve attributes
        self.assertIn('xml:id="test"', result)
        self.assertIn('type="section"', result)
        # Should add namespaces
        self.assertIn('xmlns:tei="http://www.tei-c.org/ns/1.0"', result)
        self.assertIn('xmlns:j="http://jewishliturgy.org/ns/jlptei/2"', result)
    
    def test_handles_self_closing_tag(self):
        """Test handling of self-closing tags."""
        xml_self_closing = '<tei:lb/>'
        result = _add_missing_namespaces(xml_self_closing)
        
        # Should add namespaces
        self.assertIn('xmlns:tei="http://www.tei-c.org/ns/1.0"', result)
        self.assertIn('xmlns:j="http://jewishliturgy.org/ns/jlptei/2"', result)


class TestValidateWithStart(unittest.TestCase):
    """Test the validate_with_start function for validating XML fragments."""
    
    def test_valid_tei_div_fragment(self):
        """Test validation of a valid tei:div fragment."""
        # Simple valid tei:div fragment
        valid_div = '''<tei:div xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
            <tei:head>Test Heading</tei:head>
            <tei:p>Test paragraph content.</tei:p>
        </tei:div>'''
        
        is_valid, errors = validate_with_start(valid_div, "tei:div")
        
        # Should be valid
        self.assertTrue(is_valid, f"Expected valid but got errors: {errors}")
        self.assertEqual(errors, [])
    
    def test_valid_tei_div_fragment_without_namespaces(self):
        """Test validation of a valid tei:div fragment without namespace declarations."""
        # Fragment without namespace declarations - should be added automatically
        valid_div = '''<tei:div>
            <tei:head>Test Heading</tei:head>
            <tei:p>Test paragraph content.</tei:p>
        </tei:div>'''
        
        is_valid, errors = validate_with_start(valid_div, "tei:div")
        
        # Should be valid (namespaces added automatically)
        self.assertTrue(is_valid, f"Expected valid but got errors: {errors}")
        self.assertEqual(errors, [])
    
    def test_valid_tei_p_fragment(self):
        """Test validation of a valid tei:p fragment."""
        # Simple valid tei:p fragment
        valid_p = '''<tei:p xmlns:tei="http://www.tei-c.org/ns/1.0">Test paragraph content.</tei:p>'''
        
        is_valid, errors = validate_with_start(valid_p, "tei:p")
        
        # Should be valid
        self.assertTrue(is_valid, f"Expected valid but got errors: {errors}")
        self.assertEqual(errors, [])
    
    def test_valid_tei_body_fragment(self):
        """Test validation of a valid tei:body fragment."""
        # Simple valid tei:body fragment
        valid_body = '''<tei:body xmlns:tei="http://www.tei-c.org/ns/1.0">
            <tei:div>
                <tei:p>Test content.</tei:p>
            </tei:div>
        </tei:body>'''
        
        is_valid, errors = validate_with_start(valid_body, "tei:body")
        
        # Should be valid
        self.assertTrue(is_valid, f"Expected valid but got errors: {errors}")
        self.assertEqual(errors, [])
    
    def test_invalid_tei_div_fragment_bad_structure(self):
        """Test validation of an invalid tei:div fragment with incorrect structure."""
        # Invalid: tei:div with invalid child element
        invalid_div = '''<tei:div xmlns:tei="http://www.tei-c.org/ns/1.0">
            <invalid_element>This should not be here</invalid_element>
        </tei:div>'''
        
        is_valid, errors = validate_with_start(invalid_div, "tei:div")
        
        # Should be invalid
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
        # Check that error mentions the invalid element
        error_text = " ".join(errors)
        self.assertIn("invalid_element", error_text.lower())
    
    def test_invalid_tei_p_fragment_nested_p(self):
        """Test validation of an invalid tei:p fragment with nested paragraph."""
        # Invalid: tei:p cannot contain another tei:p
        invalid_p = '''<tei:p xmlns:tei="http://www.tei-c.org/ns/1.0">
            Outer paragraph
            <tei:p>Nested paragraph (invalid)</tei:p>
        </tei:p>'''
        
        is_valid, errors = validate_with_start(invalid_p, "tei:p")
        
        # Should be invalid
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
    
    def test_invalid_start_element_not_in_schema(self):
        """Test validation with a start element that doesn't exist in the schema."""
        # Valid XML but with a start element not defined in schema
        xml_fragment = '''<nonexistent:element xmlns:nonexistent="http://example.com">
            <child>Content</child>
        </nonexistent:element>'''
        
        # Should raise an error because the start element doesn't exist
        with self.assertRaises(ValueError) as context:
            validate_with_start(xml_fragment, "nonexistent:element")
        
        # Check error message
        self.assertIn("does not define an element", str(context.exception))
    
    def test_valid_tei_bibl_fragment(self):
        """Test validation of a valid tei:bibl fragment."""
        # Simple valid tei:bibl fragment
        valid_bibl = '''<tei:bibl xmlns:tei="http://www.tei-c.org/ns/1.0">
            <tei:title>Test Title</tei:title>
            <tei:author>Test Author</tei:author>
        </tei:bibl>'''
        
        is_valid, errors = validate_with_start(valid_bibl, "tei:bibl")
        
        # Should be valid
        self.assertTrue(is_valid, f"Expected valid but got errors: {errors}")
        self.assertEqual(errors, [])
    
    def test_invalid_tei_bibl_fragment_bad_child(self):
        """Test validation of an invalid tei:bibl fragment with invalid child element."""
        # Invalid: tei:bibl with an invalid child element
        invalid_bibl = '''<tei:bibl xmlns:tei="http://www.tei-c.org/ns/1.0">
            <invalid_element>This should not be here</invalid_element>
        </tei:bibl>'''
        
        is_valid, errors = validate_with_start(invalid_bibl, "tei:bibl")
        
        # Should be invalid
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
        # Check that error mentions the invalid element
        error_text = " ".join(errors).lower()
        self.assertIn("invalid_element", error_text)
    
    def test_valid_tei_head_fragment(self):
        """Test validation of a valid tei:head fragment."""
        # Simple valid tei:head fragment
        valid_head = '''<tei:head xmlns:tei="http://www.tei-c.org/ns/1.0">Test Heading</tei:head>'''
        
        is_valid, errors = validate_with_start(valid_head, "tei:head")
        
        # Should be valid
        self.assertTrue(is_valid, f"Expected valid but got errors: {errors}")
        self.assertEqual(errors, [])


class _DocumentInADiv:
    """A minimal valid document around the encoding under test."""

    HEADER = (
        '<tei:teiHeader><tei:fileDesc>'
        '<tei:titleStmt><tei:title>t</tei:title></tei:titleStmt>'
        '<tei:publicationStmt><tei:distributor>d</tei:distributor></tei:publicationStmt>'
        '<tei:sourceDesc><tei:bibl>b</tei:bibl></tei:sourceDesc>'
        '</tei:fileDesc></tei:teiHeader>'
    )
    CONDITIONAL = (
        '<j:conditional xml:id="c1"><tei:fs type="opensiddur:holiday">'
        '<tei:f name="pesah"><tei:numeric value="1" max="8"/></tei:f>'
        '</tei:fs></j:conditional>'
    )

    def document(self, inner):
        return (
            '<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" '
            'xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xml:lang="he">'
            f'{self.HEADER}<tei:text><tei:body><tei:div>{inner}</tei:div>'
            '</tei:body></tei:text></tei:TEI>'
        )


class TestConditionalIsClosed(_DocumentInADiv, unittest.TestCase):
    """A conditional that is never closed governs the rest of the file.

    Schematron already checked that an endConditional names a conditional preceding it. It
    did not check the converse, so an unclosed conditional passed validation and silently
    conditioned everything after it to the end of the document.
    """

    def test_a_closed_conditional_is_valid(self):
        is_valid, errors = validate(self.document(
            f'{self.CONDITIONAL}<tei:p>x</tei:p><j:endConditional target="#c1"/>'))
        self.assertTrue(is_valid, f"Expected valid but got errors: {errors}")

    def test_an_unclosed_conditional_is_reported(self):
        is_valid, errors = validate(self.document(f'{self.CONDITIONAL}<tei:p>x</tei:p>'))
        self.assertFalse(is_valid)
        self.assertTrue(any("must be closed" in error for error in errors), errors)

    def test_the_closing_element_must_follow_the_conditional(self):
        # A close before its open leaves the scope open to the end of the file just as
        # surely as no close at all.
        is_valid, _ = validate(self.document(
            f'<j:endConditional target="#c1"/><tei:p>x</tei:p>{self.CONDITIONAL}'))
        self.assertFalse(is_valid)



class TestDeclarationsAndConditionsAreWellFormed(_DocumentInADiv, unittest.TestCase):
    """What the compiler relies on in a declaration or a condition, checked before it runs."""

    FS = ('<tei:fs type="opensiddur:holiday">'
          '<tei:f name="pesah"><tei:numeric value="1"/></tei:f></tei:fs>')

    def declaration(self, body=None, closed=True):
        declare = f'<j:declare xml:id="d1">{self.FS if body is None else body}</j:declare>'
        return declare + '<tei:p>x</tei:p>' + ('<j:endDeclare target="#d1"/>' if closed else '')

    def assertReported(self, inner, message):
        is_valid, errors = validate(self.document(inner))
        self.assertFalse(is_valid)
        self.assertTrue(any(message in error for error in errors), errors)

    def test_a_closed_declaration_is_valid(self):
        is_valid, errors = validate(self.document(self.declaration()))
        self.assertTrue(is_valid, f"Expected valid but got errors: {errors}")

    def test_an_unclosed_declaration_is_reported(self):
        self.assertReported(self.declaration(closed=False), "must be closed")

    def test_a_declaration_holds_only_feature_structures(self):
        self.assertReported(self.declaration(f'<j:all>{self.FS}</j:all>'), "holds only feature structures")

    def test_a_declaration_gives_no_alternatives(self):
        self.assertReported(self.declaration(
            '<tei:fs type="opensiddur:holiday"><tei:f name="pesah"><tei:vAlt>'
            '<tei:numeric value="1"/><tei:numeric value="2"/></tei:vAlt></tei:f></tei:fs>'),
            "not alternatives")

    def test_a_declaration_ends_inside_the_element_it_began_in(self):
        self.assertReported(
            '<j:declare xml:id="d1">' + self.FS + '</j:declare>'
            '<tei:p>x<j:endDeclare target="#d1"/></tei:p>', "fully contain")

    def test_a_declaration_and_its_end_are_siblings(self):
        """Begun inside an element and ended outside it, the declaration may never be made."""
        self.assertReported(
            '<tei:p><j:declare xml:id="d1">' + self.FS + '</j:declare>a</tei:p>'
            '<tei:p>b</tei:p><j:endDeclare target="#d1"/>', "must be siblings")

    def test_a_feature_structure_names_its_type_and_a_feature(self):
        self.assertReported(self.declaration('<tei:fs><tei:f name="pesah">'
                                             '<tei:numeric value="1"/></tei:f></tei:fs>'),
                            "must have a type attribute")
        self.assertReported(
            '<j:conditional xml:id="c1"><tei:fs type="opensiddur:holiday"/></j:conditional>'
            '<tei:p>x</tei:p><j:endConditional target="#c1"/>', "at least one feature")

    def test_the_note_of_a_conditional_is_an_instruction(self):
        self.assertReported(
            '<j:conditional xml:id="c1"><tei:note type="comment">On Pesah:</tei:note>'
            + self.FS + '</j:conditional><tei:p>x</tei:p><j:endConditional target="#c1"/>',
            "the rubric saying when")

    def test_a_description_is_not_the_note_of_a_conditional(self):
        """It says what the passage is, so it belongs inside the scope (JLPTEI-3)."""
        self.assertReported(
            '<j:conditional xml:id="c1"><tei:note type="description">Reader:</tei:note>'
            + self.FS + '</j:conditional><tei:p>x</tei:p><j:endConditional target="#c1"/>',
            "goes inside the scope")


if __name__ == '__main__':
    unittest.main()
