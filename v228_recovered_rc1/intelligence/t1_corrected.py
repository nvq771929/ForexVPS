"""V2 contract: a missing target is unavailable, never the price zero.

Legacy V211 cache stays immutable. Migration uses only availability/direction
already recorded before LOCK, not future cancellation or trade outcomes.
"""
import hashlib
import json
import math
from collections import Counter
from .t1_features import CONTRACT as LEGACY_CONTRACT, NAMES as LEGACY_NAMES, extract as legacy_extract

CONTRACT = 'ANCHOR_T1_UP_V2'
NAMES = LEGACY_NAMES + ('reward_available',)
KEY = 'research_t1_v2'


def correct_features(values):
    if len(values) != len(LEGACY_NAMES) or not all(math.isfinite(v) and abs(v) < 1e6 for v in values):
        raise ValueError('Invalid legacy T+1 vector for causal migration')
    index = {name: i for i, name in enumerate(LEGACY_NAMES)}
    direction = values[index['candidate_direction']]
    present = values[index['candidate_present']]
    if direction not in (-1., 0., 1.) or present != float(direction != 0):
        raise ValueError('Candidate direction/presence differs')
    for name in ('support_available', 'resistance_available'):
        if values[index[name]] not in (0., 1.):
            raise ValueError('Target availability flag is not binary')
    available = bool(direction and values[index['resistance_available' if direction > 0 else 'support_available']])
    result = list(values)
    if not available:
        result[index['reward_distance_atr']] = 0.
    return result + [float(available)]


def extract(current, locked_at_ms):
    return correct_features(legacy_extract(current, locked_at_ms))


def migrate(snapshot):
    if not snapshot.get('research_t1'):
        raise ValueError('T+1 cache required: use completed prepared_history_v211.json.gz or read original journals once')
    rows = []
    missing = Counter()
    changed = 0
    for old in snapshot['research_t1']:
        if (old.get('cohort') != LEGACY_CONTRACT or old.get('source') != 'BACKTEST_MT4_PRICE_RESEARCH' or
                old.get('is_execution_trade') is not False or old['feature_asof_ms'] != old['locked_at_ms'] or
                old['anchor_asof_ms'] != old['analysis_start'] * 1000):
            raise ValueError('Migration needs the causal historical V1 T+1 clock/contract')
        features = correct_features(old['features'])
        direction = features[LEGACY_NAMES.index('candidate_direction')]
        if direction and not features[-1]:
            missing[str(old.get('candidate_setup', 'UNKNOWN'))] += 1
        changed += int(features[:-1] != old['features'])
        rows.append(dict(old, cohort=CONTRACT, features=features))
    canonical = lambda x: json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    audit = dict(schema=1, source_contract=LEGACY_CONTRACT, target_contract=CONTRACT,
        source_rows=len(rows), corrected_reward_rows=changed, unavailable_target_candidates=sum(missing.values()),
        unavailable_target_by_setup=dict(missing), target_feature_count=len(NAMES),
        source_feature_sha256=hashlib.sha256(canonical([r['features'] for r in snapshot['research_t1']])).hexdigest(),
        derived_feature_sha256=hashlib.sha256(canonical([r['features'] for r in rows])).hexdigest(),
        rule='Missing opposite zone => reward=0 and reward_available=0. Available distances retained regardless of magnitude.',
        source_mutated=False, future_fields_used=False, tester_rerun_required=False)
    return rows, audit


def with_corrected(snapshot):
    rows, audit = migrate(snapshot)
    return dict(snapshot, **{KEY: rows}, t1_v2_migration=audit)
