import tempfile
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.importer.sefaria.conditions import ConditionsError, condition_xml, load_conditions
from opensiddur.importer.util.incipit import words

NS = {"tei": "http://www.tei-c.org/ns/1.0", "j": "http://jewishliturgy.org/ns/jlptei/2"}


def parse(xml: str) -> etree._Element:
    return etree.fromstring(f'<x xmlns:tei="{NS["tei"]}" xmlns:j="{NS["j"]}">{xml}</x>')


TABLE = """
rubrics:
  - match: "^During the Ten Days of Penitence(,)? add:"
    when: {holiday-aggregate: {aseret-ymei-tshuva: true}}
  - match: "^On Sunday:"
    when: {day-of-week: {hebrew-day: 1}}
  - match: "^\\\\(When the Chazzan repeats"
    when: {recitation: {repetition: true}}
    section: true
labels:
  - label: 'לר"ח:'
    when: {holiday: {rosh-hodesh: true}}
inline:
  - label: 'בעשי"ת'
    when: {holiday-aggregate: {aseret-ymei-tshuva: true}}
replacements:
  - alternative: 'הַשָּׁלוֹם'
    replaces: 'שָׁלוֹם'
directives:
  - "^When the Holy Ark is opened"
leaves:
  - work: w
    leaf: "Morning / Reading of the Torah"
    when: {day-of-week: {hebrew-day: 2}}
    note: "On Mondays:"
"""


def table(text: str = TABLE):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "conditions.yaml"
        path.write_text(text, encoding="utf-8")
        return load_conditions(path)


class TestConditionXml(unittest.TestCase):
    def test_kinds_of_value(self):
        xml = parse(condition_xml({"hebrew-date": {"leap-year": True, "month": [7, 13], "day": 3},
                                   "meal-context": {"meein-shalosh-food": "wine"}}))
        (both,) = xml.xpath("j:all", namespaces=NS)
        self.assertEqual(both.xpath("tei:fs/@type", namespaces=NS),
                         ["opensiddur:hebrew-date", "opensiddur:meal-context"])
        self.assertEqual(xml.xpath("//tei:f[@name='leap-year']/tei:binary/@value", namespaces=NS), ["true"])
        self.assertEqual(xml.xpath("//tei:f[@name='month']/tei:numeric/@max", namespaces=NS), ["13"])
        self.assertEqual(xml.xpath("//tei:f[@name='day']/tei:numeric/@value", namespaces=NS), ["3"])
        self.assertEqual(xml.xpath("//tei:symbol/@value", namespaces=NS), ["wine"])

    def test_any_all_none(self):
        xml = parse(condition_xml({"none": [{"holiday": {"rosh-hodesh": True}}, {"holiday": {"pesah": [3, 8]}}]}))
        self.assertEqual(len(xml.xpath("j:none/tei:fs", namespaces=NS)), 2)

    def test_a_malformed_condition_is_an_error(self):
        for bad in (None, {}, {"any": []}, {"holiday": {"x": 1.5}}, {"holiday": []}):
            with self.assertRaises(ConditionsError):
                condition_xml(bad)


class TestTable(unittest.TestCase):
    def test_rubrics_are_found_by_their_english(self):
        conditions = table()
        found = conditions.for_rubric("During the Ten Days  of Penitence,\nadd:".replace("  ", " "))
        self.assertEqual(found.when, {"holiday-aggregate": {"aseret-ymei-tshuva": True}})
        self.assertFalse(found.section)
        self.assertTrue(conditions.for_rubric("(When the Chazzan repeats the Shemoneh Esrei)").section)
        self.assertIsNone(conditions.for_rubric("During the Ten Days of Penitence, continue at the asterisk"))

    def test_labels_and_inline_alternatives_are_found_by_their_words(self):
        conditions = table()
        self.assertIsNotNone(conditions.for_label('לְר"ח:'))
        self.assertIsNotNone(conditions.for_inline('בעשי"ת הַשָּׁלוֹם'))
        self.assertIsNone(conditions.for_inline("פלוני"))
        self.assertEqual(conditions.replaced("הַשָּׁלוֹם").replaces, ("שלם",))

    def test_a_bad_entry_is_an_error(self):
        with self.assertRaises(ConditionsError):
            table("rubrics:\n  - match: '('\n    when: {holiday: {purim: true}}\n")
        with self.assertRaises(ConditionsError):
            table("labels:\n  - label: ''\n    when: {holiday: {purim: true}}\n")


class TestHowFarARubricGoverns(unittest.TestCase):
    def test_until_through_and_instead_of_previous(self):
        conditions = table("""
definitions:
  said: &said {override: {omit-tahanun: false}}
rubrics:
  - match: "^Tachanun is also omitted"
    when: *said
    until: "^The Chazzan recites the following Kaddish"
  - match: "^\\\\(When the Chazzan repeats"
    when: {recitation: {repetition: true}}
    through: "בָּרוּךְ אֵל הַהוֹדָאוֹת"
  - match: "^A woman says:"
    when: {person: {gender: female}}
    instead_of_previous: true
""")
        tachanun = conditions.for_rubric("Tachanun is also omitted in the presence of a bridegroom")
        self.assertEqual(tachanun.when, {"override": {"omit-tahanun": False}})  # the anchor is resolved
        self.assertTrue(tachanun.section)  # until implies a section
        self.assertTrue(tachanun.until.search("The Chazzan recites the following Kaddish"))
        self.assertEqual(conditions.for_rubric("(When the Chazzan repeats it)").through,
                         tuple(words("ברוך אל ההודאות")))
        self.assertTrue(conditions.for_rubric("A woman says:").instead_of_previous)
        self.assertFalse(tachanun.instead_of_previous)


class TestDirectivesAndLeaves(unittest.TestCase):
    def test_reviewed_directives_are_known(self):
        conditions = table()
        self.assertTrue(conditions.is_directive("When the Holy Ark is opened, the following is said:"))
        self.assertFalse(conditions.is_directive("On Sunday:"))

    def test_a_leaf_gate_is_found_by_its_work_and_leaf(self):
        gate = table().leaf_gate("w", "Morning / Reading of the Torah")
        self.assertEqual((gate.when, gate.note), ({"day-of-week": {"hebrew-day": 2}}, "On Mondays:"))
        self.assertIsNone(table().leaf_gate("other", "Morning / Reading of the Torah"))

    def test_malformed_entries_are_errors(self):
        for bad in ("directives: ['(']\n",
                    "leaves:\n  - leaf: x\n    when: {holiday: {purim: true}}\n",
                    "leaves:\n  - work: w\n    leaf: x\n",
                    "rubrics:\n  - match: x\n    when: {holiday: {purim: true}}\n    until: '('\n"):
            with self.assertRaises(ConditionsError, msg=bad):
                table(bad)


if __name__ == "__main__":
    unittest.main()
