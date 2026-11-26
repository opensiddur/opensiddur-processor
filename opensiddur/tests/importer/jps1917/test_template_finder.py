import unittest

from opensiddur.importer.jps1917.template_finder import (
    extract_tags_from_wikitext,
    extract_templates_from_wikitext,
)


class TestExtractTemplatesFromWikitext(unittest.TestCase):
    """Test extracting templates from wikitext"""
    
    def test_extract_single_template(self):
        """Test extracting a single template"""
        wikitext = '{{sc|small caps}}'
        result = extract_templates_from_wikitext(wikitext)
        
        self.assertIn('sc', result)
        self.assertEqual(result['sc']['count'], 1)
        self.assertGreater(len(result['sc']['examples']), 0)
    
    def test_extract_multiple_same_templates(self):
        """Test extracting multiple instances of same template"""
        wikitext = '{{sc|first}} and {{sc|second}} and {{sc|third}}'
        result = extract_templates_from_wikitext(wikitext)
        
        self.assertIn('sc', result)
        self.assertEqual(result['sc']['count'], 3)
    
    def test_extract_different_templates(self):
        """Test extracting different template types"""
        wikitext = '{{sc|small}} {{larger|big}} {{verse|1|1|text}}'
        result = extract_templates_from_wikitext(wikitext)
        
        self.assertIn('sc', result)
        self.assertIn('larger', result)
        self.assertIn('verse', result)
        self.assertEqual(result['sc']['count'], 1)
        self.assertEqual(result['larger']['count'], 1)
        self.assertEqual(result['verse']['count'], 1)
    
    def test_extract_template_parameters(self):
        """Test that template parameters are extracted"""
        wikitext = '{{verse|chapter=1|verse=1|text=In the beginning}}'
        result = extract_templates_from_wikitext(wikitext)
        
        self.assertIn('verse', result)
        # Parameters should be tracked
        self.assertGreater(len(result['verse']['parameters']), 0)
        self.assertIn('chapter', result['verse']['parameters'])
        self.assertIn('verse', result['verse']['parameters'])
        self.assertIn('text', result['verse']['parameters'])
    
    def test_extract_empty_wikitext(self):
        """Test extracting from empty wikitext"""
        result = extract_templates_from_wikitext('')
        
        self.assertEqual(result, {})
    
    def test_extract_no_templates(self):
        """Test extracting from wikitext with no templates"""
        wikitext = 'Just plain text without any templates'
        result = extract_templates_from_wikitext(wikitext)
        
        self.assertEqual(result, {})


class TestExtractTagsFromWikitext(unittest.TestCase):
    """Test extracting tags from wikitext"""
    
    def test_extract_single_tag(self):
        """Test extracting a single tag"""
        wikitext = '<ref name="note1">Reference text</ref>'
        result = extract_tags_from_wikitext(wikitext)
        
        self.assertIn('ref', result)
        self.assertEqual(result['ref']['count'], 1)
    
    def test_extract_multiple_same_tags(self):
        """Test extracting multiple instances of same tag"""
        wikitext = '<i>first</i> and <i>second</i> and <i>third</i>'
        result = extract_tags_from_wikitext(wikitext)
        
        self.assertIn('i', result)
        self.assertEqual(result['i']['count'], 3)
    
    def test_extract_different_tags(self):
        """Test extracting different tag types"""
        wikitext = '<i>italic</i> <br/> <ref>note</ref>'
        result = extract_tags_from_wikitext(wikitext)
        
        self.assertIn('i', result)
        self.assertIn('br', result)
        self.assertIn('ref', result)
    
    def test_extract_tag_attributes(self):
        """Test that tag attributes are extracted"""
        wikitext = '<section begin="intro" end="outro">content</section>'
        result = extract_tags_from_wikitext(wikitext)
        
        self.assertIn('section', result)
        # Attributes should be tracked (depends on mwparserfromhell implementation)
        self.assertIsNotNone(result['section']['attributes'])
    
    def test_extract_empty_wikitext(self):
        """Test extracting from empty wikitext"""
        result = extract_tags_from_wikitext('')
        
        self.assertEqual(result, {})
    
    def test_extract_no_tags(self):
        """Test extracting from wikitext with no tags"""
        wikitext = 'Just plain text without any tags'
        result = extract_tags_from_wikitext(wikitext)
        
        self.assertEqual(result, {})




if __name__ == '__main__':
    unittest.main()

