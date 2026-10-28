"""Frozen research classifiers; hypothetical returns never grant execution rights."""
from collections import Counter,defaultdict
import hashlib
import json
import math

from .advanced_learning import THRESHOLD,paired_roi
from .demo_learning import weekly_bounds,wilson,payoff
from .research_features import CONTRACT,NAMES
from .t1_features import CONTRACT as T1_CONTRACT,NAMES as T1_NAMES
from .t1_corrected import CONTRACT as T1_V2_CONTRACT,NAMES as T1_V2_NAMES,KEY as T1_V2_KEY
CONTRACTS={CONTRACT:NAMES,T1_CONTRACT:T1_NAMES,T1_V2_CONTRACT:T1_V2_NAMES}
from .progress import notify

KIND='V210_RESEARCH_UP_LOGISTIC_OR_HGB'
EMBARGO=86400
PARAMETERS=dict(logistic_C=.3,hgb_iterations=120,hgb_learning_rate=.05,hgb_leaf_nodes=15,
    hgb_min_samples_leaf=50,hgb_l2=1.,inner_day_fraction=.8,embargo_seconds=EMBARGO,
    threshold=THRESHOLD,assumed_payout=.82,stress_points=2,threads=2,random_state=210)


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def split(rows,fraction=.6,test_fraction=.8):
    days=sorted({r['entry_target']//86400 for r in rows})
    if len(days)<10:return [],[],[]
    cal=days[int(len(days)*fraction)]*86400;test=days[int(len(days)*test_fraction)]*86400
    calibration=[r for r in rows if cal<=r['entry_target']<test-EMBARGO]
    heldout=[r for r in rows if r['entry_target']>=test]
    if not calibration or not heldout:return [],[],[]
    cal_lock=min(r['locked_at_ms'] for r in calibration);test_lock=min(r['locked_at_ms'] for r in heldout)
    training=[r for r in rows if r['entry_target']<cal-EMBARGO and r['available_at_ms']<cal_lock]
    calibration=[r for r in calibration if r['available_at_ms']<test_lock]
    return training,calibration,heldout


def decisive(rows):return [r for r in rows if r['status'] in ('UP','DOWN')]


def direction(p):return 1 if p>=THRESHOLD else -1 if p<=1-THRESHOLD else 0


def _fit_classifier(rows,algorithm):
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import HistGradientBoostingClassifier
    x=np.asarray([r['features'] for r in rows],dtype=float);y=[r['status']=='UP' for r in rows]
    mean=x.mean(axis=0);scale=x.std(axis=0);scale[scale<1e-8]=1
    if len(rows[0]['features'])==len(T1_V2_NAMES):
        from .preprocessing import binary_indices
        binary=binary_indices(T1_V2_NAMES);mean[binary]=0.;scale[binary]=1.
    if algorithm=='logistic':
        estimator=LogisticRegression(C=.3,solver='lbfgs',max_iter=2000,tol=1e-8)
        estimator.fit(np.clip((x-mean)/scale,-6,6),y)
    else:
        estimator=HistGradientBoostingClassifier(max_iter=120,learning_rate=.05,max_leaf_nodes=15,
            min_samples_leaf=50,l2_regularization=1.,early_stopping=False,random_state=210)
        estimator.fit(x,y)
    return estimator,mean,scale


def _raw(estimator,algorithm,x,mean,scale):
    import numpy as np
    if algorithm=='logistic':return estimator.decision_function(np.clip((x-mean)/scale,-6,6))
    return estimator._raw_predict(x).reshape(-1)


def export_classifier(estimator,algorithm,mean,scale):
    base=dict(algorithm=algorithm,mean=list(map(float,mean)),scale=list(map(float,scale)))
    if algorithm=='logistic':
        base.update(intercept=float(estimator.intercept_[0]),weight=estimator.coef_[0].astype(float).tolist())
    else:
        trees=[]
        for iteration in estimator._predictors:
            if len(iteration)!=1:raise ValueError('Research HGB must be binary')
            nodes=[]
            for n in iteration[0].nodes:
                if n['is_categorical']:raise ValueError('Categorical trees are not supported')
                nodes.append(dict(leaf=bool(n['is_leaf']),value=float(n['value']),feature=int(n['feature_idx']),
                    threshold=float(n['num_threshold']),left=int(n['left']),right=int(n['right'])))
            trees.append(nodes)
        base.update(intercept=float(estimator._baseline_prediction[0,0]),trees=trees)
    return base


def raw_score(model,x):
    if len(x)!=len(model.get('feature_names',NAMES)) or not all(math.isfinite(v) for v in x):raise ValueError('Invalid research vector')
    value=model['intercept']
    if model['algorithm']=='logistic':
        return value+sum(w*max(-6,min(6,(v-m)/s)) for v,m,s,w in zip(x,model['mean'],model['scale'],model['weight']))
    for tree in model['trees']:
        index=0
        for _ in range(len(tree)):
            n=tree[index]
            if n['leaf']:value+=n['value'];break
            index=n['left'] if x[n['feature']]<=n['threshold'] else n['right']
        else:raise ValueError('Research tree contains a cycle')
    return value


def probability(model,x):
    z=model['calibration_slope']*raw_score(model,x)+model['calibration_intercept']
    return 1/(1+math.exp(-max(-35,min(35,z))))


def in_domain(model,x):
    return all(lo-max(.25*(hi-lo),.25*s)<=v<=hi+max(.25*(hi-lo),.25*s)
        for v,lo,hi,s in zip(x,model['low'],model['high'],model['scale']))


def evaluate(model,rows):
    selected=[];predictions=[];briers=[];logs=[];global_briers=[];regime_briers=[];global_logs=[];regime_logs=[];gains=[]
    for r in rows:
        p=probability(model,r['features']);allowed=in_domain(model,r['features']);d=direction(p) if allowed else 0
        prior=model['baseline_global'];regime=model['baseline_by_regime'].get(str(r['regime']),prior)
        baseline_direction=direction(regime);move=r['signed_points'];ret=0.;base_return=0.
        if d:
            proxy=dict(entry_target=r['entry_target'],signed_points=d*move,
                status='TIE' if move==0 else 'WIN' if d*move>0 else 'LOSS')
            selected.append(proxy);ret=payoff(proxy)
        if baseline_direction:
            base_return=0. if move==0 else .82 if baseline_direction*move>0 else -1.
        gains.append(ret-base_return)
        if r['status']!='TIE':
            y=int(r['status']=='UP')
            briers.append((p-y)**2);global_briers.append((prior-y)**2);regime_briers.append((regime-y)**2)
            loss=lambda q:-math.log(max(1e-12,q if y else 1-q))
            logs.append(loss(p));global_logs.append(loss(prior));regime_logs.append(loss(regime))
        predictions.append(dict(source='BACKTEST_RESEARCH_OOS',is_execution_trade=False,
            native_pre_outcome_prediction=False,independent_validation=False,evaluation_scope='HISTORICAL_EXPLORATION',sample_id=r['sample_id'],entry_target=r['entry_target'],
            status=r['status'],p_up=p,direction=d,in_domain=allowed,signed_points=move,
            hypothetical_return_at_82pct=ret,regime=r['regime'],
            candidate_setup=r.get('candidate_setup'),broker_hour=(r['entry_target']%86400)//3600,
            rejection_reason='SELECTED' if d else 'BOTH' if not allowed and not direction(p) else 'OUT_OF_DOMAIN' if not allowed else 'LOW_CONFIDENCE'))
    avg=lambda values:sum(values)/len(values) if values else None
    n=sum(r['status']!='TIE' for r in selected);wins=sum(r['status']=='WIN' for r in selected)
    low,_=wilson(wins,n);roi_low,_,weeks=weekly_bounds(selected)
    metrics=dict(samples=len(rows),decisive=len(decisive(rows)),selected=len(selected),selected_decisive=n,
        selected_weeks=weeks,coverage=len(selected)/len(rows) if rows else 0.,hypothetical_wins=wins,
        hypothetical_ties=sum(r['status']=='TIE' for r in selected),win_lower=low,
        hypothetical_roi=avg([payoff(r) for r in selected]),roi_lower=roi_low,
        stress_roi=avg([payoff(r,2) for r in selected]),paired_gain_lower=paired_roi(rows,gains),
        brier_up=avg(briers),global_baseline_brier=avg(global_briers),regime_baseline_brier=avg(regime_briers),
        log_loss_up=avg(logs),global_baseline_log_loss=avg(global_logs),regime_baseline_log_loss=avg(regime_logs),
        metric_scope='Historical price-direction research, hypothetical payout 82%; not execution/forward performance')
    return metrics,predictions


def gates(m):
    better=lambda a,b,margin=0:a is not None and b is not None and a+margin<b
    checks=dict(samples=m['decisive']>=150,selected_samples=m['selected_decisive']>=100,
        weeks=m['selected_weeks']>=8,coverage=m['coverage']>=.2,win_lower=m['win_lower']>THRESHOLD,
        hypothetical_roi_lower=m['roi_lower'] is not None and m['roi_lower']>0,
        stress=m['stress_roi'] is not None and m['stress_roi']>0,
        paired_gain=m['paired_gain_lower'] is not None and m['paired_gain_lower']>0,
        brier_global=better(m['brier_up'],m['global_baseline_brier'],.002),
        brier_regime=better(m['brier_up'],m['regime_baseline_brier'],.002),
        log_loss_global=better(m['log_loss_up'],m['global_baseline_log_loss']),
        log_loss_regime=better(m['log_loss_up'],m['regime_baseline_log_loss']))
    return [name for name,passed in checks.items() if not passed]


def _fit(rows,asof,progress,contract=CONTRACT):
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    training,calibration,test=split(rows);tr=decisive(training);ca=decisive(calibration)
    counts=dict(train=len(tr),calibration=len(ca),test=len(decisive(test)),embargo_seconds=EMBARGO)
    notify(progress,'fit',detail=f"NGHIEN CUU: train {counts['train']:,} | calibration {counts['calibration']:,} | test {counts['test']:,}")
    if len(tr)<400 or len(ca)<100 or counts['test']<150:
        return None,dict(counts,status='COLLECTING',reason='Need 400 train / 100 calibration / 150 test decisive research labels'),[],[]
    if len({r['status'] for r in tr})<2 or len({r['status'] for r in ca})<2:
        return None,dict(counts,status='REJECTED',reason='Both directions required in train and calibration'),[],[]
    days=sorted({r['entry_target']//86400 for r in tr});cut=days[int(len(days)*.8)]*86400
    inner_select=[r for r in tr if r['entry_target']>=cut]
    first_lock=min((r['locked_at_ms'] for r in inner_select),default=0)
    inner_train=[r for r in tr if r['entry_target']<cut-EMBARGO and r['available_at_ms']<first_lock]
    selection=dict(method='fixed_logistic_small_inner_sample',scores={},inner_train=len(inner_train),inner_selection=len(inner_select))
    algorithm='logistic'
    if (len(inner_train)>=200 and len(inner_select)>=100 and len({r['status'] for r in inner_train})==2):
        x=np.asarray([r['features'] for r in inner_select],dtype=float);y=np.asarray([r['status']=='UP' for r in inner_select])
        for name in ('logistic','hgb'):
            notify(progress,'fit',detail='NGHIEN CUU: inner chronological selection '+name)
            estimator,mean,scale=_fit_classifier(inner_train,name)
            raw=_raw(estimator,name,x,mean,scale);prob=1/(1+np.exp(-np.clip(raw,-35,35)))
            selection['scores'][name]=float(np.mean((prob-y)**2))
        algorithm=min(selection['scores'],key=lambda name:(selection['scores'][name],name!='logistic'))
        selection['method']='inner_chronological_brier_before_calibration_and_test'
    notify(progress,'fit',detail='NGHIEN CUU: refit '+algorithm+' on outer train only')
    estimator,mean,scale=_fit_classifier(tr,algorithm);model=export_classifier(estimator,algorithm,mean,scale)
    model.update(feature_names=list(CONTRACTS[contract]),feature_contract=contract)
    x=np.asarray([r['features'] for r in tr],dtype=float)
    model.update(low=x.min(axis=0).tolist(),high=x.max(axis=0).tolist(),selection=selection)
    # Check the data-only exporter against the fitted sklearn raw predictions.
    probe=x[:min(len(x),128)];expected=_raw(estimator,algorithm,probe,mean,scale)
    if max(abs(raw_score(model,row.tolist())-float(v)) for row,v in zip(probe,expected))>1e-9:
        raise ValueError('Research model export differs from sklearn')
    notify(progress,'calibrate',detail='NGHIEN CUU: separate chronological Platt calibration')
    raw=_raw(estimator,algorithm,np.asarray([r['features'] for r in ca]),mean,scale)
    calibrator=LogisticRegression(C=1.,solver='lbfgs',max_iter=1000,tol=1e-8)
    calibrator.fit(raw.reshape(-1,1),[r['status']=='UP' for r in ca])
    slope=float(calibrator.coef_[0,0])
    if slope<=0:return None,dict(counts,status='REJECTED',reason='Calibration reverses research ranking',selection=selection),[],[]
    prior=(sum(r['status']=='UP' for r in tr)+1)/(len(tr)+2);grouped=defaultdict(list)
    for r in tr:grouped[str(r['regime'])].append(r)
    model.update(calibration_slope=slope,calibration_intercept=float(calibrator.intercept_[0]),
        baseline_global=prior,baseline_by_regime={k:(sum(r['status']=='UP' for r in v)+10*prior)/(len(v)+10) for k,v in grouped.items()},
        created=asof,model_id=asof*1000+(213 if contract==T1_V2_CONTRACT else 211 if contract==T1_CONTRACT else 210),feature_contract=contract,phase='OFFLINE_RESEARCH_ONLY',
        split_counts=counts,train_first=tr[0]['entry_target'],train_last=tr[-1]['entry_target'],
        calibration_first=ca[0]['entry_target'],calibration_last=ca[-1]['entry_target'],
        test_first=test[0]['entry_target'],test_last=test[-1]['entry_target'],parameters=PARAMETERS,
        training_digest=hashlib.sha256(canonical(rows)).hexdigest())
    notify(progress,'evaluate',detail='NGHIEN CUU: untouched test vs frozen global and regime baselines')
    metrics,predictions=evaluate(model,test);model['offline']=metrics;model['offline_failures']=gates(metrics)
    test_days=sorted({r['entry_target']//86400 for r in test});slices=[]
    notify(progress,'holdouts',done=0,total=3,unit='doan',detail='NGHIEN CUU: same frozen classifier on three chronological slices')
    for i in range(3):
        block=set(test_days[len(test_days)*i//3:len(test_days)*(i+1)//3])
        m,_=evaluate(model,[r for r in test if r['entry_target']//86400 in block]);failed=[]
        if m['decisive']<50:failed.append('samples')
        if m['selected_decisive']<30:failed.append('selected_samples')
        if m['brier_up'] is None or m['brier_up']>=min(m['global_baseline_brier'],m['regime_baseline_brier']):failed.append('probability_quality')
        if m['stress_roi'] is None or m['stress_roi']<=0:failed.append('stress_roi')
        slices.append(dict(slice=i+1,metrics=m,failures=failed))
        notify(progress,'holdouts',done=i+1,total=3,unit='doan')
    return model,dict(counts,status='FITTED',algorithm=algorithm,selection=selection),slices,predictions


def train(snapshot,digest,progress=None,*,research_key='research'):
    if snapshot.get('origin')!='BACKTEST_MT4':raise ValueError('Research history requires BACKTEST_MT4')
    all_rows=snapshot.get(research_key,[])
    contract=T1_V2_CONTRACT if research_key==T1_V2_KEY else T1_CONTRACT if research_key=='research_t1' else CONTRACT
    names=CONTRACTS[contract]
    if any(r.get('source')!='BACKTEST_MT4_PRICE_RESEARCH' or r.get('is_execution_trade') is not False or r.get('cohort')!=contract for r in all_rows):
        raise ValueError('Research cohort/source mixed with execution or live data')
    data=sorted((r for r in all_rows if r['status'] in ('UP','DOWN','TIE') and r['available_at_ms']<snapshot['asof']*1000),key=lambda r:r['entry_target'])
    for r in data:
        if not (len(r['features'])==len(names) and all(math.isfinite(v) for v in r['features'])):
            raise ValueError('Invalid research features')
        if not r['feature_asof_ms']<=r['locked_at_ms']<r['entry_observed_ms']<r['exit_observed_ms']<r['available_at_ms']:
            raise ValueError('Research features or labels cross forecast time')
    if data:
        from threadpoolctl import threadpool_limits
        with threadpool_limits(limits=2):model,info,slices,predictions=_fit(data,snapshot['asof'],progress,contract)
    else:model,info,slices,predictions=None,dict(status='COLLECTING',reason='No closed research price labels',train=0,calibration=0,test=0),[],[]
    failures=list(model['offline_failures']) if model else ['insufficient_or_unusable_research_data']
    if any(s['failures'] for s in slices):failures.append('chronological_holdout_slices')
    qualified=bool(model is not None and not failures)
    status='RESEARCH_QUALIFIED_OFFLINE' if qualified else 'RESEARCH_TRAINED_NOT_QUALIFIED' if model else 'RESEARCH_NOT_TRAINED'
    artifact=dict(schema=1,kind=KIND if contract==CONTRACT else 'V213_T1_RESEARCH_UP_LOGISTIC_OR_HGB' if contract==T1_V2_CONTRACT else 'V211_T1_RESEARCH_UP_LOGISTIC_OR_HGB',feature_contract=contract,feature_names=list(names),logic=snapshot['policy']['logic'],
        source_origin='BACKTEST_MT4',label_source='BACKTEST_MT4_PRICE_RESEARCH',policy=snapshot['policy'],
        history_asof=snapshot['asof'],dataset_sha256=digest,validation_scope='HISTORICAL_EXPLORATION',independent_confirmation_required=True,tick_provenance='MT4_TESTER_MODEL_UNVERIFIED',
        status=status,eligible_for_research_review=qualified,eligible_for_legacy_import=False,
        eligible_for_live_filter=False,production_promoted=False,model=model,failures=failures,heldout_slices=slices)
    artifact['payload_sha256']=hashlib.sha256(canonical(artifact)).hexdigest()
    report=dict(status=status,source='BACKTEST_MT4_PRICE_RESEARCH',eligible_labels=len(data),
        counts=dict(Counter(r['status'] for r in all_rows)),fit=info,failures=failures,heldout_slices=slices,
        offline=model['offline'] if model else None,algorithm=model['algorithm'] if model else None,
        dataset_sha256=digest,execution_trade_count=0,live_forward_observations=0,automatic_live_filter=False,
        feature_contract=contract,feature_names=list(names),validation_scope='HISTORICAL_EXPLORATION',independent_confirmation_required=True,
        limitations=['Research UP/DOWN/TIE labels and hypothetical returns are not execution WIN/LOSS.',
            'A qualified offline research model is for review; it cannot be imported into the R10 execution filter.',
            'Features are observed before LOCK/entry under the stated contract; WAIT/canceled rows remain price research.',
            'MT4 modeled ticks and fixed 82% hypothetical payout do not establish Olymp settlement or an edge.'])
    return artifact,report,predictions
