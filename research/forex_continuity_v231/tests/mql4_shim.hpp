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
