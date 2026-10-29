#property strict
#property version "1.00"
#property description "Demo-only research observer. Records callbacks/history; no trading functions."

input string CaptureTag="research_001";
input int BootstrapM5Bars=2048;
input int OrderHistoryLookbackDays=30;

string captureRoot="";
int captureAccount=0;string captureServer="",captureSymbol="";
int leaseFile=-1,tickFile=-1,heartbeatFile=-1,barFile=-1,sessionFile=-1;
bool captureStarted=false,captureHealthy=true;
long tickRows=0,heartbeatRows=0,barRows=0,orderRows=0,tickCallbacks=0,lastClosedBar=0;
uint previousMono=0;long elapsedMs=0;

bool SafeTag(string s) {
   if(StringLen(s)<1 || StringLen(s)>32 || StringFind(s,"..")>=0)return false;
   for(int i=0;i<StringLen(s);i++){
      int c=StringGetCharacter(s,i);
      if(!((c>=48 && c<=57)||(c>=65 && c<=90)||(c>=97 && c<=122)||c==95||c==45))return false;
   }
   return true;
}
long ArrivalMs() {
   uint now=GetTickCount();elapsedMs+=(long)(uint)(now-previousMono);previousMono=now;return elapsedMs;
}
bool Wrote(bool ok) {
   if(!ok){captureHealthy=false;Print("Research recorder write failed: ",captureRoot);}
   return ok;
}
bool SameSource(){return AccountNumber()==captureAccount && AccountServer()==captureServer && Symbol()==captureSymbol && AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_DEMO;}
int NewCSV(string name){return FileOpen(captureRoot+"\\"+name+".csv",FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');}
void CloseCaptureFiles() {
   if(tickFile>=0){FileFlush(tickFile);FileClose(tickFile);tickFile=-1;}
   if(heartbeatFile>=0){FileFlush(heartbeatFile);FileClose(heartbeatFile);heartbeatFile=-1;}
   if(barFile>=0){FileFlush(barFile);FileClose(barFile);barFile=-1;}
   if(sessionFile>=0){FileFlush(sessionFile);FileClose(sessionFile);sessionFile=-1;}
   if(leaseFile>=0){FileClose(leaseFile);leaseFile=-1;}
}
void ExportClosedOrders() {
   int f=NewCSV("closed_orders");if(f<0){Wrote(false);return;}orderRows=0;
   Wrote(FileWrite(f,"ticket","symbol","type","magic","lots","opened_broker_seconds","closed_broker_seconds","entry_price","exit_price","profit","commission","swap","currency","exported_utc_seconds","history_source")>0);
   long cutoff=(long)TimeCurrent()-(long)OrderHistoryLookbackDays*86400;
   for(int i=0;i<OrdersHistoryTotal();i++)if(OrderSelect(i,SELECT_BY_POS,MODE_HISTORY)){
      if(OrderSymbol()!=Symbol() || (OrderType()!=OP_BUY && OrderType()!=OP_SELL) || OrderCloseTime()<=0 || (long)OrderCloseTime()<cutoff)continue;
      if(Wrote(FileWrite(f,OrderTicket(),OrderSymbol(),OrderType(),OrderMagicNumber(),DoubleToString(OrderLots(),8),
         (long)OrderOpenTime(),(long)OrderCloseTime(),DoubleToString(OrderOpenPrice(),Digits),DoubleToString(OrderClosePrice(),Digits),
         DoubleToString(OrderProfit(),8),DoubleToString(OrderCommission(),8),DoubleToString(OrderSwap(),8),AccountCurrency(),(long)TimeGMT(),"MT4_LOADED_HISTORY")>0))orderRows++;
   }
   FileFlush(f);FileClose(f);
}
void ExportClosedBars() {
   datetime current=iTime(Symbol(),PERIOD_M5,0);if(current<=0)return;
   if((long)iTime(Symbol(),PERIOD_M5,1)<=lastClosedBar)return;
   int n=(int)MathMin(BootstrapM5Bars,iBars(Symbol(),PERIOD_M5)-1);
   for(int shift=n;shift>=1;shift--){
      long t=(long)iTime(Symbol(),PERIOD_M5,shift);
      if(t<=lastClosedBar || t<=0 || t>=(long)current)continue;
      if(!Wrote(FileWrite(barFile,barRows+1,t,DoubleToString(iOpen(Symbol(),PERIOD_M5,shift),Digits),
         DoubleToString(iHigh(Symbol(),PERIOD_M5,shift),Digits),DoubleToString(iLow(Symbol(),PERIOD_M5,shift),Digits),
         DoubleToString(iClose(Symbol(),PERIOD_M5,shift),Digits),(long)iVolume(Symbol(),PERIOD_M5,shift),
         (long)TimeGMT(),(long)TimeCurrent(),"BROKER_CLOSED_HISTORY")>0))return;
      barRows++;lastClosedBar=t;
   }
}
void RenderCapture() {
   Comment("RESEARCH DATA RECORDER | DEMO | ",captureHealthy ? "RECORDING" : "WRITE ERROR",
      "\nOnTick rows: ",tickRows," | Heartbeats: ",heartbeatRows," | Closed M5: ",barRows,
      "\nNo trading functions | Output: MQL4/Files/",captureRoot);
}
int OnInit() {
   if(IsTesting() || AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO){Print("Research recorder requires a live-connected MT4 demo chart, not Strategy Tester.");return INIT_PARAMETERS_INCORRECT;}
   if(StringSubstr(Symbol(),0,6)!="EURUSD" || Period()!=PERIOD_M5 || !SafeTag(CaptureTag) || BootstrapM5Bars<64 || BootstrapM5Bars>10000 || OrderHistoryLookbackDays<1 || OrderHistoryLookbackDays>365)return INIT_PARAMETERS_INCORRECT;
   previousMono=GetTickCount();elapsedMs=0;tickRows=0;heartbeatRows=0;barRows=0;orderRows=0;tickCallbacks=0;lastClosedBar=0;captureHealthy=true;captureStarted=false;
   captureAccount=AccountNumber();captureServer=AccountServer();captureSymbol=Symbol();
   FolderCreate("EA_RESEARCH_CAPTURE");
   captureRoot="EA_RESEARCH_CAPTURE\\"+CaptureTag+"_"+IntegerToString((long)TimeLocal())+"_"+IntegerToString(ChartID())+"_"+IntegerToString(previousMono);
   FolderCreate(captureRoot);
   if(FileIsExist(captureRoot+"\\metadata.csv"))return INIT_FAILED;
   leaseFile=FileOpen(captureRoot+"\\instance.lock",FILE_READ|FILE_WRITE|FILE_BIN);if(leaseFile<0)return INIT_FAILED;
   tickFile=NewCSV("ticks");heartbeatFile=NewCSV("heartbeats");barFile=NewCSV("bars_m5");sessionFile=NewCSV("session");int meta=NewCSV("metadata");
   if(tickFile<0 || heartbeatFile<0 || barFile<0 || sessionFile<0 || meta<0){if(meta>=0)FileClose(meta);CloseCaptureFiles();return INIT_FAILED;}
   Wrote(FileWrite(meta,"contract","origin","account_mode","account","server","symbol","currency","digits","point","tick_size_price","tick_value","contract_size","min_lot","lot_step","max_lot","stop_level_points","freeze_level_points","started_utc_seconds","started_broker_seconds","chart_id")>0);
   Wrote(FileWrite(meta,"RESEARCH_CAPTURE_V1","LIVE_MT4_CALLBACKS","DEMO",AccountNumber(),AccountServer(),Symbol(),AccountCurrency(),Digits,
      DoubleToString(Point,10),DoubleToString(SymbolInfoDouble(Symbol(),SYMBOL_TRADE_TICK_SIZE),10),DoubleToString(MarketInfo(Symbol(),MODE_TICKVALUE),8),
      DoubleToString(MarketInfo(Symbol(),MODE_LOTSIZE),8),DoubleToString(MarketInfo(Symbol(),MODE_MINLOT),8),DoubleToString(MarketInfo(Symbol(),MODE_LOTSTEP),8),
      DoubleToString(MarketInfo(Symbol(),MODE_MAXLOT),8),(int)MarketInfo(Symbol(),MODE_STOPLEVEL),(int)MarketInfo(Symbol(),MODE_FREEZELEVEL),(long)TimeGMT(),(long)TimeCurrent(),ChartID())>0);
   FileFlush(meta);FileClose(meta);
   Wrote(FileWrite(tickFile,"sequence","quote_server_seconds","terminal_server_seconds","pc_utc_seconds","pc_local_seconds","mono_elapsed_ms","bid","ask","connected","valid_quote")>0);
   Wrote(FileWrite(heartbeatFile,"sequence","pc_utc_seconds","terminal_server_seconds","mono_elapsed_ms","connected","last_quote_server_seconds","tick_rows","io_ok")>0);
   Wrote(FileWrite(barFile,"sequence","time_broker","open","high","low","close","tick_volume","observed_utc_seconds","observed_broker_seconds","origin")>0);
   Wrote(FileWrite(sessionFile,"event","pc_utc_seconds","broker_seconds","tick_rows","heartbeat_rows","bar_rows","order_rows","tick_callbacks","io_ok")>0);
   ExportClosedBars();ExportClosedOrders();
   Wrote(FileWrite(sessionFile,"BEGIN",(long)TimeGMT(),(long)TimeCurrent(),tickRows,heartbeatRows,barRows,orderRows,tickCallbacks,captureHealthy ? 1 : 0)>0);
   if(!captureHealthy || !EventSetTimer(1)){CloseCaptureFiles();return INIT_FAILED;}
   captureStarted=true;RenderCapture();return INIT_SUCCEEDED;
}
void OnTick() {
   if(!captureStarted || !captureHealthy)return;if(!SameSource()){Wrote(false);return;}tickCallbacks++;
   MqlTick q;if(!SymbolInfoTick(Symbol(),q)){Wrote(false);RenderCapture();return;}
   long arrival=ArrivalMs();bool valid=MathIsValidNumber(q.bid) && MathIsValidNumber(q.ask) && q.bid>0 && q.ask>=q.bid;
   if(Wrote(FileWrite(tickFile,tickRows+1,(long)q.time,(long)TimeCurrent(),(long)TimeGMT(),(long)TimeLocal(),arrival,
      DoubleToString(q.bid,Digits),DoubleToString(q.ask,Digits),IsConnected() ? 1 : 0,valid ? 1 : 0)>0))tickRows++;
}
void OnTimer() {
   if(!captureStarted)return;
   if(!SameSource())Wrote(false);
   MqlTick q;bool quoted=SymbolInfoTick(Symbol(),q);
   if(Wrote(FileWrite(heartbeatFile,heartbeatRows+1,(long)TimeGMT(),(long)TimeCurrent(),ArrivalMs(),IsConnected() ? 1 : 0,
      quoted ? (long)q.time : 0,tickRows,captureHealthy ? 1 : 0)>0))heartbeatRows++;
   if(captureHealthy)ExportClosedBars();
   FileFlush(tickFile);FileFlush(heartbeatFile);FileFlush(barFile);FileFlush(sessionFile);RenderCapture();
}
void OnDeinit(const int reason) {
   EventKillTimer();
   if(captureStarted){if(SameSource())ExportClosedOrders();else Wrote(false);Wrote(FileWrite(sessionFile,"END",(long)TimeGMT(),(long)TimeCurrent(),tickRows,heartbeatRows,barRows,orderRows,tickCallbacks,captureHealthy ? 1 : 0)>0);}
   CloseCaptureFiles();captureStarted=false;Comment("");
}
