"""Download the English side of Birnbaum's ha-Siddur ha-Shalem from English Wikisource.

The Hebrew Wikisource transcription of this book does not hold the English pages. It
reaches them by interwiki transclusion — the Hebrew scan page for an English leaf is
nothing but ``{{iwpage|en}}`` — so the facing translation lives on en.wikisource, over
the same Commons scan, in the same ``Page:`` namespace, under the same file name.

It is very incomplete. Rather less than half the book's leaves have a page there at
all, and half of those are blank placeholders; what remains is a few hundred pages,
most of them proofread or validated. That is worth having precisely because it is
human-transcribed: it is the quality layer over the Archive's OCR, page by page, and
:mod:`opensiddur.importer.birnbaum_siddur.correspondence` decides which of the two to
prefer for each page using the proofreading level recorded here.

Pages are written under the same three-digit scan page numbers as the Hebrew side, so
``text/027.txt``, ``en/text/027.txt`` and ``ia/ocr/027.txt`` are always the same leaf.

Run as::

    uv run python -m opensiddur.importer.birnbaum_siddur.en_wikisource
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from opensiddur.importer.birnbaum_siddur.wikisource import BOOK_NAME
from opensiddur.importer.util.pages import (
    birnbaum_siddur_en_credits_directory,
    birnbaum_siddur_en_data_directory,
    birnbaum_siddur_en_text_directory,
    default_sourcetexts_root,
)
from opensiddur.importer.util.wikisource import (
    CONTACT_EMAIL_ENV_VAR,
    Wiki,
    WikisourceError,
    connect,
    resolve_contact_email,
)
from opensiddur.importer.util.wikisource_book import (
    ScanPageLayout,
    download_scan_pages,
    load_manifest,
    save_manifest,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVER = "en.wikisource.org"
WIKI_NAMESPACE = "Page"  # ProofreadPage namespace 104, as named on en.wikisource

# The Hebrew side numbers its files to three digits because the book has 815 leaves.
# This must match it, and must not be inferred: `download_scan_pages` would otherwise
# take its width from the highest page it happened to find, and only a third of the
# leaves exist here. A future run finding nothing above page 99 would start writing
# two-digit names, silently unpairing this tree from the other two.
PAGE_DIGITS = 3

# ProofreadPage's own proofreading status, stored in the page's header:
#   0 without text, 1 problematic, 2 not proofread, 3 proofread, 4 validated.
_PAGEQUALITY_RE = re.compile(r"<pagequality\s+level\s*=\s*[\"'](\d)[\"']", re.IGNORECASE)

# ProofreadPage wraps the running header and footer of a scan page in <noinclude>.
# Everything between them is the page's actual text.
_NOINCLUDE_HEAD_RE = re.compile(r"\A\s*<noinclude>.*?</noinclude>", re.DOTALL | re.IGNORECASE)
_NOINCLUDE_TAIL_RE = re.compile(r"<noinclude>.*?</noinclude>\s*\Z", re.DOTALL | re.IGNORECASE)

# At and above this level a human has read the page against the scan, so it is
# preferred over OCR. Below it — problematic, or never proofread — it is not.
PROOFREAD_LEVEL = 3


def page_quality(wikitext: str) -> int | None:
    """The ProofreadPage proofreading level of a page, or None if unstated."""
    match = _PAGEQUALITY_RE.search(wikitext)
    return int(match.group(1)) if match else None


def page_body(wikitext: str) -> str:
    """The page's text, with the ProofreadPage header and footer removed.

    A great many of these pages exist only as an empty shell — created by the
    proofreading interface, never typed into — and are indistinguishable from a real
    page until the wrappers come off.
    """
    body = _NOINCLUDE_HEAD_RE.sub("", wikitext)
    body = _NOINCLUDE_TAIL_RE.sub("", body)
    return body.strip()


def is_usable(wikitext: str) -> bool:
    """Whether this page's text should be preferred over the Archive's OCR."""
    level = page_quality(wikitext)
    return level is not None and level >= PROOFREAD_LEVEL and bool(page_body(wikitext))


def download_book(
    contact_email: str,
    sourcetexts_root: Path | None = None,
    *,
    dry_run: bool = False,
    force: bool = False,
    wiki: Wiki | None = None,
) -> dict[str, Any]:
    """Download every transcribed English page of the book, skipping unchanged ones.

    Returns the manifest that was written (or, on a dry run, would have been).
    """
    if wiki is None:
        wiki = connect(SERVER, contact_email)

    data_dir = birnbaum_siddur_en_data_directory(sourcetexts_root)
    manifest = load_manifest(data_dir)

    scans = download_scan_pages(
        wiki,
        BOOK_NAME,
        ScanPageLayout(
            data_dir=data_dir,
            text_dir=birnbaum_siddur_en_text_directory(sourcetexts_root),
            credits_dir=birnbaum_siddur_en_credits_directory(sourcetexts_root),
        ),
        dry_run=dry_run,
        force=force,
        manifest_pages=manifest.get("pages") or {},
        digits=PAGE_DIGITS,
    )

    if dry_run:
        logger.info(
            "Dry run: would write %d page(s) under %s", len(scans.stale), data_dir
        )
        return manifest

    if not scans.written:
        # Leaving the manifest untouched keeps a no-op re-run genuinely no-op.
        logger.info("Everything is already up to date.")
        return manifest

    manifest = {
        "source": wiki.server,
        "book_name": BOOK_NAME,
        "namespace": WIKI_NAMESPACE,
        "downloaded_at": datetime.now(UTC).isoformat(),
        "pages": scans.pages,
    }
    save_manifest(manifest, data_dir)
    logger.info("Wrote %d page(s) under %s", scans.written, data_dir)
    return manifest


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download the English pages of Birnbaum's ha-Siddur ha-Shalem from English "
            "Wikisource into the sourcetexts tree, refetching only what has changed."
        )
    )
    parser.add_argument(
        "--sourcetexts-root",
        type=Path,
        default=default_sourcetexts_root(),
        help=(
            "Root of the opensiddur/sourcetexts repository; page text is written under "
            "<root>/birnbaum_siddur/en (default: <repo>/sourcetexts/sources)."
        ),
    )
    parser.add_argument(
        "--contact-email",
        default=None,
        help=(
            "Contact address for the User-Agent header, as Wikimedia's User-Agent "
            f"policy requires. Falls back to ${CONTACT_EMAIL_ENV_VAR}."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Report what would be downloaded without writing anything. Still performs "
            "the read-only enumeration and change check."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Refetch every page, ignoring the manifest.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    try:
        contact_email = resolve_contact_email(args.contact_email)
        download_book(
            contact_email,
            args.sourcetexts_root,
            dry_run=args.dry_run,
            force=args.force,
        )
    except WikisourceError as exc:
        logger.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
