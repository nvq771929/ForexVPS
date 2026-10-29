"""Known-history candidate and holding-time reference research; no broker APIs."""
import argparse
from collections import Counter,defaultdict,deque
import bisect
import csv
from dataclasses import asdict
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
V1=ROOT.parent/'strategy_review_v1'
sys.path.insert(0,str(V1))
import screen as v1
PIP=.0001
MODELS=tuple(json.loads((ROOT/'protocol.json').read_text())['models'])
CONDITIONS=('pullback','touch','slow_hold','body','location','reclaim')
REGIMES={0:'UNKNOWN',1:'RANGE',2:'ORDERLY_UP',3:'ORDERLY_DOWN',4:'EXPANSION_UP',5:'EXPANSION_DOWN',6:'TRANSITION',7:'COMPRESSION'}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
    with path.open() as f:return list(csv.DictReader(f))
def dump(path,rows):v1.dump(path,rows)

def scan(bars,output):
    binary=output/'candidate_scan'
    p=subprocess.run(['g++','-std=c++17','-O2',str(ROOT/'candidate_scan.cpp'),'-o',str(binary)],text=True,capture_output=True)
    (output/'compile.log').write_text(p.stderr);p.check_returncode()
    text=str(len(bars))+'\n'+'\n'.join(f'{b.t} {b.o:.17g} {b.h:.17g} {b.l:.17g} {b.c:.17g} {b.v}' for b in bars)+'\n'
    p=subprocess.run([str(binary)],input=text,text=True,capture_output=True,check=True)
    (output/'candidate_scan.csv').write_text(p.stdout)
    return list(csv.DictReader(p.stdout.splitlines()))

def verify_baseline(rows,path):
    old=read(path)
    if len(rows)!=len(old):raise ValueError('baseline window count differs')
    for r,o in zip(rows,old):
        for key in ['anchor','config_hash','regime','routed_setup','baseline_reason','baseline_direction','no_floor_reason','no_floor_direction']:
            if r[key]!=o[key]:raise ValueError(f'native parity: {key} at {r["anchor"]}')
        if abs(float(r['atr'])-float(o['atr_raw']))>1e-15:raise ValueError('ATR parity')

def atr_context(rows):
    """Past completed broker-day hourly means only, no present-day leakage."""
    prior=defaultdict(lambda:deque(maxlen=20));daily=defaultdict(list);day=None;out={}
    for r in rows:
        t=int(r['anchor']);date=v1.broker_day(t);hour=(t%86400)//3600
        if date!=day:
            for h,values in daily.items():prior[h].append(statistics.fmean(values))
            daily=defaultdict(list);day=date
        atr=float(r['atr'])/PIP;history=prior[hour]
        median=statistics.median(history) if len(history)>=10 else None
        ratio=atr/median if median and median>0 else None
        band='UNKNOWN' if ratio is None else 'LOW' if ratio<=.75 else 'TYPICAL' if ratio<=1.25 else 'HIGH'
        out[t]={'atr_ratio':ratio,'atr_band':band,'past_days':len(history),'hourly_past_median_pips':median}
        daily[hour].append(atr)
    return out

def make_signals(bars,rows):
    features={int(r['anchor']):r for r in rows};context=atr_context(rows)
    signals={m:{} for m in MODELS};history=[];windows=0
    for b in bars:
        if history and b.t-history[-1].t!=300:history=[]
        if len(history)==64:
            windows+=1;r=features[b.t];a,new=v1.hypotheses(history)
            if abs(a-float(r['atr']))>1e-15:raise ValueError('closed-window ATR mismatch')
            directions={'native_atr3_lead1':int(r['baseline_direction']),'native_atr3_open':int(r['baseline_direction']),
                'native_atr0_open':int(r['no_floor_direction'])}
            directions.update({m:int(r[m]) for m in MODELS[3:12]})
            directions.update({'v1_'+m:d for m,d in new.items()})
            for model,d in directions.items():
                if d:
                    entry=b.t+(300 if model=='native_atr3_lead1' else 0)
                    signals[model][entry]=v1.Signal(model,b.t,entry,d,a)
        history.append(b)
        if len(history)>64:history.pop(0)
    if windows!=len(rows):raise ValueError('window mismatch')
    return signals,features,context

def stop_distance(atr):
    if not math.isfinite(atr) or atr<=0:raise ValueError('ATR must be positive')
    return math.ceil(max(1.5*atr,6*PIP)/.00001-1e-9)*.00001

class PriceBook:
    def __init__(self,bars):
        self.bars={b.t:b for b in bars};self.times=sorted(self.bars)
    def missing(self,t):
        index=bisect.bisect_left(self.times,t)
        return ('UNAVAILABLE_END',t) if index==len(self.times) else ('UNAVAILABLE_DATA_GAP',self.times[index])

def bracket(book,s,hold,path,spread_pips=0):
    """Independent entry label. Exact tick exit times are unavailable."""
    if hold<=0 or hold%5 or path not in ['stop_first','take_first']:raise ValueError('unsupported contract')
    distance=stop_distance(s.atr)
    row={'model':s.model,'anchor':s.anchor,'entry':s.entry,'direction':s.direction,'hold':hold,'path':path,
        'entered':False,'status':'REJECTED_STOP' if distance>30*PIP+1e-10 else 'PENDING','stop_pips':distance/PIP,
        'entry_price':None,'exit_price':None,'exit':None,'exit_bar':None,'why':'','ambiguous':False,'gross_pips':None,'gross_R':None}
    if row['status']=='REJECTED_STOP':return row
    if s.entry not in book.bars:row.update(status='UNAVAILABLE_ENTRY');return row
    spread=spread_pips*PIP;entry=book.bars[s.entry].o+(spread if s.direction>0 else 0)
    stop=entry-s.direction*distance;take=entry+s.direction*2*distance
    row.update(entered=True,entry_price=entry)
    def close(t,price,why,at_open=False,ambiguous=False):
        gross=s.direction*(price-entry)/PIP
        row.update(status='RESOLVED',exit_price=price,exit=t if at_open else t+300,exit_bar=t,why=why,ambiguous=ambiguous,gross_pips=gross,gross_R=gross/(distance/PIP))
        return row
    for seconds in range(0,hold*60+1,300):
        t=s.entry+seconds
        if t not in book.bars:
            status,boundary=book.missing(t);row.update(status=status,exit=boundary,exit_bar=boundary);return row
        b=book.bars[t];side=0 if s.direction>0 else spread;o,h,l=b.o+side,b.h+side,b.l+side
        if (o<=stop if s.direction>0 else o>=stop):return close(t,o,'OPEN_STOP_GAP',at_open=True)
        if (o>=take if s.direction>0 else o<=take):return close(t,take,'OPEN_TAKE_CAPPED',at_open=True)
        if seconds==hold*60:return close(t,o,'MAX_HOLD',at_open=True)
        hit_stop=l<=stop if s.direction>0 else h>=stop
        hit_take=h>=take if s.direction>0 else l<=take
        if hit_stop and (not hit_take or path=='stop_first'):return close(t,stop,'STOP',ambiguous=hit_take)
        if hit_take:return close(t,take,'TAKE',ambiguous=hit_stop)
    raise AssertionError('unreachable')

def trajectory(book,s,hold,spread_pips=0):
    distance=stop_distance(s.atr)
    row={'model':s.model,'anchor':s.anchor,'entry':s.entry,'hold':hold,'status':'REJECTED_STOP' if distance>30*PIP+1e-10 else 'PENDING',
        'endpoint_R':None,'endpoint_up':None,'mfe_no_exit_R':None,'mae_no_exit_R':None}
    if row['status']=='REJECTED_STOP':return row
    if s.entry not in book.bars:row.update(status='UNAVAILABLE_ENTRY');return row
    spread=spread_pips*PIP;entry=book.bars[s.entry].o+(spread if s.direction>0 else 0)
    mfe=mae=0.
    for seconds in range(0,hold*60+1,300):
        t=s.entry+seconds
        if t not in book.bars:row.update(status=book.missing(t)[0]);return row
        b=book.bars[t];side=0 if s.direction>0 else spread
        if seconds==hold*60:
            endpoint=s.direction*(b.o+side-entry)/distance
            row.update(status='RESOLVED',endpoint_R=endpoint,endpoint_up=endpoint>1e-10,
                mfe_no_exit_R=max(mfe,endpoint),mae_no_exit_R=min(mae,endpoint));return row
        values=[s.direction*(p+side-entry)/distance for p in [b.l,b.h]]
        mfe=max(mfe,*values);mae=min(mae,*values)
    raise AssertionError('unreachable')

def one_position(rows):
    selected=[];busy=-1
    for r in sorted(rows,key=lambda r:r['entry']):
        if not r['entered'] or r['entry']<=busy:continue
        selected.append(r)
        if r['exit_bar'] is None:raise ValueError('entered sample has no exclusion boundary')
        busy=r['exit_bar']
    return selected

def stats(rows,fee=0):
    entered=[r for r in rows if r['entered']];valid=[r for r in entered if r['status']=='RESOLVED']
    values=[r['gross_R']-fee/r['stop_pips'] for r in valid]
    pips=[r['gross_pips']-fee for r in valid]
    return {'candidates':len(rows),'entered':len(entered),'resolved':len(valid),'unavailable':len(entered)-len(valid),
        'unavailable_entry':sum(r['status']=='UNAVAILABLE_ENTRY' for r in rows),
        'rejected_stop':sum(r['status']=='REJECTED_STOP' for r in rows),'mean_R':statistics.fmean(values) if values else None,
        'mean_pips':statistics.fmean(pips) if pips else None,'sum_R':sum(values),
        'positive_fraction':sum(x>1e-10 for x in values)/len(values) if values else None,
        'stop_fraction':sum(r['why'] in ['STOP','OPEN_STOP_GAP'] for r in valid)/len(valid) if valid else None,
        'take_fraction':sum(r['why'] in ['TAKE','OPEN_TAKE_CAPPED'] for r in valid)/len(valid) if valid else None,
        'time_exit_fraction':sum(r['why']=='MAX_HOLD' for r in valid)/len(valid) if valid else None,
        'ambiguous':sum(r['ambiguous'] for r in valid),
        'mean_hold_upper_minutes':statistics.fmean((r['exit']-r['entry'])/60 for r in valid) if valid else None}

def period(t):
    date=v1.broker_day(t)
    return 'FEB_APR' if date<'2026-05-01' else 'MAY_JUL' if date<'2026-08-01' else 'AUG_OCT'

def paired(rows,holds=(30,60,120)):
    grouped=defaultdict(dict)
    for r in rows:grouped[(r['model'],r['anchor'],r['direction'],r['path'])][r['hold']]=r
    out=[]
    for (model,anchor,d,path),group in grouped.items():
        if all(h in group and group[h]['status']=='RESOLVED' for h in holds):
            a,b,c=[group[h] for h in holds]
            out.append({'model':model,'anchor':anchor,'entry':a['entry'],'direction':d,'path':path,
                'R30':a['gross_R'],'R60':b['gross_R'],'R120':c['gross_R'],
                'delta60minus30':b['gross_R']-a['gross_R'],'delta120minus60':c['gross_R']-b['gross_R']})
    return out

def run(source,baseline,output):
    protocol=json.loads((ROOT/'protocol.json').read_text())
    if sha(source)!=protocol['source_sha256']:raise ValueError('dataset differs from frozen protocol')
    output.mkdir(parents=True,exist_ok=False)
    (output/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    bars,audit=v1.load_bars(source);rows=scan(bars,output);verify_baseline(rows,baseline)
    signals,features,contexts=make_signals(bars,rows)
    if len(rows)!=47754:raise ValueError('expected47754closed windows')
    weeks=sorted({v1.broker_week(b.t) for b in bars});book=PriceBook(bars)
    signal_rows=[]
    for model,group in signals.items():
        for s in group.values():signal_rows.append(dict(asdict(s),regime=REGIMES[int(features[s.anchor]['regime'])],**contexts[s.anchor]))
    dump(output/'signals.csv',signal_rows)
    dump(output/'anchor_context.csv',[dict(anchor=t,regime=REGIMES[int(features[t]['regime'])],**r) for t,r in contexts.items()])
    coverage=[]
    for field in ['regime','baseline_reason','no_floor_reason']:
        for name,n in Counter(r[field] for r in rows).items():coverage.append({'kind':field,'value':REGIMES[int(name)] if field=='regime' else name,'count':n})
    for m,g in signals.items():coverage.append({'kind':'model_candidates','value':m,'count':len(g)})
    common=[r for r in rows if r['tp_common']=='1']
    for k,name in enumerate(CONDITIONS):
        coverage.append({'kind':'tp_component_pass_among_common','value':name,'count':sum(bool(int(r['tp_mask'])&(1<<k)) for r in common),'denominator':len(common)})
    dump(output/'coverage.csv',coverage)
    binary=[];binary_labels=[];trades=[];trajectories=[];summaries=[];breakdowns=[];offsets=[]
    fees=protocol['forex']['roundtrip_combined_commission_and_slippage_pips'];holds=protocol['forex']['holds_minutes'];paths=protocol['forex']['paths']
    for model,group in signals.items():
        print(f'Computing {model}: {len(group)} candidate entries',flush=True)
        labels=v1.binary_reference(bars,group,.82);binary_labels.extend(labels)
        valid=[r for r in labels if r['return_units'] is not None]
        wins=sum(r['outcome']=='WIN' for r in valid);losses=sum(r['outcome']=='LOSS' for r in valid);ties=sum(r['outcome']=='TIE' for r in valid)
        for payout in protocol['binary']['sensitivity_payouts']:
            scored=[dict(r,score=payout if r['outcome']=='WIN' else -1 if r['outcome']=='LOSS' else 0) for r in valid]
            lo,hi=v1.weekly_ci(scored,'score',weeks,2000,20261029)
            binary.append({'model':model,'payout':payout,'signals':len(labels),'resolved':len(valid),'unavailable':len(labels)-len(valid),
                'wins':wins,'losses':losses,'ties':ties,'decisive_win_rate':wins/(wins+losses) if wins+losses else None,
                'breakeven_decisive_win_rate':1/(1+payout),'mean_stake_return':(payout*wins-losses)/len(valid) if valid else None,
                'tie_as_loss_mean':(payout*wins-losses-ties)/len(valid) if valid else None,'ci_low':lo,'ci_high':hi})
        for field,key in [('month',lambda r:v1.broker_text(r['entry'])[:7]),('period',lambda r:period(r['entry'])),
            ('session_UTC0_provisional',lambda r:v1.session(r['entry'])),('atr_band',lambda r:contexts[r['anchor']]['atr_band'])]:
            buckets=defaultdict(list)
            for r in valid:buckets[key(r)].append(r)
            for bucket,subset in buckets.items():
                breakdowns.append({'market':'BO_MT4_REFERENCE','model':model,'group':field,'bucket':bucket,'payout':.82,
                    'resolved':len(subset),'mean_stake_return':statistics.fmean(r['return_units'] for r in subset)})
        for hold in holds:
            trajectories.extend(trajectory(book,s,hold) for s in group.values())
            for path in paths:
                labels=[bracket(book,s,hold,path) for s in group.values()];trades.extend(labels)
                for sampling,subset in [('all_entries_overlapping_diagnostics',labels),('one_position_per_model_hold_path',one_position(labels))]:
                    for fee in fees:
                        stat=stats(subset,fee)
                        scored=[{'entry':r['entry'],'score':r['gross_R']-fee/r['stop_pips']} for r in subset if r['status']=='RESOLVED']
                        lo,hi=v1.weekly_ci(scored,'score',weeks,2000,20261029)
                        summaries.append(dict(model=model,hold=hold,path=path,sampling=sampling,fee_pips=fee,**stat,ci_low_R=lo,ci_high_R=hi))
                    if hold==60 and path=='stop_first':
                        for field,key in [('month',lambda r:v1.broker_text(r['entry'])[:7]),('period',lambda r:period(r['entry'])),
                            ('session_UTC0_provisional',lambda r:v1.session(r['entry'])),('atr_band',lambda r:contexts[r['anchor']]['atr_band'])]:
                            buckets=defaultdict(list)
                            for r in subset:buckets[key(r)].append(r)
                            for bucket,part in buckets.items():breakdowns.append(dict(market='FX_REFERENCE_NOT_EA',model=model,sampling=sampling,group=field,bucket=bucket,hold=60,fee_pips=.5,**stats(part,.5)))
                        for offset in [-60,0,60]:
                            buckets=defaultdict(list)
                            for r in subset:buckets[v1.session(r['entry'],offset)].append(r)
                            for bucket,part in buckets.items():offsets.append(dict(model=model,sampling=sampling,offset_minutes=offset,session=bucket,**stats(part,.5)))
    comparisons=paired(trades);paired_summary=[]
    for model in MODELS:
        for path in paths:
            selected=[r for r in comparisons if r['model']==model and r['path']==path]
            for key in ['delta60minus30','delta120minus60']:
                lo,hi=v1.weekly_ci(selected,key,weeks,2000,20261029)
                paired_summary.append({'model':model,'path':path,'contrast':key,'complete_same_entry_cohort':len(selected),
                    'mean_delta_R':statistics.fmean(r[key] for r in selected) if selected else None,'ci_low':lo,'ci_high':hi})
    trajectory_summary=[]
    for model in MODELS:
        for hold in holds:
            selected=[r for r in trajectories if r['model']==model and r['hold']==hold];valid=[r for r in selected if r['status']=='RESOLVED']
            trajectory_summary.append({'model':model,'hold':hold,'labels':len(selected),'resolved':len(valid),'unavailable_or_rejected':len(selected)-len(valid),
                'endpoint_positive_fraction':statistics.fmean(r['endpoint_up'] for r in valid) if valid else None,
                **{f'mean_{key}':statistics.fmean(r[key] for r in valid) if valid else None for key in ['endpoint_R','mfe_no_exit_R','mae_no_exit_R']}})
    for name,data in [('binary_labels.csv',binary_labels),('binary_summary.csv',binary),('bracket_labels.csv',trades),('forex_summary.csv',summaries),
        ('trajectory_labels.csv',trajectories),('trajectory_summary.csv',trajectory_summary),('paired_hold_labels.csv',comparisons),('paired_hold_summary.csv',paired_summary),
        ('breakdowns.csv',breakdowns),('session_offset_sensitivity.csv',offsets)]:dump(output/name,data)
    receipt={'stage':protocol['stage'],'source':audit,'closed_windows':len(rows),'native_baseline_all_rows_parity':True,'v1_baseline_scan_sha256':sha(baseline),
        'models':{m:len(s) for m,s in signals.items()},'fx_summary_rows':len(summaries),'bo_summary_rows':len(binary),
        'code_sha256':{str(p.relative_to(ROOT.parent.parent)):sha(p) for p in [ROOT/'study.py',ROOT/'candidate_scan.cpp',ROOT/'protocol.json',V1/'screen.py',V1/'native_scan.cpp',V1/'market_sessions.py']},
        'timezone_database':v1.TIMEZONE_DATABASE,'no_model_fit_or_activation':True,'actual_commission_known':False,
        'sampling_warning':'Overlapping labels are diagnostic, not independent portfolio trades. One-position variants have different entry cohorts. Paired holds use identical resolved entries.',
        'historical_data_known_no_untouched_holdout':True}
    (output/'run.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--baseline-scan',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.source,a.baseline_scan,a.output)
