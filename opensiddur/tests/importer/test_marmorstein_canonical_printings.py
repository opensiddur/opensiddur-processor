"""An attested printing has page events without duplicating its shared words."""
from copy import deepcopy
from pathlib import Path
import unittest
from lxml import etree
from opensiddur.importer.marmorstein_rosh_hashanah_1 import PROJECTS
from opensiddur.importer.marmorstein_rosh_hashanah_1 import build as b
from opensiddur.importer.marmorstein_rosh_hashanah_1 import realizations as r
from opensiddur.importer.marmorstein_rosh_hashanah_1.canonical_printings import bindings, apply

P='urn:x-opensiddur:text:prayer:example/part'
A='urn:x-opensiddur:condition:prayer:example/old'
B='urn:x-opensiddur:condition:prayer:example/new'
NS={'t':b.TEI,'j':b.J}


def fixture():
    host=dict(stem='host',urn=P.rsplit('/',1)[0],title={'en':'Example'},languages={'en':[
        dict(corresp=P,paragraph=1,fragments=[dict(scan='s2',printed_page='1',text='alpha beta gamma delta',page_start=True)])]},
        canonical_home=dict(file='words',urn=P.rsplit('/',1)[0],title={'en':'Example'},map_root=False,
                            context_urn='urn:x-opensiddur:text:siddur:example/source'))
    caller=dict(stem='caller',urn='urn:x-opensiddur:text:siddur:example/appendix',title={'en':'Example'},
        wording_selection=[dict(type='opensiddur:variant',features={A:False,B:True})],languages={'en':[
            dict(canonical=P,paragraph=1,fragments=[dict(scan='s346',printed_page='20',text='alpha beta',page_start=True),
                dict(scan='s347',printed_page=None,text='gamma DELTA',page_start=True)])]})
    return dict(units=[host,caller],wording_variants=[dict(id='case',host='host',lang='en',identity=P,
        printed='alpha beta gamma delta',readings=[dict(text='alpha beta gamma delta',corresp=A),dict(text='alpha beta gamma DELTA',corresp=B)])],
        canonical_printings=[dict(id='appendix_next',host='host',caller='caller',lang='en',identity=P,fragment=1,
                                 scan='s347',printed_page=None,before='gamma DELTA')])


class CanonicalPrintingsTest(unittest.TestCase):
    def generated(self,data):
        documents=[]
        for unit in data['units']:
            lang = next(iter(unit['languages']))
            context,home=r.prepare_documents(unit,data)
            documents.append((Path('/tmp/project')/PROJECTS[lang]/(unit['stem']+'.xml'),b.unit_document(context,lang,True)))
            if home:
                documents.append((Path('/tmp/project')/PROJECTS[lang]/(unit['canonical_home']['file']+'.xml'),b.unit_document(home,lang,True)))
        apply(documents,data)
        return documents

    def test_exact_boundary_in_selected_wording_and_one_caller_transclusion(self):
        data=fixture();before=deepcopy(data);r.validate_occurrences(data);documents=self.generated(data)
        self.assertEqual(data,before)
        roots={path.stem:root for path,root in documents};marker=roots['words'].xpath('//t:pb',namespaces=NS)
        self.assertEqual(len(marker),1)
        self.assertEqual(marker[0].get('ed'),'1965 example/appendix')
        self.assertIsNone(marker[0].get('n'))
        self.assertEqual(marker[0].tail,'gamma DELTA')
        self.assertEqual(marker[0].getparent().tag,'{'+b.J+'}option')
        self.assertEqual(len(roots['caller'].xpath('//j:transclude',namespaces=NS)),1)
        self.assertEqual(len(roots['caller'].xpath('//t:pb',namespaces=NS)),1)
        r.validate_generated(documents,data)
        for root in roots.values():
            ok,errors=b.validate(etree.tostring(root,encoding='unicode'))
            self.assertTrue(ok,errors)

    def test_wrong_boundary_source_host_context_or_duplicate_is_rejected(self):
        for mutation in ['missing','word','source','label','host','duplicate','fragment','extra','id','context']:
            with self.subTest(mutation=mutation):
                data=fixture();entry=data['canonical_printings'][0]
                if mutation=='missing':data['canonical_printings']=[]
                elif mutation=='word':entry['before']='DELTA'
                elif mutation=='source':entry['scan']='s348'
                elif mutation=='label':entry['printed_page']='21'
                elif mutation=='host':entry['host']='caller'
                elif mutation=='duplicate':data['canonical_printings'].append(dict(entry,id='second'))
                elif mutation=='fragment':entry['fragment']=True
                elif mutation=='extra':entry['guess']=True
                elif mutation=='id':entry['id']='bad id'
                elif mutation=='context':data['units'][1]['urn']=P
                with self.assertRaises(ValueError):r.validate_occurrences(data)

    def test_no_printing_preserves_single_page_output_and_review_payload(self):
        data=fixture();caller=data['units'][1];caller['languages']['en'][0]['fragments']=[dict(scan='s346',printed_page='20',text='alpha beta gamma DELTA',page_start=True)]
        data.pop('canonical_printings');r.validate_occurrences(data)
        docs=self.generated(data)
        self.assertFalse(next(root for path,root in docs if path.stem=='words').xpath('//t:pb',namespaces=NS))
        payloads={key:value for key,value,_ in r.review_payloads(data)}
        self.assertNotIn('canonical_printings',payloads['realization/caller/en'])

    def test_printing_metadata_invalidates_both_host_and_caller_reviews(self):
        data=fixture();old={k:v for k,v,_ in r.review_payloads(data)}
        data['canonical_printings'][0]['scan']='s348';data['units'][1]['languages']['en'][0]['fragments'][1]['scan']='s348'
        new={k:v for k,v,_ in r.review_payloads(data)}
        for key in ['realization/host/en','realization/caller/en']:self.assertNotEqual(old[key],new[key])

    def test_undeclared_or_repeated_home_page_markers_are_rejected(self):
        for mutation in ['extra','altered','missing']:
            with self.subTest(mutation=mutation):
                data=fixture();docs=self.generated(data);root=next(root for path,root in docs if path.stem=='words');pb=root.xpath('//t:pb',namespaces=NS)[0]
                if mutation=='extra':pb.addnext(deepcopy(pb))
                elif mutation=='altered':pb.set('facs','https://example.org/wrong')
                else:pb.getparent().remove(pb)
                with self.assertRaises(ValueError):r.validate_generated(docs,data)

    def test_scan_links_choose_only_the_current_printing(self):
        from opensiddur.exporter.constants import PROCESSING_NAMESPACE
        from opensiddur.exporter.scan_links import mark_scan_links, SCAN_LINK
        data=fixture();docs=self.generated(data)
        home=next(root for path,root in docs if path.stem=='words')
        page=home.xpath('//t:pb',namespaces=NS)[0]
        for context in ['example/appendix','example/source']:
            with self.subTest(context=context):
                root=etree.Element('{'+b.TEI+'}TEI');body=etree.SubElement(etree.SubElement(root,'{'+b.TEI+'}text'),'{'+b.TEI+'}body')
                outer=etree.SubElement(body,'{'+PROCESSING_NAMESPACE+'}transclude',target='urn:x-opensiddur:text:siddur:'+context)
                p=etree.SubElement(outer,'{'+b.TEI+'}p');first=etree.SubElement(p,'{'+b.TEI+'}pb',ed='1965 '+context,facs='https://example.org/first');first.tail='alpha beta '
                shared=etree.SubElement(p,'{'+PROCESSING_NAMESPACE+'}transclude',target=P)
                copied=deepcopy(page);shared.append(copied);copied.tail='gamma DELTA'
                mark_scan_links(root)
                self.assertEqual(copied.get(SCAN_LINK)=='true',context=='example/appendix')

    def test_real_compiler_preserves_external_boundary_and_words(self):
        import tempfile
        from opensiddur.exporter.compiler import CompilerProcessor
        from opensiddur.exporter.linear import LinearData
        from opensiddur.exporter.refdb import ReferenceDatabase
        from opensiddur.tests.exporter.registry_helpers import unchecked_registry
        data=fixture();docs=self.generated(data);r.validate_generated(docs,data)
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);project=PROJECTS['en']
            for path,root in docs:
                destination=base/project/path.name;destination.parent.mkdir(exist_ok=True)
                destination.write_bytes(etree.tostring(root))
            with ReferenceDatabase(base/'reference.db') as database:
                database.sync_project(project,base)
                state=LinearData(project_priority=[project],instruction_priority=[project],annotation_projects=[])
                state.xml_cache.base_path=base
                with unchecked_registry():
                    compiled=CompilerProcessor(project,'caller.xml',linear_data=state,reference_database=database).process()
                pages=compiled.xpath('//t:body//t:pb[contains(@facs,"n346")]',namespaces=NS)
                self.assertEqual(len(pages),1)
                body=compiled.find('{'+b.TEI+'}text/{'+b.TEI+'}body')
                self.assertEqual(' '.join(''.join(body.itertext()).split()),'alpha beta gamma DELTA')

    def test_no_host_joined_word_or_following_part_is_accepted(self):
        for change in ['no_home','join_word','following']:
            with self.subTest(change=change):
                data=fixture()
                if change=='no_home':data['units'][0].pop('canonical_home')
                elif change=='join_word':data['units'][1]['languages']['en'][0]['fragments'][0]['join_next']=True
                else:data['units'][1]['languages']['en'].append(deepcopy(data['units'][1]['languages']['en'][0]))
                with self.assertRaises(ValueError):bindings(data)

    def test_unselected_option_cannot_supply_a_boundary_phrase(self):
        data=fixture();host,caller=data['units'];host['languages']['en'][0]['fragments'][0]['text']='p alpha alpha beta'
        data['wording_variants'][0].update(printed='alpha beta',readings=[dict(text='alpha beta',corresp=A),dict(text='beta y',corresp=B)])
        caller['languages']['en'][0]['fragments'][0]['text']='p'
        caller['languages']['en'][0]['fragments'][1]['text']='alpha beta y'
        data['canonical_printings'][0]['before']='alpha beta'
        bindings(data)
        with self.assertRaisesRegex(ValueError,'positively selected'):self.generated(data)

    def test_context_change_invalidates_home_review(self):
        data=fixture();before={k:v for k,v,_ in r.review_payloads(data)}
        data['units'][1]['urn']='urn:x-opensiddur:text:siddur:example/another_appendix'
        after={k:v for k,v,_ in r.review_payloads(data)}
        self.assertNotEqual(before['realization/host/en'],after['realization/host/en'])

    def test_three_page_occurrence_keeps_two_ordered_breaks_and_final_bibliography(self):
        data=fixture();host,caller=data['units'];host['languages']['en'][0]['fragments'][0]['text']='alpha beta gamma delta zeta'
        data['wording_variants'][0].update(printed='alpha beta gamma delta zeta',readings=[dict(text='alpha beta gamma delta zeta',corresp=A),dict(text='alpha beta GAMMA DELTA zeta',corresp=B)])
        fragments=caller['languages']['en'][0]['fragments'];fragments[1].update(text='GAMMA',printed_page='21');fragments.append(dict(scan='s348',printed_page='22',text='DELTA zeta',page_start=True))
        data['canonical_printings'][0].update(before='GAMMA',printed_page='21')
        data['canonical_printings'].append(dict(data['canonical_printings'][0],id='third',fragment=2,scan='s348',printed_page='22',before='DELTA zeta'))
        docs=self.generated(data);r.validate_generated(docs,data);home=next(root for path,root in docs if path.stem=='words');output=next(root for path,root in docs if path.stem=='caller')
        self.assertEqual(home.xpath('//t:pb/@n',namespaces=NS),['21','22'])
        self.assertEqual(output.xpath('//t:biblScope/@to',namespaces=NS),['22'])
        self.assertEqual(len(output.xpath('//j:transclude',namespaces=NS)),1)

    def test_another_context_cannot_select_this_printing_option(self):
        data=fixture();other=deepcopy(data['units'][1]);other['stem']='other';other['urn']='urn:x-opensiddur:text:siddur:example/other'
        other['languages']['en'][0]['fragments']=[dict(scan='s8',printed_page='4',text='alpha beta gamma DELTA',page_start=True)]
        data['units'].append(other);docs=self.generated(data)
        with self.assertRaisesRegex(ValueError,'outside its attested caller'):r.validate_generated(docs,data)

    def test_hebrew_divine_name_before_boundary_is_preserved(self):
        data=fixture();host,caller=data['units']
        for unit in data['units']:
            unit['languages']['he']=unit['languages'].pop('en');unit['title']['he']='מודים'
        host['canonical_home']['title']['he']='מודים'
        host['languages']['he'][0]['fragments'][0]['text']='מוֹדִים יְיָ נִסֶּיךָ'
        caller['languages']['he'][0]['fragments'][0]['text']='מוֹדִים יְיָ'
        caller['languages']['he'][0]['fragments'][1]['text']='נִסֶּֽיךָ'
        data['wording_variants'][0].update(lang='he',printed='מוֹדִים יְיָ נִסֶּיךָ',readings=[dict(text='מוֹדִים יְיָ נִסֶּיךָ',corresp=A),dict(text='מוֹדִים יְיָ נִסֶּֽיךָ',corresp=B)])
        data['canonical_printings'][0].update(lang='he',before='נִסֶּֽיךָ')
        docs=self.generated(data);r.validate_generated(docs,data);home=next(root for path,root in docs if path.stem=='words')
        self.assertEqual(len(home.xpath('//j:divineName',namespaces=NS)),2)
        self.assertEqual(home.xpath('//t:pb',namespaces=NS)[0].tail,'נִסֶּֽיךָ')

    def test_boundary_must_advance_to_a_later_scan(self):
        for scan in ['s346','s345']:
            with self.subTest(scan=scan):
                data=fixture();data['units'][1]['languages']['en'][0]['fragments'][1]['scan']=scan
                data['canonical_printings'][0]['scan']=scan
                with self.assertRaises(ValueError):bindings(data)

    def test_root_alias_or_range_cannot_bypass_printing_guard(self):
        for target,endpoint in [(P.rsplit('/',1)[0],None),(P,P)]:
            with self.subTest(target=target,endpoint=endpoint):
                data=fixture();data['units'][0]['canonical_home']['map_root']=True
                docs=self.generated(data);root,body=b.document('en',PROJECTS['en'],'Other','urn:x-opensiddur:text:siddur:rosh_hashanah/other',draft=True)
                declare=b.element(body,'j:declare');declare.set(b.XML+'id','other_settings')
                b.feature_structures(declare,[dict(type='opensiddur:variant',features={A:False,B:True})])
                attributes={'target':target+'@'+PROJECTS['en']}
                if endpoint:attributes['targetEnd']=endpoint
                b.element(body,'j:transclude',type='external',**attributes)
                b.element(body,'j:endDeclare',target='#other_settings')
                docs.append((Path('/tmp/project')/PROJECTS['en']/'other.xml',root))
                with self.assertRaisesRegex(ValueError,'outside its attested caller'):r.validate_generated(docs,data)
