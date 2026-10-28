"""Independent checks of numeric data, fixed-window formulas and old audited endpoints."""
import argparse,bisect,csv,gzip,hashlib,io,json,math,sys
from pathlib import Path
from collections import Counter
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from intelligence.price_dataset import read_frozen

def verify(folder,plan_path,publication_path):
 folder=Path(folder);plan=json.loads(Path(plan_path).read_text());manifest=json.loads((folder/'MANIFEST_SHA256.json').read_text())
 for n,h in manifest.items():
  if hashlib.sha256((folder/n).read_bytes()).hexdigest()!=h:raise ValueError('Dataset manifest '+n)
 with gzip.open(folder/'rows.jsonl.gz','rt') as f:rows=[json.loads(line) for line in f]
 with np.load(folder/'price_behavior.npz',allow_pickle=False) as f:arrays={k:f[k] for k in f.files}
 assert len(rows)==32836 and len({r['sample_id'] for r in rows})==len(rows)
 assert all(v.dtype.kind!='O' and np.isfinite(v).all() for v in arrays.values())
 assert arrays['x_300'].shape==(32836,32,9) and arrays['x_900'].shape==(32836,16,9) and arrays['x_3600'].shape==(32836,16,9)
 assert arrays['labels'].shape==(32836,3) and set(np.unique(arrays['labels']))<={-1,0,1,9}
 for i,r in enumerate(rows):
  assert r['native_available_ms']<=r['cutoff_ms']<r['entry_ms'] and r['asof_ms']+300000==r['entry_ms']
  for j,h in enumerate((5,15,30)):
   q=r['outcomes'][str(h)];assert q['direction']==int(arrays['labels'][i,j]) and q['target_ms']==r['entry_ms']+h*60000
   if q['direction']!=9:
    en=r['entry_quote'];ex=q['exit_quote'];assert en['session']==ex['session']
    assert 0<=en['observed_ms']-r['entry_ms']<=2000 and 0<=ex['observed_ms']-q['target_ms']<=2000
    move=ex['points']-en['points'];assert q['direction']==(1 if move>0 else -1 if move<0 else 0)
  features=dict(frames={str(s):arrays[f'x_{s}'][i].tolist() for s in (300,900,3600)},context=arrays['context'][i].tolist())
  canonical=json.dumps(features,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
  assert hashlib.sha256(canonical).hexdigest()==r['feature_sha256']
 # Match the pre-existing 237-publication horizon audit (all three boundaries).
 old=json.loads(Path(publication_path).read_text());old=old.get('cases',old) if isinstance(old,dict) else old
 by={r['asof_ms']//1000:r for r in rows};matched=0
 for p in old:
  t=p['signal_id'];r=by[t];assert r['source_id']==p['source_id']
  assert r['entry_quote']['points']==p['entry_points']
  for h in (5,15,30):
   q=r['outcomes'][str(h)];gold=p['outcomes'][str(h)]
   status='UNAVAILABLE' if q['direction']==9 else 'TIE' if q['direction']==0 else 'WIN' if q['direction']==p['direction'] else 'LOSS'
   assert status==gold['status'],(p['id'],h,status,gold['status'])
   if status!='UNAVAILABLE':assert q['exit_quote']['points']==gold['exit_points'] and q['exit_quote']['input_sequence']==gold['input_sequence']
  matched+=1
 # Reconstruct sampled feature values directly from raw native CSV packets.
 audit=read_frozen(plan['parents']['native_audit']);indexes={};cache={}
 for source in plan['sources']:
  sid=source['id'];root=Path(source['path']);items=[]
  expected=next(x for x in audit['source_receipts'] if x['source_id']==sid)
  for index in expected['indexes']:
   raw=(root/index['file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==index['sha256']
   for q in csv.DictReader(io.StringIO(raw.decode('ascii'))):
    if q['event_kind']=='1':items.append((int(q['analysis_start']),int(q['observed_ms']),q['snapshot_ref']))
  items.sort();indexes[sid]=(root,[x[0] for x in items],items)
 def bar(sid,t,cut):
  root,times,items=indexes[sid];i=bisect.bisect_left(times,t+300)
  if i==len(times) or items[i][0]-64*300>t or items[i][1]>cut:return None
  key=(sid,items[i][2])
  if key not in cache:
   raw=(root/items[i][2]).read_text();p=list(csv.reader(io.StringIO(raw)))
   cache[key]={int(x[0]):(float(x[1]),float(x[2]),float(x[3]),float(x[4]),int(x[5])) for x in p[2:]}
  return cache[key].get(t)
 def aggregate(sid,t,seconds,cut):
  q=[bar(sid,x,cut) for x in range(t,t+seconds,300)]
  if any(x is None for x in q):return None
  return q[0][0],max(x[1] for x in q),min(x[2] for x in q),q[-1][3],sum(x[4] for x in q)
 samples=sorted(set(range(0,len(rows),257))|{0,len(rows)-1}|{next(i for i,r in enumerate(rows) if r['partition']==part) for part in {r['partition'] for r in rows}})
 checked=0
 for i in samples:
  r=rows[i];asof=r['asof_ms']//1000;cut=r['cutoff_ms'];sid=r['source_id'];scale=bar(sid,asof-300,cut)[3]
  for s,n in ((300,32),(900,16),(3600,16)):
   end=asof//s*s
   for j,t in enumerate(range(end-n*s,end,s)):
    b=aggregate(sid,t,s,cut);p=aggregate(sid,t-s,s,cut)
    if b is None:want=[0.]*9
    else:
     o,h,l,c,v=b;want=[math.log(c/p[3]) if p else 0.,(c-o)/scale,(h-l)/scale,(h-max(o,c))/scale,(min(o,c)-l)/scale,math.log1p(v),float(p is None),float(p is not None),1.]
    assert np.allclose(arrays[f'x_{s}'][i,j],want,rtol=1e-12,atol=1e-14),(i,s,j)
    checked+=9
 folds=('TRAIN','INNER_VALIDATION','CALIBRATION','RETROSPECTIVE_EVALUATION_ALREADY_INSPECTED')
 intervals=[]
 for fold in folds:
  selected=[r for r in rows if r['partition']==fold]
  intervals.append((min(r['earliest_potential_feature_ms'] for r in selected),max(r['entry_ms']+1800000+2000 for r in selected)))
 assert all(a[1]<b[0] for a,b in zip(intervals,intervals[1:]))
 return dict(status='PASS',rows=len(rows),all_feature_hashes_verified=True,publication_cases_crosschecked=matched,publication_horizon_endpoints=matched*3,
  independently_reconstructed_rows=len(samples),independent_numeric_feature_values=checked,folds_have_no_shared_feature_label_time_intervals=True,
  unavailable_not_imputed=True,no_pickled_arrays=True,model_trained=False,independent_market_holdout=False)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dataset',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--publication-audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
 a=p.parse_args();result=verify(a.dataset,a.plan,a.publication_audit);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
