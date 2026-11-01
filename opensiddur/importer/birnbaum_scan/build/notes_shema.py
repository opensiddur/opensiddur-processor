"""Birnbaum's commentary and numbered references on printed 71–82."""
from .common import PRAYER


def note(target, text, lemma=None):
    result = dict(kind='commentary', target=target, paras=[dict(text=text)])
    if lemma:
        result['lemma'] = lemma
    return result


def he(text):
    return f'<tei:foreign xml:lang="he">{text}</tei:foreign>'


def italic(text):
    return f'<tei:hi rend="italic">{text}</tei:hi>'


SHEMA_NOTES = [
    note(PRAYER+'barekhu/call', 'introduces the main part of the service, consisting of the '+italic('Shema')+' and the '+italic('Shemoneh Esreh')+'. The silent meditation, found in Maḥzor Vitry, includes a sentence of the Aramaic Kaddish rendered into Hebrew and parts of Isaiah 44:6, Psalms 68:5 and 113:2.', 'ברכו'),
    note(PRAYER+'yotzer_or/opening', 'is a modified form of Isaiah 45:7, where the text has '+he('ובורא רע')+'. This variation is explained to be due to a desire of using a more auspicious expression (Berakhoth 11b).', 'יוצר אור'),
    note(PRAYER+'yotzer_or/el_barukh', 'is an alphabetical acrostic, the words beginning with the letters of the alphabet in regular order.', 'אל ברוך'),
    note(PRAYER+'ahavah_rabbah/ahavah', ', one of the most beautiful prayers in the liturgies of the world, is very old and was probably instituted by the men of the Great Assembly in the early period of the second Temple. A profound love for God and the Torah is echoed in this prayer, in which the merciful Father is entreated to enlighten our eyes and our minds to understand his teachings. This is the second of the two blessings preceding the '+italic('Shema')+', '+he('יוצר אור')+' being the first. As Psalm 19 praises God first for the sun and then for the Torah which enlightens the mind, so have we in these two blessings first a thanksgiving for natural light, then a thanksgiving for spiritual enlightenment. As in the case with all the prayers, occasional variations have been introduced here in the course of many centuries.', 'אהבה רבה'),
    note(PRAYER+'yotzer_or/qadosh', italic('Isaiah')+' 6:3.'),
    note(PRAYER+'yotzer_or/barukh_kevod', italic('Ezekiel')+' 3:12.'),
    note(PRAYER+'yotzer_or/lael_barukh', italic('Psalm')+' 136:7.'),
    note(PRAYER+'ahavah_rabbah/ahavah', 'let our heart be concentrated upon God, and not distracted by worldly desires. Such singleheartedness is frequently expressed by the phrases “a whole heart”, “a perfect heart.”', 'יחד לבבנו'),
    note(PRAYER+'shema/el_melekh_neeman', 'The initial letters of '+he('אל מלך נאמן')+' form the word '+he('אמן')+'. There are 245 words in the '+italic('Shema')+'. When the Reader repeats '+he('ה׳ אלהיכם אמת')+' the number of words is raised to 248, corresponding to the 248 parts of the human frame. On reciting the '+italic('Shema')+' privately, however, one is required to add the three words '+he('אל מלך נאמן')+' in order to complete the number 248.'),
    note('urn:x-opensiddur:text:bible:deuteronomy/6/4', 'The last letters of '+he('שמע')+' and '+he('אחד')+' form the word '+he('עד')+' (“witness”), that is, he who recites the '+italic('Shema')+' bears witness that God is One.'),
    note(PRAYER+'shema', 'The '+italic('Shema')+', Israel’s confession of faith, expresses the duty of loving and serving God with our whole being. The second paragraph demands that we give living expression to our love of God by careful observance of his precepts which are designed to assure our happiness. The third section contains the law of '+italic('tsitsith')+', intended to remind us constantly of our duties towards God, and a warning against following the evil impulses of the heart. The '+italic('Shema')+', sounding the keynote of Judaism, is the oldest prayer of the '+italic('Siddur')+'. In the morning service the '+italic('Shema')+' is preceded by two blessings and followed by one; in the evening service it is preceded by two blessings and followed by two. This is in keeping with the expression: “Seven times a day I praise thee” (Psalm 119:164; Berakhoth 11b).'),
    # A local occurrence anchor avoids attaching this note to every earlier Barukh shem.
    note('urn:x-opensiddur:text:siddur:chol/shacharit/shema/barukh_shem', 'was regularly used in the Temple. It is attributed to Jacob.', 'ברוך שם כבוד'),
    note(PRAYER+'emet_veyatziv/emet', 'is mentioned in the Mishnah (Tamid 5:1) among the prayers used in the Temple. The fifteen synonyms, '+he('ויציב–ויפה')+', correspond to the fifteen words in the last sentence of the '+italic('Shema')+', beginning with '+he('אני')+' and ending with '+he('אמת')+'. The rule is not to interrupt the connection between '+he('ה׳ אלהיכם')+' and '+he('אמת')+', as if these three words formed one sentence, meaning: “The Lord your God is true” (Mishnah Berakhoth 2:2).', 'אמת ויציב'),
    note(PRAYER+'emet_veyatziv/emet', 'refers to the '+italic('Shema')+' as a solemn profession of the Oneness of God. The '+italic('Shema')+' is the watchword of Israel’s faith, and it is the desire of every loyal Jew to have it upon his lips when he dies.', 'הדבר הזה'),
    note(PRAYER+'emet_veyatziv/mi_khamokhah', italic('Exodus')+' 15:11.'),
    note(PRAYER+'emet_veyatziv/adonai_yimlokh', italic('Exodus')+' 15:18.'),
]
