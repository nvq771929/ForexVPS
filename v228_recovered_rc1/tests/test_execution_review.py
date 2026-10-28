import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest

from intelligence.demo_learning import collect
from intelligence.execution_review import review, observers
from tests.test_demo_learning_native import NativeHarness


class ExecutionReviewTests(NativeHarness,unittest.TestCase):
    def test_fresh_tick_after_gap_is_distinct_from_stale_incoming_price(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,mode=9,testing=True)
            s=collect(source,include_research=True)
            report,rows=review(s,'a'*64,source)
            self.assertEqual(result['signals'],0)
            self.assertEqual(report['classifications'],{'FRESH_INCOMING_TICK_AFTER_OBSERVATION_GAP':1})
            self.assertFalse(report['guard_changed']);self.assertFalse(report['network_latency_proven'])
            self.assertEqual(rows[0]['latest_tick_age_ms'],0)
            self.assertEqual(rows[0]['inter_tick_gap_ms'],4000)
            self.assertEqual(rows[0]['event_trigger'],'TICK')
            self.assertTrue(rows[0]['cancel_after_lock'])

    def test_without_observer_no_network_or_trigger_is_invented(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(tmp,mode=9,testing=True)
            s=collect(source,include_research=True)
            report,rows=review(s,'a'*64)
            self.assertEqual(report['classifications'],{'STORED_QUOTE_AGE_ONLY':1})
            self.assertIsNone(rows[0]['event_trigger']);self.assertIsNone(rows[0]['latest_tick_age_ms'])
            old=copy.deepcopy(s);old.pop('execution_traces')
            report,rows=review(old,'a'*64)
            self.assertEqual(report['status'],'REQUIRES_V211_CACHE_OR_RAW_JOURNALS')
            self.assertEqual(rows,[])

    def test_replayed_lock_records_only_prior_tick_and_its_trigger(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,mode=18,testing=True)
            path=next(source.glob('execution_diagnostics_*.csv'))
            with path.open() as f:rows=list(csv.DictReader(f))
            locks=[r for r in rows if r['event_kind']=='3']
            replay=next(r for r in locks if r['event_trigger']=='TESTER_REPLAY_LOCK')
            self.assertLess(int(replay['latest_tick_ms']),int(replay['observed_ms']))
            self.assertEqual(replay['schema'],'3')
            self.assertGreater(int(replay['event_minus_lock_ms']),-1)

    def test_timer_classification_and_clock_mismatch_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            _,source=self.execute(root/'native',mode=9,testing=True)
            s=collect(source,include_research=True)
            with next(source.glob('execution_diagnostics_*.csv')).open() as f:rows=list(csv.DictReader(f))
            cancel=next(r for r in rows if r['event_kind']=='4' and r['reason']=='QUOTE_GAP')
            # Synthetic timer observer, explicitly not authenticated feed evidence.
            cancel.update(schema='2',event_trigger='TIMER',latest_tick_ms=cancel['stored_quote_ms'],latest_tick_age_ms=cancel['stored_quote_age_ms'])
            folder=root/'observer';folder.mkdir();path=folder/'execution_diagnostics_synthetic.csv'
            def save():
                with path.open('w',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=list(cancel));w.writeheader();w.writerow(cancel)
            save();report,_=review(s,'a'*64,folder)
            self.assertEqual(report['classifications'],{'TIMER_WITHOUT_RECENT_TICK':1})
            cancel['latest_tick_age_ms']='3';save()
            with self.assertRaisesRegex(ValueError,'clock'):
                observers(folder)
