#!/usr/bin/env python3
"""
JLPTEI to PDF Exporter (LuaLaTeX + reledmac/reledpar pipeline).

Compilation strategy
====================
The reledmac/reledpar packages produce auxiliary files (``.<n>.aux`` files,
``.lineenum``, etc.) that need multiple LaTeX passes to converge. The build
runs ``lualatex`` up to ``max_runs`` times, until the log stops asking for a
rerun and the table of contents stops changing, invoking ``bibtex`` once after
the first pass when the ``.aux`` shows the document cites anything.

latexmk is not used: it detects a ``.bcf`` and tries biber even when biblatex is
configured for BibTeX, and biber is often missing or broken on a minimal system.
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import nullcontext
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from pydantic import ValidationError  # noqa: E402

from opensiddur.common.constants import PROJECT_DIRECTORY  # noqa: E402
from opensiddur.exporter.cli_common import (  # noqa: E402
    TYPOGRAPHY_SETTINGS_HELP,
    SettingsError,
    add_settings_arguments,
    load_output_settings,
)
from opensiddur.exporter.tex.latex import transform_xml_to_tex  # noqa: E402


def generate_tex(
    input_file: Path,
    temp_tex_file: Path,
    settings_file: Path | None = None,
    project_directory: Path = PROJECT_DIRECTORY,
) -> bool:
    """Generate a LuaLaTeX file from compiled JLPTEI XML.

    Args:
        input_file: Path to the compiled JLPTEI XML file.
        temp_tex_file: Path to the temporary .tex file to create.
        settings_file: Optional settings.yaml whose ``typography`` section
            drives the LuaLaTeX preamble, and whose ``distribution`` section the
            notices on the title page's verso and the last page.

    Returns:
        True on success, False otherwise.
    """
    # Outside the blanket handler below, so that a settings error says which setting and why.
    try:
        settings = load_output_settings(settings_file, resolve_fonts=True)
    except (SettingsError, ValidationError) as e:
        print(f"Settings error: {e}", file=sys.stderr)
        return False
    try:
        print(f"Generating LuaLaTeX from {input_file}...", file=sys.stderr)
        transform_xml_to_tex(
            str(input_file),
            output_file=str(temp_tex_file),
            settings_file=settings_file,
            typography=settings.typography,
            distribution=settings.distribution,
            project_directory=project_directory,
        )
        print(f"TeX file generated: {temp_tex_file}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"Error generating TeX: {e}", file=sys.stderr)
        return False


# A pass over a whole Humash takes minutes; one that has run for an hour is waiting
# for something that will not come (a font, a file, a terminal).
LUALATEX_TIMEOUT_SECONDS = 3600
BIBTEX_TIMEOUT_SECONDS = 300

# How much of a failed pass's log to print. The error is at the end, and a whole
# log runs to tens of thousands of lines.
LOG_TAIL_LINES = 60


class BuildError(Exception):
    """A step of the TeX build failed; the message says which and why."""


def _log_tail(output: str, lines: int = LOG_TAIL_LINES) -> str:
    return "\n".join(output.splitlines()[-lines:])


def _have_command(name: str) -> bool:
    """Return True iff ``name`` resolves on $PATH."""
    return shutil.which(name) is not None


def _run_lualatex(tex_file: Path, output_dir: Path) -> tuple[bool, str, bool]:
    """Run a single ``lualatex`` pass.

    Returns ``(succeeded, output, needs_rerun)``. ``succeeded`` reflects exit
    code; ``needs_rerun`` is True when the log contains rerun indicators
    or the table of contents changed during this pass. Pagination changes can
    leave stale TOC pages without producing a log warning.
    """
    cmd = [
        "lualatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        f"-output-directory={output_dir}",
        tex_file.name,
    ]
    log_path = output_dir / f"{tex_file.stem}.log"
    print(f"(LuaLaTeX log: {log_path})", file=sys.stderr)

    # Stream output live so long passes are observable. We later parse the .log
    # file for rerun markers (more reliable than stdout).
    toc_path = output_dir / f"{tex_file.stem}.toc"
    previous_toc = toc_path.read_bytes() if toc_path.exists() else None
    try:
        result = subprocess.run(
            cmd, text=True, cwd=tex_file.parent, timeout=LUALATEX_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired as e:
        raise BuildError(
            f"lualatex did not finish within {LUALATEX_TIMEOUT_SECONDS} seconds; see {log_path}"
        ) from e
    output = ""
    if log_path.exists():
        try:
            output = log_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            output = ""
    needs_rerun = any(
        marker in output
        for marker in (
            "Rerun to get cross-references right",
            "Rerun to get outlines right",
            "There were undefined references",
            "Label(s) may have changed",
            "Rerun to get citations correct",
            # reledmac/reledpar specific
            "Reledmac will work only after",
            "reledpar may not have created",
        )
    )
    if toc_path.exists() and toc_path.read_bytes() != previous_toc:
        needs_rerun = True
    return result.returncode == 0, output, needs_rerun


# biblatex writes its own control database (``<job>-blx``) and a ``biblatex-control``
# citation into every .aux, sources or none, so neither says the document cites anything.
_BIBDATA = re.compile(r"\\bibdata\{([^}]*)\}")
_CITATION = re.compile(r"\\citation\{([^}]*)\}")


def _needs_bibliography(tex_stem: str, output_dir: Path) -> bool:
    """Whether the first pass's .aux names a database or a citation of the document's own."""
    aux = output_dir / f"{tex_stem}.aux"
    if not aux.exists():
        return False
    aux_content = aux.read_text(encoding="utf-8", errors="ignore")
    databases = [
        name.strip()
        for names in _BIBDATA.findall(aux_content)
        for name in names.split(",")
    ]
    citations = [
        key.strip()
        for keys in _CITATION.findall(aux_content)
        for key in keys.split(",")
    ]
    return any(name and not name.endswith("-blx") for name in databases) or any(
        key and key != "biblatex-control" for key in citations
    )


def _run_bibtex(tex_stem: str, output_dir: Path) -> bool:
    """Run bibtex if the .aux indicates a bibliography is needed.

    Returns False when bibtex is needed and failed. Its exit status is 1 for a
    warning, which leaves a usable .bbl, and 2 or more for an error, which does not.
    """
    if not _needs_bibliography(tex_stem, output_dir):
        return True
    if not _have_command("bibtex"):
        print(
            "Error: the document has a bibliography but bibtex was not found. "
            "Install texlive-binaries.",
            file=sys.stderr,
        )
        return False

    cmd = ["bibtex", tex_stem]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=output_dir, timeout=BIBTEX_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired:
        print(f"Error: bibtex did not finish within {BIBTEX_TIMEOUT_SECONDS} seconds", file=sys.stderr)
        return False
    if result.returncode >= 2 or "error message" in (result.stdout or "").lower():
        print(f"BibTeX errors:\n{result.stdout}", file=sys.stderr)
        return False
    return True


def _run_manual_loop(tex_file: Path, output_dir: Path, max_runs: int) -> bool:
    """The build loop: lualatex, bibtex if needed, then lualatex until it settles.

    Runs lualatex once, then bibtex if the ``.aux`` cites anything, then keeps
    running lualatex until the rerun markers stop appearing or ``max_runs`` is hit.
    """
    tex_stem = tex_file.stem
    log_path = output_dir / f"{tex_stem}.log"

    def failed(pass_number: int, output: str) -> bool:
        print(
            f"lualatex reported errors (pass {pass_number}); the end of {log_path}:",
            file=sys.stderr,
        )
        print(_log_tail(output), file=sys.stderr)
        return False

    print("Running lualatex (pass 1)...", file=sys.stderr)
    success, output, needs_rerun = _run_lualatex(tex_file, output_dir)
    if not success:
        return failed(1, output)

    # Run bibtex once after the first pass when needed; force a rerun afterwards
    # because bibtex updates the .bbl that lualatex needs to read.
    if _needs_bibliography(tex_stem, output_dir):
        print("Running bibtex...", file=sys.stderr)
        if not _run_bibtex(tex_stem, output_dir):
            return False
        needs_rerun = True

    run_count = 1
    while needs_rerun and run_count < max_runs:
        run_count += 1
        print(f"Running lualatex (pass {run_count})...", file=sys.stderr)
        success, output, needs_rerun = _run_lualatex(tex_file, output_dir)
        if not success:
            return failed(run_count, output)

    if needs_rerun:
        print(
            f"Warning: reached max_runs ({max_runs}); reledmac/reledpar may not be settled",
            file=sys.stderr,
        )

    print(f"Manual loop completed in {run_count} lualatex pass(es)", file=sys.stderr)
    return True


def compile_tex_to_pdf(
    tex_file: Path,
    output_pdf: Path,
    max_runs: int = 6,
    build_dir: Path | None = None,
) -> bool:
    """Compile a LuaLaTeX .tex file to PDF.

    Runs the lualatex/bibtex loop (see the module docstring) in a temporary
    build directory, or ``build_dir`` when given, and copies the PDF to
    ``output_pdf``. ``max_runs`` caps the number of lualatex passes.
    """
    try:
        if not _have_command("lualatex"):
            print(
                "Error: lualatex not found. Install texlive-luatex.",
                file=sys.stderr,
            )
            return False

        # Resolve to absolute paths: _run_lualatex sets the
        # subprocess cwd to tex_file.parent and pass only tex_file.name, so a
        # relative tex_file/build_dir must be pinned down before that split
        # happens (otherwise a directory component gets applied twice).
        tex_file = tex_file.resolve()
        if build_dir is not None:
            build_dir = build_dir.resolve()

        print(f"Compiling {tex_file} to PDF...", file=sys.stderr)
        tex_stem = tex_file.stem

        if build_dir is not None:
            temp_dir = build_dir
            temp_dir.mkdir(parents=True, exist_ok=True)
        else:
            temp_dir = None

        with tempfile.TemporaryDirectory() if temp_dir is None else nullcontext(str(temp_dir)) as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            if not _run_manual_loop(tex_file, temp_dir, max_runs):
                return False

            generated_pdf = temp_dir / f"{tex_stem}.pdf"
            if not generated_pdf.exists():
                print(f"PDF file not found: {generated_pdf}", file=sys.stderr)
                return False

            if generated_pdf != output_pdf:
                shutil.copy2(generated_pdf, output_pdf)
                print(f"PDF copied to: {output_pdf}", file=sys.stderr)
            else:
                print(f"PDF generated: {output_pdf}", file=sys.stderr)

        return True

    except FileNotFoundError as e:
        # lualatex or bibtex went missing mid-build.
        print(f"Error: command not found: {e}", file=sys.stderr)
        return False
    except BuildError as e:
        print(f"Error: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error compiling TeX to PDF: {e}", file=sys.stderr)
        return False


def export_to_pdf(
    input_file: Path,
    output_pdf: Path,
    settings_file: Path | None = None,
    tex_output: Path | None = None,
    build_dir: Path | None = None,
    project_directory: Path = PROJECT_DIRECTORY,
) -> bool:
    """Convert a compiled JLPTEI XML file to PDF.

    Args:
        input_file: Path to the input compiled JLPTEI XML file.
        output_pdf: Path to the output PDF file.
        settings_file: Optional settings.yaml whose ``typography`` section
            drives the LuaLaTeX preamble.

    Returns:
        True on success, False otherwise.
    """
    if not input_file.exists():
        print(f"Error: Input file '{input_file}' does not exist", file=sys.stderr)
        return False

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_tex_file = tex_output or (Path(temp_dir) / "output.tex")
        if tex_output is not None:
            tex_output.parent.mkdir(parents=True, exist_ok=True)

        if not generate_tex(
            input_file,
            temp_tex_file,
            settings_file=settings_file,
            project_directory=project_directory,
        ):
            return False

        if not compile_tex_to_pdf(temp_tex_file, output_pdf, build_dir=build_dir):
            return False

        print(f"Successfully generated PDF: {output_pdf}", file=sys.stderr)
        if tex_output is not None:
            print(f"Intermediate TeX saved to: {tex_output}", file=sys.stderr)
        return True


def main():  # pragma: no cover
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Convert compiled JLPTEI XML files to PDF (LuaLaTeX + reledmac)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.xml output.pdf
  %(prog)s -s settings.yaml input.xml output.pdf
        """,
    )

    parser.add_argument("input_file", type=Path, help="Path to the input compiled JLPTEI XML file")
    parser.add_argument("output_pdf", type=Path, help="Path to the output PDF file")
    add_settings_arguments(parser, TYPOGRAPHY_SETTINGS_HELP)
    parser.add_argument(
        "--keep-tex",
        action="store_true",
        help=(
            "Save the intermediate TeX file next to the output PDF "
            "as <output>.tex."
        ),
    )
    parser.add_argument(
        "--tex-output",
        type=Path,
        default=None,
        help="Path to write the intermediate TeX file (implies --keep-tex).",
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=None,
        help="Directory to keep LaTeX build artifacts (.log, .aux, etc.) for debugging.",
    )

    args = parser.parse_args()

    if args.keep_tex and args.tex_output is not None:
        print("Error: --keep-tex and --tex-output are mutually exclusive.", file=sys.stderr)
        sys.exit(2)

    tex_output: Path | None = None
    if args.tex_output is not None:
        tex_output = args.tex_output
    elif args.keep_tex:
        tex_output = args.output_pdf.with_suffix(".tex")

    if not export_to_pdf(
        args.input_file,
        args.output_pdf,
        settings_file=args.settings_file,
        tex_output=tex_output,
        build_dir=args.build_dir,
        project_directory=args.project_directory,
    ):
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
