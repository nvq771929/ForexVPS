#ifndef BO_V226_EMBEDDED_STORAGE
#define BO_V226_EMBEDDED_STORAGE
#include "EmbeddedContext.mqh"
// Numeric-only metadata: 19 signed 64-bit fields; archived ECBar is 48 bytes.
// Checkpoints are private to the same terminal layout. Packets are portable.
struct ESMeta {
   long engine,origin,offset,config,feed,policy,instance,symbol;
   long first,count,previousHash,availableMs,seed,requested,received,error,kind,terminal,streamHash;
};
const int ES_ENGINE=2026102401,ES_PACKET_MAGIC=1163087921,ES_STATE_MAGIC=1163087922;
string ESName(string root,string kind,long sequence) {
   return root+(kind=="checkpoint" ? "\\state" : "\\packets")+"\\embedded_"+kind+"_v226_"+StringFormat("%012I64d",sequence)+".bin";
}
string ESFull(string root,string name) {return StringFind(name,"\\")>=0 ? name : root+"\\"+name;}
bool ESIdentity(const ESMeta &a,const ESMeta &b) {
   return a.engine==b.engine && a.origin==b.origin && a.offset==b.offset && a.config==b.config &&
      a.feed==b.feed && a.policy==b.policy && a.instance==b.instance && a.symbol==b.symbol &&
      a.requested==b.requested && a.terminal==b.terminal;
}
bool ESMetaValid(const ESMeta &m,long nowMs) {
   return m.engine==ES_ENGINE && (m.origin==1 || m.origin==2) && m.offset>=-720 && m.offset<=840 && m.offset%5==0 &&
      m.config>0 && m.feed>0 && m.policy>0 && m.instance>0 && m.symbol>0 && m.first>0 &&
      m.count>0 && m.count<=10000000 && m.previousHash>=0 && m.previousHash<=4294967295 &&
      m.availableMs>0 && m.availableMs<=nowMs && m.seed>0 && m.seed%300==0 &&
      m.requested>=0 && m.requested<=4800 && m.received>=0 && m.received<=4800 &&
      m.error>=0 && m.kind>=1 && m.kind<=3 && m.terminal>0;
}
bool ESFrameValid(const ECFrame &f,int seconds,int warm) {
   if(f.seconds!=seconds || f.warm!=warm || f.size<0 || f.size>200 || f.count<f.size || f.count>10000000 ||
      f.trSize<0 || f.trSize>200 || f.emaSize<0 || f.emaSize>10)return false;
   for(int i=0;i<f.size;i++)if(!ECValidBar(f.bars[i]) || f.bars[i].time%seconds!=0 ||
      (i>0 && f.bars[i].time<=f.bars[i-1].time))return false;
   for(int i=0;i<f.trSize;i++)if(!MathIsValidNumber(f.tr[i]) || f.tr[i]<0)return false;
   for(int i=0;i<f.emaSize;i++)if(!MathIsValidNumber(f.emas[i]) || f.emas[i]<=0)return false;
   return MathIsValidNumber(f.ema20) && MathIsValidNumber(f.ema50) && MathIsValidNumber(f.seed20) && MathIsValidNumber(f.seed50);
}
bool ESStateValid(const ECState &s,const ESMeta &m) {
   if(!ESFrameValid(s.m5,300,64) || !ESFrameValid(s.m15,900,150) || !ESFrameValid(s.h1,3600,150) ||
      s.m5.size==0 || s.m5.count!=m.count || s.last!=s.m5.bars[s.m5.size-1].time || s.last<m.seed ||
      s.snapshot.asofMs!=(s.last+300)*1000 || s.snapshot.asofMs>m.availableMs-m.offset*60000 ||
      s.direction<0 || s.direction>4 || s.snapshot.direction!=s.direction || s.pending<0 || s.pending>4 ||
      s.pendingCount<0 || s.pendingCount>1 || s.unsupported<0 || s.unsupported>10000000 ||
      s.a15.seconds!=900 || s.a60.seconds!=3600 || s.a15.size<0 || s.a15.size>3 || s.a60.size<0 || s.a60.size>12)return false;
   if(s.started<0 || s.started>s.snapshot.asofMs || (s.started>0 && s.started%900000!=0))return false;
   return true;
}
bool ESWritePacket(string root,const ESMeta &m,const ECBar &bars[],uint &checksum) {
   if(m.count!=ArraySize(bars) || m.count>4800)return false;
   long end=m.first+m.count-1;string target=ESName(root,"packet",end),temp=target+".tmp";
   if(FileIsExist(target) || FileIsExist(temp))return false;
   int f=FileOpen(temp,FILE_READ|FILE_WRITE|FILE_BIN);if(f==INVALID_HANDLE)return false;
   bool ok=FileWriteInteger(f,ES_PACKET_MAGIC,INT_VALUE)==4 && FileWriteInteger(f,1,INT_VALUE)==4 &&
      FileWriteInteger(f,sizeof(m),INT_VALUE)==4 && FileWriteInteger(f,sizeof(ECBar),INT_VALUE)==4 && FileWriteStruct(f,m)==sizeof(m);
   for(int i=0;i<ArraySize(bars);i++)if(FileWriteStruct(f,bars[i])!=sizeof(ECBar))ok=false;
   FileFlush(f);checksum=BOChecksum(f,(long)FileSize(f));FileSeek(f,0,SEEK_END);
   if(FileWriteInteger(f,(int)checksum,INT_VALUE)!=4)ok=false;
   FileFlush(f);FileClose(f);return ok && FileMove(temp,0,target,0);
}
bool ESReadPacket(string path,const ESMeta &identity,long nowMs,ESMeta &m,ECBar &bars[],uint &checksum) {
   ZeroMemory(m);
   int f=FileOpen(path,FILE_READ|FILE_BIN);if(f==INVALID_HANDLE)return false;
   long size=(long)FileSize(f);if(size<16+sizeof(m)+48+4 || size>16+sizeof(m)+4800*48+4) {FileClose(f);return false;}
   checksum=BOChecksum(f,size-4);uint stored=(uint)FileReadInteger(f,INT_VALUE);FileSeek(f,0,SEEK_SET);
   bool ok=checksum==stored && FileReadInteger(f,INT_VALUE)==ES_PACKET_MAGIC && FileReadInteger(f,INT_VALUE)==1 &&
      FileReadInteger(f,INT_VALUE)==sizeof(m) && FileReadInteger(f,INT_VALUE)==sizeof(ECBar) && FileReadStruct(f,m)==sizeof(m);
   if(!ok || !ESMetaValid(m,nowMs) || !ESIdentity(m,identity) || m.kind==3 || m.count>4800 ||
      size!=16+sizeof(m)+m.count*sizeof(ECBar)+4) {FileClose(f);return false;}
   ArrayResize(bars,(int)m.count);
   for(int i=0;i<ArraySize(bars);i++) {
      if(FileReadStruct(f,bars[i])!=sizeof(ECBar) || !ECValidBar(bars[i]) ||
         (i>0 && bars[i].time<=bars[i-1].time) || (bars[i].time+300)*1000>m.availableMs-m.offset*60000)ok=false;
   }
   FileClose(f);
   string expectedName="embedded_packet_v226_"+StringFormat("%012I64d",m.first+m.count-1)+".bin";
   if(StringLen(path)<StringLen(expectedName) || StringSubstr(path,StringLen(path)-StringLen(expectedName))!=expectedName)ok=false;
   if(m.first==1 && bars[0].time!=m.seed)ok=false;
   return ok;
}
bool ESWriteCheckpoint(string root,const ESMeta &m,const ECState &state) {
   if(!ESStateValid(state,m))return false;
   string target=ESName(root,"checkpoint",m.count),temp=target+".tmp";
   if(FileIsExist(target))return false;
   if(FileIsExist(temp))return false;
   int f=FileOpen(temp,FILE_READ|FILE_WRITE|FILE_BIN);if(f==INVALID_HANDLE)return false;
   bool ok=FileWriteInteger(f,ES_STATE_MAGIC,INT_VALUE)==4 && FileWriteInteger(f,1,INT_VALUE)==4 &&
      FileWriteInteger(f,sizeof(m),INT_VALUE)==4 && FileWriteInteger(f,sizeof(state),INT_VALUE)==4 &&
      FileWriteStruct(f,m)==sizeof(m) && FileWriteStruct(f,state)==sizeof(state);
   FileFlush(f);uint hash=BOChecksum(f,(long)FileSize(f));FileSeek(f,0,SEEK_END);
   if(FileWriteInteger(f,(int)hash,INT_VALUE)!=4)ok=false;
   FileFlush(f);FileClose(f);if(!ok || !FileMove(temp,0,target,0))return false;
   // Keep the newest two immutable checkpoints. Never delete packets/evidence.
   string name;long search=FileFindFirst(root+"\\state\\embedded_checkpoint_v226_*.bin",name);long previous=0;
   if(search!=INVALID_HANDLE) {
      do {int p=StringFind(name,"embedded_checkpoint_v226_");long n=StringToInteger(StringSubstr(name,p+25,12));if(n<m.count && n>previous)previous=n;}while(FileFindNext(search,name));
      FileFindClose(search);
   }
   search=FileFindFirst(root+"\\state\\embedded_checkpoint_v226_*.bin",name);
   if(search!=INVALID_HANDLE) {
      do {int p=StringFind(name,"embedded_checkpoint_v226_");long n=StringToInteger(StringSubstr(name,p+25,12));if(n>0 && n<previous)FileDelete(ESFull(root+"\\state",name));}while(FileFindNext(search,name));
      FileFindClose(search);
   }
   return true;
}
bool ESReadCheckpoint(string path,const ESMeta &identity,long nowMs,ESMeta &m,ECState &state) {
   ZeroMemory(m);
   int f=FileOpen(path,FILE_READ|FILE_BIN);if(f==INVALID_HANDLE)return false;
   long size=(long)FileSize(f),expected=16+sizeof(m)+sizeof(state)+4;
   if(size!=expected) {FileClose(f);return false;}
   uint hash=BOChecksum(f,size-4),stored=(uint)FileReadInteger(f,INT_VALUE);FileSeek(f,0,SEEK_SET);
   bool ok=hash==stored && FileReadInteger(f,INT_VALUE)==ES_STATE_MAGIC && FileReadInteger(f,INT_VALUE)==1 &&
      FileReadInteger(f,INT_VALUE)==sizeof(m) && FileReadInteger(f,INT_VALUE)==sizeof(state) &&
      FileReadStruct(f,m)==sizeof(m) && FileReadStruct(f,state)==sizeof(state);
   FileClose(f);return ok && ESMetaValid(m,nowMs) && ESIdentity(m,identity) && m.kind==3 && ESStateValid(state,m);
}
#endif
