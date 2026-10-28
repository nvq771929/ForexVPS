#ifndef BO_V222_FORECAST
#define BO_V222_FORECAST
#include "Types.mqh"
void BOFormCandidate(const BOAnchor &a,const BOConfig &c,BOCandidate &f) {
   ZeroMemory(f); f.reason=BO_NO_SETUP;
   if(!a.available) { f.reason=a.reason; return; }
   f.setup=BORoutedStrategy(a.regime);
   double atr=a.volatility.atr,zatr=a.volatility.zoneATR;
   if(atr<c.atrMinPips*.0001 || atr>c.atrMaxPips*.0001 || a.candle.range>c.shockATR*zatr) { f.reason=BO_VOLATILITY_RESEARCH; return; }
   if(f.setup==0) { f.reason=BO_CONTEXT_UNSUPPORTED; return; }
   if((f.setup==1 && c.allowSR1==0) || (f.setup==2 && c.allowTP1==0) || (f.setup==3 && c.allowBR1==0)) { f.reason=BO_STRATEGY_DISABLED; return; }
   if(a.context.overlap) { f.reason=BO_AMBIGUOUS; return; }
   int d=0;
   if(f.setup==1) {
      bool call=a.structure.support.available && a.triggerLow<a.structure.support.low-c.breakATR*zatr &&
         a.triggerClose>a.structure.support.high+c.reclaimATR*zatr && a.candle.closeLocation>=c.confirmationLocation;
      bool put=a.structure.resistance.available && a.triggerHigh>a.structure.resistance.high+c.breakATR*zatr &&
         a.triggerClose<a.structure.resistance.low-c.reclaimATR*zatr && a.candle.closeLocation<=1-c.confirmationLocation;
      if(call && put) { f.reason=BO_AMBIGUOUS; return; }
      if(!call && !put) { f.reason=(!a.structure.support.available && !a.structure.resistance.available) ? BO_ZONE_UNKNOWN : BO_NO_SETUP; return; }
      d=call ? 1 : -1;
      if(a.momentum.efficiency>=c.counterEfficiency && d*a.momentum.netATR < -1) { f.reason=BO_COUNTERPRESSURE; return; }
      f.invalidation=call ? MathMin(a.triggerLow,a.structure.support.low)-c.invalidationATR*atr : MathMax(a.triggerHigh,a.structure.resistance.high)+c.invalidationATR*atr;
      f.confirmation=call ? a.structure.support.high+c.reclaimATR*zatr : a.structure.resistance.low-c.reclaimATR*zatr;
   } else {
      d=(a.regime==BO_ORDERLY_UP || a.regime==BO_EXPANSION_UP) ? 1 : -1;
      bool location=d>0 ? a.candle.closeLocation>=c.confirmationLocation : a.candle.closeLocation<=1-c.confirmationLocation;
      if(f.setup==2) {
         bool touched=d>0 ? a.triggerLow<=a.baselineFastEMA+c.pullbackTouchATR*zatr : a.triggerHigh>=a.baselineFastEMA-c.pullbackTouchATR*zatr;
         bool slowHeld=d>0 ? a.triggerLow>a.baselineSlowEMA-c.invalidationATR*atr : a.triggerHigh<a.baselineSlowEMA+c.invalidationATR*atr;
         double confirmation=a.baselineFastEMA+d*c.reclaimATR*zatr;
         if(!(d*a.pullbackNetATR<=-c.pullbackMinimumATR && touched && slowHeld && d*a.candle.body>0 && d*(a.triggerClose-confirmation)>0 && location)) return;
         f.invalidation=d>0 ? MathMin(a.triggerLow,a.baselineFastEMA-c.pullbackTouchATR*zatr)-c.invalidationATR*atr : MathMax(a.triggerHigh,a.baselineFastEMA+c.pullbackTouchATR*zatr)+c.invalidationATR*atr;
         f.confirmation=confirmation;
      } else {
         BOZone zone; ZeroMemory(zone); if(d>0) zone=a.structure.preResistance; else zone=a.structure.preSupport;
         if(!zone.available) { f.reason=BO_ZONE_UNKNOWN; return; }
         double edge=d>0 ? zone.high : zone.low;
         if(!(d*a.candle.body>0 && d*(a.triggerClose-edge)>c.breakoutBufferATR*zatr && location)) return;
         f.invalidation=d>0 ? zone.low-c.invalidationATR*atr : zone.high+c.invalidationATR*atr;
         f.confirmation=edge+d*c.reclaimATR*zatr;
         f.retestLow=d>0 ? zone.low-c.invalidationATR*atr : zone.low-c.retestBandATR*zatr;
         f.retestHigh=d>0 ? zone.high+c.retestBandATR*zatr : zone.high+c.invalidationATR*atr;
      }
   }
   f.direction=d; f.reason=BO_OK;
   f.extension=d>0 ? (a.structure.resistance.available ? a.structure.resistance.low : 0) : (a.structure.support.available ? a.structure.support.high : 0);
}
#endif
