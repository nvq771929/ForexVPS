"""Synthetic correctness only. These fixtures establish no market profitability."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import torch

from intelligence import prepared_history as cache
from intelligence import research_model as rm
from intelligence import tcn_model as tcn
from intelligence.deep_learning import train
from intelligence.sequence_data import build, arrays, LENGTH
from intelligence.t1_features import CONTRACT
from intelligence.t1_corrected import NAMES
from intelligence.research_features import NAMES as ANCHOR_NAMES, CONTRACT as ANCHOR_CONTRACT
from intelligence.history_learning import read_artifact
from tests.fixtures import START
from tests.test_demo_learning import policy

ROOT = Path(__file__).resolve().parents[1]


def sequence_fixture(days=60, per_day=64):
    rng = random.Random(212)
    base, t1 = [], []
    for day in range(days):
        for i in range(per_day):
            start = START + day * 86400 + i * 300
            target = start + 300
            x = [rng.uniform(-1, 1) for _ in ANCHOR_NAMES]
            x[ANCHOR_NAMES.index('support_available')]=float(i%2)
            x[ANCHOR_NAMES.index('resistance_available')]=float((i//2)%2)
            move = 10 if x[0] > 0 else -10
            if i % 53 == 0:
                move = 0
            row = dict(source='BACKTEST_MT4_PRICE_RESEARCH', cohort=ANCHOR_CONTRACT, is_execution_trade=False,
                sample_id=f'{day}.{i}', analysis_start=start, entry_target=target, expiry_target=target+300, horizon=1,
                locked_at_ms=(start+268)*1000, feature_asof_ms=start*1000, entry_observed_ms=target*1000,
                entry_bid=1.1, exit_observed_ms=(target+300)*1000, exit_bid=1.1+move/100000,
                available_at_ms=(target+301)*1000, status='UP' if move>0 else 'DOWN' if move<0 else 'TIE',
                signed_points=move, features=x, regime=i%8, candidate_setup=(i%3+1) if i%4 else 0)
            base.append(row)
            extra = [rng.uniform(-1, 1) for _ in range(20)]
            new = dict(row, features=x+extra, cohort=CONTRACT, anchor_asof_ms=start*1000,
                       feature_asof_ms=row['locked_at_ms'])
            for name, value in [('lock_elapsed_fraction',268/300),('last_observed_fraction',268/300),('quote_age_seconds',0.)]:
                new['features'][NAMES.index(name)] = value
            direction=(1 if i%2 else -1) if i%4 else 0
            for name,value in [('candidate_present',float(direction!=0)),('candidate_direction',float(direction)),
                ('candidate_sr1',float(row['candidate_setup']==1)),('candidate_tp1',float(row['candidate_setup']==2)),('candidate_br1',float(row['candidate_setup']==3))]:
                new['features'][NAMES.index(name)]=value
            t1.append(new)
    return dict(policy=policy(), origin='BACKTEST_MT4', asof=base[-1]['expiry_target']+1000,
                research=base, research_t1=t1, references=[], papers=[], funnel={}, records=len(base), execution_traces=[])


class SequenceDataTests(unittest.TestCase):
    def test_exact_32_past_anchors_no_weekend_fill_no_future_features(self):
        s = sequence_fixture(days=2)
        data = build(s)
        self.assertEqual(len(data['rows']), 2*(64-31))
        row = data['rows'][0]
        sequence, context, _ = arrays(data, [row])
        self.assertEqual(sequence.shape, (1, 32, 29))
        self.assertEqual(context.shape, (1, 50))
        self.assertEqual(row['sequence_first_asof_ms'], START*1000)
        self.assertLessEqual(row['sequence_last_asof_ms'], row['locked_at_ms'])
        changed = copy.deepcopy(s)
        changed['research'][-1]['features'][0] = 999.
        changed['research_t1'][-1]['features'][0] = 999.
        future = build(changed)
        np.testing.assert_array_equal(arrays(data, [row])[0], arrays(future, [future['rows'][0]])[0])
        changed = copy.deepcopy(s)
        changed['research'][10]['feature_asof_ms'] += 1000
        with self.assertRaisesRegex(ValueError, 'sequence input'):
            build(changed)
        changed = copy.deepcopy(s)
        changed['research_t1'][35]['feature_asof_ms'] += 300000
        with self.assertRaisesRegex(ValueError, 'clock'):
            build(changed)

    def test_missing_anchor_excludes_cross_gap_sequences_and_old_cache_never_invents_t1(self):
        s = sequence_fixture(days=2)
        s['research'].pop(32)
        s['research_t1'].pop(32)
        self.assertLess(len(build(s)['rows']), 66)
        s.pop('research_t1')
        with self.assertRaisesRegex(ValueError, r'T\+1 cache'):
            build(s)

    def test_previous_outcomes_are_not_sequence_features_and_duplicate_time_rejected(self):
        s = sequence_fixture(days=2)
        before = build(s)
        for r in s['research']:
            r['status'] = 'UNAVAILABLE'
            r['signed_points'] = None
        after = build(s)
        np.testing.assert_array_equal(arrays(before, before['rows'])[0], arrays(after, after['rows'])[0])
        s['research'].append(copy.deepcopy(s['research'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate anchor'):
            build(s)

    def test_temporal_split_has_embargo_and_outcome_availability_before_next_lock(self):
        data = build(sequence_fixture())
        train_rows, calibration, test = rm.split(data['rows'])
        self.assertTrue(train_rows and calibration and test)
        self.assertLess(max(r['available_at_ms'] for r in train_rows), min(r['locked_at_ms'] for r in calibration))
        self.assertLess(max(r['available_at_ms'] for r in calibration), min(r['locked_at_ms'] for r in test))
        self.assertGreaterEqual(min(r['entry_target'] for r in test)-max(r['entry_target'] for r in calibration),86400)


class TCNTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(212)
        cls.seq = rng.normal(size=(128,LENGTH,len(ANCHOR_NAMES))).astype(np.float32)
        cls.context = np.zeros((128,len(NAMES)),dtype=np.float32)
        cls.y = (cls.seq[:,-1,0]>0).astype(np.float32)
        cls.model = tcn.fit(cls.seq,cls.context,cls.y)

    def test_causal_convolution_cannot_read_later_steps(self):
        tcn.seed()
        block = tcn.CausalBlock(29,16,4).eval()
        x=torch.randn(2,29,32)
        changed=x.clone();changed[:,:,20:]+=1000
        with torch.inference_mode():
            torch.testing.assert_close(block(x)[:,:,:20],block(changed)[:,:,:20],rtol=0,atol=0)

    def test_training_normalization_is_train_only_weights_learn_and_json_scores_match(self):
        model = self.model
        expected=self.seq.mean(axis=(0,1),dtype=np.float64);expected[tcn.binary_indices(ANCHOR_NAMES)]=0.
        np.testing.assert_allclose(model['normalization']['sequence_mean'],expected)
        np.testing.assert_array_equal(model['normalization']['context_mean'],np.zeros(50))
        self.assertGreater(len(model['weights']),10)
        scores=tcn.score(model,self.seq,self.context)
        self.assertGreater(float(scores.std()),.01)
        restored=json.loads(json.dumps(model))
        np.testing.assert_array_equal(scores,tcn.score(restored,self.seq,self.context))
        self.assertTrue(tcn.domain(model,self.seq,self.context).all())
        changed=self.context.copy();changed[:,0]=1000
        self.assertFalse(tcn.domain(model,self.seq,changed).any())
        tcn.seed();initial=tcn.TemporalClassifier()
        self.assertFalse(np.array_equal(initial.state_dict()['head.2.weight'].numpy(),np.asarray(model['weights']['head.2.weight'])))

    def test_tampered_shapes_nonfinite_and_normalization_fail_closed(self):
        for mode in ('shape','nan','scale','architecture'):
            model=copy.deepcopy(self.model)
            if mode=='shape':model['weights']['head.2.bias']=[0.,1.]
            elif mode=='nan':model['weights']['head.2.bias']=[float('nan')]
            elif mode=='scale':model['normalization']['context_scale'][0]=0.
            else:model['architecture']='LOOKAHEAD'
            with self.subTest(mode=mode),self.assertRaises(ValueError):tcn.restore(model)


class DeepWorkflowTests(unittest.TestCase):
    def test_cli_full_experiment_exports_comparable_offline_models_without_touching_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'original'/cache.NAME;source.parent.mkdir()
            cache.save(source,sequence_fixture(),'a'*64)
            before=hashlib.sha256(source.read_bytes()).hexdigest()
            out=root/'output'
            p=subprocess.run([sys.executable,str(ROOT/'tools/train_deep_history.py'),'--prepared',str(source),'--output',str(out)],capture_output=True,text=True,timeout=180)
            self.assertEqual(p.returncode,0,p.stderr+'\n'+p.stdout[-3000:])
            self.assertIn('[FINISHED]',p.stdout)
            report=json.loads((out/'deep_research_report.json').read_text())
            plan=json.loads((out/'experiment_plan.json').read_text())
            selection=json.loads((out/'inner_selection.json').read_text())
            candidate=json.loads((out/'deep_model_candidate.json').read_text())
            receipt=json.loads((out/'input_receipt.json').read_text())
            migration=json.loads((out/'feature_migration.json').read_text())
            self.assertEqual(migration['target_contract'],'ANCHOR_T1_UP_V2')
            self.assertEqual(migration['target_feature_count'],50)
            self.assertGreater(migration['corrected_reward_rows'],0)
            inner_tcn=json.loads((out/'models/inner_tcn.json').read_text())
            outer_tcn=json.loads((out/'models/outer_tcn.json').read_text())
            epoch=selection['tcn_selected_epoch']
            self.assertEqual(inner_tcn['model']['training']['selected_epoch'],epoch)
            self.assertEqual(outer_tcn['model']['training']['epoch_budget'],epoch)
            self.assertEqual(outer_tcn['model']['training']['epochs_run'],epoch)
            self.assertEqual(outer_tcn['model']['training']['validation_samples'],0)
            self.assertEqual(outer_tcn['model']['training']['selection_scope'],'FIXED_EPOCH_REFIT')
            self.assertLess(inner_tcn['training']['last_target'],plan['splits']['inner_selection']['first_target'])
            self.assertTrue((out/'runtime_fingerprint.json').is_file())
            self.assertTrue((out/'learning_curves.csv').is_file())
            self.assertTrue((out/'candidate_quality_report.json').is_file())
            import zipfile
            with zipfile.ZipFile(out/'training_review_v224.zip') as archive:
                self.assertIsNone(archive.testzip())
                self.assertIn('feature_migration.json',archive.namelist())
                self.assertIn('candidate_quality_report.json',archive.namelist())
                self.assertFalse(any(n.startswith('models/') or n.endswith('.gz') for n in archive.namelist()))
            self.assertEqual(receipt['event_read_passes'],0)
            self.assertEqual(receipt['prepared_file_sha256'],before)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)
            self.assertEqual(plan['dataset']['sequence_length'],32)
            self.assertEqual(set(report['comparison']),{'logistic','hgb','tcn'})
            self.assertEqual(report['selected_algorithm'],min(selection['scores'],key=selection['scores'].get))
            sample_counts={v['offline']['samples'] for v in report['comparison'].values() if 'offline' in v}
            self.assertEqual(sample_counts,{plan['splits']['test']['samples']})
            self.assertFalse(candidate['eligible_for_live_filter']);self.assertFalse(candidate['eligible_for_legacy_import'])
            self.assertTrue(candidate['independent_confirmation_required'])
            self.assertEqual(candidate['validation_scope'],'HISTORICAL_EXPLORATION')
            payload=candidate.pop('payload_sha256')
            self.assertEqual(payload,hashlib.sha256(rm.canonical(candidate)).hexdigest())
            with self.assertRaisesRegex(ValueError,'Research models cannot import'):
                read_artifact(out/'deep_model_candidate.json')
            with (out/'deep_predictions.csv').open() as f:
                predictions=list(csv.DictReader(f))
            self.assertTrue(predictions)
            self.assertTrue(all(r['is_execution_trade']=='False' and r['independent_validation']=='False' for r in predictions))
            p=subprocess.run([sys.executable,str(ROOT/'tools/diagnose_execution.py'),'--prepared',str(source),'--output',str(root/'review')],capture_output=True,text=True,timeout=30)
            self.assertEqual(p.returncode,0,p.stderr)

    def test_insufficient_sequences_finish_explicitly_without_a_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'out'
            report=train(sequence_fixture(days=2),'a'*64,out)
            self.assertEqual(report['status'],'DEEP_NOT_TRAINED')
            self.assertFalse((out/'deep_model_candidate.json').exists())
            self.assertTrue((out/'experiment_plan.json').exists())
            with self.assertRaisesRegex(ValueError,'fresh'):
                train(sequence_fixture(days=2),'a'*64,out)


if __name__=='__main__':unittest.main()
