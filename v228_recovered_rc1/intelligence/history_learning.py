"""Train from sealed MT4 Tester journals and transfer frozen weights for live observation."""
import copy
import csv
import hashlib
import json
from pathlib import Path
from time import monotonic

from .advanced_learning import fit,split,evaluate,validate,gates,export,decisive
from .demo_learning import LOGIC,collect,atomic,csv_bytes
from .lease import exclusive
from .signal_features import VERSION
from .native_ledger import event_paths
from .origin import read_origin
from .demo_learning import read_policy
from .progress import notify


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def completion_row(source):
    with (Path(source)/'tester_complete.csv').open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream);rows=list(reader)
        if reader.fieldnames!=['schema','logic','sequence','observed_ms'] or len(rows)!=1:
            raise ValueError('Tester run has no valid completion marker')
    row={k:int(v) for k,v in rows[0].items()}
    if row['schema']!=1 or row['logic']!=LOGIC or row['sequence']<1:
        raise ValueError('Invalid Tester completion identity or sequence')
    return row


def sealed(source,snapshot):
    row=completion_row(source)
    if row['schema']!=1 or row['logic']!=LOGIC or row['sequence']!=snapshot['records'] or row['observed_ms']//1000!=snapshot['asof']:
        raise ValueError('Tester completion marker differs from committed journal')


def dataset_digest(source):
    h=hashlib.sha256()
    files=[Path(source)/n for n in ('data_origin.csv','demo_policy.csv','tester_complete.csv')]
    files+=sorted(Path(source).glob('event_*.bin'))
    for p in files:h.update(p.name.encode());h.update(p.read_bytes())
    return h.hexdigest()


def train_snapshot(snapshot,digest,progress=None):
    """Pure training operation; only the filesystem entry point seals provenance."""
    if snapshot.get('origin')!='BACKTEST_MT4':raise ValueError('Historical training requires a Tester dataset')
    data=[r for r in snapshot['references'] if r['status'] in ('WIN','LOSS','TIE')
        and r['available_at_ms']<snapshot['asof']*1000 and 'features' in r]
    data.sort(key=lambda r:r['entry_target'])
    if any(r['source']!='BACKTEST_MT4_SIMULATED' for r in data):raise ValueError('Mixed live/Tester labels')
    model,fit_info=fit(data,snapshot['asof'],progress=progress);slices=[];failures=[]
    if model:
        _,_,test=split(data);days=sorted({r['entry_target']//86400 for r in test})
        # Evaluate the SAME frozen model on three chronological held-out slices.
        # There is no threshold/hyperparameter search or refitting on these slices.
        blocks=[days[len(days)*i//3:len(days)*(i+1)//3] for i in range(3)]
        notify(progress,'holdouts',done=0,total=3,unit='doan',detail='Cung mot mo hinh, khong hoc lai tren tap test')
        for i,block in enumerate(blocks):
            rows=[r for r in test if r['entry_target']//86400 in block]
            m=evaluate(model,rows)
            failed=[]
            if m['decisive']<50:failed.append('samples')
            if m['selected_decisive']<30:failed.append('selected_samples')
            if m['brier'] is None or m['brier']>=m['bayes_brier']:failed.append('probability_quality')
            if m['stress_roi'] is None or m['stress_roi']<=0:failed.append('stress_roi')
            slices.append(dict(slice=i+1,metrics=m,failures=failed))
            notify(progress,'holdouts',done=i+1,total=3,unit='doan')
        failures=list(model['offline_failures'])
        if any(s['failures'] for s in slices):failures.append('chronological_holdout_slices')
        model['training_origin']='BACKTEST_MT4'
        model['history_dataset_sha256']=digest
    else:failures=['insufficient_or_unusable_training_data']
    qualified=bool(model is not None and not failures)
    artifact=dict(schema=1,kind='V207_HISTORY_LOGISTIC',logic=LOGIC,feature_version=VERSION,
        source_origin='BACKTEST_MT4',label_source='BACKTEST_MT4_SIMULATED',
        tick_provenance='MT4_TESTER_MODEL_UNVERIFIED',history_asof=snapshot['asof'],policy=snapshot['policy'],
        dataset_sha256=digest,eligible_for_live_observation=qualified,
        eligible_for_live_filter=False,production_promoted=False,model=model,
        failures=failures,heldout_slices=slices)
    artifact['payload_sha256']=hashlib.sha256(canonical(artifact)).hexdigest()
    counts={s:sum(r['status']==s for r in snapshot['references']) for s in ('WIN','LOSS','TIE','UNAVAILABLE','OPEN')}
    report=dict(status='QUALIFIED_FOR_OBSERVATION' if qualified else 'NOT_QUALIFIED',source='BACKTEST_MT4_SIMULATED',
        eligible_labels=len(data),counts=counts,native_records=snapshot['records'],fit=fit_info,
        failures=failures,heldout_slices=slices,dataset_sha256=digest,
        live_forward_observations=0,automatic_live_filter=False,
        limitations=['MT4 Every tick may contain generated ticks, not an authentic historical tick feed.',
            'Historical holdouts are backtest evidence; they do not satisfy genuine live forward gates.',
            'A qualified model transfers for scoring/observation; MT4 simulation is not Olymp settlement.'])
    return artifact,report


def train_history(source,output,progress=None):
    started=monotonic()
    source=Path(source);output=Path(output)
    if output.resolve()==source.resolve() or source.resolve() in output.resolve().parents:
        raise ValueError('Write trained artifacts outside the Tester dataset')
    if output.exists() and any(output.iterdir()):raise ValueError('Use a fresh output directory; preserve prior artifacts')
    notify(progress,'discover',detail='Kiem tra nguon, dau ket thuc va liet ke file; chua co tong so')
    policy=read_policy(source)
    if read_origin(source,policy)!='BACKTEST_MT4':raise ValueError('Choose a TESTER dataset, not the live journal')
    completion=completion_row(source)
    metadata={name:(source/name).read_bytes() for name in ('data_origin.csv','demo_policy.csv','tester_complete.csv')}
    paths=event_paths(source)
    if len(paths)!=completion['sequence']:raise ValueError('Tester file count differs from completion marker')
    # Bind the model to EXACTLY the verified bytes used to construct its labels.
    # Preserve V207 digest order, but never reopen event files for hashing.
    digest=hashlib.sha256()
    for name,content in metadata.items():digest.update(name.encode());digest.update(content)
    processed=0;read_bytes=0
    def verified(path,content):
        nonlocal processed,read_bytes
        digest.update(path.name.encode());digest.update(content)
        processed+=1;read_bytes+=len(content)
        if processed%256==0 or processed==len(paths):
            notify(progress,'read',done=processed,total=len(paths),unit='files',detail=f'Da doc {read_bytes/1024**2:,.1f} MiB; kem SHA256')
    notify(progress,'read',done=0,total=len(paths),unit='files',detail='Kiem tra FNV, sequence va SHA256 trong mot luot doc')
    snapshot=collect(source,policy,paths=paths,on_record=verified,progress=progress,include_research=True)
    notify(progress,'labels',done=None,total=None,detail='Kiem tra dau ket thuc va danh sach file on dinh')
    sealed(source,snapshot)
    if any((source/name).read_bytes()!=content for name,content in metadata.items()):
        raise ValueError('Tester metadata changed during training read')
    if read_policy(source)!=policy:raise ValueError('Tester policy changed during training read')
    if [p.name for p in event_paths(source)]!=[p.name for p in paths]:
        raise ValueError('Tester file list changed during training read')
    processing=dict(event_files=processed,event_bytes=read_bytes,event_read_passes=1,from_prepared=False)
    return finish_history(snapshot,digest.hexdigest(),output,processing,progress,started)


def train_prepared(path,output,progress=None):
    from .prepared_history import load
    started=monotonic();path=Path(path);output=Path(output)
    if output.resolve()==path.resolve() or path.resolve().parent==output.resolve() or path.resolve().parent in output.resolve().parents:
        raise ValueError('Write trained artifacts outside the prepared history folder')
    if output.exists() and any(output.iterdir()):raise ValueError('Use a fresh output directory; preserve prior artifacts')
    notify(progress,'read',detail='Doc prepared history: kiem tra SHA256 va hop dong; khong doc lai event BIN')
    snapshot,digest=load(path)
    processing=dict(event_files=0,event_bytes=0,event_read_passes=0,from_prepared=True,
        prepared_input=str(path.resolve()),original_native_records=snapshot['records'])
    return finish_history(snapshot,digest,output,processing,progress,started)


def json_bytes(value):return (json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()


def finish_history(snapshot,digest,output,processing,progress,started):
    from . import research_model
    from .prepared_history import save,NAME
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    # Export the verified read result BEFORE fitting. An interrupted model fit can
    # restart from this frozen local file without reopening hundreds of thousands
    # of immutable journal files. It never advances the original broker cutoff.
    notify(progress,'labels',done=None,total=None,detail='Luu prepared history truoc khi fit; co the dung lai cho lan huan luyen sau')
    save(output/NAME,snapshot,digest)
    atomic(output/'data_funnel.json',json_bytes(snapshot['funnel']))
    funnel_rows=[]
    for stage,values in snapshot['funnel'].items():
        if isinstance(values,dict):
            for reason,count in values.items():
                if isinstance(count,(int,float)):funnel_rows.append(dict(stage=stage,reason=reason,count=count))
    atomic(output/'data_funnel.csv',csv_bytes(['stage','reason','count'],funnel_rows))
    artifact,report=train_snapshot(snapshot,digest,progress=progress)
    research,summary,predictions=research_model.train(snapshot,digest,progress=progress)
    from .learning_diagnostics import diagnose
    from .execution_diagnostics import summarize
    diagnostic,_,grouped=diagnose(snapshot,research,digest,progress)
    t1_predictions=[];t1_grouped=[];t1_artifact=None
    t1_rows=[]
    if snapshot.get('research_t1'):
        from .t1_corrected import with_corrected,KEY
        corrected=with_corrected(snapshot);t1_rows=corrected[KEY]
        atomic(output/'feature_migration.json',json_bytes(corrected['t1_v2_migration']))
        t1_artifact,t1_report,t1_predictions=research_model.train(corrected,digest,progress=progress,research_key=KEY)
        t1_diagnostic,_,t1_grouped=diagnose(corrected,t1_artifact,digest,progress)
        atomic(output/'t1_learning_diagnostics.json',json_bytes(t1_diagnostic))
        atomic(output/'t1_research_model_candidate.json',json_bytes(t1_artifact))
        if t1_artifact['eligible_for_research_review']:atomic(output/'t1_research_model.json',json_bytes(t1_artifact))
    else:
        t1_report=dict(status='REQUIRES_RAW_JOURNALS',eligible_labels=0,
            feature_contract='ANCHOR_T1_UP_V2',automatic_live_filter=False,
            reason='V210 prepared cache lacks T+1 snapshots. Select the original completed Tester folder once; a new Tester run is not required.')
    atomic(output/'t1_research_report.json',json_bytes(t1_report))
    atomic(output/'learning_diagnostics.json',json_bytes(diagnostic))
    atomic(output/'execution_diagnostics.json',json_bytes(summarize(snapshot)))

    report.update(processing=processing,execution_model_status=report['status'],
        research_status=summary['status'],research_eligible_labels=summary['eligible_labels'],
        research_counts=summary['counts'],research_report='research_report.json',
        prepared_history=NAME,data_funnel='data_funnel.json',
        t1_research_status=t1_report['status'],t1_research_eligible_labels=t1_report['eligible_labels'],
        learning_diagnostics='learning_diagnostics.json',execution_diagnostics='execution_diagnostics.json')
    summary.update(prepared_history=NAME,data_funnel='data_funnel.json')
    notify(progress,'export',done=0,total=1,unit='bo ket qua',detail=report['status']+' | '+summary['status'])
    atomic(output/'history_model_candidate.json',json_bytes(artifact))
    atomic(output/'history_report.json',json_bytes(report))
    atomic(output/'research_model_candidate.json',json_bytes(research))
    atomic(output/'research_report.json',json_bytes(summary))
    for name,rows,empty in (
        ('history_reference.csv',snapshot['references'],['source','signal_id','status']),
        ('research_reference.csv',snapshot['research'],['source','sample_id','status']),
        ('research_predictions.csv',predictions,['source','sample_id','p_up','direction']),
        ('t1_research_reference.csv',t1_rows,['source','sample_id','status']),
        ('t1_research_predictions.csv',t1_predictions,['source','sample_id','p_up','direction']),
        ('execution_trace.csv',snapshot.get('execution_traces',[]),['analysis_start','entry_reason']),
        ('grouped_research.csv',grouped,['axis','value']),
        ('t1_grouped_research.csv',t1_grouped,['axis','value'])):
        columns=sorted(rows[0]) if rows else empty
        # Nested vectors are JSON data in CSV cells, never Python expressions.
        flat=[{k:json.dumps(v,separators=(',',':'),allow_nan=False) if isinstance(v,(dict,list,tuple)) else v
            for k,v in row.items()} for row in rows]
        atomic(output/name,csv_bytes(columns,flat))
    if artifact['eligible_for_live_observation']:atomic(output/'history_model.json',json_bytes(artifact))
    if research['eligible_for_research_review']:atomic(output/'research_model.json',json_bytes(research))
    notify(progress,'export',done=1,total=1,unit='bo ket qua',detail=f"{report['status']} | {summary['status']} | {monotonic()-started:.1f}s")
    return report


def read_artifact(path):
    artifact=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(artifact,dict):raise ValueError('Invalid history artifact')
    if artifact.get('label_source')=='BACKTEST_MT4_PRICE_RESEARCH':
        raise ValueError('Research models cannot import into the legacy execution filter; review research_report.json')
    digest=artifact.pop('payload_sha256',None)
    if digest!=hashlib.sha256(canonical(artifact)).hexdigest():raise ValueError('History artifact checksum mismatch')
    if artifact.get('schema')!=1 or artifact.get('kind')!='V207_HISTORY_LOGISTIC' or artifact.get('logic')!=LOGIC or artifact.get('feature_version')!=VERSION:
        raise ValueError('Unsupported history artifact')
    if artifact.get('source_origin')!='BACKTEST_MT4' or artifact.get('label_source')!='BACKTEST_MT4_SIMULATED' or artifact.get('eligible_for_live_observation') is not True:
        raise ValueError('History model did not qualify for live observation')
    model=artifact.get('model');validate(model)
    if model['offline_failures'] or gates(model['offline']) or artifact.get('failures'):
        raise ValueError('History model has failed offline gates')
    slices=artifact.get('heldout_slices',[])
    if len(slices)!=3 or any(s.get('failures') for s in slices):raise ValueError('Historical holdout slices failed')
    artifact['payload_sha256']=digest
    return artifact


def import_history(path,live_source):
    artifact=read_artifact(path);source=Path(live_source)
    with exclusive(source/'learner.lock'):
        snapshot=collect(source);p=snapshot['policy'];asof=snapshot['asof']
        if snapshot['origin']!='LIVE_MT4':raise ValueError('Import target must be a live MT4 journal, not Tester')
        if artifact['policy']!=p:raise ValueError('History and live policy/feed/horizon differ; use matching configurations')
        if artifact['history_asof']>=asof:raise ValueError('Historical training must finish before the live import time')
        state_path=source/'advanced_state_v207.json'
        if state_path.is_file():
            existing=json.loads(state_path.read_text())
            identity={k:p[k] for k in ('logic','config_hash','feed_hash','policy_hash','horizon')}
            if existing.get('identity')!=identity or existing.get('model') is not None:
                raise ValueError('Live model already exists or state differs; preserve it and use a fresh InstanceTag')
        elif (source/'advanced_model_v207.csv').is_file() or (source/'advanced_seen.csv').is_file():
            raise ValueError('Live model state is missing; preserve evidence')
        model=copy.deepcopy(artifact['model'])
        model.update(created=asof,model_id=asof*1000+902,phase='OBSERVE',active_since=0,
            historical_created=artifact['model']['created'],imported_history_sha256=artifact['payload_sha256'],
            training_origin='BACKTEST_MT4',history_holdout_slices=artifact['heldout_slices'])
        validate(model)
        state=dict(schema=1,identity={k:p[k] for k in ('logic','config_hash','feed_hash','policy_hash','horizon')},
            model=model,last_asof=asof,last_attempt_day=asof//86400)
        atomic(state_path,(json.dumps(state,indent=2,allow_nan=False)+'\n').encode())
        export(source,p,asof,model)  # phase is always OBSERVE, never ACTIVE
        receipt=dict(source='BACKTEST_MT4',target='LIVE_MT4',model_id=model['model_id'],import_asof=asof,
            historical_dataset_sha256=artifact['dataset_sha256'],history_artifact_sha256=artifact['payload_sha256'],
            phase='OBSERVE',live_forward_observations=0,automatic_filter=False)
        atomic(source/'history_import_v207.json',(json.dumps(receipt,indent=2)+'\n').encode())
        return receipt
