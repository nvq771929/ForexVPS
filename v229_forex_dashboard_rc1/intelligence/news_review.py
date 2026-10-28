"""Export source coverage and every inclusion/exclusion decision without training."""
from collections import Counter
from pathlib import Path
import hashlib,json
from .economic_calendar import load,state
from .news_policy import load_policy,selection
from .candidate_data import canonical
from .demo_learning import atomic

def write(cache,output,now,entry=None,expiry=None,policy=None):
    cache=Path(cache);output=Path(output);output.mkdir(parents=True,exist_ok=True);policy=policy or load_policy()
    try:snapshot=load(cache)
    except (OSError,ValueError,KeyError,TypeError):snapshot=None
    rows=selection(snapshot,policy);entry=now if entry is None else entry;expiry=entry+300 if expiry is None else expiry
    report=dict(contract='V222_NEWS_SOURCE_REVIEW_V1',mode='OBSERVE_ONLY',native_decisions_changed=False,
        generated_utc=now,policy=policy,calendar_state=state(snapshot,now,entry,expiry,policy),
        source_event_count=snapshot.get('source_event_count') if snapshot else None,scope_event_count=len(rows),
        tracked_events=sum(r['tracked'] for r in rows),decision_counts=dict(Counter(r['reason'] for r in rows)),events=rows,
        provider=snapshot['provider'] if snapshot else 'FAIR_ECONOMY_PUBLIC_WEEKLY',
        received_utc=snapshot['received_utc'] if snapshot else None,expires_utc=snapshot['expires_utc'] if snapshot else None,
        raw_sha256=snapshot['raw_sha256'] if snapshot else None,raw_available=False,
        coverage_caveat='Returned weekly rows establish a date range, not independent proof of calendar completeness.')
    raw=None
    if snapshot:
        path=cache/('raw_'+snapshot['raw_sha256']+'.json')
        if path.is_file():
            raw=path.read_bytes()
            if len(raw)>2000000 or hashlib.sha256(raw).hexdigest()!=snapshot['raw_sha256']:raise ValueError('News raw body checksum differs')
            report['raw_available']=True
        atomic(output/'news_snapshot_v222.json',canonical(snapshot))
    else:(output/'news_snapshot_v222.json').unlink(missing_ok=True)
    if raw is not None:atomic(output/'news_raw_v222.json',raw)
    else:(output/'news_raw_v222.json').unlink(missing_ok=True)
    status=cache/'fetch_status.json'
    if status.is_file():
        data=json.loads(status.read_bytes());report['last_fetch_status']=data.get('status');report['last_fetch_attempt_utc']=data.get('attempt_utc')
    atomic(output/'news_source_review_v222.json',canonical(report));return report
