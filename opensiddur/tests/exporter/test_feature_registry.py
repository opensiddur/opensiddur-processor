"""Tests for the settings registry (opensiddur/exporter/features.yaml, feature_registry.py).

The checks run against synthetic XML and YAML, and against small registries written for the
test. The tests that hold the code and the documentation to the real registry read only the
registry and the code's own constants, never the corpus.
"""

import re
import tempfile
import unittest
import unittest.mock
from datetime import date, timedelta
from pathlib import Path

from lxml import etree
from pydantic import ValidationError

from opensiddur.exporter import feature_registry
from opensiddur.exporter.calendar.compute import (
    AGGREGATE_FEATURES,
    FS_GREGORIAN,
    FS_HOLIDAY,
    FS_HOLIDAY_AGG,
    FS_LOCATION,
    FS_READING_CYCLE,
    FS_RECITATION,
    FS_SERVICE_TIME,
    FS_TIME,
    FS_TORAH,
    HOLIDAY_FEATURES,
    READING_CYCLE_DEFAULTS,
    RECITATION_FEATURES,
    SERVICE_TIME_FEATURES,
    TORAH_FEATURES,
    SettingSnapshot,
)
from opensiddur.exporter.client_settings import CALENDAR_FS_TYPES
from opensiddur.exporter.condition_eval import parse_condition_element
from opensiddur.exporter.conditional_settings import parse_declare_element
from opensiddur.exporter.derivation_graph import (
    DERIVED_FS_TYPES,
    topological_derivation_order,
)
from opensiddur.exporter.derived_settings import (
    FS_OVERRIDE,
    OVERRIDE_FEATURES,
    STATIC_DEFAULTS,
)
from opensiddur.exporter.feature_registry import (
    check_fs_element,
    check_yaml_value,
    load_registry,
)
from opensiddur.exporter.linear import NumericValue
from opensiddur.exporter.settings import SettingsYaml
from opensiddur.exporter.validate_features import validate

TEI = "http://www.tei-c.org/ns/1.0"
J = "http://jewishliturgy.org/ns/jlptei/2"
JLPTEI_DOC = Path(__file__).resolve().parents[3] / "schema" / "JLPTEI-3.md"

SYNTHETIC_REGISTRY = """
opensiddur:test:
  common: true
  supplied: declared
  features:
    flag: binary
    day: {numeric: {min: 0, max: 3}}
    ratio: {numeric: {min: -1, max: 1, integer: false}}
    colour: {symbol: {values: [red, blue]}}
    token: {symbol: {}}
    code: {string: {pattern: "[AB]{2}"}}
    text: {string: {}}
opensiddur:open:
  common: false
  supplied: declared
  open: {name: "x-[a-z]+", value: binary}
"""


def _registry(text: str = SYNTHETIC_REGISTRY) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "features.yaml"
        path.write_text(text)
        return load_registry.__wrapped__(path)


def _fs(fs_type: str, *features: tuple[str, str]) -> etree._Element:
    body = "".join(f'<tei:f name="{name}">{value}</tei:f>' for name, value in features)
    return etree.fromstring(f'<tei:fs xmlns:tei="{TEI}" type="{fs_type}">{body}</tei:fs>')


class TestLoading(unittest.TestCase):

    def test_kinds_and_constraints_are_read(self):
        registry = _registry()
        test = registry["opensiddur:test"]
        self.assertEqual("binary", test.features["flag"].kind)
        self.assertEqual((0, 3, True), (test.features["day"].minimum,
                                        test.features["day"].maximum,
                                        test.features["day"].integer))
        self.assertFalse(test.features["ratio"].integer)
        self.assertEqual(frozenset({"red", "blue"}), test.features["colour"].values)
        self.assertIsNone(test.features["token"].values)

    def test_an_open_type_takes_any_name_matching_its_pattern(self):
        open_type = _registry()["opensiddur:open"]
        self.assertEqual("binary", open_type.feature("x-anything").kind)
        self.assertIsNone(open_type.feature("y-anything"))

    def test_malformed_registries_are_refused(self):
        for text in (
            "opensiddur:a: {common: true, supplied: declared, features: {f: maybe}}",
            "opensiddur:a: {common: true, supplied: declared, features: {f: {numeric: {least: 1}}}}",
            "opensiddur:a: {common: true, supplied: sometimes, features: {f: binary}}",
            "opensiddur:a: {common: true, supplied: declared}",
            "other:a: {common: true, supplied: declared, features: {f: binary}}",
            "opensiddur:a: {common: true, supplied: declared, colour: red, features: {f: binary}}",
            "opensiddur:a: {supplied: declared, features: {f: binary}}",
            "opensiddur:a: {common: false, supplied: declared, open: {name: x}}",
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                _registry(text)


class TestXmlValues(unittest.TestCase):

    def setUp(self):
        self.registry = _registry()

    def _problems(self, fs, *, in_condition=True):
        return check_fs_element(fs, in_condition=in_condition, registry=self.registry)

    def test_a_registered_value_of_the_right_kind_passes(self):
        fs = _fs("opensiddur:test",
                 ("flag", '<tei:binary value="true"/>'),
                 ("day", '<tei:numeric value="1" max="3"/>'),
                 ("ratio", '<tei:numeric value="-0.5"/>'),
                 ("colour", '<tei:symbol value="red"/>'),
                 ("token", '<tei:symbol value="anything"/>'),
                 ("code", "<tei:string>AB</tei:string>"),
                 ("text", "<tei:string>free text</tei:string>"))
        self.assertEqual([], self._problems(fs))

    def test_an_unregistered_type_or_feature_is_named(self):
        self.assertEqual(["opensiddur:nope is not a registered settings type"],
                         self._problems(_fs("opensiddur:nope", ("flag", "<tei:default/>"))))
        self.assertEqual(["opensiddur:test has no feature 'lag-bomer'"],
                         self._problems(_fs("opensiddur:test",
                                            ("lag-bomer", '<tei:binary value="true"/>'))))

    def test_a_value_of_the_wrong_kind(self):
        problems = self._problems(_fs("opensiddur:test",
                                      ("flag", '<tei:numeric value="1"/>'),
                                      ("colour", "<tei:string>red</tei:string>")))
        self.assertEqual(["opensiddur:test/flag is binary, not tei:numeric",
                          "opensiddur:test/colour is a symbol, one of blue, red, not tei:string"],
                         problems)

    def test_numbers_out_of_range_or_not_whole(self):
        problems = self._problems(_fs("opensiddur:test",
                                      ("day", '<tei:numeric value="1" max="4"/>'),
                                      ("ratio", '<tei:numeric value="2"/>')))
        self.assertEqual(["opensiddur:test/day: @max 4 is above 3",
                          "opensiddur:test/ratio: @value 2 is above 1"], problems)
        self.assertEqual(["opensiddur:test/day: @value 1.5 is not an integer"],
                         self._problems(_fs("opensiddur:test",
                                            ("day", '<tei:numeric value="1.5"/>'))))

    def test_fractions_are_read_as_numbers(self):
        self.assertEqual(["opensiddur:test/day: @value 6 is above 3"],
                         self._problems(_fs("opensiddur:test",
                                            ("day", '<tei:numeric value="12/2"/>'))))
        self.assertEqual(["opensiddur:test/day: @value 0.5 is not an integer"],
                         self._problems(_fs("opensiddur:test",
                                            ("day", '<tei:numeric value="1/2"/>'))))

    def test_non_finite_numbers_are_refused(self):
        for raw in ("inf", "nan"):
            with self.subTest(raw=raw):
                problems = self._problems(_fs("opensiddur:test",
                                              ("ratio", f'<tei:numeric value="{raw}"/>')))
                self.assertEqual(1, len(problems))
                self.assertIn("not a finite number", problems[0])

    def test_symbols_and_strings_outside_their_set(self):
        problems = self._problems(_fs("opensiddur:test",
                                      ("colour", '<tei:symbol value="green"/>'),
                                      ("code", "<tei:string>ABC</tei:string>")))
        self.assertEqual(2, len(problems))
        self.assertIn("not 'green'", problems[0])
        self.assertIn("matching [AB]{2}, not 'ABC'", problems[1])

    def test_a_condition_may_ask_whether_a_number_is_true(self):
        fs = _fs("opensiddur:test", ("day", '<tei:binary value="true"/>'))
        self.assertEqual([], self._problems(fs, in_condition=True))
        self.assertEqual(["opensiddur:test/day is an integer 0..3, not tei:binary"],
                         self._problems(fs, in_condition=False))

    def test_undefined_is_any_features_value(self):
        fs = _fs("opensiddur:test",
                 ("colour", "<tei:default/>"),
                 ("day", '<tei:symbol value="undefined"/>'))
        self.assertEqual([], self._problems(fs))

    def test_alternatives_and_negations_are_each_checked(self):
        fs = _fs("opensiddur:test",
                 ("colour", '<tei:vAlt><tei:symbol value="red"/><tei:symbol value="pink"/></tei:vAlt>'),
                 ("day", '<tei:vNot><tei:numeric value="9"/></tei:vNot>'))
        self.assertEqual(2, len(self._problems(fs)))

    def test_open_feature_names(self):
        self.assertEqual([], self._problems(_fs("opensiddur:open",
                                                ("x-one", '<tei:binary value="true"/>'))))
        self.assertEqual(["opensiddur:open has no feature 'one'"],
                         self._problems(_fs("opensiddur:open",
                                            ("one", '<tei:binary value="true"/>'))))

    def test_other_namespaces_are_not_the_registrys_business(self):
        fs = _fs("example:anything", ("whatever", '<tei:numeric value="99"/>'))
        self.assertEqual([], self._problems(fs))


class TestYamlValues(unittest.TestCase):

    def setUp(self):
        self.registry = _registry()

    def _problems(self, feature, value, fs_type="opensiddur:test"):
        return check_yaml_value(fs_type, feature, value, registry=self.registry)

    def test_values_of_the_right_kind(self):
        for feature, value in (("flag", False), ("day", 2), ("ratio", 0.25), ("colour", "blue"),
                               ("token", "x"), ("code", "BA"), ("text", "t"), ("flag", None)):
            with self.subTest(feature=feature, value=value):
                self.assertEqual([], self._problems(feature, value))

    def test_values_of_the_wrong_kind(self):
        for feature, value in (("flag", "true"), ("flag", 1), ("day", True), ("day", "2"),
                               ("day", 4), ("day", 1.5), ("colour", "green"), ("code", 7),
                               ("ratio", float("nan")), ("ratio", float("inf"))):
            with self.subTest(feature=feature, value=value):
                self.assertEqual(1, len(self._problems(feature, value)))

    def test_unregistered_names(self):
        self.assertEqual(["opensiddur:test has no feature 'nope'"], self._problems("nope", True))
        self.assertEqual(["opensiddur:nope is not a registered settings type"],
                         self._problems("flag", True, fs_type="opensiddur:nope"))
        self.assertEqual([], self._problems("anything", "x", fs_type="example:mine"))


class TestEnforcement(unittest.TestCase):
    """The real registry is applied where settings are parsed."""

    def test_a_declaration_of_an_unregistered_feature_is_refused(self):
        declare = etree.fromstring(
            f'<j:declare xmlns:j="{J}" xmlns:tei="{TEI}" xml:id="d">'
            '<tei:fs type="opensiddur:holiday"><tei:f name="lag-bomer">'
            '<tei:numeric value="1"/></tei:f></tei:fs></j:declare>')
        with self.assertRaisesRegex(ValueError, "has no feature 'lag-bomer'"):
            parse_declare_element(declare, "d")

    def test_a_condition_on_an_unregistered_feature_is_refused(self):
        conditional = etree.fromstring(
            f'<j:conditional xmlns:j="{J}" xmlns:tei="{TEI}" xml:id="c">'
            '<tei:fs type="opensiddur:holiday"><tei:f name="pesah">'
            '<tei:numeric value="1" max="9"/></tei:f></tei:fs></j:conditional>')
        with self.assertRaisesRegex(ValueError, "@max 9 is above 8"):
            parse_condition_element(conditional)

    def test_the_error_says_where_the_setting_is(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "text.xml"
            path.write_text(
                f'<j:conditional xmlns:j="{J}" xmlns:tei="{TEI}" xml:id="c">\n'
                '<tei:fs type="opensiddur:holiday"><tei:f name="pesah">'
                '<tei:numeric value="9"/></tei:f></tei:fs></j:conditional>')
            conditional = etree.parse(str(path)).getroot()
            with self.assertRaisesRegex(ValueError, r"text\.xml:2: opensiddur:holiday/pesah"):
                parse_condition_element(conditional)

    def test_a_condition_may_test_a_holiday_as_binary(self):
        conditional = etree.fromstring(
            f'<j:conditional xmlns:j="{J}" xmlns:tei="{TEI}" xml:id="c">'
            '<tei:fs type="opensiddur:holiday"><tei:f name="pesah">'
            '<tei:binary value="true"/></tei:f></tei:fs></j:conditional>')
        parse_condition_element(conditional)

    def test_a_settings_file_declaration_is_checked(self):
        with self.assertRaises(ValidationError) as caught:
            SettingsYaml.model_validate({
                "priority": {},
                "declarations": {"opensiddur:override": {"house-of-morning": True}},
            })
        self.assertIn("has no feature 'house-of-morning'", str(caught.exception))
        with self.assertRaises(ValidationError):
            SettingsYaml.model_validate({
                "priority": {},
                "declarations": {"opensiddur:gregorian-date": {"month": 13}},
            })

    def test_a_settings_file_with_registered_declarations_validates(self):
        SettingsYaml.model_validate({
            "priority": {},
            "declarations": {
                "opensiddur:gregorian-date": {"year": 2026, "month": 10, "day": 12},
                "opensiddur:location": {"latitude": 31.78, "longitude": 35.22},
                "opensiddur:override": {"house-of-mourning": None},
                "opensiddur:rite": {"ashkenaz": True},
            },
        })


class TestValidator(unittest.TestCase):

    def test_reports_each_violation_with_its_file_and_line(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "proj"
            project.mkdir()
            (project / "text.xml").write_text(
                f'<tei:TEI xmlns:tei="{TEI}" xmlns:j="{J}"><tei:text><tei:body>\n'
                '<j:conditional xml:id="c">\n'
                '<tei:fs type="opensiddur:holiday"><tei:f name="pesah">'
                '<tei:numeric value="9"/></tei:f></tei:fs></j:conditional>\n'
                '<j:declare xml:id="d">\n'
                '<tei:fs type="opensiddur:quorum"><tei:f name="minyan">'
                '<tei:binary value="true"/></tei:f></tei:fs></j:declare>\n'
                '<tei:fs type="opensiddur:nope"/>\n'
                '</tei:body></tei:text></tei:TEI>')
            with unittest.mock.patch("builtins.print") as printed:
                found = validate(Path(directory))
        self.assertEqual(1, found)
        printed.assert_called_once_with(
            "proj/text.xml:3: opensiddur:holiday/pesah: @value 9 is above 8")

    def test_reports_a_file_it_cannot_read_and_a_project_that_is_not_there(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "proj"
            project.mkdir()
            (project / "broken.xml").write_text("<unclosed>")
            with unittest.mock.patch("builtins.print") as printed:
                found = validate(Path(directory), ["proj", "nope"])
        self.assertEqual(2, found)
        lines = [call.args[0] for call in printed.call_args_list]
        self.assertTrue(lines[0].startswith("proj/broken.xml:1: not well-formed XML"))
        self.assertTrue(lines[1].endswith("nope: no such project directory"))


class TestRegistryAgreesWithTheCode(unittest.TestCase):
    """The registry and the code's own lists of features name the same features."""

    def setUp(self):
        self.registry = load_registry()

    def _names(self, fs_type):
        return set(self.registry[fs_type].features)

    def test_feature_lists(self):
        for fs_type, names in (
            (FS_HOLIDAY, HOLIDAY_FEATURES),
            (FS_HOLIDAY_AGG, AGGREGATE_FEATURES),
            (FS_TORAH, TORAH_FEATURES),
            (FS_READING_CYCLE, READING_CYCLE_DEFAULTS),
            (FS_RECITATION, RECITATION_FEATURES),
            (FS_SERVICE_TIME, SERVICE_TIME_FEATURES),
            (FS_OVERRIDE, OVERRIDE_FEATURES),
        ):
            with self.subTest(fs_type=fs_type):
                self.assertEqual(set(names), self._names(fs_type))

    def test_every_type_the_code_knows_is_registered_and_common(self):
        for fs_type in DERIVED_FS_TYPES | CALENDAR_FS_TYPES | set(STATIC_DEFAULTS):
            with self.subTest(fs_type=fs_type):
                self.assertIn(fs_type, self.registry)
                self.assertTrue(self.registry[fs_type].common)

    def test_static_defaults_fit_the_registry(self):
        for fs_type, features in STATIC_DEFAULTS.items():
            for feature, value in features.items():
                with self.subTest(fs_type=fs_type, feature=feature):
                    self.assertEqual([], check_yaml_value(fs_type, feature, value))

    def test_every_derived_value_fits_the_registry(self):
        """Every value the derivations produce, over three years in Israel and the diaspora."""
        places = ((31.7683, 35.2137), (40.7128, -74.0060))
        problems = set()
        # Every fifth day, which visits each holiday's days of the week in turn, from a year
        # with a three-day Purim (Shushan Purim on Shabbat, March 2025).
        day = date(2024, 9, 1)
        while day < date(2027, 9, 1):
            for latitude, longitude in places:
                for hour in (None, 6, 21):
                    values = {
                        (FS_GREGORIAN, "year"): day.year,
                        (FS_GREGORIAN, "month"): day.month,
                        (FS_GREGORIAN, "day"): day.day,
                        (FS_LOCATION, "latitude"): latitude,
                        (FS_LOCATION, "longitude"): longitude,
                        (FS_READING_CYCLE, "triennial"): True,
                    }
                    if hour is not None:
                        values[(FS_TIME, "hour")] = hour
                        values[(FS_TIME, "minute")] = 0
                    snapshot = SettingSnapshot(get_setting=lambda t, f, values=values: values.get((t, f)))
                    for spec in topological_derivation_order():
                        for feature, value in (spec.compute(snapshot) or {}).items():
                            values[(spec.fs_type, feature)] = value
                            if isinstance(value, NumericValue):
                                value = value.value
                            for problem in check_yaml_value(spec.fs_type, feature, value):
                                problems.add(problem)
            day += timedelta(days=5)
        self.assertEqual(set(), problems)


class TestRegistryAgreesWithJlptei(unittest.TestCase):
    """JLPTEI-3 documents the common types; whatever it names must be registered."""

    def setUp(self):
        self.registry = load_registry()
        self.documented: dict[str, set[str]] = {}
        text = JLPTEI_DOC.read_text(encoding="utf-8")
        for block in re.findall(r"```xml\n(.*?)```", text, flags=re.S):
            for fs_type, body in re.findall(
                    r'<tei:fs type="(opensiddur:[^"]+)">(.*?)</tei:fs>', block, flags=re.S):
                names = set(re.findall(r'<tei:f name="([^"]+)"', body))
                self.documented.setdefault(fs_type, set()).update(names)

    def test_every_common_type_and_feature_is_documented(self):
        for fs_type, registered in self.registry.items():
            if not registered.common:
                continue
            with self.subTest(fs_type=fs_type):
                self.assertIn(fs_type, self.documented)
                if registered.open_name is None:
                    self.assertEqual(set(), set(registered.features) - self.documented[fs_type])

    def test_everything_documented_is_registered(self):
        for fs_type, names in self.documented.items():
            with self.subTest(fs_type=fs_type):
                self.assertIn(fs_type, self.registry)
                unknown = {name for name in names
                           if self.registry[fs_type].feature(name) is None}
                self.assertEqual(set(), unknown)


class TestBasicSettings(unittest.TestCase):
    """The electronic book's catalogue of reader settings names registered features."""

    def test_controls_name_registered_features(self):
        path = Path(feature_registry.__file__).parent / "html" / "basic_settings.yaml"
        text = path.read_text(encoding="utf-8")
        registry = load_registry()
        referenced = set(re.findall(r"(opensiddur:[a-z-]+)", text))
        self.assertEqual(set(), referenced - set(registry))


if __name__ == "__main__":
    unittest.main()
