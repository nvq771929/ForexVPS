import importlib.util
import math
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from screen import Bar, Signal, MODELS, hypotheses, atr14, make_signals, binary_reference, forex_reference, metrics, weekly_ci, load_bars

COST={'spread_pips':1.,'commission_roundtrip_pips':0.,'slippage_roundtrip_pips':0.}
def signal(t=0,d=1,atr=.0004):return Signal('test',t,t,d,atr)
def plain(n=14):return [Bar(i*300,1.1,1.1001,1.0999,1.1) for i in range(n)]
def trend():return [Bar(i*300,1.1+i*.00002-.00001,1.1+i*.00002+.00008,1.1+i*.00002-.00008,1.1+i*.00002) for i in range(64)]
def mirror(bars):return [Bar(b.t,2.2-b.o,2.2-b.l,2.2-b.h,2.2-b.c,b.v) for b in bars]
def native_stub(bars):
    out={};history=[]
    for b in bars:
        if history and b.t-history[-1].t!=300:history=[]
        if len(history)==64:out[b.t]={'atr_raw':atr14(history),'baseline_direction':1 if b.t//300%9==0 else 0}
        history.append(b)
        if len(history)>64:history.pop(0)
    return out

class DataAndCausality(unittest.TestCase):
    def test_strict_csv_audit_rejects_duplicate_or_bad_ohlc(self):
        for text in ['2026.01.01,00:00,1,2,0.9,1.5,2\n2026.01.01,00:00,1,2,0.9,1.5,2\n','2026.01.01,00:00,2,1,0.9,1.5,2\n']:
            with tempfile.TemporaryDirectory() as f:
                p=Path(f)/'bars.csv';p.write_text(text)
                with self.assertRaises(ValueError):load_bars(p)
    def test_future_and_entry_bar_ohlc_cannot_change_past_signals(self):
        bars=trend()+[Bar(i*300,1.1012,1.1014,1.101,1.1012+(.00002 if i%2 else 0)) for i in range(64,130)]
        changed=bars[:90]+[Bar(b.t,b.o+.01,b.h+.01,b.l+.01,b.c+.01,b.v) for b in bars[90:]]
        a,_=make_signals(bars,native_stub(bars));b,_=make_signals(changed,native_stub(changed))
        for m in MODELS:self.assertEqual({t:s for t,s in a[m].items() if s.anchor<=90*300},{t:s for t,s in b[m].items() if s.anchor<=90*300})
    def test_gap_requires_a_fresh_closed_window(self):
        bars=trend()+[Bar((i+1)*300,1.1,1.1001,1.0999,1.1) for i in range(64,130)]
        data=native_stub(bars);_,n=make_signals(bars,data)
        self.assertEqual(n,2);self.assertNotIn(65*300,data);self.assertIn(129*300,data)
    def test_native_proxy_lead_is_one_bar_and_uses_same_anchor(self):
        bars=trend()+[Bar(64*300,1.1,1.1001,1.0999,1.1)]
        native={bars[-1].t:{'atr_raw':atr14(bars[:64]),'baseline_direction':1}}
        a,_=make_signals(bars,native)
        self.assertEqual(next(iter(a[MODELS[0]]))-next(iter(a[MODELS[1]])),300)
        self.assertEqual(next(iter(a[MODELS[0]].values())).anchor,next(iter(a[MODELS[1]].values())).anchor)

class HypothesisContracts(unittest.TestCase):
    def test_trend_pullback_positive_and_mirrored_short(self):
        h=trend()
        for i,c in [(60,1.10114),(61,1.10110),(62,1.10106)]:h[i]=Bar(i*300,c+.00002,c+.00008,c-.00008,c)
        fast=sum(b.c for b in h[-21:-1])/20
        h[-1]=Bar(63*300,fast-.00004,fast+.00018,fast-.00008,fast+.00015)
        self.assertEqual(hypotheses(h)[1]['trend_pullback'],1);self.assertEqual(hypotheses(mirror(h))[1]['trend_pullback'],-1)
    def test_range_rejection_positive_and_mirrored_short(self):
        h=plain(64);h[-1]=Bar(63*300,1.09995,1.10013,1.09986,1.1001)
        self.assertEqual(hypotheses(h)[1]['range_rejection'],1);self.assertEqual(hypotheses(mirror(h))[1]['range_rejection'],-1)
    def test_breakout_positive_and_mirrored_short(self):
        h=trend();h[-1]=Bar(63*300,1.10125,1.10147,1.10124,1.10145)
        self.assertEqual(hypotheses(h)[1]['breakout_momentum'],1);self.assertEqual(hypotheses(mirror(h))[1]['breakout_momentum'],-1)
    def test_shock_and_discontinuous_history_do_not_create_new_signals(self):
        h=plain(64);h[-1]=Bar(63*300,1.1,1.12,1.08,1.11)
        self.assertTrue(all(v==0 for v in hypotheses(h)[1].values()))
        h[-1]=Bar(65*300,1.1,1.1001,1.0999,1.1);self.assertIsNone(hypotheses(h))

class BinaryContracts(unittest.TestCase):
    def test_reference_win_loss_tie_and_payout(self):
        bars=[Bar(0,1.1,1.1002,1.0999,1.1),Bar(300,1.1001,1.1002,1.1,1.1001)]
        self.assertEqual(binary_reference(bars,{0:signal()},.82)[0]['return_units'],.82)
        self.assertEqual(binary_reference(bars,{0:signal(d=-1)},.82)[0]['return_units'],-1)
        same=[bars[0],Bar(300,1.1,1.1002,1.0999,1.1)]
        self.assertEqual(binary_reference(same,{0:signal()})[0]['return_units'],0)
    def test_expiry_is_next_open_not_entry_bar_close(self):
        bars=[Bar(0,1.1,1.101,1.099,1.1005),Bar(300,1.0999,1.101,1.099,1.1005)]
        self.assertEqual(binary_reference(bars,{0:signal()})[0]['outcome'],'LOSS')
    def test_missing_entry_or_expiry_is_unavailable(self):
        for bars in [[plain()[0]],[plain()[1]]]:
            r=binary_reference(bars,{0:signal()})[0];self.assertIsNone(r['return_units']);self.assertEqual(r['status'],'UNAVAILABLE_BOUNDARY')

class ForexContracts(unittest.TestCase):
    def test_long_take_is_ask_entry_bid_exit_and_fees_are_charged(self):
        bars=[Bar(0,1.1,1.1014,1.1,1.1013)]
        r,_=forex_reference(bars,{0:signal()},COST,'stop_first');self.assertAlmostEqual(r[0]['return_R'],2)
        cost=dict(COST,commission_roundtrip_pips=.7,slippage_roundtrip_pips=.3)
        s,_=forex_reference(bars,{0:signal()},cost,'stop_first');self.assertAlmostEqual(s[0]['return_R'],2-1/6)
        self.assertAlmostEqual(s[0]['entry_price'],1.1001)
    def test_short_stop_uses_ask_not_bid_high(self):
        bars=[Bar(0,1.1,1.10055,1.09995,1.1)]
        r,_=forex_reference(bars,{0:signal(d=-1)},COST,'stop_first')
        self.assertEqual(r[0]['why'],'STOP');self.assertAlmostEqual(r[0]['return_R'],-1)
    def test_both_barriers_have_two_explicit_scenarios(self):
        bars=[Bar(0,1.1,1.1014,1.0994,1.1)]
        a,_=forex_reference(bars,{0:signal()},COST,'stop_first');b,_=forex_reference(bars,{0:signal()},COST,'take_first')
        self.assertTrue(a[0]['ambiguous']);self.assertTrue(b[0]['ambiguous']);self.assertAlmostEqual(a[0]['return_R'],-1);self.assertAlmostEqual(b[0]['return_R'],2)
    def test_adverse_open_gap_is_not_filled_optimistically_at_stop(self):
        bars=[plain()[0],Bar(300,1.099,1.0992,1.0988,1.099)]
        r,_=forex_reference(bars,{0:signal()},COST,'stop_first')
        self.assertEqual(r[0]['why'],'OPEN_STOP_GAP');self.assertAlmostEqual(r[0]['exit_price'],1.099);self.assertLess(r[0]['return_R'],-1)
    def test_favourable_open_gap_is_capped_at_target(self):
        bars=[plain()[0],Bar(300,1.0985,1.0986,1.0983,1.0985)]
        r,_=forex_reference(bars,{0:signal(d=-1)},COST,'stop_first');self.assertAlmostEqual(r[0]['return_R'],2);self.assertEqual(r[0]['why'],'OPEN_TAKE_CAPPED')
    def test_missing_m5_interval_does_not_invent_stop_or_profit(self):
        bars=[plain()[0],Bar(600,1.1,1.102,1.098,1.1)]
        r,_=forex_reference(bars,{0:signal()},COST,'stop_first');self.assertEqual(r[0]['status'],'UNAVAILABLE_DATA_GAP');self.assertIsNone(r[0]['return_R'])
    def test_time_exit_requires_observed_sixty_minute_open(self):
        a,_=forex_reference(plain(13),{0:signal()},COST,'stop_first');self.assertEqual(a[0]['why'],'MAX_HOLD');self.assertAlmostEqual(a[0]['return_R'],-1/6)
        b,_=forex_reference(plain(12),{0:signal()},COST,'stop_first');self.assertEqual(b[0]['status'],'UNAVAILABLE_END')
    def test_no_reentry_on_a_bar_occupied_at_its_open(self):
        bars=[plain()[0],Bar(300,1.1,1.102,1.0999,1.101),Bar(600,1.1,1.102,1.0999,1.101)]
        r,b=forex_reference(bars,{0:signal(),300:signal(300),600:signal(600)},COST,'stop_first')
        self.assertEqual(len(r),2);self.assertEqual(b['position_at_bar_open'],1)
    def test_stop_cap_is_rejection_not_clipping(self):
        r,b=forex_reference(plain(),{0:signal(atr=.003)},COST,'stop_first');self.assertFalse(r);self.assertEqual(b['stop_over30pips'],1)
    def test_stop_distance_is_rounded_outward_to_tick(self):
        bars=[Bar(0,1.1,1.102,1.0999,1.101)]
        r,_=forex_reference(bars,{0:signal(atr=.000401)},COST,'stop_first');self.assertAlmostEqual(r[0]['stop_pips'],6.1)

class StatisticsContracts(unittest.TestCase):
    def test_unavailable_is_not_a_zero_profit_trade(self):
        r=metrics([{'return_R':None},{'return_R':-1},{'return_R':2},{'return_R':-2}],'return_R')
        self.assertEqual(r['entered'],4);self.assertEqual(r['resolved'],3);self.assertEqual(r['unavailable'],1);self.assertEqual(r['sum_return'],-1);self.assertEqual(r['max_drawdown_units'],2)
    def test_weekly_bootstrap_is_deterministic_and_sign_correct(self):
        rows=[{'entry':i*7*86400,'x':-1.} for i in range(10)];from screen import broker_week
        weeks=sorted({broker_week(r['entry']) for r in rows})
        a=weekly_ci(rows,'x',weeks,100);b=weekly_ci(rows,'x',weeks,100);self.assertEqual(a,b);self.assertEqual(a,(-1,-1))
    def test_insufficient_sample_does_not_claim_a_confidence_interval(self):self.assertEqual(weekly_ci([{'entry':0,'x':1}],'x',['1970-W01'],100),(None,None))

if __name__=='__main__':unittest.main()
