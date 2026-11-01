# -*- coding: utf-8 -*-
"""The Hebrew of Shaḥarith li-Yladim, read off printed page 1.

The whole section is one opening -- Hebrew on page 1, Birnbaum's English facing it on
page 2 -- and printed page 3 already begins בִּרְכוֹת הַשַּֽׁחַר. So every prayer here is
first=last=1, and there is exactly one page break in the unit.

Two things on this page that the Amidah's pages never asked for:

**A printed paragraph that holds several texts and shows no seam.** Under the rubric
"When dressed:" the print sets Deuteronomy 33:4, a blessing line, Proverbs 1:8, a
two-clause declaration, the first verse of the Shema with its response, Deuteronomy 4:4
and Genesis 49:18 as ONE run-on paragraph, and the facing English does the same. Nothing
in the layout separates them. They are therefore paired by ``tei:milestone`` boundaries inside the
single ``tei:p``: the two sides join on exact URN equality, so a passage that must line
up with its translation needs a URN of its own, and there is nothing else here to line
up on. Splitting them into transcluded files would align them too, and would destroy the
printed paragraph.

**An abridged text that is not the text it looks like.** The meditation here is three
sentences; what this same book prints at page 95 after the Shemoneh Esreh is far longer.
Different words, so a different text and its own URN -- ``prayer:yeladim/elohai_netzor``
-- and ``amidah_elohai_netzor.xml`` is left exactly as it stands.
"""
import functools

from .milestones import marked
from .common import PRAYER
from . import common

#: Every page break in this module belongs to the children's printing.
pb = functools.partial(common.pb, sigil=common.SIGIL_YELADIM)

U = PRAYER


#: Paragraphs handed to `wrap` sit one level inside the division it opens at eight.
PARA_INDENT = 10


def d(urn, *paras, indent=10):
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


def passage(slug, text):
    """One text inside a shared printed paragraph, named so the two sides can join."""
    return marked(U + slug, text)


PRAYERS = []


def prayer(name, title, slug, first, last, body):
    PRAYERS.append(dict(name=name, title=title, urn=U + slug, first=first, last=last, body=body))


# ---------------------------------------------------------------- 1
prayer("yeladim_modeh_ani", "מוֹדֶה אֲנִי", "modeh_ani", 1, 1,
    wrap(U + "modeh_ani", d(None,
        f'{pb(1)}מוֹדֶה אֲנִי לְפָנֶֽיךָ, מֶֽלֶךְ חַי וְקַיָּם, שֶׁהֶחֱזַֽרְתָּ בִּי נִשְׁמָתִי '
        f'בְּחֶמְלָה; רַבָּה אֱמוּנָתֶֽךָ.', indent=10)))

# The two blessings differ only in their last two words, and the print sets both out in
# full rather than abbreviating the second.
prayer("yeladim_netilat_yadayim", "בִּרְכַּת עַל נְטִילַת יָדָֽיִם", "al_netilat_yadayim", 1, 1,
    wrap(U + "al_netilat_yadayim", d(None,
        "בָּרוּךְ אַתָּה, יְיָ אֱלֹהֵֽינוּ, מֶֽלֶךְ הָעוֹלָם, אֲשֶׁר קִדְּשָֽׁנוּ בְּמִצְוֺתָיו "
        "וְצִוָּֽנוּ עַל נְטִילַת יָדָֽיִם.", indent=10)))

prayer("yeladim_tzitzit", "בִּרְכַּת צִיצִת", "al_mitzvat_tzitzit", 1, 1,
    wrap(U + "al_mitzvat_tzitzit", d(None,
        "בָּרוּךְ אַתָּה, יְיָ אֱלֹהֵֽינוּ, מֶֽלֶךְ הָעוֹלָם, אֲשֶׁר קִדְּשָֽׁנוּ בְּמִצְוֺתָיו "
        "וְצִוָּֽנוּ עַל מִצְוַת צִיצִת.", indent=10)))

# Nine texts, one printed paragraph. The two Shema verses keep their own canonical names
# rather than nesting under this composite: they are the same words wherever the book
# prints them, and a later unit that prints them must align with this one.
prayer("yeladim_torah_tzivvah", "תּוֹרָה צִוָּה לָֽנוּ מֹשֶׁה", "torah_tzivvah", 1, 1,
    wrap(U + "torah_tzivvah", d(None, " ".join([
        passage("torah_tzivvah/morashah", "תּוֹרָה צִוָּה לָֽנוּ מֹשֶׁה, מוֹרָשָׁה קְהִלַּת יַעֲקֹב."),
        passage("torah_tzivvah/berakhot", "בְּרָכוֹת יָחֻֽלוּ עַל רֹאשִׁי."),
        passage("torah_tzivvah/shema_beni", "שְׁמַע בְּנִי מוּסַר אָבִֽיךָ, וְאַל תִּטֹּשׁ תּוֹרַת אִמֶּֽךָ."),
        passage("torah_tzivvah/torah_tehi", "תּוֹרָה תְּהִי אֱמוּנָתִי, וְאֵל שַׁדַּי בְּעֶזְרָתִי."),
        passage("torah_tzivvah/el_melekh_neeman", "אֵל מֶֽלֶךְ נֶאֱמָן."),
        passage("shema/shema_yisrael", "שְׁמַע יִשְׂרָאֵל, יְיָ אֱלֹהֵֽינוּ, יְיָ אֶחָד."),
        passage("shema/barukh_shem", "בָּרוּךְ שֵׁם כְּבוֹד מַלְכוּתוֹ לְעוֹלָם וָעֶד."),
        passage("torah_tzivvah/veattem_hadveqim", "וְאַתֶּם הַדְּבֵקִים בַּייָ אֱלֹהֵיכֶם, חַיִּים כֻּלְּכֶם הַיּוֹם."),
        passage("torah_tzivvah/lishuatekha", "לִישׁוּעָתְךָ קִוִּֽיתִי, יְיָ."),
    ]), indent=10)))

prayer("yeladim_elohai_netzor", "אֱלֹהַי נְצֹר", "yeladim/elohai_netzor", 1, 1,
    wrap(U + "yeladim/elohai_netzor", d(None,
        "אֱלֹהַי, נְצֹר לְשׁוֹנִי מֵרָע, וּשְׂפָתַי מִדַּבֵּר מִרְמָה. פְּתַח לִבִּי "
        "בְּתוֹרָתֶֽךָ, וּבְמִצְוֺתֶֽיךָ תִּרְדּוֹף נַפְשִׁי. יִהְיוּ לְרָצוֹן אִמְרֵי פִי "
        "וְהֶגְיוֹן לִבִּי לְפָנֶֽיךָ, יְיָ, צוּרִי וְגוֹאֲלִי.", indent=10)))
