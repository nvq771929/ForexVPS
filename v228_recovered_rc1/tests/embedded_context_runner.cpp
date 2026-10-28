// Executes the actual MQL4 numeric observer under a minimal C++ type/math shim.
// It does not emulate the MT4 terminal or constitute a MetaEditor compile.
#include <iostream>
#include <iomanip>
#include <cmath>
#include <cstring>
#include <string>
#include <algorithm>
using string=std::string;
template<typename A,typename B>double MathMax(A a,B b){return std::max(double(a),double(b));}
template<typename A,typename B>double MathMin(A a,B b){return std::min(double(a),double(b));}
double MathAbs(double v){return std::abs(v);}
bool MathIsValidNumber(double v){return std::isfinite(v);}
template<typename T>void ZeroMemory(T &v){std::memset(&v,0,sizeof(v));}
#include "../mt4/Include/EURUSD_M5_V224/EmbeddedContext.mqh"
void fact(const ECFacts &f){
 std::cout<<','<<f.valid;
 if(!f.valid)return;
 std::cout<<','<<f.closeMs<<','<<f.age<<','<<f.count<<','<<f.atr<<','<<f.previousATR
 <<','<<f.ema20<<','<<f.ema50<<','<<f.gap<<','<<f.slope<<','<<f.precedingSlope
 <<','<<f.efficiency<<','<<f.net6<<','<<f.range12<<','<<f.close<<','<<f.vote;
}
void zone(const ECZone &z){
 std::cout<<','<<z.valid;
 if(z.valid)std::cout<<','<<z.low<<','<<z.high<<','<<z.touches<<','<<z.age<<','<<z.knownAtMs;
}
int main(){
 std::cout<<std::setprecision(17);ECState s;ECReset(s);ECBar b;
 while(std::cin>>b.time>>b.open>>b.high>>b.low>>b.close>>b.ticks){
  if(!ECUpdate(s,b)){std::cout<<"REJECT\n";continue;}
  ECSnapshot v=s.snapshot;
  std::cout<<v.asofMs<<','<<v.direction<<','<<v.candidate<<','<<v.volatility<<','<<v.phase
  <<','<<v.flags<<','<<v.startedMs<<','<<v.ageMinutes<<','<<v.pending<<','<<v.pendingCount
  <<','<<v.unsupported<<','<<v.gap<<','<<v.ready<<','<<v.volatilityRatio<<','<<v.m5ATR;
  fact(v.m15);fact(v.h1);fact(v.m5);
  std::cout<<','<<v.zones.known;zone(v.zones.support);zone(v.zones.resistance);std::cout<<'\n';
 }
}
