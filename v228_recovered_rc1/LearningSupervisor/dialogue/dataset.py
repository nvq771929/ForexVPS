"""One last eligible pre-lock query per episode, strictly observed boundary BID."""
from bisect import bisect_left,bisect_right
import csv
import hashlib
import time
from . import FEATURE_CONTRACT
from .protocol import read_request
from supervisor.store import digest,atomic
from intelligence.demo_learning import points

DATASET='V224_PRELOCK_REQUEST_DATASET_V1'

def boundary_quotes(source,targets,cutoff):
    targets=sorted(set(targets));quotes={};manifests=[];sequences={};clocks={};global_ms=0
    if not targets:return quotes,manifests
    for path in sorted(source.glob('input_*.csv')):
        h=hashlib.sha256();used=0
        with path.open('rb') as stream:
            header=stream.readline();h.update(header);used+=len(header)
            names=next(csv.reader([header.decode('utf-8-sig')]))
            for raw in stream:
                if not raw.endswith(b'\n'):break
                row=dict(zip(names,next(csv.reader([raw.decode('ascii')]))))
                now=int(row['time_ms_estimated'])
                if now>cutoff:break
                h.update(raw);used+=len(raw);session=row['session'];seq=int(row['sequence'])
                if seq!=sequences.get(session,0)+1 or now<clocks.get(session,0):raise ValueError('Boundary replay sequence/clock gap')
                sequences[session]=seq;clocks[session]=now
                if row['event_type']!='TICK':continue
                if int(row['schema'])!=2 or int(row['logic_version'])!=2026101707 or int(row['shadow_mode'])!=1:raise ValueError('Boundary replay identity differs')
                if now<global_ms:raise ValueError('Input sessions not globally chronological')
                global_ms=now;bid=points(row['bid'])
                if points(row['ask'])<bid:raise ValueError('Negative replay spread')
                for target in targets[bisect_left(targets,now-2000):bisect_right(targets,now)]:
                    if target not in quotes:
                        quotes[target]=dict(bid_points=bid,observed_ms=now,session=session,sequence=seq,file=path.name)
        manifests.append(dict(file=path.name,bytes=used,sha256=h.hexdigest()))
    return quotes,manifests

def prepare(worker):
    store=worker.store;queries=store.all('query');chosen={}
    frozen={}
    for prefix in store.all('input_prefix'):
        name=prefix['file']
        if name not in frozen or prefix['bytes']>frozen[name]['bytes']:frozen[name]=prefix
    for name,prefix in frozen.items():
        with (worker.source/name).open('rb') as f:raw=f.read(prefix['bytes'])
        if len(raw)!=prefix['bytes'] or hashlib.sha256(raw).hexdigest()!=prefix['sha256']:
            raise ValueError('Previously audited tick prefix changed')
    for q in queries:
        check=read_request(worker.source/q['path'])
        if check['request_sha256']!=q['request_sha256'] or check['snapshot_sha256']!=q['snapshot_sha256']:
            raise ValueError('Frozen pre-lock query changed')
        r=q['meta'];key=(r['analysis_start'],r['horizon'])
        if key not in chosen or r['observed_ms']>chosen[key]['meta']['observed_ms']:chosen[key]=q
    # The native prefix is the availability cutoff; no later appended input is consumed.
    from intelligence.native_ledger import decode_bytes
    cutoff=0
    if worker.last:
        record=decode_bytes((worker.source/f'event_{worker.last:012d}.bin').read_bytes(),worker.last,compact=True)
        cutoff=record['event']['observedMs']
    if worker.origin=='BACKTEST_MT4':
        with (worker.source/'tester_complete.csv').open(encoding='ascii') as f:markers=list(csv.DictReader(f))
        if len(markers)!=1 or int(markers[0]['sequence'])!=worker.last or int(markers[0]['observed_ms'])!=cutoff:
            raise ValueError('Completed native Tester seal required')
    targets=[r['meta'][k]*1000 for r in chosen.values() for k in ('target','expiry')]
    quotes,manifest=boundary_quotes(worker.source,targets,cutoff);rows=[]
    for prefix in manifest:store.put('input_prefix',prefix['file']+':'+str(prefix['bytes']),prefix)
    for q in sorted(chosen.values(),key=lambda q:q['meta']['target']):
        r=q['meta'];entry=quotes.get(r['target']*1000);exit=quotes.get(r['expiry']*1000)
        status='PENDING' if cutoff<=(r['expiry']+2)*1000 else 'UNAVAILABLE'
        if entry is not None and exit is not None:
            move=(exit['bid_points']-entry['bid_points'])*r['direction'];status='WIN' if move>0 else 'LOSS' if move<0 else 'TIE'
        available=exit['observed_ms'] if entry is not None and exit is not None else max(cutoff,(r['expiry']+2)*1000+1)
        label=dict(status=status,available_at_ms=available,entry=entry,exit=exit,source='PRELOCK_DIRECTION_MT4_BOUNDARY_COUNTERFACTUAL')
        label['receipt_sha256']=digest(label)
        if status in ('WIN','LOSS','TIE'):store.put('label',q['path'],label)
        case=dict(signal_id=r['analysis_start'],entry_ms=r['target']*1000,expiry_ms=r['expiry']*1000,horizon=r['horizon'],
            feature_asof_ms=r['observed_ms'],features=q['feature']['features'],context=q['feature']['context'],sequence32=q['sequence32'],
            origin=q['origin'],policy=q['policy'],feature_contract=FEATURE_CONTRACT)
        rows.append(dict(case=case,label=label,query=q))
    dataset=dict(contract=DATASET,feature_contract=FEATURE_CONTRACT,origin=worker.origin,policy=worker.policy,
        broker_utc_offset_minutes=worker.offset,rows=rows,input_prefixes=manifest,native_prefix=worker.last,
        native_cutoff_ms=cutoff,selection='LAST_VALID_REQUEST_PER_EPISODE_BEFORE_DEADLINE_WITHOUT_OUTCOME_SELECTION',
        created_utc_ms=time.time_ns()//1000000,activation_allowed=False)
    dataset['sha256']=digest(dataset);store.commit();atomic(store.output/'prelock_dataset.json',dataset);return dataset
