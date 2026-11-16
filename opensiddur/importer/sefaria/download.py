"""Download a Sefaria work's schema and its Hebrew and English versions into ``sourcetexts``.

Sefaria publishes its library monthly to the public bucket ``gs://sefaria-export``, readable
over plain HTTPS at ``https://storage.googleapis.com/sefaria-export/``. The Sefaria-Export
repository on GitHub now holds only ``books.json``, the index of the bucket's files; the text
itself is no longer in git. The bucket keeps no old copies -- each export overwrites its files
in place -- so the copy committed to ``sourcetexts`` is the only pin there is.

For each work in ``works.yaml`` this writes ``sourcetexts/sources/sefaria/<work>/``:

- ``schema.json``: the work's index record (``schemas/<Title>.json``);
- ``he.json``, ``en.json``: the two versions, never ``merged.json``, which mixes in every
  other version of the text;
- ``manifest.json``: each file's URL, the bucket's ``md5Hash`` and ``generation`` for it, its
  sha256 as stored, the export date, and a hash of every leaf (``source.leaf_hashes``), which
  is what ``update`` compares;
- ``README.md``.

File URLs are taken from ``books.json``: Sefaria's file names drop the colon a versionTitle
may contain, so they are never built by hand. The JSON is stored re-indented, one segment to
a line, so that a later export's changes read as a diff.

A file whose ``md5Hash`` is the one recorded is not fetched again, and a run that fetches
nothing writes nothing: the manifest, and its export date, change only with the text. Each
version's licence is recorded; ``convert`` refuses one that is no longer ``CC-BY`` until it
has been decided, and ``update`` reports it.

Run::

    uv run python -m opensiddur.importer.sefaria.download [--work KEY ...]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import requests

from opensiddur.importer.sefaria.source import leaf_hashes, load_work_source
from opensiddur.importer.sefaria.works import Work, select_works
from opensiddur.importer.util.internet_archive import write_if_changed

logger = logging.getLogger(__name__)

BOOKS_INDEX_URL = "https://raw.githubusercontent.com/Sefaria/Sefaria-Export/master/books.json"
BUCKET = "sefaria-export"
BUCKET_URL = f"https://storage.googleapis.com/{BUCKET}"
OBJECT_METADATA_URL = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o/{{name}}"
LAST_EXPORT_URL = f"{BUCKET_URL}/last_export.txt"
USER_AGENT = "OpenSiddur-Processor/1.0 (https://github.com/opensiddur/opensiddur-processor)"

MANIFEST_NAME = "manifest.json"
FILE_NAMES = {"schema": "schema.json", "he": "he.json", "en": "en.json"}


class DownloadError(RuntimeError):
    pass


class Client:
    """HTTP for the bucket and the index, with timeouts and a few retries."""

    def __init__(self, session: requests.Session | None = None, *, retries: int = 4,
                 timeout: float = 60.0, sleep: Callable[[float], None] = time.sleep) -> None:
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", USER_AGENT)
        self.retries = retries
        self.timeout = timeout
        self.sleep = sleep

    def get_bytes(self, url: str) -> bytes:
        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code == 200:
                    return response.content
                if response.status_code not in (429, 500, 502, 503, 504):
                    raise DownloadError(f"GET {url}: HTTP {response.status_code}")
                last = DownloadError(f"GET {url}: HTTP {response.status_code}")
            except requests.RequestException as exc:
                last = exc
            self.sleep(2 ** attempt)
        raise DownloadError(f"GET {url} failed after {self.retries} attempts: {last}")

    def get_json(self, url: str) -> Any:
        return json.loads(self.get_bytes(url))


@dataclass(frozen=True)
class RemoteFile:
    role: str  # "schema", "he" or "en"
    url: str
    object_name: str
    version_title: str | None = None


def _normalized_version_title(title: str) -> str:
    """A versionTitle as ``books.json`` gives it: without the colon, whitespace collapsed."""
    return " ".join(title.replace(":", "").split())


def object_name(url: str) -> str:
    """The bucket object a public URL names."""
    prefix = BUCKET_URL + "/"
    if not url.startswith(prefix):
        raise DownloadError(f"{url} is not in the {BUCKET} bucket")
    return unquote(url[len(prefix):])


def locate(work: Work, books: dict[str, Any]) -> dict[str, RemoteFile]:
    """The schema and version files of ``work``, from the bucket index ``books.json``."""
    found: dict[str, RemoteFile] = {}
    for lang, version_title in work.versions.items():
        wanted = _normalized_version_title(version_title)
        matches = [
            entry for entry in books.get("books", [])
            if entry.get("title") == work.title
            and _normalized_version_title(entry.get("versionTitle", "")) == wanted
        ]
        if len(matches) != 1:
            raise DownloadError(
                f"{work.key}: expected one {lang} version titled {version_title!r} in books.json, "
                f"found {len(matches)}")
        url = matches[0]["json_url"]
        found[lang] = RemoteFile(lang, url, object_name(url), version_title)
    schema_path = f"schemas/{work.schema_file_title}.json"
    schema = [f for f in books.get("special_files", []) if f.get("path") == schema_path]
    if len(schema) != 1:
        raise DownloadError(f"{work.key}: {schema_path} is not in books.json")
    found["schema"] = RemoteFile("schema", schema[0]["url"], object_name(schema[0]["url"]))
    return found


def md5_base64(data: bytes) -> str:
    """An MD5 digest as the bucket gives it (``md5Hash``)."""
    return base64.b64encode(hashlib.md5(data).digest()).decode("ascii")


def stored_json(data: bytes) -> str:
    """How a downloaded JSON file is stored: indented, so that each segment is a line."""
    return json.dumps(json.loads(data), ensure_ascii=False, indent=1) + "\n"


def _check_version(work: Work, lang: str, data: dict[str, Any]) -> None:
    expected = work.versions[lang]
    if data.get("versionTitle") != expected:
        raise DownloadError(
            f"{work.key}: the {lang} file is version {data.get('versionTitle')!r}, not {expected!r}")


def load_manifest(directory: Path) -> dict[str, Any]:
    path = directory / MANIFEST_NAME
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class DownloadResult:
    work: str
    fetched: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    manifest_written: bool = False


def readme(work: Work) -> str:
    return f"""# {work.title} (Sefaria)

Source: the Sefaria export bucket, `gs://{BUCKET}` ({BUCKET_URL}/), located through
`books.json` in https://github.com/Sefaria/Sefaria-Export.

Issue: https://github.com/opensiddur/opensiddur-processor/issues/307

- `schema.json`: the work's Sefaria index record
- `he.json`: the Hebrew version "{work.versions['he']}"
- `en.json`: the English version "{work.versions['en']}"
- `manifest.json`: URLs, the bucket's md5Hash and generation, sha256 as stored, the export
  date, and a hash of every leaf

The versions are published by Sefaria under CC-BY (Creative Commons Attribution 3.0,
{work.licence}). Credit: {work.publisher}{', ' + work.place if work.place else ''}, {work.date};
translated by {work.translator}. Digitized by Sefaria (https://www.sefaria.org).

These files are regenerated by `uv run python -m opensiddur.importer.sefaria.download`.
Edit nothing here by hand: the JSON is Sefaria's, re-indented.
"""


def download_work(work: Work, client: Client, books: dict[str, Any], directory: Path, *,
                  force: bool = False) -> DownloadResult:
    """Bring ``directory`` up to the bucket's copy of ``work``."""
    result = DownloadResult(work.key)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(directory)
    recorded = manifest.get("files", {})
    remote = locate(work, books)

    entries: dict[str, dict[str, Any]] = {}
    contents: dict[str, str] = {}
    for role in ("schema", "he", "en"):
        file = remote[role]
        name = FILE_NAMES[role]
        meta = client.get_json(OBJECT_METADATA_URL.format(name=quote(file.object_name, safe="")))
        previous = recorded.get(name, {})
        path = directory / name
        if (not force and previous.get("md5Hash") == meta["md5Hash"] and path.exists()
                and hashlib.sha256(path.read_bytes()).hexdigest() == previous.get("sha256")):
            entries[name] = dict(previous)
            result.unchanged.append(name)
            continue
        data = client.get_bytes(file.url)
        if md5_base64(data) != meta["md5Hash"]:
            raise DownloadError(f"{file.url}: the download does not match the bucket's md5Hash")
        if role != "schema":
            _check_version(work, role, json.loads(data))
        contents[name] = stored_json(data)
        entry: dict[str, Any] = {
            "url": file.url,
            "md5Hash": meta["md5Hash"],
            "generation": meta.get("generation"),
            "updated": meta.get("updated"),
            "sha256": hashlib.sha256(contents[name].encode("utf-8")).hexdigest(),
            "bytes": len(contents[name].encode("utf-8")),
        }
        if file.version_title:
            entry["version_title"] = file.version_title
            entry["license"] = json.loads(data).get("license")
        entries[name] = entry
        result.fetched.append(name)

    write_if_changed(directory / "README.md", readme(work))
    if not contents and manifest:
        return result
    for name, text in contents.items():
        write_if_changed(directory / name, text)
    source = load_work_source(directory)
    new_manifest = {
        "source": "Sefaria-Export",
        "work": work.key,
        "title": work.title,
        "bucket": BUCKET_URL,
        "books_index": BOOKS_INDEX_URL,
        "books_generated_at": books.get("generated_at"),
        "last_export": client.get_bytes(LAST_EXPORT_URL).decode("utf-8").strip(),
        "files": entries,
        "leaves": leaf_hashes(source),
    }
    result.manifest_written = write_if_changed(
        directory / MANIFEST_NAME, json.dumps(new_manifest, ensure_ascii=False, indent=1) + "\n")
    return result


def download(works: list[Work], client: Client, sourcetexts_root: Path | None = None, *,
             force: bool = False) -> list[DownloadResult]:
    books = client.get_json(BOOKS_INDEX_URL)
    return [download_work(work, client, books, work.data_directory(sourcetexts_root), force=force)
            for work in works]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--work", action="append", help="a key from works.yaml; repeatable. Default: all")
    parser.add_argument("--sourcetexts-root", type=Path, default=None)
    parser.add_argument("--force", action="store_true", help="fetch every file even when unchanged")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for result in download(select_works(args.work), Client(), args.sourcetexts_root, force=args.force):
        print(f"{result.work}: fetched {result.fetched or 'nothing'}; "
              f"unchanged {result.unchanged or 'nothing'}; "
              f"manifest {'written' if result.manifest_written else 'unchanged'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
