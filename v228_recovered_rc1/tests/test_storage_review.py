import csv,json,tempfile,unittest
from pathlib import Path
from intelligence.storage_review import review
from intelligence.demo_learning import collect
from tests.test_demo_learning_native import NativeHarness,ROOT
from tests.test_v214_execution import read_csv,write_csv,tree_hash


class StorageReplayTests(NativeHarness,unittest.TestCase):
    def test_actual_windows_gap_excerpt_reports_exact_missing_sequence_without_repair(self):
        rows=json.loads((ROOT/'tests/fixtures/windows_replay_gap_v214.json').read_bytes())['rows'][:4]
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(Path(tmp),mode=0)
            path=source/'input_20261019.csv';write_csv(path,rows);before=path.read_bytes()
            with self.assertRaisesRegex(ValueError,'previous_seq=4437, current_seq=4439'):collect(source)
            self.assertEqual(path.read_bytes(),before)
    def test_concurrent_reader_requires_explicit_native_share_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(Path(tmp),mode=10)
            self.assertTrue(result['healthy']);self.assertEqual(result['signals'],1)
            self.assertEqual(review(source)['issues'],[])

    def test_failed_input_write_stops_all_further_replay_and_does_not_consume_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(Path(tmp),mode=12)
            self.assertFalse(result['healthy']);self.assertEqual(result['signals'],0)
            rows=read_csv(next(source.glob('input_*.csv')))
            seq=[int(r['sequence']) for r in rows]
            self.assertEqual(seq,list(range(1,len(rows)+1)))
            self.assertEqual(result['input_sequence'],seq[-1])
            self.assertEqual(review(source)['issues'],[])
            # A stopped clean prefix is not evidence of uninterrupted operation.
            self.assertLess(int(rows[-1]['time_ms_estimated']),int(rows[0]['time_ms_estimated'])+200000)

    def test_gap_and_clock_are_distinguished_without_repair_or_fit(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(Path(tmp),mode=0)
            p=next(source.glob('input_*.csv'));rows=read_csv(p);rows.pop(20)
            rows[30]['time_ms_estimated']=str(int(rows[29]['time_ms_estimated'])-1);write_csv(p,rows)
            before=tree_hash(source);r=review(source)
            self.assertIn('SEQUENCE_GAP',[i['kind'] for i in r['issues']])
            self.assertIn('CLOCK_BACKWARDS_OR_INVALID',[i['kind'] for i in r['issues']])
            self.assertFalse(r['trained']);self.assertFalse(r['repaired']);self.assertEqual(tree_hash(source),before)
            with self.assertRaisesRegex(ValueError,'CSV row=.*previous_seq='):collect(source)

    def test_partial_tail_is_reported_and_never_fabricated(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(Path(tmp),mode=0)
            p=next(source.glob('input_*.csv'));original=p.read_bytes();p.write_bytes(original+b'2,2026101707,partial')
            self.assertEqual(review(source)['issues'][0]['kind'],'INCOMPLETE_TAIL')
            self.assertEqual(p.read_bytes(),original+b'2,2026101707,partial')
