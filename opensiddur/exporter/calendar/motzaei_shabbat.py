"""Saturday-night omissions based on the six coming working days."""
import hdate
from pyluach.dates import HebrewDate

from .compute import FS_HEBREW_DATE, SettingSnapshot

FS_MOTZAEI_SHABBAT = 'opensiddur:motzaei-shabbat'


def omit_vihi_noam(day: HebrewDate, *, israel: bool) -> bool:
    """Omit for Yom Tov in this Hebrew week's Sunday–Friday.

    Saturday night is already Sunday in the Hebrew calendar. A festival on the
    following Sabbath alone does not interrupt the six working days. A date that is itself
    Shabbat -- a Hebrew date declared without a time -- looks to the week that follows it,
    the one its Saturday night begins.
    """
    sunday = day + 1 if day.weekday() == 7 else day - (day.weekday() - 1)
    for offset in range(6):
        upcoming = sunday + offset
        if hdate.HDateInfo(upcoming.to_greg().to_pydate(), diaspora=not israel).is_yom_tov:
            return True
    return False


def compute_motzaei_shabbat(snapshot: SettingSnapshot):
    values = [snapshot.get_int(FS_HEBREW_DATE, key) for key in ('year', 'month', 'day')]
    israel = snapshot.in_israel()
    if None in values or israel is None:
        return None
    try:
        day = HebrewDate(*values)
    except ValueError:
        return None
    return {'omit-vihi-noam': omit_vihi_noam(day, israel=israel)}
