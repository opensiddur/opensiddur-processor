"""Reader contexts omit Elohai Netzor, retain the Temple prayer, and restore settings."""
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from lxml import etree as E

from opensiddur.exporter.compiler import CompilerProcessor
from opensiddur.exporter.conditional_settings import yaml_to_declaration_entries
from opensiddur.exporter.linear import get_linear_data, reset_linear_data
from opensiddur.importer.birnbaum_scan.build import (
    build_en,
    build_he,
    festival,
    festival_musaf,
    minchah,
    rosh_hashanah,
    rosh_hodesh_musaf,
    shabbat_amidah,
    shabbat_minchah,
    shabbat_musaf,
)
from opensiddur.importer.birnbaum_scan.build.common import PROJECT_EN, PROJECT_HE
from opensiddur.importer.siddur_expanded.xml import (
    NS,
    XID,
    Author,
    J,
    T,
    feature,
    parse_fragment,
    serialize,
)


class SyntheticPrayers(dict):
    def __missing__(self, key):
        self[key] = {'urn': 'urn:x-opensiddur:text:prayer:fixture/'+key}
        return self[key]


def meditation_fixture(body):
    """Keep each real builder's scope boundaries, substituting synthetic prayer leaves."""
    root = parse_fragment(body)
    opener, = [e for e in root.iter('{'+J+'}conditional')
               if e.get(XID, '').endswith('meditation')]
    fragment = E.Element('root')
    for e in root.iter():
        if e is opener or (e.tag == '{'+J+'}endConditional' and e.get('target') == '#'+opener.get(XID)):
            fragment.append(deepcopy(e))
        elif e.tag == '{'+J+'}transclude':
            target = e.get('target', '')
            if 'elohai_netzor' in target or target.endswith('/elohai'):
                E.SubElement(fragment, '{'+T+'}p').text = 'First meditation'
            elif 'yehi_ratzon' in target or target.endswith('/yehi'):
                E.SubElement(fragment, '{'+T+'}p').text = 'Temple prayer'
    assert len(fragment.findall('{'+T+'}p')) == 2
    return ''.join(serialize(e) for e in fragment)


class TestMeditations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = []
        for lang, project, weekday in [('he', PROJECT_HE, build_he), ('en', PROJECT_EN, build_en)]:
            leaves = SyntheticPrayers()
            with patch.object(weekday, 'BY_NAME', leaves):
                weekday_body = weekday.unit_body()
            bodies = [
                ('weekday morning', 'shaharit', weekday_body),
                ('weekday afternoon', 'minha', minchah.amidah(lang, leaves)),
                ('Shabbat morning', 'shaharit', shabbat_amidah.amidah(lang, leaves)),
                ('Shabbat afternoon', 'minha', shabbat_minchah.amidah(lang)),
            ]
            for label, service, units, name in [
                ('Shabbat Musaf', 'musaf', shabbat_musaf.units(project, leaves), 'shabbat_musaf_amidah'),
                ('festival', 'shaharit', festival.units(project), 'festival_amidah'),
                ('festival Musaf', 'musaf', festival_musaf.units(project), 'festival_musaf_amidah'),
                ('Rosh Chodesh Musaf', 'musaf', rosh_hodesh_musaf.units(project), 'rosh_chodesh_musaf_amidah'),
                ('Rosh Hashanah afternoon', 'minha', rosh_hashanah.units(project), 'rh_amidah'),
            ]:
                bodies.append((label, service, next(u['body'] for u in units if u['name'] == name)))
            cls.fixtures.extend((lang, label, service, meditation_fixture(body))
                                for label, service, body in bodies)

    def compile(self, body, service, repeated, minyan):
        author = Author()
        body = author.context(body, service, repeated)
        if repeated:
            body = author.gate(feature('quorum', 'minyan'), body)
        with tempfile.TemporaryDirectory() as temp:
            reset_linear_data()
            self.addCleanup(reset_linear_data)
            base = Path(temp)
            (base/'synthetic').mkdir()
            (base/'synthetic/index.xml').write_text(f'<root xmlns:tei="{T}" xmlns:j="{J}">'+body+'</root>')
            data = get_linear_data()
            data.xml_cache.base_path = base
            CompilerProcessor.load_init_settings(data, yaml_to_declaration_entries({
                'opensiddur:quorum': {'minyan': minyan},
            }))
            processor = CompilerProcessor('synthetic', 'index.xml')
            before = processor.get_active_setting('opensiddur:quorum', 'minyan')
            result = processor.process()
            self.assertEqual(processor.get_active_setting('opensiddur:quorum', 'minyan'), before)
            self.assertFalse(data.conditional_scope_stack)
            if repeated and minyan is None:
                self.assertEqual(len(result.xpath('.//j:conditional', namespaces=NS)), 1,
                                 'The outer minyan eligibility remains undecided.')
            return result.xpath('.//tei:p/text()', namespaces=NS)

    def test_silent_prayer_retains_both_meditations(self):
        for lang, label, service, body in self.fixtures:
            for minyan in [None, False, True]:
                with self.subTest(lang=lang, variant=label, minyan=minyan):
                    self.assertEqual(self.compile(body, service, False, minyan),
                                     ['First meditation', 'Temple prayer'])

    def test_repetition_omits_first_meditation_and_keeps_temple_prayer(self):
        for lang, label, service, body in self.fixtures:
            for minyan in [None, True]:
                with self.subTest(lang=lang, variant=label, minyan=minyan):
                    self.assertEqual(self.compile(body, service, True, minyan), ['Temple prayer'])

    def test_local_public_context_does_not_force_an_inapplicable_repetition(self):
        for lang, label, service, body in self.fixtures:
            with self.subTest(lang=lang, variant=label):
                self.assertEqual(self.compile(body, service, True, False), [])
