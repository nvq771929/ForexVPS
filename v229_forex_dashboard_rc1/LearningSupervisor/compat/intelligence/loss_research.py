"""V223 manual-signal postmortem. Descriptive, train-only, never a trade filter.

All predictors are immutable native LOCK features. Future price paths are kept
in separately named ex-post columns. Binary BID labels are not Forex P&L.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import json
import math
from pathlib import Path
import numpy as np

from .candidate_data import verify
from .demo_learning import points
from .market_sessions import classify

CONTRACT = 'V223_MANUAL_LOSS_RESEARCH_V1'
TRAIN_END = 1768435200  # 2026-01-15 UTC, exclusive entry/extended outcome cutoff.
SETUPS = {1: 'SR1', 2: 'TP1', 3: 'BR1'}
REGIMES = {0: 'UNKNOWN', 1: 'RANGE', 2: 'ORDERLY_UP', 3: 'ORDERLY_DOWN',
           4: 'EXPANSION_UP', 5: 'EXPANSION_DOWN', 6: 'TRANSITION', 7: 'COMPRESSION'}
HYPOTHESES = ('opposing_momentum', 'weak_confirmation', 'far_from_confirmation',
              'limited_target_room', 'large_anchor', 'late_push', 'wide_invalidation')


def hypothesis_flags(f):
    return dict(opposing_momentum=f['momentum_direction'] < -1,
                weak_confirmation=f['confirmation_margin_atr'] < .10,
                far_from_confirmation=f['confirmation_margin_atr'] > 1,
                limited_target_room=bool(f['reward_available'] == 1 and f['reward_distance_atr'] < .5),
                large_anchor=f['range_atr'] > 1.5,
                late_push=f['t1_net_direction'] > .5,
                wide_invalidation=f['risk_distance_atr'] > 2)


def stats(rows):
    c = Counter(r['status'] for r in rows)
    n = c['WIN'] + c['LOSS']
    return dict(n=len(rows), WIN=c['WIN'], LOSS=c['LOSS'], TIE=c['TIE'],
                win_rate_decisive=c['WIN']/n if n else None,
                assumed_82pct_stake_units=round(c['WIN']*.82-c['LOSS'], 8))


def path_metrics(signal, ticks, lock_bid=None, cutoff=TRAIN_END):
    """Observed modelled ticks only. No interpolation or causal explanation."""
    result = dict(expost_path_status='UNAVAILABLE', expost_mfe_pips=None,
                  expost_mae_pips=None, expost_loss_pattern='UNKNOWN',
                  expost_lock_to_entry_signed_pips=None,
                  expost_10m_status='UNAVAILABLE', expost_15m_status='UNAVAILABLE')
    result.update(dict.fromkeys(('expost_quote_count', 'expost_max_gap_ms', 'expost_terminal_signed_pips',
                                 'expost_first_favourable_second', 'expost_last_favourable_second',
                                 'expost_first_peak_second', 'expost_final_below_entry_second'), None))
    result.update({f'expost_minute_{m}_signed_pips': None for m in range(1, 6)})
    entry, expiry = signal['entry_broker_seconds'], signal['expiry_broker_seconds']
    d = 1 if signal['direction'] == 'CALL' else -1
    if lock_bid is not None:
        result['expost_lock_to_entry_signed_pips'] = d*(float(signal['entry_bid'])-lock_bid)*10000
    if ticks is None:
        return result
    ms = ticks['ms']
    left = int(np.searchsorted(ms, entry*1000, side='left'))
    right = int(np.searchsorted(ms, expiry*1000, side='left'))
    if right >= len(ticks) or left >= len(ticks):
        return result
    if ms[left] > (entry+2)*1000 or ms[right] > (expiry+2)*1000:
        return result
    if (points(ticks['bid'][left]) != points(signal['entry_bid']) or
            points(ticks['bid'][right]) != points(signal['exit_bid'])):
        raise ValueError('Postmortem path boundary differs from verified manual ledger')
    # Work in original EURUSD integer points: avoid floating point zero crossings.
    delta = d*(np.rint(ticks['bid'][left:right+1]*100000).astype(np.int64)-points(signal['entry_bid']))
    result.update(expost_path_status='RECORDED_MODELLED_TICKS', expost_quote_count=len(delta),
                  expost_max_gap_ms=int(np.diff(ms[left:right+1]).max()) if right > left else 0,
                  expost_mfe_pips=float(max(0, delta.max())/10),
                  expost_mae_pips=float(max(0, -delta.min())/10),
                  expost_terminal_signed_pips=float(delta[-1]/10))
    favourable = np.flatnonzero(delta > 0)
    result['expost_first_favourable_second'] = float((ms[left+favourable[0]]-ms[left])/1000) if len(favourable) else None
    result['expost_last_favourable_second'] = float((ms[left+favourable[-1]]-ms[left])/1000) if len(favourable) else None
    peak = int(np.argmax(delta))
    result['expost_first_peak_second'] = float((ms[left+peak]-ms[left])/1000) if delta[peak] > 0 else None
    nonnegative = np.flatnonzero(delta >= 0)
    final_adverse = int(nonnegative[-1])+1 if len(nonnegative) else 0
    result['expost_final_below_entry_second'] = float((ms[left+final_adverse]-ms[left])/1000) if delta[-1] < 0 and final_adverse < len(delta) else None
    # End-of-minute observations, not interpolated candles. All are ex post.
    for minute in range(1, 6):
        target = entry*1000+minute*60000
        ix = min(right, int(np.searchsorted(ms, target, side='right'))-1)
        result[f'expost_minute_{minute}_signed_pips'] = float(d*(points(ticks['bid'][ix])-points(signal['entry_bid']))/10) if ix >= left else None
    if signal['status'] == 'LOSS':
        result['expost_loss_pattern'] = 'FAVOURABLE_THEN_LOST_AT_EXPIRY' if delta.max() > 0 else 'NEVER_FAVOURABLE_OBSERVED'
    else:
        result['expost_loss_pattern'] = 'NOT_A_LOSS'
    for minutes in (10, 15):
        target = entry+minutes*60
        if target >= cutoff:
            result[f'expost_{minutes}m_status'] = 'OUTSIDE_TRAIN'
            continue
        ix = int(np.searchsorted(ms, target*1000, side='left'))
        if ix < len(ticks) and ms[ix] <= (target+2)*1000:
            move = d*(points(ticks['bid'][ix])-points(signal['entry_bid']))
            result[f'expost_{minutes}m_status'] = 'WIN' if move > 0 else 'LOSS' if move < 0 else 'TIE'
    return result


def matched_effect(rows, name):
    """Within strategy/session loss-rate difference, both groups represented.

    Not a treatment effect: setup mix, dependence and unmeasured context remain.
    """
    groups = defaultdict(list)
    for r in rows:
        groups[(r['setup'], r['session'])].append(r)
    numerator = denominator = 0.
    strata = 0
    for rr in groups.values():
        a = [r for r in rr if r['hypothesis_'+name]]
        b = [r for r in rr if not r['hypothesis_'+name]]
        if not a or not b:
            continue
        weight = len(a)*len(b)/(len(a)+len(b))
        difference = sum(r['status'] == 'LOSS' for r in a)/len(a)-sum(r['status'] == 'LOSS' for r in b)/len(b)
        numerator += weight*difference
        denominator += weight
        strata += 1
    return (numerator/denominator if denominator else None), strata


def analyze(snapshot, manual, ticks=None, *, broker_offset_minutes=None, lock_bids=None, development_end=TRAIN_END):
    verify(snapshot)
    if not isinstance(development_end, int) or development_end <= 0:
        raise ValueError('Explicit positive development cutoff required')
    if (manual['status'] != 'VERIFIED_LOCAL_BOOK' or manual['contract'] != 'V218_MANUAL_PUBLICATION_V1' or
            snapshot['origin'] != 'BACKTEST_MT4' or manual['source_origin'] != snapshot['origin'] or
            manual['native_prefix_records'] != snapshot['native_records']):
        raise ValueError('Need matching sealed-Tester candidate snapshot and verified local manual book')
    if ticks is not None:
        if ticks.dtype.names != ('ms', 'bid', 'ask') or np.any(np.diff(ticks['ms']) < 0):
            raise ValueError('Invalid or backwards tick path')
        if (not np.all(np.isfinite(ticks['bid'])) or not np.all(np.isfinite(ticks['ask'])) or
                np.any(ticks['bid'] <= 0) or np.any(ticks['ask'] < ticks['bid'])):
            raise ValueError('Invalid path quote')
    by = {r['analysis_start']: r for r in snapshot['rows'] if r['ready_at_lock']}
    rows = []
    signals = manual['signals']
    if len({s['signal_id'] for s in signals}) != len(signals):
        raise ValueError('Duplicate signal')
    for s in signals:
        if s['entry_broker_seconds'] >= development_end:
            continue  # Do not read outcome/features in calibration/test for filter discovery.
        c = by.get(s['signal_id'])
        if c is None or c['features'] is None or c['entry_target'] != s['entry_broker_seconds']:
            raise ValueError('Committed publication lacks causal READY LOCK features')
        if c['feature_asof_ms'] != c['locked_at_ms'] or c['locked_at_ms'] > s['published_ms']:
            raise ValueError('Feature clock later than publication')
        if s['status'] not in ('WIN', 'LOSS', 'TIE'):
            continue
        if c['available_at_ms'] >= development_end*1000:
            continue  # Outcomes crossing the split belong to neither training nor selection.
        expected = {'FAVORABLE': 'WIN', 'ADVERSE': 'LOSS', 'TIE': 'TIE'}.get(c['quality_status'])
        if expected != s['status'] or c['expiry_target'] != s['expiry_broker_seconds']:
            raise ValueError('Candidate quality disagrees with manual boundary label')
        d = 1 if s['direction'] == 'CALL' else -1
        if d != c['direction'] or d*(points(s['exit_bid'])-points(s['entry_bid'])) != c['signed_points']:
            raise ValueError('Direction/price differs from native quality label')
        f = dict(zip(snapshot['feature_names'], c['features']))
        utc = s['entry_broker_seconds']-broker_offset_minutes*60 if broker_offset_minutes is not None else None
        row = dict(signal_id=s['signal_id'], status=s['status'], direction=s['direction'],
                   entry_broker=s['entry_broker_seconds'], expiry_broker=s['expiry_broker_seconds'],
                   feature_asof_ms=c['feature_asof_ms'], setup=SETUPS[c['setup']], regime=REGIMES[c['regime']],
                   session=classify(utc)['session'], day=s['entry_broker_seconds']//86400,
                   month=datetime.fromtimestamp(s['entry_broker_seconds'], timezone.utc).strftime('%Y-%m'),
                   native_canceled=s['native_canceled'], is_broker_trade=False,
                   entry_bid=float(s['entry_bid']), exit_bid=float(s['exit_bid']))
        row.update({'lock_'+k: v for k, v in f.items()})
        row.update({'hypothesis_'+k: v for k, v in hypothesis_flags(f).items()})
        row.update(path_metrics(s, ticks, (lock_bids or {}).get(s['signal_id']), development_end))
        rows.append(row)
    strata = []
    for key in ('setup', 'regime', 'session', 'direction', 'month', 'expost_loss_pattern'):
        for value in sorted({r[key] for r in rows}):
            strata.append(dict(dimension=key, value=value, **stats([r for r in rows if r[key] == value])))
    comparisons = []
    if rows:
        days = sorted({r['day'] for r in rows})
        rng = np.random.default_rng(223)
        indices = rng.integers(0, len(days), size=(1000, len(days)))
        by_day = {d: [r for r in rows if r['day'] == d] for d in days}
        for name in HYPOTHESES:
            affected = [r for r in rows if r['hypothesis_'+name]]
            unaffected = [r for r in rows if not r['hypothesis_'+name]]
            diff, nstrata = matched_effect(rows, name)
            samples = []
            for ix in indices:
                rr = [r for j in ix for r in by_day[days[int(j)]]]
                effect, _ = matched_effect(rr, name)
                if effect is not None:
                    samples.append(effect)
            ci = [float(x) for x in np.quantile(samples, [.025, .975])] if samples else None
            comparisons.append(dict(hypothesis=name, affected=stats(affected), unaffected=stats(unaffected),
                                    strategy_session_matched_loss_rate_difference=diff, matched_strata=nstrata,
                                    day_block_bootstrap_95pct=ci, bootstrap_resamples=1000,
                                    causal_interpretation=False, multiple_comparison_adjusted=False,
                                    accepted_as_trade_filter=False))
    losses = [r for r in rows if r['status'] == 'LOSS']
    summary = dict(contract=CONTRACT, dataset_sha256=snapshot['native_dataset_sha256'],
                   origin=snapshot['origin'], cohort='COMMITTED_MANUAL_MT4_BID_NOT_FOREX',
                   development_end_exclusive=development_end, development=stats(rows),
                   loss_patterns=dict(Counter(r['expost_loss_pattern'] for r in losses)),
                   losses_within_half_pip=sum(abs(r['exit_bid']-r['entry_bid']) <= .00005+1e-12 for r in losses),
                   losses_observed_mfe_at_least_one_pip=sum((r['expost_mfe_pips'] or 0) >= 1 for r in losses),
                   losses_observed_mfe_at_least_half_atr=sum((r['expost_mfe_pips'] or 0) >= .5*r['lock_atr_pips'] for r in losses),
                   losses_first_favourable_within_60s=sum(r.get('expost_first_favourable_second') is not None and r['expost_first_favourable_second'] <= 60 for r in losses),
                   losses_final_below_entry_in_last_60s=sum(r.get('expost_final_below_entry_second') is not None and r['expost_final_below_entry_second'] >= 240 for r in losses),
                   losses_later_status={str(m): dict(Counter(r[f'expost_{m}m_status'] for r in losses)) for m in (10, 15)},
                   wins_later_status={str(m): dict(Counter(r[f'expost_{m}m_status'] for r in rows if r['status'] == 'WIN')) for m in (10, 15)},
                   session_clock='USER_CONFIRMED_CONSTANT_OFFSET' if broker_offset_minutes is not None else 'UNKNOWN',
                   broker_offset_minutes=broker_offset_minutes, historical_news_verified=False,
                   features='IMMUTABLE_PREENTRY_LOCK_ONLY', future_path='EX_POST_DIAGNOSIS_ONLY',
                   hypotheses=len(comparisons), accepted_filters=[], native_guards_changed=False,
                   model_fit=False, source_orders_sent=False, forex_performance_inferred=False,
                   limitations=['Loss patterns and associations do not establish a unique causal root cause.',
                                'Modelled Tester ticks; no Olymp fill or bid/ask trading-cost evidence.',
                                'No historical as-of news, so news attribution is UNKNOWN.',
                                'No new filter promoted; independent evidence and native replay required.',
                                'Ex-post future metrics cannot select entry, stop or hold duration.'])
    return summary, rows, strata, comparisons


def write(output, result):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use fresh output directory outside the source journal')
    output.mkdir(parents=True, exist_ok=True)
    summary, rows, strata, comparisons = result
    for name, value in [('summary.json', summary), ('signals.json', rows), ('hypotheses.json', comparisons)]:
        (output/name).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
    for name, values in [('signals.csv', rows), ('strata.csv', strata)]:
        with (output/name).open('w', newline='', encoding='utf-8-sig') as stream:
            w = csv.DictWriter(stream, list(values[0]) if values else ['status'])
            w.writeheader()
            w.writerows(values)
    return summary
