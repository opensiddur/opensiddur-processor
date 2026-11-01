"""All printed notes, with cross-page continuations joined and Hebrew runs directed."""
from .common import PRAYER, POEM
from .omer_akdamut_data import NOTES as READINGS
from .notes_motzaei_shabbat import xml

NOTES = [dict(target=(POEM+r['key'] if r['key'].startswith('aqdamut/') else PRAYER+'sefirat_haomer/'+r['key']),kind=r['kind'],lemma='',n='',paras=[dict(text=xml(r['text']))]) for r in READINGS]
