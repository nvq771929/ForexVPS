#define STRUCTURAL_SCAN_NO_MAIN
#include "../structural_scan.cpp"
double MathFloor(double x){return std::floor(x);}
double MathCeil(double x){return std::ceil(x);}
double NormalizeDouble(double x,int digits){double k=std::pow(10.,digits);return std::round(x*k)/k;}
#include "../frozen/ForexRisk.mqh"
int main(){
   FXSettings s{};s.riskPercent=.5;s.dailyLossPercent=2;s.stopATR=1.5;s.minStopPips=6;s.maxStopPips=30;s.rewardRisk=2;
   s.maxSpreadPips=1.5;s.slippagePips=.3;s.costBufferPips=.5;s.maximumLots=1;s.maxHoldMinutes=60;s.magic=1;
   s.breakEvenR=1;s.breakEvenOffsetPips=.5;s.trailStartR=1.5;s.trailATR=1.5;s.trailMinPips=3;s.trailStepPips=.5;
   s.maxDailyAttempts=6;s.maxLossStreak=3;s.cooldownMinutes=15;s.rolloverStartMinute=1260;s.rolloverEndMinute=1335;s.fridayStopMinute=1200;s.fridayCloseMinute=1230;
   s.newsMaxAgeSeconds=1800;s.newsHighBefore=15;s.newsHighAfter=15;s.newsMediumBefore=10;s.newsMediumAfter=10;s.newsLookaheadMinutes=5;s.newsExitMinutes=5;s.newsReducePercent=50;
   s.initialRiskFraction=1;s.averageTriggerR=.2;s.averageMaxAdverseR=.8;s.averageLotRatio=.5;s.averageWindowMinutes=15;s.minMarginLevelPercent=500;s.minFreeEquityPercent=50;
   if(!FXSettingsValid(s))return 2;
   double entry,atr,invalid;int d;
   while(std::cin>>entry>>d>>atr>>invalid){FXPlan p{};string why;bool ok=FXBuildPlan(s,d,entry,entry,atr,invalid,10000,.00001,1,.01,.01,100,.00001,5,0,p,why);
      std::cout<<ok<<","<<std::setprecision(17)<<p.stop<<","<<p.take<<","<<why<<"\n";}
}
