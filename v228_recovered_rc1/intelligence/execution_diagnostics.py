"""Read-only episode traces. A canceled opportunity never becomes an execution."""
from collections import Counter
from .research_data import REASONS


def trace(groups):
    rows=[]
    for start,records in sorted(groups.items()):
        locks=[r for r in records if r['event']['kind']==3]
        entries=[r for r in records if r['event']['kind']==5]
        lock=locks[0] if locks else None;entry=entries[0] if entries else None
        c=lock['state']['current'] if lock else None
        direction=c['candidate']['direction'] if c else next((r['event']['direction'] for r in records if r['event']['direction']),0)
        if not direction:continue
        e=lock['event'] if lock else None
        cancels=[r for r in records if r['event']['kind']==4 and r['state']['current']['analysisStart']==start and r['state']['current']['canceled']]
        first=min(cancels,key=lambda r:r['event']['observedMs']) if cancels else None
        ce=first['event'] if first else None;cs=first['state']['current'] if first else None
        ee=entry['event'] if entry else None;es=entry['state']['current'] if entry else None
        rows.append(dict(analysis_start=start,target_time=start+300,candidate_direction=direction,
            setup=c['candidate']['setup'] if c else (ee['setup'] if ee else 0),
            lock_observed_ms=e['observedMs'] if e else None,lock_reason=REASONS[e['reason']] if e else None,
            locked_direction=e['lockedDirection'] if e else 0,published_at_lock=bool(e and e['lockedAction']),
            lock_quote_age_ms=e['observedMs']-c['lastQuoteMs'] if e and c['lastQuoteMs'] else None,
            first_cancel_observed_ms=ce['observedMs'] if ce else None,
            first_cancel_reason=REASONS[ce['reason']] if ce else None,
            cancel_last_quote_ms=cs['lastQuoteMs'] if cs else None,
            cancel_quote_age_ms=ce['observedMs']-cs['lastQuoteMs'] if cs and cs['lastQuoteMs'] else None,
            cancel_after_lock=bool(ce and e and ce['observedMs']>=e['observedMs']),
            entry_observed_ms=ee['observedMs'] if ee else None,entry_reason=REASONS[ee['reason']] if ee else None,
            canceled_at_entry=bool(es and es['canceled']),execution_signal_observed=bool(ee and ee['signal']),
            entry_stored_quote_age_ms=ee['observedMs']-es['lastQuoteMs'] if ee and es['lastQuoteMs'] else None,
            detail_source='VERIFIED_NATIVE_EVENTS',
            note='Stored quote age at cancellation is not proof that incoming tick price was stale; inspect observation gaps separately.'))
    return rows


def summarize(snapshot):
    rows=snapshot.get('execution_traces')
    if rows is not None:
        published=[r for r in rows if r['published_at_lock']]
        gaps=[r['cancel_quote_age_ms']/1000 for r in published if r['first_cancel_reason']=='QUOTE_GAP' and r['cancel_quote_age_ms'] is not None]
        return dict(source='VERIFIED_NATIVE_EVENTS',opportunities=len(rows),published_at_lock=len(published),
            entry_reason_for_published=dict(Counter(r['entry_reason'] or 'ENTRY_NOT_RECORDED' for r in published)),
            first_cancel_reason_for_published=dict(Counter(r['first_cancel_reason'] or 'NO_RECORDED_CANCEL' for r in published)),
            recorded_quote_gap_seconds=dict(Counter(str(v) for v in gaps)),
            exact_cancel_timing_available=sum(r['first_cancel_observed_ms'] is not None for r in published),
            execution_entries=sum(r['execution_signal_observed'] for r in rows))
    # V210 cache can link reasons, but cannot reconstruct individual tick gaps.
    by_start={r['analysis_start']:r for r in snapshot['research']};papers=snapshot['papers']
    linked=[by_start.get(p['analysis_start']) for p in papers if p.get('published')]
    return dict(source='V210_CACHE_REASON_LINK_ONLY',published_at_lock=len(linked),
        entry_reason_for_published=dict(Counter(r['entry_reason'] if r else 'UNAVAILABLE' for r in linked)),
        recorded_quote_gap_seconds={},exact_cancel_timing_available=0,
        execution_entries=sum(bool(r.get('execution_signal_observed')) for r in snapshot['research']),
        missing_detail='Raw native journals are required for cancel timestamps and pre-cancel quote age; no gap is fabricated.')
