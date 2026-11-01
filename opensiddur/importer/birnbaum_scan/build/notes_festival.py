"""The six commentaries printed on pages585–600."""
from .festival import ROOT, URNS
from .festival_data import PAGES
from .notes_motzaei_shabbat import xml

NOTES=[]
for page,key,continuation in [(585,'eruv',586),(589,'attah_vechartanu',None),
                              (590,'vattodienu',None),(592,'miqra',None),
                              (597,'savri',598),(599,'kiddush_close',None)]:
    note=PAGES[str(page)]['notes'][0]
    text=note['text']
    if continuation:text+=' '+PAGES[str(continuation)]['notes'][0]['text']
    NOTES.append(dict(target=ROOT+'/eruv_tavshilin' if key=='eruv' else URNS[key],
        kind='commentary',lemma=note['lemma'],n='',paras=[dict(text=xml(text))]))
