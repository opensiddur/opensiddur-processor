"""The Minchah reading advances the morning's reading, including Simchat Torah."""
import unittest

from pyluach import parshios
from pyluach.dates import HebrewDate

from opensiddur.exporter.calendar.compute import _next_weekly_parsha, _parsha_slug


class TestNextReading(unittest.TestCase):
    def test_shabbat_advances_the_reading(self):
        for israel in [False,True]:
            day=HebrewDate(5785,8,1)
            while day.weekday()!=7:day=day.add(days=1)
            self.assertEqual(_next_weekly_parsha(day,israel),_parsha_slug(parshios.getparsha_string(day.add(days=7),israel=israel)))
    def test_simchat_torah_precedes_bereshit_at_minchah(self):
        # Sweep Hebrew year forms: the next ordinary Shabbat can be after
        # Simchat Torah even when the current Shabbat is Chol HaMoed.
        for year in range(5780,5800):
            for israel in [False,True]:
                simchat=HebrewDate(year,7,22 if israel else 23)
                preceding=simchat.subtract(days=1)
                while preceding.weekday()!=7:preceding=preceding.subtract(days=1)
                following=preceding.add(days=7)
                if parshios.getparsha_string(following,israel=israel)=='Bereishis':
                    with self.subTest(year=year,israel=israel):
                        self.assertEqual(_next_weekly_parsha(preceding,israel),'vezos-haberachah')
                self.assertEqual(_next_weekly_parsha(simchat,israel),'bereishis')
    def test_shemini_atzeret_shabbat_has_different_mincha_in_israel(self):
        day=HebrewDate(5784,7,22)
        self.assertEqual(day.weekday(),7)
        self.assertEqual(_next_weekly_parsha(day,False),'vezos-haberachah')
        self.assertEqual(_next_weekly_parsha(day,True),'bereishis')
    def test_weekday_uses_upcoming_reading(self):
        day=HebrewDate(5785,8,3)
        self.assertEqual(_next_weekly_parsha(day,False),_parsha_slug(parshios.getparsha_string(day,israel=False)))
