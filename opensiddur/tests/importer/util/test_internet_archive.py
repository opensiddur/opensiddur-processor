"""Tests for the Internet Archive client.

Everything here runs against synthetic derivatives built in the test and a fake HTTP
session: no network, and no dependence on what any real Archive item contains today.
"""

import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from opensiddur.importer.util import internet_archive as ia
from opensiddur.importer.util.internet_archive import (
    Archive,
    InternetArchiveError,
    ItemFile,
    ItemMetadata,
    fetch_metadata,
    file_url,
    leaf_count_from_scandata,
    load_pageindex,
    load_page_numbers,
    page_image_url,
    resolve_agent_model,
    slice_searchtext,
    user_agent,
    write_if_changed,
)

IDENTIFIER = "SyntheticItem"

# A name with the punctuation real uploads carry: spaces, a comma, parentheses.
AWKWARD_NAME = "Some Book - a title (Subtitle,1949).pdf"


def fake_response(
    *, status=200, payload=None, body=b"", headers=None
) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.ok = 200 <= status < 400
    response.headers = headers or {}
    response.json = MagicMock(return_value=payload)
    response.iter_content = MagicMock(return_value=[body] if body else [])
    return response


def fake_archive(responses) -> Archive:
    """An Archive whose session returns the given responses in order."""
    session = MagicMock()
    session.get = MagicMock(side_effect=list(responses))
    limiter = MagicMock()
    return Archive(session=session, limiter=limiter, timeout=1, max_retries=3)


class UserAgentTestCase(unittest.TestCase):
    """The Archive's bot policy asks AI agents to name their model."""

    def test_plain_user_agent_for_a_human_run(self):
        agent = user_agent("someone@example.net")
        self.assertIn("OpenSiddur-Processor/", agent)
        self.assertIn("someone@example.net", agent)
        self.assertTrue(agent.endswith(")"))

    def test_model_is_named_inside_the_comment(self):
        agent = user_agent("someone@example.net", "claude-opus-5")
        self.assertTrue(agent.endswith("; claude-opus-5)"))
        self.assertIn("someone@example.net", agent)

    def test_model_resolves_from_the_environment(self):
        with patch.dict("os.environ", {ia.AGENT_MODEL_ENV_VAR: "some-model"}):
            self.assertEqual(resolve_agent_model(), "some-model")
            self.assertEqual(resolve_agent_model("explicit"), "explicit")

    def test_no_model_without_a_setting(self):
        with patch.dict("os.environ", {ia.AGENT_MODEL_ENV_VAR: ""}):
            self.assertIsNone(resolve_agent_model())


class UrlTestCase(unittest.TestCase):
    def test_file_url_quotes_awkward_names(self):
        url = file_url(IDENTIFIER, AWKWARD_NAME)
        self.assertIn("%20", url)  # space
        self.assertIn("%2C", url)  # comma
        self.assertIn("%28", url)  # (
        # Nothing unquoted may survive, or the request goes to the wrong path.
        self.assertNotIn(" ", url)
        self.assertTrue(url.startswith(f"{ia.BASE_URL}/download/{IDENTIFIER}/"))

    def test_page_image_url_uses_the_zero_based_leaf(self):
        self.assertTrue(page_image_url(IDENTIFIER, 26).endswith("/page/n26_medium.jpg"))
        self.assertTrue(page_image_url(IDENTIFIER, 0, "").endswith("/page/n0.jpg"))


class MetadataTestCase(unittest.TestCase):
    def test_files_and_metadata_are_read_from_one_request(self):
        payload = {
            "metadata": {"identifier": IDENTIFIER, "rights": "public domain"},
            "files": [
                {"name": AWKWARD_NAME, "format": "PDF", "size": "12", "sha1": "abc"},
                {"name": AWKWARD_NAME + "_djvu.txt", "format": "DjVuTXT", "size": "3"},
            ],
        }
        archive = fake_archive([fake_response(payload=payload)])
        metadata = fetch_metadata(archive, IDENTIFIER)

        self.assertEqual(metadata.metadata["rights"], "public domain")
        self.assertEqual(len(metadata.files), 2)
        self.assertEqual(metadata.files[AWKWARD_NAME].size, 12)
        self.assertEqual(metadata.files[AWKWARD_NAME].sha1, "abc")
        # One request describes the whole item; no per-file probing.
        self.assertEqual(archive.session.get.call_count, 1)

    def test_missing_item_is_an_error(self):
        # The endpoint answers 200 with an empty object for an unknown identifier.
        archive = fake_archive([fake_response(payload={})])
        with self.assertRaises(InternetArchiveError):
            fetch_metadata(archive, IDENTIFIER)

    def test_find_suffix_matches_one_file(self):
        metadata = ItemMetadata(
            identifier=IDENTIFIER,
            files={
                "a_scandata.xml": ItemFile(name="a_scandata.xml"),
                "a_djvu.txt": ItemFile(name="a_djvu.txt"),
            },
        )
        self.assertEqual(metadata.find_suffix("_scandata.xml").name, "a_scandata.xml")
        self.assertIsNone(metadata.find_suffix("_page_numbers.json"))

    def test_ambiguous_suffix_is_an_error(self):
        metadata = ItemMetadata(
            identifier=IDENTIFIER,
            files={
                "a_scandata.xml": ItemFile(name="a_scandata.xml"),
                "b_scandata.xml": ItemFile(name="b_scandata.xml"),
            },
        )
        with self.assertRaises(InternetArchiveError):
            metadata.find_suffix("_scandata.xml")


class RetryTestCase(unittest.TestCase):
    def test_429_is_retried_honouring_retry_after(self):
        archive = fake_archive(
            [
                fake_response(status=429, headers={"Retry-After": "0"}),
                fake_response(payload={"metadata": {}, "files": []}),
            ]
        )
        with patch.object(ia.time, "sleep") as sleep:
            fetch_metadata(archive, IDENTIFIER)
        self.assertEqual(archive.session.get.call_count, 2)
        sleep.assert_called_once_with(0.0)

    def test_retries_are_not_infinite(self):
        archive = fake_archive([fake_response(status=503) for _ in range(3)])
        with patch.object(ia.time, "sleep"):
            with self.assertRaises(InternetArchiveError):
                fetch_metadata(archive, IDENTIFIER)
        self.assertEqual(archive.session.get.call_count, 3)

    def test_a_404_is_not_retried(self):
        archive = fake_archive([fake_response(status=404)])
        with self.assertRaises(InternetArchiveError):
            fetch_metadata(archive, IDENTIFIER)
        self.assertEqual(archive.session.get.call_count, 1)


class DownloadFileTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_download_records_a_checksum_and_leaves_no_partial(self):
        body = b"some bytes"
        item = ItemFile(name=AWKWARD_NAME, size=len(body), sha1="unused")
        archive = fake_archive([fake_response(body=body)])

        result = ia.download_file(archive, IDENTIFIER, item, self.root / "out.pdf")

        self.assertFalse(result.skipped)
        self.assertEqual(result.size, len(body))
        self.assertEqual((self.root / "out.pdf").read_bytes(), body)
        self.assertEqual(result.sha256, ia.sha256_file(self.root / "out.pdf"))
        self.assertEqual(list(self.root.glob("*.part")), [])

    def test_an_unchanged_file_is_not_refetched(self):
        body = b"some bytes"
        destination = self.root / "out.pdf"
        destination.write_bytes(body)
        item = ItemFile(name="out.pdf", size=len(body), sha1=ia._sha1_file(destination))
        archive = fake_archive([])

        result = ia.download_file(archive, IDENTIFIER, item, destination)

        self.assertTrue(result.skipped)
        archive.session.get.assert_not_called()

    def test_force_refetches_an_unchanged_file(self):
        body = b"some bytes"
        destination = self.root / "out.pdf"
        destination.write_bytes(body)
        item = ItemFile(name="out.pdf", size=len(body), sha1=ia._sha1_file(destination))
        archive = fake_archive([fake_response(body=body)])

        result = ia.download_file(archive, IDENTIFIER, item, destination, force=True)

        self.assertFalse(result.skipped)
        self.assertEqual(archive.session.get.call_count, 1)

    def test_a_file_of_the_right_name_but_wrong_content_is_refetched(self):
        destination = self.root / "out.pdf"
        destination.write_bytes(b"stale")
        item = ItemFile(name="out.pdf", size=5, sha1="0" * 40)
        archive = fake_archive([fake_response(body=b"fresh")])

        result = ia.download_file(archive, IDENTIFIER, item, destination)

        self.assertFalse(result.skipped)
        self.assertEqual(destination.read_bytes(), b"fresh")

    def test_a_truncated_download_is_rejected_and_discarded(self):
        item = ItemFile(name="out.pdf", size=999)
        archive = fake_archive([fake_response(body=b"short")])

        with self.assertRaises(InternetArchiveError):
            ia.download_file(archive, IDENTIFIER, item, self.root / "out.pdf")

        # Neither the destination nor a partial file is left behind to be mistaken
        # for a complete download on the next run.
        self.assertFalse((self.root / "out.pdf").exists())
        self.assertEqual(list(self.root.glob("*.part")), [])


class SearchTextTestCase(unittest.TestCase):
    """Slicing the whole-book OCR into leaves.

    The page index holds byte offsets into a file that is far from pure ASCII, so
    these tests exist mainly to pin down that the slicing happens on bytes.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

        # Three leaves. The first two end in multi-byte characters, so every span
        # after the first starts at a byte offset larger than its character offset.
        self.leaves = ["café ", "naïve — dash ", "plain ascii"]
        self.buf = "".join(self.leaves).encode("utf-8")

        self.index = []
        start = 0
        for leaf in self.leaves:
            end = start + len(leaf.encode("utf-8"))
            self.index.append((start, end, 0, 0))
            start = end

    def write_index(self, index, *, gzipped=False) -> Path:
        path = self.root / ("index.json.gz" if gzipped else "index.json")
        payload = json.dumps([list(entry) for entry in index]).encode("utf-8")
        path.write_bytes(gzip.compress(payload) if gzipped else payload)
        return path

    def test_leaves_are_sliced_on_byte_offsets(self):
        chunks = slice_searchtext(self.buf, self.index)
        self.assertEqual([c.decode("utf-8") for c in chunks], self.leaves)

    def test_slicing_the_decoded_string_would_be_wrong(self):
        # Guards the reason the API takes bytes: with the same offsets applied to a
        # str, every leaf after the first multi-byte character is misaligned. If this
        # ever stops being true the test above has stopped testing anything.
        text = self.buf.decode("utf-8")
        naive = [text[start:end] for start, end, _, _ in self.index]
        self.assertNotEqual(naive, self.leaves)

    def test_gzipped_and_plain_indexes_read_the_same(self):
        self.assertEqual(
            load_pageindex(self.write_index(self.index)),
            load_pageindex(self.write_index(self.index, gzipped=True)),
        )

    def test_non_monotonic_spans_are_rejected(self):
        broken = list(self.index)
        broken[2] = (0, 4, 0, 0)
        with self.assertRaises(InternetArchiveError):
            slice_searchtext(self.buf, broken)

    def test_a_span_ending_before_it_starts_is_rejected(self):
        broken = list(self.index)
        broken[1] = (broken[1][0], broken[1][0] - 1, 0, 0)
        with self.assertRaises(InternetArchiveError):
            slice_searchtext(self.buf, broken)

    def test_an_index_longer_than_the_text_is_rejected(self):
        # The two derivatives would not be describing the same scan.
        with self.assertRaises(InternetArchiveError):
            slice_searchtext(self.buf[:-3], self.index)

    def test_an_empty_index_file_is_rejected(self):
        with self.assertRaises(InternetArchiveError):
            load_pageindex(self.write_index([]))

    def test_a_malformed_span_is_rejected(self):
        path = self.root / "index.json"
        path.write_text("[[1, 2]]", encoding="utf-8")
        with self.assertRaises(InternetArchiveError):
            load_pageindex(path)


class PageNumbersTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def write(self, payload) -> Path:
        path = self.root / "page_numbers.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_numbers_are_keyed_by_leaf_and_confidence_normalised(self):
        path = self.write(
            {
                "pages": [
                    {"leafNum": 0, "pageNumber": "", "confidence": None},
                    {"leafNum": 1, "pageNumber": "ix", "confidence": 50},
                    {"leafNum": 2, "pageNumber": "2", "confidence": 100},
                ]
            }
        )
        numbers = load_page_numbers(path)

        self.assertIsNone(numbers[0].printed)
        # Roman numerals are page numbers too; front matter has nothing else.
        self.assertEqual(numbers[1].printed, "ix")
        self.assertEqual(numbers[1].confidence, 0.5)
        self.assertEqual(numbers[2].confidence, 1.0)

    def test_a_file_without_pages_is_rejected(self):
        with self.assertRaises(InternetArchiveError):
            load_page_numbers(self.write({"identifier": "x"}))


class ScandataTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def write(self, text) -> Path:
        path = self.root / "scandata.xml"
        path.write_text(text, encoding="utf-8")
        return path

    def test_leaves_are_counted(self):
        path = self.write(
            '<book><pageData>'
            '<page leafNum="0"/><page leafNum="1"/><page leafNum="2"/>'
            "</pageData></book>"
        )
        self.assertEqual(leaf_count_from_scandata(path), 3)

    def test_a_namespaced_file_is_counted_the_same(self):
        path = self.write(
            '<book xmlns="http://archive.org/scribe/xml"><pageData>'
            '<page leafNum="0"/><page leafNum="1"/>'
            "</pageData></book>"
        )
        self.assertEqual(leaf_count_from_scandata(path), 2)

    def test_a_file_describing_no_leaves_is_rejected(self):
        with self.assertRaises(InternetArchiveError):
            leaf_count_from_scandata(self.write("<book><pageData/></book>"))

    def test_unparseable_scandata_is_rejected(self):
        with self.assertRaises(InternetArchiveError):
            leaf_count_from_scandata(self.write("<book>"))


class WriteIfChangedTestCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "sub" / "he.json"

    def test_writes_a_new_file_with_lf_endings(self):
        self.assertTrue(write_if_changed(self.path, "א\nב\n"))
        self.assertEqual("א\nב\n".encode("utf-8"), self.path.read_bytes())

    def test_leaves_an_identical_file_alone(self):
        self.path.parent.mkdir()
        self.path.write_bytes("א\n".encode("utf-8"))
        self.assertFalse(write_if_changed(self.path, "א\n"))

    def test_rewrites_a_file_that_differs_only_in_crlf_endings(self):
        # What a Windows checkout with core.autocrlf leaves on disk. Decoded as text it
        # equals the new text, but its bytes, and so its SHA-256, do not.
        self.path.parent.mkdir()
        self.path.write_bytes("א\r\nב\r\n".encode("utf-8"))
        self.assertTrue(write_if_changed(self.path, "א\nב\n"))
        self.assertEqual("א\nב\n".encode("utf-8"), self.path.read_bytes())
        self.assertFalse(write_if_changed(self.path, "א\nב\n"))


if __name__ == "__main__":
    unittest.main()
