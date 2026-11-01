# -*- coding: utf-8 -*-
"""Birnbaum's English for Seder Hanachath Tefillin, from printed pages 6, 8, 10 and 12.

Same URNs as the Hebrew, which is what aligns them. Three page turns, all mid-sentence and
all falling at the same point as the Hebrew side's -- the meditation, the Yehi Ratzon and
the parashiyoth each begin on one page and end on the next, on both sides of the opening.

Barukh Shem is transcluded, not emitted: see `he_tefillin`.

`Menorah` is marked foreign here as `tallith` and `tefillin` are. The print sets it italic
inside running roman text, which is the opposite of the rubrics' case and the same intent.
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


TEFILLIN = '<tei:foreign xml:lang="he-Latn">tefillin</tei:foreign>'
MENORAH = '<tei:foreign xml:lang="he-Latn">Menorah</tei:foreign>'

prayer("tefillin_hineni_mekhavven", "Meditation before putting on the tefillin",
       "tefillin/hineni_mekhavven", 6, 8,
       d(U + "tefillin/hineni_mekhavven",
         f"By putting on the {TEFILLIN} I intend to fulfill the command of my Creator, "
         f"who has commanded us to wear {TEFILLIN}, as it is written in the Torah: You "
         "shall bind them as a sign on your hand, and they shall be as frontlets between "
         f"your eyes. The {TEFILLIN} contain four sections of the Torah which proclaim "
         "the absolute unity of God, blessed be his name, and remind us of the miracles "
         "and wonders which he did for us when he brought us out from "
         f"{pb(8)}Egypt, he who has the power and the dominion over the heavenly and the "
         "earthly creatures to deal with them as he pleases. He has commanded us to wear "
         f"{TEFILLIN} on the arm in memory of his outstretched arm; opposite the heart, "
         "to intimate that we ought to subject our heart’s desires and designs to the "
         "service of God, blessed be he; and on the head opposite the brain, to intimate "
         "that the mind which is in the brain, and all senses and faculties, ought to be "
         "subjected to his service, blessed be he. May my observance of the "
         f"{TEFILLIN} precept bring me long life, holy inspiration and sacred thoughts, "
         "and free me from any sinful reflection whatever. May the evil impulse never "
         "tempt us, but leave us to serve the Lord as our heart desires."))

prayer("tefillin_lehanniach", "Blessing over binding the tefillin", "tefillin/lehanniach",
       8, 8,
       d(U + "tefillin/lehanniach",
         "Blessed art thou, Lord our God, King of the universe, who hast sanctified us "
         f"with thy commandments, and commanded us to wear {TEFILLIN}."))

prayer("tefillin_al_mitzvat", "Blessing over the precept of tefillin",
       "tefillin/al_mitzvat", 8, 8,
       d(U + "tefillin/al_mitzvat",
         "Blessed art thou, Lord our God, King of the universe, who hast sanctified us "
         "with thy commandments, and commanded us concerning the precept of "
         f"{TEFILLIN}."))

prayer("tefillin_umechokhmatekha", "Supreme God", "tefillin/umechokhmatekha", 8, 8,
       d(U + "tefillin/umechokhmatekha",
         "Supreme God, thou wilt imbue me with thy wisdom and thy intelligence; in thy "
         "grace thou wilt do great things for me; by thy might thou wilt cut off my foes "
         f"and my adversaries. Thou wilt pour the good oil into the seven branches of the "
         f"{MENORAH} so as to bestow thy goodness upon thy creatures. Thou openest thy "
         "hand, and satisfiest every living thing with favor."))

prayer("tefillin_verastikh", "I will betroth you to myself", "tefillin/verastikh", 8, 8,
       d(U + "tefillin/verastikh",
         "I will betroth you to myself forever; I will betroth you to myself in "
         "righteousness and in justice, in kindness and in mercy. I will betroth you to "
         "myself in faithfulness; and you shall know the Lord."))

prayer("tefillin_yehi_ratzon", "May it be thy will", "tefillin/yehi_ratzon", 8, 10,
       d(U + "tefillin/yehi_ratzon",
         "May it be thy will, Lord our God and God of our fathers, that "
         f"{pb(10)}my observance of this precept of {TEFILLIN} be considered as if I "
         "fulfilled it with all its particulars, details and implications, together with "
         "the six hundred and thirteen precepts that are related to it. Amen."))


#: Exodus 13:1-16 under its citation, in two paragraphs. The page turn falls inside the
#: second, at the same point the Hebrew page turns -- and both sides part the two portions
#: at the same place, so the parting needs no URN of its own. See
#: `readings/10.md` in sourcetexts.
prayer("tefillin_parashiyot", "The sections of the tefillin", "tefillin/parashiyot",
       10, 12,
       d(U + "tefillin/parashiyot",
         'The Lord spoke to Moses, saying: “Consecrate all the first-born to me, whatever is first-born in Israel, of man or of beast, for it belongs to me.”',
         'Moses said to the people: “Remember this day, in which you came out of Egypt, out of a house of slavery; for by a strong hand the Lord brought you out of this place; no leavened bread shall be eaten. This day you are leaving, in the month of Abib. And when the Lord will bring you into the land of the Canaanite, the Hittite, the Amorite, the Hivvite, and the Jebusite, which he swore to your fathers he would give you, a land flowing with milk and honey, then you shall perform this service in this month: For seven days you shall eat unleavened bread, and on the seventh day there shall be a festival in honor of the Lord. Unleavened bread shall be eaten throughout the seven days; no leavened bread shall be seen in your possession, nor any leaven, anywhere in your territory. And you shall tell your son on that day, saying; This is on account of what the Lord did for me when I left Egypt. It shall serve you as a sign on your hand, and as frontlets between your eyes, so that the Lord’s teaching may be ever in your mouth; for by a strong hand the Lord brought you out of Egypt. You shall observe this ordinance at its proper time from year to year. “And when the Lord will bring you into the land of the Canaanite, as he swore to you and to your fathers, and will give it to you, you shall make over to the Lord whatever is first-born; all the firstlings of the young animals that you will have, the males, shall be the Lord’s. Every firstling ass, however, you shall redeem with a lamb; but if you will not redeem it, then you shall break its neck; and every first-born son of yours you shall redeem. And when your son asks you in time to come: What does this mean? You shall tell him: By a strong hand the Lord brought us out of Egypt, out of a house of slavery; and when Pharaoh made difficulties about letting us go, the Lord slew every first-born in the' + pb(12) + 'land of Egypt, the first-born of both man and beast; that is why I sacrifice to the Lord every first-born male animal, but I redeem all my first-born sons. This shall serve as a sign on your hand, and as frontlets between your eyes; for the Lord brought you out of Egypt by a strong hand.”'))
