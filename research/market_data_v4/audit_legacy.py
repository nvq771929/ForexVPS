"""Audit accepted legacy quotes without calling them a complete broker tick feed."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

def read(p):
    with p.open() as f:return list(csv.DictReader(f))
def audit(folder):
    paths=sorted(folder.glob('forex_quotes_*.csv'));quotes=[r for p in paths for r in read(p)]
    if any(set(r)!=set(['contract','broker_ms','bid','ask']) or r['contract']!='V222_FOREX_QUOTES_V1' for r in quotes):raise ValueError('legacy quote contract')
    times=[int(r['broker_ms']) for r in quotes]
    if times!=sorted(times):raise ValueError('legacy quote time regression')
    events=read(folder/'forex_events.csv');windows=[]
    for r in events:
        if r['kind']=='INIT':windows.append([int(r['broker_seconds']),None])
        elif r['kind']=='DEINIT':
            if not windows or windows[-1][1] is not None:raise ValueError('legacy session pairing')
            windows[-1][1]=int(r['broker_seconds'])
    intervals=[(b-a)/1000 for a,b in zip(times,times[1:]) if any(start*1000<=a<=b<=end*1000+2000 for start,end in windows if end is not None)]
    return {'stage':'FORENSIC_ACCEPTED_CALLBACK_SAMPLE_NOT_TICK_BACKTEST','quote_rows':len(quotes),'active_sessions':len(windows),
        'first_estimated_broker_ms':times[0] if times else None,'last_estimated_broker_ms':times[-1] if times else None,
        'same_session_gaps_over3s':sum(x>3 for x in intervals),'maximum_same_session_interval_seconds':max(intervals,default=None),
        'order_intent_records':sum(r['kind']=='ORDER_INTENT' for r in events),
        'timestamp_basis':'EA BOClockTick estimated milliseconds, not original quote server milliseconds',
        'clock_observer_count_explanation':'Accepted clock observations throttled to at most1 per broker second; all rejected clock updates logged. Quote rows are a different stream.',
        'gaps_prove_packet_loss':False,'unfiltered_callbacks_or_broker_completeness_proven':False,
        'valid_full_strategy_tick_backtest':False,'commission_rate_available':False,
        'source_manifest':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--forex-folder',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.forex_folder);a.output.mkdir(parents=True,exist_ok=False);(a.output/'legacy_quality.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
