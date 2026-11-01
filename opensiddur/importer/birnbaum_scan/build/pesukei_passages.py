"""Biblical identifications and printed paragraph order for the pre-Ashrei passages."""
import re
from html import escape
from .common import SIDDUR, SIGIL_PESUKEI, pb
from .pesukei_data import PASSAGES
from .milestones import Correspondences

BIBLE = 'urn:x-opensiddur:text:bible:'
ROOT = SIDDUR + 'chol/shacharit/pesuqei_dezimrah/'
READER = '<tei:note type="instruction" xml:lang="en">Reader</tei:note>'
TITLES = {
    'hodu': ('הוֹדוּ', 'Hodu'),
    'romemu': ('רוֹמְמוּ', 'Exalt the Lord'),
    'vehu_rachum': ('וְהוּא רַחוּם', 'He, being merciful'),
    'hoshiah_et_ammekha': ('הוֹשִׁיעָה אֶת עַמֶּךָ', 'Save thy people'),
    'mizmor_letodah': ('מִזְמוֹר לְתוֹדָה', 'Psalm 100'),
    'yehi_khevod': ('יְהִי כְבוֹד', 'May the glory of the Lord'),
}
PAGES = {'hodu': (51, 53), 'romemu': (53, 53), 'vehu_rachum': (53, 55),
         'hoshiah_et_ammekha': (55, 55), 'mizmor_letodah': (55, 55), 'yehi_khevod': (55, 57)}


def prayers(lang):
    """One canonical definition per verse, retaining printed occurrence differences.

    Repeated occurrences point to the biblical verse with @source, rather than
    redefining its canonical URN. This preserves punctuation and pointing changes
    (I Chronicles 16:31 in English; Psalm 20:10 in Hebrew), and avoids the current
    parallel compiler's unclosed frames for inline transclusions in paragraphs.
    Reader instructions stay outside the reusable verse ranges.
    """
    result, seen = [], {}
    for name, rows in PASSAGES.items():
        urn = BIBLE + 'psalms/100' if name == 'mizmor_letodah' else ROOT + name
        body = [f'<tei:div corresp="{urn}">']
        if name == 'hodu':
            citation = 'דברי הימים א טז, ח–לו' if lang == 'he' else 'I Chronicles 16:8–36'
            body.append(f'<tei:head xml:lang="{lang}">{citation}</tei:head>')
        elif name == 'mizmor_letodah':
            citation = 'תהלים ק' if lang == 'he' else 'Psalm 100'
            body.append(f'<tei:head xml:lang="{lang}">{citation}</tei:head>')
        body.append('<tei:p>')
        marks = Correspondences()
        for ref, he, en in rows:
            text = he if lang == 'he' else en
            reader = text.startswith('{reader}')
            text = text.removeprefix('{reader}')
            if reader:
                body.append(marks.close() + READER)
            verse_urn = ROOT + 'yehi_khevod/' + ref.split(':')[1] if ref.startswith('siddur:') else BIBLE + ref
            attr = 'source' if verse_urn in seen else 'corresp'
            seen.setdefault(verse_urn, text)
            xml = re.sub(r'\{pb:(\d+)\}', lambda m: pb(int(m[1]), sigil=SIGIL_PESUKEI), escape(text))
            if name == 'mizmor_letodah' and lang == 'en' and ref.endswith('/1'):
                # The English gives the psalm superscription a paragraph of its own.
                xml = xml.replace('thank-offering. ', 'thank-offering.<tei:lb/>')
            if attr == 'source':
                body.append(marks.close() + f'<tei:seg source="{verse_urn}">{xml}</tei:seg>')
            else:
                body.append(marks.start(verse_urn) + xml)
        body += [marks.close(), '</tei:p>', '</tei:div>']
        first, last = PAGES[name]
        offset = 0 if lang == 'he' else 1
        result.append(dict(name=name, title=TITLES[name][offset], urn=urn,
                           first=first+offset, last=last+offset, body='\n'.join(body)))
    return result
