#ifndef BO_V222_CANDIDATE_DIAGNOSTICS
#define BO_V222_CANDIDATE_DIAGNOSTICS
#include "Types.mqh"
// Observer only: never writes BOConfig, candidate or runtime decision state.
bool boCandidateWriteFailed=false;
long boCandidateAnchors=0,boCandidateFormed=0,boCandidateReady=0;
void BOCandidateDiagnosticsReset() {
   boCandidateWriteFailed=false; boCandidateAnchors=0; boCandidateFormed=0; boCandidateReady=0;
}
bool BOCandidateContract(string root,string session,const BORuntimeState &s,const BOConfig &c,uint policy,int horizon) {
   string path=root+"\\candidate_contract_"+session+".csv";
   if(FileIsExist(path))return true;
   int file=FileOpen(path,FILE_WRITE|FILE_CSV|FILE_ANSI,',');if(file==INVALID_HANDLE)return false;
   bool ok=FileWrite(file,"schema","logic","config_hash","feed_hash","policy_hash","horizon",
      "range_net_max_atr","range_efficiency_max","trend_net_min_atr","trend_efficiency_min","expansion_min_atr",
      "breakout_net_min_atr","breakout_efficiency_min","break_atr","reclaim_atr","invalidation_atr","confirmation_location",
      "counter_efficiency","pullback_touch_atr","pullback_minimum_atr","breakout_buffer_atr","retest_band_atr","atr_min_pips","atr_max_pips","shock_atr")>0;
   if(ok)ok=FileWrite(file,1,2026101707,s.configHash,s.feedHash,policy,horizon,
      c.rangeNetMaxATR,c.rangeEfficiencyMax,c.trendNetMinATR,c.trendEfficiencyMin,c.expansionMinATR,
      c.breakoutNetMinATR,c.breakoutEfficiencyMin,c.breakATR,c.reclaimATR,c.invalidationATR,c.confirmationLocation,
      c.counterEfficiency,c.pullbackTouchATR,c.pullbackMinimumATR,c.breakoutBufferATR,c.retestBandATR,c.atrMinPips,c.atrMaxPips,c.shockATR)>0;
   FileFlush(file);FileClose(file);return ok;
}
void BOCandidateDiagnosticsRecord(string root,string session,const BORuntimeState &s,const BOConfig &c,const BOEvent &event,uint policy,int horizon) {
   if(event.kind!=BO_ANCHOR_EVENT && event.kind!=BO_LOCK_EVENT) return;
   if(event.analysisStart!=s.current.analysisStart) return;
   if(!BOCandidateContract(root,session,s,c,policy,horizon)) { boCandidateWriteFailed=true; return; }
   BOAnchor a=s.current.anchor; BOCandidate f=s.current.candidate;
   bool lock=event.kind==BO_LOCK_EVENT;
   bool ready=lock && !s.current.canceled && s.current.validation==BO_CONFIRMED && event.lockedAction!=0 && event.reason==BO_OK;
   if(!lock) { boCandidateAnchors++; if(f.direction!=0) boCandidateFormed++; }
   if(ready) boCandidateReady++;
   int d=(a.regime==BO_ORDERLY_UP || a.regime==BO_EXPANSION_UP) ? 1 :
      ((a.regime==BO_ORDERLY_DOWN || a.regime==BO_EXPANSION_DOWN) ? -1 : 0);
   double atr=a.volatility.atr,z=a.volatility.zoneATR;
   bool srCall=a.structure.support.available && a.triggerLow<a.structure.support.low-c.breakATR*z;
   bool srPut=a.structure.resistance.available && a.triggerHigh>a.structure.resistance.high+c.breakATR*z;
   bool callReclaim=a.structure.support.available && a.triggerClose>a.structure.support.high+c.reclaimATR*z;
   bool putReclaim=a.structure.resistance.available && a.triggerClose<a.structure.resistance.low-c.reclaimATR*z;
   bool location=d>0 ? a.candle.closeLocation>=c.confirmationLocation : (d<0 && a.candle.closeLocation<=1-c.confirmationLocation);
   bool touch=d>0 ? a.triggerLow<=a.baselineFastEMA+c.pullbackTouchATR*z : (d<0 && a.triggerHigh>=a.baselineFastEMA-c.pullbackTouchATR*z);
   bool slow=d>0 ? a.triggerLow>a.baselineSlowEMA-c.invalidationATR*atr : (d<0 && a.triggerHigh<a.baselineSlowEMA+c.invalidationATR*atr);
   double reclaim=a.baselineFastEMA+d*c.reclaimATR*z;
   BOZone prior; ZeroMemory(prior); if(d>0)prior=a.structure.preResistance; else if(d<0)prior=a.structure.preSupport;
   double edge=d>0 ? prior.high : prior.low;
   double breakoutMargin=d && prior.available ? d*(a.triggerClose-edge)-c.breakoutBufferATR*z : 0;
   double pullbackMargin=d ? -c.pullbackMinimumATR-d*a.pullbackNetATR : 0;
   double touchMargin=d>0 ? a.baselineFastEMA+c.pullbackTouchATR*z-a.triggerLow :
      (d<0 ? a.triggerHigh-(a.baselineFastEMA-c.pullbackTouchATR*z) : 0);
   double slowMargin=d>0 ? a.triggerLow-(a.baselineSlowEMA-c.invalidationATR*atr) :
      (d<0 ? a.baselineSlowEMA+c.invalidationATR*atr-a.triggerHigh : 0);
   int file=FileOpen(root+"\\candidate_rules_"+session+".csv",FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
   if(file==INVALID_HANDLE) { boCandidateWriteFailed=true; return; }
   bool ok=true;
   if(FileSize(file)==0) ok=FileWrite(file,"schema","logic","sequence","analysis_start","event_kind","observed_ms","feature_asof_ms","origin",
      "config_hash","feed_hash","policy_hash","horizon","regime","setup","direction","reason","anchor_available","canceled_at_lock","ready_at_lock",
      "atr","zone_atr","atr_min_pips","atr_max_pips","shock_atr","range","efficiency","momentum_net_atr","ema_slope","ema_gap","structure_trend",
      "close_location","overlap","atr_pass","shock_pass","strategy_enabled","sr_call_sweep","sr_call_reclaim","sr_put_sweep","sr_put_reclaim",
      "tp_pullback","tp_touch","tp_slow_held","directional_body","directional_location","tp_reclaim","br_zone_available","br_breakout",
      "retest_seen_at_lock","seconds_since_retest","quote_age_seconds","pullback_margin","touch_margin","slow_margin","reclaim_margin","breakout_margin","location_margin","counterpressure_pass","snapshot_ref",
      "previous_atr","volatility_expansion","prior_close","trigger_close")>0;
   if(!FileSeek(file,0,SEEK_END))ok=false;
   long retestAge=s.current.retestSeenMs>0 && s.current.retestSeenMs<=event.observedMs ? (event.observedMs-s.current.retestSeenMs)/1000 : -1;
   int routed=BORoutedStrategy(a.regime);
   bool enabled=(routed==1 && c.allowSR1!=0) || (routed==2 && c.allowTP1!=0) || (routed==3 && c.allowBR1!=0);
   bool counter=f.direction!=0 ? !(a.momentum.efficiency>=c.counterEfficiency && f.direction*a.momentum.netATR < -1) : false;
   if(ok)ok=FileWrite(file,1,2026101707,s.sequence,IntegerToString((long)event.analysisStart),event.kind,event.observedMs,
      lock ? event.observedMs : (long)a.closeTime*1000,IsTesting() ? "BACKTEST_MT4" : "LIVE_MT4",
      s.configHash,s.feedHash,policy,horizon,a.regime,routed,f.direction,BOReasonName(event.reason),a.available,
      lock && s.current.canceled,ready,DoubleToString(atr,10),DoubleToString(z,10),c.atrMinPips,c.atrMaxPips,c.shockATR,
      DoubleToString(a.candle.range,10),a.momentum.efficiency,a.momentum.netATR,a.baselineFastSlope,a.baselineFastEMA-a.baselineSlowEMA,a.structure.trend,
      a.candle.closeLocation,a.context.overlap,atr>=c.atrMinPips*.0001 && atr<=c.atrMaxPips*.0001,a.candle.range<=c.shockATR*z,enabled,
      srCall,callReclaim,srPut,putReclaim,d!=0 && d*a.pullbackNetATR<=-c.pullbackMinimumATR,touch,slow,
      d!=0 && d*a.candle.body>0,location,d!=0 && d*(a.triggerClose-reclaim)>0,prior.available,d!=0 && prior.available && breakoutMargin>0,
      lock && s.current.retestSeenMs>0,retestAge,s.current.lastQuoteMs>0 ? (event.observedMs-s.current.lastQuoteMs)/1000.0 : -1,
      pullbackMargin,touchMargin,slowMargin,d!=0 ? d*(a.triggerClose-reclaim) : 0,breakoutMargin,
      d>0 ? a.candle.closeLocation-c.confirmationLocation : (d<0 ? 1-c.confirmationLocation-a.candle.closeLocation : 0),counter,
      "anchor_"+IntegerToString((long)event.analysisStart)+".csv",a.volatility.previousATR,a.volatility.expansion,a.priorClose,a.triggerClose)>0;
   FileFlush(file);FileClose(file);if(!ok)boCandidateWriteFailed=true;
}
#endif
