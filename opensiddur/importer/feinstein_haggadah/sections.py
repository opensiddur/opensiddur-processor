"""Haggadah section hierarchy and slug helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Literal

from opensiddur.importer.util.hebrew import normalize_hebrew

# Index nodes may contain section headings and body text as well as transclusions.
INDEX_CHILDREN: dict[str, list[str]] = {
    "index": ["pre_seder", "seder"],
    "pre_seder": ["bediqat_chametz", "biur_chametz", "eruv_tavshilin"],
    "seder": [
        "siman_lemaasim_sedurim",
        "qaddesh",
        "urechatz",
        "karpas",
        "yachatz",
        "maggid",
        "rachatz",
        "motzi_matzah",
        "maror",
        "korekh",
        "shulchan_orekh",
        "tzafun",
        "barekh",
        "hallel",
        "nirtzah",
    ],
}

# h3 English title -> slug for top-level content sections (non-index).
H3_SLUGS: dict[str, str] = {
    "Search for Leaven": "bediqat_chametz",
    "Elimination of Leaven": "biur_chametz",
    "Mingling of Foods": "eruv_tavshilin",
    "Parts of the Seder": "siman_lemaasim_sedurim",
    "Sanctification of the Day": "qaddesh",
    "Preliminary Hand Washing": "urechatz",
    "Eating a Vegetable": "karpas",
    "Breaking the Middle Matzah": "yachatz",
    "Discussing the Exodus": "maggid",
    "Hand-Washing before the Meal": "rachatz",
    "Eating the Matzah": "motzi_matzah",
    "Eating the Bitter Herb": "maror",
    "Eating the “Hillel Sandwich”": "korekh",
    "Eating the “Hillel Sandwich&#8221;": "korekh",
    "Eating a festive meal": "shulchan_orekh",
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
    ("מַעֲשֶׂה", "maaseh_berabbi_eliezer"),
    ("אָמַר רַבִּי אֶלְעָזָר בֶּן עֲזַרְיָה", "amar_rabbi_elazar_ben_azaryah"),
    ("בָּרוּךְ הַמָּקוֹם", "barukh_hamaqom"),
    ("כְּנֶגֶד אַרְבָּעָה בָנִים", "arbaah_vanim"),
    ("חָכָם מַה הוּא אוֹמֵר", "chakham"),
    ("רָשָׁע מַה הוּא אוֹמֵר", "rasha"),
    ("תָּם מַה הוּא אוֹמֵר", "tam"),
    ("וְשֶׁאֵינוֹ יוֹדֵעַ לִשְׁאוֹל", "vesheeino_yodea_lishol"),
    ("יָכוֹל מֵרֹאשׁ חֹדֶשׁ", "yakhol_merosh_chodesh"),
    ("מִתְּחִלָּה", "matchil_bignut"),
    ("בָּרוּךְ שׁוֹמֵר", "barukh_shomer"),
    ("וְהִיא שֶׁעָמְדָה", "vehi_sheamedah"),
    ("צֵא וּלְמַד", "arami_oved_avi"),
    ("וַיֵּ֣רֶד מִצְרַ֔יְמָה", "vayyered_mitzraimah"),
    ("וַיָּ֥גׇר שָׁ֖ם", "vayyagor_sham"),
    ("בִּמְתֵ֣י מְעָ֑ט", "bimtei_meat"),
    ("וַֽיְהִי־שָׁ֕ם לְג֥וֹי גָּד֖וֹל", "vayehi_sham_legoy_gadol"),
    ("עָצ֥וּם", "atzum"),
    ("וָרָֽב", "varav"),
    ("וַיָּרֵ֧עוּ אֹתָ֛נוּ הַמִּצְרִ֖ים וַיְעַנּ֑וּנוּ", "vayyareu_otanu_hamitzrim_vayeannunu"),
    ("וַיָּרֵ֧עוּ אֹתָ֛נוּ הַמִּצְרִ֖ים", "vayyareu_otanu_hamitzrim"),
    ("וַיְעַנּ֑וּנוּ", "vayeannunu"),
    ("וַיִּתְּנ֥וּ עָלֵ֖ינוּ עֲבֹדָ֥ה קָשָֽׁה", "avodah_qashah"),
    ("וַנִּצְעַ֕ק אֶל־יְהוָ֖ה", "vannitzaq_hashem"),
    ("וַנִּצְעַ֕ק אֶל־יְהוָ֖ה אֱלֹהֵ֣י אֲבֹתֵ֑ינוּ", "vannitzaq_elohei_avoteinu"),
    ("וַיִּשְׁמַ֤ע יְהוָה֙", "vayyishma_hashem"),
    ("וַיַּ֧רְא אֶת־עׇנְיֵ֛נוּ", "vayyar_et_onyenu"),
    ("וְאֶת־עֲמָלֵ֖נוּ", "veet_amalenu"),
    ("וְאֶת־לַחֲצֵֽנוּ", "veet_lachatzenu"),
    ("וַיּוֹצִאֵ֤נוּ יְהוָה֙ מִמִּצְרַ֔יִם בְּיָ֤ד חֲזָקָה", "vayyotzienu_beyad_chazaqah"),
    ("וַיּוֹצִאֵ֤נוּ יְהוָה֙ מִמִּצְרַ֔יִם", "vayyotzienu_mimitzrayim"),
    ("וְעָבַרְתִּ֣י בְאֶֽרֶץ־מִצְרַיִם֮", "veavarti_veeretz_mitzrayim"),
    ("בְּיָ֤ד חֲזָקָה֙", "beyad_chazaqah"),
    ("וּבִזְרֹ֣עַ נְטוּיָ֔ה", "uvizroa_netuyah"),
    ("וּבְמֹרָ֖א גָּדֹ֑ל", "uvemora_gadol"),
    ("וּבְאֹת֖וֹת", "uveotot"),
    ("וּבְמֹפְתִֽים", "uvemofetim"),
    ("דָּבָר אַחֵר", "davar_acher"),
    ("אֵלּוּ עֶשֶׂר מַכּוֹת", "ellu_eser_makkot"),
    ("רַבִּי יְהוּדָה", "rabbi_yehudah_hayah_noten"),
    ("רַבִּי יוֹסֵי הַגְּלִילִי", "rabbi_yosei_hagelili"),
    ("רַבִּי אֱלִיעֶזֶר אוֹמֵר", "rabbi_eliezer_omer"),
    ("רַבִּי עֲקִיבָא אוֹמֵר", "rabbi_aqiva_omer"),
    ("כַּמָּה מַעֲלוֹת טוֹבוֹת", "kammah_maalot_tovot"),
    ("עַל אַחַת כַּמָּה וְכַמָּה", "al_achat_kammah"),
    ("רַבָּן גַּמְלִיאֵל הָיָה אוֹמֵר", "rabban_gamliel"),
    ("פֶּסַח", "pesach_shehayu"),
    ("מַצָּה זוּ", "matzah_zu"),
    ("מָרוֹר זֶה", "maror_zeh"),
    ("בְּכָׇל דּוֹר וָדוֹר", "bekhol_dor_vador"),
    ("לְפִיכָךְ", "lefikhakh"),
    ("הַ֥לֲלוּ יָ֨הּ", "psalm_113"),
    ("בְּצֵ֣את יִ֭שְׂרָאֵ֖ל", "psalm_114"),
    # The second-cup blessings close Magid on folio 26r. They are matched only inside Magid: the
    # הגפן blessing is word-for-word the fourth-cup one in Nirtzah, so only the parent tells them apart.
    ("בָּרוּךְ אַתָּה יְיָ אֱלֹהֵֽינוּ מֶֽלֶךְ הָעוֹלָם אֲשֶׁר גְּאָלָֽנוּ", "asher_gealanu"),
    ("בָּרוּךְ אַתָּה יְיָ אֱלֹהֵֽינוּ מֶֽלֶךְ הָעוֹלָם בּוֹרֵא פְּרִי הַגָּֽפֶן", "kos_sheni"),
]

NIRTZAH_SUBSECTION_PREFIXES: list[tuple[str, str]] = [
    ("חֲסַל סִדּוּר פֶּסַח", "chasal_siddur_pesach"),
    # Split from the same compilation row as Chasal Siddur Pesach: the print puts it before the
    # fourth-cup blessings and Chasal after them, so it has to be addressable on its own.
    ("לְשָּׁנָה הַבָּאָה בִּירוּשָׁלָיִם", "leshanah_habaah"),
    ("וַיְהִי בַּחֲצִי הַלַּֽיְלָה", "vayehi_bachatzi_halailah"),
    ("וַאֲמַרְתֶּם זֶֽבַח פֶּֽסַח", "vaamartem_zevach_pesach"),
    ("כִּי לוֹ נָאֶה", "ki_lo_naeh"),
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
    ("יְהַלֲלֽוּךָ", "yehalalukha"),
    ("הוֹד֣וּ לַיהֹוָ֣ה כִּי־ט֑וֹב כִּ֖י לְעוֹלָ֣ם חַסְדּֽוֹ׃ ה֭וֹדוּ לֵאלֹהֵ֣י", "psalm_136"),
    ("נִשְׁמַת כָׇּל־חַי", "nishmat"),
    ("הָאֵל בְּתַעֲצֻמוֹת עֻזֶּֽךָ", "hael_betaatzumot"),
    ("שׁוֹכֵן עַד מָרוֹם", "shokhen_ad"),
    ("בְּפִי יְשָׁרִים", "befi_yesharim"),
    ("וּבְמַקְהֲלוֹת רִבְבוֹת", "uvemaqhalot"),
    ("יִשְׁתַּבַּח שִׁמְךָ", "yishtabbach"),
    ("בָּרוּךְ אַתָּה יְיָ אֱלֹהֵֽינוּ מֶֽלֶךְ הָעוֹלָם בּוֹרֵא פְּרִי הַגָּֽפֶן", "kos_revii"),
    ("בָּרוּךְ אַתָּה יְיָ אֱלֹהֵֽינוּ מֶֽלֶךְ הָעוֹלָם עַל הַגֶּֽפֶן", "al_hagefen"),
]

# The one complete biblical unit inside Birkat HaMazon.
BARECH_SUBSECTION_PREFIXES: list[tuple[str, str]] = [
    ("שִׁיר הַמַּעֲלוֹת: בְּשׁוּב", "psalm_126"),
]

INDEX_CHILDREN["maggid"] = [slug for _, slug in MAGID_SUBSECTION_PREFIXES]
INDEX_CHILDREN["hallel"] = [
    slug for _, slug in HALLEL_SUBSECTION_PREFIXES
    # The fourth-cup blessings are printed on 38r, among the Nirtzah songs, not with Hallel.
    if slug not in ("kos_revii", "al_hagefen")
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
    "vayehi_bachatzi_halailah",
    "vaamartem_zevach_pesach",
    "ki_lo_naeh",
    "leshanah_habaah",
    "kos_revii",
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


#: Sections whose text is shared liturgy, named by its own URN rather than under `haggadah:`
#: (specs/SIDDUR_URN_SCHEME.md, "Unification with the haggadah namespace"). Each is one
#: paragraph, so it has no paragraph URN of its own.
SHARED_TEXTS = {
    "nishmat": "urn:x-opensiddur:text:prayer:nishmat",
    "shokhen_ad": "urn:x-opensiddur:text:prayer:shokhen_ad",
    "psalm_115": "urn:x-opensiddur:text:prayer:hallel/psalm_115",
    "psalm_116": "urn:x-opensiddur:text:prayer:hallel/psalm_116",
    "psalm_117": "urn:x-opensiddur:text:prayer:hallel/psalm_117",
    "psalm_118": "urn:x-opensiddur:text:prayer:hallel/psalm_118",
    "psalm_136": "urn:x-opensiddur:text:prayer:hallel_hagadol",
    "al_hagefen": "urn:x-opensiddur:text:prayer:berakhah_acharonah/al_hagefen",
    "sefirat_haomer": "urn:x-opensiddur:text:prayer:sefirat_haomer",
    "psalm_113": "urn:x-opensiddur:text:prayer:hallel/psalm_113",
    "psalm_114": "urn:x-opensiddur:text:prayer:hallel/psalm_114",
    "yehalalukha": "urn:x-opensiddur:text:prayer:hallel/yehalelukha",
    "hael_betaatzumot": "urn:x-opensiddur:text:prayer:hael_betaatzumot",
    "befi_yesharim": "urn:x-opensiddur:text:prayer:befi_yesharim",
    "uvemaqhalot": "urn:x-opensiddur:text:prayer:uvemaqhalot",
    "yishtabbach": "urn:x-opensiddur:text:prayer:yishtabbach",
    "psalm_126": "urn:x-opensiddur:text:prayer:birkat_hamazon/shir_hamaalot",
}

#: Paragraphs of a section that are shared liturgy, named by their own URNs: Birkat Hamazon's
#: and Kiddush's parts, each a paragraph of the edition. A paragraph not listed keeps its
#: `haggadah:` URN (Havdalah in Kiddush; the cup and Shefokh after Birkat Hamazon).
SHARED_PARAGRAPHS = {
    ("barekh", 1): "urn:x-opensiddur:text:prayer:birkat_hamazon/zimmun/hav_lan",
    ("barekh", 2): "urn:x-opensiddur:text:prayer:birkat_hamazon/zimmun/yehi_shem",
    ("barekh", 3): "urn:x-opensiddur:text:prayer:birkat_hamazon/zimmun/nevarekh",
    ("barekh", 4): "urn:x-opensiddur:text:prayer:birkat_hamazon/zimmun/barukh_sheakhalnu",
    ("barekh", 5): "urn:x-opensiddur:text:prayer:birkat_hamazon/zimmun/barukh_umevorakh",
    ("barekh", 6): "urn:x-opensiddur:text:prayer:birkat_hamazon/zimmun/barukh_hu",
    ("barekh", 7): "urn:x-opensiddur:text:prayer:birkat_hamazon/hazan",
    ("barekh", 8): "urn:x-opensiddur:text:prayer:birkat_hamazon/nodeh_lekha",
    ("barekh", 9): "urn:x-opensiddur:text:prayer:birkat_hamazon/veal_hakol",
    ("barekh", 10): "urn:x-opensiddur:text:prayer:birkat_hamazon/rachem",
    ("barekh", 11): "urn:x-opensiddur:text:prayer:birkat_hamazon/eloheinu_avinu",
    ("barekh", 12): "urn:x-opensiddur:text:prayer:birkat_hamazon/retzeh_vehachalitzenu",
    ("barekh", 13): "urn:x-opensiddur:text:prayer:yaaleh_veyavo",
    ("barekh", 14): "urn:x-opensiddur:text:prayer:birkat_hamazon/uveneh_yerushalayim",
    ("barekh", 15): "urn:x-opensiddur:text:prayer:birkat_hamazon/hatov_vehametiv",
    ("barekh", 16): "urn:x-opensiddur:text:prayer:birkat_hamazon/harachaman/yimlokh",
    ("barekh", 17): "urn:x-opensiddur:text:prayer:birkat_hamazon/harachaman/yitbarakh",
    ("barekh", 18): "urn:x-opensiddur:text:prayer:birkat_hamazon/harachaman/yishtabbach",
    ("barekh", 19): "urn:x-opensiddur:text:prayer:birkat_hamazon/harachaman/yefarnesenu",
    ("barekh", 20): "urn:x-opensiddur:text:prayer:birkat_hamazon/harachaman/yishbor_ullenu",
    ("barekh", 21): "urn:x-opensiddur:text:prayer:birkat_hamazon/harachaman/yishlach_berakhah",
    ("barekh", 22): "urn:x-opensiddur:text:prayer:birkat_hamazon/harachaman/yishlach_lanu",
    ("barekh", 23): "urn:x-opensiddur:text:prayer:birkat_hamazon/harachaman/yevarekh",
    ("barekh", 24): "urn:x-opensiddur:text:prayer:birkat_hamazon/bamarom",
    ("barekh", 25): "urn:x-opensiddur:text:prayer:birkat_hamazon/harachaman/yanchilenu_shabbat",
    ("barekh", 26): "urn:x-opensiddur:text:prayer:birkat_hamazon/harachaman/yanchilenu_tov",
    ("barekh", 27): "urn:x-opensiddur:text:prayer:birkat_hamazon/harachaman/yezakkenu",
    ("barekh", 28): "urn:x-opensiddur:text:prayer:birkat_hamazon/yiru_et_adonai",
    ("qaddesh", 1): "urn:x-opensiddur:text:prayer:kiddush/vayekhulu",
    ("qaddesh", 2): "urn:x-opensiddur:text:prayer:kiddush/savri",
    ("qaddesh", 3): "urn:x-opensiddur:text:prayer:kiddush/asher_bachar_banu",
    ("qaddesh", 5): "urn:x-opensiddur:text:prayer:shehecheyanu",
}


def urn_for_section(slug: str, *, paragraph: int | None = None) -> str | None:
    """The URN of a section, or of one of its paragraphs. A shared text's paragraph has
    none (:data:`SHARED_TEXTS`); a shared paragraph has its own (:data:`SHARED_PARAGRAPHS`)."""
    if slug in SHARED_TEXTS:
        return None if paragraph is not None else SHARED_TEXTS[slug]
    if (slug, paragraph) in SHARED_PARAGRAPHS:
        return SHARED_PARAGRAPHS[slug, paragraph]
    if slug == "index":
        base = "urn:x-opensiddur:text:haggadah:haggadah"
    else:
        parent = parent_index_slug(slug)
        if parent in ("maggid", "nirtzah", "hallel", "barekh"):
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
