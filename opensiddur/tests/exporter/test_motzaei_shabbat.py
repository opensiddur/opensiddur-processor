"""Upcoming-week conditions for Birnbaum's Saturday-night additions."""
import unittest
from pyluach.dates import HebrewDate
from opensiddur.exporter.calendar.motzaei_shabbat import omit_vihi_noam, compute_motzaei_shabbat
from opensiddur.exporter.calendar.compute import SettingSnapshot, FS_HEBREW_DATE, FS_ISRAEL
from opensiddur.importer.birnbaum_scan.build.common import PROJECT_EN, PROJECT_HE


class TestMotzaeiShabbat(unittest.TestCase):
    def test_ordinary_week(self):
        self.assertFalse(omit_vihi_noam(HebrewDate(5784, 2, 4), israel=True))

    def test_erev_pesach_alone_does_not_omit(self):
        day = HebrewDate(5782, 1, 9)
        self.assertEqual(day.weekday(), 1)
        for israel in (True, False):
            self.assertFalse(omit_vihi_noam(day, israel=israel))

    def test_pesach_during_the_week_omits(self):
        day = HebrewDate(5784, 1, 13)
        self.assertEqual(day.weekday(), 1)
        for israel in (True, False):
            self.assertTrue(omit_vihi_noam(day, israel=israel))

    def test_festival_only_on_following_shabbat(self):
        # Rosh Hashanah 5784 begins on Shabbat; the preceding week is complete.
        day = HebrewDate(5783, 6, 24)
        self.assertEqual(day.weekday(), 1)
        self.assertFalse(omit_vihi_noam(day, israel=False))

    def test_diaspora_second_day_on_sunday(self):
        # Shavuot 5781 began on Monday, so both locales omit.
        self.assertTrue(omit_vihi_noam(HebrewDate(5781, 3, 5), israel=True))
        # Pesach ends on Shabbat in Israel and Sunday in the Diaspora in 5781.
        day = HebrewDate(5781, 1, 22)
        self.assertEqual(day.weekday(), 1)
        self.assertFalse(omit_vihi_noam(day, israel=True))
        self.assertTrue(omit_vihi_noam(day, israel=False))

    def test_a_shabbat_date_looks_to_the_week_that_follows(self):
        # 12 Nisan 5784 is Shabbat, and Pesah begins on the Tuesday after it.
        day = HebrewDate(5784, 1, 12)
        self.assertEqual(day.weekday(), 7)
        for israel in (True, False):
            self.assertTrue(omit_vihi_noam(day, israel=israel))

    def test_unknown_date_or_locale_stays_maybe(self):
        self.assertIsNone(compute_motzaei_shabbat(SettingSnapshot(lambda f, k: None)))
        values = {'year': 5784, 'month': 2, 'day': 4}
        self.assertIsNone(compute_motzaei_shabbat(SettingSnapshot(
            lambda f, k: values.get(k) if f == FS_HEBREW_DATE else None)))

    def test_snapshot_uses_hebrew_night_date(self):
        values = {'year': 5781, 'month': 1, 'day': 22}
        result = compute_motzaei_shabbat(SettingSnapshot(
            lambda f, k: values.get(k) if f == FS_HEBREW_DATE else
            False if (f, k) == (FS_ISRAEL, 'is-israel') else None))
        self.assertEqual(result, {'omit-vihi-noam': True})


    def test_rule_is_registered_with_calendar_derivation(self):
        from opensiddur.exporter.calendar.motzaei_shabbat import FS_MOTZAEI_SHABBAT
        from opensiddur.exporter.conditional_settings import yaml_to_declaration_entries
        from opensiddur.exporter.derived_settings import (
            recalculate_derived_settings, SettingChangeTrigger, get_active_setting_entry)
        from opensiddur.exporter.linear import reset_linear_data, get_linear_data

        for year, month, day, israel, expected in (
            (5782, 1, 9, True, False),
            (5784, 1, 13, True, True),
            (5781, 1, 22, True, False),
            (5781, 1, 22, False, True),
        ):
            reset_linear_data()
            try:
                state = get_linear_data()
                state.conditional_settings.extend(yaml_to_declaration_entries({
                    FS_HEBREW_DATE: dict(year=year, month=month, day=day),
                    FS_ISRAEL: {'is-israel': israel},
                }))
                recalculate_derived_settings(state, trigger=SettingChangeTrigger.INIT)
                entry = get_active_setting_entry(state, FS_MOTZAEI_SHABBAT, 'omit-vihi-noam')
                self.assertIsNotNone(entry)
                self.assertIs(entry.value, expected)
            finally:
                reset_linear_data()


class TestMotzaeiEncoding(unittest.TestCase):
    def test_prayer_and_unit_output_names_do_not_collide(self):
        # The Hamavdil blessing and hymn are distinct texts; a collision silently
        # overwrites one during regeneration and leaves its URN unresolved.
        from opensiddur.importer.birnbaum_scan.build import build_he, build_en
        for module in (build_he, build_en):
            language = 'he' if module is build_he else 'en'
            project = {'he': PROJECT_HE, 'en': PROJECT_EN}[language]
            from opensiddur.importer.birnbaum_scan.build.motzaei_shabbat import units
            names = [p['name'] for p in module.PRAYERS]
            names += [p['name'] for p in units(project, module.BY_NAME)]
            self.assertEqual(len(names), len(set(names)), language)

    def test_printed_kaddish_retains_its_own_titkabal(self):
        from lxml import etree
        from opensiddur.importer.birnbaum_scan.build import build_he, build_en
        from opensiddur.importer.birnbaum_scan.build.motzaei_shabbat import units, ROOT
        ns = {'tei': 'http://www.tei-c.org/ns/1.0'}
        for language, module, expected in (
            ('he', build_he, 'תִּתְקַבַּל'),
            ('en', build_en, 'whole household of Israel'),
        ):
            project = {'he': PROJECT_HE, 'en': PROJECT_EN}[language]
            body = next(u['body'] for u in units(project, module.BY_NAME)
                        if u['urn'] == ROOT + '/kaddish')
            root = etree.fromstring(('<root xmlns:tei="http://www.tei-c.org/ns/1.0" '
                'xmlns:j="http://jewishliturgy.org/ns/jlptei/2">' + body + '</root>').encode())
            self.assertIn(expected, ''.join(root.itertext()))
            self.assertTrue(root.xpath('//tei:milestone[@corresp=$urn]',
                namespaces=ns, urn=ROOT + '/kaddish/titqabbal'))
