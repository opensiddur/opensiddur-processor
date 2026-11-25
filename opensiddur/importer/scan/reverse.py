"""Extract documentary XML streams by scan identity, selecting printed abbreviations.

Unlike a regex over markup, this does not concatenate editorial expansions or
mistake a transcluded passage for text printed at the referring location.
"""
from collections import defaultdict
import argparse
import difflib
from pathlib import Path
from lxml import etree

TEI = '{http://www.tei-c.org/ns/1.0}'
J = '{http://jewishliturgy.org/ns/jlptei/2}'
XML = '{http://www.w3.org/XML/1998/namespace}'


def streams(root, *, include_notes=False):
    result = defaultdict(list)
    state = {'page': None, 'lang': root.get(XML + 'lang', '')}

    def walk(el, lang):
        if not isinstance(el.tag, str):
            return
        parent_lang = lang
        lang = el.get(XML + 'lang', lang)
        language_boundary = lang != parent_lang
        if language_boundary and state['page']:
            result[(state['page'], lang)].append(' ')
        if el.tag == TEI + 'pb':
            facs = el.get('facs', '')
            import re
            match = re.search(r'/n(\d+)(?:_\w+)?\.jpg', facs)
            if not match:
                raise ValueError('Every documentary page break needs a scan-linked facsimile.')
            state['page'] = f's{int(match[1]) + 1}'
            return
        if el.tag in (TEI + 'teiHeader', TEI + 'standOff'):
            return
        if el.tag == J + 'transclude':
            raise ValueError('Reverse-check source modules, not service transclusion indexes.')
        if el.tag == TEI + 'note' and not include_notes:
            return
        if el.tag == TEI + 'note' and state['page']:
            result[(state['page'], lang)].append(' ')
        children = list(el)
        if el.tag == TEI + 'choice' and el.find(TEI + 'abbr') is not None:
            children = [el.find(TEI + 'abbr')]
        if el.tag == TEI + 'choice' and el.find(TEI + 'sic') is not None:
            children = [el.find(TEI + 'sic')]
        if el.text and state['page']:
            result[(state['page'], lang)].append(el.text)
        for child in children:
            walk(child, lang)
            if child.tail and state['page']:
                result[(state['page'], lang)].append(child.tail)
        if language_boundary and state['page']:
            result[(state['page'], lang)].append(' ')
        if el.tag in (TEI + 'p', TEI + 'l', TEI + 'head', TEI + 'lg', TEI + 'note') and state['page']:
            result[(state['page'], lang)].append('\n')

    walk(root, state['lang'])
    return {key: ' '.join(''.join(parts).split()) for key, parts in result.items()}


def check(actual, readings):
    if actual.keys() != readings.keys():
        raise ValueError(f'Source/readings coverage differs: {actual.keys() ^ readings.keys()}')
    return {key: list(difflib.unified_diff(readings[key].split(), actual[key].split(),
                                         fromfile='reading', tofile='authored', lineterm=''))
            for key in actual if actual[key].split() != readings[key].split()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('xml', nargs='+', type=Path)
    parser.add_argument('--readings', required=True, type=Path,
                        help='JSON mapping scan identity to language to documentary text.')
    parser.add_argument('--include-notes', action='store_true')
    args = parser.parse_args(argv)
    import json
    readings = {(page, lang): text for page, langs in json.loads(args.readings.read_text(encoding="utf-8")).items()
                for lang, text in langs.items()}
    actual = {}
    for path in args.xml:
        for key, text in streams(etree.parse(str(path)).getroot(), include_notes=args.include_notes).items():
            actual[key] = (actual.get(key, '') + ' ' + text).strip()
    differences = check(actual, readings)
    for key, lines in differences.items():
        print(key, '\n'.join(lines))
    print(f'{len(actual)} source-page/language streams checked; {len(differences)} differ')
    return bool(differences)


if __name__ == '__main__':
    raise SystemExit(main())
