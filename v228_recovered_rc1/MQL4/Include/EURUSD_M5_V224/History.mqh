#ifndef BO_V222_HISTORY
#define BO_V222_HISTORY
#include "Contract.mqh"

// MT4 owns the HST cache and broker history downloads. CopyRates is used in the
// indicator/EA sandbox; never open an absolute HST path or fabricate missing bars.
bool boHistoryReady=false,boHistoryTried=false;
datetime boHistoryBar=0;
uint boHistoryAttemptMono=0;
int boHistoryM5Count=0,boHistoryM1Count=0,boHistoryM5Error=0,boHistoryM1Error=0;
string boHistoryStatus="DANG_DONG_BO",boHistorySource="NONE",boHistoryLogged="";
BOBar boHistoryBars[];
const int BO_HISTORY_RETRY_SECONDS=5;

bool BOHistoryRateValid(const MqlRates &rate) {
   return MathIsValidNumber(rate.open) && MathIsValidNumber(rate.high) && MathIsValidNumber(rate.low) &&
      MathIsValidNumber(rate.close) && rate.low>0 && rate.low<=MathMin(rate.open,rate.close) &&
      rate.high>=MathMax(rate.open,rate.close) && rate.high>=rate.low;
}
bool BOHistoryUseM5(const MqlRates &rates[],int count,datetime bar,BOBar &out[]) {
   if(bar<=0 || bar%300!=0 || count!=BO_HISTORY || ArraySize(rates)!=count) return false;
   datetime first=bar-BO_HISTORY*300;
   for(int i=0;i<count;i++)
      if(rates[i].time!=first+i*300 || !BOHistoryRateValid(rates[i])) return false;
   if(ArrayResize(out,BO_HISTORY)!=BO_HISTORY) return false;
   for(int i=0;i<BO_HISTORY;i++) {
      out[i].time=rates[i].time; out[i].open=rates[i].open; out[i].high=rates[i].high;
      out[i].low=rates[i].low; out[i].close=rates[i].close; out[i].ticks=rates[i].tick_volume;
   }
   return true;
}
bool BOHistoryUseM1(const MqlRates &rates[],int count,datetime bar,BOBar &out[]) {
   if(bar<=0 || bar%300!=0 || count!=BO_HISTORY*5 || ArraySize(rates)!=count) return false;
   datetime first=bar-BO_HISTORY*300;
   for(int j=0;j<count;j++)
      if(rates[j].time!=first+j*60 || !BOHistoryRateValid(rates[j])) return false;
   if(ArrayResize(out,BO_HISTORY)!=BO_HISTORY) return false;
   for(int i=0;i<BO_HISTORY;i++) {
      int offset=i*5;
      out[i].time=rates[offset].time; out[i].open=rates[offset].open;
      out[i].high=rates[offset].high; out[i].low=rates[offset].low;
      out[i].close=rates[offset+4].close; out[i].ticks=0;
      for(int k=0;k<5;k++) {
         out[i].high=MathMax(out[i].high,rates[offset+k].high);
         out[i].low=MathMin(out[i].low,rates[offset+k].low);
         out[i].ticks+=rates[offset+k].tick_volume;
      }
   }
   return true;
}
void BOHistoryReset() {
   boHistoryReady=false; boHistoryTried=false; boHistoryBar=0; boHistoryAttemptMono=0;
   boHistoryM5Count=0; boHistoryM1Count=0; boHistoryM5Error=0; boHistoryM1Error=0;
   boHistoryStatus="DANG_DONG_BO"; boHistorySource="NONE"; boHistoryLogged=""; ArrayResize(boHistoryBars,0);
}
bool BOHistoryRefresh(bool force=false) {
   datetime bar=iTime(NULL,PERIOD_M5,0);
   uint mono=GetTickCount();
   if(!force && boHistoryTried && bar==boHistoryBar &&
      (uint)(mono-boHistoryAttemptMono)<(uint)(BO_HISTORY_RETRY_SECONDS*1000)) return false;
   // A ready packet is immutable for this M5 bar; refresh only on a new bar or
   // reconnection. A disconnected terminal must not advertise historical readiness.
   if(!force && boHistoryReady && bar==boHistoryBar && IsConnected()) return false;
   boHistoryTried=true; boHistoryAttemptMono=mono; boHistoryBar=bar;
   boHistoryReady=false; boHistorySource="NONE"; ArrayResize(boHistoryBars,0);
   boHistoryM5Count=0; boHistoryM1Count=0; boHistoryM5Error=0; boHistoryM1Error=0;
   if(!IsConnected()) { boHistoryStatus="CHO_KET_NOI_MT4"; return true; }
   if(bar<=0 || bar%300!=0 || bar!=(datetime)(((long)TimeCurrent()/300)*300)) {
      MqlRates bootstrap[]; ArraySetAsSeries(bootstrap,false);
      ResetLastError(); boHistoryM5Count=CopyRates(Symbol(),PERIOD_M5,0,BO_HISTORY+1,bootstrap);
      boHistoryM5Error=GetLastError(); boHistoryStatus=bar>0 ? "CHO_NEN_M5_CAP_NHAT" : "DANG_DONG_BO"; return true;
   }
   datetime first=bar-BO_HISTORY*300,last=bar-1;
   MqlRates m5[]; ArraySetAsSeries(m5,false);
   ResetLastError(); boHistoryM5Count=CopyRates(Symbol(),PERIOD_M5,first,last,m5); boHistoryM5Error=GetLastError();
   if(BOHistoryUseM5(m5,boHistoryM5Count,bar,boHistoryBars)) {
      boHistoryReady=true; boHistorySource="MT4_M5"; boHistoryStatus="SAN_SANG"; return true;
   }
   MqlRates m1[]; ArraySetAsSeries(m1,false);
   ResetLastError(); boHistoryM1Count=CopyRates(Symbol(),PERIOD_M1,first,last,m1); boHistoryM1Error=GetLastError();
   if(BOHistoryUseM1(m1,boHistoryM1Count,bar,boHistoryBars)) {
      boHistoryReady=true; boHistorySource="MT4_M1_COMPLETE"; boHistoryStatus="SAN_SANG"; return true;
   }
   boHistoryStatus=(boHistoryM5Count<0 || boHistoryM1Count<0 || boHistoryM5Error==4066 || boHistoryM1Error==4066)
      ? "DANG_DONG_BO" : "THIEU_NEN_TRONG_LICH_SU";
   return true;
}
bool BOHistoryCopy(datetime bar,BOBar &out[]) {
   if(!boHistoryReady || boHistoryBar!=bar || ArraySize(boHistoryBars)!=BO_HISTORY || !IsConnected()) return false;
   if(ArrayResize(out,BO_HISTORY)!=BO_HISTORY) return false;
   for(int i=0;i<BO_HISTORY;i++) out[i]=boHistoryBars[i];
   return true;
}
bool BOLogHistoryStatus(string root,string session) {
   string signature=IntegerToString((long)boHistoryBar)+"|"+boHistoryStatus+"|"+boHistorySource+"|"+
      IntegerToString(boHistoryM5Count)+"|"+IntegerToString(boHistoryM1Count)+"|"+
      IntegerToString(boHistoryM5Error)+"|"+IntegerToString(boHistoryM1Error);
   if(signature==boHistoryLogged) return true;
   int file=FileOpen(root+"\\history_"+session+".csv",FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(file==INVALID_HANDLE) return false;
   bool ok=true;
   if(FileSize(file)==0 && FileWrite(file,"schema","logic_version","session","observed_broker_seconds","analysis_bar",
      "status","source","m5_count","m1_count","m5_error","m1_error","retry_seconds")==0) ok=false;
   FileSeek(file,0,SEEK_END);
   if(FileWrite(file,BO_SCHEMA,BO_LOGIC_VERSION,session,(long)TimeCurrent(),(long)boHistoryBar,
      boHistoryStatus,boHistorySource,boHistoryM5Count,boHistoryM1Count,boHistoryM5Error,boHistoryM1Error,BO_HISTORY_RETRY_SECONDS)==0) ok=false;
   FileFlush(file); FileClose(file);
   if(ok) boHistoryLogged=signature;
   return ok;
}
#endif
