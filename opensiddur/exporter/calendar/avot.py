"""Independent Pirkei Avot chapter selectors for the summer reading cycle.

Schedule reference: https://github.com/hebcal/learning/tree/main/pirkeiavot
Three complete single-chapter rounds are followed by the final compressed round.
The computation uses pyluach locally; no network or stored yearly schedule is needed.
"""
from pyluach.dates import HebrewDate

from .compute import FS_HEBREW_DATE, SettingSnapshot

FS_AVOT = 'opensiddur:pirkei-avot'


def chapters_on(day: HebrewDate, *, israel: bool) -> tuple[int, ...]:
    """Weekly cycle, skipping festivals and Shabbat on 8/9 Av."""
    end=HebrewDate(day.year+1,7,1)
    start=HebrewDate(day.year,1,21 if israel else 22)
    if day.weekday()!=7 or not start<day<end:return ()
    eligible=[]
    current=start+1
    while current<end:
        if current.weekday()==7 and not (
            (current.month==3 and current.day in ((6,) if israel else (6,7)))
            or (current.month==5 and current.day in (8,9))
        ):eligible.append(current)
        current+=1
    if day not in eligible:return ()
    index=eligible.index(day)
    if index<18:return (index%6+1,)
    # The last two Sabbaths read 3–4 and 5–6. If there are four weeks
    # in the final round, chapters 1 and 2 each have their own week.
    remain=len(eligible)-index
    if remain==1:return (5,6)
    if remain==2:return (3,4)
    if remain==3:return (2,) if index==19 else (1,2)
    if remain==4:return (1,)
    raise ValueError('Unexpected number of Sabbaths in the Avot season')


def compute_avot(snapshot: SettingSnapshot):
    values=[snapshot.get_int(FS_HEBREW_DATE,k) for k in ('year','month','day')]
    israel=snapshot.in_israel()
    # Unknown locale must not silently select the Diaspora chapter. All
    # selectors remain MAYBE until their inputs are known or explicitly set.
    if None in values or israel is None:return None
    try:day=HebrewDate(*values)
    except ValueError:return None
    selected=chapters_on(day,israel=israel)
    # The printed seasonal rubric is intentionally broader than the weekly
    # cycle. An independently selected chapter still works on every date.
    start=HebrewDate(day.year,1,21 if israel else 22)
    end=HebrewDate(day.year+1,7,1)
    return {'season':day.weekday()==7 and start<day<end,
            **{f'chapter-{n}':n in selected for n in range(1,7)}}
