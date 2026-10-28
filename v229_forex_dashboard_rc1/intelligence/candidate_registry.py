"""Append-only research runs; mutable pointers have no native activation authority."""
import hashlib,json
from pathlib import Path
from .candidate_data import canonical
from .candidate_learning import train
from .demo_learning import atomic
from .lease import exclusive


def checked(value,key='payload_sha256'):
    value=dict(value);digest=value.pop(key,None)
    if digest!=hashlib.sha256(canonical(value)).hexdigest():raise ValueError('Candidate artifact checksum differs')
    return value


def identity(snapshot):
    return dict(origin=snapshot['origin'],policy=snapshot['policy'],feature_contract=snapshot['feature_contract'])


def enrollments(snapshot):
    causal=('analysis_start','locked_at_ms','feature_asof_ms','entry_target','expiry_target','setup','direction',
        'regime','ready_at_lock','features','feature_unavailable_reason')
    return {r['sample_id']:dict(causal_sha256=hashlib.sha256(canonical({k:r[k] for k in causal})).hexdigest(),
        label=[r['quality_status'],r['signed_points'],r['available_at_ms']] if r['quality_status']!='PENDING' else None)
        for r in snapshot['rows']}


def write_state(path,state):
    state=dict(state);state['payload_sha256']=hashlib.sha256(canonical(state)).hexdigest()
    atomic(path,canonical(state))


def update(snapshot,output,rule_report=None,progress=None):
    checked(snapshot)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    with exclusive(output/'candidate_research.lock'):
        path=output/'registry.json'
        state=checked(json.loads(path.read_bytes())) if path.exists() else dict(schema=1,kind='V215_RESEARCH_REGISTRY',
            identity=identity(snapshot),runs=[],last_frozen_candidate=None,eligible_for_native_filter=False,
            model_import_allowed=False,native_forward_predictions=0)
        if state['identity']!=identity(snapshot):raise ValueError('Registry origin/feed/policy/feature contract differs; use a separate output')
        enrolled=enrollments(snapshot)
        for sample,old in state.get('enrollments',{}).items():
            new=enrolled.get(sample)
            if new is None or old['causal_sha256']!=new['causal_sha256'] or (old['label'] is not None and old['label']!=new['label']):
                raise ValueError('Registered LOCK facts or matured label changed')
        if state.get('last_asof_ms',0)>snapshot['asof_ms'] or state.get('last_native_records',0)>snapshot['native_records']:
            raise ValueError('Registry cannot move backwards to an older native prefix')
        mature=sum(r['ready_at_lock'] and r['features'] is not None and r['quality_status'] in ('FAVORABLE','ADVERSE') for r in snapshot['rows'])
        previous=state['runs'][-1] if state['runs'] else None
        days_since=(snapshot['asof_ms']-previous['asof_ms'])/86400000 if previous else None
        added=mature-previous['mature_decisive'] if previous else None
        unchanged=state.get('last_snapshot_sha256')==snapshot['payload_sha256']
        due=not previous or (not unchanged and days_since>=7 and added>=50)
        if due:
            name=f"r{len(state['runs'])+1:06d}_{snapshot['payload_sha256'][:12]}"
            folder=output/name
            # An interrupted run is preserved for diagnosis; never silently overwrite it.
            if folder.exists():raise ValueError('Incomplete or duplicate immutable run exists: '+name)
            report=train(snapshot,folder,progress,rule_report)
            entry=dict(run=name,snapshot_sha256=snapshot['payload_sha256'],native_dataset_sha256=snapshot['native_dataset_sha256'],
                asof_ms=snapshot['asof_ms'],native_records=snapshot['native_records'],mature_decisive=mature,
                status=report['status'],report_sha256=report['report_sha256'],model_sha256=report.get('model_sha256'))
            state['runs'].append(entry)
            if report['phase']=='FROZEN_CANDIDATE':state['last_frozen_candidate']=name
            status=report['status']
        else:
            report=json.loads((output/previous['run']/'candidate_report.json').read_bytes());checked(report,'report_sha256')
            status='UNCHANGED' if unchanged else 'WAIT_NEW_DATA'
        state.update(last_snapshot_sha256=snapshot['payload_sha256'],last_asof_ms=snapshot['asof_ms'],
            last_native_records=snapshot['native_records'],latest_mature_decisive=mature,enrollments=enrolled)
        write_state(path,state)
        return dict(status=status,run=state['runs'][-1]['run'],training_attempted=due,
            registered_candidates=len(snapshot['rows']),ready_mature_decisive=mature,deficits=report['deficits'],
            phase=report['phase'],last_frozen_candidate=state['last_frozen_candidate'],
            minimum_days_between_attempts=7,minimum_new_decisive=50,days_since_attempt=days_since,
            new_decisive_since_attempt=added,model_import_allowed=False,eligible_for_native_filter=False,
            native_forward_predictions=0,validation_scope='RETROSPECTIVE_EXPLORATION')
