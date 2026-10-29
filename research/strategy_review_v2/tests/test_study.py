from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import study
from study import v1,PriceBook,bracket,trajectory,one_position,paired,stats,atr_context

def signal(t=0,d=1,atr=.0004):return v1.Signal('test',t,t,d,atr)
def flat(n=25):return [v1.Bar(i*300,1.1,1.1001,1.0999,1.1) for i in range(n)]
def labels(bars,s=None,hold=60,path='stop_first',spread=0):return bracket(PriceBook(bars),s or signal(),hold,path,spread)

class ExitContracts(unittest.TestCase):
    def test_holds_are_limits_not_fixed_duration(self):
        b=[v1.Bar(0,1.1,1.1013,1.0999,1.1001)]+flat()[1:]
        for hold in [30,60,120]:
            r=labels(b,hold=hold);self.assertEqual(r['why'],'TAKE');self.assertEqual(r['exit'],300);self.assertEqual(r['exit_bar'],0)
    def test_hold_deadlines_require_exact_observed_open(self):
        for hold in [30,60,120]:
            r=labels(flat(),hold=hold);self.assertEqual(r['why'],'MAX_HOLD');self.assertEqual(r['exit'],hold*60)
            r=labels(flat(hold//5),hold=hold);self.assertEqual(r['status'],'UNAVAILABLE_END');self.assertIsNone(r['gross_R'])
    def test_deadline_bar_high_low_cannot_affect_timeout(self):
        b=flat();b[6]=v1.Bar(1800,1.1002,1.2,1.,1.1)
        r=labels(b,hold=30);self.assertEqual(r['why'],'MAX_HOLD');self.assertAlmostEqual(r['gross_R'],1/3)
    def test_adverse_open_stop_precedes_timeout(self):
        b=flat();b[6]=v1.Bar(1800,1.099,1.0992,1.0988,1.099)
        r=labels(b,hold=30);self.assertEqual(r['why'],'OPEN_STOP_GAP');self.assertLess(r['gross_R'],-1)
    def test_favourable_open_gap_does_not_invent_improved_target(self):
        b=flat();b[1]=v1.Bar(300,1.102,1.1021,1.1019,1.102)
        r=labels(b);self.assertEqual(r['why'],'OPEN_TAKE_CAPPED');self.assertAlmostEqual(r['gross_R'],2)
    def test_both_barriers_keep_both_orders(self):
        b=[v1.Bar(0,1.1,1.1013,1.0993,1.1)]
        a=labels(b);c=labels(b,path='take_first')
        self.assertTrue(a['ambiguous']);self.assertTrue(c['ambiguous']);self.assertAlmostEqual(a['gross_R'],-1);self.assertAlmostEqual(c['gross_R'],2)
    def test_missing_interval_does_not_use_later_price(self):
        b=[flat()[0],v1.Bar(600,1.1015,1.102,1.1014,1.1016)]
        r=labels(b);self.assertEqual(r['status'],'UNAVAILABLE_DATA_GAP');self.assertIsNone(r['gross_R']);self.assertEqual(r['exit_bar'],600)
    def test_already_resolved_exit_does_not_require_future_data(self):
        b=[v1.Bar(0,1.1,1.1013,1.0999,1.1)]
        self.assertEqual(labels(b,hold=120)['status'],'RESOLVED')
    def test_long_ask_entry_short_ask_exit(self):
        b=[v1.Bar(0,1.1,1.10055,1.09995,1.1)]
        r=labels(b,signal(d=-1),spread=1);self.assertEqual(r['why'],'STOP');self.assertAlmostEqual(r['gross_R'],-1)
        b=flat();r=labels(b,spread=1);self.assertAlmostEqual(r['entry_price'],1.1001);self.assertAlmostEqual(r['gross_pips'],-1)
    def test_cost_is_per_roundtrip_and_scaled_by_initial_R(self):
        r=labels(flat());a=stats([r],.5);self.assertAlmostEqual(a['mean_pips'],-.5);self.assertAlmostEqual(a['mean_R'],-.5/6)
    def test_stop_rounding_and_rejection(self):
        r=labels(flat(),signal(atr=.000401));self.assertAlmostEqual(r['stop_pips'],6.1)
        r=labels(flat(),signal(atr=.003));self.assertEqual(r['status'],'REJECTED_STOP');self.assertFalse(r['entered'])
    def test_missing_entry_is_reported_without_fake_position(self):
        r=labels(flat(),signal(t=999));self.assertEqual(r['status'],'UNAVAILABLE_ENTRY');self.assertFalse(r['entered'])
        self.assertEqual(stats([r])['unavailable_entry'],1)
    def test_unavailable_is_not_zero_return(self):
        a=labels(flat(1));b=labels([v1.Bar(0,1.1,1.1013,1.0999,1.1)])
        result=stats([a,b]);self.assertEqual(result['resolved'],1);self.assertEqual(result['unavailable'],1);self.assertAlmostEqual(result['mean_R'],2)

class TrajectoryContracts(unittest.TestCase):
    def test_trajectory_after_exit_is_not_realized_profit(self):
        b=flat(7);b[0]=v1.Bar(0,1.1,1.1001,1.0993,1.1);b[2]=v1.Bar(600,1.1,1.102,1.0999,1.101);b[6]=v1.Bar(1800,1.101,1.1011,1.1009,1.101)
        self.assertAlmostEqual(labels(b,hold=30)['gross_R'],-1)
        r=trajectory(PriceBook(b),signal(),30);self.assertGreater(r['mfe_no_exit_R'],3);self.assertGreater(r['endpoint_R'],1)
    def test_trajectory_does_not_consume_deadline_future_range(self):
        b=flat(7);b[6]=v1.Bar(1800,1.1,1.2,1.,1.1)
        r=trajectory(PriceBook(b),signal(),30);self.assertLess(r['mfe_no_exit_R'],1);self.assertGreater(r['mae_no_exit_R'],-1)
    def test_partial_horizon_is_unavailable_even_if_bracket_resolved(self):
        b=[v1.Bar(0,1.1,1.1013,1.0999,1.1)]
        self.assertEqual(labels(b,hold=30)['status'],'RESOLVED');self.assertEqual(trajectory(PriceBook(b),signal(),30)['status'],'UNAVAILABLE_END')
    def test_short_trajectory_spread_and_endpoint(self):
        r=trajectory(PriceBook(flat(7)),signal(d=-1),30,1);self.assertAlmostEqual(r['endpoint_R'],-1/6);self.assertFalse(r['endpoint_up'])

class CohortContracts(unittest.TestCase):
    def test_one_position_blocks_exit_bar_but_allows_next_bar(self):
        b=flat(20);b[2]=v1.Bar(600,1.1,1.1013,1.0999,1.1)
        rows=[labels(b,signal(t=t),hold=30) for t in [0,300,600,900]]
        self.assertEqual([r['entry'] for r in one_position(rows)],[0,900])
    def test_gap_retains_exclusion_until_next_observation(self):
        b=[flat()[0]]+flat(15)[2:]
        rows=[labels(b,signal(t=t),hold=30) for t in [0,600,900]]
        self.assertEqual([r['entry'] for r in one_position(rows)],[0,900])
    def test_rejected_stop_does_not_block_valid_entry(self):
        a=labels(flat(),signal(atr=.003));b=labels(flat(),signal(t=300))
        self.assertEqual([r['entry'] for r in one_position([a,b])],[300])
    def test_paired_holds_exclude_any_missing_result(self):
        rows=[labels(flat(),hold=h) for h in [30,60,120]]
        self.assertEqual(len(paired(rows)),1)
        rows[-1]['status']='UNAVAILABLE_DATA_GAP';rows[-1]['gross_R']=None
        self.assertEqual(paired(rows),[])
    def test_paired_changes_use_same_entry_not_different_means(self):
        b=flat();b[6]=v1.Bar(1800,1.1002,1.1003,1.1001,1.1002);b[12]=v1.Bar(3600,1.1003,1.1004,1.1002,1.1003)
        rows=[labels(b,hold=h) for h in [30,60,120]]
        r=paired(rows)[0];self.assertAlmostEqual(r['delta60minus30'],1/6);self.assertAlmostEqual(r['delta120minus60'],-.5)

class ContextCausality(unittest.TestCase):
    def rows(self):return [{'anchor':str(1767225600+i*86400+3600),'atr':str((i+1)*.0001)} for i in range(13)]
    def test_atr_reference_requires_ten_completed_days(self):
        rows=self.rows();c=atr_context(rows)
        self.assertEqual(c[int(rows[9]['anchor'])]['atr_band'],'UNKNOWN')
        self.assertAlmostEqual(c[int(rows[10]['anchor'])]['hourly_past_median_pips'],5.5)
    def test_current_day_values_do_not_change_own_baseline(self):
        rows=self.rows();rows.append({'anchor':str(int(rows[-1]['anchor'])+300),'atr':'.2'})
        c=atr_context(rows);a=c[int(rows[-2]['anchor'])];b=c[int(rows[-1]['anchor'])]
        self.assertEqual(a['hourly_past_median_pips'],b['hourly_past_median_pips'])
    def test_future_data_does_not_rewrite_context(self):
        rows=self.rows();self.assertEqual(atr_context(rows[:11]),{t:r for t,r in atr_context(rows).items() if t<=int(rows[10]['anchor'])})

class NativeCausality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.folder=Path(cls.temp.name)
        cls.bars=[v1.Bar(i*300,1.1+i*.00002,1.1001+i*.00002,1.0999+i*.00002,1.10002+i*.00002,100) for i in range(150)]
        cls.rows=study.scan(cls.bars,cls.folder)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_native_scanner_emits_only_closed_window_features(self):
        changed=self.bars[:100]+[replace(b,o=b.o+.1,h=b.h+.1,l=b.l+.1,c=b.c+.1) for b in self.bars[100:]]
        other=study.scan(changed,self.folder)
        self.assertEqual([r for r in self.rows if int(r['anchor'])<=30000],[r for r in other if int(r['anchor'])<=30000])
    def test_prefix_has_identical_raw_features_and_signals(self):
        short=study.scan(self.bars[:110],self.folder)
        self.assertEqual(short,self.rows[:len(short)])
        a,_,_=study.make_signals(self.bars,self.rows);b,_,_=study.make_signals(self.bars[:110],short)
        for m in study.MODELS:self.assertEqual({t:s for t,s in a[m].items() if s.anchor<=109*300},b[m])
    def test_ablations_preserve_full_trigger_and_remove_only_one_bit(self):
        for r in self.rows:
            d=int(r['ema_direction']);common=r['tp_common']=='1';mask=int(r['tp_mask'])
            self.assertEqual(int(r['tp_unrouted']),d if common and mask==63 else 0)
            for k,name in enumerate(study.CONDITIONS):
                self.assertEqual(int(r['tp_without_'+name]),d if common and mask|(1<<k)==63 else 0)

if __name__=='__main__':unittest.main()
