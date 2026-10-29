// Test-only API shim. No terminal, broker or MetaEditor is invoked.
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>
using string=std::string;using datetime=long long;using uint=unsigned int;
#define input
const int FILE_READ=1,FILE_WRITE=2,FILE_BIN=4,FILE_CSV=8,FILE_ANSI=16,FILE_SHARE_READ=32;
const int INIT_SUCCEEDED=0,INIT_FAILED=1,INIT_PARAMETERS_INCORRECT=2,PERIOD_M5=5;
const int ACCOUNT_TRADE_MODE=1,ACCOUNT_TRADE_MODE_DEMO=0,SELECT_BY_POS=1,MODE_HISTORY=2,OP_BUY=0,OP_SELL=1;
const int MODE_TICKVALUE=1,MODE_LOTSIZE=2,MODE_MINLOT=3,MODE_LOTSTEP=4,MODE_MAXLOT=5,MODE_STOPLEVEL=6,MODE_FREEZELEVEL=7,SYMBOL_TRADE_TICK_SIZE=8;
int Digits=5;double Point=.00001;bool testing=false,connected=true,writeFail=false;int accountMode=0,account=100;
uint mono=100;long long utc=1793188800;string symbol="EURUSDz";
struct MqlTick{datetime time;double bid,ask,last;long volume;};
std::map<string,std::vector<string>> files;std::map<int,string> handles;int nextHandle=1;
bool IsTesting(){return testing;}long AccountInfoInteger(int){return accountMode;}int AccountNumber(){return account;}
string AccountServer(){return "Exness-Test";}string AccountCurrency(){return "USD";}string Symbol(){return symbol;}int Period(){return 5;}
long ChartID(){return 123;}uint GetTickCount(){return mono;}datetime TimeGMT(){return utc;}datetime TimeLocal(){return utc+25200;}datetime TimeCurrent(){return utc;}
int StringLen(string s){return s.size();}int StringFind(string s,string q){auto p=s.find(q);return p==string::npos?-1:(int)p;}
int StringGetCharacter(string s,int i){return s.at(i);}string StringSubstr(string s,int i,int n){return s.substr(i,n);}
string IntegerToString(long n){return std::to_string(n);}string DoubleToString(double x,int n){std::ostringstream o;o<<std::fixed<<std::setprecision(n)<<x;return o.str();}
double MathMin(double a,double b){return std::min(a,b);}bool MathIsValidNumber(double x){return std::isfinite(x);}
bool FolderCreate(string){return true;}bool FileIsExist(string s){return files.count(s);}
int FileOpen(string s,int flags,char delimiter=','){if(writeFail)return -1;int h=nextHandle++;handles[h]=s;if(flags&FILE_WRITE)files[s].clear();return h;}
template<typename T>string field(T value){std::ostringstream s;s<<value;string r=s.str();if(r.find_first_of(",\"\n")!=string::npos){string q="\"";for(char c:r){if(c=='\"')q+='\"';q+=c;}r=q+'\"';}return r;}
template<typename...Args>int FileWrite(int h,Args...args){if(writeFail||!handles.count(h))return 0;std::vector<string>v={field(args)...};string r;for(auto &x:v){if(!r.empty())r+=',';r+=x;}files[handles[h]].push_back(r);return r.size()+1;}
void FileFlush(int){}void FileClose(int h){handles.erase(h);}bool EventSetTimer(int){return true;}void EventKillTimer(){}
template<typename...Args>void Print(Args...args){}template<typename...Args>void Comment(Args...args){}
bool IsConnected(){return connected;}bool SymbolInfoTick(string,MqlTick &q){q={utc,1.10010,1.10012,0,0};return true;}
double SymbolInfoDouble(string,int){return .00001;}
double MarketInfo(string,int key){if(key==MODE_LOTSIZE)return 100000;if(key==MODE_TICKVALUE)return 1;if(key==MODE_MINLOT||key==MODE_LOTSTEP)return .01;if(key==MODE_MAXLOT)return 100;return 0;}
datetime iTime(string,int,int shift){return utc/300*300-shift*300;}int iBars(string,int){return 65;}
double iOpen(string,int,int){return 1.1001;}double iHigh(string,int,int){return 1.1002;}double iLow(string,int,int){return 1.1;}double iClose(string,int,int){return 1.1001;}long iVolume(string,int,int){return 100;}
int OrdersHistoryTotal(){return 1;}bool OrderSelect(int,int,int){return true;}string OrderSymbol(){return symbol;}int OrderType(){return OP_BUY;}
datetime OrderCloseTime(){return utc-60;}datetime OrderOpenTime(){return utc-600;}int OrderTicket(){return 1000;}int OrderMagicNumber(){return 2220520;}
double OrderLots(){return .01;}double OrderOpenPrice(){return 1.1;}double OrderClosePrice(){return 1.1002;}double OrderProfit(){return .2;}double OrderCommission(){return -.07;}double OrderSwap(){return 0;}
#include "recorder_under_test.hpp"
int main(int argc,char**argv){
   testing=true;assert(OnInit()==INIT_PARAMETERS_INCORRECT);testing=false;
   accountMode=2;assert(OnInit()==INIT_PARAMETERS_INCORRECT);accountMode=0;
   CaptureTag="../bad";assert(OnInit()==INIT_PARAMETERS_INCORRECT);CaptureTag="research_001";
   assert(OnInit()==INIT_SUCCEEDED);assert(barRows==64);
   mono+=100;OnTick();mono+=100;OnTick();assert(tickRows==2);
   mono+=1000;utc++;OnTimer();assert(heartbeatRows==1 && tickRows==2 && barRows==64);
   OnDeinit(0);assert(!captureStarted);assert(orderRows==1);
   std::filesystem::path output=argv[1];std::filesystem::create_directories(output);
   for(auto &p:files){string filename=p.first.substr(p.first.find_last_of('\\')+1);if(filename.size()<4||filename.substr(filename.size()-4)!=".csv")continue;
      std::ofstream f(output/filename);for(auto &row:p.second)f<<row<<"\n";}
   // Separate sessions prove source changes and failed writes stop tick recording.
   mono+=100;assert(OnInit()==INIT_SUCCEEDED);account=101;OnTick();assert(!captureHealthy && tickRows==0);OnDeinit(0);account=100;
   mono+=100;assert(OnInit()==INIT_SUCCEEDED);writeFail=true;OnTick();assert(!captureHealthy && tickRows==0);writeFail=false;OnDeinit(0);
   // Unsigned rollover preserves relative callback arrival.
   previousMono=UINT32_MAX-5;mono=3;elapsedMs=0;assert(ArrivalMs()==9);
   std::cout<<"collector event/safety/rollover checks passed\n";
}
