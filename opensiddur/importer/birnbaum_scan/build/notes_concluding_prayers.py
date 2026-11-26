"""Printed notes on 753–790, with Hebrew directional spans."""
from .concluding_prayers import BED, BLESSINGS, GRACE, MARRIAGE, SEVEN, URNS
from .concluding_prayers_data import NOTES as READINGS
from .notes_motzaei_shabbat import xml

TARGETS={'marriage':MARRIAGE,'seven':SEVEN,'grace':GRACE,'zimmun':GRACE+'/zimmun',
 'blessings':BLESSINGS,'bedtime':BED,'adon':BED+'/adon_olam','bed_adon_10':BED+'/adon_olam'}
NOTES=[]
for row in READINGS:
 target=TARGETS.get(row['key'],URNS.get(row['key']))
 assert target,row
 # Adjacent commentary paragraphs sharing an anchor remain separate paragraphs
 # under one marker, avoiding stacked apparatus numbers.
 if NOTES and NOTES[-1]['target']==target and NOTES[-1]['kind']==row['kind']:
  NOTES[-1]['paras'].append(dict(text=xml(row['text'])))
 else:NOTES.append(dict(target=target,kind=row['kind'],lemma='',n='',paras=[dict(text=xml(row['text']))]))
