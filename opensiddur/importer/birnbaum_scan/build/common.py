"""Envelope for the hand-authored Birnbaum TEI.

The bodies are written by hand, read off the scan, one function per prayer. This module
holds only what every file repeats: the header, the URN, the source pointer and the page
break sigils. Scaffolding — the TEI files it writes are the artifact.
"""
import re
from pathlib import Path

from opensiddur.importer.birnbaum_scan import SCAN_PAGE_PREFIX

PROJECT_HE = "hasiddur_hashalem-birnbaum-1949-he"
PROJECT_EN = "hasiddur_hashalem-birnbaum-1949-en"
#: Where the TEI is written. The opensiddur-projects submodule by default, so a fresh
#: checkout writes somewhere that exists; --project-directory overrides it, spelled the way
#: the compiler and pdf exporters already spell that flag.
DEFAULT_PROJECT_DIRECTORY = Path(__file__).resolve().parents[4] / "opensiddur-projects" / "project"
OUT = DEFAULT_PROJECT_DIRECTORY


def set_project_directory(path) -> Path:
    """Point the writers at `path`. Returns it, so a caller can report where it wrote."""
    global OUT
    OUT = Path(path)
    return OUT

IA = "https://archive.org/download/PhilipBirnbaumHaSiddurHaShalemTheDailyPrayerBook1949/page"

#: The second @ed token names which printing a break belongs to, since a shared text is
#: printed at several services. See SIDDUR_URN_SCHEME.md, "One text, printed on several pages".
#: Front matter is printed once, so it passes ``sigil=FRONT_SIGIL`` and names no printing.
#:
#: One sigil per unit, and :func:`pb` defaults to none of them. A default was safe while
#: there was one unit and became a trap the moment there were two: a page break authored in
#: the wrong module would be stamped with the other unit's printing, and nothing -- not the
#: schema, not the compiler, not the rendered PDF -- would say so. Each prayer module binds
#: its own sigil once, at import, so no call site carries it.
SIGIL_AMIDAH = "1949 chol/shacharit/amidah"
SIGIL_YELADIM = "1949 all/shacharit/yeladim"
SIGIL_BIRCHOT = "1949 all/shacharit/birkhot_hashachar"
SIGIL_PESUKEI = "1949 chol/shacharit/pesuqei_dezimrah"
SIGIL_SHEMA = "1949 chol/shacharit/shema"
FRONT_SIGIL = "1949"

PRAYER = "urn:x-opensiddur:text:prayer:"
SIDDUR = "urn:x-opensiddur:text:siddur:"
#: Piyyutim and zemiroth. `SIDDUR_URN_SCHEME.md` names Adon Olam and Yigdal
#: here rather than under `prayer:`, and addresses their stanzas by incipit.
POEM = "urn:x-opensiddur:text:poem:"
FRONT = "urn:x-opensiddur:text:front:"
#: A note is not a text. It takes no `text:` URN -- it is addressed by what it
#: annotates -- and `notes:` names the apparatus file itself, not anything in it.
NOTES = "urn:x-opensiddur:notes:"


#: IA leaf `n` is scan page `n + 1`, for the whole of this item. Fixed by how the Archive
#: numbers the scan, not by anything the book does.
LEAF_OFFSET = -1

#: Printed page -> scan page, for the pages read so far. The front matter is not in here:
#: the print numbers only twelve of its twenty-five leaves, so it is addressed by scan page.
#:
#: The +25 offset in fact holds for every numbered page in the book. The table is kept to
#: the pages actually read anyway, so that ``pb(500)`` raises rather than quietly
#: deep-linking a leaf nobody has looked at.
SCAN_PAGE = {p: p + 25 for p in range(1, 791)}


def leaf(page) -> int:
    """The IA leaf a page falls on.

    `page` is the number the book prints, or ``sN`` addressing scan page N -- which is how
    a leaf the print does not number is reached.

    This mapping is written out rather than read from ``pages.json`` on purpose. The prayer
    modules call :func:`pb` at import time, so reading a data file here would mean no part
    of the importer could even be imported without the sourcetexts submodule, and the unit
    tests would be testing the data rather than the code. `test_leaf_mapping_matches_pages_json`
    checks it against ``pages.json`` wherever the submodule is present, so it cannot drift.
    """
    token = str(page)
    if token.startswith(SCAN_PAGE_PREFIX):
        return int(token[len(SCAN_PAGE_PREFIX):]) + LEAF_OFFSET
    return SCAN_PAGE[int(token)] + LEAF_OFFSET


def pb(page, *, sigil: str, n: str | None = None) -> str:
    """A page break, deep-linked to the leaf it falls on.

    `sigil` is required: see :data:`SIGIL_AMIDAH` for why there is no default.

    `page` addresses the leaf; `n` is the designation printed on it, defaulting to `page`.
    They differ only in the front matter, where a leaf the book does not number is
    addressed as ``sN`` but designated with the number the book's own sequence implies.
    """
    return (f'<tei:pb n="{page if n is None else n}" ed="{sigil}" '
            f'facs="{IA}/n{leaf(page)}_medium.jpg"/>')


def header(*, title_he: str, title_en: str, urn: str, project: str,
           first: int, last: int, lang: str, printings=()) -> str:
    """The teiHeader every file carries.

    Philip Birnbaum gets no respStmt: a respStmt records who *digitised* a text, and he
    is the author, recorded as a source. The people who read this off the scan are the
    ones who digitised it.
    """
    if title_he:
        titles = f'<tei:title type="main" xml:lang="he">{title_he}</tei:title>'
        if title_en:
            titles += f'\n        <tei:title type="alt" xml:lang="en">{title_en}</tei:title>'
    else:
        titles = f'<tei:title type="main" xml:lang="en">{title_en}</tei:title>'
    scope = (f'<tei:biblScope unit="pages" from="{first}" to="{last}"/>'
             if first else "")
    scope += ''.join(f'\n          <tei:biblScope unit="pages" from="{a}" to="{b}"/>'
                     for a, b in printings)
    return f"""  <tei:teiHeader>
    <tei:fileDesc>
      <tei:titleStmt>
        {titles}
        <tei:respStmt>
          <tei:resp key="trc">Read from the 1949 scan and encoded by</tei:resp>
          <tei:name ref="urn:x-opensiddur:contributor:opensiddur.org/efraim-feinstein">Efraim Feinstein</tei:name>
        </tei:respStmt>
      </tei:titleStmt>
      <tei:editionStmt>
        <tei:edition>Read directly from the scanned 1949 printing, page by page</tei:edition>
      </tei:editionStmt>
      <tei:publicationStmt>
        <tei:distributor>
          <tei:ref target="http://opensiddur.org">Open Siddur Project</tei:ref>
        </tei:distributor>
        <tei:idno type="urn">{urn}@{project}</tei:idno>
        <tei:availability status="free">
          <tei:licence target="https://creativecommons.org/licenses/by-sa/4.0/">Creative Commons Attribution-ShareAlike 4.0 International</tei:licence>
        </tei:availability>
      </tei:publicationStmt>
      <tei:sourceDesc>
        <tei:bibl>
          <tei:ptr target="/{project}/index#project_source_bibl"/>
          {scope}
        </tei:bibl>
      </tei:sourceDesc>
    </tei:fileDesc>
  </tei:teiHeader>"""


def document(*, body: str, lang: str, **kw) -> str:
    from .scopes import scope_section_headings
    body = scope_section_headings(body)
    return (f'<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" '
            f'xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xml:lang="{lang}">\n'
            f'{header(lang=lang, **kw)}\n'
            f'  <tei:text>\n    <tei:body>\n{body}\n    </tei:body>\n  </tei:text>\n'
            f'</tei:TEI>\n')


def write(project: str, name: str, text: str) -> Path:
    path = OUT / project / f"{name}.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    from .page_references import dynamic_instructions
    path.write_text(dynamic_instructions(text, project), encoding="utf-8")
    return path


#: The rubrics Birnbaum prints over a conditional passage that say *what* the passage is, who
#: says it or how, rather than *when* it is said (schema/JLPTEI-3.md, *Kinds of rubric*). A
#: rubric saying when is the j:conditional's own, and is not printed once the condition is
#: known to hold; one of these belongs to the passage, so it is set as a description first
#: inside the scope and printed whenever the passage is. A rubric that says both is one of
#: these, since leaving it out would lose the name of the passage.
DESCRIPTIVE_RUBRICS = frozenset({
    # Who says it.
    "Reader:",
    "Reader, when a minyan holds service:",
    "On the Sabbath, Reader and Congregation:",
    "On the Sabbath, Congregation and Reader:",
    "Priestly blessing recited by the Reader:",
    "On fast days the Reader adds here:",
    "On fast days (except Tish‘ah b’Av) the Reader adds:",
    "On fast days, the Congregation recites here:",
    "When the Reader repeats the Amidah, the Congregation responds here by saying:",
    "When the Reader repeats the Shemoneh Esreh, the Congregation responds here by saying:",
    "On Mondays and Thursdays (if Taḥanun has been said), before returning the Torah to the "
    "ark, the Reader recites:",
    "In silent devotion:",
    # What it is.
    "Mourners’ Kaddish.",
    "MOURNERS’ KADDISH",
    "With a minyan, when Tzidduk Hadin is omitted, recite regular Mourner’s Kaddish:",
    "Full-Kaddish on Rosh Ḥodesh and festivals:",
    "Half-Kaddish on Ḥanukkah:",
    "When the Reader repeats the Amidah, the following Kedushah is said:",
    "When the Reader repeats the Amidah, the following Kedushah is said.",
    "When the Reader repeats the Shemoneh Esreh, the following Kedushah is said:",
    "After the Amidah add the following meditation:",
    "With a minyan: After the reading of the kethubah the seven blessings are chanted:",
    # How it is done.
    "There is a custom that mourners, in the first week of their mourning, remain at the "
    "entrance of the synagogue until one of the congregation says to them:",
    "Performed on the afternoon of the first day of Rosh Hashanah, or on the second, should "
    "Sabbath commence the festival. Processions are formed to the banks of a river, where the "
    "following is recited:",
    "Consisting in waving a fowl three times around the head after the recitation of the "
    "following paragraph on the day previous to Yom Kippur",
    "Waving a fowl over the heads:",
    "During Sukkoth (except Sabbath) the following is recited as the lulav (in the right hand) "
    "and the ethrog (in the left hand) are held together.",
    "When three men or more have eaten together, the following is used as an introduction to "
    "the grace. The addition is included when a minyan is present.",
})

_MARKUP = re.compile(r"<[^>]+>")


def is_descriptive_rubric(note: str) -> bool:
    """Whether a rubric says what its passage is rather than when it is said."""
    return " ".join(_MARKUP.sub("", note).split()) in DESCRIPTIVE_RUBRICS


def cond(cid: str, *, note: str = "", note_lang: str = "en", fs: str = "", negate: bool = False,
         note_urn: str = "", note_resp: str = "", marked: bool = False) -> str:
    """A j:conditional: the rubric the edition prints, and the test it states.

    ``marked`` says the book itself sets the passage off -- parentheses, or the asterisk that
    keys an ordinary reading to its substitute -- so an edition that cannot decide the
    condition sets it off too (schema/JLPTEI-3.md, *How an undecided scope is set off*).

    A rubric in :data:`DESCRIPTIVE_RUBRICS` is set after the j:conditional, as the first thing
    in its scope, rather than as the j:conditional's own note.
    """
    kind = ' type="marked"' if marked else ""
    parts = [f'        <j:conditional xml:id="{cid}"{kind}>']
    rubric = ""
    if note:
        attributes = (f' corresp="{note_urn}"' if note_urn else "")
        attributes += f' resp="{note_resp}"' if note_resp else ""
        if is_descriptive_rubric(note):
            rubric = (f'<tei:note type="description" xml:lang="{note_lang}"{attributes}>'
                      f'{note}</tei:note>')
        else:
            parts.append(f'          <tei:note type="instruction" xml:lang="{note_lang}"'
                         f'{attributes}>{note}</tei:note>')
    if negate:
        parts.append("          <j:none>")
        parts.append(fs)
        parts.append("          </j:none>")
    else:
        parts.append(fs)
    # Straight after the opener, with no whitespace between: the description is the first
    # thing in the scope, and a space before it would be text at the start of a paragraph.
    parts.append("        </j:conditional>" + rubric)
    return "\n".join(parts)


def endcond(cid: str) -> str:
    return f'        <j:endConditional target="#{cid}"/>'


def feature(fs_type: str, name: str, value: str = '<tei:binary value="true"/>') -> str:
    return (f'          <tei:fs type="{fs_type}">\n'
            f'            <tei:f name="{name}">\n'
            f'              {value}\n'
            f'            </tei:f>\n'
            f'          </tei:fs>')


AGG = "opensiddur:holiday-aggregate"
HOL = "opensiddur:holiday"
SERVICE = "opensiddur:service-time"
RECITATION = "opensiddur:recitation"
QUORUM = "opensiddur:quorum"
#: Who is saying it. Birnbaum sets two columns headed "Men say:" and "Women say:",
#: which no calendar can settle -- like the quorum, it is a fact about the people
#: praying. It takes no default, so a text compiled without knowing who will say it
#: keeps both columns with the rubrics that say who each is for.
PERSON = "opensiddur:person"


# Editorial wording, rather than a rubric attributed to the scanned edition.
# Both Kaddishes use the same conditional through their shared Yitbarakh segment.
TEN_DAYS_ADDITION = "During the Ten Days of Repentance, add:"
TEN_DAYS_ADDITION_URN = "urn:x-opensiddur:instruction:aseret_yemei_teshuvah/add"


def ten_days_addition(cid: str) -> str:
    """A standard instruction for an addition whose date may be undecided.

    The renderer places the instruction before brackets around the added words.
    Do not also encode the print's parentheses.
    The raw scan reading retains those diplomatic punctuation marks.
    """
    return cond(cid, note=TEN_DAYS_ADDITION,
                note_urn=TEN_DAYS_ADDITION_URN,
                note_resp="urn:x-opensiddur:contributor:opensiddur.org/efraim-feinstein",
                fs=feature(AGG, "aseret-ymei-tshuva"))


def standoff_document(*, notes: str, lang: str, **kw) -> str:
    """An apparatus file: a header and a tei:standOff, and no tei:text of its own.

    Birnbaum's footnotes annotate words that live in other files, so the apparatus has no
    text to carry. `tei:standOff` is a `model.resource` like `tei:text` is, so a document
    may hold one without the other -- which is what lets the apparatus be its own file
    rather than a tail on every prayer.

    The notes target `@corresp` URNs, never `#id`s. `refdb.get_references_to` matches a
    URN target across every project, and an `#id` target only within the one file that
    declares it, so an apparatus in its own file can only reach the text by URN.
    """
    return (f'<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" '
            f'xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xml:lang="{lang}">\n'
            f'{header(lang=lang, **kw)}\n'
            f'  <tei:standOff type="notes">\n{notes}\n  </tei:standOff>\n'
            f'</tei:TEI>\n')
