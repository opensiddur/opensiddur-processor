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


def _key_word(skeleton: str) -> str:
    """A word as compared: the divine name made one spelling, and every ו and י after the
    first letter dropped, so that full and defective spellings (כרות, כרת) agree."""
    if skeleton in DIVINE_NAME_SPELLINGS:
        return "יהוה"
    return skeleton[:1] + skeleton[1:].replace("ו", "").replace("י", "")


def _words(text: str) -> list[str]:
    return [_key_word(w) for w in (normalize_hebrew(word) for word in text.split()) if w]


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

    def to_json(self) -> dict[str, list[str]]:
        # In the order the parts were found, which is the order of the texts.
        return {urn: list(words) for urn, words in self.incipit_of.items()}

    @classmethod
    def from_json(cls, data: dict[str, list[str]]) -> "IncipitIndex":
        index = cls()
        for urn, words in data.items():
            index.add(urn, words)
        return index


def index_document(index: IncipitIndex, root: etree._Element) -> None:
    """Add the opening words of each ``@corresp`` scope in one document."""
    pending: list[tuple[str, list[str]]] = []

    def feed(text: str | None) -> None:
        if not text or not pending:
            return
        words = _words(text)
        if not words:
            return
        still: list[tuple[str, list[str]]] = []
        for urn, collected in pending:
            collected.extend(words)
            if len(collected) >= COLLECTED_WORDS:
                index.add(urn, collected)
            else:
                still.append((urn, collected))
        pending[:] = still

    def flush() -> None:
        # A scope shorter than a full incipit still has an opening.
        for urn, collected in pending:
            index.add(urn, collected)
        pending.clear()

    def walk(element: etree._Element) -> None:
        if not isinstance(element.tag, str):
            feed(element.tail)
            return
        local = etree.QName(element).localname
        if local in ("teiHeader", "standOff", "note"):
            feed(element.tail)
            return
        corresp = element.get("corresp", "")
        if corresp.startswith(TEXT_PREFIX):
            pending.append((corresp.split("@", 1)[0], []))
        feed(element.text)
        for child in element:
            walk(child)
        feed(element.tail)

    walk(root)
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
    return index


#: Bumped whenever the words the index stores are normalized differently.
#: 2: parts are kept in document order, which the spans of departing rows need.
INDEX_VERSION = 2


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


#: The public name of the comparison form of a text.
words = _words
