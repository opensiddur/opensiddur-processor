"""Synthetic sources exercise expansion without depending on edition data."""
import tempfile
import unittest
from pathlib import Path
from lxml import etree as E
from opensiddur.importer.siddur_expanded.compose import Composer
from opensiddur.importer.siddur_expanded.xml import Author, T, J, NS, TEXT, XID, parse_fragment, service
from opensiddur.exporter.compiler import CompilerProcessor
from opensiddur.exporter.linear import reset_linear_data, get_linear_data, ConditionalSettingEntry

class TestComposition(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for lang,title in [('he','כותרת'),('en','Heading')]:
            p=self.root/f'hasiddur_hashalem-birnbaum-1949-{lang}';p.mkdir()
            p.joinpath('index.xml').write_text(f'''<tei:TEI xmlns:tei="{T}" xmlns:j="{J}"><tei:text><tei:body>
            <tei:div corresp="{TEXT}section"><tei:head xml:lang="{lang}">{title}</tei:head>
            <j:conditional xml:id="local"><tei:fs type="opensiddur:recitation"><tei:f name="repetition"><tei:binary value="true"/></tei:f></tei:fs></j:conditional>
            <j:transclude target="{TEXT}prayer"/><j:endConditional target="#local"/>
            <j:transclude target="{TEXT}bible:genesis/1/1" targetEnd="{TEXT}bible:genesis/1/3"/>
            <tei:note type="instruction">Continue on page 4.</tei:note></tei:div>
            <tei:div corresp="{TEXT}prayer"><tei:p>Prayer words</tei:p></tei:div>
            </tei:body></tei:text></tei:TEI>''',encoding='utf-8')
        self.composer=Composer(self.root)
    def test_repeated_structure_has_distinct_scopes_and_preserves_range(self):
        tree=parse_fragment(self.composer.source(TEXT+'section')+self.composer.source(TEXT+'section'))
        ids=tree.xpath('//@xml:id',namespaces=NS)
        self.assertEqual(len(ids),len(set(ids)))
        for end in tree.iter('{'+J+'}endConditional'):
            self.assertIn(end.get('target')[1:],ids)
        ranges=tree.xpath('.//j:transclude[@targetEnd]',namespaces=NS)
        self.assertEqual(len(ranges),2)
        self.assertTrue(all(e.get('targetEnd')==TEXT+'bible:genesis/1/3' for e in ranges))
        self.assertNotIn('page 4',''.join(tree.itertext()))
        self.assertNotIn('Prayer words',''.join(tree.itertext()))
        self.assertEqual(len(tree.xpath('.//tei:head[@xml:lang="en"]',namespaces=NS)),2)
    def test_leaf_is_transcluded_without_copying_its_words(self):
        value=self.composer.source(TEXT+'prayer')
        self.assertIn('target="'+TEXT+'prayer"',value)
        self.assertNotIn('Prayer words',value)

    def test_explicit_service_wrapper_can_own_the_container_heading(self):
        tree=parse_fragment(self.composer.source(TEXT+'section',include_heading=False))
        self.assertFalse(tree.xpath('./tei:div/tei:head',namespaces=NS))
        self.assertTrue(tree.xpath('.//j:transclude',namespaces=NS))
        self.assertTrue(parse_fragment(self.composer.source(TEXT+'section')).xpath(
            './tei:div/tei:head',namespaces=NS))

    def test_wrapper_title_defers_to_the_same_language_prayer_title(self):
        self.composer.english[TEXT+'prayer'].insert(0, parse_fragment(
            '<tei:head xml:lang="en">ALENU</tei:head>')[0])
        root = parse_fragment('''<tei:div><tei:head xml:lang="he">עלינו</tei:head>
            <tei:head xml:lang="en">Alenu</tei:head><tei:pb n="1"/><j:declare xml:id="local"/>
            <j:transclude target="prayer"/></tei:div>''')[0]
        self.composer.remove_redundant_heads(root[-1], TEXT+'prayer')
        self.assertEqual(root.xpath('tei:head/text()', namespaces=NS), ['עלינו'])
        self.assertEqual(root[-1].tag, '{'+J+'}transclude')
        self.assertNotIn('Prayer words', ''.join(root.itertext()))

    def test_title_removal_respects_occurrences_and_conditional_boundaries(self):
        self.composer.english[TEXT+'prayer'].insert(0, parse_fragment(
            '<tei:head xml:lang="en">ALENU</tei:head>')[0])
        for boundary in ['<j:transclude target="earlier-prayer"/>',
                         '<j:conditional xml:id="eligible"/>',
                         '<j:endConditional target="#eligible"/>',
                         '<tei:p>Earlier prayer</tei:p>']:
            with self.subTest(boundary=boundary):
                root=parse_fragment('<tei:div><tei:head xml:lang="en">ALENU</tei:head>'
                                    +boundary+'<j:transclude target="prayer"/></tei:div>')[0]
                self.composer.remove_redundant_heads(root[-1], TEXT+'prayer')
                self.assertEqual(root.xpath('tei:head/text()', namespaces=NS), ['ALENU'])

    def test_conditionally_titled_leaf_does_not_remove_an_outer_title(self):
        leaf=self.composer.english[TEXT+'prayer']
        leaf.insert(0,parse_fragment('<j:conditional xml:id="eligible"/>')[0])
        leaf.insert(1,parse_fragment('<tei:head xml:lang="en">ALENU</tei:head>')[0])
        root=parse_fragment('''<tei:div><tei:head xml:lang="en">ALENU</tei:head>
                              <j:transclude target="prayer"/></tei:div>''')[0]
        self.composer.remove_redundant_heads(root[-1],TEXT+'prayer')
        self.assertEqual(root.xpath('tei:head/text()',namespaces=NS), ['ALENU'])

    def test_language_only_headings_do_not_shift_later_citations(self):
        # Hebrew starts the poems without titles; English titles both. The
        # subsequent bilingual citations must still precede their own prayers.
        primary = parse_fragment('''<tei:div>
            <j:transclude target="poem:first"/><j:transclude target="poem:second"/>
            <tei:head xml:lang="he">מקור א</tei:head><j:transclude target="prayer:first"/>
            <tei:head xml:lang="he">מקור ב</tei:head><j:transclude target="prayer:second"/>
            </tei:div>''')[0]
        english = parse_fragment('''<tei:div>
            <tei:head xml:lang="en">First poem</tei:head><j:transclude target="poem:first"/>
            <tei:head xml:lang="en">Second poem</tei:head><j:transclude target="poem:second"/>
            <tei:head xml:lang="en">First citation</tei:head><j:transclude target="prayer:first"/>
            <tei:head xml:lang="en">Second citation</tei:head><j:transclude target="prayer:second"/>
            </tei:div>''')[0]
        self.composer.merge_heads(primary, english)
        self.assertEqual([e.get('target') or e.text for e in primary], [
            'First poem', 'poem:first', 'Second poem', 'poem:second',
            'מקור א', 'First citation', 'prayer:first',
            'מקור ב', 'Second citation', 'prayer:second'])

    def test_extra_directions_do_not_move_a_heading_outside_its_condition(self):
        primary = parse_fragment('''<tei:div>
            <j:conditional xml:id="fast"/><tei:head xml:lang="he">קריאה</tei:head>
            <j:transclude target="reading"/><j:endConditional target="#fast"/>
            </tei:div>''')[0]
        english = parse_fragment('''<tei:div>
            <j:conditional xml:id="fast"/><tei:note type="instruction">Direction</tei:note>
            <tei:head xml:lang="en">Reading</tei:head>
            <j:transclude target="reading"/><j:endConditional target="#fast"/>
            </tei:div>''')[0]
        self.composer.merge_heads(primary, english)
        self.assertEqual([e.get('target') or e.text for e in primary],
                         [None, 'קריאה', 'Reading', 'reading', '#fast'])

    def test_different_prayer_orders_are_not_silently_paired(self):
        primary = parse_fragment('''<tei:div><tei:head>כותרת</tei:head>
            <j:transclude target="first"/><j:transclude target="second"/></tei:div>''')[0]
        english = parse_fragment('''<tei:div><tei:head>Heading</tei:head>
            <j:transclude target="second"/><j:transclude target="first"/></tei:div>''')[0]
        with self.assertRaisesRegex(ValueError, 'Cannot align structural headings'):
            self.composer.merge_heads(primary, english)
    def test_replacements_can_insert_reading_before_post_blessing(self):
        value=self.composer.source(TEXT+'section',replace={TEXT+'prayer':'<tei:div><tei:p>Inserted structure</tei:p></tei:div>'})
        self.assertIn('Inserted structure',value)
        self.assertNotIn('target="'+TEXT+'prayer"',value)
    def test_context_restores_settings_and_does_not_force_eligibility(self):
        a=Author();silent='<tei:p>silent text</tei:p>';repeated='<tei:p>repeated text</tei:p>'
        body=a.gate(service('shaharit'),a.context(silent,'shaharit')+a.context(repeated,'shaharit',True))
        # A later conditional must still see the reader's original setting.
        body+=a.gate(service('maariv'),'<tei:p>evening text</tei:p>')
        project=self.root/'synthetic';project.mkdir();project.joinpath('index.xml').write_text(f'<root xmlns:tei="{T}" xmlns:j="{J}">{body}</root>')
        for morning in [True,False]:
            reset_linear_data();data=get_linear_data();data.xml_cache.base_path=self.root
            data.conditional_settings.extend([
                ConditionalSettingEntry(source='declared',declare_id='reader',fs_type='opensiddur:service-time',feature_name='shaharit',value=morning),
                ConditionalSettingEntry(source='declared',declare_id='reader',fs_type='opensiddur:service-time',feature_name='maariv',value=not morning),
            ])
            result=CompilerProcessor('synthetic','index.xml').process();text=''.join(result.itertext())
            self.assertEqual('silent text' in text,morning)
            self.assertEqual('repeated text' in text,morning)
            self.assertEqual('evening text' in text,not morning)
        reset_linear_data()
    def test_occurrence_can_retime_a_rubric_without_overriding_the_date(self):
        # The Friday candle occurrence tests the upcoming first night, while
        # the ordinary occurrence still tests the current holiday day.
        tree=parse_fragment(self.composer.source(TEXT+'section',conditions={'local':service('shaharit')}))
        self.assertTrue(tree.xpath('.//j:conditional/tei:fs[@type="opensiddur:service-time"]',namespaces=NS))
        self.assertFalse(tree.xpath('.//j:conditional/tei:fs[@type="opensiddur:recitation"]',namespaces=NS))
        original=parse_fragment(self.composer.source(TEXT+'section'))
        self.assertTrue(original.xpath('.//j:conditional/tei:fs[@type="opensiddur:recitation"]',namespaces=NS))
        self.assertFalse(tree.xpath('.//j:declare',namespaces=NS))


class TestBirnbaumPinsAreDropped(unittest.TestCase):
    """Birnbaum pins some transclusions to itself. The expanded siddur leaves the edition to
    the volume's priorities, so it copies none of those pins."""

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        pin='@hasiddur_hashalem-birnbaum-1949-he'
        for lang in ['he','en']:
            p=root/f'hasiddur_hashalem-birnbaum-1949-{lang}';p.mkdir()
            p.joinpath('index.xml').write_text(f'''<tei:TEI xmlns:tei="{T}" xmlns:j="{J}"><tei:text><tei:body>
            <tei:div corresp="{TEXT}service"><j:transclude target="{TEXT}prayer:kaddish/yitgaddal{pin}"/>
            <j:transclude target="{TEXT}structure{pin}"/>
            <j:transclude target="{TEXT}bible:psalms/1/1{pin}" targetEnd="{TEXT}bible:psalms/1/3{pin}"/></tei:div>
            <tei:div corresp="{TEXT}structure"><j:transclude target="{TEXT}prayer:kaddish/yehe_shemeh{pin}"/></tei:div>
            <tei:div corresp="{TEXT}prayer:kaddish/yitgaddal"><tei:p>Words</tei:p></tei:div>
            <tei:div corresp="{TEXT}prayer:kaddish/yehe_shemeh"><tei:p>Words</tei:p></tei:div>
            </tei:body></tei:text></tei:TEI>''',encoding='utf-8')
        self.composer=Composer(root)

    def test_no_transclusion_keeps_a_pin(self):
        tree=parse_fragment(self.composer.source(TEXT+'service'))
        targets=tree.xpath('.//j:transclude/@target|.//j:transclude/@targetEnd',namespaces=NS)
        self.assertEqual(sorted(targets),sorted([
            TEXT+'prayer:kaddish/yitgaddal',TEXT+'prayer:kaddish/yehe_shemeh',
            TEXT+'bible:psalms/1/1',TEXT+'bible:psalms/1/3']))

    def test_a_pinned_structural_unit_is_expanded_like_an_unpinned_one(self):
        targets=parse_fragment(self.composer.source(TEXT+'service')).xpath(
            './/j:transclude/@target',namespaces=NS)
        self.assertFalse([t for t in targets if t.startswith(TEXT+'structure')])
        self.assertIn(TEXT+'prayer:kaddish/yehe_shemeh',targets)
