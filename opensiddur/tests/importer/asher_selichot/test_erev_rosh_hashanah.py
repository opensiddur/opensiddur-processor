"""Erev-specific differences must survive the shared service assembly."""
import unittest
import unittest.mock
from lxml import etree
from opensiddur.importer.asher_selichot import erev_rosh_hashanah as erev
from opensiddur.importer.asher_selichot.first_day import poetic_lines
from opensiddur.importer.asher_selichot.build import TEI,XML


class ErevAssemblyTests(unittest.TestCase):
    def test_unequal_petition_lists_share_one_prose_alignment_unit(self):
        for lang,targets in [('he',['extra','verses','daniel']),('en',['verses','daniel'])]:
            root=etree.Element('{'+TEI+'}div')
            erev.expanded_rubric(root,{'id':'verses_after_poem','expansion_targets':{lang:targets}},lang)
            root=root[0]
            self.assertEqual(root[0].get('corresp'),erev.EREV+'/verses_after_poem/expanded')
            self.assertEqual([n.get('target') for n in root[1]],targets)
            self.assertTrue(all(n.get('type')=='inline' for n in root[1]))
            self.assertEqual(root[-1].get('unit'),'prayer')
            self.assertIsNone(root[-1].get('corresp'))

    def test_a_renamed_text_is_transcluded_by_its_new_urn(self):
        with unittest.mock.patch.object(erev, 'RENAMED_URNS', {'urn:old': 'urn:new'}):
            for targets in (['urn:old', 'urn:kept'], {'he': ['urn:old', 'urn:kept']}):
                self.assertEqual(erev.targets({'expansion_targets': targets}, 'he'), ['urn:new', 'urn:kept'])

    def test_compiled_pairing_rejects_unrelated_english(self):
        ns='http://jewishliturgy.org/ns/processing'
        root=etree.Element('root');block=etree.SubElement(root,'{'+ns+'}parallel')
        primary=etree.SubElement(block,'{'+ns+'}parallelItem',role='primary')
        etree.SubElement(primary,'{'+TEI+'}milestone',corresp=erev.EREV+'/verses_after_poem/expanded')
        etree.SubElement(block,'{'+ns+'}parallelItem',role='parallel').text='Omnipotent King'
        with self.assertRaisesRegex(ValueError,'unrelated English'):erev.verify_compiled(root)

    def test_reprinted_daniel_range_keeps_its_own_wording(self):
        root=etree.Element('{'+TEI+'}body')
        text='O my God! hear; for we do not presume. Be attentive and grant: for thy own sake.'
        urn=erev.PRAYER+'selichot/ki_lo_al_tsidqotenu'
        reading={'id':'hateh_elohai','kind':'prose','range_urn':urn,
          'fragments':[{'en':{'scan':'s107','printed_page':'52','text':text},'notes':{'en':[]}}]}
        erev.printed(root,reading,'en','urn:example')
        markers=root.findall('.//{'+TEI+'}milestone')
        self.assertEqual([m.get('corresp') for m in markers],[urn,None])
        self.assertEqual(markers[0].tail,'for we do not presume. Be attentive and grant: for thy own sake.')
        self.assertEqual(''.join(root.itertext()).strip(),text)

    def test_language_specific_range_and_ark_order(self):
        reading={'id':'cue','expansion_targets':{'he':['one','two'],'en':['two']},
                 'retained_instruction':{'he':'Close the Ark.','en':'Close the Ark.'},
                 'instruction_position':{'he':'before','en':'after'}}
        for lang,order in [('he',['note','transclude','transclude']),('en',['transclude','note'])]:
            root=etree.Element('{'+TEI+'}div');erev.expanded_rubric(root,reading,lang)
            self.assertEqual([etree.QName(n).localname for n in root],order)
            self.assertEqual([n.get('target') for n in root if etree.QName(n).localname=='transclude'],reading['expansion_targets'][lang])

    def test_ark_between_attributes(self):
        root=etree.Element('{'+TEI+'}div')
        erev.expanded_rubric(root,{'id':'cue','expansion_targets':['king','attributes'],
            'retained_instruction':{'he':'Open the Ark.'},'instruction_between_targets':True},'he')
        self.assertEqual([etree.QName(n).localname for n in root],['transclude','note','transclude'])

    def test_kaddish_excludes_conflicting_calendar(self):
        root=etree.Element('{'+TEI+'}div');erev.kaddish(root)
        self.assertEqual([n.get('value') for n in root.findall('.//{'+TEI+'}binary')],['false','false'])
        self.assertEqual(root[-1].get('target'),'#'+root[0].get(XML+'id'))
        self.assertEqual(root[1].get('target'),erev.PRAYER+'kaddish/shalem')

    def test_verse_response_closing_bracket_is_attached(self):
        root=etree.Element('{'+TEI+'}lg')
        poetic_lines(root,[{'he':{'text':'אחד׃ [שנים׃] שלשה׃','scan':'s138','printed_page':'68'},'notes':{'he':[]}}],{'line_stops':'׃'})
        self.assertEqual([''.join(n.itertext()) for n in root],['אחד׃','[שנים׃]','שלשה׃'])

    def test_no_invocation_is_invented(self):
        root=etree.Element('{'+TEI+'}body');reading={'id':'poem','kind':'poem','invocation':False,
          'fragments':[{'he':{'scan':'s100','printed_page':'49','text':'אדון עולם׃'},'notes':{'he':[]}}]}
        erev.printed(root,reading,'he','urn:example')
        self.assertEqual(len(root.findall('.//{'+TEI+'}l')),1)
        self.assertEqual(root.findall('.//{'+TEI+'}head'),[])

    def test_english_foreign_body_keeps_hebrew_direction(self):
        root=etree.Element('{'+TEI+'}p');erev.body_words(root,'secret slander (לשון הרע).',[],'en')
        self.assertEqual(root[0].get(XML+'lang'),'he')
        self.assertEqual(''.join(root.itertext()),'secret slander (לשון הרע).')

    def test_pointed_litany_response_is_semantic_refrain(self):
        root=etree.Element('{'+TEI+'}body')
        reading={'id':'mi_sheanah','kind':'litany','fragments':[{'he':{'scan':'s174','printed_page':'86','text':'מִי שֶׁעָנָה הוּא יַעֲנֵנוּ׃'},'notes':{'he':[]}}]}
        erev.printed(root,reading,'he','urn:example')
        response=root.find('.//{'+TEI+'}seg[@type="refrain"]')
        self.assertIsNotNone(response)
        self.assertEqual(response.text,'הוּא יַעֲנֵנוּ׃')

    def test_alternating_refrains_and_complete_opening_repeat(self):
        root=etree.Element('{'+TEI+'}body')
        reading={'id':'pizmon','kind':'pizmon','fragments':[{'he':{'scan':'s148','printed_page':'73','text':'פתיחה׃'},'notes':{'he':[]}}],
          'refrains':[{'he':'תגובה א׃'},{'he':'תגובה ב׃'}],
          'stanzas':[{'he':'פתיחה תגובה א׃'},{'he':'בית ושוב','cue':{'he':'ושוב'}},
                     {'he':'בית והשב','cue':{'he':'והשב'}},{'he':'זכור וכו׳','opening_cue':True}]}
        erev.printed(root,reading,'he','urn:example')
        expansions=root.findall('.//{'+TEI+'}expan')
        self.assertEqual([n.text for n in expansions],['תגובה ב׃','תגובה א׃','פתיחה תגובה א׃'])
        self.assertEqual([n.text for n in root.findall('.//{'+TEI+'}abbr')],['ושוב','והשב','זכור וכו׳'])

    def test_reading_edit_invalidates_earlier_proofreading(self):
        import hashlib,json,tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'scan_reading';work=source/'erev-rosh-hashanah';(work/'initial').mkdir(parents=True)
            for path in [work/'poem.json',work/'initial/poem.json']:path.write_text('old scan reading')
            digest=hashlib.sha256(b'old scan reading').hexdigest()
            evidence=source.parent/'erev-rosh-hashanah-proofreading.json'
            evidence.write_text(json.dumps({'readings':[{'id':'poem','initial_sha256':digest,'working_sha256':digest}]}))
            erev.verify_evidence(source,[{'id':'poem'}])
            (work/'poem.json').write_text('new scan reading')
            with self.assertRaisesRegex(ValueError,'Stale Erev proofreading'):erev.verify_evidence(source,[{'id':'poem'}])

    def test_omitted_unit_invalidates_proofreading_scope(self):
        import json,tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'scan_reading';source.mkdir()
            (source.parent/'erev-rosh-hashanah-proofreading.json').write_text(json.dumps({'readings':[]}))
            with self.assertRaisesRegex(ValueError,'scope is stale'):erev.verify_evidence(source,[{'id':'missing'}])
