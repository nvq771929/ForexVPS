
#define PERIOD_M1 1
struct MqlRates{datetime time;double open,high,low,close;long tick_volume;int spread;long real_volume;};
bool connected=true,pendingHistory=false,m5Hole=false,m1Hole=false,badM1=false;
int copyRequests=0;
std::vector<long long> copyTimes;
std::vector<MqlRates> history5,history1;
bool IsConnected(){return connected;}
#ifndef BO_TEST_ERRORS
#define BO_TEST_ERRORS
int lastError=0;
void ResetLastError(){lastError=0;}
int GetLastError(){int e=lastError;lastError=0;return e;}
#endif
template<typename T>int ArraySize(const std::vector<T>&a){return a.size();}
template<typename T>bool ArraySetAsSeries(std::vector<T>&,bool){return true;}
int CopyRates(const string&,int period,datetime first,datetime last,std::vector<MqlRates>&out){
  copyRequests++;copyTimes.push_back(fakeNowMs);out.clear();if(pendingHistory){lastError=4066;return -1;}
  auto &source=period==5 ? history5:history1;
  for(auto b:source)if(b.time>=first && b.time<=last){
    bool skip=period==5 ? m5Hole && b.time==history5[10].time : m1Hole && b.time==history1[52].time;
    if(skip)continue;if(period==1 && badM1 && b.time==history1[52].time)b.high=b.low-.1;
    out.push_back(b);
  }return out.size();
}
int CopyRates(const string&s,int period,int,int,std::vector<MqlRates>&out){
  return CopyRates(s,period,datetime(0),TimeCurrent(),out);
}
void addBar(const FakeBar &b){
  history5.push_back({b.time,b.open,b.high,b.low,b.close,b.ticks,0,0});
  for(int k=0;k<5;k++)history1.push_back({b.time+k*60,b.open,b.high,b.low,b.close,k==0 ? b.ticks:0,0,0});
}
