"""The fast-day Torah direction must not appear in ordinary weekday Minchah."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lxml import etree

from opensiddur.exporter.compiler import CompilerProcessor
from opensiddur.exporter.conditional_settings import yaml_to_declaration_entries
from opensiddur.exporter.linear import get_linear_data, reset_linear_data
from opensiddur.importer.birnbaum_scan.build import minchah
from opensiddur.importer.birnbaum_scan.build.common import PROJECT_EN, PROJECT_HE

NS = {'tei': 'http://www.tei-c.org/ns/1.0', 'j': 'http://jewishliturgy.org/ns/jlptei/2'}


class TestMinchahTorahRubric(unittest.TestCase):
    def test_direction_is_kept_only_for_minor_fasts_or_an_undated_book(self):
        for project in (PROJECT_HE, PROJECT_EN):
            with patch.object(minchah, 'amidah', return_value=''), patch.object(minchah, 'avinu', return_value=''):
                opening = next(u for u in minchah.units(project, {})
                               if u['name'] == 'chol_minchah_opening')['body']
            tree = etree.fromstring((f'<root xmlns:tei="{NS["tei"]}" xmlns:j="{NS["j"]}">'
                                     + opening + '</root>').encode())
            # Synthetic prayer leaves: only the direction and its scope are at issue.
            for transclusion in tree.xpath('.//j:transclude', namespaces=NS):
                transclusion.getparent().remove(transclusion)
            for fast, expected in ((False, False), (True, True), (None, True)):
                with self.subTest(project=project, minor_fast=fast), tempfile.TemporaryDirectory() as temp:
                    reset_linear_data()
                    self.addCleanup(reset_linear_data)
                    base = Path(temp)
                    (base / 'synthetic').mkdir()
                    (base / 'synthetic/index.xml').write_bytes(etree.tostring(tree))
                    data = get_linear_data()
                    data.xml_cache.base_path = base
                    declarations = {'opensiddur:quorum': {'minyan': False}}
                    if fast is not None:
                        declarations['opensiddur:holiday-aggregate'] = {'minor-fast': fast}
                    CompilerProcessor.load_init_settings(data, yaml_to_declaration_entries(declarations))
                    output = CompilerProcessor('synthetic', 'index.xml').process()
                    self.assertEqual(minchah.TORAH_RUBRIC in ''.join(output.itertext()), expected)
                    self.assertFalse(data.conditional_scope_stack)
