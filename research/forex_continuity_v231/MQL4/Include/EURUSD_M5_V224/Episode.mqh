#ifndef BO_V222_EPISODE
#define BO_V222_EPISODE
#include "Forecast.mqh"
#include "Validation.mqh"
#include "Decision.mqh"
void BOStartEpisode(const BOAnchor &a, const BOConfig &c, datetime analysisStart, BOPrediction &e) {
   e.exists=true; e.analysisStart=analysisStart; e.targetTime=analysisStart+300; e.anchor=a;
   BOFormCandidate(a,c,e.candidate); e.validation=e.candidate.direction!=0 ? BO_PRESERVED : BO_UNAVAILABLE;
   e.reason=e.candidate.reason; e.canceled=false; e.locked=false; e.entered=false;
   e.retestSeenMs=0; e.lastQuoteMs=0; e.breachStartMs=0; e.lockedAtMs=0; e.serial=0;
   e.latestBid=0; e.lowestBid=0; e.highestBid=0; e.lockedDirection=0; e.lockedAction=0;
   e.action=0; e.horizon=0; e.modelId=0; e.p1=-1; e.p2=-1; e.p3=-1;
   if(a.available && a.closeTime!=analysisStart) BOCancel(e,BO_HISTORY_GAP);
}
long BOLockDue(const BOPrediction &e, const BOConfig &c) {
   return (long)e.targetTime*1000-(c.lockLeadSeconds+c.lockGuardSeconds)*1000;
}
#endif
