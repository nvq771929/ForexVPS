#ifndef BO_V222_CLOCK
#define BO_V222_CLOCK
long boClockBaseMs=0; uint boClockMono=0; long boLastTickMs=0;
long BONowMs() { if(IsTesting()) return boClockBaseMs>0 ? boClockBaseMs : (long)TimeCurrent()*1000; return boClockBaseMs>0 ? boClockBaseMs+(long)(uint)(GetTickCount()-boClockMono) : 0; }
bool BOClockTick(datetime serverTime, long &nowMs) {
   long floorMs=(long)serverTime*1000;
   if(IsTesting()) {
      if(boClockBaseMs>floorMs) return false;
      nowMs=floorMs; boClockBaseMs=floorMs; boClockMono=GetTickCount(); boLastTickMs=nowMs; return true;
   }
   long estimate=BONowMs();
   if(estimate>0 && floorMs<estimate-2000) return false;
   nowMs=(long)MathMax(floorMs,estimate);
   boClockBaseMs=nowMs; boClockMono=GetTickCount(); boLastTickMs=nowMs;
   return true;
}
#endif
