"""Calendar scope, reusable content and reference boundaries for life events."""
import unittest
import re
import unicodedata
from lxml import etree
from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build import lifecycle as r
from opensiddur.importer.birnbaum_scan.build.common import PROJECT_EN
from .test_tachanun_conditions import evaluate, fragment, settings, NS


class TestLifecycle(unittest.TestCase):
    def test_burial_does_not_cancel_its_own_tzidduq_hadin(self):
        values=settings(**{'house-of-mourning':True,'brit-milah':True,'omit-tahanun':True})
        self.assertEqual(evaluate(r.TZIDDUK_OCCASION,values),TriState.TRUE)
        self.assertEqual(evaluate(r.TZIDDUK_OCCASION,settings(month=1)),TriState.FALSE)
        self.assertEqual(evaluate(r.TZIDDUK_OCCASION,settings(weekday=7)),TriState.FALSE)
        self.assertEqual(evaluate(r.TZIDDUK_OCCASION,{}),TriState.UNDEFINED)
        for israel,day,want in ((True,24,TriState.TRUE),(False,24,TriState.FALSE),(False,25,TriState.TRUE)):
            self.assertEqual(evaluate(r.TZIDDUK_OCCASION,settings(month=7,day=day,israel=israel)),want)

    def test_calendar_selects_tzidduq_and_its_kaddish_with_regular_fallback(self):
        units={u['urn']:fragment(u['body']) for u in r.units(r.PROJECT_HE)}
        self.assertFalse(units[r.TZIDDUK].xpath('.//j:conditional',namespaces=NS))
        burial=units[r.BURIAL]
        condition=burial.xpath('.//j:conditional[contains(@xml:id,"tzidduq_calendar")]',namespaces=NS)[0]
        siblings=list(condition.getparent());start=siblings.index(condition)
        end=next(i for i in range(start+1,len(siblings)) if siblings[i].tag=='{'+NS['j']+'}endConditional')
        gated=[x.get('target') for x in siblings[start:end] if x.tag=='{'+NS['j']+'}transclude']
        self.assertEqual(gated,[r.TZIDDUK])
        self.assertIn(r.KADDISH,[x.get('target') for x in siblings[end+1:]])
        for key,values,expected in [('expanded',settings(),TriState.TRUE),('expanded',settings(month=1),TriState.FALSE),('regular',settings(),TriState.FALSE),('regular',settings(month=1),TriState.TRUE),('regular',{},TriState.UNDEFINED)]:
            node=burial.xpath('.//j:conditional[contains(@xml:id,"burial_'+key+'")]',namespaces=NS)[0]
            expr=''.join(etree.tostring(c,encoding='unicode') for c in node if c.tag!='{'+NS['tei']+'}note')
            if values: values['opensiddur:quorum','minyan']=True
            self.assertEqual(evaluate(expr,values),expected)
            values['opensiddur:quorum','minyan']=False
            self.assertEqual(evaluate(expr,values),TriState.FALSE)
        self.assertIn(r.PRAYER+'kaddish/yatom',burial.xpath('.//j:transclude/@target',namespaces=NS))


    def test_shared_prayers_and_chapel_psalm_are_unconditional(self):
        for project in (r.PROJECT_HE,PROJECT_EN):
            units={u['urn']:fragment(u['body']) for u in r.units(project)}
            for urn in (r.SICK,r.CHAPEL):
                self.assertFalse(units[urn].xpath('.//j:conditional',namespaces=NS))
            self.assertEqual(units[r.CHAPEL].xpath('.//j:transclude/@target',namespaces=NS)[-1],r.BIBLE+'psalms/23')
        for key in ('sick_refaenu','milah_wine','pidyon_shehecheyanu'):
            self.assertIn(key,r.REUSED)
            self.assertNotIn(r.URNS[key],[p['urn'] for p in r.prayers('he')])

    def test_psalm_boundaries_and_page_turn_are_inside_the_paragraph(self):
        for lang in ('he','en'):
            prayers={p['urn']:fragment(p['body']) for p in r.prayers(lang)}
            psalm=prayers[r.URNS['haderekh_psalm91']]
            self.assertEqual(len(psalm.xpath('.//tei:milestone[@corresp]',namespaces=NS)),16)
            self.assertEqual(len(psalm.xpath('.//tei:p',namespaces=NS)),1)
            self.assertEqual(psalm.xpath('.//tei:p/tei:seg/tei:pb/@n',namespaces=NS),[str(733+int(lang=='en'))])
            psalm23=prayers[r.BIBLE+'psalms/23']
            self.assertEqual(psalm23.xpath('.//tei:milestone[@corresp]/@corresp',namespaces=NS),[r.BIBLE+'psalms/23/'+str(i) for i in range(1,7)])
            for p in prayers.values():
                self.assertFalse(p.xpath('.//tei:seg[@corresp]',namespaces=NS))

    def test_printed_burial_kaddish_has_one_leella(self):
        row=next(x for x in r.ROWS if x['key']=='burial_kaddish_praise')
        self.assertEqual(row['he'].count('לְעֵֽלָּא'),1)
        self.assertNotIn('(',row['he'])

    def test_embedded_quotations_exclude_the_next_instruction(self):
        for lang in ('he','en'):
            row=next(x for x in r.ROWS if x['key']=='pidyon_closing')
            node=fragment('<tei:p>'+r.quoted_text(row['key'],row[lang],lang)+'</tei:p>')
            self.assertEqual(len(node.xpath('.//tei:seg[@source]',namespaces=NS)),3)
            self.assertNotIn('Amen' if lang=='en' else 'אָמֵן',''.join(node.xpath('.//tei:seg',namespaces=NS)[-1].itertext()))

    def test_both_languages_preserve_every_reading_and_reused_text(self):
        from opensiddur.importer.birnbaum_scan.build.build_he import PRAYERS as HE
        from opensiddur.importer.birnbaum_scan.build.build_en import PRAYERS as EN
        def norm(text):
            return re.sub(r'\s+','',unicodedata.normalize('NFC',re.sub(r'\{pb:\d+\}','',text)))
        for lang,prayers in [('he',HE),('en',EN)]:
            bodies={p['urn']:p['body'] for p in prayers}
            for row in r.ROWS:
                with self.subTest(lang=lang,key=row['key']):
                    actual=''.join(fragment(bodies[r.URNS[row['key']]]).itertext())
                    self.assertEqual(norm(actual),norm(row[lang]))

    def test_parenthetical_hebrew_catchword_is_one_rtl_run(self):
        from opensiddur.importer.birnbaum_scan.build.notes_lifecycle import xml
        node=fragment('<tei:p>'+xml('קדיש ל(את)חדתא refers to the restoration.')+'</tei:p>')
        runs=node.xpath('.//tei:foreign[@xml:lang="he"]',namespaces=NS)
        self.assertEqual([x.text for x in runs],['קדיש ל(את)חדתא'])
