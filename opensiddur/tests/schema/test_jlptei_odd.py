import unittest
from pathlib import Path

from lxml import etree


ODD_PATH = Path(__file__).resolve().parents[3] / "schema" / "jlptei.odd.xml"


class TestJlpteiOddConstraints(unittest.TestCase):
    def setUp(self):
        self.tree = etree.parse(str(ODD_PATH))
        self.ns = {
            "tei": "http://www.tei-c.org/ns/1.0",
            "sch": "http://purl.oclc.org/dsdl/schematron",
        }

    def test_requires_xml_lang_on_tei_root(self):
        asserts = self.tree.xpath(
            "//tei:elementSpec[@ident='TEI']//sch:assert[@test='@xml:lang']",
            namespaces=self.ns,
        )
        self.assertTrue(asserts, "Expected schematron assert requiring tei:TEI/@xml:lang")

    def test_standoff_type_is_closed_list(self):
        vals = self.tree.xpath(
            "//tei:elementSpec[@ident='standOff']//tei:attDef[@ident='type']//tei:valItem/@ident",
            namespaces=self.ns,
        )
        self.assertEqual(set(vals), {"notes", "settings", "conditions"})

    def test_transclude_type_is_closed_list(self):
        vals = self.tree.xpath(
            "//tei:elementSpec[@ident='transclude']//tei:attDef[@ident='type']//tei:valItem/@ident",
            namespaces=self.ns,
        )
        self.assertEqual(set(vals), {"external", "inline"})

    def test_transclude_forbids_ranged_target_end(self):
        asserts = self.tree.xpath(
            "//tei:elementSpec[@ident='transclude']//sch:rule[@context='j:transclude']"
            "/sch:assert[contains(@test, '@targetEnd')]",
            namespaces=self.ns,
        )
        self.assertTrue(
            asserts,
            "Expected schematron assert on j:transclude forbidding a ranged @targetEnd",
        )

    def test_paragraph_type_is_closed_list(self):
        vals = self.tree.xpath(
            "//tei:elementSpec[@ident='p']//tei:attDef[@ident='type']//tei:valItem/@ident",
            namespaces=self.ns,
        )
        self.assertEqual(
            set(vals),
            {"open-1", "open-2", "open-3", "closed-1", "closed-2", "closed-3"},
        )

    def test_divine_name_exists_and_is_agent_like(self):
        divine = self.tree.xpath(
            "//tei:elementSpec[@ident='divineName']",
            namespaces=self.ns,
        )
        self.assertTrue(divine, "Expected j:divineName elementSpec to exist in ODD")

        member = self.tree.xpath(
            "//tei:elementSpec[@ident='divineName']//tei:memberOf[@key='model.nameLike.agent']",
            namespaces=self.ns,
        )
        self.assertTrue(member, "Expected j:divineName to be member of model.nameLike.agent")

    def test_corresp_is_unique_within_a_document(self):
        """A repeated URN breaks alignment and resolution silently, so the schema rejects it."""
        reports = self.tree.xpath(
            "//tei:constraintSpec[@ident='corresp-uniqueness']//sch:report",
            namespaces=self.ns,
        )
        self.assertTrue(reports, "Expected a schematron report for duplicate @corresp")

    def test_subverse_constraints_exist(self):
        """The two sub-verse units are constrained, not merely allowed."""
        asserts = self.tree.xpath(
            "//tei:constraintSpec[@ident='subverse-constraints']//sch:assert/@test",
            namespaces=self.ns,
        )
        self.assertIn("not(@corresp) or @n = 'a' or @n = 'b'", asserts)
        self.assertTrue(
            any("ends-with(@corresp" in a for a in asserts),
            "Expected @n and @corresp to be checked against each other",
        )

    def test_edition_verse_milestone_must_not_carry_a_urn(self):
        """unit='edition-verse' records an edition's own numbering, never an identity."""
        asserts = self.tree.xpath(
            "//tei:constraintSpec[@ident='edition-verse-constraints']//sch:assert/@test",
            namespaces=self.ns,
        )
        self.assertIn("not(@corresp)", asserts)
        self.assertIn("@n", asserts)



class TestContributorRefConstraints(unittest.TestCase):
    def setUp(self):
        self.tree = etree.parse(str(ODD_PATH))
        self.ns = {
            "tei": "http://www.tei-c.org/ns/1.0",
            "sch": "http://purl.oclc.org/dsdl/schematron",
        }

    def test_a_contributor_ref_rule_exists(self):
        rules = self.tree.xpath(
            "//tei:constraintSpec[@ident='contributor-ref-constraints']"
            "//sch:rule[contains(@context, '@ref')]",
            namespaces=self.ns,
        )
        self.assertTrue(rules, "Expected a schematron rule constraining @ref")

    def test_the_rule_names_every_contributor_namespace(self):
        # The ODD cannot import the Python constant, so the two are kept in step by hand.
        from opensiddur.common.urn_registry import CONTRIBUTOR_NAMESPACES

        tests = self.tree.xpath(
            "//tei:constraintSpec[@ident='contributor-ref-constraints']//sch:assert/@test",
            namespaces=self.ns,
        )
        self.assertEqual(len(tests), 1)
        for namespace in CONTRIBUTOR_NAMESPACES:
            self.assertIn(namespace.replace(".", "\\."), tests[0])


class TestContributorRefValidation(unittest.TestCase):
    """The compiled schema's behaviour on contributor URNs.

    Requires the compiled schema artifacts (`bash scripts/build-schema.sh`).
    """

    SKELETON = (
        '<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"'
        ' xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xml:lang="he">'
        "<tei:teiHeader><tei:fileDesc>"
        '<tei:titleStmt><tei:title type="main" xml:lang="en">t</tei:title>'
        "<tei:respStmt><tei:resp key=\"trl\">Translated by</tei:resp>"
        '<tei:name ref="{ref}">Someone</tei:name></tei:respStmt></tei:titleStmt>'
        "<tei:publicationStmt><tei:distributor>d</tei:distributor></tei:publicationStmt>"
        "<tei:sourceDesc><tei:bibl><tei:title>s</tei:title></tei:bibl></tei:sourceDesc>"
        "</tei:fileDesc></tei:teiHeader>"
        '<tei:text xml:lang="he"><tei:body><tei:p>x</tei:p></tei:body></tei:text>'
        "</tei:TEI>"
    )

    def assertValidity(self, valid: bool, ref: str, message: str):
        from opensiddur.importer.util.validation import validate

        is_valid, errors = validate(self.SKELETON.format(ref=ref))
        self.assertEqual(is_valid, valid, f"{message}\n{errors if is_valid != valid else ''}")

    def test_a_well_formed_contributor_ref_validates(self):
        for ref in (
            "urn:x-opensiddur:contributor:opensiddur.org/eve-feinstein",
            "urn:x-opensiddur:contributor:en.wikisource.org/Kathleen.wright5",
            "urn:x-opensiddur:contributor:he.wikisource.org/Dovi",
        ):
            with self.subTest(ref):
                self.assertValidity(True, ref, f"{ref} should validate")

    def test_a_ref_missing_the_type_segment_is_rejected(self):
        self.assertValidity(
            False,
            "urn:x-opensiddur:opensiddur.org/eve-feinstein",
            "a contributor URN without the type segment must not validate",
        )

    def test_a_ref_in_an_unknown_namespace_is_rejected(self):
        self.assertValidity(
            False,
            "urn:x-opensiddur:contributor:example.com/someone",
            "an unknown contributor namespace must not validate",
        )

    def test_a_text_urn_on_ref_is_rejected(self):
        self.assertValidity(
            False,
            "urn:x-opensiddur:text:prayer:ashrei",
            "@ref carries contributor URNs only",
        )


class TestNoteConditionValidation(unittest.TestCase):
    """j:condition decides whether a standoff note is printed (issue #168).

    Requires the compiled schema artifacts (`bash scripts/build-schema.sh`).
    """

    SKELETON = (
        '<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"'
        ' xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xml:lang="en">'
        "<tei:teiHeader><tei:fileDesc>"
        '<tei:titleStmt><tei:title type="main" xml:lang="en">t</tei:title></tei:titleStmt>'
        "<tei:publicationStmt><tei:distributor>d</tei:distributor></tei:publicationStmt>"
        "<tei:sourceDesc><tei:bibl><tei:title>s</tei:title></tei:bibl></tei:sourceDesc>"
        "</tei:fileDesc></tei:teiHeader>"
        "{standoff}"
        '<tei:text><tei:body><tei:p>x{inline}</tei:p></tei:body></tei:text>'
        "</tei:TEI>"
    )
    CONDITION = (
        '<j:condition><tei:fs type="opensiddur:holiday-aggregate">'
        '<tei:f name="shabbat"><tei:binary value="false"/></tei:f></tei:fs></j:condition>'
    )
    TARGET = 'target="urn:x-opensiddur:text:prayer:demo"'

    def assertValidity(self, valid: bool, message: str, standoff: str = "", inline: str = ""):
        from opensiddur.importer.util.validation import validate

        is_valid, errors = validate(self.SKELETON.format(standoff=standoff, inline=inline))
        self.assertEqual(is_valid, valid, f"{message}\n{errors if is_valid != valid else ''}")

    def notes(self, note: str) -> str:
        return f'<tei:standOff type="notes">{note}</tei:standOff>'

    def test_a_condition_first_in_a_standoff_note_validates(self):
        self.assertValidity(True, "a conditioned commentary note should validate", self.notes(
            f'<tei:note type="commentary" {self.TARGET}>\n  {self.CONDITION}'
            "<tei:p>Only on weekdays.</tei:p></tei:note>"))

    def test_a_condition_combinator_validates(self):
        self.assertValidity(True, "combinators are conditions too", self.notes(
            f'<tei:note type="editorial" {self.TARGET}><j:condition><j:none>'
            '<tei:fs type="opensiddur:holiday-aggregate"><tei:f name="shabbat">'
            '<tei:binary value="true"/></tei:f></tei:fs></j:none></j:condition>'
            "Text.</tei:note>"))

    def test_a_condition_after_note_text_is_rejected(self):
        self.assertValidity(False, "j:condition must come first", self.notes(
            f'<tei:note type="commentary" {self.TARGET}><tei:p>Text.</tei:p>'
            f"{self.CONDITION}</tei:note>"))

    def test_a_condition_on_an_instruction_is_rejected(self):
        self.assertValidity(False, "instructions use j:conditional", self.notes(
            f'<tei:note type="instruction" {self.TARGET}>{self.CONDITION}Stand.</tei:note>'))

    def test_a_condition_on_an_inline_note_is_rejected(self):
        self.assertValidity(False, "j:condition is for standoff notes",
                            inline=f'<tei:note type="commentary">{self.CONDITION}Text.</tei:note>')

    def test_a_condition_outside_a_note_is_rejected(self):
        self.assertValidity(False, "j:condition is not text", inline=self.CONDITION)


class TestSubverseValidation(unittest.TestCase):
    """The compiled schema's behaviour on sub-verse milestones, not just the ODD's wording.

    Requires the compiled schema artifacts (`bash scripts/build-schema.sh`).
    """

    SKELETON = (
        '<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"'
        ' xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xml:lang="he">'
        "<tei:teiHeader><tei:fileDesc>"
        '<tei:titleStmt><tei:title type="main" xml:lang="en">t</tei:title></tei:titleStmt>'
        "<tei:publicationStmt><tei:distributor>d</tei:distributor></tei:publicationStmt>"
        "<tei:sourceDesc><tei:bibl><tei:title>s</tei:title></tei:bibl></tei:sourceDesc>"
        "</tei:fileDesc></tei:teiHeader>"
        '<tei:text xml:lang="he"><tei:body><tei:p>{body}</tei:p></tei:body></tei:text>'
        "</tei:TEI>"
    )
    VERSE = "urn:x-opensiddur:text:bible:nahum/2/2"

    def assertValidity(self, valid: bool, body: str, message: str):
        from opensiddur.importer.util.validation import validate

        is_valid, errors = validate(self.SKELETON.format(body=body))
        self.assertEqual(is_valid, valid, f"{message}\n{errors if is_valid != valid else ''}")

    def test_a_well_formed_half_verse_validates(self):
        for n in ("a", "b"):
            with self.subTest(n):
                self.assertValidity(
                    True,
                    f'<tei:milestone unit="half-verse" n="{n}" corresp="{self.VERSE}/{n}"/>x',
                    f"half-verse {n} should validate",
                )

    def test_a_half_verse_numbered_anything_else_is_rejected(self):
        self.assertValidity(
            False,
            f'<tei:milestone unit="half-verse" n="c" corresp="{self.VERSE}/c"/>x',
            "a verse has two halves, not a third",
        )

    def test_a_half_verse_whose_n_and_urn_disagree_is_rejected(self):
        self.assertValidity(
            False,
            f'<tei:milestone unit="half-verse" n="a" corresp="{self.VERSE}/b"/>x',
            "@n and the last component of @corresp must agree",
        )

    def test_a_sub_verse_milestone_without_a_urn_is_rejected(self):
        """A division nothing can refer to is the one thing these must never be."""
        for unit, n in (("half-verse", "a"), ("verse-part", "tzapeh")):
            with self.subTest(unit):
                self.assertValidity(
                    False, f'<tei:milestone unit="{unit}" n="{n}"/>x', f"{unit} needs @corresp"
                )

    def test_bare_subverse_terminators_validate(self):
        for unit, n in (("half-verse", "a"), ("verse-part", "tzapeh")):
            with self.subTest(unit=unit):
                self.assertValidity(
                    True,
                    f'<tei:milestone unit="{unit}" n="{n}" corresp="{self.VERSE}/{n}"/>'
                    f'quoted words<tei:milestone unit="{unit}"/>unrelated words',
                    f"a bare {unit} terminator must close the quotation without naming a new part",
                )

    def test_a_well_formed_verse_part_validates(self):
        self.assertValidity(
            True,
            f'<tei:milestone unit="verse-part" n="tzapeh" corresp="{self.VERSE}/tzapeh"/>x',
            "a named verse part should validate",
        )

    def test_a_verse_part_named_with_a_dash_is_rejected(self):
        """A dash in the last component of a URN is what marks a range."""
        self.assertValidity(
            False,
            f'<tei:milestone unit="verse-part" n="a_b" corresp="{self.VERSE}/a-b"/>x',
            "a verse part name may not contain a dash",
        )

    def test_a_verse_part_may_not_be_named_a_or_b(self):
        """Those are reserved for the accentual halves."""
        for name in ("a", "b"):
            with self.subTest(name):
                self.assertValidity(
                    False,
                    f'<tei:milestone unit="verse-part" n="{name}" corresp="{self.VERSE}/{name}"/>x',
                    f"{name!r} is reserved",
                )
