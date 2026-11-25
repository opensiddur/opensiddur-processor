"""Download the hebcal leyning data that supplies haftarot and festival readings.

The aliyah divisions of the weekly parshiyot come from Miqra al pi ha-Masorah instead (see
``aliyot.py``); hebcal supplies what MAM does not encode at all — the haftarot, the festival
and special-Shabbat readings, and the modern triennial cycle. hebcal's own weekly aliyot are
downloaded too, not to be emitted, but so that the MAM parse can be checked against a second
independent source (see ``crosscheck.py``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from opensiddur.importer.util.pages import (
    default_sourcetexts_root,
    hebcal_leyning_data_directory,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USER_AGENT = (
    "OpenSiddur-Processor/1.0 (https://github.com/opensiddur/opensiddur-processor; "
    "opensiddur@example.com)"
)

RAW_BASE = "https://raw.githubusercontent.com/hebcal"

# (repository, path within the repository, local file name).
SOURCE_FILES: tuple[tuple[str, str, str], ...] = (
    # Weekly parshiyot: aliyot 1-7 and maftir, the three weekday aliyot, and the Ashkenazi
    # ("haft") and Sephardi ("seph") haftarot.
    ("hebcal-leyning", "src/aliyot.json", "aliyot.json"),
    # Torah readings and haftarot for festivals, the four parshiyot, Rosh Hodesh and the rest.
    ("hebcal-leyning", "src/holiday-readings.json", "holiday-readings.json"),
    # Verse counts per chapter, used to resolve a reading that runs to the end of a chapter.
    ("hebcal-leyning", "src/numverses.json", "numverses.json"),
    # Modern triennial cycle: which third of each parshah is read in each year of the cycle.
    ("hebcal-triennial", "src/triennial.json", "triennial.json"),
    ("hebcal-triennial", "src/triennial-haft.json", "triennial-haft.json"),
)

LICENSE_URL = "https://github.com/hebcal/hebcal-leyning/blob/main/LICENSE"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def download(
    sourcetexts_root: Path | None = None,
    dry_run: bool = False,
) -> Path:
    """Fetch each source file and write it with a manifest. Returns the data directory."""
    data_dir = hebcal_leyning_data_directory(sourcetexts_root)
    if dry_run:
        logger.info("Would write %d files to %s", len(SOURCE_FILES), data_dir)
        return data_dir

    data_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    entries = []
    for repository, remote_path, file_name in SOURCE_FILES:
        url = f"{RAW_BASE}/{repository}/main/{remote_path}"
        logger.info("Downloading %s", url)
        response = session.get(url, timeout=60)
        response.raise_for_status()
        payload = response.content
        # Parse before writing: a 200 carrying an error page would otherwise be stored as data.
        parsed = json.loads(payload)
        (data_dir / file_name).write_bytes(payload)
        entries.append({
            "repository": repository,
            "url": url,
            "path": file_name,
            "bytes": len(payload),
            "top_level_keys": len(parsed),
            "sha256": _sha256_bytes(payload),
        })

    manifest = {
        "source": "hebcal",
        "license_url": LICENSE_URL,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "files": entries,
    }
    manifest_path = data_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    logger.info("Wrote %d files and a manifest to %s", len(entries), data_dir)
    return data_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sourcetexts-root",
        type=Path,
        default=None,
        help=f"sourcetexts checkout root (default: {default_sourcetexts_root()})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be downloaded without writing anything.",
    )
    args = parser.parse_args(argv)
    download(sourcetexts_root=args.sourcetexts_root, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
