"""Enroll from immutable LOCK facts first; attach matured price-proxy outcomes later."""
from collections import Counter,defaultdict
import csv,hashlib,json,math
from pathlib import Path
from . import candidate_features as cf
from .demo_learning import LOGIC,read_policy,points
from .origin import read_origin
from .native_ledger import event_paths,iter_directory
from .prepared_history import load
from .t1_corrected import correct_features,extract as causal_t1
from .progress import notify


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def base_row(start,lock,setup,direction,regime,ready,policy):
    return dict(sample_id=f"{policy['feed_hash']:08x}.{policy['policy_hash']:08x}.{start}.{policy['horizon']}",
        analysis_start=start,locked_at_ms=lock,feature_asof_ms=lock,entry_target=start+300,
        expiry_target=start+300+policy['horizon']*300,setup=setup,direction=direction,regime=regime,ready_at_lock=ready,
        features=None,feature_unavailable_reason=None,quality_status='PENDING',signed_points=None,available_at_ms=None,
        execution_signal_observed=False,is_execution_trade=False)


def set_label(row,status,move,available,cutoff):
    if status in ('UP','DOWN','TIE') and available is not None and available<cutoff:
        signed=row['direction']*move
        row.update(quality_status='FAVORABLE' if signed>0 else 'ADVERSE' if signed<0 else 'TIE',signed_points=signed,available_at_ms=available)
    elif status=='UNAVAILABLE':row['quality_status']='UNAVAILABLE'


def prepared(path):
    raw=Path(path).read_bytes();s,digest=load(path)
    if Path(path).read_bytes()!=raw:raise ValueError('Prepared cache changed during read')
    if 'research_t1' not in s:raise ValueError('V211 cache or raw journals required; never fabricate T+1')
    traces={r['analysis_start']:r for r in s.get('execution_traces',[])}
    rows=[];seen=set()
    for r in s['research_t1']:
        if not r['candidate_present']:continue
        if r['feature_asof_ms']!=r['locked_at_ms'] or not r['analysis_start']*1000<=r['locked_at_ms']<=(r['entry_target']-31)*1000:
            raise ValueError('Prepared candidate clock differs')
        ready=r['lock_reason']=='OK';trace=traces.get(r['analysis_start'])
        if trace and ready!=trace['published_at_lock']:raise ValueError('Candidate readiness differs from native LOCK')
        row=base_row(r['analysis_start'],r['locked_at_ms'],r['candidate_setup'],r['candidate_direction'],r['regime'],ready,s['policy'])
        row['features']=cf.extract(correct_features(r['features']),row['setup'],row['direction'])
        row['lock_reason']=r['lock_reason'];row['execution_signal_observed']=r['execution_signal_observed']
        set_label(row,r['status'],r['signed_points'],r['available_at_ms'],s['asof']*1000)
        rows.append(row);seen.add(r['analysis_start'])
    # Keep coverage visible for LOCKs absent from old entry-conditioned cache rows.
    for start,t in traces.items():
        if start in seen:continue
        row=base_row(start,t['lock_observed_ms'],t['setup'],t['candidate_direction'],None,t['published_at_lock'],s['policy'])
        row.update(feature_unavailable_reason='RAW_CAUSAL_LOCK_FEATURES_REQUIRED',quality_status='UNAVAILABLE',lock_reason=t['lock_reason'])
        rows.append(row)
    return finish(rows,s['policy'],s['origin'],s['asof']*1000,s['records'],digest,
        sorted({r['entry_target']//86400 for r in s['research_t1']}),dict(prepared_file_sha256=hashlib.sha256(raw).hexdigest(),raw_prefix=False))


def journals(source,progress=None):
    source=Path(source);p=read_policy(source);origin=read_origin(source,p)
    names=['data_origin.csv','demo_policy.csv'];marker=None
    if origin=='BACKTEST_MT4':
        names.append('tester_complete.csv')
        with (source/'tester_complete.csv').open(encoding='utf-8-sig') as stream:
            rr=list(csv.DictReader(stream))
        if len(rr)!=1:raise ValueError('Tester completion marker required')
        marker={k:int(v) for k,v in rr[0].items()}
        if marker.get('schema')!=1 or marker.get('logic')!=LOGIC:raise ValueError('Invalid Tester marker')
    metadata={name:(source/name).read_bytes() for name in names}
    paths=event_paths(source)
    if marker and len(paths)!=marker['sequence']:raise ValueError('Tester completion/file count differs')
    h=hashlib.sha256()
    for name,raw in metadata.items():h.update(name.encode());h.update(raw)
    groups=defaultdict(list);cutoff=0;count=0;calendar=set()
    def verified(path,raw):
        nonlocal count
        count+=1;h.update(path.name.encode());h.update(raw)
        if count%256==0 or count==len(paths):notify(progress,'read',done=count,total=len(paths),unit='BIN',detail='Immutable native prefix; no replay cutoff')
    for record in iter_directory(source,paths=paths,on_record=verified,compact=True):
        state,e=record['state'],record['event']
        if count==1 and state['sequence']!=1:raise ValueError('Complete native prefix from sequence1 required')
        if state['configHash']!=p['config_hash'] or state['feedHash']!=p['feed_hash']:raise ValueError('Journal identity changed')
        cutoff=max(cutoff,e['observedMs'])
        if e['kind']==3:calendar.add(e['targetTime']//86400)
        if e['analysisStart']>0 and e['kind'] in (3,5,6):groups[e['analysisStart']].append(record)
    if marker and (marker['sequence']!=count or marker['observed_ms']!=cutoff):raise ValueError('Tester seal differs from native prefix')
    if any((source/name).read_bytes()!=value for name,value in metadata.items()):raise ValueError('Journal metadata changed')
    rows=[];rule_facts={};counts=Counter()
    for start,records in sorted(groups.items()):
        locks=[r for r in records if r['event']['kind']==3]
        if len(locks)>1:raise ValueError('Duplicate candidate LOCK')
        if not locks:continue
        record=locks[0];e=record['event'];current=record['state']['current'];candidate=current['candidate'];d=candidate['direction'];setup=candidate['setup']
        counts['locks']+=1
        if not d:continue
        if d not in (-1,1) or setup not in (1,2,3):raise ValueError('Invalid candidate identity')
        ready=not current['canceled'] and e['validation']==2 and e['lockedAction']==d and e['reason']==0
        row=base_row(start,e['observedMs'],setup,d,e['regime'],ready,p)
        row['lock_reason']=str(e['reason'])
        if not start*1000<=e['observedMs']<=(e['targetTime']-31)*1000:
            row['feature_unavailable_reason']='LOCK_OUTSIDE_FORECAST_WINDOW'
        else:
            try:row['features']=cf.extract(causal_t1(current,e['observedMs']),setup,d)
            except ValueError:row['feature_unavailable_reason']='CAUSAL_T1_UNAVAILABLE'
        entries=[r['event'] for r in records if r['event']['kind']==5]
        outcomes=[r['event'] for r in records if r['event']['kind']==6 and r['event']['outcomeHorizon']==p['horizon']]
        if len(entries)>1 or len(outcomes)>1:raise ValueError('Duplicate candidate entry/outcome')
        if entries:
            entry=entries[0];row['execution_signal_observed']=bool(entry['signal'])
            if entry['targetTime']!=row['entry_target']:raise ValueError('Candidate entry target differs')
            if entry['signal'] and (not ready or entry['lockedDirection']!=d or entry['selectedHorizon']!=p['horizon']):
                raise ValueError('Candidate execution identity differs')
            valid=row['entry_target']*1000<=entry['observedMs']<=(row['entry_target']+2)*1000
            try:entry_points=points(entry['bid'])
            except ValueError:valid=False;entry_points=0
            if valid and outcomes:
                out=outcomes[0]
                if out['outcome']==9:row['quality_status']='UNAVAILABLE'
                else:
                    if (points(out['bid'])!=entry_points or out['targetTime']!=row['entry_target'] or
                        out['signal']!=entry['signal'] or
                        not row['expiry_target']*1000<=out['observedMs']<=(row['expiry_target']+2)*1000):raise ValueError('Candidate outcome outside exact boundary')
                    move=points(out['auxiliaryPrice'])-entry_points
                    if out['outcome']!=((move>0)-(move<0)):raise ValueError('Outcome disagrees with recorded prices')
                    set_label(row,'TIE' if move==0 else 'UP' if move>0 else 'DOWN',move,out['observedMs']+1000,cutoff)
            elif not valid or cutoff>(row['expiry_target']+2)*1000:row['quality_status']='UNAVAILABLE'
        elif cutoff>(row['entry_target']+2)*1000:row['quality_status']='UNAVAILABLE'
        rows.append(row)
    return finish(rows,p,origin,cutoff,count,h.hexdigest(),sorted(calendar),dict(raw_prefix=True,prefix_sequence=count,tester_sealed=marker is not None))


def finish(rows,policy,origin,cutoff,records,source_digest,days,receipt):
    rows=sorted(rows,key=lambda r:r['entry_target']);ids=[r['sample_id'] for r in rows]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate registered candidate')
    for r in rows:
        if r['features'] is not None:
            if len(r['features'])!=len(cf.NAMES) or r['feature_asof_ms']!=r['locked_at_ms']:raise ValueError('Candidate feature contract/clock differs')
        if r['available_at_ms'] is not None and not r['available_at_ms']<cutoff:raise ValueError('Future candidate label')
    snapshot=dict(schema=1,kind='V215_CANDIDATE_SNAPSHOT_V1',feature_contract=cf.CONTRACT,feature_names=list(cf.NAMES),
        origin=origin,policy=policy,asof_ms=cutoff,native_records=records,native_dataset_sha256=source_digest,
        calendar_days=days,rows=rows,receipt=receipt,retrospective_research=True,native_forward_predictions=0)
    snapshot['payload_sha256']=hashlib.sha256(canonical(snapshot)).hexdigest()
    verify(snapshot)
    return snapshot


def verify(snapshot):
    value=dict(snapshot);digest=value.pop('payload_sha256',None)
    if digest!=hashlib.sha256(canonical(value)).hexdigest():raise ValueError('Candidate snapshot checksum differs')
    if (snapshot['kind']!='V215_CANDIDATE_SNAPSHOT_V1' or snapshot['feature_contract']!=cf.CONTRACT or
        snapshot['feature_names']!=list(cf.NAMES) or snapshot['origin'] not in ('LIVE_MT4','BACKTEST_MT4') or
        snapshot['policy']['horizon'] not in (1,2,3) or snapshot['native_forward_predictions']!=0):raise ValueError('Unsupported candidate snapshot')
    for row in snapshot['rows']:
        if row['direction'] not in (-1,1) or row['setup'] not in (1,2,3):raise ValueError('Invalid candidate identity')
        features=row['features']
        if features is not None and (len(features)!=len(cf.NAMES) or not all(math.isfinite(v) and abs(v)<1e6 for v in features)
            or row['feature_asof_ms']!=row['locked_at_ms'] or row['locked_at_ms'] is None
            or not row['analysis_start']*1000<=row['locked_at_ms']<=(row['entry_target']-31)*1000):raise ValueError('Invalid causal candidate features')
        status=row['quality_status'];available=row['available_at_ms'];signed=row['signed_points']
        if status not in ('PENDING','UNAVAILABLE','FAVORABLE','ADVERSE','TIE'):raise ValueError('Unsupported candidate label')
        if status in ('FAVORABLE','ADVERSE','TIE'):
            if available is None or not row['expiry_target']*1000<=available<snapshot['asof_ms'] or signed is None:
                raise ValueError('Future or missing candidate label')
            if status!=('FAVORABLE' if signed>0 else 'ADVERSE' if signed<0 else 'TIE'):raise ValueError('Inconsistent candidate label')


def read(source,progress=None):
    source=Path(source)
    if source.is_dir() and (source/'data_origin.csv').is_file():return journals(source,progress)
    if source.is_dir():source=source/'prepared_history_v211.json.gz'
    return prepared(source)
