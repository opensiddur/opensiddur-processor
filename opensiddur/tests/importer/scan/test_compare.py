"""Reading comparisons classify differences without knowing either book."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from opensiddur.importer.scan import compare as c


class ComparisonTests(unittest.TestCase):
    def test_pointing_skeleton_and_separator_differences_stay_separate(self):
        result=c.compare('כָּל־אָב\nבן\n\nגד','כַל אָב בן גד',page='s1')
        self.assertEqual(result.page,'s1')
        self.assertEqual(result.word_count,4)
        tally=result.tally()
        self.assertEqual(tally[c.VOWELS]['total'],2)  # Qamats/patah and dagesh.
        self.assertEqual(tally[c.WHITESPACE]['total'],3)
        self.assertEqual(tally[c.CONSONANTS]['total'],0)
        self.assertEqual(c.separators('א־ב\nג\n\nד'),['־','\n','\n\n'])
        self.assertEqual(c.words(' א־ב '),['א','ב'])
        self.assertEqual(c.compare('alpha','omega').differences[0].bucket,c.CONSONANTS)
        self.assertEqual(c.compare('אב','א').differences[0].bucket,c.CONSONANTS)
        self.assertIn('4 words read.',c.format_tally(result))

    def test_verdicts_reject_unknown_values_and_report_stale_records(self):
        result=c.compare('אָב','אַב')
        key=result.differences[0].key
        self.assertEqual(result.apply_verdicts({key:c.PRINT,'stale':c.READING}),['stale'])
        self.assertEqual(result.tally()[c.VOWELS][c.PRINT],1)
        with self.assertRaises(ValueError):result.apply_verdicts({key:'invalid'})
        policy=c.compare('כָל','כׇל')
        self.assertEqual(policy.qamats_qatan_verdicts(),{policy.differences[0].key:c.PRINT})
        self.assertTrue(c.is_qamats_qatan_only('כָל','כׇל'))
        self.assertFalse(c.is_qamats_qatan_only('כָּל','כׇל'))
        self.assertEqual(result.qamats_qatan_verdicts(),{})

    def test_cli_json_and_table_with_stale_adjudication(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);reading=root/'reading.txt';other=root/'other.txt';verdicts=root/'verdicts.json'
            reading.write_text('alpha');other.write_text('omega');verdicts.write_text('{"stale":"print"}')
            with redirect_stdout(io.StringIO()) as log:
                self.assertEqual(c.main([str(reading),str(other),'--json','--page','s4']),0)
            payload=json.loads(log.getvalue());self.assertEqual(payload['page'],'s4');self.assertEqual(payload['differences'][0]['bucket'],c.CONSONANTS)
            with redirect_stdout(io.StringIO()) as log:
                self.assertEqual(c.main([str(reading),str(other),'--verdicts',str(verdicts)]),0)
            self.assertIn('no difference matches',log.getvalue());self.assertIn('| bucket |',log.getvalue())

    def test_opt_in_policy_writes_only_new_verdicts_and_requires_destination(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);reading=root/'reading.txt';other=root/'other.txt';verdicts=root/'verdicts.json'
            reading.write_text('כָל',encoding='utf-8');other.write_text('כׇל',encoding='utf-8')
            args=[str(reading),str(other),'--settle-qamats-qatan']
            with self.assertRaises(SystemExit):c.main(args)
            for expected in ['1 newly recorded','0 newly recorded']:
                with redirect_stdout(io.StringIO()) as log:
                    self.assertEqual(c.main(args+['--verdicts',str(verdicts)]),0)
                self.assertIn(expected,log.getvalue())
            saved=json.loads(verdicts.read_text(encoding='utf-8'));key=next(iter(saved));saved[key]=c.READING;verdicts.write_text(json.dumps(saved))
            with redirect_stdout(io.StringIO()):c.main(args+['--verdicts',str(verdicts)])
            self.assertEqual(json.loads(verdicts.read_text(encoding='utf-8'))[key],c.READING)
