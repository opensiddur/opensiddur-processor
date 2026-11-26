"""Hallel occasion boundaries and calendar integration."""
import unittest

from pyluach.dates import HebrewDate

from opensiddur.exporter.calendar.compute import (
    FS_HEBREW_DATE,
    FS_ISRAEL,
    SettingSnapshot,
)
from opensiddur.exporter.calendar.hallel import FS_HALLEL, compute_hallel, hallel_on


class TestHallel(unittest.TestCase):
    def test_festival_boundaries(self):
        cases=[(1,14,'none','none'),(1,15,'full','full'),(1,16,'half','full'),
               (1,17,'half','half'),(1,21,'half','half'),(1,22,'none','half'),
               (1,23,'none','none'),(3,5,'none','none'),(3,6,'full','full'),
               (3,7,'none','full'),(3,8,'none','none'),(7,14,'none','none'),
               (7,15,'full','full'),(7,21,'full','full'),(7,22,'full','full'),
               (7,23,'none','full'),(7,24,'none','none'),(7,1,'none','none'),
               (7,10,'none','none'),(12,14,'none','none')]
        for month,day,israel,diaspora in cases:
            for locale,expected in [(True,israel),(False,diaspora)]:
                with self.subTest(month=month,day=day,israel=locale):
                    self.assertEqual(hallel_on(HebrewDate(5785,month,day),israel=locale),expected)

    def test_hanukkah_overrides_both_rosh_hodesh_days(self):
        for year in (5784,5785):
            start=HebrewDate(year,9,25)
            for offset in range(-1,9):
                self.assertEqual(hallel_on(start+offset,israel=False),
                                 'full' if 0<=offset<8 else 'none')
        for month,day in [(2,1),(1,30),(3,30)]:
            self.assertEqual(hallel_on(HebrewDate(5785,month,day),israel=False),'half')

    def test_unknown_inputs_stay_maybe(self):
        self.assertIsNone(compute_hallel(SettingSnapshot(lambda f,k:None)))
        self.assertIsNone(compute_hallel(SettingSnapshot(lambda f,k:
            {'year':5785,'month':1,'day':16}.get(k) if f==FS_HEBREW_DATE else None)))

    def test_derivation_graph(self):
        from opensiddur.exporter.conditional_settings import yaml_to_declaration_entries
        from opensiddur.exporter.derived_settings import (
            SettingChangeTrigger,
            get_active_setting_entry,
            recalculate_derived_settings,
        )
        from opensiddur.exporter.linear import get_linear_data, reset_linear_data
        for israel,full in [(True,False),(False,True)]:
            reset_linear_data()
            try:
                state=get_linear_data()
                state.conditional_settings.extend(yaml_to_declaration_entries({FS_HEBREW_DATE:dict(year=5785,month=1,day=16),FS_ISRAEL:{'is-israel':israel}}))
                recalculate_derived_settings(state,trigger=SettingChangeTrigger.INIT)
                self.assertIs(get_active_setting_entry(state,FS_HALLEL,'recite').value,True)
                self.assertIs(get_active_setting_entry(state,FS_HALLEL,'full').value,full)
            finally:reset_linear_data()
