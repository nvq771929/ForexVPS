"""Explain frozen research predictions; never modify, qualify or deploy a model."""
from collections import Counter,defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics

from . import research_model as rm
from .demo_learning import LOGIC
from .execution_diagnostics import summarize
from .research_features import CONTRACT
from .t1_features import CONTRACT as T1_CONTRACT
from .t1_corrected import CONTRACT as T1_V2_CONTRACT,KEY as T1_V2_KEY,with_corrected
from .progress import notify


def read_model(path):
    a=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(a,dict):raise ValueError('Invalid diagnostic model object')
    checksum=a.pop('payload_sha256',None)
    if checksum!=hashlib.sha256(rm.canonical(a)).hexdigest():raise ValueError('Diagnostic model checksum mismatch')
    contract=a.get('feature_contract');names=rm.CONTRACTS.get(contract)
    kind=rm.KIND if contract==CONTRACT else 'V213_T1_RESEARCH_UP_LOGISTIC_OR_HGB' if contract==T1_V2_CONTRACT else 'V211_T1_RESEARCH_UP_LOGISTIC_OR_HGB'
    if (a.get('schema')!=1 or a.get('kind')!=kind or a.get('logic')!=LOGIC or names is None or
        a.get('feature_names')!=list(names) or a.get('source_origin')!='BACKTEST_MT4' or
        a.get('label_source')!='BACKTEST_MT4_PRICE_RESEARCH' or a.get('eligible_for_live_filter') is not False):
        raise ValueError('Unsupported diagnostic research model contract')
    m=a.get('model')
    if m is not None:
        n=len(names)
        for key in ('mean','scale','low','high'):
            if len(m[key])!=n or not all(math.isfinite(v) and abs(v)<1e6 for v in m[key]):raise ValueError('Invalid diagnostic model numeric vector')
        if any(v<=0 for v in m['scale']) or any(lo>hi for lo,hi in zip(m['low'],m['high'])):raise ValueError('Invalid diagnostic model domain')
        if m.get('feature_contract')!=contract or m.get('phase')!='OFFLINE_RESEARCH_ONLY':raise ValueError('Invalid diagnostic model identity')
        if 'feature_names' in m and m['feature_names']!=list(names):raise ValueError('Diagnostic model feature names differ')
        if not all(math.isfinite(m[k]) and abs(m[k])<1e6 for k in ('intercept','calibration_slope','calibration_intercept')) or m['calibration_slope']<=0:
            raise ValueError('Invalid diagnostic calibration')
        if m['algorithm']=='logistic':
            if len(m['weight'])!=n or not all(math.isfinite(v) and abs(v)<1e6 for v in m['weight']):raise ValueError('Invalid diagnostic weights')
        elif m['algorithm']=='hgb':
            if not 1<=len(m['trees'])<=120:raise ValueError('Unsupported diagnostic tree count')
            for tree in m['trees']:
                if not 1<=len(tree)<=29:raise ValueError('Unsupported diagnostic tree size')
                for i,node in enumerate(tree):
                    if not math.isfinite(node['value']) or not math.isfinite(node['threshold']):raise ValueError('Nonfinite diagnostic tree')
                    if not node['leaf'] and (not 0<=node['feature']<n or not i<node['left']<len(tree) or not i<node['right']<len(tree)):
                        raise ValueError('Invalid diagnostic tree topology')
        else:raise ValueError('Unsupported diagnostic algorithm')
        if not 0<m['baseline_global']<1 or not all(0<v<1 for v in m['baseline_by_regime'].values()):raise ValueError('Invalid diagnostic baselines')
    a['payload_sha256']=checksum
    return a


def values_summary(values):
    if not values:return dict(count=0,min=None,max=None,median=None,p05=None,p95=None)
    values=sorted(values)
    def quantile(p):
        pos=(len(values)-1)*p;i=int(pos);return values[i]+(values[min(i+1,len(values)-1)]-values[i])*(pos-i)
    return dict(count=len(values),min=values[0],max=values[-1],median=statistics.median(values),p05=quantile(.05),p95=quantile(.95))


def diagnose(snapshot,artifact,digest,progress=None):
    if artifact['dataset_sha256']!=digest or artifact['policy']!=snapshot['policy'] or artifact['history_asof']!=snapshot['asof']:
        raise ValueError('Diagnostic model and prepared data identity/cutoff differ')
    if artifact['feature_contract']==T1_V2_CONTRACT:
        snapshot=with_corrected(snapshot)
    key=T1_V2_KEY if artifact['feature_contract']==T1_V2_CONTRACT else 'research_t1' if artifact['feature_contract']==T1_CONTRACT else 'research'
    if key not in snapshot:raise ValueError('T+1 features require one read of raw native journals; V210 cache cannot reconstruct them')
    rows=sorted([r for r in snapshot[key] if r['status'] in ('UP','DOWN','TIE') and r['available_at_ms']<snapshot['asof']*1000],key=lambda r:r['entry_target'])
    result=dict(schema=1,status='MODEL_NOT_FITTED',source='BACKTEST_MT4_PRICE_RESEARCH',dataset_sha256=digest,
        feature_contract=artifact['feature_contract'],model_import_allowed=False,automatic_filter=False,
        validation_scope='HISTORICAL_EXPLORATION',independent_confirmation_required=True,
        execution=summarize(snapshot),t1_rows_available=len(snapshot.get('research_t1',[])),
        t1_status='AVAILABLE' if snapshot.get('research_t1') else 'REQUIRES_RAW_JOURNALS',
        note='Diagnosis does not change a model, threshold, qualification or native execution guard.')
    m=artifact['model']
    if m is None:return result,[],[]
    if hashlib.sha256(rm.canonical(rows)).hexdigest()!=m['training_digest']:raise ValueError('Diagnostic training rows digest differs')
    training,calibration,test=rm.split(rows)
    if not test:raise ValueError('Frozen model has no reproducible held-out split')
    result.update(status='DIAGNOSED',algorithm=m['algorithm'],model_id=m['model_id'],threshold_up=rm.THRESHOLD,
        threshold_down=1-rm.THRESHOLD,calibration_slope=m['calibration_slope'],split_profiles={})
    notify(progress,'evaluate',detail='Chan doan xac suat / mien du lieu; giu nguyen model')
    for name,rr in (('train',training),('calibration',calibration),('test',test)):
        probs=[rm.probability(m,r['features']) for r in rr];domains=[rm.in_domain(m,r['features']) for r in rr]
        confidence=[rm.direction(p)!=0 for p in probs]
        result['split_profiles'][name]=dict(samples=len(rr),probability_up=values_summary(probs),
            confidence_pass_ignoring_domain=sum(confidence),in_domain=sum(domains),out_of_domain=len(rr)-sum(domains),
            selected=sum(d and c for d,c in zip(domains,confidence)))
    metrics,predictions=rm.evaluate(m,test);result['heldout_metrics']=metrics
    result['rejection_counts']=dict(Counter(r['rejection_reason'] for r in predictions))
    paper_setup={r['analysis_start']:r['setup'] for r in snapshot['papers']}
    def setup(r):
        value=r.get('candidate_setup',paper_setup.get(r['analysis_start']))
        return str(value) if value is not None else 'UNKNOWN_NOT_RECORDED'
    axes={'regime':lambda r:str(r['regime']),'setup':setup,'broker_hour':lambda r:str(r['entry_target']%86400//3600)}
    grouped=[]
    for axis,group in axes.items():
        fit_counts=Counter(group(r) for r in training if r['status']!='TIE');cal_counts=Counter(group(r) for r in calibration if r['status']!='TIE')
        buckets=defaultdict(list)
        for r,p in zip(test,predictions):buckets[group(r)].append((r,p))
        for value,pairs in sorted(buckets.items()):
            dec=[(r,p) for r,p in pairs if r['status']!='TIE'];selected=[(r,p) for r,p in pairs if p['direction']]
            brier=sum((p['p_up']-int(r['status']=='UP'))**2 for r,p in dec)/len(dec) if dec else None
            grouped.append(dict(axis=axis,value=value,train_decisive=fit_counts[value],calibration_decisive=cal_counts[value],
                test_samples=len(pairs),test_decisive=len(dec),selected=len(selected),brier_up=brier,
                selected_hypothetical_return=sum(p['hypothetical_return_at_82pct'] for _,p in selected)/len(selected) if selected else None,
                enough_samples_to_consider_separate_model=fit_counts[value]>=400 and cal_counts[value]>=100 and len(dec)>=150,
                scope='DESCRIPTIVE_ONLY_NOT_MODEL_SELECTION; sample counts alone do not qualify a submodel'))
    return result,predictions,grouped
