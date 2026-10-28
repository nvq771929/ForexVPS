#ifndef FX_V222_NEWS
#define FX_V222_NEWS
// Scheduled-news execution policy is Forex-only. Network work stays outside MT4.
bool fxNewsLoaded=false,fxNewsReadTried=false;uint fxNewsReadMono=0;
long fxNewsReceived=0,fxNewsExpires=0,fxNewsFrom=0,fxNewsTo=0;
int fxNewsCount=0,fxNewsSelected=-1;string fxNewsStatus="NEWS_UNKNOWN",fxNewsSnapshot="NONE";
long fxNewsTimes[512];string fxNewsIds[512],fxNewsImpacts[512],fxNewsLabels[512];bool fxNewsUncertain[512];
string fxNewsLastAudit="";
void FXNewsAudit(string decision,int ticket=-1,double lots=0) {
   string id=fxNewsSelected>=0 ? fxNewsIds[fxNewsSelected] : "NONE";
   string detail=decision+"|"+fxNewsSnapshot+"|"+id;
   string key=detail+"|"+IntegerToString(ticket);
   if(key==fxNewsLastAudit)return;
   if(FXEvent("NEWS_DECISION",detail,ticket,lots))fxNewsLastAudit=key;
}
void FXNewsReset() {
   fxNewsLoaded=false;fxNewsReadTried=false;fxNewsReadMono=0;fxNewsCount=0;fxNewsSelected=-1;
   fxNewsReceived=0;fxNewsExpires=0;fxNewsFrom=0;fxNewsTo=0;fxNewsSnapshot="NONE";fxNewsStatus="NEWS_UNKNOWN";
   fxNewsLastAudit="";
}
void FXNewsRefresh() {
   if(!fxSettings.newsFilter || IsTesting())return;
   uint mono=GetTickCount();if(fxNewsReadTried && (uint)(mono-fxNewsReadMono)<5000)return;
   fxNewsReadTried=true;fxNewsReadMono=mono;fxNewsLoaded=false;fxNewsCount=0;
   int f=FileOpen("FX_V222\\news_calendar.csv",FILE_READ|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');if(f==INVALID_HANDLE)return;
   string header[]={"contract","kind","received","expires","coverage_from","coverage_to","snapshot","event_id","event_utc","currency","impact","tracking","label","uncertain","count","fnv"};
   string cells[];bool ok=BODemoReadCells(f,16,cells);
   if(ok)for(int i=0;i<16;i++)if(cells[i]!=header[i])ok=false;
   int rows=0,expected=-1;string common="";
   while(ok && !FileIsEnding(f)) {
      if(!BODemoReadCells(f,16,cells)){ok=false;break;}
      string payload=cells[0];for(int j=1;j<15;j++)payload+="|"+cells[j];
      if(cells[0]!="V222_FOREX_NEWS_V1" || cells[15]!=IntegerToString((long)BOHashText(payload))){ok=false;break;}
      for(int j=2;j<=5;j++)if(!BODemoInteger(cells[j]))ok=false;
      if(!BODemoInteger(cells[14]) || StringToInteger(cells[14])<0 || StringToInteger(cells[14])>512 || StringLen(cells[6])!=64){ok=false;break;}
      string metadata=cells[2]+"|"+cells[3]+"|"+cells[4]+"|"+cells[5]+"|"+cells[6]+"|"+cells[14];
      if(rows==0) {
         if(cells[1]!="META" || cells[12]!="READY"){ok=false;break;}
         common=metadata;expected=(int)StringToInteger(cells[14]);fxNewsReceived=StringToInteger(cells[2]);fxNewsExpires=StringToInteger(cells[3]);
         fxNewsFrom=StringToInteger(cells[4]);fxNewsTo=StringToInteger(cells[5]);fxNewsSnapshot=cells[6];
         if(fxNewsReceived<=0 || fxNewsExpires<=fxNewsReceived || fxNewsExpires-fxNewsReceived>3600 || fxNewsTo<=fxNewsFrom){ok=false;break;}
      } else {
         if(metadata!=common || cells[1]!="NEWS" || fxNewsCount>=expected || !BODemoInteger(cells[8]) || StringLen(cells[7])!=24 ||
            (cells[9]!="EUR" && cells[9]!="USD") ||
            (cells[10]!="High" && cells[10]!="Medium" && !(cells[10]=="Low" && cells[11]=="PRIORITY_EVENT")) ||
            (cells[13]!="0" && cells[13]!="1")){ok=false;break;}
         long event=StringToInteger(cells[8]);if(event<fxNewsFrom || event>=fxNewsTo){ok=false;break;}
         for(int j=0;j<fxNewsCount;j++)if(fxNewsIds[j]==cells[7])ok=false;
         fxNewsTimes[fxNewsCount]=event;fxNewsIds[fxNewsCount]=cells[7];fxNewsImpacts[fxNewsCount]=cells[10];
         fxNewsLabels[fxNewsCount]=cells[9]+" "+cells[10]+" | "+cells[12];fxNewsUncertain[fxNewsCount]=cells[13]=="1";fxNewsCount++;
      }
      rows++;
   }
   FileClose(f);fxNewsLoaded=ok && rows>0 && fxNewsCount==expected;
   if(!fxNewsLoaded)fxNewsCount=0;
}
long FXNewsUTC(long nowMs) {
   fxNewsSelected=-1;
   if(!fxSettings.newsFilter){fxNewsStatus="NEWS_FILTER_DISABLED";return 0;}
   if(IsTesting()){fxNewsStatus="NEWS_TESTER_NO_HISTORICAL_CALENDAR";return 0;}
   long utc=BOContextUTC(nowMs)/1000;
   if(utc<=0){fxNewsStatus="NEWS_CLOCK_UNCERTAIN";return 0;}
   FXNewsRefresh();
   if(!fxNewsLoaded){fxNewsStatus="NEWS_UNKNOWN";return 0;}
   if(utc<fxNewsReceived){fxNewsStatus="NEWS_CLOCK_UNCERTAIN";return 0;}
   if(utc>fxNewsExpires || utc-fxNewsReceived>fxSettings.newsMaxAgeSeconds){fxNewsStatus="NEWS_STALE";return 0;}
   if(utc<fxNewsFrom || utc>=fxNewsTo){fxNewsStatus="NEWS_OUTSIDE_COVERAGE";return 0;}
   for(int i=0;i<fxNewsCount;i++)if(fxNewsUncertain[i]){fxNewsStatus="NEWS_TIME_UNCERTAIN";return 0;}
   for(int i=0;i<fxNewsCount;i++)if(fxNewsTimes[i]>=utc && (fxNewsSelected<0 || fxNewsTimes[i]<fxNewsTimes[fxNewsSelected]))fxNewsSelected=i;
   fxNewsStatus="NEWS_CLEAR";return utc;
}
bool FXNewsEntryAllowed(long nowMs) {
   if(!fxSettings.newsFilter){fxNewsStatus="NEWS_FILTER_DISABLED";return true;}
   long utc=FXNewsUTC(nowMs);fxNewsSelected=-1;
   if(utc<=0){fxStatus=fxNewsStatus;FXNewsAudit(fxNewsStatus);return false;}
   long end=utc+fxSettings.newsLookaheadMinutes*60;
   if(end>=fxNewsTo){fxStatus="NEWS_LOOKAHEAD_OUTSIDE_COVERAGE";return false;}
   for(int i=0;i<fxNewsCount;i++) {
      bool high=fxNewsImpacts[i]=="High";
      long a=fxNewsTimes[i]-(high ? fxSettings.newsHighBefore : fxSettings.newsMediumBefore)*60;
      long b=fxNewsTimes[i]+(high ? fxSettings.newsHighAfter : fxSettings.newsMediumAfter)*60;
      if(utc<=b && end>=a){fxNewsSelected=i;fxNewsStatus="NEWS_ENTRY_BLOCKED";fxStatus=fxNewsStatus;FXNewsAudit(fxNewsStatus);return false;}
   }
   return true;
}
bool FXNewsManageSelected(long nowMs) {
   if(!fxSettings.newsFilter)return false;
   long utc=FXNewsUTC(nowMs);if(utc<=0)return false; // Unknown data never invents a release or forces a panic exit.
   int selected=-1;
   for(int i=0;i<fxNewsCount;i++) {
      int after=fxNewsImpacts[i]=="High" ? fxSettings.newsHighAfter : fxSettings.newsMediumAfter;
      if(utc<fxNewsTimes[i]-fxSettings.newsExitMinutes*60 || utc>fxNewsTimes[i]+after*60)continue;
      if(selected<0 || (fxNewsImpacts[i]=="High" && fxNewsImpacts[selected]!="High") ||
         (fxNewsImpacts[i]==fxNewsImpacts[selected] && fxNewsTimes[i]<fxNewsTimes[selected]))selected=i;
   }
   if(selected<0)return false;
   fxNewsSelected=selected;fxNewsStatus="NEWS_POSITION_RISK";int action=fxNewsImpacts[selected]=="High" ? fxSettings.newsHighAction : fxSettings.newsMediumAction;
   if(action==0)return false;
   double net=OrderProfit()+OrderSwap()+OrderCommission();int direction=OrderType()==OP_BUY ? 1 : -1;
   if(action==1 || net<=0){FXNewsAudit("NEWS_FULL_EXIT",OrderTicket(),OrderLots());FXRequestClose("NEWS_FULL_EXIT_"+fxNewsIds[selected]);return true;}
   // Profitable, already secured at entry: continue normal trailing, without widening the stop.
   if(direction*(OrderStopLoss()-OrderOpenPrice())>=fxSettings.breakEvenOffsetPips*.0001){FXNewsAudit("NEWS_KEEP_SECURED",OrderTicket(),OrderLots());return false;}
   string key=fxNewsIds[selected]+"_"+IntegerToString(fxNewsTimes[selected]);
   string pending=fxRoot+"\\news_reduce_"+key+".csv",done=fxRoot+"\\news_reduce_done_"+key+".csv";
   if(FileIsExist(done))return false;
   if(FileIsExist(pending)){FXRequestClose("NEWS_REDUCTION_RECONCILIATION");return true;}
   double minLot=MarketInfo(Symbol(),MODE_MINLOT),step=MarketInfo(Symbol(),MODE_LOTSTEP),originalR=0;long originalBirth=0;
   if(!FXPositive(minLot) || !FXPositive(step) || !FXPositionState(originalR,originalBirth)){FXRequestClose("NEWS_LOT_METADATA_UNAVAILABLE");return true;}
   int ticket=OrderTicket(),type=OrderType();double before=OrderLots(),entry=OrderOpenPrice(),sl=OrderStopLoss(),tp=OrderTakeProfit();
   double cut=NormalizeDouble(MathFloor(before*fxSettings.newsReducePercent/100/step+1e-9)*step,8),remaining=NormalizeDouble(before-cut,8);
   if(cut<minLot-1e-10 || remaining<minLot-1e-10){FXRequestClose("NEWS_PARTIAL_MIN_LOT_FULL_EXIT");return true;}
   MqlTick q;if(!IsConnected() || !IsTradeAllowed() || IsTradeContextBusy() || !SymbolInfoTick(Symbol(),q) ||
      !FXPositive(q.bid) || !FXPositive(q.ask) || q.ask<q.bid || nowMs<(long)q.time*1000 || nowMs-(long)q.time*1000>3000)return true;
   if(!FXWriteFlag(pending,"PARTIAL_CLOSE_RESERVED")){FXRequestClose("NEWS_REDUCTION_STORAGE_FAILURE");return true;}
   FXNewsAudit("NEWS_REDUCE_RESERVED",ticket,cut);
   // Recheck the clock after disk I/O. A late quote is retried as a full protective exit.
   long current=BONowMs();if(current<(long)q.time*1000 || current-(long)q.time*1000>3000){FXRequestClose("NEWS_REDUCTION_QUOTE_EXPIRED");return true;}
   ResetLastError();bool ok=OrderClose(ticket,cut,type==OP_BUY ? q.bid : q.ask,FXSlippagePoints(),clrNONE);int error=GetLastError();
   FXEvent(ok ? "NEWS_PARTIAL_CLOSE" : "NEWS_PARTIAL_CLOSE_FAILED",key+"_ERR_"+IntegerToString(error),ticket,cut);
   int survivors=0,survivor=-1;
   for(int i=OrdersTotal()-1;i>=0;i--)if(OrderSelect(i,SELECT_BY_POS,MODE_TRADES) && FXOwnSelected()){survivors++;survivor=OrderTicket();}
   if(survivors==1 && OrderSelect(survivor,SELECT_BY_TICKET,MODE_TRADES) && FXOwnSelected()) {
      double tick=SymbolInfoDouble(Symbol(),SYMBOL_TRADE_TICK_SIZE);
      bool matched=ok && FXPositive(tick) && OrderType()==type && MathAbs(OrderLots()-remaining)<step/2 &&
         MathAbs(OrderOpenPrice()-entry)<tick/2 && MathAbs(OrderStopLoss()-sl)<tick/2 && MathAbs(OrderTakeProfit()-tp)<tick/2;
      if(matched && FXSaveState(fxRoot+"\\position_"+IntegerToString(survivor)+".csv","V222_FOREX_POSITION_V1",FXPositionKey()+"|"+DoubleToString(originalR,Digits)+"|"+IntegerToString(originalBirth)) &&
         FXWriteFlag(done,"REDUCTION_CONFIRMED"))return true;
      FXRequestClose("NEWS_REDUCTION_RESIDUAL_UNCONFIRMED");
   } else if(survivors>1) {
      // Unexpected pool changes: do not attempt another partial close; close owned positions only.
      for(int i=OrdersTotal()-1;i>=0;i--)if(OrderSelect(i,SELECT_BY_POS,MODE_TRADES) && FXOwnSelected())FXRequestClose("NEWS_REDUCTION_POOL_ANOMALY");
   }
   return true;
}
#endif
