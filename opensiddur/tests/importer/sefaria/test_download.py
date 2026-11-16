import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

from opensiddur.importer.sefaria.download import (
    BOOKS_INDEX_URL,
    BUCKET_URL,
    LAST_EXPORT_URL,
    OBJECT_METADATA_URL,
    DownloadError,
    download_work,
    locate,
    object_name,
)

from .support import WORK, make_index, make_version

HE_URL = f"{BUCKET_URL}/json/Liturgy/Test%20Siddur/Hebrew/Test%20Siddur%20Hebrew%2C%201981.json"
EN_URL = f"{BUCKET_URL}/json/Liturgy/Test%20Siddur/English/Test%20Siddur%20Hebrew%2C%201981%20%5Ben%5D.json"
SCHEMA_URL = f"{BUCKET_URL}/schemas/Test_Siddur.json"


def books():
    # books.json gives versionTitles without their colons, as Sefaria's file names do.
    return {
        "generated_at": "2026-11-02T00:00:00Z",
        "books": [
            {"title": "Test Siddur", "language": "Hebrew", "versionTitle": "Test Siddur Hebrew, 1981", "json_url": HE_URL},
            {"title": "Test Siddur", "language": "English", "versionTitle": "Test Siddur Hebrew, 1981 [en]", "json_url": EN_URL},
            {"title": "Test Siddur", "language": "Hebrew", "versionTitle": "merged", "json_url": "x"},
        ],
        "special_files": [{"path": "schemas/Test_Siddur.json", "url": SCHEMA_URL}],
    }


class FakeClient:
    """The bucket, the index and the export date, by URL; counts what was fetched."""

    def __init__(self, files: dict[str, bytes]):
        self.files = files
        self.fetched: list[str] = []

    def get_bytes(self, url: str) -> bytes:
        if url == LAST_EXPORT_URL:
            return b"2026-11-01T00:39:57\n"
        self.fetched.append(url)
        return self.files[url]

    def get_json(self, url: str):
        if url == BOOKS_INDEX_URL:
            return books()
        for file_url, data in self.files.items():
            if url == OBJECT_METADATA_URL.format(name=quote(object_name(file_url), safe="")):
                md5 = base64.b64encode(hashlib.md5(data).digest()).decode()
                return {"md5Hash": md5, "generation": "1", "updated": "2026-11-01"}
        raise KeyError(url)


def bucket(he=None, en=None) -> dict[str, bytes]:
    tree = {"Blessings": [("<b>בָּרוּךְ</b>", "Blessed")]}
    return {
        SCHEMA_URL: json.dumps(make_index(tree)).encode(),
        HE_URL: json.dumps(he or make_version(tree, "he")).encode(),
        EN_URL: json.dumps(en or make_version(tree, "en")).encode(),
    }


class TestDownload(unittest.TestCase):
    def test_locate_finds_files_by_versiontitle_without_colons(self):
        found = locate(WORK, books())
        self.assertEqual(found["he"].url, HE_URL)
        self.assertEqual(found["en"].url, EN_URL)
        self.assertEqual(found["schema"].object_name, "schemas/Test_Siddur.json")
        self.assertEqual(found["he"].object_name, "json/Liturgy/Test Siddur/Hebrew/Test Siddur Hebrew, 1981.json")

    def test_downloads_then_does_nothing_when_unchanged(self):
        client = FakeClient(bucket())
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "w"
            first = download_work(WORK, client, books(), directory)
            self.assertEqual(sorted(first.fetched), ["en.json", "he.json", "schema.json"])
            self.assertTrue(first.manifest_written)
            manifest = json.loads((directory / "manifest.json").read_text())
            self.assertEqual(manifest["last_export"], "2026-11-01T00:39:57")
            self.assertIn("Blessings", manifest["leaves"])
            self.assertEqual(manifest["files"]["he.json"]["license"], "CC-BY")
            # Stored indented, one segment to a line.
            self.assertIn('\n  "Blessings": [\n', (directory / "he.json").read_text())
            before = {p.name: p.read_bytes() for p in directory.iterdir()}
            client.fetched.clear()
            second = download_work(WORK, client, books(), directory)
            self.assertEqual(client.fetched, [])
            self.assertFalse(second.manifest_written)
            self.assertEqual({p.name: p.read_bytes() for p in directory.iterdir()}, before)

    def test_a_different_version_is_refused(self):
        tree = {"Blessings": [("א", "a")]}
        client = FakeClient(bucket(he=make_version(tree, "he", version_title="Another")))
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(DownloadError, "not 'Test Siddur"):
            download_work(WORK, client, books(), Path(tmp))

    def test_a_new_licence_is_recorded_not_refused(self):
        # update.py must be able to report it; convert.py refuses to convert it.
        tree = {"Blessings": [("א", "a")]}
        client = FakeClient(bucket(en=make_version(tree, "en", license="CC-BY-NC")))
        with tempfile.TemporaryDirectory() as tmp:
            download_work(WORK, client, books(), Path(tmp))
            manifest = json.loads((Path(tmp) / "manifest.json").read_text())
        self.assertEqual(manifest["files"]["en.json"]["license"], "CC-BY-NC")

    def test_a_corrupt_download_is_refused(self):
        files = bucket()

        class Corrupting(FakeClient):
            def get_bytes(self, url):
                data = super().get_bytes(url)
                return data + b" " if url == HE_URL else data

        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(DownloadError, "md5Hash"):
            download_work(WORK, Corrupting(files), books(), Path(tmp))

    def test_a_version_missing_from_the_index(self):
        empty = {"books": [], "special_files": []}
        with self.assertRaisesRegex(DownloadError, "found 0"):
            locate(WORK, empty)


if __name__ == "__main__":
    unittest.main()
