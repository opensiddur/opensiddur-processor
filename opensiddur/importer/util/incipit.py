"""An index of the opening words of every text in the collection's Hebrew projects.

An importer whose source sets texts already in the collection -- a psalm, the Birkat
Hamazon, a prayer encoded from Birnbaum -- looks their openings up here to find the URNs it
must reuse. Words are compared as consonant skeletons (:func:`words`): the divine name made
one spelling, and internal ו and י dropped, so that full and defective spellings agree.

Shared by the opensiddur.org importer (``opensiddur_org.match``) and the Sefaria importer
(``sefaria.match``).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Collection
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from opensiddur.common.constants import PROJECT_DIRECTORY
from opensiddur.importer.util.hebrew import normalize_hebrew

TEXT_PREFIX = "urn:x-opensiddur:text:"

TEI = "http://www.tei-c.org/ns/1.0"
INCIPIT_WORDS = 6
#: Words collected after each scope opens: an incipit, and as much again after a blessing
#: formula.
COLLECTED_WORDS = 16
#: Words kept from the end of each scope.
CLOSING_WORDS = 10
#: After a blessing formula, the words that tell the blessings apart, and the shorter key
#: tried when there are fewer (``להדליק נר`` opens three blessings; ``של חנוכה`` decides).
AFTER_FORMULA_WORDS = (10, INCIPIT_WORDS)
MIN_AFTER_FORMULA_WORDS = 3
#: A shorter opening is used only when it is unique: four words are often a formula
#: ("ברוך אתה ה׳ אלהינו") that opens dozens of blessings.
SHORT_INCIPIT_WORDS = 4
#: Only texts are candidates: a ``siddur:`` URN is a position in a book, not a text.
INDEXED_NAMESPACES = ("prayer:", "poem:", "bible:")
HEBREW_LANGUAGES = ("he", "arc", "jpa", "tmr")


#: Spellings of the Tetragrammaton, as consonant skeletons: written out, abbreviated, or
#: substituted. They are made one word so that a blessing's opening formula is recognised as
#: the formula whichever spelling a source uses, rather than as a unique opening.
DIVINE_NAME_SPELLINGS = frozenset({"יהוה", "יי", "ייי", "ה", "יקוק", "ידוד", "השם"})


#: The spellings that are the divine name also behind a prefix letter: ``לַייָ`` and
#: ``לַיהוָה`` are one word. Not ``ה`` or ``השם``, which with a prefix are other words (לה, בהשם).
_PREFIXED_DIVINE_NAME = re.compile(r"(ו?ש?[בכלמ]?)(יהוה|ייי|יי|יקוק|ידוד)")


#: Elements a word never runs across: the start of a scope, a transclusion or a condition.
#: Words of their own: each alternative of a kri and ketiv, a marked word.
WORD_ELEMENTS = frozenset({"choice", "written", "read", "w"})
BOUNDARY_ELEMENTS = frozenset({"milestone", "transclude", "conditional", "endConditional"}) | WORD_ELEMENTS
#: Elements whose end ends a word.
BLOCK_ELEMENTS = frozenset({"p", "div", "head", "l", "lg", "ab", "item", "list", "seg", "table", "row",
                            "cell"}) | WORD_ELEMENTS


def _key_word(skeleton: str) -> str:
    """A word as compared: the divine name made one spelling, with any prefix letters kept
    before it, and every ו and י after the first letter dropped, so that full and defective
    spellings (כרות, כרת) agree."""
    if skeleton in DIVINE_NAME_SPELLINGS:
        return "יהוה"
    prefixed = _PREFIXED_DIVINE_NAME.fullmatch(skeleton)
    if prefixed and prefixed.group(1):
        return prefixed.group(1) + "יהוה"
    return skeleton[:1] + skeleton[1:].replace("ו", "").replace("י", "")


#: Words some sources print as two and others as one: (first, second) -> the one word.
_JOINED_WORDS = {("הלל", "יה"): "הללה"}


def _words(text: str) -> list[str]:
    """A text as compared: word by word, a maqaf or a paseq separating words as a space does
    (``אֶת־צֶמַח`` is ``אֶת צֶמַח``), each word a key word, and a word some sources split in
    two (``הַֽלְלוּ יָהּ``, ``הַלְלוּיָהּ``) made one."""
    text = text.replace("\u05be", " ").replace("\u05c0", " ")  # a maqaf or a paseq between words
    found = [_key_word(w) for w in (normalize_hebrew(word) for word in text.split()) if w]
    joined: list[str] = []
    for word in found:
        if joined and (joined[-1], word) in _JOINED_WORDS:
            joined[-1] = _JOINED_WORDS[(joined[-1], word)]
        else:
            joined.append(word)
    return joined


#: The opening every blessing shares. A blessing is told apart by what follows it.
BLESSING_FORMULA = tuple(_words("ברוך אתה יהוה אלהינו מלך העולם"))
_AFTER_FORMULA = "§"


def _keys(words: list[str]) -> list[tuple[str, ...]]:
    """The keys an opening is indexed and looked up by, most specific first: the words after a
    blessing formula, then the incipit."""
    keys: list[tuple[str, ...]] = []
    n = len(BLESSING_FORMULA)
    if tuple(words[:n]) == BLESSING_FORMULA:
        rest = words[n:]
        lengths = [length for length in AFTER_FORMULA_WORDS if len(rest) >= length]
        if not lengths and len(rest) >= MIN_AFTER_FORMULA_WORDS:
            lengths = [len(rest)]  # a short blessing: all of it (שהחינו וקימנו והגיענו לזמן הזה)
        keys.extend((_AFTER_FORMULA, *rest[:length]) for length in lengths)
    keys.append(tuple(words[:INCIPIT_WORDS]))
    return keys


@dataclass
class IncipitIndex:
    """Opening words of every ``@corresp`` scope in the collection's Hebrew projects."""

    by_incipit: dict[tuple[str, ...], set[str]] = field(default_factory=dict)
    incipit_of: dict[str, tuple[str, ...]] = field(default_factory=dict)
    children: dict[str, list[str]] = field(default_factory=dict)
    #: A text that opens by transcluding another, before any words of its own: text -> the
    #: transcluded one (Birnbaum's ``amidah/gevurot`` opens with ``.../attah_gibbor``). Its
    #: collected opening is then the words after the transclusion, not the text's opening.
    opens_with: dict[str, str] = field(default_factory=dict)
    #: Texts that transclude parts of themselves: the collection does not hold them whole in
    #: their collected opening, however short it is.
    compound: set[str] = field(default_factory=set)
    #: How many words of its collected opening are a short text's own: where its scope ends
    #: before :data:`COLLECTED_WORDS`. A text not listed runs on at least that far.
    length_of: dict[str, int] = field(default_factory=dict)

    #: The last words of every scope (up to :data:`CLOSING_WORDS`): a blessing is known by its
    #: closing formula (``ברוך אתה ה׳ חונן הדעת``) whatever words another rite opens it with.
    closing_of: dict[str, tuple[str, ...]] = field(default_factory=dict)

    #: A text that ends by transcluding another, with no words of its own after it.
    ends_with: dict[str, str] = field(default_factory=dict)
    #: The texts each text transcludes.
    includes: dict[str, set[str]] = field(default_factory=dict)
    #: Texts whose scope is a milestone inside another text's words (a verse Ashrei quotes),
    #: rather than a division of their own.
    milestone_scoped: set[str] = field(default_factory=set)

    def included(self, urn: str) -> set[str]:
        """Every text ``urn`` transcludes, and every text those transclude."""
        found: set[str] = set()
        todo = [urn]
        while todo:
            for target in self.includes.get(todo.pop(), ()):
                if target not in found:
                    found.add(target)
                    todo.append(target)
        return found

    def closing(self, urn: str) -> tuple[str, ...]:
        """The last words of ``urn``: its own, or those of the text it ends by transcluding."""
        seen = {urn}
        while urn in self.ends_with and self.ends_with[urn] not in seen:
            urn = self.ends_with[urn]
            seen.add(urn)
        return self.closing_of.get(urn, ())

    def own_opening(self, urn: str) -> tuple[str, ...]:
        """The collected opening, without the words past the text's end."""
        opening = self.incipit_of.get(urn, ())
        length = self.length_of.get(urn)
        return opening if length is None else opening[:length]

    def add(self, urn: str, words: list[str]) -> None:
        if len(words) < SHORT_INCIPIT_WORDS or urn in self.incipit_of:
            return
        if not urn[len(TEXT_PREFIX):].startswith(INDEXED_NAMESPACES):
            return
        self.incipit_of[urn] = tuple(words[:COLLECTED_WORDS])
        for key in _keys(words):
            self.by_incipit.setdefault(key, set()).add(urn)
        key = tuple(words[:INCIPIT_WORDS])
        if len(key) > SHORT_INCIPIT_WORDS:
            self.by_incipit.setdefault(key[:SHORT_INCIPIT_WORDS], set()).add(urn)
        self.children.setdefault(parent(urn), []).append(urn)

    def lookup(self, words: list[str]) -> set[str]:
        for key in _keys(words):
            if len(key) >= SHORT_INCIPIT_WORDS:
                found = self.by_incipit.get(key, set())
                if found:
                    return self._longest_opening(found, words)
        if len(words) >= SHORT_INCIPIT_WORDS:
            found = self.by_incipit.get(tuple(words[:SHORT_INCIPIT_WORDS]), set())
            if len(found) == 1:
                return found
        return set()

    def _longest_opening(self, found: set[str], words: list[str]) -> set[str]:
        """Of several candidates, the one whose opening goes on agreeing with ``words``
        longest, when one does. A text and its first part open alike; the part is kept,
        because what is matched is a row, a part of a post."""
        found = {urn for urn in found if not any(other.startswith(urn + "/") for other in found)}
        if len(found) < 2:
            return found

        def agreement(urn: str) -> int:
            count = 0
            for a, b in zip(self.incipit_of[urn], words):
                if a != b:
                    break
                count += 1
            return count

        ranked = sorted(found, key=agreement, reverse=True)
        if agreement(ranked[0]) > agreement(ranked[1]):
            return {ranked[0]}
        return found

    def open_with_parts(self) -> None:
        """Index each text that opens by transcluding a part under that part's opening, not
        under the words of its own that follow the transclusion (Birnbaum's Mourner's Kaddish is
        not "יהא שלמא רבא")."""
        if not self.opens_with:
            return
        collected = dict(self.incipit_of)
        for urn in self.opens_with:
            first = self.first_part(urn)
            if urn in collected:
                if first in collected:
                    collected[urn] = collected[first]
                else:
                    del collected[urn]
        order = list(self.incipit_of)
        self.by_incipit, self.incipit_of, self.children = {}, {}, {}
        for urn in order:
            if urn in collected:
                self.add(urn, list(collected[urn]))
        self.length_of = {u: n for u, n in self.length_of.items() if u not in self.opens_with}

    def first_part(self, urn: str) -> str:
        """The text ``urn``'s words begin with: itself, or what it opens by transcluding."""
        seen = {urn}
        while urn in self.opens_with and self.opens_with[urn] not in seen:
            urn = self.opens_with[urn]
            seen.add(urn)
        return urn

    def to_json(self) -> dict:
        # In the order the parts were found, which is the order of the texts.
        return {"incipits": {urn: list(words) for urn, words in self.incipit_of.items()},
                "opens_with": dict(sorted(self.opens_with.items())),
                "compound": sorted(self.compound),
                "length_of": dict(sorted(self.length_of.items())),
                "closing_of": {urn: list(words) for urn, words in sorted(self.closing_of.items())},
                "ends_with": dict(sorted(self.ends_with.items())),
                "includes": {urn: sorted(targets) for urn, targets in sorted(self.includes.items())},
                "milestone_scoped": sorted(self.milestone_scoped)}

    @classmethod
    def from_json(cls, data: dict) -> "IncipitIndex":
        index = cls()
        incipits = data.get("incipits", {}) if "incipits" in data else data
        for urn, words in incipits.items():
            index.add(urn, words)
        index.opens_with = dict(data.get("opens_with", {})) if "incipits" in data else {}
        index.compound = set(data.get("compound", ())) if "incipits" in data else set()
        index.length_of = dict(data.get("length_of", {})) if "incipits" in data else {}
        index.closing_of = ({urn: tuple(words) for urn, words in data.get("closing_of", {}).items()}
                            if "incipits" in data else {})
        index.ends_with = dict(data.get("ends_with", {})) if "incipits" in data else {}
        index.includes = ({urn: set(targets) for urn, targets in data.get("includes", {}).items()}
                          if "incipits" in data else {})
        index.milestone_scoped = set(data.get("milestone_scoped", ())) if "incipits" in data else set()
        index.open_with_parts()
        return index


def index_document(index: IncipitIndex, root: etree._Element) -> None:
    """Add the opening words of each ``@corresp`` scope in one document.

    A scope's opening is collected past its end, up to :data:`COLLECTED_WORDS`, so that a
    short part is still found by the words around it; how many of them are its own -- where
    the scope ends first: its element's end, or the next milestone of its unit -- is recorded
    in :attr:`IncipitIndex.length_of`.
    """
    # Each scope being collected: its URN, the words so far, how many of them are its own
    # (None while it is open), and what ends it: an element, or a milestone unit.
    pending: list[list] = []

    def finish(entry: list) -> None:
        urn, collected, own = entry[0], entry[1], entry[2]
        index.add(urn, collected)
        if own is not None and urn not in index.length_of:
            index.length_of[urn] = own

    # Each scope still open: its URN, its last words, what ends it, and the text it has just
    # transcluded (None once words of its own follow).
    open_scopes: list[list] = []

    def end_scopes(test) -> None:
        still = []
        for scope in open_scopes:
            if test(scope[2]):
                if scope[1] and scope[0] not in index.closing_of:
                    index.closing_of[scope[0]] = tuple(scope[1])
                if scope[3] and scope[0] not in index.ends_with:
                    index.ends_with[scope[0]] = scope[3]
            else:
                still.append(scope)
        open_scopes[:] = still

    # A word may run across elements (``לַ<j:divineName>יהוה</j:divineName>``): text that does
    # not end in a space is held until the next text, or a boundary, completes its last word.
    carry = [""]

    def feed(text: str | None) -> None:
        if not text:
            return
        text = carry[0] + text
        carry[0] = ""
        if not text[-1].isspace():
            head, _, last = text.rpartition(" ")
            if not any(c.isspace() for c in text):
                head, last = "", text
            carry[0] = last
            text = head
        _feed_words(text)

    def end_word() -> None:
        text, carry[0] = carry[0], ""
        _feed_words(text)

    def _feed_words(text: str) -> None:
        if not text or not (pending or open_scopes):
            return
        words = _words(text)
        if not words:
            return
        for scope in open_scopes:
            scope[1].extend(words)
            del scope[1][:-CLOSING_WORDS]
            scope[3] = None  # words of its own after a transclusion
        still: list[list] = []
        for entry in pending:
            entry[1].extend(words)
            if len(entry[1]) >= COLLECTED_WORDS:
                finish(entry)  # still open when its opening is full: a long text, no length
            else:
                still.append(entry)
        pending[:] = still

    def close(test) -> None:
        for entry in pending:
            if entry[2] is None and test(entry[3]):
                entry[2] = len(entry[1])
        end_scopes(test)

    def flush() -> None:
        # A scope shorter than a full incipit still has an opening.
        close(lambda _end: True)
        for entry in pending:
            finish(entry)
        pending.clear()

    enclosing: list[str] = []  # the URNs of the elements around the one being walked
    conditions: set[str] = set()  # the j:conditional scopes open here, by xml:id

    def transclusion(target: str) -> None:
        target = target.split("@", 1)[0]
        if not target.startswith(TEXT_PREFIX):
            return
        if not conditions:
            # A text said only on some occasions (Modim de-Rabbanan, in the repetition) is not
            # where the text around it opens or ends.
            for entry in pending:
                if not entry[1] and entry[0] != target:
                    index.opens_with.setdefault(entry[0], target)
            for scope in open_scopes:
                if scope[0] != target:
                    scope[3] = target
        index.compound.update(enclosing)
        for urn in enclosing:
            if urn != target:
                index.includes.setdefault(urn, set()).add(target)

    def walk(element: etree._Element) -> None:
        if not isinstance(element.tag, str):
            feed(element.tail)
            return
        local = etree.QName(element).localname
        if local in ("teiHeader", "standOff", "note"):
            end_word()
            feed(element.tail)
            return
        if (local in BOUNDARY_ELEMENTS or element.get("corresp", "").startswith(TEXT_PREFIX)
                or (len(element) == 0 and not element.text)):
            # An empty element (a note's anchor, a page break) stands between words, though
            # some sources set it with no space; only an element with words in it
            # (j:divineName) can be inside one.
            end_word()
        if local == "transclude":
            transclusion(element.get("target", ""))
            feed(element.tail)
            return
        if local == "conditional":
            xml_id = element.get("{http://www.w3.org/XML/1998/namespace}id")
            if xml_id:
                conditions.add(xml_id)
            feed(element.tail)
            return
        if local == "endConditional":
            conditions.discard(element.get("target", "").lstrip("#"))
            feed(element.tail)
            return
        corresp = element.get("corresp", "")
        if local == "milestone":
            unit = element.get("unit", "")
            close(lambda end: end[:2] == ("unit", unit))
            if corresp.startswith(TEXT_PREFIX):
                index.milestone_scoped.add(corresp.split("@", 1)[0])
                holder = next((a for a in element.iterancestors() if isinstance(a.tag, str)
                               and etree.QName(a).localname == "div"), None)
                ends = ("unit", unit, id(holder))
                pending.append([corresp.split("@", 1)[0], [], None, ends])
                open_scopes.append([corresp.split("@", 1)[0], [], ends, None])
            feed(element.tail)
            return
        scoped = corresp.startswith(TEXT_PREFIX)
        if scoped:
            pending.append([corresp.split("@", 1)[0], [], None, ("element", id(element))])
            open_scopes.append([corresp.split("@", 1)[0], [], ("element", id(element)), None])
            enclosing.append(corresp.split("@", 1)[0])
        feed(element.text)
        for child in element:
            walk(child)
        if scoped:
            enclosing.pop()
        if scoped or local in BLOCK_ELEMENTS:
            end_word()
        # A milestone's scope ends with the element it was set in, if no milestone of its unit
        # ends it first: a last verse does not run on into the next text.
        close(lambda end: end == ("element", id(element)) or (end[0] == "unit" and end[2] == id(element)))
        feed(element.tail)

    walk(root)
    end_word()
    flush()


def parent(urn: str) -> str:
    """The URN one level up, or "" for a top-level text."""
    return urn.rsplit("/", 1)[0] if "/" in urn.split(":", 3)[-1] else ""


def project_language(project: Path) -> str:
    """The ``xml:lang`` of a project's ``index.xml``, or "" when it has none."""
    index_file = project / "index.xml"
    if not index_file.exists():
        return ""
    return etree.parse(str(index_file)).getroot().get("{http://www.w3.org/XML/1998/namespace}lang", "")


def build_incipit_index(project_directory: Path = PROJECT_DIRECTORY,
                        exclude: Collection[Path] = ()) -> IncipitIndex:
    """The index of every Hebrew project in ``project_directory`` but those in ``exclude``
    (an importer leaves out its own projects, which are not evidence of themselves)."""
    index = IncipitIndex()
    excluded = {Path(p) for p in exclude}
    for project in sorted(p for p in project_directory.iterdir() if p.is_dir()):
        if project in excluded:
            continue
        if project_language(project).split("-")[0] not in HEBREW_LANGUAGES:
            continue
        for xml_file in sorted(project.glob("*.xml")):
            index_document(index, etree.parse(str(xml_file)).getroot())
    index.open_with_parts()
    return index


#: Bumped whenever the words the index stores are normalized differently.
#: 2: parts are kept in document order, which the spans of departing rows need.
#: 3: a maqaf separates words.
#: 4: הללו יה is one word; transcluded openings, compound texts and short texts' lengths are
#:    recorded.
#: 5: closings and transclusions; a conditional transclusion neither opens nor ends a text.
#: 6: milestone-scoped texts.
#: 7: a milestone's scope ends with the division it was set in.
#: 8: a word split across elements is one word; a prefixed divine name keeps its prefix; a
#:    paseq separates words.
INDEX_VERSION = 8


def index_signature(project_directory: Path, exclude: Collection[Path] = ()) -> str:
    """What the index was built from: the version, the directory, and every file's size and
    time, so that an added, changed or deleted file, or another directory, rebuilds it."""
    excluded = {Path(p) for p in exclude}
    files = sorted(
        f"{f.relative_to(project_directory)}:{f.stat().st_size}:{f.stat().st_mtime_ns}"
        for f in project_directory.glob("*/*.xml")
        if f.parent not in excluded
    )
    payload = json.dumps([INDEX_VERSION, str(project_directory.resolve()), files])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_incipit_index(cache: Path, project_directory: Path = PROJECT_DIRECTORY,
                       exclude: Collection[Path] = ()) -> IncipitIndex:
    """The index, from ``cache`` when it was built from the projects as they are now."""
    signature = index_signature(project_directory, exclude)
    if cache.exists():
        try:
            cached = json.loads(cache.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cached = {}
        if isinstance(cached, dict) and cached.get("signature") == signature:
            return IncipitIndex.from_json(cached["index"])
    index = build_incipit_index(project_directory, exclude)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"signature": signature, "index": index.to_json()}, ensure_ascii=False),
                     encoding="utf-8")
    return index


def projects_with_source(project_directory: Path, idno_types: Collection[str]) -> set[Path]:
    """The projects whose own source bibl (``project_source_bibl``) carries an ``idno`` of one
    of ``idno_types``: what an importer made, and so leaves out of the index it matches its
    source against."""
    found: set[Path] = set()
    wanted = set(idno_types)
    for index_file in sorted(Path(project_directory).glob("*/index.xml")):
        try:
            root = etree.parse(str(index_file)).getroot()
        except (OSError, etree.XMLSyntaxError):
            continue
        types = root.xpath(
            "/tei:TEI/tei:teiHeader//tei:bibl[@xml:id='project_source_bibl']/tei:idno/@type",
            namespaces={"tei": "http://www.tei-c.org/ns/1.0"},
        )
        if wanted.intersection(types):
            found.add(index_file.parent)
    return found


#: The public names of the comparison form of a text, and of the keys an opening is indexed by.
words = _words
keys = _keys
