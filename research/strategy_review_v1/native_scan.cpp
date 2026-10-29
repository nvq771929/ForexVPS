// Test-only MT4 API shim for executing the actual adapter under C++.
// It is not a native compiler, terminal emulator or production dependency.
#include <algorithm>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <regex>
#include <sstream>
#include <string>
#include <vector>
#include <ctime>
using string=std::string;
using datetime=long long;
using uint=unsigned int;
using uchar=unsigned char;
using ushort=unsigned short;
using color=int;
#define input
#define INVALID_HANDLE -1
#define FILE_READ 1
#define FILE_WRITE 2
#define FILE_BIN 4
#define FILE_CSV 8
#define FILE_ANSI 16
#define FILE_SHARE_READ 32
#define CHAR_VALUE 1
#define INT_VALUE 4
#define SEEK_SET 0
#define SEEK_CUR 1
#define SEEK_END 2
#define PERIOD_M5 5
#define TERMINAL_BUILD 1
#define TIME_DATE 1
#define TIME_SECONDS 2
#define OBJ_BUTTON 1
#define OBJ_LABEL 2
#define OBJ_RECTANGLE_LABEL 3
#define OBJPROP_CORNER 1
#define OBJPROP_XDISTANCE 2
#define OBJPROP_YDISTANCE 3
#define OBJPROP_XSIZE 4
#define OBJPROP_YSIZE 5
#define OBJPROP_TEXT 6
#define OBJPROP_STATE 7
#define OBJPROP_ANCHOR 8
#define OBJPROP_FONTSIZE 9
#define OBJPROP_COLOR 10
#define OBJPROP_SELECTABLE 11
#define OBJPROP_HIDDEN 12
#define OBJPROP_BACK 13
#define OBJPROP_ZORDER 14
#define OBJPROP_FONT 15
#define OBJPROP_BGCOLOR 16
#define OBJPROP_BORDER_COLOR 17
#define OBJPROP_BORDER_TYPE 18
#define BORDER_FLAT 0
#define CORNER_LEFT_UPPER 0
#define ANCHOR_LEFT_UPPER 0
#define clrWhiteSmoke 0xf5f5f5
#define clrSilver 0xc0c0c0
#define clrDeepSkyBlue 0xffbf00
#define clrLimeGreen 0x32cd32
#define clrTomato 0x4763ff
#define clrAqua 0xffff00
#define clrGold 0x00d7ff
#define clrDarkSlateGray 0x4f4f2f
#define clrSlateGray 0x908070
#define CORNER_RIGHT_UPPER 1
#define CHARTEVENT_OBJECT_CLICK 1
#define INIT_PARAMETERS_INCORRECT 2
#define INIT_FAILED 1
#define INIT_SUCCEEDED 0
int Digits=5;
int fakePeriod=5;
long long fakeNowMs=0;
double fakeBid=1.1002,fakeAsk=1.1003;
string filesRoot,latestComment;
std::map<std::pair<string,int>,string> objectStrings;
template<typename A,typename B> double MathMax(A a,B b){return std::max(double(a),double(b));}
template<typename A,typename B> double MathMin(A a,B b){return std::min(double(a),double(b));}
double MathAbs(double x){return std::abs(x);}
bool MathIsValidNumber(double x){return std::isfinite(x);}
template<typename T>void ZeroMemory(T &x){std::memset(&x,0,sizeof(x));}
template<typename T>int ArrayResize(std::vector<T>&x,int n){x.resize(n);return n;}
string DoubleToString(double x,int n){std::ostringstream s;s<<std::fixed<<std::setprecision(n)<<x;return s.str();}
string IntegerToString(long long x){return std::to_string(x);}
string ShortToString(ushort code){
   if(code<128)return string(1,char(code));
   if(code<2048)return string(1,char(0xc0|(code>>6)))+char(0x80|(code&63));
   return string(1,char(0xe0|(code>>12)))+char(0x80|((code>>6)&63))+char(0x80|(code&63));
}
int StringLen(const string&s){return s.size();}
int StringGetCharacter(const string&s,int i){return (uchar)s.at(i);}
int StringFind(const string&s,const string&p){auto n=s.find(p);return n==string::npos ? -1:int(n);}
string StringSubstr(const string&s,int start,int length=-1){return s.substr(start,length<0 ? string::npos:length);}
int StringSplit(const string&s,ushort delimiter,std::vector<string>&out){
 out.clear();size_t start=0;while(true){auto end=s.find(char(delimiter),start);
 out.push_back(s.substr(start,end==string::npos ? string::npos:end-start));
 if(end==string::npos)break;start=end+1;}return int(out.size());
}
int StringReplace(string&s,const string&from,const string&to){int count=0;size_t n=0;while((n=s.find(from,n))!=string::npos){s.replace(n,from.size(),to);n+=to.size();count++;}return count;}
bool StringToUpper(string&s){for(auto&c:s)c=std::toupper((uchar)c);return true;}
long long StringToInteger(const string&s){try{return std::stoll(s);}catch(...){return 0;}}
double StringToDouble(const string&s){try{return std::stod(s);}catch(...){return 0;}}
string StringFormat(const string&fmt,long long x){if(fmt.find("012")!=string::npos){std::ostringstream s;s<<std::setw(12)<<std::setfill('0')<<x;return s.str();}return std::to_string(x);}
string fakeSymbol="EURUSD";string Symbol(){return fakeSymbol;}
string fakeServer="FIXTURE_FEED";string AccountServer(){return fakeServer;}
int Period(){return fakePeriod;}
long long TerminalInfoInteger(int){return 1440;}
long long fakeChartID=123;long long ChartID(){return fakeChartID;}
uint GetTickCount(){return uint(fakeNowMs%4294967296LL);}
datetime TimeCurrent(){return fakeNowMs/1000;}
datetime TimeLocal(){return TimeCurrent()+25200;}
string TimeToString(datetime t,int flags){time_t time=t;tm parts=*std::gmtime(&time);char buffer[64];std::strftime(buffer,sizeof(buffer),flags==TIME_DATE ? "%Y.%m.%d":flags==TIME_SECONDS ? "%H:%M:%S":"%Y.%m.%d %H:%M:%S",&parts);return buffer;}
template<typename...A>void Print(A...){ }
std::vector<string>alertTexts;void Alert(const string&text){alertTexts.push_back(text);}
void Comment(const string&s){latestComment=s;}
bool EventSetTimer(int){return true;}
void EventKillTimer(){ }
void ChartRedraw(long long){ }
int ObjectFind(long long,const string&){return -1;}
template<typename...A>bool ObjectCreate(A...){return true;}
std::map<std::pair<string,int>,long long> objectIntegers;
template<typename T>bool ObjectSetInteger(long long,const string&name,int property,T value){objectIntegers[{name,property}]=(long long)value;return true;}
bool ObjectSetString(long long,const string&name,int property,const string&value){objectStrings[{name,property}]=value;return true;}
string ObjectGetString(long long,const string&name,int property){return objectStrings[{name,property}];}
bool ObjectDelete(long long,const string&){return true;}
int fakeQuoteAgeSeconds=0;
struct MqlTick{datetime time;double bid;double ask;double last;unsigned long long volume;};
bool SymbolInfoTick(const string&,MqlTick&q){q.time=TimeCurrent()-fakeQuoteAgeSeconds;q.bid=fakeBid;q.ask=fakeAsk;return true;}
struct FakeBar{long long time;double open,high,low,close;long ticks;};
std::vector<FakeBar> closedBars;
int iBars(int,int){return closedBars.size()+1;}
datetime iTime(int,int,int shift){if(shift==0)return TimeCurrent()/300*300;return closedBars.at(closedBars.size()-shift).time;}
double iOpen(int,int,int shift){return closedBars.at(closedBars.size()-shift).open;}
double iHigh(int,int,int shift){return closedBars.at(closedBars.size()-shift).high;}
double iLow(int,int,int shift){return closedBars.at(closedBars.size()-shift).low;}
double iClose(int,int,int shift){return closedBars.at(closedBars.size()-shift).close;}
long iVolume(int,int,int shift){return closedBars.at(closedBars.size()-shift).ticks;}
string nativePath(string path){StringReplace(path,"\\","/");return filesRoot+"/"+path;}
bool FolderCreate(const string&p){return std::filesystem::create_directories(nativePath(p)) || std::filesystem::exists(nativePath(p));}
struct FakeFile{string path;int flags;std::fstream stream;std::vector<std::vector<string>>csv;size_t row=0,col=0;bool lineEnd=false;};
std::map<int,FakeFile> handles;int nextHandle=10;
#define BO_TEST_ERRORS
bool fakeManualWriteFailure=false;long long fakeManualSaveDelayMs=0,fakeSaveElapsedMs=0;
int lastError=0;bool fakeFailReplayOnce=false;bool fakeExternalReplayReader=false;
void ResetLastError(){lastError=0;}
int GetLastError(){int error=lastError;lastError=0;return error;}
bool fakeFXWriteFailure=false;long long fakeFXStorageDelayMs=0;
int FileOpen(const string&p,int flags,char delimiter=','){
   if(p.find("FX_V222")!=string::npos && (flags&FILE_WRITE)){if(fakeFXWriteFailure)return -1;fakeNowMs+=fakeFXStorageDelayMs;fakeFXStorageDelayMs=0;}
   if(fakeManualWriteFailure && p.find("manual_v218_")!=string::npos && (flags&FILE_WRITE))return -1;
   if(p.find("input_")!=string::npos && ((fakeExternalReplayReader && !(flags&FILE_SHARE_READ)) || fakeFailReplayOnce)){
      lastError=5004;fakeFailReplayOnce=false;return -1;
   }
   string path=nativePath(p);for(auto &[_,f]:handles)if(f.path==path)return -1;
   if(!(flags&FILE_WRITE)&&!std::filesystem::exists(path))return -1;
   std::filesystem::create_directories(std::filesystem::path(path).parent_path());
   if((flags&FILE_WRITE)&&!std::filesystem::exists(path)){std::ofstream create(path,std::ios::binary);}
   auto mode=std::ios::binary;
   if(flags&FILE_READ)mode|=std::ios::in;
   if(flags&FILE_WRITE)mode|=std::ios::out;
   if((flags&FILE_WRITE)&&!(flags&FILE_READ))mode|=std::ios::trunc;
   int id=nextHandle++;auto &f=handles[id];f.path=path;f.flags=flags;f.stream.open(path,mode);
   if(!f.stream){handles.erase(id);return -1;}
   if((flags&FILE_CSV)&&!(flags&FILE_WRITE)){
      string line;while(std::getline(f.stream,line)){if(!line.empty()&&line.back()=='\r')line.pop_back();std::vector<string>cells;std::stringstream s(line);string cell;while(std::getline(s,cell,delimiter))cells.push_back(cell);f.csv.push_back(cells);}f.stream.clear();f.stream.seekg(0);
   }
   return id;
}
void FileClose(int h){handles.at(h).stream.close();handles.erase(h);}
void FileFlush(int h){handles.at(h).stream.flush();}
unsigned long long FileSize(int h){auto &f=handles.at(h);f.stream.flush();return std::filesystem::file_size(f.path);}
bool FileSeek(int h,long long offset,int origin){auto &s=handles.at(h).stream;s.clear();auto dir=origin==0 ? std::ios::beg:origin==2 ? std::ios::end:std::ios::cur;s.seekg(offset,dir);s.seekp(offset,dir);return bool(s);}
int FileWriteInteger(int h,int value,int size=4){auto &s=handles.at(h).stream;if(size==1){char c=value;s.write(&c,1);}else{s.write(reinterpret_cast<char*>(&value),4);}return s ? size:0;}
int FileReadInteger(int h,int size=4){auto &s=handles.at(h).stream;int value=0;if(size==1){signed char c=0;s.read(reinterpret_cast<char*>(&c),1);value=c;}else{s.read(reinterpret_cast<char*>(&value),4);}return value;}
template<typename T>int FileWriteStruct(int h,const T&x){auto&s=handles.at(h).stream;s.write(reinterpret_cast<const char*>(&x),sizeof(x));return s ? sizeof(x):0;}
template<typename T>int FileReadStruct(int h,T&x){auto&s=handles.at(h).stream;s.read(reinterpret_cast<char*>(&x),sizeof(x));return s ? sizeof(x):0;}
bool FileDelete(const string&p){std::error_code ec;return std::filesystem::remove(nativePath(p),ec);}
bool FileIsExist(const string&p){return std::filesystem::exists(nativePath(p));}
bool FileMove(const string&from,int,const string&to,int){if(from.find("manual_v218_1_")!=string::npos){fakeNowMs+=fakeManualSaveDelayMs;fakeSaveElapsedMs+=fakeManualSaveDelayMs;fakeManualSaveDelayMs=0;}string a=nativePath(from),b=nativePath(to);if(std::filesystem::exists(b))return false;std::error_code ec;std::filesystem::rename(a,b,ec);return !ec;}
bool FileIsEnding(int h){auto&f=handles.at(h);return f.row>=f.csv.size();}
bool FileIsLineEnding(int h){return handles.at(h).lineEnd;}
string FileReadString(int h){auto&f=handles.at(h);f.lineEnd=false;if(f.row>=f.csv.size())return "";string result=f.csv[f.row].at(f.col++);if(f.col>=f.csv[f.row].size()){f.row++;f.col=0;f.lineEnd=true;}return result;}
template<typename T>string cellString(T value){std::ostringstream s;s<<std::setprecision(16)<<value;return s.str();}
template<typename...A>uint FileWrite(int h,A...args){static_assert(sizeof...(A)<=62,"MQL4 FileWrite argument cap");auto &s=handles.at(h).stream;std::vector<string>cells={cellString(args)...};string line;for(size_t i=0;i<cells.size();i++){if(i)line+=',';line+=cells[i];}line+='\n';s<<line;return s ? line.size():0;}
struct Search{std::vector<string>names;size_t index=0;};std::map<long long,Search>searches;long long nextSearch=100;
long long FileFindFirst(string pattern,string&name){string full=nativePath(pattern);auto parent=std::filesystem::path(full).parent_path();string mask=std::filesystem::path(full).filename().string();string regex="^";for(char c:mask){if(c=='*')regex+=".*";else if(c=='.')regex+="\\.";else regex+=c;}regex+="$";Search search;
   if(std::filesystem::exists(parent))for(auto&f:std::filesystem::directory_iterator(parent))if(std::regex_match(f.path().filename().string(),std::regex(regex)))search.names.push_back(f.path().filename().string());
   std::sort(search.names.begin(),search.names.end());if(search.names.empty())return -1;long long id=nextSearch++;name=search.names[0];search.index=1;searches[id]=search;return id;
}
bool FileFindNext(long long h,string&name){auto&s=searches.at(h);if(s.index>=s.names.size())return false;name=s.names[s.index++];return true;}
void FileFindClose(long long h){searches.erase(h);}

long fakeBrokerUTCOffset=0,fakePCUTCJumpSeconds=0;datetime TimeGMT(){return TimeCurrent()-fakeBrokerUTCOffset+fakePCUTCJumpSeconds;}
#ifndef BO_V222_MARKET
#define BO_V222_MARKET
#ifndef BO_V222_CANDLE
#define BO_V222_CANDLE
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

void BOCandleFacts(const BOBar &b, BOCandle &out) {
   out.range=b.high-b.low; out.body=b.close-b.open;
   out.upperWick=b.high-MathMax(b.open,b.close); out.lowerWick=MathMin(b.open,b.close)-b.low;
   out.closeLocation=out.range>0 ? (b.close-b.low)/out.range : .5;
}
#endif

#ifndef BO_V222_VOLATILITY
#define BO_V222_VOLATILITY

double BOATR(const std::vector<BOBar> &b, int end, int count) {
   double sum=0;
   for(int i=end-count+1;i<=end;i++)
      sum+=MathMax(b[i].high-b[i].low,MathMax(MathAbs(b[i].high-b[i-1].close),MathAbs(b[i].low-b[i-1].close)));
   return sum/count;
}
void BOVolatilityFacts(const std::vector<BOBar> &b, BOVolatility &v) {
   v.atr=BOATR(b,BO_HISTORY-1,14); v.zoneATR=BOATR(b,BO_HISTORY-2,14);
   v.previousATR=BOATR(b,BO_HISTORY-15,14);
   v.expansion=v.zoneATR>0 ? (b[BO_HISTORY-1].high-b[BO_HISTORY-1].low)/v.zoneATR : 0;
}
#endif

#ifndef BO_V222_MOMENTUM
#define BO_V222_MOMENTUM

void BOMomentumFacts(const std::vector<BOBar> &b, double atr, BOMomentum &m) {
   int end=BO_HISTORY-1; double net=b[end].close-b[end-12].close, travel=0;
   for(int i=end-11;i<=end;i++) travel+=MathAbs(b[i].close-b[i-1].close);
   m.netATR=atr>0 ? net/atr : 0; m.efficiency=travel>0 ? MathAbs(net)/travel : 0;
   m.acceleration=atr>0 ? ((b[end].close-b[end-3].close)-(b[end-3].close-b[end-6].close))/atr : 0;
}
#endif

#ifndef BO_V222_STRUCTURE
#define BO_V222_STRUCTURE

void BOEmptyZone(BOZone &z) { z.available=false; z.low=0; z.high=0; z.touches=0; z.age=0; z.knownAt=0; }
void BOFindStructure(const std::vector<BOBar> &b, const BOConfig &c, double atr, BOStructure &s) {
   BOPivot lows[BO_MAX_PIVOTS], highs[BO_MAX_PIVOTS];
   ZeroMemory(lows); ZeroMemory(highs);
   int nl=0,nh=0;
   int end=BO_HISTORY-2;
   for(int i=c.swingRadius;i<=end-c.swingRadius;i++) {
      bool low=true,high=true;
      for(int k=1;k<=c.swingRadius;k++) {
         // Strict to the left, non-strict to the right: earliest pivot owns a flat extreme.
         if(b[i].low>=b[i-k].low || b[i].low>b[i+k].low) low=false;
         if(b[i].high<=b[i-k].high || b[i].high<b[i+k].high) high=false;
      }
      if(low) { lows[nl].price=b[i].low; lows[nl].index=i; lows[nl].kind=-1; nl++; }
      if(high) { highs[nh].price=b[i].high; highs[nh].index=i; highs[nh].kind=1; nh++; }
   }
   s.lowCount=nl; s.highCount=nh; s.trend=(nl>=2 && nh>=2) ? 0 : 2; // UNKNOWN is distinct from neutral.
   if(nl>=2 && nh>=2) {
      if(lows[nl-1].price>lows[nl-2].price && highs[nh-1].price>highs[nh-2].price) s.trend=1;
      else if(lows[nl-1].price<lows[nl-2].price && highs[nh-1].price<highs[nh-2].price) s.trend=-1;
   }
   BOEmptyZone(s.support); BOEmptyZone(s.resistance); BOEmptyZone(s.preSupport); BOEmptyZone(s.preResistance);
   double reference=b[BO_HISTORY-1].close;
   if(atr<=0) return;
   for(int side=0;side<2;side++) {
      int count=side==0 ? nl : nh;
      for(int seed=0;seed<count;seed++) {
         int seedIndex=side==0 ? lows[seed].index : highs[seed].index;
         if(end-seedIndex>c.maximumZoneAge) continue;
         double seedPrice=side==0 ? lows[seed].price : highs[seed].price;
         BOZone zone; BOEmptyZone(zone); zone.low=seedPrice; zone.high=seedPrice;
         int newest=-1;
         for(int j=0;j<count;j++) {
            double p=side==0 ? lows[j].price : highs[j].price;
            int index=side==0 ? lows[j].index : highs[j].index;
            if(end-index>c.maximumZoneAge || MathAbs(p-seedPrice)>c.clusterATR*atr) continue;
            zone.low=MathMin(zone.low,p); zone.high=MathMax(zone.high,p); zone.touches++;
            newest=(int)MathMax(newest,index);
         }
         if(zone.touches<c.minimumTouches || zone.high-zone.low>c.maxZoneATR*atr) continue;
         double padding=MathMax(0,c.minZoneATR*atr-(zone.high-zone.low))/2;
         zone.low-=padding; zone.high+=padding; zone.available=true;
         zone.age=end-newest; zone.knownAt=b[newest+c.swingRadius].time+300;
         if(side==0 && zone.high<reference && (!s.support.available || zone.high>s.support.high)) s.support=zone;
         if(side==1 && zone.low>reference && (!s.resistance.available || zone.low<s.resistance.low)) s.resistance=zone;
         double previous=b[BO_HISTORY-2].close;
         if(side==0 && zone.high<previous && (!s.preSupport.available || zone.high>s.preSupport.high)) s.preSupport=zone;
         if(side==1 && zone.low>previous && (!s.preResistance.available || zone.low<s.preResistance.low)) s.preResistance=zone;
      }
   }
}
#endif

#ifndef BO_V222_CONTEXT
#define BO_V222_CONTEXT

void BOContextFacts(const BOStructure &s, double price, double atr, BOContext &x) {
   x.supportDistanceATR=s.support.available && atr>0 ? (price-s.support.high)/atr : -1;
   x.resistanceDistanceATR=s.resistance.available && atr>0 ? (s.resistance.low-price)/atr : -1;
   x.overlap=s.support.available && s.resistance.available && s.support.high>=s.resistance.low;
}
#endif

#ifndef BO_V222_REGIME
#define BO_V222_REGIME

int BOClassifyRegime(const BOAnchor &a,const BOConfig &c) {
   if(a.volatility.atr<=0) return BO_REGIME_UNKNOWN;
   if(a.volatility.previousATR>0 && a.volatility.atr/a.volatility.previousATR<.75) return BO_COMPRESSION;
   if(a.volatility.expansion>=c.expansionMinATR && a.momentum.efficiency>=c.breakoutEfficiencyMin) {
      if(a.structure.preResistance.available && a.candle.body>0 && a.momentum.netATR>=c.breakoutNetMinATR &&
         a.priorClose<=a.structure.preResistance.high && a.triggerClose>a.structure.preResistance.high+c.breakoutBufferATR*a.volatility.zoneATR) return BO_EXPANSION_UP;
      if(a.structure.preSupport.available && a.candle.body<0 && a.momentum.netATR<=-c.breakoutNetMinATR &&
         a.priorClose>=a.structure.preSupport.low && a.triggerClose<a.structure.preSupport.low-c.breakoutBufferATR*a.volatility.zoneATR) return BO_EXPANSION_DOWN;
   }
   if(a.structure.trend==2) return BO_REGIME_UNKNOWN;
   if(a.structure.trend>0 && a.momentum.netATR>=c.trendNetMinATR && a.momentum.efficiency>=c.trendEfficiencyMin &&
      a.baselineFastEMA>a.baselineSlowEMA && a.baselineFastSlope>0) return BO_ORDERLY_UP;
   if(a.structure.trend<0 && a.momentum.netATR<=-c.trendNetMinATR && a.momentum.efficiency>=c.trendEfficiencyMin &&
      a.baselineFastEMA<a.baselineSlowEMA && a.baselineFastSlope<0) return BO_ORDERLY_DOWN;
   if(a.structure.trend==0 && MathAbs(a.momentum.netATR)<c.rangeNetMaxATR && a.momentum.efficiency<c.rangeEfficiencyMax) return BO_RANGE;
   return BO_TRANSITION;
}
#endif

#ifndef BO_V2_TREND
#define BO_V2_TREND

double BOEMA(const std::vector<BOBar> &b,int end,int period) {
   double value=0; for(int i=0;i<period;i++) value+=b[i].close;
   value/=period; double alpha=2.0/(period+1);
   for(int i=period;i<=end;i++) value=alpha*b[i].close+(1-alpha)*value;
   return value;
}
void BOTrendFacts(const std::vector<BOBar> &b,BOAnchor &a) {
   a.priorClose=b[BO_HISTORY-2].close;
   a.fastEMA=BOEMA(b,63,20); a.slowEMA=BOEMA(b,63,50);
   a.baselineFastEMA=BOEMA(b,62,20); a.baselineSlowEMA=BOEMA(b,62,50);
   a.baselineFastSlope=a.baselineFastEMA-BOEMA(b,59,20);
   a.pullbackNetATR=(b[62].close-b[59].close)/a.volatility.zoneATR;
}
#endif

void BOBuildMarket(const std::vector<BOBar> &b, int count, const BOConfig &c, BOAnchor &a) {
   ZeroMemory(a);
   a.candle.closeLocation=.5; a.structure.trend=2;
   a.context.supportDistanceATR=-1; a.context.resistanceDistanceATR=-1;
   a.available=false; a.reason=BO_HISTORY_SHORT;
   if(count!=BO_HISTORY) return;
   for(int i=0;i<count;i++) {
      if(!MathIsValidNumber(b[i].open) || !MathIsValidNumber(b[i].high) || !MathIsValidNumber(b[i].low) || !MathIsValidNumber(b[i].close) ||
         b[i].low<=0 || b[i].low>MathMin(b[i].open,b[i].close) || b[i].high<MathMax(b[i].open,b[i].close) || b[i].time%300!=0) {
         a.reason=BO_BAD_OHLC; return;
      }
      if(i>0 && b[i].time-b[i-1].time!=300) { a.reason=BO_HISTORY_GAP; return; }
   }
   a.closeTime=b[count-1].time+300; a.triggerLow=b[count-1].low; a.triggerHigh=b[count-1].high; a.triggerClose=b[count-1].close;
   BOCandleFacts(b[count-1],a.candle); BOVolatilityFacts(b,a.volatility);
   if(a.volatility.atr<=0 || a.volatility.zoneATR<=0) { a.reason=BO_VOLATILITY_RESEARCH; return; }
   BOMomentumFacts(b,a.volatility.atr,a.momentum); BOFindStructure(b,c,a.volatility.zoneATR,a.structure);
   BOContextFacts(a.structure,a.triggerClose,a.volatility.atr,a.context);
   BOTrendFacts(b,a); a.regime=BOClassifyRegime(a,c); a.available=true; a.reason=BO_OK;
}
#endif
#ifndef BO_V222_FORECAST
#define BO_V222_FORECAST

void BOFormCandidate(const BOAnchor &a,const BOConfig &c,BOCandidate &f) {
   ZeroMemory(f); f.reason=BO_NO_SETUP;
   if(!a.available) { f.reason=a.reason; return; }
   f.setup=BORoutedStrategy(a.regime);
   double atr=a.volatility.atr,zatr=a.volatility.zoneATR;
   if(atr<c.atrMinPips*.0001 || atr>c.atrMaxPips*.0001 || a.candle.range>c.shockATR*zatr) { f.reason=BO_VOLATILITY_RESEARCH; return; }
   if(f.setup==0) { f.reason=BO_CONTEXT_UNSUPPORTED; return; }
   if((f.setup==1 && c.allowSR1==0) || (f.setup==2 && c.allowTP1==0) || (f.setup==3 && c.allowBR1==0)) { f.reason=BO_STRATEGY_DISABLED; return; }
   if(a.context.overlap) { f.reason=BO_AMBIGUOUS; return; }
   int d=0;
   if(f.setup==1) {
      bool call=a.structure.support.available && a.triggerLow<a.structure.support.low-c.breakATR*zatr &&
         a.triggerClose>a.structure.support.high+c.reclaimATR*zatr && a.candle.closeLocation>=c.confirmationLocation;
      bool put=a.structure.resistance.available && a.triggerHigh>a.structure.resistance.high+c.breakATR*zatr &&
         a.triggerClose<a.structure.resistance.low-c.reclaimATR*zatr && a.candle.closeLocation<=1-c.confirmationLocation;
      if(call && put) { f.reason=BO_AMBIGUOUS; return; }
      if(!call && !put) { f.reason=(!a.structure.support.available && !a.structure.resistance.available) ? BO_ZONE_UNKNOWN : BO_NO_SETUP; return; }
      d=call ? 1 : -1;
      if(a.momentum.efficiency>=c.counterEfficiency && d*a.momentum.netATR < -1) { f.reason=BO_COUNTERPRESSURE; return; }
      f.invalidation=call ? MathMin(a.triggerLow,a.structure.support.low)-c.invalidationATR*atr : MathMax(a.triggerHigh,a.structure.resistance.high)+c.invalidationATR*atr;
      f.confirmation=call ? a.structure.support.high+c.reclaimATR*zatr : a.structure.resistance.low-c.reclaimATR*zatr;
   } else {
      d=(a.regime==BO_ORDERLY_UP || a.regime==BO_EXPANSION_UP) ? 1 : -1;
      bool location=d>0 ? a.candle.closeLocation>=c.confirmationLocation : a.candle.closeLocation<=1-c.confirmationLocation;
      if(f.setup==2) {
         bool touched=d>0 ? a.triggerLow<=a.baselineFastEMA+c.pullbackTouchATR*zatr : a.triggerHigh>=a.baselineFastEMA-c.pullbackTouchATR*zatr;
         bool slowHeld=d>0 ? a.triggerLow>a.baselineSlowEMA-c.invalidationATR*atr : a.triggerHigh<a.baselineSlowEMA+c.invalidationATR*atr;
         double confirmation=a.baselineFastEMA+d*c.reclaimATR*zatr;
         if(!(d*a.pullbackNetATR<=-c.pullbackMinimumATR && touched && slowHeld && d*a.candle.body>0 && d*(a.triggerClose-confirmation)>0 && location)) return;
         f.invalidation=d>0 ? MathMin(a.triggerLow,a.baselineFastEMA-c.pullbackTouchATR*zatr)-c.invalidationATR*atr : MathMax(a.triggerHigh,a.baselineFastEMA+c.pullbackTouchATR*zatr)+c.invalidationATR*atr;
         f.confirmation=confirmation;
      } else {
         BOZone zone; ZeroMemory(zone); if(d>0) zone=a.structure.preResistance; else zone=a.structure.preSupport;
         if(!zone.available) { f.reason=BO_ZONE_UNKNOWN; return; }
         double edge=d>0 ? zone.high : zone.low;
         if(!(d*a.candle.body>0 && d*(a.triggerClose-edge)>c.breakoutBufferATR*zatr && location)) return;
         f.invalidation=d>0 ? zone.low-c.invalidationATR*atr : zone.high+c.invalidationATR*atr;
         f.confirmation=edge+d*c.reclaimATR*zatr;
         f.retestLow=d>0 ? zone.low-c.invalidationATR*atr : zone.low-c.retestBandATR*zatr;
         f.retestHigh=d>0 ? zone.high+c.retestBandATR*zatr : zone.high+c.invalidationATR*atr;
      }
   }
   f.direction=d; f.reason=BO_OK;
   f.extension=d>0 ? (a.structure.resistance.available ? a.structure.resistance.low : 0) : (a.structure.support.available ? a.structure.support.high : 0);
}
#endif
#ifndef BO_V222_CONTRACT
#define BO_V222_CONTRACT

#define BO_LOGIC_VERSION 2026101707
void BOHashNumber(string &text, double value) { text+="|"+DoubleToString(value,6); }
uint BOHashText(string text) {
   uint hash=2166136261;
   for(int i=0;i<StringLen(text);i++) hash=(hash^(uint)StringGetCharacter(text,i))*16777619;
   return hash;
}
uint BOConfigHash(const BOConfig &c) {
   string text="BO2";
   BOHashNumber(text,c.swingRadius); BOHashNumber(text,c.minimumTouches); BOHashNumber(text,c.maximumZoneAge);
   BOHashNumber(text,c.clusterATR); BOHashNumber(text,c.minZoneATR); BOHashNumber(text,c.maxZoneATR);
   BOHashNumber(text,c.breakATR); BOHashNumber(text,c.reclaimATR); BOHashNumber(text,c.invalidationATR);
   BOHashNumber(text,c.confirmationLocation); BOHashNumber(text,c.deepBreachATR);
   BOHashNumber(text,c.breachSeconds); BOHashNumber(text,c.quoteFreshSeconds);
   BOHashNumber(text,c.lockLeadSeconds); BOHashNumber(text,c.clockUncertaintySeconds); BOHashNumber(text,c.lockGuardSeconds);
   BOHashNumber(text,c.boundaryLagSeconds); BOHashNumber(text,c.atrMinPips); BOHashNumber(text,c.atrMaxPips);
   BOHashNumber(text,c.shockATR); BOHashNumber(text,c.counterEfficiency); BOHashNumber(text,c.spreadMaxPips);
   BOHashNumber(text,c.probabilityMargin); BOHashNumber(text,c.fixedPayoutFraction);
   BOHashNumber(text,c.maximumAnalysisDelaySeconds); BOHashNumber(text,c.maximumObservationGapSeconds);
   BOHashNumber(text,c.rangeNetMaxATR); BOHashNumber(text,c.rangeEfficiencyMax);
   BOHashNumber(text,c.trendNetMinATR); BOHashNumber(text,c.trendEfficiencyMin);
   BOHashNumber(text,c.expansionMinATR); BOHashNumber(text,c.breakoutNetMinATR);
   BOHashNumber(text,c.breakoutEfficiencyMin); BOHashNumber(text,c.breakoutBufferATR);
   BOHashNumber(text,c.pullbackTouchATR); BOHashNumber(text,c.pullbackMinimumATR); BOHashNumber(text,c.retestBandATR);
   BOHashNumber(text,c.allowSR1); BOHashNumber(text,c.allowTP1); BOHashNumber(text,c.allowBR1);
   return BOHashText(text);
}
bool BOSafeTag(string tag) {
   if(StringLen(tag)<1 || StringLen(tag)>32) return false;
   for(int i=0;i<StringLen(tag);i++) {
      int ch=StringGetCharacter(tag,i);
      if(!((ch>=48 && ch<=57)||(ch>=65 && ch<=90)||(ch>=97 && ch<=122)||ch==95||ch==45||ch==46)) return false;
   }
   return StringFind(tag,"..")<0;
}
string BOEpisodeId(datetime start) { return Symbol()+"_M5_"+IntegerToString((long)start); }
#endif

int main(){
 int count;std::cin>>count;std::vector<BOBar>bars;
 std::cout<<"anchor,config_hash,regime,routed_setup,atr_raw,zone_atr_raw,candle_range_raw,atr_pips,zone_atr_pips,candle_range_pips,median_tr14_pips,rv14_pips,baseline_reason,baseline_direction,no_floor_reason,no_floor_direction\n";
 BOConfig c{};BOConfigDefaults(c);
 for(int j=0;j<count;j++){
  BOBar next{};std::cin>>next.time>>next.open>>next.high>>next.low>>next.close>>next.ticks;if(!std::cin)return 2;
  bool continuous=!bars.empty() && next.time-bars.back().time==300;
  if(!continuous)bars.clear();
  if(bars.size()==64){
   BOAnchor a{};BOBuildMarket(bars,64,c,a);if(!a.available)return 3;
   BOCandidate original{},unfiltered{};BOFormCandidate(a,c,original);BOConfig zero=c;zero.atrMinPips=0;BOFormCandidate(a,zero,unfiltered);
   std::vector<double> ranges;double square=0;
   for(int k=50;k<64;k++){
    ranges.push_back(std::max(bars[k].high-bars[k].low,std::max(std::abs(bars[k].high-bars[k-1].close),std::abs(bars[k].low-bars[k-1].close))));
    double ret=std::log(bars[k].close/bars[k-1].close);square+=ret*ret;
   }
   std::sort(ranges.begin(),ranges.end());double median=(ranges[6]+ranges[7])/2;
   std::cout<<next.time<<","<<BOConfigHash(c)<<","<<a.regime<<","<<original.setup<<","<<std::setprecision(17)
    <<a.volatility.atr<<","<<a.volatility.zoneATR<<","<<a.candle.range<<","<<a.volatility.atr/.0001<<","<<a.volatility.zoneATR/.0001<<","<<a.candle.range/.0001<<","<<median/.0001<<","<<bars.back().close*std::sqrt(square/14)/.0001
    <<","<<BOReasonName(original.reason)<<","<<original.direction<<","<<BOReasonName(unfiltered.reason)<<","<<unfiltered.direction<<"\n";
  }
  bars.push_back(next);if(bars.size()>64)bars.erase(bars.begin());
 }
 return 0;
}
