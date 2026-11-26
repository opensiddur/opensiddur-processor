"""The day on which each of Asher's services is said, as a running-order gate.

Every gate is built from what the calendar already derives -- the Hebrew date, the Hebrew
weekday, the holidays and the Ten Days -- so a dated edition prints only that day's
Selichot and an undated one prints them all, with nothing around them.

The days before Rosh Hashanah follow the book's own rule (first-day rubric): the Selichot
begin on the Sunday before the New Year, or on the Sunday a week earlier when it falls on
Monday or Tuesday. They are not said on the Sabbath, and the days are said in order, so a
short year never reaches the later ones. Rosh Hashanah falls on only four weekdays, and
each service's gate is the union of its date over all four.
"""

from opensiddur.importer.util.occasion import (
    DAY_OF_WEEK,
    HEBREW_DATE,
    Condition,
    Feature,
    aggregate,
    all_of,
    any_of,
    gate,
    holiday,
)

ELUL, TISHREI = 6, 7
SHABBAT = 7
# 1 Tishrei is never on Sunday, Wednesday or Friday.
ROSH_HASHANAH_WEEKDAYS = (2, 3, 5, 7)
ELUL_DAYS = ('first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh')
PENITENTIAL_DAYS = ('second', 'third', 'fourth', 'fifth')
NATIVE_FASTS = {'tenth-tevet': 'asara-btevet', 'esther-fast': 'taanit-esther',
                'tammuz-fast': 'tzom-tammuz'}


def _weekday(rh_weekday, offset):
    """The Hebrew weekday `offset` days after 1 Tishrei (negative: before it)."""
    return (rh_weekday - 1 + offset) % 7 + 1


def elul_schedule(rh_weekday):
    """The (Elul date, weekday) of each Selichot day before Erev Rosh Hashanah, in order."""
    weekday = lambda day: _weekday(rh_weekday, day - 30)
    start = max(day for day in range(23, 30) if weekday(day) == 1)
    if rh_weekday in (2, 3):
        start -= 7
    return [(day, weekday(day)) for day in range(start, 29) if weekday(day) != SHABBAT]


def ten_days_schedule(rh_weekday):
    """The (Tishrei date, weekday) of Tzom Gedaliah and the four penitential days after it."""
    weekday = lambda day: _weekday(rh_weekday, day - 1)
    gedaliah = 4 if weekday(3) == SHABBAT else 3
    days = [(day, weekday(day)) for day in range(gedaliah, 9) if weekday(day) != SHABBAT]
    if len(days) != 1 + len(PENITENTIAL_DAYS):
        raise ValueError(f'{len(days) - 1} penitential days when Rosh Hashanah is on day {rh_weekday}')
    return days


def _dates(month, pairs):
    """Conditions, all true on exactly these (date, weekday) pairs of `month`, in every year."""
    pairs = sorted(set(pairs))
    weekdays = {weekday for _, weekday in pairs}
    days = [day for day, _ in pairs]
    if len(weekdays) == 1 and days[-1] - days[0] < 7:
        # One weekday in a window shorter than a week: the window names the day.
        return (Feature(HEBREW_DATE, 'month', month),
                Feature(DAY_OF_WEEK, 'hebrew-day', weekdays.pop()),
                Feature(HEBREW_DATE, 'day', days[0], days[-1] if len(days) > 1 else None))
    return (Feature(HEBREW_DATE, 'month', month),
            any_of(*(all_of(Feature(HEBREW_DATE, 'day', day), Feature(DAY_OF_WEEK, 'hebrew-day', weekday))
                     for day, weekday in pairs)))


def _elul_day(n):
    return [elul_schedule(rh)[n] for rh in ROSH_HASHANAH_WEEKDAYS if len(elul_schedule(rh)) > n]


def _penitential_day(n):
    return [ten_days_schedule(rh)[n] for rh in ROSH_HASHANAH_WEEKDAYS]


def _behab(weekday, first, last):
    """A BeHaB fast: the Monday, Thursday and Monday after the first Sabbath of Iyar or Marheshvan."""
    return all_of(any_of(Feature(HEBREW_DATE, 'month', 2), Feature(HEBREW_DATE, 'month', 8)),
                  Feature(DAY_OF_WEEK, 'hebrew-day', weekday), Feature(HEBREW_DATE, 'day', first, last))


# The eve of the New Moon, or the Thursday before it when the New Moon is on the Sabbath or
# Sunday. Not before the New Moons of Tishrei (that is Erev Rosh Hashanah), Marheshvan
# (just after the festivals), Tevet (Hanukkah) or Iyar (Nisan).
YOM_KIPPUR_KATAN = all_of(
    any_of(Feature(HEBREW_DATE, 'month', 2, 5), Feature(HEBREW_DATE, 'month', 8),
           Feature(HEBREW_DATE, 'month', 10, 13)),
    any_of(all_of(Feature(HEBREW_DATE, 'day', 29), Feature(DAY_OF_WEEK, 'hebrew-day', 1, 5)),
           all_of(Feature(HEBREW_DATE, 'day', 27, 28), Feature(DAY_OF_WEEK, 'hebrew-day', 5))))


def condition(service) -> Condition | None:
    """The gate on `service` (a day name or service key), or None for a service with no day."""
    before, during = aggregate('aseret-ymei-tshuva', False), aggregate('aseret-ymei-tshuva')
    if service in ELUL_DAYS:
        return all_of(before, *_dates(ELUL, _elul_day(ELUL_DAYS.index(service))))
    if service == 'erev-rosh-hashanah':
        return all_of(before, Feature(HEBREW_DATE, 'month', ELUL), Feature(HEBREW_DATE, 'day', 29))
    if service == 'tzom-gedaliah':
        return all_of(during, holiday('tzom-gedalia'))
    if service.startswith('penitential-'):
        return all_of(during, *_dates(TISHREI, _penitential_day(1 + PENITENTIAL_DAYS.index(service[len('penitential-'):]))))
    if service == 'erev-yom-kippur':
        return all_of(during, Feature(HEBREW_DATE, 'month', TISHREI), Feature(HEBREW_DATE, 'day', 9))
    if service == 'monday-fast':
        return _behab(2, 3, 9)
    if service == 'thursday-fast':
        return _behab(5, 6, 12)
    if service == 'last-monday-fast':
        return _behab(2, 10, 16)
    if service in NATIVE_FASTS:
        return holiday(NATIVE_FASTS[service])
    if service == 'yom-kippur-katan':
        return YOM_KIPPUR_KATAN
    if service == 'circumcision':
        # Said when a circumcision takes place, which no calendar knows. Like a life-cycle
        # service it is left ungated: a condition on opensiddur:override would count as
        # false in an edition that names no occasion, and the pizmon would vanish from it.
        return None
    raise KeyError(service)


def gated_transclusion(service, target):
    """The running-order markup transcluding `target`, behind its service's gate."""
    transclusion = f'<j:transclude target="{target}"/>'
    found = condition(service)
    if found is None:
        return [transclusion]
    name = service + '_day' if service in ELUL_DAYS else service
    opening, closing = gate(name.replace('-', '_') + '_occasion', found)
    return [opening, transclusion, closing]
