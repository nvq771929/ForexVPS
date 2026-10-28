"""History transfer and live-forward separation; all fixtures are synthetic."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from intelligence.history_learning import train_snapshot,read_artifact,import_history,train_history
from intelligence.advanced_learning import update as update_advanced
from intelligence.demo_learning import collect,update
from tests.test_advanced_learning import rows
from tests.test_demo_learning import policy
from tests.fixtures import START
from tests.test_demo_learning_native import NativeHarness


def historical():
    data=rows(360,START-400*86400)
    for r in data:r['source']='BACKTEST_MT4_SIMULATED'
    return dict(policy=policy(),origin='BACKTEST_MT4',references=data,
        asof=data[-1]['entry_target']+1000,records=len(data))


class HistoryLearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=historical();cls.artifact,cls.report=train_snapshot(cls.snapshot,'a'*64)

    def test_history_model_is_qualified_only_for_observation_with_three_holdouts(self):
        a=self.artifact
        self.assertTrue(a['eligible_for_live_observation'])
        self.assertFalse(a['eligible_for_live_filter']);self.assertFalse(a['production_promoted'])
        self.assertEqual(len(a['heldout_slices']),3)
        self.assertFalse(any(s['failures'] for s in a['heldout_slices']))

    def test_backtest_never_qualifies_as_live_forward(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'Tester'):update_advanced(tmp,self.snapshot)
            with self.assertRaisesRegex(ValueError,'Tester'):update(tmp,self.snapshot)
            self.assertFalse(list(Path(tmp).glob('advanced_model*')))

    def test_training_source_must_be_historical_and_labels_cannot_be_mixed(self):
        for mode in ('origin','labels'):
            data=copy.deepcopy(self.snapshot)
            if mode=='origin':data['origin']='LIVE_MT4'
            else:data['references'][0]['source']='MT4_SIMULATED'
            with self.subTest(mode=mode),self.assertRaises(ValueError):train_snapshot(data,'a'*64)

    def test_tampered_artifact_is_rejected_and_low_samples_cannot_deploy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'model.json';a=copy.deepcopy(self.artifact);a['model']['weight'][0]+=1
            path.write_text(json.dumps(a))
            with self.assertRaisesRegex(ValueError,'checksum'):read_artifact(path)
        data=copy.deepcopy(self.snapshot);data['references']=data['references'][:12]
        a,r=train_snapshot(data,'b'*64)
        self.assertFalse(a['eligible_for_live_observation']);self.assertEqual(r['status'],'NOT_QUALIFIED')


class HistoryNativeTests(NativeHarness,unittest.TestCase):
    def test_tester_records_origin_seals_data_and_works_without_timer(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,testing=True)
            self.assertEqual(result['signals'],1)
            snap=collect(source);self.assertEqual(snap['origin'],'BACKTEST_MT4')
            self.assertEqual(snap['papers'][0]['source'],'BACKTEST_MT4_SIMULATED')
            self.assertEqual(snap['papers'][0]['status'],'WIN')
            self.assertTrue((source/'tester_complete.csv').is_file())
            with self.assertRaises(ValueError):update(source)
            output=Path(tmp)/'trained';report=train_history(source,output)
            self.assertEqual(report['status'],'NOT_QUALIFIED')
            self.assertFalse((output/'history_model.json').exists())


    def test_tester_lock_between_ticks_uses_only_previously_known_quote(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,mode=18,testing=True)
            self.assertEqual(result['signals'],1)
            from intelligence.native_ledger import read_directory
            from intelligence.demo_learning import LOGIC
            lock=next(r for r in read_directory(source,LOGIC) if r['event']['kind']==3)
            self.assertEqual(lock['event']['observedMs'],(START+268)*1000)
            cur=lock['state']['current']
            self.assertEqual(cur['highestBid'],cur['latestBid'])


    def test_tester_cannot_be_resumed_or_optimized_as_a_training_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(tmp,testing=True)
            first=(source/'tester_complete.csv').read_bytes()
            result,_=self.execute(tmp,testing=True)
            self.assertNotEqual(result['init'],0)
            self.assertEqual((source/'tester_complete.csv').read_bytes(),first)
        with tempfile.TemporaryDirectory() as tmp:
            result,_=self.execute(tmp,mode=19,testing=True)
            self.assertNotEqual(result['init'],0)


    def test_import_rebinds_id_but_preserves_weights_and_cannot_activate(self):
        a,_=train_snapshot(historical(),'a'*64)
        with tempfile.TemporaryDirectory() as tmp:
            _,live=self.execute(tmp)
            path=Path(tmp)/'model.json';path.write_text(json.dumps(a))
            receipt=import_history(path,live)
            self.assertEqual(receipt['phase'],'OBSERVE');self.assertFalse(receipt['automatic_filter'])
            state=json.loads((live/'advanced_state_v207.json').read_text())
            self.assertEqual(state['model']['weight'],a['model']['weight'])
            self.assertNotEqual(state['model']['model_id'],a['model']['model_id'])
            self.assertGreater(state['model']['created'],a['model']['created'])
            report=update_advanced(live,collect(live))
            self.assertEqual(report['native_forecasts'],0);self.assertEqual(report['status'],'OBSERVE')
            restored,_=self.execute(tmp,mode=20)
            self.assertEqual(restored['advanced_status'],'OBSERVE_ONLY')
            self.assertEqual(restored['advanced_id'],receipt['model_id'])
            with self.assertRaisesRegex(ValueError,'already exists'):import_history(path,live)


    def test_import_cannot_target_tester_or_future_data_or_wrong_policy(self):
        a,_=train_snapshot(historical(),'a'*64)
        with tempfile.TemporaryDirectory() as tmp:
            _,target=self.execute(tmp,testing=True)
            path=Path(tmp)/'model.json';path.write_text(json.dumps(a))
            with self.assertRaisesRegex(ValueError,'not Tester'):import_history(path,target)
        for mode in ('future','feed'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                _,target=self.execute(tmp)
                changed=copy.deepcopy(a);changed.pop('payload_sha256')
                if mode=='future':changed['history_asof']=START+10000
                else:changed['policy']['feed_hash']+=1
                from intelligence.history_learning import canonical
                import hashlib
                changed['payload_sha256']=hashlib.sha256(canonical(changed)).hexdigest()
                path=Path(tmp)/'model.json';path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):import_history(path,target)
                self.assertFalse((target/'advanced_state_v207.json').exists())


    def test_incomplete_tester_or_live_journal_cannot_train(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(tmp,testing=True);(source/'tester_complete.csv').unlink()
            with self.assertRaises((ValueError,OSError)):train_history(source,Path(tmp)/'model')
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(tmp)
            with self.assertRaises(ValueError):train_history(source,Path(tmp)/'model')


