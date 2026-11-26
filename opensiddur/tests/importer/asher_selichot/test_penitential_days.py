"""Later penitential days retain language-specific cues and seasonal scopes."""
import copy
import unittest

from lxml import etree

from opensiddur.importer.asher_selichot import penitential_days as day
from opensiddur.importer.asher_selichot.build import TEI, XML
from opensiddur.importer.scan.reverse import streams


class LaterPenitentialDaysTests(unittest.TestCase):
    def test_opening_words_are_not_mistaken_for_concluding_cue(self):
        f={'he':{'scan':'s300','printed_page':'149','text':'יי יי אל רחום׃'},
           'en':{'scan':'s301','printed_page':'149','text':'The Eternal is merciful.'},'notes':{'he':[],'en':[]}}
        g={'he':{'scan':'s302','printed_page':'150','text':'אזכרה׃ יי יי'},
           'en':{'scan':'s303','printed_page':'150','text':'I remember. (The Eternal, &c.)'},'notes':{'he':[],'en':[]}}
        r={'fragments':[f,g],'stanzas':[{'fragments':[f]},{'fragments':[g]}],
           'refrain':{'he':'','en':''},'refrain_cues':{'he':'(?!)','en':'(?!)'},
           'opening_cue':{'he':'יי יי','en':'(The Eternal, &c.)'}}
        for lang in ['he','en']:
            root=etree.Element('{'+TEI+'}body');day.pizmon(root,r,lang,'urn:example')
            choices=root.findall('.//{'+TEI+'}choice')
            self.assertEqual(len(choices),1)
            self.assertEqual(choices[0].find('{'+TEI+'}expan').text,f[lang]['text'])

    def test_english_final_cue_repeats_opening_including_refrain(self):
        f={'en':{'scan':'s275','printed_page':'136','text':'Thou who dwellest. My life at my request.'},'notes':{'en':[]}}
        g={'en':{'scan':'s277','printed_page':'137','text':'Let my voice. (My life, &c.) (Thou who dwellest, &c.)'},'notes':{'en':[]}}
        r={'fragments':[f,g],'stanzas':[{'fragments':[f]},{'fragments':[g]}],
           'refrain':{'en':'My life at my request.'},'refrain_cues':{'en':r'\(My life, &c\.\)'},
           'opening_cue':{'en':'(Thou who dwellest, &c.)'}}
        root=etree.Element('{'+TEI+'}body');day.pizmon(root,r,'en','urn:example')
        expansions=root.findall('.//{'+TEI+'}expan')
        self.assertEqual([e.text for e in expansions],[r['refrain']['en'],f['en']['text']])

    def test_enter_not_target_excludes_preceding_mercy_verse(self):
        from opensiddur.importer.asher_selichot.erev_rosh_hashanah import EXTRA, printed
        r={'id':'adonai_boqer_tishma_qoli','kind':'prose','fragments':[
            {'en':{'scan':'s107','printed_page':'52','text':'Morning. Thy mercy is great. Enter not into judgment with us.'},'notes':{'en':[]}}]}
        root=etree.Element('{'+TEI+'}body');printed(root,r,'en','urn:example')
        markers=root.findall('.//{'+TEI+'}milestone')
        start=next(m for m in markers if m.get('corresp')==EXTRA+'/al_tavo')
        self.assertEqual(start.tail,'Enter not into judgment with us.')
        self.assertNotIn('Thy mercy',start.tail)

    def test_hebrew_only_opening_repeat_does_not_create_english_repeat(self):
        f={'he':{'scan':'s250','printed_page':'124','text':'שמע׃ יהוה עזור׃'},
           'en':{'scan':'s251','printed_page':'124','text':'Hear us. Lord, help us!'},'notes':{'he':[],'en':[]}}
        g={'he':{'scan':'s252','printed_page':'125','text':'יונה׃ יהוה ושמע וכו׳'},
           'en':{'scan':'s253','printed_page':'125','text':'Dove. (Lord, &c.)'},'notes':{'he':[],'en':[]}}
        r={'fragments':[f,g],'stanzas':[{'fragments':[f]},{'fragments':[g]}],
           'refrain':{'he':'יהוה עזור׃','en':'Lord, help us!'},
           'refrain_cues':{'he':'יהוה(?! עזור)','en':r'\(Lord, &c\.\)'},'opening_cue':{'he':'ושמע וכו׳'}}
        original=copy.deepcopy(r)
        for lang,count in [('he',2),('en',1)]:
            root=etree.Element('{'+TEI+'}body');root.set(XML+'lang',lang)
            day.pizmon(root,r,lang,'urn:example')
            choices=root.findall('.//{'+TEI+'}choice');self.assertEqual(len(choices),count)
            if lang=='he':self.assertEqual(choices[-1].find('{'+TEI+'}expan').text,f['he']['text'])
            for c in choices:c.remove(c.find('{'+TEI+'}expan'))
            actual=streams(root)
            for source in [f,g]:self.assertEqual(actual[source[lang]['scan'],lang].strip(),source[lang]['text'])
        self.assertEqual(r,original)

    def test_each_day_has_distinct_scoped_kaddish_declarations(self):
        ids=[]
        for ordinal in day.DAYS:
            root=etree.Element('{'+TEI+'}div');day.full_kaddish(root,ordinal)
            self.assertEqual([n.get('value')for n in root.findall('.//{'+TEI+'}binary')],['false','true'])
            identity=root[0].get(XML+'id');ids.append(identity)
            self.assertEqual(root[-1].get('target'),'#'+identity)
        self.assertEqual(len(set(ids)),3)

    def test_petition_alignment_uses_day_identity(self):
        for ordinal in day.DAYS:
            root=etree.Element('{'+TEI+'}div')
            r={'id':'verses_after_example','expansion_targets':{'he':['a','b'],'en':['c']}}
            day.expanded_rubric(root,r,'en',ordinal)
            self.assertEqual([n.get('target')for n in root.findall('.//{'+day.J+'}transclude')],['c'])
            self.assertEqual(root.find('.//{'+TEI+'}milestone').get('corresp'),day.service_urn(ordinal)+'/verses_after_example/expanded')

    def test_unknown_day_is_rejected(self):
        with self.assertRaises(ValueError):day.service_urn('sixth')

    def test_duplicated_printed_invocation_is_rejected(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            units=[{'id':'opening_instruction'}, {'id':'poem','kind':'poem','fragments':[{'he':{'text':'אלהינו ואלהי אבותינו\nאלהינו ואלהי אבותינו\nשיר'}}]}, {'id':'conclusion'}]
            units[0]['kind']=units[-1]['kind']='rubric'
            for i,u in enumerate(units):(root/f'{i}.json').write_text(json.dumps(u))
            (root/'penitential-third-day.json').write_text(json.dumps({'complete':True,'readings':['0.json','1.json','2.json']}))
            with self.assertRaisesRegex(ValueError,'Duplicated invocation'):day.readings(root,'third')
