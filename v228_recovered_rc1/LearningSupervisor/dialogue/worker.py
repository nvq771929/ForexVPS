"""Non-blocking peer for an EA. Writes only request-matched scoped reply files."""
from collections import deque
import hashlib
import json
from pathlib import Path
import time
from .protocol import read_request,read_final,row_bytes,REPLY
from .features import extract
from . import CONTRACT,FEATURE_CONTRACT
from .models import qualification
from supervisor.store import Store,digest,atomic
from supervisor.learning import probabilities,in_domain
from intelligence.native_ledger import decode_bytes
from intelligence.research_features import extract as anchor_features

class Worker:
    def __init__(self,source,output,offset=None,model=None,receipt=None):
        self.source=Path(source).resolve();self.output=Path(output).resolve()
        if self.source==self.output or self.source in self.output.parents or self.output in self.source.parents:
            raise ValueError('Worker output and native journal must be separate, non-nested directories')
        self.store=Store(self.output);self.offset=offset;self.model=model;self.receipt_path=receipt
        self.last=max((r['sequence'] for r in self.store.all('native')),default=0)
        self.anchors=deque(sorted(self.store.all('anchor'),key=lambda a:a['start'])[-32:],maxlen=32)
        self.seen={r['path'] for r in self.store.all('query')}
        from intelligence.demo_learning import read_policy
        from intelligence.origin import read_origin
        self.policy=read_policy(self.source);self.origin=read_origin(self.source,self.policy)
        identity=dict(source=str(self.source),policy=self.policy,origin=self.origin,
            metadata={n:hashlib.sha256((self.source/n).read_bytes()).hexdigest() for n in ('demo_policy.csv','data_origin.csv')})
        self.store.put('identity','source',identity);self.store.commit()
        for item in self.store.all('native'):
            if hashlib.sha256((self.source/item['file']).read_bytes()).hexdigest()!=item['sha256']:
                raise ValueError('Previously observed native prefix changed')
        for item in self.store.all('query'):
            reread=read_request(self.source/item['path'])
            if reread['request_sha256']!=item['request_sha256'] or reread['snapshot_sha256']!=item['snapshot_sha256']:
                raise ValueError('Previously observed request changed')
        for item in self.store.all('final'):
            if read_final(self.source/item['path'])[1]!=item['sha256']:raise ValueError('Previously observed native decision changed')
        self.qualified=qualification(receipt,model,self.policy) if model else dict(qualified=False,cutoff_utc_ms=0,reason='NO_PRELOCK_MODEL')
        if self.qualified['qualified']:
            self.native()
            from .dataset import prepare
            from .models import export_forward_receipt
            expected=export_forward_receipt(self,prepare(self),model,persist=False)
            supplied=json.loads(Path(receipt).read_text())
            index={(r['analysis_start'],r['horizon']):r for r in expected['rows']}
            if any(index.get((r['analysis_start'],r['horizon']))!=r for r in supplied['rows']):
                raise ValueError('Qualification evidence is not reproduced by this worker ledger/native receipts/ticks')
        self.wall=time.time();self.mono=time.monotonic();self.clock_ok=True

    def native(self):
        while True:
            path=self.source/f'event_{self.last+1:012d}.bin'
            if not path.exists():
                if any(int(p.stem[6:])>self.last+1 for p in self.source.glob('event_*.bin')):raise ValueError('Native prefix gap')
                break
            raw=path.read_bytes();record=decode_bytes(raw,self.last+1,compact=True);s,e=record['state'],record['event']
            if s['configHash']!=self.policy['config_hash'] or s['feedHash']!=self.policy['feed_hash']:raise ValueError('Native policy differs')
            if e['kind']==1:
                try:a=dict(start=e['analysisStart'],observed_ms=e['observedMs'],features=anchor_features(s['current']))
                except ValueError:pass
                else:self.store.put('anchor',a['start'],a);self.anchors.append(a)
            if e['kind']==3:self.store.put('native_lock',e['analysisStart'],dict(observed_ms=e['observedMs'],locked_action=e['lockedAction']))
            self.last+=1;self.store.put('native',self.last,dict(sequence=self.last,file=path.name,sha256=hashlib.sha256(raw).hexdigest()))
            if self.last%512==0:self.store.commit()

    def observe(self,path):
        request=read_request(path);meta=request['meta'];feature=extract(request)
        if request['policy']!=self.policy or request['origin']!=self.origin:raise ValueError('Request source cohort changed')
        prefix=[a for a in self.anchors if a['start']<=meta['analysis_start'] and a['observed_ms']<=meta['observed_ms']][-32:]
        seq=None
        if len(prefix)==32 and prefix[-1]['start']==meta['analysis_start'] and all(b['start']-a['start']==300 for a,b in zip(prefix,prefix[1:])):
            seq=[a['features'] for a in prefix]
        # Older requests can be imported after the deque has advanced; DB retains causal anchors.
        if seq is None:
            wanted=[meta['analysis_start']-i*300 for i in range(31,-1,-1)]
            rows=[self.store.get('anchor',t) for t in wanted]
            if all(a is not None and a['observed_ms']<=meta['observed_ms'] for a in rows):seq=[a['features'] for a in rows]
        observed=dict(path=str(path.relative_to(self.source)),meta=meta,origin=request['origin'],policy=request['policy'],
            query_policy={k:int(request['transport'][k]) for k in ('interval','max_age','reserve')},
            request_sha256=request['request_sha256'],snapshot_sha256=request['snapshot_sha256'],feature=feature,sequence32=seq,
            source=str(self.source))
        self.store.put('query',observed['path'],observed);self.store.commit();return observed

    def respond(self,query):
        r=query['meta'];now=time.time_ns()//1000000
        # Replayed or Tester requests are collected only. Never answer a historical clock.
        if self.origin!='LIVE_MT4' or self.offset is None or not self.clock_ok:return 'COLLECT_ONLY_OR_CLOCK_UNKNOWN'
        request_utc=r['observed_ms']-self.offset*60000;deadline_utc=r['deadline_ms']-self.offset*60000
        if not request_utc-1000<=now<deadline_utc:return 'LATE_COLLECT_ONLY'
        model=self.model;p=-1;decision=0;valid=0;reason='NO_COMPATIBLE_MODEL';domain=False
        if model and model['policy']==self.policy and model['broker_utc_offset_minutes']==self.offset and model['query_policy']==query['query_policy']:
            if model['created_utc_ms']<request_utc and model['trained_cutoff_utc_ms']<request_utc:
                if model['network']['algorithm']=='LOGISTIC40' or query['sequence32'] is not None:
                    # Generic tensor evaluator only; feature/model contract is checked by dialogue.models.
                    sequence=query['sequence32']
                    if sequence is None:sequence=[[0.]*29 for _ in range(32)]
                    case=dict(features=query['feature']['features'],context=query['feature']['context'],sequence32=sequence)
                    p=probabilities(model['network'],[dict(case=case,label=dict(status='UNLABELED'))])[0]
                    domain=in_domain(model['network'],case)
                    decision=1 if domain and p>=model['threshold'] else -1
                    reason='MODEL_KEEP' if decision==1 else 'MODEL_WAIT'
                    valid=int(self.qualified['qualified'] and self.qualified['cutoff_utc_ms']<request_utc)
        completed=time.time_ns()//1000000
        if completed>=deadline_utc:return 'SCORING_FINISHED_TOO_LATE'
        fields={k:r[k] for k in REPLY if k in r}
        fields.update(schema=1,contract=CONTRACT,requested_ms=r['observed_ms'],decision=decision,
            probability_ppm=round(p*1000000) if p>=0 else -1,model_id=model['model_id'] if model and p>=0 else 'NONE',
            trained_cutoff_utc_ms=model['trained_cutoff_utc_ms'] if model and p>=0 else 0,
            model_created_utc_ms=model['created_utc_ms'] if model and p>=0 else 0,response_utc_ms=completed,
            qualification_cutoff_utc_ms=self.qualified['cutoff_utc_ms'] if valid else 0,validated=valid)
        destination=self.source/query['path'];destination=destination.with_name(f"reply_{r['sequence']:012d}.csv")
        if destination.exists():return 'REPLY_ALREADY_EXISTS'
        temp=destination.with_suffix('.csv.tmp')
        with temp.open('xb') as stream:
            stream.write(row_bytes(REPLY,fields));stream.flush()
            import os;os.fsync(stream.fileno())
        # Exclusive publication: an existing reply is never overwritten.
        try:
            import os
            os.link(temp,destination)
        except FileExistsError:
            temp.unlink();return 'REPLY_ALREADY_EXISTS'
        except OSError:
            # Windows os.link is available on NTFS. A failure leaves EA fallback intact.
            temp.unlink();return 'REPLY_PUBLICATION_UNAVAILABLE'
        temp.unlink();durable=time.time_ns()//1000000
        prediction=dict(query_path=query['path'],request_sha256=query['request_sha256'],feature_contract=FEATURE_CONTRACT,
            model_id=fields['model_id'],probability=p,in_domain=bool(domain),decision=decision,validated=bool(valid),
            request_utc_ms=request_utc,written_utc_ms=completed,durable_utc_ms=durable,deadline_utc_ms=deadline_utc,
            response_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),origin=self.origin,
            timing='PROSPECTIVE_PRELOCK' if request_utc<=completed<=durable<deadline_utc else 'LATE',reason=reason)
        self.store.put('prediction',query['path'],prediction);self.store.commit()
        return reason

    def poll(self):
        if abs((time.time()-self.wall)-(time.monotonic()-self.mono))>2:self.clock_ok=False
        self.native();new=0
        for path in sorted((self.source/'advisory_v224').glob('*/request_*.csv')):
            relative=str(path.relative_to(self.source))
            if relative in self.seen:continue
            if not path.resolve().is_relative_to((self.source/'advisory_v224').resolve()):raise ValueError('Dialogue path escaped source')
            q=self.observe(path);result=self.respond(q);self.seen.add(relative);new+=1
            self.store.put('processing',relative,dict(result=result));self.store.commit()
        for path in sorted((self.source/'advisory_v224').glob('*/final_*.csv')):
            relative=str(path.relative_to(self.source));row,h=read_final(path)
            native=self.store.get('native_lock',row['analysis_start'])
            if native is None:continue  # Native writer can be ahead of this captured prefix.
            if native['observed_ms']!=int(row['final_ms']) or native['locked_action']!=int(row['final_action']):
                raise ValueError('Final decision differs from native LOCK')
            self.store.put('final',relative,dict(path=relative,sha256=h,row=row))
        self.store.commit()
        status=dict(contract=CONTRACT,origin=self.origin,requests=len(self.seen),new_requests=new,
            ea_final_decisions=len(self.store.all('final')),
            replies=len(self.store.all('prediction')),model_id=self.model['model_id'] if self.model else None,
            qualification=self.qualified,clock_ok=self.clock_ok,ea_decides_on_timeout=True,post_lock_effects=False,
            updated_utc_ms=time.time_ns()//1000000)
        atomic(self.output/'dialogue_status.json',status);return status

    def close(self):self.store.close()
