"""Page layout can put a line number and a footnote marker between prayer words."""
import subprocess
import sys
import unittest

from lxml import etree

from opensiddur.importer.asher_selichot.check_penitential_fifth_pdf import (
    ANCHORS,
    check,
)


class FifthPdfMarkersTests(unittest.TestCase):
    def fixture(self, missing=False, after_punctuation=False):
        root=etree.Element('document');page=etree.SubElement(root,'page');y=90
        def row(he='',en='',size='12'):
            nonlocal y
            y+=20;line=etree.SubElement(page,'line',text=he+' '+en)
            font=etree.SubElement(line,'font',name='fixture',size=size)
            for i,c in enumerate(he):
                x=250-i;etree.SubElement(font,'char',c=c,x=str(x),y=str(y),quad=f'{x} {y-10} {x+1} {y-10} {x} {y} {x+1} {y}')
            for i,c in enumerate(en):
                x=350+i;etree.SubElement(font,'char',c=c,x=str(x),y=str(y),quad=f'{x} {y-10} {x+1} {y-10} {x} {y} {x+1} {y}')
        row(en='Pardon us, our Father! People of the Lord, let us be courageous')
        for he,en in ANCHORS:row(he,en)
        for _ in range(2):row('לעלאלעלאמןכלברכתא','being; 35 an Omnipotent God' if after_punctuation else 'being; an Omnipotent God')
        for _ in range(8):row(en='Omnipotent King, who')
        for _ in range(9 if missing else 10):row(en='take us for thy heritage.')
        row(en='take 5 509 us for thy heritage.')
        row(en='May the prayers and supplications')
        for note in ['Which man has contracted towards God by his sins.', 'With allusion to Isa. i. 3.', 'Ps. cii. 28.', 'Gen. xii. 8.', 'See Jer. xxxi. 22.', 'With reference to Job xxxiii. 29.']:
            row(en=note,size='9')
        return root

    def test_consecutive_line_and_footnote_markers_do_not_hide_a_prayer(self):
        check(self.fixture(),expanded=True)

    def test_an_actually_missing_prayer_is_still_rejected(self):
        with self.assertRaisesRegex(ValueError,'repeat the complete thirteen-attributes'):
            check(self.fixture(missing=True),expanded=True)

    def test_line_number_after_punctuation_does_not_hide_a_prayer(self):
        check(self.fixture(after_punctuation=True),expanded=True)


class NumericMarkerRuntimeTests(unittest.TestCase):
    def test_long_nonmarker_digit_run_does_not_backtrack_exponentially(self):
        # A failed trailing boundary triggered the previous nested repetition.
        # Bound the child process so a regression fails without hanging the suite.
        code="from opensiddur.importer.scan.pdf import strip_numeric_markers; text='a'+'0'*20000+'x'; assert strip_numeric_markers(text)==text"
        subprocess.run([sys.executable,'-c',code],check=True,timeout=5,capture_output=True)
