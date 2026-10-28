#ifndef BO_V225_EMBEDDED_OBSERVER
#define BO_V225_EMBEDDED_OBSERVER
#include "EmbeddedContext.mqh"
#include "EmbeddedStorage.mqh"

ECState boEmbedded;
long boEmbeddedSeed=0,boEmbeddedWritten=0,boEmbeddedLastPacket=0;
int boEmbeddedOffset=0,boEmbeddedBootstrapCount=0;
bool boEmbeddedEnabled=false,boEmbeddedClock=false,boEmbeddedIO=true,boEmbeddedHistoryChanged=false;
string boEmbeddedStatus="OFF",boEmbeddedPanel="";
ESMeta boEmbeddedIdentity;
string boEmbeddedStoreRoot="",boEmbeddedStoreSession="",boEmbeddedResume="FRESH";
uint boEmbeddedStreamHash=0;
long boEmbeddedCheckpointCount=0;
bool boEmbeddedStorageBlocked=false;
int boEmbeddedRequested=0,boEmbeddedCopyError=0;


bool BOEmbeddedOffsetValid(int minutes) {return minutes>=-720 && minutes<=840 && minutes%5==0;}
void BOEmbeddedReset(bool enabled,bool verified,int offset) {
   ZeroMemory(boEmbeddedIdentity);boEmbeddedStoreRoot="";boEmbeddedStoreSession="";boEmbeddedResume="FRESH";
   boEmbeddedStreamHash=0;boEmbeddedCheckpointCount=0;boEmbeddedStorageBlocked=false;boEmbeddedRequested=0;boEmbeddedCopyError=0;
   ECReset(boEmbedded);boEmbeddedSeed=0;boEmbeddedWritten=0;boEmbeddedLastPacket=0;
   boEmbeddedBootstrapCount=0;boEmbeddedOffset=offset;boEmbeddedEnabled=enabled;
   boEmbeddedClock=verified && BOEmbeddedOffsetValid(offset);boEmbeddedIO=true;boEmbeddedHistoryChanged=false;boEmbeddedPanel="";
   boEmbeddedStatus=!enabled ? "OFF" : (!boEmbeddedClock ? "CLOCK_UNVERIFIED" : "COLLECTING");
}
void BOEmbeddedBlock(string status) {boEmbeddedStorageBlocked=true;boEmbeddedStatus=status;}
ESMeta BOEmbeddedMeta(long availableMs,int kind) {
   ESMeta m=boEmbeddedIdentity;m.seed=boEmbeddedSeed;m.requested=boEmbeddedRequested;
   m.received=boEmbeddedBootstrapCount;m.error=boEmbeddedCopyError;m.kind=kind;
   m.availableMs=availableMs;m.previousHash=boEmbeddedStreamHash;m.streamHash=boEmbeddedStreamHash;return m;
}
bool BOEmbeddedCheckpoint(long nowMs,bool force=false) {
   if(boEmbeddedStorageBlocked || boEmbedded.last<=0 || boEmbedded.m5.count==boEmbeddedCheckpointCount)return !boEmbeddedStorageBlocked;
   if(!force && boEmbeddedCheckpointCount>0 && boEmbedded.m5.count-boEmbeddedCheckpointCount<12)return true;
   ESMeta m=BOEmbeddedMeta(nowMs,3);m.first=1;m.count=boEmbedded.m5.count;
   if(!ESWriteCheckpoint(boEmbeddedStoreRoot,m,boEmbedded)) {BOEmbeddedBlock("CHECKPOINT_WRITE_FAILED");return false;}
   boEmbeddedCheckpointCount=boEmbedded.m5.count;return true;
}
bool BOEmbeddedPacket(const ECBar &bars[],long availableMs,int kind) {
   int count=ArraySize(bars);if(count==0)return true;
   if(boEmbeddedStorageBlocked || count>4800 || boEmbeddedStoreRoot=="")return false;
   ECState next=boEmbedded;
   for(int i=0;i<count;i++) {
      if((bars[i].time+300)*1000>availableMs-(long)boEmbeddedOffset*60000 || !ECUpdate(next,bars[i])) {
         BOEmbeddedBlock("INPUT_PACKET_INVALID");return false;
      }
   }
   long seed=boEmbeddedSeed>0 ? boEmbeddedSeed : bars[0].time;
   ESMeta m=BOEmbeddedMeta(availableMs,kind);m.seed=seed;m.first=boEmbedded.m5.count+1;m.count=count;
   uint checksum=0;
   if(!ESWritePacket(boEmbeddedStoreRoot,m,bars,checksum)) {BOEmbeddedBlock("INPUT_ARCHIVE_WRITE_FAILED");return false;}
   // Publish numerical state only after its exact input packet is committed.
   boEmbedded=next;boEmbeddedSeed=seed;boEmbeddedStreamHash=checksum;
   boEmbeddedStatus=boEmbedded.snapshot.ready ? "OBSERVE_ONLY" : "COLLECTING";
   return BOEmbeddedCheckpoint(availableMs);
}
bool BOEmbeddedReplayPacket(string file,long nowMs) {
   ESMeta m;ECBar bars[];uint checksum=0;
   if(!ESReadPacket(file,boEmbeddedIdentity,nowMs,m,bars,checksum) || m.first!=boEmbedded.m5.count+1 ||
      m.previousHash!=(long)boEmbeddedStreamHash || (boEmbeddedSeed>0 && m.seed!=boEmbeddedSeed))return false;
   ECState next=boEmbedded;
   for(int i=0;i<ArraySize(bars);i++)if(!ECUpdate(next,bars[i]))return false;
   boEmbedded=next;boEmbeddedSeed=m.seed;boEmbeddedStreamHash=checksum;
   boEmbeddedBootstrapCount=(int)m.received;boEmbeddedCopyError=(int)m.error;return true;
}
bool BOEmbeddedRestore(long nowMs) {
   string name,bestName="";long best=0;
   long search=FileFindFirst(boEmbeddedStoreRoot+"\\state\\embedded_checkpoint_v226_*.bin",name);
   if(search!=INVALID_HANDLE) {
      do {int pos=StringFind(name,"embedded_checkpoint_v226_");long seq=StringToInteger(StringSubstr(name,pos+25,12));if(seq>best) {best=seq;bestName=name;}}while(FileFindNext(search,name));
      FileFindClose(search);
   }
   if(best>0) {
      ESMeta m;ECState restored;
      if(!ESReadCheckpoint(ESFull(boEmbeddedStoreRoot+"\\state",bestName),boEmbeddedIdentity,nowMs,m,restored) || m.count!=best) {
         BOEmbeddedBlock("CHECKPOINT_INVALID_NO_FALLBACK");return false;
      }
      // Check the committed input packet linked by the checkpoint.
      ESMeta linked;ECBar unused[];uint linkedHash=0;
      if(!ESReadPacket(ESName(boEmbeddedStoreRoot,"packet",best),boEmbeddedIdentity,nowMs,linked,unused,linkedHash) ||
         linkedHash!=(uint)m.streamHash || linked.first+linked.count-1!=best || linked.seed!=m.seed) {
         BOEmbeddedBlock("CHECKPOINT_INPUT_LINK_INVALID");return false;
      }
      boEmbedded=restored;boEmbeddedSeed=m.seed;boEmbeddedStreamHash=(uint)m.streamHash;
      boEmbeddedBootstrapCount=(int)m.received;boEmbeddedCopyError=(int)m.error;boEmbeddedCheckpointCount=best;
      boEmbeddedResume="CHECKPOINT_RESTORED";
   }
   // Sort only the bounded tail. No checkpoint => replay a short intact WAL,
   // never silently switch to a new seed when prior inputs exist.
   string paths[];long sequences[];int count=0;
   search=FileFindFirst(boEmbeddedStoreRoot+"\\packets\\embedded_packet_v226_*.bin",name);
   if(search!=INVALID_HANDLE) {
      do {
         int pos=StringFind(name,"embedded_packet_v226_");long seq=StringToInteger(StringSubstr(name,pos+21,12));
         if(seq>best) {
            if(count>=4800) {FileFindClose(search);BOEmbeddedBlock("REPLAY_TAIL_LIMIT");return false;}
            ArrayResize(paths,count+1);ArrayResize(sequences,count+1);int j=count;
            while(j>0 && sequences[j-1]>seq) {sequences[j]=sequences[j-1];paths[j]=paths[j-1];j--;}
            sequences[j]=seq;paths[j]=ESFull(boEmbeddedStoreRoot+"\\packets",name);count++;
         }
      }while(FileFindNext(search,name));FileFindClose(search);
   }
   for(int i=0;i<count;i++)if(!BOEmbeddedReplayPacket(paths[i],nowMs)) {BOEmbeddedBlock("INPUT_CHAIN_INVALID");return false;}
   if(count>0)boEmbeddedResume=best>0 ? "CHECKPOINT_PLUS_TAIL" : "INPUT_CHAIN_REPLAYED";
   if(boEmbedded.last>0)boEmbeddedStatus=boEmbedded.snapshot.ready ? "OBSERVE_ONLY" : "COLLECTING";
   return true;
}
void BOEmbeddedLineage(long nowMs) {
   int f=FileOpen(boEmbeddedStoreRoot+"\\embedded_lineage_v226_"+boEmbeddedStoreSession+".csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(f==INVALID_HANDLE) {BOEmbeddedBlock("LINEAGE_WRITE_FAILED");return;}
   bool ok=FileWrite(f,"schema","contract","session","origin","observed_broker_ms","offset_minutes","config_hash","feed_hash","policy_hash","bootstrap_requested_positions","bootstrap_received_bars","bootstrap_copy_error","seed_utc_seconds","resume_status","observer_status","stream_count","stream_hash","engine_version","state_bytes","age_meaning","ea_effects")>0;
   if(FileWrite(f,1,"V226_CLOSED_M5_STREAM_V1",boEmbeddedStoreSession,IsTesting() ? "BACKTEST_MT4" : "LIVE_MT4",nowMs,boEmbeddedOffset,
      boEmbeddedIdentity.config,boEmbeddedIdentity.feed,boEmbeddedIdentity.policy,boEmbeddedRequested,boEmbeddedBootstrapCount,boEmbeddedCopyError,
      boEmbeddedSeed,boEmbeddedResume,boEmbeddedStatus,boEmbedded.m5.count,boEmbeddedStreamHash,ES_ENGINE,sizeof(ECState),"SINCE_RULE_CONFIRMATION_NOT_TRUE_TREND_ONSET",0)==0)ok=false;
   FileFlush(f);FileClose(f);if(!ok)BOEmbeddedBlock("LINEAGE_WRITE_FAILED");
}
// A single bounded CopyRates on attach, before the EA starts. All bootstrap bars
// are historical inputs, NOT forecasts. Failure leaves UNKNOWN and uses cache.
void BOEmbeddedBootstrap(int requested) {
   if(!boEmbeddedEnabled || !boEmbeddedClock || requested<=0 || !IsConnected())return;
   long cutoff=(long)TimeCurrent();long end=(cutoff/300)*300;
   MqlRates rates[];ArraySetAsSeries(rates,false);
   ResetLastError();
   int count=CopyRates(Symbol(),PERIOD_M5,(datetime)(end-requested*300),(datetime)(end-1),rates);
   boEmbeddedCopyError=GetLastError();
   if(count<0 || count>requested || ArraySize(rates)!=count) {boEmbeddedStatus="BOOTSTRAP_UNAVAILABLE";return;}
   long previous=0;
   // Validate the whole packet before consuming it. Never sort or repair inputs.
   for(int i=0;i<count;i++) {
      ECBar b;b.time=(long)rates[i].time-(long)boEmbeddedOffset*60;
      b.open=rates[i].open;b.high=rates[i].high;b.low=rates[i].low;b.close=rates[i].close;b.ticks=rates[i].tick_volume;
      if(!ECValidBar(b) || (long)rates[i].time+300>cutoff || (previous>0 && b.time<=previous)) {
         boEmbeddedStatus="BOOTSTRAP_INVALID";return;
      }
      previous=b.time;
   }
   ECBar bars[];ArrayResize(bars,count);
   for(int i=0;i<count;i++) {
      bars[i].time=(long)rates[i].time-(long)boEmbeddedOffset*60;bars[i].open=rates[i].open;bars[i].high=rates[i].high;
      bars[i].low=rates[i].low;bars[i].close=rates[i].close;bars[i].ticks=rates[i].tick_volume;
   }
   boEmbeddedBootstrapCount=count;
   BOEmbeddedPacket(bars,cutoff*1000,1);
}
void BOEmbeddedStart(string root,string session,uint config,uint feed,uint policy,int requested) {
   if(!boEmbeddedEnabled || !boEmbeddedClock)return;
   boEmbeddedStoreRoot=root+"\\embedded_v226";boEmbeddedStoreSession=session;
   FolderCreate(boEmbeddedStoreRoot);FolderCreate(boEmbeddedStoreRoot+"\\state");FolderCreate(boEmbeddedStoreRoot+"\\packets");boEmbeddedRequested=requested;
   ZeroMemory(boEmbeddedIdentity);boEmbeddedIdentity.engine=ES_ENGINE;boEmbeddedIdentity.origin=IsTesting() ? 2 : 1;
   boEmbeddedIdentity.offset=boEmbeddedOffset;boEmbeddedIdentity.config=config;boEmbeddedIdentity.feed=feed;boEmbeddedIdentity.policy=policy;
   boEmbeddedIdentity.instance=BOHashText(root);boEmbeddedIdentity.symbol=BOHashText(Symbol());boEmbeddedIdentity.requested=requested;
   boEmbeddedIdentity.terminal=TerminalInfoInteger(TERMINAL_BUILD);
   long nowMs=(long)TimeCurrent()*1000;
   if(BOEmbeddedRestore(nowMs) && boEmbedded.last==0)BOEmbeddedBootstrap(requested);
   BOEmbeddedLineage(nowMs);
}
void BOEmbeddedFinish(long nowMs) {
   if(boEmbeddedEnabled && boEmbeddedClock && boEmbeddedStoreRoot!="" && !boEmbeddedHistoryChanged)BOEmbeddedCheckpoint(nowMs,true);
}
bool BOEmbeddedSafe(const BORuntimeState &state,const BOConfig &config,long nowMs) {
   // Keep heavy numerical work and new observer I/O out of imminent boundaries.
   if(state.current.exists && !state.current.entered && !state.current.canceled) {
      long target=(long)state.current.targetTime*1000;
      if(target-nowMs<=120000)return false;
   }
   for(int i=0;i<BO_MAX_PENDING;i++)if(state.pending[i].used)
      for(int h=1;h<=3;h++)if((state.pending[i].resolvedMask & (1<<(h-1)))==0) {
         long remaining=(long)(state.pending[i].targetTime+h*300)*1000-nowMs;
         if(remaining>=-config.boundaryLagSeconds*1000 && remaining<=60000)return false;
      }
   return true;
}
bool BOEmbeddedWrite(string root,string session,long availableBrokerMs) {
   if(boEmbedded.last<=0 || boEmbedded.snapshot.asofMs==boEmbeddedWritten)return true;
   boEmbeddedWritten=boEmbedded.snapshot.asofMs; // at most one attempt per new snapshot
   int file=FileOpen(root+"\\embedded_context_v226_"+session+".csv",FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(file==INVALID_HANDLE)return false;
   bool ok=true;
   if(FileSize(file)==0 && FileWrite(file,"schema","contract","session","origin","available_broker_ms",
      "broker_utc_offset_minutes","seed_utc_seconds","bootstrap_bars","asof_utc_ms","ready","direction",
      "phase","phase_flags","observed_age_minutes","m5_count","m15_count","h1_count","data_gap",
      "trade_model","ea_effects")==0)ok=false;
   FileSeek(file,0,SEEK_END);
   if(FileWrite(file,1,"V226_EMBEDDED_CONTEXT_V2",session,IsTesting() ? "BACKTEST_MT4" : "LIVE_MT4",
      availableBrokerMs,boEmbeddedOffset,boEmbeddedSeed,boEmbeddedBootstrapCount,boEmbedded.snapshot.asofMs,
      (int)boEmbedded.snapshot.ready,ECDirectionName(boEmbedded.snapshot.direction),ECPhaseName(boEmbedded.snapshot.phase),
      boEmbedded.snapshot.flags,DoubleToString(boEmbedded.snapshot.ageMinutes,3),boEmbedded.m5.count,
      boEmbedded.m15.count,boEmbedded.h1.count,(int)boEmbedded.snapshot.gap,"UNAVAILABLE",0)==0)ok=false;
   FileFlush(file);FileClose(file);return ok;
}
void BOEmbeddedPump(string root,string session,const BORuntimeState &state,const BOConfig &config,long nowMs) {
   if(!boEmbeddedEnabled || !boEmbeddedClock || boEmbeddedHistoryChanged || boEmbeddedStorageBlocked || nowMs<=0 || !BOEmbeddedSafe(state,config,nowMs))return;
   // Read only the native immutable cache; NO CopyRates, files/models/network on
   // the LOCK/ENTRY path. A delayed cache retains its real availability time.
   if(boHistoryReady && boHistoryBar!=boEmbeddedLastPacket && ArraySize(boHistoryBars)==BO_HISTORY) {
      boEmbeddedLastPacket=(long)boHistoryBar;
      // A broker revision must not silently rewrite an already consumed past.
      // Stop only this observer; reattach for a fresh, explicitly seeded replay.
      for(int i=0;i<BO_HISTORY;i++) {
         long utc=(long)boHistoryBars[i].time-(long)boEmbeddedOffset*60;
         for(int j=0;j<boEmbedded.m5.size;j++)if(boEmbedded.m5.bars[j].time==utc) {
            if(boEmbedded.m5.bars[j].open!=boHistoryBars[i].open || boEmbedded.m5.bars[j].high!=boHistoryBars[i].high ||
               boEmbedded.m5.bars[j].low!=boHistoryBars[i].low || boEmbedded.m5.bars[j].close!=boHistoryBars[i].close ||
               boEmbedded.m5.bars[j].ticks!=boHistoryBars[i].ticks) {
               boEmbeddedHistoryChanged=true;boEmbeddedStatus="HISTORY_CHANGED_NEW_INSTANCE_TAG";return;
            }
         }
      }
      ECBar batch[];ArrayResize(batch,0);
      for(int i=0;i<BO_HISTORY;i++) {
         long utc=(long)boHistoryBars[i].time-(long)boEmbeddedOffset*60;
         if(utc<=boEmbedded.last)continue;
         int n=ArraySize(batch);ArrayResize(batch,n+1);batch[n].time=utc;
         batch[n].open=boHistoryBars[i].open;batch[n].high=boHistoryBars[i].high;batch[n].low=boHistoryBars[i].low;
         batch[n].close=boHistoryBars[i].close;batch[n].ticks=boHistoryBars[i].ticks;
      }
      if(!BOEmbeddedPacket(batch,nowMs,2))return;
   }
   if(!BOEmbeddedWrite(root,session,nowMs))boEmbeddedIO=false;
}
string BOEmbeddedDisplayStatus(long brokerMs) {
   if(!boEmbeddedEnabled || !boEmbeddedClock)return boEmbeddedStatus;
   if(boEmbeddedHistoryChanged || boEmbeddedStorageBlocked)return boEmbeddedStatus;
   if(!boEmbeddedIO)return "OBSERVER_IO_ERROR";
   if(boEmbedded.last<=0)return boEmbeddedStatus;
   long lag=brokerMs-(long)boEmbeddedOffset*60000-boEmbedded.snapshot.asofMs;
   if(lag<0 || lag>=300000)return "STALE";
   return boEmbeddedStatus;
}
void BOEmbeddedDeletePanel() {
   for(int i=0;i<4;i++)ObjectDelete(0,"BOV226Embedded_"+IntegerToString(i));boEmbeddedPanel="";
}
void BOEmbeddedRender(long brokerMs,int left,int top) {
   if(!boEmbeddedEnabled)return;
   string status=BOEmbeddedDisplayStatus(brokerMs);
   string line[4];line[0]="BOI CANH NOI BO | "+status;
   bool visible=status=="OBSERVE_ONLY";
   line[1]=visible ? "Boi canh: "+ECDirectionName(boEmbedded.snapshot.direction)+" | "+ECPhaseName(boEmbedded.snapshot.phase) :
      "Lam am M15/H1: "+IntegerToString(boEmbedded.m15.count)+"/"+IntegerToString(boEmbedded.h1.count)+" (can 150 moi khung)";
   line[2]=visible && boEmbedded.snapshot.startedMs>0 ? "Tuoi tu xac nhan: "+DoubleToString(boEmbedded.snapshot.ageMinutes,0)+" phut" : "Tuoi xu huong: CHUA XAC DINH";
   line[3]="Mo hinh giao dich: CHUA CO | Chi quan sat";
   string signature=status+line[1]+line[2]+IntegerToString(left)+IntegerToString(top);
   if(signature==boEmbeddedPanel)return;boEmbeddedPanel=signature;
   for(int i=0;i<4;i++) {
      string name="BOV226Embedded_"+IntegerToString(i);
      if(ObjectFind(0,name)<0)ObjectCreate(0,name,OBJ_LABEL,0,0,0);
      ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);ObjectSetInteger(0,name,OBJPROP_XDISTANCE,left);
      ObjectSetInteger(0,name,OBJPROP_YDISTANCE,top+i*21);ObjectSetInteger(0,name,OBJPROP_FONTSIZE,11);
      ObjectSetInteger(0,name,OBJPROP_COLOR,clrAqua);ObjectSetString(0,name,OBJPROP_FONT,"Arial");
      ObjectSetString(0,name,OBJPROP_TEXT,line[i]);
   }
}
#endif
