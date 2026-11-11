"""Exercise authoring algorithms with invented text, never edition readings."""
import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unicodedata
import unittest
from unittest.mock import Mock

from lxml import etree
from opensiddur.importer.scan import authoring as a


class AuthoringTests(unittest.TestCase):
    def parent(self):
        return etree.Element(f'{{{a.TEI}}}div')

    def test_namespaces_choice_milestone_and_boolean_scope(self):
        p = self.parent()
        a.marker(p, 'urn:test:verse')
        self.assertEqual(p[0].get('unit'), 'stanza')
        self.assertEqual(p[0].get('corresp'), 'urn:test:verse')
        choice = a.choice(p, 'short', 'complete phrase')
        self.assertEqual([n.text for n in choice], ['short', 'complete phrase'])
        for present in [False, True]:
            scope = a.conditional_scope(p, 'sample', present, fs_type='test:edition', feature='supplied')
            self.assertEqual(scope.tag, f'{{{a.J}}}conditional')
            self.assertEqual(scope.get(a.XML+'id'), 'sample')
            self.assertEqual(scope[0].get('type'), 'test:edition')
            self.assertEqual(scope[0][0].get('name'), 'supplied')
            self.assertEqual(scope[0][0][0].get('value'), str(present).lower())

    def test_append_preserves_existing_text_children_and_tails(self):
        p = self.parent()
        a.append_words(p, 'before ')
        a.append_words(p, 'again ')
        child = a.element(p, 'hi', 'word')
        a.append_words(p, ' after')
        a.append_words(p, ' end')
        self.assertEqual(p.text, 'before again ')
        self.assertEqual(child.tail, ' after end')
        self.assertEqual(''.join(p.itertext()), 'before again word after end')

    def test_emphasis_keeps_order_and_all_words(self):
        p = self.parent(); p.text = 'One alpha, two beta, three.'
        a.italicize(p, ['beta', 'alpha'])
        self.assertEqual(''.join(p.itertext()), 'One alpha, two beta, three.')
        self.assertEqual([n.text for n in p], ['alpha', 'beta'])
        self.assertTrue(all(n.get('rend') == 'italic' for n in p))
        empty = self.parent(); a.italicize(empty, [])
        self.assertIsNone(empty.text)
        with self.assertRaisesRegex(ValueError, 'Missing printed emphasis'):
            a.italicize(p, ['missing'])

    def test_normalization_retains_binding_spaces_and_sof_pasuq(self):
        p = self.parent(); p.text = 'שָׁם · בָּא\u00a0· סוף׃'
        result = etree.fromstring(a.normalized_xml(p).encode()).text
        self.assertEqual(result, unicodedata.normalize('NFKD', 'שָׁם')+'\u00a0· '+
                         unicodedata.normalize('NFKD', 'בָּא')+'\u00a0· סוף׃')

    def test_mixed_languages_preserve_punctuation_and_words(self):
        p = self.parent(); words = 'Before אֶחָד · שְׁנַיִם, after.'
        a.mixed_words(p, words)
        self.assertEqual(''.join(p.itertext()), words)
        self.assertEqual(len(p), 1)
        self.assertEqual(p[0].get(a.XML+'lang'), 'he')
        self.assertEqual(p[0].tail, ', after.')
        pure = self.parent(); a.mixed_words(pure, 'English only.')
        self.assertEqual(pure.text, 'English only.')

    def test_notes_follow_sequential_anchors_once(self):
        p = self.parent()
        a.words_with_notes(p, 'echo and echo end', [
            {'anchor':'echo', 'text':'first note'},
            {'anchor':'echo', 'text':'second note'}], 'en')
        self.assertEqual(p.text, 'echo')
        self.assertEqual([n.text for n in p], ['first note', 'second note'])
        self.assertEqual([n.tail for n in p], [' and echo', ' end'])
        with self.assertRaisesRegex(ValueError, 'Footnote anchor absent'):
            a.words_with_notes(self.parent(), 'body', [{'anchor':'absent','text':'note'}], 'en')

    def test_mixed_language_notes_use_correct_scopes(self):
        p = self.parent()
        a.words_with_notes(p, 'אב׃', [{'anchor':'אב','text':'Say גד now\nהו׃'}], 'he')
        note = p[0]
        self.assertEqual(note[0].get(a.XML+'lang'), 'en')
        self.assertEqual(note[0][0].get(a.XML+'lang'), 'he')
        self.assertEqual(note[1].text, 'הו׃')
        self.assertEqual(note.tail, '׃')
        english = self.parent()
        a.words_with_notes(english, 'word.', [{'anchor':'word','text':'See אב.'}], 'en')
        self.assertEqual(english[0].get(a.XML+'lang'), 'en')
        self.assertEqual(english[0][0].get(a.XML+'lang'), 'he')
        plain = self.parent()
        a.words_with_notes(plain, 'אב', [{'anchor':'אב','text':'גד'}], 'he')
        self.assertEqual(plain[0].text, 'גד')

    def test_a_multi_line_note_is_paragraphs_with_their_emphasis(self):
        p = self.parent()
        a.words_with_notes(p, 'praise? Then', [{'anchor': 'praise?', 'text': 'Said by the Reader—\nBlessed are the people.',
                                                  'italic': ['Said by the Reader—']}], 'en')
        note = p[0]
        self.assertEqual(['p', 'p'], [etree.QName(child).localname for child in note])
        self.assertEqual('italic', note[0][0].get('rend'))
        self.assertEqual('Said by the Reader—', note[0][0].text)
        self.assertEqual('Blessed are the people.', note[1].text)
        self.assertEqual(' Then', note.tail)

    def correctable(self):
        root = etree.fromstring(f'<div xmlns="{a.TEI}"><p>the oppessors fled; Isaiah vi. 7.'
                                f'<note>first<hi>inner</hi></note>” after<abbr>(When, &amp;c.</abbr>'
                                f'<abbr>(When, &amp;c.)</abbr></p></div>')
        return root

    def choices(self, root):
        return [(c[0].text, c[1].text) for c in root.iter(f'{{{a.TEI}}}choice')]

    def test_a_correction_marks_the_printed_form_beside_its_correction(self):
        root = self.correctable()
        a.apply_corrections({'x/y.xml': root}, [
            {'id': 'typo', 'file': 'x/y.xml', 'sic': 'oppessors', 'corr': 'oppressors'},
            {'id': 'cite', 'file': 'x/y.xml', 'before': 'Isaiah ', 'sic': 'vi.', 'corr': 'lvi.', 'after': ' 7.'}])
        self.assertEqual([('oppessors', 'oppressors'), ('vi.', 'lvi.')], self.choices(root))
        self.assertEqual('the oppessors fled; Isaiah vi. 7.firstinner” after(When, &c.(When, &c.)', a.printed_text(root))

    def test_printed_text_excludes_an_abbreviations_editorial_expansion(self):
        root = etree.fromstring(f'<p xmlns="{a.TEI}">Before <choice>'
                                '<abbr>ב״א</abbr><expan>ברוך אתה</expan>'
                                '</choice> after.</p>')
        self.assertEqual(a.printed_text(root), 'Before ב״א after.')

    def test_a_correction_can_follow_an_element_or_match_a_whole_text(self):
        root = self.correctable()
        a.apply_corrections({'x/y.xml': root}, [
            {'id': 'stray', 'file': 'x/y.xml', 'follows': 'inner', 'sic': '”', 'corr': ''},
            {'id': 'paren', 'file': 'x/y.xml', 'exact': True, 'before': '(When, ', 'sic': '&c.', 'corr': '&c.)'}])
        self.assertEqual([('”', None), ('&c.', '&c.)')], self.choices(root))
        self.assertEqual(' after', root.find(f'.//{{{a.TEI}}}choice').tail)

    def test_a_correction_that_matches_nowhere_or_twice_is_refused(self):
        for correction in [{'id': 'gone', 'file': 'x/y.xml', 'sic': 'absent', 'corr': 'x'},
                           {'id': 'twice', 'file': 'x/y.xml', 'sic': '(When, &c.', 'corr': 'x'},
                           {'id': 'nofile', 'file': 'x/z.xml', 'sic': 'fled', 'corr': 'x'}]:
            with self.subTest(correction=correction['id']), self.assertRaises(ValueError):
                a.apply_corrections({'x/y.xml': self.correctable()}, [correction])

    def test_duplicate_passage_can_be_corrected_at_one_explicit_occurrence(self):
        root = etree.fromstring(f'<div xmlns="{a.TEI}"><p>same words</p><p>same words</p></div>')
        spec = {'id': 'duplicate', 'file': 'x/y.xml', 'sic': 'same words', 'corr': '',
                'xpath': './tei:p[2]', 'exact': True}
        a.apply_corrections({'x/y.xml': root}, [spec])
        self.assertEqual(root[0].text, 'same words')
        self.assertEqual(self.choices(root), [('same words', None)])
        self.assertEqual(a.printed_text(root), 'same wordssame words')
        for selector in ['./tei:p', './tei:missing', 'string(.)', 'true()']:
            with self.subTest(selector=selector), self.assertRaises(ValueError):
                a.apply_corrections({'x/y.xml': root}, [dict(spec, xpath=selector)])
        root[1].tail = 'outside'
        with self.assertRaises(ValueError):
            a.apply_corrections({'x/y.xml': root}, [dict(spec, sic='outside')])

    def test_a_misspelt_note_emphasis_phrase_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'Missing printed emphasis'):
            a.words_with_notes(self.parent(), 'word', [{'anchor': 'word', 'text': 'one\ntwo', 'italic': ['three']}], 'en')

    def test_a_correction_never_lands_inside_an_earlier_one(self):
        root = etree.fromstring(f'<div xmlns="{a.TEI}"><p>oppessors and oppressors</p></div>')
        a.apply_corrections({'x/y.xml': root}, [
            {'id': 'first', 'file': 'x/y.xml', 'sic': 'oppessors', 'corr': 'oppressors and more'},
            {'id': 'second', 'file': 'x/y.xml', 'before': 'and ', 'sic': 'oppressors', 'corr': 'x'}])
        self.assertEqual([('oppessors', 'oppressors and more'), ('oppressors', 'x')], self.choices(root))

    def test_a_correction_after_an_element_keeps_its_context(self):
        root = etree.fromstring(f'<div xmlns="{a.TEI}"><p>the unclean<note>Thy laws.</note> for the clean;</p></div>')
        a.apply_corrections({'x/y.xml': root}, [
            {'id': 'second', 'file': 'x/y.xml', 'follows': 'Thy laws.', 'before': ' for the ', 'sic': 'clean',
             'corr': 'unclean', 'after': ';'}])
        note = root.find(f'.//{{{a.TEI}}}note')
        self.assertEqual(' for the ', note.tail)
        self.assertEqual([('clean', 'unclean')], self.choices(root))

    def test_an_editorial_note_is_standoff_on_an_anchor_where_the_text_names(self):
        root = etree.fromstring(f'<TEI xmlns="{a.TEI}"><text><body><p>unto thy holy mountain, and I will</p>'
                                f'</body></text></TEI>')
        a.apply_editorial_notes({'x/y.xml': root}, [
            {'id': 'holy-mountain', 'file': 'x/y.xml', 'before': 'thy holy mountain', 'after': ', and I',
             'text': 'Editor: Isaiah reads “my holy mountain” (הַר קָדְשִׁי).'}])
        p = root.find(f'.//{{{a.TEI}}}p')
        anchor = p.find(f'{{{a.TEI}}}anchor')
        self.assertEqual('unto thy holy mountain', p.text)
        self.assertEqual(', and I will', anchor.tail)
        note = root.find(f'{{{a.TEI}}}standOff[@type="notes"]/{{{a.TEI}}}note')
        self.assertEqual(('editorial', '#editorial_holy_mountain'), (note.get('type'), note.get('target')))
        self.assertEqual('editorial_holy_mountain', anchor.get(a.XML + 'id'))
        self.assertEqual('he', note.find(f'{{{a.TEI}}}foreign').get(a.XML + 'lang'))
        with self.assertRaisesRegex(ValueError, 'Editorial note gone'):
            a.apply_editorial_notes({'x/y.xml': root}, [{'id': 'gone', 'file': 'x/y.xml', 'before': 'absent', 'text': 'x'}])

    def test_language_wrapping_preserves_tree_and_is_idempotent(self):
        p = self.parent(); p.text = 'Start אב '
        hi = a.element(p, 'hi', 'inside גד'); hi.tail = ' end הו.'
        hebrew = a.element(p, 'p', 'זח'); hebrew.set(a.XML+'lang', 'he')
        foreign = a.element(p, 'foreign', 'טי'); foreign.set(a.XML+'lang', 'he')
        before = ''.join(p.itertext())
        a.wrap_hebrew(p)
        self.assertEqual(''.join(p.itertext()), before)
        self.assertIs(hi.getparent(), p)
        self.assertEqual(hebrew.text, 'זח')
        self.assertEqual(len(hebrew), 0)
        self.assertEqual(len(foreign), 0)
        frozen = etree.tostring(p)
        a.wrap_hebrew(p)
        self.assertEqual(etree.tostring(p), frozen)

    def fragment(self, text, *, scan='s2', notes=(), join_next=False):
        return {'he':{'text':text,'scan':scan,'printed_page':'x','join_next':join_next},
                'notes':{'he':list(notes)}}

    def test_poetry_keeps_continuing_verse_pagebreak_and_terminal_refrain(self):
        group = self.parent()
        fragments = [self.fragment('אב',join_next=True),
                     self.fragment('גד הו׃ זח ·',scan='s4')]
        def page_break(parent, scan, label):
            return a.element(parent, 'pb', n=label, facs=scan)
        a.poetic_lines(group, fragments, {'line_stops':'׃·','refrain':'הו'}, page_break=page_break)
        self.assertEqual(len(group), 2)
        self.assertEqual(''.join(group[0].itertext()), 'אבגד הו׃')
        self.assertEqual(group[0][0].tag, f'{{{a.TEI}}}pb')
        self.assertEqual(group[0][0].get('facs'), 's4')
        self.assertEqual(group[0][-1].get('type'), 'refrain')
        self.assertEqual(group[1].text, 'זח\u00a0·')
        unit = self.parent(); unit.tag = f'{{{a.TEI}}}div'; group.tag = f'{{{a.TEI}}}lg';unit.append(group)
        a.check_poetry(unit, {'line_count':2,'refrain_count':1,'refrain':'הו'})

    def test_poetry_spaces_closed_lines_and_note_boundaries(self):
        group = self.parent(); callback = Mock()
        a.poetic_lines(group, [self.fragment('אב'),self.fragment(' גד׃)',scan='s4')],
                       {'line_stops':'׃'}, page_break=callback)
        self.assertEqual(''.join(group[0].itertext()), 'אב גד׃)')
        callback.assert_called_once_with(group[0], 's4', 'x')
        closed = self.parent(); callback.reset_mock()
        a.poetic_lines(closed,[self.fragment('אב׃'),self.fragment('גד׃',scan='s4')],
                       {'line_stops':'׃'},page_break=callback)
        callback.assert_called_once_with(closed,'s4','x')
        noted = self.parent()
        a.poetic_lines(noted,[self.fragment('אב׃',notes=[{'anchor':'אב','text':'גד'}])],
                       {'line_stops':'׃'},page_break=callback)
        self.assertEqual(noted[0][0].text, 'גד')
        with self.assertRaisesRegex(ValueError, 'anchor crosses'):
            a.poetic_lines(self.parent(),[self.fragment('אב׃ גד׃',notes=[{'anchor':'אב׃ גד','text':'note'}])],
                           {'line_stops':'׃'},page_break=callback)
        whitespace = self.parent()
        a.poetic_lines(whitespace,[self.fragment('   ')],{'line_stops':'׃'},page_break=callback)
        self.assertEqual(len(whitespace),0)

    def test_structure_audit_rejects_prose_wrong_counts_and_nonterminal_refrains(self):
        unit = self.parent(); lg = a.element(unit,'lg'); line = a.element(lg,'l','אב ')
        a.element(line,'seg','גד׃',type='refrain')
        rule = {'line_count':1,'refrain_count':1,'refrain':'גד'}
        a.check_poetry(unit,rule)
        for variant in ['prose','line_count','refrain_count','wording','parent','following','tail']:
            with self.subTest(variant=variant):
                broken = copy.deepcopy(unit); r = broken.find(f'.//{{{a.TEI}}}seg'); expected = dict(rule)
                if variant=='prose':a.element(broken,'p','אב גד׃')
                elif variant=='line_count':expected['line_count']=2
                elif variant=='refrain_count':expected['refrain_count']=0
                elif variant=='wording':r.text='הו׃'
                elif variant=='parent':r.getparent().remove(r);broken.append(r)
                elif variant=='following':a.element(r.getparent(),'seg','extra')
                else:r.tail='extra'
                with self.assertRaises(ValueError):a.check_poetry(broken,expected)

    def test_failed_validation_leaves_existing_files_and_obsolete_paths_untouched(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); existing = root/'existing.xml'; existing.write_text('old')
            obsolete = root/'obsolete.xml'; obsolete.write_text('keep')
            validator = Mock(side_effect=[(True,[]),(False,['invalid shape'])])
            with self.assertRaisesRegex(ValueError,'invalid shape'):
                a.write_documents([(existing,self.parent()),(root/'new.xml',self.parent())],
                                  validator=validator,obsolete_paths=[obsolete])
            self.assertEqual(existing.read_text(),'old')
            self.assertFalse((root/'new.xml').exists())
            self.assertTrue(obsolete.exists())

    def test_writes_validated_set_and_removes_only_explicit_obsolete_files(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); obsolete = root/'old.xml';obsolete.write_text('old')
            keep = root/'keep.xml';keep.write_text('keep')
            target = root/'nested/new.xml'; validator=Mock(return_value=(True,[]))
            result=a.write_documents([(target,self.parent())],validator=validator,
                                     obsolete_paths=[obsolete,root/'missing.xml'])
            self.assertEqual(result,[target]);validator.assert_called_once()
            self.assertEqual(target.read_text(),validator.call_args.args[0])
            self.assertFalse(obsolete.exists());self.assertTrue(keep.exists())
