"""Reuse source structure while retaining every word of prayer in its edition.

Only structural containers are expanded. A unit that owns prayer words remains
one transclusion, so no Hebrew or translation is copied into the new project.
"""
from copy import deepcopy
from itertools import count
from pathlib import Path
import unicodedata
from lxml import etree as E
from opensiddur.importer.birnbaum_scan.build.common import PROJECT_EN, PROJECT_HE
from .xml import T, J, NS, XID, TEXT, feature, parse_fragment, transclude, serialize

def unpinned(urn):
    """`urn` without an `@project` suffix naming the edition it must come from."""
    return urn.split('@', 1)[0] if urn.startswith('urn:') else urn


class Composer:
    def __init__(self, project_directory):
        self.directory = Path(project_directory)
        self.units = {}; self.english = {}; self.used = set(); self.depth = 0; self.occurrences = count(1)
        for lang, target in [('he', self.units), ('en', self.english)]:
            for path in sorted((self.directory/{'he': PROJECT_HE, 'en': PROJECT_EN}[lang]).glob('*.xml')):
                root = E.parse(str(path))
                for div in root.xpath('//tei:body/tei:div[@corresp]', namespaces=NS):
                    target[div.get('corresp')] = div

    def has_words(self, node):
        for e in node.iter():
            if e.tag in [f'{{{T}}}p',f'{{{T}}}l',f'{{{T}}}seg'] and ''.join(e.itertext()).strip():
                if not any(a.tag==f'{{{T}}}note' for a in e.iterancestors()): return True
        return False

    def remove_redundant_heads(self, reference, target):
        """Let a prayer's own title replace an identical adjacent wrapper title.

        Compare languages separately. Stop at prayer content or scope markers so
        distinct occurrences and conditionally different headings remain intact.
        """
        def key(heading):
            text = ' '.join(''.join(heading.itertext()).split()).casefold()
            text = ''.join(c for c in unicodedata.normalize('NFD', text)
                           if not unicodedata.category(c).startswith('M'))
            return heading.get('{http://www.w3.org/XML/1998/namespace}lang'), text

        transparent = {f'{{{T}}}{tag}' for tag in ('pb', 'milestone', 'note')}
        transparent.update(f'{{{J}}}{tag}' for tag in ('declare', 'endDeclare'))
        titles = set()
        for units in (self.units, self.english):
            source = units.get(target)
            if source is None or not self.has_words(source):
                continue
            for child in source:
                if child.tag == f'{{{T}}}head':
                    titles.add(key(child))
                elif child.tag not in transparent:
                    break
        for previous in list(reference.itersiblings(preceding=True)):
            if previous.tag == f'{{{T}}}head':
                if key(previous) in titles:
                    previous.getparent().remove(previous)
            elif previous.tag not in transparent:
                break

    @staticmethod
    def declare_public_context(root):
        """Resolve inherited quorum tests inside an already eligible public passage.

        The outer gate remains undecided when the reader hasn't selected quorum.
        Its contents are intrinsically public, including separately transcluded
        paragraphs whose original source has its own quorum gate.
        """
        for gate in list(root.iter(f'{{{J}}}conditional')):
            gate_id = gate.get(XID)
            if not gate_id:
                continue
            predicates = [e for e in gate if e.tag != f'{{{T}}}note']
            if len(predicates) != 1:
                continue
            fs = predicates[0]
            if (fs.tag != f'{{{T}}}fs' or fs.get('type') != 'opensiddur:quorum'
                    or len(fs) != 1 or fs[0].tag != f'{{{T}}}f'
                    or fs[0].get('name') != 'minyan' or len(fs[0]) != 1
                    or fs[0][0].tag != f'{{{T}}}binary'
                    or fs[0][0].get('value') != 'true'):
                continue
            parent = gate.getparent()
            closer = next((e for e in gate.itersiblings()
                           if e.tag == f'{{{J}}}endConditional'
                           and e.get('target') == '#'+gate_id), None)
            if closer is None:
                continue
            ident = gate_id+'_public_context'
            fragment = parse_fragment(
                f'<j:declare xml:id="{ident}">'+feature('quorum', 'minyan')
                +f'</j:declare><j:endDeclare target="#{ident}"/>')
            declaration, end = list(fragment)
            parent.insert(parent.index(gate)+1, declaration)
            parent.insert(parent.index(closer), end)

    def merge_heads(self, primary, counterpart):
        """Keep translated headings at their source position among shared structure.

        A source can have a heading where its counterpart has none (the English
        Adon Olam and Yigdal titles, for example). Pairing all headings by ordinal
        shifts every later title. Instead, match parents without counting heads,
        and merge headings only within the same gap between their other children.
        """
        heading = f'{{{T}}}head'
        if not counterpart.xpath('.//tei:head', namespaces=NS):
            return
        # Directions may be present on only one side; they do not identify a
        # prayer's position. Keep the primary directions, and align the other
        # structural nodes (including conditional boundaries).
        ignored = {heading, f'{{{T}}}note'}
        left = [e for e in primary if e.tag not in ignored]
        right = [e for e in counterpart if e.tag not in ignored]
        def structural_key(element):
            if element.tag == f'{{{J}}}transclude':
                return element.tag, element.get('target'), element.get('targetEnd')
            if element.tag == f'{{{J}}}conditional':
                return element.tag, element.get(XID)
            if element.tag == f'{{{J}}}endConditional':
                return element.tag, element.get('target')
            return (element.tag,)
        if [structural_key(e) for e in left] != [structural_key(e) for e in right]:
            raise ValueError('Cannot align structural headings: '+str(primary.get('corresp')))

        def gaps(parent):
            result = {}; slot = 0
            for child in parent:
                if child.tag == heading:
                    result.setdefault(slot, []).append(child)
                elif child.tag not in ignored:
                    slot += 1
            return result

        primary_heads, translated_heads = gaps(primary), gaps(counterpart)
        children = []; slot = 0; head_index = 0
        def remaining_heads():
            children.extend(deepcopy(e) for e in translated_heads.get(slot, [])[len(primary_heads.get(slot, [])):])
        for child in primary:
            if child.tag == heading:
                children.append(child)
                translations = translated_heads.get(slot, [])
                if head_index < len(translations) and ''.join(child.itertext()) != ''.join(translations[head_index].itertext()):
                    children.append(deepcopy(translations[head_index]))
                head_index += 1
            elif child.tag in ignored:
                children.append(child)
            else:
                remaining_heads()
                self.merge_heads(child, right[slot])
                children.append(child)
                slot += 1; head_index = 0
        remaining_heads()
        primary[:] = children

    def source(self, urn, *, replace=None, omit=(), mode=None, conditions=None, include_heading=True):
        urn = urn if urn.startswith('urn:') else TEXT+urn
        self.used.add(urn)
        if urn not in self.units or self.has_words(self.units[urn]): return transclude(urn)
        if self.depth > 24: raise ValueError('Structural transclusion cycle: '+urn)
        self.depth += 1
        try:
            root = deepcopy(self.units[urn])
            counterpart = self.english.get(urn)
            if counterpart is not None:
                self.merge_heads(root, counterpart)
            if not include_heading:
                for heading in list(root.findall('tei:head', NS)):
                    root.remove(heading)
            # Wrapper identities are the source edition's. Reusing them here would
            # compete with that edition and select its unexpanded parallel container.
            for element in root.iter():
                if element.tag==f'{{{T}}}div' or element.get('corresp','').startswith(TEXT):
                    element.attrib.pop('corresp',None)
            for e in list(root.xpath('.//tei:note',namespaces=NS)):
                text=' '.join(''.join(e.itertext()).split())
                if e.xpath('.//tei:seg[@type="optional-page-reference"]|.//tei:ref[@type="page"]',namespaces=NS) or 'page ' in text or 'pages ' in text:
                    e.getparent().remove(e)
                elif mode is not None and ('The Reader repeats the' in text or 'is recited in silent devotion while standing' in text):
                    e.getparent().remove(e)
            # The abridged Amidah is an alternative reference item, not another
            # prayer to say after the complete Amidah.
            for div in list(root.xpath('.//tei:div',namespaces=NS)):
                if any('ABRIDGED SHEMONEH' in ''.join(h.itertext()) for h in div.findall('tei:head',NS)):
                    div.getparent().remove(div)
            for conditional in root.iter(f'{{{J}}}conditional'):
                predicate=(conditions or {}).get(conditional.get(XID))
                if predicate is not None:
                    for child in list(conditional):
                        if child.tag!=f'{{{T}}}note':conditional.remove(child)
                    fragment=E.fromstring(f'<root xmlns:tei="{T}" xmlns:j="{J}">{predicate}</root>'.encode())
                    conditional.extend(list(fragment))
            self.declare_public_context(root)
            replace = replace or {}
            for e in list(root.iter(f'{{{J}}}transclude')):
                # Birnbaum pins some of its transclusions to itself, so that its own
                # words are set where another edition mints the same URN. The expanded
                # siddur is not Birnbaum: which edition supplies the words is the
                # volume's choice, by its transclusion priorities, so the pin is dropped.
                for attribute in ('target', 'targetEnd'):
                    if e.get(attribute):
                        e.set(attribute, unpinned(e.get(attribute)))
                target=e.get('target')
                if target not in omit and target not in replace:
                    self.remove_redundant_heads(e, target)
                self.used.add(target)
                if target in omit: replacement=''
                elif target in replace: replacement=replace[target]
                else: replacement=self.source(target, replace=replace, omit=omit, mode=mode, conditions=conditions) if target in self.units and not self.has_words(self.units[target]) else serialize(e)
                parent=e.getparent();index=parent.index(e);parent.remove(e)
                frag=E.fromstring(f'<root xmlns:tei="{T}" xmlns:j="{J}">{replacement}</root>'.encode())
                for child in list(frag): parent.insert(index,child);index+=1
            # Every occurrence has its own IDs, including source declaration markers.
            prefix='occurrence_'+str(next(self.occurrences))+'_'
            ids={e.get(XID) for e in root.iter() if e.get(XID)}
            for e in root.iter():
                if e.get(XID): e.set(XID,prefix+e.get(XID))
                target=e.get('target','')
                if target.startswith('#') and target[1:] in ids:e.set('target','#'+prefix+target[1:])
            return serialize(root)
        finally: self.depth -= 1
