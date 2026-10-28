"""Frozen, calibrated logistic challenger for V207 manual demo signals.

Retrospective scores never grant activation. Only probabilities recorded by the
EA before entry can qualify a candidate in its subsequent forward cohort.
JSON/CSV only; no pickle, downloaded model, broker or external AI service.
"""
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

from .demo_learning import LOGIC,SOURCE,atomic,csv_bytes,payoff,wilson,weekly_bounds
from .signal_features import NAMES,VERSION
from .progress import notify

COLUMNS=['schema','source','logic','config_hash','feed_hash','policy_hash','asof','expires',
    'model_id','feature_version','active','threshold','intercept','index','mean','scale','weight','low','high','count']
THRESHOLD=round(1/1.82+.02,12)


def context(row):return f"{row['setup']}:{row['direction']}:{row['regime']}:{row['horizon']}"


def probability(model,x):
    if len(x)!=len(NAMES) or not all(math.isfinite(v) for v in x):raise ValueError('Invalid feature vector')
    z=model['intercept']+sum(w*max(-6,min(6,(v-m)/s)) for v,m,s,w in zip(x,model['mean'],model['scale'],model['weight']))
    return 1/(1+math.exp(-max(-35,min(35,z))))


def in_domain(model,x):
    for v,low,high,scale in zip(x,model['low'],model['high'],model['scale']):
        margin=max(.25*(high-low),.25*scale)
        if not low-margin<=v<=high+margin:return False
    return True


def decisive(rows):return [r for r in rows if r['status'] in ('WIN','LOSS')]


def split(rows):
    """Day blocks; purge labels not yet available at the next block's lock."""
    days=sorted({r['entry_target']//86400 for r in rows})
    if len(days)<10:return [],[],[]
    cal_day=days[int(len(days)*.6)];test_day=days[int(len(days)*.8)]
    calibration=[r for r in rows if cal_day<=r['entry_target']//86400<test_day]
    test=[r for r in rows if r['entry_target']//86400>=test_day]
    if not calibration or not test:return [],[],[]
    cal_lock=min(r['locked_at_ms'] for r in calibration);test_lock=min(r['locked_at_ms'] for r in test)
    training=[r for r in rows if r['entry_target']//86400<cal_day and r['available_at_ms']<cal_lock]
    calibration=[r for r in calibration if r['available_at_ms']<test_lock]
    return training,calibration,test


def paired_roi(rows,values):
    """Weekly paired gain per eligible opportunity, including WAIT as zero."""
    weeks=defaultdict(list)
    for r,v in zip(rows,values):
        day=r['entry_target']//86400;weeks[day-(day+3)%7].append(v)
    if len(weeks)<8:return None
    blocks=[(sum(v),len(v)) for v in weeks.values()];rng=random.Random(20401);samples=[]
    for _ in range(1500):
        chosen=rng.choices(blocks,k=len(blocks));samples.append(sum(v for v,n in chosen)/sum(n for v,n in chosen))
    return sorted(samples)[int(.025*len(samples))]


def evaluate(model,rows):
    all_p=[probability(model,r['features']) for r in rows]
    eligible=[in_domain(model,r['features']) for r in rows]
    selected=[r for r,p,ok in zip(rows,all_p,eligible) if ok and p>=THRESHOLD]
    chosen=[ok and p>=THRESHOLD for p,ok in zip(all_p,eligible)]
    dec=decisive(rows);wins=sum(r['status']=='WIN' for r in selected)
    n=len(decisive(selected));low,_=wilson(wins,n);roi_low,_,weeks=weekly_bounds(selected)
    errors=[];baseline=[];logloss=[];baseline_log=[]
    for r,p in zip(rows,all_p):
        if r['status']=='TIE':continue
        y=int(r['status']=='WIN');b=model['bayes'].get(context(r),model['bayes_global'])
        errors.append((p-y)**2);baseline.append((b-y)**2)
        logloss.append(-math.log(max(1e-12,p if y else 1-p)))
        baseline_log.append(-math.log(max(1e-12,b if y else 1-b)))
    gains=[(payoff(r) if take else 0)-payoff(r) for r,take in zip(rows,chosen)]
    return dict(samples=len(rows),decisive=len(dec),selected=len(selected),selected_decisive=n,
        selected_weeks=weeks,coverage=len(selected)/len(rows) if rows else 0,
        win_lower=low,roi_lower=roi_low,paired_gain_lower=paired_roi(rows,gains),
        stress_roi=statistics.mean(payoff(r,2) for r in selected) if selected else None,
        brier=statistics.mean(errors) if errors else None,bayes_brier=statistics.mean(baseline) if baseline else None,
        log_loss=statistics.mean(logloss) if logloss else None,bayes_log_loss=statistics.mean(baseline_log) if baseline_log else None)


def gates(metrics):
    checks=dict(samples=metrics['decisive']>=150,selected_samples=metrics['selected_decisive']>=100,
        weeks=metrics['selected_weeks']>=8,coverage=metrics['coverage']>=.2,
        profitable_lower=metrics['roi_lower'] is not None and metrics['roi_lower']>0,
        win_lower=metrics['win_lower']>THRESHOLD,
        stress=metrics['stress_roi'] is not None and metrics['stress_roi']>0,
        paired_gain=metrics['paired_gain_lower'] is not None and metrics['paired_gain_lower']>0,
        brier=metrics['brier'] is not None and metrics['brier']+.002<metrics['bayes_brier'],
        log_loss=metrics['log_loss'] is not None and metrics['log_loss']<metrics['bayes_log_loss'])
    return [name for name,ok in checks.items() if not ok]


def fit(rows,asof,progress=None):
    training,calibration,test=split(rows)
    notify(progress,'fit',detail=f'Train {len(decisive(training)):,} | calibration {len(decisive(calibration)):,} | test {len(decisive(test)):,}')
    if len(decisive(training))<400 or len(decisive(calibration))<100 or len(decisive(test))<150:
        return None,dict(status='COLLECTING',reason='Need 400 train / 100 calibration / 150 later decisive labels',
            train=len(decisive(training)),calibration=len(decisive(calibration)),test=len(decisive(test)))
    # Imports are local so the original Bayesian workflow remains usable alone.
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    tr=decisive(training);ca=decisive(calibration)
    if len({r['status'] for r in tr})<2 or len({r['status'] for r in ca})<2:
        return None,dict(status='COLLECTING',reason='Both classes required in training and calibration')
    x=np.asarray([r['features'] for r in tr],dtype=float)
    mean=x.mean(axis=0);scale=x.std(axis=0);scale[scale<1e-8]=1
    learner=LogisticRegression(C=.3,solver='lbfgs',max_iter=2000,tol=1e-8)
    learner.fit(np.clip((x-mean)/scale,-6,6),[r['status']=='WIN' for r in tr])
    notify(progress,'calibrate',detail=f'{len(ca):,} mau hieu chinh xac suat')
    raw=learner.decision_function(np.clip((np.asarray([r['features'] for r in ca])-mean)/scale,-6,6))
    calibrator=LogisticRegression(C=1.,solver='lbfgs',max_iter=1000,tol=1e-8)
    calibrator.fit(raw.reshape(-1,1),[r['status']=='WIN' for r in ca])
    slope=float(calibrator.coef_[0,0])
    if slope<=0:return None,dict(status='REJECTED',reason='Calibration reverses learned ranking')
    grouped=defaultdict(list)
    for r in tr:grouped[context(r)].append(r)
    bayes={k:(sum(r['status']=='WIN' for r in v)+1)/(len(v)+2) for k,v in grouped.items()}
    model=dict(feature_version=VERSION,created=asof,model_id=asof*1000+901,phase='OBSERVE',active_since=0,
        mean=mean.tolist(),scale=scale.tolist(),weight=(slope*learner.coef_[0]).tolist(),
        intercept=slope*float(learner.intercept_[0])+float(calibrator.intercept_[0]),
        low=x.min(axis=0).tolist(),high=x.max(axis=0).tolist(),bayes=bayes,
        bayes_global=(sum(r['status']=='WIN' for r in tr)+1)/(len(tr)+2),
        fit_cutoff=max(r['available_at_ms'] for r in training),
        calibration_cutoff=max(r['available_at_ms'] for r in calibration),
        test_lock_start=min(r['locked_at_ms'] for r in test),
        training_rows=len(tr),calibration_rows=len(ca),test_rows=len(test))
    # Freeze the exact decimal representation that the native reader receives.
    for key in ('mean','scale','weight','low','high'):
        model[key]=[round(v,12) for v in model[key]]
    model['intercept']=round(model['intercept'],12)
    notify(progress,'evaluate',detail=f'{len(test):,} mau kiem dinh; bao gom bootstrap theo tuan')
    model['offline']=evaluate(model,test);model['offline_failures']=gates(model['offline'])
    # A fixed, documented feature set and C; no random folds or threshold sweep.
    model['training_digest']=hashlib.sha256(json.dumps(rows,sort_keys=True,allow_nan=False).encode()).hexdigest()
    return model,dict(status='OBSERVE',reason='Candidate frozen; require forecasts recorded before new outcomes')


def validate(model):
    required=('feature_version','created','model_id','phase','active_since','mean','scale','weight','low','high',
        'intercept','bayes','bayes_global','offline','offline_failures','training_rows','calibration_rows','test_rows')
    if not isinstance(model,dict) or any(k not in model for k in required):raise ValueError('Truncated advanced state')
    if not all(isinstance(model[k],int) and model[k]>=0 for k in ('created','model_id','active_since','training_rows','calibration_rows','test_rows')):
        raise ValueError('Invalid advanced state counters')
    if not isinstance(model['offline_failures'],list) or not isinstance(model['bayes'],dict):raise ValueError('Invalid advanced state metadata')
    if model.get('feature_version')!=VERSION or model.get('phase') not in ('OBSERVE','ACTIVE','SUSPENDED'):
        raise ValueError('Unsupported advanced state')
    for key in ('mean','scale','weight','low','high'):
        v=model.get(key)
        if not isinstance(v,list) or len(v)!=len(NAMES) or not all(isinstance(x,(int,float)) and math.isfinite(x) and abs(x)<1e6 for x in v):
            raise ValueError('Invalid advanced parameters')
    if any(v<=0 for v in model['scale']) or any(a>b for a,b in zip(model['low'],model['high'])):
        raise ValueError('Invalid advanced domain')
    if not isinstance(model['intercept'],(int,float)) or not math.isfinite(model['intercept']) or abs(model['intercept'])>1000:raise ValueError('Invalid intercept')
    if not 0<model['model_id']<=model['created']*1000+999:raise ValueError('Invalid model ID')
    if not 0<model['bayes_global']<1 or not all(0<p<1 for p in model['bayes'].values()):raise ValueError('Invalid baseline')


def forward(model,rows):
    result=[]
    for r in rows:
        # Reconstruction is only an integrity check. Qualification requires the
        # model ID AND probability actually recorded in the immutable LOCK.
        if r['model_id']!=model['model_id'] or r['locked_at_ms']<=model['created']*1000:continue
        if not in_domain(model,r['features']):raise ValueError('Native forecast outside trained domain')
        if abs(r['locked_probability']-probability(model,r['features']))>2e-6:
            raise ValueError('Native/Python advanced forecast mismatch')
        result.append(r)
    return result


def export(source,p,asof,model):
    common=dict(schema=1,source=SOURCE,logic=LOGIC,config_hash=p['config_hash'],feed_hash=p['feed_hash'],
        policy_hash=p['policy_hash'],asof=asof,expires=asof+86400,model_id=model['model_id'],feature_version=VERSION,
        active=int(model['phase']=='ACTIVE'),threshold=f'{THRESHOLD:.12f}',intercept=f"{model['intercept']:.12f}",count=len(NAMES))
    rows=[dict(common,index=-1,mean='0',scale='1',weight='0',low='0',high='0')]
    for i in range(len(NAMES)):
        row=dict(common,index=i)
        for key in ('mean','scale','weight','low','high'):row[key]=f'{model[key][i]:.12f}'
        rows.append(row)
    atomic(Path(source)/'advanced_model_v207.csv',csv_bytes(COLUMNS,rows))


def update(source,snapshot):
    if snapshot.get('origin','LIVE_MT4')!='LIVE_MT4':raise ValueError('Tester records cannot qualify a live forward model')
    source=Path(source);p=snapshot['policy'];asof=snapshot['asof'];state_path=source/'advanced_state_v207.json'
    identity={k:p[k] for k in ('logic','config_hash','feed_hash','policy_hash','horizon')}
    rows=sorted([r for r in snapshot['references'] if r['status'] in ('WIN','LOSS','TIE')
        and r['available_at_ms']<asof*1000 and 'features' in r],key=lambda r:r['entry_target'])
    if state_path.is_file():
        state=json.loads(state_path.read_text())
        if not isinstance(state,dict) or state.get('schema')!=1 or state.get('identity')!=identity or not isinstance(state.get('last_asof'),int) or state['last_asof']>asof or 'model' not in state or not isinstance(state.get('last_attempt_day'),int):
            raise ValueError('Advanced state identity/time mismatch')
    else:
        if (source/'advanced_model_v207.csv').is_file() or (source/'advanced_seen.csv').is_file():
            raise ValueError('Advanced state missing; preserve evidence rather than silently reset')
        state=dict(schema=1,identity=identity,model=None,last_asof=0,last_attempt_day=-1)
    model=state['model'];day=asof//86400
    if model:
        validate(model)
        if model['created']>asof:raise ValueError('Future advanced state')
    # A candidate remains frozen through genuine forward observation. It is not
    # refitted every 30 seconds, which would repeatedly reset its forward test.
    can_fit=model is None or (model['phase']=='SUSPENDED' and asof-model.get('suspended_at',asof)>=7*86400)
    info=dict(status='COLLECTING',reason='Waiting for chronological sample sizes')
    if can_fit and state['last_attempt_day']!=day:
        candidate,info=fit(rows,asof);state['last_attempt_day']=day
        if candidate:
            if model:
                atomic(source/f"advanced_archive_{model['model_id']}.json",(json.dumps(model,indent=2,allow_nan=False)+'\n').encode())
            state['model']=model=candidate
    if model:
        validate(model);observed=forward(model,rows);metrics=evaluate(model,observed);failures=gates(metrics)
        if model['phase']=='OBSERVE' and not model['offline_failures'] and not failures:
            model['phase']='ACTIVE';model['active_since']=asof
        elif model['phase']=='OBSERVE' and len(decisive(observed))>=300 and weekly_bounds(observed)[2]>=8 and (failures or model['offline_failures']):
            model['phase']='SUSPENDED';model['suspended_at']=asof;model['suspension_reason']='Failed frozen forward test'
        if model['phase']=='ACTIVE':
            recent=[r for r in observed if r['locked_at_ms']>model['active_since']*1000][-200:]
            if len(decisive(recent))>=100:
                rm=evaluate(model,recent)
                if rm['brier']>rm['bayes_brier']+.01 or (rm['selected_decisive']>=30 and rm['stress_roi']<=0):
                    model['phase']='SUSPENDED';model['suspended_at']=asof;model['suspension_reason']='Recent forward deterioration'
        info=dict(status=model['phase'],model_id=model['model_id'],created=model['created'],training_origin=model.get('training_origin','LIVE_MT4'),
            offline=model['offline'],offline_failures=model['offline_failures'],forward=metrics,forward_failures=failures,
            features=list(NAMES),training_rows=model['training_rows'],calibration_rows=model['calibration_rows'],
            test_rows=model['test_rows'],native_forecasts=len(observed),active_since=model['active_since'])
    state['last_asof']=asof
    atomic(state_path,(json.dumps(state,indent=2,allow_nan=False)+'\n').encode())
    info.update(source=SOURCE,automatic_broker_orders=False,production_promoted=False,
        comparison='Frozen training-only Bayesian probabilities; filtered vs unfiltered fixed reference opportunities',
        limits=['Forward gates are exploratory demo criteria; not an untouched production-performance certificate.',
            'Rolling candidate attempts reuse history; failed attempts are retained in the archived state history.',
            'Filter only removes otherwise eligible signals; it never changes direction or structural/quote guards.'])
    atomic(source/'advanced_report_v207.json',(json.dumps(info,indent=2,allow_nan=False)+'\n').encode())
    if model:export(source,p,asof,model)
    return info
