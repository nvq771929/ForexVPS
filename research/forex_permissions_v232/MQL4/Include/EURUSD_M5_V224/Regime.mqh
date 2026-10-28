#ifndef BO_V222_REGIME
#define BO_V222_REGIME
#include "Types.mqh"
int BOClassifyRegime(const BOAnchor &a,const BOConfig &c) {
   if(a.volatility.atr<=0) return BO_REGIME_UNKNOWN;
   if(a.volatility.previousATR>0 && a.volatility.atr/a.volatility.previousATR<.75) return BO_COMPRESSION;
   if(a.volatility.expansion>=c.expansionMinATR && a.momentum.efficiency>=c.breakoutEfficiencyMin) {
      if(a.structure.preResistance.available && a.candle.body>0 && a.momentum.netATR>=c.breakoutNetMinATR &&
         a.priorClose<=a.structure.preResistance.high && a.triggerClose>a.structure.preResistance.high+c.breakoutBufferATR*a.volatility.zoneATR) return BO_EXPANSION_UP;
      if(a.structure.preSupport.available && a.candle.body<0 && a.momentum.netATR<=-c.breakoutNetMinATR &&
         a.priorClose>=a.structure.preSupport.low && a.triggerClose<a.structure.preSupport.low-c.breakoutBufferATR*a.volatility.zoneATR) return BO_EXPANSION_DOWN;
   }
   if(a.structure.trend==2) return BO_REGIME_UNKNOWN;
   if(a.structure.trend>0 && a.momentum.netATR>=c.trendNetMinATR && a.momentum.efficiency>=c.trendEfficiencyMin &&
      a.baselineFastEMA>a.baselineSlowEMA && a.baselineFastSlope>0) return BO_ORDERLY_UP;
   if(a.structure.trend<0 && a.momentum.netATR<=-c.trendNetMinATR && a.momentum.efficiency>=c.trendEfficiencyMin &&
      a.baselineFastEMA<a.baselineSlowEMA && a.baselineFastSlope<0) return BO_ORDERLY_DOWN;
   if(a.structure.trend==0 && MathAbs(a.momentum.netATR)<c.rangeNetMaxATR && a.momentum.efficiency<c.rangeEfficiencyMax) return BO_RANGE;
   return BO_TRANSITION;
}
#endif
