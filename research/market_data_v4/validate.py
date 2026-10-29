"""Read-only capture/BO data quality. No training, execution or profitability score."""
import argparse
from collections import Counter
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import statistics

FIELDS={
 'metadata':'contract,origin,account_mode,account,server,symbol,currency,digits,point,tick_size_price,tick_value,contract_size,min_lot,lot_step,max_lot,stop_level_points,freeze_level_points,started_utc_seconds,started_broker_seconds,chart_id',
 'ticks':'sequence,quote_server_seconds,terminal_server_seconds,pc_utc_seconds,pc_local_seconds,mono_elapsed_ms,bid,ask,connected,valid_quote',
 'heartbeats':'sequence,pc_utc_seconds,terminal_server_seconds,mono_elapsed_ms,connected,last_quote_server_seconds,tick_rows,io_ok',
 'bars_m5':'sequence,time_broker,open,high,low,close,tick_volume,observed_utc_seconds,observed_broker_seconds,origin',
 'closed_orders':'ticket,symbol,type,magic,lots,opened_broker_seconds,closed_broker_seconds,entry_price,exit_price,profit,commission,swap,currency,exported_utc_seconds,history_source',
 'session':'event,pc_utc_seconds,broker_seconds,tick_rows,heartbeat_rows,bar_rows,order_rows,tick_callbacks,io_ok',
 'bo_quotes':'record_id,platform,account_mode,asset_label,observed_at_iso,platform_price,payout_5m,payout_10m,payout_15m,source_reference',
 'bo_trades':'record_id,platform,account_mode,asset_label,direction,opened_at_iso,expires_at_iso,entry_platform_price,expiry_platform_price,payout_fraction,stake,currency,result,source_reference'}
def rows(path,expected=None):
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if expected and reader.fieldnames!=FIELDS[expected].split(','):raise ValueError(f'{path.name}: unsupported schema')
        out=list(reader)
    if any(None in r or any(v is None for v in r.values()) for r in out):raise ValueError(f'{path.name}: incomplete/extra fields')
    return out
def finite(value):
    x=float(value)
    if not math.isfinite(x):raise ValueError('nonfinite numeric field')
    return x
def sequence(data):
    if [int(r['sequence']) for r in data]!=list(range(1,len(data)+1)):raise ValueError('noncontiguous local sequence')
def timestamp(value):
    x=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if x.tzinfo is None or x.utcoffset() is None:raise ValueError('Timestamp requires timezone, e.g.2026-10-29T10:00:00+07:00')
    return x.timestamp()

def capture(folder):
    required=['metadata','ticks','heartbeats','bars_m5','closed_orders','session']
    data={name:rows(folder/(name+'.csv'),name) for name in required}
    if len(data['metadata'])!=1:raise ValueError('one metadata row required')
    m=data['metadata'][0]
    if m['contract']!='RESEARCH_CAPTURE_V1' or m['origin']!='LIVE_MT4_CALLBACKS' or m['account_mode']!='DEMO':raise ValueError('not an eligible demo callback capture')
    for name in ['ticks','heartbeats','bars_m5']:sequence(data[name])
    ticks=data['ticks'];beats=data['heartbeats'];bars=data['bars_m5'];orders=data['closed_orders']
    elapsed=[int(r['mono_elapsed_ms']) for r in ticks]
    if elapsed!=sorted(elapsed):raise ValueError('monotonic arrival went backwards')
    invalid=0
    for r in ticks:
        try:valid=finite(r['bid'])>0 and finite(r['ask'])>=finite(r['bid'])
        except ValueError:valid=False
        if (r['valid_quote']=='1')!=valid:raise ValueError('quote validity flag disagrees with values')
        invalid+=not valid
    hb_time=[int(r['mono_elapsed_ms']) for r in beats]
    if hb_time!=sorted(hb_time):raise ValueError('heartbeat arrival went backwards')
    counts=[int(r['tick_rows']) for r in beats]
    if counts!=sorted(counts) or any(n>len(ticks) for n in counts):raise ValueError('heartbeat tick count inconsistent')
    bar_times=[int(r['time_broker']) for r in bars]
    if any(t%300 for t in bar_times) or any(b<=a for a,b in zip(bar_times,bar_times[1:])):raise ValueError('closed bar timestamp order')
    for r in bars:
        o,h,l,c=[finite(r[k]) for k in ['open','high','low','close']]
        if not 0<l<=min(o,c)<=max(o,c)<=h or int(r['tick_volume'])<0 or r['origin']!='BROKER_CLOSED_HISTORY':raise ValueError('invalid closed bar')
    events=data['session'];sealed=bool(events and events[-1]['event']=='END')
    if not events or events[0]['event']!='BEGIN':raise ValueError('missing BEGIN')
    if sealed:
        end=events[-1]
        for key,part in [('tick_rows',ticks),('heartbeat_rows',beats),('bar_rows',bars),('order_rows',orders)]:
            if int(end[key])!=len(part):raise ValueError('END footer count differs: '+key)
        if int(end['tick_callbacks'])<len(ticks):raise ValueError('callback count below written rows')
    charge=[];converted=[];contract=finite(m['contract_size'])
    for r in orders:
        lot=finite(r['lots']);commission=finite(r['commission'])
        if lot<=0 or int(r['type']) not in [0,1] or r['symbol']!=m['symbol'] or r['history_source']!='MT4_LOADED_HISTORY':raise ValueError('invalid closed order')
        if int(r['closed_broker_seconds'])<int(r['opened_broker_seconds']):raise ValueError('closed order reversed time')
        for key in ['profit','swap','entry_price','exit_price']:finite(r[key])
        # MT4 commission is signed; a positive value is not silently made a cost.
        cost_per_lot=-commission/lot
        if r['currency']=='USD' and m['currency']=='USD' and contract>0 and m['symbol'].startswith('EURUSD'):
            charge.append(cost_per_lot);converted.append(cost_per_lot/(contract*.0001))
    gaps=[(b-a)/1000 for a,b in zip(elapsed,elapsed[1:])]
    server=[int(r['quote_server_seconds']) for r in ticks];utc=[int(r['pc_utc_seconds']) for r in ticks]
    flags=[]
    if int(m['digits']) not in [4,5] or finite(m['point'])<=0 or finite(m['tick_size_price'])<=0 or contract<=0:flags.append('SYMBOL_METADATA_NOT_READY')
    if not sealed:flags.append('UNSEALED_CAPTURE')
    if sealed and events[-1]['io_ok']!='1':flags.append('IO_OR_SOURCE_CHANGE_REVIEW')
    if invalid:flags.append('INVALID_QUOTES_PRESENT')
    if any(b<a for a,b in zip(server,server[1:])):flags.append('BROKER_QUOTE_CLOCK_REGRESSION')
    if any(b<a for a,b in zip(utc,utc[1:])):flags.append('PC_UTC_REGRESSION')
    if not ticks:flags.append('NO_TICK_CALLBACKS')
    if len(bars)<64:flags.append('INSUFFICIENT_CLOSED_HISTORY')
    if any(r['connected']!='1' for r in beats):flags.append('DISCONNECTED_HEARTBEATS')
    return {'stage':'CAPTURE_QUALITY_NOT_STRATEGY_BACKTEST','sealed_local_files':sealed,'status':'NEEDS_REVIEW' if flags else 'LOCAL_FILES_CONSISTENT',
        'flags':flags,'tick_callbacks_written':len(ticks),'heartbeat_rows':len(beats),'closed_bars':len(bars),'closed_order_rows':len(orders),
        'invalid_quotes':invalid,'arrival_gaps_over3s':sum(x>3 for x in gaps),'max_arrival_gap_seconds':max(gaps,default=None),
        'recorded_commission_cost_USD_per_lot_median':statistics.median(charge) if charge else None,
        'recorded_commission_cost_pips_median':statistics.median(converted) if converted else None,
        'commission_scope':'Signed commission on exported closed demo market-order tickets; loaded MT4 history only. Not a real-account rate guarantee; no rows means unknown.',
        'broker_millisecond_timestamps_available':False,'complete_broker_tick_stream_proven':False,'economic_validation_completed':False,
        'source_manifest':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob('*.csv'))}}

def bo(path,kind):
    data=rows(path,'bo_'+kind)
    identifiers=set()
    for r in data:
        if not r['record_id'] or r['record_id'] in identifiers:raise ValueError('missing/duplicate BO record_id')
        identifiers.add(r['record_id'])
        if r['account_mode']!='DEMO' or not r['platform'] or not r['asset_label'] or not r['source_reference']:raise ValueError('BO demo/platform/source reference missing')
        if kind=='quotes':
            timestamp(r['observed_at_iso'])
            if finite(r['platform_price'])<=0:raise ValueError('BO platform price')
            for k in ['payout_5m','payout_10m','payout_15m']:
                if r[k] and not 0<finite(r[k])<=1:raise ValueError('Payout fraction must be like0.82, not82')
        else:
            if r['direction'] not in ['CALL','PUT'] or r['result'] not in ['WIN','LOSS','TIE','UNAVAILABLE']:raise ValueError('BO direction/result')
            if timestamp(r['expires_at_iso'])<=timestamp(r['opened_at_iso']):raise ValueError('BO expiry time')
            if not 0<finite(r['payout_fraction'])<=1 or finite(r['stake'])<=0:raise ValueError('BO payout/stake')
            if finite(r['entry_platform_price'])<=0:raise ValueError('BO entry price')
            if r['expiry_platform_price'] and finite(r['expiry_platform_price'])<=0:raise ValueError('BO expiry price')
            if r['result']!='UNAVAILABLE' and not r['expiry_platform_price']:raise ValueError('Settled BO result needs platform expiry price')
    return {'stage':'BO_PLATFORM_DATA_INGEST_NOT_PERFORMANCE_VALIDATION','records':len(data),'status':'STRUCTURE_VALID_NOT_INDEPENDENTLY_AUTHENTICATED' if data else 'NO_DATA',
        'actual_platform_quotes_required':True,'MT4_reference_not_substituted':True,'profitability_estimated':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path);p.add_argument('--bo-quotes',type=Path);p.add_argument('--bo-trades',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result={}
    if a.capture:result['capture']=capture(a.capture)
    if a.bo_quotes:result['bo_quotes']=bo(a.bo_quotes,'quotes')
    if a.bo_trades:result['bo_trades']=bo(a.bo_trades,'trades')
    if not result:p.error('provide at least one input')
    a.output.mkdir(parents=True,exist_ok=False);(a.output/'quality.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
