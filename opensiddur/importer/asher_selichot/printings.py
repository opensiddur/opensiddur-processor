"""A text the book prints twice, in words that differ: one text, each printing its variant.

Asher prints אָדוֹן דִּין twice, for Erev Rosh Hashanah (p. 62, אִם־יִדַּקֵּן) and for Erev Yom
Kippur (p. 155, אִם־תְּדַקְדֵּק), and אָדוֹן בְּפָקְדְּךָ twice, for both (לִבְקָרִים,
לַבְּקָרִים). The readings keep each printing as the scan has it, in a file of its own; the build
then writes both into the first printing's file, each branch scoped by an ``opensiddur:variant``
feature (JLPTEI-3, as the Metsudah volumes encode their variants), and each service declares
which printing it says around its transclusion.

A later printing the book records as a recension of the text -- יִשְׂרָאֵל נוֹשַׁע for the fasts,
``poem:yisrael_nosha/fast_day_recension`` -- keeps its URN, a child of the text's: its branch is
a division with that URN, and the variant's feature is named by it.
"""

import copy
import re

from lxml import etree

from opensiddur.importer.scan.authoring import element

TEI = 'http://www.tei-c.org/ns/1.0'
J = 'http://jewishliturgy.org/ns/jlptei/2'
XML = '{http://www.w3.org/XML/1998/namespace}'
TEXT = 'urn:x-opensiddur:text:'
CONDITION = 'urn:x-opensiddur:condition:'

#: the file of a later printing: (the file of the text it prints, the name of its variant)
LATER_PRINTINGS = {
    'adon_din_im_tedaqdeq': ('adon_din_im_yiddeqen', 'selichot_erev_yom_kippur'),
    'adon_befaqdekha_enosh_labeqarim': ('adon_befaqdekha_enosh_livqarim', 'selichot_erev_yom_kippur'),
    'yisrael_nosha_fast_day_recension': ('yisrael_nosha', 'fast_day_recension'),
}


def _urn(root):
    return root.find(f'.//{{{TEI}}}body/{{{TEI}}}div').get('corresp')


def _feature(text_urn, variant):
    return CONDITION + text_urn[len(TEXT):] + '/' + variant


def _fs(parent, feature, value):
    fs = element(parent, 'fs', type='opensiddur:variant')
    f = element(fs, 'f')
    f.set('name', feature)
    element(f, 'binary', value='true' if value else 'false')


def _branch(div, feature, value, identity, children):
    start = element(div, 'j:conditional')
    start.set(XML + 'id', identity)
    _fs(start, feature, value)
    for child in children:
        div.append(child)
    element(div, 'j:endConditional', target='#' + identity)


def _declare_around(service, target, feature, value, identity):
    """Declare the variant around each transclusion of ``target`` in ``service`` that does not
    declare it already; a second in one service has its own id (``<identity>_2``)."""
    nodes = [node for node in service.iter(f'{{{J}}}transclude') if node.get('target') == target
             and not _declares(node.getprevious(), feature)]
    taken = {node.get(XML + 'id') for node in service.iter(f'{{{J}}}declare')}
    for node in nodes:
        unique, count = identity, 1
        while unique in taken:
            count += 1
            unique = f'{identity}_{count}'
        taken.add(unique)
        declaration = etree.Element(f'{{{J}}}declare')
        declaration.set(XML + 'id', unique)
        _fs(declaration, feature, value)
        end = etree.Element(f'{{{J}}}endDeclare', target='#' + unique)
        end.tail, node.tail = node.tail, None
        node.addprevious(declaration)
        node.addnext(end)


def unify(documents):
    """``documents`` (path, root) with each later printing written into the file of the text it
    prints, and the paths of the later printings' files, which are no longer written."""
    by_path = {path: root for path, root in documents}
    dropped = []
    for later_stem, (stem, variant) in LATER_PRINTINGS.items():
        for later_path in [p for p in by_path if p.stem == later_stem]:
            path = later_path.with_name(stem + later_path.suffix)
            first, later = by_path[path], by_path.pop(later_path)
            text_urn, later_urn = _urn(first), _urn(later)
            feature = _feature(text_urn, variant)
            div = first.find(f'.//{{{TEI}}}body/{{{TEI}}}div')
            later_div = later.find(f'.//{{{TEI}}}body/{{{TEI}}}div')
            first_children = list(div)
            for child in first_children:
                div.remove(child)
            _branch(div, feature, False, stem + '_printed', first_children)
            if later_urn.startswith(text_urn + '/'):
                # A recension the book names: its division, URN and all, is the branch.
                kept = etree.Element(f'{{{TEI}}}div', corresp=later_urn)
                kept.extend(list(later_div))
                _branch(div, feature, True, stem + '_' + variant, [kept])
            else:
                _branch(div, feature, True, stem + '_' + variant, list(later_div))
            for other_path, root in by_path.items():
                if other_path.parent != path.parent or other_path == path:
                    continue
                _declare_around(root, later_urn, feature, True, stem + '_' + variant)
                for node in root.iter(f'{{{J}}}transclude'):
                    if node.get('target') == later_urn:
                        node.set('target', text_urn)
                _declare_around(root, text_urn, feature, False, stem + '_printed')
            dropped.append(later_path)
    return [(p, r) for p, r in documents if p in by_path], dropped


def text_urn(urn):
    """The URN of the text a later printing (named by its own reading's URN) prints."""
    path = urn.rsplit(':', 1)[-1]
    for later_stem, (stem, _) in LATER_PRINTINGS.items():
        if path.replace('/', '_') == later_stem:
            return urn[:-len(path)] + stem
    return urn


def _declared(root, feature):
    return any(f.get('name') == feature for f in root.iter(f'{{{TEI}}}f'))


def _declares(node, feature):
    return node is not None and node.tag == f'{{{J}}}declare' and _declared(node, feature)


def printing(project, name):
    """The body ``tei:div`` of the printing the readings know as the file ``name`` (spelled as
    the book spells it), in ``project``: a later printing is its branch of the text's file."""
    for later_stem, (stem, variant) in LATER_PRINTINGS.items():
        if name in (later_stem, stem):
            root = etree.parse(str(project / (stem + '.xml')))
            div = root.find(f'.//{{{TEI}}}body/{{{TEI}}}div')
            found = branch(div, _feature(div.get('corresp'), variant), name == later_stem)
            # A recension's own division, as its file had it.
            divisions = [child for child in found if child.tag == f'{{{TEI}}}div']
            if name == later_stem and len(found) == 1 and len(divisions) == 1:
                return divisions[0]
            return found
    return etree.parse(str(project / (name + '.xml'))).find(f'.//{{{TEI}}}body/{{{TEI}}}div')


def branch(div, feature, value):
    """A copy of ``div`` with only the branch of ``feature`` that is ``value``."""
    out = copy.deepcopy(div)
    keep = opened = None
    for child in list(out):
        if child.tag == f'{{{J}}}conditional' and _declared(child, feature):
            keep = child.find(f'.//{{{TEI}}}binary').get('value') == ('true' if value else 'false')
            opened = child.get(XML + 'id')
            out.remove(child)
        elif child.tag == f'{{{J}}}endConditional' and opened and child.get('target') == '#' + opened:
            keep = opened = None
            out.remove(child)
        elif keep is False:
            out.remove(child)
    return out


_DECLARATIONS = {identity for later_stem, (stem, variant) in LATER_PRINTINGS.items()
                 for identity in (stem + '_printed', stem + '_' + variant)}


def is_declaration(node):
    """A variant declaration (or its end) the build put around a transclusion in a service."""
    if node.tag == f'{{{J}}}declare':
        return _ours(node.get(XML + 'id', ''))
    return node.tag == f'{{{J}}}endDeclare' and _ours(node.get('target', '').lstrip('#'))


def _ours(identity):
    return identity in _DECLARATIONS or re.sub(r'_\d+$', '', identity) in _DECLARATIONS
