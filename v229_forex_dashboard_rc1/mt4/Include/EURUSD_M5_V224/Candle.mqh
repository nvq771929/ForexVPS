#ifndef BO_V222_CANDLE
#define BO_V222_CANDLE
#include "Types.mqh"
void BOCandleFacts(const BOBar &b, BOCandle &out) {
   out.range=b.high-b.low; out.body=b.close-b.open;
   out.upperWick=b.high-MathMax(b.open,b.close); out.lowerWick=MathMin(b.open,b.close)-b.low;
   out.closeLocation=out.range>0 ? (b.close-b.low)/out.range : .5;
}
#endif
