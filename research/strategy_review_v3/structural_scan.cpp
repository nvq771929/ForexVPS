// Read-only extraction of structural invalidations from the frozen native core.
#define STRATEGY_V2_NO_MAIN
#include "../strategy_review_v2/candidate_scan.cpp"

double TPInvalidation(const BOAnchor &a,const BOConfig &c,int d) {
   if(!d)return 0;
   return d>0 ? MathMin(a.triggerLow,a.baselineFastEMA-c.pullbackTouchATR*a.volatility.zoneATR)-c.invalidationATR*a.volatility.atr :
      MathMax(a.triggerHigh,a.baselineFastEMA+c.pullbackTouchATR*a.volatility.zoneATR)+c.invalidationATR*a.volatility.atr;
}
#ifndef STRUCTURAL_SCAN_NO_MAIN
int main() {
   int count;if(!(std::cin>>count))return 2;std::vector<BOBar>bars;BOConfig c{};BOConfigDefaults(c);BOConfig zero=c;zero.atrMinPips=0;
   std::cout<<"anchor,atr,baseline_direction,baseline_inv,no_floor_direction,no_floor_inv,sr_unrouted,sr_inv,tp_unrouted,tp_inv,br_unrouted,br_inv,tp_counterfact_inv,trigger_low,trigger_high\n";
   for(int j=0;j<count;j++) {
      BOBar next{};std::cin>>next.time>>next.open>>next.high>>next.low>>next.close>>next.ticks;if(!std::cin)return 3;
      if(bars.empty() || next.time-bars.back().time!=300)bars.clear();
      if(bars.size()==64) {
         BOAnchor a{};BOBuildMarket(bars,64,c,a);if(!a.available)return 4;
         BOCandidate baseline{},unfiltered{},sr{},tp{},br{};BOFormCandidate(a,c,baseline);BOFormCandidate(a,zero,unfiltered);
         int d=EMADirection(a);BOAnchor forced=a;forced.regime=BO_RANGE;BOFormCandidate(forced,zero,sr);
         if(d) {
            forced.regime=d>0 ? BO_ORDERLY_UP : BO_ORDERLY_DOWN;BOFormCandidate(forced,zero,tp);
            forced.regime=d>0 ? BO_EXPANSION_UP : BO_EXPANSION_DOWN;BOFormCandidate(forced,zero,br);
         }
         double tpInv=TPInvalidation(a,c,d);if(tp.direction && std::abs(tp.invalidation-tpInv)>1e-15)return 5;
         std::cout<<next.time<<","<<std::setprecision(17)<<a.volatility.atr<<","<<baseline.direction<<","<<baseline.invalidation
            <<","<<unfiltered.direction<<","<<unfiltered.invalidation<<","<<sr.direction<<","<<sr.invalidation
            <<","<<tp.direction<<","<<tp.invalidation<<","<<br.direction<<","<<br.invalidation<<","<<tpInv
            <<","<<a.triggerLow<<","<<a.triggerHigh<<"\n";
      }
      bars.push_back(next);if(bars.size()>64)bars.erase(bars.begin());
   }
   return 0;
}
#endif
