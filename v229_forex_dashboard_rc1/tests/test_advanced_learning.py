"""Synthetic data tests of chronology and activation; no market-performance claims."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from intelligence.advanced_learning import (fit,split,probability,forward,update,evaluate,validate)
from intelligence.signal_features import NAMES
from tests.test_demo_learning import policy

START=1767225600


def rows(days=360,start=START):
    result=[]
    for day in range(days):
        for i in range(6):
            win=i<3;target=start+day*86400+i*1200
            x=[0.]*len(NAMES);x[0]=4.;x[5]=2. if win else -2.;x[15]=1.;x[18]=1.
            result.append(dict(source='MT4_SIMULATED',signal_id=f'{target}',setup=1,direction=1,regime=1,horizon=1,
                status='WIN' if win else 'LOSS',signed_points=20 if win else -20,
                entry_target=target,locked_at_ms=(target-32)*1000,available_at_ms=(target+301)*1000,
                atr_pips=4.,features=x,model_id=0,locked_probability=.5))
    return result


def snapshot(data,asof=None):
    return dict(policy=policy(),asof=asof or max(r['entry_target'] for r in data)+1000,references=data)


class AdvancedLearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=rows();cls.asof=cls.data[-1]['entry_target']+1000
        cls.model,cls.info=fit(cls.data,cls.asof)

    def test_real_regularized_fit_and_calibration_can_pass_synthetic_offline_gate(self):
        m=self.model;self.assertIsNotNone(m);validate(m)
        self.assertEqual(m['offline_failures'],[])
        self.assertEqual(m['phase'],'OBSERVE')
        self.assertLess(m['calibration_cutoff'],m['test_lock_start'])
        self.assertGreater(probability(m,self.data[0]['features']),.8)
        self.assertLess(probability(m,self.data[5]['features']),.2)

    def test_small_sample_never_creates_a_fitted_model(self):
        model,info=fit(rows(10),self.asof)
        self.assertIsNone(model);self.assertEqual(info['status'],'COLLECTING')

    def test_scaler_coefficients_and_calibration_do_not_fit_test_future(self):
        altered=copy.deepcopy(self.data)
        for r in altered[-432:]:
            r['features'][5]*=7;r['status']='LOSS' if r['status']=='WIN' else 'WIN'
        changed,_=fit(altered,self.asof)
        for key in ('weight','mean','scale','intercept'):
            self.assertEqual(changed[key],self.model[key])
        self.assertNotEqual(changed['offline_failures'],[])

    def test_purge_removes_prior_labels_available_after_next_lock(self):
        data=rows();train,cal,test=split(data)
        boundary=min(r['locked_at_ms'] for r in cal)
        train_target=train[-1]['entry_target']
        for r in data:
            if r['entry_target']==train_target:r['available_at_ms']=boundary+1
        tr,_,_=split(data)
        self.assertNotIn(train_target,[r['entry_target'] for r in tr])

    def test_backward_predictions_cannot_be_claimed_as_forward_evidence(self):
        self.assertEqual(forward(self.model,self.data),[])
        fake=copy.deepcopy(self.data[0]);fake['model_id']=self.model['model_id']
        fake['locked_probability']=probability(self.model,fake['features'])
        self.assertEqual(forward(self.model,[fake]),[])

    def test_native_recorded_forecast_probability_must_match_frozen_model(self):
        data=self.future()
        data[0]['locked_probability']+=.05
        with self.assertRaisesRegex(ValueError,'mismatch'):forward(self.model,data)

    def future(self):
        start=(self.asof//86400+1)*86400
        data=rows(120,start)
        for r in data:
            r['model_id']=self.model['model_id'];r['locked_probability']=probability(self.model,r['features'])
        return data

    def test_offline_success_never_activates_without_recorded_forward_forecasts(self):
        with tempfile.TemporaryDirectory() as tmp:
            report=update(tmp,snapshot(self.data))
            self.assertEqual(report['status'],'OBSERVE');self.assertEqual(report['native_forecasts'],0)
            self.assertFalse(report['production_promoted'])
            text=(Path(tmp)/'advanced_model_v207.csv').read_text()
            self.assertTrue(text.startswith('schema,source,logic,'))

    def test_candidate_is_frozen_and_active_only_after_forward_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            update(tmp,snapshot(self.data))
            report=update(tmp,snapshot(self.data+self.future()))
            self.assertEqual(report['status'],'ACTIVE');self.assertEqual(report['model_id'],self.model['model_id'])
            self.assertEqual(report['forward_failures'],[])
            self.assertFalse(report['production_promoted'])

    def test_wrong_model_id_does_not_count_as_native_forward_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            update(tmp,snapshot(self.data));data=self.future()
            for r in data:r['model_id']+=1
            report=update(tmp,snapshot(self.data+data))
            self.assertEqual(report['status'],'OBSERVE');self.assertEqual(report['native_forecasts'],0)

    def test_deterioration_suspends_filter_without_rewriting_closed_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            update(tmp,snapshot(self.data));future=self.future()
            activated=update(tmp,snapshot(self.data+future));self.assertEqual(activated['status'],'ACTIVE')
            bad=rows(40,(future[-1]['entry_target']//86400+1)*86400)
            for r in bad:
                r['status']='LOSS' if r['status']=='WIN' else 'WIN';r['signed_points']*=-1
                r['model_id']=self.model['model_id'];r['locked_probability']=probability(self.model,r['features'])
            report=update(tmp,snapshot(self.data+future+bad))
            self.assertEqual(report['status'],'SUSPENDED')
            report=update(tmp,snapshot(self.data+future+bad,bad[-1]['entry_target']+9*86400))
            self.assertEqual(report['status'],'OBSERVE')
            self.assertNotEqual(report['model_id'],self.model['model_id'])
            self.assertTrue((Path(tmp)/f"advanced_archive_{self.model['model_id']}.json").is_file())

    def test_missing_state_identity_change_and_time_rollback_are_rejected(self):
        for mode in ('missing','identity','rollback','truncated'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                update(tmp,snapshot(self.data));path=Path(tmp)/'advanced_state_v207.json'
                if mode=='missing':path.unlink()
                else:
                    state=json.loads(path.read_text())
                    if mode=='identity':state['identity']['feed_hash']+=1
                    elif mode=='rollback':state['last_asof']+=100
                    else:del state['model']['weight']
                    path.write_text(json.dumps(state))
                with self.assertRaises(ValueError):update(tmp,snapshot(self.data))

    def test_unavailable_ties_and_future_labels_do_not_enter_logistic_fit(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=rows(10)
            for r in data:r['status']='UNAVAILABLE';r['available_at_ms']=None
            report=update(tmp,snapshot(data,self.asof))
            self.assertEqual(report['status'],'COLLECTING')
            self.assertFalse((Path(tmp)/'advanced_model_v207.csv').exists())


if __name__=='__main__':unittest.main()
