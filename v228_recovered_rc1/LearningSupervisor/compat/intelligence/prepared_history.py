"""Reusable, frozen, data-only history; local checksums do not authenticate a feed."""
import gzip
import hashlib
import json
import math
from pathlib import Path

from .demo_learning import LOGIC,atomic,fnv,points
from .signal_features import VERSION as LEGACY_FEATURE_VERSION,NAMES as LEGACY_NAMES
from .research_features import CONTRACT,NAMES
from .t1_features import CONTRACT as T1_CONTRACT,NAMES as T1_NAMES

KIND='V211_PREPARED_HISTORY_V2'
NAME='prepared_history_v211.json.gz'
MAX_JSON_BYTES=512*1024**2


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def validate(snapshot):
    if not isinstance(snapshot,dict) or snapshot.get('origin')!='BACKTEST_MT4':raise ValueError('Prepared history requires BACKTEST_MT4')
    p=snapshot['policy']
    if (p['schema']!=1 or p['logic']!=LOGIC or p['horizon'] not in (1,2,3) or
        p['enabled'] not in (0,1) or p['learning'] not in (0,1) or
        not all(isinstance(p[k],int) and 0<p[k]<=0xffffffff for k in ('config_hash','feed_hash','policy_hash'))):
        raise ValueError('Prepared policy differs from supported contract')
    if p['policy_hash']!=fnv('DEMO1|'+'|'.join(str(p[k]) for k in ('config_hash','feed_hash','horizon','enabled','learning'))):
        raise ValueError('Prepared policy fingerprint differs')
    if not isinstance(snapshot['asof'],int) or snapshot['asof']<=0 or not isinstance(snapshot['records'],int) or snapshot['records']<1:
        raise ValueError('Invalid prepared cutoff or record count')
    for key in ('references','papers','research')+ (('research_t1',) if 'research_t1' in snapshot else ()):
        if not isinstance(snapshot[key],list):raise ValueError('Invalid prepared rows')
        seen=set()
        for r in snapshot[key]:
            research=key in ('research','research_t1');t1=key=='research_t1'
            expected='BACKTEST_MT4_PRICE_RESEARCH' if research else 'BACKTEST_MT4_SIMULATED'
            if r['source']!=expected:raise ValueError('Prepared row source differs')
            identity=r['sample_id' if research else 'signal_id']
            if identity in seen:raise ValueError('Duplicate prepared row identity')
            seen.add(identity)
            target=r['entry_target'];start=r['analysis_start'];h=r['horizon']
            if h!=p['horizon'] or target!=start+300 or start%300 or r['expiry_target']!=target+h*300:
                raise ValueError('Prepared row target/horizon differs')
            if 'features' in r:
                n=len(T1_NAMES) if t1 else len(NAMES) if research else len(LEGACY_NAMES)
                if len(r['features'])!=n or not all(isinstance(v,(int,float)) and math.isfinite(v) and abs(v)<1e6 for v in r['features']):
                    raise ValueError('Invalid prepared features')
            if research:
                if r.get('cohort')!=(T1_CONTRACT if t1 else CONTRACT) or r.get('is_execution_trade') is not False or 'features' not in r:
                    raise ValueError('Prepared research/execution cohort mixed')
                if (r['feature_asof_ms']!=(r['locked_at_ms'] if t1 else start*1000) or not start*1000<=r['locked_at_ms']<=(target-31)*1000 or
                    not target*1000<=r['entry_observed_ms']<=(target+2)*1000):
                    raise ValueError('Prepared features or entry cross forecast window')
                if t1 and r.get('anchor_asof_ms')!=start*1000:raise ValueError('Prepared T+1 anchor time differs')
            statuses=('UP','DOWN','TIE','UNAVAILABLE','OPEN') if research else ('WIN','LOSS','TIE','UNAVAILABLE','OPEN','CANCELED','ENTRY_UNAVAILABLE','PENDING_ENTRY')
            if r['status'] not in statuses:raise ValueError('Invalid prepared label status')
            closed=r['status'] in (('UP','DOWN','TIE') if research else ('WIN','LOSS','TIE'))
            if closed:
                if not target*1000<=r['entry_observed_ms']<=(target+2)*1000:raise ValueError('Invalid prepared entry window')
                due=r['expiry_target']*1000
                if not due<=r['exit_observed_ms']<=due+2000 or r['available_at_ms']!=r['exit_observed_ms']+1000:
                    raise ValueError('Invalid prepared outcome window')
                move=points(r['exit_bid'])-points(r['entry_bid'])
                signed=move if research else r['direction']*move
                label=('UP' if move>0 else 'DOWN' if move<0 else 'TIE') if research else ('WIN' if signed>0 else 'LOSS' if signed<0 else 'TIE')
                if label!=r['status'] or signed!=r['signed_points']:raise ValueError('Prepared prices disagree with label')
    base={r['sample_id']:r for r in snapshot['research']}
    for r in snapshot.get('research_t1',[]):
        original=base.get(r['sample_id'])
        if original is None or r['features'][:len(NAMES)]!=original['features']:
            raise ValueError('Prepared T+1 base features differ')
        for field in ('analysis_start','entry_target','expiry_target','horizon','locked_at_ms','status','entry_bid','exit_bid','available_at_ms'):
            if r[field]!=original[field]:raise ValueError('Prepared T+1 label identity differs')
        elapsed,last,age=(r['features'][T1_NAMES.index(k)] for k in ('lock_elapsed_fraction','last_observed_fraction','quote_age_seconds'))
        expected=(r['locked_at_ms']-r['analysis_start']*1000)/300000
        if not 0<=last<=elapsed<=1 or age<0 or abs(elapsed-expected)>1e-9 or abs((elapsed-last)*300-age)>1e-7:
            raise ValueError('Prepared T+1 observation clock differs')
    seen=set()
    for r in snapshot.get('execution_traces',[]):
        start=r['analysis_start']
        if start in seen or start%300 or r['target_time']!=start+300 or r['detail_source']!='VERIFIED_NATIVE_EVENTS':
            raise ValueError('Invalid prepared execution trace identity')
        seen.add(start)
        if r['execution_signal_observed'] and r['canceled_at_entry']:raise ValueError('Canceled execution trace cannot claim entry')
        cancel=r['first_cancel_observed_ms'];quote=r['cancel_last_quote_ms'];age=r['cancel_quote_age_ms']
        if cancel is not None:
            if cancel<start*1000 or (quote is not None and quote>cancel):raise ValueError('Invalid prepared cancellation clock')
            if quote and age!=cancel-quote:raise ValueError('Prepared cancellation gap differs')
        elif quote is not None or age is not None:raise ValueError('Prepared trace cannot invent cancellation timing')
    if not isinstance(snapshot.get('funnel'),dict):raise ValueError('Missing prepared data funnel')


def save(path,snapshot,digest):
    validate(snapshot)
    artifact=dict(schema=2,kind=KIND,logic=LOGIC,legacy_feature_version=LEGACY_FEATURE_VERSION,
        research_feature_contract=CONTRACT,t1_feature_contract=T1_CONTRACT,source_origin='BACKTEST_MT4',dataset_sha256=digest,
        snapshot=snapshot,trust='Local derived data with integrity checksum; preserve original sealed journals')
    artifact['payload_sha256']=hashlib.sha256(canonical(artifact)).hexdigest()
    raw=canonical(artifact)
    if len(raw)>MAX_JSON_BYTES:raise ValueError('Prepared history exceeds supported 512 MiB JSON limit')
    atomic(Path(path),gzip.compress(raw,compresslevel=6,mtime=0))


def load(path):
    with gzip.open(path,'rb') as stream:
        raw=stream.read(MAX_JSON_BYTES+1)
    if len(raw)>MAX_JSON_BYTES:raise ValueError('Prepared history exceeds supported 512 MiB JSON limit; use raw journals')
    try:artifact=json.loads(raw)
    except (ValueError,UnicodeDecodeError):raise ValueError('Invalid prepared history JSON') from None
    if not isinstance(artifact,dict):raise ValueError('Invalid prepared history object')
    digest=artifact.pop('payload_sha256',None)
    if digest!=hashlib.sha256(canonical(artifact)).hexdigest():raise ValueError('Prepared history checksum mismatch')
    legacy=artifact.get('schema')==1 and artifact.get('kind')=='V210_PREPARED_HISTORY_V1'
    current=artifact.get('schema')==2 and artifact.get('kind')==KIND and artifact.get('t1_feature_contract')==T1_CONTRACT
    if (not (legacy or current) or artifact.get('logic')!=LOGIC or
        artifact.get('legacy_feature_version')!=LEGACY_FEATURE_VERSION or artifact.get('research_feature_contract')!=CONTRACT or
        artifact.get('source_origin')!='BACKTEST_MT4'):
        raise ValueError('Unsupported prepared history contract')
    if legacy and ('research_t1' in artifact['snapshot'] or 'execution_traces' in artifact['snapshot']):
        raise ValueError('V210 cache cannot claim native T+1 or exact cancellation details')
    dataset=artifact['dataset_sha256']
    if len(dataset)!=64 or any(c not in '0123456789abcdef' for c in dataset):raise ValueError('Invalid prepared dataset digest')
    validate(artifact['snapshot'])
    return artifact['snapshot'],dataset
