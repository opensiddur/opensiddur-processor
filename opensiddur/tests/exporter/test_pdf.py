"""Tests for the PDF exporter module (LuaLaTeX + reledmac/reledpar pipeline)."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import ANY, MagicMock, Mock, patch

from opensiddur.exporter.pdf.pdf import (
    LOG_TAIL_LINES,
    _have_command,
    _run_bibtex,
    _run_lualatex,
    _run_manual_loop,
    compile_tex_to_pdf,
    export_to_pdf,
    generate_tex,
)
from opensiddur.exporter.settings import DistributionSettings
from opensiddur.exporter.typography import PaperType, TypographyConfig


class TestGenerateTex(unittest.TestCase):
    """Test the generate_tex function."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_dir = Path(self.temp_dir.name)

    def test_generate_tex_success(self):
        """generate_tex calls transform_xml_to_tex and propagates success."""
        input_file = self.test_dir / "input.xml"
        output_file = self.test_dir / "output.tex"
        input_file.write_text("<tei:TEI xmlns:tei='http://www.tei-c.org/ns/1.0'/>")

        def write_tex(path, output_file=None, **kwargs):
            if output_file:
                Path(output_file).write_text(r"\documentclass{book}")
            return r"\documentclass{book}"

        with patch(
            "opensiddur.exporter.pdf.pdf.transform_xml_to_tex",
            side_effect=write_tex,
        ) as mock_transform:
            result = generate_tex(input_file, output_file)

        self.assertTrue(result)
        self.assertTrue(output_file.exists())
        mock_transform.assert_called_once_with(
            str(input_file),
            output_file=str(output_file),
            settings_file=None,
            typography=TypographyConfig(),
            distribution=DistributionSettings(),
            project_directory=ANY,
        )

    def test_generate_tex_reads_the_settings_file(self):
        """The settings file's typography is what transform_xml_to_tex is given."""
        input_file = self.test_dir / "input.xml"
        output_file = self.test_dir / "output.tex"
        settings_file = self.test_dir / "settings.yaml"
        settings_file.write_text("typography:\n  page:\n    paper: a5paper\n")
        input_file.write_text("<tei:TEI xmlns:tei='http://www.tei-c.org/ns/1.0'/>")

        with patch("opensiddur.exporter.pdf.pdf.transform_xml_to_tex") as mock_transform:
            self.assertTrue(generate_tex(input_file, output_file, settings_file=settings_file))

        typography = mock_transform.call_args.kwargs["typography"]
        self.assertEqual(typography.page.paper, PaperType.A5PAPER)

    def test_generate_tex_passes_the_distribution_settings(self):
        """The notices come from the same settings file, which the logo's path is relative to."""
        input_file = self.test_dir / "input.xml"
        output_file = self.test_dir / "output.tex"
        settings_file = self.test_dir / "settings.yaml"
        settings_file.write_text("distribution:\n  notice: none\n")
        input_file.write_text("<tei:TEI xmlns:tei='http://www.tei-c.org/ns/1.0'/>")

        with patch("opensiddur.exporter.pdf.pdf.transform_xml_to_tex") as mock_transform:
            self.assertTrue(generate_tex(input_file, output_file, settings_file=settings_file))

        kwargs = mock_transform.call_args.kwargs
        self.assertEqual(kwargs["distribution"].notice, "none")
        self.assertEqual(kwargs["settings_file"], settings_file)

    def test_a_broken_settings_file_fails_before_transforming(self):
        """An unreadable or invalid settings file is an error, not the default typography."""
        input_file = self.test_dir / "input.xml"
        output_file = self.test_dir / "output.tex"
        input_file.write_text("<tei:TEI xmlns:tei='http://www.tei-c.org/ns/1.0'/>")
        for name, text in (("unparseable", ":\n: not yaml"),
                           ("invalid", "typography:\n  page:\n    paper: tabloid\n")):
            with self.subTest(name):
                settings_file = self.test_dir / f"{name}.yaml"
                settings_file.write_text(text)
                with patch("opensiddur.exporter.pdf.pdf.transform_xml_to_tex") as mock_transform, \
                        patch("sys.stderr") as stderr:
                    self.assertFalse(
                        generate_tex(input_file, output_file, settings_file=settings_file))
                mock_transform.assert_not_called()
                printed = "".join(call.args[0] for call in stderr.write.call_args_list)
                self.assertIn("Settings error", printed)

    def test_generate_tex_handles_exception(self):
        """generate_tex returns False when transform_xml_to_tex raises."""
        input_file = self.test_dir / "input.xml"
        output_file = self.test_dir / "output.tex"
        input_file.write_text("<tei:TEI xmlns:tei='http://www.tei-c.org/ns/1.0'/>")

        with patch(
            "opensiddur.exporter.pdf.pdf.transform_xml_to_tex",
            side_effect=RuntimeError("boom"),
        ):
            result = generate_tex(input_file, output_file)

        self.assertFalse(result)
        self.assertFalse(output_file.exists())


class TestCompileTexToPdf(unittest.TestCase):
    """compile_tex_to_pdf runs lualatex and copies the PDF out of the temp
    build directory.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_dir = Path(self.temp_dir.name)
        self.tex_file = self.test_dir / "test.tex"
        self.tex_file.write_text(r"\documentclass{book}\begin{document}Test\end{document}")
        self.output_pdf = self.test_dir / "out.pdf"

    def _have_command(self, name):
        return name in {"lualatex", "bibtex"}

    def _lualatex_run(self, cmd, **kwargs):
        """Simulate lualatex producing a PDF in -output-directory."""
        out_dir = next(
            Path(arg.split("=", 1)[1])
            for arg in cmd
            if arg.startswith("-output-directory=")
        )
        (out_dir / f"{self.tex_file.stem}.pdf").write_bytes(b"%PDF-1.4 fake")
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    def test_runs_lualatex(self):
        """When tools resolve on $PATH, lualatex produces the PDF."""
        with patch(
            "opensiddur.exporter.pdf.pdf._have_command",
            side_effect=self._have_command,
        ):
            with patch(
                "subprocess.run", side_effect=self._lualatex_run
            ) as mock_run:
                result = compile_tex_to_pdf(self.tex_file, self.output_pdf)

        self.assertTrue(result)
        self.assertTrue(self.output_pdf.exists())
        cmds = [c.args[0][0] for c in mock_run.call_args_list]
        self.assertIn("lualatex", cmds)
        self.assertNotIn("latexmk", cmds)

    def test_fails_when_lualatex_missing(self):
        """Without lualatex on $PATH, compile_tex_to_pdf returns False up-front."""
        with patch(
            "opensiddur.exporter.pdf.pdf._have_command",
            return_value=False,
        ):
            with patch("subprocess.run") as mock_run:
                result = compile_tex_to_pdf(self.tex_file, self.output_pdf)

        self.assertFalse(result)
        mock_run.assert_not_called()

    def test_returns_false_when_pdf_not_produced(self):
        """A run that doesn't write a PDF is treated as a failed build."""
        def lualatex_no_pdf(cmd, **kwargs):
            r = MagicMock()
            r.returncode = 0
            r.stdout = ""
            r.stderr = ""
            return r

        with patch(
            "opensiddur.exporter.pdf.pdf._have_command",
            side_effect=self._have_command,
        ):
            with patch("subprocess.run", side_effect=lualatex_no_pdf):
                result = compile_tex_to_pdf(self.tex_file, self.output_pdf)

        self.assertFalse(result)


class TestCompileTexToPdfManualLoop(unittest.TestCase):
    """Tests for the lualatex/bibtex build loop."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_dir = Path(self.temp_dir.name)
        self.tex_file = self.test_dir / "test.tex"
        self.tex_file.write_text(r"\documentclass{book}\begin{document}Test\end{document}")
        self.output_pdf = self.test_dir / "out.pdf"

    def _only_lualatex(self, name):
        return name in {"lualatex", "bibtex"}

    def _make_lualatex_run(self, aux_bib=False, rerun_passes=0):
        """Return a subprocess.run side_effect that simulates lualatex (and bibtex)."""
        call_count = [0]

        def side_effect(cmd, **kwargs):
            r = MagicMock()
            r.returncode = 0
            r.stdout = ""
            r.stderr = ""
            if cmd[0] == "lualatex":
                call_count[0] += 1
                out_dir = next(
                    Path(arg.split("=", 1)[1])
                    for arg in cmd
                    if arg.startswith("-output-directory=")
                )
                if call_count[0] == 1 and aux_bib:
                    (out_dir / f"{self.tex_file.stem}.aux").write_text("\\bibdata{job}\\n")
                if call_count[0] <= rerun_passes:
                    r.stdout = "Rerun to get cross-references right"
                (out_dir / f"{self.tex_file.stem}.pdf").write_bytes(b"%PDF fake")
            elif cmd[0] == "bibtex":
                r.stdout = ""
            return r

        return side_effect, call_count

    def test_manual_loop_runs_lualatex(self):
        side_effect, call_count = self._make_lualatex_run()
        with patch(
            "opensiddur.exporter.pdf.pdf._have_command",
            side_effect=self._only_lualatex,
        ):
            with patch("subprocess.run", side_effect=side_effect):
                result = compile_tex_to_pdf(self.tex_file, self.output_pdf)

        self.assertTrue(result)
        self.assertGreaterEqual(call_count[0], 1)

    def test_manual_loop_invokes_bibtex_when_aux_indicates_bibliography(self):
        """A first-pass .aux with \\bibdata triggers bibtex + at least one extra lualatex pass."""
        side_effect, _ = self._make_lualatex_run(aux_bib=True)
        with patch(
            "opensiddur.exporter.pdf.pdf._have_command",
            side_effect=self._only_lualatex,
        ):
            with patch("subprocess.run", side_effect=side_effect) as mock_run:
                compile_tex_to_pdf(self.tex_file, self.output_pdf)

        bibtex_calls = [c for c in mock_run.call_args_list if c.args[0][0] == "bibtex"]
        lualatex_calls = [
            c for c in mock_run.call_args_list if c.args[0][0] == "lualatex"
        ]
        self.assertEqual(len(bibtex_calls), 1)
        # At least 2 lualatex passes: the initial one plus the post-bibtex rerun.
        self.assertGreaterEqual(len(lualatex_calls), 2)

    def test_manual_loop_caps_at_max_runs(self):
        """The loop must not run lualatex more than max_runs times."""
        side_effect, call_count = self._make_lualatex_run(rerun_passes=99)
        with patch(
            "opensiddur.exporter.pdf.pdf._have_command",
            side_effect=self._only_lualatex,
        ):
            with patch("subprocess.run", side_effect=side_effect):
                compile_tex_to_pdf(self.tex_file, self.output_pdf, max_runs=3)

        self.assertLessEqual(call_count[0], 3)


class TestCompileTexToPdfRelativeTexFile(unittest.TestCase):
    """Regression tests for a tex_file given as a relative path with a
    directory component (e.g. from --tex-output build/intermediate.tex).

    _run_lualatex sets the subprocess cwd to tex_file.parent and
    pass only tex_file.name; if tex_file isn't resolved to an absolute path
    first, a relative "build/doc.tex" makes lualatex look for
    "build/build/doc.tex" relative to its cwd -- the bug this guards against.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_dir = Path(self.temp_dir.name)
        self.orig_cwd = os.getcwd()
        os.chdir(self.test_dir)
        self.addCleanup(os.chdir, self.orig_cwd)

        (self.test_dir / "build").mkdir()
        self.relative_tex_file = Path("build") / "doc.tex"
        self.relative_tex_file.write_text(
            r"\documentclass{book}\begin{document}Test\end{document}"
        )
        self.output_pdf = Path("out.pdf")

    def _only_lualatex(self, name):
        return name in {"lualatex", "bibtex"}

    def test_relative_tex_file_resolved_before_subprocess_split(self):
        def side_effect(cmd, **kwargs):
            self.assertEqual(cmd[-1], "doc.tex")
            self.assertTrue(Path(kwargs["cwd"]).is_absolute())
            out_dir = next(
                Path(arg.split("=", 1)[1]) for arg in cmd if arg.startswith("-output-directory=")
            )
            (out_dir / "doc.pdf").write_bytes(b"%PDF fake")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch(
            "opensiddur.exporter.pdf.pdf._have_command",
            side_effect=self._only_lualatex,
        ):
            with patch("subprocess.run", side_effect=side_effect):
                result = compile_tex_to_pdf(self.relative_tex_file, self.output_pdf)

        self.assertTrue(result)

    @unittest.skipUnless(
        shutil.which("lualatex") and shutil.which("bibtex"),
        "requires a real lualatex/bibtex installation",
    )
    def test_real_lualatex_finds_relative_tex_file(self):
        """End-to-end: no mocking, so this fails if lualatex genuinely can't
        find the .tex file -- the actual failure mode from the bug report."""
        result = compile_tex_to_pdf(self.relative_tex_file, self.output_pdf)

        self.assertTrue(result)
        self.assertTrue(self.output_pdf.exists())


@unittest.skipUnless(
    shutil.which("lualatex") and shutil.which("bibtex"),
    "requires a real lualatex/bibtex installation",
)
class TestBibliographyLineBreaking(unittest.TestCase):
    def test_long_archive_url_and_eprint_fit_the_text_block(self):
        from pypdf import PdfReader

        from opensiddur.tests.exporter.stylesheet_helpers import transform
        identifier = "PhilipBirnbaumHaSiddurHaShalemTheDailyPrayerBook1949"
        url = "https://archive.org/details/" + identifier
        bibliography = (
            r"\geometry{textwidth=240pt}" + "\n"
            + r"\begin{filecontents*}[overwrite]{\jobname.bib}" + "\n"
            + "@book{longarchive, title={A book}, author={An Author}, date={1949},"
            + "url={" + url + "}, eprinttype={archive.org}, eprint={" + identifier + "}}\n"
            + r"\end{filecontents*}" + "\n" + r"\addbibresource{\jobname.bib}"
        )
        xml = ('<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xml:lang="en">'
               '<tei:text><tei:body><tei:p>Bibliography regression.</tei:p>'
               '</tei:body></tei:text></tei:TEI>')
        tex = transform(xml, **{
            "additional-preamble": bibliography,
            "additional-postamble": r"\nocite{longarchive}\printbibliography",
        })
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "doc.tex"
            source.write_text(tex)
            pdf = root / "result.pdf"
            build = root / "build"
            self.assertTrue(compile_tex_to_pdf(source, pdf, build_dir=build))
            self.assertNotIn(r"Overfull \hbox", (build / "doc.log").read_text())
            reader = PdfReader(pdf)
            text = "".join("".join(page.extract_text().split()) for page in reader.pages)
            self.assertIn(identifier, text)
            self.assertIn("archive.org:" + identifier, text)
            links = [annotation.get_object().get("/A", {}).get("/URI")
                     for page in reader.pages for annotation in page.get("/Annots", [])]
            self.assertIn(url, links)


class TestExportToPdf(unittest.TestCase):
    """Test the export_to_pdf function."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_dir = Path(self.temp_dir.name)

    def test_export_to_pdf_success(self):
        input_file = self.test_dir / "input.xml"
        output_pdf = self.test_dir / "out.pdf"
        input_file.write_text("<tei:TEI xmlns:tei='http://www.tei-c.org/ns/1.0'/>")

        with patch(
            "opensiddur.exporter.pdf.pdf.generate_tex", return_value=True
        ) as mock_gen:
            with patch(
                "opensiddur.exporter.pdf.pdf.compile_tex_to_pdf", return_value=True
            ) as mock_compile:
                result = export_to_pdf(input_file, output_pdf)

        self.assertTrue(result)
        mock_gen.assert_called_once()
        mock_compile.assert_called_once()

    def test_export_to_pdf_forwards_settings_file_to_generate(self):
        """settings_file is forwarded to generate_tex (the consumer of typography)."""
        input_file = self.test_dir / "input.xml"
        output_pdf = self.test_dir / "out.pdf"
        settings_file = self.test_dir / "settings.yaml"
        input_file.write_text("<tei:TEI xmlns:tei='http://www.tei-c.org/ns/1.0'/>")

        with patch(
            "opensiddur.exporter.pdf.pdf.generate_tex", return_value=True
        ) as mock_gen:
            with patch(
                "opensiddur.exporter.pdf.pdf.compile_tex_to_pdf", return_value=True
            ):
                export_to_pdf(input_file, output_pdf, settings_file=settings_file)

        kwargs = mock_gen.call_args.kwargs
        self.assertEqual(kwargs.get("settings_file"), settings_file)

    def test_export_to_pdf_writes_intermediate_tex_when_requested(self):
        """When tex_output is provided, generate_tex writes to that path and it is kept."""
        input_file = self.test_dir / "input.xml"
        output_pdf = self.test_dir / "out.pdf"
        tex_output = self.test_dir / "intermediate.tex"
        input_file.write_text("<tei:TEI xmlns:tei='http://www.tei-c.org/ns/1.0'/>")

        with patch("opensiddur.exporter.pdf.pdf.generate_tex", return_value=True) as mock_gen:
            with patch("opensiddur.exporter.pdf.pdf.compile_tex_to_pdf", return_value=True):
                result = export_to_pdf(input_file, output_pdf, tex_output=tex_output)

        self.assertTrue(result)
        self.assertEqual(mock_gen.call_args.args[1], tex_output)

    def test_export_to_pdf_input_file_not_found(self):
        input_file = self.test_dir / "nope.xml"
        output_pdf = self.test_dir / "out.pdf"

        result = export_to_pdf(input_file, output_pdf)

        self.assertFalse(result)

    def test_export_to_pdf_generate_tex_failure(self):
        input_file = self.test_dir / "input.xml"
        output_pdf = self.test_dir / "out.pdf"
        input_file.write_text("<tei:TEI xmlns:tei='http://www.tei-c.org/ns/1.0'/>")

        with patch(
            "opensiddur.exporter.pdf.pdf.generate_tex", return_value=False
        ):
            result = export_to_pdf(input_file, output_pdf)

        self.assertFalse(result)

    def test_export_to_pdf_compile_failure(self):
        input_file = self.test_dir / "input.xml"
        output_pdf = self.test_dir / "out.pdf"
        input_file.write_text("<tei:TEI xmlns:tei='http://www.tei-c.org/ns/1.0'/>")

        with patch(
            "opensiddur.exporter.pdf.pdf.generate_tex", return_value=True
        ):
            with patch(
                "opensiddur.exporter.pdf.pdf.compile_tex_to_pdf", return_value=False
            ):
                result = export_to_pdf(input_file, output_pdf)

        self.assertFalse(result)


class TestHaveCommand(unittest.TestCase):
    def test_returns_true_when_command_on_path(self):
        with patch("opensiddur.exporter.pdf.pdf.shutil.which", return_value="/usr/bin/lualatex"):
            self.assertTrue(_have_command("lualatex"))

    def test_returns_false_when_command_missing(self):
        with patch("opensiddur.exporter.pdf.pdf.shutil.which", return_value=None):
            self.assertFalse(_have_command("missing-tool"))


class TestRunLualatex(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_dir = Path(self.temp_dir.name)
        self.tex_file = self.test_dir / "doc.tex"
        self.tex_file.write_text(r"\documentclass{book}\begin{document}X\end{document}")
        self.output_dir = self.test_dir / "build"
        self.output_dir.mkdir()

    def test_detects_rerun_markers_from_log(self):
        def side_effect(cmd, **kwargs):
            out_dir = Path(next(arg.split("=", 1)[1] for arg in cmd if arg.startswith("-output-directory=")))
            (out_dir / "doc.log").write_text("Rerun to get cross-references right")
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=side_effect):
            success, output, needs_rerun = _run_lualatex(self.tex_file, self.output_dir)

        self.assertTrue(success)
        self.assertTrue(needs_rerun)
        self.assertIn("Rerun to get cross-references right", output)

    def test_handles_log_read_failure(self):
        log_path = self.output_dir / "doc.log"

        def side_effect(cmd, **kwargs):
            log_path.write_text("ok")
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=side_effect):
            with patch.object(
                type(log_path),
                "read_text",
                side_effect=OSError("cannot read log"),
            ):
                success, output, needs_rerun = _run_lualatex(self.tex_file, self.output_dir)

        self.assertTrue(success)
        self.assertEqual(output, "")
        self.assertFalse(needs_rerun)

    def test_reports_lualatex_failure(self):
        with patch("subprocess.run", return_value=MagicMock(returncode=1)):
            success, output, needs_rerun = _run_lualatex(self.tex_file, self.output_dir)

        self.assertFalse(success)
        self.assertFalse(needs_rerun)

    def test_passes_basename_with_cwd_set_to_parent(self):
        """The file argument must be a bare filename, not a path including
        tex_file.parent -- cwd is already set to that parent, so passing the
        full path makes lualatex look for <parent>/<parent>/doc.tex."""
        with patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            _run_lualatex(self.tex_file, self.output_dir)

        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd[-1], "doc.tex")
        self.assertEqual(mock_run.call_args.kwargs["cwd"], self.tex_file.parent)

    def test_manual_loop_waits_for_toc_pages_even_without_log_markers(self):
        toc = self.output_dir / 'doc.toc'
        contents = iter([b'heading page 64', b'heading page 63', b'heading page 63'])
        def run(*args, **kwargs):
            toc.write_bytes(next(contents))
            return Mock(returncode=0)
        with patch('subprocess.run', side_effect=run) as command:
            self.assertTrue(_run_manual_loop(self.tex_file, self.output_dir, max_runs=5))
        self.assertEqual(3, command.call_count)

    def test_unchanged_toc_does_not_force_another_pass(self):
        toc = self.output_dir / 'doc.toc'
        toc.write_bytes(b'heading page 63')
        def run(*args, **kwargs):
            toc.write_bytes(b'heading page 63')
            return Mock(returncode=0)
        with patch('subprocess.run', side_effect=run) as command:
            self.assertTrue(_run_manual_loop(self.tex_file, self.output_dir, max_runs=5))
        self.assertEqual(1, command.call_count)


class TestRunBibtex(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.output_dir = Path(self.temp_dir.name)

    def test_skips_when_aux_missing(self):
        with patch("subprocess.run") as mock_run:
            self.assertTrue(_run_bibtex("doc", self.output_dir))
        mock_run.assert_not_called()

    def test_skips_when_aux_has_no_bibliography(self):
        (self.output_dir / "doc.aux").write_text("\\relax")
        with patch("subprocess.run") as mock_run:
            self.assertTrue(_run_bibtex("doc", self.output_dir))
        mock_run.assert_not_called()

    def test_skips_when_aux_has_only_biblatex_control_entries(self):
        """biblatex writes these into every .aux, sources or none."""
        (self.output_dir / "doc.aux").write_text(
            "\\bibdata{doc-blx}\n\\citation{biblatex-control}\n"
        )
        with patch("subprocess.run") as mock_run:
            self.assertTrue(_run_bibtex("doc", self.output_dir))
        mock_run.assert_not_called()

    def test_runs_bibtex_for_the_documents_own_database(self):
        (self.output_dir / "doc.aux").write_text(
            "\\bibdata{doc-blx,doc}\n\\citation{biblatex-control}\n"
        )
        result = MagicMock(returncode=0, stdout="")
        with patch("opensiddur.exporter.pdf.pdf._have_command", return_value=True):
            with patch("subprocess.run", return_value=result) as mock_run:
                self.assertTrue(_run_bibtex("doc", self.output_dir))
        mock_run.assert_called_once()

    def test_runs_bibtex_when_aux_indicates_bibliography(self):
        (self.output_dir / "doc.aux").write_text("\\bibdata{job}")
        result = MagicMock(returncode=0, stdout="")
        with patch("opensiddur.exporter.pdf.pdf._have_command", return_value=True):
            with patch("subprocess.run", return_value=result) as mock_run:
                self.assertTrue(_run_bibtex("doc", self.output_dir))
        self.assertEqual(mock_run.call_args.args[0][0], "bibtex")

    def test_error_exit_status_fails(self):
        """bibtex exits 2 on an error, and the .bbl it leaves is unusable."""
        (self.output_dir / "doc.aux").write_text("\\citation{ref}")
        result = MagicMock(returncode=2, stdout="I couldn't open database file doc.bib")
        with patch("opensiddur.exporter.pdf.pdf._have_command", return_value=True):
            with patch("subprocess.run", return_value=result):
                self.assertFalse(_run_bibtex("doc", self.output_dir))

    def test_warning_exit_status_succeeds(self):
        (self.output_dir / "doc.aux").write_text("\\citation{ref}")
        result = MagicMock(returncode=1, stdout="Warning--empty year in ref")
        with patch("opensiddur.exporter.pdf.pdf._have_command", return_value=True):
            with patch("subprocess.run", return_value=result):
                self.assertTrue(_run_bibtex("doc", self.output_dir))

    def test_timeout_fails(self):
        (self.output_dir / "doc.aux").write_text("\\citation{ref}")
        with patch("opensiddur.exporter.pdf.pdf._have_command", return_value=True):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("bibtex", 1)):
                self.assertFalse(_run_bibtex("doc", self.output_dir))

    def test_reports_bibtex_errors(self):
        (self.output_dir / "doc.aux").write_text("\\citation{ref}")
        result = MagicMock(returncode=0, stdout="error message in output")
        with patch("opensiddur.exporter.pdf.pdf._have_command", return_value=True):
            with patch("subprocess.run", return_value=result) as mock_run:
                self.assertFalse(_run_bibtex("doc", self.output_dir))
        mock_run.assert_called_once()


class TestRunManualLoop(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_dir = Path(self.temp_dir.name)
        self.tex_file = self.test_dir / "doc.tex"
        self.tex_file.write_text(r"\documentclass{book}\begin{document}X\end{document}")
        self.output_dir = self.test_dir / "build"
        self.output_dir.mkdir()

    def test_returns_false_when_first_pass_fails(self):
        with patch(
            "opensiddur.exporter.pdf.pdf._run_lualatex",
            return_value=(False, "log output", False),
        ):
            self.assertFalse(_run_manual_loop(self.tex_file, self.output_dir, max_runs=3))

    def test_returns_false_when_later_pass_fails(self):
        with patch(
            "opensiddur.exporter.pdf.pdf._run_lualatex",
            side_effect=[
                (True, "", True),
                (False, "later pass failed", False),
            ],
        ):
            self.assertFalse(_run_manual_loop(self.tex_file, self.output_dir, max_runs=3))

    def test_warns_when_max_runs_reached(self):
        with patch(
            "opensiddur.exporter.pdf.pdf._run_lualatex",
            return_value=(True, "Rerun to get cross-references right", True),
        ):
            with patch("sys.stderr", new_callable=Mock) as mock_stderr:
                self.assertTrue(_run_manual_loop(self.tex_file, self.output_dir, max_runs=2))

        stderr_output = "".join(str(c) for c in mock_stderr.write.call_args_list)
        self.assertIn("max_runs", stderr_output)

    def test_no_max_runs_warning_when_the_last_pass_settles(self):
        with patch(
            "opensiddur.exporter.pdf.pdf._run_lualatex",
            side_effect=[(True, "", True), (True, "", False)],
        ):
            with patch("sys.stderr", new_callable=Mock) as mock_stderr:
                self.assertTrue(_run_manual_loop(self.tex_file, self.output_dir, max_runs=2))

        stderr_output = "".join(str(c) for c in mock_stderr.write.call_args_list)
        self.assertNotIn("max_runs", stderr_output)

    def test_bibtex_failure_fails_the_loop(self):
        (self.output_dir / "doc.aux").write_text("\\bibdata{doc}")
        with patch(
            "opensiddur.exporter.pdf.pdf._run_lualatex", return_value=(True, "", False)
        ) as lualatex:
            with patch("opensiddur.exporter.pdf.pdf._run_bibtex", return_value=False):
                self.assertFalse(_run_manual_loop(self.tex_file, self.output_dir, max_runs=3))
        self.assertEqual(1, lualatex.call_count)

    def test_failure_prints_only_the_end_of_the_log(self):
        log = "\n".join(f"line {n}" for n in range(1000))
        with patch(
            "opensiddur.exporter.pdf.pdf._run_lualatex", return_value=(False, log, False)
        ):
            with patch("sys.stderr", new_callable=Mock) as mock_stderr:
                self.assertFalse(_run_manual_loop(self.tex_file, self.output_dir, max_runs=3))

        stderr_output = "".join(str(c) for c in mock_stderr.write.call_args_list)
        self.assertIn("line 999", stderr_output)
        first_printed = 1000 - LOG_TAIL_LINES
        self.assertIn(f"line {first_printed}", stderr_output)
        self.assertNotIn(f"line {first_printed - 1}", stderr_output)


class TestCompileTexToPdfEdgeCases(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_dir = Path(self.temp_dir.name)
        self.tex_file = self.test_dir / "doc.tex"
        self.tex_file.write_text(r"\documentclass{book}\begin{document}X\end{document}")

    def _tools_available(self, name):
        return name in {"lualatex", "bibtex"}

    def test_uses_build_dir_when_provided(self):
        build_dir = self.test_dir / "build"
        output_pdf = self.test_dir / "out.pdf"

        with patch(
            "opensiddur.exporter.pdf.pdf._have_command",
            side_effect=self._tools_available,
        ):
            with patch(
                "opensiddur.exporter.pdf.pdf._run_manual_loop",
                return_value=True,
            ) as mock_loop:
                with patch(
                    "opensiddur.exporter.pdf.pdf.shutil.copy2",
                ) as mock_copy:
                    build_dir.mkdir()
                    (build_dir / "doc.pdf").write_bytes(b"%PDF fake")
                    result = compile_tex_to_pdf(
                        self.tex_file,
                        output_pdf,
                        build_dir=build_dir,
                    )

        self.assertTrue(result)
        self.assertTrue(build_dir.exists())
        mock_loop.assert_called_once_with(self.tex_file, build_dir, 6)
        mock_copy.assert_called_once()

    def test_bibtex_is_not_required_without_a_bibliography(self):
        def have(name):
            return name == "lualatex"

        def run(cmd, **kwargs):
            out_dir = Path(next(a.split("=", 1)[1] for a in cmd if a.startswith("-output-directory=")))
            (out_dir / "doc.aux").write_text("\\relax")
            (out_dir / "doc.pdf").write_bytes(b"%PDF fake")
            return MagicMock(returncode=0)

        with patch("opensiddur.exporter.pdf.pdf._have_command", side_effect=have):
            with patch("subprocess.run", side_effect=run) as mock_run:
                result = compile_tex_to_pdf(self.tex_file, self.test_dir / "out.pdf")

        self.assertTrue(result)
        self.assertEqual({"lualatex"}, {c.args[0][0] for c in mock_run.call_args_list})

    def test_fails_when_a_bibliography_needs_missing_bibtex(self):
        def have(name):
            return name == "lualatex"

        def run(cmd, **kwargs):
            out_dir = Path(next(a.split("=", 1)[1] for a in cmd if a.startswith("-output-directory=")))
            (out_dir / "doc.aux").write_text("\\bibdata{doc}")
            (out_dir / "doc.pdf").write_bytes(b"%PDF fake")
            return MagicMock(returncode=0)

        with patch("opensiddur.exporter.pdf.pdf._have_command", side_effect=have):
            with patch("subprocess.run", side_effect=run):
                result = compile_tex_to_pdf(self.tex_file, self.test_dir / "out.pdf")

        self.assertFalse(result)

    def test_lualatex_timeout_fails_the_build(self):
        with patch("opensiddur.exporter.pdf.pdf._have_command", return_value=True):
            with patch(
                "subprocess.run", side_effect=subprocess.TimeoutExpired("lualatex", 1)
            ):
                result = compile_tex_to_pdf(self.tex_file, self.test_dir / "out.pdf")

        self.assertFalse(result)

    def test_fails_when_manual_loop_fails(self):
        with patch(
            "opensiddur.exporter.pdf.pdf._have_command",
            side_effect=self._tools_available,
        ):
            with patch(
                "opensiddur.exporter.pdf.pdf._run_manual_loop",
                return_value=False,
            ):
                result = compile_tex_to_pdf(self.tex_file, self.test_dir / "out.pdf")

        self.assertFalse(result)

    def test_skips_copy_when_output_pdf_is_build_artifact(self):
        build_dir = self.test_dir / "build"
        output_pdf = build_dir / "doc.pdf"

        with patch(
            "opensiddur.exporter.pdf.pdf._have_command",
            side_effect=self._tools_available,
        ):
            with patch(
                "opensiddur.exporter.pdf.pdf._run_manual_loop",
                return_value=True,
            ):
                with patch("opensiddur.exporter.pdf.pdf.shutil.copy2") as mock_copy:
                    build_dir.mkdir(parents=True)
                    output_pdf.write_bytes(b"%PDF fake")
                    result = compile_tex_to_pdf(
                        self.tex_file,
                        output_pdf,
                        build_dir=build_dir,
                    )

        self.assertTrue(result)
        mock_copy.assert_not_called()

    def test_handles_file_not_found_error(self):
        with patch(
            "opensiddur.exporter.pdf.pdf._have_command",
            side_effect=self._tools_available,
        ):
            with patch(
                "opensiddur.exporter.pdf.pdf._run_manual_loop",
                return_value=True,
            ):
                with patch(
                    "opensiddur.exporter.pdf.pdf.shutil.copy2",
                    side_effect=FileNotFoundError("lualatex"),
                ):
                    with patch("tempfile.TemporaryDirectory") as mock_temp:
                        temp_path = self.test_dir / "tempbuild"
                        temp_path.mkdir()
                        mock_temp.return_value.__enter__.return_value = str(temp_path)
                        (temp_path / "doc.pdf").write_bytes(b"%PDF fake")
                        result = compile_tex_to_pdf(
                            self.tex_file,
                            self.test_dir / "out.pdf",
                        )

        self.assertFalse(result)

    def test_handles_unexpected_exception(self):
        with patch(
            "opensiddur.exporter.pdf.pdf._have_command",
            side_effect=RuntimeError("unexpected"),
        ):
            result = compile_tex_to_pdf(self.tex_file, self.test_dir / "out.pdf")

        self.assertFalse(result)


class TestExportToPdfExtras(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.test_dir = Path(self.temp_dir.name)

    def test_forwards_build_dir_to_compile(self):
        input_file = self.test_dir / "input.xml"
        output_pdf = self.test_dir / "out.pdf"
        build_dir = self.test_dir / "build"
        input_file.write_text("<tei:TEI xmlns:tei='http://www.tei-c.org/ns/1.0'/>")

        with patch("opensiddur.exporter.pdf.pdf.generate_tex", return_value=True):
            with patch(
                "opensiddur.exporter.pdf.pdf.compile_tex_to_pdf",
                return_value=True,
            ) as mock_compile:
                export_to_pdf(input_file, output_pdf, build_dir=build_dir)

        self.assertEqual(mock_compile.call_args.kwargs.get("build_dir"), build_dir)

    def test_prints_intermediate_tex_message(self):
        input_file = self.test_dir / "input.xml"
        output_pdf = self.test_dir / "out.pdf"
        tex_output = self.test_dir / "intermediate.tex"
        input_file.write_text("<tei:TEI xmlns:tei='http://www.tei-c.org/ns/1.0'/>")

        with patch("opensiddur.exporter.pdf.pdf.generate_tex", return_value=True):
            with patch("opensiddur.exporter.pdf.pdf.compile_tex_to_pdf", return_value=True):
                with patch("sys.stderr", new_callable=Mock) as mock_stderr:
                    export_to_pdf(input_file, output_pdf, tex_output=tex_output)

        stderr_output = "".join(str(c) for c in mock_stderr.write.call_args_list)
        self.assertIn("Intermediate TeX saved to", stderr_output)


if __name__ == "__main__":
    unittest.main()
