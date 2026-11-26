"""Download Open Siddur haggadah compilation and HebrewBooks 1822 PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml

from opensiddur.importer.util.pages import (
    default_sourcetexts_root,
    feinstein_haggadah_data_directory,
    heidenheim_haggadah_data_directory,
    heidenheim_pdf_path,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USER_AGENT = (
    "OpenSiddur-Processor/1.0 (https://github.com/opensiddur/opensiddur-processor; "
    "opensiddur@example.com)"
)

OSP_PERMALINK = (
    "https://opensiddur.org/compilations/table-guides-and-haggadot/"
    "passover-seder/haggadah-for-pesah-an-english-translation/"
)
OSP_POST_ID = 6207
OSP_JSON_URL = (
    f"https://opensiddur.org/wp-admin/admin-post.php?"
    f"action=export_json&post_id={OSP_POST_ID}&extension=.json"
)
OSP_XML_URL = (
    f"https://opensiddur.org/wp-admin/admin-post.php?"
    f"action=export_xml&post_id={OSP_POST_ID}&extension=.xml"
)

HEBREWBOOKS_SEFER_ID = 4909
HEBREWBOOKS_PAGE_URL = f"https://www.hebrewbooks.org/{HEBREWBOOKS_SEFER_ID}"
HEBREWBOOKS_PDF_URLS = (
    f"https://www.hebrewbooks.org/pdfpager.aspx?req={HEBREWBOOKS_SEFER_ID}",
    f"https://hebrewbooks.org/pdfpager.aspx?req={HEBREWBOOKS_SEFER_ID}",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _download_url(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 300,
) -> bytes:
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    response = requests.get(url, headers=hdrs, timeout=timeout)
    response.raise_for_status()
    return response.content


def _discover_hebrewbooks_pdf_url(html: str) -> str | None:
    patterns = [
        r'href="([^"]*pdfpager\.aspx\?req=\d+[^"]*)"',
        r'href="([^"]*Download[^"]*\.pdf[^"]*)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            href = match.group(1).replace("&amp;", "&")
            if href.startswith("http"):
                return href
            if href.startswith("/"):
                return f"https://www.hebrewbooks.org{href}"
            return f"https://www.hebrewbooks.org/{href}"
    return None


def download_osp_compilation(
    sourcetexts_root: Path | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Download JSON (and XML) export from opensiddur.org."""
    data_dir = feinstein_haggadah_data_directory(sourcetexts_root)
    manifest_path = data_dir / "manifest.json"

    if dry_run:
        logger.info("Would download OSP JSON from %s", OSP_JSON_URL)
        logger.info("Would write under %s", data_dir)
        return {"dry_run": True}

    data_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading OSP compilation JSON ...")
    json_bytes = _download_url(OSP_JSON_URL)
    json_path = data_dir / "compilation.json"
    json_path.write_bytes(json_bytes)
    compilation = json.loads(json_bytes.decode("utf-8"))

    xml_path = data_dir / "compilation.xml"
    xml_downloaded = False
    try:
        logger.info("Downloading OSP compilation XML ...")
        xml_bytes = _download_url(OSP_XML_URL)
        if xml_bytes.strip().startswith(b"<"):
            xml_path.write_bytes(xml_bytes)
            xml_downloaded = True
    except requests.RequestException as exc:
        logger.warning("OSP XML export failed: %s", exc)

    metadata = {
        "post_id": compilation.get("post_id", OSP_POST_ID),
        "title": compilation.get("title"),
        "author": compilation.get("author"),
        "permalink": compilation.get("permalink", OSP_PERMALINK),
        "date": compilation.get("date"),
        "last_updated": compilation.get("last_updated"),
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "source_url": OSP_PERMALINK,
    }
    metadata_path = data_dir / "metadata.yaml"
    metadata_path.write_text(
        yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )

    files: list[dict[str, Any]] = [
        {
            "path": "compilation.json",
            "sha256": _sha256_file(json_path),
            "bytes": json_path.stat().st_size,
        },
        {
            "path": "metadata.yaml",
            "sha256": _sha256_file(metadata_path),
            "bytes": metadata_path.stat().st_size,
        },
    ]
    if xml_downloaded:
        files.append(
            {
                "path": "compilation.xml",
                "sha256": _sha256_file(xml_path),
                "bytes": xml_path.stat().st_size,
            }
        )

    manifest = {
        "source": "opensiddur.org",
        "permalink": OSP_PERMALINK,
        "json_url": OSP_JSON_URL,
        "xml_url": OSP_XML_URL if xml_downloaded else None,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }
    _write_manifest(manifest_path, manifest)
    logger.info("Wrote OSP manifest to %s", manifest_path)
    return manifest


def download_hebrewbooks_pdf(
    sourcetexts_root: Path | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any] | None:
    """Download 1822 Heidenheim PDF from HebrewBooks.org if accessible."""
    data_dir = heidenheim_haggadah_data_directory(sourcetexts_root)
    pdf_path = data_dir / "heidenheim_1822.pdf"
    manifest_path = data_dir / "manifest.json"

    existing = heidenheim_pdf_path(sourcetexts_root)
    if existing and existing.is_file() and not dry_run:
        manifest = {
            "source": "hebrewbooks.org",
            "sefer_id": HEBREWBOOKS_SEFER_ID,
            "page_url": HEBREWBOOKS_PAGE_URL,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "pdf_downloaded": True,
            "files": [
                {
                    "path": existing.name,
                    "sha256": _sha256_file(existing),
                    "bytes": existing.stat().st_size,
                }
            ],
            "note": "PDF supplied locally; not downloaded by script.",
        }
        _write_manifest(manifest_path, manifest)
        logger.info("Using existing PDF at %s", existing)
        return manifest

    if dry_run:
        logger.info("Would attempt HebrewBooks PDF from %s", HEBREWBOOKS_PAGE_URL)
        return {"dry_run": True}

    data_dir.mkdir(parents=True, exist_ok=True)
    pdf_url: str | None = None
    pdf_bytes: bytes | None = None

    try:
        page_html = _download_url(HEBREWBOOKS_PAGE_URL, timeout=60).decode(
            "utf-8", errors="replace"
        )
        pdf_url = _discover_hebrewbooks_pdf_url(page_html)
    except requests.RequestException as exc:
        logger.warning("Could not fetch HebrewBooks sefer page: %s", exc)

    candidates = [pdf_url] if pdf_url else []
    candidates.extend(u for u in HEBREWBOOKS_PDF_URLS if u not in candidates)

    for url in candidates:
        if not url:
            continue
        try:
            logger.info("Trying HebrewBooks PDF URL %s", url)
            content = _download_url(url, timeout=120)
            if content[:4] == b"%PDF":
                pdf_bytes = content
                pdf_url = url
                break
        except requests.RequestException as exc:
            logger.warning("HebrewBooks PDF attempt failed for %s: %s", url, exc)

    if pdf_bytes is None:
        logger.warning(
            "HebrewBooks PDF download failed (Cloudflare or URL change). "
            "Continue without page-break reference PDF."
        )
        manifest = {
            "source": "hebrewbooks.org",
            "sefer_id": HEBREWBOOKS_SEFER_ID,
            "page_url": HEBREWBOOKS_PAGE_URL,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "pdf_downloaded": False,
            "warning": "PDF not available; tei:pb alignment requires manual page_breaks.json",
        }
        _write_manifest(manifest_path, manifest)
        return manifest

    pdf_path.write_bytes(pdf_bytes)
    manifest = {
        "source": "hebrewbooks.org",
        "sefer_id": HEBREWBOOKS_SEFER_ID,
        "page_url": HEBREWBOOKS_PAGE_URL,
        "pdf_url": pdf_url,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "pdf_downloaded": True,
        "files": [
            {
                "path": "heidenheim_1822.pdf",
                "sha256": _sha256_file(pdf_path),
                "bytes": pdf_path.stat().st_size,
            }
        ],
    }
    _write_manifest(manifest_path, manifest)
    logger.info("Wrote HebrewBooks PDF to %s", pdf_path)
    return manifest


def download_all(
    sourcetexts_root: Path | None = None,
    *,
    dry_run: bool = False,
    skip_pdf: bool = False,
) -> None:
    download_osp_compilation(sourcetexts_root, dry_run=dry_run)
    if not skip_pdf:
        download_hebrewbooks_pdf(sourcetexts_root, dry_run=dry_run)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download the Open Siddur Feinstein/Heidenheim haggadah compilation "
            "and (optionally) the HebrewBooks 1822 PDF facsimile."
        )
    )
    parser.add_argument(
        "--sourcetexts-root",
        type=Path,
        default=default_sourcetexts_root(),
        help="Root of sourcetexts (default: <repo>/sourcetexts/sources).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without downloading or writing files.",
    )
    parser.add_argument(
        "--skip-pdf",
        action="store_true",
        help="Skip HebrewBooks PDF download.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    try:
        download_all(
            args.sourcetexts_root,
            dry_run=args.dry_run,
            skip_pdf=args.skip_pdf,
        )
    except Exception as exc:
        logger.error("Download failed: %s", exc)
        raise
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
