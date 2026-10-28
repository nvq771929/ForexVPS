"""Tester boundaries, frozen native headers and isolated continuity behavior."""
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
EXPERT=ROOT/'mt4/Experts/EURUSD_M5_Intelligence_V232_PermissionResearch.mq4'

def flatten_expert():
    seen=set()
    def load(name):
        if '/' not in name:name='EURUSD_M5_V224/'+name
        if name in seen:return ''
        seen.add(name);return flatten((ROOT/'mt4/Include'/name).read_text())
    def flatten(text):
        text=re.sub(r'(?<!\\)\\x([0-9A-Fa-f]{4})',lambda m:chr(int(m[1],16)),text).replace('"+"','')
        text=re.sub(r'#include [<"]([^>"]+)[>"]',lambda m:load(m[1]),text)
        text=re.sub(r'^#property.*$','',text,flags=re.M)
        text=re.sub(r'const (\w+) &(\w+)\[\]',r'const std::vector<\1> &\2',text)
        text=re.sub(r'(?<!const )(\w+) &(\w+)\[\]',r'std::vector<\1> &\2',text)
        return re.sub(r'\b(\w+) (\w+)\[\];',r'std::vector<\1> \2;',text)
    sdk=''.join((ROOT/'tests'/p).read_text() for p in ['mql4_shim.hpp','forex_api.hpp','history_api.hpp'])
    sdk+='\nbool fakeTesting=true,fakeOptimization=false;bool IsTesting(){return fakeTesting;}bool IsOptimization(){return fakeOptimization;}double MathRound(double x){return std::round(x);}double MathExp(double x){return std::exp(x);}\n'
    return sdk+flatten(EXPERT.read_text())

HARNESS=r'''
int main(int argc,char**argv){
 filesRoot=argv[1];int scenario=std::stoi(argv[2]);ForexResearchPostLockGapSeconds=std::stoi(argv[3]);ForexResearchMinAtrPips=std::stod(argv[4]);
 fakeNowMs=1767268800000LL;fakeServer="Exness-Demo";
 if(scenario>=100){
  BOConfig c{};BOConfigDefaults(c);BOPrediction e{};
  e.exists=true;e.locked=true;e.targetTime=fakeNowMs/1000;e.candidate.direction=1;e.candidate.setup=1;
  e.candidate.invalidation=1.0992;e.candidate.confirmation=1.1;e.anchor.volatility.atr=.0003;
  e.validation=BO_CONFIRMED;e.action=1;e.lastQuoteMs=fakeNowMs-4000;e.lockedDirection=1;
  fxResearchPostLockGapSeconds=ForexResearchPostLockGapSeconds;bool eligible=false,equal=true;
  if(scenario==101)e.lastQuoteMs=fakeNowMs-5000;
  if(scenario==102)e.lastQuoteMs=fakeNowMs-6000;
  if(scenario==103)e.lastQuoteMs=fakeNowMs+1000;
  if(scenario==104){e.locked=false;e.lastQuoteMs=fakeNowMs-31000;}
  if(scenario==105)e.locked=false;
  if(scenario==106||scenario==107){e.candidate.invalidation=1.10025;e.breachStartMs=fakeNowMs-4000;if(scenario==107)e.lastQuoteMs=fakeNowMs-2000;}
  if(scenario==108){e.locked=false;e.targetTime=fakeNowMs/1000+32;std::vector<BOProbability>p(3);BOLock(e,c,fakeNowMs,true,false,p);}
  else if(scenario==109)eligible=BOEntryAllowed(e,c,fakeNowMs,false);
  else if(scenario==110||scenario==111){if(scenario==111){e.locked=false;e.lastQuoteMs=fakeNowMs-31000;}FXR231CheckQuoteAge(e,c,fakeNowMs);}
  else if(scenario==113){
   fxResearchPostLockGapSeconds=3;unsigned seed=1234567;
   for(int i=0;i<10000;i++){
    seed=seed*1664525u+1013904223u;BOPrediction a=e;a.locked=(seed&1);a.candidate.direction=(seed%3)-1;
    a.lastQuoteMs=fakeNowMs-(seed%37000);a.candidate.invalidation=1.1001+(int(seed%30)-15)*.00001;
    a.breachStartMs=fakeNowMs-(seed%6000);BOPrediction b=a;
    BOObserve(a,c,fakeNowMs,1.1002,1.1003);FXR231Observe(b,c,fakeNowMs,1.1002,1.1003);
    if(std::memcmp(&a,&b,sizeof(a))!=0)equal=false;
    a=e;b=a;BOCheckQuoteAge(a,c,fakeNowMs);FXR231CheckQuoteAge(b,c,fakeNowMs);
    if(std::memcmp(&a,&b,sizeof(a))!=0)equal=false;
   }
  }
  else FXR231Observe(e,c,fakeNowMs,scenario==112?1.0990:1.1002,scenario==112?1.0991:1.1003);
  std::cout<<"{\"canceled\":"<<e.canceled<<",\"reason\":"<<e.reason<<",\"breach_start\":"<<e.breachStartMs
    <<",\"now\":"<<fakeNowMs<<",\"eligible\":"<<eligible<<",\"baseline_equal\":"<<equal<<"}";return 0;
 }
 if(scenario==1)fakeTesting=false;
 if(scenario==2)fakeOptimization=true;
 if(scenario==3)TradingMode=BinaryOption;
 if(scenario==4)ForexAllowRealTrading=true;
 if(scenario==5)ForexNewsFilter=true;
 if(scenario==6)UseValidatedLearning=true;
 if(scenario==7)EnableBinaryLearningDialogue=true;
 if(scenario==8)BinaryLearningAdviceAffectsSignals=true;
 if(scenario==9)EnableEmbeddedContext=true;
 if(scenario==10)fakePeriod=15;
 if(scenario==20)MinimumLockLeadSeconds=31;
 if(scenario==21)RecordReplayInputs=false;
 if(scenario==22)RecordClockObservation=false;
 if(scenario==23)InstanceTag="v230_old_tag";
 int result=OnInit();bool started=fxStarted;int second=-1;
 if(result==0&&scenario>=12&&scenario<=27){
  ZeroMemory(fxEpisode);fxEpisode.exists=true;fxEpisode.locked=true;fxEpisode.targetTime=TimeCurrent();fxEpisode.candidate.direction=1;fxEpisode.candidate.setup=1;
  fxEpisode.candidate.invalidation=1.0992;fxEpisode.candidate.confirmation=1.1;fxEpisode.anchor.volatility.atr=.0003;
  fxEpisode.validation=BO_CONFIRMED;fxEpisode.action=1;fxEpisode.lockedDirection=1;fxEpisode.lockedAction=1;
  fxEpisode.lastQuoteMs=fakeNowMs-4000;boClockBaseMs=fxEpisode.lastQuoteMs;fxLastStarted=TimeCurrent();
  if(scenario==13)FXSend(fxEpisode,fakeNowMs);
  else if(scenario==14){fxEpisode.targetTime-=3;fxEpisode.lastQuoteMs=fakeNowMs;boClockBaseMs=fakeNowMs;FXSend(fxEpisode,fakeNowMs);}
  else{
   if(scenario==15)fakeBid=1.0990;
   if(scenario==17)fakeTradeBusy=true;
   if(scenario==18){FXDayGuard(TimeCurrent());fakeEquity=9700;}
   if(scenario==19)fakeAsk=1.1004;
   if(scenario==24)connected=false;
   if(scenario==25){fakeTradingAllowed=false;fakeEAAllowed=false;}
   if(scenario==26)fakeMarketAllowed=false;
   int diagnosticLease=INVALID_HANDLE;
   if(scenario==27){fakeMarketAllowed=false;diagnosticLease=FileOpen(fxRoot+"\\research_permissions_v232.csv",FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI,',');}
   OnTick();
   if(diagnosticLease!=INVALID_HANDLE)FileClose(diagnosticLease);
  }
 }
 string status=fxStatus;if(result==0)OnDeinit(0);
 if(scenario==11){second=OnInit();OnDeinit(0);}
 int files=0;for(auto&p:std::filesystem::recursive_directory_iterator(filesRoot))if(p.is_regular_file())files++;
 std::cout<<"{\"init\":"<<result<<",\"started\":"<<started<<",\"gap\":"<<fxResearchPostLockGapSeconds
   <<",\"fresh\":"<<fxConfig.quoteFreshSeconds<<",\"lag\":"<<fxConfig.boundaryLagSeconds<<",\"files\":"<<files
   <<",\"send_calls\":"<<fakeSendCalls<<",\"status\":\""<<status<<"\",\"second_init\":"<<second<<"}";
}
'''

def fnv(text):
    n=2166136261
    for b in text.encode('ascii'):n=((n^b)*16777619)&0xffffffff
    return n

class ContinuityResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();p=Path(cls.tmp.name);cls.binary=p/'expert'
        (p/'expert.cpp').write_text(flatten_expert()+HARNESS)
        proc=subprocess.run(['g++','-std=c++17','-O1',str(p/'expert.cpp'),'-o',str(cls.binary)],capture_output=True,text=True)
        if proc.returncode:raise RuntimeError(proc.stderr)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def run_case(self,scenario=0,gap=3,minimum=3):
        with tempfile.TemporaryDirectory() as folder:
            proc=subprocess.run([str(self.binary),folder,str(scenario),str(gap),str(minimum)],capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr)
            result=json.loads(proc.stdout);paths=list(Path(folder).rglob('research_config_v232.csv'))
            result['metadata']=paths[0].read_text() if paths else None
            permission=list(Path(folder).rglob('research_permissions_v232.csv'));result['permissions']=list(csv.DictReader(io.StringIO(permission[0].read_text()))) if permission else []
        return result
    def test_rejects_live_demo_chart_before_writes(self):
        r=self.run_case(1);self.assertEqual(r['init'],2);self.assertEqual(r['files'],0);self.assertEqual(r['send_calls'],0)
    def test_rejects_unsafe_modes_and_non_m5(self):
        for case in range(2,11):
            with self.subTest(case=case):
                r=self.run_case(case);self.assertEqual(r['init'],2);self.assertEqual(r['files'],0)
    def test_rejects_nonfixed_atr_and_invalid_gap(self):
        for minimum in [0,1.5,3.1,'nan','inf']:
            with self.subTest(minimum=minimum):self.assertEqual(self.run_case(minimum=minimum)['init'],2)
        for gap in [-1,0,2,31,300]:
            with self.subTest(gap=gap):self.assertEqual(self.run_case(gap=gap)['init'],2)
    def test_requires_frozen_native_configuration_logging_and_new_tag(self):
        for case in [20,21,22,23]:
            with self.subTest(case=case):self.assertEqual(self.run_case(case)['init'],2)
    def test_all_policy_values_have_distinct_verified_metadata(self):
        policies=set()
        for gap in [3,5,10,15,30]:
            r=self.run_case(gap=gap);self.assertEqual(r['init'],0);self.assertEqual(r['gap'],gap);self.assertEqual(r['fresh'],3);self.assertEqual(r['lag'],2)
            row=list(csv.DictReader(io.StringIO(r['metadata'])))[0]
            self.assertEqual(int(row['requested_post_lock_gap_s']),gap);self.assertEqual(int(row['applied_post_lock_gap_s']),gap)
            self.assertEqual(row['native_config_hash'],'2669644079');self.assertEqual(row['entry_quote_fresh_s'],'3');self.assertEqual(row['pre_lock_gap_s'],'30');self.assertEqual(row['entry_lag_s'],'2')
            self.assertEqual(row['news_filter'],'0');self.assertEqual(row['real_allowed'],'0');self.assertEqual(row['quote_recording'],'1');self.assertEqual(row['clock_recording'],'1')
            payload=f"V231_POSTLOCK_CONTINUITY_V1|2669644079|{gap}|3|30|2"
            self.assertEqual(fnv(payload),int(row['policy_hash']));policies.add(row['policy_hash'])
            self.assertEqual(fnv('|'.join(row[k] for k in ['tag','native_config_hash','requested_post_lock_gap_s','applied_post_lock_gap_s','policy_hash'])),int(row['checksum']))
        self.assertEqual(len(policies),5)
    def test_duplicate_run_preserves_original_metadata(self):
        r=self.run_case(11);self.assertEqual(r['init'],0);self.assertNotEqual(r['second_init'],0);self.assertTrue(r['metadata'])
    def test_gap3_adapter_matches_native_over_ten_thousand_states(self):self.assertTrue(self.run_case(113)['baseline_equal'])
    def test_locked_gap_boundary_uses_separate_limit(self):
        self.assertTrue(self.run_case(100,3)['canceled']);self.assertFalse(self.run_case(100,5)['canceled'])
        self.assertFalse(self.run_case(101,5)['canceled']);self.assertTrue(self.run_case(102,5)['canceled'])
    def test_prelock_gap_and_backward_clock_are_unchanged(self):
        self.assertTrue(self.run_case(103,30)['canceled']);self.assertEqual(self.run_case(103,30)['reason'],27)
        self.assertTrue(self.run_case(104,30)['canceled']);self.assertFalse(self.run_case(105,3)['canceled'])
    def test_unobserved_interval_never_counts_as_persistent_breach(self):
        r=self.run_case(106,10);self.assertFalse(r['canceled']);self.assertEqual(r['breach_start'],r['now'])
        self.assertEqual(self.run_case(107,10)['reason'],11)
    def test_deep_structural_break_still_cancels(self):self.assertEqual(self.run_case(112,10)['reason'],11)
    def test_lock_freshness_stays_three_seconds(self):self.assertEqual(self.run_case(108,30)['reason'],9)
    def test_quote_age_checker_uses_postlock_limit_only(self):
        self.assertTrue(self.run_case(110,3)['canceled']);self.assertFalse(self.run_case(110,5)['canceled']);self.assertTrue(self.run_case(111,30)['canceled'])
    def test_entry_freshness_and_two_second_deadline_are_unchanged(self):
        self.assertFalse(self.run_case(109,30)['eligible'])
        for case in [13,14]:
            r=self.run_case(case,30);self.assertEqual(r['send_calls'],0);self.assertEqual(r['status'],'NATIVE_ENTRY_NOT_ALLOWED')
    def test_full_expert_scope_reaches_mock_broker_only_when_gap_allowed(self):
        blocked=self.run_case(12,3);allowed=self.run_case(12,5)
        self.assertEqual(blocked['send_calls'],0);self.assertEqual(allowed['send_calls'],1)
    def test_structure_permission_spread_and_daily_risk_still_block(self):
        for case in [15,17,18,19]:
            with self.subTest(case=case):self.assertEqual(self.run_case(case,10)['send_calls'],0)

    def test_each_failed_native_predicate_is_identified_without_allowing_order(self):
        for case,trigger,value in [(24,'IS_CONNECTED','0.000000'),(25,'IS_TRADE_ALLOWED','0.000000'),(17,'IS_TRADE_CONTEXT_BUSY','1.000000'),(26,'MODE_TRADEALLOWED','0.000000')]:
            with self.subTest(case=case):
                r=self.run_case(case,10);self.assertEqual(r['send_calls'],0);self.assertEqual(r['status'],'TERMINAL_TRADING_UNAVAILABLE')
                self.assertEqual(len(r['permissions']),1);row=r['permissions'][0]
                self.assertEqual(row['trigger'],trigger);self.assertEqual(row['observed_value'],value)
                self.assertEqual(row['native_config_hash'],'2669644079');self.assertEqual(row['post_lock_gap_s'],'10')
                if case==25:self.assertEqual(row['ea_trade_allowed'],'0')
    def test_allowed_entry_produces_no_failure_diagnostic(self):
        r=self.run_case(12,10);self.assertEqual(r['send_calls'],1);self.assertEqual(r['permissions'],[])
    def test_no_diagnostic_for_nonentry_risk_or_live_rejection(self):
        for case in [0,1,18]:self.assertEqual(self.run_case(case,10)['permissions'],[])
    def test_diagnostic_write_failure_does_not_bypass_failed_guard(self):
        r=self.run_case(27,10);self.assertEqual(r['send_calls'],0);self.assertEqual(r['status'],'TERMINAL_TRADING_UNAVAILABLE');self.assertEqual(r['permissions'],[])

class BundleTests(unittest.TestCase):
    def test_v231_continuity_adapter_is_preserved(self):
        for name,digest in json.loads((ROOT/'BASELINE_V231_ADAPTER.json').read_text()).items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest)
    def test_forty_delivered_headers_preserved(self):
        baseline=json.loads((ROOT/'BASELINE_V229_HEADERS.json').read_text());self.assertEqual(len(baseline),40)
        for name,digest in baseline.items():self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest)
    def test_adapter_changes_only_two_continuity_expressions(self):
        native=(ROOT/'mt4/Include/EURUSD_M5_V224/Validation.mqh').read_text()
        expected=native[native.index('void BOObserve('):native.rindex('#endif')]
        actual=(ROOT/'mt4/Include/EURUSD_M5_V231_Research/Continuity.mqh').read_text()
        actual=actual[actual.index('void FXR231Observe('):actual.rindex('#endif')]
        actual=actual.replace('FXR231Observe(','BOObserve(').replace('FXR231CheckQuoteAge(','BOCheckQuoteAge(')
        actual=actual.replace('(e.locked && gap>fxResearchPostLockGapSeconds*1000)','(e.locked && gap>c.quoteFreshSeconds*1000)')
        actual=actual.replace('int limit=e.locked ? fxResearchPostLockGapSeconds : c.maximumObservationGapSeconds;','int limit=e.locked ? c.quoteFreshSeconds : c.maximumObservationGapSeconds;')
        self.assertEqual(actual,expected)
    def test_canonical_and_install_mirror_match(self):
        a=ROOT/'mt4';b=ROOT/'MQL4'
        self.assertEqual({p.relative_to(a):p.read_bytes() for p in a.rglob('*') if p.is_file()},{p.relative_to(b):p.read_bytes() for p in b.rglob('*') if p.is_file()})
    def test_presets_change_only_gap_identity_and_logging_from_v230_baseline(self):
        names=set(re.findall(r'^input\s+\w+\s+(\w+)\s*=',EXPERT.read_text(),re.M));presets=sorted((ROOT/'mt4/Presets').glob('*.set'))
        self.assertEqual(len(presets),1);tags=set();gaps=set();common=None
        for path in presets:
            pairs=[x.split('=',1) for x in path.read_text().splitlines() if x];data=dict(pairs)
            self.assertEqual(len(pairs),len(data));self.assertEqual(set(data),names)
            self.assertEqual(float(data['ForexResearchMinAtrPips']),3);self.assertEqual(data['RecordReplayInputs'],'true');self.assertEqual(data['RecordClockObservation'],'true')
            self.assertTrue(data['InstanceTag'].startswith('v232_'));tags.add(data.pop('InstanceTag'));gaps.add(int(data.pop('ForexResearchPostLockGapSeconds')))
            if common is None:common=data
            self.assertEqual(data,common)
        self.assertEqual(gaps,{10});self.assertEqual(len(tags),1)

if __name__=='__main__':unittest.main()
