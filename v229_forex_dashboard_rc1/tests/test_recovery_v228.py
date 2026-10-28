"""Recovery regressions execute two independent copies of the EA on a shared fake broker.

These are C++/file semantics tests, not a MetaEditor compile or a Windows pilot.
"""
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from tests.fixtures import START, sr_bars
from tests.test_demo_learning_native import NativeHarness

ROOT = Path(__file__).resolve().parents[1]


class RecoveredChartTests(NativeHarness, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        source = re.sub(r'^#(?:ifndef \w+|define \w+\s*|endif)\s*$', '', cls.native_source, flags=re.M)
        # Each namespace has its own EA globals, clocks, leases and input values.
        # Only broker state and the test filesystem API are shared.
        code = cls.native_shim + cls.native_api
        code += '\nnamespace chartA {\n' + source + '\n}\nnamespace chartB {\n' + source + '\n}\n'
        code += r'''
void activateA(){fakeChartID=101;fakeSymbol="EURUSD";}
void activateB(){fakeChartID=202;fakeSymbol="EURUSDz";}
int main(int argc,char**argv){
 filesRoot=argv[1];int scenario=std::stoi(argv[2]);long long start;int count;std::cin>>start>>count;
 for(int i=0;i<count;i++){FakeBar b;std::cin>>b.time>>b.open>>b.high>>b.low>>b.close>>b.ticks;closedBars.push_back(b);addBar(b);}
 fakeNowMs=(start-100)*1000;fakeServer="Exness-Demo";
 if(scenario>=200){
  activateA();bool parity=true;
  if(scenario==201)fakeTesting=true;
  if(scenario==202)fakeNowMs=(fakeNowMs/4294967296LL+1)*4294967296LL-4000;
  if(scenario==203)fakePCUTCJumpSeconds=3600;
  chartA::BOClockObservationBind("clock_test","run","BinaryOption",scenario!=204);
  for(int i=0;i<18;i++){
   fakeNowMs+=1000;long server=TimeCurrent()-(i==4 || i==5 ? 10:0);
   long base=chartA::boClockBaseMs,last=chartA::boLastTickMs;uint mono=chartA::boClockMono;
   long oldNow=0;bool oldOK=chartA::BOClockTick(server,oldNow);
   long expectedBase=chartA::boClockBaseMs,expectedLast=chartA::boLastTickMs;uint expectedMono=chartA::boClockMono;
   chartA::boClockBaseMs=base;chartA::boLastTickMs=last;chartA::boClockMono=mono;
   long observedNow=0;bool observedOK=chartA::BOObservedClockTick(server,observedNow);
   parity=parity && oldNow==observedNow && oldOK==observedOK && expectedBase==chartA::boClockBaseMs &&
      expectedLast==chartA::boLastTickMs && expectedMono==chartA::boClockMono;
  }
  std::cout<<"{\"parity\":"<<parity<<",\"rows\":"<<chartA::boClockObservationSequence<<"}";return 0;
 }
 chartA::InstanceTag="v229_binary_demo_utc0";chartA::TradingMode=chartA::BinaryOption;
 chartB::InstanceTag="v229_forex_demo_utc0";chartB::TradingMode=chartB::Forex;chartB::ForexNewsFilter=false;
 if(scenario==11 || scenario==12)fakePeriod=15;
 if(scenario==12)fakeTesting=true;
 if(scenario==18){fakeAccountMode=ACCOUNT_TRADE_MODE_REAL;fakeServer="Exness-Real18";chartB::ForexAllowRealTrading=true;}
 int a=-9,b=-9,changed=-9;
 if(scenario==1){activateA();a=chartA::OnInit();activateB();b=chartB::OnInit();}
 else{activateB();b=chartB::OnInit();
  if(scenario!=8 && scenario!=12 && scenario!=19)fakeOrders.push_back({88,OP_BUY,2220520,"EURUSDz","FX222:recovery",.01,1.1,1.099,1.102,0,0,0,TimeCurrent(),0});
  activateA();a=chartA::OnInit();}
 if(scenario==1)fakeOrders.push_back({88,OP_BUY,2220520,"EURUSDz","FX222:recovery",.01,1.1,1.099,1.102,0,0,0,TimeCurrent(),0});
 if(scenario==2){activateB();chartB::OnDeinit(0);fakeNowMs+=1000;b=chartB::OnInit();}
 if(scenario==3){activateA();chartA::OnDeinit(0);fakeNowMs+=1000;a=chartA::OnInit();}
 if(scenario==4 || scenario==9 || scenario==15){activateB();chartB::OnDeinit(0);
  if(scenario==9 || scenario==15)fakeOrders.clear();chartB::TradingMode=chartB::BinaryOption;changed=chartB::OnInit();}
 if(scenario==5 || scenario==8){activateA();chartA::OnDeinit(0);chartA::TradingMode=chartA::Forex;
  chartA::ForexNewsFilter=false;changed=chartA::OnInit();}
 if(scenario==6){activateB();chartB::OnDeinit(0);chartB::ForexMagicNumber++;changed=chartB::OnInit();}
 if(scenario==7){activateB();chartB::OnDeinit(0);fakeSymbol="EURUSD";changed=chartB::OnInit();}
 if(scenario==10 || scenario==14){activateA();chartA::OnDeinit(0);
  std::ofstream f(nativePath(chartA::boRolePath),std::ios::binary|std::ios::app);f<<(scenario==10?"CORRUPTED\n":"V228_CHART_ROLE_V1,2");f.close();changed=chartA::OnInit();}
 if(scenario==13){activateB();chartB::OnDeinit(0);std::ofstream f(nativePath(chartB::boRolePath));f<<"CORRUPTED\n";f.close();changed=chartB::OnInit();}
 if(scenario==15 && changed==0){chartB::OnDeinit(0);fakeNowMs+=1000;changed=chartB::OnInit();}
 if(scenario==19){activateB();fakeNowMs+=1000;chartB::OnTick();}
 int sent=fakeSendCalls,closed=fakeCloseCalls,modified=fakeModifyCalls;
 if(a==0 && scenario!=5 && scenario!=8 && scenario!=10 && scenario!=14){
  activateA();for(int i=0;i<6;i++){fakeNowMs+=1000;chartA::OnTick();chartA::OnTimer();}
 }
 bool isolated=fakeSendCalls==sent && fakeCloseCalls==closed && fakeModifyCalls==modified;
 bool manager=chartB::fxStarted;int orders=fakeOrders.size();
 if(scenario==16 && b==0){
  activateB();fakeOrders[0].opened=TimeCurrent()-3601;OrderSelect(0,SELECT_BY_POS,MODE_TRADES);
  chartB::FXSaveOriginalRisk();long now=0;chartB::BOClockTick(TimeCurrent(),now);chartB::FXManagePositions();
 }
 std::cout<<"{\"binary_init\":"<<a<<",\"forex_init\":"<<b<<",\"changed_init\":"<<changed
  <<",\"isolated\":"<<isolated<<",\"manager_active\":"<<manager<<",\"orders_before_management\":"<<orders
  <<",\"orders_after_management\":"<<fakeOrders.size()<<",\"close_calls\":"<<fakeCloseCalls<<"}";
 return 0;
}
'''
        path = cls.binary.parent/'two_charts.cpp'
        path.write_text(code)
        cls.binary = path.with_suffix('')
        proc = subprocess.run(['g++', '-std=c++17', '-O1', str(path), '-o', str(cls.binary)], capture_output=True, text=True)
        if proc.returncode:
            raise RuntimeError(proc.stderr)

    def run_scenario(self, scenario, folder):
        bars = sr_bars(1)
        text = f'{START} {len(bars)}\n' + '\n'.join(f'{b.time} {b.open:.17g} {b.high:.17g} {b.low:.17g} {b.close:.17g} {b.ticks}' for b in bars) + '\n'
        proc = subprocess.run([str(self.binary), str(folder), str(scenario)], input=text, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_both_initialization_orders_allow_independent_binary_and_forex_charts(self):
        for case in (0, 1):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                r = self.run_scenario(case, tmp)
                self.assertEqual((r['binary_init'], r['forex_init']), (0, 0));self.assertTrue(r['isolated'])
                self.assertEqual(r['orders_after_management'], 1)

    def test_restart_either_chart_keeps_both_roles_and_forex_position(self):
        for case in (2, 3):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                r = self.run_scenario(case, tmp)
                self.assertEqual((r['binary_init'], r['forex_init']), (0, 0));self.assertTrue(r['manager_active'])
                self.assertEqual(r['orders_after_management'], 1)

    def test_switching_forex_chart_to_binary_with_position_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_scenario(4, tmp);self.assertEqual(r['changed_init'], 1)
            self.assertEqual(r['orders_after_management'], 1)

    def test_second_forex_manager_is_blocked_with_and_without_open_position(self):
        for case in (5, 8):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                r = self.run_scenario(case, tmp);self.assertEqual(r['changed_init'], 1)
                self.assertTrue(r['manager_active'])

    def test_forex_symbol_or_magic_change_cannot_abandon_position(self):
        for case in (6, 7):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                r = self.run_scenario(case, tmp);self.assertEqual(r['changed_init'], 1)
                self.assertEqual(r['orders_after_management'], 1)

    def test_role_transition_without_positions_is_persisted_and_restartable(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_scenario(15, tmp);self.assertEqual(r['changed_init'], 0)
            ledgers = list((Path(tmp)/'EA_MODE_V228').glob('*_202_LIVE.csv'))
            self.assertEqual(len(ledgers), 1)
            with ledgers[0].open() as stream:
                rows = list(csv.reader(stream))
            self.assertEqual([row[9] for row in rows], ['1', '0'])

    def test_corrupt_or_truncated_role_state_blocks_initialization(self):
        for case in (10, 13, 14):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                r = self.run_scenario(case, tmp);self.assertEqual(r['changed_init'], 1)
                self.assertEqual(r['orders_after_management'], 1)

    def test_live_chart_period_change_is_allowed_while_analysis_remains_m5(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_scenario(11, tmp)
            self.assertEqual((r['binary_init'], r['forex_init']), (0, 0));self.assertTrue(r['isolated'])

    def test_non_m5_tester_remains_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_scenario(12, tmp)
            self.assertEqual((r['binary_init'], r['forex_init']), (2, 2))

    def test_binary_never_manages_forex_but_forex_manager_can_close_expired_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_scenario(16, tmp);self.assertTrue(r['isolated'])
            self.assertEqual(r['orders_before_management'], 1);self.assertEqual(r['orders_after_management'], 0)
            self.assertEqual(r['close_calls'], 1)

    def test_real_account_still_supports_separate_binary_and_forex_charts(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_scenario(18, tmp)
            self.assertEqual((r['binary_init'], r['forex_init']), (0, 0));self.assertTrue(r['isolated'])

    def test_frozen_forex_engine_emits_observations_through_adapter_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_scenario(19, tmp)
            self.assertEqual((r['binary_init'], r['forex_init']), (0, 0))
            paths = list((Path(tmp)/'FX_V222').glob('LIVE_*/clock_observation_v227_*.csv'))
            self.assertEqual(len(paths), 1)
            with paths[0].open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['mode'], 'Forex');self.assertEqual(rows[0]['symbol'], 'EURUSDz')
            self.assertEqual(rows[0]['accepted'], '1')

    def test_clock_observer_preserves_accepted_and_rejected_clock_state(self):
        for case in (200, 201, 202, 203):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                r = self.run_scenario(case, tmp);self.assertTrue(r['parity']);self.assertEqual(r['rows'], 18)
                paths = list((Path(tmp)/'clock_test').glob('clock_observation_v227_*.csv'))
                rows = []
                for p in paths:
                    with p.open() as stream:
                        rows.extend(csv.DictReader(stream))
                self.assertEqual(len(rows), 18)
                self.assertEqual(sum(row['accepted'] == '0' for row in rows), 2)
                self.assertTrue(all(row['contract'] == 'V227_CLOCK_OBSERVATION_V1' for row in rows))

    def test_disabled_clock_observer_writes_nothing_and_preserves_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_scenario(204, tmp);self.assertTrue(r['parity']);self.assertEqual(r['rows'], 0)
            self.assertFalse((Path(tmp)/'clock_test').exists())


class RecoveryIntegrityTests(unittest.TestCase):
    def test_all_original_native_headers_remain_byte_identical(self):
        baseline = json.loads((ROOT/'baseline_v226_sha256.json').read_text())
        for name, expected in baseline.items():
            if not name.startswith('mt4/Include/'):
                continue
            data = (ROOT/name).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected, name)

    def test_four_demo_real_presets_preserve_guards_and_observation_permissions(self):
        for account in ('Demo', 'Real'):
            for mode in ('Binary', 'Forex'):
                name = f'EURUSD_M5_V229_{mode}_{account}_{"Observe" if mode == "Binary" else "Execute"}_UTC0.set'
                p = ROOT/'mt4/Presets'/name
                v = dict(line.split('=', 1) for line in p.read_text().splitlines() if '=' in line)
                self.assertEqual(v['TradingMode'], '0' if mode == 'Binary' else '1')
                self.assertEqual(v['ForexEnableTrading'], 'false' if mode == 'Binary' else 'true')
                self.assertEqual(v['ForexAllowRealTrading'], 'true' if mode == 'Forex' and account == 'Real' else 'false')
                for key in ('EnableBinaryLearningDialogue', 'BinaryLearningAdviceAffectsSignals', 'ForexEnableAveraging', 'UseValidatedLearning', 'EmbeddedBrokerClockVerified'):
                    self.assertEqual(v[key], 'false', (name, key))
                for key, expected in {'MinimumLockLeadSeconds':'30','MaximumAnalysisStartDelaySeconds':'15','MaximumObservationGapSeconds':'30',
                                      'ForexRiskPercent':'0.5','ForexMaxDailyLossPercent':'2.0','ForexMaxHoldMinutes':'60',
                                      'ForexMinStopLossPips':'6.0','ForexMaxStopLossPips':'30.0','ForexMaxSpreadPips':'1.5',
                                      'ForexMinMarginLevelPercent':'500.0','ForexMinFreeEquityPercent':'50.0','ForexNewsFilter':'true'}.items():
                    self.assertEqual(v[key], expected, (name, key))
                self.assertEqual(p.read_bytes(), (ROOT/'MQL4/Presets'/name).read_bytes())


if __name__ == '__main__':
    unittest.main()
