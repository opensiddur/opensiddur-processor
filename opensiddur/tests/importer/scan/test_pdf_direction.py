"""Direction must follow glyph coordinates, not extractor ordering."""
from contextlib import redirect_stdout
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from lxml import etree
from opensiddur.importer.scan import pdf_direction as d


class DirectionTests(unittest.TestCase):
    def test_letter_normalization_and_nonletters(self):
        self.assertEqual(d.letters('a אֶב1ג׃'), 'אבג')
        self.assertEqual(d.base('שׁ'),'ש')
        self.assertEqual(d.base('\ue802'),'ך')
        self.assertIsNone(d.base('.'))
        self.assertIsNone(d.base('\ufb1e'))  # A point-only compatibility glyph.
        self.assertEqual(d.score('אבגדה',{'אבגד','בגדה'}),2)
        self.assertEqual(d.score('אב',{'אבגד'}),0)

    def test_runs_sort_coordinates_preserve_spaces_and_skip_points(self):
        line=etree.Element('line')
        for char,x in [('ה',1),('ד',2),(' ',3),('ג',4),('ב',5),('א',6),('ָ',6),('.',7),('ז',8),('',9)]:
            etree.SubElement(line,'char',c=char,x=str(x))
        self.assertEqual(d.runs_of(line),['הדגבא','ז'])

    def extract(self,root,text):
        p=root/'glyphs.xml';document=etree.Element('document');page=etree.SubElement(document,'page',id='page3')
        row=etree.SubElement(page,'line',bbox='0 120 200 140')
        for x,c in enumerate(text):etree.SubElement(row,'char',c=c,x=str(x))
        p.write_bytes(etree.tostring(document));return p

    def test_measured_direction_and_reversal_control(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);tex=root/'source.tex';tex.write_text('אבגדה',encoding='utf-8')
            corpus=d.corpus_of(tex);self.assertEqual(corpus,{'אבגד','בגדה'})
            extracted=self.extract(root,'הדגבא.אב')
            self.assertEqual(d.check(extracted,corpus),([],1))
            flagged,total=d.check(extracted,corpus,reverse=True)
            self.assertEqual((flagged,total),([(3,120,'אבגדה')],1))

    def test_cli_failure_and_unverifiable_controls(self):
        cases=[(([],1),([],1),['--control'],2),
               (([],0),None,[],2),
               (([(1,10,'אבגד')],1),None,[],1),
               (([],1),([(1,10,'אבגד')],1),['--control'],0)]
        for actual,control,args,expected in cases:
            with self.subTest(actual=actual,args=args),patch.object(d,'corpus_of',return_value=set()),patch.object(d,'stext',return_value=Path('/tmp/fake')),patch.object(d,'check',side_effect=[actual,control]),redirect_stdout(io.StringIO()):
                self.assertEqual(d.main(['fake.pdf','fake.tex']+args),expected)

    def test_extraction_invokes_mutool_and_returns_output_path(self):
        with TemporaryDirectory() as tmp,patch.object(d.tempfile,'mkdtemp',return_value=tmp),patch.object(d.subprocess,'run') as run:
            pdf=Path('/tmp/input.pdf');out=d.stext(pdf)
            self.assertEqual(out,Path(tmp)/'stext.xml')
            run.assert_called_once_with(['mutool','draw','-F','stext','-o',str(out),str(pdf)],check=True,capture_output=True)
