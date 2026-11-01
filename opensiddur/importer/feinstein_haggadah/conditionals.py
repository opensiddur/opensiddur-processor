"""Curated table of the haggadah's conditional passages.

Parts of the haggadah are said only under some condition — on Shabbat, on the first or second
seder night, when a minyan is present. Both sources record this typographically and neither
records it in a form a processor can act on: the 1822 Hebrew parenthesises the conditional
words inline, and the 2009 English marks its rubrics with ``<span class="instruction">``.

``parse_compilation.split_parenthetical_instructions`` recovers the *shape* of every English
conditional from that markup — which words are the rubric and which are the text it governs.
What it cannot recover is *which* condition applies, and the Hebrew has no rubrics at all. This
module supplies both: :data:`RUBRIC_CONDITIONS` names the condition behind each English rubric,
and :data:`CONDITIONALS` carries every passage the sources mark only by parentheses, keyed to
the text on either side exactly as ``page_breaks_1822.json`` keys page breaks.

Every entry must resolve against the source. ``convert.py`` fails the conversion if one does
not, so that a change in the source wording surfaces as an error rather than as a silently
dropped condition.
"""

from __future__ import annotations

from dataclasses import dataclass

from opensiddur.importer.feinstein_haggadah.sections import urn_for_section
from opensiddur.importer.util.occasion import (
    DAY_OF_WEEK,
    HEBREW_DATE,
    ISRAEL,
    Feature,
    all_of,
    any_of,
    holiday,
    none_of,
)

class ConditionalError(Exception):
    """A conditional in the table could not be placed in the source text."""


# --------------------------------------------------------------------------------------
# Conditions
# --------------------------------------------------------------------------------------

#: Feature structures, one per condition, written once and referenced by key. The exporter
#: evaluates these against settings; see ``opensiddur/exporter/calendar/compute.py`` for what
#: computes each feature and ``schema/JLPTEI-3.md`` for the vocabulary.
CONDITIONS: dict[str, str] = {
    "shabbat": (
        '<tei:fs type="opensiddur:holiday-aggregate">'
        '<tei:f name="shabbat"><tei:binary value="true"/></tei:f>'
        "</tei:fs>"
    ),
    "motzaei_shabbat": (
        '<tei:fs type="opensiddur:holiday-aggregate">'
        '<tei:f name="motzaei-shabbat"><tei:binary value="true"/></tei:f>'
        "</tei:fs>"
    ),
    "eruv_tavshilin": (
        '<tei:fs type="opensiddur:holiday-aggregate">'
        '<tei:f name="eruv-tavshilin"><tei:binary value="true"/></tei:f>'
        "</tei:fs>"
    ),
    # The seder nights are the first and second days of Pesah: the Hebrew day begins in the
    # evening, so the night of the first seder is already 15 Nisan.
    "first_night": (
        '<tei:fs type="opensiddur:holiday">'
        '<tei:f name="pesah"><tei:numeric value="1"/></tei:f>'
        "</tei:fs>"
    ),
    "second_night": (
        '<tei:fs type="opensiddur:holiday">'
        '<tei:f name="pesah"><tei:numeric value="2"/></tei:f>'
        "</tei:fs>"
    ),
    # The seder: the first night of Pesah, and the second outside Israel, where the second day
    # is a festival day too. A volume dated with no time to the day of the first seder -- the
    # eve, 14 Nisan, until nightfall -- has it as well.
    "seder_night": any_of(
        all_of(Feature(HEBREW_DATE, "month", 1), Feature(HEBREW_DATE, "day", 14)),
        holiday("pesah", 1),
        all_of(holiday("pesah", 2), Feature(ISRAEL, "is-israel", False)),
    ).markup(),
    # The search for leaven is made on the night of 14 Nisan -- the night of the 13th when the
    # 14th falls on Shabbat, the Friday being the 13th.
    "bediqat_chametz": all_of(
        Feature(HEBREW_DATE, "month", 1),
        any_of(
            all_of(Feature(HEBREW_DATE, "day", 14),
                   none_of(Feature(DAY_OF_WEEK, "hebrew-day", 7))),
            all_of(Feature(HEBREW_DATE, "day", 13), Feature(DAY_OF_WEEK, "hebrew-day", 6)),
        ),
    ).markup(),
    # The leaven is burned on the morning of the 14th, on the Friday before when the 14th is
    # Shabbat; the final nullification, which is what this section prints, is said on the
    # 14th either way.
    "biur_chametz": all_of(
        Feature(HEBREW_DATE, "month", 1),
        any_of(Feature(HEBREW_DATE, "day", 14),
               all_of(Feature(HEBREW_DATE, "day", 13), Feature(DAY_OF_WEEK, "hebrew-day", 6))),
    ).markup(),
    "zimmun": (
        '<tei:fs type="opensiddur:quorum">'
        '<tei:f name="zimmun"><tei:binary value="true"/></tei:f>'
        "</tei:fs>"
    ),
    "minyan": (
        '<tei:fs type="opensiddur:quorum">'
        '<tei:f name="minyan"><tei:binary value="true"/></tei:f>'
        "</tei:fs>"
    ),
    "present_not_eaten": (
        '<tei:fs type="opensiddur:quorum">'
        '<tei:f name="present-not-eaten"><tei:binary value="true"/></tei:f>'
        "</tei:fs>"
    ),
    "at_fathers_home": (
        '<tei:fs type="opensiddur:household">'
        '<tei:f name="at-fathers-home"><tei:binary value="true"/></tei:f>'
        "</tei:fs>"
    ),
    "at_mothers_home": (
        '<tei:fs type="opensiddur:household">'
        '<tei:f name="at-mothers-home"><tei:binary value="true"/></tei:f>'
        "</tei:fs>"
    ),
}


def variant_urn(slug: str, name: str) -> str:
    """The URN naming one textual variant of a passage.

    A variant is a property of the text, not of the edition that prints it, so two sources
    offering the same variant name the same URN and one setting selects it in both. The path
    mirrors the passage's own text URN and carries no ``@project`` — see the URN section of
    ``schema/JLPTEI-3.md``.
    """
    text_urn = urn_for_section(slug)
    return text_urn.replace("urn:x-opensiddur:text:", "urn:x-opensiddur:condition:", 1) + f"/{name}"


def variant_condition(slug: str, name: str) -> str:
    """A condition testing whether one textual variant is wanted."""
    return (
        '<tei:fs type="opensiddur:variant">'
        f'<tei:f name="{variant_urn(slug, name)}"><tei:binary value="true"/></tei:f>'
        "</tei:fs>"
    )


# --------------------------------------------------------------------------------------
# Scopes
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Paragraphs:
    """Whole numbered paragraphs of a section, inclusive.

    ``bracketed`` says the source parenthesises the whole passage, in which case the brackets
    are dropped: the markers now express what they meant.
    """

    first: int
    last: int | None = None
    bracketed: bool = False
    #: Whether the passage is ``type="marked"``: by default, whether the source brackets it.
    marked: bool | None = None

    @property
    def is_marked(self) -> bool:
        return self.bracketed if self.marked is None else self.marked

    @property
    def through(self) -> int:
        return self.last if self.last is not None else self.first


@dataclass(frozen=True)
class Inline:
    """A run of words inside a paragraph, located by the text on either side.

    ``bracketed`` says the run is parenthesised in the source, in which case each marker takes
    the place of the bracket it replaces rather than sitting beside it: the markup now
    expresses what the brackets meant, and leaving both would say it twice. Set it false where
    the source never bracketed the words at all.
    """

    before_text: str
    after_text: str
    end_before_text: str
    end_after_text: str
    bracketed: bool = True
    #: Whether the passage is ``type="marked"``: by default, whether the source brackets it.
    #: Set it where the source's marking was lost -- a born-digital text that brackets every
    #: other such passage -- to restore the marking without swallowing brackets not there.
    marked: bool | None = None

    @property
    def is_marked(self) -> bool:
        return self.bracketed if self.marked is None else self.marked


@dataclass(frozen=True)
class Transclusion:
    """A whole section, marked around its transclusion in the parent document.

    A section's presence is decided when it is included, so the whole file is transcluded or it
    is not; the child stands as an unconditional document in its own right. Neither source
    marks a section off as a whole, so its scope is never ``type="marked"``.
    """

    child_slug: str
    bracketed = False
    is_marked = False


Scope = Paragraphs | Inline | Transclusion


@dataclass(frozen=True)
class Conditional:
    """One conditional passage, and where it falls in each of the two projects."""

    slug: str
    cond_id: str
    condition: str
    scope_he: Scope | None = None
    scope_en: Scope | None = None
    #: Rubric to emit inside the scope where the source has none of its own. JLPTEI-3.md
    #: requires a conditional-reading instruction to sit inside the text it controls.
    rubric_he: str | None = None
    rubric_en: str | None = None
    #: Editorial gloss, emitted as the j:conditional's own note and so shown only when the
    #: condition cannot be decided. For conditions the sources do not mark at all.
    note_he: str | None = None
    note_en: str | None = None

    def scope_for(self, lang: str) -> Scope | None:
        return self.scope_he if lang == "he" else self.scope_en

    def rubric_for(self, lang: str) -> str | None:
        return self.rubric_he if lang == "he" else self.rubric_en

    def note_for(self, lang: str) -> str | None:
        return self.note_he if lang == "he" else self.note_en


# --------------------------------------------------------------------------------------
# The inventory
# --------------------------------------------------------------------------------------

CONDITIONALS: tuple[Conditional, ...] = (
    # -- Shabbat -----------------------------------------------------------------------
    # Vayechulu, said only when the seder falls on Friday night. The English marks it with a
    # rubric of its own; the Hebrew simply prints it.
    Conditional(
        slug="qaddesh",
        cond_id="qaddesh_vayechulu",
        condition="shabbat",
        scope_he=Paragraphs(1),
        scope_en=Paragraphs(1),
        rubric_he="בשבת מתחילין כאן",
    ),
    # The kiddush's own Shabbat insertions. The Hebrew parenthesises six; the English hoists
    # five of them into rubric spans, and leaves the sixth ("with love") unmarked in the
    # running text, so that one is anchored explicitly on both sides.
    Conditional(
        slug="qaddesh",
        cond_id="qaddesh_shabbatot_limnuha",
        condition="shabbat",
        scope_he=Inline("בְּאַהֲבָה", "שַׁבָּתוֹת", "לִמְנוּחָה וּ", "מוֹעֲדִים"),
    ),
    Conditional(
        slug="qaddesh",
        cond_id="qaddesh_yom_hashabbat",
        condition="shabbat",
        scope_he=Inline("אֶת יוֹם", "הַשַּׁבָּת", "וְאֶת יוֹם", "חַג הַמַּצוֹת"),
    ),
    Conditional(
        slug="qaddesh",
        cond_id="qaddesh_beahava",
        condition="shabbat",
        scope_he=Inline("חֵרוּתֵֽנוּ", "בְּאַהֲבָה", "בְּאַהֲבָה", "מִקְרָא קֹֽדֶשׁ"),
        # The English words are already in the running text, merely never bracketed, so the
        # markers swallow nothing. The 2009 translation is born digital and sets every other
        # Shabbat insertion of this kiddush as "(on Shabbat say: ...)", as the Hebrew brackets
        # this one: the marking and its rubric were lost, and are restored.
        scope_en=Inline(
            "of our liberation", "with love", "with love", "a holy convocation",
            bracketed=False, marked=True,
        ),
        rubric_en="on Shabbat say:",
    ),
    Conditional(
        slug="qaddesh",
        cond_id="qaddesh_veshabbat",
        condition="shabbat",
        scope_he=Inline("מִכָׇּל־הָעַמִּים", "וְשָׁבָּת", "וְשָׁבָּת", "וּמוֹעֲדֵי"),
    ),
    Conditional(
        slug="qaddesh",
        cond_id="qaddesh_beahava_uvratzon",
        condition="shabbat",
        scope_he=Inline("קָׇדְשֶֽׁךָ", "בְּאַהֲבָה וּבְרָצוֹן", "וּבְרָצוֹן", "בְּשִׂמְחָה"),
    ),
    Conditional(
        slug="qaddesh",
        cond_id="qaddesh_mekadesh_hashabbat",
        condition="shabbat",
        scope_he=Inline("מְקַדֵּשׁ", "הַשָּׁבָּת", "הַשָּׁבָּת וְ", "יִשְׂרָאֵל"),
    ),
    # Havdalah, said when the seder falls on Saturday night.
    Conditional(
        slug="qaddesh",
        cond_id="qaddesh_havdalah",
        condition="motzaei_shabbat",
        scope_he=Paragraphs(4),
        scope_en=Paragraphs(4),
        rubric_he="במוצאי שבת מוסיפין",
    ),
    # Retzeh vehachalitzenu in birkat hamazon.
    Conditional(
        slug="barekh",
        cond_id="barekh_retzeh",
        condition="shabbat",
        scope_he=Paragraphs(12),
        scope_en=Paragraphs(12),
        rubric_he="בשבת מוסיפין",
    ),
    # Harachaman … yom shekulo shabbat.
    Conditional(
        slug="barekh",
        cond_id="barekh_harachaman_shabbat",
        condition="shabbat",
        scope_he=Paragraphs(25),
        scope_en=Paragraphs(25),
        rubric_he="בשבת מוסיפין",
    ),
    # The Shabbat insertion in the blessing after wine. Neither side is marked by a span, so
    # both are anchored.
    Conditional(
        slug="al_hagefen",
        cond_id="al_hagefen_retzeh",
        condition="shabbat",
        scope_he=Inline(
            "וְבְׇטָׇהֳרָה", "וּרְצֵה", "בְּיוֹם הַשַּׁבָּת הַזֶּה", "וְשַׂמְחֵֽנוּ"
        ),
        scope_en=Inline("in holiness and purity.", "May it be", "this Sabbath day.", "Let us rejoice"),
    ),
    # -- The two seder nights ------------------------------------------------------------
    Conditional(
        slug="nirtzah",
        cond_id="nirtzah_first_night",
        condition="first_night",
        scope_he=Transclusion("vayehi_bachatzi_halailah"),
        scope_en=Transclusion("vayehi_bachatzi_halailah"),
        rubric_he="בליל ראשון",
        rubric_en="On the first night recite the following:",
    ),
    Conditional(
        slug="nirtzah",
        cond_id="nirtzah_second_night",
        condition="second_night",
        scope_he=Transclusion("vaamartem_zevach_pesach"),
        scope_en=Transclusion("vaamartem_zevach_pesach"),
        rubric_he="בליל שני",
        rubric_en="On the second night recite the following:",
    ),
    Conditional(
        slug="nirtzah",
        cond_id="nirtzah_sefirat_haomer",
        condition="second_night",
        scope_he=Transclusion("sefirat_haomer"),
        scope_en=Transclusion("sefirat_haomer"),
        rubric_he="בליל שני סופרים העומר",
        rubric_en="On the second night of Passover, the first night of the Omer is counted:",
    ),
    # -- Eruv tavshilin ------------------------------------------------------------------
    # Neither source marks this; the condition is editorial, so it goes in the note that is
    # shown only when the condition cannot be decided.
    Conditional(
        slug="pre_seder",
        cond_id="pre_seder_eruv_tavshilin",
        condition="eruv_tavshilin",
        scope_he=Transclusion("eruv_tavshilin"),
        scope_en=Transclusion("eruv_tavshilin"),
        note_he="כשחל יום טוב ביום שישי, מערבין ערב יום טוב",
        note_en=(
            "Prepared before a festival that runs into Shabbat — that is, when the festival "
            "falls on Friday."
        ),
    ),
    # -- Occasions -----------------------------------------------------------------------
    # The running order's own gates: which night or day each part of the book is for. They are
    # for the processor, not the reader -- the book says what each part is in its heading -- so
    # they carry no rubric and no note, and an edition with no date prints the parts as they
    # are (schema/JLPTEI-3.md, *Conditions on a running order*).
    Conditional(
        slug="index",
        cond_id="index_seder",
        condition="seder_night",
        scope_he=Transclusion("seder"),
        scope_en=Transclusion("seder"),
    ),
    Conditional(
        slug="pre_seder",
        cond_id="pre_seder_bediqat_chametz",
        condition="bediqat_chametz",
        scope_he=Transclusion("bediqat_chametz"),
        scope_en=Transclusion("bediqat_chametz"),
    ),
    Conditional(
        slug="pre_seder",
        cond_id="pre_seder_biur_chametz",
        condition="biur_chametz",
        scope_he=Transclusion("biur_chametz"),
        scope_en=Transclusion("biur_chametz"),
    ),
    # -- Quorum --------------------------------------------------------------------------
    # The zimmun: the invitation to bless, said only when three have eaten together.
    Conditional(
        slug="barekh",
        cond_id="barekh_zimmun",
        condition="zimmun",
        scope_he=Paragraphs(1, 6),
        scope_en=Paragraphs(1, 6),
        rubric_he="בזימון",
    ),
    # Elohenu, added to the invitation when ten are present. Nested inside the zimmun.
    Conditional(
        slug="barekh",
        cond_id="barekh_minyan_nevarech",
        condition="minyan",
        scope_he=Inline(
            "נְבָרֵךְ", "אֱלֹהֵֽינוּ", "נְבָרֵךְ אֱלֹהֵֽינוּ", "שֶׁאָכַֽלְנוּ"
        ),
    ),
    Conditional(
        slug="barekh",
        cond_id="barekh_minyan_barukh",
        condition="minyan",
        scope_he=Inline(
            "מִשֶּׁלּוֹ בָּרוּךְ", "אֱלֹהֵֽינוּ",
            "בָּרוּךְ אֱלֹהֵֽינוּ", "שֶׁאָכַֽלְנוּ מִשֶּׁלּוֹ וּבְטוּבוֹ",
        ),
    ),
    # The response of those present who have not eaten.
    Conditional(
        slug="barekh",
        cond_id="barekh_not_eaten",
        condition="present_not_eaten",
        scope_he=Paragraphs(5, bracketed=True),
        # The English carries its own rubric for this one, so its scope is derived from the
        # source rather than declared here.
        rubric_he="מי שלא אכל אומר",
    ),
    # -- Household -----------------------------------------------------------------------
    Conditional(
        slug="barekh",
        cond_id="barekh_avi",
        condition="at_fathers_home",
        scope_he=Inline("הוּא יְבָרֵךְ אֶת", "אָבִי", "אָבִי", "מוֹרִי"),
    ),
    Conditional(
        slug="barekh",
        cond_id="barekh_imi",
        condition="at_mothers_home",
        scope_he=Inline("הַזֶּה וְאֶת", "אִמִּי", "אִמִּי", "מוֹרָתִי"),
    ),
    # -- Textual variants ------------------------------------------------------------------
    Conditional(
        slug="lefikhakh",
        cond_id="lefikhakh_shirah_chadashah",
        condition=variant_condition("lefikhakh", "shirah_chadashah"),
        scope_he=Inline("לְפָנָיו", "שִׁירָה חֲדָשָׁה", "שִׁירָה חֲדָשָׁה", "הַלְלוּיָהּ"),
    ),
    Conditional(
        slug="avadim_hayinu",
        cond_id="avadim_hayinu_lefaroh",
        condition=variant_condition("avadim_hayinu", "lefaroh"),
        scope_he=Inline(
            "מְשֻׁעְבָּדִים הָיִינוּ", "לְפַרְעֹה", "לְפַרְעֹה", "בְּמִצְרָיִם. וַאֲפִילוּ"
        ),
    ),
    Conditional(
        slug="korekh",
        cond_id="korekh_pesach",
        condition=variant_condition("korekh", "pesach"),
        scope_he=Inline("כּוֹרֵךְ", "פֶּסַח", "פֶּסַח", "מַצָּה וּמָרוֹר"),
        scope_en=Inline("a sandwich of", "the Passover sacrifice,", "the Passover sacrifice,", "the matzah"),
    ),
    Conditional(
        slug="yehalalukha",
        cond_id="yehalalukha_al",
        condition=variant_condition("yehalalukha", "al"),
        scope_he=Inline("אֱלֹהֵֽינוּ", "עַל", "עַל", "כָּל מַעֲשֶֽׂיךָ"),
    ),
    Conditional(
        slug="asher_gealanu",
        cond_id="asher_gealanu_haggienu",
        condition=variant_condition("asher_gealanu", "haggienu"),
        scope_he=Inline("יַגִּיעֵֽנוּ", "הַגִּיעֵֽנוּ", "הַגִּיעֵֽנוּ", "לְמוֹעֲדִים"),
    ),
)


@dataclass(frozen=True)
class Alternate:
    """Two wordings of one paragraph, exactly one of which is read.

    Not a condition — nothing is added or omitted, one wording is chosen over another — so this
    becomes a ``tei:choice`` of ``j:option`` rather than a ``j:conditional``. The 1822 print
    gives the invitation to bless in both Hebrew and Yiddish this way, the Yiddish in
    parentheses, which is the same typography it uses for conditional text and means something
    different.
    """

    slug: str
    lang: str
    paragraph: int
    #: ``(xml:lang, text)`` per option, in the order the source prints them.
    options: tuple[tuple[str, str], ...]


ALTERNATES: tuple[Alternate, ...] = (
    Alternate(
        slug="barekh",
        lang="he",
        paragraph=1,
        options=(
            ("he", "הב לן ונברך"),
            ("yi", "רבותי וויר וואָללן בענטשן"),
        ),
    ),
)


def alternate_for(slug: str, lang: str, paragraph: int) -> Alternate | None:
    for entry in ALTERNATES:
        if entry.slug == slug and entry.lang == lang and entry.paragraph == paragraph:
            return entry
    return None


#: The condition behind each English rubric the source marks with an instruction span. The
#: parser recovers which words are the rubric and which are the text it governs; this says
#: what the condition is. Every governing rubric must appear here.
RUBRIC_CONDITIONS: dict[str, str] = {
    "on Shabbat say:": "shabbat",
    "if ten are present, add:": "minyan",
    "Alternately, if people are present who did not eat (?!) they respond:": "present_not_eaten",
    "at one’s father’s home, add:": "at_fathers_home",
    "at one’s mother’s home, add:": "at_mothers_home",
    "some add:": None,  # resolved per section, see VARIANT_RUBRIC_SECTIONS
    "some add": None,
}

#: "some add" introduces a different variant in each section it appears in, so the condition
#: comes from the section rather than from the rubric's wording.
VARIANT_RUBRIC_SECTIONS: dict[str, str] = {
    "lefikhakh": "shirah_chadashah",
    "avadim_hayinu": "lefaroh",
}


def condition_for_rubric(rubric: str, slug: str) -> str:
    """The condition a governing English rubric expresses, as a tei:fs fragment."""
    normalised = rubric.strip()
    if normalised not in RUBRIC_CONDITIONS:
        raise ConditionalError(
            f"English rubric {normalised!r} in section {slug} governs text but no condition "
            f"is recorded for it in RUBRIC_CONDITIONS"
        )
    key = RUBRIC_CONDITIONS[normalised]
    if key is None:
        if slug not in VARIANT_RUBRIC_SECTIONS:
            raise ConditionalError(
                f"rubric {normalised!r} introduces a textual variant, but section {slug} has "
                f"no entry in VARIANT_RUBRIC_SECTIONS naming it"
            )
        return variant_condition(slug, VARIANT_RUBRIC_SECTIONS[slug])
    return CONDITIONS[key]


def condition_markup(condition: str) -> str:
    """Resolve a condition given either as a CONDITIONS key or as a literal fragment."""
    return CONDITIONS.get(condition, condition)


def conditionals_for(slug: str) -> list[Conditional]:
    return [entry for entry in CONDITIONALS if entry.slug == slug]


def all_cond_ids() -> set[str]:
    return {entry.cond_id for entry in CONDITIONALS}
