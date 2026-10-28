import csv
import hashlib
import io
import re
from pathlib import Path
from . import CONTRACT,FEATURE_CONTRACT
from intelligence.native_ledger import decode_bytes
from intelligence.demo_learning import read_policy
from intelligence.origin import read_origin
from supervisor.store import canonical,digest

REQUEST='schema contract session sequence config_hash feed_hash policy_hash transport_policy_hash analysis_start target expiry horizon direction setup regime validation observed_ms deadline_ms snapshot_checksum checksum'.split()
REPLY='schema contract session sequence config_hash feed_hash policy_hash transport_policy_hash analysis_start target expiry horizon direction setup regime requested_ms deadline_ms snapshot_checksum decision probability_ppm model_id trained_cutoff_utc_ms model_created_utc_ms response_utc_ms qualification_cutoff_utc_ms validated checksum'.split()

def fnv(text):
    value=2166136261
    for b in text.encode('ascii'):value=((value^b)*16777619)&0xffffffff
    return value

def row_bytes(names,row):
    row={k:str(row[k]) for k in names if k!='checksum'}
    row['checksum']=str(fnv('|'.join(row[k] for k in names[:-1])))
    buffer=io.StringIO(newline='');writer=csv.DictWriter(buffer,names,lineterminator='\r\n');writer.writeheader();writer.writerow(row)
    return buffer.getvalue().encode('ascii')

def read_row(path,names):
    raw=Path(path).read_bytes()
    if len(raw)>16384 or not raw.endswith(b'\n'):raise ValueError('Incomplete/oversized dialogue CSV')
    r=csv.DictReader(io.StringIO(raw.decode('ascii')));rows=list(r)
    if r.fieldnames!=names or len(rows)!=1 or None in rows[0]:raise ValueError('Dialogue CSV layout differs')
    row=rows[0]
    if str(fnv('|'.join(row[k] for k in names[:-1])))!=row['checksum']:raise ValueError('Dialogue checksum differs')
    for k,v in row.items():
        if k not in ('contract','session','model_id') and not re.fullmatch(r'-?\d+',v):raise ValueError('Invalid dialogue integer')
    if row['contract']!=CONTRACT or row['schema']!='1' or not re.fullmatch(r'[0-9_-]{1,128}',row['session']):
        raise ValueError('Dialogue identity differs')
    return {k:v if k in ('contract','session','model_id') else int(v) for k,v in row.items()},raw

def read_request(path):
    path=Path(path);row,raw=read_row(path,REQUEST)
    if path.name!=f"request_{row['sequence']:012d}.csv" or row['session']!=path.parent.name:raise ValueError('Request path differs')
    source=path.parent.parent.parent
    policy=read_policy(source);origin=read_origin(source,policy)
    if any(row[k]!=policy[k] for k in ('config_hash','feed_hash','policy_hash','horizon')):raise ValueError('Request native policy differs')
    with (path.parent/'policy.csv').open(encoding='ascii',newline='') as f:
        transport=list(csv.DictReader(f))
    if len(transport)!=1:raise ValueError('Dialogue session policy missing')
    t=transport[0]
    if (t['schema']!='1' or t['contract']!=CONTRACT or t['session']!=row['session'] or t['enabled']!='1' or
        int(t['transport_policy_hash'])!=row['transport_policy_hash'] or
        fnv('PRELOCK1|1|'+t['affects']+'|'+t['interval']+'|'+t['max_age']+'|'+t['reserve'])!=row['transport_policy_hash']):
        raise ValueError('Dialogue session policy differs')
    if (int(t['affects']) not in (0,1) or not 10<=int(t['interval'])<=60 or not 5<=int(t['max_age'])<=60 or not 3<=int(t['reserve'])<=15):
        raise ValueError('Dialogue session settings invalid')
    if (row['analysis_start']<=0 or row['analysis_start']%300 or row['target']!=row['analysis_start']+300 or
        row['expiry']!=row['target']+row['horizon']*300 or row['direction'] not in (-1,1) or
        row['setup'] not in (1,2,3) or row['regime'] not in range(8) or
        not row['analysis_start']*1000+15000<row['observed_ms']<row['deadline_ms']<row['target']*1000-31000):
        raise ValueError('Request causal clock/value differs')
    binary=path.parent/f"event_{row['sequence']:012d}.bin";blob=binary.read_bytes()
    if int.from_bytes(blob[-4:],'little')!=row['snapshot_checksum']:raise ValueError('Request snapshot checksum differs')
    snapshot=decode_bytes(blob,row['sequence']);s,e=snapshot['state'],snapshot['event'];c=s['current']
    if (e['kind']!=2 or e['analysisStart']!=row['analysis_start'] or e['targetTime']!=row['target'] or
        e['observedMs']!=row['observed_ms'] or c['locked'] or c['entered'] or c['canceled'] or
        c['candidate']['direction']!=row['direction'] or c['candidate']['setup']!=row['setup'] or
        c['anchor']['regime']!=row['regime'] or c['validation']!=row['validation'] or
        s['configHash']!=row['config_hash'] or s['feedHash']!=row['feed_hash']):raise ValueError('Request snapshot identity differs')
    # Session configuration supplies the original native lock lead; never assume UTC or 30 seconds.
    with (source/f"session_{row['session']}.csv").open(encoding='ascii') as f: native=list(csv.DictReader(f))
    if len(native)!=1:raise ValueError('Native session configuration missing')
    if any(int(native[0][k])!=row[k] for k in ('config_hash','feed_hash')):raise ValueError('Native session policy differs')
    lead=int(native[0]['lock_lead_seconds'])+int(native[0]['lock_guard_seconds'])
    due=row['target']*1000-lead*1000
    if not (row['observed_ms']<due-int(t['reserve'])*1000 and
            row['deadline_ms']==min(due-int(t['reserve'])*1000,row['observed_ms']+int(t['max_age'])*1000)):
        raise ValueError('Request deadline differs from native lock')
    return dict(meta=row,snapshot=snapshot,policy=policy,transport=t,origin=origin,source=str(source.resolve()),
        request_sha256=hashlib.sha256(raw).hexdigest(),snapshot_sha256=hashlib.sha256(blob).hexdigest())

def read_final(path):
    raw=Path(path).read_bytes()
    if len(raw)>16384 or not raw.endswith(b'\n'):raise ValueError('Incomplete final receipt')
    names='schema analysis_start final_ms request_sequence request_ms received_ms native_action final_action status model_id checksum'.split()
    reader=csv.DictReader(io.StringIO(raw.decode('ascii')));rows=list(reader)
    if reader.fieldnames!=names or len(rows)!=1 or None in rows[0]:raise ValueError('Final receipt layout differs')
    row=rows[0]
    if row['schema']!='1' or str(fnv('|'.join(row[k] for k in names[:-1])))!=row['checksum']:raise ValueError('Final receipt checksum differs')
    return row,hashlib.sha256(raw).hexdigest()
