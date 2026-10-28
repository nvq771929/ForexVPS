"""CPU causal TCN: train-only preprocessing and temporal-validation early stopping."""
import math
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from .sequence_data import LENGTH
from .research_features import NAMES as ANCHOR_NAMES
from .t1_corrected import NAMES as CONTEXT_NAMES
from .progress import notify
from .preprocessing import binary_indices

PARAMETERS = dict(channels=16, kernel_size=3, dilations=[1,2,4,8], head=16,
    epochs=12, patience=3, min_delta=.0001, batch_size=128, learning_rate=.001,
    weight_decay=.01, gradient_clip=1., seed=213, threads=2, device='cpu', numeric_clip=6.)


class CausalBlock(nn.Module):
    def __init__(self,inputs,channels,dilation):
        super().__init__();self.dilation=dilation
        self.first=nn.Conv1d(inputs,channels,3,dilation=dilation)
        self.second=nn.Conv1d(channels,channels,3,dilation=dilation)
        self.residual=nn.Conv1d(inputs,channels,1) if inputs!=channels else nn.Identity()
    def forward(self,x):
        v=F.relu(self.first(F.pad(x,(2*self.dilation,0))))
        return F.relu(self.second(F.pad(v,(2*self.dilation,0)))+self.residual(x))


class TemporalClassifier(nn.Module):
    def __init__(self):
        super().__init__();c=PARAMETERS['channels']
        self.blocks=nn.Sequential(*[CausalBlock(len(ANCHOR_NAMES) if i==0 else c,c,d)
            for i,d in enumerate(PARAMETERS['dilations'])])
        self.head=nn.Sequential(nn.Linear(c+len(CONTEXT_NAMES),PARAMETERS['head']),nn.ReLU(),nn.Linear(PARAMETERS['head'],1))
    def forward(self,sequence,context):
        return self.head(torch.cat((self.blocks(sequence.transpose(1,2))[:,:,-1],context),dim=1)).squeeze(-1)


def seed():
    torch.set_num_threads(PARAMETERS['threads']);torch.manual_seed(PARAMETERS['seed'])
    torch.use_deterministic_algorithms(True)


def validate_arrays(sequence,context,labels=None):
    if (sequence.ndim!=3 or sequence.shape[1:]!=(LENGTH,len(ANCHOR_NAMES)) or
        context.shape!=(len(sequence),len(CONTEXT_NAMES)) or len(sequence)==0 or
        not np.isfinite(sequence).all() or not np.isfinite(context).all()):
        raise ValueError('TCN input shape/value differs')
    if labels is not None and (labels.shape!=(len(sequence),) or not np.isin(labels,[0.,1.]).all()):
        raise ValueError('TCN labels must be binary with matching length')


def normalization(sequence,context):
    result={}
    for prefix,x,names,axis in [('sequence',sequence,ANCHOR_NAMES,(0,1)),('context',context,CONTEXT_NAMES,0)]:
        mean=x.mean(axis=axis,dtype=np.float64);scale=x.std(axis=axis,dtype=np.float64)
        scale[scale<1e-6]=1.
        binary=binary_indices(names);mean[binary]=0.;scale[binary]=1.
        result.update({prefix+'_mean':mean.tolist(),prefix+'_scale':scale.tolist(),
            prefix+'_low':x.min(axis=axis).tolist(),prefix+'_high':x.max(axis=axis).tolist(),prefix+'_binary_indices':binary})
    return result


def transform(x,normal,prefix):
    value=(x-np.asarray(normal[prefix+'_mean']))/np.asarray(normal[prefix+'_scale'])
    return np.clip(value,-PARAMETERS['numeric_clip'],PARAMETERS['numeric_clip']).astype(np.float32)


def exported(net):return {k:v.detach().cpu().tolist() for k,v in net.state_dict().items()}


def fit(sequence,context,labels,progress=None,label='TCN',*,validation=None,epochs=None):
    validate_arrays(sequence,context,labels)
    limit=PARAMETERS['epochs'] if epochs is None else epochs
    if not isinstance(limit,int) or not 1<=limit<=PARAMETERS['epochs']:raise ValueError('Invalid fixed epoch budget')
    if validation is not None:validate_arrays(*validation)
    seed();normal=normalization(sequence,context)
    sx=torch.from_numpy(transform(sequence,normal,'sequence'));cx=torch.from_numpy(transform(context,normal,'context'))
    y=torch.from_numpy(labels.astype(np.float32))
    if validation is not None:
        vx=torch.from_numpy(transform(validation[0],normal,'sequence'))
        vc=torch.from_numpy(transform(validation[1],normal,'context'));vy=torch.from_numpy(validation[2].astype(np.float32))
    net=TemporalClassifier();initial=exported(net)
    optimizer=torch.optim.AdamW(net.parameters(),lr=PARAMETERS['learning_rate'],weight_decay=PARAMETERS['weight_decay'])
    generator=torch.Generator().manual_seed(PARAMETERS['seed'])
    best=float('inf');best_epoch=0;best_state=None;wait=0;curves=[]
    for epoch in range(1,limit+1):
        net.train();loss_sum=0.
        for batch in torch.randperm(len(y),generator=generator).split(PARAMETERS['batch_size']):
            optimizer.zero_grad(set_to_none=True)
            loss=F.binary_cross_entropy_with_logits(net(sx[batch],cx[batch]),y[batch])
            if not torch.isfinite(loss):raise ValueError('Non-finite TCN loss; candidate rejected')
            loss.backward();nn.utils.clip_grad_norm_(net.parameters(),PARAMETERS['gradient_clip']);optimizer.step()
            loss_sum+=float(loss.detach())*len(batch)
        row=dict(epoch=epoch,train_loss=loss_sum/len(y),validation_loss=None,validation_brier=None)
        if validation is not None:
            net.eval();logits=[]
            with torch.inference_mode():
                for j in range(0,len(vy),512):logits.append(net(vx[j:j+512],vc[j:j+512]))
            raw=torch.cat(logits);vl=float(F.binary_cross_entropy_with_logits(raw,vy))
            if not math.isfinite(vl):raise ValueError('Non-finite validation loss')
            row.update(validation_loss=vl,validation_brier=float(((torch.sigmoid(raw)-vy)**2).mean()))
            improved=vl<best-PARAMETERS['min_delta']
        else:improved=True;vl=None
        if improved:
            best=vl if vl is not None else row['train_loss'];best_epoch=epoch;wait=0
            best_state={k:v.detach().clone() for k,v in net.state_dict().items()}
        else:wait+=1
        curves.append(row)
        detail=f'{label} | train loss {row["train_loss"]:.6f}'
        if vl is not None:detail+=f' | inner validation {vl:.6f} | best epoch {best_epoch}'
        notify(progress,'fit',done=epoch,total=limit,unit='epochs',detail=detail)
        if validation is not None and wait>=PARAMETERS['patience']:break
    final=exported(net);net.load_state_dict(best_state);net.eval();weights=exported(net)
    return dict(algorithm='tcn',architecture='CAUSAL_TCN32_T1_V2',parameters=dict(PARAMETERS),normalization=normal,
        weights=weights,checkpoints=dict(initial=initial,final=final,best=weights),
        training=dict(selection_scope='INNER_CHRONOLOGICAL_TRAIN_VALIDATION' if validation is not None else 'FIXED_EPOCH_REFIT',
            epoch_budget=limit,epochs_run=len(curves),selected_epoch=best_epoch,stopped_early=len(curves)<limit,
            validation_samples=len(validation[2]) if validation is not None else 0,curves=curves))


def restore(model):
    if (model.get('algorithm')!='tcn' or model.get('architecture')!='CAUSAL_TCN32_T1_V2' or model.get('parameters')!=PARAMETERS):
        raise ValueError('Unsupported TCN architecture/parameters')
    net=TemporalClassifier();expected=net.state_dict()
    if set(model['weights'])!=set(expected):raise ValueError('TCN weight names differ')
    state={}
    for name,reference in expected.items():
        value=torch.tensor(model['weights'][name],dtype=torch.float32)
        if value.shape!=reference.shape or not torch.isfinite(value).all():raise ValueError('TCN weight shape/value differs')
        state[name]=value
    normal=model['normalization']
    for prefix,names in [('sequence',ANCHOR_NAMES),('context',CONTEXT_NAMES)]:
        for suffix in ('mean','scale','low','high'):
            values=normal[prefix+'_'+suffix]
            if len(values)!=len(names) or not all(math.isfinite(v) for v in values):raise ValueError('TCN normalization differs')
        if min(normal[prefix+'_scale'])<=0 or any(a>b for a,b in zip(normal[prefix+'_low'],normal[prefix+'_high'])):
            raise ValueError('TCN normalization bounds differ')
        if normal.get(prefix+'_binary_indices')!=binary_indices(names):raise ValueError('TCN binary preprocessing differs')
        if any(normal[prefix+'_mean'][i]!=0 or normal[prefix+'_scale'][i]!=1 for i in binary_indices(names)):
            raise ValueError('TCN binary scale differs')
    net.load_state_dict(state,strict=True);return net.eval()


def score(model,sequence,context):
    validate_arrays(sequence,context)
    normal=model['normalization'];net=restore(model)
    sx=transform(sequence,normal,'sequence');cx=transform(context,normal,'context');result=[]
    with torch.inference_mode():
        for i in range(0,len(sx),512):result.extend(net(torch.from_numpy(sx[i:i+512]),torch.from_numpy(cx[i:i+512])).tolist())
    values=np.asarray(result,dtype=float)
    if not np.isfinite(values).all():raise ValueError('Non-finite TCN score')
    return values


def domain(model,sequence,context):
    normal=model['normalization']
    def allowed(x,prefix):
        low,high,scale=(np.asarray(normal[prefix+'_'+k]) for k in ('low','high','scale'))
        margin=np.maximum(.25*(high-low),.25*scale);good=(x>=low-margin)&(x<=high+margin)
        return good.all(axis=tuple(range(1,good.ndim)))
    return allowed(sequence,'sequence')&allowed(context,'context')
