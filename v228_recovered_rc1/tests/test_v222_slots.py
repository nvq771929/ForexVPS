"""Actual adapter under sparse chart ticks: creation, failures and native boundaries."""
import csv,json,subprocess,tempfile,unittest
from pathlib import Path
from intelligence.candidate_data import read
from intelligence.slot_review import review
from tests.test_demo_learning_native import NativeHarness,ROOT


class SparseTickTests(NativeHarness,unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass();folder=cls.binary.parent;path=folder/'demo.cpp';code=path.read_text()
        before='datetime iTime(int,int,int shift){if(shift==0)return TimeCurrent()/300*300;return closedBars.at(closedBars.size()-shift).time;}'
        after='datetime fakeLiveBarOverride=-1;\ndatetime iTime(int,int,int shift){if(shift==0)return fakeLiveBarOverride>=0 ? fakeLiveBarOverride : TimeCurrent()/300*300;return closedBars.at(closedBars.size()-shift).time;}'
        assert before in code;code=code.replace(before,after)
        code=code.replace('int copyRequests=0;','int copyRequests=0;long fakeHistoryDelayMs=0;')
        code=code.replace('  copyRequests++;copyTimes.push_back(fakeNowMs);','  fakeNowMs+=fakeHistoryDelayMs;fakeHistoryDelayMs=0;copyRequests++;copyTimes.push_back(fakeNowMs);')
        branch=r'''
 if(mode>=40 && mode<=51){
  long first=3171,second=18265;
  if(mode==41){first=3421;second=18890;}if(mode==42){first=2172;second=29141;}if(mode==43){first=1735;second=19938;}
  if(mode==44){first=16000;second=19000;}
  if(mode==46)second=10000;
  auto early=closedBars[0];early.time-=300;addBar(early);
  std::sort(history5.begin(),history5.end(),[](auto a,auto b){return a.time<b.time;});
  std::sort(history1.begin(),history1.end(),[](auto a,auto b){return a.time<b.time;});
  fakeNowMs=(start-1)*1000;fakeLiveBarOverride=start-300;EnableAlerts=false;
  if(OnInit()!=0)return 3;boFirstLiveTick=false;long seed=0;if(!BOClockTick(TimeCurrent(),seed))return 4;
  if(mode==48)boState.resumeAt=start+600;
  for(long ms=0;ms<=std::max(22000L,second+1000);ms++){
   fakeNowMs=start*1000+ms;
   if(ms==first || ms==second || (mode==46 && ms==14000)){
    fakeLiveBarOverride=start;
    if(mode==45 && ms==first)fakeHistoryDelayMs=5000;
    if(mode==50 && ms==first)fakeHistoryDelayMs=1000;
    if(mode==51 && ms==first)fakeHistoryDelayMs=13000;
    if(mode==46){m5Hole=ms==first;m1Hole=ms==first;}
    if(mode==47){m5Hole=true;m1Hole=true;}
    if(mode==49)connected=false;
    OnTick();
    if(fakeNowMs>start*1000+ms)ms=fakeNowMs-start*1000;
   }
   if(ms%1000==0)OnTimer();
  }
  int anchors=0;string n;long long h=FileFindFirst(boRoot+"\\event_*.bin",n);
  if(h!=INVALID_HANDLE){do{BORuntimeState state{};BOEvent e{};if(!BOReadLedger(boRoot+"\\"+n,state,e))return 5;if(e.kind==BO_ANCHOR_EVENT)anchors++;}while(FileFindNext(h,n));FileFindClose(h);}
  std::cout<<"{\"anchors\":"<<anchors<<",\"healthy\":"<<boHealthy<<",\"slot_status\":\""<<boSlotStatus<<"\",\"slot_blocker\":\""<<boSlotBlocker<<"\"}";
  OnDeinit(0);return 0;
 }
'''
        code=code.replace(' if(mode==22 || mode==23){',branch+'\n if(mode==22 || mode==23){');path.write_text(code)
        proc=subprocess.run(['g++','-std=c++17','-O1',str(path),'-o',str(cls.binary)],capture_output=True,text=True)
        if proc.returncode:raise RuntimeError(proc.stderr)

    def slot_rows(self,source):
        rows=[]
        for path in source.glob('analysis_slots_v222_*.csv'):
            with path.open() as stream:rows.extend(csv.DictReader(stream))
        return rows

    def test_four_recorded_sparse_tick_schedules_create_exactly_one_anchor(self):
        for mode in (40,41,42,43):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,mode=mode)
                self.assertEqual(result['anchors'],1);self.assertTrue(result['healthy'])
                rows=self.slot_rows(source);final=[r for r in rows if r['phase']=='FINAL']
                self.assertEqual(len(final),1);self.assertEqual(final[0]['status'],'CREATED')
                self.assertEqual(sum(r['status']=='WAIT_HISTORY_BAR' for r in rows),1)
                report=review(source,read(source));self.assertEqual(report['final_counts']['CREATED'],1)

    def test_late_tick_and_history_work_exceeding_quote_age_do_not_backdate_anchor(self):
        for mode in (44,45):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,mode=mode)
                self.assertEqual(result['anchors'],0)
                finals=[r for r in self.slot_rows(source) if r['phase']=='FINAL']
                self.assertEqual(len(finals),1);self.assertEqual(finals[0]['status'],'MISSED_START_WINDOW')
                if mode==45:self.assertEqual(finals[0]['blocker'],'QUOTE_TOO_OLD')

    def test_history_can_recover_within_window_but_missing_history_cannot_create(self):
        for mode,expected in ((46,1),(47,0)):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,mode=mode);self.assertEqual(result['anchors'],expected)
                self.assertEqual([r['status'] for r in self.slot_rows(source) if r['phase']=='FINAL'],['CREATED' if expected else 'MISSED_START_WINDOW'])

    def test_history_latency_preserves_actual_quote_timestamp_and_cannot_extend_window(self):
        from intelligence.native_ledger import read_directory
        for mode,expected in ((50,1),(51,0)):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,mode=mode);self.assertEqual(result['anchors'],expected)
                records=read_directory(source)
                if expected:
                    row=next(r for r in records if r['event']['kind']==1)
                    self.assertEqual(row['event']['observedMs']-row['state']['current']['lastQuoteMs'],1000)
                else:self.assertEqual(result['slot_status'],'MISSED_START_WINDOW')

    def test_cooldown_and_disconnect_have_reasons_without_bypassing_native_guards(self):
        for mode,status in ((48,'COOLDOWN'),(49,'MISSED_START_WINDOW')):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,mode=mode);self.assertEqual(result['anchors'],0)
                finals=[r for r in self.slot_rows(source) if r['phase']=='FINAL']
                self.assertEqual(finals[0]['status'],status)
                if mode==49:self.assertEqual(finals[0]['blocker'],'DISCONNECTED')

    def test_slot_created_row_tampering_or_duplicate_final_is_rejected(self):
        for duplicate in (False,True):
            with self.subTest(duplicate=duplicate),tempfile.TemporaryDirectory() as tmp:
                _,source=self.execute(tmp,mode=40);snapshot=read(source);path=next(source.glob('analysis_slots_v222_*.csv'));rows=self.slot_rows(source)
                if duplicate:rows.append(rows[-1])
                else:rows[-1]['native_sequence']='1'
                with path.open('w',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
                with self.assertRaises(ValueError):review(source,snapshot)

    def test_missed_slot_diagnostics_advance_even_without_new_native_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(tmp,mode=47);snapshot=read(source)
            report=review(source,snapshot)
            self.assertEqual(report['final_counts'],{'MISSED_START_WINDOW':1})
            self.assertGreater(report['observer_asof_ms'],report['native_prefix_asof_ms'])
            self.assertFalse(report['activation_allowed'])

    def test_tester_retains_legacy_sampling_and_origin(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,mode=40,testing=True)
            self.assertEqual(result['anchors'],0)
            self.assertEqual(read(source)['origin'],'BACKTEST_MT4')
