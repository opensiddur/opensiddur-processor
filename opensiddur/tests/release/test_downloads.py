"""The downloads list of a book release, from synthetic settings and a synthetic release."""

import json
import tempfile
import unittest
from pathlib import Path

from opensiddur.release.downloads import (
    BookEntry,
    book_entries,
    human_size,
    main,
    render_downloads,
)

TAG = "v20990101"
RELEASES = "https://github.com/example/projects/releases"


def asset(name: str, size: int = 2048) -> dict:
    return {"name": name, "size": size, "url": f"{RELEASES}/download/{TAG}/{name}"}


def release(assets: list[dict], body: str = "Built with opensiddur-processor v9.8.7 (link)") -> dict:
    return {
        "tagName": TAG,
        "url": f"{RELEASES}/tag/{TAG}",
        "publishedAt": "2099-01-01T00:03:04Z",
        "body": f"Books built from opensiddur-projects abc123.\n\n{body}\n",
        "assets": assets,
    }


class TestBookEntries(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.settings = Path(self._tmp.name)

    def _write(self, name: str, text: str):
        path = self.settings / f"{name}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_title_and_folded_description(self):
        self._write("synthetic-book-2099-he/annual", (
            "description: >\n"
            "  A synthetic book, folded\n"
            "  over two lines.\n"
            "book:\n"
            "  project: synthetic-book-2099-he\n"
            "  file_name: index.xml\n"
            "  title: Synthetic Book\n"
        ))
        self.assertEqual(book_entries(self.settings), [BookEntry(
            "synthetic-book-2099-he/annual", "Synthetic Book",
            "A synthetic book, folded over two lines.")])

    def test_name_when_there_is_no_title_or_description(self):
        self._write("a/one", "book:\n  project: a\n  file_name: index.xml\n")
        self.assertEqual(book_entries(self.settings), [BookEntry("a/one", "a/one", None)])

    def test_unknown_keys_and_unreadable_files(self):
        self._write("a/one", "a_key_from_the_future: 1\ndescription: Still listed.\n")
        self._write("b/two", "description: [unclosed\n")
        self._write("c/three", "- not a mapping\n")
        self.assertEqual(book_entries(self.settings), [
            BookEntry("a/one", "a/one", "Still listed."),
            BookEntry("b/two", "b/two", None),
            BookEntry("c/three", "c/three", None),
        ])

    def test_name_order(self):
        self._write("b/one", "{}\n")
        self._write("a/two", "{}\n")
        self.assertEqual([b.name for b in book_entries(self.settings)], ["a/two", "b/one"])


class TestRenderDownloads(unittest.TestCase):
    BOOKS = [
        BookEntry("synthetic-book-2099-he/annual", "Synthetic Book", "Both forms."),
        BookEntry("e_book/only", "Electronic Only"),
        BookEntry("failed/book", "A Failed Book", "Nothing attached."),
    ]

    def test_sections(self):
        text = render_downloads(release([
            asset(f"synthetic-book-2099-he-annual-{TAG}.pdf", 3 * 1024 * 1024),
            asset(f"synthetic-book-2099-he-annual-{TAG}.html", 1536),
            asset(f"e_book-only-{TAG}.html", 100),
        ]), self.BOOKS)
        self.assertEqual(text, f"""\
# Downloads

Books from the opensiddur-projects book release [{TAG}]({RELEASES}/tag/{TAG}), published 2099-01-01, \
built with opensiddur-processor v9.8.7. Each book release rewrites this file. Earlier releases are \
on the [releases page]({RELEASES}).

## Synthetic Book

Both forms.

- Electronic book: [synthetic-book-2099-he-annual-{TAG}.html]({RELEASES}/download/{TAG}/synthetic-book-2099-he-annual-{TAG}.html) (1.5 KB)
- Printed book: [synthetic-book-2099-he-annual-{TAG}.pdf]({RELEASES}/download/{TAG}/synthetic-book-2099-he-annual-{TAG}.pdf) (3.0 MB)

## Electronic Only

- Electronic book: [e_book-only-{TAG}.html]({RELEASES}/download/{TAG}/e_book-only-{TAG}.html) (100 bytes)

## Not in this release

- A Failed Book (failed/book)
""")

    def test_other_files(self):
        text = render_downloads(release([
            asset("z-unknown.pdf"), asset(f"e_book-only-{TAG}.html"), asset("a-unknown.txt"),
        ]), self.BOOKS[1:2])
        self.assertTrue(text.endswith(
            "## Other files\n\n"
            f"- [a-unknown.txt]({RELEASES}/download/{TAG}/a-unknown.txt) (2.0 KB)\n"
            f"- [z-unknown.pdf]({RELEASES}/download/{TAG}/z-unknown.pdf) (2.0 KB)\n"))

    def test_an_asset_of_another_tag_is_not_the_book(self):
        text = render_downloads(release([asset("e_book-only-v20981201.html")]), self.BOOKS[1:2])
        self.assertIn("## Not in this release\n\n- Electronic Only (e_book/only)\n", text)
        self.assertIn("## Other files", text)

    def test_without_the_built_with_line(self):
        text = render_downloads(release([], body="Something else."), [])
        self.assertIn("published 2099-01-01. Each book release", text)
        self.assertNotIn("built with", text)

    def test_no_assets_and_no_books(self):
        text = render_downloads(release([]), [])
        self.assertNotIn("##", text)


class TestHumanSize(unittest.TestCase):
    def test_sizes(self):
        for size, expected in [
            (0, "0 bytes"), (1023, "1023 bytes"), (1024, "1.0 KB"), (1024 * 1024 - 1, "1.0 MB"),
            (5 * 1024 * 1024 + 512 * 1024, "5.5 MB"), (3 * 1024 ** 3, "3.0 GB"),
        ]:
            with self.subTest(size=size):
                self.assertEqual(human_size(size), expected)


class TestMain(unittest.TestCase):
    def test_writes_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "settings" / "e_book").mkdir(parents=True)
            (tmp / "settings" / "e_book" / "only.yaml").write_text(
                "book:\n  project: e_book\n  file_name: index.xml\n  title: Electronic Only\n")
            (tmp / "release.json").write_text(json.dumps(release([asset(f"e_book-only-{TAG}.html")])))
            output = tmp / "DOWNLOADS.md"
            self.assertEqual(main([str(tmp / "release.json"), "--settings-directory",
                                   str(tmp / "settings"), "--output", str(output)]), 0)
            self.assertIn("## Electronic Only", output.read_text())


if __name__ == "__main__":
    unittest.main()
