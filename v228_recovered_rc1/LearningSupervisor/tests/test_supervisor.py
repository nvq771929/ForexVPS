import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import signal
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from supervisor.store import Store,digest
from supervisor.collector import Collector
from supervisor.audit import audit
from supervisor.learning import (train,fit_network,probabilities,load_model,verify_dataset,split_rows,metrics)
from supervisor.forecast import forecast,shadow_evaluation
from supervisor.dashboard import render
from supervisor.knowledge import summarize

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/'tests/fixtures'

def hashes(source):
    return {str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}

def extract(name,root):
    source=Path(root)/'journal';source.mkdir()
    with zipfile.ZipFile(FIXTURES/(name+'.zip')) as z:z.extractall(source)
    return source

def synthetic_rows(count=48):
    import numpy as np
    random=np.random.default_rng(224);rows=[]
    for i in range(count):
        f=random.normal(size=40).tolist();seq=random.normal(size=(32,29)).tolist();ctx=random.normal(size=50).tolist()
        ms=(1577836800+i*86400)*1000
        c=dict(signal_id=ms//1000-300,direction=1,setup=1,regime=2,published_ms=ms-32000,
            entry_ms=ms,expiry_ms=ms+300000,horizon=1,feature_asof_ms=ms-32000,
            feature_contract='V224_OFFICIAL_SIGNAL_SEQUENCE32_QUALITY_V1',features=f,sequence32=seq,context=ctx,
            origin='BACKTEST_MT4',policy=dict(test='SYNTHETIC_ONLY'))
        c['feature_hash']=digest({k:c[k] for k in ('features','context','sequence32','feature_asof_ms')})
        l=dict(signal_id=c['signal_id'],status='WIN' if f[0]>.1 else 'LOSS',available_at_ms=ms+301000)
        rows.append(dict(case=c,label=l))
    return rows

def toy_dataset(count=1200):
    d=dict(contract='V224_AUDITED_OFFICIAL_SIGNAL_DATASET_V1',origin='BACKTEST_MT4',
        policy=dict(test='SYNTHETIC_ONLY'),rows=synthetic_rows(count),broker_utc_offset_minutes=0,
        provenance='SYNTHETIC SOFTWARE TEST ONLY; no market evidence')
    d['sha256']=digest(d);return d

class NativeCompatibility(unittest.TestCase):
    def fixture(self,name,root):
        source=extract(name,root);store=Store(Path(root)/'output');c=Collector(source,store);return source,store,c

    def test_all_outcomes_and_cancel_survival(self):
        for name,status in [('win','WIN'),('loss','LOSS'),('tie','TIE'),('cancel_loss','LOSS'),('missing','UNAVAILABLE')]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                source,store,c=self.fixture(name,tmp);before=hashes(source)
                d=audit(c,broker_utc_offset_minutes=0)
                self.assertEqual([r['label']['status'] for r in d['rows']],[status])
                self.assertEqual(len(store.all('case')),1)
                if name=='cancel_loss':self.assertTrue(d['rows'][0]['label']['native_canceled'])
                self.assertEqual(before,hashes(source));store.close()

    def test_restart_idempotent_and_source_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            source,store,c=self.fixture('win',tmp);c.poll();c.poll()
            self.assertEqual(len(store.all('case')),1);last=c.last;store.close()
            store=Store(Path(tmp)/'output');again=Collector(source,store)
            self.assertEqual(again.last,last);self.assertEqual(again.poll(),0)
            p=source/'event_000000000001.bin';p.write_bytes(p.read_bytes()+b'changed')
            with self.assertRaisesRegex(ValueError,'bytes changed'):again.verify_prefix()
            store.close()

    def test_gap_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source,store,c=self.fixture('win',tmp)
            (source/'event_000000000001.bin').unlink()
            with self.assertRaisesRegex(ValueError,'gap'):c.poll()
            store.close()

    def test_withheld_and_no_signal_do_not_train(self):
        for name in ('withheld','rejected'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                _,store,c=self.fixture(name,tmp);d=audit(c)
                self.assertEqual(d['rows'],[]);self.assertEqual(store.all('label'),[])
                self.assertEqual(c.status()['official_cases'],0)
                store.close()

    def test_batch_paths_include_wait_and_do_not_become_features(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,store,c=self.fixture('win',tmp);audit(c,include_paths=True)
            study=json.loads((store.output/'path_diagnostics.json').read_text())
            self.assertFalse(study['feature_eligible'])
            self.assertTrue(any(k.startswith('decision:') for k in study['windows']))
            self.assertTrue(any(k.startswith('official:') for k in study['windows']))
            store.close()

    def test_insufficient_data_saves_no_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,store,c=self.fixture('win',tmp);audit(c)
            result=train(store.output/'audited_dataset.json',store.output/'models')
            self.assertEqual(result['status'],'COLLECTING')
            self.assertFalse(list((store.output/'models').glob('model_*.json')))
            store.close()

    def test_bad_tester_seal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source,store,c=self.fixture('win',tmp);(source/'tester_complete.csv').unlink()
            with self.assertRaises(FileNotFoundError):audit(c)
            store.close()

    def test_fact_database_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);store.put('a',1,dict(x=1));store.commit()
            with self.assertRaises(ValueError):store.put('a',1,dict(x=2))
            with self.assertRaises(sqlite3.IntegrityError):store.db.execute("UPDATE facts SET body='{}'")
            store.close()

    def test_cli_rejects_nested_output_before_creating_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=extract('win',tmp);before=hashes(source)
            result=subprocess.run([sys.executable,str(ROOT/'run_supervisor.py'),'collect','--source',str(source),
                '--output',str(source/'new_output')],capture_output=True)
            self.assertNotEqual(result.returncode,0);self.assertFalse((source/'new_output').exists())
            self.assertEqual(before,hashes(source))

    def test_dashboard_and_knowledge_are_honest(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,store,c=self.fixture('win',tmp);d=audit(c,broker_utc_offset_minutes=0);k=summarize(d,store)
            s=render(c,Path(tmp)/'Common/Files')
            self.assertEqual(s['level'],1);self.assertFalse(s['activation_allowed'])
            self.assertTrue((Path(tmp)/'Common/Files/V224Supervisor/learning_status.csv').exists())
            self.assertEqual(k['proposals'],[])
            self.assertIn('Bộ học đã ghi nhận gì?',(store.output/'dashboard.html').read_text())
            before=len(store.all('progress'));render(c)
            self.assertEqual(len(store.all('progress')),before)
            store.close()

    def test_fixture_provenance_hashes(self):
        manifest=json.loads((FIXTURES/'manifest.json').read_text())
        for name,info in manifest['fixtures'].items():
            self.assertEqual(hashlib.sha256((FIXTURES/(name+'.zip')).read_bytes()).hexdigest(),info['sha256'])

    def test_cli_cycle_then_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=extract('win',tmp);output=Path(tmp)/'cli'
            command=[sys.executable,str(ROOT/'run_supervisor.py'),'cycle','--source',str(source),'--output',str(output),'--broker-utc-offset-minutes','0']
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue((output/'knowledge.json').exists())
            self.assertEqual(json.loads((output/'models/training_status.json').read_text())['status'],'COLLECTING')
            result=subprocess.run(command[:2]+['export']+command[3:],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue((output/'V224_Supervisor_Review.zip').exists())

    def test_watch_background_worker_ingests_labels_without_ea_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=extract('live_win',tmp);before=hashes(source);output=Path(tmp)/'watch'
            log=Path(tmp)/'watch.log'
            with log.open('w') as f:
                proc=subprocess.Popen([sys.executable,str(ROOT/'run_supervisor.py'),'watch','--source',str(source),
                    '--output',str(output),'--broker-utc-offset-minutes','0'],stdout=f,stderr=f)
            try:
                stop=time.monotonic()+25;state={}
                while time.monotonic()<stop and proc.poll() is None:
                    status=output/'status.json'
                    if status.exists():
                        state=json.loads(status.read_text())
                        if state.get('audited_decisive')==1:break
                    time.sleep(.2)
                self.assertEqual(state.get('audited_decisive'),1,log.read_text())
                self.assertEqual(state['prospective'],0)
                self.assertEqual(before,hashes(source))
            finally:
                if proc.poll() is None:
                    if sys.platform=='win32':proc.terminate()
                    else:proc.send_signal(signal.SIGINT)
                    proc.wait(timeout=10)

    def test_export_has_consistent_database(self):
        from supervisor.packaging import export_review
        with tempfile.TemporaryDirectory() as tmp:
            _,store,c=self.fixture('loss',tmp);audit(c);p=export_review(store.output)
            with zipfile.ZipFile(p) as z:self.assertIn('review_database.sqlite',z.namelist())
            store.close()

class ModelSoftwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=synthetic_rows()
        cls.net=fit_network(cls.rows,'CAUSAL_TCN32_CONTEXT50',epochs=1)

    def model(self):
        now=time.time_ns()//1000000
        m=dict(contract='V224_OFFICIAL_SIGNAL_SHADOW_MODEL_V1',feature_contract='V224_OFFICIAL_SIGNAL_SEQUENCE32_QUALITY_V1',
            target='OFFICIAL_SIGNAL_MT4_WIN_VS_LOSS',policy=self.rows[0]['case']['policy'],network=copy.deepcopy(self.net),
            threshold=.60,created_utc_ms=now-10000,evaluation_cutoff_ms=now-86400000,
            training_broker_utc_offset_minutes=0,activation_allowed=False,train_prior=.5)
        m['model_id']=digest(m);return m

    def live_case(self):
        c=copy.deepcopy(self.rows[0]['case']);now=time.time_ns()//1000000
        c.update(feature_asof_ms=now-1000,published_ms=now-1000,entry_ms=now+32000,expiry_ms=now+332000)
        c['feature_hash']=digest({k:c[k] for k in ('features','context','sequence32','feature_asof_ms')})
        return c

    def test_deep_fit_produces_finite_probabilities(self):
        p=probabilities(self.net,self.rows)
        self.assertEqual(len(p),len(self.rows));self.assertTrue(all(0<v<1 for v in p))

    def test_model_json_roundtrip_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'model.json';m=self.model();p.write_text(json.dumps(m))
            loaded=load_model(p);self.assertEqual(probabilities(loaded['network'],self.rows),probabilities(self.net,self.rows))
            m['threshold']=.1;p.write_text(json.dumps(m))
            with self.assertRaises(ValueError):load_model(p)

    def test_prospective_requires_origin_clock_and_actual_time(self):
        for origin,offset,clock,expected in [('LIVE_MT4',0,True,'PROSPECTIVE_SHADOW'),
                ('BACKTEST_MT4',0,True,'RETROSPECTIVE_ONLY'),('LIVE_MT4',None,True,'RETROSPECTIVE_ONLY'),
                ('LIVE_MT4',0,False,'RETROSPECTIVE_ONLY')]:
            with self.subTest(origin=origin,offset=offset,clock=clock),tempfile.TemporaryDirectory() as tmp:
                store=Store(tmp);c=self.live_case();m=self.model()
                result=forecast(store,c,m,origin,offset,clock)
                receipt=store.all('forecast_receipt')[0]
                self.assertEqual(receipt['timing'],expected)
                self.assertFalse(result['ea_control_enabled']);store.close()

    def test_commit_crossing_deadline_cannot_be_forward_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);c=self.live_case();m=self.model()
            with patch('supervisor.forecast.time.time_ns',side_effect=[(c['entry_ms']-1)*1000000,(c['entry_ms']+1)*1000000]):
                # Force the initial feature clock to be fresh enough for a candidate.
                c['feature_asof_ms']=c['entry_ms']-10000
                forecast(store,c,m,'LIVE_MT4',0,True)
            self.assertEqual(store.all('forecast_receipt')[0]['timing'],'RETROSPECTIVE_ONLY');store.close()

    def test_late_replay_is_not_counted_as_forward(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);m=self.model();store.put('model',m['model_id'],m)
            c=copy.deepcopy(self.rows[0]['case']);forecast(store,c,m,'LIVE_MT4',0)
            store.put('label',c['signal_id'],self.rows[0]['label'])
            result=shadow_evaluation(store)[0]
            self.assertIsNone(result['metrics']);store.close()

    def test_no_duplicate_forecast_and_no_reversal_from_low_win_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);c=self.live_case();m=self.model();forecast(store,c,m,'LIVE_MT4',0)
            self.assertIsNone(forecast(store,c,m,'LIVE_MT4',0))
            self.assertIn(store.all('forecast')[0]['shadow_suggestion'],('CALL','WAIT'))
            store.close()

    def test_dataset_clock_origin_and_future_feature_checks(self):
        original=toy_dataset(10)
        self.assertEqual(verify_dataset(original)['origin'],'BACKTEST_MT4')
        for field in ('clock','origin','feature'):
            d=copy.deepcopy(original);d.pop('sha256')
            if field=='clock':d['rows'][0]['case']['feature_asof_ms']=d['rows'][0]['case']['entry_ms']+1
            elif field=='origin':d['rows'][0]['case']['origin']='LIVE_MT4'
            else:d['rows'][0]['case']['features'][0]+=1
            d['sha256']=digest(d)
            with self.subTest(field=field),self.assertRaises(ValueError):verify_dataset(d)

    def test_chronological_splits_embargo_and_no_label_overlap(self):
        parts=split_rows(toy_dataset(1200))
        for a,b in [('train','calibration'),('calibration','evaluation')]:
            self.assertLess(max(r['label']['available_at_ms'] for r in parts[a]),min(r['case']['entry_ms'] for r in parts[b])-86400000)
        ids=[r['case']['signal_id'] for part in parts.values() for r in part]
        self.assertEqual(len(ids),len(set(ids)))

    def test_full_fitting_path_freezes_model_and_reuses_experiment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'synthetic.json';path.write_text(json.dumps(toy_dataset()))
            result=train(path,Path(tmp)/'models')
            self.assertEqual(result['status'],'FROZEN_SHADOW')
            m=load_model(result['model_file']);self.assertFalse(m['activation_allowed'])
            self.assertEqual(result['model_id'],train(path,Path(tmp)/'models')['model_id'])
            self.assertEqual(len(list((Path(tmp)/'models/experiments').glob('*.json'))),1)
            # A new audit receipt for the same market cases is not a fresh holdout.
            refreshed=toy_dataset();refreshed.pop('sha256');refreshed['audit_revision']='same_cases_new_receipt'
            refreshed['sha256']=digest(refreshed);path.write_text(json.dumps(refreshed))
            again=train(path,Path(tmp)/'models')
            self.assertEqual(again['counts']['evaluation'],0)
            self.assertEqual(again['status'],'COLLECTING')
            self.assertEqual(len(list((Path(tmp)/'models').glob('model_*.json'))),1)

if __name__=='__main__':unittest.main()
