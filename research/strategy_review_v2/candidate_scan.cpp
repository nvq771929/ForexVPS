// Research-only observer. The frozen native implementation remains in v1.
#define main frozen_v1_main
#include "../strategy_review_v1/native_scan.cpp"
#undef main

int EMADirection(const BOAnchor &a) {
   if(a.baselineFastEMA>a.baselineSlowEMA && a.baselineFastSlope>0)return 1;
   if(a.baselineFastEMA<a.baselineSlowEMA && a.baselineFastSlope<0)return -1;
   return 0;
}
int TPMask(const BOAnchor &a,const BOConfig &c,int d) {
   if(!d)return 0;
   double z=a.volatility.zoneATR,atr=a.volatility.atr;
   bool pass[6]={
      d*a.pullbackNetATR<=-c.pullbackMinimumATR,
      d>0 ? a.triggerLow<=a.baselineFastEMA+c.pullbackTouchATR*z : a.triggerHigh>=a.baselineFastEMA-c.pullbackTouchATR*z,
      d>0 ? a.triggerLow>a.baselineSlowEMA-c.invalidationATR*atr : a.triggerHigh<a.baselineSlowEMA+c.invalidationATR*atr,
      d*a.candle.body>0,
      d>0 ? a.candle.closeLocation>=c.confirmationLocation : a.candle.closeLocation<=1-c.confirmationLocation,
      d*(a.triggerClose-(a.baselineFastEMA+d*c.reclaimATR*z))>0
   };
   int mask=0;for(int k=0;k<6;k++)if(pass[k])mask|=1<<k;return mask;
}
#ifndef STRATEGY_V2_NO_MAIN
int main() {
   int count;if(!(std::cin>>count))return 2;std::vector<BOBar>bars;
   BOConfig c{};BOConfigDefaults(c);BOConfig zero=c;zero.atrMinPips=0;
   std::cout<<"anchor,config_hash,regime,routed_setup,atr,zone_atr,candle_range,baseline_reason,baseline_direction,no_floor_reason,no_floor_direction,ema_direction,tp_common,tp_mask,sr_unrouted,tp_unrouted,br_unrouted,tp_without_pullback,tp_without_touch,tp_without_slow_hold,tp_without_body,tp_without_location,tp_without_reclaim\n";
   for(int j=0;j<count;j++) {
      BOBar next{};std::cin>>next.time>>next.open>>next.high>>next.low>>next.close>>next.ticks;if(!std::cin)return 3;
      if(bars.empty() || next.time-bars.back().time!=300)bars.clear();
      if(bars.size()==64) {
         BOAnchor a{};BOBuildMarket(bars,64,c,a);if(!a.available)return 4;
         BOCandidate baseline{},unfiltered{};BOFormCandidate(a,c,baseline);BOFormCandidate(a,zero,unfiltered);
         int d=EMADirection(a),mask=TPMask(a,zero,d);
         bool common=d && a.volatility.atr>0 && a.volatility.atr<=zero.atrMaxPips*.0001 &&
            a.candle.range<=zero.shockATR*a.volatility.zoneATR && !a.context.overlap;
         BOAnchor forced=a;BOCandidate sr{},tp{},br{};
         forced.regime=BO_RANGE;BOFormCandidate(forced,zero,sr);
         if(d) {
            forced.regime=d>0 ? BO_ORDERLY_UP : BO_ORDERLY_DOWN;BOFormCandidate(forced,zero,tp);
            forced.regime=d>0 ? BO_EXPANSION_UP : BO_EXPANSION_DOWN;BOFormCandidate(forced,zero,br);
         }
         if(tp.direction!=(common && mask==63 ? d : 0))return 5;
         std::cout<<next.time<<","<<BOConfigHash(c)<<","<<a.regime<<","<<baseline.setup<<","<<std::setprecision(17)
            <<a.volatility.atr<<","<<a.volatility.zoneATR<<","<<a.candle.range<<","<<BOReasonName(baseline.reason)<<","<<baseline.direction
            <<","<<BOReasonName(unfiltered.reason)<<","<<unfiltered.direction<<","<<d<<","<<common<<","<<mask
            <<","<<sr.direction<<","<<tp.direction<<","<<br.direction;
         for(int k=0;k<6;k++)std::cout<<","<<(common && (mask|(1<<k))==63 ? d : 0);
         std::cout<<"\n";
      }
      bars.push_back(next);if(bars.size()>64)bars.erase(bars.begin());
   }
   return 0;
}
#endif
