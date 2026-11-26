"""Download the Internet Archive scan of Birnbaum's ha-Siddur ha-Shalem.

The Archive's copy and the Wikimedia Commons file that Hebrew Wikisource transcribes
are the same scan — same 815 leaves, and the same file name down to the byte. That is
what makes this worth doing: the Archive OCR'd the whole book, so its text can be laid
against the Wikisource transcription leaf for leaf without any alignment work, and
each covers what the other lacks.

What the Archive supplies that Wikisource does not is the English. The Hebrew
Wikisource edition is not a faithful reproduction of the 1949 printing — it renders
Birnbaum's English rubrics into Hebrew of its own, and it omits the English-only front
matter entirely — and it leaves the facing English pages to an interwiki transclusion
that is only about a third written. The Archive has all of it.

What the Archive supplies badly is the Hebrew: its OCR reads Hebrew as Latin gibberish.
So the pages written here are the English side of the book, plus, on the Hebrew pages,
Birnbaum's English footnote commentary tangled up with that gibberish in reading order.
Separating those is a later stage's job; nothing here pretends the Hebrew pages'
``ocr/`` files are prose.

**Every file this module writes is named by Wikisource scan page, not by Archive leaf.**
The Archive numbers leaves from zero and the wiki numbers pages from one, so the two
differ by one for the whole length of the book. Keeping that offset in
:func:`scan_page_for_leaf` alone — and nowhere in a filename — is what stops it
becoming a bug that only shows up eight hundred pages later.

Run as::

    uv run python -m opensiddur.importer.birnbaum_siddur.internet_archive
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from opensiddur.common.constants import OUTPUT_DIRECTORY
from opensiddur.importer.util.internet_archive import (
    AGENT_MODEL_ENV_VAR,
    Archive,
    InternetArchiveError,
    ItemFile,
    ItemMetadata,
    connect,
    download_file,
    fetch_metadata,
    leaf_count_from_scandata,
    load_pageindex,
    read_maybe_gzip,
    resolve_agent_model,
    slice_searchtext,
    write_if_changed,
)
from opensiddur.importer.util.pages import (
    birnbaum_siddur_ia_derivatives_directory,
    birnbaum_siddur_ia_directory,
    birnbaum_siddur_ia_ocr_directory,
    default_sourcetexts_root,
)
from opensiddur.importer.util.wikisource import (
    CONTACT_EMAIL_ENV_VAR,
    WikisourceError,
    resolve_contact_email,
)
from opensiddur.importer.util.wikisource_book import (
    MANIFEST_NAME,
    load_manifest,
    page_key,
    save_manifest,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

IA_IDENTIFIER = "PhilipBirnbaumHaSiddurHaShalemTheDailyPrayerBook1949"

# Leaf zero of the scan is scan page one on the wiki. Verified against every page the
# Wikisource transcription numbers itself: 361 printed page numbers agree at this
# offset and none disagrees.
LEAF_OFFSET = -1

PAGE_DIGITS = 3

# Named by suffix rather than in full: the derivative names are the uploaded PDF's
# name plus these, and that name contains spaces, a comma and parentheses. Matching a
# suffix also survives the Archive re-deriving the item under a different name.
PAGE_NUMBERS_SUFFIX = "_page_numbers.json"
PAGEINDEX_SUFFIX = "_hocr_pageindex.json.gz"
SEARCHTEXT_SUFFIX = "_hocr_searchtext.txt.gz"
SCANDATA_SUFFIX = "_scandata.xml"
DJVU_SUFFIX = "_djvu.xml"
TEXT_PDF_SUFFIX = "_text.pdf"

# About a megabyte in total, and enough for the page numbers and all the OCR text.
DEFAULT_DERIVATIVES = (
    PAGE_NUMBERS_SUFFIX,
    PAGEINDEX_SUFFIX,
    SEARCHTEXT_SUFFIX,
    SCANDATA_SUFFIX,
)

# Kept out of git: the word-coordinate file is twenty megabytes and only the deferred
# segmentation stage reads it, and the text PDF is thirty. The full scan PDF is nearly
# half a gigabyte and never lands in sourcetexts at all.
GITIGNORE = """\
# Large derivatives: fetched on demand, never committed.
*_djvu.xml
*_djvu.xml.gz
*_text.pdf
*.part
"""


def leaf_for_scan_page(scan_page: int) -> int:
    """The Archive leaf holding Wikisource scan page ``scan_page``."""
    return scan_page + LEAF_OFFSET


def scan_page_for_leaf(leaf: int) -> int:
    """The Wikisource scan page number of Archive leaf ``leaf``."""
    return leaf - LEAF_OFFSET


def _require(metadata: ItemMetadata, suffix: str) -> ItemFile:
    found = metadata.find_suffix(suffix)
    if found is None:
        raise InternetArchiveError(
            f"Item {metadata.identifier} has no file ending in {suffix!r}. "
            "The Archive may have re-derived it; check the item's file list."
        )
    return found


def download_derivatives(
    archive: Archive,
    metadata: ItemMetadata,
    suffixes: tuple[str, ...],
    destination: Path,
    *,
    force: bool = False,
) -> tuple[dict[str, dict[str, Any]], int]:
    """Fetch the named derivatives into ``destination``, keyed by file name.

    Records the Archive's own sha1 and mtime beside our sha256. Without them a
    re-derivation — the Archive regenerating OCR from the same images — is
    indistinguishable from the scan itself having changed.

    Also returns how many files were actually transferred, so a run that fetched
    nothing can leave the manifest alone.
    """
    records: dict[str, dict[str, Any]] = {}
    fetched = 0
    for suffix in suffixes:
        item_file = _require(metadata, suffix)
        result = download_file(
            archive,
            metadata.identifier,
            item_file,
            destination / item_file.name,
            force=force,
        )
        records[item_file.name] = {
            "suffix": suffix,
            "sha256": result.sha256,
            "size": result.size,
            "ia_sha1": item_file.sha1,
            "ia_mtime": item_file.mtime,
            "format": item_file.format,
        }
        fetched += 0 if result.skipped else 1
        logger.info(
            "%s %s (%d bytes)",
            "Unchanged" if result.skipped else "Fetched",
            item_file.name,
            result.size,
        )
    return records, fetched


def write_leaf_text(
    derivatives_dir: Path,
    metadata: ItemMetadata,
    ocr_dir: Path,
) -> dict[str, Any]:
    """Slice the whole-book OCR into one file per scan page.

    Cross-checks the page index against the scan data before writing anything: if the
    two derivatives disagree about how many leaves the book has, they are not
    describing the same scan, and 815 quietly misaligned files are far worse than a
    failure here.
    """
    pageindex_path = derivatives_dir / _require(metadata, PAGEINDEX_SUFFIX).name
    searchtext_path = derivatives_dir / _require(metadata, SEARCHTEXT_SUFFIX).name
    scandata_path = derivatives_dir / _require(metadata, SCANDATA_SUFFIX).name

    index = load_pageindex(pageindex_path)
    leaves = leaf_count_from_scandata(scandata_path)
    if len(index) != leaves:
        raise InternetArchiveError(
            f"The page index describes {len(index)} leaves but the scan data describes "
            f"{leaves}; refusing to slice text that may not line up with the scan."
        )

    # Bytes, not str: the offsets in the page index are byte offsets, and this text is
    # full of multi-byte UTF-8. Decoding first would shift every leaf after the first
    # non-ASCII character.
    chunks = slice_searchtext(read_maybe_gzip(searchtext_path), index)

    ocr_dir.mkdir(parents=True, exist_ok=True)
    changed = 0
    empty = 0
    for leaf, chunk in enumerate(chunks):
        text = chunk.decode("utf-8", errors="replace")
        if not text.strip():
            empty += 1
        key = page_key(scan_page_for_leaf(leaf), PAGE_DIGITS)
        if write_if_changed(ocr_dir / f"{key}.txt", text):
            changed += 1

    logger.info(
        "%d of %d OCR page(s) changed under %s (%d empty)",
        changed,
        len(chunks),
        ocr_dir,
        empty,
    )
    return {
        "changed": changed,
        "leaf_count": leaves,
        "pages": len(chunks),
        "empty_pages": empty,
        "sliced_from": searchtext_path.name,
        "leaf_offset": LEAF_OFFSET,
    }


def fetch_scan_pdf(
    archive: Archive,
    metadata: ItemMetadata,
    destination_dir: Path,
    *,
    force: bool = False,
) -> Path:
    """Fetch the full scan PDF for human comparison, outside any repository.

    Around half a gigabyte, and useful only to a person reading pages side by side, so
    it goes to the untracked output directory rather than into sourcetexts.
    """
    candidates = [
        f
        for name, f in metadata.files.items()
        if name.lower().endswith(".pdf") and not name.endswith(TEXT_PDF_SUFFIX)
    ]
    if not candidates:
        raise InternetArchiveError(f"Item {metadata.identifier} has no scan PDF")
    item_file = max(candidates, key=lambda f: f.size or 0)

    destination_dir.mkdir(parents=True, exist_ok=True)
    result = download_file(
        archive,
        metadata.identifier,
        item_file,
        destination_dir / item_file.name,
        force=force,
    )
    logger.info(
        "%s the scan PDF at %s",
        "Already had" if result.skipped else "Fetched",
        result.path,
    )
    return result.path


def download_ia(
    contact_email: str,
    sourcetexts_root: Path | None = None,
    *,
    dry_run: bool = False,
    force: bool = False,
    with_djvu: bool = False,
    with_text_pdf: bool = False,
    fetch_pdf: bool = False,
    skip_slice: bool = False,
    pdf_dir: Path | None = None,
    agent_model: str | None = None,
    archive: Archive | None = None,
) -> dict[str, Any]:
    """Download the Archive derivatives and slice their OCR into per-page files.

    Returns the manifest that was written (or, on a dry run, would have been).
    """
    if archive is None:
        archive = connect(contact_email, model=agent_model)

    data_dir = birnbaum_siddur_ia_directory(sourcetexts_root)
    derivatives_dir = birnbaum_siddur_ia_derivatives_directory(sourcetexts_root)
    ocr_dir = birnbaum_siddur_ia_ocr_directory(sourcetexts_root)

    metadata = fetch_metadata(archive, IA_IDENTIFIER)

    suffixes = DEFAULT_DERIVATIVES
    if with_djvu:
        suffixes += (DJVU_SUFFIX,)
    if with_text_pdf:
        suffixes += (TEXT_PDF_SUFFIX,)

    if dry_run:
        names = [_require(metadata, s).name for s in suffixes]
        logger.info(
            "Dry run: would fetch %d derivative(s) into %s:\n  %s",
            len(names),
            derivatives_dir,
            "\n  ".join(names),
        )
        if fetch_pdf:
            logger.info("Dry run: would fetch the scan PDF into %s", pdf_dir or OUTPUT_DIRECTORY)
        return load_manifest(data_dir)

    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / ".gitignore").write_text(GITIGNORE, encoding="utf-8")

    records, fetched = download_derivatives(
        archive, metadata, suffixes, derivatives_dir, force=force
    )

    ocr: dict[str, Any] = {}
    if skip_slice:
        logger.info("Skipping OCR slicing at request.")
    else:
        ocr = write_leaf_text(derivatives_dir, metadata, ocr_dir)

    if fetch_pdf:
        fetch_scan_pdf(
            archive,
            metadata,
            (pdf_dir or OUTPUT_DIRECTORY / "birnbaum_siddur"),
            force=force,
        )

    # The item's own metadata and file list, kept whole. It carries the rights
    # statement, and the sha1 of the scan PDF — which is the evidence that this item
    # and the Commons file Wikisource transcribes are one and the same scan, and so
    # the evidence for pairing the two sources leaf by leaf at all.
    write_if_changed(
        data_dir / "metadata.json",
        json.dumps(
            {
                "identifier": metadata.identifier,
                "metadata": metadata.metadata,
                "files": {
                    name: item.model_dump(exclude_none=True)
                    for name, item in sorted(metadata.files.items())
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )

    previous = load_manifest(data_dir)
    if not fetched and not ocr.get("changed") and previous.get("derivatives"):
        # Nothing was transferred and nothing on disk differs, so rewriting the
        # manifest would change only its timestamp. Same reasoning as the
        # Wikisource downloaders: an unchanged run should leave no diff.
        logger.info("Everything is already up to date.")
        return previous

    manifest = {
        "source": "archive.org",
        "identifier": IA_IDENTIFIER,
        "downloaded_at": datetime.now(UTC).isoformat(),
        "leaf_offset": LEAF_OFFSET,
        "derivatives": records,
        "ocr": ocr,
    }
    save_manifest(manifest, data_dir)
    logger.info("Wrote %s under %s", MANIFEST_NAME, data_dir)
    return manifest


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download the Internet Archive scan derivatives of Birnbaum's ha-Siddur "
            "ha-Shalem into the sourcetexts tree and slice their OCR into one file "
            "per Wikisource scan page."
        )
    )
    parser.add_argument(
        "--sourcetexts-root",
        type=Path,
        default=default_sourcetexts_root(),
        help=(
            "Root of the opensiddur/sourcetexts repository; files are written under "
            "<root>/birnbaum_siddur/ia (default: <repo>/sourcetexts/sources)."
        ),
    )
    parser.add_argument(
        "--contact-email",
        default=None,
        help=(
            "Contact address for the User-Agent header, as the Archive's bot policy "
            f"requires. Falls back to ${CONTACT_EMAIL_ENV_VAR}."
        ),
    )
    parser.add_argument(
        "--agent-model",
        default=None,
        help=(
            "Model name to add to the User-Agent, which the Archive's bot policy asks "
            f"of AI-agent clients. Falls back to ${AGENT_MODEL_ENV_VAR}; omitted "
            "entirely when neither is set."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be fetched without writing anything.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Refetch every derivative, ignoring the checksums already on disk.",
    )
    parser.add_argument(
        "--with-djvu",
        action="store_true",
        help=(
            "Also fetch the 20 MB word-coordinate file, which the page-region "
            "segmentation stage needs. Not committed to git."
        ),
    )
    parser.add_argument(
        "--with-text-pdf",
        action="store_true",
        help="Also fetch the 32 MB text-only PDF. Not committed to git.",
    )
    parser.add_argument(
        "--fetch-pdf",
        action="store_true",
        help=(
            "Also fetch the full ~488 MB scan PDF for reading alongside the text. "
            "Written to the untracked output directory, never to sourcetexts."
        ),
    )
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=None,
        help="Where --fetch-pdf writes (default: <repos>/output/birnbaum_siddur).",
    )
    parser.add_argument(
        "--skip-slice",
        action="store_true",
        help="Download the derivatives but do not rewrite the per-page OCR files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    try:
        contact_email = resolve_contact_email(args.contact_email)
        download_ia(
            contact_email,
            args.sourcetexts_root,
            dry_run=args.dry_run,
            force=args.force,
            with_djvu=args.with_djvu,
            with_text_pdf=args.with_text_pdf,
            fetch_pdf=args.fetch_pdf,
            skip_slice=args.skip_slice,
            pdf_dir=args.pdf_dir,
            agent_model=resolve_agent_model(args.agent_model),
        )
    except (InternetArchiveError, WikisourceError) as exc:
        logger.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
