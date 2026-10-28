"""Execute the actual Forex MQL source under a test-only C++ broker API.

No network, real broker account, MetaEditor compile or profitability claims.
"""
import csv
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from tests.test_demo_learning_native import NativeHarness
from tests.fixtures import START,sr_bars


class ForexExecutionTests(NativeHarness,unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        path=cls.binary.parent/'demo.cpp';code=path.read_text()
        branch=r'''
 if(mode>=100){
  if(argc>7)ForexUseDashboard=std::stoi(argv[7])!=0;
  TradingMode=Forex;ForexNewsFilter=false;fakeServer="Exness-Demo";fakeNowMs=(start-100)*1000;
  if(mode==101 || mode==102){fakeAccountMode=ACCOUNT_TRADE_MODE_REAL;fakeServer="Exness-Real18";}
  if(mode==102)ForexAllowRealTrading=true;
  if(mode==103)ForexEnableTrading=false;
  if(mode==105){fakeBalance=100;fakeEquity=100;fakeMinLot=.1;}
  if(mode==106)fakeTickValue=0;
  if(mode==108)fakeFreeMargin=0;
  if(mode==113)fakeTradingAllowed=false;
  if(mode==123)fakeServer="OTHER_BROKER";
  if(mode==125 || mode==204){Digits=4;Point=.0001;fakeTickSize=.0001;fakeTickValue=10;}
  if(mode==126)fakeLotStep=.1;
  if(mode==127)ForexRiskPercent=9;
  if(mode==130)fakeAccountMode=1;
  if(mode==132)ForexRiskPercent=std::nan("");
  if(mode>=201 && mode<=209)ForexTakeProfitRR=6;
  if(mode==428)ForexTakeProfitRR=6;
  if(mode>=400 && mode<=434){ForexEnableAveraging=true;fakeBalance=1000;fakeEquity=1000;fakeFreeMargin=1000;}
  if(mode==407)ForexInitialRiskFraction=.3;
  if(mode==410)ForexInitialRiskFraction=1.1;
  if(mode==211){fakeFillSlippage=.001;fakeCloseFailure=true;}
  if(mode==215)ForexTrailingStepPips=std::nan("");
  if(mode>=600 && mode<=612){
   fakeAccountMode=ACCOUNT_TRADE_MODE_REAL;fakeServer="Exness-Real18";ForexAllowRealTrading=true;
   fakeBalance=1000;fakeEquity=1000;fakeFreeMargin=1000;
   if(mode==600 || mode==601 || mode==610){fakeBalance=0;fakeEquity=mode==600?100:10000;}
   if(mode==602)fakeBalance=-100;
   if(mode==603){fakeBalance=.01;fakeEquity=.01;}
   if(mode==605){fakeEquity=10000;fakeFreeMargin=10000;}
   if(mode==606)fakeBalance=10000;
   if(mode==607)ForexAllowRealTrading=false;
   if(mode==608)fakeTradingAllowed=false;
   if(mode==609)ForexEnableTrading=false;
   if(mode==612)fakeEquity=0;
  }
  int init=OnInit();bool result=false,dayOK=true,restartDayOK=true,duplicateLock=false;
  int switchInit=-1;double baseline=0,lots=0,stop=0,take=0,price=0,risk=0,firstSL=0,secondSL=0,finalSL=0,originalRisk=0;
  bool recovered=false,gateA=false,gateB=false,gateC=false;double basketBudget=0,basketRisk=0,weightedEntry=0;int basketCount=0;
  if(init==0){
   if(mode>=140 && mode<=143){
    BOConfig c{};BOConfigDefaults(c);std::vector<BOBar>b;
    for(auto &z:closedBars)b.push_back({z.time,z.open,z.high,z.low,z.close,z.ticks});
    BOAnchor a{};BOBuildMarket(b,count,c,a);BOCandidate f{};BOFormCandidate(a,c,f);
    double reference=f.confirmation+f.direction*.00001;
    for(int sec=0;sec<=300;sec++){
     fakeNowMs=(start+sec)*1000;
     if(sec==300)addBar({start,reference,reference+.0002,reference-.0002,reference,10});
     fakeBid=reference;fakeAsk=reference+.0001;
     if(mode==141 && sec>=264 && sec<=270)continue;
     if(mode==142 && sec==280){OnDeinit(0);OnInit();}
     OnTick();if(!fakeTesting)OnTimer();
    }
    result=fakeSendCalls>0;
   }else{
    fakeNowMs=start*1000;long now=0;BOClockTick(TimeCurrent(),now);
    fakeBid=1.10000;fakeAsk=1.10010;
    BOPrediction e{};e.exists=true;e.locked=true;e.lockedDirection=1;e.lockedAction=1;e.action=1;
    e.targetTime=start;e.lastQuoteMs=now;e.validation=BO_CONFIRMED;e.anchor.volatility.atr=.0004;e.candidate.invalidation=1.0993;
    if(mode==202 || mode==330 || mode==401){e.action=-1;e.lockedAction=-1;e.lockedDirection=-1;e.candidate.invalidation=1.1008;}
    if(mode>=400 && mode<=434){e.candidate.setup=1;e.candidate.invalidation=e.action>0 ? 1.09910 : 1.10100;}
    if(mode==104)fakeAsk=1.1003;
    if(mode==107)e.candidate.invalidation=1.09;
    if(mode==109)fakeSendError=130;
    if(mode==110)fakeSendTimeoutAccepted=true;
    if(mode==111)fakeFXWriteFailure=true;
    if(mode==114)e.lastQuoteMs-=4000;
    if(mode==115)e.targetTime-=3;
    if(mode==116)fakeFXStorageDelayMs=4000;
    if(mode==124)fakeOrders.push_back({88,OP_BUYLIMIT,77,"EURUSD","manual",.01,1.1,1.09,1.11,0,0,0,TimeCurrent(),0});
    if(mode==128)e.candidate.invalidation=1.101;
    if(mode==131)fakeQuoteAgeSeconds=5;
    if(mode==133)fakeTradeBusy=true;
    if(mode==134)fakeMarketAllowed=false;
    if(mode==135)fxSettings.enabled=false;
    if(mode==136)fakeNakedFill=true;
    if(mode==137)fakeFillSlippage=.001;
    if(mode==138){fakeMinLot=.1;fakeMaxLot=.01;}
    if(mode==121){FXDayGuard(now/1000);baseline=fxDayEquity;fakeEquity=9800;dayOK=FXDayGuard(now/1000);}
    if(mode==122){
     string p=fxRoot+"\\risk_day_"+IntegerToString(now/86400000)+".csv";
     int h=FileOpen(p,FILE_WRITE|FILE_CSV|FILE_ANSI);FileWrite(h,"CORRUPTED");FileClose(h);
    }

    auto newsClock=[&](){boContextClockValid=true;boContextSamples=3;boContextOffset=fakeBrokerUTCOffset;boContextCalibratedMono=GetTickCount();};
    auto makeNews=[&](string impact,long when,int age=30,bool uncertain=false,bool corrupt=false){
     fxSettings.newsFilter=true;newsClock();
     long received=TimeGMT()-age,from=TimeGMT()/86400*86400-86400,to=from+8*86400;
     string common=IntegerToString(received)+"|"+IntegerToString(received+3600)+"|"+IntegerToString(from)+"|"+IntegerToString(to)+"|"+string(64,'b');
     int f=FileOpen("FX_V222\\news_calendar.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
     FileWrite(f,"contract","kind","received","expires","coverage_from","coverage_to","snapshot","event_id","event_utc","currency","impact","tracking","label","uncertain","count","fnv");
     string meta="V222_FOREX_NEWS_V1|META|"+common+"|NONE|0|NONE|NONE|NONE|READY|0|1";
     FileWrite(f,"V222_FOREX_NEWS_V1","META",received,received+3600,from,to,string(64,'b'),"NONE",0,"NONE","NONE","NONE","READY",0,1,BOHashText(meta));
     string payload="V222_FOREX_NEWS_V1|NEWS|"+common+"|"+string(24,'a')+"|"+IntegerToString(when)+"|USD|"+impact+"|IMPACT_"+impact+"|TEST_EVENT|"+(uncertain?"1":"0")+"|1";
     FileWrite(f,"V222_FOREX_NEWS_V1","NEWS",received,received+3600,from,to,string(64,'b'),string(24,'a'),when,"USD",impact,"IMPACT_"+impact,"TEST_EVENT",uncertain?1:0,1,corrupt?0:BOHashText(payload));
     FileClose(f);fxNewsReadTried=false;
    };
    if(mode>=300 && mode<=311){
     if(mode==300){fxSettings.newsFilter=true;newsClock();}
     else makeNews(mode==309?"Medium":"High",TimeGMT()+(mode==301?3600:600),mode==302?1900:30,mode==303,mode==304);
     if(mode==305)boContextClockValid=false;
     if(mode==306)fakeTesting=true;
     if(mode==307)fxSettings.newsFilter=false;
     if(mode==308){fxSettings.newsLookaheadMinutes=5;makeNews("High",TimeGMT()+33*60);}
     if(mode==310){makeNews("High",TimeGMT()-16*60);}
     if(mode==311){makeNews("Medium",TimeGMT()+16*60);fxSettings.newsLookaheadMinutes=0;}
    }
    if(mode==610){fakeBalance=1000;fakeEquity=1000;}
    result=FXSend(e,now);
    if(mode==611 && !fakeOrders.empty()){
     fakeBalance=0;fakeEquity=100;fakeNowMs+=3601000;BOClockTick(TimeCurrent(),now);FXManagePositions();
    }
    if(!fakeOrders.empty()){auto o=fakeOrders[0];lots=o.lots;stop=o.sl;take=o.tp;price=o.price;}

    if(mode>=200 && mode<250){
     auto advance=[&](int seconds){fakeNowMs+=seconds*1000;BOClockTick(TimeCurrent(),now);};
     auto profitable=[&](double multiple){
      auto o=fakeOrders[0];double r=std::abs(o.price-stop),exit=o.price+(o.type==OP_BUY?1:-1)*r*multiple;
      fakeBid=o.type==OP_BUY?exit:exit-.0001;fakeAsk=fakeBid+.0001;
     };
     if(mode>=201 && mode<=209 && !fakeOrders.empty()){
      profitable(mode==203 ? 3.0 : 1.1);
      if(mode==205)fakeFreezeLevel=1000;
      if(mode==206)fakeModifyError=130;
      if(mode==207){fakeModifyError=128;fakeModifyTimeoutAccepted=true;}
      if(mode==209){int h=FileOpen(fxRoot+"\\position_"+IntegerToString(fakeOrders[0].ticket)+".csv",FILE_WRITE|FILE_CSV|FILE_ANSI);FileWrite(h,"CORRUPTED");FileClose(h);}
      boHistoryReady=true;boHistoryBar=TimeCurrent()/300*300;boHistoryBars.clear();
      for(auto &b:closedBars)boHistoryBars.push_back({b.time,b.open,b.high,b.low,b.close,b.ticks});
      FXManagePositions();if(!fakeOrders.empty())firstSL=fakeOrders[0].sl;
      if(mode==203){advance(6);profitable(4);FXManagePositions();secondSL=fakeOrders[0].sl;advance(6);profitable(2);FXManagePositions();}
      if(mode==206){advance(2);FXManagePositions();gateA=fakeModifyCalls==1;fakeModifyError=0;advance(4);FXManagePositions();}
      if(mode==207){advance(6);FXManagePositions();}
      if(mode==208){OnDeinit(0);init=OnInit();BOClockTick(TimeCurrent(),now);profitable(1.2);advance(6);FXManagePositions();OrderSelect(0,SELECT_BY_POS,MODE_TRADES);recovered=FXOriginalRisk(originalRisk);}
     }
     if(mode==211){OnDeinit(0);init=OnInit();fakeCloseFailure=false;BOClockTick(TimeCurrent(),now);FXManagePositions();}
     if(mode==212){
      fakeOrders.push_back({99,OP_BUY,77,"EURUSD","manual",.01,1.1,1.09,1.11,0,0,0,TimeCurrent(),0});
      fxSettings.emergencyClose=true;FXManagePositions();FXSend(e,now);
     }
     if(mode==213){FXDayGuard(now/1000);fakeEquity=9700;FXDayGuard(now/1000);FXManagePositions();}
     if(mode==214){fakeQuoteAgeSeconds=10;profitable(1.1);FXManagePositions();}
     if(mode==216){connected=false;fxSettings.emergencyClose=true;FXManagePositions();gateA=fakeOrders.size()==1;connected=true;advance(1);FXManagePositions();}
     if(mode==230){
      // Close the initial ticket, then reserve rejected attempts. Cooldown is disabled only in this fixture.
      fxSettings.cooldownMinutes=0;fxSettings.maxLossStreak=20;
      if(!fakeOrders.empty()){OrderSelect(0,SELECT_BY_POS,MODE_TRADES);OrderClose(OrderTicket(),OrderLots(),fakeBid,0,clrNONE);}
      fakeSendError=130;
      for(int j=0;j<6;j++){advance(300);e.targetTime=TimeCurrent();e.lastQuoteMs=now;FXSend(e,now);}
      OnDeinit(0);init=OnInit();BOClockTick(TimeCurrent(),now);fxSettings.cooldownMinutes=0;fxSettings.maxLossStreak=20;
      advance(300);e.targetTime=TimeCurrent();e.lastQuoteMs=now;FXSend(e,now);
     }
     if(mode==231){
      for(int j=0;j<3;j++)FXRegisterExit(80+j,TimeCurrent()-10+j,-1.5);
      gateA=FXRiskEntryGuard(TimeCurrent());OnDeinit(0);init=OnInit();BOClockTick(TimeCurrent(),now);gateB=FXRiskEntryGuard(TimeCurrent());
      advance(86400);gateC=FXRiskEntryGuard(TimeCurrent());
     }
     if(mode==232){advance(120);
      FXRegisterExit(82,TimeCurrent()-30,1);FXRegisterExit(81,TimeCurrent()-10,-2);FXRegisterExit(80,TimeCurrent()-20,-3);
      fxSettings.cooldownMinutes=0;gateA=FXRiskEntryGuard(TimeCurrent());baseline=fxLossStreak;
      FXRegisterExit(83,TimeCurrent(),1);gateB=FXRiskEntryGuard(TimeCurrent());risk=fxLossStreak;
     }
     if(mode==233){
      FXRegisterExit(81,TimeCurrent(),-2);OnDeinit(0);init=OnInit();BOClockTick(TimeCurrent(),now);
      gateA=FXRiskEntryGuard(TimeCurrent());advance(901);gateB=FXRiskEntryGuard(TimeCurrent());
     }
     if(mode==234){
      string p=fxRoot+"\\attempts_"+IntegerToString(TimeCurrent()/86400)+".csv";
      int h=FileOpen(p,FILE_WRITE|FILE_CSV|FILE_ANSI);FileWrite(h,"CORRUPTED");FileClose(h);
      advance(300);e.targetTime=TimeCurrent();e.lastQuoteMs=now;FXRiskEntryGuard(TimeCurrent());
     }
     if(mode==235){
      // Thursday -> Friday, Saturday, Sunday. All schedule arguments are broker seconds.
      long friday=start+86400;
      gateA=FXScheduleEntry(friday+19*3600+59*60);
      gateB=FXScheduleEntry(friday+20*3600);
      gateC=FXFridayExit(friday+20*3600+30*60);
      baseline=FXScheduleEntry(start+21*3600);risk=FXScheduleEntry(start+22*3600+15*60);
      recovered=!FXScheduleEntry(friday+86400) && !FXScheduleEntry(friday+2*86400);
     }
     if(mode==236){
      fxSettings.rolloverStartMinute=23*60+45;fxSettings.rolloverEndMinute=15;
      gateA=FXScheduleEntry(start+23*3600+50*60);gateB=FXScheduleEntry(start+5*60);gateC=FXScheduleEntry(start+20*60);
     }
     if(mode==237){
      fakeNowMs=(start+86400+20*3600+30*60)*1000;BOClockTick(TimeCurrent(),now);fakeCloseFailure=true;
      FXManagePositions();gateA=!fakeOrders.empty();OnDeinit(0);init=OnInit();fakeCloseFailure=false;BOClockTick(TimeCurrent(),now);FXManagePositions();
     }
     if(!fakeOrders.empty())finalSL=fakeOrders[0].sl;
    }

    if(mode>=320 && mode<=331 && !fakeOrders.empty()){
     if(mode==324){fakeOrders[0].lots=.01;}
     fakeOrders[0].profit=mode==322?-10:10;
     if(mode==330){fakeAsk=fakeOrders[0].price-.0003;fakeBid=fakeAsk-.0001;}
     else {fakeBid=fakeOrders[0].price+.0003;fakeAsk=fakeBid+.0001;}
     if(mode==331){FXWriteFlag(fxRoot+"\\news_reduce_"+string(24,'a')+"_"+IntegerToString(TimeGMT()+240)+".csv","PARTIAL_CLOSE_RESERVED");}
     if(mode==323)fakeOrders[0].sl=fakeOrders[0].price+.00005;
     if(mode==326){fakeNowMs+=3300000;BOClockTick(TimeCurrent(),now);}
     if(mode==327)fakeCloseFailure=true;
     if(mode==329)fakeQuoteAgeSeconds=10;
     makeNews(mode==320?"High":"Medium",TimeGMT()+240);
     FXManagePositions();if(!fakeOrders.empty())firstSL=fakeOrders[0].lots;
     if(mode==325 || mode==326 || mode==328){
      OnDeinit(0);init=OnInit();BOClockTick(TimeCurrent(),now);fxSettings.newsFilter=true;newsClock();
      fakeNowMs+=(mode==326?301:6)*1000;BOClockTick(TimeCurrent(),now);FXManagePositions();
     }
     if(mode==327){fakeCloseFailure=false;fakeNowMs+=1000;BOClockTick(TimeCurrent(),now);FXManagePositions();}
     if(!fakeOrders.empty()){finalSL=fakeOrders[0].lots;OrderSelect(0,SELECT_BY_POS,MODE_TRADES);long birth=0;recovered=FXPositionState(originalRisk,birth);baseline=birth;}
    }

    if(mode>=400 && mode<=434 && !fakeOrders.empty()){
     int primary=fakeOrders[0].ticket;long birth=fakeOrders[0].opened;int direction=fakeOrders[0].type==OP_BUY?1:-1;
     fakeNowMs=(start+600)*1000;BOClockTick(TimeCurrent(),now);
     double exit=fakeOrders[0].price-direction*.00050;
     if(direction>0){fakeBid=exit;fakeAsk=exit+.0001;}else {fakeAsk=exit;fakeBid=exit-.0001;}
     fakeEquity=998.5;fakeMargin=30;fakeFreeMargin=fakeEquity-fakeMargin;
     e.action=direction;e.lockedAction=direction;e.lockedDirection=direction;e.analysisStart=start+300;e.targetTime=TimeCurrent();e.lastQuoteMs=now;
     e.anchor.volatility.atr=.0003;e.candidate.setup=1;e.candidate.invalidation=direction>0?1.09920:1.10090;
     if(mode==403){e.action=-direction;e.lockedAction=-direction;e.lockedDirection=-direction;}
     if(mode==404)e.analysisStart=start-300;
     if(mode==405){fakeNowMs=(start+1900)*1000;BOClockTick(TimeCurrent(),now);e.targetTime=TimeCurrent();e.lastQuoteMs=now;}
     if(mode==406)fakeOrders[0].sl+=direction*.0002;
     if(mode==408)fakeSendError=130;
     if(mode==409)fakeSendTimeoutAccepted=true;
     if(mode==416)fakeFXStorageDelayMs=4000;
     if(mode==417)fakeFillSlippage=.0008;
     if(mode==418)fakeOrders.push_back({90,OP_BUYLIMIT,77,"EURUSD","manual",.01,1.1,1.09,1.11,0,0,0,TimeCurrent(),0});
     if(mode==419){fakeEquity=981.5;fakeFreeMargin=fakeEquity-fakeMargin;}
     if(mode==420)fakeFreeMargin=20;
     if(mode==421){fakeBid=1.0989;fakeAsk=fakeBid+.0001;}
     if(mode==422){fxSettings.newsFilter=true;newsClock();}
     if(mode==423)FXWriteFlag(FXBasketFlag("reserved",primary),"INTERRUPTED_BEFORE_ACK");
     if(mode==424){int f=FileOpen(FXBasketPath(primary),FILE_WRITE|FILE_CSV|FILE_ANSI);FileWrite(f,"CORRUPTED");FileClose(f);}
     if(mode==426){fakeMargin=220;fakeFreeMargin=fakeEquity-fakeMargin;}
     if(mode==427){fakeFreeMargin=510;fakeMargin=fakeEquity-fakeFreeMargin;}
     if(mode==429)fxSettings.riskPercent=.3;
     if(mode==430)fxSettings.riskPercent=2;
     if(mode==431)FXWriteFlag(fxRoot+"\\close_required_"+IntegerToString(primary)+".csv","BASKET_EXIT_ALREADY_RESERVED");
     if(mode==432)FXWriteFlag(fxRoot+"\\intent_"+IntegerToString((long)e.targetTime)+".csv","TARGET_ALREADY_RESERVED");
     if(mode==433)fakeCloseOnMarginCheck=primary;
     if(mode==434)fakeManualOnMarginCheck=true;
     result=FXSend(e,now);
     if(mode==402){fakeNowMs+=300000;BOClockTick(TimeCurrent(),now);e.targetTime=TimeCurrent();e.analysisStart+=300;e.lastQuoteMs=now;FXSend(e,now);}
     if(mode==408){OnDeinit(0);init=OnInit();BOClockTick(TimeCurrent(),now);FXSend(e,now);FXManagePositions();}
     if(mode==409 || mode==417 || mode==421)FXManagePositions();
     if(mode==411 && fakeOrders.size()==2){auto child=fakeOrders.back();OrderSelect(child.ticket,SELECT_BY_TICKET,MODE_TRADES);OrderClose(child.ticket,child.lots,direction>0?fakeBid:fakeAsk,0,clrNONE);FXManagePositions();}
     if(mode==423 || mode==424){
      fakeOrders.push_back({90,OP_BUY,77,"EURUSD","manual",.01,1.1,1.09,1.11,0,0,0,TimeCurrent(),0});
      OnDeinit(0);init=OnInit();BOClockTick(TimeCurrent(),now);FXManagePositions();
     }
     if(mode==425 && fakeOrders.size()==2){auto parent=fakeOrders.front();OrderSelect(parent.ticket,SELECT_BY_TICKET,MODE_TRADES);OrderClose(parent.ticket,parent.lots,fakeBid,0,clrNONE);FXManagePositions();}
     if(mode==412){fakeNowMs=(birth+3601)*1000;BOClockTick(TimeCurrent(),now);FXManagePositions();}
     if(mode==413){OnDeinit(0);ForexEnableAveraging=false;ForexRiskPercent=2;init=OnInit();BOClockTick(TimeCurrent(),now);FXManagePositions();}
     if(mode==414){
      double total=0,weighted=0;for(auto o:fakeOrders){total+=o.lots;weighted+=o.price*o.lots;}weighted/=total;
      fakeBid=weighted+.0011;fakeAsk=fakeBid+.0001;FXManagePositions();
      gateA=fakeOrders.size()==2 && std::abs(fakeOrders[0].sl-fakeOrders[1].sl)<1e-8 && fakeOrders[0].sl>weighted;
     }
     if(mode==415){
      makeNews("High",TimeGMT()+240);fakeCloseFailure=true;FXManagePositions();
      gateA=FileIsExist(fxRoot+"\\close_required_"+IntegerToString(fakeOrders[0].ticket)+".csv") && FileIsExist(fxRoot+"\\close_required_"+IntegerToString(fakeOrders[1].ticket)+".csv");
      OnDeinit(0);init=OnInit();fakeCloseFailure=false;BOClockTick(TimeCurrent(),now);FXManagePositions();
     }
     if(mode==428){
      double total=0,weighted=0;for(auto o:fakeOrders){total+=o.lots;weighted+=o.price*o.lots;}weighted/=total;
      boHistoryReady=true;boHistoryBar=TimeCurrent()/300*300;boHistoryBars.clear();
      for(auto z:closedBars)boHistoryBars.push_back({z.time,z.open,z.high,z.low,z.close,z.ticks});
      fakeBid=weighted+.002;fakeAsk=fakeBid+.0001;FXManagePositions();
      firstSL=fakeOrders.front().sl;fakeNowMs+=6000;BOClockTick(TimeCurrent(),now);
      fakeBid=weighted+.0016;fakeAsk=fakeBid+.0001;FXManagePositions();
      gateA=fakeOrders.size()==2 && std::abs(fakeOrders.front().sl-fakeOrders.back().sl)<1e-8 && fakeOrders.front().sl>=firstSL;
     }
     FXBasket b{};recovered=FXAverageLoad(b);basketCount=b.count;basketBudget=b.budget;
     double total=0;
     if(recovered && b.count){
      for(int k=0;k<b.count;k++){total+=b.sizes[k];weightedEntry+=b.entries[k]*b.sizes[k];basketRisk+=(std::abs(b.entries[k]-b.stop)+.00008)/.00001*b.sizes[k];}
      weightedEntry/=total;
     }
     if(mode==400 || mode==401){OnDeinit(0);init=OnInit();BOClockTick(TimeCurrent(),now);FXManagePositions();FXBasket x{};gateB=FXAverageLoad(x) && x.count==2 && std::abs(x.budget-5)<1e-8;}
    }
    if(mode==109)FXSend(e,now);
    if(mode==110){fakeOrders.clear();fakeNowMs+=300000;BOClockTick(TimeCurrent(),now);e.targetTime=TimeCurrent();e.lastQuoteMs=now;FXSend(e,now);}
    if(mode==112){int h=FileOpen(fxRoot+"\\instance.lock",FILE_READ|FILE_WRITE|FILE_BIN);duplicateLock=h==INVALID_HANDLE;if(h!=INVALID_HANDLE)FileClose(h);}
    if(mode==117 && !fakeOrders.empty()){
     fakeOrders[0].sl=0;fakeOrders.push_back({89,OP_BUY,77,"EURUSD","manual",.01,1.1,0,0,0,0,0,TimeCurrent(),0});
     FXManagePositions();
    }
    if(mode==118 && !fakeOrders.empty()){
     fxSettings.enabled=false;fakeOrders[0].opened=TimeCurrent()-3601;FXManagePositions();
    }
    if(mode==119){OnDeinit(0);TradingMode=BinaryOption;switchInit=OnInit();TradingMode=Forex;}
    if(mode==150)FXSend(e,now);
    if(mode==151){
     FXDayGuard(now/1000);fakeEquity=9700;dayOK=FXDayGuard(now/1000);
     fakeEquity=10000;fakeNowMs+=86400000;BOClockTick(TimeCurrent(),now);restartDayOK=FXDayGuard(now/1000);
    }
    if(mode==152 && !fakeOrders.empty()){
     fakeOrders[0].sl=0;fakeCloseFailure=true;FXManagePositions();fakeCloseFailure=false;fakeNowMs+=1000;FXManagePositions();
    }
    if(mode==120){
     if(!fakeOrders.empty()){OrderSelect(0,SELECT_BY_POS,MODE_TRADES);OrderClose(OrderTicket(),OrderLots(),fakeBid,0,clrNONE);}
     OnDeinit(0);init=OnInit();BOClockTick(TimeCurrent(),now);FXSend(e,now);
    }
    if(mode==121){
     OnDeinit(0);fakeEquity=10000;init=OnInit();BOClockTick(TimeCurrent(),now);restartDayOK=FXDayGuard(now/1000);
    }
   }
  }
  bool healthy=fxHealthy;string status=fxStatus,root=fxRoot;StringReplace(root,"\\","/");
  bool review=FileIsExist(fxRoot+"\\execution_review_required.csv");
  OnDeinit(0);
  std::cout<<"{\"init\":"<<init<<",\"result\":"<<result<<",\"send_calls\":"<<fakeSendCalls
   <<",\"close_calls\":"<<fakeCloseCalls<<",\"orders\":"<<fakeOrders.size()<<",\"healthy\":"<<healthy
   <<",\"status\":\""<<status<<"\",\"root\":\""<<root<<"\",\"lots\":"<<lots<<",\"stop\":"<<stop
   <<",\"take\":"<<take<<",\"price\":"<<price<<",\"review\":"<<review<<",\"duplicate_lock\":"<<duplicateLock
   <<",\"day_ok\":"<<dayOK<<",\"restart_day_ok\":"<<restartDayOK<<",\"baseline\":"<<baseline
   <<",\"basket_budget\":"<<basketBudget<<",\"basket_risk\":"<<basketRisk<<",\"basket_count\":"<<basketCount<<",\"weighted_entry\":"<<weightedEntry
   <<",\"news_status\":\""<<fxNewsStatus<<"\""
   <<",\"modify_calls\":"<<fakeModifyCalls<<",\"first_sl\":"<<firstSL<<",\"second_sl\":"<<secondSL<<",\"final_sl\":"<<finalSL<<",\"original_r\":"<<originalRisk<<",\"recovered\":"<<recovered<<",\"gate_a\":"<<gateA<<",\"gate_b\":"<<gateB<<",\"gate_c\":"<<gateC<<",\"risk\":"<<risk
   <<",\"switch_init\":"<<switchInit<<",\"slippage_points\":"<<fakeSlippagePoints<<"}";
  return 0;
 }
'''
        needle=' if(mode==22 || mode==23){';assert needle in code;code=code.replace(needle,branch+needle)
        needle='std::cout<<"{\\"embedded_status\\":'
        assert needle in code
        code=code.replace(needle,'std::cout<<"{\\"broker_order_calls\\":"<<fakeSendCalls<<",\\"embedded_status\\":')
        path.write_text(code)
        proc=subprocess.run(['g++','-std=c++17','-O1',str(path),'-o',str(cls.binary)],capture_output=True,text=True)
        if proc.returncode:raise RuntimeError(proc.stderr)

    def run_case(self,folder,mode=100,direction=1,testing=False,dashboard=None):
        bars=sr_bars(direction)
        text=f'{START} {len(bars)}\n'+'\n'.join(f'{b.time} {b.open:.17g} {b.high:.17g} {b.low:.17g} {b.close:.17g} {b.ticks}' for b in bars)+'\n'
        args=[str(self.binary),str(folder),str(mode),'5',str(int(testing))]
        if dashboard is not None:args+=['0','v229_demo',str(int(dashboard))]
        proc=subprocess.run(args,input=text,capture_output=True,text=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        return json.loads(proc.stdout)

    def test_dashboard_on_off_preserves_native_orders_and_journals_byte_for_byte(self):
        for mode in (140,141,102,330):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
                left=self.run_case(a,mode,dashboard=True)
                right=self.run_case(b,mode,dashboard=False)
                self.assertEqual(left,right)
                files=lambda root:{p.relative_to(root).as_posix():p.read_bytes() for p in Path(root).rglob('*') if p.is_file()}
                self.assertEqual(files(a),files(b))

    def test_recovered_real_zero_balance_credit_never_opens(self):
        for mode in (600,601):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode)
                self.assertEqual(r['init'],0);self.assertEqual(r['send_calls'],0);self.assertEqual(r['orders'],0)

    def test_recovered_real_negative_or_tiny_capital_never_forces_min_lot(self):
        for mode in (602,603,612):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['send_calls'],0);self.assertEqual(r['orders'],0)

    def test_recovered_real_uses_lower_balance_or_equity_for_risk(self):
        for mode in (604,605,606):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertTrue(r['result']);self.assertEqual(r['send_calls'],1)
                self.assertLessEqual(r['lots']*(abs(r['price']-r['stop'])+.00005)/.00001,5.000001)

    def test_recovered_real_requires_real_input_terminal_permission_and_enabled_entry(self):
        for mode in (607,608,609):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['init'],0);self.assertEqual(r['send_calls'],0)

    def test_recovered_real_can_open_after_deposit_without_reinitializing(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,610);self.assertTrue(r['result']);self.assertEqual(r['send_calls'],1)

    def test_recovered_real_zero_balance_does_not_disable_existing_position_management(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,611);self.assertEqual(r['send_calls'],1)
            self.assertEqual(r['close_calls'],1);self.assertEqual(r['orders'],0)

    def test_demo_order_has_structural_atr_stop_take_and_risk_bounded_lots(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp)
            self.assertEqual(r['init'],0);self.assertEqual(r['send_calls'],1);self.assertEqual(r['orders'],1)
            self.assertLess(r['stop'],r['price']);self.assertGreater(r['take'],r['price'])
            self.assertLessEqual(r['lots']*((r['price']-r['stop']+.00008)/.00001),50.0001)
            self.assertAlmostEqual(r['take']-r['price'],2*(r['price']-r['stop']),places=5)
            root=Path(tmp)/r['root'];self.assertTrue((root/'forex_events.csv').exists())
            self.assertFalse((root/'data_origin.csv').exists());self.assertFalse(list(root.glob('event_*.bin')))

    def test_real_account_requires_explicit_input_and_demo_remains_available(self):
        for mode,orders in [(101,0),(102,1),(100,1)]:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['send_calls'],orders)
                if mode==101:self.assertEqual(r['status'],'REAL_TRADING_DISABLED')

    def test_account_permission_and_entry_quality_fail_closed(self):
        modes={103:'TRADING_DISABLED',104:'SPREAD_LIMIT',105:'MIN_LOT_EXCEEDS_RISK',106:'INVALID_MARKET_METADATA',
               107:'STOP_TOO_WIDE',108:'INSUFFICIENT_MARGIN',113:'TERMINAL_TRADING_UNAVAILABLE',
               114:'NATIVE_ENTRY_NOT_ALLOWED',115:'NATIVE_ENTRY_NOT_ALLOWED',123:'EXNESS_ACCOUNT_REQUIRED',
               124:'EURUSD_ORDER_ALREADY_EXISTS',128:'INVALID_STRUCTURAL_STOP',130:'UNSUPPORTED_ACCOUNT_MODE',
               131:'ENTRY_QUOTE_TOO_OLD_OR_LATE',133:'TERMINAL_TRADING_UNAVAILABLE',134:'TERMINAL_TRADING_UNAVAILABLE',135:'TRADING_DISABLED'}
        modes[138]='INVALID_MARKET_METADATA'
        for mode,status in modes.items():
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['send_calls'],0);self.assertEqual(r['status'],status)

    def test_invalid_risk_and_nan_are_rejected_at_initialization(self):
        for mode in (127,132):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['init'],2);self.assertEqual(r['send_calls'],0)

    def test_four_digit_quotes_and_lot_step_round_down(self):
        for mode,step in [(125,.01),(126,.1)]:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['orders'],1)
                self.assertAlmostEqual(r['lots']/step,round(r['lots']/step),places=7)
                self.assertLessEqual(r['lots']*((r['price']-r['stop']+.00008)/.00001),50.0001)

    def test_slippage_maximum_is_not_rounded_up_to_a_larger_pip_limit(self):
        for mode,expected in [(100,3),(125,0)]:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['send_calls'],1);self.assertEqual(r['slippage_points'],expected)

    def test_rejection_and_restart_do_not_resend_same_intent(self):
        for mode in (109,120):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['send_calls'],1);self.assertEqual(r['status'],'EXIT_COOLDOWN' if mode==120 else 'ENTRY_ALREADY_ATTEMPTED')

    def test_accepted_timeout_persists_uncertain_execution_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,110);self.assertEqual(r['send_calls'],1);self.assertTrue(r['review'])
            self.assertEqual(r['status'],'ORDER_STATE_REVIEW_REQUIRED')

    def test_storage_failure_and_elapsed_io_never_create_backdated_order(self):
        for mode in (111,116):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['send_calls'],0)
                if mode==111:self.assertFalse(r['healthy'])

    def test_account_symbol_lease_prevents_second_owner(self):
        with tempfile.TemporaryDirectory() as tmp:self.assertTrue(self.run_case(tmp,112)['duplicate_lock'])

    def test_manager_protects_own_orders_only_and_works_with_entries_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,117);self.assertEqual(r['close_calls'],1);self.assertEqual(r['orders'],1)
            root=Path(tmp)/r['root'];rows=list(root.glob('forex_closed_*.csv'));self.assertEqual(len(rows),1)
            with rows[0].open() as f:self.assertIn('net',next(csv.reader(f)))
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,118);self.assertEqual(r['close_calls'],1);self.assertEqual(r['orders'],0)

    def test_unprotected_broker_fill_is_closed_without_naked_order_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,136);self.assertEqual(r['send_calls'],1);self.assertEqual(r['close_calls'],1);self.assertEqual(r['orders'],0)

    def test_excessive_actual_fill_risk_triggers_close_without_another_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,137);self.assertEqual(r['send_calls'],1);self.assertEqual(r['close_calls'],1);self.assertEqual(r['orders'],0)

    def test_second_attempt_with_open_position_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,150);self.assertEqual(r['send_calls'],1);self.assertEqual(r['status'],'EURUSD_ORDER_ALREADY_EXISTS')

    def test_new_broker_day_resets_daily_halt_without_rewriting_previous_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,151);self.assertFalse(r['day_ok']);self.assertTrue(r['restart_day_ok'])
            self.assertEqual(len(list((Path(tmp)/r['root']).glob('risk_day_*.csv'))),2)

    def test_protection_close_failure_is_retried_as_close_not_another_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,152);self.assertEqual(r['send_calls'],1);self.assertEqual(r['close_calls'],2);self.assertEqual(r['orders'],0)

    def test_switch_to_binary_is_blocked_while_forex_position_exists(self):
        with tempfile.TemporaryDirectory() as tmp:self.assertEqual(self.run_case(tmp,119)['switch_init'],1)

    def test_daily_equity_limit_latches_and_survives_restart_and_equity_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,121);self.assertEqual(r['baseline'],10000);self.assertFalse(r['day_ok'])
            self.assertFalse(r['restart_day_ok']);self.assertEqual(r['send_calls'],0)

    def test_corrupted_persisted_risk_baseline_blocks_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,122);self.assertFalse(r['healthy']);self.assertEqual(r['send_calls'],0)

    def test_full_native_setup_confirmation_lock_and_entry_buy_and_sell(self):
        for direction in (1,-1):
            with self.subTest(direction=direction),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,140,direction);self.assertEqual(r['send_calls'],1);self.assertEqual(r['orders'],1)
                with next((Path(tmp)/r['root']).glob('forex_anchor_*.csv')).open() as f:self.assertEqual(len(list(csv.reader(f))),66)

    def test_sparse_tick_guard_and_restart_before_entry_do_not_create_orders(self):
        for mode in (141,142):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                self.assertEqual(self.run_case(tmp,mode)['send_calls'],0)

    def test_tester_forex_executes_broker_api_but_uses_separate_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,140,testing=True);self.assertEqual(r['send_calls'],1)
            self.assertIn('_TESTER_',r['root']);self.assertFalse((Path(tmp)/'BO_V2').exists())

    def test_binary_default_never_calls_broker_order_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            r,_=self.execute(tmp);self.assertEqual(r['broker_order_calls'],0)


    def test_break_even_uses_bid_for_buy_and_ask_for_sell(self):
        for mode in (201,202,204):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['modify_calls'],1)
                if mode==202:self.assertLess(r['final_sl'],r['price'])
                else:self.assertGreaterEqual(r['final_sl'],r['price'])
                self.assertEqual(r['send_calls'],1)

    def test_atr_trailing_tightens_and_never_retreats_on_pullback(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,203);self.assertEqual(r['modify_calls'],2)
            self.assertGreater(r['second_sl'],r['first_sl']);self.assertEqual(r['final_sl'],r['second_sl'])

    def test_freeze_level_and_stale_quotes_defer_stop_modification(self):
        for mode in (205,214):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['modify_calls'],0);self.assertEqual(r['orders'],1)

    def test_rejected_modify_has_backoff_and_retries_without_new_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,206);self.assertTrue(r['gate_a']);self.assertEqual(r['modify_calls'],2)
            self.assertGreaterEqual(r['final_sl'],r['price']);self.assertEqual(r['send_calls'],1)

    def test_timeout_with_applied_stop_does_not_repeat_same_modification(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,207);self.assertEqual(r['modify_calls'],1);self.assertEqual(r['send_calls'],1)

    def test_original_r_is_preserved_after_break_even_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,208);self.assertTrue(r['recovered'])
            self.assertAlmostEqual(r['original_r'],r['price']-r['stop'],places=5)
            self.assertEqual(r['modify_calls'],1);self.assertEqual(r['final_sl'],r['first_sl'])

    def test_corrupted_position_state_blocks_entries_and_requests_owned_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,209);self.assertFalse(r['healthy']);self.assertEqual(r['orders'],0)
            self.assertEqual(r['close_calls'],1)

    def test_excess_fill_risk_close_intent_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,211);self.assertEqual(r['close_calls'],2);self.assertEqual(r['orders'],0)
            self.assertEqual(r['send_calls'],1)

    def test_emergency_exit_closes_owned_position_and_blocks_new_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,212);self.assertEqual(r['close_calls'],1);self.assertEqual(r['orders'],1)
            self.assertEqual(r['status'],'EMERGENCY_CLOSE_ACTIVE')

    def test_daily_equity_halt_can_close_owned_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,213);self.assertEqual(r['orders'],0);self.assertEqual(r['close_calls'],1)

    def test_disconnected_close_is_persisted_and_retried_after_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,216);self.assertTrue(r['gate_a']);self.assertEqual(r['orders'],0)
            self.assertEqual(r['send_calls'],1)

    def test_invalid_trailing_settings_fail_before_any_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,215);self.assertEqual(r['init'],2);self.assertEqual(r['send_calls'],0)

    def test_daily_attempt_budget_is_persistent_and_counts_rejected_sends(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,230);self.assertEqual(r['send_calls'],6)
            self.assertEqual(r['status'],'DAILY_ENTRY_ATTEMPT_LIMIT')

    def test_loss_streak_limit_survives_restart_and_resets_next_broker_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,231);self.assertFalse(r['gate_a']);self.assertFalse(r['gate_b']);self.assertTrue(r['gate_c'])

    def test_streak_is_chronological_and_net_of_costs(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,232);self.assertTrue(r['gate_a']);self.assertEqual(r['baseline'],2)
            self.assertTrue(r['gate_b']);self.assertEqual(r['risk'],0)

    def test_exit_cooldown_survives_restart_and_expires_by_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,233);self.assertFalse(r['gate_a']);self.assertTrue(r['gate_b'])

    def test_corrupted_attempt_counter_fail_stops_new_entries(self):
        with tempfile.TemporaryDirectory() as tmp:self.assertFalse(self.run_case(tmp,234)['healthy'])

    def test_weekend_friday_and_rollover_schedule_use_broker_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,235);self.assertTrue(r['gate_a']);self.assertFalse(r['gate_b']);self.assertTrue(r['gate_c'])
            self.assertEqual(r['baseline'],0);self.assertEqual(r['risk'],1);self.assertTrue(r['recovered'])
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,236);self.assertFalse(r['gate_a']);self.assertFalse(r['gate_b']);self.assertTrue(r['gate_c'])

    def test_friday_close_failure_remains_required_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,237);self.assertTrue(r['gate_a']);self.assertEqual(r['orders'],0)
            self.assertEqual(r['close_calls'],2);self.assertEqual(r['send_calls'],1)



    def test_forex_news_blocks_unknown_stale_uncertain_corrupt_and_tester_current_calendar(self):
        expected={300:'NEWS_UNKNOWN',302:'NEWS_STALE',303:'NEWS_TIME_UNCERTAIN',304:'NEWS_UNKNOWN',305:'NEWS_CLOCK_UNCERTAIN',306:'NEWS_TESTER_NO_HISTORICAL_CALENDAR'}
        for mode,status in expected.items():
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['send_calls'],0);self.assertEqual(r['status'],status)

    def test_high_medium_news_windows_and_entry_lookahead(self):
        for mode,expected in [(301,1),(307,1),(308,0),(309,0),(310,1),(311,1)]:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['send_calls'],expected,r)

    def test_high_news_closes_owned_position_before_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,320);self.assertEqual(r['orders'],0);self.assertEqual(r['close_calls'],1)

    def test_medium_news_reduces_profitable_unsecured_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,321);self.assertEqual(r['orders'],1);self.assertEqual(r['close_calls'],1)
            self.assertAlmostEqual(r['final_sl'],r['lots']/2,places=2);self.assertTrue(r['recovered'])

    def test_medium_news_closes_loser_and_preserves_secured_profit(self):
        for mode,closes,orders in [(322,1,0),(323,0,1),(324,1,0)]:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['close_calls'],closes);self.assertEqual(r['orders'],orders)

    def test_partial_news_close_is_not_repeated_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,325);self.assertEqual(r['close_calls'],1);self.assertEqual(r['orders'],1)
            self.assertAlmostEqual(r['first_sl'],r['final_sl'],places=7)

    def test_partial_close_preserves_original_maximum_hold_deadline(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,326);self.assertEqual(r['close_calls'],2);self.assertEqual(r['orders'],0)

    def test_rejected_partial_close_escalates_to_durable_full_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,327);self.assertEqual(r['close_calls'],3);self.assertEqual(r['orders'],0)
            self.assertEqual(r['send_calls'],1)

    def test_stale_quotes_do_not_send_news_partial_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,329);self.assertEqual(r['close_calls'],0);self.assertEqual(r['orders'],1)



    def test_medium_news_partial_close_also_handles_sell_positions(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,330);self.assertEqual(r['close_calls'],1);self.assertEqual(r['orders'],1)
            self.assertAlmostEqual(r['final_sl'],r['lots']/2,places=2);self.assertTrue(r['recovered'])

    def test_reserved_but_unconfirmed_partial_reconciles_as_full_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,331);self.assertEqual(r['close_calls'],1);self.assertEqual(r['orders'],0)



    def test_averaging_buy_and_sell_share_original_budget_and_survive_restart(self):
        for mode in (400,401):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['send_calls'],2);self.assertEqual(r['orders'],2)
                self.assertAlmostEqual(r['lots'],.03);self.assertEqual(r['basket_count'],2)
                self.assertAlmostEqual(r['basket_budget'],5);self.assertLessEqual(r['basket_risk'],5)
                self.assertTrue(r['gate_b']);self.assertTrue(r['recovered'])
                if mode==400:self.assertLess(r['weighted_entry'],r['price'])
                else:self.assertGreater(r['weighted_entry'],r['price'])

    def test_averaging_is_bounded_to_one_addition(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,402);self.assertEqual(r['send_calls'],2);self.assertEqual(r['orders'],2)

    def test_averaging_requires_new_same_direction_setup_and_original_stop(self):
        for mode in (403,404,405,406,407,418,419,420,421):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['send_calls'],1,r)

    def test_averaging_reject_does_not_retry_basket_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,408);self.assertEqual(r['send_calls'],2);self.assertEqual(r['orders'],1)
            self.assertTrue(r['recovered']);self.assertFalse(r['review'])

    def test_ambiguous_averaging_fill_closes_owned_basket_without_resend(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,409);self.assertEqual(r['send_calls'],2);self.assertEqual(r['orders'],0);self.assertTrue(r['review'])

    def test_invalid_averaging_inputs_are_rejected_before_opening(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,410);self.assertEqual(r['init'],2);self.assertEqual(r['send_calls'],0)

    def test_loss_of_one_basket_leg_closes_the_survivor(self):
        for mode in (411,425):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['orders'],0);self.assertEqual(r['close_calls'],2)
                self.assertFalse(r['review'])

    def test_averaging_hold_deadline_is_the_original_open_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,412);self.assertEqual(r['orders'],0);self.assertEqual(r['close_calls'],2)

    def test_disabling_additions_and_increasing_risk_does_not_expand_existing_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,413);self.assertEqual(r['send_calls'],2);self.assertEqual(r['orders'],2)
            self.assertAlmostEqual(r['basket_budget'],5);self.assertTrue(r['recovered'])

    def test_basket_break_even_uses_weighted_price_and_common_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,414);self.assertTrue(r['gate_a']);self.assertEqual(r['modify_calls'],2)

    def test_news_reserves_entire_basket_close_and_retries_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,415);self.assertTrue(r['gate_a']);self.assertEqual(r['orders'],0)
            self.assertEqual(r['send_calls'],2)

    def test_slow_storage_cancels_addition_without_issuing_late_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,416);self.assertEqual(r['send_calls'],1);self.assertEqual(r['orders'],1)

    def test_bad_average_fill_is_closed_instead_of_chasing_another_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,417);self.assertEqual(r['send_calls'],2);self.assertEqual(r['orders'],0)
            self.assertTrue(r['review'])

    def test_unknown_news_blocks_addition_without_dropping_existing_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,422);self.assertEqual(r['send_calls'],1);self.assertEqual(r['orders'],1)
            self.assertGreater(r['stop'],0);self.assertTrue(r['recovered'])

    def test_interrupted_or_corrupt_basket_closes_owned_position_and_preserves_manual(self):
        for mode in (423,424):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['send_calls'],1);self.assertEqual(r['orders'],1)
                self.assertTrue(r['review']);self.assertEqual(r['close_calls'],1)

    def test_positive_free_margin_does_not_bypass_margin_reserve(self):
        for mode in (426,427):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['send_calls'],1);self.assertEqual(r['orders'],1)
                self.assertEqual(r['status'],'MARGIN_RESERVE_LIMIT')

    def test_weighted_basket_trailing_never_moves_stop_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,428);self.assertTrue(r['gate_a']);self.assertEqual(r['orders'],2)
            self.assertGreater(r['first_sl'],r['weighted_entry'])

    def test_addition_never_reopens_a_closing_basket_or_reuses_target_intent(self):
        for mode in (431,432):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['send_calls'],1);self.assertEqual(r['orders'],1)
                self.assertIn(r['status'],('AVERAGE_BASKET_EXIT_PENDING','ENTRY_ALREADY_ATTEMPTED'))

    def test_parent_close_or_manual_exposure_during_preflight_prevents_addition(self):
        for mode,orders in ((433,0),(434,2)):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                r=self.run_case(tmp,mode);self.assertEqual(r['send_calls'],1);self.assertEqual(r['orders'],orders)
                self.assertEqual(r['status'],'AVERAGE_PARENT_OR_EXPOSURE_CHANGED')

    def test_current_risk_can_restrict_but_cannot_expand_saved_basket_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,429);self.assertEqual(r['send_calls'],1)
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_case(tmp,430);self.assertEqual(r['send_calls'],2)
            self.assertAlmostEqual(r['basket_budget'],5);self.assertLessEqual(r['basket_risk'],5)


if __name__=='__main__':unittest.main()
