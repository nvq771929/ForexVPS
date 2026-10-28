#ifndef BO_V225_EMBEDDED_CONTEXT
#define BO_V225_EMBEDDED_CONTEXT
// Frozen RC1 numerical port. No MT4 history, file, clock, order or adviser API.
// Times are verified UTC seconds. This observer never supplies a trade decision.
const int EC_UNKNOWN=0,EC_UP=1,EC_DOWN=2,EC_RANGE=3,EC_UNCERTAIN=4;
const int EC_COLLECTING=0,EC_UNCONFIRMED=1,EC_FORMING=2,EC_CONTINUING=3,
          EC_EXTENDED=4,EC_WEAKENING=5,EC_BOUNDED_RANGE=6;
struct ECBar { long time; double open,high,low,close; long ticks; };
struct ECFrame {
   ECBar bars[200]; double tr[200],emas[10];
   int size,trSize,emaSize,count,seconds,warm;
   double ema20,ema50,seed20,seed50;
};
struct ECFacts {
   bool valid; long closeMs; int age,count,vote;
   double atr,previousATR,ema20,ema50,gap,slope,precedingSlope,efficiency,net6,range12,close;
};
struct ECAggregate { ECBar bars[12]; long bucket; int size,seconds; };
struct ECZone { bool valid; double low,high; int touches,age; long knownAtMs; };
struct ECZones { bool known; ECZone support,resistance; };
struct ECSnapshot {
   long asofMs,startedMs; double ageMinutes,volatilityRatio,m5ATR;
   int direction,candidate,volatility,phase,flags,pending,pendingCount,unsupported;
   bool ready,gap; ECFacts m15,h1,m5; ECZones zones;
};
struct ECState {
   ECFrame m5,m15,h1; ECAggregate a15,a60; long last,started;
   int direction,pending,pendingCount,unsupported; ECSnapshot snapshot;
};
void ECClearDirection(ECState &s) {
   s.direction=EC_UNKNOWN;s.started=0;s.pending=0;s.pendingCount=0;s.unsupported=0;
}
void ECReset(ECState &s) {
   ZeroMemory(s);s.m5.seconds=300;s.m5.warm=64;
   s.m15.seconds=900;s.m15.warm=150;s.h1.seconds=3600;s.h1.warm=150;
   s.a15.seconds=900;s.a60.seconds=3600;
}
bool ECValidBar(const ECBar &b) {
   return b.time>0 && b.time%300==0 && b.ticks>=0 &&
      MathIsValidNumber(b.open) && MathIsValidNumber(b.high) &&
      MathIsValidNumber(b.low) && MathIsValidNumber(b.close) &&
      b.low>0 && b.low<=MathMin(b.open,b.close) && b.high>=MathMax(b.open,b.close);
}
void ECFramePush(ECFrame &f,const ECBar &b) {
   if(f.size>0) {
      double prev=f.bars[f.size-1].close;
      if(f.trSize==200) { for(int i=1;i<200;i++)f.tr[i-1]=f.tr[i];f.trSize--; }
      f.tr[f.trSize++]=MathMax(b.high-b.low,MathMax(MathAbs(b.high-prev),MathAbs(b.low-prev)));
   }
   if(f.size==200) { for(int i=1;i<200;i++)f.bars[i-1]=f.bars[i];f.size--; }
   f.bars[f.size++]=b;f.count++;
   if(f.count<=20) { f.seed20+=b.close;if(f.count==20)f.ema20=f.seed20/20; }
   else f.ema20=(2.0/21)*b.close+(1-2.0/21)*f.ema20;
   if(f.count<=50) { f.seed50+=b.close;if(f.count==50)f.ema50=f.seed50/50; }
   else f.ema50=(2.0/51)*b.close+(1-2.0/51)*f.ema50;
   if(f.count>=20) {
      if(f.emaSize==10) {for(int i=1;i<10;i++)f.emas[i-1]=f.emas[i];f.emaSize--;}
      f.emas[f.emaSize++]=f.ema20;
   }
}
bool ECAggregatePush(ECAggregate &a,const ECBar &b,ECBar &closed) {
   long bucket=(b.time/a.seconds)*a.seconds;
   if(bucket!=a.bucket) {a.bucket=bucket;a.size=0;}
   if(a.size>=12)a.size=0;
   a.bars[a.size++]=b;
   if(b.time+300!=bucket+a.seconds)return false;
   int size=a.size;a.size=0;
   if(size!=a.seconds/300)return false;
   for(int i=0;i<size;i++)if(a.bars[i].time!=bucket+i*300)return false;
   closed=a.bars[0];closed.close=b.close;
   for(int i=1;i<size;i++) {
      closed.high=MathMax(closed.high,a.bars[i].high);
      closed.low=MathMin(closed.low,a.bars[i].low);closed.ticks+=a.bars[i].ticks;
   }
   return true;
}
void ECGetFacts(const ECFrame &f,long now,ECFacts &v) {
   ZeroMemory(v);if(f.size==0)return;
   long end=f.bars[f.size-1].time+f.seconds,age=now-end;
   if(f.count<f.warm || age<0 || age>=f.seconds || f.trSize<28 || f.emaSize<7)return;
   double atr=0,prior=0;
   for(int i=f.trSize-14;i<f.trSize;i++)atr+=f.tr[i];
   for(int i=f.trSize-28;i<f.trSize-14;i++)prior+=f.tr[i];
   atr/=14;prior/=14;if(atr<=0)return;
   int n=f.size,e=f.emaSize;double net=f.bars[n-1].close-f.bars[n-13].close,travel=0;
   double hi=f.bars[n-1].high,lo=f.bars[n-1].low;
   for(int i=n-12;i<n;i++) {
      travel+=MathAbs(f.bars[i].close-f.bars[i-1].close);
      hi=MathMax(hi,f.bars[i].high);lo=MathMin(lo,f.bars[i].low);
   }
   double slope=f.emas[e-1]-f.emas[e-4],prev=f.emas[e-4]-f.emas[e-7];
   v.valid=true;v.closeMs=end*1000;v.age=(int)age;v.count=f.count;v.atr=atr;v.previousATR=prior;
   v.ema20=f.ema20;v.ema50=f.ema50;v.gap=(f.ema20-f.ema50)/atr;
   v.slope=slope/atr;v.precedingSlope=prev/atr;v.efficiency=travel>0 ? MathAbs(net)/travel : 0;
   v.net6=(f.bars[n-1].close-f.bars[n-7].close)/atr;v.range12=(hi-lo)/atr;v.close=f.bars[n-1].close;
   v.vote=v.gap>.10 && slope>0 ? 1 : (v.gap<-.10 && slope<0 ? -1 : 0);
}
void ECGetZones(const ECFrame &f,ECZones &out) {
   ZeroMemory(out);if(f.size<64 || f.trSize<15)return;
   double atr=0;for(int i=f.trSize-15;i<f.trSize-1;i++)atr+=f.tr[i];atr/=14;
   if(atr<=0)return;
   int start=f.size-64;
   for(int i=start+1;i<f.size;i++)if(f.bars[i].time-f.bars[i-1].time!=300)return;
   out.known=true;double price=f.bars[f.size-1].close;
   for(int side=0;side<2;side++) {
      int indices[64]={0};double prices[64]={0.0};int total=0;
      for(int i=2;i<=60;i++) {
         int p=start+i;double val=side==0 ? f.bars[p].low : f.bars[p].high;bool valid=true;
         for(int k=1;k<=2;k++) {
            if(side==0 && !(val<f.bars[p-k].low && val<=f.bars[p+k].low))valid=false;
            if(side==1 && !(val>f.bars[p-k].high && val>=f.bars[p+k].high))valid=false;
         }
         if(valid) {indices[total]=i;prices[total++]=val;}
      }
      for(int seed=0;seed<total;seed++) {
         if(62-indices[seed]>48)continue;
         int touches=0,newest=0;double lo=prices[seed],hi=lo;
         for(int i=0;i<total;i++)if(62-indices[i]<=48 && MathAbs(prices[i]-prices[seed])<=.25*atr) {
            lo=MathMin(lo,prices[i]);hi=MathMax(hi,prices[i]);touches++;newest=(int)MathMax(newest,indices[i]);
         }
         if(touches<2 || hi-lo>.5*atr)continue;
         double pad=MathMax(0,.10*atr-(hi-lo))/2;lo-=pad;hi+=pad;
         ECZone z;ZeroMemory(z);z.valid=true;z.low=lo;z.high=hi;z.touches=touches;z.age=62-newest;
         z.knownAtMs=(f.bars[start+newest+2].time+300)*1000;
         if(side==0 && hi<price && (!out.support.valid || hi>out.support.high))out.support=z;
         if(side==1 && lo>price && (!out.resistance.valid || lo<out.resistance.low))out.resistance=z;
      }
   }
}
int ECCandidate(const ECFacts &m,const ECFacts &h,const ECZones &z) {
   if(m.vote==h.vote && m.vote!=0)return m.vote>0 ? EC_UP : EC_DOWN;
   bool two=z.known && z.support.valid && z.resistance.valid && z.support.high<z.resistance.low;
   if(h.vote==0 && MathAbs(m.gap)<=.25 && m.efficiency<.35 && m.range12<=4 && two)return EC_RANGE;
   return EC_UNCERTAIN;
}
void ECConfirm(ECState &s,int candidate,long asofMs) {
   bool stable=candidate==EC_UP || candidate==EC_DOWN || candidate==EC_RANGE;
   if(candidate==s.direction && stable) {s.pending=0;s.pendingCount=0;s.unsupported=0;return;}
   if(stable) {s.pendingCount=s.pending==candidate ? s.pendingCount+1 : 1;s.pending=candidate;}
   else {s.pending=0;s.pendingCount=0;}
   if(s.pendingCount>=2) {
      s.direction=candidate;s.started=(candidate==EC_UP || candidate==EC_DOWN) ? asofMs : 0;
      s.unsupported=0;s.pending=0;s.pendingCount=0;return;
   }
   if(s.direction==EC_UP || s.direction==EC_DOWN) {
      s.unsupported++;if(s.unsupported>=2) {s.direction=EC_UNCERTAIN;s.started=0;}
   } else {s.direction=EC_UNCERTAIN;s.started=0;}
}
bool ECUpdate(ECState &s,const ECBar &b) {
   if(!ECValidBar(b) || (s.last>0 && b.time<=s.last))return false;
   ECSnapshot v;ZeroMemory(v);v.ageMinutes=-1;v.volatilityRatio=-1;
   v.gap=s.last>0 && b.time-s.last!=300;if(v.gap)ECClearDirection(s);
   s.last=b.time;ECFramePush(s.m5,b);ECBar closed15,closed60;
   bool has15=ECAggregatePush(s.a15,b,closed15),has60=ECAggregatePush(s.a60,b,closed60);
   if(has15)ECFramePush(s.m15,closed15);if(has60)ECFramePush(s.h1,closed60);
   long now=b.time+300;v.asofMs=now*1000;
   ECGetFacts(s.m5,now,v.m5);ECGetFacts(s.m15,now,v.m15);ECGetFacts(s.h1,now,v.h1);
   v.ready=v.m5.valid && v.m15.valid && v.h1.valid;ECGetZones(s.m5,v.zones);
   if(!v.ready)ECClearDirection(s);
   v.candidate=v.ready ? ECCandidate(v.m15,v.h1,v.zones) : EC_UNKNOWN;
   if(v.ready && has15)ECConfirm(s,v.candidate,v.asofMs);
   if(v.ready && s.direction==EC_RANGE && v.candidate!=EC_RANGE) {s.direction=EC_UNCERTAIN;s.started=0;}
   if(s.started>0)v.ageMinutes=(v.asofMs-s.started)/60000.0;
   if(v.m5.valid && v.m5.previousATR>0)v.volatilityRatio=v.m5.atr/v.m5.previousATR;
   v.volatility=v.volatilityRatio<0 ? 0 : (v.volatilityRatio<.75 ? 1 : (v.volatilityRatio>1.25 ? 3 : 2));
   v.phase=v.ready ? EC_UNCONFIRMED : EC_COLLECTING;
   int d=s.direction==EC_UP ? 1 : (s.direction==EC_DOWN ? -1 : 0);
   if(d!=0) {
      if(v.m15.vote!=d || v.h1.vote!=d || s.unsupported>0)v.flags|=1;
      if(d*v.m15.net6<=0)v.flags|=2;
      if(d*v.m15.precedingSlope>0 && d*v.m15.slope<.5*d*v.m15.precedingSlope)v.flags|=4;
      ECZone opposite;if(d>0)opposite=v.zones.resistance;else opposite=v.zones.support;
      double edge=d>0 ? opposite.low : opposite.high;
      double room=d*(edge-b.close)/v.m5.atr;
      if(opposite.valid && room>=0 && room<=.5)v.flags|=8;
      bool extended=d*(v.m15.close-v.m15.ema20)/v.m15.atr>1.5;
      v.phase=v.flags!=0 ? EC_WEAKENING : (extended ? EC_EXTENDED : (v.ageMinutes<30 ? EC_FORMING : EC_CONTINUING));
   } else if(s.direction==EC_RANGE)v.phase=EC_BOUNDED_RANGE;
   v.direction=s.direction;v.startedMs=s.started;v.pending=s.pending;
   v.pendingCount=s.pendingCount;v.unsupported=s.unsupported;v.m5ATR=v.m5.valid ? v.m5.atr : 0;
   s.snapshot=v;return true;
}
string ECDirectionName(int value) {
   if(value==EC_UP)return "UP";if(value==EC_DOWN)return "DOWN";
   if(value==EC_RANGE)return "RANGE";if(value==EC_UNCERTAIN)return "UNCERTAIN";return "UNKNOWN";
}
string ECPhaseName(int value) {
   if(value==EC_FORMING)return "FORMING";if(value==EC_CONTINUING)return "CONTINUING";
   if(value==EC_EXTENDED)return "EXTENDED";if(value==EC_WEAKENING)return "WEAKENING";
   if(value==EC_BOUNDED_RANGE)return "BOUNDED_RANGE";if(value==EC_UNCONFIRMED)return "UNCONFIRMED";return "COLLECTING";
}
#endif
