"""Exploratory closed-bar research; never a native EA or BO-platform backtest."""
import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import asdict, dataclass
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import subprocess

from market_sessions import classify, TIMEZONE_DATABASE

ROOT=Path(__file__).resolve().parent
PIP=.0001
QUANTUM=.00001
MODELS=('legacy_atr3_lead1_proxy','legacy_atr3_open_proxy','trend_pullback','range_rejection','breakout_momentum')

@dataclass(frozen=True)
class Bar:
    t:int
    o:float
    h:float
    l:float
    c:float
    v:int=0

@dataclass(frozen=True)
class Signal:
    model:str
    anchor:int
    entry:int
    direction:int
    atr:float

def broker_text(t):return dt.datetime.fromtimestamp(t,dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
def broker_day(t):return broker_text(t)[:10]
def broker_week(t):
    d=dt.datetime.fromtimestamp(t,dt.timezone.utc);w=d.isocalendar();return f'{w.year}-W{w.week:02d}'
def session(t,offset=0):return classify(t-offset*60)['session']

def load_bars(path):
    raw=path.read_bytes();bars=[]
    for n,row in enumerate(csv.reader(raw.decode('utf-8-sig').splitlines()),1):
        if len(row)!=7:raise ValueError(f'row{n}: expected7columns')
        t=int(dt.datetime.strptime(row[0]+' '+row[1],'%Y.%m.%d %H:%M').replace(tzinfo=dt.timezone.utc).timestamp())
        o,h,l,c=map(float,row[2:6]);v=int(row[6])
        if t%300 or not all(math.isfinite(x) and x>0 for x in [o,h,l,c]) or not l<=min(o,c)<=max(o,c)<=h or v<0:raise ValueError(f'row{n}: invalid OHLC/time/volume')
        if bars and t<=bars[-1].t:raise ValueError(f'row{n}: duplicate/nonascending time')
        bars.append(Bar(t,o,h,l,c,v))
    gaps=[b.t-a.t for a,b in zip(bars,bars[1:]) if b.t-a.t!=300]
    return bars,{'sha256':hashlib.sha256(raw).hexdigest(),'bars':len(bars),'first_broker':broker_text(bars[0].t),'last_broker':broker_text(bars[-1].t),
                 'gap_count':len(gaps),'short_gap_count':sum(x<=86400 for x in gaps),'short_missing_m5':sum(x//300-1 for x in gaps if x<=86400)}

def native_scan(bars,output):
    binary=output/'native_scan'
    p=subprocess.run(['g++','-std=c++17','-O2',str(ROOT/'native_scan.cpp'),'-o',str(binary)],capture_output=True,text=True)
    (output/'native_compile.log').write_text(p.stderr);p.check_returncode()
    text=str(len(bars))+'\n'+'\n'.join(f'{b.t} {b.o:.17g} {b.h:.17g} {b.l:.17g} {b.c:.17g} {b.v}' for b in bars)+'\n'
    p=subprocess.run([str(binary)],input=text,capture_output=True,text=True,check=True)
    (output/'native_scan.csv').write_text(p.stdout)
    rows=list(csv.DictReader(p.stdout.splitlines()))
    if not all(r['config_hash']=='2669644079' for r in rows):raise ValueError('unexpected native config')
    return {int(r['anchor']):r for r in rows}

def atr14(history,end=63):
    return sum(max(history[j].h-history[j].l,abs(history[j].h-history[j-1].c),abs(history[j].l-history[j-1].c)) for j in range(end-13,end+1))/14

def hypotheses(history):
    """Only closed bars. No entry bar OHLC, target label or native lock input."""
    if len(history)!=64 or any(b.t-a.t!=300 for a,b in zip(history,history[1:])):return None
    a=atr14(history);prev=atr14(history,62);trigger=history[-1];rng=trigger.h-trigger.l
    output={m:0 for m in MODELS[2:]}
    if a<=0 or a>30*PIP or rng>2.5*prev or rng<=0:return a,output
    fast=statistics.fmean(x.c for x in history[-21:-1]);slow=statistics.fmean(x.c for x in history[-51:-1]);older=statistics.fmean(x.c for x in history[-56:-6])
    low=min(x.l for x in history[-25:-1]);high=max(x.h for x in history[-25:-1]);body=trigger.c-trigger.o;location=(trigger.c-trigger.l)/rng
    retrace=history[-2].c-history[-5].c
    if fast>slow and slow>older and retrace<0 and trigger.l<=fast+.1*prev and trigger.c>fast+.05*prev and body>0 and location>=.6:output['trend_pullback']=1
    elif fast<slow and slow<older and retrace>0 and trigger.h>=fast-.1*prev and trigger.c<fast-.05*prev and body<0 and location<=.4:output['trend_pullback']=-1
    if abs(fast-slow)<=prev:
        if trigger.l<low-.05*prev and trigger.c>low+.05*prev and body>0 and location>=.6:output['range_rejection']=1
        elif trigger.h>high+.05*prev and trigger.c<high-.05*prev and body<0 and location<=.4:output['range_rejection']=-1
    if fast>slow and trigger.c>high+.1*prev and body>=.5*rng and location>=.75:output['breakout_momentum']=1
    elif fast<slow and trigger.c<low-.1*prev and -body>=.5*rng and location<=.25:output['breakout_momentum']=-1
    return a,output

def make_signals(bars,native):
    signals={m:{} for m in MODELS};history=[];windows=0
    for b in bars:
        if history and b.t-history[-1].t!=300:history=[]
        if len(history)==64:
            windows+=1;answer=hypotheses(history);a,new=answer
            r=native[b.t]
            if abs(a-float(r['atr_raw']))>1e-15:raise ValueError('Python/native ATR mismatch')
            direction=int(r['baseline_direction'])
            if direction:
                for model,delay in [(MODELS[0],300),(MODELS[1],0)]:signals[model][b.t+delay]=Signal(model,b.t,b.t+delay,direction,a)
            for model,direction in new.items():
                if direction:signals[model][b.t]=Signal(model,b.t,b.t,direction,a)
        history.append(b)
        if len(history)>64:history.pop(0)
    if windows!=len(native):raise ValueError('native/Python window coverage mismatch')
    return signals,windows

def binary_reference(bars,signals,payout=.82):
    by_time={b.t:b for b in bars};trades=[]
    for t,s in sorted(signals.items()):
        row={'model':s.model,'anchor':s.anchor,'entry':t,'exit':t+300,'direction':s.direction,'status':'RESOLVED','outcome':'','return_units':None}
        if t not in by_time or t+300 not in by_time:row.update(status='UNAVAILABLE_BOUNDARY')
        else:
            change=s.direction*(by_time[t+300].o-by_time[t].o)
            outcome=0 if abs(change)<=1e-10 else (1 if change>0 else -1)
            row.update(outcome={0:'TIE',1:'WIN',-1:'LOSS'}[outcome],return_units=payout if outcome==1 else (-1. if outcome<0 else 0.))
        trades.append(row)
    return trades

def forex_reference(bars,signals,cost,path):
    spread=cost['spread_pips']*PIP;fees=cost['commission_roundtrip_pips']+cost['slippage_roundtrip_pips'];trades=[];position=None;previous=None;blocked=Counter();available_times={b.t for b in bars}
    def close(b,price,why,ambiguous=False,at_open=False):
        nonlocal position
        p=position;net=p['direction']*(price-p['price'])/PIP-fees
        trades.append({'model':p['model'],'anchor':p['anchor'],'entry':p['entry'],'exit':b.t if at_open else b.t+300,'direction':p['direction'],
            'status':'RESOLVED','why':why,'ambiguous':ambiguous,'entry_price':p['price'],'exit_price':price,'stop_pips':p['distance']/PIP,'net_pips':net,'return_R':net/(p['distance']/PIP)})
        position=None
    def unavailable(b,why):
        nonlocal position
        p=position;trades.append({'model':p['model'],'anchor':p['anchor'],'entry':p['entry'],'exit':b.t,'direction':p['direction'],
            'status':why,'why':why,'ambiguous':False,'entry_price':p['price'],'exit_price':None,'stop_pips':p['distance']/PIP,'net_pips':None,'return_R':None});position=None
    def mark(b):
        if position is None:return
        p=position;side=0 if p['direction']>0 else spread;o,h,l=b.o+side,b.h+side,b.l+side
        stop_open=o<=p['stop'] if p['direction']>0 else o>=p['stop'];take_open=o>=p['take'] if p['direction']>0 else o<=p['take']
        if stop_open:close(b,o,'OPEN_STOP_GAP',at_open=True);return
        if take_open:close(b,p['take'],'OPEN_TAKE_CAPPED',at_open=True);return
        if b.t-p['entry']>=3600:close(b,o,'MAX_HOLD',at_open=True);return
        hit_stop=l<=p['stop'] if p['direction']>0 else h>=p['stop'];hit_take=h>=p['take'] if p['direction']>0 else l<=p['take']
        ambiguous=hit_stop and hit_take
        if hit_stop and (not hit_take or path=='stop_first'):close(b,p['stop'],'STOP',ambiguous)
        elif hit_take:close(b,p['take'],'TAKE',ambiguous)
    for b in bars:
        occupied=position is not None
        if position is not None and previous is not None and b.t-previous.t!=300:unavailable(b,'UNAVAILABLE_DATA_GAP')
        if occupied:
            mark(b)
            if b.t in signals:blocked['position_at_bar_open']+=1
        elif b.t in signals:
            s=signals[b.t];distance=math.ceil(max(1.5*s.atr,6*PIP)/QUANTUM-1e-9)*QUANTUM
            if distance>30*PIP+1e-10:blocked['stop_over30pips']+=1
            else:
                price=b.o+(spread if s.direction>0 else 0.)
                position={'model':s.model,'anchor':s.anchor,'entry':b.t,'direction':s.direction,'price':price,'distance':distance,
                          'stop':price-s.direction*distance,'take':price+s.direction*2*distance}
                mark(b)
        previous=b
    if position is not None:unavailable(bars[-1],'UNAVAILABLE_END')
    blocked['missing_entry_bar']=sum(t not in available_times for t in signals)
    return trades,dict(blocked)

def weekly_ci(trades,key,weeks,reps=2000,seed=20261028):
    blocks={w:[0.,0] for w in weeks}
    for row in trades:
        if row.get(key) is None:continue
        b=blocks[broker_week(row['entry'])];b[0]+=row[key];b[1]+=1
    values=list(blocks.values());rng=random.Random(seed);means=[]
    if sum(x[1] for x in values)<2 or len(values)<2:return None,None
    for _ in range(reps):
        total=0.;count=0
        for _ in values:
            a,n=values[rng.randrange(len(values))];total+=a;count+=n
        if count:means.append(total/count)
    means.sort()
    if not means:return None,None
    return means[int(.025*(len(means)-1))],means[int(.975*(len(means)-1))]

def metrics(rows,key):
    resolved=[r for r in rows if r.get(key) is not None];values=[r[key] for r in resolved];equity=peak=drawdown=0.
    for value in values:equity+=value;peak=max(peak,equity);drawdown=max(drawdown,peak-equity)
    positive=sum(x for x in values if x>0);negative=-sum(x for x in values if x<0)
    return {'entered':len(rows),'resolved':len(values),'unavailable':len(rows)-len(values),'sum_return':sum(values),'mean_return':statistics.fmean(values) if values else None,
            'profit_factor':positive/negative if negative>0 else None,'max_drawdown_units':drawdown,'positive_trades':sum(x>0 for x in values),
            'negative_trades':sum(x<0 for x in values),'zero_trades':sum(x==0 for x in values)}

def dump(path,rows):
    if not rows:path.write_text('');return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def run(source,output,bootstrap_reps=2000,broker_offset=0):
    protocol=json.loads((ROOT/'protocol.json').read_text());output.mkdir(parents=True,exist_ok=False)
    bars,audit=load_bars(source)
    if audit['sha256']!=protocol['source_sha256']:raise ValueError('Protocol covers a different frozen input; declare a new dataset protocol before running')
    native=native_scan(bars,output);signals,windows=make_signals(bars,native)
    weeks=sorted({broker_week(b.t) for b in bars});summaries=[];breakdowns=[];all_trades=[];sensitivity=[]
    for model in MODELS:
        for payout in protocol['binary']['sensitivity_payouts']:
            rows=binary_reference(bars,signals[model],payout);label=f'payout{payout:.2f}';key='return_units'
            stat=metrics(rows,key);lo,hi=weekly_ci(rows,key,weeks,bootstrap_reps)
            wins=sum(r['outcome']=='WIN' for r in rows);loss=sum(r['outcome']=='LOSS' for r in rows);ties=sum(r['outcome']=='TIE' for r in rows)
            summaries.append(dict(market='BO_MT4_REFERENCE',model=model,scenario=label,path='bar_open_boundaries',signals=len(signals[model]),**stat,ci_low=lo,ci_high=hi,
                                  wins=wins,losses=loss,ties=ties,decisive_win_rate=wins/(wins+loss) if wins+loss else None,breakeven_win_rate=1/(1+payout),tie_loss_mean=(payout*wins-loss-ties)/(wins+loss+ties) if wins+loss+ties else None))
            for r in rows:r.update(market='BO_MT4_REFERENCE',scenario=label,path='bar_open_boundaries',entry_session=session(r['entry'],broker_offset))
            all_trades+=rows
            if payout==.82:
                for field,group in [('month',lambda r:broker_text(r['entry'])[:7]),('entry_session',lambda r:r['entry_session'])]:
                    buckets=defaultdict(list)
                    for r in rows:buckets[group(r)].append(r)
                    for bucket,subset in sorted(buckets.items()):breakdowns.append(dict(market='BO_MT4_REFERENCE',model=model,scenario=label,path='bar_open_boundaries',group=field,bucket=bucket,**metrics(subset,key)))
                for offset in [-60,0,60]:
                    buckets=defaultdict(list)
                    for r in rows:buckets[session(r['entry'],offset)].append(r)
                    for bucket,subset in sorted(buckets.items()):sensitivity.append(dict(market='BO_MT4_REFERENCE',model=model,assumed_broker_utc_offset_minutes=offset,entry_session=bucket,**metrics(subset,key)))
        for cost in protocol['forex']['costs']:
            for path in protocol['forex']['intrabar_ambiguity']:
                rows,blocked=forex_reference(bars,signals[model],cost,path);key='return_R';stat=metrics(rows,key);lo,hi=weekly_ci(rows,key,weeks,bootstrap_reps)
                summaries.append(dict(market='FX_REFERENCE_NOT_EA',model=model,scenario=cost['id'],path=path,signals=len(signals[model]),**stat,ci_low=lo,ci_high=hi,
                                      ambiguous_exits=sum(r['ambiguous'] for r in rows),**{'blocked_'+k:v for k,v in blocked.items()}))
                for r in rows:r.update(market='FX_REFERENCE_NOT_EA',scenario=cost['id'],path=path,entry_session=session(r['entry'],broker_offset))
                all_trades+=rows
                if cost['id']=='cost_addon' and path=='stop_first':
                    for field,group in [('month',lambda r:broker_text(r['entry'])[:7]),('entry_session',lambda r:r['entry_session'])]:
                        buckets=defaultdict(list)
                        for r in rows:buckets[group(r)].append(r)
                        for bucket,subset in sorted(buckets.items()):breakdowns.append(dict(market='FX_REFERENCE_NOT_EA',model=model,scenario=cost['id'],path=path,group=field,bucket=bucket,**metrics(subset,key)))
                    for offset in [-60,0,60]:
                        buckets=defaultdict(list)
                        for r in rows:buckets[session(r['entry'],offset)].append(r)
                        for bucket,subset in sorted(buckets.items()):sensitivity.append(dict(market='FX_REFERENCE_NOT_EA',model=model,assumed_broker_utc_offset_minutes=offset,entry_session=bucket,**metrics(subset,key)))
    dump(output/'summary.csv',summaries);dump(output/'breakdowns.csv',breakdowns);dump(output/'session_offset_sensitivity.csv',sensitivity);dump(output/'reference_trades.csv',all_trades)
    dump(output/'signals.csv',[asdict(s) for model in MODELS for s in signals[model].values()])
    meta={'stage':protocol['stage'],'source_audit':audit,'protocol_sha256':hashlib.sha256((ROOT/'protocol.json').read_bytes()).hexdigest(),
          'tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'native_cpp_sha256':hashlib.sha256((ROOT/'native_scan.cpp').read_bytes()).hexdigest(),
          'native_windows':windows,'native_reasons':dict(Counter(r['baseline_reason'] for r in native.values())),
          'signals_by_model':{m:len(s) for m,s in signals.items()},'scenario_streams':len(summaries),'bootstrap_reps':bootstrap_reps,'bootstrap_blocks':len(weeks),
          'timezone_database':TIMEZONE_DATABASE,'broker_utc_offset_minutes_assumed':broker_offset,'session_offset_independently_verified_for_whole_history':False,
          'native_ea_order_backtest_completed':False,'real_bo_platform_results':False,'news_vintages_available':False,'untouched_holdout_available':False,'strategy_selected_or_activated':False,
          'forex_reference_unavailable_counts':[{'model':r['model'],'scenario':r['scenario'],'path':r['path'],'unavailable':r['unavailable']} for r in summaries if r['market']=='FX_REFERENCE_NOT_EA']}
    (output/'run.json').write_text(json.dumps(meta,indent=2)+'\n');(output/'protocol.json').write_bytes((ROOT/'protocol.json').read_bytes())
    print(json.dumps(meta,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--bootstrap-reps',type=int,default=2000);p.add_argument('--broker-utc-offset-minutes',type=int,default=0)
    a=p.parse_args()
    if a.bootstrap_reps<100 or not -840<=a.broker_utc_offset_minutes<=840:p.error('invalid bootstrap/offset')
    run(a.source,a.output,a.bootstrap_reps,a.broker_utc_offset_minutes)
