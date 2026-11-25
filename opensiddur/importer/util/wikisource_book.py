"""Downloading a scan-backed Wikisource book to disk, one file per page.

:mod:`opensiddur.importer.util.wikisource` deliberately knows nothing about the
filesystem: it speaks the Action API and returns revisions. This module is the layer
above it that owns the parts every book downloader would otherwise repeat — where the
files go, and the manifest that lets a re-run skip pages that have not changed.

What stays with the individual importers is whatever is genuinely particular to their
book: the Birnbaum siddur's mainspace source tree and its structure index have no JPS
equivalent, and the JPS scan pages carry their own text.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from opensiddur.importer.util.wikisource import (
    Wiki,
    WikisourceError,
    fetch_contributors,
    fetch_revisions,
    list_book_pages,
)

logger = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.json"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def page_key(page_num: int, digits: int) -> str:
    """Zero-padded page identifier, used for both filenames and manifest keys."""
    return f"{page_num:0{digits}d}"


def manifest_path(data_dir: Path) -> Path:
    return data_dir / MANIFEST_NAME


def load_manifest(data_dir: Path) -> dict[str, Any]:
    """Read the manifest, or return an empty one if this is a first run."""
    path = manifest_path(data_dir)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        logger.warning(
            "Manifest at %s is unreadable (%s); treating every page as new. "
            "Use --force to rewrite it cleanly.",
            path,
            exc,
        )
        return {}


def save_manifest(manifest: dict[str, Any], data_dir: Path) -> None:
    path = manifest_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def download_date(data_dir: Path) -> str | None:
    """The date the manifest was last written, as ``YYYY-MM-DD``, or None.

    This is what a TEI ``sourceDesc`` should report as the date the source was
    retrieved, so that the header states when the wikitext underneath it was actually
    fetched rather than a date someone typed once.
    """
    stamp = load_manifest(data_dir).get("downloaded_at")
    if not isinstance(stamp, str) or not stamp:
        return None
    # Written by datetime.isoformat(), so the date is everything before the "T"; be
    # lenient about anything else that parses, and report nothing if it does not.
    try:
        return datetime.fromisoformat(stamp).date().isoformat()
    except ValueError:
        logger.warning("Manifest in %s has an uninterpretable date: %r", data_dir, stamp)
        return None


def needs_download(
    key: str,
    revid: int,
    manifest_pages: dict[str, Any],
    text_dir: Path,
    credits_dir: Path,
) -> bool:
    """Whether a page must be fetched: unknown, changed, or missing on disk.

    The on-disk check matters because a manifest entry alone does not prove the files
    survived — someone may have deleted or partially written them.
    """
    recorded = manifest_pages.get(key)
    if recorded is None or recorded.get("revid") != revid:
        return True
    return not (
        (text_dir / f"{key}.txt").is_file() and (credits_dir / f"{key}.txt").is_file()
    )


@dataclass
class ScanPageLayout:
    """Where one book's per-page files live."""

    data_dir: Path
    text_dir: Path
    credits_dir: Path


@dataclass
class ScanDownloadResult:
    """What one pass over a book's scan pages found and wrote."""

    pages: dict[str, Any] = field(default_factory=dict)
    titles_by_number: dict[int, str] = field(default_factory=dict)
    stale: list[int] = field(default_factory=list)
    written: int = 0
    digits: int = 1


def download_scan_pages(
    wiki: Wiki,
    book_name: str,
    layout: ScanPageLayout,
    *,
    dry_run: bool = False,
    force: bool = False,
    manifest_pages: dict[str, Any] | None = None,
    digits: int | None = None,
) -> ScanDownloadResult:
    """Download every transcribed page of ``book_name``, skipping unchanged ones.

    Enumerates what is actually transcribed, probes revision ids in bulk, and only then
    fetches wikitext and contributors for the pages that need writing. Returns manifest
    entries keyed by zero-padded page number, alongside what was found and written.
    """
    recorded: dict[str, Any] = {} if force else dict(manifest_pages or {})

    logger.info("Enumerating pages of %s ...", book_name)
    titles_by_number = list_book_pages(wiki, book_name)
    if not titles_by_number:
        raise WikisourceError(
            f"No transcribed pages found for {book_name!r} on {wiki.server}. "
            "Has the book been moved or renamed?"
        )

    page_numbers = sorted(titles_by_number)
    if digits is None:
        digits = len(str(page_numbers[-1]))
    logger.info(
        "Found %d transcribed pages (%d-%d)",
        len(page_numbers),
        page_numbers[0],
        page_numbers[-1],
    )

    # A revision-id-only probe: no wikitext is serialised, so this stays cheap even
    # when nothing has changed.
    logger.info("Checking which pages have changed ...")
    latest = fetch_revisions(
        wiki, [titles_by_number[n] for n in page_numbers], include_content=False
    )

    stale: list[int] = []
    for number in page_numbers:
        title = titles_by_number[number]
        revision = latest.get(title)
        if revision is None:
            logger.warning("No revision reported for %s; skipping", title)
            continue
        if force or needs_download(
            page_key(number, digits),
            revision.revid,
            recorded,
            layout.text_dir,
            layout.credits_dir,
        ):
            stale.append(number)

    logger.info("%d of %d scan pages need downloading", len(stale), len(page_numbers))

    result = ScanDownloadResult(
        pages=recorded,
        titles_by_number=titles_by_number,
        stale=stale,
        digits=digits,
    )

    if not stale:
        logger.info("Scan pages are already up to date.")
        return result
    if dry_run:
        return result

    stale_titles = [titles_by_number[n] for n in stale]
    logger.info("Fetching wikitext ...")
    contents = fetch_revisions(wiki, stale_titles, include_content=True)
    logger.info("Fetching contributors ...")
    contributors = fetch_contributors(wiki, stale_titles)

    layout.text_dir.mkdir(parents=True, exist_ok=True)
    layout.credits_dir.mkdir(parents=True, exist_ok=True)

    for number in stale:
        title = titles_by_number[number]
        revision = contents.get(title)
        if revision is None or revision.content is None:
            logger.warning("No wikitext returned for %s; leaving it for the next run", title)
            continue

        key = page_key(number, digits)
        credits_text = "\n".join(contributors.get(title, []))

        for path, text in ((layout.text_dir / f"{key}.txt", revision.content),
                           (layout.credits_dir / f"{key}.txt", credits_text)):
            path.write_text(text, encoding="utf-8", newline="\n")

        recorded[key] = {
            "revid": revision.revid,
            "timestamp": revision.timestamp,
            "text_sha256": sha256_text(revision.content),
            "credits_sha256": sha256_text(credits_text),
        }
        result.written += 1
        if result.written % 50 == 0:
            logger.info("Wrote %d/%d scan pages", result.written, len(stale))

    return result
