"""Independent manual-publication cohort, exercised through the actual adapter."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from intelligence.candidate_data import read
from intelligence.manual_signals import review,checksum
from tests.test_demo_learning_native import NativeHarness
from tests.test_v214_execution import tree_hash


class ManualSignalTests(NativeHarness,unittest.TestCase):
    def book(self,source):return review(source,read(source))

    def test_official_put_keeps_loss_after_native_gap_cancellation(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,mode=24,direction=-1)
            self.assertEqual(result['signals'],0)
            self.assertEqual(result['dash_losses'],0)
            self.assertEqual(result['manual_losses'],1)
            self.assertTrue(result['manual_held_after_cancel'])
            self.assertEqual(result['official_alerts'],1)
            report=self.book(source)
            self.assertEqual(report['counts']['LOSS'],1)
            self.assertEqual(report['native_canceled_after_publication'],1)
            self.assertFalse(report['manual_broker_fills_known'])
            self.assertFalse(report['learning_active'])

    def test_fixed_horizons_and_call_put_outcomes_match_saved_book(self):
        for direction in (1,-1):
            for horizon in (1,2,3):
                with self.subTest(direction=direction,horizon=horizon),tempfile.TemporaryDirectory() as tmp:
                    result,source=self.execute(tmp,direction=direction,horizon=horizon)
                    self.assertEqual(result['manual_wins'],1)
                    self.assertTrue(result['alert_contract'])
                    self.assertTrue(result['manual_ui_hold'])
                    self.assertEqual(result['official_alerts'],1)
                    row=self.book(source)['signals'][0]
                    self.assertEqual(row['hold_minutes'],horizon*5)
                    self.assertEqual(row['expiry_broker_seconds']-row['entry_broker_seconds'],horizon*300)

    def test_loss_tie_and_missing_boundary_are_not_wins(self):
        for mode,status in ((13,'LOSS'),(14,'TIE'),(4,'UNAVAILABLE'),(25,'UNAVAILABLE')):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,mode=mode)
                report=self.book(source)
                self.assertEqual(report['counts'][status],1)
                self.assertEqual(report['counts']['WIN'],0)
                self.assertEqual(result['manual_total'],1)
                self.assertEqual(result['manual_pending'],0)

    def test_prelock_rejection_has_no_official_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,mode=2)
            self.assertEqual(result['official_alerts'],0)
            self.assertEqual(self.book(source)['counts']['COMMITTED'],0)

    def test_pause_and_restart_do_not_erase_committed_signal_or_repeat_alert(self):
        for mode in (3,27,28):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,mode=mode)
                self.assertEqual(result['manual_wins'],1)
                self.assertEqual(result['official_alerts'],1)
                self.assertEqual(self.book(source)['counts']['COMMITTED'],1)

    def test_durable_loss_counter_recovers_without_duplicate_or_manual_record_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(tmp,mode=24)
            before=tree_hash(source)
            restored,_=self.execute(tmp,mode=20)
            self.assertEqual(restored['manual_total'],1)
            self.assertEqual(restored['manual_losses'],1)
            self.assertEqual(restored['manual_pending'],0)
            self.assertFalse(restored['manual_error'])
            self.assertEqual({k:v for k,v in before.items() if k.startswith('manual_')},
                             {k:v for k,v in tree_hash(source).items() if k.startswith('manual_')})

    def test_manual_disk_failure_blocks_publication_but_preserves_native_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,mode=26)
            self.assertTrue(result['manual_error'])
            self.assertEqual(result['manual_total'],0)
            self.assertEqual(result['official_alerts'],0)
            self.assertEqual(result['signals'],1)
            self.assertTrue(result['healthy'])

    def test_late_durable_write_is_withheld_and_not_alerted_or_scored(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,mode=29)
            self.assertEqual(result['manual_total'],0)
            self.assertEqual(result['manual_withheld'],1)
            self.assertEqual(result['official_alerts'],0)
            report=self.book(source)
            self.assertEqual(report['counts']['WITHHELD'],1)
            self.assertEqual(report['counts']['COMMITTED'],0)

    def test_corrupt_result_cannot_silently_change_win_counter(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(tmp,mode=24)
            path=next(source.glob('manual_v218_4_*.csv'))
            with path.open() as stream:rows=list(csv.DictReader(stream))
            row=rows[0];row['result']='1';row['checksum']=str(checksum(row))
            with path.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(row));writer.writeheader();writer.writerows(rows)
            with self.assertRaisesRegex(ValueError,'disagrees'):self.book(source)
            restored,_=self.execute(tmp,mode=20)
            self.assertTrue(restored['manual_error'])
            self.assertEqual(restored['manual_losses'],0)

    def test_quote_replay_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(tmp)
            quote=next(source.glob('manual_v218_2_*.csv'))
            with quote.open() as stream:rows=list(csv.DictReader(stream))
            row=rows[0];row['bid']='1.5000000000';row['checksum']=str(checksum(row))
            with quote.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(row));writer.writeheader();writer.writerows(rows)
            with self.assertRaisesRegex(ValueError,'replay price'):self.book(source)

    def test_research_zip_contains_separate_book_and_no_source_mutation(self):
        from tools.candidate_research import run
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,source=self.execute(root/'native',mode=24)
            before=tree_hash(source);output=root/'research';output.mkdir()
            result=run(source,output)
            self.assertEqual(result['manual_book_status'],'VERIFIED_LOCAL_BOOK')
            with zipfile.ZipFile(output/'candidate_review_v224.zip') as archive:
                self.assertEqual(json.loads(archive.read('manual_signal_review.json'))['counts']['LOSS'],1)
                self.assertIn('manual_signals.csv',archive.namelist())
            self.assertEqual(before,tree_hash(source))

    def test_boundary_two_seconds_is_valid_and_three_seconds_is_unavailable(self):
        for mode,status in ((30,'WIN'),(31,'UNAVAILABLE')):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,mode=mode)
                self.assertEqual(self.book(source)['counts'][status],1)
                self.assertLessEqual(result['panel_height'],1050)

    def test_muted_popup_and_disabled_replay_do_not_fabricate_receipts(self):
        for mode in (0,33):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,mode=mode,testing=(mode==0))
                report=self.book(source)
                self.assertEqual(report['counts']['WIN'],1)
                self.assertFalse(report['notification_delivery_verified'])
                if mode==33:self.assertEqual(result['official_alerts'],0)
                if mode==0:self.assertEqual(report['replay_manifest'],[])

    def test_partial_and_orphan_books_fail_closed(self):
        for partial in (True,False):
            with self.subTest(partial=partial),tempfile.TemporaryDirectory() as tmp:
                _,source=self.execute(tmp)
                if partial:(source/'manual_v218_2_1.csv.tmp').write_text('incomplete')
                else:next(source.glob('manual_v218_1_*.csv')).unlink()
                with self.assertRaises(ValueError):self.book(source)
                restored,_=self.execute(tmp,mode=20)
                self.assertTrue(restored['manual_error'])

    def test_disabled_replay_input_is_still_rejected_by_inherited_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,mode=32)
            self.assertNotEqual(result['init'],0)
            self.assertEqual(list(source.glob('manual_v218_*.csv')),[])
