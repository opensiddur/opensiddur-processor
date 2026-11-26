"""Monthly service preserves interleaved rubrics and non-seasonal Kaddish."""
import unittest
from unittest.mock import patch

from lxml import etree

from opensiddur.importer.asher_selichot import penitential_days as service
from opensiddur.importer.asher_selichot.build import PRAYER, TEI, XML
from opensiddur.importer.asher_selichot.first_day import entry


class YomKippurKatanTests(unittest.TestCase):
    def test_occasion_is_the_eve_of_the_new_moon(self):
        with patch('opensiddur.importer.asher_selichot.first_day.titles'):
            root=entry('he','example',{},book=True,remaining_services=('yom-kippur-katan',))
        gate=root.find('.//{'+service.J+'}conditional[@xml:id="yom_kippur_katan_occasion"]',namespaces={'xml':XML[1:-1]})
        self.assertEqual({'opensiddur:hebrew-date','opensiddur:day-of-week'},{n.get('type') for n in gate.findall('.//{'+TEI+'}fs')})
        self.assertIsNone(gate.find('.//{'+TEI+'}note'))

    def test_two_kaddish_supplies_have_distinct_scopes_without_ten_days(self):
        root=etree.Element('{'+TEI+'}body')
        for id,target in [('reader',PRAYER+'kaddish/chatzi'),('conclusion',PRAYER+'kaddish/shalem')]:
            service.full_kaddish(root,'yom-kippur-katan',target,id)
        self.assertEqual([n.get(XML+'id') for n in root.findall('{'+service.J+'}declare')],['reader','conclusion'])
        self.assertEqual([n.get('value') for n in root.findall('.//{'+TEI+'}binary')],['false']*4)
        self.assertEqual([n.get('target') for n in root.findall('{'+service.J+'}transclude')],[PRAYER+'kaddish/chatzi',PRAYER+'kaddish/shalem'])

    def test_abbreviation_does_not_add_space_after_dash(self):
        f={'en':{'scan':'s395','printed_page':'196','text':'Mercy,—for his sake, &c.'},'notes':{'en':[]}}
        r={'fragments':[f],'stanzas':[{'fragments':[f]}],'refrain_cues':{'en':r'for his sake, &c\.'},'refrain':{'en':'for his sake he will forgive.'}}
        root=etree.Element('{'+TEI+'}body');service.pizmon(root,r,'en','urn:example')
        p=root.find('.//{'+TEI+'}p')
        self.assertEqual(p.text,'Mercy,—')
        self.assertEqual(p[0][0][0].text,'for his sake, &c.')

    def test_empty_counterpart_has_no_rewinding_page_break(self):
        root=etree.Element('{'+TEI+'}body')
        r={'kind':'rubric','fragments':[{'en':{'scan':'s389','printed_page':'193','text':''}}]}
        service.printed(root,r,'en','urn:example')
        self.assertEqual(root.findall('.//{'+TEI+'}pb'),[])

    def test_interleaved_cue_stays_before_continuation(self):
        def f(s,t):return {'en':dict(scan='s'+str(s),printed_page=str((s-3)//2),text=t),'notes':{'en':[]}}
        cue={'id':'verses_after_test','kind':'rubric','fragments':[f(389,'Say the prayer.')],'expansion_targets':[PRAYER+'ashamnu']}
        r={'id':'test','kind':'poem','fragments':[f(389,'Remember the'),dict(f(391,'bull.'),paragraph_start=True)],'interleaved_rubrics':[dict(before_fragment=1,reading=cue)]}
        root=etree.Element('{'+TEI+'}body');unit=service.printed(root,r,'en','urn:example','yom-kippur-katan')
        self.assertEqual([n.get('facs').split('/n')[-1].split('_')[0] for n in unit.findall('.//{'+TEI+'}pb')],['388','388','390'])
        self.assertEqual(unit.find('.//{'+TEI+'}note').text.strip(),'Say the prayer.')
        self.assertEqual(''.join(unit[-1].itertext()).strip(),'bull.')
        self.assertIsNone(unit.find('{'+TEI+'}p'))
