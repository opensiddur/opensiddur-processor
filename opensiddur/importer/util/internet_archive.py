"""Reading an Internet Archive item: its metadata, its files, and its OCR.

The Archive is the second source of scanned books this project reads, after
Wikisource, and the two overlap more than they look like they should: a Commons scan
indexed by a Wikisource ``Index:`` page is frequently the very same scan the Archive
holds, digitised once and copied. When that is so — compare the file names, and the
sha1 in :func:`fetch_metadata` — the Archive's OCR can be aligned to the Wikisource
transcription leaf by leaf for nothing, and each fills the other's gaps.

This module speaks to archive.org and parses its derivative formats. It knows nothing
about any particular book or about where files belong on disk; that is the importer's
job. It deliberately reuses the HTTP etiquette already written for Wikisource rather
than growing a second, subtly different implementation of pacing and backoff — see
:ref:`the policy note <ia-bot-policy>` in :func:`build_session`.

The one piece of arithmetic worth stating once, because getting it wrong is silent:
the Archive numbers *leaves* from zero, while a ``ProofreadPage`` wiki numbers *pages*
from one. Nothing here converts between them — an importer that pairs the two sources
owns that offset and should keep it in exactly one place.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import requests
from pydantic import BaseModel, Field

from opensiddur.importer.util.wikisource import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    USER_AGENT_TEMPLATE,
    RateLimiter,
    # Same package, and the Archive asks for precisely the behaviour this already
    # implements: honour Retry-After, else exponential backoff. Sharing it keeps the
    # two clients from drifting into two different ideas of politeness.
    _backoff_seconds,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://archive.org"

# The Archive publishes no numeric rate limit; its own worked example is four
# concurrent requests paced a second apart. One request at a time, slightly slower,
# is well inside that and matches what we already do against Wikimedia.
DEFAULT_MIN_INTERVAL = 1.3

_HTTP_BACKOFF_BASE = 2.0

# archive.org/developers/bots.html asks that AI-agent clients name the model driving
# them, over and above the tool and contact address every automated client must send.
# Unset for a human-invoked run, which then sends the plain project User-Agent.
AGENT_MODEL_ENV_VAR = "OPENSIDDUR_AGENT_MODEL"

# Streaming chunk for large files; the scanned PDFs run to hundreds of megabytes and
# must never be assembled in memory.
_CHUNK_SIZE = 1 << 20


class InternetArchiveError(RuntimeError):
    """archive.org reported an error, or returned something we cannot trust."""


class ItemFile(BaseModel):
    """One file in an item, as the metadata endpoint describes it."""

    name: str = Field(description="File name within the item")
    format: str | None = Field(default=None, description="Archive's format label")
    size: int | None = Field(default=None, description="Size in bytes, if reported")
    sha1: str | None = Field(default=None, description="Archive's own checksum")
    mtime: str | None = Field(default=None, description="Archive's last-modified stamp")


class ItemMetadata(BaseModel):
    """An item's metadata and file list, from ``/metadata/<identifier>``."""

    identifier: str = Field(description="Archive item identifier")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="The item's descriptive metadata"
    )
    files: dict[str, ItemFile] = Field(
        default_factory=dict, description="Files in the item, keyed by name"
    )

    def find_suffix(self, suffix: str) -> ItemFile | None:
        """The single file whose name ends with ``suffix``, or None.

        Derivative names are the source file's name plus a suffix, and that source
        name is whatever the uploader called it — spaces, commas and parentheses
        included. Matching on the suffix avoids reconstructing it, and avoids being
        broken by a re-derivation that renames the item's files.
        """
        matches = [f for name, f in self.files.items() if name.endswith(suffix)]
        if not matches:
            return None
        if len(matches) > 1:
            raise InternetArchiveError(
                f"{len(matches)} files in {self.identifier} end with {suffix!r}: "
                + ", ".join(sorted(f.name for f in matches))
            )
        return matches[0]


class LeafPageNumber(BaseModel):
    """The printed page number the Archive's OCR detected on one leaf."""

    leaf: int = Field(description="Zero-based leaf number")
    printed: str | None = Field(
        default=None, description="Printed page number as text, or None if undetected"
    )
    confidence: float | None = Field(
        default=None, description="Archive's confidence, 0.0-1.0, if reported"
    )


@dataclass
class DownloadedFile:
    """What one file fetch did."""

    path: Path
    sha256: str
    size: int
    skipped: bool = False


def user_agent(contact_email: str, model: str | None = None) -> str:
    """The project User-Agent, naming the model when an agent is driving.

    Built from the Wikisource template so the tool name and version stay defined in
    one place; the model, which only the Archive asks for, is appended inside the
    parenthesised comment.
    """
    base = USER_AGENT_TEMPLATE.format(contact_email=contact_email)
    if not model:
        return base
    return f"{base[:-1]}; {model})" if base.endswith(")") else f"{base} ({model})"


def resolve_agent_model(cli_value: str | None = None) -> str | None:
    """The model name to advertise, or None for a human-invoked run."""
    return (cli_value or os.environ.get(AGENT_MODEL_ENV_VAR) or "").strip() or None


def build_session(contact_email: str, model: str | None = None) -> requests.Session:
    """A session identified as archive.org's bot policy asks.

    .. _ia-bot-policy:

    https://archive.org/developers/bots.html sets no numeric rate limit. What it does
    require is a descriptive User-Agent giving tool and version (plus the model, for
    an AI agent), honouring ``429`` and ``Retry-After``, exponential backoff, delays
    between bulk requests, and preferring bulk endpoints to many small ones. The first
    is here, the next three are in :func:`http_get`, the pacing is
    :class:`RateLimiter`, and the last is a caller's decision.
    """
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent(contact_email, model),
            "Accept-Encoding": "gzip, deflate",
        }
    )
    return session


@dataclass
class Archive:
    """A paced, identified client for one archive.org host."""

    session: requests.Session
    limiter: RateLimiter
    timeout: int = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES


def connect(
    contact_email: str,
    *,
    model: str | None = None,
    min_interval: float = DEFAULT_MIN_INTERVAL,
) -> Archive:
    """Convenience constructor for a paced, correctly-identified :class:`Archive`."""
    return Archive(
        session=build_session(contact_email, model),
        limiter=RateLimiter(min_interval),
    )


def http_get(
    archive: Archive, url: str, *, stream: bool = False
) -> requests.Response:
    """GET a URL, retrying on 429 and 5xx with the shared backoff.

    Returns a response the caller must close when ``stream`` is set.
    """
    last: requests.Response | None = None
    for attempt in range(archive.max_retries):
        archive.limiter.wait()
        response = archive.session.get(url, timeout=archive.timeout, stream=stream)
        if response.status_code == 429 or response.status_code >= 500:
            delay = _backoff_seconds(response, attempt, _HTTP_BACKOFF_BASE)
            logger.warning(
                "%s returned HTTP %d; retrying in %.1fs (attempt %d/%d)",
                url,
                response.status_code,
                delay,
                attempt + 1,
                archive.max_retries,
            )
            response.close()
            last = response
            time.sleep(delay)
            continue
        if not response.ok:
            response.close()
            raise InternetArchiveError(f"HTTP {response.status_code} for {url}")
        return response

    status = last.status_code if last is not None else "unknown"
    raise InternetArchiveError(
        f"Gave up on {url} after {archive.max_retries} attempts (last status {status})"
    )


def file_url(identifier: str, name: str) -> str:
    """Download URL for one file in an item.

    The name is quoted because uploaders' file names routinely contain spaces,
    commas and parentheses.
    """
    return f"{BASE_URL}/download/{urllib.parse.quote(identifier)}/{urllib.parse.quote(name)}"


def page_image_url(identifier: str, leaf: int, size: str = "medium") -> str:
    """URL of one leaf's page image, for use as a facsimile reference.

    Takes a zero-based leaf number, as the Archive's own page URLs do.
    """
    suffix = f"_{size}" if size else ""
    return f"{BASE_URL}/download/{urllib.parse.quote(identifier)}/page/n{leaf}{suffix}.jpg"


def fetch_metadata(archive: Archive, identifier: str) -> ItemMetadata:
    """Read an item's metadata and file list in a single request.

    One call describes every file, with the Archive's own sha1 and mtime for each, so
    nothing here needs a per-file HEAD to decide what to fetch.
    """
    url = f"{BASE_URL}/metadata/{urllib.parse.quote(identifier)}"
    logger.info("Reading item metadata for %s", identifier)
    response = http_get(archive, url)
    try:
        payload = response.json()
    except ValueError as exc:
        raise InternetArchiveError(f"{url} did not return JSON: {exc}") from exc
    finally:
        response.close()

    if not payload or "files" not in payload:
        # The endpoint answers 200 with "{}" for an identifier that does not exist.
        raise InternetArchiveError(
            f"No such item, or no files listed, for identifier {identifier!r}"
        )

    files: dict[str, ItemFile] = {}
    for entry in payload.get("files") or []:
        name = entry.get("name")
        if not name:
            continue
        size = entry.get("size")
        files[name] = ItemFile(
            name=name,
            format=entry.get("format"),
            size=int(size) if size is not None and str(size).isdigit() else None,
            sha1=entry.get("sha1"),
            mtime=entry.get("mtime"),
        )

    return ItemMetadata(
        identifier=identifier,
        metadata=payload.get("metadata") or {},
        files=files,
    )


def sha256_file(path: Path) -> str:
    """Checksum of a file, read in chunks so size does not matter."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(
    archive: Archive,
    identifier: str,
    item_file: ItemFile,
    destination: Path,
    *,
    force: bool = False,
) -> DownloadedFile:
    """Fetch one file of an item, skipping it when the copy on disk already matches.

    The skip test is the Archive's own sha1 against the file on disk, which is the
    only check that distinguishes "unchanged" from "we happen to have a file of the
    right name". Streams to a temporary sibling and renames, so an interrupted fetch
    cannot leave a truncated file looking complete.
    """
    if destination.is_file() and not force and item_file.sha1:
        if _sha1_file(destination) == item_file.sha1:
            logger.debug("%s is unchanged; skipping", item_file.name)
            return DownloadedFile(
                path=destination,
                sha256=sha256_file(destination),
                size=destination.stat().st_size,
                skipped=True,
            )

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    url = file_url(identifier, item_file.name)

    logger.info(
        "Downloading %s%s",
        item_file.name,
        f" ({item_file.size / 1e6:.1f} MB)" if item_file.size else "",
    )
    response = http_get(archive, url, stream=True)
    try:
        with open(temporary, "wb") as f:
            for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
    finally:
        response.close()

    size = temporary.stat().st_size
    if item_file.size is not None and size != item_file.size:
        temporary.unlink(missing_ok=True)
        raise InternetArchiveError(
            f"{item_file.name} is {size} bytes but the item says {item_file.size}"
        )

    temporary.replace(destination)
    return DownloadedFile(path=destination, sha256=sha256_file(destination), size=size)


def write_if_changed(path: Path, text: str) -> bool:
    """Write ``text`` only if it differs from what is there. Returns whether it did.

    These files are committed to a repository, so rewriting one with identical
    content is not free: it churns the working tree and turns a run that fetched
    nothing into a diff.

    The bytes are compared, not the decoded text, because decoding turns CRLF into LF: a
    file a Windows checkout gave CRLF endings would compare equal and never be rewritten,
    and its SHA-256 would never match the LF text the manifest records.
    """
    if path.is_file() and path.read_bytes() == text.encode("utf-8"):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def read_maybe_gzip(path: Path) -> bytes:
    """Read a file, decompressing it when it is gzipped.

    Decided by content, not by name: these derivatives are stored gzipped but are
    served with content-encoding that some clients undo, so the suffix is not a
    reliable guide to what actually landed on disk.
    """
    with open(path, "rb") as f:
        head = f.read(2)
    if head == b"\x1f\x8b":
        with gzip.open(path, "rb") as gz:
            return gz.read()
    return path.read_bytes()


def load_pageindex(path: Path) -> list[tuple[int, int, int, int]]:
    """Read a ``_hocr_pageindex.json`` file: one span per leaf.

    Each entry is ``(searchtext_start, searchtext_end, hocr_start, hocr_end)``. All
    four are **byte** offsets — the first pair into the plain search text, the second
    into the much larger hOCR. Only the first pair is used here.
    """
    try:
        payload = json.loads(read_maybe_gzip(path).decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise InternetArchiveError(f"Cannot read page index {path}: {exc}") from exc

    if not isinstance(payload, list) or not payload:
        raise InternetArchiveError(f"Page index {path} is not a non-empty list")

    index: list[tuple[int, int, int, int]] = []
    for position, entry in enumerate(payload):
        if not isinstance(entry, Sequence) or len(entry) < 4:
            raise InternetArchiveError(
                f"Page index {path} entry {position} is not a 4-element span: {entry!r}"
            )
        index.append(tuple(int(v) for v in entry[:4]))  # type: ignore[arg-type]
    return index


def slice_searchtext(
    buf: bytes, index: Iterable[tuple[int, int, int, int]]
) -> list[bytes]:
    """Cut the whole-book search text into one chunk per leaf.

    ``buf`` must be the decompressed search text **as bytes**. The page index holds
    byte offsets, and this file mixes ASCII with multi-byte UTF-8 — the Hebrew that
    OCR misread as Latin is not the only non-ASCII in it — so slicing a decoded
    ``str`` by these offsets would shift every leaf after the first multi-byte
    character. Decode each chunk afterwards, never before.
    """
    spans = list(index)
    previous_end = 0
    for position, (start, end, _, _) in enumerate(spans):
        if start < previous_end:
            raise InternetArchiveError(
                f"Page index is not monotonic at leaf {position}: "
                f"span starts at {start} but the previous span ended at {previous_end}"
            )
        if end < start:
            raise InternetArchiveError(
                f"Page index span for leaf {position} ends ({end}) before it starts ({start})"
            )
        previous_end = end

    if spans and spans[-1][1] > len(buf):
        raise InternetArchiveError(
            f"Page index runs to byte {spans[-1][1]} but the search text is only "
            f"{len(buf)} bytes; the two derivatives do not belong to the same scan"
        )

    return [buf[start:end] for start, end, _, _ in spans]


def load_page_numbers(path: Path) -> dict[int, LeafPageNumber]:
    """Read a ``_page_numbers.json`` file, keyed by zero-based leaf number.

    The Archive reports the printed page number it detected on each leaf. It is a
    guess from OCR: usually right, occasionally absent, and worth cross-checking
    against any human-entered number a transcription provides.
    """
    try:
        payload = json.loads(read_maybe_gzip(path).decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise InternetArchiveError(f"Cannot read page numbers {path}: {exc}") from exc

    pages = payload.get("pages") if isinstance(payload, dict) else None
    if not isinstance(pages, list):
        raise InternetArchiveError(f"Page numbers {path} has no 'pages' list")

    numbers: dict[int, LeafPageNumber] = {}
    for entry in pages:
        leaf = entry.get("leafNum")
        if leaf is None:
            continue
        printed = (entry.get("pageNumber") or "").strip() or None
        confidence = entry.get("confidence")
        numbers[int(leaf)] = LeafPageNumber(
            leaf=int(leaf),
            printed=printed,
            # Reported 0-100; normalised here so callers never have to wonder.
            confidence=float(confidence) / 100.0 if confidence is not None else None,
        )
    return numbers


def leaf_count_from_scandata(path: Path) -> int:
    """Count the leaves an item's ``_scandata.xml`` describes.

    This is the independent check that a page index belongs to the scan it is being
    used against: two derivatives that disagree about how many leaves the book has
    cannot both be describing it.
    """
    try:
        root = ET.fromstring(read_maybe_gzip(path).decode("utf-8"))
    except (OSError, ET.ParseError) as exc:
        raise InternetArchiveError(f"Cannot parse scandata {path}: {exc}") from exc

    # The file is namespaced in some derivations and not in others, and nests
    # <page> under <pageData>; match on the local name and the leafNum attribute
    # rather than on a path that only holds for one of the two shapes.
    count = sum(
        1
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1] == "page" and "leafNum" in element.attrib
    )
    if not count:
        raise InternetArchiveError(f"Scandata {path} describes no leaves")
    return count
