#ifndef BO_V222_MANUAL_SIGNALS
#define BO_V222_MANUAL_SIGNALS
#include "DemoLearning.mqh"
#include "Journal.mqh"
// Separate manual-publication book. Never writes BOPrediction/BORuntimeState.
#define BO_MANUAL_COLUMNS 24
#define BO_MANUAL_SLOTS 64
struct BOManualRecord {
   long id; long lockSequence; int direction; long target; long expiry; int horizon;
   int setup; int regime; long publishedMs; long observedMs; double bid; int result;
   string session; long inputSequence; int alerts; long deadlineMs;
};
struct BOManualSlot { bool used; bool entryKnown; bool exitKnown; BOManualRecord plan; BOManualRecord entry; BOManualRecord exit; };
BOManualSlot boManualSlots[BO_MANUAL_SLOTS];
string boManualRoot="",boManualSession="";
bool boManualError=false;
long boManualTotal=0,boManualWins=0,boManualLosses=0,boManualTies=0,boManualMissing=0,boManualPending=0,boManualWithheld=0;
BOManualRecord boManualLatest; int boManualLatestResult=8;
string boManualHeader[BO_MANUAL_COLUMNS]={"schema","kind","logic","config_hash","feed_hash","policy_hash","signal_id","lock_sequence",
   "direction","target","expiry","horizon","setup","regime","published_ms","observed_ms","bid","result","quote_session",
   "input_sequence","alerts_enabled","receipt","deadline_ms","checksum"};
void BOManualClear(BOManualRecord &r) {
   r.id=0;r.lockSequence=0;r.direction=0;r.target=0;r.expiry=0;r.horizon=0;r.setup=0;r.regime=0;
   r.publishedMs=0;r.observedMs=0;r.bid=0;r.result=8;r.session="";r.inputSequence=0;r.alerts=0;r.deadlineMs=0;
}
void BOManualReset() {
   boManualRoot="";boManualSession="";boManualError=false;
   boManualTotal=0;boManualWins=0;boManualLosses=0;boManualTies=0;boManualMissing=0;boManualPending=0;boManualWithheld=0;
   BOManualClear(boManualLatest);boManualLatestResult=8;
   for(int i=0;i<BO_MANUAL_SLOTS;i++) {
      boManualSlots[i].used=false;boManualSlots[i].entryKnown=false;boManualSlots[i].exitKnown=false;
      BOManualClear(boManualSlots[i].plan);BOManualClear(boManualSlots[i].entry);BOManualClear(boManualSlots[i].exit);
   }
}
string BOManualPath(int kind,long id) { return boManualRoot+"\\manual_v218_"+IntegerToString(kind)+"_"+IntegerToString(id)+".csv"; }
bool BOManualSessionSafe(string value) {
   if(StringLen(value)<1 || StringLen(value)>128)return false;
   for(int i=0;i<StringLen(value);i++) { int c=StringGetCharacter(value,i);if(!((c>=48 && c<=57)||c==95||c==45))return false; }
   return true;
}
string BOManualHashText(const string &cells[]) {
   string value="";for(int i=0;i<BO_MANUAL_COLUMNS-1;i++) { if(i>0)value+="|";value+=cells[i]; }return value;
}
void BOManualCells(int kind,const BOManualRecord &r,string &v[]) {
   ArrayResize(v,BO_MANUAL_COLUMNS);
   v[0]="1";v[1]=IntegerToString(kind);v[2]=IntegerToString(BO_LOGIC_VERSION);v[3]=IntegerToString((long)boDemoConfig);
   v[4]=IntegerToString((long)boDemoFeed);v[5]=IntegerToString((long)boDemoPolicy);v[6]=IntegerToString(r.id);v[7]=IntegerToString(r.lockSequence);
   v[8]=IntegerToString(r.direction);v[9]=IntegerToString(r.target);v[10]=IntegerToString(r.expiry);v[11]=IntegerToString(r.horizon);
   v[12]=IntegerToString(r.setup);v[13]=IntegerToString(r.regime);v[14]=IntegerToString(r.publishedMs);v[15]=IntegerToString(r.observedMs);
   v[16]=DoubleToString(r.bid,10);v[17]=IntegerToString(r.result);v[18]=r.session;v[19]=IntegerToString(r.inputSequence);
   v[20]=IntegerToString(r.alerts);v[21]="UNCONFIRMED";v[22]=IntegerToString(r.deadlineMs);v[23]=IntegerToString((long)BOHashText(BOManualHashText(v)));
}
bool BOManualReadFile(string path,int kind,long id,BOManualRecord &r) {
   int file=FileOpen(path,FILE_READ|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
   if(file==INVALID_HANDLE) { boManualError=true;return false; }
   string h[];string v[];bool ok=BODemoReadCells(file,BO_MANUAL_COLUMNS,h) && BODemoReadCells(file,BO_MANUAL_COLUMNS,v) && FileIsEnding(file);
   if(ok)for(int i=0;i<BO_MANUAL_COLUMNS;i++) {
      if(h[i]!=boManualHeader[i])ok=false;
      if(i!=16 && i!=18 && i!=21 && !BODemoInteger(v[i]))ok=false;
   }
   if(ok)ok=BODemoNumber(v[16]) && BOManualSessionSafe(v[18]) && v[21]=="UNCONFIRMED" &&
      (uint)StringToInteger(v[23])==BOHashText(BOManualHashText(v)) && StringToInteger(v[0])==1 && StringToInteger(v[1])==kind &&
      StringToInteger(v[2])==BO_LOGIC_VERSION && (uint)StringToInteger(v[3])==boDemoConfig &&
      (uint)StringToInteger(v[4])==boDemoFeed && (uint)StringToInteger(v[5])==boDemoPolicy;
   if(ok) {
      BOManualClear(r);r.id=StringToInteger(v[6]);r.lockSequence=StringToInteger(v[7]);r.direction=(int)StringToInteger(v[8]);
      r.target=StringToInteger(v[9]);r.expiry=StringToInteger(v[10]);r.horizon=(int)StringToInteger(v[11]);
      r.setup=(int)StringToInteger(v[12]);r.regime=(int)StringToInteger(v[13]);r.publishedMs=StringToInteger(v[14]);
      r.observedMs=StringToInteger(v[15]);r.bid=StringToDouble(v[16]);r.result=(int)StringToInteger(v[17]);r.session=v[18];
      r.inputSequence=StringToInteger(v[19]);r.alerts=(int)StringToInteger(v[20]);r.deadlineMs=StringToInteger(v[22]);
      ok=r.id>0 && (id==0 || id==r.id) && path==BOManualPath(kind,r.id) && r.lockSequence>0 &&
         (r.direction==1 || r.direction==-1) && r.target==r.id+300 && r.horizon==boDemoHorizon && r.horizon>=1 && r.horizon<=3 &&
         r.expiry==r.target+r.horizon*300 && r.setup>=1 && r.setup<=3 && r.regime>=1 && r.regime<=7 &&
         r.publishedMs>=r.id*1000 && r.publishedMs<=r.deadlineMs && r.deadlineMs<=(r.target-31)*1000 &&
         r.observedMs>=r.publishedMs && r.bid>=0 && r.inputSequence>=0 && (r.alerts==0 || r.alerts==1);
   }
   FileClose(file);if(!ok)boManualError=true;return ok;
}
bool BOManualRead(int kind,long id,BOManualRecord &r) { return BOManualReadFile(BOManualPath(kind,id),kind,id,r); }
bool BOManualSame(const BOManualRecord &a,const BOManualRecord &b) {
   return a.id==b.id && a.lockSequence==b.lockSequence && a.direction==b.direction && a.target==b.target && a.expiry==b.expiry &&
      a.horizon==b.horizon && a.setup==b.setup && a.regime==b.regime && a.publishedMs==b.publishedMs && a.alerts==b.alerts && a.deadlineMs==b.deadlineMs;
}
bool BOManualStore(int kind,const BOManualRecord &r) {
   if(boManualError)return false;
   string name=BOManualPath(kind,r.id);string cells[];BOManualCells(kind,r,cells);
   if(FileIsExist(name)) {
      BOManualRecord old;BOManualClear(old);if(!BOManualRead(kind,r.id,old))return false;
      string prior[];BOManualCells(kind,old,prior);
      if(prior[23]!=cells[23]) { boManualError=true;return false; }return true;
   }
   string temp=name+".tmp";if(FileIsExist(temp)) { boManualError=true;return false; }
   int file=FileOpen(temp,FILE_WRITE|FILE_CSV|FILE_ANSI,',');if(file==INVALID_HANDLE) { boManualError=true;return false; }
   bool ok=FileWrite(file,boManualHeader[0],boManualHeader[1],boManualHeader[2],boManualHeader[3],boManualHeader[4],boManualHeader[5],
      boManualHeader[6],boManualHeader[7],boManualHeader[8],boManualHeader[9],boManualHeader[10],boManualHeader[11],boManualHeader[12],
      boManualHeader[13],boManualHeader[14],boManualHeader[15],boManualHeader[16],boManualHeader[17],boManualHeader[18],boManualHeader[19],
      boManualHeader[20],boManualHeader[21],boManualHeader[22],boManualHeader[23])>0;
   if(ok)ok=FileWrite(file,cells[0],cells[1],cells[2],cells[3],cells[4],cells[5],cells[6],cells[7],cells[8],cells[9],cells[10],cells[11],
      cells[12],cells[13],cells[14],cells[15],cells[16],cells[17],cells[18],cells[19],cells[20],cells[21],cells[22],cells[23])>0;
   FileFlush(file);FileClose(file);if(ok)ok=FileMove(temp,0,name,0);if(!ok)boManualError=true;return ok;
}
bool BOManualBoundaryValid(const BOManualRecord &p,const BOManualRecord &q,int kind) {
   long target=(kind==2 ? p.target : p.expiry)*1000;
   return BOManualSame(p,q) && ((q.result==0 && q.bid>0 && q.observedMs>=target && q.observedMs<=target+2000) ||
      (q.result==9 && q.bid==0 && q.observedMs>target+2000));
}
int BOManualOutcome(const BOManualRecord &entry,const BOManualRecord &exit,int direction) {
   if(entry.result==9 || exit.result==9)return 9;
   double move=(MathRound(exit.bid*10000000000.0)-MathRound(entry.bid*10000000000.0))*direction;return move>0 ? 1 : move<0 ? -1 : 0;
}
void BOManualCountResult(const BOManualRecord &r) {
   if(boManualPending>0)boManualPending--;
   if(r.result==1)boManualWins++;else if(r.result==-1)boManualLosses++;else if(r.result==0)boManualTies++;else boManualMissing++;
   if(r.id==boManualLatest.id)boManualLatestResult=r.result;
}
int BOManualFreeSlot() { for(int i=0;i<BO_MANUAL_SLOTS;i++)if(!boManualSlots[i].used)return i;return -1; }
bool BOManualEnroll(const BOManualRecord &p) {
   boManualTotal++;boManualPending++;
   if(p.publishedMs>boManualLatest.publishedMs) { boManualLatest=p;boManualLatestResult=8; }
   bool hasEntry=FileIsExist(BOManualPath(2,p.id)),hasExit=FileIsExist(BOManualPath(3,p.id));
   BOManualRecord entry,exit;BOManualClear(entry);BOManualClear(exit);
   if(hasEntry && (!BOManualRead(2,p.id,entry) || !BOManualBoundaryValid(p,entry,2))) { boManualError=true;return false; }
   if(hasExit && (!BOManualRead(3,p.id,exit) || !BOManualBoundaryValid(p,exit,3))) { boManualError=true;return false; }
   if(FileIsExist(BOManualPath(4,p.id))) {
      BOManualRecord result;BOManualClear(result);
      if(!hasEntry || !hasExit || !BOManualRead(4,p.id,result) || !BOManualSame(p,result) || result.bid!=0 ||
         result.result!=BOManualOutcome(entry,exit,p.direction) || result.observedMs<MathMax(entry.observedMs,exit.observedMs)) { boManualError=true;return false; }
      BOManualCountResult(result);return true;
   }
   int slot=BOManualFreeSlot();if(slot<0) { boManualError=true;return false; }
   boManualSlots[slot].used=true;boManualSlots[slot].plan=p;boManualSlots[slot].entryKnown=hasEntry;boManualSlots[slot].exitKnown=hasExit;
   boManualSlots[slot].entry=entry;boManualSlots[slot].exit=exit;return true;
}
bool BOManualLockMatches(const BOManualRecord &p) {
   BORuntimeState state;BOEvent e;ZeroMemory(state);ZeroMemory(e);
   if(!BOReadLedger(BOLedgerName(boManualRoot,p.lockSequence),state,e))return false;
   return state.sequence==p.lockSequence && state.configHash==boDemoConfig && state.feedHash==boDemoFeed &&
      e.kind==BO_LOCK_EVENT && (long)e.analysisStart==p.id && (long)e.targetTime==p.target &&
      e.lockedAction==p.direction && e.selectedHorizon==p.horizon && e.setup==p.setup && e.regime==p.regime &&
      e.validation==BO_CONFIRMED && e.reason==BO_OK && !state.current.canceled && e.observedMs<=p.publishedMs;
}
bool BOManualRestore(string root,string session) {
   boManualRoot=root;boManualSession=session;
   string name;long handle=FileFindFirst(root+"\\manual_v218_*.csv.tmp",name);
   if(handle!=INVALID_HANDLE) { FileFindClose(handle);boManualError=true;return false; }
   // A partial or orphan book is never silently treated as an empty cohort.
   handle=FileFindFirst(root+"\\manual_v218_*.csv",name);
   if(handle!=INVALID_HANDLE) {
      int records=0;bool complete=true;
      do {
         int kind=(int)StringToInteger(StringSubstr(name,12,1));BOManualRecord r;BOManualClear(r);
         if(++records>500000 || kind<1 || kind>5 || !BOManualReadFile(root+"\\"+name,kind,0,r) || !FileIsExist(BOManualPath(1,r.id))) { complete=false;break; }
      }while(FileFindNext(handle,name));
      FileFindClose(handle);if(!complete) { boManualError=true;return false; }
   }
   handle=FileFindFirst(root+"\\manual_v218_1_*.csv",name);if(handle==INVALID_HANDLE)return true;
   int count=0;bool ok=true;
   do {
      BOManualRecord p;BOManualClear(p);
      if(++count>100000 || !BOManualReadFile(root+"\\"+name,1,0,p) || p.result!=8 || p.bid<=0 || p.observedMs!=p.publishedMs || !BOManualLockMatches(p)) { ok=false;break; }
      if(FileIsExist(BOManualPath(5,p.id))) {
         BOManualRecord withheld;BOManualClear(withheld);
         if(!BOManualRead(5,p.id,withheld) || !BOManualSame(p,withheld) || withheld.observedMs<=p.deadlineMs || withheld.result!=8 || withheld.bid!=0) { ok=false;break; }
         boManualWithheld++;continue;
      }
      if(!BOManualEnroll(p)) { ok=false;break; }
   }while(FileFindNext(handle,name));
   FileFindClose(handle);if(!ok)boManualError=true;return ok;
}
bool BOManualPublish(const BOPrediction &e,long sequence,const BOConfig &c,bool alerts) {
   if(boManualError || boManualRoot=="" || e.action==0 || e.canceled || !e.locked || e.horizon<1 || e.horizon>3)return false;
   // Never redispatch an existing ID, including after crash/restart.
   if(FileIsExist(BOManualPath(1,(long)e.analysisStart)))return false;
   if(BOManualFreeSlot()<0) { boManualError=true;return false; }
   long now=BONowMs(),deadline=(long)e.targetTime*1000-(c.lockLeadSeconds+c.clockUncertaintySeconds)*1000;
   if(now<=0 || now>deadline)return false;
   BOManualRecord p;BOManualClear(p);p.id=(long)e.analysisStart;p.lockSequence=sequence;p.direction=e.action;
   p.target=(long)e.targetTime;p.expiry=p.target+e.horizon*300;p.horizon=e.horizon;p.setup=e.candidate.setup;p.regime=e.anchor.regime;
   p.publishedMs=now;p.observedMs=now;p.bid=e.latestBid;p.result=8;p.session=boManualSession;p.alerts=alerts ? 1 : 0;p.deadlineMs=deadline;
   if(!BOManualStore(1,p))return false;
   long after=BONowMs();
   if(after>deadline) { BOManualRecord withheld;withheld=p;withheld.observedMs=after;withheld.bid=0;
      if(BOManualStore(5,withheld))boManualWithheld++;return false; }
   return BOManualEnroll(p);
}
void BOManualObserve(long nowMs,bool tick,double bid,double ask,long inputSequence,const BOConfig &c) {
   if(boManualError || boManualRoot=="" || nowMs<=0)return;
   bool quote=tick && MathIsValidNumber(bid) && MathIsValidNumber(ask) && bid>0 && ask>=bid && (ask-bid)/.0001<=c.spreadMaxPips;
   for(int i=0;i<BO_MANUAL_SLOTS;i++) {
      if(!boManualSlots[i].used)continue;
      for(int kind=2;kind<=3;kind++) {
         if((kind==2 && boManualSlots[i].entryKnown) || (kind==3 && boManualSlots[i].exitKnown))continue;
         long target=(kind==2 ? boManualSlots[i].plan.target : boManualSlots[i].plan.expiry)*1000;
         if(nowMs<target || (!quote && nowMs<=target+2000))continue;
         BOManualRecord q;q=boManualSlots[i].plan;q.observedMs=nowMs;q.session=boManualSession;
         q.result=nowMs>target+2000 ? 9 : 0;q.bid=q.result==9 ? 0 : bid;q.inputSequence=q.result==9 ? 0 : inputSequence;
         if(!BOManualStore(kind,q))return;
         if(kind==2) { boManualSlots[i].entry=q;boManualSlots[i].entryKnown=true; }
         else { boManualSlots[i].exit=q;boManualSlots[i].exitKnown=true; }
      }
      if(boManualSlots[i].entryKnown && boManualSlots[i].exitKnown) {
         BOManualRecord result;result=boManualSlots[i].plan;result.observedMs=nowMs;result.bid=0;
         result.result=BOManualOutcome(boManualSlots[i].entry,boManualSlots[i].exit,result.direction);
         if(!BOManualStore(4,result))return;
         BOManualCountResult(result);boManualSlots[i].used=false;
      }
   }
}
bool BOManualOwns(long id) { return boManualLatest.id==id && boManualLatest.id>0; }
string BOManualResultName(int result) { return result==1 ? "WIN" : result==-1 ? "LOSS" : result==0 ? "TIE" : result==9 ? "UNAVAILABLE" : "CHO KET QUA"; }
string BOManualHeadline(long nowMs) {
   if(boManualLatest.id<=0)return "TIN HIEU CHINH THUC: WAIT";
   string d=boManualLatest.direction==1 ? "CALL" : "PUT";
   if(nowMs<boManualLatest.target*1000)return "TIN HIEU DA CHOT: "+d;
   if(nowMs<=boManualLatest.target*1000+2000)return "DEN MOC VAO: "+d;
   return (boManualLatestResult==8 ? "TIN DA PHAT: " : "GAN NHAT: ")+d+" | "+BOManualResultName(boManualLatestResult);
}
string BOManualAlertText(const BOManualRecord &p) {
   return Symbol()+" "+(p.direction==1 ? "CALL" : "PUT")+" | GIU "+IntegerToString(p.horizon*5)+" PHUT ("+IntegerToString(p.horizon)+" M5)\n"+
      "Vao "+TimeToString((datetime)p.target,TIME_SECONDS)+" | Het han "+TimeToString((datetime)p.expiry,TIME_SECONDS)+" | Broker\n"+
      "Cho dung moc vao | ID "+IntegerToString(p.id)+" | MT4 mo phong";
}
#endif
