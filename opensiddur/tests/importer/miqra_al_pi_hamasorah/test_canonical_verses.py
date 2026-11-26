"""Tests for splitting MAM's verses onto the canonical verse division.

The fixtures are synthetic: a miniature ``miqra:book`` carrying just enough structure to
exercise each case. They deliberately do not read MAM's files, so a change to the source
cannot turn these into failures.
"""

import unittest

from lxml import etree

from opensiddur.importer.miqra_al_pi_hamasorah.canonical_verses import (
    CanonicalVerseError,
    annotate_canonical_verses,
)

MIQRA_NS = "urn:x-opensiddur:miqra:intermediate"
Q = f"{{{MIQRA_NS}}}"


def dual_accent(tachton: str, elyon: str) -> str:
    """A span carried with both cantillations, as ``{{מ:כפול}}`` parses to."""
    return (
        "<miqra:dual-accent>"
        f"<miqra:merged>{tachton}</miqra:merged>"
        f'<miqra:strand role="א">{tachton}</miqra:strand>'
        f'<miqra:strand role="ב">{elyon}</miqra:strand>'
        "</miqra:dual-accent>"
    )


def book(*rows: str, file_name: str = "exodus") -> str:
    joined = "\n".join(rows)
    return (
        f'<miqra:book xmlns:miqra="{MIQRA_NS}" '
        f'xmlns:mw="urn:x-opensiddur:mw:intermediate" fileName="{file_name}">'
        f"{joined}</miqra:book>"
    )


def row(chapter: int, verse: int, text: str) -> str:
    return (
        f'<miqra:row chapter="{chapter}" verse="{verse}">'
        f"<miqra:nav/><miqra:scaffold/><miqra:text>{text}</miqra:text>"
        f"</miqra:row>"
    )


def rows_of(annotated: str) -> list[dict]:
    root = etree.fromstring(annotated.encode("utf-8"))
    return [
        {
            "chapter": int(r.get("chapter")),
            "verse": int(r.get("verse")),
            "edition_verse": int(r.get("editionVerse")),
            "first": r.get("editionVerseStart") == "true",
            "text": "".join(r.find(f"{Q}text").itertext()),
        }
        for r in root.findall(f"{Q}row")
    ]


class TestUndivergentChapters(unittest.TestCase):
    def test_rows_pass_through_with_their_own_numbering(self):
        annotated = rows_of(annotate_canonical_verses(
            book(row(1, 1, "בְּרֵאשִׁית׃"), row(1, 2, "וְהָאָרֶץ׃"), file_name="genesis"),
            "genesis",
        ))
        self.assertEqual([(r["chapter"], r["verse"]) for r in annotated], [(1, 1), (1, 2)])
        self.assertTrue(all(r["first"] for r in annotated))

    def test_edition_verse_is_recorded_even_when_it_matches(self):
        annotated = rows_of(annotate_canonical_verses(
            book(row(1, 1, "בְּרֵאשִׁית׃"), file_name="genesis"), "genesis"))
        self.assertEqual(annotated[0]["edition_verse"], 1)


class TestDecalogueSplit(unittest.TestCase):
    """MAM's Exodus 20:12 is the four short commandments; canonically they are 13-16."""

    def build(self):
        # The elyon strand ends each commandment; MAM's own (tachton) reading runs them on.
        text = (
            dual_accent("לֹא תִרְצָח", "לֹא תִּרְצָֽח׃")
            + dual_accent("לֹא תִנְאָף", "לֹא תִּנְאָֽף׃")
            + dual_accent("לֹא תִגְנֹב", "לֹא תִּגְנֹֽב׃")
            + "לֹא תַעֲנֶה׃"
        )
        return rows_of(annotate_canonical_verses(book(row(20, 12, text)), "exodus"))

    def test_one_edition_verse_becomes_four_canonical_verses(self):
        self.assertEqual([r["verse"] for r in self.build()], [13, 14, 15, 16])

    def test_every_segment_records_the_same_edition_verse(self):
        self.assertEqual({r["edition_verse"] for r in self.build()}, {12})

    def test_only_the_first_segment_opens_the_edition_verse(self):
        self.assertEqual([r["first"] for r in self.build()], [True, False, False, False])

    def test_the_text_is_partitioned_not_duplicated(self):
        segments = self.build()
        self.assertIn("תִרְצָח", segments[0]["text"])
        self.assertNotIn("תִנְאָף", segments[0]["text"])
        self.assertIn("תַעֲנֶה", segments[3]["text"])

    def test_anokhi_and_lo_yihyeh_split_into_two(self):
        text = dual_accent("אָנֹכִי", "אָנֹכִֽי׃") + "לֹא יִהְיֶה לְךָ׃"
        annotated = rows_of(annotate_canonical_verses(book(row(20, 2, text)), "exodus"))
        self.assertEqual([r["verse"] for r in annotated], [2, 3])

    def test_the_rest_of_the_chapter_is_renumbered(self):
        annotated = rows_of(annotate_canonical_verses(book(row(20, 22, "וְלֹא תַעֲלֶה׃")), "exodus"))
        self.assertEqual(annotated[0]["verse"], 26)
        self.assertEqual(annotated[0]["edition_verse"], 22)


class TestMidVerseParashahIsNotAVerseBoundary(unittest.TestCase):
    """MAM's Exodus 20:13 is one canonical verse (17) despite a break inside it."""

    def test_a_break_inside_a_verse_does_not_split_it(self):
        text = (
            "לֹא תַחְמֹד בֵּית רֵעֶךָ"
            + '<miqra:parashah type="close" midVerse="true"/>'
            + "לֹא תַחְמֹד אֵשֶׁת רֵעֶךָ׃"
        )
        annotated = rows_of(annotate_canonical_verses(book(row(20, 13, text)), "exodus"))
        self.assertEqual(len(annotated), 1)
        self.assertEqual(annotated[0]["verse"], 17)


class TestCrossChapterMerge(unittest.TestCase):
    """MAM's Numbers 26:1 carries canonical 25:19 ahead of canonical 26:1."""

    def test_split_at_a_mid_verse_parashah_wrapped_in_a_variant(self):
        text = (
            "וַיְהִי אַחֲרֵי הַמַּגֵּפָה"
            + "<miqra:variant><miqra:display>"
            + '<miqra:parashah type="open" midVerse="true"/>'
            + "</miqra:display></miqra:variant>"
            + "וַיֹּאמֶר יְהוָה אֶל מֹשֶׁה׃"
        )
        annotated = rows_of(annotate_canonical_verses(
            book(row(26, 1, text), file_name="numbers"), "numbers"))
        self.assertEqual(
            [(r["chapter"], r["verse"]) for r in annotated], [(25, 19), (26, 1)]
        )
        self.assertEqual([r["first"] for r in annotated], [True, False])


class TestChapterBoundaryShift(unittest.TestCase):
    """MAM's Jeremiah 30:25 is canonical 31:1, and 31 is renumbered throughout."""

    def test_absorbed_verse_moves_to_the_next_chapter(self):
        annotated = rows_of(annotate_canonical_verses(
            book(row(30, 25, "בָּעֵת הַהִיא׃"), file_name="jeremiah"), "jeremiah"))
        self.assertEqual((annotated[0]["chapter"], annotated[0]["verse"]), (31, 1))

    def test_following_chapter_is_shifted(self):
        annotated = rows_of(annotate_canonical_verses(
            book(row(31, 1, "כֹּה אָמַר יְהוָה׃"), file_name="jeremiah"), "jeremiah"))
        self.assertEqual((annotated[0]["chapter"], annotated[0]["verse"]), (31, 2))


class TestOmittedVerses(unittest.TestCase):
    """Joshua 21:36-37 are absent from MAM, so its 21:36 is canonical 21:38."""

    def test_numbering_resumes_past_the_omission(self):
        annotated = rows_of(annotate_canonical_verses(
            book(row(21, 36, "וּמִמַּטֵּה גָד׃"), file_name="joshua"), "joshua"))
        self.assertEqual(annotated[0]["verse"], 38)


class TestSourceAndTableMustAgree(unittest.TestCase):
    def test_missing_boundaries_are_an_error(self):
        # Recorded as four canonical verses, but the source offers no interior boundary.
        with self.assertRaises(CanonicalVerseError) as caught:
            annotate_canonical_verses(book(row(20, 12, "לֹא תִרְצָח׃")), "exodus")
        self.assertIn("interior boundaries", str(caught.exception))

    def test_a_verse_outside_the_table_is_an_error(self):
        with self.assertRaises(CanonicalVerseError):
            annotate_canonical_verses(book(row(25, 19, "וַיְהִי׃"), file_name="numbers"), "numbers")

    def test_non_numeric_rows_are_left_alone(self):
        annotated = annotate_canonical_verses(
            book('<miqra:row chapter="" verse=""><miqra:text/></miqra:row>', file_name="genesis"),
            "genesis",
        )
        root = etree.fromstring(annotated.encode("utf-8"))
        self.assertEqual(len(root.findall(f"{Q}row")), 1)


if __name__ == "__main__":
    unittest.main()
