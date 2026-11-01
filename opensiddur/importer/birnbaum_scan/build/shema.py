"""Shema and its weekday morning blessings, printed 71–82."""
import re
from html import escape
from .common import PRAYER, SIDDUR, SIGIL_SHEMA, pb, cond, endcond, feature, QUORUM
from .shema_data import ROWS
from .milestones import Correspondences

BIBLE = 'urn:x-opensiddur:text:bible:'
ORDER = ('barekhu', 'yotzer_or', 'ahavah_rabbah', 'shema', 'emet_veyatziv')
TITLES = [('בָּרְכוּ', 'Barekhu'), ('יוֹצֵר אוֹר', 'Yotzer or'),
          ('אַהֲבָה רַבָּה', 'Ahavah rabbah'), ('שְׁמַע', 'Shema'),
          ('אֱמֶת וְיַצִּיב', 'Emet veyatziv')]
PAGES = [(71, 71), (71, 73), (73, 75), (75, 77), (77, 81)]
CITATIONS = {'bible:deuteronomy/6/4': ('דברים ו, ד–ט', 'Deuteronomy 6:4–9'),
             'bible:deuteronomy/11/13': ('דברים יא, יג–כא', 'Deuteronomy 11:13–21'),
             'bible:numbers/15/37': ('במדבר טו, לז–מא', 'Numbers 15:37–41')}


def text_xml(text):
    value = re.sub(r'\{pb:(\d+)\}', lambda m: pb(int(m[1]), sigil=SIGIL_SHEMA), escape(text))
    for marker, label in [('reader', 'Reader'), ('reader_colon', 'Reader:'), ('congregation', 'Congregation and Reader:'), ('silent', 'Silent meditation:')]:
        value = value.replace('{'+marker+'}', f'<tei:note type="instruction" xml:lang="en">{label}</tei:note> ')
    return value.replace('{lb}', '<tei:lb/>')


def prayers(lang):
    side = 0 if lang == 'he' else 1
    groups = {name: [] for name in ORDER}
    current = 'barekhu'
    for ref, he, en in ROWS:
        if not ref.startswith('bible:'):
            current = ref.split('/')[0]
        groups[current].append((ref, (he, en)[side]))
    result = []
    for name, title, pages in zip(ORDER, TITLES, PAGES):
        parts = [f'<tei:div corresp="{PRAYER}{name}">']
        if name == 'shema':
            if lang == 'en':
                parts.append('<tei:head xml:lang="en">SHEMA</tei:head>')
            else:
                from .shacharit_end import editorial_head
                parts.append(editorial_head(lang, 'שְׁמַע', 'Shema'))
        scripture_open = False
        marks = Correspondences()
        for ref, text in groups[name]:
            # Consecutive Torah verses share one paragraph, as in the print.
            torah = ref.startswith(('bible:deuteronomy/', 'bible:numbers/'))
            new_para = ref in CITATIONS or ref == 'bible:deuteronomy/6/5' or (lang == 'he' and ref == 'bible:deuteronomy/11/21')
            if scripture_open and (not torah or new_para):
                parts.append(marks.close() + '</tei:p></tei:div>')
                scripture_open = False
            if torah:
                if not scripture_open:
                    parts.append('<tei:div>')
                    if ref in CITATIONS:
                        parts.append(f'<tei:head xml:lang="{lang}">{CITATIONS[ref][side]}</tei:head>')
                    parts.append('<tei:p>')
                    scripture_open = True
                parts.append(marks.start(BIBLE + ref[6:]) + text_xml(text) + ' ')
            elif ref.startswith('bible:'):
                # These Exodus verses already occur in the Song at the Sea.
                key = 'mi_khamokhah' if ref.endswith('/11') else 'adonai_yimlokh'
                parts.append(f'<tei:div corresp="{PRAYER}{name}/{key}"><tei:p><tei:seg source="{BIBLE}{ref[6:]}">{text_xml(text)}</tei:seg></tei:p></tei:div>')
            elif ref == 'shema/barukh_shem':
                parts.append(f'<tei:div corresp="{SIDDUR}chol/shacharit/shema/barukh_shem"><j:transclude type="external" target="{PRAYER}{ref}"/></tei:div>')
            else:
                if ref == "barekhu/call":
                    text = text.replace("{reader}", "{reader_colon}")
                value = text_xml(text)
                if ref == 'shema/el_melekh_neeman':
                    value = (cond('cond_shema_private', note='When praying in private, add:',
                                  fs=feature(QUORUM, 'minyan', '<tei:binary value="false"/>'))
                             + value + endcond('cond_shema_private'))
                # The two Kedushah responses quote only part of their Bible verse.
                quote = {'yotzer_or/qadosh': 'isaiah/6/3', 'yotzer_or/barukh_kevod': 'ezekiel/3/12'}.get(ref)
                if quote:
                    value = f'<tei:seg source="{BIBLE}{quote}">{value}</tei:seg>'
                parts.append(f'<tei:div corresp="{PRAYER}{ref}"><tei:p>{value}</tei:p></tei:div>')
        if scripture_open:
            parts.append(marks.close() + '</tei:p></tei:div>')
        parts.append('</tei:div>')
        result.append(dict(name=name, title=title[side], urn=PRAYER+name,
                           first=pages[0]+side, last=pages[1]+side, body=''.join(parts)))
    return result


def unit_body(project, by_name):
    from .build_he import declaration, _transclude
    lines = [f'<tei:div corresp="{SIDDUR}chol/shacharit/shema">', declaration()]
    for name in ORDER:
        _transclude(lines, by_name, name)
    return '\n'.join(lines + ['<j:endDeclare target="#unit_service"/>', '</tei:div>'])
