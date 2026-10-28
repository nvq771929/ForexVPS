"""Validate V222 per-slot diagnostics against the immutable native prefix."""
import csv,hashlib,io
from collections import Counter
from pathlib import Path
from .native_ledger import iter_directory,event_paths

def review(source,snapshot):
    source=Path(source);files=sorted(source.glob('analysis_slots_v222_*.csv')) if source.is_dir() else []
    if not files:return dict(contract='V222_ANALYSIS_SLOT_V1',status='UNAVAILABLE_OLD_SOURCE',rows=0,final_counts={},records=[],activation_allowed=False)
    limit=snapshot['native_records'];native={r['state']['sequence']:r for r in iter_directory(source,paths=event_paths(source)[:limit],compact=True)}
    rows=[];final=set();manifests=[];policy=snapshot['policy'];states={}
    valid={'WAIT_TICK','WAIT_HISTORY_BAR','HISTORY_UNAVAILABLE','QUOTE_TOO_OLD','DISCONNECTED','CREATED','MISSED_START_WINDOW','ATTACH_OR_RECOVERY','COOLDOWN','STORAGE_ERROR'}
    for path in files:
        raw=path.read_bytes()
        if len(raw)>32*1024**2:raise ValueError('Slot observer exceeds size limit')
        if raw and not raw.endswith(b'\n'):raw=raw[:raw.rfind(b'\n')+1]
        manifests.append(dict(name=path.name,consumed_sha256=hashlib.sha256(raw).hexdigest()))
        for row in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
            seq=int(row['native_sequence']);observed=int(row['observed_ms']);bar=int(row['analysis_start'])
            if seq>limit:continue # Diagnostic time can advance without a new native decision; never a model input.
            key=(row['session'],bar)
            # This is the unchanged V222 observer contract, not the worker release.
            if int(row['schema'])!=1 or int(row['logic'])!=policy['logic'] or row['software']!='2.22' or path.name!='analysis_slots_v222_'+row['session']+'.csv':raise ValueError('Invalid slot identity')
            if any(int(row[k])!=policy[k] for k in ('config_hash','feed_hash','policy_hash')):raise ValueError('Slot policy differs')
            if bar<=0 or bar%300 or observed<bar*1000 or seq not in native or row['status'] not in valid or row['phase'] not in ('WAIT','FINAL') or row['history_ready'] not in ('true','false','0','1') or row['paused'] not in ('0','1'):raise ValueError('Invalid slot observation')
            if observed<native[seq]['event']['observedMs']:raise ValueError('Slot observation precedes its native reference')
            if key in final:raise ValueError('Slot observation after final result')
            if observed<states.get(key,0):raise ValueError('Slot clock moved backwards')
            states[key]=observed
            if row['phase']=='FINAL':
                final.add(key)
                if row['status'] not in {'CREATED','MISSED_START_WINDOW','ATTACH_OR_RECOVERY','COOLDOWN','STORAGE_ERROR'}:raise ValueError('Invalid slot final state')
            if row['status']=='CREATED':
                e=native[seq]['event']
                if row['phase']!='FINAL' or e['kind']!=1 or e['analysisStart']!=bar or e['observedMs']!=observed:raise ValueError('Slot ANCHOR differs from native record')
            rows.append(row)
    return dict(contract='V222_ANALYSIS_SLOT_V1',status='VERIFIED_LOCAL_OBSERVER',rows=len(rows),
        final_counts=dict(Counter(r['status'] for r in rows if r['phase']=='FINAL')),
        missed_by_last_blocker=dict(Counter(r['blocker'] for r in rows if r['status']=='MISSED_START_WINDOW')),
        native_prefix_asof_ms=snapshot['asof_ms'],observer_asof_ms=max((int(r['observed_ms']) for r in rows),default=None),
        open_observed_slots=len(states)-len(final),observer_files=manifests,records=rows,activation_allowed=False,
        interpretation='Observed slots only; local diagnostic time may follow the last native event. Created rows cross-check native ANCHOR; other statuses are observer facts, never model inputs. Gaps without events are not reconstructed.')
