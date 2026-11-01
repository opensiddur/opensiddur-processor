# -*- coding: utf-8 -*-
"""Write the English project. Same URNs as the Hebrew, which is what aligns them."""
import argparse
import sys
from .common import set_project_directory
from .common import PROJECT_EN, PRAYER, SIDDUR, FRONT, NOTES, document, standoff_document, write, cond, endcond, feature, SERVICE, AGG
from .front import SECTIONS, front_block, section_body
from .index import index
from .en_prayers import PRAYERS as AMIDAH_PRAYERS
from .en_yeladim import PRAYERS as YELADIM_PRAYERS
from .en_tallith import PRAYERS as TALLITH_PRAYERS
from .en_tefillin import PRAYERS as TEFILLIN_PRAYERS
from .en_poems import PRAYERS as POEM_PRAYERS
from .en_berakhot import PRAYERS as BERAKHOT_PRAYERS
from .en_akedah import PRAYERS as AKEDAH_PRAYERS
from .en_korbanot import PRAYERS as KORBANOT_PRAYERS
from .en_ishmael import PRAYERS as ISHMAEL_PRAYERS
from .en_pesukei import PRAYERS as PESUKEI_PRAYERS
from .shema import prayers as shema_prayers
SHEMA_PRAYERS = shema_prayers("en")
from .avinu_malkenu import prayers as avinu_prayers
AVINU_PRAYERS = avinu_prayers("en")
from .tachanun import prayers as tachanun_prayers
TACHANUN_PRAYERS = tachanun_prayers("en")
from .torah import prayers as torah_prayers
TORAH_PRAYERS = torah_prayers("en")
from . import build_he
from . import notes as apparatus
from .notes_pesukei import PESUKEI_NOTES
from .notes_shema import SHEMA_NOTES

#: Every prayer file this project writes, both units.
PRAYERS = (AMIDAH_PRAYERS + YELADIM_PRAYERS + TALLITH_PRAYERS
           + TEFILLIN_PRAYERS + POEM_PRAYERS + BERAKHOT_PRAYERS
           + AKEDAH_PRAYERS + KORBANOT_PRAYERS + ISHMAEL_PRAYERS + PESUKEI_PRAYERS + SHEMA_PRAYERS + AVINU_PRAYERS + TACHANUN_PRAYERS + TORAH_PRAYERS)
from .conclusion import prayers as conclusion_prayers
PRAYERS += conclusion_prayers("en", PRAYERS)
from .shacharit_end import prayers as final_prayers
PRAYERS += final_prayers("en")
from .minchah import shared as minchah_shared, prayers as minchah_prayers
PRAYERS = minchah_shared("en", PRAYERS) + minchah_prayers("en")
from .arvit import shared as arvit_shared, prayers as arvit_prayers
PRAYERS = arvit_shared("en", PRAYERS)
PRAYERS += arvit_prayers("en", PRAYERS)
from .shabbat_opening import shared as shabbat_shared, prayers as shabbat_prayers
PRAYERS = shabbat_shared("en", PRAYERS) + shabbat_prayers("en")
from .kabbalat_shabbat import shared as kabbalat_shared, prayers as kabbalat_prayers
PRAYERS = kabbalat_shared("en", PRAYERS) + kabbalat_prayers("en")
from .bameh_madlikin import shared as bameh_shared, prayers as bameh_prayers
PRAYERS = bameh_shared("en", PRAYERS) + bameh_prayers("en")
from .shabbat_arvit import shared as shabbat_arvit_shared, prayers as shabbat_arvit_prayers
PRAYERS = shabbat_arvit_shared("en", PRAYERS)
PRAYERS += shabbat_arvit_prayers("en", PRAYERS)
from .leil_shabbat import shared as leil_shabbat_shared, prayers as leil_shabbat_prayers
PRAYERS = leil_shabbat_shared("en", PRAYERS)
PRAYERS += leil_shabbat_prayers("en", PRAYERS)
from .shabbat_pesukei import shared as shabbat_pesukei_shared, prayers as shabbat_pesukei_prayers
PRAYERS = shabbat_pesukei_shared("en", PRAYERS)
PRAYERS += shabbat_pesukei_prayers("en")
from .shabbat_shema import shared as shabbat_shema_shared, prayers as shabbat_shema_prayers
PRAYERS = shabbat_shema_shared("en", PRAYERS)
PRAYERS += shabbat_shema_prayers("en")
from .shabbat_amidah import shared as shabbat_amidah_shared, prayers as shabbat_amidah_prayers
PRAYERS = shabbat_amidah_shared("en", PRAYERS)
PRAYERS += shabbat_amidah_prayers("en", PRAYERS)
from .shabbat_torah import shared as shabbat_torah_shared, prayers as shabbat_torah_prayers
PRAYERS = shabbat_torah_shared("en", PRAYERS)
PRAYERS += shabbat_torah_prayers("en", PRAYERS)
from .shabbat_musaf import shared as musaf_shared, prayers as musaf_prayers
PRAYERS = musaf_shared("en", PRAYERS)
PRAYERS += musaf_prayers("en", PRAYERS)
from .shabbat_day_meal import shared as day_meal_shared, prayers as day_meal_prayers
PRAYERS = day_meal_shared("en", PRAYERS)
PRAYERS += day_meal_prayers("en", PRAYERS)
from .shabbat_minchah import shared as shabbat_minchah_shared, prayers as shabbat_minchah_prayers
PRAYERS = shabbat_minchah_shared("en", PRAYERS)
PRAYERS += shabbat_minchah_prayers("en", PRAYERS)
from .avot import prayers as avot_prayers
PRAYERS += avot_prayers("en")
from .motzaei_shabbat import prayers as motzaei_prayers, shared as motzaei_shared
PRAYERS = motzaei_shared("en", PRAYERS)
PRAYERS += motzaei_prayers("en", PRAYERS)
from .hallel import shared as hallel_shared, prayers as hallel_prayers
PRAYERS = hallel_shared("en", PRAYERS)
PRAYERS += hallel_prayers("en")
from .rosh_hodesh_musaf import prayers as rc_musaf_prayers, shared as rc_musaf_shared
PRAYERS = rc_musaf_shared("en", PRAYERS)
PRAYERS += rc_musaf_prayers("en")
from .festival import prayers as festival_prayers, shared as festival_shared
PRAYERS = festival_shared("en", PRAYERS)
PRAYERS += festival_prayers("en")
from .yizkor import prayers as yizkor_prayers
PRAYERS += yizkor_prayers("en")
from .festival_musaf import prayers as festival_musaf_prayers, shared as festival_musaf_shared
PRAYERS = festival_musaf_shared("en", PRAYERS)
PRAYERS += festival_musaf_prayers("en")
from .omer_akdamut import prayers as omer_akdamut_prayers
PRAYERS += omer_akdamut_prayers("en")
from .rosh_hashanah import prayers as rosh_hashanah_prayers
PRAYERS += rosh_hashanah_prayers("en")
from .sukkot_rites import prayers as sukkot_rites_prayers
PRAYERS += sukkot_rites_prayers("en")
from .hanukkah_purim import prayers as hanukkah_purim_prayers, shared as hanukkah_purim_shared
PRAYERS = hanukkah_purim_shared("en", PRAYERS)
PRAYERS += hanukkah_purim_prayers("en")
from .lifecycle import prayers as lifecycle_prayers, shared as lifecycle_shared
PRAYERS = lifecycle_shared("en", PRAYERS)
PRAYERS += lifecycle_prayers("en")
from .concluding_prayers import prayers as concluding_prayers, shared as concluding_shared
PRAYERS = concluding_shared("en", PRAYERS)
PRAYERS += concluding_prayers("en")


U, S = PRAYER, SIDDUR

BY_NAME = {p["name"]: p for p in PRAYERS}

#: Which printed pages each unit spans, on the English side of the opening.
EN_UNIT_PAGES = {"yeladim": (2, 2), "birkhot": (4, 48), "opening": (50, 52), "pesuqei": (52, 70), "shema": (72, 82), "amidah": (82, 98), "avinu": (98, 102)}

#: Birnbaum's footnotes, one apparatus file per unit. They are written here and not in
#: `build_he` because the commentary is English prose, as his introduction is: the
#: English side realises it and the Hebrew reaches it by resolution. The pages named
#: are the pages the notes were read from, which for the commentary are the *Hebrew*
#: pages -- that is where the print sets it.
from .avinu_malkenu import NOTES as AVINU_NOTES

from .notes_tachanun import NOTES as TACHANUN_NOTES

from .notes_torah import NOTES as TORAH_NOTES

from .notes_conclusion import make_notes
from .conclusion import ANCHORS
CONCLUSION_NOTES = make_notes(ANCHORS)

from .shacharit_end import NOTES as FINAL_NOTES

from .notes_minchah import NOTES as MINCHAH_NOTES

from .notes_arvit import NOTES as ARVIT_NOTES

from .notes_shabbat_opening import NOTES as SHABBAT_OPENING_NOTES

from .notes_kabbalat_shabbat import NOTES as KABBALAT_NOTES

from .notes_bameh_madlikin import NOTES as BAMEH_NOTES

from .notes_shabbat_arvit import NOTES as SHABBAT_ARVIT_NOTES

from .notes_leil_shabbat import NOTES as LEIL_SHABBAT_NOTES

from .notes_shabbat_pesukei import NOTES as SHABBAT_PESUKEI_NOTES

from .notes_shabbat_shema import NOTES as SHABBAT_SHEMA_NOTES

from .notes_shabbat_amidah import NOTES as SHABBAT_AMIDAH_NOTES

from .notes_shabbat_torah import NOTES as SHABBAT_TORAH_NOTES

from .notes_shabbat_musaf import NOTES as MUSAF_NOTES

from .notes_shabbat_day_meal import NOTES as DAY_MEAL_NOTES

from .notes_shabbat_minchah import NOTES as SHABBAT_MINCHAH_NOTES

from .notes_avot import NOTES as AVOT_NOTES

from .notes_motzaei_shabbat import NOTES as MOTZAEI_NOTES

from .notes_hallel import NOTES as HALLEL_NOTES

from .notes_rosh_hodesh_musaf import NOTES as RC_MUSAF_NOTES
from .notes_festival import NOTES as FESTIVAL_NOTES

from .notes_yizkor import NOTES as YIZKOR_NOTES
from .notes_sukkot_rites import NOTES as SUKKOT_RITES_NOTES
from .notes_rosh_hashanah import NOTES as ROSH_HASHANAH_NOTES
from .notes_omer_akdamut import NOTES as OMER_AKDAMUT_NOTES
from .notes_festival_musaf import NOTES as FESTIVAL_MUSAF_NOTES

from .notes_hanukkah_purim import NOTES as HANUKKAH_PURIM_NOTES

from .notes_lifecycle import NOTES as LIFECYCLE_NOTES
from .notes_concluding_prayers import NOTES as CONCLUDING_NOTES

APPARATUS = {
    "notes_concluding_prayers": dict(entries=CONCLUDING_NOTES, slug="birnbaum_1949/concluding_prayers", title="Notes on marriage, meals, blessings, bedtime and Israel", first=753, last=790),
    "notes_lifecycle": dict(entries=LIFECYCLE_NOTES, slug="birnbaum_1949/lifecycle", title="Notes on journey, illness, burial, circumcision and redemption", first=731, last=752),
    "notes_chanukah_purim": dict(entries=HANUKKAH_PURIM_NOTES, slug="birnbaum_1949/chanukah_purim", title="Notes on Hanukkah, Megillat Hashmonaim and Purim", first=709, last=730),
    "notes_sukkot_rites": dict(entries=SUKKOT_RITES_NOTES, slug="birnbaum_1949/sukkot_rites", title="Notes on Sukkot rites", first=675, last=708),
    "notes_rosh_hashanah": dict(entries=ROSH_HASHANAH_NOTES, slug="birnbaum_1949/rosh_hashanah", title="Notes on Rosh Hashanah and Kapparot", first=655, last=674),
    "notes_omer_aqdamut": dict(entries=OMER_AKDAMUT_NOTES, slug="birnbaum_1949/omer_aqdamut", title="Notes on the Omer and Akdamut", first=637, last=654),
    "notes_festival_musaf": dict(entries=FESTIVAL_MUSAF_NOTES, slug="birnbaum_1949/festival_musaf", title="Notes on festival Musaf, priestly blessing, Kiddush and dew", first=609, last=636),
    "notes_yizkor": dict(entries=YIZKOR_NOTES, slug="birnbaum_1949/yizkor", title="Notes on the memorial service", first=601, last=608),
    "notes_festival": dict(entries=FESTIVAL_NOTES, slug="birnbaum_1949/regalim", title="Notes on the festival prayers", first=585, last=600),
    "notes_rosh_chodesh_musaf": dict(entries=RC_MUSAF_NOTES, slug="birnbaum_1949/rosh_chodesh_musaf", title="Notes on Musaf for Rosh Hodesh", first=575, last=584),
    "notes_hallel": dict(entries=HALLEL_NOTES, slug="birnbaum_1949/hallel", title="Notes on Hallel", first=565, last=574),
    "notes_motzaei_shabbat": dict(entries=MOTZAEI_NOTES, slug="birnbaum_1949/motzaei_shabbat", title="Notes on the conclusion of Sabbath and the moon blessing", first=535, last=566),
    "notes_avot": dict(entries=AVOT_NOTES, slug="birnbaum_1949/avot", title="Notes on Pirkei Avot", first=477, last=534),
    "notes_shabbat_minchah": dict(entries=SHABBAT_MINCHAH_NOTES, slug="birnbaum_1949/shabbat_minchah", title="Notes on Sabbath Mincha and winter Psalms", first=437, last=476),
    "notes_shabbat_day_meal": dict(entries=DAY_MEAL_NOTES, slug="birnbaum_1949/shabbat_day_meal", title="Notes on Sabbath morning Kiddush and hymns", first=424, last=436),
    "notes_shabbat_musaf": dict(entries=MUSAF_NOTES, slug="birnbaum_1949/shabbat_musaf", title="Notes on Sabbath Musaf", first=391, last=422),
    "notes_shabbat_torah": dict(entries=SHABBAT_TORAH_NOTES, slug="birnbaum_1949/shabbat_torah", title="Notes on Sabbath and festival Torah reading", first=361, last=390),
    "notes_shabbat_amidah": dict(entries=SHABBAT_AMIDAH_NOTES, slug="birnbaum_1949/shabbat_amidah", title="Notes on Sabbath morning Amidah", first=352, last=360),
    "notes_shabbat_shema": dict(entries=SHABBAT_SHEMA_NOTES, slug="birnbaum_1949/shabbat_shema", title="Notes on Sabbath and festival Shema blessings", first=337, last=340),
    "notes_shabbat_pesuqei": dict(entries=SHABBAT_PESUKEI_NOTES, slug="birnbaum_1949/shabbat_pesuqei",
        title="Notes on Sabbath and festival verses of praise", first=305, last=334),
    "notes_leil_shabbat": dict(entries=LEIL_SHABBAT_NOTES, slug="birnbaum_1949/leil_shabbat",
        title="Notes on the Friday-night home prayers and hymns", first=283, last=298),
    "notes_shabbat_arvit": dict(entries=SHABBAT_ARVIT_NOTES, slug="birnbaum_1949/shabbat_arvit",
        title="Notes on the Sabbath and festival evening service", first=262, last=280),
    "notes_bameh_madlikin": dict(entries=BAMEH_NOTES, slug="birnbaum_1949/bameh_madlikin",
        title="Notes on Bameh Madlikin", first=251, last=256),
    "notes_qabbalat_shabbat": dict(entries=KABBALAT_NOTES, slug="birnbaum_1949/qabbalat_shabbat",
        title="Notes on welcoming the Sabbath", first=237, last=250),
    "notes_shabbat_opening": dict(entries=SHABBAT_OPENING_NOTES, slug="birnbaum_1949/shabbat_opening",
                        title="Notes on candle lighting, parental blessing and Song of Songs", first=221, last=236),
    "notes_arvit": dict(entries=ARVIT_NOTES, slug="birnbaum_1949/arvit",
                        title="Notes on the evening service", first=189, last=220),
    "notes_minchah": dict(entries=MINCHAH_NOTES, slug="birnbaum_1949/minchah",
                          title="Notes on the afternoon service", first=157, last=188),
    "notes_shacharit_end": dict(entries=FINAL_NOTES, slug="birnbaum_1949/shacharit_end",
                               title="Notes on the final morning readings", first=151, last=156),
    "notes_conclusion": dict(entries=CONCLUSION_NOTES, slug="birnbaum_1949/conclusion",
                             title="Notes on the conclusion and psalms", first=128, last=152),
    "notes_torah": dict(entries=TORAH_NOTES, slug="birnbaum_1949/torah",
                        title="Notes on the weekday Torah service", first=119, last=128),
    "notes_tachanun": dict(entries=TACHANUN_NOTES, slug="birnbaum_1949/tachanun",
                           title="Notes on Tachanun", first=103, last=118),
    "notes_avinu_malkenu": dict(entries=AVINU_NOTES, slug="birnbaum_1949/avinu_malkenu",
                                title="Notes on Avinu Malkenu", first=98, last=100),
    "notes_shema": dict(entries=SHEMA_NOTES, slug="birnbaum_1949/shema",
                        title="Notes on Shema and its blessings", first=71, last=82),
    "notes_pesuqei": dict(entries=PESUKEI_NOTES, slug="birnbaum_1949/pesuqei_dezimrah",
                          title="Notes on the opening of the morning service", first=49, last=70),
    "notes_yeladim": dict(entries=apparatus.YELADIM_NOTES, slug="birnbaum_1949/yeladim",
                          title="Notes on Shaḥarith li-Yladim", first=1, last=1),
    "notes_birkhot": dict(entries=apparatus.BIRCHOT_NOTES,
                          slug="birnbaum_1949/birkhot_hashachar",
                          title="Notes on Birkhoth ha-Shaḥar", first=3, last=47),
    "notes_amidah": dict(entries=apparatus.AMIDAH_NOTES, slug="birnbaum_1949/amidah",
                         title="Notes on the weekday morning Amidah", first=81, last=98),
}


def unit_body():
    lines = [f'      <tei:div corresp="{S}chol/shacharit/amidah">', build_he.declaration()]
    lines.append('        <tei:head xml:lang="en">SHEMONEH ESREH</tei:head>')
    lines.append('        <tei:note type="instruction" xml:lang="en">The Shemoneh Esreh is recited in silent devotion while standing, facing east.</tei:note>')
    lines.append('        <tei:note type="instruction" xml:lang="en">The Reader repeats the Shemoneh Esreh aloud when a minyan holds service.</tei:note>')
    public = '<j:all>'+feature('opensiddur:recitation', 'repetition')+feature('opensiddur:quorum', 'minyan')+'</j:all>'
    gates = {'amidah_qedushah': ('weekday_qedushah', public),
             'amidah_qedushat_hashem': ('weekday_silent_qedushat_hashem', '<j:none>'+public+'</j:none>'),
             'amidah_birkat_kohanim': ('weekday_reader_birkat_kohanim', public)}
    for name in build_he.ORDER:
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
    lines.append('        <tei:note type="instruction" xml:lang="en">Hallel (page 566) is recited here on Rosh Ḥodesh, Ḥol ha-Mo‘ed and Ḥanukkah.</tei:note>')
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
    n = 0
    write(PROJECT_EN, "index", index(
        project=PROJECT_EN, lang="en", front=front_block(PROJECT_EN))); n += 1
    # The prose front matter is realised here and transcluded by both indexes:
    # Birnbaum wrote it in English and the print has no Hebrew counterpart.
    for s in SECTIONS:
        write(PROJECT_EN, s["name"], document(
            body=section_body(s), lang="en", title_he="", title_en=s["title"],
            urn=FRONT + s["slug"], project=PROJECT_EN,
            first=s["first"], last=s["last"])); n += 1
    for unit in build_he.units(PROJECT_EN, EN_UNIT_PAGES, BY_NAME, unit_body()):
        write(PROJECT_EN, unit["name"], document(
            body=unit["body"], lang="en", title_he=unit["title_he"],
            title_en=unit["title_en"], urn=unit["urn"], project=PROJECT_EN,
            first=unit["pages"][0], last=unit["pages"][1])); n += 1
    for name, a in APPARATUS.items():
        if not a["entries"]:
            continue
        write(PROJECT_EN, name, standoff_document(
            notes=apparatus.standoff(a["entries"]), lang="en", title_he="",
            title_en=a["title"], urn=NOTES + a["slug"], project=PROJECT_EN,
            first=a["first"], last=a["last"])); n += 1
    for p in PRAYERS:
        write(PROJECT_EN, p["name"], document(
            body=p["body"], lang="en", title_he="", title_en=p["title"],
            urn=p["urn"], project=PROJECT_EN, first=p["first"], last=p["last"], printings=p.get("printings", ()))); n += 1
    print(f"{n} files")


if __name__ == "__main__":
    sys.exit(main())
