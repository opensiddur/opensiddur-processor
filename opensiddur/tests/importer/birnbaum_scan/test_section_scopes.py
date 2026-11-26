"""Whole-section gates govern headings and declarations, but never mixed text."""

import tempfile
import unittest
from pathlib import Path

from opensiddur.exporter.compiler import CompilerProcessor
from opensiddur.exporter.conditional_settings import yaml_to_declaration_entries
from opensiddur.exporter.linear import get_linear_data, reset_linear_data
from opensiddur.importer.birnbaum_scan.build.scopes import (
    TEI,
    J,
    scope_section_headings,
)


class TestSectionScopes(unittest.TestCase):
    def compile(self, body, minyan):
        reset_linear_data()
        self.addCleanup(reset_linear_data)
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / "synthetic").mkdir()
            get_linear_data().xml_cache.base_path = base
            CompilerProcessor.load_init_settings(get_linear_data(), yaml_to_declaration_entries({
                "opensiddur:quorum": {"minyan": minyan},
            }))
            (base / "synthetic" / "index.xml").write_text(
                f'<root xmlns:tei="{TEI}" xmlns:j="{J}"><tei:text>'
                + scope_section_headings(body) + '</tei:text></root>')
            output = CompilerProcessor("synthetic", "index.xml").process()
            self.assertFalse(get_linear_data().conditional_scope_stack)
            return " ".join(output.itertext())

    def test_false_gate_omits_heading_and_does_not_enter_local_context(self):
        body = '''<tei:div><tei:head>Public prayer</tei:head>
          <j:declare xml:id="local"><tei:fs type="opensiddur:recitation">
            <tei:f name="repetition"><tei:binary value="true"/></tei:f>
          </tei:fs></j:declare>
          <j:conditional xml:id="public"><tei:fs type="opensiddur:quorum">
            <tei:f name="minyan"><tei:binary value="true"/></tei:f>
          </tei:fs></j:conditional><tei:p>Congregational words</tei:p>
          <j:endConditional target="#public"/><j:endDeclare target="#local"/>
        </tei:div><tei:p>Following passage</tei:p>'''
        output = self.compile(body, False)
        self.assertNotIn("Public prayer", output)
        self.assertNotIn("Congregational words", output)
        self.assertIn("Following passage", output)
        self.assertFalse(any(entry.declare_id.endswith("local")
                             for entry in get_linear_data().conditional_settings))
        output = self.compile(body, True)
        self.assertIn("Public prayer", output)
        self.assertIn("Congregational words", output)
        self.assertIn("Following passage", output)

    def test_mixed_section_keeps_its_heading_and_unconditional_text(self):
        body = '''<tei:div><tei:head>Mixed service</tei:head><tei:p>Common words</tei:p>
          <j:conditional xml:id="public"><tei:fs type="opensiddur:quorum">
            <tei:f name="minyan"><tei:binary value="true"/></tei:f>
          </tei:fs></j:conditional><tei:p>Public words</tei:p>
          <j:endConditional target="#public"/></tei:div>'''
        output = self.compile(body, False)
        self.assertIn("Mixed service", output)
        self.assertIn("Common words", output)
        self.assertNotIn("Public words", output)

    def test_unwrapped_words_prevent_whole_section_reclassification(self):
        body = '''<tei:div><tei:head>Mixed service</tei:head>Unwrapped common words
          <j:conditional xml:id="public"><tei:fs type="opensiddur:quorum">
            <tei:f name="minyan"><tei:binary value="true"/></tei:f>
          </tei:fs></j:conditional><tei:p>Public words</tei:p>
          <j:endConditional target="#public"/></tei:div>'''
        self.assertEqual(scope_section_headings(body), body)
        self.assertIn("Unwrapped common words", self.compile(body, False))
