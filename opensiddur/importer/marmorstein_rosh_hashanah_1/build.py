"""Build source witnesses and the expanded mahzor from image readings.

Unreviewed material requires --draft and is visibly labeled as such. Missing
English witnesses produce no English file and never acquire substitute words.
"""
import argparse
import json
import re
from copy import deepcopy
from pathlib import Path

from lxml import etree
import yaml

from opensiddur.common.constants import PROJECT_DIRECTORY, SOURCETEXTS_ROOT
from opensiddur.common.urn_registry import load_registry, parse_urn
from opensiddur.importer.scan.authoring import (
    TEI, J, XML, element, mixed_words, append_words, write_documents, apply_corrections,
)
from opensiddur.importer.scan.navigation import append_instruction
from opensiddur.importer.scan.review import review_is_current
from opensiddur.importer.util.internet_archive import page_image_url, write_if_changed
from opensiddur.importer.util.validation import validate
from . import BOOK, IDENTIFIER, PROJECTS, EXPANDED, ROOT_URN, EXPANDED_URN

FRONT_KINDS = ('cover', 'title', 'copyright', 'preface')
ROLE_LABELS = {'reader': 'חזן', 'congregation': 'קהל',
               'reader_and_congregation': 'קהל וחזן'}


def document(lang, project, title, urn, *, index=False, draft=False):
    root = etree.Element(f'{{{TEI}}}TEI', nsmap={'tei': TEI, 'j': J}, attrib={XML+'lang': lang})
    desc = element(element(root, 'teiHeader'), 'fileDesc')
    titles = element(desc, 'titleStmt')
    element(titles, 'title', title, type='main')
    responsibility = element(titles, 'respStmt')
    element(responsibility, 'resp', 'AI-assisted scan reading and JLPTEI encoding', key='trc')
    element(responsibility, 'name', 'Codex', ref='urn:x-opensiddur:contributor:opensiddur.org/codex')
    edition = element(desc, 'editionStmt')
    element(edition, 'edition', ('DRAFT: independent adjudication pending. ' if draft else '')
            + 'Digitization in progress. Independent image readings and '
              'adjudications are recorded in sources/marmorstein_rosh_hashanah_1/.')
    publication = element(desc, 'publicationStmt')
    element(element(publication, 'distributor'), 'ref', 'Open Siddur Project', target='https://opensiddur.org')
    element(publication, 'idno', urn+'@'+project, type='urn')
    availability = element(publication, 'availability', status='free')
    element(availability, 'licence', 'CC0 1.0 Universal', target='https://creativecommons.org/publicdomain/zero/1.0/')
    source = element(desc, 'sourceDesc')
    if index:
        bibl = element(source, 'bibl')
        bibl.set(XML+'id', 'project_source_bibl')
        element(bibl, 'title', 'Prayerbook for the New Year [First Day]')
        element(bibl, 'editor', 'Wolf Heidenheim', role='arranger')
        element(bibl, 'editor', 'Jenny Marmorstein', role='translator')
        element(bibl, 'publisher', 'Victor Goldschmidt Publishers')
        element(bibl, 'pubPlace', 'Basle')
        element(bibl, 'date', '1965', when='1965')
        element(bibl, 'idno', f'https://archive.org/details/{IDENTIFIER}', type='url')
        element(bibl, 'idno', IDENTIFIER, type='internet_archive')
        element(bibl, 'date', '2026-11-08', type='accessed', when='2026-11-08')
        element(bibl, 'ref', 'Open Siddur source record', target='https://opensiddur.org/?p=69112')
        element(bibl, 'note', 'Digital imaging and document preparation: Aharon N. Varady; '
                'copy held by the HUC-JIR Klau Library, Cincinnati. The scan is the source. '
                'Independent reader: Claude Opus 5.5; CLI configured for medium reasoning. '
                'No translations have been supplied for passages absent from the English edition.')
    else:
        element(element(source, 'bibl'), 'ptr', target=f'/{project}/index#project_source_bibl')
    return root, element(element(root, 'text'), 'body')


def words(parent, text, lang):
    if lang == 'en':
        mixed_words(parent, text)
    else:
        # Preserve the source spelling/pointing, including its abbreviated Name.
        end = 0
        # Maqaf and sof pasuq are boundaries, despite sharing the Hebrew block.
        points = r'[\u0591-\u05bd\u05bf\u05c1\u05c2\u05c4\u05c5\u05c7]'
        letters_and_points = r'[\u05d0-\u05ea\u0591-\u05bd\u05bf\u05c1\u05c2\u05c4\u05c5\u05c7]'
        name = rf'([ובלמכש]?{points}*)(י{points}*(?:י{points}*|ה{points}*ו{points}*ה{points}*))'
        for match in re.finditer(r'(?<!'+letters_and_points+')'+name+'(?!'+letters_and_points+')', text):
            append_words(parent, text[end:match.start()]+match[1])
            element(parent, 'j:divineName', match[2])
            end = match.end()
        append_words(parent, text[end:])


def rubric_words(parent, rubric, lang):
    """Keep source abbreviations selectable without losing their printed form."""
    if isinstance(rubric, str):
        words(parent, rubric, lang)
        return
    text = rubric['text']
    if rubric.get('language_spans') and rubric.get('abbreviations'):
        raise ValueError('Overlapping abbreviation and language-span interpretation is not supported')
    for span in rubric.get('language_spans', []):
        before, found, text = text.partition(span['text'])
        if not found:
            raise ValueError('Language span missing from its source text')
        words(parent, before, lang)
        foreign = element(parent, 'foreign')
        foreign.set(XML+'lang', span['language'])
        words(foreign, span['text'], span['language'])
    for abbreviation in rubric.get('abbreviations', []):
        before, found, text = text.partition(abbreviation['abbr'])
        if not found:
            raise ValueError('Rubric abbreviation missing from its source text')
        words(parent, before, lang)
        choice = element(parent, 'choice')
        element(choice, 'abbr', abbreviation['abbr'])
        element(choice, 'expan', abbreviation['expan'])
    words(parent, text, lang)
    for uncertain in rubric.get('uncertain_characters', []):
        word, character = uncertain['word'], uncertain['character']
        if len(character) != 1 or word.count(character) != 1:
            raise ValueError('An uncertain character must occur once in its source word')
        matches = [(node, field, value)
                   for node in parent.iter() for field in ('text', 'tail')
                   if (node is not parent or field == 'text')
                   and (value := getattr(node, field)) and word in value]
        if len(matches) != 1 or matches[0][2].count(word) != 1:
            raise ValueError('Uncertain source word is missing or ambiguous')
        node, field, value = matches[0]
        offset = value.index(word) + word.index(character)
        glyph = etree.Element('{'+TEI+'}c', cert='low')
        glyph.text, glyph.tail = character, value[offset+1:]
        setattr(node, field, value[:offset])
        if field == 'text':
            node.insert(0, glyph)
        else:
            container = node.getparent()
            container.insert(container.index(node)+1, glyph)


def instruction_review_text(instruction):
    parts = [instruction['text']]
    parts.extend(a['abbr']+' ['+a['expan']+']' for a in instruction.get('abbreviations', []))
    parts.extend(span['text']+' ['+span['language']+']'
                 for span in instruction.get('language_spans', []))
    parts.extend(item['word']+' [uncertain '+item['character']+'; cert=low]'
                 for item in instruction.get('uncertain_characters', []))
    return ' '.join(parts)


def unit_urn(unit):
    """Name the actual excerpt rather than its containing chapter."""
    if unit.get('publication_context'):
        return unit['publication_context']
    target = unit.get('start', unit['urn'])
    if unit.get('end'):
        if target.partition('/')[0] != unit['end'].partition('/')[0]:
            raise ValueError('A documentary unit cannot span different works')
        target += '-/'+unit['end'].partition('/')[2]
    return target


def unit_instructions(unit, lang):
    return [note for note in unit.get('instructions', [])
            if lang in note.get('witnesses', [lang])]


def unit_document(unit, lang, draft):
    project = PROJECTS[lang]
    root, body = document(lang, project, unit['title'][lang], unit_urn(unit), draft=draft)
    if unit.get('publication_context'):
        body = element(body, 'div', corresp=unit['publication_context'])
    biblical_root = ':bible:' in unit['urn']
    reuse = unit.get('reuse', {}).get(lang)
    div = element(body, 'div', **({'corresp': unit['urn']} if not reuse and unit.get('map_root', not biblical_root) else {}))
    opening = unit['languages'][lang][0]['fragments'][0]
    div.set('facs', page_image_url(IDENTIFIER, int(opening['scan'][1:])-1, size=''))
    last = unit['languages'][lang][-1]['fragments'][-1]
    if opening.get('printed_page') is not None and last.get('printed_page') is not None:
        element(root.find(f'.//{{{TEI}}}sourceDesc/{{{TEI}}}bibl'), 'biblScope',
                unit='pages', **{'from': opening['printed_page'], 'to': last['printed_page']})
    if reuse:
        # A documentary occurrence can reuse an identical earlier witness
        # without registering the canonical prayer a second time.
        element(element(div, 'p'), 'j:transclude', type='inline', target=reuse+'@'+project)
        return root
    conditions = unit.get('conditions', [])
    if conditions:
        conditional = element(div, 'j:conditional')
        conditional.set(XML+'id', unit['stem']+'_condition')
        feature_structures(element(conditional, 'j:all'), conditions)
    current_page = None
    if unit.get('head', {}).get(lang):
        opening = unit['languages'][lang][0]['fragments'][0]
        element(div, 'pb', ed='1965', n=opening['printed_page'],
                facs=page_image_url(IDENTIFIER, int(opening['scan'][1:])-1, size=''))
        current_page = opening['scan']
        element(div, 'head', unit['head'][lang]).set(XML+'lang', lang)
    for instruction in unit_instructions(unit, lang):
        if instruction.get('placement') == 'condition' and not conditions:
            raise ValueError('A condition rubric requires a condition')
        parent = conditional if instruction.get('placement') == 'condition' else div
        note = element(parent, 'note', type=instruction.get('type', 'instruction'))
        if parent is not div:
            parent.remove(note)
            parent.insert(len(parent)-1, note)
        note.set(XML+'lang', instruction['language'])
        rubric_words(note, instruction, instruction['language'])
    citations = unit.get('citations', {}).get(lang, [])
    if citations:
        notes = element(root, 'standOff', type='notes')
        root.remove(notes)
        root.insert(list(root).index(body.getparent()), notes)
        passage_scans = {fragment['scan'] for segment in unit['languages'][lang]
                         for fragment in segment['fragments']}
        for citation in citations:
            if citation['scan'] not in passage_scans:
                raise ValueError('Citation scan is outside the passage')
            note = element(notes, 'note', type=citation.get('note_type', 'citation'),
                           target=citation.get('target', unit.get('start', unit['urn'])))
            citation_text = citation['text'].strip()
            if citation_text.startswith('(') and citation_text.endswith(')'):
                citation_text = citation_text[1:-1].strip()
            paragraph = element(note, 'p')
            if citation.get('reference'):
                element(paragraph, 'ref', citation_text, target=citation['reference'])
            elif citation.get('text_type'):
                element(paragraph, 'seg', citation_text, type=citation['text_type'])
            else:
                paragraph.text = citation_text
    paragraph = None
    current_paragraph = None
    current_chapter = None
    seen_chapters = set()
    active_reference = None
    line_group = None
    poetry = unit.get('poetry', {}).get(lang, False)

    def close_references():
        nonlocal active_reference, current_chapter
        if active_reference:
            element(paragraph, 'milestone', unit=active_reference)
            active_reference = None
        if current_chapter:
            element(paragraph, 'milestone', unit='chapter')
            current_chapter = None

    for segment_index, segment in enumerate(unit['languages'][lang]):
        if segment.get('transclude'):
            if paragraph is not None:
                close_references()
            element(div, 'j:transclude', type='external', target=segment['transclude']+'@'+project)
            paragraph = current_paragraph = None
            line_group = None
            continue
        identity = segment.get('paragraph', 1)
        text_language = segment.get('language', lang)
        if paragraph is None or identity != current_paragraph:
            if poetry and line_group is None:
                line_group = element(div, 'lg')
            paragraph = element(line_group if poetry else div, 'l' if poetry else 'p')
            if text_language != lang:
                paragraph.set(XML+'lang', text_language)
            current_paragraph = identity
        segment_conditions = segment.get('conditions', [])
        if segment_conditions:
            # Conditions select words within a printed paragraph. Keep the
            # matching end marker in that paragraph, including continuations.
            segment_condition_id = unit['stem']+'_segment_'+str(segment_index)
            condition = element(paragraph, 'j:conditional', **({'type': 'marked'} if segment.get('marked') else {}))
            condition.set(XML+'id', segment_condition_id)
            if segment.get('condition_instruction'):
                note = element(condition, 'note', type='instruction')
                note.set(XML+'lang', lang)
                words(note, segment['condition_instruction'], lang)
            feature_structures(element(condition, 'j:all'), segment_conditions)
        fragments = segment['fragments']
        if segment.get('marked'):
            if not segment_conditions or not fragments[0]['text'].startswith('(') or not fragments[-1]['text'].endswith(')'):
                raise ValueError('Marked source condition requires paired source parentheses')
            fragments = deepcopy(fragments)
            fragments[0]['text'] = fragments[0]['text'][1:]
            fragments[-1]['text'] = fragments[-1]['text'][:-1]
        for index, fragment in enumerate(fragments):
            if fragment['scan'] != current_page:
                attributes = {'ed': '1965', 'facs': page_image_url(IDENTIFIER, int(fragment['scan'][1:])-1, size='')}
                if fragment.get('printed_page') is not None:
                    attributes['n'] = fragment['printed_page']
                if fragment.get('page_start', True):
                    element(paragraph, 'pb', **attributes)
                current_page = fragment['scan']
            if index == 0 and segment.get('edition_label'):
                close_references()
                if not segment.get('edition_label_in_reference'):
                    element(paragraph, 'label', segment['edition_label'])
                    append_words(paragraph, ' ')
            if index == 0:
                for instruction in segment.get('instructions', []):
                    note = element(paragraph, 'note', type=instruction.get('type', 'instruction'))
                    note.set(XML+'lang', instruction.get('language', lang))
                    rubric_words(note, instruction, instruction.get('language', lang))
            for instruction in fragment.get('instructions', []):
                note = element(paragraph, 'note', type=instruction.get('type', 'description'))
                note.set(XML+'lang', instruction.get('language', lang))
                rubric_words(note, instruction, instruction.get('language', lang))
            reference_marker = None
            if index == 0 and segment.get('speaker_before_reference') and segment.get('speaker') and active_reference:
                element(paragraph, 'milestone', unit=active_reference)
                active_reference = None
            if index == 0 and segment.get('corresp'):
                urn = segment['corresp']
                biblical = ':bible:' in urn
                if biblical:
                    parts = urn.split(':')[-1].split('/')
                    chapter = urn.rsplit('/', len(parts)-2)[0]
                    if chapter != current_chapter:
                        close_references()
                        attributes = {'unit': 'chapter', 'n': parts[1]}
                        # Excerpted chapters supply context, not a substitute
                        # witness for the whole chapter.
                        if chapter not in seen_chapters and ((chapter == unit['urn'] and not unit.get('start')) or chapter in unit.get('complete_chapters', [])):
                            attributes['corresp'] = chapter
                            seen_chapters.add(chapter)
                        element(paragraph, 'milestone', **attributes)
                        current_chapter = chapter
                    reference_unit = ('verse' if len(parts) == 3 else
                                      'half-verse' if parts[-1] in ('a', 'b') else 'verse-part')
                    attributes = {'n': parts[-1]}
                else:
                    reference_unit, attributes = segment.get('reference_unit', 'prayer-part'), {}
                    quoted_source = segment.get('source', '')
                    if reference_unit == 'verse' and ':bible:' in quoted_source:
                        parts = quoted_source.rsplit(':', 1)[-1].split('/')
                        chapter = quoted_source.rsplit('/', 1)[0]
                        if chapter != current_chapter:
                            close_references()
                            element(paragraph, 'milestone', unit='chapter', n=parts[1])
                            current_chapter = chapter
                        attributes = {'n': parts[-1]}
                    elif current_chapter:
                        close_references()
                if active_reference and active_reference != reference_unit:
                    element(paragraph, 'milestone', unit=active_reference)
                reference_marker = element(paragraph, 'milestone', unit=reference_unit, corresp=urn, **attributes)
                active_reference = reference_unit
            if index == 0 and segment.get('edition_label_in_reference'):
                if not segment.get('edition_label') or not segment.get('corresp'):
                    raise ValueError('A referenced edition label needs its text and correspondence')
                element(paragraph, 'label', segment['edition_label'])
                append_words(paragraph, ' ')
            if index == 0 and segment.get('speaker'):
                speaker = segment['speaker']
                if 'label' in speaker:
                    role = speaker['role']
                    if role not in ROLE_LABELS:
                        raise ValueError(f'Unknown speaker role: {role}')
                else:
                    expansion = speaker['expan']
                    try:
                        roles = {label: role for role, label in ROLE_LABELS.items()}
                        roles['חזן וקהל'] = 'reader_and_congregation'
                        role = roles[expansion]
                    except KeyError:
                        raise ValueError(f'Unknown speaker expansion: {expansion}') from None
                identity = 'urn:x-opensiddur:instruction:role/'+role
                description = element(paragraph, 'note', type='description', corresp=identity)
                description.set(XML+'lang', speaker.get('language', 'he'))
                if 'label' in speaker:
                    words(description, speaker['label'], speaker.get('language', 'he'))
                else:
                    choice = element(description, 'choice')
                    element(choice, 'abbr', speaker['abbr'])
                    element(choice, 'expan', speaker['expan'])
                append_words(paragraph, ' ')
                if segment.get('speaker_before_reference') and reference_marker is not None:
                    paragraph.remove(description)
                    paragraph.insert(paragraph.index(reference_marker), description)
            if segment.get('repeat'):
                # Repeated recitation reuses the witness; it does not define a
                # second element with the same canonical identity in one file.
                close_references()
                element(paragraph, 'j:transclude', type='inline', target=segment['repeat']+'@'+project)
                append_words(paragraph, ' ')
                continue
            source_reference = segment.get('source_reference')
            if source_reference and index == 0:
                book, chapter, verse = source_reference.rsplit(':', 1)[-1].split('/')
                element(paragraph, 'milestone', unit='chapter', n=chapter)
                element(paragraph, 'milestone', unit='verse', n=verse, corresp=source_reference)
            content = paragraph
            if segment.get('source'):
                attributes = {'source': segment['source']}
                if segment.get('source_type'):
                    attributes['type'] = segment['source_type']
                content = element(paragraph, 'seg', **attributes)
            if fragment.get('text_type'):
                content = element(content, 'seg', type=fragment['text_type'])
            if fragment.get('expansion'):
                choice = element(content, 'choice')
                abbreviation = element(choice, 'abbr')
                if fragment.get('divine_name_tail'):
                    start = fragment['text'].rindex('י')
                    append_words(abbreviation, fragment['text'][:start])
                    element(abbreviation, 'j:divineName', fragment['text'][start:])
                else:
                    words(abbreviation, fragment['text'], lang)
                words(element(choice, 'expan'), fragment['expansion'], lang)
            elif fragment.get('abbreviations'):
                rubric_words(content, fragment, text_language)
            elif fragment.get('enlarged_letters'):
                letters = fragment['enlarged_letters']
                if any(len(letter) != 1 or fragment['text'].count(letter) != 1 for letter in letters):
                    raise ValueError('Each enlarged letter must identify one source character')
                for part in re.split('(['+re.escape(''.join(letters))+'])', fragment['text']):
                    if part in letters:
                        element(content, 'c', part, rend='large')
                    else:
                        words(content, part, text_language)
            else:
                words(content, fragment['text'], text_language)
            if source_reference and index == len(segment['fragments']) - 1:
                element(paragraph, 'milestone', unit='verse')
                element(paragraph, 'milestone', unit='chapter')
            if not fragment.get('join_next') and not fragment['text'].rstrip().endswith('־'):
                append_words(paragraph, ' ')
        if segment_conditions:
            element(paragraph, 'j:endConditional', target='#'+segment_condition_id)
        if segment.get('repeat_cue'):
            close_references()
            cue = segment['repeat_cue']
            note = element(paragraph, 'note', type='instruction')
            note.set(XML+'lang', lang)
            element(note, 'ref', cue['text'], target=cue['target']+'@'+project)
    if paragraph is not None:
        close_references()
    if conditions:
        element(div, 'j:endConditional', target='#'+unit['stem']+'_condition')
    return root


def unit_text(unit, lang):
    return ' '.join(fragment['text'] for segment in unit['languages'][lang] for fragment in segment['fragments'])


def unit_review_text(unit, lang):
    # This is a review payload, not printed prayer text. Include both the
    # source abbreviation and its interpretation so either change needs review.
    parts = ([unit['head'][lang]] if unit.get('head', {}).get(lang) else [])
    parts.extend(instruction['text'] for instruction in unit_instructions(unit, lang))
    for instruction in unit_instructions(unit, lang):
        parts.extend(a['abbr']+' ['+a['expan']+']' for a in instruction.get('abbreviations', []))
        parts.extend(span['text']+' ['+span['language']+']'
                     for span in instruction.get('language_spans', []))
    for segment in unit['languages'][lang]:
        if segment.get('edition_label'):
            parts.append(segment['edition_label'])
        for instruction in segment.get('instructions', []):
            parts.append(instruction_review_text(instruction))
        if segment.get('condition_instruction'):
            parts.append(segment['condition_instruction'])
        if segment.get('speaker'):
            speaker = segment['speaker']
            parts.append(speaker['label']+' ['+speaker['role']+']' if 'label' in speaker else
                         speaker['abbr']+' ['+speaker['expan']+']')
        for fragment in segment['fragments']:
            parts.extend(instruction_review_text(instruction)
                         for instruction in fragment.get('instructions', []))
            parts.append(fragment['text'])
            if fragment.get('text_type'):
                parts.append('['+fragment['text_type']+']')
            if fragment.get('expansion'):
                parts.append('['+fragment['expansion']+']')
            parts.extend(a['abbr']+' ['+a['expan']+']' for a in fragment.get('abbreviations', []))
        if segment.get('repeat_cue'):
            cue = segment['repeat_cue']
            parts.append(cue['text']+' ['+cue['target']+']')
    return ' '.join(parts)


def reference(unit):
    return {'target': unit.get('start', unit['urn']),
            **({'targetEnd': unit['end']} if unit.get('end') else {})}


def feature_structures(parent, structures):
    for structure in structures:
        if 'operator' in structure:
            if structure['operator'] not in ('all', 'any', 'none', 'one'):
                raise ValueError('Unknown condition operator')
            feature_structures(element(parent, 'j:'+structure['operator']), structure['conditions'])
            continue
        features = element(parent, 'fs', type=structure['type'])
        for name, value in structure['features'].items():
            feature = element(features, 'f')
            feature.set('name', name)
            kind = ('binary' if isinstance(value, bool) else
                    'symbol' if isinstance(value, str) else 'numeric')
            element(feature, kind,
                    value=str(value).lower() if isinstance(value, bool) else str(value))


def expanded_order(parent, order, readings, by_stem):
    """Keep service choices local while sharing one sequence across languages."""
    for occurrence in order:
        if 'section' in occurrence:
            outer = element(parent, 'div')
            identifier = 'section_'+occurrence['section']
            outer.set(XML+'id', identifier)
            conditions = occurrence.get('conditions', [])
            if conditions:
                conditional = element(outer, 'j:conditional')
                conditional.set(XML+'id', identifier+'_condition')
                if occurrence.get('condition_rubrics'):
                    rubric = element(conditional, 'note', type='instruction')
                    for language, text in occurrence['condition_rubrics'].items():
                        part = element(rubric, 'foreign')
                        part.set(XML+'lang', language)
                        rubric_words(part, text, language)
                        append_words(rubric, ' ')
                all_conditions = element(conditional, 'j:all')
                feature_structures(all_conditions, conditions)
            content = element(outer, 'div')
            for language, heading in occurrence.get('heads', {}).items():
                element(content, 'head', heading).set(XML+'lang', language)
            if occurrence.get('role'):
                role = occurrence['role']
                try:
                    label = ROLE_LABELS[role]
                except KeyError:
                    raise ValueError(f'Unknown speaker role: {role}') from None
                element(content, 'note', label,
                        type='description', corresp='urn:x-opensiddur:instruction:role/'+role).set(XML+'lang', 'he')
            for language, rubric in occurrence.get('rubrics', {}).items():
                for text in rubric if isinstance(rubric, list) else [rubric]:
                    note = element(content, 'note', type='description')
                    note.set(XML+'lang', language)
                    rubric_words(note, text, language)
            if occurrence.get('declarations'):
                declaration = element(content, 'j:declare')
                declaration.set(XML+'id', identifier+'_settings')
                feature_structures(declaration, occurrence['declarations'])
            expanded_order(content, occurrence['order'], readings, by_stem)
            if occurrence.get('declarations'):
                element(content, 'j:endDeclare', target='#'+identifier+'_settings')
            if conditions:
                element(outer, 'j:endConditional', target='#'+identifier+'_condition')
        elif 'instruction' in occurrence:
            keys = occurrence['instruction']
            keys = keys if isinstance(keys, list) else [keys]
            instructions = [readings['documentary_instructions'][key] for key in keys]
            kinds = {instruction.get('type', 'instruction') for instruction in instructions}
            if len(kinds) != 1:
                raise ValueError('A shared bilingual rubric must have one semantic kind')
            note = element(parent, 'note', type=kinds.pop())
            for instruction in instructions:
                content = element(note, 'foreign') if len(instructions) > 1 else note
                content.set(XML+'lang', instruction['language'])
                rubric_words(content, instruction, instruction['language'])
                if content is not note:
                    append_words(note, ' ')
        elif 'navigation' in occurrence:
            navigation = readings['navigation'][occurrence['navigation']]
            clauses = deepcopy(navigation['clauses'])
            for clause in clauses:
                if 'target' in clause:
                    clause['target'] = clause['target'].format(project=PROJECTS['he'])
            append_instruction(parent, clauses, expanded=True)
        elif 'reference' in occurrence:
            element(parent, 'j:transclude', type='external', **occurrence['reference'])
        else:
            element(parent, 'j:transclude', type='external', **reference(by_stem[occurrence['unit']]))


def front_text(page):
    return ' '.join(([page['head']] if page.get('head') else [])+page['paragraphs'])


def paratext_gate(parent, identifier, feature):
    conditional = element(parent, 'j:conditional')
    conditional.set(XML+'id', identifier)
    feature_structures(conditional, [{'type': 'opensiddur:paratext', 'features': {feature: True}}])


def add_front(root, pages, *, expanded=False):
    text = root.find(f'{{{TEI}}}text')
    front = etree.Element(f'{{{TEI}}}front')
    text.insert(0, front)
    if expanded:
        paratext_gate(front, 'expanded_editorial_front', 'include')
        title = element(front, 'div')
        title.set(XML+'lang', 'en')
        element(title, 'head', 'Expanded Ashkenazi Mahzor')
        element(title, 'p', 'First day of Rosh ha-Shanah')
        element(title, 'note', 'An editorial arrangement of the reviewed Heidenheim–Marmorstein passages. Digitization remains in progress.', type='description')
        element(front, 'j:endConditional', target='#expanded_editorial_front')
        return
    for page in pages:
        if page['kind'] not in FRONT_KINDS:
            continue
        facs = page_image_url(IDENTIFIER, int(page['scan'][1:])-1, size='')
        element(front, 'pb', ed='1965', facs=facs)
        identifier = 'front_'+page['scan']
        paratext_gate(front, identifier, 'title-page' if page['kind'] in ('title', 'copyright') else 'include')
        if page['kind'] == 'copyright':
            title = element(front, 'titlePage')
            title.set(XML+'lang', page['language'])
            imprint = element(title, 'docImprint')
            for index, paragraph in enumerate(page['paragraphs']):
                if index:
                    element(imprint, 'lb')
                words(imprint, paragraph, page['language'])
        elif page['kind'] == 'title':
            title = element(front, 'titlePage')
            title.set(XML+'lang', page['language'])
            titles = element(title, 'docTitle')
            layout = page.get('title_layout', {'main': 0, 'bylines': [1, 2], 'publisher': 3, 'place': 4})
            element(titles, 'titlePart', page['paragraphs'][layout['main']], type='main')
            if 'sub' in layout:
                element(titles, 'titlePart', page['paragraphs'][layout['sub']], type='sub')
            for index in layout['bylines']:
                byline = element(title, 'byline')
                language = page.get('paragraph_languages', {}).get(str(index), page['language'])
                if language != page['language']:
                    byline.set(XML+'lang', language)
                    byline = element(byline, 'foreign')
                    byline.set(XML+'lang', language)
                words(byline, page['paragraphs'][index], language)
            if any(key in layout for key in ('publisher', 'place', 'date')):
                imprint = element(title, 'docImprint')
                for key, tag in [('publisher', 'publisher'), ('place', 'pubPlace'), ('date', 'docDate')]:
                    if key in layout:
                        element(imprint, tag, page['paragraphs'][layout[key]])
        else:
            div = element(front, 'div')
            div.set(XML+'lang', page['language'])
            if page.get('head'):
                element(div, 'head', page['head'])
            for index, paragraph in enumerate(page['paragraphs']):
                language = page.get('paragraph_languages', {}).get(str(index), page['language'])
                node = element(div, 'p')
                if language != page['language']:
                    node.set(XML+'lang', language)
                    # Keep the whole foreign-language line, including abbreviation
                    # punctuation, in one directional span in the print stream.
                    node = element(node, 'foreign')
                    node.set(XML+'lang', language)
                words(node, paragraph, language)
        element(front, 'j:endConditional', target='#'+identifier)


def require_review(readings, reviews):
    for unit in readings['units']:
        for lang in unit['languages']:
            review = reviews.get(unit['stem']+'/'+lang, {})
            if not review_is_current(review, unit_review_text(unit, lang)):
                raise ValueError(f"Independent review pending or stale: {unit['stem']}/{lang}; use --draft for inspection")
            for index, citation in enumerate(unit.get('citations', {}).get(lang, [])):
                key = f"citation/{unit['stem']}/{lang}/{index}"
                if not review_is_current(reviews.get(key, {}), citation['text']):
                    raise ValueError('Independent citation review pending: '+key)
    by_identity = {unit['urn']: unit for unit in readings['units'] if unit.get('map_root', True)}
    for unit in readings['units']:
        for lang, segments in unit['languages'].items():
            for segment in segments:
                if segment.get('transclude'):
                    witness = by_identity.get(segment['transclude'])
                    text = ' '.join(fragment['text'] for fragment in segment['fragments'])
                    if not witness or lang not in witness['languages'] or text.split() != unit_text(witness, lang).split():
                        raise ValueError('Documentary transclusion review is stale: '+segment['transclude'])
    for name, navigation in readings.get('navigation', {}).items():
        for lang in navigation['scan']:
            key = 'navigation/'+name+'/'+lang
            if not review_is_current(reviews.get(key, {}), navigation['raw']):
                raise ValueError(f'Independent navigation review pending or stale: {key}')
    for name, instruction in readings.get('documentary_instructions', {}).items():
        key = 'instruction/'+name
        if not review_is_current(reviews.get(key, {}), instruction_review_text(instruction)):
            raise ValueError('Independent instruction review pending or stale: '+key)


def documentary_order(div, order, readings, by_stem, lang, project):
    """Preserve source sections without attaching service headings to reusable prayers."""
    for occurrence in order:
        if 'section' in occurrence:
            if lang not in occurrence.get('witnesses', PROJECTS):
                continue
            if occurrence.get('file'):
                element(div, 'j:transclude', type='external', target=occurrence['corresp']+'@'+project)
                continue
            section = element(div, 'div')
            if occurrence.get('corresp'):
                section.set('corresp', occurrence['corresp'])
            conditions = occurrence.get('conditions', [])
            if conditions:
                identifier = 'documentary_'+occurrence['section']+'_'+lang
                condition = element(section, 'j:conditional')
                condition.set(XML+'id', identifier)
                rubric_key = occurrence.get('condition_instruction', {}).get(lang)
                if rubric_key:
                    rubric = readings['documentary_instructions'][rubric_key]
                    note = element(condition, 'note', type='instruction')
                    note.set(XML+'lang', rubric['language'])
                    rubric_words(note, rubric, rubric['language'])
                feature_structures(element(condition, 'j:all'), conditions)
            key = occurrence['heading']
            if isinstance(key, dict):
                key = key.get(lang)
            heading = readings['documentary_instructions'].get(key)
            if heading and lang in heading['witnesses']:
                if heading.get('page_start', True):
                    element(section, 'pb', ed='1965', n=heading['printed_page'],
                            facs=page_image_url(IDENTIFIER, int(heading['scan'][1:])-1, size=''))
                element(section, 'head', heading['text']).set(XML+'lang', heading['language'])
            documentary_order(section, occurrence['order'], readings, by_stem, lang, project)
            if conditions:
                element(section, 'j:endConditional', target='#'+identifier)
            if not len(section) or all(child.tag in (f'{{{J}}}conditional', f'{{{J}}}endConditional')
                                       for child in section):
                div.remove(section)
        elif 'instruction' in occurrence:
            instruction = readings['documentary_instructions'][occurrence['instruction']]
            if lang in instruction['witnesses']:
                facs = page_image_url(IDENTIFIER, int(instruction['scan'][1:])-1, size='')
                page_start = instruction.get('page_start', True)
                if page_start.get(lang, False) if isinstance(page_start, dict) else page_start:
                    element(div, 'pb', ed='1965', n=instruction['printed_page'], facs=facs)
                note = element(div, 'note', type=instruction.get('type', 'instruction'), facs=facs)
                note.set(XML+'lang', instruction['language'])
                rubric_words(note, instruction, instruction['language'])
        elif 'navigation' in occurrence:
            navigation = readings['navigation'][occurrence['navigation']]
            scan = navigation['scan'][lang]
            if navigation.get('page_start', True):
                element(div, 'pb', ed='1965', n=navigation['printed_page'],
                        facs=page_image_url(IDENTIFIER, int(scan[1:])-1, size=''))
            clauses = deepcopy(navigation['clauses'])
            for clause in clauses:
                if 'target' in clause:
                    clause['target'] = clause['target'].format(project=project)
            append_instruction(div, clauses)
        elif 'reference' in occurrence:
            # A partial translation may need separate ranges around an absent
            # verse while its source file retains the printed chapter structure.
            if lang not in occurrence.get('witnesses', PROJECTS):
                continue
            attributes = dict(occurrence['reference'])
            # The end point inherits the start point's project.
            if '@' not in attributes['target']:
                attributes['target'] += '@'+project
            element(div, 'j:transclude', type='external', **attributes)
        else:
            unit = by_stem[occurrence['unit']]
            if lang in unit['languages']:
                element(div, 'j:transclude', type='external', target=unit_urn(unit)+'@'+project)


def build(source, project_directory, *, draft=False):
    readings = json.loads((source/'readings.json').read_text())
    reviews_path = source/'reviews.json'
    reviews = json.loads(reviews_path.read_text()) if reviews_path.exists() else {}
    front_path = source/'front.json'
    front_pages = json.loads(front_path.read_text())['pages'] if front_path.exists() else []
    if not draft:
        require_review(readings, reviews)
        for page in front_pages:
            if page['kind'] in FRONT_KINDS:
                if not review_is_current(reviews.get('front/'+page['scan'], {}), front_text(page)):
                    raise ValueError('Independent front-matter review pending: '+page['scan'])
    registry, problems = load_registry()
    if problems:
        raise ValueError('URN registry cannot be loaded cleanly')
    for unit in readings['units']:
        identities = [unit['urn']] + [s[key] for segments in unit['languages'].values()
                                     for s in segments for key in ('corresp', 'source', 'source_reference', 'transclude', 'repeat') if s.get(key)]
        if unit.get('publication_context'):
            identities.append(unit['publication_context'])
        identities.extend(unit.get('reuse', {}).values())
        identities += [citation['target'] for citations in unit.get('citations', {}).values()
                       for citation in citations if citation.get('target')]
        for urn in identities:
            # Numeric scripture descendants can be implicit in the registered book.
            if registry.resolve(urn) != urn:
                raise ValueError(f'Use the existing canonical URN, not its alias: {urn}')
            parsed = parse_urn(urn)
            if parsed.governed and urn not in registry.records and str(parsed.without_numeric_tail()) not in registry.records:
                raise ValueError(f'Unregistered identity: {urn}')
    documents = []
    def service_sections(order):
        for occurrence in order:
            if 'section' in occurrence:
                if occurrence.get('file'):
                    yield occurrence
                yield from service_sections(occurrence['order'])

    for lang, project in PROJECTS.items():
        root, body = document(lang, project, 'Prayerbook for the New Year — first day', ROOT_URN,
                              index=True, draft=draft)
        if front_pages:
            add_front(root, front_pages)
        div = element(body, 'div', corresp=ROOT_URN)
        by_stem = {unit['stem']: unit for unit in readings['units']}
        for section in service_sections(readings.get('source_order', [])):
            if lang not in section.get('witnesses', PROJECTS):
                continue
            heading_key = section.get('heading')
            if isinstance(heading_key, dict):
                heading_key = heading_key.get(lang)
            title = (section['titles'][lang] if section.get('titles') else
                     readings['documentary_instructions'][heading_key]['text'])
            service_root, service_body = document(lang, project, title, section['corresp'], draft=draft)
            inline_section = deepcopy(section)
            inline_section.pop('file')
            documentary_order(service_body, [inline_section], readings, by_stem, lang, project)
            documents.append((project_directory/project/(section['file']+'.xml'), service_root))
        documentary_order(div, readings.get('source_order', [{'unit': unit['stem']} for unit in readings['units']]),
                          readings, by_stem, lang, project)
        for unit in readings['units']:
            if lang in unit['languages']:
                pending = not review_is_current(reviews.get(unit['stem']+'/'+lang, {}),
                                                unit_review_text(unit, lang))
                documents.append((project_directory/project/(unit['stem']+'.xml'),
                                  unit_document(unit, lang, draft and pending)))
        documents.append((project_directory/project/'index.xml', root))
    root, body = document('he', EXPANDED, 'Expanded Ashkenazi Mahzor', EXPANDED_URN, index=True, draft=draft)
    for dependency in readings.get('dependencies', []):
        source_description = root.find(f'.//{{{TEI}}}sourceDesc')
        bibliography = element(source_description, 'bibl')
        element(bibliography, 'ptr', target='/'+dependency['project']+'/index#project_source_bibl')
        element(bibliography, 'note', dependency['reason'])
    if readings.get('expanded_coverage_note'):
        bibliography = root.find(f'.//{{{TEI}}}sourceDesc/{{{TEI}}}bibl')
        element(bibliography, 'note', readings['expanded_coverage_note'])
    add_front(root, [], expanded=True)
    div = element(body, 'div', corresp=EXPANDED_URN)
    element(div, 'head', 'מחזור אשכנז מורחב').set(XML+'lang', 'he')
    element(div, 'head', 'Expanded Ashkenazi Mahzor').set(XML+'lang', 'en')
    # The same structural sequence drives Hebrew and any English counterparts.
    order = readings.get('expanded_order', [{'unit': unit['stem']} for unit in readings['units']])
    by_stem = {unit['stem']: unit for unit in readings['units']}
    expanded_order(div, order, readings, by_stem)
    documents.append((project_directory/EXPANDED/'index.xml', root))
    corrections = source/'corrections.json'
    if corrections.exists():
        by_path = {f'{path.parent.name}/{path.name}': root for path, root in documents}
        apply_corrections(by_path, json.loads(corrections.read_text())['corrections'])
    # A language witness removed from the readings must not remain discoverable
    # through refdb merely because an earlier build wrote its file.
    obsolete = [project_directory/project/(unit['stem']+'.xml')
                for lang, project in PROJECTS.items() for unit in readings['units']
                if lang not in unit['languages']]
    obsolete += [project_directory/project/(section['file']+'.xml')
                 for lang, project in PROJECTS.items()
                 for section in service_sections(readings.get('source_order', []))
                 if lang not in section.get('witnesses', PROJECTS)]
    paths = write_documents(documents, validator=validate, obsolete_paths=obsolete)
    settings_directory = project_directory.parent/'settings'
    for project, variant, parallel in [(PROJECTS['he'], 'documentary', False),
                                       (PROJECTS['he'], 'with_translation', True),
                                       (EXPANDED, 'undated', True)]:
        settings = {'description': 'First-day Rosh ha-Shanah mahzor; digitization in progress.',
                    'requires_processor': '>=0.8.0.dev0',
                    'book': {'project': project, 'file_name': 'index.xml', 'title': 'Prayerbook for the New Year — first day'},
                    'annotations': list(PROJECTS.values()) if parallel else [PROJECTS['he']],
                    'priority': {'transclusion': [project]+[p for p in PROJECTS.values() if p != project],
                                 'instructions': [project]+[p for p in PROJECTS.values() if p != project]},
                    'typography': {'instructions': {'from': 'both'}, 'line_numbers': {'enabled': False}}}
        if parallel:
            settings['parallel'] = {'projects': [PROJECTS['en']]}
        if project != EXPANDED:
            settings['electronic'] = {'day': 'none'}
        if project == EXPANDED:
            settings['readings'] = {'abbreviations': 'expanded'}
            for dependency in readings.get('dependencies', []):
                for kind in ('transclusion', 'instructions'):
                    # Hebrew dependencies precede translations even when a
                    # future English witness acquires the same prayer URN.
                    settings['priority'][kind].insert(-1, dependency['project'])
        destination = settings_directory/project/(variant+'.yaml')
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_if_changed(destination, yaml.safe_dump(settings, allow_unicode=True, sort_keys=False))
    print(f'{len(paths)} validated JLPTEI files; ' + ('DRAFT review status' if draft else 'reviewed installment'))
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=SOURCETEXTS_ROOT)
    parser.add_argument('--project-directory', type=Path, default=PROJECT_DIRECTORY)
    parser.add_argument('--draft', action='store_true')
    args = parser.parse_args(argv)
    build(args.source_root/BOOK, args.project_directory, draft=args.draft)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
