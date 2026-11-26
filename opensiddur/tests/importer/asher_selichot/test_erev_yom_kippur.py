"""Erev Yom Kippur keeps its own bounds, full refrains and Reader role."""
import unittest

from lxml import etree

from opensiddur.importer.asher_selichot import penitential_days as service
from opensiddur.importer.asher_selichot.build import TEI, XML


class ErevYomKippurTests(unittest.TestCase):
    def test_service_identity_is_independent_of_penitential_ordinals(self):
        self.assertEqual(service.service_urn('erev-yom-kippur'),'urn:x-opensiddur:text:siddur:selichot/erev_yom_kippur')
        self.assertEqual(service.manifest_name('erev-yom-kippur'),'erev-yom-kippur')
        self.assertEqual(service.service_filename('erev-yom-kippur'),'erev_yom_kippur.xml')
        self.assertNotIn('erev-yom-kippur',service.DAYS)
        with self.assertRaises(ValueError):service.manifest_name('second-fast')

    def test_fulfilled_kaddish_preserves_reader_and_seasonal_scope(self):
        root=etree.Element('{'+TEI+'}div')
        service.expanded_rubric(root,{'id':'conclusion','performance_instruction':{'en':'The Reader'},'supply_kaddish':True,'expansion_targets':['urn:x-opensiddur:text:prayer:kaddish/shalem'],'fragments':[{'notes':{'en':[]}}]},'en','erev-yom-kippur')
        self.assertEqual(root.find('.//{'+TEI+'}note').text,'The Reader')
        self.assertNotIn('says',''.join(root.itertext()))
        self.assertEqual([n.get('value')for n in root.findall('.//{'+TEI+'}binary')],['false','true'])
        declaration=root.find('{'+service.J+'}declare')
        self.assertEqual(root.find('{'+service.J+'}endDeclare').get('target'),'#'+declaration.get(XML+'id'))

    def test_full_refrain_variants_keep_words_and_footnotes(self):
        f={'en':{'scan':'s315','printed_page':'156','text':'Be pleased; O let this sign be to-morrow.'},'notes':{'en':[{'anchor':'pleased;','text':'Fasting note.'}]}}
        g={'en':{'scan':'s317','printed_page':'157','text':'Come near. O let that sign be to-morrow. (Be pleased, &c.)'},'notes':{'en':[]}}
        r={'fragments':[f,g],'stanzas':[{'fragments':[f]},{'fragments':[g]}],'refrain':{'en':'O let this sign be to-morrow.'},'refrain_cues':{'en':'(?!)'},'opening_cue':{'en':'(Be pleased, &c.)'},'full_refrain_pattern':{'en':r'O let th(?:is|at) sign be to-morrow\.'}}
        root=etree.Element('{'+TEI+'}body');service.pizmon(root,r,'en','urn:example')
        self.assertEqual([n.text for n in root.findall('.//{'+TEI+'}seg[@type="refrain"]')][:2],['O let this sign be to-morrow.','O let that sign be to-morrow.'])
        self.assertEqual(len(root.findall('.//{'+TEI+'}note')),1)
        self.assertEqual(root.find('.//{'+TEI+'}expan').text,f['en']['text'])

    def test_index_gate_uses_ninth_of_tishrei_without_printed_instruction(self):
        from unittest.mock import patch

        from opensiddur.importer.asher_selichot.first_day import entry
        with patch('opensiddur.importer.asher_selichot.first_day.titles'):
            root=entry('he','example',{},book=True,include_erev_yom_kippur=True)
        condition=root.find('.//{'+service.J+'}conditional[@xml:id="erev_yom_kippur_occasion"]',namespaces={'xml':XML[1:-1]})
        self.assertIsNotNone(condition)
        self.assertEqual([(f.get('name'),f[0].get('value'))for f in condition.findall('.//{'+TEI+'}fs[@type="opensiddur:hebrew-date"]/{'+TEI+'}f')],[('month','7'),('day','9')])
        self.assertIsNone(condition.find('.//{'+TEI+'}note'))
        self.assertEqual({'opensiddur:hebrew-date','opensiddur:holiday-aggregate'},{fs.get('type')for fs in condition.findall('.//{'+TEI+'}fs')})
