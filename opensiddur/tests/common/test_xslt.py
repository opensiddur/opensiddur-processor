import unittest
import tempfile
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock

from opensiddur.common.xslt import xslt_transform_string, xslt_transform, _to_xdm_value
from saxonche import PySaxonProcessor, PyXdmAtomicValue


class TestXSLTTransformString(unittest.TestCase):
    """Test xslt_transform_string function with various scenarios"""
    
    def test_basic_transformation(self):
        """Test a simple valid XSLT transformation"""
        # Create a simple XSLT that wraps content in a <result> tag
        xslt_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="xml" indent="yes"/>
    <xsl:template match="/">
        <result>
            <xsl:copy-of select="//text()"/>
        </result>
    </xsl:template>
</xsl:stylesheet>'''
        
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<root>
    <item>Hello World</item>
</root>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as f:
            f.write(xslt_content)
            f.flush()
            xslt_file = Path(f.name)
            
            result = xslt_transform_string(xslt_file, input_xml)
            
            # Verify the result contains expected content
            self.assertIsInstance(result, str)
            self.assertIn('<result>', result)
            self.assertIn('Hello World', result)
    
    def test_invalid_xslt_file(self):
        """Test that invalid XSLT raises an appropriate error"""
        # Create an invalid XSLT (malformed XML)
        xslt_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:template match="/">
        <result>Test</result>
    <!-- Missing closing template tag -->
</xsl:stylesheet>'''
        
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<root><item>Test</item></root>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as f:
            f.write(xslt_content)
            f.flush()
            xslt_file = Path(f.name)
            
            with self.assertRaises(Exception):
                xslt_transform_string(xslt_file, input_xml)
    
    def test_transformation_with_parameters(self):
        """Test XSLT transformation with parameters of different types"""
        # Create XSLT that uses parameters
        xslt_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" 
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema">
    <xsl:output method="xml" indent="yes"/>
    <xsl:param name="string_param" as="xs:string"/>
    <xsl:param name="bool_param" as="xs:boolean"/>
    <xsl:param name="int_param" as="xs:integer"/>
    <xsl:param name="float_param" as="xs:double"/>
    
    <xsl:template match="/">
        <result>
            <string><xsl:value-of select="$string_param"/></string>
            <bool><xsl:value-of select="$bool_param"/></bool>
            <int><xsl:value-of select="$int_param"/></int>
            <float><xsl:value-of select="$float_param"/></float>
        </result>
    </xsl:template>
</xsl:stylesheet>'''
        
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<root/>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as f:
            f.write(xslt_content)
            f.flush()
            xslt_file = Path(f.name)
            
            params = {
                'string_param': 'test string',
                'bool_param': True,
                'int_param': 42,
                'float_param': 3.14
            }
            
            result = xslt_transform_string(xslt_file, input_xml, xslt_params=params)
            
            # Verify all parameters were passed correctly
            self.assertIn('test string', result)
            self.assertIn('true', result)
            self.assertIn('42', result)
            self.assertIn('3.14', result)
    
    def test_multiple_results(self):
        """Test XSLT transformation that produces multiple result documents"""
        # Create XSLT that produces secondary result documents
        xslt_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="xml" indent="yes"/>
    
    <xsl:template match="/">
        <primary>
            <xsl:text>Primary Result</xsl:text>
        </primary>
        <xsl:result-document href="file:///output/secondary1.xml">
            <secondary1>Secondary Document 1</secondary1>
        </xsl:result-document>
        <xsl:result-document href="file:///output/secondary2.xml">
            <secondary2>Secondary Document 2</secondary2>
        </xsl:result-document>
    </xsl:template>
</xsl:stylesheet>'''
        
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<root/>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as f:
            f.write(xslt_content)
            f.flush()
            xslt_file = Path(f.name)
            
            result = xslt_transform_string(xslt_file, input_xml, multiple_results=True)
            
            # Verify result is a dict
            self.assertIsInstance(result, dict)
            
            # Verify primary result
            self.assertIn('', result)
            self.assertIn('Primary Result', result[''])
            
            # Verify secondary results
            self.assertIn('secondary1.xml', result)
            self.assertIn('Secondary Document 1', result['secondary1.xml'])
            
            self.assertIn('secondary2.xml', result)
            self.assertIn('Secondary Document 2', result['secondary2.xml'])
    
    def test_multiple_results_wrong_base_uri(self):
        """Test XSLT with multiple results but incorrect base URI"""
        # Create XSLT with result documents using different base URI
        xslt_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="xml" indent="yes"/>
    
    <xsl:template match="/">
        <primary>Primary</primary>
        <xsl:result-document href="file:///different/path/doc.xml">
            <secondary>Different Base</secondary>
        </xsl:result-document>
    </xsl:template>
</xsl:stylesheet>'''
        
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<root/>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as f:
            f.write(xslt_content)
            f.flush()
            xslt_file = Path(f.name)
            
            result = xslt_transform_string(xslt_file, input_xml, multiple_results=True)
            
            # Should still work - the function extracts filename from full URI path
            self.assertIsInstance(result, dict)
            self.assertIn('', result)
            # The secondary document should still be captured with its filename
            self.assertIn('doc.xml', result)
    
    def test_transformation_failure_during_execution(self):
        """Test handling of errors that occur during transformation"""
        # Division by zero in XSLT actually produces Infinity in XPath 3.0
        # So let's use a different error - calling a non-existent function
        xslt_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="xml" indent="yes"/>
    <xsl:template match="/">
        <result>
            <xsl:value-of select="nonexistent:function()"/>
        </result>
    </xsl:template>
</xsl:stylesheet>'''
        
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<root/>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as f:
            f.write(xslt_content)
            f.flush()
            xslt_file = Path(f.name)
            
            with self.assertRaises(Exception):
                xslt_transform_string(xslt_file, input_xml)
    
    def test_compile_stylesheet_none_raises_value_error(self):
        """Line 35: raises ValueError when compile_stylesheet returns None."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt') as f:
            f.write('<root/>')
            f.flush()

            with patch('opensiddur.common.xslt.PySaxonProcessor') as mock_proc_class:
                mock_proc = MagicMock()
                mock_proc_class.return_value.__enter__.return_value = mock_proc
                mock_proc_class.return_value.__exit__.return_value = False

                mock_xslt_proc = MagicMock()
                mock_proc.new_xslt30_processor.return_value = mock_xslt_proc
                mock_xslt_proc.compile_stylesheet.return_value = None
                mock_xslt_proc.error_message = 'Stylesheet compilation failed'

                with self.assertRaises(ValueError) as ctx:
                    xslt_transform_string(Path(f.name), '<root/>')

            self.assertIn('Failed to compile XSLT', str(ctx.exception))
            self.assertIn('Stylesheet compilation failed', str(ctx.exception))

    def test_single_result_returns_string(self):
        """Test that single result mode returns a string, not a dict"""
        xslt_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="xml" indent="yes"/>
    <xsl:template match="/">
        <output>Single Result</output>
    </xsl:template>
</xsl:stylesheet>'''
        
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<root/>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as f:
            f.write(xslt_content)
            f.flush()
            xslt_file = Path(f.name)
            
            # Default behavior (multiple_results=False)
            result = xslt_transform_string(xslt_file, input_xml)
            
            # Should return a string, not a dict
            self.assertIsInstance(result, str)
            self.assertNotIsInstance(result, dict)
            self.assertIn('Single Result', result)


class TestXSLTTransform(unittest.TestCase):
    """Test xslt_transform function that works with files"""
    
    def test_transform_with_output_file(self):
        """Test transformation that writes to an output file"""
        # Create a simple XSLT
        xslt_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="xml" indent="yes"/>
    <xsl:template match="/">
        <output>
            <xsl:value-of select="//text()"/>
        </output>
    </xsl:template>
</xsl:stylesheet>'''
        
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<root>
    <item>Test Content</item>
</root>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as xslt_f, \
             tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete_on_close=False) as input_f, \
             tempfile.NamedTemporaryFile(mode='r', suffix='.xml', delete=False) as output_f:
            
            # Write XSLT and input files
            xslt_f.write(xslt_content)
            xslt_f.flush()
            
            input_f.write(input_xml)
            input_f.flush()
            
            output_path = Path(output_f.name)
            output_f.close()
            
            try:
                # Perform transformation
                xslt_transform(Path(xslt_f.name), Path(input_f.name), output_path)
                
                # Read and verify output
                with open(output_path, 'r') as f:
                    result = f.read()
                
                self.assertIn('<output>', result)
                self.assertIn('Test Content', result)
            finally:
                output_path.unlink()
    
    def test_transform_to_stdout(self):
        """Test transformation that writes to stdout when no output file specified"""
        # Create a simple XSLT
        xslt_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="xml" indent="yes"/>
    <xsl:template match="/">
        <stdout-output>
            <xsl:value-of select="//message"/>
        </stdout-output>
    </xsl:template>
</xsl:stylesheet>'''
        
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<root>
    <message>Stdout Test</message>
</root>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as xslt_f, \
             tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete_on_close=False) as input_f:
            
            # Write XSLT and input files
            xslt_f.write(xslt_content)
            xslt_f.flush()
            
            input_f.write(input_xml)
            input_f.flush()
            
            # Capture stdout
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                xslt_transform(Path(xslt_f.name), Path(input_f.name), None)
            
            # Verify output went to stdout
            result = captured_output.getvalue()
            self.assertIn('<stdout-output>', result)
            self.assertIn('Stdout Test', result)
    
    def test_transform_with_missing_input_file(self):
        """Test that missing input file raises appropriate error"""
        # Create XSLT but not input file
        xslt_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="xml" indent="yes"/>
    <xsl:template match="/">
        <output>Test</output>
    </xsl:template>
</xsl:stylesheet>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt') as xslt_f:
            xslt_f.write(xslt_content)
            xslt_f.flush()
            
            # Try to transform with non-existent input file
            non_existent_input = Path('/tmp/non_existent_input_file.xml')
            
            with self.assertRaises(FileNotFoundError):
                xslt_transform(Path(xslt_f.name), non_existent_input, None)
    
    def test_transform_with_invalid_xslt(self):
        """Test that invalid XSLT in file raises appropriate error"""
        # Create invalid XSLT
        xslt_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:template match="/">
        <output>Test</output>
    <!-- Missing closing template tag -->
</xsl:stylesheet>'''
        
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<root>Test</root>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as xslt_f, \
             tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete_on_close=False) as input_f:
            
            xslt_f.write(xslt_content)
            xslt_f.flush()
            
            input_f.write(input_xml)
            input_f.flush()
            
            with self.assertRaises(Exception):
                xslt_transform(Path(xslt_f.name), Path(input_f.name), None)
    
    def test_transform_with_invalid_xml_input(self):
        """Test that invalid XML input raises appropriate error"""
        # Create valid XSLT
        xslt_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="xml" indent="yes"/>
    <xsl:template match="/">
        <output>Test</output>
    </xsl:template>
</xsl:stylesheet>'''
        
        # Create invalid XML input
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<root>
    <unclosed>
</root>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', delete_on_close=False) as xslt_f, \
             tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete_on_close=False) as input_f:
            
            xslt_f.write(xslt_content)
            xslt_f.flush()
            
            input_f.write(input_xml)
            input_f.flush()
            
            with self.assertRaises(Exception):
                xslt_transform(Path(xslt_f.name), Path(input_f.name), None)
    
    def test_transform_preserves_encoding(self):
        """Test that transformation preserves UTF-8 encoding"""
        # Create XSLT that passes through content
        xslt_content = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="xml" indent="yes" encoding="UTF-8"/>
    <xsl:template match="/">
        <output>
            <xsl:value-of select="//text"/>
        </output>
    </xsl:template>
</xsl:stylesheet>'''
        
        # Create input with Unicode characters (Hebrew)
        input_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<root>
    <text>שלום עולם</text>
</root>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xslt', encoding='utf-8', delete_on_close=False) as xslt_f, \
             tempfile.NamedTemporaryFile(mode='w', suffix='.xml', encoding='utf-8', delete_on_close=False) as input_f, \
             tempfile.NamedTemporaryFile(mode='r', suffix='.xml', encoding='utf-8', delete=False) as output_f:
            
            # Write files
            xslt_f.write(xslt_content)
            xslt_f.flush()
            
            input_f.write(input_xml)
            input_f.flush()
            
            output_path = Path(output_f.name)
            output_f.close()
            
            try:
                # Perform transformation
                xslt_transform(Path(xslt_f.name), Path(input_f.name), output_path)
                
                # Read and verify output preserves Hebrew
                with open(output_path, 'r', encoding='utf-8') as f:
                    result = f.read()
                
                self.assertIn('שלום עולם', result)
            finally:
                output_path.unlink()


class TestToXdmValue(unittest.TestCase):
    """Test the _to_xdm_value helper function"""
    
    def test_string_conversion(self):
        """Test converting string values to XDM"""
        with PySaxonProcessor(license=False) as proc:
            result = _to_xdm_value(proc, "test string")
            
            # Verify it's a PyXdmAtomicValue
            self.assertIsInstance(result, PyXdmAtomicValue)
            
            # Verify it's an xs:string
            self.assertEqual(result.primitive_type_name, "xs:string")
            
            # Verify the value is correct
            self.assertEqual(result.get_string_value(), "test string")
    
    def test_boolean_conversion(self):
        """Test converting boolean values to XDM"""
        with PySaxonProcessor(license=False) as proc:
            result_true = _to_xdm_value(proc, True)
            result_false = _to_xdm_value(proc, False)
            
            # Verify both are PyXdmAtomicValue
            self.assertIsInstance(result_true, PyXdmAtomicValue)
            self.assertIsInstance(result_false, PyXdmAtomicValue)
            
            # Verify they're xs:boolean (with namespace)
            self.assertIn('boolean', result_true.primitive_type_name)
            self.assertIn('boolean', result_false.primitive_type_name)
            
            # Verify the values are correct
            self.assertTrue(result_true.boolean_value)
            self.assertFalse(result_false.boolean_value)
    
    def test_integer_conversion(self):
        """Test converting integer values to XDM"""
        with PySaxonProcessor(license=False) as proc:
            result = _to_xdm_value(proc, 42)
            
            # Verify it's a PyXdmAtomicValue
            self.assertIsInstance(result, PyXdmAtomicValue)
            
            # Verify it's an xs:integer
            self.assertIn('integer', result.primitive_type_name)
            
            # Verify the value is correct
            self.assertEqual(result.integer_value, 42)
    
    def test_float_conversion(self):
        """Test converting float values to XDM"""
        with PySaxonProcessor(license=False) as proc:
            result = _to_xdm_value(proc, 3.14)
            
            # Verify it's a PyXdmAtomicValue
            self.assertIsInstance(result, PyXdmAtomicValue)
            
            # Verify it's an xs:double
            self.assertIn('double', result.primitive_type_name)
            
            # Verify the value is correct (with small tolerance for floating point)
            self.assertAlmostEqual(result.double_value, 3.14, places=2)
    
    def test_fallback_conversion(self):
        """Test fallback conversion for other types"""
        with PySaxonProcessor(license=False) as proc:
            # Test with a list (should convert to string)
            result = _to_xdm_value(proc, [1, 2, 3])
            
            # Verify it's a PyXdmAtomicValue
            self.assertIsInstance(result, PyXdmAtomicValue)
            
            # Verify it's converted to xs:string
            self.assertEqual(result.primitive_type_name, "xs:string")
            
            # Verify the value is the string representation
            self.assertEqual(result.get_string_value(), "[1, 2, 3]")


if __name__ == '__main__':
    unittest.main()

