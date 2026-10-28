"""Sparse, pre-LOCK candidate quality research, separate from generic UP prediction."""
from collections import Counter, defaultdict
import hashlib
import math
from .t1_corrected import NAMES
from .research_model import canonical, THRESHOLD
from .demo_learning import wilson

CONTRACT='V213_CANDIDATE_QUALITY_V1'
PARAMETERS=dict(prior_strength=20.,minimum_group_train=30,minimum_train=200,minimum_calibration=50,
                minimum_test=100,minimum_selected_test=30,threshold=THRESHOLD,assumed_payout=.82)


def candidates(rows):
    result=[]
    for r in rows:
        f=r['features'];d=int(f[NAMES.index('candidate_direction')])
        if not f[NAMES.index('candidate_present')]:continue
        setup=int(r.get('candidate_setup',0))
        if d not in (-1,1) or setup not in (1,2,3):raise ValueError('Invalid candidate-quality identity')
        if r['status'] not in ('UP','DOWN','TIE'):continue
        signed=d*r['signed_points']
        result.append(dict(r,quality_direction=d,quality_setup=setup,
            quality_status='FAVORABLE' if signed>0 else 'ADVERSE' if signed<0 else 'TIE',quality_signed_points=signed))
    return result


def summarize(rows):
    counts=Counter(r['quality_status'] for r in rows);n=counts['FAVORABLE']+counts['ADVERSE']
    lo,hi=wilson(counts['FAVORABLE'],n)
    return dict(samples=len(rows),decisive=n,favorable=counts['FAVORABLE'],adverse=counts['ADVERSE'],ties=counts['TIE'],
        favorable_rate=counts['FAVORABLE']/n if n else None,wilson_lower=lo,wilson_upper=hi,
        setups=dict(Counter(str(r['quality_setup']) for r in rows)))


def train(all_corrected,split_rows,native_digest):
    # Use exactly the context experiment's calendar windows, not a split
    # recomputed on the much sparser candidate days. All inputs are pre-LOCK.
    splits={}
    for name,rr in split_rows.items():
        if rr:
            first=min(r['entry_target'] for r in rr);last=max(r['entry_target'] for r in rr)
            chosen=[r for r in all_corrected if first<=r['entry_target']<=last and r['status'] in ('UP','DOWN','TIE')]
            if name=='train' and split_rows.get('calibration'):
                cutoff=min(r['locked_at_ms'] for r in split_rows['calibration'])
                chosen=[r for r in chosen if r['available_at_ms']<cutoff]
            if name=='calibration' and split_rows.get('test'):
                cutoff=min(r['locked_at_ms'] for r in split_rows['test'])
                chosen=[r for r in chosen if r['available_at_ms']<cutoff]
            splits[name]=candidates(chosen)
        else:splits[name]=[]
    tr=splits['train'];stats=summarize(tr);prior=(stats['favorable']+1)/(stats['decisive']+2)
    buckets=defaultdict(list)
    for r in tr:buckets[f"{r['quality_setup']}:{r['quality_direction']}"].append(r)
    groups={}
    for key,rr in sorted(buckets.items()):
        m=summarize(rr);m['p_win']=(m['favorable']+PARAMETERS['prior_strength']*prior)/(m['decisive']+PARAMETERS['prior_strength'])
        groups[key]=m
    predictions=[];metrics={}
    for name,rr in splits.items():
        brier=[];base=[];selected=[]
        for r in rr:
            key=f"{r['quality_setup']}:{r['quality_direction']}";g=groups.get(key)
            p=g['p_win'] if g else prior
            allowed=bool(g and g['decisive']>=PARAMETERS['minimum_group_train'] and g['wilson_lower']>THRESHOLD and p>=THRESHOLD)
            status=r['quality_status'];signed=r['quality_signed_points']
            ret=0. if status=='TIE' else .82 if status=='FAVORABLE' else -1.
            if status!='TIE':
                y=int(status=='FAVORABLE');brier.append((p-y)**2);base.append((prior-y)**2)
            row=dict(split=name,sample_id=r['sample_id'],entry_target=r['entry_target'],setup=r['quality_setup'],
                candidate_direction=r['quality_direction'],p_win=p,train_group_samples=g['decisive'] if g else 0,
                train_wilson_lower=g['wilson_lower'] if g else 0.,selected=allowed,quality_status=status,
                hypothetical_return=ret if allowed else 0.,stress_return=(0. if signed==2 else .82 if signed>2 else -1.) if allowed else 0.,
                is_execution_trade=False,independent_validation=False,source='BACKTEST_MT4_PRICE_RESEARCH')
            predictions.append(row)
            if allowed:selected.append(row)
        selected_dec=[r for r in selected if r['quality_status']!='TIE'];wins=sum(r['quality_status']=='FAVORABLE' for r in selected_dec)
        lo,_=wilson(wins,len(selected_dec))
        metrics[name]=dict(summarize(rr),brier_win=sum(brier)/len(brier) if brier else None,
            train_prior_baseline_brier=sum(base)/len(base) if base else None,selected=len(selected),selected_decisive=len(selected_dec),
            selected_favorable=wins,selected_win_lower=lo,
            hypothetical_roi=sum(r['hypothetical_return'] for r in selected)/len(selected) if selected else None,
            stress_roi=sum(r['stress_return'] for r in selected)/len(selected) if selected else None)
    failed=[]
    for name,minimum in [('train',200),('calibration',50),('test',100)]:
        if metrics[name]['decisive']<minimum:failed.append(name+'_samples')
    test=metrics['test']
    if test['selected_decisive']<30:failed.append('selected_test_samples')
    if test['selected_win_lower']<=THRESHOLD:failed.append('selected_win_lower')
    if test['hypothetical_roi'] is None or test['hypothetical_roi']<=0:failed.append('hypothetical_roi')
    if test['stress_roi'] is None or test['stress_roi']<=0:failed.append('stress_roi')
    if test['brier_win'] is None or test['brier_win']>=test['train_prior_baseline_brier']:failed.append('probability_quality')
    artifact=dict(schema=1,kind=CONTRACT,feature_contract=CONTRACT,label_source='BACKTEST_MT4_PRICE_RESEARCH',
        dataset_sha256=native_digest,eligible_for_live_filter=False,eligible_for_legacy_import=False,
        phase='OFFLINE_RESEARCH_ONLY',parameters=PARAMETERS,prior_win=prior,groups=groups,
        train_ids_sha256=hashlib.sha256(canonical([r['sample_id'] for r in tr])).hexdigest())
    artifact['payload_sha256']=hashlib.sha256(canonical(artifact)).hexdigest()
    report=dict(schema=1,feature_contract=CONTRACT,status='CANDIDATE_RESEARCH_NOT_QUALIFIED' if failed else 'CANDIDATE_OFFLINE_REVIEW_ONLY',
        source='BACKTEST_MT4_PRICE_RESEARCH',model='TRAIN_ONLY_BAYESIAN_SHRINKAGE_BY_SETUP_AND_DIRECTION',
        parameters=PARAMETERS,splits=metrics,train_groups=groups,failures=failed,
        calendar_windows='Same calendar windows as context experiment; candidate cohort need not have 32 anchors',
        outcome_meaning='Future Bid movement along the pre-LOCK candidate; includes canceled/unpublished candidates, not actual trading wins',
        model_import_allowed=False,automatic_filter=False,independent_confirmation_required=True,
        validation_scope='HISTORICAL_EXPLORATION',execution_trade_count=0)
    return report,predictions,artifact
