"""Separate-process batch fitting and frozen, JSON-only shadow model artifacts.

Targets are official-signal MT4 WIN/LOSS. No stakes, user trades, payout or
post-entry features enter the models. This module has no EA write interface.
"""
import copy
import json
import math
from pathlib import Path
import time
from .audit import DATASET
from .collector import FEATURE_CONTRACT
from .store import canonical, digest, atomic

MODEL_CONTRACT='V224_OFFICIAL_SIGNAL_SHADOW_MODEL_V1'
MINIMUM=dict(train=400,calibration=100,evaluation=150)
THRESHOLD=.60
EMBARGO_MS=86400000

def metrics(y,p):
    if not y: return None
    p=[max(1e-7,min(1-1e-7,float(v))) for v in p]
    return dict(samples=len(y),brier=sum((a-b)**2 for a,b in zip(y,p))/len(y),
        log_loss=-sum(a*math.log(b)+(1-a)*math.log(1-b) for a,b in zip(y,p))/len(y))

def verify_dataset(value):
    value=copy.deepcopy(value);h=value.pop('sha256',None)
    if h!=digest(value) or value.get('contract')!=DATASET:raise ValueError('Audited dataset checksum/contract differs')
    if value['origin'] not in ('LIVE_MT4','BACKTEST_MT4'):raise ValueError('Invalid dataset origin')
    seen=set()
    for r in value['rows']:
        c,l=r['case'],r['label'];sid=c['signal_id']
        if sid in seen or sid!=l['signal_id']:raise ValueError('Duplicate/mismatched label')
        seen.add(sid)
        if c['origin']!=value['origin'] or c['policy']!=value['policy'] or c['feature_contract']!=FEATURE_CONTRACT:
            raise ValueError('Mixed data identity')
        if (c['feature_asof_ms']>c['published_ms'] or c['published_ms']>c['entry_ms']-31000 or
            l['available_at_ms']<c['expiry_ms'] or c['expiry_ms']!=c['entry_ms']+c['horizon']*300000):
            raise ValueError('Noncausal sample clock')
        if c['feature_hash']!=digest({k:c[k] for k in ('features','context','sequence32','feature_asof_ms')}):
            raise ValueError('Feature receipt differs')
    value['sha256']=h
    return value

def split_rows(dataset):
    rows=sorted([r for r in dataset['rows'] if r['label']['status'] in ('WIN','LOSS') and
        all(r['case'][k] is not None for k in ('features','context','sequence32'))],key=lambda r:r['case']['entry_ms'])
    if not rows:return dict(train=[],calibration=[],evaluation=[])
    days=sorted({r['case']['entry_ms']//EMBARGO_MS for r in rows})
    if len(days)<5:return dict(train=rows,calibration=[],evaluation=[])
    cal_start=days[int(len(days)*.6)]*EMBARGO_MS
    eval_start=days[int(len(days)*.8)]*EMBARGO_MS
    return dict(train=[r for r in rows if r['case']['entry_ms']<cal_start-EMBARGO_MS and r['label']['available_at_ms']<cal_start-EMBARGO_MS],
        calibration=[r for r in rows if cal_start<=r['case']['entry_ms']<eval_start-EMBARGO_MS and r['label']['available_at_ms']<eval_start-EMBARGO_MS],
        evaluation=[r for r in rows if r['case']['entry_ms']>=eval_start])

def arrays(rows):
    import numpy as np
    return (np.asarray([r['case']['features'] for r in rows],dtype='float32'),
            np.asarray([r['case']['sequence32'] for r in rows],dtype='float32'),
            np.asarray([r['case']['context'] for r in rows],dtype='float32'),
            np.asarray([r['label']['status']=='WIN' for r in rows],dtype='float32'))

def network(algorithm):
    import torch
    from torch import nn
    if algorithm=='LOGISTIC40':return nn.Linear(40,1)
    if algorithm!='CAUSAL_TCN32_CONTEXT50':raise ValueError('Unsupported algorithm')
    from intelligence.tcn_model import CausalBlock
    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.blocks=nn.Sequential(*[CausalBlock(29 if i==0 else 16,16,d) for i,d in enumerate((1,2,4,8))])
            self.head=nn.Sequential(nn.Linear(66,16),nn.ReLU(),nn.Linear(16,1))
        def forward(self,seq,ctx):
            return self.head(torch.cat((self.blocks(seq.transpose(1,2))[:,:,-1],ctx),dim=1))
    return Net()

def normalize_fit(x,axis):
    import numpy as np
    mean=x.mean(axis=axis,dtype=np.float64);scale=x.std(axis=axis,dtype=np.float64);scale[scale<1e-6]=1
    return dict(mean=mean.tolist(),scale=scale.tolist(),low=x.min(axis=axis).tolist(),high=x.max(axis=axis).tolist())

def transform(x,n):
    import numpy as np
    return np.clip((x-np.asarray(n['mean']))/np.asarray(n['scale']),-6,6).astype('float32')

def fit_network(rows,algorithm,epochs=8,validation=None):
    import torch
    from torch import nn
    torch.set_num_threads(1);torch.manual_seed(224);torch.use_deterministic_algorithms(True)
    x,s,c,y=arrays(rows)
    normal=dict(x=normalize_fit(x,0),s=normalize_fit(s,(0,1)),c=normalize_fit(c,0))
    tx,ts,tc=[torch.from_numpy(transform(a,normal[k])) for a,k in ((x,'x'),(s,'s'),(c,'c'))]
    ty=torch.from_numpy(y).reshape(-1,1);net=network(algorithm)
    optimizer=torch.optim.AdamW(net.parameters(),lr=.002,weight_decay=.01)
    generator=torch.Generator().manual_seed(224);best=None;best_loss=float('inf');best_epoch=epochs
    for epoch in range(1,epochs+1):
        net.train()
        for idx in torch.randperm(len(y),generator=generator).split(128):
            optimizer.zero_grad(set_to_none=True)
            logits=net(tx[idx]) if algorithm=='LOGISTIC40' else net(ts[idx],tc[idx])
            loss=nn.functional.binary_cross_entropy_with_logits(logits,ty[idx])
            if not torch.isfinite(loss):raise ValueError('Nonfinite training loss')
            loss.backward();nn.utils.clip_grad_norm_(net.parameters(),1.);optimizer.step()
        if validation:
            model=dict(algorithm=algorithm,normalization=normal,weights={k:v.detach().tolist() for k,v in net.state_dict().items()})
            vy=[int(r['label']['status']=='WIN') for r in validation]
            score=metrics(vy,probabilities(model,validation))['log_loss']
            if score<best_loss-.0001:
                best_loss=score;best_epoch=epoch;best=copy.deepcopy(model['weights'])
    return dict(algorithm=algorithm,normalization=normal,
        weights=best if best is not None else {k:v.detach().tolist() for k,v in net.state_dict().items()},selected_epoch=best_epoch)

def validate_model_net(model):
    import numpy as np
    import torch
    torch.set_num_threads(1)
    net=network(model['algorithm']);expected=net.state_dict()
    if set(model['weights'])!=set(expected):raise ValueError('Model weight names differ')
    for k,v in expected.items():
        t=torch.tensor(model['weights'][k],dtype=torch.float32)
        if t.shape!=v.shape or not torch.isfinite(t).all():raise ValueError('Model weight value/shape differs')
        expected[k]=t
    for k,width in (('x',40),('s',29),('c',50)):
        normal=model['normalization'][k]
        for name in ('mean','scale','low','high'):
            a=np.asarray(normal[name])
            if a.shape!=(width,) or not np.isfinite(a).all():raise ValueError('Model normalization differs')
        if min(normal['scale'])<=0 or any(a>b for a,b in zip(normal['low'],normal['high'])):
            raise ValueError('Model normalization range differs')
    net.load_state_dict(expected);net.eval();return net

def probabilities(model,rows):
    import numpy as np
    import torch
    net=validate_model_net(model);x,s,c,_=arrays(rows)
    for a,shape in ((x,(len(rows),40)),(s,(len(rows),32,29)),(c,(len(rows),50))):
        if a.shape!=shape or not np.isfinite(a).all():raise ValueError('Input tensor shape/value differs')
    tx,ts,tc=[torch.from_numpy(transform(a,model['normalization'][k])) for a,k in ((x,'x'),(s,'s'),(c,'c'))]
    result=[]
    with torch.inference_mode():
        for i in range(0,len(rows),128):
            logits=net(tx[i:i+128]) if model['algorithm']=='LOGISTIC40' else net(ts[i:i+128],tc[i:i+128])
            result.extend(torch.sigmoid(logits.reshape(-1)/model.get('temperature',1.)).tolist())
    return result

def in_domain(model,case):
    import numpy as np
    pairs=[('x',case['features'])] if model['algorithm']=='LOGISTIC40' else [('s',case['sequence32']),('c',case['context'])]
    for k,a in pairs:
        n=model['normalization'][k];lo,hi,scale=(np.asarray(n[t]) for t in ('low','high','scale'))
        margin=np.maximum(.25*(hi-lo),.25*scale)
        if not ((np.asarray(a)>=lo-margin)&(np.asarray(a)<=hi+margin)).all():return False
    return True

def load_model(path):
    artifact=json.loads(Path(path).read_text(encoding='utf-8'));payload=copy.deepcopy(artifact);h=payload.pop('model_id',None)
    if (digest(payload)!=h or artifact.get('contract')!=MODEL_CONTRACT or
        artifact.get('feature_contract')!=FEATURE_CONTRACT or artifact.get('activation_allowed') is not False or
        artifact.get('target')!='OFFICIAL_SIGNAL_MT4_WIN_VS_LOSS' or artifact.get('threshold')!=THRESHOLD):
        raise ValueError('Model receipt/contract differs')
    if not math.isfinite(artifact['network'].get('temperature',1)) or not .5<=artifact['network'].get('temperature',1)<=3:
        raise ValueError('Invalid calibration temperature')
    validate_model_net(artifact['network'])
    return artifact

def train(dataset_path,output):
    dataset=verify_dataset(json.loads(Path(dataset_path).read_text(encoding='utf-8')))
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    identity=dict(origin=dataset['origin'],policy=dataset['policy'],identity_hash=dataset.get('identity_hash'))
    identity_file=output/'training_identity.json'
    if identity_file.exists() and json.loads(identity_file.read_text())!=identity:
        raise ValueError('Training output belongs to another source/policy/origin')
    if not identity_file.exists():atomic(identity_file,identity)
    ledger=output/'experiments';ledger.mkdir(exist_ok=True)
    # A frozen experiment is never overwritten or reevaluated with tuned settings.
    existing=ledger/(dataset['sha256']+'.json')
    if existing.exists():
        result=json.loads(existing.read_text())
        atomic(output/'current_model.json',dict(model_id=result['model_id'],model_file=result['model_file']))
        return result
    old=[json.loads(p.read_text()) for p in ledger.glob('*.json')]
    newest=max(old,key=lambda r:r['created_utc_ms']) if old else None
    parts=split_rows(dataset)
    ids={r['case']['signal_id'] for part in parts.values() for r in part}
    if newest:
        previous_cutoff=newest['evaluation_cutoff_ms']
        parts['evaluation']=[r for r in parts['evaluation'] if r['case']['entry_ms']>previous_cutoff]
    counts={k:len(v) for k,v in parts.items()}
    weeks=len({r['case']['entry_ms']//(7*EMBARGO_MS) for r in parts['evaluation']})
    report=dict(contract=MODEL_CONTRACT,status='COLLECTING',counts=counts,
        deficits={k:max(0,MINIMUM[k]-counts[k]) for k in MINIMUM},evaluation_weeks=weeks,
        minimum_evaluation_weeks=8,activation_allowed=False,dataset_sha256=dataset['sha256'],
        excluded_nondecisive_or_missing_sequence=len(dataset['rows'])-sum(counts.values()),
        label_scope='OFFICIAL_SIGNAL_MT4_ONLY',price_source='MT4_BID')
    if any(report['deficits'].values()):
        atomic(output/'training_status.json',report);return report
    now=time.time_ns()//1000000
    if newest and (now-newest['created_utc_ms']<7*EMBARGO_MS or len(ids-set(newest['sample_ids']))<50):
        report['status']='WAIT_NEW_DATA';atomic(output/'training_status.json',report);return report
    ty=[int(r['label']['status']=='WIN') for r in parts['train']]
    if min(sum(ty),len(ty)-sum(ty))<20:
        report['status']='INSUFFICIENT_CLASS_DIVERSITY';atomic(output/'training_status.json',report);return report
    # Epoch selection uses an inner chronological train split with its own embargo.
    inner_cut=parts['train'][int(len(parts['train'])*.8)]['case']['entry_ms']
    inner=[r for r in parts['train'] if r['label']['available_at_ms']<inner_cut-EMBARGO_MS]
    validation=[r for r in parts['train'] if r['case']['entry_ms']>=inner_cut]
    candidates=[];cal_y=[int(r['label']['status']=='WIN') for r in parts['calibration']]
    for algorithm in ('LOGISTIC40','CAUSAL_TCN32_CONTEXT50'):
        epochs=80 if algorithm=='LOGISTIC40' else 8
        if algorithm!='LOGISTIC40' and len(inner)>=100 and len(validation)>=50:
            selected=fit_network(inner,algorithm,8,validation)['selected_epoch']
        else:selected=epochs
        net=fit_network(parts['train'],algorithm,selected)
        calibrated=[]
        for temperature in (.5,.75,1.,1.5,2.,3.):
            net['temperature']=temperature
            calibrated.append((metrics(cal_y,probabilities(net,parts['calibration']))['log_loss'],temperature))
        net['temperature']=min(calibrated)[1]
        cal=metrics(cal_y,probabilities(net,parts['calibration']))
        candidates.append((cal['brier'],algorithm,net,cal))
    _,algorithm,net,cal=min(candidates,key=lambda t:(t[0],t[1]))
    ev_y=[int(r['label']['status']=='WIN') for r in parts['evaluation']]
    probabilities_eval=probabilities(net,parts['evaluation']);ev=metrics(ev_y,probabilities_eval)
    prior=(sum(ty)+1)/(len(ty)+2);base=metrics(ev_y,[prior]*len(ev_y))
    selected=[i for i,(p,r) in enumerate(zip(probabilities_eval,parts['evaluation'])) if p>=THRESHOLD and in_domain(net,r['case'])]
    gates=dict(brier_better_than_prior=ev['brier']<base['brier'],log_loss_better_than_prior=ev['log_loss']<base['log_loss'],
        selected_at_least_100=len(selected)>=100,coverage_at_least_20_percent=len(selected)/len(ev_y)>=.2,
        eight_evaluation_weeks=weeks>=8)
    created=time.time_ns()//1000000
    model=dict(contract=MODEL_CONTRACT,feature_contract=FEATURE_CONTRACT,target='OFFICIAL_SIGNAL_MT4_WIN_VS_LOSS',
        training_origin=dataset['origin'],policy=dataset['policy'],dataset_sha256=dataset['sha256'],
        training_broker_utc_offset_minutes=dataset.get('broker_utc_offset_minutes'),
        trained_label_cutoff_ms=max(r['label']['available_at_ms'] for r in parts['train']+parts['calibration']),
        evaluation_cutoff_ms=max(r['label']['available_at_ms'] for r in parts['evaluation']),
        created_utc_ms=created,threshold=THRESHOLD,network=net,
        calibration=cal,evaluation=ev,baseline=base,train_prior=prior,gates=gates,
        offline_review_passed=all(gates.values()),activation_allowed=False,
        status='FROZEN_SHADOW',selection_scope='CHRONOLOGICAL_CALIBRATION_ONLY',
        counts=counts,evaluation_weeks=weeks,selected_count=len(selected),
        selected_win_rate=sum(ev_y[i] for i in selected)/len(selected) if selected else None)
    model['model_id']=digest(model)
    path=output/('model_'+model['model_id']+'.json');atomic(path,model)
    report.update(status='FROZEN_SHADOW',model_id=model['model_id'],model_file=str(path.resolve()),
        created_utc_ms=created,sample_ids=sorted(ids),evaluation_cutoff_ms=model['evaluation_cutoff_ms'],
        offline_review_passed=model['offline_review_passed'],
        selection_scope=model['selection_scope'],evaluation=ev,baseline=base,gates=gates,
        algorithms_calibration=[dict(algorithm=a,metrics=c) for _,a,_,c in candidates])
    atomic(existing,report);atomic(output/'training_status.json',report)
    atomic(output/'current_model.json',dict(model_id=model['model_id'],model_file=str(path.resolve())))
    return report
