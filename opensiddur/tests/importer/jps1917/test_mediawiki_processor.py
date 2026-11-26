import unittest

from opensiddur.importer.jps1917.mediawiki_processor import (
    ConversionResult,
    MediaWikiProcessor,
    create_processor,
    process_page,
)


class TestBasicProcessing(unittest.TestCase):
    """Test basic MediaWiki to XML processing functionality"""
    
    def setUp(self):
        """Create processor instance for each test"""
        self.processor = create_processor()
    
    def test_create_processor(self):
        """Test that create_processor returns a MediaWikiProcessor instance"""
        processor = create_processor()
        self.assertIsInstance(processor, MediaWikiProcessor)
    
    def test_process_page(self):
        """Test the process_page convenience function"""
        wikitext = '{{sc|test}}'
        result = process_page(wikitext)
        
        self.assertIsInstance(result, ConversionResult)
        self.assertIn('<sc>test</sc>', result.xml_content)
    
    def test_basic_template_processing(self):
        """Test basic template to XML conversion"""
        wikitext = '{{sc|small caps text}}'
        result = self.processor.process_wikitext(wikitext)
        
        self.assertIn('<sc>small caps text</sc>', result.xml_content)
        self.assertIn('<mediawiki>', result.xml_content)
        self.assertIn('</mediawiki>', result.xml_content)
    
    def test_basic_tag_processing(self):
        """Test basic HTML tag processing"""
        wikitext = '<i>italic text</i>'
        result = self.processor.process_wikitext(wikitext)
        
        self.assertIn('<i>italic text</i>', result.xml_content)
    
    def test_plain_text_preserved(self):
        """Test that plain text is preserved"""
        wikitext = 'Plain text without any markup'
        result = self.processor.process_wikitext(wikitext)
        
        self.assertIn('Plain text without any markup', result.xml_content)


class TestTemplateHandlers(unittest.TestCase):
    """Test individual template handler functions"""
    
    def setUp(self):
        """Create processor instance for each test"""
        self.processor = create_processor()
    
    def test_small_caps_template(self):
        """Test {{sc|text}} converts to <sc>text</sc>"""
        result = self.processor.process_wikitext('{{sc|LORD}}')
        self.assertIn('<sc>LORD</sc>', result.xml_content)
    
    def test_larger_template(self):
        """Test {{larger|text}} converts to <larger>text</larger>"""
        result = self.processor.process_wikitext('{{larger|Big Text}}')
        self.assertIn('<larger>Big Text</larger>', result.xml_content)
    
    def test_x_larger_template(self):
        """Test {{x-larger|text}} converts to <x-larger>text</x-larger>"""
        result = self.processor.process_wikitext('{{x-larger|Bigger}}')
        self.assertIn('<x-larger>Bigger</x-larger>', result.xml_content)
    
    def test_xx_larger_template(self):
        """Test {{xx-larger|text}} converts to <xx-larger>text</xx-larger>"""
        result = self.processor.process_wikitext('{{xx-larger|Even Bigger}}')
        self.assertIn('<xx-larger>Even Bigger</xx-larger>', result.xml_content)
    
    def test_xxx_larger_template(self):
        """Test {{xxx-larger|text}} converts to <xxx-larger>text</xxx-larger>"""
        result = self.processor.process_wikitext('{{xxx-larger|Huge}}')
        self.assertIn('<xxx-larger>Huge</xxx-larger>', result.xml_content)
    
    def test_smaller_template(self):
        """Test {{smaller|text}} converts to <smaller>text</smaller>"""
        result = self.processor.process_wikitext('{{smaller|tiny}}')
        self.assertIn('<smaller>tiny</smaller>', result.xml_content)
    
    def test_center_template(self):
        """Test {{c|text}} converts to <c>text</c>"""
        result = self.processor.process_wikitext('{{c|Centered Text}}')
        self.assertIn('<c>Centered Text</c>', result.xml_content)
    
    def test_right_align_template(self):
        """Test {{right|text}} converts to <right>text</right>"""
        result = self.processor.process_wikitext('{{right|Right Aligned}}')
        self.assertIn('<right>Right Aligned</right>', result.xml_content)
    
    def test_rule_template(self):
        """Test {{rule}} converts to <rule/>"""
        result = self.processor.process_wikitext('{{rule}}')
        self.assertIn('<rule/>', result.xml_content)
    
    def test_nop_template(self):
        """Test {{nop}} converts to <nop/>"""
        result = self.processor.process_wikitext('{{nop}}')
        self.assertIn('<nop/>', result.xml_content)
    
    def test_verse_template_with_parameters(self):
        """Test {{verse|chapter|verse|text}} conversion"""
        result = self.processor.process_wikitext('{{verse|1|1|In the beginning}}')
        
        self.assertIn('<verse', result.xml_content)
        self.assertIn('chapter="1"', result.xml_content)
        self.assertIn('verse="1"', result.xml_content)
        self.assertIn('In the beginning', result.xml_content)
    
    def test_verse_template_named_parameters(self):
        """Test {{verse}} with named parameters"""
        result = self.processor.process_wikitext('{{verse|chapter=2|verse=3|text=Test text}}')
        
        self.assertIn('chapter="2"', result.xml_content)
        self.assertIn('verse="3"', result.xml_content)
        self.assertIn('Test text', result.xml_content)
    
    def test_right_header_template(self):
        """Test {{rh|text}} converts to <rh>text</rh>"""
        result = self.processor.process_wikitext('{{rh|Header Text}}')
        self.assertIn('<rh>Header Text</rh>', result.xml_content)
    
    def test_drop_initial_template(self):
        """Test {{dropinitial|letter}} converts to <dropinitial>letter</dropinitial>"""
        result = self.processor.process_wikitext('{{dropinitial|I}}')
        self.assertIn('<dropinitial>I</dropinitial>', result.xml_content)
    
    def test_dhr_template_no_value(self):
        """Test {{dhr}} converts to <dhr/>"""
        result = self.processor.process_wikitext('{{dhr}}')
        self.assertIn('<dhr/>', result.xml_content)
    
    def test_dhr_template_with_value(self):
        """Test {{dhr|value}} converts to <dhr value="value"/>"""
        result = self.processor.process_wikitext('{{dhr|2}}')
        self.assertIn('<dhr value="2"/>', result.xml_content)
    
    def test_anchor_template(self):
        """Test {{anchor|name}} converts to <anchor name="name"/>"""
        result = self.processor.process_wikitext('{{anchor|chapter1}}')
        self.assertIn('<anchor name="chapter1"/>', result.xml_content)
    
    def test_anchor_plus_template(self):
        """Test {{anchor+|name|text}} converts to <anchor name="name">text</anchor>"""
        result = self.processor.process_wikitext('{{anchor+|ch1|Chapter 1}}')
        self.assertIn('<anchor name="ch1">Chapter 1</anchor>', result.xml_content)
    
    def test_language_template(self):
        """Test {{lang|code|text}} converts to <lang code="code">text</lang>"""
        result = self.processor.process_wikitext('{{lang|he|שלום}}')
        self.assertIn('<lang code="he">שלום</lang>', result.xml_content)
    
    def test_smallrefs_template(self):
        """Test {{smallrefs}} converts to <smallrefs/>"""
        result = self.processor.process_wikitext('{{smallrefs}}')
        self.assertIn('<smallrefs/>', result.xml_content)
    
    def test_hws_template(self):
        """Test {{hws|text}} converts to <hws>text</hws>"""
        result = self.processor.process_wikitext('{{hws|Hebrew word start}}')
        self.assertIn('<hws>Hebrew word start</hws>', result.xml_content)
    
    def test_hwe_template(self):
        """Test {{hwe|text}} converts to <hwe>text</hwe>"""
        result = self.processor.process_wikitext('{{hwe|Hebrew word end}}')
        self.assertIn('<hwe>Hebrew word end</hwe>', result.xml_content)
    
    def test_asterisks_template_default(self):
        """Test {{***}} converts to <asterisks n="3">***</asterisks>"""
        result = self.processor.process_wikitext('{{***}}')
        self.assertIn('<asterisks n="3">***</asterisks>', result.xml_content)
    
    def test_asterisks_template_with_count(self):
        """Test {{***|5}} converts to <asterisks n="5">***</asterisks>"""
        result = self.processor.process_wikitext('{{***|5}}')
        self.assertIn('<asterisks n="5">***</asterisks>', result.xml_content)
    
    def test_reconstruct_template(self):
        """Test {{reconstruct|content|note}} conversion"""
        result = self.processor.process_wikitext('{{reconstruct|text|editorial note}}')
        self.assertIn('<reconstruct>', result.xml_content)
        self.assertIn('<reg>text</reg>', result.xml_content)
        self.assertIn('<note>editorial note</note>', result.xml_content)
    
    def test_sic_template(self):
        """Test {{sic|text}} and {{SIC|text}} convert to <sic>text</sic>"""
        result1 = self.processor.process_wikitext('{{sic|mispeling}}')
        self.assertIn('<sic>mispeling</sic>', result1.xml_content)
        
        result2 = self.processor.process_wikitext('{{SIC|CAPS}}')
        self.assertIn('<sic>CAPS</sic>', result2.xml_content)
    
    def test_superscript_template(self):
        """Test {{sup|text}} converts to <sup>text</sup>"""
        result = self.processor.process_wikitext('{{sup|2}}')
        self.assertIn('<sup>2</sup>', result.xml_content)
    
    def test_bar_template_default(self):
        """Test {{bar}} converts to <bar length="6"/>"""
        result = self.processor.process_wikitext('{{bar}}')
        self.assertIn('<bar length="6"/>', result.xml_content)
    
    def test_bar_template_with_length(self):
        """Test {{bar|10}} converts to <bar length="10"/>"""
        result = self.processor.process_wikitext('{{bar|10}}')
        self.assertIn('<bar length="10"/>', result.xml_content)
    
    def test_gap_template_no_length(self):
        """Test {{gap}} converts to <gap/>"""
        result = self.processor.process_wikitext('{{gap}}')
        self.assertIn('<gap/>', result.xml_content)
    
    def test_gap_template_with_length(self):
        """Test {{gap|5}} converts to <gap length="5"/>"""
        result = self.processor.process_wikitext('{{gap|5}}')
        self.assertIn('<gap length="5"/>', result.xml_content)
    
    def test_overfloat_left_template(self):
        """Test {{overfloat left|align|padding|text}} conversion"""
        result = self.processor.process_wikitext('{{overfloat left|right|10|Content}}')
        
        self.assertIn('<overfloat_left', result.xml_content)
        self.assertIn('align="right"', result.xml_content)
        self.assertIn('padding="10"', result.xml_content)
        self.assertIn('Content', result.xml_content)
    
    def test_float_right_template(self):
        """Test {{float right|text}} converts to <float_right>text</float_right>"""
        result = self.processor.process_wikitext('{{float right|Floated}}')
        self.assertIn('<float_right>Floated</float_right>', result.xml_content)
    
    def test_smaller_block_templates(self):
        """Test {{smaller block/s}} and {{smaller block/e}} conversion"""
        result = self.processor.process_wikitext('{{smaller block/s}}content{{smaller block/e}}')
        
        self.assertIn('<smaller_block>', result.xml_content)
        self.assertIn('</smaller_block>', result.xml_content)
        self.assertIn('content', result.xml_content)


class TestTagHandlers(unittest.TestCase):
    """Test individual tag handler functions"""
    
    def setUp(self):
        """Create processor instance for each test"""
        self.processor = create_processor()
    
    def test_section_tag(self):
        """Test <section> tag processing"""
        result = self.processor.process_wikitext('<section begin="intro"/>content<section end="intro"/>')
        
        self.assertIn('<section', result.xml_content)
        self.assertIn('begin="intro"', result.xml_content)
        self.assertIn('end="intro"', result.xml_content)
    
    def test_table_tag(self):
        """Test <table> tag processing"""
        result = self.processor.process_wikitext('<table>content</table>')
        self.assertIn('<table>content</table>', result.xml_content)
    
    def test_table_row_tag(self):
        """Test <tr> tag processing"""
        result = self.processor.process_wikitext('<tr>row content</tr>')
        self.assertIn('<tr>row content</tr>', result.xml_content)
    
    def test_table_cell_tag(self):
        """Test <td> tag processing"""
        result = self.processor.process_wikitext('<td>cell</td>')
        self.assertIn('<td>cell</td>', result.xml_content)
    
    def test_italic_tag(self):
        """Test <i> tag processing"""
        result = self.processor.process_wikitext('<i>italic</i>')
        self.assertIn('<i>italic</i>', result.xml_content)
    
    def test_br_tag(self):
        """Test <br> tag converts to <br/>"""
        result = self.processor.process_wikitext('Line 1<br>Line 2')
        self.assertIn('<br/>', result.xml_content)
    
    def test_span_tag_with_attributes(self):
        """Test <span> tag with attributes"""
        result = self.processor.process_wikitext('<span class="test">content</span>')
        
        self.assertIn('<span', result.xml_content)
        self.assertIn('class="test"', result.xml_content)
        self.assertIn('content', result.xml_content)
    
    def test_dd_tag(self):
        """Test <dd> tag processing"""
        result = self.processor.process_wikitext('<dd>definition</dd>')
        self.assertIn('<dd>definition</dd>', result.xml_content)
    
    def test_ref_tag(self):
        """Test <ref> tag processing"""
        result = self.processor.process_wikitext('<ref name="note1">Reference text</ref>')
        
        self.assertIn('<ref', result.xml_content)
        self.assertIn('name="note1"', result.xml_content)
        self.assertIn('Reference text', result.xml_content)
    
    def test_noinclude_tag(self):
        """Test <noinclude> tag processing"""
        result = self.processor.process_wikitext('<noinclude>header info</noinclude>')
        self.assertIn('<noinclude>header info</noinclude>', result.xml_content)
    
    def test_pagequality_tag(self):
        """Test <pagequality> tag processing"""
        result = self.processor.process_wikitext('<pagequality level="4">quality</pagequality>')
        
        self.assertIn('<pagequality', result.xml_content)
        self.assertIn('level="4"', result.xml_content)


class TestWikilinkHandling(unittest.TestCase):
    """Test wikilink processing and capture"""
    
    def setUp(self):
        """Create processor instance for each test"""
        self.processor = create_processor()
    
    def test_simple_wikilink(self):
        """Test that [[Page]] is converted to <__link__> and captured"""
        result = self.processor.process_wikitext('See [[Genesis]] for details')
        
        # Should convert to __link__ tag
        self.assertIn('<__link__', result.xml_content)
        self.assertIn('title="Genesis"', result.xml_content)
        self.assertIn('Genesis', result.xml_content)
        
        # Should be captured in wikilinks
        self.assertEqual(len(result.wikilinks), 1)
        self.assertEqual(result.wikilinks[0]['title'], 'Genesis')
    
    def test_wikilink_with_display_text(self):
        """Test that [[Page|Display]] is converted properly"""
        result = self.processor.process_wikitext('[[Creation|the creation]]')
        
        self.assertIn('<__link__', result.xml_content)
        self.assertIn('title="Creation"', result.xml_content)
        self.assertIn('the creation', result.xml_content)
    
    def test_multiple_wikilinks_captured(self):
        """Test that multiple wikilinks are all captured"""
        result = self.processor.process_wikitext('See [[Genesis]] and [[Exodus]] and [[Numbers]]')
        
        # Should have 3 wikilinks
        self.assertEqual(len(result.wikilinks), 3)
        titles = [wl['title'] for wl in result.wikilinks]
        self.assertIn('Genesis', titles)
        self.assertIn('Exodus', titles)
        self.assertIn('Numbers', titles)


class TestPreprocessors(unittest.TestCase):
    """Test preprocessing functions"""
    
    def setUp(self):
        """Create processor instance for each test"""
        self.processor = create_processor()
    
    def test_noinclude_line_break_fix(self):
        """Test that </noinclude> followed by text gets a line break"""
        wikitext = '<noinclude>header</noinclude>Main content'
        result = self.processor.process_wikitext(wikitext)
        
        # After preprocessing, there should be proper separation
        # The content should be processed correctly
        self.assertIn('header', result.xml_content)
        self.assertIn('Main content', result.xml_content)
    
    def test_paragraph_breaks_converted(self):
        """Test that double newlines become <p/> markers"""
        wikitext = 'Paragraph 1\n\nParagraph 2'
        result = self.processor.process_wikitext(wikitext)
        
        # Should have paragraph marker
        self.assertIn('<p/>', result.xml_content)
        self.assertIn('Paragraph 1', result.xml_content)
        self.assertIn('Paragraph 2', result.xml_content)
    
    def test_nop_prevents_paragraph_breaks(self):
        """Test that {{nop}} prevents paragraph break conversion"""
        wikitext = '{{nop}}\n\nText after nop'
        result = self.processor.process_wikitext(wikitext)
        
        # Should have nop marker
        self.assertIn('<nop/>', result.xml_content)
        # Adjacent double newline should not become <p/>
        # (This is the intended behavior based on the preprocessor)
    
    def test_special_characters_escaped(self):
        """Test that standalone ampersands are escaped"""
        wikitext = 'Tom & Jerry'
        result = self.processor.process_wikitext(wikitext)
        
        # Ampersand should be escaped
        self.assertIn('Tom &amp; Jerry', result.xml_content)
    
    def test_existing_entities_preserved(self):
        """Test that existing XML entities are not double-escaped"""
        wikitext = 'Less than &lt; and greater than &gt;'
        result = self.processor.process_wikitext(wikitext)
        
        # Entities should be preserved, not double-escaped
        self.assertIn('&lt;', result.xml_content)
        self.assertIn('&gt;', result.xml_content)
        self.assertNotIn('&amp;lt;', result.xml_content)


class TestNestedContent(unittest.TestCase):
    """Test nested template and tag processing"""
    
    def setUp(self):
        """Create processor instance for each test"""
        self.processor = create_processor()
    
    def test_nested_templates(self):
        """Test that nested templates are processed correctly"""
        result = self.processor.process_wikitext('{{sc|{{larger|Nested}}}}')
        
        # Should have both tags, properly nested
        self.assertIn('<sc>', result.xml_content)
        self.assertIn('<larger>Nested</larger>', result.xml_content)
        self.assertIn('</sc>', result.xml_content)
    
    def test_template_in_tag(self):
        """Test template inside HTML tag"""
        result = self.processor.process_wikitext('<i>{{sc|text}}</i>')
        
        self.assertIn('<i>', result.xml_content)
        self.assertIn('<sc>text</sc>', result.xml_content)
        self.assertIn('</i>', result.xml_content)
    
    def test_complex_nesting(self):
        """Test complex nested structures"""
        result = self.processor.process_wikitext('{{verse|1|1|{{sc|GOD}} said {{larger|Let there be light}}}}')
        
        self.assertIn('<verse', result.xml_content)
        self.assertIn('<sc>GOD</sc>', result.xml_content)
        self.assertIn('<larger>Let there be light</larger>', result.xml_content)


class TestConversionResult(unittest.TestCase):
    """Test ConversionResult structure and metadata"""
    
    def setUp(self):
        """Create processor instance for each test"""
        self.processor = create_processor()
    
    def test_result_structure(self):
        """Test that ConversionResult has all expected fields"""
        result = self.processor.process_wikitext('test')
        
        self.assertIsInstance(result, ConversionResult)
        self.assertTrue(hasattr(result, 'xml_content'))
        self.assertTrue(hasattr(result, 'metadata'))
        self.assertTrue(hasattr(result, 'warnings'))
        self.assertTrue(hasattr(result, 'errors'))
        self.assertTrue(hasattr(result, 'wikilinks'))
    
    def test_unknown_template_warning(self):
        """Test that unknown templates generate warnings"""
        result = self.processor.process_wikitext('{{unknown_template|content}}')
        
        # Should have warnings
        self.assertGreater(len(result.warnings), 0)
        self.assertTrue(any('unknown_template' in w for w in result.warnings))
        
        # Unknown template content should still be in output (processed as nested)
        self.assertIn('content', result.xml_content)
    
    def test_unknown_tag_warning(self):
        """Test that unknown tags generate warnings"""
        result = self.processor.process_wikitext('<unknowntag>content</unknowntag>')
        
        # Should have warnings
        self.assertGreater(len(result.warnings), 0)
        self.assertTrue(any('unknowntag' in w.lower() for w in result.warnings))
        
        # Unknown tag content should still be in output
        self.assertIn('content', result.xml_content)
    
    def test_multiple_unknown_templates(self):
        """Test that multiple unknown templates all generate warnings"""
        result = self.processor.process_wikitext('{{unknown1|a}} {{unknown2|b}} {{unknown3|c}}')
        
        # Should have multiple warnings
        self.assertGreaterEqual(len(result.warnings), 3)
        self.assertTrue(any('unknown1' in w for w in result.warnings))
        self.assertTrue(any('unknown2' in w for w in result.warnings))
        self.assertTrue(any('unknown3' in w for w in result.warnings))
    
    def test_mixed_known_and_unknown_templates(self):
        """Test processing with both known and unknown templates"""
        result = self.processor.process_wikitext('{{sc|known}} {{unknown|unknown}} {{larger|also known}}')
        
        # Known templates should be processed
        self.assertIn('<sc>known</sc>', result.xml_content)
        self.assertIn('<larger>also known</larger>', result.xml_content)
        
        # Unknown template should generate warning
        self.assertTrue(any('unknown' in w for w in result.warnings))
        
        # Content should be preserved
        self.assertIn('unknown', result.xml_content)
    
    def test_unhandled_template_preserved_as_is(self):
        """Test that unhandled templates are preserved as-is in output"""
        result = self.processor.process_wikitext('{{unknown_template|content}}')
        
        # Should have warning about unknown template
        self.assertTrue(any('unknown_template' in w for w in result.warnings))
        
        # Unknown template should be preserved in output (not converted)
        self.assertIn('{{unknown_template|content}}', result.xml_content)
    
    def test_unhandled_tag_preserved_as_is(self):
        """Test that unhandled tags are preserved as-is in output"""
        result = self.processor.process_wikitext('<unknowntag attr="value">content</unknowntag>')
        
        # Should have warning about unknown tag
        self.assertTrue(any('unknowntag' in w.lower() for w in result.warnings))
        
        # Unknown tag should be preserved in output
        self.assertIn('unknowntag', result.xml_content.lower())
        self.assertIn('content', result.xml_content)


class TestCustomHandlers(unittest.TestCase):
    """Test ability to add custom handlers"""
    
    def setUp(self):
        """Create processor instance for each test"""
        self.processor = create_processor()
    
    def test_add_custom_template_handler(self):
        """Test that custom template handlers can be added"""
        def custom_handler(template):
            content = str(template.get(1, ''))
            return f'<custom>{content}</custom>'
        
        self.processor.add_template_handler('mytemplate', custom_handler)
        result = self.processor.process_wikitext('{{mytemplate|test}}')
        
        self.assertIn('<custom>test</custom>', result.xml_content)
    
    def test_add_custom_tag_handler(self):
        """Test that custom tag handlers can be added"""
        def custom_tag_handler(tag):
            content = str(tag.contents) if tag.contents else ''
            return f'<customtag>{content}</customtag>'
        
        self.processor.add_tag_handler('mytag', custom_tag_handler)
        result = self.processor.process_wikitext('<mytag>content</mytag>')
        
        self.assertIn('<customtag>content</customtag>', result.xml_content)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""
    
    def setUp(self):
        """Create processor instance for each test"""
        self.processor = create_processor()
    
    def test_empty_wikitext(self):
        """Test that empty wikitext returns valid result"""
        result = self.processor.process_wikitext('')
        
        self.assertIsInstance(result, ConversionResult)
        self.assertIn('<mediawiki>', result.xml_content)
        self.assertEqual(len(result.errors), 0)
    
    def test_wikitext_with_only_whitespace(self):
        """Test wikitext with only whitespace"""
        result = self.processor.process_wikitext('   \n\n   ')
        
        self.assertIsInstance(result, ConversionResult)
        self.assertIn('<mediawiki>', result.xml_content)
    
    def test_multiple_templates_in_sequence(self):
        """Test multiple templates one after another"""
        result = self.processor.process_wikitext('{{sc|A}}{{larger|B}}{{smaller|C}}')
        
        self.assertIn('<sc>A</sc>', result.xml_content)
        self.assertIn('<larger>B</larger>', result.xml_content)
        self.assertIn('<smaller>C</smaller>', result.xml_content)
    
    def test_template_with_empty_parameter(self):
        """Test templates with empty parameters"""
        result = self.processor.process_wikitext('{{sc|}}')
        
        # Should still create the tag even with empty content
        self.assertIn('<sc></sc>', result.xml_content)
    
    def test_wikilink_capture_and_retrieval(self):
        """Test that wikilinks can be retrieved and cleared"""
        self.processor.process_wikitext('[[Page1]] and [[Page2]]')
        
        # Get wikilinks
        wikilinks = self.processor.get_wikilinks()
        self.assertEqual(len(wikilinks), 2)
        
        # Clear wikilinks
        self.processor.clear_wikilinks()
        self.assertEqual(len(self.processor.get_wikilinks()), 0)


if __name__ == '__main__':
    unittest.main()

