"""Strict read-only CSV validation against a committed native ANCHOR record."""
import csv
import hashlib
import io
import math
import re
from .context.engine import validate_bar

def read_anchor(source,record,policy):
    event=record['event'];cur=record['state']['current'];start=event['analysisStart']
    if event['kind']!=1 or event['observedMs']<start*1000 or cur['anchor']['closeTime']!=start:
        raise ValueError('Native anchor clock differs')
    path=source/f'anchor_{start}.csv'
    if path.is_symlink() or not path.resolve().is_relative_to(source):raise ValueError('Anchor escaped source')
    raw=path.read_bytes()
    if len(raw)>32768 or not raw.endswith(b'\n'):raise ValueError('Incomplete/oversized anchor CSV')
    rows=list(csv.reader(io.StringIO(raw.decode('ascii'))))
    if len(rows)!=66 or len(rows[0])!=7:raise ValueError('Anchor CSV row count')
    h=rows[0]
    if (h[:3]!=['BO_ANCHOR','2',str(policy['logic'])] or not re.fullmatch(r'EURUSD[A-Za-z0-9_.-]{0,16}',h[3]) or
        h[4:]!=[str(start),str(policy['config_hash']),'64'] or rows[1]!=['time_broker','open','high','low','close','tick_volume']):
        raise ValueError('Anchor CSV identity differs')
    bars=[]
    for row in rows[2:]:
        if len(row)!=6:raise ValueError('Anchor CSV column count')
        b=dict(time=int(row[0]),open=float(row[1]),high=float(row[2]),low=float(row[3]),close=float(row[4]),ticks=int(row[5]))
        validate_bar(b)
        if b['time']+300>start or (bars and b['time']<=bars[-1]['time']):raise ValueError('Future/unordered anchor bar')
        bars.append(b)
    a=cur['anchor']
    for name,key in [('close','triggerClose'),('high','triggerHigh'),('low','triggerLow')]:
        if not math.isclose(bars[-1][name],a[key],rel_tol=0,abs_tol=1e-9):raise ValueError('Anchor/POD price differs')
    if bars[-1]['time']+300!=start:raise ValueError('Last closed anchor is stale')
    return bars,dict(file=path.name,sha256=hashlib.sha256(raw).hexdigest(),symbol=h[3],start=start)
