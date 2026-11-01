"""A public passage's inherited quorum tests must not split the prayer."""
from pathlib import Path
import tempfile
import unittest
from lxml import etree as E

from opensiddur.exporter.compiler import CompilerProcessor
from opensiddur.exporter.conditional_settings import yaml_to_declaration_entries
from opensiddur.exporter.linear import get_linear_data, reset_linear_data
from opensiddur.importer.birnbaum_scan.build import build_he, common
from opensiddur.importer.siddur_expanded.compose import Composer
from opensiddur.importer.siddur_expanded.xml import Author, T, J, NS, feature, parse_fragment, serialize


class SyntheticPrayers(dict):
    def __missing__(self, key):
        self[key] = {'urn': 'urn:x-opensiddur:text:prayer:fixture/'+key}
        return self[key]


class TestPublicContext(unittest.TestCase):
    def compile(self, body, quorum):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'fixture').mkdir()
            (root/'fixture/index.xml').write_text(f'<root xmlns:tei="{T}" xmlns:j="{J}">{body}</root>')
            reset_linear_data(); self.addCleanup(reset_linear_data)
            data=get_linear_data(); data.xml_cache.base_path=root
            CompilerProcessor.load_init_settings(data,yaml_to_declaration_entries({
                'opensiddur:quorum': {'minyan':quorum}}))
            processor=CompilerProcessor('fixture','index.xml')
            before=processor.get_active_setting('opensiddur:quorum','minyan')
            result=processor.process()
            self.assertEqual(processor.get_active_setting('opensiddur:quorum','minyan'),before)
            self.assertFalse(data.conditional_scope_stack)
            return result

    def test_entire_morning_kaddish_is_gated_in_both_languages(self):
        for project in [common.PROJECT_HE,common.PROJECT_EN]:
            lines=[]; build_he._emit(lines,project,SyntheticPrayers(),build_he.ISHMAEL_ORDER)
            tree=parse_fragment('\n'.join(lines))
            # Replace prayer references with synthetic leaves, keeping the real scopes.
            for node in list(tree.iter('{'+J+'}transclude')):
                leaf=E.Element('{'+T+'}p'); leaf.text=node.get('target').rsplit('/',1)[-1]
                node.getparent().replace(node,leaf)
            for quorum in [None,False,True]:
                with self.subTest(project=project,quorum=quorum):
                    result=self.compile(''.join(serialize(e) for e in tree),quorum)
                    prayers=result.xpath('.//tei:p/text()',namespaces=NS)
                    for part in ['yitgaddal','yehe_shemeh','yitbarakh','al_yisrael','yehe_shelama','oseh_shalom']:
                        self.assertEqual('kaddish_derabbanan_'+part in prayers,quorum is not False)
                    self.assertEqual(bool(result.xpath('.//tei:head[contains(.,"KADDISH") or contains(.,"קַדִּישׁ")]',namespaces=NS)),quorum is not False)
                    self.assertIn('ishmael_yehi_ratzon',prayers)

    def test_public_context_resolves_nested_quorum_without_forcing_outer_gate(self):
        author=Author(); minyan=feature('quorum','minyan')
        inner=author.gate(minyan,'<tei:p>Middle paragraph</tei:p>','Inner quorum instruction')
        body=author.gate(minyan,'<tei:head>Whole prayer</tei:head><tei:p>Opening</tei:p>'+inner+'<tei:p>Closing</tei:p>','With a minyan:')
        tree=parse_fragment(body)
        Composer.declare_public_context(tree)
        outside=author.gate(minyan,'<tei:p>Later public passage</tei:p>')
        for quorum in [None,False,True]:
            with self.subTest(quorum=quorum):
                result=self.compile(''.join(serialize(e) for e in tree)+outside,quorum)
                prayers=result.xpath('.//tei:p/text()',namespaces=NS)
                self.assertEqual('Middle paragraph' in prayers,quorum is not False)
                self.assertEqual('Opening' in prayers,quorum is not False)
                self.assertEqual('Closing' in prayers,quorum is not False)
                gates=result.xpath('.//j:conditional',namespaces=NS)
                self.assertEqual(len(gates),2 if quorum is None else 0)
                self.assertNotIn('Inner quorum instruction',''.join(result.itertext()))

    def test_negative_or_compound_quorum_gate_does_not_declare_a_minyan(self):
        author=Author(); minyan=feature('quorum','minyan')
        for predicate in [feature('quorum','minyan',False),'<j:none>'+minyan+'</j:none>',
                          '<j:all>'+minyan+feature('recitation','repetition')+'</j:all>']:
            tree=parse_fragment(author.gate(predicate,'<tei:p>Passage</tei:p>'))
            Composer.declare_public_context(tree)
            self.assertFalse(tree.xpath('.//j:declare',namespaces=NS))
