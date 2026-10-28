#ifndef BO_V222_STRUCTURE
#define BO_V222_STRUCTURE
#include "Types.mqh"
void BOEmptyZone(BOZone &z) { z.available=false; z.low=0; z.high=0; z.touches=0; z.age=0; z.knownAt=0; }
void BOFindStructure(const BOBar &b[], const BOConfig &c, double atr, BOStructure &s) {
   BOPivot lows[BO_MAX_PIVOTS], highs[BO_MAX_PIVOTS];
   ZeroMemory(lows); ZeroMemory(highs);
   int nl=0,nh=0;
   int end=BO_HISTORY-2;
   for(int i=c.swingRadius;i<=end-c.swingRadius;i++) {
      bool low=true,high=true;
      for(int k=1;k<=c.swingRadius;k++) {
         // Strict to the left, non-strict to the right: earliest pivot owns a flat extreme.
         if(b[i].low>=b[i-k].low || b[i].low>b[i+k].low) low=false;
         if(b[i].high<=b[i-k].high || b[i].high<b[i+k].high) high=false;
      }
      if(low) { lows[nl].price=b[i].low; lows[nl].index=i; lows[nl].kind=-1; nl++; }
      if(high) { highs[nh].price=b[i].high; highs[nh].index=i; highs[nh].kind=1; nh++; }
   }
   s.lowCount=nl; s.highCount=nh; s.trend=(nl>=2 && nh>=2) ? 0 : 2; // UNKNOWN is distinct from neutral.
   if(nl>=2 && nh>=2) {
      if(lows[nl-1].price>lows[nl-2].price && highs[nh-1].price>highs[nh-2].price) s.trend=1;
      else if(lows[nl-1].price<lows[nl-2].price && highs[nh-1].price<highs[nh-2].price) s.trend=-1;
   }
   BOEmptyZone(s.support); BOEmptyZone(s.resistance); BOEmptyZone(s.preSupport); BOEmptyZone(s.preResistance);
   double reference=b[BO_HISTORY-1].close;
   if(atr<=0) return;
   for(int side=0;side<2;side++) {
      int count=side==0 ? nl : nh;
      for(int seed=0;seed<count;seed++) {
         int seedIndex=side==0 ? lows[seed].index : highs[seed].index;
         if(end-seedIndex>c.maximumZoneAge) continue;
         double seedPrice=side==0 ? lows[seed].price : highs[seed].price;
         BOZone zone; BOEmptyZone(zone); zone.low=seedPrice; zone.high=seedPrice;
         int newest=-1;
         for(int j=0;j<count;j++) {
            double p=side==0 ? lows[j].price : highs[j].price;
            int index=side==0 ? lows[j].index : highs[j].index;
            if(end-index>c.maximumZoneAge || MathAbs(p-seedPrice)>c.clusterATR*atr) continue;
            zone.low=MathMin(zone.low,p); zone.high=MathMax(zone.high,p); zone.touches++;
            newest=(int)MathMax(newest,index);
         }
         if(zone.touches<c.minimumTouches || zone.high-zone.low>c.maxZoneATR*atr) continue;
         double padding=MathMax(0,c.minZoneATR*atr-(zone.high-zone.low))/2;
         zone.low-=padding; zone.high+=padding; zone.available=true;
         zone.age=end-newest; zone.knownAt=b[newest+c.swingRadius].time+300;
         if(side==0 && zone.high<reference && (!s.support.available || zone.high>s.support.high)) s.support=zone;
         if(side==1 && zone.low>reference && (!s.resistance.available || zone.low<s.resistance.low)) s.resistance=zone;
         double previous=b[BO_HISTORY-2].close;
         if(side==0 && zone.high<previous && (!s.preSupport.available || zone.high>s.preSupport.high)) s.preSupport=zone;
         if(side==1 && zone.low>previous && (!s.preResistance.available || zone.low<s.preResistance.low)) s.preResistance=zone;
      }
   }
}
#endif
