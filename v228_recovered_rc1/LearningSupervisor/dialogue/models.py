"""Frozen pre-lock model and recomputed, prospective-only eligibility receipt."""
import copy
import json
import math
from pathlib import Path
from . import MODEL_CONTRACT,FEATURE_CONTRACT
from .features import NAMES,CONTEXT_NAMES
from supervisor.store import digest
from supervisor.learning import validate_model_net,metrics

def load(path):
    model=json.loads(Path(path).read_text(encoding='utf-8'));payload=copy.deepcopy(model);identity=payload.pop('model_id',None)
    if (model.get('contract')!=MODEL_CONTRACT or model.get('feature_contract')!=FEATURE_CONTRACT or
        digest(payload)!=identity or model.get('target')!='REQUEST_DIRECTION_MT4_WIN_VS_LOSS' or
        model.get('feature_names')!=list(NAMES) or model.get('context_names')!=list(CONTEXT_NAMES)):
        raise ValueError('Incompatible adviser model; LOCK/shadow models cannot advise before lock')
    if model['training_origin'] not in ('BACKTEST_MT4','LIVE_MT4') or model['broker_utc_offset_minutes'] is None:
        raise ValueError('Verified model clock/origin required')
    if not 0<model['train_prior']<1 or model['trained_cutoff_utc_ms']>=model['created_utc_ms']:
        raise ValueError('Invalid model chronology/prior')
    if model['threshold']!=.60:raise ValueError('Unregistered adviser threshold')
    temperature=model['network'].get('temperature',1.)
    if not isinstance(temperature,(int,float)) or not math.isfinite(temperature) or not .5<=temperature<=3:
        raise ValueError('Invalid pre-lock calibration temperature')
    validate_model_net(model['network'])
    return model

def qualification(path,model,policy):
    """A manually toggled 'validated' boolean alone never grants effects.

    This is local evidence integrity, not independent broker authentication.
    Receipt generation must use the audited pre-lock worker forecast ledger.
    """
    if path is None:return dict(qualified=False,cutoff_utc_ms=0,reason='NO_INDEPENDENT_FORWARD_RECEIPT')
    receipt=json.loads(Path(path).read_text());payload=dict(receipt);h=payload.pop('sha256',None)
    if (digest(payload)!=h or receipt.get('contract')!='V224_PRELOCK_FORWARD_VALIDATION_V1' or
        receipt.get('model_id')!=model['model_id'] or receipt.get('feature_contract')!=FEATURE_CONTRACT or receipt.get('policy')!=policy):
        raise ValueError('Forward validation receipt identity differs')
    rows=receipt['rows'];seen=set();y=[];p=[];selected=[];weeks=set()
    for r in rows:
        key=(r['feed_hash'],r['policy_hash'],r['analysis_start'],r['horizon'])
        if key in seen:raise ValueError('Repeated episode in independent validation')
        seen.add(key)
        if (r['origin']!='LIVE_MT4' or r['status'] not in ('WIN','LOSS') or r['model_id']!=model['model_id'] or
            r['feature_contract']!=FEATURE_CONTRACT or r['feed_hash']!=policy['feed_hash'] or r['policy_hash']!=policy['policy_hash'] or
            not model['created_utc_ms']<r['request_utc_ms']<=r['written_utc_ms']<=r['durable_utc_ms']<=r['ea_received_utc_ms']<r['deadline_utc_ms']<=r['ea_finalized_utc_ms']<r['entry_utc_ms']<r['expiry_utc_ms']<=r['label_available_utc_ms'] or
            not 0<=r['probability']<=1 or len(r['request_sha256'])!=64 or len(r['label_receipt_sha256'])!=64):
            raise ValueError('Invalid/retrospective independent validation row')
        y.append(int(r['status']=='WIN'));p.append(r['probability']);weeks.add(r['entry_utc_ms']//604800000)
        selected.append(bool(r['in_domain'] and r['probability']>=model['threshold']))
    score=metrics(y,p);base=metrics(y,[model['train_prior']]*len(y));n=sum(selected)
    good=(model.get('offline_review_passed') is True and len(rows)>=150 and len(weeks)>=8 and n>=100 and n/max(1,len(rows))>=.2 and
        score['brier']<base['brier'] and score['log_loss']<base['log_loss'])
    return dict(qualified=bool(good),cutoff_utc_ms=max((r['label_available_utc_ms'] for r in rows),default=0),
        reason='INDEPENDENT_GATES_PASSED' if good else 'FORWARD_EVIDENCE_INSUFFICIENT',samples=len(rows),weeks=len(weeks),selected=n,
        metrics=score,baseline=base,receipt_sha256=h)

def export_forward_receipt(worker,dataset,model,persist=True):
    import csv
    rows=[];offset=worker.offset
    if offset is None:raise ValueError('Verified UTC offset required for prospective validation')
    predictions={r['query_path']:r for r in worker.store.all('prediction') if r['model_id']==model['model_id'] and r['timing']=='PROSPECTIVE_PRELOCK'}
    for sample in dataset['rows']:
        q=sample['query'];r=q['meta'];label=sample['label'];prediction=predictions.get(q['path'])
        if prediction is None or label['status'] not in ('WIN','LOSS'):continue
        final_path=worker.source/q['path'];final_path=final_path.with_name(f"final_{r['analysis_start']}.csv")
        if not final_path.exists():continue
        from .protocol import read_final
        f,final_sha256=read_final(final_path)
        if (int(f['request_sequence'])!=r['sequence'] or f['model_id']!=model['model_id'] or
            int(f['native_action'])!=r['direction'] or int(f['received_ms'])<=0):continue
        native=worker.store.get('native_lock',r['analysis_start'])
        if native is None or native['observed_ms']!=int(f['final_ms']) or native['locked_action']!=int(f['final_action']):
            raise ValueError('Advisory final receipt differs from authoritative native LOCK')
        rows.append(dict(origin=worker.origin,status=label['status'],model_id=model['model_id'],feature_contract=FEATURE_CONTRACT,
            feed_hash=r['feed_hash'],policy_hash=r['policy_hash'],analysis_start=r['analysis_start'],horizon=r['horizon'],
            request_utc_ms=prediction['request_utc_ms'],written_utc_ms=prediction['written_utc_ms'],durable_utc_ms=prediction['durable_utc_ms'],
            ea_received_utc_ms=int(f['received_ms'])-offset*60000,ea_finalized_utc_ms=int(f['final_ms'])-offset*60000,
            deadline_utc_ms=prediction['deadline_utc_ms'],entry_utc_ms=r['target']*1000-offset*60000,
            expiry_utc_ms=r['expiry']*1000-offset*60000,label_available_utc_ms=label['available_at_ms']-offset*60000,
            probability=prediction['probability'],in_domain=prediction['in_domain'],
            request_sha256=q['request_sha256'],label_receipt_sha256=label['receipt_sha256'],native_receipt_sha256=final_sha256))
    receipt=dict(contract='V224_PRELOCK_FORWARD_VALIDATION_V1',feature_contract=FEATURE_CONTRACT,model_id=model['model_id'],
        policy=worker.policy,rows=rows,source='AUDITED_QUERY_TICKS_AND_NATIVE_RECEIPTS',activation_allowed=False)
    receipt['sha256']=digest(receipt)
    if not persist:return receipt
    from supervisor.store import atomic
    path=worker.output/'forward_validation.json';atomic(path,receipt)
    result=qualification(path,model,worker.policy);atomic(worker.output/'forward_validation_status.json',result);return result
