"""Forex-specific chart objects and read-only presentation semantics, not MT4 screenshots."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tests.test_demo_learning_native import NativeHarness
from tests.fixtures import START, sr_bars

ROOT=Path(__file__).resolve().parents[1]


class ForexDashboardTests(NativeHarness,unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        shim=cls.native_shim.replace('bool ObjectDelete(long long,const string&){return true;}',r'''
bool ObjectDelete(long long,const string&name){
 for(auto i=objectStrings.begin();i!=objectStrings.end();)if(i->first.first==name)i=objectStrings.erase(i);else ++i;
 for(auto i=objectIntegers.begin();i!=objectIntegers.end();)if(i->first.first==name)i=objectIntegers.erase(i);else ++i;
 return true;
}
''')
        main=r'''
int main(int argc,char**argv){
 filesRoot=argv[1];int scenario=std::stoi(argv[2]);long long start;int count;std::cin>>start>>count;
 for(int i=0;i<count;i++){FakeBar b;std::cin>>b.time>>b.open>>b.high>>b.low>>b.close>>b.ticks;closedBars.push_back(b);addBar(b);}
 fakeNowMs=start*1000;fakeServer="Exness-Demo";TradingMode=Forex;
 if(scenario==701){fakeAccountMode=ACCOUNT_TRADE_MODE_REAL;fakeServer="Exness-Real18";}
 if(scenario==702)fakeTradingAllowed=false;
 if(scenario==703)connected=false;
 if(scenario==712){PanelFontSize=18;PanelFontName="Consolas";PanelLeft=36;PanelTop=44;}
 if(scenario==713)ForexUseDashboard=false;
 if(scenario==715)TradingMode=BinaryOption;
 if(scenario==720)ForexMaxHoldMinutes=0;
 int init=OnInit();long now=0;BOClockTick(TimeCurrent(),now);
 if(scenario==704)fxDayHalted=true;
 if(scenario==705)fxHealthy=false;
 if(scenario==716)fxDayEquity=0;
 if(scenario==717){fakeBalance=0;fakeEquity=100;}
 if(scenario==718){fakeAsk=fakeBid+.0003;}
 if(scenario==719){fakeQuoteAgeSeconds=10;}
 if(scenario==706 || scenario==708 || scenario==709 || scenario==710 || scenario==711){
  fakeOrders.push_back({88,OP_BUY,2220520,"EURUSD","FX222:test",.01,1.10010,1.09910,1.10210,12.5,-.5,-1,start-600,0});
  OrderSelect(0,SELECT_BY_POS,MODE_TRADES);FXSaveOriginalRisk();
  if(scenario==708){fakeOrders[0].opened=start-60;OrderSelect(0,SELECT_BY_POS,MODE_TRADES);
   FXSaveState(fxRoot+"\\position_88.csv","V222_FOREX_POSITION_V1",FXPositionKey()+"|0.00100|"+IntegerToString(start-1200));}
  if(scenario==709){std::ofstream f(nativePath(fxRoot+"\\position_88.csv"));f<<"BROKEN\n";}
  if(scenario==710)fakeOrders[0].sl=0;
  if(scenario==711){fakeOrders.push_back({89,OP_SELL,2220520,"EURUSD","FX222:test",.02,1.1,1.101,1.098,-5,0,0,start-60,0});}
  fakeOrders.push_back({99,OP_BUY,77,"EURUSD","manual",.5,1.1,1.09,1.11,100,0,0,start-60,0});
 }
 fxNewsStatus="NEWS_CLOCK_UNCERTAIN";
 string status=fxStatus;bool healthy=fxHealthy,halt=fxDayHalted;double day=fxDayEquity;
 FXSettings settings=fxSettings;BOPrediction episode=fxEpisode;int orders=fakeOrders.size();
 int sends=fakeSendCalls,closes=fakeCloseCalls,modifies=fakeModifyCalls;
 if(scenario!=715)for(int i=0;i<3;i++)FXRender();
 bool changed=fxStatus!=status || fxHealthy!=healthy || fxDayHalted!=halt || fxDayEquity!=day ||
  std::memcmp(&settings,&fxSettings,sizeof(settings))!=0 || std::memcmp(&episode,&fxEpisode,sizeof(episode))!=0 ||
  orders!=int(fakeOrders.size()) || sends!=fakeSendCalls || closes!=fakeCloseCalls || modifies!=fakeModifyCalls;
 BOUILabel("BO_TEST_SENTINEL","Binary on its own chart",12,12,14,clrWhiteSmoke,"Arial");
 if(scenario==714)OnDeinit(0);
 bool sentinel=objectStrings.count({"BO_TEST_SENTINEL",OBJPROP_TEXT})>0;
 std::cout<<"{\"init\":"<<init<<",\"mutated\":"<<changed<<",\"binary_untouched\":"<<sentinel
  <<",\"legacy_comment\":"<<(!latestComment.empty())<<",\"background\":"<<objectIntegers.count({"FX_V229_BACKGROUND",OBJPROP_XSIZE})
  <<",\"width\":"<<objectIntegers[{"FX_V229_BACKGROUND",OBJPROP_XSIZE}]<<",\"height\":"<<objectIntegers[{"FX_V229_BACKGROUND",OBJPROP_YSIZE}]
  <<",\"left\":"<<objectIntegers[{"FX_V229_BACKGROUND",OBJPROP_XDISTANCE}]<<",\"top\":"<<objectIntegers[{"FX_V229_BACKGROUND",OBJPROP_YDISTANCE}]
  <<",\"labels\":[";bool first=true;
 for(auto &[key,value]:objectStrings)if(key.first.find("FX_V229_LINE_")==0 && key.second==OBJPROP_TEXT){
  if(!first)std::cout<<",";first=false;
  std::cout<<"{\"text\":"<<std::quoted(value)<<",\"font\":"<<std::quoted(objectStrings[{key.first,OBJPROP_FONT}])
   <<",\"size\":"<<objectIntegers[{key.first,OBJPROP_FONTSIZE}]<<",\"color\":"<<objectIntegers[{key.first,OBJPROP_COLOR}]
   <<",\"y\":"<<objectIntegers[{key.first,OBJPROP_YDISTANCE}]<<"}";
 }
 std::cout<<"]}";return 0;
}
'''
        path=cls.binary.parent/'forex_dashboard.cpp'
        path.write_text(shim+cls.native_api+cls.native_source+main)
        cls.binary=path.with_suffix('')
        proc=subprocess.run(['g++','-std=c++17','-O1',str(path),'-o',str(cls.binary)],capture_output=True,text=True)
        if proc.returncode:raise RuntimeError(proc.stderr)

    def render(self,scenario=700):
        bars=sr_bars(1)
        data=f'{START} {len(bars)}\n'+'\n'.join(f'{b.time} {b.open:.17g} {b.high:.17g} {b.low:.17g} {b.close:.17g} {b.ticks}' for b in bars)+'\n'
        with tempfile.TemporaryDirectory() as tmp:
            p=subprocess.run([str(self.binary),tmp,str(scenario)],input=data,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        r=json.loads(p.stdout);self.assertEqual(r['init'],0);self.assertFalse(r['mutated'])
        return r

    def text(self,r):return '\n'.join(row['text'] for row in r['labels'])

    def test_forex_has_readable_background_and_no_binary_learning_content(self):
        r=self.render();text=self.text(r)
        self.assertTrue(r['background']);self.assertFalse(r['legacy_comment'])
        self.assertIn('V2.29 FOREX | DEMO',text)
        self.assertGreaterEqual(min(row['size'] for row in r['labels']),12)
        self.assertGreaterEqual(r['width'],600);self.assertLess(r['height'],950)
        for forbidden in ['OLYMP','DEMO LEARNING','Payout','Logistic','CALL/PUT']:
            self.assertNotIn(forbidden,text)

    def test_account_risk_position_and_operational_sections_show_actual_values(self):
        text=self.text(self.render())
        for expected in ['Balance 10000.00 USD','Equity 10000.00 USD','Free margin 10000.00 USD',
                         '0.50% = 50.00 USD','/ 2.00%','VI THE CUA EA | 0 LENH','Spread:',
                         'NEWS_CLOCK_UNCERTAIN','Break-even: ON','Trailing: ON','Giu toi da 60 phut']:
            self.assertIn(expected,text)

    def test_real_opt_in_disconnected_permission_and_storage_warnings(self):
        cases={701:'CHUA CHO PHEP REAL',702:'QUYEN GIAO DICH MT4 TAT',703:'MAT KET NOI BROKER',
               704:'DA CHAM GIOI HAN LO NGAY',705:'LOI LUU TRU | CHAN MO MOI'}
        for case,warning in cases.items():
            with self.subTest(case=case):self.assertIn(warning,self.text(self.render(case)))

    def test_own_position_has_ticket_lot_entry_sl_tp_net_and_hold_time(self):
        text=self.text(self.render(706))
        for expected in ['VI THE CUA EA | 1 LENH','BUY #88 | 0.01 lot | P/L 11.00 USD',
                         'P/L tha noi EA: 11.00 USD','Vao 1.10010 | SL 1.09910 | TP 1.10210',
                         'Da giu: 10:00 | Con lai: 50:00','Lenh EURUSD khac / pending: 1']:
            self.assertIn(expected,text)
        self.assertNotIn('P/L tha noi EA: 111.00',text)

    def test_hold_deadline_uses_original_birth_for_partial_close_residual(self):
        text=self.text(self.render(708));self.assertIn('Da giu: 20:00 | Con lai: 40:00',text)
        self.assertNotIn('Da giu: 01:00',text)

    def test_invalid_position_state_is_unknown_without_mutating_native_health(self):
        self.assertIn('Thoi gian giu: CHUA XAC THUC STATE',self.text(self.render(709)))

    def test_missing_sl_is_visible_without_sending_or_modifying_an_order(self):
        r=self.render(710)
        row=next(x for x in r['labels'] if x['text'].startswith('Vao '))
        self.assertIn('SL 0.00000',row['text']);self.assertEqual(row['color'],0x4763ff)

    def test_two_owned_positions_and_total_float_are_kept_separate_from_manual_order(self):
        text=self.text(self.render(711))
        for expected in ['VI THE CUA EA | 2 LENH','BUY #88','SELL #89','P/L tha noi EA: 6.00 USD']:
            self.assertIn(expected,text)

    def test_preset_font_and_position_controls_apply_to_forex(self):
        r=self.render(712)
        self.assertEqual((r['left'],r['top']),(36,44))
        self.assertTrue(all(x['font']=='Consolas' and x['size']>=16 for x in r['labels']))

    def test_optional_legacy_display_and_deinitialization_cleanup(self):
        r=self.render(713);self.assertFalse(r['background']);self.assertTrue(r['legacy_comment'])
        r=self.render(714);self.assertFalse(r['background']);self.assertEqual(r['labels'],[])
        self.assertTrue(r['binary_untouched'])

    def test_binary_initialization_does_not_create_forex_dashboard(self):
        r=self.render(715);self.assertFalse(r['background']);self.assertEqual(r['labels'],[])

    def test_missing_daily_baseline_and_zero_capital_are_not_presented_as_ready(self):
        self.assertIn('CHUA CO MOC EQUITY',self.text(self.render(716)))
        self.assertIn('0.50% = 0.00 USD',self.text(self.render(717)))

    def test_spread_and_quote_age_show_observed_data(self):
        self.assertIn('Spread: 3.00 pip | Gioi han 1.50 pip',self.text(self.render(718)))
        self.assertIn('Tuoi quote: 10.0s',self.text(self.render(719)))

    def test_no_time_limit_preset_is_displayed_as_unlimited(self):
        text=self.text(self.render(720));self.assertIn('Giu: KHONG GIOI HAN',text)
        self.assertNotIn('Giu toi da 0 phut',text)


class ForexDashboardPreservationTests(unittest.TestCase):
    def test_every_v228_header_is_byte_identical_and_dashboard_has_no_trade_actions(self):
        baseline=json.loads((ROOT/'baseline_v228_sha256.json').read_text())
        for name,expected in baseline.items():
            if name.startswith('mt4/Include/'):
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),expected,name)
        text=(ROOT/'mt4/Include/EURUSD_M5_V224/ForexDashboard.mqh').read_text()
        for forbidden in ['OrderSend(', 'OrderModify(', 'OrderClose(', 'FXStorageFailure(', 'FXReadState(',
                          'FXAccountPermission(', 'FXDayGuard(', 'FXNewsEntryAllowed(', 'FXScheduleEntry(', 'WebRequest(']:
            self.assertNotIn(forbidden,text)


if __name__=='__main__':unittest.main()
