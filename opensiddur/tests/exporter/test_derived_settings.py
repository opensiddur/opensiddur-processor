"""Tests for derived settings (feature defaulting)."""

import tempfile
import unittest
from pathlib import Path

import yaml
from lxml import etree

from opensiddur.exporter.compiler import CompilerProcessor
from opensiddur.exporter.condition_eval import (
    TriState,
    evaluate_condition,
    parse_condition_element,
)
from opensiddur.exporter.conditional_settings import (
    INIT_DECLARE_ID,
    yaml_to_declaration_entries,
)
from opensiddur.exporter.constants import JLPTEI_NAMESPACE, TEI_NS
from opensiddur.exporter.derived_settings import (
    SettingChangeTrigger,
    derived_declare_id,
    get_active_setting_entry,
    recalculate_derived_settings,
    register_derived_entry,
)
from opensiddur.exporter.linear import (
    ConditionalSettingEntry,
    TwilightValue,
    Undefined,
    get_linear_data,
    reset_linear_data,
)
from opensiddur.exporter.settings import load_settings

TEI = TEI_NS
J = JLPTEI_NAMESPACE

MINIMAL_XML = b'<root xmlns:tei="http://www.tei-c.org/ns/1.0"/>'


def _declare_xml(body: str) -> bytes:
    return f'''<root xmlns:tei="{TEI}" xmlns:j="{J}">
    <tei:text>
        {body}
    </tei:text>
</root>'''.encode()


class TestDerivedSettingsFramework(unittest.TestCase):
    def setUp(self):
        reset_linear_data()
        self.linear_data = get_linear_data()
        self.proc = None

    def _entry(self, declare_id: str, fs_type: str, feature: str, value, source: str = "declared"):
        return ConditionalSettingEntry(
            declare_id=declare_id,
            fs_type=fs_type,
            feature_name=feature,
            value=value,
            source=source,
        )

    def test_override_defaults_on_init(self):
        recalculate_derived_settings(self.linear_data, trigger=SettingChangeTrigger.INIT)
        self.assertFalse(
            get_active_setting_entry(self.linear_data, "opensiddur:override", "omit-tahanun").value
        )
        entry = get_active_setting_entry(self.linear_data, "opensiddur:override", "omit-tahanun")
        self.assertEqual(entry.source, "derived")
        self.assertIn(INIT_DECLARE_ID, entry.contributors)

    def test_explicit_override_wins_over_default(self):
        self.linear_data.conditional_settings.append(
            self._entry(INIT_DECLARE_ID, "opensiddur:override", "omit-tahanun", True, source="init")
        )
        recalculate_derived_settings(self.linear_data, trigger=SettingChangeTrigger.INIT)
        entry = get_active_setting_entry(self.linear_data, "opensiddur:override", "omit-tahanun")
        self.assertTrue(entry.value)
        self.assertEqual(entry.source, "init")

    def test_paratext_defaults_to_kept(self):
        """A volume that says nothing keeps its prefaces and its title pages."""
        recalculate_derived_settings(self.linear_data, trigger=SettingChangeTrigger.INIT)
        for feature in ("include", "title-page"):
            with self.subTest(feature=feature):
                entry = get_active_setting_entry(
                    self.linear_data, "opensiddur:paratext", feature)
                self.assertIs(entry.value, True)
                self.assertEqual(entry.source, "derived")

    def test_declared_paratext_wins_over_default(self):
        self.linear_data.conditional_settings.append(
            self._entry(INIT_DECLARE_ID, "opensiddur:paratext", "include", False, source="init")
        )
        recalculate_derived_settings(self.linear_data, trigger=SettingChangeTrigger.INIT)
        entry = get_active_setting_entry(self.linear_data, "opensiddur:paratext", "include")
        self.assertIs(entry.value, False)
        self.assertEqual(entry.source, "init")

    def test_an_electronic_book_leaves_paratext_to_its_reader(self):
        self.linear_data.defer_reader_settings = True
        recalculate_derived_settings(self.linear_data, trigger=SettingChangeTrigger.INIT)
        self.assertIsNone(
            get_active_setting_entry(self.linear_data, "opensiddur:paratext", "include"))

    CYCLE = "opensiddur:reading-cycle"

    def _cycle(self) -> dict[str, object]:
        """Which readings the volume carries, as a plain dict."""
        return {
            feature: get_active_setting_entry(self.linear_data, self.CYCLE, feature).value
            for feature in
            ("annual", "triennial-year-1", "triennial-year-2", "triennial-year-3")
        }

    def test_reading_cycle_defaults_to_the_annual_reading_alone(self):
        """These cannot be left undefined the way opensiddur:rite is.

        The annual haftarah and the three triennial ones are read on the same Shabbat, and an
        undefined condition keeps its text, so an open feature here would print all four.
        """
        recalculate_derived_settings(self.linear_data, trigger=SettingChangeTrigger.INIT)
        self.assertEqual(self._cycle(), {
            "annual": True,
            "triennial-year-1": False,
            "triennial-year-2": False,
            "triennial-year-3": False,
        })

    def test_a_date_alone_selects_no_triennial_year(self):
        """Every date falls in some year of the cycle, including an annual volume's."""
        CompilerProcessor.load_init_settings(
            self.linear_data,
            yaml_to_declaration_entries({
                "opensiddur:gregorian-date": {"year": 2026, "month": 1, "day": 3},
            }),
        )
        self.assertEqual(self._cycle()["annual"], True)
        self.assertEqual(self._cycle()["triennial-year-1"], False)

    def test_a_triennial_volume_takes_its_year_from_the_date(self):
        """5788 is the third year of the cycle, and the annual reading gives way to it."""
        CompilerProcessor.load_init_settings(
            self.linear_data,
            yaml_to_declaration_entries({
                "opensiddur:gregorian-date": {"year": 2028, "month": 1, "day": 8},
                "opensiddur:reading-cycle": {"triennial": True},
            }),
        )
        self.assertEqual(self._cycle(), {
            "annual": False,
            "triennial-year-1": False,
            "triennial-year-2": False,
            "triennial-year-3": True,
        })

    def test_a_withdrawn_cycle_year_falls_back_to_the_static_default(self):
        """When the date that chose a cycle year becomes unknown, the annual reading returns."""
        CompilerProcessor.load_init_settings(
            self.linear_data,
            yaml_to_declaration_entries({
                "opensiddur:gregorian-date": {"year": 2028, "month": 1, "day": 8},
                "opensiddur:reading-cycle": {"triennial": True},
            }),
        )
        self.assertTrue(self._cycle()["triennial-year-3"])
        self.linear_data.conditional_settings.append(ConditionalSettingEntry(
            declare_id="inner", fs_type="opensiddur:gregorian-date", feature_name="day",
            value=Undefined, source="declared"))
        recalculate_derived_settings(self.linear_data, trigger=SettingChangeTrigger.DECLARE,
                                     declare_id="inner")
        self.assertEqual(self._cycle(), {
            "annual": True,
            "triennial-year-1": False,
            "triennial-year-2": False,
            "triennial-year-3": False,
        })

    def test_a_volume_for_a_whole_cycle_keeps_all_three_years(self):
        """A printed humash covering a cycle turns on every year; a date would allow only one."""
        CompilerProcessor.load_init_settings(
            self.linear_data,
            yaml_to_declaration_entries({
                "opensiddur:reading-cycle": {
                    "annual": False,
                    "triennial-year-1": True,
                    "triennial-year-2": True,
                    "triennial-year-3": True,
                },
            }),
        )
        self.assertEqual(self._cycle(), {
            "annual": False,
            "triennial-year-1": True,
            "triennial-year-2": True,
            "triennial-year-3": True,
        })

    def test_a_declared_year_wins_over_the_date(self):
        CompilerProcessor.load_init_settings(
            self.linear_data,
            yaml_to_declaration_entries({
                "opensiddur:gregorian-date": {"year": 2026, "month": 1, "day": 3},
                "opensiddur:reading-cycle": {"triennial": True, "triennial-year-2": True},
            }),
        )
        self.assertEqual(self._cycle()["triennial-year-2"], True)

    def test_triennial_year_is_derived_from_the_date(self):
        """The cycle is counted from 5756, so 5786 opens one and 5788 closes it."""
        for gregorian, expected in (((2026, 1, 3), 1), ((2028, 1, 8), 3)):
            with self.subTest(date=gregorian):
                reset_linear_data()
                linear_data = get_linear_data()
                year, month, day = gregorian
                CompilerProcessor.load_init_settings(
                    linear_data,
                    yaml_to_declaration_entries({
                        "opensiddur:gregorian-date": {
                            "year": year, "month": month, "day": day
                        },
                    }),
                )
                entry = get_active_setting_entry(
                    linear_data, "opensiddur:torah-reading", "triennial-year"
                )
                self.assertEqual(entry.value, expected)

    def test_secular_day_from_gregorian_init(self):
        CompilerProcessor.load_init_settings(
            self.linear_data,
            yaml_to_declaration_entries({
                "opensiddur:gregorian-date": {"year": 2024, "month": 10, "day": 3},
            }),
        )
        entry = get_active_setting_entry(self.linear_data, "opensiddur:day-of-week", "secular-day")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.source, "derived")
        self.assertEqual(entry.value, 5)  # Thursday

    def test_a_static_default_outlives_a_derivation_that_cannot_run(self):
        """The volume's fixed choice is the one that matters when there is no date: the
        reading cycle is derived, and without a date its derivation contributes nothing."""
        recalculate_derived_settings(self.linear_data, trigger=SettingChangeTrigger.INIT)
        entry = get_active_setting_entry(self.linear_data, "opensiddur:reading-cycle", "annual")
        self.assertIsNotNone(entry)
        self.assertTrue(entry.value)

    def test_a_date_declared_undefined_is_not_a_date(self):
        for declarations in (
            {"opensiddur:gregorian-date": {"year": None, "month": 4, "day": 20},
             "opensiddur:location": {"latitude": 40.71, "longitude": -74.01}},
            {"opensiddur:hebrew-date": {"year": None, "month": 1, "day": 22},
             "opensiddur:israel": {"is-israel": False}},
        ):
            with self.subTest(declarations=declarations):
                reset_linear_data()
                linear_data = get_linear_data()
                CompilerProcessor.load_init_settings(
                    linear_data, yaml_to_declaration_entries(declarations))
                self.assertIsNone(
                    get_active_setting_entry(linear_data, "opensiddur:holiday", "pesah"))

    def test_israel_declared_undefined_is_not_israel(self):
        CompilerProcessor.load_init_settings(
            self.linear_data,
            yaml_to_declaration_entries({
                "opensiddur:gregorian-date": {"year": 2025, "month": 4, "day": 20},
                "opensiddur:location": {"latitude": 40.71, "longitude": -74.01},
                "opensiddur:israel": {"is-israel": None},
            }),
        )
        # 22 Nisan: the eighth of Pesah outside Israel, not a day of Pesah in it.
        self.assertIs(
            get_active_setting_entry(self.linear_data, "opensiddur:holiday", "pesah").value,
            Undefined)
        self.assertEqual(
            get_active_setting_entry(self.linear_data, "opensiddur:holiday", "hanukkah").value, 0)

    def test_an_unknown_locale_replaces_values_derived_for_a_known_one(self):
        """A scope that makes the locale unknown leaves no festival of the outer one behind."""
        CompilerProcessor.load_init_settings(
            self.linear_data,
            yaml_to_declaration_entries({
                "opensiddur:gregorian-date": {"year": 2025, "month": 4, "day": 20},
                "opensiddur:location": {"latitude": 40.71, "longitude": -74.01},
            }),
        )
        self.assertEqual(
            get_active_setting_entry(self.linear_data, "opensiddur:holiday", "pesah").value, 8)
        self.linear_data.conditional_settings.append(ConditionalSettingEntry(
            declare_id="inner", fs_type="opensiddur:israel", feature_name="is-israel",
            value=Undefined, source="declared"))
        recalculate_derived_settings(self.linear_data, trigger=SettingChangeTrigger.DECLARE,
                                     declare_id="inner")
        for fs_type, feature in (("opensiddur:holiday", "pesah"),
                                 ("opensiddur:holiday-aggregate", "yom-tov")):
            with self.subTest(feature=feature):
                self.assertIs(
                    get_active_setting_entry(self.linear_data, fs_type, feature).value, Undefined)

    def test_a_value_derived_from_an_input_now_undefined_is_withdrawn(self):
        CompilerProcessor.load_init_settings(
            self.linear_data,
            yaml_to_declaration_entries({
                "opensiddur:gregorian-date": {"year": 2025, "month": 4, "day": 13},
                "opensiddur:location": {"latitude": 40.71, "longitude": -74.01},
            }),
        )
        self.assertEqual(
            get_active_setting_entry(self.linear_data, "opensiddur:holiday", "pesah").value, 1)
        # The holidays could still be worked out from the civil date, but the volume has said
        # it does not know the Hebrew date they are reckoned by.
        self.linear_data.conditional_settings.append(ConditionalSettingEntry(
            declare_id="inner", fs_type="opensiddur:hebrew-date", feature_name="day",
            value=Undefined, source="declared"))
        recalculate_derived_settings(self.linear_data, trigger=SettingChangeTrigger.DECLARE,
                                     declare_id="inner")
        self.assertIsNone(get_active_setting_entry(self.linear_data, "opensiddur:holiday", "pesah"))

    def test_a_declared_hebrew_date_does_not_warn(self):
        with self.assertNoLogs("opensiddur.exporter.derived_settings", level="WARNING"):
            CompilerProcessor.load_init_settings(
                self.linear_data,
                yaml_to_declaration_entries({
                    "opensiddur:gregorian-date": {"year": 2024, "month": 10, "day": 3},
                    "opensiddur:hebrew-date": {"year": 5785, "month": 7, "day": 1},
                }),
            )

    def test_a_date_without_a_place_warns(self):
        with self.assertLogs("opensiddur.exporter.derived_settings", level="WARNING") as logs:
            CompilerProcessor.load_init_settings(
                self.linear_data,
                yaml_to_declaration_entries({
                    "opensiddur:gregorian-date": {"year": 2024, "month": 10, "day": 3},
                }),
            )
        self.assertIn("opensiddur:location", logs.output[0])

    def test_hebrew_date_requires_location(self):
        CompilerProcessor.load_init_settings(
            self.linear_data,
            yaml_to_declaration_entries({
                "opensiddur:gregorian-date": {"year": 2024, "month": 10, "day": 3},
            }),
        )
        self.assertIsNone(
            get_active_setting_entry(self.linear_data, "opensiddur:hebrew-date", "year")
        )

    def test_hebrew_date_derived_with_location(self):
        CompilerProcessor.load_init_settings(
            self.linear_data,
            yaml_to_declaration_entries({
                "opensiddur:gregorian-date": {"year": 2024, "month": 10, "day": 3},
                "opensiddur:location": {"latitude": 31.78, "longitude": 35.22},
            }),
        )
        self.assertEqual(
            get_active_setting_entry(self.linear_data, "opensiddur:hebrew-date", "year").value,
            5785,
        )
        self.assertEqual(
            get_active_setting_entry(self.linear_data, "opensiddur:hebrew-date", "month").value,
            7,
        )
        self.assertEqual(
            get_active_setting_entry(self.linear_data, "opensiddur:hebrew-date", "day").value,
            1,
        )

    def test_explicit_hebrew_date_wins_over_derived(self):
        CompilerProcessor.load_init_settings(
            self.linear_data,
            yaml_to_declaration_entries({
                "opensiddur:gregorian-date": {"year": 2024, "month": 10, "day": 3},
                "opensiddur:location": {"latitude": 31.78, "longitude": 35.22},
                "opensiddur:hebrew-date": {"year": 5784, "month": 1, "day": 15},
            }),
        )
        entry = get_active_setting_entry(self.linear_data, "opensiddur:hebrew-date", "year")
        self.assertEqual(entry.source, "init")
        self.assertEqual(entry.value, 5784)

    def test_end_declare_restores_prior_derived(self):
        self.proc = _make_processor()
        self.proc._push_declare(
            "A",
            [self._entry("A", "opensiddur:gregorian-date", "year", 2024)],
        )
        self.proc._push_declare(
            "A",
            [
                self._entry("A", "opensiddur:gregorian-date", "month", 10),
                self._entry("A", "opensiddur:gregorian-date", "day", 3),
            ],
        )
        self.assertIsNotNone(
            get_active_setting_entry(self.proc.linear_data, "opensiddur:day-of-week", "secular-day")
        )
        self.proc._end_declare("A")
        self.assertIsNone(
            get_active_setting_entry(self.proc.linear_data, "opensiddur:day-of-week", "secular-day")
        )

    def test_contributor_removal_invalidates_derived(self):
        derived = ConditionalSettingEntry(
            declare_id=derived_declare_id("t:fs", "x"),
            fs_type="t:fs",
            feature_name="x",
            value=1,
            source="derived",
            contributors={"A"},
        )
        register_derived_entry(self.linear_data, derived)
        self.linear_data.conditional_settings = [
            e for e in self.linear_data.conditional_settings
            if not (e.source == "derived" and "A" in e.contributors)
        ]
        recalculate_derived_settings(
            self.linear_data, trigger=SettingChangeTrigger.END_DECLARE, declare_id="A"
        )


def _make_processor() -> CompilerProcessor:
    reset_linear_data()
    temp = tempfile.TemporaryDirectory()
    base = Path(temp.name)
    project_dir = base / "test_project"
    project_dir.mkdir(parents=True)
    get_linear_data().xml_cache.base_path = base
    (project_dir / "minimal.xml").write_bytes(MINIMAL_XML)
    return CompilerProcessor("test_project", "minimal.xml")


class TestDerivedSettingsIntegration(unittest.TestCase):
    def setUp(self):
        reset_linear_data()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base = Path(self.temp_dir.name)
        self.project_dir = self.base / "test_project"
        self.project_dir.mkdir(parents=True)
        get_linear_data().xml_cache.base_path = self.base

    def _write(self, name: str, content: str) -> str:
        path = self.project_dir / name
        path.write_bytes(content.encode())
        return name

    def test_declare_derives_secular_day_during_compile(self):
        body = '''
        <j:declare xml:id="s">
            <tei:fs type="opensiddur:gregorian-date">
                <tei:f name="year"><tei:numeric value="2024"/></tei:f>
                <tei:f name="month"><tei:numeric value="10"/></tei:f>
                <tei:f name="day"><tei:numeric value="3"/></tei:f>
            </tei:fs>
        </j:declare>
        <tei:p>content</tei:p>
        <j:endDeclare target="#s"/>
        '''
        fn = self._write("d.xml", _declare_xml(body).decode())
        proc = CompilerProcessor("test_project", fn)
        proc.process()
        self.assertIsNone(
            get_active_setting_entry(proc.linear_data, "opensiddur:day-of-week", "secular-day")
        )


    def test_a_hebrew_date_declared_in_a_text_prevails_within_it(self):
        """The volume's secular date is Pesah; a text declaring 1 Tishrei is Rosh Hashanah
        until its declaration ends, and Pesah again after."""
        CompilerProcessor.load_init_settings(get_linear_data(), yaml_to_declaration_entries({
            "opensiddur:gregorian-date": {"year": 2025, "month": 4, "day": 13},
            "opensiddur:location": {"latitude": 40.71, "longitude": -74.01},
        }))

        def on(holiday, text):
            return (f'<j:conditional xml:id="{text}"><tei:fs type="opensiddur:holiday">'
                    f'<tei:f name="{holiday}"><tei:numeric value="1"/></tei:f></tei:fs>'
                    f'</j:conditional><tei:p>{text}</tei:p><j:endConditional target="#{text}"/>')

        body = ('<j:declare xml:id="h"><tei:fs type="opensiddur:hebrew-date">'
                '<tei:f name="year"><tei:numeric value="5786"/></tei:f>'
                '<tei:f name="month"><tei:numeric value="7"/></tei:f>'
                '<tei:f name="day"><tei:numeric value="1"/></tei:f></tei:fs></j:declare>'
                + on("rosh-hashana", "inside_rh") + on("pesah", "inside_pesah")
                + '<j:endDeclare target="#h"/>' + on("pesah", "after_pesah"))
        fn = self._write("d.xml", _declare_xml(body).decode())
        text = "".join(CompilerProcessor("test_project", fn).process().itertext())
        self.assertIn("inside_rh", text)
        self.assertNotIn("inside_pesah", text)
        self.assertIn("after_pesah", text)


class TestGoldenCalendarDates(unittest.TestCase):
    """Phase B golden-date fixtures."""

    def setUp(self):
        reset_linear_data()
        self.linear_data = get_linear_data()

    def _load(self, declarations: dict) -> None:
        CompilerProcessor.load_init_settings(
            self.linear_data,
            yaml_to_declaration_entries(declarations),
        )

    def test_rosh_hashana_2024(self):
        self._load({
            "opensiddur:gregorian-date": {"year": 2024, "month": 10, "day": 3},
            "opensiddur:location": {"latitude": 31.78, "longitude": 35.22},
        })
        holidays = {
            entry.feature_name: entry.value
            for entry in self.linear_data.conditional_settings
            if entry.fs_type == "opensiddur:holiday" and entry.source == "derived"
        }
        self.assertEqual(holidays.get("rosh-hashana"), 1)
        self.assertEqual(holidays.get("pesah"), 0)

    def test_pesach_first_day_2024(self):
        self._load({
            "opensiddur:gregorian-date": {"year": 2024, "month": 4, "day": 23},
            "opensiddur:location": {"latitude": 40.71, "longitude": -74.01},
        })
        entry = get_active_setting_entry(self.linear_data, "opensiddur:holiday", "pesah")
        self.assertEqual(entry.value, 1)

    def test_holiday_aggregate_shabbat(self):
        self._load({
            "opensiddur:gregorian-date": {"year": 2024, "month": 4, "day": 20},
            "opensiddur:location": {"latitude": 40.71, "longitude": -74.01},
        })
        entry = get_active_setting_entry(self.linear_data, "opensiddur:holiday-aggregate", "shabbat")
        self.assertTrue(entry.value)

    def test_purim_is_celebrated_on_the_fourteenth_unless_the_volume_says_otherwise(self):
        # 15 Adar 5786 is 4 March 2026: Shushan Purim.
        shushan_purim = {
            "opensiddur:gregorian-date": {"year": 2026, "month": 3, "day": 4},
            "opensiddur:location": {"latitude": 31.78, "longitude": 35.22},
        }
        for declared, expected in (({}, 0), ({"opensiddur:purim-observance": {"day": 15}}, 1)):
            with self.subTest(declared=declared):
                reset_linear_data()
                self.linear_data = get_linear_data()
                self._load({**shushan_purim, **declared})
                entry = get_active_setting_entry(
                    self.linear_data, "opensiddur:holiday", "purim-observed")
                self.assertEqual(entry.value, expected)

    def test_timezone_is_derived_from_the_coordinates(self):
        self._load({
            "opensiddur:location": {"latitude": 40.71, "longitude": -74.01},
        })
        entry = get_active_setting_entry(self.linear_data, "opensiddur:location", "timezone")
        self.assertEqual(entry.value, "America/New_York")
        self.assertEqual(entry.source, "derived")

    def test_declared_timezone_beats_the_derived_one(self):
        self._load({
            "opensiddur:location": {
                "latitude": 40.71,
                "longitude": -74.01,
                "timezone": "UTC",
            },
        })
        entry = get_active_setting_entry(self.linear_data, "opensiddur:location", "timezone")
        self.assertEqual(entry.value, "UTC")
        self.assertNotEqual(entry.source, "derived")

    def test_local_evening_rolls_the_hebrew_date_over(self):
        """The reported case: a New York seder at 8:30pm on 1 April 2026 is 15 Nisan."""
        self._load({
            "opensiddur:gregorian-date": {"year": 2026, "month": 4, "day": 1},
            "opensiddur:time": {"hour": 20, "minute": 30},
            "opensiddur:location": {"latitude": 40.71, "longitude": -74.01},
        })
        self.assertEqual(
            get_active_setting_entry(self.linear_data, "opensiddur:hebrew-date", "day").value, 15
        )
        self.assertEqual(
            get_active_setting_entry(self.linear_data, "opensiddur:holiday", "pesah").value, 1
        )

    def test_a_triennial_variation_condition_selects_on_the_declared_date(self):
        """The condition the humash puts on the twelve doubled parshiyot, end to end.

        A parshah that is sometimes read with its partner divides differently depending on how
        the pair fell across the cycle, so each division is conditioned on the patterns that
        select it. With a date declared, only the live one survives.
        """
        def condition(*patterns: str):
            alternatives = "".join(
                f'<tei:fs type="opensiddur:torah-reading">'
                f'<tei:f name="triennial-pattern-vayakhel-pekudei">'
                f"<tei:string>{pattern}</tei:string></tei:f></tei:fs>"
                for pattern in patterns
            )
            element = etree.fromstring(
                f'<j:conditional xmlns:j="{J}" xmlns:tei="{TEI}" xml:id="c">'
                f"<j:any>{alternatives}</j:any></j:conditional>".encode()
            )
            return parse_condition_element(element)

        processor = CompilerProcessor.__new__(CompilerProcessor)
        processor.linear_data = self.linear_data

        # Undeclared, every variation is kept, the way an undeclared rite keeps every rite.
        self.assertEqual(evaluate_condition(condition("TSS"), processor), TriState.UNDEFINED)

        # 5786 opens a cycle in which the pair falls together, apart, together.
        self._load({"opensiddur:gregorian-date": {"year": 2025, "month": 11, "day": 1}})
        self.assertEqual(evaluate_condition(condition("TST"), processor), TriState.TRUE)
        self.assertEqual(
            evaluate_condition(condition("TSS", "SSS"), processor), TriState.FALSE
        )

    def test_torah_reading_parsha(self):
        self._load({
            "opensiddur:gregorian-date": {"year": 2024, "month": 10, "day": 3},
        })
        diaspora = get_active_setting_entry(
            self.linear_data, "opensiddur:torah-reading", "diaspora-parsha"
        )
        self.assertEqual(diaspora.value, "haazinu")

    def test_yaml_init_full_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            project_dir = project_root / "proj-a"
            project_dir.mkdir()
            (project_dir / "minimal.xml").write_bytes(MINIMAL_XML)
            settings_path = project_root / "settings.yaml"
            with open(settings_path, "w") as f:
                yaml.dump({
                    "priority": {"transclusion": ["proj-a"], "instructions": ["proj-a"]},
                    "declarations": {
                        "opensiddur:gregorian-date": {"year": 2024, "month": 10, "day": 3},
                        "opensiddur:location": {"latitude": 31.78, "longitude": 35.22},
                    },
                }, f)
            load_settings(settings_path, project_directory=project_root)
            ld = get_linear_data()
            self.assertEqual(
                get_active_setting_entry(ld, "opensiddur:hebrew-date", "day").value,
                1,
            )




class TestTheDayCelebratedAsPurimInADocument(unittest.TestCase):
    """A document may say which day it celebrates as Purim for a stretch of its text."""

    JERUSALEM = {"latitude": 31.78, "longitude": 35.22}
    # 14 and 15 Adar II 5787.
    PURIM, SHUSHAN_PURIM = {"year": 2027, "month": 3, "day": 23}, {"year": 2027, "month": 3, "day": 24}

    def _processor(self, date, **declarations):
        proc = _make_processor()
        self.addCleanup(reset_linear_data)
        CompilerProcessor.load_init_settings(proc.linear_data, yaml_to_declaration_entries({
            "opensiddur:gregorian-date": date, "opensiddur:location": self.JERUSALEM,
            **declarations}))
        return proc

    def _observed(self, proc):
        return get_active_setting_entry(
            proc.linear_data, "opensiddur:holiday", "purim-observed").value

    def test_a_declaration_changes_the_day_until_it_ends(self):
        for date, inside, outside in ((self.PURIM, 0, 1), (self.SHUSHAN_PURIM, 1, 0)):
            with self.subTest(date=date):
                proc = self._processor(date)
                proc._push_declare("walled", [ConditionalSettingEntry(
                    declare_id="walled", fs_type="opensiddur:purim-observance",
                    feature_name="day", value=15, source="declared")])
                self.assertEqual(self._observed(proc), inside)
                proc._end_declare("walled")
                self.assertEqual(self._observed(proc), outside)

    def test_bein_hashmashot_holds_both_days(self):
        for day, expected in ((14, TwilightValue(ending=1, starting=0)),
                              (15, TwilightValue(ending=0, starting=1))):
            with self.subTest(day=day):
                proc = self._processor(
                    self.PURIM, **{"opensiddur:time": {"hour": 18, "minute": 5},
                                   "opensiddur:purim-observance": {"day": day}})
                self.assertEqual(self._observed(proc), expected)

class TestTheLastDateDeclaredPrevails(unittest.TestCase):
    """JLPTEI-3: if both the secular and the Hebrew date are set, the last setting prevails."""

    NEW_YORK = {"latitude": 40.71, "longitude": -74.01}

    def setUp(self):
        reset_linear_data()
        self.linear_data = get_linear_data()
        self.addCleanup(reset_linear_data)

    def _load(self, declarations: dict) -> None:
        CompilerProcessor.load_init_settings(
            self.linear_data, yaml_to_declaration_entries(declarations))

    def _value(self, fs_type: str, feature: str):
        entry = get_active_setting_entry(self.linear_data, fs_type, feature)
        return None if entry is None else entry.value

    def _hebrew_date(self):
        return tuple(self._value("opensiddur:hebrew-date", f) for f in ("year", "month", "day"))

    def _gregorian_date(self):
        return tuple(self._value("opensiddur:gregorian-date", f) for f in ("year", "month", "day"))

    def test_a_later_hebrew_date_moves_the_secular_date(self):
        self._load({
            "opensiddur:gregorian-date": {"year": 2025, "month": 4, "day": 13},
            "opensiddur:location": self.NEW_YORK,
            "opensiddur:hebrew-date": {"year": 5786, "month": 7, "day": 1},
        })
        self.assertEqual((5786, 7, 1), self._hebrew_date())
        self.assertEqual((2025, 9, 23), self._gregorian_date())
        self.assertEqual(1, self._value("opensiddur:holiday", "rosh-hashana"))
        self.assertEqual(0, self._value("opensiddur:holiday", "pesah"))

    def test_a_later_secular_date_moves_the_hebrew_date(self):
        self._load({
            "opensiddur:hebrew-date": {"year": 5786, "month": 7, "day": 1},
            "opensiddur:location": self.NEW_YORK,
            "opensiddur:gregorian-date": {"year": 2025, "month": 4, "day": 13},
        })
        self.assertEqual((5785, 1, 15), self._hebrew_date())
        self.assertEqual((2025, 4, 13), self._gregorian_date())
        self.assertEqual(1, self._value("opensiddur:holiday", "pesah"))

    def test_a_hebrew_date_at_an_evening_hour_is_the_evening_before_its_day(self):
        self._load({
            "opensiddur:gregorian-date": {"year": 2025, "month": 9, "day": 23},
            "opensiddur:location": self.NEW_YORK,
            "opensiddur:time": {"hour": 21, "minute": 0},
            "opensiddur:hebrew-date": {"year": 5785, "month": 1, "day": 15},
        })
        self.assertEqual((2025, 4, 12), self._gregorian_date())
        self.assertEqual((5785, 1, 15), self._hebrew_date())

    def test_a_later_partial_hebrew_date_takes_the_rest_from_the_secular_one(self):
        """Settled when the volume is loaded, not at the next declaration."""
        self._load({
            "opensiddur:gregorian-date": {"year": 2025, "month": 4, "day": 13},
            "opensiddur:location": self.NEW_YORK,
            "opensiddur:hebrew-date": {"year": 5790},
        })
        self.assertEqual((5790, 1, 15), self._hebrew_date())
        self.assertEqual((2030, 4, 18), self._gregorian_date())

    def test_a_later_secular_date_without_a_place_leaves_the_hebrew_date_undefined(self):
        """It overrides the Hebrew date but cannot give one: neither date may be mixed in."""
        with self.assertLogs("opensiddur.exporter.derived_settings", "WARNING") as logs:
            self._load({
                "opensiddur:hebrew-date": {"year": 5786, "month": 7, "day": 1},
                "opensiddur:gregorian-date": {"year": 2025, "month": 4, "day": 13},
            })
        self.assertEqual((Undefined,) * 3, self._hebrew_date())
        self.assertIn(self._value("opensiddur:holiday", "pesah"), (None, Undefined))
        self.assertIn(self._value("opensiddur:holiday", "rosh-hashana"), (None, Undefined))
        self.assertEqual(1, sum("without an opensiddur:location" in line for line in logs.output))

    def test_a_later_hebrew_date_that_is_not_a_date_leaves_the_secular_one_undefined(self):
        with self.assertLogs("opensiddur.exporter.derived_settings", "WARNING"):
            self._load({
                "opensiddur:gregorian-date": {"year": 2025, "month": 4, "day": 13},
                "opensiddur:location": self.NEW_YORK,
                "opensiddur:hebrew-date": {"year": 5786, "month": 13, "day": 1},
            })
        self.assertEqual((Undefined,) * 3, self._gregorian_date())
        self.assertIn(self._value("opensiddur:holiday", "pesah"), (None, Undefined))

    def test_a_hebrew_date_alone_is_left_as_it_was(self):
        self._load({"opensiddur:hebrew-date": {"year": 5785, "month": 1, "day": 15}})
        self.assertEqual((None, None, None), self._gregorian_date())
        self.assertEqual((5785, 1, 15), self._hebrew_date())


if __name__ == "__main__":
    unittest.main()
