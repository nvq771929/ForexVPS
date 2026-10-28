"""Pre-lock protocol, causal features and worker tests; no market qualification."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile
from dialogue.protocol import read_request,read_row,REPLY,REQUEST,row_bytes
from dialogue.features import extract
from dialogue.worker import Worker
from dialogue.dataset import prepare
from dialogue.training import train
from dialogue.models import load,qualification
from supervisor.store import digest
from supervisor.learning import fit_network
from test_supervisor import synthetic_rows

ROOT=Path(__file__).resolve().parents[1]

def fixture(root,name='prelock_tester'):
    source=Path(root)/'native';source.mkdir()
    with zipfile.ZipFile(ROOT/'tests/fixtures'/f'{name}.zip') as z:z.extractall(source)
    return source

def hashes(source):
    return {str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}

class DialogueTests(unittest.TestCase):
    def test_real_native_prelock_snapshot_is_not_a_lock_model_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=fixture(tmp);path=next((source/'advisory_v224').glob('*/request_*.csv'))
            r=read_request(path);f=extract(r)
            self.assertFalse(r['snapshot']['state']['current']['locked'])
            self.assertEqual(f['contract'],'V224_PRELOCK_DIALOGUE_FEATURES_V1')
            self.assertEqual((len(f['features']),len(f['context'])),(40,50))
            from intelligence.t1_corrected import extract as locked_extract
            with self.assertRaises(ValueError):locked_extract(r['snapshot']['state']['current'],r['meta']['observed_ms'])

    def test_tester_collection_and_tick_labels_never_write_replies(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=fixture(tmp);before=hashes(source);worker=Worker(source,Path(tmp)/'out',0)
            s=worker.poll();d=prepare(worker)
            self.assertGreater(s['requests'],0);self.assertEqual(s['replies'],0)
            self.assertEqual(len(d['rows']),1)
            self.assertEqual(d['rows'][0]['label']['status'],'WIN')
            self.assertEqual(worker.poll()['new_requests'],0)
            trained=train(d,worker.output/'models');self.assertEqual(trained['status'],'COLLECTING')
            self.assertFalse(list((worker.output/'models').glob('prelock_model_*.json')))
            self.assertEqual(before,hashes(source));worker.close()

    def test_missing_boundary_tick_is_unavailable_without_interpolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=fixture(tmp);inputs=list(source.glob('input_*.csv'))
            self.assertTrue(inputs)
            # Remove the replay file altogether: native snapshots cannot fill price boundaries.
            for p in inputs:p.unlink()
            worker=Worker(source,Path(tmp)/'out',0);worker.poll();d=prepare(worker)
            self.assertEqual(d['rows'][0]['label']['status'],'UNAVAILABLE');worker.close()

    def test_request_crc_or_identity_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=fixture(tmp);p=next((source/'advisory_v224').glob('*/request_*.csv'))
            r=read_request(p)['meta'];r['target']+=300;p.write_bytes(row_bytes(REQUEST,r))
            with self.assertRaises(ValueError):read_request(p)

    def test_unknown_clock_collects_only_and_late_requests_are_not_answered(self):
        for offset in (None,0):
            with self.subTest(offset=offset),tempfile.TemporaryDirectory() as tmp:
                source=fixture(tmp,'prelock_live');before=hashes(source)
                w=Worker(source,Path(tmp)/'out',offset);s=w.poll()
                self.assertEqual(s['replies'],0);self.assertEqual(before,hashes(source));w.close()

    def test_real_live_request_gets_scoped_abstention_and_durable_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=fixture(tmp,'prelock_live');p=sorted((source/'advisory_v224').glob('*/request_*.csv'))[0]
            r=read_request(p)['meta'];w=Worker(source,Path(tmp)/'out',0)
            # Simulated wall clock for software test, not prospective market evidence.
            with patch('dialogue.worker.time.time_ns',return_value=(r['observed_ms']+1000)*1000000):s=w.poll()
            self.assertEqual(s['replies'],1)
            response,_=read_row(p.with_name(f"reply_{r['sequence']:012d}.csv"),REPLY)
            self.assertEqual(response['decision'],0);self.assertEqual(response['validated'],0)
            self.assertEqual(response['model_id'],'NONE')
            self.assertEqual(w.store.all('prediction')[0]['timing'],'PROSPECTIVE_PRELOCK')
            self.assertEqual(w.poll()['new_requests'],0);w.close()

    def test_rc1_lock_model_cannot_be_loaded_as_prelock_adviser(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'old.json';m=dict(contract='V224_OFFICIAL_SIGNAL_SHADOW_MODEL_V1',feature_contract='V224_OFFICIAL_SIGNAL_SEQUENCE32_QUALITY_V1')
            m['model_id']=digest(m);p.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'LOCK/shadow'):load(p)

    def test_fixture_hashes(self):
        for name in ('prelock_manifest','prelock_live_manifest'):
            m=json.loads((ROOT/'tests/fixtures'/f'{name}.json').read_text())
            self.assertEqual(hashlib.sha256((ROOT/'tests/fixtures'/m['file']).read_bytes()).hexdigest(),m['sha256'])

    def test_qualification_recomputes_gates_and_rejects_retrospective_evidence(self):
        model=dict(model_id='a'*64,created_utc_ms=1000,train_prior=.5,threshold=.6,offline_review_passed=True)
        policy=dict(feed_hash=1,policy_hash=2);rows=[]
        for i in range(160):
            request=2000+i*86400000;entry=request+60000
            rows.append(dict(origin='LIVE_MT4',status='WIN' if i%5 else 'LOSS',model_id=model['model_id'],
                feature_contract='V224_PRELOCK_DIALOGUE_FEATURES_V1',feed_hash=1,policy_hash=2,analysis_start=i+1,horizon=1,
                request_utc_ms=request,written_utc_ms=request+1,durable_utc_ms=request+2,ea_received_utc_ms=request+3,
                deadline_utc_ms=request+1000,ea_finalized_utc_ms=request+2000,entry_utc_ms=entry,expiry_utc_ms=entry+300000,
                label_available_utc_ms=entry+300001,probability=.8,in_domain=True,request_sha256='b'*64,label_receipt_sha256='c'*64))
        report=dict(contract='V224_PRELOCK_FORWARD_VALIDATION_V1',feature_contract='V224_PRELOCK_DIALOGUE_FEATURES_V1',model_id=model['model_id'],policy=policy,rows=rows)
        report['sha256']=digest(report)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'receipt.json';p.write_text(json.dumps(report))
            self.assertTrue(qualification(p,model,policy)['qualified'])
            report.pop('sha256');report['rows'][0]['durable_utc_ms']=report['rows'][0]['entry_utc_ms']+1
            report['sha256']=digest(report);p.write_text(json.dumps(report))
            with self.assertRaises(ValueError):qualification(p,model,policy)

    def test_unqualified_model_has_no_permission_by_boolean_alone(self):
        self.assertFalse(qualification(None,dict(model_id='a'*64),dict())['qualified'])

    def test_fabricated_good_metrics_cannot_authorize_worker_without_actual_evidence(self):
        from dialogue.features import NAMES,CONTEXT_NAMES
        from intelligence.demo_learning import read_policy
        with tempfile.TemporaryDirectory() as tmp:
            source=fixture(tmp,'prelock_live');policy=read_policy(source)
            model=dict(contract='V224_PRELOCK_ADVISOR_MODEL_V1',feature_contract='V224_PRELOCK_DIALOGUE_FEATURES_V1',
                target='REQUEST_DIRECTION_MT4_WIN_VS_LOSS',feature_names=list(NAMES),context_names=list(CONTEXT_NAMES),
                training_origin='BACKTEST_MT4',broker_utc_offset_minutes=0,policy=policy,
                query_policy=dict(interval=30,max_age=30,reserve=5),created_utc_ms=1000,trained_cutoff_utc_ms=999,
                threshold=.60,train_prior=.5,offline_review_passed=True,network=fit_network(synthetic_rows(24),'LOGISTIC40',epochs=1))
            model['model_id']=digest(model);rows=[]
            for i in range(160):
                t=2000+i*86400000;e=t+60000
                rows.append(dict(origin='LIVE_MT4',status='WIN' if i%5 else 'LOSS',model_id=model['model_id'],
                    feature_contract='V224_PRELOCK_DIALOGUE_FEATURES_V1',feed_hash=policy['feed_hash'],policy_hash=policy['policy_hash'],
                    analysis_start=i+1,horizon=1,request_utc_ms=t,written_utc_ms=t+1,durable_utc_ms=t+2,ea_received_utc_ms=t+3,
                    deadline_utc_ms=t+1000,ea_finalized_utc_ms=t+2000,entry_utc_ms=e,expiry_utc_ms=e+300000,
                    label_available_utc_ms=e+300001,probability=.8,in_domain=True,request_sha256='b'*64,label_receipt_sha256='c'*64))
            report=dict(contract='V224_PRELOCK_FORWARD_VALIDATION_V1',feature_contract='V224_PRELOCK_DIALOGUE_FEATURES_V1',
                model_id=model['model_id'],policy=policy,rows=rows)
            report['sha256']=digest(report);path=Path(tmp)/'forged_receipt.json';path.write_text(json.dumps(report))
            self.assertTrue(qualification(path,model,policy)['qualified'])
            with self.assertRaisesRegex(ValueError,'not reproduced'):
                Worker(source,Path(tmp)/'out',0,model,path)

    def test_new_contract_full_fit_freezes_shadow_model_without_old_lock_conversion(self):
        rows=synthetic_rows(1200)
        for r in rows:
            c=r['case'];c['feature_asof_ms']=c['entry_ms']-60000;c['feature_contract']='V224_PRELOCK_DIALOGUE_FEATURES_V1'
            r['query']=dict(meta=dict(observed_ms=c['feature_asof_ms'],deadline_ms=c['entry_ms']-37000),
                feature=dict(features=c['features'],context=c['context']),query_policy=dict(interval=30,max_age=30,reserve=5))
        d=dict(contract='V224_PRELOCK_REQUEST_DATASET_V1',feature_contract='V224_PRELOCK_DIALOGUE_FEATURES_V1',
            rows=rows,origin='BACKTEST_MT4',policy=dict(test='SYNTHETIC_ONLY'),broker_utc_offset_minutes=0,
            provenance='SYNTHETIC SOFTWARE ARRAYS ONLY; not old LOCK market records')
        d['sha256']=digest(d)
        with tempfile.TemporaryDirectory() as tmp:
            result=train(d,Path(tmp));self.assertEqual(result['status'],'FROZEN_SHADOW')
            model=load(result['model_file']);self.assertEqual(model['query_policy'],dict(interval=30,max_age=30,reserve=5))
            self.assertFalse(model['activation_allowed'])
            self.assertFalse(qualification(None,model,model['policy'])['qualified'])
            self.assertEqual(train(d,Path(tmp))['model_id'],model['model_id'])

if __name__=='__main__':unittest.main()
