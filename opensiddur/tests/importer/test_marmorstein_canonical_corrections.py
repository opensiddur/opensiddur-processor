"""Shared corrections require exact literal attestations and unchanged source words."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from opensiddur.importer.marmorstein_rosh_hashanah_1 import PROJECTS
from opensiddur.importer.marmorstein_rosh_hashanah_1.build import unit_document, document, transclude_unit
from opensiddur.importer.marmorstein_rosh_hashanah_1.realizations import (
    prepare_documents, prepare_unit, review_payloads, validate_generated,
)
from opensiddur.importer.marmorstein_rosh_hashanah_1.canonical_corrections import (
    bind_corrections, apply_bound_corrections,
)
from opensiddur.importer.scan.authoring import apply_corrections

P = 'urn:x-opensiddur:text:prayer:example'
NS = {'t':'http://www.tei-c.org/ns/1.0'}


def fixture():
    fragment = dict(scan='s2',printed_page='1',text='Thou has created it.',page_start=True)
    host = dict(stem='old',urn=P,title={'en':'Example'},languages={'en':[
        dict(paragraph=1,corresp=P+'/part',fragments=[fragment])]},
        canonical_home=dict(file='home',urn=P,title={'en':'Example'},map_root=False,
                            context_urn='urn:x-opensiddur:text:siddur:example/old'))
    caller = dict(stem='new',urn='urn:x-opensiddur:text:siddur:example/new',title={'en':'Example'},
                  languages={'en':[dict(paragraph=1,canonical=P+'/part',fragments=[dict(fragment,scan='s4')])]})
    correction = dict(id='has_hast',file=PROJECTS['en']+'/home.xml',identity=P+'/part',
                      sic='has',corr='hast',before='Thou ',after=' created',
                      attestations=[dict(unit='old',scan='s2'),dict(unit='new',scan='s4')])
    return dict(units=[host,caller]), [correction]


def documents(readings):
    context,home = prepare_documents(readings['units'][0],readings)
    project = Path('/projects')/PROJECTS['en']
    return [(project/'old.xml',unit_document(context,'en',True)),
            (project/'home.xml',unit_document(home,'en',True)),
            (project/'new.xml',unit_document(prepare_unit(readings['units'][1],readings),'en',True))]


class CanonicalCorrectionTest(unittest.TestCase):
    def test_bound_correction_keeps_sic_and_changes_only_corr(self):
        readings,items=fixture();original=deepcopy(readings)
        docs=documents(readings);apply_bound_corrections(docs,readings,items)
        root=docs[1][1]
        self.assertEqual(root.xpath('//t:sic/text()',namespaces=NS),['has'])
        self.assertEqual(root.xpath('//t:corr/text()',namespaces=NS),['hast'])
        self.assertEqual(readings,original)
        validate_generated(docs,readings)
        self.assertFalse(root.xpath('//t:pb',namespaces=NS))
        self.assertEqual(docs[0][1].xpath('//t:body/t:div/@corresp',namespaces=NS),
                         ['urn:x-opensiddur:text:siddur:example/old'])

    def test_documentary_caller_selects_its_context_while_expanded_uses_the_prayer(self):
        r,_=fixture();root,body=document('en',PROJECTS['en'],'Example',P+'/spine')
        transclude_unit(body,r['units'][0],r,project=PROJECTS['en'],documentary=True)
        transclude_unit(body,r['units'][0],r)
        ns={'j':'http://jewishliturgy.org/ns/jlptei/2'}
        self.assertEqual(root.xpath('//j:transclude/@target',namespaces=ns),
                         ['urn:x-opensiddur:text:siddur:example/old@'+PROJECTS['en'],P])

    def test_missing_extra_wrong_file_or_unprinted_attestation_fails(self):
        for mutation in ['missing','extra','duplicate','context','wrong_source','wrong_scan','wrong_identity']:
            with self.subTest(mutation=mutation):
                r,c=fixture()
                if mutation=='missing':c[0]['attestations'].pop()
                elif mutation=='extra':c[0]['attestations'].append(dict(unit='other',scan='s9'))
                elif mutation=='duplicate':c[0]['attestations']*=2
                elif mutation=='context':c[0]['file']=PROJECTS['en']+'/old.xml'
                elif mutation=='wrong_source':r['units'][1]['languages']['en'][0]['fragments'][0]['text']='Thou hast created it.'
                elif mutation=='wrong_scan':c[0]['attestations'][1]['scan']='s9'
                else:c[0]['identity']=P+'/other'
                with self.assertRaises(ValueError):bind_corrections(r,c)

    def test_overlay_overlap_fails(self):
        r,c=fixture();r['wording_variants']=[dict(id='word',host='old',lang='en',identity=P+'/part',
            printed='has',readings=[dict(text='has',corresp='urn:x-opensiddur:condition:prayer:example/has'),
                                    dict(text='hath',corresp='urn:x-opensiddur:condition:prayer:example/hath')])]
        with self.assertRaisesRegex(ValueError,'overlap'):bind_corrections(r,c)

    def test_changed_or_missing_correction_invalidates_both_mapping_receipts(self):
        r,c=fixture();before={k:v for k,v,_ in review_payloads(r,c)}
        c[0]['corr']='hath';changed={k:v for k,v,_ in review_payloads(r,c)}
        missing={k:v for k,v,_ in review_payloads(r,[])}
        for key in ['realization/old/en','realization/new/en']:
            self.assertNotEqual(before[key],changed[key])
            self.assertNotEqual(before[key],missing[key])

    def test_projection_guard_catches_an_unrelated_word_change(self):
        r,c=fixture();docs=documents(r)
        def corrupt(documents,items):
            apply_corrections(documents,items)
            root=documents[items[0]['file']]
            root.xpath('//t:body',namespaces=NS)[0].text='unrelated drift'
        with patch('opensiddur.importer.marmorstein_rosh_hashanah_1.canonical_corrections.apply_corrections',corrupt):
            with self.assertRaisesRegex(ValueError,'source-printed projection'):apply_bound_corrections(docs,r,c)

    def test_missing_or_ambiguous_generated_locator_fails(self):
        r,c=fixture();docs=documents(r)
        # The raw source still attests has, but the generated home was corrupted.
        text=docs[1][1].xpath('//t:p',namespaces=NS)[-1]
        text.text='missing context'
        for child in list(text):text.remove(child)
        with self.assertRaisesRegex(ValueError,'Correction has_hast: 0 places match'):apply_bound_corrections(docs,r,c)

    def test_generated_home_context_and_publication_guards(self):
        from lxml import etree
        T=NS['t'];tag=lambda name:'{'+T+'}'+name
        for mutation in ['home_pb','context_identity','context_other_identity','missing_idno','duplicate_idno','duplicate_publication']:
            with self.subTest(mutation=mutation):
                r,_=fixture();docs=documents(r)
                if mutation=='home_pb':etree.SubElement(docs[1][1].xpath('//t:body//t:p',namespaces=NS)[0],tag('pb'),n='2')
                elif mutation=='context_identity':docs[0][1].xpath('//t:body/t:div',namespaces=NS)[0].set('corresp',P)
                elif mutation=='context_other_identity':docs[0][1].xpath('//t:body/t:div',namespaces=NS)[0].set('corresp',P+'/part')
                elif mutation in ['missing_idno','duplicate_idno']:
                    node=docs[1][1].xpath('//t:publicationStmt/t:idno',namespaces=NS)[0]
                    if mutation=='missing_idno':node.getparent().remove(node)
                    else:node.getparent().append(deepcopy(node))
                else:
                    node=docs[0][1].xpath('//t:publicationStmt/t:idno',namespaces=NS)[0]
                    docs[2][1].xpath('//t:publicationStmt/t:idno',namespaces=NS)[0].text=node.text
                with self.assertRaises(ValueError):validate_generated(docs,r)

    def test_literal_context_page_positions_are_checked_against_raw_fragments(self):
        from lxml import etree
        r,_=fixture();host=r['units'][0];old=deepcopy(host['languages']['en'][0]['fragments'][0])
        host['languages']['en'][0]['fragments']=[dict(old,text='prefix'),dict(old,scan='s3',printed_page='2')]
        host['canonical_home']['context']='literal'
        r['units'][1]['languages']['en'][0]['fragments'][0]['text']='prefix Thou has created it.'
        validate_generated(documents(r),r)
        for mutation in ['remove','inject','move']:
            with self.subTest(mutation=mutation):
                docs=documents(r);root=docs[0][1];pbs=root.xpath('//t:pb',namespaces=NS)
                if mutation=='remove':pbs[-1].getparent().remove(pbs[-1])
                elif mutation=='inject':pbs[0].getparent().append(deepcopy(pbs[0]))
                else:
                    node=pbs[-1];parent=node.getparent();previous=node.getprevious()
                    if previous is not None:previous.tail=(previous.tail or '')+(node.tail or '')
                    else:parent.text=(parent.text or '')+(node.tail or '')
                    node.tail=None;parent.remove(node);parent.append(node)
                with self.assertRaisesRegex(ValueError,'raw source page breaks'):validate_generated(docs,r)

    def test_context_overlaps_with_either_kind_of_wording_are_rejected(self):
        for optional in [False,True]:
            for side in ['before','after']:
                with self.subTest(optional=optional,side=side):
                    r,c=fixture();text='(Thou) has (created)'
                    r['units'][0]['languages']['en'][0]['fragments'][0]['text']=text
                    r['units'][1]['languages']['en'][0]['fragments'][0]['text']=text
                    c[0]['before']='(Thou) ';c[0]['after']=' (created)'
                    word='(Thou)'if side=='before'else'(created)'
                    overlay=dict(id='other',host='old',lang='en',identity=P+'/part',printed=word)
                    if optional:overlay.update(kind='optional',text=word[1:-1],condition='urn:x-opensiddur:condition:prayer:example/optional')
                    else:overlay['readings']=[dict(text=word,corresp='urn:x-opensiddur:condition:prayer:example/one'),dict(text='other',corresp='urn:x-opensiddur:condition:prayer:example/two')]
                    r['wording_variants']=[overlay]
                    with self.assertRaisesRegex(ValueError,'overlap'):bind_corrections(r,c)

    def test_literal_unbound_correction_remains_independent_and_cannot_redeclare_home(self):
        r,c=fixture();third=dict(stem='literal',urn='urn:x-opensiddur:text:siddur:example/literal',title={'en':'Literal'},
                               languages={'en':[dict(fragments=[dict(scan='s6',printed_page='3',text='Thou has created it.')])]})
        r['units'].append(third);docs=documents(r);file=Path('/projects')/PROJECTS['en']/'literal.xml'
        docs.append((file,unit_document(third,'en',True)))
        ordinary=dict(c[0],id='literal_has',file=PROJECTS['en']+'/literal.xml',scan='s6')
        ordinary.pop('identity');ordinary.pop('attestations');c.append(ordinary)
        self.assertEqual(len(bind_corrections(r,c)),1)
        apply_bound_corrections(docs,r,c);validate_generated(docs,r)
        self.assertEqual(docs[-1][1].xpath('//t:corr/text()',namespaces=NS),['hast'])
        from lxml import etree
        etree.SubElement(docs[-1][1].xpath('//t:p',namespaces=NS)[-1],'{'+NS['t']+'}milestone',unit='prayer-part',corresp=P+'/part')
        with self.assertRaisesRegex(ValueError,'one generated home'):validate_generated(docs,r)

    def test_payload_source_literal_and_corrected_hashes_bind_the_actual_wordings(self):
        import hashlib,json
        r,c=fixture();payloads={key:json.loads(value)for key,value,_ in review_payloads(r,c)}
        for key in ['realization/old/en','realization/new/en']:
            fidelity=payloads[key]['source_fidelity'][0]
            self.assertEqual(fidelity['resolved_sha256'],fidelity['literal_sha256'])
            self.assertEqual(fidelity['resolved_sha256'],hashlib.sha256(b'Thou has created it.').hexdigest())
            self.assertEqual(fidelity['corrected_sha256'],hashlib.sha256(b'Thou hast created it.').hexdigest())

    def test_ambiguous_generated_locator_is_rejected_before_projection(self):
        from lxml import etree
        r,c=fixture();docs=documents(r)
        etree.SubElement(docs[1][1].xpath('//t:body/t:div',namespaces=NS)[0],'{'+NS['t']+'}p').text='Thou has created it.'
        with self.assertRaisesRegex(ValueError,'Correction has_hast: 2 places match'):
            apply_bound_corrections(docs,r,c)

    def test_corrected_spine_references_name_an_attester_and_bind_both_orders(self):
        import json
        r,c=fixture();before={k:v for k,v,_ in review_payloads(r,c)}
        r['expanded_order']=[{'reference':{'target':P+'/part'}}]
        with self.assertRaisesRegex(ValueError,'source witness'):bind_corrections(r,c)
        r['expanded_order'][0]['source_witness']='new'
        self.assertEqual(len(bind_corrections(r,c)),1)
        after={k:v for k,v,_ in review_payloads(r,c)}
        self.assertNotEqual(before['realization/old/en'],after['realization/old/en'])
        r['source_order']=[{'unit':'new'}]
        later={k:v for k,v,_ in review_payloads(r,c)}
        self.assertNotEqual(after['realization/old/en'],later['realization/old/en'])
        for key in ['repeat','transclude']:
            altered=deepcopy(r);altered['units'][1]['languages']['en'][0][key]=P+'/part'
            with self.assertRaisesRegex(ValueError,'attested canonical'):bind_corrections(altered,c)

    def test_compact_range_cannot_bypass_source_witness_binding(self):
        r,c=fixture();host=r['units'][0]
        host['languages']['en'].insert(0,dict(corresp=P+'/before',paragraph=1,
            fragments=[dict(scan='s2',printed_page='1',text='Introduction.',page_start=False)]))
        r['expanded_order']=[{'reference':{'target':P+'/before-/part'}}]
        with self.assertRaisesRegex(ValueError,'source witness'):bind_corrections(r,c)
        r['expanded_order'][0]['source_witness']='old'
        self.assertEqual(len(bind_corrections(r,c)),1)
