"""What the scan viewer shows for a link to a scan (scan_view.py)."""

import hashlib
import unittest

from opensiddur.exporter.scan_view import scan_view, wikimedia_page_image


class TestScanView(unittest.TestCase):
    def test_an_archive_page_is_shown_at_full_size(self):
        self.assertEqual(
            ("image", "https://archive.org/download/someBook1949/page/n417.jpg"),
            scan_view("https://archive.org/download/someBook1949/page/n417_medium.jpg"))

    def test_an_archive_page_at_full_size_is_kept(self):
        self.assertEqual(
            ("image", "https://archive.org/download/someBook/page/n3.jpg"),
            scan_view("https://archive.org/download/someBook/page/n3.jpg"))

    def test_a_wikisource_page_is_shown_as_the_commons_page_image(self):
        kind, url = scan_view("https://en.wikisource.org/wiki/Page:Some_Scan.djvu/995")
        digest = hashlib.md5(b"Some_Scan.djvu").hexdigest()
        self.assertEqual("image", kind)
        self.assertEqual(
            f"https://upload.wikimedia.org/wikipedia/commons/thumb/{digest[0]}/{digest[:2]}/"
            "Some_Scan.djvu/page995-1280px-Some_Scan.djvu.jpg", url)

    def test_the_commons_path_is_the_md5_of_the_underscored_name(self):
        # Commons stores File:A b.djvu as A_b.djvu, under its md5's first hex digits.
        digest = hashlib.md5(b"A_b.djvu").hexdigest()
        self.assertIn(f"/thumb/{digest[0]}/{digest[:2]}/A_b.djvu/page2-",
                      wikimedia_page_image("A b.djvu", 2))

    def test_a_hebrewbooks_page_is_shown_as_its_page_pdf(self):
        self.assertEqual(
            ("pdf", "https://beta.hebrewbooks.org/pagefeed/hebrewbooks_org_12_34.pdf"),
            scan_view("https://www.hebrewbooks.org/pdfpager.aspx?req=12&pgnum=34"))

    def test_any_image_is_shown_as_it_is(self):
        self.assertEqual(("image", "https://scan.example/a/page.PNG"),
                         scan_view("https://scan.example/a/page.PNG"))
        self.assertEqual(("image", "data:image/png;base64,AAAA"),
                         scan_view("data:image/png;base64,AAAA"))

    def test_a_web_page_cannot_be_shown(self):
        self.assertIsNone(scan_view("https://scan.example/viewer?page=3"))
        self.assertIsNone(scan_view("https://www.hebrewbooks.org/pdfpager.aspx?req=x"))
        self.assertIsNone(scan_view("ftp://scan.example/page.png"))
        self.assertIsNone(scan_view(""))

    def test_only_wikisource_itself_is_read_as_wikisource(self):
        self.assertIsNone(scan_view("https://notwikisource.org/wiki/Page:Some_Scan.djvu/1"))
        self.assertIsNotNone(scan_view("https://wikisource.org/wiki/Page:Some_Scan.djvu/1"))


if __name__ == "__main__":
    unittest.main()
