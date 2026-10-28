"""Read immutable manual-publication records; never activate or train a model."""
import csv,hashlib,io,json,re
from collections import Counter
from decimal import Decimal
from pathlib import Path
from .candidate_data import canonical
from .demo_learning import atomic,csv_bytes,points
from .native_ledger import iter_directory,event_paths

CONTRACT='V218_MANUAL_PUBLICATION_V1'
COLUMNS='schema kind logic config_hash feed_hash policy_hash signal_id lock_sequence direction target expiry horizon setup regime published_ms observed_ms bid result quote_session input_sequence alerts_enabled receipt deadline_ms checksum'.split()
TEXT={'bid','quote_session','receipt'}

def checksum(row):
    value=2166136261
    for b in '|'.join(row[k] for k in COLUMNS[:-1]).encode('ascii'):value=((value^b)*16777619)&0xffffffff
    return value


def record(path,policy):
    raw=path.read_bytes()
    if len(raw)>16384:raise ValueError('Manual record size limit')
    reader=csv.DictReader(io.StringIO(raw.decode('ascii')));rows=list(reader)
    if reader.fieldnames!=COLUMNS or len(rows)!=1 or None in rows[0]:raise ValueError('Invalid manual record layout')
    row=rows[0]
    if any(not re.fullmatch(r'-?\d+',v) for k,v in row.items() if k not in TEXT):raise ValueError('Invalid manual integer')
    if checksum(row)!=int(row['checksum']):raise ValueError('Manual checksum differs')
    if not re.fullmatch(r'\d+\.\d{10}',row['bid']) or not re.fullmatch(r'[0-9_-]{1,128}',row['quote_session']) or row['receipt']!='UNCONFIRMED':raise ValueError('Invalid manual data field')
    r={k:(v if k in TEXT else int(v)) for k,v in row.items()};r['bid_decimal']=Decimal(row['bid'])
    if r['schema']!=1 or r['logic']!=policy['logic'] or any(r[k]!=policy[k] for k in ('config_hash','feed_hash','policy_hash')):raise ValueError('Manual policy identity differs')
    if path.name!=f"manual_v218_{r['kind']}_{r['signal_id']}.csv" or r['kind'] not in range(1,6):raise ValueError('Manual filename/kind differs')
    if (r['signal_id']<=0 or r['lock_sequence']<=0 or r['direction'] not in (-1,1) or r['target']!=r['signal_id']+300 or
        r['horizon']!=policy['horizon'] or not 1<=r['horizon']<=3 or r['expiry']!=r['target']+r['horizon']*300 or
        not 1<=r['setup']<=3 or not 1<=r['regime']<=7 or not r['signal_id']*1000<=r['published_ms']<=r['deadline_ms']<=(r['target']-31)*1000 or
        r['observed_ms']<r['published_ms'] or r['bid_decimal']<0 or r['input_sequence']<0 or r['alerts_enabled'] not in (0,1)):
        raise ValueError('Manual clock/value differs')
    return r,dict(file=path.name,sha256=hashlib.sha256(raw).hexdigest())


def same(a,b):
    return all(a[k]==b[k] for k in ('signal_id','lock_sequence','direction','target','expiry','horizon','setup','regime','published_ms','deadline_ms','alerts_enabled'))


def replay_quotes(source,wanted):
    """Cross-check only referenced real quote rows, using complete CSV prefixes."""
    matched={};manifests=[];previous={};clocks={}
    remaining={(sid,seq) for sid,seqs in wanted.items() for seq in seqs}
    if not remaining:return matched,manifests
    for path in sorted(source.glob('input_*.csv')):
        raw=path.read_bytes()
        if raw and not raw.endswith(b'\n'):raw=raw[:raw.rfind(b'\n')+1]
        used=False
        for r in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
            sid=r['session']
            if sid not in wanted:continue
            seq=int(r['sequence']);now=int(r['time_ms_estimated'])
            if seq!=previous.get(sid,0)+1 or now<clocks.get(sid,0):raise ValueError('Manual replay sequence/clock differs')
            previous[sid]=seq;clocks[sid]=now;used=True
            if (sid,seq) in remaining:
                if r['event_type']!='TICK' or int(r['schema'])!=2 or int(r['logic_version'])!=2026101707 or int(r['shadow_mode'])!=1:
                    raise ValueError('Manual replay identity differs')
                matched[(sid,seq)]=r;remaining.remove((sid,seq))
            if not remaining:break
        if used:manifests.append(dict(file=path.name,complete_prefix_sha256=hashlib.sha256(raw).hexdigest()))
        if not remaining:break
    if remaining:raise ValueError('Manual referenced replay missing')
    return matched,manifests


def review(source,snapshot,output=None):
    source=Path(source);files=sorted(source.glob('manual_v218_*.csv')) if source.is_dir() else []
    if source.is_dir() and any(source.glob('manual_v218_*.csv.tmp')):raise ValueError('Incomplete manual temporary record')
    policy=snapshot['policy'];limit=snapshot['native_records'];all_rows={};manifest=[]
    for path in files:
        r,m=record(path,policy);manifest.append(m)
        if r['lock_sequence']>limit:continue # Writer may be ahead of the captured immutable native prefix.
        key=(r['signal_id'],r['kind'])
        if key in all_rows:raise ValueError('Duplicate manual record')
        all_rows[key]=r
    commits={sid:r for (sid,kind),r in all_rows.items() if kind==1}
    if any(sid not in commits for sid,_ in all_rows):raise ValueError('Orphan manual record')
    wanted={};quotes=[]
    for (sid,kind),r in all_rows.items():
        if kind not in (2,3):continue
        p=commits[sid];target=(p['target'] if kind==2 else p['expiry'])*1000
        if not same(p,r) or not ((r['result']==0 and r['bid_decimal']>0 and target<=r['observed_ms']<=target+2000) or
             (r['result']==9 and r['bid_decimal']==0 and r['observed_ms']>target+2000)):
            raise ValueError('Invalid manual boundary quote')
        if r['result']==0 and r['input_sequence']>0:wanted.setdefault(r['quote_session'],set()).add(r['input_sequence']);quotes.append(r)
    replay,replay_manifest=replay_quotes(source,wanted)
    for q in quotes:
        r=replay[(q['quote_session'],q['input_sequence'])]
        if int(r['time_ms_estimated'])!=q['observed_ms'] or points(r['bid'])!=points(q['bid_decimal']):
            raise ValueError('Manual boundary differs from replay price/clock')
        if Decimal(r['ask'])<Decimal(r['bid']):raise ValueError('Invalid replay spread')
    native={};canceled={};entries={}
    if commits:
        for r in iter_directory(source,paths=event_paths(source)[:limit],compact=True):
            e=r['event'];seq=r['state']['sequence']
            if e['kind']==3:native[seq]=r
            if e['kind']==4:canceled[e['analysisStart']]=e['reason']
            if e['kind']==5:entries[e['analysisStart']]=bool(e['signal'])
    export=[];counts=Counter();latest_ms=0
    for sid,p in sorted(commits.items()):
        n=native.get(p['lock_sequence'])
        if not n:raise ValueError('Manual LOCK reference absent')
        e=n['event'];cur=n['state']['current']
        if (e['analysisStart']!=sid or e['targetTime']!=p['target'] or e['lockedAction']!=p['direction'] or e['selectedHorizon']!=p['horizon'] or
            e['setup']!=p['setup'] or e['regime']!=p['regime'] or e['validation']!=2 or e['reason']!=0 or cur['canceled'] or
            e['observedMs']>p['published_ms'] or p['result']!=8 or p['observed_ms']!=p['published_ms'] or p['bid_decimal']<=0):raise ValueError('Manual publication differs from native LOCK')
        withdrawn=all_rows.get((sid,5))
        if withdrawn:
            if not same(p,withdrawn) or withdrawn['observed_ms']<=p['deadline_ms'] or withdrawn['result']!=8 or withdrawn['bid_decimal']!=0:raise ValueError('Invalid withheld publication')
            if any((sid,k) in all_rows for k in (2,3,4)):raise ValueError('Withheld publication has price outcomes')
            counts['WITHHELD']+=1;continue
        counts['COMMITTED']+=1;entry=all_rows.get((sid,2));exit=all_rows.get((sid,3));result=all_rows.get((sid,4))
        status='PENDING'
        if result:
            if entry is None or exit is None or not same(p,result) or result['bid_decimal']!=0 or result['observed_ms']<max(entry['observed_ms'],exit['observed_ms']):raise ValueError('Incomplete manual result')
            move=(exit['bid_decimal']-entry['bid_decimal'])*p['direction']
            expected=9 if entry['result']==9 or exit['result']==9 else 1 if move>0 else -1 if move<0 else 0
            if result['result']!=expected:raise ValueError('Manual result disagrees with prices')
            status={1:'WIN',-1:'LOSS',0:'TIE',9:'UNAVAILABLE'}[expected]
        counts[status]+=1
        latest_ms=max(latest_ms,max(r['observed_ms'] for (i,_),r in all_rows.items() if i==sid))
        export.append(dict(signal_id=sid,direction='CALL' if p['direction']==1 else 'PUT',hold_minutes=p['horizon']*5,m5_bars=p['horizon'],
            entry_broker_seconds=p['target'],expiry_broker_seconds=p['expiry'],published_ms=p['published_ms'],status=status,
            native_canceled=sid in canceled,native_cancel_reason=canceled.get(sid),native_signal_entry=entries.get(sid,False),
            notification_receipt='UNCONFIRMED',entry_bid=str(entry['bid_decimal']) if entry and entry['result']==0 else None,
            exit_bid=str(exit['bid_decimal']) if exit and exit['result']==0 else None))
    report=dict(schema=1,software_version='2.24',contract=CONTRACT,source_origin=snapshot['origin'],
        status='VERIFIED_LOCAL_BOOK' if files else 'NO_MANUAL_PUBLICATION_BOOK',native_prefix_records=limit,
        manual_asof_broker_ms=latest_ms,counts={k:counts[k] for k in ('COMMITTED','WIN','LOSS','TIE','UNAVAILABLE','PENDING','WITHHELD')},
        signals=export,record_manifest=manifest,replay_manifest=replay_manifest,
        native_canceled_after_publication=sum(r['native_canceled'] for r in export),
        native_entries=sum(r['native_signal_entry'] for r in export),notification_delivery_verified=False,manual_broker_fills_known=False,
        learning_active=False,activation_allowed=False,price_source='MT4_BID_MANUAL_SIGNAL',
        trust='Local checksum/native LOCK/referenced replay cross-check (price at legacy EURUSD 1e-5 resolution); not independent broker authentication. Input sequence0 uses native quote record only.',
        interpretation='Committed manual-signal simulation, including later native cancellations; not Olymp results or forecasts.')
    if output is not None:
        output=Path(output);output.mkdir(parents=True,exist_ok=True);atomic(output/'manual_signal_review.json',canonical(report))
        atomic(output/'manual_signals.csv',csv_bytes(list(export[0]) if export else ['signal_id','status'],export))
    return report
