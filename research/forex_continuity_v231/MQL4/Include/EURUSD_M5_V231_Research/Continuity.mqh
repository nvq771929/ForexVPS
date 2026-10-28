#ifndef FX_RESEARCH_V231_CONTINUITY
#define FX_RESEARCH_V231_CONTINUITY
// Tester-only Forex adapter. Entry/lock quote freshness remains native3s.
// Derived from frozen Validation.mqh: only the two post-lock continuity limits differ.
// In particular, breachStartMs still resets after gaps>native quoteFreshSeconds.
int fxResearchPostLockGapSeconds=3;
void FXR231Observe(BOPrediction &e, const BOConfig &c, long nowMs, double bid, double ask) {
   if(!e.exists || e.entered || e.canceled) return;
   if(!MathIsValidNumber(bid) || !MathIsValidNumber(ask) || bid<=0 || ask<bid || (ask-bid)/.0001>c.spreadMaxPips) { BOCancel(e,BO_BAD_QUOTE); return; }
   int direction=e.candidate.direction;
   long gap=e.lastQuoteMs>0 ? nowMs-e.lastQuoteMs : 0;
   if(e.lastQuoteMs>0 && gap<0) { BOCancel(e,BO_TIME_ANOMALY); return; }
   if(direction!=0 && e.lastQuoteMs>0 && (gap>c.maximumObservationGapSeconds*1000 || (e.locked && gap>fxResearchPostLockGapSeconds*1000))) {
      BOCancel(e,BO_QUOTE_GAP); return;
   }
   // An unseen interval never counts toward a persistent structural breach.
   if(gap>c.quoteFreshSeconds*1000) e.breachStartMs=0;
   e.lastQuoteMs=nowMs; e.latestBid=bid;
   e.lowestBid=e.lowestBid>0 ? MathMin(e.lowestBid,bid) : bid;
   e.highestBid=MathMax(e.highestBid,bid);
   if(direction==0) { e.validation=BO_UNAVAILABLE; return; }
   if(!e.locked) e.reason=BO_OK;
   double depth=direction*(e.candidate.invalidation-bid);
   if(depth>0) {
      if(e.breachStartMs==0) e.breachStartMs=nowMs;
      if(depth>=c.deepBreachATR*e.anchor.volatility.atr || nowMs-e.breachStartMs>=c.breachSeconds*1000) {
         BOCancel(e,BO_STRUCTURAL_BREAK); return;
      }
      if(!e.locked) e.validation=BO_DEGRADED;
      return;
   }
   e.breachStartMs=0;
   if(e.locked) return; // Locked forecast is immutable; only cancellation remains possible.
   if(e.candidate.extension>0 && direction*(bid-e.candidate.extension)>=0) { BOCancel(e,BO_EXTENSION_REACHED); return; }
   if(e.candidate.setup==3) {
      if(e.retestSeenMs==0 && bid>=e.candidate.retestLow && bid<=e.candidate.retestHigh) e.retestSeenMs=nowMs;
      if(e.retestSeenMs==0 || nowMs<=e.retestSeenMs) { e.validation=BO_PRESERVED; e.reason=BO_RETEST_PENDING; return; }
   }
   e.validation=direction*(bid-e.candidate.confirmation)>0 ? BO_CONFIRMED : BO_DEGRADED;
}
void FXR231CheckQuoteAge(BOPrediction &e,const BOConfig &c,long nowMs) {
   if(!e.exists || e.entered || e.canceled || e.candidate.direction==0 || e.lastQuoteMs<=0) return;
   long age=nowMs-e.lastQuoteMs;
   if(age<0) { BOCancel(e,BO_TIME_ANOMALY); return; }
   int limit=e.locked ? fxResearchPostLockGapSeconds : c.maximumObservationGapSeconds;
   if(age>limit*1000) { BOCancel(e,BO_QUOTE_GAP); return; }
   if(!e.locked && age>c.quoteFreshSeconds*1000) {
      e.breachStartMs=0; e.validation=BO_UNAVAILABLE; e.reason=BO_WAIT_QUOTE;
   }
}
#endif
