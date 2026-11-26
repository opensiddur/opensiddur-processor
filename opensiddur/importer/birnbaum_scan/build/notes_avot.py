"""Every printed Avot commentary paragraph and source citation, keyed by URN."""
import re

from .avot import READINGS, ROOT, records, reference, text_xml


def notes():
    grouped={}
    rows=records('he')
    for page,pair in READINGS.items():
        for entry in re.split(r'\n(?=[\w.]+\|)',pair['notes']):
            if not entry:continue
            key,lemma,text=entry.split('|',2)
            if key=='intro':target=ROOT
            elif key in ('opening','closing'):
                chapter=next(r['chapter'] for r in rows if r['page']==int(page) and r['key']==key)
                target=f'{ROOT}/{chapter}/{key}'
            else:target=reference(key)
            kind='source' if lemma=='cite' else 'commentary'
            group=grouped.setdefault((target,kind),dict(target=target,kind=kind,lemma='',n='',paras=[]))
            prefix='' if kind=='source' else '<tei:label xml:lang="he">'+text_xml(lemma)+'</tei:label> '
            for n,para in enumerate(text.split('\n\n')):
                group['paras'].append(dict(text=(prefix if n==0 else '')+text_xml(para)))
    return list(grouped.values())


NOTES=notes()
