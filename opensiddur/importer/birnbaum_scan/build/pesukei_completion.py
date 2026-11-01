"""Ashrei through Half Kaddish, read from printed 57–70 (IA n81–n94)."""
import re
from html import escape
from .common import PRAYER, SIGIL_PESUKEI, pb
from .pesukei_passages import BIBLE, ROOT, READER
from .pesukei_data import PASSAGES as EARLIER
from .pesukei_completion_data import PASSAGES
from .milestones import Correspondences

ORDER = ('ashrei', 'psalm_146', 'psalm_147', 'psalm_148', 'psalm_149',
         'psalm_150', 'barukh_adonai', 'vayevarekh_david', 'attah_hu',
         'vayyosha', 'az_yashir', 'ki_ladonai', 'yishtabbach', 'kaddish_chatzi')
PAGES = {'ashrei': (57, 59), 'psalm_146': (59, 61), 'psalm_147': (61, 61),
         'psalm_148': (61, 63), 'psalm_149': (63, 63), 'psalm_150': (63, 65),
         'barukh_adonai': (65, 65), 'vayevarekh_david': (65, 65),
         'attah_hu': (65, 67), 'vayyosha': (67, 67), 'az_yashir': (67, 69),
         'ki_ladonai': (69, 69), 'yishtabbach': (69, 69), 'kaddish_chatzi': (69, 69)}
CITATIONS = {'psalm_145': ('תהלים קמה', 'Psalm 145'),
             'psalm_146': ('תהלים קמו', 'Psalm 146'),
             'psalm_147': ('תהלים קמז', 'Psalm 147'),
             'psalm_148': ('תהלים קמח', 'Psalm 148'),
             'psalm_149': ('תהלים קמט', 'Psalm 149'),
             'psalm_150': ('תהלים קנ', 'Psalm 150'),
             'vayevarekh_david': ('דברי הימים א כט, י–יג', 'I Chronicles 29:10–13'),
             'attah_hu': ('נחמיה ט, ו–יא', 'Nehemiah 9:6–11'),
             'vayyosha': ('שמות יד, ל–לא', 'Exodus 14:30–31'),
             'az_yashir': ('שמות טו, א–יח', 'Exodus 15:1–18')}
TITLES = {'ashrei': ('אַשְׁרֵי', 'Ashrei'), 'barukh_adonai': ('בָּרוּךְ יְיָ לְעוֹלָם', 'Blessed be the Lord'),
          'ki_ladonai': ('כִּי לַייָ הַמְּלוּכָה', 'For sovereignty is the Lord’s'),
          'yishtabbach': ('יִשְׁתַּבַּח', 'Yishtabach'),
          'kaddish_chatzi': ('חֲצִי קַדִּישׁ', 'Half Kaddish'), **CITATIONS}


def prayers(lang):
    offset = 0 if lang == 'he' else 1
    seen = {BIBLE + r[0] for rows in EARLIER.values() for r in rows if not r[0].startswith('siddur:')}

    def paragraph(name, enclosing=None):
        parts = ['<tei:p>']
        marks = Correspondences()
        for ref, he, en in PASSAGES[name]:
            value = he if lang == 'he' else en
            urn = PRAYER + ref[7:] if ref.startswith('prayer:') else BIBLE + ref
            if value.startswith('{reader}'):
                parts.append(marks.close() + READER)
                value = value.removeprefix('{reader}')
            xml = re.sub(r'\{pb:(\d+)\}', lambda m: pb(int(m[1]), sigil=SIGIL_PESUKEI), escape(value))
            if ref == 'psalms/145/2':
                xml = pb(129 + offset, sigil='1949 chol/shacharit/conclusion') + xml
            xml = xml.replace('{lb}', '<tei:lb/>').replace('{reader}', READER)
            if urn == enclosing:
                parts.append(marks.close() + xml)
            elif not value:
                parts.append('<!-- No corresponding repetition printed in English. -->')
            else:
                attr = 'source' if urn in seen else 'corresp'
                if attr == 'source':
                    parts.append(marks.close() + f'<tei:seg source="{urn}">{xml}</tei:seg>')
                else:
                    parts.append(marks.start(urn) + xml)
            seen.add(urn)
            parts.append('<tei:lb/>' if name == 'psalm_145' else ' ')
        parts.append(marks.close() + '</tei:p>')
        return ''.join(parts)

    def citation(name):
        return f'<tei:head xml:lang="{lang}">{CITATIONS[name][offset]}</tei:head>'

    result = []
    for name in ORDER:
        if name in ('ashrei', 'yishtabbach'):
            urn = PRAYER + name
        elif name == 'kaddish_chatzi':
            urn = PRAYER + 'kaddish/chatzi'
        elif name.startswith('psalm_') and name != 'psalm_150':
            urn = BIBLE + 'psalms/' + name[6:]
        else:
            urn = ROOT + name
        body = [f'<tei:div corresp="{urn}">']
        if name == 'ashrei':
            body += ['<tei:div>'+paragraph('ashrei_prefix')+'</tei:div>', f'<tei:div corresp="{BIBLE}psalms/145">',
                     citation('psalm_145'), paragraph('psalm_145'), '</tei:div>', '<tei:div>'+paragraph('ashrei_suffix')+'</tei:div>']
        elif name == 'psalm_150':
            body += [f'<tei:div corresp="{BIBLE}psalms/150">', citation(name), paragraph(name),
                     '</tei:div>', '<tei:div>'+paragraph('psalm_150_repeat')+'</tei:div>']
        elif name == 'kaddish_chatzi':
            body += ['<tei:note type="instruction" xml:lang="en">Reader:</tei:note>']
            body += [f'<j:transclude type="external" target="{PRAYER}kaddish/{part}"/>'
                     for part in ('yitgaddal', 'yehe_shemeh', 'yitbarakh')]
        else:
            if name in CITATIONS:
                body.append(citation(name))
            body.append(paragraph(name, urn))
            if name == 'az_yashir':
                body.append(paragraph('adonai_yimlokh_repeat'))
        body.append('</tei:div>')
        first, last = PAGES[name]
        result.append(dict(name=name, title=TITLES[name][offset], urn=urn,
                           first=first+offset, last=last+offset, printings=((127+offset,129+offset),) if name == "ashrei" else (), body='\n'.join(body)))
    return result
