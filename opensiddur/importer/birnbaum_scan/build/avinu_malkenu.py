"""Avinu Malkenu in the weekday morning order, printed 97–102."""
from html import escape
from itertools import groupby

from .avinu_malkenu_data import ROWS
from .common import AGG, HOL, PRAYER, SIDDUR, cond, endcond, feature, pb

URN = PRAYER + "avinu_malkenu"
SIGIL = "1949 chol/shacharit/avinu_malkenu"
TEN_DAYS = feature(AGG, "aseret-ymei-tshuva")
# The existing minor-fast aggregate omits Tammuz; include its named holiday.
FAST = "<j:any>" + feature(AGG, "minor-fast") + feature(
    HOL, "tzom-tammuz", '<tei:numeric value="1"/>') + "</j:any>"
# The Ten Days wording takes precedence when a fast falls within that period.
FAST_WORDING = "<j:all>" + FAST + "<j:none>" + TEN_DAYS + "</j:none></j:all>"
RUBRICS = {
    "ten_days": "From Rosh Hashanah to Yom Kippur:",
    "fast": "On fast days:",
}
PREFIX = {"he": "אָבִֽינוּ מַלְכֵּֽנוּ, ", "en": "Our Father, our King, "}


def _contents(lang):
    side = 0 if lang == "he" else 1
    parts = []
    page_seen = None
    # Keep the five inscription alternatives together under each printed rubric.
    before = [r for r in ROWS if not r[0].startswith(("kotvenu_", "zokhrenu_")) and r[1] < 101]
    inscriptions = [r for r in ROWS if r[0].startswith(("kotvenu_", "zokhrenu_"))]
    after = [r for r in ROWS if r[1] == 101]
    for block, rows in (("opening", before), ("inscriptions", inscriptions), ("closing", after)):
        if block == "inscriptions":
            parts.append(f'<tei:div corresp="{URN}/inscriptions">')
        for group_number, (condition, grouped) in enumerate(groupby(rows, key=lambda r: r[2])):
            cid = f"avinu_{block}_{group_number}"
            if condition:
                parts.append(cond(cid, note=RUBRICS[condition],
                                  fs=TEN_DAYS if condition == "ten_days" else FAST_WORDING))
            for key, page, _, he, en in grouped:
                marker = ""
                if page != page_seen:
                    marker = pb(page + side, sigil=SIGIL)
                    page_seen = page
                text = PREFIX[lang] + (he if lang == "he" else en)
                # Milestones are the compiler's parallel alignment boundaries.
                parts.append(f'<tei:div><tei:p><tei:milestone unit="petition" corresp="{URN}/{key}"/>{marker}{escape(text)}</tei:p></tei:div>')
            if condition:
                parts.append(endcond(cid))
        if block == "inscriptions":
            parts.append("</tei:div>")
    return parts


def prayers(lang):
    side = 0 if lang == "he" else 1
    parts = [f'<tei:div corresp="{URN}">', *_contents(lang), "</tei:div>"]
    return [dict(name="avinu_malkenu", title="אָבִֽינוּ מַלְכֵּֽנוּ" if lang == "he" else "Avinu Malkenu",
                 urn=URN, first=97 + side, last=101 + side, body="\n".join(parts))]


def unit_body(project, by_name):
    from .build_he import _transclude, declaration
    parts = [f'<tei:div corresp="{SIDDUR}chol/shacharit/avinu_malkenu">', declaration(),
             cond("avinu_occasion",
                  note="Between Rosh Hashanah and Yom Kippur and on fast days:",
                  fs="<j:any>" + TEN_DAYS + FAST + "</j:any>")]
    _transclude(parts, by_name, "avinu_malkenu")
    return "\n".join(parts + [endcond("avinu_occasion"),
                               '<j:endDeclare target="#unit_service"/>', "</tei:div>"])


NOTES = [
    dict(kind="commentary", target=URN + "/chatanu", lemma="אבינו מלכנו", paras=[dict(text=(
        'is mentioned in the Talmud (Ta‘anith 25b) as the prayer of Rabbi Akiba on a fast day. '
        'There is a close resemblance between some of its phrases and the '
        '<tei:hi rend="italic">Shemoneh Esreh</tei:hi>. In the ninth century '
        '<tei:hi rend="italic">Siddur</tei:hi> of Amram Gaon there are only twenty-five verses of '
        '<tei:hi rend="italic">Avinu Malkenu</tei:hi>. In the course of time the number has '
        'been increased on account of disaster and persecution.'
    ))]),
    dict(kind="instruction", n="*", target=URN + "/zokhrenu", paras=[dict(text=(
        'On fast days, instead of “inscribe us” the phrase “remember us” is used.'
    ), rend="italic")]),
]
