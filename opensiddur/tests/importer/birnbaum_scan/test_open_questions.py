"""Tests for the queue of unsettled differences.

Every fixture is synthetic. Nothing here reads the sourcetexts submodule: CI does not
initialise one, and a test that read the committed reading would break whenever a reading
is corrected, which is the thing this module exists to make easy.
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from opensiddur.importer.birnbaum_scan import open_questions as oq
from opensiddur.importer.scan import compare as cmp


class _Reading:
    """A synthetic pair of readings and a verdict file, on disk."""

    def __init__(self, tmp: Path):
        self.hebrew = tmp / "hebrew"
        self.transcription = tmp / "transcription"
        self.verdicts = tmp / "verdicts"
        for d in (self.hebrew, self.transcription, self.verdicts):
            d.mkdir(parents=True)

    def page(self, page, ours, theirs, verdicts=None):
        (self.hebrew / f"{page}.txt").write_text(ours, encoding="utf-8")
        (self.transcription / f"{page}.txt").write_text(theirs, encoding="utf-8")
        if verdicts is not None:
            (self.verdicts / f"{page}.json").write_text(
                json.dumps(verdicts, ensure_ascii=False), encoding="utf-8")

    def collect(self):
        return oq.collect(hebrew=self.hebrew, transcription=self.transcription,
                          verdicts=self.verdicts)


class OpenQuestionsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.r = _Reading(Path(self._tmp.name))


class TestWhatCounts(OpenQuestionsTest):
    def test_a_settled_difference_is_left_out(self):
        """The settled ones are noise to whoever has to decide the rest."""
        self.r.page("3", "אָ בָּ", "אָ בְּ",
                    {"vowels:1:בָּ|בְּ": "print"})
        self.assertEqual(self.r.collect(), [])

    def test_a_difference_recorded_unresolved_is_open(self):
        self.r.page("3", "אָ בָּ", "אָ בְּ", {"vowels:1:בָּ|בְּ": "unresolved"})
        questions = self.r.collect()
        self.assertEqual(len(questions), 1)
        self.assertTrue(questions[0].recorded)

    def test_a_difference_with_no_entry_at_all_is_open_and_says_so(self):
        """The state that was invisible: absent from the verdict file is
        indistinguishable from a page nobody opened, which is how six of page 7's
        differences went unnoticed."""
        self.r.page("3", "אָ בָּ", "אָ בְּ", {})
        questions = self.r.collect()
        self.assertEqual(len(questions), 1)
        self.assertFalse(questions[0].recorded)
        self.assertIn("never written down", oq.render(questions))

    def test_a_page_with_no_verdict_file_is_still_read(self):
        self.r.page("3", "אָ בָּ", "אָ בְּ")
        self.assertEqual(len(self.r.collect()), 1)

    def test_pages_come_in_printed_order_not_asciibetical(self):
        for page in ("3", "11", "7"):
            self.r.page(page, "אָ בָּ", "אָ בְּ")
        self.assertEqual([q.page for q in self.r.collect()], ["3", "7", "11"])


class TestContext(OpenQuestionsTest):
    def test_the_surrounding_phrase_is_quoted(self):
        """A bare pair of forms is not enough to decide from."""
        ours = "אחת שתים שלוש בָּ ארבע חמש שש"
        self.r.page("3", ours, ours.replace("בָּ", "בְּ"))
        context = self.r.collect()[0].context
        self.assertIn("שלוש", context)
        self.assertIn("ארבע", context)


class TestDescribingTheDifference(OpenQuestionsTest):
    """Two pointed words differing by one meteg look identical in a list."""

    def test_a_mark_the_reading_has_is_named(self):
        self.assertIn("reading has METEG", oq.describe("רֶֽחֶם", "רֶחֶם"))

    def test_a_mark_the_transcription_has_is_named(self):
        self.assertIn("transcription has METEG", oq.describe("לָתֶת", "לָֽתֶת"))

    def test_a_swapped_point_names_both_sides(self):
        described = oq.describe("לְהָנִיחַ", "לְהַנִיחַ")
        self.assertIn("QAMATS", described)
        self.assertIn("PATAH", described)

    def test_a_difference_in_letters_says_so_rather_than_naming_points(self):
        self.assertIn("letters differ", oq.describe("זְרוֹעַ", "זְרוֹעוֹ"))

    def test_the_description_reaches_the_queue(self):
        self.r.page("3", "אָ רֶֽחֶם", "אָ רֶחֶם")
        self.assertIn("differs by", oq.render(self.r.collect()))


class TestAnswers(OpenQuestionsTest):
    def test_the_readings_own_form_means_print(self):
        self.assertEqual(oq.verdict_for("vowels:1:בָּ|בְּ", "בָּ"), cmp.PRINT)

    def test_the_transcriptions_form_means_reading(self):
        self.assertEqual(oq.verdict_for("vowels:1:בָּ|בְּ", "בְּ"), cmp.READING)

    def test_a_verdict_word_is_taken_as_written(self):
        self.assertEqual(oq.verdict_for("vowels:1:בָּ|בְּ", "print"), cmp.PRINT)

    def test_a_whitespace_answer_works_quoted_or_bare(self):
        """The queue shows whitespace candidates quoted, because a bare space is
        invisible. Nobody should have to type the quotes back."""
        key = "whitespace:1:' '|'־'"
        self.assertEqual(oq.verdict_for(key, "'־'"), cmp.READING)
        self.assertEqual(oq.verdict_for(key, "־"), cmp.READING)
        self.assertEqual(oq.verdict_for(key, "' '"), cmp.PRINT)

    def test_a_form_that_is_neither_is_refused_rather_than_guessed(self):
        """Both readings are in the key, so an answer can be checked instead of trusted."""
        with self.assertRaises(ValueError):
            oq.verdict_for("vowels:1:בָּ|בְּ", "גָּ")

    def test_an_unanswered_block_is_not_a_decision(self):
        queue = oq.render(self.r.collect())
        self.assertEqual(oq.parse_answers(queue), {})

    def test_answering_writes_the_verdict_to_its_page(self):
        self.r.page("3", "אָ בָּ", "אָ בְּ")
        queue = oq.render(self.r.collect()).replace("answer:", "answer: בְּ")
        written = oq.apply(queue, verdicts=self.r.verdicts,
                           hebrew=self.r.hebrew, transcription=self.r.transcription)
        self.assertEqual(written, {"3": 1})
        recorded = json.loads((self.r.verdicts / "3.json").read_text(encoding="utf-8"))
        self.assertEqual(recorded["vowels:1:בָּ|בְּ"], cmp.READING)
        self.assertEqual(self.r.collect(), [])

    def test_answering_keeps_the_verdicts_already_in_the_file(self):
        self.r.page("3", "אָ בָּ גּ", "אָ בְּ גִּ", {"vowels:1:בָּ|בְּ": "print"})
        queue = oq.render(self.r.collect()).replace("answer:", "answer: reading")
        oq.apply(queue, verdicts=self.r.verdicts,
                 hebrew=self.r.hebrew, transcription=self.r.transcription)
        recorded = json.loads((self.r.verdicts / "3.json").read_text(encoding="utf-8"))
        self.assertEqual(recorded["vowels:1:בָּ|בְּ"], "print")
        self.assertEqual(len(recorded), 2)

    def test_an_answer_to_a_question_that_is_not_open_is_refused(self):
        """A stale queue must not write a verdict against a difference that has since
        been corrected away -- that is how a fixed reading acquires a verdict saying it
        was never fixed."""
        self.r.page("3", "אָ בָּ", "אָ בְּ")
        with self.assertRaises(ValueError):
            oq.apply("    key: vowels:99:x|y\n    answer: print",
                     verdicts=self.r.verdicts, hebrew=self.r.hebrew,
                     transcription=self.r.transcription)


class TestEmptyQueue(OpenQuestionsTest):
    def test_nothing_open_says_so_plainly(self):
        self.assertIn("None.", oq.render([]))


if __name__ == "__main__":
    unittest.main()
