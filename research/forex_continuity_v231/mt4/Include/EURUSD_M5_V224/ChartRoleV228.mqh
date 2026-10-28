#ifndef BO_V228_CHART_ROLE
#define BO_V228_CHART_ROLE
// Persist chart identity, never infer Binary ownership from another chart's orders.
// This append-only ledger is not deleted on deinitialization. Corruption blocks init.
string boRolePath="",boRoleSymbol="";
long boRoleSequence=0;uint boRoleChecksum=0;
int boRoleMode=-1,boRoleMagic=0;
string BOChartRoleOrigin() { return IsTesting() ? "BACKTEST_MT4" : "LIVE_MT4"; }
bool BOChartRoleOrders(string symbol,int magic) {
   for(int i=OrdersTotal()-1;i>=0;i--) if(OrderSelect(i,SELECT_BY_POS,MODE_TRADES) && OrderSymbol()==symbol) {
      string note=OrderComment();
      if(OrderMagicNumber()==magic || StringFind(note,"FX222:")==0 || StringFind(note,"FX222A:")==0 ||
         StringFind(note,"FX221:")==0 || StringFind(note,"FX220:")==0) return true;
   }
   return false;
}
bool BOChartRolePrepare(int mode,int magic,string tag) {
   boRoleSequence=0;boRoleChecksum=0;boRoleMode=-1;boRoleMagic=0;boRoleSymbol="";
   if(!BOSafeTag(Symbol()) || !BOSafeTag(tag))return false;
   string identity=IntegerToString(AccountNumber())+"_"+IntegerToString((long)BOHashText(AccountServer()))+"_"+IntegerToString(ChartID());
   boRolePath="EA_MODE_V228\\"+identity+(IsTesting() ? "_TESTER_"+tag : "_LIVE")+".csv";
   FolderCreate("EA_MODE_V228");
   if(FileIsExist(boRolePath)) {
      int f=FileOpen(boRolePath,FILE_READ|FILE_CSV|FILE_ANSI,',');if(f==INVALID_HANDLE)return false;
      string row[];bool ok=FileSize(f)>0;
      while(ok && !FileIsEnding(f)) {
         if(!BODemoReadCells(f,11,row)){ok=false;break;}
         for(int j=1;j<11;j++) if(j!=5 && j!=7 && !BODemoInteger(row[j]))ok=false;
         string payload="";for(int k=0;k<10;k++)payload+=(k>0 ? "|" : "")+row[k];
         if(!ok || row[0]!="V228_CHART_ROLE_V1" || StringToInteger(row[1])!=boRoleSequence+1 ||
            (uint)StringToInteger(row[2])!=boRoleChecksum || StringToInteger(row[3])!=AccountNumber() ||
            (uint)StringToInteger(row[4])!=BOHashText(AccountServer()) || row[5]!=BOChartRoleOrigin() ||
            StringToInteger(row[6])!=ChartID() || !BOSafeTag(row[7]) || StringToInteger(row[8])<=0 ||
            (StringToInteger(row[9])!=0 && StringToInteger(row[9])!=1) ||
            (uint)StringToInteger(row[10])!=BOHashText(payload)){ok=false;break;}
         boRoleSequence=StringToInteger(row[1]);boRoleChecksum=(uint)StringToInteger(row[10]);
         boRoleSymbol=row[7];boRoleMagic=(int)StringToInteger(row[8]);boRoleMode=(int)StringToInteger(row[9]);
      }
      FileClose(f);if(!ok)return false;
   }
   // A distinct Binary chart is allowed. This former Forex chart must keep managing
   // its positions until they are closed, including after a symbol/magic change.
   if(boRoleMode==1 && (mode!=1 || Symbol()!=boRoleSymbol || magic!=boRoleMagic) &&
      BOChartRoleOrders(boRoleSymbol,boRoleMagic)) {
      Print("V228: this chart previously managed Forex positions. Restore its Forex mode, symbol and magic; preserve EA_MODE_V228 state.");
      return false;
   }
   return true;
}
bool BOChartRoleCommit(int mode,int magic) {
   if(boRoleMode==mode && boRoleSymbol==Symbol() && boRoleMagic==magic)return true;
   string payload="V228_CHART_ROLE_V1|"+IntegerToString(boRoleSequence+1)+"|"+IntegerToString((long)boRoleChecksum)+"|"+
      IntegerToString(AccountNumber())+"|"+IntegerToString((long)BOHashText(AccountServer()))+"|"+BOChartRoleOrigin()+"|"+
      IntegerToString(ChartID())+"|"+Symbol()+"|"+IntegerToString(magic)+"|"+IntegerToString(mode);
   uint checksum=BOHashText(payload);
   int f=FileOpen(boRolePath,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI,',');if(f==INVALID_HANDLE)return false;
   bool ok=FileSeek(f,0,SEEK_END);
   if(ok)ok=FileWrite(f,"V228_CHART_ROLE_V1",boRoleSequence+1,boRoleChecksum,AccountNumber(),BOHashText(AccountServer()),
      BOChartRoleOrigin(),ChartID(),Symbol(),magic,mode,checksum)>0;
   FileFlush(f);FileClose(f);
   if(ok){boRoleSequence++;boRoleChecksum=checksum;boRoleMode=mode;boRoleMagic=magic;boRoleSymbol=Symbol();}
   return ok;
}
#endif
