"""Dedicated Forex calendar publication; Binary observers and journals stay untouched.

Public calendar vintages establish scheduled-event coverage, not complete news coverage.
No broker API. Current weekly news must never be used as historical Tester news.
"""
import csv
import io
from pathlib import Path
from .economic_calendar import load
from .news_policy import load_policy, selection
from .demo_learning import atomic

CONTRACT='V222_FOREX_NEWS_V1'
COLUMNS=('contract','kind','received','expires','coverage_from','coverage_to','snapshot',
         'event_id','event_utc','currency','impact','tracking','label','uncertain','count','fnv')

def fnv(text):
    value=2166136261
    for byte in text.encode('ascii'): value=((value^byte)*16777619)&0xffffffff
    return value

def publish(cache,files_root,now,policy=None):
    """Atomic replacement, preserving original receive time even after failed refresh."""
    snapshot=load(cache)
    if snapshot is None: raise ValueError('No verified calendar snapshot')
    rows=[e for e in selection(snapshot,policy or load_policy()) if e['tracked']]
    if len(rows)>512: raise ValueError('Forex news capacity exceeded')
    common=[str(snapshot[k]) for k in ('received_utc','expires_utc','coverage_from_utc','coverage_to_utc','payload_sha256')]
    records=[[CONTRACT,'META',*common,'NONE','0','NONE','NONE','NONE','READY','0',str(len(rows))]]
    for e in rows:
        records.append([CONTRACT,'NEWS',*common,e['event_id'],str(e['scheduled_utc']),e['currency'],e['impact'],
                        e['reason'],e['label'],str(int(e['time_uncertain'])),str(len(rows))])
    out=io.StringIO(newline='');writer=csv.writer(out,lineterminator='\r\n');writer.writerow(COLUMNS)
    for row in records:
        if any('|' in cell or not cell.isascii() for cell in row): raise ValueError('Invalid news cell')
        writer.writerow([*row,fnv('|'.join(row))])
    path=Path(files_root)/'FX_V222'/'news_calendar.csv'
    path.parent.mkdir(parents=True,exist_ok=True)
    atomic(path,out.getvalue().encode('ascii'))
    return dict(path=str(path),events=len(rows),received_utc=snapshot['received_utc'],
                status='FRESH' if snapshot['received_utc']<=now<=snapshot['expires_utc'] else 'STALE',
                snapshot=snapshot['payload_sha256'])
