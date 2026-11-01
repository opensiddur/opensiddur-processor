"""Short and Monday/Thursday Tachanun; separate Kaddish and Torah introduction."""
import re
from html import escape

from .common import PRAYER, SIDDUR, PROJECT_HE, QUORUM, cond, endcond, feature, pb
from .tachanun_data import PASSAGES
from .milestones import Correspondences
from .tachanun_conditions import occasion, EL_EREKH_OCCASION

ROOT = SIDDUR + 'chol/shacharit/tachanun'
BIBLE = 'urn:x-opensiddur:text:bible:'
SIGIL = '1949 chol/shacharit/tachanun'
READER = '<tei:note type="instruction" xml:lang="en">Reader</tei:note>'
# Mixed biblical/liturgical paragraphs belong to the edition's service sequence.
AGGREGATES = {'vehu', 'hatteh', 'vaanachnu', 'psalm6'}
URNS = {key: (ROOT + '/' + key if key in AGGREGATES else PRAYER + 'tachanun/' + key)
        for key in PASSAGES}
URNS['vayomer'] = BIBLE + 'samuel_2/24/14'
URNS['ozrenu'] = BIBLE + 'psalms/79/9'
URNS['el_erekh_appayim'] = PRAYER + 'el_erekh_appayim'

OMISSIONS = ('Taḥanun is omitted on the following occasions: Rosh Ḥodesh, the entire month '
    'of Nisan, Lag b’Omer, the first eight days of Sivan, the 9th and 15th of Av, '
    'Erev Rosh Hashanah, from Erev Yom Kippur until the second day after Sukkoth, '
    'Ḥanukkah, the 15th of Shevat, the 14th and 15th of Adar and Adar Sheni. '
    'Taḥanun is also omitted in the house of a mourner during the week of mourning, '
    'and on the occasion of a Brith Milah.')
EL_RUBRIC = ('The following paragraph is said on Mondays and Thursdays, except on '
    'Rosh Ḥodesh, Erev Pesaḥ, Tish‘ah b’Av, Erev Yom Kippur, Ḥanukkah, '
    'the 14th and 15th of Adar and Adar Sheni.')
NEFILAH = ('vayomer', 'rachum', 'psalm6')
CLOSING = ('shomer_yisrael', 'shomer_goy_echad', 'shomer_goy_qadosh', 'mitratzeh', 'vaanachnu')
LONG_OPENING = ('vehu', 'hatteh', 'habbet_na', 'anna_melekh', 'el_rachum', 'ein_kamokha', 'hapoteach')
LONG_ENDING = ('adonai_elohei', 'habbet_mishamayim', 'uvekhol', 'zarim',
    'anna_shuv', 'chusah', 'anna_shuv', 'qolenu',
    'uvekhol', 'ozrenu', 'adonai_elohei')


def text_xml(value):
    return re.sub(r'\{pb:(\d+)\}', lambda m: pb(int(m[1]), sigil=SIGIL),
                  escape(value)).replace('{reader}', READER)


def prayers(lang):
    side = 0 if lang == 'he' else 1
    result = []
    for key, row in PASSAGES.items():
        urn = URNS[key]
        body = [f'<tei:div corresp="{urn}">']
        if key == 'psalm6':
            body.append(f'<tei:head xml:lang="{lang}">' + ('תהלים ו' if lang == 'he' else 'Psalm 6') + '</tei:head>')
            body.append('<tei:p>')
            for verse, he, en in row['verses']:
                body.append(f'<tei:milestone unit="verse" corresp="{BIBLE}psalms/6/{verse}"/>'
                            + text_xml(he if lang == 'he' else en))
            body.append('</tei:p>')
        elif 'chunks' in row:
            marks = Correspondences()
            body.append(f'<tei:p><tei:milestone unit="prayer" corresp="{urn}/text"/>')
            for chunk in row['chunks']:
                value = chunk[lang]
                source = f' source="{BIBLE}{chunk["source"]}"' if chunk['source'] else ''
                text = text_xml(value.removesuffix('{p}'))
                if source:
                    text = f'<tei:seg{source}>{text}</tei:seg>'
                body.append(marks.start(urn + '/' + chunk['anchor']) + text.rstrip())
                if value.endswith('{p}'):
                    body.append('</tei:p><tei:p>')
            body.append(marks.close() + '</tei:p>')
        else:
            # Milestones align the shared passage at each occurrence in both forms.
            marker = '' if urn.startswith(BIBLE) else f'<tei:milestone unit="prayer" corresp="{urn}/text"/>'
            for i, paragraph in enumerate(row[lang].split('{p}')):
                suffix = (f' <tei:seg source="{URNS["adonai_elohei"]}">'
                          + text_xml(PASSAGES['adonai_elohei'][lang]) + '</tei:seg>'
                          if key in ('uvekhol', 'anna_shuv') else '')
                body.append('<tei:p>' + (marker if i == 0 else '') + text_xml(paragraph) + suffix + '</tei:p>')
        body.append('</tei:div>')
        result.append(dict(name='tachanun_' + key if key != 'el_erekh_appayim' else key,
            title=('תהלים ו' if key == 'psalm6' else ' '.join(row.get('he', row.get('chunks', [{}])[0].get('he', '')).split()[:3])) if lang == 'he' else key.replace('_', ' ').capitalize(), urn=urn, body='\n'.join(body),
            first=row['first'] + side, last=row['last'] + side))
    return result


def transclude(key):
    return f'<j:transclude type="external" target="{URNS[key]}"/>'


def unit_body(project):
    from .build_he import declaration
    side = 0 if project == PROJECT_HE else 1
    parts = [f'<tei:div corresp="{ROOT}">', declaration(),
             f'<tei:head xml:lang="{"he" if side == 0 else "en"}">' + ('תַּחֲנוּן' if side == 0 else 'TAḤANUN') + '</tei:head>',
             pb(103 + side, sigil=SIGIL)]
    short_rubric = ('Except Mondays and Thursdays, the following Taḥanun is recited daily. '
        f'On Mondays and Thursdays, the long Taḥanun is said (pages {105 + side}–{117 + side}).')
    parts += [cond('tachanun_short', note=short_rubric + ' ' + OMISSIONS, fs=occasion()),
              f'<tei:milestone unit="section" corresp="{ROOT}/short"/>']
    for key in NEFILAH + CLOSING:
        if key == 'shomer_goy_echad':
            parts.append(pb(105 + side, sigil=SIGIL))
        parts.append(transclude(key))
    parts += [f'<tei:note type="instruction" xml:lang="en">The service is continued with '
              f'the Reader’s recital of the Kaddish on page {117 + side}.</tei:note>',
              endcond('tachanun_short'),
              cond('tachanun_long', note=f'The following is omitted during the occasions enumerated on page {103 + side}.',
                   fs=occasion(long=True)),
              '<tei:head xml:lang="en">TAḤANUN FOR MONDAYS AND THURSDAYS</tei:head>',
              pb(105 + side, sigil=SIGIL),
              f'<tei:milestone unit="section" corresp="{ROOT}/long/opening"/>']
    parts += [transclude(key) for key in LONG_OPENING]
    parts += [pb(113 + side, sigil=SIGIL),
              f'<tei:milestone unit="section" corresp="{ROOT}/long/nefilah"/>'] + [transclude(key) for key in NEFILAH]
    parts.append(f'<tei:milestone unit="section" corresp="{ROOT}/long/closing"/>')
    for i, key in enumerate(LONG_ENDING):
        if i == 2:
            parts.append(pb(115 + side, sigil=SIGIL))
        parts.append(transclude(key))
    for key in CLOSING:
        if key == 'shomer_goy_qadosh':
            parts.append(pb(117 + side, sigil=SIGIL))
        parts.append(transclude(key))
    parts += [endcond('tachanun_long'), '<j:endDeclare target="#unit_service"/>', '</tei:div>']
    return '\n'.join(parts)


def kaddish_body(project):
    page = 117 if project == PROJECT_HE else 118
    return '\n'.join([f'<tei:div corresp="{SIDDUR}chol/shacharit/kaddish_after_tachanun">',
        pb(page, sigil='1949 chol/shacharit/kaddish_after_tachanun'),
        cond('kaddish_after_tachanun_minyan', note='When a minyan holds service:',
             fs=feature(QUORUM, 'minyan'),
             note_resp='urn:x-opensiddur:contributor:opensiddur.org/efraim-feinstein'),
        f'<j:transclude type="external" target="{PRAYER}kaddish/chatzi"/>',
        endcond('kaddish_after_tachanun_minyan'), '</tei:div>'])


def torah_intro_body(project):
    from .build_he import declaration
    page = 117 if project == PROJECT_HE else 118
    return '\n'.join([f'<tei:div corresp="{SIDDUR}chol/shacharit/torah_intro">', declaration(),
        pb(page, sigil='1949 chol/shacharit/torah_intro'),
        cond('el_erekh_occasion', note=EL_RUBRIC, fs=EL_EREKH_OCCASION),
        transclude('el_erekh_appayim'), endcond('el_erekh_occasion'),
        '<j:endDeclare target="#unit_service"/>', '</tei:div>'])
