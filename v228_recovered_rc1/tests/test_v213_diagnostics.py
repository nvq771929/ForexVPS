"""Causal T+1, compatibility, exact cancellation traces and frozen diagnostics."""
import copy,csv,gzip,hashlib,json
from pathlib import Path
import subprocess,sys,tempfile,unittest
from unittest.mock import patch
from intelligence.demo_learning import collect
from intelligence import prepared_history as cache
from intelligence import research_model as rm
from intelligence.t1_features import CONTRACT,NAMES,extract
from intelligence.learning_diagnostics import diagnose,read_model
from intelligence.history_learning import train_history,train_prepared,read_artifact
from tests.test_demo_learning_native import NativeHarness
from tests.test_research_learning import snapshot
from tests.fixtures import START

ROOT=Path(__file__).resolve().parents[1]


def write_legacy_cache(path,s,digest):
    s=copy.deepcopy(s)
    for k in ('research_t1','t1_data_audit','execution_traces'):s.pop(k,None)
    for r in s['research']:
        r.pop('candidate_setup',None);r.pop('candidate_direction',None)
    a=dict(schema=1,kind='V210_PREPARED_HISTORY_V1',logic=2026101707,legacy_feature_version=1,
        research_feature_contract='CLOSED_ANCHOR_UP_V1',source_origin='BACKTEST_MT4',dataset_sha256=digest,snapshot=s)
    a['payload_sha256']=hashlib.sha256(cache.canonical(a)).hexdigest();path.write_bytes(gzip.compress(cache.canonical(a)))
    return s


class T1ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=snapshot();rr=cls.s.pop('research')
        import random
        rng=random.Random(211)
        for r in rr:
            r.update(cohort=CONTRACT,anchor_asof_ms=r['feature_asof_ms'],feature_asof_ms=r['locked_at_ms'])
            r['features'] += [rng.uniform(-1,1) for _ in range(len(NAMES)-len(r['features']))]
        cls.s['research_t1']=rr
        cls.artifact,cls.report,_=rm.train(cls.s,'a'*64,research_key='research_t1')

    def test_t1_classifier_uses_versioned_49_features_and_stays_offline(self):
        a=self.artifact
        self.assertEqual(a['feature_contract'],CONTRACT);self.assertEqual(len(a['feature_names']),49)
        self.assertEqual(len(a['model']['mean']),49)
        if a['model']['algorithm']=='logistic':self.assertEqual(len(a['model']['weight']),49)
        else:self.assertTrue(a['model']['trees'])
        self.assertEqual(a['model']['phase'],'OFFLINE_RESEARCH_ONLY')
        self.assertFalse(a['eligible_for_live_filter']);self.assertFalse(a['eligible_for_legacy_import'])
        self.assertTrue(a['independent_confirmation_required'])
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'model.json';p.write_text(json.dumps(a));self.assertEqual(read_model(p)['model'],a['model'])
            with self.assertRaisesRegex(ValueError,'Research models cannot import'):read_artifact(p)

    def test_frozen_diagnostics_match_model_metrics_and_do_not_fit(self):
        s=copy.deepcopy(self.s);s.update(papers=[],research=[],funnel={})
        before=copy.deepcopy(self.artifact)
        with patch('intelligence.research_model._fit',side_effect=AssertionError('diagnosis must not fit')):
            report,predictions,groups=diagnose(s,self.artifact,'a'*64)
        self.assertEqual(report['heldout_metrics'],self.artifact['model']['offline'])
        self.assertEqual(before,self.artifact);self.assertEqual(sum(report['rejection_counts'].values()),len(predictions))
        self.assertTrue(groups);self.assertTrue(all('DESCRIPTIVE_ONLY' in r['scope'] for r in groups))
        changed=copy.deepcopy(s);changed['research_t1'][0]['features'][0]+=.001
        with self.assertRaisesRegex(ValueError,'digest'):diagnose(changed,self.artifact,'a'*64)

    def test_low_confidence_and_domain_are_separate_reasons(self):
        s=copy.deepcopy(self.s);s.update(papers=[],research=[],funnel={})
        a=copy.deepcopy(self.artifact);m=a['model'];m.update(algorithm='logistic',weight=[0.]*49,intercept=0.,calibration_slope=1.,calibration_intercept=0.,low=[-100.]*49,high=[100.]*49)
        r,_,_=diagnose(s,a,'a'*64)
        self.assertEqual(r['rejection_counts'],{'LOW_CONFIDENCE':r['split_profiles']['test']['samples']})
        m['low'][0]=m['high'][0]=10000.
        r,_,_=diagnose(s,a,'a'*64);self.assertEqual(set(r['rejection_counts']),{'BOTH'})
        m['intercept']=2.
        r,_,_=diagnose(s,a,'a'*64);self.assertEqual(set(r['rejection_counts']),{'OUT_OF_DOMAIN'})

    def test_model_checksum_domain_and_contract_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'a.json'
            for mode in ('checksum','names','scale'):
                a=copy.deepcopy(self.artifact)
                if mode=='names':a['feature_names'][0]='future_exit'
                elif mode=='scale':a['model']['scale'][0]=0.
                else:a['model']['intercept']+=1
                if mode!='checksum':
                    a.pop('payload_sha256');a['payload_sha256']=hashlib.sha256(rm.canonical(a)).hexdigest()
                p.write_text(json.dumps(a))
                with self.subTest(mode=mode),self.assertRaises(ValueError):read_model(p)


class T1NativeTests(NativeHarness,unittest.TestCase):
    def test_t1_values_are_known_at_lock_and_differ_from_closed_anchor_only(self):
        from intelligence.native_ledger import read_directory
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(tmp,testing=True);s=collect(source,include_research=True)
            old=s['research'][0];r=s['research_t1'][0]
            self.assertEqual(len(r['features']),49);self.assertEqual(r['features'][:29],old['features'])
            self.assertEqual(r['feature_asof_ms'],r['locked_at_ms']);self.assertLess(r['feature_asof_ms'],r['entry_observed_ms'])
            cur=next(v['state']['current'] for v in read_directory(source) if v['event']['kind']==3)
            expected=extract(cur,cur['lockedAtMs'])
            changed=copy.deepcopy(cur);changed['lastQuoteMs']=cur['lockedAtMs']+1000
            with self.assertRaisesRegex(ValueError,'newer than LOCK'):extract(changed,cur['lockedAtMs'])
            changed=copy.deepcopy(cur);changed['entered']=True
            with self.assertRaises(ValueError):extract(changed,cur['lockedAtMs'])
            # Future labels and audit fields cannot enter the feature constructor.
            cur['exit_bid']=100.;cur['future_outcome']='WIN';self.assertEqual(extract(cur,cur['lockedAtMs']),expected)

    def test_post_lock_4_second_gap_is_still_blocked_and_diagnosed_as_observation_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,mode=9,testing=True);s=collect(source,include_research=True)
            self.assertEqual(result['signals'],0);self.assertEqual(s['papers'][0]['status'],'CANCELED')
            trace=next(r for r in s['execution_traces'] if r['published_at_lock'])
            self.assertTrue(trace['cancel_after_lock']);self.assertEqual(trace['first_cancel_reason'],'QUOTE_GAP')
            self.assertEqual(trace['cancel_quote_age_ms'],4000)
            self.assertEqual(trace['first_cancel_observed_ms'],(START+272)*1000)
            self.assertEqual(trace['entry_reason'],'QUOTE_GAP');self.assertFalse(trace['execution_signal_observed'])
            paths=list(source.glob('execution_diagnostics_*.csv'));self.assertTrue(paths)
            with paths[0].open() as f:rows=list(csv.DictReader(f))
            c=next(r for r in rows if r['event_kind']=='4' and r['reason']=='QUOTE_GAP')
            self.assertEqual(c['stored_quote_age_ms'],'4000');self.assertEqual(c['latest_tick_age_ms'],'0')
            self.assertEqual(c['inter_tick_gap_ms'],'4000')
            self.assertEqual(s['references'],[])

    def test_csv_and_dashboard_observers_do_not_change_native_entry_or_labels(self):
        for mode,count,status in ((0,1,'WIN'),(13,1,'LOSS'),(14,1,'TIE'),(5,0,'CANCELED')):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,mode=mode,testing=True);s=collect(source,include_research=True)
                self.assertEqual(result['signals'],count);self.assertEqual(s['papers'][0]['status'],status)
                self.assertTrue(list(source.glob('execution_diagnostics_*.csv')))
                self.assertEqual(collect(source,include_research=True,compact=False),s)
        text=(ROOT/'mt4/Include/EURUSD_M5_V224/UI.mqh').read_text()
        self.assertIn('BODiagnosticsStage',text);self.assertIn('Tuoi tick:',text)

    def test_new_cache_roundtrip_t1_clock_and_trace_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);_,source=self.execute(tmp/'native',mode=9,testing=True)
            s=collect(source,include_research=True);p=tmp/cache.NAME;cache.save(p,s,'a'*64)
            loaded,_=cache.load(p);self.assertEqual(loaded,s)
            for mode in ('future','clock','trace'):
                a=json.loads(gzip.decompress(p.read_bytes()))
                if mode=='future':a['snapshot']['research_t1'][0]['feature_asof_ms']+=1000
                elif mode=='clock':a['snapshot']['research_t1'][0]['features'][NAMES.index('quote_age_seconds')]+=1
                else:a['snapshot']['execution_traces'][0]['cancel_quote_age_ms']+=1
                a.pop('payload_sha256');a['payload_sha256']=hashlib.sha256(cache.canonical(a)).hexdigest()
                bad=tmp/'bad.gz';bad.write_bytes(gzip.compress(cache.canonical(a)))
                with self.subTest(mode=mode),self.assertRaises(ValueError):cache.load(bad)

    def test_v210_cache_is_supported_without_inventing_t1_or_cancel_timestamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);_,source=self.execute(tmp/'native',mode=9,testing=True)
            s=collect(source,include_research=True);p=tmp/'old/prepared_history_v210.json.gz';p.parent.mkdir()
            old=write_legacy_cache(p,s,'a'*64);before=p.read_bytes()
            loaded,digest=cache.load(p);self.assertEqual(loaded,old)
            with patch('intelligence.history_learning.event_paths',side_effect=AssertionError('cache cannot read raw files')):
                report=train_prepared(p,tmp/'trained')
            self.assertEqual(report['t1_research_status'],'REQUIRES_RAW_JOURNALS')
            self.assertFalse((tmp/'trained/t1_research_model_candidate.json').exists())
            diag=json.loads((tmp/'trained/execution_diagnostics.json').read_text())
            self.assertEqual(diag['entry_reason_for_published'],{'QUOTE_GAP':1});self.assertEqual(diag['exact_cancel_timing_available'],0)
            self.assertEqual(before,p.read_bytes())

    def test_raw_training_writes_t1_and_grouped_and_execution_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);_,source=self.execute(tmp/'native',testing=True)
            report=train_history(source,tmp/'out')
            self.assertGreater(report['t1_research_eligible_labels'],0)
            for name in ('t1_research_report.json','t1_research_model_candidate.json','learning_diagnostics.json',
                         'execution_diagnostics.json','execution_trace.csv','t1_research_reference.csv','grouped_research.csv'):
                self.assertTrue((tmp/'out'/name).is_file(),name)
            self.assertFalse((tmp/'out/t1_research_model.json').exists())
            proc=subprocess.run([sys.executable,str(ROOT/'tools/diagnose_learning.py'),'--folder',str(tmp/'out'),
                '--output',str(tmp/'diagnosis')],capture_output=True,text=True,timeout=60)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertIn('MODEL_NOT_FITTED',proc.stdout)
