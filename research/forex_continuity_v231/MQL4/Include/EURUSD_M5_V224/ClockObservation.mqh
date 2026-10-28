#ifndef BO_V227_CLOCK_OBSERVATION
#define BO_V227_CLOCK_OBSERVATION
// Observation only. BOClockTick and its original two-second rejection remain intact.
string boClockObservationRoot="",boClockObservationSession="",boClockObservationMode="";
bool boClockObservationEnabled=true,boClockObservationWriteFailed=false;
long boClockObservationSequence=0,boClockObservationLastAccepted=-1;
void BOClockObservationBind(string root,string session,string mode,bool enabled) {
   boClockObservationRoot=root;boClockObservationSession=session;boClockObservationMode=mode;
   boClockObservationEnabled=enabled;boClockObservationWriteFailed=false;
   boClockObservationSequence=0;boClockObservationLastAccepted=-1;
}
bool BOObservedClockTick(datetime serverTime,long &nowMs) {
   long previousBase=boClockBaseMs,previousTick=boLastTickMs,estimate=BONowMs();
   uint mono=GetTickCount(),previousMono=boClockMono;
   datetime terminalTime=TimeCurrent(),localTime=TimeLocal(),utcTime=TimeGMT();
   bool accepted=BOClockTick(serverTime,nowMs);
   // Every rejected quote and at most one accepted quote per broker second.
   if(!boClockObservationEnabled || boClockObservationRoot=="" ||
      (accepted && boClockObservationLastAccepted==(long)serverTime))return accepted;
   string path=boClockObservationRoot+"\\clock_observation_v227_"+IntegerToString((long)serverTime/86400)+".csv";
   int f=FileOpen(path,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
   if(f==INVALID_HANDLE){boClockObservationWriteFailed=true;return accepted;}
   bool ok=true;
   if(FileSize(f)==0)ok=FileWrite(f,"contract","session","sequence","mode","origin","account","server_hash","symbol",
      "accepted","quote_server_seconds","terminal_server_seconds","pc_local_seconds","pc_utc_seconds","mono_ms",
      "previous_base_ms","previous_mono_ms","previous_tick_ms","estimate_ms","quote_minus_estimate_ms","result_ms","clock_after_ms")>0;
   if(!FileSeek(f,0,SEEK_END))ok=false;
   if(ok)ok=FileWrite(f,"V227_CLOCK_OBSERVATION_V1",boClockObservationSession,boClockObservationSequence+1,boClockObservationMode,
      IsTesting() ? "BACKTEST_MT4" : "LIVE_MT4",AccountNumber(),BOHashText(AccountServer()),Symbol(),accepted ? 1 : 0,
      (long)serverTime,(long)terminalTime,(long)localTime,(long)utcTime,mono,previousBase,previousMono,previousTick,
      estimate,(long)serverTime*1000-estimate,nowMs,boClockBaseMs)>0;
   FileFlush(f);FileClose(f);
   if(ok){boClockObservationSequence++;if(accepted)boClockObservationLastAccepted=(long)serverTime;}
   else boClockObservationWriteFailed=true;
   return accepted;
}
#endif
