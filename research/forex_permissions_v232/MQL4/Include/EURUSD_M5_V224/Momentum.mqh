#ifndef BO_V222_MOMENTUM
#define BO_V222_MOMENTUM
#include "Types.mqh"
void BOMomentumFacts(const BOBar &b[], double atr, BOMomentum &m) {
   int end=BO_HISTORY-1; double net=b[end].close-b[end-12].close, travel=0;
   for(int i=end-11;i<=end;i++) travel+=MathAbs(b[i].close-b[i-1].close);
   m.netATR=atr>0 ? net/atr : 0; m.efficiency=travel>0 ? MathAbs(net)/travel : 0;
   m.acceleration=atr>0 ? ((b[end].close-b[end-3].close)-(b[end-3].close-b[end-6].close))/atr : 0;
}
#endif
