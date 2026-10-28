#ifndef BO_V222_SLOT_DIAGNOSTICS
#define BO_V222_SLOT_DIAGNOSTICS
#include "Types.mqh"
// Independent observer. Never changes native POD, decisions or the start window.
datetime boSlotBar=0;
bool boSlotFinal=false,boSlotWriteFailed=false;
long boSlotAttempts=0,boSlotCreated=0,boSlotMissed=0;
string boSlotStatus="WAIT_FIRST_TICK",boSlotBlocker="WAIT_TICK";
void BOSlotReset() {
   boSlotBar=0;boSlotFinal=false;boSlotWriteFailed=false;boSlotAttempts=0;
   boSlotCreated=0;boSlotMissed=0;boSlotStatus="WAIT_FIRST_TICK";boSlotBlocker="WAIT_TICK";
}
void BOSlotWrite(string root,string session,const BORuntimeState &s,uint policy,long nowMs,string phase,string status,string blocker) {
   if(boSlotBar<=0)return;
   int file=FileOpen(root+"\\analysis_slots_v222_"+session+".csv",FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
   if(file==INVALID_HANDLE) { boSlotWriteFailed=true;return; }
   bool ok=true;
   if(FileSize(file)==0)ok=FileWrite(file,"schema","logic","software","session","analysis_start","observed_ms","config_hash","feed_hash","policy_hash",
      "phase","status","blocker","attempts","history_bar","history_ready","quote_age_ms","native_sequence","paused")>0;
   if(!FileSeek(file,0,SEEK_END))ok=false;
   long age=boLastTickMs>0 ? nowMs-boLastTickMs : -1;
   if(ok)ok=FileWrite(file,1,2026101707,"2.22",session,(long)boSlotBar,nowMs,s.configHash,s.feedHash,policy,
      phase,status,blocker,boSlotAttempts,(long)boHistoryBar,boHistoryReady,age,s.sequence,s.paused ? 1 : 0)>0;
   FileFlush(file);FileClose(file);if(!ok)boSlotWriteFailed=true;
}
void BOSlotState(string root,string session,const BORuntimeState &s,uint policy,long nowMs,string status,bool isFinal=false) {
   if(boSlotFinal)return;
   if(!isFinal && boSlotStatus==status)return;
   if(isFinal) {
      boSlotFinal=true;if(status=="CREATED")boSlotCreated++;else if(status=="MISSED_START_WINDOW")boSlotMissed++;
   } else boSlotBlocker=status;
   boSlotStatus=status;
   BOSlotWrite(root,session,s,policy,nowMs,isFinal ? "FINAL" : "WAIT",status,boSlotBlocker);
}
void BOSlotObserve(string root,string session,const BORuntimeState &s,const BOConfig &c,uint policy,long nowMs,datetime attachBar) {
   if(nowMs<=0)return;
   datetime bar=(datetime)((nowMs/300000)*300);
   if(bar!=boSlotBar) {
      if(boSlotBar>0 && !boSlotFinal)BOSlotState(root,session,s,policy,nowMs,"MISSED_START_WINDOW",true);
      boSlotBar=bar;boSlotFinal=false;boSlotAttempts=0;boSlotStatus="";boSlotBlocker="WAIT_TICK";
      if(bar<=attachBar || (bar<=s.lastStarted && (!s.current.exists || s.current.analysisStart!=bar))) {
         BOSlotState(root,session,s,policy,nowMs,"ATTACH_OR_RECOVERY",true);return;
      }
      BOSlotState(root,session,s,policy,nowMs,"WAIT_TICK");
   }
   if(boSlotFinal)return;
   if(s.current.exists && s.current.analysisStart==bar && s.lastStarted==bar) {
      BOSlotState(root,session,s,policy,nowMs,"CREATED",true);return;
   }
   if(bar<s.resumeAt) { BOSlotState(root,session,s,policy,nowMs,"COOLDOWN",true);return; }
   if(nowMs>(long)(bar+c.maximumAnalysisDelaySeconds)*1000)BOSlotState(root,session,s,policy,nowMs,"MISSED_START_WINDOW",true);
}
#endif
