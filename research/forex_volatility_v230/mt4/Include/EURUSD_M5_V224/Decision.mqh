#ifndef BO_V222_DECISION
#define BO_V222_DECISION
#include "Types.mqh"
void BOLock(BOPrediction &e, const BOConfig &c, long nowMs, bool shadow, bool paused,
            const BOProbability &rows[]) {
   if(e.locked || !e.exists) return;
   e.locked=true; e.lockedAtMs=nowMs; e.lockedDirection=0; e.lockedAction=0; e.action=0; e.horizon=0; e.modelId=0;
   e.p1=-1; e.p2=-1; e.p3=-1;
   long cutoff=(long)e.targetTime*1000-(c.lockLeadSeconds+c.clockUncertaintySeconds)*1000;
   if(nowMs>cutoff) { e.reason=BO_LOCK_MISSED; return; }
   if(e.canceled) return;
   if(e.candidate.direction==0) { e.reason=e.candidate.reason; return; }
   if(e.lastQuoteMs==0 || nowMs-e.lastQuoteMs>c.quoteFreshSeconds*1000) { BOCancel(e,BO_QUOTE_GAP); return; }
   if(e.validation!=BO_CONFIRMED) { e.reason=BO_NOT_CONFIRMED; return; }
   e.lockedDirection=e.candidate.direction;
   if(paused) { e.reason=BO_PAUSED; return; }
   double payout=c.fixedPayoutFraction,best=-1;
   for(int i=0;i<3;i++) {
      BOProbability p=rows[i];
      if(p.available) { if(i==0)e.p1=p.probability; if(i==1)e.p2=p.probability; if(i==2)e.p3=p.probability; }
      if(payout<=0 || payout>1 || !p.available || !p.promoted || p.horizon!=i+1 || p.expiresAt<e.targetTime+c.boundaryLagSeconds ||
         e.anchor.volatility.atr/.0001<p.minATR || e.anchor.volatility.atr/.0001>p.maxATR) continue;
      if(p.lower<=1/(1+payout)+c.probabilityMargin || p.roiLower<=0) continue;
      double edge=(1+payout)*p.lower-1;
      if(edge>best) { best=edge; e.horizon=i+1; e.modelId=p.modelId; }
   }
   if(shadow) { e.reason=BO_SHADOW_ONLY; e.horizon=0; return; }
   if(best<0) { e.reason=BO_MODEL_UNAVAILABLE; return; }
   e.lockedAction=e.lockedDirection; e.action=e.lockedAction; e.reason=BO_OK;
}
bool BOEntryAllowed(const BOPrediction &e, const BOConfig &c, long nowMs, bool paused) {
   return e.locked && !e.canceled && e.action!=0 && !paused && nowMs>=(long)e.targetTime*1000 &&
      nowMs<=(long)(e.targetTime+c.boundaryLagSeconds)*1000 && e.lastQuoteMs>0 &&
      nowMs-e.lastQuoteMs<=c.quoteFreshSeconds*1000;
}
#endif
