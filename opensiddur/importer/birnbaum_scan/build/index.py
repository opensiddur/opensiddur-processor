# -*- coding: utf-8 -*-
"""The project index: the book's running order, and its front matter.

One function for both projects. The English index used to be derived from the Hebrew one
by byte-exact string replacement, which meant reflowing the Hebrew literal silently
changed the English file; the two now differ only in the arguments passed here.
"""
from opensiddur.importer.util.occasion import (
    DAY_OF_WEEK,
    HEBREW_DATE,
    ISRAEL,
    Feature,
    aggregate,
    all_of,
    any_of,
    gated,
    holiday,
    none_of,
    service,
)

from .avot import caller as avot_caller
from .common import PROJECT_EN, PROJECT_HE, SIDDUR

S = SIDDUR

#: What each project says it is. The English is Birnbaum's own translation, and that is
#: said here and in a note beside the citation -- not as a respStmt, which records who
#: *digitised* a text rather than who wrote the one being digitised.
EDITION = {
    PROJECT_HE: "Read directly from the scanned 1949 printing, page by page. "
                "Not derived from any transcription of it.",
    PROJECT_EN: "Birnbaum’s own English, read from the facing pages of the scanned "
                "1949 printing",
}
TRANSLATION_NOTE = ("The English of this project is Birnbaum’s own translation, printed "
                    "on the pages facing the Hebrew.")

#: The occasions the running order gates its sections on. Each is a condition on what the
#: calendar derives (schema/JLPTEI-3.md, *Conditions on a running order*); a section with none
#: is said on any day. The Hebrew day begins at nightfall, so a date with no time is the whole
#: Hebrew day, and Friday evening already belongs to the Sabbath.
SHABBAT = aggregate("shabbat")
YOM_TOV = aggregate("yom-tov")
#: The weekday services are also those of Rosh Hodesh, Hol ha-Moed, Hanukkah and Purim: "not
#: a Sabbath or a festival", not "an ordinary day".
WEEKDAY = none_of(SHABBAT, YOM_TOV)
#: Birnbaum's Sabbath Maariv, Shaharit and Minha are the festivals' too: they choose between
#: the two by conditions of their own, so they are gated on either and declare neither.
SHABBAT_OR_FESTIVAL = any_of(SHABBAT, YOM_TOV)
#: A festival day of the three pilgrimage festivals, Shemini Atzeret with them; the same
#: condition as the festival service's own (festival.py, REGALIM).
FESTIVAL = all_of(YOM_TOV, any_of(holiday("pesah", 1, 8), holiday("shavuot", 1, 2),
                                  holiday("sukkot", 1, 7), holiday("shmini-atzeret", 1, 2)))
#: Candle lighting and Kabbalat Shabbat come before nightfall, on the Hebrew Friday.
SHABBAT_EVENING = any_of(
    all_of(Feature(DAY_OF_WEEK, "hebrew-day", 6), service("minha")),
    all_of(SHABBAT, service("maariv")),
)
DAYTIME = none_of(service("maariv"))
IN_ISRAEL = Feature(ISRAEL, "is-israel", True)
IN_DIASPORA = Feature(ISRAEL, "is-israel", False)

#: The running order, in the order the book prints it, as (target, gate). Shaḥarith
#: li-Yladim is on pages 1-2 and so comes first. It is filed under the occasion `all` rather
#: than `chol`: a child says it every morning, Sabbaths and festivals included, and filing it
#: under weekdays would be a claim the book does not make. See SIDDUR_URN_SCHEME.md.
CHOL = (
    ("chol/shacharit", all_of(WEEKDAY, service("shaharit"))),
    ("chol/minchah", all_of(WEEKDAY, service("minha"))),
    ("chol/arvit", all_of(WEEKDAY, service("maariv"))),
)
SHABBAT_SECTIONS = (
    # The Hebrew Friday, which is also what an electronic book's reader sets as the day.
    ("shabbat/preparations", SHABBAT_EVENING),
    # Often said before nightfall, while it is still the Hebrew Friday.
    ("shabbat/qabbalat_service", SHABBAT_EVENING),
    ("shabbat/arvit", all_of(SHABBAT_OR_FESTIVAL, service("maariv"))),
    ("shabbat/leil_shabbat", all_of(SHABBAT, service("maariv"))),
    ("shabbat/shacharit", all_of(SHABBAT_OR_FESTIVAL, service("shaharit"))),
    # The Sabbath Musaf, and the prayers after Musaf on festivals and Hol ha-Moed too: the
    # festival Musaf ends with its Amidah, and this section chooses its own Amidah by
    # conditions on both. So it declares neither.
    ("shabbat/musaf", all_of(any_of(SHABBAT, YOM_TOV, aggregate("chol-hamoed")), DAYTIME)),
    ("shabbat/day_meal", all_of(SHABBAT, DAYTIME)),
)
#: Minha and the Pirkei Avot that follows it on summer Sabbath afternoons share one gate.
SHABBAT_MINCHAH = all_of(SHABBAT_OR_FESTIVAL, service("minha"))
#: Saturday night is a distinct occasion, tested before its local Sunday declaration.
SHABBAT_CONCLUSION = all_of(aggregate("motzaei-shabbat"), service("maariv"), none_of(YOM_TOV))
OCCASIONS = (
    # Birnbaum gives no window; the Ashkenazic custom is from the third day of the month to
    # the middle of it.
    ("berakhot/birkat_halevanah", Feature(HEBREW_DATE, "day", 3, 15)),
    ("hallel", all_of(service("shaharit"), any_of(holiday("rosh-hodesh", 1, 2), holiday("hanukkah", 1, 8),
        holiday("pesah", 1, 8), holiday("shavuot", 1, 2), holiday("sukkot", 1, 7), holiday("shmini-atzeret", 1, 2)))),
    ("rosh_chodesh/musaf", all_of(holiday("rosh-hodesh", 1, 2), DAYTIME)),
    # The festival service opens with the eruv tavshilin, made on the eve of the festival.
    ("regalim", any_of(FESTIVAL, aggregate("eruv-tavshilin"))),
    # The same days as yizkor.py's own OCCASION.
    ("yizkor", any_of(holiday("yom-kippur", 1), holiday("shmini-atzeret", 1),
                      all_of(IN_ISRAEL, any_of(holiday("pesah", 7), holiday("shavuot", 1))),
                      all_of(IN_DIASPORA, any_of(holiday("pesah", 8), holiday("shavuot", 2))))),
    # Musaf of Hol ha-Moed is the festival Musaf.
    ("regalim/musaf", all_of(any_of(FESTIVAL, aggregate("chol-hamoed")), DAYTIME)),
    ("regalim/morning_meal", all_of(FESTIVAL, DAYTIME)),
    ("sefirat_haomer", all_of(holiday("omer", 1, 49), service("maariv"))),
    ("regalim/aqdamut", holiday("shavuot", 1)),
    # Rosh Hashanah, and Kapparoth on the eve of Yom Kippur: the Ten Days.
    ("rosh_hashanah/minchah_maariv_and_rites", aggregate("aseret-ymei-tshuva")),
    ("sukkot/rites", any_of(holiday("sukkot", 1, 7), holiday("shmini-atzeret", 1, 2))),
    ("chanukah", holiday("hanukkah", 1, 8)),
    # On the day this community celebrates Purim: the 14th, or the 15th in a walled city.
    ("purim", holiday("purim-observed", 1)),
    # Not gated: the life-cycle services turn on opensiddur:override, which counts as false
    # when undefined, so a gate would take them out of every edition that names no occasion.
    ("lifecycle", None),
    ("concluding_prayers", None),
)


def _entry(target: str, condition, indent: int = 8) -> str:
    """One section of the running order, inside its occasion's gate."""
    pad = " " * indent
    xml_id = "occasion_" + target.replace("/", "_")
    return pad + gated(xml_id, condition,
                       f'\n{pad}<j:transclude type="external" target="{S}{target}"/>\n{pad}'
                       if condition is not None else
                       f'<j:transclude type="external" target="{S}{target}"/>')


def _entries(entries, indent: int) -> str:
    return "\n".join(_entry(target, condition, indent) for target, condition in entries)


BODY = f"""      <tei:div corresp="{S}siddur">
        <tei:div corresp="{S}all">
          <tei:div corresp="{S}all/shacharit">
            <j:conditional xml:id="occasion_yeladim">{service("shaharit").markup()}</j:conditional>
            <j:transclude type="external" target="{S}all/shacharit/yeladim"/>
            <j:endConditional target="#occasion_yeladim"/>
          </tei:div>
        </tei:div>
        <tei:div corresp="{S}chol">
{_entries(CHOL, 10)}
        </tei:div>
        <tei:div corresp="{S}shabbat">
{_entries(SHABBAT_SECTIONS, 10)}
          {gated("occasion_shabbat_minchah", SHABBAT_MINCHAH,
                 f'<j:transclude type="external" target="{S}shabbat/minchah"/>{avot_caller()}')}
{_entry("shabbat/conclusion", SHABBAT_CONCLUSION, 10)}
        </tei:div>
{_entries(OCCASIONS, 8)}
      </tei:div>"""


def index(*, project: str, lang: str, front: str) -> str:
    """One project's ``index.xml``: its header, its front matter and its running order."""
    notes = ""
    if project == PROJECT_EN:
        notes = f'          <tei:note xml:lang="en">{TRANSLATION_NOTE}</tei:note>\n'
    return f"""<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xml:lang="{lang}">
  <tei:teiHeader>
    <tei:fileDesc>
      <tei:titleStmt>
        <tei:title type="main" xml:lang="he">הַסִּדּוּר הַשָּׁלֵם</tei:title>
        <tei:title type="alt" xml:lang="en">ha-Siddur ha-Shalem (The Daily Prayer Book)</tei:title>
        <tei:respStmt>
          <tei:resp key="trc">Read from the 1949 scan and encoded by</tei:resp>
          <tei:name ref="urn:x-opensiddur:contributor:opensiddur.org/efraim-feinstein">Efraim Feinstein</tei:name>
        </tei:respStmt>
      </tei:titleStmt>
      <tei:editionStmt>
        <tei:edition>{EDITION[project]}</tei:edition>
      </tei:editionStmt>
      <tei:publicationStmt>
        <tei:distributor>
          <tei:ref target="http://opensiddur.org">Open Siddur Project</tei:ref>
        </tei:distributor>
        <tei:idno type="urn">{S}siddur@{project}</tei:idno>
        <tei:availability status="free">
          <tei:licence target="https://creativecommons.org/licenses/by-sa/4.0/">Creative Commons Attribution-ShareAlike 4.0 International</tei:licence>
        </tei:availability>
      </tei:publicationStmt>
      <tei:sourceDesc>
        <tei:bibl xml:id="project_source_bibl">
          <tei:title>ha-Siddur ha-Shalem: The Daily Prayer Book</tei:title>
          <tei:author>Philip Birnbaum</tei:author>
          <tei:publisher>Hebrew Publishing Company</tei:publisher>
          <tei:pubPlace>New York</tei:pubPlace>
          <tei:date when="1949">1949</tei:date>
          <tei:date type="accessed" when="2026-09-08">2026-09-08</tei:date>
          <tei:idno type="url">https://archive.org/details/PhilipBirnbaumHaSiddurHaShalemTheDailyPrayerBook1949</tei:idno>
          <tei:idno type="archive.org">PhilipBirnbaumHaSiddurHaShalemTheDailyPrayerBook1949</tei:idno>
{notes}          <tei:note xml:lang="en">The scan cited here is the source of the text, not merely a reference for it: every word was read off it, page by page.</tei:note>
          <tei:note type="encoding" xml:lang="en">Every tei:pb/@facs in this project deep-links into the leaf its page break falls on. The scan is 1541x2291 pixels per leaf, which is the scan itself and not a derivative.</tei:note>
          <tei:note type="encoding" xml:lang="en">In the front matter, tei:pb/@n in square brackets is a designation the book implies rather than prints. The printed Roman sequence runs IX to XXIII on scan leaves 11 to 25, which fixes leaf 3 as I; leaves 1 and 2 precede that sequence and are numbered from the scan.</tei:note>
        </tei:bibl>
      </tei:sourceDesc>
    </tei:fileDesc>
  </tei:teiHeader>
  <tei:text>
{front}
    <tei:body>
{BODY}
    </tei:body>
  </tei:text>
</tei:TEI>
"""
