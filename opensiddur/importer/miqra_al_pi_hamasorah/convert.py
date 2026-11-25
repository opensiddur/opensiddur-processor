from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

from opensiddur.common.constants import PROJECT_DIRECTORY
from opensiddur.common.versification import MIQRA_PROJECT
from opensiddur.common.subverse import add_subverse_milestones
from opensiddur.common.xslt import xslt_transform_string
from opensiddur.importer.util.pages import (
    default_sourcetexts_root,
    miqra_al_pi_hamasorah_data_directory,
    miqra_al_pi_hamasorah_plus_directory,
)
from opensiddur.importer.util.prettify import prettify_xml
from opensiddur.importer.util.validation import validate
from opensiddur.importer.miqra_al_pi_hamasorah.canonical_verses import annotate_canonical_verses
from opensiddur.importer.miqra_al_pi_hamasorah.download import (
    LICENSE_NAME,
    MANIFEST_NAME,
    _FULL_SHA,
    file_sha256,
)
from opensiddur.importer.miqra_al_pi_hamasorah.miqra_plus import (
    MIQRA_NS,
    MW_NS,
    PlusFormatError,
    PlusToIntermediate,
    _NUMBER,
    _xml_escape,
    check_plus_file,
)

logger = logging.getLogger(__name__)

MIQRA_TO_TEI_XSLT = Path(__file__).parent / "miqra_to_tei.xslt"


def make_project_directory(project_dir: Path | None = None) -> Path:
    directory = (
        project_dir.resolve()
        if project_dir is not None
        else PROJECT_DIRECTORY / MIQRA_PROJECT
    )
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _default_project_directory() -> Path:
    return PROJECT_DIRECTORY / MIQRA_PROJECT


@dataclass(frozen=True)
class Book:
    book_name_he: str
    book_name_en: str
    file_name: str


@dataclass(frozen=True)
class Index:
    index_title_en: str
    index_title_he: Optional[str]
    index_sub_en: Optional[str]
    index_sub_he: Optional[str]
    file_name: str
    transclusions: list[Book | "Index"]


TANAKH_INDEX: list[Index] = [
    Index(
        index_title_en="Miqra al pi ha-Masorah",
        index_title_he="מקרא על פי המסורה",
        index_sub_en=None,
        index_sub_he=None,
        file_name="index",
        transclusions=[
            Index(
                index_title_en="The Law",
                index_title_he="תורה",
                index_sub_en=None,
                index_sub_he=None,
                file_name="the_law",
                transclusions=[
                    Book("בראשית", "Genesis", "genesis"),
                    Book("שמות", "Exodus", "exodus"),
                    Book("ויקרא", "Leviticus", "leviticus"),
                    Book("במדבר", "Numbers", "numbers"),
                    Book("דברים", "Deuteronomy", "deuteronomy"),
                ],
            ),
            Index(
                index_title_en="The Prophets",
                index_title_he="נביאים",
                index_sub_en=None,
                index_sub_he=None,
                file_name="the_prophets",
                transclusions=[
                    Book("יהושע", "Joshua", "joshua"),
                    Book("שופטים", "Judges", "judges"),
                    Book("שמואל א", "I Samuel", "samuel_1"),
                    Book("שמואל ב", "II Samuel", "samuel_2"),
                    Book("מלכים א", "I Kings", "kings_1"),
                    Book("מלכים ב", "II Kings", "kings_2"),
                    Book("ישעיהו", "Isaiah", "isaiah"),
                    Book("ירמיהו", "Jeremiah", "jeremiah"),
                    Book("יחזקאל", "Ezekiel", "ezekiel"),
                    Index(
                        index_title_en="The Twelve",
                        index_title_he=None,
                        index_sub_en=None,
                        index_sub_he=None,
                        file_name="the_twelve",
                        transclusions=[
                            Book("הושע", "Hosea", "hosea"),
                            Book("יואל", "Joel", "joel"),
                            Book("עמוס", "Amos", "amos"),
                            Book("עבדיה", "Obadiah", "obadiah"),
                            Book("יונה", "Jonah", "jonah"),
                            Book("מיכה", "Micah", "micah"),
                            Book("נחום", "Nahum", "nahum"),
                            Book("חבקוק", "Habakkuk", "habakkuk"),
                            Book("צפניה", "Zephaniah", "zephaniah"),
                            Book("חגי", "Haggai", "haggai"),
                            Book("זכריה", "Zechariah", "zechariah"),
                            Book("מלאכי", "Malachi", "malachi"),
                        ],
                    ),
                ],
            ),
            Index(
                index_title_en="The Writings",
                index_title_he="כתובים",
                index_sub_en=None,
                index_sub_he=None,
                file_name="the_writings",
                transclusions=[
                    Book("תהלים", "Psalms", "psalms"),
                    Book("משלי", "Proverbs", "proverbs"),
                    Book("איוב", "Job", "job"),
                    Book("שיר השירים", "Song of Songs", "song_of_songs"),
                    Book("רות", "Ruth", "ruth"),
                    Book("איכה", "Lamentations", "lamentations"),
                    Book("קהלת", "Ecclesiastes", "ecclesiastes"),
                    Book("אסתר", "Esther", "esther"),
                    Book("דניאל", "Daniel", "daniel"),
                    Book("עזרא", "Ezra", "ezra"),
                    Book("נחמיה", "Nehemiah", "nehemiah"),
                    Book("דברי הימים א", "I Chronicles", "chronicles_1"),
                    Book("דברי הימים ב", "II Chronicles", "chronicles_2"),
                ],
            ),
        ],
    )
]


def _flatten_books(indices: Iterable[Index]) -> list[Book]:
    books: list[Book] = []
    for idx in indices:
        for t in idx.transclusions:
            if isinstance(t, Book):
                books.append(t)
            else:
                books.extend(_flatten_books([t]))
    return books


def header(
    title_he: Optional[str],
    title_en: str,
    *,
    source_note: str,
    project_id: str = MIQRA_PROJECT,
    namespace: str = "bible",
    entrypoint: str = "tanakh",
    license_url: str = "https://creativecommons.org/licenses/by-sa/4.0/",
    license_name: str = "Creative Commons Attribution-ShareAlike 4.0 International",
) -> str:
    title_he_xml = (
        f"""<tei:title type="alt" xml:lang="he">{title_he}</tei:title>""" if title_he else ""
    )
    return f"""<tei:teiHeader>
  <tei:fileDesc>
    <tei:titleStmt>
      <tei:title type="main" xml:lang="en">{title_en}</tei:title>
      {title_he_xml}
    </tei:titleStmt>
    <tei:publicationStmt>
      <tei:distributor>
        <tei:ref target="http://opensiddur.org">Open Siddur Project</tei:ref>
      </tei:distributor>
      <tei:idno type="urn">urn:x-opensiddur:text:{namespace}:{entrypoint}@{project_id}</tei:idno>
      <tei:availability status="free">
        <tei:licence target="{license_url}">{license_name}</tei:licence>
      </tei:availability>
    </tei:publicationStmt>
    <tei:sourceDesc>
      <tei:bibl>
        <tei:title xml:lang="he">מקרא על פי המסורה</tei:title>
        <tei:editor>Avi Kadish</tei:editor>
        <tei:distributor>
          <tei:ref target="https://he.wikisource.org/wiki/%D7%9E%D7%A7%D7%A8%D7%90_%D7%A2%D7%9C_%D7%A4%D7%99_%D7%94%D7%9E%D7%A1%D7%95%D7%A8%D7%94#%D7%A8%D7%90%D7%A9">Hebrew Wikisource</tei:ref>
        </tei:distributor>
        <tei:idno type="url">https://he.wikisource.org/wiki/%D7%9E%D7%A7%D7%A8%D7%90_%D7%A2%D7%9C_%D7%A4%D7%99_%D7%94%D7%9E%D7%A1%D7%95%D7%A8%D7%94#%D7%A8%D7%90%D7%A9</tei:idno>
        <tei:note xml:lang="en">{_xml_escape(source_note)}</tei:note>
      </tei:bibl>
    </tei:sourceDesc>
  </tei:fileDesc>
</tei:teiHeader>
"""


def tei_file(
    header_xml: str,
    *,
    default_lang: str = "he",
    front: str = "",
    body: str = "",
    back: str = "",
    stand_off: str = "",
) -> str:
    return f"""<tei:TEI xml:lang="{default_lang}" xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
{header_xml}
<tei:text>
{front}
{body}
{back}
</tei:text>
{stand_off}
</tei:TEI>
"""


def validate_and_write_tei_file(
    tei_content: str,
    file_name: str,
    project_dir: Path | None,
    add_subverse: bool = False,
) -> Path:
    directory = project_dir.resolve() if project_dir is not None else _default_project_directory()
    out_path = directory / f"{file_name}.xml"
    pretty_xml = prettify_xml(tei_content, remove_xml_declaration=True)
    if add_subverse:
        # After prettifying, not before: the pass splits text nodes to place its milestones,
        # and re-indenting afterwards would put whitespace inside the words it split.
        pretty_xml = add_subverse_milestones(
            pretty_xml, language="he", project=MIQRA_PROJECT
        )
    is_valid, errors = validate(pretty_xml)
    if not is_valid:
        raise Exception(f"Errors in {file_name}: {errors}")
    out_path.write_text(pretty_xml, encoding="utf-8")
    return out_path


# A book that is a sub-book of one of the 24 books is named by its abbreviation or by its own
# name (sub_book_name: "שמ\"א", "הושע", "נחמיה"); any other by its 24-book name without its
# "ספר " or "מגילת " (book24_name: "ספר בראשית", "מגילת רות").
_BOOK24_PREFIX = re.compile(r"^(?:ספר|מגילת) ")
_SUB_BOOK_NAMES = {
    'שמ"א': "שמואל א",
    'שמ"ב': "שמואל ב",
    'מל"א': "מלכים א",
    'מל"ב': "מלכים ב",
    'דה"א': "דברי הימים א",
    'דה"ב': "דברי הימים ב",
}


def _book_name_he(book39: dict[str, Any]) -> str:
    """The name TANAKH_INDEX gives a plus book39."""
    sub_book_name = book39["sub_book_name"]
    if sub_book_name is not None:
        return _SUB_BOOK_NAMES.get(sub_book_name, sub_book_name)
    return _BOOK24_PREFIX.sub("", book39["book24_name"])


@dataclass(frozen=True)
class Attribution:
    """A statement of MAM's licence, an attribution or a credit, then the page it links to."""

    statement: str
    link_text: str
    url: str


# The two attributions in LICENSE.md, each a line followed by a Markdown link to its page.
_ATTRIBUTIONS = {
    "en": re.compile(
        r"^(?P<statement>Attribution in English and all languages other than Hebrew[^\r\n]*)"
        r"\s*\[(?P<text>[^\]\r\n]+)\]\((?P<url>[^)\s]+)\)",
        re.MULTILINE,
    ),
    "he": re.compile(
        r"^(?P<statement>הייחוס בעברית[^\r\n]*)\s*\[(?P<text>[^\]\r\n]+)\]\((?P<url>[^)\s]+)\)",
        re.MULTILINE,
    ),
}


def read_attributions(licence: str) -> dict[str, Attribution]:
    """The English and Hebrew attributions MAM-parsed's LICENSE.md asks for.

    The file repeats MAM's statement for historical reasons, so a match may occur more than
    once; every occurrence must be the same.
    """
    attributions: dict[str, Attribution] = {}
    for lang, pattern in _ATTRIBUTIONS.items():
        found = {
            Attribution(m.group("statement").strip(), m.group("text"), m.group("url"))
            for m in pattern.finditer(licence)
        }
        if len(found) != 1:
            raise PlusFormatError(f"LICENSE.md: expected one {lang} attribution, found {found}")
        attributions[lang] = found.pop()
    return attributions


# The paragraph of LICENSE.md, in each language, that credits MAM's editors, and the link to
# the licence that follows it.
_CREDITS = {
    "en": re.compile(
        r'^(?P<statement>"Miqra according to the Masorah" [^\[]*?)'
        r"\s*\[(?P<text>[^\]\r\n]+)\]\((?P<url>[^)\s]+)\)",
        re.MULTILINE,
    ),
    "he": re.compile(
        r'^(?P<statement>"מקרא על פי המסורה" [^\[]*?)'
        r"\s*\[(?P<text>[^\]\r\n]+)\]\((?P<url>[^)\s]+)\)",
        re.MULTILINE,
    ),
}


def read_credits(licence: str) -> dict[str, Attribution]:
    """The English and Hebrew paragraphs of MAM-parsed's LICENSE.md that credit MAM's editors.

    Each is the paragraph as MAM wrote it, its line breaks made spaces, with the link to the
    licence that it ends by pointing to. As with the attributions, every occurrence must be
    the same.
    """
    credits: dict[str, Attribution] = {}
    for lang, pattern in _CREDITS.items():
        found = {
            Attribution(" ".join(m.group("statement").split()), m.group("text"), m.group("url"))
            for m in pattern.finditer(licence)
        }
        if len(found) != 1:
            raise PlusFormatError(f"LICENSE.md: expected one {lang} credit, found {found}")
        credits[lang] = found.pop()
    return credits


@dataclass
class MamSource:
    """The downloaded MAM-parsed plus files and what the manifest says of them."""

    repository: str
    commit: str
    plus_path: str
    attributions: dict[str, Attribution]
    credits: dict[str, Attribution]
    book39s: dict[str, dict[str, Any]]

    @property
    def repository_url(self) -> str:
        return f"https://github.com/{self.repository}"

    def note(self, *, with_commit: bool = False) -> str:
        """The TEI header's account of the source; only the index names the commit."""
        at_commit = f" at commit {self.commit}" if with_commit else ""
        return (
            "Prepared by Avi Kadish, based on Hebrew Wikisource material; taken from "
            f"{self.plus_path} in {self.repository_url}{at_commit}, which is derived from "
            "Hebrew Wikisource."
        )


def _listed_contents(
    data_dir: Path, manifest: dict[str, Any], manifest_path: Path
) -> dict[str, str]:
    """The text of each file the manifest lists, by its path there, after checking it.

    A file must match the manifest's SHA-256, byte for byte, so that a download that failed or
    was edited is never credited to the manifest's commit.
    """
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise PlusFormatError(f"{manifest_path} lists no files (run download)")
    contents: dict[str, str] = {}
    for entry in files:
        path = data_dir / entry["path"]
        if not path.is_file():
            raise PlusFormatError(f"{path}, which {manifest_path} lists, is missing (run download)")
        data = path.read_bytes()
        if file_sha256(data) != entry["sha256"]:
            raise PlusFormatError(f"{path} is not the file {manifest_path} lists (run download)")
        contents[entry["path"]] = data.decode("utf-8")
    return contents


def load_source(sourcetexts_root: Path | None) -> MamSource:
    """Read the download: its manifest, MAM's licence and every book of the plus files.

    The files read are those the manifest lists, each checked against its SHA-256 there; a
    JSON file in ``plus/`` that the manifest does not list is refused.
    """
    data_dir = miqra_al_pi_hamasorah_data_directory(sourcetexts_root)
    manifest_path = data_dir / MANIFEST_NAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing {manifest_path} (run download first)")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    commit = manifest.get("commit", "")
    if not _FULL_SHA.fullmatch(commit):
        raise PlusFormatError(f"{manifest_path}: no full commit SHA: {commit!r}")
    contents = _listed_contents(data_dir, manifest, manifest_path)
    plus_dir = miqra_al_pi_hamasorah_plus_directory(sourcetexts_root)
    plus_paths = sorted(f"{plus_dir.name}/{path.name}" for path in plus_dir.glob("*.json"))
    unlisted = [path for path in plus_paths if path not in contents]
    if unlisted:
        raise PlusFormatError(f"{manifest_path} does not list {unlisted} (run download)")
    if LICENSE_NAME not in contents:
        raise PlusFormatError(f"{manifest_path} does not list {LICENSE_NAME}")
    attributions = read_attributions(contents[LICENSE_NAME])
    credits = read_credits(contents[LICENSE_NAME])

    known = {book.book_name_he for book in _flatten_books(TANAKH_INDEX)}
    book39s: dict[str, dict[str, Any]] = {}
    for path in plus_paths:
        plus_file = json.loads(contents[path])
        check_plus_file(plus_file, path)
        for book39 in plus_file["book39s"]:
            name = _book_name_he(book39)
            if name not in known or name in book39s:
                raise PlusFormatError(f"{path}: unexpected book {name!r}")
            book39s[name] = book39
    return MamSource(
        repository=manifest["repository"],
        commit=commit,
        plus_path=manifest["plus_path"],
        attributions=attributions,
        credits=credits,
        book39s=book39s,
    )


def _numbered(mapping: Any, what: str) -> Iterator[tuple[str, Any]]:
    """The entries of a chapters or verses object, whose keys count up from "1"."""
    if not isinstance(mapping, dict):
        raise PlusFormatError(f"{what}: not an object: {mapping!r}")
    for expected, (key, value) in enumerate(mapping.items(), start=1):
        if not _NUMBER.fullmatch(key) or int(key) != expected:
            raise PlusFormatError(f"{what}: key {key!r} where {expected} was expected")
        yield key, value


def miqra_book_to_intermediate(
    book: Book, book39: dict[str, Any], converter: PlusToIntermediate
) -> str:
    """
    Build an intermediate XML document for a single book.

    Each verse of the plus book39 becomes a row, numbered by its chapter and verse keys. The
    book39's good ending (good_ending_plus) is checked but not rendered, as the sheet's
    good-ending rows were not.
    """
    converter.check_good_ending(book39["good_ending_plus"], book.file_name)
    rows_xml: list[str] = []
    for chapter, verses in _numbered(book39["chapters"], book.file_name):
        for verse, columns in _numbered(verses, f"{book.file_name} {chapter}"):
            if not isinstance(columns, list) or len(columns) != 3:
                raise PlusFormatError(f"{book.file_name} {chapter}:{verse} is not [C, D, E]")
            nav, scaffold, text = columns
            rows_xml.append(
                f"""<miqra:row chapter="{chapter}" verse="{verse}">
  <miqra:nav>{converter.column(nav, "C")}</miqra:nav>
  <miqra:scaffold>{converter.column(scaffold, "D")}</miqra:scaffold>
  <miqra:text>{converter.column(text, "E")}</miqra:text>
</miqra:row>"""
            )

    rows_joined = "\n".join(rows_xml)
    return f"""<miqra:book xmlns:miqra="{MIQRA_NS}" xmlns:mw="{MW_NS}" fileName="{_xml_escape(book.file_name)}" bookNameHe="{_xml_escape(book.book_name_he)}" bookNameEn="{_xml_escape(book.book_name_en)}">
{rows_joined}
</miqra:book>
"""


def convert_books(source: MamSource) -> dict[str, str]:
    """Every book's intermediate XML, by file name, in the order a full run writes the books.

    One converter converts them all, so that the notes are numbered across the whole Tanakh
    and a book's note ids are the same whether it is written alone (``--only-book``) or in a
    full run. Every book is converted before any file is written, so a book missing from the
    download, or a template the reader refuses, stops the run before it has changed the
    project directory.
    """
    converter = PlusToIntermediate()
    intermediates: dict[str, str] = {}
    for book in _flatten_books(TANAKH_INDEX):
        book39 = source.book39s.get(book.book_name_he)
        if book39 is None:
            raise PlusFormatError(f"the MAM-parsed plus files have no {book.book_name_en}")
        intermediates[book.file_name] = miqra_book_to_intermediate(book, book39, converter)
    return intermediates


def intermediate_to_tei(intermediate_xml: str, *, xslt_params: Optional[dict[str, Any]] = None) -> dict[str, str]:
    outputs = xslt_transform_string(
        MIQRA_TO_TEI_XSLT,
        intermediate_xml,
        multiple_results=True,
        xslt_params=xslt_params,
    )
    return {
        "front": outputs.get("front", ""),
        "body": outputs.get("body", outputs.get("", "")),
        "stand_off": outputs.get("standoff", ""),
    }


def book_file(
    book: Book,
    *,
    source: MamSource,
    intermediate: str,
    project_dir: Path | None,
) -> None:
    intermediate = annotate_canonical_verses(intermediate, book.file_name)
    xml_dict = intermediate_to_tei(intermediate)
    header_xml = header(
        book.book_name_he, book.book_name_en, entrypoint=book.file_name, source_note=source.note()
    )
    tei_content = tei_file(header_xml, **xml_dict)
    make_project_directory(project_dir)
    validate_and_write_tei_file(tei_content, book.file_name, project_dir, add_subverse=True)


def front_matter(source: MamSource) -> str:
    """The index's front matter: where the text was taken from, and, in each language, MAM's
    credit to its editors and the attribution it asks for."""
    paragraphs = [
        f'<tei:p xml:lang="en">Taken from {_xml_escape(source.plus_path)} in '
        f"{_xml_escape(source.repository_url)} at commit {source.commit}, which is derived "
        "from Hebrew Wikisource. Available under the CC BY-SA 4.0 licence.</tei:p>"
    ]
    for lang in ("en", "he"):
        for statement in (source.credits[lang], source.attributions[lang]):
            paragraphs.append(
                f'<tei:p xml:lang="{lang}">{_xml_escape(statement.statement)} '
                f'<tei:ref target="{_xml_escape(statement.url)}">'
                f"{_xml_escape(statement.link_text)}</tei:ref></tei:p>"
            )
    paras = "\n".join(paragraphs)
    return f"<tei:front xmlns:tei=\"http://www.tei-c.org/ns/1.0\">{paras}</tei:front>"


def index_urn_name(file_name: str) -> str:
    """The name an index file's URN has: the whole canon is ``tanakh``, as in every Tanakh
    project; any other index (``the_prophets``) is named by its file."""
    return "tanakh" if file_name == "index" else file_name


def index_file(
    idx: Index,
    *,
    source: MamSource,
    intermediates: dict[str, str],
    project_dir: Path | None,
) -> None:
    transclusion_str = "\n".join(
        [
            f"""<j:transclude target="urn:x-opensiddur:text:bible:{t.file_name}"/>"""
            for t in idx.transclusions
        ]
    )
    index_body = f"""<tei:body xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
  <tei:div corresp="urn:x-opensiddur:text:bible:{index_urn_name(idx.file_name)}">
    <tei:head xml:lang="en">{_xml_escape(idx.index_title_en)}</tei:head>
    {transclusion_str}
  </tei:div>
</tei:body>
"""
    is_index = idx.file_name == "index"
    front = front_matter(source) if is_index else ""
    header_xml = header(
        idx.index_title_he,
        idx.index_title_en,
        entrypoint=index_urn_name(idx.file_name),
        source_note=source.note(with_commit=is_index),
    )
    tei_content = tei_file(header_xml, front=front, body=index_body)
    make_project_directory(project_dir)
    validate_and_write_tei_file(tei_content, idx.file_name, project_dir)

    for t in idx.transclusions:
        if isinstance(t, Index):
            index_file(t, source=source, intermediates=intermediates, project_dir=project_dir)
        else:
            book_file(
                t, source=source, intermediate=intermediates[t.file_name], project_dir=project_dir
            )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert Miqra al pi ha-Masorah, as MAM-parsed plus JSON, to JLPTEI."
    )
    parser.add_argument(
        "--sourcetexts-root",
        type=Path,
        default=default_sourcetexts_root(),
        help="Root of sourcetexts tree (default: <repo>/sourcetexts/sources).",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=None,
        help=(
            f"Output project directory (default: <repo>/opensiddur-projects/project/{MIQRA_PROJECT})."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions without writing files.",
    )
    parser.add_argument(
        "--only-book",
        type=str,
        default=None,
        help=(
            "Only generate a single book by file slug (e.g. genesis). Every book is still "
            "converted, so that its notes are numbered as in a full run."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Read and convert the whole download, writing nothing (run it after moving "
            "download.COMMIT)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = _build_arg_parser().parse_args(argv)

    data_dir = miqra_al_pi_hamasorah_data_directory(args.sourcetexts_root)
    out_dir = args.project_dir if args.project_dir is not None else _default_project_directory()

    if args.dry_run:
        logger.info("Would read MAM-parsed plus from %s", data_dir)
        logger.info("Would write project files to %s", out_dir)
        if args.only_book:
            logger.info("Would generate only book: %s", args.only_book)
        return 0

    book = None
    if args.only_book:
        all_books = {b.file_name: b for b in _flatten_books(TANAKH_INDEX)}
        book = all_books.get(args.only_book)
        if book is None:
            raise ValueError(f"Unknown book slug: {args.only_book}")

    source = load_source(args.sourcetexts_root)
    intermediates = convert_books(source)
    if args.check:
        logger.info(
            "MAM-parsed plus at %s converts (all %d books)", source.commit, len(intermediates)
        )
        return 0
    if book is not None:
        book_file(
            book,
            source=source,
            intermediate=intermediates[book.file_name],
            project_dir=args.project_dir,
        )
        return 0

    # Generate index + all transclusions recursively
    index_file(
        TANAKH_INDEX[0], source=source, intermediates=intermediates, project_dir=args.project_dir
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
