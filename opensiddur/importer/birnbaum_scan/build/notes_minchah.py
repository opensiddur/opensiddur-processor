"""Commentary printed with Minchah, including the essay on Kaddish (187–188)."""
from .minchah import NACHEM, ROOT


def note(target, text, *, lemma='', kind='commentary', n=''):
    return dict(kind=kind,target=target,lemma=lemma,n=n,paras=[dict(text=p) for p in text.split('\n\n')])


NOTES = [
    note(ROOT,
        'occurs in the Bible frequently in the sense of “gift” and “meal-offering.” It is only in talmudic literature that Minḥah denotes the afternoon service. Minḥah is one of the three daily services mentioned in Daniel 6:11 (“and three times a day he kneeled upon his knees, praying and giving thanks before his God”). According to tradition, the patriarchs Abraham, Isaac and Jacob were the authors of the three daily services. Both Shaḥarith and Minḥah correspond to the daily sacrifice (Tamid) which was offered in the Temple in the morning and in the afternoon. Since the recital of the Shema is obligatory only “when you lie down and when you rise up,” it is not included in the afternoon service. Minḥah may be recited at any time from noon (12:30) to sunset. The Minḥah service was postponed in the nineteenth century to very near sunset for the sake of convenience, so that Minḥah might be followed by Ma‘ariv after a short interval.', lemma='מנחה'),
    note(ROOT+'/opening', 'On <tei:foreign xml:lang="he">אשרי</tei:foreign>, see pages 57–59.'),
    note(ROOT+'/ki_shem', 'precedes the <tei:hi rend="italic">Amidahs</tei:hi> of <tei:hi rend="italic">Musaf</tei:hi> and <tei:hi rend="italic">Minḥah</tei:hi> only. In <tei:hi rend="italic">Shaḥarith</tei:hi> and <tei:hi rend="italic">Ma‘ariv</tei:hi> this verse is omitted, because there it would interrupt the connection between the benediction <tei:foreign xml:lang="he">גאל ישראל</tei:foreign> and the <tei:hi rend="italic">Amidah</tei:hi>.', lemma='כי שם'),
    note(ROOT+'/ki_shem', 'Deuteronomy 32:3.',kind='citation',n='2'),
    note(NACHEM+'/quotation', 'Zechariah 2:9.',kind='citation',n='1'),
    note(ROOT+'/tachanun', 'On <tei:foreign xml:lang="he">נפילת אפים</tei:foreign>, the posture assumed during the recital of <tei:hi rend="italic">Taḥanun</tei:hi>, see page 103.'),
    note(ROOT+'/conclusion', 'On <tei:foreign xml:lang="he">עלינו</tei:foreign>, see page 135.'),
    note(ROOT+'/conclusion/kaddish',
        '<tei:hi rend="smallcaps">The Kaddish</tei:hi>\n\n'
        'The essential part of the Kaddish consists of the congregational response: “May his great name be blessed forever and ever.” Around this response, which is found almost verbatim in Daniel 2:20, the whole Kaddish developed. Originally, it was recited at the close of sermons delivered in Aramaic, the language spoken by the Jews for about a thousand years after the Babylonian captivity. Hence the Kaddish was composed in Aramaic, the language in which the religious discourses were held. At a later period the Kaddish was introduced into the liturgy to mark the conclusion of sections of the service or of the reading of the biblical and talmudic passages.\n\n'
        'The Kaddish contains no reference to the dead. The earliest allusion to the Kaddish as a mourners’ prayer is found in Maḥzor Vitry, dated 1208, where it is said plainly: “The lad rises and recites Kaddish.” One may safely assume that since the Kaddish has as its underlying thought the hope for the redemption and ultimate healing of suffering mankind, the power of redeeming the dead from the sufferings of <tei:hi rend="italic">Gehinnom</tei:hi> came to be ascribed in the course of time to the recitation of this sublime doxology. Formerly the Kaddish was recited the whole year of mourning, so as to rescue the soul of one’s parents from the torture of <tei:hi rend="italic">Gehinnom</tei:hi> where the wicked are said to spend no less than twelve months. In order not to count one’s own parents among the wicked, the period for reciting the Kaddish was later reduced to eleven months.\n\n'
        'The observance of the anniversary of parents’ death, the Jahrzeit, originated in Germany, as the term itself well indicates. Rabbi Isaac Luria, the celebrated Kabbalist of the sixteenth century, explains that “while the orphan’s Kaddish within the eleven months helps the soul to pass from <tei:hi rend="italic">Gehinnom</tei:hi> to <tei:hi rend="italic">Gan-Eden</tei:hi>, the Jahrzeit Kaddish elevates the soul every year to a higher sphere in Paradise.” The Kaddish has thus become a great pillar of Judaism. No matter how far a Jew may have drifted away from Jewish life, the Kaddish restores him to his people and to the Jewish way of living.'),
    note(ROOT+'/conclusion/kaddish',
        'refers to the hymns of praise contained in the Psalms of David; compare the expression <tei:foreign xml:lang="he">על כל דברי שירות ותשבחות דוד</tei:foreign>.', lemma='לעילא מן כל... ושירתא תשבחתא'),
    note(ROOT+'/conclusion/kaddish',
        'is said between <tei:hi rend="italic">Rosh Hashanah</tei:hi> and <tei:hi rend="italic">Yom Kippur</tei:hi>; otherwise only <tei:foreign xml:lang="he">לעילא</tei:foreign> is said. In the Italian ritual <tei:foreign xml:lang="he">לעילא</tei:foreign> is repeated throughout the year. <tei:foreign xml:lang="he">לעילא לעילא</tei:foreign> is the Targum’s rendering of <tei:foreign xml:lang="he">מעלה מעלה</tei:foreign> (Deuteronomy 28:43).', lemma='לעילא לעילא'),
    note(ROOT+'/conclusion/kaddish',
        '(“consolations”), occurring in the Kaddish as a synonym of praise, probably refers to prophetic works such as the Book of Isaiah, called “Books of Consolation,” which contain hymns of praise as well as Messianic prophecies.',lemma='ונחמתא'),
    note(ROOT+'/conclusion/kaddish',
        ', which repeats in Hebrew the thought expressed in the preceding Aramaic paragraph, seems to have been added from the meditation recited at the end of the <tei:hi rend="italic">Shemoneh Esreh</tei:hi>. The same sentence is also added at the end of the grace recited after meals. The three steps backwards, which formed the respectful manner of retiring from a superior, were likewise transferred from the concluding sentence of the <tei:hi rend="italic">Shemoneh Esreh</tei:hi>. On the other hand, the phrase “and say Amen”, added at the end of the silent meditation after the <tei:hi rend="italic">Shemoneh Esreh</tei:hi>, must have been borrowed from the Kaddish which is always recited in the hearing of no fewer than ten men.',lemma='עושה שלום'),
]

# Place the essay at the congregational response, the three comments on
# Yitbarakh together at that paragraph, and Oseh Shalom at its own text.
_kaddish = [n for n in NOTES if n['target'] == ROOT+'/conclusion/kaddish']
NOTES = [n for n in NOTES if n not in _kaddish]
_kaddish[0]['target'] += '/response'
_kaddish[-1]['target'] += '/peace'
_praise = dict(kind='commentary', target=ROOT+'/conclusion/kaddish/praise', paras=[])
for entry in _kaddish[1:-1]:
    for para in entry['paras']:
        _praise['paras'].append(dict(text='<tei:label xml:lang="he">'+entry['lemma']+'</tei:label> '+para['text']))
NOTES += [_kaddish[0], _praise, _kaddish[-1]]
