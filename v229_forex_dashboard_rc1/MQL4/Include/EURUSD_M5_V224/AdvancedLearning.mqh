#ifndef BO_V222_ADVANCED_LEARNING
#define BO_V222_ADVANCED_LEARNING
#include "DemoLearning.mqh"

#define BO_ADV_FEATURES 21
double boAdvMean[21],boAdvScale[21],boAdvWeight[21],boAdvLow[21],boAdvHigh[21];
double boAdvIntercept=0,boAdvThreshold=0;
long boAdvId=0,boAdvAsOf=0,boAdvExpires=0;
bool boAdvBad=false,boAdvSeen=false,boAdvActive=false,boAdvReadTried=false;
uint boAdvReadMono=0;
string boAdvStatus="COLLECTING";

void BOAdvancedReset() {
   boAdvId=0; boAdvAsOf=0; boAdvExpires=0;
   boAdvBad=false; boAdvSeen=false; boAdvActive=false; boAdvReadTried=false; boAdvReadMono=0;
   boAdvStatus="COLLECTING";
}
bool BOAdvancedFeatures(const BOPrediction &e,double &x[]) {
   if(e.lockedDirection!=1 && e.lockedDirection!=-1) return false;
   BOAnchor a=e.anchor; BOCandidate c=e.candidate;
   double atr=a.volatility.atr,d=e.lockedDirection,width=MathMax(a.candle.range,.00001),bid=e.latestBid;
   if(!a.available || !MathIsValidNumber(atr) || atr<=0) return false;
   ArrayResize(x,21);
   x[0]=atr*10000; x[1]=a.candle.range/atr; x[2]=a.candle.body/width;
   x[3]=d*(a.candle.lowerWick-a.candle.upperWick)/width; x[4]=d*(a.candle.closeLocation-.5)*2;
   x[5]=d*a.momentum.netATR; x[6]=a.momentum.efficiency; x[7]=d*a.momentum.acceleration;
   x[8]=a.volatility.expansion; x[9]=d*(a.fastEMA-a.slowEMA)/atr; x[10]=d*a.baselineFastSlope/atr;
   x[11]=d*(c.extension-bid)/atr; x[12]=d*(bid-c.confirmation)/atr;
   x[13]=(d==1 ? a.triggerClose-e.lowestBid : e.highestBid-a.triggerClose)/atr;
   x[14]=(d==1 ? e.highestBid-a.triggerClose : a.triggerClose-e.lowestBid)/atr;
   x[15]=c.setup==1 ? 1 : 0; x[16]=c.setup==2 ? 1 : 0; x[17]=c.setup==3 ? 1 : 0;
   x[18]=d; x[19]=d*a.pullbackNetATR; x[20]=d*(bid-c.invalidation)/atr;
   for(int i=0;i<21;i++) if(!MathIsValidNumber(x[i]) || MathAbs(x[i])>=1e6) return false;
   return true;
}
bool BOAdvancedLoad(string root,long now) {
   string path=root+"\\advanced_model_v207.csv";
   if(!FileIsExist(path)) {
      boAdvId=0; boAdvBad=boAdvSeen || FileIsExist(root+"\\advanced_seen.csv");
      boAdvStatus=boAdvBad ? "MODEL_MISSING" : "COLLECTING"; return !boAdvBad;
   }
   boAdvBad=true; boAdvStatus="INVALID_MODEL";
   int file=FileOpen(path,FILE_READ|FILE_CSV|FILE_ANSI,','); if(file==INVALID_HANDLE) return false;
   string expected[20]={"schema","source","logic","config_hash","feed_hash","policy_hash","asof","expires",
      "model_id","feature_version","active","threshold","intercept","index","mean","scale","weight","low","high","count"};
   string cells[]; string meta[];
   bool ok=BODemoReadCells(file,20,cells);
   if(ok) for(int j=0;j<20;j++) if(cells[j]!=expected[j]) ok=false;
   // Explicit initialization satisfies MetaEditor's definite-assignment analysis.
   // Every coefficient row must still pass validation before these arrays load.
   double means[21]={0.0};
   double scales[21]={0.0};
   double weights[21]={0.0};
   double lows[21]={0.0};
   double highs[21]={0.0};
   int count=-1;
   while(ok && !FileIsEnding(file)) {
      if(!BODemoReadCells(file,20,cells)) { ok=false; break; }
      for(int j=0;j<20;j++) {
         if(j==1) continue;
         bool floating=j==11 || j==12 || (j>=14 && j<=18);
         if((floating && !BODemoNumber(cells[j])) || (!floating && !BODemoInteger(cells[j]))) ok=false;
      }
      if(!ok) break;
      if(count==-1) {
         ArrayResize(meta,20); for(int j=0;j<20;j++) meta[j]=cells[j];
         long asof=StringToInteger(meta[6]),expiry=StringToInteger(meta[7]),id=StringToInteger(meta[8]);
         double threshold=StringToDouble(meta[11]),intercept=StringToDouble(meta[12]);
         int active=(int)StringToInteger(meta[10]);
         if(StringToInteger(meta[0])!=1 || meta[1]!="MT4_SIMULATED" || StringToInteger(meta[2])!=BO_LOGIC_VERSION ||
            (uint)StringToInteger(meta[3])!=boDemoConfig || (uint)StringToInteger(meta[4])!=boDemoFeed ||
            (uint)StringToInteger(meta[5])!=boDemoPolicy || StringToInteger(meta[9])!=1 || (active!=0 && active!=1) ||
            asof<=0 || asof>now || expiry<=now || expiry<=asof || expiry-asof>86400 ||
            (boAdvSeen && asof<boAdvAsOf) || id<=0 || id>asof*1000+999 ||
            threshold<.55 || threshold>.8 || MathAbs(intercept)>1000 ||
            StringToInteger(meta[13])!=-1 || StringToInteger(meta[19])!=21) ok=false;
         count=0; continue;
      }
      if(count>=21 || StringToInteger(cells[13])!=count) { ok=false; break; }
      for(int j=0;j<=12;j++) if(cells[j]!=meta[j]) ok=false;
      if(cells[19]!=meta[19]) ok=false;
      if(!ok) break;
      means[count]=StringToDouble(cells[14]); scales[count]=StringToDouble(cells[15]); weights[count]=StringToDouble(cells[16]);
      lows[count]=StringToDouble(cells[17]); highs[count]=StringToDouble(cells[18]);
      if(scales[count]<1e-12 || scales[count]>1e6 || MathAbs(means[count])>=1e6 || MathAbs(weights[count])>=1e6 ||
         MathAbs(lows[count])>=1e6 || MathAbs(highs[count])>=1e6 || lows[count]>highs[count]) ok=false;
      count++;
   }
   FileClose(file);
   if(!ok || count!=21) { boAdvId=0; return false; }
   if(!FileIsExist(root+"\\advanced_seen.csv")) {
      int marker=FileOpen(root+"\\advanced_seen.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
      if(marker==INVALID_HANDLE) return false;
      bool stored=FileWrite(marker,1,boDemoPolicy,StringToInteger(meta[8]))>0; FileFlush(marker); FileClose(marker);
      if(!stored) return false;
   }
   for(int j=0;j<21;j++) { boAdvMean[j]=means[j]; boAdvScale[j]=scales[j]; boAdvWeight[j]=weights[j]; boAdvLow[j]=lows[j]; boAdvHigh[j]=highs[j]; }
   boAdvId=StringToInteger(meta[8]); boAdvAsOf=StringToInteger(meta[6]); boAdvExpires=StringToInteger(meta[7]);
   boAdvIntercept=StringToDouble(meta[12]); boAdvThreshold=StringToDouble(meta[11]); boAdvActive=StringToInteger(meta[10])==1;
   boAdvBad=false; boAdvSeen=true; boAdvStatus=boAdvActive ? "ACTIVE_FILTER" : "OBSERVE_ONLY"; return true;
}
void BOAdvancedRefresh(string root,long now) {
   if(now<=0) return;
   uint mono=GetTickCount(); if(boAdvReadTried && (uint)(mono-boAdvReadMono)<15000) return;
   boAdvReadTried=true; boAdvReadMono=mono; BOAdvancedLoad(root,now);
}
void BOAdvancedApply(BOPrediction &e,long nowMs,bool useLearning) {
   if(!useLearning || !e.locked || e.canceled || e.validation!=BO_CONFIRMED || e.lockedDirection==0) return;
   if(boAdvBad || (boAdvSeen && nowMs/1000>=boAdvExpires)) {
      e.action=0; e.lockedAction=0; e.horizon=0; e.reason=BO_MODEL_UNAVAILABLE; return;
   }
   if(boAdvId<=0) return;
   double x[]; if(!BOAdvancedFeatures(e,x)) return;
   double logit=boAdvIntercept;
   for(int i=0;i<21;i++) {
      double margin=MathMax(.25*(boAdvHigh[i]-boAdvLow[i]),.25*boAdvScale[i]);
      // Outside training support: no ML forecast/filter; base rules still apply.
      if(x[i]<boAdvLow[i]-margin || x[i]>boAdvHigh[i]+margin) return;
      logit+=boAdvWeight[i]*MathMax(-6,MathMin(6,(x[i]-boAdvMean[i])/boAdvScale[i]));
   }
   double p=1/(1+MathExp(-MathMax(-35,MathMin(35,logit))));
   e.modelId=boAdvId;
   if(boDemoHorizon==1) e.p1=p; if(boDemoHorizon==2) e.p2=p; if(boDemoHorizon==3) e.p3=p;
   if(boAdvActive && p<boAdvThreshold && e.action!=0) {
      e.action=0; e.lockedAction=0; e.horizon=0; e.reason=BO_NO_EDGE;
   }
}
#endif
