#ifndef BO_V222_OUTCOMES
#define BO_V222_OUTCOMES
#include "Types.mqh"
int BOOutcome(double entry,double exit) { double delta=MathRound(exit*100000)-MathRound(entry*100000); return delta>0 ? 1 : (delta<0 ? -1 : 0); }
int BOFreePending(const BORuntimeState &state) {
   for(int i=0;i<BO_MAX_PENDING;i++) if(!state.pending[i].used || state.pending[i].resolvedMask==7) return i;
   return -1;
}
void BOCaptureEntry(const BOPrediction &e,long nowMs,double bid,bool signal,BOPending &p) {
   ZeroMemory(p); p.used=true; p.analysisStart=e.analysisStart; p.targetTime=e.targetTime;
   p.observedEntryMs=nowMs; p.entryBid=bid; p.direction=e.lockedDirection;
   p.setup=e.candidate.setup; p.regime=e.anchor.regime; p.validation=e.validation;
   p.signal=signal; p.selectedHorizon=signal ? e.horizon : 0; p.modelId=e.modelId;
}
#endif
