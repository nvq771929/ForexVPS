#ifndef FX_V222_AVERAGE
#define FX_V222_AVERAGE
// One same-direction addition. This module never allocates a second basket budget.
struct FXBasket {
   int id; long birth; int direction; double entry; double stop; double take; double lots; double budget; int setup; long target;
   int count; int tickets[2]; double sizes[2]; double entries[2]; double stops[2];
   bool pairIncomplete; int child; double childLots;
};
long fxAverageModifyDue=0,fxAverageCloseDue=0;int fxAverageCloseFailures=0;
string fxAverageStatus="OFF";
string FXBasketPath(int id) { return fxRoot+"\\basket_"+IntegerToString(id)+".csv"; }
string FXBasketLink(int ticket) { return fxRoot+"\\basket_link_"+IntegerToString(ticket)+".csv"; }
string FXBasketFlag(string name,int id) { return fxRoot+"\\average_"+name+"_"+IntegerToString(id)+".csv"; }
string FXBasketPayload(const FXBasket &b) {
   return IntegerToString(b.id)+"|"+IntegerToString(b.birth)+"|"+IntegerToString(b.direction)+"|"+
      DoubleToString(b.entry,Digits)+"|"+DoubleToString(b.stop,Digits)+"|"+DoubleToString(b.take,Digits)+"|"+
      DoubleToString(b.lots,8)+"|"+DoubleToString(b.budget,8)+"|"+IntegerToString(b.setup)+"|"+IntegerToString(b.target);
}
bool FXAverageRegister(const BOPrediction &e,double cap) {
   FXBasket b;ZeroMemory(b);b.id=OrderTicket();b.birth=(long)OrderOpenTime();b.direction=OrderType()==OP_BUY ? 1 : -1;
   b.entry=OrderOpenPrice();b.stop=OrderStopLoss();b.take=OrderTakeProfit();b.lots=OrderLots();b.budget=cap;b.setup=e.candidate.setup;b.target=(long)e.targetTime;
   if(!FXPositive(cap) || b.direction*(b.entry-b.stop)<=0)return false;
   if(!FXSaveState(FXBasketPath(b.id),"V222_FOREX_BASKET_V1",FXBasketPayload(b)))return false;
   return FXSaveState(FXBasketLink(b.id),"V222_FOREX_BASKET_LINK_V1",IntegerToString(b.id));
}
bool FXAverageRoot(int id,FXBasket &b) {
   string payload;string p[];
   if(!FXReadState(FXBasketPath(id),"V222_FOREX_BASKET_V1",payload) || StringSplit(payload,124,p)!=10)return false;
   b.id=(int)StringToInteger(p[0]);b.birth=StringToInteger(p[1]);b.direction=(int)StringToInteger(p[2]);
   b.entry=StringToDouble(p[3]);b.stop=StringToDouble(p[4]);b.take=StringToDouble(p[5]);b.lots=StringToDouble(p[6]);
   b.budget=StringToDouble(p[7]);b.setup=(int)StringToInteger(p[8]);b.target=StringToInteger(p[9]);
   return b.id==id && b.birth>0 && b.target>0 && (b.direction==1 || b.direction==-1) && FXPositive(b.entry) &&
      FXPositive(b.stop) && FXPositive(b.take) && FXPositive(b.lots) && FXPositive(b.budget) &&
      b.direction*(b.entry-b.stop)>0 && b.direction*(b.take-b.entry)>0 && payload==FXBasketPayload(b);
}
bool FXAverageActive() {
   if(fxSettings.averaging)return true;
   for(int i=OrdersTotal()-1;i>=0;i--)if(OrderSelect(i,SELECT_BY_POS,MODE_TRADES) && FXOwnSelected() && FileIsExist(FXBasketLink(OrderTicket())))return true;
   return false;
}
bool FXAverageLoad(FXBasket &b) {
   ZeroMemory(b);int id=0;
   for(int i=OrdersTotal()-1;i>=0;i--)if(OrderSelect(i,SELECT_BY_POS,MODE_TRADES) && FXOwnSelected()) {
      if(b.count>=2)return false;
      int ticket=OrderTicket();string text;
      if(!FileIsExist(FXBasketLink(ticket)) || !FXReadState(FXBasketLink(ticket),"V222_FOREX_BASKET_LINK_V1",text))return false;
      int linked=(int)StringToInteger(text);if(linked<=0 || text!=IntegerToString(linked) || (id>0 && linked!=id))return false;
      id=linked;int k=b.count;b.tickets[k]=ticket;b.sizes[k]=OrderLots();b.entries[k]=OrderOpenPrice();b.stops[k]=OrderStopLoss();b.count++;
      if(!FXPositive(OrderStopLoss()) || !FXPositive(OrderTakeProfit()))return false;
      double r=0;long birth=0;if(!FXPositionState(r,birth))return false;
   }
   if(b.count==0)return true;
   if(!FXAverageRoot(id,b))return false;
   bool parent=false,childPresent=false;int child=0;double childLots=0;
   string text;
   if(FileIsExist(FXBasketFlag("filled",id))) {
      if(!FXReadState(FXBasketFlag("filled",id),"V222_FOREX_ADDITION_V1",text))return false;
      string parts[];if(StringSplit(text,124,parts)!=2)return false;
      child=(int)StringToInteger(parts[0]);childLots=StringToDouble(parts[1]);
      if(child<=0 || !FXPositive(childLots) || text!=IntegerToString(child)+"|"+DoubleToString(childLots,8))return false;
   }
   bool pending=FileIsExist(FXBasketFlag("reserved",id)),failed=FileIsExist(FXBasketFlag("failed",id));
   if((pending && child==0 && !failed) || (child>0 && failed) || (child==0 && b.count!=1))return false;
   b.child=child;b.childLots=childLots;
   for(int k=0;k<b.count;k++) {
      if(!OrderSelect(b.tickets[k],SELECT_BY_TICKET,MODE_TRADES) || !FXOwnSelected() || (OrderType()==OP_BUY ? 1 : -1)!=b.direction)return false;
      double r=0;long birth=0;if(!FXPositionState(r,birth) || birth!=b.birth || MathAbs(r-MathAbs(b.entry-b.stop))>Point/2)return false;
      if(b.tickets[k]==b.id){parent=true;if(MathAbs(b.sizes[k]-b.lots)>1e-8)return false;}
      else if(b.tickets[k]!=child || MathAbs(b.sizes[k]-childLots)>1e-8)return false;
      else childPresent=true;
      if(b.direction*(OrderStopLoss()-b.stop)<-Point/2 || MathAbs(OrderTakeProfit()-b.take)>Point/2)return false;
   }
   if(child>0 && b.count==1) {
      int missing=parent ? child : b.id;
      if(!OrderSelect(missing,SELECT_BY_TICKET,MODE_HISTORY) || !FXOwnSelected() || OrderCloseTime()<=0 ||
         MathAbs(OrderLots()-(parent ? childLots : b.lots))>1e-8)return false;
      b.pairIncomplete=true;return true;
   }
   return parent && (child==0 || childPresent);
}
void FXAverageCloseAll(string reason,long now) {
   // Reserve every owned close BEFORE attempting the first API operation.
   for(int i=OrdersTotal()-1;i>=0;i--)if(OrderSelect(i,SELECT_BY_POS,MODE_TRADES) && FXOwnSelected())
      FXWriteFlag(fxRoot+"\\close_required_"+IntegerToString(OrderTicket())+".csv",reason);
   fxAverageStatus="BASKET_CLOSE_"+reason;
   if(now<fxAverageCloseDue)return;
   bool failed=false;
   for(int i=OrdersTotal()-1;i>=0;i--)if(OrderSelect(i,SELECT_BY_POS,MODE_TRADES) && FXOwnSelected())if(!FXCloseSelected(reason))failed=true;
   if(failed){fxAverageCloseFailures++;long delay=1000;for(int j=1;j<fxAverageCloseFailures && delay<30000;j++)delay*=2;
      fxAverageCloseDue=now+(long)MathMin(delay,30000);}
   else {fxAverageCloseFailures=0;fxAverageCloseDue=0;}
}
bool FXMarginReserve(double lots,double remaining,double bid,double ask) {
   double tick=SymbolInfoDouble(Symbol(),SYMBOL_TRADE_TICK_SIZE),value=MarketInfo(Symbol(),MODE_TICKVALUE);
   double margin=AccountMargin(),free=AccountFreeMargin(),equity=AccountEquity();
   if(!FXPositive(tick) || !FXPositive(value) || !FXPositive(equity) || !MathIsValidNumber(margin) || margin<0 || !MathIsValidNumber(free)){
      fxStatus="MARGIN_METADATA_INVALID";return false;}
   double costs=((ask-bid)+fxSettings.costBufferPips*.0001)/tick*value*lots;
   double afterEquity=equity-costs,afterMargin=margin+MathMax(0,free-remaining),afterFree=remaining-costs;
   if(afterEquity<=0 || afterFree<afterEquity*fxSettings.minFreeEquityPercent/100 ||
      (afterMargin>0 && afterEquity/afterMargin*100<fxSettings.minMarginLevelPercent)){
      fxStatus="MARGIN_RESERVE_LIMIT";return false;}
   return true;
}
double FXAverageBudget() {
   double user=MathMin(AccountBalance(),AccountEquity())*fxSettings.riskPercent/100;
   double day=AccountEquity()-fxDayEquity*(1-fxSettings.dailyLossPercent/100);
   return MathMax(0,MathMin(user,day));
}
bool FXAverageAbort(int id,string reason) {
   FXWriteFlag(FXBasketFlag("failed",id),reason);fxStatus=reason;return false;
}
bool FXAverageParentLive(const FXBasket &b) {
   int related=0;
   for(int i=OrdersTotal()-1;i>=0;i--)if(OrderSelect(i,SELECT_BY_POS,MODE_TRADES)){
      string name=OrderSymbol();StringToUpper(name);if(StringFind(name,"EURUSD")==0)related++;
   }
   // MT4 ignores the pool argument with SELECT_BY_TICKET: a closed ticket can
   // still be selected from history. Check its actual close time explicitly.
   return related==1 && OrderSelect(b.id,SELECT_BY_TICKET,MODE_TRADES) && FXOwnSelected() && OrderCloseTime()==0 &&
      MathAbs(OrderLots()-b.lots)<1e-8 && MathAbs(OrderStopLoss()-b.stop)<Point/2 && MathAbs(OrderTakeProfit()-b.take)<Point/2;
}
bool FXAverageTrySend(BOPrediction &e,long now) {
   fxStatus="AVERAGE_NOT_ELIGIBLE";
   int total=0,own=0;
   for(int i=OrdersTotal()-1;i>=0;i--)if(OrderSelect(i,SELECT_BY_POS,MODE_TRADES)){
      string name=OrderSymbol();StringToUpper(name);if(StringFind(name,"EURUSD")==0)total++;if(FXOwnSelected())own++;
   }
   if(!fxSettings.averaging || own!=1 || total!=1)return false;
   FXBasket b;if(!FXAverageLoad(b) || b.count!=1){fxStatus="AVERAGE_BASKET_UNRECONCILED";return false;}
   if(FileIsExist(FXBasketFlag("reserved",b.id))){fxStatus="AVERAGE_ALREADY_ATTEMPTED";return false;}
   if(FileIsExist(fxRoot+"\\close_required_"+IntegerToString(b.id)+".csv")){fxStatus="AVERAGE_BASKET_EXIT_PENDING";return false;}
   string intent=fxRoot+"\\intent_"+IntegerToString((long)e.targetTime)+".csv";
   if(FileIsExist(intent)){fxStatus="ENTRY_ALREADY_ATTEMPTED";return false;}
   if(now/1000<b.birth || now/1000-b.birth>fxSettings.averageWindowMinutes*60 ||
      (fxSettings.maxHoldMinutes>0 && now/1000-b.birth>=fxSettings.maxHoldMinutes*60))return false;
   // A post-entry closed M5 must form a NEW, confirmed setup and complete T+1.
   if(e.action!=b.direction || e.candidate.setup!=b.setup || b.setup<1 || e.analysisStart<b.target+300 ||
      e.targetTime<=b.target || b.direction*(e.candidate.invalidation-b.stop)<0){fxStatus="AVERAGE_NEW_SETUP_REQUIRED";return false;}
   if(!FXAverageParentLive(b))return false;
   MqlTick q;if(!SymbolInfoTick(Symbol(),q) || !FXPositive(q.bid) || !FXPositive(q.ask) || q.ask<q.bid)return false;
   long actual=BONowMs();if(actual<(long)q.time*1000 || actual-(long)q.time*1000>3000 || actual>(long)(e.targetTime+fxConfig.boundaryLagSeconds)*1000)return false;
   double r=MathAbs(b.entry-b.stop),exit=b.direction>0 ? q.bid : q.ask;
   double adverse=b.direction*(b.entry-exit)/r;
   // Decimal prices can put the exact 0.5R boundary a few ulps below 0.5.
   if(adverse+1e-9<fxSettings.averageTriggerR || adverse-1e-9>fxSettings.averageMaxAdverseR || b.direction*(exit-b.stop)<=0){fxStatus="AVERAGE_ADVERSE_WINDOW";return false;}
   double price=b.direction>0 ? q.ask : q.bid;
   double tick=SymbolInfoDouble(Symbol(),SYMBOL_TRADE_TICK_SIZE),value=MarketInfo(Symbol(),MODE_TICKVALUE);
   double step=MarketInfo(Symbol(),MODE_LOTSTEP),minimum=MarketInfo(Symbol(),MODE_MINLOT),maximum=MarketInfo(Symbol(),MODE_MAXLOT);
   int stops=(int)MarketInfo(Symbol(),MODE_STOPLEVEL);
   if(!FXPositive(tick) || !FXPositive(value) || !FXPositive(step) || !FXPositive(minimum) || !FXPositive(maximum) || minimum>maximum || stops<0)return false;
   if((q.ask-q.bid)/.0001>fxSettings.maxSpreadPips){fxStatus="SPREAD_LIMIT";return false;}
   double distance=b.direction*(price-b.stop);
   double needed=MathMax(fxSettings.minStopPips*.0001,MathMax(fxSettings.stopATR*e.anchor.volatility.atr,(stops+2)*Point+q.ask-q.bid));
   if(!FXPositive(e.anchor.volatility.atr) || distance+1e-10<needed || distance>fxSettings.maxStopPips*.0001 || b.direction*(b.take-exit)<stops*Point)return false;
   double buffer=(fxSettings.slippagePips+fxSettings.costBufferPips)*.0001;
   double originalRisk=(r+buffer)/tick*value*b.lots,perLot=(distance+buffer)/tick*value;
   double basketLimit=MathMin(b.budget,MathMin(AccountBalance(),AccountEquity())*fxSettings.riskPercent/100);
   double futureExisting=(b.direction*(exit-b.stop)+buffer)/tick*value*b.lots;
   double dayRemaining=AccountEquity()-fxDayEquity*(1-fxSettings.dailyLossPercent/100)-futureExisting;
   double cash=MathMin(MathMax(0,basketLimit-originalRisk),MathMax(0,dayRemaining));
   double limit=MathMin(b.lots*fxSettings.averageLotRatio,MathMin(maximum,MathMax(0,fxSettings.maximumLots-b.lots)));
   double lots=NormalizeDouble(MathFloor((MathMin(limit,cash/perLot)+1e-12)/step)*step,8);
   if(lots<minimum-1e-10 || !FXPositive(lots) || originalRisk+lots*perLot>basketLimit+1e-7){fxStatus="AVERAGE_NO_RISK_HEADROOM";return false;}
   if(!IsConnected() || !IsTradeAllowed() || IsTradeContextBusy() || MarketInfo(Symbol(),MODE_TRADEALLOWED)==0)return false;
   ResetLastError();double remaining=AccountFreeMarginCheck(Symbol(),b.direction>0 ? OP_BUY : OP_SELL,lots);int error=GetLastError();
   if(!FXPositive(remaining) || error!=0){fxStatus="INSUFFICIENT_MARGIN";return false;}
   if(!FXMarginReserve(lots,remaining,q.bid,q.ask))return false;
   if(!FXRiskEntryGuard(now/1000,true))return false;
   if(!FXWriteFlag(FXBasketFlag("reserved",b.id),"ONE_ADDITION_RESERVED"))return false;
   if(!FXWriteFlag(intent,"AVERAGE_ATTEMPT_RESERVED") ||
      !FXEvent("AVERAGE_INTENT","BASKET_"+IntegerToString(b.id),-1,lots,price,b.stop,b.take,originalRisk+lots*perLot))return FXAverageAbort(b.id,"AVERAGE_STORAGE_ABORT");
   actual=BONowMs();
   if(actual>(long)(e.targetTime+fxConfig.boundaryLagSeconds)*1000 || actual<(long)q.time*1000 || actual-(long)q.time*1000>3000 ||
      !IsConnected() || !IsTradeAllowed() || IsTradeContextBusy() || !FXDayGuard(actual/1000) || !FXAccountPermission() || !FXNewsEntryAllowed(actual))return FXAverageAbort(b.id,"AVERAGE_FINAL_GATE_ABORT");
   actual=BONowMs();if(actual>(long)(e.targetTime+fxConfig.boundaryLagSeconds)*1000 || actual<(long)q.time*1000 || actual-(long)q.time*1000>3000)return FXAverageAbort(b.id,"AVERAGE_FINAL_QUOTE_ABORT");
   if(!FXAverageParentLive(b))return FXAverageAbort(b.id,"AVERAGE_PARENT_OR_EXPOSURE_CHANGED");
   ResetLastError();int ticket=OrderSend(Symbol(),b.direction>0 ? OP_BUY : OP_SELL,lots,price,FXSlippagePoints(),b.stop,b.take,
      "FX222A:"+IntegerToString(b.id),fxSettings.magic,0,clrNONE);error=GetLastError();fxLastTicket=ticket;fxLastLots=lots;
   if(ticket<0){
      if(error==128 || error==0 || error==1 || error==6){FXWriteFlag(fxRoot+"\\execution_review_required.csv","AMBIGUOUS_AVERAGE_RESULT");fxStatus="AVERAGE_RECONCILIATION_REQUIRED";}
      else FXAverageAbort(b.id,"AVERAGE_REJECTED_"+IntegerToString(error));
      return false;
   }
   double actualRisk=0;bool ok=OrderSelect(ticket,SELECT_BY_TICKET,MODE_TRADES) && FXOwnSelected();
   if(ok) {
      actualRisk=(MathAbs(OrderOpenPrice()-b.stop)+fxSettings.costBufferPips*.0001)/tick*value*OrderLots();
      ok=MathAbs(OrderLots()-lots)<1e-8 && MathAbs(OrderStopLoss()-b.stop)<Point/2 && MathAbs(OrderTakeProfit()-b.take)<Point/2 &&
         originalRisk+actualRisk<=basketLimit+1e-6 && b.direction*(b.entry-OrderOpenPrice())>0;
      if(ok)ok=FXSaveState(fxRoot+"\\position_"+IntegerToString(ticket)+".csv","V222_FOREX_POSITION_V1",FXPositionKey()+"|"+DoubleToString(r,Digits)+"|"+IntegerToString(b.birth)) &&
         FXSaveState(FXBasketLink(ticket),"V222_FOREX_BASKET_LINK_V1",IntegerToString(b.id)) &&
         FXSaveState(FXBasketFlag("filled",b.id),"V222_FOREX_ADDITION_V1",IntegerToString(ticket)+"|"+DoubleToString(lots,8));
   }
   if(!ok){FXWriteFlag(fxRoot+"\\execution_review_required.csv","AVERAGE_FILL_OR_STATE_UNCONFIRMED");FXAverageCloseAll("AVERAGE_FILL_OR_STATE_UNCONFIRMED",actual);return false;}
   fxStatus="AVERAGE_OPEN_"+IntegerToString(ticket);fxAverageStatus=fxStatus;
   FXEvent("AVERAGE_FILLED","BASKET_"+IntegerToString(b.id),ticket,lots,OrderOpenPrice(),b.stop,b.take,originalRisk+actualRisk);
   return true;
}
void FXAverageManage(long now) {
   FXBasket b;
   if(!FXAverageLoad(b)){FXWriteFlag(fxRoot+"\\execution_review_required.csv","BASKET_STATE_UNRECONCILED");FXAverageCloseAll("BASKET_STATE_UNRECONCILED",now);return;}
   if(b.count==0)return;
   if(b.pairIncomplete){FXAverageCloseAll("BASKET_LEG_CLOSED",now);return;}
   for(int k=0;k<b.count;k++)if(FileIsExist(fxRoot+"\\close_required_"+IntegerToString(b.tickets[k])+".csv")){FXAverageCloseAll("BASKET_DURABLE_CLOSE",now);return;}
   if(fxSettings.emergencyClose || (fxSettings.closeOnDailyLoss && fxDayHalted) || FXFridayExit(now/1000) ||
      (fxSettings.maxHoldMinutes>0 && now/1000-b.birth>=fxSettings.maxHoldMinutes*60)){
      FXAverageCloseAll(fxSettings.emergencyClose ? "EMERGENCY_CLOSE_OWN" : fxDayHalted ? "DAILY_EQUITY_LOSS_EXIT" : FXFridayExit(now/1000) ? "WEEKEND_EXIT" : "MAX_HOLD_TIME",now);return;}
   // Reserve the entire basket exit before any close API; never run per-leg partials.
   long utc=fxSettings.newsFilter ? FXNewsUTC(now) : 0;
   if(utc>0)for(int i=0;i<fxNewsCount;i++) {
      bool high=fxNewsImpacts[i]=="High";int action=high ? fxSettings.newsHighAction : fxSettings.newsMediumAction;
      int after=high ? fxSettings.newsHighAfter : fxSettings.newsMediumAfter;
      if(action>0 && utc>=fxNewsTimes[i]-fxSettings.newsExitMinutes*60 && utc<=fxNewsTimes[i]+after*60){
         fxNewsSelected=i;fxNewsStatus="NEWS_BASKET_RISK";FXNewsAudit("NEWS_BASKET_FULL_EXIT",b.id);
         FXAverageCloseAll("BASKET_NEWS_EXIT",now);return;
      }
   }
   if(now<fxAverageModifyDue || !IsConnected() || !IsTradeAllowed() || IsTradeContextBusy())return;
   MqlTick q;if(!SymbolInfoTick(Symbol(),q) || !FXPositive(q.bid) || !FXPositive(q.ask) || q.ask<q.bid ||
      now<(long)q.time*1000 || now-(long)q.time*1000>3000)return;
   double lots=0,weighted=0,desired=b.stops[0];
   double currentExit=b.direction>0 ? q.bid : q.ask;
   for(int k=0;k<b.count;k++)if(b.direction*(currentExit-b.stops[k])<=0){FXAverageCloseAll("BASKET_STOP_PRICE_REACHED",now);return;}
   for(int k=0;k<b.count;k++){lots+=b.sizes[k];weighted+=b.entries[k]*b.sizes[k];if(b.direction*(b.stops[k]-desired)>0)desired=b.stops[k];}
   if(!FXPositive(lots))return;weighted/=lots;
   double r=MathAbs(b.entry-b.stop),exit=b.direction>0 ? q.bid : q.ask,profit=b.direction*(exit-weighted);
   if(fxSettings.breakEven && profit>=r*fxSettings.breakEvenR){double stop=weighted+b.direction*fxSettings.breakEvenOffsetPips*.0001;if(b.direction*(stop-desired)>0)desired=stop;}
   if(fxSettings.trailing && profit>=r*fxSettings.trailStartR && boHistoryReady && boHistoryBar==(datetime)(now/1000/300*300) && ArraySize(boHistoryBars)==BO_HISTORY){
      double atr=BOATR(boHistoryBars,BO_HISTORY-1,14);
      if(FXPositive(atr)){double stop=exit-b.direction*MathMax(atr*fxSettings.trailATR,fxSettings.trailMinPips*.0001);if(b.direction*(stop-desired)>0)desired=stop;}
   }
   double tick=SymbolInfoDouble(Symbol(),SYMBOL_TRADE_TICK_SIZE);if(!FXPositive(tick))return;
   desired=NormalizeDouble(b.direction>0 ? MathFloor(desired/tick+1e-9)*tick : MathCeil(desired/tick-1e-9)*tick,Digits);
   int stops=(int)MarketInfo(Symbol(),MODE_STOPLEVEL),freeze=(int)MarketInfo(Symbol(),MODE_FREEZELEVEL);
   if(stops<0 || freeze<0 || b.direction*(exit-desired)<(MathMax(stops,freeze)+2)*Point || b.direction*(b.take-exit)<(MathMax(stops,freeze)+2)*Point)return;
   bool attempted=false;
   for(int k=0;k<b.count;k++)if(b.direction*(desired-b.stops[k])>=fxSettings.trailStepPips*.0001-1e-10 && b.direction*(exit-b.stops[k])>freeze*Point &&
      OrderSelect(b.tickets[k],SELECT_BY_TICKET,MODE_TRADES) && FXOwnSelected()) {
      long actual=BONowMs();if(actual<(long)q.time*1000 || actual-(long)q.time*1000>3000)break;
      ResetLastError();bool ok=OrderModify(OrderTicket(),OrderOpenPrice(),desired,b.take,0,clrNONE);int error=GetLastError();attempted=true;
      FXEvent(ok ? "BASKET_STOP_MOVED" : "BASKET_STOP_FAILED","BASKET_"+IntegerToString(b.id)+"_ERR_"+IntegerToString(error),OrderTicket(),OrderLots(),weighted,desired,b.take);
   }
   if(attempted)fxAverageModifyDue=now+5000;
   fxAverageStatus="BASKET_"+IntegerToString(b.id)+"_LEGS_"+IntegerToString(b.count);
}
bool FXAverageInitPolicy() {
   fxAverageModifyDue=0;fxAverageCloseDue=0;fxAverageCloseFailures=0;fxAverageStatus=fxSettings.averaging ? "WAIT_NEW_BASKET" : "OFF";
   int f=FileOpen(fxRoot+"\\forex_average_policy.csv",FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');if(f==INVALID_HANDLE)return false;
   bool ok=true;if(FileSize(f)==0)ok=FileWrite(f,"contract","broker_seconds","enabled","initial_fraction","trigger_R","max_adverse_R","max_added_lot_ratio","window_minutes","min_margin_level","min_free_equity_pct","basket_risk_pct","max_legs")>0;
   FileSeek(f,0,SEEK_END);if(ok)ok=FileWrite(f,"V222_FOREX_AVERAGE_V1",(long)TimeCurrent(),fxSettings.averaging,fxSettings.initialRiskFraction,fxSettings.averageTriggerR,
      fxSettings.averageMaxAdverseR,fxSettings.averageLotRatio,fxSettings.averageWindowMinutes,fxSettings.minMarginLevelPercent,fxSettings.minFreeEquityPercent,fxSettings.riskPercent,2)>0;
   FileFlush(f);FileClose(f);return ok;
}
#endif
