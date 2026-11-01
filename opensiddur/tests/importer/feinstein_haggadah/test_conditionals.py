"""Tests for the haggadah's conditional passages.

Split in two. Most of this file tests how a scope is *rendered* — where the markers land
relative to the text, the rubric and the transclusion they apply to — and so builds its own
input and patches its own entries in, running everywhere. ``TestAgainstTheSource`` at the end
tests that the curated tables still *match* the real compilation, which needs the sourcetexts
checkout and skips without it.
"""

import re
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from opensiddur.importer.feinstein_haggadah.conditionals import (
    ALTERNATES,
    Alternate,
    CONDITIONALS,
    CONDITIONS,
    RUBRIC_CONDITIONS,
    VARIANT_RUBRIC_SECTIONS,
    Conditional,
    ConditionalError,
    Inline,
    Paragraphs,
    Transclusion,
    condition_for_rubric,
    variant_urn,
)
from opensiddur.importer.feinstein_haggadah.sections import (
    SectionContent,
    TextBlock,
    urn_for_section,
)
from opensiddur.importer.feinstein_haggadah.tei_builder import (
    _alternate_xml,
    section_body,
    tei_document,
)
from opensiddur.importer.util.validation import validate
from opensiddur.tests.importer.feinstein_haggadah import support


def _strip_conditions(xml: str) -> str:
    """Collapse each condition to a marker, so the shape of the output is readable."""
    xml = re.sub(r"\s*<tei:fs.*?</tei:fs>\s*", "", xml, flags=re.DOTALL)
    xml = re.sub(r'<j:conditional xml:id="cond_([^"]+)"(?: type="marked")?>\s*</j:conditional>',
                 r"[\1[", xml)
    xml = re.sub(r'<j:endConditional target="#cond_([^"]+)"/>', r"]\1]", xml)
    return xml


def _section(*paragraphs: str, lang: str = "he", slug: str = "qaddesh") -> SectionContent:
    """A section of plain numbered paragraphs, with nothing else in it."""
    field = "hebrew" if lang == "he" else "english"
    return SectionContent(
        slug=slug,
        blocks=[
            TextBlock(kind="paragraph", starts_paragraph=True, **{field: text})
            for text in paragraphs
        ],
    )


@contextmanager
def _entries(*conditionals: Conditional, alternate: Alternate | None = None):
    """Render as though the curated tables held exactly these entries.

    ``section_body`` reaches the tables through ``conditionals_for``/``alternate_for``, which
    it imports into its own namespace, so patching there decouples every emission test from
    what the real haggadah happens to contain.
    """
    module = "opensiddur.importer.feinstein_haggadah.tei_builder"
    with patch(f"{module}.conditionals_for", return_value=list(conditionals)):
        with patch(f"{module}.alternate_for", return_value=alternate):
            yield


class TestConditionTable(unittest.TestCase):
    def test_cond_ids_are_unique(self):
        ids = [entry.cond_id for entry in CONDITIONALS]
        self.assertCountEqual(ids, set(ids))

    def test_every_entry_has_a_scope_in_at_least_one_language(self):
        for entry in CONDITIONALS:
            with self.subTest(entry.cond_id):
                self.assertTrue(
                    entry.scope_he is not None or entry.scope_en is not None,
                    "an entry with no scope in either language is never emitted",
                )

    def test_every_condition_validates_in_a_document(self):
        """A malformed feature structure would only surface as a jing error at write time."""
        for name, fragment in CONDITIONS.items():
            with self.subTest(name):
                self.assertTrue(self._validates(fragment), f"{name} did not validate")

    def test_variant_conditions_validate(self):
        for entry in CONDITIONALS:
            if entry.condition in CONDITIONS:
                continue
            with self.subTest(entry.cond_id):
                self.assertTrue(self._validates(entry.condition))

    @staticmethod
    def _validates(condition: str) -> bool:
        body = f"""<tei:body>
          <tei:div corresp="urn:x-opensiddur:text:haggadah:qaddesh">
            <j:conditional xml:id="cond_test">{condition}</j:conditional>
            <tei:p>text</tei:p>
            <j:endConditional target="#cond_test"/>
          </tei:div>
        </tei:body>"""
        header = (
            '<tei:teiHeader xmlns:tei="http://www.tei-c.org/ns/1.0"><tei:fileDesc>'
            '<tei:titleStmt><tei:title type="main">t</tei:title></tei:titleStmt>'
            "<tei:publicationStmt><tei:distributor>d</tei:distributor>"
            '<tei:idno type="urn">urn:x-opensiddur:text:haggadah:qaddesh@p</tei:idno>'
            "</tei:publicationStmt><tei:sourceDesc><tei:bibl>"
            '<tei:ptr target="urn:x-opensiddur:text:haggadah:qaddesh@p"/>'
            "</tei:bibl></tei:sourceDesc></tei:fileDesc></tei:teiHeader>"
        )
        is_valid, _ = validate(tei_document(header, body, lang="he"))
        return is_valid


class TestVariantUrns(unittest.TestCase):
    def test_variant_urn_mirrors_the_text_urn(self):
        self.assertEqual(
            variant_urn("lefikhakh", "shirah_chadashah"),
            urn_for_section("lefikhakh").replace(
                "urn:x-opensiddur:text:", "urn:x-opensiddur:condition:"
            )
            + "/shirah_chadashah",
        )

    def test_variant_urn_carries_no_project(self):
        """A variant belongs to the text, not to the edition that prints it."""
        self.assertNotIn("@", variant_urn("korekh", "pesach"))


class TestRubricConditions(unittest.TestCase):
    def test_unknown_rubric_raises(self):
        with self.assertRaises(ConditionalError) as caught:
            condition_for_rubric("on Tuesdays say:", "qaddesh")
        self.assertIn("RUBRIC_CONDITIONS", str(caught.exception))

    def test_variant_rubric_without_a_section_entry_raises(self):
        with self.assertRaises(ConditionalError) as caught:
            condition_for_rubric("some add:", "qaddesh")
        self.assertIn("VARIANT_RUBRIC_SECTIONS", str(caught.exception))

    def test_variant_rubric_sections_resolve(self):
        for slug in VARIANT_RUBRIC_SECTIONS:
            with self.subTest(slug):
                self.assertIn("opensiddur:variant", condition_for_rubric("some add:", slug))


class TestEmission(unittest.TestCase):
    """Each scope kind places its markers where it should.

    Every case here supplies its own text and its own entry: what is under test is where the
    markers land relative to the text, which is independent of which real passage carries it.
    """

    def _render(self, slug, section, *conditionals, lang="he", **kwargs):
        return _strip_conditions(self._raw(slug, section, *conditionals, lang=lang, **kwargs))

    def _raw(self, slug, section, *conditionals, lang="he", **kwargs):
        with _entries(*conditionals):
            return section_body(slug, section, lang=lang, **kwargs)

    def test_inline_scope_replaces_the_brackets(self):
        entry = Conditional(
            slug="qaddesh",
            cond_id="inline",
            condition="shabbat",
            scope_he=Inline("אָלֶף", "בֵּית", "בֵּית", "גִּימֶל"),
        )
        body = self._render("qaddesh", _section("אָלֶף (בֵּית) גִּימֶל"), entry)
        self.assertIn("[inline[בֵּית]inline]", body)
        self.assertNotIn("(בֵּית)", body)

    def test_inline_scope_keeps_the_text_around_it(self):
        entry = Conditional(
            slug="qaddesh",
            cond_id="inline",
            condition="shabbat",
            scope_he=Inline("אָלֶף", "בֵּית", "בֵּית", "גִּימֶל"),
        )
        body = self._render("qaddesh", _section("אָלֶף (בֵּית) גִּימֶל"), entry)
        self.assertIn("אָלֶף", body)
        self.assertIn("גִּימֶל", body)

    def test_unbracketed_inline_scope_keeps_the_words_it_wraps(self):
        """Where the source never bracketed the run, no character may be swallowed."""
        entry = Conditional(
            slug="qaddesh",
            cond_id="inline",
            condition="shabbat",
            scope_he=Inline("אָלֶף", "בֵּית", "בֵּית", "גִּימֶל", bracketed=False),
        )
        body = self._render("qaddesh", _section("אָלֶף בֵּית גִּימֶל"), entry)
        self.assertIn("[inline[בֵּית", body)
        # A bracketed scope eats the bracket on each side; with no brackets to eat, every
        # letter of the paragraph must survive.
        text = re.search(r"<tei:p>(.*?)</tei:p>", body, re.DOTALL).group(1)
        self.assertEqual(re.sub(r"\[[a-z_]+\[|\][a-z_]+\]", "", text), "אָלֶף בֵּית גִּימֶל")

    def test_a_bracketed_scope_is_marked(self):
        """The markers stand for the source's brackets, so an edition that cannot decide the
        condition prints them as the source did."""
        entry = Conditional(
            slug="qaddesh",
            cond_id="inline",
            condition="shabbat",
            scope_he=Inline("אָלֶף", "בֵּית", "בֵּית", "גִּימֶל"),
        )
        body = self._raw("qaddesh", _section("אָלֶף (בֵּית) גִּימֶל"), entry)
        self.assertIn('<j:conditional xml:id="cond_inline" type="marked">', body)

    def test_an_unbracketed_scope_is_not_marked(self):
        entry = Conditional(
            slug="qaddesh",
            cond_id="inline",
            condition="shabbat",
            scope_he=Inline("אָלֶף", "בֵּית", "בֵּית", "גִּימֶל", bracketed=False),
        )
        body = self._raw("qaddesh", _section("אָלֶף בֵּית גִּימֶל"), entry)
        self.assertIn('<j:conditional xml:id="cond_inline">', body)

    def test_a_lost_marking_is_restored_without_swallowing_anything(self):
        entry = Conditional(
            slug="qaddesh",
            cond_id="inline",
            condition="shabbat",
            scope_he=Inline("אָלֶף", "בֵּית", "בֵּית", "גִּימֶל", bracketed=False, marked=True),
        )
        body = self._raw("qaddesh", _section("אָלֶף בֵּית גִּימֶל"), entry)
        self.assertIn('<j:conditional xml:id="cond_inline" type="marked">', body)
        self.assertEqual(_strip_conditions(body).count("בֵּית"), 1)
        self.assertIn("גִּימֶל", body)

    def test_a_bracketed_paragraph_scope_is_marked(self):
        entry = Conditional(
            slug="qaddesh", cond_id="para", condition="shabbat",
            scope_he=Paragraphs(1, bracketed=True),
        )
        body = self._raw("qaddesh", _section("(אָלֶף)", "בֵּית"), entry)
        self.assertIn('<j:conditional xml:id="cond_para" type="marked">', body)

    def test_a_transcluded_section_is_never_marked(self):
        entry = Conditional(
            slug="nirtzah", cond_id="child", condition="first_night",
            scope_he=Transclusion("vayehi_bachatzi_halailah"),
        )
        body = self._raw("nirtzah", None, entry, child_slugs=["vayehi_bachatzi_halailah"])
        self.assertIn('<j:conditional xml:id="cond_child">', body)

    def test_an_unbracketed_scope_closes_on_its_last_word(self):
        """The closer goes before the space after the scope, not after it, so that a bracket
        printed for it hugs the words it closes."""
        entry = Conditional(
            slug="qaddesh",
            cond_id="inline",
            condition="shabbat",
            scope_he=Inline("אָלֶף", "בֵּית", "בֵּית", "גִּימֶל", bracketed=False),
        )
        body = self._render("qaddesh", _section("אָלֶף בֵּית גִּימֶל"), entry)
        self.assertIn("[inline[בֵּית]inline] גִּימֶל", body)

    def test_paragraph_scope_brackets_whole_paragraphs(self):
        entry = Conditional(
            slug="qaddesh", cond_id="para", condition="shabbat", scope_he=Paragraphs(1)
        )
        body = self._render("qaddesh", _section("אָלֶף", "בֵּית", "גִּימֶל"), entry)
        between = body[body.index("[para["):body.index("]para]")]
        self.assertIn('unit="paragraph" n="1"', between)
        self.assertNotIn('unit="paragraph" n="2"', between)

    def test_paragraph_range_covers_every_paragraph_in_it(self):
        entry = Conditional(
            slug="barech", cond_id="range", condition="zimmun", scope_he=Paragraphs(1, 6)
        )
        section = _section(*(f"פִּסְקָה {n}" for n in range(1, 8)), slug="barech")
        body = self._render("barech", section, entry)
        between = body[body.index("[range["):body.index("]range]")]
        for number in range(1, 7):
            with self.subTest(paragraph=number):
                self.assertIn(f'unit="paragraph" n="{number}"', between)
        self.assertNotIn('unit="paragraph" n="7"', between)

    def test_transclusion_scope_wraps_only_its_own_child(self):
        entry = Conditional(
            slug="nirtzah",
            cond_id="child",
            condition="first_night",
            scope_he=Transclusion("vayehi_bachatzi_halailah"),
        )
        body = self._render(
            "nirtzah",
            None,
            entry,
            child_slugs=["vayehi_bachatzi_halailah", "ki_lo_naeh"],
        )
        between = body[body.index("[child["):body.index("]child]")]
        self.assertIn("vayehi_bachatzi_halailah", between)
        self.assertNotIn("ki_lo_naeh", between)

    def test_a_rubric_sits_inside_the_scope(self):
        """JLPTEI-3.md: a conditional-reading instruction goes inside the text it controls."""
        entry = Conditional(
            slug="qaddesh",
            cond_id="para",
            condition="shabbat",
            scope_he=Paragraphs(1),
            rubric_he="בשבת מתחילין כאן",
        )
        body = self._render("qaddesh", _section("אָלֶף", "בֵּית"), entry)
        between = body[body.index("[para["):body.index("]para]")]
        self.assertIn('<tei:note type="instruction">בשבת מתחילין כאן</tei:note>', between)

    def test_a_scope_the_source_parenthesises_with_its_rubric_is_marked(self):
        """The English sets a Shabbat insertion as "(on Shabbat say: ...)": the parentheses
        set the passage off, and the rubric sits inside the scope."""
        entry = Conditional(slug="qaddesh", cond_id="src", condition="shabbat")
        section = SectionContent(slug="qaddesh", blocks=[
            TextBlock(kind="instruction", english="on Shabbat say:", starts_paragraph=True,
                      governs=True),
            TextBlock(kind="paragraph", english="Sabbaths for rest and", governed=True),
        ])
        body = self._raw("qaddesh", section, entry, lang="en")
        self.assertIn('<j:conditional xml:id="cond_src" type="marked">', body)
        self.assertRegex(body, r'</j:conditional>\s*<tei:note type="instruction">on Shabbat say:')

    def test_an_editorial_note_sits_on_the_conditional_itself(self):
        """Shown only when the condition cannot be decided, unlike a source rubric."""
        entry = Conditional(
            slug="pre_seder",
            cond_id="note",
            condition="eruv_tavshilin",
            scope_en=Transclusion("eruv_tavshilin"),
            note_en="Said when the festival falls on a Friday.",
        )
        with _entries(entry):
            body = section_body(
                "pre_seder", None, lang="en", child_slugs=["eruv_tavshilin"]
            )
        marker = re.search(
            r'<j:conditional xml:id="cond_note">(.*?)</j:conditional>', body, re.DOTALL
        )
        self.assertIsNotNone(marker)
        self.assertIn('<tei:note type="instruction">', marker.group(1))
        # The note is the conditional's own, not part of the text it controls.
        self.assertNotIn("<tei:note", body[marker.end():])

    def test_markers_are_balanced_for_every_scope_kind(self):
        cases = {
            "paragraphs": (
                Conditional(
                    slug="qaddesh",
                    cond_id="p",
                    condition="shabbat",
                    scope_he=Paragraphs(1),
                    scope_en=Paragraphs(1),
                ),
                {},
            ),
            "inline": (
                Conditional(
                    slug="qaddesh",
                    cond_id="i",
                    condition="shabbat",
                    scope_he=Inline("אָלֶף", "בֵּית", "בֵּית", "גִּימֶל"),
                    scope_en=Inline("alpha", "beta", "beta", "gamma"),
                ),
                {},
            ),
            "transclusion": (
                Conditional(
                    slug="qaddesh",
                    cond_id="t",
                    condition="shabbat",
                    scope_he=Transclusion("karpas"),
                    scope_en=Transclusion("karpas"),
                ),
                {"child_slugs": ["karpas"]},
            ),
        }
        texts = {"he": "אָלֶף (בֵּית) גִּימֶל", "en": "alpha (beta) gamma"}
        for name, (entry, kwargs) in cases.items():
            for lang in ("he", "en"):
                with self.subTest(scope=name, lang=lang):
                    section = _section(texts[lang], "שֵׁנִי" if lang == "he" else "second",
                                       lang=lang)
                    with _entries(entry):
                        body = section_body(
                            "qaddesh", section, lang=lang, **kwargs
                        )
                    opened = re.findall(r'<j:conditional xml:id="cond_([^"]+)"', body)
                    closed = re.findall(r'<j:endConditional target="#cond_([^"]+)"', body)
                    self.assertCountEqual(opened, closed)
                    self.assertEqual(opened, [entry.cond_id])


class TestAlternates(unittest.TestCase):
    def test_alternate_becomes_a_choice_of_options(self):
        alternate = Alternate(
            slug="barech",
            lang="he",
            paragraph=1,
            options=(("he", "הב לן ונברך"), ("yi", "רבותי וויר וואָללן בענטשן")),
        )
        section = _section("הב לן ונברך (רבותי וויר וואָללן בענטשן)", slug="barech")
        with _entries(alternate=alternate):
            body = section_body("barech", section, lang="he")
        choice = re.search(r"<tei:choice>.*?</tei:choice>", body, re.DOTALL)
        self.assertIsNotNone(choice)
        self.assertEqual(choice.group().count("<j:option"), 2)
        self.assertIn('xml:lang="yi"', choice.group())

    def test_alternate_wording_absent_from_the_source_raises(self):
        """A hand-written option must not stand in for wording no longer in the source."""
        alternate = Alternate(
            slug="barech",
            lang="he",
            paragraph=1,
            options=(("he", "הב לן ונברך"), ("yi", "מלה שאיננה שם")),
        )
        with self.assertRaises(ConditionalError) as caught:
            _alternate_xml(alternate, "הב לן ונברך", "barech")
        self.assertIn("not in the source text", str(caught.exception))


class TestScopeKinds(unittest.TestCase):
    def test_paragraphs_through_defaults_to_first(self):
        self.assertEqual(Paragraphs(4).through, 4)
        self.assertEqual(Paragraphs(4, 9).through, 9)

    def test_inline_is_bracketed_unless_told_otherwise(self):
        self.assertTrue(Inline("a", "b", "c", "d").bracketed)
        self.assertFalse(Inline("a", "b", "c", "d", bracketed=False).bracketed)

    def test_scope_for_selects_by_language(self):
        entry = Conditional(
            slug="x",
            cond_id="x",
            condition="shabbat",
            scope_he=Paragraphs(1),
            scope_en=Paragraphs(2),
        )
        self.assertEqual(entry.scope_for("he"), Paragraphs(1))
        self.assertEqual(entry.scope_for("en"), Paragraphs(2))


class TestUnmatchedAnchor(unittest.TestCase):
    def test_an_unmatched_anchor_raises(self):
        """A source rewording must fail the conversion, not go quiet."""
        entry = Conditional(
            slug="lefikhakh",
            cond_id="lefikhakh_shirah_chadashah",
            condition="shabbat",
            scope_he=Inline("אָלֶף", "בֵּית", "בֵּית", "גִּימֶל"),
        )
        section = _section("אין כאן שום דבר", slug="lefikhakh")
        with _entries(entry):
            with self.assertRaises(Exception) as caught:
                section_body("lefikhakh", section, lang="he")
        self.assertIn("lefikhakh_shirah_chadashah", str(caught.exception))


class TestAgainstTheSource(unittest.TestCase):
    """The curated tables must still match the real compilation.

    Unlike everything above, these read the sourcetexts checkout: their subject is the curated
    data, not the code. They skip where it is not present; ``convert.py`` fails the conversion
    on the same conditions.
    """

    def setUp(self) -> None:
        self.sections = support.compilation_sections()

    def test_every_governing_rubric_in_the_source_is_known(self):
        """The conversion must not meet a conditional it cannot name."""
        for slug, section in self.sections.items():
            for block in section.blocks:
                if block.governs:
                    with self.subTest(slug=slug, rubric=block.english):
                        condition_for_rubric(block.english, slug)

    def test_rubric_table_has_no_unreachable_entries(self):
        """A rubric no longer in the source is a table entry that has gone stale."""
        seen = {
            block.english.strip()
            for section in self.sections.values()
            for block in section.blocks
            if block.governs
        }
        self.assertEqual(set(RUBRIC_CONDITIONS) - seen, set())

    def test_every_alternate_names_a_real_section(self):
        for entry in ALTERNATES:
            with self.subTest(entry.slug):
                self.assertIn(entry.slug, self.sections)

    def test_every_scope_resolves_against_the_source(self):
        """Every curated anchor must still match, in both projects."""
        for lang in ("he", "en"):
            for slug in sorted({entry.slug for entry in CONDITIONALS}):
                with self.subTest(lang=lang, slug=slug):
                    section_body(slug, self.sections.get(slug), lang=lang)

    def test_markers_are_balanced_in_every_section(self):
        for lang in ("he", "en"):
            for slug in sorted({entry.slug for entry in CONDITIONALS}):
                with self.subTest(lang=lang, slug=slug):
                    body = section_body(
                        slug,
                        self.sections.get(slug),
                        lang=lang,
                        child_slugs=[
                            scope.child_slug
                            for entry in CONDITIONALS
                            if entry.slug == slug
                            and isinstance(scope := entry.scope_for(lang), Transclusion)
                        ],
                    )
                    opened = re.findall(r'<j:conditional xml:id="cond_([^"]+)"', body)
                    closed = re.findall(r'<j:endConditional target="#cond_([^"]+)"', body)
                    self.assertCountEqual(opened, closed)


if __name__ == "__main__":
    unittest.main()
