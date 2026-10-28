#property strict
#property indicator_chart_window
#property indicator_buffers 0

// Display-only companion. Never sends orders or changes another EA's objects.
input int PanelX=12;
input int PanelY=24;
input bool ShowLocalAIAssistant=true;
input string AIAssistantChannel="v224_demo";
string prefix="V224LearningMonitor_";

void Line(int index,string text,color ink=clrLightSteelBlue) {
   string name=prefix+IntegerToString(index);
   if(ObjectFind(0,name)<0)ObjectCreate(0,name,OBJ_LABEL,0,0,0);
   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_RIGHT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_ANCHOR,ANCHOR_RIGHT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,PanelX);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE,PanelY+index*21);
   ObjectSetInteger(0,name,OBJPROP_COLOR,ink);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,10);
   ObjectSetString(0,name,OBJPROP_FONT,"Arial");
   ObjectSetString(0,name,OBJPROP_TEXT,text);
}

void UpdateLearningPanel() {
   Line(0,"BO HOC V2.24 | CHI GIAM SAT",clrAqua);
   int handle=FileOpen("V224Supervisor\\learning_status.csv",FILE_CSV|FILE_READ|FILE_COMMON|FILE_SHARE_READ|FILE_SHARE_WRITE,',');
   if(handle==INVALID_HANDLE) {
      Line(1,"CHUA NHAN DU LIEU TU CMD",clrYellow);
      for(int k=2;k<8;k++)Line(k,"");
      return;
   }
   int schema=(int)FileReadNumber(handle);
   long updated=(long)FileReadNumber(handle);
   int level=(int)FileReadNumber(handle);
   int cases=(int)FileReadNumber(handle);
   int decisive=(int)FileReadNumber(handle);
   int forecasts=(int)FileReadNumber(handle);
   int models=(int)FileReadNumber(handle);
   string state=FileReadString(handle);
   string experience=FileReadString(handle);
   string proposal=FileReadString(handle);
   FileClose(handle);
   if(schema!=2 || level<0 || level>3) {
      Line(1,"TELEMETRY KHONG HOP LE",clrYellow);
      for(int j=2;j<8;j++)Line(j,"");
      return;
   }
   string stage="CHO DU LIEU";
   if(level==1)stage="DANG THU THAP";
   if(level==2)stage="DA HUAN LUYEN - SHADOW";
   if(level==3)stage="DANG KIEM THU DU BAO";
   long age=(long)TimeGMT()-updated;
   bool stale=(age>30 || age< -5 || state=="ERROR");
   Line(1,stale ? "CMD DUNG / DU LIEU CU - KIEM TRA CMD" : stage,stale ? clrYellow : clrLimeGreen);
   Line(2,"Mau doi soat: "+IntegerToString(decisive)+" | Mo hinh: "+IntegerToString(models)+" | Du bao truoc gio: "+IntegerToString(forecasts));
   Line(3,"Ghi nhan: "+experience);
   Line(4,"De xuat: "+proposal);
   Line(5,"Bo hoc ket qua: QUAN SAT | Chi tiet: dashboard.html",clrYellow);
   Line(6,"");Line(7,"");
   ChartRedraw();
}

bool AISafeChannel(string value) {
   int size=StringLen(value);if(size<1 || size>48)return false;
   for(int i=0;i<size;i++) {
      int c=StringGetCharacter(value,i);
      if(!((c>=48 && c<=57)||(c>=65 && c<=90)||(c>=97 && c<=122)||c==95||c==45))return false;
   }
   return true;
}

void UpdateAIPanel() {
   for(int i=6;i<10;i++)Line(i,"");
   if(!ShowLocalAIAssistant)return;
   Line(6,"AI CUC BO | CHI QUAN SAT",clrAqua);
   if(!AISafeChannel(AIAssistantChannel)){Line(7,"AI: CHANNEL KHONG HOP LE",clrYellow);return;}
   string path="V224Assistant\\"+AIAssistantChannel+"\\status.csv";
   int f=FileOpen(path,FILE_CSV|FILE_READ|FILE_COMMON|FILE_SHARE_READ|FILE_SHARE_WRITE,',');
   if(f==INVALID_HANDLE){Line(7,"AI: CHUA CHAY CMD TRO LY",clrYellow);return;}
   if(FileSize(f)>4096){FileClose(f);Line(7,"AI: TELEMETRY KHONG HOP LE",clrYellow);return;}
   string cells[15];bool ok=true;
   for(int j=0;j<15;j++){if(FileIsEnding(f)){ok=false;break;}cells[j]=FileReadString(f);}
   if(!FileIsEnding(f))ok=false;
   FileClose(f);
   if(!ok || cells[0]!="1" || cells[3]!=Symbol() || cells[4]!="BINARY_RESEARCH" || cells[5]!="300" || cells[7]!=AIAssistantChannel ||
      (cells[2]!="LIVE_MT4" && cells[2]!="BACKTEST_MT4")) {
      Line(7,"AI: SAI SYMBOL / CHANNEL / TELEMETRY",clrYellow);return;
   }
   long age=(long)TimeGMT()-(long)StringToInteger(cells[1]);
   if(age>30 || age< -5 || cells[12]=="ERROR") {Line(7,"AI: CMD DUNG / DU LIEU CU / LOI",clrYellow);return;}
   if(cells[12]=="SOURCE_STALE" || cells[12]=="SOURCE_CLOCK_AHEAD") {Line(7,"AI: NGUON EA CU / DONG HO LECH",clrYellow);return;}
   if(Period()!=PERIOD_M5){Line(7,"AI: DU LIEU M5 - KHAC KHUNG CHART",clrYellow);return;}
   string model="MO HINH CHUA CAU HINH";
   if(cells[11]=="LOCAL_MODEL_SELECTED_EVIDENCE")model="MO HINH DA CHON DU KIEN";
   if(cells[11]=="LOCAL_MODEL_UNAVAILABLE")model="MO HINH KHONG SAN SANG";
   if(cells[11]=="LOCAL_MODEL_WAITING" || cells[11]=="LOCAL_MODEL_WAITING_NEW_FACTS")model="CHO MO HINH / DU KIEN MOI";
   Line(6,"AI CUC BO | "+model,clrAqua);
   Line(7,"RC1: "+cells[8]+" | Tuoi xac nhan: "+cells[9]+" | "+cells[10]);
   Line(8,"De xuat: "+cells[14]);
   if(cells[2]=="BACKTEST_MT4")Line(9,"AI: HOI CUU TESTER | KHONG PHAI DU BAO LIVE",clrYellow);
   else if(cells[12]=="CATCHING_UP")Line(9,"AI: DANG DOC NHAT KY | KHONG CAN THIEP",clrYellow);
   else if(cells[12]=="COLLECTING_CLOCK_UNKNOWN")Line(9,"AI: CHUA XAC NHAN MUI GIO | KHONG CAN THIEP",clrYellow);
   else Line(9,"AI: CHUA CO MODEL WIN/LOSS 30 PHUT | KHONG CAN THIEP",clrYellow);
}

void UpdatePanel(){UpdateLearningPanel();UpdateAIPanel();ChartRedraw();}

int OnInit(){EventSetTimer(2);UpdatePanel();return INIT_SUCCEEDED;}
void OnTimer(){UpdatePanel();}
void OnDeinit(const int reason){EventKillTimer();for(int i=0;i<10;i++)ObjectDelete(0,prefix+IntegerToString(i));}
int OnCalculate(const int rates_total,const int prev_calculated,const datetime &time[],const double &open[],const double &high[],const double &low[],const double &close[],const long &tick_volume[],const long &volume[],const int &spread[]){return rates_total;}
