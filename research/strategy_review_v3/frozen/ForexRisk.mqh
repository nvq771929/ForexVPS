#ifndef FX_V222_RISK
#define FX_V222_RISK
// New Forex contract. Never part of the frozen Binary Option POD or model vector.
enum BOTradingMode { BinaryOption=0, Forex=1 };
struct FXSettings {
   bool enabled; bool allowReal; bool recordQuotes;
   double riskPercent; double dailyLossPercent; double stopATR; double minStopPips;
   double maxStopPips; double rewardRisk; double maxSpreadPips; double slippagePips;
   double costBufferPips; double maximumLots;
   int maxHoldMinutes; int magic;
   bool breakEven; bool trailing; bool emergencyClose; bool schedule; bool closeOnDailyLoss;
   double breakEvenR; double breakEvenOffsetPips; double trailStartR; double trailATR;
   double trailMinPips; double trailStepPips;
   int maxDailyAttempts; int maxLossStreak; int cooldownMinutes;
   int rolloverStartMinute; int rolloverEndMinute; int fridayStopMinute; int fridayCloseMinute;
   bool newsFilter;
   int newsMaxAgeSeconds; int newsHighBefore; int newsHighAfter; int newsMediumBefore; int newsMediumAfter;
   int newsLookaheadMinutes; int newsExitMinutes; int newsHighAction; int newsMediumAction;
   double newsReducePercent;
   bool averaging;
   double initialRiskFraction; double averageTriggerR; double averageMaxAdverseR; double averageLotRatio;
   int averageWindowMinutes;
   double minMarginLevelPercent; double minFreeEquityPercent;
};
struct FXPlan { int direction; double price; double stop; double take; double lots; double plannedRisk; double riskBudget; };
bool FXPositive(double x) { return MathIsValidNumber(x) && x>0; }
bool FXSettingsValid(const FXSettings &s) {
   return FXPositive(s.riskPercent) && s.riskPercent<=2 && FXPositive(s.dailyLossPercent) && s.dailyLossPercent<=10 &&
      FXPositive(s.stopATR) && s.stopATR<=10 && FXPositive(s.minStopPips) && s.minStopPips<=s.maxStopPips &&
      FXPositive(s.maxStopPips) && s.maxStopPips<=100 && FXPositive(s.rewardRisk) && s.rewardRisk<=10 &&
      FXPositive(s.maxSpreadPips) && s.maxSpreadPips<=2 && FXPositive(s.maximumLots) &&
      MathIsValidNumber(s.slippagePips) && s.slippagePips>=0 && s.slippagePips<=2 &&
      MathIsValidNumber(s.costBufferPips) && s.costBufferPips>=0 && s.costBufferPips<=10 &&
      s.maxHoldMinutes>=0 && s.maxHoldMinutes<=1440 && s.magic>0 &&
      FXPositive(s.breakEvenR) && s.breakEvenR<=10 && MathIsValidNumber(s.breakEvenOffsetPips) &&
      s.breakEvenOffsetPips>=0 && s.breakEvenOffsetPips<=10 && FXPositive(s.trailStartR) && s.trailStartR<=10 &&
      FXPositive(s.trailATR) && s.trailATR<=10 && FXPositive(s.trailMinPips) && s.trailMinPips<=100 &&
      FXPositive(s.trailStepPips) && s.trailStepPips<=10 && s.maxDailyAttempts>=1 && s.maxDailyAttempts<=100 &&
      s.maxLossStreak>=1 && s.maxLossStreak<=20 && s.cooldownMinutes>=0 && s.cooldownMinutes<=1440 &&
      s.rolloverStartMinute>=0 && s.rolloverStartMinute<1440 && s.rolloverEndMinute>=0 && s.rolloverEndMinute<1440 &&
      s.fridayStopMinute>=0 && s.fridayStopMinute<=s.fridayCloseMinute && s.fridayCloseMinute<1440 &&
      s.newsMaxAgeSeconds>=60 && s.newsMaxAgeSeconds<=3600 && s.newsHighBefore>=1 && s.newsHighBefore<=120 &&
      s.newsHighAfter>=1 && s.newsHighAfter<=120 && s.newsMediumBefore>=1 && s.newsMediumBefore<=120 &&
      s.newsMediumAfter>=1 && s.newsMediumAfter<=120 && s.newsLookaheadMinutes>=0 && s.newsLookaheadMinutes<=60 &&
      s.newsExitMinutes>=1 && s.newsExitMinutes<=s.newsMediumBefore && s.newsExitMinutes<=s.newsHighBefore &&
      s.newsHighAction>=0 && s.newsHighAction<=2 && s.newsMediumAction>=0 && s.newsMediumAction<=2 &&
      FXPositive(s.newsReducePercent) && s.newsReducePercent<100 &&
      FXPositive(s.initialRiskFraction) && s.initialRiskFraction<=1 && FXPositive(s.averageTriggerR) &&
      s.averageTriggerR<s.averageMaxAdverseR && s.averageMaxAdverseR<1 && FXPositive(s.averageLotRatio) && s.averageLotRatio<=1 &&
      s.averageWindowMinutes>=5 && s.averageWindowMinutes<=60 &&
      FXPositive(s.minMarginLevelPercent) && s.minMarginLevelPercent<=10000 &&
      FXPositive(s.minFreeEquityPercent) && s.minFreeEquityPercent<100;
}
// TickSize is SYMBOL_TRADE_TICK_SIZE in price units, not MODE_TICKSIZE points.
bool FXBuildPlan(const FXSettings &s,int direction,double bid,double ask,double atr,double invalidation,
                 double capital,double tickSize,double tickValue,double minLot,double lotStep,double maxLot,
                 double point,int digits,int stopLevel,FXPlan &p,string &why) {
   ZeroMemory(p); why="INVALID_MARKET_METADATA";
   if(!FXSettingsValid(s) || (direction!=1 && direction!=-1) || !FXPositive(bid) || !FXPositive(ask) || ask<bid ||
      !FXPositive(atr) || !FXPositive(invalidation) || !FXPositive(capital) || !FXPositive(tickSize) ||
      !FXPositive(tickValue) || !FXPositive(minLot) || !FXPositive(lotStep) || !FXPositive(maxLot) ||
      minLot>maxLot || !FXPositive(point) || (digits!=4 && digits!=5) || stopLevel<0) return false;
   if((ask-bid)/.0001>s.maxSpreadPips+1e-8) { why="SPREAD_LIMIT";return false; }
   double price=direction>0 ? ask : bid;
   if(direction*(price-invalidation)<=0) { why="INVALID_STRUCTURAL_STOP";return false; }
   double minDistance=(stopLevel+2)*point+(ask-bid);
   double distance=MathMax(MathAbs(price-invalidation),MathMax(s.stopATR*atr,MathMax(s.minStopPips*.0001,minDistance)));
   double stop=direction>0 ? MathFloor((price-distance)/tickSize+1e-9)*tickSize : MathCeil((price+distance)/tickSize-1e-9)*tickSize;
   stop=NormalizeDouble(stop,digits); distance=MathAbs(price-stop);
   if(!FXPositive(stop) || distance>s.maxStopPips*.0001+1e-10) { why="STOP_TOO_WIDE";return false; }
   double take=direction>0 ? MathCeil((price+distance*s.rewardRisk)/tickSize-1e-9)*tickSize : MathFloor((price-distance*s.rewardRisk)/tickSize+1e-9)*tickSize;
   take=NormalizeDouble(take,digits);
   if(!FXPositive(take) || (direction>0 && (bid-stop<stopLevel*point || take-bid<stopLevel*point)) ||
      (direction<0 && (stop-ask<stopLevel*point || ask-take<stopLevel*point))) { why="BROKER_STOP_DISTANCE";return false; }
   double cash=capital*s.riskPercent/100;
   double riskPerLot=(distance+(s.slippagePips+s.costBufferPips)*.0001)/tickSize*tickValue;
   double lots=MathFloor((MathMin(cash/riskPerLot,MathMin(maxLot,s.maximumLots))+1e-12)/lotStep)*lotStep;
   lots=NormalizeDouble(lots,8);
   if(lots<minLot-1e-10 || !FXPositive(lots)) { why="MIN_LOT_EXCEEDS_RISK";return false; }
   if(lots*riskPerLot>cash+1e-7 || lots>maxLot+1e-10) { why="RISK_ROUNDING";return false; }
   p.direction=direction;p.price=price;p.stop=stop;p.take=take;p.lots=lots;p.plannedRisk=lots*riskPerLot;p.riskBudget=cash;
   why="READY";return true;
}
#endif
