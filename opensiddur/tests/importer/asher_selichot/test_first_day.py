"""Synthetic checks for source boundaries, page crossings and printed apparatus."""
import unittest
from lxml import etree
from opensiddur.importer.asher_selichot.first_day import section, TEI, XML
from opensiddur.importer.asher_selichot.identities import project_name
from opensiddur.importer.scan.reverse import streams


class FirstDayTest(unittest.TestCase):
    def test_single_hebrew_letter_does_not_reverse_english_note(self):
        from opensiddur.importer.asher_selichot.first_day import words_with_notes
        parent = etree.Element(f'{{{TEI}}}p')
        text = 'With reference to Job xxxiii. 29. See also Talmud Joma, 86, א.'
        words_with_notes(parent, 'countenance;',
                         [{'anchor': 'countenance;', 'text': text}], 'en')
        note = parent.find(f'{{{TEI}}}note')
        self.assertEqual('en', note.get(XML+'lang'))
        self.assertEqual('With reference to Job xxxiii. 29. See also Talmud Joma, 86, ', note.text)
        foreign = note.find(f'{{{TEI}}}foreign')
        self.assertEqual('א', foreign.text)
        self.assertEqual('.', foreign.tail)
        self.assertEqual(text, ''.join(note.itertext()))

    def test_rendered_litany_rejects_collapsed_verses_and_lost_refrains(self):
        from opensiddur.importer.asher_selichot.check_first_day_pdf import check_mi_sheanah
        rows = [(1, n*15, 'מישענהאבינוהואיעננו') for n in range(20)]
        check_mi_sheanah(rows)
        with self.assertRaisesRegex(ValueError, '20 distinct verse starts'):
            check_mi_sheanah([(1, 100, row[2]) for row in rows])
        with self.assertRaisesRegex(ValueError, '20 refrains'):
            check_mi_sheanah([row if n else (1, 0, 'מישענהאבינו') for n,row in enumerate(rows)])

    def test_hebrew_litany_is_verse_with_terminal_refrains(self):
        from opensiddur.importer.asher_selichot.verify import check_poetry
        group = {'id':'mi_sheanah', 'kind':'litany', 'fragments':[
            self.fragment('s46', 'מי שענה לאברהם הוא יעננו׃\nמי שענה ליצחק הוא יעננו׃')]}
        rule = {'line_stops':'׃', 'line_count':2, 'refrain':'הוא יעננו', 'refrain_count':2}
        root = section('he', 'fixture', 'closing', [group], {'mi_sheanah':rule})
        unit = root.find(f'.//{{{TEI}}}body/{{{TEI}}}div/{{{TEI}}}div')
        check_poetry(unit, rule)
        self.assertEqual(['הוא יעננו׃']*2,
            [n.text for n in unit.findall(f'.//{{{TEI}}}seg')])
        self.assertEqual('מי שענה לאברהם הוא יעננו׃ מי שענה ליצחק הוא יעננו׃', streams(root)[('s46','he')])
        # Same words in prose must fail the structural audit.
        unit.find(f'{{{TEI}}}lg').tag = f'{{{TEI}}}p'
        with self.assertRaisesRegex(ValueError, 'verse structure'):
            check_poetry(unit, rule)

    def test_poetic_line_crosses_source_page_without_new_verse(self):
        group = {'id':'ashamnu_mikol', 'kind':'prose', 'fragments':[
            self.fragment('s38', 'אשמנו מכל עם · גלה ממנו'),
            self.fragment('s40', 'משוש · דוה לבנו׃', [{'anchor':'דוה לבנו׃', 'text':'הערת דפוס׃'}])]}
        root = section('he', 'fixture', 'closing', [group],
                       {'ashamnu_mikol':{'line_stops':'·׃'}})
        lines = root.findall(f'.//{{{TEI}}}lg/{{{TEI}}}l')
        self.assertEqual(3, len(lines))
        self.assertEqual('גלה ממנו משוש\u00a0·', ''.join(lines[1].itertext()).strip())
        self.assertIsNotNone(lines[1].find(f'{{{TEI}}}pb'))
        self.assertEqual(1, len(lines[2].findall(f'{{{TEI}}}note')))
        english = section('en', 'fixture', 'closing', [group],
                          {'ashamnu_mikol':{'line_stops':'·׃'}})
        self.assertEqual([], english.findall(f'.//{{{TEI}}}lg'))
        self.assertEqual(1, len(english.findall(f'.//{{{TEI}}}body//{{{TEI}}}p')))

    def test_missing_or_displaced_refrain_fails_structure_audit(self):
        from opensiddur.importer.asher_selichot.verify import check_poetry
        group = {'id':'anenu', 'kind':'prose', 'fragments':[self.fragment('s44', 'עננו אבינו עננו׃')]}
        rule = {'line_stops':'׃', 'line_count':1, 'refrain':'עננו', 'refrain_count':1}
        root = section('he','fixture','closing',[group], {'anenu':rule})
        unit = root.find(f'.//{{{TEI}}}body/{{{TEI}}}div/{{{TEI}}}div')
        refrain = unit.find(f'.//{{{TEI}}}seg')
        refrain.tail = 'extra'
        with self.assertRaisesRegex(ValueError, 'end its verse'):
            check_poetry(unit, rule)
        refrain.tail = None
        refrain.attrib.clear()
        with self.assertRaisesRegex(ValueError, 'refrain count'):
            check_poetry(unit, rule)

    def test_poem_cue_selects_printed_instruction_or_its_prayers(self):
        """Shared services must supply this conclusion once without a view wrapper."""
        import tempfile
        from pathlib import Path
        from opensiddur.importer.asher_selichot.build import poem, J, PRAYER
        from opensiddur.exporter.compiler import CompilerProcessor
        from opensiddur.exporter.conditional_settings import yaml_to_declaration_entries
        from opensiddur.exporter.linear import LinearData
        for lang in ('he', 'en'):
            for supplied in (False, True):
                with self.subTest(lang=lang, supplied=supplied), tempfile.TemporaryDirectory() as temp:
                    root=poem(lang, 'fixture', {
                        'heading':'Poem', 'rubric':'Repeat the refrain.',
                        'stanzas':[['שורה׃']] if lang=='he' else ['Poem words.'],
                        'cues':{}, 'conclusion':'Say the printed prayers.'})
                    references=root.findall(f'.//{{{J}}}transclude')
                    self.assertEqual([PRAYER+'el_melekh_yoshev', PRAYER+'vayaavor'],
                                     [n.get('target') for n in references])
                    for number,reference in enumerate(references,1):
                        replacement=etree.Element(f'{{{TEI}}}p')
                        replacement.text=f'Supplied prayer {number}.'
                        reference.getparent().replace(reference,replacement)
                    project=Path(temp)/'fixture';project.mkdir()
                    (project/'index.xml').write_bytes(etree.tostring(root))
                    data=LinearData();data.xml_cache.base_path=Path(temp)
                    CompilerProcessor.load_init_settings(data, yaml_to_declaration_entries({
                        'asher:expansions': {'prayers_present':supplied}}))
                    output=CompilerProcessor('fixture','index.xml',linear_data=data).process()
                    words=' '.join(output.find(f'{{{TEI}}}text').itertext())
                    self.assertEqual(not supplied, 'Say' in words)
                    for number in (1,2):
                        self.assertEqual(int(supplied),words.count(f'Supplied prayer {number}.'))

    def test_reusable_modules_use_common_names_and_distinctive_incipits(self):
        """Service position/evidence IDs must not become a reusable text identity."""
        import json
        import tempfile
        from pathlib import Path
        from opensiddur.importer.asher_selichot.first_day import documents
        from opensiddur.importer.asher_selichot.identities import TEXTS, text_urn
        title = {'scan':'s3', 'titles':['Selichoth'], 'edition':'Translation',
                 'place':'London', 'publisher':'Vallentine', 'address':'Duke Street', 'date':'1912'}
        opening = {'start_scan':'s6', 'next_scan':'s8', 'next_label':'3',
                   'heading':'First day', 'rubrics':[], 'kaddish_rubrics':[],
                   'prelude':['Opening verse.', 'Second verse.'], 'psalm':['Psalm verse.']*21,
                   'verse_9_continuation':'Continuation.', 'postlude':'Conclusion.',
                   'kaddish_preface':['Preface.', 'Remember.']}
        poem_ids = ['ein_mi_yiqra', 'im_avoneinu', 'tavo_lefanekha_selihah']
        groups = [{'id':identity, 'kind':'poem', 'incipit_he':'Distinctive incipit',
                   'fragments':[self.fragment('s22', 'Original piyyut words.')]}
                  for identity in poem_ids]
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            (source/'title-pages.json').write_text(json.dumps({'he':title,'en':title}))
            readings = {lang:dict(opening, kaddish=['First part.',
                'Blessed. '+('יִתְבָּרַךְ' if lang=='he' else 'and may his hallowed')+(' לְעֵלָּא מִן כָּל׃' if lang=='he' else ' name.')])
                for lang in ('he','en')}
            (source/'first-day-opening.json').write_text(json.dumps(readings))
            (source/'first-day-continuation.json').write_text(json.dumps({'sections':{'preface':groups}}))
            modules = {(project,filename):root for project,filename,root in documents(source)}
        j = '{http://jewishliturgy.org/ns/jlptei/2}'
        for lang in ('he','en'):
            project = project_name(lang)
            with self.subTest(lang=lang):
                index = modules[project,'index.xml']
                self.assertIsNotNone(index.find(f'.//{{{TEI}}}front/{{{TEI}}}titlePage'))
                self.assertEqual('urn:x-opensiddur:text:siddur:selichot@'+project,
                    index.find(f'.//{{{TEI}}}idno[@type="urn"]').text)
                first_day=modules[project,'first_day.xml']
                self.assertEqual('urn:x-opensiddur:text:siddur:selichot/first_day',
                    first_day.find(f'.//{{{TEI}}}body/{{{TEI}}}div').get('corresp'))
                for filename,urn in [('ashrei.xml','prayer:ashrei'),('kaddish_chatzi.xml','prayer:kaddish/chatzi')]:
                    module=modules[project,filename]
                    self.assertEqual('urn:x-opensiddur:text:'+urn+'@'+project,
                        module.find(f'.//{{{TEI}}}idno[@type="urn"]').text)
                assembly=modules[project,'first_day.xml']
                references=assembly.findall(f'.//{j}transclude')
                self.assertEqual([text_urn(identity) for identity in poem_ids],
                                 [node.get('target') for node in references][3:])
                from opensiddur.importer.asher_selichot.first_day import OBSOLETE_ASSEMBLIES
                self.assertTrue(all((project,name+'.xml') not in modules for name in OBSOLETE_ASSEMBLIES))
                for filename in ('index.xml', 'expanded.xml'):
                    self.assertEqual(['urn:x-opensiddur:text:siddur:selichot/first_day'],
                        [n.get('target') for n in modules[project,filename].findall(f'.//{j}transclude')])
                self.assertNotIn('Original piyyut words.',etree.tostring(assembly,encoding='unicode'))
                for identity in poem_ids:
                    filename=TEXTS[identity][0]+'.xml'
                    module=modules[project,filename]
                    self.assertIn('Original piyyut words.',etree.tostring(module,encoding='unicode'))
                    self.assertEqual(text_urn(identity)+'@'+project,
                        module.find(f'.//{{{TEI}}}idno[@type="urn"]').text)
                    self.assertNotIn('first_day',text_urn(identity))
                    self.assertNotIn('asher',text_urn(identity))
                self.assertNotIn('pilot',etree.tostring(index,encoding='unicode').lower())

    def fragment(self, scan, text, notes=(), kind='prose'):
        return {'he': {'scan':scan,'printed_page':'16','text':text},
                'en': {'scan':scan,'printed_page':'16','text':text},
                'notes': {'he':list(notes),'en':list(notes)}}

    def render(self, fragments, lang='en', kind='prose'):
        return section(lang,'fixture','closing',[{'id':'test','kind':kind,'fragments':fragments}])

    def test_page_crossing_retains_one_paragraph_and_joins_word(self):
        first=self.fragment('s35','a trans');first['en']['join_next']=True
        root=self.render([first,self.fragment('s37','gression ends.')])
        paragraphs=root.findall(f'.//{{{TEI}}}body//{{{TEI}}}p')
        self.assertEqual(1,len(paragraphs))
        self.assertEqual('a transgression ends.', ''.join(paragraphs[0].itertext()).strip())
        self.assertEqual({('s35','en'):'a trans',('s37','en'):'gression ends.'},streams(root))
        self.assertIn('/n36_medium.jpg',paragraphs[0].find(f'{{{TEI}}}pb').get('facs'))

    def test_repeated_anchor_places_distinct_notes_once_in_source_order(self):
        root=self.render([self.fragment('s35','as written, first. as written, second.',
            [{'anchor':'as written,','text':'First citation.'},{'anchor':'as written,','text':'Second citation.'}])])
        notes=root.findall(f'.//{{{TEI}}}note')
        self.assertEqual(['First citation.','Second citation.'],[n.text for n in notes])
        self.assertEqual(' first. as written,',notes[0].tail)
        self.assertEqual(' second. ',notes[1].tail)

    def test_missing_footnote_anchor_fails_before_authoring(self):
        with self.assertRaisesRegex(ValueError,'Footnote anchor absent'):
            self.render([self.fragment('s35','Different words.',[{'anchor':'not here','text':'note'}])])

    def test_mixed_final_rubric_preserves_languages_and_stops_at_boundary(self):
        root=self.render([self.fragment('s52','The Reader says קדיש תתקבל.')],lang='he',kind='rubric')
        note=root.find(f'.//{{{TEI}}}note')
        self.assertEqual('en',note.get(XML+'lang'))
        self.assertEqual('he',note.find(f'{{{TEI}}}foreign').get(XML+'lang'))
        self.assertEqual('The Reader says קדיש תתקבל.', ''.join(note.itertext()).strip())
        self.assertNotIn('SECOND DAY',etree.tostring(root,encoding='unicode'))

    def test_litany_has_printed_line_breaks_and_reader_note_once(self):
        words='\n'.join(f'Answer {n}.' for n in range(1,10))
        root=self.render([self.fragment('s47',words,[{'anchor':'Answer 8.','text':'Numbers xxv 7.'}])],kind='litany')
        self.assertEqual(8,len(root.findall(f'.//{{{TEI}}}lb')))
        self.assertEqual(1,len(root.findall(f'.//{{{TEI}}}note')))
        self.assertEqual(' '.join(words.split()),streams(root)[('s47','en')])

    def test_piyyut_invocation_is_body_text_in_both_languages(self):
        fragment = self.fragment('s22', '')
        fragment['he']['text'] = 'אלהינו ואלהי אבותינו\nאין מי יקרא בצדק׃'
        fragment['en']['text'] = 'Our God and the God of our fathers.\nNo one calleth upon thee.'
        for lang in ('he', 'en'):
            with self.subTest(lang=lang):
                root = self.render([fragment], lang=lang, kind='poem')
                body = root.find(f'.//{{{TEI}}}body')
                self.assertEqual([], body.findall(f'.//{{{TEI}}}head'))
                self.assertEqual(' '.join(fragment[lang]['text'].split()),
                                 streams(root)[('s22', lang)])
                if lang == 'he':
                    lines = body.findall(f'.//{{{TEI}}}lg/{{{TEI}}}l')
                    self.assertEqual(['אלהינו ואלהי אבותינו', 'אין מי יקרא בצדק׃'],
                                     [line.text for line in lines])
                else:
                    paragraph = body.find(f'.//{{{TEI}}}p')
                    self.assertIn('Our God', paragraph.text)
                    self.assertIn('No one calleth', paragraph.text)

    def test_expanded_instruction_uses_unqualified_full_kaddish_urn(self):
        root = section('en', 'fixture', 'closing', [{
            'id': 'reader_kaddish', 'kind': 'rubric',
            'fragments': [self.fragment('s53', 'The Reader says Kaddish.')]}])
        j = '{http://jewishliturgy.org/ns/jlptei/2}'
        scopes = root.findall(f'.//{j}conditional')
        self.assertEqual(['false', 'true'], [scope.find(f'{{{TEI}}}fs/{{{TEI}}}f/{{{TEI}}}binary').get('value') for scope in scopes])
        self.assertEqual(['urn:x-opensiddur:text:prayer:kaddish/shalem'],
                         [node.get('target') for node in root.findall(f'.//{j}transclude')])
        self.assertEqual('The Reader says Kaddish.', root.find(f'.//{{{TEI}}}note').text.strip())
        declaration = root.find(f'.//{j}declare')
        self.assertIsNotNone(declaration)
        self.assertEqual('true', declaration.find(f'{{{TEI}}}fs[@type="asher:selichot"]/{{{TEI}}}f[@name="first_day"]/{{{TEI}}}binary').get('value'))
        self.assertEqual('false', declaration.find(f'{{{TEI}}}fs[@type="opensiddur:holiday-aggregate"]/{{{TEI}}}f[@name="aseret-ymei-tshuva"]/{{{TEI}}}binary').get('value'))
        self.assertEqual(f'{j}transclude', declaration.getnext().tag)
        self.assertEqual('#'+declaration.get(XML+'id'), declaration.getnext().getnext().get('target'))


    def test_repeated_verses_start_inside_paragraph_and_end_before_next_unit(self):
        root = section('en', 'fixture', 'preface', [{
            'id': 'morning_scriptural_petitions', 'kind': 'prose',
            'repeat_start': {'en': 'Like a father'},
            'fragments': [self.fragment('s21', 'Earlier verses. Like a father. Ending.')]},
            {'id': 'next', 'kind': 'prose', 'fragments': [self.fragment('s21', 'Unrelated.')]}])
        p = root.find(f'.//{{{TEI}}}body//{{{TEI}}}p')
        self.assertEqual('Earlier verses. ', p.text)
        markers = p.findall(f'{{{TEI}}}milestone')
        self.assertEqual(2, len(markers))
        self.assertTrue(markers[0].get('corresp').endswith('/repeat'))
        self.assertEqual('Like a father. Ending. ', markers[0].tail)
        self.assertIsNone(markers[1].get('corresp'))

    def test_birnbaum_full_kaddish_keeps_all_six_parts_in_its_own_edition(self):
        from opensiddur.importer.birnbaum_scan.build.conclusion import full_kaddish
        for lang in ('he', 'en'):
            body = etree.fromstring(('<root xmlns:tei="'+TEI+'" xmlns:j="http://jewishliturgy.org/ns/jlptei/2">'+full_kaddish(lang)['body']+'</root>').encode())
            targets = [node.get('target') for node in body.findall('.//{http://jewishliturgy.org/ns/jlptei/2}transclude')]
            self.assertEqual(6, len(targets))
            self.assertTrue(all(target.endswith('@hasiddur_hashalem-birnbaum-1949-'+lang) for target in targets))
            self.assertIn('/titqabbal@', targets[3])
            self.assertIn('/oseh_shalom@', targets[-1])

    def test_first_day_kaddish_overrides_ten_days_and_restores_caller_context(self):
        import tempfile
        from pathlib import Path
        from opensiddur.exporter.compiler import CompilerProcessor
        from opensiddur.exporter.conditional_settings import yaml_to_declaration_entries
        from opensiddur.exporter.linear import LinearData
        root = section('en', 'fixture', 'closing', [{
            'id': 'reader_kaddish', 'kind': 'rubric',
            'fragments': [self.fragment('s53', 'The Reader says Kaddish.')]}])
        j = '{http://jewishliturgy.org/ns/jlptei/2}'
        unit = root.find(f'.//{{{TEI}}}body/{{{TEI}}}div/{{{TEI}}}div')
        target = unit.find(f'{j}transclude')
        probe = etree.fromstring(('<root xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xmlns:tei="'+TEI+'">'
            '<j:conditional xml:id="ten_days"><tei:fs type="opensiddur:holiday-aggregate"><tei:f name="aseret-ymei-tshuva"><tei:binary value="true"/></tei:f></tei:fs></j:conditional>'
            '<tei:p>Excluded Ten Days addition.</tei:p><j:endConditional target="#ten_days"/>'
            '<tei:p>Full Kaddish remains.</tei:p></root>').encode())
        position = unit.index(target); unit.remove(target)
        for child in reversed(list(probe)):unit.insert(position, child)
        following = etree.fromstring(('<root xmlns:j="http://jewishliturgy.org/ns/jlptei/2" xmlns:tei="'+TEI+'">'
            '<j:conditional xml:id="restored"><tei:fs type="opensiddur:holiday-aggregate"><tei:f name="aseret-ymei-tshuva"><tei:binary value="true"/></tei:f></tei:fs></j:conditional>'
            '<tei:p>Caller context restored.</tei:p><j:endConditional target="#restored"/></root>').encode())
        fixture = etree.Element('root', nsmap={'tei':TEI,'j':j[1:-1]})
        text = etree.SubElement(fixture, f'{{{TEI}}}text');text.append(unit)
        for child in list(following):text.append(child)
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)/'fixture';project.mkdir()
            (project/'index.xml').write_bytes(etree.tostring(fixture))
            data = LinearData();data.xml_cache.base_path = Path(temp)
            CompilerProcessor.load_init_settings(data, yaml_to_declaration_entries({
                'asher:expansions': {'repetitions_present': True},
                'opensiddur:holiday-aggregate': {'aseret-ymei-tshuva': True}}))
            output = etree.tostring(CompilerProcessor('fixture','index.xml',linear_data=data).process(),encoding='unicode')
        self.assertNotIn('Excluded Ten Days addition.', output)
        self.assertIn('Full Kaddish remains.', output)
        self.assertIn('Caller context restored.', output)
