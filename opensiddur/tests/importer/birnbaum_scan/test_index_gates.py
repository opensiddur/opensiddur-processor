"""The occasions the Birnbaum running order gates its sections on (opensiddur-processor#228).

Each section said only on some days is conditioned where index.py transcludes it. These tests
read the gates off the generated index, and decide them against what the calendar derives for
dates of known character -- no project data is read.
"""

import json
import unittest

import yaml
from lxml import etree

from opensiddur.exporter.client_settings import resolve
from opensiddur.exporter.condition_eval import TriState, parse_condition_element
from opensiddur.exporter.html.kinds_of_day import OUTPUT as KINDS_OF_DAY
from opensiddur.importer.birnbaum_scan.build.common import PROJECT_HE, SIDDUR
from opensiddur.importer.birnbaum_scan.build.index import index
from opensiddur.tests.importer.occasion_support import NEW_YORK, CalendarDay

J = "http://jewishliturgy.org/ns/jlptei/2"
TEI = "http://www.tei-c.org/ns/1.0"
NS = {"j": J, "tei": TEI}
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"

TRUE, FALSE, UNDEFINED = TriState.TRUE, TriState.FALSE, TriState.UNDEFINED


def _index() -> etree.ElementBase:
    return etree.fromstring(index(project=PROJECT_HE, lang="he", front="").encode())


def _gates(root: etree.ElementBase) -> dict[str, etree.ElementBase]:
    """Each transcluded section's innermost enclosing gate, by the section's path."""
    found = {}
    for transclude in root.iterfind(".//j:transclude", NS):
        target = transclude.get("target").removeprefix(SIDDUR)
        open_scopes: list[etree.ElementBase] = []
        for element in transclude.itersiblings(preceding=True):
            if element.tag == f"{{{J}}}endConditional":
                open_scopes.append(None)
            elif element.tag == f"{{{J}}}conditional":
                if open_scopes and open_scopes[-1] is None:
                    open_scopes.pop()
                else:
                    found[target] = element
                    break
    return found


class TestTheGates(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.root = _index()
        cls.gates = _gates(cls.root)

    def test_every_occasion_s_section_is_gated(self):
        for section in ("chol/shacharit", "chol/minchah", "chol/arvit",
                        "shabbat/preparations", "shabbat/qabbalat_service", "shabbat/arvit",
                        "shabbat/leil_shabbat", "shabbat/shacharit", "shabbat/musaf",
                        "shabbat/day_meal", "shabbat/minchah", "shabbat/conclusion",
                        "berakhot/birkat_halevanah", "hallel", "rosh_chodesh/musaf", "regalim",
                        "yizkor", "regalim/musaf", "regalim/morning_meal", "sefirat_haomer",
                        "regalim/aqdamut", "rosh_hashanah/minchah_maariv_and_rites",
                        "sukkot/rites", "chanukah", "purim"):
            with self.subTest(section):
                self.assertIn(section, self.gates)

    def test_sections_said_on_any_day_are_not_gated(self):
        """The life-cycle services turn on opensiddur:override, which is false when undefined:
        a gate on it would take them out of every edition that names no occasion."""
        for section in ("lifecycle", "concluding_prayers"):
            with self.subTest(section):
                self.assertNotIn(section, self.gates)

    def test_a_gate_says_nothing_to_the_reader(self):
        for section, gate in self.gates.items():
            if not gate.get(XML_ID).startswith("occasion_"):
                continue
            with self.subTest(section):
                self.assertIsNone(gate.find("tei:note", NS))
                self.assertIsNone(gate.get("type"))

    def test_pirqei_avot_is_inside_the_sabbath_minha_gate(self):
        gate = self.gates["shabbat/minchah"]
        avot = self.root.xpath(".//j:conditional[@xml:id='avot_season']", namespaces=NS)[0]
        self.assertIn(avot, list(gate.itersiblings()))
        closer = self.root.find(".//j:endConditional[@target='#occasion_shabbat_minchah']", NS)
        self.assertIn(closer, list(avot.itersiblings()))

    def _declared(self, section: str) -> dict[tuple[str, str], str]:
        gate = self.gates[section]
        declare = gate.getnext()
        if declare is None or declare.tag != f"{{{J}}}declare":
            return {}
        return {(fs.get("type"), f.get("name")): (f[0].get("value"))
                for fs in declare.iterfind("tei:fs", NS) for f in fs.iterfind("tei:f", NS)}

    def test_aqdamut_declares_the_first_day_of_shavuot(self):
        self.assertEqual(self._declared("regalim/aqdamut"),
                         {("opensiddur:holiday", "shavuot"): "1"})

    def test_the_weekday_services_declare_the_kind_of_day(self):
        self.assertEqual(self._declared("chol/arvit"), {
            ("opensiddur:holiday-aggregate", "shabbat"): "false",
            ("opensiddur:holiday-aggregate", "yom-tov"): "false",
            ("opensiddur:service-time", "maariv"): "true",
        })

    def test_the_sabbath_services_that_serve_festivals_declare_no_occasion(self):
        """Declaring shabbat=true in them would drop their festival text."""
        for section in ("shabbat/arvit", "shabbat/shacharit", "shabbat/musaf",
                        "shabbat/minchah"):
            with self.subTest(section):
                self.assertNotIn(("opensiddur:holiday-aggregate", "shabbat"),
                                 self._declared(section))

    def test_hanukkah_declares_nothing_it_does_not_fix(self):
        self.assertEqual(self._declared("chanukah"), {})


class TestTheGatesAgainstTheCalendar(unittest.TestCase):
    """Whether each section is kept on a day of known character."""

    @classmethod
    def setUpClass(cls):
        cls.gates = _gates(_index())

    def _assert_days(self, day: CalendarDay, expected: dict[str, TriState]):
        for section, state in expected.items():
            with self.subTest(section):
                self.assertEqual(day.decide(self.gates[section]), state)

    def test_an_ordinary_monday(self):
        """16 November 2026, 6 Kislev: no Sabbath, festival, Rosh Hodesh or Hanukkah. With no
        time given, every weekday service is left in; nothing for another day is."""
        self._assert_days(CalendarDay(date=(2026, 11, 16)), {
            "chol/shacharit": UNDEFINED, "chol/minchah": UNDEFINED, "chol/arvit": UNDEFINED,
            "shabbat/preparations": FALSE, "shabbat/qabbalat_service": FALSE,
            "shabbat/arvit": FALSE, "shabbat/leil_shabbat": FALSE, "shabbat/shacharit": FALSE,
            "shabbat/musaf": FALSE, "shabbat/day_meal": FALSE, "shabbat/minchah": FALSE,
            "shabbat/conclusion": FALSE, "hallel": FALSE, "rosh_chodesh/musaf": FALSE,
            "regalim": FALSE, "yizkor": FALSE, "regalim/musaf": FALSE,
            "regalim/morning_meal": FALSE, "sefirat_haomer": FALSE, "regalim/aqdamut": FALSE,
            "rosh_hashanah/minchah_maariv_and_rites": FALSE, "sukkot/rites": FALSE,
            "chanukah": FALSE, "purim": FALSE,
            "berakhot/birkat_halevanah": TRUE,
        })

    def test_an_ordinary_monday_morning(self):
        self._assert_days(CalendarDay(date=(2026, 11, 16), time=(8, 0)), {
            "chol/shacharit": TRUE, "chol/minchah": FALSE, "chol/arvit": FALSE,
        })

    def test_a_sabbath(self):
        """21 November 2026, 11 Kislev. Without a time the evening sections stay undecided; Saturday night is a separate Hebrew day."""
        self._assert_days(CalendarDay(date=(2026, 11, 21)), {
            "chol/shacharit": FALSE, "chol/minchah": FALSE, "chol/arvit": FALSE,
            "shabbat/preparations": UNDEFINED, "shabbat/qabbalat_service": UNDEFINED,
            "shabbat/arvit": UNDEFINED, "shabbat/leil_shabbat": UNDEFINED,
            "shabbat/shacharit": UNDEFINED, "shabbat/musaf": UNDEFINED, "shabbat/day_meal": UNDEFINED,
            "shabbat/minchah": UNDEFINED, "shabbat/conclusion": FALSE,
            "regalim": FALSE, "hallel": FALSE,
        })

    def test_shmini_atzeret_on_shabbat_at_nine(self):
        self._assert_days(CalendarDay(date=(2023, 10, 7), time=(9, 0), place=NEW_YORK), {
            "all/shacharit/yeladim": TRUE, "shabbat/shacharit": TRUE,
            "shabbat/musaf": TRUE, "regalim/musaf": TRUE, "hallel": TRUE,
            "shabbat/qabbalat_service": FALSE, "shabbat/preparations": FALSE,
            "shabbat/arvit": FALSE, "shabbat/leil_shabbat": FALSE,
            "shabbat/conclusion": FALSE,
        })

    def test_saturday_night_is_a_weekday_with_havdalah(self):
        self._assert_days(CalendarDay(date=(2026, 11, 21), time=(20, 0)), {
            "chol/arvit": TRUE, "shabbat/arvit": FALSE, "shabbat/conclusion": TRUE,
            "shabbat/qabbalat_service": FALSE,
        })

    def test_friday_is_for_the_sabbath_s_preparations(self):
        self._assert_days(CalendarDay(date=(2026, 11, 20)), {
            "shabbat/preparations": UNDEFINED, "shabbat/qabbalat_service": UNDEFINED,
            "shabbat/arvit": FALSE, "chol/shacharit": UNDEFINED,
        })

    def test_friday_evening_is_the_sabbath(self):
        self._assert_days(CalendarDay(date=(2026, 11, 20), time=(20, 0)), {
            "chol/arvit": FALSE, "shabbat/arvit": TRUE, "shabbat/qabbalat_service": TRUE,
            "shabbat/preparations": TRUE,
        })

    def test_weekday_rosh_hodesh(self):
        """10 November 2026, 30 Heshvan: the weekday services, Hallel and Rosh Hodesh Musaf."""
        self._assert_days(CalendarDay(date=(2026, 11, 10)), {
            "chol/shacharit": UNDEFINED, "hallel": UNDEFINED, "rosh_chodesh/musaf": UNDEFINED,
            "shabbat/shacharit": FALSE, "regalim/musaf": FALSE,
        })

    def test_hanukkah(self):
        self._assert_days(CalendarDay(date=(2026, 12, 7)), {
            "chanukah": TRUE, "hallel": UNDEFINED, "chol/shacharit": UNDEFINED, "purim": FALSE,
        })

    def test_purim(self):
        self._assert_days(CalendarDay(date=(2027, 3, 23)), {
            "purim": TRUE, "chanukah": FALSE, "hallel": FALSE,
        })

    def test_the_first_day_of_shavuot(self):
        """11 June 2027, a Friday: a festival, not a weekday, and Akdamut is chanted."""
        self._assert_days(CalendarDay(date=(2027, 6, 11)), {
            "regalim/aqdamut": TRUE, "regalim": TRUE, "regalim/musaf": UNDEFINED,
            "regalim/morning_meal": UNDEFINED, "hallel": UNDEFINED, "shabbat/shacharit": UNDEFINED,
            "chol/shacharit": FALSE, "yizkor": TRUE,
            # Its prayers after Musaf are the festival's too.
            "shabbat/musaf": UNDEFINED,
        })

    def test_yizkor_is_on_the_second_day_of_shavuot_outside_israel(self):
        self._assert_days(CalendarDay(date=(2027, 6, 12), place=NEW_YORK), {"yizkor": TRUE})

    def test_hol_hamoed(self):
        """1 October 2026, the sixth of Sukkot: the weekday services, with the festival's
        Musaf, Hallel and rites."""
        self._assert_days(CalendarDay(date=(2026, 10, 1)), {
            "chol/shacharit": UNDEFINED, "regalim/musaf": UNDEFINED, "hallel": UNDEFINED,
            "sukkot/rites": TRUE, "regalim": FALSE, "regalim/morning_meal": FALSE,
            "yizkor": FALSE, "shabbat/musaf": UNDEFINED, "shabbat/shacharit": FALSE,
        })

    def test_rosh_hashanah(self):
        self._assert_days(CalendarDay(date=(2026, 9, 12)), {
            "rosh_hashanah/minchah_maariv_and_rites": TRUE, "regalim": FALSE,
            "regalim/musaf": FALSE, "hallel": FALSE, "shabbat/musaf": UNDEFINED,
        })


class TestTheGatesOnAReadersDevice(unittest.TestCase):
    """An electronic book's reader sets the day by hand: a day of the week and a kind of day.
    Set to an ordinary Monday, the book hides every Sabbath and festival section."""

    @classmethod
    def setUpClass(cls):
        cls.gates = _gates(_index())
        controls = yaml.safe_load(
            (KINDS_OF_DAY.parent / "basic_settings.yaml").read_text(encoding="utf-8"))
        days = next(c for c in controls["controls"] if c["id"] == "day-of-week")["options"]
        kinds = json.loads(KINDS_OF_DAY.read_text(encoding="utf-8"))
        cls.monday = {}
        for chosen in (next(o for o in days if o["label"] == "Monday"),
                       next(k for k in kinds if k["label"] == "An ordinary day")):
            for fs, features in chosen["set"].items():
                cls.monday.setdefault(fs, {}).update(features)

    def test_an_ordinary_monday_hides_the_sabbath_and_the_festivals(self):
        for section in ("shabbat/preparations", "shabbat/qabbalat_service", "shabbat/arvit",
                        "shabbat/leil_shabbat", "shabbat/shacharit", "shabbat/musaf",
                        "shabbat/day_meal", "shabbat/minchah", "shabbat/conclusion", "hallel",
                        "rosh_chodesh/musaf", "yizkor", "regalim/musaf", "regalim/morning_meal",
                        "regalim/aqdamut", "rosh_hashanah/minchah_maariv_and_rites",
                        "sukkot/rites", "chanukah", "purim"):
            with self.subTest(section):
                self.assertEqual(
                    resolve(parse_condition_element(self.gates[section]), reader=self.monday),
                    FALSE)

    def test_what_an_ordinary_monday_cannot_settle_is_kept(self):
        """The omer is counted, the moon blessed and an eruv tavshilin made on ordinary days,
        and no service has been chosen."""
        for section in ("chol/shacharit", "sefirat_haomer", "berakhot/birkat_halevanah",
                        "regalim"):
            with self.subTest(section):
                self.assertEqual(
                    resolve(parse_condition_element(self.gates[section]), reader=self.monday),
                    UNDEFINED)


if __name__ == "__main__":
    unittest.main()
