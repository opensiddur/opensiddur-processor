# -*- coding: utf-8 -*-
"""Emit `build/he_korbanot.py`, lifting its text from the readings rather than retyping it.

This is kept because the module it writes is 340 lines of pointed Hebrew and **typing that
is how six words went wrong in `he_akedah`**. The generated file is committed and is the
source of record; this script is how it was made and how it is remade if a reading is
corrected.

It lives in `specs/` and not in the package because it reads the sourcetexts submodule,
which nothing importable may do -- CI has no submodule, and a test that read the committed
reading would be testing the data rather than the code.

Run from the repository root:

    uv run python specs/birnbaum_scan/generate_he_korbanot.py

then check it with `reverse`, which is the thing that actually proves it:

    uv run python -m opensiddur.importer.birnbaum_scan.reverse 27 29 31 33 35 37 39 \\
        --readings <sourcetexts>/.../scan_reading/hebrew --module he_korbanot
"""
import pathlib, textwrap

ST = pathlib.Path("/home/efeins/src/opensiddur-repos/sourcetexts/feat_birnbaum-birchot-hashachar/sources/birnbaum_siddur/scan_reading")
PAGES = {p: (ST / "hebrew" / f"{p}.txt").read_text(encoding="utf-8").strip().split("\n\n")
         for p in (27, 29, 31, 33, 35, 37, 39, 41)}


def para(page, i):
    return PAGES[page][i].replace("\n", " ")


def lines(page, i):
    return PAGES[page][i].split("\n")


def literal(text, first_prefix="", indent=9):
    """A run of Python string literals, wrapped, with an optional f-string head."""
    pad = " " * indent
    words = text.split()
    wrapped = textwrap.wrap(" ".join(words), width=72, break_on_hyphens=False)
    out = []
    for n, line in enumerate(wrapped):
        tail = " " if n < len(wrapped) - 1 else ""
        if n == 0 and first_prefix:
            out.append(f'{pad}f"{first_prefix}{line}{tail}"')
        else:
            out.append(f'{pad}"{line}{tail}"')
    return "\n".join(out)


def spanning(pieces, indent=9):
    """One paragraph assembled across page turns: [(text, pb_or_None), ...]."""
    out = []
    for n, (text, brk) in enumerate(pieces):
        out.append(literal(text, first_prefix=brk or "", indent=indent))
    return "\n".join(out)


BODY = []


def emit(code):
    BODY.append(code)


HEAD = '''# -*- coding: utf-8 -*-
"""The Hebrew of the korbanot, printed pages 27 to 41.

The laver, the Tamid and the ketoreth with their Yehi Ratzon passages; Pittum ha-Ketoreth
and the baraithoth that follow it; the verses and Abaye's order of the service; Ana
B'khoaḥ; Ribbon ha-Olamim; the Sabbath and Rosh Ḥodesh musaf passages; and Eizehu
Mekoman.

**Every scriptural passage is printed under a citation**, set in the Hebrew column in small
unpointed type. The citations are `tei:note type="citation"` on the unit rather than text
of the prayers: they are the same fact on both sides of the opening, set in each language's
own convention -- `שמות ל, יז–כא` against `Exodus 30:17–21` -- and a passage's words are
the same whether or not the citation is shown.

**The Sabbath and Rosh Ḥodesh passages are the unit's first conditionals.** They are
additions and not substitutions: on an ordinary weekday neither is said and the page simply
has less on it. So each is a plain `j:conditional`, not the negated pair the Amidah's
inserts need, and the rubric that introduces each is set as printed -- English, centred, on
the Hebrew page.

**Ana B'khoaḥ is seven lines of six words**, which is not a typographic choice: Birnbaum's
own footnote under printed 33 says so and explains that the forty-two words stand for the
forty-two-letter Name. An encoding that reflowed the lines would be contradicted by the
apparatus printed beneath them.

**The text in this file is lifted from `scan_reading/hebrew/*.txt`, not retyped.** The
first draft of `he_akedah` was typed and had six words wrong; `reverse` checks every page
of this one against the reading, word for word.
"""
import functools

from .common import PRAYER, POEM, cond, endcond, feature
from . import common

pb = functools.partial(common.pb, sigil=common.SIGIL_BIRCHOT)

U = PRAYER
P = POEM

PRAYERS = []


def prayer(name, title, slug, first, last, body, *, base=None):
    PRAYERS.append(dict(name=name, title=title, urn=(base or U) + slug,
                        first=first, last=last, body=body))


def d(urn, *paras, indent=8):
    pad = " " * indent
    inner = "\\n".join(f"{pad}  <tei:p>{p}</tei:p>" for p in paras)
    return f'{pad}<tei:div corresp="{urn}">\\n{inner}\\n{pad}</tei:div>'


def verses(urn, ls, *, indent=8):
    """Verses the print sets one to a centred line."""
    pad = " " * indent
    inner = "\\n".join(f"{pad}    <tei:l>{line}</tei:l>" for line in ls)
    return ('%s<tei:div corresp="%s">\\n%s  <tei:lg>\\n%s\\n%s  </tei:lg>\\n%s</tei:div>'
            % (pad, urn, pad, inner, pad, pad))

'''

#: Every prayer of the korbanot, **in the order the print sets them**. The order matters:
#: `reverse` gathers the authored words page by page in declaration order, so grouping the
#: simple passages before the spanning ones put the Tamid's tail after the ketoreth on
#: printed 29 and the diff said so at once.
#:
#: kind is "p" (one paragraph), "s" (a paragraph spanning a page turn), "v" (verse lines)
#: or a callable emitting its own code.
ORDER = [
    ("p", "korbanot_kiyor", "פָּרָשַׁת הַכִּיּוֹר", "korbanot/kiyor", (27, 0), None),
    ("p", "korbanot_yehi_ratzon_miqdash", "יְהִי רָצוֹן שֶׁתְּרַחֵם עָלֵֽינוּ",
     "korbanot/yehi_ratzon_miqdash", (27, 1), None),
    ("s", "korbanot_tamid", "פָּרָשַׁת הַתָּמִיד", "korbanot/tamid", [(27, 2), (29, 0)],
     "#: Runs across the page turn at `נֶֽסֶךְ שֵׁכָר לַייָ. | וְאֵת הַכֶּֽבֶשׂ`."),
    ("p", "korbanot_ushchat", "וְשָׁחַט אֹתוֹ", "korbanot/ushchat", (29, 1), None),
    ("p", "korbanot_yehi_ratzon_amirah", "יְהִי רָצוֹן שֶׁתְּהֵא אֲמִירָה זוֹ",
     "korbanot/yehi_ratzon_amirah", (29, 2), None),
    ("p", "korbanot_atah_hu", "אַתָּה הוּא יְיָ אֱלֹהֵֽינוּ שֶׁהִקְטִֽירוּ",
     "korbanot/atah_hu", (29, 3), None),
    ("p", "korbanot_ketoret", "פָּרָשַׁת הַקְּטֹֽרֶת", "korbanot/ketoret", (29, 4), None),
    ("s", "korbanot_pittum", "פִּטּוּם הַקְּטֹֽרֶת", "korbanot/pittum_haketoret",
     [(29, 5), (31, 0)],
     "#: Runs across the page turn at `וְשׁוֹחֲקָן | יָפֶה יָפֶה`, which falls inside a\n"
     "#: phrase rather than between sentences."),
    ("p", "korbanot_rashbag", "רַבָּן שִׁמְעוֹן בֶּן גַּמְלִיאֵל",
     "korbanot/pittum_haketoret/rashbag", (31, 1), None),
    ("p", "korbanot_rabbi_natan", "תַּנְיָא, רַבִּי נָתָן אוֹמֵר",
     "korbanot/pittum_haketoret/rabbi_natan", (31, 2), None),
    ("s", "korbanot_bar_kappara", "תַּנְיָא, בַּר קַפָּרָא אוֹמֵר",
     "korbanot/pittum_haketoret/bar_kappara", [(31, 3), (33, 0)],
     "#: Runs across the page turn at `לַעֲמֹד מִפְּנֵי | רֵיחָהּ`."),
    ("v", "korbanot_pesukim", "יְיָ צְבָאוֹת עִמָּֽנוּ", "korbanot/pesukim", (33, 1),
     "#: Three verses, each on its own centred line in the print. The English page sets\n"
     "#: them as indented lines instead -- see `readings/english_28_48.md`."),
    ("p", "korbanot_atah_seter", "אַתָּה סֵֽתֶר לִי", "korbanot/atah_seter", (33, 2), None),
    ("p", "korbanot_vearvah", "וְעָרְבָה לַייָ", "korbanot/vearvah", (33, 3), None),
    ("p", "korbanot_abaye", "סֵֽדֶר הַמַּעֲרָכָה", "korbanot/seder_hamaarakhah",
     (33, 4), None),
    ("ana", None, None, None, None, None),
    ("p", "korbanot_ribbon_haolamim", "רִבּוֹן הָעוֹלָמִים", "korbanot/ribbon_haolamim",
     (35, 1), None),
    ("p", "korbanot_musaf_shabbat", "מוּסַף שֶׁל שַׁבָּת", "korbanot/musaf/shabbat",
     (35, 2),
     "#: Said only on the day its rubric names, and nothing is negated when it is not:\n"
     "#: on an ordinary weekday the page simply has less on it. A plain conditional, and\n"
     "#: not the negated pair the Amidah's inserts need."),
    ("s", "korbanot_musaf_rosh_chodesh", "מוּסַף שֶׁל רֹאשׁ חֹֽדֶשׁ",
     "korbanot/musaf/rosh_chodesh", [(35, 3), (37, 0)], None),
    ("p", "eizehu_mekoman_1", "אֵיזֶֽהוּ מְקוֹמָן א", "eizehu_mekoman/1", (37, 1),
     "#: Eizehu Mekoman. Each mishnah opens with its Hebrew numeral and a full stop, set\n"
     "#: inline with the words -- the numeral is text and not a heading, and the English\n"
     "#: side sets `1.` where this sets `א.`."),
    ("p", "eizehu_mekoman_2", "אֵיזֶֽהוּ מְקוֹמָן ב", "eizehu_mekoman/2", (37, 2), None),
    ("p", "eizehu_mekoman_3", "אֵיזֶֽהוּ מְקוֹמָן ג", "eizehu_mekoman/3", (37, 3), None),
    ("p", "eizehu_mekoman_4", "אֵיזֶֽהוּ מְקוֹמָן ד", "eizehu_mekoman/4", (39, 0), None),
    ("p", "eizehu_mekoman_5", "אֵיזֶֽהוּ מְקוֹמָן ה", "eizehu_mekoman/5", (39, 1), None),
    ("p", "eizehu_mekoman_6", "אֵיזֶֽהוּ מְקוֹמָן ו", "eizehu_mekoman/6", (39, 2), None),
    ("p", "eizehu_mekoman_7", "אֵיזֶֽהוּ מְקוֹמָן ז", "eizehu_mekoman/7", (39, 3), None),
    ("s", "eizehu_mekoman_8", "אֵיזֶֽהוּ מְקוֹמָן ח", "eizehu_mekoman/8",
     [(39, 4), (41, 0)],
     "#: The eighth runs onto printed 41, where Rabbi Ishmael's rules begin."),
]

ANA_COMMENT = ("#: Seven lines of six words, which is not a typographic choice: Birnbaum's\n"
               "#: own footnote under printed 33 says so and explains that the forty-two\n"
               "#: words stand for the forty-two-letter Name. The break falls after the\n"
               "#: second line, and `Barukh Shem` follows the poem on printed 35 -- realised\n"
               "#: by the children's unit, so transcluded here and not emitted.")

for kind, name, title, slug, where, comment in ORDER:
    if kind == "ana":
        ana = lines(33, 5) + lines(35, 0)[:5]
        assert len(ana) == 7 and all(len(x.split()) == 6 for x in ana)
        emit(ANA_COMMENT)
        emit('prayer("poem_anna_bekhoach", "אָנָּא בְּכֹֽחַ", "anna_bekhoach", 33, 35,\n'
             '       verses(P + "anna_bekhoach", [\n'
             + "\n".join(f'           "{v}",' for v in ana[:2])
             + '\n           f"{pb(35)}' + ana[2] + '",\n'
             + "\n".join(f'           "{v}",' for v in ana[3:]) + "\n       ]), base=P)\n")
        continue
    if comment:
        emit(comment)
    if kind == "p":
        page, index = where
        emit(f'prayer("{name}", "{title}", "{slug}", {page}, {page},\n'
             f'       d(U + "{slug}",\n{literal(para(page, index))}))\n')
    elif kind == "s":
        pieces = [(para(pg, ix), "" if n == 0 else "{pb(%d)}" % pg)
                  for n, (pg, ix) in enumerate(where)]
        emit(f'prayer("{name}", "{title}", "{slug}", {where[0][0]}, {where[-1][0]},\n'
             f'       d(U + "{slug}",\n{spanning(pieces)}))\n')
    elif kind == "v":
        page, index = where
        vs = lines(page, index)
        emit(f'prayer("{name}", "{title}", "{slug}", {page}, {page},\n'
             f'       verses(U + "{slug}", [\n'
             + "\n".join(f'           "{v}",' for v in vs) + "\n       ]))\n")

out = pathlib.Path("opensiddur/importer/birnbaum_scan/build/he_korbanot.py")
out.write_text(HEAD + "\n" + "\n".join(BODY), encoding="utf-8")
print("wrote", out, len(BODY), "blocks")
