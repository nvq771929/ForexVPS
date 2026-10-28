"""Refresh the diagnostic funnel every cycle, independent of immutable model runs."""
from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
from statistics import median
from pathlib import Path
from .candidate_data import canonical
from .native_ledger import iter_directory,event_paths
from .session_observation import observations
from .demo_learning import atomic,csv_bytes,wilson
from .research_data import REASONS
from .market_sessions import TIMEZONE_DATABASE
from .slot_review import review as slot_review


def metrics(rows,trade=False):
    if trade:rows=[r for r in rows if r['execution_signal_observed']]
    counts=Counter(r['quality_status'] for r in rows)
    w,l,t=(counts[x] for x in ('FAVORABLE','ADVERSE','TIE'));n=w+l;lo,hi=wilson(w,n)
    return dict(samples=len(rows),favorable=w,adverse=l,ties=t,unavailable=counts['UNAVAILABLE'],pending=counts['PENDING'],
        decisive=n,win_rate=w/n if n else None,wilson_lower=lo,wilson_upper=hi,
        assumed_roi=(.82*w-l)/(w+l+t) if w+l+t else None,state='DESCRIPTIVE_ONLY' if n>=100 else 'COLLECTING',
        interpretation='MT4 simulated signal trades' if trade else 'Directional price proxy, including canceled candidates')


def anchor_diagnostics(rows):
    reasons=Counter();values=[]
    for e,a in rows:
        atr=a['volatility']['atr']/.0001
        if a['available']:values.append(atr)
        detail=REASONS[e['reason']]
        if e['reason']==7:
            detail='ATR_BELOW_3_PIPS' if atr<3 else 'ATR_ABOVE_30_PIPS' if atr>30 else 'TRIGGER_RANGE_OVER_2_5_ZONE_ATR' if a['candle']['range']>2.5*a['volatility']['zoneATR'] else 'UNRESOLVED_VOLATILITY_REASON'
        reasons[detail]+=1
    return dict(anchors=len(rows),first_rejection_counts=dict(reasons),atr_min_pips=min(values) if values else None,
        atr_median_pips=median(values) if values else None,atr_max_pips=max(values) if values else None,
        atr_eligibility_only={str(t):sum(t<=v<=30 for v in values) for t in (2.,2.5,3.)},
        interpretation='ATR-only counts overlap and do not establish setups, trade signals, wins or a recommended threshold; live threshold remains 3 pips.')


def write(source,snapshot,rules,output,model_run,now_utc=None):
    import time
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    contexts,audit=observations(source,snapshot);anchors=Counter();reasons=defaultdict(Counter)
    anchor_regimes=defaultdict(Counter);anchor_atrs=defaultdict(list);news_groups=defaultdict(list);daily=defaultdict(list);session_details=defaultdict(list)
    groups=defaultdict(list);candidates={r['analysis_start']:r for r in snapshot['rows']};candidate_context={};event_counts=Counter()
    paths=event_paths(source)[:snapshot['native_records']] if Path(source).is_dir() else []
    for record in iter_directory(source,paths=paths,compact=True) if paths else []:
        e=record['event'];seq=record['state']['sequence'];event_counts[e['kind']]+=1
        context=contexts.get(seq,dict(session='SESSION_UNKNOWN',news_status='NEWS_UNKNOWN'))
        if e['kind']==1:
            session=context['session'];anchor=record['state']['current']['anchor']
            anchors[session]+=1;reasons[session][REASONS[e['reason']]]+=1;anchor_regimes[session][str(anchor['regime'])]+=1
            if anchor['available']:anchor_atrs[session].append(anchor['volatility']['atr']/.0001)
            utc=context.get('utc_seconds');day=datetime.fromtimestamp(utc,timezone(timedelta(hours=7))).date().isoformat() if utc is not None else 'DAY_UNKNOWN'
            daily[(day,session)].append((e,anchor));session_details[session].append((e,anchor))
        if e['kind']==3 and e['analysisStart'] in candidates:candidate_context[e['analysisStart']]=context
    export=[]
    for row in snapshot['rows']:
        context=candidate_context.get(row['analysis_start'],dict(session='SESSION_UNKNOWN',news_status='NEWS_UNKNOWN'))
        key=(context['session'],row['regime'],row['setup'],snapshot['policy']['horizon'])
        groups[key].append(row)
        news_groups[(context['session'],context['news_status'])].append(row)
        export.append(dict(sample_id=row['sample_id'],feature_asof_ms=row['feature_asof_ms'],session=context['session'],
            entry_session=context.get('entry_session','SESSION_UNKNOWN'),expiry_session=context.get('expiry_session','SESSION_UNKNOWN'),
            crosses_session_boundary=context.get('crosses_session_boundary'),news_status=context['news_status'],
            ready_at_lock=row['ready_at_lock'],quality_status=row['quality_status'],execution_signal_observed=row['execution_signal_observed']))
    summaries=[]
    for (session,regime,setup,horizon),rr in sorted(groups.items(),key=lambda p:str(p[0])):
        ready=[r for r in rr if r['ready_at_lock']]
        summaries.append(dict(session=session,regime=regime,setup=setup,horizon=horizon,candidates=len(rr),ready=len(ready),
            quality=metrics(ready),trades=metrics(ready,True)))
    report=dict(schema=1,software_version='2.23',contract='V216_LIVE_SESSION_REVIEW_V1',
        native_records=snapshot['native_records'],native_asof_broker_ms=snapshot['asof_ms'],generated_utc=int(time.time() if now_utc is None else now_utc),
        snapshot_sha256=snapshot['payload_sha256'],timezone_database=TIMEZONE_DATABASE,source_origin=snapshot['origin'],anchors=sum(anchors.values()),
        locks=event_counts[3],registered_candidates=len(snapshot['rows']),ready_at_lock=sum(r['ready_at_lock'] for r in snapshot['rows']),
        opportunities_by_anchor_session={key:dict(anchors=value,reasons=dict(reasons[key]),regimes=dict(anchor_regimes[key]),
            atr_pips_min=min(anchor_atrs[key]) if anchor_atrs[key] else None,atr_pips_max=max(anchor_atrs[key]) if anchor_atrs[key] else None) for key,value in anchors.items()},
        candidates_by_lock_session=summaries,clock_audit=audit,
        candidates_by_session_news=[dict(session=s,news_status=n,candidates=len(rr),
            quality=metrics([r for r in rr if r['ready_at_lock']]),trades=metrics([r for r in rr if r['ready_at_lock']],True))
            for (s,n),rr in sorted(news_groups.items())],
        news_context_counts=dict(Counter(r['news_status'] for r in contexts.values())),
        model_run=model_run,model_report_is_immutable=True,current_diagnostics_refreshed=True,
        activation_allowed=False,native_decisions_changed=False,forecast=False,
        assumptions='Sessions are research conventions. Unknown historical UTC remains unknown. Payout assumed 82%; no Olymp fill evidence.')
    report['daily_session_diagnostics']=[dict(day_vn=day,session=session,**anchor_diagnostics(rr)) for (day,session),rr in sorted(daily.items())]
    report['session_filter_diagnostics']={k:anchor_diagnostics(v) for k,v in session_details.items()}
    slots=slot_review(source,snapshot);report['analysis_slots']=dict(status=slots['status'],rows=slots['rows'],final_counts=slots['final_counts'])
    atomic(output/'slot_diagnostics_v222.json',canonical(slots))
    atomic(output/'live_session_review.json',canonical(report));atomic(output/'rule_diagnostics_current.json',canonical(rules))
    atomic(output/'session_observer_audit.json',canonical(audit))
    if export:atomic(output/'session_candidates.csv',csv_bytes(list(export[0]),export))
    return report
