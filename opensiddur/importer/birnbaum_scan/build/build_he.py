# -*- coding: utf-8 -*-
"""Write the Hebrew project: one file per prayer, a unit file per unit, and an index."""
import argparse
import sys
from .common import set_project_directory
from .common import (PROJECT_EN, PROJECT_HE, PRAYER, SIDDUR, document, write, cond,
                    endcond, feature, SERVICE, AGG, HOL, PERSON)
from .front import SECTIONS, front_block, section_body
from .index import index
from .he_prayers import PRAYERS as AMIDAH_PRAYERS
from .he_yeladim import PRAYERS as YELADIM_PRAYERS
from .he_tallith import PRAYERS as TALLITH_PRAYERS
from .he_tefillin import PRAYERS as TEFILLIN_PRAYERS
from .he_poems import PRAYERS as POEM_PRAYERS
from .he_berakhot import PRAYERS as BERAKHOT_PRAYERS, BLESSINGS
from .he_akedah import PRAYERS as AKEDAH_PRAYERS
from .he_korbanot import PRAYERS as KORBANOT_PRAYERS
from .he_ishmael import PRAYERS as ISHMAEL_PRAYERS
from .he_pesukei import PRAYERS as PESUKEI_PRAYERS
from .shema import prayers as shema_prayers
SHEMA_PRAYERS = shema_prayers("he")
from .avinu_malkenu import prayers as avinu_prayers
AVINU_PRAYERS = avinu_prayers("he")
from .tachanun import prayers as tachanun_prayers
TACHANUN_PRAYERS = tachanun_prayers("he")
from .torah import prayers as torah_prayers
TORAH_PRAYERS = torah_prayers("he")

#: Every prayer file this project writes, both units.
PRAYERS = (AMIDAH_PRAYERS + YELADIM_PRAYERS + TALLITH_PRAYERS
           + TEFILLIN_PRAYERS + POEM_PRAYERS + BERAKHOT_PRAYERS
           + AKEDAH_PRAYERS + KORBANOT_PRAYERS + ISHMAEL_PRAYERS + PESUKEI_PRAYERS + SHEMA_PRAYERS + AVINU_PRAYERS + TACHANUN_PRAYERS + TORAH_PRAYERS)
from .conclusion import prayers as conclusion_prayers
PRAYERS += conclusion_prayers("he", PRAYERS)
from .shacharit_end import prayers as final_prayers
PRAYERS += final_prayers("he")
from .minchah import shared as minchah_shared, prayers as minchah_prayers
PRAYERS = minchah_shared("he", PRAYERS) + minchah_prayers("he")
from .arvit import shared as arvit_shared, prayers as arvit_prayers
PRAYERS = arvit_shared("he", PRAYERS)
PRAYERS += arvit_prayers("he", PRAYERS)
from .shabbat_opening import shared as shabbat_shared, prayers as shabbat_prayers
PRAYERS = shabbat_shared("he", PRAYERS) + shabbat_prayers("he")
from .kabbalat_shabbat import shared as kabbalat_shared, prayers as kabbalat_prayers
PRAYERS = kabbalat_shared("he", PRAYERS) + kabbalat_prayers("he")
from .bameh_madlikin import shared as bameh_shared, prayers as bameh_prayers
PRAYERS = bameh_shared("he", PRAYERS) + bameh_prayers("he")
from .shabbat_arvit import shared as shabbat_arvit_shared, prayers as shabbat_arvit_prayers
PRAYERS = shabbat_arvit_shared("he", PRAYERS)
PRAYERS += shabbat_arvit_prayers("he", PRAYERS)
from .leil_shabbat import shared as leil_shabbat_shared, prayers as leil_shabbat_prayers
PRAYERS = leil_shabbat_shared("he", PRAYERS)
PRAYERS += leil_shabbat_prayers("he", PRAYERS)
from .shabbat_pesukei import shared as shabbat_pesukei_shared, prayers as shabbat_pesukei_prayers
PRAYERS = shabbat_pesukei_shared("he", PRAYERS)
PRAYERS += shabbat_pesukei_prayers("he")
from .shabbat_shema import shared as shabbat_shema_shared, prayers as shabbat_shema_prayers
PRAYERS = shabbat_shema_shared("he", PRAYERS)
PRAYERS += shabbat_shema_prayers("he")
from .shabbat_amidah import shared as shabbat_amidah_shared, prayers as shabbat_amidah_prayers
PRAYERS = shabbat_amidah_shared("he", PRAYERS)
PRAYERS += shabbat_amidah_prayers("he", PRAYERS)
from .shabbat_torah import shared as shabbat_torah_shared, prayers as shabbat_torah_prayers
PRAYERS = shabbat_torah_shared("he", PRAYERS)
PRAYERS += shabbat_torah_prayers("he", PRAYERS)
from .shabbat_musaf import shared as musaf_shared, prayers as musaf_prayers
PRAYERS = musaf_shared("he", PRAYERS)
PRAYERS += musaf_prayers("he", PRAYERS)
from .shabbat_day_meal import shared as day_meal_shared, prayers as day_meal_prayers
PRAYERS = day_meal_shared("he", PRAYERS)
PRAYERS += day_meal_prayers("he", PRAYERS)
from .shabbat_minchah import shared as shabbat_minchah_shared, prayers as shabbat_minchah_prayers
PRAYERS = shabbat_minchah_shared("he", PRAYERS)
PRAYERS += shabbat_minchah_prayers("he", PRAYERS)
from .avot import prayers as avot_prayers
PRAYERS += avot_prayers("he")
from .motzaei_shabbat import prayers as motzaei_prayers, shared as motzaei_shared
PRAYERS = motzaei_shared("he", PRAYERS)
PRAYERS += motzaei_prayers("he", PRAYERS)
from .hallel import shared as hallel_shared, prayers as hallel_prayers
PRAYERS = hallel_shared("he", PRAYERS)
PRAYERS += hallel_prayers("he")
from .rosh_hodesh_musaf import prayers as rc_musaf_prayers, shared as rc_musaf_shared
PRAYERS = rc_musaf_shared("he", PRAYERS)
PRAYERS += rc_musaf_prayers("he")
from .festival import prayers as festival_prayers, shared as festival_shared
PRAYERS = festival_shared("he", PRAYERS)
PRAYERS += festival_prayers("he")
from .yizkor import prayers as yizkor_prayers
PRAYERS += yizkor_prayers("he")
from .festival_musaf import prayers as festival_musaf_prayers, shared as festival_musaf_shared
PRAYERS = festival_musaf_shared("he", PRAYERS)
PRAYERS += festival_musaf_prayers("he")
from .omer_akdamut import prayers as omer_akdamut_prayers
PRAYERS += omer_akdamut_prayers("he")
from .rosh_hashanah import prayers as rosh_hashanah_prayers
PRAYERS += rosh_hashanah_prayers("he")
from .sukkot_rites import prayers as sukkot_rites_prayers
PRAYERS += sukkot_rites_prayers("he")
from .hanukkah_purim import prayers as hanukkah_purim_prayers, shared as hanukkah_purim_shared
PRAYERS = hanukkah_purim_shared("he", PRAYERS)
PRAYERS += hanukkah_purim_prayers("he")
from .lifecycle import prayers as lifecycle_prayers, shared as lifecycle_shared
PRAYERS = lifecycle_shared("he", PRAYERS)
PRAYERS += lifecycle_prayers("he")
from .concluding_prayers import prayers as concluding_prayers, shared as concluding_shared
PRAYERS = concluding_shared("he", PRAYERS)
PRAYERS += concluding_prayers("he")


U, S = PRAYER, SIDDUR

# The unit declares its service and that it is a weekday, and declares EVERY service --
# an undeclared false is undefined, and undefined keeps the text, so declaring shaharit
# alone would leave every other service's readings standing. It declares NOTHING about
# the date, so the rain seasons, the Ten Days, Ya'aleh v'Yavo and עננו stay open.
def declaration(service="shaharit"):
    svc = "\n".join(
        f'          <tei:f name="{n}">\n            <tei:binary value="{"true" if n==service else "false"}"/>\n          </tei:f>'
        for n in ("shaharit", "minha", "maariv", "musaf", "neila", "slihot"))
    agg = "\n".join(
        f'          <tei:f name="{n}">\n            <tei:binary value="false"/>\n          </tei:f>'
        for n in ("shabbat", "yom-tov"))
    return (f'        <j:declare xml:id="unit_service">\n'
            f'          <tei:fs type="{SERVICE}">\n{svc}\n          </tei:fs>\n'
            f'          <tei:fs type="{AGG}">\n{agg}\n          </tei:fs>\n'
            f'        </j:declare>')


# Shaḥarith li-Yladim is not the weekday Amidah's kind of unit: a child says it every
# morning, festivals and Sabbaths included, so it declares the service and says NOTHING
# about the date or the holiday aggregates. The Amidah declares those false because it is
# specifically the weekday Amidah; repeating that here would file this page under weekdays.
# There is no j:conditional anywhere in the unit -- nothing on the page depends on season,
# occasion, service or minyan -- so the declaration governs no conditional text. It is kept
# as the unit's standing claim about when it is said, for whatever later transcludes it.
def declaration_yeladim():
    svc = "\n".join(
        f'          <tei:f name="{n}">\n            <tei:binary value="{"true" if n=="shaharit" else "false"}"/>\n          </tei:f>'
        for n in ("shaharit", "minha", "maariv", "musaf", "neila", "slihot"))
    return (f'        <j:declare xml:id="unit_service">\n'
            f'          <tei:fs type="{SERVICE}">\n{svc}\n          </tei:fs>\n'
            f'        </j:declare>')


# Birkhoth ha-Shaḥar is said every morning, Sabbaths and festivals included -- the print
# says so twice on its own pages: `On Sabbath say:` stands inside the section, and it ends
# `On Sabbaths and on major festivals the service is continued on page 299.` So it declares
# the service and **nothing about the day**, exactly as Shaḥarith li-Yladim does.
#
# It used to share the Amidah's `declaration()`, which declares `shabbat: false` because
# that unit is specifically the weekday Amidah. The effect was that the Sabbath musaf
# passage was resolved away in *every* compile, including the undecided one -- a conditional
# that could never be true, in a unit whose own rubric says when to say it. The compile is
# what surfaced it; nothing else in the pass could.
def declaration_birchot():
    return declaration_yeladim()


#: The rubrics of printed page 1, in the order the page sets them, each naming the
#: prayers it governs. Birnbaum sets them in ENGLISH on the Hebrew page as well as on the
#: English one, so both projects emit them identically -- the same practice as the Amidah.
#: "When dressed:" governs two prayers, which is why this is a table and not a field on
#: each prayer.
YELADIM_RUBRICS = (
    ("Upon awakening in the morning:", ["yeladim_modeh_ani"]),
    ("When washing the hands:", ["yeladim_netilat_yadayim"]),
    ("When putting on the <tei:foreign xml:lang=\"he-Latn\">arba kanfoth</tei:foreign>:",
     ["yeladim_tzitzit"]),
    ("When dressed:", ["yeladim_torah_tzivvah", "yeladim_elohai_netzor"]),
)


def unit_body_yeladim(head, by_name):
    """The children's unit.

    `head` differs between the projects -- see YELADIM_HEAD -- and `by_name` is the
    calling project's own prayer table, since each project transcludes its own files.
    """
    lines = [f'      <tei:div corresp="{S}all/shacharit/yeladim">', declaration_yeladim(), head]
    for note, names in YELADIM_RUBRICS:
        lines.append(f'        <tei:note type="instruction" xml:lang="en">{note}</tei:note>')
        for name in names:
            lines.append(f'        <j:transclude type="external" target="{by_name[name]["urn"]}"/>')
    lines.append('        <j:endDeclare target="#unit_service"/>')
    lines.append("      </tei:div>")
    return "\n".join(lines)


#: The rubrics of printed pages 3 and 5, in the order the pages set them. English on the
#: Hebrew page as well as the English one, as everywhere in this book, so both projects
#: emit them identically. `tallith` is marked foreign in both: the Hebrew page sets it
#: italic against a roman rubric and the English page sets it inside an already-italic
#: one, which is the same intent realised twice and belongs to typography, not to the URN.
TALLITH = '<tei:foreign xml:lang="he-Latn">tallith</tei:foreign>'
BIRCHOT_RUBRICS = (
    ("Upon entering the synagogue:", ["birkhot_mah_tovu"]),
    (f"Before putting on the {TALLITH}:",
     ["tallith_barkhi_nafshi", "tallith_hineni_mitattef"]),
    (f"When putting on the {TALLITH}:", ["tallith_lehitattef"]),
)

#: The tefillin order's heading and rubrics, printed pages 5-11 against 6-12. Barukh Shem
#: is transcluded from the children's unit rather than re-emitted: the same words wherever
#: the book prints them, and refdb refuses a text URN mapped twice in one project.
TEFILLIN_HEAD = {
    PROJECT_HE: '        <tei:head xml:lang="he">סֵֽדֶר הַנָּחַת תְּפִלִּין</tei:head>',
    PROJECT_EN: '        <tei:head xml:lang="en">PUTTING ON THE TEFILLIN</tei:head>',
}
#: The Shema verse and Barukh Shem are `tei:seg`s inside the children's `torah_tzivvah`
#: rather than files of their own, so they are reached by URN and not by prayer name. They
#: are the same words wherever the book prints them, which is the whole point of giving
#: them canonical URNs there.
SHEMA_PASUK = PRAYER + "shema/shema_yisrael"
SHEMA_BARUKH_SHEM = PRAYER + "shema/barukh_shem"

TEFILLIN_RUBRICS = (
    ("Meditation before putting on the tefillin", ["tefillin_hineni_mekhavven"]),
    ("When placing the tefillin on the left arm:", ["tefillin_lehanniach"]),
    ("When placing the tefillin on the forehead:", ["tefillin_al_mitzvat"]),
    # Printed 7 sets Barukh Shem here, between the two blessings. It is realised on the
    # children's page, so the unit reaches it by URN -- which `he_tefillin`'s docstring has
    # said all along and the unit did not in fact do.
    ("", [SHEMA_BARUKH_SHEM]),
    ("", ["tefillin_umechokhmatekha"]),
    ("When winding the retsuah three times round the middle finger:",
     ["tefillin_verastikh"]),
    ("", ["tefillin_yehi_ratzon"]),
    # Printed 9 sets the parashiyoth under their citation; printed 10 sets the same
    # citation centred, and gives the four sections again as a numbered footnote.
    ("", [("citation", "שמות יג, א–טז", "Exodus 13:1–16"), "tefillin_parashiyot"]),
)

#: The source citation over Psalm 36:8–11, which the two sides punctuate differently: the
#: Hebrew page separates chapter from verse with a comma and the English page with a
#: colon. Both are his, and the separator belongs to the language the citation is set in.
#:
#: **The range takes an en dash on both sides.** Checked at 8x on printed 6; the reading
#: says so too. The hyphen that stood here until now came from the English Wikisource
#: transcription, which sets a hyphen in every range on every page of this book -- a
#: systematic departure, and one `reverse` cannot see because it checks the Hebrew side.
BIRCHOT_CITATION = {
    PROJECT_HE: '        <tei:head xml:lang="he">תהלים לו, ח–יא</tei:head>',
    PROJECT_EN: '        <tei:head xml:lang="en">Psalm 36:8–11</tei:head>',
}

#: Hebrew on the Hebrew page, English on the English one -- as the children's unit heads
#: are, and unlike the Amidah, which heads both sides in English.
BIRCHOT_HEAD = {
    PROJECT_HE: '        <tei:head xml:lang="he">בִּרְכוֹת הַשַּֽׁחַר</tei:head>',
    PROJECT_EN: '        <tei:head xml:lang="en">PRELIMINARY MORNING SERVICE</tei:head>',
}

#: The tallith order's own heading, under the section heading.
TALLITH_HEAD = {
    PROJECT_HE: '        <tei:head xml:lang="he">סֵֽדֶר עֲטִיפַת טַלִּית</tei:head>',
    PROJECT_EN: '        <tei:head xml:lang="en">PUTTING ON THE TALLITH</tei:head>',
}


#: The poems are headed on the English page and not on the Hebrew one -- the sharpest
#: asymmetry in this unit. An empty string on the Hebrew side is the encoding saying so.
POEM_HEADS = {
    PROJECT_HE: ("", ""),
    PROJECT_EN: ('        <tei:head xml:lang="en">ADON OLAM</tei:head>',
                 '        <tei:head xml:lang="en">YIGDAL</tei:head>'),
}


GENDERED = (
    ("cond_blessing_men", "Men say:", "male", "birkhot_shelo_asani_ishah"),
    ("cond_blessing_women", "Women say:", "female", "birkhot_sheasani_kirtzono"),
)

#: Printed 13 sets the washing blessing word for word as printed 1 does. The children's
#: unit realises it, so this transcludes -- refdb refuses a text URN mapped twice in one
#: project. Which unit ought to realise it is for when the whole book is read; the
#: children's page is certainly not its home.
SHARED_WITH_YELADIM = ("yeladim_netilat_yadayim",)

TORAH_BLESSINGS = ("asher_yatzar", "birkhot_hatorah_laasoq", "birkhot_hatorah_vehaarev",
                   "birkhot_hatorah_asher_bachar", "birkat_kohanim", "ellu_devarim",
                   "elohai_neshamah")


def _citation(lines, project, he, en):
    """A source citation, centred over the passage it introduces.

    The print sets one on both pages, each in its own language's convention: the Hebrew
    side parts chapter from verse with a **comma** and the English side with a **colon**,
    and a range takes an **en dash** on both. Where a citation names more than one place,
    a semicolon parts them.
    """
    lines.append('        <tei:head xml:lang="%s">%s</tei:head>'
                 % (("he", he) if project == PROJECT_HE else ("en", en)))


def _transclude(lines, by_name, name):
    """Transclude by prayer name, or -- when the name is already a URN -- by URN.

    A URN is how a text realised as a `tei:seg` inside another file is reached: it has no
    file of its own, and `refdb` resolves a URN to wherever it is declared.
    """
    urn = name if name.startswith("urn:") else by_name[name]["urn"]
    lines.append(f'        <j:transclude type="external" target="{urn}"/>')


#: The citations printed over the Torah blessings and the three texts that follow them,
#: each keyed to the prayer it introduces. Printed 13 sets one between the poems and the
#: blessings; printed 15 sets three, more than any other page of the unit.
BLESSING_CITATIONS = {
    "yeladim_netilat_yadayim": ("מסכת ברכות יא, א; ס, ב", "Talmud Berakhoth 11a; 60b"),
    "birkat_kohanim": ("במדבר ו, כד–כו", "Numbers 6:24–26"),
    "ellu_devarim": ("פאה א, משנה א; מסכת שבת קכז, א",
                    "Mishnah Peah 1:1; Talmud Shabbath 127a"),
    "elohai_neshamah": ("מסכת ברכות ס, ב", "Talmud Berakhoth 60b"),
}


def _birkhot_blessings(lines, project, by_name):
    """Printed 13-19: the Torah blessings, then the morning blessings in page order."""
    for name in SHARED_WITH_YELADIM + TORAH_BLESSINGS:
        if name in BLESSING_CITATIONS:
            _citation(lines, project, *BLESSING_CITATIONS[name])
        _transclude(lines, by_name, name)
    gendered = {n for _, _, _, n in GENDERED}
    for slug, _words, _page in BLESSINGS:
        name = f"birkhot_{slug}"
        if name in gendered:
            continue
        _transclude(lines, by_name, name)
        if slug == "shelo_asani_aved":
            for cid, note, value, gname in GENDERED:
                lines.append(cond(cid, note=note,
                                  fs=feature(PERSON, "gender",
                                             f'<tei:symbol value="{value}"/>')))
                _transclude(lines, by_name, gname)
                lines.append(endcond(cid))
    for name in ("birkhot_shetargilenu", "birkhot_gomel_chasadim",
                 "birkhot_shetatzileni", "birkhot_zokhrenu"):
        _transclude(lines, by_name, name)


#: Printed 19 to 25, from the Akedah to the end of the Atah Hu passages.
#:
#: The two `Reader` labels on printed 25 are what make `lefikhakh/ashreinu` and
#: `attah_hu/uvishuatekha` texts of their own: a label cannot stand inside a `tei:p`, and a
#: passage that must start level with its translation needs a URN. The English page runs
#: straight on and is parted at the same two points so the columns join URN for URN.
AKEDAH_ORDER = (
    ("citation", "בראשית כב, א–יט", "Genesis 22:1\u201319"),
    "aqedah",
    "aqedah_ribbono",
    "leolam_yehe_adam",
    "ribbon_kol_haolamim",
    "aval_anachnu",
    "lefikhakh",
    ("reader", "ashreinu"),
    ("transclude", SHEMA_PASUK),
    ("transclude", SHEMA_BARUKH_SHEM),
    "attah_hu_ad",
    ("reader", "attah_hu_uvishuatekha"),
    "attah_hu_bashamayim",
)

#: Printed 27 to 41. Every scriptural passage is printed under a citation, set in the
#: Hebrew column in small unpointed type and on the English page as a centred italic line;
#: chapter and verse take a comma there and a colon here, and a range takes an en dash in
#: both. A citation naming two places parts them with a semicolon.
KORBANOT_ORDER = (
    ("citation", "שמות ל, יז–כא", "Exodus 30:17\u201321"),
    "qorbanot_kiyyor",
    "qorbanot_yehi_ratzon_miqdash",
    ("citation", "במדבר כח, א–ח", "Numbers 28:1\u20138"),
    "qorbanot_tamid",
    ("citation", "ויקרא א, יא", "Leviticus 1:11"),
    "qorbanot_ushchat",
    "qorbanot_yehi_ratzon_amirah",
    "qorbanot_attah_hu",
    ("citation", "שמות ל, לד–לו; ל ז–ח", "Exodus 30:34\u201336; 30:7\u20138"),
    "qorbanot_qetoret",
    ("citation", "תלמוד בבלי, כריתות ו, א; תלמוד ירושלמי, יומא ד, ה",
     "Babylonian Talmud, Kerithoth 6a; Palestinian Talmud, Yoma 4:5"),
    "qorbanot_pittum",
    "qorbanot_rashbag",
    "qorbanot_rabbi_natan",
    "qorbanot_bar_kappara",
    "qorbanot_pesuqim",
    "qorbanot_attah_seter",
    "qorbanot_vearvah",
    ("citation", "מסכת יומא לג, א", "Talmud Yoma 33a"),
    "qorbanot_abaye",
    "poem_anna_bekhoach",
    ("transclude", SHEMA_BARUKH_SHEM),
    "qorbanot_ribbon_haolamim",
    ("conditional", "cond_musaf_shabbat", "On Sabbath say:",
     feature(AGG, "shabbat"),
     "במדבר כח, ט–י", "Numbers 28:9\u201310", "qorbanot_musaf_shabbat"),
    ("conditional", "cond_musaf_rosh_chodesh", "On Rosh \u1e24odesh say:",
     feature(HOL, "rosh-hodesh", '<tei:numeric value="1" max="2"/>'),
     "במדבר כח, יא–טו", "Numbers 28:11\u201315", "qorbanot_musaf_rosh_chodesh"),
    ("citation", "משנה זבחים, פרק ה", "Mishnah Zebaḥim, Chapter 5"),
) + tuple(f"eizehu_meqoman_{n}" for n in range(1, 9))

#: Printed 41 to 47. The English page carries a heading this one does not, which is the
#: sharpest asymmetry in the section and is why `head` here is a per-project value.
ISHMAEL_ORDER = (
    ("head", None, "TALMUDIC EXPOSITION OF THE SCRIPTURES"),
    ("citation", "ספרא, פתיחה", "Sifra, Introduction"),
    "ishmael_lead",
) + tuple(f"middot_{n}" for n in range(1, 14)) + (
    ("citation", "אבות ה, כג; מלאכי ג, ד", "Mishnah Avoth 5:23; Malachi 3:4"),
    "ishmael_yehi_ratzon",
    ("start-conditional", "morning_study_kaddish", "When a minyan holds service:",
     feature("opensiddur:quorum", "minyan")),
    ("head", "קַדִּישׁ דְּרַבָּנָן", "KADDISH D\u2019RABBANAN"),
    ("mourners", None),
    "kaddish_derabbanan_yitgaddal",
    "kaddish_derabbanan_yehe_shemeh",
    "kaddish_derabbanan_yitbarakh",
    "kaddish_derabbanan_al_yisrael",
    "kaddish_derabbanan_yehe_shelama",
    "kaddish_derabbanan_oseh_shalom",
    ("end-conditional", "morning_study_kaddish"),
    ("closing", None),
)

#: The last line of the section, and the one place the two sides say different words: each
#: names its own half of the target opening. Set as printed, and not linked -- page 299 is
#: outside what these projects hold.
CLOSING_RUBRIC = {
    PROJECT_HE: "On Sabbaths and on major festivals the service is continued on page 299.",
    PROJECT_EN: "On Sabbaths and on major festivals the service is continued on page 300.",
}


def _emit(lines, project, by_name, order):
    """One ordered run of the unit: texts, citations, headings and conditionals."""
    for item in order:
        if isinstance(item, str):
            _transclude(lines, by_name, item)
            continue
        kind = item[0]
        if kind == "citation":
            _he, _en = item[1], item[2]
            lines.append('        <tei:head xml:lang="%s">%s</tei:head>'
                         % (("he", _he) if project == PROJECT_HE else ("en", _en)))
        elif kind == "head":
            _he, _en = item[1], item[2]
            if project == PROJECT_HE and _he is None:
                continue        # printed 42 heads the section and printed 41 does not
            lines.append('        <tei:head xml:lang="%s">%s</tei:head>'
                         % (("he", _he) if project == PROJECT_HE else ("en", _en)))
        elif kind == "transclude":
            _transclude(lines, by_name, item[1])
        elif kind == "reader":
            lines.append('        <tei:note type="instruction" xml:lang="en">Reader</tei:note>')
            _transclude(lines, by_name, item[1])
        elif kind == "mourners":
            lines.append('        <tei:note type="instruction" xml:lang="en">Mourners:</tei:note>')
        elif kind == "closing":
            lines.append('        <tei:note type="instruction" xml:lang="en">%s</tei:note>'
                         % CLOSING_RUBRIC[project])
        elif kind == "conditional":
            cid, note, fs, he_cit, en_cit, name = item[1:]
            lines.append(cond(cid, note=note, fs=fs))
            lines.append('        <tei:head xml:lang="%s">%s</tei:head>'
                         % (("he", he_cit) if project == PROJECT_HE else ("en", en_cit)))
            _transclude(lines, by_name, name)
            lines.append(endcond(cid))
        elif kind == "start-conditional":
            lines.append(cond(item[1], note=item[2], fs=item[3],
                              note_resp='urn:x-opensiddur:contributor:opensiddur.org/efraim-feinstein'))
        elif kind == "end-conditional":
            lines.append(endcond(item[1]))
        else:
            raise ValueError(f"unknown unit item {item!r}")


def unit_body_birchot(project, by_name):
    """Birkhoth ha-Shaḥar entire: printed 3 to 47 on the Hebrew side, 4 to 48 on the
    English one."""
    lines = [f'      <tei:div corresp="{S}all/shacharit/birkhot_hashachar">',
             declaration_birchot(), BIRCHOT_HEAD[project]]
    for n, (note, names) in enumerate(BIRCHOT_RUBRICS):
        if n == 1:                      # the tallith order opens with its own heading
            lines.append(TALLITH_HEAD[project])
        lines.append(f'        <tei:note type="instruction" xml:lang="en">{note}</tei:note>')
        for name in names:
            _transclude(lines, by_name, name)
    lines.append(BIRCHOT_CITATION[project])
    for name in ("tallith_mah_yaqar", "tallith_yehi_ratzon"):
        _transclude(lines, by_name, name)
    tefillin = ('<j:all><j:none>'+feature(AGG, 'shabbat')+feature(AGG, 'yom-tov')
                +feature(HOL, 'tisha-bav', '<tei:numeric value="1"/>')+'</j:none><j:any>'
                +'<j:none>'+feature(AGG, 'chol-hamoed')+'</j:none>'
                +feature('opensiddur:practice', 'tefillin-on-chol-hamoed')+'</j:any></j:all>')
    lines.append(cond('morning_tefillin', fs=tefillin,
        note='On weekdays, except Shabbat, Yom Tov and Tish‘ah b’Av morning; on Ḥol ha-Mo‘ed, according to the custom of wearing tefillin:',
        note_resp='urn:x-opensiddur:contributor:opensiddur.org/efraim-feinstein'))
    lines.append(TEFILLIN_HEAD[project])
    for note, names in TEFILLIN_RUBRICS:
        if note:
            lines.append(f'        <tei:note type="instruction" xml:lang="en">{note}</tei:note>')
        for name in names:
            if isinstance(name, tuple):
                _citation(lines, project, name[1], name[2])
            else:
                _transclude(lines, by_name, name)
    lines.append(endcond('morning_tefillin'))
    adon, yigdal = POEM_HEADS[project]
    for head, name in ((adon, "poem_adon_olam"), (yigdal, "poem_yigdal")):
        if head:
            lines.append(head)
        _transclude(lines, by_name, name)
    _birkhot_blessings(lines, project, by_name)
    for order in (AKEDAH_ORDER, KORBANOT_ORDER, ISHMAEL_ORDER):
        _emit(lines, project, by_name, order)
    lines.append('        <j:endDeclare target="#unit_service"/>')
    lines.append("      </tei:div>")
    return "\n".join(lines)


def unit_body_opening(project, by_name):
    """Psalm 30 and Mourners’ Kaddish precede Pesukei dezimrah."""
    he = project == PROJECT_HE
    lines = [f'<tei:div corresp="{S}chol/shacharit/opening">', declaration(),
             '<tei:head xml:lang="he">תְּפִלַּת שַׁחֲרִית</tei:head>' if he else
             '<tei:head xml:lang="en">MORNING SERVICE</tei:head>']
    _transclude(lines, by_name, "mizmor_shir_chanukat_habayit")
    lines.append('<tei:head xml:lang="en">MOURNERS’ KADDISH</tei:head>')
    _transclude(lines, by_name, "kaddish_yatom")
    lines += ['<j:endDeclare target="#unit_service"/>', '</tei:div>']
    return "\n".join(lines)


def todah_condition():
    """The three omissions printed on 55–56; Hebrew months use Nisan=1."""
    def date(month, day):
        return (f'<tei:fs type="opensiddur:hebrew-date">'
                f'<tei:f name="month"><tei:numeric value="{month}"/></tei:f>'
                f'<tei:f name="day"><tei:numeric value="{day}"/></tei:f></tei:fs>')
    return cond('cond_mizmor_letodah', negate=True,
                note=('The following psalm is omitted on '
                      '<tei:foreign xml:lang="he-Latn">Erev Yom Kippur</tei:foreign>, '
                      '<tei:foreign xml:lang="he-Latn">Erev Pesaḥ</tei:foreign> and '
                      '<tei:foreign xml:lang="he-Latn">Ḥol ha-Mo‘ed Pesaḥ</tei:foreign>.'),
                fs=date(7, 9) + date(1, 14) + '<j:all>' +
                feature(AGG, 'chol-hamoed') +
                feature(HOL, 'pesah', '<tei:numeric value="1" max="8"/>') + '</j:all>')


def unit_body_pesukei(project, by_name):
    """Hareni mezamen through the concluding Half Kaddish."""
    lines = [f'<tei:div corresp="{S}chol/shacharit/pesuqei_dezimrah">', declaration()]
    for name in ('hareini_mezammen', 'barukh_sheamar', 'hodu', 'romemu',
                 'vehu_rachum', 'hoshiah_et_ammekha'):
        _transclude(lines, by_name, name)
    lines.append(todah_condition())
    _transclude(lines, by_name, 'mizmor_letodah')
    lines.append(endcond('cond_mizmor_letodah'))
    _transclude(lines, by_name, 'yehi_khevod')
    from .pesukei_completion import ORDER
    for name in ORDER:
        _transclude(lines, by_name, name)
    lines += ['<j:endDeclare target="#unit_service"/>', '</tei:div>']
    return "\n".join(lines)


#: The book's running order: the children's page is printed first, and comes first here.
#: Each entry is what write() needs to put one unit file on disk. Both projects build
#: their units from this one function, so a unit cannot exist on one side only.
def units(project, pages, by_name, amidah_body):
    """`pages` maps a unit key to its (first, last) printed pages in THIS project.

    The two projects foliate differently -- the Hebrew is on 1 and 81-97, the English on
    2 and 82-98 -- which is the same thing the Amidah already does across an opening.
    """
    from .shema import unit_body as shema_body
    from .avinu_malkenu import unit_body as avinu_body
    from .tachanun import unit_body as tachanun_body, kaddish_body, torah_intro_body
    from .torah import unit_body as torah_body
    from .conclusion import unit_body as conclusion_body, psalms_body
    from .shacharit_end import service_body, unit_body as final_body, editorial_head
    side = 0 if project == PROJECT_HE else 1
    lang = "he" if side == 0 else "en"
    result = (
        dict(name="all_shacharit_yeladim",
             body=unit_body_yeladim(YELADIM_HEAD[project], by_name),
             title_he="שַׁחֲרִית לִילָדִים", title_en="Morning prayer for children",
             urn=f"{S}all/shacharit/yeladim", pages=pages["yeladim"]),
        dict(name="all_shacharit_birkhot_hashachar",
             body=unit_body_birchot(project, by_name),
             title_he="בִּרְכוֹת הַשַּֽׁחַר", title_en="Preliminary morning service",
             urn=f"{S}all/shacharit/birkhot_hashachar", pages=pages["birkhot"]),
        dict(name="chol_shacharit_opening",
             body=unit_body_opening(project, by_name),
             title_he="תְּפִלַּת שַׁחֲרִית", title_en="Morning service opening",
             urn=f"{S}chol/shacharit/opening", pages=pages["opening"]),
        dict(name="chol_shacharit_pesuqei_dezimrah",
             body=unit_body_pesukei(project, by_name),
             title_he="פְּסוּקֵי דְזִמְרָה", title_en="Verses of praise",
             urn=f"{S}chol/shacharit/pesuqei_dezimrah", pages=pages["pesuqei"]),
        dict(name="chol_shacharit_shema", body=shema_body(project, by_name),
             title_he="קְרִיאַת שְׁמַע וּבִרְכוֹתֶיהָ", title_en="Shema and its blessings",
             urn=f"{S}chol/shacharit/shema", pages=pages["shema"]),
        dict(name="chol_shacharit_amidah", body=amidah_body,
             title_he="תְּפִלַּת הָעֲמִידָה לְשַׁחֲרִית בְּחוֹל",
             title_en="The weekday morning Amidah",
             urn=f"{S}chol/shacharit/amidah", pages=pages["amidah"]),
        dict(name="chol_shacharit_avinu_malkenu", body=avinu_body(project, by_name),
             title_he="אָבִֽינוּ מַלְכֵּֽנוּ", title_en="Avinu Malkenu",
             urn=f"{S}chol/shacharit/avinu_malkenu", pages=pages["avinu"]),
        dict(name="chol_shacharit_tachanun", body=tachanun_body(project),
             title_he="תַּחֲנוּן", title_en="Tachanun",
             urn=f"{S}chol/shacharit/tachanun", pages=(103 + side, 117 + side)),
        dict(name="chol_shacharit_kaddish_after_tachanun", body=kaddish_body(project),
             title_he="חֲצִי קַדִּישׁ", title_en="Half Kaddish after Tachanun",
             urn=f"{S}chol/shacharit/kaddish_after_tachanun", pages=(117 + side, 117 + side)),
        dict(name="chol_shacharit_torah_intro", body=torah_intro_body(project),
             title_he="אֵל אֶֽרֶךְ אַפַּֽיִם", title_en="Introduction to the Torah service",
             urn=f"{S}chol/shacharit/torah_intro", pages=(117 + side, 117 + side)),
        dict(name="chol_shacharit_torah", body=torah_body(project),
             title_he="קְרִיאַת הַתּוֹרָה", title_en="Reading of the Torah",
             urn=f"{S}chol/shacharit/torah", pages=(119 + side, 127 + side)),
        dict(name="chol_shacharit_conclusion", body=conclusion_body(project),
             title_he="סיום תפילת שחרית", title_en="Conclusion of the morning service",
             urn=f"{S}chol/shacharit/conclusion", pages=(127 + side, 137 + side)),
        dict(name="chol_shacharit_psalms", body=psalms_body(project),
             title_he="מזמורים לימים ולמועדים", title_en="Psalms for days and occasions",
             urn=f"{S}chol/shacharit/psalms", pages=(139 + side, 151 + side)),
        dict(name="chol_shacharit_final_readings", body=final_body(lang),
             title_he="קריאות לסיום שחרית", title_en="Final readings",
             urn=f"{S}chol/shacharit/final_readings", pages=(151 + side, 155 + side)),
        dict(name="chol_shacharit", body=service_body(lang),
             title_he="תפילת שחרית ליום חול", title_en="Weekday Shacharit",
             urn=f"{S}chol/shacharit", pages=(3 + side, 155 + side)),
    )
    # Explicit editorial section headings supply navigation where the printed
    # book relies on placement. Prayer headings remain inside their sections.
    for unit in result:
        if unit['name'] in ('chol_shacharit_pesuqei_dezimrah', 'chol_shacharit_shema',
                            'chol_shacharit_conclusion', 'chol_shacharit_psalms'):
            start, rest = unit['body'].split('>', 1)
            unit['body'] = start + '>\n' + editorial_head(lang, unit['title_he'], unit['title_en']) + rest
    from .minchah import units as minchah_units
    from .arvit import units as arvit_units
    from .shabbat_opening import units as shabbat_units
    from .kabbalat_shabbat import units as kabbalat_units
    from .bameh_madlikin import units as bameh_units
    from .shabbat_arvit import units as shabbat_arvit_units
    from .leil_shabbat import units as leil_shabbat_units
    from .shabbat_pesukei import units as shabbat_pesukei_units
    from .shabbat_shema import units as shabbat_shema_units, extend_service
    from .shabbat_amidah import units as shabbat_amidah_units, extend_service as extend_amidah
    complete = extend_service(result + minchah_units(project, by_name) + arvit_units(project, by_name) + shabbat_units(project) + kabbalat_units(project) + bameh_units(project) + shabbat_arvit_units(project, by_name) + leil_shabbat_units(project) + shabbat_pesukei_units(project, by_name)) + shabbat_shema_units(project, by_name)
    from .shabbat_torah import units as torah_units, extend_service as extend_torah
    from .shabbat_musaf import units as musaf_units
    from .avot import units as avot_units
    from .rosh_hodesh_musaf import units as rc_musaf_units
    from .hallel import units as hallel_units
    from .motzaei_shabbat import units as motzaei_units
    from .shabbat_minchah import units as shabbat_minchah_units
    from .shabbat_day_meal import units as day_meal_units
    from .festival import units as festival_units, extend_services
    from .yizkor import units as yizkor_units, extend_services as extend_yizkor
    from .hanukkah_purim import units as hanukkah_purim_units
    from .lifecycle import units as lifecycle_units
    from .concluding_prayers import units as concluding_units
    from .sukkot_rites import units as sukkot_rites_units
    from .rosh_hashanah import units as rosh_hashanah_units
    from .omer_akdamut import units as omer_akdamut_units
    from .festival_musaf import units as festival_musaf_units
    return extend_yizkor(extend_services(extend_torah(extend_amidah(complete, lang) + shabbat_amidah_units(project, by_name), lang) + torah_units(project, by_name) + musaf_units(project, by_name) + day_meal_units(project) + shabbat_minchah_units(project, by_name) + avot_units(project) + motzaei_units(project, by_name) + hallel_units(project) + rc_musaf_units(project)) + festival_units(project) + yizkor_units(project)) + festival_musaf_units(project) + omer_akdamut_units(project) + rosh_hashanah_units(project) + sukkot_rites_units(project) + hanukkah_purim_units(project) + lifecycle_units(project) + concluding_units(project)


#: The one place the two projects' unit files genuinely differ. The Amidah's three
#: headings are English on both sides because that is what the print does; this unit's
#: heading is Hebrew on the Hebrew page and English on the English one.
YELADIM_HEAD = {
    PROJECT_HE: '        <tei:head xml:lang="he">שַׁחֲרִית לִילָדִים</tei:head>',
    PROJECT_EN: '        <tei:head xml:lang="en">MORNING PRAYER FOR CHILDREN</tei:head>',
}


ORDER = ["amidah_adonai_sefatai", "amidah_avot", "amidah_gevurot", "amidah_qedushah",
         "amidah_qedushat_hashem", "amidah_binah", "amidah_teshuvah", "amidah_selichah",
         "amidah_geullah", "amidah_refuah", "amidah_shanim", "amidah_qibbutz_galuyot",
         "amidah_mishpat", "amidah_minim", "amidah_tzaddiqim", "amidah_yerushalayim",
         "amidah_david", "amidah_tefillah", "amidah_avodah", "amidah_hodaah",
         "amidah_birkat_kohanim", "amidah_shalom", "amidah_elohai_netzor",
         "amidah_yehi_ratzon"]

BY_NAME = {p["name"]: p for p in PRAYERS}

#: Which printed pages each unit spans, on the Hebrew side of the opening.
HE_UNIT_PAGES = {"yeladim": (1, 1), "birkhot": (3, 47), "opening": (49, 51), "pesuqei": (51, 69), "shema": (71, 81), "amidah": (81, 97), "avinu": (97, 101)}


def unit_body():
    lines = [f'      <tei:div corresp="{S}chol/shacharit/amidah">', declaration()]
    lines.append('        <tei:head xml:lang="en">SHEMONEH ESREH</tei:head>')
    lines.append('        <tei:note type="instruction" xml:lang="en">The Shemoneh Esreh is recited in silent devotion while standing, facing east.</tei:note>')
    lines.append('        <tei:note type="instruction" xml:lang="en">The Reader repeats the Shemoneh Esreh aloud when a minyan holds service.</tei:note>')
    public = '<j:all>'+feature('opensiddur:recitation', 'repetition')+feature('opensiddur:quorum', 'minyan')+'</j:all>'
    gates = {'amidah_qedushah': ('weekday_qedushah', public),
             'amidah_qedushat_hashem': ('weekday_silent_qedushat_hashem', '<j:none>'+public+'</j:none>'),
             'amidah_birkat_kohanim': ('weekday_reader_birkat_kohanim', public)}
    for name in ORDER:
        if name == 'amidah_elohai_netzor':
            lines.append(cond('weekday_silent_meditation', fs='<j:none>'+public+'</j:none>'))
        if name in gates:
            cid, predicate = gates[name]
            lines.append(cond(cid, fs=predicate))
        if name == "amidah_qedushah":
            lines.append('        <tei:head xml:lang="en">KEDUSHAH</tei:head>')
        lines.append(f'        <j:transclude type="external" target="{BY_NAME[name]["urn"]}"/>')
        if name in gates:
            lines.append(endcond(gates[name][0]))
        if name == 'amidah_elohai_netzor':
            lines.append(endcond('weekday_silent_meditation'))
    # A cross-reference rubric: it names a page in this book and governs nothing here.
    lines.append('        <tei:note type="instruction" xml:lang="en">Hallel (page 565) is recited here on Rosh Ḥodesh, Ḥol ha-Mo‘ed and Ḥanukkah.</tei:note>')
    lines.append('        <tei:div>')
    lines.append('          <tei:head xml:lang="en">ABRIDGED SHEMONEH ESREH</tei:head>')
    lines.append('          <tei:note type="instruction" xml:lang="en">Used when one is unable to recite the complete Amidah</tei:note>')
    lines.append(f'          <j:transclude type="external" target="{BY_NAME["amidah_havinenu"]["urn"]}"/>')
    lines.append('        </tei:div>')
    lines.append('        <j:endDeclare target="#unit_service"/>')
    lines.append("      </tei:div>")
    return "\n".join(lines)


def main(argv=None):
    parsed = argparse.ArgumentParser(description=__doc__)
    parsed.add_argument(
        "--project-directory",
        help="Where to write the TEI. Defaults to the opensiddur-projects submodule; "
             "point it at a worktree to write there instead.",
    )
    args = parsed.parse_args(argv)
    if args.project_directory:
        set_project_directory(args.project_directory)
    written = []
    written.append(write(PROJECT_HE, "index", index(
        project=PROJECT_HE, lang="he", front=front_block(PROJECT_HE))))
    for unit in units(PROJECT_HE, HE_UNIT_PAGES, BY_NAME, unit_body()):
        written.append(write(PROJECT_HE, unit["name"], document(
            body=unit["body"], lang="he", title_he=unit["title_he"],
            title_en=unit["title_en"], urn=unit["urn"], project=PROJECT_HE,
            first=unit["pages"][0], last=unit["pages"][1])))
    for p in PRAYERS:
        written.append(write(PROJECT_HE, p["name"], document(
            body=p["body"], lang="he", title_he=p["title"], title_en="",
            urn=p["urn"], project=PROJECT_HE, first=p["first"], last=p["last"], printings=p.get("printings", ()))))
    print(f"{len(written)} files")
    for w in written:
        print(" ", w.name)


if __name__ == "__main__":
    sys.exit(main())
