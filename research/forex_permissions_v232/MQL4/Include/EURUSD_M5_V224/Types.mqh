#ifndef BO_V222_TYPES
#define BO_V222_TYPES

#define BO_SCHEMA 2
#define BO_HISTORY 64
#define BO_MAX_PIVOTS 64
#define BO_MAX_ZONES 32
#define BO_MAX_PENDING 16

enum BOValidation { BO_UNAVAILABLE=0, BO_PRESERVED=1, BO_CONFIRMED=2, BO_DEGRADED=3, BO_INVALIDATED=4 };
enum BORegime { BO_REGIME_UNKNOWN=0, BO_RANGE=1, BO_ORDERLY_UP=2, BO_ORDERLY_DOWN=3, BO_EXPANSION_UP=4, BO_EXPANSION_DOWN=5, BO_TRANSITION=6, BO_COMPRESSION=7 };
enum BOReason { BO_OK=0, BO_HISTORY_SHORT=1, BO_HISTORY_GAP=2, BO_BAD_OHLC=3, BO_NO_SETUP=4, BO_AMBIGUOUS=5, BO_ZONE_UNKNOWN=6,
   BO_VOLATILITY_RESEARCH=7, BO_COUNTERPRESSURE=8, BO_QUOTE_GAP=9, BO_BAD_QUOTE=10, BO_STRUCTURAL_BREAK=11,
   BO_EXTENSION_REACHED=12, BO_LOCK_MISSED=13, BO_NOT_CONFIRMED=14, BO_MODEL_UNAVAILABLE=15, BO_MODEL_OOD=16,
   BO_SHADOW_ONLY=17, BO_PAYOUT_STALE=18, BO_NO_EDGE=19, BO_PAUSED=20, BO_RESTART=21, BO_STORAGE_ERROR=22,
   BO_ENTRY_MISSED=23, BO_OUTCOME_MISSED=24, BO_PENDING_FULL=25, BO_CONFIG_CHANGED=26, BO_TIME_ANOMALY=27, BO_WAIT_QUOTE=28, BO_CONTEXT_UNSUPPORTED=29, BO_RETEST_PENDING=30, BO_STRATEGY_DISABLED=31 };
enum BOEventKind { BO_ANCHOR_EVENT=1, BO_VALIDATION_EVENT=2, BO_LOCK_EVENT=3, BO_CANCEL_EVENT=4, BO_ENTRY_EVENT=5,
   BO_OUTCOME_EVENT=6, BO_RECOVERY_EVENT=7, BO_WAIT_EVENT=8 };

struct BOConfig {
   int swingRadius; int minimumTouches; int maximumZoneAge;
   double clusterATR; double minZoneATR; double maxZoneATR;
   double breakATR; double reclaimATR; double invalidationATR;
   double confirmationLocation; double deepBreachATR;
   int breachSeconds; int quoteFreshSeconds;
   int lockLeadSeconds; int clockUncertaintySeconds; int lockGuardSeconds; int boundaryLagSeconds;
   double atrMinPips; double atrMaxPips; double shockATR; double counterEfficiency;
   double spreadMaxPips; double probabilityMargin;
   double fixedPayoutFraction;
   int maximumAnalysisDelaySeconds; int maximumObservationGapSeconds;
   double rangeNetMaxATR; double rangeEfficiencyMax; double trendNetMinATR; double trendEfficiencyMin;
   double expansionMinATR; double breakoutNetMinATR; double breakoutEfficiencyMin; double breakoutBufferATR;
   double pullbackTouchATR; double pullbackMinimumATR; double retestBandATR;
   int allowSR1; int allowTP1; int allowBR1;
};
struct BOBar { datetime time; double open; double high; double low; double close; long ticks; };
struct BOCandle { double range; double body; double upperWick; double lowerWick; double closeLocation; };
struct BOVolatility { double atr; double zoneATR; double previousATR; double expansion; };
struct BOMomentum { double netATR; double efficiency; double acceleration; };
struct BOPivot { double price; int index; int kind; };
struct BOZone { bool available; double low; double high; int touches; int age; datetime knownAt; };
struct BOStructure { int trend; int lowCount; int highCount; BOZone support; BOZone resistance; BOZone preSupport; BOZone preResistance; };
struct BOContext { double supportDistanceATR; double resistanceDistanceATR; bool overlap; };
struct BOAnchor {
   bool available; int reason; datetime closeTime;
   BOCandle candle; BOVolatility volatility; BOMomentum momentum; BOStructure structure; BOContext context;
   int regime; double triggerLow; double triggerHigh; double triggerClose;
   double priorClose; double fastEMA; double slowEMA; double baselineFastEMA; double baselineSlowEMA;
   double baselineFastSlope; double pullbackNetATR;
};
struct BOCandidate { int direction; int setup; int reason; double invalidation; double confirmation; double extension; double retestLow; double retestHigh; };
struct BOProbability {
   bool available; bool promoted; long modelId; int horizon;
   double probability; double lower; double upper; double roiLower;
   int trainCount; int calibrationCount; int testCount;
   double minATR; double maxATR; datetime expiresAt;
};
struct BOPrediction {
   bool exists; datetime analysisStart; datetime targetTime;
   BOAnchor anchor; BOCandidate candidate;
   int validation; int reason; bool canceled; bool locked; bool entered;
   long lastQuoteMs; long breachStartMs; long lockedAtMs; int serial;
   double latestBid; double lowestBid; double highestBid;
   int lockedDirection; int lockedAction; int action; int horizon; long modelId;
   double p1; double p2; double p3; long retestSeenMs;
};
struct BOPending {
   bool used; datetime analysisStart; datetime targetTime;
   long observedEntryMs; double entryBid; int direction; int setup; int regime; int validation;
   bool signal; int selectedHorizon; long modelId;
   int resolvedMask; int invalidMask; double exit1; double exit2; double exit3;
};
struct BOEvent {
   int kind; datetime analysisStart; datetime targetTime; long observedMs;
   int direction; int setup; int regime; int validation; int lockedDirection;
   int lockedAction; int action; int selectedHorizon; long modelId; int reason;
   double bid; double auxiliaryPrice; int outcomeHorizon; int outcome; long lockedAtMs;
   double p1; double p2; double p3; bool signal; int serial;
};
struct BORuntimeState {
   long sequence; uint configHash; uint feedHash; datetime lastStarted; datetime resumeAt;
   bool paused; double payout; datetime payoutAsOf;
   BOPrediction current; BOPending pending[BO_MAX_PENDING];
};

void BOConfigDefaults(BOConfig &c) {
   c.swingRadius=2; c.minimumTouches=2; c.maximumZoneAge=48;
   c.clusterATR=.25; c.minZoneATR=.10; c.maxZoneATR=.50;
   c.breakATR=.05; c.reclaimATR=.05; c.invalidationATR=.10;
   c.confirmationLocation=.65; c.deepBreachATR=.50;
   c.breachSeconds=3; c.quoteFreshSeconds=3;
   c.lockLeadSeconds=30; c.clockUncertaintySeconds=1; c.lockGuardSeconds=2; c.boundaryLagSeconds=2;
   c.atrMinPips=3; c.atrMaxPips=30; c.shockATR=2.5; c.counterEfficiency=.70;
   c.spreadMaxPips=2; c.probabilityMargin=.02; c.fixedPayoutFraction=.82;
   c.maximumAnalysisDelaySeconds=15; c.maximumObservationGapSeconds=30;
   c.rangeNetMaxATR=1.5; c.rangeEfficiencyMax=.5; c.trendNetMinATR=.75; c.trendEfficiencyMin=.35;
   c.expansionMinATR=1.5; c.breakoutNetMinATR=.5; c.breakoutEfficiencyMin=.25; c.breakoutBufferATR=.10;
   c.pullbackTouchATR=.25; c.pullbackMinimumATR=.05; c.retestBandATR=.25;
   c.allowSR1=1; c.allowTP1=1; c.allowBR1=1;
}
string BOActionName(int d) { if(d>0) return "CALL"; if(d<0) return "PUT"; return "WAIT"; }
string BORegimeName(int r) {
   if(r==BO_RANGE) return "RANGE"; if(r==BO_ORDERLY_UP) return "ORDERLY_UP";
   if(r==BO_ORDERLY_DOWN) return "ORDERLY_DOWN"; if(r==BO_EXPANSION_UP) return "EXPANSION_UP";
   if(r==BO_EXPANSION_DOWN) return "EXPANSION_DOWN"; if(r==BO_COMPRESSION) return "COMPRESSION";
   if(r==BO_TRANSITION) return "TRANSITION"; return "UNKNOWN";
}
string BOValidationName(int v) {
   if(v==BO_PRESERVED) return "PRESERVED"; if(v==BO_CONFIRMED) return "CONFIRMED";
   if(v==BO_DEGRADED) return "DEGRADED"; if(v==BO_INVALIDATED) return "INVALIDATED"; return "UNAVAILABLE";
}
string BOReasonName(int r) {
   switch(r) {
      case BO_OK:return "OK"; case BO_HISTORY_SHORT:return "HISTORY_SHORT"; case BO_HISTORY_GAP:return "HISTORY_GAP";
      case BO_BAD_OHLC:return "BAD_OHLC"; case BO_NO_SETUP:return "NO_SETUP"; case BO_AMBIGUOUS:return "AMBIGUOUS";
      case BO_ZONE_UNKNOWN:return "ZONE_UNKNOWN"; case BO_VOLATILITY_RESEARCH:return "VOLATILITY_RESEARCH_FILTER";
      case BO_COUNTERPRESSURE:return "COUNTERPRESSURE"; case BO_QUOTE_GAP:return "QUOTE_GAP"; case BO_BAD_QUOTE:return "BAD_QUOTE";
      case BO_STRUCTURAL_BREAK:return "STRUCTURAL_BREAK"; case BO_EXTENSION_REACHED:return "EXTENSION_REACHED";
      case BO_LOCK_MISSED:return "LOCK_MISSED"; case BO_NOT_CONFIRMED:return "NOT_CONFIRMED";
      case BO_MODEL_UNAVAILABLE:return "MODEL_UNAVAILABLE"; case BO_MODEL_OOD:return "MODEL_OOD";
      case BO_SHADOW_ONLY:return "SHADOW_ONLY"; case BO_PAYOUT_STALE:return "PAYOUT_STALE";
      case BO_NO_EDGE:return "NO_EDGE"; case BO_PAUSED:return "PAUSED"; case BO_RESTART:return "RESTART";
      case BO_STORAGE_ERROR:return "STORAGE_ERROR"; case BO_ENTRY_MISSED:return "ENTRY_MISSED";
      case BO_OUTCOME_MISSED:return "OUTCOME_MISSED"; case BO_PENDING_FULL:return "PENDING_FULL";
      case BO_CONFIG_CHANGED:return "CONFIG_CHANGED"; case BO_TIME_ANOMALY:return "TIME_ANOMALY";
      case BO_WAIT_QUOTE:return "WAIT_QUOTE";
      case BO_CONTEXT_UNSUPPORTED:return "CONTEXT_UNSUPPORTED";
      case BO_RETEST_PENDING:return "RETEST_PENDING";
      case BO_STRATEGY_DISABLED:return "STRATEGY_DISABLED";
   }
   return "UNKNOWN_REASON";
}
int BORoutedStrategy(int regime) {
   if(regime==BO_RANGE) return 1;
   if(regime==BO_ORDERLY_UP || regime==BO_ORDERLY_DOWN) return 2;
   if(regime==BO_EXPANSION_UP || regime==BO_EXPANSION_DOWN) return 3;
   return 0;
}
string BOStrategyName(int setup) {
   if(setup==1) return "SR1_FAILED_BREAK";
   if(setup==2) return "TP1_TREND_PULLBACK";
   if(setup==3) return "BR1_BREAKOUT_RETEST";
   return "WAIT";
}
#endif
