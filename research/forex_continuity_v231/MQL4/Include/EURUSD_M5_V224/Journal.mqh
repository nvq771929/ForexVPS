#ifndef BO_V222_JOURNAL
#define BO_V222_JOURNAL
#include "Contract.mqh"
// Immutable write-ahead records are authoritative checkpoints. All persisted structs contain POD only.
uint BOChecksum(int handle, long bytes) {
   FileSeek(handle,0,SEEK_SET); uint checksum=2166136261;
   for(long i=0;i<bytes;i++) checksum=(checksum^(uint)(uchar)FileReadInteger(handle,CHAR_VALUE))*16777619;
   return checksum;
}
string BOLedgerName(string root,long sequence) { return root+"\\event_"+StringFormat("%012I64d",sequence)+".bin"; }
bool BOReadLedger(string filename, BORuntimeState &state, BOEvent &event) {
   int handle=FileOpen(filename,FILE_READ|FILE_BIN);
   if(handle==INVALID_HANDLE) return false;
   long expected=20+sizeof(state)+sizeof(event)+4;
   if((long)FileSize(handle)!=expected) { FileClose(handle); return false; }
   uint computed=BOChecksum(handle,expected-4);
   uint stored=(uint)FileReadInteger(handle,INT_VALUE);
   FileSeek(handle,0,SEEK_SET);
   bool ok=FileReadInteger(handle,INT_VALUE)==1112494385 && FileReadInteger(handle,INT_VALUE)==BO_SCHEMA &&
      FileReadInteger(handle,INT_VALUE)==BO_LOGIC_VERSION && FileReadInteger(handle,INT_VALUE)==sizeof(state) && FileReadInteger(handle,INT_VALUE)==sizeof(event);
   if(ok && FileReadStruct(handle,state)!=sizeof(state)) ok=false;
   if(ok && FileReadStruct(handle,event)!=sizeof(event)) ok=false;
   FileClose(handle); return ok && computed==stored;
}
bool BOCommit(string root, BORuntimeState &state, const BOEvent &event) {
   string target=BOLedgerName(root,state.sequence),temp=target+".write_"+IntegerToString((long)GetTickCount())+".tmp";
   if(FileIsExist(target)) return false; // Never replace committed evidence.
   if(FileIsExist(temp)) return false;
   int handle=FileOpen(temp,FILE_READ|FILE_WRITE|FILE_BIN);
   if(handle==INVALID_HANDLE) return false;
   bool ok=true;
   if(FileWriteInteger(handle,1112494385,INT_VALUE)!=4) ok=false;
   if(FileWriteInteger(handle,BO_SCHEMA,INT_VALUE)!=4) ok=false;
   if(FileWriteInteger(handle,BO_LOGIC_VERSION,INT_VALUE)!=4) ok=false;
   if(FileWriteInteger(handle,sizeof(state),INT_VALUE)!=4) ok=false;
   if(FileWriteInteger(handle,sizeof(event),INT_VALUE)!=4) ok=false;
   if(FileWriteStruct(handle,state)!=sizeof(state) || FileWriteStruct(handle,event)!=sizeof(event)) ok=false;
   FileFlush(handle);
   if(ok) {
      long bytes=(long)FileSize(handle); uint checksum=BOChecksum(handle,bytes);
      FileSeek(handle,0,SEEK_END); if(FileWriteInteger(handle,(int)checksum,INT_VALUE)!=4) ok=false;
   }
   FileFlush(handle); FileClose(handle);
   if(!ok) return false;
   return FileMove(temp,0,target,0); // Atomic publication in the same MT4 Files sandbox.
}
bool BORestore(string root,BORuntimeState &state,bool &found) {
   found=false; long best=0; string name,bestName="";
   long search=FileFindFirst(root+"\\event_*.bin",name);
   if(search!=INVALID_HANDLE) {
      do {
         int offset=StringFind(name,"event_");
         if(offset<0) continue;
         long seq=StringToInteger(StringSubstr(name,offset+6,12));
         if(seq>best) { best=seq; bestName=name; }
      } while(FileFindNext(search,name));
      FileFindClose(search);
   }
   if(best==0) return true;
   found=true; BOEvent event;
   string filename=StringFind(bestName,"\\")>=0 ? bestName : root+"\\"+bestName;
   if(!BOReadLedger(filename,state,event)) return false;
   return state.sequence==best;
}
void BOMakeEvent(const BOPrediction &e,int kind,long nowMs,BOEvent &v) {
   ZeroMemory(v); v.kind=kind; v.analysisStart=e.analysisStart; v.targetTime=e.targetTime; v.observedMs=nowMs;
   v.direction=e.candidate.direction; v.setup=e.candidate.setup; v.regime=e.anchor.regime; v.validation=e.validation;
   v.lockedDirection=e.lockedDirection; v.lockedAction=e.lockedAction; v.action=e.action; v.selectedHorizon=e.horizon;
   v.modelId=e.modelId; v.reason=e.reason; v.bid=e.latestBid; v.lockedAtMs=e.lockedAtMs; v.p1=e.p1; v.p2=e.p2; v.p3=e.p3; v.serial=e.serial;
}
bool BOLogReplayInput(string root,string session,long sequence,string kind,long nowMs,datetime serverTime,double bid,double ask,bool shadow) {
   string day=TimeToString((datetime)(nowMs/1000),TIME_DATE); StringReplace(day,".","");
   string path=root+"\\input_"+day+".csv";
   ResetLastError();
   // The local learner reads this append-only file. Keep writes single-owner
   // through the instance lease, while explicitly allowing concurrent readers.
   int handle=FileOpen(path,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
   if(handle==INVALID_HANDLE) { Print("REPLAY_WRITE_FAILED stage=OPEN error=",GetLastError()," path=",path," attempted_sequence=",sequence); return false; }
   if(FileSize(handle)==0 && FileWrite(handle,"schema","logic_version","session","sequence","event_type","time_ms_estimated","server_time_seconds","bid","ask","shadow_mode")==0) {
      int error=GetLastError();FileClose(handle);Print("REPLAY_WRITE_FAILED stage=HEADER error=",error," path=",path);return false;
   }
   if(!FileSeek(handle,0,SEEK_END)) { int error=GetLastError();FileClose(handle);Print("REPLAY_WRITE_FAILED stage=SEEK error=",error," path=",path);return false; }
   uint written=FileWrite(handle,BO_SCHEMA,BO_LOGIC_VERSION,session,sequence,kind,nowMs,(long)serverTime,DoubleToString(bid,Digits),DoubleToString(ask,Digits),shadow ? 1 : 0);
   int error=GetLastError();FileFlush(handle);int flushError=GetLastError();FileClose(handle);
   if(written==0 || error!=0 || flushError!=0) {
      Print("REPLAY_WRITE_FAILED stage=ROW_OR_FLUSH error=",error," flush_error=",flushError," path=",path," attempted_sequence=",sequence);return false;
   }
   return true;
}
bool BOWriteSnapshot(string root,datetime start,const BOBar &bars[],uint hash) {
   string target=root+"\\anchor_"+IntegerToString((long)start)+".csv",temp=target+".write_"+IntegerToString((long)GetTickCount())+".tmp";
   if(FileIsExist(target)) return false;
   int handle=FileOpen(temp,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(handle==INVALID_HANDLE) return false;
   bool ok=FileWrite(handle,"BO_ANCHOR",BO_SCHEMA,BO_LOGIC_VERSION,Symbol(),(long)start,hash,BO_HISTORY)>0;
   if(FileWrite(handle,"time_broker","open","high","low","close","tick_volume")==0) ok=false;
   for(int i=0;i<BO_HISTORY;i++)
      if(FileWrite(handle,(long)bars[i].time,DoubleToString(bars[i].open,Digits),DoubleToString(bars[i].high,Digits),
         DoubleToString(bars[i].low,Digits),DoubleToString(bars[i].close,Digits),bars[i].ticks)==0) ok=false;
   FileFlush(handle); FileClose(handle);
   return ok && FileMove(temp,0,target,0);
}
bool BOWriteSessionInfo(string root,string session,string release,const BOConfig &c,uint hash,uint feed,bool shadow) {
   string target=root+"\\session_"+session+".csv",temporary=target+".tmp";
   if(FileIsExist(target) || FileIsExist(temporary)) return false;
   int file=FileOpen(temporary,FILE_WRITE|FILE_CSV|FILE_ANSI,','); if(file==INVALID_HANDLE) return false;
   bool ok=FileWrite(file,"schema","logic_version","ea_release","config_hash","feed_hash","shadow","payout",
      "analysis_start_delay_seconds","prelock_observation_gap_seconds","quote_fresh_seconds","reference_boundary_seconds",
      "lock_lead_seconds","lock_guard_seconds","allow_sr1","allow_tp1","allow_br1","payout_policy","history_policy","history_retry_seconds")>0;
   if(FileWrite(file,BO_SCHEMA,BO_LOGIC_VERSION,release,hash,feed,shadow ? 1 : 0,c.fixedPayoutFraction,
      c.maximumAnalysisDelaySeconds,c.maximumObservationGapSeconds,c.quoteFreshSeconds,c.boundaryLagSeconds,
      c.lockLeadSeconds,c.lockGuardSeconds,c.allowSR1,c.allowTP1,c.allowBR1,"FIXED_82","M5_THEN_COMPLETE_M1",5)==0) ok=false;
   FileFlush(file); FileClose(file); return ok && FileMove(temporary,0,target,0);
}
#endif
