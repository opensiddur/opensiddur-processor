import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from requests.structures import CaseInsensitiveDict

from opensiddur.importer.miqra_al_pi_hamasorah import download
from opensiddur.importer.util.pages import (
    miqra_al_pi_hamasorah_data_directory,
    miqra_al_pi_hamasorah_plus_directory,
)

COMMIT = "0123456789abcdef0123456789abcdef01234567"
GENESIS = b'{"header": {}, "book39s": []}\n'
SONG = b'{"header": {}, "book39s": [1]}\n'
LICENSE = b"Attribution: Hebrew Wikisource\n"


class FakeClient:
    """GitHub as the downloader sees it: two directory listings and the raw files."""

    def __init__(self, files: dict[str, bytes], commit: str = COMMIT) -> None:
        self.files = files
        self.commit = commit
        self.requests: list[str] = []

    def _entry(self, path: str) -> dict:
        data = self.files[path]
        return {"name": path.rsplit("/", 1)[1], "type": "file", "size": len(data),
                "sha": download.git_blob_sha(data)}

    def get_json(self, url: str):
        self.requests.append(url)
        directory = url.split("/contents/", 1)[1].split("?", 1)[0]
        prefix = directory.replace("%20", " ") + "/"
        entries = [self._entry(p) for p in self.files if p.startswith(prefix) and "/" not in p[len(prefix):]]
        return entries + [{"name": "provenance.md", "type": "file", "size": 1, "sha": "x"}]

    def get_bytes(self, url: str, *, accept: str | None = None) -> bytes:
        self.requests.append(url)
        if accept == "application/vnd.github.sha":
            return self.commit.encode("ascii")
        path = url.split(f"/{self.commit}/", 1)[1].replace("%20", " ")
        return self.files[path]


def _files() -> dict[str, bytes]:
    return {
        "MAM-parsed/plus/A1-Genesis.json": GENESIS,
        "MAM-parsed/plus/E1-Song of Songs.json": SONG,
        "MAM-parsed/LICENSE.md": LICENSE,
    }


class FakeResponse:
    def __init__(self, status_code: int, headers: dict[str, str] | None = None,
                 content: bytes = b"") -> None:
        self.status_code = status_code
        # As requests gives them: GitHub sends the names in lower case.
        self.headers = CaseInsensitiveDict(headers or {})
        self.content = content


class FakeSession:
    """A requests session that answers each GET with the next of the given responses."""

    def __init__(self, *responses: FakeResponse) -> None:
        self.responses = list(responses)
        self.headers: dict[str, str] = {}
        self.urls: list[str] = []

    def get(self, url: str, headers=None, timeout=None) -> FakeResponse:
        self.urls.append(url)
        return self.responses.pop(0)


class TestDownloadMiqra(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.sourcetexts_root = Path(self.tmp.name)
        self.data_dir = miqra_al_pi_hamasorah_data_directory(self.sourcetexts_root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _manifest(self) -> dict:
        return json.loads((self.data_dir / "manifest.json").read_text(encoding="utf-8"))

    def test_download_writes_files_and_manifest(self) -> None:
        client = FakeClient(_files())
        result = download.download(self.sourcetexts_root, commit=COMMIT, client=client)

        plus_dir = miqra_al_pi_hamasorah_plus_directory(self.sourcetexts_root)
        self.assertEqual((plus_dir / "A1-Genesis.json").read_bytes(), GENESIS)
        self.assertEqual((plus_dir / "E1-Song of Songs.json").read_bytes(), SONG)
        self.assertEqual((self.data_dir / "LICENSE.md").read_bytes(), LICENSE)
        self.assertFalse((plus_dir / "provenance.md").exists())
        self.assertTrue(result.manifest_written)

        manifest = self._manifest()
        self.assertEqual(manifest["repository"], download.REPOSITORY)
        self.assertEqual(manifest["commit"], COMMIT)
        song = next(f for f in manifest["files"] if f["path"] == "plus/E1-Song of Songs.json")
        self.assertEqual(
            song["url"],
            f"https://raw.githubusercontent.com/bdenckla/MAM-basics/{COMMIT}/MAM-parsed/plus/E1-Song%20of%20Songs.json",
        )
        self.assertEqual(song["bytes"], len(SONG))
        self.assertEqual(song["sha256"], hashlib.sha256(SONG).hexdigest())

    def test_unchanged_run_is_a_no_op(self) -> None:
        download.download(self.sourcetexts_root, commit=COMMIT, client=FakeClient(_files()))
        before = (self.data_dir / "manifest.json").read_bytes()
        client = FakeClient(_files())
        result = download.download(self.sourcetexts_root, commit=COMMIT, client=client)
        self.assertEqual(client.requests, [])
        self.assertFalse(result.manifest_written)
        self.assertEqual((self.data_dir / "manifest.json").read_bytes(), before)

    def test_a_branch_is_resolved_to_its_commit(self) -> None:
        client = FakeClient(_files())
        result = download.download(self.sourcetexts_root, commit="main", client=client)
        self.assertEqual(result.commit, COMMIT)
        self.assertEqual(self._manifest()["commit"], COMMIT)
        self.assertTrue(client.requests[0].endswith("/repos/bdenckla/MAM-basics/commits/main"))

    def test_a_file_that_does_not_match_its_listing_is_refused(self) -> None:
        client = FakeClient(_files())
        client.get_bytes = lambda url, accept=None: b"tampered"
        with self.assertRaises(download.DownloadError):
            download.download(self.sourcetexts_root, commit=COMMIT, client=client)
        self.assertFalse((self.data_dir / "manifest.json").exists())

    def test_a_failed_download_leaves_the_previous_one_intact(self) -> None:
        download.download(self.sourcetexts_root, commit=COMMIT, client=FakeClient(_files()))
        before = {path: path.read_bytes() for path in self.data_dir.rglob("*") if path.is_file()}
        other = "fedcba9876543210fedcba9876543210fedcba98"
        files = {path: data + b" " for path, data in _files().items()}
        client = FakeClient(files, other)
        fetch = client.get_bytes

        def get_bytes(url: str, *, accept: str | None = None) -> bytes:
            # Song of Songs, fetched after Genesis, does not match its listing.
            return b"tampered" if url.endswith("Song%20of%20Songs.json") else fetch(url, accept=accept)

        client.get_bytes = get_bytes
        with self.assertRaises(download.DownloadError):
            download.download(self.sourcetexts_root, commit=other, client=client)
        after = {path: path.read_bytes() for path in self.data_dir.rglob("*") if path.is_file()}
        self.assertEqual(after, before)

    def test_only_files_a_previous_download_recorded_are_deleted(self) -> None:
        download.download(self.sourcetexts_root, commit=COMMIT, client=FakeClient(_files()))
        sheets = self.data_dir / "sheets" / "torah.tsv"
        sheets.parent.mkdir(parents=True)
        sheets.write_text("retired\n", encoding="utf-8")
        files = _files()
        del files["MAM-parsed/plus/E1-Song of Songs.json"]
        other = "fedcba9876543210fedcba9876543210fedcba98"
        result = download.download(self.sourcetexts_root, commit=other, client=FakeClient(files, other))
        self.assertEqual(result.deleted, ["plus/E1-Song of Songs.json"])
        self.assertFalse((self.data_dir / "plus" / "E1-Song of Songs.json").exists())
        self.assertTrue(sheets.exists())

    @patch("opensiddur.importer.miqra_al_pi_hamasorah.download.requests.Session")
    def test_dry_run_writes_nothing(self, mock_session) -> None:
        download.download(self.sourcetexts_root, dry_run=True)
        self.assertFalse(self.data_dir.exists())
        mock_session.assert_not_called()

    def test_main_dry_run_exit_code(self) -> None:
        with patch(
            "opensiddur.importer.miqra_al_pi_hamasorah.download.download"
        ) as mock_download:
            code = download.main(
                ["--dry-run", "--sourcetexts-root", str(self.sourcetexts_root)]
            )
        self.assertEqual(code, 0)
        mock_download.assert_called_once()
        self.assertTrue(mock_download.call_args.kwargs["dry_run"])


class TestClient(unittest.TestCase):
    URL = "https://api.github.com/repos/bdenckla/MAM-basics/contents/MAM-parsed"

    def setUp(self) -> None:
        self.sleeps: list[float] = []

    def _client(self, *responses: FakeResponse) -> tuple[download.Client, FakeSession]:
        session = FakeSession(*responses)
        return download.Client(session, sleep=self.sleeps.append, clock=lambda: 1000.0), session

    def test_a_real_client_sends_its_user_agent(self) -> None:
        # A requests session has a User-Agent of its own, which the client's replaces.
        self.assertEqual(download.Client().session.headers["User-Agent"], download.USER_AGENT)

    def test_retry_after_is_honoured(self) -> None:
        client, _ = self._client(FakeResponse(429, {"retry-after": "7"}), FakeResponse(200, content=b"ok"))
        with self.assertLogs(download.logger, "WARNING"):
            self.assertEqual(client.get_bytes(self.URL), b"ok")
        self.assertEqual(self.sleeps, [7.0])

    def test_a_used_up_rate_limit_is_waited_out_until_its_reset(self) -> None:
        used_up = {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1030"}
        client, _ = self._client(FakeResponse(503, used_up), FakeResponse(200, content=b"ok"))
        with self.assertLogs(download.logger, "WARNING"):
            self.assertEqual(client.get_bytes(self.URL), b"ok")
        self.assertEqual(self.sleeps, [30.0])

    def test_a_403_for_a_used_up_rate_limit_is_waited_out_until_its_reset(self) -> None:
        used_up = {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1030"}
        client, _ = self._client(FakeResponse(403, used_up), FakeResponse(200, content=b"ok"))
        with self.assertLogs(download.logger, "WARNING"):
            self.assertEqual(client.get_bytes(self.URL), b"ok")
        self.assertEqual(self.sleeps, [30.0])

    def test_a_403_with_retry_after_is_honoured(self) -> None:
        # GitHub's secondary rate limit, while the primary one still has requests left.
        limited = {"retry-after": "7", "x-ratelimit-remaining": "59"}
        client, _ = self._client(FakeResponse(403, limited), FakeResponse(200, content=b"ok"))
        with self.assertLogs(download.logger, "WARNING"):
            self.assertEqual(client.get_bytes(self.URL), b"ok")
        self.assertEqual(self.sleeps, [7.0])

    def test_a_wait_of_more_than_a_minute_fails_at_once(self) -> None:
        cases = (
            (FakeResponse(429, {"retry-after": "3600"}), "asks for a wait of 3600 s"),
            (FakeResponse(403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "4600"}),
             "rate limit asks for a wait of 3600 s until 1970-01-01T01:16:40"),
        )
        for response, message in cases:
            with self.subTest(status=response.status_code):
                self.sleeps.clear()
                client, session = self._client(response)
                with self.assertRaisesRegex(download.DownloadError, message):
                    client.get_bytes(self.URL)
                self.assertEqual((session.urls, self.sleeps), ([self.URL], []))

    def test_another_403_is_not_retried(self) -> None:
        client, session = self._client(FakeResponse(403, {"x-ratelimit-remaining": "59"}))
        with self.assertRaisesRegex(download.DownloadError, r"HTTP 403$"):
            client.get_bytes(self.URL)
        self.assertEqual((session.urls, self.sleeps), ([self.URL], []))

    def test_no_wait_after_the_last_attempt(self) -> None:
        client, session = self._client(*[FakeResponse(502)] * 4)
        with self.assertLogs(download.logger, "WARNING"), self.assertRaises(download.DownloadError):
            client.get_bytes(self.URL)
        self.assertEqual(len(session.urls), 4)
        self.assertEqual(self.sleeps, [1.0, 2.0, 4.0])


if __name__ == "__main__":
    unittest.main()
