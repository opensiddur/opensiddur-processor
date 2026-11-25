"""A source typo in one printing must not alter the default shared wording."""
from copy import deepcopy
import json
import unittest
from opensiddur.tests.importer import test_marmorstein_canonical_printings as cases
from opensiddur.importer.marmorstein_rosh_hashanah_1 import PROJECTS
from opensiddur.importer.marmorstein_rosh_hashanah_1 import realizations as r
from opensiddur.importer.marmorstein_rosh_hashanah_1.canonical_corrections import bind_corrections, apply_bound_corrections


def fixture():
    data=cases.fixture()
    correction=dict(id='appendix_typo',file=PROJECTS['en']+'/words.xml',identity=cases.P,
        wording=cases.B,xpath='//j:option[@corresp="'+cases.B+'"]',sic='DELTA',corr='epsilon',
        before='gamma ',attestations=[dict(unit='caller',scan='s347')])
    return data,[correction]


class PrintingCorrectionTest(unittest.TestCase):
    def test_only_selected_printing_gets_sic_corr_and_raw_readings_stay_exact(self):
        data,items=fixture();original=deepcopy(data)
        documents=cases.CanonicalPrintingsTest().generated(data)
        apply_bound_corrections(documents,data,items)
        root=next(root for path,root in documents if path.stem=='words')
        self.assertEqual(root.xpath('//t:sic/text()',namespaces=cases.NS),['DELTA'])
        self.assertEqual(root.xpath('//t:corr/text()',namespaces=cases.NS),['epsilon'])
        self.assertFalse(root.xpath('//j:option[@corresp=$urn]//t:choice',urn=cases.A,namespaces=cases.NS))
        self.assertEqual(data,original)
        r.validate_generated(documents,data)

    def test_bad_locator_identity_printing_guard_or_attestation_fails_closed(self):
        for mutation in ['xpath','identity','default','sic','guard','missing','duplicate','old_host','wrong_scan','unowned']:
            with self.subTest(mutation=mutation):
                data,items=fixture();item=items[0]
                if mutation=='xpath':item['xpath']='//t:body'
                elif mutation=='identity':item['identity']+='other'
                elif mutation=='default':item['wording']=cases.A;item['xpath']='//j:option[@corresp="'+cases.A+'"]'
                elif mutation=='sic':item['sic']='absent'
                elif mutation=='guard':data['canonical_printings']=[]
                elif mutation=='missing':item['attestations']=[]
                elif mutation=='duplicate':item['attestations']*=2
                elif mutation=='old_host':item['attestations'].append(dict(unit='host',scan='s2'))
                elif mutation=='wrong_scan':item['attestations'][0]['scan']='s99'
                else:
                    extra=deepcopy(data['units'][1]);extra['stem']='extra';data['units'].append(extra)
                with self.assertRaises(ValueError):bind_corrections(data,items)

    def test_source_hashes_remain_printed_and_corrected_hash_changes_only_in_new_printing(self):
        data,items=fixture();payloads={key:json.loads(value)for key,value,_ in r.review_payloads(data,items)}
        earlier=payloads['realization/host/en']['source_fidelity'][0]
        appendix=payloads['realization/caller/en']['source_fidelity'][0]
        self.assertEqual(earlier['resolved_sha256'],earlier['corrected_sha256'])
        self.assertEqual(appendix['resolved_sha256'],appendix['literal_sha256'])
        self.assertNotEqual(appendix['resolved_sha256'],appendix['corrected_sha256'])

    def test_spine_requires_known_source_and_allows_unaffected_default_witness(self):
        data,items=fixture();data['expanded_order']=[dict(reference=dict(target=cases.P),source_witness='host')]
        self.assertEqual(len(bind_corrections(data,items)),1)
        data['expanded_order'][0].pop('source_witness')
        with self.assertRaisesRegex(ValueError,'source witness'):bind_corrections(data,items)

    def test_other_printing_cannot_contain_same_correction_context(self):
        data,items=fixture();data['wording_variants'][0]['readings'][0]['text']='alpha beta gamma DELTA'
        with self.assertRaisesRegex(ValueError,'unique'):bind_corrections(data,items)

    def test_mixed_file_requires_explicit_part_and_exact_attestation(self):
        data,_=fixture();identity=cases.P+'/literal';unit=dict(stem='mixed',urn='urn:x-opensiddur:text:siddur:example/mixed',title={'en':'Mixed'},languages={'en':[
            dict(paragraph=1,canonical=cases.P,fragments=[dict(scan='s8',printed_page='3',text='alpha beta gamma delta')]),
            dict(paragraph=2,corresp=identity,fragments=[dict(scan='s8',printed_page='3',text='remaining bad word')]) ]})
        data['units'].append(unit);item=dict(id='literal',file=PROJECTS['en']+'/mixed.xml',sic='bad',corr='good',before='remaining ',after=' word')
        with self.assertRaisesRegex(ValueError,'explicit shared home'):bind_corrections(data,[item])
        item.update(literal_provider=True,identity=identity,attestations=[dict(unit='mixed',scan='s8')])
        self.assertEqual(len(bind_corrections(data,[item])),1)
        documents=cases.CanonicalPrintingsTest().generated(data);apply_bound_corrections(documents,data,[item])
        root=next(root for path,root in documents if path.stem=='mixed')
        self.assertEqual(root.xpath('//t:sic/text()',namespaces=cases.NS),['bad'])
        # A subsequent shared caller must now be named and attest the actual source.
        caller=dict(stem='literal_caller',urn=unit['urn']+'/caller',title={'en':'Caller'},languages={'en':[dict(paragraph=1,canonical=identity,fragments=[dict(scan='s9',printed_page='4',text='remaining bad word')])]})
        data['units'].append(caller)
        with self.assertRaisesRegex(ValueError,'attestations'):bind_corrections(data,[item])
        item['attestations'].append(dict(unit='literal_caller',scan='s9'))
        self.assertEqual(len(bind_corrections(data,[item])),1)
        item['identity']=cases.P
        with self.assertRaisesRegex(ValueError,'literal part'):bind_corrections(data,[item])

    def test_whole_text_host_and_shared_literal_target_do_not_bypass_old_guard(self):
        data,_=fixture();host=dict(stem='mixed',urn='urn:x-opensiddur:text:siddur:example/mixed',text_corresp=cases.P+'/whole',title={'en':'Mixed'},languages={'en':[dict(paragraph=1,corresp=cases.P+'/literal',fragments=[dict(scan='s8',printed_page='3',text='remaining bad word')])]})
        data['units'].append(host);item=dict(id='literal',file=PROJECTS['en']+'/mixed.xml',sic='bad',corr='good',before='remaining ',after=' word')
        data['units'].append(dict(stem='whole_caller',urn=host['urn']+'/caller',canonical_whole=host['text_corresp'],title={'en':'Caller'},languages={'en':host['languages']['en']}))
        with self.assertRaisesRegex(ValueError,'explicit shared home'):bind_corrections(data,[item])
        host.pop('text_corresp');host['languages']['en'].insert(0,deepcopy(data['units'][1]['languages']['en'][0]))
        with self.assertRaisesRegex(ValueError,'explicit shared home'):bind_corrections(data,[item])

    def test_multiple_overlays_or_host_fragments_cannot_borrow_an_unrelated_page_guard(self):
        for mutation in ['overlay','fragments']:
            with self.subTest(mutation=mutation):
                data,items=fixture()
                if mutation=='overlay':
                    extra=deepcopy(data['wording_variants'][0]);extra['id']='another';data['wording_variants'].append(extra)
                else:
                    part=data['units'][0]['languages']['en'][0];part['fragments'].append(deepcopy(part['fragments'][0]))
                with self.assertRaisesRegex(ValueError,'whole-fragment|one non-default'):bind_corrections(data,items)

    def test_following_context_is_preserved_in_bound_correction_projection(self):
        data,_=fixture();identity=cases.P+'/literal';host=dict(stem='mixed',urn='urn:x-opensiddur:text:siddur:example/mixed',title={'en':'Mixed'},languages={'en':[dict(paragraph=1,corresp=identity,fragments=[dict(scan='s8',printed_page='3',text='this day.')])]})
        data['units'].append(host);item=dict(id='quote',file=PROJECTS['en']+'/mixed.xml',literal_provider=True,identity=identity,sic='.',corr='!.',follows='this day',attestations=[dict(unit='mixed',scan='s8')])
        from opensiddur.importer.marmorstein_rosh_hashanah_1.canonical_corrections import corrected_text
        bindings=bind_corrections(data,[item]);self.assertEqual(corrected_text('this day.',bindings),'this day!.')

    def test_explicit_provider_whole_text_alias_still_requires_witness_and_rejects_raw_transclusion(self):
        data,_=fixture();identity=cases.P+'/literal';alias=cases.P+'/whole'
        host=dict(stem='mixed',urn='urn:x-opensiddur:text:siddur:example/mixed',text_corresp=alias,title={'en':'Mixed'},languages={'en':[dict(paragraph=1,corresp=identity,fragments=[dict(scan='s8',printed_page='3',text='remaining bad word')])]})
        data['units'].append(host);item=dict(id='literal',file=PROJECTS['en']+'/mixed.xml',literal_provider=True,identity=identity,sic='bad',corr='good',before='remaining ',after=' word',attestations=[dict(unit='mixed',scan='s8')])
        data['expanded_order']=[dict(reference=dict(target=alias))]
        with self.assertRaisesRegex(ValueError,'source witness'):bind_corrections(data,[item])
        data['expanded_order'][0]['source_witness']='mixed';self.assertEqual(len(bind_corrections(data,[item])),1)
        data['units'].append(dict(stem='raw',urn=host['urn']+'/raw',title={'en':'Raw'},languages={'en':[dict(transclude=alias)]}))
        with self.assertRaisesRegex(ValueError,'attested canonical pointers'):bind_corrections(data,[item])

    def test_every_correction_in_a_literal_provider_file_requires_its_own_explicit_flag(self):
        data,_=fixture();identity=cases.P+'/literal';host=dict(stem='mixed',urn='urn:x-opensiddur:text:siddur:example/mixed',title={'en':'Mixed'},languages={'en':[dict(paragraph=1,corresp=identity,fragments=[dict(scan='s8',printed_page='3',text='remaining bad word')])]})
        data['units'].append(host);item=dict(id='literal',file=PROJECTS['en']+'/mixed.xml',literal_provider=True,identity=identity,sic='bad',corr='good',before='remaining ',after=' word',attestations=[dict(unit='mixed',scan='s8')]);unflagged=deepcopy(item);unflagged.pop('literal_provider');unflagged['id']='unflagged'
        for items in [[item,unflagged],[unflagged,item]]:
            with self.assertRaisesRegex(ValueError,'explicit source file'):bind_corrections(data,items)
