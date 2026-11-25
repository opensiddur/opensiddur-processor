import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lxml import etree

from opensiddur.importer.asher_selichot import printings

TEI = 'http://www.tei-c.org/ns/1.0'
J = 'http://jewishliturgy.org/ns/jlptei/2'
T = 'urn:x-opensiddur:text:'
FEATURE = 'urn:x-opensiddur:condition:poem:first_poem/later_service'


def module(urn, words):
    return etree.fromstring(
        f'<tei:TEI xmlns:tei="{TEI}" xmlns:j="{J}"><tei:text><tei:body>'
        f'<tei:div corresp="{urn}"><tei:pb n="1"/><tei:lg><tei:l>{words}</tei:l></tei:lg></tei:div>'
        f'</tei:body></tei:text></tei:TEI>')


def service(target):
    return etree.fromstring(
        f'<tei:TEI xmlns:tei="{TEI}" xmlns:j="{J}"><tei:text><tei:body><tei:div>'
        f'<tei:head>h</tei:head><j:transclude target="{target}"/><tei:p>after</tei:p>'
        f'</tei:div></tei:body></tei:text></tei:TEI>')


@mock.patch.object(printings, 'LATER_PRINTINGS', {'later_poem': ('first_poem', 'later_service')})
@mock.patch.object(printings, '_DECLARATIONS', {'first_poem_printed', 'first_poem_later_service'})
class TestUnify(unittest.TestCase):
    """A text printed twice in words that differ: one file, a variant branch per printing."""

    def documents(self, project):
        return [(project / 'first_poem.xml', module(T + 'poem:first_poem', 'first words')),
                (project / 'later_poem.xml', module(T + 'poem:later_poem', 'later words')),
                (project / 'first_service.xml', service(T + 'poem:first_poem')),
                (project / 'later_service.xml', service(T + 'poem:later_poem'))]

    def test_the_later_printing_is_a_branch_of_the_first(self):
        project = Path('p')
        documents, dropped = printings.unify(self.documents(project))
        self.assertEqual(dropped, [project / 'later_poem.xml'])
        by_name = {path.name: root for path, root in documents}
        self.assertNotIn('later_poem.xml', by_name)
        div = by_name['first_poem.xml'].find(f'.//{{{TEI}}}div')
        for value, words in (('false', 'first words'), ('true', 'later words')):
            branch = printings.branch(div, FEATURE, value == 'true')
            self.assertEqual(''.join(branch.itertext()), words)

    def test_each_service_declares_its_printing(self):
        documents, _ = printings.unify(self.documents(Path('p')))
        by_name = {path.name: root for path, root in documents}
        for name, value in (('first_service.xml', 'false'), ('later_service.xml', 'true')):
            div = by_name[name].find(f'.//{{{TEI}}}div')
            tags = [etree.QName(n).localname for n in div]
            self.assertEqual(tags, ['head', 'declare', 'transclude', 'endDeclare', 'p'])
            self.assertEqual(div.find(f'{{{J}}}transclude').get('target'), T + 'poem:first_poem')
            self.assertEqual(div.find(f'.//{{{TEI}}}f').get('name'), FEATURE)
            self.assertEqual(div.find(f'.//{{{TEI}}}binary').get('value'), value)
            # The verifiers see the service as the readings do: the declarations are the build's.
            self.assertEqual([etree.QName(n).localname for n in div if not printings.is_declaration(n)],
                             ['head', 'transclude', 'p'])

    def test_a_service_saying_the_text_twice_declares_each_with_its_own_id(self):
        project = Path('p')
        twice = service(T + 'poem:first_poem')
        div = twice.find(f'.//{{{TEI}}}div')
        div.append(etree.fromstring(f'<j:transclude xmlns:j="{J}" target="{T}poem:first_poem"/>'))
        later_too = service(T + 'poem:first_poem')
        later_too.find(f'.//{{{TEI}}}div').append(
            etree.fromstring(f'<j:transclude xmlns:j="{J}" target="{T}poem:later_poem"/>'))
        documents = self.documents(project)[:2] + [(project / 'twice.xml', twice), (project / 'both.xml', later_too)]
        by_name = {path.name: root for path, root in printings.unify(documents)[0]}
        ids = by_name['twice.xml'].xpath('//j:declare/@xml:id', namespaces={'j': J})
        self.assertEqual(ids, ['first_poem_printed', 'first_poem_printed_2'])
        self.assertEqual(by_name['twice.xml'].xpath('//j:endDeclare/@target', namespaces={'j': J}),
                         ['#first_poem_printed', '#first_poem_printed_2'])
        self.assertTrue(all(printings.is_declaration(n) for n in by_name['twice.xml'].iter(f'{{{J}}}declare')))
        # A service saying both printings declares each.
        values = by_name['both.xml'].xpath('//j:declare//tei:binary/@value', namespaces={'j': J, 'tei': TEI})
        self.assertEqual(sorted(values), ['false', 'true'])

    def test_a_branch_ends_at_its_own_end_only(self):
        div = module(T + 'poem:first_poem', 'first words').find(f'.//{{{TEI}}}div')
        printings._branch(div, FEATURE, False, 'first_poem_printed', [
            etree.fromstring(f'<j:conditional xmlns:j="{J}" xml:id="own"/>'),
            etree.fromstring(f'<tei:p xmlns:tei="{TEI}">kept</tei:p>'),
            etree.fromstring(f'<j:endConditional xmlns:j="{J}" target="#own"/>'),
            etree.fromstring(f'<tei:p xmlns:tei="{TEI}">still first</tei:p>')])
        printings._branch(div, FEATURE, True, 'first_poem_later_service',
                          [etree.fromstring(f'<tei:p xmlns:tei="{TEI}">later</tei:p>')])
        self.assertNotIn('later', ''.join(printings.branch(div, FEATURE, False).itertext()))
        self.assertIn('still first', ''.join(printings.branch(div, FEATURE, False).itertext()))
        self.assertNotIn('still first', ''.join(printings.branch(div, FEATURE, True).itertext()))

    def test_the_verifiers_find_each_printing_by_its_file_name(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            for path, root in printings.unify(self.documents(project))[0]:
                path.write_bytes(etree.tostring(root))
            self.assertEqual(''.join(printings.printing(project, 'later_poem').itertext()), 'later words')
            self.assertEqual(''.join(printings.printing(project, 'first_poem').itertext()), 'first words')
        self.assertEqual(printings.text_urn(T + 'poem:later_poem'), T + 'poem:first_poem')


@mock.patch.object(printings, 'LATER_PRINTINGS', {'first_poem_recension': ('first_poem', 'recension')})
@mock.patch.object(printings, '_DECLARATIONS', {'first_poem_printed', 'first_poem_recension'})
class TestRecension(unittest.TestCase):
    """A later printing the book names as a recension of the text keeps its child URN."""

    def test_the_recension_keeps_its_urn(self):
        recension = T + 'poem:first_poem/recension'
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            documents, dropped = printings.unify([
                (project / 'first_poem.xml', module(T + 'poem:first_poem', 'first words')),
                (project / 'first_poem_recension.xml', module(recension, 'fast words')),
                (project / 'fast_service.xml', service(recension))])
            by_name = {path.name: root for path, root in documents}
            self.assertEqual([p.name for p in dropped], ['first_poem_recension.xml'])
            self.assertEqual(by_name['first_poem.xml'].xpath('//tei:div/tei:div/@corresp', namespaces={'tei': TEI}),
                             [recension])
            fast = by_name['fast_service.xml']
            self.assertEqual(fast.find(f'.//{{{J}}}transclude').get('target'), T + 'poem:first_poem')
            self.assertEqual(fast.find(f'.//{{{TEI}}}f').get('name'),
                             'urn:x-opensiddur:condition:poem:first_poem/recension')
            for path, root in documents:
                path.write_bytes(etree.tostring(root))
            found = printings.printing(project, 'first_poem_recension')
            self.assertEqual((found.get('corresp'), ''.join(found.itertext())), (recension, 'fast words'))
        self.assertEqual(printings.text_urn(recension), T + 'poem:first_poem')


if __name__ == '__main__':
    unittest.main()
