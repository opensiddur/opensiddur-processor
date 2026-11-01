"""Convert downloaded Open Siddur haggadah compilation to JLPTEI projects."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from opensiddur.common.constants import PROJECT_DIRECTORY
from opensiddur.importer.feinstein_haggadah.conditionals import (
    CONDITIONALS,
    ConditionalError,
)
from opensiddur.importer.feinstein_haggadah.page_breaks import (
    PageBreak,
    load_page_breaks,
    load_section_ranges,
    page_breaks_by_section,
)
from opensiddur.importer.feinstein_haggadah.parse_compilation import (
    build_section_contents,
    load_compilation_json,
    parse_rows,
)
from opensiddur.importer.feinstein_haggadah.sections import (
    INDEX_CHILDREN,
    INDEX_NODES,
    document_order_slugs,
    leaf_slugs,
)
from opensiddur.importer.feinstein_haggadah.tei_builder import (
    InlineAnchor,
    citation_bibl,
    content_body,
    header_with_bibls,
    header_with_only_bibls,
    index_body,
    minimal_index_header,
    read_front_stub,
    page_break_anchors,
    printed_verse_body,
    read_header_stub,
    require_project_source_bibl_id,
    tei_document,
    project_citation_bibl,
    transcription_bibl,
    validate_and_write,
    validate_header_stub,
    validate_project_directory,
    verse_anchors,
)
from opensiddur.importer.feinstein_haggadah.versify import (
    BiblicalSection,
    PrintedPsalm,
    load_printed_psalms,
    load_verse_anchors,
)
from opensiddur.importer.util.pages import (
    default_sourcetexts_root,
    feinstein_haggadah_data_directory,
)
from opensiddur.importer.util.tei_project import prune_stale_files
from opensiddur.exporter.validate_urn_references import validate_project_urn_references

#: The Heidenheim haggadah and Feinstein's translation of it (specs/NAMING_SCHEME.md).
HE_PROJECT = "haggadah_leleil_shimmurim-heidenheim-1822-he"
EN_PROJECT = "haggadah_leleil_shimmurim-feinstein-2009-en"

INDEX_TITLES: dict[str, str] = {
    "index": "Haggadah",
    "pre_seder": "Pre-Seder",
    "seder": "Seder",
    "maggid": "Magid",
    "nirtzah": "Nirtzah",
    "hallel": "Hallel",
    "barekh": "Barech",
}


def index_header(
    header: str,
    *,
    project_id: str,
    ranges: dict[str, tuple[str, str]],
) -> str:
    """The project index's header: the full bibliography, plus the project's page scope.

    The index is the one document that holds the source citations in full; see
    :func:`document_header` for every other document.
    """
    from_page, to_page = ranges.get("index", (None, None))
    if not (from_page and to_page):
        return header
    return header_with_bibls(header, [citation_bibl(project_id, from_page, to_page)])


def document_header(
    header: str,
    slug: str,
    *,
    project_id: str,
    ranges: dict[str, tuple[str, str]],
    scripture: dict[str, BiblicalSection],
) -> str:
    """A non-index document's header: the index's bibliography cited by pointer.

    Per ``schema/JLPTEI-3.md`` the full citations belong to the project header alone.
    Copying them into each document would duplicate the ``xml:id``s they are addressed by
    across a hundred files, and make correcting any of them a whole-project rewrite.
    """
    from_page, to_page = ranges.get(slug, (None, None))
    bibls = [project_citation_bibl(project_id, from_page=from_page, to_page=to_page)]
    if slug in scripture:
        bibls.append(transcription_bibl(scripture[slug]))
    return header_with_only_bibls(header, bibls)


def make_project_directory(project_dir: Path) -> Path:
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def convert_project(
    *,
    project_id: str,
    lang: str,
    header_stub: str,
    sourcetexts_root: Path | None,
    project_dir: Path,
    include_page_breaks: bool = False,
    title_page_stub: str | None = None,
) -> None:
    json_path = feinstein_haggadah_data_directory(sourcetexts_root) / "compilation.json"
    compilation = load_compilation_json(json_path)
    rows = parse_rows(compilation)
    contents = build_section_contents(rows)

    grouped: dict[str, list[PageBreak]] = {}
    ranges: dict[str, tuple[str, str]] = {}
    scripture: dict[str, BiblicalSection] = {}
    printed: dict[str, PrintedPsalm] = {}
    if include_page_breaks:
        breaks = load_page_breaks()
        grouped = page_breaks_by_section(breaks)
        ranges = page_ranges(breaks, load_section_ranges())
        scripture = load_verse_anchors()
        # Psalms transcribed from the 1822 print supersede the compilation text. They arrive
        # already versified and with their page breaks in place, so they take neither kind of
        # anchor; only psalm_126, which the print does not carry, still needs matching.
        printed = load_printed_psalms()
        scripture = {
            slug: section for slug, section in scripture.items() if slug not in printed
        }

    validate_header_stub(header_stub, lang=lang)
    main_header = read_header_stub(header_stub)
    require_project_source_bibl_id(main_header, header_stub=header_stub)
    # The title page belongs to the book as a whole, so it goes on the project index and
    # nowhere else. A project with no printed title page simply has no stub.
    title_page = read_front_stub(title_page_stub) if title_page_stub else ""

    def _anchors(slug: str) -> list[InlineAnchor]:
        """Page breaks first, so a page opening a psalm is marked before its chapter."""
        anchors = page_break_anchors(grouped.get(slug, []))
        if slug in scripture:
            anchors += verse_anchors(scripture[slug])
        return anchors

    def _header(header: str, slug: str) -> str:
        return document_header(
            header, slug, project_id=project_id, ranges=ranges, scripture=scripture
        )

    for index_slug, children in INDEX_CHILDREN.items():
        section = contents.get(index_slug)
        body = index_body(
            index_slug, children, section, lang=lang, anchors=_anchors(index_slug)
        )
        if index_slug == "index":
            header = index_header(main_header, project_id=project_id, ranges=ranges)
        else:
            from_page, to_page = ranges.get(index_slug, (None, None))
            header = minimal_index_header(
                INDEX_TITLES.get(index_slug, index_slug),
                project_id=project_id,
                urn_suffix=index_slug,
                lang=lang,
                from_page=from_page,
                to_page=to_page,
            )
        front = title_page if index_slug == "index" else ""
        xml = tei_document(header, body, lang=lang, front_xml=front)
        validate_and_write(xml, index_slug, project_dir)

    written = set(INDEX_CHILDREN)
    for slug in leaf_slugs():
        written.add(slug)
        section = contents.get(slug)
        if slug in printed:
            body = printed_verse_body(printed[slug])
        else:
            body = content_body(
                slug,
                section,
                lang=lang,
                anchors=_anchors(slug),
                # A biblical section is numbered by chapter and verse; a generic paragraph
                # milestone alongside would be a second, redundant citation scheme.
                number_paragraphs=slug not in scripture,
            )
        xml = tei_document(_header(main_header, slug), body, lang=lang)
        validate_and_write(xml, slug, project_dir)

    prune_stale_files(project_dir, written)
    verify_conditionals(project_dir, lang=lang)
    validate_project_directory(project_dir)

    # Runs once, after every file in the project has been written -- individual files can be
    # transiently unresolvable mid-write, so this check belongs at the project level, not
    # per-file. Cross-project urn:x-opensiddur: resolution needs refdb already synced for
    # every project a URN might resolve into (a separate, explicit step), so it's left out
    # here; only the self-contained file/fragment (xml:id) references -- e.g. the bibl
    # citation this check exists to catch -- are checked automatically.
    urn_failures = validate_project_urn_references(
        project_id, project_directory=project_dir.parent, check_urns=False
    )
    if urn_failures:
        details = "; ".join(
            f"{f.file_name}:{f.element_path} @{f.attribute_name}={f.urn}" for f in urn_failures
        )
        raise RuntimeError(
            f"unresolved reference(s) in {project_dir.name}: {details}"
        )


def verify_conditionals(project_dir: Path, *, lang: str) -> None:
    """Check that every curated conditional reached the output, balanced.

    An anchor that no longer matches already stops the conversion, but an entry scoped to a
    paragraph or a transclusion that has been renumbered or renamed would simply never be
    emitted. Silently losing a condition is the failure worth guarding against: the text still
    reads correctly, so nothing else would notice.
    """
    emitted: set[str] = set()
    for path in sorted(project_dir.glob("*.xml")):
        content = path.read_text(encoding="utf-8")
        opened = set(re.findall(r'<j:conditional xml:id="cond_([^"]+)"', content))
        closed = set(re.findall(r'<j:endConditional target="#cond_([^"]+)"', content))
        if opened != closed:
            raise ConditionalError(
                f"{path.name}: conditionals opened but not closed, or the reverse: "
                f"{sorted(opened ^ closed)}"
            )
        emitted |= opened

    expected = {
        entry.cond_id for entry in CONDITIONALS if entry.scope_for(lang) is not None
    }
    missing = expected - emitted
    if missing:
        raise ConditionalError(
            f"conditionals in the table never reached the {lang} output: {sorted(missing)}"
        )


def page_ranges(
    breaks: list[PageBreak],
    overrides: dict[str, tuple[str, str]] | None = None,
) -> dict[str, tuple[str, str]]:
    """Map every slug to the (first, last) page of the source it appears on.

    Walking the leaves in document order, the page "in effect" carries forward: a section
    with no page break of its own lies wholly within the page opened by an earlier section,
    and a section whose first break is not at its start began on the preceding page.
    Index nodes span their subtree. ``overrides`` supplies ranges for sections whose content
    is not contiguous in the print, which the carry-forward walk cannot express.
    """
    grouped = page_breaks_by_section(breaks)
    ranges: dict[str, tuple[str, str]] = {}
    current: str | None = None
    for slug in document_order_slugs():
        entries = grouped.get(slug, [])
        if entries and entries[0].at_section_start:
            first = entries[0].page
        elif current is not None:
            first = current
        else:
            first = entries[0].page if entries else None
        if entries:
            current = entries[-1].page
        if first is None or current is None:
            raise ValueError(f"no page range could be determined for {slug}")
        ranges[slug] = (overrides or {}).get(slug, (first, current))

    def _span(node: str) -> tuple[str, str]:
        spans = [
            _span(child) if child in INDEX_NODES else ranges[child]
            for child in INDEX_CHILDREN[node]
        ]
        # A content-bearing node's own text continues past its children, so its range must take
        # in the walk's result for the node itself as well as its children's.
        if node in ranges:
            spans.append(ranges[node])
        ranges[node] = (overrides or {}).get(node, (spans[0][0], spans[-1][1]))
        return ranges[node]

    _span("index")
    return ranges


def convert_all(
    *,
    sourcetexts_root: Path | None = None,
    project_root: Path | None = None,
) -> None:
    root = project_root or PROJECT_DIRECTORY

    he_dir = make_project_directory(root / HE_PROJECT)
    convert_project(
        project_id=HE_PROJECT,
        lang="he",
        header_stub=f"{HE_PROJECT}_header_stub.xml",
        sourcetexts_root=sourcetexts_root,
        project_dir=he_dir,
        include_page_breaks=True,
        title_page_stub=f"{HE_PROJECT}_title_page.xml",
    )

    en_dir = make_project_directory(root / EN_PROJECT)
    convert_project(
        project_id=EN_PROJECT,
        lang="en",
        header_stub=f"{EN_PROJECT}_header_stub.xml",
        sourcetexts_root=sourcetexts_root,
        project_dir=en_dir,
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert Feinstein/Heidenheim haggadah sources to JLPTEI projects."
    )
    parser.add_argument(
        "--sourcetexts-root",
        type=Path,
        default=default_sourcetexts_root(),
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=PROJECT_DIRECTORY,
        help="Parent directory containing project subdirectories.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    convert_all(sourcetexts_root=args.sourcetexts_root, project_root=args.project_dir)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
