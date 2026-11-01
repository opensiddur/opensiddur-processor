# -*- coding: utf-8 -*-
"""Weekday opening and verses of praise, printed 49–69, through Half Kaddish.
The new biblical passages are built by pesukei_passages; the preceding opening
remains separate from the wrapper that begins at Hareni mezamen.
"""
import functools
from . import common
from .common import PRAYER
from .he_prayers import d
pb = functools.partial(common.pb, sigil=common.SIGIL_PESUKEI)
U = PRAYER
PRAYERS = []

def prayer(name, title, slug, first, last, body):
    PRAYERS.append(dict(name=name, title=title, urn=U + slug,
                        first=first, last=last, body=body))

prayer('mizmor_shir_chanukat_habayit', 'מִזְמוֹר שִׁיר חֲנֻכַּת הַבַּיִת', 'mizmor_shir_chanukat_habayit', 49, 49,
    "\n".join([f'<tei:div corresp="{U}mizmor_shir_chanukat_habayit">',
        '<tei:head xml:lang="he">תהלים ל</tei:head>',
        '<tei:div corresp="urn:x-opensiddur:text:bible:psalms/30">',
        d(U + "mizmor_shir_chanukat_habayit/aromimkha", f'{pb(49)}' + (
            'מִזְמוֹר שִׁיר חֲנֻכַּת הַבַּיִת לְדָוִד. אֲרוֹמִמְךָ, יְיָ, כִּי '
            'דִלִּיתָֽנִי, וְלֹא שִׂמַּֽחְתָּ אֹיְבַי לִי. יְיָ אֱלֹהָי, שִׁוַּעְתִּי '
            'אֵלֶֽיךָ וַתִּרְפָּאֵֽנִי. יְיָ, הֶעֱלִֽיתָ מִן שְׁאוֹל נַפְשִׁי, '
            'חִיִּיתַֽנִי מִיָּרְדִי בוֹר. זַמְּרוּ לַייָ חֲסִידָיו, וְהוֹדוּ לְזֵֽכֶר '
            'קָדְשׁוֹ. כִּי רֶֽגַע בְּאַפּוֹ, חַיִּים בִּרְצוֹנוֹ; בָּעֶֽרֶב יָלִין '
            'בֶּֽכִי, וְלַבֹּֽקֶר רִנָּה. וַאֲנִי אָמַֽרְתִּי בְשַׁלְוִי, בַּל אֶמּוֹט '
            'לְעוֹלָם. יְיָ, בִּרְצוֹנְךָ הֶעֱמַֽדְתָּה לְהַרְרִי עֹז; הִסְתַּרְתָּ '
            'פָנֶֽיךָ, הָיִיתִי נִבְהָל. אֵלֶֽיךָ יְיָ אֶקְרָא, וְאֶל אֲדֹנָי אֶתְחַנָּן.'
            ' מַה בֶּֽצַע בְּדָמִי, בְּרִדְתִּי אֶל שָֽׁחַת; הֲיוֹדְךָ עָפָר, הֲיַגִּיד '
            'אֲמִתֶּֽךָ. שְׁמַע יְיָ וְחָנֵּֽנִי; יְיָ הֱיֵה עֹזֵר לִי. הָפַֽכְתָּ '
            'מִסְפְּדִי לְמָחוֹל לִי; פִּתַּֽחְתָּ שַׂקִּי וַתְּאַזְּרֵֽנִי שִׂמְחָה.')),
        '<tei:note type="instruction" xml:lang="en">Reader</tei:note>',
        d(U + "mizmor_shir_chanukat_habayit/lemaan", 'לְמַֽעַן יְזַמֶּֽרְךָ כָבוֹד, וְלֹא יִדֹּם; יְיָ אֱלֹהַי, לְעוֹלָם אוֹדֶֽךָּ.'),
        "</tei:div></tei:div>"]))

prayer('kaddish_yatom', 'קַדִּישׁ יָתוֹם', 'kaddish/yatom', 49, 51,
    "\n".join([f'<tei:div corresp="{U}kaddish/yatom">',
      f'<j:transclude type="external" target="{U}kaddish/yitgaddal"/>',
      f'<j:transclude type="external" target="{U}kaddish/yehe_shemeh"/>',
      f'<j:transclude type="external" target="{U}kaddish/yitbarakh"/>',
      d(U + "kaddish/yatom/yehe_shelama",
      f'{pb(51)}' + 'יְהֵא שְׁלָמָא רַבָּא מִן שְׁמַיָּא, וְחַיִּים, עָלֵֽינוּ וְעַל כָּל יִשְׂרָאֵל, וְאִמְרוּ אָמֵן.'),
      d(U + "kaddish/yatom/oseh_shalom", 'עֹשֶׂה שָׁלוֹם בִּמְרוֹמָיו, הוּא יַעֲשֶׂה שָׁלוֹם עָלֵֽינוּ וְעַל כָּל יִשְׂרָאֵל, וְאִמְרוּ אָמֵן.'),
      "</tei:div>"]))

prayer('hareini_mezammen', 'הֲרֵינִי מְזַמֵּן', 'hareini_mezammen', 51, 51,
    d(U + "hareini_mezammen", 'הֲרֵינִי מְזַמֵּן אֶת פִּי לְהוֹדוֹת וּלְהַלֵּל וּלְשַׁבֵּֽחַ אֶת בּוֹרְאִי.'))

prayer('barukh_sheamar', 'בָּרוּךְ שֶׁאָמַר', 'pesuqei_dezimrah/barukh_sheamar', 51, 51,
    "\n".join([f'<tei:div corresp="{U}pesuqei_dezimrah/barukh_sheamar">',
        d(U + "pesuqei_dezimrah/barukh_sheamar/barukh", (
            'בָּרוּךְ שֶׁאָמַר וְהָיָה הָעוֹלָם, בָּרוּךְ הוּא. בָּרוּךְ עוֹשֶׂה '
            'בְרֵאשִׁית, בָּרוּךְ אוֹמֵר וְעוֹשֶׂה, בָּרוּךְ גּוֹזֵר וּמְקַיֵּם, בָּרוּךְ'
            ' מְרַחֵם עַל הָאָֽרֶץ, בָּרוּךְ מְרַחֵם עַל הַבְּרִיּוֹת, בָּרוּךְ מְשַׁלֵּם'
            ' שָׂכָר טוֹב לִירֵאָיו, בָּרוּךְ חַי לָעַד וְקַיָּם לָנֶֽצַח, בָּרוּךְ '
            'פּוֹדֶה וּמַצִּיל, בָּרוּךְ שְׁמוֹ. בָּרוּךְ אַתָּה, יְיָ אֱלֹהֵֽינוּ, '
            'מֶֽלֶךְ הָעוֹלָם, הָאֵל, הָאָב הָרַחֲמָן, הַמְהֻלָּל בְּפִי עַמּוֹ, '
            'מְשֻׁבָּח וּמְפֹאָר בִּלְשׁוֹן חֲסִידָיו וַעֲבָדָיו. וּבְשִׁירֵי דָוִד '
            'עַבְדְּךָ נְהַלֶּלְךָ, יְיָ אֱלֹהֵֽינוּ; בִּשְׁבָחוֹת וּבִזְמִירוֹת '
            'נְגַדֶּלְךָ וּנְשַׁבֵּחֲךָ וּנְפָאֶרְךָ, וְנַזְכִּיר שִׁמְךָ וְנַמְלִיכְךָ, '
            'מַלְכֵּֽנוּ, אֱלֹהֵֽינוּ.')),
        '<tei:note type="instruction" xml:lang="en">Reader</tei:note>',
        d(U + "pesuqei_dezimrah/barukh_sheamar/yachid", 'יָחִיד, חֵי הָעוֹלָמִים, מֶֽלֶךְ, מְשֻׁבָּח וּמְפֹאָר עֲדֵי־עַד שְׁמוֹ הַגָּדוֹל. בָּרוּךְ אַתָּה, יְיָ, מֶֽלֶךְ מְהֻלָּל בַּתִּשְׁבָּחוֹת.'),
        "</tei:div>"]))

# Biblical passages before Ashrei.
from .pesukei_passages import prayers
PRAYERS += prayers("he")

from .pesukei_completion import prayers as completion_prayers
PRAYERS += completion_prayers("he")
