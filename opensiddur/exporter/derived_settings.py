"""Derived conditional settings (feature defaulting)."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from enum import StrEnum
from typing import Any

from pyluach import dates as pyluach_dates

from opensiddur.exporter.calendar.compute import (
    FS_GREGORIAN,
    FS_HEBREW_DATE,
    FS_PURIM_OBSERVANCE,
    FS_READING_CYCLE,
    READING_CYCLE_DEFAULTS,
    SettingSnapshot,
    _effective_gregorian_date,
)
from opensiddur.exporter.client_settings import is_reader_supplied
from opensiddur.exporter.conditional_settings import INIT_DECLARE_ID
from opensiddur.exporter.derivation_graph import (
    DerivationSpec,
    topological_derivation_order,
)
from opensiddur.exporter.linear import (
    ConditionalSettingEntry,
    LinearData,
    TwilightValue,
    Undefined,
)

logger = logging.getLogger(__name__)

FS_OVERRIDE = "opensiddur:override"
FS_PARATEXT = "opensiddur:paratext"

OVERRIDE_FEATURES = (
    "omit-tahanun",
    "house-of-mourning",
    "brit-milah",
    "wedding",
    "sheva-brachot",
)

# Features that are never computed from anything and take a fixed value unless the volume
# declares otherwise. An undeclared feature is normally *undefined*, which keeps every variant
# of a conditional text; these are the ones that instead have to answer true or false, because
# leaving them open would keep alternatives that contradict one another.
STATIC_DEFAULTS: dict[str, dict[str, Any]] = {
    FS_OVERRIDE: dict.fromkeys(OVERRIDE_FEATURES, False),
    FS_READING_CYCLE: READING_CYCLE_DEFAULTS,
    # Purim is the 14th of Adar unless a volume, for a walled city, says the 15th.
    FS_PURIM_OBSERVANCE: {"day": 14},
    # A book's prefaces and title pages are kept unless a volume leaves them out.
    FS_PARATEXT: {"include": True, "title-page": True},
}


class SettingChangeTrigger(StrEnum):
    INIT = "init"
    DECLARE = "declare"
    END_DECLARE = "end_declare"


def derived_declare_id(fs_type: str, feature_name: str) -> str:
    return f"__derived__:{fs_type}:{feature_name}"


def get_active_setting_entry(
    linear_data: LinearData,
    fs_type: str,
    feature_name: str,
) -> ConditionalSettingEntry | None:
    for entry in reversed(linear_data.conditional_settings):
        if entry.fs_type == fs_type and entry.feature_name == feature_name:
            return entry
    return None


def _is_explicit(entry: ConditionalSettingEntry) -> bool:
    return entry.source in ("init", "declared")


def _remove_derived_for_feature(
    linear_data: LinearData,
    fs_type: str,
    feature_name: str,
) -> None:
    declare_id = derived_declare_id(fs_type, feature_name)
    linear_data.conditional_settings = [
        entry
        for entry in linear_data.conditional_settings
        if not (entry.source == "derived" and entry.declare_id == declare_id)
    ]


def register_derived_entry(linear_data: LinearData, entry: ConditionalSettingEntry) -> None:
    linear_data.conditional_settings.append(entry)


def remove_derived_for_contributor(linear_data: LinearData, declare_id: str) -> None:
    """Remove the derived entries that were computed from a declaration."""
    linear_data.conditional_settings = [
        entry
        for entry in linear_data.conditional_settings
        if not (entry.source == "derived" and declare_id in entry.contributors)
    ]


def _collect_contributors(
    linear_data: LinearData,
    required_inputs: frozenset[tuple[str, str]],
) -> tuple[set[str], bool]:
    """Return contributor declare_ids and whether all required inputs are present."""
    contributors: set[str] = set()
    for fs_type, feature_name in required_inputs:
        entry = get_active_setting_entry(linear_data, fs_type, feature_name)
        if entry is None or entry.value is Undefined:
            return contributors, False
        contributors.add(entry.declare_id)
    return contributors, True


def _push_static_defaults(linear_data: LinearData) -> None:
    for fs_type, features in STATIC_DEFAULTS.items():
        for feature_name in features:
            if get_active_setting_entry(linear_data, fs_type, feature_name) is not None:
                continue
            _push_static_default(linear_data, fs_type, feature_name)


def _push_static_default(linear_data: LinearData, fs_type: str, feature_name: str) -> None:
    """Put a feature's fixed default on the stack, if it has one."""
    features = STATIC_DEFAULTS.get(fs_type, {})
    if feature_name not in features:
        return
    if linear_data.defer_reader_settings and is_reader_supplied(fs_type):
        # The book's default for its reader to change, not a value to compile in.
        return
    _remove_derived_for_feature(linear_data, fs_type, feature_name)
    register_derived_entry(
        linear_data,
        ConditionalSettingEntry(
            declare_id=derived_declare_id(fs_type, feature_name),
            fs_type=fs_type,
            feature_name=feature_name,
            value=features[feature_name],
            source="derived",
            contributors={INIT_DECLARE_ID},
        ),
    )


def _clear_derived(linear_data: LinearData, fs_type: str, feature_name: str) -> None:
    """Withdraw a derived value that no longer holds, falling back to the static default.

    Nothing but the static default stands behind the feature then: the absence of a date is
    exactly when a volume's fixed choice matters.
    """
    entry = get_active_setting_entry(linear_data, fs_type, feature_name)
    if entry is None or entry.source != "derived":
        return
    _remove_derived_for_feature(linear_data, fs_type, feature_name)
    _push_static_default(linear_data, fs_type, feature_name)


def _unknown_overridden(
    linear_data: LinearData, fs_type: str, overridable: frozenset[tuple[str, str]],
) -> None:
    """A later declaration overrides these features, but what it gives cannot be worked out.

    The earlier declared value no longer holds, and nothing stands in for it: the feature is
    undefined rather than left at a value the volume has since contradicted.
    """
    for overridden_type, feature_name in sorted(overridable):
        if overridden_type != fs_type:
            continue
        _remove_derived_for_feature(linear_data, fs_type, feature_name)
        register_derived_entry(
            linear_data,
            ConditionalSettingEntry(
                declare_id=derived_declare_id(fs_type, feature_name),
                fs_type=fs_type,
                feature_name=feature_name,
                value=Undefined,
                source="derived",
                contributors=_explicit_contributors(linear_data, FS_GREGORIAN),
            ),
        )


def _explicit_contributors(linear_data: LinearData, fs_type: str) -> set[str]:
    """The declarations that give a date's year, month and day."""
    return {
        entry.declare_id
        for entry in (get_active_setting_entry(linear_data, fs_type, feature)
                      for feature in _DATE_FEATURES)
        if entry is not None and _is_explicit(entry)
    }


def _compute_across_twilight(
    spec: DerivationSpec, snapshot: SettingSnapshot, twilight: bool,
) -> dict | None:
    """What a derivation gives, and between sunset and nightfall what it gives on both days.

    Bein hashmashot has something of the day that is ending and of the one that is beginning,
    so each derivation is worked out for both. A feature on which they agree keeps its value;
    one on which they differ holds both, as a TwilightValue, and a condition on it is decided
    only if it comes out the same either way.
    """
    if not twilight:
        return spec.compute(snapshot)
    days = (snapshot.on_day(0), snapshot.on_day(1))
    ending, starting = (spec.compute(day) for day in days)
    if ending is None or starting is None:
        # Both days have the same inputs but the date, so a derivation that cannot run on one
        # cannot run on the other either; none of them does otherwise.
        return None

    def on(day: int, computed: dict, feature_name: str) -> Any:
        # A derivation that contributes nothing to a feature on one day leaves it as it is
        # on that day (compute_holiday_from_aggregate gives only what a false yom-tov says).
        if feature_name in computed:
            return computed[feature_name]
        value = days[day].get(spec.fs_type, feature_name)
        return Undefined if value is None else value

    merged: dict[str, Any] = {}
    for feature_name in [*ending, *(name for name in starting if name not in ending)]:
        on_ending = on(0, ending, feature_name)
        on_starting = on(1, starting, feature_name)
        merged[feature_name] = (on_ending if on_ending == on_starting
                                else TwilightValue(ending=on_ending, starting=on_starting))
    return merged


def _apply_derivation_spec(
    linear_data: LinearData,
    spec: DerivationSpec,
    snapshot: SettingSnapshot,
    overridable: frozenset[tuple[str, str]] = frozenset(),
    twilight: bool = False,
) -> None:
    fs_type = spec.fs_type
    existing_features = {
        entry.feature_name
        for entry in linear_data.conditional_settings
        if entry.fs_type == fs_type
    }

    computed = _compute_across_twilight(spec, snapshot, twilight)
    if computed is None:
        for feature_name in existing_features:
            _clear_derived(linear_data, fs_type, feature_name)
        _unknown_overridden(linear_data, fs_type, overridable)
        return

    contributors, inputs_ok = _collect_contributors(linear_data, spec.required_inputs)
    if not inputs_ok:
        # An input is declared undefined. What was derived from it before no longer holds,
        # so it goes rather than standing in for a value nothing now supports.
        for feature_name in computed:
            _clear_derived(linear_data, fs_type, feature_name)
        _unknown_overridden(linear_data, fs_type, overridable)
        return

    for feature_name, value in computed.items():
        winning = get_active_setting_entry(linear_data, fs_type, feature_name)
        if (winning is not None and _is_explicit(winning)
                and (fs_type, feature_name) not in overridable):
            continue
        _remove_derived_for_feature(linear_data, fs_type, feature_name)
        register_derived_entry(
            linear_data,
            ConditionalSettingEntry(
                declare_id=derived_declare_id(fs_type, feature_name),
                fs_type=fs_type,
                feature_name=feature_name,
                value=value,
                source="derived",
                contributors=contributors,
            ),
        )


def _get_setting_from_linear_data(
    linear_data: LinearData,
    fs_type: str,
    feature_name: str,
) -> Any | None:
    entry = get_active_setting_entry(linear_data, fs_type, feature_name)
    if entry is None:
        return None
    return entry.value


def recalculate_derived_settings(
    linear_data: LinearData,
    *,
    trigger: SettingChangeTrigger,
    declare_id: str | None = None,
) -> None:
    """Recompute derived entries invalidated by a settings change."""
    del declare_id  # reserved for incremental invalidation in future

    if trigger == SettingChangeTrigger.INIT:
        _push_static_defaults(linear_data)

    snapshot = SettingSnapshot(
        get_setting=lambda fs_type, feature_name: _get_setting_from_linear_data(
            linear_data, fs_type, feature_name
        ),
    )
    # The dates and what follows from them are worked out together until they agree: a later
    # Hebrew date may be partial, and take its month and day from the derivation it overrides.
    for _ in range(_MAX_DATE_PASSES):
        before = _date_fingerprint(linear_data)
        overridable = _reconcile_dates(linear_data, snapshot)
        # Bein hashmashot is worked out for both days -- unless the volume's last word on the
        # date is a Hebrew date, which already says which day it is.
        twilight = snapshot.in_twilight() and not _hebrew_date_prevails(linear_data)
        for spec in topological_derivation_order():
            _apply_derivation_spec(linear_data, spec, snapshot, overridable, twilight)
        if _date_fingerprint(linear_data) == before:
            break

    if trigger == SettingChangeTrigger.INIT:
        _warn_on_a_date_without_a_place(snapshot)


_DATE_FEATURES = ("year", "month", "day")

#: Enough for a partial later date to be filled in and the result to settle.
_MAX_DATE_PASSES = 3


def _warn_once(linear_data: LinearData, message: str) -> None:
    if message not in linear_data.date_warnings:
        linear_data.date_warnings.add(message)
        logger.warning(message)


def _date_fingerprint(linear_data: LinearData) -> tuple:
    return tuple(
        _get_setting_from_linear_data(linear_data, fs_type, feature)
        for fs_type in (FS_GREGORIAN, FS_HEBREW_DATE) for feature in _DATE_FEATURES)


def _last_declared(linear_data: LinearData, fs_type: str) -> int:
    """Where the latest declaration of a date's year, month or day stands, or -1 for none."""
    for index in range(len(linear_data.conditional_settings) - 1, -1, -1):
        entry = linear_data.conditional_settings[index]
        if (entry.fs_type == fs_type and entry.feature_name in _DATE_FEATURES
                and _is_explicit(entry)):
            return index
    return -1


def _hebrew_date_prevails(linear_data: LinearData) -> bool:
    """Whether a Hebrew date is the volume's last word on the date."""
    hebrew = _last_declared(linear_data, FS_HEBREW_DATE)
    return hebrew >= 0 and hebrew > _last_declared(linear_data, FS_GREGORIAN)


def _reconcile_dates(
    linear_data: LinearData, snapshot: SettingSnapshot,
) -> frozenset[tuple[str, str]]:
    """When both a secular and a Hebrew date are declared, the last one declared prevails.

    JLPTEI-3: "If both the secular date and the Hebrew date are set, the last setting
    prevails." A later secular date makes the Hebrew date derived from it override the one
    declared earlier: the features returned may be overridden by derivation. A later Hebrew
    date gives the secular date that day falls on, overriding the one declared earlier, so
    that everything computed from the secular date follows it too.
    """
    gregorian = _last_declared(linear_data, FS_GREGORIAN)
    hebrew = _last_declared(linear_data, FS_HEBREW_DATE)
    if gregorian < 0 or hebrew < 0 or gregorian > hebrew:
        for feature_name in _DATE_FEATURES:
            _clear_derived(linear_data, FS_GREGORIAN, feature_name)
        if gregorian >= 0 and hebrew >= 0:
            # Without a location it cannot give one, and the Hebrew date is undefined;
            # _warn_on_a_date_without_a_place says so.
            return frozenset((FS_HEBREW_DATE, feature) for feature in _DATE_FEATURES)
        return frozenset()
    if None in (snapshot.get_int(FS_HEBREW_DATE, key) for key in _DATE_FEATURES):
        # A partial Hebrew date: its other parts come from the derivation this pass, and the
        # next pass works out the secular date from the whole.
        return frozenset()
    civil = _civil_date_of_hebrew(snapshot)
    contributors = {
        entry.declare_id
        for entry in (get_active_setting_entry(linear_data, FS_HEBREW_DATE, feature)
                      for feature in _DATE_FEATURES)
        if entry is not None
    }
    values = (Undefined,) * 3 if civil is None else (civil.year, civil.month, civil.day)
    if civil is None:
        _warn_once(linear_data, "the declared opensiddur:hebrew-date is not a date, so the "
                                "secular date and everything that follows from it are undefined")
    for feature_name, value in zip(_DATE_FEATURES, values):
        _remove_derived_for_feature(linear_data, FS_GREGORIAN, feature_name)
        register_derived_entry(
            linear_data,
            ConditionalSettingEntry(
                declare_id=derived_declare_id(FS_GREGORIAN, feature_name),
                fs_type=FS_GREGORIAN,
                feature_name=feature_name,
                value=value,
                source="derived",
                contributors=contributors,
            ),
        )
    return frozenset()


def _civil_date_of_hebrew(snapshot: SettingSnapshot) -> date | None:
    """The secular date on which the declared Hebrew date falls, at the declared time.

    A Hebrew day begins at nightfall, so at an evening time it is the secular day before its
    daytime: the 15th of Nisan at 9 PM is the evening of the 14th of April, not the 15th.
    """
    values = [snapshot.get_int(FS_HEBREW_DATE, key) for key in _DATE_FEATURES]
    if None in values:
        return None
    try:
        daytime = pyluach_dates.HebrewDate(*values).to_greg().to_pydate()
    except ValueError:
        return None
    evening = daytime - timedelta(days=1)
    civil = dict(zip(_DATE_FEATURES, (evening.year, evening.month, evening.day)))
    probe = SettingSnapshot(get_setting=lambda fs_type, feature_name: (
        civil[feature_name] if fs_type == FS_GREGORIAN and feature_name in civil
        else snapshot.get(fs_type, feature_name)))
    return evening if _effective_gregorian_date(probe) == daytime else daytime


def _warn_on_a_date_without_a_place(snapshot: SettingSnapshot) -> None:
    """A civil date says which Hebrew date it is only at a place, the day turning at nightfall.

    Without one, and without a declared Hebrew date to fall back on, nothing that follows from
    the Hebrew date is derived -- not the holidays, not Shabbat -- and a volume that meant to be
    dated would come out undated without a word.
    """
    hebrew_date = [snapshot.get_int(FS_HEBREW_DATE, key) for key in ("year", "month", "day")]
    if (snapshot.gregorian_date() is not None and snapshot.location() is None
            and None in hebrew_date):
        logger.warning(
            "opensiddur:gregorian-date is set without an opensiddur:location, so no Hebrew "
            "date, holiday or Shabbat is derived from it")
