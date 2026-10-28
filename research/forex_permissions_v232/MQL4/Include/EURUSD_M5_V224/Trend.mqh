#ifndef BO_V2_TREND
#define BO_V2_TREND
#include "Types.mqh"
double BOEMA(const BOBar &b[],int end,int period) {
   double value=0; for(int i=0;i<period;i++) value+=b[i].close;
   value/=period; double alpha=2.0/(period+1);
   for(int i=period;i<=end;i++) value=alpha*b[i].close+(1-alpha)*value;
   return value;
}
void BOTrendFacts(const BOBar &b[],BOAnchor &a) {
   a.priorClose=b[BO_HISTORY-2].close;
   a.fastEMA=BOEMA(b,63,20); a.slowEMA=BOEMA(b,63,50);
   a.baselineFastEMA=BOEMA(b,62,20); a.baselineSlowEMA=BOEMA(b,62,50);
   a.baselineFastSlope=a.baselineFastEMA-BOEMA(b,59,20);
   a.pullbackNetATR=(b[62].close-b[59].close)/a.volatility.zoneATR;
}
#endif
