"""Tests for fetching and cutting up a page of the Birnbaum scan.

Every fixture here is synthetic. The real ``pages.json`` is 815 entries derived from
three sources and is regenerated whenever any of them changes, so a test asserting
against it would be a test of the sources rather than of this code, and would start
failing for reasons that have nothing to do with what it checks.
"""

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from PIL import Image

from opensiddur.importer.birnbaum_scan import pages


def write_pages_json(directory: Path) -> Path:
    """A pages.json holding one opening and one unnumbered leaf."""
    payload = {
        "ia_identifier": "TestItem",
        "leaf_offset": -1,
        "pages": [
            {
                "scan_page": 106,
                "ia_leaf": 105,
                "printed_page": "81",
                "side": "he",
                "facing_scan_page": 107,
                "facs": "https://archive.org/download/TestItem/page/n105_medium.jpg",
            },
            {
                "scan_page": 107,
                "ia_leaf": 106,
                "printed_page": "82",
                "side": "en",
                "facing_scan_page": 106,
                "facs": "https://archive.org/download/TestItem/page/n106_medium.jpg",
            },
            {
                "scan_page": 3,
                "ia_leaf": 2,
                "printed_page": None,
                "side": None,
                "facing_scan_page": None,
                "facs": "https://archive.org/download/TestItem/page/n2_medium.jpg",
            },
        ],
    }
    path = directory / "pages.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class LoadPagesTestCase(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.pages_json = write_pages_json(Path(self.directory.name))

    def test_keys_by_printed_page_and_by_scan_page(self):
        """Both, so that a numbered leaf can be asked for either way."""
        table = pages.load_pages(self.pages_json)
        self.assertLessEqual({"81", "82", "s106", "s107"}, set(table))
        self.assertIs(table["81"], table["s106"])

    def test_reaches_a_leaf_the_print_does_not_number(self):
        """The front matter is mostly unnumbered, and has to be addressable anyway."""
        table = pages.load_pages(self.pages_json)
        unnumbered = [r for r in table.values() if r.printed_page is None]
        self.assertTrue(unnumbered, "the fixture has an unnumbered leaf")
        for reference in unnumbered:
            self.assertIn(f"s{reference.scan_page}", table)

    def test_designation_is_what_the_book_prints_else_the_scan_page(self):
        table = pages.load_pages(self.pages_json)
        self.assertEqual("81", table["s106"].designation)
        unnumbered = next(r for r in table.values() if r.printed_page is None)
        self.assertEqual(f"s{unnumbered.scan_page}", unnumbered.designation)

    def test_naming_a_leaf_that_answers_to_nothing_says_how_to_address_one(self):
        with self.assertRaises(pages.ScanError) as caught:
            pages.lookup("nonesuch", self.pages_json)
        self.assertIn("s", str(caught.exception))

    def test_records_every_numbering(self):
        reference = pages.load_pages(self.pages_json)["81"]
        self.assertEqual("81", reference.printed_page)
        self.assertEqual(106, reference.scan_page)
        self.assertEqual(105, reference.leaf)
        self.assertEqual("he", reference.side)
        self.assertEqual(107, reference.facing_scan_page)

    def test_printed_page_is_a_string(self):
        """The front matter numbers itself in Roman numerals, so the key is textual."""
        self.assertIsInstance(next(iter(pages.load_pages(self.pages_json))), str)

    def test_a_missing_pages_json_names_the_likely_cause(self):
        with self.assertRaises(pages.ScanError) as caught:
            pages.load_pages(Path(self.directory.name) / "absent.json")
        self.assertIn("submodule", str(caught.exception))


class LookupTestCase(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.pages_json = write_pages_json(Path(self.directory.name))

    def test_accepts_a_number_or_a_string(self):
        self.assertEqual(
            pages.lookup(81, self.pages_json), pages.lookup("81", self.pages_json)
        )

    def test_an_unprinted_number_is_reported_by_name(self):
        with self.assertRaises(pages.ScanError) as caught:
            pages.lookup(999, self.pages_json)
        self.assertIn("999", str(caught.exception))

    def test_image_url_is_full_resolution_not_the_facs_link(self):
        """@facs wants a link a person follows; reading wants every pixel there is."""
        reference = pages.lookup(81, self.pages_json)
        self.assertIn("_medium", reference.facs)
        self.assertNotIn("_medium", reference.image_url)
        self.assertTrue(reference.image_url.endswith("/page/n105.jpg"))


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.closed = False

    def iter_content(self, chunk_size=None):
        yield self.payload

    def close(self):
        self.closed = True


class FetchTestCase(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.pages_json = write_pages_json(root)
        patch = mock.patch.object(pages, "PAGE_DIRECTORY", root / "pages")
        patch.start()
        self.addCleanup(patch.stop)

    def test_fetches_the_leaf_the_printed_page_resolves_to(self):
        response = FakeResponse(b"\xff\xd8jpeg")
        with mock.patch.object(pages, "http_get", return_value=response) as http_get:
            path = pages.fetch(
                81, archive=mock.Mock(), pages_json=self.pages_json
            )
        self.assertEqual(b"\xff\xd8jpeg", path.read_bytes())
        self.assertTrue(http_get.call_args.args[1].endswith("/page/n105.jpg"))
        self.assertTrue(response.closed)

    def test_a_cached_page_is_never_refetched(self):
        cached = pages.image_path(81)
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(b"already here")
        with mock.patch.object(pages, "http_get") as http_get:
            path = pages.fetch(81, archive=mock.Mock(), pages_json=self.pages_json)
        http_get.assert_not_called()
        self.assertEqual(b"already here", path.read_bytes())

    def test_force_refetches(self):
        cached = pages.image_path(81)
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(b"stale")
        with mock.patch.object(
            pages, "http_get", return_value=FakeResponse(b"fresh")
        ):
            pages.fetch(
                81, archive=mock.Mock(), pages_json=self.pages_json, force=True
            )
        self.assertEqual(b"fresh", cached.read_bytes())

    def test_an_empty_body_leaves_nothing_behind(self):
        """A truncated fetch must not leave a file that looks like a cached page."""
        with mock.patch.object(pages, "http_get", return_value=FakeResponse(b"")):
            with self.assertRaises(pages.ScanError):
                pages.fetch(81, archive=mock.Mock(), pages_json=self.pages_json)
        self.assertFalse(pages.image_path(81).exists())
        self.assertFalse(pages.image_path(81).with_suffix(".jpg.part").exists())

    def test_no_contact_address_is_refused_before_any_request(self):
        with mock.patch.dict("os.environ", {pages.CONTACT_EMAIL_ENV_VAR: ""}):
            with mock.patch.object(pages, "http_get") as http_get:
                with self.assertRaises(pages.ScanError) as caught:
                    pages.fetch(81, pages_json=self.pages_json)
        http_get.assert_not_called()
        self.assertIn(pages.CONTACT_EMAIL_ENV_VAR, str(caught.exception))


class BandsTestCase(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        patch = mock.patch.object(pages, "BAND_DIRECTORY", root / "bands")
        patch.start()
        self.addCleanup(patch.stop)
        self.source = root / "page.jpg"
        Image.new("L", (100, 400), color=255).save(self.source)

    def test_one_band_per_slice_in_reading_order(self):
        written = pages.bands(81, count=4, source=self.source)
        self.assertEqual(4, len(written))
        self.assertEqual(
            [pages.band_path(81, i) for i in range(4)], written
        )
        self.assertTrue(all(path.is_file() for path in written))

    def test_enlarged_by_the_scale(self):
        """A qamats is a few pixels tall at 1541px; the enlargement is the point."""
        written = pages.bands(81, count=4, overlap=0, scale=3, source=self.source)
        with Image.open(written[0]) as band:
            self.assertEqual(300, band.width)
            self.assertEqual(300, band.height)

    def test_bands_overlap_so_no_line_is_cut_in_two(self):
        # Read each height before the next call, since a band is written to the same
        # path every time -- re-cutting a page replaces its bands rather than adding
        # to them, which is what makes the cache safe to re-run.
        plain = pages.bands(81, count=4, overlap=0, scale=1, source=self.source)
        with Image.open(plain[1]) as band:
            without = band.height
        overlapped = pages.bands(81, count=4, overlap=0.25, scale=1, source=self.source)
        with Image.open(overlapped[1]) as band:
            with_overlap = band.height
        self.assertEqual(100, without)
        self.assertEqual(150, with_overlap)

    def test_the_bands_cover_the_whole_page(self):
        written = pages.bands(81, count=4, overlap=0, scale=1, source=self.source)
        total = 0
        for path in written:
            with Image.open(path) as band:
                total += band.height
        self.assertEqual(400, total)

    def test_an_unfetched_page_is_reported_rather_than_guessed_at(self):
        with self.assertRaises(pages.ScanError):
            pages.bands(97, source=self.directory.name + "/absent.jpg")

    def test_refuses_a_nonsensical_cut(self):
        with self.assertRaises(ValueError):
            pages.bands(81, count=0, source=self.source)
        with self.assertRaises(ValueError):
            pages.bands(81, overlap=0.5, source=self.source)


class CommandLineTestCase(unittest.TestCase):
    """The fetching and the cutting are tested above; this is the wiring between them.

    Both are patched out: what the command line owes a caller is that it names every
    page it was asked for, honours --no-bands, and passes the cutting options through.
    """

    def _run(self, *arguments):
        output = io.StringIO()
        with mock.patch.object(pages, "fetch", side_effect=lambda p, **kw: Path(f"/scan/{p}.jpg")) as fetch, \
             mock.patch.object(pages, "bands", return_value=[Path("/scan/81-1.jpg")]) as bands, \
             redirect_stdout(output):
            self.assertEqual(0, pages.main(list(arguments)))
        return output.getvalue(), fetch, bands

    def test_fetches_and_cuts_every_page_it_is_given(self):
        printed, fetch, bands = self._run("81", "82")
        self.assertEqual(["81", "82"], [call.args[0] for call in fetch.call_args_list])
        self.assertEqual(2, bands.call_count)
        self.assertIn(str(Path("/scan/81.jpg")), printed)
        self.assertIn(str(Path("/scan/81-1.jpg")), printed)

    def test_no_bands_fetches_the_page_and_stops_there(self):
        printed, _, bands = self._run("81", "--no-bands")
        bands.assert_not_called()
        self.assertIn(str(Path("/scan/81.jpg")), printed)

    def test_passes_the_cutting_options_through(self):
        _, fetch, bands = self._run("81", "--bands", "6", "--scale", "3", "--force")
        self.assertTrue(fetch.call_args.kwargs["force"])
        self.assertEqual({"count": 6, "scale": 3}, bands.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
