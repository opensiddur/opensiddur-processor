"""Reusable scan-to-JLPTEI authoring and structural checks.

Edition wording, identifiers, page labels and layout decisions belong to callers.
These operations accept synthetic text/data and are covered independently of books.
"""
import re
import unicodedata
from lxml import etree

TEI = 'http://www.tei-c.org/ns/1.0'
J = 'http://jewishliturgy.org/ns/jlptei/2'
XML = '{http://www.w3.org/XML/1998/namespace}'

def element(parent, name, text=None, **attributes):
    tag=f'{{{J if name.startswith("j:") else TEI}}}{name.split(":")[-1]}'
    node=etree.SubElement(parent,tag,attributes)
    node.text=text
    return node


def marker(parent, urn):
    element(parent,'milestone',unit='stanza',corresp=urn)


def choice(parent, abbr, expan):
    node=element(parent,'choice');element(node,'abbr',abbr);element(node,'expan',expan)
    return node


def italicize(parent, phrases):
    """Apply supplied emphasis spans without changing the documentary words."""
    original = parent.text or ''
    locations = []
    for phrase in phrases:
        position = original.find(phrase)
        if position < 0:
            raise ValueError(f'Missing printed emphasis phrase: {phrase}')
        locations.append((position, phrase))
    locations.sort()
    if not locations:
        return
    parent.text = original[:locations[0][0]]
    for i, (position, phrase) in enumerate(locations):
        hi = element(parent, 'hi', phrase, rend='italic')
        end = locations[i + 1][0] if i + 1 < len(locations) else len(original)
        hi.tail = original[position + len(phrase):end]


def normalized_xml(root):
    """Normalize source glyphs while preserving binding spaces before phrase dots."""
    xml=etree.tostring(root,encoding='unicode',pretty_print=True)
    xml='\u00a0'.join(unicodedata.normalize('NFKD',part) for part in xml.split('\u00a0'))
    return xml.replace(' ·','\u00a0·')


def append_words(parent, words):
    if len(parent):
        parent[-1].tail = (parent[-1].tail or '') + words
    else:
        parent.text = (parent.text or '') + words


def mixed_words(parent, words):
    """Wrap Hebrew spans explicitly inside English text."""
    for part in re.split(r'([\u0590-\u05ff](?:[\u0590-\u05ff ·\s]*[\u0590-\u05ff])?)', words):
        if re.search(r'[\u05d0-\u05ea]', part):
            element(parent, 'foreign', part).set(XML+'lang', 'he')
        else:
            append_words(parent, part)


def words_with_notes(parent, words, notes, lang):
    """Place each printed footnote at its recorded anchor, exactly once."""
    rest = words
    for note in notes:
        anchor = unicodedata.normalize('NFKD', note['anchor'])
        if anchor not in rest:
            raise ValueError(f'Footnote anchor absent: {anchor!r}')
        before, rest = rest.split(anchor, 1)
        append_words(parent, before+anchor)
        node = element(parent, 'note', type='commentary')
        if lang == 'he' and re.search('[A-Za-z]',note['text']):
            first, following = note['text'].split('\n',1)
            p = element(node,'p');p.set(XML+'lang','en');mixed_words(p,first)
            element(node,'p',following)
        elif '\n' in note['text']:
            # Each printed line of a multi-paragraph note is its own paragraph, with the
            # emphasis the print gives it.
            italic = note.get('italic', [])
            for phrase in italic:
                if not any(phrase in paragraph for paragraph in note['text'].split('\n')):
                    raise ValueError(f'Missing printed emphasis phrase: {phrase}')
            for paragraph in note['text'].split('\n'):
                p = element(node, 'p')
                if lang == 'en' and re.search(r'[\u05d0-\u05ea]', paragraph):
                    mixed_words(p, paragraph)
                else:
                    p.text = paragraph
                    italicize(p, [phrase for phrase in italic if phrase in paragraph])
        elif lang == 'en' and re.search(r'[\u05d0-\u05ea]', note['text']):
            node.set(XML+'lang', 'en')
            mixed_words(node, note['text'])
        else:
            node.text = note['text']
    append_words(parent, rest)


def poetic_lines(node, fragments, rule, *, page_break):
    """Keep semantic verse lines across scan boundaries and mark terminal refrains."""
    stops = rule['line_stops']
    line = None
    for i, fragment in enumerate(fragments):
        data = fragment['he']
        if i:
            page_break(line if line is not None else node, data['scan'], data['printed_page'])
        remaining_notes = list(fragment['notes']['he'])
        for words in re.findall(r'[^'+re.escape(stops)+r']+['+re.escape(stops)+r'][\]\)]?|[^'+re.escape(stops)+r']+$', data['text']):
            words = words.strip()
            # A phrase dot is printed apart from the word, but must not wrap alone.
            words = re.sub(r' +(?=·$)', '\u00a0', words)
            if not words:
                continue
            if line is None:
                line = element(node, 'l')
                line.tail = ' '
            notes = [note for note in remaining_notes if note['anchor'] in words]
            for note in notes:
                remaining_notes.remove(note)
            refrain = rule.get('refrain')
            match = re.search(re.escape(refrain)+r'\s*['+re.escape(stops)+r']$', words) if refrain else None
            if match:
                words_with_notes(line, words[:match.start()], notes, 'he')
                element(line, 'seg', words[match.start():], type='refrain')
            else:
                words_with_notes(line, words, notes, 'he')
            if words.rstrip('])')[-1] in stops:
                line = None
            elif not data.get('join_next'):
                append_words(line, ' ')
        if remaining_notes:
            raise ValueError('Poetry footnote anchor crosses a verse boundary')


def wrap_hebrew(node):
    """Wrap Hebrew in English body text as well as its apparatus."""
    for parent in list(node.iter()):
        if parent.get(XML+'lang')=='he' or parent.tag==f'{{{TEI}}}foreign':continue
        if parent.text and re.search('[\u05d0-\u05ea]',parent.text):
            words=parent.text;parent.text=None
            temporary=etree.Element('temporary');mixed_words(temporary,words)
            parent.text=temporary.text
            for index,child in enumerate(list(temporary)):parent.insert(index,child)
        for child in list(parent):
            if child.tail and re.search('[\u05d0-\u05ea]',child.tail):
                words=child.tail;child.tail=None
                temporary=etree.Element('temporary');mixed_words(temporary,words)
                child.tail=temporary.text
                for index,following in enumerate(list(temporary),parent.index(child)+1):parent.insert(index,following)


def check_poetry(unit, rule):
    """Audit structure separately: identical prose words must not pass as poetry."""
    lines = unit.findall(f'{{{TEI}}}lg/{{{TEI}}}l')
    if unit.findall(f'{{{TEI}}}p') or len(lines) != rule['line_count']:
        raise ValueError('Poetry verse structure differs from scan adjudication')
    refrains = unit.findall(f'.//{{{TEI}}}seg[@type="refrain"]')
    if len(refrains) != rule.get('refrain_count', 0):
        raise ValueError('Poetry refrain count differs from scan adjudication')
    for refrain in refrains:
        words = ''.join(refrain.itertext())
        if (words.rstrip('·׃ ').strip() != rule['refrain']
                or refrain.getparent().tag != f'{{{TEI}}}l'
                or refrain.getnext() is not None or (refrain.tail or '').strip()):
            raise ValueError('Poetry refrain must end its verse exactly once')


def conditional_scope(parent, identity, present, *, fs_type, feature):
    """Start a boolean scope; callers own its edition-specific feature name."""
    conditional = element(parent, 'j:conditional')
    conditional.set(XML + 'id', identity)
    fs = element(conditional, 'fs', type=fs_type)
    field = element(fs, 'f')
    field.set('name', feature)
    element(field, 'binary', value='true' if present else 'false')
    return conditional


def printed_text(node, separator=''):
    """The printed branches of source choices, excluding corrections and expansions."""
    parts = []
    def walk(current):
        if current.text:
            parts.append(current.text)
        for child in current:
            if child.tag not in (f'{{{TEI}}}corr', f'{{{TEI}}}expan'):
                walk(child)
            if child.tail:
                parts.append(child.tail)
    walk(node)
    return separator.join(parts)


def _locate(documents, spec, span, kind):
    """The one text position a correction or editorial note names: (root, node, attribute, start).

    A spec names its `file` (``project/file.xml``) and the `before`/`after` text around `span`
    in one text node (the whole of it, with `exact`), or `follows`: the end of the string value
    of the element whose tail it begins. Text inside an earlier correction is never matched.
    It must match exactly once, so an entry never lands twice or goes stale silently.
    """
    root = documents.get(spec['file'])
    if root is None:
        raise ValueError(f"{kind} {spec['id']}: no document {spec['file']}")
    before, after = spec.get('before', ''), spec.get('after', '')
    target = before + span + after
    matches = []
    corrected = {f'{{{TEI}}}sic', f'{{{TEI}}}corr'}
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        inside = node.tag in corrected or any(a.tag in corrected for a in node.iterancestors())
        for attribute in ('text', 'tail'):
            if inside and (attribute == 'text' or node.tag not in corrected):
                continue
            value = getattr(node, attribute)
            if not value:
                continue
            if 'follows' in spec:
                if (attribute == 'tail' and value.startswith(target)
                        and ''.join(node.itertext()).endswith(spec['follows'])):
                    matches.append((node, attribute, len(before)))
            elif spec.get('exact'):
                if value == target:
                    matches.append((node, attribute, len(before)))
            elif value.count(target) == 1:
                matches.append((node, attribute, value.index(target) + len(before)))
            elif value.count(target) > 1:
                matches.extend([None, None])
    if len(matches) != 1 or matches[0] is None:
        raise ValueError(f"{kind} {spec['id']}: {len(matches)} places match in {spec['file']}")
    return (root,) + matches[0]


def _insert_at(node, attribute, start, end, new):
    """Put `new` where characters start..end of node.text/.tail were, keeping the rest."""
    value = getattr(node, attribute)
    new.tail = value[end:]
    setattr(node, attribute, value[:start])
    if attribute == 'text':
        node.insert(0, new)
    else:
        parent = node.getparent()
        parent.insert(parent.index(node) + 1, new)


def apply_corrections(documents, corrections):
    """Mark each recorded misprint as tei:choice/tei:sic + tei:corr in its document.

    `documents` maps a project-relative path to its root. Each correction gives the printed
    `sic` and its `corr`, located as `_locate` describes.
    """
    for correction in corrections:
        _, node, attribute, start = _locate(documents, correction, correction['sic'], 'Correction')
        choice_node = etree.Element(f'{{{TEI}}}choice')
        element(choice_node, 'sic', correction['sic'] or None)
        element(choice_node, 'corr', correction['corr'] or None)
        _insert_at(node, attribute, start, start + len(correction['sic']), choice_node)


def apply_editorial_notes(documents, notes):
    """Add each editorial note as a standoff tei:note on an anchor at its place in the text.

    A note gives its `text` (English; Hebrew in it is marked as such) and is placed after the
    `before` text, located as `_locate` describes. Notes are found through the anchor, so they
    print only where a book lists the project under its annotations.
    """
    for note in notes:
        root, node, attribute, start = _locate(documents, note, '', 'Editorial note')
        anchor = etree.Element(f'{{{TEI}}}anchor')
        anchor.set(XML + 'id', 'editorial_' + note['id'].replace('-', '_'))
        _insert_at(node, attribute, start, start, anchor)
        standoff = root.find(f'{{{TEI}}}standOff[@type="notes"]')
        if standoff is None:
            standoff = etree.SubElement(root, f'{{{TEI}}}standOff', type='notes')
        editorial = element(standoff, 'note', type='editorial', target='#' + anchor.get(XML + 'id'))
        editorial.set(XML + 'lang', 'en')
        mixed_words(editorial, note['text'])


def write_documents(documents, *, validator, obsolete_paths=()):
    """Validate the complete generated set before writing or removing any files."""
    prepared = []
    for path, root in documents:
        xml = normalized_xml(root)
        valid, errors = validator(xml)
        if not valid:
            raise ValueError(f'{path}: ' + '\n'.join(errors))
        prepared.append((path, xml))
    for path, xml in prepared:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(xml, encoding='utf-8')
    for path in obsolete_paths:
        path.unlink(missing_ok=True)
    return [path for path, _ in prepared]
