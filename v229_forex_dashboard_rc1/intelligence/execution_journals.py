"""Read-only execution diagnosis from a stable raw journal; never fit a model."""
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

from .demo_learning import LOGIC, atomic, csv_bytes, read_policy
from .native_ledger import event_paths, iter_directory
from .origin import read_origin
from .research_data import REASONS
from .execution_diagnostics import trace
from .execution_review import review
from .progress import notify


def input_quality(source, origin, progress=None, cancellations=()):
    paths = sorted(source.glob('input_*.csv'))
    sessions, gaps, kinds = {}, Counter(), Counter()
    ticks = zero = rows = 0
    first = last = None
    files = []
    expected = defaultdict(list)
    for cancel in cancellations:
        if cancel.get('observer_matched') and cancel.get('event_trigger') == 'TICK':
            expected[cancel['first_cancel_observed_ms']].append(cancel)
    matched = set()
    for index, path in enumerate(paths, 1):
        before = path.stat()
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            def lines():
                for raw in stream:
                    digest.update(raw)
                    if not raw.endswith(b'\n'):
                        raise ValueError('Incomplete input row; stop EA and copy the journal first')
                    yield raw.decode('utf-8-sig')
            for row in csv.DictReader(lines()):
                if int(row['schema']) != 2 or int(row['logic_version']) != LOGIC or row['shadow_mode'] != '1':
                    raise ValueError('Replay input identity differs')
                sid, seq, now = row['session'], int(row['sequence']), int(row['time_ms_estimated'])
                previous = sessions.get(sid)
                if seq != (previous[0] + 1 if previous else 1) or now <= 0 or (previous and now < previous[1]):
                    raise ValueError('Replay input sequence/clock mismatch')
                tick_time = previous[2] if previous else None
                kind = row['event_type']
                if kind not in ('TICK', 'TIMER', 'PAUSE_ON', 'PAUSE_OFF'):
                    raise ValueError('Unknown replay input type')
                if kind == 'TICK':
                    # Live time_ms_estimated may include sub-second monotonic time.
                    server = int(row['server_time_seconds']) * 1000
                    if origin == 'BACKTEST_MT4' and now != server:
                        raise ValueError('Tester input clock differs from server timestamp')
                    bid, ask = float(row['bid']), float(row['ask'])
                    import math
                    if not math.isfinite(bid) or not math.isfinite(ask) or bid <= 0 or ask < bid:
                        raise ValueError('Invalid input quote')
                    if tick_time is not None:
                        gaps[now - tick_time] += 1
                    for cancel in expected.get(now, []):
                        if (cancel.get('latest_bid') and cancel.get('latest_ask') and
                            bid == float(cancel['latest_bid']) and ask == float(cancel['latest_ask']) and
                            tick_time is not None and now-tick_time == cancel['inter_tick_gap_ms']):
                            matched.add(cancel['analysis_start'])
                    tick_time = now
                    zero += bid == ask
                    ticks += 1
                sessions[sid] = (seq, now, tick_time)
                kinds[kind] += 1
                rows += 1
                first = now if first is None else min(first, now)
                last = now if last is None else max(last, now)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('Replay input changed; use a stopped, copied journal')
        files.append(dict(name=path.name, bytes=after.st_size, sha256=digest.hexdigest()))
        notify(progress, 'read', done=index, total=len(paths), unit='input CSV', detail=f'{rows:,} replay rows verified')
    expected_starts = {c['analysis_start'] for group in expected.values() for c in group}
    if paths and matched != expected_starts:
        raise ValueError('Incoming cancellation observer differs from replay tick price/gap')
    return dict(source_origin=origin, input_files=files, input_rows=rows, tick_rows=ticks,
        incoming_cancellations_expected=len(expected_starts), incoming_cancellations_matched_to_input=len(matched),
        event_types=dict(kinds), first_observed_ms=first, last_observed_ms=last,
        zero_spread_ticks=zero, all_ticks_zero_spread=bool(ticks and zero == ticks),
        inter_tick_gap_ms=dict(sorted(gaps.items())), gaps_over_three_seconds=sum(n for gap, n in gaps.items() if gap > 3000),
        tick_provenance='MT4_TESTER_MODEL_UNVERIFIED' if origin == 'BACKTEST_MT4' else 'LOCAL_MT4_OBSERVATION_NOT_INDEPENDENT_FEED_AUTHENTICATION',
        network_latency_proven=False,
        warnings=(['ZERO_SPREAD_NOT_REPRESENTATIVE_OF_TRADING_COSTS'] if ticks and zero == ticks else []) +
                 (['NO_REPLAY_INPUTS'] if not paths else []))


def diagnose(source, output, progress=None):
    source, output = Path(source), Path(output)
    if output.resolve() == source.resolve() or source.resolve() in output.resolve().parents:
        raise ValueError('Write diagnosis outside the input journal')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a fresh diagnosis output directory')
    policy = read_policy(source)
    origin = read_origin(source, policy)
    names = ['data_origin.csv', 'demo_policy.csv']
    completion = None
    if origin == 'BACKTEST_MT4':
        names.append('tester_complete.csv')
    metadata = {name: (source/name).read_bytes() for name in names}
    if origin == 'BACKTEST_MT4':
        with (source/'tester_complete.csv').open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream); complete = list(reader)
            if reader.fieldnames != ['schema', 'logic', 'sequence', 'observed_ms'] or len(complete) != 1:
                raise ValueError('Invalid Tester completion marker')
        completion = {k: int(v) for k, v in complete[0].items()}
        if completion['schema'] != 1 or completion['logic'] != LOGIC:
            raise ValueError('Tester completion identity differs')
    paths = event_paths(source)
    if completion and len(paths) != completion['sequence']:
        raise ValueError('Tester file count differs from completion marker')
    initial_files = sorted(p.name for p in source.iterdir() if p.is_file())
    initial_stats = {name: ((source/name).stat().st_size, (source/name).stat().st_mtime_ns) for name in initial_files}
    digest = hashlib.sha256()
    for name, content in metadata.items():
        digest.update(name.encode()); digest.update(content)
    count = asof = 0
    facts, groups = {}, defaultdict(list)
    def verified(path, content):
        nonlocal count
        digest.update(path.name.encode()); digest.update(content)
        count += 1
        if count % 256 == 0 or count == len(paths):
            notify(progress, 'read', done=count, total=len(paths), unit='BIN', detail='FNV, sequence and SHA256; no training')
    for record in iter_directory(source, paths=paths, on_record=verified, compact=True):
        s, event = record['state'], record['event']
        if count == 1 and s['sequence'] != 1:
            raise ValueError('Need full journal starting at sequence 1')
        if s['configHash'] != policy['config_hash'] or s['feedHash'] != policy['feed_hash']:
            raise ValueError('Journal config/feed differs from policy')
        asof = max(asof, event['observedMs'])
        if event['analysisStart'] > 0 and event['kind'] in (3, 4, 5, 6, 7):
            groups[event['analysisStart']].append(record)
        if event['kind'] in (3, 4, 5):
            facts[s['sequence']] = dict(analysis_start=event['analysisStart'], event_kind=event['kind'],
                observed_ms=event['observedMs'], stored_quote_ms=s['current']['lastQuoteMs'],
                reason=REASONS[event['reason']], locked_direction=event['lockedDirection'],
                canceled=s['current']['canceled'], signal=event['signal'])
    if completion and (completion['sequence'] != count or completion['observed_ms'] != asof):
        raise ValueError('Tester completion differs from verified journal')
    snapshot = dict(origin=origin, execution_traces=trace(groups))
    report, rows = review(snapshot, digest.hexdigest(), source, native_facts=facts)
    quality = input_quality(source, origin, progress, rows)
    if (sorted(p.name for p in source.iterdir() if p.is_file()) != initial_files or
        [p.name for p in event_paths(source)] != [p.name for p in paths] or
        any((source/name).read_bytes() != content for name, content in metadata.items())):
        raise ValueError('Journal changed during diagnosis; stop EA and copy it first')
    if any(((source/name).stat().st_size, (source/name).stat().st_mtime_ns) != signature
           for name, signature in initial_stats.items()):
        raise ValueError('Journal file changed during diagnosis; use a stopped copy')
    for item in report['observer_files']:
        if hashlib.sha256((source/item['name']).read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Observer changed during diagnosis')
    report.update(raw_journal=True, native_records=count, completion_marker_verified=completion is not None,
        model_trained=False, input_quality_file='input_quality.json', native_guards_changed=False,
        source_snapshot='SEALED_TESTER' if completion else 'STABLE_LOCAL_LIVE_JOURNAL',
        broker_orders_sent_by_diagnosis=False)
    output.mkdir(parents=True, exist_ok=True)
    atomic(output/'execution_review.json', (json.dumps(report, indent=2, sort_keys=True)+'\n').encode())
    atomic(output/'input_quality.json', (json.dumps(quality, indent=2, sort_keys=True)+'\n').encode())
    atomic(output/'execution_review.csv', csv_bytes(sorted(rows[0]) if rows else ['status'], rows))
    return report
