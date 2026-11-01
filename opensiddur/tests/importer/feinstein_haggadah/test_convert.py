import os
import shutil
import tempfile
import unittest
from pathlib import Path

from opensiddur.common.versification import WLC_PROJECT
from opensiddur.importer.feinstein_haggadah.convert import EN_PROJECT, HE_PROJECT
from opensiddur.importer.feinstein_haggadah.convert import (
    convert_all,
    document_header,
    index_header,
)
from opensiddur.importer.feinstein_haggadah.parse_compilation import _clean_html_cell
from opensiddur.importer.feinstein_haggadah.tei_builder import (
    header_with_only_bibls,
    minimal_index_header,
    project_citation_bibl,
    read_front_stub,
    tei_document,
    validate_and_write,
    validate_project_directory,
)
from opensiddur.importer.feinstein_haggadah.versify import BiblicalSection
from opensiddur.importer.util.validation import validate
from opensiddur.tests.importer.feinstein_haggadah import support

SAMPLE_HTML = """
<table>
<tr>
<td><div class="liturgy">קַדֵּשׁ</div></td>
<td><div class="english"><h3>Sanctification of the Day</h3><p>Kadesh text.</p></div></td>
</tr>
</table>
"""


class TestParseCompilationCleanup(unittest.TestCase):
    def test_clean_html_cell_strips_footnote_jquery(self) -> None:
        raw = (
            "Blessed.[1] Genesis 1:1 "
            "jQuery('#footnote_plugin_tooltip__1_1').tooltip({ tip: 'x' });"
        )
        cleaned = _clean_html_cell(raw)
        self.assertNotIn("jQuery", cleaned)
        self.assertIn("Genesis 1:1", cleaned)


class TestTeiBuilderValidation(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_validate_and_write_rejects_invalid_jlptei(self) -> None:
        invalid = """<tei:TEI xml:lang="he" xmlns:tei="http://www.tei-c.org/ns/1.0">
<tei:text><tei:body><tei:head>bad</tei:head></tei:body></tei:text>
</tei:TEI>"""
        with self.assertRaises(RuntimeError) as ctx:
            validate_and_write(invalid, "bad", self.project_dir)
        self.assertIn("JLPTEI validation failed", str(ctx.exception))

    def test_validate_project_directory_checks_all_files(self) -> None:
        valid = tei_document(
            """<tei:teiHeader xmlns:tei="http://www.tei-c.org/ns/1.0">
  <tei:fileDesc>
    <tei:titleStmt><tei:title>Test</tei:title></tei:titleStmt>
    <tei:publicationStmt><tei:distributor><tei:ref target="http://opensiddur.org">OSP</tei:ref></tei:distributor></tei:publicationStmt>
    <tei:sourceDesc><tei:bibl><tei:title>Test</tei:title></tei:bibl></tei:sourceDesc>
  </tei:fileDesc>
</tei:teiHeader>""",
            """<tei:body><tei:div><tei:p>ok</tei:p></tei:div></tei:body>""",
            lang="he",
        )
        validate_and_write(valid, "ok", self.project_dir)
        validate_project_directory(self.project_dir)


class TestConvertProducesValidJlptei(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("OPENSIDDUR_RUN_SLOW_TESTS"),
        "slow end-to-end conversion of the full haggadah compilation (schema-validates every "
        "output file with jing); set OPENSIDDUR_RUN_SLOW_TESTS=1 to run it",
    )
    def test_convert_all_writes_valid_project_files(self) -> None:
        compilation_path = support.require_path(
            support.compilation_path(), "haggadah compilation not checked out"
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = root / "sources"
            feinstein_dir = sources / "feinstein_haggadah_2009"
            feinstein_dir.mkdir(parents=True)
            shutil.copy(compilation_path, feinstein_dir / "compilation.json")

            project_root = root / "project"
            convert_all(sourcetexts_root=sources, project_root=project_root)

            self._assert_psalms_follow_the_1822_print(
                project_root / HE_PROJECT
            )
            self._assert_only_the_index_holds_the_bibliography(
                project_root / HE_PROJECT
            )

            for project in (HE_PROJECT, EN_PROJECT):
                project_dir = project_root / project
                self.assertTrue(project_dir.is_dir())
                xml_files = list(project_dir.glob("*.xml"))
                self.assertGreater(len(xml_files), 10)
                validate_project_directory(project_dir)
                for path in xml_files:
                    is_valid, errors = validate(path)
                    self.assertTrue(is_valid, f"{path.name}: {errors}")

    def _assert_only_the_index_holds_the_bibliography(self, project_dir: Path) -> None:
        """schema/JLPTEI-3.md: the full source citations live in the project index; every
        other document cites them by pointer. An xml:id repeated across files would also
        make the pointer's fragment ambiguous."""
        holders = [
            path.name
            for path in sorted(project_dir.glob("*.xml"))
            if 'xml:id="project_source_bibl"' in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(holders, ["index.xml"])

        qaddesh = (project_dir / "qaddesh.xml").read_text(encoding="utf-8")
        self.assertIn(
            f'<tei:ptr target="/{HE_PROJECT}/index#project_source_bibl"/>',
            qaddesh,
        )
        # The pointer replaces the bibliography; it does not sit alongside a copy of it.
        self.assertNotIn("HebrewBooks.org #4909", qaddesh)
        self.assertNotIn("Differences from the 1822 Heidenheim original", qaddesh)
        # Responsibility and licence stay on every document — only sourceDesc collapses.
        self.assertIn("<tei:respStmt>", qaddesh)
        self.assertIn("<tei:licence", qaddesh)

    def _assert_psalms_follow_the_1822_print(self, project_dir: Path) -> None:
        """The psalms the print carries reach the project as transcribed, not as WLC."""
        for slug in ("psalm_113", "psalm_115", "psalm_117", "psalm_136"):
            written = (project_dir / f"{slug}.xml").read_text(encoding="utf-8")
            with self.subTest(slug=slug):
                self.assertIn("<j:divineName>יְיָ</j:divineName>", written)
                self.assertNotIn("יְהֹוָה", written)
                self.assertNotIn("יהוה", written)
                # WLC cites itself as the text source; these no longer come from it.
                self.assertNotIn(f"text:bible:psalms@{WLC_PROJECT}", written)

        # Psalm 126 is not in the print and keeps the compilation's text and its WLC citation.
        psalm_126 = (project_dir / "psalm_126.xml").read_text(encoding="utf-8")
        self.assertIn(f"text:bible:psalms@{WLC_PROJECT}", psalm_126)
        self.assertNotIn("<j:divineName>", psalm_126)


PROJECT_HEADER = """<tei:teiHeader xmlns:tei="http://www.tei-c.org/ns/1.0">
  <tei:fileDesc>
    <tei:titleStmt>
      <tei:title>Test</tei:title>
      <tei:respStmt><tei:resp key="trc">Transcribed by</tei:resp><tei:name>A Contributor</tei:name></tei:respStmt>
    </tei:titleStmt>
    <tei:publicationStmt>
      <tei:distributor><tei:ref target="http://opensiddur.org">OSP</tei:ref></tei:distributor>
      <tei:availability status="free"><tei:licence target="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</tei:licence></tei:availability>
    </tei:publicationStmt>
    <tei:sourceDesc>
      <tei:bibl xml:id="project_source_bibl"><tei:title>The printed source</tei:title></tei:bibl>
      <tei:bibl xml:id="facsimile_bibl"><tei:title>The facsimile</tei:title></tei:bibl>
    </tei:sourceDesc>
  </tei:fileDesc>
</tei:teiHeader>"""


class TestDocumentHeaders(unittest.TestCase):
    """schema/JLPTEI-3.md: the full source citations belong to the project index; every
    other document cites them by pointer."""

    def test_index_header_keeps_the_bibliography_and_adds_its_page_scope(self) -> None:
        header = index_header(
            PROJECT_HEADER, project_id="p", ranges={"index": ("2r", "40v")}
        )
        self.assertIn('xml:id="project_source_bibl"', header)
        self.assertIn('xml:id="facsimile_bibl"', header)
        self.assertIn('<tei:biblScope unit="pages" from="2r" to="40v"/>', header)

    def test_index_header_without_a_page_range_is_left_alone(self) -> None:
        self.assertEqual(
            index_header(PROJECT_HEADER, project_id="p", ranges={}), PROJECT_HEADER
        )

    def test_document_header_replaces_the_bibliography_with_a_pointer(self) -> None:
        header = document_header(
            PROJECT_HEADER,
            "qaddesh",
            project_id="p",
            ranges={"qaddesh": ("3v", "4r")},
            scripture={},
        )
        self.assertIn(
            '<tei:ptr target="/p/index#project_source_bibl"/>',
            header,
        )
        self.assertIn('<tei:biblScope unit="pages" from="3v" to="4r"/>', header)
        # The citations themselves, and the xml:ids addressing them, stay in the index.
        self.assertNotIn('xml:id="project_source_bibl"', header)
        self.assertNotIn('xml:id="facsimile_bibl"', header)
        self.assertNotIn("The facsimile", header)
        # Only sourceDesc collapses; responsibility and licence belong to every document.
        self.assertIn("<tei:respStmt>", header)
        self.assertIn("<tei:licence", header)

    def test_document_header_without_a_page_range_still_cites_the_bibl(self) -> None:
        """A project with no page breaks — the 2009 translation — has no ranges at all, but
        still names the specific bibl entry, just without a page scope."""
        header = document_header(
            PROJECT_HEADER, "qaddesh", project_id="p", ranges={}, scripture={}
        )
        self.assertIn('<tei:ptr target="/p/index#project_source_bibl"/>', header)
        self.assertNotIn("biblScope", header)

    def test_document_header_adds_the_wlc_bibl_for_a_scripture_section(self) -> None:
        header = document_header(
            PROJECT_HEADER,
            "psalm_126",
            project_id="p",
            ranges={"psalm_126": ("27r", "27r")},
            scripture={
                "psalm_126": BiblicalSection(
                    section="psalm_126", book="psalms", chapter=126, verses=[]
                )
            },
        )
        self.assertIn(f'<tei:ptr target="urn:x-opensiddur:text:bible:psalms@{WLC_PROJECT}"/>', header)
        self.assertIn('<tei:biblScope unit="chapter" from="126" to="126"/>', header)

    def test_minimal_index_header_cites_the_project_by_pointer(self) -> None:
        """Sub-indices (pre_seder, seder, magid…) get a header of their own rather than a
        copy of the project's, and cite the bibliography the same way a leaf does."""
        header = minimal_index_header(
            "Magid", project_id="p", urn_suffix="maggid", from_page="5r", to_page="9v"
        )
        self.assertIn('<tei:title type="main" xml:lang="he">Magid</tei:title>', header)
        self.assertIn(
            '<tei:idno type="urn">urn:x-opensiddur:text:haggadah:maggid@p</tei:idno>', header
        )
        self.assertIn('<tei:biblScope unit="pages" from="5r" to="9v"/>', header)
        self.assertNotIn('xml:id="project_source_bibl"', header)

    def test_minimal_index_header_without_pages_omits_the_scope(self) -> None:
        header = minimal_index_header("Seder", project_id="p", urn_suffix="seder")
        self.assertIn('<tei:ptr target="/p/index#project_source_bibl"/>', header)
        self.assertNotIn("biblScope", header)

    def test_header_with_only_bibls_rejects_a_header_without_a_source_desc(self) -> None:
        with self.assertRaises(ValueError):
            header_with_only_bibls("<tei:teiHeader/>", ["<tei:bibl/>"])

    def test_project_citation_bibl_scopes_to_pages_when_they_are_known(self) -> None:
        self.assertIn(
            '<tei:biblScope unit="pages" from="1r" to="2v"/>',
            project_citation_bibl("p", from_page="1r", to_page="2v"),
        )
        self.assertNotIn("biblScope", project_citation_bibl("p"))
        # A half-known range is not a range.
        self.assertNotIn("biblScope", project_citation_bibl("p", from_page="1r"))


class TestTitlePage(unittest.TestCase):
    HEADER = """<tei:teiHeader xmlns:tei="http://www.tei-c.org/ns/1.0">
  <tei:fileDesc>
    <tei:titleStmt><tei:title>Test</tei:title></tei:titleStmt>
    <tei:publicationStmt><tei:distributor><tei:ref target="http://opensiddur.org">OSP</tei:ref></tei:distributor></tei:publicationStmt>
    <tei:sourceDesc><tei:bibl><tei:title>Test</tei:title></tei:bibl></tei:sourceDesc>
  </tei:fileDesc>
</tei:teiHeader>"""

    def test_tei_document_places_front_before_body(self) -> None:
        document = tei_document(
            self.HEADER,
            "<tei:body><tei:div><tei:p>ok</tei:p></tei:div></tei:body>",
            lang="he",
            front_xml='<tei:front xmlns:tei="http://www.tei-c.org/ns/1.0"><tei:pb n="1r"/></tei:front>',
        )
        self.assertLess(document.index("<tei:front"), document.index("<tei:body>"))
        is_valid, errors = validate(document)
        self.assertTrue(is_valid, errors)

    def test_tei_document_without_front_emits_none(self) -> None:
        document = tei_document(
            self.HEADER,
            "<tei:body><tei:div><tei:p>ok</tei:p></tei:div></tei:body>",
            lang="he",
        )
        self.assertNotIn("<tei:front", document)

    def test_1822_title_page_stub_is_valid_and_transcribes_the_leaf(self) -> None:
        stub = read_front_stub(f"{HE_PROJECT}_title_page.xml")
        self.assertIn("<tei:titlePage>", stub)
        self.assertIn("ההגדה לליל שמורים", stub)
        self.assertIn("רעדלהיים", stub)
        self.assertIn("Roedelheim,", stub)
        # The title leaf precedes the 1822 foliation, which starts at 2r.
        self.assertIn('<tei:pb n="1r"', stub)

        document = tei_document(
            self.HEADER,
            "<tei:body><tei:div><tei:p>ok</tei:p></tei:div></tei:body>",
            lang="he",
            front_xml=stub,
        )
        is_valid, errors = validate(document)
        self.assertTrue(is_valid, errors)


if __name__ == "__main__":
    unittest.main()
