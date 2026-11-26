"""Helpers the Asher PDF checks share: corrected reading text, whole Hebrew rows, line numbers."""
import json
import tempfile
import unittest
from pathlib import Path

from lxml import etree

from opensiddur.importer.asher_selichot.check_pdf import (
    corrected,
    hebrew_rows,
    load_glyphs,
    strip_line_numbers,
)


class CorrectedReadingTests(unittest.TestCase):
    def test_reading_text_is_read_with_its_corrections(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            (source / 'scan_reading').mkdir()
            (source / 'scan_reading/corrections.json').write_text(json.dumps({'corrections': [
                {'id': 'cite', 'before': 'Jer. iii. ', 'sic': '2.', 'corr': '3.', 'after': ''},
                {'id': 'exact', 'exact': True, 'sic': 'x', 'corr': 'y'},
                {'id': 'follows', 'follows': 'z', 'sic': '”', 'corr': ''}]}))
            self.assertEqual('See Jer. iii. 3. and x”', corrected('See Jer. iii. 2. and x”', source))

    def test_without_a_corrections_file_the_text_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual('Jer. iii. 2.', corrected('Jer. iii. 2.', Path(temp)))


def glyphs(*lines):
    """A one-page mutool glyph document; each line is (bbox, [(char, x, y)])."""
    page = etree.Element('page', width='612', height='792')
    for bbox, chars in lines:
        line = etree.SubElement(page, 'line', bbox=' '.join(map(str, bbox)), text=''.join(c for c, _, _ in chars))
        font = etree.SubElement(line, 'font', size='12')
        for c, x, y in chars:
            etree.SubElement(font, 'char', c=c, x=str(x), y=str(y))
    document = etree.Element('document')
    document.append(page)
    return document


class HebrewRowTests(unittest.TestCase):
    def word_split_row(self):
        # One Hebrew row that mutool split per word, one fragment carrying a margin line number,
        # beside an English line on the same baseline.
        return glyphs(((240, 100, 280, 112), [('א', 270, 110), ('ש', 262, 110)]),
                      ((60, 100, 230, 112), [('5', 60, 110), ('ר', 220, 110), ('י', 212, 110)]),
                      ((330, 100, 500, 112), [('H', 330, 110), ('i', 338, 110)]),
                      ((240, 120, 280, 132), [('ב', 270, 130)]))

    def test_a_row_is_read_whole_and_right_to_left(self):
        page = self.word_split_row().find('page')
        self.assertEqual([(110.0, 'אשרי'), (130.0, 'ב')], hebrew_rows(page, 288))

    def test_adjacent_hebrew_fragments_join_but_numbered_and_english_lines_do_not(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'g.xml'
            path.write_bytes(etree.tostring(glyphs(
                ((240, 100, 280, 112), [('א', 270, 110)]), ((200, 100, 236, 112), [('ב', 220, 110)]),
                ((60, 100, 190, 112), [('5', 60, 110), ('ג', 180, 110)]),
                ((330, 100, 500, 112), [('H', 330, 110)]))))
            lines = load_glyphs(path).findall('.//line')
        self.assertEqual(['א ב', '5ג', 'H'], [line.get('text') for line in lines])


class LineNumberTests(unittest.TestCase):
    def test_line_numbers_go_and_citations_stay(self):
        self.assertEqual('O Lord, be thou', strip_line_numbers('O Lord, 15 be thou'))
        self.assertEqual('mercy when', strip_line_numbers('mercy 10 when'))
        self.assertEqual('pp. 11, 12. and', strip_line_numbers('pp. 11, 12. and'))
        self.assertEqual('Job xxxiii. 24, and', strip_line_numbers('Job xxxiii. 24, and'))


if __name__ == '__main__':
    unittest.main()
