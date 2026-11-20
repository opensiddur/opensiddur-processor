"""Source evidence stays immutable while canonical mappings get their own review."""
from copy import deepcopy
import unittest

from opensiddur.importer.marmorstein_rosh_hashanah_1.build import (
    unit_document, unit_review_text, transclude_unit, document, require_review,
)
from opensiddur.importer.marmorstein_rosh_hashanah_1.realizations import (
    prepare_unit, prepare_documents, validate_occurrences, review_payloads, selection,
)

P = 'urn:x-opensiddur:text:prayer:example'
A = 'urn:x-opensiddur:condition:prayer:example/for_ever'
B = 'urn:x-opensiddur:condition:prayer:example/forever'
NS = {'tei':'http://www.tei-c.org/ns/1.0','j':'http://jewishliturgy.org/ns/jlptei/2'}


def fixture():
    host = dict(stem='host', urn=P, title={'en':'Example'}, languages={'en':[
        dict(corresp=P+'/part', paragraph=1, fragments=[dict(scan='s2', printed_page='1', text='for ever', page_start=True)])]})
    occurrence = dict(stem='occurrence', urn='urn:x-opensiddur:text:siddur:example', title={'en':'Example'},
        wording_selection=[dict(type='opensiddur:variant',features={A:False,B:True})],
        languages={'en':[dict(paragraph=1, canonical=P+'/part', fragments=[dict(scan='s4',printed_page='2',text='forever',page_start=True)])]})
    overlay = dict(id='example',host='host',lang='en',identity=P+'/part',printed='for ever',
                   readings=[dict(text='for ever',corresp=A),dict(text='forever',corresp=B)])
    return dict(units=[host,occurrence],wording_variants=[overlay])


class RealizationTest(unittest.TestCase):
    def test_partial_translation_note_stays_in_source_header_and_requires_review(self):
        u=fixture()['units'][0]
        before=unit_review_text(u,'en')
        u['source_notes']={'en':[dict(text='Only the final stanza is translated in the source.')]}
        root=unit_document(u,'en',True)
        self.assertEqual(root.xpath('//tei:sourceDesc/tei:bibl/tei:note[@type="encoding"]/text()',namespaces=NS),
                         ['Only the final stanza is translated in the source.'])
        self.assertNotIn('Only the final stanza',''.join(root.xpath('//tei:body',namespaces=NS)[0].itertext()))
        self.assertNotEqual(before,unit_review_text(u,'en'))

    def test_context_wrapper_does_not_break_standoff_annotation_placement(self):
        u=fixture()['units'][0]
        u['publication_context']='urn:x-opensiddur:text:siddur:example/context'
        u['citations']={'en':[dict(scan='s2',text='Source apparatus.',note_type='annotation')]}
        root=unit_document(u,'en',True)
        self.assertEqual([e.tag.rsplit('}',1)[-1] for e in root],['teiHeader','standOff','text'])
        self.assertEqual(root.xpath('//tei:standOff/tei:note/@target',namespaces=NS),[P])
        self.assertEqual(root.xpath('//tei:body/tei:div/@corresp',namespaces=NS),[u['publication_context']])

    def test_overlay_does_not_edit_literal_evidence_or_its_review(self):
        r=fixture();before=deepcopy(r);payload=unit_review_text(r['units'][0],'en')
        effective=prepare_unit(r['units'][0],r)
        self.assertEqual(r,before)
        self.assertEqual(unit_review_text(r['units'][0],'en'),payload)
        root=unit_document(effective,'en',True)
        self.assertEqual(root.xpath('//j:option/@corresp',namespaces=NS),[A,B])
        self.assertFalse(root.xpath('//j:declare',namespaces=NS))

    def test_canonical_occurrence_preserves_own_paragraph_and_page(self):
        r=fixture();validate_occurrences(r)
        root=unit_document(prepare_unit(r['units'][1],r),'en',True)
        p=root.xpath('//tei:body/tei:div/tei:p',namespaces=NS)
        self.assertEqual(len(p),1)
        self.assertEqual([v.tag.rsplit('}',1)[-1]for v in p[0]],['pb','transclude'])
        self.assertEqual(p[0][0].get('n'),'2')
        self.assertEqual(p[0][0].get('ed'),'1965 example')
        self.assertEqual(root.xpath('count(//j:declare)',namespaces=NS),1)
        self.assertEqual(root.xpath('count(//j:endDeclare)',namespaces=NS),1)
        self.assertNotIn('forever',''.join(p[0].itertext()))

    def test_source_drift_missing_selection_and_multiple_hosts_fail(self):
        for mutation in ['source','selection','ambiguous','fragment']:
            with self.subTest(mutation=mutation):
                r=fixture()
                if mutation=='source':r['units'][1]['languages']['en'][0]['fragments'][0]['text']='different'
                elif mutation=='selection':r['units'][1]['wording_selection']=[]
                elif mutation=='ambiguous':r['units'].append(deepcopy(r['units'][0]))
                else:r['units'][1]['languages']['en'][0]['fragments']*=2
                with self.assertRaises(ValueError):validate_occurrences(r)

    def test_mapping_and_note_conditions_have_separate_review_payloads(self):
        r=fixture();before=unit_review_text(r['units'][1],'en');payloads=dict((k,v)for k,v,_ in review_payloads(r))
        r['units'][1]['languages']['en'][0]['canonical']=P+'/other'
        self.assertEqual(unit_review_text(r['units'][1],'en'),before)
        with self.assertRaisesRegex(ValueError,'one host'):
            list(review_payloads(r))
        r=fixture();before=dict((k,v)for k,v,_ in review_payloads(r))
        r['units'][0]['citations']={'en':[dict(text='comment',scan='s2',conditions=[dict(type='opensiddur:variant',features={A:True})])]}
        self.assertNotEqual(before['realization/host/en'],dict((k,v)for k,v,_ in review_payloads(r))['realization/host/en'])

    def test_host_default_is_local_to_each_transcluder(self):
        r=fixture();root,body=document('en','example','Example',P)
        transclude_unit(body,r['units'][0],r)
        transclude_unit(body,r['units'][0],r)
        self.assertEqual(selection(r,'host')[0]['features'],{A:True,B:False})
        ids=root.xpath('//j:declare/@xml:id',namespaces=NS)
        self.assertEqual(len(ids),2);self.assertEqual(len(set(ids)),2)
        self.assertEqual(root.xpath('//j:endDeclare/@target',namespaces=NS),['#'+i for i in ids])

    def test_canonical_home_leaves_only_transclusions_in_its_context(self):
        r=fixture();u=r['units'][0]
        u['urn']='urn:x-opensiddur:text:siddur:example'
        u['canonical_home']=dict(file='example_parts',urn=P+'/part',map_root=False,title={'en':'Example'})
        context,home=prepare_documents(u,r)
        self.assertEqual(home['urn'],P+'/part')
        self.assertFalse(home['map_root'])
        root=unit_document(context,'en',True)
        body=root.xpath('//tei:body',namespaces=NS)[0]
        self.assertNotIn('for ever',''.join(body.itertext()))
        self.assertTrue(body.xpath('.//j:transclude',namespaces=NS))
        validate_occurrences(r)

    def test_overlay_cannot_claim_a_different_first_printed_reading(self):
        r=fixture();r['wording_variants'][0]['readings'][0]['text']='not the source'
        with self.assertRaisesRegex(ValueError,'printed reading first'):prepare_unit(r['units'][0],r)

    def test_complete_formula_keeps_invocation_outside_verse(self):
        r=fixture();u=r['units'][0];u['urn']=P;u['text_corresp']=P+'/text';s=u['languages']['en'][0]
        s['corresp']='urn:x-opensiddur:text:bible:psalms/22/4';s['source']=s['corresp'];s['end_reference']=True
        u['languages']['en'].append(dict(paragraph=1,fragments=[dict(scan='s2',printed_page='1',text=', O God.',page_start=True)]))
        root=unit_document(u,'en',True);p=root.xpath('//tei:body/tei:div/tei:p',namespaces=NS)[0]
        starts=p.xpath('tei:milestone[@corresp]',namespaces=NS)
        self.assertEqual([v.get('corresp')for v in starts],[P+'/text',s['corresp']])
        terminator=p.xpath('tei:milestone[@unit="verse" and not(@corresp)]',namespaces=NS)[0]
        following = (terminator.tail or '') + ''.join(''.join(n.itertext())+(n.tail or '') for n in list(p)[p.index(terminator)+1:])
        self.assertIn('O God',following)
        self.assertEqual(p[-1].get('unit'),'prayer-part')
        self.assertIsNone(p[-1].get('corresp'))

    def test_all_occurrence_controls_are_bound_into_review(self):
        for key,value in [('conditions',[{'type':'opensiddur:service','features':{'service':'musaf'}}]),
                          ('start',P+'/different'),('end',P+'/end'),('reuse',{'en':P}),
                          ('title',{'en':'Different'}),('map_root',False),('marked',True)]:
            with self.subTest(key=key):
                r=fixture();before=dict((k,v) for k,v,_ in review_payloads(r))
                r['units'][1][key]=value
                self.assertNotEqual(before['realization/occurrence/en'],
                                    dict((k,v) for k,v,_ in review_payloads(r))['realization/occurrence/en'])

    def test_unmodeled_host_controls_fail_before_export(self):
        for key in ['conditions','speaker','instructions','marked','repeat','edition_label']:
            with self.subTest(segment=key):
                r=fixture();r['units'][0]['languages']['en'][0][key]='unmodeled'
                with self.assertRaises(ValueError):validate_occurrences(r)
        for key in ['qere_ketiv','alternatives','quotations','abbreviations','enlarged_letters']:
            with self.subTest(fragment=key):
                r=fixture();r['units'][0]['languages']['en'][0]['fragments'][0][key]=[{}]
                with self.assertRaises(ValueError):validate_occurrences(r)

    def test_orphan_overlay_wrong_selection_and_partial_selection_fail(self):
        for mutation in ['host','lang','type','partial','duplicate']:
            with self.subTest(mutation=mutation):
                r=fixture()
                if mutation in ('host','lang'):r['wording_variants'][0][mutation]='missing'
                elif mutation=='type':r['units'][1]['wording_selection'][0]['type']='opensiddur:calendar'
                elif mutation=='partial':del r['units'][1]['wording_selection'][0]['features'][A]
                else:r['wording_variants'].append(deepcopy(r['wording_variants'][0]))
                with self.assertRaises(ValueError):validate_occurrences(r)

    def test_optional_word_is_marked_and_absent_in_selected_occurrence(self):
        r=fixture();s=r['units'][0]['languages']['en'][0];s['fragments'][0]['text']='The (word) follows.'
        r['wording_variants']=[dict(id='optional',host='host',lang='en',identity=P+'/part',
            kind='optional',printed='(word)',text='word',condition=A)]
        r['units'][1]['wording_selection'][0]['features']={A:False}
        r['units'][1]['languages']['en'][0]['fragments'][0]['text']='The follows.'
        validate_occurrences(r)
        root=unit_document(prepare_unit(r['units'][0],r),'en',True)
        self.assertTrue(root.xpath('//j:conditional[@type="marked"]',namespaces=NS))
        self.assertFalse(root.xpath('//j:option',namespaces=NS))
        self.assertFalse(selection(r,'host'))

    def test_canonical_home_rejects_context_controls_and_suppresses_old_pb(self):
        r=fixture();u=r['units'][0]
        u['canonical_home']=dict(file='home',urn=P,title={'en':'Canonical words'},map_root=False,
                                 context_urn='urn:x-opensiddur:text:siddur:example/context')
        context,home=prepare_documents(u,r)
        self.assertFalse(unit_document(home,'en',True).xpath('//tei:pb',namespaces=NS))
        self.assertEqual(home['title'],{'en':'Canonical words'})
        for key in ['conditions','instructions','publication_context','text_corresp','reuse']:
            with self.subTest(key=key):
                altered=deepcopy(u);altered[key]='forbidden'
                with self.assertRaises(ValueError):prepare_documents(altered,r)

    def test_pure_parts_require_attestations_and_never_become_a_service(self):
        r=fixture();host,caller=r['units'];host['canonical_parts']=True
        caller['wording_selection']=selection(r,'host')
        caller['languages']['en'][0]['fragments']=deepcopy(host['languages']['en'][0]['fragments'])
        validate_occurrences(r)
        root=unit_document(prepare_unit(host,r),'en',True)
        self.assertFalse(root.xpath('//tei:pb | //tei:div[@corresp]',namespaces=NS))
        self.assertIn('realization/host/en',dict((k,v)for k,v,_ in review_payloads(r)))
        for mutation in ['no_attestation','speaker','unit_condition','order','range']:
            with self.subTest(mutation=mutation):
                altered=deepcopy(r)
                if mutation=='no_attestation':altered['units']=altered['units'][:1]
                elif mutation=='speaker':altered['units'][0]['languages']['en'][0]['speaker']={'label':'Reader'}
                elif mutation=='unit_condition':altered['units'][0]['conditions']=[]
                elif mutation=='order':altered['expanded_order']=[{'section':'x','order':[{'unit':'host'}]}]
                else:altered['units'][1]['languages']['en'][0]['canonical_end']=P+'/part'
                with self.assertRaises(ValueError):validate_occurrences(altered)

    def test_caller_fidelity_payload_binds_resolved_source_words(self):
        r=fixture();before=dict((k,v)for k,v,_ in review_payloads(r))
        r['wording_variants'][0]['readings'][1]['text']='for always'
        after=dict((k,v)for k,v,_ in review_payloads(r))
        self.assertNotEqual(before['realization/occurrence/en'],after['realization/occurrence/en'])

    def test_literal_home_preserves_page_break_and_scopes_overlay_to_one_fragment(self):
        r=fixture();host,caller=r['units'];segment=host['languages']['en'][0]
        original=deepcopy(segment['fragments'][0]);segment['fragments'][0]['text']='prefix'
        segment['fragments'].append(dict(original,scan='s3',printed_page='2'))
        host['canonical_home']=dict(file='home',urn=P,title={'en':'Example'},map_root=False,
                                   context='literal',context_urn='urn:x-opensiddur:text:siddur:example/context')
        r['wording_variants'][0]['fragment']=1
        caller['languages']['en'][0]['fragments'][0]['text']='prefix forever'
        validate_occurrences(r)
        context,home=prepare_documents(host,r)
        self.assertFalse(context['map_root'])
        self.assertEqual(context['wording_selection'],[])
        self.assertEqual([f['text']for f in context['languages']['en'][0]['fragments']],['prefix','for ever'])
        self.assertEqual(len(unit_document(context,'en',True).xpath('//tei:pb',namespaces=NS)),2)
        self.assertFalse(unit_document(home,'en',True).xpath('//tei:pb',namespaces=NS))
        self.assertIn('alternatives',home['languages']['en'][0]['fragments'][1])
        self.assertNotIn('alternatives',home['languages']['en'][0]['fragments'][0])
        for mutation in ['index','no_context','span_across_join','single_page','same_scan_default']:
            with self.subTest(mutation=mutation):
                altered=deepcopy(r)
                if mutation=='index':del altered['wording_variants'][0]['fragment']
                elif mutation=='no_context':del altered['units'][0]['canonical_home']['context']
                elif mutation=='span_across_join':altered['wording_variants'][0]['printed']='prefix for ever'
                elif mutation=='same_scan_default':
                    fragments=altered['units'][0]['languages']['en'][0]['fragments']
                    fragments[1]['scan']=fragments[0]['scan'];fragments[1].pop('page_start',None)
                else:altered['units'][0]['languages']['en'][0]['fragments'][1]['page_start']=False
                with self.assertRaises(ValueError):validate_occurrences(altered)

    def test_remapping_to_another_valid_host_changes_the_receipt(self):
        r=fixture();before={k:v for k,v,_ in review_payloads(r)}
        other=deepcopy(r['units'][0]);other['stem']='other'
        other['languages']['en'][0]['corresp']=P+'/other'
        other['languages']['en'][0]['fragments'][0]['text']='forever'
        r['units'].append(other)
        r['units'][1]['languages']['en'][0]['canonical']=P+'/other'
        r['units'][1]['wording_selection']=[]
        validate_occurrences(r)
        after={k:v for k,v,_ in review_payloads(r)}
        self.assertNotEqual(before['realization/occurrence/en'],after['realization/occurrence/en'])

    def test_original_cross_page_and_wrong_wording_guards_still_fail(self):
        r=fixture();r['units'][1]['wording_selection']=selection(r,'host')
        with self.assertRaisesRegex(ValueError,'differs from its image'):validate_occurrences(r)
        r=fixture();r['wording_variants']=[];r['units'][1]['wording_selection']=[]
        r['units'][0]['languages']['en'][0]['fragments'].append(dict(scan='s3',text='continuation'))
        with self.assertRaisesRegex(ValueError,'crosses a printed source page'):validate_occurrences(r)

    def test_duplicate_bible_host_fails_before_rendering(self):
        r=fixture();r['wording_variants']=[];r['units'][1]['wording_selection']=[]
        identity='urn:x-opensiddur:text:bible:psalms/146/10'
        r['units'][0]['languages']['en'][0]['corresp']=identity
        other=deepcopy(r['units'][0]);other['stem']='other';r['units'].append(other)
        r['units'][1]['languages']['en'][0]['canonical']=identity
        with self.assertRaisesRegex(ValueError,'one host'):validate_occurrences(r)

    def test_join_respects_punctuation_and_split_words(self):
        from opensiddur.importer.marmorstein_rosh_hashanah_1.realizations import join_source_fragments
        self.assertEqual(join_source_fragments([{'text':'Israel'},{'text':', O God.'}]),'Israel, O God.')
        self.assertEqual(join_source_fragments([{'text':'fore','join_next':True},{'text':'ver'}]),'forever')

    def test_generated_canonical_collision_and_direct_caller_defaults(self):
        from pathlib import Path
        from opensiddur.importer.marmorstein_rosh_hashanah_1.realizations import validate_generated
        r=fixture();root=unit_document(prepare_unit(r['units'][0],r),'en',True)
        caller,body=document('en','example','Example',P+'/caller')
        from lxml import etree
        etree.SubElement(body,'{'+NS['j']+'}transclude',target=P+'/part',type='inline')
        docs=[(Path('/project/example-en/host.xml'),root),(Path('/project/example-en/caller.xml'),caller)]
        validate_generated(docs,r)
        self.assertEqual(caller.xpath('//tei:f/@name',namespaces=NS),[A,B])
        with self.assertRaisesRegex(ValueError,'one generated home|Duplicate generated publication'):
            validate_generated(docs+[(Path('/project/example-en/duplicate.xml'),deepcopy(root))],r)

    def test_range_caller_selects_overlay_after_an_unvaried_start(self):
        from pathlib import Path
        from lxml import etree
        from opensiddur.importer.marmorstein_rosh_hashanah_1.realizations import validate_generated
        r=fixture();u=r['units'][0];u['languages']['en'].insert(0,dict(paragraph=1,corresp=P+'/before',fragments=[dict(scan='s2',printed_page='1',text='Beginning',page_start=True)]))
        root=unit_document(prepare_unit(u,r),'en',True);caller,body=document('en','example','Example',P+'/caller')
        etree.SubElement(body,'{'+NS['j']+'}transclude',target=P+'/before',targetEnd=P+'/part',type='inline')
        validate_generated([(Path('/project/example-en/host.xml'),root),(Path('/project/example-en/caller.xml'),caller)],r)
        self.assertEqual(caller.xpath('//tei:f/@name',namespaces=NS),[A,B])

    def test_expanded_selector_edits_invalidate_realization_review(self):
        r=fixture();before=dict((k,v) for k,v,_ in review_payloads(r))
        r['expanded_order']=[dict(reference={'target':P+'/part'},declarations=[dict(type='opensiddur:variant',features={A:True,B:False})])]
        after=dict((k,v) for k,v,_ in review_payloads(r))
        self.assertNotEqual(before['realization/occurrence/en'],after['realization/occurrence/en'])

    def test_generated_pure_library_rejects_controls_roots_and_ranges(self):
        from pathlib import Path
        from lxml import etree
        from opensiddur.importer.marmorstein_rosh_hashanah_1 import PROJECTS
        from opensiddur.importer.marmorstein_rosh_hashanah_1.realizations import validate_generated
        T='{'+NS['tei']+'}';J='{'+NS['j']+'}'
        def setup():
            r=fixture();host,caller=r['units'];host['canonical_parts']=True
            caller['wording_selection']=selection(r,'host')
            caller['languages']['en'][0]['fragments']=deepcopy(host['languages']['en'][0]['fragments'])
            root=unit_document(prepare_unit(host,r),'en',True)
            other=unit_document(prepare_unit(caller,r),'en',True)
            project=Path('/projects')/PROJECTS['en']
            return r,[(project/'host.xml',root),(project/'occurrence.xml',other)]
        r,docs=setup();validate_generated(docs,r)
        self.assertFalse(docs[0][1].findall('.//'+T+'publicationStmt/'+T+'idno'))
        for mutation in ['pb','note','head','conditional','declare','transclude','root','publication','targetEnd','range']:
            with self.subTest(mutation=mutation):
                r,docs=setup();root=docs[0][1];body=root.find(T+'text/'+T+'body/'+T+'div')
                if mutation in ['conditional','declare','transclude']:etree.SubElement(body,J+mutation)
                elif mutation in ['pb','note','head']:etree.SubElement(body,T+mutation)
                elif mutation=='root':body.set('corresp',P)
                elif mutation=='publication':etree.SubElement(root.find('.//'+T+'publicationStmt'),T+'idno',type='urn').text=P
                else:
                    attrs={'target':P+'/part','targetEnd':P+'/part'}if mutation=='targetEnd'else{'target':P+'/part-/part'}
                    etree.SubElement(docs[1][1].find(T+'text/'+T+'body/'+T+'div'),J+'transclude',**attrs)
                with self.assertRaises(ValueError):validate_generated(docs,r)

    def test_pure_word_edit_changes_the_library_and_both_caller_receipts(self):
        r=fixture();r['wording_variants']=[];host,caller=r['units'];host['canonical_parts']=True
        caller['wording_selection']=[];caller['languages']['en'][0]['fragments']=deepcopy(host['languages']['en'][0]['fragments'])
        other=deepcopy(caller);other['stem']='another';other['urn']='urn:x-opensiddur:text:siddur:another';r['units'].append(other)
        before={k:v for k,v,_ in review_payloads(r)}
        host['languages']['en'][0]['fragments'][0]['text']='changed source words'
        after={k:v for k,v,_ in review_payloads(r)}
        for stem in ['host','occurrence','another']:
            self.assertNotEqual(before['realization/'+stem+'/en'],after['realization/'+stem+'/en'])

    def test_redirected_old_qedushah_keeps_its_own_speakers_and_scope(self):
        import json
        from opensiddur.common.constants import SOURCETEXTS_ROOT
        from opensiddur.importer.marmorstein_rosh_hashanah_1 import BOOK
        from pathlib import Path
        old=json.loads((Path(__file__).parent/'fixtures/marmorstein_qedushah_before_reuse.json').read_text())['unit']
        original=deepcopy(old);parts=[P.replace('prayer:example','prayer:amidah/qedushah')+'/'+s for s in ['qadosh','barukh_kevod','uvedivrei','ledor_vador']]
        library=dict(stem='library',urn='urn:x-opensiddur:text:siddur:shared/qedushah_parts',title={'he':'חלקי קדושה'},canonical_parts=True,languages={'he':[]})
        for segment in old['languages']['he']:
            if segment.get('corresp')in parts:
                identity=segment.pop('corresp');library['languages']['he'].append(dict(corresp=identity,fragments=deepcopy(segment['fragments'])))
                segment['canonical']=identity
        old['page_context']='minchah/qedushah'
        caller=dict(stem='musaf',urn='urn:x-opensiddur:text:siddur:example/musaf',title={'he':'מוסף'},languages={'he':[]})
        for segment in library['languages']['he']:
            caller['languages']['he'].append(dict(canonical=segment['corresp'],speaker={'label':'חזן חדש','role':'reader'},fragments=deepcopy(segment['fragments'])))
        r={'units':[old,library,caller]};validate_occurrences(r)
        self.assertEqual(unit_review_text(old,'he'),unit_review_text(original,'he'))
        root=unit_document(prepare_unit(old,r),'he',True)
        kept={s['corresp']for s in original['languages']['he']if s.get('corresp')not in parts}
        self.assertTrue(kept.issubset(set(root.xpath('//tei:milestone/@corresp',namespaces=NS))))
        transclusions=root.xpath('//j:transclude',namespaces=NS)
        self.assertEqual([n.get('target').partition('@')[0]for n in transclusions],parts)
        for node in transclusions:self.assertEqual(node.getprevious().tag,'{'+NS['tei']+'}note')
        opening=root.xpath('//j:conditional',namespaces=NS)[0]
        ending=root.xpath('//j:endConditional',namespaces=NS)[-1]
        flattened=list(root.iter())
        self.assertTrue(all(flattened.index(opening)<flattened.index(n)<flattened.index(ending)for n in transclusions))
        new=unit_document(prepare_unit(caller,r),'he',True)
        self.assertEqual(new.xpath('//tei:note/text()',namespaces=NS),['חזן חדש']*4)

    def test_opt_in_encoding_receipt_binds_condition_and_option_interpretation(self):
        r=fixture();r['units']=r['units'][:1];r['wording_variants']=[];u=r['units'][0];u['review_encoding']=True
        segment=u['languages']['en'][0]
        before_literal=unit_review_text(u,'en');before={k:v for k,v,_ in review_payloads(r)}
        segment['conditions']=[dict(type='opensiddur:variant',features={A:True})]
        self.assertEqual(unit_review_text(u,'en'),before_literal)
        changed={k:v for k,v,_ in review_payloads(r)}
        self.assertNotEqual(before['realization/host/en'],changed['realization/host/en'])
        segment['fragments'][0]['alternatives']=[dict(printed='for ever',readings=[dict(text='for ever',corresp=A),dict(text='forever',corresp=B)])]
        previous={k:v for k,v,_ in review_payloads(r)}
        segment['fragments'][0]['alternatives'][0]['readings'][1]['corresp']=A+'/different'
        later={k:v for k,v,_ in review_payloads(r)}
        self.assertNotEqual(previous['realization/host/en'],later['realization/host/en'])

    def test_pure_library_root_has_no_target_and_printed_parts_require_pointers(self):
        r=fixture();r['wording_variants']=[];host,caller=r['units'];host['canonical_parts']=True
        caller['wording_selection']=[];caller['languages']['en'][0]['fragments']=deepcopy(host['languages']['en'][0]['fragments'])
        r['expanded_order']=[{'reference':{'target':P+'/part'}}]
        validate_occurrences(r)  # A backed single-part recitation reference is supported.
        for mode in ['order','repeat','transclude','cue','reuse']:
            for target in [host['urn'],P+'/part']:
                with self.subTest(mode=mode,target=target):
                    altered=deepcopy(r)
                    if mode=='order':
                        if target==P+'/part':continue
                        altered['expanded_order']=[{'reference':{'target':target}}]
                    else:
                        extra=deepcopy(caller);extra['stem']='extra';extra['wording_selection']=[]
                        segment=extra['languages']['en'][0];segment.pop('canonical');segment['fragments'][0]['text']='Source cue'
                        if mode=='reuse':extra['reuse']={'en':target}
                        elif mode=='cue':segment['repeat_cue']={'target':target,'text':'cue'}
                        else:segment[mode]=target
                        altered['units'].append(extra)
                    with self.assertRaisesRegex(ValueError,'whole-library target|attested canonical pointers'):
                        validate_occurrences(altered)
