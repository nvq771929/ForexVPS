#ifndef BO_V222_MARKET_CONTEXT
#define BO_V222_MARKET_CONTEXT
#include "DemoLearning.mqh"
// Observation only. No BOConfig/BORuntimeState writes and no broker/network API.
bool boContextClockValid=false,boContextWriteFailed=false,boContextReadTried=false;
int boContextOffset=0,boContextSamples=0,boContextProposed=0;
uint boContextReadMono=0;
uint boContextCalibratedMono=0;
const long BO_CONTEXT_CLOCK_TTL_MS=900000;
long boContextCreated=0,boContextExpires=0,boContextNewsReceived=0,boContextNewsExpires=0,boContextFrom=0,boContextTo=0;
int boContextRows=0;
long boContextStart[512],boContextEnd[512];
string boContextKind[512],boContextLabel[512];
long boContextEventTime[512];
string boContextEventId[512],boContextCurrency[512],boContextImpact[512],boContextTracking[512];
string boContextProvider="UNKNOWN",boContextNewsPolicy="UNKNOWN";
int boContextScope=-1,boContextTracked=-1,boContextSelected=-1;
string boNewsAlertKey="";bool boNewsAlertFailed=false;
string boContextMeta="NEWS_UNKNOWN",boContextSnapshot="NO_NEWS";

void BOContextReset() {
   boContextClockValid=false;boContextWriteFailed=false;boContextReadTried=false;boContextReadMono=0;
   boContextOffset=0;boContextSamples=0;boContextProposed=0;boContextRows=0;boContextCalibratedMono=0;
   boContextCreated=0;boContextExpires=0;boContextNewsReceived=0;boContextNewsExpires=0;boContextFrom=0;boContextTo=0;
   boContextMeta="NEWS_UNKNOWN";boContextSnapshot="NO_NEWS";
   boContextProvider="UNKNOWN";boContextNewsPolicy="UNKNOWN";boContextScope=-1;boContextTracked=-1;boContextSelected=-1;boNewsAlertKey="";boNewsAlertFailed=false;
}
void BOContextClockTick(long nowMs) {
   if(IsTesting()) { boContextClockValid=false;return; }
   if(boContextClockValid && (long)(uint)(GetTickCount()-boContextCalibratedMono)>BO_CONTEXT_CLOCK_TTL_MS) {
      boContextClockValid=false;boContextSamples=0;
   }
   long utc=(long)TimeGMT();
   long delta=nowMs/1000-utc;
   int offset=(int)(MathRound(delta/900.0)*900);
   if(utc<=0 || MathAbs(delta-offset)>3 || MathAbs(offset)>14*3600) { boContextClockValid=false;boContextSamples=0;return; }
   if(boContextSamples==0 || offset!=boContextProposed) { boContextProposed=offset;boContextSamples=1;boContextClockValid=false; }
   else if(boContextSamples<3)boContextSamples++;
   if(boContextSamples>=3) { boContextOffset=offset;boContextClockValid=true;boContextCalibratedMono=GetTickCount(); }
}
long BOContextCalibrationAge() {
   return boContextSamples>=3 ? (long)(uint)(GetTickCount()-boContextCalibratedMono) : -1;
}
long BOContextUTC(long observedMs) {
   if(IsTesting() || !boContextClockValid || boLastTickMs<=0 || observedMs<boLastTickMs)return 0;
   if(BOContextCalibrationAge()>BO_CONTEXT_CLOCK_TTL_MS) { boContextClockValid=false;boContextSamples=0;return 0; }
   long utcMs=observedMs-(long)boContextOffset*1000;
   if(MathAbs((double)(utcMs-(long)TimeGMT()*1000))>5000) { boContextClockValid=false;boContextSamples=0;return 0; }
   return utcMs;
}
void BOContextRefresh(string root,const BORuntimeState &s,uint policy,int horizon) {
   if(IsTesting())return;
   uint mono=GetTickCount();if(boContextReadTried && (uint)(mono-boContextReadMono)<15000)return;
   boContextReadTried=true;boContextReadMono=mono;
   int file=FileOpen(root+"\\context_schedule_v216.csv",FILE_READ|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
   if(file==INVALID_HANDLE)return;
   string expected[25]={"schema","config","feed","policy","horizon","created","expires","kind","start","end","label",
      "news_received","news_expires","coverage_from","coverage_to","snapshot_id","event_utc","event_id","currency","impact","tracking_reason",
      "provider","news_policy","scope_count","tracked_count"};
   string cells[];ArrayResize(cells,25);int columns=0;bool ok=true;
   while(columns<25 && !FileIsEnding(file)) {
      cells[columns]=FileReadString(file);columns++;
      if(FileIsLineEnding(file))break;
   }
   if((columns!=16 && columns!=25) || !FileIsLineEnding(file))ok=false;
   if(ok)for(int j=0;j<columns;j++)if(cells[j]!=expected[j])ok=false;
   int count=0;
   // Incomplete/foreign policy replacements cannot advertise a clear calendar.
   boContextRows=0;boContextCreated=0;boContextExpires=0;boContextScope=-1;boContextTracked=-1;
   long created=0,expires=0;
   while(ok && !FileIsEnding(file)) {
      if(!BODemoReadCells(file,columns,cells)) { ok=false;break; }
      if(StringToInteger(cells[0])!=(columns==25 ? 2 : 1) || (uint)StringToInteger(cells[1])!=s.configHash || (uint)StringToInteger(cells[2])!=s.feedHash ||
         (uint)StringToInteger(cells[3])!=policy || StringToInteger(cells[4])!=horizon) { ok=false;break; }
      long rowCreated=StringToInteger(cells[5]),rowExpires=StringToInteger(cells[6]);
      if(count==0) {
         if(cells[7]!="META") { ok=false;break; }
         created=rowCreated;expires=rowExpires;
         if(created<=0 || expires<=created || expires-created>1800) { ok=false;break; }
         boContextMeta=cells[10];boContextNewsReceived=StringToInteger(cells[11]);boContextNewsExpires=StringToInteger(cells[12]);
         boContextFrom=StringToInteger(cells[13]);boContextTo=StringToInteger(cells[14]);boContextSnapshot=cells[15];
         boContextProvider=columns==25 ? cells[21] : "LEGACY_HIGH_ONLY";
         boContextNewsPolicy=columns==25 ? cells[22] : "LEGACY_V216";
         if(columns==25) {
            if(!BODemoInteger(cells[23]) || !BODemoInteger(cells[24]) || StringLen(cells[22])!=64) { ok=false;break; }
            boContextScope=(int)StringToInteger(cells[23]);boContextTracked=(int)StringToInteger(cells[24]);
            if(boContextScope<0 || boContextScope>5000 || boContextTracked<0 || boContextTracked>boContextScope) { ok=false;break; }
         }
      } else {
         if(rowCreated!=created || rowExpires!=expires || boContextRows>=512 || (cells[7]!="SESSION" && cells[7]!="NEWS")) { ok=false;break; }
         if(StringToInteger(cells[11])!=boContextNewsReceived || StringToInteger(cells[12])!=boContextNewsExpires ||
            StringToInteger(cells[13])!=boContextFrom || StringToInteger(cells[14])!=boContextTo || cells[15]!=boContextSnapshot) { ok=false;break; }
         if(columns==25 && (cells[21]!=boContextProvider || cells[22]!=boContextNewsPolicy || StringToInteger(cells[23])!=boContextScope || StringToInteger(cells[24])!=boContextTracked)) { ok=false;break; }
         long start=StringToInteger(cells[8]),end=StringToInteger(cells[9]);
         if(start<=0 || end<=start) { ok=false;break; }
         long eventTime=columns==25 ? StringToInteger(cells[16]) : start+900;
         if(cells[7]=="NEWS" && columns==25 && (eventTime<start || eventTime>end || StringLen(cells[17])!=24 ||
            (cells[18]!="EUR" && cells[18]!="USD") || (cells[19]!="High" && cells[19]!="Medium" && cells[19]!="Low") ||
            (cells[20]!="IMPACT_HIGH" && cells[20]!="IMPACT_MEDIUM" && cells[20]!="IMPACT_LOW" && cells[20]!="PRIORITY_EVENT"))) { ok=false;break; }
         boContextStart[boContextRows]=start;boContextEnd[boContextRows]=end;boContextKind[boContextRows]=cells[7];boContextLabel[boContextRows]=cells[10];
         boContextEventTime[boContextRows]=eventTime;boContextEventId[boContextRows]=columns==25 ? cells[17] : cells[10];
         boContextCurrency[boContextRows]=columns==25 ? cells[18] : "";boContextImpact[boContextRows]=columns==25 ? cells[19] : "High";
         boContextTracking[boContextRows]=columns==25 ? cells[20] : "LEGACY_HIGH_ONLY";boContextRows++;
      }
      count++;
   }
   FileClose(file);
   if(ok && count>1) { boContextCreated=created;boContextExpires=expires; }
   else { boContextRows=0;boContextCreated=0;boContextExpires=0; }
}
int BOContextMask(long utc) {
   long reference=(long)TimeGMT();
   if(utc<=0 || boContextCreated<=0 || reference<boContextCreated || reference>boContextExpires)return -1;
   int mask=0;
   for(int i=0;i<boContextRows;i++)if(boContextKind[i]=="SESSION" && utc>=boContextStart[i] && utc<boContextEnd[i]) {
      string name=boContextLabel[i];if(name=="TOKYO" || name=="SYDNEY")mask|=1;
      else if(name=="LONDON")mask|=2;else if(name=="NEW_YORK")mask|=4;
   }
   return mask;
}
string BOContextSession(int mask) {
   if(mask<0)return "SESSION_UNKNOWN";
   if(mask==1)return "ASIA";if(mask==2)return "LONDON";if(mask==3)return "ASIA_LONDON";
   if(mask==4)return "NEW_YORK";if(mask==5)return "ASIA_NEW_YORK";if(mask==6)return "LONDON_NEW_YORK";
   if(mask==7)return "ASIA_LONDON_NEW_YORK";return "OFF_WINDOW";
}
string BOContextNews(long nowUtc,long entry,long expiry,string &detail,long &eventUtc) {
   detail="NONE";eventUtc=0;boContextSelected=-1;
   if(nowUtc<=0)return "NEWS_CLOCK_UNCERTAIN";
   if(boContextCreated<=0 || nowUtc<boContextCreated || nowUtc>boContextExpires || boContextNewsReceived<=0)return "NEWS_UNKNOWN";
   if(nowUtc<boContextNewsReceived)return "NEWS_CLOCK_UNCERTAIN";
   if(nowUtc>boContextNewsExpires)return "NEWS_STALE";
   if(entry<boContextFrom || expiry>=boContextTo || entry>expiry)return "NEWS_UNKNOWN";
   if(boContextMeta=="NEWS_TIME_UNCERTAIN" || boContextMeta=="NEWS_NO_RELEVANT_EVENTS" || boContextMeta=="NEWS_NO_TRACKED_EVENTS")return boContextMeta;
   if(boContextMeta!="AVAILABLE")return "NEWS_UNKNOWN";
   long distance=0;
   for(int i=0;i<boContextRows;i++)if(boContextKind[i]=="NEWS" && entry<=boContextEnd[i] && expiry>=boContextStart[i]) {
      long d=(long)MathAbs((double)(boContextEventTime[i]-entry));
      if(boContextSelected<0 || d<distance) { boContextSelected=i;distance=d; }
   }
   if(boContextSelected>=0) {
      detail=boContextEventId[boContextSelected];eventUtc=boContextEventTime[boContextSelected];return "NEWS_RISK_WINDOW";
   }
   for(int j=0;j<boContextRows;j++)if(boContextKind[j]=="NEWS" && boContextEventTime[j]>=nowUtc && (boContextSelected<0 || boContextEventTime[j]<eventUtc)) {
      boContextSelected=j;detail=boContextEventId[j];eventUtc=boContextEventTime[j];
   }
   return "NEWS_CLEAR";
}

// One durable notification intent per event/time/policy; never evidence of delivery or a trade.
bool BOContextNewsAlert(string root,long nowMs,long targetBroker,int horizon,string &warning) {
   warning="";if(IsTesting())return false;
   long utc=BOContextUTC(nowMs)/1000,entry=utc>0 ? (long)MathMax(utc,targetBroker-boContextOffset) : 0;
   string detail;long eventTime=0;
   if(BOContextNews(utc,entry,entry+horizon*300,detail,eventTime)!="NEWS_RISK_WINDOW" || boContextSelected<0)return false;
   string identity=detail+"|"+IntegerToString(eventTime)+"|"+boContextNewsPolicy;
   if(identity==boNewsAlertKey)return false;
   string id=StringLen(detail)>=24 ? StringSubstr(detail,0,24) : IntegerToString((long)BOHashText(detail));
   if(!BOSafeTag(id))id=IntegerToString((long)BOHashText(detail));
   string path=root+"\\news_alert_v222_"+id+"_"+IntegerToString(eventTime)+"_"+StringSubstr(boContextNewsPolicy,0,12)+".csv";
   if(FileIsExist(path)) {
      int prior=FileOpen(path,FILE_READ|FILE_CSV|FILE_ANSI,',');string header[];string row[];
      bool valid=prior!=INVALID_HANDLE;
      if(valid)valid=BODemoReadCells(prior,6,header) && BODemoReadCells(prior,6,row) && FileIsEnding(prior);
      if(valid)valid=header[0]=="schema" && header[1]=="event_id" && header[2]=="event_utc" && header[3]=="policy" && header[4]=="attempt_utc" && header[5]=="delivery" &&
         row[0]=="1" && row[1]==detail && StringToInteger(row[2])==eventTime && row[3]==boContextNewsPolicy && row[5]=="UNCONFIRMED";
      if(prior!=INVALID_HANDLE)FileClose(prior);
      if(valid)boNewsAlertKey=identity;else boNewsAlertFailed=true;
      return false;
   }
   string temp=path+".tmp";if(FileIsExist(temp)) { boNewsAlertFailed=true;return false; }
   int file=FileOpen(temp,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(file==INVALID_HANDLE) { boNewsAlertFailed=true;return false; }
   bool ok=FileWrite(file,"schema","event_id","event_utc","policy","attempt_utc","delivery")>0;
   if(ok)ok=FileWrite(file,1,detail,eventTime,boContextNewsPolicy,utc,"UNCONFIRMED")>0;
   FileFlush(file);FileClose(file);
   if(!ok || !FileMove(temp,0,path,0)) { boNewsAlertFailed=true;return false; }
   boNewsAlertKey=identity;
   int i=boContextSelected;
   warning="LICH TIN QUAN SAT | "+boContextCurrency[i]+" "+boContextImpact[i]+" | "+boContextLabel[i]+" | "+
      TimeToString((datetime)(eventTime+25200),TIME_DATE|TIME_SECONDS)+" VN"+
      (boContextTracking[i]=="PRIORITY_EVENT" ? " | UU TIEN" : "");
   return true;
}
void BOContextRecord(string root,string session,const BORuntimeState &s,const BOEvent &event,uint policy,int horizon) {
   if(event.kind!=BO_ANCHOR_EVENT && event.kind!=BO_LOCK_EVENT && event.kind!=BO_ENTRY_EVENT && event.kind!=BO_OUTCOME_EVENT)return;
   long calibrationAge=BOContextCalibrationAge();
   long utcMs=BOContextUTC(event.observedMs),utc=utcMs/1000;
   long entry=utc>0 ? (long)event.targetTime-boContextOffset : 0,expiry=entry>0 ? entry+horizon*300 : 0;
   string detail="";long newsTime=0;string news=BOContextNews(utc,entry,expiry,detail,newsTime);
   int file=FileOpen(root+"\\market_context_"+session+".csv",FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
   if(file==INVALID_HANDLE) { boContextWriteFailed=true;return; }
   bool ok=true;
   if(FileSize(file)==0)ok=FileWrite(file,"schema","logic","sequence","analysis_start","event_kind","observed_ms","config_hash","feed_hash","policy_hash","horizon",
      "clock_status","offset_seconds","utc_ms","utc_reference_seconds","session_mask","session_label","entry_mask","expiry_mask","snapshot_created_utc",
      "news_status","news_event_id","news_event_utc","snapshot_id","mode","clock_calibration_age_ms","clock_calibration_ttl_ms")>0;
   if(!FileSeek(file,0,SEEK_END))ok=false;
   if(ok)ok=FileWrite(file,2,2026101707,s.sequence,(long)event.analysisStart,event.kind,event.observedMs,s.configHash,s.feedHash,policy,horizon,
      utcMs>0 ? "UTC_ESTIMATED_FROM_PC" : "CLOCK_UNKNOWN",boContextOffset,utcMs,(long)TimeGMT(),BOContextMask(utc),BOContextSession(BOContextMask(utc)),
      BOContextMask(entry),BOContextMask(expiry),boContextCreated,news,detail,newsTime,boContextSnapshot,"OBSERVE_ONLY",calibrationAge,BO_CONTEXT_CLOCK_TTL_MS)>0;
   FileFlush(file);FileClose(file);if(!ok)boContextWriteFailed=true;
}
#endif
