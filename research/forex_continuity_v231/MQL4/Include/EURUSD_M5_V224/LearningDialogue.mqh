#ifndef BO_V224_LEARNING_DIALOGUE
#define BO_V224_LEARNING_DIALOGUE
#include "Journal.mqh"
#include "DemoLearning.mqh"
#include "Context.mqh"

// Optional local, asynchronous Binary adviser. Native POD/strategy guards stay intact.
const string BO_ADVISOR_CONTRACT="V224_PRELOCK_DIALOGUE_V1";
bool boAdvisorEnabled=false,boAdvisorAffects=false,boAdvisorStorageBad=false;
int boAdvisorInterval=30,boAdvisorMaxAge=30,boAdvisorReserve=5;
long boAdvisorSequence=0,boAdvisorStart=0,boAdvisorRequestMs=0,boAdvisorDeadline=0;
long boAdvisorReceivedMs=0,boAdvisorFinalStart=0;
uint boAdvisorSnapshotChecksum=0,boAdvisorTransportPolicy=0;
int boAdvisorDirection=0,boAdvisorSetup=0,boAdvisorRegime=0,boAdvisorValidation=0;
int boAdvisorDecision=0,boAdvisorProbability=-1;
bool boAdvisorValidated=false,boAdvisorFinalPending=false;
double boAdvisorBid=0;
string boAdvisorModel="NONE",boAdvisorStatus="OFF",boAdvisorFolder="";
int boAdvisorNativeAction=0,boAdvisorFinalAction=0;
long boAdvisorFinalMs=0;

void BOAdvisorReset(bool enabled,bool affects,int interval,int maxAge,int reserve) {
   boAdvisorEnabled=enabled;boAdvisorAffects=affects;boAdvisorInterval=interval;
   boAdvisorMaxAge=maxAge;boAdvisorReserve=reserve;boAdvisorSequence=0;
   boAdvisorStart=0;boAdvisorRequestMs=0;boAdvisorDeadline=0;boAdvisorReceivedMs=0;
   boAdvisorDecision=0;boAdvisorProbability=-1;boAdvisorValidated=false;boAdvisorModel="NONE";
   boAdvisorFinalPending=false;boAdvisorFinalStart=0;boAdvisorStorageBad=false;
   boAdvisorStatus=enabled ? (IsTesting() ? "TESTER_COLLECT_ONLY" : "WAIT_CANDIDATE") : "OFF";
}

string BOAdvisorStem(long sequence) { return StringFormat("%012I64d",sequence); }
string BOAdvisorUserStatus() {
   if(!boAdvisorEnabled)return "Trao doi OFF";
   if(boAdvisorStorageBad)return "Loi giao tiep; EA tu quyet dinh";
   if(IsTesting())return "Tester: thu mau truoc khoa; EA tu quyet dinh";
   if(boAdvisorStatus=="ASKING")return "Dang trao doi; chua chot tin hieu";
   if(boAdvisorStatus=="ADVICE_WAIT")return "Bo hoc de nghi WAIT; cho moc khoa";
   if(boAdvisorStatus=="ADVICE_KEEP")return "Bo hoc dong y huong EA; cho moc khoa";
   if(boAdvisorStatus=="FINAL_WAIT_BY_ADVICE")return "Da chot WAIT theo tu van";
   if(boAdvisorStatus=="FINAL_NATIVE_CONFIRMED")return "Da chot theo EA; bo hoc dong y";
   if(boAdvisorStatus=="SHADOW_EA_DECIDES")return "Chi quan sat; EA tu quyet dinh";
   if(boAdvisorStatus=="WAIT_CANDIDATE")return "Cho ung vien cua EA";
   return "Chua co tu van du dieu kien; EA tu quyet dinh";
}
string BOAdvisorPolicyText() {
   return "PRELOCK1|"+IntegerToString(boAdvisorEnabled ? 1 : 0)+"|"+IntegerToString(boAdvisorAffects ? 1 : 0)+"|"+
      IntegerToString(boAdvisorInterval)+"|"+IntegerToString(boAdvisorMaxAge)+"|"+IntegerToString(boAdvisorReserve);
}
bool BOAdvisorBind(string root,string session) {
   boAdvisorTransportPolicy=BOHashText(BOAdvisorPolicyText());
   if(!boAdvisorEnabled)return true;
   FolderCreate(root+"\\advisory_v224");boAdvisorFolder=root+"\\advisory_v224\\"+session;
   FolderCreate(boAdvisorFolder);
   string path=boAdvisorFolder+"\\policy.csv",temp=path+".tmp";
   int file=FileOpen(temp,FILE_WRITE|FILE_CSV|FILE_ANSI,',');if(file==INVALID_HANDLE)return false;
   bool ok=FileWrite(file,"schema","contract","session","enabled","affects","interval","max_age","reserve","transport_policy_hash")>0;
   if(FileWrite(file,1,BO_ADVISOR_CONTRACT,session,1,boAdvisorAffects ? 1 : 0,boAdvisorInterval,
      boAdvisorMaxAge,boAdvisorReserve,boAdvisorTransportPolicy)==0)ok=false;
   FileFlush(file);FileClose(file);return ok && FileMove(temp,0,path,0);
}

void BOAdvisorRead(string session,const BOConfig &c,long nowMs) {
   if(IsTesting() || boAdvisorSequence<=0 || boAdvisorReceivedMs>0 || nowMs>=boAdvisorDeadline)return;
   string path=boAdvisorFolder+"\\reply_"+BOAdvisorStem(boAdvisorSequence)+".csv";
   if(!FileIsExist(path))return;
   int file=FileOpen(path,FILE_READ|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
   if(file==INVALID_HANDLE)return;
   string names[27]={"schema","contract","session","sequence","config_hash","feed_hash","policy_hash","transport_policy_hash",
      "analysis_start","target","expiry","horizon","direction","setup","regime","requested_ms","deadline_ms","snapshot_checksum",
      "decision","probability_ppm","model_id","trained_cutoff_utc_ms","model_created_utc_ms","response_utc_ms","qualification_cutoff_utc_ms","validated","checksum"};
   string header[];string cells[];bool ok=FileSize(file)<=16384 && BODemoReadCells(file,27,header) && BODemoReadCells(file,27,cells) && FileIsEnding(file);
   FileClose(file);
   if(ok)for(int i=0;i<27;i++)if(header[i]!=names[i] || (i!=1 && i!=2 && i!=20 && !BODemoInteger(cells[i])))ok=false;
   string text="";
   if(ok)for(int j=0;j<26;j++)text+=(j>0 ? "|" : "")+cells[j];
   if(!ok || (uint)StringToInteger(cells[26])!=BOHashText(text)) {boAdvisorStatus="INVALID_REPLY_EA_DECIDES";return;}
   long received=BONowMs();long utcMs=BOContextUTC(received);
   if(received<=0 || received>=boAdvisorDeadline || received>=boAdvisorStart*1000+300000-(c.lockLeadSeconds+c.lockGuardSeconds)*1000 || utcMs<=0) {
      boAdvisorStatus="LATE_OR_CLOCK_UNKNOWN_EA_DECIDES";return;
   }
   long requestUtc=boAdvisorRequestMs-(long)boContextOffset*1000;
   int decision=(int)StringToInteger(cells[18]),probability=(int)StringToInteger(cells[19]);
   long trained=StringToInteger(cells[21]),created=StringToInteger(cells[22]),response=StringToInteger(cells[23]),qualification=StringToInteger(cells[24]);
   int validated=(int)StringToInteger(cells[25]);string model=cells[20];
   bool modelOK=model=="NONE";
   if(StringLen(model)==64) {modelOK=true;for(int k=0;k<64;k++){int ch=StringGetCharacter(model,k);if(!((ch>=48 && ch<=57)||(ch>=97 && ch<=102)))modelOK=false;}}
   if(StringToInteger(cells[0])!=1 || cells[1]!=BO_ADVISOR_CONTRACT || cells[2]!=session || StringToInteger(cells[3])!=boAdvisorSequence ||
      (uint)StringToInteger(cells[4])!=boDemoConfig || (uint)StringToInteger(cells[5])!=boDemoFeed ||
      (uint)StringToInteger(cells[6])!=boDemoPolicy || (uint)StringToInteger(cells[7])!=boAdvisorTransportPolicy ||
      StringToInteger(cells[8])!=boAdvisorStart || StringToInteger(cells[9])!=boAdvisorStart+300 ||
      StringToInteger(cells[10])!=boAdvisorStart+300+boDemoHorizon*300 || StringToInteger(cells[11])!=boDemoHorizon ||
      StringToInteger(cells[12])!=boAdvisorDirection || StringToInteger(cells[13])!=boAdvisorSetup ||
      StringToInteger(cells[14])!=boAdvisorRegime || StringToInteger(cells[15])!=boAdvisorRequestMs ||
      StringToInteger(cells[16])!=boAdvisorDeadline || (uint)StringToInteger(cells[17])!=boAdvisorSnapshotChecksum ||
      decision< -1 || decision>1 || probability< -1 || probability>1000000 || !modelOK ||
      validated<0 || validated>1 || response<=0 || response>utcMs+1000 || utcMs-response>boAdvisorMaxAge*1000 ||
      (decision!=0 && (model=="NONE" || probability<0 || trained<=0 || created<=0 || trained>=requestUtc || created>=requestUtc)) ||
      (validated==1 && (decision==0 || qualification<=0 || qualification>=requestUtc))) {
      boAdvisorStatus="MISMATCH_REPLY_EA_DECIDES";return;
   }
   boAdvisorReceivedMs=received;boAdvisorDecision=decision;boAdvisorProbability=probability;
   boAdvisorValidated=validated==1;boAdvisorModel=model;
   boAdvisorStatus=decision==0 ? "ABSTAIN_EA_DECIDES" : decision<0 ? "ADVICE_WAIT" : "ADVICE_KEEP";
}

bool BOAdvisorRequest(string session,const BORuntimeState &state,const BOConfig &c,long nowMs) {
   BORuntimeState snapshot=state;snapshot.sequence=boAdvisorSequence+1;
   BOEvent event;BOMakeEvent(state.current,BO_VALIDATION_EVENT,nowMs,event);
   if(!BOCommit(boAdvisorFolder,snapshot,event))return false;
   string binary=BOLedgerName(boAdvisorFolder,snapshot.sequence);
   int handle=FileOpen(binary,FILE_READ|FILE_BIN);if(handle==INVALID_HANDLE)return false;
   uint hash=BOChecksum(handle,(long)FileSize(handle)-4);FileClose(handle);
   long deadline=(long)MathMin(BOLockDue(state.current,c)-boAdvisorReserve*1000,nowMs+boAdvisorMaxAge*1000);
   string fields="1|"+BO_ADVISOR_CONTRACT+"|"+session+"|"+IntegerToString(snapshot.sequence)+"|"+
      IntegerToString(state.configHash)+"|"+IntegerToString(state.feedHash)+"|"+IntegerToString(boDemoPolicy)+"|"+
      IntegerToString(boAdvisorTransportPolicy)+"|"+IntegerToString((long)state.current.analysisStart)+"|"+
      IntegerToString((long)state.current.targetTime)+"|"+IntegerToString((long)state.current.targetTime+boDemoHorizon*300)+"|"+
      IntegerToString(boDemoHorizon)+"|"+IntegerToString(state.current.candidate.direction)+"|"+
      IntegerToString(state.current.candidate.setup)+"|"+IntegerToString(state.current.anchor.regime)+"|"+
      IntegerToString(state.current.validation)+"|"+IntegerToString(nowMs)+"|"+IntegerToString(deadline)+"|"+IntegerToString(hash);
   string path=boAdvisorFolder+"\\request_"+BOAdvisorStem(snapshot.sequence)+".csv",temp=path+".tmp";
   int file=FileOpen(temp,FILE_WRITE|FILE_CSV|FILE_ANSI,',');if(file==INVALID_HANDLE)return false;
   bool ok=FileWrite(file,"schema","contract","session","sequence","config_hash","feed_hash","policy_hash","transport_policy_hash",
      "analysis_start","target","expiry","horizon","direction","setup","regime","validation","observed_ms","deadline_ms","snapshot_checksum","checksum")>0;
   if(FileWrite(file,1,BO_ADVISOR_CONTRACT,session,snapshot.sequence,state.configHash,state.feedHash,boDemoPolicy,boAdvisorTransportPolicy,
      (long)state.current.analysisStart,(long)state.current.targetTime,(long)state.current.targetTime+boDemoHorizon*300,
      boDemoHorizon,state.current.candidate.direction,state.current.candidate.setup,state.current.anchor.regime,state.current.validation,
      nowMs,deadline,hash,BOHashText(fields))==0)ok=false;
   FileFlush(file);FileClose(file);
   if(!ok || !FileMove(temp,0,path,0))return false;
   boAdvisorSequence=snapshot.sequence;boAdvisorStart=(long)state.current.analysisStart;
   boAdvisorRequestMs=nowMs;boAdvisorDeadline=deadline;boAdvisorSnapshotChecksum=hash;
   boAdvisorDirection=state.current.candidate.direction;boAdvisorSetup=state.current.candidate.setup;
   boAdvisorRegime=state.current.anchor.regime;boAdvisorValidation=state.current.validation;boAdvisorBid=state.current.latestBid;
   boAdvisorReceivedMs=0;boAdvisorDecision=0;boAdvisorProbability=-1;boAdvisorModel="NONE";boAdvisorValidated=false;
   boAdvisorStatus=IsTesting() ? "TESTER_COLLECT_ONLY" : "ASKING";return true;
}

// Pure cached decision: never wait for Python or perform file IO at the lock.
void BOAdvisorFinalize(BOPrediction &e,const BOConfig &c,long nowMs) {
   if(!boAdvisorEnabled)return;
   boAdvisorNativeAction=e.action;boAdvisorFinalAction=e.action;boAdvisorFinalStart=(long)e.analysisStart;boAdvisorFinalMs=nowMs;
   boAdvisorFinalPending=true;
   if(IsTesting()){boAdvisorStatus="TESTER_EA_DECIDES";return;}
   if(boAdvisorStorageBad){boAdvisorStatus="BRIDGE_IO_ERROR_EA_DECIDES";return;}
   if(!boAdvisorAffects){boAdvisorStatus="SHADOW_EA_DECIDES";return;}
   if(e.action==0 || e.canceled || e.validation!=BO_CONFIRMED || e.reason!=BO_OK) {boAdvisorStatus="NATIVE_GUARD_EA_DECIDES";return;}
   if(boAdvisorStart!=(long)e.analysisStart || boAdvisorReceivedMs<=0 || boAdvisorReceivedMs>=boAdvisorDeadline ||
      boAdvisorReceivedMs>=BOLockDue(e,c) || nowMs<boAdvisorRequestMs || nowMs-boAdvisorRequestMs>boAdvisorMaxAge*1000 ||
      boAdvisorDirection!=e.candidate.direction || boAdvisorSetup!=e.candidate.setup || boAdvisorRegime!=e.anchor.regime ||
      boAdvisorValidation!=e.validation || e.anchor.volatility.atr<=0 || MathAbs(e.latestBid-boAdvisorBid)>.25*e.anchor.volatility.atr) {
      boAdvisorStatus="MISSING_LATE_OR_CHANGED_EA_DECIDES";return;
   }
   if(!boAdvisorValidated || boAdvisorDecision==0){boAdvisorStatus="UNQUALIFIED_EA_DECIDES";return;}
   if(boAdvisorDecision<0) {e.action=0;e.lockedAction=0;boAdvisorFinalAction=0;boAdvisorStatus="FINAL_WAIT_BY_ADVICE";}
   else boAdvisorStatus="FINAL_NATIVE_CONFIRMED";
}

void BOAdvisorWriteFinal() {
   if(!boAdvisorFinalPending)return;
   string path=boAdvisorFolder+"\\final_"+IntegerToString(boAdvisorFinalStart)+".csv";
   if(FileIsExist(path)){boAdvisorFinalPending=false;return;}
   string temp=path+".tmp";int file=FileOpen(temp,FILE_WRITE|FILE_CSV|FILE_ANSI,',');if(file==INVALID_HANDLE)return;
   string text="1|"+IntegerToString(boAdvisorFinalStart)+"|"+IntegerToString(boAdvisorFinalMs)+"|"+IntegerToString(boAdvisorSequence)+"|"+
      IntegerToString(boAdvisorRequestMs)+"|"+IntegerToString(boAdvisorReceivedMs)+"|"+IntegerToString(boAdvisorNativeAction)+"|"+
      IntegerToString(boAdvisorFinalAction)+"|"+boAdvisorStatus+"|"+boAdvisorModel;
   bool ok=FileWrite(file,"schema","analysis_start","final_ms","request_sequence","request_ms","received_ms","native_action","final_action","status","model_id","checksum")>0;
   if(FileWrite(file,1,boAdvisorFinalStart,boAdvisorFinalMs,boAdvisorSequence,boAdvisorRequestMs,boAdvisorReceivedMs,
      boAdvisorNativeAction,boAdvisorFinalAction,boAdvisorStatus,boAdvisorModel,BOHashText(text))==0)ok=false;
   FileFlush(file);FileClose(file);if(ok && FileMove(temp,0,path,0))boAdvisorFinalPending=false;
}

void BOAdvisorPump(string session,const BORuntimeState &state,const BOConfig &c,long nowMs) {
   if(!boAdvisorEnabled || boAdvisorStorageBad)return;
   // Persist after publication, without changing any native fact or published signal.
   BOAdvisorWriteFinal();
   if(boAdvisorFinalPending)return;
   if(!state.current.exists || state.current.locked || state.current.entered || state.current.canceled || state.paused)return;
   long due=BOLockDue(state.current,c);
   if(nowMs<=(long)state.current.analysisStart*1000+15000 || nowMs>=due-boAdvisorReserve*1000)return;
   if(state.current.candidate.direction==0 || state.current.lastQuoteMs<=0 || nowMs-state.current.lastQuoteMs>c.quoteFreshSeconds*1000)return;
   BOAdvisorRead(session,c,nowMs);
   if(boAdvisorStart==(long)state.current.analysisStart && nowMs-boAdvisorRequestMs<boAdvisorInterval*1000)return;
   if(!BOAdvisorRequest(session,state,c,nowMs)) {boAdvisorStorageBad=true;boAdvisorStatus="BRIDGE_IO_ERROR_EA_DECIDES";}
}
#endif
