"""Data-time, payout, chronological gates and recovery contracts for V207."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from intelligence.demo_learning import (LOGIC,MODEL_COLUMNS,fnv,outcome,points,read_policy,train,weekly_bounds)


def policy(horizon=1):
    p=dict(schema=1,logic=LOGIC,config_hash=2669644079,feed_hash=fnv('FIXTURE_FEED|EURUSD|5'),
        horizon=horizon,enabled=1,learning=1)
    p['policy_hash']=fnv('DEMO1|'+ '|'.join(str(p[k]) for k in ('config_hash','feed_hash','horizon','enabled','learning')))
    return p


def row(day,index=0,win=True):
    target=1767225600+day*86400+index*1200
    return dict(setup=1,direction=1,regime=1,horizon=1,status='WIN' if win else 'LOSS',
        signed_points=20 if win else -20,entry_target=target,available_at_ms=(target+301)*1000,atr_pips=4.)


class DemoLearningTests(unittest.TestCase):
    def test_call_put_and_tie_are_point_based(self):
        self.assertEqual(outcome(1.1,1.1001,1),('WIN',10))
        self.assertEqual(outcome(1.1,1.1001,-1),('LOSS',-10))
        self.assertEqual(outcome(1.1,1.0999,-1),('WIN',10))
        self.assertEqual(outcome(1.1,1.10000000000001,1),('TIE',0))
        for v in (0,-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):points(v)

    def test_policy_fingerprint_and_account_independence(self):
        from intelligence.demo_learning import POLICY_COLUMNS
        with tempfile.TemporaryDirectory() as tmp:
            p=policy();path=Path(tmp)/'demo_policy.csv'
            with path.open('w',newline='') as s:w=csv.DictWriter(s,fieldnames=POLICY_COLUMNS);w.writeheader();w.writerow(p)
            self.assertEqual(read_policy(tmp),p)
            p['horizon']=2
            with path.open('w',newline='') as s:w=csv.DictWriter(s,fieldnames=POLICY_COLUMNS);w.writeheader();w.writerow(p)
            with self.assertRaisesRegex(ValueError,'fingerprint'):read_policy(tmp)

    def test_small_sample_updates_bayes_but_never_applies_filter(self):
        data=[row(d,win=d%2==0) for d in range(10)]
        snap=dict(policy=policy(),asof=data[-1]['entry_target']+1000,references=data)
        models,report=train(snap)
        self.assertEqual(len(models),1);self.assertEqual(models[0]['decision'],0)
        self.assertAlmostEqual(report['contexts'][0]['candidate_probability'],.5)
        self.assertFalse(models[0]['validated']);self.assertFalse(report['production_promoted'])

    def test_future_unclosed_or_unavailable_labels_cannot_train(self):
        data=[row(d) for d in range(5)];asof=data[-1]['entry_target']+1000
        before=train(dict(policy=policy(),asof=asof,references=data))
        future=dict(row(6),available_at_ms=(asof+1)*1000)
        invalid=dict(row(2),status='UNAVAILABLE',available_at_ms=None)
        after=train(dict(policy=policy(),asof=asof,references=data+[future,invalid]))
        self.assertEqual(before,after)

    def test_ties_do_not_inflate_win_probability(self):
        data=[dict(row(d),status='TIE',signed_points=0) for d in range(10)]
        models,report=train(dict(policy=policy(),asof=data[-1]['entry_target']+1000,references=data))
        self.assertEqual(report['contexts'][0]['candidate_probability'],.5)
        self.assertEqual(models[0]['n_train'],0);self.assertEqual(models[0]['decision'],0)

    def test_chronological_forward_reversal_rejects_old_allow_action(self):
        data=[row(d,i,win=d<120 or i==0) for d in range(180) for i in range(4)]
        models,r=train(dict(policy=policy(),asof=data[-1]['entry_target']+1000,references=data))
        ctx=r['contexts'][0]
        self.assertEqual(ctx['training_frozen_action'],1)
        self.assertEqual(models[0]['decision'],0)
        self.assertIn('forward_allow_not_confirmed',ctx['failures'])

    def test_persistent_poor_context_can_only_block_after_forward_gate(self):
        data=[row(d,i,win=i==0) for d in range(180) for i in range(4)]
        models,r=train(dict(policy=policy(),asof=data[-1]['entry_target']+1000,references=data))
        self.assertEqual(r['contexts'][0]['training_frozen_action'],-1)
        self.assertEqual(models[0]['decision'],-1);self.assertEqual(models[0]['validated'],1)

    def test_consistent_strong_context_can_pass_demo_filter_gate(self):
        data=[row(d,i,win=i<3) for d in range(180) for i in range(4)]
        models,r=train(dict(policy=policy(),asof=data[-1]['entry_target']+1000,references=data))
        self.assertEqual(models[0]['decision'],1);self.assertEqual(models[0]['validated'],1)
        self.assertFalse(r['production_promoted'])

    def test_only_one_week_of_many_samples_cannot_validate(self):
        data=[row(d,i,win=True) for d in range(5) for i in range(200)]
        models,r=train(dict(policy=policy(),asof=max(x['entry_target'] for x in data)+1000,references=data))
        self.assertEqual(models[0]['decision'],0)
        self.assertIn('forward_samples_or_weeks',r['contexts'][0]['failures'])


if __name__=='__main__':unittest.main()
