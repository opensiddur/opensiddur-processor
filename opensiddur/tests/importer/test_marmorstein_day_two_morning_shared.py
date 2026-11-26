"""Synthetic printing/provenance and documentary scope regressions."""
import hashlib
import unittest
from copy import deepcopy

from opensiddur.importer.marmorstein_rosh_hashanah_2 import PROJECTS, ROOT_URN
from opensiddur.importer.marmorstein_rosh_hashanah_2.morning_shared import (
    J,
    T,
    contextual_document,
    expressions,
    feature,
    shared_documents,
)

IDENTITY = 'urn:x-opensiddur:text:bible:psalms/17/6'


def fixture():
    xml = f'''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="{J}" xml:lang="he"><tei:text><tei:body><tei:div corresp="{IDENTITY}"><tei:pb n="1" facs="https://example.org/night"/><tei:p><tei:milestone unit="verse" corresp="{IDENTITY}"/><tei:seg source="{IDENTITY}">Night <j:divineName>יי</j:divineName> words.</tei:seg><tei:milestone unit="verse"/></tei:p></tei:div></tei:body></tei:text></tei:TEI>'''
    unit = {'stem': 'synthetic', 'urn': IDENTITY, 'title': {'he': 'ניסוי', 'en': 'Example'}, 'languages': {
        lang: [{'paragraph': 1, 'corresp': IDENTITY, 'fragments': [
            {'scan': 's26', 'printed_page': '2', 'text': 'Morning' if lang=='en' else 'בקר'},
            {'scan': 's28', 'printed_page': '3', 'text': 'continuation' if lang=='en' else 'המשך', 'page_start': True}]}]
        for lang in ('he', 'en')}}
    recipe = {'libraries': [{'unit': 'synthetic', 'stem': 'synthetic_library', 'urn': IDENTITY,
        'xpath': './/tei:seg', 'new_english': True, 'templates': {'he': {'xml': xml, 'sha256': hashlib.sha256(xml.encode()).hexdigest()}}}], 'units': []}
    return recipe, {'synthetic': unit}


class TestMorningShared(unittest.TestCase):
    def test_canonical_boundary_is_outside_alternates_and_selected_page_precedes_words(self):
        recipe, units = fixture()
        documents, features = shared_documents(recipe, units)
        he = next(root for path,root in documents if path.parent.name==PROJECTS['he'])
        markers = [node for node in he.iter(T+'milestone') if node.get('corresp')==IDENTITY]
        self.assertEqual(len(markers), 1)
        self.assertFalse(any(node.tag=='{'+J+'}option' for node in markers[0].iterancestors()))
        options = list(he.iter('{'+J+'}option'))
        night = next(n for n in options if n.get('corresp')==feature(IDENTITY,'night'))
        morning = next(n for n in options if n.get('corresp')==feature(IDENTITY,'morning'))
        self.assertEqual(night[0].tag, T+'pb')
        self.assertFalse((night.text or '').strip())
        self.assertEqual(night[0].get('facs'), 'https://example.org/night')
        self.assertEqual(' '.join(''.join(night.itertext()).split()), 'Night יי words.')
        self.assertEqual([p.get('n')for p in morning.iter(T+'pb')], ['2','3'])
        self.assertTrue(all('day-two' in p.get('facs')for p in morning.iter(T+'pb')))
        selected = expressions(features, 'morning')
        self.assertTrue(selected[feature(IDENTITY,'morning')])
        self.assertFalse(selected[feature(IDENTITY,'night')])

    def test_absent_night_translation_is_guarded_not_an_empty_option(self):
        recipe, units = fixture()
        documents, _ = shared_documents(recipe, units)
        en = next(root for path,root in documents if path.parent.name==PROJECTS['en'])
        div = en.find('.//'+T+'body/'+T+'div')
        self.assertEqual(div[0].tag, '{'+J+'}conditional')
        self.assertEqual(div[-1].tag, '{'+J+'}endConditional')
        self.assertEqual(len(list(en.iter('{'+J+'}option'))), 0)
        self.assertIn('Morning continuation', ' '.join(''.join(div.itertext()).split()))

    def test_accepted_template_hash_is_checked_before_rendering(self):
        recipe, units = fixture()
        recipe['libraries'][0]['templates']['he']['xml']+=' '
        with self.assertRaisesRegex(ValueError, 'Changed accepted printing'):
            shared_documents(recipe, units)

    def test_literal_repeat_has_its_own_bounded_bible_quote_context(self):
        _, units = fixture()
        unit = deepcopy(units['synthetic'])
        unit['languages'] = {'he': [{'paragraph':1, 'reference_unit':'occurrence',
            'corresp': ROOT_URN+'/repeat', 'source': IDENTITY,
            'fragments':[{'scan':'s28','printed_page':'3','text':'אֲנִי קְרָאתִיךָ'}]}]}
        root = contextual_document(unit, 'he')
        markers = [n for n in root.iter(T+'milestone')if n.get('corresp')]
        self.assertEqual([n.get('unit')for n in markers], ['occurrence','chapter','verse'])
        self.assertTrue(all(n.get('corresp').startswith(ROOT_URN+'/morning_occurrences/')for n in markers))
        self.assertTrue(any(n.get('unit')=='verse' and n.get('n')=='6'for n in markers))
        self.assertNotIn(IDENTITY,[n.get('corresp')for n in markers])


class TestApprovedMorningInputs(unittest.TestCase):
    def test_missing_stale_or_unapproved_bindings_fail_closed(self):
        import json
        import tempfile
        from pathlib import Path

        from opensiddur.importer.marmorstein_rosh_hashanah_2.morning_shared import (
            approved_readings,
        )
        with tempfile.TemporaryDirectory() as directory:
            batch=Path(directory)
            (batch/'working').mkdir()
            raw=b'{"units": []}'
            (batch/'working/readings.json').write_bytes(raw)
            record={'status':'approved_source_only','working_readings_sha256':hashlib.sha256(raw).hexdigest()}
            approval=json.dumps(record).encode()
            (batch/'source_approval.json').write_bytes(approval)
            recipe={'readings_sha256':hashlib.sha256(raw).hexdigest(), 'source_approval_sha256':hashlib.sha256(approval).hexdigest()}
            self.assertEqual(approved_readings(batch,recipe),{'units':[]})
            for key in recipe:
                with self.subTest(missing=key):
                    invalid=dict(recipe)
                    invalid.pop(key)
                    with self.assertRaisesRegex(ValueError,'binding'):
                        approved_readings(batch,invalid)
            record['status']='pending'
            approval=json.dumps(record).encode()
            (batch/'source_approval.json').write_bytes(approval)
            recipe['source_approval_sha256']=hashlib.sha256(approval).hexdigest()
            with self.assertRaisesRegex(ValueError,'not current'):
                approved_readings(batch,recipe)

    def test_shared_output_paths_cannot_escape_or_overwrite_each_other(self):
        recipe, units = fixture()
        recipe['libraries'][0]['stem']='../escape'
        with self.assertRaisesRegex(ValueError,'Unsafe'):
            shared_documents(recipe,units)
        recipe, units = fixture()
        recipe['night_callers']={'/tmp/escape.xml':'<TEI/>'}
        with self.assertRaisesRegex(ValueError,'Unsafe night'):
            shared_documents(recipe,units)
