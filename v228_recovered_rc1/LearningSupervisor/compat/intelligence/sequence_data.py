"""Causal sequences of recorded CLOSED-anchor features, not reconstructed OHLC/ticks."""
from collections import Counter
import hashlib
import math

from .research_features import NAMES as ANCHOR_NAMES, CONTRACT as ANCHOR_CONTRACT
from .t1_corrected import NAMES as CONTEXT_NAMES, CONTRACT as CONTEXT_CONTRACT, with_corrected, KEY
from .research_model import canonical

CONTRACT = 'V213_CLOSED_ANCHOR_SEQUENCE32_T1_V2'
LENGTH = 32


def build(snapshot):
    if snapshot.get('origin') != 'BACKTEST_MT4':
        raise ValueError('Deep history requires BACKTEST_MT4, never live evidence')
    snapshot = with_corrected(snapshot)
    anchors = {}
    for r in snapshot['research']:
        start = r['analysis_start']
        if (r['source'] != 'BACKTEST_MT4_PRICE_RESEARCH' or r['cohort'] != ANCHOR_CONTRACT or
                r['feature_asof_ms'] != start * 1000 or start % 300 or
                len(r['features']) != len(ANCHOR_NAMES) or
                not all(math.isfinite(v) and abs(v) < 1e6 for v in r['features'])):
            raise ValueError('Invalid closed-anchor sequence input')
        if start in anchors:
            raise ValueError('Duplicate anchor time; do not merge feeds/policies')
        anchors[start] = list(r['features'])
    times = sorted(anchors)
    indexes = {t: i for i, t in enumerate(times)}
    rows = []
    exclusions = Counter()
    seen = set()
    for original in sorted(snapshot[KEY], key=lambda r: r['entry_target']):
        r = dict(original)
        if r['sample_id'] in seen:
            raise ValueError('Duplicate T+1 sample')
        seen.add(r['sample_id'])
        start = r['analysis_start']
        if (r['cohort'] != CONTEXT_CONTRACT or r['source'] != 'BACKTEST_MT4_PRICE_RESEARCH' or
                r.get('is_execution_trade') is not False or r['horizon'] != snapshot['policy']['horizon'] or
                r['entry_target'] != start + 300 or r['expiry_target'] != r['entry_target'] + r['horizon'] * 300 or
                r['anchor_asof_ms'] != start * 1000 or r['feature_asof_ms'] != r['locked_at_ms'] or
                not start * 1000 <= r['locked_at_ms'] <= (r['entry_target'] - 31) * 1000 or
                len(r['features']) != len(CONTEXT_NAMES) or
                not all(math.isfinite(v) and abs(v) < 1e6 for v in r['features'])):
            raise ValueError('T+1 sequence clock/feature contract differs')
        if start not in anchors or r['features'][:len(ANCHOR_NAMES)] != anchors[start]:
            raise ValueError('Sequence final anchor differs from T+1 context')
        if r['status'] not in ('UP', 'DOWN', 'TIE'):
            exclusions['open_or_unavailable_label'] += 1
            continue
        if not r['locked_at_ms'] < r['entry_observed_ms'] < r['exit_observed_ms'] < r['available_at_ms'] < snapshot['asof'] * 1000:
            raise ValueError('Sequence features/outcome cross forecast or cutoff')
        end = indexes[start]
        if end < LENGTH - 1 or times[end - LENGTH + 1:end + 1] != list(range(start - (LENGTH - 1) * 300, start + 1, 300)):
            exclusions['missing_contiguous_anchor_history'] += 1
            continue
        r.update(sequence_end_index=end, sequence_first_asof_ms=(start - (LENGTH - 1) * 300) * 1000,
                 sequence_last_asof_ms=start * 1000)
        rows.append(r)
    # Bind all values used as inputs, not just the selected labels or native digest.
    anchor_digest = hashlib.sha256(canonical([(t, anchors[t]) for t in times])).hexdigest()
    data_digest = hashlib.sha256(canonical(dict(contract=CONTRACT, anchor_digest=anchor_digest, rows=rows))).hexdigest()
    audit = dict(contract=CONTRACT, sequence_length=LENGTH, sequence_channels=list(ANCHOR_NAMES),
                 context_features=list(CONTEXT_NAMES), anchor_count=len(times), eligible_samples=len(rows),
                 exclusions=dict(exclusions), anchor_values_sha256=anchor_digest, input_sha256=data_digest,
                 sequence_order='oldest_to_newest', sequence_spacing_seconds=300,
                 input_meaning='32 recorded closed-anchor feature vectors plus current pre-entry T+1 context; not raw OHLC',
                 imputation=False, future_candles=False, source='BACKTEST_MT4_PRICE_RESEARCH',
                 feature_migration=snapshot['t1_v2_migration'])
    return dict(rows=rows, times=times, anchors=[anchors[t] for t in times], audit=audit,
                all_corrected_rows=snapshot[KEY])


def arrays(dataset, rows):
    import numpy as np
    table = np.asarray(dataset['anchors'], dtype=np.float32)
    indexes = np.asarray([r['sequence_end_index'] for r in rows], dtype=np.int64)[:, None]
    offsets = np.arange(-LENGTH + 1, 1, dtype=np.int64)[None, :]
    return (table[indexes + offsets], np.asarray([r['features'] for r in rows], dtype=np.float32),
            np.asarray([r['status'] == 'UP' for r in rows], dtype=np.float32))
