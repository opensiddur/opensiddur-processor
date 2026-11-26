"""Edition differences at the Gedaliah refrain and supplied Kaddish boundaries."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.importer.asher_selichot import tzom_gedaliah as gedaliah
from opensiddur.importer.asher_selichot.build import TEI, XML
from opensiddur.importer.scan.reverse import streams


class GedaliahTests(unittest.TestCase):
    def test_kaddish_declares_ten_days_and_restores_scope(self):
        root=etree.Element('{'+TEI+'}div');gedaliah.full_kaddish(root)
        self.assertEqual([n.get('value') for n in root.findall('.//{'+TEI+'}binary')],['false','true'])
        self.assertEqual(root[1].get('target'),gedaliah.PRAYER+'kaddish/shalem')
        self.assertEqual(root[-1].get('target'),'#'+root[0].get(XML+'id'))

    def test_foreign_body_and_footnote_preserve_text_and_direction(self):
        root=etree.Element('{'+TEI+'}p');root.text='Penitence (תשובה).'
        note=etree.SubElement(root,'{'+TEI+'}note');note.text='Called שתית.';note.tail=' Later.'
        before=''.join(root.itertext());gedaliah.wrap_hebrew(root)
        self.assertEqual(''.join(root.itertext()),before)
        foreign=root.findall('.//{'+TEI+'}foreign')
        self.assertEqual([n.text for n in foreign],['תשובה','שתית'])
        self.assertTrue(all(n.get(XML+'lang')=='he' for n in foreign))

    def test_refrain_is_before_judah_in_english_after_both_in_hebrew(self):
        f={'he':{'scan':'s200','printed_page':'99','text':'ראובן '},'en':{'scan':'s201','printed_page':'99','text':'Reuben '},'notes':{'he':[],'en':[]}}
        g={'he':{'scan':'s202','printed_page':'100','text':'יהודה׃ הורית'},'en':{'scan':'s203','printed_page':'100','text':'repented. (Teach.) Judah confessed.'},'notes':{'he':[],'en':[]}}
        reading={'fragments':[f,g],'refrain':{'he':'השיבנו׃','en':'Turn us.'},'stanzas':[{'fragments':[f,g],'cue':{'he':'הורית','en':'(Teach.)'},'cue_positions':{'en':'before_judah','he':'end'}}]}
        for lang in ['he','en']:
            root=etree.Element('{'+TEI+'}body');root.set(XML+'lang',lang)
            gedaliah.pizmon(root,reading,lang,'urn:example')
            choice=root.find('.//{'+TEI+'}choice')
            expansion=''.join(choice.find('{'+TEI+'}expan').itertext())
            self.assertEqual(expansion,reading['refrain'][lang])
            # Remove the editorial branch to inspect the actual documentary order.
            choice.remove(choice.find('{'+TEI+'}expan'))
            text=''.join(root.itertext())
            if lang=='en':self.assertLess(text.index('(Teach.)'),text.index('Judah'))
            else:self.assertGreater(text.index('הורית'),text.index('יהודה'))
            self.assertEqual(len(root.findall('.//{'+TEI+'}pb')),2)
            self.assertEqual(set(streams(root)),{('s200','he'),('s202','he')} if lang=='he' else {('s201','en'),('s203','en')})

    def test_unequal_cue_lists_stay_in_one_paired_paragraph(self):
        root=etree.Element('{'+TEI+'}div')
        gedaliah.expanded_rubric(root,{'id':'verses_after_example','expansion_targets':{'he':['extra','verses'],'en':['verses']}},'he')
        refs=root.findall('.//{http://jewishliturgy.org/ns/jlptei/2}transclude')
        self.assertEqual([n.get('target') for n in refs],['extra','verses'])
        self.assertTrue(all(n.get('type')=='inline' for n in refs))
        self.assertEqual(len(root.findall('.//{'+TEI+'}p')),1)

    def test_compiled_petitions_reject_unrelated_english(self):
        ns='http://jewishliturgy.org/ns/processing'
        root=etree.Element('root');block=etree.SubElement(root,'{'+ns+'}parallel')
        primary=etree.SubElement(block,'{'+ns+'}parallelItem',role='primary')
        etree.SubElement(primary,'{'+TEI+'}milestone',corresp=gedaliah.GEDALIAH+'/verses_after_example/expanded')
        etree.SubElement(block,'{'+ns+'}parallelItem',role='parallel').text='Omnipotent King'
        with self.assertRaisesRegex(ValueError,'unrelated English'):gedaliah.verify_compiled(root)

    def test_occasion_encloses_only_gedaliah_without_visible_instruction(self):
        from opensiddur.importer.asher_selichot.first_day import entry
        title={k:'' for k in ['edition','place','publisher','address','date']}
        title.update(scan='s1',titles=['Test'])
        root=entry('en','selichoth-asher-1912-en',{'he':title,'en':title},book=True,include_gedaliah=True)
        ns={'t':TEI,'j':'http://jewishliturgy.org/ns/jlptei/2'}
        gate=root.find('.//j:conditional[@xml:id="tzom_gedaliah_occasion"]',dict(ns,xml=XML[1:-1]))
        self.assertIsNone(gate.get('type'))
        self.assertEqual(gate.find('.//t:fs[@type="opensiddur:holiday"]/t:f',ns).get('name'),'tzom-gedalia')
        self.assertEqual(gate.find('.//t:fs[@type="opensiddur:holiday"]/t:f/t:numeric',ns).get('value'),'1')
        self.assertFalse(gate.findall('.//t:note',ns))
        refs=root.findall('.//j:transclude',ns)
        self.assertEqual(refs[-1].get('target'),gedaliah.GEDALIAH)
        children=list(gate.getparent())
        self.assertLess(children.index(gate),children.index(refs[-1]))
        end=gate.getparent().find('j:endConditional[@target="#tzom_gedaliah_occasion"]',ns)
        self.assertGreater(children.index(end),children.index(refs[-1]))

    def test_evidence_rejects_a_changed_working_reading(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source=base/'scan_reading';directory=source/'tzom-gedaliah'
            record={'id':'example'}
            for key,prefix in [('initial_sha256','initial'),('assembled_sha256','assembled-first-pass'),('working_sha256','')]:
                path=directory/prefix/'example.json';path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(b'{"text":"first"}')
                record[key]=hashlib.sha256(path.read_bytes()).hexdigest()
            (base/'tzom-gedaliah-proofreading.json').write_text(json.dumps({'readings':[record]}))
            gedaliah.verify_evidence(source,[{'id':'example'}])
            (directory/'example.json').write_bytes(b'{"text":"changed"}')
            with self.assertRaisesRegex(ValueError,'Stale Gedaliah evidence'):gedaliah.verify_evidence(source,[{'id':'example'}])

    def test_compiled_kaddish_must_have_ten_days_reading(self):
        ns='http://jewishliturgy.org/ns/processing'
        root=etree.Element('root')
        for number in range(4):
            block=etree.SubElement(root,'{'+ns+'}parallel')
            urn=gedaliah.GEDALIAH+'/verses_after_'+str(number)+'/expanded'
            for role in ['primary','parallel']:
                item=etree.SubElement(block,'{'+ns+'}parallelItem',role=role)
                etree.SubElement(item,'{'+TEI+'}milestone',corresp=urn)
                if role=='parallel':item[-1].tail='Like a father hath compassion; for we do not presume; delay not for thine own sake'
        service=etree.SubElement(root,'{'+ns+'}transclude',target=gedaliah.GEDALIAH)
        half=etree.SubElement(service,'{'+ns+'}transclude',target=gedaliah.PRAYER+'kaddish/chatzi')
        half_item=etree.SubElement(half,'{'+ns+'}parallelItem',role='primary')
        half_item.text='לעלא לעלא מן כל ברכתא'
        kaddish=etree.SubElement(service,'{'+ns+'}transclude',target=gedaliah.PRAYER+'kaddish/shalem')
        item=etree.SubElement(kaddish,'{'+ns+'}parallelItem',role='primary')
        item.text='לעלא לעלא מן כל ברכתא'
        gedaliah.verify_compiled(root)
        half_item.text='לעלא מן כל ברכתא'
        with self.assertRaisesRegex(ValueError,'Half Kaddish seasonal reading'):gedaliah.verify_compiled(root)
        half_item.text='לעלא לעלא מן כל ברכתא'
        item.text='לעלא מן כל ברכתא'
        with self.assertRaisesRegex(ValueError,'Ten Days reading'):gedaliah.verify_compiled(root)

    def test_fulfilled_secondary_instruction_has_explicit_empty_override(self):
        root=etree.Element('{'+TEI+'}TEI');gedaliah.fulfilled_instructions(root)
        note=root.find('.//{'+TEI+'}note')
        self.assertEqual(note.get('corresp'),gedaliah.FULFILLED_ADD)
        self.assertEqual(note.get('type'),'instruction')
        self.assertEqual(''.join(note.itertext()),'')
        self.assertEqual(note.get('resp'),'urn:x-opensiddur:contributor:opensiddur.org/codex')
