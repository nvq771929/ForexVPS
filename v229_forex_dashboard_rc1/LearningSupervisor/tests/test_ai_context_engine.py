import copy,math,random,unittest
from assistant.context.engine import Aggregate,Frame,ContextObserver,zones

def bar(i,close=1.1):return dict(time=i*300,open=close-.00002,high=close+.00010,low=close-.00010,close=close,ticks=10)
def synthetic(n=2200):return [bar(i,1.1+i*.000001+math.sin(i/50)*.0001) for i in range(n)]
def run(bars):
    x=ContextObserver();return [x.update(b) for b in bars]

class AggregateTests(unittest.TestCase):
    def test_no_h1_until_all_twelve_closed(self):
        a=Aggregate(3600)
        for i in range(11):self.assertIsNone(a.push(bar(i)))
        z=a.push(bar(11));self.assertEqual(z['time'],0);self.assertEqual(z['ticks'],120)
    def test_missing_constituent_invalidates_h1(self):
        a=Aggregate(3600);result=None
        for i in range(12):
            if i!=5:result=a.push(bar(i))
        self.assertIsNone(result)
    def test_partial_first_bucket_not_backfilled(self):
        a=Aggregate(900);self.assertIsNone(a.push(bar(1)));self.assertIsNone(a.push(bar(2)))
    def test_persistent_ema_matches_independent_recurrence(self):
        f=Frame(300);bb=synthetic(170)
        for b in bb:f.push(b)
        val=sum(v['close'] for v in bb[:50])/50
        for b in bb[50:]:val=(2/51)*b['close']+(49/51)*val
        self.assertAlmostEqual(f.e50,val,places=14);self.assertEqual(f.count,170)
    def test_frame_stale_and_warmup_unknown(self):
        f=Frame(900)
        for i in range(149):f.push(dict(bar(i*3),time=i*900))
        self.assertIsNone(f.facts(149*900));f.push(dict(bar(149*3),time=149*900));self.assertIsNotNone(f.facts(150*900));self.assertIsNone(f.facts(151*900))

class CausalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bars=synthetic();cls.snapshots=run(cls.bars)
    def test_warmup_requires_150_actual_h1_bars(self):
        self.assertTrue(all(not x['ready'] for x in self.snapshots[:1799]));self.assertTrue(self.snapshots[1799]['ready'])
    def test_prefix_invariance_when_future_prices_change(self):
        changed=copy.deepcopy(self.bars)
        for b in changed[2050:]:
            for k in ('open','high','low','close'):b[k]*=1.3
        actual=run(changed);self.assertEqual(self.snapshots[:2050],actual[:2050])
    def test_higher_timeframe_timestamps_never_exceed_asof(self):
        for s in self.snapshots:
            for k in ('m15','h1'):
                if s[k] is not None:self.assertLessEqual(s[k]['close_ms'],s['asof_ms'])
    def test_age_starts_at_confirmation_not_first_candidate(self):
        first=next(x for x in self.snapshots if x['direction'] in ('UP','DOWN'))
        self.assertEqual(first['observed_age_minutes'],0);self.assertEqual(first['detected_start_ms'],first['asof_ms'])
    def test_same_m15_not_counted_per_m5(self):
        x=ContextObserver();x._confirm('UP',1000);self.assertEqual(x.pending_count,1);x._confirm('UP',901000);self.assertEqual(x.direction,'UP')
        # Actual replay sees only one _confirm call at each closed M15 boundary.
        for a,b in zip(self.snapshots,self.snapshots[1:]):
            if a['ready'] and b['ready'] and a['m15']['close_ms']==b['m15']['close_ms']:
                self.assertEqual(a['pending_m15_count'],b['pending_m15_count'])
    def test_one_conflict_retains_direction_two_clear_it(self):
        x=ContextObserver();x._confirm('UP',0);x._confirm('UP',900000);x._confirm('UNCERTAIN',1800000);self.assertEqual(x.direction,'UP');x._confirm('UNCERTAIN',2700000);self.assertEqual(x.direction,'UNCERTAIN')
    def test_gap_clears_age_and_does_not_fill_missing_bar(self):
        x=ContextObserver()
        for b in self.bars[:2000]:x.update(b)
        s=x.update(self.bars[2012]);self.assertTrue(s['data_gap']);self.assertIsNone(s['observed_age_minutes'])
    def test_bad_or_duplicate_bar_rejected(self):
        x=ContextObserver();b=bar(0);x.update(b)
        with self.assertRaises(ValueError):x.update(b)
        y=bar(1);y['low']=2
        with self.assertRaises(ValueError):x.update(y)
    def test_no_effect_or_supervised_probability_in_engine(self):
        for r in self.snapshots:self.assertFalse(r['EA_effects_allowed']);self.assertFalse(r['historical_probabilities_qualified'])
    def test_zones_do_not_use_unconfirmed_pivot_or_gap(self):
        bb=synthetic(64);bb[63]['high']=2;z=zones(bb,.001)
        for key in ('support','resistance'):
            if z[key] is not None:self.assertLessEqual(z[key]['known_at_ms'],(bb[-1]['time']+300)*1000)
        bb[20]['time']-=300;self.assertFalse(zones(bb,.001)['known'])


if __name__=="__main__":unittest.main()
