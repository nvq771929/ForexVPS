"""V213 research is causal price research, never an executed trade or live evidence.

All model fixtures are synthetic. Native harness is source semantics, not MT4.
"""
import copy
import gzip
import hashlib
import json
import random
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from intelligence.demo_learning import collect,points
from intelligence.history_learning import train_history,train_prepared,read_artifact
from intelligence.native_ledger import read_directory
from intelligence.research_data import build
from intelligence.research_features import extract,CONTRACT,NAMES
from intelligence import research_model as rm
from intelligence import prepared_history as prepared
from tests.test_demo_learning import policy
from tests.fixtures import START
from tests.test_demo_learning_native import NativeHarness


def snapshot(days=360,per_day=8,nonlinear=False,noise=False):
    rng=random.Random(210);rows=[]
    for day in range(days):
        for i in range(per_day):
            start=START+day*86400+i*600;target=start+300
            x=[rng.uniform(-2,2) for _ in NAMES]
            up=(x[0]*x[1]>0) if nonlinear else x[0]>0
            if rng.random()<(.5 if noise else .025):up=not up
            move=10 if up else -10
            rows.append(dict(source='BACKTEST_MT4_PRICE_RESEARCH',cohort=CONTRACT,is_execution_trade=False,
                sample_id=f'{day}.{i}',analysis_start=start,entry_target=target,expiry_target=target+300,horizon=1,
                locked_at_ms=(start+268)*1000,feature_asof_ms=start*1000,entry_observed_ms=target*1000,
                exit_observed_ms=(target+300)*1000,available_at_ms=(target+301)*1000,
                entry_bid=1.1,exit_bid=1.1+move/100000,signed_points=move,
                features=x,status='UP' if up else 'DOWN',regime=i%8))
    return dict(policy=policy(),origin='BACKTEST_MT4',asof=rows[-1]['expiry_target']+1000,research=rows,records=len(rows))


class ResearchModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=snapshot();cls.artifact,cls.report,cls.predictions=rm.train(cls.data,'a'*64)

    def test_model_trains_and_qualifies_only_as_offline_research(self):
        a=self.artifact
        self.assertIsNotNone(a['model']);self.assertEqual(self.report['status'],'RESEARCH_QUALIFIED_OFFLINE')
        self.assertFalse(a['eligible_for_legacy_import']);self.assertFalse(a['eligible_for_live_filter'])
        self.assertFalse(a['production_promoted']);self.assertEqual(self.report['execution_trade_count'],0)
        self.assertTrue(all(p['native_pre_outcome_prediction'] is False for p in self.predictions))
        self.assertEqual(len(a['heldout_slices']),3)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'model.json';p.write_text(json.dumps(a))
            with self.assertRaisesRegex(ValueError,'Research models cannot import'):read_artifact(p)

    def test_chronological_split_purges_time_and_labels_and_uses_no_test_for_selection(self):
        tr,ca,te=rm.split(self.data['research'])
        self.assertLess(max(r['available_at_ms'] for r in tr),min(r['locked_at_ms'] for r in ca))
        self.assertLess(max(r['available_at_ms'] for r in ca),min(r['locked_at_ms'] for r in te))
        self.assertGreaterEqual(ca[0]['entry_target']-tr[-1]['entry_target'],86400)
        self.assertGreaterEqual(te[0]['entry_target']-ca[-1]['entry_target'],86400)
        changed=copy.deepcopy(self.data);first=te[0]['entry_target']
        for r in changed['research']:
            if r['entry_target']>=first:
                r['status']='DOWN' if r['status']=='UP' else 'UP';r['signed_points']*=-1
        a,_,_=rm.train(changed,'b'*64)
        for key in ('algorithm','mean','scale','weight','intercept','calibration_slope','calibration_intercept',
                    'baseline_global','baseline_by_regime','selection'):
            self.assertEqual(self.artifact['model'].get(key),a['model'].get(key),key)
        self.assertNotEqual(self.artifact['model']['offline'],a['model']['offline'])

    def test_json_tree_export_matches_sklearn_on_nonlinear_out_of_train_vectors(self):
        import numpy as np
        from threadpoolctl import threadpool_limits
        data=snapshot(80,20,nonlinear=True)['research'];train=data[:1200];test=data[1200:]
        with threadpool_limits(limits=2):
            for algorithm in ('logistic','hgb'):
                estimator,mean,scale=rm._fit_classifier(train,algorithm)
                model=rm.export_classifier(estimator,algorithm,mean,scale)
                expected=rm._raw(estimator,algorithm,np.asarray([r['features'] for r in test]),mean,scale)
                actual=[rm.raw_score(model,r['features']) for r in test]
                self.assertLess(max(abs(a-b) for a,b in zip(actual,expected)),1e-9)
        self.assertNotIn('pickle',json.dumps(model));self.assertTrue(model['trees'])

    def test_hgb_can_be_selected_by_inner_data_for_nonlinear_relationship(self):
        a,r,_=rm.train(snapshot(160,20,nonlinear=True),'a'*64)
        self.assertIsNotNone(a['model']);self.assertEqual(r['algorithm'],'hgb')
        self.assertEqual(a['model']['selection']['method'],'inner_chronological_brier_before_calibration_and_test')

    def test_noise_or_insufficient_data_never_qualifies_and_no_future_label_is_used(self):
        a,r,_=rm.train(snapshot(100,8,noise=True),'a'*64)
        self.assertFalse(a['eligible_for_research_review'])
        self.assertNotEqual(r['status'],'RESEARCH_QUALIFIED_OFFLINE')
        data=snapshot(3,8);a,r,_=rm.train(data,'a'*64)
        self.assertIsNone(a['model']);self.assertEqual(r['status'],'RESEARCH_NOT_TRAINED')
        data['asof']=data['research'][0]['available_at_ms']//1000
        _,r,_=rm.train(data,'a'*64);self.assertEqual(r['eligible_labels'],0)

    def test_mixed_sources_and_future_features_are_rejected(self):
        for mode in ('source','cohort','execution','future'):
            data=snapshot(3,8);r=data['research'][0]
            if mode=='source':r['source']='MT4_SIMULATED'
            elif mode=='cohort':r['cohort']='CONFIRMED_REFERENCE'
            elif mode=='execution':r['is_execution_trade']=True
            else:r['feature_asof_ms']=r['entry_observed_ms']
            with self.subTest(mode=mode),self.assertRaises(ValueError):rm.train(data,'a'*64)


class ResearchNativeTests(NativeHarness,unittest.TestCase):
    def records_and_groups(self,source):
        from collections import defaultdict
        records=read_directory(source);groups=defaultdict(list)
        for r in records:
            e=r['event']
            if e['analysisStart']>0 and e['kind'] in (3,4,5,6,7):groups[e['analysisStart']].append(r)
        return records,groups

    def test_wait_disabled_and_canceled_still_provide_price_labels_but_no_execution_wins(self):
        for mode in (17,5):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,mode=mode,testing=True)
                self.assertEqual(result['signals'],0)
                s=collect(source,include_research=True)
                self.assertEqual(s['references'],[])
                closed=[r for r in s['research'] if r['status'] in ('UP','DOWN','TIE')]
                self.assertGreater(len(closed),0)
                self.assertTrue(all(not r['is_execution_trade'] for r in closed))
                self.assertEqual(s['funnel']['counts'].get('simulated_execution_entries',0),0)
                self.assertEqual(s['research_data_audit']['execution_trade_count'],0)
                self.assertEqual(collect(source,include_research=True,compact=False),s)

    def test_features_ignore_current_quotes_cancel_direction_outcomes_and_respect_closed_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(tmp,testing=True);records,groups=self.records_and_groups(source)
            current=next(r['state']['current'] for r in records if r['event']['kind']==3)
            expected=extract(current);changed=copy.deepcopy(current)
            changed.update(latestBid=99.,lowestBid=0.,highestBid=100.,canceled=True,lockedDirection=-1)
            changed['candidate']['direction']=-1;self.assertEqual(extract(changed),expected)
            changed['anchor']['closeTime']+=300
            with self.assertRaisesRegex(ValueError,'non-causal'):extract(changed)
            altered=copy.deepcopy(groups)
            lock=next(r for rr in altered.values() for r in rr if r['event']['kind']==3)
            lock['state']['current']['analysisStart']+=300
            with self.assertRaisesRegex(ValueError,'relationship'):build(altered,policy(),START+1000,'BACKTEST_MT4',points)

    def test_missing_quotes_cannot_be_interpolated_and_wrong_outcome_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(tmp,testing=True);records,groups=self.records_and_groups(source)
            p=collect(source)['policy']
            rows,_=build(groups,p,START+1000,'BACKTEST_MT4',points)
            self.assertEqual(rows[0]['status'],'UP')
            for mode in ('entry_missing','entry_late','expiry_missing','exit_wrong','price_mismatch','duplicate'):
                g=copy.deepcopy(groups);rr=g[START]
                if mode=='entry_missing':g[START]=[r for r in rr if r['event']['kind']!=5]
                elif mode=='entry_late':next(r['event'] for r in rr if r['event']['kind']==5)['observedMs']+=3000
                elif mode=='expiry_missing':g[START]=[r for r in rr if r['event']['kind']!=6 or r['event']['outcomeHorizon']!=1]
                else:
                    e=next(r for r in rr if r['event']['kind']==6 and r['event']['outcomeHorizon']==1)
                    if mode=='exit_wrong':e['event']['outcome']=-1
                    elif mode=='price_mismatch':e['event']['bid']+=.0001
                    else:rr.append(copy.deepcopy(e))
                if mode in ('exit_wrong','price_mismatch','duplicate'):
                    with self.subTest(mode=mode),self.assertRaises(ValueError):build(g,p,START+1000,'BACKTEST_MT4',points)
                else:
                    r,_=build(g,p,START+1000,'BACKTEST_MT4',points)
                    self.assertFalse(any(x['status'] in ('UP','DOWN','TIE') and x['analysis_start']==START for x in r))

    def test_selected_horizon_and_direction_independence(self):
        for h in (1,2,3):
            with self.subTest(h=h),tempfile.TemporaryDirectory() as tmp:
                _,source=self.execute(tmp,direction=-1,horizon=h,testing=True)
                s=collect(source,include_research=True)
                r=s['research'][0];strict=s['references'][0]
                self.assertEqual(r['status'],'DOWN');self.assertEqual(strict['status'],'WIN')
                self.assertEqual(r['expiry_target'],r['entry_target']+h*300)
                self.assertEqual(r['horizon'],h)

    def test_prepared_roundtrip_checksum_contract_and_raw_journal_immutability(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);_,source=self.execute(tmp/'native',mode=17,testing=True)
            before={p.name:p.read_bytes() for p in source.iterdir()}
            out=tmp/'first';report=train_history(source,out)
            saved=out/prepared.NAME;snapshot,digest=prepared.load(saved)
            self.assertEqual(snapshot['research'],collect(source,include_research=True)['research'])
            self.assertGreater(report['research_eligible_labels'],0);self.assertEqual(report['eligible_labels'],0)
            self.assertFalse((out/'history_model.json').exists());self.assertFalse((out/'research_model.json').exists())
            def no_source_read(path):raise AssertionError('Prepared workflow reopened source journals')
            with patch('intelligence.history_learning.event_paths',no_source_read):
                report2=train_prepared(saved,tmp/'second')
            self.assertEqual(report2['processing']['event_read_passes'],0)
            self.assertEqual(report['dataset_sha256'],report2['dataset_sha256'])
            for name in ('research_model_candidate.json','history_model_candidate.json','research_reference.csv','data_funnel.json'):
                self.assertEqual((out/name).read_bytes(),(tmp/'second'/name).read_bytes(),name)
            self.assertEqual(before,{p.name:p.read_bytes() for p in source.iterdir()})
            for mode in ('checksum','contract','time','label','source'):
                a=json.loads(gzip.decompress(saved.read_bytes()))
                if mode=='contract':a['research_feature_contract']='BAD'
                elif mode=='time':a['snapshot']['research'][0]['feature_asof_ms']+=300000
                elif mode=='label':a['snapshot']['research'][0]['signed_points']+=1
                elif mode=='source':a['snapshot']['research'][0]['source']='BACKTEST_MT4_SIMULATED'
                else:a['snapshot']['asof']+=100
                if mode!='checksum':
                    a.pop('payload_sha256');a['payload_sha256']=hashlib.sha256(prepared.canonical(a)).hexdigest()
                path=tmp/(mode+'.gz');path.write_bytes(gzip.compress(prepared.canonical(a)))
                with self.subTest(mode=mode),self.assertRaises(ValueError):prepared.load(path)

    def test_cache_exists_before_fit_and_cli_can_reuse_it_without_native_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);_,source=self.execute(tmp/'native',mode=17,testing=True);out=tmp/'first'
            with patch('intelligence.history_learning.train_snapshot',side_effect=KeyboardInterrupt()):
                with self.assertRaises(KeyboardInterrupt):train_history(source,out)
            self.assertTrue((out/prepared.NAME).is_file());self.assertFalse((out/'history_report.json').exists())
            script=Path(__file__).resolve().parents[1]/'tools/train_history.py'
            proc=subprocess.run([sys.executable,str(script),'--prepared',str(out/prepared.NAME),
                '--output',str(tmp/'second'),'--progress-log',str(tmp/'progress.log')],text=True,capture_output=True,timeout=60)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertIn('PRICE RESEARCH',proc.stdout);self.assertIn('RESEARCH_NOT_TRAINED',proc.stdout)
            self.assertIn('offline only',proc.stdout);self.assertIn('[FINISHED]',proc.stdout)
            self.assertEqual(json.loads((tmp/'second/history_report.json').read_text())['processing']['event_read_passes'],0)
