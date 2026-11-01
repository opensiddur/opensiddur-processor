"""Weekday Torah service through the closing of the ark, before Ashrei."""
import re
from html import escape

from .common import (PRAYER, SIDDUR, PROJECT_HE, QUORUM, PERSON, AGG,
                     cond, endcond, feature, pb)
from .tachanun_conditions import MON_THU, holiday, occasion
from .avinu_malkenu import FAST
from .torah_data import PASSAGES
from .milestones import Correspondences

ROOT = SIDDUR + 'chol/shacharit/torah'
BIBLE = 'urn:x-opensiddur:text:bible:'
SIGIL = '1949 chol/shacharit/torah'
URNS = {key: ROOT + '/' + key for key in PASSAGES}
URNS.update({
    'berikh_shemeh': PRAYER + 'berikh_shemeh',
    'gaddelu': ROOT + '/gaddelu',
    'av_harachamim': PRAYER + 'av_harachamim/hu_yerachem',
    'veattem': BIBLE + 'deuteronomy/4/4',
    'asher_natan': PRAYER + 'birkhot_hatorah/asher_natan',
    'hagomel': PRAYER + 'birkat_hagomel',
    'yehi_ratzon': PRAYER + 'yehi_ratzon_milifnei_avinu',
    'psalm24': BIBLE + 'psalms/24',
})
READING_RUBRIC = ('The Torah is read on Mondays and Thursdays, Rosh Ḥodesh, '
    'Ḥol ha-Mo‘ed, Ḥanukkah, Purim, and on fast days.')
SUPPLICATION_RUBRIC = ('On Mondays and Thursdays (if Taḥanun has been said), '
    'before returning the Torah to the ark, the Reader recites:')
GOMEL_RUBRIC = 'One who has come safely through a dangerous experience recites:'
READING_DAYS = ('<j:any>' + MON_THU + holiday('rosh-hodesh', 2)
    + feature(AGG, 'chol-hamoed') + holiday('hanukkah', 8)
    + holiday('purim-observed') + FAST + '</j:any>')
# A known missing minyan or a known non-reading day must suppress the service,
# even when the other fact has not been supplied.
READING_OCCASION = ('<j:none>'
    + feature(QUORUM, 'minyan', '<tei:binary value="false"/>')
    + '<j:none>' + READING_DAYS + '</j:none></j:none>')

# These full verses have no earlier realization in this edition. Repeated or
# partial verses instead carry source= and a local alignment anchor, avoiding
# ambiguous duplicate URNs (notably Psalm 148, already in Pesukei de-Zimrah).
BIBLICAL_ANCHORS = {
    ('vayehi_binsoa', 'vayehi'),
    ('vetiggaleh', 'torat'), ('vetiggaleh', 'pikkudei'),
    ('vetiggaleh', 'oz'), ('vetiggaleh', 'hael'),
    ('vezot_hatorah', 'vezot'), ('vezot_hatorah', 'etz'),
    ('vezot_hatorah', 'derakheha'), ('vezot_hatorah', 'orekh'),
    ('vezot_hatorah', 'adonai_chafetz'),
    ('uvnucho', 'uvnucho'), ('uvnucho', 'kumah'), ('uvnucho', 'kohanekha'),
    ('uvnucho', 'baavur'), ('uvnucho', 'ki_leqach'), ('uvnucho', 'hashivenu'),
}


def anchor(key, name, source):
    if key in ('gaddelu', 'veattem'):
        return URNS[key]
    if key == 'psalm24' or (key, name) in BIBLICAL_ANCHORS:
        return BIBLE + source
    return URNS[key] + '/' + name


def instruction(text):
    return '<tei:note type="instruction" xml:lang="en">' + escape(text) + '</tei:note>'


def text_xml(value):
    value = re.sub(r'\{pb:(\d+)\}', lambda m: pb(int(m[1]), sigil=SIGIL), escape(value))
    return value.replace('{reader}', instruction('Reader') + ' ').replace(
        '{name_rubric}', instruction('the Reader names the first person called to the Torah'))


def prayers(lang):
    side = 0 if lang == 'he' else 1
    result = []
    for key, passage in PASSAGES.items():
        urn = URNS[key]
        parts = [f'<tei:div corresp="{urn}">']
        if key == 'berikh_shemeh':
            parts.append(f'<tei:head xml:lang="{lang}">' + ('זוהר, ויקהל' if side == 0 else 'Zohar, Wayyakhel') + '</tei:head>')
        if key == 'psalm24':
            parts.append(f'<tei:head xml:lang="{lang}">' + ('תהלים כד' if side == 0 else 'Psalm 24') + '</tei:head>')
        parts.append('<tei:p>')
        marks = Correspondences()
        for i, (name, source, he, en) in enumerate(passage['rows']):
            # Paragraphs and role changes follow the print; verse boundaries alone
            # do not introduce paragraphs in the prose Psalms or verse composites.
            new_para = ((key == 'berikh_shemeh' and side == 1 and i == 1)
                or (key == 'vayehi_binsoa' and name == 'barukh')
                or (key == 'vezot_hatorah' and name == 'etz')
                or (key in ('yehi_ratzon', 'barekhu', 'hagomel') and i > 0)
                or (key == 'yehalelu' and name == 'congregation'))
            if new_para:
                parts.append('</tei:p><tei:p>')
            if key in ('barekhu', 'hagomel') and name == 'response':
                parts.append(marks.close() + instruction('Congregation responds:'))
            if key == 'yehalelu' and name == 'congregation':
                parts.append(marks.close() + instruction('Congregation:'))
            ref = anchor(key, name, source)
            attributes = f' source="{BIBLE}{source}"' if source and not ref.startswith(BIBLE) else ''
            if key in ('barekhu', 'asher_bachar'):
                original = PRAYER + ('barekhu/' + name if key == 'barekhu' else 'birkhot_hatorah/asher_bachar')
                attributes = f' source="{original}"'
            value = text_xml((he, en)[side])
            if key in ('gaddelu', 'veattem'):
                parts.append(f'<tei:seg{attributes}>{value}</tei:seg>' if attributes else value)
            else:
                if attributes:
                    value = f'<tei:seg{attributes}>{value}</tei:seg>'
                parts.append(marks.start(ref) + value)
        parts += [marks.close(), '</tei:p>', '</tei:div>']
        title = ' '.join(passage['rows'][0][2].split()[:3]) if side == 0 else key.replace('_', ' ').capitalize()
        result.append(dict(name='torah_' + key, title=title, urn=urn,
            first=passage['first'] + side, last=passage['last'] + side,
            body='\n'.join(parts)))
    return result


def transclude(key):
    return f'<j:transclude type="external" target="{URNS[key]}"/>'


def unit_body(project):
    from .build_he import declaration
    side = 0 if project == PROJECT_HE else 1
    lang = 'he' if side == 0 else 'en'
    parts = [f'<tei:div corresp="{ROOT}">', declaration(),
        cond('torah_reading_day', note=READING_RUBRIC, fs=READING_OCCASION),
        pb(119 + side, sigil=SIGIL),
        f'<tei:head xml:lang="{lang}">' + ('קְרִיאַת הַתּוֹרָה' if side == 0 else 'READING OF THE TORAH') + '</tei:head>',
        instruction('The ark is opened.'), instruction('Reader and Congregation:'),
        transclude('vayehi_binsoa'), transclude('berikh_shemeh'),
        instruction('The Reader takes the Torah and says:'), transclude('gaddelu'),
        instruction('Congregation:'), transclude('lekha_adonai'), transclude('av_harachamim'),
        instruction('The Torah is placed on the desk. The Reader unrolls it and says:'),
        transclude('vetiggaleh'), instruction('Congregation and Reader:'), transclude('veattem'),
        pb(123 + side, sigil=SIGIL), instruction('The person called to the Torah recites:'),
        transclude('barekhu'), instruction('He repeats the response and continues:'),
        transclude('asher_bachar'), instruction('The Torah is read. Then he recites:'),
        transclude('asher_natan'),
        cond('torah_hagomel', note=GOMEL_RUBRIC, fs=feature(PERSON, 'birkat-hagomel')),
        f'<tei:head xml:lang="{lang}">' + ('בִּרְכַת הַגּוֹמֵל' if side == 0 else 'THANKSGIVING') + '</tei:head>',
        transclude('hagomel'), endcond('torah_hagomel'),
        instruction('When the reading of the Torah is concluded, the Reader recites:'),
        f'<j:transclude type="external" target="{PRAYER}kaddish/chatzi"/>',
        pb(125 + side, sigil=SIGIL),
        instruction('When the Torah is raised, the Congregation recites:'),
        transclude('vezot_hatorah'),
        cond('torah_supplications', note=SUPPLICATION_RUBRIC, fs=occasion(long=True)),
        transclude('yehi_ratzon'), endcond('torah_supplications'),
        instruction('The Reader takes the Torah and says:'), transclude('yehalelu'),
        transclude('psalm24'), instruction('While the Torah is being placed in the ark:'),
        transclude('uvnucho'), instruction('The ark is closed. The morning service continues.'),
        endcond('torah_reading_day'), '<j:endDeclare target="#unit_service"/>', '</tei:div>']
    return '\n'.join(parts)
