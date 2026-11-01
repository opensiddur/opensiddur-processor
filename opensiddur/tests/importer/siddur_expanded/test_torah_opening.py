"""Simchat Torah continues from the hakafot rather than restarting the opening."""
import tempfile
import unittest
from pathlib import Path

from opensiddur.exporter.compiler import CompilerProcessor
from opensiddur.exporter.conditional_settings import yaml_to_declaration_entries
from opensiddur.exporter.linear import get_linear_data, reset_linear_data
from opensiddur.importer.siddur_expanded.build import Builder
from opensiddur.importer.siddur_expanded.xml import Author, T, J, NS


class TestMorningTorahOpening(unittest.TestCase):
    def compile_opening(self, declarations):
        builder = Builder.__new__(Builder)
        builder.a = Author()
        # Synthetic prayer leaves: only their order and eligibility are tested.
        def source(urn):
            name = {'siddur:shabbat/shacharit/torah/opening': 'ordinary-opening',
                    'siddur:chol/shacharit/torah_intro': 'weekday-opening'}.get(urn, urn.rsplit('/', 1)[-1].rsplit(':', 1)[-1])
            return '<tei:p>'+name+'</tei:p>'
        builder.s = source
        body = builder.morning_torah_opening()
        with tempfile.TemporaryDirectory() as temp:
            reset_linear_data()
            self.addCleanup(reset_linear_data)
            base = Path(temp)
            (base/'synthetic').mkdir()
            (base/'synthetic/index.xml').write_text(
                f'<root xmlns:tei="{T}" xmlns:j="{J}">'+body+'</root>')
            data = get_linear_data()
            data.xml_cache.base_path = base
            CompilerProcessor.load_init_settings(data, yaml_to_declaration_entries(declarations))
            result = CompilerProcessor('synthetic', 'index.xml').process()
            self.assertFalse(data.conditional_scope_stack)
            return result.xpath('.//tei:p/text()', namespaces=NS)

    def settings(self, israel=False, shabbat=False, festival=False, shemini=0):
        return {'opensiddur:israel': {'is-israel': israel},
                'opensiddur:holiday-aggregate': {'shabbat': shabbat, 'yom-tov': festival},
                'opensiddur:holiday': {'shmini-atzeret': shemini}}

    def test_simchat_torah_in_each_locale_starts_with_lekha(self):
        for israel, day, shabbat in [(True, 1, True), (True, 1, False), (False, 2, False), (False, 2, True)]:
            with self.subTest(israel=israel, day=day, shabbat=shabbat):
                result = self.compile_opening(self.settings(israel, shabbat, True, day))
                self.assertEqual(result, ['lekha_adonai', 'al_hakol', 'hu_yerachem', 'vayaazor'])

    def test_shemini_atzeret_in_diaspora_keeps_the_ordinary_opening(self):
        for shabbat in [False, True]:
            with self.subTest(shabbat=shabbat):
                self.assertEqual(self.compile_opening(self.settings(False, shabbat, True, 1)),
                                 ['ordinary-opening'])

    def test_other_festivals_and_shabbat_keep_the_ordinary_opening(self):
        for shabbat, festival in [(True, False), (False, True), (True, True)]:
            with self.subTest(shabbat=shabbat, festival=festival):
                self.assertEqual(self.compile_opening(self.settings(False, shabbat, festival)),
                                 ['ordinary-opening'])

    def test_weekday_opening_is_unchanged(self):
        self.assertEqual(self.compile_opening(self.settings()),
                         ['weekday-opening', 'vayehi_binsoa', 'berikh_shemeh', 'gaddelu',
                          'lekha_adonai', 'hu_yerachem', 'vetiggaleh'])

    def test_undated_output_keeps_both_major_day_alternatives(self):
        result = self.compile_opening({})
        self.assertIn('ordinary-opening', result)
        self.assertIn('lekha_adonai', result)
