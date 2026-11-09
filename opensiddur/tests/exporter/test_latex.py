"""Tests for the latex.py driver around the reledmac.xslt stylesheet.

The driver is responsible for:

  - extracting license/credit/source metadata from referenced source files,
  - and feeding all of those into the XSLT as parameters.

These tests cover those responsibilities. The actual XSLT output is tested
separately in ``test_reledmac_xslt.py``.
"""

import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

import opensiddur.exporter.tex.latex as latex_module
from opensiddur.exporter import typography as typography_module
from opensiddur.exporter.typography import TypographyConfig
from opensiddur.exporter.tex.latex import (
    CreditRecord,
    LicenseRecord,
    credits_to_tex,
    extract_credits,
    extract_licenses,
    get_file_references,
    group_credits,
    group_licenses,
    licenses_to_tex,
    order_credits,
    sources_to_tex,
    transform_xml_to_tex,
)
from opensiddur.exporter import metadata


def extract_sources(xml_file_paths):
    """The bibliography the PDF stage embeds for these files' projects."""
    return sources_to_tex(metadata.extract_sources(xml_file_paths))


def _no_fontconfig():
    """Mock out the installed-font lookup.

    The settings models check a font chain a settings file names against
    fontconfig. Whether the machine running the tests has Ezra SIL is not what
    any test here is about, and a test that turned on it would fail for reasons
    that have nothing to do with the code.
    """
    return patch.object(
        typography_module, "_installed_font_families", return_value=None
    )


class TestExtractLicenses(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_dir = Path(self.temp_dir.name)

    def _create(self, project: str, filename: str, content: bytes) -> Path:
        d = self.test_dir / project
        d.mkdir(parents=True, exist_ok=True)
        p = d / filename
        p.write_bytes(content)
        return p

    def test_extract_single_license(self):
        xml = b"""<root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:teiHeader><tei:fileDesc><tei:publicationStmt>
            <tei:availability>
              <tei:licence target="http://example.com/cc">CC0</tei:licence>
            </tei:availability>
          </tei:publicationStmt></tei:fileDesc></tei:teiHeader>
        </root>"""
        f = self._create("p", "a.xml", xml)
        with patch.object(latex_module, "projects_source_root", self.test_dir):
            result = extract_licenses([f])
        self.assertEqual(len(result), 1)
        record = next(iter(result.values()))
        self.assertEqual(record.url, "http://example.com/cc")
        self.assertEqual(record.name, "CC0")

    def test_license_without_url_is_skipped(self):
        xml = b"""<root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:licence>Unknown</tei:licence></root>"""
        f = self._create("p", "a.xml", xml)
        with patch.object(latex_module, "projects_source_root", self.test_dir):
            result = extract_licenses([f])
        self.assertEqual(len(result), 0)

    def test_invalid_xml_is_skipped(self):
        f = self._create("p", "a.xml", b"not xml")
        with patch.object(latex_module, "projects_source_root", self.test_dir):
            result = extract_licenses([f])
        self.assertEqual(len(result), 0)


class TestGroupLicenses(unittest.TestCase):

    def test_dedupes_by_url(self):
        records = {
            Path("a"): LicenseRecord(url="http://x", name="X"),
            Path("b"): LicenseRecord(url="http://x", name="X"),
            Path("c"): LicenseRecord(url="http://y", name="Y"),
        }
        grouped = group_licenses(records)
        self.assertEqual(len(grouped), 2)
        self.assertEqual({lr.url for lr in grouped}, {"http://x", "http://y"})

    def test_order_does_not_depend_on_file_order(self):
        """A rebuild must not reshuffle the Legal section."""
        records = [
            (Path("b"), LicenseRecord(url="http://z", name="Zed")),
            (Path("a"), LicenseRecord(url="http://y", name="alpha")),
            (Path("c"), LicenseRecord(url="http://x", name="Mid")),
        ]
        forward = group_licenses(dict(records))
        backward = group_licenses(dict(reversed(records)))
        self.assertEqual(["alpha", "Mid", "Zed"], [lr.name for lr in forward])
        self.assertEqual(forward, backward)


class TestLicensesToTex(unittest.TestCase):

    def test_emits_legal_chapter(self):
        out = licenses_to_tex(
            [LicenseRecord(url="http://creativecommons.org/cc", name="CC")]
        )
        self.assertIn(r"\section*{Legal}", out)
        self.assertIn("CC", out)
        self.assertIn(r"\url{http://creativecommons.org/cc}", out)

    def test_escapes_the_name_but_not_the_url(self):
        out = licenses_to_tex(
            [LicenseRecord(url="http://example.org/a_b%20c", name="Free & Open_Licence")]
        )
        self.assertIn(r"\item Free \& Open\_Licence (", out)
        self.assertIn(r"\url{http://example.org/a_b%20c}", out)

    def test_no_licences_emits_nothing(self):
        """An itemize with no items is a LaTeX error and kills the run before any PDF.

        A document can genuinely have no licences to list — one built entirely of public
        domain text, or compiled without annotations.
        """
        self.assertEqual(licenses_to_tex([]), "")


class TestExtractCredits(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_dir = Path(self.temp_dir.name)

    def _create(self, project: str, filename: str, content: bytes) -> Path:
        d = self.test_dir / project
        d.mkdir(parents=True, exist_ok=True)
        p = d / filename
        p.write_bytes(content)
        return p

    def test_extracts_resp_stmt(self):
        xml = b"""<root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:respStmt>
            <tei:resp key="aut">Author</tei:resp>
            <tei:name ref="urn:x-opensiddur:contributor:ns/person">A B</tei:name>
          </tei:respStmt>
        </root>"""
        f = self._create("p", "a.xml", xml)
        result = extract_credits([f])
        credits = result[f]
        self.assertEqual(len(credits), 1)
        self.assertEqual(credits[0].role, "aut")
        self.assertEqual(credits[0].namespace, "ns")
        self.assertEqual(credits[0].contributor, "person")

    def test_a_credit_with_no_reference_is_still_a_person(self):
        # It used to be dropped in silence. A respStmt records who digitised a text, so
        # one without a reference is malformed data rather than somebody to leave out --
        # and leaving them out is how a contributor disappears without anyone noticing.
        xml = b"""<root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:respStmt>
            <tei:resp key="trc">Transcribed by</tei:resp>
            <tei:name>Someone</tei:name>
          </tei:respStmt>
        </root>"""
        f = self._create("p", "a.xml", xml)
        credits = extract_credits([f])[f]
        self.assertEqual(len(credits), 1)
        self.assertEqual(credits[0].name_text, "Someone")
        self.assertEqual(credits[0].namespace, "")

    def test_a_credit_that_says_nothing_about_what_was_done_is_skipped(self):
        # Without a resp/@key there is no telling which list to put them in.
        xml = b"""<root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:respStmt><tei:resp>Transcribed by</tei:resp>
          <tei:name>Someone</tei:name></tei:respStmt>
        </root>"""
        f = self._create("p", "a.xml", xml)
        self.assertEqual(extract_credits([f])[f], [])

    def test_a_reference_that_is_not_a_contributor_urn_is_reported(self):
        # A plain URL read as a URN gave the heading "From " with nothing after it.
        xml = b"""<root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:respStmt>
            <tei:resp key="trc">Transcribed by</tei:resp>
            <tei:name ref="https://he.wikisource.org/">Someone</tei:name>
          </tei:respStmt>
        </root>"""
        f = self._create("p", "a.xml", xml)
        credits = extract_credits([f])[f]
        self.assertEqual(credits[0].namespace, "")

    def test_a_name_carrying_markup_is_read_whole(self):
        xml = b"""<root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:respStmt>
            <tei:resp key="trc">Transcribed by</tei:resp>
            <tei:name ref="urn:x-opensiddur:contributor:ns/p"><tei:hi>A</tei:hi> B</tei:name>
          </tei:respStmt>
        </root>"""
        f = self._create("p", "a.xml", xml)
        self.assertEqual(extract_credits([f])[f][0].name_text, "A B")


class TestGroupCredits(unittest.TestCase):

    def test_groups_by_role_and_namespace(self):
        c = CreditRecord(
            role="aut",
            resp_text="Author",
            ref="urn:x-opensiddur:contributor:ns/p1",
            name_text="P1",
            namespace="ns",
            contributor="p1",
        )
        grouped = group_credits({Path("a"): [c]})
        self.assertIn("aut", grouped)
        self.assertIn("ns", grouped["aut"])
        self.assertEqual(len(grouped["aut"]["ns"]), 1)

    def test_dedupes_by_role_and_ref(self):
        c = CreditRecord(
            role="aut",
            resp_text="Author",
            ref="urn:x-opensiddur:contributor:ns/p1",
            name_text="P1",
            namespace="ns",
            contributor="p1",
        )
        grouped = group_credits({Path("a"): [c], Path("b"): [c]})
        self.assertEqual(len(grouped["aut"]["ns"]), 1)


class TestCreditsToTex(unittest.TestCase):

    def test_pluralizes_role_when_multiple_contributors(self):
        c1 = CreditRecord(
            role="aut", resp_text="Author", ref="urn:x:ns/a",
            name_text="A", namespace="ns", contributor="a",
        )
        c2 = CreditRecord(
            role="aut", resp_text="Author", ref="urn:x:ns/b",
            name_text="B", namespace="ns", contributor="b",
        )
        out = credits_to_tex(order_credits({"aut": {"ns": [c1, c2]}}))
        self.assertIn(r"\subsection*{Authors}", out)

    def test_emits_singular_when_one_contributor(self):
        c1 = CreditRecord(
            role="aut", resp_text="Author", ref="urn:x:ns/a",
            name_text="A", namespace="ns", contributor="a",
        )
        out = credits_to_tex(order_credits({"aut": {"ns": [c1]}}))
        self.assertIn(r"\subsection*{Author}", out)
        self.assertNotIn(r"\subsection*{Authors}", out)

    def test_escapes_names_and_sets_hebrew_as_hebrew(self):
        """Names are the sources' own text: a TeX special in one must not end the run."""
        credits = [
            CreditRecord(
                role="trl", resp_text="Translator", ref="urn:x:ns_one/a",
                name_text="A. & B. Smith_Jones", namespace="ns_one", contributor="a",
            ),
            CreditRecord(
                role="trl", resp_text="Translator", ref="urn:x:ns_one/b",
                name_text="משה בן 100%", namespace="ns_one", contributor="b",
            ),
        ]
        out = credits_to_tex(order_credits({"trl": {"ns_one": credits}}))
        self.assertIn(r"\subsubsection*{From ns\_one}", out)
        self.assertIn(r"\item A. \& B. Smith\_Jones", out)
        self.assertIn(r"\item \texthebrew{משה בן} 100\%", out)


class TestExtractSources(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_dir = Path(self.temp_dir.name)

    def _create(self, project: str, filename: str, content: bytes) -> Path:
        d = self.test_dir / project
        d.mkdir(parents=True, exist_ok=True)
        p = d / filename
        p.write_bytes(content)
        return p

    def test_emits_filecontents_block_when_bibl_present(self):
        index = b"""<?xml version="1.0"?>
        <root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:listBibl>
            <tei:bibl><tei:title>T</tei:title><tei:author>A</tei:author></tei:bibl>
          </tei:listBibl>
        </root>"""
        doc = self._create("p", "doc.xml", b"<root/>")
        self._create("p", "index.xml", index)
        preamble, postamble = extract_sources([doc])
        self.assertIn(r"\begin{filecontents*}[overwrite]{\jobname.bib}", preamble)
        self.assertIn(r"\addbibresource{\jobname.bib}", preamble)
        self.assertIn(r"\printbibliography", postamble)

    def test_a_bibl_that_only_points_to_the_index_is_not_a_source(self):
        """A file's pointer back to its project's index is a tei:bibl with nothing to cite."""
        index = b"""<?xml version="1.0"?>
        <root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:sourceDesc>
            <tei:bibl><tei:title>A Book</tei:title><tei:author>Author</tei:author></tei:bibl>
            <tei:bibl><tei:ptr target="index.xml"/><tei:biblScope unit="page">1</tei:biblScope></tei:bibl>
          </tei:sourceDesc>
        </root>"""
        doc = self._create("p", "doc.xml", b"<root/>")
        self._create("p", "index.xml", index)
        preamble, _ = extract_sources([doc])
        self.assertEqual(1, preamble.count("@"))
        self.assertIn("A Book", preamble)

    def test_returns_empty_strings_when_no_bibl(self):
        doc = self._create("p", "doc.xml", b"<root/>")
        self._create("p", "index.xml", b"<root/>")
        preamble, postamble = extract_sources([doc])
        self.assertEqual(preamble, "")
        self.assertEqual(postamble, "")

    def test_dedupes_when_multiple_files_share_index(self):
        index = b"""<?xml version="1.0"?>
        <root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:listBibl>
            <tei:bibl><tei:title>T</tei:title><tei:author>A</tei:author></tei:bibl>
          </tei:listBibl>
        </root>"""
        f1 = self._create("p", "doc1.xml", b"<root/>")
        f2 = self._create("p", "doc2.xml", b"<root/>")
        self._create("p", "index.xml", index)
        preamble, _ = extract_sources([f1, f2])
        self.assertEqual(preamble.count("@"), 1)

    def test_bibtex_wraps_hebrew_fields_in_texthebrew(self):
        index = """<?xml version="1.0"?>
        <root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:listBibl>
            <tei:bibl>
              <tei:title xml:lang="he">מקרא על פי המסורה</tei:title>
              <tei:editor>Avi Kadish</tei:editor>
            </tei:bibl>
          </tei:listBibl>
        </root>""".encode("utf-8")
        doc = self._create("p", "doc.xml", b"<root/>")
        self._create("p", "index.xml", index)
        preamble, _ = extract_sources([doc])
        self.assertIn(r"title = {\texthebrew{מקרא על פי המסורה}}", preamble)

    def test_bibtex_leaves_latin_fields_unwrapped_under_hebrew_lang(self):
        """Latin content inheriting xml:lang="he" must not get \\texthebrew.

        The wrapper sets \\textdir TRT, which renders Latin text reversed.
        """
        index = """<?xml version="1.0"?>
        <root xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:listBibl>
            <tei:bibl>
              <tei:title>Page-break reference facsimile</tei:title>
              <tei:edition>First edition (Yaari 447)</tei:edition>
              <tei:publisher>Wolf Heidenheim</tei:publisher>
              <tei:author>Meir Halevi Heidenheim</tei:author>
            </tei:bibl>
          </tei:listBibl>
        </root>""".encode("utf-8")
        doc = self._create("p", "doc.xml", b"<root/>")
        self._create("p", "index.xml", index)
        preamble, _ = extract_sources([doc])
        self.assertNotIn(r"\texthebrew", preamble)
        self.assertIn("title = {Page-break reference facsimile}", preamble)
        self.assertIn("edition = {First edition (Yaari 447)}", preamble)
        self.assertIn("publisher = {Wolf Heidenheim}", preamble)
        self.assertIn("author = {Meir Halevi Heidenheim}", preamble)

    def test_bibtex_wraps_hebrew_runs_inside_english_text(self):
        index = """<?xml version="1.0"?>
        <root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:listBibl>
            <tei:bibl>
              <tei:title>Notes</tei:title>
              <tei:note xml:lang="en">The print reads לשנה הבאה בירושלים then נרצה.</tei:note>
            </tei:bibl>
          </tei:listBibl>
        </root>""".encode("utf-8")
        doc = self._create("p", "doc.xml", b"<root/>")
        self._create("p", "index.xml", index)
        preamble, _ = extract_sources([doc])
        self.assertIn(r"\texthebrew{לשנה הבאה בירושלים}", preamble)
        self.assertIn(r"\texthebrew{נרצה}", preamble)
        self.assertIn("The print reads ", preamble)

    def test_bibtex_escapes_tex_special_characters(self):
        """Unescaped specials abort the LaTeX run at \\printbibliography.

        Project slugs carry underscores, which TeX reads as math subscripts:
        "Missing $ inserted" with no PDF produced.
        """
        index = """<?xml version="1.0"?>
        <root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:listBibl>
            <tei:bibl>
              <tei:title>Published as heidenheim_haggadah_1822</tei:title>
              <tei:note xml:lang="en">100% of A &amp; B; #3; a~b; x^2; cost $5</tei:note>
            </tei:bibl>
          </tei:listBibl>
        </root>""".encode("utf-8")
        doc = self._create("p", "doc.xml", b"<root/>")
        self._create("p", "index.xml", index)
        preamble, _ = extract_sources([doc])
        self.assertIn(r"title = {Published as heidenheim\_haggadah\_1822}", preamble)
        self.assertIn(r"100\% of A \& B", preamble)
        self.assertIn(r"\#3", preamble)
        self.assertIn(r"a\textasciitilde{}b", preamble)
        self.assertIn(r"x\textasciicircum{}2", preamble)
        self.assertIn(r"cost \$5", preamble)

    def test_bibtex_escape_does_not_touch_its_own_wrapper_braces(self):
        """The \\texthebrew wrapper and escape output must not be re-escaped."""
        index = """<?xml version="1.0"?>
        <root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:listBibl>
            <tei:bibl><tei:title xml:lang="he">הגדה</tei:title></tei:bibl>
          </tei:listBibl>
        </root>""".encode("utf-8")
        doc = self._create("p", "doc.xml", b"<root/>")
        self._create("p", "index.xml", index)
        preamble, _ = extract_sources([doc])
        self.assertIn(r"title = {\texthebrew{הגדה}}", preamble)
        self.assertNotIn(r"\textbackslash", preamble)
        self.assertNotIn(r"\{\}", preamble)

    def test_bibtex_cites_an_online_copy_on_the_work_it_reproduces(self):
        """A scan is a copy of the book, so it is fields on the book's entry.

        biblatex prints eprinttype/eprint ("archive.org: <id>") and the access
        date beside the URL; howpublished it does not print at all.
        """
        index = """<?xml version="1.0"?>
        <root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:listBibl>
            <tei:bibl>
              <tei:title>Book of Examples</tei:title>
              <tei:author>Example Author</tei:author>
              <tei:publisher>Example Press</tei:publisher>
              <tei:date when="1949">1949</tei:date>
              <tei:date type="accessed" when="2026-09-08">2026-09-08</tei:date>
              <tei:idno type="url">https://example.org/details/book</tei:idno>
              <tei:idno type="example.org">book</tei:idno>
            </tei:bibl>
          </tei:listBibl>
        </root>""".encode("utf-8")
        doc = self._create("p", "doc.xml", b"<root/>")
        self._create("p", "index.xml", index)
        preamble, _ = extract_sources([doc])
        self.assertIn("@book{example1949,", preamble)
        self.assertIn("url = {https://example.org/details/book},", preamble)
        self.assertIn("urldate = {2026-09-08},", preamble)
        self.assertIn("eprinttype = {example.org},", preamble)
        self.assertIn("eprint = {book},", preamble)
        self.assertNotIn("howpublished", preamble)
        self.assertNotIn("\n  date = {2026-09-08}", preamble)

    def test_bibtex_emits_iso_dates_as_date_and_others_as_year(self):
        index = """<?xml version="1.0"?>
        <root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:listBibl>
            <tei:bibl>
              <tei:title>Dated</tei:title>
              <tei:author>Iso</tei:author>
              <tei:date>2025-07-27</tei:date>
            </tei:bibl>
            <tei:bibl>
              <tei:title>Prose date</tei:title>
              <tei:author>Prose</tei:author>
              <tei:date>25 January 2016</tei:date>
            </tei:bibl>
          </tei:listBibl>
        </root>""".encode("utf-8")
        doc = self._create("p", "doc.xml", b"<root/>")
        self._create("p", "index.xml", index)
        preamble, _ = extract_sources([doc])
        self.assertIn("date = {2025-07-27},", preamble)
        self.assertIn("year = {25 January 2016},", preamble)

    def test_bibtex_joins_notes_and_accession_into_one_addendum(self):
        """A repeated field makes biber reject the entry."""
        index = """<?xml version="1.0"?>
        <root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:listBibl>
            <tei:bibl>
              <tei:title>Noted</tei:title>
              <tei:author>Noter</tei:author>
              <tei:note>First remark.</tei:note>
              <tei:note>Second remark.</tei:note>
              <tei:idno type="Accession">X 19 A</tei:idno>
            </tei:bibl>
          </tei:listBibl>
        </root>""".encode("utf-8")
        doc = self._create("p", "doc.xml", b"<root/>")
        self._create("p", "index.xml", index)
        preamble, _ = extract_sources([doc])
        self.assertEqual(preamble.count("addendum = {"), 1)
        self.assertIn(
            "addendum = {First remark. Second remark. Accession: X 19 A},", preamble
        )
        self.assertNotIn("note = {", preamble)

    def test_bibtex_omits_encoding_notes(self):
        """How this project encodes the source is no part of citing the book."""
        index = """<?xml version="1.0"?>
        <root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:listBibl>
            <tei:bibl>
              <tei:title>Noted</tei:title>
              <tei:author>Noter</tei:author>
              <tei:note>Worth citing.</tei:note>
              <tei:note type="encoding">The scan is 1541x2291 pixels per leaf.</tei:note>
            </tei:bibl>
          </tei:listBibl>
        </root>""".encode("utf-8")
        doc = self._create("p", "doc.xml", b"<root/>")
        self._create("p", "index.xml", index)
        preamble, _ = extract_sources([doc])
        self.assertIn("addendum = {Worth citing.},", preamble)
        self.assertNotIn("1541x2291", preamble)

    def test_bibtex_emits_distributor_of_an_online_source_as_organization(self):
        """biblatex ignores publisher in @online, so a host filed there vanishes."""
        index = """<?xml version="1.0"?>
        <root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:listBibl>
            <tei:bibl>
              <tei:title>A page</tei:title>
              <tei:distributor>
                <tei:ref target="https://example.org">Example Wiki</tei:ref>
              </tei:distributor>
              <tei:idno type="url">https://example.org/page</tei:idno>
            </tei:bibl>
          </tei:listBibl>
        </root>""".encode("utf-8")
        doc = self._create("p", "doc.xml", b"<root/>")
        self._create("p", "index.xml", index)
        preamble, _ = extract_sources([doc])
        self.assertIn("@online{example", preamble)
        self.assertIn("organization = {Example Wiki},", preamble)
        self.assertNotIn("publisher = {", preamble)

    def test_bibtex_takes_the_url_from_a_bare_ref(self):
        index = """<?xml version="1.0"?>
        <root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:listBibl>
            <tei:bibl>
              <tei:title>Facsimile</tei:title>
              <tei:ref target="https://example.org/4909">Example #4909</tei:ref>
            </tei:bibl>
          </tei:listBibl>
        </root>""".encode("utf-8")
        doc = self._create("p", "doc.xml", b"<root/>")
        self._create("p", "index.xml", index)
        preamble, _ = extract_sources([doc])
        self.assertIn("@online{unknownnd,", preamble)
        self.assertIn("url = {https://example.org/4909},", preamble)

    def test_bibtex_disambiguates_colliding_cite_keys_in_one_index(self):
        """Duplicate keys make biber drop all but the first entry."""
        index = """<?xml version="1.0"?>
        <root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:listBibl>
            <tei:bibl xml:id="facsimile_bibl"><tei:title>Facsimile</tei:title></tei:bibl>
            <tei:bibl><tei:title>Transcription</tei:title></tei:bibl>
          </tei:listBibl>
        </root>""".encode("utf-8")
        doc = self._create("p", "doc.xml", b"<root/>")
        self._create("p", "index.xml", index)
        preamble, _ = extract_sources([doc])
        self.assertIn("@misc{unknownnd-facsimilebibl,", preamble)
        self.assertIn("@misc{unknownnd-2,", preamble)

    def test_different_works_sharing_a_key_across_indexes_are_both_kept(self):
        """BibTeX keeps one entry per key, so the second work is given its own key."""

        def index(title: str) -> bytes:
            return f"""<?xml version="1.0"?>
            <root xmlns:tei="http://www.tei-c.org/ns/1.0">
              <tei:listBibl>
                <tei:bibl>
                  <tei:title>{title}</tei:title>
                  <tei:author>Example Author</tei:author>
                  <tei:date>1949</tei:date>
                </tei:bibl>
              </tei:listBibl>
            </root>""".encode("utf-8")

        one = self._create("one", "doc.xml", b"<root/>")
        self._create("one", "index.xml", index("First Book"))
        two = self._create("two", "doc.xml", b"<root/>")
        self._create("two", "index.xml", index("Second Book"))
        preamble, _ = extract_sources([one, two])
        self.assertIn("{example1949,", preamble)
        self.assertIn("{example1949-2,", preamble)
        self.assertIn("First Book", preamble)
        self.assertIn("Second Book", preamble)

    def test_a_renamed_work_arriving_again_is_listed_once(self):
        """Work Y, renamed away from work X's key, must not be renamed a second time."""

        def index(title: str) -> bytes:
            return f"""<?xml version="1.0"?>
            <root xmlns:tei="http://www.tei-c.org/ns/1.0">
              <tei:listBibl>
                <tei:bibl>
                  <tei:title>{title}</tei:title>
                  <tei:author>Example Author</tei:author>
                  <tei:date>1949</tei:date>
                </tei:bibl>
              </tei:listBibl>
            </root>""".encode("utf-8")

        files = []
        for project, title in (("a", "Work X"), ("b", "Work Y"), ("c", "Work Y")):
            files.append(self._create(project, "doc.xml", b"<root/>"))
            self._create(project, "index.xml", index(title))
        preamble, _ = extract_sources(files)
        self.assertEqual(1, preamble.count("Work Y"))
        self.assertIn("{example1949-2,", preamble)
        self.assertNotIn("{example1949-3,", preamble)

    def test_cite_key_has_no_punctuation_from_a_display_date(self):
        """A key ends at its first comma, so one from "March 3, 1822" corrupted the entry."""
        index = b"""<?xml version="1.0"?>
        <root xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:listBibl>
            <tei:bibl><tei:title>T</tei:title><tei:author>O'Brien{x}</tei:author>
              <tei:date>March 3, 1822</tei:date></tei:bibl>
          </tei:listBibl>
        </root>"""
        doc = self._create("p", "doc.xml", b"<root/>")
        self._create("p", "index.xml", index)
        preamble, _ = extract_sources([doc])
        self.assertIn("@misc{obrienxmarch31822,", preamble)

    def test_dedupes_entries_that_share_a_cite_key_across_indexes(self):
        """Two projects of one book cite it alike but for a note."""

        def index(note: str) -> bytes:
            return f"""<?xml version="1.0"?>
            <root xmlns:tei="http://www.tei-c.org/ns/1.0">
              <tei:listBibl>
                <tei:bibl>
                  <tei:title>Book of Examples</tei:title>
                  <tei:author>Example Author</tei:author>
                  <tei:date>1949</tei:date>
                  <tei:note>{note}</tei:note>
                </tei:bibl>
              </tei:listBibl>
            </root>""".encode("utf-8")

        he = self._create("he", "doc.xml", b"<root/>")
        self._create("he", "index.xml", index("The Hebrew of this project."))
        en = self._create("en", "doc.xml", b"<root/>")
        self._create("en", "index.xml", index("The English of this project."))
        preamble, _ = extract_sources([he, en])
        self.assertEqual(preamble.count("{example1949,"), 1)


class TestGetFileReferences(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_dir = Path(self.temp_dir.name)
        self.project_dir = self.test_dir / "project"
        self.project_dir.mkdir()

    def _create(self, filename: str, content: bytes) -> Path:
        p = self.project_dir / filename
        p.write_bytes(content)
        return p

    def test_collects_main_and_index(self):
        xml = b"""<root xmlns:tei="http://www.tei-c.org/ns/1.0"
                       xmlns:p="http://jewishliturgy.org/ns/processing"
                       p:project="proj" p:file_name="main.xml"/>"""
        f = self._create("main.xml", xml)
        result = get_file_references(f, self.project_dir)
        self.assertIn(self.project_dir / "proj" / "main.xml", result)
        self.assertIn(self.project_dir / "proj" / "index.xml", result)

    def test_collects_transcluded_files(self):
        xml = b"""<root xmlns:tei="http://www.tei-c.org/ns/1.0"
                       xmlns:p="http://jewishliturgy.org/ns/processing"
                       p:project="a" p:file_name="main.xml">
          <p:transclude p:project="b" p:file_name="x.xml"/>
        </root>"""
        f = self._create("main.xml", xml)
        result = get_file_references(f, self.project_dir)
        self.assertIn(self.project_dir / "a" / "main.xml", result)
        self.assertIn(self.project_dir / "b" / "x.xml", result)
        self.assertIn(self.project_dir / "a" / "index.xml", result)
        self.assertIn(self.project_dir / "b" / "index.xml", result)


class TestTransformXmlToTex(unittest.TestCase):
    """End-to-end driver test: confirms the typography parameters reach
    the XSLT and that integration with license/credit/source extraction
    works."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_dir = Path(self.temp_dir.name)

    def _create(self, project: str, filename: str, content: bytes) -> Path:
        d = self.test_dir / project
        d.mkdir(parents=True, exist_ok=True)
        p = d / filename
        p.write_bytes(content)
        return p

    def test_basic_transform_produces_lualatex_document(self):
        xml = b"""<?xml version="1.0"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>
            <tei:milestone unit="verse" n="1"/>Hello.
          </tei:p></tei:body></tei:text>
        </tei:TEI>"""
        f = self._create("p", "input.xml", xml)
        with patch.object(latex_module, "projects_source_root", self.test_dir):
            out = transform_xml_to_tex(f)

        self.assertIn(r"\documentclass", out)
        self.assertIn(r"\begin{document}", out)
        self.assertIn(r"\end{document}", out)
        self.assertIn(r"\usepackage{reledmac}", out)
        # Hebrew font must be declared via fontspec for Hebrew script support.
        self.assertIn(r"\newfontfamily\hebrewfont", out)

    def test_a_failed_transformation_raises_rather_than_exiting(self):
        """A library function that calls sys.exit takes its caller down with it."""
        f = self._create("p", "input.xml", b"<tei:TEI xmlns:tei='http://www.tei-c.org/ns/1.0'>")
        with patch.object(latex_module, "projects_source_root", self.test_dir):
            with self.assertRaises(Exception) as caught:
                transform_xml_to_tex(f)
        self.assertNotIsInstance(caught.exception, SystemExit)

    def test_typography_object_is_threaded_into_preamble(self):
        xml = b"""<?xml version="1.0"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>x</tei:p></tei:body></tei:text>
        </tei:TEI>"""
        f = self._create("p", "input.xml", xml)
        with _no_fontconfig():
            typography = TypographyConfig.model_validate(
                {
                    "fonts": {"hebrew": ["Ezra SIL", "FreeSerif"], "latin": "FreeSerif"},
                    "parallel": {"layout": "pairs"},
                    "page": {"paper": "letterpaper", "base_font_size": "12pt"},
                }
            )

            with patch.object(latex_module, "projects_source_root", self.test_dir):
                out = transform_xml_to_tex(f, typography=typography)

        self.assertIn(r"\documentclass[12pt,letterpaper]{book}", out)
        self.assertIn(r"\newfontfamily\hebrewfont", out)
        self.assertIn(r"\setmainfont{FreeSerif}", out)

    def test_a_settings_file_reaches_the_emitted_tex(self):
        """The whole path, YAML to TeX: a settings file that names paper,
        margins, a heading size and line numbers has to show up in the
        document, and what it did not name is printed at its default."""
        xml = b"""<?xml version="1.0"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>x</tei:p></tei:body></tei:text>
        </tei:TEI>"""
        f = self._create("p", "input.xml", xml)
        settings_path = self.test_dir / "settings.yaml"
        settings_path.write_text(
            """
typography:
  page:
    paper: a5paper
    base_font_size: 10pt
    sides: one
    margins: {top: 2cm, inner: 25mm}
  paragraphs:
    line_spacing: 1.4
  styles:
    heading1: {size: small, weight: normal}
  line_numbers:
    enabled: false
"""
        )

        with patch.object(latex_module, "projects_source_root", self.test_dir):
            out = transform_xml_to_tex(f, settings_file=settings_path)

        self.assertIn(r"\documentclass[10pt,a5paper,oneside]{book}", out)
        self.assertIn("top=2cm", out)
        self.assertIn("left=25mm", out)   # one-sided, so inner is the left margin
        self.assertIn(r"\linespread{1.4}", out)
        self.assertIn(r"{\normalfont\small\mdseries #1}", out)
        self.assertIn(r"\renewcommand*{\linenumberlist}{-1}", out)
        self.assertNotIn(r"\numberlinefalse", out)
        # What it did not name is at its default.
        self.assertIn(r"{\normalfont\Large\bfseries #1}", out)
        self.assertNotIn("bottom=", out)

    def test_an_invalid_settings_file_fails_before_anything_is_rendered(self):
        """And says which setting is wrong. The blanket handler around the
        transform would flatten the message to one line, so validation has to
        happen outside it."""
        xml = b"""<?xml version="1.0"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>x</tei:p></tei:body></tei:text>
        </tei:TEI>"""
        f = self._create("p", "input.xml", xml)
        settings_path = self.test_dir / "settings.yaml"
        settings_path.write_text("typography:\n  page:\n    paper: tabloid\n")

        with patch.object(latex_module, "projects_source_root", self.test_dir):
            with self.assertRaises(ValidationError) as caught:
                transform_xml_to_tex(f, settings_file=settings_path)
        self.assertIn("paper", str(caught.exception))

    def test_running_heads_are_built_into_the_page_style_preamble(self):
        xml = b"""<?xml version="1.0"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>x</tei:p></tei:body></tei:text>
        </tei:TEI>"""
        f = self._create("p", "input.xml", xml)
        typography = TypographyConfig.model_validate(
            {
                "page_header": {"odd": {"left": "{book-title}"}},
                "page_footer": {"all": {"center": "{page}"}},
            }
        )

        with patch.object(latex_module, "projects_source_root", self.test_dir):
            out = transform_xml_to_tex(f, typography=typography)

        self.assertIn(r"\usepackage{fancyhdr}", out)
        self.assertIn(r"\fancyhead[LO]{", out)
        self.assertIn(r"\fancyfoot[C]{", out)

    _PLAIN_TEI = b"""<?xml version="1.0"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>x</tei:p></tei:body></tei:text>
        </tei:TEI>"""

    def test_default_typography_heads_the_page_with_its_section_title(self):
        f = self._create("p", "input.xml", self._PLAIN_TEI)
        with patch.object(latex_module, "projects_source_root", self.test_dir):
            out = transform_xml_to_tex(f, typography=TypographyConfig())
        self.assertIn(r"\usepackage{fancyhdr}", out)
        self.assertIn(r"\LastMark{OSheadAny}", out)

    def test_table_of_contents_does_not_leak_into_the_running_head(self):
        """Regression: the Heidenheim haggadah showed "CONTENTS" on every page.

        book.cls's \\tableofcontents issues \\@mkboth{CONTENTS}{CONTENTS}. With no
        page style of our own, the class's `headings` style read that mark back
        and, since nothing here ever sets another, kept it for the whole book.
        """
        xml = b"""<?xml version="1.0"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">
          <tei:text><tei:body>
            <tei:div><tei:head>Section One</tei:head><tei:p>x</tei:p></tei:div>
          </tei:body></tei:text>
        </tei:TEI>"""
        f = self._create("p", "input.xml", xml)
        typography = TypographyConfig.model_validate(
            {"table_of_contents": {"enabled": True}}
        )
        with patch.object(latex_module, "projects_source_root", self.test_dir):
            out = transform_xml_to_tex(f, typography=typography)

        self.assertIn(r"\tableofcontents", out)
        self.assertIn(r"\let\@mkboth\@gobbletwo", out)
        # The head names the section it is on, read from a mark the heading
        # already inserted -- never \leftmark/\rightmark, which carried CONTENTS.
        self.assertIn(r"\LastMark{OSheadAny}", out)
        self.assertNotIn(r"\leftmark", out)
        self.assertNotIn(r"\rightmark", out)

    def test_empty_page_header_emits_no_page_style_but_still_silences_marks(self):
        """Asking for no head must not fall back to the class's own marks."""
        f = self._create("p", "input.xml", self._PLAIN_TEI)
        typography = TypographyConfig.model_validate({"page_header": {}})
        with patch.object(latex_module, "projects_source_root", self.test_dir):
            out = transform_xml_to_tex(f, typography=typography)
        self.assertNotIn("fancyhdr", out)
        self.assertIn(r"\let\@mkboth\@gobbletwo", out)

    def test_document_language_fills_in_for_slots_that_declare_none(self):
        xml = """<?xml version="1.0"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="he">
          <tei:text><tei:body><tei:p>x</tei:p></tei:body></tei:text>
        </tei:TEI>""".encode()
        f = self._create("p", "input.xml", xml)
        typography = TypographyConfig.model_validate(
            {"page_header": {"all": {"left": "{book-title}"}}}
        )
        with patch.object(latex_module, "projects_source_root", self.test_dir):
            out = transform_xml_to_tex(f, typography=typography)
        self.assertIn(r"\fancyhead[L]{{\textdir TRT\foreignlanguage{hebrew}{", out)

    def test_layout_pairs_propagates_to_parallel_block(self):
        xml = """<?xml version="1.0"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he"><tei:p>שלום</tei:p></p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en"><tei:p>Hi</tei:p></p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>""".encode("utf-8")
        f = self._create("p", "input.xml", xml)
        typography = TypographyConfig.model_validate({"parallel": {"layout": "pairs"}})
        with patch.object(latex_module, "projects_source_root", self.test_dir):
            out = transform_xml_to_tex(f, typography=typography)
        self.assertIn(r"\begin{pairs}", out)
        self.assertIn(r"\Columns", out)

    def test_layout_interleaved_propagates_to_parallel_block(self):
        xml = """<?xml version="1.0"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing">
          <tei:text><tei:body>
            <p:parallel column-order="primary_first">
              <p:parallelItem role="primary" xml:lang="he"><tei:p>שלום</tei:p></p:parallelItem>
              <p:parallelItem role="parallel" xml:lang="en"><tei:p>Hi</tei:p></p:parallelItem>
            </p:parallel>
          </tei:body></tei:text>
        </tei:TEI>""".encode("utf-8")
        f = self._create("p", "input.xml", xml)
        typography = TypographyConfig.model_validate({
            "parallel": {"layout": "interleaved", "interleaved": {"line_numbers": "both"}},
            "line_numbers": {"increment": 2},
        })
        with patch.object(latex_module, "projects_source_root", self.test_dir):
            out = transform_xml_to_tex(f, typography=typography)
        self.assertNotIn(r"\usepackage{reledpar}", out)
        self.assertNotIn(r"\begin{pairs}", out)
        self.assertNotIn(r"\linenumincrementR", out)
        self.assertIn(r"\begin{OSInterleavedTranslation}", out)
        # Defined once, at the setting's value.
        self.assertEqual(1, out.count(r"\newcommand{\OSInterleavedNumbering}"))
        self.assertIn(r"\newcommand{\OSInterleavedNumbering}{}", out)

    def test_table_of_contents_setting_is_threaded_into_xslt_params(self):
        xml = b"""<?xml version="1.0"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0">
          <tei:text><tei:body><tei:p>x</tei:p></tei:body></tei:text>
        </tei:TEI>"""
        f = self._create("p", "input.xml", xml)
        typography = TypographyConfig(
            table_of_contents={"enabled": True, "depth": 2}
        )
        with patch.object(latex_module, "projects_source_root", self.test_dir):
            out = transform_xml_to_tex(f, typography=typography)
        self.assertIn(r"\tableofcontents", out)
        self.assertIn(r"\setcounter{tocdepth}{2}", out)

    def test_integrates_licenses_into_postamble(self):
        xml = b"""<?xml version="1.0"?>
        <tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"
                 xmlns:p="http://jewishliturgy.org/ns/processing"
                 p:project="p" p:file_name="input.xml">
          <tei:teiHeader><tei:fileDesc><tei:publicationStmt>
            <tei:availability>
              <tei:licence target="http://example.com/lic">My License</tei:licence>
            </tei:availability>
          </tei:publicationStmt></tei:fileDesc></tei:teiHeader>
          <tei:text><tei:body><tei:p>x</tei:p></tei:body></tei:text>
        </tei:TEI>"""
        f = self._create("p", "input.xml", xml)
        with patch.object(latex_module, "projects_source_root", self.test_dir):
            out = transform_xml_to_tex(f)
        self.assertIn(r"\section*{Metadata}", out)
        self.assertIn(r"\section*{Legal}", out)
        self.assertIn("My License", out)


if __name__ == "__main__":
    unittest.main()
