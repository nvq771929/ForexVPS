"""Causal candidate enrollment, native observer parity and immutable research lifecycle."""
import copy,gzip,hashlib,json,random,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from intelligence import candidate_data as data,candidate_learning as learning,candidate_registry as registry
from intelligence.candidate_features import NAMES,extract
from intelligence.candidate_rules import summarize
from intelligence.t1_corrected import extract as t1_extract
from intelligence.native_ledger import read_directory
from intelligence.lease import exclusive
from tests.test_demo_learning_native import NativeHarness,ROOT
from tests.test_demo_learning import policy
from tests.test_v214_execution import tree_hash,read_csv,write_csv
from tests.fixtures import sr_bars
from tests.context_fixtures import trend_bars,breakout_bars


def snapshot(n=30,days=100):
    rng=random.Random(215);start=1767225600;rows=[]
    for i in range(n):
        day=i*days//n;target=start+day*86400+3600+(i%20)*900
        r=data.base_row(target-300,(target-32)*1000,1 if i%3 else 2,1 if i%2 else -1,1,True,policy())
        x=[rng.uniform(-1,1) for _ in NAMES];win=rng.random()<(.85 if x[0]>.1 else .2)
        r.update(features=x,quality_status='FAVORABLE' if win else 'ADVERSE',signed_points=10 if win else -10,
            available_at_ms=(target+301)*1000,lock_reason='OK')
        rows.append(r)
    return data.finish(rows,policy(),'BACKTEST_MT4',(start+(days+1)*86400)*1000,n*3,'a'*64,
        list(range(start//86400,start//86400+days)),dict(synthetic=True))


class CandidateLearningTests(unittest.TestCase):
    def test_collecting_never_fits_or_exports_a_model(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(learning,'fitted',side_effect=AssertionError('Must not fit')):
            result=learning.train(snapshot(),Path(tmp)/'run')
            self.assertEqual(result['status'],'COLLECTING');self.assertFalse(result['model_fitted'])
            self.assertFalse((Path(tmp)/'run/candidate_model.json').exists())
            self.assertTrue(any(result['deficits'].values()))
            registry.checked(json.loads((Path(tmp)/'run/candidate_report.json').read_bytes()),'report_sha256')

    def test_temporal_split_and_label_availability_are_purged(self):
        s=snapshot(1800);parts,windows=learning.split(s)
        self.assertTrue(max(r['entry_target'] for r in parts['train'])<windows['calibration_start']-86400)
        cut=windows['calibration_start']*1000
        row=parts['train'][0];row['available_at_ms']=cut
        self.assertNotIn(row,learning.eligible(parts['train'],cut))
        row['available_at_ms']=cut-1;row['features']=None
        self.assertNotIn(row,learning.eligible(parts['train'],cut))

    def test_large_synthetic_fit_is_offline_and_holdout_never_changes_weights(self):
        s=snapshot(1800)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);r=learning.train(s,root/'a')
            self.assertTrue(r['model_fitted']);self.assertFalse(r['model_import_allowed'])
            a=json.loads((root/'a/candidate_model.json').read_bytes());registry.checked(a)
            self.assertFalse(a['eligible_for_observe']);self.assertFalse(a['eligible_for_native_filter'])
            modified=copy.deepcopy(s);_,windows=learning.split(modified)
            for row in modified['rows']:
                if row['entry_target']>=windows['evaluation_start']:
                    row['quality_status']='ADVERSE' if row['quality_status']=='FAVORABLE' else 'FAVORABLE'
                    row['signed_points']=-row['signed_points'];row['features']=[10000.]*len(NAMES)
            modified.pop('payload_sha256');modified['payload_sha256']=hashlib.sha256(data.canonical(modified)).hexdigest()
            learning.train(modified,root/'b')
            b=json.loads((root/'b/candidate_model.json').read_bytes())
            self.assertEqual(a['model'],b['model'])
            from intelligence.history_learning import read_artifact
            with self.assertRaisesRegex(ValueError,'Unsupported history artifact'):read_artifact(root/'a/candidate_model.json')
            predictions=read_csv(root/'a/candidate_predictions.csv')
            self.assertTrue(all(p['source']=='RETROSPECTIVE_PRICE_RESEARCH' for p in predictions))

    def test_registry_skips_identical_and_under_scheduled_runs_and_rejects_rewriting(self):
        s=snapshot()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);first=registry.update(s,root);before=tree_hash(root/first['run'])
            self.assertEqual(registry.update(s,root)['status'],'UNCHANGED')
            newer=copy.deepcopy(s);newer.pop('payload_sha256');newer['asof_ms']+=86400000;newer['native_records']+=1
            newer['payload_sha256']=hashlib.sha256(data.canonical(newer)).hexdigest()
            self.assertEqual(registry.update(newer,root)['status'],'WAIT_NEW_DATA')
            self.assertEqual(tree_hash(root/first['run']),before)
            newer['rows'][0]['features'][0]+=1;newer.pop('payload_sha256')
            newer['payload_sha256']=hashlib.sha256(data.canonical(newer)).hexdigest()
            with self.assertRaisesRegex(ValueError,'LOCK facts'):registry.update(newer,root)
            with exclusive(root/'candidate_research.lock'):
                with self.assertRaises(RuntimeError):registry.update(s,root)

    def test_registry_binds_origin_and_preserves_prior_frozen_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);s=snapshot();registry.update(s,root)
            state=registry.checked(json.loads((root/'registry.json').read_bytes()))
            state['last_frozen_candidate']='prior_offline_candidate';registry.write_state(root/'registry.json',state)
            self.assertEqual(registry.update(s,root)['last_frozen_candidate'],'prior_offline_candidate')
            s['origin']='LIVE_MT4';s.pop('payload_sha256');s['payload_sha256']=hashlib.sha256(data.canonical(s)).hexdigest()
            with self.assertRaisesRegex(ValueError,'origin/feed/policy'):registry.update(s,root)

    def test_registry_research_retry_requires_both_elapsed_days_and_new_mature_labels(self):
        s=snapshot()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);first=registry.update(s,root);before=tree_hash(root/first['run'])
            more=copy.deepcopy(s);base=more['asof_ms']//1000
            for i in range(60):
                row=copy.deepcopy(s['rows'][i%len(s['rows'])]);target=base+86400+i*900
                row.update(sample_id='new.'+str(i),analysis_start=target-300,entry_target=target,expiry_target=target+300,
                    locked_at_ms=(target-32)*1000,feature_asof_ms=(target-32)*1000,available_at_ms=(target+301)*1000)
                more['rows'].append(row)
            more['asof_ms']+=9*86400000;more['native_records']+=180
            more['calendar_days']+=list(range(base//86400,base//86400+9))
            more.pop('payload_sha256');more['payload_sha256']=hashlib.sha256(data.canonical(more)).hexdigest()
            result=registry.update(more,root)
            self.assertTrue(result['training_attempted']);self.assertEqual(result['new_decisive_since_attempt'],60)
            self.assertNotEqual(first['run'],result['run']);self.assertEqual(tree_hash(root/first['run']),before)


class CandidateNativeTests(NativeHarness,unittest.TestCase):
    def test_native_decisions_match_frozen_v214_bytes_across_three_setups_and_both_directions(self):
        golden=json.loads((ROOT/'tests/fixtures/native_decisions_v214.json').read_bytes())
        for case in golden['cases']:
            with self.subTest(case=case),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(Path(tmp),mode=case['mode'],direction=case['direction'],testing=True,
                    factory={'SR1':sr_bars,'TP1':trend_bars,'BR1':breakout_bars}[case['setup']])
                paths=sorted(source.glob('event_*.bin'))
                self.assertEqual(len(paths),case['records']);self.assertEqual(result['signals'],case['signals'])
                self.assertEqual(hashlib.sha256(b''.join(p.read_bytes() for p in paths)).hexdigest(),case['native_sha256'])

    def test_outcome_changes_do_not_change_lock_features_or_membership(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows=[]
            for mode in (0,13,14):
                _,source=self.execute(Path(tmp)/str(mode),mode=mode,testing=True)
                rows.append(data.read(source)['rows'][0])
            self.assertEqual([r['quality_status'] for r in rows],['FAVORABLE','ADVERSE','TIE'])
            self.assertEqual(rows[0]['features'],rows[1]['features']);self.assertEqual(rows[1]['features'],rows[2]['features'])
            self.assertTrue(all(r['ready_at_lock'] for r in rows))

    def test_observer_matches_native_and_post_lock_cancellation_keeps_quality_cohort(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);snapshots=[]
            for mode in (0,9,18,5):
                result,source=self.execute(root/str(mode),mode=mode,testing=True);before=tree_hash(source)
                s=data.read(source);rules=summarize(source,s)
                self.assertGreaterEqual(rules['verified_rows'],2);self.assertEqual(rules['missing_observer_rows'],0)
                self.assertEqual(tree_hash(source),before)
                self.assertEqual(len(s['rows']),1);snapshots.append(s)
                self.assertEqual(s['rows'][0]['quality_status'],'FAVORABLE')
                self.assertFalse(s['rows'][0]['is_execution_trade'])
            normal,canceled=snapshots[:2]
            a,b=normal['rows'][0],canceled['rows'][0]
            self.assertTrue(a['ready_at_lock']);self.assertTrue(b['ready_at_lock'])
            self.assertEqual(a['features'],b['features']);self.assertTrue(a['execution_signal_observed'])
            self.assertFalse(b['execution_signal_observed'])

    def test_enrollment_exists_before_entry_and_label_arrives_later(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,source=self.execute(root/'native',mode=0,testing=False)
            full=data.read(source);records=read_directory(source)
            cutoff=next(r['state']['sequence'] for r in records if r['event']['kind']==3)
            prefix=root/'prefix';prefix.mkdir()
            for p in source.iterdir():
                if p.name.startswith('event_') and int(p.stem[6:])>cutoff:continue
                if p.is_file():(prefix/p.name).write_bytes(p.read_bytes())
            early=data.read(prefix);self.assertEqual(early['rows'][0]['quality_status'],'PENDING')
            self.assertEqual(early['rows'][0]['features'],full['rows'][0]['features'])
            self.assertEqual(early['rows'][0]['sample_id'],full['rows'][0]['sample_id'])
            # Observer may already be ahead of the captured immutable prefix.
            self.assertGreater(summarize(prefix,early)['verified_rows'],0)

    def test_rule_tampering_and_unsealed_tester_are_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(Path(tmp),mode=0,testing=True);s=data.read(source)
            path=next(source.glob('candidate_rules_*.csv'));rows=read_csv(path);rows[0]['tp_touch']='1' if rows[0]['tp_touch']=='0' else '0'
            write_csv(path,rows)
            with self.assertRaisesRegex(ValueError,'predicate'):summarize(source,s)
            (source/'tester_complete.csv').unlink()
            with self.assertRaises(OSError):data.read(source)

    def test_new_candidate_cli_is_readonly_and_zip_is_reviewable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,source=self.execute(root/'native',mode=9,testing=True);before=tree_hash(source)
            args=[sys.executable,str(ROOT/'tools/candidate_research.py'),'--source',str(source),'--output',str(root/'out')]
            proc=subprocess.run(args,capture_output=True,text=True,timeout=60)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertTrue((root/'out/candidate_review_v224.zip').is_file());self.assertEqual(tree_hash(source),before)
            proc=subprocess.run(args,capture_output=True,text=True,timeout=60)
            self.assertEqual(proc.returncode,0,proc.stderr);self.assertIn('UNCHANGED',proc.stdout)
