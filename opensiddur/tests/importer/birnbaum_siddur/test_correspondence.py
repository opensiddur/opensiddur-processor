"""Tests for the Birnbaum page correspondence table.

The book here is fifteen synthetic leaves built in a temporary sourcetexts tree. It is
deliberately shaped to contain one of everything the real book contains and nothing
else: all four spellings of the running-header template, a Roman-numbered front
matter, a run of Hebrew pages with no facing English, a transcribed page number that
goes backwards, and one page for each way the English text can be sourced.
"""

import json
import tempfile
import unittest
from pathlib import Path

from opensiddur.importer.birnbaum_siddur.correspondence import (
    MATTER_BACK,
    MATTER_BODY,
    MATTER_FRONT,
    SIDE_ENGLISH,
    SIDE_HEBREW,
    SIDE_OTHER,
    SOURCE_EN_WIKISOURCE,
    SOURCE_IA_OCR,
    SOURCE_IA_OCR_UNSEGMENTED,
    SOURCE_NONE,
    _classify_matter,
    _ranges,
    build_correspondence,
    classify_side,
    load_correspondence,
    main,
    parse_running_header,
    resolve_page_text,
    save_correspondence,
)
from opensiddur.importer.util.pages import (
    birnbaum_siddur_correspondence_path,
    birnbaum_siddur_en_data_directory,
    birnbaum_siddur_en_text_directory,
    birnbaum_siddur_ia_derivatives_directory,
    birnbaum_siddur_ia_ocr_directory,
    birnbaum_siddur_text_directory,
)

IWPAGE = "{{iwpage|en}}"


def header(*arguments: str) -> str:
    return "{{כותרת רצה|" + "|".join(arguments) + "}}"


def english_page(level: int, body: str) -> str:
    return (
        f'<noinclude><pagequality level="{level}" user="X" /></noinclude>'
        f"{body}<noinclude><references/></noinclude>"
    )


# scan -> (hebrew wikitext, Archive's detected printed number)
#
# Numbers run i, -, iii for the front matter and 1..12 through the body, with the
# Hebrew pages stating their own and the English pages known only to the Archive.
BOOK = {
    1: (IWPAGE, "i"),
    2: ("a Hebrew title page with no markers at all", ""),
    3: (IWPAGE, "iii"),
    # Slot-1 form, the one that opens a section. Printed page 1 starts the body.
    4: (header("", "1", ""), "1"),
    5: (IWPAGE, "2"),
    # Slot-0 form with three arguments: the commonest shape.
    6: (header("3", "Section A", ""), "3"),
    7: (IWPAGE, "4"),
    # Two-argument form.
    8: (header("5", "Section A"), "5"),
    9: (IWPAGE, "6"),
    # Slot-2 form: section first, number last.
    10: (header("", "Section B", "7"), "7"),
    11: (header("", "Section B", "8"), "8"),
    12: (header("", "Section B", "9"), "9"),
    13: (IWPAGE, "10"),
    # A transcribed number copied from an earlier page and never updated: it goes
    # backwards from 10, and the Archive reads 11.
    14: (header("", "3", ""), "11"),
    15: (IWPAGE, "12"),
}

# scan -> English Wikisource wikitext, for the pages that have one.
ENGLISH = {
    5: english_page(4, "proofread English"),
    7: english_page(1, "problematic English"),
    9: english_page(4, "   "),
}

# Pages whose OCR came out blank.
BLANK_OCR = {15}


class CorrespondenceTestCase(unittest.TestCase):
    """Builds the synthetic book on disk, then the table over it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

        text_dir = birnbaum_siddur_text_directory(self.root)
        en_dir = birnbaum_siddur_en_text_directory(self.root)
        ocr_dir = birnbaum_siddur_ia_ocr_directory(self.root)
        derivatives = birnbaum_siddur_ia_derivatives_directory(self.root)
        for directory in (text_dir, en_dir, ocr_dir, derivatives):
            directory.mkdir(parents=True, exist_ok=True)

        for scan_page, (wikitext, _) in BOOK.items():
            (text_dir / f"{scan_page:03d}.txt").write_text(wikitext, encoding="utf-8")
            (ocr_dir / f"{scan_page:03d}.txt").write_text(
                "" if scan_page in BLANK_OCR else f"OCR of leaf {scan_page - 1}\n",
                encoding="utf-8",
            )

        for scan_page, wikitext in ENGLISH.items():
            (en_dir / f"{scan_page:03d}.txt").write_text(wikitext, encoding="utf-8")

        (birnbaum_siddur_en_data_directory(self.root) / "manifest.json").write_text(
            json.dumps(
                {"pages": {f"{n:03d}": {"revid": 900 + n} for n in ENGLISH}}
            ),
            encoding="utf-8",
        )

        (derivatives / "Synthetic Book_page_numbers.json").write_text(
            json.dumps(
                {
                    "pages": [
                        {
                            "leafNum": scan_page - 1,
                            "pageNumber": number,
                            "confidence": 90 if number else None,
                        }
                        for scan_page, (_, number) in BOOK.items()
                    ]
                }
            ),
            encoding="utf-8",
        )

        self.correspondence = build_correspondence(self.root)
        self.by_scan = {r["scan_page"]: r for r in self.correspondence["pages"]}


class RunningHeaderTestCase(unittest.TestCase):
    """The template is used in four shapes, and the number moves between them."""

    def test_number_first_with_three_arguments(self):
        self.assertEqual(
            parse_running_header(header("75", "תפלת שחרית", "")), ("75", "תפלת שחרית")
        )

    def test_two_arguments_only(self):
        self.assertEqual(
            parse_running_header(header("13", "ברכות השחר")), ("13", "ברכות השחר")
        )

    def test_number_second_with_no_section(self):
        self.assertEqual(parse_running_header(header("", "3", "")), ("3", None))

    def test_number_third(self):
        self.assertEqual(
            parse_running_header(header("", "הושענות", "681")), ("681", "הושענות")
        )

    def test_a_positional_reader_would_lose_most_of_these(self):
        # 44 of the 405 real pages put the number somewhere other than slot 0. If
        # this ever starts passing by reading slot 0, those pages go silently
        # missing -- and with them the evidence for the printed pagination.
        for shape in (header("", "3", ""), header("", "הושענות", "681")):
            first_argument = shape.split("|")[1]
            self.assertNotEqual(parse_running_header(shape)[0], first_argument)

    def test_a_page_without_a_header_reports_nothing(self):
        self.assertEqual(parse_running_header(IWPAGE), (None, None))


class SideTestCase(unittest.TestCase):
    def test_side_comes_from_the_markers(self):
        self.assertEqual(classify_side(header("75", "x", "")), SIDE_HEBREW)
        self.assertEqual(classify_side(IWPAGE), SIDE_ENGLISH)
        self.assertEqual(classify_side("neither marker"), SIDE_OTHER)


class SideAndMatterTestCase(CorrespondenceTestCase):
    def test_every_leaf_is_classified(self):
        counts = self.correspondence["counts"]
        self.assertEqual(counts["total"], len(BOOK))
        # Hebrew 4, 6, 8, 10, 11, 12, 14; English 1, 3, 5, 7, 9, 13, 15; and the
        # unmarked title page at 2.
        self.assertEqual(counts[SIDE_HEBREW], 7)
        self.assertEqual(counts[SIDE_ENGLISH], 7)
        self.assertEqual(counts[SIDE_OTHER], 1)
        self.assertEqual(
            counts[SIDE_HEBREW] + counts[SIDE_ENGLISH] + counts[SIDE_OTHER],
            counts["total"],
        )

    def test_parity_is_not_used_to_decide_the_side(self):
        # Scan 11 is odd, which in the real book usually means English, but it
        # carries a running header and so is Hebrew. A parity rule would put every
        # page after the Hebrew-only run on the wrong side.
        self.assertEqual(self.by_scan[11]["side"], SIDE_HEBREW)
        self.assertEqual(self.by_scan[10]["side"], SIDE_HEBREW)

    def test_matter_boundaries_are_found_not_assumed(self):
        # Front matter is everything before the Hebrew page printed as page 1.
        self.assertEqual(
            [n for n, r in self.by_scan.items() if r["matter"] == MATTER_FRONT],
            [1, 2, 3],
        )
        self.assertEqual(self.by_scan[4]["matter"], MATTER_BODY)
        self.assertEqual(self.by_scan[14]["matter"], MATTER_BODY)
        self.assertEqual(self.by_scan[15]["matter"], MATTER_BODY)

    def test_unpaired_leaves_after_final_translation_are_back_matter(self):
        records = [dict(r) for r in self.correspondence["pages"]]
        records.append(dict(scan_page=16, side=SIDE_OTHER))
        _classify_matter(records)
        self.assertEqual(records[-2]["matter"], MATTER_BODY)
        self.assertEqual(records[-1]["matter"], MATTER_BACK)

    def test_english_front_matter_is_counted(self):
        # This is the material the Hebrew transcription omits entirely.
        self.assertEqual(self.correspondence["counts"]["front_matter_english"], 2)

    def test_the_leaf_offset_holds_for_every_page(self):
        for record in self.correspondence["pages"]:
            self.assertEqual(record["ia_leaf"], record["scan_page"] - 1)

    def test_every_page_carries_a_facsimile_url(self):
        record = self.by_scan[4]
        self.assertIn(f"n{record['ia_leaf']}", record["facs"])


class PrintedPageTestCase(CorrespondenceTestCase):
    def test_the_transcribed_number_is_preferred(self):
        record = self.by_scan[6]
        self.assertEqual(record["printed_page"], "3")
        self.assertEqual(record["printed_page_source"], "wikisource_header")

    def test_the_archive_fills_in_where_nothing_was_transcribed(self):
        record = self.by_scan[5]
        self.assertEqual(record["printed_page"], "2")
        self.assertEqual(record["printed_page_source"], "ia_page_numbers")

    def test_roman_front_matter_is_kept_as_text(self):
        # Coercing page numbers to integers would lose the front matter, which is
        # exactly where the English-only material lives.
        self.assertEqual(self.by_scan[1]["printed_page"], "i")
        self.assertEqual(self.by_scan[3]["printed_page"], "iii")

    def test_a_backwards_number_is_corrected_from_the_archive(self):
        record = self.by_scan[14]
        self.assertEqual(record["printed_page"], "11")
        self.assertEqual(record["printed_page_source"], "ia_page_numbers_corrected")
        # Both readings survive, so the correction can always be audited.
        self.assertEqual(record["printed_page_wikisource"], "3")
        self.assertEqual(record["printed_page_ia"], "11")
        self.assertTrue(record["printed_page_conflict"])

    def test_the_correction_is_reported(self):
        conflicts = self.correspondence["conflicts"]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["scan_page"], 14)
        self.assertEqual(conflicts[0]["resolution"], "corrected to 11")

    def test_nothing_else_is_reported_as_a_conflict(self):
        # The tripwire only works if it is quiet when the data is good.
        self.assertEqual(
            [c["scan_page"] for c in self.correspondence["conflicts"]], [14]
        )

    def test_an_unrepairable_number_is_left_alone_and_flagged(self):
        # With the Archive offering nothing better, inventing a number would be
        # worse than surfacing the problem.
        numbers = birnbaum_siddur_ia_derivatives_directory(self.root) / "Synthetic Book_page_numbers.json"
        payload = json.loads(numbers.read_text(encoding="utf-8"))
        for entry in payload["pages"]:
            if entry["leafNum"] == 13:
                entry["pageNumber"] = ""
        numbers.write_text(json.dumps(payload), encoding="utf-8")

        rebuilt = build_correspondence(self.root)
        record = next(r for r in rebuilt["pages"] if r["scan_page"] == 14)

        self.assertEqual(record["printed_page"], "3")
        self.assertEqual(rebuilt["conflicts"][0]["resolution"], "unresolved")


class FacingPageTestCase(CorrespondenceTestCase):
    def test_hebrew_pairs_with_the_english_leaf_that_follows(self):
        self.assertEqual(self.by_scan[6]["facing_scan_page"], 7)
        self.assertEqual(self.by_scan[7]["facing_scan_page"], 6)

    def test_a_hebrew_only_run_is_left_unpaired(self):
        # Pairing these to the next English page would attach them to a different
        # section entirely.
        self.assertEqual(
            [entry["scan_page"] for entry in self.correspondence["unpaired"]], [10, 11]
        )
        self.assertIsNone(self.by_scan[10]["facing_scan_page"])
        self.assertIsNone(self.by_scan[11]["facing_scan_page"])

    def test_the_last_page_of_a_run_still_pairs(self):
        # Scan 12 ends the Hebrew-only run but is followed by English, so it pairs.
        self.assertEqual(self.by_scan[12]["facing_scan_page"], 13)

    def test_pairing_uses_the_corrected_page_number(self):
        # Scan 14's transcribed 3 would not be one less than 15's 12; its corrected
        # 11 is. Without the correction this pair would be lost.
        self.assertEqual(self.by_scan[14]["facing_scan_page"], 15)


class TextSourceTestCase(CorrespondenceTestCase):
    def test_a_proofread_english_page_wins(self):
        self.assertEqual(self.by_scan[5]["text_source"], SOURCE_EN_WIKISOURCE)

    def test_a_problematic_english_page_falls_back_to_ocr(self):
        self.assertEqual(self.by_scan[7]["text_source"], SOURCE_IA_OCR)
        # The page is still recorded, so the fallback can be reviewed.
        self.assertEqual(self.by_scan[7]["en"]["quality"], 1)

    def test_a_validated_but_empty_english_page_falls_back_to_ocr(self):
        # Roughly half the pages that exist on en.wikisource are empty shells.
        self.assertEqual(self.by_scan[9]["text_source"], SOURCE_IA_OCR)
        self.assertTrue(self.by_scan[9]["en"]["empty"])

    def test_an_english_page_with_no_transcription_uses_ocr(self):
        self.assertIsNone(self.by_scan[13]["en"])
        self.assertEqual(self.by_scan[13]["text_source"], SOURCE_IA_OCR)

    def test_a_hebrew_page_is_marked_unsegmented(self):
        # Birnbaum's English footnotes are on it, tangled with Hebrew that OCR read
        # as Latin. Calling this plain OCR would invite a later stage to quote it.
        self.assertEqual(self.by_scan[6]["text_source"], SOURCE_IA_OCR_UNSEGMENTED)

    def test_a_page_with_no_text_anywhere_reports_none(self):
        self.assertEqual(self.by_scan[15]["text_source"], SOURCE_NONE)

    def test_the_usable_count_is_reported(self):
        self.assertEqual(self.correspondence["counts"]["en_wikisource_used"], 1)
        self.assertEqual(self.correspondence["counts"]["en_wikisource_present"], 3)


class ResolveTextTestCase(CorrespondenceTestCase):
    def setUp(self):
        super().setUp()
        save_correspondence(self.correspondence, self.root)

    def test_proofread_text_comes_back_without_its_wrappers(self):
        text, source = resolve_page_text(5, self.root)
        self.assertEqual(source, SOURCE_EN_WIKISOURCE)
        self.assertEqual(text, "proofread English")

    def test_ocr_text_comes_back_for_a_page_without_a_transcription(self):
        text, source = resolve_page_text(13, self.root)
        self.assertEqual(source, SOURCE_IA_OCR)
        self.assertIn("leaf 12", text)

    def test_a_page_with_nothing_returns_nothing(self):
        self.assertEqual(resolve_page_text(15, self.root), (None, SOURCE_NONE))

    def test_an_unknown_page_returns_nothing(self):
        self.assertEqual(resolve_page_text(999, self.root), (None, SOURCE_NONE))

    def test_rebuilding_an_unchanged_table_leaves_the_file_alone(self):
        path = birnbaum_siddur_correspondence_path(self.root)
        before = path.read_text(encoding="utf-8")
        mtime = path.stat().st_mtime_ns

        # A fresh build carries a new generated_at, which is the only difference.
        save_correspondence(build_correspondence(self.root), self.root)

        self.assertEqual(path.read_text(encoding="utf-8"), before)
        self.assertEqual(path.stat().st_mtime_ns, mtime)

    def test_a_real_change_is_written(self):
        path = birnbaum_siddur_correspondence_path(self.root)
        before = path.read_text(encoding="utf-8")

        english = birnbaum_siddur_en_text_directory(self.root) / "013.txt"
        english.write_text(english_page(4, "newly proofread"), encoding="utf-8")
        save_correspondence(build_correspondence(self.root), self.root)

        self.assertNotEqual(path.read_text(encoding="utf-8"), before)

    def test_the_table_round_trips(self):
        self.assertEqual(
            load_correspondence(self.root)["counts"], self.correspondence["counts"]
        )


class RangesTestCase(unittest.TestCase):
    def test_consecutive_pages_collapse(self):
        self.assertEqual(_ranges([704, 705, 706]), "704-706")

    def test_gaps_are_not_bridged(self):
        # A step of two must not collapse: "100-102" would claim 101 as well.
        self.assertEqual(_ranges([100, 102]), "100, 102")

    def test_mixed_runs(self):
        self.assertEqual(_ranges([584, 585, 704, 705]), "584-585, 704-705")

    def test_empty(self):
        self.assertEqual(_ranges([]), "")


class MainTestCase(CorrespondenceTestCase):
    def test_the_table_is_written(self):
        self.assertEqual(main(["--sourcetexts-root", str(self.root)]), 0)
        self.assertTrue(birnbaum_siddur_correspondence_path(self.root).is_file())

    def test_dry_run_writes_nothing(self):
        self.assertEqual(
            main(["--sourcetexts-root", str(self.root), "--dry-run"]), 0
        )
        self.assertFalse(birnbaum_siddur_correspondence_path(self.root).exists())

    def test_check_passes_when_every_number_was_settled(self):
        # The seeded conflict is corrected, not unresolved, so --check is happy.
        self.assertEqual(main(["--sourcetexts-root", str(self.root), "--check"]), 0)
        self.assertFalse(birnbaum_siddur_correspondence_path(self.root).exists())

    def test_check_fails_on_an_unresolved_number(self):
        numbers = birnbaum_siddur_ia_derivatives_directory(self.root) / "Synthetic Book_page_numbers.json"
        payload = json.loads(numbers.read_text(encoding="utf-8"))
        for entry in payload["pages"]:
            if entry["leafNum"] == 13:
                entry["pageNumber"] = ""
        numbers.write_text(json.dumps(payload), encoding="utf-8")

        self.assertEqual(main(["--sourcetexts-root", str(self.root), "--check"]), 1)

    def test_missing_hebrew_pages_are_reported_not_crashed_on(self):
        empty = self.root / "empty"
        self.assertEqual(main(["--sourcetexts-root", str(empty)]), 1)


if __name__ == "__main__":
    unittest.main()
