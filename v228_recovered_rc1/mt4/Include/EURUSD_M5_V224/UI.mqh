#ifndef BO_V222_UI
#define BO_V222_UI
#include "Contract.mqh"
#include "History.mqh"
#include "DemoLearning.mqh"
#include "ManualSignals.mqh"
#include "RuntimeDiagnostics.mqh"
#include "CandidateDiagnostics.mqh"
#include "SlotDiagnostics.mqh"
#include "LearningDialogue.mqh"

// Source contains ASCII escape tokens; Unicode code units are constructed at runtime.
// Plain Vietnamese is the default until accented rendering is confirmed on the terminal.

bool boUIAccents=false;
int BOUIBaseLetter(int code) {
   switch(code) {
      case 0x00C0: case 0x00C1: case 0x00C3: case 0x1EA0: case 0x1EA2: case 0x1EA4: case 0x1EAC: case 0x1EB6: return 65;
      case 0x0110: return 68;
      case 0x1EBE: case 0x1EC0: case 0x1EC6: return 69;
      case 0x00CD: case 0x1ECA: return 73;
      case 0x00D3: case 0x1ED0: case 0x1ED4: case 0x1ED6: case 0x1ED8: case 0x1EE2: return 79;
      case 0x00DA: case 0x01AF: case 0x1EE6: case 0x1EEA: case 0x1EEC: case 0x1EEE: return 85;
      case 0x00DD: return 89;
      case 0x00E0: case 0x00E1: case 0x00E2: case 0x00E3: case 0x1EA1: case 0x1EA3: case 0x1EA5: case 0x1EAB: case 0x1EAD: case 0x1EB7: return 97;
      case 0x0111: return 100;
      case 0x00EA: case 0x1EB9: case 0x1EBF: case 0x1EC1: case 0x1EC3: case 0x1EC5: case 0x1EC7: return 101;
      case 0x00EC: case 0x00ED: case 0x1EC9: case 0x1ECB: return 105;
      case 0x00F3: case 0x00F4: case 0x1ECD: case 0x1ED1: case 0x1ED3: case 0x1ED5: case 0x1ED7: case 0x1ED9: case 0x1EDB: case 0x1EDD: case 0x1EDF: case 0x1EE1: case 0x1EE3: return 111;
      case 0x00F9: case 0x00FA: case 0x0169: case 0x01B0: case 0x1EE5: case 0x1EE7: case 0x1EE9: case 0x1EEB: case 0x1EED: case 0x1EEF: case 0x1EF1: return 117;
      case 0x1EF3: return 121;
   }
   return code<128 ? code : 63;
}
int BOUIHexDigit(int code) {
   if(code>=48 && code<=57) return code-48;
   if(code>=65 && code<=70) return code-65+10;
   if(code>=97 && code<=102) return code-97+10;
   return -1;
}
string BOUIDecode(string encoded,bool accented) {
   string result=""; int length=StringLen(encoded);
   for(int i=0;i<length;i++) {
      int code=StringGetCharacter(encoded,i);
      if(code==92 && i+5<length && StringGetCharacter(encoded,i+1)==120) {
         int point=0; bool valid=true;
         for(int k=2;k<=5;k++) {
            int digit=BOUIHexDigit(StringGetCharacter(encoded,i+k));
            if(digit<0) { valid=false; break; }
            point=point*16+digit;
         }
         if(valid) { code=point; i+=5; }
      }
      if(!accented) code=BOUIBaseLetter(code);
      result+=ShortToString((ushort)code);
   }
   return result;
}
string BOUIText(string encoded) { return BOUIDecode(encoded,boUIAccents); }

#define BO_UI_ROWS 64
const color BO_UI_BACKGROUND=0x201814;

string BOProbabilityText(double value) {
   return value>=0 ? DoubleToString(value*100,2)+"%" : "N/A";
}
string BOUICountdown(long seconds) {
   seconds=(long)MathMax(0,seconds);
   long minutes=seconds/60,tail=seconds%60;
   return (minutes<10 ? "0" : "")+IntegerToString(minutes)+":"+(tail<10 ? "0" : "")+IntegerToString(tail);
}
string BOUIValidation(int value) {
   if(value==BO_CONFIRMED) return BOUIText("\\x0110\\x01AF\\x1EE2")+BOUIText("C C\\x1EE6NG C\\x1ED0");
   if(value==BO_PRESERVED) return BOUIText("\\x0110")+BOUIText("ANG GI\\x1EEE GI\\x1EA2 THUY\\x1EBET");
   if(value==BO_DEGRADED) return BOUIText("SUY Y\\x1EBEU");
   if(value==BO_INVALIDATED) return BOUIText("\\x0110\\x00C3 H\\x1EE6Y");
   return BOUIText("CH\\x01AF")+BOUIText("A \\x0110\\x1EE6 \\x0110I\\x1EC0U KI\\x1EC6N");
}
string BOUIReason(int reason) {
   switch(reason) {
      case BO_OK:return BOUIText("\\x0110i\\x1EC1u ki\\x1EC7n hi\\x1EC7n t\\x1EA1i h\\x1EE3p l\\x1EC7.");
      case BO_HISTORY_SHORT:return BOUIText("Ch\\x01B0")+BOUIText("a \\x0111\\x1EE7 64 n\\x1EBFn \\x0111\\x00E3 \\x0111\\x00F3ng.");
      case BO_HISTORY_GAP:return BOUIText("Chu\\x1ED7i n\\x1EBFn c\\x00F3 kho\\x1EA3ng tr\\x1ED1ng d\\x1EEF li\\x1EC7u.");
      case BO_BAD_OHLC:return BOUIText("D\\x1EEF li\\x1EC7u n\\x1EBFn kh\\x00F4ng h\\x1EE3p l\\x1EC7.");
      case BO_NO_SETUP:return BOUIText("Ch\\x01B0")+BOUIText("a c\\x00F3 m\\x1EABu gi\\x00E1 ph\\x00F9 h\\x1EE3p.");
      case BO_AMBIGUOUS:return BOUIText("Hai h\\x01B0\\x1EDBng m\\x00E2u thu\\x1EABn; ch\\x1EDD.");
      case BO_ZONE_UNKNOWN:return BOUIText("Ch\\x01B0")+BOUIText("a x\\x00E1")+BOUIText("c \\x0111\\x1ECBnh \\x0111\\x01B0\\x1EE3")+BOUIText("c v\\x00F9ng S/R ph\\x00F9 h\\x1EE3p.");
      case BO_VOLATILITY_RESEARCH:return BOUIText("Bi\\x1EBFn \\x0111\\x1ED9ng ngo\\x00E0i \\x0111i\\x1EC1u ki\\x1EC7n nghi\\x00EAn c\\x1EE9u.");
      case BO_COUNTERPRESSURE:return BOUIText("\\x00C1p l\\x1EF1")+BOUIText("c gi\\x00E1 ng\\x01B0\\x1EE3")+BOUIText("c gi\\x1EA3 thuy\\x1EBFt.");
      case BO_QUOTE_GAP:return BOUIText("Gi\\x00E1 c\\x1EADp nh\\x1EADt b\\x1ECB gi\\x00E1n \\x0111o\\x1EA1n ho\\x1EB7")+BOUIText("c qu\\x00E1 c\\x0169.");
      case BO_BAD_QUOTE:return BOUIText("Quote ho\\x1EB7")+BOUIText("c spread kh\\x00F4ng h\\x1EE3p l\\x1EC7.");
      case BO_STRUCTURAL_BREAK:return BOUIText("Gi\\x00E1 \\x0111\\x00E3 ph\\x00E1 m\\x1ED1")+BOUIText("c v\\x00F4 hi\\x1EC7u h\\x00F3")+"a.";
      case BO_EXTENSION_REACHED:return BOUIText("Gi\\x00E1 \\x0111\\x00E3 t\\x1EDBi v\\x00F9ng c\\x1EA3n \\x0111\\x1ED1i di\\x1EC7n.");
      case BO_LOCK_MISSED:return BOUIText("\\x0110\\x00E3 l\\x1EE1 m\\x1ED1")+BOUIText("c ch\\x1ED1t; kh\\x00F4ng ph\\x00E1t t\\x00EDn hi\\x1EC7u mu\\x1ED9n.");
      case BO_NOT_CONFIRMED:return BOUIText("Gi\\x00E1 T+1 ch\\x01B0")+BOUIText("a c\\x1EE7ng c\\x1ED1 \\x0111\\x1EE7 gi\\x1EA3 thuy\\x1EBFt.");
      case BO_MODEL_UNAVAILABLE:return BOUIText("Ch\\x01B0")+BOUIText("a c\\x00F3 m\\x00F4 h\\x00ECnh \\x0111\\x1EE7 \\x0111i\\x1EC1u ki\\x1EC7n.");
      case BO_MODEL_OOD:return BOUIText("B\\x1ED1i c\\x1EA3nh ngo\\x00E0i mi\\x1EC1n ki\\x1EC3m \\x0111\\x1ECBnh c\\x1EE7")+BOUIText("a m\\x00F4 h\\x00ECnh.");
      case BO_SHADOW_ONLY:return BOUIText("Shadow: ch\\x1EC9 thu d\\x1EEF li\\x1EC7u, kh\\x00F4ng c\\x1EA5p t\\x00EDn hi\\x1EC7u.");
      case BO_PAYOUT_STALE:return BOUIText("Payout ch\\x01B0")+BOUIText("a \\x0111\\x01B0\\x1EE3")+BOUIText("c x\\x00E1")+BOUIText("c nh\\x1EADn ho\\x1EB7")+BOUIText("c \\x0111\\x00E3 h\\x1EBFt h\\x1EA1n.");
      case BO_NO_EDGE:return BOUIText("Ch\\x01B0")+BOUIText("a \\x0111\\x1EE7 l\\x1EE3i th\\x1EBF theo payout hi\\x1EC7n t\\x1EA1i.");
      case BO_PAUSED:return BOUIText("\\x0110\\x00E3 t\\x1EA1m d\\x1EEBng quy\\x1EC1n ph\\x00E1t t\\x00EDn hi\\x1EC7u.");
      case BO_RESTART:return BOUIText("\\x0110\\x00E3 kh\\x1EDFi \\x0111\\x1ED9ng l\\x1EA1i; kh\\x00F4ng d\\x00F9ng l\\x1EA1i t\\x00EDn hi\\x1EC7u c\\x0169.");
      case BO_STORAGE_ERROR:return BOUIText("L\\x1ED7i l\\x01B0u tr\\x1EEF ho\\x1EB7")+BOUIText("c t\\x00EDnh to\\x00E0n v\\x1EB9n d\\x1EEF li\\x1EC7u.");
      case BO_ENTRY_MISSED:return BOUIText("\\x0110\\x00E3 l\\x1EE1 c\\x1EED")+BOUIText("a s\\x1ED5 gi\\x00E1 v\\x00E0o tham chi\\x1EBFu.");
      case BO_OUTCOME_MISSED:return BOUIText("Thi\\x1EBFu gi\\x00E1 h\\x1EBFt h\\x1EA1n tham chi\\x1EBFu.");
      case BO_PENDING_FULL:return BOUIText("Ch\\x01B0")+BOUIText("a c\\x00F3 ch\\x1ED7 l\\x01B0u k\\x1EBFt qu\\x1EA3 \\x0111")+BOUIText("ang ch\\x1EDD.");
      case BO_CONFIG_CHANGED:return BOUIText("C\\x1EA5u h\\x00ECnh ho\\x1EB7")+BOUIText("c ngu\\x1ED3n gi\\x00E1 \\x0111\\x00E3 thay \\x0111\\x1ED5i.");
      case BO_TIME_ANOMALY:return BOUIText("\\x0110\\x1ED3ng h\\x1ED3 ngu\\x1ED3n gi\\x00E1 kh\\x00F4ng li\\x00EAn t\\x1EE5")+"c.";
      case BO_CONTEXT_UNSUPPORTED:return "Boi canh chua phu hop; cho luot moi.";
      case BO_RETEST_PENDING:return "Cho gia kiem tra lai vung pha vo va giu dung huong.";
      case BO_STRATEGY_DISABLED:return "Chien luoc cua boi canh nay dang tat.";
      case BO_WAIT_QUOTE:return "Dang cho tick moi; chua huy luot.";
   }
   return BOUIText("Ch\\x01B0")+BOUIText("a c\\x00F3 di\\x1EC5n gi\\x1EA3i cho tr\\x1EA1ng th\\x00E1i n\\x00E0y.");
}
void BOUILabel(string name,string text,int x,int y,int size,color tone,string font) {
   if(ObjectFind(0,name)<0) ObjectCreate(0,name,OBJ_LABEL,0,0,0);
   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_ANCHOR,ANCHOR_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,x); ObjectSetInteger(0,name,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,size); ObjectSetInteger(0,name,OBJPROP_COLOR,tone);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false); ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
   ObjectSetInteger(0,name,OBJPROP_BACK,false); ObjectSetInteger(0,name,OBJPROP_ZORDER,1);
   ObjectSetString(0,name,OBJPROP_FONT,font); ObjectSetString(0,name,OBJPROP_TEXT,text);
}
void BOUIRow(int &row,int &y,string text,int size,color tone,string font,int x) {
   BOUILabel("BO_V222_LINE_"+IntegerToString(row),text,x,y,size,tone,font);
   row++; y+=(size*4+2)/3+7;
}
void BOButton(string name,string text,int x,int y,int width,int size,string font) {
   if(ObjectFind(0,name)<0) ObjectCreate(0,name,OBJ_BUTTON,0,0,0);
   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,x); ObjectSetInteger(0,name,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,name,OBJPROP_XSIZE,width); ObjectSetInteger(0,name,OBJPROP_YSIZE,(size*4+2)/3+16);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,size); ObjectSetInteger(0,name,OBJPROP_COLOR,clrWhiteSmoke);
   ObjectSetInteger(0,name,OBJPROP_BGCOLOR,clrDarkSlateGray); ObjectSetInteger(0,name,OBJPROP_BORDER_COLOR,clrSlateGray);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false); ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
   ObjectSetInteger(0,name,OBJPROP_BACK,false); ObjectSetInteger(0,name,OBJPROP_ZORDER,2);
   ObjectSetString(0,name,OBJPROP_FONT,font); ObjectSetString(0,name,OBJPROP_TEXT,text);
}
void BODeletePanel() {
   for(int i=0;i<BO_UI_ROWS;i++) ObjectDelete(0,"BO_V222_LINE_"+IntegerToString(i));
   ObjectDelete(0,"BO_V222_BACKGROUND"); ObjectDelete(0,"BO_V222_PAUSE"); ObjectDelete(0,"BO_V222_PAYOUT");
}
string BOUIRegime(int regime) {
   if(regime==BO_RANGE) return "DI NGANG";
   if(regime==BO_ORDERLY_UP) return "XU HUONG TANG";
   if(regime==BO_ORDERLY_DOWN) return "XU HUONG GIAM";
   if(regime==BO_EXPANSION_UP) return "PHA VO TANG";
   if(regime==BO_EXPANSION_DOWN) return "PHA VO GIAM";
   if(regime==BO_COMPRESSION) return "CO HEP";
   if(regime==BO_TRANSITION) return "CHUYEN TIEP";
   return "CHUA RO";
}
string BOUISetup(int setup) {
   if(setup==1) return "SR1 | Pha vo that bai";
   if(setup==2) return "TP1 | Hoi theo xu huong";
   if(setup==3) return "BR1 | Pha vo va kiem tra lai";
   return "WAIT | Chua chon";
}
void BORender(const BORuntimeState &s,const BOConfig &config,long nowMs,bool shadow,bool healthy,string root,int modelCount,
              bool diagnostic,int fontSize,int actionSize,string font,int left,int top,string eaRelease) {
   string background="BO_V222_BACKGROUND";
   if(ObjectFind(0,background)<0) ObjectCreate(0,background,OBJ_RECTANGLE_LABEL,0,0,0);
   int width=fontSize*34+56,x=left+14,y=top+12,row=0;
   int small=(int)MathMax(11,fontSize-3),buttonSize=(int)MathMax(11,fontSize-2);
   ObjectSetInteger(0,background,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,background,OBJPROP_XDISTANCE,left); ObjectSetInteger(0,background,OBJPROP_YDISTANCE,top);
   ObjectSetInteger(0,background,OBJPROP_XSIZE,width); ObjectSetInteger(0,background,OBJPROP_BGCOLOR,BO_UI_BACKGROUND);
   ObjectSetInteger(0,background,OBJPROP_BORDER_TYPE,BORDER_FLAT); ObjectSetInteger(0,background,OBJPROP_COLOR,clrSlateGray);
   ObjectSetInteger(0,background,OBJPROP_BACK,false); ObjectSetInteger(0,background,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,background,OBJPROP_HIDDEN,true); ObjectSetInteger(0,background,OBJPROP_ZORDER,0);
   BOUIRow(row,y,Symbol()+" M5 | TRO LY "+eaRelease+" | DEMO LEARNING",fontSize,clrWhiteSmoke,font,x);
   if(IsTesting()) {
      BOUIRow(row,y,"BACKTEST MT4 | DU LIEU HUAN LUYEN RIENG",small,clrDeepSkyBlue,font,x);
      BOUIRow(row,y,"Gio mo phong: "+TimeToString((datetime)(nowMs/1000),TIME_DATE|TIME_SECONDS),small,clrWhiteSmoke,font,x);
      BOUIRow(row,y,"Ticks: "+IntegerToString(boTesterTicks)+" | Phan tich: "+IntegerToString(boTesterAnchors)+" | Moc gia: "+IntegerToString(boTesterEntries),small,clrSilver,font,x);
   }
   BOUIRow(row,y,"OLYMP DEMO: VAO THU CONG | CHUA KIEM DINH LOI THE",small,clrGold,font,x);
   BOUIRow(row,y,"MT4_SIMULATED | BID | Payout gia dinh 82%",small,clrDeepSkyBlue,font,x);
   string advisorMode=boAdvisorAffects ? "TU VAN" : "QUAN SAT";
   BOUIRow(row,y,boAdvisorEnabled ? "Bo hoc: TRAO DOI TRUOC KHOA | "+advisorMode : "Bo hoc sau: NGHIEN CUU | Trao doi OFF",small,clrSilver,font,x);
   BOUIRow(row,y,boAdvisorEnabled ? BOAdvisorUserStatus() : "Hoc ung vien: NGHIEN CUU | CHUA LOC TIN HIEU",small,clrSilver,font,x);
   long contextUtcMs=BOContextUTC(nowMs);long contextUtc=contextUtcMs/1000;
   BOUIRow(row,y,"Phien thi truong: "+BOContextSession(BOContextMask(contextUtc))+" | QUAN SAT",small,clrDeepSkyBlue,font,x);
   long entryUtc=contextUtc>0 ? (long)MathMax(contextUtc,s.current.exists ? (long)s.current.targetTime-boContextOffset : contextUtc) : 0;
   string newsDetail;long newsTime=0;string newsState=BOContextNews(contextUtc,entryUtc,entryUtc+boDemoHorizon*300,newsDetail,newsTime);
   BOUIRow(row,y,"Tin: "+newsState+" | CHUA LOC TIN HIEU",small,clrSilver,font,x);
   if(boContextNewsReceived>0) {
      string coverage=boContextNewsPolicy=="LEGACY_V216" ? "HIGH ONLY (LICH CU)" : "MEDIUM/HIGH + UU TIEN";
      BOUIRow(row,y,"Faireconomy: "+coverage+" | "+TimeToString((datetime)(boContextNewsReceived+25200),TIME_SECONDS)+" VN",small,clrSilver,font,x);
   }
   if(newsTime>0 && boContextSelected>=0) {
      int selected=boContextSelected;string title=boContextLabel[selected];
      if(boContextNewsPolicy=="LEGACY_V216" && StringLen(title)>25)title=StringSubstr(title,25);
      if(StringLen(title)>49)title=StringSubstr(title,0,46)+"...";
      BOUIRow(row,y,boContextCurrency[selected]+" "+boContextImpact[selected]+" | "+title,small,newsState=="NEWS_RISK_WINDOW" ? clrGold : clrSilver,font,x);
      long remain=newsTime-contextUtc;
      string timing=remain>=0 ? "Con "+BOUICountdown(remain) : "Da ra "+BOUICountdown(-remain);
      BOUIRow(row,y,TimeToString((datetime)(newsTime+25200),TIME_DATE|TIME_SECONDS)+" VN | "+timing+
         (boContextTracking[selected]=="PRIORITY_EVENT" ? " | UU TIEN" : ""),small,clrSilver,font,x);
   }
   if(boNewsAlertFailed)BOUIRow(row,y,"CANH BAO TIN: LOI GHI THONG BAO",small,clrTomato,font,x);
   if(boContextWriteFailed)BOUIRow(row,y,"LOG PHIEN: LOI GHI | KIEM TRA NHAT KY",small,clrTomato,font,x);
   color manualTone=boManualLatest.id>0 ? clrLimeGreen : clrGold;
   if(boManualLatestResult==-1 || boManualError)manualTone=clrTomato;
   if(boManualLatestResult==9)manualTone=clrGold;
   BOUIRow(row,y,BOManualHeadline(nowMs),actionSize,manualTone,font,x);
   if(boManualLatest.id>0) {
      BOUIRow(row,y,"GIU "+IntegerToString(boManualLatest.horizon*5)+" PHUT ("+IntegerToString(boManualLatest.horizon)+" M5) | DA CHOT",fontSize,clrWhiteSmoke,font,x);
      BOUIRow(row,y,"ID "+IntegerToString(boManualLatest.id)+(nowMs<boManualLatest.target*1000 ? " | CHO DUNG MOC VAO" : " | KHONG VAO MUON"),small,clrWhiteSmoke,font,x);
      BOUIRow(row,y,"Vao "+TimeToString((datetime)boManualLatest.target,TIME_SECONDS)+" | Het han "+TimeToString((datetime)boManualLatest.expiry,TIME_SECONDS)+" | Broker",small,clrWhiteSmoke,font,x);
      if(nowMs<boManualLatest.target*1000)BOUIRow(row,y,"Con den moc vao: "+BOUICountdown((boManualLatest.target*1000-nowMs)/1000),small,clrWhiteSmoke,font,x);
      else if(nowMs<boManualLatest.expiry*1000)BOUIRow(row,y,"Con den het han: "+BOUICountdown((boManualLatest.expiry*1000-nowMs)/1000),small,clrWhiteSmoke,font,x);
      if(BOManualOwns((long)s.current.analysisStart) && s.current.canceled)
         BOUIRow(row,y,"TIN DA PHAT DUOC GIU | CANH BAO NATIVE: "+BOReasonName(s.current.reason),small,clrGold,font,x);
   } else BOUIRow(row,y,"Ky han du kien: "+IntegerToString(boDemoHorizon*5)+" phut ("+IntegerToString(boDemoHorizon)+" M5)",small,clrSilver,font,x);
   BOUIRow(row,y,"Tin da phat: "+IntegerToString(boManualTotal)+" | Cho: "+IntegerToString(boManualPending),small,clrWhiteSmoke,font,x);
   BOUIRow(row,y,"MT4 tin hieu: WIN "+IntegerToString(boManualWins)+" | LOSS "+IntegerToString(boManualLosses)+" | TIE "+IntegerToString(boManualTies)+" | Thieu gia "+IntegerToString(boManualMissing),small,clrWhiteSmoke,font,x);
   if(boManualError)BOUIRow(row,y,"LOI SO TIN HIEU | DUNG PHAT MOI - GIU NHAT KY",small,clrTomato,font,x);
   BOUIRow(row,y,"Boi canh dang phan tich: "+BOUIRegime(s.current.anchor.regime),fontSize,clrDeepSkyBlue,font,x);
   BOUIRow(row,y,"Chien luoc: "+BOUISetup(s.current.candidate.setup),fontSize,clrWhiteSmoke,font,x);
   BOUIRow(row,y,"Native gia thuyet: "+BOActionName(s.current.candidate.direction)+" | "+BOValidationName(s.current.validation),small,clrSilver,font,x);
   BOUIRow(row,y,"Kiem tra native: "+(healthy ? BOReasonName(s.current.reason) : "STORAGE_ERROR"),small,healthy ? clrGold : clrTomato,font,x);
   BOUIRow(row,y,"Chan doan native: "+BODiagnosticsStage(s),small,clrGold,font,x);
   BOUIRow(row,y,"Luot M5: "+boSlotStatus+" | Tao "+IntegerToString(boSlotCreated)+" | Lo "+IntegerToString(boSlotMissed),small,boSlotMissed>0 ? clrGold : clrSilver,font,x);
   if(boSlotWriteFailed)BOUIRow(row,y,"LOG LUOT M5: LOI GHI",small,clrTomato,font,x);
   long tickAge=boDiagTickMs>0 ? (long)MathMax(0,nowMs-boDiagTickMs) : -1;
   BOUIRow(row,y,"Tuoi tick: "+(tickAge>=0 ? DoubleToString(tickAge/1000.0,1)+"s" : "N/A")+
      " | Gap tick: "+DoubleToString(boDiagGapMs/1000.0,1)+"s | Gioi han sau khoa: "+IntegerToString(config.quoteFreshSeconds)+"s",small,clrSilver,font,x);
   BOUIRow(row,y,"Luot chay: Khoa "+IntegerToString(boDiagLocks)+" | Huy gap "+IntegerToString(boDiagGapCancels)+
      " | Entry "+IntegerToString(boDiagEntries),small,clrSilver,font,x);
   if(diagnostic) {
      BOUIRow(row,y,"Ung vien phien: "+IntegerToString(boCandidateFormed)+" | Du tai LOCK: "+IntegerToString(boCandidateReady),small,clrSilver,font,x);
      if(boCandidateWriteFailed) BOUIRow(row,y,"LOG DIEU KIEN: LOI GHI | KIEM TRA NHAT KY",small,clrTomato,font,x);
      BOUIRow(row,y,"Huy gap: giua tick "+IntegerToString(boDiagIncomingGapCancels)+" | thieu tick "+IntegerToString(boDiagNoTickCancels),small,clrSilver,font,x);
      long storedAge=s.current.lastQuoteMs>0 ? (long)MathMax(0,nowMs-s.current.lastQuoteMs) : -1;
      BOUIRow(row,y,"Tuoi gia luu: "+(storedAge>=0 ? DoubleToString(storedAge/1000.0,1)+"s" : "N/A"),small,clrSilver,font,x);
      if(boDiagLastGapClass!="NONE") {
         string meaning=boDiagLastGapClass=="INCOMING_TICK_AFTER_OBSERVATION_GAP" ? "TICK MOI SAU GIAN DOAN" :
            (boDiagLastGapClass=="NO_RECENT_TICK_AT_CHECK" ? "CHUA CO TICK GAN DAY" : "CAN DOI CHIEU");
         BOUIRow(row,y,"Huy gap gan nhat: "+meaning,small,clrGold,font,x);
         BOUIRow(row,y,"Luc huy: gia luu "+DoubleToString(boDiagCancelStoredAge/1000.0,1)+"s | tick "+
            (boDiagCancelTickAge>=0 ? DoubleToString(boDiagCancelTickAge/1000.0,1)+"s" : "N/A"),small,clrSilver,font,x);
      }
   }
   if(boDiagWriteFailed) BOUIRow(row,y,"LOG CHAN DOAN: LOI GHI | NHAT KY BIN VAN LA NGUON",small,clrTomato,font,x);
   if(s.current.exists && !BOManualOwns((long)s.current.analysisStart)) {
      BOUIRow(row,y,"CHUAN BI, CHUA PHAT: "+TimeToString(s.current.targetTime,TIME_SECONDS)+" Broker",small,clrSilver,font,x);
      BOUIRow(row,y,"Het han du kien: "+TimeToString(s.current.targetTime+boDemoHorizon*300,TIME_SECONDS)+" (Broker)",small,clrSilver,font,x);
      BOUIRow(row,y,"Khoa truoc: "+IntegerToString(config.lockLeadSeconds+config.lockGuardSeconds)+"s | Con: "+BOUICountdown((s.current.targetTime*1000-nowMs)/1000),small,clrSilver,font,x);
   }
   BOUIRow(row,y,"Ky han mo phong: "+IntegerToString(boDemoHorizon*5)+" phut",small,clrSilver,font,x);
   if(IsTesting()) {
      BOUIRow(row,y,"Hoc lich su: DANG THU THAP - CHUA HUAN LUYEN",small,clrDeepSkyBlue,font,x);
      BOUIRow(row,y,"Sau Tester: chay TRAIN-HISTORY.CMD",small,clrSilver,font,x);
      BOUIRow(row,y,"Bo dem ben duoi: tinh truc tiep tu nhat ky Tester",small,clrSilver,font,x);
   } else {
      BOUIRow(row,y,"ML Logistic: "+boAdvStatus,small,boAdvBad ? clrTomato : clrLimeGreen,font,x);
      BOUIRow(row,y,"Hoc: "+boLearnStatus+" | Nhom: "+IntegerToString(modelCount),small,boLearnBad ? clrTomato : clrLimeGreen,font,x);
      BOUIRow(row,y,"Bo hoc cap nhat: "+(boLearnAsOf>0 ? TimeToString((datetime)boLearnAsOf,TIME_SECONDS)+" (Broker)" : "CHUA CO - CHAY START-DEMO-LEARNING"),small,clrSilver,font,x);
   }
   BOUIRow(row,y,"ENTRY ky thuat: "+IntegerToString(boPaperSignals)+" | Cho: "+IntegerToString(boPaperOpen),small,clrWhiteSmoke,font,x);
   BOUIRow(row,y,"ENTRY: WIN "+IntegerToString(boPaperWins)+" | LOSS "+IntegerToString(boPaperLosses)+" | TIE "+IntegerToString(boPaperTies),small,clrWhiteSmoke,font,x);
   BOUIRow(row,y,"Thieu gia: "+IntegerToString(boPaperMissing)+" | Gan nhat: "+boPaperLast,small,clrGold,font,x);
   BOUIRow(row,y,"Model dang dung: "+IntegerToString(s.current.modelId)+" | 0 = CHUA DU MAU",small,clrSilver,font,x);
   double estimate=boDemoHorizon==1 ? s.current.p1 : boDemoHorizon==2 ? s.current.p2 : s.current.p3;
   BOUIRow(row,y,"Uoc luong nghien cuu: "+(s.current.modelId>0 ? BOProbabilityText(estimate) : "CHUA DU MAU"),small,clrSilver,font,x);
   BOUIRow(row,y,string("Du lieu: ")+boHistoryStatus,small,boHistoryReady ? clrLimeGreen : clrGold,font,x);
   if(IsTesting()) {
      BOUIRow(row,y,"Lich su M5: "+IntegerToString(boHistoryM5Count)+"/64 | M1: "+IntegerToString(boHistoryM1Count)+"/320",small,clrSilver,font,x);
      if(!boHistoryReady) BOUIRow(row,y,"Can 64 nen M5 lien tiep, khong bu nen thieu",small,clrGold,font,x);
   }
   if(boClockBaseMs==0) BOUIRow(row,y,"CHO TICK EURUSD MOI | CHUA PHAT TIN HIEU",small,clrGold,font,x);
   BOUIRow(row,y,"Ket qua mo phong khong phai ket qua Olymp Trade",small,clrGold,font,x);
   BOUIRow(row,y,"Nhat ky: "+root,small,clrSilver,font,x);
   BOButton("BO_V222_PAUSE",s.paused ? "Tiep tuc tin hieu demo" : "Tam dung tin hieu demo",x,y,width-28,buttonSize,font);
   y+=(buttonSize*4+2)/3+23;
   ObjectSetInteger(0,background,OBJPROP_YSIZE,y-top+8);
   for(int i=row;i<BO_UI_ROWS;i++) ObjectDelete(0,"BO_V222_LINE_"+IntegerToString(i));
   ChartRedraw(0); Comment("");
}
#endif
