"""Explain recorded cancellations; never relax guards or infer network latency."""
from collections import Counter
import calendar
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

from .execution_diagnostics import summarize
from .demo_learning import atomic, csv_bytes, LOGIC


def broker_seconds(value):
    """Parse a broker clock coordinate, never the worker's local timezone."""
    value = str(value)
    if re.fullmatch(r'[0-9]+', value):
        result = int(value)
    elif re.fullmatch(r'[0-9]{4}\.[0-9]{2}\.[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}', value):
        result = calendar.timegm(datetime.strptime(value, '%Y.%m.%d %H:%M:%S').timetuple())
    else:
        raise ValueError('Unsupported observer broker timestamp')
    if not 0 < result <= 253402300799:
        raise ValueError('Observer broker timestamp outside supported range')
    return result


def gap_class(trigger, tick_age, gap):
    if trigger == 'TICK' and tick_age == 0 and gap > 3000:
        return 'INCOMING_TICK_AFTER_OBSERVATION_GAP'
    if trigger in ('TIMER', 'TESTER_REPLAY_LOCK') and tick_age > 3000:
        return 'NO_RECENT_TICK_AT_CHECK'
    return 'REVIEW_REQUIRED'


def observer_bool(value):
    if value in ('1', 'true'):
        return True
    if value in ('0', 'false'):
        return False
    raise ValueError('Invalid observer boolean')


def observers(folder, origin='BACKTEST_MT4', native_facts=None):
    result = {}
    files = []
    if folder is None:
        return result, files
    for path in sorted(Path(folder).glob('execution_diagnostics_*.csv')):
        if path.stat().st_size > 128 * 1024 ** 2:
            raise ValueError('Observer CSV exceeds 128 MiB limit')
        raw = path.read_bytes()
        if len(raw) > 128 * 1024 ** 2:
            raise ValueError('Observer CSV exceeds 128 MiB limit')
        files.append(dict(name=path.name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        from io import StringIO
        verified_rows = 0
        for row in csv.DictReader(StringIO(raw.decode('utf-8-sig'))):
            if int(row['schema']) not in (1, 2, 3) or int(row['logic']) != LOGIC or row['origin'] != origin:
                raise ValueError('Observer must match journal origin and supported logic/schema')
            start = broker_seconds(row['analysis_start'])
            kind = int(row['event_kind'])
            observed, stored = int(row['observed_ms']), int(row['stored_quote_ms'])
            latest, age = int(row['latest_tick_ms']), int(row['latest_tick_age_ms'])
            if observed < start*1000 or stored > observed or latest > observed:
                raise ValueError('Observer contains a future tick or invalid event clock')
            expected_stored_age = observed-stored if stored > 0 else -1
            if int(row['stored_quote_age_ms']) != expected_stored_age or (latest and age != observed-latest):
                raise ValueError('Observer quote clock differs')
            if native_facts is not None:
                fact = native_facts.get(int(row['sequence']))
                if fact is None:
                    raise ValueError('Observer sequence not present in authoritative journal')
                expected = dict(analysis_start=start, event_kind=kind,
                    observed_ms=int(row['observed_ms']), stored_quote_ms=int(row['stored_quote_ms']),
                    reason=row['reason'], locked_direction=int(row['locked_direction']),
                    canceled=observer_bool(row['canceled']), signal=observer_bool(row['signal']))
                if fact != expected:
                    raise ValueError('Observer differs from authoritative sequence/event facts')
                verified_rows += 1
            if kind != 4 or row['reason'] != 'QUOTE_GAP':
                continue
            key = (start, int(row['observed_ms']))
            value = {k: int(row[k]) for k in ('stored_quote_age_ms', 'latest_tick_ms', 'latest_tick_age_ms', 'inter_tick_gap_ms')}
            value.update(event_trigger=row.get('event_trigger', 'UNKNOWN_V211_OBSERVER'), source_file=path.name,
                         stored_quote_ms=int(row['stored_quote_ms']))
            value.update(latest_bid=row.get('latest_bid', ''), latest_ask=row.get('latest_ask', ''))
            if value['latest_tick_ms'] > key[1] or value['stored_quote_ms'] > key[1]:
                raise ValueError('Observer contains a future tick')
            if value['stored_quote_age_ms'] != key[1] - value['stored_quote_ms']:
                raise ValueError('Observer stored quote clock differs')
            if value['latest_tick_ms'] and value['latest_tick_age_ms'] != key[1] - value['latest_tick_ms']:
                raise ValueError('Observer latest tick clock differs')
            expected_class = gap_class(value['event_trigger'], value['latest_tick_age_ms'], value['inter_tick_gap_ms'])
            if int(row['schema']) == 3 and row.get('gap_class') != expected_class:
                raise ValueError('Observer gap classification differs from recorded clocks')
            if int(row['schema']) == 3 and int(row['quote_fresh_seconds']) != 3:
                raise ValueError('Observer quote guard differs from inherited contract')
            if key in result:
                previous = dict(result[key]); previous.pop('source_file')
                current = dict(value); current.pop('source_file')
                if previous != current:
                    raise ValueError('Conflicting observer rows; choose one original Tester run')
            result[key] = value
        files[-1]['native_rows_verified'] = verified_rows
    return result, files


def review(snapshot, native_digest, observer_folder=None, *, native_facts=None):
    origin = snapshot.get('origin', 'BACKTEST_MT4')
    if origin not in ('BACKTEST_MT4', 'LIVE_MT4'):
        raise ValueError('Unsupported execution review origin')
    obs, files = observers(observer_folder, origin, native_facts)
    summary = summarize(snapshot)
    rows = []
    categories = Counter()
    for trace in snapshot.get('execution_traces', []):
        if not trace['published_at_lock']:
            continue
        cancel = trace['first_cancel_observed_ms']
        gap = trace['cancel_quote_age_ms']
        row = dict(analysis_start=trace['analysis_start'], setup=trace['setup'], target_time=trace['target_time'],
            first_cancel_observed_ms=cancel, cancel_after_lock=trace['cancel_after_lock'],
            cancel_minus_lock_ms=cancel-trace['lock_observed_ms'] if cancel is not None and trace['lock_observed_ms'] is not None else None,
            cancel_minus_entry_target_ms=cancel-trace['target_time']*1000 if cancel is not None else None,
            first_cancel_reason=trace['first_cancel_reason'], stored_quote_age_ms=gap,
            entry_reason=trace['entry_reason'], execution_signal_observed=trace['execution_signal_observed'],
            observer_matched=False, latest_tick_age_ms=None, inter_tick_gap_ms=None,
            latest_tick_ms=None, latest_bid=None, latest_ask=None, gap_class=None,
            event_trigger=None, classification='NO_RECORDED_CANCEL' if cancel is None else 'OTHER_CANCELLATION')
        if trace['first_cancel_reason'] == 'QUOTE_GAP':
            row['classification'] = 'STORED_QUOTE_AGE_ONLY'
            found = obs.get((trace['analysis_start'], cancel))
            if found:
                if found['stored_quote_age_ms'] != gap or found['stored_quote_ms'] != trace['cancel_last_quote_ms']:
                    raise ValueError('Observer does not match authoritative cancellation facts')
                row.update(observer_matched=True, latest_tick_age_ms=found['latest_tick_age_ms'],
                           latest_tick_ms=found['latest_tick_ms'], latest_bid=found['latest_bid'], latest_ask=found['latest_ask'],
                           inter_tick_gap_ms=found['inter_tick_gap_ms'], event_trigger=found['event_trigger'])
                if found['latest_tick_age_ms'] == 0 and found['inter_tick_gap_ms'] > 3000:
                    row['classification'] = 'FRESH_INCOMING_TICK_AFTER_OBSERVATION_GAP'
                elif found['event_trigger'] in ('TIMER', 'TESTER_REPLAY_LOCK') and found['latest_tick_age_ms'] > 3000:
                    row['classification'] = 'TIMER_WITHOUT_RECENT_TICK'
                else:
                    row['classification'] = 'OBSERVER_PRESENT_REVIEW_REQUIRED'
                row['gap_class'] = gap_class(found['event_trigger'], found['latest_tick_age_ms'], found['inter_tick_gap_ms'])
        categories[row['classification']] += 1
        rows.append(row)
    canceled=[r for r in rows if r['first_cancel_observed_ms'] is not None]
    boundary=dict(published=len(rows),canceled_after_lock=sum(r['cancel_after_lock'] for r in canceled),
        canceled_at_entry_target=sum(r['cancel_minus_entry_target_ms']==0 for r in canceled),
        canceled_before_entry_target=sum(r['cancel_minus_entry_target_ms']<0 for r in canceled),
        cancel_offset_target_ms=dict(Counter(str(r['cancel_minus_entry_target_ms']) for r in canceled)),
        examples=[dict(analysis_start=r['analysis_start'],target_time=r['target_time'],
            first_cancel_observed_ms=r['first_cancel_observed_ms'],stored_quote_age_ms=r['stored_quote_age_ms'],
            observer_matched=r['observer_matched'],classification=r['classification']) for r in canceled[:5]])
    report = dict(schema=3, status='REVIEWED' if 'execution_traces' in snapshot else 'REQUIRES_V211_CACHE_OR_RAW_JOURNALS',
        dataset_sha256=native_digest, source=origin, native_summary=summary,
        entry_boundary=boundary,
        classifications=dict(categories), matched_observer_rows=sum(r['observer_matched'] for r in rows),
        observer_files=files, observer_trust='Optional sidecar, cross-checked against native cancellation facts; not independent feed authentication',
        observer_sequence_verified=native_facts is not None,
        observer_native_rows_verified=sum(f['native_rows_verified'] for f in files),
        guard_seconds=3, guard_changed=False, network_latency_proven=False, automated_repair=False,
        explanation='Incoming tick age, stored prediction quote age and inter-tick gap are separate. A fresh arriving tick can cancel after an observation gap. Network latency is not established.',
        next_check='Review representative LOCK/CANCEL/ENTRY with Tester tick model and observer CSV. Do not loosen guards to create trades.')
    return report, rows


def write(snapshot, digest, output, observer_folder=None):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a fresh execution review output directory')
    report, rows = review(snapshot, digest, observer_folder)
    output.mkdir(parents=True, exist_ok=True)
    atomic(output/'execution_review.json', (json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+'\n').encode())
    atomic(output/'execution_review.csv', csv_bytes(sorted(rows[0]) if rows else ['status'], rows))
    return report
