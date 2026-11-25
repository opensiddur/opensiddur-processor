"""Intrinsic prayer choices survive shared printings without moving instructions."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from lxml import etree
from opensiddur.tests.importer import test_marmorstein_canonical_printings as printing_cases
fixture = printing_cases.fixture
P, A, B, NS = printing_cases.P, printing_cases.A, printing_cases.B, printing_cases.NS
from opensiddur.importer.marmorstein_rosh_hashanah_1 import build as b
from opensiddur.importer.marmorstein_rosh_hashanah_1 import realizations as r
F='urn:x-opensiddur:condition:prayer:example/family'


def intrinsic_fixture():
    data=fixture();host,caller=data['units'];old=dict(printed='(family)',text='family',condition=F);new=dict(printed='(household)',text='household',condition=F)
    host['languages']['en'][0]['fragments'][0].update(text='alpha (family) gamma',optional_spans=[old])
    host['languages']['en'].append(dict(paragraph=2,corresp=P.rsplit('/',1)[0]+'/amen',instructions=[dict(language='en',text='Finish together.')],fragments=[dict(scan='s2',printed_page='1',text='Amen.',page_start=False)]))
    host['canonical_home'].update(preserve_intrinsic_optionals=True,instructions_in_context=True)
    data['wording_variants'][0].update(printed='alpha (family) gamma',readings=[dict(text='alpha (family) gamma',corresp=A,optional_spans=[old]),dict(text='ALPHA (household) GAMMA',corresp=B,optional_spans=[new])])
    caller['languages']['en'][0]['fragments'][0]['text']='ALPHA (household)'
    caller['languages']['en'][0]['fragments'][1]['text']='GAMMA'
    data['canonical_printings'][0]['before']='GAMMA'
    return data


class IntrinsicOptionalTest(unittest.TestCase):
    def generated(self,data):
        return printing_cases.CanonicalPrintingsTest().generated(data)

    def test_intrinsic_controls_and_instructions_stay_in_correct_documents(self):
        data=intrinsic_fixture();before=deepcopy(data);r.validate_occurrences(data);docs=self.generated(data);r.validate_generated(docs,data)
        roots={path.stem:root for path,root in docs}
        self.assertEqual(data,before)
        self.assertFalse(roots['words'].xpath('//t:note',namespaces=NS))
        self.assertEqual(roots['host'].xpath('//t:note/text()',namespaces=NS),['Finish together.'])
        self.assertEqual(len(roots['words'].xpath('//j:option/j:conditional[@type="marked"]',namespaces=NS)),2)
        ids=roots['words'].xpath('//@xml:id',namespaces={'xml':b.XML[1:-1]})
        self.assertEqual(len(ids),len(set(ids)))
        for root in roots.values():
            ok,errors=b.validate(etree.tostring(root,encoding='unicode'));self.assertTrue(ok,errors)

    def test_optional_words_really_include_and_omit_through_compiler(self):
        from opensiddur.exporter.compiler import CompilerProcessor
        from opensiddur.exporter.linear import LinearData
        from opensiddur.exporter.refdb import ReferenceDatabase
        from opensiddur.tests.exporter.registry_helpers import unchecked_registry
        for included in [False,True]:
            with self.subTest(included=included), tempfile.TemporaryDirectory() as directory:
                data=intrinsic_fixture();docs=self.generated(data);r.validate_generated(docs,data);base=Path(directory);project=b.PROJECTS['en']
                for path,root in docs:
                    if path.stem=='caller':
                        div=root.find('{'+b.TEI+'}text/{'+b.TEI+'}body/{'+b.TEI+'}div');start=etree.Element('{'+b.J+'}declare',attrib={b.XML+'id':'family_settings'});b.feature_structures(start,[dict(type='opensiddur:variant',features={F:included})]);div.insert(0,start);b.element(div,'j:endDeclare',target='#family_settings')
                    dest=base/project/path.name;dest.parent.mkdir(exist_ok=True);dest.write_bytes(etree.tostring(root))
                database=ReferenceDatabase(base/'reference.db')
                try:
                    database.sync_project(project,base);state=LinearData(project_priority=[project],instruction_priority=[project],annotation_projects=[]);state.xml_cache.base_path=base
                    with unchecked_registry():compiled=CompilerProcessor(project,'caller.xml',linear_data=state,reference_database=database).process()
                    body=compiled.find('{'+b.TEI+'}text/{'+b.TEI+'}body');text=' '.join(''.join(body.itertext()).split());self.assertEqual(text,'ALPHA household GAMMA'if included else'ALPHA GAMMA');self.assertEqual(len(body.xpath('.//t:pb[contains(@facs,"n346")]',namespaces=NS)),1)
                finally:database.close()

    def test_controls_must_be_explicit_and_printing_conditions_must_agree(self):
        for mutation in ['flag','instruction_flag','wrong_condition','missing_span','partial','bad_instruction']:
            with self.subTest(mutation=mutation):
                data=intrinsic_fixture();host=data['units'][0];overlay=data['wording_variants'][0]
                if mutation=='flag':host['canonical_home'].pop('preserve_intrinsic_optionals')
                elif mutation=='instruction_flag':host['canonical_home'].pop('instructions_in_context')
                elif mutation=='wrong_condition':overlay['readings'][1]['optional_spans'][0]['condition']=F+'/different'
                elif mutation=='missing_span':overlay['readings'][1]['optional_spans'][0]['printed']='(absent)'
                elif mutation=='partial':overlay.update(printed='alpha',readings=[dict(text='alpha',corresp=A),dict(text='ALPHA',corresp=B)])
                else:host['languages']['en'][1]['instructions']=[dict(text='No language')]
                with self.assertRaises(ValueError):r.validate_occurrences(data)

    def test_page_marker_cannot_disappear_with_omitted_optional_words(self):
        data=intrinsic_fixture();host,caller=data['units'];old=dict(printed='(family child)',text='family child',condition=F);new=dict(printed='(household CHILD)',text='household CHILD',condition=F)
        host['languages']['en'][0]['fragments'][0].update(text='alpha (family child) gamma',optional_spans=[old])
        data['wording_variants'][0].update(printed='alpha (family child) gamma',readings=[dict(text='alpha (family child) gamma',corresp=A,optional_spans=[old]),dict(text='ALPHA (household CHILD) GAMMA',corresp=B,optional_spans=[new])])
        caller['languages']['en'][0]['fragments'][0]['text']='ALPHA (household'
        caller['languages']['en'][0]['fragments'][1]['text']='CHILD) GAMMA'
        data['canonical_printings'][0]['before']='CHILD'
        with self.assertRaisesRegex(ValueError,'disappear inside optional words'):self.generated(data)

    def test_overlay_cannot_invent_intrinsic_optional_controls(self):
        data=intrinsic_fixture();data['units'][0]['languages']['en'][0]['fragments'][0].pop('optional_spans')
        with self.assertRaisesRegex(ValueError,'intrinsic source optional'):r.validate_occurrences(data)

    def test_legacy_identical_optional_occurrences_keep_sequential_semantics(self):
        unit=dict(stem='legacy',urn=P,title={'en':'Legacy'},languages={'en':[dict(paragraph=1,fragments=[dict(scan='s2',printed_page='1',text='(x) and (x)',optional_spans=[dict(printed='(x)',text='x',condition=F),dict(printed='(x)',text='x',condition=F+'/other')])])]})
        root=b.unit_document(unit,'en',True)
        self.assertEqual(len(root.xpath('//j:conditional[@type="marked"]',namespaces=NS)),2)
        self.assertEqual(root.xpath('//j:conditional/@xml:id',namespaces={**NS,'xml':b.XML[1:-1]}),['legacy_optional_0_0_0','legacy_optional_0_0_1'])

    def test_nonboolean_home_interpretation_flags_are_rejected(self):
        for key in ['preserve_intrinsic_optionals','instructions_in_context']:
            for value in [False,'true',1]:
                with self.subTest(key=key,value=value):
                    data=intrinsic_fixture();data['units'][0]['canonical_home'][key]=value
                    with self.assertRaises(ValueError):r.validate_occurrences(data)

    def test_intrinsic_home_without_overlay_still_preserves_flat_optionals(self):
        data=intrinsic_fixture();data['wording_variants']=[];data['canonical_printings']=[];caller=data['units'][1];caller.pop('wording_selection');caller['languages']['en'][0]['fragments']=[dict(scan='s346',printed_page='20',text='alpha (family) gamma',page_start=True)]
        r.validate_occurrences(data);docs=self.generated(data);r.validate_generated(docs,data);roots={path.stem:root for path,root in docs}
        self.assertEqual(len(roots['words'].xpath('//j:conditional[@type="marked"]',namespaces=NS)),1)
        self.assertFalse(roots['host'].xpath('//j:conditional[@type="marked"]',namespaces=NS))
        data['units'][0]['languages']['en'][0]['fragments'][0]['optional_spans'][0]['printed']='family)'
        with self.assertRaises(ValueError):r.validate_occurrences(data)
