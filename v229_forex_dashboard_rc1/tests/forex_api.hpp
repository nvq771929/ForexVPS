// Test-only broker API. No network or real account connections.
#define OP_BUY 0
#define OP_SELL 1
#define OP_BUYLIMIT 2
#define SELECT_BY_POS 0
#define SELECT_BY_TICKET 1
#define MODE_TRADES 0
#define MODE_HISTORY 1
#define MODE_TICKVALUE 20
#define MODE_MINLOT 21
#define MODE_LOTSTEP 22
#define MODE_MAXLOT 23
#define MODE_STOPLEVEL 24
#define MODE_FREEZELEVEL 26
#define MODE_TRADEALLOWED 25
#define SYMBOL_TRADE_TICK_SIZE 30
#define ACCOUNT_TRADE_MODE 40
#define ACCOUNT_TRADE_MODE_DEMO 0
#define ACCOUNT_TRADE_MODE_REAL 2
#define clrNONE -1
double Point=.00001;
double MathFloor(double x){return std::floor(x);}
double MathCeil(double x){return std::ceil(x);}
double NormalizeDouble(double x,int n){double s=std::pow(10.,n);return std::round(x*s)/s;}
double fakeBalance=10000.,fakeEquity=10000.,fakeFreeMargin=10000.,fakeMargin=0;
double fakeTickValue=1.,fakeTickSize=.00001,fakeMinLot=.01,fakeLotStep=.01,fakeMaxLot=100.;
int fakeAccountMode=0,fakeStopLevel=10,fakeAccountNumber=100;
bool fakeTradingAllowed=true,fakeTradeBusy=false,fakeMarketAllowed=true,fakeCloseFailure=false;
int fakeSendError=0,fakeSendCalls=0,fakeCloseCalls=0;bool fakeSendTimeoutAccepted=false,fakeNakedFill=false;
int fakeSlippagePoints=-1,fakeFreezeLevel=0,fakeModifyCalls=0,fakeModifyError=0;
bool fakeModifyTimeoutAccepted=false;
long long fakeSendDelayMs=0;
double fakeFillSlippage=0;
long AccountInfoInteger(int){return fakeAccountMode;}
int AccountNumber(){return fakeAccountNumber;}
double AccountBalance(){return fakeBalance;}
double AccountEquity(){return fakeEquity;}
double AccountMargin(){return fakeMargin;}
double AccountFreeMargin(){return fakeFreeMargin;}
string AccountCurrency(){return "USD";}
bool IsTradeAllowed(){return fakeTradingAllowed;}
bool IsTradeContextBusy(){return fakeTradeBusy;}
double SymbolInfoDouble(const string&,int){return fakeTickSize;}
double MarketInfo(const string&,int mode){switch(mode){
 case MODE_TICKVALUE:return fakeTickValue;case MODE_MINLOT:return fakeMinLot;
 case MODE_LOTSTEP:return fakeLotStep;case MODE_MAXLOT:return fakeMaxLot;
 case MODE_FREEZELEVEL:return fakeFreezeLevel;case MODE_STOPLEVEL:return fakeStopLevel;case MODE_TRADEALLOWED:return fakeMarketAllowed;
 }return 0;}
double AccountFreeMarginCheck(const string&,int,double lots);
struct FakeOrder {int ticket,type,magic;string symbol,comment;double lots,price,sl,tp,profit=0,swap=0,commission=0;datetime opened,closed=0;};
std::vector<FakeOrder>fakeOrders,fakeOrderHistory;int selectedPool=0,selectedIndex=-1,nextTicket=1000;
FakeOrder& selectedOrder(){return selectedPool==MODE_TRADES ? fakeOrders.at(selectedIndex):fakeOrderHistory.at(selectedIndex);}
int OrdersTotal(){return fakeOrders.size();}
int OrdersHistoryTotal(){return fakeOrderHistory.size();}
bool OrderSelect(int id,int selection,int pool=MODE_TRADES){
 auto&v=pool==MODE_TRADES ? fakeOrders:fakeOrderHistory;
 if(selection==SELECT_BY_POS){if(id<0 || id>=int(v.size()))return false;selectedIndex=id;selectedPool=pool;return true;}
 // MT4 SELECT_BY_TICKET ignores the pool and can select an already closed order.
 for(int actualPool=0;actualPool<=1;actualPool++){
  auto &tickets=actualPool==MODE_TRADES ? fakeOrders:fakeOrderHistory;
  for(size_t i=0;i<tickets.size();i++)if(tickets[i].ticket==id){selectedIndex=i;selectedPool=actualPool;return true;}
 }
 return false;
}
string OrderSymbol(){return selectedOrder().symbol;}
string OrderComment(){return selectedOrder().comment;}
int OrderMagicNumber(){return selectedOrder().magic;}
int OrderType(){return selectedOrder().type;}
int OrderTicket(){return selectedOrder().ticket;}
double OrderLots(){return selectedOrder().lots;}
double OrderOpenPrice(){return selectedOrder().price;}
double OrderStopLoss(){return selectedOrder().sl;}
double OrderTakeProfit(){return selectedOrder().tp;}
datetime OrderOpenTime(){return selectedOrder().opened;}
datetime OrderCloseTime(){return selectedOrder().closed;}
double OrderProfit(){return selectedOrder().profit;}
double OrderSwap(){return selectedOrder().swap;}
double OrderCommission(){return selectedOrder().commission;}
int OrderSend(const string&symbol,int cmd,double lots,double price,int deviation,double sl,double tp,const string&comment,int magic,datetime,color){
 fakeSendCalls++;fakeSlippagePoints=deviation;fakeNowMs+=fakeSendDelayMs;fakeSendDelayMs=0;
 if(fakeSendError && !fakeSendTimeoutAccepted){lastError=fakeSendError;return -1;}
 int ticket=nextTicket++;fakeOrders.push_back({ticket,cmd,magic,symbol,comment,lots,price+(cmd==OP_BUY?1:-1)*fakeFillSlippage,fakeNakedFill?0:sl,fakeNakedFill?0:tp,0,0,0,TimeCurrent(),0});
 if(fakeSendTimeoutAccepted){lastError=128;return -1;}
 return ticket;
}
bool OrderClose(int ticket,double lots,double price,int,color){
 fakeCloseCalls++;if(fakeCloseFailure){lastError=136;return false;}
 for(size_t i=0;i<fakeOrders.size();i++)if(fakeOrders[i].ticket==ticket){
  auto order=fakeOrders[i];order.closed=TimeCurrent();
  order.profit=(price-order.price)*(order.type==OP_BUY?1:-1)/fakeTickSize*fakeTickValue*lots;
  order.lots=lots;fakeOrderHistory.push_back(order);
  if(lots<fakeOrders[i].lots-1e-9){
   auto residual=fakeOrders[i];residual.ticket=nextTicket++;residual.lots-=lots;residual.comment="from #"+std::to_string(ticket);residual.opened=TimeCurrent();
   fakeOrders[i]=residual;
  }else fakeOrders.erase(fakeOrders.begin()+i);
  selectedIndex=-1;return true;}
 lastError=4108;return false;
}

bool OrderModify(int ticket,double,double sl,double tp,datetime,color){
 fakeModifyCalls++;
 if(fakeModifyError && !fakeModifyTimeoutAccepted){lastError=fakeModifyError;return false;}
 for(auto &order:fakeOrders)if(order.ticket==ticket){order.sl=sl;order.tp=tp;
  if(fakeModifyTimeoutAccepted){lastError=128;return false;}return true;}
 lastError=4108;return false;
}
int fakeCloseOnMarginCheck=-1;bool fakeManualOnMarginCheck=false;
double AccountFreeMarginCheck(const string&,int,double lots){
 if(fakeCloseOnMarginCheck>0){int ticket=fakeCloseOnMarginCheck;fakeCloseOnMarginCheck=-1;
  if(OrderSelect(ticket,SELECT_BY_TICKET) && OrderCloseTime()==0)OrderClose(ticket,OrderLots(),fakeBid,0,clrNONE);}
 if(fakeManualOnMarginCheck){fakeManualOnMarginCheck=false;fakeOrders.push_back({90,OP_BUY,77,"EURUSD","manual",.01,1.1,1.09,1.11,0,0,0,TimeCurrent(),0});}
 return fakeFreeMargin-lots*1000;
}
