"""Compiling for an electronic book: the reader's settings are left for the reader's device.

`--destination electronic` (LinearData.defer_reader_settings) withholds the settings a reader
supplies -- from the settings file and from the static defaults -- so their conditions stay
undecided, and records on each retained conditional the values the compile did know.
"""

import json
import tempfile
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.exporter.client_settings import is_reader_supplied, resolve
from opensiddur.exporter.compiler import CompilerProcessor, main
from opensiddur.exporter.condition_eval import parse_condition_element
from opensiddur.exporter.constants import JLPTEI_NAMESPACE, PROCESSING_NAMESPACE, TEI_NS
from opensiddur.exporter.linear import Undefined, get_linear_data, reset_linear_data
from opensiddur.exporter.settings import load_settings
from opensiddur.tests.exporter.registry_helpers import unchecked_registry

J = JLPTEI_NAMESPACE
P = PROCESSING_NAMESPACE


def _document(body: str) -> bytes:
    return f'''<tei:TEI xmlns:tei="{TEI_NS}" xmlns:j="{J}" xml:lang="en">
  <tei:teiHeader><tei:fileDesc><tei:titleStmt><tei:title>T</tei:title></tei:titleStmt>
  </tei:fileDesc></tei:teiHeader>
  <tei:text><tei:body><tei:div>{body}</tei:div></tei:body></tei:text>
</tei:TEI>'''.encode()


OMIT_TAHANUN = '''
  <j:conditional xml:id="c"><tei:fs type="opensiddur:override">
    <tei:f name="omit-tahanun"><tei:binary value="true"/></tei:f></tei:fs></j:conditional>
  <tei:p>no tahanun today</tei:p>
  <j:endConditional target="#c"/>'''

MAARIV_SECTION = '''
  <j:declare xml:id="d"><tei:fs type="opensiddur:service-time">
    <tei:f name="maariv"><tei:binary value="true"/></tei:f></tei:fs></j:declare>
  <j:conditional xml:id="c"><j:any>
    <tei:fs type="opensiddur:recitation"><tei:f name="repetition"><tei:binary value="true"/></tei:f></tei:fs>
    <tei:fs type="opensiddur:quorum"><tei:f name="minyan"><tei:binary value="true"/></tei:f></tei:fs>
  </j:any></j:conditional>
  <tei:p>aloud, or in a minyan</tei:p>
  <j:endConditional target="#c"/>
  <j:endDeclare target="#d"/>'''


SEDER_SECTION = '''
  <j:declare xml:id="d"><tei:fs type="opensiddur:hebrew-date">
    <tei:f name="year"><tei:numeric value="5786"/></tei:f>
    <tei:f name="month"><tei:numeric value="1"/></tei:f>
    <tei:f name="day"><tei:numeric value="15"/></tei:f></tei:fs></j:declare>
  <j:conditional xml:id="c"><tei:fs type="opensiddur:holiday-aggregate">
    <tei:f name="yom-tov"><tei:binary value="true"/></tei:f></tei:fs></j:conditional>
  <tei:p>on yom tov</tei:p>
  <j:endConditional target="#c"/>
  <j:endDeclare target="#d"/>'''


PLACED_SECTION = '''
  <j:declare xml:id="d"><tei:fs type="opensiddur:location">
    <tei:f name="latitude"><tei:numeric value="31.778"/></tei:f>
    <tei:f name="longitude"><tei:numeric value="35.235"/></tei:f></tei:fs></j:declare>
  <j:conditional xml:id="c"><tei:fs type="opensiddur:holiday-aggregate">
    <tei:f name="yom-tov"><tei:binary value="true"/></tei:f></tei:fs></j:conditional>
  <tei:p>on yom tov</tei:p>
  <j:endConditional target="#c"/>
  <j:endDeclare target="#d"/>'''


class _Compiling(unittest.TestCase):

    def setUp(self):
        reset_linear_data()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base = Path(self.temp_dir.name)
        (self.base / "proj").mkdir()
        get_linear_data().xml_cache.base_path = self.base

    def _compile(self, body: str, *, electronic: bool) -> etree.ElementBase:
        (self.base / "proj" / "doc.xml").write_bytes(_document(body))
        linear_data = get_linear_data()
        linear_data.defer_reader_settings = electronic
        CompilerProcessor.load_init_settings(linear_data, [])
        return CompilerProcessor("proj", "doc.xml").process()


class TestStaticDefaults(_Compiling):

    def test_print_compiles_the_static_default_in(self):
        root = self._compile(OMIT_TAHANUN, electronic=False)
        self.assertNotIn("no tahanun today", "".join(root.itertext()))
        self.assertIsNone(root.find(f".//{{{J}}}conditional"))

    def test_electronic_leaves_it_to_the_reader(self):
        root = self._compile(OMIT_TAHANUN, electronic=True)
        self.assertIn("no tahanun today", "".join(root.itertext()))
        self.assertIsNotNone(root.find(f".//{{{J}}}conditional"))
        self.assertIsNotNone(root.find(f".//{{{J}}}endConditional"))

    def test_calendar_settings_are_compiled_as_in_print(self):
        def stack(electronic):
            reset_linear_data()
            linear_data = get_linear_data()
            linear_data.defer_reader_settings = electronic
            CompilerProcessor.load_init_settings(linear_data, [])
            return {(e.fs_type, e.feature_name, repr(e.value))
                    for e in linear_data.conditional_settings}

        printed, electronic = stack(False), stack(True)
        self.assertEqual(
            {entry for entry in printed if is_reader_supplied(entry[0])} | electronic,
            printed)
        self.assertFalse(any(is_reader_supplied(entry[0]) for entry in electronic))
        self.assertIn("opensiddur:override", {entry[0] for entry in printed})


ANNUAL_HAFTARAH = '''
  <j:conditional xml:id="c"><tei:fs type="opensiddur:reading-cycle">
    <tei:f name="annual"><tei:binary value="true"/></tei:f></tei:fs></j:conditional>
  <tei:p>the annual haftarah</tei:p>
  <j:endConditional target="#c"/>'''


class TestReadingCycle(_Compiling):
    """Annual or triennial is the reader's choice in an electronic book."""

    def test_print_reads_the_annual_cycle(self):
        root = self._compile(ANNUAL_HAFTARAH, electronic=False)
        self.assertIn("the annual haftarah", "".join(root.itertext()))
        self.assertIsNone(root.find(f".//{{{J}}}conditional"))

    def test_electronic_leaves_the_cycle_to_the_reader(self):
        root = self._compile(ANNUAL_HAFTARAH, electronic=True)
        self.assertIsNotNone(root.find(f".//{{{J}}}conditional"))


class TestPinnedValues(_Compiling):

    def test_declared_and_derived_values_are_pinned(self):
        """Ma'ariv, declared by the section, implies no repetition; the minyan is unknown.

        The condition is undecided, and the device needs what the compile knew to decide
        it once the reader says whether there is a minyan.
        """
        root = self._compile(MAARIV_SECTION, electronic=True)
        conditional = root.find(f".//{{{J}}}conditional")
        pinned = conditional.find(f"{{{P}}}pinned")
        self.assertIsNotNone(pinned)
        # The service too: the device derives the recitation from it, and must not from the
        # reader's choice of service where the section has said which it is.
        self.assertEqual(
            json.loads(pinned.text),
            {"opensiddur:recitation": {"repetition": False},
             "opensiddur:service-time": {"maariv": True}})

    def test_the_inputs_of_a_derivation_are_pinned_transitively(self):
        """A section declares its Hebrew date; a condition on yom tov stands in it.

        The device derives yom tov from a date, as the compile does, so the section's date
        goes with the condition -- and prevails there over the device's clock.
        """
        root = self._compile(SEDER_SECTION, electronic=True)
        pinned = root.find(f".//{{{J}}}conditional/{{{P}}}pinned")
        self.assertIsNotNone(pinned)
        self.assertEqual(json.loads(pinned.text)["opensiddur:hebrew-date"],
                         {"year": {"num": 5786}, "month": {"num": 1}, "day": {"num": 15}})

    def test_a_place_is_pinned_with_its_zone(self):
        """The device takes a place only with its zone; the compile derives the zone."""
        root = self._compile(PLACED_SECTION, electronic=True)
        pinned = json.loads(root.find(f".//{{{J}}}conditional/{{{P}}}pinned").text)
        self.assertEqual(pinned["opensiddur:location"]["timezone"], "Asia/Jerusalem")
        self.assertIs(pinned["opensiddur:israel"]["is-israel"], True)

    def test_print_pins_nothing(self):
        root = self._compile(MAARIV_SECTION, electronic=False)
        self.assertIsNotNone(root.find(f".//{{{J}}}conditional"))
        self.assertIsNone(root.find(f".//{{{P}}}pinned"))

    def test_nothing_known_pins_nothing(self):
        root = self._compile(OMIT_TAHANUN, electronic=True)
        self.assertIsNone(root.find(f".//{{{P}}}pinned"))


# Its feature names are made up for the test.
@unchecked_registry()
class TestSettingsFile(_Compiling):

    def _load(self, electronic: bool):
        settings = self.base / "settings.yaml"
        settings.write_text(
            "priority:\n  transclusion: [proj]\n"
            "declarations:\n"
            "  opensiddur:rite:\n    rite: ashkenaz\n"
            "  opensiddur:israel:\n    is-israel: true\n",
            encoding="utf-8")
        linear_data = get_linear_data()
        linear_data.defer_reader_settings = electronic
        load_settings(settings, linear_data=linear_data, project_directory=self.base)
        return {(e.fs_type, e.feature_name): e.value
                for e in linear_data.conditional_settings if e.source == "init"}

    def test_print_compiles_every_declaration(self):
        declared = self._load(electronic=False)
        self.assertEqual(declared[("opensiddur:rite", "rite")], "ashkenaz")
        self.assertIs(declared[("opensiddur:israel", "is-israel")], True)

    def test_electronic_compiles_only_the_calendar(self):
        """The reader's declarations stay on the stack, undefined: still explicit, so nothing
        is derived over them, but left for the device to decide."""
        declared = self._load(electronic=True)
        self.assertIs(declared[("opensiddur:rite", "rite")], Undefined)
        self.assertIs(declared[("opensiddur:israel", "is-israel")], True)


ZIMMUN_UNDER_A_DECLARED_MINYAN = '''
  <j:declare xml:id="d"><tei:fs type="opensiddur:quorum">
    <tei:f name="minyan">{minyan}</tei:f></tei:fs></j:declare>
  <j:conditional xml:id="c"><tei:fs type="opensiddur:quorum">
    <tei:f name="zimmun"><tei:binary value="true"/></tei:f></tei:fs></j:conditional>
  <tei:p>with a zimmun</tei:p>
  <j:endConditional target="#c"/>
  <j:endDeclare target="#d"/>'''


class TestElectronicAgreesWithPrint(_Compiling):
    """The device, given the settings file's values as its defaults, decides as print does."""

    def _compile_with(self, body: str, declarations: dict, *, electronic: bool):
        (self.base / "proj" / "doc.xml").write_bytes(_document(body))
        settings = self.base / "settings.yaml"
        lines = ["priority:", "  transclusion: [proj]", "declarations:"]
        for fs, features in declarations.items():
            lines.append(f"  {fs}:")
            lines += [f"    {name}: {json.dumps(value)}" for name, value in features.items()]
        settings.write_text("\n".join(lines) + "\n", encoding="utf-8")
        reset_linear_data()
        linear_data = get_linear_data()
        linear_data.defer_reader_settings = electronic
        get_linear_data().xml_cache.base_path = self.base
        load_settings(settings, linear_data=linear_data, project_directory=self.base)
        return CompilerProcessor("proj", "doc.xml").process()

    def _device(self, root, defaults) -> str | None:
        """What the device decides for the one conditional: None if the compile decided it."""
        conditional = root.find(f".//{{{J}}}conditional")
        if conditional is None:
            return "compiled in" if "with a zimmun" in "".join(root.itertext()) else "compiled out"
        pinned_element = conditional.find(f"{{{P}}}pinned")
        pinned = json.loads(pinned_element.text) if pinned_element is not None else {}
        return resolve(parse_condition_element(conditional), pinned=pinned, defaults=defaults)

    def _printed(self, body, declarations) -> str:
        root = self._compile_with(body, declarations, electronic=False)
        if root.find(f".//{{{J}}}conditional") is not None:
            return "undefined"
        return "true" if "with a zimmun" in "".join(root.itertext()) else "false"

    def _check(self, body, declarations):
        printed = self._printed(body, declarations)
        electronic = self._compile_with(body, declarations, electronic=True)
        self.assertEqual(self._device(electronic, declarations), printed)

    def test_an_explicit_setting_is_not_derived_over(self):
        """The volume says there is no zimmun; the section declares a minyan. Print keeps the
        volume's word, and so must the device -- not a zimmun derived at compile time."""
        self._check(ZIMMUN_UNDER_A_DECLARED_MINYAN.format(minyan='<tei:binary value="true"/>'),
                    {"opensiddur:quorum": {"zimmun": False}})

    def test_the_documents_minyan_reaches_the_device(self):
        """The volume says there is a minyan; this section says there is not. Print derives no
        zimmun here; the device must not derive one from the volume's minyan."""
        self._check(ZIMMUN_UNDER_A_DECLARED_MINYAN.format(minyan='<tei:binary value="false"/>'),
                    {"opensiddur:quorum": {"minyan": True}})

    def test_a_declared_undefined_is_kept(self):
        body = '''
  <j:declare xml:id="d"><tei:fs type="opensiddur:quorum">
    <tei:f name="zimmun"><tei:default/></tei:f></tei:fs></j:declare>
  <j:conditional xml:id="c"><tei:fs type="opensiddur:quorum">
    <tei:f name="zimmun"><tei:binary value="true"/></tei:f></tei:fs></j:conditional>
  <tei:p>with a zimmun</tei:p>
  <j:endConditional target="#c"/>
  <j:endDeclare target="#d"/>'''
        self._check(body, {"opensiddur:quorum": {"zimmun": True}})
        root = self._compile_with(body, {"opensiddur:quorum": {"zimmun": True}}, electronic=True)
        pinned = json.loads(root.find(f".//{{{P}}}pinned").text)
        self.assertEqual(pinned, {"opensiddur:quorum": {"zimmun": None}})

    def test_the_volumes_own_values_are_not_pinned(self):
        root = self._compile_with(OMIT_TAHANUN, {"opensiddur:override": {"omit-tahanun": True}},
                                  electronic=True)
        self.assertIsNone(root.find(f".//{{{P}}}pinned"))


class TestMain(_Compiling):

    def _main(self, *extra) -> etree.ElementBase:
        (self.base / "proj" / "doc.xml").write_bytes(_document(OMIT_TAHANUN))
        output = self.base / "out.xml"
        main(["-p", "proj", "-f", "doc.xml", "-o", str(output),
              "--project-directory", str(self.base), *extra])
        return etree.parse(str(output)).getroot()

    def test_electronic_output_says_so(self):
        root = self._main("--destination", "electronic")
        self.assertEqual(root.get(f"{{{P}}}destination"), "electronic")
        self.assertIsNotNone(root.find(f".//{{{J}}}conditional"))

    def test_print_is_the_default(self):
        root = self._main()
        self.assertIsNone(root.get(f"{{{P}}}destination"))
        self.assertIsNone(root.find(f".//{{{J}}}conditional"))


if __name__ == "__main__":
    unittest.main()
