"""Romanize pointed Hebrew for URN and file names, by the table in ``schema/JLPTEI-3.md``.

This seeds a name; it does not settle one. It knows the table (het ``ch``, khaf ``kh``, qof
``q``, tzadi ``tz``, aleph and ayin silent, dagesh hazak doubled but never a digraph, final heh
written, the divine name read ``adonai``, no doubling after a one-letter prefix) and the common cases of the vowels, but not grammar:
it reads every qamatz as ``a``, and a sheva as ``e`` only on a word's first letter, under a
dagesh, or where the source marks it sounded, and it tells a prefix from a root letter only by its vowel
(:data:`PREFIX_VOWELS`), so that שַׁבָּת is doubled but הַלֵּל is not. A name it makes
is respelled by ``specs/naming/spellings.yaml`` (:func:`name_from_hebrew`) and reviewed where it
is recorded, like any other name an importer mints.
"""

from __future__ import annotations

import re
import unicodedata

from opensiddur.common.validate_names import Spellings, load_spellings, respell

DAGESH = "ּ"
SHIN_DOT = "ׁ"
SIN_DOT = "ׂ"
SHEVA = "ְ"
TSERE = "ֵ"
HIRIQ = "ִ"
HOLAM = ("ֹ", "ֺ")
#: Metsudah, like many prayer books, marks a sheva that is sounded with this accent after it.
VOCAL_SHEVA_MARK = "֒"

VOWELS = {
    "ֱ": "e",  # hataf segol
    "ֲ": "a",  # hataf patah
    "ֳ": "o",  # hataf qamatz
    HIRIQ: "i",
    TSERE: "e",
    "ֶ": "e",  # segol
    "ַ": "a",  # patah
    "ָ": "a",  # qamatz
    "ֹ": "o",  # holam
    "ֺ": "o",  # holam haser for vav
    "ֻ": "u",  # qubutz
    "ׇ": "o",  # qamatz qatan
}

#: Letters whose sound the dagesh changes: (with it, without it).
BEGADKEFAT = {"ב": ("b", "v"), "כ": ("k", "kh"), "ך": ("k", "kh"), "פ": ("p", "f"), "ף": ("p", "f")}
CONSONANTS = {
    "א": "", "ג": "g", "ד": "d", "ה": "h", "ו": "v", "ז": "z", "ח": "ch", "ט": "t", "י": "y",
    "ל": "l", "מ": "m", "ם": "m", "נ": "n", "ן": "n", "ס": "s", "ע": "", "צ": "tz", "ץ": "tz",
    "ק": "q", "ר": "r", "ת": "t",
}
#: Letters a dagesh never doubles (in heh it is a mappiq).
NOT_DOUBLED = {"א", "ה", "ע", "ח", "ר"}
DIVINE_NAME = {"יהוה", "יי", "ייי"}
#: Letters that can be prefixed to a word.
PREFIXES = set("ובכלמהש")
SEGOL = "\u05b6"
QAMATZ = "\u05b8"

#: Cantillation and other marks with no sound; the vocal-sheva accent is kept.
_SILENT_MARKS = re.compile("[֑֓-ֽֿ֯׀׃-׆]")
_LETTER = re.compile("[א-ת]")


def _letters(word: str) -> list[tuple[str, str]]:
    """The word as (letter, marks) pairs."""
    out: list[tuple[str, str]] = []
    for ch in word:
        if _LETTER.match(ch):
            out.append((ch, ""))
        elif out and unicodedata.category(ch) == "Mn":
            out[-1] = (out[-1][0], out[-1][1] + ch)
    return out


#: A first letter read as a prefix -- whose dagesh in the next letter is not doubled -- by its
#: vowel: the article (הַ, הָ, הֶ), מִ (from), שֶׁ (that), and בַּ, כַּ, לַ (the article
#: merged). A root letter with those vowels (שַׁבָּת, הַלֵּל) is misread, and doubled
#: names that need it are listed in spellings.yaml.
PREFIX_VOWELS = {"ה": {"\u05b7", "\u05b8", "\u05b6"}, "מ": {HIRIQ}, "ש": {"\u05b6"},
                 "ב": {"\u05b7"}, "כ": {"\u05b7"}, "ל": {"\u05b7"}}


def _is_prefix(letter: str, marks: str) -> bool:
    return any(mark in PREFIX_VOWELS.get(letter, ()) for mark in marks)


def transliterate_word(word: str) -> str:
    letters = _letters(_SILENT_MARKS.sub("", unicodedata.normalize("NFD", word)))
    spelled = "".join(letter for letter, _ in letters)
    if spelled in DIVINE_NAME:
        return "adonai"
    if len(letters) > 1 and spelled[1:] in DIVINE_NAME and spelled[0] in PREFIXES:
        # A prefix on the divine name (לַיהוָה, וַיהוָה): the prefix, then "adonai".
        letter, marks = letters[0]
        vowel = next((VOWELS[m] for m in marks if m in VOWELS), "")
        return (CONSONANTS.get(letter) or BEGADKEFAT.get(letter, ("", ""))[0]) + vowel + "donai"
    out: list[str] = []
    #: the vowel mark last sounded, or "" after a silent letter
    last_vowel = ""
    for i, (letter, marks) in enumerate(letters):
        vowel_mark = next((m for m in marks if m in VOWELS), "")
        dagesh = DAGESH in marks
        if letter == "ו" and i == 0 and dagesh and not vowel_mark:
            out.append("u")  # a conjunction as shuruk: וּבְכָל
            last_vowel = "\u05bb"
            continue
        if letter == "ו" and i > 0 and not (vowel_mark and vowel_mark not in HOLAM):
            # Vav with holam is the vowel o, except after a letter with a sheva or a vowel of
            # its own, where it is a consonant carrying the o (מִצְוֹת, "mitzvot"; עָוֹן,
            # עֲוֺנֵינוּ, "avon", "avoneinu").
            before = letters[i - 1][1]
            if vowel_mark in HOLAM and SHEVA not in before and not any(m in VOWELS for m in before):
                out.append("o")
                last_vowel = vowel_mark
                continue
            if dagesh and SHEVA not in marks:
                out.append("u")
                last_vowel = "ֻ"
                continue
        if letter == "י" and i > 0 and not vowel_mark and SHEVA not in marks:
            # A mater lectionis: silent after hiriq and segol, and in qamatz-yod-vav (ָיו,
            # "-av"); "ei" after tsere.
            final_av = last_vowel == QAMATZ and i == len(letters) - 2 and letters[-1][0] == "ו"
            if last_vowel in (HIRIQ, SEGOL) or final_av:
                last_vowel = ""
                continue
            if last_vowel == TSERE:
                out.append("i")
                last_vowel = ""
                continue
        if letter == "ש":
            sound = "s" if SIN_DOT in marks else "sh"
        elif letter in BEGADKEFAT:
            hard, soft = BEGADKEFAT[letter]
            sound = hard if dagesh else soft
        else:
            sound = CONSONANTS.get(letter, "")
        after_prefix = i == 1 and _is_prefix(*letters[0])
        if (dagesh and i > 0 and last_vowel and letter not in NOT_DOUBLED and len(sound) == 1
                and not after_prefix):
            sound += sound
        out.append(sound)
        if vowel_mark:
            out.append(VOWELS[vowel_mark])
            last_vowel = vowel_mark
        elif SHEVA in marks and (i == 0 or VOCAL_SHEVA_MARK in marks or (dagesh and len(sound) >= 1)
                                 or (i == 1 and out[:1] == ["u"])):
            out.append("e")
            last_vowel = SHEVA
        else:
            last_vowel = ""
    return re.sub(r"[^a-z]", "", "".join(out))


def transliterate(text: str) -> list[str]:
    """The words of ``text``, romanized; a maqaf or slash separates words."""
    words = re.split(r"[\s־/]+", text)
    return [w for w in (transliterate_word(word) for word in words) if w]


def name_from_hebrew(text: str, max_words: int, spellings: Spellings | None = None) -> str:
    """A URN path component from the first ``max_words`` words of pointed Hebrew, respelled."""
    words = transliterate(text)[:max_words]
    return respell("_".join(words), spellings or load_spellings())
