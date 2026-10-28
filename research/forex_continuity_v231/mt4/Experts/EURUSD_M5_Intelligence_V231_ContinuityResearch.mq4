#property strict
#property version "2.31"
#property description "TESTER ONLY: post-lock continuity research at fixed ATR3. Entry freshness remains3s. No historical news validation."
#include <EURUSD_M5_V224/Market.mqh>
#include <EURUSD_M5_V224/Episode.mqh>
#include <EURUSD_M5_V224/AdvancedLearning.mqh>
#include <EURUSD_M5_V224/Origin.mqh>
#include <EURUSD_M5_V224/Journal.mqh>
#include <EURUSD_M5_V224/Outcomes.mqh>
#include <EURUSD_M5_V224/Clock.mqh>
#include <EURUSD_M5_V224/ClockObservation.mqh>
#include <EURUSD_M5_V224/History.mqh>
#include <EURUSD_M5_V224/TesterDashboard.mqh>
#include <EURUSD_M5_V224/RuntimeDiagnostics.mqh>
#include <EURUSD_M5_V224/CandidateDiagnostics.mqh>
#include <EURUSD_M5_V224/MarketContext.mqh>
#include <EURUSD_M5_V224/ManualSignals.mqh>
#include <EURUSD_M5_V224/SlotDiagnostics.mqh>
#include <EURUSD_M5_V224/LearningDialogue.mqh>
#include <EURUSD_M5_V224/UI.mqh>
// Scope observation to the adapter's Forex include without editing frozen headers.
void FXDashboardComment(string legacyText);
#include <EURUSD_M5_V231_Research/Continuity.mqh>
#define BOObserve FXR231Observe
#define BOCheckQuoteAge FXR231CheckQuoteAge
#define BOClockTick BOObservedClockTick
#define Comment FXDashboardComment
#include <EURUSD_M5_V224/ForexEngine.mqh>
#undef Comment
#undef BOClockTick
#undef BOCheckQuoteAge
#undef BOObserve
#include <EURUSD_M5_V224/ForexDashboard.mqh>
#include <EURUSD_M5_V224/EmbeddedObserver.mqh>
#include <EURUSD_M5_V224/ChartRoleV228.mqh>

const string BO_EA_RELEASE="V2.31_RESEARCH";

input BOTradingMode TradingMode=Forex;
input string InstanceTag="v231_gap03_run001";
input double ForexResearchMinAtrPips=3.0;
input int ForexResearchPostLockGapSeconds=3;
const bool ShadowOnly=true; // Binary journal only; Forex has a separate execution path.
input bool EnableDemoSignals=true;
input int DemoExpiryMinutes=5;
input bool UseValidatedLearning=false;
input bool EnableAlerts=false;
input bool EnableNewsAlerts=true;
input bool DiagnosticMode=false;
input bool RecordClockObservation=true;
input bool UseVietnameseAccents=false;
input string PanelFontName="Arial";
input int PanelFontSize=16;
input int ActionFontSize=28;
input int PanelLeft=12;
input int PanelTop=20;
input int MinimumLockLeadSeconds=30;
input int MaximumAnalysisStartDelaySeconds=15;
input int MaximumObservationGapSeconds=30;
input bool AllowSR1=true;
input bool AllowTP1=true;
input bool AllowBR1=true;
input bool RecordReplayInputs=true;
input bool CompactTesterLogs=true;

// Binary-only pre-lock adviser. No reply/late reply => the native EA decides.
input bool EnableBinaryLearningDialogue=false;
input bool BinaryLearningAdviceAffectsSignals=false;
input int BinaryLearningRequestIntervalSeconds=30;
input int BinaryLearningReplyMaxAgeSeconds=30;
input int BinaryLearningReserveBeforeLockSeconds=5;

// Embedded closed-bar context is independent of the optional external learner.
// No model weights or action override are shipped. Verify the broker clock first.
input bool EnableEmbeddedContext=false;
input bool EmbeddedBrokerClockVerified=false;
input int EmbeddedBrokerUTCOffsetMinutes=0;
input int EmbeddedBootstrapM5Bars=4800;
input int EmbeddedPanelLeft=570;
input int EmbeddedPanelTop=260;

// Forex settings do not alter the frozen Binary Option probability/POD contract.
input bool ForexEnableTrading=true;
input bool ForexUseDashboard=false;
input bool ForexAllowRealTrading=false;
input double ForexRiskPercent=0.5;
input double ForexMaxDailyLossPercent=2.0;
input double ForexStopLossATR=1.5;
input double ForexMinStopLossPips=6.0;
input double ForexMaxStopLossPips=30.0;
input double ForexTakeProfitRR=2.0;
input double ForexMaxSpreadPips=1.5;
input double ForexMaxSlippagePips=0.3;
input double ForexCostBufferPips=0.5;
input double ForexMaximumLots=1.0;
input int ForexMaxHoldMinutes=60;
input int ForexMagicNumber=2220520;
// Forex protection: thresholds use the original filled entry-to-SL distance (1R).
input bool ForexBreakEven=true;
input double ForexBreakEvenAtR=1.0;
input double ForexBreakEvenOffsetPips=0.5;
input bool ForexTrailingStop=true;
input double ForexTrailingStartR=1.5;
input double ForexTrailingATR=1.5;
input double ForexTrailingMinPips=3.0;
input double ForexTrailingStepPips=0.5;
input int ForexMaxDailyEntryAttempts=6;
input int ForexMaxConsecutiveLosses=3;
input int ForexCooldownMinutes=15;
input bool ForexEmergencyCloseOwnPositions=false;
input bool ForexCloseOwnOnDailyLoss=true;
// Minutes after midnight of the BROKER clock. Defaults for the confirmed UTC+0 feed.
input bool ForexUseTradingSchedule=true;
input int ForexRolloverStartMinute=1260; // 21:00: avoids both NY DST/winter rollover windows.
input int ForexRolloverEndMinute=1335;   // 22:15.
input int ForexFridayStopMinute=1200;   // No new entries after Friday 20:00.
input int ForexFridayCloseMinute=1230;  // Close own positions from Friday 20:30.
input bool ForexNewsFilter=false;
input int ForexNewsMaxAgeSeconds=1800;
input int ForexNewsHighBeforeMinutes=30;
input int ForexNewsHighAfterMinutes=15;
input int ForexNewsMediumBeforeMinutes=15;
input int ForexNewsMediumAfterMinutes=10;
input int ForexNewsEntryLookaheadMinutes=5;
input int ForexNewsPositionExitMinutes=5;
// 0=keep SL/TP, 1=close full, 2=close losing / reduce profitable unprotected / keep secured.
input int ForexNewsHighPositionAction=1;
input int ForexNewsMediumPositionAction=2;
input double ForexNewsReducePercent=50.0;
// Averaging is an explicit research option. RiskPercent covers the WHOLE basket.
input bool ForexEnableAveraging=false;
input double ForexInitialRiskFraction=0.7;
input double ForexAverageTriggerR=0.5;
input double ForexAverageMaxAdverseR=0.8;
input double ForexAverageMaxLotRatio=0.5;
input int ForexAverageWindowMinutes=30;
input double ForexMinMarginLevelPercent=500.0;
input double ForexMinFreeEquityPercent=50.0;

BOTradingMode boActiveTradingMode=BinaryOption;
bool FXMode() { return TradingMode==Forex; }
int FXInitFromInputs() {
   string symbol=Symbol();StringToUpper(symbol);
   if((IsTesting() && Period()!=PERIOD_M5) || StringFind(symbol,"EURUSD")!=0 || StringFind(symbol,"OTC")>=0 ||
      (Digits!=4 && Digits!=5) || !BOSafeTag(Symbol()) || !BOSafeTag(InstanceTag) || IsOptimization() ||
      MinimumLockLeadSeconds<30 || MinimumLockLeadSeconds>120 || MaximumAnalysisStartDelaySeconds<1 ||
      MaximumAnalysisStartDelaySeconds>60 || MaximumObservationGapSeconds<3 || MaximumObservationGapSeconds>60)return INIT_PARAMETERS_INCORRECT;
   FXSettings settings;ZeroMemory(settings);
   settings.enabled=ForexEnableTrading;settings.allowReal=ForexAllowRealTrading;settings.recordQuotes=RecordReplayInputs;
   settings.riskPercent=ForexRiskPercent;settings.dailyLossPercent=ForexMaxDailyLossPercent;settings.stopATR=ForexStopLossATR;
   settings.minStopPips=ForexMinStopLossPips;settings.maxStopPips=ForexMaxStopLossPips;settings.rewardRisk=ForexTakeProfitRR;
   settings.maxSpreadPips=ForexMaxSpreadPips;settings.slippagePips=ForexMaxSlippagePips;settings.costBufferPips=ForexCostBufferPips;
   settings.maximumLots=ForexMaximumLots;settings.maxHoldMinutes=ForexMaxHoldMinutes;settings.magic=ForexMagicNumber;
   settings.breakEven=ForexBreakEven;settings.breakEvenR=ForexBreakEvenAtR;settings.breakEvenOffsetPips=ForexBreakEvenOffsetPips;
   settings.trailing=ForexTrailingStop;settings.trailStartR=ForexTrailingStartR;settings.trailATR=ForexTrailingATR;
   settings.trailMinPips=ForexTrailingMinPips;settings.trailStepPips=ForexTrailingStepPips;
   settings.maxDailyAttempts=ForexMaxDailyEntryAttempts;settings.maxLossStreak=ForexMaxConsecutiveLosses;settings.cooldownMinutes=ForexCooldownMinutes;
   settings.emergencyClose=ForexEmergencyCloseOwnPositions;settings.schedule=ForexUseTradingSchedule;
   settings.closeOnDailyLoss=ForexCloseOwnOnDailyLoss;
   settings.rolloverStartMinute=ForexRolloverStartMinute;settings.rolloverEndMinute=ForexRolloverEndMinute;
   settings.fridayStopMinute=ForexFridayStopMinute;settings.fridayCloseMinute=ForexFridayCloseMinute;
   settings.newsFilter=ForexNewsFilter;settings.newsMaxAgeSeconds=ForexNewsMaxAgeSeconds;
   settings.newsHighBefore=ForexNewsHighBeforeMinutes;settings.newsHighAfter=ForexNewsHighAfterMinutes;
   settings.newsMediumBefore=ForexNewsMediumBeforeMinutes;settings.newsMediumAfter=ForexNewsMediumAfterMinutes;
   settings.newsLookaheadMinutes=ForexNewsEntryLookaheadMinutes;settings.newsExitMinutes=ForexNewsPositionExitMinutes;
   settings.newsHighAction=ForexNewsHighPositionAction;settings.newsMediumAction=ForexNewsMediumPositionAction;
   settings.newsReducePercent=ForexNewsReducePercent;
   settings.averaging=ForexEnableAveraging;settings.initialRiskFraction=ForexInitialRiskFraction;
   settings.averageTriggerR=ForexAverageTriggerR;settings.averageMaxAdverseR=ForexAverageMaxAdverseR;
   settings.averageLotRatio=ForexAverageMaxLotRatio;settings.averageWindowMinutes=ForexAverageWindowMinutes;
   settings.minMarginLevelPercent=ForexMinMarginLevelPercent;settings.minFreeEquityPercent=ForexMinFreeEquityPercent;
   BOConfig config;BOConfigDefaults(config);config.atrMinPips=ForexResearchMinAtrPips;config.lockLeadSeconds=MinimumLockLeadSeconds;
   config.maximumAnalysisDelaySeconds=MaximumAnalysisStartDelaySeconds;config.maximumObservationGapSeconds=MaximumObservationGapSeconds;
   config.allowSR1=AllowSR1 ? 1 : 0;config.allowTP1=AllowTP1 ? 1 : 0;config.allowBR1=AllowBR1 ? 1 : 0;
   if(BOConfigHash(config)!=(uint)2669644079)return INIT_PARAMETERS_INCORRECT;
   return FXInit(settings,config,InstanceTag);
}



uint FXR231PolicyHash() {
   return BOHashText("V231_POSTLOCK_CONTINUITY_V1|"+IntegerToString((long)BOConfigHash(fxConfig))+"|"+
      IntegerToString(fxResearchPostLockGapSeconds)+"|"+IntegerToString(fxConfig.quoteFreshSeconds)+"|"+
      IntegerToString(fxConfig.maximumObservationGapSeconds)+"|"+IntegerToString(fxConfig.boundaryLagSeconds));
}
bool FXResearchRecordConfig() {
   string path=fxRoot+"\\research_config_v231.csv";
   if(FileIsExist(path))return false;
   int f=FileOpen(path,FILE_WRITE|FILE_CSV|FILE_ANSI,',');if(f==INVALID_HANDLE)return false;
   uint policy=FXR231PolicyHash();
   string payload=InstanceTag+"|"+IntegerToString((long)BOConfigHash(fxConfig))+"|"+
      IntegerToString(ForexResearchPostLockGapSeconds)+"|"+IntegerToString(fxResearchPostLockGapSeconds)+"|"+IntegerToString((long)policy);
   bool ok=FileWrite(f,"contract","release","origin","tag","min_atr_pips","native_config_hash","requested_post_lock_gap_s",
      "applied_post_lock_gap_s","entry_quote_fresh_s","pre_lock_gap_s","entry_lag_s","policy_hash","news_filter","real_allowed","quote_recording","clock_recording","checksum")>0;
   if(ok)ok=FileWrite(f,"V231_FOREX_CONTINUITY_RESEARCH_V1",BO_EA_RELEASE,"TESTER_PRICE_ONLY_NO_NEWS",InstanceTag,
      DoubleToString(fxConfig.atrMinPips,6),BOConfigHash(fxConfig),ForexResearchPostLockGapSeconds,fxResearchPostLockGapSeconds,
      fxConfig.quoteFreshSeconds,fxConfig.maximumObservationGapSeconds,fxConfig.boundaryLagSeconds,policy,
      fxSettings.newsFilter ? 1 : 0,fxSettings.allowReal ? 1 : 0,fxSettings.recordQuotes ? 1 : 0,RecordClockObservation ? 1 : 0,BOHashText(payload))>0;
   FileFlush(f);FileClose(f);return ok;
}

BOConfig boConfig; BORuntimeState boState;
string boRoot,boSession; int boLease=INVALID_HANDLE;
bool boHealthy=true; long boInputSequence=0; bool boStarted=false; bool boFirstLiveTick=true; datetime boAttachBar=0;

void BOFailStorage() {
   boHealthy=false;
   BOSlotState(boRoot,boSession,boState,boDemoPolicy,BONowMs(),"STORAGE_ERROR",true);
   if(boState.current.exists && !boState.current.entered) BOCancel(boState.current,BO_STORAGE_ERROR);
   Print("BO V224 storage/integrity blocked. Replay writing stopped. Preserve logs and Experts messages before restarting with a fresh InstanceTag.");
}
bool BORecordReplay(string kind,long nowMs,datetime serverTime,double bid,double ask) {
   if(!boHealthy)return false;
   long next=boInputSequence+1;
   if(!BOLogReplayInput(boRoot,boSession,next,kind,nowMs,serverTime,bid,ask,ShadowOnly)) { BOFailStorage();return false; }
   boInputSequence=next;return true;
}
bool BORecord(BOEvent &event) {
   if(!boHealthy) return false;
   boState.sequence++;
   if(!BOCommit(boRoot,boState,event)) { BOFailStorage(); return false; }
   BOTesterDashboardRecord(event);
   BODiagnosticsRecord(boRoot,boSession,boState,boConfig,event);
   BOCandidateDiagnosticsRecord(boRoot,boSession,boState,boConfig,event,boDemoPolicy,boDemoHorizon);
   BOContextRecord(boRoot,boSession,boState,event,boDemoPolicy,boDemoHorizon);
   return true;
}
bool BORecordCurrent(int kind,long nowMs) {
   BOEvent event; BOMakeEvent(boState.current,kind,nowMs,event); return BORecord(event);
}
void BOAlertChange(string text) { if(EnableAlerts && !IsTesting()) Alert(text); }
void BOManualWarning(string fallback) {
   if(BOManualOwns((long)boState.current.analysisStart))
      BOAlertChange("TIN DA PHAT DUOC GIU | Canh bao du lieu/kiem tra native: "+BOReasonName(boState.current.reason));
   else BOAlertChange(fallback);
}
void BORenderCurrent(long nowMs) {
   BOContextRefresh(boRoot,boState,boDemoPolicy,boDemoHorizon);
   string newsWarning;
   if(EnableAlerts && EnableNewsAlerts && BOContextNewsAlert(boRoot,nowMs,(long)boState.current.targetTime,boDemoHorizon,newsWarning))BOAlertChange(newsWarning);
   BORender(boState,boConfig,nowMs,ShadowOnly,boHealthy,boRoot,boLearnCount,DiagnosticMode,
            PanelFontSize,ActionFontSize,PanelFontName,PanelLeft,PanelTop,BO_EA_RELEASE);
   BOEmbeddedRender(nowMs,EmbeddedPanelLeft,EmbeddedPanelTop);
}

void BORefreshHistory() {
   if(!boHealthy) return;
   // CopyRates can wait for broker data. Protect a running preparation and
   // reference boundaries; process quotes/outcomes before requesting history.
   if(boState.current.exists && !boState.current.entered && !boState.current.canceled) return;
   long nowMs=BONowMs();
   if(nowMs>0) for(int i=0;i<BO_MAX_PENDING;i++) if(boState.pending[i].used) {
      for(int h=1;h<=3;h++) {
         if((boState.pending[i].resolvedMask & (1<<(h-1)))!=0) continue;
         long remaining=(long)(boState.pending[i].targetTime+h*300)*1000-nowMs;
         if(remaining>=-boConfig.boundaryLagSeconds*1000 && remaining<=60000) return;
      }
   }
   long brokerNow=nowMs>0 ? nowMs/1000 : (long)TimeCurrent();
   if(!IsTesting()) { BOLearnRefresh(boRoot,brokerNow); BOAdvancedRefresh(boRoot,brokerNow); }
   if(BOHistoryRefresh() && !BOLogHistoryStatus(boRoot,boSession)) BOFailStorage();
}
bool BOLoadBars(BOBar &bars[]) {
   return BOHistoryCopy(iTime(NULL,PERIOD_M5,0),bars);
}
void BOResolve(long nowMs,bool tick,double bid) {
   if(!boHealthy) return;
   for(int i=0;i<BO_MAX_PENDING;i++) {
      if(!boState.pending[i].used || boState.pending[i].resolvedMask==7) continue;
      for(int h=1;h<=3;h++) {
         int bit=1<<(h-1); if((boState.pending[i].resolvedMask & bit)!=0) continue;
         long target=(long)(boState.pending[i].targetTime+h*300)*1000;
         if(nowMs<target) continue;
         bool missed=nowMs>target+boConfig.boundaryLagSeconds*1000;
         if(!tick && !missed) continue;
         if(!tick || bid<=0 || !MathIsValidNumber(bid)) missed=true;
         boState.pending[i].resolvedMask|=bit;
         if(missed) boState.pending[i].invalidMask|=bit;
         else { if(h==1)boState.pending[i].exit1=bid; if(h==2)boState.pending[i].exit2=bid; if(h==3)boState.pending[i].exit3=bid; }
         BOEvent event; ZeroMemory(event); event.kind=BO_OUTCOME_EVENT; event.analysisStart=boState.pending[i].analysisStart;
         event.targetTime=boState.pending[i].targetTime; event.observedMs=nowMs;
         event.direction=boState.pending[i].direction; event.setup=boState.pending[i].setup; event.regime=boState.pending[i].regime;
         event.validation=boState.pending[i].validation; event.bid=boState.pending[i].entryBid; event.auxiliaryPrice=missed ? 0 : bid;
         event.outcomeHorizon=h; event.outcome=missed ? 9 : BOOutcome(event.bid,bid);
         event.reason=missed ? BO_OUTCOME_MISSED : BO_OK; event.signal=boState.pending[i].signal;
         event.selectedHorizon=boState.pending[i].selectedHorizon; event.modelId=boState.pending[i].modelId;
         if(!BORecord(event)) return;
      }
   }
}
void BOAttemptAnchor(long quoteMs,double bid,double ask) {
   if(!boHealthy)return;
   long nowMs=BONowMs();
   BOSlotObserve(boRoot,boSession,boState,boConfig,boDemoPolicy,nowMs,boAttachBar);
   datetime bar=iTime(NULL,PERIOD_M5,0);
   if(boSlotFinal || bar!=boSlotBar || bar<=boState.lastStarted || bar<boState.resumeAt)return;
   if(nowMs<quoteMs || nowMs-quoteMs>boConfig.quoteFreshSeconds*1000) {
      BOSlotState(boRoot,boSession,boState,boDemoPolicy,nowMs,"QUOTE_TOO_OLD");return;
   }
   if(!IsConnected()) { BOSlotState(boRoot,boSession,boState,boDemoPolicy,nowMs,"DISCONNECTED");return; }
   boSlotAttempts++;
   BOBar bars[];BOAnchor snapshot;ZeroMemory(snapshot);
   if(!BOLoadBars(bars)) {
      BOSlotState(boRoot,boSession,boState,boDemoPolicy,nowMs,boHistoryBar!=bar ? "WAIT_HISTORY_BAR" : "HISTORY_UNAVAILABLE");return;
   }
   BOBuildMarket(bars,BO_HISTORY,boConfig,snapshot);
   // CPU/history work may have consumed the window. Never create a backdated preparation.
   nowMs=BONowMs();
   if(nowMs>(long)(bar+boConfig.maximumAnalysisDelaySeconds)*1000 || iTime(NULL,PERIOD_M5,0)!=bar) {
      BOSlotState(boRoot,boSession,boState,boDemoPolicy,nowMs,"MISSED_START_WINDOW",true);return;
   }
   if(nowMs<quoteMs || nowMs-quoteMs>boConfig.quoteFreshSeconds*1000) {
      BOSlotState(boRoot,boSession,boState,boDemoPolicy,nowMs,"QUOTE_TOO_OLD");return;
   }
   BOStartEpisode(snapshot,boConfig,bar,boState.current);boState.lastStarted=bar;
   if(!BOWriteSnapshot(boRoot,bar,bars,boState.configHash)) { BOFailStorage();return; }
   BOObserve(boState.current,boConfig,quoteMs,bid,ask); // Preserve the actual quote clock across history work.
   if(!BORecordCurrent(BO_ANCHOR_EVENT,nowMs))return;
   BOSlotState(boRoot,boSession,boState,boDemoPolicy,nowMs,"CREATED",true);
}
void BOProcess(long nowMs,bool tick,double bid,double ask) {
   if(nowMs<=0 || !boHealthy) return;
   BOResolve(nowMs,tick,bid);
   if(!boHealthy) return;
   if(boState.current.exists && !boState.current.entered) {
      int previousValidation=boState.current.validation,previousReason=boState.current.reason; bool wasCanceled=boState.current.canceled; long previousRetest=boState.current.retestSeenMs;
      if(tick) BOObserve(boState.current,boConfig,nowMs,bid,ask);
      else BOCheckQuoteAge(boState.current,boConfig,nowMs);
      if(previousValidation!=boState.current.validation || wasCanceled!=boState.current.canceled || previousReason!=boState.current.reason || previousRetest!=boState.current.retestSeenMs) {
         boState.current.serial++;
         if(!BORecordCurrent(boState.current.canceled ? BO_CANCEL_EVENT : BO_VALIDATION_EVENT,nowMs)) return;
         if(boState.current.canceled && boState.current.lockedAction!=0) BOManualWarning("CANCELED -> WAIT: "+BOReasonName(boState.current.reason));
      }
      if(!boState.current.locked && nowMs>=BOLockDue(boState.current,boConfig)) {
         BODemoLock(boState.current,boConfig,nowMs,EnableDemoSignals,boState.paused,DemoExpiryMinutes/5,UseValidatedLearning && !IsTesting());
         if(!IsTesting()) BOAdvancedApply(boState.current,nowMs,UseValidatedLearning);
         BOAdvisorFinalize(boState.current,boConfig,nowMs);
         if(!BORecordCurrent(BO_LOCK_EVENT,nowMs)) return;
         // Disk work may consume the remaining clock margin: never publish late.
         if(boState.current.lockedDirection!=0 && BONowMs()>(long)boState.current.targetTime*1000-(boConfig.lockLeadSeconds+boConfig.clockUncertaintySeconds)*1000) {
            BOCancel(boState.current,BO_LOCK_MISSED); if(!BORecordCurrent(BO_CANCEL_EVENT,BONowMs())) return;
         }
         if(boState.current.action!=0 && BOManualPublish(boState.current,boState.sequence,boConfig,EnableAlerts))
            BOAlertChange(BOManualAlertText(boManualLatest));
      }
      if(nowMs>=(long)boState.current.targetTime*1000) {
         bool missed=nowMs>(long)(boState.current.targetTime+boConfig.boundaryLagSeconds)*1000;
         if(tick || missed) {
            int slot=BOFreePending(boState);
            if(slot<0) { BOCancel(boState.current,BO_PENDING_FULL); boState.current.entered=true; BORecordCurrent(BO_WAIT_EVENT,nowMs); }
            else if(missed || !tick || bid<=0 || !MathIsValidNumber(bid)) {
               if(!boState.current.canceled) BOCancel(boState.current,BO_ENTRY_MISSED);
               boState.current.entered=true;
               BOEvent excluded; BOMakeEvent(boState.current,BO_WAIT_EVENT,nowMs,excluded); excluded.reason=BO_ENTRY_MISSED;
               if(!BORecord(excluded)) return;
            } else {
               bool signal=BOEntryAllowed(boState.current,boConfig,nowMs,boState.paused);
               if(!signal) boState.current.action=0;
               BOCaptureEntry(boState.current,nowMs,bid,signal,boState.pending[slot]); boState.current.entered=true;
               if(signal) boState.resumeAt=boState.current.targetTime+boState.current.horizon*300+300;
               BOEvent entry; BOMakeEvent(boState.current,BO_ENTRY_EVENT,nowMs,entry); entry.bid=bid; entry.signal=signal;
               if(!BORecord(entry)) return;
               // Reference entry is recorded regardless of user execution. Hide expired action immediately.
               boState.current.action=0;
            }
         }
      }
   }
   if(tick) BOAttemptAnchor(nowMs,bid,ask);
   else BOSlotObserve(boRoot,boSession,boState,boConfig,boDemoPolicy,nowMs,boAttachBar);
}

// Tester may not deliver Timer events. Replay only a due lock before the new
// tick, using the previously observed quote and the unchanged freshness guard.
// The incoming quote is never visible to this earlier scheduled decision.
void BOReplayTesterLock(long nextMs) {
   if(!IsTesting() || boClockBaseMs<=0 || !boState.current.exists || boState.current.locked ||
      boState.current.entered || boState.current.canceled || !boHealthy) return;
   long due=BOLockDue(boState.current,boConfig),prior=boClockBaseMs;
   if(due<=prior || due>=nextMs) return;
   boClockBaseMs=due;
   string previousDiagnosticTrigger=boDiagTrigger;
   BODiagnosticsTrigger("TESTER_REPLAY_LOCK");
   if(RecordReplayInputs && !CompactTesterLogs && !BORecordReplay("TIMER",due,0,0,0)) {
      BODiagnosticsTrigger(previousDiagnosticTrigger);boClockBaseMs=prior;return;
   }
   BOProcess(due,false,0,0);
   BODiagnosticsTrigger(previousDiagnosticTrigger);
   boClockBaseMs=prior;
}

int OnInit() {
   // This research adapter never initializes on a live/demo chart.
   if(!IsTesting() || IsOptimization() || TradingMode!=Forex || ForexAllowRealTrading || ForexNewsFilter ||
      UseValidatedLearning || EnableBinaryLearningDialogue || BinaryLearningAdviceAffectsSignals || EnableEmbeddedContext ||
      !MathIsValidNumber(ForexResearchMinAtrPips) || ForexResearchMinAtrPips!=3.0 ||
      ForexResearchPostLockGapSeconds<3 || ForexResearchPostLockGapSeconds>30 ||
      !RecordReplayInputs || !RecordClockObservation || StringFind(InstanceTag,"v231_")!=0) {
      Print("V231 RESEARCH: Forex Tester only; ATR3, post-lock gap3-30s, v231_ tag, quote/clock logging ON; Optimization/Real/news/models OFF.");
      return INIT_PARAMETERS_INCORRECT;
   }
   fxResearchPostLockGapSeconds=ForexResearchPostLockGapSeconds;
   boActiveTradingMode=TradingMode;
   if(TradingMode!=BinaryOption && TradingMode!=Forex)return INIT_PARAMETERS_INCORRECT;
   if(!BOChartRolePrepare((int)TradingMode,ForexMagicNumber,InstanceTag)) {
      Print("V228 chart role continuity failed. Preserve EA_MODE_V228 files and restore this chart's previous Forex identity if positions remain.");
      return INIT_FAILED;
   }
   if(FXMode()) {
      FXDashboardConfigure(ForexUseDashboard,PanelFontSize,ActionFontSize,PanelFontName,PanelLeft,PanelTop,BO_EA_RELEASE);
      int initialized=FXInitFromInputs();
      if(initialized!=INIT_SUCCEEDED)return initialized;
      if(!FXResearchRecordConfig()){FXDeinit();return INIT_FAILED;}
      if(!BOChartRoleCommit((int)TradingMode,ForexMagicNumber)){FXDeinit();return INIT_FAILED;}
      BOClockObservationBind(fxRoot,IntegerToString((long)TimeLocal())+"_"+IntegerToString(ChartID()),"Forex",RecordClockObservation);
      return INIT_SUCCEEDED;
   }
   // MQL globals can survive a parameter reinitialization; reset process clocks,
   // input numbering and readiness explicitly for every new session.
   if(IsOptimization()) { Print("Optimization is not a historical training run. Disable Optimization and use a fresh history InstanceTag."); return INIT_PARAMETERS_INCORRECT; }
   BOEmbeddedReset(EnableEmbeddedContext,EmbeddedBrokerClockVerified,EmbeddedBrokerUTCOffsetMinutes);
   if(EnableEmbeddedContext && (!BOEmbeddedOffsetValid(EmbeddedBrokerUTCOffsetMinutes) ||
      EmbeddedBootstrapM5Bars<0 || EmbeddedBootstrapM5Bars>4800 || EmbeddedPanelLeft<0 || EmbeddedPanelTop<0))return INIT_PARAMETERS_INCORRECT;
   boStarted=false; boHealthy=true; boFirstLiveTick=true; boInputSequence=0;
   BODemoReset(); BOAdvancedReset(); BOTesterDashboardReset(); BODiagnosticsReset();
   BOCandidateDiagnosticsReset(); BOContextReset(); BOManualReset();
   BOAdvisorReset(EnableBinaryLearningDialogue,BinaryLearningAdviceAffectsSignals,
      BinaryLearningRequestIntervalSeconds,BinaryLearningReplyMaxAgeSeconds,BinaryLearningReserveBeforeLockSeconds);
   boClockBaseMs=0; boClockMono=0; boLastTickMs=0; BOHistoryReset();BOSlotReset();
   string symbol=Symbol(); StringToUpper(symbol);
   if((IsTesting() && Period()!=PERIOD_M5) || StringFind(symbol,"EURUSD")!=0 || StringFind(symbol,"OTC")>=0 || (Digits!=4 && Digits!=5) ||
      !BOSafeTag(InstanceTag) || !BOSafeTag(Symbol()) || MinimumLockLeadSeconds<30 || MinimumLockLeadSeconds>120 ||
      StringLen(PanelFontName)==0 || PanelFontSize<12 || PanelFontSize>24 || ActionFontSize<PanelFontSize || ActionFontSize>48 || PanelLeft<0 || PanelTop<0 ||
      MaximumAnalysisStartDelaySeconds<1 || MaximumAnalysisStartDelaySeconds>60 || MaximumObservationGapSeconds<3 || MaximumObservationGapSeconds>60) return INIT_PARAMETERS_INCORRECT;
   if(BinaryLearningRequestIntervalSeconds<10 || BinaryLearningRequestIntervalSeconds>60 ||
      BinaryLearningReplyMaxAgeSeconds<5 || BinaryLearningReplyMaxAgeSeconds>60 ||
      BinaryLearningReserveBeforeLockSeconds<3 || BinaryLearningReserveBeforeLockSeconds>15)return INIT_PARAMETERS_INCORRECT;
   if(!RecordReplayInputs) { Print("Publication requires replay input recording."); return INIT_PARAMETERS_INCORRECT; }
   if(DemoExpiryMinutes!=5 && DemoExpiryMinutes!=10 && DemoExpiryMinutes!=15) return INIT_PARAMETERS_INCORRECT;
   boUIAccents=UseVietnameseAccents;
   BOConfigDefaults(boConfig); boConfig.lockLeadSeconds=MinimumLockLeadSeconds;
   boConfig.maximumAnalysisDelaySeconds=MaximumAnalysisStartDelaySeconds;
   boConfig.maximumObservationGapSeconds=MaximumObservationGapSeconds;
   boConfig.allowSR1=AllowSR1 ? 1 : 0; boConfig.allowTP1=AllowTP1 ? 1 : 0; boConfig.allowBR1=AllowBR1 ? 1 : 0;
   boRoot="BO_V2\\"+InstanceTag+(IsTesting() ? "_TESTER_" : "_")+Symbol();
   FolderCreate("BO_V2"); FolderCreate(boRoot);
   boLease=FileOpen(boRoot+"\\instance.lock",FILE_READ|FILE_WRITE|FILE_BIN);
   if(boLease==INVALID_HANDLE) { Print("Another instance or inaccessible storage: ",boRoot); return INIT_FAILED; }
   ZeroMemory(boState); bool found=false;
   if(!BORestore(boRoot,boState,found)) { Print("Invalid latest ledger; do not silently fall back to older state."); return INIT_FAILED; }
   if(IsTesting() && found) { Print("Tester dataset already exists. Use a fresh InstanceTag per historical run."); return INIT_FAILED; }
   uint expectedHash=BOConfigHash(boConfig);
   boSession=IntegerToString((long)TimeLocal())+"_"+IntegerToString((long)GetTickCount())+"_"+IntegerToString(ChartID());
   BOClockObservationBind(boRoot,boSession,"BinaryOption",RecordClockObservation);
   uint expectedFeed=BOHashText(AccountServer()+"|"+Symbol()+"|"+IntegerToString(Digits));
   if(!BOBindOrigin(boRoot,expectedHash,expectedFeed)) { Print("Data origin mismatch; keep Tester and live evidence separate."); return INIT_FAILED; }
   bool mismatch=found && (boState.configHash!=expectedHash || boState.feedHash!=expectedFeed);
   if(mismatch) { Print("V222 config/feed changed: use a new InstanceTag; old evidence is preserved."); return INIT_FAILED; }
   if(found && boState.current.exists && !boState.current.entered) BOCancel(boState.current,BO_RESTART);
   // Old preparations are finished at recovery, even if their entry is still
   // ahead. Do not lock/capture them again or reuse a same-bar snapshot.
   if(found && boState.current.exists && !boState.current.entered) boState.current.entered=true;
   if(boState.current.entered) boState.current.action=0;
   boState.configHash=expectedHash; boState.feedHash=expectedFeed; boState.payout=boConfig.fixedPayoutFraction;
   boState.payoutAsOf=0; // Reserved ledger field; fixed payout has no expiry.
   boAttachBar=iTime(NULL,PERIOD_M5,0);
   boState.lastStarted=(datetime)MathMax((long)boState.lastStarted,(long)boAttachBar);
   if(!BOWriteSessionInfo(boRoot,boSession,BO_EA_RELEASE,boConfig,expectedHash,expectedFeed,ShadowOnly)) {
      Print("Cannot commit session configuration; initialization blocked."); return INIT_FAILED;
   }
   if(!BODemoBindPolicy(boRoot,expectedHash,expectedFeed,DemoExpiryMinutes/5,EnableDemoSignals,UseValidatedLearning)) { Print("Demo policy changed: use a new InstanceTag."); return INIT_FAILED; }
   if(!BOAdvisorBind(boRoot,boSession)) {boAdvisorStorageBad=true;boAdvisorStatus="BRIDGE_IO_ERROR_EA_DECIDES";}
   if(!BOManualRestore(boRoot,boSession)) Print("Manual publication ledger invalid: new manual publications blocked; preserve files.");
   if(!IsTesting()) { BOLearnRefresh(boRoot,(long)TimeCurrent()); BOAdvancedRefresh(boRoot,(long)TimeCurrent()); }
   BOEvent recovery; BOMakeEvent(boState.current,BO_RECOVERY_EVENT,(long)TimeCurrent()*1000,recovery);
   recovery.reason=mismatch ? BO_CONFIG_CHANGED : (found ? BO_RESTART : BO_OK);
   if(!BORecord(recovery)) return INIT_FAILED;
   BORefreshHistory(); if(!boHealthy) return INIT_FAILED;
   if(!IsTesting() && !EventSetTimer(1)) { Print("Required timer unavailable; cannot guarantee early lock."); return INIT_FAILED; }
   Print("BO EA build V2.31 RESEARCH | logic ",BO_LOGIC_VERSION," | config ",expectedHash,
      " | analysis delay ",boConfig.maximumAnalysisDelaySeconds," | observation gap ",boConfig.maximumObservationGapSeconds,
      " | strategies ",boConfig.allowSR1,"/",boConfig.allowTP1,"/",boConfig.allowBR1," | log ",boRoot);
   BOEmbeddedStart(boRoot,boSession,expectedHash,expectedFeed,boDemoPolicy,EmbeddedBootstrapM5Bars);
   if(!BOChartRoleCommit((int)TradingMode,ForexMagicNumber))return INIT_FAILED;
   boStarted=true; BORenderCurrent((long)TimeCurrent()*1000);
   return INIT_SUCCEEDED;
}
void OnTick() {
   if(FXMode()){FXTick();return;}
   if(!boStarted) return;
   if(!boHealthy) { BORenderCurrent(BONowMs());return; }
   MqlTick quote; if(!SymbolInfoTick(Symbol(),quote)) return;
   if(IsTesting()) BOReplayTesterLock((long)quote.time*1000);
   BODiagnosticsTrigger("TICK");
   long nowMs=0;
   if(!BOObservedClockTick(quote.time,nowMs)) {
      if(boState.current.exists && !boState.current.entered) { BOCancel(boState.current,BO_TIME_ANOMALY); BORecordCurrent(BO_CANCEL_EVENT,BONowMs()); }
      return;
   }
   BODiagnosticsTick(nowMs,quote.bid,quote.ask);
   BOContextClockTick(nowMs);
   if(IsTesting()) boTesterTicks++;
   if(boFirstLiveTick) {
      datetime liveBar=iTime(NULL,PERIOD_M5,0);
      if(liveBar<=0 || liveBar!=(datetime)((nowMs/300000)*300)) { BORenderCurrent(nowMs); return; }
      if(boAttachBar<=0 || liveBar==boAttachBar)
         boState.lastStarted=(datetime)MathMax((long)boState.lastStarted,(long)liveBar);
      boFirstLiveTick=false;
   }
   if(RecordReplayInputs && (!IsTesting() || !CompactTesterLogs) && !BORecordReplay("TICK",nowMs,quote.time,quote.bid,quote.ask)) { BORenderCurrent(nowMs);return; }
   BOManualObserve(nowMs,true,quote.bid,quote.ask,boInputSequence,boConfig);
   BOProcess(nowMs,true,quote.bid,quote.ask);
   BOAdvisorPump(boSession,boState,boConfig,BONowMs());
   BORefreshHistory();
   BOEmbeddedPump(boRoot,boSession,boState,boConfig,BONowMs());
   // Only retry the anchor, never replay ENTRY/OUTCOME/LOCK or invent a new tick.
   // Keep the sealed historical sampling schedule and frozen native golden records unchanged.
   if(!IsTesting())BOAttemptAnchor(nowMs,quote.bid,quote.ask);BORenderCurrent(BONowMs());
}
void OnTimer() {
   if(FXMode()){FXTimer();return;}
   if(!boStarted) return;
   if(!boHealthy) { BORenderCurrent(BONowMs());return; }
   BODiagnosticsTrigger("TIMER");
   long nowMs=BONowMs(); if(nowMs<=0) { BORefreshHistory(); BORenderCurrent((long)TimeCurrent()*1000); return; }
   if(RecordReplayInputs && (!IsTesting() || !CompactTesterLogs) && !BORecordReplay("TIMER",nowMs,0,0,0)) { BORenderCurrent(nowMs);return; }
   BOManualObserve(nowMs,false,0,0,0,boConfig);
   BOProcess(nowMs,false,0,0);
   BOAdvisorPump(boSession,boState,boConfig,BONowMs());
   BORefreshHistory();
   BOEmbeddedPump(boRoot,boSession,boState,boConfig,BONowMs());
   BOSlotObserve(boRoot,boSession,boState,boConfig,boDemoPolicy,BONowMs(),boAttachBar);BORenderCurrent(BONowMs());
}
void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam) {
   if(FXMode())return;
   if(id!=CHARTEVENT_OBJECT_CLICK || !boStarted || !boHealthy) return;
   BODiagnosticsTrigger("CHART");
   long nowMs=BONowMs(); if(nowMs<=0) nowMs=(long)TimeCurrent()*1000;
   if(sparam=="BO_V222_PAUSE") {
      boState.paused=!boState.paused;
      if(RecordReplayInputs && (!IsTesting() || !CompactTesterLogs) && !BORecordReplay(boState.paused ? "PAUSE_ON" : "PAUSE_OFF",nowMs,0,0,0)) { BORenderCurrent(nowMs);return; }
      if(boState.paused && boState.current.exists && !boState.current.entered && boState.current.lockedAction!=0) {
         BOCancel(boState.current,BO_PAUSED); BOManualWarning("SIGNAL PAUSED -> WAIT");
      }
      BORecordCurrent(BO_CANCEL_EVENT,nowMs);
   }
   ObjectSetInteger(0,sparam,OBJPROP_STATE,false); BORenderCurrent(nowMs);
}
void OnDeinit(const int reason) {
   if(boActiveTradingMode==Forex){FXDeinit();return;}
   if(IsTesting() && boStarted && boHealthy) {
      long ended=(long)TimeCurrent()*1000;
      if(BORecordCurrent(BO_WAIT_EVENT,ended) && !BOCompleteTester(boRoot,boState.sequence,ended)) Print("Cannot seal Tester dataset; keep logs for diagnosis.");
   }
   BOEmbeddedFinish((long)TimeCurrent()*1000);
   boStarted=false;
   BOEmbeddedDeletePanel();
   EventKillTimer(); BODeletePanel(); Comment("");
   if(boLease!=INVALID_HANDLE) {FileClose(boLease);boLease=INVALID_HANDLE;}
}
