import tempfile
import unittest
from pathlib import Path

from opensiddur.importer.sefaria.works import load_works

ENTRY = """
w:
  title: T
  versions: {he: H, en: E}
  projects: {he: p-he, en: p-en}
  title_en: T
  title_he: ת
  rite: R
  licence: L
  publisher: P
  translator: X
  date: 1981
"""


class TestLoadWorks(unittest.TestCase):
    def load(self, extra=""):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "works.yaml"
            path.write_text(ENTRY + extra, encoding="utf-8")
            return load_works(path)["w"]

    def test_defaults(self):
        work = self.load()
        self.assertEqual((work.supplements, work.layout, work.translation_note), ({}, "linear", ""))

    def test_supplements_layout_and_translation_note(self):
        work = self.load("  supplements: {he: Second}\n  layout: paragraph\n  translation_note: >-\n    Based\n    on.\n")
        self.assertEqual((work.supplements, work.layout, work.translation_note), ({"he": "Second"}, "paragraph", "Based on."))

    def test_a_supplement_for_no_language_or_an_unknown_layout_is_an_error(self):
        for extra in ("  supplements: {fr: Second}\n", "  layout: columns\n"):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.load(extra)


if __name__ == "__main__":
    unittest.main()
