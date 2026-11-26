"""Declarative derivation graph for JLPTEI derived feature structures."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from opensiddur.exporter.calendar.avot import FS_AVOT, compute_avot
from opensiddur.exporter.calendar.compute import (
    FS_DAY_OF_WEEK,
    FS_GREGORIAN,
    FS_HEBREW_DATE,
    FS_HEBREW_TIME,
    FS_HOLIDAY,
    FS_HOLIDAY_AGG,
    FS_ISRAEL,
    FS_LOCATION,
    FS_PURIM_OBSERVANCE,
    FS_QUORUM,
    FS_READING_CYCLE,
    FS_RECITATION,
    FS_SERVICE_TIME,
    FS_TIME,
    FS_TORAH,
    FeatureRef,
    SettingSnapshot,
    compute_day_of_week,
    compute_hebrew_date,
    compute_hebrew_time,
    compute_holiday,
    compute_holiday_aggregate,
    compute_holiday_from_aggregate,
    compute_israel,
    compute_location,
    compute_quorum,
    compute_reading_cycle,
    compute_recitation,
    compute_service_time,
    compute_torah_reading,
)
from opensiddur.exporter.calendar.hallel import FS_HALLEL, compute_hallel
from opensiddur.exporter.calendar.motzaei_shabbat import (
    FS_MOTZAEI_SHABBAT,
    compute_motzaei_shabbat,
)

ComputeFn = Callable[[SettingSnapshot], dict[str, object] | None]


@dataclass(frozen=True)
class DerivationSpec:
    """One derived feature-structure group and its inputs."""

    fs_type: str
    required_inputs: frozenset[FeatureRef]
    compute: ComputeFn


def _gregorian_inputs() -> frozenset[FeatureRef]:
    return frozenset({
        (FS_GREGORIAN, "year"),
        (FS_GREGORIAN, "month"),
        (FS_GREGORIAN, "day"),
    })


def _location_inputs() -> frozenset[FeatureRef]:
    return frozenset({
        (FS_LOCATION, "latitude"),
        (FS_LOCATION, "longitude"),
    })


def _time_inputs() -> frozenset[FeatureRef]:
    return frozenset({
        (FS_TIME, "hour"),
        (FS_TIME, "minute"),
    })


DERIVATION_SPECS: tuple[DerivationSpec, ...] = (
    DerivationSpec(
        fs_type=FS_HALLEL,
        required_inputs=frozenset({(FS_HEBREW_DATE, key) for key in ("year", "month", "day")} | {(FS_ISRAEL, "is-israel")}),
        compute=compute_hallel,
    ),
    DerivationSpec(
        fs_type=FS_MOTZAEI_SHABBAT,
        required_inputs=frozenset({(FS_HEBREW_DATE, key) for key in ("year", "month", "day")} | {(FS_ISRAEL, "is-israel")}),
        compute=compute_motzaei_shabbat,
    ),
    DerivationSpec(
        fs_type=FS_AVOT,
        required_inputs=frozenset({(FS_HEBREW_DATE, key) for key in ("year", "month", "day")} | {(FS_ISRAEL, "is-israel")}),
        compute=compute_avot,
    ),
    # Its inputs are all declared, so the topological order emits it in the first pass, and the
    # derived time zone is on the stack before anything that reads a location.
    DerivationSpec(
        fs_type=FS_LOCATION,
        required_inputs=_location_inputs(),
        compute=compute_location,
    ),
    DerivationSpec(
        fs_type=FS_ISRAEL,
        required_inputs=_location_inputs(),
        compute=compute_israel,
    ),
    DerivationSpec(
        fs_type=FS_HEBREW_DATE,
        required_inputs=_gregorian_inputs() | _location_inputs(),
        compute=compute_hebrew_date,
    ),
    DerivationSpec(
        fs_type=FS_DAY_OF_WEEK,
        required_inputs=_gregorian_inputs(),
        compute=compute_day_of_week,
    ),
    DerivationSpec(
        fs_type=FS_HEBREW_TIME,
        required_inputs=_gregorian_inputs() | _location_inputs() | _time_inputs(),
        compute=compute_hebrew_time,
    ),
    # Also read, but not required: opensiddur:purim-observance/day, for purim-observed. A
    # holiday is known without it, and without it only that one feature is undefined.
    DerivationSpec(
        fs_type=FS_HOLIDAY,
        required_inputs=_gregorian_inputs()
        | frozenset({
            (FS_HEBREW_DATE, "year"),
            (FS_HEBREW_DATE, "month"),
            (FS_HEBREW_DATE, "day"),
        }),
        compute=compute_holiday,
    ),
    DerivationSpec(
        fs_type=FS_HOLIDAY_AGG,
        required_inputs=_gregorian_inputs()
        | frozenset({
            (FS_HEBREW_DATE, "year"),
            (FS_HEBREW_DATE, "month"),
            (FS_HEBREW_DATE, "day"),
        }),
        compute=compute_holiday_aggregate,
    ),
    DerivationSpec(
        fs_type=FS_TORAH,
        required_inputs=_gregorian_inputs(),
        compute=compute_torah_reading,
    ),
    DerivationSpec(
        fs_type=FS_SERVICE_TIME,
        required_inputs=_gregorian_inputs() | _location_inputs() | _time_inputs(),
        compute=compute_service_time,
    ),
    # After the Torah reading, whose cycle year it draws on when the volume reads triennially.
    DerivationSpec(
        fs_type=FS_READING_CYCLE,
        required_inputs=frozenset({(FS_READING_CYCLE, "triennial"), (FS_TORAH, "triennial-year")}),
        compute=compute_reading_cycle,
    ),
    # Backward, and the only one that runs that way: a volume may say what kind of day it
    # is without saying which day. Placed after the aggregate, whose own inputs are dates,
    # so there is no cycle.
    DerivationSpec(
        fs_type=FS_HOLIDAY,
        required_inputs=frozenset({(FS_HOLIDAY_AGG, "yom-tov")}),
        compute=compute_holiday_from_aggregate,
    ),
    # Ma'ariv has no repetition, so its Amidah is always the silent one.
    DerivationSpec(
        fs_type=FS_RECITATION,
        required_inputs=frozenset({(FS_SERVICE_TIME, "maariv")}),
        compute=compute_recitation,
    ),
    DerivationSpec(
        fs_type=FS_QUORUM,
        required_inputs=frozenset({(FS_QUORUM, "minyan")}),
        compute=compute_quorum,
    ),
)


DERIVED_FS_TYPES: frozenset[str] = frozenset(spec.fs_type for spec in DERIVATION_SPECS)

#: Every feature a derivation reads: the inputs it requires, and what it consults besides --
#: the zone of a place, the seconds of a time, the day Purim is kept, whether it is Israel.
#: html/assets/calendar.js has the same list (READ_FEATURES), and a test holds both to what
#: the derivations read.
READ_FEATURES: frozenset[FeatureRef] = frozenset(
    {ref for spec in DERIVATION_SPECS for ref in spec.required_inputs}
    | {(FS_LOCATION, "timezone"), (FS_TIME, "second"), (FS_PURIM_OBSERVANCE, "day"),
       (FS_ISRAEL, "is-israel")}
)


def topological_derivation_order() -> list[DerivationSpec]:
    """Return specs in dependency order (derived inputs before dependents)."""
    specs = list(DERIVATION_SPECS)
    ordered: list[DerivationSpec] = []
    emitted_fs: set[str] = set()

    while len(ordered) < len(specs):
        progress = False
        for spec in specs:
            if spec in ordered:
                continue
            input_fs_types = {fs for fs, _ in spec.required_inputs}
            external = input_fs_types - {spec.fs_type}
            derived_deps = external & DERIVED_FS_TYPES
            if derived_deps <= emitted_fs:
                ordered.append(spec)
                emitted_fs.add(spec.fs_type)
                progress = True
        if not progress:
            raise RuntimeError("Circular dependency in derivation graph")
    return ordered
