"""Batch audit, delayed labels and ex-post path studies; separate from watch."""
import csv
import hashlib
import io
import time
from . import CONTRACT
from .store import digest, atomic
from intelligence.manual_signals import review, record
from intelligence.demo_learning import points

DATASET = 'V224_AUDITED_OFFICIAL_SIGNAL_DATASET_V1'

def audit(collector, include_paths=False, broker_utc_offset_minutes=None):
    collector.poll(); collector.verify_prefix()
    source,store=collector.source,collector.store
    if collector.origin=='BACKTEST_MT4':
        with (source/'tester_complete.csv').open(encoding='utf-8-sig') as f:
            markers=list(csv.DictReader(f))
        cutoff=max((r['observed_ms'] for r in store.all('native')), default=0)
        if (len(markers)!=1 or int(markers[0]['schema'])!=1 or int(markers[0]['logic'])!=collector.policy['logic'] or
            int(markers[0]['sequence'])!=collector.last or int(markers[0]['observed_ms'])!=cutoff):
            raise ValueError('Completed Tester seal must match the native prefix')
    snapshot=dict(policy=collector.policy, native_records=collector.last, origin=collector.origin)
    book=review(source,snapshot)
    rows=[]
    for r in book['signals']:
        case=store.get('case',r['signal_id'])
        if case is None: raise ValueError('Audit publication not yet captured; retry audit')
        if r['status']=='PENDING': continue
        result,_=record(source/f"manual_v218_4_{r['signal_id']}.csv",collector.policy)
        if result['observed_ms']<case['expiry_ms']:
            raise ValueError('Outcome observed before expiry')
        label=dict(signal_id=r['signal_id'],status=r['status'],available_at_ms=result['observed_ms'],
                   entry_bid=r['entry_bid'],exit_bid=r['exit_bid'],price_source='MT4_BID',
                   native_canceled=r['native_canceled'],native_cancel_reason=r['native_cancel_reason'])
        store.put('label',r['signal_id'],label)
        rows.append(dict(case=case,label=label))
    # The complete review receipt includes the native LOCK and referenced TICK checks.
    dataset=dict(contract=DATASET, supervisor_contract=CONTRACT, origin=collector.origin,
        policy=collector.policy, identity_hash=digest(collector.identity), rows=rows,
        book=book, broker_utc_offset_minutes=broker_utc_offset_minutes,
        created_utc_ms=time.time_ns()//1000000, activation_allowed=False)
    dataset['sha256']=digest(dataset)
    collector.verify_prefix()
    if include_paths:
        paths=path_study(collector)
        atomic(store.output/'path_diagnostics.json',paths)
    atomic(store.output/'audited_dataset.json',dataset)
    store.put('audit',dataset['sha256'],dict(sha256=dataset['sha256'],rows=len(rows),
        created_utc_ms=dataset['created_utc_ms'],origin=collector.origin))
    store.commit(); collector.write_status()
    return dataset

def path_study(collector):
    """Observed windows only. Diagnostics are never feature inputs or training rows.

    Missing ticks remain unavailable; a price path does not prove a tradable
    setup. Every LOCK decision gets a fixed next-M5 counterfactual, not an
    outcome-selected entry/exit. Official signals retain their own expiry.
    """
    windows={}
    for r in collector.store.all('opportunity'):
        windows['decision:'+str(r['start'])]=dict(target=r['target']*1000,
            expiry=(r['target']+300)*1000,direction=1,decision=r)
    for r in collector.store.all('case'):
        windows['official:'+str(r['signal_id'])]=dict(target=r['entry_ms'],expiry=r['expiry_ms'],direction=r['direction'])
    ordered=sorted(windows.items(),key=lambda kv:kv[1]['target']); cursor=0; active={}; finished={}
    last_seq={};last_ms={};manifests=[];global_tick_ms=0
    for file in sorted(collector.source.glob('input_*.csv')):
        h=hashlib.sha256();prefix=0
        with file.open('rb') as stream:
            header=stream.readline();h.update(header);prefix+=len(header)
            names=next(csv.reader([header.decode('utf-8-sig')]))
            for raw in stream:
                if not raw.endswith(b'\n'):break
                h.update(raw);prefix+=len(raw)
                row=dict(zip(names,next(csv.reader([raw.decode('ascii')]))))
                sid=row['session'];seq=int(row['sequence']);ms=int(row['time_ms_estimated'])
                if seq!=last_seq.get(sid,0)+1 or ms<last_ms.get(sid,0):raise ValueError('Path input sequence/clock differs')
                last_seq[sid]=seq;last_ms[sid]=ms
                if int(row['schema'])!=2 or int(row['logic_version'])!=collector.policy['logic'] or int(row['shadow_mode'])!=1:
                    raise ValueError('Path input contract differs')
                if row['event_type']!='TICK':continue
                if ms<global_tick_ms:raise ValueError('Input sessions are not globally chronological; path study withheld')
                global_tick_ms=ms
                bid=points(row['bid'])
                if points(row['ask'])<bid:raise ValueError('Path negative spread')
                while cursor<len(ordered) and ordered[cursor][1]['target']<=ms:
                    key,w=ordered[cursor];active[key]=dict(w,entry=None,exit=None,mfe=None,mae=None,first_minute_favorable=False,
                        observed_ticks=0,last_tick_ms=None,max_observed_gap_ms=0)
                    cursor+=1
                for key,w in list(active.items()):
                    if ms>w['expiry']+2000:
                        finished[key]=w;del active[key];continue
                    if w['entry'] is None and w['target']<=ms<=w['target']+2000:w['entry']=bid
                    if w['expiry']<=ms<=w['expiry']+2000 and w['exit'] is None:w['exit']=bid
                    if w['entry'] is not None and w['target']<=ms<=w['expiry']:
                        move=(bid-w['entry'])*w['direction'];w['observed_ticks']+=1
                        w['mfe']=max(w['mfe'] or 0,move);w['mae']=min(w['mae'] or 0,move)
                        if w['last_tick_ms'] is not None:w['max_observed_gap_ms']=max(w['max_observed_gap_ms'],ms-w['last_tick_ms'])
                        w['last_tick_ms']=ms
                        if ms<=w['target']+60000 and move>0:w['first_minute_favorable']=True
        manifests.append(dict(file=file.name,bytes=prefix,sha256=h.hexdigest()))
    finished.update(active)
    for key,w in ordered[cursor:]:finished[key]=dict(w,entry=None,exit=None)
    for key,w in finished.items():
        move=None if w['entry'] is None or w['exit'] is None else (w['exit']-w['entry'])*w['direction']
        w['status']='UNAVAILABLE' if move is None else 'WIN' if move>0 else 'LOSS' if move<0 else 'TIE'
        if key.startswith('decision:'):
            w['call_status']=w['status'];w['put_status']={'WIN':'LOSS','LOSS':'WIN'}.get(w['status'],w['status'])
    return dict(contract='V224_EXPOST_OPPORTUNITY_PATHS_V1',origin=collector.origin,
        input_prefixes=manifests,windows=finished,feature_eligible=False,
        interpretation='Fixed-window MT4 counterfactuals; missing ticks never interpolated. Not proof of a missed opportunity; no new strategy is qualified.')
