"""Causal observer parity and integration isolation. No market-profit claims."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
from tools.verify_embedded_context import compile_runner,compare
from tests.test_demo_learning_native import NativeHarness,ROOT
from tests.fixtures import Bar,START,sr_bars


def stream(n=2100):
    start=1760054400//3600*3600;out=[];prev=1.12
    for i in range(n):
        close=1.12+.0015*math.sin(i/43)+.0003*math.sin(i/5)+i*.0000005
        # A real chronological gap exercises reset/aggregation/stale frame rules.
        t=start+(i+(12 if i>=1950 else 0))*300
        out.append(dict(time=t,open=prev,high=max(prev,close)+.00011,
            low=min(prev,close)-.00009,close=close,ticks=i%170))
        prev=close
    return out


class EmbeddedCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.binary=Path(cls.tmp.name)/'observer';compile_runner(cls.binary)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_reference_parity_warmup_transitions_and_gap(self):
        r=compare(stream(),self.binary)
        self.assertEqual(r['status'],'PASS');self.assertGreater(r['exact_discrete_values'],30000)

    def test_invalid_or_nonmonotonic_bars_do_not_mutate_state(self):
        bars=stream(1);b=bars[0]
        line=lambda x:' '.join(str(x[k]) for k in ('time','open','high','low','close','ticks'))+'\n'
        invalid=[dict(b,time=b['time']+1),dict(b,ticks=-1),dict(b,low=b['high']+.1)]
        text=line(b)+line(b)+''.join(line(x) for x in invalid)+line(dict(b,time=b['time']+300))
        rows=subprocess.run([str(self.binary)],input=text,capture_output=True,text=True,check=True).stdout.splitlines()
        self.assertEqual(rows[1:5],['REJECT']*4)
        self.assertEqual(int(rows[-1].split(',')[0]),(b['time']+600)*1000)

    def test_state_is_not_trained_or_order_capable(self):
        text=(ROOT/'mt4/Include/EURUSD_M5_V224/EmbeddedContext.mqh').read_text()
        for token in ('FileOpen(', 'CopyRates(', 'OrderSend(', 'BOAdvisor', 'TimeGMT(', 'WebRequest(', '#import'):
            self.assertNotIn(token,text)
        self.assertIn('if(!v.ready)ECClearDirection(s)',text)

    def test_native_boundary_and_forex_code_remain_frozen(self):
        original=json.loads((ROOT/'baseline_v224_rc3_sha256.json').read_text())
        paths=[n for n in original if n.startswith('mt4/Include/')]
        self.assertGreater(len(paths),20)
        for n in paths:self.assertEqual(hashlib.sha256((ROOT/n).read_bytes()).hexdigest(),original[n],n)
        receipt=json.loads((ROOT/'docs/embedded_native_preservation.json').read_text())
        self.assertTrue(all(x['identical'] for x in receipt['functions']))
        main=(ROOT/'mt4/Experts/EURUSD_M5_Intelligence_V228.mq4').read_text()
        for row in receipt['functions']:
            start=main.index(row['name']+'(');start=main.rfind('\n',0,start)+1
            br=main.index('{',start);level=1;i=br+1
            while level:
                level+=(main[i]=='{')-(main[i]=='}');i+=1
            function=main[start:i]
            if row['name']=='FXInitFromInputs':
                # The handed-off ChartFix1 permits a different display timeframe
                # on live charts only. All other initialization/risk logic is frozen.
                changed='if((IsTesting() && Period()!=PERIOD_M5) ||'
                self.assertEqual(function.count(changed),1)
                function=function.replace(changed,'if(Period()!=PERIOD_M5 ||')
            self.assertEqual(hashlib.sha256(function.encode()).hexdigest(),row['rc3_sha256'],row['name'])

    def test_pilot_is_binary_only_and_explicit_clock(self):
        p=ROOT/'MQL4/Presets/EURUSD_M5_V228_Embedded_Pilot_UTC0.set'
        v=dict(x.split('=',1) for x in p.read_text().splitlines() if '=' in x)
        for k in ('EnableEmbeddedContext','EmbeddedBrokerClockVerified'):self.assertEqual(v[k],'true')
        for k in ('ForexEnableTrading','ForexAllowRealTrading','EnableBinaryLearningDialogue','BinaryLearningAdviceAffectsSignals'):
            self.assertEqual(v[k],'false')
        self.assertEqual(v['DemoExpiryMinutes'],'5');self.assertEqual(v['EmbeddedBrokerUTCOffsetMinutes'],'0')


def warm_fixture(direction=1):
    bars=[]
    for i in range(2100-64):
        t=START-(2100-i)*300;c=1.10+.0002*math.sin(i/30)
        bars.append(Bar(t,c,c+.0002,c-.0002,c,20))
    return bars+sr_bars(direction)


class EmbeddedAdapterTests(NativeHarness,unittest.TestCase):
    def test_attach_bootstrap_excludes_current_bar_and_can_warm_without_cmd(self):
        with tempfile.TemporaryDirectory() as tmp:
            r,_=self.execute(tmp,mode=54,factory=warm_fixture)
            self.assertTrue(r['ready']);self.assertGreaterEqual(r['h1'],150)
            self.assertLessEqual(r['asof'],(START-100)*1000)
            self.assertEqual(r['stale'],'STALE')

    def test_pending_boundary_defers_observer_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            r,source=self.execute(tmp,mode=55,factory=warm_fixture)
            self.assertEqual(r['m5'],r['before'])
            self.assertFalse(list(source.glob('embedded_context_v226_*.csv')))

    def test_consumed_history_revision_stops_only_observer(self):
        with tempfile.TemporaryDirectory() as tmp:
            r,_=self.execute(tmp,mode=56,factory=warm_fixture)
            self.assertEqual(r['status'],'HISTORY_CHANGED_NEW_INSTANCE_TAG');self.assertEqual(r['m5'],r['before'])

    def test_ready_journal_availability_is_current_not_a_backdated_forecast(self):
        import csv
        with tempfile.TemporaryDirectory() as tmp:
            r,source=self.execute(tmp,mode=57,factory=warm_fixture)
            with next(source.glob('embedded_context_v226_*.csv')).open() as stream:
                rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),1)
            row=rows[0];self.assertGreaterEqual(int(row['available_broker_ms']),int(row['asof_utc_ms']))
            self.assertEqual(row['trade_model'],'UNAVAILABLE');self.assertEqual(row['ea_effects'],'0')

    def test_enabled_observer_preserves_native_ledger_input_and_manual_book(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            off,sa=self.execute(a,mode=0);on,sb=self.execute(b,mode=50)
            self.assertEqual(on['signals'],off['signals']);self.assertEqual(on['manual_wins'],off['manual_wins'])
            self.assertGreater(on['embedded_bootstrap'],0);self.assertGreater(on['embedded_m5'],0)
            for pattern in ('event_*.bin','input_*.csv','manual_v218*'):
                left={p.name:p.read_bytes() for p in sa.glob(pattern) if p.is_file()}
                right={p.name:p.read_bytes() for p in sb.glob(pattern) if p.is_file()}
                self.assertTrue(left,pattern);self.assertEqual(left,right,pattern)
            self.assertEqual(len(list(sb.glob('embedded_context_v226_*.csv'))),1)
            self.assertFalse(list(sa.glob('embedded_context_v226_*.csv')))

    def test_clock_unverified_does_no_extra_history_or_analysis(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            off,_=self.execute(a);on,source=self.execute(b,mode=51)
            self.assertEqual(on['embedded_status'],'CLOCK_UNVERIFIED');self.assertEqual(on['embedded_m5'],0)
            self.assertEqual(off['copy_requests'],on['copy_requests'])
            self.assertFalse(list(source.glob('embedded_context_v226_*.csv')))

    def test_invalid_offset_rejects_initialization(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,_=self.execute(tmp,mode=52);self.assertEqual(result['init'],2)

    def test_zero_bootstrap_consumes_cache_only(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            off,_=self.execute(a);on,_=self.execute(b,mode=53)
            self.assertEqual(on['embedded_bootstrap'],0);self.assertGreater(on['embedded_m5'],0)
            self.assertEqual(on['copy_requests'],off['copy_requests'])

    def test_tester_keeps_backtest_origin_and_no_extra_boundary_history(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            off,sa=self.execute(a,testing=True);on,sb=self.execute(b,mode=50,testing=True)
            self.assertEqual(on['manual_total'],off['manual_total'])
            self.assertEqual({p.name:p.read_bytes() for p in sa.glob('event_*.bin')},{p.name:p.read_bytes() for p in sb.glob('event_*.bin')})
            log=next(sb.glob('embedded_context_v226_*.csv')).read_text()
            self.assertIn('BACKTEST_MT4',log);self.assertNotIn('LIVE_MT4',log)

if __name__=='__main__':unittest.main()
