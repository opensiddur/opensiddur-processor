import copy
import dataclasses
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import yaml

from opensiddur.importer.sefaria.align import AlignmentError, LeafDecision
from opensiddur.importer.sefaria.corrections import CorrectionError, SegmentCorrection
from opensiddur.importer.sefaria.update import classify, committed_manifest, main, update

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

    def correction(self, lang="en", segment=2):
        return SegmentCorrection("Blessings", lang, segment, "Adonoy", "God")

    def test_text_change_under_a_correction_needs_review(self):
        after = copy.deepcopy(self.before)
        after["leaves"]["Blessings"]["en"] = "different"
        changes = classify("w", self.before, after, corrections=[self.correction()])
        self.assertEqual(changes.text_changed, [])
        self.assertEqual(changes.curated, ["Blessings"])
        self.assertIn("misprint correction (en 2", changes.notes["Blessings"])
        self.assertTrue(changes.needs_review)

    def test_change_to_the_other_version_leaves_a_correction_alone(self):
        after = copy.deepcopy(self.before)
        after["leaves"]["Blessings"]["he"] = "different"
        changes = classify("w", self.before, after, corrections=[self.correction("en")])
        self.assertEqual(changes.text_changed, ["Blessings"])
        self.assertFalse(changes.needs_review)

    def decision(self, leaf: dict) -> LeafDecision:
        return LeafDecision(leaf["he"], leaf["en"], frozenset(), frozenset({3}))

    def test_text_change_under_an_alignment_decision_needs_review(self):
        decisions = {"Blessings": self.decision(self.before["leaves"]["Blessings"])}
        after = copy.deepcopy(self.before)
        after["leaves"]["Blessings"]["he"] = "different"
        changes = classify("w", self.before, after, decisions=decisions)
        self.assertEqual(changes.curated, ["Blessings"])
        self.assertEqual(changes.notes["Blessings"], "alignment decision")
        self.assertTrue(changes.needs_review)

    def test_decision_already_made_for_the_new_text_needs_no_review(self):
        after = copy.deepcopy(self.before)
        after["leaves"]["Blessings"]["he"] = "different"
        decisions = {"Blessings": self.decision(after["leaves"]["Blessings"])}
        changes = classify("w", self.before, after, decisions=decisions)
        self.assertEqual(changes.text_changed, ["Blessings"])
        self.assertFalse(changes.needs_review)

    def test_resegmented_leaf_notes_its_correction(self):
        after = copy.deepcopy(self.before)
        after["leaves"]["Blessings"]["en"] = "different"
        after["leaves"]["Blessings"]["en_segments"] += 1
        changes = classify("w", self.before, after, corrections=[self.correction()])
        self.assertEqual(changes.resegmented, ["Blessings"])
        self.assertEqual(changes.curated, [])
        self.assertIn("misprint correction", changes.notes["Blessings"])


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


CONVERT = "opensiddur.importer.sefaria.convert.convert_work"
CURATED_HEADING = "### Text changed where a misprint correction or alignment decision applies"


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.org",
                    *args], check=True, capture_output=True)


class TestUpdateWithChanges(unittest.TestCase):
    """A committed sourcetexts checkout whose manifest then changes on disk."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.other = dataclasses.replace(WORK, key="other_siddur")
        for work in (WORK, self.other):
            write_work_dir(self.root / "sefaria" / work.key)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        git(self.root, "add", ".")
        git(self.root, "commit", "-q", "-m", "x")
        self.corrections = self.root / "corrections.yaml"
        self.decisions = self.root / "alignment_decisions.yaml"
        self.corrections.write_text("{}\n")
        self.decisions.write_text("{}\n")

    def change_text(self, work, leaf="Blessings", lang="en") -> dict:
        path = self.root / "sefaria" / work.key / "manifest.json"
        data = manifest(path.parent)
        before = copy.deepcopy(data["leaves"][leaf])
        data["leaves"][leaf][lang] = "different"
        path.write_text(json.dumps(data))
        return before

    def run_update(self, works):
        return update(works, sourcetexts_root=self.root, fetch=False, output_directory=self.root / "out",
                      corrections_path=self.corrections, decisions_path=self.decisions)

    def test_correction_is_reported_and_not_converted(self):
        self.corrections.write_text(yaml.safe_dump({WORK.key: [
            {"leaf": "Blessings", "lang": "en", "segment": 2, "sic": "Adonoy", "corr": "God"}]}))
        self.change_text(WORK)
        with mock.patch(CONVERT) as convert:
            changes, path = self.run_update([WORK])
        convert.assert_not_called()
        self.assertTrue(changes[0].failed)
        text = path.read_text()
        self.assertIn(CURATED_HEADING, text)
        self.assertIn("- Blessings (misprint correction (en 2: 'Adonoy'))", text)
        self.assertIn("Not converted: review the changes above first.", text)

    def test_alignment_decision_is_reported_and_not_converted(self):
        before = self.change_text(WORK, lang="he")
        self.decisions.write_text(yaml.safe_dump({WORK.key: {"Blessings": {
            "as_of": {"he": before["he"], "en": before["en"]}, "opens": [3]}}}))
        with mock.patch(CONVERT) as convert:
            changes, path = self.run_update([WORK])
        convert.assert_not_called()
        self.assertEqual(changes[0].curated, ["Blessings"])
        self.assertIn("- Blessings (alignment decision)", path.read_text())

    def test_a_failed_conversion_does_not_stop_the_others(self):
        self.change_text(WORK)
        self.change_text(self.other)
        plan = SimpleNamespace(decisions=SimpleNamespace(decided=[object(), object()]))

        def convert_work(work, **kwargs):
            self.assertEqual(kwargs["corrections_path"], self.corrections)
            if work.key == WORK.key:
                raise CorrectionError("misprint corrections that no longer apply:\nBlessings (en 2)")
            return plan

        with mock.patch(CONVERT, side_effect=convert_work) as convert:
            changes, path = self.run_update([WORK, self.other])
        self.assertEqual(convert.call_count, 2)
        self.assertIn("CorrectionError", changes[0].error)
        self.assertTrue(changes[0].failed)
        self.assertFalse(changes[1].failed)
        text = path.read_text()
        first, second = text.split(f"## {self.other.key}")
        self.assertIn("Not converted:", first)
        self.assertIn("Blessings (en 2)", first)
        self.assertIn("Converted: 2 text URN(s) decided again", second)

    def test_an_alignment_error_is_reported_too(self):
        self.change_text(WORK)
        with mock.patch(CONVERT, side_effect=AlignmentError("Blessings: not a run of trailing rubrics")):
            changes, path = self.run_update([WORK])
        self.assertTrue(changes[0].error.startswith("AlignmentError: "))
        self.assertIn("not a run of trailing rubrics", path.read_text())

    def test_main_exits_non_zero_after_a_failed_conversion(self):
        failed = classify(WORK.key, {}, {})
        failed.error = "AlignmentError: stale"
        with mock.patch("opensiddur.importer.sefaria.update.update",
                        return_value=([failed], self.root / "report.md")), \
                mock.patch("opensiddur.importer.sefaria.update.select_works", return_value=[WORK]), \
                mock.patch("builtins.print"):
            self.assertEqual(main(["--no-download"]), 1)


if __name__ == "__main__":
    unittest.main()
