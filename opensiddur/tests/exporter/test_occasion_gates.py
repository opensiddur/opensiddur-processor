"""An occasion's gate around a section, compiled end to end (opensiddur-processor#228).

A running order gates each section said only on some days. A compile dated to another day
leaves the section out; one with no date keeps it, and prints it with nothing around it, the
gate being a direction to the processor rather than to the reader.
"""

import tempfile
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.exporter.compiler import CompilerProcessor
from opensiddur.exporter.conditional_markers import mark_silent_scopes
from opensiddur.exporter.conditional_settings import yaml_to_declaration_entries
from opensiddur.exporter.constants import JLPTEI_NAMESPACE, PROCESSING_NAMESPACE, TEI_NS
from opensiddur.exporter.linear import get_linear_data, reset_linear_data
from opensiddur.importer.util.occasion import aggregate, gated, none_of
from opensiddur.tests.exporter.stylesheet_helpers import transform

SHABBAT = aggregate("shabbat")
WEEKDAY = none_of(SHABBAT, aggregate("yom-tov"))

RUNNING_ORDER = (
    gated("weekday", WEEKDAY, "<tei:div><tei:p>Weekday service</tei:p></tei:div>")
    + gated("sabbath", SHABBAT, "<tei:div><tei:p>Sabbath service</tei:p></tei:div>")
    + "<tei:div><tei:p>Said every day</tei:p></tei:div>"
)


class TestAGatedRunningOrder(unittest.TestCase):

    def setUp(self):
        reset_linear_data()
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        base = Path(temp_dir.name)
        (base / "book").mkdir()
        (base / "book" / "index.xml").write_text(
            f'<tei:TEI xmlns:tei="{TEI_NS}" xmlns:j="{JLPTEI_NAMESPACE}" xml:lang="en">'
            f"<tei:text><tei:body>{RUNNING_ORDER}</tei:body></tei:text></tei:TEI>",
            encoding="utf-8")
        get_linear_data().xml_cache.base_path = base

    def _compile(self, date=None) -> etree.ElementBase:
        if date is not None:
            CompilerProcessor.load_init_settings(
                get_linear_data(),
                yaml_to_declaration_entries({
                    "opensiddur:gregorian-date": dict(zip(("year", "month", "day"), date)),
                    "opensiddur:location": {"latitude": 31.78, "longitude": 35.22},
                }))
        return CompilerProcessor("book", "index.xml").process()

    @staticmethod
    def _text(root: etree.ElementBase) -> str:
        return " ".join("".join(root.itertext()).split())

    def test_a_weekday_leaves_out_the_sabbath(self):
        text = self._text(self._compile(date=(2026, 11, 16)))
        self.assertIn("Weekday service", text)
        self.assertNotIn("Sabbath service", text)
        self.assertIn("Said every day", text)

    def test_a_sabbath_leaves_out_the_weekday(self):
        text = self._text(self._compile(date=(2026, 11, 21)))
        self.assertNotIn("Weekday service", text)
        self.assertIn("Sabbath service", text)

    def test_with_no_date_both_are_kept(self):
        root = self._compile()
        text = self._text(root)
        self.assertIn("Weekday service", text)
        self.assertIn("Sabbath service", text)
        self.assertEqual(len(root.findall(f".//{{{JLPTEI_NAMESPACE}}}conditional")), 2)

    def test_with_no_date_nothing_is_printed_around_them(self):
        root = self._compile()
        mark_silent_scopes(root)
        self.assertEqual(
            {marker.get(f"{{{PROCESSING_NAMESPACE}}}silent")
             for marker in root.iter(f"{{{JLPTEI_NAMESPACE}}}conditional",
                                     f"{{{JLPTEI_NAMESPACE}}}endConditional")},
            {"true"})
        tex = transform(etree.tostring(root, encoding="unicode"))
        body = tex.split(r"\begin{document}", 1)[1]
        self.assertNotIn(r"\OSCond", body)
        self.assertIn("Sabbath service", body)



class TestARubricTheScopeOpensWith(unittest.TestCase):
    """A scope announced by the rubric it opens with is not silent (conditional_markers)."""

    def _scope(self, opening: str):
        from lxml import etree

        from opensiddur.exporter.conditional_markers import is_silent
        root = etree.fromstring(
            '<r xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">'
            f'<j:conditional xml:id="c"/>{opening}<tei:p>x</tei:p><j:endConditional target="#c"/></r>')
        return is_silent(root[0])

    def test_a_description_announces_it(self):
        self.assertFalse(self._scope('<tei:note type="description">Reader:</tei:note>'))

    def test_even_after_an_annotation_anchored_there(self):
        self.assertFalse(self._scope('<tei:note type="commentary">A remark.</tei:note>'
                                     '<tei:note type="description">Reader:</tei:note>'))

    def test_a_scope_with_no_rubric_is_silent(self):
        self.assertTrue(self._scope('<tei:note type="commentary">A remark.</tei:note>'))


if __name__ == "__main__":
    unittest.main()
