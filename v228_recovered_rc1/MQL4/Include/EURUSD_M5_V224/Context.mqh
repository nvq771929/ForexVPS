#ifndef BO_V222_CONTEXT
#define BO_V222_CONTEXT
#include "Types.mqh"
void BOContextFacts(const BOStructure &s, double price, double atr, BOContext &x) {
   x.supportDistanceATR=s.support.available && atr>0 ? (price-s.support.high)/atr : -1;
   x.resistanceDistanceATR=s.resistance.available && atr>0 ? (s.resistance.low-price)/atr : -1;
   x.overlap=s.support.available && s.resistance.available && s.support.high>=s.resistance.low;
}
#endif
