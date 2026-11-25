r"""The distribution notice on the title page's verso, and the statement after the colophon.

The settings, the helpers both output stages share, and how each stage sets them: the PDF
on its own pages (read off the ``.tex``, and in one test off a real PDF), the electronic
book after its title page and in its colophon. Every settings file and logo is made here.
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from opensiddur.exporter import books, notices, typography
from opensiddur.exporter.html.html import build_book, colophon_to_html, notice_line_html
from opensiddur.exporter.metadata import Colophon
from opensiddur.exporter.notices import RunKind
from opensiddur.exporter.settings import (
    DistributionNotice,
    DistributionSettings,
    SettingsYaml,
    validate_settings,
)
from opensiddur.exporter.tex.latex import (
    back_notice_to_tex,
    distribution_notice_to_tex,
    notice_line_to_tex,
    transform_xml_to_tex,
)
from opensiddur.tests.exporter.stylesheet_helpers import transform

TEI = "http://www.tei-c.org/ns/1.0"
P = "http://jewishliturgy.org/ns/processing"

# The smallest PNG there is: one transparent pixel.
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000005000100d2a8e0b5"
    "0000000049454e44ae426082"
)


def _settings(data: dict) -> SettingsYaml:
    return validate_settings(data, resolve_fonts=False, check_projects=False)


def _document(front: str = "", body: str = "<tei:p>In the beginning.</tei:p>") -> str:
    front = f"<tei:front>{front}</tei:front>" if front else ""
    return f"""<tei:TEI xmlns:tei="{TEI}" xmlns:p="{P}" xml:lang="en">
  <tei:text>{front}<tei:body>{body}</tei:body></tei:text>
</tei:TEI>"""


_TITLE_PAGE = ('<tei:titlePage><tei:docTitle><tei:titlePart type="main">THE BOOK'
               "</tei:titlePart></tei:docTitle></tei:titlePage>")
_COPYRIGHT_PAGE = ('<tei:titlePage type="copyright"><tei:docImprint>Copyright, 1917'
                   "</tei:docImprint></tei:titlePage>")
_PREFACE = "<tei:div><tei:p>The preface.</tei:p></tei:div>"

_NOTICE = "\\null\\vfill\n\\OSDistributionNotice{NOTICE}\n\n"
# The notice where it is set, not the macro where the preamble defines it.
_SET = "\\OSDistributionNotice{NOTICE}"


class TestSettings(unittest.TestCase):

    def test_by_default_a_book_carries_the_open_siddur_notice(self):
        notice = SettingsYaml().distribution.notice
        self.assertEqual(notice.logo, "default")
        self.assertEqual(notice.text, ["Distributed by The Open Siddur Project",
                                       "https://opensiddur.org",
                                       "https://github.com/opensiddur"])
        self.assertEqual(notice.position, "bottom")

    def test_by_default_the_back_notice_differs_between_print_and_electronic(self):
        back = SettingsYaml().distribution.back_notice
        self.assertIn("against printing sacred texts", back.electronic[0])
        self.assertIn("against making unnecessary printed copies", back.print[0])
        self.assertEqual(back.electronic[1], back.print[1])
        self.assertIn("_genizah_", back.print[1])

    def test_either_part_can_be_left_out(self):
        settings = _settings({"distribution": {"notice": "none", "back_notice": "none"}})
        self.assertIsNone(notices.distribution_notice(settings.distribution))
        self.assertEqual(notices.back_notice_items(settings.distribution, "print"), [])

    def test_a_part_can_be_set_and_the_rest_kept(self):
        settings = _settings({"distribution": {"notice": {"text": ["Ours"], "logo": "none"},
                                               "back_notice": {"print": ["Keep it"]}}})
        self.assertEqual(settings.distribution.notice.text, ["Ours"])
        self.assertEqual(settings.distribution.notice.logo_width, "1.25in")
        self.assertEqual(notices.back_notice_items(settings.distribution, "print"),
                         ["Keep it"])
        self.assertEqual(len(notices.back_notice_items(settings.distribution, "electronic")), 2)

    def test_unknown_or_malformed_settings_are_refused(self):
        for name, distribution in (
                ("unknown key", {"notice": {"colour": "red"}}),
                ("unknown section", {"colophon": {}}),
                ("position", {"notice": {"position": "left"}}),
                ("width", {"notice": {"logo_width": "wide"}}),
                ("logo format", {"notice": {"logo": "logo.svg"}}),
                ("logo name", {"notice": {"logo": "my#logo.png"}}),
                ("off is none", {"notice": "off"}),
                ("blank line", {"notice": {"text": ["One", " "]}}),
                ("blank statement", {"back_notice": {"print": [""]}})):
            with self.subTest(name), self.assertRaises(ValidationError):
                _settings({"distribution": distribution})


class TestHelpers(unittest.TestCase):

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.base = Path(temp_dir.name)

    def test_a_line_is_split_into_text_emphasis_and_urls(self):
        self.assertEqual(
            notices.notice_runs("Find a _genizah_ at https://example.org/a_b_c."),
            [(RunKind.TEXT, "Find a "), (RunKind.EMPHASIS, "genizah"),
             (RunKind.TEXT, " at "), (RunKind.URL, "https://example.org/a_b_c"),
             (RunKind.TEXT, ".")])
        self.assertEqual(notices.notice_runs("plain"), [(RunKind.TEXT, "plain")])

    def test_underscores_inside_words_and_urls_are_not_emphasis(self):
        self.assertEqual(notices.notice_runs("snake_case at https://x.org/a_b"),
                         [(RunKind.TEXT, "snake_case at "), (RunKind.URL, "https://x.org/a_b")])

    def test_a_url_keeps_a_parenthesis_it_opened(self):
        self.assertEqual(notices.notice_runs("(see https://w.org/Foo_(bar))."),
                         [(RunKind.TEXT, "(see "), (RunKind.URL, "https://w.org/Foo_(bar)"),
                          (RunKind.TEXT, ").")])

    def test_the_default_logo_is_the_packaged_one(self):
        logo = notices.resolve_logo(DistributionNotice(), None)
        self.assertEqual(logo, notices.OPEN_SIDDUR_LOGO)
        self.assertTrue(logo.is_file())

    def test_no_logo(self):
        self.assertIsNone(notices.resolve_logo(DistributionNotice(logo="none"), None))

    def test_a_logo_is_relative_to_its_settings_file(self):
        (self.base / "art").mkdir()
        (self.base / "art" / "logo.png").write_bytes(_PNG)
        settings_file = self.base / "settings.yaml"
        logo = notices.resolve_logo(DistributionNotice(logo="art/logo.png"), settings_file)
        self.assertEqual(logo, (self.base / "art" / "logo.png").resolve())

    def test_a_missing_logo_is_an_error(self):
        with self.assertRaisesRegex(FileNotFoundError, "missing.png"):
            notices.resolve_logo(DistributionNotice(logo="missing.png"),
                                 self.base / "settings.yaml")

    def _check(self, settings_file: Path, settings_directory: Path) -> books.BookResult:
        # Whatever fonts this machine has: the default chains' fonts are checked first, and a
        # machine without them (as CI is) would report those instead of the logo.
        with patch.object(typography, "_installed_font_families",
                          return_value=frozenset({"linux libertine o", "freeserif"})):
            return books.check(settings_file, settings_directory, self.base)

    def test_checking_a_book_reports_a_missing_logo(self):
        settings_directory = self.base / "settings"
        (settings_directory / "book").mkdir(parents=True)
        (self.base / "proj").mkdir()
        (self.base / "proj" / "index.xml").write_text("<x/>")
        settings_file = settings_directory / "book" / "edition.yaml"
        settings_file.write_text(
            "requires_processor: \">=0.1.0\"\n"
            "book:\n  project: proj\n  file_name: index.xml\n"
            "distribution:\n  notice:\n    logo: missing.png\n")
        result = self._check(settings_file, settings_directory)
        self.assertIsNotNone(result.error)
        self.assertIn("missing.png", result.error)

    def test_checking_a_book_reports_a_logo_that_is_not_an_image(self):
        settings_directory = self.base / "settings"
        (settings_directory / "book").mkdir(parents=True)
        (self.base / "proj").mkdir()
        (self.base / "proj" / "index.xml").write_text("<x/>")
        (settings_directory / "book" / "logo.png").write_text("not a picture")
        settings_file = settings_directory / "book" / "edition.yaml"
        settings_file.write_text(
            "requires_processor: \">=0.1.0\"\n"
            "book:\n  project: proj\n  file_name: index.xml\n"
            "distribution:\n  notice:\n    logo: logo.png\n")
        result = self._check(settings_file, settings_directory)
        self.assertIn("not a readable image", result.error or "")


class TestTex(unittest.TestCase):

    def test_a_line_is_escaped_and_its_urls_and_emphasis_set(self):
        self.assertEqual(notice_line_to_tex("50% of a _genizah_ & https://example.org/#top"),
                         r"50\% of a \emph{genizah} \& {\urlstyle{same}\url{https://example.org/\#top}}")

    def test_the_notice_has_the_logo_then_a_line_each(self):
        logo = Path("/art/logo.png")
        tex = distribution_notice_to_tex(DistributionNotice(), logo)
        self.assertEqual(
            tex,
            "\\null\\vfill\n"
            "\\OSDistributionNotice{\\includegraphics[width=1.25in]{" + logo.resolve().as_posix()
            + "}\\\\{}\n"
            "Distributed by The Open Siddur Project\\\\{}\n"
            "{\\urlstyle{same}\\url{https://opensiddur.org}}\\\\{}\n"
            "{\\urlstyle{same}\\url{https://github.com/opensiddur}}}\n\n")

    def test_the_notice_stands_where_it_is_asked_to(self):
        for position, above, below in (("top", "", "\\vfill"),
                                       ("center", "\\vfill", "\\vfill"),
                                       ("bottom", "\\vfill", "")):
            with self.subTest(position):
                tex = distribution_notice_to_tex(
                    DistributionNotice(position=position, text=["x"]), None)
                self.assertEqual(tex, f"\\null{above}\n\\OSDistributionNotice{{x}}\n{below}\n")

    def test_no_notice_is_nothing(self):
        self.assertEqual(distribution_notice_to_tex(None, None), "")
        self.assertEqual(back_notice_to_tex([]), "")

    def test_the_back_notice_is_a_page_of_its_own(self):
        tex = back_notice_to_tex(["One.", "A _genizah_."])
        self.assertTrue(tex.startswith("\\clearpage\n\\thispagestyle{empty}\n"))
        self.assertIn("\\item{} One.\n\\item{} A \\emph{genizah}.\n", tex)

    def test_a_line_beginning_with_a_bracket_is_not_an_argument(self):
        tex = distribution_notice_to_tex(DistributionNotice(text=["One", "[Two]"]), None)
        self.assertIn("One\\\\{}\n[Two]", tex)
        self.assertIn("\\item{} [Note]", back_notice_to_tex(["[Note]"]))

    def test_a_url_tex_cannot_read_is_percent_encoded(self):
        self.assertEqual(notice_line_to_tex("https://ex.org/a}b{c\\d^e"),
                         r"{\urlstyle{same}\url{https://ex.org/a\%7Db\%7Bc\%5Cd\%5Ee}}")

    def test_a_logo_under_a_directory_tex_cannot_name_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "#"):
            distribution_notice_to_tex(DistributionNotice(), Path("/books/#1/logo.png"))


class TestStylesheet(unittest.TestCase):

    def _transform(self, xml: str, notice: str = "NOTICE", back: str = "") -> str:
        return transform(xml, **{"distribution-notice": _NOTICE if notice else "",
                                 "back-notice": back})

    def test_the_notice_is_on_the_verso_of_the_title_page(self):
        out = self._transform(_document(_TITLE_PAGE + _PREFACE))
        title_end = out.index("\\end{titlepage}")
        notice = out.index(_SET)
        self.assertLess(title_end, notice)
        self.assertLess(notice, out.index("The preface."))
        page = out[title_end:out.index("The preface.")]
        self.assertIn("\\clearpage\n\\thispagestyle{empty}\n" + _NOTICE + "\\clearpage", page)

    def test_the_verso_is_not_a_titlepage_environment(self):
        """That resets the page counter, and would count the verso as a recto."""
        out = self._transform(_document(_TITLE_PAGE))
        self.assertEqual(out.count("\\begin{titlepage}"), 1)

    def test_the_notice_follows_the_first_title_page_only(self):
        out = self._transform(_document(_TITLE_PAGE + _COPYRIGHT_PAGE))
        self.assertEqual(out.count(_SET), 1)
        self.assertLess(out.index(_SET), out.index("Copyright, 1917"))

    def test_without_a_title_page_the_notice_opens_the_front_matter(self):
        out = self._transform(_document(_PREFACE))
        self.assertLess(out.index("\\frontmatter"), out.index(_SET))
        self.assertLess(out.index(_SET), out.index("The preface."))

    def test_without_front_matter_the_notice_opens_the_book(self):
        out = self._transform(_document())
        self.assertLess(out.index("\\frontmatter"), out.index(_SET))
        self.assertLess(out.index(_SET), out.index("\\mainmatter"))
        self.assertLess(out.index("\\mainmatter"), out.index("In the beginning."))

    def test_no_notice_leaves_the_book_as_it_was(self):
        self.assertEqual(self._transform(_document(_TITLE_PAGE), notice=""),
                         transform(_document(_TITLE_PAGE)))
        self.assertNotIn("\\frontmatter", self._transform(_document(), notice=""))

    def test_the_back_notice_follows_the_colophon(self):
        out = transform(_document(), **{"additional-postamble": "COLOPHON",
                                        "back-notice": "BACK"})
        self.assertLess(out.index("COLOPHON"), out.index("BACK"))
        self.assertLess(out.index("BACK"), out.index("\\end{document}"))


class TestTransform(unittest.TestCase):
    """What latex.py hands the stylesheet, from a settings file."""

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.base = Path(temp_dir.name)
        self.compiled = self.base / "compiled.xml"
        self.compiled.write_text(_document(_TITLE_PAGE))

    def _tex(self, settings: str | None) -> str:
        settings_file = None
        if settings is not None:
            settings_file = self.base / "settings.yaml"
            settings_file.write_text(settings)
        return transform_xml_to_tex(self.compiled, settings_file=settings_file,
                                    project_directory=self.base)

    def test_the_printed_book_carries_the_default_notices(self):
        tex = self._tex(None)
        self.assertIn("\\usepackage{graphicx}", tex)
        self.assertIn(
            f"\\includegraphics[width=1.25in]{{{notices.OPEN_SIDDUR_LOGO.resolve().as_posix()}}}",
            tex)
        self.assertIn("Distributed by The Open Siddur Project", tex)
        self.assertIn("against making unnecessary printed copies", tex)
        self.assertNotIn("against printing sacred texts", tex)

    def test_a_logo_is_found_beside_its_settings_file(self):
        (self.base / "mine.png").write_bytes(_PNG)
        tex = self._tex("distribution:\n  notice:\n    logo: mine.png\n    logo_width: 2cm\n")
        self.assertIn(
            f"\\includegraphics[width=2cm]{{{(self.base / 'mine.png').resolve().as_posix()}}}",
            tex)

    def test_none_leaves_both_out(self):
        tex = self._tex("distribution:\n  notice: none\n  back_notice: none\n")
        self.assertNotIn("\\OSDistributionNotice{", tex)
        self.assertNotIn("\\OSBackNotice{", tex)
        self.assertNotIn("genizah", tex)


class TestElectronicBook(unittest.TestCase):

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.base = Path(temp_dir.name)
        (self.base / "proj").mkdir()
        (self.base / "proj" / "index.xml").write_text(
            f'<tei:TEI xmlns:tei="{TEI}" xml:lang="en"><tei:teiHeader><tei:fileDesc>'
            "<tei:titleStmt><tei:title>T</tei:title></tei:titleStmt>"
            "</tei:fileDesc></tei:teiHeader><tei:text><tei:body/></tei:text></tei:TEI>")
        self.compiled = self.base / "compiled.xml"

    def _build(self, front: str = _TITLE_PAGE, settings: str | None = None) -> str:
        self.compiled.write_text(_document(front).replace(
            'xml:lang="en"',
            'xml:lang="en" p:destination="electronic" p:project="proj" p:file_name="index.xml"',
            1))
        settings_file = None
        if settings is not None:
            settings_file = self.base / "settings.yaml"
            settings_file.write_text(settings)
        return build_book(self.compiled, settings_file, self.base)

    def test_the_notice_follows_the_title_page(self):
        page = self._build(_TITLE_PAGE + _COPYRIGHT_PAGE + _PREFACE)
        self.assertEqual(page.count('<aside class="os-distribution">'), 1)
        self.assertLess(page.index("THE BOOK"), page.index('<aside class="os-distribution">'))
        self.assertLess(page.index('<aside class="os-distribution">'),
                        page.index("Copyright, 1917"))
        self.assertNotIn("@@DISTRIBUTION@@", page)

    def test_without_a_title_page_the_notice_opens_the_book(self):
        page = self._build(_PREFACE)
        self.assertLess(page.index('<aside class="os-distribution">'), page.index("The preface."))

    def test_the_logo_is_inlined(self):
        aside = self._build().split('<aside class="os-distribution">', 1)[1]
        self.assertRegex(aside, r'^<img src="data:image/png;base64,[A-Za-z0-9+/=]+" alt="" '
                                r'style="width: 1.25in">')
        self.assertIn('<p><a href="https://opensiddur.org">https://opensiddur.org</a></p>', aside)

    def test_a_cmyk_logo_is_inlined(self):
        from PIL import Image
        Image.new("CMYK", (8, 8)).save(self.base / "print.jpg")
        aside = self._build(settings="distribution:\n  notice:\n    logo: print.jpg\n")
        self.assertIn('<img src="data:image/png;base64,', aside)

    def test_the_back_notice_follows_the_software_notice(self):
        about = self._build().split('<footer class="os-about">', 1)[1].split("</footer>", 1)[0]
        self.assertLess(about.index("GNU Lesser General Public License"),
                        about.index('<ul class="os-back-notice">'))
        self.assertIn("against printing sacred texts", about)
        self.assertIn("<em>genizah</em>", about)
        self.assertNotIn("against making unnecessary printed copies", about)

    def test_none_leaves_both_out(self):
        page = self._build(settings="distribution:\n  notice: none\n  back_notice: none\n")
        self.assertNotIn("os-distribution\">", page)
        self.assertNotIn('<ul class="os-back-notice">', page)
        self.assertNotIn("@@DISTRIBUTION@@", page)

    def test_a_colophon_without_a_back_notice_is_as_it_was(self):
        colophon = Colophon(licenses=[], credits=[], sources=[])
        self.assertEqual(colophon_to_html("Book", colophon, back_notice=[]),
                         colophon_to_html("Book", colophon))

    def test_a_line_is_escaped_and_its_urls_and_emphasis_set(self):
        self.assertEqual(notice_line_html("A <b> _genizah_ https://x.org"),
                         'A &lt;b&gt; <em>genizah</em> <a href="https://x.org">https://x.org</a>')


@unittest.skipUnless(
    shutil.which("lualatex") and shutil.which("pdftotext"),
    "requires a real lualatex installation and pdftotext",
)
class TestPrintedPages(unittest.TestCase):
    """In a real PDF: the notice is page 2, the title page's verso; the back notice is last."""

    def test_the_notices_land_on_their_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "in.xml").write_text(_document(_TITLE_PAGE + _PREFACE))
            transform_xml_to_tex(work / "in.xml", output_file=str(work / "t.tex"),
                                 project_directory=work)
            done = subprocess.run(["lualatex", "-interaction=nonstopmode", "t.tex"],
                                  cwd=work, capture_output=True, text=True)
            if not (work / "t.pdf").exists():
                self.fail(f"lualatex failed:\n{done.stdout[-3000:]}")
            text = subprocess.run(["pdftotext", "-layout", "t.pdf", "-"], cwd=work,
                                  capture_output=True, text=True, check=True).stdout
        pages = text.split("\f")
        if not pages[-1].strip():
            pages = pages[:-1]
        self.assertIn("THE BOOK", pages[0])
        # "The" is set with a ligature, which pdftotext does not read back.
        self.assertIn("Open Siddur Project", pages[1])
        self.assertIn("https://github.com/opensiddur", pages[1])
        self.assertNotIn("preface.", pages[1])
        self.assertIn("preface.", pages[2])
        # Counted on from the title page, not restarted: the third page is a recto.
        self.assertEqual(pages[2].split()[0], "iii")
        self.assertIn("genizah", re.sub(r"\s+", " ", pages[-1]))
        self.assertNotIn("Metadata", pages[-1])


if __name__ == "__main__":
    unittest.main()
