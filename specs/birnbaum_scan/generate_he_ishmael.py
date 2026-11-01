# -*- coding: utf-8 -*-
"""Emit `build/he_ishmael.py`, lifting its text from the readings rather than retyping it.

Same reason and same use as `generate_he_korbanot.py`: see its docstring. Run from the
repository root, then check the result with `reverse`.
"""
import pathlib
import textwrap

ST = pathlib.Path("/home/efeins/src/opensiddur-repos/sourcetexts/feat_birnbaum-birchot-hashachar/sources/birnbaum_siddur/scan_reading")
PAGES = {p: (ST / "hebrew" / f"{p}.txt").read_text(encoding="utf-8").strip().split("\n\n")
         for p in (41, 43, 45, 47)}


def para(page, i):
    return PAGES[page][i].replace("\n", " ")


def lines(page, i):
    return PAGES[page][i].split("\n")


def literal(text, first_prefix="", indent=9):
    pad = " " * indent
    wrapped = textwrap.wrap(" ".join(text.split()), width=72, break_on_hyphens=False)
    out = []
    for n, line in enumerate(wrapped):
        tail = " " if n < len(wrapped) - 1 else ""
        if n == 0 and first_prefix:
            out.append(f'{pad}f"{first_prefix}{line}{tail}"')
        else:
            out.append(f'{pad}"{line}{tail}"')
    return "\n".join(out)


HEAD = '''# -*- coding: utf-8 -*-
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
    inner = "\\n".join(f"{pad}  <tei:p>{p}</tei:p>" for p in paras)
    return f'{pad}<tei:div corresp="{urn}">\\n{inner}\\n{pad}</tei:div>'

'''

BODY = []


def emit(code):
    BODY.append(code)


emit('prayer("ishmael_lead", "רַבִּי יִשְׁמָעֵאל אוֹמֵר", "middot/lead", 41, 41,\n'
     '       d(U + "middot/lead",\n' + literal(lines(41, 1)[0]) + "))\n")

#: Each rule is its own text, so a note or a translation can reach one of them.
RULES = ([(n, 41, 1, i) for n, i in zip("א ב ג ד ה ו".split(), range(1, 7))]
         + [(n, 43, 0, i) for n, i in zip("ז ח ט י יא יב".split(), range(0, 6))]
         + [("יג", 45, 0, 0)])
emit("#: One text per rule, so a note or a translation can reach a single one of them. The\n"
     "#: numeral is inside the text because the print sets it inline with the words.")
for ordinal, page, par, index in RULES:
    slug = f"middot/{RULES.index((ordinal, page, par, index)) + 1}"
    body = lines(page, par)[index]
    emit(f'prayer("middot_{RULES.index((ordinal, page, par, index)) + 1}", '
         f'"מִדָּה {ordinal}", "{slug}", {page}, {page},\n'
         f'       d(U + "{slug}",\n{literal(body)}))\n')

emit('prayer("ishmael_yehi_ratzon", "יְהִי רָצוֹן שֶׁיִּבָּנֶה בֵּית הַמִּקְדָּשׁ",\n'
     '       "middot/yehi_ratzon", 45, 45,\n'
     '       d(U + "middot/yehi_ratzon",\n' + literal(para(45, 1)) + "))\n")

emit("#: Kaddish d'Rabbanan. `יִתְבָּרַךְ` runs across the page turn at\n"
     "#: `וּלְעָלְמֵי עָלְמַיָּא. | יִתְבָּרַךְ`, which is a paragraph boundary, so the\n"
     "#: break opens the next passage rather than sitting inside this one.")
KADDISH = [
    ("kaddish_derabbanan_yitgaddal", "יִתְגַּדַּל וְיִתְקַדַּשׁ", "kaddish/derabbanan/yitgaddal",
     45, 45, para(45, 2), ""),
    ("kaddish_derabbanan_yehe_shemeh", "יְהֵא שְׁמֵהּ רַבָּא מְבָרַךְ",
     "kaddish/derabbanan/yehe_shemeh", 45, 45, para(45, 3), ""),
    ("kaddish_derabbanan_yitbarakh", "יִתְבָּרַךְ וְיִשְׁתַּבַּח",
     "kaddish/derabbanan/yitbarakh", 47, 47, para(47, 0), "{pb(47)}"),
    ("kaddish_derabbanan_al_yisrael", "עַל יִשְׂרָאֵל וְעַל רַבָּנָן",
     "kaddish/derabbanan/al_yisrael", 47, 47, para(47, 1), ""),
    ("kaddish_derabbanan_yehe_shelama", "יְהֵא שְׁלָמָא רַבָּא",
     "kaddish/derabbanan/yehe_shelama", 47, 47, para(47, 2), ""),
    ("kaddish_derabbanan_oseh_shalom", "עֹשֶׂה שָׁלוֹם בִּמְרוֹמָיו",
     "kaddish/derabbanan/oseh_shalom", 47, 47, para(47, 3), ""),
]
for name, title, slug, first, last, text, brk in KADDISH:
    emit(f'prayer("{name}", "{title}", "{slug}", {first}, {last},\n'
         f'       d(U + "{slug}",\n{literal(text, first_prefix=brk)}))\n')

out = pathlib.Path("opensiddur/importer/birnbaum_scan/build/he_ishmael.py")
out.write_text(HEAD + "\n" + "\n".join(BODY), encoding="utf-8")
print("wrote", out, len(BODY), "blocks")
