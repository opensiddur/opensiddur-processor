"""Tie the Birnbaum siddur's three sources together, page by page.

One printing, one scan, three transcriptions of it, none of them complete:

* ``text/`` — Hebrew Wikisource. Has the Hebrew, renders Birnbaum's English rubrics
  into Hebrew of its own, and leaves the facing English pages as bare
  ``{{iwpage|en}}`` stubs.
* ``en/`` — English Wikisource, the same scan in the same ``Page:`` namespace. Human
  transcription, and so the best text there is, but only 284 of 815 pages exist and
  under half of those have been proofread.
* ``ia/ocr/`` — the Internet Archive's OCR of the same scan. Complete, machine-read,
  and hopeless at Hebrew.

This module writes ``pages.json``, which says for every one of the 815 leaves what it
is and where its text should come from. It is the artifact every later stage reads,
and it is *derived*: regenerate it, never edit it by hand.

Two things it works out rather than assumes.

**Which side of the opening a page is.** From the markers, never from parity. Odd
scan pages are usually English and even usually Hebrew, but ten pages break that, and
they break it in two contiguous runs — Hoshanot and one other section print Hebrew
with no facing English at all. A parity rule would mis-pair every page after each run.

**What the printed page number is.** The Hebrew transcription states it in a running
header, which is a human reading the page and so the best evidence available — except
where it is wrong. See :func:`resolve_printed_pages`.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from opensiddur.importer.birnbaum_siddur.en_wikisource import (
    is_usable,
    page_body,
    page_quality,
)
from opensiddur.importer.birnbaum_siddur.internet_archive import (
    IA_IDENTIFIER,
    LEAF_OFFSET,
    PAGE_DIGITS,
    leaf_for_scan_page,
)
from opensiddur.importer.birnbaum_siddur.wikisource import BOOK_NAME
from opensiddur.importer.util.internet_archive import (
    load_page_numbers,
    page_image_url,
    sha256_file,
)
from opensiddur.importer.util.pages import (
    birnbaum_siddur_correspondence_path,
    birnbaum_siddur_data_directory,
    birnbaum_siddur_en_data_directory,
    birnbaum_siddur_en_text_directory,
    birnbaum_siddur_ia_derivatives_directory,
    birnbaum_siddur_ia_ocr_directory,
    birnbaum_siddur_text_directory,
    default_sourcetexts_root,
)
from opensiddur.importer.util.wikisource_book import load_manifest, page_key

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The Hebrew running-header template. Its arguments are taken by *shape*, not by
# position: the printed page number appears in the first, second or third slot
# depending on the variant, and the template is used with both two and three
# arguments. Reading slot 0 positionally would silently lose 44 of the 405 pages
# that carry a number.
RUNNING_HEADER_RE = re.compile(r"\{\{כותרת רצה((?:\|[^|}]*)*)\}\}")

# The marker a Hebrew scan page carries in place of the English it does not hold.
IWPAGE_RE = re.compile(r"\{\{iwpage\|en\}\}")

_ARABIC_RE = re.compile(r"[0-9]+")
_ROMAN_RE = re.compile(r"[ivxlcdm]+", re.IGNORECASE)

SIDE_HEBREW = "he"
SIDE_ENGLISH = "en"
SIDE_OTHER = "other"

MATTER_FRONT = "front"
MATTER_BODY = "body"
MATTER_BACK = "back"

# Where a page's English text should be taken from.
SOURCE_EN_WIKISOURCE = "en.wikisource"
SOURCE_IA_OCR = "ia_ocr"
# A Hebrew page. Birnbaum's English footnote commentary is on it and the OCR read it
# correctly, but it arrives interleaved with Hebrew misread as Latin, in reading
# order, with nothing marking the boundary. Real text, not yet usable text.
SOURCE_IA_OCR_UNSEGMENTED = "ia_ocr_unsegmented"
SOURCE_NONE = "none"

PAGE_NUMBERS_SUFFIX = "_page_numbers.json"


def parse_running_header(wikitext: str) -> tuple[str | None, str | None]:
    """The printed page number and section name from a page's running header.

    Takes whichever argument *looks like* a page number — Arabic or Roman — as the
    number, and the remaining non-empty argument as the section, because the template
    is used in at least four shapes across this book:

    ``{{כותרת רצה|75|תפלת שחרית|}}``  number first, 397 pages
    ``{{כותרת רצה|13|ברכות השחר}}``   two arguments only, 8 pages
    ``{{כותרת רצה||3|}}``             number second, no section, 34 pages
    ``{{כותרת רצה||הושענות|N}}``      number third, 10 pages
    """
    match = RUNNING_HEADER_RE.search(wikitext)
    if match is None:
        return None, None

    arguments = [argument.strip() for argument in match.group(1).split("|")[1:]]

    number = None
    number_at = None
    for position, argument in enumerate(arguments):
        if argument and (_ARABIC_RE.fullmatch(argument) or _ROMAN_RE.fullmatch(argument)):
            number, number_at = argument, position
            break

    section = next(
        (
            argument
            for position, argument in enumerate(arguments)
            if argument and position != number_at
        ),
        None,
    )
    return number, section


def classify_side(wikitext: str) -> str:
    """Which side of the printed opening a scan page is.

    The two markers are mutually exclusive across the whole book — 405 pages carry a
    running header, 408 carry the interwiki stub, none carries both — which is what
    makes this a decision rather than a guess.
    """
    if RUNNING_HEADER_RE.search(wikitext):
        return SIDE_HEBREW
    if IWPAGE_RE.search(wikitext):
        return SIDE_ENGLISH
    return SIDE_OTHER


def _arabic(value: str | None) -> int | None:
    return int(value) if value and _ARABIC_RE.fullmatch(value) else None


DIRECT_SCAN_NUMBERS = {811: "786", 813: "788", 815: "790"}


def resolve_printed_pages(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Settle each page's printed number, correcting transcription slips.

    The Hebrew transcription's running header is preferred: a person read the page
    and typed what was on it, which beats OCR. But people copy templates between
    pages and forget to change the number, and a printed page number that goes
    backwards is impossible rather than merely surprising.

    So the sequence is checked for monotonicity over the Arabic-numbered pages, and
    where a transcribed number breaks it the Archive's reading is used instead — but
    only when that reading actually repairs the sequence. A page that cannot be
    repaired keeps its transcribed number and is reported, because inventing a
    number would be worse than surfacing a problem.

    Returns the conflicts found, and mutates the records in place.
    """
    conflicts: list[dict[str, Any]] = []

    for record in records:
        wikisource = record["printed_page_wikisource"]
        archive = record["printed_page_ia"]
        record["printed_page"] = wikisource or archive
        record["printed_page_source"] = (
            "wikisource_header" if wikisource else ("ia_page_numbers" if archive else None)
        )
        record["printed_page_conflict"] = bool(
            wikisource and archive and wikisource != archive
        )

    # Direct reading of IA n810/n812/n814 confirms the printed numbers missing
    # from both metadata layers. Evidence: scan_reading/concluding_prayers in
    # sourcetexts, final three facing English pages of the 1949 volume.
    for record in records:
        if record["scan_page"] in DIRECT_SCAN_NUMBERS and record["printed_page"] is None:
            record["printed_page"] = DIRECT_SCAN_NUMBERS[record["scan_page"]]
            record["printed_page_source"] = "direct_scan_reading"

    # Only Arabic numbers take part: the front matter is numbered in Roman, and the
    # two sequences do not compare.
    numbered = [r for r in records if _arabic(r["printed_page"]) is not None]

    highest = None
    for position, record in enumerate(numbered):
        current = _arabic(record["printed_page"])
        if highest is not None and current < highest:
            following = next(
                (_arabic(r["printed_page"]) for r in numbered[position + 1 :]), None
            )
            candidate = _arabic(record["printed_page_ia"])
            repairs = (
                candidate is not None
                and candidate > highest
                and (following is None or candidate <= following)
            )
            conflict = {
                "scan_page": record["scan_page"],
                "kind": "printed_page_out_of_sequence",
                "wikisource": record["printed_page_wikisource"],
                "ia": record["printed_page_ia"],
                "previous": str(highest),
            }
            if repairs:
                logger.warning(
                    "Scan page %d says printed page %s, which goes backwards from %d; "
                    "using the Archive's %s instead.",
                    record["scan_page"],
                    record["printed_page"],
                    highest,
                    record["printed_page_ia"],
                )
                record["printed_page"] = record["printed_page_ia"]
                record["printed_page_source"] = "ia_page_numbers_corrected"
                conflict["resolution"] = f"corrected to {record['printed_page_ia']}"
                current = candidate
            else:
                logger.error(
                    "Scan page %d says printed page %s, which goes backwards from %d, "
                    "and the Archive offers nothing better. Left as transcribed.",
                    record["scan_page"],
                    record["printed_page"],
                    highest,
                )
                conflict["resolution"] = "unresolved"
            conflicts.append(conflict)
        highest = current if highest is None else max(highest, current)

    return conflicts


def pair_facing_pages(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pair each Hebrew page with the English page that translates it.

    Birnbaum prints the two on facing pages, Hebrew first, so the English page is the
    next leaf and its printed number is one higher. Both parts are checked: some
    sections print Hebrew with no facing English at all, and pairing those to the next
    English page — which belongs to a later section — would be worse than not pairing
    them.
    """
    by_scan = {record["scan_page"]: record for record in records}
    unpaired: list[dict[str, Any]] = []

    for record in records:
        if record["side"] != SIDE_HEBREW:
            continue

        hebrew_number = _arabic(record["printed_page"])
        following = by_scan.get(record["scan_page"] + 1)

        if following is not None and following["side"] == SIDE_ENGLISH:
            english_number = _arabic(following["printed_page"])
            if (
                hebrew_number is None
                or english_number is None
                or english_number == hebrew_number + 1
            ):
                record["facing_scan_page"] = following["scan_page"]
                following["facing_scan_page"] = record["scan_page"]
                continue

        unpaired.append(
            {
                "scan_page": record["scan_page"],
                "side": SIDE_HEBREW,
                "printed_page": record["printed_page"],
                "reason": (
                    "the next leaf is not an English page"
                    if following is None or following["side"] != SIDE_ENGLISH
                    else "the next leaf's printed page number does not follow"
                ),
            }
        )

    return unpaired


def _classify_matter(records: list[dict[str, Any]]) -> None:
    """Mark each page front matter, body or back matter.

    The body starts at the first Hebrew page printed as page 1 and ends at the last
    Hebrew page and its paired English translation; both are found rather than
    hardcoded. Everything before is front
    matter — which is where the English-only material the Hebrew transcription omits
    entirely, the preface among it, lives.
    """
    hebrew = [r for r in records if r["side"] == SIDE_HEBREW]
    first_body = next(
        (r["scan_page"] for r in hebrew if r["printed_page_wikisource"] == "1"), None
    )
    last_body = (
        max(hebrew[-1]["scan_page"], hebrew[-1].get("facing_scan_page") or 0)
        if hebrew else None
    )

    for record in records:
        scan_page = record["scan_page"]
        if first_body is not None and scan_page < first_body:
            record["matter"] = MATTER_FRONT
        elif last_body is not None and scan_page > last_body:
            record["matter"] = MATTER_BACK
        else:
            record["matter"] = MATTER_BODY


def _page_numbers_path(sourcetexts_root: Path | None) -> Path | None:
    directory = birnbaum_siddur_ia_derivatives_directory(sourcetexts_root)
    matches = sorted(directory.glob(f"*{PAGE_NUMBERS_SUFFIX}"))
    return matches[0] if matches else None


def build_correspondence(sourcetexts_root: Path | None = None) -> dict[str, Any]:
    """Read all three layers off disk and work out how they line up."""
    text_dir = birnbaum_siddur_text_directory(sourcetexts_root)
    en_text_dir = birnbaum_siddur_en_text_directory(sourcetexts_root)
    ocr_dir = birnbaum_siddur_ia_ocr_directory(sourcetexts_root)

    scan_pages = sorted(int(p.stem) for p in text_dir.glob("*.txt"))
    if not scan_pages:
        raise FileNotFoundError(
            f"No Hebrew scan pages under {text_dir}. Run the wikisource downloader first."
        )

    numbers_path = _page_numbers_path(sourcetexts_root)
    archive_numbers = load_page_numbers(numbers_path) if numbers_path else {}
    if not archive_numbers:
        logger.warning(
            "No Internet Archive page numbers found; transcribed page numbers cannot "
            "be cross-checked and out-of-sequence numbers cannot be repaired."
        )

    en_manifest = load_manifest(birnbaum_siddur_en_data_directory(sourcetexts_root))
    en_pages = en_manifest.get("pages") or {}

    records: list[dict[str, Any]] = []
    for scan_page in scan_pages:
        key = page_key(scan_page, PAGE_DIGITS)
        leaf = leaf_for_scan_page(scan_page)
        wikitext = (text_dir / f"{key}.txt").read_text(encoding="utf-8")

        number, section = parse_running_header(wikitext)
        archive_number = archive_numbers.get(leaf)

        english: dict[str, Any] | None = None
        en_file = en_text_dir / f"{key}.txt"
        if en_file.is_file():
            en_text = en_file.read_text(encoding="utf-8")
            english = {
                "title": f"Page:{BOOK_NAME}/{scan_page}",
                "revid": (en_pages.get(key) or {}).get("revid"),
                "quality": page_quality(en_text),
                "empty": not page_body(en_text),
                "usable": is_usable(en_text),
                "path": f"en/text/{key}.txt",
            }

        archive: dict[str, Any] | None = None
        ocr_file = ocr_dir / f"{key}.txt"
        if ocr_file.is_file():
            archive = {
                "path": f"ia/ocr/{key}.txt",
                "sha256": sha256_file(ocr_file),
                "empty": not ocr_file.read_text(encoding="utf-8").strip(),
            }

        records.append(
            {
                "scan_page": scan_page,
                "ia_leaf": leaf,
                "matter": None,
                "side": classify_side(wikitext),
                "side_source": "wikisource_marker",
                "section": section,
                "printed_page": None,
                "printed_page_source": None,
                "printed_page_wikisource": number,
                "printed_page_ia": archive_number.printed if archive_number else None,
                "printed_page_ia_confidence": (
                    archive_number.confidence if archive_number else None
                ),
                "printed_page_conflict": False,
                "facing_scan_page": None,
                "facs": page_image_url(IA_IDENTIFIER, leaf),
                "en": english,
                "ia": archive,
                "text_source": None,
            }
        )

    conflicts = resolve_printed_pages(records)
    unpaired = pair_facing_pages(records)
    _classify_matter(records)

    for record in records:
        record["text_source"] = _text_source(record)

    counts = {
        "total": len(records),
        SIDE_HEBREW: sum(1 for r in records if r["side"] == SIDE_HEBREW),
        SIDE_ENGLISH: sum(1 for r in records if r["side"] == SIDE_ENGLISH),
        SIDE_OTHER: sum(1 for r in records if r["side"] == SIDE_OTHER),
        "en_wikisource_present": sum(1 for r in records if r["en"]),
        "en_wikisource_used": sum(
            1 for r in records if r["text_source"] == SOURCE_EN_WIKISOURCE
        ),
        "front_matter_english": sum(
            1
            for r in records
            if r["matter"] == MATTER_FRONT and r["side"] == SIDE_ENGLISH
        ),
    }

    return {
        "generated_from": (
            "text/, en/text/, ia/ocr/ and ia/derivatives/*_page_numbers.json. "
            "Derived: regenerate with birnbaum_siddur.correspondence rather than editing."
        ),
        "generated_at": datetime.now(UTC).isoformat(),
        "ia_identifier": IA_IDENTIFIER,
        "leaf_offset": LEAF_OFFSET,
        "counts": counts,
        "conflicts": conflicts,
        "unpaired": unpaired,
        "pages": records,
    }


def _text_source(record: dict[str, Any]) -> str:
    """Where this page's English text should be read from."""
    if record["en"] and record["en"]["usable"]:
        return SOURCE_EN_WIKISOURCE
    if not record["ia"] or record["ia"]["empty"]:
        return SOURCE_NONE
    if record["side"] == SIDE_ENGLISH:
        return SOURCE_IA_OCR
    return SOURCE_IA_OCR_UNSEGMENTED


def _serialise(correspondence: dict[str, Any]) -> str:
    return json.dumps(correspondence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def save_correspondence(
    correspondence: dict[str, Any], sourcetexts_root: Path | None = None
) -> Path:
    """Write the table, unless the only thing that would change is its timestamp.

    The table is rebuilt on every run and committed to a repository. Since
    ``generated_at`` differs every time, writing unconditionally would turn a run
    that found nothing new into a one-line diff, which trains people to ignore
    diffs on this file.
    """
    path = birnbaum_siddur_correspondence_path(sourcetexts_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            existing = None
        if existing is not None:
            compared = dict(correspondence, generated_at=existing.get("generated_at"))
            if _serialise(compared) == path.read_text(encoding="utf-8"):
                logger.info("%s is already up to date.", path.name)
                return path

    path.write_text(_serialise(correspondence), encoding="utf-8")
    return path


def load_correspondence(sourcetexts_root: Path | None = None) -> dict[str, Any]:
    path = birnbaum_siddur_correspondence_path(sourcetexts_root)
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_page_text(
    scan_page: int, sourcetexts_root: Path | None = None
) -> tuple[str | None, str]:
    """The best English text for one scan page, and where it came from.

    Reads the two sources rather than a resolved third copy of the text: a
    materialised copy would go stale the moment either input were refetched.
    """
    correspondence = load_correspondence(sourcetexts_root)
    record = next(
        (r for r in correspondence["pages"] if r["scan_page"] == scan_page), None
    )
    if record is None:
        return None, SOURCE_NONE

    root = birnbaum_siddur_data_directory(sourcetexts_root)
    source = record["text_source"]
    if source == SOURCE_EN_WIKISOURCE:
        return page_body((root / record["en"]["path"]).read_text(encoding="utf-8")), source
    if source in (SOURCE_IA_OCR, SOURCE_IA_OCR_UNSEGMENTED):
        return (root / record["ia"]["path"]).read_text(encoding="utf-8"), source
    return None, SOURCE_NONE


def report(correspondence: dict[str, Any]) -> Iterable[str]:
    """Human-readable summary of what the table says and what it could not settle."""
    counts = correspondence["counts"]
    yield (
        f"{counts['total']} leaves: {counts['he']} Hebrew, {counts['en']} English, "
        f"{counts['other']} neither."
    )
    yield (
        f"English text: {counts['en_wikisource_used']} pages from en.wikisource, "
        f"the rest from OCR ({counts['en_wikisource_present']} en.wikisource pages exist)."
    )
    yield f"{counts['front_matter_english']} English front-matter pages."
    for conflict in correspondence["conflicts"]:
        yield (
            f"  conflict: scan {conflict['scan_page']} transcribed as "
            f"{conflict['wikisource']}, Archive reads {conflict['ia']} "
            f"({conflict['resolution']})"
        )
    if correspondence["unpaired"]:
        pages = [entry["scan_page"] for entry in correspondence["unpaired"]]
        yield f"  {len(pages)} Hebrew page(s) with no facing English: {_ranges(pages)}"


def _ranges(numbers: list[int]) -> str:
    """Collapse a sorted list of page numbers into readable ranges."""
    if not numbers:
        return ""
    # Only genuinely consecutive numbers are collapsed. Allowing a step of two
    # would be tempting, since Hebrew pages fall on every other leaf, but "100-102"
    # would then claim 101 as well and quietly overstate the problem.
    spans: list[list[int]] = [[numbers[0], numbers[0]]]
    for number in numbers[1:]:
        if number == spans[-1][1] + 1:
            spans[-1][1] = number
        else:
            spans.append([number, number])
    return ", ".join(
        str(low) if low == high else f"{low}-{high}" for low, high in spans
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build pages.json, the table tying the Birnbaum siddur's Hebrew "
            "Wikisource, English Wikisource and Internet Archive layers together."
        )
    )
    parser.add_argument(
        "--sourcetexts-root",
        type=Path,
        default=default_sourcetexts_root(),
        help=(
            "Root of the opensiddur/sourcetexts repository; the table is written to "
            "<root>/birnbaum_siddur/pages.json (default: <repo>/sourcetexts/sources)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the table and report on it without writing anything.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Rebuild in memory and exit non-zero if any page number could not be "
            "settled. For CI; writes nothing."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    try:
        correspondence = build_correspondence(args.sourcetexts_root)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s", exc)
        return 1

    for line in report(correspondence):
        logger.info("%s", line)

    if args.check:
        unresolved = [
            conflict
            for conflict in correspondence["conflicts"]
            if conflict.get("resolution") == "unresolved"
        ]
        if unresolved:
            logger.error("%d page number(s) could not be settled.", len(unresolved))
            return 1
        return 0

    if args.dry_run:
        logger.info("Dry run: nothing written.")
        return 0

    path = save_correspondence(correspondence, args.sourcetexts_root)
    logger.info("Wrote %s", path)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
