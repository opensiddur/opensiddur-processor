"""Exercise the generated service spine against small synthetic source editions."""
from pathlib import Path
from itertools import count
import tempfile
import unittest
from unittest.mock import patch

from lxml import etree as E

from opensiddur.exporter.compiler import CompilerProcessor
from opensiddur.exporter.conditional_settings import yaml_to_declaration_entries
from opensiddur.exporter.linear import get_linear_data, reset_linear_data
from opensiddur.importer.humash.refs import ReadingSpan, VerseRef, UNIT_ALIYAH
from opensiddur.importer.siddur_expanded import build as edition
from opensiddur.importer.siddur_expanded.readings import Entry, SHABBAT, FAST
from opensiddur.importer.siddur_expanded.xml import (
    T, J, NS, TEXT, ROOT, XID, PROJECT, Author, feature, transclude, parse_fragment,
)


class TestExpandedBuild(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        # Only containers that need replacement/omission have structure. All
        # other prayers remain opaque references, just as real prayer leaves do.
        sources = {
            'siddur:siddur': Author().gate(feature('holiday', 'rosh-hashana', 1),
                transclude(TEXT+'siddur:rosh_hashanah/tashlikh')),
            'siddur:all/shacharit/birkhot_hashachar':
                '<tei:head xml:lang="he">מסכת ברכות יא, א; ס, ב</tei:head>'
                '<tei:head xml:lang="en">Talmud Berakhoth 11a; 60b</tei:head>'
                + transclude(TEXT+'prayer:fixture/morning_blessings'),
            'siddur:shabbat/shacharit/torah/reading': ''.join(transclude(TEXT+u) for u in [
                'siddur:chol/shacharit/torah/barekhu',
                'siddur:chol/shacharit/torah/asher_bachar',
                'prayer:birkhot_hatorah/asher_natan', 'prayer:kaddish/chatzi']),
            'siddur:shabbat/shacharit/torah/haftarah':
                transclude(TEXT+'prayer:birkhot_haftarah/after'),
            'siddur:shabbat/minchah/torah': ''.join(transclude(TEXT+u) for u in [
                'siddur:chol/shacharit/torah/asher_bachar',
                'siddur:shabbat/minchah/torah/vezot_hatorah',
                'siddur:shabbat/minchah/torah/uvenuchoh']),
            'siddur:chol/shacharit/conclusion': ''.join(transclude(TEXT+u) for u in [
                'siddur:chol/shacharit/conclusion/ashrei',
                'siddur:chol/shacharit/conclusion/aleinu',
                'prayer:kaddish/yatom', 'siddur:chol/shacharit/conclusion/al_tira']),
            'siddur:shabbat/musaf': '<tei:head>Printed Musaf heading</tei:head>'
                + transclude(TEXT+'siddur:shabbat/musaf/amidah')
                + transclude(TEXT+'prayer:fixture/major_conclusion'),
            'siddur:chol/minchah': ''.join(transclude(TEXT+u) for u in [
                'siddur:chol/minchah/opening', 'siddur:chol/minchah/amidah']),
            'siddur:shabbat/minchah': ''.join(transclude(TEXT+u) for u in [
                'siddur:shabbat/minchah/torah', 'siddur:shabbat/minchah/amidah',
                'siddur:regalim/amidah']),
            'siddur:chol/arvit': transclude(TEXT+'siddur:chol/arvit/amidah')
                + transclude(TEXT+'siddur:chol/arvit/conclusion'),
            'siddur:shabbat/arvit': transclude(TEXT+'siddur:shabbat/arvit/amidah')
                + transclude(TEXT+'siddur:shabbat/arvit/conclusion'),
            'siddur:shabbat/conclusion': transclude(TEXT+'siddur:chol/arvit/amidah'),
            'siddur:meals': transclude(TEXT+'prayer:fixture/meal'),
        }
        directory = self.base/'hasiddur_hashalem-birnbaum-1949-he'
        directory.mkdir()
        directory.joinpath('index.xml').write_text(
            f'<tei:TEI xmlns:tei="{T}" xmlns:j="{J}"><tei:text><tei:body>'
            + ''.join(f'<tei:div corresp="{TEXT+urn}">{body}</tei:div>'
                      for urn, body in sources.items())
            + '</tei:body></tei:text></tei:TEI>')
        span = ReadingSpan(UNIT_ALIYAH, '1', VerseRef('genesis', 1, 1), VerseRef('genesis', 1, 5))
        entries = [Entry('morning_fixture', 'Morning fixture', SHABBAT, torah=[span],
                         haftarah=TEXT+'bible:haftarah/fixture'),
                   Entry('afternoon_fixture', 'Afternoon fixture', FAST, 'afternoon', torah=[span],
                         haftarah=TEXT+'bible:haftarah/fixture')]
        self.manifest = patch.object(edition, 'manifest', return_value=entries)
        self.manifest.start()
        self.addCleanup(self.manifest.stop)
        self.builder = edition.build(self.base, self.base/'sources')
        self.documents = {p.stem: E.parse(str(p)).getroot()
                          for p in (self.base/PROJECT).glob('*.xml')}

    def compile_service(self, module, *, service='shaharit', major=False, hallel=False, quorum=True):
        root = E.fromstring(E.tostring(self.documents[module]))
        occurrences = count(1)
        # Resolve only structure; synthetic prayer leaves identify which source
        # units survive the real compiler's predicates and scoped declarations.
        def expand(parent):
            for node in list(parent):
                if node.tag == '{'+J+'}transclude':
                    target = node.get('target')
                    if target.startswith(ROOT+'/'):
                        name = target.rsplit('/', 1)[-1]
                        replacement = E.fromstring(E.tostring(self.documents[name].find('.//tei:body', NS)))
                        prefix = 'fixture_occurrence_'+str(next(occurrences))+'_'
                        ids = {e.get(XID) for e in replacement.iter() if e.get(XID)}
                        for element in replacement.iter():
                            if element.get(XID):
                                element.set(XID, prefix+element.get(XID))
                            target_id = element.get('target', '')
                            if target_id.startswith('#') and target_id[1:] in ids:
                                element.set('target', '#'+prefix+target_id[1:])
                        expand(replacement)
                    else:
                        replacement = E.Element('{'+T+'}p')
                        replacement.text = target.removeprefix(TEXT)
                    parent.replace(node, replacement)
                else:
                    expand(node)
        expand(root)
        fixture = self.base/'compiled_fixture'
        fixture.mkdir(exist_ok=True)
        fixture.joinpath('index.xml').write_bytes(E.tostring(root))
        reset_linear_data()
        self.addCleanup(reset_linear_data)
        data = get_linear_data()
        data.xml_cache.base_path = self.base
        settings = {
            'opensiddur:service-time': {n: n == service for n in
                ['shaharit', 'minha', 'maariv', 'musaf', 'neila', 'slihot']},
            'opensiddur:holiday-aggregate': {'shabbat': major, 'yom-tov': False,
                'chol-hamoed': False, 'minor-fast': False, 'motzaei-shabbat': False},
            'opensiddur:holiday': {n: 0 for n in ['rosh-hashana', 'yom-kippur',
                'pesah', 'shavuot', 'sukkot', 'shmini-atzeret', 'rosh-hodesh',
                'hanukkah', 'tisha-bav', 'purim-observed']},
            'opensiddur:quorum': {'minyan': quorum},
            'opensiddur:hallel': {'recite': hallel},
        }
        CompilerProcessor.load_init_settings(data, yaml_to_declaration_entries(settings))
        result = CompilerProcessor('compiled_fixture', 'index.xml').process()
        self.assertFalse(data.conditional_scope_stack)
        return result.xpath('.//tei:p/text()', namespaces=NS)

    def test_every_module_has_resolvable_structure_and_balanced_occurrence_scopes(self):
        self.assertEqual(set(self.documents), {'index', 'morning', 'afternoon', 'evening',
            'musaf', 'occasions', 'appendices', *(
                f'readings_{service}_{slot}' for service in ['morning', 'afternoon']
                for slot in ['torah', 'maftir', 'haftarah'])})
        for name, root in self.documents.items():
            with self.subTest(module=name):
                ids = root.xpath('//@xml:id', namespaces=NS)
                self.assertEqual(len(ids), len(set(ids)))
                stack = []
                for node in root.iter():
                    if node.tag in ['{'+J+'}conditional', '{'+J+'}declare']:
                        stack.append((node.tag, node.get(XID)))
                    elif node.tag in ['{'+J+'}endConditional', '{'+J+'}endDeclare']:
                        opening, ident = stack.pop()
                        self.assertEqual(node.get('target'), '#'+ident)
                        self.assertEqual(node.tag, opening.replace('}conditional', '}endConditional')
                                         .replace('}declare', '}endDeclare'))
                    elif node.tag == '{'+J+'}transclude' and node.get('target').startswith(ROOT+'/'):
                        self.assertIn(node.get('target').rsplit('/', 1)[-1], self.documents)
                self.assertFalse(stack)
        self.assertIn('Morning and Torah blessings', ''.join(self.documents['morning'].itertext()))
        self.assertNotIn('Printed Musaf heading', ''.join(self.documents['morning'].itertext()))
        self.assertIn('prayer:fixture/meal', self.compile_service('appendices'))

    def test_morning_places_hallel_before_readings_and_conclusions_after_musaf(self):
        prayers = self.compile_service('morning', major=True, hallel=True)
        self.assertLess(prayers.index('siddur:hallel'), prayers.index('bible:genesis/1/1-1/5'))
        self.assertLess(prayers.index('bible:genesis/1/1-1/5'), prayers.index('siddur:shabbat/musaf/amidah'))
        self.assertLess(prayers.index('siddur:shabbat/musaf/amidah'), prayers.index('prayer:fixture/major_conclusion'))
        self.assertEqual(prayers.count('siddur:shabbat/musaf/amidah'), 2)
        self.assertNotIn('siddur:chol/shacharit/amidah', prayers)

    def test_weekday_without_quorum_keeps_one_silent_amidah_and_one_aleinu(self):
        prayers = self.compile_service('morning', quorum=False)
        self.assertEqual(prayers.count('siddur:chol/shacharit/amidah'), 1)
        self.assertEqual(prayers.count('siddur:chol/shacharit/conclusion/aleinu'), 1)
        self.assertNotIn('siddur:hallel', prayers)
        self.assertNotIn('bible:genesis/1/1-1/5', prayers)
        self.assertNotIn('siddur:shabbat/musaf/amidah', prayers)

    def test_services_are_selected_before_local_context_is_entered(self):
        for module, service, amidah, count in [
            ('afternoon', 'minha', 'siddur:chol/minchah/amidah', 2),
            ('evening', 'maariv', 'siddur:chol/arvit/amidah', 1),
            ('musaf', 'musaf', 'siddur:shabbat/musaf/amidah', 2),
        ]:
            with self.subTest(module=module):
                prayers = self.compile_service(module, service=service, major=module == 'musaf')
                self.assertEqual(prayers.count(amidah), count)
                wrong = self.compile_service(module, service='shaharit', major=True)
                self.assertNotIn(amidah, wrong)

    def test_rebuild_does_not_rewrite_identical_files(self):
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in (self.base/PROJECT).glob('*.xml')}
        edition.build(self.base, self.base/'sources')
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})


class TestBlessingLabels(unittest.TestCase):
    def test_citation_pair_is_required_and_unrelated_headings_are_preserved(self):
        root = parse_fragment('<tei:div><tei:head>Other title</tei:head></tei:div>')
        self.assertEqual(edition.label_morning_blessings(root), 0)
        self.assertEqual(root[0][0].text, 'Other title')
        root = parse_fragment('<tei:div><tei:head>Talmud Berakhoth 11a; 60b</tei:head></tei:div>')
        with self.assertRaisesRegex(ValueError, 'bilingual morning-blessings citation'):
            edition.label_morning_blessings(root)
