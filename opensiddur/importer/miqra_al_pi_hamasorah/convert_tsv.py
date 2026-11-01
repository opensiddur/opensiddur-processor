from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

import mwparserfromhell

from opensiddur.common.constants import PROJECT_DIRECTORY
from opensiddur.common.versification import MIQRA_PROJECT
from opensiddur.common.subverse import add_subverse_milestones
from opensiddur.common.xslt import xslt_transform_string
from opensiddur.importer.util.pages import (
    default_sourcetexts_root,
    miqra_al_pi_hamasorah_sheets_directory,
)
from opensiddur.importer.util.prettify import prettify_xml
from opensiddur.importer.util.validation import validate
from opensiddur.importer.miqra_al_pi_hamasorah.canonical_verses import annotate_canonical_verses
from opensiddur.importer.miqra_al_pi_hamasorah.miqra_wikitext import (
    wikitext_to_intermediate_xml,
)

logger = logging.getLogger(__name__)

MIQRA_TO_TEI_XSLT = Path(__file__).parent / "miqra_to_tei.xslt"

# Biblical-book tabs only (5-column A–E schema). Do not ingest special/auto_edits/etc.
BIBLICAL_TSV_SLUGS = frozenset(
    {
        "torah",
        "neviim_rishonim",
        "neviim_acharonim",
        "sifrei_emet",
        "chamisha_megillot",
        "ketuvim_aharonim",
    }
)

_NON_VERSE_ROW_IDS = frozenset({"0", "תתת"})


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
        <tei:note xml:lang="en">Prepared by Avi Kadish, based on Hebrew Wikisource material; distributed via a public Google Sheet.</tei:note>
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


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


_PAGE_KEY_RE = re.compile(r"^\s*(?:(?:ספר|מגילת)\s+)?(?P<book>[^/]+)\s*/\s*(?P<rest>.+?)\s*$")

# Some sheet tabs group several books under one outer "ספר X" label, with the
# actual sub-book abbreviated and embedded alongside the chapter numeral in
# the second field (e.g. "ספר שמואל/שמ""א א" -> sub-book שמ"א, chapter א).
_SUBBOOK_ABBREVIATIONS = {
    'שמ"א': "שמואל א",
    'שמ"ב': "שמואל ב",
    'מל"א': "מלכים א",
    'מל"ב': "מלכים ב",
    'דה"א': "דברי הימים א",
    'דה"ב': "דברי הימים ב",
}


def _split_page_key(page_key: str) -> Optional[tuple[str, str]]:
    """Resolve a page key to (book_name_he, chapter_token), or None if unparseable."""
    m = _PAGE_KEY_RE.match(page_key or "")
    if not m:
        return None
    outer_book = m.group("book").strip()
    rest = m.group("rest").strip()
    parts = rest.split(None, 1)
    if len(parts) == 2:
        sub_label, chapter_token = parts
        book = _SUBBOOK_ABBREVIATIONS.get(sub_label, sub_label)
        return book, chapter_token
    return outer_book, rest


def _book_key_from_page_key(page_key: str) -> Optional[str]:
    parsed = _split_page_key(page_key)
    return parsed[0] if parsed else None


_HEBREW_NUM_RE = re.compile(r"^[\u05d0-\u05ea\"׳״\s]+$")


def _hebrew_numeral_to_int(value: str) -> Optional[int]:
    """
    Very small Hebrew-numeral parser for verse/chapter labels.

    Handles single-letter verse labels (א,ב,ג,...) and common gershayim/geresh marks.
    For anything more complex, we return None and fall back to original.
    """
    s = (value or "").strip()
    if not s:
        return None
    s = s.replace("״", "").replace("׳", "").replace("'", "").replace('"', "").strip()
    if not s:
        return None
    if not _HEBREW_NUM_RE.match(s):
        return None

    # Simple gematria for Hebrew letters
    mapping = {
        "א": 1,
        "ב": 2,
        "ג": 3,
        "ד": 4,
        "ה": 5,
        "ו": 6,
        "ז": 7,
        "ח": 8,
        "ט": 9,
        "י": 10,
        "כ": 20,
        "ך": 20,
        "ל": 30,
        "מ": 40,
        "ם": 40,
        "נ": 50,
        "ן": 50,
        "ס": 60,
        "ע": 70,
        "פ": 80,
        "ף": 80,
        "צ": 90,
        "ץ": 90,
        "ק": 100,
        "ר": 200,
        "ש": 300,
        "ת": 400,
    }

    total = 0
    for ch in s:
        if ch.isspace():
            continue
        v = mapping.get(ch)
        if v is None:
            return None
        total += v
    return total if total > 0 else None


def _normalize_to_arabic_numerals(value: str) -> str:
    s = (value or "").strip()
    if not s:
        return ""
    if s.isdigit():
        return s
    n = _hebrew_numeral_to_int(s)
    if n is not None:
        return str(n)
    return ""


def _valid_urn_segment(value: str) -> str:
    """Return an Arabic numeral string suitable for URN path segments, or empty."""
    normalized = _normalize_to_arabic_numerals(value)
    return normalized if normalized.isdigit() else ""


def _chapter_from_page_key(page_key: str) -> str:
    parsed = _split_page_key(page_key)
    if not parsed:
        return ""
    return _normalize_to_arabic_numerals(parsed[1])


def _extract_m_pasuk(scaffold_wikitext: str) -> tuple[str, str]:
    """
    Extract (chapter, verse) from {{מ:פסוק|...}} when present.
    Expected: {{מ:פסוק|<book>|<chapter>|<verse>}}.
    """
    parsed = mwparserfromhell.parse(scaffold_wikitext or "")
    # Top-level only: avoid nested {{מ:פסוק|...}} inside verse text in other columns.
    for t in parsed.filter_templates(recursive=False):
        if str(t.name).strip() != "מ:פסוק":
            continue
        ch_raw = str(t.get(2).value).strip() if t.has(2) else ""
        v_raw = str(t.get(3).value).strip() if t.has(3) else ""
        ch = _valid_urn_segment(ch_raw)
        v = _valid_urn_segment(v_raw)
        if ch and v:
            return ch, v
    return "", ""


def _extract_chapter_verse_numbers(page_key: str, row_id: str, scaffold_wikitext: str) -> tuple[str, str]:
    row_id = (row_id or "").strip()
    if row_id in _NON_VERSE_ROW_IDS or len(row_id) > 8:
        return "", ""

    ch2, v2 = _extract_m_pasuk(scaffold_wikitext)
    if ch2 and v2:
        return ch2, v2

    chapter = _valid_urn_segment(_chapter_from_page_key(page_key))
    verse = _valid_urn_segment(row_id)
    if chapter and verse:
        return chapter, verse
    return "", ""


def _build_book_name_map() -> dict[str, Book]:
    # Map Hebrew book title → Book
    books = _flatten_books(TANAKH_INDEX)
    return {b.book_name_he: b for b in books}


def _iter_tsv_rows(tsv_path: Path) -> Iterable[list[str]]:
    with tsv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            yield row


def _looks_like_header_row(row: list[str]) -> bool:
    # Conservative heuristic: TSV export may include a header row with obvious labels.
    joined = "\t".join(row).lower()
    return any(k in joined for k in ("page", "row", "navigation", "scaffold", "text", "עמוד", "שורה"))


def miqra_rows_to_intermediate(book: Book, sheets_dir: Path) -> str:
    """
    Build an intermediate XML document for a single book.

    We scan all TSVs under sheets_dir and select rows whose page key identifies
    the requested book.
    """
    he_to_book = _build_book_name_map()
    target_he = book.book_name_he

    rows_xml: list[str] = []
    for tsv_path in sorted(sheets_dir.glob("*.tsv")):
        slug = tsv_path.stem
        if slug not in BIBLICAL_TSV_SLUGS:
            continue

        first = True
        for row in _iter_tsv_rows(tsv_path):
            if first and _looks_like_header_row(row):
                first = False
                continue
            first = False

            # Biblical tabs: require the 5-column A–E schema.
            if len(row) < 5:
                continue

            page_key = row[0]
            row_id = row[1]
            nav = row[2]
            scaffold = row[3]
            text = row[4]

            book_he = _book_key_from_page_key(page_key) or ""
            resolved = he_to_book.get(book_he)
            if resolved is None or resolved.book_name_he != target_he:
                continue

            chapter_n, verse_n = _extract_chapter_verse_numbers(page_key, row_id, scaffold)
            if not chapter_n or not verse_n:
                continue

            rows_xml.append(
                f"""<miqra:row source="{_xml_escape(slug)}" pageKey="{_xml_escape(page_key)}" rowId="{_xml_escape(row_id)}" chapter="{_xml_escape(chapter_n)}" verse="{_xml_escape(verse_n)}">
  <miqra:nav>{wikitext_to_intermediate_xml(nav, column_c=True)}</miqra:nav>
  <miqra:scaffold>{wikitext_to_intermediate_xml(scaffold)}</miqra:scaffold>
  <miqra:text>{wikitext_to_intermediate_xml(text)}</miqra:text>
</miqra:row>"""
            )

    rows_joined = "\n".join(rows_xml)
    return f"""<miqra:book xmlns:miqra="urn:x-opensiddur:miqra:intermediate" xmlns:mw="urn:x-opensiddur:mw:intermediate" fileName="{_xml_escape(book.file_name)}" bookNameHe="{_xml_escape(book.book_name_he)}" bookNameEn="{_xml_escape(book.book_name_en)}">
{rows_joined}
</miqra:book>
"""


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


def book_file(book: Book, *, sourcetexts_root: Path | None, project_dir: Path | None) -> None:
    sheets_dir = miqra_al_pi_hamasorah_sheets_directory(sourcetexts_root)
    if not sheets_dir.exists():
        raise FileNotFoundError(f"Missing Miqra sheets directory: {sheets_dir} (run download first)")

    intermediate = miqra_rows_to_intermediate(book, sheets_dir)
    intermediate = annotate_canonical_verses(intermediate, book.file_name)
    xml_dict = intermediate_to_tei(intermediate)
    header_xml = header(book.book_name_he, book.book_name_en, entrypoint=book.file_name)
    tei_content = tei_file(header_xml, **xml_dict)
    make_project_directory(project_dir)
    validate_and_write_tei_file(tei_content, book.file_name, project_dir, add_subverse=True)


def _readme_front_matter(sourcetexts_root: Path | None) -> str:
    sheets_dir = miqra_al_pi_hamasorah_sheets_directory(sourcetexts_root)
    readme = sheets_dir / "readme.tsv"
    if not readme.exists():
        return ""
    lines: list[str] = []
    for row in _iter_tsv_rows(readme):
        # Preserve all cells; this is human prose.
        line = " ".join(c for c in row if c).strip()
        if line:
            lines.append(line)
    paras = "\n".join([f"<tei:p>{_xml_escape(l)}</tei:p>" for l in lines])
    return f"<tei:front xmlns:tei=\"http://www.tei-c.org/ns/1.0\">{paras}</tei:front>"


def index_urn_name(file_name: str) -> str:
    """The name an index file's URN has: the whole canon is ``tanakh``, as in every Tanakh
    project; any other index (``the_prophets``) is named by its file."""
    return "tanakh" if file_name == "index" else file_name


def index_file(idx: Index, *, sourcetexts_root: Path | None, project_dir: Path | None) -> None:
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
    front = _readme_front_matter(sourcetexts_root) if idx.file_name == "index" else ""
    header_xml = header(idx.index_title_he, idx.index_title_en, entrypoint=index_urn_name(idx.file_name))
    tei_content = tei_file(header_xml, front=front, body=index_body)
    make_project_directory(project_dir)
    validate_and_write_tei_file(tei_content, idx.file_name, project_dir)

    for t in idx.transclusions:
        if isinstance(t, Index):
            index_file(t, sourcetexts_root=sourcetexts_root, project_dir=project_dir)
        else:
            book_file(t, sourcetexts_root=sourcetexts_root, project_dir=project_dir)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert Miqra al pi ha-Masorah TSV sheets to JLPTEI."
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
        help="Only generate a single book by file slug (e.g. genesis).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = _build_arg_parser().parse_args(argv)

    sheets_dir = miqra_al_pi_hamasorah_sheets_directory(args.sourcetexts_root)
    out_dir = args.project_dir if args.project_dir is not None else _default_project_directory()

    if args.dry_run:
        logger.info("Would read Miqra TSVs from %s", sheets_dir)
        logger.info("Would write project files to %s", out_dir)
        if args.only_book:
            logger.info("Would generate only book: %s", args.only_book)
        return 0

    if args.only_book:
        all_books = {b.file_name: b for b in _flatten_books(TANAKH_INDEX)}
        book = all_books.get(args.only_book)
        if book is None:
            raise ValueError(f"Unknown book slug: {args.only_book}")
        book_file(book, sourcetexts_root=args.sourcetexts_root, project_dir=args.project_dir)
        return 0

    # Generate index + all transclusions recursively
    index_file(TANAKH_INDEX[0], sourcetexts_root=args.sourcetexts_root, project_dir=args.project_dir)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

