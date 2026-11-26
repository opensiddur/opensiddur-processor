"""Tests for the Birnbaum Internet Archive downloader.

The whole book here is four synthetic leaves in a temporary sourcetexts tree, with
every network call faked. Nothing reads the real item or the real sourcetexts data, so
none of this changes meaning when either does.
"""

import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from opensiddur.importer.birnbaum_siddur import internet_archive as birnbaum_ia
from opensiddur.importer.birnbaum_siddur.internet_archive import (
    DEFAULT_DERIVATIVES,
    DJVU_SUFFIX,
    PAGEINDEX_SUFFIX,
    SCANDATA_SUFFIX,
    SEARCHTEXT_SUFFIX,
    TEXT_PDF_SUFFIX,
    download_ia,
    leaf_for_scan_page,
    main,
    scan_page_for_leaf,
)
from opensiddur.importer.util.internet_archive import (
    DownloadedFile,
    InternetArchiveError,
    ItemFile,
    ItemMetadata,
    sha256_file,
)
from opensiddur.importer.util.pages import (
    birnbaum_siddur_ia_derivatives_directory,
    birnbaum_siddur_ia_directory,
    birnbaum_siddur_ia_ocr_directory,
)

# A name carrying the punctuation the real one does.
BASENAME = "Synthetic Book (Subtitle,1949).pdf"

# Not an example.* domain: resolve_contact_email rejects those as unreachable.
CONTACT = "tests@opensiddur.invalid"

# Four leaves, two of which end in multi-byte characters so the byte offsets in the
# page index differ from character offsets.
LEAVES = ["front matter\n", "café au lait\n", "naïve — dash\n", "plain\n"]


def build_searchtext():
    buf = "".join(LEAVES).encode("utf-8")
    index, start = [], 0
    for leaf in LEAVES:
        end = start + len(leaf.encode("utf-8"))
        index.append([start, end, 0, 0])
        start = end
    return buf, index


def build_scandata(leaves):
    pages = "".join(f'<page leafNum="{n}"/>' for n in range(leaves))
    return f"<book><pageData>{pages}</pageData></book>".encode()


def build_page_numbers():
    return json.dumps(
        {
            "pages": [
                {"leafNum": 0, "pageNumber": "", "confidence": None},
                {"leafNum": 1, "pageNumber": "i", "confidence": 90},
                {"leafNum": 2, "pageNumber": "1", "confidence": 95},
                {"leafNum": 3, "pageNumber": "2", "confidence": 95},
            ]
        }
    ).encode("utf-8")


class BirnbaumIaTestCase(unittest.TestCase):
    """Fixture wiring the downloader to a temporary tree and a fake Archive."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

        self.data_dir = birnbaum_siddur_ia_directory(self.root)
        self.derivatives_dir = birnbaum_siddur_ia_derivatives_directory(self.root)
        self.ocr_dir = birnbaum_siddur_ia_ocr_directory(self.root)

        searchtext, index = build_searchtext()
        self.contents = {
            BASENAME: b"%PDF-1.4 pretend this is 488 megabytes",
            BASENAME + "_page_numbers.json": build_page_numbers(),
            BASENAME + PAGEINDEX_SUFFIX: gzip.compress(
                json.dumps(index).encode("utf-8")
            ),
            BASENAME + SEARCHTEXT_SUFFIX: gzip.compress(searchtext),
            BASENAME + SCANDATA_SUFFIX: build_scandata(len(LEAVES)),
            BASENAME + DJVU_SUFFIX: b"<DjVuXML/>",
            BASENAME + TEXT_PDF_SUFFIX: b"%PDF-1.4 text only",
        }

        self.metadata = ItemMetadata(
            identifier=birnbaum_ia.IA_IDENTIFIER,
            metadata={"identifier": birnbaum_ia.IA_IDENTIFIER, "rights": "public domain"},
            files={
                name: ItemFile(name=name, size=len(body), sha1=f"sha1-of-{name}")
                for name, body in self.contents.items()
            },
        )

        # Every file the code actually asked the Archive for, in order.
        self.requested: list[str] = []

        patcher = patch.multiple(
            birnbaum_ia,
            fetch_metadata=MagicMock(return_value=self.metadata),
            download_file=MagicMock(side_effect=self.fake_download_file),
            connect=MagicMock(return_value=MagicMock()),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake_download_file(self, archive, identifier, item_file, destination, *, force=False):
        body = self.contents[item_file.name]
        # Mirror the real skip-if-unchanged behaviour, so a second run through the
        # fixture is as quiet as a second run against archive.org.
        if destination.is_file() and destination.read_bytes() == body and not force:
            return DownloadedFile(
                path=destination,
                sha256=sha256_file(destination),
                size=len(body),
                skipped=True,
            )
        self.requested.append(item_file.name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
        return DownloadedFile(
            path=destination, sha256=sha256_file(destination), size=len(body)
        )

    def run_download(self, **kwargs):
        return download_ia(CONTACT, self.root, **kwargs)

    def read_manifest(self):
        return json.loads((self.data_dir / "manifest.json").read_text(encoding="utf-8"))


class LeafArithmeticTestCase(unittest.TestCase):
    """The Archive numbers leaves from zero; the wiki numbers pages from one."""

    def test_the_offset_round_trips(self):
        self.assertEqual(leaf_for_scan_page(100), 99)
        self.assertEqual(scan_page_for_leaf(99), 100)
        self.assertEqual(leaf_for_scan_page(1), 0)
        for scan_page in (1, 27, 738, 815):
            self.assertEqual(scan_page_for_leaf(leaf_for_scan_page(scan_page)), scan_page)


class DownloadSetTestCase(BirnbaumIaTestCase):
    def test_only_the_small_derivatives_are_fetched_by_default(self):
        self.run_download()
        self.assertEqual(
            self.requested,
            [BASENAME + suffix for suffix in DEFAULT_DERIVATIVES],
        )

    def test_the_scan_pdf_is_never_fetched_by_default(self):
        self.run_download()
        # Half a gigabyte that must never enter sourcetexts.
        self.assertNotIn(BASENAME, self.requested)

    def test_with_djvu_adds_exactly_one_file(self):
        self.run_download(with_djvu=True)
        self.assertEqual(len(self.requested), len(DEFAULT_DERIVATIVES) + 1)
        self.assertIn(BASENAME + DJVU_SUFFIX, self.requested)

    def test_with_text_pdf_adds_exactly_one_file(self):
        self.run_download(with_text_pdf=True)
        self.assertEqual(len(self.requested), len(DEFAULT_DERIVATIVES) + 1)
        self.assertIn(BASENAME + TEXT_PDF_SUFFIX, self.requested)

    def test_fetch_pdf_writes_outside_sourcetexts(self):
        pdf_dir = self.root / "elsewhere"
        self.run_download(fetch_pdf=True, pdf_dir=pdf_dir)

        self.assertIn(BASENAME, self.requested)
        self.assertTrue((pdf_dir / BASENAME).is_file())
        # It must not have landed anywhere under the sourcetexts tree.
        self.assertEqual(list(self.data_dir.rglob("*.pdf")), [])

    def test_a_missing_derivative_is_an_error(self):
        del self.metadata.files[BASENAME + SCANDATA_SUFFIX]
        with self.assertRaises(InternetArchiveError):
            self.run_download()

    def test_dry_run_writes_nothing_at_all(self):
        self.run_download(dry_run=True)
        self.assertEqual(self.requested, [])
        self.assertFalse(self.data_dir.exists())


class SliceTestCase(BirnbaumIaTestCase):
    def test_one_ocr_file_per_leaf_named_by_scan_page(self):
        self.run_download()
        written = sorted(p.name for p in self.ocr_dir.glob("*.txt"))
        # Leaves 0-3 become scan pages 1-4, zero-padded to the book's three digits.
        self.assertEqual(written, ["001.txt", "002.txt", "003.txt", "004.txt"])

    def test_leaf_text_lands_on_the_right_scan_page(self):
        self.run_download()
        for leaf, expected in enumerate(LEAVES):
            key = f"{scan_page_for_leaf(leaf):03d}"
            actual = (self.ocr_dir / f"{key}.txt").read_text(encoding="utf-8")
            self.assertEqual(actual, expected, f"leaf {leaf}")

    def test_multibyte_text_survives_slicing(self):
        self.run_download()
        # If the slicing had happened on a decoded string these would be truncated
        # or shifted; the accented leaves are the ones that would show it.
        self.assertIn("café", (self.ocr_dir / "002.txt").read_text(encoding="utf-8"))
        self.assertIn("naïve — dash", (self.ocr_dir / "003.txt").read_text(encoding="utf-8"))

    def test_slicing_stops_when_the_derivatives_disagree(self):
        # A scan data file describing a different book length means the two
        # derivatives are not from the same scan.
        self.contents[BASENAME + SCANDATA_SUFFIX] = build_scandata(len(LEAVES) + 1)
        self.metadata.files[BASENAME + SCANDATA_SUFFIX].size = len(
            self.contents[BASENAME + SCANDATA_SUFFIX]
        )
        with self.assertRaises(InternetArchiveError):
            self.run_download()
        self.assertFalse(self.ocr_dir.exists())

    def test_skip_slice_leaves_the_ocr_alone(self):
        self.run_download(skip_slice=True)
        self.assertFalse(self.ocr_dir.exists())
        self.assertEqual(self.read_manifest()["ocr"], {})


class ManifestTestCase(BirnbaumIaTestCase):
    def test_manifest_lands_beside_the_derivatives(self):
        self.run_download()
        self.assertTrue((self.data_dir / "manifest.json").is_file())

    def test_manifest_records_both_checksums(self):
        self.run_download()
        entry = self.read_manifest()["derivatives"][BASENAME + SCANDATA_SUFFIX]
        # Ours proves what is on disk; the Archive's distinguishes a re-derivation
        # of the same scan from the scan itself changing.
        self.assertEqual(len(entry["sha256"]), 64)
        self.assertEqual(entry["ia_sha1"], f"sha1-of-{BASENAME}{SCANDATA_SUFFIX}")

    def test_manifest_records_the_leaf_offset_and_page_count(self):
        manifest = self.run_download()
        self.assertEqual(manifest["leaf_offset"], -1)
        self.assertEqual(manifest["ocr"]["pages"], len(LEAVES))
        self.assertEqual(manifest["ocr"]["leaf_count"], len(LEAVES))

    def test_item_metadata_is_kept_whole(self):
        self.run_download()
        payload = json.loads((self.data_dir / "metadata.json").read_text(encoding="utf-8"))
        # The rights statement and the PDF's sha1 are the evidence for the licensing
        # claims made about this material, so the item's own metadata is preserved.
        self.assertEqual(payload["metadata"]["rights"], "public domain")

    def test_an_unchanged_rerun_leaves_no_diff(self):
        self.run_download()
        before = (self.data_dir / "manifest.json").read_text(encoding="utf-8")
        ocr_before = {
            p.name: (p.read_text(encoding="utf-8"), p.stat().st_mtime_ns)
            for p in self.ocr_dir.glob("*.txt")
        }
        self.requested.clear()

        self.run_download()

        # Nothing fetched, nothing rewritten -- not even the manifest, whose
        # timestamp would otherwise churn a diff on every run.
        self.assertEqual(self.requested, [])
        self.assertEqual((self.data_dir / "manifest.json").read_text(encoding="utf-8"), before)
        for path in self.ocr_dir.glob("*.txt"):
            text, mtime = ocr_before[path.name]
            self.assertEqual(path.read_text(encoding="utf-8"), text)
            self.assertEqual(path.stat().st_mtime_ns, mtime, path.name)

    def test_changed_ocr_is_rewritten_and_the_manifest_updated(self):
        self.run_download()
        before = (self.data_dir / "manifest.json").read_text(encoding="utf-8")

        searchtext, index = build_searchtext()
        altered = searchtext.replace(b"plain", b"PLAIN")
        self.contents[BASENAME + SEARCHTEXT_SUFFIX] = gzip.compress(altered)
        self.metadata.files[BASENAME + SEARCHTEXT_SUFFIX].size = len(
            self.contents[BASENAME + SEARCHTEXT_SUFFIX]
        )

        self.run_download()

        self.assertIn("PLAIN", (self.ocr_dir / "004.txt").read_text(encoding="utf-8"))
        self.assertNotEqual(
            (self.data_dir / "manifest.json").read_text(encoding="utf-8"), before
        )

    def test_large_derivatives_are_kept_out_of_git(self):
        self.run_download()
        ignored = (self.data_dir / ".gitignore").read_text(encoding="utf-8")
        for pattern in ("*_djvu.xml", "*_text.pdf", "*.part"):
            self.assertIn(pattern, ignored)


class MainTestCase(BirnbaumIaTestCase):
    def test_main_returns_zero_on_success(self):
        code = main(
            [
                "--sourcetexts-root",
                str(self.root),
                "--contact-email",
                CONTACT,
            ]
        )
        self.assertEqual(code, 0)
        self.assertTrue((self.data_dir / "manifest.json").is_file())

    def test_main_reports_a_failure_without_a_traceback(self):
        del self.metadata.files[BASENAME + PAGEINDEX_SUFFIX]
        code = main(
            [
                "--sourcetexts-root",
                str(self.root),
                "--contact-email",
                CONTACT,
            ]
        )
        self.assertEqual(code, 1)

    def test_main_requires_a_real_contact_address(self):
        with patch.dict("os.environ", {"OPENSIDDUR_CONTACT_EMAIL": ""}):
            self.assertEqual(main(["--sourcetexts-root", str(self.root)]), 1)


if __name__ == "__main__":
    unittest.main()
