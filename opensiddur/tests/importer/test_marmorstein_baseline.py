"""Existing acceptance is fixed before new identities and pointers are introduced."""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from opensiddur.common.constants import SOURCETEXTS_ROOT
from opensiddur.importer.marmorstein_rosh_hashanah_1 import BOOK
from opensiddur.importer.marmorstein_rosh_hashanah_1.baseline import (
    snapshot,
    validate_baseline,
    validate_redirection,
)

BASELINE=Path(__file__).parent/'fixtures/marmorstein_accepted_660.json'
PARTS=['urn:x-opensiddur:text:prayer:amidah/qedushah/'+x
       for x in ['qadosh','barukh_kevod','uvedivrei','ledor_vador']]


def accepted_readings():
    path = SOURCETEXTS_ROOT/BOOK/'readings.json'
    if not path.exists():
        raise unittest.SkipTest('Accepted source integration requires the sourcetexts submodule')
    return json.loads(path.read_text())


class LiteralBaselineTest(unittest.TestCase):
    def test_source_integration_reports_missing_submodule_as_skip(self):
        with TemporaryDirectory() as folder, patch(__name__+'.SOURCETEXTS_ROOT', Path(folder)):
            with self.assertRaisesRegex(unittest.SkipTest, 'sourcetexts submodule'):
                accepted_readings()

    def test_all660_literal_witnesses_and_protected_raw_fields_stay_accepted(self):
        baseline=json.loads(BASELINE.read_text())
        self.assertEqual(sum(len(x['literal_sha256'])for x in baseline.values()),660)
        validate_baseline(accepted_readings(),baseline)

    def test_frozen_qedushah_fixture_has_accepted_provenance(self):
        unit=json.loads((BASELINE.parent/'marmorstein_qedushah_before_reuse.json').read_text())['unit']
        self.assertEqual(snapshot({'units':[unit]})['amidah_qedushah'],
                         json.loads(BASELINE.read_text())['amidah_qedushah'])

    def test_integrated_source_baseline_extends_fixed_importer_fixture(self):
        readings=accepted_readings()
        if any(u.get('canonical_parts') for u in readings['units']):
            self.assertIn('accepted_literal_baseline',readings)
            path=SOURCETEXTS_ROOT/BOOK/readings['accepted_literal_baseline']
            current = json.loads(path.read_text())
            fixed = json.loads(BASELINE.read_text())
            self.assertLessEqual(fixed.keys(), current.keys())
            self.assertEqual({key: current[key] for key in fixed}, fixed)
            validate_baseline(readings, current)

    def test_only_mapping_additions_are_allowed_and_raw_fragment_changes_fail(self):
        original=accepted_readings();baseline=json.loads(BASELINE.read_text());changed=deepcopy(original)
        unit=next(u for u in changed['units']if u['stem']=='amidah_qedushah')
        unit['page_context']='rosh_hashanah/minchah/qedushah';unit['wording_selection']=[]
        part=next(s for s in unit['languages']['he']if s.get('corresp',s.get('canonical'))==PARTS[0])
        part.pop('corresp',None);part['canonical']=PARTS[0]
        validate_baseline(changed,baseline)
        for key in ['text','scan','printed_page','page_start','join_next']:
            with self.subTest(key=key):
                altered=deepcopy(changed);fragment=altered['units'][0]['languages']['he'][0]['fragments'][0]
                fragment[key]=('different' if key not in ['page_start','join_next'] else not fragment.get(key,False))
                with self.assertRaisesRegex(ValueError,'Accepted source witness'):validate_baseline(altered,baseline)
        altered=deepcopy(changed);altered['units'][0]['title']['he']='Changed'
        with self.assertRaises(ValueError):validate_baseline(altered,baseline)

    def test_enabling_encoding_review_preserves_legacy_source_and_binds_mapping(self):
        from opensiddur.importer.marmorstein_rosh_hashanah_1.realizations import (
            review_payloads,
        )
        original = {'units': [dict(stem='old', urn='urn:x-opensiddur:text:siddur:example',
            title={'he': 'Example'}, languages={'he': [dict(paragraph=1,
                fragments=[dict(scan='s1', printed_page='1', text='words', page_start=True)])]})]}
        baseline = snapshot(original)
        reviewed = deepcopy(original)
        reviewed['units'][0]['review_encoding'] = True
        validate_baseline(reviewed, baseline)
        payload = {key: value for key, value, _ in review_payloads(reviewed)}
        self.assertIn('realization/old/he', payload)
        reviewed['units'][0]['languages']['he'][0]['end_reference'] = True
        validate_baseline(reviewed, baseline)
        changed = {key: value for key, value, _ in review_payloads(reviewed)}
        self.assertNotEqual(payload['realization/old/he'], changed['realization/old/he'])
        for mutation in ('text', 'title', 'disabled', 'non_boolean'):
            with self.subTest(mutation=mutation):
                bad = deepcopy(reviewed)
                if mutation == 'text':
                    bad['units'][0]['languages']['he'][0]['fragments'][0]['text'] = 'changed'
                elif mutation == 'title':
                    bad['units'][0]['title']['he'] = 'Changed'
                else:
                    bad['units'][0]['review_encoding'] = False if mutation == 'disabled' else 'yes'
                with self.assertRaises(ValueError):
                    validate_baseline(bad, baseline)
        gated = snapshot(reviewed)
        reviewed['units'][0].pop('review_encoding')
        with self.assertRaises(ValueError):
            validate_baseline(reviewed, gated)

    def test_redirection_preflight_checks_controls_and_interpretations(self):
        old=json.loads((BASELINE.parent/'marmorstein_qedushah_before_reuse.json').read_text())['unit']
        original={'units':[old]};validate_redirection(original,'amidah_qedushah',PARTS)
        for mutation in ['fragments','conditions','source_reference_part','condition_end_corresp','repeat_cue','citation','quotations','transclude','order_reference']:
            with self.subTest(mutation=mutation):
                r=deepcopy(original);unit=next(u for u in r['units']if u['stem']=='amidah_qedushah')
                segment=next(s for s in unit['languages']['he']if s.get('corresp')==PARTS[0])
                if mutation=='fragments':segment['fragments']*=2
                elif mutation=='conditions':segment['conditions']=[{}]
                elif mutation=='source_reference_part':segment[mutation]={'unit':'half-verse'}
                elif mutation=='condition_end_corresp':unit['languages']['he'][0][mutation]=PARTS[0]
                elif mutation=='repeat_cue':unit['languages']['he'][0][mutation]={'target':PARTS[0]}
                elif mutation=='transclude':unit['languages']['he'][0]['transclude']=PARTS[0]
                elif mutation=='order_reference':r['expanded_order']=[{'reference':{'target':PARTS[0]}}]
                elif mutation=='citation':unit['citations']={'he':[{'target':PARTS[0]}]}
                else:segment['fragments'][0]['quotations']=[{}]
                with self.assertRaises(ValueError):validate_redirection(r,'amidah_qedushah',PARTS)


class ControlledRedirectionTest(unittest.TestCase):
    def test_bilingual_conditioned_parts_keep_their_original_controls_and_baseline(self):
        identity = 'urn:x-opensiddur:text:prayer:example/part'
        source = dict(stem='source', urn='urn:x-opensiddur:text:siddur:example', title={'he':'Example'},
                      languages={lang: [dict(corresp=identity, paragraph=1,
                          conditions=[dict(type='opensiddur:rite', features={'frankfurt_am_main':False})],
                          condition_instruction='Regional instruction', condition_instruction_language='en',
                          fragments=[dict(scan='s2', printed_page='1', text='literal', page_start=False)])]
                          for lang in ['he','en']})
        readings = {'units':[source]}
        baseline = snapshot(readings)
        validate_redirection(readings, 'source', [identity])
        for segments in source['languages'].values():
            segments[0]['canonical'] = segments[0].pop('corresp')
        validate_baseline(readings, baseline)
        source['languages']['en'][0]['conditions'][0]['features']['frankfurt_am_main'] = True
        with self.assertRaisesRegex(ValueError, 'Accepted source witness'):
            validate_baseline(readings, baseline)

    def test_duplicate_identity_in_one_language_and_unmodeled_controls_fail(self):
        old = json.loads((BASELINE.parent/'marmorstein_qedushah_before_reuse.json').read_text())['unit']
        for mode in ['duplicate', 'marked', 'anchor']:
            with self.subTest(mode=mode):
                unit = deepcopy(old)
                segment = next(s for s in unit['languages']['he'] if s.get('corresp') == PARTS[0])
                if mode == 'duplicate': unit['languages']['he'].append(deepcopy(segment))
                else: segment[mode] = True
                with self.assertRaises(ValueError):
                    validate_redirection({'units':[unit]}, unit['stem'], [PARTS[0]])

    def test_speaker_controls_survive_redirection(self):
        identity = 'urn:x-opensiddur:text:prayer:example/part'
        for speaker in [{'abbr': 'ח׳', 'expan': 'חזן'}, {'label': 'Cantor', 'role': 'reader'}]:
            u = dict(stem='source', languages={'he': [dict(corresp=identity,
                speaker=speaker, speaker_before_reference=True,
                fragments=[dict(scan='s2', printed_page='1', text='words')])]})
            r = {'units': [u]}; baseline = snapshot(r)
            validate_redirection(r, 'source', [identity])
            segment = u['languages']['he'][0]
            segment['canonical'] = segment.pop('corresp')
            validate_baseline(r, baseline)
        for fields in [dict(speaker_before_reference=True),
                       dict(speaker={'abbr': 'x', 'expan': 'unknown'})]:
            u = dict(stem='source', languages={'he': [dict(corresp=identity,
                fragments=[dict(scan='s2', text='words')], **fields)]})
            with self.assertRaisesRegex(ValueError, 'speaker|Speaker'):
                validate_redirection({'units': [u]}, 'source', [identity])
