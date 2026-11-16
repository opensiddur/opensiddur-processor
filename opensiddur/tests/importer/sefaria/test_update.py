import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from opensiddur.importer.sefaria.update import classify, committed_manifest, update

from .support import WORK, write_work_dir


def manifest(directory: Path) -> dict:
    return json.loads((directory / "manifest.json").read_text())


class TestClassify(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.before = manifest(write_work_dir(Path(self.tmp.name) / "w"))

    def test_unchanged(self):
        changes = classify("w", self.before, copy.deepcopy(self.before))
        self.assertFalse(changes.changed)
        self.assertEqual(len(changes.unchanged), 3)

    def test_each_class(self):
        after = copy.deepcopy(self.before)
        after["leaves"]["Blessings"]["he"] = "different"
        after["leaves"]["Morning / Amidah"]["en_segments"] += 1
        after["leaves"]["New leaf"] = after["leaves"].pop("Morning / Upon Arising")
        after["files"]["en.json"]["license"] = "CC-BY-SA"
        changes = classify("w", self.before, after)
        self.assertEqual(changes.text_changed, ["Blessings"])
        self.assertEqual(changes.resegmented, ["Morning / Amidah"])
        self.assertEqual(changes.added, ["New leaf"])
        self.assertEqual(changes.removed, ["Morning / Upon Arising"])
        self.assertEqual(changes.metadata, ["en.json license: 'CC-BY' -> 'CC-BY-SA'"])
        self.assertTrue(changes.needs_review)

    def test_text_change_alone_needs_no_review(self):
        after = copy.deepcopy(self.before)
        after["leaves"]["Blessings"]["en"] = "different"
        changes = classify("w", self.before, after)
        self.assertTrue(changes.changed)
        self.assertFalse(changes.needs_review)


class TestCommittedManifest(unittest.TestCase):
    def test_reads_the_committed_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            directory = write_work_dir(repo / "w")
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.org",
                            "commit", "-q", "-m", "x"], check=True)
            committed = manifest(directory)
            (directory / "manifest.json").write_text("{}")
            self.assertEqual(committed_manifest(directory), committed)

    def test_none_outside_a_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(committed_manifest(Path(tmp)), {})


class TestUpdate(unittest.TestCase):
    def test_reports_without_converting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_work_dir(root / "sefaria" / WORK.key)
            changes, path = update([WORK], sourcetexts_root=root, fetch=False, convert=False,
                                   output_directory=root / "out")
            self.assertFalse(changes[0].changed)
            self.assertIn("No leaf changed.", path.read_text())


if __name__ == "__main__":
    unittest.main()
