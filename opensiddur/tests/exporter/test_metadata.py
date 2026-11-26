"""Tests for the colophon model the output stages share (metadata.py).

How the PDF stage writes the model as TeX is tested in test_latex.py, how the electronic book
writes it as HTML in test_html_book.py; these test what both are given.
"""

import tempfile
import unittest
from pathlib import Path

from opensiddur.exporter.html.html import colophon_to_html, source_html
from opensiddur.exporter.metadata import (
    Colophon,
    CreditRecord,
    LicenseRecord,
    SourceRecord,
    build_colophon,
    extract_sources,
    group_licenses,
    order_credits,
)
from opensiddur.exporter.tex.latex import source_to_bibtex

TEI = "http://www.tei-c.org/ns/1.0"
P = "http://jewishliturgy.org/ns/processing"


def _index(*bibls: str) -> bytes:
    return (f'<tei:TEI xmlns:tei="{TEI}" xml:lang="en"><tei:teiHeader><tei:fileDesc>'
            f'<tei:sourceDesc>{"".join(bibls)}</tei:sourceDesc>'
            "</tei:fileDesc></tei:teiHeader></tei:TEI>").encode()


def _credit(role: str, contributor: str, name: str, namespace: str = "ns",
            resp: str = "") -> CreditRecord:
    return CreditRecord(role=role, resp_text=resp,
                        ref=f"urn:x-opensiddur:contributor:{namespace}/{contributor}",
                        name_text=name, namespace=namespace, contributor=contributor)


class _Projects(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base = Path(self.temp_dir.name)

    def _create(self, project: str, filename: str, content: bytes) -> Path:
        directory = self.base / project
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        path.write_bytes(content)
        return path

    def _sources(self, *bibls: str) -> list[SourceRecord]:
        return extract_sources([self._create("p", "index.xml", _index(*bibls))])


class TestExtractSources(_Projects):

    def test_a_printed_book(self):
        source, = self._sources(
            '<tei:bibl><tei:author>Philip  Birnbaum</tei:author>'
            '<tei:title type="main">ha-Siddur ha-Shalem</tei:title>'
            '<tei:title type="sub">The Daily Prayer Book</tei:title>'
            '<tei:edition>First</tei:edition><tei:publisher>Hebrew Publishing Company</tei:publisher>'
            '<tei:pubPlace><tei:ref target="https://example.org/ny">New York</tei:ref></tei:pubPlace>'
            '<tei:date when="1949">nineteen forty-nine</tei:date>'
            '<tei:idno type="ISBN">0-88482-054-6</tei:idno>'
            '<tei:idno type="archive.org">birnbaum1949</tei:idno></tei:bibl>')
        self.assertEqual(source, SourceRecord(
            key="philip1949", entry_type="book", title="ha-Siddur ha-Shalem",
            subtitle="The Daily Prayer Book", authors=["Philip Birnbaum"], edition="First",
            publisher="Hebrew Publishing Company", address=["New York"], date="1949",
            identifiers=[("ISBN", "0-88482-054-6"), ("archive.org", "birnbaum1949")]))

    def test_an_online_source_is_distributed_and_consulted(self):
        source, = self._sources(
            '<tei:bibl><tei:title>Bible</tei:title>'
            '<tei:distributor><tei:ref target="https://en.wikisource.org/">Wikisource</tei:ref>'
            '</tei:distributor><tei:date type="accessed" when="2025-07-27"/></tei:bibl>')
        self.assertEqual(
            (source.entry_type, source.distributor, source.url, source.urldate, source.date),
            ("online", "Wikisource", "https://en.wikisource.org/", "2025-07-27", ""))

    def test_a_distributor_is_dropped_when_there_is_a_publisher(self):
        source, = self._sources(
            "<tei:bibl><tei:title>T</tei:title><tei:publisher>Press</tei:publisher>"
            "<tei:distributor>Shop</tei:distributor></tei:bibl>")
        self.assertEqual((source.publisher, source.distributor), ("Press", ""))

    def test_notes_and_accession_numbers_are_remarks(self):
        source, = self._sources(
            '<tei:bibl><tei:title>Codex</tei:title><tei:note>First remark.</tei:note>'
            '<tei:note type="encoding">How the XML is made.</tei:note>'
            '<tei:idno type="Accession">B 19 A</tei:idno></tei:bibl>')
        self.assertEqual(source.notes, ["First remark.", "Accession: B 19 A"])
        self.assertEqual(source.identifiers, [])

    def test_values_are_left_unescaped(self):
        source, = self._sources("<tei:bibl><tei:title>Prayers &amp; 100% of_them</tei:title>"
                                "</tei:bibl>")
        self.assertEqual(source.title, "Prayers & 100% of_them")

    def test_a_pointer_back_to_the_index_is_not_a_source(self):
        self.assertEqual(self._sources(
            '<tei:bibl><tei:ptr target="index.xml"/><tei:biblScope unit="page">1</tei:biblScope>'
            "</tei:bibl>"), [])

    def test_keys_that_collide_in_one_index_are_told_apart(self):
        sources = self._sources(
            '<tei:bibl xml:id="facsimile_bibl"><tei:title>Scan</tei:title></tei:bibl>'
            "<tei:bibl><tei:title>Transcription</tei:title></tei:bibl>")
        self.assertEqual([s.key for s in sources], ["unknownnd-facsimilebibl", "unknownnd-2"])

    def test_the_same_work_in_two_projects_is_listed_once(self):
        bibl = "<tei:bibl><tei:author>Asher</tei:author><tei:title>Selichoth</tei:title>{}</tei:bibl>"
        sources = extract_sources([
            self._create("he", "index.xml", _index(bibl.format("<tei:note>Hebrew</tei:note>"))),
            self._create("en", "index.xml", _index(bibl.format("<tei:note>English</tei:note>")))])
        self.assertEqual([(s.key, s.notes) for s in sources], [("ashernd", ["English"])])

    def test_a_different_work_with_the_same_key_gets_a_key_of_its_own(self):
        sources = extract_sources([
            self._create(name, "index.xml",
                         _index(f"<tei:bibl><tei:author>Example</tei:author><tei:title>{name}"
                                "</tei:title><tei:date>1949</tei:date></tei:bibl>"))
            for name in ("one", "two")])
        self.assertEqual([s.key for s in sources], ["example1949", "example1949-2"])

    def test_an_unreadable_index_is_skipped(self):
        self.assertEqual(extract_sources([self._create("p", "index.xml", b"<not xml")]), [])


class TestOrderCredits(unittest.TestCase):

    def test_roles_namespaces_and_people_are_in_a_stable_order(self):
        ordered = order_credits({
            "trc": {"z.org": [_credit("trc", "b", "Bee", "z.org"), _credit("trc", "a", "Ay", "z.org")],
                    "a.org": [_credit("trc", "c", "Sea", "a.org")]},
            "aut": {"ns": [_credit("aut", "d", "Dee")]},
        })
        self.assertEqual([role.role for role in ordered], ["aut", "trc"])
        self.assertEqual([group.namespace for group in ordered[1].namespaces], ["a.org", "z.org"])
        self.assertEqual(ordered[1].names, ["Sea", "Ay", "Bee"])

    def test_headings_are_plural_for_more_than_one_person(self):
        ordered = order_credits({
            "aut": {"ns": [_credit("aut", "a", "A")]},
            "trc": {"x": [_credit("trc", "a", "A", "x")], "y": [_credit("trc", "b", "B", "y")]},
        })
        self.assertEqual([role.heading for role in ordered], ["Author", "Transcriptionists"])

    def test_an_unknown_role_is_called_what_the_document_calls_it(self):
        ordered = order_credits({"xyz": {"ns": [_credit("xyz", "a", "A", resp="Illuminated by")]}})
        self.assertEqual(ordered[0].heading, "Illuminated by")

    def test_the_documents_wording_takes_no_plural(self):
        ordered = order_credits({"xyz": {"ns": [_credit("xyz", "a", "A", resp="Illuminated by"),
                                                _credit("xyz", "b", "B", resp="Illuminated by")]}})
        self.assertEqual(ordered[0].heading, "Illuminated by")

    def test_one_person_credited_from_two_namespaces_is_one_person(self):
        ordered = order_credits({"trl": {"x": [_credit("trl", "bob", "Bob", "x")],
                                         "y": [_credit("trl", "bob", "Bob", "y")]}})
        self.assertEqual((ordered[0].heading, ordered[0].names), ("Translator", ["Bob"]))


class TestGroupLicenses(unittest.TestCase):

    def test_a_licence_with_no_name_is_called_by_its_url(self):
        grouped = group_licenses({Path("a"): LicenseRecord(url="http://x", name="")})
        self.assertEqual(grouped[0].name, "http://x")


class TestBuildColophon(_Projects):

    def test_credits_come_from_the_compiled_document_and_the_rest_from_the_sources(self):
        """Whoever the compiler did not carry into the book is not credited by it, even though a
        file the book refers to names them: the PDF and the electronic book credit the same
        people because they both read the book."""
        self._create("p", "index.xml", f"""<tei:TEI xmlns:tei="{TEI}" xml:lang="en">
          <tei:teiHeader><tei:fileDesc><tei:titleStmt><tei:title>I</tei:title>
          <tei:respStmt><tei:resp key="trc">Transcribed by</tei:resp>
          <tei:name ref="urn:x-opensiddur:contributor:ns/source-only">Source Only</tei:name>
          </tei:respStmt></tei:titleStmt>
          <tei:publicationStmt><tei:availability><tei:licence target="http://cc0">CC0</tei:licence>
          </tei:availability></tei:publicationStmt>
          <tei:sourceDesc><tei:bibl><tei:title>A Book</tei:title></tei:bibl></tei:sourceDesc>
          </tei:fileDesc></tei:teiHeader></tei:TEI>""".encode())
        compiled = self._create("out", "book.xml", f"""<tei:TEI xmlns:tei="{TEI}" xmlns:p="{P}"
          xml:lang="en" p:project="p" p:file_name="index.xml">
          <tei:teiHeader><tei:fileDesc><tei:titleStmt><tei:title>Book</tei:title>
          <tei:respStmt><tei:resp key="trc">Transcribed by</tei:resp>
          <tei:name ref="urn:x-opensiddur:contributor:ns/in-the-book">In The Book</tei:name>
          </tei:respStmt></tei:titleStmt></tei:fileDesc></tei:teiHeader>
          <tei:text><tei:body/></tei:text></tei:TEI>""".encode())
        colophon = build_colophon(compiled, self.base)
        self.assertEqual([role.names for role in colophon.credits], [["In The Book"]])
        self.assertEqual(colophon.licenses, [LicenseRecord(url="http://cc0", name="CC0")])
        self.assertEqual([source.title for source in colophon.sources], ["A Book"])


class TestSerialisers(unittest.TestCase):
    """One record, written both ways."""

    SOURCE = SourceRecord(
        key="heidenheim1822", entry_type="book", title="הגדה לליל שימורים",
        authors=["Wolf Heidenheim"], publisher="Heidenheim & Co.", address=["Rödelheim"],
        date="1822", url="https://example.org/a_b", identifiers=[("IBSN", "123")],
        notes=["Folio 2_40."])

    def test_bibtex(self):
        self.assertEqual(source_to_bibtex(self.SOURCE),
                         "@book{heidenheim1822,\n"
                         "  title = {\\texthebrew{הגדה לליל שימורים}},\n"
                         "  author = {Wolf Heidenheim},\n"
                         "  publisher = {Heidenheim \\& Co.},\n"
                         "  address = {Rödelheim},\n"
                         "  date = {1822},\n"
                         "  url = {https://example.org/a_b},\n"
                         "  isbn = {123},\n"
                         "  addendum = {Folio 2\\_40.},\n"
                         "}\n\n")

    def test_each_field_is_written_once(self):
        """A repeated field is an error to biber: a second identifier becomes a remark."""
        source = SourceRecord(key="k", entry_type="online", notes=["A note."],
                              identifiers=[("opensiddur.org", "101"), ("archive.org", "book"),
                                           ("ISBN", "1"), ("ISBN", "2")])
        bibtex = source_to_bibtex(source)
        names = [line.split(" = ")[0].strip() for line in bibtex.splitlines()[1:-1]]
        self.assertEqual(len(names), len(set(names)), bibtex)
        self.assertIn("  eprinttype = {opensiddur.org},\n  eprint = {101},\n", bibtex)
        self.assertIn("  addendum = {A note. archive.org: book ISBN: 2},\n", bibtex)

    def test_a_display_date_is_a_year(self):
        source = SourceRecord(key="k", entry_type="misc", date="March 3, 1822")
        self.assertIn("  year = {March 3, 1822},\n", source_to_bibtex(source))

    def test_online_distributor_is_an_organization(self):
        source = SourceRecord(key="k", entry_type="online", distributor="Wikisource")
        self.assertIn("  organization = {Wikisource},\n", source_to_bibtex(source))

    def test_html(self):
        self.assertEqual(source_html(self.SOURCE),
                         "Wolf Heidenheim. <cite><bdi>הגדה לליל שימורים</bdi></cite>. "
                         "Rödelheim, Heidenheim &amp; Co., 1822. ISBN: 123. "
                         '<a href="https://example.org/a_b">https://example.org/a_b</a>. '
                         "Folio 2_40.")

    def test_a_hebrew_phrase_is_one_run_across_its_punctuation(self):
        """Set as three runs, the words of the phrase would be laid out left to right. The
        closing parenthesis is part of the phrase that opened it (#338)."""
        source = SourceRecord(key="k", entry_type="misc", title='ספר "החינוך" (ה׳)')
        self.assertIn('  title = {\\texthebrew{ספר "החינוך" (ה׳)}},\n', source_to_bibtex(source))

    def test_a_right_to_left_mark_does_not_reach_the_bibliography(self):
        """The mark printed as a box in the Latin font, and kept the closing parenthesis
        out of the Hebrew run (#338)."""
        source = SourceRecord(key="k", entry_type="misc", title="לכה דודי (נוסח אחר)\u200f")
        self.assertIn("  title = {\\texthebrew{לכה דודי (נוסח אחר)}},\n",
                      source_to_bibtex(source))

    def test_bibliography_specials_are_escaped_inside_a_hebrew_run(self):
        source = SourceRecord(key="k", entry_type="misc", title="ספר & טוב")
        self.assertIn("  title = {\\texthebrew{ספר \\& טוב}},\n", source_to_bibtex(source))

    def test_html_a_full_stop_inside_markup_is_not_doubled(self):
        source = SourceRecord(key="k", entry_type="misc", title="Collected Works, ed.",
                              notes=["הערה."])
        self.assertEqual(source_html(source),
                         "<cite>Collected Works, ed</cite>. <bdi>הערה</bdi>.")

    def test_html_links_only_web_addresses(self):
        source = SourceRecord(key="k", entry_type="misc", url="javascript:alert(1)")
        self.assertEqual(source_html(source), "javascript:alert(1).")
        html = colophon_to_html("Book", Colophon(
            licenses=[LicenseRecord(url="urn:x-licence:cc0", name="CC0")], credits=[], sources=[]))
        self.assertIn("<li>CC0</li>", html)

    def test_html_names_editors_when_there_is_no_author(self):
        source = SourceRecord(key="k", entry_type="misc", title="T", editors=["A", "B"])
        self.assertEqual(source_html(source), "A and B (eds.). <cite>T</cite>.")

    def test_html_colophon_without_sources_has_no_sources_section(self):
        html = colophon_to_html("Book", Colophon(licenses=[], credits=[], sources=[]))
        self.assertNotIn("Sources", html)


if __name__ == "__main__":
    unittest.main()
