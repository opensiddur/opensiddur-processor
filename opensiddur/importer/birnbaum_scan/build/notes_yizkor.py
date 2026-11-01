"""All printed commentary and source citations on pages 601–608."""
from .yizkor import ROOT, SERVICE, URNS
from .yizkor_data import PAGES
from .notes_motzaei_shabbat import xml

def note(target,kind,text):
    return dict(target=target,kind=kind,lemma='',n='',paras=[dict(text=xml(p)) for p in text.split('\n')])
NOTES = [note(URNS['opening_144_3'],'commentary',PAGES['601']['notes'][0]['text']),
    note(URNS['opening_ecclesiastes_12_7'],'source',PAGES['602']['notes'][0]['text']),
    note(URNS['el_male_man'],'commentary',PAGES['606']['notes'][1]['text']),
    note(URNS['av_harachamim']+'/minachal','commentary',PAGES['607']['notes'][1]['text']+' '+PAGES['608']['notes'][1]['text']),
    note(URNS['av_harachamim']+'/harninu','source','Deuteronomy 32:43.'),
    note(URNS['av_harachamim']+'/veniqqeiti','source','Joel 4:21.'),
    note(URNS['av_harachamim']+'/lammah','source','Psalms 79:10; 9:13; 110:6–7.')]
