"""Seven printed commentary notes, with the Hashmonaim continuation joined once."""
from .hanukkah_purim import URNS, MAOZ, HASHMONAIM, ASHER
from .hanukkah_purim_data import NOTES as READINGS
from .notes_motzaei_shabbat import xml
TARGETS={'maoz':MAOZ,'hachashmonaim':HASHMONAIM,'asher':ASHER}
NOTES=[dict(target=TARGETS.get(r['key'],URNS.get(r['key'])),kind='commentary',lemma='',n='',paras=[dict(text=xml(r['text']))]) for r in READINGS]
