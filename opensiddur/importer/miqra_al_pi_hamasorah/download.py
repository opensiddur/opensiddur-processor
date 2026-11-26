"""Download Miqra al pi ha-Masorah, as MAM-parsed plus JSON from MAM-basics, into sourcetexts.

MAM-basics (https://github.com/bdenckla/MAM-basics) publishes MAM, parsed from its text at
Hebrew Wikisource, as ``MAM-parsed/plus/*.json``: one file per book of the 24, documented at
https://bdenckla.github.io/MAM-basics/MAM-parsed/plus/html/mpplus.html. MAM-basics keeps no
release of the files, so a download is pinned to a commit: ``COMMIT``, or ``--commit``, which
takes a full SHA or a branch or tag that GitHub's API resolves to one.

This writes ``<sourcetexts-root>/miqra_al_pi_hamasorah/``:

- ``plus/*.json``: the files, byte for byte as at the commit;
- ``LICENSE.md``: MAM's licence and attribution statement (``MAM-parsed/LICENSE.md``);
- ``manifest.json``: the repository, the commit, each file's URL, size and SHA-256, and the
  time of the download.

Each file is checked against the Git blob SHA that GitHub lists for it at the commit. Every
file is fetched and checked before any is written, and the manifest is written last, so a
download that fails leaves the previous one as it was. A run whose commit and files match the
manifest fetches nothing and writes nothing. Files are compared byte for byte, so the
sourcetexts commit that adds the download also adds the ``.gitattributes`` line
``sources/miqra_al_pi_hamasorah/** -text``, which keeps Git for Windows from turning their line
ends into CRLF. A file under ``plus/`` that the previous manifest recorded and the commit no
longer has is deleted.

The first download replaces ``manifest.json``, which described the retired Google Sheet export
in ``sheets/``. The importer no longer reads ``sheets/``; the download leaves it for the
maintainer to remove in the sourcetexts commit that adds the download.

Run::

    uv run python -m opensiddur.importer.miqra_al_pi_hamasorah.download [--commit REF]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from opensiddur.importer.util.pages import (
    default_sourcetexts_root,
    miqra_al_pi_hamasorah_data_directory,
    miqra_al_pi_hamasorah_plus_directory,
)

logger = logging.getLogger(__name__)

REPOSITORY = "bdenckla/MAM-basics"
#: The MAM-basics commit the import is pinned to. Move it forward to take MAM's later edits.
#: Then run the download and ``convert --check``, which reads and converts the new files and
#: writes nothing.
COMMIT = "632ff4b65aac33436e8fb96281b798d774c5e092"
PLUS_PATH = "MAM-parsed/plus"
LICENSE_PATH = "MAM-parsed/LICENSE.md"
DOCUMENTATION_URL = "https://bdenckla.github.io/MAM-basics/MAM-parsed/plus/html/mpplus.html"

API_URL = "https://api.github.com"
RAW_URL = "https://raw.githubusercontent.com"
USER_AGENT = "OpenSiddur-Processor/1.0 (https://github.com/opensiddur/opensiddur-processor)"
#: The longest wait, in seconds, that the downloader sleeps through when GitHub asks it to
#: wait; a longer one fails the download at once, saying when to try again.
MAX_WAIT = 60.0

MANIFEST_NAME = "manifest.json"
LICENSE_NAME = "LICENSE.md"

_FULL_SHA = re.compile(r"[0-9a-f]{40}")


class DownloadError(RuntimeError):
    pass


def _rate_limited(response: requests.Response) -> bool:
    """Whether the response is GitHub's rate limit.

    GitHub marks its secondary rate limit on a 403 or 429 with ``Retry-After``, and its
    primary one with ``X-RateLimit-Remaining: 0``.
    """
    headers = response.headers
    return bool(headers.get("Retry-After")) or headers.get("X-RateLimit-Remaining") == "0"


def _retry_delay(response: requests.Response, attempt: int, now: float) -> float:
    """Seconds to wait before retrying a 403, 429 or 503, as GitHub asks.

    ``Retry-After`` when the response has one; else, when it says the rate limit is used up
    (``X-RateLimit-Remaining: 0``), until ``X-RateLimit-Reset``, a Unix time; else 1, 2, 4...
    A wait longer than the client's ``max_wait`` (:data:`MAX_WAIT`) is not taken: the download
    fails at once.
    """
    headers = response.headers
    try:
        if headers.get("Retry-After"):
            return max(0.0, float(headers["Retry-After"]))
        if headers.get("X-RateLimit-Remaining") == "0" and headers.get("X-RateLimit-Reset"):
            return max(0.0, float(headers["X-RateLimit-Reset"]) - now)
    except ValueError:
        logger.debug("Ignoring an uninterpretable retry header in %r", dict(headers))
    return float(2 ** attempt)


def _rate_limit_reset(response: requests.Response) -> str:
    reset = response.headers.get("X-RateLimit-Reset", "")
    if not reset.isdigit():
        return ""
    return f" until {datetime.fromtimestamp(int(reset), timezone.utc).isoformat()}"


class Client:
    """HTTP for GitHub's API and raw files, with timeouts and a few retries.

    A 429, a 5xx and a 403 that is GitHub's rate limit (:func:`_rate_limited`) are retried,
    after the wait a 403, 429 or 503 asks for (:func:`_retry_delay`); any other 403 fails at
    once. That wait is taken when it is at most ``max_wait`` seconds (:data:`MAX_WAIT`); a
    longer one fails the download at once, saying how long GitHub asked it to wait and, from
    ``X-RateLimit-Reset``, until when.
    """

    def __init__(self, session: requests.Session | None = None, *, retries: int = 4,
                 timeout: float = 60.0, max_wait: float = MAX_WAIT,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.time) -> None:
        self.session = session or requests.Session()
        # Assigned, not set by default: a requests session already has a User-Agent of its own.
        self.session.headers["User-Agent"] = USER_AGENT
        self.retries = retries
        self.timeout = timeout
        self.max_wait = max_wait
        self.sleep = sleep
        self.clock = clock

    def get_bytes(self, url: str, *, accept: str | None = None) -> bytes:
        headers = {"Accept": accept} if accept else {}
        problem = ""
        for attempt in range(self.retries):
            delay = float(2 ** attempt)
            try:
                response = self.session.get(url, headers=headers, timeout=self.timeout)
                status = response.status_code
                if status == 200:
                    return response.content
                if status == 403 and not _rate_limited(response):
                    raise DownloadError(f"GET {url}: HTTP 403")
                if status not in (403, 429, 500, 502, 503, 504):
                    raise DownloadError(f"GET {url}: HTTP {status}")
                problem = f"HTTP {status}"
                if status in (403, 429, 503):
                    delay = _retry_delay(response, attempt, self.clock())
                    if delay > self.max_wait:
                        who = "GitHub" if status == 503 else "GitHub's rate limit"
                        raise DownloadError(
                            f"GET {url}: HTTP {status}: {who} asks for a wait of {delay:.0f} s"
                            f"{_rate_limit_reset(response)}, more than the {self.max_wait:.0f} s "
                            "the downloader waits; try again then")
            except requests.RequestException as exc:
                problem = str(exc) or type(exc).__name__
            # No wait after the last attempt: nothing follows it.
            if attempt + 1 < self.retries:
                logger.warning("GET %s: %s; retrying in %.0f s (attempt %d of %d)",
                               url, problem, delay, attempt + 1, self.retries)
                self.sleep(delay)
        raise DownloadError(f"GET {url} failed after {self.retries} attempts: {problem}")

    def get_json(self, url: str) -> Any:
        return json.loads(self.get_bytes(url, accept="application/vnd.github+json"))


def resolve_commit(client: Client, ref: str) -> str:
    """The full SHA of ``ref``: a full SHA as it is; a branch, tag or short SHA through the API."""
    if _FULL_SHA.fullmatch(ref):
        return ref
    url = f"{API_URL}/repos/{REPOSITORY}/commits/{quote(ref, safe='')}"
    sha = client.get_bytes(url, accept="application/vnd.github.sha").decode("ascii").strip()
    if not _FULL_SHA.fullmatch(sha):
        raise DownloadError(f"{url} did not give a commit SHA: {sha!r}")
    return sha


def raw_url(commit: str, path: str) -> str:
    return f"{RAW_URL}/{REPOSITORY}/{commit}/{quote(path)}"


def git_blob_sha(data: bytes) -> str:
    """The SHA-1 Git names a file's content by, which GitHub's contents API lists."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _listing(client: Client, commit: str, directory: str) -> dict[str, dict[str, Any]]:
    """The files of a repository directory at a commit, by name: each with size and blob SHA."""
    entries = client.get_json(f"{API_URL}/repos/{REPOSITORY}/contents/{quote(directory)}?ref={commit}")
    if not isinstance(entries, list):
        raise DownloadError(f"{directory} at {commit} is not a directory")
    return {entry["name"]: entry for entry in entries if entry.get("type") == "file"}


def _fetch(client: Client, commit: str, path: str, listed: dict[str, Any]) -> bytes:
    """A file at the commit, checked against the size and blob SHA the API lists for it."""
    data = client.get_bytes(raw_url(commit, path))
    if len(data) != listed["size"] or git_blob_sha(data) != listed["sha"]:
        raise DownloadError(f"{path} at {commit} does not match its listing")
    return data


def file_sha256(data: bytes) -> str:
    """The SHA-256 the manifest records for a file: that of its bytes as downloaded.

    The checks compare it byte for byte, so the sourcetexts commit that adds the download
    keeps Git from changing line ends (``sources/miqra_al_pi_hamasorah/** -text`` in its
    ``.gitattributes``).
    """
    return hashlib.sha256(data).hexdigest()


def load_manifest(data_dir: Path) -> dict[str, Any]:
    path = data_dir / MANIFEST_NAME
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _recorded_files(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """The files a manifest written by this downloader records; none for any other manifest."""
    if manifest.get("repository") != REPOSITORY:
        return []
    return manifest.get("files", [])


def _intact(data_dir: Path, manifest: dict[str, Any]) -> bool:
    files = _recorded_files(manifest)
    return bool(files) and all(
        (data_dir / entry["path"]).is_file()
        and file_sha256((data_dir / entry["path"]).read_bytes()) == entry["sha256"]
        for entry in files
    )


def _write_bytes_if_changed(path: Path, data: bytes) -> bool:
    if path.is_file() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


@dataclass
class DownloadResult:
    commit: str
    fetched: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    manifest_written: bool = False


def download(
    sourcetexts_root: Path | None = None,
    *,
    commit: str = COMMIT,
    client: Client | None = None,
    dry_run: bool = False,
) -> DownloadResult:
    """Bring ``<sourcetexts-root>/miqra_al_pi_hamasorah`` up to MAM-parsed plus at ``commit``."""
    data_dir = miqra_al_pi_hamasorah_data_directory(sourcetexts_root)
    plus_dir = miqra_al_pi_hamasorah_plus_directory(sourcetexts_root)
    if dry_run:
        logger.info("Would download %s and %s of %s at %s into %s",
                    PLUS_PATH, LICENSE_PATH, REPOSITORY, commit, data_dir)
        return DownloadResult(commit)

    client = client or Client()
    sha = resolve_commit(client, commit)
    manifest = load_manifest(data_dir)
    if (data_dir / "sheets").exists():
        logger.warning("%s holds the retired Google Sheet export, which the importer no longer "
                       "reads and whose manifest.json the first download replaces; it is left "
                       "for the maintainer to remove in the sourcetexts commit that adds the "
                       "download", data_dir / "sheets")
    if manifest.get("commit") == sha and _intact(data_dir, manifest):
        logger.info("MAM-parsed plus at %s is already downloaded", sha)
        return DownloadResult(sha)

    result = DownloadResult(sha)
    plus_listing = {
        name: entry for name, entry in _listing(client, sha, PLUS_PATH).items()
        if name.endswith(".json")
    }
    if not plus_listing:
        raise DownloadError(f"no JSON files in {PLUS_PATH} at {sha}")
    licence_directory, licence_name = LICENSE_PATH.rsplit("/", 1)
    licence_listed = _listing(client, sha, licence_directory).get(licence_name)
    if licence_listed is None:
        raise DownloadError(f"no {LICENSE_PATH} at {sha}")

    downloads = [(f"{PLUS_PATH}/{name}", f"{plus_dir.name}/{name}", entry)
                 for name, entry in sorted(plus_listing.items())]
    downloads.append((LICENSE_PATH, LICENSE_NAME, licence_listed))
    contents: list[tuple[str, bytes]] = []
    entries = []
    for remote_path, local_path, listed in downloads:
        logger.info("Downloading %s", remote_path)
        data = _fetch(client, sha, remote_path, listed)
        contents.append((local_path, data))
        entries.append({
            "path": local_path,
            "url": raw_url(sha, remote_path),
            "bytes": len(data),
            "sha256": file_sha256(data),
        })

    # Every file has been fetched and checked before any is written, and the manifest is
    # written last: a download that fails leaves the previous one and its manifest as they were.
    for local_path, data in contents:
        if _write_bytes_if_changed(data_dir / local_path, data):
            result.fetched.append(local_path)

    # Only the files an earlier download of this source recorded are deleted.
    kept = {entry["path"] for entry in entries}
    for entry in _recorded_files(manifest):
        stale = data_dir / entry["path"]
        if entry["path"] not in kept and stale.is_file():
            logger.info("Deleting %s, which MAM-parsed plus at %s does not have", stale, sha)
            stale.unlink()
            result.deleted.append(entry["path"])

    new_manifest = {
        "source": "MAM-parsed plus",
        "repository": REPOSITORY,
        "commit": sha,
        "plus_path": PLUS_PATH,
        "license_path": LICENSE_PATH,
        "documentation": DOCUMENTATION_URL,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "files": entries,
    }
    result.manifest_written = _write_bytes_if_changed(
        data_dir / MANIFEST_NAME,
        (json.dumps(new_manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    return result


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download Miqra al pi ha-Masorah, as MAM-parsed plus JSON from MAM-basics, into "
            "<sourcetexts-root>/miqra_al_pi_hamasorah."
        )
    )
    parser.add_argument(
        "--sourcetexts-root",
        type=Path,
        default=default_sourcetexts_root(),
        help=(
            "Root of the sourcetexts tree; output is written under "
            "<root>/miqra_al_pi_hamasorah (default: <repo>/sourcetexts/sources)."
        ),
    )
    parser.add_argument(
        "--commit",
        default=COMMIT,
        help=f"MAM-basics commit, branch or tag to download (default: {COMMIT}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without downloading or writing files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    result = download(args.sourcetexts_root, commit=args.commit, dry_run=args.dry_run)
    if not args.dry_run:
        print(f"{REPOSITORY} at {result.commit}: fetched {result.fetched or 'nothing'}; "
              f"deleted {result.deleted or 'nothing'}; "
              f"manifest {'written' if result.manifest_written else 'unchanged'}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
