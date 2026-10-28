"""Offline READY_AT_LOCK quality learner. Never exports a native execution filter."""
from collections import Counter,defaultdict
import gzip,hashlib,json,math,platform
import sklearn
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from .candidate_features import CONTRACT,NAMES,ANCHOR_NAMES
from .candidate_data import canonical,verify
from .demo_learning import atomic,csv_bytes,wilson,weekly_bounds
from .advanced_learning import paired_roi
from .progress import notify

PARAMETERS=dict(minimum_train=400,minimum_calibration=100,minimum_evaluation=150,minimum_selected=100,
    minimum_weeks=8,minimum_coverage=.2,threshold=.569450549451,assumed_payout=.82,stress_points=2,
    embargo_seconds=86400,logistic_C=.1,threads=2)


def summary(rows):
    counts=Counter(r['quality_status'] for r in rows);n=counts['FAVORABLE']+counts['ADVERSE'];lo,hi=wilson(counts['FAVORABLE'],n)
    return dict(samples=len(rows),decisive=n,status_counts=dict(counts),favorable_rate=counts['FAVORABLE']/n if n else None,wilson_lower=lo,wilson_upper=hi)


def split(snapshot):
    days=snapshot['calendar_days'];rr=snapshot['rows']
    if len(days)<10:return dict(train=[],calibration=[],evaluation=[]),dict(reason='Need at least 10 observed calendar days for a temporal split')
    cal=days[int(len(days)*.6)]*86400;test=days[int(len(days)*.8)]*86400
    registered=dict(train=[r for r in rr if r['entry_target']<cal-86400],
        calibration=[r for r in rr if cal<=r['entry_target']<test-86400],evaluation=[r for r in rr if r['entry_target']>=test])
    return registered,dict(calibration_start=cal,evaluation_start=test,embargo_seconds=86400,
        embargo_excluded=len(rr)-sum(len(x) for x in registered.values()))


def eligible(rows,cutoff):
    return [r for r in rows if r['ready_at_lock'] and r['features'] is not None and r['quality_status'] in ('FAVORABLE','ADVERSE','TIE')
        and r['available_at_ms'] is not None and r['available_at_ms']<cutoff and r['locked_at_ms'] is not None
        and r['analysis_start']*1000<=r['locked_at_ms']<=(r['entry_target']-31)*1000]


def fitted(rows,width):
    x=np.asarray([r['features'][:width] for r in rows]);y=[r['quality_status']=='FAVORABLE' for r in rows]
    scaler=StandardScaler().fit(x)
    estimator=LogisticRegression(C=.1,solver='lbfgs',max_iter=2000,tol=1e-8,class_weight=None)
    with threadpool_limits(limits=2):estimator.fit(np.clip(scaler.transform(x),-6,6),y)
    return dict(feature_count=width,feature_names=list(NAMES[:width]),mean=scaler.mean_.tolist(),scale=scaler.scale_.tolist(),
        weights=estimator.coef_[0].tolist(),intercept=float(estimator.intercept_[0]),
        low=x.min(axis=0).tolist(),high=x.max(axis=0).tolist())


def raw(model,rows):
    width=model['feature_count'];x=np.asarray([r['features'][:width] for r in rows])
    return np.clip((x-model['mean'])/model['scale'],-6,6)@np.asarray(model['weights'])+model['intercept']


def probabilities(scores,slope=1.,intercept=0.):return 1/(1+np.exp(-np.clip(slope*scores+intercept,-35,35)))


def domain(model,row):
    return all(lo-max(.25*(hi-lo),.25*s)<=x<=hi+max(.25*(hi-lo),.25*s)
        for x,lo,hi,s in zip(row['features'][:model['feature_count']],model['low'],model['high'],model['scale']))


def priors(train):
    prior=(sum(r['quality_status']=='FAVORABLE' for r in train)+1)/(len(train)+2);buckets=defaultdict(list)
    for r in train:buckets[(r['setup'],r['direction'])].append(r)
    groups={str(k[0])+':'+str(k[1]):(sum(r['quality_status']=='FAVORABLE' for r in rr)+20*prior)/(len(rr)+20) for k,rr in buckets.items()}
    return prior,groups


def evaluate(rows,p,allowed,prior,groups):
    sq=[];global_sq=[];group_sq=[];logs=[];global_logs=[];group_logs=[];selected=[];gains=[];predictions=[]
    for r,prob,permit in zip(rows,p,allowed):
        prob=float(prob);y=r['quality_status']=='FAVORABLE';group=groups.get(str(r['setup'])+':'+str(r['direction']),prior)
        take=bool(permit and prob>=PARAMETERS['threshold']);signed=r['signed_points']
        ret=0. if not signed else .82 if signed>0 else -1.
        if signed:
            sq.append((prob-y)**2);global_sq.append((prior-y)**2);group_sq.append((group-y)**2)
            loss=lambda v:-math.log(max(1e-12,v if y else 1-v))
            logs.append(loss(prob));global_logs.append(loss(prior));group_logs.append(loss(group))
        proxy=dict(entry_target=r['entry_target'],signed_points=signed,status='TIE' if not signed else 'WIN' if signed>0 else 'LOSS')
        if take:selected.append(proxy)
        gains.append((ret if take else 0)-(ret if group>=PARAMETERS['threshold'] else 0))
        predictions.append(dict(sample_id=r['sample_id'],feature_asof_ms=r['feature_asof_ms'],entry_target=r['entry_target'],
            p_favorable=prob,selected=take,in_domain=bool(permit),quality_status=r['quality_status'],
            source='RETROSPECTIVE_PRICE_RESEARCH',native_pre_outcome_prediction=False,is_execution_trade=False))
    avg=lambda x:sum(x)/len(x) if x else None
    n=sum(r['status']!='TIE' for r in selected);wins=sum(r['status']=='WIN' for r in selected);lo,_=wilson(wins,n)
    lower,_,weeks=weekly_bounds(selected)
    return dict(samples=len(rows),decisive=len(sq),selected=len(selected),selected_decisive=n,wins=wins,win_lower=lo,
        weeks=weeks,coverage=len(selected)/len(rows) if rows else 0,brier=avg(sq),global_brier=avg(global_sq),group_brier=avg(group_sq),
        log_loss=avg(logs),global_log_loss=avg(global_logs),group_log_loss=avg(group_logs),roi_lower=lower,
        stress_roi=avg([.82 if r['signed_points']>2 else -1. if r['signed_points']<2 else 0 for r in selected]),
        paired_gain_lower=paired_roi(rows,gains)),predictions


def gates(m):
    checks=dict(evaluation_samples=m['decisive']>=150,selected_samples=m['selected_decisive']>=100,weeks=m['weeks']>=8,
        coverage=m['coverage']>=.2,win_lower=m['win_lower']>PARAMETERS['threshold'],
        weekly_roi=m['roi_lower'] is not None and m['roi_lower']>0,stress=m['stress_roi'] is not None and m['stress_roi']>0,
        paired_gain=m['paired_gain_lower'] is not None and m['paired_gain_lower']>0,
        brier_global=m['brier'] is not None and m['brier']+.002<m['global_brier'],
        brier_group=m['brier'] is not None and m['brier']+.002<m['group_brier'],
        log_global=m['log_loss'] is not None and m['log_loss']<m['global_log_loss'],
        log_group=m['log_loss'] is not None and m['log_loss']<m['group_log_loss'])
    return [key for key,passed in checks.items() if not passed]


def train(snapshot,output,progress=None,rule_report=None):
    verify(snapshot)
    output=Path(output)
    if output.exists() and any(output.iterdir()):raise ValueError('Fresh candidate output required')
    registered,windows=split(snapshot)
    cal_cut=windows.get('calibration_start',0)*1000;eval_cut=windows.get('evaluation_start',0)*1000
    parts={name:eligible(rows,cal_cut if name=='train' else eval_cut if name=='calibration' else snapshot['asof_ms']) for name,rows in registered.items()}
    decisive=lambda rr:[r for r in rr if r['quality_status']!='TIE']
    tr,ca,ev=(decisive(parts[k]) for k in ('train','calibration','evaluation'))
    deficits={name:max(0,need-len(rr)) for name,need,rr in [('train',400,tr),('calibration',100,ca),('evaluation',150,ev)]}
    report=dict(schema=1,software_version='2.24',feature_contract=CONTRACT,status='COLLECTING',phase='COLLECTING',
        source_origin=snapshot['origin'],native_dataset_sha256=snapshot['native_dataset_sha256'],snapshot_sha256=snapshot['payload_sha256'],
        registered_candidates=len(snapshot['rows']),ready_at_lock=sum(r['ready_at_lock'] for r in snapshot['rows']),
        ready_mature_decisive=sum(r['ready_at_lock'] and r['features'] is not None and r['quality_status'] in ('FAVORABLE','ADVERSE') for r in snapshot['rows']),
        feature_unavailable=sum(r['features'] is None for r in snapshot['rows']),
        all_status_counts=dict(Counter(r['quality_status'] for r in snapshot['rows'])),
        windows=windows,cohorts={k:dict(registered=len(registered[k]),eligible=summary(parts[k])) for k in parts},deficits=deficits,
        parameters=PARAMETERS,model_fitted=False,model_import_allowed=False,eligible_for_native_filter=False,eligible_for_observe=False,
        native_forward_predictions=0,independent_confirmation_required=True,validation_scope='RETROSPECTIVE_EXPLORATION',
        decisions_changed=False,explanation='Ready at LOCK membership is outcome-blind; post-LOCK cancellations are not losses')
    report['setup_direction_counts']={name:{str(setup)+':'+str(direction):summary([r for r in parts[name] if r['setup']==setup and r['direction']==direction])
        for setup in (1,2,3) for direction in (-1,1)} for name in parts}
    report['calendar_days_observed']=len(snapshot['calendar_days'])
    report['quality_label_source']='MT4_BID_EXACT_BOUNDARY_PRICE_PROXY'
    report['payout_source']='ASSUMED_82_PERCENT_NOT_OLYMP_ACTUAL'
    output.mkdir(parents=True,exist_ok=True)
    atomic(output/'candidate_snapshot.json.gz',gzip.compress(canonical(snapshot),mtime=0))
    model=None;predictions=[]
    if not any(deficits.values()):
        if any(len({r['quality_status'] for r in rr})<2 for rr in (tr,ca)):
            report.update(status='REJECTED',phase='RESEARCH',failures=['Both classes required in each temporal partition'])
        else:
            days=sorted({r['entry_target']//86400 for r in tr});cut=days[int(len(days)*.8)]*86400
            inner=[r for r in tr if r['entry_target']<cut-86400 and r['available_at_ms']<cut*1000]
            selection=[r for r in tr if r['entry_target']>=cut]
            width=len(ANCHOR_NAMES);scores={}
            if len(inner)>=200 and len(selection)>=100 and len({r['quality_status'] for r in inner})==2:
                for n in (len(ANCHOR_NAMES),len(NAMES)):
                    trial=fitted(inner,n);p=probabilities(raw(trial,selection));y=np.asarray([r['quality_status']=='FAVORABLE' for r in selection])
                    scores[str(n)]=float(np.mean((p-y)**2))
                width=int(min(scores,key=lambda n:(scores[n],int(n))))
            notify(progress,'fit',detail='Pooled candidate Logistic; selection inside train only')
            model=fitted(tr,width);prior,groups=priors(tr)
            calibration=LogisticRegression(C=1.,solver='lbfgs',max_iter=1000,tol=1e-8)
            with threadpool_limits(limits=2):calibration.fit(raw(model,ca).reshape(-1,1),[r['quality_status']=='FAVORABLE' for r in ca])
            slope=float(calibration.coef_[0,0]);intercept=float(calibration.intercept_[0])
            model.update(calibration_slope=slope,calibration_intercept=intercept,global_prior=prior,group_priors=groups,
                inner_brier=scores,selection_scope='INNER_TRAIN_ONLY_OR_FIXED_ANCHOR_DEFAULT')
            probabilities_ev=probabilities(raw(model,parts['evaluation']),slope,intercept)
            metrics,predictions=evaluate(parts['evaluation'],probabilities_ev,[domain(model,r) for r in parts['evaluation']],prior,groups)
            failures=gates(metrics)+(['calibration_reverses_ranking'] if slope<=0 else [])
            if len({r['quality_status'] for r in ev})<2:failures.append('evaluation_single_class')
            slices=[];eval_days=sorted({r['entry_target']//86400 for r in parts['evaluation']})
            for i in range(3):
                days=set(eval_days[len(eval_days)*i//3:len(eval_days)*(i+1)//3]);rr=[r for r in parts['evaluation'] if r['entry_target']//86400 in days]
                if rr:
                    mm,_=evaluate(rr,probabilities(raw(model,rr),slope,intercept),[domain(model,r) for r in rr],prior,groups)
                    failed=mm['decisive']<50 or mm['selected_decisive']<30 or mm['brier'] is None or mm['brier']>=mm['global_brier'] or mm['stress_roi'] is None or mm['stress_roi']<=0
                else:mm={};failed=True
                slices.append(dict(slice=i+1,metrics=mm,failed=failed))
            if any(s['failed'] for s in slices):failures.append('chronological_slices')
            artifact=dict(schema=1,kind='V215_CANDIDATE_QUALITY_LOGISTIC',feature_contract=CONTRACT,policy=snapshot['policy'],
                source_origin=snapshot['origin'],snapshot_sha256=snapshot['payload_sha256'],model=model,
                training_windows=windows,partition_decisive={k:len(decisive(v)) for k,v in parts.items()},parameters=PARAMETERS,
                runtime=dict(python=platform.python_version(),numpy=np.__version__,scikit_learn=sklearn.__version__,
                    solver='lbfgs',stochastic_seed=None,threads=2,device='cpu'),
                phase='RESEARCH' if failures else 'FROZEN_CANDIDATE',model_import_allowed=False,eligible_for_native_filter=False,
                eligible_for_observe=False,forward_predictions=0,training_scope='RETROSPECTIVE_EXPLORATION')
            artifact['payload_sha256']=hashlib.sha256(canonical(artifact)).hexdigest()
            atomic(output/'candidate_model.json',canonical(artifact))
            report.update(model_fitted=True,status='RESEARCH_NOT_QUALIFIED' if failures else 'FROZEN_CANDIDATE',
                phase=artifact['phase'],metrics=metrics,heldout_slices=slices,failures=failures,
                model_sha256=artifact['payload_sha256'],model_file='candidate_model.json')
    report['report_sha256']=hashlib.sha256(canonical(report)).hexdigest()
    atomic(output/'candidate_report.json',canonical(report))
    atomic(output/'rule_diagnostics.json',canonical(rule_report or dict(status='UNAVAILABLE_OLD_SOURCE')))
    if predictions:atomic(output/'candidate_predictions.csv',csv_bytes(sorted(predictions[0]),predictions))
    return report
