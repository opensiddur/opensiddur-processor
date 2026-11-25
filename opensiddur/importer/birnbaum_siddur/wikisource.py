"""Download the Birnbaum ha-Siddur ha-Shalem from Hebrew Wikisource into sourcetexts.

Writes one wikitext file and one credits file per scan page, mirroring the layout the
JPS 1917 importer uses, plus a manifest recording each page's revision id so later
runs only refetch what actually changed.

The HTTP etiquette — batching, pacing, maxlag, backoff, identification — lives in
:mod:`opensiddur.importer.util.wikisource`, along with the reasoning for reading the
Action API rather than the monthly dumps.

Note that the Wikisource edition is not a faithful transcription of the 1949
printing: it renders the English rubrics into Hebrew, adds Eretz Yisrael customs and
makes textual corrections. Anything describing this source downstream should call it
the Wikisource edition, not Birnbaum 1949.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from opensiddur.importer.util.pages import (
    birnbaum_siddur_credits_directory,
    birnbaum_siddur_data_directory,
    birnbaum_siddur_external_credits_directory,
    birnbaum_siddur_external_text_directory,
    birnbaum_siddur_source_credits_directory,
    birnbaum_siddur_source_text_directory,
    birnbaum_siddur_text_directory,
    default_sourcetexts_root,
    relative_path_to_title,
    title_to_relative_path,
)
from opensiddur.importer.util.wikisource import (
    CONTACT_EMAIL_ENV_VAR,
    Wiki,
    WikisourceError,
    connect,
    download_closure,
    fetch_contributors,
    find_sections,
    find_transclusions,
    is_redirect,
    list_pages_with_prefix,
    normalize_title,
    resolve_contact_email,
)
from opensiddur.importer.util.wikisource_book import (
    ScanPageLayout,
    download_scan_pages,
    load_manifest,
    save_manifest,
    sha256_text,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVER = "he.wikisource.org"
WIKI_NAMESPACE = "עמוד"  # ProofreadPage namespace 104, as named on he.wikisource
BOOK_NAME = "Philip Birnbaum - ha-Siddur ha-Shalem (The Daily Prayer Book,1949).pdf"

# The scan pages are nearly empty: they lay out the printed page and pull the actual
# text in from this mainspace subtree with {{#קטע:…}} (labeled section transclusion).
SOURCE_ROOT = "הסידור השלם (בירנבוים)"

# Stop runaway traversal if the wiki ever grows a link out into unrelated content.
# The real graph settles in two hops; anything deeper deserves a look before it is
# silently downloaded.
MAX_SOURCE_DEPTH = 5

STRUCTURE_NAME = "structure.json"


def is_scan_page(title: str) -> bool:
    """Whether a title names one of the scan pages we download page-by-page."""
    return normalize_title(title).startswith(f"{WIKI_NAMESPACE}:")


def classify_source_title(title: str) -> tuple[str, str]:
    """Split a title into which tree it belongs in and its path within that tree.

    Subtree pages drop the shared root prefix, so the on-disk layout mirrors the
    siddur's own organization rather than repeating its name in every path. Anything
    else keeps its full title, and the two trees stay separate so a path is never
    ambiguous about whether a prefix was stripped.
    """
    title = normalize_title(title)
    if title == SOURCE_ROOT:
        return "source", "index"
    if title.startswith(f"{SOURCE_ROOT}/"):
        return "source", title[len(SOURCE_ROOT) + 1 :]
    return "external", title


def source_page_paths(
    title: str, sourcetexts_root: Path | None = None
) -> tuple[Path, Path]:
    """Where the wikitext and credits for a source page belong."""
    area, relative = classify_source_title(title)
    if area == "source":
        text_dir = birnbaum_siddur_source_text_directory(sourcetexts_root)
        credits_dir = birnbaum_siddur_source_credits_directory(sourcetexts_root)
    else:
        text_dir = birnbaum_siddur_external_text_directory(sourcetexts_root)
        credits_dir = birnbaum_siddur_external_credits_directory(sourcetexts_root)
    relative_path = title_to_relative_path(relative)
    return text_dir / relative_path, credits_dir / relative_path


def download_source_pages(
    wiki: Wiki,
    sourcetexts_root: Path | None = None,
    *,
    dry_run: bool = False,
    force: bool = False,
    manifest_pages: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    """Download the mainspace pages the scan pages transclude their text from.

    Returns manifest entries keyed by wiki title, and how many pages were written.
    Scan pages are deliberately not followed: they are downloaded separately, and the
    two layers reference each other, so following them here would fetch the whole
    book twice.
    """
    recorded: dict[str, Any] = {} if force else dict(manifest_pages or {})

    logger.info("Enumerating the %s subtree ...", SOURCE_ROOT)
    roots = list_pages_with_prefix(wiki, f"{SOURCE_ROOT}/")
    # The prefix search cannot match the root page itself, whose title has no slash.
    roots.append(SOURCE_ROOT)
    logger.info("Found %d pages in the subtree", len(roots))

    logger.info("Following transclusions ...")
    revisions = download_closure(
        wiki,
        roots,
        include=lambda title: not is_scan_page(title),
        max_depth=MAX_SOURCE_DEPTH,
    )

    outside = sorted(t for t in revisions if classify_source_title(t)[0] == "external")
    if outside:
        logger.info("Pulled in %d page(s) from outside the subtree: %s", len(outside), outside)

    titles = sorted(revisions)
    stale = [
        title
        for title in titles
        if force
        or recorded.get(title, {}).get("revid") != revisions[title].revid
        or not all(p.is_file() for p in source_page_paths(title, sourcetexts_root))
    ]
    logger.info("%d of %d source pages need writing", len(stale), len(titles))

    if dry_run or not stale:
        if not stale:
            logger.info("Source pages are already up to date.")
        return recorded, 0

    logger.info("Fetching contributors for source pages ...")
    contributors = fetch_contributors(wiki, stale)

    written = 0
    for title in stale:
        revision = revisions[title]
        if revision.content is None:
            logger.warning("No wikitext returned for %s; leaving it for the next run", title)
            continue
        text_path, credits_path = source_page_paths(title, sourcetexts_root)
        credits_text = "\n".join(contributors.get(title, []))

        text_path.parent.mkdir(parents=True, exist_ok=True)
        credits_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(revision.content, encoding="utf-8", newline="\n")
        credits_path.write_text(credits_text, encoding="utf-8", newline="\n")

        redirect, target = is_redirect(revision.content)
        recorded[title] = {
            "revid": revision.revid,
            "timestamp": revision.timestamp,
            "text_sha256": sha256_text(revision.content),
            "credits_sha256": sha256_text(credits_text),
            "redirect_target": target if redirect else None,
        }
        written += 1
        if written % 50 == 0:
            logger.info("Wrote %d/%d source pages", written, len(stale))

    logger.info("Wrote %d source pages", written)
    return recorded, written


def _iter_stored_pages(
    sourcetexts_root: Path | None = None,
) -> Iterator[tuple[str, Path]]:
    """Every downloaded page as ``(wiki title, path to its wikitext)``."""
    scan_dir = birnbaum_siddur_text_directory(sourcetexts_root)
    if scan_dir.is_dir():
        for path in sorted(scan_dir.glob("*.txt")):
            yield f"{WIKI_NAMESPACE}:{BOOK_NAME}/{int(path.stem)}", path

    for area, directory in (
        ("source", birnbaum_siddur_source_text_directory(sourcetexts_root)),
        ("external", birnbaum_siddur_external_text_directory(sourcetexts_root)),
    ):
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.txt")):
            relative = relative_path_to_title(path.relative_to(directory))
            if area == "source":
                title = SOURCE_ROOT if relative == "index" else f"{SOURCE_ROOT}/{relative}"
            else:
                title = relative
            yield title, path


def build_structure(sourcetexts_root: Path | None = None) -> dict[str, Any]:
    """Describe how the downloaded pages fit together.

    Derived entirely from the wikitext on disk, so it can be regenerated at any time
    and is never a second source of truth. What it records is the thing Wikisource
    contributes beyond the raw text: which named sections each page defines, and
    which sections every other page pulls in. The scan pages are included precisely
    because their transclusions are what tie the printed pagination to the liturgical
    text.
    """
    pages: dict[str, Any] = {}
    defined: dict[str, set[str]] = {}
    data_dir = birnbaum_siddur_data_directory(sourcetexts_root)

    for title, path in _iter_stored_pages(sourcetexts_root):
        content = path.read_text(encoding="utf-8")
        redirect, target = is_redirect(content)
        sections = find_sections(content)
        defined[normalize_title(title)] = set(sections)
        pages[title] = {
            "path": str(path.relative_to(data_dir)),
            "redirect_target": target if redirect else None,
            "defines": sections,
            "transcludes": [
                {"title": ref_title, "section": section}
                for ref_title, section in find_transclusions(content)
            ],
        }

    dangling = sorted(
        {
            (reference["title"], reference["section"])
            for page in pages.values()
            for reference in page["transcludes"]
            if reference["section"] not in defined.get(normalize_title(reference["title"]), ())
        }
    )

    return {
        "generated_from": (
            "the wikitext in text/, source/text/ and external/text/; regenerate rather "
            "than edit by hand"
        ),
        "pages": pages,
        "dangling": [{"title": t, "section": s} for t, s in dangling],
    }


def save_structure(structure: dict[str, Any], sourcetexts_root: Path | None = None) -> Path:
    path = birnbaum_siddur_data_directory(sourcetexts_root) / STRUCTURE_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(structure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def download_book(
    contact_email: str,
    sourcetexts_root: Path | None = None,
    *,
    dry_run: bool = False,
    force: bool = False,
    wiki: Wiki | None = None,
    include_source: bool = True,
) -> dict[str, Any]:
    """Download every transcribed page of the book, skipping unchanged ones.

    Returns the manifest that was written (or, on a dry run, would have been).
    """
    if wiki is None:
        wiki = connect(SERVER, contact_email)

    data_dir = birnbaum_siddur_data_directory(sourcetexts_root)

    manifest = load_manifest(data_dir)

    scans = download_scan_pages(
        wiki,
        BOOK_NAME,
        ScanPageLayout(
            data_dir=data_dir,
            text_dir=birnbaum_siddur_text_directory(sourcetexts_root),
            credits_dir=birnbaum_siddur_credits_directory(sourcetexts_root),
        ),
        dry_run=dry_run,
        force=force,
        manifest_pages=manifest.get("pages") or {},
    )
    manifest_pages = scans.pages
    written = scans.written

    # The scan pages carry almost no text of their own; this is where it lives.
    source_pages: dict[str, Any] = {} if force else dict(manifest.get("source_pages") or {})
    source_written = 0
    if include_source:
        source_pages, source_written = download_source_pages(
            wiki,
            sourcetexts_root,
            dry_run=dry_run,
            force=force,
            manifest_pages=source_pages,
        )

    if dry_run:
        logger.info(
            "Dry run: would write %d scan page(s) and refresh source pages under %s",
            len(scans.stale),
            data_dir,
        )
        return manifest

    structure_file = data_dir / STRUCTURE_NAME
    if not (written or source_written or not structure_file.is_file()):
        # Nothing changed. Leaving the manifest alone keeps a no-op re-run genuinely
        # no-op, so an unchanged run never shows up as a diff.
        logger.info("Everything is already up to date.")
        return manifest

    manifest = {
        "source": wiki.server,
        "book_name": BOOK_NAME,
        "namespace": WIKI_NAMESPACE,
        "source_root": SOURCE_ROOT,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "pages": manifest_pages,
        "source_pages": source_pages,
    }
    # Written once, at the end. A crash mid-run then leaves the previous manifest
    # intact and the interrupted pages simply look stale next time, which is safer
    # than a per-page write that could claim a page is current when its file was
    # only half written.
    save_manifest(manifest, data_dir)
    structure = build_structure(sourcetexts_root)
    save_structure(structure, sourcetexts_root)
    logger.info(
        "Wrote %d scan page(s) and %d source page(s); %d pages indexed, %d dangling reference(s)",
        written,
        source_written,
        len(structure["pages"]),
        len(structure["dangling"]),
    )
    return manifest


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download the Birnbaum ha-Siddur ha-Shalem from Hebrew Wikisource into the "
            "sourcetexts tree, refetching only pages that have changed."
        )
    )
    parser.add_argument(
        "--sourcetexts-root",
        type=Path,
        default=default_sourcetexts_root(),
        help=(
            "Root of the opensiddur/sourcetexts repository; pages are written under "
            "<root>/birnbaum_siddur (default: <repo>/sourcetexts/sources)."
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
    parser.add_argument(
        "--skip-source",
        action="store_true",
        help=(
            "Download only the page-by-page scans, not the mainspace pages they "
            "transclude their text from. Rarely what you want: the scan pages on "
            "their own contain almost no text."
        ),
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
            include_source=not args.skip_source,
        )
    except WikisourceError as exc:
        logger.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
