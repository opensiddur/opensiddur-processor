#!/usr/bin/env python3
"""
JLPTEI to LuaLaTeX exporter (reledmac/reledpar pipeline).

This module is the Python driver for the reledmac.xslt stylesheet. It writes the
book's colophon (``metadata.build_colophon``: licences, credits and sources) as
TeX, then drives the XSLT transformation that produces a LuaLaTeX document
ready for ``lualatex`` (``pdf/pdf.py`` runs the passes).

Typography settings (font, paper, layout, fontsize, running heads) are pulled from the same
``settings.yaml`` the compiler uses (``cli_common.load_output_settings``); only the
``typography`` section is used here. When no settings file is supplied, the defaults from
``TypographyConfig`` are used.
"""

import argparse
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Optional

from lxml import etree
from pydantic import ValidationError

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from opensiddur.common.xslt import xslt_transform_string  # noqa: E402
from opensiddur.common.constants import PROJECT_DIRECTORY  # noqa: E402
from opensiddur.exporter.typography import TypographyConfig  # noqa: E402
from opensiddur.exporter.tex.escape import escape_tex  # noqa: E402
from opensiddur.exporter.tex.running_heads import (  # noqa: E402
    build_page_style_tex,
    escape_with_hebrew_runs,
)
from opensiddur.exporter.cli_common import (  # noqa: E402
    TYPOGRAPHY_SETTINGS_HELP,
    SettingsError,
    add_settings_arguments,
    load_output_settings,
    prepare_compiled_tree,
    scan_links_wanted,
)
from opensiddur.exporter.tex.typography_tex import (  # noqa: E402
    build_typography_preamble,
    documentclass_options,
)

from opensiddur.exporter.metadata import (  # noqa: E402
    ISBN_TYPES,
    ISO_DATE,
    CreditRecord,
    LicenseRecord,
    RoleCredits,
    SourceRecord,
    build_colophon,
    extract_credits,
    group_credits,
    group_licenses,
    order_credits,
)
from opensiddur.exporter import metadata  # noqa: E402
from opensiddur.exporter import notices  # noqa: E402
from opensiddur.exporter.notices import RunKind  # noqa: E402
from opensiddur.exporter.settings import (  # noqa: E402
    TEX_UNSAFE_PATH_CHARACTERS,
    DistributionNotice,
    DistributionSettings,
)

XSLT_FILE = Path(__file__).parent / "reledmac.xslt"

# Default project root for resolving p:project/p:file_name references in compiled XML.
projects_source_root = PROJECT_DIRECTORY


def extract_licenses(
    xml_file_paths: list[Path],
    project_directory: Path | None = None,
) -> dict[Path, LicenseRecord]:
    """metadata.extract_licenses, relative to this stage's project root by default."""
    return metadata.extract_licenses(xml_file_paths, project_directory or projects_source_root)


def licenses_to_tex(licenses: list[LicenseRecord]) -> str:
    """Convert a list of LicenseRecord objects into a LaTeX section."""
    if not licenses:
        # An itemize with no items is a LaTeX error, and a Legal section listing nothing
        # would be misleading anyway. Matches credits_to_tex, which already guards.
        return ""
    # A licence's name is the source's own text, so it is escaped like any other; the
    # URL is not, because \url reads its argument verbatim.
    items = "\n".join(
        f"\\item {escape_with_hebrew_runs(license.name)} (\\url{{{license.url}}})"
        for license in licenses
    )
    return (
        "\\section*{Legal}\n"
        "This document includes copyrighted texts licensed under the following licenses.\n"
        "The full text of the licenses can be found at the given URLs:\n\n"
        "\\begin{itemize}\n"
        f"{items}\n"
        "\\end{itemize}\n"
    )


def notice_line_to_tex(text: str) -> str:
    """One line of a distribution or back notice: its text escaped, its URLs and emphasis set."""
    tex = ""
    for kind, run in notices.notice_runs(text):
        if kind is RunKind.URL:
            # The URL is set inside a macro's argument, where \url reads it already tokenized:
            # % and # have to be escaped there to survive at all (url.sty documents this),
            # and a brace, backslash or caret cannot be read as part of it at all, so those
            # are percent-encoded (the same address). In the notice's own type, not \url's
            # typewriter.
            url = "".join(f"%{ord(c):02X}" if c in _URL_UNREADABLE else c for c in run)
            tex += ("{\\urlstyle{same}\\url{" + url.replace("%", "\\%").replace("#", "\\#")
                    + "}}")
        elif kind is RunKind.EMPHASIS:
            tex += "\\emph{" + escape_with_hebrew_runs(run) + "}"
        else:
            tex += escape_with_hebrew_runs(run)
    return tex


#: What \url cannot read in a macro's argument, even escaped.
_URL_UNREADABLE = set("{}\\^")

#: Where the notice stands on its page: the fills above and below it.
_NOTICE_FILLS = {
    "top": ("", "\\vfill"),
    "center": ("\\vfill", "\\vfill"),
    "bottom": ("\\vfill", ""),
}


def distribution_notice_to_tex(notice: Optional[DistributionNotice], logo: Optional[Path]) -> str:
    """The body of the distribution notice's page, or nothing if the book carries none.

    The stylesheet sets it on a page of its own, on the verso of the title page.
    """
    if notice is None:
        return ""
    lines = []
    if logo is not None:
        # The path the settings gave was checked; the directory it is relative to was not.
        if unsafe := sorted(TEX_UNSAFE_PATH_CHARACTERS.intersection(logo.resolve().as_posix())):
            raise ValueError(f"the logo's path {logo.resolve()} has characters TeX cannot take "
                             f"in a file name: {' '.join(unsafe)}")
        # A path in braces, and with / separators whatever the platform: TeX reads a
        # backslash in a file name as a macro.
        lines.append(
            f"\\includegraphics[width={notice.logo_width}]{{{logo.resolve().as_posix()}}}"
        )
    lines += [notice_line_to_tex(line) for line in notice.text]
    above, below = _NOTICE_FILLS[notice.position]
    # A page that is all fills and no box would be dropped: \null holds the top of it.
    return (
        "\\null" + above + "\n"
        # `\\{}`: a bare \\ would read a line beginning with [ or * as its own argument.
        + "\\OSDistributionNotice{" + "\\\\{}\n".join(lines) + "}\n"
        + below + "\n"
    )


def back_notice_to_tex(items: list[str]) -> str:
    """The book's last page, after the colophon: the back notice, at the foot of the page."""
    if not items:
        return ""
    # `\\item{}`: a bare \\item would read a statement beginning with [ as its label.
    entries = "\n".join(f"\\item{{}} {notice_line_to_tex(item)}" for item in items)
    return (
        "\\clearpage\n"
        "\\thispagestyle{empty}\n"
        "\\null\\vfill\n"
        "\\OSBackNotice{\\begin{itemize}\n" + entries + "\n\\end{itemize}}\n"
    )


def credits_to_tex(credits: list[RoleCredits]) -> str:
    """Convert ordered credits into a LaTeX appendix section."""
    if not credits:
        return ""
    tex = "\\section*{Contributor credits}\n"
    for role in credits:
        tex += f"\\subsection*{{{escape_with_hebrew_runs(role.heading)}}}\n"
        for group in role.namespaces:
            # A credit with no namespace is one whose reference could not be read. It is
            # still a person, so it is listed -- just under no heading claiming to know
            # where their name is meaningful.
            if group.namespace:
                tex += f"\\subsubsection*{{From {escape_with_hebrew_runs(group.namespace)}}}\n"
            tex += "\\begin{itemize}\n"
            for credit in group.credits:
                tex += f"\\item {escape_with_hebrew_runs(credit.name_text)}\n"
            tex += "\\end{itemize}\n"
    return tex


# Hebrew letters and points, and the geresh and gershayim that end an abbreviation or a
# numeral (ה׳, תשפ״ו), which belong to the word they end.
_BIBLIOGRAPHY_HEBREW = re.compile("[\u05d0-\u05ea\u0591-\u05c7\u05f3\u05f4\ufb1d-\ufb4f]+")


def _bibliography_text(text: str) -> str:
    """Escape a bibliographic value, setting each Hebrew phrase as one Hebrew run.

    Wider than ``escape_with_hebrew_runs``: Hebrew words separated only by spaces and
    punctuation of any kind (quotation marks, parentheses, a geresh) are one phrase. A title
    such as ספר "החינוך" set as three runs would have its words laid out left to right in
    the left-to-right bibliography, so the phrase would read backwards.
    """
    runs: list[list[int]] = []
    for match in _BIBLIOGRAPHY_HEBREW.finditer(text):
        gap = text[runs[-1][1]:match.start()] if runs else None
        if gap is not None and all(c.isspace() or unicodedata.category(c).startswith("P")
                                   for c in gap):
            runs[-1][1] = match.end()
        else:
            runs.append([match.start(), match.end()])
    parts: list[str] = []
    position = 0
    for run_start, run_end in runs:
        parts.append(escape_tex(text[position:run_start]))
        parts.append(r"\texthebrew{" + escape_tex(text[run_start:run_end]) + "}")
        position = run_end
    parts.append(escape_tex(text[position:]))
    return "".join(parts)


def source_to_bibtex(source: SourceRecord) -> str:
    """One source as a BibTeX entry, ending in a blank line.

    Every value is escaped, with its Hebrew runs set as Hebrew, except the URL, which biblatex
    reads verbatim. Direction is decided by the script actually in the string, not by the
    language of the index it came from: a Hebrew index cites Latin publishers and
    transliterations, and Hebrew turns up in English notes.
    """
    fields: list[tuple[str, str]] = []

    def add(name: str, value: str) -> None:
        if value:
            fields.append((name, _bibliography_text(value)))

    add("title", source.title)
    add("subtitle", source.subtitle)
    if source.editors:
        fields.append(("editor", " and ".join(map(_bibliography_text, source.editors))))
    if source.authors:
        fields.append(("author", " and ".join(map(_bibliography_text, source.authors))))
    add("edition", source.edition)
    add("publisher", source.publisher)
    # The site that hosts an online source is its organization: biblatex prints
    # "organization" for @online and ignores "publisher" there. For a printed source with no
    # publisher of its own, the distributor is the closest thing to one.
    add("organization" if source.entry_type == "online" else "publisher", source.distributor)
    if source.address:
        fields.append(("address", ", ".join(map(_bibliography_text, source.address))))
    # An ISO-shaped date goes in "date", which biblatex parses and formats; anything else
    # stays in "year", which it prints verbatim.
    add("date" if ISO_DATE.match(source.date) else "year", source.date)
    if source.url:
        fields.append(("url", source.url))
    add("urldate", source.urldate)
    # A site-specific identifier (archive.org, hebrewbooks) becomes an eprint keyed by the
    # site that issued it, which biblatex prints as "archive.org: <id>". An entry has one
    # eprint and one isbn: a repeated field is an error to biber, so any further identifier
    # is a remark in the addendum.
    notes = list(source.notes)
    for kind, value in source.identifiers:
        field = "isbn" if kind in ISBN_TYPES else "eprint"
        if any(name == field for name, _ in fields):
            notes.append(f"{kind}: {value}" if kind else value)
        elif field == "isbn":
            add("isbn", value)
        else:
            add("eprinttype", kind)
            add("eprint", value)
    # Everything explanatory is one addendum: it prints after the publication data and the
    # URL, where a remark on a citation belongs.
    if notes:
        fields.append(("addendum", " ".join(map(_bibliography_text, notes))))
    body = "".join(f"  {name} = {{{value}}},\n" for name, value in fields)
    return f"@{source.entry_type}{{{source.key},\n{body}}}\n\n"


def sources_to_tex(sources: list[SourceRecord]) -> tuple[str, str]:
    """The bibliography, as a (preamble_tex, postamble_tex) pair.

    The preamble embeds the .bib in a ``filecontents*`` block and adds it as a resource; the
    postamble prints it. Both are empty when there are no sources.
    """
    if not sources:
        return "", ""
    bibtex_blob = "\n\n".join(source_to_bibtex(source).strip() for source in sources)

    # Named after the job, so two documents built in one directory do not share it, and
    # overwritten, because filecontents otherwise keeps a .bib it finds already there —
    # a reused build directory would print the previous build's sources.
    preamble_tex = (
        "\\begin{filecontents*}[overwrite]{\\jobname.bib}\n"
        f"{bibtex_blob}\n"
        "\\end{filecontents*}\n"
        "\\addbibresource{\\jobname.bib}\n"
    )
    postamble_tex = (
        "\n\\section*{Sources}\n"
        "\\begingroup\n"
        "\\nocite{*}\n"
        "\\printbibliography[heading=none]\n"
        "\\endgroup\n"
    )
    return preamble_tex, postamble_tex


def get_file_references(
    input_file: Path, project_directory: Path | None = None
) -> list[Path]:
    """metadata.get_file_references, relative to this stage's project root by default."""
    return metadata.get_file_references(input_file, project_directory or projects_source_root)


def typography_parameters(typography: TypographyConfig, root: etree._Element) -> dict:
    """Every stylesheet parameter that carries typography, for one document.

    The stylesheet keeps no typography default of its own and requires each of
    these, so this is the one place a document's appearance is handed to it.
    ``root`` is the compiled document's root element.
    """
    # Running-head slots that declare no language of their own follow the
    # document's, so their direction is right without being restated.
    root_language = root.get("{http://www.w3.org/XML/1998/namespace}lang")
    # Several reledpar declarations do not exist unless the package is
    # loaded, and the stylesheet loads it only for a document with two
    # aligned streams. The typography block has to know which this is.
    has_parallel = (
        root.find(".//{http://jewishliturgy.org/ns/processing}parallel") is not None
    )
    return {
        "documentclass-options": documentclass_options(typography),
        "typography-preamble": build_typography_preamble(typography, has_parallel),
        "layout": typography.parallel.layout.value,
        "notes-placement": typography.notes.placement.value,
        "notes-mark": typography.notes.mark.value,
        "scan-links": typography.markers.scan_links.placement.value,
        "table-of-contents": typography.table_of_contents.enabled,
        "table-of-contents-depth": typography.table_of_contents.depth,
        "bookmarks-from": typography.bookmarks.from_.value,
        "headings-from": typography.headings.from_.value,
        "instructions-from": typography.instructions.from_.value,
        "page-style-preamble": build_page_style_tex(
            typography.page_header, typography.page_footer, root_language
        ),
    }


def transform_xml_to_tex(
    input_file,
    xslt_file: Path = XSLT_FILE,
    output_file: Optional[str] = None,
    settings_file: Optional[Path] = None,
    typography: Optional[TypographyConfig] = None,
    project_directory: Path | None = None,
    distribution: Optional[DistributionSettings] = None,
) -> str:
    """Transform a compiled JLPTEI XML file into a LuaLaTeX document.

    Args:
        input_file: Path to the compiled JLPTEI XML file.
        xslt_file: Path to ``reledmac.xslt`` (overridable for tests).
        output_file: If given, write to this path; otherwise return the string.
        settings_file: Optional path to a settings.yaml to read typography from.
        typography: Pre-loaded TypographyConfig (takes precedence over settings_file).
        distribution: Pre-loaded distribution notices (takes precedence over
            settings_file). A notice's logo path is relative to settings_file all the same.
        project_directory: Base directory containing project subdirectories.

    Returns:
        The transformed LaTeX content as a string.

    Raises:
        SettingsError: if the settings file cannot be read.
        pydantic.ValidationError: if the settings file is invalid.
        Exception: whatever the transformation raised; the command-line entry
            point reports it and exits non-zero, a caller decides for itself.
    """
    if typography is None or distribution is None:
        settings = load_output_settings(settings_file, resolve_fonts=typography is None)
        typography = typography or settings.typography
        distribution = distribution or settings.distribution
    notice = notices.distribution_notice(distribution)
    notice_tex = distribution_notice_to_tex(
        notice, notices.resolve_logo(notice, settings_file) if notice else None
    )
    # PDF is the printed book.
    back_notice_tex = back_notice_to_tex(notices.back_notice_items(distribution, "print"))

    if project_directory is None:
        project_directory = projects_source_root
    project_directory = project_directory.resolve()
    colophon = build_colophon(Path(input_file), project_directory)
    licenses_tex = licenses_to_tex(colophon.licenses)
    credits_tex = credits_to_tex(colophon.credits)
    sources_preamble_tex, sources_postamble_tex = sources_to_tex(colophon.sources)

    parsed = etree.parse(input_file)
    root = parsed.getroot()
    prepare_compiled_tree(root, scan_links=scan_links_wanted(typography))
    input_xml = etree.tostring(root, encoding="unicode")

    result = xslt_transform_string(
        Path(xslt_file),
        input_xml,
        xslt_params={
            "additional-preamble": sources_preamble_tex,
            "additional-postamble": (
                "\\par\\bigskip\n"
                "\\hrule\\bigskip\n"
                "\\section*{Metadata}\n"
                + licenses_tex
                + "\n"
                + credits_tex
                + "\n"
                + sources_postamble_tex
            ),
            "distribution-notice": notice_tex,
            "back-notice": back_notice_tex,
            **typography_parameters(typography, root),
        },
    )

    if output_file:
        with open(output_file, "w", encoding="utf-8") as output_fd:
            output_fd.write(result)
        print(f"LuaLaTeX output written to: {output_file}", file=sys.stderr)
    else:
        sys.stdout.write(result)

    return result


def main():  # pragma: no cover
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Convert compiled JLPTEI XML files to LuaLaTeX (reledmac/reledpar)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.xml
  %(prog)s input.xml -o output.tex
  %(prog)s input.xml -s settings.yaml -o output.tex
        """,
    )

    parser.add_argument("input_file", help="Path to the input compiled JLPTEI XML file")
    parser.add_argument(
        "-o",
        "--output",
        dest="output_file",
        help="Path to the output .tex file (default: output to stdout)",
    )
    add_settings_arguments(parser, TYPOGRAPHY_SETTINGS_HELP)
    parser.add_argument(
        "--xslt",
        dest="xslt_file",
        default=str(XSLT_FILE),
        help="Path to the XSLT file (default: reledmac.xslt next to this script)",
    )

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' does not exist", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.xslt_file):
        print(f"Error: XSLT file '{args.xslt_file}' does not exist", file=sys.stderr)
        sys.exit(1)

    try:
        settings = load_output_settings(args.settings_file, resolve_fonts=True)
    except (SettingsError, ValidationError) as e:
        print(f"Settings error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        transform_xml_to_tex(
            args.input_file,
            xslt_file=Path(args.xslt_file),
            output_file=args.output_file,
            settings_file=args.settings_file,
            typography=settings.typography,
            distribution=settings.distribution,
            project_directory=args.project_directory,
        )
    except Exception as e:
        print(f"Transformation error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
