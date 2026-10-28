#ifndef BO_V222_ORIGIN
#define BO_V222_ORIGIN
#include "DemoLearning.mqh"

string BOOriginKind() { return IsTesting() ? "BACKTEST_MT4" : "LIVE_MT4"; }
bool BOCompleteTester(string root,long sequence,long nowMs) {
   string path=root+"\\tester_complete.csv",temp=path+".tmp";
   if(FileIsExist(path) || FileIsExist(temp)) return false;
   int file=FileOpen(temp,FILE_WRITE|FILE_CSV|FILE_ANSI,','); if(file==INVALID_HANDLE) return false;
   bool ok=FileWrite(file,"schema","logic","sequence","observed_ms")>0;
   if(FileWrite(file,1,BO_LOGIC_VERSION,sequence,nowMs)==0) ok=false;
   FileFlush(file); FileClose(file); return ok && FileMove(temp,0,path,0);
}
bool BOBindOrigin(string root,uint config,uint feed) {
   string path=root+"\\data_origin.csv",kind=BOOriginKind();
   string expected[5]={"schema","logic","kind","config_hash","feed_hash"};
   if(FileIsExist(path)) {
      int file=FileOpen(path,FILE_READ|FILE_CSV|FILE_ANSI,','); if(file==INVALID_HANDLE) return false;
      string header[]; string row[];
      bool ok=BODemoReadCells(file,5,header) && BODemoReadCells(file,5,row) && FileIsEnding(file);
      if(ok) for(int i=0;i<5;i++) if(header[i]!=expected[i] || (i!=2 && !BODemoInteger(row[i]))) ok=false;
      if(ok) ok=StringToInteger(row[0])==1 && StringToInteger(row[1])==BO_LOGIC_VERSION && row[2]==kind &&
         (uint)StringToInteger(row[3])==config && (uint)StringToInteger(row[4])==feed;
      FileClose(file); return ok;
   }
   string temp=path+".tmp"; if(FileIsExist(temp)) return false;
   int file=FileOpen(temp,FILE_WRITE|FILE_CSV|FILE_ANSI,','); if(file==INVALID_HANDLE) return false;
   bool ok=FileWrite(file,"schema","logic","kind","config_hash","feed_hash")>0;
   if(FileWrite(file,1,BO_LOGIC_VERSION,kind,config,feed)==0) ok=false;
   FileFlush(file); FileClose(file); return ok && FileMove(temp,0,path,0);
}
#endif
