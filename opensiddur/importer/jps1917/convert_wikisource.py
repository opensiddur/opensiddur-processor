import argparse
import logging
import re
from pathlib import Path
from typing import Any, Optional
import urllib

from pydantic import BaseModel

from opensiddur.importer.util.pages import (
    default_sourcetexts_root,
    get_credits,
    get_page,
    jps1917_data_directory,
)
from opensiddur.importer.util.wikisource_book import download_date
from opensiddur.importer.jps1917.canonical_verses import annotate_canonical_verses
from opensiddur.importer.jps1917.mediawiki_processor import create_processor
from opensiddur.importer.jps1917.wikisource import BOOK_NAME
from opensiddur.importer.util.parshiyot import skeleton_map_json
from opensiddur.importer.util.prettify import prettify_xml
from opensiddur.importer.util.validation import validate
from opensiddur.common.xslt import xslt_transform_string
from opensiddur.common.constants import PROJECT_DIRECTORY
from opensiddur.common.versification import JPS_PROJECT

logger = logging.getLogger(__name__)

MEDIAWIKI_TO_TEI_XSLT = Path(__file__).parent / "mediawiki_to_tei.xslt"

# What the header reported before the downloader kept a manifest. Used only when there
# is none to read, so that a conversion run against a tree downloaded by the old
# scraper still states the date those files were actually fetched.
FALLBACK_DOWNLOAD_DATE = "2025-07-27"


def source_download_date(sourcetexts_root: Path | None = None) -> str:
    """The date the Wikisource pages under this tree were last downloaded."""
    return download_date(jps1917_data_directory(sourcetexts_root)) or FALLBACK_DOWNLOAD_DATE


def make_project_directory(project_dir: Path | None = None) -> Path:
    """Create the JPS 1917 project directory if missing; return its path."""
    directory = (
        project_dir.resolve()
        if project_dir is not None
        else PROJECT_DIRECTORY / JPS_PROJECT
    )
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _default_project_directory() -> Path:
    return PROJECT_DIRECTORY / JPS_PROJECT

class Book(BaseModel):
    book_name_he: str
    book_name_en: str
    file_name: str
    start_page: int
    end_page: int
    is_section: Optional[bool] = False
    # The parshah a book of the Torah opens with. The source marks parshiyot with a centered
    # running head, but the first one of each book has none — the book's title heading is
    # printed in its place — so it has to be declared here.
    first_parsha: Optional[str] = None

class Index(BaseModel):
    index_title_en: str
    index_title_he: Optional[str] = None
    index_sub_he: Optional[str] = None
    index_sub_en: Optional[str] = None
    file_name: str
    transclusions: list #[Book | Index]
    start_page: Optional[int] = None
    end_page: Optional[int] = None

PAGE_OFFSET = 22
#: A page of the scan Wikisource transcribes, by its number in the scan: `@facs` of each page
#: break (schema/JLPTEI-3.md). The page shows the scan beside its transcription.
FACS_PREFIX = f"https://en.wikisource.org/wiki/Page:{BOOK_NAME}/"
#: The scan itself.
SCAN_URL = f"https://commons.wikimedia.org/wiki/File:{BOOK_NAME}"

JPS_1917 = [
    Index(
        index_title_en = "The Holy Scriptures",
        index_title_he = "תורה נביאים וכתובים",
        index_sub_he = None,
        index_sub_en = "According to the Masoretic Text: A New Translation With The Aid of Previous Versions And With Constant Consultation of Jewish Authorities",
        file_name = "index",
        # preface = front matter
        start_page = 9,
        end_page = 18,
        transclusions = [
            Index(
                index_title_en = "The Law",
                index_title_he = "תורה",
                file_name = "the_law",
                transclusions = [
                    Book(
                        book_name_en = "Genesis", 
                        book_name_he = "בראשית", 
                        file_name = "genesis", 
                        first_parsha = "בראשית", 
                        start_page = 3+PAGE_OFFSET, 
                        end_page = 64+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "Exodus", 
                        book_name_he = "שמות", 
                        file_name = "exodus", 
                        first_parsha = "שמות", 
                        start_page = 65+PAGE_OFFSET, 
                        end_page = 117+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "Leviticus", 
                        book_name_he = "ויקרא", 
                        file_name = "leviticus", 
                        first_parsha = "ויקרא", 
                        start_page = 118+PAGE_OFFSET, 
                        end_page = 156+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "Numbers", 
                        book_name_he = "במדבר", 
                        file_name = "numbers", 
                        first_parsha = "במדבר", 
                        start_page = 157+PAGE_OFFSET, 
                        end_page = 211+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "Deuteronomy", 
                        book_name_he = "דברים", 
                        file_name = "deuteronomy", 
                        first_parsha = "דברים", 
                        start_page = 212+PAGE_OFFSET, 
                        end_page = 258+PAGE_OFFSET
                    ),
                ],
            ),
            Index(
                index_title_en = "The Prophets",
                index_title_he = "נביאים",
                file_name = "the_prophets",
                transclusions = [
                    Book(
                        book_name_en = "Joshua",
                        book_name_he = "יהושע",
                        file_name = "joshua",
                        start_page = 261+PAGE_OFFSET,
                        end_page = 292+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "Judges",
                        book_name_he = "שפטים",
                        file_name = "judges",
                        start_page = 293+PAGE_OFFSET,
                        end_page = 324+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "I Samuel",
                        book_name_he = "שמואל א",
                        file_name = "samuel_1",
                        start_page = 325+PAGE_OFFSET,
                        end_page = 365+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "II Samuel",
                        book_name_he = "שמואל ב",
                        file_name = "samuel_2",
                        start_page = 366+PAGE_OFFSET,
                        end_page = 400+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "I Kings",
                        book_name_he = "מלכים א",
                        file_name = "kings_1",
                        start_page = 401+PAGE_OFFSET,
                        end_page = 440+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "II Kings",
                        book_name_he = "מלכים ב",
                        file_name = "kings_2",
                        start_page = 441+PAGE_OFFSET,
                        end_page = 478+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "Isaiah",
                        book_name_he = "ישעיה",
                        file_name = "isaiah",
                        start_page = 479+PAGE_OFFSET,
                        end_page = 560+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "Jeremiah",
                        book_name_he = "ירמיה",
                        file_name = "jeremiah",
                        start_page = 561+PAGE_OFFSET,
                        end_page = 643+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "Ezekiel",
                        book_name_he = "יחזקאל",
                        file_name = "ezekiel",
                        start_page = 644+PAGE_OFFSET,
                        end_page = 708+PAGE_OFFSET
                    ),
                    Index(
                        index_title_en = "The Twelve",
                        file_name = "the_twelve",
                        transclusions = [
                            Book(
                                book_name_en = "Hosea",
                                book_name_he = "הושע",
                                file_name = "hosea",
                                start_page = 709+PAGE_OFFSET,
                                end_page = 720+PAGE_OFFSET,
                                is_section = True,
                            ),
                            Book(
                                book_name_en = "Joel",
                                book_name_he = "יואל",
                                file_name = "joel",
                                start_page = 720+PAGE_OFFSET,
                                end_page = 725+PAGE_OFFSET,
                                is_section = True,
                            ),
                            Book(
                                book_name_en = "Amos",
                                book_name_he = "עמוס",
                                file_name = "amos",
                                start_page = 725+PAGE_OFFSET,
                                end_page = 734+PAGE_OFFSET,
                                is_section = True,
                            ),
                            Book(
                                book_name_en = "Obadiah",
                                book_name_he = "עובדיה",
                                file_name = "obadiah",
                                start_page = 734+PAGE_OFFSET,
                                end_page = 736+PAGE_OFFSET,
                                is_section = True,
                            ),
                            Book(
                                book_name_en = "Jonah",
                                book_name_he = "יונה",
                                file_name = "jonah",
                                start_page = 736+PAGE_OFFSET,
                                end_page = 738+PAGE_OFFSET,
                                is_section = True,
                            ),
                            Book(
                                book_name_en = "Micah", 
                                book_name_he = "מיכה",
                                file_name = "micah",
                                start_page = 739+PAGE_OFFSET,
                                end_page = 746+PAGE_OFFSET,
                                is_section = True,
                            ),
                            Book(
                                book_name_en = "Nahum",
                                book_name_he = "נחום",
                                file_name = "nahum",
                                start_page = 746+PAGE_OFFSET,
                                end_page = 749+PAGE_OFFSET,
                                is_section = True,
                            ),
                            Book(
                                book_name_en = "Habakkuk",
                                book_name_he = "חבקוק",
                                file_name = "habakkuk",
                                start_page = 749+PAGE_OFFSET,
                                end_page = 752+PAGE_OFFSET,
                                is_section = True,
                            ),
                            Book(
                                book_name_en = "Zephaniah",
                                book_name_he = "צפניה",
                                file_name = "zephaniah",
                                start_page = 753+PAGE_OFFSET,
                                end_page = 756+PAGE_OFFSET,
                                is_section = True,
                            ),
                            Book(
                                book_name_en = "Haggai",
                                book_name_he = "חגי",
                                file_name = "haggai",
                                start_page = 757+PAGE_OFFSET,
                                end_page = 758+PAGE_OFFSET,
                                is_section = True,
                            ),
                            Book(
                                book_name_en = "Zechariah",
                                book_name_he = "זכריה",
                                file_name = "zechariah",
                                start_page = 759+PAGE_OFFSET,
                                end_page = 770+PAGE_OFFSET,
                                is_section = True,
                            ),
                            Book(
                                book_name_en = "Malachi",
                                book_name_he = "מלאכי",
                                file_name = "malachi",
                                start_page = 770+PAGE_OFFSET,
                                end_page = 774+PAGE_OFFSET,
                                is_section = True,
                            ),
                        ],
                    ),
                ],
            ),
            Index(
                index_title_en = "The Writings",
                index_title_he = "כתובים",
                file_name = "the_writings",
                transclusions = [
                    Book(
                        book_name_en = "Psalms",
                        book_name_he = "תהילים",
                        file_name = "psalms",
                        start_page = 777+PAGE_OFFSET,
                        end_page = 882+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "Proverbs",
                        book_name_he = "משלי",
                        file_name = "proverbs",
                        start_page = 883+PAGE_OFFSET,
                        end_page = 923+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "Job",
                        book_name_he = "איוב",
                        file_name = "job",
                        start_page = 924+PAGE_OFFSET,
                        end_page = 965+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "Song of Songs",
                        book_name_he = "שיר השירים",
                        file_name = "song_of_songs",
                        start_page = 966+PAGE_OFFSET,
                        end_page = 972+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "Ruth",
                        book_name_he = "רות",
                        file_name = "ruth",
                        start_page = 973+PAGE_OFFSET,
                        end_page = 977+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "Lamentations",
                        book_name_he = "איכה",
                        file_name = "lamentations",
                        start_page = 978+PAGE_OFFSET,
                        end_page = 986+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "Ecclesiastes",
                        book_name_he = "קהלת",
                        file_name = "ecclesiastes",
                        start_page = 987+PAGE_OFFSET,
                        end_page = 996+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "Esther",
                        book_name_he = "אסתר",
                        file_name = "esther",
                        start_page = 997+PAGE_OFFSET,
                        end_page = 1006+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "Daniel",
                        book_name_he = "דניאל",
                        file_name = "daniel",
                        start_page = 1007+PAGE_OFFSET,
                        end_page = 1026+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "Ezra",
                        book_name_he = "עזרא",
                        file_name = "ezra",
                        start_page = 1027+PAGE_OFFSET,
                        end_page = 1039+PAGE_OFFSET,
                        is_section = True,
                    ),
                    Book(
                        book_name_en = "Nehemiah",
                        book_name_he = "נחמיה",
                        file_name = "nehemiah",
                        start_page = 1039+PAGE_OFFSET,
                        end_page = 1057+PAGE_OFFSET,
                        is_section = True,
                    ),
                    Book(
                        book_name_en = "I Chronicles",
                        book_name_he = "דברי הימים א",
                        file_name = "chronicles_1",
                        start_page = 1058+PAGE_OFFSET,
                        end_page = 1093+PAGE_OFFSET
                    ),
                    Book(
                        book_name_en = "II Chronicles",
                        book_name_he = "דברי הימים ב",
                        file_name = "chronicles_2",
                        start_page = 1094+PAGE_OFFSET,
                        end_page = 1136+PAGE_OFFSET
                    ),
                ],
            )
        ],
    ),
]

def get_credits_pages(
    start_page: int, end_page: int, sourcetexts_root: Path | None = None
) -> list[str]:
    credits = set()
    for page in range(start_page, end_page + 1):
        page_credits = get_credits(page, sourcetexts_root)
        if page_credits is not None:
            credits.update(page_credits)
    return sorted(credits)

def header(
    book_name_he: str,
    book_name_en: str,
    book_sub_he: Optional[str] = None,
    book_sub_en: Optional[str] = None,
    namespace: str = "bible",
    entrypoint: str = "tanakh",
    qualifier: str = "",
    project_id: str = JPS_PROJECT,
    license_url: str = "http://www.creativecommons.org/publicdomain/zero/1.0/",
    license_name: str = "Creative Commons Public Domain Dedication 1.0",
    transcription_credits: Optional[list[str]] = None,
    source_download_date: Optional[str] = None,
):
    transcription_credits = transcription_credits or []
    source_download_date = source_download_date or FALLBACK_DOWNLOAD_DATE
    book_sub_he = (
        f"""<tei:title type="alt-sub" xml:lang="he">{book_sub_he}</tei:title>"""
        if book_sub_he else ""
    )
    book_sub_en = (
        f"""<tei:title type="alt-sub" xml:lang="en">{book_sub_en}</tei:title>"""
        if book_sub_en else ""
    )

    resp_stmt_str = "\n".join([
        f"""<tei:respStmt>
            <tei:resp key="trc">Transcribed by</tei:resp>
            <tei:name ref="urn:x-opensiddur:contributor:en.wikisource.org/{urllib.parse.quote(contributor_name)}">{contributor_name} (English Wikisource contributor)</tei:name>
        </tei:respStmt>"""
        for contributor_name in transcription_credits if contributor_name != "Wikisource-bot"
    ])

    return f"""<tei:teiHeader>
    <tei:fileDesc>
        <tei:titleStmt>
            <tei:title type="main" xml:lang="en">{book_name_en}</tei:title>
            {book_sub_en}
            <tei:title type="alt" xml:lang="he">{book_name_he}</tei:title>
            {book_sub_he}
            {resp_stmt_str}
         </tei:titleStmt>
         <tei:publicationStmt>
            <tei:distributor>
               <tei:ref target="http://opensiddur.org">Open Siddur Project</tei:ref>
            </tei:distributor>
            <tei:idno type="urn">urn:x-opensiddur:text:{namespace}:{entrypoint}{qualifier}@{project_id}</tei:idno>
            <tei:availability status="free">
               <tei:licence target="{license_url}">{license_name}</tei:licence>
            </tei:availability>
         </tei:publicationStmt>
         <tei:sourceDesc>
            <tei:bibl>
                <tei:title>Bible (Jewish Publication Society 1917)</tei:title>
                <tei:distributor><tei:ref target="https://en.wikisource.org">Wikisource</tei:ref></tei:distributor>
                <tei:idno type="url">https://en.wikisource.org/wiki/Bible_(Jewish_Publication_Society_1917)</tei:idno>
                <tei:date>{source_download_date}</tei:date>
            </tei:bibl>
            <tei:bibl>
               <tei:title type="main">The Holy Scriptures</tei:title>
               <tei:title type="sub">According to the Masoretic Text: A New Translation With The Aid of Previous Versions And With Constant Consultation of Jewish Authorities</tei:title>
               <tei:title xml:lang="he" type="alt">תורה נביאים וכתובים</tei:title>
               <tei:edition>Third Impression, August 1919</tei:edition>
               <tei:publisher>Jewish Publication Society of America</tei:publisher>
               <tei:pubPlace>Philadelphia</tei:pubPlace>
               <tei:date>1917</tei:date>
               <tei:note>Lakeside Press, Chicago</tei:note>
               <tei:idno type="url">{SCAN_URL}</tei:idno>
            </tei:bibl>
        </tei:sourceDesc>
    </tei:fileDesc>
</tei:teiHeader>
"""

# Transcription of the title leaf of the printed 1917 edition: Wikisource page 7 (recto,
# the title page proper) and page 8 (verso, the copyright statement). Both are short and
# entirely deterministic, so they are transcribed here rather than run through the LLM
# encoding agent along with the preface (which starts at page 9). The foliation is the
# printed book's own — the preface that follows opens at page iii.
TITLE_PAGE = f"""<tei:pb n="i" ed="1917" facs="{FACS_PREFIX}7"/>
    <tei:titlePage>
        <tei:docTitle>
            <tei:titlePart type="alt" xml:lang="he">תורה נביאים וכתובים</tei:titlePart>
            <tei:titlePart type="main">THE HOLY SCRIPTURES</tei:titlePart>
            <tei:titlePart type="sub">ACCORDING TO THE MASORETIC TEXT</tei:titlePart>
            <tei:titlePart type="sub">A NEW TRANSLATION</tei:titlePart>
            <tei:titlePart type="sub">WITH THE AID OF PREVIOUS VERSIONS AND WITH<tei:lb/>CONSTANT CONSULTATION OF JEWISH AUTHORITIES</tei:titlePart>
        </tei:docTitle>
        <tei:docImprint>
            <tei:pubPlace>PHILADELPHIA</tei:pubPlace>
            <tei:publisher>THE JEWISH PUBLICATION SOCIETY OF AMERICA</tei:publisher>
            <tei:docDate>5677–1917</tei:docDate>
        </tei:docImprint>
    </tei:titlePage>
    <tei:pb n="ii" ed="1917" facs="{FACS_PREFIX}8"/>
    <tei:titlePage type="copyright">
        <tei:docImprint>Copyright, 1917,<tei:lb/>By <tei:publisher>The Jewish Publication Society of America</tei:publisher><tei:lb/><tei:hi rend="italic">All rights reserved</tei:hi></tei:docImprint>
        <tei:docEdition>Third Impression, August, 1919</tei:docEdition>
        <tei:docImprint>The Lakeside Press, Chicago</tei:docImprint>
    </tei:titlePage>
    """

_FRONT_OPEN_TAG = re.compile(r"<tei:front\b[^>]*>")


def prepend_to_front(front_xml: str, fragment: str) -> str:
    """Insert ``fragment`` as the first content of a ``tei:front`` element.

    ``front_xml`` is the serialized ``<tei:front>...</tei:front>`` produced by the
    MediaWiki-to-TEI transform (which carries its own namespace declarations), or the
    empty string when there is no front matter yet.
    """
    if not front_xml.strip():
        return f"<tei:front>\n    {fragment}</tei:front>"
    match = _FRONT_OPEN_TAG.search(front_xml)
    if match is None:
        raise ValueError("front matter does not start with a tei:front element")
    return front_xml[: match.end()] + "\n    " + fragment + front_xml[match.end():]


def tei_file(
    header: str,
    default_lang: str = "en",
    front: str = "",
    body: str = "",
    back: str = "",
    standOff: str = "",
):
    return f"""<tei:TEI xml:lang="{default_lang}" xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    {header}
    <tei:text>
    {front}
    {body}
    {back}
    </tei:text>
    {standOff}
    </tei:TEI>
    """

def mediawiki_xml_to_tei(xml_content: str, 
    xslt_params: Optional[dict[str, Any]] = None,
    mediawiki_to_tei_xslt: Path = MEDIAWIKI_TO_TEI_XSLT,
):
    outputs = xslt_transform_string(mediawiki_to_tei_xslt, xml_content, multiple_results=True, xslt_params=xslt_params)
    return {
        "front": outputs[""] if "tei:front" in outputs[""] else "",
        "body": outputs[""] if "tei:body" in outputs[""] else "",
        "standOff": outputs["standoff"] if "standoff" in outputs and "tei:note" in outputs["standoff"] else "",
    }

def process_mediawiki(
    start_page: int,
    end_page: int,
    wrapper_element: str,
    sourcetexts_root: Path | None = None,
    **kwargs,
) -> str:
    mw_processor = create_processor()
    start_page = start_page
    end_page = end_page

    content = ""
    for page in range(start_page, end_page + 1):
        logger.info("Processing page %s", page)
        page_obj = get_page(page, sourcetexts_root)
        if page_obj is None:
            raise FileNotFoundError(
                f"JPS 1917 page file missing for page {page} (check sourcetexts tree)"
            )
        page_content = page_obj.content
        page_xml = mw_processor.process_wikitext(page_content).xml_content
        # Which scan page this is, for the page break's link to it (mediawiki_to_tei.xslt).
        page_xml = page_xml.replace("<mediawiki>", f'<mediawiki scan="{page}">', 1)
        content += " " + page_xml

    pre_xml = f"""<tei:{wrapper_element} xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">
    <mediawikis>{content}</mediawikis>
    </tei:{wrapper_element}>
    """
    book_name = kwargs.get("book_name")
    if book_name:
        pre_xml = annotate_canonical_verses(pre_xml, book_name)
    # Path("temp").mkdir(parents=True, exist_ok=True)
    # with open(f"temp/{kwargs.get("book_name", "temp")}.temp.xml", "w") as f:
    #     f.write(pre_xml)
    return mediawiki_xml_to_tei(pre_xml, xslt_params={**kwargs, "facs_prefix": FACS_PREFIX})

def validate_and_write_tei_file(
    tei_content: str,
    file_name: str,
    project_dir: Path | None = None,
):
    directory = (
        project_dir.resolve() if project_dir is not None else _default_project_directory()
    )
    out_path = directory / f"{file_name}.xml"
    logger.info("Writing %s", out_path)
    pretty_xml = prettify_xml(tei_content, remove_xml_declaration=True)
    is_valid, errors = validate(pretty_xml)
    if not is_valid:
        raise Exception(f"Errors in {file_name}: {errors}")
    with open(out_path, "w") as f:
        f.write(pretty_xml)

def book_file(
    book: Book,
    sourcetexts_root: Path | None = None,
    project_dir: Path | None = None,
) -> str:
    transcription_credits = get_credits_pages(
        book.start_page, book.end_page, sourcetexts_root
    )
    header_content = header(
        book_name_he = book.book_name_he,
        book_name_en = book.book_name_en,
        entrypoint = book.file_name,
        transcription_credits = transcription_credits,
        source_download_date = source_download_date(sourcetexts_root),
    )
    xml_dict = process_mediawiki(
        book.start_page,
        book.end_page,
        "body",
        sourcetexts_root=sourcetexts_root,
        wrapper_div_type="book",
        book_name=book.file_name,
        is_section=book.is_section,
        parsha_names=skeleton_map_json(),
        first_parsha=book.first_parsha or "",
    )

    tei_content = tei_file(
        header = header_content,
        **xml_dict,
    )
    validate_and_write_tei_file(tei_content, book.file_name, project_dir)

    return tei_content


def index_file(
    idx: Index,
    sourcetexts_root: Path | None = None,
    project_dir: Path | None = None,
) -> str:
    if idx.start_page is not None and idx.end_page is not None:
        transcription_credits = get_credits_pages(
            idx.start_page, idx.end_page, sourcetexts_root
        )
    else:
        transcription_credits = None
    # The top-level index stands for the whole Tanakh, so it keeps the tanakh URN; the
    # sub-indices name themselves. Either way the document URN matches the body div below,
    # so no two files in the project claim the same one.
    entrypoint = "tanakh" if idx.file_name == "index" else idx.file_name
    header_content = header(
        book_name_he = idx.index_title_he,
        book_name_en = idx.index_title_en,
        book_sub_he = idx.index_sub_he,
        book_sub_en = idx.index_sub_en,
        entrypoint = entrypoint,
        transcription_credits = transcription_credits,
        source_download_date = source_download_date(sourcetexts_root),
    )
    if idx.start_page is not None and idx.end_page is not None:
        xml_dict = process_mediawiki(
            idx.start_page,
            idx.end_page,
            "front",
            sourcetexts_root=sourcetexts_root,
            wrapper_div_type="",
            book_name="",
            parsha_names=skeleton_map_json(),
        )
    else:
        xml_dict = {}

    # Only the top-level index stands for the book as a whole, so only it carries the
    # printed title page. The sub-indices (the_law, the_prophets, the_writings) are
    # structural and have no front matter of their own.
    if idx.file_name == "index":
        xml_dict["front"] = prepend_to_front(xml_dict.get("front", ""), TITLE_PAGE)

    transclusion_str = "\n".join([
        f"""<j:transclude target="urn:x-opensiddur:text:bible:{book.file_name}"/>"""
        for book in idx.transclusions
    ])
    index_body = f"""<tei:body>
    <tei:div corresp="urn:x-opensiddur:text:bible:{entrypoint}">
        <tei:head>{idx.index_title_en}</tei:head>
        {transclusion_str}
    </tei:div>
</tei:body>
    """
    xml_dict["body"] = index_body

    tei_content = tei_file(
        header = header_content,
        **xml_dict,
    )
    validate_and_write_tei_file(tei_content, idx.file_name, project_dir)

    for transclusion in idx.transclusions:
        if isinstance(transclusion, Index):
            index_file(transclusion, sourcetexts_root, project_dir)
        else:
            book_file(transclusion, sourcetexts_root, project_dir)

    return tei_content


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert JPS 1917 Wikisource page dumps to JLPTEI under "
                    f"opensiddur-projects/project/{JPS_PROJECT}."
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=_default_project_directory(),
        help=(
            "Output directory for generated JLPTEI "
            f"(default: <repo>/opensiddur-projects/project/{JPS_PROJECT})."
        ),
    )
    parser.add_argument(
        "--sourcetexts-root",
        type=Path,
        default=default_sourcetexts_root(),
        help=(
            "Root of the opensiddur/sourcetexts repository; page text is read from "
            "<root>/jps1917 (default: <repo>/sourcetexts/sources)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> None:  # pragma: no cover
    args = _build_arg_parser().parse_args(argv)
    project_directory = make_project_directory(args.project_dir)
    for part in JPS_1917:
        index_file(part, args.sourcetexts_root, project_directory)


if __name__ == "__main__":  # pragma: no cover
    # Only the CLI turns the progress log on. Tests call these functions directly, so under
    # the test runner the records go nowhere.
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()