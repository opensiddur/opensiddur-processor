"""The commentary and source citations printed with Rosh Hodesh Musaf."""
from .rosh_hodesh_musaf import URNS
from .rosh_hodesh_musaf_data import PAGES
from .notes_motzaei_shabbat import xml

NOTES=[]
def add(key,text,kind='source',n=''):
    NOTES.append(dict(target=URNS[key],kind=kind,lemma='',n=n,paras=[dict(text=xml(text))]))
add('rashei',PAGES['577']['notes'][0]['text']+' '+PAGES['578']['notes'][0]['text'],kind='commentary')
for page,keys in [(576,['ki_shem','sefatai','qadosh']),(578,['barukh','yimlokh']),(580,['offerings']),(584,['kohanim','elohai','yehi'])]:
    for key,note in zip(keys,[n for n in PAGES[str(page)]['notes'] if 'n' in n]):
        # Shared passages already carry these exact source citations.
        if key in ('ki_shem','sefatai','qadosh','barukh','yehi'):continue
        add(key,note['text'],n=note['n'])
