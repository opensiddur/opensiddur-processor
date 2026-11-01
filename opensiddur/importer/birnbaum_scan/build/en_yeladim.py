# -*- coding: utf-8 -*-
"""Birnbaum's English for Shaḥarith li-Yladim, read off printed page 2.

Emits the SAME URNs as :mod:`he_yeladim`, which is what aligns the two columns.

Read off the scan, as page 1 was, and afterwards checked against the proofread
en.wikisource transcription of the same leaf. 185 words, one difference, and the scan
settled it for the print: Birnbaum closes "falsehood." with a full stop where the
transcription has a comma. The facing Hebrew agrees — it closes מִרְמָה with a full stop
too, where the longer page-95 meditation has a comma because the sentence runs on there.
The transcription had punctuated the abridged text as though it were the long one.

The paragraph under "When dressed:" is continuous prose on this side too, with no visual
break between the nine texts it holds -- so it is segmented exactly as the Hebrew is, at
``tei:seg``, with matching URNs. There is nothing in either column's layout to align on;
the URNs are the whole mechanism. A ``@corresp`` repeated inside one document breaks that
join silently, so every slug here appears exactly once.

One thing the reading records that the encoding deliberately does not: this page sets its
rubrics in italic, and the facing Hebrew page sets the same rubrics in roman. Inside the
third rubric that inverts -- "arba kanfoth" is italic against roman on the Hebrew page and
indistinguishable inside the italic rubric here. Both sides mark the term as foreign and
leave the rest to the typography.
"""
import functools

from .milestones import marked
from .common import PRAYER
from . import common

#: Every page break in this module belongs to the children's printing.
pb = functools.partial(common.pb, sigil=common.SIGIL_YELADIM)

U = PRAYER

#: The Hebrew page and the English page that faces it. One opening, so one entry.
EN_PAGE = {1: 2}


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


# ---------------------------------------------------------------- 2
prayer("yeladim_modeh_ani", "Modeh Ani", "modeh_ani", 2, 2,
    wrap(U + "modeh_ani", d(None, pb(2) + "I render thanks to thee, everlasting King, who hast mercifully restored my soul within me; thy faithfulness is great.", indent=10)))

prayer("yeladim_netilat_yadayim", "Blessing for washing the hands", "al_netilat_yadayim", 2, 2,
    wrap(U + "al_netilat_yadayim", d(None, "Blessed art thou, Lord our God, King of the universe, who hast sanctified us with thy commandments, and commanded us concerning the washing of the hands.", indent=10)))

prayer("yeladim_tzitzit", "Blessing for the tsitsith", "al_mitzvat_tzitzit", 2, 2,
    wrap(U + "al_mitzvat_tzitzit", d(None, "Blessed art thou, Lord our God, King of the universe, who hast sanctified us with thy commandments, and commanded us concerning the precept of tsitsith.", indent=10)))

prayer("yeladim_torah_tzivvah", "The Torah which Moses handed down to us", "torah_tzivvah", 2, 2,
    wrap(U + "torah_tzivvah", d(None, " ".join([
        passage("torah_tzivvah/morashah", "The Torah which Moses handed down to us is the heritage of the community of Jacob."),
        passage("torah_tzivvah/berakhot", "May blessings rest on my head."),
        passage("torah_tzivvah/shema_beni", "Hear, my son, your father’s instruction, and reject not your mother’s teaching."),
        passage("torah_tzivvah/torah_tehi", "The Torah shall be my trust, and the Almighty my help."),
        passage("torah_tzivvah/el_melekh_neeman", "God is a faithful King."),
        passage("shema/shema_yisrael", "Hear, O Israel, the Lord is our God, the Lord is One."),
        passage("shema/barukh_shem", "Blessed be the name of his glorious majesty forever and ever."),
        passage("torah_tzivvah/veattem_hadveqim", "You who cling to the Lord are all alive today."),
        passage("torah_tzivvah/lishuatekha", "For thy salvation I hope, O Lord."),
    ]), indent=10)))

prayer("yeladim_elohai_netzor", "My God, guard my tongue", "yeladim/elohai_netzor", 2, 2,
    wrap(U + "yeladim/elohai_netzor", d(None, "My God, guard my tongue from evil, and my lips from speaking falsehood. Open my heart to thy Torah, that my soul may follow thy commands. May the words of my mouth and the meditation of my heart be pleasing before thee, O Lord, my Stronghold and my Redeemer.", indent=10)))
