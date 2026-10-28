"""Read V226 archived closed-M5 packets. Never deserialize native checkpoint state.

Packet metadata is 19 int64 fields and bars are qddddq; FNV verifies bytes before
use. A checkpoint is terminal-layout-specific and is never a model/data format.
"""
import hashlib
import struct
from pathlib import Path
from .price_behavior import valid_bar

META=('engine','origin','offset','config','feed','policy','instance','symbol','first','count','previousHash',
      'availableMs','seed','requested','received','error','kind','terminal','streamHash')
IDENTITY=('engine','origin','offset','config','feed','policy','instance','symbol','requested','terminal')
HEADER=struct.Struct('<4i');METADATA=struct.Struct('<19q');BAR=struct.Struct('<qddddq')
def fnv(blob):
    n=2166136261
    for x in blob:n=((n^x)*16777619)&0xffffffff
    return n

def read_packet(path):
    path=Path(path);raw=path.read_bytes()
    if len(raw)<HEADER.size+METADATA.size+BAR.size+4:raise ValueError('Packet truncated')
    if HEADER.unpack_from(raw)!=(1163087921,1,METADATA.size,BAR.size):raise ValueError('Packet layout/version')
    checksum=struct.unpack_from('<I',raw,len(raw)-4)[0]
    if fnv(raw[:-4])!=checksum:raise ValueError('Packet FNV')
    m=dict(zip(META,METADATA.unpack_from(raw,HEADER.size)))
    if m['engine']!=2026102401 or m['origin'] not in (1,2) or m['kind'] not in (1,2) or not 0<m['count']<=4800 or m['first']<=0:raise ValueError('Packet metadata')
    if len(raw)!=HEADER.size+METADATA.size+m['count']*BAR.size+4:raise ValueError('Packet size')
    if not -720<=m['offset']<=840 or m['offset']%5:raise ValueError('Packet clock')
    if path.name!=f"embedded_packet_v226_{m['first']+m['count']-1:012d}.bin":raise ValueError('Packet filename/sequence')
    bars=[]
    for i in range(m['count']):
        values=BAR.unpack_from(raw,HEADER.size+METADATA.size+i*BAR.size)
        b=dict(zip(('time','open','high','low','close','ticks'),values));valid_bar(b)
        if (bars and b['time']<=bars[-1]['time']) or (b['time']+300)*1000>m['availableMs']-m['offset']*60000:raise ValueError('Packet future/nonmonotonic bar')
        bars.append(b)
    if m['first']==1 and m['seed']!=bars[0]['time']:raise ValueError('Packet seed')
    return m,bars,checksum,dict(file=path.name,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))

def read_stream(root):
    records=[read_packet(p) for p in Path(root).glob('*.bin')]
    records.sort(key=lambda x:x[0]['first']);identity=None;previous=0;count=0;last=0;out=[];receipts=[]
    for m,bars,checksum,receipt in records:
        current=tuple(m[k] for k in IDENTITY)
        if identity is None:identity=current
        if current!=identity or m['first']!=count+1 or m['previousHash']!=previous:raise ValueError('Packet lineage/sequence gap')
        if last and bars[0]['time']<=last:raise ValueError('Packet stream nonmonotonic')
        out.extend(dict(bar=b,available_broker_ms=m['availableMs'],kind=m['kind']) for b in bars)
        count+=len(bars);last=bars[-1]['time'];previous=checksum;receipts.append(receipt)
    if not records:raise ValueError('No input packets')
    return dict(identity=dict(zip(IDENTITY,identity)),count=count,last_hash=previous,observations=out,receipts=receipts)
