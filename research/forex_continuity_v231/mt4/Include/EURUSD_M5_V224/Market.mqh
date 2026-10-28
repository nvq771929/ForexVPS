#ifndef BO_V222_MARKET
#define BO_V222_MARKET
#include "Candle.mqh"
#include "Volatility.mqh"
#include "Momentum.mqh"
#include "Structure.mqh"
#include "Context.mqh"
#include "Regime.mqh"
#include "Trend.mqh"
void BOBuildMarket(const BOBar &b[], int count, const BOConfig &c, BOAnchor &a) {
   ZeroMemory(a);
   a.candle.closeLocation=.5; a.structure.trend=2;
   a.context.supportDistanceATR=-1; a.context.resistanceDistanceATR=-1;
   a.available=false; a.reason=BO_HISTORY_SHORT;
   if(count!=BO_HISTORY) return;
   for(int i=0;i<count;i++) {
      if(!MathIsValidNumber(b[i].open) || !MathIsValidNumber(b[i].high) || !MathIsValidNumber(b[i].low) || !MathIsValidNumber(b[i].close) ||
         b[i].low<=0 || b[i].low>MathMin(b[i].open,b[i].close) || b[i].high<MathMax(b[i].open,b[i].close) || b[i].time%300!=0) {
         a.reason=BO_BAD_OHLC; return;
      }
      if(i>0 && b[i].time-b[i-1].time!=300) { a.reason=BO_HISTORY_GAP; return; }
   }
   a.closeTime=b[count-1].time+300; a.triggerLow=b[count-1].low; a.triggerHigh=b[count-1].high; a.triggerClose=b[count-1].close;
   BOCandleFacts(b[count-1],a.candle); BOVolatilityFacts(b,a.volatility);
   if(a.volatility.atr<=0 || a.volatility.zoneATR<=0) { a.reason=BO_VOLATILITY_RESEARCH; return; }
   BOMomentumFacts(b,a.volatility.atr,a.momentum); BOFindStructure(b,c,a.volatility.zoneATR,a.structure);
   BOContextFacts(a.structure,a.triggerClose,a.volatility.atr,a.context);
   BOTrendFacts(b,a); a.regime=BOClassifyRegime(a,c); a.available=true; a.reason=BO_OK;
}
#endif
