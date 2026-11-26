"""Tests for the cross-project versification validator.

Each test builds a miniature project tree in a temporary directory, so nothing here depends
on the real Tanakh projects.
"""

import tempfile
import unittest
from pathlib import Path

from opensiddur.common.versification import JPS_PROJECT as JPS
from opensiddur.common.versification import MIQRA_PROJECT as MIQRA
from opensiddur.common.versification import WLC_PROJECT as WLC
from opensiddur.exporter.validate_versification import (
    collect_verse_urns,
    validate_versification,
)

TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
  <tei:text><tei:body><tei:div type="book">{milestones}</tei:div></tei:body></tei:text>
</tei:TEI>
"""


def milestone(book: str, chapter: int, verse: int) -> str:
    return (
        f'<tei:milestone unit="verse" n="{verse}" '
        f'corresp="urn:x-opensiddur:text:bible:{book}/{chapter}/{verse}"/>'
    )


class VersificationTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def write_project(self, project: str, book: str, verses, *, chapter: int = 20):
        directory = self.root / project
        directory.mkdir(parents=True, exist_ok=True)
        body = "".join(milestone(book, chapter, verse) for verse in verses)
        (directory / f"{book}.xml").write_text(TEMPLATE.format(milestones=body), encoding="utf-8")


class TestAgreement(VersificationTestCase):
    def test_projects_that_agree_report_nothing(self):
        for project in (WLC, MIQRA, JPS):
            self.write_project(project, "exodus", range(1, 27))
        report = validate_versification(project_directory=self.root)
        self.assertTrue(report.ok)
        self.assertEqual(report.duplicates, [])
        self.assertEqual(report.missing, [])

    def test_a_book_only_one_project_has_is_not_a_disagreement(self):
        self.write_project(WLC, "exodus", range(1, 27))
        self.write_project(MIQRA, "genesis", range(1, 32), chapter=1)
        self.write_project(JPS, "genesis", range(1, 32), chapter=1)
        report = validate_versification(project_directory=self.root)
        self.assertTrue(report.ok)


class TestDuplicates(VersificationTestCase):
    def test_a_repeated_urn_is_reported(self):
        self.write_project(WLC, "exodus", [1, 2, 2, 3])
        self.write_project(MIQRA, "exodus", [1, 2, 3])
        self.write_project(JPS, "exodus", [1, 2, 3])
        report = validate_versification(project_directory=self.root)
        self.assertFalse(report.ok)
        self.assertEqual(len(report.duplicates), 1)
        duplicate = report.duplicates[0]
        self.assertEqual(duplicate.project, WLC)
        self.assertEqual(duplicate.occurrences, 2)
        self.assertIn("exodus/20/2", duplicate.urn)


class TestCoverage(VersificationTestCase):
    def test_a_project_short_of_the_others_is_reported(self):
        # The Decalogue failure mode: one edition stops four verses early.
        self.write_project(WLC, "exodus", range(1, 27))
        self.write_project(JPS, "exodus", range(1, 27))
        self.write_project(MIQRA, "exodus", range(1, 23))
        report = validate_versification(project_directory=self.root)
        self.assertFalse(report.ok)
        self.assertEqual(len(report.missing), 1)
        missing = report.missing[0]
        self.assertEqual(missing.project, MIQRA)
        self.assertEqual(missing.verses, (23, 24, 25, 26))

    def test_a_documented_absence_is_not_a_failure(self):
        # Joshua 21:36-37 are genuinely absent from MAM.
        verses = [v for v in range(1, 46) if v not in (36, 37)]
        self.write_project(MIQRA, "joshua", verses, chapter=21)
        self.write_project(WLC, "joshua", range(1, 46), chapter=21)
        self.write_project(JPS, "joshua", range(1, 46), chapter=21)
        report = validate_versification(project_directory=self.root)
        self.assertTrue(report.ok, msg=str(report.missing))

    def test_an_undocumented_gap_in_the_same_chapter_still_fails(self):
        verses = [v for v in range(1, 46) if v not in (36, 37, 40)]
        self.write_project(MIQRA, "joshua", verses, chapter=21)
        self.write_project(WLC, "joshua", range(1, 46), chapter=21)
        self.write_project(JPS, "joshua", range(1, 46), chapter=21)
        report = validate_versification(project_directory=self.root)
        self.assertFalse(report.ok)
        self.assertEqual(report.missing[0].verses, (40,))

    def test_a_verse_only_one_project_has_is_that_project_s_defect(self):
        """Zechariah 4's failure mode: verses attributed to the wrong chapter.

        Reporting it as the other two projects "missing" verse 15 would blame two correct
        projects for one project's error, so it is reported against the outlier instead.
        """
        # haggai 1 stands in for zechariah 4, which is on the documented unresolved list and
        # so would be reported there rather than as a live finding.
        self.write_project(JPS, "haggai", range(1, 22), chapter=1)
        self.write_project(WLC, "haggai", range(1, 15), chapter=1)
        self.write_project(MIQRA, "haggai", range(1, 15), chapter=1)
        report = validate_versification(project_directory=self.root)
        self.assertFalse(report.ok)
        self.assertEqual(report.missing, [])
        self.assertEqual(len(report.extra), 1)
        self.assertEqual(report.extra[0].project, JPS)
        self.assertEqual(report.extra[0].verses, tuple(range(15, 22)))


class TestCollectVerseUrns(VersificationTestCase):
    def test_only_verse_urns_are_collected(self):
        directory = self.root / WLC
        directory.mkdir(parents=True)
        body = (
            milestone("exodus", 20, 1)
            + '<tei:milestone unit="chapter" corresp="urn:x-opensiddur:text:bible:exodus/20"/>'
            + '<tei:seg corresp="urn:x-opensiddur:condition:bible:taam-elyon"/>'
        )
        (directory / "exodus.xml").write_text(TEMPLATE.format(milestones=body), encoding="utf-8")
        self.assertEqual(
            collect_verse_urns(WLC, project_directory=self.root),
            {("exodus", 20, 1): 1},
        )

    def test_a_missing_project_is_an_error(self):
        with self.assertRaises(ValueError):
            collect_verse_urns("nope", project_directory=self.root)


if __name__ == "__main__":
    unittest.main()
