# -*- coding: utf-8 -*-
"""The Hebrew of Mah Tovu and Seder Atifath Tallith, read off printed pages 3 and 5.

The first sub-unit of Birkhoth ha-Shaḥar. Printed page 3 opens the section under its own
heading and runs to the end of Hineni Mitatef; page 5 carries the blessing over wrapping,
Psalm 36:8-11 and the Yehi Ratzon that closes the order.

**Mah Tovu is one paragraph here and two on the facing English page.** The print sets the
whole catena -- Numbers 24:5, then Psalms 5:8, 26:8, 95:6, 69:14 -- as a single unbroken
paragraph, and page 4 begins a new indented paragraph at *By thy abundant grace I enter
thy house*. The two sides join on exact URN equality, so a parting made on one side and
not the other pairs the columns at the top of the passage and lets them drift through the
rest of it.

So the parting is named on both sides and the paragraphing of each is kept: here two
milestone ranges inside the one printed paragraph, there the same ranges in two ``tei:p``. That is the same device
page 1 uses for its run-on paragraph, applied in the other direction -- there the print
ran several texts together on both sides, here it runs them together on one side only.
"""
import functools

from .milestones import marked
from .common import PRAYER
from . import common

#: Every page break in this module belongs to Birkhoth ha-Shaḥar.
pb = functools.partial(common.pb, sigil=common.SIGIL_BIRCHOT)

U = PRAYER

PRAYERS = []


def prayer(name, title, slug, first, last, body):
    PRAYERS.append(dict(name=name, title=title, urn=U + slug,
                        first=first, last=last, body=body))


def d(urn, *paras, indent=8):
    """A division carrying a URN and holding its paragraphs."""
    pad = " " * indent
    inner = "\n".join(f"{pad}  <tei:p>{p}</tei:p>" for p in paras)
    return f'{pad}<tei:div corresp="{urn}">\n{inner}\n{pad}</tei:div>'


def passage(slug, text):
    return marked(U + slug, text)


prayer("birkhot_mah_tovu", "מַה טֹּֽבוּ", "mah_tovu", 3, 3, "\n".join([
    f'        <tei:div corresp="{U}mah_tovu">',
    '          <tei:p>'
    + passage("mah_tovu/mah_tovu",
          "מַה טֹּֽבוּ אֹהָלֶֽיךָ יַעֲקֹב, מִשְׁכְּנֹתֶֽיךָ יִשְׂרָאֵל.")
    + " "
    + passage("mah_tovu/varani",
          "וַאֲנִי בְּרֹב חַסְדְּךָ אָבֹא בֵיתֶֽךָ, אֶשְׁתַּחֲוֶה אֶל הֵיכַל "
          "קָדְשְׁךָ בְּיִרְאָתֶֽךָ. יְיָ, אָהַֽבְתִּי מְעוֹן בֵּיתֶֽךָ, וּמְקוֹם "
          "מִשְׁכַּן כְּבוֹדֶֽךָ. וַאֲנִי אֶשְׁתַּחֲוֶה וְאֶכְרָֽעָה, אֶבְרְכָה "
          "לִפְנֵי יְיָ עֹשִׂי. וַאֲנִי תְפִלָּתִי לְךָ, יְיָ, עֵת רָצוֹן; "
          "אֱלֹהִים, בְּרָב־חַסְדֶּֽךָ, עֲנֵֽנִי בֶּאֱמֶת יִשְׁעֶֽךָ.")
    + '</tei:p>',
    '        </tei:div>']))

prayer("tallith_barkhi_nafshi", "בָּרְכִי נַפְשִׁי", "tallith/barkhi_nafshi", 3, 3,
       d(U + "tallith/barkhi_nafshi",
         "בָּרְכִי נַפְשִׁי אֶת יְיָ; יְיָ אֱלֹהַי, גָּדַֽלְתָּ מְאֹד, הוֹד וְהָדָר "
         "לָבָֽשְׁתָּ. עֹֽטֶה אוֹר כַּשַּׂלְמָה, נוֹטֶה שָׁמַֽיִם כַּיְרִיעָה."))

prayer("tallith_hineni_mitattef", "הִנְנִי מִתְעַטֵּף", "tallith/hineni_mitattef", 3, 3,
       d(U + "tallith/hineni_mitattef",
         "הִנְנִי מִתְעַטֵּף בְּטַלִּית שֶׁל צִיצִת כְּדֵי לְקַיֵּם מִצְוַת בּוֹרְאִי, "
         "כַּכָּתוּב בַּתּוֹרָה: וְעָשׂוּ לָהֶם צִיצִת עַל כַּנְפֵי בִגְדֵיהֶם "
         "לְדֹרֹתָם. וּכְשֵׁם שֶׁאֲנִי מִתְכַּסֶּה בְּטַלִּית בָּעוֹלָם הַזֶּה, כֵּן "
         "תִּזְכֶּה נִשְׁמָתִי לְהִתְלַבֵּשׁ בְּטַלִּית נָאָה לָעוֹלָם הַבָּא בְּגַן "
         "עֵֽדֶן. אָמֵן."))

prayer("tallith_lehitattef", "בִּרְכַּת הָעֲטִיפָה", "tallith/lehitattef", 5, 5,
       d(U + "tallith/lehitattef",
         f"{pb(5)}בָּרוּךְ אַתָּה, יְיָ אֱלֹהֵֽינוּ, מֶֽלֶךְ הָעוֹלָם, אֲשֶׁר "
         "קִדְּשָֽׁנוּ בְּמִצְוֺתָיו וְצִוָּֽנוּ לְהִתְעַטֵּף בַּצִּיצִת."))

prayer("tallith_mah_yaqar", "מַה יָּקָר", "tallith/mah_yaqar", 5, 5,
       d(U + "tallith/mah_yaqar",
         "מַה יָּקָר חַסְדְּךָ, אֱלֹהִים, וּבְנֵי אָדָם בְּצֵל כְּנָפֶֽיךָ יֶחֱסָיוּן. "
         "יִרְוְיֻן מִדֶּֽשֶׁן בֵּיתֶֽךָ, וְנַֽחַל עֲדָנֶֽיךָ תַשְׁקֵם. כִּי עִמְּךָ "
         "מְקוֹר חַיִּים, בְּאוֹרְךָ נִרְאֶה אוֹר. מְשֹׁךְ חַסְדְּךָ לְיֹדְעֶֽיךָ, "
         "וְצִדְקָתְךָ לְיִשְׁרֵי לֵב."))

prayer("tallith_yehi_ratzon", "יְהִי רָצוֹן", "tallith/yehi_ratzon", 5, 5,
       d(U + "tallith/yehi_ratzon",
         "יְהִי רָצוֹן מִלְּפָנֶֽיךָ, יְיָ אֱלֹהֵֽינוּ וֵאלֹהֵי אֲבוֹתֵֽינוּ, שֶׁתְּהֵא "
         "חֲשׁוּבָה מִצְוַת צִיצִת זוֹ כְּאִלּוּ קִיַּמְתִּֽיהָ בְּכָל פְּרָטֶֽיהָ "
         "וְדִקְדּוּקֶֽיהָ וְכַוָּנוֹתֶֽיהָ וְתַרְיַ\"ג מִצְוֺת הַתְּלוּיִם בָּהּ. "
         "אָמֵן סֶֽלָה."))
