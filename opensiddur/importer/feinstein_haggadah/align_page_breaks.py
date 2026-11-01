"""Rough first-pass alignment of OSP haggadah sections to pages of the 1822 facsimile.

This is a developer aid, **not** the source of truth. It fuzzy-matches consonant
subsequences against ``pdftotext`` output and then interpolates and clamps, which in
practice drifts and fails outright over long stretches. Its output is a starting point for
hand verification only.

The conversion pipeline reads the hand-curated
``opensiddur/importer/feinstein_haggadah/page_breaks_1822.json`` instead; see
:mod:`opensiddur.importer.feinstein_haggadah.page_breaks`. Nothing in the conversion path
may import this module.

The draft it writes speaks the same language as the curated table: folio designations of
the 1822 edition (``2r``-``40v``), derived from the page of the scan a section was matched
to. What is unreliable is the *matching*, not the numbering.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader

from opensiddur.importer.feinstein_haggadah.parse_compilation import (
    build_section_contents,
    load_compilation_json,
    parse_rows,
)
from opensiddur.importer.feinstein_haggadah.page_breaks import (
    FACSIMILE_FIRST_PAGE,
    FACSIMILE_LAST_PAGE,
    folio_at_facsimile_page,
)
from opensiddur.importer.feinstein_haggadah.sections import (
    MAGID_SUBSECTION_PREFIXES,
    NIRTZAH_SUBSECTION_PREFIXES,
    document_order_slugs,
)
from opensiddur.importer.util.hebrew import normalize_hebrew as _normalize_hebrew
from opensiddur.importer.util.pages import (
    default_sourcetexts_root,
    feinstein_haggadah_data_directory,
    heidenheim_haggadah_data_directory,
    heidenheim_pdf_path,
)


def page_breaks_path(sourcetexts_root: Path | None = None) -> Path:
    """Where this tool writes its draft alignment, for hand verification."""
    return heidenheim_haggadah_data_directory(sourcetexts_root) / "page_breaks.draft.json"


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hebrew fragments that survive pdftotext on the 1822 facsimile.
HEADER_ANCHORS: dict[str, list[str]] = {
    "bediqat_chametz": ["בדיקתחמץ"],
    "biur_chametz": ["ביעורחמץ"],
    "eruv_tavshilin": ["עירוב"],
    "qaddesh": ["סדרקידוש"],
    "urechatz": ["ורחץ"],
    "karpas": ["כרפס"],
    "yachatz": ["יחץ"],
    "ha_lachma_anya": ["האלחמא", "לחמאעניא"],
    "mah_nishtanah": ["מהנשתנה"],
    "avadim_hayinu": ["עבדיםהיינו", "עבריםהיינו"],
    "arbaah_vanim": ["ארבעהבנים", "כנגדארבעה"],
    "chakham": ["חכםמההוא"],
    "rasha": ["רשעמההוא"],
    "tam": ["תםמההוא"],
    "vehi_sheamedah": ["והיאשעמדה"],
    "arami_oved_avi": ["צאולמד"],
    "rabban_gamliel": ["רבןגמליאל"],
    "tzafun": ["אפיקומן", "צפון"],
    "motzi_matzah": ["מוציאמצה"],
    "maror": ["מרור"],
    "korekh": ["כורך"],
    "shulchan_orekh": ["שלחןעורך"],
    # The two hand-washings are told apart by the vav alone: the first is headed ורחץ above
    # under its standard name urechatz, the second רחץ here. Neither fragment may be given to
    # both, or _subseq_ratio cannot choose between them.
    "rachatz": ["רחץ"],
    "barekh": ["ברך"],
    "hallel": ["הלל"],
    "chasal_siddur_pesach": ["חסלסידור"],
    "vayehi_bachatzi_halailah": ["ויהיבחצי"],
    "echad_mi_yodea": ["אחדמייודע"],
    "chad_gadya": ["חדגדיא"],
    "sefirat_haomer": ["ספירתהעומר"],
    "ellu_eser_makkot": ["אלועשרמכות"],
    "rabbi_yehudah_hayah_noten": ["יהודההיהנותן"],
    "psalm_113": ["הללויה"],
    "lefikhakh": ["לפיכך"],
    "vaamartem_zevach_pesach": ["ואמרתם"],
    "ki_lo_naeh": ["כילונאה"],
    "addir_hu": ["אדירהוא"],
    "psalm_114": ["בצאתישראל"],
}


def _subseq_ratio(needle: str, haystack: str) -> float:
    if not needle:
        return 0.0
    index = 0
    matched = 0
    for char in haystack:
        if index < len(needle) and char == needle[index]:
            matched += 1
            index += 1
    return matched / len(needle)


def _pdftotext_pages(pdf_path: Path) -> list[str]:
    output = subprocess.check_output(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        text=True,
        errors="replace",
    )
    pages = output.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return pages


def _scan_page_by_pdf_index(page_count: int) -> list[int]:
    """Map each 0-based PDF page index to its page number in the scan.

    The reference copy is paginated 1:1 with the scan, so this is just ``index + 1``. It used
    to be read off the foot of each page by OCR, which was never necessary and broke outright
    on copies whose text layer splits a two-digit number into separate digits.
    """
    return list(range(1, page_count + 1))


def _build_needles(
    slugs: list[str],
    contents: dict,
) -> dict[str, list[str]]:
    prefix_by_slug = dict(MAGID_SUBSECTION_PREFIXES + NIRTZAH_SUBSECTION_PREFIXES)
    needles: dict[str, list[str]] = {}
    for slug in slugs:
        variants: set[str] = set(HEADER_ANCHORS.get(slug, []))
        if slug in prefix_by_slug:
            variants.add(_normalize_hebrew(prefix_by_slug[slug]))
        section = contents.get(slug)
        if section and section.hebrew_lines:
            normalized = _normalize_hebrew("\n".join(section.hebrew_lines[:4]))
            for length in (32, 24):
                if len(normalized) >= length:
                    variants.add(normalized[:length])
        needles[slug] = [v for v in variants if len(v) >= 6]
    return needles


def _score_page(variants: list[str], page_text: str) -> float:
    if not variants:
        return 0.0
    return max(_subseq_ratio(variant, page_text) for variant in variants)


def _interpolate_missing(
    aligned: dict[str, int],
    slugs: list[str],
) -> dict[str, int]:
    """Fill gaps using nearest aligned neighbors in document order."""
    result = dict(aligned)
    for index, slug in enumerate(slugs):
        if slug in result:
            continue
        prev_page: int | None = None
        for prior in reversed(slugs[:index]):
            if prior in result:
                prev_page = result[prior]
                break
        next_page: int | None = None
        for following in slugs[index + 1 :]:
            if following in result:
                next_page = result[following]
                break
        if prev_page is not None and next_page is not None:
            result[slug] = min(prev_page, next_page)
        elif prev_page is not None:
            result[slug] = min(prev_page + 1, FACSIMILE_LAST_PAGE)
        elif next_page is not None:
            result[slug] = next_page
    return result


def _enforce_monotonic(mapping: dict[str, int], slugs: list[str]) -> dict[str, int]:
    """Ensure page numbers never decrease in document order."""
    last = FACSIMILE_FIRST_PAGE
    result: dict[str, int] = {}
    for slug in slugs:
        if slug not in mapping:
            continue
        page = min(max(mapping[slug], last), FACSIMILE_LAST_PAGE)
        result[slug] = page
        last = page
    return result


def _align_pass(
    *,
    slugs: list[str],
    needles: dict[str, list[str]],
    page_norm: list[str],
    printed: list[int],
    page_count: int,
    start_pdf_index: int,
    score_threshold: float,
    anchor_threshold: float,
    existing: dict[str, int] | None = None,
) -> tuple[dict[str, int], int]:
    aligned = dict(existing or {})
    prev_pdf_index = start_pdf_index
    for slug in slugs:
        if slug in aligned:
            continue
        variants = needles.get(slug, [])
        best_score = 0.0
        best_index: int | None = None
        for pdf_index in range(prev_pdf_index + 1, page_count):
            score = _score_page(variants, page_norm[pdf_index])
            if score > best_score:
                best_score = score
                best_index = pdf_index
        threshold = anchor_threshold if slug in HEADER_ANCHORS else score_threshold
        if best_index is not None and best_score >= threshold:
            aligned[slug] = printed[best_index]
            prev_pdf_index = best_index
    return aligned, prev_pdf_index


def align_page_breaks(
    *,
    sourcetexts_root: Path | None = None,
    pdf_path: Path | None = None,
    score_threshold: float = 0.72,
    anchor_threshold: float = 0.55,
) -> dict[str, int]:
    """Return slug -> printed page number using the 1822 PDF facsimile."""
    pdf = pdf_path or heidenheim_pdf_path(sourcetexts_root)
    if pdf is None or not pdf.is_file():
        raise FileNotFoundError(
            "1822 Heidenheim PDF not found under heidenheim_haggadah_1822/"
        )

    json_path = feinstein_haggadah_data_directory(sourcetexts_root) / "compilation.json"
    rows = parse_rows(load_compilation_json(json_path))
    contents = build_section_contents(rows)
    slugs = document_order_slugs()
    needles = _build_needles(slugs, contents)

    reader = PdfReader(str(pdf))
    pdftotext_pages = _pdftotext_pages(pdf)
    if len(pdftotext_pages) != len(reader.pages):
        logger.warning(
            "pdftotext page count (%d) != PDF page count (%d)",
            len(pdftotext_pages),
            len(reader.pages),
        )
    page_count = min(len(pdftotext_pages), len(reader.pages))
    page_norm = [_normalize_hebrew(pdftotext_pages[i]) for i in range(page_count)]
    printed = _scan_page_by_pdf_index(page_count)

    aligned, _ = _align_pass(
        slugs=slugs,
        needles=needles,
        page_norm=page_norm,
        printed=printed,
        page_count=page_count,
        start_pdf_index=-1,
        score_threshold=score_threshold,
        anchor_threshold=anchor_threshold,
    )
    filled = _interpolate_missing(aligned, slugs)
    return _enforce_monotonic(filled, slugs)


def write_page_breaks(
    mapping: dict[str, int],
    sourcetexts_root: Path | None = None,
) -> Path:
    path = page_breaks_path(sourcetexts_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_comment": (
            "DRAFT ONLY - not used by the converter. Maps section slug to the folio of the "
            "1822 edition (2r-40v) the section was matched to. Generated by "
            "align_page_breaks.py; the matching drifts, so verify every entry by hand "
            "against the facsimile before transferring it to page_breaks_1822.json."
        ),
        **{slug: folio_at_facsimile_page(page) for slug, page in mapping.items()},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Align haggadah section slugs to folios of the 1822 Heidenheim edition "
            "using the HebrewBooks PDF facsimile."
        )
    )
    parser.add_argument(
        "--sourcetexts-root",
        type=Path,
        default=default_sourcetexts_root(),
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=None,
        help="Path to PDF (default: auto-detect under heidenheim_haggadah_1822/).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print alignment without writing page_breaks.json.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    mapping = align_page_breaks(
        sourcetexts_root=args.sourcetexts_root,
        pdf_path=args.pdf,
    )
    slugs = document_order_slugs()
    logger.info("Aligned %d / %d sections", len(mapping), len(slugs))
    for slug in slugs:
        if slug in mapping:
            print(f"{folio_at_facsimile_page(mapping[slug]):>4}  {slug}")

    missing = [slug for slug in slugs if slug not in mapping]
    if missing:
        logger.warning("Unaligned sections (%d): %s", len(missing), ", ".join(missing))

    if args.dry_run:
        return 0

    path = write_page_breaks(mapping, args.sourcetexts_root)
    logger.info("Wrote %s", path)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
