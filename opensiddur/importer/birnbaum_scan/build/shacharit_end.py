"""Final readings and the addressable complete weekday morning service."""
from .common import SIDDUR, PRAYER, pb
from .conclusion import BIBLE, text_xml, transclude
from .milestones import Correspondences, marked
from .shacharit_end_data import DECALOGUE, PRINCIPLES, BELIEVE, HOPE, TARGUM

SERVICE = SIDDUR + 'chol/shacharit'
ROOT = SERVICE + '/final_readings'
DECALOGUE_URN = ROOT + '/decalogue'
PRINCIPLES_URN = PRAYER + 'ani_maamin'
HOPE_URN = ROOT + '/lishuatekha_qivviti'
SIGIL = '1949 chol/shacharit/final_readings'
EDITOR = 'urn:x-opensiddur:contributor:opensiddur.org/efraim-feinstein'

# The children's alternative remains separate. The common preliminary service is
# reused here, not reclassified as weekday-only or duplicated in the book index.
SERVICE_PARTS = (SIDDUR + 'all/shacharit/birkhot_hashachar',) + tuple(
    SERVICE + '/' + key for key in (
        'opening', 'pesuqei_dezimrah', 'shema', 'amidah', 'avinu_malkenu',
        'tachanun', 'kaddish_after_tachanun', 'torah_intro', 'torah',
        'conclusion', 'psalms', 'final_readings'))


def editorial_head(lang, he, en):
    return f'<tei:head xml:lang="{lang}" resp="{EDITOR}">{he if lang == "he" else en}</tei:head>'


def service_body(lang, parts=SERVICE_PARTS):
    from .build_he import declaration
    weekday = declaration().replace('xml:id="unit_service"', 'xml:id="weekday_service"')
    return '\n'.join([f'<tei:div corresp="{SERVICE}">',
        editorial_head(lang, 'תְּפִלַּת שַׁחֲרִית לְיוֹם חוֹל', 'Weekday Shacharit'), weekday,
        *(transclude(urn) for urn in parts), '<j:endDeclare target="#weekday_service"/>', '</tei:div>'])


def unit_body(lang):
    return '\n'.join([f'<tei:div corresp="{ROOT}">',
        editorial_head(lang, 'קריאות לסיום שחרית', 'Final readings'),
        *(transclude(urn) for urn in (DECALOGUE_URN, PRINCIPLES_URN, HOPE_URN)), '</tei:div>'])


def decalogue_body(lang, rows=DECALOGUE):
    """Biblical verse milestones within the printed commandment paragraphs."""
    side = 0 if lang == 'he' else 1
    title = 'עֲשֶׂרֶת הַדִּבְּרוֹת' if lang == 'he' else 'THE TEN COMMANDMENTS'
    citation = 'שמות כ, א–יז' if lang == 'he' else 'Exodus 20:1–17'
    out = [f'<tei:div corresp="{DECALOGUE_URN}">', pb(151 + side, sigil=SIGIL),
           f'<tei:head xml:lang="{lang}">{title}</tei:head>',
           f'<tei:p xml:lang="{lang}"><tei:hi rend="italic">{citation}</tei:hi></tei:p>']
    marks = Correspondences()
    opened = False
    command = 0
    for verse, label, he, en in rows:
        printed_label = ""
        if label is not None:
            if opened:
                out.append(marks.close() + '</tei:p>')
            out.append('<tei:p>')
            opened = True
            if label:
                command += 1
                printed_label = f'<tei:label>{label if lang == "he" else command}.</tei:label> '
        out.append(marks.start(BIBLE + f'exodus/20/{verse}'))
        out.append(printed_label + text_xml(he if lang == 'he' else en, SIGIL) + ' ')
    if opened:
        out.append(marks.close() + '</tei:p>')
    return '\n'.join(out + ['</tei:div>'])


def principles_body(lang, rows=PRINCIPLES):
    side = 0 if lang == 'he' else 1
    title = 'שְׁלֹשָׁה עָשָׂר עִקָּרִים' if lang == 'he' else 'THIRTEEN PRINCIPLES OF FAITH'
    out = [f'<tei:div corresp="{PRINCIPLES_URN}">', pb(153 + side, sigil=SIGIL),
           f'<tei:head xml:lang="{lang}">{title}</tei:head>']
    for number, (label, he, en) in enumerate(rows, 1):
        if number == 5:
            out.append(pb(155 + side, sigil=SIGIL))
        value = text_xml(BELIEVE + he if lang == 'he' else en, SIGIL)
        value = value.replace('{quote}', f'<tei:seg source="{BIBLE}psalms/33/15">').replace('{/quote}', '</tei:seg>')
        # Keep the printed label inside the same alignment unit as its text.
        # A label preceding the milestone becomes a separate parallel paragraph.
        value = f'<tei:label>{label if lang == "he" else number}.</tei:label> ' + value
        out.append('<tei:p>' + marked(PRINCIPLES_URN + f'/{number}', value) + '</tei:p>')
    return '\n'.join(out + ['</tei:div>'])


def hope_body(lang):
    out = [f'<tei:div corresp="{HOPE_URN}"><tei:p>']
    for i, pair in enumerate(HOPE):
        value = text_xml(pair[0 if lang == 'he' else 1], SIGIL)
        if i == 0:
            out.append(marked(BIBLE + 'genesis/49/18', value, unit='verse'))
        else:
            out.append(marked(HOPE_URN + f'/permutation_{i+1}',
                              f'<tei:seg source="{BIBLE}genesis/49/18">{value}</tei:seg>'))
        out.append(' ')
    out.append('</tei:p>')
    if lang == 'he':
        # The facing English page translates the Hebrew only. Do not invent an
        # English repetition of the Targum; its printed explanatory note is kept.
        out.append('<tei:p xml:lang="arc">' + marked(HOPE_URN + '/targum',
            f'<tei:seg source="{BIBLE}genesis/49/18">{TARGUM}</tei:seg>') + '</tei:p>')
    return '\n'.join(out + ['</tei:div>'])


def prayers(lang):
    side = 0 if lang == 'he' else 1
    return [dict(name=name, urn=urn, first=first+side, last=last+side,
                 title=he if lang == 'he' else en, body=builder(lang))
        for name, urn, first, last, he, en, builder in (
            ('decalogue', DECALOGUE_URN, 151, 153, 'עשרת הדברות', 'The Ten Commandments', decalogue_body),
            ('ani_maamin', PRINCIPLES_URN, 153, 155, 'שלושה עשר עיקרים', 'Thirteen principles of faith', principles_body),
            ('lishuatekha_qivviti', HOPE_URN, 155, 155, 'לישועתך קויתי', 'For thy salvation I hope', hope_body))]


def commentary(target, lemma, text):
    return dict(kind='commentary', target=target, lemma=lemma, paras=[dict(text=text)])


NOTES = [
    commentary(BIBLE+'exodus/20/1', 'עשרת הדברות', ', the Ten Commandments, were recited in the Temple daily before the <tei:hi rend="italic">Shema</tei:hi>. On account of the heretics, however, who asserted that only the Ten Commandments were divinely given, this custom was abolished outside Palestine (Berakhoth 12a).'),
    commentary(BIBLE+'exodus/20/5', 'לשונאי…', 'The penalty of man’s sins will be shared by his immediate descendants only if they too hate the ways of God; but the benefits of a man’s good deeds will extend indefinitely.'),
    commentary(BIBLE+'exodus/20/12', 'כבד…', 'The last six commandments are intended to safeguard a man’s life, domestic relations, property, and reputation.'),
    commentary(PRINCIPLES_URN+'/1', 'אני מאמין', ', like the poem <tei:hi rend="italic">Yigdal</tei:hi>, is based on the Thirteen Principles in which Moses Maimonides (1135–1204) sums up his Jewish philosophy, namely: 1) There is a Creator. 2) He is One. 3) He is incorporeal. 4) He is eternal. 5) He alone must be worshipped. 6) The prophets are true. 7) Moses was the greatest of all prophets. 8) The entire Torah was divinely given to Moses. 9) The Torah is immutable. 10) God knows all the acts and thoughts of man. 11) He rewards and punishes. 12) Messiah will come. 13) There will be resurrection.'),
    # This note is printed on the English page although the Targum has no English
    # counterpart. Anchor it after the final bilingual permutation, rather than
    # leaving a standalone note mark before the paragraph.
    commentary(HOPE_URN+'/permutation_3', 'לפורקנך סברית', 'is the Targum paraphrase of the preceding verse.'),
    dict(kind='citation', n='1', target=PRINCIPLES_URN+'/10', paras=[dict(text=f'<tei:ref target="{BIBLE}psalms/33/15">Psalm 33:15.</tei:ref>')]),
    dict(kind='citation', n='2', target=BIBLE+'genesis/49/18', paras=[dict(text=f'<tei:ref target="{BIBLE}genesis/49/18">Genesis 49:18.</tei:ref>')]),
]
