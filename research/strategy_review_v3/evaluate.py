"""Offline native-stop/causal-M5-management proxies; no terminal or broker API."""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'strategy_review_v2'))
import study as v2
PIP=.0001
POLICIES=('ATR_FIXED_CONTROL','STRUCT_FIXED','STRUCT_BE','STRUCT_BE_TRAIL')

def plan(entry,d,atr,invalidation):
    if not math.isfinite(invalidation) or invalidation<=0 or d*(entry-invalidation)<=0:return None,'REJECTED_STRUCTURAL_STOP'
    distance=max(abs(entry-invalidation),1.5*atr,6*PIP,2*.00001)
    stop=round(math.floor((entry-distance)/.00001+1e-9)*.00001 if d>0 else math.ceil((entry+distance)/.00001-1e-9)*.00001,5)
    distance=abs(entry-stop)
    if distance>30*PIP+1e-10:return None,'REJECTED_STOP'
    take=round(math.ceil((entry+2*distance)/.00001-1e-9)*.00001 if d>0 else math.floor((entry-2*distance)/.00001+1e-9)*.00001,5)
    return {'stop':stop,'take':take,'distance':distance},'READY'

def protected_stop(entry,d,risk,old,take,quote,atr,policy):
    """Only the presently observed open and earlier closed ATR may move a stop."""
    if policy=='STRUCT_FIXED':return old,''
    profit=d*(quote-entry);desired=old;reason=''
    if profit>=risk:
        be=entry+d*.5*PIP
        if d*(be-desired)>0:desired=be;reason='BREAK_EVEN'
    if policy=='STRUCT_BE_TRAIL' and profit>=1.5*risk and atr is not None and atr>0:
        trail=quote-d*max(1.5*atr,3*PIP)
        if d*(trail-desired)>0:desired=trail;reason='ATR_TRAILING'
    if not reason:return old,''
    desired=round(math.floor(desired/.00001+1e-9)*.00001 if d>0 else math.ceil(desired/.00001-1e-9)*.00001,5)
    if d*(quote-desired)<.00002 or d*(desired-old)<.5*PIP-1e-10 or d*(take-quote)<=.00002 or d*(quote-old)<=0:return old,''
    return desired,reason

def simulate(book,s,invalidation,atrs,hold,path,policy):
    if policy not in POLICIES:raise ValueError('policy')
    if policy=='ATR_FIXED_CONTROL':
        row=v2.bracket(book,s,hold,path)
        stop=row['entry_price']-s.direction*row['stop_pips']*PIP if row['entered'] else None
        return dict(row,policy=policy,initial_stop=stop,final_stop=stop,stop_moves=0,be_moves=0,trail_moves=0)
    if hold<=0 or hold%5 or path not in ['stop_first','take_first']:raise ValueError('contract')
    row={'model':s.model,'anchor':s.anchor,'entry':s.entry,'direction':s.direction,'hold':hold,'path':path,'policy':policy,
        'entered':False,'status':'UNAVAILABLE_ENTRY','stop_pips':None,'entry_price':None,'exit_price':None,'exit':None,'exit_bar':None,
        'why':'','ambiguous':False,'gross_pips':None,'gross_R':None,'initial_stop':None,'final_stop':None,'stop_moves':0,'be_moves':0,'trail_moves':0}
    if s.entry not in book.bars:return row
    entry=book.bars[s.entry].o;p,status=plan(entry,s.direction,s.atr,invalidation)
    if p is None:row['status']=status;return row
    stop=p['stop'];take=p['take'];risk=p['distance']
    row.update(entered=True,status='PENDING',stop_pips=risk/PIP,entry_price=entry,initial_stop=stop,final_stop=stop)
    def close(t,price,why,at_open=False,ambiguous=False):
        gross=s.direction*(price-entry)/PIP
        row.update(status='RESOLVED',exit_price=price,exit=t if at_open else t+300,exit_bar=t,why=why,ambiguous=ambiguous,
            gross_pips=gross,gross_R=gross/(risk/PIP),final_stop=stop)
        return row
    for seconds in range(0,hold*60+1,300):
        t=s.entry+seconds
        if t not in book.bars:
            status,boundary=book.missing(t);row.update(status=status,exit=boundary,exit_bar=boundary);return row
        b=book.bars[t]
        if (b.o<=stop if s.direction>0 else b.o>=stop):return close(t,b.o,'OPEN_STOP_GAP',at_open=True)
        if (b.o>=take if s.direction>0 else b.o<=take):return close(t,take,'OPEN_TAKE_CAPPED',at_open=True)
        if seconds==hold*60:return close(t,b.o,'MAX_HOLD',at_open=True)
        new,reason=protected_stop(entry,s.direction,risk,stop,take,b.o,atrs.get(t),policy)
        if reason:
            assert s.direction*(new-stop)>0
            stop=new;row['stop_moves']+=1;row['be_moves']+=reason=='BREAK_EVEN';row['trail_moves']+=reason=='ATR_TRAILING';row['final_stop']=stop
        hit_stop=b.l<=stop if s.direction>0 else b.h>=stop
        hit_take=b.h>=take if s.direction>0 else b.l<=take
        if hit_stop and (not hit_take or path=='stop_first'):return close(t,stop,'STOP',ambiguous=hit_take)
        if hit_take:return close(t,take,'TAKE',ambiguous=hit_stop)
    raise AssertionError('unreachable')

def binary_labels(book,s,expiry):
    row={'model':s.model,'anchor':s.anchor,'entry':s.entry,'direction':s.direction,'expiry':expiry,'status':'RESOLVED','outcome':'','return82':None}
    for seconds in range(0,expiry*60+1,300):
        if s.entry+seconds not in book.bars:row['status']='UNAVAILABLE_BOUNDARY_OR_PATH';return row
    delta=s.direction*(book.bars[s.entry+expiry*60].o-book.bars[s.entry].o)
    outcome=0 if abs(delta)<=1e-10 else 1 if delta>0 else -1
    row.update(outcome={0:'TIE',1:'WIN',-1:'LOSS'}[outcome],return82=.82 if outcome>0 else -1 if outcome<0 else 0)
    return row

def structural_scan(bars,output):
    binary=output/'structural_scan'
    p=subprocess.run(['g++','-std=c++17','-O2',str(ROOT/'structural_scan.cpp'),'-o',str(binary)],text=True,capture_output=True)
    (output/'compile.log').write_text(p.stderr);p.check_returncode()
    data=str(len(bars))+'\n'+'\n'.join(f'{b.t} {b.o:.17g} {b.h:.17g} {b.l:.17g} {b.c:.17g} {b.v}' for b in bars)+'\n'
    p=subprocess.run([str(binary)],input=data,text=True,capture_output=True,check=True)
    (output/'structural_scan.csv').write_text(p.stdout)
    return list(csv.DictReader(p.stdout.splitlines()))

def invalidation(s,r):
    m=s.model
    if m in ['native_atr3_lead1','native_atr3_open']:return float(r['baseline_inv'])
    if m=='native_atr0_open':return float(r['no_floor_inv'])
    if m=='sr_unrouted':return float(r['sr_inv'])
    if m=='br_unrouted':return float(r['br_inv'])
    if m.startswith('tp_'):return float(r['tp_counterfact_inv'])
    return float(r['trigger_low'])-.10*s.atr if s.direction>0 else float(r['trigger_high'])+.10*s.atr

def stats(rows,fee):
    stat=v2.stats(rows,fee)
    valid=[r for r in rows if r['status']=='RESOLVED']
    stat.update(invalid_structural=sum(r['status']=='REJECTED_STRUCTURAL_STOP' for r in rows),
        protected_fraction=statistics.fmean(r['stop_moves']>0 for r in valid) if valid else None,
        gross_fee_breakeven_pips=statistics.fmean(r['gross_pips'] for r in valid) if valid else None)
    return stat

def run(source,signals_path,prior_scan,prior_labels,output):
    protocol=json.loads((ROOT/'protocol.json').read_text())
    if v2.sha(source)!=protocol['source_sha256'] or v2.sha(signals_path)!=protocol['signals_sha256']:raise ValueError('frozen input mismatch')
    output.mkdir(parents=True,exist_ok=False);(output/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    bars,audit=v2.v1.load_bars(source);book=v2.PriceBook(bars);raw=structural_scan(bars,output)
    original=v2.read(prior_scan);assert len(raw)==len(original)==47754
    for r,o in zip(raw,original):
        assert r['anchor']==o['anchor'] and abs(float(r['atr'])-float(o['atr']))<1e-15
        for field in ['baseline_direction','no_floor_direction','sr_unrouted','tp_unrouted','br_unrouted']:assert r[field]==o[field]
    scanned={int(r['anchor']):r for r in raw};atrs={t:float(r['atr']) for t,r in scanned.items()}
    signals=defaultdict(list)
    for r in v2.read(signals_path):signals[r['model']].append(v2.v1.Signal(r['model'],int(r['anchor']),int(r['entry']),int(r['direction']),float(r['atr'])))
    assert tuple(signals)==v2.MODELS
    old={(r['model'],int(r['anchor']),int(r['hold']),r['path']):r for r in v2.read(prior_labels)}
    weeks=sorted({v2.v1.broker_week(b.t) for b in bars});summaries=[];fx_labels=[];bo_labels=[];bo_summary=[];breakdowns=[];paired_fx=[];paired_bo=[];control_checks=0
    for model,group in signals.items():
        print(f'Evaluating {model}, {len(group)} unchanged candidates',flush=True)
        for hold in protocol['forex']['holds_minutes']:
            for path in protocol['forex']['paths']:
                all_policy={}
                for policy in POLICIES:
                    labels=[simulate(book,s,invalidation(s,scanned[s.anchor]),atrs,hold,path,policy) for s in group];all_policy[policy]=labels;fx_labels.extend(labels)
                    if policy=='ATR_FIXED_CONTROL':
                        for r in labels:
                            prior=old[model,r['anchor'],hold,path];assert r['status']==prior['status']
                            assert r['entered']==(prior['entered']=='True')
                            if r['status']=='RESOLVED':
                                assert r['why']==prior['why'] and r['exit']==int(prior['exit']) and abs(r['gross_R']-float(prior['gross_R']))<1e-12
                            control_checks+=1
                    selected=v2.one_position(labels)
                    for fee in protocol['forex']['combined_roundtrip_fee_pips']:
                        scored=[{'entry':r['entry'],'x':r['gross_R']-fee/r['stop_pips']} for r in selected if r['status']=='RESOLVED']
                        lo,hi=v2.v1.weekly_ci(scored,'x',weeks,2000,20261029)
                        summaries.append(dict(model=model,hold=hold,path=path,policy=policy,fee=fee,**stats(selected,fee),ci_low=lo,ci_high=hi,
                            all_candidate_count=len(labels),all_invalid_structural=sum(r['status']=='REJECTED_STRUCTURAL_STOP' for r in labels),all_stop_too_wide=sum(r['status']=='REJECTED_STOP' for r in labels)))
                        if hold==60 and path=='stop_first':
                            for field,key in [('period',lambda r:v2.period(r['entry'])),('month',lambda r:v2.v1.broker_text(r['entry'])[:7]),('session_UTC0_provisional',lambda r:v2.v1.session(r['entry']))]:
                                buckets=defaultdict(list)
                                for r in selected:buckets[key(r)].append(r)
                                for bucket,part in buckets.items():breakdowns.append(dict(model=model,policy=policy,fee=fee,group=field,bucket=bucket,**stats(part,fee)))
                if hold==60:
                    indexed=[{r['anchor']:r for r in all_policy[p]} for p in POLICIES[1:]]
                    for s in group:
                        parts=[g[s.anchor] for g in indexed]
                        if all(r['status']=='RESOLVED' for r in parts):
                            a,b,c=parts;assert abs(a['stop_pips']-b['stop_pips'])<1e-12 and abs(a['stop_pips']-c['stop_pips'])<1e-12
                            paired_fx.append({'model':model,'anchor':s.anchor,'entry':s.entry,'path':path,'BE_minus_FIXED':b['gross_R']-a['gross_R'],'TRAIL_minus_FIXED':c['gross_R']-a['gross_R']})
        expiry_groups={}
        for expiry in protocol['binary']['expiry_minutes']:
            labels=[binary_labels(book,s,expiry) for s in group];bo_labels.extend(labels);expiry_groups[expiry]={r['anchor']:r for r in labels}
            valid=[r for r in labels if r['status']=='RESOLVED'];wins=sum(r['outcome']=='WIN' for r in valid);losses=sum(r['outcome']=='LOSS' for r in valid);ties=sum(r['outcome']=='TIE' for r in valid)
            for payout in protocol['binary']['payouts']:
                scored=[dict(r,x=payout if r['outcome']=='WIN' else -1 if r['outcome']=='LOSS' else 0) for r in valid]
                lo,hi=v2.v1.weekly_ci(scored,'x',weeks,2000,20261029)
                bo_summary.append({'model':model,'expiry':expiry,'payout':payout,'candidates':len(labels),'resolved':len(valid),'unavailable':len(labels)-len(valid),
                    'wins':wins,'losses':losses,'ties':ties,'decisive_win_rate':wins/(wins+losses) if wins+losses else None,
                    'mean_stake_return':(payout*wins-losses)/len(valid) if valid else None,'tie_as_loss_mean':(payout*wins-losses-ties)/len(valid) if valid else None,'ci_low':lo,'ci_high':hi})
        for s in group:
            parts=[expiry_groups[e][s.anchor] for e in [5,10,15]]
            if all(r['status']=='RESOLVED' for r in parts):
                a,b,c=parts;paired_bo.append({'model':model,'anchor':s.anchor,'entry':s.entry,'10minus5':b['return82']-a['return82'],'15minus5':c['return82']-a['return82']})
    paired_summary=[]
    for market,data,fields in [('FX',paired_fx,['BE_minus_FIXED','TRAIL_minus_FIXED']),('BO',paired_bo,['10minus5','15minus5'])]:
        for m in v2.MODELS:
            for path in (['stop_first','take_first'] if market=='FX' else ['endpoint']):
                subset=[r for r in data if r['model']==m and (market=='BO' or r['path']==path)]
                for field in fields:
                    lo,hi=v2.v1.weekly_ci(subset,field,weeks,2000,20261029)
                    paired_summary.append({'market':market,'model':m,'path':path,'contrast':field,'same_entry_resolved':len(subset),'mean_delta':statistics.fmean(r[field] for r in subset) if subset else None,'ci_low':lo,'ci_high':hi})
    for name,data in [('forex_summary.csv',summaries),('forex_labels.csv',fx_labels),('binary_labels.csv',bo_labels),('binary_summary.csv',bo_summary),('breakdowns.csv',breakdowns),('paired_fx_labels.csv',paired_fx),('paired_bo_labels.csv',paired_bo),('paired_summary.csv',paired_summary)]:v2.dump(output/name,data)
    assert len(summaries)==1080 and len(bo_summary)==135
    code=[ROOT/'evaluate.py',ROOT/'structural_scan.cpp',ROOT/'protocol.json',ROOT.parent/'strategy_review_v2/study.py',ROOT.parent/'strategy_review_v2/candidate_scan.cpp',ROOT.parent/'strategy_review_v1/native_scan.cpp']
    result={'stage':protocol['stage'],'source':audit,'structural_scan_rows_matched':len(raw),'prior_ATR_control_labels_matched':control_checks,'signals':{m:len(g) for m,g in signals.items()},
        'forex_summary_rows':len(summaries),'binary_summary_rows':len(bo_summary),'code_hashes':{str(p.relative_to(ROOT.parent.parent)):v2.sha(p) for p in code},
        'prior_signals_hash':v2.sha(signals_path),'prior_labels_hash':v2.sha(prior_labels),'no_training_selection_activation_or_broker_actions':True,'M5_open_management_not_tick_equivalence':True}
    (output/'run.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['source','signals','prior-scan','prior-labels','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.source,a.signals,a.prior_scan,a.prior_labels,a.output)
