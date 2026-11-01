"""Haggadah section hierarchy and slug helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Literal

from opensiddur.importer.util.hebrew import normalize_hebrew

# Index nodes may contain section headings and body text as well as transclusions.
INDEX_CHILDREN: dict[str, list[str]] = {
    "index": ["pre_seder", "seder"],
    "pre_seder": ["bedikat_chametz", "biur_chametz", "eruv_tavshilin"],
    "seder": [
        "siman_maaseh_sedurim",
        "kadesh",
        "urechatz",
        "karpas",
        "yachatz",
        "magid",
        "rachtzah",
        "motzi_matzah",
        "maror",
        "korech",
        "shulchan_orech",
        "tzafun",
        "barekh",
        "hallel",
        "nirtzah",
    ],
}

# h3 English title -> slug for top-level content sections (non-index).
H3_SLUGS: dict[str, str] = {
    "Search for Leaven": "bedikat_chametz",
    "Elimination of Leaven": "biur_chametz",
    "Mingling of Foods": "eruv_tavshilin",
    "Parts of the Seder": "siman_maaseh_sedurim",
    "Sanctification of the Day": "kadesh",
    "Preliminary Hand Washing": "urechatz",
    "Eating a Vegetable": "karpas",
    "Breaking the Middle Matzah": "yachatz",
    "Discussing the Exodus": "magid",
    "Hand-Washing before the Meal": "rachtzah",
    "Eating the Matzah": "motzi_matzah",
    "Eating the Bitter Herb": "maror",
    "Eating the “Hillel Sandwich”": "korech",
    "Eating the “Hillel Sandwich&#8221;": "korech",
    "Eating a festive meal": "shulchan_orech",
    "Eating the Afikoman": "tzafun",
    "Blessing After Meals": "barekh",
    "Songs of Praise": "hallel",
    "Concluding Songs": "nirtzah",
    "Sefirat HaOmer": "sefirat_haomer",
}

# Explicit slugs for magid subsections (Hebrew first-line prefix -> slug).
MAGID_SUBSECTION_PREFIXES: list[tuple[str, str]] = [
    ("הָא לַחְמָא עַנְיָא", "ha_lachma_anya"),
    ("מַה נִשְׁתַּנָּה", "mah_nishtanah"),
    ("עֲבָדִים הָיִינוּ", "avadim_hayinu"),
    ("מַעֲשֶׂה", "maaseh_be_rabbi_eliezer"),
    ("אָמַר רַבִּי אֶלְעָזָר בֶּן עֲזַרְיָה", "amar_rabbi_elazar_ben_azariah"),
    ("בָּרוּךְ הַמָּקוֹם", "barukh_hamaqom"),
    ("כְּנֶגֶד אַרְבָּעָה בָנִים", "arba_banim"),
    ("חָכָם מַה הוּא אוֹמֵר", "chacham"),
    ("רָשָׁע מַה הוּא אוֹמֵר", "rashaa"),
    ("תָּם מַה הוּא אוֹמֵר", "tam"),
    ("וְשֶׁאֵינוֹ יוֹדֵעַ לִשְׁאוֹל", "she_eino_yodea_lishol"),
    ("יָכוֹל מֵרֹאשׁ חֹדֶשׁ", "yachol_meros_chodesh"),
    ("מִתְּחִלָּה", "matchil_b_genut"),
    ("בָּרוּךְ שׁוֹמֵר", "barukh_shomer"),
    ("וְהִיא שֶׁעָמְדָה", "vehi_sheamda"),
    ("צֵא וּלְמַד", "arami_oved_avi"),
    ("וַיֵּ֣רֶד מִצְרַ֔יְמָה", "vayered_mitsraymah"),
    ("וַיָּ֥גׇר שָׁ֖ם", "vayagar_sham"),
    ("בִּמְתֵ֣י מְעָ֑ט", "bimtei_me_at"),
    ("וַֽיְהִי־שָׁ֕ם לְג֥וֹי גָּד֖וֹל", "vayehi_sham_le_goy_gadol"),
    ("עָצ֥וּם", "atzum"),
    ("וָרָֽב", "varav"),
    ("וַיָּרֵ֧עוּ אֹתָ֛נוּ הַמִּצְרִ֖ים וַיְעַנּ֑וּנוּ", "mitzrim_ra_v_inyu"),
    ("וַיָּרֵ֧עוּ אֹתָ֛נוּ הַמִּצְרִ֖ים", "mitzrim_ra"),
    ("וַיְעַנּ֑וּנוּ", "vay_inyunu"),
    ("וַיִּתְּנ֥וּ עָלֵ֖ינוּ עֲבֹדָ֥ה קָשָֽׁה", "avodah_kasha"),
    ("וַנִּצְעַ֕ק אֶל־יְהוָ֖ה", "vanitzak_hashem"),
    ("וַנִּצְעַ֕ק אֶל־יְהוָ֖ה אֱלֹהֵ֣י אֲבֹתֵ֑ינוּ", "vanitzak_elohai_avot"),
    ("וַיִּשְׁמַ֤ע יְהוָה֙", "vayishma_hashem"),
    ("וַיַּ֧רְא אֶת־עׇנְיֵ֛נוּ", "vayar_et_onyenu"),
    ("וְאֶת־עֲמָלֵ֖נוּ", "ve_et_amalenu"),
    ("וְאֶת־לַחֲצֵֽנוּ", "ve_et_lachatzenu"),
    ("וַיּוֹצִאֵ֤נוּ יְהוָה֙ מִמִּצְרַ֔יִם בְּיָ֤ד חֲזָקָה", "vayotzieinu_yad_chazaka"),
    ("וַיּוֹצִאֵ֤נוּ יְהוָה֙ מִמִּצְרַ֔יִם", "vayotzieinu_mimitzrayim"),
    ("וְעָבַרְתִּ֣י בְאֶֽרֶץ־מִצְרַיִם֮", "ve_avarti_b_eretz_mitzrayim"),
    ("בְּיָ֤ד חֲזָקָה֙", "b_yad_chazaka"),
    ("וּבִזְרֹ֣עַ נְטוּיָ֔ה", "u_vizroa_netuya"),
    ("וּבְמֹרָ֖א גָּדֹ֑ל", "u_v_mora_gadol"),
    ("וּבְאֹת֖וֹת", "u_votot"),
    ("וּבְמֹפְתִֽים", "u_v_moftim"),
    ("דָּבָר אַחֵר", "davar_acher"),
    ("אֵלּוּ עֶשֶׂר מַכּוֹת", "ellu_eser_makkot"),
    ("רַבִּי יְהוּדָה", "rabbi_yehudah_makkot"),
    ("רַבִּי יוֹסֵי הַגְּלִילִי", "rabbi_yossi_hagalili"),
    ("רַבִּי אֱלִיעֶזֶר אוֹמֵר", "rabbi_eliezer_omar"),
    ("רַבִּי עֲקִיבָא אוֹמֵר", "rabbi_akiva_omar"),
    ("כַּמָּה מַעֲלוֹת טוֹבוֹת", "kammah_maalot_tovot"),
    ("עַל אַחַת כַּמָּה וְכַמָּה", "al_achat_kammah"),
    ("רַבָּן גַּמְלִיאֵל הָיָה אוֹמֵר", "rabban_gamliel"),
    ("פֶּסַח", "pesach_mitzvah"),
    ("מַצָּה זוּ", "matzah_zu"),
    ("מָרוֹר זֶה", "maror_zeh"),
    ("בְּכָׇל דּוֹר וָדוֹר", "bekhol_dor_vador"),
    ("לְפִיכָךְ", "lefikach"),
    ("הַ֥לֲלוּ יָ֨הּ", "psalm_113"),
    ("בְּצֵ֣את יִ֭שְׂרָאֵ֖ל", "psalm_114"),
    # The second-cup blessings close Magid on folio 26r. They are matched only inside Magid: the
    # הגפן blessing is word-for-word the fourth-cup one in Nirtzah, so only the parent tells them apart.
    ("בָּרוּךְ אַתָּה יְיָ אֱלֹהֵֽינוּ מֶֽלֶךְ הָעוֹלָם אֲשֶׁר גְּאָלָֽנוּ", "asher_ge_alanu"),
    ("בָּרוּךְ אַתָּה יְיָ אֱלֹהֵֽינוּ מֶֽלֶךְ הָעוֹלָם בּוֹרֵא פְּרִי הַגָּֽפֶן", "hagafen_second_cup"),
]

NIRTZAH_SUBSECTION_PREFIXES: list[tuple[str, str]] = [
    ("חֲסַל סִדּוּר פֶּסַח", "chasal_siddur_pesach"),
    # Split from the same compilation row as Chasal Siddur Pesach: the print puts it before the
    # fourth-cup blessings and Chasal after them, so it has to be addressable on its own.
    ("לְשָּׁנָה הַבָּאָה בִּירוּשָׁלָיִם", "lshana_haba_ah"),
    ("וַיְהִי בַּחֲצִי הַלַּֽיְלָה", "it_happened_at_midnight"),
    ("וַאֲמַרְתֶּם זֶֽבַח פֶּֽסַח", "you_shall_say_pesach"),
    ("כִּי לוֹ נָאֶה", "ki_lo_na_eh"),
    ("אַדִּיר הוּא", "addir_hu"),
    ("אֶחָד מִי יוֹדֵעַ", "echad_mi_yodea"),
    ("חַד גַּדְיָא", "chad_gadya"),
]

# Hallel, folios 30v-35v, plus the fourth-cup blessings the print holds back to 38r.
# Psalms 118 and 136 both open "הודו ליהוה כי טוב כי לעולם חסדו", so 118's prefix must run on into
# its second verse; the two הגפן blessings are distinguished only by what follows "מלך העולם".
HALLEL_SUBSECTION_PREFIXES: list[tuple[str, str]] = [
    ("לֹ֤א לָ֥נוּ יְהֹוָ֗ה", "psalm_115"),
    ("אָ֭הַבְתִּי כִּי־יִשְׁמַ֥ע", "psalm_116"),
    ("הַֽלְל֣וּ אֶת־יְ֭הֹוָה כׇּל־גּוֹיִ֑ם", "psalm_117"),
    ("הוֹד֣וּ לַיהֹוָ֣ה כִּי־ט֑וֹב כִּ֖י לְעוֹלָ֣ם חַסְדּֽוֹ׃ יֹאמַר־נָ֥א יִשְׂרָאֵ֑ל", "psalm_118"),
    ("יְהַלֲלֽוּךָ", "yehalelukha"),
    ("הוֹד֣וּ לַיהֹוָ֣ה כִּי־ט֑וֹב כִּ֖י לְעוֹלָ֣ם חַסְדּֽוֹ׃ ה֭וֹדוּ לֵאלֹהֵ֣י", "psalm_136"),
    ("נִשְׁמַת כָׇּל־חַי", "nishmat"),
    ("הָאֵל בְּתַעֲצֻמוֹת עֻזֶּֽךָ", "ha_el_betaatzumot"),
    ("שׁוֹכֵן עַד מָרוֹם", "shokhen_ad"),
    ("בְּפִי יְשָׁרִים", "befi_yesharim"),
    ("וּבְמַקְהֲלוֹת רִבְבוֹת", "uvmaqhalot"),
    ("יִשְׁתַּבַּח שִׁמְךָ", "yishtabbach"),
    ("בָּרוּךְ אַתָּה יְיָ אֱלֹהֵֽינוּ מֶֽלֶךְ הָעוֹלָם בּוֹרֵא פְּרִי הַגָּֽפֶן", "hagafen_fourth_cup"),
    ("בָּרוּךְ אַתָּה יְיָ אֱלֹהֵֽינוּ מֶֽלֶךְ הָעוֹלָם עַל הַגֶּֽפֶן", "al_hagefen"),
]

# The one complete biblical unit inside Birkat HaMazon.
BARECH_SUBSECTION_PREFIXES: list[tuple[str, str]] = [
    ("שִׁיר הַמַּעֲלוֹת: בְּשׁוּב", "psalm_126"),
]

INDEX_CHILDREN["magid"] = [slug for _, slug in MAGID_SUBSECTION_PREFIXES]
INDEX_CHILDREN["hallel"] = [
    slug for _, slug in HALLEL_SUBSECTION_PREFIXES
    # The fourth-cup blessings are printed on 38r, among the Nirtzah songs, not with Hallel.
    if slug not in ("hagafen_fourth_cup", "al_hagefen")
]
INDEX_CHILDREN["barekh"] = [slug for _, slug in BARECH_SUBSECTION_PREFIXES]

# Transclusion order for nirtzah follows the 1822 print, which differs from the order of the Open
# Siddur compilation, all verified against the facsimile:
#   - Chasal Siddur Pesach (Nirtzah proper) is printed on folio 38r, after Ki Lo Na'eh and the
#     fourth-cup blessings, not before Vayehi Bachatzi HaLailah (35v). Heidenheim places Vayehi
#     Bachatzi HaLailah and Va'amartem Zevach Pesach directly after Yishtabach as the first- and
#     second-night piyyutim.
#   - לשנה הבאה בירושלים comes before the fourth-cup blessings and Chasal Siddur Pesach after them,
#     though the compilation runs them together as one passage.
#   - The fourth-cup blessings are held back from Hallel to here.
#   - Sefirat HaOmer (folio 39r) falls between Adir Hu and Echad Mi Yodea. The compilation lists it
#     as a top-level h3 at the very end; it stays an H3_SLUGS entry because that is how it is
#     parsed, only its position in the tree moves.
# The prefix lists above remain the parsing tables; this list is the document order.
INDEX_CHILDREN["nirtzah"] = [
    "it_happened_at_midnight",
    "you_shall_say_pesach",
    "ki_lo_na_eh",
    "lshana_haba_ah",
    "hagafen_fourth_cup",
    "al_hagefen",
    "chasal_siddur_pesach",
    "addir_hu",
    "sefirat_haomer",
    "echad_mi_yodea",
    "chad_gadya",
]

INDEX_NODES = frozenset(INDEX_CHILDREN.keys())

#: Index nodes that keep text of their own *after* their transclusions. Birkat HaMazon transcludes
#: Psalm 126 and then continues with its own thirty paragraphs, which run from folio 27v to 30v, so
#: unlike the other index nodes it holds page breaks and takes a place of its own in document order.
CONTENT_BEARING_INDEX_NODES = frozenset({"barekh"})


@dataclass
class TextBlock:
    kind: Literal["head", "paragraph", "instruction"]
    hebrew: str = ""
    english: str = ""
    starts_paragraph: bool = False
    #: Set on the two blocks of a conditional passage the source marked as such: ``governs`` on
    #: the rubric, ``governed`` on the text it controls. See
    #: ``parse_compilation.split_parenthetical_instructions``.
    governs: bool = False
    governed: bool = False


@dataclass
class SectionContent:
    slug: str
    blocks: list[TextBlock] = field(default_factory=list)
    #: For an index node, the block index its transclusions sit at, so a parent can hold text both
    #: before and after its children. ``None`` means after everything.
    children_at: int | None = None

    @property
    def hebrew_lines(self) -> list[str]:
        """Paragraph Hebrew text in order (for page-break alignment)."""
        return [block.hebrew for block in self.blocks if block.kind == "paragraph" and block.hebrew]

    @property
    def english_lines(self) -> list[str]:
        return [block.english for block in self.blocks if block.kind == "paragraph" and block.english]


def parent_index_slug(slug: str) -> str | None:
    for parent, children in INDEX_CHILDREN.items():
        if slug in children:
            return parent
    return None


def urn_for_section(slug: str, *, paragraph: int | None = None) -> str:
    if slug == "index":
        base = "urn:x-opensiddur:text:haggadah:haggadah"
    else:
        parent = parent_index_slug(slug)
        if parent in ("magid", "nirtzah", "hallel", "barekh"):
            base = f"urn:x-opensiddur:text:haggadah:{parent}/{slug}"
        else:
            base = f"urn:x-opensiddur:text:haggadah:{slug}"
    if paragraph is not None:
        return f"{base}/{paragraph}"
    return base


def iter_index_files() -> Iterator[str]:
    yield "index"
    for node in INDEX_NODES:
        if node != "index":
            yield node


def leaf_slugs() -> list[str]:
    leaves: list[str] = []
    for parent, children in INDEX_CHILDREN.items():
        for child in children:
            if child not in INDEX_NODES:
                leaves.append(child)
    return leaves


def document_order_slugs() -> list[str]:
    """Section slugs that hold text, in haggadah reading order (for page alignment).

    Index nodes contribute only their children, except those in
    :data:`CONTENT_BEARING_INDEX_NODES`, which follow their children because their own text does.
    """
    order: list[str] = []

    def add_leaves(parent: str) -> None:
        for child in INDEX_CHILDREN[parent]:
            if child in INDEX_NODES:
                add_leaves(child)
            else:
                order.append(child)
        if parent in CONTENT_BEARING_INDEX_NODES:
            order.append(parent)

    add_leaves("index")
    return order


def match_subsection_slug(
    first_line: str,
    prefixes: list[tuple[str, str]],
) -> str | None:
    for prefix, slug in prefixes:
        if first_line.startswith(prefix) or prefix in first_line:
            return slug
    return None


def match_subsection_by_incipit(
    text: str,
    prefixes: list[tuple[str, str]],
) -> str | None:
    """Match ``text`` against prefixes on the consonant skeleton alone.

    Insensitive to vowels, cantillation, punctuation and line breaks, which is what lets the two
    בורא פרי הגפן blessings be told apart from על הגפן: they share their whole opening formula and
    differ only in what follows it, several printed lines in. The prefix must match at the start.
    """
    normalized = normalize_hebrew(text)
    if not normalized:
        return None
    for prefix, slug in prefixes:
        if normalized.startswith(normalize_hebrew(prefix)):
            return slug
    return None
