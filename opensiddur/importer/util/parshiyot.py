"""The names of the weekly parshiyot, in the three forms the importers need.

``JLPTEI-3.md`` asks for transliterated Hebrew in URN path segments, "unless the text has a
common name (with a common spelling)". Every parshah does, so the table below is explicit
rather than produced by running the transliteration rules over the Hebrew: mechanical
transliteration would give forms nobody writes (``vzat_hbrkh``), and it would silently drop
the maqaf in לך־לך.

The table is also the join between sources that name the parshiyot differently — MAM in
pointed Hebrew, hebcal in English, the JPS 1917 scans in unpointed Hebrew with the maqaf
sometimes written as a space and sometimes not at all — so lookups by Hebrew name go through
:func:`opensiddur.importer.util.hebrew.normalize_hebrew`, which reduces a name to its bare
consonant skeleton. That is why ``לךלך`` (jps1917), ``לך־לך`` (MAM) and ``לֶךְ־לְךָ`` all resolve
to the same entry. The skeletons of all 54 names are distinct, so nothing is conflated:
``כי תשא``/``כי־תצא``/``כי־תבוא`` fold to ``כיתשא``/``כיתצא``/``כיתבוא``.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache

from opensiddur.common.validate_names import load_spellings, respell
from opensiddur.importer.util.hebrew import normalize_hebrew

# (Hebrew name, hebcal name, opensiddur slug)
PARSHA_NAMES: tuple[tuple[str, str, str], ...] = (
    ("בראשית", "Bereshit", "bereshit"),
    ("נֹח", "Noach", "noach"),
    ("לך־לך", "Lech-Lecha", "lech_lecha"),
    ("וירא", "Vayera", "vayera"),
    ("חיי שרה", "Chayei Sara", "chayei_sara"),
    ("תולדֹת", "Toldot", "toldot"),
    ("ויצא", "Vayetzei", "vayetzei"),
    ("וישלח", "Vayishlach", "vayishlach"),
    ("וישב", "Vayeshev", "vayeshev"),
    ("מקץ", "Miketz", "miketz"),
    ("ויגש", "Vayigash", "vayigash"),
    ("ויחי", "Vayechi", "vayechi"),
    ("שמות", "Shemot", "shemot"),
    ("וארא", "Vaera", "vaera"),
    ("בֹא", "Bo", "bo"),
    ("בשלח", "Beshalach", "beshalach"),
    ("יתרו", "Yitro", "yitro"),
    ("משפטים", "Mishpatim", "mishpatim"),
    ("תרומה", "Terumah", "terumah"),
    ("תצוה", "Tetzaveh", "tetzaveh"),
    ("כי תשא", "Ki Tisa", "ki_tisa"),
    ("ויקהל", "Vayakhel", "vayakhel"),
    ("פקודי", "Pekudei", "pekudei"),
    ("ויקרא", "Vayikra", "vayikra"),
    ("צו", "Tzav", "tzav"),
    ("שמיני", "Shmini", "shmini"),
    ("תזריע", "Tazria", "tazria"),
    ("מצֹרע", "Metzora", "metzora"),
    ("אחרי מות", "Achrei Mot", "achrei_mot"),
    ("קדֹשים", "Kedoshim", "kedoshim"),
    ("אמֹר", "Emor", "emor"),
    ("בהר", "Behar", "behar"),
    ("בחֻקֹתי", "Bechukotai", "bechukotai"),
    ("במדבר", "Bamidbar", "bamidbar"),
    ("נשֹא", "Nasso", "nasso"),
    ("בהעלֹתך", "Beha'alotcha", "behaalotcha"),
    ("שלח", "Sh'lach", "shlach"),
    ("קֹרח", "Korach", "korach"),
    ("חֻקת", "Chukat", "chukat"),
    ("בלק", "Balak", "balak"),
    ("פינחס", "Pinchas", "pinchas"),
    ("מטות", "Matot", "matot"),
    ("מסעי", "Masei", "masei"),
    ("דברים", "Devarim", "devarim"),
    ("ואתחנן", "Vaetchanan", "vaetchanan"),
    ("עקב", "Eikev", "eikev"),
    ("ראה", "Re'eh", "reeh"),
    ("שֹפטים", "Shoftim", "shoftim"),
    ("כי־תצא", "Ki Teitzei", "ki_teitzei"),
    ("כי־תבוא", "Ki Tavo", "ki_tavo"),
    ("נִצבים", "Nitzavim", "nitzavim"),
    ("וילך", "Vayeilech", "vayeilech"),
    ("האזינו", "Ha'azinu", "haazinu"),
    ("וזאת הברכה", "Vezot Haberakhah", "vezot_haberakhah"),
)

# Weeks on which two parshiyot are read together. hebcal names these by joining the two.
COMBINED_PARSHIYOT: tuple[tuple[str, str], ...] = (
    ("Vayakhel-Pekudei", "vayakhel_pekudei"),
    ("Tazria-Metzora", "tazria_metzora"),
    ("Achrei Mot-Kedoshim", "achrei_mot_kedoshim"),
    ("Behar-Bechukotai", "behar_bechukotai"),
    ("Chukat-Balak", "chukat_balak"),
    ("Matot-Masei", "matot_masei"),
    ("Nitzavim-Vayeilech", "nitzavim_vayeilech"),
)

# Spellings that differ from the table by more than pointing, so the consonant skeleton alone
# does not reach them: a source writing a name plene where the table has it defective. Listed
# explicitly rather than folded away, because dropping every mater lectionis would conflate
# real names — וישלח and שלח both reduce to שלח once ו and י go.
SPELLING_ALIASES: tuple[tuple[str, str], ...] = (
    ("תולדות", "תולדֹת"),  # jps1917
    ("אמור", "אמֹר"),  # jps1917
)

_BY_SKELETON = {
    normalize_hebrew(hebrew): (hebrew, hebcal, slug)
    for hebrew, hebcal, slug in PARSHA_NAMES
}
_BY_SKELETON.update({
    normalize_hebrew(variant): _BY_SKELETON[normalize_hebrew(canonical)]
    for variant, canonical in SPELLING_ALIASES
})

HEBCAL_TO_SLUG = {hebcal: slug for _, hebcal, slug in PARSHA_NAMES}
HEBCAL_TO_SLUG.update(dict(COMBINED_PARSHIYOT))
SLUG_TO_HEBREW = {slug: hebrew for hebrew, _, slug in PARSHA_NAMES}


def _entry(hebrew: str) -> tuple[str, str, str]:
    entry = _BY_SKELETON.get(normalize_hebrew(hebrew))
    if entry is None:
        raise KeyError(f"Unknown parshah name: {hebrew!r}")
    return entry


def canonical_hebrew(hebrew: str) -> str:
    """The table's spelling of a parshah named in Hebrew, however it was written."""
    return _entry(hebrew)[0]


def slug_for_hebrew(hebrew: str) -> str:
    """The slug for a parshah named in Hebrew, with or without pointing."""
    return _entry(hebrew)[2]


def hebcal_for_hebrew(hebrew: str) -> str:
    return _entry(hebrew)[1]


def slugify_reading_name(name: str) -> str:
    """Slug for a reading hebcal names but the parshah table does not, e.g. a festival, its
    words respelled by the spelling list and its punctuation dropped (specs/NAMING_SCHEME.md):
    hebcal's "Yom Kippur (Mincha, Traditional)" is ``yom_kippur_mincha_traditional``. The
    article joins its word, as the table writes it: "Chol ha-Moed" is ``chol_hamoed``."""
    folded = re.sub(r"\b([Hh]a)-(?=\w)", r"\1", name.replace("'", "").replace("’", ""))
    return respell(re.sub(r"[^a-z0-9]+", "_", folded.lower()).strip("_"), _spellings())


@lru_cache(maxsize=1)
def _spellings():
    return load_spellings()


def skeleton_map_json() -> str:
    """The table as JSON, keyed by consonant skeleton, for handing to an XSLT stylesheet.

    ``xslt_transform_string`` can only marshal atomic values, so stylesheets that need the
    table take it as a string parameter and rebuild it with ``parse-json()``. Keying by
    skeleton lets the stylesheet do the same widening with one ``replace()``.
    """
    return json.dumps(
        {
            skeleton: {"n": hebrew, "slug": slug}
            for skeleton, (hebrew, _, slug) in _BY_SKELETON.items()
        },
        ensure_ascii=False,
    )
