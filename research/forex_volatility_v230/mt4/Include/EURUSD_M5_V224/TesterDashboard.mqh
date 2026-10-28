#ifndef BO_V222_TESTER_DASHBOARD
#define BO_V222_TESTER_DASHBOARD
#include "DemoLearning.mqh"

// Display only: count successful journal commits, never invent learning labels
// or alter the immutable prediction/outcome state. Tester starts a fresh run.
long boTesterTicks=0,boTesterAnchors=0,boTesterEntries=0;
void BOTesterDashboardReset() {
   boTesterTicks=0; boTesterAnchors=0; boTesterEntries=0;
}
void BOTesterDashboardRecord(const BOEvent &event) {
   if(!IsTesting()) return;
   if(event.kind==BO_ANCHOR_EVENT) boTesterAnchors++;
   if(event.kind==BO_ENTRY_EVENT) {
      boTesterEntries++;
      if(event.signal) { boPaperSignals++; boPaperOpen++; }
   }
   // Only the chosen expiry of a published signal belongs in its win/loss.
   // Other reference horizons and canceled/WAIT entries must not count.
   if(event.kind!=BO_OUTCOME_EVENT || !event.signal ||
      event.selectedHorizon<1 || event.selectedHorizon>3 ||
      event.outcomeHorizon!=event.selectedHorizon) return;
   if(boPaperOpen>0) boPaperOpen--;
   if(event.outcome==9) { boPaperMissing++; boPaperLast="UNAVAILABLE"; }
   else if(event.outcome==0) { boPaperTies++; boPaperLast="TIE"; }
   else if(event.outcome*event.direction>0) { boPaperWins++; boPaperLast="WIN"; }
   else { boPaperLosses++; boPaperLast="LOSS"; }
}
#endif
