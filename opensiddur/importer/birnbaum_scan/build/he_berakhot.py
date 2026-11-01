# -*- coding: utf-8 -*-
"""The Hebrew of the Torah blessings and Birkhoth ha-Shaḥar, printed pages 13 to 19.

The blessings over the Torah; the Priestly Blessing; Elu Devarim; Elohai Neshamah; the
run of morning blessings; and the two Yehi Ratzon passages that close them.

**The Priestly Blessing takes a top-level name.** The Amidah already emits
``prayer:amidah/birkat_kohanim``, but that is a different text: the Reader's introduction
with the verses inside it, not separately addressable. Here the bare verses stand alone
under their own citation, and they are said in many places, so by *nest only what lives in
one place* they are ``prayer:birkat_kohanim``. Worth refactoring the Amidah's later so its
verses transclude this one; not worth doing before the pages that print them are read.

**Two blessings are said by one person or the other, and the page says which.** Printed 17
breaks into two columns headed `Men say:` and `Women say:`, the men's on the right, which
on a Hebrew page is read first. So the men's conditional comes first here, and the English
page mirrors the placement to keep the same reading order -- see `readings/17.md` and `18`.

`opensiddur:person/gender` has no default. A compile that does not say who is praying
keeps both columns with the rubrics naming who each is for, which is what the page does.
"""
import functools

from .common import PRAYER, PERSON, feature, cond, endcond
from . import common

pb = functools.partial(common.pb, sigil=common.SIGIL_BIRCHOT)

U = PRAYER

PRAYERS = []


def prayer(name, title, slug, first, last, body):
    PRAYERS.append(dict(name=name, title=title, urn=U + slug,
                        first=first, last=last, body=body))


def d(urn, *paras, indent=8):
    pad = " " * indent
    inner = "\n".join(f"{pad}  <tei:p>{p}</tei:p>" for p in paras)
    return f'{pad}<tei:div corresp="{urn}">\n{inner}\n{pad}</tei:div>'


B = "בָּרוּךְ אַתָּה, יְיָ אֱלֹהֵֽינוּ, מֶֽלֶךְ הָעוֹלָם, "

#: Printed 13 sets the washing blessing and Asher Yatzar before the Torah blessings. The
#: washing blessing is NOT emitted here: the children's page already realises
#: `prayer:al_netilat_yadayim`, and refdb refuses a text URN mapped twice in one project.
#: The unit transcludes it, as it does Barukh Shem -- the second time this rule bites.
prayer("asher_yatzar", "אֲשֶׁר יָצַר", "asher_yatzar", 13, 13,
       d(U + "asher_yatzar",
         B + "אֲשֶׁר יָצַר אֶת הָאָדָם בְּחָכְמָה, וּבָרָא בוֹ נְקָבִים נְקָבִים, "
         "חֲלוּלִים חֲלוּלִים. גָּלוּי וְיָדֽוּעַ לִפְנֵי כִסֵּא כְבוֹדֶֽךָ, שֶׁאִם "
         "יִפָּתֵֽחַ אֶחָד מֵהֶם אוֹ יִסָּתֵם אֶחָד מֵהֶם אִי אֶפְשָׁר לְהִתְקַיֵּם "
         "וְלַעֲמוֹד לְפָנֶֽיךָ. בָּרוּךְ אַתָּה, יְיָ, רוֹפֵא כָל בָּשָׂר וּמַפְלִיא "
         "לַעֲשׂוֹת."))

prayer("birkhot_hatorah_laasoq", "לַעֲסוֹק בְּדִבְרֵי תוֹרָה",
       "birkhot_hatorah/laasoq", 13, 13,
       d(U + "birkhot_hatorah/laasoq",
         B + "אֲשֶׁר קִדְּשָֽׁנוּ בְּמִצְוֺתָיו וְצִוָּֽנוּ לַעֲסוֹק בְּדִבְרֵי תוֹרָה."))

prayer("birkhot_hatorah_vehaarev", "וְהַעֲרֶב־נָא", "birkhot_hatorah/vehaarev", 13, 13,
       d(U + "birkhot_hatorah/vehaarev",
         "וְהַעֲרֶב־נָא, יְיָ אֱלֹהֵֽינוּ, אֶת דִּבְרֵי תוֹרָתְךָ בְּפִֽינוּ, וּבְפִי "
         "עַמְּךָ בֵּית יִשְׂרָאֵל, וְנִהְיֶה אֲנַֽחְנוּ וְצֶאֱצָאֵֽינוּ, וְצֶאֱצָאֵי "
         "עַמְּךָ בֵּית יִשְׂרָאֵל, כֻּלָּֽנוּ יוֹדְעֵי שְׁמֶֽךָ וְלוֹמְדֵי תוֹרָתֶֽךָ "
         "לִשְׁמָהּ. בָּרוּךְ אַתָּה, יְיָ, הַמְלַמֵּד תּוֹרָה לְעַמּוֹ יִשְׂרָאֵל."))

prayer("birkhot_hatorah_asher_bachar", "אֲשֶׁר בָּֽחַר בָּֽנוּ",
       "birkhot_hatorah/asher_bachar", 13, 13,
       d(U + "birkhot_hatorah/asher_bachar",
         B + "אֲשֶׁר בָּֽחַר בָּֽנוּ מִכָּל הָעַמִּים, וְנָֽתַן לָֽנוּ אֶת תּוֹרָתוֹ. "
         "בָּרוּךְ אַתָּה, יְיָ, נוֹתֵן הַתּוֹרָה."))

prayer("birkat_kohanim", "בִּרְכַּת כֹּהֲנִים", "birkat_kohanim", 15, 15,
       d(U + "birkat_kohanim",
         f"{pb(15)}יְבָרֶכְךָ יְיָ וְיִשְׁמְרֶֽךָ. יָאֵר יְיָ פָּנָיו אֵלֶֽיךָ "
         "וִיחֻנֶּֽךָּ. יִשָּׂא יְיָ פָּנָיו אֵלֶֽיךָ, וְיָשֵׂם לְךָ שָׁלוֹם."))

prayer("ellu_devarim", "אֵֽלּוּ דְבָרִים", "ellu_devarim", 15, 15,
       d(U + "ellu_devarim",
         "אֵֽלּוּ דְבָרִים שֶׁאֵין לָהֶם שִׁעוּר: הַפֵּאָה, וְהַבִּכּוּרִים, "
         "וְהָרְאָיוֹן, וּגְמִילוּת חֲסָדִים, וְתַלְמוּד תּוֹרָה. אֵֽלּוּ דְבָרִים "
         "שֶׁאָדָם אוֹכֵל פֵּרוֹתֵיהֶם בָּעוֹלָם הַזֶּה וְהַקֶּֽרֶן קַיֶּֽמֶת לוֹ "
         "לָעוֹלָם הַבָּא, וְאֵֽלּוּ הֵן: כִּבּוּד אָב וָאֵם, וּגְמִילוּת חֲסָדִים, "
         "וְהַשְׁכָּמַת בֵּית הַמִּדְרָשׁ שַׁחֲרִית וְעַרְבִית, וְהַכְנָסַת אוֹרְחִים, "
         "וּבִקּוּר חוֹלִים, וְהַכְנָסַת כַּלָּה, וְהַלְוָיַת הַמֵּת, וְעִיּוּן "
         "תְּפִלָּה, וַהֲבָאַת שָׁלוֹם בֵּין אָדָם לַחֲבֵרוֹ; וְתַלְמוּד תּוֹרָה "
         "כְּנֶֽגֶד כֻּלָּם."))

prayer("elohai_neshamah", "אֱלֹהַי, נְשָׁמָה", "elohai_neshamah", 15, 15,
       d(U + "elohai_neshamah",
         "אֱלֹהַי, נְשָׁמָה שֶׁנָּתַֽתָּ בִּי טְהוֹרָה הִיא. אַתָּה בְרָאתָהּ, אַתָּה "
         "יְצַרְתָּהּ, אַתָּה נְפַחְתָּהּ בִּי, וְאַתָּה מְשַׁמְּרָהּ בְּקִרְבִּי, "
         "וְאַתָּה עָתִיד לִטְּלָהּ מִמֶּֽנִּי וּלְהַחֲזִירָהּ בִּי לֶעָתִיד לָבֹא. כָּל "
         "זְמַן שֶׁהַנְּשָׁמָה בְקִרְבִּי מוֹדֶה אֲנִי לְפָנֶֽיךָ, יְיָ אֱלֹהַי וֵאלֹהֵי "
         "אֲבוֹתַי, רִבּוֹן כָּל הַמַּעֲשִׂים, אֲדוֹן כָּל הַנְּשָׁמוֹת. בָּרוּךְ אַתָּה, "
         "יְיָ, הַמַּחֲזִיר נְשָׁמוֹת לִפְגָרִים מֵתִים."))

#: The run of morning blessings, printed 15 to 17. Each is one line on the page, and the
#: two that depend on who is praying are held apart here and conditioned in the unit file,
#: because the rubric that governs each belongs to the unit's running order rather than to
#: the blessing itself.
BLESSINGS = [
    ("lasekhvi", "אֲשֶׁר נָתַן לַשֶּֽׂכְוִי בִינָה לְהַבְחִין בֵּין יוֹם וּבֵין לָֽיְלָה.", 15),
    ("shelo_asani_goy", "שֶׁלֹּא עָשַֽׂנִי גּוֹי.", 15),
    ("shelo_asani_aved", "שֶׁלֹּא עָשַֽׂנִי עָֽבֶד.", 17),
    ("shelo_asani_ishah", "שֶׁלֹּא עָשַֽׂנִי אִשָּׁה.", 17),
    ("sheasani_kirtzono", "שֶׁעָשַֽׂנִי כִּרְצוֹנוֹ.", 17),
    ("poqeach_ivrim", "פּוֹקֵֽחַ עִוְרִים.", 17),
    ("malbish_arummim", "מַלְבִּישׁ עֲרֻמִּים.", 17),
    ("mattir_asurim", "מַתִּיר אֲסוּרִים.", 17),
    ("zoqef_kefufim", "זוֹקֵף כְּפוּפִים.", 17),
    ("roqa_haaretz", "רוֹקַע הָאָֽרֶץ עַל הַמָּֽיִם.", 17),
    ("sheasah_li", "שֶׁעָֽשָׂה לִי כָּל צָרְכִּי.", 17),
    ("hamekhin", "הַמֵּכִין מִצְעֲדֵי גָֽבֶר.", 17),
    ("ozer_yisrael", "אוֹזֵר יִשְׂרָאֵל בִּגְבוּרָה.", 17),
    ("oter_yisrael", "עוֹטֵר יִשְׂרָאֵל בְּתִפְאָרָה.", 17),
    ("hanoten_layaef", "הַנּוֹתֵן לַיָּעֵף כֹּֽחַ.", 17),
    ("hamaavir_shenah",
     "הַמַּעֲבִיר שֵׁנָה מֵעֵינָי וּתְנוּמָה מֵעַפְעַפָּי.", 17),
]

for _slug, _words, _page in BLESSINGS:
    _brk = pb(17) if _slug == "shelo_asani_aved" else ""
    prayer(f"birkhot_{_slug}", _words.rstrip("."), f"birkhot_hashachar/{_slug}",
           _page, _page,
           d(U + f"birkhot_hashachar/{_slug}", _brk + B + _words))

prayer("birkhot_shetargilenu", "שֶׁתַּרְגִּילֵֽנוּ", "birkhot_hashachar/shetargilenu",
       17, 19,
       d(U + "birkhot_hashachar/shetargilenu",
         "וִיהִי רָצוֹן מִלְּפָנֶֽיךָ, יְיָ אֱלֹהֵֽינוּ וֵאלֹהֵי אֲבוֹתֵֽינוּ, "
         "שֶׁתַּרְגִּילֵֽנוּ בְּתוֹרָתֶֽךָ וְדַבְּקֵֽנוּ בְּמִצְוֺתֶֽיךָ; וְאַל "
         "תְּבִיאֵֽנוּ לֹא לִידֵי חֵטְא, וְלֹא לִידֵי עֲבֵרָה וְעָוֺן, וְלֹא לִידֵי "
         "נִסָּיוֹן, וְלֹא לִידֵי בִזָּיוֹן; וְאַל תַּשְׁלֶט־בָּֽנוּ יֵֽצֶר הָרָע; "
         "וְהַרְחִיקֵֽנוּ מֵאָדָם רָע וּמֵחָבֵר רָע; וְדַבְּקֵֽנוּ בְּיֵֽצֶר "
         f"{pb(19)}הַטּוֹב וּבְמַעֲשִׂים טוֹבִים; וְכֹף אֶת יִצְרֵֽנוּ "
         "לְהִשְׁתַּעְבֶּד־לָךְ."))

prayer("birkhot_gomel_chasadim", "גּוֹמֵל חֲסָדִים טוֹבִים",
       "birkhot_hashachar/gomel_chasadim", 19, 19,
       d(U + "birkhot_hashachar/gomel_chasadim",
         "וּתְנֵֽנוּ הַיּוֹם וּבְכָל יוֹם לְחֵן וּלְחֶֽסֶד וּלְרַחֲמִים בְּעֵינֶֽיךָ "
         "וּבְעֵינֵי כָל רוֹאֵֽינוּ, וְתִגְמְלֵֽנוּ חֲסָדִים טוֹבִים. בָּרוּךְ אַתָּה, "
         "יְיָ, גּוֹמֵל חֲסָדִים טוֹבִים לְעַמּוֹ יִשְׂרָאֵל."))

prayer("birkhot_shetatzileni", "שֶׁתַּצִּילֵֽנִי הַיּוֹם",
       "birkhot_hashachar/shetatzileni", 19, 19,
       d(U + "birkhot_hashachar/shetatzileni",
         "יְהִי רָצוֹן מִלְּפָנֶֽיךָ, יְיָ אֱלֹהַי וֵאלֹהֵי אֲבוֹתַי, שֶׁתַּצִּילֵֽנִי "
         "הַיּוֹם וּבְכָל יוֹם מֵעַזֵּי פָנִים וּמֵעַזּוּת פָּנִים, מֵאָדָם רָע "
         "וּמֵחָבֵר רָע, וּמִשָּׁכֵן רָע וּמִפֶּֽגַע רָע וּמִשָּׂטָן הַמַּשְׁחִית, "
         "מִדִּין קָשֶׁה וּמִבַּֽעַל דִּין קָשֶׁה, בֵּין שֶׁהוּא בֶן־בְּרִית וּבֵין "
         "שֶׁאֵינוֹ בֶן־בְּרִית."))


prayer("birkhot_zokhrenu", "זָכְרֵֽנוּ בְּזִכָּרוֹן טוֹב", "birkhot_hashachar/zokhrenu",
       19, 19,
       d(U + "birkhot_hashachar/zokhrenu",
         "אֱלֹהֵֽינוּ וֵאלֹהֵי אֲבוֹתֵֽינוּ, זָכְרֵֽנוּ בְּזִכָּרוֹן טוֹב לְפָנֶֽיךָ, "
         "וּפָקְדֵֽנוּ בִּפְקֻדַּת יְשׁוּעָה וְרַחֲמִים מִשְּׁמֵי שְׁמֵי קֶֽדֶם; "
         "וּזְכָר־לָֽנוּ, יְיָ אֱלֹהֵֽינוּ, אַהֲבַת הַקַּדְמוֹנִים, אַבְרָהָם יִצְחָק "
         "וְיִשְׂרָאֵל עֲבָדֶֽיךָ, אֶת הַבְּרִית וְאֶת הַחֶֽסֶד, וְאֶת הַשְּׁבוּעָה "
         "שֶׁנִּשְׁבַּֽעְתָּ לְאַבְרָהָם אָבִֽינוּ בְּהַר הַמּוֹרִיָּה, וְאֶת "
         "הָעֲקֵדָה שֶׁעָקַד אֶת יִצְחָק בְּנוֹ עַל גַּבֵּי הַמִּזְבֵּֽחַ, כַּכָּתוּב "
         "בְּתוֹרָתֶֽךָ:"))
