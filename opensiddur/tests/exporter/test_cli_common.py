"""What the output stages share: their arguments, their settings and the tree preparation."""

import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lxml import etree
from pydantic import ValidationError

from opensiddur.common.constants import PROJECT_DIRECTORY
from opensiddur.exporter import typography as typography_module
from opensiddur.exporter.cli_common import (
    COLOPHON_BACK,
    SettingsError,
    add_settings_arguments,
    load_output_settings,
    prepare_compiled_tree,
    relocate_colophons,
)
from opensiddur.exporter.settings import SettingsYaml, read_settings
from opensiddur.exporter.typography import PaperType, ParallelLayout, TypographyConfig

P = "http://jewishliturgy.org/ns/processing"
J = "http://jewishliturgy.org/ns/jlptei/2"


def _no_fontconfig():
    """Mock out the installed-font lookup: whether this machine has a font is not under test."""
    return patch.object(typography_module, "_installed_font_families", return_value=None)


class TestLoadOutputSettings(unittest.TestCase):
    """One policy for every output stage: a settings file that is not valid settings is an
    error, as it is to the compiler. Only the projects it names are not checked."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_dir = Path(self.temp_dir.name)

    def _settings(self, text: str) -> Path:
        path = self.test_dir / "settings.yaml"
        path.write_text(text, encoding="utf-8")
        return path

    def _load(self, path):
        return load_output_settings(path, resolve_fonts=True)

    # ── Files that cannot be read as settings ───────────────────────────────

    def test_no_settings_file_is_the_defaults(self):
        self.assertEqual(self._load(None), SettingsYaml())

    def test_a_missing_file_is_an_error(self):
        with self.assertRaises(SettingsError) as caught:
            self._load(self.test_dir / "no-such.yaml")
        self.assertIn("no-such.yaml", str(caught.exception))

    def test_unparseable_yaml_is_an_error(self):
        with self.assertRaises(SettingsError):
            self._load(self._settings(":\n: not yaml"))

    def test_a_document_that_is_not_a_mapping_is_an_error(self):
        with self.assertRaises(SettingsError):
            self._load(self._settings("- a\n- b\n"))

    def test_an_empty_file_is_an_error(self):
        with self.assertRaises(SettingsError):
            self._load(self._settings(""))

    # ── Invalid settings ────────────────────────────────────────────────────

    def test_invalid_typography_is_an_error_not_a_silent_default(self):
        """Substituting defaults for a mistyped running-head code would produce a
        PDF missing what was asked for, explained only by a warning on stderr."""
        path = self._settings('typography:\n  page_header:\n    all:\n      left: "{no-such-code}"\n')
        with self.assertRaises(ValidationError) as caught:
            self._load(path)
        self.assertIn("Unknown header/footer code", str(caught.exception))

    def test_an_invalid_paper_names_the_setting(self):
        with self.assertRaises(ValidationError) as caught:
            self._load(self._settings("typography:\n  page:\n    paper: tabloid\n"))
        self.assertIn("paper", str(caught.exception))

    def test_all_combined_with_odd_is_an_error(self):
        path = self._settings(
            'typography:\n  page_footer:\n    all:\n      center: "{page}"\n'
            '    odd:\n      left: "{page}"\n')
        with self.assertRaises(ValidationError):
            self._load(path)

    def test_an_unknown_key_outside_typography_is_an_error(self):
        with self.assertRaises(ValidationError) as caught:
            self._load(self._settings("electronic:\n  colums: both\n"))
        self.assertIn("colums", str(caught.exception))

    def test_an_unknown_top_level_key_is_an_error(self):
        with self.assertRaises(ValidationError):
            self._load(self._settings("typograhpy: {}\n"))

    def test_an_unregistered_declaration_is_an_error(self):
        with self.assertRaises(ValidationError):
            self._load(self._settings("declarations:\n  opensiddur:no-such-type:\n    x: true\n"))

    # ── What is not checked ─────────────────────────────────────────────────

    def test_projects_it_names_need_not_exist(self):
        """An output stage reads the compiled file; the compiler checked the projects."""
        path = self._settings(
            "book:\n  project: a-project-that-does-not-exist\n  file_name: index.xml\n"
            "priority:\n  transclusion: [a-project-that-does-not-exist]\n"
            "  instructions: [another-missing-project]\n"
            "annotations: [a-missing-annotation-project]\n"
            "parallel:\n  projects: [a-missing-parallel-project]\n"
            "typography:\n  page:\n    paper: a5paper\n")
        settings = self._load(path)
        self.assertEqual(settings.book.project, "a-project-that-does-not-exist")
        self.assertEqual(settings.typography.page.paper, PaperType.A5PAPER)
        # The compiler still checks them.
        with self.assertRaises(ValidationError) as caught:
            read_settings(path, project_directory=self.test_dir, resolve_fonts=False)
        self.assertIn("does not exist", str(caught.exception))

    def test_fonts_are_not_resolved_for_a_stage_that_selects_none(self):
        path = self._settings("typography:\n  fonts:\n    hebrew: [No Such Font At All]\n")
        with patch.object(typography_module, "_installed_font_families",
                          return_value={"freeserif"}):
            with self.assertRaises(ValidationError):
                load_output_settings(path, resolve_fonts=True)
            settings = load_output_settings(path, resolve_fonts=False)
        self.assertEqual(settings.typography.fonts["hebrew"].names, ["No Such Font At All"])

    # ── The typography section ──────────────────────────────────────────────

    def test_a_file_of_typography_alone_is_valid(self):
        settings = self._load(self._settings("typography:\n  page:\n    paper: a5paper\n"))
        self.assertEqual(settings.typography.page.paper, PaperType.A5PAPER)
        self.assertEqual(settings.priority.transclusion, [])

    def test_reads_typography_section(self):
        path = self._settings("""
priority:
  transclusion: [p]
  instructions: []
typography:
  fonts:
    hebrew: [Ezra SIL, FreeSerif]
    latin: TeX Gyre Pagella
  parallel:
    layout: pairs
  page:
    paper: letterpaper
    base_font_size: 12pt
  table_of_contents:
    enabled: true
    depth: 2
""")
        with _no_fontconfig():
            typography = self._load(path).typography
        self.assertEqual(typography.fonts["hebrew"].names, ["Ezra SIL", "FreeSerif"])
        self.assertEqual(typography.fonts["latin"].names, ["TeX Gyre Pagella"])
        self.assertEqual(typography.parallel.layout, ParallelLayout.PAIRS)
        self.assertEqual(typography.page.paper, PaperType.LETTERPAPER)
        self.assertEqual(typography.page.base_font_size, "12pt")
        self.assertTrue(typography.table_of_contents.enabled)
        self.assertEqual(typography.table_of_contents.depth, 2)

    def test_defaults_when_typography_section_missing(self):
        path = self._settings("priority:\n  transclusion: [p]\n  instructions: []\n")
        self.assertEqual(self._load(path).typography, TypographyConfig())

    def test_reads_running_head_settings(self):
        path = self._settings("""
typography:
  page_header:
    odd:
      left: "{book-title}"
      right: {text: "{page}", language: en}
  page_footer:
    all:
      center: "{page}"
""")
        typography = self._load(path).typography
        self.assertEqual(typography.page_header.odd.left.text, "{book-title}")
        self.assertEqual(typography.page_header.odd.right.language, "en")
        self.assertIsNone(typography.page_header.even)
        self.assertEqual(typography.page_footer.all.center.text, "{page}")


class TestAddSettingsArguments(unittest.TestCase):

    def _parser(self):
        parser = argparse.ArgumentParser()
        add_settings_arguments(parser, "help")
        return parser

    def test_defaults(self):
        args = self._parser().parse_args([])
        self.assertIsNone(args.settings_file)
        self.assertEqual(args.project_directory, PROJECT_DIRECTORY)

    def test_both_given(self):
        args = self._parser().parse_args(["-s", "x.yaml", "--project-directory", "projects"])
        self.assertEqual(args.settings_file, Path("x.yaml"))
        self.assertEqual(args.project_directory, Path("projects"))
        args = self._parser().parse_args(["--settings", "y.yaml"])
        self.assertEqual(args.settings_file, Path("y.yaml"))


class TestPrepareCompiledTree(unittest.TestCase):

    def _document(self):
        return etree.fromstring(f'''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
            xmlns:p="{P}" xmlns:j="{J}" p:project="he">
            <tei:text><tei:body>
              <tei:note type="instruction">See page <tei:ref type="page" target="urn:prayer@he"/></tei:note>
              <tei:div corresp="urn:prayer"><tei:p>First</tei:p></tei:div>
              <tei:div corresp="urn:prayer"><tei:p>Again</tei:p></tei:div>
              <j:conditional xml:id="c1"/><tei:p>Gated</tei:p><j:endConditional target="#c1"/>
              <j:conditional xml:id="c2" type="marked"/><tei:p>Marked</tei:p><j:endConditional target="#c2"/>
            </tei:body></tei:text></tei:TEI>''')

    def _anchors(self, root):
        return root.xpath('//*[local-name()="anchor"]')

    def test_page_references_are_resolved(self):
        root = self._document()
        prepare_compiled_tree(root)
        anchors = self._anchors(root)
        self.assertEqual(len(anchors), 1)
        [ref] = root.xpath('//*[local-name()="ref"]')
        self.assertEqual(ref.get("target"), anchors[0].get("n"))

    def test_every_occurrence(self):
        root = self._document()
        prepare_compiled_tree(root, every_occurrence=True)
        self.assertEqual(len(self._anchors(root)), 2)

    def test_both_markers_of_each_scope_say_whether_it_is_silent(self):
        root = self._document()
        prepare_compiled_tree(root)
        silent = f"{{{P}}}silent"
        openers = root.findall(f".//{{{J}}}conditional")
        closers = root.findall(f".//{{{J}}}endConditional")
        self.assertEqual([e.get(silent) for e in openers], ["true", "false"])
        self.assertEqual([e.get(silent) for e in closers], ["true", "false"])


class TestRelocateColophons(unittest.TestCase):
    """A digital edition's colophon divisions leave the front matter for the end."""

    def _document(self, front: str):
        return etree.fromstring(f'''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
            xmlns:p="{P}" xmlns:j="{J}"><tei:text><tei:front>{front}</tei:front>
            <tei:body><tei:p>Text</tei:p></tei:body></tei:text></tei:TEI>''')

    def _names(self, element):
        return [etree.QName(child).localname + (f"[{child.get('type')}]" if child.get("type") else "")
                for child in element]

    def test_a_gated_colophon_moves_with_its_markers(self):
        root = self._document(
            '<tei:div type="preface"><tei:p>Preface</tei:p></tei:div>'
            '<j:conditional xml:id="c1"/><tei:div type="colophon"><tei:p>Ours</tei:p></tei:div>'
            '<j:endConditional target="#c1"/>')
        back = relocate_colophons(root)
        text = root.find("{http://www.tei-c.org/ns/1.0}text")
        self.assertEqual(self._names(text), ["front", "body", "back"])
        self.assertEqual(back.get(COLOPHON_BACK), "true")
        self.assertEqual(self._names(back), ["conditional", "div[colophon]", "endConditional"])
        self.assertEqual(self._names(text[0]), ["div[preface]"])

    def test_front_matter_left_empty_is_removed(self):
        root = self._document('<tei:div type="colophon"><tei:p>Ours</tei:p></tei:div>')
        relocate_colophons(root)
        self.assertEqual(self._names(root[0]), ["body", "back"])

    def test_without_colophons_nothing_changes(self):
        root = self._document('<tei:div type="preface"><tei:p>Preface</tei:p></tei:div>')
        before = etree.tostring(root)
        self.assertIsNone(relocate_colophons(root))
        self.assertEqual(etree.tostring(root), before)

    def test_one_gate_around_two_colophons_moves_whole(self):
        root = self._document(
            '<j:conditional xml:id="c1"/><tei:div type="colophon"><tei:p>A</tei:p></tei:div>'
            '<tei:div type="colophon"><tei:p>B</tei:p></tei:div><j:endConditional target="#c1"/>')
        back = relocate_colophons(root)
        self.assertEqual(self._names(back), ["conditional", "div[colophon]", "div[colophon]", "endConditional"])

    def test_a_colophon_leaving_a_transclusion_keeps_its_language_and_project(self):
        root = self._document(
            '<p:transclude xml:lang="en" p:project="osp"><tei:div type="colophon"><tei:p>A</tei:p>'
            '</tei:div></p:transclude>')
        back = relocate_colophons(root)
        div = back[0]
        self.assertEqual(div.get("{http://www.w3.org/XML/1998/namespace}lang"), "en")
        self.assertEqual(div.get(f"{{{P}}}project"), "osp")
        # The emptied wrapper, and the front matter with it, are gone.
        self.assertEqual(self._names(root[0]), ["body", "back"])

    def test_every_stage_relocates_them(self):
        root = self._document('<tei:div type="colophon"><tei:p>Ours</tei:p></tei:div>')
        prepare_compiled_tree(root)
        self.assertEqual(self._names(root[0]), ["body", "back"])


if __name__ == "__main__":
    unittest.main()
