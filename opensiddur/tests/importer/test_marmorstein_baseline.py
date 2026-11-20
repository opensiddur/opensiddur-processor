"""Existing acceptance is fixed before new identities and pointers are introduced."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from opensiddur.common.constants import SOURCETEXTS_ROOT
from opensiddur.importer.marmorstein_rosh_hashanah_1 import BOOK
from opensiddur.importer.marmorstein_rosh_hashanah_1.baseline import validate_baseline, validate_redirection, snapshot

BASELINE=Path(__file__).parent/'fixtures/marmorstein_accepted_660.json'
PARTS=['urn:x-opensiddur:text:prayer:amidah/qedushah/'+x
       for x in ['qadosh','barukh_kevod','uvedivrei','ledor_vador']]


def accepted_readings():
    return json.loads((SOURCETEXTS_ROOT/BOOK/'readings.json').read_text())


class LiteralBaselineTest(unittest.TestCase):
    def test_all660_literal_witnesses_and_protected_raw_fields_stay_accepted(self):
        baseline=json.loads(BASELINE.read_text())
        self.assertEqual(sum(len(x['literal_sha256'])for x in baseline.values()),660)
        validate_baseline(accepted_readings(),baseline)

    def test_frozen_qedushah_fixture_has_accepted_provenance(self):
        unit=json.loads((BASELINE.parent/'marmorstein_qedushah_before_reuse.json').read_text())['unit']
        self.assertEqual(snapshot({'units':[unit]})['amidah_qedushah'],
                         json.loads(BASELINE.read_text())['amidah_qedushah'])

    def test_integrated_source_baseline_matches_fixed_importer_fixture(self):
        readings=accepted_readings()
        if any(u.get('canonical_parts') for u in readings['units']):
            self.assertIn('accepted_literal_baseline',readings)
            path=SOURCETEXTS_ROOT/BOOK/readings['accepted_literal_baseline']
            self.assertEqual(json.loads(path.read_text()),json.loads(BASELINE.read_text()))

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
