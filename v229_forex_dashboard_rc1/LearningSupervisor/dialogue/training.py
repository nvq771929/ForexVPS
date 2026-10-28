"""New-contract pre-lock training; never relabel an existing LOCK model."""
import copy
import json
from pathlib import Path
import time
from . import FEATURE_CONTRACT,MODEL_CONTRACT
from .dataset import DATASET
from .features import NAMES,CONTEXT_NAMES
from supervisor.store import digest,atomic
from supervisor.learning import split_rows,fit_network,probabilities,metrics,in_domain

def train(dataset,output):
    value=copy.deepcopy(dataset);h=value.pop('sha256',None)
    if h!=digest(value) or value['contract']!=DATASET or value['feature_contract']!=FEATURE_CONTRACT:raise ValueError('Pre-lock dataset receipt differs')
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    if dataset['broker_utc_offset_minutes'] is None:raise ValueError('Verify the entire training period broker UTC offset first')
    policies={digest(r['query']['query_policy']):r['query']['query_policy'] for r in dataset['rows']}
    if len(policies)>1:raise ValueError('Mixed query timing policies; use a separate research cohort')
    query_policy=next(iter(policies.values()),None)
    # Generic chronological splitter operates on tensors and clocks; no legacy data conversion.
    parts=split_rows(dataset)
    ids=[r['case']['signal_id'] for r in dataset['rows']]
    if len(ids)!=len(set(ids)):raise ValueError('Only one selected request per native episode may train')
    for r in dataset['rows']:
        c,q,l=r['case'],r['query'],r['label'];m=q['meta']
        if (c['feature_contract']!=FEATURE_CONTRACT or c['feature_asof_ms']!=m['observed_ms'] or
            c['features']!=q['feature']['features'] or c['context']!=q['feature']['context'] or
            not c['feature_asof_ms']<m['deadline_ms']<c['entry_ms']-31000 or
            (l['status'] in ('WIN','LOSS','TIE') and l['available_at_ms']<c['expiry_ms'])):
            raise ValueError('Invalid pre-lock feature/label chronology')
    identity=dict(origin=dataset['origin'],policy=dataset['policy'],feature_contract=FEATURE_CONTRACT,offset=dataset['broker_utc_offset_minutes'])
    bound=output/'identity.json'
    if bound.exists() and json.loads(bound.read_text())!=identity:raise ValueError('Model output belongs to another pre-lock cohort')
    if not bound.exists():atomic(bound,identity)
    experiments=output/'experiments';experiments.mkdir(exist_ok=True);existing=experiments/(h+'.json')
    if existing.exists():return json.loads(existing.read_text())
    old=[json.loads(p.read_text()) for p in experiments.glob('*.json')]
    newest=max(old,key=lambda r:r['created_utc_ms']) if old else None
    if newest:parts['evaluation']=[r for r in parts['evaluation'] if r['case']['entry_ms']>newest['evaluation_cutoff_ms']]
    counts={k:len(v) for k,v in parts.items()};minimum=dict(train=400,calibration=100,evaluation=150)
    result=dict(contract=MODEL_CONTRACT,feature_contract=FEATURE_CONTRACT,status='COLLECTING',counts=counts,
        deficits={k:max(0,minimum[k]-counts[k]) for k in counts},unique_episodes=len(ids),activation_allowed=False)
    if any(result['deficits'].values()):atomic(output/'training_status.json',result);return result
    now=time.time_ns()//1000000
    if newest and (now-newest['created_utc_ms']<604800000 or len(set(ids)-set(newest['sample_ids']))<50):
        result['status']='WAIT_NEW_DATA';atomic(output/'training_status.json',result);return result
    labels=[int(r['label']['status']=='WIN') for r in parts['train']]
    if min(sum(labels),len(labels)-sum(labels))<20:
        result['status']='INSUFFICIENT_CLASS_DIVERSITY';atomic(output/'training_status.json',result);return result
    cut=parts['train'][int(len(parts['train'])*.8)]['case']['entry_ms']
    inner=[r for r in parts['train'] if r['label']['available_at_ms']<cut-86400000]
    validation=[r for r in parts['train'] if r['case']['entry_ms']>=cut]
    cal_y=[int(r['label']['status']=='WIN') for r in parts['calibration']];candidates=[]
    for algorithm in ('LOGISTIC40','CAUSAL_TCN32_CONTEXT50'):
        epochs=80 if algorithm=='LOGISTIC40' else 8
        if algorithm!='LOGISTIC40' and len(inner)>=100 and len(validation)>=50:
            epochs=fit_network(inner,algorithm,8,validation)['selected_epoch']
        net=fit_network(parts['train'],algorithm,epochs)
        temperatures=[]
        for t in (.5,.75,1.,1.5,2.,3.):
            net['temperature']=t;temperatures.append((metrics(cal_y,probabilities(net,parts['calibration']))['log_loss'],t))
        net['temperature']=min(temperatures)[1]
        cal=metrics(cal_y,probabilities(net,parts['calibration']))
        candidates.append((cal['brier'],algorithm,net,cal))
    _,_,net,cal=min(candidates,key=lambda r:(r[0],r[1]))
    ev_y=[int(r['label']['status']=='WIN') for r in parts['evaluation']];p=probabilities(net,parts['evaluation'])
    prior=(sum(labels)+1)/(len(labels)+2);ev=metrics(ev_y,p);base=metrics(ev_y,[prior]*len(ev_y))
    selected=sum(prob>=.60 and in_domain(net,row['case']) for prob,row in zip(p,parts['evaluation']))
    weeks=len({r['case']['entry_ms']//604800000 for r in parts['evaluation']})
    offset=dataset['broker_utc_offset_minutes'];created=time.time_ns()//1000000
    cutoff=max(r['label']['available_at_ms'] for part in parts.values() for r in part)
    if cutoff-offset*60000>=created:raise ValueError('Historical/observed labels must precede model creation in verified UTC')
    model=dict(contract=MODEL_CONTRACT,feature_contract=FEATURE_CONTRACT,target='REQUEST_DIRECTION_MT4_WIN_VS_LOSS',
        feature_names=list(NAMES),context_names=list(CONTEXT_NAMES),
        training_origin=dataset['origin'],broker_utc_offset_minutes=offset,policy=dataset['policy'],dataset_sha256=h,
        query_policy=query_policy,
        created_utc_ms=created,trained_cutoff_utc_ms=cutoff-offset*60000,train_prior=prior,threshold=.60,network=net,
        calibration=cal,evaluation=ev,baseline=base,counts=counts,
        offline_review_passed=ev['brier']<base['brier'] and ev['log_loss']<base['log_loss'] and selected>=100 and weeks>=8 and selected/len(ev_y)>=.2,
        activation_allowed=False,independent_forward_validation_required=True)
    model['model_id']=digest(model);path=output/('prelock_model_'+model['model_id']+'.json');atomic(path,model)
    result.update(status='FROZEN_SHADOW',model_id=model['model_id'],model_file=str(path.resolve()),
        created_utc_ms=created,evaluation_cutoff_ms=cutoff,sample_ids=sorted(set(ids)),offline_review_passed=model['offline_review_passed'])
    atomic(existing,result);atomic(output/'training_status.json',result);return result
