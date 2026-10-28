#ifndef BO_V222_RUNTIME_DIAGNOSTICS
#define BO_V222_RUNTIME_DIAGNOSTICS
#include "Types.mqh"
// Session-only observers. Never mutate the authoritative state or entry guards.
long boDiagTickMs=0,boDiagGapMs=0,boDiagLocks=0,boDiagGapCancels=0,boDiagEntries=0;
long boDiagIncomingGapCancels=0,boDiagNoTickCancels=0;
long boDiagCancelStoredAge=-1,boDiagCancelTickAge=-1,boDiagCancelGap=-1;
string boDiagLastGapClass="NONE";
double boDiagBid=0,boDiagAsk=0;
bool boDiagWriteFailed=false;
string boDiagTrigger="INIT";
void BODiagnosticsTrigger(string trigger) { boDiagTrigger=trigger; }
void BODiagnosticsReset() {
   boDiagTickMs=0; boDiagGapMs=0; boDiagLocks=0; boDiagGapCancels=0; boDiagEntries=0;
   boDiagBid=0; boDiagAsk=0; boDiagWriteFailed=false; boDiagTrigger="INIT";
   boDiagIncomingGapCancels=0; boDiagNoTickCancels=0;
   boDiagCancelStoredAge=-1; boDiagCancelTickAge=-1; boDiagCancelGap=-1; boDiagLastGapClass="NONE";
}
void BODiagnosticsTick(long nowMs,double bid,double ask) {
   boDiagGapMs=boDiagTickMs>0 ? nowMs-boDiagTickMs : 0;
   boDiagTickMs=nowMs; boDiagBid=bid; boDiagAsk=ask;
}
string BODiagnosticsGapClass(long tickAge,long gap) {
   if(boDiagTrigger=="TICK" && tickAge==0 && gap>3000) return "INCOMING_TICK_AFTER_OBSERVATION_GAP";
   if((boDiagTrigger=="TIMER" || boDiagTrigger=="TESTER_REPLAY_LOCK") && tickAge>3000) return "NO_RECENT_TICK_AT_CHECK";
   return "REVIEW_REQUIRED";
}
void BODiagnosticsRecord(string root,string session,const BORuntimeState &s,const BOConfig &config,const BOEvent &event) {
   if(event.kind==BO_LOCK_EVENT && event.lockedDirection!=0) boDiagLocks++;
   if(event.kind==BO_CANCEL_EVENT && event.reason==BO_QUOTE_GAP) boDiagGapCancels++;
   if(event.kind==BO_ENTRY_EVENT && event.signal) boDiagEntries++;
   if((event.kind!=BO_LOCK_EVENT && event.kind!=BO_CANCEL_EVENT && event.kind!=BO_ENTRY_EVENT) ||
      event.analysisStart!=s.current.analysisStart || s.current.candidate.direction==0) return;
   long storedAge=s.current.lastQuoteMs>0 ? event.observedMs-s.current.lastQuoteMs : -1;
   long tickAge=boDiagTickMs>0 ? event.observedMs-boDiagTickMs : -1;
   bool known=boDiagTickMs>0 && boDiagTickMs<=event.observedMs;
   string gapClass="NONE";
   if(event.kind==BO_CANCEL_EVENT && event.reason==BO_QUOTE_GAP) {
      gapClass=BODiagnosticsGapClass(known ? tickAge : -1,known ? boDiagGapMs : -1);
      boDiagLastGapClass=gapClass; boDiagCancelStoredAge=storedAge;
      boDiagCancelTickAge=known ? tickAge : -1; boDiagCancelGap=known ? boDiagGapMs : -1;
      if(gapClass=="INCOMING_TICK_AFTER_OBSERVATION_GAP") boDiagIncomingGapCancels++;
      if(gapClass=="NO_RECENT_TICK_AT_CHECK") boDiagNoTickCancels++;
   }
   int file=FileOpen(root+"\\execution_diagnostics_"+session+".csv",FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(file==INVALID_HANDLE) { boDiagWriteFailed=true; return; }
   bool ok=true;
   if(FileSize(file)==0) ok=FileWrite(file,"schema","logic","sequence","analysis_start","event_kind","observed_ms",
      "stored_quote_ms","stored_quote_age_ms","latest_tick_ms","latest_tick_age_ms","inter_tick_gap_ms",
      "latest_bid","latest_ask","spread_pips","locked","canceled","validation","reason","locked_direction","signal","origin",
      "event_trigger","event_minus_target_ms","event_minus_lock_ms","gap_class","quote_fresh_seconds","maximum_observation_gap_seconds")>0;
   if(!FileSeek(file,0,SEEK_END)) ok=false;
   // Tick facts are visible only if observed before this event, including replayed LOCK.
   if(ok) ok=FileWrite(file,3,2026101707,s.sequence,IntegerToString((long)event.analysisStart),event.kind,event.observedMs,
      s.current.lastQuoteMs,storedAge,known ? boDiagTickMs : 0,known ? tickAge : -1,known ? boDiagGapMs : -1,
      known ? DoubleToString(boDiagBid,5) : "",known ? DoubleToString(boDiagAsk,5) : "",
      known ? DoubleToString((boDiagAsk-boDiagBid)/.0001,3) : "",s.current.locked,s.current.canceled,
      event.validation,BOReasonName(event.reason),event.lockedDirection,event.signal,IsTesting() ? "BACKTEST_MT4" : "LIVE_MT4",
      boDiagTrigger,event.observedMs-(long)s.current.targetTime*1000,
      s.current.lockedAtMs>0 ? event.observedMs-s.current.lockedAtMs : -1,gapClass,config.quoteFreshSeconds,config.maximumObservationGapSeconds)>0;
   FileFlush(file); FileClose(file);
   if(!ok) boDiagWriteFailed=true;
}
string BODiagnosticsStage(const BORuntimeState &s) {
   if(!s.current.exists) return "CHO DU LIEU / CHUA CO LUOT";
   if(s.current.canceled) return "DA HUY | "+BOReasonName(s.current.reason);
   if(s.current.entered) return "DA QUA MOC ENTRY";
   if(s.current.candidate.direction==0) return "KHONG CO SETUP | "+BOReasonName(s.current.reason);
   if(s.current.validation!=BO_CONFIRMED) return "CHO XAC NHAN T+1";
   if(!s.current.locked) return "DA XAC NHAN | CHO KHOA";
   return s.current.action!=0 ? "DA KHOA HUONG | CHO ENTRY" : "KHOA CHUA PHAT | "+BOReasonName(s.current.reason);
}
#endif
