"""Printed commentary and source notes, pages609–636, with split notes rejoined."""
import re
from .festival_musaf import URNS
from .festival_musaf_data import PAGES
from .notes_motzaei_shabbat import xml

def note(key,kind,text):
    return dict(target=URNS[key],kind=kind,lemma='',n='',paras=[dict(text=xml(text))])

# Citation and commentary anchors are deliberately separate when the scan's
# superscript and catchword fall on different phrases.
ANCHORS={609:['avot'],610:['ki_shem','ki_shem','sefatai'],611:['hu_eloheinu'],
 612:['qadosh_major','barukh_major','shema','ani','addir','yimlokh_major'],
 616:['shabbat_offering','pesach_offering'],617:['sukkot_opening'],
 618:['sukkot_day2','shavuot_offering','sukkot_opening'],619:['uminchatam'],
 620:['shemini_offering'],622:['shalosh_peamim'],624:['kohanim_reader'],
 625:['veteerav'],626:[None,'elohai_netzor','yehi_ratzon'],627:['dream'],
 628:['kohanim_response_1_3'],630:['kohanim_response_2_5','kohanim_response_3_4','kohanim_response_3_7'],
 631:['addir_bamarom'],632:['kohanim_ribbon','kiddush_shabbat','vayedaber'],633:['tal_bereshuto'],634:[None]}
NOTES=[]
for page,keys in ANCHORS.items():
    notes=PAGES[str(page)]['notes']
    assert len(keys)==len(notes),(page,keys,notes)
    for key,n in zip(keys,notes):
        if key is None:continue
        text=n['text']
        if page in (625,633):text+=' '+PAGES[str(page+1)]['notes'][0]['text']
        kind='source' if n['kind']=='citation' else 'commentary'
        text=re.sub(r'^\d+ ','',text)
        NOTES.append(note(key,kind,text))
