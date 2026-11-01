"""Printed commentary and source citations for the conclusion of Shabbat."""
import re
from html import escape
from .motzaei_shabbat import ROOT, LEVANAH, POEMS
from .common import PRAYER, POEM
from .motzaei_data import READINGS


def xml(value):
    value=escape(value)
    return re.sub(r'([\u0590-\u05ff]+(?:[ \u0590-\u05ff׳״]*[\u0590-\u05ff])?)',
        r'<tei:foreign xml:lang="he">\1</tei:foreign>',value)


def notes():
    rows=[]
    targets={536:ROOT+'/psalm144',537:ROOT+'/vihi_noam',538:ROOT+'/veattah_qadosh',
        539:ROOT+'/veattah_qadosh',540:ROOT+'/veattah_qadosh',541:ROOT+'/veyitten_lekha',
        542:ROOT+'/veyitten_lekha',544:ROOT+'/veyitten_lekha',545:ROOT+'/veyitten_lekha',
        546:ROOT+'/veyitten_lekha',547:ROOT+'/veyitten_lekha',548:ROOT+'/veyitten_lekha',
        549:ROOT+'/veyitten_lekha',550:ROOT+'/veyitten_lekha',551:ROOT+'/havdalah',552:ROOT+'/havdalah',
        553:POEM+POEMS[0],555:POEM+POEMS[1],557:POEM+POEMS[3],
        559:PRAYER+'ribbon_haolamim',562:LEVANAH+'/blessing',563:LEVANAH+'/david',564:LEVANAH+'/kol_dodi',566:LEVANAH+'/yehi_ratzon'}
    for page,base_target in targets.items():
        for i,text in enumerate(READINGS[str(page)].get('notes',[])):
            target=base_target
            text=text.removeprefix('* ')
            # Continuations join their preceding commentary rather than making
            # a second note out of the middle of a sentence.
            if (page,i) in ((550,0),(552,0)):continue
            if (page,i)==(549,1):
                text+=' '+READINGS['550']['notes'][0]
                target=ROOT+'/psalm128'
            if page==551:text+=' '+READINGS['552']['notes'][0]
            if (page,i)==(550,1):target=ROOT+'/psalm128'
            if (page,i)==(559,1):target=PRAYER+'ufetach_lanu'
            if (page,i)==(563,1):target=LEVANAH+'/greetings'
            if page==566:target=LEVANAH+('/mi_zot' if i==0 else '/yehi_ratzon')
            source=bool(re.match(r'\d ',text)) or page==566
            rows.append(dict(target=target,kind='source' if source else 'commentary',lemma='',n='',paras=[dict(text=xml(text))]))
    return rows

NOTES=notes()
