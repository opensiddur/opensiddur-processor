"""Decide the URN of every text a Sefaria work sets, reusing the collection's where they exist.

Each :class:`blocks.TextBlock` is one text. Its URN is, in order of preference:

1. **A repeat.** A text the same volume printed earlier (Ashrei at Shacharit and at Minchah,
   Aleinu three times) is the same text, and its later printings transclude the first: one
   project carries a URN once. A later printing whose wording differs too much to be the same
   text (:func:`repeat_length`) is a text of its own; a block that runs on past the first
   printing is cut where it ends.
2. **An existing text.** The block's opening words are looked up in the incipit index of the
   collection's Hebrew projects (``util/incipit.py``), as the opensiddur.org importer does. A
   match is a whole text or a part of one (``prayer:amidah/avot``); when the block runs on
   past the part into the next part of the same text, it is the whole text, and the match
   moves up. A scriptural match is kept only as a whole chapter that the block opens at its
   first verse; a block that opens with a verse in the middle of a chapter (Hodu) is a
   liturgical text that quotes scripture, and is minted.
3. **A new text**, minted from its Hebrew incipit (``util/transliterate.py``), respelled, in
   ``prayer:``, lengthened until it is not taken.

Decisions are recorded in ``specs/sefaria/metsudah_urns.jsonl`` -- one line per block, keyed
by work, leaf and the Hebrew index of the block's first phrase -- and are sticky: a recorded
block keeps its URN on every later run, so a reviewer may correct a line and rerun. A record
carries a hash of the block's Hebrew (``as_of``); when the text changes, the record lapses and
the block is decided again and reported.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Collection, Iterable
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from opensiddur.common.constants import REPO_ROOT
from opensiddur.common.urn_registry import REGISTRY_DIRECTORY
from opensiddur.common.validate_names import Spellings, load_spellings
from opensiddur.importer.sefaria.blocks import Item, Rubric, TextBlock, is_phrase, split_block
from opensiddur.importer.sefaria.equivalents import Equivalents
from opensiddur.importer.sefaria.markup import is_numbered, is_pointed, plain_text
from opensiddur.importer.sefaria.phrases import SAME_PHRASE, map_phrases, similarity, skeleton
from opensiddur.importer.util.incipit import (
    BLESSING_FORMULA,
    CLOSING_WORDS,
    COLLECTED_WORDS,
    INCIPIT_WORDS,
    SHORT_INCIPIT_WORDS,
    TEXT_PREFIX,
    IncipitIndex,
    keys,
    parent,
    projects_with_source,
    words,
)
from opensiddur.importer.util.transliterate import name_from_hebrew

URNS_PATH = REPO_ROOT / "specs" / "sefaria" / "metsudah_urns.jsonl"
#: The ``idno`` types of the projects the index leaves out: the opensiddur.org imports, whose
#: rows open with formulas that match unrelated texts, and the Sefaria imports themselves.
EXCLUDED_SOURCES = ("opensiddur.org", "sefaria")
#: After the blessing formula, the words every blessing over a commandment shares.
MITZVAH_FORMULA = tuple(words("אשר קדשנו במצותיו וצונו"))
#: Words of a new text's incipit its name starts from, and the most it grows to. Two words
#: ("yehi_ratzon", "shir_hamaalot") would claim an opening many texts share.
MIN_NAME_WORDS, MAX_NAME_WORDS = 3, 8
NEW_NAMESPACE = "prayer"
#: The namespaces new texts are minted in, whose paths must not repeat across them.
MINTED_NAMESPACES = frozenset({"prayer", "poem"})
#: Openings that many petitions share: a new text is named "yehi_ratzon" and the words after.
PETITION_FORMULAS = tuple(tuple(words(f)) for f in (
    "יהי רצון מלפניך יהוה אלהינו ואלהי אבותינו",
    "יהי רצון מלפניך יהוה אלהי ואלהי אבותי",
    "יהי רצון מלפניך יהוה אלהינו",
    "יהי רצון מלפניך יהוה אלהי",
))
#: An address a text opens with that names none of it: a selichah's "Our God and God of our
#: fathers". A new text is named from the words after it, as Asher's Selichoth names them.
ADDRESS_FORMULAS = tuple(tuple(words(f)) for f in (
    "אלהינו ואלהי אבותינו",
))


@dataclass
class TextRecord:
    work: str
    leaf: str
    block: int
    urn: str
    #: "existing", "new" or "repeat"
    kind: str
    incipit: str
    as_of: str
    evidence: list[str] = field(default_factory=list)
    #: The block's phrase numbers, when they are not 1, 2, 3...: a text whose phrases an
    #: earlier volume named, or a variant's.
    phrases: list[int] | None = None
    #: For a "variant" -- a later printing of a text with words of its own -- its name: the
    #: last component of its condition URN (``tei_builder.variant_urn``).
    variant: str | None = None
    #: For a "variant", the texts the collection already names among its own words: the
    #: number of the passage's first phrase -> the text's URN (Nachem in Boneh Yerushalayim).
    parts: dict[str, str] | None = None

    @property
    def key(self) -> tuple[str, str, int]:
        return (self.work, self.leaf, self.block)

    def to_json(self) -> str:
        data = {k: v for k, v in asdict(self).items() if v not in (None, [])}
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> "TextRecord":
        data = json.loads(line)
        return cls(**data)


def load_records(path: Path = URNS_PATH) -> dict[tuple[str, str, int], TextRecord]:
    if not path.exists():
        return {}
    records = [TextRecord.from_json(line) for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    return {record.key: record for record in records}


def save_records(records: dict[tuple[str, str, int], TextRecord], path: Path = URNS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(records[key].to_json() + "\n" for key in sorted(records)), encoding="utf-8")


def block_text(block: TextBlock) -> str:
    """The Hebrew words of a block's phrases."""
    return " ".join(plain_text(pair.he) for pair in block.phrases)


def matching_words(pair) -> list[str]:
    """A phrase's words as matching compares them: without an alternative or insertion the
    book prints in parentheses (``(בעשי"ת הַשָּׁלוֹם)``)."""
    return words(re.sub(r"\([^)]*\)", " ", plain_text(pair.he)))


def block_hash(block: TextBlock) -> str:
    return hashlib.sha256(skeleton(block_text(block)).encode("utf-8")).hexdigest()[:16]


def phrase_skeletons(block: TextBlock) -> list[str]:
    return [skeleton(plain_text(pair.he)) for pair in block.phrases]


def _namespace_and_path(urn: str) -> tuple[str, list[str]]:
    namespace, _, path = urn[len(TEXT_PREFIX):].partition(":")
    return namespace, path.split("/")


#: How much of a candidate's collected opening (up to 16 words) the block must agree with,
#: beyond the six-word key that found it: many texts open with the same few words ("יהי רצון
#: מלפניך ה׳ אלהי ואלהי אבותי") and go on differently.
CONFIRM_OPENING = 0.6


#: How much better the best of several four-word matches must agree than the next.
CLEARLY_BEST = 0.1

#: How much a text the block opens like must agree, to be taken when the first text it opens
#: like is printed earlier and differs.
SECOND_CHOICE = 0.75


def excluded_projects(project_directory: Path) -> set[Path]:
    return projects_with_source(project_directory, EXCLUDED_SOURCES)


def lookup(index: IncipitIndex, block_words: list[str], *, confirm: bool = True) -> set[str]:
    """The index's candidates for a block, each confirmed (:func:`confirmed`), in tiers; the
    first tier that finds any wins.

    1. The index's own keys: six words (a blessing only by the words after its formula, since
       the formula opens every blessing and finds them all).
    2. Four words -- for a blessing, three to five words after the formula -- when they name
       one text, or one that agrees clearly best over its whole collected opening. Another
       rite's wording may part from the collection's within six words (Sefard וְלִתְפִלָּתָם,
       Ashkenaz וּבִתְפִלָּתָם), and a short blessing (בורא מיני מזונות) is all of three words.
    3. The same, a word or two out of step: the collection's text opens with a label or a
       heading word the book does not print (``א אזה מקמן``, ``ישתבח ישתבח``), the book's
       block opens a word late (``ואמונה``, its ``אמת`` ending the Shema before it), or the
       book prints a line of up to three words before the text (``לעמתם משבחים ואומרים``).

    ``confirm`` false takes the index's own keys unconfirmed: for the volume's own earlier
    printings, which the caller compares phrase by phrase.
    """
    blessing = tuple(block_words[:len(BLESSING_FORMULA)]) == BLESSING_FORMULA
    if blessing:
        found: set[str] = set()
        for key in keys(block_words)[:-1]:
            if len(key) >= SHORT_INCIPIT_WORDS and index.by_incipit.get(key):
                found = index._longest_opening(index.by_incipit[key], block_words)
                break
    else:
        found = index.lookup(block_words)
    if confirm:
        found = {u for u in found if confirmed(u, block_words, index)}
    if found:
        return found
    rest = block_words[len(BLESSING_FORMULA):]
    # A blessing over a commandment shares "אשר קדשנו במצותיו וצונו" with every other: its
    # keys must reach a word past it.
    shared = len(MITZVAH_FORMULA) if tuple(rest[:len(MITZVAH_FORMULA)]) == MITZVAH_FORMULA else 0
    if blessing:
        short = set()
        for length in (5, 4, 3):
            if len(rest) >= length > shared:
                short |= index.by_incipit.get(("§", *rest[:length]), set())
    else:
        short = set(index.by_incipit.get(tuple(block_words[:SHORT_INCIPIT_WORDS]), set()))
    best = clearly_best(short, lambda u: opening_agreement(u, block_words, index),
                        threshold=CONFIRM_OPENING if confirm else 0.0)
    if best:
        return best
    if blessing:
        # A blessing of two words after its formula (פוקח עורים) has no key of its own: it is
        # found by those words in the openings the index holds.
        two = (blessings_by_two_words(index).get(tuple(rest[:2]), set())
               if len(rest) >= 2 and not shared else set())
        return clearly_best(two, lambda u: opening_agreement(u, block_words, index))
    shifted: dict[str, float] = {}
    for urn, offset in shifted_openings(index).get(tuple(block_words[:SHORT_INCIPIT_WORDS]), ()):
        shifted[urn] = max(shifted.get(urn, 0.0), opening_agreement(urn, block_words, index, skip_text=offset))
    for skip in (1, 2, 3):
        for urn in index.by_incipit.get(tuple(block_words[skip:skip + SHORT_INCIPIT_WORDS]), ()):
            shifted[urn] = max(shifted.get(urn, 0.0),
                               opening_agreement(urn, block_words, index, skip_block=skip))
    return clearly_best(set(shifted), shifted.__getitem__)


def clearly_best(candidates: set[str], agreement, threshold: float = CONFIRM_OPENING) -> set[str]:
    """Of several candidates (a text and its first part counting as one, the part), the one
    that agrees best, when it agrees at least ``threshold`` and clearly better than the next."""
    deepest = {u for u in candidates if not any(o.startswith(u + "/") for o in candidates)}
    if not deepest:
        return set()
    ranked = sorted(deepest, key=lambda u: (-agreement(u), u))
    best = agreement(ranked[0])
    second = agreement(ranked[1]) if len(ranked) > 1 else 0.0
    return {ranked[0]} if best >= threshold and best - second >= CLEARLY_BEST else set()


def blessings_by_two_words(index: IncipitIndex) -> dict[tuple[str, ...], set[str]]:
    """The blessings the index holds, by the first two words after their formula. Kept on the
    index, and rebuilt when it has grown."""
    cached = getattr(index, "_two_word_blessings", None)
    if cached is not None and cached[0] == len(index.incipit_of):
        return cached[1]
    n = len(BLESSING_FORMULA)
    table: dict[tuple[str, ...], set[str]] = {}
    for urn, opening in index.incipit_of.items():
        if tuple(opening[:n]) == BLESSING_FORMULA and len(opening) >= n + 2:
            table.setdefault(tuple(opening[n:n + 2]), set()).add(urn)
    index._two_word_blessings = (len(index.incipit_of), table)  # type: ignore[attr-defined]
    return table


def shifted_openings(index: IncipitIndex) -> dict[tuple[str, ...], list[tuple[str, int]]]:
    """Four-word keys taken a word or two into each indexed opening, past a label or heading
    word: key -> (URN, words skipped). Kept on the index, and rebuilt when it has grown."""
    cached = getattr(index, "_shifted", None)
    if cached is not None and cached[0] == len(index.incipit_of):
        return cached[1]
    table: dict[tuple[str, ...], list[tuple[str, int]]] = {}
    for urn, opening in index.incipit_of.items():
        for offset in (1, 2):
            key = tuple(opening[offset:offset + SHORT_INCIPIT_WORDS])
            if len(key) == SHORT_INCIPIT_WORDS:
                table.setdefault(key, []).append((urn, offset))
    index._shifted = (len(index.incipit_of), table)  # type: ignore[attr-defined]
    return table


#: The words a blessing's closing formula opens with.
CHATIMAH = tuple(words("ברוך אתה יהוה"))


def chatimah(block_words: list[str] | tuple[str, ...]) -> tuple[str, ...] | None:
    """A blessing's closing formula, from ``ברוך אתה ה׳`` among its last words to the end
    (``ברוך אתה ה׳ חונן הדעת``), when it ends with one."""
    tail = list(block_words[-CLOSING_WORDS:])
    for k in range(len(tail) - len(CHATIMAH), -1, -1):
        if tuple(tail[k:k + len(CHATIMAH)]) == CHATIMAH:
            found = tuple(tail[k:])
            return found if len(found) > len(CHATIMAH) else None
    return None


def by_chatimah(index: IncipitIndex) -> dict[tuple[str, ...], set[str]]:
    """The texts the index holds, by their closing formula. Kept on the index, and rebuilt
    when it has grown."""
    size = (len(index.closing_of), len(index.ends_with))
    cached = getattr(index, "_by_chatimah", None)
    if cached is not None and cached[0] == size:
        return cached[1]
    table: dict[tuple[str, ...], set[str]] = {}
    for urn in set(index.closing_of) | set(index.ends_with):
        if not urn[len(TEXT_PREFIX):].startswith(("prayer:", "poem:")):
            continue  # scripture is not a blessing, and a siddur: URN is a place, not a text
        key = chatimah(index.closing(urn))
        if key is not None:
            table.setdefault(key, set()).add(urn)
    index._by_chatimah = (size, table)  # type: ignore[attr-defined]
    return table


def closing_text(block_words: list[str], index: IncipitIndex) -> str | None:
    """The one text (a text and its last part counting as one, the text) whose closing formula
    the block ends with, or None."""
    key = chatimah(block_words)
    if key is None:
        return None
    found = by_chatimah(index).get(key, set())
    shallowest = {u for u in found if not any(u.startswith(o + "/") for o in found)}
    return next(iter(shallowest)) if len(shallowest) == 1 else None


#: How closely a text found inside a block must agree over its collected opening for the
#: block to be cut there.
LATER_TEXT_AGREEMENT = 0.8


def _root_urn(urn: str) -> str:
    while parent(urn):
        urn = parent(urn)
    return urn


def _root(urn: str) -> str:
    namespace, path = _namespace_and_path(urn)
    return f"{namespace}:{path[0]}"


#: How much of what follows a short text in the collection must follow it in the block too.
FOLLOWED_ALIKE = 0.5


def _sibling_before(urn: str, before: list[str], index: IncipitIndex) -> bool:
    """Whether the words before hold the opening of another part of the text ``urn`` is a
    part of: the block is that text, a section at a time."""
    joined = "".join(before)
    here, up = urn, parent(urn)
    while up:
        for part in index.children.get(up, []):
            key = index.own_opening(part)[:INCIPIT_WORDS]
            if part != here and len(key) >= INCIPIT_WORDS and "".join(key) in joined:
                return True
        here, up = up, parent(up)
    return False


def _followed_alike(urn: str, rest: list[str], index: IncipitIndex) -> bool:
    """Whether a short text (one the index holds whole) is followed in the block by what follows
    it in the collection: Adonai Sefatai by the Amidah, not a line quoted from the end of Avinu
    Malkenu by words of another prayer."""
    length = index.length_of.get(urn)
    if length is None:
        return True
    after = list(index.incipit_of.get(urn, ()))[length:]
    if not after or len(rest) <= length + 2:
        # It ends the collection's document, or the block: then the other must end with it too.
        return len(rest) <= length + 2
    ours = rest[length:length + len(after)]
    return SequenceMatcher(None, after, ours, autojunk=False).ratio() >= FOLLOWED_ALIKE


def later_text(phrase_words: list[list[str]], urn: str | None, index: IncipitIndex, *,
               before: int | None = None) -> tuple[int, str] | None:
    """Where a block runs on into another text the collection names (Vezot Hatorah, then Yehi
    Ratzon Milifnei Avinu): the 0-based phrase it opens at, before ``before``, and its URN.
    Only a six-word match that agrees closely over the whole collected opening counts; scripture,
    and texts of the same family as ``urn`` (``amidah/...``), do not -- except a whole psalm,
    said after a text that does not open with a verse, from its first verse to its last."""
    if urn is not None and urn[len(TEXT_PREFIX):].startswith("bible:"):
        return None  # a chapter ends where its last verse does (_chapter_end), not at a verse in it
    family = _root(urn) if urn else None
    # What the collection's own encoding of the text, or of a text it is part of, transcludes
    # is the text's own (Birnbaum's Birkat Kohanim in the Amidah transcludes the verses).
    own: set[str] = set()
    up = urn
    while up:
        own |= index.included(up)
        up = parent(up)
    end = len(phrase_words) if before is None else before
    # Verses, then a psalm, are a collage, one text (Vihi Noam: Psalms 90:17, then Psalm 91).
    block_words = [w for phrase in phrase_words for w in phrase]
    collage = any(f[len(TEXT_PREFIX):].startswith("bible:")
                  and opening_agreement(f, block_words, index) >= LATER_TEXT_AGREEMENT
                  for f in index.lookup(block_words))
    # Where the collection prints the text going on into the psalm, the psalm is the text's.
    printed = index.incipit_of.get(urn, ()) if urn else ()
    for start in range(1, end):
        if sum(len(p) for p in phrase_words[:start]) < 2:
            continue  # not a word on its own (וְאָמְרוּ:) before the text it leads into
        rest = [w for phrase in phrase_words[start:] for w in phrase]
        if len(rest) < INCIPIT_WORDS:
            break
        found_here = sorted(index.lookup(rest))
        if not collage and (psalm := _psalm_opening(found_here, phrase_words[start:], own, index)) is not None \
                and not _contains(printed, rest[:INCIPIT_WORDS // 2]):
            return start, psalm
        if found_here and _contains(printed, rest[:INCIPIT_WORDS]):
            # The collection prints the text going on with these words (Asher's Vayaavor, with the
            # Thirteen Attributes a stanza of Ezkerah also quotes): they are the text's own.
            continue
        verse = any(f[len(TEXT_PREFIX):].startswith("bible:")
                    and opening_agreement(f, rest, index) >= LATER_TEXT_AGREEMENT for f in found_here)
        for found in found_here:
            if (found[len(TEXT_PREFIX):].startswith("poem:") and parent(found)
                    and not _opens(_root_urn(found), found, index)):
                continue  # a later stanza of a poem, quoting what the block says (the Thirteen Attributes)
            if (found[len(TEXT_PREFIX):].startswith("bible:") or _root(found) == family
                    or found in own or len(index.incipit_of.get(found, ())) < INCIPIT_WORDS):
                continue
            if verse and found in index.length_of and found in index.milestone_scoped:
                continue  # a verse the collection quotes inside a text, not the verse a text opens with
            if not _followed_alike(found, rest, index) and not _sibling_before(
                    found, [w for phrase in phrase_words[:start] for w in phrase], index):
                continue  # a line one text quotes from another (אבינו מלכנו חננו ועננו)
            if opening_agreement(found, rest, index) >= LATER_TEXT_AGREEMENT:
                return start, found
    return None


def _chapter_end(chapter: str, phrase_words: list[list[str]], index: IncipitIndex) -> int | None:
    """Where a block that is a chapter of scripture runs on past it (Psalm 20, then Uva
    Letziyon): the 0-based phrase after the one that ends its last verse, or None."""
    end = _chapter_span(chapter, phrase_words, index)
    return end if end is not None and end < len(phrase_words) else None


def _chapter_span(chapter: str, phrase_words: list[list[str]], index: IncipitIndex) -> int | None:
    """The phrases that run through ``chapter`` to the end of its last verse: the 0-based
    phrase after the one that ends it (the number of phrases, where it ends the block), or None
    where its last verse is not there."""
    verses = [u for u in index.children.get(chapter, []) if u.rsplit("/", 1)[-1].isdigit()]
    if not verses:
        return None
    last = max(verses, key=lambda u: int(u.rsplit("/", 1)[-1]))
    key = index.own_opening(last)[:SHORT_INCIPIT_WORDS]
    length = index.length_of.get(last)
    if len(key) < 2 or length is None:
        return None
    # Where it opens after the verse before it: an earlier verse may open alike (Psalm 99's
    # refrain, verses 5 and 9), and the text after the chapter may quote it (Uva Letziyon,
    # Psalm 20:10).
    after = 0
    ordered = sorted(verses, key=lambda u: int(u.rsplit("/", 1)[-1]))
    if len(ordered) > 1:
        before = index.own_opening(ordered[-2])[:SHORT_INCIPIT_WORDS]
        found = next((k for k in range(len(phrase_words)) if len(before) >= 2
                      and _opens_at(phrase_words, k, tuple(before))), None)
        after = found + 1 if found is not None else 0
    for start in range(after, len(phrase_words)):
        if _opens_at(phrase_words, start, tuple(key)):
            count = 0
            for j in range(start, len(phrase_words)):
                count += len(phrase_words[j])
                if count >= length:
                    return j + 1
            return None
    return None


#: The first verse of a psalm, which a block may run on into: the psalm is said whole after
#: the text (Psalm 130 after Yishtabach in the Ten Days of Repentance).
PSALM_OPENING = re.compile(r"^(bible:psalms/\d+)/1(?:/[a-z])?$")


def _contains(words_: Iterable[str], run: list[str]) -> bool:
    """Whether ``run`` is found, in order and together, in ``words_``."""
    words_ = list(words_)
    return bool(run) and any(words_[k:k + len(run)] == run for k in range(len(words_) - len(run) + 1))


def _psalm_opening(found_here: list[str], following: list[list[str]], own: set[str],
                   index: IncipitIndex) -> str | None:
    """The psalm a block runs on into, said whole from its first verse, where only scripture
    opens so (Hallel's psalms are Hallel's) and the text the block is does not include it."""
    if any(not f[len(TEXT_PREFIX):].startswith("bible:") for f in found_here):
        return None
    rest = [w for phrase in following for w in phrase]
    for found in found_here:
        match = PSALM_OPENING.match(found[len(TEXT_PREFIX):])
        if match is None:
            continue
        chapter = TEXT_PREFIX + match.group(1)
        if chapter in own or opening_agreement(found, rest, index) < LATER_TEXT_AGREEMENT:
            continue
        if _chapter_span(chapter, following, index) is not None:
            return chapter
    return None


def _opens(text: str, part: str, index: IncipitIndex) -> bool:
    """Whether ``part`` is where ``text`` begins: what it opens by transcluding, or its first
    part in the document, and so on down. Not a later part that opens with the same words
    (מודים דרבנן)."""
    here, seen = text, {text}
    while True:
        first = index.opens_with.get(here) or next(iter(index.children.get(here, [])), None)
        if first is None or first in seen:
            return False
        if first == part or part.startswith(first + "/"):
            return True
        here = first
        seen.add(first)


@dataclass
class Resolution:
    urn: str | None
    evidence: list[str]
    #: the 0-based phrase at which the next part of the same text opens, where the block runs
    #: on past the part it matched
    split_at: int | None = None


def _opens_at(phrase_words: list[list[str]], start: int, incipit: tuple[str, ...]) -> bool:
    following = [w for phrase in phrase_words[start:] for w in phrase][:len(incipit)]
    return bool(incipit) and tuple(following) == incipit




def opening_agreement(urn: str, block_words: list[str], index: IncipitIndex, *,
                      skip_text: int = 0, skip_block: int = 0) -> float:
    """How far a candidate's collected opening (up to 16 words) agrees with the block's, past
    ``skip_text`` words of the one and ``skip_block`` of the other."""
    # A short text's own words (where it ends before its collected opening is full), not the
    # words of whatever followed it in the collection.
    own = index.own_opening(urn)
    opening = list(own if len(own) >= SHORT_INCIPIT_WORDS else index.incipit_of.get(urn, ()))[skip_text:]
    if not opening:
        return 0.0
    ours = block_words[skip_block:skip_block + len(opening)]
    return SequenceMatcher(None, opening, ours, autojunk=False).ratio()


def opening_agreement_words(ours: list[str], theirs: list[str], length: int = COLLECTED_WORDS) -> float:
    """How far two printings' openings (up to ``length`` words) agree."""
    return SequenceMatcher(None, ours[:length], theirs[:length], autojunk=False).ratio()


def confirmed(urn: str, block_words: list[str], index: IncipitIndex) -> bool:
    if len(index.incipit_of.get(urn, ())) <= INCIPIT_WORDS or len(block_words) <= INCIPIT_WORDS:
        return True
    return opening_agreement(urn, block_words, index) >= CONFIRM_OPENING


def resolve(candidates: set[str], phrase_words: list[list[str]], index: IncipitIndex, *,
            cut_at_end: bool = True) -> Resolution:
    """The one text a block is, from the index's candidates.

    A match that opens a text -- its parent is encoded, and opens with the same words -- moves
    up to the whole text when the block runs on into another part of it. A match that is a later part of a text stays that part, and
    the block is cut where another part of the text opens (:attr:`Resolution.split_at`). Scripture moves up
    no further than a chapter and is never cut: a block that opens a chapter at its first verse
    is that chapter, and one that opens mid-chapter is liturgy quoting it.
    """
    evidence: list[str] = []
    block_words = [w for phrase in phrase_words for w in phrase]
    closing = closing_text(block_words, index)
    if not candidates:
        if closing is not None:
            # Opened otherwise -- another rite's words -- but closed with a blessing's formula.
            return Resolution(closing, [f"ends like {closing}, whose closing formula it shares"])
        return Resolution(None, evidence)
    for candidate in sorted(candidates):
        # A block that is one whole verse is that verse, whatever liturgical text also is it
        # (Malachi 3:4 after the Amidah; Birnbaum's Korbanot name it as one of their parts).
        namespace, path = _namespace_and_path(candidate)
        if namespace == "bible" and len(path) >= 3:
            verse = candidate if len(path) == 3 else parent(candidate)
            if _whole_verse(verse, block_words, index):
                return Resolution(verse, [f"the verse {verse}, whole"])
    liturgical = sorted(c for c in candidates if not c.startswith(TEXT_PREFIX + "bible:"))
    pool = liturgical or sorted(candidates)
    if len(pool) > 1:
        # Texts that open with the same words (הודו ליהוה כי טוב opens four psalms) are told
        # apart by what follows: the collected opening runs on past a short text's end.
        def agreement(u: str) -> float:
            opening = list(index.incipit_of.get(u, ()))
            return SequenceMatcher(None, opening, block_words[:len(opening)], autojunk=False).ratio()
        pool = sorted(pool, key=lambda u: (-round(agreement(u), 6), u))
    urn = pool[0]
    if len(pool) > 1:
        evidence.append(f"the opening matches {len(pool)} texts ({', '.join(pool[:4])}); took the one "
                        "that agrees best past it")
    joined = "".join(w for phrase in phrase_words for w in phrase)

    def part_key(u: str) -> tuple[str, ...]:
        # A part's opening, without words past its end -- unless it is too short to tell
        # where it is (a heading word), when the words after it say.
        own = index.own_opening(u)
        return (own if len(own) >= MIN_PART_KEY_WORDS else index.incipit_of.get(u, ()))[:INCIPIT_WORDS]

    def other_parts(u: str) -> list[str]:
        # The index keeps parts in the order of the files they were found in, which is not
        # always the order of the text, so every other part counts.
        return [s for s in index.children.get(parent(u), []) if s != u]

    def opening_in_parent(u: str) -> bool:
        # The parent is encoded, and the part's opening is at (or, past a heading caught in
        # the parent's opening, near) the start of it.
        up = parent(u)
        namespace, path = _namespace_and_path(u)
        if namespace == "bible" and path[-1] in ("1", "a"):
            return True  # scripture opens by position: the first half of a verse, its first verse
        if up in index.opens_with:
            # The parent opens by transcluding a part: its words begin with that part's.
            return index.opens_with[up] == u
        if up not in index.incipit_of:
            return False
        key = index.incipit_of[u][:SHORT_INCIPIT_WORDS]
        opening = index.incipit_of[up]
        return any(opening[k:k + len(key)] == key for k in range(0, SHORT_INCIPIT_WORDS + 1))

    def covers(u: str) -> bool:
        # The block holds most of the parent's other parts: it is the whole text, not one
        # part that happens to open it.
        others = other_parts(u)
        found = sum(1 for s in others
                    if "".join(index.own_opening(s)[:INCIPIT_WORDS] or part_key(s)) in joined)
        return bool(others) and found >= max(1, math.ceil(MOVE_UP_COVERAGE * len(others)))

    while parent(urn):
        namespace, path = _namespace_and_path(urn)
        if namespace == "bible" and len(path) <= 2:
            break  # never above a chapter
        if not (opening_in_parent(urn) and covers(urn)):
            break  # a part of the text: cut, below, where another part opens
        evidence.append(f"runs on past {urn.rsplit('/', 1)[-1]} through most of {parent(urn)}")
        urn = parent(urn)
    if closing is not None and closing != urn and urn.startswith(closing + "/") and _opens(closing, urn, index):
        # It opens like a part of a blessing and ends with the whole blessing's closing formula:
        # the blessing, in another rite's words.
        evidence.append(f"runs on to the closing formula of {closing}")
        urn = closing
        evidence.insert(0, f"opens like a part of {urn}")
        return Resolution(urn, evidence)
    namespace, path = _namespace_and_path(urn)
    if namespace == "bible":
        if len(path) >= 3:
            verse = urn if len(path) == 3 else parent(urn)
            if _whole_verse(verse, block_words, index):
                return Resolution(verse, [f"the verse {verse}, whole"])
            run = verse_run(verse, block_words, index)
            if run is not None:
                return Resolution(run, [f"the verses {run}, whole"])
            walked = _walk_verses(verse, block_words, index)
            if walked is not None:
                # The verses, then another text the collection names (Vayechulu, then Magen
                # Avot): cut where it opens.
                run, end = walked
                count = 0
                for j, phrase in enumerate(phrase_words[:-1]):
                    count += len(phrase)
                    if abs(count - end) <= VERSE_RUN_SLACK and any(
                            not u.startswith(TEXT_PREFIX + "bible:") for u in lookup(index, block_words[count:])):
                        # (Not more verses: verses after verses are a collage, one text.)
                        return Resolution(run, [f"the verses {run}, then another text"], j + 1)
                    if count > end + VERSE_RUN_SLACK:
                        break
            evidence.append(f"opens with the verse {urn}; a liturgical text, not that verse")
            return Resolution(None, evidence)
        first_verse = (index.incipit_of.get(f"{urn}/1") or index.incipit_of.get(f"{urn}/1/a") or ())[:INCIPIT_WORDS]
        if not first_verse or SequenceMatcher(None, list(first_verse), block_words[:len(first_verse)],
                                              autojunk=False).ratio() < FIRST_VERSE_AGREEMENT:
            evidence.append(f"quotes {urn} but does not open at its first verse")
            return Resolution(None, evidence)
        evidence.insert(0, f"opens like {urn}")
        return Resolution(urn, evidence, _chapter_end(urn, phrase_words, index))
    evidence.insert(0, f"opens like {urn}")
    split_at = None
    cut_at_part = None
    for sibling in other_parts(urn) if parent(urn) else []:
        incipit = part_key(sibling)
        if _is_stanza(sibling):
            # A stanza worded otherwise opens where it agrees best, if well enough.
            near = [(opening_agreement(sibling, [w for p in phrase_words[start:] for w in p], index), -start)
                    for start in range(1, len(phrase_words))
                    if sum(len(p) for p in phrase_words[:start]) >= 2]
            best = max(near, default=None)
            if best is not None and best[0] >= STANZA_AGREEMENT and (split_at is None or -best[1] < split_at):
                split_at = -best[1]
            continue
        for start in range(1, len(phrase_words)):
            if sum(len(p) for p in phrase_words[:start]) < 2:
                continue  # not a word on its own (וְאָמְרוּ:) before the part it leads into
            if _opens_at(phrase_words, start, incipit) and (
                    len(index.own_opening(sibling)) <= INCIPIT_WORDS
                    or opening_agreement(sibling, [w for p in phrase_words[start:] for w in p], index)
                    >= CONFIRM_OPENING):
                # Six words open many texts alike (יהי רצון מלפניך ה׳ אלהינו ואלהי): the part
                # must go on agreeing.
                if split_at is None or start < split_at:
                    split_at, cut_at_part = start, sibling
                break
    if split_at is not None:
        evidence.append(f"cut before phrase {split_at + 1}, where the next part of {parent(urn)} opens")
        opening = index.first_part(urn)
        if cut_at_part in index.included(urn) and opening not in (None, urn):
            # A text made of parts (Birnbaum's half Kaddish: יתגדל, the response, יתברך), cut
            # where another of its own parts opens: the block is the part it opens with.
            evidence.append(f"the part {opening.rsplit(':', 1)[-1]} {urn.rsplit(':', 1)[-1]} opens with")
            urn = opening
    # A text the index holds whole (shorter than its collected opening) ends where its words do.
    whole = index.own_opening(urn)
    if (cut_at_end and 0 < len(whole) < COLLECTED_WORDS and len(block_words) > len(whole) + 2
            and urn not in index.compound):
        count = 0
        for j, phrase in enumerate(phrase_words):
            count += len(phrase)
            if count >= len(whole):
                if continues_closing(phrase_words[j + 1:]):
                    break  # "... and Rosh Chodesh": the closing goes on, not another text
                if 0 < j + 1 < len(phrase_words) and (split_at is None or j + 1 < split_at):
                    split_at = j + 1
                    evidence.append(f"cut before phrase {j + 2}, where {urn.rsplit(':', 1)[-1]} ends")
                break
    return Resolution(urn, evidence, split_at)


#: How closely the next stanza of a poem must agree with the collection's, over its collected
#: opening, where another rite words its opening otherwise (Nusach Lita's פְּחוּדִים הֵם מִכָּל
#: צָרוֹת, Asher's ... צָרֵיהֶם): the stanza two lines on agrees at most 0.62.
STANZA_AGREEMENT = 0.75


def _is_stanza(urn: str) -> bool:
    return urn.rsplit("/", 1)[-1].startswith("stanza_")


#: The most words a last phrase opening "and" may add to a text the index holds whole and still
#: be its continuation (מקדש השבת / וישראל וראשי חדשים), not a text of its own.
CONTINUED_CLOSING_WORDS = 4
def _whole_verse(verse: str, block_words: list[str], index: IncipitIndex) -> bool:
    """Whether the block is the verse, whole: its own words, a word more or less."""
    own = list(index.own_opening(verse)) if verse in index.length_of else []
    return bool(own) and abs(len(block_words) - len(own)) <= 1 and SequenceMatcher(
        None, own, block_words, autojunk=False).ratio() >= WHOLE_VERSE_AGREEMENT


def continues_closing(rest: list[list[str]]) -> bool:
    """Whether the phrases after a text's end only carry its closing on: one short phrase opening
    "and" (מקדש השבת / וישראל וראשי חדשים), not a text of its own."""
    return len(rest) == 1 and 0 < len(rest[0]) <= CONTINUED_CLOSING_WORDS and rest[0][0].startswith("ו")


#: How closely a block must agree with a verse to be that verse, whole.
WHOLE_VERSE_AGREEMENT = 0.85
#: How far (in words) a verse may open from where the verses before it end, in another
#: source's spelling (a word printed joined or apart); and how many of its opening words must
#: agree there.
VERSE_DRIFT, VERSE_OPENING_WORDS, VERSE_OPENING_AGREEMENT = 3, 4, 0.75
#: How far the last verse of a run may end from the end of the block.
VERSE_RUN_SLACK = 2


def verse_run(first: str, block_words: list[str], index: IncipitIndex) -> str | None:
    """The run of verses a block is, whole: ``bible:proverbs/31/10-31`` -- or its chapter, when
    it runs from the first verse to the last -- when the block opens at ``first`` and goes on
    through the verses after it, in order, to its end. ``None`` when it is a single verse, or
    leaves the verses for words of its own."""
    walked = _walk_verses(first, block_words, index)
    if walked is None or abs(walked[1] - len(block_words)) > VERSE_RUN_SLACK:
        return None
    return walked[0]


#: How far past a long verse's opening its last words are looked for.
MAX_VERSE_WORDS = 80


def _words_end(closing: list[str], block_words: list[str], start: int) -> int | None:
    """Where ``closing`` ends in the block, looking from ``start``: the first place it agrees."""
    if len(closing) < VERSE_OPENING_WORDS:
        return None
    for at in range(start, min(len(block_words), start + MAX_VERSE_WORDS) - len(closing) + 1):
        if SequenceMatcher(None, closing, block_words[at:at + len(closing)],
                           autojunk=False).ratio() >= VERSE_OPENING_AGREEMENT:
            return at + len(closing)
    return None


def _verse_opens_at(opening: list[str], block_words: list[str], at: int) -> bool:
    """Whether the block has a verse's opening words at ``at``: word by word, or letter by
    letter when the source splits a word in two (Metsudah's ``שִׁלְּ֒ חָה``, Proverbs 31:19)."""
    here = block_words[at:at + len(opening)]
    if len(here) < len(opening):
        return False
    if SequenceMatcher(None, opening, here, autojunk=False).ratio() >= VERSE_OPENING_AGREEMENT:
        return True
    letters = "".join(opening)
    found = "".join(block_words[at:at + len(opening) + 1])[:len(letters)]
    return SequenceMatcher(None, letters, found, autojunk=False).ratio() >= VERSE_OPENING_AGREEMENT


def _walk_verses(first: str, block_words: list[str], index: IncipitIndex) -> tuple[str, int] | None:
    """The run of two or more verses the block opens with, from ``first`` (:func:`verse_run`),
    and the word where it ends."""
    chapter, _, number = first.rpartition("/")
    if not number.isdigit():
        return None
    start = int(number)
    pos, verse = 0, start
    while True:
        urn = f"{chapter}/{verse}"
        length = index.length_of.get(urn)
        opening = list(index.own_opening(urn))[:VERSE_OPENING_WORDS]
        if len(opening) < min(VERSE_OPENING_WORDS, length or VERSE_OPENING_WORDS):
            break
        best = None
        for drift in sorted(range(-VERSE_DRIFT, VERSE_DRIFT + 1), key=abs):
            at = pos + drift
            if at < 0 or (verse == start and drift):
                continue
            if _verse_opens_at(opening, block_words, at):
                best = at
                break
        if best is None:
            break
        if length is None:
            # A verse longer than the index's collected opening: it ends where its last words do.
            end = _words_end(list(index.closing(urn))[-VERSE_OPENING_WORDS:], block_words,
                             best + len(opening))
            if end is None:
                break
            pos, verse = end, verse + 1
        else:
            pos, verse = best + length, verse + 1
        if pos >= len(block_words) - VERSE_RUN_SLACK:
            break
    last = verse - 1
    if last <= start:
        return None
    if start == 1 and f"{chapter}/{last + 1}" not in index.incipit_of:
        return chapter, pos
    return f"{chapter}/{start}-{last}", pos

#: How closely a block must open like a chapter's first verse to be that chapter (two sources
#: of scripture spell לה׳ differently).
FIRST_VERSE_AGREEMENT = 0.8

#: The fewest words of a part's own that tell where it is in a block.
MIN_PART_KEY_WORDS = 3

#: Share of a text's other parts a block must hold to be the whole text rather than the part
#: that opens it.
MOVE_UP_COVERAGE = 0.75

#: Share of an earlier printing's phrases a later block must print, and share of the block's
#: phrases (up to where the earlier printing ends) that must be the earlier printing's, for the
#: block to be that text again.
REPEAT_COVERAGE = 0.75
#: The most phrases between two matched phrases of one printing.
REPEAT_GAP = 3


#: The share of an earlier printing that must follow a variant's own passage, for the passage
#: to stand inside the text rather than after it.
INSERTION_REST = 0.15

#: The share, for a variant, in place of :data:`REPEAT_COVERAGE`: a later printing that adds or
#: leaves out a passage (Nachem at Minchah of Tisha b'Av) is still the text.
VARIANT_COVERAGE = 0.5


def regrouped_length(block_phrases: list[str], earlier: list[str]) -> int | None:
    """How many of a block's phrases hold exactly the words of ``earlier`` (phrase skeletons),
    lined otherwise: a text the book printed phrase by phrase and prints again as a paragraph
    (the Selichot's later days, which set the close of the service in paragraphs). None when
    the words differ, or when ``earlier`` ends inside one of the block's phrases."""
    wanted = " ".join(earlier).split()
    seen: list[str] = []
    for count, phrase in enumerate(block_phrases, 1):
        seen.extend(phrase.split())
        if len(seen) >= len(wanted):
            return count if seen == wanted else None
        if seen != wanted[:len(seen)]:
            return None
    return None


def repeat_length(block_phrases: list[str], earlier: list[str], coverage: float = REPEAT_COVERAGE,
                  *, insertions: bool = False, introduced: frozenset[int] = frozenset()) -> int | None:
    """How many of a block's phrases are a later printing of ``earlier`` (phrase skeletons),
    or None when the block is not that text. Phrases are paired as :func:`map_phrases` pairs
    them, so a phrase that is mostly the same counts.

    With ``insertions``, a passage of the block's own may stand in the middle, however long:
    when the book introduces it with a rubric (its first phrase in ``introduced``, the block's
    phrases a rubric comes before) and the rest of ``earlier`` follows it, in order, to its last
    phrase (Minchah's Boneh Yerushalayim, Nachem printed before its closing), the printing runs
    on to there."""
    if not earlier or not block_phrases:
        return None
    numbers = map_phrases(block_phrases, {i + 1: s for i, s in enumerate(earlier)})
    matched = [i for i, n in enumerate(numbers) if n <= len(earlier)]
    needed = math.ceil(coverage * len(earlier))
    if len(matched) < needed:
        return None
    # Where the earlier printing ends in the block: once enough of it is matched, as far as the
    # matches run on without a gap. A phrase further on that happens to be like one of the
    # earlier printing's (a closing verse both texts end with) is not part of it.
    if insertions:
        # The passage may come early, before as much of the earlier printing as coverage asks
        # (Attah Chonantanu, after the two phrases Binah opens with): the printing so far is the
        # run of matches from the first.
        head = 0
        while head + 1 < len(matched) and matched[head + 1] - matched[head] <= REPEAT_GAP:
            head += 1
        inserted = _inserted_until(numbers, matched, head, len(earlier), introduced)
        if inserted is not None:
            return inserted
    end = needed - 1
    while end + 1 < len(matched) and matched[end + 1] - matched[end] <= REPEAT_GAP:
        end += 1
    if insertions and end + 1 < len(matched):
        seen = [numbers[i] for i in matched[:end + 1]]
        rest = [numbers[i] for i in matched[end + 1:]]
        rest_at = matched[end + 1:]
        # The rest of the earlier printing, after the passage: all of it, in order, without
        # gaps, and enough of it -- a closing "וְאִמְרוּ אָמֵן" many texts share is not.
        if (matched[end] + 1 in introduced
                and rest == sorted(rest) and min(rest) > max(seen)
                and sorted(seen + rest) == list(range(1, len(earlier) + 1))
                and len(rest) >= max(2, math.ceil(INSERTION_REST * len(earlier)))
                and all(b - a <= REPEAT_GAP for a, b in zip(rest_at, rest_at[1:]))):
            return matched[-1] + 1
    length = matched[end] + 1
    if (end + 1) / length >= coverage:
        return length
    return None


def _inserted_until(numbers: list[int], matched: list[int], head: int, count: int,
                    introduced: frozenset[int]) -> int | None:
    """Where a printing with a passage of its own after its ``head``-th match ends: the end of
    the earlier printing's rest, when the passage is introduced and all of the rest follows it,
    in order and without gaps. None otherwise."""
    if head + 1 >= len(matched) or matched[head] + 1 not in introduced:
        return None
    seen = [numbers[i] for i in matched[:head + 1]]
    rest = [numbers[i] for i in matched[head + 1:]]
    rest_at = matched[head + 1:]
    if (rest == sorted(rest) and min(rest) > max(seen)
            and sorted(seen + rest) == list(range(1, count + 1))
            and len(rest) >= max(2, math.ceil(INSERTION_REST * count))
            and all(b - a <= REPEAT_GAP for a, b in zip(rest_at, rest_at[1:]))):
        return matched[-1] + 1
    return None


def distinctive_words(block_words: list[str]) -> list[str]:
    """What tells a blessing apart: its words after the formula, and after "אשר קדשנו במצותיו
    וצונו" for a blessing over a commandment. Not a blessing: all its words."""
    if tuple(block_words[:len(BLESSING_FORMULA)]) != BLESSING_FORMULA:
        return block_words
    rest = block_words[len(BLESSING_FORMULA):]
    if tuple(rest[:len(MITZVAH_FORMULA)]) == MITZVAH_FORMULA:
        rest = rest[len(MITZVAH_FORMULA):]
    return rest


def same_blessing(block_words: list[str], earlier_words: list[str]) -> bool:
    """Whether two printings can be one text, as far as blessings go: two blessings only when
    their first words past the formulas agree (על מצות ציצית is not על מצות תפלין)."""
    if tuple(block_words[:len(BLESSING_FORMULA)]) != BLESSING_FORMULA:
        return True
    ours, theirs = distinctive_words(block_words), distinctive_words(earlier_words)
    length = min(BLESSING_DISTINCTIVE_WORDS, len(ours), len(theirs))
    return length > 0 and ours[:length] == theirs[:length]


#: The words past a blessing's formulas that must agree for two printings to be one blessing.
BLESSING_DISTINCTIVE_WORDS = 3


def introduced_phrases(block: TextBlock) -> frozenset[int]:
    """The positions of a block's phrases that a rubric comes directly before, or that open a
    parenthesis: the book sets the passage off (``(אַתָּה חוֹנַנְתָּֽנוּ`` at Maariv)."""
    found: set[int] = set()
    position = 0
    after_rubric = False
    for pair in block.pairs:
        if is_phrase(pair):
            if after_rubric or plain_text(pair.he).lstrip().startswith("("):
                found.add(position)
            position += 1
            after_rubric = False
        else:
            after_rubric = True
    return frozenset(found)


def mint(text: str, taken: set[str], spellings: Spellings, namespace: str = NEW_NAMESPACE) -> str:
    """A new URN in ``namespace`` (``prayer:`` unless the work says otherwise) from a text's
    incipit. A blessing is named from the words after its formula, which every blessing shares."""
    # Words as the index counts them: a maqaf separates words, punctuation alone is none.
    # A parenthesized or unpointed word is a label or an abbreviation, not the text's words.
    hebrew = [token for token in re.split(r"[\s\u05be]+", re.sub(r"\([^)]*\)", " ", text))
              if words(token) and is_pointed(token) and not token.startswith("(")]
    if tuple(words(" ".join(hebrew[:6]))) == BLESSING_FORMULA:
        hebrew = hebrew[6:] or hebrew
        if tuple(words(" ".join(hebrew[:4]))) == MITZVAH_FORMULA:
            hebrew = hebrew[4:] or hebrew
    for formula in ADDRESS_FORMULAS:
        if (tuple(words(" ".join(hebrew[:len(formula)]))) == formula
                and len(hebrew) >= len(formula) + MIN_NAME_WORDS):
            hebrew = hebrew[len(formula):]
            break
    if hebrew and words(hebrew[0]) == ["אמן"] and len(hebrew) > MIN_NAME_WORDS:
        hebrew = hebrew[1:]  # the response before the text (אָמֵן. כְּשֵׁם שֶׁנִּכְנַס)
    minimum = MIN_NAME_WORDS
    for formula in PETITION_FORMULAS:
        if tuple(words(" ".join(hebrew[:len(formula)]))) == formula and len(hebrew) > len(formula):
            # "yehi_ratzon", and then the words that say what is asked for -- two at least.
            hebrew = hebrew[:2] + hebrew[len(formula):]
            minimum = MIN_NAME_WORDS + 1
            break
    def free(name: str) -> bool:
        # A path is taken in either namespace: a prayer and a poem of one name would share
        # their metsudah: phrases.
        return all(f"{TEXT_PREFIX}{other}:{name}" not in taken for other in MINTED_NAMESPACES | {namespace})

    for count in range(minimum, MAX_NAME_WORDS + 1):
        name = name_from_hebrew(" ".join(hebrew), count, spellings)
        if not name:
            break
        if free(name):
            return f"{TEXT_PREFIX}{namespace}:{name}"
    base = name_from_hebrew(" ".join(hebrew), MAX_NAME_WORDS, spellings) or "text"
    n = 2
    while not free(f"{base}_{n}"):
        n += 1
    return f"{TEXT_PREFIX}{namespace}:{base}_{n}"


def registry_urns(registry_directory: Path = REGISTRY_DIRECTORY) -> set[str]:
    urns: set[str] = set()
    for path in registry_directory.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                urns.add(json.loads(line)["urn"])
    return urns


@dataclass
class Decisions:
    """The outcome of deciding a work's texts: every block's record, and what changed."""

    records: dict[tuple[str, str, int], TextRecord]
    decided: list[TextRecord] = field(default_factory=list)
    lapsed: list[TextRecord] = field(default_factory=list)


def decide_work(
    work_key: str,
    leaves: Iterable[tuple[str, list[Item]]],
    index: IncipitIndex,
    records: dict[tuple[str, str, int], TextRecord],
    taken: set[str],
    *,
    recorded_phrases: dict[str, dict[int, str]] | None = None,
    spellings: Spellings | None = None,
    places: dict[str, str] | None = None,
    own_phrases: dict[str, dict[int, str]] | None = None,
    equivalents: Equivalents | None = None,
    registered: set[str] | None = None,
    clashes: Collection[str] = frozenset(),
    numbered_namespace: str = NEW_NAMESPACE,
) -> Decisions:
    """Decide the URN of every block of ``work_key`` that has no current record.

    ``leaves`` is each leaf's path with its items (``blocks.divide``), in book order. A text
    found to run on past the text it is -- or a first printing that a later one shows ran on
    past it -- is cut, and its leaf's list is changed in place to hold both parts. A cut is
    recorded by the second part's record, and replayed from it on every later run.
    ``taken`` is every URN already in use (registry and records); minted URNs are added to it.
    ``recorded_phrases`` are the phrases other Metsudah volumes have named
    (``phrases.recorded_phrases``), and ``own_phrases`` the ones this work's Hebrew project named
    on its last run, which a text whose words changed keeps. ``places`` gives each leaf's
    ``siddur:`` path, which names the variants printed there. ``equivalents`` are the curated
    choices (``equivalents.yaml``), and ``registered`` the URNs the registry holds: a chosen URN
    it does not hold is minted: in ``prayer:``, or, when the book numbers the text (a numbered
    label just before it, ``markup.is_numbered``), in ``numbered_namespace``.
    """
    decider = _Decider(work_key, index, records, taken, recorded_phrases or {},
                       spellings or load_spellings(), places or {})
    decider.own_phrases = own_phrases or {}
    decider.equivalents = equivalents or Equivalents()
    decider.registered = taken if registered is None else registered
    decider.clashes = clashes
    decider.numbered_namespace = numbered_namespace
    return decider.run(leaves)


@dataclass
class _Printing:
    """Where this volume first printed a text, so that a later printing can cut it."""

    leaf: str
    blocks: list[Item]
    block: TextBlock


class _Decider:
    def __init__(self, work_key: str, index: IncipitIndex, records: dict[tuple[str, str, int], TextRecord],
                 taken: set[str], recorded_phrases: dict[str, dict[int, str]], spellings: Spellings,
                 places: dict[str, str]):
        self.work_key = work_key
        self.places = places
        #: the highest phrase number each text has used, its variants' included
        self.numbers_used: dict[str, int] = {}
        # A later printing's record, kept when its block is reached, has numbered its own
        # phrases already: a variant decided before it must not reuse them.
        for record in records.values():
            if record.work == work_key and record.phrases:
                self.note_numbers(record.urn, record.phrases)
        #: the variant names each text has
        self.variant_names: dict[str, set[str]] = {}
        #: texts the collection names that a variant's own words are, each used once
        self.parts_used: set[str] = set()
        self._printed_numbers: set[int] = set()
        #: where the candidate :meth:`another_candidate` took would cut the block
        self.candidate_cut: int | None = None
        #: the blocks decided (by ``id``)
        self.done: set[int] = set()
        #: blocks a cut replaced, kept so that their ids are not reused
        self.replaced: list[TextBlock] = []
        self.equivalents = Equivalents()
        self.registered: set[str] = set(taken)
        #: texts whose first printing was chosen (equivalents.yaml): a later, shorter printing
        #: does not cut them
        self.chosen: set[str] = set()
        #: the phrases this work's own Hebrew project named on the last run, by text path
        self.own_phrases: dict[str, dict[int, str]] = {}
        #: the paths more than one text namespace uses (``phrases.clashing_paths``)
        self.clashes: Collection[str] = frozenset()
        #: the namespace a new text the book numbers is minted in (the work's ``numbered_texts``)
        self.numbered_namespace = NEW_NAMESPACE
        self.index = index
        self.records = records
        self.taken = taken
        self.recorded_phrases = recorded_phrases
        self.spellings = spellings
        self.outcome = Decisions(dict(records))
        self.printed: dict[str, _Printing] = {}
        #: texts too short for the incipit index: their words -> URN
        self.short_printed: dict[str, str] = {}
        self.own = IncipitIndex()
        self.stale_keys = {key for key in records if key[0] == work_key}
        #: each leaf's recorded block starts: where earlier runs cut
        self.starts: dict[str, set[int]] = {}
        for work, leaf, block in records:
            if work == work_key:
                self.starts.setdefault(leaf, set()).add(block)

    def run(self, leaves: Iterable[tuple[str, list[Item]]]) -> Decisions:
        for leaf_path, blocks in leaves:
            i = 0
            while i < len(blocks):
                # A first printing cut in this leaf moves the blocks after it along: a block
                # already decided is not decided again.
                if isinstance(blocks[i], TextBlock) and id(blocks[i]) not in self.done:
                    self.decide(leaf_path, blocks, i)
                i += 1
        for key in sorted(self.stale_keys):
            self.outcome.lapsed.append(self.outcome.records.pop(key))
        return self.outcome

    # -- bookkeeping -----------------------------------------------------------------------

    def key(self, leaf: str, block: TextBlock) -> tuple[str, str, int]:
        return (self.work_key, leaf, block.first_index)

    def remember(self, urn: str, leaf: str, blocks: list[Item], block: TextBlock,
                 phrases: list[int] | None = None) -> None:
        self.note_numbers(urn, phrases or list(range(1, len(block.phrases) + 1)))
        self.printed.setdefault(urn, _Printing(leaf, blocks, block))
        self.own.add(urn, [w for pair in block.phrases for w in matching_words(pair)])
        self.short_printed.setdefault(skeleton(block_text(block)), urn)

    def note_numbers(self, urn: str, phrases: list[int]) -> None:
        if phrases:
            self.numbers_used[urn] = max(self.numbers_used.get(urn, 0), max(phrases))

    def keep(self, record: TextRecord, leaf: str, blocks: list[Item], block: TextBlock) -> None:
        """Take a current record into account without deciding anew."""
        self.done.add(id(block))
        if record.kind == "variant":
            self.note_numbers(record.urn, record.phrases or [])
            self.parts_used.update((record.parts or {}).values())
            self.variant_names.setdefault(record.urn, set()).add(record.variant or "")
        elif record.kind != "repeat":
            self.remember(record.urn, leaf, blocks, block, record.phrases)

    def opens_as_recorded(self, leaf: str, block: TextBlock, j: int) -> bool:
        """Whether the text a record says begins at the block's ``j``-th phrase still begins
        with the words it was recorded with: a recorded cut is replayed only then, not after the
        leaf was resegmented under it."""
        record = self.records.get((self.work_key, leaf, block.phrases[j].he_index))
        if record is None:
            return False
        # The record holds at most six words: fewer when its text is shorter.
        recorded = record.incipit.split()
        here = " ".join(" ".join(plain_text(p.he) for p in block.phrases[j:]).split()[:len(recorded)])
        return skeleton(here) == skeleton(" ".join(recorded))

    def kept_numbers(self, record: TextRecord, skeletons: list[str]) -> list[int] | None:
        """The phrase numbers of a text whose words changed: the ones its phrases had, by the
        phrases this project named last time where they are known, else as recorded when the
        count is the same, else 1, 2, 3..."""
        from opensiddur.importer.sefaria.phrases import text_path

        named = self.own_phrases.get(text_path(record.urn, self.clashes))
        if named:
            numbers = map_phrases(skeletons, named)
        elif record.phrases and len(record.phrases) == len(skeletons):
            numbers = record.phrases
        else:
            numbers = list(range(1, len(skeletons) + 1))
        return None if numbers == list(range(1, len(numbers) + 1)) else numbers

    def variant_name(self, urn: str, leaf: str, block: TextBlock) -> str:
        """A variant's name: the ``siddur:`` place it is printed at (``chol_minchah_amidah``),
        made unique among the text's variants."""
        place = self.places.get(leaf) or re.sub(r"[^a-z0-9]+", "_", leaf.lower()).strip("_")
        name = place.replace("/", "_")
        names = self.variant_names.setdefault(urn, set())
        if name in names:
            name = f"{name}_{block.first_index}"
        names.add(name)
        return name

    def save(self, record: TextRecord, *, lapsed: TextRecord | None = None) -> None:
        if lapsed is not None and lapsed not in self.outcome.lapsed:
            self.outcome.lapsed.append(lapsed)
        self.outcome.records[record.key] = record
        # A record decided again this run (a first printing cut later) replaces the first.
        self.outcome.decided = [r for r in self.outcome.decided if r.key != record.key]
        self.outcome.decided.append(record)

    def cut(self, leaf: str, blocks: list[Item], i: int, at: int) -> TextBlock:
        # The block cut stays referenced: :attr:`done` holds ids, which Python would otherwise
        # give to a new block.
        self.replaced.append(blocks[i])
        first, rest = split_block(blocks[i], at)
        blocks[i:i + 1] = [first, rest]
        return first

    # -- deciding --------------------------------------------------------------------------

    def decide(self, leaf: str, blocks: list[Item], i: int) -> None:
        block = blocks[i]
        assert isinstance(block, TextBlock)
        # Replay the cuts earlier runs made: a recorded start inside this block.
        replay = next((j for j, pair in enumerate(block.phrases)
                       if j > 0 and pair.he_index in self.starts.get(leaf, ())
                       and self.opens_as_recorded(leaf, block, j)), None)
        # A new blessing in the middle of a block is a text of its own -- unless the block is
        # one text that opens with a part of it and ends with its closing formula (Barukh
        # She'amar: its litany, then its blessing). It is cut there even where a recorded start
        # lies further on (Kiddush Levanah's blessing, after Psalm 148, before Psalm 67's verse).
        phrase_words = [words(plain_text(pair.he)) for pair in block.phrases]
        blessing = next((j for j in range(1, replay if replay is not None else len(phrase_words))
                         if _opens_at(phrase_words, j, BLESSING_FORMULA)), None)
        if blessing is not None:
            # Whether the block up to the recorded start is one text ending with the blessing's
            # closing formula: what follows that start is another text's.
            matching = [matching_words(pair) for pair in block.phrases[:replay]]
            whole = resolve(lookup(self.index, [w for p in matching for w in p]), matching, self.index)
            closing = closing_text([w for p in matching for w in p], self.index)
            if whole.split_at is not None and whole.split_at < blessing:
                # The text the block opens with ends before the blessing (Hareini Mezammen,
                # then Barukh She'amar): the block after it is judged on its own.
                pass
            elif whole.urn is None or closing is None or not (
                    whole.urn == closing or whole.urn.startswith(closing + "/")):
                # Not one text that ends with the blessing's closing formula.
                replay = blessing
        if replay is not None:
            block = self.cut(leaf, blocks, i, replay)
        key = self.key(leaf, block)
        self.stale_keys.discard(key)
        text = block_text(block)
        record = self.records.get(key)
        if record is not None and record.as_of == block_hash(block) and (
                record.urn not in self.printed if record.kind in ("existing", "new") else record.urn in self.printed):
            # A repeat or variant is current only while its first printing is; a first printing,
            # only while no block before it now prints the text (a text cut off earlier in the
            # book, Psalm 67 in Kiddush Levanah before the counting of the Omer).
            self.keep(record, leaf, blocks, block)
            return
        if record is not None and record.kind in ("existing", "new") and record.urn not in self.printed and (
                similarity(skeleton(record.incipit), skeleton(" ".join(text.split()[:INCIPIT_WORDS])))
                >= SAME_PHRASE) and not self.runs_on(record.urn, block):
            # The words changed, but it is still the text it was: it keeps its URN, and its
            # phrases their numbers.
            skeletons = phrase_skeletons(block)
            phrases = self.kept_numbers(record, skeletons)
            self.done.add(id(block))
            self.save(TextRecord(
                work=self.work_key, leaf=leaf, block=block.first_index, urn=record.urn, kind=record.kind,
                incipit=" ".join(text.split()[:INCIPIT_WORDS]), as_of=block_hash(block),
                evidence=record.evidence + ["the words changed; the URN of the earlier decision is kept"],
                phrases=phrases), lapsed=record)
            self.remember(record.urn, leaf, blocks, block, phrases)
            return
        self.decide_anew(leaf, blocks, i, record)

    def runs_on(self, urn: str, block: TextBlock) -> bool:
        """Whether a block runs on past the text ``urn`` into another (a chapter ends, a text the
        collection names opens): its words changed because it was divided otherwise, not
        because the text did, and it is decided again (and cut)."""
        phrase_words = [matching_words(pair) for pair in block.phrases]
        namespace, path = _namespace_and_path(urn)
        if namespace == "bible" and len(path) == 2:
            return _chapter_end(urn, phrase_words, self.index) is not None
        if namespace == "bible":
            # A verse, or a run of verses: the block must still be that, whole.
            block_words = [w for phrase in phrase_words for w in phrase]
            head, _, last = urn.rpartition("/")
            first = f"{head}/{last.split('-', 1)[0]}"
            return not ((first == urn and _whole_verse(urn, block_words, self.index))
                        or verse_run(first, block_words, self.index) == urn)
        if urn not in self.index.incipit_of:
            return False
        split = resolve({urn}, phrase_words, self.index).split_at
        return split is not None or later_text(phrase_words, urn, self.index) is not None

    def later_choice(self, leaf: str, phrase_words: list[list[str]], *,
                     before: int | None = None) -> tuple[int, str] | None:
        """Where a block runs on into a text ``equivalents.yaml`` chooses whole by its last
        words (``ends``): the 0-based phrase it opens at, before ``before``, and its URN."""
        end = len(phrase_words) if before is None else before
        for start in range(1, end):
            if sum(len(p) for p in phrase_words[:start]) < 2:
                continue
            found = self.equivalents.choice(leaf, [w for phrase in phrase_words[start:] for w in phrase])
            if found is not None and found.ends:
                return start, found.urn
        return None

    def decide_anew(self, leaf: str, blocks: list[Item], i: int, record: TextRecord | None) -> None:
        block = blocks[i]
        assert isinstance(block, TextBlock)
        text = block_text(block)
        phrase_words = [matching_words(pair) for pair in block.phrases]
        block_words = [w for phrase in phrase_words for w in phrase]
        skeletons = phrase_skeletons(block)
        evidence: list[str] = []
        kind = "existing"
        choice = self.equivalents.choice(leaf, block_words)

        def find(pw: list[list[str]]) -> Resolution:
            """The text the block (or its first phrases, ``pw``) is."""
            bw = [w for phrase in pw for w in phrase]
            if choice is not None:
                # Chosen: the text is that one. It is cut only where another part of it opens.
                found = (resolve({choice.urn}, pw, self.index, cut_at_end=False)
                         if choice.urn in self.index.incipit_of and not choice.ends else Resolution(None, []))
                if found.urn is None:
                    # (A choice that names its last words is the text to them, its parts and all:
                    # the half Kaddish is not cut where its response opens.)
                    found = Resolution(choice.urn, [])
                found.evidence.insert(0, "chosen in equivalents.yaml" + (f": {choice.note}" if choice.note else ""))
                end = choice.end(pw)
                if end is not None and (found.split_at is None or end < found.split_at):
                    # The words the text ends with, and more after them (the day's verses after
                    # the Selichot's Vayaavor, printed without a bold opening): it ends there.
                    found.split_at = end
                    found.evidence.append(f"cut before phrase {end + 1}, after the words it ends with")
                return found
            context = self.sibling(leaf, blocks, i, bw, pw)
            if context is not None:
                return context
            short_key = skeleton(" ".join(plain_text(pair.he) for pair in block.phrases[:len(pw)]))
            if len(bw) < SHORT_INCIPIT_WORDS and short_key in self.short_printed:
                # Too short for the incipit index: a repeat is found by its words alone.
                return Resolution(self.short_printed[short_key], ["the same words as an earlier text"])
            found = resolve(lookup(self.own, bw, confirm=False), pw, self.own)
            if found.urn is None:
                found = resolve(lookup(self.index, bw), pw, self.index)
            return found

        resolution = find(phrase_words)
        cut = resolution.split_at
        # A choice that names its last words ends there, and no text it holds before them ends
        # it first (the full Kaddish's הוּא יַעֲשֶׂה שָׁלוֹם, a text of its own in Birnbaum).
        # A text this volume printed before is found where the block runs on into it, too
        # (the Selichot's עֲשֵׂה עִמָּנוּ after a selichah).
        later = (None if choice is not None and choice.ends
                 else later_text(phrase_words, resolution.urn, self.index, before=cut)
                 or later_text(phrase_words, resolution.urn, self.own, before=cut))
        if choice is None or not choice.ends:
            # A text chosen whole by its last words, which the block runs on into (Ashrei, then
            # the half Kaddish, whose Sefard words do not agree closely with Birnbaum's).
            chosen_later = self.later_choice(leaf, phrase_words, before=later[0] if later else cut)
            if chosen_later is not None:
                later = chosen_later
        if later is not None:
            # The block runs on into another text: what it is, it is up to there.
            at, found_text = later
            resolution = find(phrase_words[:at])
            cut = resolution.split_at if resolution.split_at is not None else at
            resolution.evidence.append(f"cut before phrase {at + 1}, where {found_text} opens")
        urn = resolution.urn
        evidence.extend(resolution.evidence)
        if choice is not None and urn is not None and urn not in self.printed:
            self.chosen.add(urn)
        if urn is not None and urn in self.printed and not same_blessing(
                block_words, words(block_text(self.printed[urn].block))):
            evidence.append(f"a blessing other than {urn}, whose formula it shares")
            self.candidate_cut = None
            urn = self.another_candidate(block_words, phrase_words, evidence)
            cut = self.candidate_cut
        if urn is not None and urn in self.printed:
            earlier = self.printed[urn]
            earlier_skeletons = phrase_skeletons(earlier.block)
            # Where each printing of the text ends in the other, matching mostly-same phrases.
            length = repeat_length(skeletons, earlier_skeletons, VARIANT_COVERAGE, insertions=True,
                                   introduced=introduced_phrases(block))
            earlier_length = repeat_length(earlier_skeletons, skeletons, VARIANT_COVERAGE)
            regrouped = regrouped_length(skeletons, earlier_skeletons)
            if (regrouped is not None and skeletons[:regrouped] != earlier_skeletons
                    and not (length is not None and skeletons[:length] == earlier_skeletons)):
                # The same words, lined otherwise (a paragraph where the first printing went
                # phrase by phrase): the same text.
                kind = "repeat"
                cut = regrouped if regrouped < len(skeletons) else None
                evidence.append("the same words as its first printing in this volume, lined otherwise; "
                                "transcluded")
            elif (earlier_length is not None and earlier_length < len(earlier_skeletons)
                    and skeletons == earlier_skeletons[:earlier_length] and urn not in self.chosen
                    and earlier_length not in introduced_phrases(earlier.block)):
                # (Not where a rubric introduces what follows in the first printing: that is a
                # passage inside the text -- the prayer for sustenance in שמע קולנו -- not its end.)
                # The first printing ran on past this text: cut it where this one ends.
                self.cut_earlier(urn, earlier_length)
                kind, cut = "repeat", None
                evidence.append("the same words as its first printing in this volume, which ran on past "
                                "them and is cut where this one ends; transcluded")
            elif (choice is not None and length is not None and length < len(skeletons) and cut is None
                  and not self.names_text([w for p in phrase_words[length:] for w in p])):
                # Chosen as the whole text: a shorter first printing (the Shema's first verse,
                # in the morning supplications) does not cut it, unless what follows is another
                # text. Its further words are its own.
                kind = "variant"
                evidence.append("its first printing in this volume, and more: a variant of it")
            elif (length is not None and skeletons[:length] == earlier_skeletons
                  and length < len(skeletons) and continues_closing(phrase_words[length:])):
                # The first printing's words and a closing that goes on ("... and Yom Tov"):
                # the same blessing, its further words its own.
                kind = "variant"
                evidence.append("its first printing in this volume, its closing going on: a variant of it")
            elif length is not None and skeletons[:length] == earlier_skeletons:
                kind = "repeat"
                cut = length if length < len(skeletons) else None
                evidence.append("the same words as its first printing in this volume, transcluded")
                if cut is not None:
                    evidence.append(f"cut before phrase {cut + 1}, where the first printing ends")
            elif length is not None:
                # Mostly the same text, with words of its own -- added, left out or worded
                # otherwise: the text's URN, its own words a variant of it, conditional where
                # the text is printed.
                kind = "variant"
                end = cut if cut is not None and cut > length else len(skeletons)
                tail = [w for p in phrase_words[length:end] for w in p]
                if length >= len(skeletons) or continues_closing(phrase_words[length:]):
                    cut = None
                elif len(tail) <= CONTINUED_CLOSING_WORDS and not self.names_text(tail):
                    # A few last words lined otherwise than the first printing's (דאמירן
                    # בעלמא, then ואמרו אמן): the variant's own, not a text of their own.
                    cut = end if end < len(skeletons) else None
                else:
                    cut = length
                evidence.append("the text of its first printing in this volume, with words of its own: "
                                "a variant of it")
            elif choice is not None:
                # Chosen: the same text, however much its words differ from the first printing.
                kind = "variant"
                evidence.append("differs from its first printing in this volume: a variant of it")
            elif opening_agreement_words(block_words, words(block_text(earlier.block))) >= SECOND_CHOICE:
                # Worded otherwise -- another rite's or another occasion's words -- but opening
                # as the first printing does: the same text.
                kind = "variant"
                evidence.append("worded otherwise than its first printing in this volume, which it opens "
                                "like: a variant of it")
            else:
                evidence.append(f"differs from the first printing of {urn} in this volume")
                first = self.index.first_part(urn)
                if first != urn and first not in self.printed and first in self.index.incipit_of:
                    # The block is the part the text opens with, not the whole text printed
                    # before (Retzeh alone, where the morning Amidah printed all of its Avodah).
                    part = resolve({first}, phrase_words, self.index)
                    urn, cut = part.urn or first, part.split_at
                    evidence.append(f"the part {first.rsplit(':', 1)[-1]} it opens with")
                else:
                    self.candidate_cut = None
                    urn = self.another_candidate(block_words, phrase_words, evidence)
                    cut = self.candidate_cut
        if cut is not None:
            block = self.cut(leaf, blocks, i, cut)
            text = block_text(block)
            skeletons = phrase_skeletons(block)
            key = self.key(leaf, block)
            record = self.records.get(key)
            if record is not None and record.as_of == block_hash(block) and record.urn == urn:
                self.keep(record, leaf, blocks, block)
                return
        if urn is None:
            # The book numbers it: its heading, or the rubric just before it, is its number.
            numbered = (block.head is not None and is_numbered(block.head.he)) or (
                i > 0 and isinstance(blocks[i - 1], Rubric)
                and any(is_numbered(pair.he) for pair in blocks[i - 1].pairs))
            known = self.poem_worded_otherwise(block_words) if numbered else None
            if known is not None:
                urn = known
                evidence.append(f"agrees with {known}, worded otherwise: the same poem")
            else:
                urn = mint(text, self.taken, self.spellings,
                           self.numbered_namespace if numbered else NEW_NAMESPACE)
                kind = "new"
        elif (kind == "existing" and urn not in self.index.incipit_of and urn not in self.registered
              and not urn.startswith(TEXT_PREFIX + "bible:")):
            # A name chosen for a text the collection does not hold yet. Scripture is named by
            # its place, not chosen (a run of verses, ``bible:proverbs/31/10-31``).
            kind = "new"
        self.taken.add(urn)
        phrases = None
        variant_name = None
        parts = None
        if kind == "variant":
            phrases = self.variant_numbers(urn, skeletons)
            variant_name = self.variant_name(urn, leaf, block)
            parts = self.inserted_texts(block, phrases, evidence) or None
        elif kind != "repeat":
            phrases = self.phrase_numbers(urn, skeletons, evidence)
            self.remember(urn, leaf, blocks, block, phrases)
        self.done.add(id(block))
        self.save(TextRecord(work=self.work_key, leaf=leaf, block=block.first_index, urn=urn, kind=kind,
                             incipit=" ".join(text.split()[:INCIPIT_WORDS]), as_of=block_hash(block),
                             evidence=evidence, phrases=phrases, variant=variant_name, parts=parts),
                  lapsed=record)

    def names_text(self, block_words: list[str]) -> bool:
        """Whether the collection names a text (not scripture) that opens with these words, by
        any of its keys."""
        found = set(lookup(self.index, block_words))
        found |= self.index.by_incipit.get(tuple(block_words[:SHORT_INCIPIT_WORDS]), set())
        return any(not u[len(TEXT_PREFIX):].startswith("bible:") for u in found)

    def poem_worded_otherwise(self, block_words: list[str]) -> str | None:
        """The collection's poem a numbered selichah is, where another rite words its opening
        otherwise (Nusach Lita's אָדוֹן דִּין אִם יְדֻקְדַּק, Asher's אִם יִדַּקֵּן): the whole poem
        that agrees best over its collected opening, its address apart, if at least as well as
        a stanza must (``STANZA_AGREEMENT``)."""
        for formula in ADDRESS_FORMULAS:
            if tuple(block_words[:len(formula)]) == formula:
                block_words = block_words[len(formula):]
        poem = TEXT_PREFIX + "poem:"
        best = max(((opening_agreement(u, block_words, self.index), u) for u in self.index.incipit_of
                    if u.startswith(poem) and not _is_stanza(u)
                    and len(self.index.incipit_of[u]) >= INCIPIT_WORDS), default=None)
        return best[1] if best is not None and best[0] >= STANZA_AGREEMENT else None

    def sibling(self, leaf: str, blocks: list[Item], i: int, block_words: list[str],
                phrase_words: list[list[str]]) -> Resolution | None:
        """The next part of the text the block before it (rubrics apart) is a part of, when the
        block opens like one part of it: the Kedushah's קדוש קדוש קדוש is Birnbaum's
        ``amidah/qedushah/qadosh`` there, not Yotzer's."""
        k = i - 1
        while k >= 0 and isinstance(blocks[k], Rubric):
            k -= 1
        if k < 0 or not isinstance(blocks[k], TextBlock):
            return None
        previous = self.outcome.records.get(self.key(leaf, blocks[k]))
        if previous is None or previous.urn.startswith(TEXT_PREFIX + "bible:"):
            return None
        up = parent(previous.urn)
        if not up:
            return None
        # Among the texts the block's own keys find (a blessing's only past its formula, which
        # finds every blessing), the one that is a part of the same text.
        block_keys = keys(block_words)
        if tuple(block_words[:len(BLESSING_FORMULA)]) == BLESSING_FORMULA:
            block_keys = block_keys[:-1]
        candidates: set[str] = set()
        for key in block_keys:
            if len(key) >= SHORT_INCIPIT_WORDS:
                candidates |= self.index.by_incipit.get(key, set())
        if len(block_words) >= SHORT_INCIPIT_WORDS and tuple(block_words[:len(BLESSING_FORMULA)]) != BLESSING_FORMULA:
            candidates |= self.index.by_incipit.get(tuple(block_words[:SHORT_INCIPIT_WORDS]), set())
        found = sorted(u for u in candidates if parent(u) == up and u != previous.urn)
        if not found and _is_stanza(previous.urn):
            # The next stanza, worded otherwise than the collection's: the stanza it agrees with best.
            near = max(((opening_agreement(u, block_words, self.index), u)
                        for u in self.index.children.get(up, []) if _is_stanza(u) and u != previous.urn),
                       default=None)
            if near is not None and near[0] >= STANZA_AGREEMENT:
                resolution = resolve({near[1]}, phrase_words, self.index)
                if resolution.urn is None:
                    resolution = Resolution(near[1], [f"opens like {near[1]}, worded otherwise"])
                resolution.evidence.append(f"the next stanza of {up}, as the text before it is")
                return resolution
        if len(found) != 1:
            return None
        # A part of the same text, but not one the block agrees with less than another text.
        best = max((opening_agreement(u, block_words, self.index) for u in candidates), default=0.0)
        if opening_agreement(found[0], block_words, self.index) < best:
            return None
        resolution = resolve({found[0]}, phrase_words, self.index)
        if resolution.urn is None:
            return None
        resolution.evidence.append(f"the next part of {up}, as the text before it is")
        return resolution

    def inserted_texts(self, block: TextBlock, phrases: list[int], evidence: list[str]) -> dict[str, str]:
        """The variant's own passages that are texts the collection names, and not printed
        elsewhere in this project: first phrase number -> URN."""
        printing = self.printed_numbers
        found: dict[str, str] = {}
        run: list[int] = []

        def close() -> None:
            # The passage, text by text: a match that is one part of a text (the passage lacking
            # the rest of it) is that part, and the passage goes on from where another opens.
            start = 0
            while len(run) - start >= 2:
                phrase_words = [words(plain_text(block.phrases[i].he)) for i in run[start:]]
                run_words = [w for phrase in phrase_words for w in phrase]
                resolution = resolve(lookup(self.index, run_words), phrase_words, self.index)
                urn = resolution.urn
                if not urn or urn in self.printed or urn in self.parts_used:
                    break
                self.parts_used.add(urn)
                self.taken.add(urn)
                found[str(phrases[run[start]])] = urn
                evidence.append(f"its own words from phrase {phrases[run[start]]} are {urn}")
                if resolution.split_at is None:
                    break
                start += resolution.split_at
            run.clear()

        for i, number in enumerate(phrases):
            if number in printing:
                close()
            else:
                run.append(i)
        close()
        return found

    @property
    def printed_numbers(self) -> set[int]:
        return self._printed_numbers

    def variant_numbers(self, urn: str, skeletons: list[str]) -> list[int]:
        """A variant's phrase numbers: the first printing's where the phrase has the same words,
        and new ones, after every number the text has used, for its own words."""
        printing = self.printed[urn]
        base = self.outcome.records[self.key(printing.leaf, printing.block)]
        base_numbers = base.phrases or list(range(1, len(printing.block.phrases) + 1))
        recorded = dict(zip(base_numbers, phrase_skeletons(printing.block)))
        self._printed_numbers = set(base_numbers)
        mapped = map_phrases(skeletons, recorded)
        top = max(base_numbers)
        next_number = self.numbers_used.get(urn, top) + 1
        numbers: list[int] = []
        for number, words_here in zip(mapped, skeletons):
            # A phrase worded otherwise than the first printing's is a phrase of its own.
            if number in recorded and recorded[number] == words_here:
                numbers.append(number)
            else:
                numbers.append(next_number)
                next_number += 1
        self.note_numbers(urn, numbers)
        return numbers

    def another_candidate(self, block_words: list[str], phrase_words: list[list[str]],
                          evidence: list[str]) -> str | None:
        """A text the block opens like that this volume has not printed yet, or None."""
        candidates: set[str] = set()
        for key in keys(block_words):
            candidates |= self.index.by_incipit.get(key, set())
        # A second choice must agree more closely than a first, and a blessing must be the same
        # blessing past its formulas: the formula alone finds every blessing.
        candidates = {u for u in candidates - set(self.printed)
                      if opening_agreement(u, block_words, self.index) >= SECOND_CHOICE
                      and same_blessing(block_words, list(self.index.incipit_of.get(u, ())))}
        for urn in sorted(candidates, key=lambda u: (-opening_agreement(u, block_words, self.index), u)):
            resolution = resolve({urn}, phrase_words, self.index)
            if resolution.urn is not None and resolution.urn not in self.printed:
                evidence.append(f"took {resolution.urn}, which opens alike and is not printed earlier")
                self.candidate_cut = resolution.split_at
                return resolution.urn
        return None

    def phrase_numbers(self, urn: str, skeletons: list[str], evidence: list[str]) -> list[int] | None:
        from opensiddur.importer.sefaria.phrases import text_path

        numbers = map_phrases(skeletons, self.recorded_phrases.get(text_path(urn, self.clashes), {}))
        if numbers == list(range(1, len(numbers) + 1)):
            return None
        evidence.append("phrase numbers follow the phrases an earlier volume named")
        return numbers

    def cut_earlier(self, urn: str, length: int) -> None:
        """Cut the first printing of ``urn`` after ``length`` phrases, and decide the rest."""
        printing = self.printed[urn]
        i = printing.blocks.index(printing.block)
        first = self.cut(printing.leaf, printing.blocks, i, length)
        previous = self.outcome.records[self.key(printing.leaf, first)]
        self.save(TextRecord(
            work=self.work_key, leaf=printing.leaf, block=first.first_index, urn=urn, kind=previous.kind,
            incipit=previous.incipit, as_of=block_hash(first),
            evidence=previous.evidence + [f"cut before phrase {length + 1}, where a later printing ends"],
            phrases=previous.phrases[:length] if previous.phrases else None))
        printing.block = first
        self.decide_anew(printing.leaf, printing.blocks, i + 1, self.records.get(
            self.key(printing.leaf, printing.blocks[i + 1])))
        # Deciding the rest may cut it again, in a leaf already passed: decide every piece.
        j = i + 2
        while j < len(printing.blocks):
            piece = printing.blocks[j]
            if isinstance(piece, TextBlock) and id(piece) not in self.done:
                self.decide_anew(printing.leaf, printing.blocks, j,
                                 self.records.get(self.key(printing.leaf, piece)))
            j += 1


def verse_length(urn: str, index: IncipitIndex) -> int | None:
    """A verse's length in words, when the index holds it whole (shorter than its collected
    opening)."""
    if urn not in index.incipit_of:
        return None
    opening = index.own_opening(urn)
    return len(opening) if len(opening) < COLLECTED_WORDS else None


def scripture_verses(block: TextBlock, index: IncipitIndex) -> dict[int, str]:
    """The verses of scripture a text quotes, by the phrase each opens: phrase position ->
    ``bible:`` verse URN. A verse is found at a phrase that opens like it (six words, confirmed
    over its collected opening, as :func:`lookup` confirms); a half-verse found first is its
    verse when it is the first half."""
    phrase_words = [words(plain_text(pair.he)) for pair in block.phrases]
    found: dict[int, str] = {}
    for start in range(len(phrase_words)):
        following = [w for phrase in phrase_words[start:] for w in phrase]
        if len(following) < INCIPIT_WORDS:
            break
        verses = set()
        for urn in index.by_incipit.get(tuple(following[:INCIPIT_WORDS]), ()):
            namespace, path = _namespace_and_path(urn)
            if namespace != "bible" or len(path) < 3 or not confirmed(urn, following, index):
                continue
            if len(path) == 4:
                if path[3] != "a":
                    continue
                urn = urn.rsplit("/", 1)[0]
            verses.add(urn)
        if len(verses) == 1:
            found[start] = verses.pop()
    return found
