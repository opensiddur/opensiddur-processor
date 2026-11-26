"""Editorial replacements for navigational page numbers in Birnbaum's rubrics.

The original readings remain in the transcription data. Generated TEI addresses
passages by edition-qualified URN; the exporter supplies the typeset page number.
"""
import re

PREFIX = 'urn:x-opensiddur:text:'
# Printed Hebrew page -> the passage the instruction actually names. The facing
# English instruction usually adds one, even where its target page was misprinted.
TARGETS = {
    299: 'siddur:shabbat/shacharit/opening',
    759: 'prayer:birkat_hamazon/zimmun/nevarekh',
    767: 'prayer:birkat_hamazon/harachaman/self',
    103: 'siddur:chol/shacharit/tachanun',
    733: 'bible:psalms/23',
    637: 'prayer:sefirat_haomer/counting',
    537: 'siddur:shabbat/conclusion/after_amidah',
    535: 'siddur:shabbat/conclusion/opening',
    93: 'prayer:amidah/birkat_kohanim',
    95: 'prayer:amidah/shalom/sim_shalom',
    565: 'prayer:hallel/blessing',
    575: 'siddur:rosh_chodesh/musaf',
    609: 'siddur:regalim/musaf',
    105: 'siddur:chol/shacharit/tachanun/long/opening',
    117: 'siddur:chol/shacharit/kaddish_after_tachanun',
    119: 'siddur:chol/shacharit/torah',
    127: 'siddur:chol/shacharit/conclusion',
    361: 'siddur:shabbat/shacharit/torah',
    213: 'siddur:chol/arvit/conclusion',
    191: 'siddur:chol/arvit/blessings_before_shema',
    465: 'bible:psalms/104',
    135: 'siddur:chol/shacharit/conclusion/aleinu',
    585: 'siddur:regalim/amidah',
    257: 'siddur:shabbat/arvit',
    341: 'prayer:yotzer_or/titbarakh',
    365: 'prayer:shema/torah_procession',
    405: 'siddur:shabbat/musaf/kaddish',
}
NOTE = re.compile(r'(<tei:note\b[^>]*\btype="(?:instruction|description)"[^>]*>)(.*?)(</tei:note>)', re.S)
PAGE = re.compile(r'(\bpages?\s+)(\d+)(?:[–-](\d+))?', re.I)


def dynamic_instructions(text, project):
    """Replace only rubrics (instructions and descriptions), leaving bibliographic citations
    untouched."""
    # The English facing page is one lower; a project's last field is its language.
    side = int(project.endswith('-en'))

    def ref(urn):
        return f'<tei:ref type="page" target="{PREFIX}{urn}@{project}"/>'

    def instruction(match):
        content = match[2]
        if 'type="page"' in content or not PAGE.search(content):
            return match[0]
        # Sentences/semicolon clauses can disappear independently without losing
        # unrelated directions (notably the long list of Taḥanun omissions).
        content = content.replace('; for Ḥol', '. Musaf for Ḥol')
        content = content.replace('; ', '. ')
        parts = re.split(r'(?<=\.)\s+', content)
        result = []
        for part in parts:
            if not PAGE.search(part):
                result.append(part)
                continue

            def replace(m, part=part):
                number = int(m[2]) - side
                if m[3] and m[2] == '11':
                    # The preliminary service runs from Adon Olam to Rabbi Ishmael.
                    return m[1] + ref('poem:adon_olam') + '–' + ref('prayer:kaddish/derabbanan/oseh_shalom')
                if int(m[2]) == 405:
                    number = 405
                target = TARGETS[number]
                if 'continue with Musaf' in part:
                    target = 'siddur:regalim/musaf'
                if 'Thou sustainest' in part or 'מכלכל חיים' in part:
                    target = 'siddur:regalim/musaf/text/mekhalkel'
                replacement = m[1] + ref(target)
                if m[3]:
                    replacement += '–' + ref('siddur:chol/shacharit/tachanun/long/closing')
                return replacement

            part = PAGE.sub(replace, part)
            result.append('<tei:seg type="optional-page-reference">' + part + '</tei:seg>')
        return match[1] + ' '.join(result) + match[3]

    return NOTE.sub(instruction, text)
