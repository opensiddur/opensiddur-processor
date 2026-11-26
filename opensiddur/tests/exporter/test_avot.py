"""Avot schedule boundaries and independent explicit selection."""
import unittest
from pyluach.dates import HebrewDate
from opensiddur.exporter.calendar.avot import chapters_on,compute_avot,FS_AVOT
from opensiddur.exporter.calendar.compute import SettingSnapshot,FS_HEBREW_DATE,FS_ISRAEL
from opensiddur.exporter.conditional_settings import yaml_to_declaration_entries
from opensiddur.exporter.derived_settings import recalculate_derived_settings,SettingChangeTrigger,get_active_setting_entry
from opensiddur.exporter.linear import reset_linear_data,get_linear_data

class TestAvot(unittest.TestCase):
    def test_israel_diaspora_festival_boundaries(self):
        self.assertEqual(chapters_on(HebrewDate(5782,1,22),israel=True),(1,))
        self.assertEqual(chapters_on(HebrewDate(5782,1,22),israel=False),())
        self.assertEqual(chapters_on(HebrewDate(5783,3,7),israel=True),(1,))
        self.assertEqual(chapters_on(HebrewDate(5783,3,7),israel=False),())
        self.assertEqual(chapters_on(HebrewDate(5783,3,14),israel=False),(1,))
    def test_shabbat_before_shavuot_is_not_a_festival(self):
        self.assertEqual(chapters_on(HebrewDate(5784,3,2),israel=True),(6,))
        self.assertEqual(chapters_on(HebrewDate(5784,3,2),israel=False),(6,))

    def test_final_combined_chapters(self):
        self.assertEqual(chapters_on(HebrewDate(5783,6,9),israel=True),(2,))
        self.assertEqual(chapters_on(HebrewDate(5783,6,9),israel=False),(1,2))
        self.assertEqual(chapters_on(HebrewDate(5783,6,16),israel=False),(3,4))
        self.assertEqual(chapters_on(HebrewDate(5783,6,23),israel=False),(5,6))
    def test_non_reading_dates(self):
        for y,m,d in [(5784,1,24),(5782,5,9),(5781,5,8),(5783,7,6),(5784,1,19)]:
            self.assertEqual(chapters_on(HebrewDate(y,m,d),israel=True),())
    def test_unknown_inputs_stay_maybe(self):
        self.assertIsNone(compute_avot(SettingSnapshot(lambda f,k:None)))
        values=dict(year=5783,month=6,day=9)
        self.assertIsNone(compute_avot(SettingSnapshot(lambda f,k:values.get(k) if f==FS_HEBREW_DATE else None)))
    def test_all_six_explicit_chapters_survive_derivation(self):
        reset_linear_data()
        ld=get_linear_data()
        declarations={FS_HEBREW_DATE:dict(year=5783,month=6,day=9),FS_ISRAEL:{'is-israel':True},FS_AVOT:{f'chapter-{n}':True for n in range(1,7)}}
        ld.conditional_settings.extend(yaml_to_declaration_entries(declarations))
        recalculate_derived_settings(ld,trigger=SettingChangeTrigger.INIT)
        for n in range(1,7):self.assertIs(get_active_setting_entry(ld,FS_AVOT,f'chapter-{n}').value,True)
        reset_linear_data()
    def test_year_shapes_repeat_three_rounds_then_finish_at_six(self):
        for y in range(5770,5800):
            for israel in (True,False):
                day=HebrewDate(y,1,21);end=HebrewDate(y+1,7,1);chapters=[]
                while day<end:
                    chapters.extend(chapters_on(day,israel=israel));day+=1
                self.assertEqual(chapters[:18],list(range(1,7))*3,(y,israel))
                self.assertIn(chapters[18:],([1,2,3,4,5,6],[3,4,5,6]),(y,israel))

class TestAvotInstructionModes(unittest.TestCase):
    def test_a_selected_chapter_is_printed_without_its_selection_rubric(self):
        """The rubric says when a chapter is read; once that is known it is not printed."""
        import tempfile
        from pathlib import Path
        from opensiddur.exporter.compiler import CompilerProcessor
        from opensiddur.importer.birnbaum_scan.build.common import cond, endcond, feature

        for selected, expected_text, expected_instruction in [
            (True, True, False),
            (False, False, False),
            (None, True, True),
        ]:
            with self.subTest(selected=selected), tempfile.TemporaryDirectory() as tmp:
                reset_linear_data()
                ld=get_linear_data()
                ld.xml_cache.base_path=Path(tmp)
                folder=Path(tmp)/'synthetic';folder.mkdir()
                body=(cond('chapter',note='Selection rubric',fs=feature(FS_AVOT,'chapter-1'))
                      +'<tei:p>Chapter content</tei:p>'+endcond('chapter'))
                (folder/'text.xml').write_text(
                    '<root xmlns:tei="http://www.tei-c.org/ns/1.0" '
                    'xmlns:j="http://jewishliturgy.org/ns/jlptei/2"><tei:text>'
                    +body+'</tei:text></root>')
                CompilerProcessor.load_init_settings(ld,yaml_to_declaration_entries(
                    {FS_AVOT:{'chapter-1':selected}}))
                compiled=CompilerProcessor('synthetic','text.xml').process()
                text=''.join(compiled.itertext())
                self.assertEqual('Chapter content' in text,expected_text)
                self.assertEqual('Selection rubric' in text,expected_instruction)
        reset_linear_data()

    def test_siddur_caller_requires_season_and_a_selected_chapter(self):
        import tempfile
        from pathlib import Path
        from opensiddur.exporter.compiler import CompilerProcessor
        from opensiddur.importer.birnbaum_scan.build.avot import caller, ROOT, transclude

        # The seasonal rubric says when Avot is read, so a season known to hold prints Avot
        # without it, and only an undecided one keeps it.
        cases = [
            (True, False, False, False),
            (True, True, True, False),
            (False, True, False, False),
            (None, None, True, True),
        ]
        for season, selected, content, instruction in cases:
            with self.subTest(season=season, selected=selected), tempfile.TemporaryDirectory() as tmp:
                reset_linear_data()
                ld = get_linear_data()
                ld.xml_cache.base_path = Path(tmp)
                folder = Path(tmp) / 'synthetic'
                folder.mkdir()
                body = caller().replace(transclude(ROOT), '<tei:p>Avot content</tei:p>')
                (folder / 'text.xml').write_text(
                    '<root xmlns:tei="http://www.tei-c.org/ns/1.0" '
                    'xmlns:j="http://jewishliturgy.org/ns/jlptei/2"><tei:text>'
                    + body + '</tei:text></root>', encoding='utf-8')
                settings = {f'chapter-{n}': False for n in range(1, 7)}
                settings.update({'season': season, 'chapter-1': selected})
                CompilerProcessor.load_init_settings(ld, yaml_to_declaration_entries({FS_AVOT: settings}))
                compiled = CompilerProcessor('synthetic', 'text.xml').process()
                text = ''.join(compiled.itertext())
                self.assertEqual('Avot content' in text, content)
                self.assertEqual('Recited on the Sabbaths between Pesaḥ and Rosh Hashanah' in text, instruction)
        reset_linear_data()
