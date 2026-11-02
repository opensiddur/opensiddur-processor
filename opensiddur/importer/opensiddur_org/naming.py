"""Project identifiers for posts: ``<title>-<author>-<date>-<lang>`` (``specs/NAMING_SCHEME.md``).

A post is named by what it is, not by its number on the site:

- ``title``: the Latin-script part of the post's title, up to the first comma or "by", with
  anything in brackets left out, folded to ASCII. A post that romanizes its own name keeps its
  romanization; only the style guide's diacritics are mapped onto the table's digraphs. A post
  whose title has no Latin part is named from its slug.
- ``author``: whoever made this column what it is. A translation is its translator's, and has
  no author when its translator is unknown; any other column is the original author's. The
  credits do not always say which is which -- a translator who has died is credited as an
  author, and so is a congregation -- so the title's "by" settles it where it names one of
  them: "... by Penina Moïse", "trans. by Frederick de Sola Mendes". A name with a patronymic
  or a place (``Yosef ben Shlomo of Carcassonne``) is given by its first name, any other by
  its surname.
- ``date``: the year of the original work, else of the post. A translation has none: when it
  was made is rarely recorded, and the post's date would say something false.
- ``lang``: the column's language.

A second column in the same language as another (a literal and a singable translation) is
told apart by its variant, added before the language. Two posts that would share an identifier
are told apart by their post IDs, added before the language. A post that already has the plain identifier keeps it, and otherwise the older post,
by ID, has it, so adding a post never renames an older one. A post's projects are found again by the post ID in their ``index.xml``, not by
their names.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from lxml import etree

from opensiddur.common.validate_names import PROJECT_ID_RE
from opensiddur.importer.opensiddur_org.contributors import PLACEHOLDER_SLUGS, role_key
from opensiddur.importer.opensiddur_org.parse_post import Column, Post

logger = logging.getLogger(__name__)

#: The longest a title field may be, cut back to a whole word.
TITLE_LENGTH = 60

#: The style guide's romanization, onto the table's (schema/JLPTEI-3.md#transliteration).
#: Letters the table writes without a diacritic lose theirs when folded.
_LETTERS = {
    "ḥ": "ch", "Ḥ": "ch", "ẓ": "tz", "Ẓ": "tz", "ƙ": "kh", "Ƙ": "kh", "š": "sh", "Š": "sh",
    "ḳ": "q", "Ḳ": "q", "ḇ": "v", "þ": "t", "Þ": "t", "ʝ": "j", "Ʝ": "j", "ß": "ss",
    "æ": "ae", "Æ": "ae", "ø": "o", "Ø": "o", "ł": "l", "Ł": "l", "Ḇ": "v", "œ": "oe", "Œ": "oe",
    "ð": "d", "Ð": "d", "đ": "d", "Đ": "d", "ı": "i", "ə": "e", "Ə": "e",
}
#: Marks for an aleph or an ayin, and apostrophes, which the table does not write.
_DROPPED = "ʼʾʿʕ'’‘`ʻȝȜŋŊ"

_BRACKETED = re.compile(r"\([^()]*\)|\[[^\[\]]*\]")
#: Where a title's name ends and its attribution begins: a comma, "by", a dash, or a colon
#: before an honorific ("…of the U.S. Senate: Rabbi Peter S. Berg").
_TITLE_END = re.compile(
    r",|\s(?:by|von|par|por)\s|\s[–—]\s|:\s+(?=(?:rabbi|rebbe|kohenet|cantor|dr|rev)\b)",
    re.IGNORECASE)
#: Words a name cut short must not end on.
_DANGLING = frozenset({"a", "an", "the", "of", "on", "in", "at", "to", "for", "and", "or", "by",
                       "with", "while", "from", "as", "de", "der", "die", "das", "la", "le"})

#: Words before a name that are not part of it.
_HONORIFICS = frozenset({
    "rabbi", "rebbe", "reb", "r", "rav", "moreh", "kohenet", "cantor", "hazzan", "chazzan",
    "dr", "rev", "phd", "ph", "d", "mr", "mrs", "ms",
})
#: Words after the first that make a name a patronymic or an epithet, so that its first word
#: names the person: "Yosef ben Shlomo of Carcassonne".
_PATRONYMIC = frozenset({"ben", "bar", "bat", "of"})
#: An epithet that ends a name the same way: "Mordekhai ben Yitsḥaq ha-Levi".
#: An organization's own abbreviation, given beside its name: "Central Conference of American
#: Rabbis [CCAR]".
_ABBREVIATION = re.compile(r"[\[(]\s*([A-Z][A-Z0-9.&]*[A-Z0-9])\s*[\])]")
_LAST_EPITHET = re.compile(r"^ha-|^halevi$|^hakohen$")

#: The parts of a title that credit someone: split at commas, brackets and dashes.
_CLAUSE = re.compile(r"[,()\[\];|–—]")
#: "by" and who follows it, to the end of the clause.
_BY = re.compile(r"\bby\s+(?P<who>.+)", re.IGNORECASE)
#: "trans. Yehudis Fishman", with no "by".
_TRANS_NAMED = re.compile(r"\btrans(?:lated|lation)?\.?\s+(?!by\b)(?P<who>.+)", re.IGNORECASE)
#: Words that make a clause's "by" credit a translation: "a German translation of Maoz Tsur by
#: Leopold Stein". Not "transliterated".
_TRANSLATED = re.compile(r"\b(?:trans(?!lit)|adapt|interpret|render)", re.IGNORECASE)

TRANSLATION_ROLES = frozenset({"translation", "adaptation"})

#: A post's original, as a column, for the author of the text as a whole.
ORIGINAL = Column(header="", role="source", lang="")


def fold(text: str) -> list[str]:
    """``text``'s words in the identifier alphabet: lowercase ASCII letters and digits."""
    # Composed first: the post's text arrives decomposed, Ḥ as H and a combining dot.
    text = unicodedata.normalize("NFC", text)
    for letter, replacement in _LETTERS.items():
        text = text.replace(letter, replacement)
    text = "".join(c for c in text if c not in _DROPPED)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", text.lower())


def _joined(words: list[str], limit: int | None = None) -> str:
    """``words`` joined by ``_``, cut to ``limit`` at a whole word that is not a dangling
    "of" or "the"."""
    field = "_".join(words)
    if limit is not None and len(field) > limit:
        field = field[: limit + 1].rsplit("_", 1)[0] if "_" in field[:limit] else field[:limit]
        kept = field.split("_")
        while len(kept) > 1 and kept[-1] in _DANGLING:
            kept.pop()
        field = "_".join(kept)
    return field


def latin_title(post: Post) -> str | None:
    """The part of the post's title written in Latin letters, if any."""
    from opensiddur.importer.opensiddur_org.tei_builder import titles_by_language

    return next((title for lang, title in titles_by_language(post) if lang == "en"), None)


#: A first letter whose shva the romanization elides, then an apostrophe: "l’Garesh", "Y’qar",
#: "Ṭ’horot"; or a prefix letter, then a hyphen: "l-Tsur", "b-Af". The table writes the shva
#: (`legaresh`, `yeqar`, `tehorot`, `letzur`, `beaf`). French elides the same way ("l’instruction"),
#: so a French post's title is not joined (:func:`title_words`).
_CONSONANT = "BCDFGHJKLMNPQRSTVWXYZbcdfghjklmnpqrstvwxyzḤḥḲḳṬṭẒẓŠš"
_ELIDED_SHVA = re.compile(rf"\b([{_CONSONANT}]|[SsCcKk]h|[Tt]z)['’ʼ‘](?=[^\W\d_])"
                          r"|\b([BbKkLlMm])-(?=[^\W\d_])")
#: A prefix written with a hyphen, "ha-Hodayah", "u-Netaneh", which the table joins to its word.
_HYPHENED_PREFIX = re.compile(r"\b([Hh]a|[Ll][ai]|[Bb][ai]|[Mm]i|[Uu])-(?=[^\W\d_])")
#: The prefixes a joined word may begin with, whose word is respelled by the list after them.
_PREFIXES = ("she", "be", "de", "ke", "le", "me", "ve", "ha")


def join_prefixes(text: str) -> str:
    """``text`` with its Hebrew prefixes joined to their words as the table writes them:
    "Banu Ḥoshekh l’Garesh" is "Banu Ḥoshekh leGaresh", "li-Ymei ha-Hodayah" is
    "li-Ymei haHodayah"."""
    text = _ELIDED_SHVA.sub(lambda m: (m.group(1) or m.group(2)) + "e", text)
    return _HYPHENED_PREFIX.sub(r"\1", text)


def respelled(word: str, variants: Mapping[str, str]) -> str:
    """``word`` spelled by the list, or a prefix and its word so spelled (`letsur` is `letzur`)."""
    if word in variants:
        return variants[word]
    for prefix in _PREFIXES:
        rest = word[len(prefix):]
        # A variant that only doubles a letter may, after a prefix, be another word: `sheelu`
        # is שְׁאֵלוּ, not she + אֵלּוּ.
        if word.startswith(prefix) and rest in variants and re.sub(r"(.)\1", r"\1", variants[rest]) != rest:
            return prefix + variants[rest]
    return word


def _french(post: Post) -> bool:
    """Whether the post is in French, by its languages (ISO 639-3) or its columns."""
    return (any(code in ("fra", "fre") for code in post.languages)
            or any(column.lang == "fr" for column in post.columns))


def title_words(post: Post, *, prefixes_joined: bool = False) -> list[str]:
    """The words that name the post: its Latin title up to the attribution, folded. A text's
    name joins the title's Hebrew prefixes to their words (:func:`join_prefixes`), unless the
    post is in French, whose elisions look the same; a project's title keeps the post's own
    romanization."""
    title = latin_title(post)
    if title is not None:
        name = _BRACKETED.sub(" ", title)
        name = _TITLE_END.split(name, 1)[0]
        if prefixes_joined and not _french(post):
            name = join_prefixes(name)
        words = fold(name) or fold(title)
    else:
        words = []
    if not words:
        # The site's slug is already romanized; its attribution starts at "by".
        slug = re.split(r"-by-", post.slug, 1)[0]
        words = fold(slug.replace("-", " ")) or ["post"]
    return words


def title_field(post: Post) -> str:
    return _joined(title_words(post), TITLE_LENGTH)


def text_name(post: Post, variants: Mapping[str, str]) -> str:
    """The name of the text a post publishes, for its URN: its title words, each respelled by
    the spelling list (``specs/naming/spellings.yaml``), since a URN follows the table where a
    project title keeps the post's own romanization; then its author's name, since a new text
    on the site is someone's (``chanukah_wise``, not ``chanukah``)."""
    name = _joined([respelled(word, variants) for word in title_words(post, prefixes_joined=True)],
                   TITLE_LENGTH)
    # The author is respelled too: a URN is spelled by the table throughout, and the person's
    # own spelling stays in the registry's label and the credits (ibn Tsur -> `tzur`).
    author = "_".join(variants.get(word, word) for word in original_author(post).split("_") if word)
    return f"{name}_{author}" if author else name


def original_author(post: Post) -> str:
    """The name of whoever wrote the post's original: its credited author, or when no one is
    credited but a placeholder, the author its title names."""
    if author := author_field(post, ORIGINAL):
        return author
    _, authored = _credited(post)
    return next((field for name in authored if (field := name_field(name))), "")


def _name_words(name: str) -> list[str]:
    """A name's words, without honorifics or anything in brackets."""
    words = [w for w in re.split(r"\s+", re.sub(r"[.,]", " ", _BRACKETED.sub(" ", name))) if w]
    return [w for w in words if fold(w) and "".join(fold(w)) not in _HONORIFICS]


def name_field(name: str) -> str:
    """The word(s) that name a person in an identifier: a surname, or a first name.

    The first name, for a patronymic or an epithet; otherwise the last word. An initial is not
    a patronymic: "Lieba B. Ruth" is `ruth`. A hyphenated name is one word: "Bat-Sheva Cohen".
    An organization that gives its own abbreviation is named by it: `ccar`.
    """
    abbreviation = _ABBREVIATION.search(name)
    if abbreviation and sum(c.isupper() for c in abbreviation.group(1)) >= 2:
        return _joined(fold(abbreviation.group(1)))
    words = _name_words(name)
    if not words:
        return ""
    lowered = [unicodedata.normalize("NFC", w).lower() for w in words]
    patronymic = (any(w in _PATRONYMIC for w in lowered[1:])
                  or any(w == "b" for w in lowered[1:-2])
                  or (len(lowered) > 1 and bool(_LAST_EPITHET.match(lowered[-1]))))
    return _joined(fold(words[0] if patronymic else words[-1]))


def _named(post: Post) -> tuple[list[str], list[str]]:
    """The people the post credits: (translators, everyone credited with no role). A name in a
    script that folds to nothing -- Hebrew -- is given by the person's profile slug."""
    translators: list[str] = []
    others: list[str] = []
    for coauthor in post.coauthors:
        if coauthor.name.lower() in PLACEHOLDER_SLUGS or coauthor.profile_slug in PLACEHOLDER_SLUGS:
            continue
        name = coauthor.name if fold(coauthor.name) else coauthor.profile_slug.replace("-", " ")
        role = role_key(coauthor.qualifier)
        if role is None:
            others.append(name)
        elif role[0] == "trl":
            translators.append(name)
    return translators, others


def _credited(post: Post) -> tuple[list[str], list[str]]:
    """Each name the title credits, as written: (as translator, as author)."""
    translated: list[str] = []
    authored: list[str] = []
    for clause in _CLAUSE.split(latin_title(post) or ""):
        if match := _BY.search(clause):
            before = clause[: match.start()]
            (translated if _TRANSLATED.search(before) else authored).append(match.group("who"))
        elif match := _TRANS_NAMED.search(clause):
            translated.append(match.group("who"))
    return translated, authored


def _attributions(post: Post) -> tuple[list[set[str]], list[set[str]]]:
    """The words of each name the title credits: (as translator, as author)."""
    translated, authored = _credited(post)
    return [set(fold(n)) for n in translated], [set(fold(n)) for n in authored]


def _in(name: str, attributions: list[set[str]]) -> bool:
    """Whether the title credits ``name``: every word of it, honorifics aside."""
    words = {word for w in _name_words(name) for word in fold(w)}
    return bool(words) and any(words <= named for named in attributions)


def author_field(post: Post, column: Column) -> str:
    translators, others = _named(post)
    translated, authored = _attributions(post)
    if column.role in TRANSLATION_ROLES:
        chosen = ([n for n in translators if _in(n, translated + authored)][:1] or translators[:1]
                  or [n for n in others if _in(n, translated)][:1])
    else:
        originals = [n for n in others if n not in translators and not _in(n, translated)]
        chosen = [n for n in originals if _in(n, authored)][:1] or originals[:1]
    return name_field(chosen[0]) if chosen else ""


def _year(date: str) -> str:
    """``1240-00-00`` -> ``1240``; ``-0515-00-00`` -> ``515bce``; nothing for no year."""
    match = re.match(r"^(-?)0*(\d+)", date or "")
    if not match or match.group(2) == "0":
        return ""
    return f"{match.group(2)}bce" if match.group(1) else match.group(2)


def date_field(post: Post, column: Column) -> str:
    if column.role in TRANSLATION_ROLES:
        return ""
    return _year(post.date_src_start) or _year(post.date)


def base_project_id(post: Post, column: Column) -> str:
    fields = [title_field(post), author_field(post, column), date_field(post, column)]
    return "-".join(f for f in fields if f)


@dataclass(frozen=True)
class Candidate:
    """One column of one post that will be a project."""

    post: Post
    column: Column


def assign_project_ids(
    candidates: Iterable[Candidate],
    taken: Iterable[str] = (),
    held: Mapping[str, int] | None = None,
) -> dict[tuple[int, str], str]:
    """Each candidate's project identifier, keyed by ``(post_id, column key)``.

    ``taken`` are identifiers no candidate may have: projects no post made, or that posts not
    being named hold. ``held`` maps an identifier on disk to the post holding it. Of the
    candidates wanting one identifier, the post holding it keeps it, so a post never loses a
    name it has; else the post with the lowest ID has it. The others add their post IDs.

    A candidate whose identifier would not be valid is left out, with a warning.
    """
    taken = set(taken)
    held = held or {}
    wanting: dict[str, list[tuple[Candidate, str, str]]] = {}
    for candidate in sorted(candidates, key=lambda c: (c.post.post_id, c.column.key)):
        lang = candidate.column.lang.lower()
        base = base_project_id(candidate.post, candidate.column)
        if candidate.column.variant:
            # A second column in one language, told apart by its header (see parse_post).
            base = f"{base}-{candidate.column.variant}"
        wanting.setdefault(f"{base}-{lang}", []).append((candidate, base, lang))

    ids: dict[tuple[int, str], str] = {}
    used = set(taken)
    for plain, group in sorted(wanting.items()):
        if plain in taken:
            keeper = None
        else:
            holders = [g for g in group if g[0].post.post_id == held.get(plain)]
            keeper = (holders or group)[0][0]
        for candidate, base, lang in group:
            post_id = candidate.post.post_id
            pid = plain if candidate is keeper else f"{base}-{post_id}-{lang}"
            if not PROJECT_ID_RE.match(pid) or pid in used:
                logger.warning("post %s: cannot be named %r; not converted", post_id, pid)
                continue
            used.add(pid)
            ids[(post_id, candidate.column.key)] = pid
    return ids


def imported_projects(project_directory: Path) -> dict[int, list[Path]]:
    """The projects converted from posts, by post ID, read from each ``index.xml``."""
    found: dict[int, list[Path]] = {}
    for index in sorted(Path(project_directory).glob("*/index.xml")):
        try:
            root = etree.parse(str(index)).getroot()
        except (OSError, etree.XMLSyntaxError):
            continue
        # The post the project was converted from, in its own source bibl -- not a post some
        # other project cites.
        ids = root.xpath(
            "/tei:TEI/tei:teiHeader//tei:bibl[@xml:id='project_source_bibl']"
            "/tei:idno[@type='opensiddur.org']/text()",
            namespaces={"tei": "http://www.tei-c.org/ns/1.0"},
        )
        if ids and ids[0].strip().isdigit():
            found.setdefault(int(ids[0].strip()), []).append(index.parent)
    return found
