"""Build an audited research dataset; no training, activation or broker API."""
import csv
import gzip
import hashlib
import io
import json
import math
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from .price_behavior import PriceWindow,CONTRACT,CHANNELS,FRAMES,temporal_partition
from .native_ledger import decode_bytes
from .demo_learning import read_policy
from .origin import read_origin
from .history_learning import completion_row
from .market_sessions import classify,TIMEZONE_DATABASE

HORIZONS=(5,15,30)
INPUT_HEADER=b'schema,logic_version,session,sequence,event_type,time_ms_estimated,server_time_seconds,bid,ask,shadow_mode'
def sha(blob):return hashlib.sha256(blob).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def read_frozen(ref):
    blob=Path(ref['path']).read_bytes()
    if sha(blob)!=ref['sha256'] or len(blob)!=ref['bytes']:raise ValueError('Frozen parent changed: '+ref['path'])
    return json.loads(blob)

def extract_boundaries(root,manifest,targets,session_clock=None):
    """First TICK >= target, <=2s. Targets are sorted unique market times."""
    target=sorted(set(targets));result={};cursor=0;previous={};last=0;receipts=[];events=Counter()
    if {p.name for p in root.glob('input_*.csv')}!={r['file'] for r in manifest}:raise ValueError('Replay file inventory changed')
    for meta in manifest:
        p=root/meta['file'];before=p.stat();h=hashlib.sha256();size=0
        with p.open('rb') as f:
            header=f.readline();h.update(header);size+=len(header)
            if header.rstrip(b'\r\n')!=INPUT_HEADER:raise ValueError('Replay schema')
            for line,raw in enumerate(f,2):
                h.update(raw);size+=len(raw)
                if not raw.endswith(b'\n'):raise ValueError('Partial input row')
                v=raw.rstrip(b'\r\n').split(b',')
                if len(v)!=10 or v[0]!=b'2' or v[1]!=b'2026101707' or v[9]!=b'1':raise ValueError('Replay identity')
                sid=v[2].decode('ascii');seq=int(v[3]);kind=v[4];t=int(v[5]);old=previous.get(sid)
                if seq!=(old[0]+1 if old else 1) or t<last or (old and t<old[1]):raise ValueError('Replay sequence/clock')
                previous[sid]=(seq,t);last=t;events[kind.decode('ascii')]+=1
                if kind not in (b'TICK',b'TIMER',b'PAUSE_ON',b'PAUSE_OFF'):raise ValueError('Replay event type')
                if kind!=b'TICK':continue
                bid,ask=float(v[7]),float(v[8])
                if int(v[6])*1000!=t or not math.isfinite(bid) or not math.isfinite(ask) or bid<=0 or ask<bid:raise ValueError('Replay quote')
                while cursor<len(target) and target[cursor]<=t:
                    due=target[cursor];cursor+=1
                    result[due]=dict(points=int(math.floor(bid*100000+.5)) if t-due<=2000 else None,
                        observed_ms=t,lag_ms=t-due,session=sid,input_file=p.name,input_line=line,input_sequence=seq,
                        reason=None if t-due<=2000 else 'NO_TICK_WITHIN_2S')
        after=p.stat()
        if (after.st_size,after.st_mtime_ns)!=(before.st_size,before.st_mtime_ns) or size!=meta['bytes'] or h.hexdigest()!=meta['sha256']:raise ValueError('Replay bytes changed: '+p.name)
        receipts.append(dict(file=p.name,bytes=size,sha256=h.hexdigest()))
    for due in target[cursor:]:result[due]=dict(points=None,observed_ms=None,lag_ms=None,reason='NO_TICK_BEFORE_SEALED_END',session=None)
    return result,dict(input_manifests=receipts,input_events=dict(events),boundaries=len(target))

def label(entry,exit):
    if entry['points'] is None or exit['points'] is None:return 9,'UNAVAILABLE'
    if entry['session']!=exit['session']:return 9,'QUOTE_SESSION_CHANGED'
    move=exit['points']-entry['points'];return (1 if move>0 else -1 if move<0 else 0),'UP' if move>0 else 'DOWN' if move<0 else 'TIE'

def build(plan_path,output):
    plan_path=Path(plan_path);plan=json.loads(plan_path.read_text());output=Path(output)
    if output.exists():raise ValueError('Fresh output required')
    if plan['contract']!=CONTRACT or plan['broker_utc_offset_minutes']!=0 or plan['horizons_minutes']!=list(HORIZONS):raise ValueError('Dataset contract/clock')
    parents={k:read_frozen(v) for k,v in plan['parents'].items()}
    expected_cases={r['id']:r for r in parents['native_cases']};audit={r['source_id']:r for r in parents['native_audit']['source_receipts']}
    replay={r['source_id']:r for r in parents['replay_audit']['source_receipts']}
    rows=[];feature_rows=[];y=[];source_receipts=[];seen=set();raw_candidates=0
    for source in plan['sources']:
        sid=source['id'];root=Path(source['path']);out_path=output.resolve()
        if out_path==root.resolve() or root.resolve() in out_path.parents:raise ValueError('Output overlaps source')
        policy=read_policy(root);origin=read_origin(root,policy);seal=completion_row(root)
        if origin!='BACKTEST_MT4' or len(list(root.glob('event_*.bin')))!=seal['sequence']:raise ValueError('Need sealed complete Tester source')
        window=PriceWindow();hasher=hashlib.sha256();native_hasher=hashlib.sha256();anchored=set();selected=[]
        for index in audit[sid]['indexes']:
            blob=(root/index['file']).read_bytes()
            if sha(blob)!=index['sha256'] or len(blob)!=index['bytes']:raise ValueError('Anchor index changed')
            for q in csv.DictReader(io.StringIO(blob.decode('ascii'))):
                if q['event_kind']!='1':continue
                seq=int(q['sequence']);filename=f'event_{seq:012d}.bin';raw=(root/filename).read_bytes();native=decode_bytes(raw,seq,compact=True);e=native['event'];cur=native['state']['current']
                t=int(q['analysis_start']);name=q['snapshot_ref'];available=int(q['observed_ms'])
                if name!=f'anchor_{t}.csv' or name in anchored or e['kind']!=1 or e['analysisStart']!=t or e['observedMs']!=available or native['state']['configHash']!=policy['config_hash'] or native['state']['feedHash']!=policy['feed_hash']:raise ValueError('Native/index disagreement')
                raw_anchor=(root/name).read_bytes();packet=list(csv.reader(io.StringIO(raw_anchor.decode('ascii'))))
                if packet[0]!=['BO_ANCHOR','2','2026101707','EURUSD',str(t),str(policy['config_hash']),'64'] or len(packet)!=66:raise ValueError('Snapshot schema')
                last_time=None
                for row in packet[2:]:
                    b=dict(time=int(row[0]),open=float(row[1]),high=float(row[2]),low=float(row[3]),close=float(row[4]),ticks=int(row[5]))
                    if last_time is not None and b['time']-last_time!=300:raise ValueError('Incomplete native M5 packet')
                    if b['time']+300>t:raise ValueError('Future native anchor bar')
                    window.observe(b,available);last_time=b['time']
                if last_time+300!=t:raise ValueError('Anchor target')
                anchored.add(name);hasher.update(f'{name}:{sha(raw_anchor)}\n'.encode());native_hasher.update(f'{filename}:{sha(raw)}\n'.encode());raw_candidates+=1
                key=f'{sid}:{t}'
                if key in expected_cases:
                    old=expected_cases[key]
                    if old['native_sha256']!=sha(raw) or old['anchor_sha256']!=sha(raw_anchor):raise ValueError('Frozen case identity changed')
                    identity=f"{policy['feed_hash']}:{policy['config_hash']}:{t}:PRELOCK32"
                    if identity in seen:raise ValueError('Duplicate sample in fixed source merge')
                    seen.add(identity)
                    selected.append(dict(sample_id=identity,source_id=sid,source_case=key,asof_ms=t*1000,cutoff_ms=(t+300)*1000-32000,
                        entry_ms=(t+300)*1000,native_anchor_file=name,native_anchor_sha256=sha(raw_anchor),native_file=filename,native_sha256=sha(raw),native_available_ms=available,
                        native_regime=cur['anchor']['regime'],native_setup=cur['candidate']['setup'],native_candidate_direction=cur['candidate']['direction'],
                        source_origin=origin,policy_hash=policy['policy_hash'],feed_hash=policy['feed_hash'],config_hash=policy['config_hash']))
        if anchored!={p.name for p in root.glob('anchor_*.csv')} or len(anchored)!=audit[sid]['all_anchors_verified'] or hasher.hexdigest()!=audit[sid]['anchor_manifest_sha256'] or native_hasher.hexdigest()!=audit[sid]['native_manifest_sha256']:raise ValueError('Anchor/native frozen manifest mismatch')
        targets=[]
        for r in selected:targets.extend([r['entry_ms']]+[r['entry_ms']+h*60000 for h in HORIZONS])
        boundary,quote_receipt=extract_boundaries(root,replay[sid]['input_manifests'],targets)
        print(f'{sid}: {len(anchored)} native anchors and {len(targets)} requested boundaries verified',flush=True)
        for r in selected:
            f=window.features(r['asof_ms'],r['cutoff_ms']);entry=boundary[r['entry_ms']];labels=[];facts={}
            for horizon in HORIZONS:
                due=r['entry_ms']+horizon*60000;exit=boundary[due];direction,status=label(entry,exit);labels.append(direction)
                facts[str(horizon)]=dict(status=status,direction=direction,target_ms=due,exit_quote=exit,
                    available_ms=max(entry['observed_ms'] or 0,exit['observed_ms'] or 0) if direction!=9 else None)
            session=classify(r['asof_ms']//1000);day=r['asof_ms']//86400000;minute=(r['asof_ms']//60000)%1440
            context=[math.sin(2*math.pi*minute/1440),math.cos(2*math.pi*minute/1440),math.sin(2*math.pi*((day+3)%7)/7),math.cos(2*math.pi*((day+3)%7)/7)]
            context.extend(float(session['mask']==i) for i in range(8));context.extend(f['coverage'][str(s)]/n for s,n in FRAMES)
            features=dict(frames=f['frames'],context=context)
            r.update(feature_contract=CONTRACT,feature_sha256=sha(canonical(features)),coverage=f['coverage'],session=session['session'],entry_quote=entry,outcomes=facts,
                partition=temporal_partition(r['asof_ms'],r['entry_ms']+30*60000+2000),history_previously_inspected=True,
                earliest_potential_feature_ms=r['asof_ms']-18*3600000,label_is_price_direction_not_trade_result=True,observer_age_used=False)
            rows.append(r);feature_rows.append(features);y.append(labels)
        source_receipts.append(dict(source_id=sid,origin=origin,seal=seal,raw_anchors=len(anchored),selected=len(selected),anchor_manifest_sha256=hasher.hexdigest(),native_manifest_sha256=native_hasher.hexdigest(),**quote_receipt))
    order=sorted(range(len(rows)),key=lambda i:rows[i]['asof_ms']);rows=[rows[i] for i in order];feature_rows=[feature_rows[i] for i in order];y=[y[i] for i in order]
    if len(rows)!=len(expected_cases):raise ValueError('Frozen anchor cohort incomplete')
    output.mkdir(parents=True)
    arrays={f'x_{s}':np.asarray([r['frames'][str(s)] for r in feature_rows],dtype=np.float64) for s,n in FRAMES}
    arrays.update(context=np.asarray([r['context'] for r in feature_rows],dtype=np.float64),labels=np.asarray(y,dtype=np.int8),asof_ms=np.asarray([r['asof_ms'] for r in rows],dtype=np.int64))
    np.savez_compressed(output/'price_behavior.npz',**arrays)
    (output/'rows.jsonl.gz').write_bytes(gzip.compress(b''.join(canonical(r)+b'\n' for r in rows),mtime=0))
    partitions={name:dict(rows=sum(r['partition']==name for r in rows),primary_status=dict(Counter(r['outcomes']['30']['status'] for r in rows if r['partition']==name))) for name in sorted({r['partition'] for r in rows})}
    report=dict(contract=CONTRACT,schema=1,rows=len(rows),raw_anchors=raw_candidates,overlap_anchors_not_counted_as_new=raw_candidates-len(rows),unique_samples=len(seen),frames=[list(x) for x in FRAMES],channels=CHANNELS,primary_horizon_minutes=30,secondary_horizons_minutes=[5,15],label_missing_value=9,
        normalization='Per-anchor closed price and deterministic transforms; no fitted scaler',time_contract='Verified broker UTC+0; first observed bar availability must precede scheduled prelock cutoff',partitions=partitions,
        outcomes={str(h):dict(Counter(r['outcomes'][str(h)]['status'] for r in rows)) for h in HORIZONS},source_receipts=source_receipts,plan_sha256=sha(plan_path.read_bytes()),timezone_database=TIMEZONE_DATABASE,
        observer_age_used=False,models_trained=False,activation_allowed=False,all_history_previously_inspected=True,independent_forward_evidence=False,split_embargo_minutes=18*60+35,
        price_source='SEALED_MT4_TESTER_BID_MODELLED',trade_results=False,training_required_next=True)
    (output/'DATASET_REPORT.json').write_bytes(canonical(report))
    (output/'MANIFEST_SHA256.json').write_bytes(canonical({p.name:sha(p.read_bytes()) for p in output.iterdir() if p.is_file()}))
    print(json.dumps({k:v for k,v in report.items() if k!='source_receipts'},indent=2));return report
