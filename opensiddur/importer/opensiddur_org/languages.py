"""Languages on opensiddur.org: from the site's ``lang`` attributes and column headers to BCP 47.

The site marks each cell ``lang="<ISO 639-3>-<ISO 15924>"`` (``heb-Hebr``, ``eng-Latn``,
``yid-Latn``). JLPTEI uses BCP 47, which prefers the two-letter ISO 639-1 code where one
exists and leaves out a script that is the language's usual one: ``heb-Hebr`` is ``he``,
``heb-Latn`` is ``he-Latn``, ``lad-Hebr`` is ``lad`` and ``lad-Latn`` is ``lad-Latn``. The
exporters rely on the script subtag to set a Latin transliteration left-to-right.
"""

from __future__ import annotations

import difflib
import re

UNKNOWN_LANGUAGE = "und"

#: ISO 639-3 -> ISO 639-1, for the languages the site uses that have one.
ISO639_1: dict[str, str] = {
    "ara": "ar", "deu": "de", "ell": "el", "eng": "en", "epo": "eo", "fas": "fa",
    "fra": "fr", "heb": "he", "hrv": "hr", "hun": "hu", "ita": "it", "lat": "la",
    "mar": "mr", "nld": "nl", "pol": "pl", "por": "pt", "ron": "ro", "rus": "ru",
    "spa": "es", "tur": "tr", "ukr": "uk", "yid": "yi", "zho": "zh", "amh": "am",
    "ces": "cs", "dan": "da", "fin": "fi", "swe": "sv", "nor": "no", "jpn": "ja",
    "kor": "ko", "hin": "hi", "cat": "ca", "glg": "gl", "eus": "eu", "gle": "ga",
    "cym": "cy", "srp": "sr", "slk": "sk", "slv": "sl", "bul": "bg", "lit": "lt",
    "lav": "lv", "est": "et", "isl": "is", "afr": "af", "swa": "sw", "ind": "id",
    "msa": "ms", "tgl": "tl", "vie": "vi", "tha": "th", "bel": "be", "kat": "ka",
    "hye": "hy", "aze": "az", "kaz": "kk", "uzb": "uz", "tgk": "tg", "urd": "ur",
    "ben": "bn", "pan": "pa", "tam": "ta", "tel": "te", "mal": "ml", "kan": "kn",
    "guj": "gu", "sqi": "sq", "mkd": "mk", "bos": "bs", "ltz": "lb", "fry": "fy",
    "oci": "oc", "bre": "br", "cos": "co", "san": "sa",
}

#: The script each language is usually written in. A script subtag equal to this is dropped.
DEFAULT_SCRIPT: dict[str, str] = {
    "heb": "Hebr", "yid": "Hebr", "lad": "Hebr", "arc": "Hebr", "jpa": "Hebr", "tmr": "Hebr",
    "jrb": "Hebr", "ajt": "Hebr", "aju": "Hebr", "yej": "Hebr", "sdt": "Hebr", "itk": "Hebr",
    "bhh": "Hebr", "jdt": "Hebr", "yhd": "Hebr", "jye": "Hebr",
    "ara": "Arab", "fas": "Arab", "urd": "Arab",
    "zho": "Hans", "jpn": "Jpan", "kor": "Kore",
    "ell": "Grek", "grc": "Grek",
    "rus": "Cyrl", "ukr": "Cyrl", "bel": "Cyrl", "bul": "Cyrl", "srp": "Cyrl", "mkd": "Cyrl",
    "kaz": "Cyrl", "tgk": "Cyrl",
    "mar": "Deva", "hin": "Deva", "san": "Deva",
    "gez": "Ethi", "amh": "Ethi",
    "hye": "Armn", "kat": "Geor", "tha": "Thai",
}

#: Language names as the site's column headers spell them -> ISO 639-3.
LANGUAGE_NAMES: dict[str, str] = {
    "hebrew": "heb", "english": "eng", "german": "deu", "aramaic": "arc", "armaic": "arc",
    "yiddish": "yid", "french": "fra", "latin": "lat", "ladino": "lad", "judeo-spanish": "lad",
    "arabic": "ara", "chinese": "zho", "spanish": "spa", "magyar": "hun", "hungarian": "hun",
    "italian": "ita", "ge’ez": "gez", "ge'ez": "gez", "geez": "gez", "ukrainian": "ukr",
    "romanian": "ron", "marathi": "mar", "portuguese": "por", "polish": "pol",
    "turkish": "tur", "dutch": "nld", "croatian": "hrv", "greek": "ell", "russian": "rus",
    "esperanto": "epo", "persian": "fas", "farsi": "fas", "judeo-arabic": "jrb",
    "judeo-provençal": "sdt", "judeo-provencal": "sdt", "judeo-greek": "yej",
    "judeo-italian": "itk", "judeo-tajik": "bhh", "bukhari": "bhh", "amharic": "amh",
    "czech": "ces", "swedish": "swe", "danish": "dan", "finnish": "fin", "norwegian": "nor",
    "japanese": "jpn", "korean": "kor", "hindi": "hin", "catalan": "cat", "welsh": "cym",
    "irish": "gle", "serbian": "srp", "slovak": "slk", "slovenian": "slv", "bulgarian": "bul",
    "lithuanian": "lit", "latvian": "lav", "estonian": "est", "icelandic": "isl",
    "afrikaans": "afr", "swahili": "swa", "indonesian": "ind", "vietnamese": "vie",
    "thai": "tha", "georgian": "kat", "armenian": "hye", "sanskrit": "san",
    "judezmo": "lad", "bukhori": "bhh", "yevanic": "yej", "old norse": "non",
    "old english": "ang", "gothic": "got",
}

#: Script names a header gives after a language: "Bukhori/Cyrillic".
SCRIPT_NAMES: dict[str, str] = {
    "cyrillic": "Cyrl", "latin": "Latn", "greek": "Grek", "arabic": "Arab", "hebrew": "Hebr",
}

#: The first word of a header's role -> the role this importer uses.
ROLE_WORDS: dict[str, str] = {
    "source": "source",
    "original": "source",
    "translation": "translation",
    "transliteration": "transliteration",
    "romanization": "transliteration",
    "adaptation": "adaptation",
    "adapted": "adaptation",
    "reconstruction": "reconstruction",
    "reconstructed": "reconstruction",
    "contribute": "contribute",
    "paraliturgical": "translation",
    "free": "translation",
    "interpretive": "translation",
    "poetic": "translation",
    "rhyming": "translation",
    "literal": "translation",
    "singable": "translation",
    "variation": "translation",
    "amendation": "adaptation",
    "amended": "adaptation",
    "hebraization": "hebraization",
    # Columns that are not texts of their own (see :data:`NOT_TEXT_ROLES`).
    "initials": "initials",
    "acrostic": "initials",
    "commentary": "commentary",
    "description": "description",
}

#: Roles of columns that do not become projects. "Initials" columns repeat the acrostic
#: letters of the source beside it; commentary and description columns become notes on the
#: column they sit beside.
NOT_TEXT_ROLES = frozenset({"initials", "commentary", "description", "contribute"})

_SCRIPT_RE = re.compile(r"^[A-Z][a-z]{3}$")


def site_lang(tag: str) -> str:
    """A BCP 47 tag as the site writes ``lang``: ``he-Latn`` is ``heb-Latn``, ``en`` is ``eng``."""
    language, _, script = tag.partition("-")
    three = next((k for k, v in ISO639_1.items() if v == language), language)
    return f"{three}-{script}" if script else three


def bcp47(iso639_3: str, script: str = "") -> str:
    """BCP 47 for an ISO 639-3 code and an optional ISO 15924 script."""
    iso639_3 = iso639_3.lower()
    if not iso639_3:
        return UNKNOWN_LANGUAGE
    primary = ISO639_1.get(iso639_3, iso639_3)
    if script and script != DEFAULT_SCRIPT.get(iso639_3, "Latn"):
        return f"{primary}-{script}"
    return primary


def language_from_lang_attribute(value: str) -> str | None:
    """``heb-Hebr`` -> ``he``. None when the attribute is empty."""
    value = value.strip()
    if not value:
        return None
    parts = value.split("-")
    language = parts[0]
    script = next((p for p in parts[1:] if _SCRIPT_RE.match(p)), "")
    return bcp47(language, script)


def _language_name(text: str) -> str:
    """A header's language name -> BCP 47, or "" when it names no language this table knows.

    "Romanized Hebrew" is Hebrew in Latin script. What follows a comma is not the language
    ("English, 1852"). After a slash comes another name for the language or its script:
    "Judezmo/Ladino", "Bukhori/Cyrillic". A "Judeo-" language the table does not know is that
    language in Hebrew letters: "Judeo-Old Norse".
    """
    text = text.split(",", 1)[0].strip().lower().replace("’", "’")
    romanized = False
    for prefix in ("romanized ", "romanised ", "transliterated "):
        if text.startswith(prefix):
            romanized = True
            text = text[len(prefix):]
    first, *rest = [part.strip() for part in text.split("/")]
    script = "Latn" if romanized else ""
    code = LANGUAGE_NAMES.get(first)
    if not code and first.startswith("judeo-") and first[len("judeo-"):] in LANGUAGE_NAMES:
        code, script = LANGUAGE_NAMES[first[len("judeo-"):]], script or "Hebr"
    for part in rest:
        if part in SCRIPT_NAMES and code:
            script = script or SCRIPT_NAMES[part]
        elif not code:
            code = LANGUAGE_NAMES.get(part, "")
    if not code:
        return ""
    return bcp47(code, script)


def _with_role(role: str, language: str) -> tuple[str, str]:
    """A transliteration is in Latin script whatever the header says: "Transliteration
    (Ge’ez)" is Ge’ez in Latin letters. A transliteration headed "(English)" names the
    reader, not the language, so the header's language is ignored. A hebraization is the
    language in Hebrew letters."""
    if role == "hebraization" and language:
        primary = language.split("-")[0]
        iso639_3 = next((k for k, v in ISO639_1.items() if v == primary), primary)
        return role, bcp47(iso639_3, "Hebr")
    if role == "transliteration" and language and "-Latn" not in language:
        if language == "en":
            return role, ""
        return role, f"{language}-Latn"
    return role, language


def language_from_header(header: str) -> tuple[str, str]:
    """A column header's role and language: "Source (Hebrew)" -> ("source", "he").

    Headers are "Role (Language)", occasionally reversed ("Yiddish (source)") or a bare
    language ("Hebrew", which is taken as the source). A role or language the tables do not
    know comes back as "".
    """
    header = header.strip()
    match = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", header)
    outside, inside = (match.group(1), match.group(2)) if match else (header, "")

    def role_of(text: str) -> str:
        # Close matches catch the site's typos ("Souce", "Tranlsation").
        for word in re.findall(r"[a-z]+", text.lower()):
            close = difflib.get_close_matches(word, ROLE_WORDS, n=1, cutoff=0.8)
            if close:
                return ROLE_WORDS[close[0]]
        return ""

    if inside:
        language = _language_name(inside)
        if language:
            return _with_role(role_of(outside), language)
        # Reversed: "Yiddish (source)".
        language = _language_name(outside)
        if language:
            return _with_role(role_of(inside) or "source", language)
        return role_of(outside) or role_of(inside), ""
    language = _language_name(outside)
    if language:
        return "source", language
    return role_of(outside), ""


#: Languages a header names generically and the markup names precisely. A header saying
#: "Aramaic" over cells marked ``jpa-Hebr`` (Jewish Palestinian Aramaic) agrees with them.
LANGUAGE_FAMILIES: tuple[frozenset[str], ...] = (
    frozenset({"arc", "jpa", "tmr", "syc", "sam", "oar", "jbn"}),
    frozenset({"jrb", "ajt", "aju", "yhd", "yud", "jye"}),
    frozenset({"el", "grc", "gmy", "grk"}),
)


def same_language(a: str, b: str) -> bool:
    """Whether two BCP 47 tags name the same language in the same kind of script.

    Only the primary subtag and whether the script is Latin are compared, so ``he`` and
    ``he-Hebr`` agree but ``he`` and ``he-Latn`` (a transliteration) do not.
    """
    primary_a, primary_b = a.split("-")[0], b.split("-")[0]
    if ("Latn" in a.split("-")[1:]) != ("Latn" in b.split("-")[1:]):
        return False
    if primary_a == primary_b:
        return True
    return any(primary_a in family and primary_b in family for family in LANGUAGE_FAMILIES)


#: Jewish languages and the language each is a variety of (primary subtags). A header that
#: names the Jewish language is more precise than markup naming the other: "Ladino" over
#: ``spa-Latn``, "Judeo-Italian" over ``ita``.
JEWISH_VARIETY_OF: dict[str, str] = {
    "lad": "es", "itk": "it", "yej": "el", "jrb": "ar", "jye": "ar", "ajt": "ar", "aju": "ar",
    "yhd": "ar", "yud": "ar", "bhh": "tg", "yi": "de", "sdt": "oc", "jpr": "fa",
}

#: What WordPress writes when no one chose a language: the markup's word counts for little.
DEFAULT_MARKUP_LANGUAGES = frozenset({"he", "en"})


def resolve_disagreement(header_lang: str, markup_lang: str) -> str:
    """Which language a column is in when its header and its markup disagree.

    The header wins when the markup is WordPress's default (``heb``, ``eng``), and when the
    header names a Jewish variety of the markup's language. Otherwise the markup, which
    someone chose, wins: a "Source (Hebrew)" column marked ``yid-Hebr`` holds Yiddish.
    """
    header_primary, markup_primary = header_lang.split("-")[0], markup_lang.split("-")[0]
    if markup_primary in DEFAULT_MARKUP_LANGUAGES:
        return header_lang
    if JEWISH_VARIETY_OF.get(header_primary) == markup_primary:
        return header_lang
    return markup_lang
