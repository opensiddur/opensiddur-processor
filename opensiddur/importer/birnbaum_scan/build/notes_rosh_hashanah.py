"""All notes from printed655–674; cross-page continuations joined once."""
from .notes_motzaei_shabbat import xml
from .rosh_hashanah import AMIDAH, KAPPAROT, TASHLIKH, URNS
from .rosh_hashanah_data import NOTES as READINGS

TARGETS = dict(URNS, rh_heading=AMIDAH, tashlikh=TASHLIKH,kapparot=KAPPAROT,
    benei_adam_psalm=URNS['benei_adam']+'/psalms/107/10',
    benei_adam_job=URNS['benei_adam']+'/job/33/23')
TARGETS.update({'psalm130_'+str(n):URNS['psalm130']+'/psalms/130/'+str(n) for n in (1,3,4,6)})
NOTES = [dict(target=TARGETS[r['key']],kind=r['kind'],lemma='',n='',paras=[dict(text=xml(r['text']))]) for r in READINGS]
