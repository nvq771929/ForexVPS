#ifndef BO_V222_VOLATILITY
#define BO_V222_VOLATILITY
#include "Types.mqh"
double BOATR(const BOBar &b[], int end, int count) {
   double sum=0;
   for(int i=end-count+1;i<=end;i++)
      sum+=MathMax(b[i].high-b[i].low,MathMax(MathAbs(b[i].high-b[i-1].close),MathAbs(b[i].low-b[i-1].close)));
   return sum/count;
}
void BOVolatilityFacts(const BOBar &b[], BOVolatility &v) {
   v.atr=BOATR(b,BO_HISTORY-1,14); v.zoneATR=BOATR(b,BO_HISTORY-2,14);
   v.previousATR=BOATR(b,BO_HISTORY-15,14);
   v.expansion=v.zoneATR>0 ? (b[BO_HISTORY-1].high-b[BO_HISTORY-1].low)/v.zoneATR : 0;
}
#endif
