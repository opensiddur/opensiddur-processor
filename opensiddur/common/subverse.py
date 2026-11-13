"""Sub-verse milestones: the accentual half-verse, and named parts of a verse.

A URN reaches no further than a whole verse unless something inside the verse carries one.
Two milestone units divide a verse, and both hang a URN one component below the verse's:

``half-verse``
    The accentual division, at the etnachta. `a` runs from the start of the verse to the
    accent, `b` from there to the end. Derived from the text itself, so it can be placed
    everywhere without anyone declaring anything.

``verse-part``
    A break the accents do not make — the Thirteen Attributes open at the second יהוה of
    Exodus 34:6, three words before its etnachta, and close one word past the etnachta of
    34:7. These cannot be derived, so they are declared in `VERSE_PARTS` and named by their
    transliterated incipit, the same way JLPTEI-3.md already names divisions of a poem.

The two divisions cut at different points and are separate unit-spaces: neither ends the
other's scope (see `UNIT_CONTAINED_BY` in opensiddur/exporter/refdb.py).

Both are inserted by a pass over converted TEI rather than by each importer's XSLT, because
Miqra al pi ha-Masorah and the WLC emit the same shape by the time they are TEI — running
text with inline elements in it — while their sources do not resemble each other at all.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

TEI_NS = "http://www.tei-c.org/ns/1.0"
JLPTEI_NS = "http://jewishliturgy.org/ns/jlptei/2"

#: U+0591 HEBREW ACCENT ETNAHTA, the main disjunctive of the twenty-one books: the accent
#: that divides a verse in two, and the point a citation means by "2:2b".
ETNAHTA = "֑"

#: U+05AB HEBREW ACCENT OLE. In Psalms, Proverbs and Job the primary division of a verse may
#: fall at ole-we-yored rather than at the etnachta, in which case the etnachta divides only
#: the second part. Rather than guess which of the two governs, verses carrying ole are left
#: undivided — see `_half_verse_boundary`.
OLE = "֫"

#: The three books read with the poetic accents.
POETIC_BOOKS = frozenset({"psalms", "proverbs", "job"})

#: U+05BE HEBREW PUNCTUATION MAQAF joins words into one accentual unit. It separates words
#: for the purpose of *matching* an incipit, but it is not a place a milestone may go: the
#: words it joins are read as one, and a break inside one is not expressible here.
MAQAF = "־"

#: U+05C0 HEBREW PUNCTUATION PASEQ separates. Miqra al pi ha-Masorah sets it tight against
#: the words on either side and the WLC sets it with spaces, so it has to be a token
#: separator in its own right or the two editions would tokenize differently.
PASEQ = "׀"

#: Milestone units that close a verse's scope, and so bound the text a sub-verse milestone
#: may be placed in. This is the containment table of opensiddur/exporter/refdb.py, reduced
#: to the two units that matter in a Tanakh file; the importers must not depend on the
#: exporter.
_VERSE_TERMINATING_UNITS = frozenset({"verse", "chapter"})


class UnplaceableVersePartError(ValueError):
    """A verse part that `VERSE_PARTS` declares could not be put anywhere in the text."""


@dataclass(frozen=True)
class Unplaceable:
    """A sub-verse boundary that was asked for and could not be put anywhere."""

    urn: str
    reason: str

    def __str__(self) -> str:
        return f"{self.urn}: {self.reason}"


#: Verse parts that liturgy needs and the accents do not give, by (book, chapter, verse).
#:
#: Each part is a name — used as the last component of its URN, so it may not contain '-',
#: which marks a range — and the incipit that locates it, per language. The incipit is
#: matched on consonants alone, so it is not disturbed by an edition's vowels or accents,
#: and it must begin at a word boundary. A language a verse declares nothing for simply gets
#: no parts, which is how translations carry none.
#:
#: A part's scope runs to the next sub-verse milestone or to the end of the verse, so a
#: passage that stops in the middle of a verse needs a part declared at the point the
#: *remainder* begins as well: `lo_yenakeh` exists to end `venakeh`.
VERSE_PARTS: dict[tuple[str, int, int], tuple[tuple[str, dict[str, str]], ...]] = {
    # Kiddush opens on the last two words of the sixth day rather than on the half-verse,
    # so that it does not begin with "and there was evening".
    ("genesis", 1, 31): (
        ("yom_hashishi", {"he": "יום הששי"}),
    ),
    # The Thirteen Attributes. They begin at the second יהוה — the first belongs to
    # "and the LORD passed by before him and proclaimed" — and end at ונקה, since
    # "he will by no means clear the guilty" is not among the attributes recited.
    # notzer_chesed bounds the prefix before venakeh, so an edition quoting both
    # clauses can mark each precisely rather than claiming the complete verse.
    ("exodus", 34, 6): (
        ("adonai_adonai", {"he": "יהוה יהוה אל"}),
    ),
    ("exodus", 34, 7): (
        ("notzer_chesed", {"he": "נצר חסד"}),
        ("venakeh", {"he": "ונקה"}),
        ("lo_yenakeh", {"he": "לא ינקה"}),
    ),
    # The scroll-lifting formula appends only the closing words of this verse.
    ("numbers", 9, 23): (
        ("al_pi", {"he": "על פי יהוה ביד משה"}),
    ),
    # Entrance prayers quote these clauses without the rest of the verse.
    ("psalms", 39, 13): (
        ("shimah", {"he": "שמעה תפלתי"}),
        ("ki_ger", {"he": "כי גר אנכי"}),
    ),
    # The qedushah divides the introductory call from the angels' response.
    ("isaiah", 6, 3): (
        ("veqara", {"he": "וקרא זה אל זה ואמר"}),
        ("qadosh", {"he": "קדוש קדוש קדוש"}),
    ),
}


def add_subverse_milestones(xml: str, *, language: str, project: str = "") -> str:
    """`xml` with both kinds of sub-verse milestone added to every verse that can take one.

    This is what an importer calls. It is applied to already-serialised TEI rather than
    written into each importer's XSLT because the two Hebrew editions produce the same shape
    once they are TEI — running text with elements through it — and nothing alike before
    that.

    It works on the text rather than on a parsed tree, and splices the milestones in, so that
    a file comes back byte-for-byte as it went in apart from what was added. Re-serialising
    instead would rewrite every file the WLC importer produces: Saxon sets each attribute on
    its own line and lxml does not, so a regeneration would bury the milestones in a whole-
    project reformat.

    Raises:
        UnplaceableVersePartError: if a part `VERSE_PARTS` declares for `language` is not
            where it says it is. A part that quietly failed to appear would leave its URN
            resolving to the whole verse, silently reading more than was asked for, which is
            the failure this whole mechanism exists to prevent. The halves are not checked
            this way: no one declares them individually, and a verse the accents do not
            divide simply has no halves.
    """
    xml, _ = insert_half_verses(xml, project=project)
    xml, unplaceable = insert_verse_parts(xml, language=language, project=project)
    if unplaceable:
        raise UnplaceableVersePartError(
            f"{project or 'project'}: declared verse parts not found in the text: "
            + "; ".join(str(item) for item in unplaceable)
        )

    return xml


def add_subverse_milestones_to_file(path, *, language: str, project: str = "") -> None:
    """`add_subverse_milestones`, applied to a file in place."""
    path = Path(path)
    path.write_text(
        add_subverse_milestones(
            path.read_text(encoding="utf-8"), language=language, project=project
        ),
        encoding="utf-8",
    )


def _consonants(text: str) -> str:
    """`text` reduced to its Hebrew consonants, dropping vowels, accents and punctuation.

    Comparing on consonants lets one declared incipit match every edition: the WLC and
    Miqra al pi ha-Masorah differ in vowels and accents constantly, and in the spelling of
    the divine name.
    """
    return "".join(c for c in unicodedata.normalize("NFD", text) if "א" <= c <= "ת")


# One item of XML markup, or the run of character data between two of them. Attribute values
# may legally contain '>', so the tag pattern steps over quoted values rather than stopping at
# the first '>'.
_MARKUP = re.compile(
    r"""
      <!--.*?-->
    | <\?.*?\?>
    | <!\[CDATA\[.*?\]\]>
    | <!DOCTYPE(?:[^<>\[]|\[.*?\])*>
    | <(?P<close>/?)(?P<name>[^\s/>]+)(?P<attrs>(?:"[^"]*"|'[^']*'|[^>"'])*)(?P<empty>/?)>
    """,
    re.S | re.X,
)

_ATTRIBUTE = re.compile(r"""([\w:.-]+)\s*=\s*("([^"]*)"|'([^']*)')""")

# The scanner works on source text, so it matches elements by the prefixed names both
# importers write. TEI_NS and JLPTEI_NS below are the namespaces those prefixes are bound to.
_CHOICE_TAG = "tei:choice"
_READ_TAG = "j:read"
_OPTION_TAG = "j:option"
_VERSE_MILESTONE_UNITS = _VERSE_TERMINATING_UNITS


def _attributes(attrs: str) -> dict[str, str]:
    return {m.group(1): m.group(3) if m.group(3) is not None else m.group(4)
            for m in _ATTRIBUTE.finditer(attrs)}


@dataclass
class _Run:
    """One run of character data in the source, and where it came from."""

    source: int      # offset of this run in the source text
    offset: int      # offset of this run within the verse's assembled text
    text: str
    # Where a boundary at this run's very start must go instead, when the run sits inside an
    # element that may not be split: the offset of that element's start tag. None otherwise.
    before: int | None = None
    splittable: bool = True


class _VerseText:
    """A verse's running text, assembled from the source, with a map back into it.

    The text of one verse is broken over elements — Miqra al pi ha-Masorah splits words, as in
    ``<tei:hi rend="large">נֹ</tei:hi>צֵר``, and drops anchors between them — and a verse may
    run across a paragraph boundary where a parashah break falls inside it. So it is read as
    one string and written back through the offsets each run came from.
    """

    def __init__(self, urn: str, opens_at: int, runs: list[_Run]):
        self.urn = urn
        self.opens_at = opens_at  # source offset just after the verse milestone
        self.runs = runs
        self.text = "".join(run.text for run in runs)
        self.has_variant_reading = False

    def tokens(self) -> list[tuple[int, str]]:
        """(offset, token) for each whitespace/paseq-delimited token, in reading order."""
        return [(m.start(), m.group()) for m in re.finditer(f"[^\\s{PASEQ}]+", self.text)]

    def source_offset(self, offset: int) -> int:
        """Where in the source a boundary at `offset` in the verse's text goes.

        Raises:
            ValueError: if the boundary falls somewhere no milestone may be placed.
        """
        run = self.runs[0] if self.runs else None
        for candidate in self.runs:
            if candidate.offset <= offset:
                run = candidate
            else:
                break
        if run is None:
            raise ValueError("the verse has no text to divide")

        local = offset - run.offset
        if run.splittable:
            return run.source + local
        if local == 0 and run.before is not None:
            # The point just before the element is the same point, and it is always available:
            # a ketiv/qere at the head of the second half of a verse arrives here.
            return run.before
        raise ValueError(
            "the boundary falls inside a choice, which is a single word or a single reading"
        )


def _choice_extent(xml: str, choice_start: int, after_open_tag: int) -> tuple[int, int, int]:
    """(end of the choice, start of its read text, end of its read text).

    A ketiv and a qere are two readings of one word, not two words: taking both would put the
    unpointed ketiv into the running text beside the qere, doubling the word and — since only
    the qere carries the accents — moving every boundary measured after it. The qere is what
    is read. A variant (`j:option`) has no one reading, so the first stands in; a verse that
    contains one is not divided at all (`_has_variant_reading`).
    """
    depth = 1
    keep: tuple[int, int] | None = None
    open_at: dict[str, int] = {}
    position = after_open_tag

    for match in _MARKUP.finditer(xml, after_open_tag):
        name = match.group("name")
        if name is None:  # comment, PI, CDATA
            continue
        if match.group("empty"):
            continue
        if not match.group("close"):
            depth += 1
            if keep is None and name in (_READ_TAG, _OPTION_TAG):
                open_at[name] = match.end()
        else:
            depth -= 1
            if depth == 0:
                position = match.start()
                break
            if keep is None and name in open_at:
                keep = (open_at[name], match.start())
                if name == _READ_TAG:
                    break

    end = position
    for match in _MARKUP.finditer(xml, position):
        if match.group("name") == _CHOICE_TAG and match.group("close"):
            end = match.end()
            break

    if keep is None:
        keep = (after_open_tag, position)
    return end, keep[0], keep[1]


def _verses(xml: str) -> list[_VerseText]:
    """Every verse in the document, with the text that belongs to it.

    A verse runs from its milestone to the next milestone that closes it — the next verse, or
    the next chapter. Only the milestones inside `tei:text` count: a header may quote a verse,
    and quoting one is not carrying it.
    """
    verses: list[_VerseText] = []
    current: _VerseText | None = None
    runs: list[_Run] = []
    urn = ""
    opens_at = 0
    length = 0
    in_text = False
    variant = False
    skip_until = 0
    choice: tuple[int, int, int] | None = None  # (choice start, keep start, keep end)
    position = 0

    def close():
        nonlocal current, runs, length, variant
        if urn:
            verse = _VerseText(urn, opens_at, runs)
            verse.has_variant_reading = variant
            verses.append(verse)
        runs, length, variant = [], 0, False

    for match in _MARKUP.finditer(xml):
        data_start, data_end = position, match.start()
        position = match.end()

        if urn and data_end > data_start:
            text = xml[data_start:data_end]
            keep = True
            before = None
            splittable = True
            if choice is not None:
                choice_start, keep_start, keep_end = choice
                keep = keep_start <= data_start < keep_end
                splittable = False
                before = choice_start if not runs or runs[-1].source < choice_start else None
            if keep:
                runs.append(_Run(source=data_start, offset=length, text=text,
                                 before=before, splittable=splittable))
                length += len(text)

        name = match.group("name")
        if name is None:
            continue

        if urn and choice is None and (name == "tei:lb" or
                                      (name == "tei:p" and match.group("close"))):
            # MAM serializes adjacent lines without literal whitespace. They
            # remain separate words; this synthetic separator has no output.
            runs.append(_Run(source=match.end(), offset=length, text=" "))
            length += 1

        if not match.group("close") and not match.group("empty"):
            if name == "tei:text":
                in_text = True
            elif name == _CHOICE_TAG and choice is None:
                end, keep_start, keep_end = _choice_extent(xml, match.start(), match.end())
                choice = (match.start(), keep_start, keep_end)
                skip_until = end
                if _OPTION_TAG in xml[match.end():end]:
                    variant = True
        elif match.group("close") and name == _CHOICE_TAG:
            choice = None

        if choice is not None and position >= skip_until:
            choice = None

        if not in_text or name != "tei:milestone":
            continue

        attributes = _attributes(match.group("attrs") or "")
        unit = attributes.get("unit")
        if unit not in _VERSE_MILESTONE_UNITS:
            continue
        close()
        if unit == "verse" and attributes.get("corresp"):
            urn, opens_at = attributes["corresp"], match.end()
        else:
            urn = ""

    if urn:
        data = xml[position:]
        if data:
            runs.append(_Run(source=position, offset=length, text=data))
        close()

    return verses


def _has_variant_reading(verse: _VerseText) -> bool:
    """Whether the verse's text depends on which variant a setting selects."""
    return verse.has_variant_reading


def _milestone_xml(unit: str, n: str, corresp: str) -> str:
    return f'<tei:milestone unit="{unit}" n="{n}" corresp="{corresp}"/>'


def _splice(xml: str, insertions: list[tuple[int, str]]) -> str:
    """`xml` with each string put at its offset, leaving everything else exactly as it was.

    Applied from the end backwards so that earlier offsets stay valid, and stably within one
    offset so that two milestones at the same point keep the order they were added in.
    """
    result = xml
    for source, text in sorted(insertions, key=lambda item: item[0], reverse=True):
        result = result[:source] + text + result[source:]
    return result


def _verse_urn_parts(corresp: str) -> tuple[str, int, int] | None:
    """(book, chapter, verse) from a verse milestone's URN, or None if it is not one."""
    match = re.fullmatch(r"urn:x-opensiddur:text:bible:([^/]+)/(\d+)/(\d+)", corresp or "")
    if match is None:
        return None
    return match.group(1), int(match.group(2)), int(match.group(3))


def _half_verse_boundary(verse: _VerseText, book: str) -> int | None:
    """The offset the second half of the verse begins at, or None if it has no halves.

    The boundary is the start of the word after the one carrying the etnachta, so the
    accent stays with the half it closes.
    """
    if _has_variant_reading(verse):
        # The two cantillations of the Decalogue put the etnachta in different places —
        # under ta'am elyon Exodus 20:2 divides after אלהיך, under ta'am tachton after
        # עבדים — so the verse has no one accentual division. A URN must denote the same
        # words wherever it is resolved, so it gets no halves rather than ambiguous ones.
        return None

    tokens = verse.tokens()
    accented = [i for i, (_, token) in enumerate(tokens) if ETNAHTA in token]
    if not accented:
        return None
    if book in POETIC_BOOKS and OLE in verse.text:
        # Ole-we-yored outranks the etnachta where it occurs, so in these verses the
        # etnachta is not the primary division and dividing there would misname the halves.
        return None
    index = accented[0]
    if index + 1 >= len(tokens):
        return None  # nothing after the accent, so there is no second half
    return tokens[index + 1][0]


def insert_half_verses(xml: str, *, project: str = "") -> tuple[str, list[Unplaceable]]:
    """`xml` with a `half-verse` milestone at the etnachta of every verse that has one.

    A verse with no etnachta, or one whose primary division the accents leave ambiguous,
    simply gets none: the halves are an addition to what a verse already says, so their
    absence costs nothing but the ability to address them.

    Returns:
        The new text, and the verses whose accentual boundary could not be expressed. The
        latter is not an error — no one asked for these individually — but is worth logging.
    """
    unplaceable: list[Unplaceable] = []
    insertions: list[tuple[int, str]] = []

    for verse in _verses(xml):
        parts = _verse_urn_parts(verse.urn)
        if parts is None:
            continue
        book, _chapter, _verse = parts

        boundary = _half_verse_boundary(verse, book)
        if boundary is None:
            continue

        try:
            source = verse.source_offset(boundary)
        except ValueError as error:
            unplaceable.append(Unplaceable(urn=f"{verse.urn}/b", reason=str(error)))
            continue

        insertions.append((verse.opens_at, _milestone_xml("half-verse", "a", f"{verse.urn}/a")))
        insertions.append((source, _milestone_xml("half-verse", "b", f"{verse.urn}/b")))

    logger.info(
        "%s: divided %d verses at the etnachta%s", project or "sub-verse",
        len(insertions) // 2,
        f", {len(unplaceable)} not expressible" if unplaceable else "",
    )
    return _splice(xml, insertions), unplaceable


def insert_verse_parts(
    xml: str, *, language: str, project: str = "",
) -> tuple[str, list[Unplaceable]]:
    """`xml` with the `verse-part` milestones `VERSE_PARTS` declares for `language`.

    Unlike the halves, every one of these was asked for by name. A declared part that cannot
    be placed is returned for the caller to fail on: a part that is silently absent is a URN
    that silently resolves to the whole verse, which is the over-reading this whole mechanism
    exists to stop.
    """
    unplaceable: list[Unplaceable] = []
    insertions: list[tuple[int, str]] = []

    for verse in _verses(xml):
        key = _verse_urn_parts(verse.urn)
        if key is None or key not in VERSE_PARTS:
            continue

        declared = [
            (name, incipits[language])
            for name, incipits in VERSE_PARTS[key]
            if language in incipits
        ]

        for name, incipit in declared:
            offset = _incipit_offset(verse, incipit)
            if offset is None:
                unplaceable.append(Unplaceable(
                    urn=f"{verse.urn}/{name}",
                    reason=f"no word boundary in the verse begins {incipit!r}",
                ))
                continue
            try:
                source = verse.source_offset(offset)
            except ValueError as error:
                unplaceable.append(Unplaceable(urn=f"{verse.urn}/{name}", reason=str(error)))
                continue
            insertions.append((source, _milestone_xml("verse-part", name, f"{verse.urn}/{name}")))

    logger.info("%s: placed %d declared verse parts", project or "sub-verse", len(insertions))
    return _splice(xml, insertions), unplaceable


def _incipit_offset(verse: _VerseText, incipit: str) -> int | None:
    """Where `incipit` begins in the verse, or None if no word boundary begins it.

    Matching runs over consonants, and over words rather than tokens, so that a maqqef
    inside the incipit or inside the text does not defeat it. The match must begin at the
    start of a token: the words a maqqef joins are read as one and a milestone may not be
    put between them.
    """
    wanted = [_consonants(word) for word in incipit.split() if _consonants(word)]
    if not wanted:
        return None

    # (offset, consonants, starts_a_token) for every word in the verse.
    words: list[tuple[int, str, bool]] = []
    for token_offset, token in verse.tokens():
        offset = token_offset
        for index, piece in enumerate(token.split(MAQAF)):
            consonants = _consonants(piece)
            if consonants:
                words.append((offset, consonants, index == 0))
            offset += len(piece) + len(MAQAF)

    for start in range(len(words) - len(wanted) + 1):
        if not words[start][2]:
            continue  # the incipit would begin inside a maqqef-joined unit
        if all(words[start + i][1] == wanted[i] for i in range(len(wanted))):
            return words[start][0]
    return None
