"""Actual V208 MQL adapter under a C++ MT4 API shim, including packed logs.

This executes source semantics and native-layout journaling. It does NOT claim
a MetaEditor compile or a Windows MT4 runtime test.
"""
import ast
import csv
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from intelligence.demo_learning import (LOGIC,MODEL_COLUMNS,POLICY_COLUMNS,collect,update)
from intelligence.native_ledger import read_directory
from tests.test_demo_learning import policy
from tests.fixtures import START,sr_bars

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('g++'),'g++ required for native source harness')
class NativeHarness:
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();folder=Path(cls.tmp.name);seen=set();inc=ROOT/'mt4/Include/EURUSD_M5_V224'
        def flatten(text):
            text=re.sub(r'(?<!\\)\\x([0-9A-Fa-f]{4})',lambda m:chr(int(m[1],16)),text).replace('"+"','')
            text=re.sub(r'#include [<"](?:EURUSD_M5_V224/)?([^>"]+)[>"]',lambda m:load(m[1]),text)
            text=re.sub(r'^#property.*$','',text,flags=re.M)
            text=re.sub(r'const (\w+) &(\w+)\[\]',r'const std::vector<\1> &\2',text)
            text=re.sub(r'(?<!const )(\w+) &(\w+)\[\]',r'std::vector<\1> &\2',text)
            return re.sub(r'\b(\w+) (\w+)\[\];',r'std::vector<\1> \2;',text)
        def load(name):
            if name in seen:return ''
            seen.add(name);text=(inc/name).read_text()
            if name=='Types.mqh':
                text=text.replace('struct BOConfig {','#pragma pack(push,1)\nstruct BOConfig {')
                text=text.replace('void BOConfigDefaults(','#pragma pack(pop)\nvoid BOConfigDefaults(')
            return flatten(text)
        api=(ROOT/'tests/history_api.hpp').read_text()
        source=flatten((ROOT/'mt4/Experts/EURUSD_M5_Intelligence_V228.mq4').read_text())
        shim=(ROOT/'tests/mql4_shim.hpp').read_text()+'\n'+(ROOT/'tests/forex_api.hpp').read_text()
        api+='\nbool fakeTesting=false;bool fakeOptimization=false;bool IsTesting(){return fakeTesting;} bool IsOptimization(){return fakeOptimization;}\ndouble MathRound(double v){return std::round(v); } double MathExp(double v){return std::exp(v);}\n'
        cls.native_source=source;cls.native_api=api;cls.native_shim=shim
        main=r'''
// Test-only peer replies. These exercise transport semantics, not a qualified market model.
void FakeAdvisorReply(int mode){
 if(boAdvisorSequence<=0)return;
 string file=boAdvisorFolder+"\\reply_"+BOAdvisorStem(boAdvisorSequence)+".csv";
 std::ofstream out(nativePath(file));
 if(mode==45){out<<"schema,broken\n1,";return;}
 string model(64,'a');int decision=mode==41 ? 1:-1;int valid=mode==39 ? 0:1;
 long long requestUtc=boAdvisorRequestMs-(long long)fakeBrokerUTCOffset*1000;
 std::vector<string> cells={"1",BO_ADVISOR_CONTRACT,boSession,IntegerToString(boAdvisorSequence+(mode==38 ? 1:0)),
 IntegerToString(boDemoConfig),IntegerToString(boDemoFeed),IntegerToString(boDemoPolicy),IntegerToString(boAdvisorTransportPolicy),
 IntegerToString(boAdvisorStart),IntegerToString(boAdvisorStart+300),IntegerToString(boAdvisorStart+300+boDemoHorizon*300),
 IntegerToString(boDemoHorizon),IntegerToString(boAdvisorDirection),IntegerToString(boAdvisorSetup),IntegerToString(boAdvisorRegime),
 IntegerToString(boAdvisorRequestMs),IntegerToString(boAdvisorDeadline),IntegerToString(boAdvisorSnapshotChecksum),
 IntegerToString(decision),"700000",model,IntegerToString(requestUtc-86400000),IntegerToString(requestUtc-3600000),
 IntegerToString(fakeNowMs-(long long)fakeBrokerUTCOffset*1000),IntegerToString(requestUtc-1000),IntegerToString(valid)};
 string text="";for(size_t i=0;i<cells.size();i++)text+=(i ? "|":"")+cells[i];cells.push_back(IntegerToString(BOHashText(text)));
 out<<"schema,contract,session,sequence,config_hash,feed_hash,policy_hash,transport_policy_hash,analysis_start,target,expiry,horizon,direction,setup,regime,requested_ms,deadline_ms,snapshot_checksum,decision,probability_ppm,model_id,trained_cutoff_utc_ms,model_created_utc_ms,response_utc_ms,qualification_cutoff_utc_ms,validated,checksum\n";
 for(size_t i=0;i<cells.size();i++)out<<(i ? ",":"")<<cells[i];out<<"\n";
}
long LegacyV216ContextUTC(long observedMs) {
   if(IsTesting() || !boContextClockValid || boLastTickMs<=0 || observedMs<boLastTickMs || observedMs-boLastTickMs>3000)return 0;
   long utcMs=observedMs-(long)boContextOffset*1000;
   if(MathAbs((double)(utcMs-(long)TimeGMT()*1000))>5000)return 0;
   return utcMs;
}
int main(int argc,char**argv){
 filesRoot=argv[1];if(argc>4)fakeTesting=std::stoi(argv[4])!=0;if(argc>5)fakeBrokerUTCOffset=std::stol(argv[5]);if(argc>6)InstanceTag=argv[6];int mode=std::stoi(argv[2]);DemoExpiryMinutes=std::stoi(argv[3]);
 long long start;int count;std::cin>>start>>count;
 for(int i=0;i<count;i++){FakeBar b;std::cin>>b.time>>b.open>>b.high>>b.low>>b.close>>b.ticks;closedBars.push_back(b);addBar(b);}

 if(mode==22 || mode==23){
  BOContextReset();boClockBaseMs=0;
  long long seed=start*1000;
  if(mode==23)seed=(seed/4294967296LL+1)*4294967296LL-4000;
  auto tick=[&](long long value){fakeNowMs=value;long now=0;BOClockTick(TimeCurrent(),now);BOContextClockTick(now);return BOContextUTC(now)>0;};
  fakeNowMs=seed;bool initial=BOContextUTC(fakeNowMs)>0;
  bool a=tick(seed),b=tick(seed+1000),c=tick(seed+2000);long long base=fakeNowMs;
  long utc=TimeGMT();boContextCreated=utc-100;boContextExpires=utc+3600;boContextRows=1;
  boContextKind[0]="SESSION";boContextLabel[0]="TOKYO";boContextStart[0]=utc-100;boContextEnd[0]=utc+3600;
  std::cout<<"{\"initial\":"<<initial<<",\"warmup\":["<<a<<","<<b<<","<<c<<"],\"quiet\":[";
  std::vector<long long>ages={4900,18400,60000,900000};std::vector<bool>legacyQuiet;
  for(int i=0;i<4;i++){fakeNowMs=base+ages[i];long mapped=BOContextUTC(BONowMs());legacyQuiet.push_back(LegacyV216ContextUTC(BONowMs())>0);if(i)std::cout<<",";std::cout<<(mapped>0 && BOContextMask(mapped/1000)==1);}
  fakeNowMs=base+900001;bool expired=BOContextUTC(BONowMs())==0;
  bool r1=tick(base+901000),r2=tick(base+902000),r3=tick(base+903000);
  fakePCUTCJumpSeconds=30;bool jump=BOContextUTC(BONowMs())==0;fakePCUTCJumpSeconds=0;
  bool j1=tick(base+904000),j2=tick(base+905000),j3=tick(base+906000);
  fakeBrokerUTCOffset+=3600;
  bool d1=tick(base+907000),d2=tick(base+908000),d3=tick(base+909000);
  fakeTesting=true;bool tester=BOContextUTC(BONowMs())==0;
  std::cout<<"],\"legacy_quiet\":[";for(int i=0;i<4;i++){if(i)std::cout<<",";std::cout<<legacyQuiet[i];}
  std::cout<<"],\"expired\":"<<expired<<",\"recalibrated\":["<<r1<<","<<r2<<","<<r3<<"],\"pc_jump_unknown\":"<<jump
   <<",\"pc_recovery\":["<<j1<<","<<j2<<","<<j3<<"],\"offset_change\":["<<d1<<","<<d2<<","<<d3<<"],\"tester_unknown\":"<<tester<<"}";
  return 0;
 }
 if(mode==30 || mode==31){PanelFontSize=14;DiagnosticMode=true;}
 if(mode==32)RecordReplayInputs=false;
 if(mode==33)EnableAlerts=false;
 if(mode>=34 && mode<=49){EnableBinaryLearningDialogue=true;BinaryLearningAdviceAffectsSignals=mode!=34 && mode!=49;}
 if(mode>=50 && mode<=57){EnableEmbeddedContext=true;EmbeddedBrokerClockVerified=mode!=51;
  EmbeddedBrokerUTCOffsetMinutes=mode==52 ? 1:0;EmbeddedBootstrapM5Bars=mode==53 ? 0:2400;}
 if(mode==44)CompactTesterLogs=false;
 if(mode==42)EnableDemoSignals=false;
 if(mode==26)fakeManualWriteFailure=true;
 if(mode==29)fakeManualSaveDelayMs=5000;
 if(mode==6)EnableDemoSignals=false;
 if(mode==7 || mode==8){m5Hole=true;m1Hole=true;}
 if(mode==19)fakeOptimization=true;
 if(mode==17){AllowSR1=false;AllowTP1=false;AllowBR1=false;}
 fakeNowMs=((mode==20 || mode==21) ? start+(mode-19)*1000 : start-100)*1000;int initialized=OnInit();
 if(initialized!=0){std::cout<<"{\"init\":"<<initialized<<"}";OnDeinit(0);return 0;}

 if(mode==54 || mode==55 || mode==56 || mode==57){
  long before=boEmbedded.m5.count;
  if(mode==55){boState.current.exists=true;boState.current.entered=false;boState.current.canceled=false;
   boState.current.targetTime=TimeCurrent()+60;BOEmbeddedPump(boRoot,boSession,boState,boConfig,(long)fakeNowMs);}
  if(mode==56 && boHistoryReady){boHistoryBars[5].high+=.00001;BOEmbeddedPump(boRoot,boSession,boState,boConfig,(long)fakeNowMs);}
  if(mode==57){BOEmbeddedPump(boRoot,boSession,boState,boConfig,(long)fakeNowMs);}
  std::cout<<"{\"init\":0,\"ready\":"<<boEmbedded.snapshot.ready<<",\"m5\":"<<boEmbedded.m5.count
   <<",\"before\":"<<before<<",\"asof\":"<<boEmbedded.snapshot.asofMs<<",\"m15\":"<<boEmbedded.m15.count
   <<",\"h1\":"<<boEmbedded.h1.count<<",\"status\":\""<<BOEmbeddedDisplayStatus(fakeNowMs)<<"\",\"stale\":\""
   <<BOEmbeddedDisplayStatus(fakeNowMs+600000)<<"\"}";OnDeinit(0);return 0;
 }
 if(mode==20 || mode==21){std::cout<<"{\"init\":0,\"learning_status\":\""<<boLearnStatus<<"\",\"bad\":"<<boLearnBad
 <<",\"manual_total\":"<<boManualTotal<<",\"manual_losses\":"<<boManualLosses<<",\"manual_missing\":"<<boManualMissing<<",\"manual_pending\":"<<boManualPending<<",\"manual_error\":"<<boManualError
 <<",\"advanced_status\":\""<<boAdvStatus<<"\",\"advanced_id\":"<<boAdvId<<",\"models\":"<<boLearnCount<<",\"wins\":"<<boPaperWins<<"}";OnDeinit(0);return 0;}
 BOConfig c{};BOConfigDefaults(c);std::vector<BOBar>b;
 for(auto &z:closedBars)b.push_back({z.time,z.open,z.high,z.low,z.close,z.ticks});
 BOAnchor a{};BOBuildMarket(b,count,c,a);BOCandidate f{};BOFormCandidate(a,c,f);
 bool heldAfterCancel=false;double reference=f.confirmation+f.direction*.00001;int end=(mode==8 ? 600:300)+DemoExpiryMinutes*60+3;
 for(int sec=0;sec<=end;sec++){
  fakeNowMs=(start+sec)*1000+fakeSaveElapsedMs;
  if(mode==10)fakeExternalReplayReader=true;
  if(mode==12 && sec==200)fakeFailReplayOnce=true;
  if(mode==8 && sec==300){m5Hole=false;m1Hole=false;}
  if(sec>0 && sec%300==0)addBar({start+sec-300,reference,reference+.0002,reference-.0002,reference,10});
  if(mode==3 && sec==350){OnDeinit(0);continue;}
  if(mode==3 && sec>350 && sec<400)continue;
  if(mode==3 && sec==400){if(OnInit()!=0)return 3;}
  if(mode==1 && sec==200)boState.paused=true;
  if(mode==27 && sec==275)OnChartEvent(CHARTEVENT_OBJECT_CLICK,0,0,"BO_V222_PAUSE");
  if(mode==28 && sec==280){OnDeinit(0);continue;}
  if(mode==28 && sec>280 && sec<290)continue;
  if(mode==28 && sec==290){if(OnInit()!=0)return 3;}
  fakeBid=reference;
  if(f.setup==3 && mode==16)fakeBid=f.direction==1 ? f.retestHigh+.0001 : f.retestLow-.0001;
  if(f.setup==3 && mode!=16 && sec==0)fakeBid=f.direction==1 ? f.retestHigh+.0001 : f.retestLow-.0001;
  if(f.setup==3 && mode!=16 && sec==1)fakeBid=f.direction==1 ? a.structure.preResistance.high : a.structure.preSupport.low;
  int expiry=300+DemoExpiryMinutes*60;
  if(sec==expiry){if(mode==13 || mode==24)fakeBid-=f.direction*.0001;else if(mode!=14)fakeBid+=f.direction*.0001;}
  if(mode==5 && sec==280)fakeBid=f.invalidation-f.direction*.001;
  if(mode==18 && sec==269)fakeBid+=f.direction*.00002;
  if(mode==40 && sec>=267 && sec<300)fakeBid+=f.direction*a.volatility.atr*.30;
  if((mode>=36 && mode<=45 && sec==(mode==37 ? 269:260)) || (mode==46 && sec==230) ||
     (mode==47 && sec==260) || (mode==48 && sec==269) || (mode==49 && sec==260))FakeAdvisorReply(mode);
  if(mode==47 && sec==267)boAdvisorStorageBad=true;
  fakeAsk=fakeBid+.0001;
  bool skip=((mode==9 || mode==24) && sec>=269 && sec<=271) || (mode==18 && sec==268) || (mode==2 && sec>=264 && sec<=269) || (mode==4 && sec>=expiry && sec<=expiry+3) || (mode==25 && sec>=300 && sec<=303) || (mode==30 && sec>=300 && sec<=301) || (mode==31 && sec>=300 && sec<=302);
  if(!skip)OnTick();if(!fakeTesting)OnTimer();
  if(boState.current.canceled && BOManualOwns((long)boState.current.analysisStart) && sec<300)
     heldAfterCancel=BOManualHeadline(BONowMs()).find("WAIT")==string::npos;
 }
 long long sequence=boState.sequence;OnTick();bool dedup=sequence==boState.sequence;
 long long beforeHash=boState.configHash;bool healthy=boHealthy;bool hasPending=boState.pending[0].used;
 int signals=0;string n;long long h=FileFindFirst(boRoot+"\\event_*.bin",n);
 if(h!=INVALID_HANDLE){do{BORuntimeState state{};BOEvent e{};if(!BOReadLedger(boRoot+"\\"+n,state,e))return 4;
  if(e.kind==BO_ENTRY_EVENT && e.signal)signals++;
 }while(FileFindNext(h,n));FileFindClose(h);}
 auto contains=[&](const string &text){for(auto &item:objectStrings)if(item.second.find(text)!=string::npos)return true;return false;};
 int newsAlerts=0;for(auto &text:alertTexts)if(text.find("LICH TIN QUAN SAT | ")==0)newsAlerts++;
 int officialAlerts=0;bool alertContract=true;
 for(auto &text:alertTexts)if(text.find("| GIU ")!=string::npos){officialAlerts++;alertContract=alertContract && text.find("EURUSD "+BOActionName(f.direction)+" | GIU "+IntegerToString(DemoExpiryMinutes)+" PHUT ("+IntegerToString(DemoExpiryMinutes/5)+" M5)\nVao ")==0 && text.find(" | Het han ")!=string::npos && text.find(" | Broker\n")!=string::npos;}
 bool holdLabel=contains("GIU "+IntegerToString(DemoExpiryMinutes)+" PHUT ("+IntegerToString(DemoExpiryMinutes/5)+" M5)");
 string status=boLearnStatus;
 std::cout<<"{\"embedded_status\":\""<<BOEmbeddedDisplayStatus(BONowMs())<<"\",\"embedded_m5\":"<<boEmbedded.m5.count<<",\"embedded_bootstrap\":"<<boEmbeddedBootstrapCount<<",\"copy_requests\":"<<copyRequests<<",\"advisor_requests\":"<<boAdvisorSequence<<",\"advisor_status\":\""<<boAdvisorStatus<<"\",\"news_alerts\":"<<newsAlerts<<",\"tester_ticks\":"<<boTesterTicks<<",\"tester_anchors\":"<<boTesterAnchors
 <<",\"manual_total\":"<<boManualTotal<<",\"manual_wins\":"<<boManualWins<<",\"manual_losses\":"<<boManualLosses<<",\"manual_ties\":"<<boManualTies<<",\"manual_missing\":"<<boManualMissing<<",\"manual_pending\":"<<boManualPending<<",\"manual_error\":"<<boManualError
 <<",\"manual_ui_hold\":"<<holdLabel<<",\"alert_contract\":"<<alertContract<<",\"panel_height\":"<<objectIntegers[{"BO_V222_BACKGROUND",OBJPROP_YSIZE}]
 <<",\"manual_withheld\":"<<boManualWithheld
 <<",\"manual_held_after_cancel\":"<<heldAfterCancel<<",\"official_alerts\":"<<officialAlerts
 <<",\"reference_entries\":"<<boTesterEntries<<",\"dash_signals\":"<<boPaperSignals
 <<",\"dash_open\":"<<boPaperOpen<<",\"dash_wins\":"<<boPaperWins<<",\"dash_losses\":"<<boPaperLosses
 <<",\"dash_ties\":"<<boPaperTies<<",\"dash_missing\":"<<boPaperMissing
 <<",\"history_status\":\""<<boHistoryStatus<<"\",\"tester_training_help\":"<<contains("Sau Tester: chay TRAIN-HISTORY.CMD")
 <<",\"live_learning_help\":"<<contains("CHUA CO - CHAY START-DEMO-LEARNING")
 <<",\"tester_time\":"<<contains("Gio mo phong:")<<",";
 OnDeinit(0);
 int restore=-1;if(mode==11){DemoExpiryMinutes=10;restore=OnInit();OnDeinit(0);}
 std::cout<<"\"init\":0,\"input_sequence\":"<<boInputSequence<<",\"signals\":"<<signals<<",\"healthy\":"<<healthy<<",\"dedup\":"<<dedup
 <<",\"pending\":"<<hasPending<<",\"learning_status\":\""<<status<<"\",\"changed_policy_init\":"<<restore<<"}";
}
'''
        code=shim+api+source+main;(folder/'demo.cpp').write_text(code)
        cls.binary=folder/'demo'
        proc=subprocess.run(['g++','-std=c++17','-O1',str(folder/'demo.cpp'),'-o',str(cls.binary)],capture_output=True,text=True)
        if proc.returncode:raise RuntimeError(proc.stderr)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def execute(self,root,mode=0,direction=1,horizon=1,model=None,advanced=None,factory=sr_bars,testing=False,context_schedule=None,utc_offset=0,instance_tag='v222_demo'):
        source=Path(root)/('BO_V2/'+instance_tag+('_TESTER' if testing else '')+'_EURUSD');source.mkdir(parents=True,exist_ok=True)
        if context_schedule is not None:(source/'context_schedule_v216.csv').write_bytes(context_schedule)
        if advanced:
            from intelligence.advanced_learning import export
            from intelligence.signal_features import NAMES
            count=len(NAMES);asof=START-200
            m=dict(model_id=asof*1000+901,created=asof,phase='OBSERVE',intercept=-2.,
                mean=[0.]*count,scale=[1.]*count,weight=[0.]*count,low=[-1000.]*count,high=[1000.]*count)
            if isinstance(advanced,dict):m.update(advanced)
            export(source,policy(horizon),asof,m)
            path=source/'advanced_model_v207.csv'
            if advanced=='stale':path.write_text(path.read_text().replace(str(asof+86400),str(START-101)))
            if advanced=='wrong_feed':
                p=policy(horizon);path.write_text(path.read_text().replace(str(p['feed_hash']),str(p['feed_hash']+1)))
            if advanced=='truncated':path.write_text('\n'.join(path.read_text().splitlines()[:-1])+'\n')
        if model:
            p=policy(horizon);asof=START-200
            common=dict(schema=1,source='MT4_SIMULATED',logic=LOGIC,config_hash=p['config_hash'],feed_hash=p['feed_hash'],
                policy_hash=p['policy_hash'],asof=asof,expires=asof+86400,row_count=1,reserved=0)
            meta=dict(common,model_id=0,setup=0,direction=0,regime=0,horizon=horizon,decision=0,p_win=.5,n_train=0,n_test=0,atr_min=0,atr_max=0,validated=0)
            row=dict(common,model_id=1,setup=1,direction=direction,regime=1,horizon=horizon,decision=-1,p_win=.3,
                n_train=200,n_test=100,atr_min=3,atr_max=30,validated=1)
            if model=='stale':meta['expires']=row['expires']=START-101
            if model=='wrong_feed':meta['feed_hash']=row['feed_hash']=1
            if model=='truncated':rows=[meta]
            else:rows=[meta,row]
            with (source/'learning_model_v207.csv').open('w',newline='') as stream:
                w=csv.DictWriter(stream,fieldnames=MODEL_COLUMNS);w.writeheader();w.writerows(rows)
        bars=factory(direction);text=f'{START} {len(bars)}\n'+'\n'.join(f'{b.time} {b.open:.17g} {b.high:.17g} {b.low:.17g} {b.close:.17g} {b.ticks}' for b in bars)
        proc=subprocess.run([str(self.binary),str(root),str(mode),str(horizon*5),str(int(testing)),str(utc_offset),instance_tag],input=text,capture_output=True,text=True,check=True)
        return json.loads(proc.stdout),source

class DemoNativeTests(NativeHarness,unittest.TestCase):
    def test_published_call_and_put_simulate_win_without_manual_execution(self):
        for d in (1,-1):
            with self.subTest(direction=d),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,direction=d)
                self.assertEqual(result['init'],0);self.assertEqual(result['signals'],1);self.assertTrue(result['dedup'])
                snap=collect(source);self.assertEqual(len(snap['papers']),1);self.assertEqual(snap['papers'][0]['status'],'WIN')
                report=update(source);self.assertEqual(report['summary']['wins'],1)
                self.assertEqual(report['available_closed_reference_labels'],1)
                self.assertTrue((source/'paper_trades_v207.csv').is_file())
                read_directory(source,LOGIC)  # actual shim records match native POD/FNV

    def test_selected_5_10_15_minute_labels_do_not_become_three_trades(self):
        for h in (1,2,3):
            with self.subTest(horizon=h),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,horizon=h)
                self.assertEqual(result['signals'],1)
                rows=collect(source)['papers'];self.assertEqual(len(rows),1)
                self.assertEqual(rows[0]['horizon'],h);self.assertEqual(rows[0]['status'],'WIN')

    def test_loss_and_tie_are_kept_separate(self):
        for mode,status in ((13,'LOSS'),(14,'TIE')):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,mode=mode)
                self.assertEqual(collect(source)['papers'][0]['status'],status)

    def test_pause_stale_quote_and_preentry_cancel_do_not_score_wins(self):
        for mode in (1,2,5):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,mode=mode)
                self.assertEqual(result['signals'],0)
                self.assertFalse(any(x['status']=='WIN' for x in collect(source)['papers']))

    def test_missing_expiry_is_unavailable_not_loss_or_interpolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,mode=4)
            self.assertEqual(result['signals'],1)
            self.assertEqual(collect(source)['papers'][0]['status'],'UNAVAILABLE')
            r=update(source);self.assertEqual(r['summary']['unavailable'],1)
            self.assertEqual(r['summary']['losses'],0);self.assertEqual(r['available_closed_reference_labels'],0)

    def test_restart_retains_open_paper_trade_and_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,mode=3)
            self.assertEqual(result['signals'],1)
            self.assertEqual(len(collect(source)['papers']),1)
            self.assertEqual(collect(source)['papers'][0]['status'],'WIN')

    def test_validated_block_still_collects_separate_reference_for_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,model='block')
            self.assertEqual(result['signals'],0)
            snap=collect(source);self.assertEqual(len(snap['papers']),0)
            self.assertEqual(len(snap['references']),1);self.assertEqual(snap['references'][0]['status'],'WIN')

    def test_stale_wrong_feed_and_truncated_model_cannot_publish(self):
        for model in ('stale','wrong_feed','truncated'):
            with self.subTest(model=model),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,model=model)
                self.assertEqual(result['signals'],0)

    def test_policy_change_requires_new_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,mode=11)
            self.assertNotEqual(result['changed_policy_init'],0)

    def test_corrupt_latest_journal_is_not_used_for_learning(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(tmp)
            latest=sorted(source.glob('event_*.bin'))[-1];latest.write_bytes(latest.read_bytes()[:-1])
            with self.assertRaises(ValueError):update(source)
            self.assertFalse((source/'learning_model_v207.csv').is_file())

    def test_companion_model_loads_back_and_summary_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(tmp)
            update(source)
            with (source/'learning_model_v207.csv').open() as s:rows=list(csv.DictReader(s))
            self.assertEqual(len(rows),2);self.assertEqual(rows[1]['decision'],'0')
            self.assertEqual(rows[1]['validated'],'0')
            restored,_=self.execute(tmp,mode=20)
            self.assertEqual(restored['init'],0);self.assertFalse(restored['bad'])
            self.assertEqual(restored['models'],1);self.assertEqual(restored['wins'],1)
            self.assertEqual(restored['learning_status'],'LEARNING')
            (source/'learning_model_v207.csv').unlink()
            restored,_=self.execute(tmp,mode=21)
            self.assertTrue(restored['bad']);self.assertEqual(restored['learning_status'],'MODEL_MISSING')

    def test_partial_replay_tail_does_not_change_committed_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(tmp)
            before=collect(source)
            tail=sorted(source.glob('input_*.csv'))[-1]
            with tail.open('a') as f:f.write('2,partial')
            self.assertEqual(collect(source)['papers'],before['papers'])

    def test_invalid_summary_is_not_displayed_as_valid_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(tmp);update(source)
            path=source/'paper_summary_v207.csv'
            path.write_text(path.read_text().replace('wins','WRONG'))
            restored,_=self.execute(tmp,mode=20)
            self.assertEqual(restored['wins'],0)

    def test_inherited_range_trend_and_breakout_routes_both_directions(self):
        from tests.context_fixtures import trend_bars,breakout_bars
        for factory,setup in ((sr_bars,1),(trend_bars,2),(breakout_bars,3)):
            for direction in (1,-1):
                with self.subTest(setup=setup,direction=direction),tempfile.TemporaryDirectory() as tmp:
                    result,source=self.execute(tmp,direction=direction,factory=factory)
                    self.assertEqual(result['signals'],1)
                    rows=collect(source)['references'];self.assertEqual(rows[0]['setup'],setup)
                    self.assertEqual(rows[0]['direction'],direction);self.assertEqual(rows[0]['status'],'WIN')

    def test_breakout_without_retest_never_publishes(self):
        from tests.context_fixtures import breakout_bars
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,mode=16,factory=breakout_bars)
            self.assertEqual(result['signals'],0)

    def test_disabling_strategies_does_not_create_fallback_signals(self):
        from tests.context_fixtures import trend_bars,breakout_bars
        for factory in (sr_bars,trend_bars,breakout_bars):
            with self.subTest(factory=factory.__name__),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,mode=17,factory=factory)
                self.assertEqual(result['signals'],0)

    def test_logistic_observe_does_not_block_and_forecast_matches_python(self):
        import math
        from intelligence.advanced_learning import probability
        from intelligence.signal_features import NAMES
        for direction in (1,-1):
            with self.subTest(direction=direction),tempfile.TemporaryDirectory() as tmp:
                weight=[(i-10)*.01 for i in range(len(NAMES))]
                result,source=self.execute(tmp,direction=direction,advanced={'weight':weight})
                self.assertEqual(result['signals'],1)
                row=collect(source)['references'][0]
                m=dict(intercept=-2.,mean=[0.]*len(NAMES),scale=[1.]*len(NAMES),weight=weight)
                self.assertAlmostEqual(row['locked_probability'],probability(m,row['features']),places=8)
                self.assertEqual(row['model_id'],(START-200)*1000+901)

    def test_active_logistic_only_removes_signals_and_keeps_reference_labels(self):
        for intercept,expected in ((-2.,0),(2.,1)):
            with self.subTest(intercept=intercept),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,advanced={'phase':'ACTIVE','intercept':intercept})
                self.assertEqual(result['signals'],expected)
                rows=collect(source)['references'];self.assertEqual(len(rows),1)
                self.assertEqual(rows[0]['status'],'WIN')

    def test_advanced_stale_identity_and_truncation_cannot_publish(self):
        for model in ('stale','wrong_feed','truncated'):
            with self.subTest(model=model),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,advanced=model)
                self.assertEqual(result['signals'],0)

    def test_advanced_domain_abstains_without_changing_base_direction(self):
        from intelligence.signal_features import NAMES
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,advanced={'phase':'ACTIVE','low':[0.]*len(NAMES),'high':[0.]*len(NAMES)})
            self.assertEqual(result['signals'],1)
            self.assertEqual(collect(source)['references'][0]['model_id'],0)

    def test_no_broker_order_api_is_in_v207_source(self):
        text=(ROOT/'mt4/Experts/EURUSD_M5_Intelligence_V228.mq4').read_text()
        for forbidden in ('AutoTrade.mqh','BOAuto','WebRequest','OrderSend','PracticeTestMode','Password='):
            self.assertNotIn(forbidden,text)


if __name__=='__main__':unittest.main()
