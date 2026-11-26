import unittest

from lxml import etree

from opensiddur.importer.util.prettify import prettify_xml


class TestPrettifyXML(unittest.TestCase):
    """Test the prettify_xml function"""
    
    def test_prettify_unformatted_xml(self):
        """Test that unformatted XML gets properly formatted with indentation"""
        # Create ugly, unformatted XML on one line with tail text
        ugly_xml = '<root><child1><grandchild>text</grandchild>tail after grandchild</child1>tail after child1<child2 attr="value"><item>data</item>item tail</child2></root>'
        
        result = prettify_xml(ugly_xml)
        
        # Should have proper formatting
        self.assertIn('<?xml version', result)  # Has XML declaration by default
        self.assertIn('\n', result)  # Has line breaks
        
        # Verify structure is preserved
        self.assertIn('<root>', result)
        self.assertIn('<child1>', result)
        self.assertIn('<grandchild>text</grandchild>', result)
        self.assertIn('<child2 attr="value">', result)
        self.assertIn('</root>', result)
        
        # Verify tail text is preserved
        self.assertIn('tail after grandchild', result)
        self.assertIn('tail after child1', result)
        self.assertIn('item tail', result)
        
        # Should have multiple lines (indented)
        lines = result.split('\n')
        self.assertGreater(len(lines), 1, "Should have multiple lines")
    
    def test_prettify_preserves_content(self):
        """Test that prettifying preserves all content and attributes"""
        xml_string = '''<book><title id="123">Test Title</title><author role="primary">John Doe</author><content>Text content here</content></book>'''
        
        result = prettify_xml(xml_string)
        
        # All content should be preserved
        self.assertIn('Test Title', result)
        self.assertIn('John Doe', result)
        self.assertIn('Text content here', result)
        
        # All attributes should be preserved
        self.assertIn('id="123"', result)
        self.assertIn('role="primary"', result)
    
    def test_remove_xml_declaration(self):
        """Test that XML declaration can be removed"""
        xml_string = '<root><child>content</child></root>'
        
        # With declaration (default)
        result_with_decl = prettify_xml(xml_string, remove_xml_declaration=False)
        self.assertIn('<?xml version', result_with_decl)
        
        # Without declaration
        result_without_decl = prettify_xml(xml_string, remove_xml_declaration=True)
        self.assertNotIn('<?xml version', result_without_decl)
        self.assertNotIn('<?xml', result_without_decl)
        
        # Content should still be there
        self.assertIn('<root>', result_without_decl)
        self.assertIn('<child>content</child>', result_without_decl)
    
    def test_invalid_xml_raises_parse_error(self):
        """Test that invalid XML raises lxml.etree.XMLSyntaxError (subclass of ParseError)"""
        # Missing closing tag
        invalid_xml = '<root><child>content</root>'
        
        with self.assertRaises(etree.XMLSyntaxError):
            prettify_xml(invalid_xml)
    
    def test_malformed_xml_syntax_error(self):
        """Test that malformed XML raises XMLSyntaxError"""
        # Completely broken XML
        invalid_xml = '<root><unclosed><another>text</root>'
        
        with self.assertRaises(etree.XMLSyntaxError):
            prettify_xml(invalid_xml)
    
    def test_invalid_xml_characters(self):
        """Test that XML with invalid characters raises XMLSyntaxError"""
        # XML with unescaped < in content
        invalid_xml = '<root>content < more content</root>'
        
        with self.assertRaises(etree.XMLSyntaxError):
            prettify_xml(invalid_xml)
    
    def test_empty_xml_raises_error(self):
        """Test that empty string raises XMLSyntaxError"""
        with self.assertRaises(etree.XMLSyntaxError):
            prettify_xml('')
    
    def test_utf8_encoding_default(self):
        """Test that UTF-8 encoding works (default)"""
        # XML with Hebrew characters
        xml_string = '<root><text>שלום עולם</text></root>'
        
        result = prettify_xml(xml_string)
        
        # Hebrew should be preserved
        self.assertIn('שלום עולם', result)
        # lxml uses single quotes in XML declaration
        self.assertIn("encoding='utf-8'", result)
    
    def test_custom_encoding(self):
        """Test that custom encoding parameter works"""
        xml_string = '<root><text>Hello World</text></root>'
        
        result = prettify_xml(xml_string, encoding='utf-16')
        
        # Should use specified encoding (lxml uses single quotes)
        self.assertIn("encoding='utf-16'", result)
        self.assertIn('Hello World', result)
    
    def test_preserves_namespaces(self):
        """Test that prettifying preserves XML namespaces and prefixes"""
        xml_string = '''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"><tei:text><tei:body>Content</tei:body></tei:text></tei:TEI>'''
        
        result = prettify_xml(xml_string)
        
        # Namespace declaration should be preserved
        self.assertIn('xmlns:tei="http://www.tei-c.org/ns/1.0"', result)
        
        # Prefixes should be preserved
        self.assertIn('tei:TEI', result)
        self.assertIn('tei:text', result)
        self.assertIn('tei:body', result)
    
    def test_preserves_mixed_content(self):
        """Test that mixed content (text and elements) is preserved"""
        xml_string = '<p>Text before <em>emphasized</em> and after</p>'
        
        result = prettify_xml(xml_string)
        
        # Mixed content should be preserved
        self.assertIn('Text before', result)
        self.assertIn('<em>emphasized</em>', result)
        self.assertIn('and after', result)
    
    def test_already_prettified_xml(self):
        """Test that already formatted XML remains valid"""
        pretty_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<root>
  <child>
    <grandchild>content</grandchild>
  </child>
</root>'''
        
        result = prettify_xml(pretty_xml)
        
        # Should still be valid and contain all elements
        self.assertIn('<?xml version', result)
        self.assertIn('<root>', result)
        self.assertIn('<child>', result)
        self.assertIn('<grandchild>content</grandchild>', result)
    
    def test_xml_with_cdata(self):
        """Test that CDATA content is preserved (as escaped text)"""
        xml_string = '<root><content><![CDATA[Some <special> & characters]]></content></root>'
        
        result = prettify_xml(xml_string)
        
        # lxml converts CDATA to escaped text, which is semantically equivalent
        # The important thing is the content is preserved
        self.assertIn('Some &lt;special&gt; &amp; characters', result)
    
    def test_xml_with_comments(self):
        """Test that XML comments are preserved"""
        xml_string = '<root><!-- This is a comment --><child>content</child></root>'
        
        result = prettify_xml(xml_string)
        
        # Comments should be preserved
        self.assertIn('<!-- This is a comment -->', result)
        self.assertIn('<child>content</child>', result)
    
    def test_strips_trailing_whitespace(self):
        """Test that result is stripped of trailing whitespace"""
        xml_string = '<root><child>content</child></root>'
        
        result = prettify_xml(xml_string)
        
        # Should not end with newlines or spaces
        self.assertFalse(result.endswith('\n'))
        self.assertFalse(result.endswith(' '))


if __name__ == '__main__':
    unittest.main()

