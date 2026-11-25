"""Tests for the Miqra intermediate → JLPTEI stylesheet
(``opensiddur/importer/miqra_al_pi_hamasorah/miqra_to_tei.xslt``).

These run the transformation directly over hand-written intermediate XML, so
they exercise the stylesheet without depending on the shape of the real
sources.
"""

import re
import unittest

from lxml import etree

from opensiddur.importer.miqra_al_pi_hamasorah.convert import intermediate_to_tei

TEI_NS = "http://www.tei-c.org/ns/1.0"
J_NS = "http://jewishliturgy.org/ns/jlptei/2"
NS = {"tei": TEI_NS, "j": J_NS}

TAAM_TACHTON = "urn:x-opensiddur:condition:bible:taam-tachton"
TAAM_ELYON = "urn:x-opensiddur:condition:bible:taam-elyon"


def _book(*rows: str) -> str:
    return (
        '<miqra:book xmlns:miqra="urn:x-opensiddur:miqra:intermediate"'
        ' xmlns:mw="urn:x-opensiddur:mw:intermediate"'
        ' fileName="exodus" bookNameEn="Exodus">'
        + "".join(rows)
        + "</miqra:book>"
    )


def _row(
    verse: str,
    text: str,
    chapter: str = "20",
    nav: str = "",
    scaffold: str = "",
) -> str:
    return (
        f'<miqra:row chapter="{chapter}" verse="{verse}">'
        f"<miqra:nav>{nav}</miqra:nav><miqra:scaffold>{scaffold}</miqra:scaffold>"
        f"<miqra:text>{text}</miqra:text>"
        "</miqra:row>"
    )


def _transform(*rows: str) -> tuple[etree._Element, etree._Element | None]:
    """Return the parsed body and standOff (``None`` when there are no notes)."""
    outputs = intermediate_to_tei(_book(*rows))
    body = etree.fromstring(outputs["body"].encode("utf-8"))
    stand_off = outputs.get("stand_off") or ""
    return body, etree.fromstring(stand_off.encode("utf-8")) if stand_off else None


def _verse_text(body: etree._Element, chapter: str, verse: str) -> str:
    """All text scoped to one verse: from its milestone up to the next verse milestone.

    A verse split by a parashah break repeats its milestone in each paragraph, so the
    text is gathered across paragraphs rather than read out of a single one.
    """
    urn = f"urn:x-opensiddur:text:bible:exodus/{chapter}/{verse}"
    collected: list[str] = []
    collecting = False
    for node in body.iter():
        if node.tag == f"{{{TEI_NS}}}milestone" and node.get("unit") == "verse":
            collecting = node.get("corresp") == urn
        if collecting and node.text and node.tag != f"{{{TEI_NS}}}milestone":
            collected.append(node.text)
        if collecting and node.tail:
            collected.append(node.tail)
    return re.sub(r"\s+", " ", "".join(collected)).strip()


def _anchor_ids(element: etree._Element) -> list[str]:
    return [
        anchor.get(f"{{http://www.w3.org/XML/1998/namespace}}id")
        for anchor in element.findall(f".//{{{TEI_NS}}}anchor")
    ]


class TestDualAccent(unittest.TestCase):
    """``{{מ:כפול}}`` carries a verse in both cantillations. The two readings are
    alternate wordings — exactly one is read — which is what ``j:option`` expresses."""

    DUAL = (
        "<miqra:dual-accent>"
        "<miqra:merged>גג֑֔ג</miqra:merged>"
        '<miqra:strand role="א">תחתון</miqra:strand>'
        '<miqra:strand role="ב">עליון</miqra:strand>'
        "</miqra:dual-accent>"
    )

    def test_emits_a_choice_of_two_options(self):
        body, _ = _transform(_row("2", self.DUAL))
        options = body.findall(f".//{{{J_NS}}}option")
        self.assertEqual(2, len(options))
        self.assertEqual(
            [TAAM_TACHTON, TAAM_ELYON], [o.get("corresp") for o in options]
        )
        # MAM-parsed documents א as ta'am tachton and ב as ta'am elyon (mpplus_dualcant.html).
        self.assertEqual("תחתון", options[0].text)
        self.assertEqual("עליון", options[1].text)

    def test_options_are_not_mixed_with_kri_ktiv(self):
        """Schematron forbids j:option beside j:read/j:written; keep them apart."""
        body, _ = _transform(_row("2", self.DUAL))
        choice = body.find(f".//{{{TEI_NS}}}choice")
        self.assertIsNone(choice.find(f"{{{J_NS}}}read"))
        self.assertIsNone(choice.find(f"{{{J_NS}}}written"))

    def test_merged_text_is_not_rendered_but_its_notes_stay_anchored(self):
        dual = (
            "<miqra:dual-accent>"
            "<miqra:merged>"
            '<miqra:variant noteId="n1"><miqra:display>גג֑֔ג</miqra:display></miqra:variant>'
            '<miqra:note xml:id="n1">הערה</miqra:note>'
            "</miqra:merged>"
            '<miqra:strand role="א">תחתון</miqra:strand>'
            '<miqra:strand role="ב">עליון</miqra:strand>'
            "</miqra:dual-accent>"
        )
        body, stand_off = _transform(_row("2", dual))
        self.assertNotIn("גג֑֔ג", _verse_text(body, "20", "2"))

        note = stand_off.find(f".//{{{TEI_NS}}}note")
        self.assertEqual("#n1-ref", note.get("target"))
        anchors = [
            anchor.get(f"{{http://www.w3.org/XML/1998/namespace}}id")
            for anchor in body.findall(f".//{{{TEI_NS}}}anchor")
        ]
        self.assertIn("n1-ref", anchors)

    def test_parashah_only_strands_become_one_break(self):
        """When both strands hold only a parashah break they agree on where it falls and
        differ only in whether it lands mid-verse. A break is block structure and cannot
        live inside tei:choice, so the ta'am tachton marker is kept and no choice is made."""
        dual = (
            "<miqra:dual-accent>"
            "<miqra:merged/>"
            '<miqra:strand role="א"><miqra:parashah type="close" midVerse="true"/></miqra:strand>'
            '<miqra:strand role="ב"><miqra:parashah type="close"/></miqra:strand>'
            "</miqra:dual-accent>"
        )
        body, _ = _transform(_row("12", f"לפני{dual}אחרי"))
        self.assertEqual([], body.findall(f".//{{{J_NS}}}option"))
        paragraphs = body.findall(f"{{{TEI_NS}}}div/{{{TEI_NS}}}p")
        self.assertEqual(2, len(paragraphs))
        self.assertEqual("closed-1", paragraphs[1].get("type"))
        self.assertEqual("לפני", _verse_text(body, "20", "12")[:4])
        self.assertIn("אחרי", _verse_text(body, "20", "12"))


class TestMidVerseParashah(unittest.TestCase):
    """A parashah break inside a verse splits its paragraph but not the verse. The text
    carries on across the break under a single milestone."""

    def test_verse_survives_a_mid_text_break(self):
        body, _ = _transform(
            _row("13", 'AAA<miqra:parashah type="close-inline" midVerse="true"/>BBB'),
            _row("14", "CCC"),
        )
        self.assertEqual("AAABBB", _verse_text(body, "20", "13"))
        milestones = [
            m.get("corresp")
            for m in body.findall(f".//{{{TEI_NS}}}milestone")
            if m.get("unit") == "verse"
        ]
        # Exactly one milestone per verse. Repeating it in the second paragraph would give
        # the verse two identical corresp values, and both the reference database and the
        # parallel compiler keep only the first of those and silently drop the rest. The
        # verse's scope runs to the next verse milestone regardless of paragraph boundaries,
        # so a single milestone still covers the text after the break.
        self.assertEqual(1, milestones.count("urn:x-opensiddur:text:bible:exodus/20/13"))
        self.assertIn("urn:x-opensiddur:text:bible:exodus/20/14", milestones)

    def test_plain_verse_is_unaffected(self):
        body, _ = _transform(_row("14", "CCC"))
        self.assertEqual("CCC", _verse_text(body, "20", "14"))


class TestNavAndScaffoldNotes(unittest.TestCase):
    """Notes from columns C (nav) and D (scaffold) reach the standOff, so the anchors they
    target have to exist in the body — the columns themselves are never rendered."""

    def assertNoDanglingTargets(self, body, stand_off):
        ids = set(body.xpath("//*/@xml:id"))
        dangling = [
            n.get("target")
            for n in (stand_off if stand_off is not None else [])
            if n.get("target", "").lstrip("#") not in ids
        ]
        self.assertEqual([], dangling)

    def test_nav_variant_wrapping_a_break_keeps_the_break_and_anchors_the_note(self):
        """{{נוסח}} around a parashah break records another witness's reading; the break is
        still MAM's own, so it opens a paragraph and the note anchors at its head."""
        nav = (
            '<miqra:variant noteId="n1">'
            '<miqra:display><miqra:parashah type="close"/></miqra:display>'
            "</miqra:variant>"
            '<miqra:note xml:id="n1">ל=פרשה פתוחה</miqra:note>'
        )
        body, stand_off = _transform(_row("1", "AAA"), _row("2", "BBB", nav=nav))
        paragraphs = body.findall(f"{{{TEI_NS}}}div/{{{TEI_NS}}}p")
        self.assertEqual(2, len(paragraphs))
        self.assertEqual("closed-1", paragraphs[1].get("type"))
        self.assertEqual(
            "n1-ref",
            paragraphs[1][0].get(f"{{http://www.w3.org/XML/1998/namespace}}id"),
        )
        self.assertNoDanglingTargets(body, stand_off)

    def test_a_wrapped_break_structures_the_text_like_a_bare_one(self):
        """Regression: the nav lift used to select miqra:nav/miqra:parashah only, so every
        break the source wrapped in {{נוסח}} was dropped from the body."""
        bare = '<miqra:parashah type="open"/>'
        wrapped = (
            '<miqra:variant noteId="n1">'
            f"<miqra:display>{bare}</miqra:display>"
            "</miqra:variant>"
            '<miqra:note xml:id="n1">ל=פרשה סתומה</miqra:note>'
        )
        expected, _ = _transform(_row("1", "AAA"), _row("2", "BBB", nav=bare))
        actual, _ = _transform(_row("1", "AAA"), _row("2", "BBB", nav=wrapped))
        self.assertEqual(
            [(p.tag, p.get("type")) for p in expected.iter(f"{{{TEI_NS}}}p")],
            [(p.tag, p.get("type")) for p in actual.iter(f"{{{TEI_NS}}}p")],
        )
        self.assertEqual(_verse_text(expected, "20", "2"), _verse_text(actual, "20", "2"))

    def test_nav_note_without_a_break_anchors_at_the_verse(self):
        """MAM prints no break here — the note only reports that another witness has one —
        so there is nothing in the body to anchor to but the verse itself."""
        nav = (
            '<miqra:variant noteId="n2"><miqra:display/></miqra:variant>'
            '<miqra:note xml:id="n2">ל=פרשה סתומה</miqra:note>'
        )
        body, stand_off = _transform(_row("2", "BBB", nav=nav))
        paragraphs = body.findall(f"{{{TEI_NS}}}div/{{{TEI_NS}}}p")
        self.assertEqual(1, len(paragraphs))
        self.assertIn("n2-ref", _anchor_ids(paragraphs[0]))
        self.assertEqual("BBB", _verse_text(body, "20", "2"))
        self.assertNoDanglingTargets(body, stand_off)

    def test_scaffold_note_anchors_at_the_verse(self):
        """Column D notes annotate the row's seder/aliyah marker, which is scaffolding for
        the verse rather than a point inside it."""
        scaffold = (
            '<miqra:variant noteId="n3"><miqra:display/></miqra:variant>'
            '<miqra:note xml:id="n3">תחילת סדר מצויינת כאן</miqra:note>'
        )
        body, stand_off = _transform(_row("2", "BBB", scaffold=scaffold))
        self.assertIn("n3-ref", _anchor_ids(body))
        self.assertEqual("BBB", _verse_text(body, "20", "2"))
        self.assertNoDanglingTargets(body, stand_off)

    def test_mam_note_anchor_in_nav_is_lifted(self):
        """{{מ:הערה}} mints its own anchor next to the note; in column C that anchor was
        discarded with the column."""
        nav = (
            '<miqra:anchor xml:id="n4-ref"/>'
            '<miqra:note xml:id="n4">הערה</miqra:note>'
        )
        body, stand_off = _transform(_row("2", "BBB", nav=nav))
        self.assertIn("n4-ref", _anchor_ids(body))
        self.assertNoDanglingTargets(body, stand_off)

    def test_column_c_text_is_still_not_rendered(self):
        """Anchoring the notes must not leak the navigation column into the text."""
        nav = (
            "ניווט"
            '<miqra:variant noteId="n5"><miqra:display/></miqra:variant>'
            '<miqra:note xml:id="n5">הערה</miqra:note>'
        )
        body, _ = _transform(_row("2", "BBB", nav=nav))
        self.assertEqual("BBB", _verse_text(body, "20", "2"))
        self.assertNotIn("הערה", "".join(body.itertext()))


class TestChapterMilestone(unittest.TestCase):
    """A chapter milestone has no column of its own in MAM's source; it is inferred from a
    row's chapter differing from the one before it."""

    def _chapter_milestones(self, body: etree._Element) -> list[tuple[str, str]]:
        return [
            (m.get("n"), m.get("corresp"))
            for m in body.findall(f".//{{{TEI_NS}}}milestone")
            if m.get("unit") == "chapter"
        ]

    def test_first_verse_of_the_book_opens_a_chapter(self):
        body, _ = _transform(_row("1", "AAA", chapter="20"))
        self.assertEqual(
            [("20", "urn:x-opensiddur:text:bible:exodus/20")],
            self._chapter_milestones(body),
        )

    def test_chapter_milestone_precedes_the_verse_milestone(self):
        body, _ = _transform(_row("1", "AAA", chapter="20"))
        p = body.find(f"{{{TEI_NS}}}div/{{{TEI_NS}}}p")
        milestones = list(p.findall(f"{{{TEI_NS}}}milestone"))
        self.assertEqual("chapter", milestones[0].get("unit"))
        self.assertEqual("verse", milestones[1].get("unit"))

    def test_no_milestone_for_a_later_verse_of_the_same_chapter(self):
        body, _ = _transform(
            _row("1", "AAA", chapter="20"), _row("2", "BBB", chapter="20"),
        )
        self.assertEqual(
            [("20", "urn:x-opensiddur:text:bible:exodus/20")],
            self._chapter_milestones(body),
        )

    def test_chapter_change_opens_a_new_milestone(self):
        body, _ = _transform(
            _row("18", "AAA", chapter="20"), _row("1", "BBB", chapter="21"),
        )
        self.assertEqual(
            [
                ("20", "urn:x-opensiddur:text:bible:exodus/20"),
                ("21", "urn:x-opensiddur:text:bible:exodus/21"),
            ],
            self._chapter_milestones(body),
        )

    def test_mid_verse_parashah_break_does_not_repeat_the_chapter_milestone(self):
        """A verse split by a parashah break still opens only once (see
        TestMidVerseParashah); the chapter milestone must not double up with it."""
        body, _ = _transform(
            _row("13", 'AAA<miqra:parashah type="close-inline" midVerse="true"/>BBB', chapter="20"),
        )
        self.assertEqual(
            [("20", "urn:x-opensiddur:text:bible:exodus/20")],
            self._chapter_milestones(body),
        )


if __name__ == "__main__":
    unittest.main()
