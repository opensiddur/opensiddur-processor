# -*- coding: utf-8 -*-
"""The Hebrew of Seder Hanachath Tefillin, read off printed pages 5, 7, 9 and 11.

Four printed pages and three page turns, every one of them mid-sentence: the meditation
begins on 5 and ends on 7, the Yehi Ratzon begins on 7 and ends on 9, and the parashiyoth
begin on 9 and end on 11. So three `tei:pb` sit inside a `tei:p` here.

**Barukh Shem is not emitted by this module.** The print sets it on page 7 between the two
blessings, and the children's page already sets the same words at page 1, where it is
realised as `prayer:shema/barukh_shem`. `refdb` refuses a text URN mapped twice inside one
project, and re-emitting it would be wrong even if it did not: they are the same words
wherever the book prints them. The unit transcludes the URN and the children's file gains
a second `tei:pb` under this unit's sigil -- which is what `SIDDUR_URN_SCHEME.md` means by
one text printed on several pages.

**The restriction to weekdays is not encoded.** Tefillin are not worn on Sabbaths and
festivals, and Birnbaum says so -- in a footnote on printed page 6, with his reason. No
rubric anywhere on pages 5 to 11 conditions these passages on the day. So they stand
unconditional and the fact stays in the apparatus, where he put it.
"""
import functools

from .common import PRAYER
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


prayer("tefillin_hineni_mekhavven", "הִנְנִי מְכַוֵּן", "tefillin/hineni_mekhavven", 5, 7,
       d(U + "tefillin/hineni_mekhavven",
         "הִנְנִי מְכַוֵּן בְּהַנָּחַת תְּפִלִּין לְקַיֵּם מִצְוַת בּוֹרְאִי שֶׁצִּוָּֽנוּ "
         "לְהַנִּֽיחַ תְּפִלִּין, כַּכָּתוּב בַּתּוֹרָה: וּקְשַׁרְתָּם לְאוֹת עַל יָדֶֽךָ, "
         "וְהָיוּ לְטֹטָפֹת בֵּין עֵינֶֽיךָ. וְהֵם אַרְבַּע פָּרָשִׁיּוֹת אֵֽלּוּ: שְׁמַע, "
         "וְהָיָה אִם שָׁמֹֽעַ, קַדֶּשׁ, וְהָיָה כִּי יְבִיאֲךָ, שֶׁיֵּשׁ בָּהֶם יִחוּדוֹ "
         "וְאַחְדוּתוֹ יִתְבָּרַךְ שְׁמוֹ בָּעוֹלָם; וְשֶׁנִּזְכֹּר נִסִּים וְנִפְלָאוֹת "
         f"שֶׁעָשָׂה עִמָּֽנוּ בְּהוֹצִיאוֹ אוֹתָֽנוּ {pb(7)}מִמִּצְרָֽיִם, וַאֲשֶׁר לוֹ "
         "הַכֹּֽחַ וְהַמֶּמְשָׁלָה בָּעֶלְיוֹנִים וּבַתַּחְתּוֹנִים לַעֲשׂוֹת בָּהֶם "
         "כִּרְצוֹנוֹ. וְצִוָּֽנוּ לְהַנִֽיחַ עַל הַיָּד לְזִכְרוֹן זְרוֹעוֹ הַנְּטוּיָה; "
         "וְשֶׁהִיא נֶֽגֶד הַלֵּב, לְשַׁעְבֵּד בָּזֶה תַּאֲוֺת וּמַחְשְׁבוֹת לִבֵּֽנוּ "
         "לַעֲבוֹדָתוֹ, יִתְבָּרַךְ שְׁמוֹ; וְעַל הָרֹאשׁ נֶֽגֶד הַמֹּֽחַ, שֶׁהַנְּשָׁמָה "
         "שֶׁבְּמֹחִי עִם שְׁאָר חוּשַׁי וְכֹחוֹתַי כֻּלָּם יִהְיוּ מְשֻׁעְבָּדִים "
         "לַעֲבוֹדָתוֹ, יִתְבָּרַךְ שְׁמוֹ. וּמִשֶּֽׁפַע מִצְוַת תְּפִלִּין יִתְמַשֵּׁךְ "
         "עָלַי לִהְיוֹת לִי חַיִּים אֲרֻכִּים וְשֶֽׁפַע קֹֽדֶשׁ וּמַחֲשָׁבוֹת קְדוֹשׁוֹת, "
         "בְּלִי הַרְהוֹר חֵטְא וְעָוֺן כְּלָל, וְשֶׁלֹּא יְפַתֵּֽנוּ וְלֹא יִתְגָּֽרֶה "
         "בָּֽנוּ יֵֽצֶר הָרָע, וְיַנִּיחֵֽנוּ לַעֲבוֹד אֶת יְיָ כַּאֲשֶׁר עִם לְבָבֵֽנוּ. "
         "אָמֵן."))

prayer("tefillin_lehanniach", "בִּרְכַּת לְהָנִֽיחַ", "tefillin/lehanniach", 7, 7,
       d(U + "tefillin/lehanniach",
         "בָּרוּךְ אַתָּה, יְיָ אֱלֹהֵֽינוּ, מֶֽלֶךְ הָעוֹלָם, אֲשֶׁר קִדְּשָֽׁנוּ "
         "בְּמִצְוֺתָיו וְצִוָּֽנוּ לְהַנִּֽיחַ תְּפִלִּין."))

prayer("tefillin_al_mitzvat", "עַל מִצְוַת תְּפִלִּין", "tefillin/al_mitzvat", 7, 7,
       d(U + "tefillin/al_mitzvat",
         "בָּרוּךְ אַתָּה, יְיָ אֱלֹהֵֽינוּ, מֶֽלֶךְ הָעוֹלָם, אֲשֶׁר קִדְּשָֽׁנוּ "
         "בְּמִצְוֺתָיו וְצִוָּֽנוּ עַל מִצְוַת תְּפִלִּין."))

prayer("tefillin_umechokhmatekha", "וּמֵחָכְמָתְךָ", "tefillin/umechokhmatekha", 7, 7,
       d(U + "tefillin/umechokhmatekha",
         "וּמֵחָכְמָתְךָ, אֵל עֶלְיוֹן, תַּאֲצִיל עָלַי, וּמִבִּינָתְךָ תְּבִינֵֽנִי; "
         "וּבְחַסְדְּךָ תַּגְדִּיל עָלַי, וּבִגְבוּרָתְךָ תַּצְמִית אֹיְבַי וְקָמַי; "
         "וְשֶֽׁמֶן הַטּוֹב תָּרִיק עַל שִׁבְעָה קְנֵי הַמְּנוֹרָה לְהַשְׁפִּֽיעַ טוּבְךָ "
         "לִבְרִיּוֹתֶֽיךָ. פּוֹתֵֽחַ אֶת יָדֶֽךָ, וּמַשְׂבִּֽיעַ לְכָל חַי רָצוֹן."))

prayer("tefillin_verastikh", "וְאֵרַשְׂתִּיךְ", "tefillin/verastikh", 7, 7,
       d(U + "tefillin/verastikh",
         "וְאֵרַשְׂתִּיךְ לִי לְעוֹלָם, וְאֵרַשְׂתִּיךְ לִי בְּצֶֽדֶק וּבְמִשְׁפָּט "
         "וּבְחֶֽסֶד וּבְרַחֲמִים. וְאֵרַשְׂתִּיךְ לִי בֶּאֱמוּנָה, וְיָדַֽעַתְּ אֶת יְיָ."))

prayer("tefillin_yehi_ratzon", "וִיהִי רָצוֹן", "tefillin/yehi_ratzon", 7, 9,
       d(U + "tefillin/yehi_ratzon",
         "וִיהִי רָצוֹן מִלְּפָנֶֽיךָ, יְיָ אֱלֹהֵֽינוּ וֵאלֹהֵי אֲבוֹתֵֽינוּ, שֶׁתְּהֵא "
         f"{pb(9)}חֲשׁוּבָה מִצְוַת הֲנָחַת תְּפִלִּין זוֹ כְּאִלּוּ קִיַּמְתִּֽיהָ בְּכָל "
         "פְּרָטֶֽיהָ וְדִקְדּוּקֶֽיהָ וְכַוָּנוֹתֶֽיהָ וְתַרְיַ\"ג מִצְוֺת הַתְּלוּיִם "
         "בָּהּ. אָמֵן סֶֽלָה."))

#: The four sections the tefillin contain, as the print sets them: Exodus 13:1-16 under a
#: centred source citation, in two paragraphs with nothing between them. The English page
#: parts them at exactly the same point, so the parting needs no URN of its own -- unlike
#: Mah Tovu, where only one side parted the passage. See `readings/9.md` and `10`.
prayer("tefillin_parashiyot", "פָּרָשִׁיּוֹת הַתְּפִלִּין", "tefillin/parashiyot", 9, 11,
       d(U + "tefillin/parashiyot",
         "וַיְדַבֵּר יְיָ אֶל־מֹשֶׁה לֵּאמֹר: קַדֶּשׁ־לִי כָל בְּכוֹר, פֶּֽטֶר כָּל רֶֽחֶם "
         "בִּבְנֵי יִשְׂרָאֵל, בָּאָדָם וּבַבְּהֵמָה, לִי הוּא. וַיֹּֽאמֶר מֹשֶׁה אֶל "
         "הָעָם: זָכוֹר אֶת הַיּוֹם הַזֶּה אֲשֶׁר יְצָאתֶם מִמִּצְרַֽיִם, מִבֵּית "
         "עֲבָדִים, כִּי בְּחֹֽזֶק יָד הוֹצִיא יְיָ אֶתְכֶם מִזֶּה; וְלֹא יֵאָכֵל חָמֵץ. "
         "הַיּוֹם אַתֶּם יֹצְאִים, בְּחֹֽדֶשׁ הָאָבִיב. וְהָיָה כִי יְבִיאֲךָ יְיָ אֶל "
         "אֶֽרֶץ הַכְּנַעֲנִי, וְהַחִתִּי וְהָאֱמֹרִי וְהַחִוִּי וְהַיְבוּסִי, אֲשֶׁר "
         "נִשְׁבַּע לַאֲבֹתֶֽיךָ לָֽתֶת לָךְ, אֶֽרֶץ זָבַת חָלָב וּדְבָשׁ, וְעָבַדְתָּ אֶת "
         "הָעֲבֹדָה הַזֹּאת בַּחֹֽדֶשׁ הַזֶּה. שִׁבְעַת יָמִים תֹּאכַל מַצֹּת, וּבַיּוֹם "
         "הַשְּׁבִיעִי חַג לַייָ. מַצּוֹת יֵאָכֵל אֵת שִׁבְעַת הַיָּמִים, וְלֹא יֵרָאֶה "
         "לְךָ חָמֵץ וְלֹא יֵרָאֶה לְךָ שְׂאֹר בְּכָל גְּבֻלֶֽךָ. וְהִגַּדְתָּ לְבִנְךָ "
         "בַּיּוֹם הַהוּא לֵאמֹר: בַּעֲבוּר זֶה עָשָׂה יְיָ לִי בְּצֵאתִי מִמִּצְרָֽיִם. "
         "וְהָיָה לְךָ לְאוֹת עַל יָדְךָ, וּלְזִכָּרוֹן בֵּין עֵינֶֽיךָ, לְמַֽעַן תִּהְיֶה "
         "תּוֹרַת יְיָ בְּפִֽיךָ, כִּי בְּיָד חֲזָקָה הוֹצִאֲךָ יְיָ מִמִּצְרָֽיִם. "
         "וְשָׁמַרְתָּ אֶת הַחֻקָּה הַזֹּאת לְמוֹעֲדָהּ מִיָּמִים יָמִֽימָה.",

         "וְהָיָה, כִּי יְבִאֲךָ יְיָ אֶל אֶֽרֶץ הַכְּנַעֲנִי, כַּאֲשֶׁר נִשְׁבַּע לְךָ "
         "וְלַאֲבֹתֶֽיךָ, וּנְתָנָהּ לָךְ. וְהַעֲבַרְתָּ כָל פֶּֽטֶר רֶֽחֶם לַייָ; וְכָל "
         "פֶּֽטֶר שֶֽׁגֶר בְּהֵמָה אֲשֶׁר יִהְיֶה לְךָ, הַזְּכָרִים, לַייָ. וְכָל פֶּֽטֶר "
         "חֲמֹר תִּפְדֶּה בְשֶׂה, וְאִם לֹא תִפְדֶּה וַעֲרַפְתּוֹ; וְכֹל בְּכוֹר אָדָם "
         "בְּבָנֶֽיךָ תִּפְדֶּה. וְהָיָה, כִּי יִשְׁאָלְךָ בִנְךָ מָחָר לֵאמֹר מַה זֹּאת, "
         "וְאָמַרְתָּ אֵלָיו: בְּחֹֽזֶק יָד הוֹצִיאָֽנוּ יְיָ מִמִּצְרַֽיִם, מִבֵּית "
         "עֲבָדִים. וַיְהִי כִּי הִקְשָׁה פַרְעֹה לְשַׁלְּחֵֽנוּ, וַיַּהֲרֹג יְיָ כָּל "
         f"בְּכוֹר בְּאֶֽרֶץ מִצְרַֽיִם, {pb(11)}מִבְּכוֹר אָדָם וְעַד בְּכוֹר בְּהֵמָה, "
         "עַל כֵּן אֲנִי זֹבֵֽחַ לַייָ כָּל פֶּֽטֶר רֶֽחֶם, הַזְּכָרִים, וְכָל בְּכוֹר "
         "בָּנַי אֶפְדֶּה. וְהָיָה לְאוֹת עַל יָדְכָה, וּלְטוֹטָפֹת בֵּין עֵינֶֽיךָ, כִּי "
         "בְּחֹֽזֶק יָד הוֹצִיאָֽנוּ יְיָ מִמִּצְרָֽיִם."))
