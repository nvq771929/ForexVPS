"""V207 local MT4 simulation learner. Standard library only; no order API.

Native FNV-checked immutable journals are authoritative. Published demo paper
trades and a separately scheduled confirmed-reference cohort are kept apart.
All model updates use closed labels available BEFORE the model's broker cutoff.
"""
from collections import Counter,defaultdict
import csv
from dataclasses import dataclass
from decimal import Decimal,ROUND_HALF_UP
import hashlib
import io
import json
import math
from pathlib import Path
import random
import statistics

from .native_ledger import iter_directory
from .signal_features import extract as extract_features
from .origin import read_origin
from .progress import notify

LOGIC=2026101707
SOURCE='MT4_SIMULATED'
MODEL_COLUMNS=['schema','source','logic','config_hash','feed_hash','policy_hash','asof','expires','model_id',
    'setup','direction','regime','horizon','decision','p_win','n_train','n_test','atr_min','atr_max','validated','row_count','reserved']
SUMMARY_COLUMNS=['schema','source','logic','config_hash','feed_hash','policy_hash','asof','signals','wins','losses',
    'ties','unavailable','pending','last_target','last_direction','last_result']
POLICY_COLUMNS=['schema','logic','config_hash','feed_hash','policy_hash','horizon','enabled','learning']


def fnv(text):
    value=2166136261
    for byte in text.encode('ascii'):value=((value^byte)*16777619)&0xffffffff
    return value


def points(price):
    price=float(price)
    if not math.isfinite(price) or price<=0:raise ValueError('Invalid MT4 price')
    return int((Decimal(str(price))*100000).quantize(Decimal('1'),rounding=ROUND_HALF_UP))


def read_policy(source):
    with (Path(source)/'demo_policy.csv').open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream);rows=list(reader)
        if reader.fieldnames!=POLICY_COLUMNS or len(rows)!=1:raise ValueError('Invalid V207 policy file')
    try:p={k:int(v) for k,v in rows[0].items()}
    except (ValueError,TypeError):raise ValueError('Policy requires integers') from None
    if p['schema']!=1 or p['logic']!=LOGIC or p['horizon'] not in (1,2,3) or p['enabled'] not in (0,1) or p['learning'] not in (0,1):
        raise ValueError('Unsupported demo policy')
    if not all(0<v<=0xffffffff for v in (p['config_hash'],p['feed_hash'],p['policy_hash'])):raise ValueError('Invalid identity hashes')
    expected=fnv('DEMO1|'+ '|'.join(str(p[k]) for k in ('config_hash','feed_hash','horizon','enabled','learning')))
    if expected!=p['policy_hash']:raise ValueError('Policy fingerprint differs')
    return p


def outcome(entry,result,direction):
    movement=points(result)-points(entry)
    signed=direction*movement
    return ('WIN' if signed>0 else 'LOSS' if signed<0 else 'TIE'),signed


def collect(source,policy=None,*,paths=None,on_record=None,progress=None,compact=True,include_research=False):
    """Decode all committed records; never execute scripts from uploaded logs."""
    source=Path(source);p=policy or read_policy(source);origin=read_origin(source,p)
    groups=defaultdict(list);asof=0;record_count=0
    if include_research:
        from .research_data import Funnel,build
        funnel=Funnel()
    for r in iter_directory(source,logic_version=LOGIC,paths=paths,on_record=on_record,compact=compact):
        state,e=r['state'],r['event']
        if include_research:funnel.observe(r)
        record_count+=1
        if record_count==1 and state['sequence']!=1:raise ValueError('Need complete journal from sequence 1')
        if state['configHash']!=p['config_hash'] or state['feedHash']!=p['feed_hash']:
            raise ValueError('Journal config/feed differs from demo policy')
        asof=max(asof,int(e['observedMs'])//1000)
        if e['analysisStart']>0 and e['kind'] in (3,4,5,6,7):
            # The 16 pending POD slots are not needed after verification.
            # Avoid retaining them for every event in multi-year Tester runs.
            slim=dict(paused=state['paused'],current=state['current'] if e['kind']==3 else {k:state['current'][k] for k in ('canceled','analysisStart','targetTime','lastQuoteMs','locked','lockedAtMs')})
            groups[e['analysisStart']].append(dict(state=slim,event=e))
    # Timer/TICK input rows advance the observed broker cutoff even between
    # journal events. An outcome is not used at its own timestamp by accident.
    notify(progress,'labels',detail='Doc moc thoi gian replay neu co')
    inputs=sorted(source.glob('input_*.csv'))
    if inputs:
        content=inputs[-1].read_text(encoding='utf-8-sig')
        if content and not content.endswith('\n'):
            content=content[:content.rfind('\n')+1]  # concurrent partial tail
        prior={}
        for line,row in enumerate(csv.DictReader(io.StringIO(content)),2):
            if int(row['schema'])!=2 or int(row['logic_version'])!=LOGIC or row['shadow_mode']!='1':
                raise ValueError('Unsupported replay input identity')
            seq=int(row['sequence']);now=int(row['time_ms_estimated']);sid=row['session']
            if sid in prior and (seq!=prior[sid][0]+1 or now<prior[sid][1]):
                previous_seq,previous_ms=prior[sid]
                kind='SEQUENCE_GAP_OR_DUPLICATE' if seq!=previous_seq+1 else 'CLOCK_BACKWARDS'
                raise ValueError(f'Replay sequence/clock mismatch: {kind}; file={inputs[-1].name}; CSV row={line}; '
                    f'session={sid}; previous_seq={previous_seq}, current_seq={seq}; previous_ms={previous_ms}, current_ms={now}. Preserve original logs.')
            prior[sid]=(seq,now);asof=max(asof,now//1000)
    papers=[];references=[];audit=Counter();resume_at=0;h=p['horizon']
    notify(progress,'labels',done=0,total=len(groups),unit='nhom',detail='Giu nguyen quy tac nhan va ky han')
    for index,(start,rr) in enumerate(sorted(groups.items()),1):
        if index%1000==0:notify(progress,'labels',done=index,total=len(groups),unit='nhom')
        locks=[r for r in rr if r['event']['kind']==3]
        entries=[r for r in rr if r['event']['kind']==5]
        if len(locks)>1 or len(entries)>1:raise ValueError('Duplicate lock or entry')
        if not locks:continue
        lock=locks[0];e=lock['event'];target=int(e['targetTime'])
        if target!=start+300:raise ValueError('Invalid anchor/entry relationship')
        direction=int(e['lockedDirection']);published=e['lockedAction'] in (-1,1)
        if published and (direction!=e['lockedAction'] or e['selectedHorizon']!=h):raise ValueError('Published demo contract changed')
        base=dict(source=SOURCE if origin=='LIVE_MT4' else 'BACKTEST_MT4_SIMULATED',signal_id=f"{p['feed_hash']:08x}.{p['policy_hash']:08x}.{start}",
            analysis_start=start,entry_target=target,expiry_target=target+h*300,direction=direction,
            setup=int(e['setup']),regime=int(e['regime']),horizon=h,model_id=int(e['modelId']),
            locked_at_ms=int(e['lockedAtMs']),entry_observed_ms=None,exit_observed_ms=None,
            entry_bid=None,exit_bid=None,status='PENDING_ENTRY',signed_points=None,
            available_at_ms=None,simulated_entry=False,published=published,atr_pips=float(lock['state']['current']['anchor']['volatility']['atr'])*10000)
        if direction in (-1,1) and e['validation']==2:
            base['features']=extract_features(lock['state']['current'])
            base['locked_probability']=float(e['p1' if h==1 else 'p2' if h==2 else 'p3'])
        entry=entries[0] if entries else None
        canceled=any(r['event']['kind'] in (4,7) and r['state']['current']['canceled'] for r in rr)
        if entry is None:
            base['status']='CANCELED' if canceled else 'ENTRY_UNAVAILABLE' if asof>target+2 else 'PENDING_ENTRY'
            if published:papers.append(base)
            continue
        event=entry['event'];current=entry['state']['current']
        valid=(direction in (-1,1) and e['validation']==2 and event['validation']==2
            and event['lockedDirection']==direction and not current['canceled'] and not entry['state']['paused']
            and target*1000<=event['observedMs']<=(target+2)*1000
            and e['lockedAtMs']<=(target-31)*1000)
        if not valid:
            base['status']='CANCELED' if current['canceled'] else 'ENTRY_UNAVAILABLE'
            if published:papers.append(base)
            audit['invalid_or_canceled_entries']+=1;continue
        if published!=bool(event['signal']):raise ValueError('Paper entry disagrees with published lock')
        points(event['bid'])
        base.update(entry_observed_ms=int(event['observedMs']),entry_bid=float(event['bid']),
            simulated_entry=published,status='OPEN')
        results=[r['event'] for r in rr if r['event']['kind']==6 and r['event']['outcomeHorizon']==h]
        if len(results)>1:raise ValueError('Duplicate selected-horizon outcome')
        if results:
            result=results[0];due=(target+h*300)*1000
            if result['direction']!=direction or result['selectedHorizon']!=(h if published else 0) or result['signal']!=published:
                raise ValueError('Outcome identity/horizon changed')
            if result['outcome']==9:
                base['status']='UNAVAILABLE'
            else:
                if result['targetTime']!=target or not due<=result['observedMs']<=due+2000:
                    raise ValueError('Outcome outside exact boundary')
                if points(result['bid'])!=points(event['bid']):raise ValueError('Outcome entry price changed')
                status,signed=outcome(event['bid'],result['auxiliaryPrice'],direction)
                move=points(result['auxiliaryPrice'])-points(event['bid'])
                if result['outcome']!=((move>0)-(move<0)):raise ValueError('Native outcome disagrees with prices')
                base.update(status=status,signed_points=signed,exit_bid=float(result['auxiliaryPrice']),
                    exit_observed_ms=int(result['observedMs']),available_at_ms=int(result['observedMs'])+1000)
        elif asof>target+h*300+2:
            # Missing records do not become inferred wins; terminal may have stopped.
            base['status']='UNAVAILABLE'
        if published:papers.append(dict(base))
        # Fixed, outcome-blind occupancy applies to BOTH blocked references and
        # published paper signals. No future completeness may free this slot.
        if start<resume_at:audit['reference_occupancy_blocked']+=1;continue
        resume_at=target+h*300+300
        references.append(dict(base,cohort='CONFIRMED_REFERENCE'))
    notify(progress,'labels',done=len(groups),total=len(groups),unit='nhom',detail=f'{len(references):,} mau tham chieu')
    result=dict(policy=p,origin=origin,asof=asof,papers=papers,references=references,audit=dict(audit),records=record_count)
    if include_research:
        result['research'],result['research_data_audit']=build(groups,p,asof,origin,points,progress)
        result['funnel']=funnel.result()
        result['funnel']['strict_reference_rows']=len(references)
        result['funnel']['strict_status_counts']=dict(Counter(r['status'] for r in references))
        result['funnel']['strict_collector_audit']=dict(audit)
        result['funnel']['research_data_audit']=result['research_data_audit']
        from .t1_features import enrich
        from .execution_diagnostics import trace
        result['research_t1'],result['t1_data_audit']=enrich(result['research'],groups,progress)
        result['execution_traces']=trace(groups)
        result['funnel']['t1_data_audit']=result['t1_data_audit']
        result['funnel']['t1_data_audit']=result['t1_data_audit']
        result['funnel']['t1_data_audit']=result['t1_data_audit']
    return result


def wilson(wins,n,z=1.96):
    if not n:return 0.,1.
    p=wins/n;den=1+z*z/n;mid=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return mid-half,mid+half


def payoff(row,stress_points=0):
    delta=row['signed_points']-stress_points
    return .82 if delta>0 else -1. if delta<0 else 0.


def weekly_bounds(rows,repeats=2000):
    weeks=defaultdict(lambda:[0.,0])
    for row in rows:
        day=row['entry_target']//86400;week=day-(day+3)%7
        weeks[week][0]+=payoff(row);weeks[week][1]+=1
    if len(weeks)<8:return None,None,len(weeks)
    blocks=list(weeks.values());rng=random.Random(2026101707);ratios=[]
    for _ in range(repeats):
        sample=rng.choices(blocks,k=len(blocks));ratios.append(sum(x[0] for x in sample)/sum(x[1] for x in sample))
    ratios.sort();return ratios[int(.025*repeats)],ratios[min(repeats-1,int(.975*repeats))],len(weeks)


def phase_stats(rows):
    decisive=[r for r in rows if r['status']!='TIE'];wins=sum(r['status']=='WIN' for r in decisive)
    low,high=wilson(wins,len(decisive));lb,ub,weeks=weekly_bounds(rows)
    return dict(samples=len(rows),decisive=len(decisive),wins=wins,ties=len(rows)-len(decisive),
        p=(wins+1)/(len(decisive)+2),low=low,high=high,roi=statistics.mean(map(payoff,rows)) if rows else None,
        stress_roi=statistics.mean(payoff(r,2) for r in rows) if rows else None,
        roi_lower=lb,roi_upper=ub,weeks=weeks)


def train(snapshot):
    """Freeze action on earlier dates; validate that SAME action on later data.

    Research/demo filter only. No claim of independent untouched market testing
    or of production promotion. Rows stay OBSERVE until substantial evidence.
    """
    p=snapshot['policy'];asof=snapshot['asof'];groups=defaultdict(list)
    closed=[r for r in snapshot['references'] if r['status'] in ('WIN','LOSS','TIE') and r['available_at_ms']<asof*1000]
    days=sorted({r['entry_target']//86400 for r in closed})
    cutoff=days[max(0,min(len(days)-1,int(len(days)*2/3)))]*86400 if days else asof
    for row in closed:groups[(row['setup'],row['direction'],row['regime'],row['horizon'])].append(row)
    models=[];details=[]
    for identity,rows in sorted(groups.items()):
        earlier=[r for r in rows if r['entry_target']<cutoff and r['available_at_ms']<cutoff*1000]
        later=[r for r in rows if r['entry_target']>=cutoff]
        tr=phase_stats(earlier);te=phase_stats(later);all_stats=phase_stats(rows)
        action=0;frozen=0;failures=[]
        if tr['decisive']<200 or tr['weeks']<8:failures.append('training_samples_or_weeks')
        else:
            if tr['low']>1/1.82+.02 and tr['roi_lower'] is not None and tr['roi_lower']>0 and tr['stress_roi']>0:frozen=1
            elif tr['high']<1/1.82-.02 and tr['roi_upper'] is not None and tr['roi_upper']<0:frozen=-1
            else:failures.append('no_frozen_training_action')
        if te['decisive']<100 or te['weeks']<8:failures.append('forward_samples_or_weeks')
        if frozen==1 and not (te['low']>1/1.82+.02 and te['roi_lower'] is not None and te['roi_lower']>0 and te['stress_roi']>0):
            failures.append('forward_allow_not_confirmed')
        if frozen==-1 and not (te['high']<1/1.82-.02 and te['roi_upper'] is not None and te['roi_upper']<0):
            failures.append('forward_block_not_confirmed')
        decisive_test=te['decisive']
        if frozen and decisive_test and abs(tr['p']-te['wins']/decisive_test)>.10:failures.append('forward_probability_drift')
        if frozen and not failures:action=frozen
        domain=earlier if action else rows
        probability=tr['p'] if action else all_stats['p']
        setup,direction,regime,horizon=identity
        model_id=asof*1000+setup*100+(direction+1)*10+regime
        models.append(dict(model_id=model_id,setup=setup,direction=direction,regime=regime,horizon=horizon,
            decision=action,p_win=probability,n_train=tr['decisive'],n_test=te['decisive'],
            atr_min=min(r['atr_pips'] for r in domain),atr_max=max(r['atr_pips'] for r in domain),validated=int(action!=0)))
        details.append(dict(context=identity,candidate_probability=all_stats['p'],training=tr,forward=te,
            training_frozen_action=frozen,applied_decision=action,failures=failures))
    return models,dict(source=SOURCE,cutoff_broker_seconds=cutoff,available_closed_reference_labels=len(closed),
        contexts=details,automatic_broker_orders=False,production_promoted=False,
        limits=['Dense same-feed observational simulation; not Olymp settlements.',
            'Default Wilson/weekly resampling gates are exploratory demo criteria, not a production certificate.',
            'Repeated rolling updates reuse historical evidence; fresh forward monitoring remains necessary.',
            'OBSERVE rows update descriptive probability only; no claim of improvement from a few labels.'])


def csv_bytes(columns,rows):
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=columns,lineterminator='\r\n')
    writer.writeheader();writer.writerows(rows);return stream.getvalue().encode('ascii')


def atomic(path,content):
    path=Path(path);temp=path.with_name(path.name+'.python.tmp')
    temp.write_bytes(content);temp.replace(path)


def update(source,snapshot=None):
    source=Path(source);snap=collect(source) if snapshot is None else snapshot
    if snap.get('origin','LIVE_MT4')!='LIVE_MT4':raise ValueError('Use Train-History for Tester data; it cannot update live models')
    models,report=train(snap);p=snap['policy'];asof=snap['asof']
    if asof<=0:raise ValueError('Waiting for broker time')
    common=dict(schema=1,source=SOURCE,logic=LOGIC,config_hash=p['config_hash'],feed_hash=p['feed_hash'],
        policy_hash=p['policy_hash'],asof=asof,expires=asof+86400,row_count=len(models),reserved=0)
    meta=dict(common,model_id=0,setup=0,direction=0,regime=0,horizon=p['horizon'],decision=0,p_win='0.500000000',
        n_train=0,n_test=0,atr_min='0.000000000',atr_max='0.000000000',validated=0)
    model_rows=[meta]
    for model in models:
        row=dict(common,**model)
        for key in ('p_win','atr_min','atr_max'):row[key]=format(row[key],'.9f')
        model_rows.append(row)
    entries=[r for r in snap['papers'] if r['simulated_entry']]
    counts=Counter(r['status'] for r in entries)
    resolved=[r for r in entries if r['status'] in ('WIN','LOSS','TIE','UNAVAILABLE')]
    last=max(resolved,key=lambda r:r['expiry_target']) if resolved else None
    summary=dict(schema=1,source=SOURCE,logic=LOGIC,config_hash=p['config_hash'],feed_hash=p['feed_hash'],policy_hash=p['policy_hash'],
        asof=asof,signals=len(entries),wins=counts['WIN'],losses=counts['LOSS'],ties=counts['TIE'],unavailable=counts['UNAVAILABLE'],
        pending=counts['OPEN'],last_target=last['entry_target'] if last else 0,last_direction=last['direction'] if last else 0,
        last_result={'WIN':1,'LOSS':-1,'TIE':0,'UNAVAILABLE':9}.get(last['status'],8) if last else 8)
    report.update(summary=summary,audit=snap['audit'],native_records=snap['records'],source_policy=p,
        input_journal_last_sha256=hashlib.sha256((source/f"event_{snap['records']:012}.bin").read_bytes()).hexdigest())
    for name,rows in [('paper_trades_v207.csv',snap['papers']),('confirmed_reference_v207.csv',snap['references'])]:
        columns=list(rows[0]) if rows else ['source','signal_id','status']
        atomic(source/name,csv_bytes(columns,rows))
    atomic(source/'paper_summary_v207.csv',csv_bytes(SUMMARY_COLUMNS,[summary]))
    atomic(source/'learning_report_v207.json',(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8'))
    # Publish model last: an interrupted report write cannot publish half a model.
    atomic(source/'learning_model_v207.csv',csv_bytes(MODEL_COLUMNS,model_rows))
    return report
