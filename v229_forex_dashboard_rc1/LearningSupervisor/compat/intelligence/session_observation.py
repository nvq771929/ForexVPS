"""Read causal clock observations and publish an observation-only local schedule."""
import csv,hashlib,io,time
from pathlib import Path
from .native_ledger import iter_directory,event_paths
from .candidate_data import canonical
from .demo_learning import atomic,csv_bytes
from .market_sessions import classify,windows,episode,CONTRACT
from .economic_calendar import load as load_calendar,label,state as news_state
from .news_policy import selection,load_policy,CONTRACT as NEWS_POLICY_CONTRACT

BRIDGE_COLUMNS=['schema','config','feed','policy','horizon','created','expires','kind','start','end','label',
    'news_received','news_expires','coverage_from','coverage_to','snapshot_id']

BRIDGE_V222_COLUMNS=BRIDGE_COLUMNS+['event_utc','event_id','currency','impact','tracking_reason','provider','news_policy','scope_count','tracked_count']

def publish(source,cache,now=None,policy=None):
    from .demo_learning import read_policy
    from .origin import read_origin
    source=Path(source);p=read_policy(source)
    if read_origin(source,p)!='LIVE_MT4':raise ValueError('Observation schedule can publish only to LIVE_MT4')
    now=int(time.time() if now is None else now);policy=policy or load_policy()
    try:news=load_calendar(cache)
    except (ValueError,OSError,KeyError,TypeError):news=None
    sid=news['raw_sha256'] if news else 'NO_NEWS'
    selected=selection(news,policy);tracked=[e for e in selected if e['tracked']]
    base=dict(schema=2,config=p['config_hash'],feed=p['feed_hash'],policy=p['policy_hash'],horizon=p['horizon'],
        created=now,expires=now+900,start=0,end=0,news_received=news['received_utc'] if news else 0,
        news_expires=news['expires_utc'] if news else 0,coverage_from=news['coverage_from_utc'] if news else 0,
        coverage_to=news['coverage_to_utc'] if news else 0,snapshot_id=sid,
        event_utc=0,event_id='',currency='',impact='',tracking_reason='',provider=news['provider'] if news else 'FAIR_ECONOMY_PUBLIC_WEEKLY',
        news_policy=policy['policy_sha256'],scope_count=len(selected),tracked_count=len(tracked))
    uncertain=news and any(e['time_uncertain'] for e in tracked)
    meta='NEWS_UNKNOWN' if not news else 'NEWS_TIME_UNCERTAIN' if uncertain else 'NEWS_NO_RELEVANT_EVENTS' if not selected else 'NEWS_NO_TRACKED_EVENTS' if not tracked else 'AVAILABLE'
    rows=[dict(base,kind='META',label=meta)]
    for w in windows(now):rows.append(dict(base,kind='SESSION',start=w['start'],end=w['end'],label=w['name']))
    for e in tracked:
        if not e['time_uncertain']:
            rows.append(dict(base,kind='NEWS',start=e['window_start'],end=e['window_end'],label=label(e['title']),
                event_utc=e['scheduled_utc'],event_id=e['event_id'],currency=e['currency'],impact=e['provider_impact'],tracking_reason=e['reason']))
    if len(rows)>513:raise ValueError('Observation schedule exceeds native row limit')
    # CSV file is the only companion-written native bridge. BIN/session/policy remain untouched.
    atomic(source/'context_schedule_v216.csv',csv_bytes(BRIDGE_V222_COLUMNS,rows))
    return dict(published_utc=now,news_available=news is not None,news_status=news_state(news,now,now,now+300,policy)['status'],
        tracked_events=len(tracked),scope_events=len(selected),news_policy=policy['policy_sha256'],mode='OBSERVE_ONLY',source_id=sid)


def observations(source,snapshot):
    source=Path(source);files=sorted(source.glob('market_context_*.csv')) if source.is_dir() else []
    if not files:return {},dict(status='CLOCK_CONTEXT_UNAVAILABLE',rows=0,contract=CONTRACT)
    limit=snapshot['native_records'];native={r['state']['sequence']:r for r in iter_directory(source,paths=event_paths(source)[:limit],compact=True)}
    result={};manifests=[]
    for path in files:
        raw=path.read_bytes()
        if len(raw)>128*1024**2:raise ValueError('Context CSV exceeds size limit')
        if raw and not raw.endswith(b'\n'):raw=raw[:raw.rfind(b'\n')+1]
        manifests.append(dict(name=path.name,consumed_sha256=hashlib.sha256(raw).hexdigest()))
        for row in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
            seq=int(row['sequence'])
            if seq>limit:continue
            if seq in result:raise ValueError('Duplicate market context sequence')
            record=native.get(seq)
            if record is None:raise ValueError('Market context native sequence absent')
            e=record['event'];p=snapshot['policy']
            if row['mode']!='OBSERVE_ONLY':raise ValueError('Market context mode differs')
            schema=int(row['schema'])
            if schema not in (1,2) or int(row['logic'])!=p['logic'] or any(int(row[k])!=p[k] for k in ('config_hash','feed_hash','policy_hash','horizon')):
                raise ValueError('Market context identity differs')
            if any(int(row[k])!=e[n] for k,n in [('analysis_start','analysisStart'),('event_kind','kind'),('observed_ms','observedMs')]):raise ValueError('Market context event/clock differs')
            utc=None
            if row['clock_status']=='UTC_ESTIMATED_FROM_PC':
                if schema==2 and (int(row['clock_calibration_ttl_ms'])!=900000 or not 0<=int(row['clock_calibration_age_ms'])<=900000):
                    raise ValueError('Invalid clock calibration age/TTL')
                offset=int(row['offset_seconds']);utc_ms=int(row['utc_ms'])
                if abs(offset)>14*3600 or offset%900 or utc_ms!=e['observedMs']-offset*1000 or abs(utc_ms-int(row['utc_reference_seconds'])*1000)>5000:
                    raise ValueError('Invalid broker/UTC context mapping')
                utc=utc_ms/1000
            elif row['clock_status']!='CLOCK_UNKNOWN':raise ValueError('Unknown clock observation status')
            if row['news_status'] not in ('NEWS_UNKNOWN','NEWS_CLOCK_UNCERTAIN','NEWS_STALE','NEWS_TIME_UNCERTAIN','NEWS_RISK_WINDOW','NEWS_CLEAR','NEWS_NO_RELEVANT_EVENTS','NEWS_NO_TRACKED_EVENTS'):
                raise ValueError('Unknown news observation status')
            if row['news_status'] in ('NEWS_RISK_WINDOW','NEWS_CLEAR','NEWS_TIME_UNCERTAIN') and (utc is None or not 0<int(row['snapshot_created_utc'])<=utc):
                raise ValueError('News context unavailable at observation time')
            info=episode(utc,utc+(e['targetTime']*1000-e['observedMs'])/1000 if utc is not None else None,
                utc+((e['targetTime']+p['horizon']*300)*1000-e['observedMs'])/1000 if utc is not None else None)
            result[seq]=dict(info,utc_seconds=utc,clock_status=row['clock_status'],clock_schema=schema,
                clock_calibration_age_ms=int(row['clock_calibration_age_ms']) if schema==2 else None,native_session_label=row['session_label'],
                news_status=row['news_status'],news_event_id=row['news_event_id'],news_snapshot_id=row['snapshot_id'],
                context_created_utc=int(row['snapshot_created_utc']),mode='OBSERVE_ONLY')
    return result,dict(status='VERIFIED_EVENT_CLOCK_OBSERVER',rows=len(result),files=manifests,contract=CONTRACT,
        clock_trust='Broker/PC offset calibrated on ticks; schema2 bounded to 15 minutes monotonic with PC UTC cross-check. Not independent UTC authentication.',
        unavailable_rows=sum(r['utc_seconds'] is None for r in result.values()))
