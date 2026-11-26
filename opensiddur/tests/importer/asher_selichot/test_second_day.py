"""Synthetic checks for second-day scope, repeated cues and semantic alignment."""
import unittest

from lxml import etree

from opensiddur.importer.asher_selichot.build import TEI, XML
from opensiddur.importer.asher_selichot.first_day import expansion_scope
from opensiddur.importer.asher_selichot.second_day import OPENING, pizmon, printed_unit
from opensiddur.importer.scan.reverse import streams


class SecondDayTest(unittest.TestCase):
    @staticmethod
    def fragment(scan, he, en='English text.'):
        return {'he':{'scan':scan,'printed_page':'28','text':he},
                'en':{'scan':'s'+str(int(scan[1:])+1),'printed_page':'28','text':en},
                'notes':{'he':[],'en':[]}}

    def test_pizmon_choices_and_stanza_boundaries_are_independent_of_layout(self):
        urn='urn:x-opensiddur:text:poem:yisrael_nosha'
        refrain={'he':'כי אתה׃','en':'Thou pardonest.'}
        reading={'urn':urn,'stanzas':[
            {'id':'opening','fragments':[self.fragment('s58','ישראל נושע ·')],'refrain':refrain},
            {'id':'petition','fragments':[self.fragment('s58','לילה'),self.fragment('s60','ויום ·')],
             'cue':{'he':'כי','en':'(Thou, &c.)'},'opening_cue':{'he':'וישראל וכו׳','en':'(Israel, &c.)'}}]}
        root=pizmon('he','fixture',reading,refrain)
        milestones=root.findall(f'.//{{{TEI}}}milestone')
        self.assertEqual([urn+'/opening',urn+'/petition',None],[m.get('corresp') for m in milestones])
        self.assertTrue(all(m.get('unit')=='stanza' for m in milestones))
        self.assertIsNone(root.find(f'.//{{{TEI}}}lg[@corresp]'))
        lines=root.findall(f'.//{{{TEI}}}lg')[1].findall(f'{{{TEI}}}l')
        self.assertEqual('לילה ויום\u00a0·',''.join(lines[0].itertext()).strip())
        self.assertIsNotNone(lines[0].find(f'{{{TEI}}}pb'))
        choices=root.findall(f'.//{{{TEI}}}choice')
        self.assertEqual(['כי אתה׃','ישראל נושע · כי אתה׃'],[''.join(c.find(f'{{{TEI}}}expan').itertext()) for c in choices])
        self.assertNotIn('Thou pardonest.', ' '.join(streams(pizmon('en','fixture',reading,refrain)).values()).split('(Thou,')[1])
        self.assertIsNone(pizmon('en','fixture',reading,refrain).find(f'.//{{{TEI}}}head'))

    def test_invocation_remains_body_and_page_break_does_not_split_line(self):
        root=etree.Element('{'+TEI+'}div');root.set(XML+'lang','he')
        reading={'kind':'poem','fragments':[self.fragment('s54','אלהינו ואלהי אבותינו\nאיה קנאתך · ועתה'),self.fragment('s56','הושיענו׃')]}
        unit=printed_unit(root,reading,'he','urn:x-opensiddur:text:poem:fixture')
        self.assertIsNone(unit.find(f'{{{TEI}}}head'))
        self.assertEqual('אלהינו ואלהי אבותינו',unit.find(f'{{{TEI}}}lg/{{{TEI}}}l').text)
        self.assertIn('ועתה הושיענו׃',' '.join(streams(root).values()))
        self.assertEqual(3,len(unit.findall(f'{{{TEI}}}lg/{{{TEI}}}l')))

    def test_expansion_feature_does_not_change_existing_repetition_default(self):
        root=etree.Element('{'+TEI+'}div')
        expansion_scope(root,'existing',True)
        expansion_scope(root,'prayers',False,feature='prayers_present')
        self.assertEqual(['repetitions_present','prayers_present'],[f.get('name') for f in root.findall(f'.//{{{TEI}}}f')])
        self.assertIn('urn:x-opensiddur:text:prayer:selah_lanu_avinu',OPENING)
        self.assertNotIn('urn:x-opensiddur:text:poem:eikh_niftah_peh',OPENING)

    def test_bookmark_audit_rejects_a_day_below_its_pizmon(self):
        from opensiddur.importer.asher_selichot.check_book_pdf import day_bookmarks
        rows=[(0,'FIRST DAY',5,650),(1,'פזמון',20,600),(0,'SECOND DAY',36,600),(1,'פזמון',39,600)]
        self.assertEqual([rows[0],rows[2]],day_bookmarks(rows))
        with self.assertRaisesRegex(ValueError,'top-level bookmark'):
            day_bookmarks(rows[:2]+[(1,*rows[2][1:]),rows[3]])
        with self.assertRaisesRegex(ValueError,'expected child heading'):
            day_bookmarks(rows[:3])
