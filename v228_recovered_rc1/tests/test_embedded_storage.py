"""Execute actual MQL checkpoint/input code under C++ shim. Not MetaEditor."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from tests.test_demo_learning_native import NativeHarness,ROOT
from tests.test_embedded_context import stream
from intelligence.embedded_packets import read_stream

class StorageHarness(NativeHarness,unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        p=cls.binary.parent/'demo.cpp';code=p.read_text();code=code[:code.rindex('int main(int argc,char**argv){')]
        main=r'''
int main(int argc,char**argv){
 filesRoot=argv[1];int mode=std::stoi(argv[2]);int split=std::stoi(argv[3]);
 ECState reference{};ECReset(reference);std::vector<ECBar> all;ECBar b{};
 while(std::cin>>b.time>>b.open>>b.high>>b.low>>b.close>>b.ticks){all.push_back(b);ECUpdate(reference,b);}
 if(all.empty())return 1;
 fakeNowMs=(all[0].time+300)*1000;
 BOEmbeddedReset(true,true,0);BOEmbeddedStart("audit","first",17,19,23,0);
 for(int i=0;i<split;i+=32){std::vector<ECBar> batch;for(int j=i;j<std::min(split,i+32);j++)batch.push_back(all[j]);fakeNowMs=(batch.back().time+300)*1000;
  if(!BOEmbeddedPacket(batch,fakeNowMs,2))return 2;}
 // Leave an actual input tail newer than the checkpoint (models crash timing).
 if(mode==1 || mode==5){boEmbeddedCheckpointCount=boEmbedded.m5.count;std::vector<ECBar> tail;
  for(int j=split;j<std::min(int(all.size()),split+3);j++)tail.push_back(all[j]);fakeNowMs=(tail.back().time+300)*1000;
  if(!BOEmbeddedPacket(tail,fakeNowMs,2))return 3;split+=tail.size();}
 string store=boEmbeddedStoreRoot;long before=boEmbedded.m5.count;
 if(mode==2){auto cp=nativePath(ESName(store,"checkpoint",boEmbeddedCheckpointCount));std::fstream f(cp,std::ios::binary|std::ios::in|std::ios::out);f.seekp(30);f.put('X');}
 if(mode==4){for(auto &p:std::filesystem::directory_iterator(nativePath(store+"\\state")))std::filesystem::remove(p.path());}
 if(mode==5){auto packet=nativePath(ESName(store,"packet",boEmbedded.m5.count));std::fstream f(packet,std::ios::binary|std::ios::in|std::ios::out);f.seekp(100);f.put('X');}
 BOEmbeddedReset(true,true,mode==3?60:0);BOEmbeddedStart("audit","second",17,19,23,0);
 bool restored=boEmbedded.m5.count==before;string status=boEmbeddedStatus,resume=boEmbeddedResume;
 if(!boEmbeddedStorageBlocked)for(int i=split;i<int(all.size());i+=32){std::vector<ECBar> batch;
  for(int j=i;j<std::min(int(all.size()),i+32);j++)batch.push_back(all[j]);fakeNowMs=(batch.back().time+300)*1000;
  if(!BOEmbeddedPacket(batch,fakeNowMs,2))return 4;}
 bool exact=std::memcmp(&reference,&boEmbedded,sizeof(reference))==0;
 int checkpoints=0;for(auto &p:std::filesystem::directory_iterator(nativePath(store+"\\state")))checkpoints++;
 std::cout<<"{\"restored\":"<<restored<<",\"exact\":"<<exact<<",\"blocked\":"<<boEmbeddedStorageBlocked
 <<",\"status\":\""<<status<<"\",\"resume\":\""<<resume<<"\",\"count\":"<<boEmbedded.m5.count
 <<",\"checkpoints\":"<<checkpoints<<"}";
}
'''
        p.write_text(code+main);proc=subprocess.run(['g++','-std=c++17','-O1',str(p),'-o',str(cls.binary)],capture_output=True,text=True)
        if proc.returncode:raise RuntimeError(proc.stderr)

    def run_stream(self,folder,mode=0,bars=None):
        bars=bars or stream(2150)
        data=''.join(' '.join(str(b[k]) for k in ('time','open','high','low','close','ticks'))+'\n' for b in bars)
        p=subprocess.run([str(self.binary),str(folder),str(mode),'1800'],input=data,capture_output=True,text=True,check=True)
        return json.loads(p.stdout)

    def test_checkpoint_restart_preserves_all_state_bytes_and_archived_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            r=self.run_stream(d);self.assertTrue(r['exact']);self.assertTrue(r['restored']);self.assertFalse(r['blocked'])
            self.assertLessEqual(r['checkpoints'],2)
            archive=read_stream(Path(d)/'audit/embedded_v226/packets');self.assertEqual(archive['count'],2150)
            self.assertEqual([x['bar'] for x in archive['observations']],stream(2150))

    def test_committed_tail_replayed_after_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            r=self.run_stream(d,1);self.assertTrue(r['exact']);self.assertEqual(r['resume'],'CHECKPOINT_PLUS_TAIL')

    def test_missing_checkpoint_can_replay_short_complete_chain(self):
        with tempfile.TemporaryDirectory() as d:
            r=self.run_stream(d,4);self.assertTrue(r['exact']);self.assertEqual(r['resume'],'INPUT_CHAIN_REPLAYED')

    def test_corrupt_latest_checkpoint_does_not_fall_back(self):
        with tempfile.TemporaryDirectory() as d:
            r=self.run_stream(d,2);self.assertTrue(r['blocked']);self.assertEqual(r['status'],'CHECKPOINT_INVALID_NO_FALLBACK')

    def test_clock_identity_change_cannot_restore(self):
        with tempfile.TemporaryDirectory() as d:
            r=self.run_stream(d,3);self.assertTrue(r['blocked']);self.assertEqual(r['status'],'CHECKPOINT_INVALID_NO_FALLBACK')

    def test_corrupt_input_tail_blocks_resume(self):
        with tempfile.TemporaryDirectory() as d:
            r=self.run_stream(d,5);self.assertTrue(r['blocked']);self.assertEqual(r['status'],'INPUT_CHAIN_INVALID')

    def test_packet_reader_rejects_removed_middle_packet(self):
        with tempfile.TemporaryDirectory() as d:
            self.run_stream(d);path=Path(d)/'audit/embedded_v226/packets';files=sorted(path.glob('*.bin'));files[3].unlink()
            with self.assertRaisesRegex(ValueError,'lineage/sequence'):read_stream(path)

class PriceWindowTests(unittest.TestCase):
    def test_fixed_window_features_do_not_depend_on_extra_older_history(self):
        from intelligence.price_behavior import PriceWindow
        bars=stream(2100);a=PriceWindow();b=PriceWindow();end=(bars[-1]['time']+300)*1000
        for row in bars:a.observe(row,(row['time']+300)*1000)
        for row in bars:
            if row['time']*1000>=end-18*3600000:b.observe(row,(row['time']+300)*1000)
        self.assertEqual(a.features(end,end),b.features(end,end))

    def test_future_and_late_available_bars_cannot_fill_current_window(self):
        from intelligence.price_behavior import PriceWindow
        b=stream(100);w=PriceWindow()
        for x in b:w.observe(x,(x['time']+300)*1000+10000)
        end=(b[-1]['time']+300)*1000
        with self.assertRaisesRegex(ValueError,'unavailable'):w.features(end,end)
        before=w.features(end,end+10000)
        future=dict(b[-1],time=b[-1]['time']+300,high=2.0)
        w.observe(future,(future['time']+300)*1000)
        self.assertEqual(before,w.features(end,end+10000))

    def test_missing_higher_frame_is_masked_not_fabricated(self):
        from intelligence.price_behavior import PriceWindow
        b=stream(64);w=PriceWindow()
        for x in b:w.observe(x,(x['time']+300)*1000)
        f=w.features((b[-1]['time']+300)*1000,(b[-1]['time']+300)*1000)
        self.assertLess(f['coverage']['3600'],16)
        for row in f['frames']['3600']:
            if row[-1]==0:self.assertEqual(row,[0.]*9)

    def test_revised_past_bar_requires_new_lineage(self):
        from intelligence.price_behavior import PriceWindow
        b=stream(1)[0];w=PriceWindow();w.observe(b,(b['time']+300)*1000)
        with self.assertRaisesRegex(ValueError,'revision'):w.observe(dict(b,ticks=b['ticks']+1),(b['time']+300)*1000)

if __name__=='__main__':unittest.main()
