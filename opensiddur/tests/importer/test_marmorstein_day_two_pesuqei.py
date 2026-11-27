"""Synthetic tests for a continuation with an untranslated repeated verse."""
import unittest
from copy import deepcopy

from lxml import etree

from opensiddur.importer.marmorstein_rosh_hashanah_2 import PROJECTS
from opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei import (
    SERVICE_URN,
    XML,
    T,
    append_sequence,
    guard_translation,
    service_document,
)
from opensiddur.importer.scan.authoring import J

NS = {'tei': 'http://www.tei-c.org/ns/1.0', 'j': J}
IDENTITY = 'urn:x-opensiddur:text:bible:psalms/7/2'


class TestPesuqeiContinuation(unittest.TestCase):
    def test_translation_guard_preserves_words_source_and_exact_endpoint(self):
        root = etree.fromstring(f'''<tei:div xmlns:tei="{NS['tei']}"><tei:p>
          <tei:milestone unit="verse" corresp="{IDENTITY}"/>Initial
          <tei:pb facs="https://example.org/scan/8"/><tei:seg>words</tei:seg> tail
          <tei:milestone unit="verse"/>Following unrelated words.
        </tei:p></tei:div>''')
        before = ''.join(root.itertext())
        guard_translation(root, IDENTITY)
        self.assertEqual(''.join(root.itertext()), before)
        marker = root.find('.//'+T+'milestone')
        self.assertEqual(marker.getnext().tag, '{'+J+'}conditional')
        self.assertIsNone(marker.tail)
        end = root.find('.//{'+J+'}endConditional')
        self.assertEqual(end.getnext().get('unit'), 'verse')
        self.assertIsNone(end.getnext().get('corresp'))
        self.assertEqual(marker.getnext().getnext().get('facs'), 'https://example.org/scan/8')

    def test_unbounded_or_duplicate_reference_fails(self):
        for markers in [f'<tei:milestone unit="verse" corresp="{IDENTITY}"/>words',
                        f'<tei:milestone unit="verse" corresp="{IDENTITY}"/><tei:milestone unit="verse" corresp="{IDENTITY}"/><tei:milestone unit="verse"/>']:
            with self.subTest(markers=markers):
                root = etree.fromstring(f'<tei:div xmlns:tei="{NS["tei"]}"><tei:p>{markers}</tei:p></tei:div>')
                with self.assertRaises(ValueError):
                    guard_translation(root, IDENTITY)

    def test_missing_translation_has_no_documentary_call(self):
        units = {'shared': {'urn': IDENTITY, 'languages': {'he': [], 'en': []}},
                 'repeat': {'urn': 'urn:x-opensiddur:text:siddur:example/repeat', 'languages': {'he': []}}}
        order = [{'key': key, 'expanded_target': IDENTITY} for key in units]
        he = service_document(units, order, 'he')
        en = service_document(units, order, 'en')
        self.assertEqual(len(he.findall('.//{'+J+'}transclude')), 2)
        calls = en.findall('.//{'+J+'}transclude')
        self.assertEqual([n.get('target') for n in calls], [IDENTITY+'@'+PROJECTS['en']])
        self.assertFalse(en.findall('.//'+T+'head'))

    def test_expanded_repeat_is_canonical_with_local_translation_suppression(self):
        template = etree.fromstring(f'''<tei:TEI xmlns:tei="{NS['tei']}"><tei:text><tei:body><tei:div>
          <tei:div xml:id="morning_blessings"><tei:head>Morning Prayer</tei:head><tei:p>Earlier words</tei:p></tei:div>
        </tei:div></tei:body></tei:text></tei:TEI>''')
        original = etree.tostring(template)
        units = {'shared': {'urn': IDENTITY, 'languages': {'he': [], 'en': []}},
                 'repeat': {'urn': 'urn:x-opensiddur:text:siddur:example/repeat', 'languages': {'he': []}}}
        order = [{'key': 'shared', 'expanded_target': IDENTITY},
                 {'key': 'repeat', 'expanded_target': IDENTITY, 'hebrew_only_repeat': True}]
        result = append_sequence(template, units, order, lang='he', expanded=True)
        self.assertEqual(etree.tostring(template), original)
        section = result.find('.//'+T+'div[@'+XML+'id="second_day_pesuqei_dezimrah"]')
        self.assertEqual(section.getparent().get(XML+'id'), 'morning_blessings')
        calls = section.findall('.//{'+J+'}transclude')
        self.assertEqual([n.get('target') for n in calls], [IDENTITY, IDENTITY])
        declare = calls[1].getprevious()
        self.assertEqual(declare.tag, '{'+J+'}declare')
        self.assertEqual(declare.find('.//'+T+'binary').get('value'), 'false')
        self.assertEqual(calls[1].getnext().get('target'), '#'+declare.get(XML+'id'))
        self.assertIn('Earlier words', ''.join(result.itertext()))
        self.assertEqual(len(section.findall(T+'head')), 2)

    def test_documentary_extension_stays_below_shacharit(self):
        template = etree.fromstring(f'<tei:TEI xmlns:tei="{NS["tei"]}"><tei:text><tei:body><tei:div><tei:div xml:id="morning_blessings"><tei:head>Morning Prayer</tei:head><tei:p>Existing</tei:p></tei:div></tei:div></tei:body></tei:text></tei:TEI>')
        result = append_sequence(deepcopy(template), {}, [], lang='en')
        call = result.find('.//{'+J+'}transclude')
        self.assertEqual(call.getparent().get(XML+'id'), 'morning_blessings')
        self.assertEqual(call.get('target'), SERVICE_URN+'@'+PROJECTS['en'])

class TestPesuqeiWriteGuards(unittest.TestCase):
    def test_bare_chapter_is_not_a_verse_endpoint(self):
        root = etree.fromstring(f'<tei:div xmlns:tei="{NS["tei"]}"><tei:p><tei:milestone unit="verse" corresp="{IDENTITY}"/>Words<tei:milestone unit="chapter"/></tei:p></tei:div>')
        with self.assertRaisesRegex(ValueError, 'same-unit endpoint'):
            guard_translation(root, IDENTITY)

    def test_guard_uses_a_dedicated_condition_derived_from_its_verse(self):
        from opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei import (
            translation_feature,
        )
        root = etree.fromstring(f'<tei:div xmlns:tei="{NS["tei"]}"><tei:p><tei:milestone unit="verse" corresp="{IDENTITY}"/>Words<tei:milestone unit="verse"/></tei:p></tei:div>')
        guard_translation(root, IDENTITY)
        self.assertEqual(root.find('.//'+T+'f').get('name'), translation_feature(IDENTITY))
        self.assertEqual(root.find('.//'+T+'binary').get('value'), 'true')

    def test_shared_repeat_cannot_invent_a_documentary_english_repeat(self):
        units = {'repeat': {'urn': IDENTITY, 'languages': {'he': [], 'en': []}}}
        with self.assertRaisesRegex(ValueError, 'distinct Hebrew-only'):
            service_document(units, [{'key':'repeat', 'expanded_target':IDENTITY,
                                     'hebrew_only_repeat':True}], 'en')

    def test_project_qualified_targets_and_escaped_paths_are_rejected(self):
        from pathlib import Path

        from opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei import (
            call,
            project_path,
        )
        with self.assertRaisesRegex(ValueError, 'unqualified'):
            call(etree.Element(T+'div'), IDENTITY+'@other-project')
        for path in ('/tmp/private', '../other/file.xml', 'project/../file.xml', 'file.xml'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'Unsafe'):
                project_path(Path('/tmp/projects'), path)

    def test_existing_targets_must_be_unchanged_baselines_or_identical_outputs(self):
        import hashlib
        import tempfile
        from pathlib import Path

        from opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei import (
            verify_existing_outputs,
        )
        from opensiddur.importer.scan.authoring import normalized_xml
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path = base/'example/text.xml'
            path.parent.mkdir()
            root = etree.fromstring(f'<tei:div xmlns:tei="{NS["tei"]}">New words</tei:div>')
            docs = [('example/text.xml', root)]
            path.write_text('Accepted old template', encoding='utf-8')
            template = {'path':'example/text.xml','sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            verify_existing_outputs(base, docs, [template])
            path.write_text(normalized_xml(root), encoding='utf-8')
            verify_existing_outputs(base, docs, [template])
            path.write_text('A subsequent accepted edit', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'unreviewed changes'):
                verify_existing_outputs(base, docs, [template])

    def test_only_reviewed_edition_parallel_profiles_can_supply_english(self):
        import hashlib
        import tempfile
        from pathlib import Path

        import yaml

        from opensiddur.importer.marmorstein_rosh_hashanah_2 import EXPANDED
        from opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei import (
            require_edition_parallel_profiles,
        )
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            hashes = {}
            for relative in (PROJECTS['he']+'/documentary_parallel.yaml', EXPANDED+'/second_day_morning.yaml'):
                path = base/relative
                path.parent.mkdir(exist_ok=True)
                path.write_text(yaml.safe_dump({'parallel':{'projects':[PROJECTS['en']]}}), encoding='utf-8')
                hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            require_edition_parallel_profiles(base, hashes)
            path.write_text(yaml.safe_dump({'parallel':{'projects':[PROJECTS['en'],'unprinted_english']}}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'profile changed'):
                require_edition_parallel_profiles(base, hashes)
            hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'missing translations'):
                require_edition_parallel_profiles(base, hashes)


class TestRepeatedVerseCompilation(unittest.TestCase):
    def test_first_translation_survives_while_repeat_stays_hebrew_only(self):
        import tempfile
        from pathlib import Path

        from opensiddur.exporter.external_compiler import ExternalCompilerProcessor
        from opensiddur.exporter.linear import LinearData
        from opensiddur.exporter.refdb import ReferenceDatabase
        from opensiddur.importer.marmorstein_rosh_hashanah_2.morning_shared import (
            declaration,
        )
        from opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei import (
            translation_feature,
        )
        from opensiddur.importer.scan.authoring import element
        from opensiddur.tests.exporter.test_conditional_counterpart import doc
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db = ReferenceDatabase(base/'references.sqlite')
            self.addCleanup(db.close)
            bodies = {
                'he': f'<tei:div><tei:p><tei:milestone unit="verse" corresp="{IDENTITY}"/>HE-WORDS<tei:milestone unit="verse"/></tei:p></tei:div>',
                'en': f'<tei:div><tei:p><tei:milestone unit="verse" corresp="{IDENTITY}"/>EN-WORDS<tei:milestone unit="verse"/></tei:p></tei:div>',
                'unselected_en': f'<tei:div corresp="{IDENTITY}">UNPRINTED-FALLBACK</tei:div>',
            }
            for project, body in bodies.items():
                root = etree.fromstring(doc(body, 'he' if project == 'he' else 'en').encode('utf-8'))
                if project == 'en':
                    guard_translation(root, IDENTITY)
                directory = base/project
                directory.mkdir()
                path = directory/'text.xml'
                path.write_bytes(etree.tostring(root))
                db.index_file(path, project, 'text.xml')
            for first in (True, False, None):
                with self.subTest(first=first):
                    spine = etree.fromstring(doc('<tei:div/>').encode('utf-8'))
                    parent = spine.find('.//'+T+'body/'+T+'div')
                    feature = translation_feature(IDENTITY)
                    if first is not None:
                        declaration(parent, 'first', {feature:first})
                    element(parent,'j:transclude',target=IDENTITY,type='external')
                    if first is not None:
                        element(parent,'j:endDeclare',target='#first')
                    declaration(parent,'repeat',{feature:False})
                    element(parent,'j:transclude',target=IDENTITY,type='external')
                    element(parent,'j:endDeclare',target='#repeat')
                    directory = base/'spine'
                    directory.mkdir(exist_ok=True)
                    path = directory/'text.xml'
                    path.write_bytes(etree.tostring(spine))
                    ld = LinearData(project_priority=['he'], parallel_projects=['en'])
                    ld.xml_cache.base_path = base
                    result = ExternalCompilerProcessor('spine','text.xml',linear_data=ld,
                                                       reference_database=db).process()
                    output = etree.Element('output')
                    output.extend(result)
                    text = ' '.join(''.join(output.itertext()).split())
                    self.assertEqual(text.count('HE-WORDS'),2)
                    self.assertEqual(text.count('EN-WORDS'),0 if first is False else 1)
                    self.assertNotIn('UNPRINTED-FALLBACK',text)

class TestPesuqeiRecipeAssembly(unittest.TestCase):
    def fixture(self):
        import hashlib

        from opensiddur.importer.marmorstein_rosh_hashanah_2 import EXPANDED
        unit = {'stem':'example_words','urn':'urn:x-opensiddur:text:bible:psalms/7',
                'title':{'he':'ניסיון','en':'Example'},'languages':{
                    lang:[{'corresp':IDENTITY,'paragraph':1,'fragments':[
                        {'scan':'s8','printed_page':'1','text':'HE' if lang=='he' else 'EN'}]}]
                    for lang in ('he','en')}}
        repeat = {'stem':'example_repeat','urn':'urn:x-opensiddur:text:siddur:example/repeat',
                  'title':{'he':'חזרה','en':'Repeat'},'languages':{'he':[
                      {'corresp':'urn:x-opensiddur:text:siddur:example/repeat/verse',
                       'source':IDENTITY,'reference_unit':'verse','paragraph':1,
                       'fragments':[{'scan':'s8','printed_page':'1','text':'HE'}]}]}}
        template = f'<tei:TEI xmlns:tei="{NS["tei"]}"><tei:text><tei:body><tei:div><tei:div xml:id="morning_blessings"><tei:head>Morning Prayer</tei:head><tei:p>Accepted earlier words</tei:p></tei:div></tei:div></tei:body></tei:text></tei:TEI>'
        paths = [p+'/morning_prayers_service.xml' for p in PROJECTS.values()]+[EXPANDED+'/second_day_morning.xml']
        recipe = {'order':[{'key':'example_words','expanded_target':IDENTITY},
                           {'key':'example_repeat','expanded_target':IDENTITY,'hebrew_only_repeat':True}],
                  'protected_files':{},'spine_templates':[]}
        for path in paths:
            project = path.split('/')[0]
            lang = 'en' if project == PROJECTS['en'] else 'he'
            xml = template.replace('<tei:TEI ', '<tei:TEI xml:lang="'+lang+'" ', 1).replace('<tei:text>', '<tei:teiHeader><tei:fileDesc><tei:publicationStmt><tei:idno type="urn">urn:x-opensiddur:text:siddur:example@'+project+'</tei:idno></tei:publicationStmt></tei:fileDesc></tei:teiHeader><tei:text>', 1)
            recipe['spine_templates'].append({'path':path,'xml':xml,'sha256':hashlib.sha256(xml.encode('utf-8')).hexdigest(),'baseline_commit':'a'*40})
        return recipe, {u['stem']:u for u in (unit,repeat)}

    def test_full_assembly_keeps_literal_repeat_and_guards_one_english_provider(self):
        from opensiddur.importer.marmorstein_rosh_hashanah_2 import EXPANDED
        from opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei import (
            build_documents,
        )
        recipe, units = self.fixture()
        documents = dict(build_documents(recipe, units))
        self.assertEqual(len(documents),8)
        en = documents[PROJECTS['en']+'/example_words.xml']
        self.assertEqual(len(en.findall('.//{'+J+'}conditional')),1)
        source = documents[PROJECTS['en']+'/pesuqei_service.xml']
        self.assertEqual(len(source.findall('.//{'+J+'}transclude')),1)
        expanded = documents[EXPANDED+'/second_day_morning.xml']
        self.assertEqual(len(expanded.findall('.//{'+J+'}transclude')),2)
        self.assertIn('Accepted earlier words',''.join(expanded.itertext()))

    def test_repeat_without_an_english_canonical_boundary_fails_closed(self):
        from opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei import (
            build_documents,
        )
        recipe, units = self.fixture()
        units['example_words']['languages']['en'][0]['corresp'] = IDENTITY.rsplit('/',1)[0]+'/3'
        with self.assertRaisesRegex(ValueError, 'guardable English'):
            build_documents(recipe,units)

    def test_duplicate_order_stale_templates_and_protected_targets_are_rejected(self):
        from opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei import (
            build_documents,
        )
        for failure in ('order','template','protected'):
            with self.subTest(failure=failure):
                recipe, units = self.fixture()
                if failure=='order':recipe['order'].append(dict(recipe['order'][0]))
                elif failure=='template':recipe['spine_templates'][0]['xml']+=' '
                else:recipe['protected_files'][PROJECTS['he']+'/example_words.xml']='protected'
                with self.assertRaises(ValueError):
                    build_documents(recipe,units)

    def test_unreviewed_structure_cannot_reach_project_writes(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from opensiddur.importer.marmorstein_rosh_hashanah_2 import BOOK
        from opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei import BATCH, main
        with tempfile.TemporaryDirectory() as tmp:
            batch=Path(tmp)/BOOK/'batches'/BATCH
            batch.mkdir(parents=True)
            (batch/'pesuqei_units.json').write_text('{}',encoding='utf-8')
            (batch/'recipe_approval.json').write_text(json.dumps({'status':'pending'}),encoding='utf-8')
            with patch('opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei.write_documents') as write:
                with self.assertRaisesRegex(ValueError,'independent review'):
                    main(['--source-root',tmp,'--project-directory',str(Path(tmp)/'projects')])
                write.assert_not_called()


    def test_generated_documentary_and_expanded_nested_scopes_compile(self):
        import tempfile
        from pathlib import Path

        from opensiddur.exporter.external_compiler import ExternalCompilerProcessor
        from opensiddur.exporter.linear import LinearData
        from opensiddur.exporter.refdb import ReferenceDatabase
        from opensiddur.importer.marmorstein_rosh_hashanah_2 import EXPANDED
        from opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei import (
            build_documents,
        )
        from opensiddur.tests.exporter.test_conditional_counterpart import doc
        recipe, units = self.fixture()
        units['example_words']['map_root'] = True
        recipe['order'][0]['expanded_target'] = units['example_words']['urn']
        following = deepcopy(units['example_words'])
        following.update(stem='example_following', urn=IDENTITY.rsplit('/',1)[0]+'/following')
        for lang, segments in following['languages'].items():
            segments[0]['corresp'] = IDENTITY.rsplit('/',1)[0]+'/3'
            segments[0]['fragments'] = [{'scan':'s9','printed_page':'2','text':'AFTER-'+lang}]
        units['example_following'] = following
        recipe['order'].append({'key':'example_following','expanded_target':following['urn']})
        partial_root='urn:x-opensiddur:text:bible:psalms/8'
        partial=deepcopy(following)
        partial.update(stem='example_partial',urn=partial_root)
        partial['languages']={lang:[{'corresp':partial_root+'/'+str(v),'paragraph':v,
                                   'fragments':[{'scan':'s10','printed_page':'3','text':'PART'+str(v)+'-'+lang}]}
                                   for v in ([1,2,3]if lang=='he'else[1,3])]
                              for lang in ('he','en')}
        units['example_partial']=partial
        recipe['order'].append({'key':'example_partial','expanded_target':partial_root,
                                'ranges':[{'target':partial_root+'/'+str(v),'witnesses':['he']if v==2 else['he','en']}for v in (1,2,3)]})

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db = ReferenceDatabase(base/'references.sqlite')
            self.addCleanup(db.close)
            documents = dict(build_documents(recipe,units))
            for project in PROJECTS.values():
                documents[project+'/index.xml'] = etree.fromstring(doc(
                    '<tei:div/>','en' if project==PROJECTS['en'] else 'he').encode())
                header = documents[project+'/index.xml'].find('.//'+T+'fileDesc')
                source = etree.SubElement(header,T+'sourceDesc')
                etree.SubElement(source,T+'bibl',{XML+'id':'day_two_source_bibl'}).text='Synthetic source'
            documents['unselected_english/text.xml'] = etree.fromstring(doc(
                f'<tei:div corresp="{IDENTITY}">UNPRINTED-FALLBACK</tei:div>','en').encode())
            for relative, root in documents.items():
                path = base/relative
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(etree.tostring(root))
                project, filename = relative.split('/')
                db.index_file(path,project,filename)
            for project, filename in [(EXPANDED,'second_day_morning.xml'),
                                      (PROJECTS['he'],'pesuqei_service.xml')]:
                with self.subTest(project=project):
                    ld = LinearData(project_priority=[PROJECTS['he']],parallel_projects=[PROJECTS['en']])
                    ld.xml_cache.base_path = base
                    result = ExternalCompilerProcessor(project,filename,linear_data=ld,reference_database=db).process()
                    output = etree.Element('output')
                    output.extend(result)
                    words = ' '.join(''.join(p.itertext()) for p in output.iter(T+'p')).split()
                    self.assertEqual(words.count('HE'),2)
                    self.assertEqual(words.count('EN'),1)
                    self.assertEqual(words.count('AFTER-he'),1)
                    self.assertEqual(words.count('AFTER-en'),1)
                    self.assertNotIn('UNPRINTED-FALLBACK',words)
                    for v in (1,2,3):
                        self.assertEqual(words.count('PART'+str(v)+'-he'),1)
                        self.assertEqual(words.count('PART'+str(v)+'-en'),0 if v==2 else 1)
                    gap=[n for n in output.iter('{http://jewishliturgy.org/ns/processing}transclude')if n.get('target','').split('@')[0]==partial_root+'/2']
                    self.assertEqual(len(gap),1)
                    counterparts=gap[0].xpath('.//*[@role="parallel"]')
                    self.assertFalse(''.join(''.join(n.itertext())for n in counterparts).strip())
                    english_pages = output.xpath('.//tei:pb[ancestor::*[@xml:lang="en"]]/@facs',namespaces=NS)
                    # A repeated Hebrew-only verse must not claim an English page.
                    changes = [url for i,url in enumerate(english_pages) if i==0 or url!=english_pages[i-1]]
                    self.assertEqual(len(changes),3)
                    self.assertTrue(changes[0].endswith('/n7.jpg'))
                    self.assertTrue(changes[1].endswith('/n8.jpg'))
                    self.assertTrue(changes[2].endswith('/n9.jpg'))

    def test_an_older_unguarded_provider_is_rejected(self):
        import tempfile
        from pathlib import Path

        from opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei import (
            reject_existing_repeat_providers,
        )
        recipe, units = self.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path = base/PROJECTS['en']/'older.xml'
            path.parent.mkdir()
            path.write_text(f'<tei:div xmlns:tei="{NS["tei"]}"><tei:milestone unit="verse" corresp="{IDENTITY}"/>Old English</tei:div>',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'bypass the repeat guard'):
                reject_existing_repeat_providers(base,[],recipe['order'])
            reject_existing_repeat_providers(base,[(str(path.relative_to(base)),etree.Element(T+'div'))],recipe['order'])
            path.write_text(f'<tei:div xmlns:tei="{NS["tei"]}" corresp="{IDENTITY}">Old root provider</tei:div>',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'bypass the repeat guard'):
                reject_existing_repeat_providers(base,[],recipe['order'])

    def test_containing_scope_and_wrong_language_template_fail_closed(self):
        import hashlib

        from opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei import (
            build_documents,
        )
        root = etree.fromstring(f'<tei:div xmlns:tei="{NS["tei"]}"><tei:p><tei:milestone unit="verse" corresp="{IDENTITY}"/>Words<tei:milestone unit="chapter" corresp="{IDENTITY.rsplit("/",1)[0]}"/><tei:milestone unit="verse"/></tei:p></tei:div>')
        with self.assertRaisesRegex(ValueError,'Containing reference'):
            guard_translation(root,IDENTITY)
        recipe, units = self.fixture()
        template=recipe['spine_templates'][0]
        template['xml']=template['xml'].replace('xml:lang="he"','xml:lang="en"')
        template['sha256']=hashlib.sha256(template['xml'].encode()).hexdigest()
        with self.assertRaisesRegex(ValueError,'language/publication'):
            build_documents(recipe,units)


    def test_range_availability_must_match_actual_witness_boundaries(self):
        from opensiddur.importer.marmorstein_rosh_hashanah_2.pesuqei import (
            build_documents,
        )
        for mismatch in ('unprinted_english','missing_english'):
            with self.subTest(mismatch=mismatch):
                recipe, units=self.fixture()
                item=recipe['order'][0]
                item['ranges']=[{'target':IDENTITY,'witnesses':['he']if mismatch=='unprinted_english'else['he','en']}]
                if mismatch=='missing_english':
                    units['example_words']['languages']['en'][0]['corresp']=IDENTITY.rsplit('/',1)[0]+'/3'
                with self.assertRaisesRegex(ValueError,'availability disagrees'):
                    build_documents(recipe,units)
