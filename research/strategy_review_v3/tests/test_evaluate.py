from dataclasses import replace
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import evaluate as e
from evaluate import v2

def flat(n=25):return [v2.v1.Bar(i*300,1.1,1.1001,1.0999,1.1) for i in range(n)]
def signal(d=1):return v2.v1.Signal('test',0,0,d,.0004)
def sim(bars,policy='STRUCT_BE',d=1,hold=30):
    return e.simulate(v2.PriceBook(bars),signal(d),1.0998 if d>0 else 1.1002,{b.t:.0001 for b in bars},hold,'stop_first',policy)

class Management(unittest.TestCase):
    def test_intrabar_high_does_not_activate_BE_at_prior_open(self):
        b=flat();b[0]=v2.v1.Bar(0,1.1,1.1008,1.0999,1.1007)
        r=sim(b);self.assertEqual(r['stop_moves'],0);self.assertEqual(r['why'],'MAX_HOLD')
    def test_BE_uses_observed_open_and_originalR(self):
        b=flat();b[1]=v2.v1.Bar(300,1.1007,1.1008,1.10001,1.1001)
        r=sim(b);self.assertEqual(r['why'],'STOP');self.assertEqual(r['be_moves'],1);self.assertAlmostEqual(r['gross_pips'],.5);self.assertAlmostEqual(r['gross_R'],.5/6)
    def test_short_BE_mirrors_long(self):
        b=flat();b[1]=v2.v1.Bar(300,1.0993,1.09999,1.0992,1.0999)
        r=sim(b,d=-1);self.assertEqual(r['be_moves'],1);self.assertAlmostEqual(r['gross_pips'],.5)
    def test_trailing_uses_closedATR_and_does_not_move_backwards(self):
        b=flat();b[1]=v2.v1.Bar(300,1.10095,1.101,1.1006,1.1007)
        r=sim(b,policy='STRUCT_BE_TRAIL');self.assertEqual(r['trail_moves'],1);self.assertAlmostEqual(r['final_stop'],1.10065)
        new,why=e.protected_stop(1.1,1,.0006,1.10065,1.1012,1.1010,.0008,'STRUCT_BE_TRAIL')
        self.assertEqual(new,1.10065);self.assertEqual(why,'')
    def test_BE_only_does_not_trail(self):
        new,why=e.protected_stop(1.1,1,.0006,1.0994,1.1012,1.10095,.0001,'STRUCT_BE')
        self.assertAlmostEqual(new,1.10005);self.assertEqual(why,'BREAK_EVEN')
    def test_take_at_open_precedes_modification(self):
        b=flat();b[1]=v2.v1.Bar(300,1.1013,1.1014,1.1,1.1)
        r=sim(b,policy='STRUCT_BE_TRAIL');self.assertEqual(r['why'],'OPEN_TAKE_CAPPED');self.assertEqual(r['stop_moves'],0)
    def test_timeout_precedes_modification_and_ignores_future_range(self):
        b=flat();b[6]=v2.v1.Bar(1800,1.1008,1.2,1.,1.1)
        r=sim(b);self.assertEqual(r['why'],'MAX_HOLD');self.assertEqual(r['stop_moves'],0)
    def test_stop_gap_is_not_filled_at_stop(self):
        b=flat();b[1]=v2.v1.Bar(300,1.099,1.0992,1.0989,1.099)
        r=sim(b);self.assertEqual(r['why'],'OPEN_STOP_GAP');self.assertLess(r['gross_R'],-1)
    def test_wrong_side_structural_stop_rejected(self):
        p,why=e.plan(1.1,1,.0004,1.1001);self.assertIsNone(p);self.assertEqual(why,'REJECTED_STRUCTURAL_STOP')
    def test_structural_stop_can_override_ATR_but_cannot_clip_cap(self):
        p,_=e.plan(1.1,1,.0004,1.099);self.assertAlmostEqual(p['distance'],.001)
        p,why=e.plan(1.1,1,.0004,1.096);self.assertIsNone(p);self.assertEqual(why,'REJECTED_STOP')
    def test_gap_outcome_unavailable_with_no_fake_profit(self):
        r=sim([flat()[0]]+flat()[2:]);self.assertEqual(r['status'],'UNAVAILABLE_DATA_GAP');self.assertIsNone(r['gross_R'])
    def test_control_exactly_reuses_v2_contract(self):
        b=flat();a=e.simulate(v2.PriceBook(b),signal(),0,{},60,'stop_first','ATR_FIXED_CONTROL');prior=v2.bracket(v2.PriceBook(b),signal(),60,'stop_first')
        for k,v in prior.items():self.assertEqual(a[k],v)
    def test_stop_and_take_same_bar_keep_both_paths(self):
        b=[v2.v1.Bar(0,1.1,1.1013,1.0993,1.1)]
        a=e.simulate(v2.PriceBook(b),signal(),1.0998,{},30,'stop_first','STRUCT_FIXED')
        c=e.simulate(v2.PriceBook(b),signal(),1.0998,{},30,'take_first','STRUCT_FIXED')
        self.assertAlmostEqual(a['gross_R'],-1);self.assertAlmostEqual(c['gross_R'],2)

class BOHorizons(unittest.TestCase):
    def test_all_expiries_use_observed_open_not_close(self):
        b=flat()
        for expiry in [5,10,15]:
            q=b.copy();q[expiry//5]=v2.v1.Bar(expiry*60,1.1001,1.101,1.099,1.099)
            r=e.binary_labels(v2.PriceBook(q),signal(),expiry);self.assertEqual(r['outcome'],'WIN');self.assertEqual(r['return82'],.82)
    def test_missing_interior_is_unavailable_at_longer_expiry(self):
        b=[flat()[0]]+flat()[2:];r=e.binary_labels(v2.PriceBook(b),signal(),15)
        self.assertEqual(r['status'],'UNAVAILABLE_BOUNDARY_OR_PATH');self.assertIsNone(r['return82'])
    def test_ties_refunded_not_counted_as_wins(self):
        r=e.binary_labels(v2.PriceBook(flat()),signal(),5);self.assertEqual(r['outcome'],'TIE');self.assertEqual(r['return82'],0)

class NativeParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.folder=Path(cls.temp.name)
        cls.probe=cls.folder/'plan_probe'
        subprocess.run(['g++','-std=c++17','-O2',str(ROOT/'tests/plan_probe.cpp'),'-o',str(cls.probe)],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_price_plan_matches_actual_frozen_FXBuildPlan(self):
        rng=random.Random(20261029);samples=[]
        for _ in range(200):
            entry=round(rng.uniform(1.,1.2),5);d=rng.choice([-1,1]);atr=rng.uniform(.00005,.0022);inv=entry-d*rng.uniform(-.0002,.0035)
            samples.append((entry,d,atr,inv))
        p=subprocess.run([str(self.probe)],input='\n'.join(' '.join(map(str,x)) for x in samples)+'\n',capture_output=True,text=True,check=True)
        for args,line in zip(samples,p.stdout.splitlines()):
            actual=line.split(',');expected,status=e.plan(*args)
            self.assertEqual(expected is not None,actual[0]=='1',args)
            if expected:
                self.assertAlmostEqual(expected['stop'],float(actual[1]),places=10);self.assertAlmostEqual(expected['take'],float(actual[2]),places=10)
    def test_structural_scanner_has_closed_bar_prefix_causality(self):
        bars=[v2.v1.Bar(i*300,1.1+i*.00002,1.1001+i*.00002,1.0999+i*.00002,1.10002+i*.00002,100) for i in range(130)]
        a=e.structural_scan(bars,self.folder)
        changed=bars[:100]+[replace(b,o=b.o+.1,h=b.h+.1,l=b.l+.1,c=b.c+.1) for b in bars[100:]]
        b=e.structural_scan(changed,self.folder)
        self.assertEqual([r for r in a if int(r['anchor'])<=30000],[r for r in b if int(r['anchor'])<=30000])

if __name__=='__main__':unittest.main()
