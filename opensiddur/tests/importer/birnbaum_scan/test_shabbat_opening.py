"""Synthetic checks for recipient selection and biblical paragraph boundaries."""
import unittest

from opensiddur.exporter.condition_eval import TriState
from opensiddur.importer.birnbaum_scan.build.shabbat_opening import (
    RECIPIENT,
    SONG,
    recipient_condition,
    song_body,
)

from .test_tachanun_conditions import NS, evaluate, fragment


class TestParentalBlessing(unittest.TestCase):
    def test_reciters_gender_does_not_select_childs_blessing(self):
        for gender in ('male', 'female'):
            values = {('opensiddur:person', 'gender'): gender}
            for child in ('male', 'female'):
                with self.subTest(parent=gender, child=child):
                    self.assertEqual(evaluate(recipient_condition(child), values), TriState.UNDEFINED)

    def test_recipient_selects_one_formula(self):
        for actual in ('male', 'female'):
            for selected in ('male', 'female'):
                with self.subTest(actual=actual, selected=selected):
                    self.assertEqual(evaluate(recipient_condition(selected), {(RECIPIENT, 'gender'): actual}),
                                     TriState.TRUE if actual == selected else TriState.FALSE)


class TestBiblicalParagraphs(unittest.TestCase):
    def test_paragraph_and_page_breaks_do_not_create_extra_verses(self):
        body = fragment(song_body('en', {1: 'First{p}continued.\nSecond {pb:224}verse.'}, {1: (1, 2)}))
        marks = body.findall('.//tei:milestone', NS)
        self.assertEqual([m.get('corresp') for m in marks], [SONG+'/1/1', SONG+'/1/2', None])
        chapter = body.find(f'.//tei:div[@corresp="{SONG}/1"]', NS)
        self.assertEqual(len(chapter.findall('tei:p', NS)), 3)
        self.assertEqual(len(body.findall('.//tei:pb', NS)), 2)
        text = ''.join(body.itertext())
        self.assertIn('Firstcontinued.', text)
        self.assertIn('Second verse.', text)

    def test_qere_retains_both_printed_forms_inside_one_verse(self):
        body = fragment(song_body('he', {2: '{qere:כתיב|קְרִי}'}))
        self.assertEqual(body.find('.//j:written', NS).text, 'כתיב')
        self.assertEqual(body.find('.//j:read', NS).text, 'קְרִי')
        self.assertEqual(body.find('.//tei:milestone', NS).get('corresp'), SONG+'/2/1')
        self.assertNotIn('{qere:', ''.join(body.itertext()))
