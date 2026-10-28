"""Incremental native LOCK capture and official publication enrollment.

Only the audit command attaches verified outcomes. Collection never reads a
future outcome to build an input vector, and never writes into the EA journal.
"""
from collections import Counter, deque
import hashlib
import json
from pathlib import Path
import time
from . import CONTRACT
from .store import canonical, digest, atomic
from intelligence.demo_learning import read_policy
from intelligence.origin import read_origin
from intelligence.native_ledger import decode_bytes
from intelligence import candidate_features as cf
from intelligence.research_features import extract as anchor_features
from intelligence.t1_corrected import extract as context_features
from intelligence.manual_signals import record

FEATURE_CONTRACT = 'V224_OFFICIAL_SIGNAL_SEQUENCE32_QUALITY_V1'

class Collector:
    def __init__(self, source, store):
        self.source = Path(source).resolve(); self.store = store
        if self.source == store.output or self.source in store.output.parents or store.output in self.source.parents:
            raise ValueError('Journal and output must be separate, non-nested directories')
        self.policy = read_policy(self.source)
        self.origin = read_origin(self.source, self.policy)
        metadata = {n: hashlib.sha256((self.source / n).read_bytes()).hexdigest()
                    for n in ('demo_policy.csv', 'data_origin.csv')}
        self.identity = dict(contract=CONTRACT, policy=self.policy, origin=self.origin,
                             metadata=metadata, source_path=str(self.source))
        store.put('identity', 'source', self.identity); store.commit()
        self.verify_prefix()
        native = store.all('native')
        self.last = max((r['sequence'] for r in native), default=0)
        anchors = sorted(store.all('anchor'), key=lambda r:r['start'])
        self.anchors = deque(anchors[-32:], maxlen=32)
        self.seen = {r['file'] for r in store.all('manual_file')}
        self.verify_cursor=0

    def verify_batch(self,limit=256):
        """Bound foreground work. Full prefix checks still run on startup/audit."""
        for name,h in self.identity['metadata'].items():
            if hashlib.sha256((self.source/name).read_bytes()).hexdigest()!=h:
                raise ValueError('Journal metadata changed')
        rows=self.store.db.execute("SELECT kind,id FROM facts WHERE kind IN ('native','manual_file') ORDER BY kind,id LIMIT ? OFFSET ?",(limit,self.verify_cursor)).fetchall()
        if not rows:
            self.verify_cursor=0;return
        for kind,identity in rows:
            fact=self.store.get(kind,identity)
            if hashlib.sha256((self.source/fact['file']).read_bytes()).hexdigest()!=fact['sha256']:
                raise ValueError('Previously observed journal bytes changed')
        self.verify_cursor+=len(rows)

    def verify_prefix(self):
        for name, h in self.identity['metadata'].items():
            if hashlib.sha256((self.source/name).read_bytes()).hexdigest() != h:
                raise ValueError('Journal metadata changed')
        for fact in self.store.all('native') + self.store.all('manual_file'):
            if hashlib.sha256((self.source/fact['file']).read_bytes()).hexdigest() != fact['sha256']:
                raise ValueError('Previously observed journal bytes changed')

    def poll(self):
        # Native records are atomically renamed by the EA. Never accept gaps.
        n = 0
        while True:
            sequence = self.last + 1
            path = self.source / f'event_{sequence:012d}.bin'
            if not path.exists():
                if any(int(p.stem[6:]) > sequence for p in self.source.glob('event_*.bin')):
                    raise ValueError('Native sequence gap')
                break
            raw = path.read_bytes(); r = decode_bytes(raw, sequence, compact=True)
            s,e = r['state'],r['event']; cur = s['current']
            if s['configHash'] != self.policy['config_hash'] or s['feedHash'] != self.policy['feed_hash']:
                raise ValueError('Native policy changed')
            if e['kind'] == 1:
                try:
                    a = dict(start=e['analysisStart'], observed_ms=e['observedMs'], features=anchor_features(cur))
                except ValueError as ex:
                    # Missing history is a diagnostic, never fabricated input.
                    self.store.put('feature_error', sequence, dict(sequence=sequence, error=str(ex)))
                else:
                    self.store.put('anchor',a['start'],a);self.anchors.append(a)
            if e['kind'] == 3:
                d = cur['candidate']['direction']; setup = cur['candidate']['setup']
                row = dict(start=e['analysisStart'], sequence=sequence, event=e,
                           canceled=bool(cur['canceled']), context=None, features=None, sequence32=None,
                           feature_contract=FEATURE_CONTRACT)
                if d in (-1,1) and setup in (1,2,3):
                    try:
                        context = context_features(cur, e['observedMs'])
                        row.update(context=context, features=cf.extract(context,setup,d))
                    except ValueError as ex:
                        row['feature_error'] = str(ex)
                starts = [a['start'] for a in self.anchors]
                if (len(starts)==32 and starts[-1]==e['analysisStart'] and
                    all(b-a==300 for a,b in zip(starts,starts[1:])) and
                    all(a['observed_ms']<=e['observedMs'] for a in self.anchors)):
                    row['sequence32'] = [a['features'] for a in self.anchors]
                self.store.put('lock', sequence, row)
                # Includes WAIT/rejected LOCKs. This is not an official signal cohort.
                self.store.put('opportunity', row['start'], dict(start=row['start'], target=e['targetTime'],
                    asof_ms=e['observedMs'], native_action=e['lockedAction'], native_reason=e['reason'],
                    validation=e['validation'], features_available=row['features'] is not None,
                    interpretation='OBSERVED_DECISION_NOT_A_MISSED_TRADE'))
            self.store.put('native', sequence, dict(sequence=sequence, file=path.name,
                sha256=hashlib.sha256(raw).hexdigest(), observed_ms=e['observedMs']))
            self.last = sequence; n += 1
            if n % 512 == 0: self.store.commit()
        for path in sorted(self.source.glob('manual_v218_*.csv')):
            if path.name in self.seen: continue
            row,m = record(path,self.policy)
            if row['lock_sequence'] > self.last: continue
            if row['kind'] == 1:
                lock = self.store.get('lock', row['lock_sequence'])
                if not lock: raise ValueError('Official publication LOCK absent')
                e = lock['event']
                if (e['analysisStart']!=row['signal_id'] or e['targetTime']!=row['target'] or
                    e['lockedAction']!=row['direction'] or e['selectedHorizon']!=row['horizon'] or
                    e['setup']!=row['setup'] or e['regime']!=row['regime'] or e['validation']!=2 or
                    e['reason']!=0 or lock['canceled'] or e['observedMs']>row['published_ms'] or
                    row['result']!=8 or row['observed_ms']!=row['published_ms'] or row['bid_decimal']<=0):
                    raise ValueError('Official publication differs from LOCK')
                if not row['signal_id']*1000<=e['observedMs']<=(row['target']-31)*1000:
                    raise ValueError('LOCK outside causal window')
                case = dict(signal_id=row['signal_id'], direction=row['direction'], setup=row['setup'],
                    native_model_id=e['modelId'],
                    regime=row['regime'], published_ms=row['published_ms'], entry_ms=row['target']*1000,
                    expiry_ms=row['expiry']*1000, horizon=row['horizon'], feature_asof_ms=e['observedMs'],
                    feature_contract=FEATURE_CONTRACT, features=lock['features'], context=lock['context'],
                    sequence32=lock['sequence32'], origin=self.origin, policy=self.policy)
                case['feature_hash'] = digest({k:case[k] for k in ('features','context','sequence32','feature_asof_ms')})
                self.store.put('case', row['signal_id'], case)
            if row['kind']==5:
                self.store.put('withheld',row['signal_id'],dict(signal_id=row['signal_id'],observed_ms=row['observed_ms']))
            self.store.put('manual_file', path.name, m); self.seen.add(path.name)
        self.store.commit()
        return n

    def status(self):
        labels = self.store.all('label')
        predictions = self.store.all('forecast')
        withheld={r['signal_id'] for r in self.store.all('withheld')}
        return dict(contract=CONTRACT, origin=self.origin, native_records=self.last,
                    official_cases=sum(r['signal_id'] not in withheld for r in self.store.all('case')),
                    withheld_publications=len(withheld),observed_decisions=len(self.store.all('opportunity')),
                    audited_outcomes=dict(Counter(r['status'] for r in labels)),
                    forecasts=len(predictions), prospective=sum(r['timing']=='PROSPECTIVE_SHADOW' and r['signal_id'] not in withheld for r in self.store.all('forecast_receipt')),
                    lifecycle='COLLECTING' if not self.store.all('model') else 'FROZEN_SHADOW',
                    ea_control_enabled=False, activation_allowed=False, price_source='MT4_BID',
                    updated_utc_ms=time.time_ns()//1000000)

    def write_status(self):
        result = self.status(); atomic(self.store.output/'status.json', result); return result
