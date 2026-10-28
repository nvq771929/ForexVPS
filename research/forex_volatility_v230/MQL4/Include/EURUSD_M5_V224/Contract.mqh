#ifndef BO_V222_CONTRACT
#define BO_V222_CONTRACT
#include "Types.mqh"
#define BO_LOGIC_VERSION 2026101707
void BOHashNumber(string &text, double value) { text+="|"+DoubleToString(value,6); }
uint BOHashText(string text) {
   uint hash=2166136261;
   for(int i=0;i<StringLen(text);i++) hash=(hash^(uint)StringGetCharacter(text,i))*16777619;
   return hash;
}
uint BOConfigHash(const BOConfig &c) {
   string text="BO2";
   BOHashNumber(text,c.swingRadius); BOHashNumber(text,c.minimumTouches); BOHashNumber(text,c.maximumZoneAge);
   BOHashNumber(text,c.clusterATR); BOHashNumber(text,c.minZoneATR); BOHashNumber(text,c.maxZoneATR);
   BOHashNumber(text,c.breakATR); BOHashNumber(text,c.reclaimATR); BOHashNumber(text,c.invalidationATR);
   BOHashNumber(text,c.confirmationLocation); BOHashNumber(text,c.deepBreachATR);
   BOHashNumber(text,c.breachSeconds); BOHashNumber(text,c.quoteFreshSeconds);
   BOHashNumber(text,c.lockLeadSeconds); BOHashNumber(text,c.clockUncertaintySeconds); BOHashNumber(text,c.lockGuardSeconds);
   BOHashNumber(text,c.boundaryLagSeconds); BOHashNumber(text,c.atrMinPips); BOHashNumber(text,c.atrMaxPips);
   BOHashNumber(text,c.shockATR); BOHashNumber(text,c.counterEfficiency); BOHashNumber(text,c.spreadMaxPips);
   BOHashNumber(text,c.probabilityMargin); BOHashNumber(text,c.fixedPayoutFraction);
   BOHashNumber(text,c.maximumAnalysisDelaySeconds); BOHashNumber(text,c.maximumObservationGapSeconds);
   BOHashNumber(text,c.rangeNetMaxATR); BOHashNumber(text,c.rangeEfficiencyMax);
   BOHashNumber(text,c.trendNetMinATR); BOHashNumber(text,c.trendEfficiencyMin);
   BOHashNumber(text,c.expansionMinATR); BOHashNumber(text,c.breakoutNetMinATR);
   BOHashNumber(text,c.breakoutEfficiencyMin); BOHashNumber(text,c.breakoutBufferATR);
   BOHashNumber(text,c.pullbackTouchATR); BOHashNumber(text,c.pullbackMinimumATR); BOHashNumber(text,c.retestBandATR);
   BOHashNumber(text,c.allowSR1); BOHashNumber(text,c.allowTP1); BOHashNumber(text,c.allowBR1);
   return BOHashText(text);
}
bool BOSafeTag(string tag) {
   if(StringLen(tag)<1 || StringLen(tag)>32) return false;
   for(int i=0;i<StringLen(tag);i++) {
      int ch=StringGetCharacter(tag,i);
      if(!((ch>=48 && ch<=57)||(ch>=65 && ch<=90)||(ch>=97 && ch<=122)||ch==95||ch==45||ch==46)) return false;
   }
   return StringFind(tag,"..")<0;
}
string BOEpisodeId(datetime start) { return Symbol()+"_M5_"+IntegerToString((long)start); }
#endif
