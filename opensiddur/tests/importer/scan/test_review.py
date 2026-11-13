import unittest
from opensiddur.importer.scan.review import review, adjudicate_fragments, review_is_current, reading_hash


class ReviewTest(unittest.TestCase):
    def check(self, primary, independent, **kwargs):
        return review(primary, independent, primary_model='reader-a', independent_model='reader-b',
                      evidence='https://example.org/page/n3.jpg', **kwargs)

    def test_pointing_requires_adjudication(self):
        result = self.check('בָּם', 'בַּם')
        self.assertFalse(result['complete'])
        self.assertEqual(result['differences'][0]['bucket'], 'vowels')

    def test_line_wrap_and_combining_order_are_not_disputes(self):
        self.assertTrue(self.check('בָּם שם', 'בָּם\nשם')['complete'])

    def test_every_dispute_needs_image_evidence(self):
        result = self.check('first second', 'third second')
        key = result['differences'][0]['key']
        settlement = {k: result[k] for k in ('primary_sha256', 'independent_sha256')}
        settlement['decisions'] = {key: {'accepted': 'primary'}}
        self.assertFalse(self.check('first second', 'third second', settlement=settlement)['complete'])
        settlement['decisions'][key]['evidence'] = 'Enlarged first line of scan n3'
        self.assertTrue(self.check('first second', 'third second', settlement=settlement)['complete'])
        with self.assertRaisesRegex(ValueError, 'Stale'):
            self.check('first changed', 'third second', settlement=settlement)

    def test_same_model_cannot_be_claimed_as_different(self):
        with self.assertRaises(ValueError):
            review('a', 'a', primary_model='same', independent_model='same', evidence='scan')

    def settled(self, primary, independent):
        report = self.check(primary, independent)
        report['decisions'] = {d['key']: {'accepted': 'independent', 'evidence': 'Enlarged scan'}
                               for d in report['differences']}
        return report

    def test_repeated_word_changes_only_at_reviewed_position(self):
        report = self.settled('same same other same', 'same same, other same')
        self.assertEqual(adjudicate_fragments(['same same other same'], report), ['same same, other same'])

    def test_page_boundaries_survive_edits(self):
        report = self.settled('first same same last', 'first same changed last')
        self.assertEqual(adjudicate_fragments(['first same', 'same last'], report), ['first same', 'changed last'])
        with self.assertRaisesRegex(ValueError, 'Stale'):
            adjudicate_fragments(['first altered', 'same last'], report)

    def test_unresolved_and_cross_page_changes_need_manual_placement(self):
        with self.assertRaisesRegex(ValueError, 'Unresolved'):
            adjudicate_fragments(['first second'], self.check('first second', 'third fourth'))
        report = self.settled('first second', 'third fourth')
        with self.assertRaisesRegex(ValueError, 'crosses'):
            adjudicate_fragments(['first', 'second'], report)

    def test_final_review_expires_when_text_or_uncertainty_changes(self):
        entry = self.check('agreed text', 'agreed text')
        entry['final_sha256'] = reading_hash('agreed text')
        self.assertTrue(review_is_current(entry, 'agreed text'))
        self.assertFalse(review_is_current(entry, 'changed text'))
        entry['pending_ambiguities'] = ['Both readers could not identify one mark']
        self.assertFalse(review_is_current(entry, 'agreed text'))
