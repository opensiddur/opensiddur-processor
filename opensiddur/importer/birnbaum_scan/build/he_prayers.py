# -*- coding: utf-8 -*-
"""The Hebrew text of the weekday shacharit Amidah, read off printed pages 81-97.

One entry per prayer file. Each is (file name, title, urn slug, first page, last page,
body). The body is hand-authored: a division holds content or subdivisions but never
both, so words that share a division with a conditional get a division of their own --
one carrying a URN, because it names a text. An unnamed wrapper would satisfy the rule
too and name nothing, which is a level to see through; see the skill's note on divisions.
"""
import functools

from .common import PRAYER, cond, endcond, feature, AGG, HOL, SERVICE, RECITATION, QUORUM
from . import common

#: Every page break in this module belongs to the Amidah's printing. Bound once here
#: because common.pb takes no default sigil -- see common.SIGIL_AMIDAH.
pb = functools.partial(common.pb, sigil=common.SIGIL_AMIDAH)

U = PRAYER


#: Paragraphs handed to `wrap` sit one level inside the division it opens at eight.
PARA_INDENT = 10


def d(urn, *paras, indent=8):
    """A division carrying a URN and holding its paragraphs, or the paragraphs alone.

    ``d(None, ...)`` returns the paragraphs by themselves, for `wrap` to put inside the
    division it opens. It used to return them inside a second, unnamed division, which
    named nothing and grouped nothing -- a level for a reader to see through. The rule
    that a division holds content or subdivisions but never both is real, but it bites
    where a division would hold words alongside a conditional, and every such division
    here carries a URN of its own. So nothing ever needed the unnamed one.

    `indent` governs the named form only; bare paragraphs take :data:`PARA_INDENT`,
    because `wrap` always opens its division at eight.
    """
    if urn is None:
        pad = " " * PARA_INDENT
        return "\n".join(f"{pad}<tei:p>{p}</tei:p>" for p in paras)
    pad = " " * indent
    inner = "\n".join(f"{pad}  <tei:p>{p}</tei:p>" for p in paras)
    return f'{pad}<tei:div corresp="{urn}">\n{inner}\n{pad}</tei:div>'


def wrap(urn, inner):
    return f'        <tei:div corresp="{urn}">\n{inner}\n        </tei:div>'


AYT = feature(AGG, "aseret-ymei-tshuva")

PRAYERS = []


def prayer(name, title, slug, first, last, body):
    PRAYERS.append(dict(name=name, title=title, urn=U + slug, first=first, last=last, body=body))


# ---------------------------------------------------------------- 81
prayer("amidah_adonai_sefatai", "אֲדֹנָי שְׂפָתַי תִּפְתָּח", "amidah/adonai_sefatai", 81, 81,
    wrap(U + "amidah/adonai_sefatai", d(None,
        f'{pb(81)}אֲדֹנָי, שְׂפָתַי תִּפְתָּח, וּפִי יַגִּיד תְּהִלָּתֶֽךָ.', indent=10)))

prayer("amidah_avot", "בִּרְכַּת אָבוֹת", "amidah/avot", 81, 83, "\n".join([
    f'        <tei:div corresp="{U}amidah/avot">',
    d(U + "amidah/avot/barukh_attah", "בָּרוּךְ אַתָּה, יְיָ אֱלֹהֵֽינוּ וֵאלֹהֵי אֲבוֹתֵֽינוּ, אֱלֹהֵי אַבְרָהָם, אֱלֹהֵי יִצְחָק, "
            "וֵאלֹהֵי יַעֲקֹב, הָאֵל הַגָּדוֹל הַגִּבּוֹר וְהַנּוֹרָא, אֵל עֶלְיוֹן, גּוֹמֵל חֲסָדִים טוֹבִים, "
            "וְקוֹנֵה הַכֹּל, וְזוֹכֵר חַסְדֵי אָבוֹת, וּמֵבִיא גוֹאֵל לִבְנֵי בְנֵיהֶם לְמַֽעַן שְׁמוֹ בְּאַהֲבָה.", indent=10),
    cond("cond_avot_aseret", note="Between Rosh Hashanah and Yom Kippur add:", fs=AYT),
    d(U + "amidah/avot/zokhrenu",
      f'({pb(83)}זָכְרֵֽנוּ לְחַיִּים, מֶֽלֶךְ חָפֵץ בַּחַיִּים, וְכָתְבֵֽנוּ בְּסֵֽפֶר הַחַיִּים, '
      f'לְמַעַנְךָ אֱלֹהִים חַיִּים.)', indent=10),
    endcond("cond_avot_aseret"),
    d(U + "amidah/avot/magen_avraham",
      "מֶֽלֶךְ עוֹזֵר וּמוֹשִֽׁיעַ וּמָגֵן. בָּרוּךְ אַתָּה, יְיָ, מָגֵן אַבְרָהָם.", indent=10),
    "        </tei:div>"]))

# ---------------------------------------------------------------- 83
prayer("amidah_gevurot", "בִּרְכַּת גְּבוּרוֹת", "amidah/gevurot", 83, 83, "\n".join([
    f'        <tei:div corresp="{U}amidah/gevurot">',
    d(U + "amidah/gevurot/attah_gibbor", "אַתָּה גִבּוֹר לְעוֹלָם, אֲדֹנָי; מְחַיֵּה מֵתִים אַתָּה, רַב לְהוֹשִֽׁיעַ.", indent=10),
    cond("cond_gevurot_geshem", note="Between Sukkoth and Pesaḥ add:",
         fs=feature(AGG, "geshem")),
    d(U + "amidah/gevurot/mashiv_haruach",
      "(מַשִּׁיב הָרֽוּחַ וּמוֹרִיד הַגָּֽשֶׁם.)", indent=10),
    endcond("cond_gevurot_geshem"),
    d(U + "amidah/gevurot/mekhalkel_chayyim", "מְכַלְכֵּל חַיִּים בְּחֶֽסֶד, מְחַיֵּה מֵתִים בְּרַחֲמִים רַבִּים, סוֹמֵךְ נוֹפְלִים, וְרוֹפֵא חוֹלִים, "
            "וּמַתִּיר אֲסוּרִים, וּמְקַיֵּם אֱמוּנָתוֹ לִישֵׁנֵי עָפָר. מִי כָמֽוֹךָ, בַּֽעַל גְּבוּרוֹת, "
            "וּמִי דּֽוֹמֶה לָּךְ, מֶֽלֶךְ מֵמִית וּמְחַיֶּה וּמַצְמִֽיחַ יְשׁוּעָה.", indent=10),
    cond("cond_gevurot_aseret", note="Between Rosh Hashanah and Yom Kippur add:", fs=AYT),
    d(U + "amidah/gevurot/mi_khamokha",
      "(מִי כָמֽוֹךָ, אַב הָרַחֲמִים, זוֹכֵר יְצוּרָיו לְחַיִּים בְּרַחֲמִים.)", indent=10),
    endcond("cond_gevurot_aseret"),
    d(U + "amidah/gevurot/mechayyeh_hametim",
      "וְנֶאֱמָן אַתָּה לְהַחֲיוֹת מֵתִים. בָּרוּךְ אַתָּה, יְיָ, מְחַיֵּה הַמֵּתִים.", indent=10),
    "        </tei:div>"]))

# ---------------------------------------------------------------- 83-85: the Reader's Kedushah
prayer("amidah_qedushah", "קְדֻשָּׁה", "amidah/qedushah", 83, 85, "\n".join([
    f'        <tei:div corresp="{U}amidah/qedushah">',
    cond("cond_qedushah_repetition",
         note="When the Reader repeats the Shemoneh Esreh, the following Kedushah is said:",
         fs="<j:all>"+feature(RECITATION, "repetition")+feature(QUORUM, "minyan")+"</j:all>"),
    d(U + "amidah/qedushah/neqaddesh",
      "נְקַדֵּשׁ אֶת שִׁמְךָ בָּעוֹלָם כְּשֵׁם שֶׁמַּקְדִּישִׁים אוֹתוֹ בִּשְׁמֵי מָרוֹם, "
      "כַּכָּתוּב עַל יַד נְבִיאֶֽךָ: וְקָרָא זֶה אֶל זֶה וְאָמַר:", indent=10),
    d(U + "amidah/qedushah/qadosh",
      "קָדוֹשׁ, קָדוֹשׁ, קָדוֹשׁ יְיָ צְבָאוֹת; מְלֹא כָל הָאָֽרֶץ כְּבוֹדוֹ.", indent=10),
    f'        <tei:div corresp="{U}amidah/qedushah/leummatam">',
    '          <tei:note type="instruction" xml:lang="en" corresp="urn:x-opensiddur:instruction:role/reader">Reader</tei:note>',
    "          <tei:p>לְעֻמָּתָם בָּרוּךְ יֹאמֵֽרוּ—</tei:p>",
    "        </tei:div>",
    d(U + "amidah/qedushah/barukh_kevod", "בָּרוּךְ כְּבוֹד יְיָ מִמְּקוֹמוֹ.", indent=10),
    f'        <tei:div corresp="{U}amidah/qedushah/uvdivrei">',
    '          <tei:note type="instruction" xml:lang="en" corresp="urn:x-opensiddur:instruction:role/reader">Reader</tei:note>',
    "          <tei:p>וּבְדִבְרֵי קָדְשְׁךָ כָּתוּב לֵאמֹר:</tei:p>",
    "        </tei:div>",
    d(U + "amidah/qedushah/yimlokh",
      "יִמְלֹךְ יְיָ לְעוֹלָם, אֱלֹהַֽיִךְ צִיּוֹן לְדֹר וָדֹר; הַלְלוּיָהּ.", indent=10),
    f'        <tei:div corresp="{U}amidah/qedushah/ledor_vador">',
    '          <tei:note type="instruction" xml:lang="en" corresp="urn:x-opensiddur:instruction:role/reader">Reader</tei:note>',
    f"          <tei:p>{pb(85)}לְדוֹר וָדוֹר נַגִּיד גָּדְלֶֽךָ, וּלְנֵֽצַח נְצָחִים קְדֻשָּׁתְךָ נַקְדִּישׁ, "
    "וְשִׁבְחֲךָ אֱלֹהֵֽינוּ מִפִּֽינוּ לֹא יָמוּשׁ לְעוֹלָם וָעֶד, כִּי אֵל מֶֽלֶךְ גָּדוֹל וְקָדוֹשׁ אָֽתָּה.</tei:p>",
    "        </tei:div>",
    # The asterisk marks the seal as substitutable: on the Ten Days הָאֵל הַקָּדוֹשׁ is NOT
    # said and הַמֶּלֶךְ הַקָּדוֹשׁ stands in its place. Two exclusive readings, not an addition.
    cond("cond_qedushah_seal_ordinary", fs=AYT, negate=True, marked=True),
    d(U + "amidah/qedushah/hael_haqadosh",
      "בָּרוּךְ אַתָּה, יְיָ, הָאֵל הַקָּדוֹשׁ.", indent=10),
    endcond("cond_qedushah_seal_ordinary"),
    cond("cond_qedushah_seal_aseret",
         note="Between Rosh Hashanah and Yom Kippur substitute:", fs=AYT),
    d(U + "amidah/qedushah/hamelekh_haqadosh",
      "(בָּרוּךְ אַתָּה, יְיָ, הַמֶּֽלֶךְ הַקָּדוֹשׁ.)", indent=10),
    endcond("cond_qedushah_seal_aseret"),
    endcond("cond_qedushah_repetition"),
    "        </tei:div>"]))

# ---------------------------------------------------------------- 85
prayer("amidah_qedushat_hashem", "קְדֻשַּׁת הַשֵּׁם", "amidah/qedushat_hashem", 85, 85, "\n".join([
    f'        <tei:div corresp="{U}amidah/qedushat_hashem">',
    d(U + "amidah/qedushat_hashem/attah_qadosh", "אַתָּה קָדוֹשׁ וְשִׁמְךָ קָדוֹשׁ, וּקְדוֹשִׁים בְּכָל יוֹם יְהַלְלֽוּךָ סֶּֽלָה.", indent=10),
    cond("cond_qh_seal_ordinary", fs=AYT, negate=True, marked=True),
    d(U + "amidah/qedushat_hashem/hael_haqadosh",
      "בָּרוּךְ אַתָּה, יְיָ, הָאֵל הַקָּדוֹשׁ.", indent=10),
    endcond("cond_qh_seal_ordinary"),
    cond("cond_qh_seal_aseret",
         note="Between Rosh Hashanah and Yom Kippur substitute:", fs=AYT),
    d(U + "amidah/qedushat_hashem/hamelekh_haqadosh",
      "(בָּרוּךְ אַתָּה, יְיָ, הַמֶּֽלֶךְ הַקָּדוֹשׁ.)", indent=10),
    endcond("cond_qh_seal_aseret"),
    "        </tei:div>"]))

for nm, ti, sl, txt in [
    ("amidah_binah", "בִּינָה", "amidah/binah",
     "אַתָּה חוֹנֵן לְאָדָם דַּֽעַת, וּמְלַמֵּד לֶאֱנוֹשׁ בִּינָה. חָנֵּֽנוּ מֵאִתְּךָ דֵּעָה, בִּינָה וְהַשְׂכֵּל. "
     "בָּרוּךְ אַתָּה, יְיָ, חוֹנֵן הַדָּֽעַת."),
    ("amidah_teshuvah", "תְּשׁוּבָה", "amidah/teshuvah",
     "הֲשִׁיבֵֽנוּ אָבִֽינוּ לְתוֹרָתֶֽךָ, וְקָרְבֵֽנוּ מַלְכֵּֽנוּ לַעֲבוֹדָתֶֽךָ, וְהַחֲזִירֵֽנוּ בִּתְשׁוּבָה שְׁלֵמָה "
     "לְפָנֶֽיךָ. בָּרוּךְ אַתָּה, יְיָ, הָרוֹצֶה בִּתְשׁוּבָה."),
    ("amidah_selichah", "סְלִיחָה", "amidah/selichah",
     "סְלַח לָֽנוּ אָבִֽינוּ כִּי חָטָֽאנוּ, מְחַל לָֽנוּ מַלְכֵּֽנוּ כִּי פָשָֽׁעְנוּ, כִּי מוֹחֵל וְסוֹלֵֽחַ אָֽתָּה. "
     "בָּרוּךְ אַתָּה, יְיָ, חַנּוּן הַמַּרְבֶּה לִסְלֹֽחַ."),
]:
    prayer(nm, ti, sl, 85, 85, wrap(U + sl, d(None, txt, indent=10)))

prayer("amidah_geullah", "גְּאוּלָּה", "amidah/geullah", 85, 85, "\n".join([
    f'        <tei:div corresp="{U}amidah/geullah">',
    d(U + "amidah/geullah/reeh_na", "רְאֵה נָא בְעָנְיֵֽנוּ וְרִיבָה רִיבֵֽנוּ, וּגְאָלֵֽנוּ מְהֵרָה לְמַֽעַן שְׁמֶֽךָ, כִּי גוֹאֵל חָזָק אָֽתָּה. "
            "בָּרוּךְ אַתָּה, יְיָ, גּוֹאֵל יִשְׂרָאֵל.", indent=10),
    # Two tests, and they combine with j:all only because both carry a value: a fast day,
    # and the Reader's repetition. Tish'ah b'Av is excluded by name in the rubric.
    cond("cond_geullah_aneinu",
         note="On fast days (except Tish‘ah b’Av) the Reader adds:",
         fs="\n".join(["          <j:all>", feature(AGG, "minor-fast"),
                       feature(RECITATION, "repetition"), feature(QUORUM, "minyan"), "          </j:all>"])),
    d(U + "amidah/aneinu",
      "(עֲנֵֽנוּ, יְיָ, עֲנֵֽנוּ בְּיוֹם צוֹם תַּעֲנִיתֵֽנוּ, כִּי בְצָרָה גְדוֹלָה אֲנָֽחְנוּ. אַל תֵּֽפֶן אֶל רִשְׁעֵֽנוּ, "
      "וְאַל תַּסְתֵּר פָּנֶֽיךָ מִמֶּֽנּוּ, וְאַל תִּתְעַלַּם מִתְּחִנָּתֵֽנוּ. הֱיֵה נָא קָרוֹב לְשַׁוְעָתֵֽנוּ, יְהִי נָא "
      "חַסְדְּךָ לְנַחֲמֵֽנוּ; טֶֽרֶם נִקְרָא אֵלֶֽיךָ עֲנֵֽנוּ, כַּדָּבָר שֶׁנֶּאֱמַר: וְהָיָה טֶֽרֶם יִקְרָֽאוּ, וַאֲנִי "
      "אֶעֱנֶה; עוֹד הֵם מְדַבְּרִים, וַאֲנִי אֶשְׁמָע. כִּי אַתָּה, יְיָ, הָעוֹנֶה בְּעֵת צָרָה, פּוֹדֶה וּמַצִּיל "
      "בְּכָל עֵת צָרָה וְצוּקָה. בָּרוּךְ אַתָּה, יְיָ, הָעוֹנֶה בְּעֵת צָרָה.)", indent=10),
    endcond("cond_geullah_aneinu"),
    "        </tei:div>"]))

# ---------------------------------------------------------------- 87
prayer("amidah_refuah", "רְפוּאָה", "amidah/refuah", 87, 87,
    wrap(U + "amidah/refuah", d(None,
        f'{pb(87)}רְפָאֵֽנוּ יְיָ וְנֵרָפֵא, הוֹשִׁיעֵֽנוּ וְנִוָּשֵֽׁעָה, כִּי תְהִלָּתֵֽנוּ אָֽתָּה; וְהַעֲלֵה רְפוּאָה '
        'שְׁלֵמָה לְכָל מַכּוֹתֵֽינוּ, כִּי אֵל מֶֽלֶךְ רוֹפֵא נֶאֱמָן וְרַחֲמָן אָֽתָּה. בָּרוּךְ אַתָּה, יְיָ, '
        'רוֹפֵא חוֹלֵי עַמּוֹ יִשְׂרָאֵל.', indent=10)))

# The seasonal phrase is printed as two columns, each with its own heading. They are
# exclusive alternatives inside one sentence, so each is its own conditional and the
# second negates the first's feature. Birnbaum states the DIASPORA rule as a civil date.
prayer("amidah_shanim", "בִּרְכַּת הַשָּׁנִים", "amidah/shanim", 87, 87, "\n".join([
    f'        <tei:div corresp="{U}amidah/shanim">',
    d(U + "amidah/shanim/barekh_aleinu", "בָּרֵךְ עָלֵֽינוּ, יְיָ אֱלֹהֵֽינוּ, אֶת הַשָּׁנָה הַזֹּאת וְאֶת כָּל מִינֵי תְבוּאָתָהּ לְטוֹבָה,", indent=10),
    cond("cond_shanim_berakhah", note="From Pesaḥ till December 4th say:",
         fs=feature(AGG, "tal-umatar"), negate=True),
    d(U + "amidah/shanim/veten_berakhah", "וְתֵן בְּרָכָה", indent=10),
    endcond("cond_shanim_berakhah"),
    cond("cond_shanim_tal_umatar", note="From December 4th till Pesaḥ say:",
         fs=feature(AGG, "tal-umatar")),
    d(U + "amidah/shanim/veten_tal_umatar", "וְתֵן טַל וּמָטָר לִבְרָכָה", indent=10),
    endcond("cond_shanim_tal_umatar"),
    d(U + "amidah/shanim/al_penei_haadamah", "עַל פְּנֵי הָאֲדָמָה, וְשַׂבְּעֵֽנוּ מִטּוּבָהּ, וּבָרֵךְ שְׁנָתֵֽנוּ כַּשָּׁנִים הַטּוֹבוֹת. "
            "בָּרוּךְ אַתָּה, יְיָ, מְבָרֵךְ הַשָּׁנִים.", indent=10),
    "        </tei:div>"]))

prayer("amidah_qibbutz_galuyot", "קִבּוּץ גָּלֻיּוֹת", "amidah/qibbutz_galuyot", 87, 87,
    wrap(U + "amidah/qibbutz_galuyot", d(None,
        "תְּקַע בְּשׁוֹפָר גָּדוֹל לְחֵרוּתֵֽנוּ, וְשָׂא נֵס לְקַבֵּץ גָּלֻיּוֹתֵֽינוּ, וְקַבְּצֵֽנוּ יַֽחַד מֵאַרְבַּע "
        "כַּנְפוֹת הָאָֽרֶץ. בָּרוּךְ אַתָּה, יְיָ, מְקַבֵּץ נִדְחֵי עַמּוֹ יִשְׂרָאֵל.", indent=10)))

prayer("amidah_mishpat", "בִּרְכַּת מִשְׁפָּט", "amidah/mishpat", 87, 87, "\n".join([
    f'        <tei:div corresp="{U}amidah/mishpat">',
    d(U + "amidah/mishpat/hashivah_shofeteinu", "הָשִֽׁיבָה שׁוֹפְטֵֽינוּ כְּבָרִאשׁוֹנָה, וְיוֹעֲצֵֽינוּ כְּבַתְּחִלָּה; וְהָסֵר מִמֶּֽנּוּ יָגוֹן וַאֲנָחָה; "
            "וּמְלוֹךְ עָלֵֽינוּ, אַתָּה יְיָ לְבַדְּךָ, בְּחֶֽסֶד וּבְרַחֲמִים, וְצַדְּקֵֽנוּ בַּמִּשְׁפָּט.", indent=10),
    cond("cond_mishpat_seal_ordinary", fs=AYT, negate=True, marked=True),
    d(U + "amidah/mishpat/melekh_ohev_tzedaqah",
      "בָּרוּךְ אַתָּה, יְיָ, מֶֽלֶךְ אוֹהֵב צְדָקָה וּמִשְׁפָּט.", indent=10),
    endcond("cond_mishpat_seal_ordinary"),
    cond("cond_mishpat_seal_aseret",
         note="Between Rosh Hashanah and Yom Kippur substitute:", fs=AYT),
    d(U + "amidah/mishpat/hamelekh_hamishpat",
      "(בָּרוּךְ אַתָּה, יְיָ, הַמֶּֽלֶךְ הַמִּשְׁפָּט.)", indent=10),
    endcond("cond_mishpat_seal_aseret"),
    "        </tei:div>"]))

prayer("amidah_minim", "בִּרְכַּת הַמִּינִים", "amidah/minim", 87, 87,
    wrap(U + "amidah/minim", d(None,
        "וְלַמַּלְשִׁינִים אַל תְּהִי תִקְוָה, וְכָל הָרִשְׁעָה כְּרֶֽגַע תֹּאבֵד, וְכָל אֹיְבֶֽיךָ מְהֵרָה יִכָּרֵֽתוּ; "
        "וְהַזֵּדִים מְהֵרָה תְעַקֵּר וּתְשַׁבֵּר וּתְמַגֵּר וְתַכְנִיעַ בִּמְהֵרָה בְיָמֵֽינוּ. בָּרוּךְ אַתָּה, יְיָ, "
        "שׁוֹבֵר אֹיְבִים וּמַכְנִֽיעַ זֵדִים.", indent=10)))

# The page turn falls mid-sentence, on בְּשִׁמְךָ. tei:pb is model.milestoneLike and valid
# inside tei:p, so the paragraph is not broken: pagination and paragraphing are
# orthogonal hierarchies and the printer's break is not a division of the text.
prayer("amidah_tzaddiqim", "בִּרְכַּת צַדִּיקִים", "amidah/tzaddiqim", 87, 89,
    wrap(U + "amidah/tzaddiqim", d(None,
        "עַל הַצַּדִּיקִים וְעַל הַחֲסִידִים, וְעַל זִקְנֵי עַמְּךָ בֵּית יִשְׂרָאֵל וְעַל פְּלֵיטַת סוֹפְרֵיהֶם, "
        "וְעַל גֵּרֵי הַצֶּֽדֶק וְעָלֵֽינוּ, יֶהֱמוּ נָא רַחֲמֶֽיךָ, יְיָ אֱלֹהֵֽינוּ; וְתֵן שָׂכָר טוֹב לְכָל "
        f"הַבּוֹטְחִים בְּשִׁמְךָ{pb(89)} בֶּאֱמֶת, וְשִׂים חֶלְקֵֽנוּ עִמָּהֶם, וּלְעוֹלָם לֹא נֵבוֹשׁ, כִּי בְךָ "
        "בָּטָֽחְנוּ. בָּרוּךְ אַתָּה, יְיָ, מִשְׁעָן וּמִבְטָח לַצַּדִּיקִים.", indent=10)))

# ---------------------------------------------------------------- 89
for nm, ti, sl, txt in [
    ("amidah_yerushalayim", "בִּרְכַּת יְרוּשָׁלַֽיִם", "amidah/yerushalayim",
     "וְלִירוּשָׁלַֽיִם עִירְךָ בְּרַחֲמִים תָּשׁוּב, וְתִשְׁכּוֹן בְּתוֹכָהּ כַּאֲשֶׁר דִּבַּֽרְתָּ; וּבְנֵה אוֹתָהּ "
     "בְּקָרוֹב בְּיָמֵֽינוּ בִּנְיַן עוֹלָם; וְכִסֵּא דָוִד מְהֵרָה לְתוֹכָהּ תָּכִין. בָּרוּךְ אַתָּה, יְיָ, "
     "בּוֹנֵה יְרוּשָׁלָֽיִם."),
    ("amidah_david", "בִּרְכַּת דָּוִד", "amidah/david",
     "אֶת צֶֽמַח דָּוִד עַבְדְּךָ מְהֵרָה תַצְמִֽיחַ, וְקַרְנוֹ תָּרוּם בִּישׁוּעָתֶֽךָ, כִּי לִישׁוּעָתְךָ קִוִּֽינוּ "
     "כָּל הַיּוֹם. בָּרוּךְ אַתָּה, יְיָ, מַצְמִֽיחַ קֶֽרֶן יְשׁוּעָה."),
    ("amidah_tefillah", "תְּפִלָּה", "amidah/tefillah",
     "שְׁמַע קוֹלֵֽנוּ, יְיָ אֱלֹהֵֽינוּ; חוּס וְרַחֵם עָלֵֽינוּ, וְקַבֵּל בְּרַחֲמִים וּבְרָצוֹן אֶת תְּפִלָּתֵֽנוּ, "
     "כִּי אֵל שׁוֹמֵֽעַ תְּפִלּוֹת וְתַחֲנוּנִים אָֽתָּה; וּמִלְּפָנֶֽיךָ מַלְכֵּֽנוּ רֵיקָם אַל תְּשִׁיבֵֽנוּ, כִּי "
     "אַתָּה שׁוֹמֵֽעַ תְּפִלַּת עַמְּךָ יִשְׂרָאֵל בְּרַחֲמִים. בָּרוּךְ אַתָּה, יְיָ, שׁוֹמֵֽעַ תְּפִלָּה."),
]:
    prayer(nm, ti, sl, 89, 89, wrap(U + sl, d(None, txt, indent=10)))

# ---------------------------------------------------------------- 89-91: Avodah
# Whether Ya'aleh v'Yavo is said belongs to the CONTEXT, so the conditional is written
# here, around the transclusion. Which day it names belongs to the passage, and is
# written inside its own file. A shared text carrying its own outer condition would be
# bound to one occasion and useless in Birkat HaMazon.
prayer("amidah_avodah", "עֲבוֹדָה", "amidah/avodah", 89, 91, "\n".join([
    f'        <tei:div corresp="{U}amidah/avodah">',
    d(U + "amidah/avodah/retzeh", "רְצֵה, יְיָ אֱלֹהֵֽינוּ, בְּעַמְּךָ יִשְׂרָאֵל וּבִתְפִלָּתָם; וְהָשֵׁב אֶת הָעֲבוֹדָה לִדְבִיר בֵּיתֶֽךָ, "
            "וְאִשֵּׁי יִשְׂרָאֵל וּתְפִלָּתָם בְּאַהֲבָה תְקַבֵּל בְּרָצוֹן, וּתְהִי לְרָצוֹן תָּמִיד עֲבוֹדַת "
            "יִשְׂרָאֵל עַמֶּֽךָ.", indent=10),
    cond("cond_avodah_yaaleh", note="On Rosh Ḥodesh and Ḥol ha-Mo‘ed add:",
         fs="\n".join(["          <j:any>", feature(HOL, "rosh-hodesh",
                       '<tei:numeric value="1" max="2"/>'),
                       feature(AGG, "chol-hamoed"), "          </j:any>"])),
    f'        <j:transclude type="external" target="{U}yaaleh_veyavo"/>',
    endcond("cond_avodah_yaaleh"),
    d(U + "amidah/avodah/vetechezeinah",
      "וְתֶחֱזֶֽינָה עֵינֵֽינוּ בְּשׁוּבְךָ לְצִיּוֹן בְּרַחֲמִים. בָּרוּךְ אַתָּה, יְיָ, "
      "הַמַּחֲזִיר שְׁכִינָתוֹ לְצִיּוֹן.", indent=10),
    "        </tei:div>"]))

# Top-level: Ya'aleh v'Yavo is said in the Amidah and in Birkat HaMazon, so it is an
# independent unit both quote, not a part of either. The three occasion names are set as
# three columns, each labelled by a bare day-name -- which is an instruction, short for
# "say this on Rosh Hodesh".
prayer("yaaleh_veyavo", "יַעֲלֶה וְיָבֹא", "yaaleh_veyavo", 89, 91, "\n".join([
    f'        <tei:div corresp="{U}yaaleh_veyavo">',
    d(U + "yaaleh_veyavo/eloheinu_velohei", "(אֱלֹהֵֽינוּ וֵאלֹהֵי אֲבוֹתֵֽינוּ, יַעֲלֶה וְיָבֹא, וְיַגִּֽיעַ וְיֵרָאֶה, וְיֵרָצֶה וְיִשָּׁמַע, "
            "וְיִפָּקֵד וְיִזָּכֵר זִכְרוֹנֵֽנוּ וּפִקְדוֹנֵֽנוּ, וְזִכְרוֹן אֲבוֹתֵֽינוּ, וְזִכְרוֹן מָשִֽׁיחַ בֶּן דָּוִד "
            "עַבְדֶּֽךָ, וְזִכְרוֹן יְרוּשָׁלַֽיִם עִיר קָדְשֶֽׁךָ, וְזִכְרוֹן כָּל עַמְּךָ בֵּית יִשְׂרָאֵל לְפָנֶֽיךָ, "
            "לִפְלֵיטָה וּלְטוֹבָה, לְחֵן וּלְחֶֽסֶד וּלְרַחֲמִים, לְחַיִּים וּלְשָׁלוֹם, בְּיוֹם", indent=10),
    cond("cond_yvy_rosh_chodesh", note="Rosh Ḥodesh",
         fs=feature(HOL, "rosh-hodesh", '<tei:numeric value="1" max="2"/>')),
    d(U + "yaaleh_veyavo/rosh_chodesh", "רֹאשׁ הַחֹֽדֶשׁ", indent=10),
    endcond("cond_yvy_rosh_chodesh"),
    cond("cond_yvy_pesach", note="Pesaḥ",
         fs=feature(HOL, "pesah", '<tei:numeric value="1" max="8"/>')),
    d(U + "yaaleh_veyavo/pesach", "חַג הַמַּצּוֹת", indent=10),
    endcond("cond_yvy_pesach"),
    cond("cond_yvy_sukkot", note="Sukkoth",
         fs=feature(HOL, "sukkot", '<tei:numeric value="1" max="7"/>')),
    d(U + "yaaleh_veyavo/sukkot", "חַג הַסֻּכּוֹת", indent=10),
    endcond("cond_yvy_sukkot"),
    d(U + "yaaleh_veyavo/zokhrenu", "הַזֶּה. זָכְרֵֽנוּ, יְיָ אֱלֹהֵֽינוּ, בּוֹ לְטוֹבָה, וּפָקְדֵֽנוּ בוֹ לִבְרָכָה, "
            f"{pb(91)}וְהוֹשִׁיעֵֽנוּ בוֹ לְחַיִּים; וּבִדְבַר יְשׁוּעָה וְרַחֲמִים חוּס וְחָנֵּֽנוּ, וְרַחֵם עָלֵֽינוּ "
            "וְהוֹשִׁיעֵֽנוּ, כִּי אֵלֶֽיךָ עֵינֵֽינוּ, כִּי אֵל מֶֽלֶךְ חַנּוּן וְרַחוּם אָֽתָּה.)", indent=10),
    "        </tei:div>"]))

# ---------------------------------------------------------------- 91-93: Hodaah
# Modim and Modim d'Rabbanan stand side by side, split by a printed vertical rule. They
# are SIMULTANEOUS -- the congregation says one while the Reader says the other -- so
# Modim d'Rabbanan is conditioned on the repetition and Modim itself is not conditioned
# at all. Encoding them as alternatives would be wrong.
prayer("amidah_hodaah", "הוֹדָאָה", "amidah/hodaah", 91, 93, "\n".join([
    f'        <tei:div corresp="{U}amidah/hodaah">',
    cond("cond_modim_derabbanan",
         note="When the Reader repeats the Shemoneh Esreh, the Congregation responds here by saying:",
         fs="<j:all>"+feature(RECITATION, "repetition")+feature(QUORUM, "minyan")+"</j:all>"),
    d(U + "amidah/hodaah/modim_derabbanan",
      "(מוֹדִים אֲנַֽחְנוּ לָךְ, שָׁאַתָּה הוּא יְיָ אֱלֹהֵֽינוּ וֵאלֹהֵי אֲבוֹתֵֽינוּ. אֱלֹהֵי כָל בָּשָׂר, "
      "יוֹצְרֵֽנוּ, יוֹצֵר בְּרֵאשִׁית. בְּרָכוֹת וְהוֹדָאוֹת לְשִׁמְךָ הַגָּדוֹל וְהַקָּדוֹשׁ עַל שֶׁהֶחֱיִיתָֽנוּ "
      "וְקִיַּמְתָּֽנוּ. כֵּן תְּחַיֵּֽנוּ וּתְקַיְּמֵֽנוּ, וְתֶאֱסוֹף גָּלֻיּוֹתֵֽינוּ לְחַצְרוֹת קָדְשֶֽׁךָ לִשְׁמֹר "
      "חֻקֶּֽיךָ וְלַעֲשׂוֹת רְצוֹנֶֽךָ, וּלְעָבְדְּךָ בְּלֵבָב שָׁלֵם, עַל שֶׁאֲנַֽחְנוּ מוֹדִים לָךְ. "
      "בָּרוּךְ אֵל הַהוֹדָאוֹת.)", indent=10),
    endcond("cond_modim_derabbanan"),
    d(U + "amidah/hodaah/modim", "מוֹדִים אֲנַֽחְנוּ לָךְ, שָׁאַתָּה הוּא יְיָ אֱלֹהֵֽינוּ וֵאלֹהֵי אֲבוֹתֵֽינוּ לְעוֹלָם וָעֶד. "
            "צוּר חַיֵּֽינוּ, מָגֵן יִשְׁעֵֽנוּ אַתָּה הוּא. לְדוֹר וָדוֹר נֽוֹדֶה לְּךָ, וּנְסַפֵּר תְּהִלָּתֶֽךָ, "
            "עַל חַיֵּֽינוּ הַמְּסוּרִים בְּיָדֶֽךָ, וְעַל נִשְׁמוֹתֵֽינוּ הַפְּקוּדוֹת לָךְ, וְעַל נִסֶּֽיךָ שֶׁבְּכָל "
            "יוֹם עִמָּֽנוּ, וְעַל נִפְלְאוֹתֶֽיךָ וְטוֹבוֹתֶֽיךָ שֶׁבְּכָל עֵת, עֶֽרֶב וָבֹֽקֶר וְצָהֳרָֽיִם. "
            "הַטּוֹב כִּי לֹא כָלוּ רַחֲמֶֽיךָ, וְהַמְרַחֵם כִּי לֹא תַֽמּוּ חֲסָדֶֽיךָ, מֵעוֹלָם קִוִּֽינוּ לָךְ.", indent=10),
    cond("cond_hodaah_chanukah", note="On Ḥanukkah add:",
         fs=feature(HOL, "hanukkah", '<tei:numeric value="1" max="8"/>')),
    f'        <j:transclude type="external" target="{U}al_hanissim/chanukah"/>',
    endcond("cond_hodaah_chanukah"),
    cond("cond_hodaah_purim", note="On Purim add:",
         fs=feature(HOL, "purim-observed", '<tei:numeric value="1"/>')),
    f'        <j:transclude type="external" target="{U}al_hanissim/purim"/>',
    endcond("cond_hodaah_purim"),
    d(U + "amidah/hodaah/veal_kullam", "וְעַל כֻּלָּם יִתְבָּרַךְ וְיִתְרוֹמַם שִׁמְךָ, מַלְכֵּֽנוּ, תָּמִיד לְעוֹלָם וָעֶד.", indent=10),
    cond("cond_hodaah_aseret", note="Between Rosh Hashanah and Yom Kippur add:", fs=AYT),
    d(U + "amidah/hodaah/ukhtov",
      "(וּכְתוֹב לְחַיִּים טוֹבִים כָּל בְּנֵי בְרִיתֶֽךָ.)", indent=10),
    endcond("cond_hodaah_aseret"),
    d(U + "amidah/hodaah/hatov_shimkha",
      "וְכֹל הַחַיִּים יוֹדֽוּךָ סֶּֽלָה, וִיהַלְלוּ אֶת שִׁמְךָ בֶּאֱמֶת, הָאֵל, יְשׁוּעָתֵֽנוּ וְעֶזְרָתֵֽנוּ סֶֽלָה. "
      "בָּרוּךְ אַתָּה, יְיָ, הַטּוֹב שִׁמְךָ, וּלְךָ נָאֶה לְהוֹדוֹת.", indent=10),
    "        </tei:div>"]))

# Al HaNissim is in the Amidah and in Birkat HaMazon, so it is top-level. Birnbaum prints
# the two occasions as TWO COMPLETE PASSAGES, one after the other, each under its own
# rubric and its own parentheses -- not one passage with a variable middle. They are
# named by the occasion because that is what tells them apart.
prayer("al_hanissim_chanukah", "עַל הַנִּסִּים לַחֲנֻכָּה", "al_hanissim/chanukah", 91, 93,
    wrap(U + "al_hanissim/chanukah", "\n".join([
      d(U + "al_hanissim/chanukah/al_hanissim", "(עַל הַנִּסִּים וְעַל הַפֻּרְקָן, וְעַל הַגְּבוּרוֹת וְעַל הַתְּשׁוּעוֹת, וְעַל הַמִּלְחָמוֹת, "
              "שֶׁעָשִֽׂיתָ לַאֲבוֹתֵֽינוּ בַּיָּמִים הָהֵם בַּזְּמַן הַזֶּה—", indent=10),
      d(U + "al_hanissim/chanukah/bimei", "בִּימֵי מַתִּתְיָֽהוּ בֶּן יוֹחָנָן כֹּהֵן גָּדוֹל, חַשְׁמוֹנַאי וּבָנָיו, כְּשֶׁעָמְדָה מַלְכוּת יָוָן "
              "הָרְשָׁעָה עַל עַמְּךָ יִשְׂרָאֵל לְהַשְׁכִּיחָם תּוֹרָתֶֽךָ, וּלְהַעֲבִירָם מֵחֻקֵּי רְצוֹנֶֽךָ. "
              f"וְאַתָּה בְּרַחֲמֶֽיךָ הָרַבִּים עָמַֽדְתָּ לָהֶם{pb(93)} בְּעֵת צָרָתָם, רַֽבְתָּ אֶת רִיבָם, "
              "דַּֽנְתָּ אֶת דִּינָם, נָקַֽמְתָּ אֶת נִקְמָתָם; מָסַֽרְתָּ גִבּוֹרִים בְּיַד חַלָּשִׁים, וְרַבִּים "
              "בְּיַד מְעַטִּים, וּטְמֵאִים בְּיַד טְהוֹרִים. וּרְשָׁעִים בְּיַד צַדִּיקִים, וְזֵדִים בְּיַד "
              "עוֹסְקֵי תוֹרָתֶֽךָ. וּלְךָ עָשִֽׂיתָ שֵׁם גָּדוֹל וְקָדוֹשׁ בְּעוֹלָמֶֽךָ, וּלְעַמְּךָ יִשְׂרָאֵל "
              "עָשִֽׂיתָ תְּשׁוּעָה גְדוֹלָה וּפֻרְקָן כְּהַיּוֹם הַזֶּה. וְאַחַר כֵּן בָּֽאוּ בָנֶֽיךָ לִדְבִיר "
              "בֵּיתֶֽךָ, וּפִנּוּ אֶת הֵיכָלֶֽךָ, וְטִהֲרוּ אֶת מִקְדָּשֶֽׁךָ, וְהִדְלִֽיקוּ נֵרוֹת בְּחַצְרוֹת "
              "קָדְשֶֽׁךָ, וְקָבְעוּ שְׁמוֹנַת יְמֵי חֲנֻכָּה אֵֽלּוּ לְהוֹדוֹת וּלְהַלֵּל לְשִׁמְךָ הַגָּדוֹל.)", indent=10)])))

prayer("al_hanissim_purim", "עַל הַנִּסִּים לְפוּרִים", "al_hanissim/purim", 93, 93,
    wrap(U + "al_hanissim/purim", "\n".join([
      d(U + "al_hanissim/purim/al_hanissim", "(עַל הַנִּסִּים וְעַל הַפֻּרְקָן, וְעַל הַגְּבוּרוֹת וְעַל הַתְּשׁוּעוֹת, וְעַל הַמִּלְחָמוֹת, "
              "שֶׁעָשִֽׂיתָ לַאֲבוֹתֵֽינוּ בַּיָּמִים הָהֵם בַּזְּמַן הַזֶּה—", indent=10),
      d(U + "al_hanissim/purim/bimei", "בִּימֵי מָרְדְּכַי וְאֶסְתֵּר בְּשׁוּשַׁן הַבִּירָה, כְּשֶׁעָמַד עֲלֵיהֶם הָמָן הָרָשָׁע. בִּקֵּשׁ "
              "לְהַשְׁמִיד לַהֲרוֹג וּלְאַבֵּד אֶת כָּל הַיְּהוּדִים, מִנַּֽעַר וְעַד זָקֵן, טַף וְנָשִׁים, "
              "בְּיוֹם אֶחָד, בִּשְׁלוֹשָׁה עָשָׂר לְחֹֽדֶשׁ שְׁנֵים עָשָׂר, הוּא חֹֽדֶשׁ אֲדָר, וּשְׁלָלָם לָבוֹז. "
              "וְאַתָּה בְּרַחֲמֶֽיךָ הָרַבִּים הֵפַֽרְתָּ אֶת עֲצָתוֹ, וְקִלְקַֽלְתָּ אֶת מַחֲשַׁבְתּוֹ, "
              "וַהֲשֵׁבֽוֹתָ גְּמוּלוֹ בְּרֹאשׁוֹ, וְתָלוּ אוֹתוֹ וְאֶת בָּנָיו עַל הָעֵץ.)", indent=10)])))

# ---------------------------------------------------------------- 93-95
# "Priestly blessing recited by Reader:" is a RUBRIC, in English, on the Hebrew page --
# not a heading. Birnbaum prints the three verses and nothing else: no call to the
# kohanim, no interlinear responses, no Ribono shel Olam, no Adir baMarom.
prayer("amidah_birkat_kohanim", "בִּרְכַּת כֹּהֲנִים", "amidah/birkat_kohanim", 93, 95, "\n".join([
    f'        <tei:div corresp="{U}amidah/birkat_kohanim">',
    '          <tei:note type="instruction" xml:lang="en" corresp="urn:x-opensiddur:instruction:amidah/birkat_kohanim_leshatz">Priestly blessing recited by Reader:</tei:note>',
    f'          <tei:p>אֱלֹהֵֽינוּ וֵאלֹהֵי אֲבוֹתֵֽינוּ, בָּרְכֵֽנוּ בַּבְּרָכָה הַמְשֻׁלֶּֽשֶׁת בַּתּוֹרָה'
    f'{pb(95)} הַכְּתוּבָה עַל יְדֵי מֹשֶׁה עַבְדֶּֽךָ, הָאֲמוּרָה מִפִּי אַהֲרֹן וּבָנָיו, כֹּהֲנִים עַם '
    'קְדוֹשֶֽׁךָ, כָּאָמוּר: יְבָרֶכְךָ יְיָ וְיִשְׁמְרֶֽךָ. יָאֵר יְיָ פָּנָיו אֵלֶֽיךָ וִיחֻנֶּֽךָ. '
    'יִשָּׂא יְיָ פָּנָיו אֵלֶֽיךָ, וְיָשֵׂם לְךָ שָׁלוֹם.</tei:p>',
    "        </tei:div>"]))

# Birnbaum prints ONLY שִׂים שָׁלוֹם -- there is no שָׁלוֹם רָב in this unit. The Ten Days
# substitution carries both an added sentence and a different seal, and his rubric here
# says "say", not "substitute": the wording is per position and is set as he printed it.
prayer("amidah_shalom", "בִּרְכַּת שָׁלוֹם", "amidah/shalom", 95, 95, "\n".join([
    f'        <tei:div corresp="{U}amidah/shalom">',
    d(U + "amidah/shalom/sim_shalom",
      "שִׂים שָׁלוֹם, טוֹבָה וּבְרָכָה, חֵן וָחֶֽסֶד וְרַחֲמִים, עָלֵֽינוּ וְעַל כָּל יִשְׂרָאֵל עַמֶּֽךָ. "
      "בָּרְכֵֽנוּ אָבִֽינוּ, כֻּלָּֽנוּ כְּאֶחָד, בְּאוֹר פָּנֶֽיךָ; כִּי בְאוֹר פָּנֶֽיךָ נָתַֽתָּ לָּֽנוּ, "
      "יְיָ אֱלֹהֵֽינוּ, תּוֹרַת חַיִּים וְאַהֲבַת חֶֽסֶד, וּצְדָקָה וּבְרָכָה וְרַחֲמִים, וְחַיִּים וְשָׁלוֹם. "
      "וְטוֹב בְּעֵינֶֽיךָ לְבָרֵךְ אֶת עַמְּךָ יִשְׂרָאֵל בְּכָל עֵת וּבְכָל שָׁעָה בִּשְׁלוֹמֶֽךָ.", indent=10),
    cond("cond_shalom_seal_ordinary", fs=AYT, negate=True, marked=True),
    d(U + "amidah/shalom/hamevarekh",
      "בָּרוּךְ אַתָּה, יְיָ, הַמְבָרֵךְ אֶת עַמּוֹ יִשְׂרָאֵל בַּשָּׁלוֹם.", indent=10),
    endcond("cond_shalom_seal_ordinary"),
    cond("cond_shalom_seal_aseret",
         note="Between Rosh Hashanah and Yom Kippur say:", fs=AYT),
    d(U + "amidah/shalom/besefer_chayyim",
      "(בְּסֵֽפֶר חַיִּים, בְּרָכָה וְשָׁלוֹם וּפַרְנָסָה טוֹבָה, נִזָּכֵר וְנִכָּתֵב לְפָנֶֽיךָ, אֲנַֽחְנוּ "
      "וְכָל עַמְּךָ בֵּית יִשְׂרָאֵל, לְחַיִּים טוֹבִים וּלְשָׁלוֹם. "
      "בָּרוּךְ אַתָּה, יְיָ, עוֹשֵׂה הַשָּׁלוֹם.)", indent=10),
    endcond("cond_shalom_seal_aseret"),
    "        </tei:div>"]))

prayer("amidah_elohai_netzor", "אֱלֹהַי נְצֹר", "amidah/elohai_netzor", 95, 95, "\n".join([
    f'        <tei:div corresp="{U}amidah/elohai_netzor">',
    '          <tei:note type="instruction" xml:lang="en">After the Shemoneh Esreh add the following meditation:</tei:note>',
    "          <tei:p>אֱלֹהַי, נְצֹר לְשׁוֹנִי מֵרָע, וּשְׂפָתַי מִדַּבֵּר מִרְמָה, וְלִמְקַלְלַי נַפְשִׁי תִדּוֹם, "
    "וְנַפְשִׁי כֶּעָפָר לַכֹּל תִּהְיֶה. פְּתַח לִבִּי בְּתוֹרָתֶֽךָ, וּבְמִצְוֺתֶֽיךָ תִּרְדּוֹף נַפְשִׁי; "
    "וְכָל הַחוֹשְׁבִים עָלַי רָעָה, מְהֵרָה הָפֵר עֲצָתָם וְקַלְקֵל מַחֲשַׁבְתָּם. עֲשֵׂה לְמַֽעַן שְׁמֶֽךָ, "
    "עֲשֵׂה לְמַֽעַן יְמִינֶֽךָ, עֲשֵׂה לְמַֽעַן קְדֻשָּׁתֶֽךָ, עֲשֵׂה לְמַֽעַן תּוֹרָתֶֽךָ. לְמַֽעַן יֵחָלְצוּן "
    "יְדִידֶֽיךָ, הוֹשִֽׁיעָה יְמִינְךָ וַעֲנֵֽנִי. יִהְיוּ לְרָצוֹן אִמְרֵי פִי וְהֶגְיוֹן לִבִּי לְפָנֶֽיךָ, "
    "יְיָ, צוּרִי וְגוֹאֲלִי. עֹשֶׂה שָׁלוֹם בִּמְרוֹמָיו, הוּא יַעֲשֶׂה שָׁלוֹם עָלֵֽינוּ וְעַל כָּל יִשְׂרָאֵל, "
    "וְאִמְרוּ אָמֵן.</tei:p>",
    "        </tei:div>"]))

prayer("amidah_yehi_ratzon", "יְהִי רָצוֹן שֶׁיִּבָּנֶה בֵּית הַמִּקְדָּשׁ", "amidah/yehi_ratzon", 95, 97,
    wrap(U + "amidah/yehi_ratzon", d(None,
        "יְהִי רָצוֹן מִלְּפָנֶֽיךָ, יְיָ אֱלֹהֵֽינוּ וֵאלֹהֵי אֲבוֹתֵֽינוּ, שֶׁיִּבָּנֶה בֵּית הַמִּקְדָּשׁ "
        f"בִּמְהֵרָה בְיָמֵֽינוּ, וְתֵן חֶלְקֵֽנוּ בְּתוֹרָתֶֽךָ. וְשָׁם נַעֲבָדְךָ{pb(97)} בְּיִרְאָה, "
        "כִּימֵי עוֹלָם וּכְשָׁנִים קַדְמוֹנִיּוֹת. וְעָרְבָה לַיְיָ מִנְחַת יְהוּדָה וִירוּשָׁלָֽיִם, "
        "כִּימֵי עוֹלָם וּכְשָׁנִים קַדְמוֹנִיּוֹת.", indent=10)))

prayer("amidah_havinenu", "הֲבִינֵֽנוּ", "amidah/havinenu", 97, 97,
    wrap(U + "amidah/havinenu", d(None,
        "הֲבִינֵֽנוּ, יְיָ אֱלֹהֵֽינוּ, לָדַֽעַת דְּרָכֶֽיךָ; וּמוֹל אֶת לְבָבֵֽנוּ לְיִרְאָתֶֽךָ; וְתִסְלַח לָֽנוּ "
        "לִהְיוֹת גְּאוּלִים; וְרַחֲקֵֽנוּ מִמַּכְאוֹב; וְדַשְּׁנֵֽנוּ בִּנְאוֹת אַרְצֶֽךָ; וּנְפוּצוֹתֵֽינוּ "
        "מֵאַרְבַּע כַּנְפוֹת הָאָֽרֶץ תְּקַבֵּץ. וְהַתּוֹעִים עַל דַּעְתְּךָ יִשָּׁפֵֽטוּ; וְעַל הָרְשָׁעִים "
        "תָּנִיף יָדֶֽךָ; וְיִשְׂמְחוּ צַדִּיקִים בְּבִנְיַן עִירֶֽךָ, וּבְתִקּוּן הֵיכָלֶֽךָ, וּבִצְמִיחַת "
        "קֶֽרֶן לְדָוִד עַבְדֶּֽךָ, וּבַעֲרִיכַת נֵר לְבֶן יִשַׁי מְשִׁיחֶֽךָ; טֶֽרֶם נִקְרָא אַתָּה תַעֲנֶה. "
        "בָּרוּךְ אַתָּה, יְיָ, שׁוֹמֵֽעַ תְּפִלָּה.", indent=10)))
