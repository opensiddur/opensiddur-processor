"""The full and abridged Hallel occasions printed in Birnbaum."""
from pyluach.dates import HebrewDate

from .compute import FS_HEBREW_DATE, SettingSnapshot

FS_HALLEL = 'opensiddur:hallel'


def hallel_on(day: HebrewDate, *, israel: bool) -> str:
    """Return full, half, or none; personal/service exclusions belong to callers."""
    month, date = day.month, day.day
    if 0 <= day.jd - HebrewDate(day.year, 9, 25).jd < 8:
        return 'full'
    if month == 1 and 15 <= date <= (21 if israel else 22):
        return 'full' if date <= (15 if israel else 16) else 'half'
    if month == 3 and 6 <= date <= (6 if israel else 7):
        return 'full'
    if month == 7 and 15 <= date <= (22 if israel else 23):
        return 'full'
    if date == 30 or (date == 1 and month != 7):
        return 'half'
    return 'none'


def compute_hallel(snapshot: SettingSnapshot):
    values = [snapshot.get_int(FS_HEBREW_DATE, key) for key in ('year', 'month', 'day')]
    israel = snapshot.in_israel()
    if None in values or israel is None:
        return None
    try:
        mode = hallel_on(HebrewDate(*values), israel=israel)
    except ValueError:
        return None
    return {'recite': mode != 'none', 'full': mode == 'full'}
