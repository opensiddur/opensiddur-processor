"""Candle lighting, parental blessing and Song of Songs, printed 221–236."""
import re
from .common import PRAYER, SIDDUR, PROJECT_HE, cond, endcond, feature, pb
from .conclusion import BIBLE, instruction, transclude, text_xml
from .milestones import Correspondences, milestone, marked
from .shacharit_end import editorial_head
from .song_of_songs_data import HE, EN, EN_PARAGRAPHS

ROOT = SIDDUR + 'shabbat/preparations'
CANDLES = PRAYER + 'hadlaqat_ner_shabbat'
PARENTAL = PRAYER + 'birkat_horim'
SONG = BIBLE + 'song_of_songs'
SIGIL = '1949 shabbat/preparations'
RECIPIENT = 'opensiddur:blessing-recipient'

CANDLE_TEXT = (
    'בָּרוּךְ אַתָּה, יְיָ אֱלֹהֵֽינוּ, מֶֽלֶךְ הָעוֹלָם, אֲשֶׁר קִדְּשָֽׁנוּ בְּמִצְוֹתָיו וְצִוָּֽנוּ לְהַדְלִיק נֵר שֶׁל שַׁבָּת.',
    'Blessed art thou, Lord our God, King of the universe, who hast sanctified us with thy commandments, and commanded us to light the Sabbath lights.')
CHILD_TEXT = {
    'sons': ('יְשִׂמְךָ אֱלֹהִים כְּאֶפְרַיִם וְכִמְנַשֶּׁה.',
             'May God make you like Ephraim and like Manasseh.'),
    'daughters': ('יְשִׂמֵךְ אֱלֹהִים כְּשָׂרָה, רִבְקָה, רָחֵל וְלֵאָה.',
                  'May God make you like Sarah and Rebekah, Rachel and Leah.'),
}


def recipient_condition(gender):
    # This is the child being blessed, not the person reciting the blessing.
    return feature(RECIPIENT, 'gender', f'<tei:symbol value="{gender}"/>')


def shared(lang, prayers):
    """Add biblical verse addresses to the already-encoded priestly blessing."""
    result = [dict(p) for p in prayers]
    p = next(p for p in result if p['name'] == 'birkat_kohanim')
    starts = ('יְבָרֶכְךָ', 'יָאֵר', 'יִשָּׂא') if lang == 'he' else (
        'May the Lord bless', 'may the Lord countenance', 'may the Lord favor')
    for verse, start in enumerate(starts, 24):
        if p['body'].count(start) != 1:
            raise ValueError(f'Ambiguous priestly blessing verse {verse}: {start}')
        p['body'] = p['body'].replace(start, milestone(BIBLE+f'numbers/6/{verse}', unit='verse')+start)
    p['body'] = p['body'].replace('</tei:p>', milestone(unit='verse')+'</tei:p>')
    page = 221 + int(lang == 'en')
    p['printings'] = (*p.get('printings', ()), (page, page))
    return result


def song_body(lang, chapters=None, paragraph_starts=None):
    """Biblical milestones preserve the print's independent paragraph structure."""
    chapters = (HE if lang == 'he' else EN) if chapters is None else chapters
    if paragraph_starts is None:
        paragraph_starts = {} if lang == 'he' else EN_PARAGRAPHS
    side = int(lang == 'en')
    title = 'שִׁיר הַשִּׁירִים' if lang == 'he' else 'THE SONG OF SONGS'
    parts = [f'<tei:div corresp="{SONG}"><tei:head xml:lang="{lang}">{title}</tei:head>', pb(221+side, sigil=SIGIL),
             '<tei:p>'+instruction('Chanted shortly before the Kabbalath Shabbath service.')+'</tei:p>']
    for chapter, verses in chapters.items():
        title = '[ '+ 'אבגדהוזח'[chapter-1]+' ]' if lang == 'he' else ('I','II','III','IV','V','VI','VII','VIII')[chapter-1]
        parts.append(f'<tei:div corresp="{SONG}/{chapter}"><tei:head xml:lang="{lang}">{title}</tei:head><tei:p>')
        marks = Correspondences()
        for number, text in enumerate(verses.splitlines(), 1):
            if number != 1 and number in paragraph_starts.get(chapter, ()):
                parts.append('</tei:p><tei:p>')
            parts.append(marks.start(f'{SONG}/{chapter}/{number}'))
            # A printed paragraph can also start within a verse (7:1 and 8:5).
            value = text_xml(text, SIGIL).replace('{p}', '</tei:p><tei:p>')
            value = re.sub(r'\{qere:([^|}]+)\|([^}]+)\}',
                r'<tei:choice><j:written>\1</j:written><j:read>\2</j:read></tei:choice>', value)
            parts.append(value+' ')
        parts.append(marks.close()+'</tei:p></tei:div>')
    return '\n'.join(parts+['</tei:div>'])


def prayers(lang):
    side = int(lang == 'en')
    result = []
    def add(name, urn, title, body, last=221):
        result.append(dict(name=name, urn=urn, title=title, first=221+side, last=last+side, body=body))
    title = ('הַדְלָקַת נֵר שֶׁל שַׁבָּת', 'LIGHTING OF THE SABBATH LIGHTS')[side]
    rubric = instruction('Upon lighting the Sabbath lights:') if lang == 'he' else ''
    add('shabbat_candles', CANDLES, title,
        f'<tei:div corresp="{CANDLES}"><tei:head xml:lang="{lang}">{title}</tei:head>'
        + pb(221+side, sigil=SIGIL) + rubric + '<tei:p>'+text_xml(CANDLE_TEXT[side], SIGIL)+'</tei:p></tei:div>')
    for key, texts in CHILD_TEXT.items():
        urn = PARENTAL+'/'+key
        text = text_xml(texts[side], SIGIL)
        if key == 'sons':
            # The print quotes only the blessing within Genesis 48:20, not the full verse.
            text = f'<tei:seg source="{BIBLE}genesis/48/20">{text}</tei:seg>'
        add('birkat_horim_'+key, urn, ('For '+key), '<tei:p>'+marked(urn, text)+'</tei:p>')
    add('song_of_songs', SONG, ('שִׁיר הַשִּׁירִים', 'The Song of Songs')[side], song_body(lang), 235)
    return result


def parental_body(lang):
    title = 'בִּרְכַּת הוֹרִים' if lang == 'he' else 'PARENTAL BLESSING'
    parts = [f'<tei:div corresp="{PARENTAL}"><tei:head xml:lang="{lang}">{title}</tei:head>',
             pb(221+int(lang=='en'), sigil=SIGIL)]
    for key, gender in (('sons', 'male'), ('daughters', 'female')):
        cid = 'blessing_'+key
        parts += [cond(cid, note='For '+key+':', fs=recipient_condition(gender)),
                  transclude(PARENTAL+'/'+key), endcond(cid)]
    parts.append(f'<j:transclude type="external" target="{BIBLE}numbers/6/24" targetEnd="{BIBLE}numbers/6/26"/>')
    return '\n'.join(parts+['</tei:div>'])


def units(project):
    lang = 'he' if project == PROJECT_HE else 'en'
    side = int(lang == 'en')
    return (
        dict(name='birkat_horim', urn=PARENTAL, title_he='בִּרְכַּת הוֹרִים', title_en='Parental blessing',
             pages=(221+side,221+side), body=parental_body(lang)),
        dict(name='shabbat_preparations', urn=ROOT, title_he='הכנות לשבת', title_en='Before the Sabbath service',
             pages=(221+side,235+side), body=f'<tei:div corresp="{ROOT}">'
             +editorial_head(lang,'הכנות לשבת','Before the Sabbath service')
             +transclude(CANDLES)+transclude(PARENTAL)
             +transclude(SONG)+'</tei:div>'),
    )
