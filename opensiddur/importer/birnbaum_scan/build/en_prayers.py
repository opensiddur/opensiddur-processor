# -*- coding: utf-8 -*-
"""The English of the weekday shacharit Amidah, printed pages 82-98.

Taken from the en.wikisource page-by-page transcription of this same print and checked
against the scan; the column layouts and the 565/566 Hallel page numbers were verified
on the image. Emits the SAME URNs as the Hebrew project, which is what aligns them.
"""
import functools

from .common import QUORUM, PRAYER, cond, endcond, feature, AGG, HOL, RECITATION
from . import common

#: Every page break in this module belongs to the Amidah's printing. Bound once here
#: because common.pb takes no default sigil -- see common.SIGIL_AMIDAH.
pb = functools.partial(common.pb, sigil=common.SIGIL_AMIDAH)

U = PRAYER
EN_PAGE = {81: 82, 83: 84, 85: 86, 87: 88, 89: 90, 91: 92, 93: 94, 95: 96, 97: 98}
AYT = feature(AGG, "aseret-ymei-tshuva")


def epb(hebrew_page):
    return pb(EN_PAGE[hebrew_page])


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


PRAYERS = []


def prayer(name, title, slug, first, last, body):
    PRAYERS.append(dict(name=name, title=title, urn=U + slug, first=first, last=last, body=body))


def simple(name, title, slug, page, text):
    prayer(name, title, slug, EN_PAGE[page], EN_PAGE[page], wrap(U + slug, d(None, text)))


prayer("amidah_adonai_sefatai", "O Lord, open thou my lips", "amidah/adonai_sefatai", 82, 82,
    wrap(U + "amidah/adonai_sefatai",
         d(None, f"{epb(81)}O Lord, open thou my lips, that my mouth may declare thy praise.")))

prayer("amidah_avot", "Blessing of the Patriarchs", "amidah/avot", 82, 84, "\n".join([
    f'        <tei:div corresp="{U}amidah/avot">',
    d(U + "amidah/avot/barukh_attah", "Blessed art thou, Lord our God and God of our fathers, God of Abraham, God of "
            "Isaac and God of Jacob; great, mighty and revered God, sublime God, who bestowest "
            "lovingkindness, and art Master of all things; who rememberest the good deeds of "
            "our fathers, and who wilt graciously bring a redeemer to their children’s children "
            "for the sake of thy name."),
    cond("cond_avot_aseret", note="Between Rosh Hashanah and Yom Kippur add:", fs=AYT),
    d(U + "amidah/avot/zokhrenu",
      f"({epb(83)}Remember us to life, O King who delightest in life; inscribe us in the book "
      "of life for thy sake, O living God.)"),
    endcond("cond_avot_aseret"),
    d(U + "amidah/avot/magen_avraham",
      "O King, Supporter, Savior and Shield! Blessed art thou, O Lord, Shield of Abraham."),
    "        </tei:div>"]))

prayer("amidah_gevurot", "Blessing of God’s might", "amidah/gevurot", 84, 84, "\n".join([
    f'        <tei:div corresp="{U}amidah/gevurot">',
    d(U + "amidah/gevurot/attah_gibbor", "Thou, O Lord, art mighty forever; thou revivest the dead; thou art powerful to save."),
    cond("cond_gevurot_geshem", note="Between Sukkoth and Pesaḥ add:", fs=feature(AGG, "geshem")),
    d(U + "amidah/gevurot/mashiv_haruach",
      "(Thou causest the wind to blow and the rain to fall.)"),
    endcond("cond_gevurot_geshem"),
    d(U + "amidah/gevurot/mekhalkel_chayyim", "Thou sustainest the living with kindness, and revivest the dead with great mercy; "
            "thou supportest all who fall, and healest the sick; thou settest the captives free, "
            "and keepest faith with those who sleep in the dust. Who is like thee, Lord of power? "
            "Who resembles thee, O King? Thou bringest death and restorest life, and causest "
            "salvation to flourish."),
    cond("cond_gevurot_aseret", note="Between Rosh Hashanah and Yom Kippur add:", fs=AYT),
    d(U + "amidah/gevurot/mi_khamokha",
      "(Who is like thee, merciful Father? In mercy thou rememberest thy creatures to life.)"),
    endcond("cond_gevurot_aseret"),
    d(U + "amidah/gevurot/mechayyeh_hametim",
      "Thou art faithful to revive the dead. Blessed art thou, O Lord, who revivest the dead."),
    "        </tei:div>"]))

prayer("amidah_qedushah", "Kedushah", "amidah/qedushah", 84, 86, "\n".join([
    f'        <tei:div corresp="{U}amidah/qedushah">',
    cond("cond_qedushah_repetition",
         note="When the Reader repeats the Shemoneh Esreh, the following Kedushah is said:",
         fs="<j:all>"+feature(RECITATION, "repetition")+feature(QUORUM, "minyan")+"</j:all>"),
    d(U + "amidah/qedushah/neqaddesh",
      "We sanctify thy name in this world even as they sanctify it in the highest heavens, "
      "as it is written by thy prophet: “They keep calling to one another:"),
    d(U + "amidah/qedushah/qadosh",
      "Holy, holy, holy is the Lord of hosts;", "The whole earth is full of his glory.”"),
    d(U + "amidah/qedushah/leummatam", "Those opposite them say: Blessed—"),
    d(U + "amidah/qedushah/barukh_kevod",
      "Blessed be the glory of the Lord from his abode."),
    d(U + "amidah/qedushah/uvdivrei", "And in thy holy Scriptures it is written:"),
    d(U + "amidah/qedushah/yimlokh",
      "The Lord shall reign forever,", "Your God, O Zion, for all generations.", "Praise the Lord!"),
    f'          <tei:div corresp="{U}amidah/qedushah/ledor_vador">',
    '            <tei:note type="instruction" xml:lang="en" corresp="urn:x-opensiddur:instruction:role/reader">Reader:</tei:note>',
    f"            <tei:p>{epb(85)}Through all generations we will declare thy greatness; to all "
    "eternity we will proclaim thy holiness; thy praise, our God, shall never depart from our "
    "mouth, for thou art a great and holy God and King.</tei:p>",
    "          </tei:div>",
    cond("cond_qedushah_seal_ordinary", fs=AYT, negate=True, marked=True),
    d(U + "amidah/qedushah/hael_haqadosh", "Blessed art thou, O Lord, holy God."),
    endcond("cond_qedushah_seal_ordinary"),
    cond("cond_qedushah_seal_aseret",
         note="Between Rosh Hashanah and Yom Kippur substitute:", fs=AYT),
    d(U + "amidah/qedushah/hamelekh_haqadosh", "(Blessed art thou, O Lord, holy King.)"),
    endcond("cond_qedushah_seal_aseret"),
    endcond("cond_qedushah_repetition"),
    "        </tei:div>"]))

prayer("amidah_qedushat_hashem", "Sanctification of God’s name", "amidah/qedushat_hashem", 86, 86, "\n".join([
    f'        <tei:div corresp="{U}amidah/qedushat_hashem">',
    d(U + "amidah/qedushat_hashem/attah_qadosh", "Thou art holy and thy name is holy, and holy beings praise thee daily."),
    cond("cond_qh_seal_ordinary", fs=AYT, negate=True, marked=True),
    d(U + "amidah/qedushat_hashem/hael_haqadosh", "Blessed art thou, O Lord, holy God."),
    endcond("cond_qh_seal_ordinary"),
    cond("cond_qh_seal_aseret",
         note="Between Rosh Hashanah and Yom Kippur substitute:", fs=AYT),
    d(U + "amidah/qedushat_hashem/hamelekh_haqadosh", "(Blessed art thou, O Lord, holy King.)"),
    endcond("cond_qh_seal_aseret"),
    "        </tei:div>"]))

simple("amidah_binah", "Blessing for knowledge", "amidah/binah", 85,
       "Thou favorest man with knowledge, and teachest mortals understanding. O grant us "
       "knowledge, understanding and insight. Blessed art thou, O Lord, gracious Giver of knowledge.")
simple("amidah_teshuvah", "Blessing for repentance", "amidah/teshuvah", 85,
       "Restore us, our Father, to thy Torah; draw us near, our King, to thy service; cause us "
       "to return to thee in perfect repentance. Blessed art thou, O Lord, who art pleased with "
       "repentance.")
simple("amidah_selichah", "Blessing for forgiveness", "amidah/selichah", 85,
       "Forgive us, our Father, for we have sinned; pardon us, our King, for we have "
       "transgressed; for thou dost pardon and forgive. Blessed art thou, O Lord, who art "
       "gracious and ever forgiving.")

prayer("amidah_geullah", "Blessing for redemption", "amidah/geullah", 86, 86, "\n".join([
    f'        <tei:div corresp="{U}amidah/geullah">',
    d(U + "amidah/geullah/reeh_na", "Look upon our affliction and champion our cause; redeem us speedily for thy name’s "
            "sake, for thou art a mighty Redeemer. Blessed art thou, O Lord, Redeemer of Israel."),
    cond("cond_geullah_aneinu",
         note="On fast days (except Tish‘ah b’Av) the Reader adds:",
         fs="\n".join(["          <j:all>", feature(AGG, "minor-fast"),
                       feature(RECITATION, "repetition"), feature(QUORUM, "minyan"), "          </j:all>"])),
    d(U + "amidah/aneinu",
      "(Answer us, O Lord, answer us on the day of our fast, for we are in great distress. "
      "Regard not our wickedness; conceal not thy presence from us, and hide not thyself from "
      "our supplication. Be near to our cry, and let thy kindness comfort us; even before we "
      "call to thee answer us, as it is said: “Before they call, I will answer; while they are "
      "yet speaking, I will hear.” For thou, O Lord, art he who answers in time of trouble, who "
      "redeems and delivers in all times of woe and stress. Blessed art thou, O Lord, who "
      "answerest in time of distress.)"),
    endcond("cond_geullah_aneinu"),
    "        </tei:div>"]))

simple("amidah_refuah", "Blessing for healing", "amidah/refuah", 87,
       f"{epb(87)}Heal us, O Lord, and we shall be healed; save us and we shall be saved; for "
       "thou art our praise. Grant a perfect healing to all our wounds; for thou art a faithful "
       "and merciful God, King and Healer. Blessed art thou, O Lord, who healest the sick among "
       "thy people Israel.")

# The English page mirrors the physical placement of the two columns so that the READING
# ORDER stays the same. Only the season is encoded; column position is a fact about the
# page, not about the text.
prayer("amidah_shanim", "Blessing of the years", "amidah/shanim", 88, 88, "\n".join([
    f'        <tei:div corresp="{U}amidah/shanim">',
    d(U + "amidah/shanim/barekh_aleinu", "Bless for us, Lord our God, this year and all kinds of its produce for the best."),
    cond("cond_shanim_berakhah", note="From Pesaḥ till December 4th say:",
         fs=feature(AGG, "tal-umatar"), negate=True),
    d(U + "amidah/shanim/veten_berakhah", "Bestow a blessing"),
    endcond("cond_shanim_berakhah"),
    cond("cond_shanim_tal_umatar", note="From December 4th till Pesaḥ say:",
         fs=feature(AGG, "tal-umatar")),
    d(U + "amidah/shanim/veten_tal_umatar", "Bestow dew and rain for a blessing"),
    endcond("cond_shanim_tal_umatar"),
    d(U + "amidah/shanim/al_penei_haadamah", "upon the face of the earth. Satisfy us with thy goodness, and bless our year like "
            "other good years. Blessed art thou, O Lord, who blessest the years."),
    "        </tei:div>"]))

simple("amidah_qibbutz_galuyot", "Blessing for the ingathering", "amidah/qibbutz_galuyot", 87,
       "Sound the great Shofar for our freedom; lift up the banner to bring our exiles together, "
       "and assemble us from the four corners of the earth. Blessed art thou, O Lord, who "
       "gatherest the dispersed of thy people Israel.")

prayer("amidah_mishpat", "Blessing for justice", "amidah/mishpat", 88, 88, "\n".join([
    f'        <tei:div corresp="{U}amidah/mishpat">',
    d(U + "amidah/mishpat/hashivah_shofeteinu", "Restore our judges as at first, and our counselors as at the beginning; remove from "
            "us sorrow and sighing; reign thou alone over us, O Lord, in kindness and mercy, and "
            "clear us in judgment."),
    cond("cond_mishpat_seal_ordinary", fs=AYT, negate=True, marked=True),
    d(U + "amidah/mishpat/melekh_ohev_tzedaqah",
      "Blessed art thou, O Lord, King, who lovest righteousness and justice."),
    endcond("cond_mishpat_seal_ordinary"),
    cond("cond_mishpat_seal_aseret",
         note="Between Rosh Hashanah and Yom Kippur substitute:", fs=AYT),
    d(U + "amidah/mishpat/hamelekh_hamishpat", "(Blessed art thou, O Lord, King of Justice.)"),
    endcond("cond_mishpat_seal_aseret"),
    "        </tei:div>"]))

simple("amidah_minim", "Blessing against slanderers", "amidah/minim", 87,
       "May the slanderers have no hope; may all wickedness perish instantly; may all thy enemies "
       "be soon cut down. Do thou speedily uproot and crush the arrogant; cast them down and "
       "humble them speedily in our days. Blessed art thou, O Lord, who breakest the enemies and "
       "humblest the arrogant.")

prayer("amidah_tzaddiqim", "Blessing for the righteous", "amidah/tzaddiqim", 88, 90,
    wrap(U + "amidah/tzaddiqim", d(None,
        "May thy compassion, Lord our God, be aroused over the righteous and over the godly; over "
        "the leaders of thy people, the house of Israel, and over the remnant of their sages; over "
        "the true proselytes and over us. Grant a good reward to all who truly trust"
        f"{epb(89)} in thy name, and place our lot among them; may we never come to shame, for in "
        "thee we trust. Blessed art thou, O Lord, who art the stay and trust of the righteous.")))

for nm, ti, sl, txt in [
    ("amidah_yerushalayim", "Blessing for Jerusalem", "amidah/yerushalayim",
     "Return in mercy to thy city Jerusalem and dwell in it as thou hast promised; rebuild it "
     "soon, in our days, as an everlasting structure, and speedily establish in it the throne of "
     "David. Blessed art thou, O Lord, Builder of Jerusalem."),
    ("amidah_david", "Blessing of David", "amidah/david",
     "Speedily cause the offspring of thy servant David to flourish, and let his glory be exalted "
     "by thy help, for we hope for thy deliverance all day. Blessed art thou, O Lord, who causest "
     "salvation to flourish."),
    ("amidah_tefillah", "Blessing for prayer", "amidah/tefillah",
     "Hear our voice, Lord our God; spare us and have pity on us; accept our prayer in mercy and "
     "favor, for thou art God who hearest prayers and supplications; from thy presence, our King, "
     "dismiss us not empty-handed, for thou hearest in mercy the prayer of thy people Israel. "
     "Blessed art thou, O Lord, who hearest prayer."),
]:
    prayer(nm, ti, sl, 90, 90, wrap(U + sl, d(None, txt)))

prayer("amidah_avodah", "Blessing for the Temple service", "amidah/avodah", 90, 92, "\n".join([
    f'        <tei:div corresp="{U}amidah/avodah">',
    d(U + "amidah/avodah/retzeh", "Be pleased, Lord our God, with thy people Israel and with their prayer; restore the "
            "worship to thy most holy sanctuary; accept Israel’s offerings and prayer with "
            "gracious love. May the worship of thy people Israel be ever pleasing to thee."),
    cond("cond_avodah_yaaleh", note="On Rosh Ḥodesh and Ḥol ha-Mo‘ed add:",
         fs="\n".join(["          <j:any>",
                       feature(HOL, "rosh-hodesh", '<tei:numeric value="1" max="2"/>'),
                       feature(AGG, "chol-hamoed"), "          </j:any>"])),
    f'        <j:transclude type="external" target="{U}yaaleh_veyavo"/>',
    endcond("cond_avodah_yaaleh"),
    d(U + "amidah/avodah/vetechezeinah",
      "May our eyes behold thy return in mercy to Zion. Blessed art thou, O Lord, who restorest "
      "thy divine presence to Zion."),
    "        </tei:div>"]))

prayer("yaaleh_veyavo", "Ya‘aleh v’yavo", "yaaleh_veyavo", 90, 92, "\n".join([
    f'        <tei:div corresp="{U}yaaleh_veyavo">',
    d(U + "yaaleh_veyavo/eloheinu_velohei", "(Our God and God of our fathers, may the remembrance of us, of our fathers, of "
            "Messiah the son of David thy servant, of Jerusalem thy holy city, and of all thy "
            "people the house of Israel, ascend and come and be accepted before thee for "
            "deliverance and happiness, for grace, kindness and mercy, for life and peace, on "
            "this day of"),
    cond("cond_yvy_rosh_chodesh", note="Rosh Ḥodesh",
         fs=feature(HOL, "rosh-hodesh", '<tei:numeric value="1" max="2"/>')),
    d(U + "yaaleh_veyavo/rosh_chodesh", "the New Moon."),
    endcond("cond_yvy_rosh_chodesh"),
    cond("cond_yvy_pesach", note="Pesaḥ",
         fs=feature(HOL, "pesah", '<tei:numeric value="1" max="8"/>')),
    d(U + "yaaleh_veyavo/pesach", "the Feast of Unleavened Bread."),
    endcond("cond_yvy_pesach"),
    cond("cond_yvy_sukkot", note="Sukkoth",
         fs=feature(HOL, "sukkot", '<tei:numeric value="1" max="7"/>')),
    d(U + "yaaleh_veyavo/sukkot", "the Feast of Tabernacles."),
    endcond("cond_yvy_sukkot"),
    d(U + "yaaleh_veyavo/zokhrenu", "Remember us this day, Lord our God, for happiness; be mindful"
            f"{epb(91)} of us for blessing; save us to enjoy life. With a promise of salvation "
            "and mercy spare us and be gracious to us; have pity on us and save us, for we look "
            "to thee, for thou art a gracious and merciful God and King.)"),
    "        </tei:div>"]))

prayer("amidah_hodaah", "Blessing of thanksgiving", "amidah/hodaah", 92, 94, "\n".join([
    f'        <tei:div corresp="{U}amidah/hodaah">',
    cond("cond_modim_derabbanan",
         note="When the Reader repeats the Shemoneh Esreh, the Congregation responds here by saying:",
         fs="<j:all>"+feature(RECITATION, "repetition")+feature(QUORUM, "minyan")+"</j:all>"),
    d(U + "amidah/hodaah/modim_derabbanan",
      "(We thank thee, who art the Lord our God and the God of our fathers. God of all mankind, "
      "our Creator and Creator of the universe, blessings and thanks are due to thy great and "
      "holy name, because thou hast kept us alive and sustained us; mayest thou ever grant us "
      "life and sustenance. O gather our exiles to thy holy courts to observe thy laws, to do thy "
      "will, and to serve thee with a perfect heart. For this we thank thee. Blessed be God to "
      "whom all thanks are due.)"),
    endcond("cond_modim_derabbanan"),
    d(U + "amidah/hodaah/modim", f"{epb(91)}We ever thank thee, who art the Lord our God and the God of our fathers. "
            "Thou art the strength of our life and our saving shield. In every generation we will "
            "thank thee and recount thy praise—for our lives which are in thy charge, for our "
            "souls which are in thy care, for thy miracles which are daily with us, and for thy "
            "continual wonders and favors—evening, morning and noon. Beneficent One, whose "
            "mercies never fail, Merciful One, whose kindnesses never cease, thou hast always "
            "been our hope."),
    cond("cond_hodaah_chanukah", note="On Ḥanukkah add:",
         fs=feature(HOL, "hanukkah", '<tei:numeric value="1" max="8"/>')),
    f'        <j:transclude type="external" target="{U}al_hanissim/chanukah"/>',
    endcond("cond_hodaah_chanukah"),
    cond("cond_hodaah_purim", note="On Purim add:",
         fs=feature(HOL, "purim-observed", '<tei:numeric value="1"/>')),
    f'        <j:transclude type="external" target="{U}al_hanissim/purim"/>',
    endcond("cond_hodaah_purim"),
    d(U + "amidah/hodaah/veal_kullam", "For all these acts may thy name, our King, be blessed and exalted forever and ever."),
    cond("cond_hodaah_aseret", note="Between Rosh Hashanah and Yom Kippur add:", fs=AYT),
    d(U + "amidah/hodaah/ukhtov",
      "(Inscribe all thy people of the covenant for a happy life.)"),
    endcond("cond_hodaah_aseret"),
    d(U + "amidah/hodaah/hatov_shimkha",
      "All the living shall ever thank thee and sincerely praise thy name, O God, who art always "
      "our salvation and help. Blessed art thou, O Lord, Beneficent One, to whom it is fitting to "
      "give thanks."),
    "        </tei:div>"]))

prayer("al_hanissim_chanukah", "Al ha-Nissim for Ḥanukkah", "al_hanissim/chanukah", 92, 94,
    wrap(U + "al_hanissim/chanukah", "\n".join([
      d(U + "al_hanissim/chanukah/al_hanissim", "(We thank thee for the miracles, for the redemption, for the mighty deeds and "
              "triumphs, and for the battles which thou didst perform for our fathers in those "
              "days, at this season—"),
      d(U + "al_hanissim/chanukah/bimei", "In the days of the Hasmonean, Mattathias ben Yoḥanan, the High Priest, and his "
              "sons, when a wicked Hellenic government rose up against thy people Israel to make "
              f"them forget thy Torah and transgress the laws of thy will. Thou in thy great "
              f"mercy didst{epb(93)} stand by them in the time of their distress. Thou didst "
              "champion their cause, defend their rights and avenge their wrong; thou didst "
              "deliver the strong into the hands of the weak, the many into the hands of the few, "
              "the impure into the hands of the pure, the wicked into the hands of the righteous, "
              "and the arrogant into the hands of the students of thy Torah. Thou didst make a "
              "great and holy name for thyself in thy world, and for thy people Israel thou didst "
              "perform a great deliverance unto this day. Thereupon thy children entered the "
              "shrine of thy house, cleansed thy Temple, purified thy sanctuary, kindled lights "
              "in thy holy courts, and designated these eight days of Ḥanukkah for giving thanks "
              "and praise to thy great name.)")])))

prayer("al_hanissim_purim", "Al ha-Nissim for Purim", "al_hanissim/purim", 94, 94,
    wrap(U + "al_hanissim/purim", "\n".join([
      d(U + "al_hanissim/purim/al_hanissim", "(We thank thee for the miracles, for the redemption, for the mighty deeds and "
              "triumphs, and for the battles which thou didst perform for our fathers in those "
              "days, at this season—"),
      d(U + "al_hanissim/purim/bimei", "In the days of Mordecai and Esther, in Shushan the capital [of Persia], when the "
              "wicked Haman rose up against them and sought to destroy, slay and wipe out all the "
              "Jews, young and old, infants and women, in one day, on the thirteenth of the "
              "twelfth month Adar, and to plunder their wealth. Thou in thy great mercy didst "
              "frustrate his counsel and upset his plan; thou didst cause his mischief to recoil "
              "on his own head, so that he and his sons were hanged upon the gallows.)")])))

prayer("amidah_birkat_kohanim", "Priestly blessing", "amidah/birkat_kohanim", 94, 96, "\n".join([
    f'        <tei:div corresp="{U}amidah/birkat_kohanim">',
    '          <tei:note type="instruction" xml:lang="en" corresp="urn:x-opensiddur:instruction:amidah/birkat_kohanim_leshatz">Priestly blessing recited by Reader:</tei:note>',
    "          <tei:p>Our God and God of our fathers, bless us with the threefold"
    f"{epb(95)} blessing written in thy Torah by thy servant Moses and spoken by Aaron and his "
    "sons the priests, thy holy people, as it is said: “May the Lord bless you and protect you; "
    "may the Lord countenance you and be gracious to you; may the Lord favor you and grant you "
    "peace.”</tei:p>",
    "        </tei:div>"]))

prayer("amidah_shalom", "Blessing for peace", "amidah/shalom", 96, 96, "\n".join([
    f'        <tei:div corresp="{U}amidah/shalom">',
    d(U + "amidah/shalom/sim_shalom",
      "O grant peace, happiness, blessing, grace, kindness and mercy to us and to all Israel thy "
      "people. Bless us all alike, our Father, with the light of thy countenance; indeed, by the "
      "light of thy countenance thou hast given us, Lord our God, a Torah of life, "
      "lovingkindness, charity, blessing, mercy, life and peace. May it please thee to bless thy "
      "people Israel with peace at all times and hours."),
    cond("cond_shalom_seal_ordinary", fs=AYT, negate=True, marked=True),
    d(U + "amidah/shalom/hamevarekh",
      "Blessed art thou, O Lord, who blessest thy people Israel with peace."),
    endcond("cond_shalom_seal_ordinary"),
    cond("cond_shalom_seal_aseret",
         note="Between Rosh Hashanah and Yom Kippur say:", fs=AYT),
    d(U + "amidah/shalom/besefer_chayyim",
      "(May we and all Israel thy people be remembered and inscribed before thee in the book of "
      "life and blessing, peace and prosperity, for a happy life and for peace. Blessed art thou, "
      "O Lord, Author of peace.)"),
    endcond("cond_shalom_seal_aseret"),
    "        </tei:div>"]))

prayer("amidah_elohai_netzor", "My God, guard my tongue", "amidah/elohai_netzor", 96, 96, "\n".join([
    f'        <tei:div corresp="{U}amidah/elohai_netzor">',
    '          <tei:note type="instruction" xml:lang="en">After the Shemoneh Esreh add the following meditation:</tei:note>',
    "          <tei:p>My God, guard my tongue from evil, and my lips from speaking falsehood. May "
    "my soul be silent to those who insult me; be my soul lowly to all as the dust. Open my heart "
    "to thy Torah, that my soul may follow thy commands. Speedily defeat the counsel of all those "
    "who plan evil against me, and upset their design. Do it for the glory of thy name; do it for "
    "the sake of thy power; do it for the sake of thy holiness; do it for the sake of thy Torah. "
    "That thy beloved may be rescued, save with thy right hand and answer me. May the words of my "
    "mouth and the meditation of my heart be pleasing before thee, O Lord, my Stronghold and my "
    "Redeemer. May he who creates peace in his high heavens create peace for us and for all "
    "Israel. Amen.</tei:p>",
    "        </tei:div>"]))

prayer("amidah_yehi_ratzon", "May it be thy will", "amidah/yehi_ratzon", 96, 98,
    wrap(U + "amidah/yehi_ratzon", d(None,
        "May it be thy will, Lord our God and God of our fathers, that the Temple be speedily "
        "rebuilt in our days, and grant us a share in thy Torah. There we will serve thee with "
        f"reverence, as in the{epb(97)} days of old and as in former years. Then the offering of "
        "Judah and Jerusalem will be pleasing to the Lord, as in the days of old and as in "
        "former years.")))

prayer("amidah_havinenu", "Abridged Shemoneh Esreh", "amidah/havinenu", 98, 98,
    wrap(U + "amidah/havinenu", d(None,
        "Grant us, Lord our God, wisdom to learn thy ways; subject our heart to thy worship; "
        "forgive us so that we may be redeemed; keep us from suffering; satisfy us with the "
        "products of thy earth; gather our dispersed people from the four corners of the earth. "
        "Judge those who stray from thy faith; punish the wicked; may the righteous rejoice over "
        "the rebuilding of thy city, the reconstruction of thy Temple, the flourishing dynasty of "
        "thy servant David and the continuance of the offspring of thy anointed, the son of "
        "Jesse. Answer us before we call. Blessed art thou, O Lord, who hearest prayer.")))
