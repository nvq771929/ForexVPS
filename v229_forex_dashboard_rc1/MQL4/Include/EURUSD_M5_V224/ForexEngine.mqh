#ifndef FX_V222_ENGINE
#define FX_V222_ENGINE
#include "ForexRisk.mqh"
// Actual Forex orders are isolated from Binary publications, learners and labels.
FXSettings fxSettings; BOConfig fxConfig; BOPrediction fxEpisode;
string fxRoot="",fxStatus="INITIALIZING"; int fxLease=INVALID_HANDLE;
bool fxStarted=false,fxHealthy=true,fxPaused=false; datetime fxLastStarted=0;
long fxDay=0,fxLastManagement=0; double fxDayEquity=0; bool fxDayHalted=false;
int fxLastTicket=-1; double fxLastLots=0;
int fxClosedTrades=0; double fxClosedNet=0;
int fxCloseTicket=-1,fxCloseFailures=0;long fxCloseDueMs=0;
int FXSlippagePoints() {
   // A maximum is rounded down: a 0.3-pip limit on a 4-digit feed is 0 points,
   // not 1 point (1 pip). Market-execution brokers may still ignore deviation.
   return (int)MathFloor(fxSettings.slippagePips*.0001/Point+1e-9);
}

bool FXOwnSelected() { return OrderSymbol()==Symbol() && OrderMagicNumber()==fxSettings.magic && (OrderType()==OP_BUY || OrderType()==OP_SELL); }
bool FXAnyEURUSDOrder() {
   for(int i=OrdersTotal()-1;i>=0;i--) if(OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) {
      string name=OrderSymbol();StringToUpper(name);
      if(StringFind(name,"EURUSD")==0) return true; // Includes manual/other-EA positions and pending orders.
   }
   return false;
}
bool FXHasManagedOrders(int magic) {
   for(int i=OrdersTotal()-1;i>=0;i--) if(OrderSelect(i,SELECT_BY_POS,MODE_TRADES) && OrderSymbol()==Symbol() && OrderMagicNumber()==magic) return true;
   return false;
}
bool FXHasForeignMagicOrders(int magic) {
   for(int i=OrdersTotal()-1;i>=0;i--) if(OrderSelect(i,SELECT_BY_POS,MODE_TRADES) && OrderSymbol()==Symbol() &&
      OrderMagicNumber()!=magic && (StringFind(OrderComment(),"FX222:")==0 || StringFind(OrderComment(),"FX222A:")==0 || StringFind(OrderComment(),"FX221:")==0 || StringFind(OrderComment(),"FX220:")==0))return true;
   return false;
}
void FXStorageFailure() { fxHealthy=false;fxStatus="STORAGE_ERROR_ENTRIES_BLOCKED";Print("FX V222 storage failed; entries blocked. Existing broker SL/TP remains; own-position management continues."); }
bool FXEvent(string kind,string detail,int ticket=-1,double lots=0,double price=0,double stop=0,double take=0,double risk=0) {
   int f=FileOpen(fxRoot+"\\forex_events.csv",FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
   if(f==INVALID_HANDLE) { FXStorageFailure();return false; }
   bool ok=true;
   if(FileSize(f)==0) ok=FileWrite(f,"contract","broker_seconds","kind","detail","ticket","lots","price","sl","tp","planned_risk","currency")>0;
   FileSeek(f,0,SEEK_END);
   if(ok)ok=FileWrite(f,"V222_FOREX_EXECUTION_V1",(long)TimeCurrent(),kind,detail,ticket,DoubleToString(lots,8),
      DoubleToString(price,Digits),DoubleToString(stop,Digits),DoubleToString(take,Digits),DoubleToString(risk,2),AccountCurrency())>0;
   FileFlush(f);FileClose(f);if(!ok)FXStorageFailure();return ok;
}
bool FXWriteFlag(string path,string label) {
   if(FileIsExist(path)) return true;
   int f=FileOpen(path,FILE_WRITE|FILE_CSV|FILE_ANSI,',');if(f==INVALID_HANDLE) { FXStorageFailure();return false; }
   bool ok=FileWrite(f,"V222_FOREX_EXECUTION_V1",label,(long)TimeCurrent())>0;FileFlush(f);FileClose(f);
   if(!ok)FXStorageFailure();return ok;
}
bool FXDayGuard(long now) {
   long day=now/86400;
   if(day!=fxDay || fxDayEquity<=0) {
      fxDay=day;fxDayEquity=0;fxDayHalted=false;
      string path=fxRoot+"\\risk_day_"+IntegerToString(day)+".csv";
      if(FileIsExist(path)) {
         int f=FileOpen(path,FILE_READ|FILE_CSV|FILE_ANSI,',');if(f==INVALID_HANDLE){FXStorageFailure();return false;}
         string contract=FileReadString(f);long storedDay=StringToInteger(FileReadString(f));
         double equity=StringToDouble(FileReadString(f));uint storedHash=(uint)StringToInteger(FileReadString(f));FileClose(f);
         string payload=IntegerToString(storedDay)+"|"+DoubleToString(equity,2);
         if(contract!="V222_FOREX_DAY_V1" || storedDay!=day || !FXPositive(equity) || BOHashText(payload)!=storedHash){FXStorageFailure();return false;}
         fxDayEquity=equity;
      } else {
         fxDayEquity=NormalizeDouble(AccountEquity(),2);if(!FXPositive(fxDayEquity)){fxStatus="INVALID_ACCOUNT_EQUITY";return false;}
         int f=FileOpen(path,FILE_WRITE|FILE_CSV|FILE_ANSI,',');if(f==INVALID_HANDLE){FXStorageFailure();return false;}
         string payload=IntegerToString(day)+"|"+DoubleToString(fxDayEquity,2);
         bool ok=FileWrite(f,"V222_FOREX_DAY_V1",day,DoubleToString(fxDayEquity,2),BOHashText(payload))>0;
         FileFlush(f);FileClose(f);if(!ok){FXStorageFailure();return false;}
      }
   }
   string halt=fxRoot+"\\halt_"+IntegerToString(day)+".csv";
   if(FileIsExist(halt))fxDayHalted=true;
   if(!MathIsValidNumber(AccountEquity()) || AccountEquity()<=0 || AccountEquity()<=fxDayEquity*(1-fxSettings.dailyLossPercent/100)) {
      fxDayHalted=true;if(!FXWriteFlag(halt,"DAILY_EQUITY_LIMIT"))return false;
   }
   if(fxDayHalted){fxStatus="DAILY_LOSS_LIMIT";return false;}
   return fxHealthy;
}
bool FXAccountPermission() {
   if(IsTesting())return true;
   long mode=AccountInfoInteger(ACCOUNT_TRADE_MODE);
   if(mode!=ACCOUNT_TRADE_MODE_DEMO && mode!=ACCOUNT_TRADE_MODE_REAL){fxStatus="UNSUPPORTED_ACCOUNT_MODE";return false;}
   if(mode==ACCOUNT_TRADE_MODE_REAL && !fxSettings.allowReal){fxStatus="REAL_TRADING_DISABLED";return false;}
   string server=AccountServer();StringToUpper(server);
   if(StringFind(server,"EXNESS")<0){fxStatus="EXNESS_ACCOUNT_REQUIRED";return false;}
   return true;
}
bool FXCloseSelected(string reason) {
   int ticket=OrderTicket();double lots=OrderLots();int type=OrderType();
   if(!IsConnected() || !IsTradeAllowed() || IsTradeContextBusy())return false;
   MqlTick q;if(!SymbolInfoTick(Symbol(),q) || !FXPositive(q.bid) || !FXPositive(q.ask))return false;
   long now=BONowMs();if(now<(long)q.time*1000 || now-(long)q.time*1000>3000)return false;
   if(ticket==fxCloseTicket && now<fxCloseDueMs)return false;
   ResetLastError();bool ok=OrderClose(ticket,lots,type==OP_BUY ? q.bid : q.ask,FXSlippagePoints(),clrNONE);
   int error=GetLastError();FXEvent(ok ? "CLOSE_SENT" : "CLOSE_FAILED",reason+"_ERR_"+IntegerToString(error),ticket,lots);
   if(ok){fxCloseTicket=-1;fxCloseFailures=0;fxCloseDueMs=0;}
   else {
      if(fxCloseTicket!=ticket)fxCloseFailures=0;
      fxCloseTicket=ticket;fxCloseFailures++;
      long delay=1000;for(int i=1;i<fxCloseFailures && delay<30000;i++)delay*=2;
      fxCloseDueMs=now+(long)MathMin(delay,30000);
   }
   return ok;
}
#include "ForexProtection.mqh"
#include "ForexNews.mqh"
#include "ForexAverage.mqh"
void FXSyncClosed() {
   fxClosedTrades=0;fxClosedNet=0;
   for(int j=OrdersHistoryTotal()-1;j>=0;j--) if(OrderSelect(j,SELECT_BY_POS,MODE_HISTORY) && FXOwnSelected() && OrderCloseTime()>0) {
      double net=OrderProfit()+OrderSwap()+OrderCommission();fxClosedTrades++;fxClosedNet+=net;
      FXRegisterExit(OrderTicket(),(long)OrderCloseTime(),net);
      string path=fxRoot+"\\forex_closed_"+IntegerToString(OrderTicket())+".csv";
      if(FileIsExist(path))continue;
      int f=FileOpen(path,FILE_WRITE|FILE_CSV|FILE_ANSI,',');if(f==INVALID_HANDLE){FXStorageFailure();continue;}
      bool ok=FileWrite(f,"contract","ticket","symbol","magic","type","lots","opened","closed","entry","profit","swap","commission","net","currency")>0;
      if(ok)ok=FileWrite(f,"V222_FOREX_CLOSED_V1",OrderTicket(),OrderSymbol(),OrderMagicNumber(),OrderType(),DoubleToString(OrderLots(),8),
         (long)OrderOpenTime(),(long)OrderCloseTime(),DoubleToString(OrderOpenPrice(),Digits),DoubleToString(OrderProfit(),2),
         DoubleToString(OrderSwap(),2),DoubleToString(OrderCommission(),2),DoubleToString(net,2),AccountCurrency())>0;
      FileFlush(f);FileClose(f);if(!ok)FXStorageFailure();
   }
}
void FXManagePositions() {
   long now=BONowMs();if(now<=0)now=(long)TimeCurrent()*1000;
   if(fxLastManagement>0 && now-fxLastManagement<1000)return;fxLastManagement=now;
   if(FXAverageActive()){FXAverageManage(now);FXSyncClosed();return;}
   for(int i=OrdersTotal()-1;i>=0;i--) if(OrderSelect(i,SELECT_BY_POS,MODE_TRADES) && FXOwnSelected()) {
      if(FileIsExist(fxRoot+"\\close_required_"+IntegerToString(OrderTicket())+".csv"))FXRequestClose("DURABLE_CLOSE_RETRY");
      else if(fxSettings.emergencyClose)FXRequestClose("EMERGENCY_CLOSE_OWN");
      else if(fxSettings.closeOnDailyLoss && fxDayHalted)FXRequestClose("DAILY_EQUITY_LOSS_EXIT");
      else if(OrderStopLoss()<=0 || OrderTakeProfit()<=0) FXRequestClose("MISSING_BROKER_PROTECTION");
      else if(FXFridayExit(now/1000))FXRequestClose("WEEKEND_EXIT");
      else {
         double originalR=0;long birth=0;
         if(!FXPositionState(originalR,birth))FXRequestClose("POSITION_STATE_UNAVAILABLE");
         else if(fxSettings.maxHoldMinutes>0 && now/1000-birth>=fxSettings.maxHoldMinutes*60)FXRequestClose("MAX_HOLD_TIME");
         else if(!FXNewsManageSelected(now))FXProtectSelected(now);
      }
   }
   FXSyncClosed();
}
bool FXSend(BOPrediction &e,long nowMs) {
   fxStatus="ENTRY_CHECK";fxLastTicket=-1;fxLastLots=0;
   if(!fxHealthy || !fxSettings.enabled || fxPaused){fxStatus=fxPaused ? "PAUSED" : "TRADING_DISABLED";return false;}
   if(FileIsExist(fxRoot+"\\execution_review_required.csv")){fxStatus="ORDER_STATE_REVIEW_REQUIRED";return false;}
   if(fxSettings.emergencyClose){fxStatus="EMERGENCY_CLOSE_ACTIVE";return false;}
   if(!BOEntryAllowed(e,fxConfig,nowMs,false)){fxStatus="NATIVE_ENTRY_NOT_ALLOWED";return false;}
   if(!FXAccountPermission() || !FXDayGuard(nowMs/1000))return false;
   FXSyncClosed();
   if(!fxHealthy || !FXScheduleEntry(nowMs/1000) || !FXRiskEntryGuard(nowMs/1000) || !FXNewsEntryAllowed(nowMs))return false;
   if(FXAnyEURUSDOrder()){
      if(fxSettings.averaging)return FXAverageTrySend(e,nowMs);
      fxStatus="EURUSD_ORDER_ALREADY_EXISTS";return false;
   }
   if(!IsConnected() || !IsTradeAllowed() || IsTradeContextBusy() || MarketInfo(Symbol(),MODE_TRADEALLOWED)==0){fxStatus="TERMINAL_TRADING_UNAVAILABLE";return false;}
   MqlTick q;if(!SymbolInfoTick(Symbol(),q)){fxStatus="QUOTE_UNAVAILABLE";return false;}
   long currentMs=BONowMs();
   if(currentMs<nowMs || currentMs>(long)(e.targetTime+fxConfig.boundaryLagSeconds)*1000 || currentMs<(long)q.time*1000 ||
      currentMs-(long)q.time*1000>3000){fxStatus="ENTRY_QUOTE_TOO_OLD_OR_LATE";return false;}
   FXPlan plan;string why;
   double capital=MathMin(AccountBalance(),AccountEquity());
   FXSettings sizing=fxSettings;double basketCap=0;
   if(fxSettings.averaging){basketCap=FXAverageBudget();sizing.riskPercent=capital>0 ? basketCap*fxSettings.initialRiskFraction/capital*100 : 0;}
   if(!FXBuildPlan(sizing,e.action,q.bid,q.ask,e.anchor.volatility.atr,e.candidate.invalidation,capital,
      SymbolInfoDouble(Symbol(),SYMBOL_TRADE_TICK_SIZE),MarketInfo(Symbol(),MODE_TICKVALUE),MarketInfo(Symbol(),MODE_MINLOT),
      MarketInfo(Symbol(),MODE_LOTSTEP),MarketInfo(Symbol(),MODE_MAXLOT),Point,Digits,(int)MarketInfo(Symbol(),MODE_STOPLEVEL),plan,why)){
      fxStatus=why;return false;
   }
   int cmd=plan.direction>0 ? OP_BUY : OP_SELL;
   ResetLastError();double remaining=AccountFreeMarginCheck(Symbol(),cmd,plan.lots);int error=GetLastError();
   if(!FXPositive(remaining) || error!=0){fxStatus="INSUFFICIENT_MARGIN";return false;}
   if(!FXMarginReserve(plan.lots,remaining,q.bid,q.ask))return false;
   string intent=fxRoot+"\\intent_"+IntegerToString((long)e.targetTime)+".csv";
   if(FileIsExist(intent)){fxStatus="ENTRY_ALREADY_ATTEMPTED";return false;}
   if(!FXRiskEntryGuard(nowMs/1000,true))return false;
   // Durable at-most-one attempt. An ambiguous timeout is never blindly retried.
   if(!FXWriteFlag(intent,"ATTEMPT_RESERVED"))return false;
   if(!FXEvent("ORDER_INTENT","PRE_SEND",-1,plan.lots,plan.price,plan.stop,plan.take,plan.plannedRisk))return false;
   currentMs=BONowMs();if(currentMs>(long)(e.targetTime+fxConfig.boundaryLagSeconds)*1000){fxStatus="STORAGE_DELAY_MISSED_ENTRY";return false;}
   if(FXAnyEURUSDOrder()){fxStatus="EURUSD_ORDER_ALREADY_EXISTS";return false;}
   if(!FXAccountPermission())return false;
   if(!FXNewsEntryAllowed(currentMs))return false;
   currentMs=BONowMs();
   if(currentMs>(long)(e.targetTime+fxConfig.boundaryLagSeconds)*1000 || currentMs<(long)q.time*1000 || currentMs-(long)q.time*1000>3000){fxStatus="FINAL_QUOTE_TOO_OLD_OR_LATE";return false;}
   if(!IsConnected() || !IsTradeAllowed() || IsTradeContextBusy()){fxStatus="TERMINAL_TRADING_UNAVAILABLE";return false;}
   // Never send a naked order as a fallback for broker error 130 / ECN rejection.
   ResetLastError();int ticket=OrderSend(Symbol(),cmd,plan.lots,plan.price,FXSlippagePoints(),
      plan.stop,plan.take,"FX222:"+IntegerToString((long)e.targetTime),fxSettings.magic,0,clrNONE);
   error=GetLastError();fxLastTicket=ticket;fxLastLots=plan.lots;
   if(ticket<0){fxStatus="ORDER_REJECTED_"+IntegerToString(error);FXEvent("ORDER_FAILED",fxStatus);
      if(error==128 || error==0 || error==1 || error==6)FXWriteFlag(fxRoot+"\\execution_review_required.csv","AMBIGUOUS_ORDER_RESULT");
      return false;}
   fxStatus="ORDER_OPEN_"+IntegerToString(ticket);
   if(OrderSelect(ticket,SELECT_BY_TICKET,MODE_TRADES) && FXOwnSelected()) {
      FXEvent("ORDER_FILLED","BROKER_CONFIRMED",ticket,OrderLots(),OrderOpenPrice(),OrderStopLoss(),OrderTakeProfit(),plan.plannedRisk);
      bool saved=FXSaveOriginalRisk();
      if(saved && fxSettings.averaging)saved=FXAverageRegister(e,basketCap);
      double tickSize=SymbolInfoDouble(Symbol(),SYMBOL_TRADE_TICK_SIZE),tickValue=MarketInfo(Symbol(),MODE_TICKVALUE);
      bool unprotected=OrderStopLoss()<=0 || OrderTakeProfit()<=0;
      double actualRisk=FXPositive(tickSize) && FXPositive(tickValue) ?
         (MathAbs(OrderOpenPrice()-OrderStopLoss())+(fxSettings.costBufferPips)*.0001)/tickSize*tickValue*OrderLots() : plan.riskBudget+1;
      if(!saved || unprotected || actualRisk>plan.riskBudget+1e-6)FXRequestClose(!saved ? "POSITION_STATE_NOT_SAVED" : unprotected ? "MISSING_BROKER_PROTECTION" : "FILL_RISK_LIMIT");
   } else { fxStatus="TICKET_RECONCILIATION_REQUIRED";FXEvent("RECONCILE_REQUIRED","DO_NOT_RESEND",ticket);
      FXWriteFlag(fxRoot+"\\execution_review_required.csv","TICKET_RECONCILIATION_REQUIRED"); }
   return true;
}
void FXLock(long nowMs) {
   BOProbability empty[];ArrayResize(empty,3);for(int i=0;i<3;i++)ZeroMemory(empty[i]);
   BOLock(fxEpisode,fxConfig,nowMs,true,fxPaused,empty);
   // Explicit rule-based Forex contract; Binary payout/model cold-start is NOT broker qualification.
   if(!fxEpisode.canceled && fxEpisode.reason==BO_SHADOW_ONLY && fxEpisode.validation==BO_CONFIRMED && fxEpisode.lockedDirection!=0 && !fxPaused) {
      fxEpisode.action=fxEpisode.lockedDirection;fxEpisode.lockedAction=fxEpisode.action;fxEpisode.reason=BO_OK;
   }
   fxStatus="LOCK_"+BOReasonName(fxEpisode.reason);FXEvent("LOCK",fxStatus);
}
void FXAdvance(long nowMs,bool tick,double bid,double ask) {
   if(!fxHealthy || !fxEpisode.exists || fxEpisode.entered)return;
   bool previous=fxEpisode.canceled;
   if(tick)BOObserve(fxEpisode,fxConfig,nowMs,bid,ask);else BOCheckQuoteAge(fxEpisode,fxConfig,nowMs);
   // Input/storage work may have elapsed after the received quote. Never backdate LOCK/ENTRY.
   long actual=BONowMs();if(actual>nowMs){nowMs=actual;BOCheckQuoteAge(fxEpisode,fxConfig,nowMs);}
   if(!previous && fxEpisode.canceled){fxStatus="CANCELED_"+BOReasonName(fxEpisode.reason);FXEvent("CANCEL",fxStatus);}
   if(!fxEpisode.locked && nowMs>=BOLockDue(fxEpisode,fxConfig))FXLock(nowMs);
   if(nowMs>=(long)fxEpisode.targetTime*1000 && (tick || nowMs>(long)(fxEpisode.targetTime+fxConfig.boundaryLagSeconds)*1000)) {
      fxEpisode.entered=true;
      if(tick && fxEpisode.action!=0 && !fxEpisode.canceled)FXSend(fxEpisode,nowMs);
      else if(!fxEpisode.canceled)fxStatus="NO_EXECUTABLE_SIGNAL";
      FXEvent("ENTRY_RESULT","T_"+IntegerToString((long)fxEpisode.targetTime)+"_"+fxStatus,fxLastTicket);
      fxEpisode.action=0;
   }
}
void FXHistoryRefresh() {
   if(fxEpisode.exists && !fxEpisode.entered && !fxEpisode.canceled)return;
   BOHistoryRefresh(); // Quote/position boundaries were processed before this possibly blocking call.
}
void FXAttemptAnchor(long quoteMs,double bid,double ask) {
   if(!fxHealthy)return;
   datetime bar=iTime(NULL,PERIOD_M5,0);long now=BONowMs();
   if(bar<=fxLastStarted || now<(long)bar*1000 || now>(long)(bar+fxConfig.maximumAnalysisDelaySeconds)*1000 ||
      now<quoteMs || now-quoteMs>3000 || !IsConnected())return;
   BOBar bars[];if(!BOHistoryCopy(bar,bars)){fxStatus="HISTORY_"+boHistoryStatus;return;}
   BOAnchor snapshot;ZeroMemory(snapshot);BOBuildMarket(bars,BO_HISTORY,fxConfig,snapshot);
   now=BONowMs();if(now>(long)(bar+fxConfig.maximumAnalysisDelaySeconds)*1000 || iTime(NULL,PERIOD_M5,0)!=bar || now<quoteMs || now-quoteMs>3000)return;
   BOStartEpisode(snapshot,fxConfig,bar,fxEpisode);fxLastStarted=bar;BOObserve(fxEpisode,fxConfig,quoteMs,bid,ask);
   string path=fxRoot+"\\forex_anchor_"+IntegerToString((long)bar)+".csv";
   if(FileIsExist(path)){fxStatus="DUPLICATE_ANCHOR_STORAGE";FXStorageFailure();return;}
   int f=FileOpen(path,FILE_WRITE|FILE_CSV|FILE_ANSI,',');if(f==INVALID_HANDLE){FXStorageFailure();return;}
   bool ok=FileWrite(f,"V222_FOREX_ANCHOR_V1",(long)bar,BOConfigHash(fxConfig),fxEpisode.candidate.setup,fxEpisode.candidate.direction,
      snapshot.regime,DoubleToString(snapshot.volatility.atr,10))>0;
   if(ok)ok=FileWrite(f,"time_broker","open","high","low","close","tick_volume")>0;
   for(int k=0;k<ArraySize(bars) && ok;k++)ok=FileWrite(f,(long)bars[k].time,DoubleToString(bars[k].open,Digits),DoubleToString(bars[k].high,Digits),
      DoubleToString(bars[k].low,Digits),DoubleToString(bars[k].close,Digits),bars[k].ticks)>0;
   FileFlush(f);FileClose(f);if(!ok){FXStorageFailure();return;}
   fxStatus="ANALYSIS_"+BOReasonName(fxEpisode.reason);FXEvent("ANCHOR",fxStatus);
}
void FXRender() {
   string account=IsTesting() ? "TESTER" : AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_REAL ? "REAL" : "DEMO";
   int own=0;string position="KHONG CO";
   for(int i=OrdersTotal()-1;i>=0;i--)if(OrderSelect(i,SELECT_BY_POS,MODE_TRADES) && FXOwnSelected()) {
      own++;position=(OrderType()==OP_BUY ? "BUY " : "SELL ")+DoubleToString(OrderLots(),2)+" lot | #"+IntegerToString(OrderTicket())+
         " | SL "+DoubleToString(OrderStopLoss(),Digits)+" | TP "+DoubleToString(OrderTakeProfit(),Digits);
   }
   string riskStatus=fxDayHalted ? "DA CHAM GIOI HAN LO NGAY" : "DANG THEO DOI";
   if(FileIsExist(fxRoot+"\\execution_review_required.csv"))riskStatus="CAN DOI CHIEU LENH VOI BROKER";
   Comment("EURUSD M5 | V2.22 FOREX | "+account+"\n"+
      "Trang thai: "+fxStatus+"\n"+
      "Vi the: "+position+"\n"+
      "Rui ro du kien: "+DoubleToString(fxSettings.riskPercent,2)+"% / lenh | 1 vi the EURUSD\n"+
      "Gioi han ngay: "+DoubleToString(fxSettings.dailyLossPercent,2)+"% | "+riskStatus+"\n"+
      "SL: cau truc + ATR | TP: "+DoubleToString(fxSettings.rewardRisk,2)+"R | Giu toi da: "+IntegerToString(fxSettings.maxHoldMinutes)+" phut\n"+
      "Hoa von: "+(fxSettings.breakEven ? "ON" : "OFF")+" | Trailing ATR: "+(fxSettings.trailing ? "ON" : "OFF")+" | "+fxProtectionStatus+"\n"+
      "Luot vao/ngay (luu ben vung): "+IntegerToString(fxDailyAttempts)+"/"+IntegerToString(fxSettings.maxDailyAttempts)+" | Chuoi thua/ngay: "+IntegerToString(fxLossStreak)+"\n"+
      "Lich broker: "+(fxSettings.schedule ? "ON" : "OFF")+" | Dong khan cap: "+(fxSettings.emergencyClose ? "ON" : "OFF")+"\n"+
      "Binh quan: "+(FXAverageActive() ? fxAverageStatus : "OFF")+" | Risk "+DoubleToString(fxSettings.riskPercent,2)+"% cho CA CUM\n"+
      "Cho phep tai khoan that: "+(fxSettings.allowReal ? "CO" : "KHONG")+" | AutoTrading: "+(IsTradeAllowed() ? "ON" : "OFF")+"\n"+
      "Ket noi: "+(IsConnected() ? "ON" : "MAT KET NOI")+" | Tin Forex: "+fxNewsStatus+"\n"+
      (fxNewsSelected>=0 ? "Tin lien quan: "+fxNewsLabels[fxNewsSelected]+" | "+TimeToString((datetime)(fxNewsTimes[fxNewsSelected]+25200),TIME_DATE|TIME_SECONDS)+" VN\n" : "")+
      "Lenh da dong (lich su MT4 dang tai): "+IntegerToString(fxClosedTrades)+" | Net: "+DoubleToString(fxClosedNet,2)+" "+AccountCurrency()+"\n"+
      "Mo hinh: RULE_BASED_FOREX_V1 | Chua kiem dinh loi nhuan\n"+
      "Nhat ky: "+fxRoot);
}
bool FXRecordQuote(long nowMs,const MqlTick &q) {
   if(!fxSettings.recordQuotes)return true;
   int f=FileOpen(fxRoot+"\\forex_quotes_"+IntegerToString(nowMs/86400000)+".csv",FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
   if(f==INVALID_HANDLE){FXStorageFailure();return false;}
   bool ok=true;if(FileSize(f)==0)ok=FileWrite(f,"contract","broker_ms","bid","ask")>0;
   FileSeek(f,0,SEEK_END);if(ok)ok=FileWrite(f,"V222_FOREX_QUOTES_V1",nowMs,DoubleToString(q.bid,Digits),DoubleToString(q.ask,Digits))>0;
   FileFlush(f);FileClose(f);if(!ok)FXStorageFailure();return ok;
}
void FXTick() {
   if(!fxStarted)return;
   MqlTick q;if(!SymbolInfoTick(Symbol(),q))return;
   if(IsTesting() && fxEpisode.exists && !fxEpisode.entered && !fxEpisode.locked) {
      long due=BOLockDue(fxEpisode,fxConfig),prior=boClockBaseMs;
      if(prior>0 && due>prior && due<(long)q.time*1000){boClockBaseMs=due;FXAdvance(due,false,0,0);boClockBaseMs=prior;}
   }
   long now=0;if(!BOClockTick(q.time,now)){if(fxEpisode.exists && !fxEpisode.entered)BOCancel(fxEpisode,BO_TIME_ANOMALY);fxStatus="CLOCK_ANOMALY";FXManagePositions();FXRender();return;}
   if(fxSettings.newsFilter){BOContextClockTick(now);FXNewsUTC(now);}else fxNewsStatus="NEWS_FILTER_DISABLED";
   if(fxHealthy)FXDayGuard(now/1000);
   if(fxHealthy && FXRecordQuote(now,q)){FXAdvance(now,true,q.bid,q.ask);}
   FXManagePositions();
   if(fxHealthy){FXHistoryRefresh();FXAttemptAnchor(now,q.bid,q.ask);}
   FXRender();
}
void FXTimer() {
   if(!fxStarted)return;
   long now=BONowMs();if(now>0){if(fxHealthy)FXDayGuard(now/1000);if(fxSettings.newsFilter)FXNewsUTC(now);}
   FXManagePositions();if(now>0)FXAdvance(now,false,0,0);FXHistoryRefresh();FXRender();
}
int FXInit(const FXSettings &settings,const BOConfig &config,string tag) {
   fxSettings=settings;fxConfig=config;fxStarted=false;fxHealthy=true;fxPaused=false;fxLastStarted=0;
   fxDay=0;fxDayEquity=0;fxDayHalted=false;fxLastManagement=0;fxLastTicket=-1;fxLastLots=0;fxClosedTrades=0;fxClosedNet=0;ZeroMemory(fxEpisode);
   if(!FXSettingsValid(settings) || !BOSafeTag(tag))return INIT_PARAMETERS_INCORRECT;
   if(FXHasForeignMagicOrders(settings.magic)){Print("Existing FX222 position uses another magic. Restore its original magic before managing it.");return INIT_FAILED;}
   FolderCreate("FX_V222");
   fxRoot="FX_V222\\"+(IsTesting() ? tag+"_TESTER_"+Symbol() : "LIVE_"+IntegerToString(AccountNumber())+"_"+IntegerToString((long)BOHashText(AccountServer()+"|EURUSD")));
   FolderCreate(fxRoot);fxLease=FileOpen(fxRoot+"\\instance.lock",FILE_READ|FILE_WRITE|FILE_BIN);
   if(fxLease==INVALID_HANDLE){Print("Forex instance/account/symbol is already locked or inaccessible.");return INIT_FAILED;}
   fxNextModifyMs=0;fxProtectionStatus="WAITING";fxDailyAttempts=0;fxLossStreak=0;fxLatestExit=0;
   fxCloseTicket=-1;fxCloseFailures=0;fxCloseDueMs=0;
   BOContextReset();FXNewsReset();
   if(!FXLoadRiskExits())return INIT_FAILED;
   if(IsTesting() && FileIsExist(fxRoot+"\\forex_session.csv")){Print("Use a fresh Forex Tester InstanceTag.");return INIT_FAILED;}
   int f=FileOpen(fxRoot+"\\forex_session.csv",FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
   if(f==INVALID_HANDLE)return INIT_FAILED;
   bool ok=true;
   if(FileSize(f)==0)ok=FileWrite(f,"contract","origin","broker_seconds","tag","server","symbol","magic","risk_pct","allow_real","stop_atr","reward_risk","day_loss_pct",
      "enabled","record_quotes","min_stop_pips","max_stop_pips","max_spread_pips","slippage_pips","cost_buffer_pips","max_lots","max_hold_minutes",
      "native_config_hash","lock_lead_seconds","analysis_window_seconds","observation_gap_seconds","allow_sr1","allow_tp1","allow_br1","break_even","be_r","be_offset_pips","trailing","trail_start_r","trail_atr","trail_min_pips","trail_step_pips","max_daily_attempts","max_daily_loss_streak","cooldown_minutes","emergency_close","schedule_broker_clock","rollover_start_minute","rollover_end_minute","friday_stop_minute","friday_close_minute","close_own_on_daily_loss","news_filter","news_max_age_s","news_high_before","news_high_after","news_medium_before","news_medium_after","news_lookahead","news_exit_minutes","news_high_action","news_medium_action","news_reduce_pct")>0;
   FileSeek(f,0,SEEK_END);if(ok)ok=FileWrite(f,"V222_FOREX_SESSION_V1",IsTesting() ? "FOREX_BACKTEST_MT4" : "FOREX_LIVE_MT4",(long)TimeCurrent(),
      tag,AccountServer(),Symbol(),settings.magic,settings.riskPercent,settings.allowReal,settings.stopATR,settings.rewardRisk,settings.dailyLossPercent,
      settings.enabled,settings.recordQuotes,settings.minStopPips,settings.maxStopPips,settings.maxSpreadPips,settings.slippagePips,settings.costBufferPips,settings.maximumLots,settings.maxHoldMinutes,
      BOConfigHash(config),config.lockLeadSeconds,config.maximumAnalysisDelaySeconds,config.maximumObservationGapSeconds,config.allowSR1,config.allowTP1,config.allowBR1,settings.breakEven,settings.breakEvenR,settings.breakEvenOffsetPips,settings.trailing,settings.trailStartR,settings.trailATR,settings.trailMinPips,settings.trailStepPips,settings.maxDailyAttempts,settings.maxLossStreak,settings.cooldownMinutes,settings.emergencyClose,settings.schedule,settings.rolloverStartMinute,settings.rolloverEndMinute,settings.fridayStopMinute,settings.fridayCloseMinute,settings.closeOnDailyLoss,settings.newsFilter,settings.newsMaxAgeSeconds,settings.newsHighBefore,settings.newsHighAfter,settings.newsMediumBefore,settings.newsMediumAfter,settings.newsLookaheadMinutes,settings.newsExitMinutes,settings.newsHighAction,settings.newsMediumAction,settings.newsReducePercent)>0;
   FileFlush(f);FileClose(f);if(!ok)return INIT_FAILED;
   if(!FXAverageInitPolicy())return INIT_FAILED;
   boClockBaseMs=0;boClockMono=0;boLastTickMs=0;BOHistoryReset();
   fxLastStarted=iTime(NULL,PERIOD_M5,0);FXHistoryRefresh();
   if(!IsTesting() && !EventSetTimer(1))return INIT_FAILED;
   fxStarted=true;fxStatus="WAIT_NEXT_COMPLETE_M5";
   FXAccountPermission();FXEvent("INIT",fxStatus);FXRender();return fxHealthy ? INIT_SUCCEEDED : INIT_FAILED;
}
void FXDeinit() {
   if(fxStarted) {
      FXSyncClosed();FXEvent("DEINIT","BROKER_SL_TP_REMAINS_NO_NEW_ENTRIES");
      if(IsTesting() && fxHealthy) {
         int f=FileOpen(fxRoot+"\\forex_tester_complete.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
         if(f!=INVALID_HANDLE){FileWrite(f,"V222_FOREX_TESTER_COMPLETE_V1",(long)TimeCurrent(),OrdersTotal(),fxClosedTrades,DoubleToString(fxClosedNet,2));FileFlush(f);FileClose(f);}
      }
   }
   fxStarted=false;EventKillTimer();Comment("");
   if(fxLease!=INVALID_HANDLE){FileClose(fxLease);fxLease=INVALID_HANDLE;}
}
#endif
