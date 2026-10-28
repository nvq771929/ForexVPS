#ifndef BO_V222_DEMO_LEARNING
#define BO_V222_DEMO_LEARNING
#include "Episode.mqh"
#include "Contract.mqh"

// Data-only local companion. No WebRequest, account credentials or order API.
struct BODemoLearnRow {
   int setup; int direction; int regime; int horizon; int decision;
   long modelId; double probability; int trainCount; int testCount;
   double minATR; double maxATR;
};
BODemoLearnRow boLearnRows[64]; int boLearnCount=0;
uint boDemoPolicy=0,boDemoConfig=0,boDemoFeed=0; int boDemoHorizon=1;
long boLearnAsOf=0,boLearnExpires=0,boLearnNextRead=0;
bool boLearnBad=false,boLearnSeen=false;
string boLearnStatus="COLLECTING";
uint boLearnReadMono=0; bool boLearnReadTried=false;
long boPaperSignals=0,boPaperWins=0,boPaperLosses=0,boPaperTies=0,boPaperMissing=0,boPaperOpen=0;
string boPaperLast="N/A";

void BODemoReset() {
   boLearnReadMono=0; boLearnReadTried=false;
   boLearnCount=0; boLearnAsOf=0; boLearnExpires=0; boLearnNextRead=0;
   boLearnBad=false; boLearnSeen=false; boLearnStatus="COLLECTING";
   boPaperSignals=0; boPaperWins=0; boPaperLosses=0; boPaperTies=0; boPaperMissing=0; boPaperOpen=0; boPaperLast="N/A";
}

bool BODemoInteger(string value) {
   if(StringLen(value)==0) return false;
   int start=StringGetCharacter(value,0)==45 ? 1 : 0;
   if(start==StringLen(value)) return false;
   for(int i=start;i<StringLen(value);i++) if(StringGetCharacter(value,i)<48 || StringGetCharacter(value,i)>57) return false;
   return true;
}
bool BODemoNumber(string value) {
   if(StringLen(value)==0) return false;
   int dots=0,digits=0;
   for(int i=0;i<StringLen(value);i++) {
      int ch=StringGetCharacter(value,i);
      if(ch==46) dots++;
      else if(ch>=48 && ch<=57) digits++;
      else if(!(ch==45 && i==0)) return false;
   }
   return dots<=1 && digits>0 && MathIsValidNumber(StringToDouble(value));
}
bool BODemoReadCells(int file,int count,string &cells[]) {
   ArrayResize(cells,count);
   for(int i=0;i<count;i++) {
      if(FileIsEnding(file)) return false;
      cells[i]=FileReadString(file);
      if(i<count-1 && FileIsLineEnding(file)) return false;
   }
   return FileIsLineEnding(file);
}
bool BODemoBindPolicy(string root,uint config,uint feed,int horizon,bool enabled,bool learning) {
   boDemoConfig=config; boDemoFeed=feed; boDemoHorizon=horizon;
   boDemoPolicy=BOHashText("DEMO1|"+IntegerToString(config)+"|"+IntegerToString(feed)+"|"+
      IntegerToString(horizon)+"|"+IntegerToString(enabled ? 1 : 0)+"|"+IntegerToString(learning ? 1 : 0));
   string name=root+"\\demo_policy.csv";
   string names[8]={"schema","logic","config_hash","feed_hash","policy_hash","horizon","enabled","learning"};
   if(FileIsExist(name)) {
      int file=FileOpen(name,FILE_READ|FILE_CSV|FILE_ANSI,','); if(file==INVALID_HANDLE) return false;
      string header[]; string row[]; bool ok=BODemoReadCells(file,8,header) && BODemoReadCells(file,8,row) && FileIsEnding(file);
      if(ok) for(int i=0;i<8;i++) if(header[i]!=names[i] || !BODemoInteger(row[i])) ok=false;
      if(ok) ok=StringToInteger(row[0])==1 && StringToInteger(row[1])==BO_LOGIC_VERSION &&
         (uint)StringToInteger(row[2])==config && (uint)StringToInteger(row[3])==feed &&
         (uint)StringToInteger(row[4])==boDemoPolicy && StringToInteger(row[5])==horizon &&
         StringToInteger(row[6])==(enabled ? 1 : 0) && StringToInteger(row[7])==(learning ? 1 : 0);
      FileClose(file); return ok;
   }
   string temp=name+".tmp";
   if(FileIsExist(temp)) return false;
   int file=FileOpen(temp,FILE_WRITE|FILE_CSV|FILE_ANSI,','); if(file==INVALID_HANDLE) return false;
   bool ok=FileWrite(file,"schema","logic","config_hash","feed_hash","policy_hash","horizon","enabled","learning")>0;
   if(FileWrite(file,1,BO_LOGIC_VERSION,config,feed,boDemoPolicy,horizon,enabled ? 1 : 0,learning ? 1 : 0)==0) ok=false;
   FileFlush(file); FileClose(file); return ok && FileMove(temp,0,name,0);
}
bool BOLearnLoad(string root,long now) {
   boLearnCount=0; boLearnBad=false;
   string path=root+"\\learning_model_v207.csv";
   if(!FileIsExist(path)) {
      boLearnBad=boLearnSeen || FileIsExist(root+"\\learning_seen.csv");
      boLearnStatus=boLearnBad ? "MODEL_MISSING" : "COLLECTING"; return !boLearnBad;
   }
   boLearnBad=true; boLearnStatus="INVALID_MODEL";
   int file=FileOpen(path,FILE_READ|FILE_CSV|FILE_ANSI,','); if(file==INVALID_HANDLE) return false;
   string expected[22]={"schema","source","logic","config_hash","feed_hash","policy_hash","asof","expires","model_id",
      "setup","direction","regime","horizon","decision","p_win","n_train","n_test","atr_min","atr_max","validated","row_count","reserved"};
   string cells[]; bool ok=BODemoReadCells(file,22,cells);
   if(ok) for(int i=0;i<22;i++) if(cells[i]!=expected[i]) ok=false;
   int count=0,expectedRows=-1; long asof=0,expires=0;
   while(ok && !FileIsEnding(file)) {
      if(!BODemoReadCells(file,22,cells)) { ok=false; break; }
      for(int j=0;j<22;j++) if(j!=1 && j!=14 && j!=17 && j!=18 && !BODemoInteger(cells[j])) ok=false;
      if(!BODemoNumber(cells[14]) || !BODemoNumber(cells[17]) || !BODemoNumber(cells[18])) ok=false;
      if(!ok) break;
      if(StringToInteger(cells[0])!=1 || cells[1]!="MT4_SIMULATED" || StringToInteger(cells[2])!=BO_LOGIC_VERSION ||
         (uint)StringToInteger(cells[3])!=boDemoConfig || (uint)StringToInteger(cells[4])!=boDemoFeed ||
         (uint)StringToInteger(cells[5])!=boDemoPolicy || StringToInteger(cells[12])!=boDemoHorizon || StringToInteger(cells[21])!=0) { ok=false; break; }
      long rowAsOf=StringToInteger(cells[6]),rowExpires=StringToInteger(cells[7]);
      if(rowAsOf<=0 || rowAsOf>now || rowExpires<=rowAsOf || rowExpires<=now || rowExpires-rowAsOf>86400) { ok=false; break; }
      if(expectedRows<0) {
         expectedRows=(int)StringToInteger(cells[20]); asof=rowAsOf; expires=rowExpires;
         if(expectedRows<0 || expectedRows>64 || StringToInteger(cells[8])!=0 || StringToInteger(cells[9])!=0 ||
            StringToInteger(cells[10])!=0 || StringToInteger(cells[11])!=0 || StringToInteger(cells[13])!=0 ||
            StringToInteger(cells[19])!=0) ok=false;
         continue;
      }
      if(count>=expectedRows || rowAsOf!=asof || rowExpires!=expires || StringToInteger(cells[20])!=expectedRows) { ok=false; break; }
      BODemoLearnRow row; ZeroMemory(row);
      row.modelId=StringToInteger(cells[8]); row.setup=(int)StringToInteger(cells[9]); row.direction=(int)StringToInteger(cells[10]);
      row.regime=(int)StringToInteger(cells[11]); row.horizon=(int)StringToInteger(cells[12]); row.decision=(int)StringToInteger(cells[13]);
      row.probability=StringToDouble(cells[14]); row.trainCount=(int)StringToInteger(cells[15]); row.testCount=(int)StringToInteger(cells[16]);
      row.minATR=StringToDouble(cells[17]); row.maxATR=StringToDouble(cells[18]); int validated=(int)StringToInteger(cells[19]);
      if(row.modelId<=0 || row.modelId>asof*1000+999 || row.setup<1 || row.setup>3 || (row.direction!=1 && row.direction!=-1) ||
         row.setup!=BORoutedStrategy(row.regime) || row.decision< -1 || row.decision>1 || row.probability<0 || row.probability>1 ||
         row.trainCount<0 || row.testCount<0 || row.minATR<=0 || row.maxATR<row.minATR ||
         (validated!=0 && validated!=1) || (row.decision!=0 && (validated!=1 || row.trainCount<200 || row.testCount<100))) { ok=false; break; }
      for(int k=0;k<count;k++) if(boLearnRows[k].setup==row.setup && boLearnRows[k].direction==row.direction && boLearnRows[k].regime==row.regime) ok=false;
      if(!ok) break;
      boLearnRows[count]=row; count++;
   }
   FileClose(file);
   if(!ok || expectedRows<0 || count!=expectedRows || (boLearnSeen && asof<boLearnAsOf)) { boLearnCount=0; return false; }
   boLearnAsOf=asof; boLearnExpires=expires; boLearnCount=count; boLearnBad=false; boLearnSeen=true;
   boLearnStatus=count>0 ? "LEARNING" : "COLLECTING";
   if(!FileIsExist(root+"\\learning_seen.csv")) {
      int marker=FileOpen(root+"\\learning_seen.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
      if(marker==INVALID_HANDLE) { boLearnBad=true; return false; }
      bool stored=FileWrite(marker,1,boDemoPolicy,asof)>0; FileFlush(marker); FileClose(marker);
      if(!stored) { boLearnBad=true; return false; }
   }
   return true;
}
void BOLearnSummary(string root) {
   int file=FileOpen(root+"\\paper_summary_v207.csv",FILE_READ|FILE_CSV|FILE_ANSI,','); if(file==INVALID_HANDLE) return;
   string expected[16]={"schema","source","logic","config_hash","feed_hash","policy_hash","asof","signals","wins","losses",
      "ties","unavailable","pending","last_target","last_direction","last_result"};
   string header[]; string row[];
   bool ok=BODemoReadCells(file,16,header) && BODemoReadCells(file,16,row) && FileIsEnding(file);
   if(ok) for(int i=0;i<16;i++) if(header[i]!=expected[i] || (i!=1 && !BODemoInteger(row[i]))) ok=false;
   if(ok) ok=row[1]=="MT4_SIMULATED" && StringToInteger(row[0])==1 && StringToInteger(row[2])==BO_LOGIC_VERSION &&
      (uint)StringToInteger(row[3])==boDemoConfig && (uint)StringToInteger(row[4])==boDemoFeed && (uint)StringToInteger(row[5])==boDemoPolicy;
   if(ok) {
      long total=0;
      for(int j=7;j<=13;j++) if(StringToInteger(row[j])<0) ok=false;
      for(int j=8;j<=12;j++) total+=StringToInteger(row[j]);
      int last=(int)StringToInteger(row[15]),direction=(int)StringToInteger(row[14]);
      if(total!=StringToInteger(row[7]) || StringToInteger(row[6])<=0 || (direction!=0 && direction!=1 && direction!=-1) ||
         (last!=1 && last!=-1 && last!=0 && last!=8 && last!=9)) ok=false;
   }
   if(ok) {
      boPaperSignals=StringToInteger(row[7]); boPaperWins=StringToInteger(row[8]); boPaperLosses=StringToInteger(row[9]);
      boPaperTies=StringToInteger(row[10]); boPaperMissing=StringToInteger(row[11]); boPaperOpen=StringToInteger(row[12]);
      int result=(int)StringToInteger(row[15]); boPaperLast=result==1 ? "WIN" : result==-1 ? "LOSS" : result==0 ? "TIE" : result==9 ? "UNAVAILABLE" : "N/A";
   }
   FileClose(file);
}
void BOLearnRefresh(string root,long now) {
   if(now<=0) return;
   uint mono=GetTickCount(); if(boLearnReadTried && (uint)(mono-boLearnReadMono)<15000) return;
   boLearnReadTried=true; boLearnReadMono=mono; boLearnNextRead=now+15; BOLearnLoad(root,now); BOLearnSummary(root);
}
void BODemoLock(BOPrediction &e,const BOConfig &c,long nowMs,bool enabled,bool paused,int horizon,bool useLearning) {
   if(e.locked || horizon<1 || horizon>3) return;
   BOProbability empty[]; ArrayResize(empty,3);
   for(int i=0;i<3;i++) ZeroMemory(empty[i]);
   BOLock(e,c,nowMs,true,paused,empty);
   if(!enabled || paused || e.canceled || e.lockedDirection==0 || e.validation!=BO_CONFIRMED || e.reason!=BO_SHADOW_ONLY) return;
   if(useLearning && (boLearnBad || (boLearnSeen && nowMs/1000>=boLearnExpires))) { e.reason=BO_MODEL_UNAVAILABLE; return; }
   e.modelId=0;
   if(useLearning) for(int j=0;j<boLearnCount;j++) {
      BODemoLearnRow row=boLearnRows[j];
      if(row.setup!=e.candidate.setup || row.direction!=e.lockedDirection || row.regime!=e.anchor.regime || row.horizon!=horizon) continue;
      double atr=e.anchor.volatility.atr/.0001;
      if(atr<row.minATR || atr>row.maxATR) continue;
      e.modelId=row.modelId;
      if(horizon==1)e.p1=row.probability; if(horizon==2)e.p2=row.probability; if(horizon==3)e.p3=row.probability;
      if(row.decision<0) { e.reason=BO_NO_EDGE; return; }
   }
   // Explicit exploratory DEMO publication; preserves price/structure/lock guards.
   // modelId=0 means cold start. This never qualifies an actual broker order.
   e.horizon=horizon; e.lockedAction=e.lockedDirection; e.action=e.lockedDirection; e.reason=BO_OK;
}
#endif
