"""Regression and temporal correctness; synthetic data is not market evidence."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np
import torch
from torch.nn import functional as F

from intelligence import t1_corrected as corrected
from intelligence.t1_features import NAMES as OLD_NAMES
from intelligence import tcn_model as tcn
from intelligence.sequence_data import build
from intelligence import research_model as rm
from intelligence.candidate_quality import train as quality_train
from intelligence.prepared_history import save,load,NAME
from intelligence.history_learning import train_prepared,read_artifact
from intelligence.learning_diagnostics import read_model,diagnose
from tests.test_deep_learning import sequence_fixture


class CorrectedFeatureTests(unittest.TestCase):
    def vector(self,direction,support,resistance,reward):
        v=[0.]*len(OLD_NAMES)
        for n,x in [('candidate_direction',direction),('candidate_present',float(direction!=0)),
                    ('support_available',support),('resistance_available',resistance),('reward_distance_atr',reward)]:
            v[OLD_NAMES.index(n)]=x
        return v

    def test_call_and_put_without_target_have_zero_distance_and_explicit_unavailability(self):
        for d,s,r,reward in [(1,1,0,-3666.),(-1,0,1,3666.)]:
            with self.subTest(direction=d):
                v=self.vector(d,s,r,reward);before=v.copy();new=corrected.correct_features(v)
                self.assertEqual(len(new),50);self.assertEqual(new[-1],0.)
                self.assertEqual(new[OLD_NAMES.index('reward_distance_atr')],0.)
                self.assertEqual(v,before)

    def test_available_target_and_genuine_far_target_are_retained_not_threshold_clipped(self):
        for d,value in [(1,2.5),(-1,3.2),(1,5000.)]:
            v=self.vector(d,1,1,value);new=corrected.correct_features(v)
            self.assertEqual(new[-1],1.)
            self.assertEqual(new[OLD_NAMES.index('reward_distance_atr')],value)
        new=corrected.correct_features(self.vector(0,1,1,100.))
        self.assertEqual(new[-1],0.);self.assertEqual(new[44],0.)

    def test_invalid_availability_direction_and_nonfinite_fail_closed(self):
        for mode in ('flag','direction','present','nan'):
            v=self.vector(1,1,1,2.)
            if mode=='flag':v[OLD_NAMES.index('resistance_available')]=.5
            elif mode=='direction':v[OLD_NAMES.index('candidate_direction')]=.7
            elif mode=='present':v[OLD_NAMES.index('candidate_present')]=0.
            else:v[0]=float('nan')
            with self.subTest(mode=mode),self.assertRaises(ValueError):corrected.correct_features(v)

    def test_migration_is_immutable_and_does_not_use_future_outcomes_or_cancellation(self):
        s=sequence_fixture(days=2);before=copy.deepcopy(s)
        result=corrected.with_corrected(s)
        self.assertEqual(s,before);self.assertTrue(result['t1_v2_migration']['corrected_reward_rows'])
        self.assertEqual(result[corrected.KEY][0]['cohort'],corrected.CONTRACT)
        changed=copy.deepcopy(s)
        for r in changed['research_t1']:
            r.update(canceled_at_entry=True,entry_reason='ANY_FUTURE_REASON',status='UNAVAILABLE',exit_bid=None)
        other=corrected.with_corrected(changed)
        self.assertEqual([r['features'] for r in result[corrected.KEY]],[r['features'] for r in other[corrected.KEY]])
        self.assertEqual(result['t1_v2_migration']['derived_feature_sha256'],other['t1_v2_migration']['derived_feature_sha256'])


class EarlyStoppingTests(unittest.TestCase):
    def test_patience_restores_best_checkpoint_and_never_fits_validation_statistics(self):
        rng=np.random.default_rng(213)
        seq=rng.normal(size=(16,32,29)).astype(np.float32)
        ctx=np.zeros((16,50),np.float32);labels=np.asarray([0.,1.]*8,dtype=np.float32)
        vseq=seq+100.;vctx=ctx+100.
        original=F.binary_cross_entropy_with_logits
        validation_losses=iter([1.,.9,.90005,.9001,.9002,.91,.92])
        def controlled(logits,target,*args,**kwargs):
            if not logits.requires_grad:return torch.tensor(next(validation_losses))
            return original(logits,target,*args,**kwargs)
        with patch('intelligence.tcn_model.F.binary_cross_entropy_with_logits',side_effect=controlled):
            model=tcn.fit(seq,ctx,labels,validation=(vseq,vctx,labels))
        info=model['training']
        self.assertEqual(info['epochs_run'],5);self.assertEqual(info['selected_epoch'],2);self.assertTrue(info['stopped_early'])
        self.assertEqual(model['weights'],model['checkpoints']['best'])
        self.assertNotEqual(model['weights'],model['checkpoints']['final'])
        self.assertEqual(model['normalization']['context_mean'],[0.]*50)
        self.assertLess(max(abs(v) for v in model['normalization']['sequence_mean']),1.)
        restored=tcn.restore(json.loads(json.dumps(model)));self.assertIsNotNone(restored)

    def test_fixed_outer_refit_has_no_validation_and_exact_selected_epoch_budget(self):
        rng=np.random.default_rng(3);seq=rng.normal(size=(16,32,29)).astype(np.float32)
        ctx=np.zeros((16,50),np.float32);labels=np.asarray([0.,1.]*8,dtype=np.float32)
        m=tcn.fit(seq,ctx,labels,epochs=2)
        self.assertEqual(m['training']['epochs_run'],2)
        self.assertEqual(m['training']['validation_samples'],0)
        self.assertEqual(m['training']['selection_scope'],'FIXED_EPOCH_REFIT')
        self.assertTrue(all(r['validation_loss'] is None for r in m['training']['curves']))

    def test_binary_features_are_not_centered_and_numeric_outliers_are_bounded(self):
        seq=np.zeros((4,32,29),np.float32);ctx=np.zeros((4,50),np.float32)
        binary=corrected.NAMES.index('candidate_present');ctx[-1,binary]=1.
        n=tcn.normalization(seq,ctx)
        self.assertEqual(n['context_mean'][binary],0.);self.assertEqual(n['context_scale'][binary],1.)
        x=ctx.copy();x[:,0]=1e5
        z=tcn.transform(x,n,'context')
        self.assertTrue(np.isfinite(z).all());self.assertLessEqual(float(np.abs(z).max()),6.)
        self.assertEqual(z[-1,binary],1.)


class V213WorkflowTests(unittest.TestCase):
    def test_history_pipeline_trains_corrected_contract_but_keeps_cache_legacy_and_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'input'/NAME;source.parent.mkdir();s=sequence_fixture()
            save(source,s,'a'*64);before=hashlib.sha256(source.read_bytes()).hexdigest()
            train_prepared(source,root/'output')
            a=read_model(root/'output/t1_research_model_candidate.json')
            self.assertEqual(a['feature_contract'],corrected.CONTRACT);self.assertEqual(len(a['feature_names']),50)
            loaded,_=load(root/'output'/NAME)
            self.assertNotIn(corrected.KEY,loaded);self.assertEqual(loaded['research_t1'][0]['cohort'],'ANCHOR_T1_UP_V1')
            diag,_,_=diagnose(loaded,a,'a'*64)
            self.assertEqual(diag['feature_contract'],corrected.CONTRACT)
            self.assertEqual(before,hashlib.sha256(source.read_bytes()).hexdigest())
            with self.assertRaisesRegex(ValueError,'Research models cannot import'):read_artifact(root/'output/t1_research_model_candidate.json')

    def test_candidate_scorer_uses_prelock_presence_and_train_only_groups(self):
        s=sequence_fixture();data=build(s);tr,ca,te=rm.split(data['rows'])
        splits=dict(train=tr,calibration=ca,test=te)
        report,pred,artifact=quality_train(data['all_corrected_rows'],splits,'a'*64)
        changed=copy.deepcopy(data['all_corrected_rows']);test_ids={r['sample_id'] for r in te}
        for r in changed:
            r.update(entry_reason='FUTURE_CANCEL',canceled_at_entry=True)
            if r['sample_id'] in test_ids:
                r['signed_points']=-r['signed_points']
                r['status']='DOWN' if r['status']=='UP' else 'UP' if r['status']=='DOWN' else 'TIE'
        other,other_pred,other_artifact=quality_train(changed,splits,'a'*64)
        self.assertEqual(artifact,other_artifact)
        self.assertEqual([r['p_win'] for r in pred],[r['p_win'] for r in other_pred])
        self.assertEqual(report['splits']['test']['samples'],other['splits']['test']['samples'])
        self.assertFalse(report['model_import_allowed']);self.assertFalse(artifact['eligible_for_live_filter'])
        self.assertTrue(all(not r['is_execution_trade'] for r in pred))

    def test_candidate_report_explicitly_refuses_sparse_test_qualification(self):
        data=build(sequence_fixture());tr,ca,te=rm.split(data['rows'])
        report,_,_=quality_train(data['all_corrected_rows'],dict(train=tr,calibration=ca,test=te[-10:]),'a'*64)
        self.assertIn('test_samples',report['failures'])
        self.assertEqual(report['status'],'CANDIDATE_RESEARCH_NOT_QUALIFIED')


if __name__=='__main__':unittest.main()
