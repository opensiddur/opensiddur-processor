"""Check the MAM aliyah parse against hebcal's independent record of the same divisions.

The humash takes its weekly aliyot from Miqra al pi ha-Masorah, whose divisions agree with the
MAM text the reader is looking at. hebcal records the same divisions separately, so comparing
the two catches errors in MAM's aliyah markers, or in reading them from MAM-parsed plus, that no
internal consistency check could.

Where the two genuinely differ they differ for a reason — the sources disagree about where a
few aliyot begin, and hebcal notes the alternative in a third element of the range. Those are
listed in ``KNOWN_DIVERGENCES`` so that a new difference stands out from an expected one.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from opensiddur.importer.humash.aliyot import parse_parshiyot
from opensiddur.importer.humash.names import HEBCAL_TO_SLUG
from opensiddur.importer.humash.refs import (
    HEBCAL_BOOK_TO_SLUG,
    UNIT_ALIYAH,
    UNIT_MAFTIR,
    UNIT_WEEKDAY,
    parse_hebcal_ref,
)
from opensiddur.importer.util.pages import hebcal_leyning_data_directory

logger = logging.getLogger(__name__)

# hebcal numbers the books 1-5 in its aliyot.json.
_HEBCAL_BOOK_NUMBERS = {1: "genesis", 2: "exodus", 3: "leviticus", 4: "numbers", 5: "deuteronomy"}

# Aliyot where MAM and hebcal deliberately differ. hebcal's own note names MAM's division as
# what "some sources use", so these are two live traditions, not an error in either.
KNOWN_DIVERGENCES: frozenset[tuple[str, str, str]] = frozenset({
    # (parshah slug, unit, label)
    ("bereshit", UNIT_ALIYAH, "5"),   # hebcal 4:19-4:22; MAM 4:19-4:26
    ("bereshit", UNIT_ALIYAH, "6"),   # hebcal 4:23-5:24; MAM 5:1-5:24
    ("terumah", UNIT_ALIYAH, "2"),    # hebcal 25:16-25:30; MAM 25:17-25:30
    ("terumah", UNIT_ALIYAH, "3"),    # hebcal 25:31-26:14; MAM 25:31-26:14
})


@dataclass(frozen=True)
class Divergence:
    parsha: str
    unit: str
    label: str
    mam: str
    hebcal: str
    note: str | None = None

    @property
    def is_known(self) -> bool:
        return (self.parsha, self.unit, self.label) in KNOWN_DIVERGENCES

    def __str__(self) -> str:
        marker = "known" if self.is_known else "NEW"
        line = f"[{marker}] {self.parsha} {self.unit} {self.label}: MAM {self.mam} / hebcal {self.hebcal}"
        return f"{line} ({self.note})" if self.note else line


def _hebcal_spans(entry: dict) -> dict[tuple[str, str], tuple[str, str | None]]:
    """Flatten one hebcal parshah entry to {(unit, label): (range, note)}."""
    book = _HEBCAL_BOOK_NUMBERS[entry["book"]]
    spans: dict[tuple[str, str], tuple[str, str | None]] = {}
    for key, unit in (("fullkriyah", UNIT_ALIYAH), ("weekday", UNIT_WEEKDAY)):
        for label, value in entry.get(key, {}).items():
            note = value[2] if len(value) > 2 else None
            start = parse_hebcal_ref(book, value[0])
            end = parse_hebcal_ref(book, value[1])
            target_unit = UNIT_MAFTIR if label == "M" else unit
            target_label = "maftir" if label == "M" else label
            spans[(target_unit, target_label)] = (f"{start.chapter}:{start.verse}-{end.chapter}:{end.verse}", note)
    return spans


def compare(sourcetexts_root: Path | None = None) -> list[Divergence]:
    """Compare every MAM span against hebcal's, returning the differences."""
    path = hebcal_leyning_data_directory(sourcetexts_root) / "aliyot.json"
    hebcal = json.loads(path.read_text(encoding="utf-8"))
    by_slug = {
        HEBCAL_TO_SLUG[name]: entry
        for name, entry in hebcal.items()
        if not entry.get("combined") and name in HEBCAL_TO_SLUG
    }

    divergences: list[Divergence] = []
    for parsha in parse_parshiyot(sourcetexts_root):
        entry = by_slug.get(parsha.slug)
        if entry is None:
            logger.warning("hebcal has no entry for %s", parsha.slug)
            continue
        expected = _hebcal_spans(entry)
        for span in parsha.spans:
            label = "maftir" if span.unit == UNIT_MAFTIR else span.label
            key = (span.unit, label)
            if key not in expected:
                divergences.append(Divergence(
                    parsha.slug, span.unit, label,
                    f"{span.start.chapter}:{span.start.verse}-{span.end.chapter}:{span.end.verse}",
                    "absent",
                ))
                continue
            hebcal_range, note = expected.pop(key)
            mam_range = f"{span.start.chapter}:{span.start.verse}-{span.end.chapter}:{span.end.verse}"
            if mam_range != hebcal_range:
                divergences.append(
                    Divergence(parsha.slug, span.unit, label, mam_range, hebcal_range, note)
                )
        for (unit, label), (hebcal_range, note) in expected.items():
            divergences.append(Divergence(parsha.slug, unit, label, "absent", hebcal_range, note))
    return divergences


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sourcetexts-root", type=Path, default=None)
    args = parser.parse_args(argv)

    divergences = compare(args.sourcetexts_root)
    unexpected = [d for d in divergences if not d.is_known]
    for divergence in divergences:
        print(divergence)
    print(f"\n{len(divergences)} divergences, {len(unexpected)} of them unexpected")
    return 1 if unexpected else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
