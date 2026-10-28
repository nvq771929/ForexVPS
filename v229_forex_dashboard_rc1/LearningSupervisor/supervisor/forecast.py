"""Actual write-time provenance. Suggestions never become EA instructions."""
import time
from .learning import probabilities, in_domain

def forecast(store, case, model, origin, broker_offset=None, clock_ok=True):
    key=f"{model['model_id']}:{case['signal_id']}"
    if store.get('forecast',key):return None
    if case['policy']!=model['policy']:
        return 'MODEL_POLICY_MISMATCH'
    if any(case[k] is None for k in ('features','sequence32','context')):
        return 'FEATURES_OR_32_CONSECUTIVE_ANCHORS_MISSING'
    # A dummy label only satisfies the common tensor shape, never training.
    p=probabilities(model['network'],[dict(case=case,label=dict(status='UNLABELED'))])[0]
    if not 0<=p<=1:raise ValueError('Invalid forecast probability')
    domain=in_domain(model['network'],case)
    written=time.time_ns()//1000000
    timing='RETROSPECTIVE_ONLY';reason='BACKTEST_OR_UNVERIFIED_CLOCK_OR_LATE'
    training_offset=model.get('training_broker_utc_offset_minutes')
    if origin=='LIVE_MT4' and broker_offset is not None and training_offset==broker_offset and clock_ok:
        target_utc=case['entry_ms']-broker_offset*60000
        feature_utc=case['feature_asof_ms']-broker_offset*60000
        model_cutoff_utc=model['evaluation_cutoff_ms']-training_offset*60000
        if (feature_utc-1000<=written<target_utc and written-feature_utc<=15000 and
            model['created_utc_ms']<=feature_utc and model_cutoff_utc<feature_utc):
            timing='PRE_ENTRY_CANDIDATE';reason='AWAIT_DURABLE_RECEIPT'
    suggestion=('CALL' if case['direction']==1 else 'PUT') if domain and p>=model['threshold'] else 'WAIT'
    row=dict(model_id=model['model_id'],signal_id=case['signal_id'],feature_hash=case['feature_hash'],
        probability_mt4_win=p,in_domain=bool(domain),shadow_suggestion=suggestion,
        written_utc_ms=written,entry_broker_ms=case['entry_ms'],broker_utc_offset_minutes=broker_offset,
        timing=timing,timing_reason=reason,origin=origin,ea_control_enabled=False)
    store.put('forecast',key,row);store.commit()
    durable_by=time.time_ns()//1000000
    accepted=(timing=='PRE_ENTRY_CANDIDATE' and written<=durable_by<case['entry_ms']-broker_offset*60000)
    store.put('forecast_receipt',key,dict(model_id=model['model_id'],signal_id=case['signal_id'],
        durable_by_utc_ms=durable_by,timing='PROSPECTIVE_SHADOW' if accepted else 'RETROSPECTIVE_ONLY'))
    store.commit()
    return row

def shadow_evaluation(store):
    from .learning import metrics
    labels={r['signal_id']:r for r in store.all('label')}
    results=[]
    for m in store.all('model'):
        predictions=[r for r in store.all('forecast') if r['model_id']==m['model_id'] and
            (store.get('forecast_receipt',f"{r['model_id']}:{r['signal_id']}") or {}).get('timing')=='PROSPECTIVE_SHADOW' and r['signal_id'] in labels and
            labels[r['signal_id']]['status'] in ('WIN','LOSS')]
        y=[int(labels[r['signal_id']]['status']=='WIN') for r in predictions]
        p=[r['probability_mt4_win'] for r in predictions]
        selected=[i for i,r in enumerate(predictions) if r['shadow_suggestion']!='WAIT']
        # Frozen train prior, not a baseline refit using the future observations.
        prior=m.get('train_prior',.5)
        results.append(dict(model_id=m['model_id'],metrics=metrics(y,p),baseline=metrics(y,[prior]*len(y)),
            selected=len(selected),selected_wins=sum(y[i] for i in selected),
            status='PROSPECTIVE_OBSERVATION_ONLY',activation_allowed=False))
    return results
