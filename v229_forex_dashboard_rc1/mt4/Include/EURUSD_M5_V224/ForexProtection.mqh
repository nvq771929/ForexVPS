#ifndef FX_V222_PROTECTION
#define FX_V222_PROTECTION
// Separate Forex management contract; never changes Binary features or outcomes.
int fxRiskTickets[]; long fxRiskTimes[]; double fxRiskNets[];
int fxDailyAttempts=0,fxLossStreak=0; long fxLatestExit=0,fxNextModifyMs=0;
string fxProtectionStatus="WAITING";

bool FXReadState(string path,string contract,string &payload) {
   int f=FileOpen(path,FILE_READ|FILE_CSV|FILE_ANSI,',');
   if(f==INVALID_HANDLE){FXStorageFailure();return false;}
   string kind=FileReadString(f);payload=FileReadString(f);
   string hash=FileReadString(f);bool end=FileIsEnding(f);FileClose(f);
   if(kind!=contract || hash!=IntegerToString((long)BOHashText(payload)) || !end){FXStorageFailure();return false;}
   return true;
}
bool FXSaveState(string path,string contract,string payload) {
   int f=FileOpen(path,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(f==INVALID_HANDLE){FXStorageFailure();return false;}
   bool ok=FileWrite(f,contract,payload,BOHashText(payload))>0;FileFlush(f);FileClose(f);
   if(!ok)FXStorageFailure();return ok;
}
bool FXScheduleEntry(long now) {
   if(!fxSettings.schedule)return true;
   // Calendar arithmetic on broker coordinates. No PC clock or Tester TimeGMT.
   int day=(int)((now/86400+4)%7),minute=(int)((now%86400)/60);
   if(day==0 || day==6){fxStatus="WEEKEND_NO_ENTRY";return false;}
   if(day==5 && minute>=fxSettings.fridayStopMinute){fxStatus="FRIDAY_NO_ENTRY";return false;}
   int a=fxSettings.rolloverStartMinute,b=fxSettings.rolloverEndMinute;
   bool rollover=a<b ? minute>=a && minute<b : a>b && (minute>=a || minute<b);
   if(rollover){fxStatus="ROLLOVER_NO_ENTRY";return false;}return true;
}
bool FXFridayExit(long now) {
   int day=(int)((now/86400+4)%7),minute=(int)((now%86400)/60);
   return fxSettings.schedule && (day==6 || day==0 || (day==5 && minute>=fxSettings.fridayCloseMinute));
}
bool FXLoadRiskExits() {
   ArrayResize(fxRiskTickets,0);ArrayResize(fxRiskTimes,0);ArrayResize(fxRiskNets,0);
   string path=fxRoot+"\\risk_exits.csv";if(!FileIsExist(path))return true;
   int f=FileOpen(path,FILE_READ|FILE_CSV|FILE_ANSI,',');if(f==INVALID_HANDLE){FXStorageFailure();return false;}
   bool ok=true;
   while(!FileIsEnding(f)) {
      string ticket=FileReadString(f),closed=FileReadString(f),net=FileReadString(f),hash=FileReadString(f);
      int id=(int)StringToInteger(ticket);long time=StringToInteger(closed);double value=StringToDouble(net);
      if(id<=0 || time<=0 || !MathIsValidNumber(value) || ticket!=IntegerToString(id) || closed!=IntegerToString(time) ||
         net!=DoubleToString(value,2) || hash!=IntegerToString((long)BOHashText(ticket+"|"+closed+"|"+net))){ok=false;break;}
      int n=ArraySize(fxRiskTickets);for(int i=0;i<n;i++)if(fxRiskTickets[i]==id)ok=false;
      if(!ok)break;
      if(ArrayResize(fxRiskTickets,n+1)!=n+1 || ArrayResize(fxRiskTimes,n+1)!=n+1 || ArrayResize(fxRiskNets,n+1)!=n+1){ok=false;break;}
      fxRiskTickets[n]=id;fxRiskTimes[n]=time;fxRiskNets[n]=value;
   }
   FileClose(f);if(!ok)FXStorageFailure();return ok;
}
void FXRegisterExit(int ticket,long closed,double net) {
   if(!fxHealthy)return;
   int n=ArraySize(fxRiskTickets);for(int i=0;i<n;i++)if(fxRiskTickets[i]==ticket)return;
   string payload=IntegerToString(ticket)+"|"+IntegerToString(closed)+"|"+DoubleToString(net,2);
   int f=FileOpen(fxRoot+"\\risk_exits.csv",FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(f==INVALID_HANDLE){FXStorageFailure();return;}
   FileSeek(f,0,SEEK_END);bool ok=FileWrite(f,ticket,closed,DoubleToString(net,2),BOHashText(payload))>0;FileFlush(f);FileClose(f);
   if(!ok){FXStorageFailure();return;}
   if(ArrayResize(fxRiskTickets,n+1)!=n+1 || ArrayResize(fxRiskTimes,n+1)!=n+1 || ArrayResize(fxRiskNets,n+1)!=n+1){FXStorageFailure();return;}
   fxRiskTickets[n]=ticket;fxRiskTimes[n]=closed;fxRiskNets[n]=NormalizeDouble(net,2);
}
bool FXRiskEntryGuard(long now,bool reserve=false) {
   fxLatestExit=0;fxLossStreak=0;
   // Walk exits in reverse chronological order, independent of MT4 history enumeration order.
   long beforeTime=2147483647;int beforeTicket=2147483647;
   for(int k=0;k<ArraySize(fxRiskTickets);k++) {
      int best=-1;
      for(int i=0;i<ArraySize(fxRiskTickets);i++)if(fxRiskTimes[i]<beforeTime || (fxRiskTimes[i]==beforeTime && fxRiskTickets[i]<beforeTicket))
         if(best<0 || fxRiskTimes[i]>fxRiskTimes[best] || (fxRiskTimes[i]==fxRiskTimes[best] && fxRiskTickets[i]>fxRiskTickets[best]))best=i;
      if(best<0)break;
      long t=fxRiskTimes[best];if(k==0)fxLatestExit=t;
      if(t>now){fxStatus="EXIT_CLOCK_ANOMALY";return false;}
      if(t/86400!=now/86400 || fxRiskNets[best]>=0)break;
      fxLossStreak++;beforeTime=t;beforeTicket=fxRiskTickets[best];
   }
   if(fxLossStreak>=fxSettings.maxLossStreak){fxStatus="DAILY_LOSS_STREAK_LIMIT";return false;}
   if(fxLatestExit>0 && now-fxLatestExit<fxSettings.cooldownMinutes*60){fxStatus="EXIT_COOLDOWN";return false;}
   string path=fxRoot+"\\attempts_"+IntegerToString(now/86400)+".csv",payload="0";
   if(FileIsExist(path) && !FXReadState(path,"V222_FOREX_ATTEMPTS_V1",payload))return false;
   fxDailyAttempts=(int)StringToInteger(payload);
   if(payload!=IntegerToString(fxDailyAttempts) || fxDailyAttempts<0){FXStorageFailure();return false;}
   if(fxDailyAttempts>=fxSettings.maxDailyAttempts){fxStatus="DAILY_ENTRY_ATTEMPT_LIMIT";return false;}
   if(reserve){fxDailyAttempts++;return FXSaveState(path,"V222_FOREX_ATTEMPTS_V1",IntegerToString(fxDailyAttempts));}
   return true;
}
string FXPositionKey() {
   return IntegerToString(OrderTicket())+"|"+IntegerToString((long)OrderOpenTime())+"|"+IntegerToString(OrderType())+"|"+DoubleToString(OrderOpenPrice(),Digits);
}
bool FXSaveOriginalRisk() {
   double r=MathAbs(OrderOpenPrice()-OrderStopLoss());if(!FXPositive(r))return false;
   return FXSaveState(fxRoot+"\\position_"+IntegerToString(OrderTicket())+".csv","V222_FOREX_POSITION_V1",
      FXPositionKey()+"|"+DoubleToString(r,Digits)+"|"+IntegerToString((long)OrderOpenTime()));
}
bool FXPositionState(double &r,long &birth) {
   string path=fxRoot+"\\position_"+IntegerToString(OrderTicket())+".csv",payload;
   if(!FileIsExist(path)){fxProtectionStatus="ORIGINAL_R_MISSING";return false;}
   if(!FXReadState(path,"V222_FOREX_POSITION_V1",payload))return false;
   string parts[];if(StringSplit(payload,124,parts)!=6){FXStorageFailure();return false;}
   r=StringToDouble(parts[4]);birth=StringToInteger(parts[5]);
   if(!FXPositive(r) || birth<=0 || birth>(long)OrderOpenTime() ||
      payload!=FXPositionKey()+"|"+DoubleToString(r,Digits)+"|"+IntegerToString(birth)){FXStorageFailure();return false;}
   return true;
}
bool FXOriginalRisk(double &r) { long birth=0;return FXPositionState(r,birth); }
bool FXRequestClose(string reason) {
   // Persist BEFORE trying close; partial failures/restarts may only retry this ticket's close.
   int ticket=OrderTicket();FXWriteFlag(fxRoot+"\\close_required_"+IntegerToString(ticket)+".csv",reason);
   fxProtectionStatus="CLOSE_REQUIRED_"+IntegerToString(ticket);return FXCloseSelected(reason);
}
void FXProtectSelected(long now) {
   int ticket=OrderTicket();double originalR=0;
   if(!FXOriginalRisk(originalR)){FXRequestClose("ORIGINAL_R_UNAVAILABLE");return;}
   if(!fxSettings.breakEven && !fxSettings.trailing)return;
   if(now<fxNextModifyMs || !IsConnected() || !IsTradeAllowed() || IsTradeContextBusy())return;
   MqlTick q;if(!SymbolInfoTick(Symbol(),q) || !FXPositive(q.bid) || !FXPositive(q.ask) || q.ask<q.bid ||
      now<(long)q.time*1000 || now-(long)q.time*1000>3000)return;
   double tick=SymbolInfoDouble(Symbol(),SYMBOL_TRADE_TICK_SIZE);
   if(!FXPositive(tick))return;
   int direction=OrderType()==OP_BUY ? 1 : -1;
   double exit=direction>0 ? q.bid : q.ask,entry=OrderOpenPrice(),oldSL=OrderStopLoss(),desired=oldSL;
   double profit=direction*(exit-entry);string reason="";
   if(fxSettings.breakEven && profit>=originalR*fxSettings.breakEvenR) {
      double be=entry+direction*fxSettings.breakEvenOffsetPips*.0001;
      if(direction*(be-desired)>0){desired=be;reason="BREAK_EVEN";}
   }
   if(fxSettings.trailing && profit>=originalR*fxSettings.trailStartR) {
      datetime bar=(datetime)((now/1000/300)*300);
      if(boHistoryReady && boHistoryBar==bar && ArraySize(boHistoryBars)==BO_HISTORY) {
         double atr=BOATR(boHistoryBars,BO_HISTORY-1,14);
         if(FXPositive(atr)){
            double trail=exit-direction*MathMax(atr*fxSettings.trailATR,fxSettings.trailMinPips*.0001);
            if(direction*(trail-desired)>0){desired=trail;reason="ATR_TRAILING";}
         }
      }
   }
   if(reason=="")return;
   // Round away from the current price and respect BOTH stop and freeze levels.
   desired=NormalizeDouble(direction>0 ? MathFloor(desired/tick+1e-9)*tick : MathCeil(desired/tick-1e-9)*tick,Digits);
   int stops=(int)MarketInfo(Symbol(),MODE_STOPLEVEL),freeze=(int)MarketInfo(Symbol(),MODE_FREEZELEVEL);
   double distance=(MathMax(stops,freeze)+2)*Point;
   if(stops<0 || freeze<0 || direction*(exit-desired)<distance || direction*(desired-oldSL)<fxSettings.trailStepPips*.0001-1e-10 ||
      direction*(OrderTakeProfit()-exit)<=distance || direction*(exit-oldSL)<=freeze*Point)return;
   long actual=BONowMs();
   if(actual<(long)q.time*1000 || actual-(long)q.time*1000>3000)return;
   // Protection never moves backwards, and TP remains unchanged.
   fxNextModifyMs=now+5000;
   ResetLastError();bool ok=OrderModify(ticket,entry,desired,OrderTakeProfit(),0,clrNONE);int error=GetLastError();
   fxProtectionStatus=ok ? reason : "MODIFY_RETRY_"+IntegerToString(error);
   FXEvent(ok ? "STOP_MOVED" : "STOP_MODIFY_FAILED",fxProtectionStatus,ticket,OrderLots(),entry,desired,OrderTakeProfit());
}
#endif
