"""Printed notes for Birnbaum pages 731–752; continuations joined once."""
from .lifecycle import URNS, TZIDDUK, KADDISH, CHAPEL, RESHUT, HARACHAMAN, PIDYON, MILAH
from .lifecycle_data import NOTES as READINGS
from .notes_motzaei_shabbat import xml as prose_xml
TARGETS={'tzidduq':TZIDDUK,'burial_kaddish':KADDISH,'chapel':CHAPEL,
         'milah_poem':RESHUT,'milah_harachaman':HARACHAMAN,'pidyon':PIDYON}


def xml(text):
    # Keep the parenthetical Aramaic spelling inside one RTL run.
    catchword='קדיש ל(את)חדתא'
    return prose_xml(text).replace(prose_xml(catchword),
        '<tei:foreign xml:lang="he">'+catchword+'</tei:foreign>')


def target(row):
    # Commentary has no printed numbered callout. Anchor it to the relevant
    # phrase/context without stacking two apparatus numbers on one word.
    if row['page']==743 and row['key']=='milah_elijah':return MILAH
    if row['page']==750 and row['kind']=='commentary':return URNS['pidyon_present']+'/shekel_haqodesh'
    if row['page']==752 and row['kind']=='commentary':return URNS['pidyon_answer']
    return TARGETS.get(row['key'],URNS.get(row['key']))


NOTES=[]
for row in READINGS:
    t=target(row)
    # These are adjacent paragraphs of the same unnumbered commentary on 749.
    # Keep them as two paragraphs under one apparatus marker.
    if NOTES and t==HARACHAMAN+'/6' and NOTES[-1]['target']==t:
        NOTES[-1]['paras'].append(dict(text=xml(row['text'])))
    else:
        NOTES.append(dict(target=t,kind=row['kind'],lemma='',n='',paras=[dict(text=xml(row['text']))]))
