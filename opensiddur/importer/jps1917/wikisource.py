"""Download the JPS 1917 Bible translation from English Wikisource into sourcetexts.

Writes one wikitext file and one credits file per scan page, plus a manifest recording
each page's revision id so later runs only refetch what actually changed.

Unlike the Birnbaum siddur, these scan pages hold their own text: there is no labeled
section transclusion to follow, so a page-by-page download is the whole job.

The HTTP etiquette — batching, pacing, maxlag, backoff, identification — lives in
:mod:`opensiddur.importer.util.wikisource`, along with the reasoning for reading the
Action API rather than the monthly dumps. The per-page filesystem layout and the
manifest live in :mod:`opensiddur.importer.util.wikisource_book`.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from opensiddur.importer.util.pages import (
    default_sourcetexts_root,
    jps1917_credits_directory,
    jps1917_data_directory,
    jps1917_text_directory,
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
BOOK_NAME = "JPS-1917-Universal.djvu"


def download_book(
    contact_email: str,
    sourcetexts_root: Path | None = None,
    *,
    dry_run: bool = False,
    force: bool = False,
    wiki: Wiki | None = None,
) -> dict[str, Any]:
    """Download every transcribed page of the book, skipping unchanged ones.

    Returns the manifest that was written (or, on a dry run, would have been).
    """
    if wiki is None:
        wiki = connect(SERVER, contact_email)

    data_dir = jps1917_data_directory(sourcetexts_root)
    manifest = load_manifest(data_dir)

    scans = download_scan_pages(
        wiki,
        BOOK_NAME,
        ScanPageLayout(
            data_dir=data_dir,
            text_dir=jps1917_text_directory(sourcetexts_root),
            credits_dir=jps1917_credits_directory(sourcetexts_root),
        ),
        dry_run=dry_run,
        force=force,
        manifest_pages=manifest.get("pages") or {},
    )

    if dry_run:
        logger.info(
            "Dry run: would write %d page(s) under %s", len(scans.stale), data_dir
        )
        return manifest

    if not scans.written:
        # Nothing changed. Leaving the manifest alone keeps a no-op re-run genuinely
        # no-op, so an unchanged run never shows up as a diff.
        logger.info("Everything is already up to date.")
        return manifest

    manifest = {
        "source": wiki.server,
        "book_name": BOOK_NAME,
        "namespace": WIKI_NAMESPACE,
        "downloaded_at": datetime.now(UTC).isoformat(),
        "pages": scans.pages,
    }
    # Written once, at the end. A crash mid-run then leaves the previous manifest
    # intact and the interrupted pages simply look stale next time, which is safer
    # than a per-page write that could claim a page is current when its file was
    # only half written.
    save_manifest(manifest, data_dir)
    logger.info("Wrote %d page(s) under %s", scans.written, data_dir)
    return manifest


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download JPS 1917 Bible pages from English Wikisource into the sourcetexts "
            "tree, refetching only pages that have changed."
        )
    )
    parser.add_argument(
        "--sourcetexts-root",
        type=Path,
        default=default_sourcetexts_root(),
        help=(
            "Root of the opensiddur/sourcetexts repository; page text is written under "
            "<root>/jps1917 (default: <repo>/sourcetexts/sources)."
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
