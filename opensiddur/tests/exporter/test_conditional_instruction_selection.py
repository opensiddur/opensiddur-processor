"""A resolved conditional rubric still uses the edition's instruction selection."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from lxml import etree
from opensiddur.exporter.compiler import CompilerProcessor
from opensiddur.exporter.external_compiler import ExternalCompilerProcessor
from opensiddur.exporter.inline_compiler import InlineCompilerProcessor
from opensiddur.exporter.linear import LinearData
from opensiddur.exporter.refdb import ReferenceDatabase, UrnMapping

TEI='http://www.tei-c.org/ns/1.0'
J='http://jewishliturgy.org/ns/jlptei/2'
URN='urn:x-opensiddur:instruction:aseret_yemei_teshuvah/add'


class ConditionalInstructionSelectionTests(unittest.TestCase):
    def compile(self, selected, processor_class, note_type='instruction', inside=False):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        base=Path(temp.name)
        for project in ['book','instructions']:(base/project).mkdir()
        rubric=f'<tei:note type="{note_type}" corresp="{URN}">Original rubric</tei:note>'
        body=f'''<tei:p>Before <j:declare xml:id="d"><tei:fs type="test"><tei:f name="include"><tei:binary value="true"/></tei:f></tei:fs></j:declare>
          <j:conditional xml:id="c">{'' if inside else rubric}
          <tei:fs type="test"><tei:f name="include"><tei:binary value="true"/></tei:f></tei:fs></j:conditional>{rubric if inside else ''}Included
          <j:endConditional target="#c"/> After<j:endDeclare target="#d"/></tei:p>'''
        wrapper=lambda content:f'<tei:TEI xmlns:tei="{TEI}" xmlns:j="{J}" xml:lang="en"><tei:text><tei:body>{content}</tei:body></tei:text></tei:TEI>'
        (base/'book'/'text.xml').write_text(wrapper(body))
        replacement=etree.fromstring(wrapper(f'<tei:note type="{note_type}" corresp="{URN}">{selected}</tei:note>').encode())
        (base/'instructions'/'text.xml').write_bytes(etree.tostring(replacement))
        note=replacement.find('.//{'+TEI+'}note')
        refdb=MagicMock(spec=ReferenceDatabase)
        refdb.get_references_to.return_value=[]
        refdb.get_urn_mappings.return_value=[UrnMapping(urn=URN,project='instructions',file_name='text.xml',element_path=note.getroottree().getpath(note),element_tag=note.tag,element_type='instruction')]
        data=LinearData(instruction_priority=['instructions','book']);data.xml_cache.base_path=base
        kwargs={'from_start':None,'to_end':None} if processor_class is InlineCompilerProcessor else {}
        result=processor_class('book','text.xml',linear_data=data,reference_database=refdb,**kwargs).process()
        roots=result if isinstance(result,list) else [result]
        return ' '.join(' '.join(''.join(n.itertext()).split()) for n in roots),roots

    def test_true_conditional_prints_no_instruction_in_any_wording(self):
        for cls in [CompilerProcessor,ExternalCompilerProcessor,InlineCompilerProcessor]:
            with self.subTest(processor=cls.__name__):
                text,_=self.compile('Selected rubric',cls)
                self.assertNotIn('Selected rubric',text)
                self.assertNotIn('Original rubric',text)
                self.assertIn('Included',text);self.assertIn('After',text)

    def test_a_description_inside_a_true_scope_uses_the_selected_wording(self):
        for cls in [CompilerProcessor,ExternalCompilerProcessor,InlineCompilerProcessor]:
            with self.subTest(processor=cls.__name__):
                text,_=self.compile('Selected description',cls,note_type='description',inside=True)
                self.assertIn('Selected description',text)
                self.assertNotIn('Original rubric',text)
                self.assertIn('Included',text)

    def test_selected_empty_instruction_omits_fulfilled_rubric_and_keeps_tail(self):
        for cls in [CompilerProcessor,ExternalCompilerProcessor,InlineCompilerProcessor]:
            with self.subTest(processor=cls.__name__):
                text,roots=self.compile('',cls)
                self.assertEqual(text,'Before Included After')
                self.assertFalse(any(n.findall('.//{'+TEI+'}note') for n in roots))


class LocalRubricSelectionTests(unittest.TestCase):
    def test_same_edition_keeps_each_local_wording_language_and_tail(self):
        for cls in [CompilerProcessor, ExternalCompilerProcessor]:
            for note_type in ['instruction','description']:
                with self.subTest(processor=cls.__name__,kind=note_type):
                    temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
                    base=Path(temp.name);(base/'book').mkdir()
                    wrapper=lambda content:f'<tei:TEI xmlns:tei="{TEI}" xmlns:j="{J}" xml:lang="he"><tei:text><tei:body>{content}</tei:body></tei:text></tei:TEI>'
                    original=f'<tei:p><tei:note type="{note_type}" corresp="{URN}" xml:lang="he">קו״ח</tei:note> First tail <tei:note type="{note_type}" corresp="{URN}" xml:lang="he">ק׳</tei:note> Second tail</tei:p>'
                    (base/'book/local.xml').write_text(wrapper(original),encoding='utf-8')
                    other=etree.fromstring(wrapper(f'<tei:note type="{note_type}" corresp="{URN}" xml:lang="en">Congregation:</tei:note>').encode())
                    (base/'book/other.xml').write_bytes(etree.tostring(other));note=other.find('.//{'+TEI+'}note')
                    db=MagicMock(spec=ReferenceDatabase);db.get_references_to.return_value=[]
                    db.get_urn_mappings.return_value=[UrnMapping(urn=URN,project='book',file_name='other.xml',element_path=note.getroottree().getpath(note),element_tag=note.tag,element_type=note_type)]
                    data=LinearData(instruction_priority=['book']);data.xml_cache.base_path=base
                    result=cls('book','local.xml',linear_data=data,reference_database=db).process()
                    roots=result if isinstance(result,list) else [result]
                    notes=[n for root in roots for n in root.findall('.//{'+TEI+'}note')]
                    self.assertEqual([''.join(n.itertext()) for n in notes],['קו״ח','ק׳'])
                    self.assertEqual([n.get('{http://www.w3.org/XML/1998/namespace}lang') for n in notes],['he','he'])
                    self.assertIn('First tail',''.join(''.join(root.itertext())for root in roots));self.assertIn('Second tail',''.join(''.join(root.itertext())for root in roots))
