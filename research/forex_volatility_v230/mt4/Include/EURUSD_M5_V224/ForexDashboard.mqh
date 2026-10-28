#ifndef FX_V229_DASHBOARD
#define FX_V229_DASHBOARD
// Read-only presentation. Do not call entry, risk, news or management guards here.
#define FX_DASH_ROWS 48
#define FX_DASH_POSITIONS 3
bool fxDashboardEnabled=true;
int fxDashboardFontSize=14,fxDashboardActionSize=22,fxDashboardLeft=12,fxDashboardTop=20;
string fxDashboardFont="Arial",fxDashboardRelease="V2.29";
void FXDashboardConfigure(bool enabled,int size,int actionSize,string font,int left,int top,string release) {
   fxDashboardEnabled=enabled;fxDashboardFontSize=(int)MathMax(12,MathMin(24,size));
   fxDashboardActionSize=(int)MathMax(fxDashboardFontSize,MathMin(24,actionSize));
   fxDashboardFont=StringLen(font)>0 ? font : "Arial";
   fxDashboardLeft=(int)MathMax(0,left);fxDashboardTop=(int)MathMax(0,top);fxDashboardRelease=release;
}
void FXDashboardDelete() {
   for(int i=0;i<FX_DASH_ROWS;i++)ObjectDelete(0,"FX_V229_LINE_"+IntegerToString(i));
   ObjectDelete(0,"FX_V229_BACKGROUND");
}
void FXDashboardRow(int &row,int &y,string text,int size,color tone) {
   if(row>=FX_DASH_ROWS)return;
   BOUILabel("FX_V229_LINE_"+IntegerToString(row),text,fxDashboardLeft+14,y,size,tone,fxDashboardFont);
   row++;y+=(size*4+2)/3+7;
}
void FXDashboardSection(int &row,int &y,string text) {
   y+=6;FXDashboardRow(row,y,text,fxDashboardFontSize,clrDeepSkyBlue);
}
string FXDashboardMoney(double value) { return DoubleToString(value,2)+" "+AccountCurrency(); }
string FXDashboardFlag(bool value) { return value ? "ON" : "OFF"; }
string FXDashboardReason() {
   if(fxStatus=="WAIT_NEXT_COMPLETE_M5")return "Cho chu ky M5 hoan chinh tiep theo";
   if(fxStatus=="REAL_TRADING_DISABLED")return "Tai khoan Real chua duoc cho phep";
   if(fxStatus=="TERMINAL_TRADING_UNAVAILABLE")return "MT4 chua cho phep giao dich";
   if(fxStatus=="EURUSD_ORDER_ALREADY_EXISTS")return "Da co lenh trong ho EURUSD";
   if(fxStatus=="DAILY_LOSS_LIMIT")return "Da cham gioi han giam Equity ngay";
   if(fxStatus=="EXIT_COOLDOWN")return "Dang cho het thoi gian nghi sau lenh";
   if(fxStatus=="SPREAD_LIMIT")return "Spread vuot gioi han";
   if(fxStatus=="MARGIN_RESERVE_LIMIT")return "Chua du margin du tru theo cau hinh";
   if(fxStatus=="TRADING_DISABLED")return "Dang tat mo lenh moi";
   if(StringFind(fxStatus,"ANALYSIS_")==0)return "Dang phan tich chu ky M5";
   if(StringFind(fxStatus,"NEWS_")==0)return "Chua dat dieu kien lich tin Forex";
   return fxStatus;
}
// Read and validate original basket birth without changing fxHealthy/status on error.
bool FXDashboardBirth(long &birth) {
   birth=0;string path=fxRoot+"\\position_"+IntegerToString(OrderTicket())+".csv";
   int f=FileOpen(path,FILE_READ|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');if(f==INVALID_HANDLE)return false;
   string cells[];bool ok=BODemoReadCells(f,3,cells) && FileIsEnding(f);FileClose(f);
   if(!ok || cells[0]!="V222_FOREX_POSITION_V1" || cells[2]!=IntegerToString((long)BOHashText(cells[1])))return false;
   string parts[];if(StringSplit(cells[1],124,parts)!=6)return false;
   long candidate=StringToInteger(parts[5]);double originalR=StringToDouble(parts[4]);
   if(!FXPositive(originalR) || candidate<=0 || candidate>(long)OrderOpenTime() ||
      cells[1]!=FXPositionKey()+"|"+DoubleToString(originalR,Digits)+"|"+IntegerToString(candidate))return false;
   birth=candidate;return true;
}
string FXDashboardHold(long now) {
   long birth=0;
   if(!FXDashboardBirth(birth) || now<birth)return "Thoi gian giu: CHUA XAC THUC STATE";
   string held=BOUICountdown(now-birth);
   if(fxSettings.maxHoldMinutes<=0)return "Da giu: "+held+" | Khong gioi han thoi gian";
   long deadline=birth+fxSettings.maxHoldMinutes*60;
   return "Da giu: "+held+" | Con lai: "+BOUICountdown(deadline-now)+" | Han "+TimeToString((datetime)deadline,TIME_SECONDS)+" broker";
}
void FXDashboardComment(string legacyText) {
   if(legacyText==""){FXDashboardDelete();Comment("");return;}
   if(!fxDashboardEnabled){FXDashboardDelete();Comment(legacyText);return;}
   Comment("");
   int size=fxDashboardFontSize,small=(int)MathMax(12,size-2);
   int row=0,y=fxDashboardTop+12,own=0,otherEURUSD=0,shown=0;double floating=0;
   long now=BONowMs();long seconds=now>0 ? now/1000 : (long)TimeCurrent();
   string orderLines[FX_DASH_POSITIONS],priceLines[FX_DASH_POSITIONS],holdLines[FX_DASH_POSITIONS];
   bool protectedOrders[FX_DASH_POSITIONS];
   for(int i=OrdersTotal()-1;i>=0;i--)if(OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) {
      if(FXOwnSelected()) {
         own++;double net=OrderProfit()+OrderSwap()+OrderCommission();floating+=net;
         if(shown<FX_DASH_POSITIONS) {
            string side=OrderType()==OP_BUY ? "BUY" : "SELL";
            orderLines[shown]=side+" #"+IntegerToString(OrderTicket())+" | "+
               DoubleToString(OrderLots(),2)+" lot | P/L "+FXDashboardMoney(net);
            priceLines[shown]="Vao "+DoubleToString(OrderOpenPrice(),Digits)+" | SL "+DoubleToString(OrderStopLoss(),Digits)+" | TP "+DoubleToString(OrderTakeProfit(),Digits);
            holdLines[shown]=FXDashboardHold(seconds);protectedOrders[shown]=OrderStopLoss()>0 && OrderTakeProfit()>0;shown++;
         }
      } else {
         string name=OrderSymbol();StringToUpper(name);if(StringFind(name,"EURUSD")==0)otherEURUSD++;
      }
   }
   string account=IsTesting() ? "TESTER" : AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_REAL ? "REAL" : "DEMO";
   string headline=own>0 ? "CO VI THE MO" : "CHO DIEU KIEN VAO LENH";color statusTone=own>0 ? clrAqua : clrGold;
   if(!fxSettings.enabled && own==0){headline="TAM DUNG MO LENH";statusTone=clrSilver;}
   if(account=="REAL" && !fxSettings.allowReal && own==0){headline="CHUA CHO PHEP REAL";statusTone=clrGold;}
   if(!IsTradeAllowed()) {
      headline=own>0 ? "CO VI THE | GIAO DICH BI CHAN" : "QUYEN GIAO DICH MT4 TAT";
      if(!IsExpertEnabled())headline="AUTOTRADING MT4 DANG TAT";
      else if(!MQLInfoInteger(MQL_TRADE_ALLOWED))headline="EA CHUA DUOC CAP QUYEN";
      else if(IsTradeContextBusy())headline="TRADE CONTEXT DANG BAN";
      statusTone=clrGold;
   }
   if(!IsConnected()){headline="MAT KET NOI BROKER";statusTone=clrTomato;}
   if(fxDayHalted){headline="DA CHAM GIOI HAN LO NGAY";statusTone=clrTomato;}
   if(!fxHealthy){headline="LOI LUU TRU | CHAN MO MOI";statusTone=clrTomato;}
   string background="FX_V229_BACKGROUND";
   if(ObjectFind(0,background)<0)ObjectCreate(0,background,OBJ_RECTANGLE_LABEL,0,0,0);
   ObjectSetInteger(0,background,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,background,OBJPROP_XDISTANCE,fxDashboardLeft);ObjectSetInteger(0,background,OBJPROP_YDISTANCE,fxDashboardTop);
   ObjectSetInteger(0,background,OBJPROP_XSIZE,size*42+56);ObjectSetInteger(0,background,OBJPROP_BGCOLOR,BO_UI_BACKGROUND);
   ObjectSetInteger(0,background,OBJPROP_BORDER_TYPE,BORDER_FLAT);ObjectSetInteger(0,background,OBJPROP_COLOR,clrSlateGray);
   ObjectSetInteger(0,background,OBJPROP_BACK,false);ObjectSetInteger(0,background,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,background,OBJPROP_HIDDEN,true);ObjectSetInteger(0,background,OBJPROP_ZORDER,0);
   FXDashboardRow(row,y,Symbol()+" M5 | "+fxDashboardRelease+" FOREX | "+account,size+2,clrWhiteSmoke);
   FXDashboardRow(row,y,AccountServer()+" | #"+IntegerToString(AccountNumber())+" | Magic "+IntegerToString(fxSettings.magic),small,clrSilver);
   FXDashboardRow(row,y,headline,fxDashboardActionSize,statusTone);
   FXDashboardRow(row,y,FXDashboardReason(),size,statusTone);
   FXDashboardRow(row,y,"Ma native: "+fxStatus,small,clrSilver);

   FXDashboardSection(row,y,"TAI KHOAN DUNG CHUNG | RUI RO");
   FXDashboardRow(row,y,"Balance "+FXDashboardMoney(AccountBalance())+" | Equity "+FXDashboardMoney(AccountEquity()),size,clrWhiteSmoke);
   double margin=AccountMargin();string level=margin>0 ? DoubleToString(AccountEquity()/margin*100,1)+"%" : "N/A (khong dung margin)";
   FXDashboardRow(row,y,"Free margin "+FXDashboardMoney(AccountFreeMargin())+" | Margin level "+level,small,clrWhiteSmoke);
   FXDashboardRow(row,y,"Du tru: Margin level >= "+DoubleToString(fxSettings.minMarginLevelPercent,0)+"% | Free/Equity >= "+DoubleToString(fxSettings.minFreeEquityPercent,0)+"%",small,clrSilver);
   double cap=MathMax(0,MathMin(AccountBalance(),AccountEquity()))*fxSettings.riskPercent/100;
   FXDashboardRow(row,y,"Tran rui ro theo von: "+DoubleToString(fxSettings.riskPercent,2)+"% = "+FXDashboardMoney(cap),size,cap>0 ? clrWhiteSmoke : clrGold);
   string day=fxDayEquity>0 ? DoubleToString(MathMax(0,(fxDayEquity-AccountEquity())/fxDayEquity*100),2)+"%" : "CHUA CO MOC EQUITY";
   FXDashboardRow(row,y,"Giam Equity ngay: "+day+" / "+DoubleToString(fxSettings.dailyLossPercent,2)+"%"+(fxDayHalted ? " | DA KHOA" : ""),size,fxDayHalted ? clrTomato : clrWhiteSmoke);
   FXDashboardRow(row,y,"Luot vao: "+IntegerToString(fxDailyAttempts)+"/"+IntegerToString(fxSettings.maxDailyAttempts)+" | Chuoi thua: "+IntegerToString(fxLossStreak)+"/"+IntegerToString(fxSettings.maxLossStreak),small,clrSilver);
   long cooldown=fxLatestExit>0 ? (long)MathMax(0,fxLatestExit+fxSettings.cooldownMinutes*60-seconds) : 0;
   FXDashboardRow(row,y,"Cho sau lenh: "+BOUICountdown(cooldown)+" | Cau hinh "+IntegerToString(fxSettings.cooldownMinutes)+" phut",small,cooldown>0 ? clrGold : clrSilver);

   FXDashboardSection(row,y,"VI THE CUA EA | "+IntegerToString(own)+" LENH");
   FXDashboardRow(row,y,"P/L tha noi EA: "+FXDashboardMoney(floating),size,floating<0 ? clrTomato : floating>0 ? clrLimeGreen : clrWhiteSmoke);
   if(own==0)FXDashboardRow(row,y,"Chua co vi the cua EA tren symbol nay",size,clrSilver);
   for(int p=0;p<shown;p++) {
      FXDashboardRow(row,y,orderLines[p],size,clrWhiteSmoke);
      FXDashboardRow(row,y,priceLines[p],small,protectedOrders[p] ? clrSilver : clrTomato);
      FXDashboardRow(row,y,holdLines[p],small,clrSilver);
   }
   if(own>shown)FXDashboardRow(row,y,"Con "+IntegerToString(own-shown)+" lenh; xem them trong Terminal / Trade",small,clrGold);
   if(otherEURUSD>0)FXDashboardRow(row,y,"Lenh EURUSD khac / pending: "+IntegerToString(otherEURUSD)+" | Can chu y exposure",small,clrGold);

   FXDashboardSection(row,y,"DIEU KIEN THI TRUONG | VAN HANH");
   MqlTick q;bool quote=SymbolInfoTick(Symbol(),q) && FXPositive(q.bid) && FXPositive(q.ask) && q.ask>=q.bid;
   double spread=quote ? (q.ask-q.bid)/.0001 : -1;
   FXDashboardRow(row,y,"Spread: "+(quote ? DoubleToString(spread,2)+" pip" : "N/A")+" | Gioi han "+DoubleToString(fxSettings.maxSpreadPips,2)+" pip",size,spread>=0 && spread<=fxSettings.maxSpreadPips ? clrWhiteSmoke : clrGold);
   FXDashboardRow(row,y,"Ket noi: "+FXDashboardFlag(IsConnected())+" | Quyen MT4: "+FXDashboardFlag(IsTradeAllowed())+" | Real opt-in: "+FXDashboardFlag(fxSettings.allowReal),small,IsConnected() && IsTradeAllowed() ? clrLimeGreen : clrGold);
   FXDashboardRow(row,y,"AutoTrading MT4: "+FXDashboardFlag(IsExpertEnabled())+" | Allow live trading EA: "+FXDashboardFlag(MQLInfoInteger(MQL_TRADE_ALLOWED)!=0),small,IsExpertEnabled() && MQLInfoInteger(MQL_TRADE_ALLOWED) ? clrWhiteSmoke : clrGold);
   FXDashboardRow(row,y,"Loc tin: "+(fxSettings.newsFilter ? fxNewsStatus : "TAT"),size,fxSettings.newsFilter && fxNewsStatus=="NEWS_CLEAR" ? clrLimeGreen : clrGold);
   if(fxNewsSelected>=0 && fxNewsSelected<fxNewsCount)FXDashboardRow(row,y,"Tin lien quan: "+fxNewsLabels[fxNewsSelected],small,clrGold);
   string age=quote && now>0 && now>=(long)q.time*1000 ? DoubleToString((now-(long)q.time*1000)/1000.0,1)+"s" : "N/A";
   FXDashboardRow(row,y,"Gio broker: "+TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS)+" | Tuoi quote: "+age,small,clrSilver);

   FXDashboardSection(row,y,"BAO VE LENH");
   FXDashboardRow(row,y,"Break-even: "+FXDashboardFlag(fxSettings.breakEven)+" | Trailing: "+FXDashboardFlag(fxSettings.trailing)+" | TP "+DoubleToString(fxSettings.rewardRisk,1)+"R",size,clrWhiteSmoke);
   string holdLimit=fxSettings.maxHoldMinutes>0 ? "Giu toi da "+IntegerToString(fxSettings.maxHoldMinutes)+" phut" : "Giu: KHONG GIOI HAN";
   FXDashboardRow(row,y,"Bao ve: "+(own>0 ? fxProtectionStatus : "Chua co vi the")+" | "+holdLimit,small,clrSilver);
   FXDashboardRow(row,y,"Binh quan: "+FXDashboardFlag(fxSettings.averaging)+" | Lich broker: "+FXDashboardFlag(fxSettings.schedule)+" | Emergency close: "+FXDashboardFlag(fxSettings.emergencyClose),small,fxSettings.emergencyClose ? clrTomato : clrSilver);
   FXDashboardRow(row,y,"Da dong (lich su MT4 dang tai): "+IntegerToString(fxClosedTrades)+" | Net "+FXDashboardMoney(fxClosedNet),small,clrSilver);
   FXDashboardRow(row,y,"Nhat ky: "+fxRoot,small,clrSilver);
   for(int stale=row;stale<FX_DASH_ROWS;stale++)ObjectDelete(0,"FX_V229_LINE_"+IntegerToString(stale));
   ObjectSetInteger(0,background,OBJPROP_YSIZE,y-fxDashboardTop+12);ChartRedraw(0);
}
#endif
