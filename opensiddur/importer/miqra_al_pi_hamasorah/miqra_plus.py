"""
Convert Miqra al pi ha-Masorah, as MAM-parsed plus JSON, to intermediate XML.

MAM-basics' ``MAM-parsed/plus/*.json`` holds MAM's Hebrew Wikisource wikitext parsed into
trees (https://bdenckla.github.io/MAM-basics/MAM-parsed/plus/html/mpplus.html). A verse is
``[C, D, E]``: the separator from the previous verse, the verse label and the verse proper,
each a list of strings and templates ``{"tmpl_name": ..., "tmpl_params": {...}}``. A
parameter's value is a string, a template or a list of strings and templates.

The walk is closed. Every template of the current plus roster has a handler here that names
the role of each of its parameters, and only the parameters it renders are walked into the
output; a parameter holding an alternative reading or apparatus is checked but not rendered.
An unknown template, a parameter outside a template's schema or a node of an unexpected shape
raises :class:`PlusFormatError`.

The output is the vocabulary ``miqra_to_tei.xslt`` reads (``miqra:*`` and ``mw:*``
elements), as the importer's earlier wikitext front end wrote it, so the stylesheet and
everything after it are unchanged. Only ``miqra:ketiv-only`` and ``miqra:qeri-only`` differ:
they hold the bare form, to which the stylesheet adds MAM's parentheses or brackets, where
the earlier front end added a pair of its own to MAM's. Notes are numbered by one counter
per run, in the order that front end numbered them: the notes inside a template's
parameters before the template's own.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Optional
from urllib.parse import quote

MIQRA_NS = "urn:x-opensiddur:miqra:intermediate"
MW_NS = "urn:x-opensiddur:mw:intermediate"

_ANY_HI_RE = re.compile(r"'''''(.*?)'''''|'''(.*?)'''|''(.*?)''")
_TAG_OPEN_RE = re.compile(r"<(miqra|mw):([a-zA-Z0-9-]+)([^>]*?)(/?)>")

#: In MAM's wikitext a double underscore stands for a space. Plus keeps it only in column C,
#: as the usual separator (mpplus.html, "C column"), so only column C's are read as spaces;
#: but see :meth:`PlusToIntermediate._inverted_nun`.
_SPACE_CODE = "__"
#: Wikitext the plus parse would have turned into templates or links, or text that would be
#: read as this module's own markup.
_UNEXPECTED_TEXT_RE = re.compile(r"\{\{|\}\}|\[\[|\]\]|<(?:miqra|mw):")
_NUMBER = re.compile(r"[1-9][0-9]*")

#: Where a scroll-difference note's marker stands: after its target, or before it.
STAR_AFTER = "אאא*"
STAR_BEFORE = "*אאא"

#: The argument of a parashah break that falls inside a verse.
MID_VERSE = "פסקא באמצע פסוק"

DOCUMENTATION_NOTE = "נוסח"
SCROLL_DIFFERENCE_NOTE = "מ:הערה-2"
VERSE_LABEL = "מ:פסוק"
ALIYAH = "מ:עלייה"
GOOD_ENDING = "מ:סיום בטוב"


class PlusFormatError(ValueError):
    """The plus data has a template, parameter or node shape this converter does not know."""


def link_target_to_uri(target: str) -> str:
    """Turn a URL or Hebrew Wikisource page title into a valid URI for tei:ref/@target."""
    t = (target or "").strip()
    if not t:
        return ""
    if re.match(r"^https?://", t, re.I):
        return t
    if t.startswith("//"):
        return "https:" + t
    page, sep, frag = t.partition("#")
    page = page.replace(" ", "_").strip()
    if page:
        uri = "https://he.wikisource.org/wiki/" + quote(page, safe="/:%")
    else:
        uri = "https://he.wikisource.org/wiki/"
    if sep:
        uri += "#" + quote(frag, safe=":/%.-_")
    return uri


def _xml_escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _wikitext_basic_markup_to_xml(text: str) -> str:
    s = text or ""
    out: list[str] = []
    pos = 0
    for m in _ANY_HI_RE.finditer(s):
        out.append(_xml_escape(s[pos : m.start()]))
        if m.group(1) is not None:
            rend, inner = "bold-italic", m.group(1)
        elif m.group(2) is not None:
            rend, inner = "bold", m.group(2)
        else:
            rend, inner = "italic", m.group(3) or ""
        out.append(f'<mw:hi rend="{rend}">{_xml_escape(inner)}</mw:hi>')
        pos = m.end()
    out.append(_xml_escape(s[pos:]))
    return "".join(out)


def _escape_outside_tags(fragment: str) -> str:
    """Escape text nodes while preserving nested miqra:/mw: XML elements."""

    out: list[str] = []
    pos = 0
    while pos < len(fragment):
        m = _TAG_OPEN_RE.search(fragment, pos)
        if not m:
            out.append(_wikitext_basic_markup_to_xml(fragment[pos:]))
            break
        out.append(_wikitext_basic_markup_to_xml(fragment[pos : m.start()]))
        ns, local, _attrs, self_close = m.group(1), m.group(2), m.group(3), m.group(4)
        if self_close == "/":
            out.append(m.group(0))
            pos = m.end()
            continue
        close = f"</{ns}:{local}>"
        depth = 1
        search = m.end()
        closed_at: Optional[int] = None
        while depth > 0 and search <= len(fragment):
            next_close = fragment.find(close, search)
            if next_close == -1:
                break
            inner_open = _TAG_OPEN_RE.search(fragment, search, next_close)
            if inner_open and inner_open.start() < next_close and inner_open.group(4) != "/":
                inner_local = inner_open.group(2)
                if inner_open.group(1) == ns and inner_local == local:
                    depth += 1
                search = inner_open.end()
            else:
                depth -= 1
                if depth == 0:
                    closed_at = next_close
                else:
                    search = next_close + len(close)
        if closed_at is None:
            out.append(_wikitext_basic_markup_to_xml(fragment[m.start() :]))
            break
        inner = fragment[m.end() : closed_at]
        out.append(m.group(0))
        out.append(_escape_outside_tags(inner))
        out.append(close)
        pos = closed_at + len(close)
    return "".join(out)


def _keys(*names: str) -> frozenset[str]:
    return frozenset(names)


#: Each template's parameters: (required, allowed). The roster and the schemas are MAM-basics'
#: CURRENT_PLUS_TMPL_NAMES and CURRENT_PLUS_PARAM_POLICY (py/mb_cmn/template_names.py).
TEMPLATE_SCHEMAS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    # Documentation and notes.
    DOCUMENTATION_NOTE: (_keys("1", "2"), _keys("1", "2")),
    SCROLL_DIFFERENCE_NOTE: (_keys("1", "2", "3"), _keys("1", "2", "3")),
    "ש": (_keys(), _keys()),
    "מודגש": (_keys("1"), _keys("1")),
    "מ:קישור בהערה": (_keys("1", "2"), _keys("1", "2")),
    "מ:קישור פנימי בהערה": (_keys("1", "2"), _keys("1", "2")),
    # Ketiv and qere.
    "כו״ק": (_keys("1", "2"), _keys("1", "2")),
    "קו״כ": (_keys("1", "2"), _keys("1", "2")),
    "מ:כו״ק מיוחד": (_keys("1", "2", "סוג"), _keys("1", "2", "סוג")),
    "מ:קו״כ-אם-2": (_keys("1", "2", "3"), _keys("1", "2", "3", "מקורות", "סוג")),
    "כתיב ולא קרי": (_keys("1", "2"), _keys("1", "2", "3")),
    "קרי ולא כתיב": (_keys("1", "2"), _keys("1", "2")),
    # Special letters.
    "מ:אות-ג": (_keys("1"), _keys("1")),
    "מ:אות-ק": (_keys("1"), _keys("1")),
    "מ:אות תלויה": (_keys("1"), _keys("1")),
    "מ:אות-מיוחדת-במילה": (_keys("1", "2", "3", "4", "5"), _keys("1", "2", "3", "4", "5")),
    "מ:נו״ן הפוכה": (_keys("1"), _keys("1")),
    # Choices.
    "מ:דחי": (_keys("1", "2"), _keys("1", "2")),
    "מ:צינור": (_keys("1", "2"), _keys("1", "2")),
    "מ:קמץ": (_keys("ד", "ס"), _keys("ד", "ס")),
    "מ:כפול": (_keys("כפול", "א", "ב"), _keys("כפול", "א", "ב")),
    "מ:סילוק לפני געיה": (_keys("1", "2"), _keys("1", "2")),
    # Punctuation.
    "מ:לגרמיה-2": (_keys(), _keys()),
    "מ:פסק": (_keys(), _keys()),
    "מ:מקף אפור": (_keys(), _keys()),
    # Whitespace: parashah breaks and poetic spacing.
    "פפ": (_keys(), _keys("1")),
    "פפפ": (_keys(), _keys("1")),
    "סס": (_keys(), _keys("1")),
    "ססס": (_keys(), _keys("1")),
    "מ:ששש": (_keys(), _keys()),
    "ר0": (_keys(), _keys()),
    "ר1": (_keys(), _keys()),
    "ר2": (_keys(), _keys()),
    "ר3": (_keys(), _keys()),
    "ר4": (_keys(), _keys()),
    # Book, section and chapter markers.
    "מ:ספר חדש": (_keys("1"), _keys("1")),
    "מ:רווח בתרי עשר בפסוק הראשון": (_keys("1"), _keys("1")),
    "מ:רווח לספר בתהלים בפסוק הראשון": (_keys("1"), _keys("1")),
    "מ:אין פרשה בתחילת פרק": (_keys(), _keys()),
    "מ:אין פרשה בתחילת פרק בספרי אמ״ת": (_keys(), _keys()),
    "מ:אין רווח של פרשה בתחילת פרשת השבוע": (_keys(), _keys()),
    # The verse label and the aliyah it may carry.
    VERSE_LABEL: (_keys("1", "2", "3"), _keys("1", "2", "3", "סדר", "עלייה")),
    ALIYAH: (
        _keys("א", "ב0"),
        _keys("א", "ב0", "ב1", "ב2", "ב3", "ג0", "ג1", "ג2", "ג3"),
    ),
    # The good ending, which plus keeps beside the chapters (good_ending_plus).
    GOOD_ENDING: (_keys("1"), _keys("1")),
}

#: The keys of a plus file, of its header and of each of its book39s: (required, allowed).
#: MAM-basics added the header's consumer_notice on 2026-09-16 (37cbca1), so a download of an
#: earlier commit, through ``download --commit``, has none.
PLUS_FILE_KEYS = (_keys("header", "book39s"), _keys("header", "book39s"))
HEADER_KEYS = (
    _keys("book24_name", "sub_book_names", "chapter_counts"),
    _keys("book24_name", "sub_book_names", "chapter_counts", "consumer_notice"),
)
BOOK39_KEYS = (
    _keys("book24_name", "sub_book_name", "good_ending_plus", "chapters"),
    _keys("book24_name", "sub_book_name", "good_ending_plus", "chapters"),
)

#: Templates that carry a note, which must not stand in a parameter that is not rendered.
_NOTE_TEMPLATES = frozenset({DOCUMENTATION_NOTE, SCROLL_DIFFERENCE_NOTE})
#: Templates with one place each: the verse label in column D, the aliyah in the label's עלייה
#: and the good ending in good_ending_plus.
_PLACED_TEMPLATES = frozenset({VERSE_LABEL, ALIYAH, GOOD_ENDING})

_PARASHAH_TYPES = {"פפ": "open", "פפפ": "open-line", "סס": "close", "ססס": "close-inline"}
_POETIC_LEVELS = {"ר0": "0", "ר1": "1", "ר2": "2", "ר3": "3", "ר4": "4"}
_LETTER_RENDS = {"מ:אות-ג": "large", "מ:אות-ק": "small", "מ:אות תלויה": "raised"}

#: Markers of a book's or a section's start, a chapter's lack of a parashah break, and the
#: weekly portion's: layout the stylesheet does not use.
_UNRENDERED_MARKERS = frozenset(
    {
        "מ:ספר חדש",
        "מ:רווח בתרי עשר בפסוק הראשון",
        "מ:רווח לספר בתהלים בפסוק הראשון",
        "מ:אין פרשה בתחילת פרק",
        "מ:אין פרשה בתחילת פרק בספרי אמ״ת",
        "מ:אין רווח של פרשה בתחילת פרשת השבוע",
    }
)

_Handler = Callable[[str, dict[str, Any], str], str]


def template_params(node: Any) -> tuple[str, dict[str, Any]]:
    """A plus template's name and parameters, after checking them against its schema."""
    if not isinstance(node, dict) or not isinstance(node.get("tmpl_name"), str):
        raise PlusFormatError(f"not a plus template: {node!r}")
    extra = set(node) - {"tmpl_name", "tmpl_params"}
    if extra:
        raise PlusFormatError(f"unexpected keys {sorted(extra)} in template {node!r}")
    name = node["tmpl_name"]
    schema = TEMPLATE_SCHEMAS.get(name)
    if schema is None:
        raise PlusFormatError(f"unknown template {name!r}")
    params = node.get("tmpl_params", {})
    if not isinstance(params, dict):
        raise PlusFormatError(f"{name}: parameters are not a mapping: {params!r}")
    required, allowed = schema
    if not required <= params.keys() <= allowed:
        raise PlusFormatError(
            f"{name}: parameters {sorted(params)}; required {sorted(required)}, "
            f"allowed {sorted(allowed)}"
        )
    return name, params


def _string(name: str, params: dict[str, Any], key: str) -> str:
    """A parameter that must be plain text: apparatus, metadata or a label."""
    value = params[key]
    if not isinstance(value, str):
        raise PlusFormatError(f"{name}: parameter {key} is not a string: {value!r}")
    return value


def check_aliyah(value: Any) -> dict[str, str]:
    """The parameters of the מ:עלייה that a verse label's עלייה holds, all plain text."""
    name, params = template_params(value)
    if name != ALIYAH:
        raise PlusFormatError(f"עלייה holds {name}, not {ALIYAH}")
    return {key: _string(name, params, key) for key in params}


def _check_keys(value: Any, schema: tuple[frozenset[str], frozenset[str]], what: str) -> None:
    if not isinstance(value, dict):
        raise PlusFormatError(f"{what} is not an object: {value!r}")
    required, allowed = schema
    if not required <= value.keys() <= allowed:
        raise PlusFormatError(
            f"{what}: keys {sorted(value)}; required {sorted(required)}, allowed {sorted(allowed)}"
        )


def check_plus_file(data: Any, where: str) -> None:
    """The keys of a plus file, of its header and of each of its book39s."""
    _check_keys(data, PLUS_FILE_KEYS, where)
    _check_keys(data["header"], HEADER_KEYS, f"{where}: header")
    if not isinstance(data["book39s"], list):
        raise PlusFormatError(f"{where}: book39s is not a list")
    for index, book39 in enumerate(data["book39s"]):
        _check_keys(book39, BOOK39_KEYS, f"{where}: book39 {index}")


class PlusToIntermediate:
    """Converts MAM-parsed plus verse columns into intermediate XML fragments.

    One instance numbers the notes of a run: the ids (``miqra-note-N``) count up across every
    column it converts, in the order it converts them.
    """

    def __init__(self) -> None:
        self._note_seq = 0
        handlers: dict[str, _Handler] = {
            DOCUMENTATION_NOTE: self._documentation_note,
            SCROLL_DIFFERENCE_NOTE: self._scroll_difference_note,
            "ש": self._doc_part_separator,
            "מודגש": self._bold,
            "מ:קישור בהערה": self._note_link,
            "מ:קישור פנימי בהערה": self._note_link,
            "כו״ק": self._ketiv_first,
            "מ:כו״ק מיוחד": self._ketiv_first,
            "קו״כ": self._qeri_first,
            "מ:קו״כ-אם-2": self._trivial_qere,
            "כתיב ולא קרי": self._ketiv_only,
            "קרי ולא כתיב": self._qeri_only,
            "מ:אות-מיוחדת-במילה": self._word_with_special_letter,
            "מ:נו״ן הפוכה": self._inverted_nun,
            "מ:דחי": self._without_stress_helper,
            "מ:צינור": self._without_stress_helper,
            "מ:קמץ": self._qamats,
            "מ:כפול": self._dual_cantillation,
            "מ:סילוק לפני געיה": self._silluq_before_meteg,
            "מ:לגרמיה-2": self._legarmeh,
            "מ:פסק": self._paseq,
            "מ:מקף אפור": self._grey_maqaf,
            "מ:ששש": self._shirah_break,
            VERSE_LABEL: self._verse_label,
            ALIYAH: self._out_of_place,
            GOOD_ENDING: self._out_of_place,
        }
        handlers.update({name: self._parashah for name in _PARASHAH_TYPES})
        handlers.update({name: self._poetic for name in _POETIC_LEVELS})
        handlers.update({name: self._special_letter for name in _LETTER_RENDS})
        handlers.update({name: self._unrendered_marker for name in _UNRENDERED_MARKERS})
        if handlers.keys() != TEMPLATE_SCHEMAS.keys():
            raise AssertionError("every template needs a schema and a handler")
        self._handlers = handlers

    def column(self, nodes: Any, column: str) -> str:
        """Column C, D or E of one verse as an escaped intermediate XML fragment."""
        if column not in ("C", "D", "E"):
            raise ValueError(f"no column {column!r}")
        if not isinstance(nodes, list):
            raise PlusFormatError(f"column {column} is not a list: {nodes!r}")
        return _escape_outside_tags(self._render(nodes, column))

    # --- the walk ---

    def _render(self, value: Any, column: str) -> str:
        """A column or a rendered parameter, as raw markup: text unescaped, tags literal."""
        if isinstance(value, str):
            return self._text(value, column)
        if isinstance(value, dict):
            name, params = template_params(value)
            return self._handlers[name](name, params, column)
        if isinstance(value, list):
            parts = []
            for item in value:
                if not isinstance(item, (str, dict)):
                    raise PlusFormatError(f"unexpected list item {item!r}")
                parts.append(self._render(item, column))
            return "".join(parts)
        raise PlusFormatError(f"unexpected node {value!r}")

    def _text(self, value: str, column: str) -> str:
        if _UNEXPECTED_TEXT_RE.search(value):
            raise PlusFormatError(f"unexpected markup in text: {value!r}")
        return value.replace(_SPACE_CODE, " ") if column == "C" else value

    def _unrendered(self, value: Any) -> None:
        """Check a parameter that is not rendered: an alternative reading or apparatus.

        Its templates must be known and well formed, and it may hold no note, which would
        vanish from the output, and no verse label, aliyah or good ending, which belong
        elsewhere.
        """
        if isinstance(value, str):
            if _UNEXPECTED_TEXT_RE.search(value):
                raise PlusFormatError(f"unexpected markup in text: {value!r}")
            return
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, (str, dict)):
                    raise PlusFormatError(f"unexpected list item {item!r}")
                self._unrendered(item)
            return
        name, params = template_params(value)
        if name in _NOTE_TEMPLATES or name in _PLACED_TEMPLATES:
            raise PlusFormatError(f"{name} in a parameter that is not rendered")
        for item in params.values():
            self._unrendered(item)

    def check_good_ending(self, value: Any, where: str) -> None:
        """Check a book39's good_ending_plus, which is not rendered.

        It is null, or the chapter and verse it follows (``last_chapnver``) and the good ending
        itself (``wikitext_element``): a נוסח whose 1 is מ:סיום בטוב and whose 2 is its note.
        """
        if value is None:
            return
        if not isinstance(value, dict) or value.keys() != {"last_chapnver", "wikitext_element"}:
            raise PlusFormatError(f"{where}: unexpected good_ending_plus {value!r}")
        chapnver = value["last_chapnver"]
        if not (
            isinstance(chapnver, list)
            and len(chapnver) == 2
            and all(isinstance(n, str) and _NUMBER.fullmatch(n) for n in chapnver)
        ):
            raise PlusFormatError(f"{where}: unexpected good ending last_chapnver {chapnver!r}")
        name, params = template_params(value["wikitext_element"])
        if name != DOCUMENTATION_NOTE:
            raise PlusFormatError(f"{where}: the good ending is {name}, not {DOCUMENTATION_NOTE}")
        ending_name, ending_params = template_params(params["1"])
        if ending_name != GOOD_ENDING:
            raise PlusFormatError(
                f"{where}: the good ending's {DOCUMENTATION_NOTE} documents {ending_name}"
            )
        self._unrendered(ending_params["1"])
        self._unrendered(params["2"])

    def _next_note_id(self) -> str:
        self._note_seq += 1
        return f"miqra-note-{self._note_seq}"

    # --- documentation and notes ---

    def _documentation_note(self, name: str, params: dict[str, Any], column: str) -> str:
        """נוסח: 1 is the target, the text documented, rendered in place; 2 is the note."""
        target = params["1"]
        if isinstance(target, dict) and target.get("tmpl_name") == SCROLL_DIFFERENCE_NOTE:
            return self._documented_scroll_difference(target, params["2"], column)
        display = self._render(target, column)
        return self._documented(display, self._render(params["2"], column))

    def _documented(self, display: str, note: str) -> str:
        if not note:
            return display
        note_id = self._next_note_id()
        return (
            f'<miqra:variant noteId="{note_id}">'
            f"<miqra:display>{display}</miqra:display>"
            f"</miqra:variant>"
            f'<miqra:note xml:id="{note_id}">{note}</miqra:note>'
        )

    def _documented_scroll_difference(self, scroll: Any, note: Any, column: str) -> str:
        """A documentation note whose whole target carries a scroll-difference note.

        MAM's wikitext writes the two side by side, ``{{נוסח|target|…}}{{מ:הערה|…}}``, and
        plus moves the scroll-difference note into the documentation note's target. Both
        notes keep the wikitext's order and marker positions: the scroll-difference note's
        marker stands before or after the whole documented span, not inside it.
        """
        name, params = template_params(scroll)
        star = _string(name, params, "3")
        if star == STAR_AFTER:
            display = self._render(params["1"], column)
            documented = self._documented(display, self._render(note, column))
            return documented + self._scroll_note(params["2"], column)
        if star == STAR_BEFORE:
            marker = self._scroll_note(params["2"], column)
            display = self._render(params["1"], column)
            return marker + self._documented(display, self._render(note, column))
        raise PlusFormatError(f"{name}: unknown marker position {star!r}")

    def _scroll_difference_note(self, name: str, params: dict[str, Any], column: str) -> str:
        """מ:הערה-2: 1 is the target, rendered in place; 2 is the note; 3 says whether the
        note's marker stands after the target or before it."""
        star = _string(name, params, "3")
        if star == STAR_AFTER:
            target = self._render(params["1"], column)
            return target + self._scroll_note(params["2"], column)
        if star == STAR_BEFORE:
            marker = self._scroll_note(params["2"], column)
            return marker + self._render(params["1"], column)
        raise PlusFormatError(f"{name}: unknown marker position {star!r}")

    def _scroll_note(self, note: Any, column: str) -> str:
        body = self._render(note, column)
        note_id = self._next_note_id()
        return (
            f'<miqra:anchor xml:id="{note_id}-ref"/>'
            f'<miqra:note xml:id="{note_id}">{body}</miqra:note>'
        )

    def _doc_part_separator(self, name: str, params: dict[str, Any], column: str) -> str:
        """ש: separates the parts of a note."""
        return "<miqra:fn-mark/>"

    def _bold(self, name: str, params: dict[str, Any], column: str) -> str:
        """מודגש: 1 is bold text in a note."""
        return f'<mw:hi rend="bold">{self._render(params["1"], column)}</mw:hi>'

    def _note_link(self, name: str, params: dict[str, Any], column: str) -> str:
        """מ:קישור בהערה, מ:קישור פנימי בהערה: 1 is the link's target (a URL, or a Wikisource
        page), 2 its text."""
        raw_target = _string(name, params, "1")
        label = self._render(params["2"], column) or raw_target
        target = _xml_escape(link_target_to_uri(raw_target))
        return f'<mw:link target="{target}">{label}</mw:link>'

    # --- ketiv and qere ---

    def _ketiv_first(self, name: str, params: dict[str, Any], column: str) -> str:
        """כו״ק and מ:כו״ק מיוחד: 1 is the ketiv, 2 the qere. מ:כו״ק מיוחד's סוג, which
        classifies the pair, is not rendered."""
        ketiv = self._render(params["1"], column)
        qeri = self._render(params["2"], column)
        if "סוג" in params:
            _string(name, params, "סוג")
        return (
            f'<miqra:kq order="ketiv-first">'
            f"<miqra:ketiv>{ketiv}</miqra:ketiv>"
            f"<miqra:qeri>{qeri}</miqra:qeri>"
            f"</miqra:kq>"
        )

    def _qeri_first(self, name: str, params: dict[str, Any], column: str) -> str:
        """קו״כ: 1 is the ketiv, 2 the qere, read first."""
        ketiv = self._render(params["1"], column)
        qeri = self._render(params["2"], column)
        return (
            f'<miqra:kq order="qeri-first">'
            f"<miqra:ketiv>{ketiv}</miqra:ketiv>"
            f"<miqra:qeri>{qeri}</miqra:qeri>"
            f"</miqra:kq>"
        )

    def _trivial_qere(self, name: str, params: dict[str, Any], column: str) -> str:
        """מ:קו״כ-אם-2: 1 is the pointed ketiv, rendered; 2, the unpointed ketiv, and 3, the
        pointed qere, are alternative forms, checked and not rendered; מקורות and סוג are not
        rendered."""
        display = self._render(params["1"], column)
        self._unrendered(params["2"])
        self._unrendered(params["3"])
        for key in ("מקורות", "סוג"):
            if key in params:
                _string(name, params, key)
        return display

    def _ketiv_only(self, name: str, params: dict[str, Any], column: str) -> str:
        """כתיב ולא קרי: 1 is the ketiv as MAM shows it: 2, the bare ketiv, in parentheses,
        followed by 3, a maqaf, when there is one. The element holds 2 and 3 follows it, so
        that the stylesheet, which adds the parentheses, gives 1 exactly; 1 is checked to be
        that."""
        shown = _string(name, params, "1")
        ketiv = _string(name, params, "2")
        after = _string(name, params, "3") if "3" in params else ""
        expected = f"({ketiv}){after}"
        if shown != expected:
            raise PlusFormatError(f"{name}: parameter 1 is {shown!r}, not {expected!r}")
        return (
            f"<miqra:ketiv-only>{self._text(ketiv, column)}</miqra:ketiv-only>"
            f"{self._text(after, column)}"
        )

    def _qeri_only(self, name: str, params: dict[str, Any], column: str) -> str:
        """קרי ולא כתיב: 1 is the qere as MAM shows it: 2, the bare qere, in brackets. The
        element holds 2, so that the stylesheet, which adds the brackets, gives 1 exactly; 1
        is checked to be that."""
        shown = _string(name, params, "1")
        qeri = _string(name, params, "2")
        expected = f"[{qeri}]"
        if shown != expected:
            raise PlusFormatError(f"{name}: parameter 1 is {shown!r}, not {expected!r}")
        return f"<miqra:qeri-only>{self._text(qeri, column)}</miqra:qeri-only>"

    # --- special letters ---

    def _special_letter(self, name: str, params: dict[str, Any], column: str) -> str:
        """מ:אות-ג, מ:אות-ק, מ:אות תלויה: 1 is a large, small or hung letter with its marks."""
        letter = self._render(params["1"], column)
        return f'<miqra:hi rend="{_LETTER_RENDS[name]}">{letter}</miqra:hi>'

    def _word_with_special_letter(self, name: str, params: dict[str, Any], column: str) -> str:
        """מ:אות-מיוחדת-במילה: 1 is the word spelled around its special letters, rendered;
        2 to 5 (the plain word, a dot mask, the type and a summary) restate it and are not."""
        word = self._render(params["1"], column)
        for key in ("2", "3", "4", "5"):
            _string(name, params, key)
        return word

    def _inverted_nun(self, name: str, params: dict[str, Any], column: str) -> str:
        """מ:נו״ן הפוכה: 1 is the inverted nun, with the space after it where MAM has one.

        In whatever column, a ``__`` in it is read as that space: MAM-basics wrote the space
        after Psalm 107's inverted nuns as ``__`` until its commit de85675 (2026-10-15), so a
        download of an earlier commit, through ``download --commit``, still has it.
        """
        nun = self._render(params["1"], column).replace(_SPACE_CODE, " ")
        return f"<miqra:inverted-nun>{nun}</miqra:inverted-nun>"

    # --- choices ---

    def _without_stress_helper(self, name: str, params: dict[str, Any], column: str) -> str:
        """מ:דחי, מ:צינור: 1 is the word without the stress helper, rendered; 2 with it."""
        word = self._render(params["1"], column)
        self._unrendered(params["2"])
        return word

    def _qamats(self, name: str, params: dict[str, Any], column: str) -> str:
        """מ:קמץ: ד is the grammatical form, rendered; ס the Sephardic tradition's."""
        word = self._render(params["ד"], column)
        self._unrendered(params["ס"])
        return word

    def _dual_cantillation(self, name: str, params: dict[str, Any], column: str) -> str:
        """מ:כפול: כפול is the dually accented text, whose notes are kept; א and ב are its two
        singly accented strands (ta'am tachton and ta'am elyon in the Decalogues).

        They are rendered in that order, not in the JSON's key order, so that their notes are
        numbered the same whatever the order of the keys."""
        merged = self._render(params["כפול"], column)
        first = self._render(params["א"], column)
        second = self._render(params["ב"], column)
        return (
            "<miqra:dual-accent>"
            f"<miqra:merged>{merged}</miqra:merged>"
            f'<miqra:strand role="א">{first}</miqra:strand>'
            f'<miqra:strand role="ב">{second}</miqra:strand>'
            "</miqra:dual-accent>"
        )

    def _silluq_before_meteg(self, name: str, params: dict[str, Any], column: str) -> str:
        """מ:סילוק לפני געיה: 1 is the word, rendered; 2 locates its silluq."""
        word = self._render(params["1"], column)
        _string(name, params, "2")
        return word

    # --- punctuation ---

    def _legarmeh(self, name: str, params: dict[str, Any], column: str) -> str:
        return '<miqra:punct type="legarmeh">׀</miqra:punct>'

    def _paseq(self, name: str, params: dict[str, Any], column: str) -> str:
        return '<miqra:punct type="paseq">׀</miqra:punct>'

    def _grey_maqaf(self, name: str, params: dict[str, Any], column: str) -> str:
        return '<miqra:maqaf rend="grey">־</miqra:maqaf>'

    # --- whitespace ---

    def _parashah(self, name: str, params: dict[str, Any], column: str) -> str:
        """פפ, פפפ, סס, ססס: a parashah break; 1, when present, says it falls mid-verse."""
        mid_verse = ""
        if "1" in params and MID_VERSE in _string(name, params, "1"):
            mid_verse = ' midVerse="true"'
        return f'<miqra:parashah type="{_PARASHAH_TYPES[name]}"{mid_verse}/>'

    def _shirah_break(self, name: str, params: dict[str, Any], column: str) -> str:
        return '<miqra:parashah type="shirah"/>'

    def _poetic(self, name: str, params: dict[str, Any], column: str) -> str:
        return f'<miqra:poetic level="{_POETIC_LEVELS[name]}"/>'

    def _unrendered_marker(self, name: str, params: dict[str, Any], column: str) -> str:
        if "1" in params:
            _string(name, params, "1")
        return ""

    # --- the verse label ---

    def _verse_label(self, name: str, params: dict[str, Any], column: str) -> str:
        """מ:פסוק: 1 to 3 are the book, chapter and verse; סדר the seder; עלייה the aliyah.

        It belongs in column D only. None of it is rendered: chapter and verse come from the
        JSON keys, and the humash reads the aliyot itself (``humash.aliyot``)."""
        if column != "D":
            raise PlusFormatError(f"{name} in column {column}")
        for key in ("1", "2", "3", "סדר"):
            if key in params:
                _string(name, params, key)
        if "עלייה" in params:
            check_aliyah(params["עלייה"])
        return ""

    def _out_of_place(self, name: str, params: dict[str, Any], column: str) -> str:
        """מ:עלייה belongs only in a verse label, מ:סיום בטוב only in good_ending_plus."""
        raise PlusFormatError(f"{name} in column {column}")
