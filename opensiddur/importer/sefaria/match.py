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
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from opensiddur.common.constants import REPO_ROOT
from opensiddur.common.urn_registry import REGISTRY_DIRECTORY
from opensiddur.common.validate_names import Spellings, load_spellings
from opensiddur.importer.sefaria.blocks import Item, TextBlock, split_block
from opensiddur.importer.sefaria.markup import plain_text
from opensiddur.importer.sefaria.phrases import SAME_PHRASE, map_phrases, similarity, skeleton
from opensiddur.importer.util.incipit import (
    BLESSING_FORMULA,
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
#: Words of a new text's incipit its name starts from, and the most it grows to.
MIN_NAME_WORDS, MAX_NAME_WORDS = 2, 8
NEW_NAMESPACE = "prayer"


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
    #: earlier volume named.
    phrases: list[int] | None = None

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


def block_hash(block: TextBlock) -> str:
    return hashlib.sha256(skeleton(block_text(block)).encode("utf-8")).hexdigest()[:16]


def phrase_skeletons(block: TextBlock) -> list[str]:
    return [skeleton(plain_text(pair.he)) for pair in block.phrases]


def _namespace_and_path(urn: str) -> tuple[str, list[str]]:
    namespace, _, path = urn[len(TEXT_PREFIX):].partition(":")
    return namespace, path.split("/")


def excluded_projects(project_directory: Path) -> set[Path]:
    return projects_with_source(project_directory, EXCLUDED_SOURCES)


def lookup(index: IncipitIndex, block_words: list[str]) -> set[str]:
    """The index's candidates for a block. A blessing is found only by the words after its
    formula: the formula itself opens every blessing, and finds them all."""
    n = len(BLESSING_FORMULA)
    if tuple(block_words[:n]) != BLESSING_FORMULA:
        return index.lookup(block_words)
    for key in keys(block_words)[:-1]:
        if len(key) >= SHORT_INCIPIT_WORDS:
            found = index.by_incipit.get(key, set())
            if found:
                return index._longest_opening(found, block_words)
    return set()


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


#: How much of a candidate's collected opening (up to 16 words) the block must agree with,
#: beyond the six-word key that found it: many texts open with the same few words ("יהי רצון
#: מלפניך ה׳ אלהי ואלהי אבותי") and go on differently.
CONFIRM_OPENING = 0.6


def confirmed(urn: str, block_words: list[str], index: IncipitIndex) -> bool:
    opening = list(index.incipit_of.get(urn, ()))
    if len(opening) <= INCIPIT_WORDS or len(block_words) <= INCIPIT_WORDS:
        return True
    ours = block_words[:len(opening)]
    return SequenceMatcher(None, opening, ours, autojunk=False).ratio() >= CONFIRM_OPENING


def resolve(candidates: set[str], phrase_words: list[list[str]], index: IncipitIndex) -> Resolution:
    """The one text a block is, from the index's candidates.

    A match that opens a text -- its parent is encoded, and opens with the same words -- moves
    up to the whole text when the block runs on into another part of it. A match that is a later part of a text stays that part, and
    the block is cut where another part of the text opens (:attr:`Resolution.split_at`). Scripture moves up
    no further than a chapter and is never cut: a block that opens a chapter at its first verse
    is that chapter, and one that opens mid-chapter is liturgy quoting it.
    """
    evidence: list[str] = []
    block_words = [w for phrase in phrase_words for w in phrase]
    unconfirmed = sorted(c for c in candidates if not confirmed(c, block_words, index))
    if unconfirmed:
        evidence.append(f"opens like {', '.join(unconfirmed[:3])} but goes on differently")
        candidates = candidates - set(unconfirmed)
    if not candidates:
        return Resolution(None, evidence)
    liturgical = sorted(c for c in candidates if not c.startswith(TEXT_PREFIX + "bible:"))
    pool = liturgical or sorted(candidates)
    urn = pool[0]
    if len(pool) > 1:
        evidence.append(f"the opening matches {len(pool)} texts ({', '.join(pool[:4])}); took the first")
    joined = "".join(w for phrase in phrase_words for w in phrase)

    def other_parts(u: str) -> list[str]:
        # The index keeps parts in the order of the files they were found in, which is not
        # always the order of the text, so every other part counts.
        return [s for s in index.children.get(parent(u), []) if s != u]

    def opens_parent(u: str) -> bool:
        up = parent(u)
        return up in index.incipit_of and index.incipit_of[up][:INCIPIT_WORDS] == index.incipit_of[u][:INCIPIT_WORDS]

    while parent(urn):
        namespace, path = _namespace_and_path(urn)
        if namespace == "bible" and len(path) <= 2:
            break  # never above a chapter
        if not opens_parent(urn):
            break  # a later part, or a part of a text not encoded whole: cut, below
        if not any("".join(index.incipit_of[s][:INCIPIT_WORDS]) in joined for s in other_parts(urn)):
            break
        evidence.append(f"runs on past {urn.rsplit('/', 1)[-1]} into the rest of {parent(urn)}")
        urn = parent(urn)
    namespace, path = _namespace_and_path(urn)
    if namespace == "bible":
        if len(path) >= 3:
            evidence.append(f"opens with the verse {urn}; a liturgical text, not that verse")
            return Resolution(None, evidence)
        verses = index.children.get(urn, [])
        first_verse = index.incipit_of.get(verses[0], ())[:INCIPIT_WORDS] if verses else ()
        if not first_verse or tuple(block_words[:len(first_verse)]) != first_verse:
            evidence.append(f"quotes {urn} but does not open at its first verse")
            return Resolution(None, evidence)
        evidence.insert(0, f"opens like {urn}")
        return Resolution(urn, evidence)
    evidence.insert(0, f"opens like {urn}")
    split_at = None
    for sibling in other_parts(urn) if parent(urn) else []:
        incipit = index.incipit_of[sibling][:INCIPIT_WORDS]
        for start in range(1, len(phrase_words)):
            if _opens_at(phrase_words, start, incipit):
                if split_at is None or start < split_at:
                    split_at = start
                break
    if split_at is not None:
        evidence.append(f"cut before phrase {split_at + 1}, where the next part of {parent(urn)} opens")
    return Resolution(urn, evidence, split_at)


#: Share of an earlier printing's phrases a later block must print, and share of the block's
#: phrases (up to where the earlier printing ends) that must be the earlier printing's, for the
#: block to be that text again.
REPEAT_COVERAGE = 0.75


def repeat_length(block_phrases: list[str], earlier: list[str]) -> int | None:
    """How many of a block's phrases are a later printing of ``earlier`` (phrase skeletons),
    or None when the block is not that text. Phrases are paired as :func:`map_phrases` pairs
    them, so a phrase that is mostly the same counts."""
    if not earlier or not block_phrases:
        return None
    numbers = map_phrases(block_phrases, {i + 1: s for i, s in enumerate(earlier)})
    matched = [i for i, n in enumerate(numbers) if n <= len(earlier)]
    if not matched:
        return None
    length = matched[-1] + 1
    if (len(matched) / len(earlier) >= REPEAT_COVERAGE
            and len(matched) / length >= REPEAT_COVERAGE):
        return length
    return None


def mint(text: str, taken: set[str], spellings: Spellings) -> str:
    """A new ``prayer:`` URN from a text's incipit. A blessing is named from the words after
    its formula, which every blessing shares."""
    # Words as the index counts them: a maqaf separates words, punctuation alone is none.
    hebrew = [token for token in re.split(r"[\s\u05be]+", text) if words(token)]
    if tuple(words(" ".join(hebrew[:6]))) == BLESSING_FORMULA:
        hebrew = hebrew[6:] or hebrew
        if tuple(words(" ".join(hebrew[:4]))) == MITZVAH_FORMULA:
            hebrew = hebrew[4:] or hebrew
    for count in range(MIN_NAME_WORDS, MAX_NAME_WORDS + 1):
        name = name_from_hebrew(" ".join(hebrew), count, spellings)
        if not name:
            break
        urn = f"{TEXT_PREFIX}{NEW_NAMESPACE}:{name}"
        if urn not in taken:
            return urn
    base = f"{TEXT_PREFIX}{NEW_NAMESPACE}:{name_from_hebrew(' '.join(hebrew), MAX_NAME_WORDS, spellings) or 'text'}"
    n = 2
    while f"{base}_{n}" in taken:
        n += 1
    return f"{base}_{n}"


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
) -> Decisions:
    """Decide the URN of every block of ``work_key`` that has no current record.

    ``leaves`` is each leaf's path with its items (``blocks.divide``), in book order; a text
    found to run on past the text it opens is cut, and the leaf's list is changed in place to
    hold both parts.
    ``taken`` is every URN already in use (registry and records); minted URNs are added to it.
    ``recorded_phrases`` are the phrases other Metsudah volumes have named
    (``phrases.recorded_phrases``).
    """
    from opensiddur.importer.sefaria.phrases import text_path

    spellings = spellings or load_spellings()
    recorded_phrases = recorded_phrases or {}
    outcome = Decisions(dict(records))
    #: the texts this work printed earlier: URN -> the skeletons of its first printing's phrases
    printed: dict[str, list[str]] = {}
    #: texts too short for the incipit index: their words -> URN
    short_printed: dict[str, str] = {}
    own = IncipitIndex()
    stale_keys = {key for key in records if key[0] == work_key}
    for leaf_path, blocks in leaves:
        i = 0
        while i < len(blocks):
            block = blocks[i]
            if not isinstance(block, TextBlock):
                i += 1
                continue
            key = (work_key, leaf_path, block.first_index)
            text = block_text(block)
            this_short = skeleton(text)
            phrase_words = [words(plain_text(pair.he)) for pair in block.phrases]
            block_words = [w for phrase in phrase_words for w in phrase]
            skeletons = phrase_skeletons(block)
            record = records.get(key)
            if record is not None and record.as_of == block_hash(block):
                stale_keys.discard(key)
                if record.kind != "repeat":
                    printed.setdefault(record.urn, skeletons)
                    own.add(record.urn, block_words)
                    short_printed.setdefault(skeleton(text), record.urn)
                i += 1
                continue
            if record is not None and record.kind != "repeat" and record.urn not in printed and (
                    similarity(skeleton(record.incipit), skeleton(" ".join(text.split()[:INCIPIT_WORDS])))
                    >= SAME_PHRASE):
                # The words changed, but it is still the text it was: it keeps its URN, and its
                # phrases their numbers.
                stale_keys.discard(key)
                outcome.lapsed.append(record)
                kept = TextRecord(
                    work=work_key, leaf=leaf_path, block=block.first_index, urn=record.urn,
                    kind=record.kind, incipit=" ".join(text.split()[:INCIPIT_WORDS]),
                    as_of=block_hash(block),
                    evidence=record.evidence + ["the words changed; the URN of the earlier decision is kept"],
                    phrases=record.phrases if record.phrases and len(record.phrases) == len(skeletons) else None)
                outcome.records[key] = kept
                outcome.decided.append(kept)
                printed.setdefault(kept.urn, skeletons)
                own.add(kept.urn, block_words)
                i += 1
                continue
            evidence: list[str] = []
            kind = "existing"
            if len(block_words) < SHORT_INCIPIT_WORDS and this_short in short_printed:
                # Too short for the incipit index: a repeat is found by its words alone.
                resolution = Resolution(short_printed[this_short], ["the same words as an earlier text"])
            else:
                resolution = resolve(lookup(own, block_words), phrase_words, own)
            if resolution.urn is None:
                resolution = resolve(lookup(index, block_words), phrase_words, index)
            urn = resolution.urn
            evidence.extend(resolution.evidence)
            cut = resolution.split_at
            if urn is not None and urn in printed:
                length = repeat_length(skeletons, printed[urn])
                if length is not None:
                    kind = "repeat"
                    cut = length if length < len(skeletons) else None
                    evidence.append("the same text as its first printing in this volume, transcluded")
                    if cut is not None:
                        evidence.append(f"cut before phrase {cut + 1}, where the first printing ends")
                else:
                    evidence.append(f"differs from the first printing of {urn} in this volume")
                    urn, cut = None, None
            if cut is not None:
                block, rest = split_block(block, cut)
                blocks[i:i + 1] = [block, rest]
                key = (work_key, leaf_path, block.first_index)
                text = block_text(block)
                block_words = words(text)
                skeletons = phrase_skeletons(block)
            record = records.get(key)
            if record is not None and record.as_of == block_hash(block):
                # The part before the cut was recorded already.
                stale_keys.discard(key)
                if record.kind != "repeat":
                    printed.setdefault(record.urn, skeletons)
                    own.add(record.urn, block_words)
                    short_printed.setdefault(skeleton(text), record.urn)
                i += 1
                continue
            if record is not None:
                outcome.lapsed.append(record)
            stale_keys.discard(key)
            if urn is None:
                urn = mint(text, taken, spellings)
                kind = "new"
            taken.add(urn)
            phrases = None
            if kind != "repeat":
                printed.setdefault(urn, skeletons)
                own.add(urn, block_words)
                short_printed.setdefault(skeleton(text), urn)
                numbers = map_phrases(skeletons, recorded_phrases.get(text_path(urn), {}))
                if numbers != list(range(1, len(numbers) + 1)):
                    phrases = numbers
                    evidence.append("phrase numbers follow the phrases an earlier volume named")
            new = TextRecord(work=work_key, leaf=leaf_path, block=block.first_index, urn=urn, kind=kind,
                             incipit=" ".join(text.split()[:INCIPIT_WORDS]), as_of=block_hash(block),
                             evidence=evidence, phrases=phrases)
            outcome.records[key] = new
            outcome.decided.append(new)
            i += 1
    for key in sorted(stale_keys):
        outcome.lapsed.append(outcome.records.pop(key))
    return outcome
