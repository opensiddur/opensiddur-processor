# -*- coding: utf-8 -*-
"""The Hebrew of Rabbi Ishmael's thirteen rules and Kaddish d'Rabbanan, printed 41 to 47.

**The rules are a numbered list and the numerals are text.** They are set `א)` with a
closing parenthesis, one rule to a line, the numeral standing at the right margin. Eizehu
Mekoman four pages earlier numbers its mishnayoth `א.` with a full stop, inline with the
words -- two sequences, two marks, and each set as printed. The facing English page numbers
both `1.`, so the numeral is not a thing the two sides share.

**The lead-in is not part of the list.** `רַבִּי יִשְׁמָעֵאל אוֹמֵר` introduces the rules
and ends in a colon; it is its own paragraph and the thirteen are a `tei:list` after it.

**The English page carries a heading this one does not.** Printed 42 heads the section
`TALMUDIC EXPOSITION OF THE SCRIPTURES` in small capitals; printed 41 goes straight from
the tail of Zevaḥim to the citation. That asymmetry is in the unit body, not here.

**The text is lifted from `scan_reading/hebrew/*.txt`, not retyped** -- see
`specs/birnbaum_scan/generate_he_ishmael.py`.
"""
import functools

from .common import PRAYER, endcond, ten_days_addition
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


prayer("ishmael_lead", "רַבִּי יִשְׁמָעֵאל אוֹמֵר", "middot/lead", 41, 41,
       d(U + "middot/lead",
         "רַבִּי יִשְׁמָעֵאל אוֹמֵר: בִּשְׁלֹשׁ עֶשְׂרֵה מִדּוֹת הַתּוֹרָה "
         "נִדְרָֽשֶׁת:"))

#: One text per rule, so a note or a translation can reach a single one of them. The
#: numeral is inside the text because the print sets it inline with the words.
prayer("middot_1", "מִדָּה א", "middot/1", 41, 41,
       d(U + "middot/1",
         "א) מִקַּל וָחֹֽמֶר;"))

prayer("middot_2", "מִדָּה ב", "middot/2", 41, 41,
       d(U + "middot/2",
         "ב) וּמִגְּזֵרָה שָׁוָה;"))

prayer("middot_3", "מִדָּה ג", "middot/3", 41, 41,
       d(U + "middot/3",
         "ג) מִבִּנְיַן אָב מִכָּתוּב אֶחָד, וּמִבִּנְיַן אָב מִשְּׁנֵי כְתוּבִים;"))

prayer("middot_4", "מִדָּה ד", "middot/4", 41, 41,
       d(U + "middot/4",
         "ד) מִכְּלָל וּפְרָט;"))

prayer("middot_5", "מִדָּה ה", "middot/5", 41, 41,
       d(U + "middot/5",
         "ה) וּמִפְּרָט וּכְלָל;"))

prayer("middot_6", "מִדָּה ו", "middot/6", 41, 41,
       d(U + "middot/6",
         "ו) כְּלָל וּפְרָט וּכְלָל אִי אַתָּה דָן אֶלָּא כְּעֵין הַפְּרָט;"))

prayer("middot_7", "מִדָּה ז", "middot/7", 43, 43,
       d(U + "middot/7",
         "ז) מִכְּלָל שֶׁהוּא צָרִיךְ לִפְרָט, וּמִפְּרָט שֶׁהוּא צָרִיךְ לִכְלָל;"))

prayer("middot_8", "מִדָּה ח", "middot/8", 43, 43,
       d(U + "middot/8",
         "ח) כָּל דָּבָר שֶׁהָיָה בִּכְלָל וְיָצָא מִן הַכְּלָל לְלַמֵּד, לֹא "
         "לְלַמֵּד עַל עַצְמוֹ יָצָא, אֶלָּא לְלַמֵּד עַל הַכְּלָל כֻּלּוֹ יָצָא;"))

prayer("middot_9", "מִדָּה ט", "middot/9", 43, 43,
       d(U + "middot/9",
         "ט) כָּל דָּבָר שֶׁהָיָה בִּכְלָל וְיָצָא לִטְעוֹן טֹֽעַן אַחֵר שֶׁהוּא "
         "כְעִנְיָנוֹ, יָצָא לְהָקֵל וְלֹא לְהַחֲמִיר;"))

prayer("middot_10", "מִדָּה י", "middot/10", 43, 43,
       d(U + "middot/10",
         "י) כָּל דָּבָר שֶׁהָיָה בִּכְלָל וְיָצָא לִטְעוֹן טֹֽעַן אַחֵר שֶׁלֹּא "
         "כְעִנְיָנוֹ, יָצָא לְהָקֵל וּלְהַחֲמִיר;"))

prayer("middot_11", "מִדָּה יא", "middot/11", 43, 43,
       d(U + "middot/11",
         "יא) כָּל דָּבָר שֶׁהָיָה בִּכְלָל וְיָצָא לִדּוֹן בַּדָּבָר הֶחָדָשׁ, "
         "אִי אַתָּה יָכוֹל לְהַחֲזִירוֹ לִכְלָלוֹ עַד שֶׁיַּחֲזִירֶֽנּוּ "
         "הַכָּתוּב לִכְלָלוֹ בְּפֵרוּשׁ;"))

prayer("middot_12", "מִדָּה יב", "middot/12", 43, 43,
       d(U + "middot/12",
         "יב) דָּבָר הַלָּמֵד מֵעִנְיָנוֹ, וְדָבָר הַלָּמֵד מִסּוֹפוֹ;"))

prayer("middot_13", "מִדָּה יג", "middot/13", 45, 45,
       d(U + "middot/13",
         "יג) וְכֵן שְׁנֵי כְתוּבִים הַמַּכְחִישִׁים זֶה אֶת זֶה, עַד שֶׁיָּבֹא "
         "הַכָּתוּב הַשְּׁלִישִׁי וְיַכְרִֽיעַ בֵּינֵיהֶם."))

prayer("ishmael_yehi_ratzon", "יְהִי רָצוֹן שֶׁיִּבָּנֶה בֵּית הַמִּקְדָּשׁ",
       "middot/yehi_ratzon", 45, 45,
       d(U + "middot/yehi_ratzon",
         "יְהִי רָצוֹן מִלְּפָנֶֽיךָ, יְיָ אֱלֹהֵֽינוּ וֵאלֹהֵי אֲבוֹתֵֽינוּ, "
         "שֶׁיִּבָּנֶה בֵּית הַמִּקְדָּשׁ בִּמְהֵרָה בְיָמֵֽינוּ, וְתֵן חֶלְקֵֽנוּ "
         "בְּתוֹרָתֶֽךָ. וְשָׁם נַעֲבָדְךָ בְּיִרְאָה, כִּימֵי עוֹלָם וּכְשָׁנִים "
         "קַדְמוֹנִיּוֹת."))

#: Kaddish d'Rabbanan. `יִתְבָּרַךְ` runs across the page turn at
#: `וּלְעָלְמֵי עָלְמַיָּא. | יִתְבָּרַךְ`, which is a paragraph boundary, so the
#: break opens the next passage rather than sitting inside this one.
prayer("kaddish_derabbanan_yitgaddal", "יִתְגַּדַּל וְיִתְקַדַּשׁ", "kaddish/derabbanan/yitgaddal", 45, 45,
       d(U + "kaddish/derabbanan/yitgaddal",
         f'<tei:milestone unit="prayer-part" corresp="{U}kaddish/yitgaddal"/>'
         "יִתְגַּדַּל וְיִתְקַדַּשׁ שְׁמֵהּ רַבָּא בְּעָלְמָא דִּי בְרָא "
         "כִרְעוּתֵהּ; וְיַמְלִיךְ מַלְכוּתֵהּ בְּחַיֵּיכוֹן וּבְיוֹמֵיכוֹן, "
         "וּבְחַיֵּי דְכָל בֵּית יִשְׂרָאֵל, בַּעֲגָלָא וּבִזְמַן קָרִיב, "
         "וְאִמְרוּ אָמֵן."
         '<tei:milestone unit="prayer-part"/>'))

prayer("kaddish_derabbanan_yehe_shemeh", "יְהֵא שְׁמֵהּ רַבָּא מְבָרַךְ", "kaddish/derabbanan/yehe_shemeh", 45, 45,
       d(U + "kaddish/derabbanan/yehe_shemeh",
         f'<tei:milestone unit="prayer-part" corresp="{U}kaddish/yehe_shemeh"/>'
         "יְהֵא שְׁמֵהּ רַבָּא מְבָרַךְ לְעָלַם וּלְעָלְמֵי עָלְמַיָּא."
         '<tei:milestone unit="prayer-part"/>'))

prayer("kaddish_derabbanan_yitbarakh", "יִתְבָּרַךְ וְיִשְׁתַּבַּח", "kaddish/derabbanan/yitbarakh", 47, 47,
       d(U + "kaddish/derabbanan/yitbarakh",
         f'{pb(47)}'
         f'<tei:milestone unit="prayer-part" corresp="{U}kaddish/yitbarakh"/>'
         "יִתְבָּרַךְ וְיִשְׁתַּבַּח, וְיִתְפָּאַר וְיִתְרוֹמָם, וְיִתְנַשֵּׂא "
         "וְיִתְהַדָּר, וְיִתְעַלֶּה וְיִתְהַלָּל שְׁמֵהּ דְּקֻדְשָׁא, בְּרִיךְ "
         "הוּא, לְעֵֽלָּא "
         + ten_days_addition("cond_kaddish_aseret")
         + "לְעֵֽלָּא" + endcond("cond_kaddish_aseret")
         + " מִן כָּל בִּרְכָתָא וְשִׁירָתָא, "
         "תֻּשְׁבְּחָתָא וְנֶחֱמָתָא, דַּאֲמִירָן בְּעָלְמָא, וְאִמְרוּ אָמֵן."
         '<tei:milestone unit="prayer-part"/>'))

prayer("kaddish_derabbanan_al_yisrael", "עַל יִשְׂרָאֵל וְעַל רַבָּנָן", "kaddish/derabbanan/al_yisrael", 47, 47,
       d(U + "kaddish/derabbanan/al_yisrael",
         "עַל יִשְׂרָאֵל וְעַל רַבָּנָן וְעַל תַּלְמִידֵיהוֹן, וְעַל כָּל "
         "תַּלְמִידֵי תַלְמִידֵיהוֹן, וְעַל כָּל מָן דְּעָסְקִין בְּאוֹרַיְתָא, "
         "דִּי בְּאַתְרָא הָדֵן וְדִי בְּכָל אֲתַר וַאֲתַר, יְהֵא לְהוֹן וּלְכוֹן "
         "שְׁלָמָא רַבָּא, חִנָּא וְחִסְדָּא וְרַחֲמִין, וְחַיִּין אֲרִיכִין, "
         "וּמְזוֹנֵי רְוִיחֵי, וּפֻרְקָנָא מִן קֳדָם אֲבוּהוֹן דְּבִשְׁמַיָּא "
         "וְאַרְעָא, וְאִמְרוּ אָמֵן."))

prayer("kaddish_derabbanan_yehe_shelama", "יְהֵא שְׁלָמָא רַבָּא", "kaddish/derabbanan/yehe_shelama", 47, 47,
       d(U + "kaddish/derabbanan/yehe_shelama",
         "יְהֵא שְׁלָמָא רַבָּא מִן שְׁמַיָּא, וְחַיִּים טוֹבִים, עָלֵֽינוּ וְעַל "
         "כָּל יִשְׂרָאֵל, וְאִמְרוּ אָמֵן."))

prayer("kaddish_derabbanan_oseh_shalom", "עֹשֶׂה שָׁלוֹם בִּמְרוֹמָיו", "kaddish/derabbanan/oseh_shalom", 47, 47,
       d(U + "kaddish/derabbanan/oseh_shalom",
         "עֹשֶׂה שָׁלוֹם בִּמְרוֹמָיו, הוּא בְּרַחֲמָיו יַעֲשֶׂה שָׁלוֹם עָלֵֽינוּ "
         "וְעַל כָּל יִשְׂרָאֵל, וְאִמְרוּ אָמֵן."))
