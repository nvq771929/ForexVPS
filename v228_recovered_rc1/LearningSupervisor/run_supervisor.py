"""Portable CLI. Python 3.11+; collection and audit use standard library only."""
import argparse
import json
from pathlib import Path
import time
import os
import sys
import subprocess
from supervisor.store import Store,atomic
from supervisor.collector import Collector
from supervisor.audit import audit

def main():
    p=argparse.ArgumentParser(description='V2.24 Binary MT4 signal observer; EA control disabled')
    p.add_argument('command',choices=['watch','collect','audit','train','dashboard','export','cycle'])
    p.add_argument('--source',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--dataset',type=Path)
    p.add_argument('--model',type=Path)
    p.add_argument('--paths',action='store_true',help='Batch tick-path audit including WAIT decisions')
    p.add_argument('--broker-utc-offset-minutes',type=int,help='Explicitly verified server clock; e.g. UTC+0 = 0')
    p.add_argument('--common-dir',type=Path,help='Optional actual Terminal/Common/Files directory; telemetry only')
    p.add_argument('--no-auto-research',action='store_true',help='Disable the separate background audit/train worker')
    args=p.parse_args()
    if args.broker_utc_offset_minutes is not None and not -720<=args.broker_utc_offset_minutes<=840:
        p.error('Broker offset out of range')
    args.output=args.output.resolve()
    if args.source:
        journal=args.source.resolve()
        if journal==args.output or journal in args.output.parents or args.output in journal.parents:
            p.error('Output and journal must be separate, non-nested directories')
    args.output.mkdir(parents=True,exist_ok=True)
    # Atomic directory mutex is shared by all mutations, including TRAIN.
    # Watch may be stopped with Ctrl+C before AUDIT/TRAIN, while EA keeps running.
    lock=args.output/'.writer-lock'
    try:lock.mkdir()
    except FileExistsError:raise SystemExit('Output is busy. Close the other supervisor CMD; see recovery instructions if it crashed.')
    (lock/'owner.json').write_text(json.dumps(dict(pid=os.getpid(),created_utc=time.time())))
    store=None
    try:
        if args.command=='train':
            if not args.dataset:p.error('--dataset required')
            from supervisor.learning import train
            print(json.dumps(train(args.dataset,args.output/'models'),indent=2));return
        if not args.source:p.error('--source journal directory required')
        store=Store(args.output);collector=Collector(args.source,store)
        if args.command=='export':
            from supervisor.packaging import export_review
            print(export_review(args.output));return
        if args.command in ('audit','cycle'):
            result=audit(collector,args.paths,args.broker_utc_offset_minutes)
            from supervisor.knowledge import summarize
            summarize(result,store)
            if args.command=='cycle':
                from supervisor.learning import train
                train(args.output/'audited_dataset.json',args.output/'models')
            from supervisor.dashboard import render
            render(collector,args.common_dir)
            print(json.dumps(dict(status='AUDITED',rows=len(result['rows']),sha256=result['sha256']),indent=2));return
        model=None
        if args.model:
            from supervisor.learning import load_model
            model=load_model(args.model);store.put('model',model['model_id'],model);store.commit()
        if args.command=='watch' and collector.origin!='LIVE_MT4':
            p.error('WATCH accepts LIVE_MT4 only. Use COLLECT/AUDIT for completed Tester data.')
        from supervisor.dashboard import render
        from supervisor.forecast import forecast
        last_check=time.monotonic();base_wall=time.time();base_mono=time.monotonic();clock_ok=True
        attempted=set();child=None;last_research=-float('inf');last_merged=None
        while True:
            collector.poll()
            if args.command=='watch' and not args.no_auto_research:
                if (child is None or child.poll() is not None) and time.monotonic()-last_research>=900:
                    research=args.output/'research'
                    if not (research/'.writer-lock').exists():
                        command=[sys.executable,str(Path(__file__).resolve()),'cycle','--source',str(args.source.resolve()),'--output',str(research)]
                        if args.broker_utc_offset_minutes is not None:
                            command+=['--broker-utc-offset-minutes',str(args.broker_utc_offset_minutes)]
                        research.mkdir(exist_ok=True)
                        with (research/'worker.log').open('ab') as log:
                            env=dict(os.environ,OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
                            child=subprocess.Popen(command,stdout=log,stderr=log,env=env)
                        atomic(args.output/'research_worker_status.json',dict(state='RUNNING',started_utc_ms=time.time_ns()//1000000))
                        last_research=time.monotonic()
                if child is not None and child.poll() is not None:
                    worker_status=args.output/'research_worker_status.json'
                    old=json.loads(worker_status.read_text()) if worker_status.exists() else {}
                    if old.get('state')=='RUNNING':
                        atomic(worker_status,dict(state='FINISHED' if child.returncode==0 else 'FAILED',
                            exit_code=child.returncode,finished_utc_ms=time.time_ns()//1000000))
                # Import only a complete, audited, same-source immutable dataset.
                dataset_path=args.output/'research/audited_dataset.json'
                if dataset_path.exists():
                    stamp=dataset_path.stat().st_mtime_ns
                    if stamp!=last_merged:
                        from supervisor.learning import verify_dataset
                        from supervisor.store import digest
                        dataset=verify_dataset(json.loads(dataset_path.read_text()))
                        if dataset['identity_hash']!=digest(collector.identity):raise ValueError('Background audit source differs')
                        for r in dataset['rows']:
                            c=store.get('case',r['case']['signal_id'])
                            if c is not None:
                                if c!=r['case']:raise ValueError('Background features differ')
                                store.put('label',c['signal_id'],r['label'])
                        store.commit();last_merged=stamp
                # New frozen weights may enter shadow observation only.
                training=args.output/'research/models/current_model.json'
                if args.model is None and training.exists():
                    training_state=json.loads(training.read_text())
                    model_path=training_state.get('model_file')
                    if model_path and (model is None or model['model_id']!=training_state['model_id']):
                        from supervisor.learning import load_model
                        model=load_model(model_path)
                        if model['policy']==collector.policy:
                            store.put('model',model['model_id'],model);store.commit();attempted=set()
                        else:model=None
            if abs((time.time()-base_wall)-(time.monotonic()-base_mono))>2:clock_ok=False
            if model:
                for c in store.all('case'):
                    if store.get('withheld',c['signal_id']):continue
                    if c['signal_id'] not in attempted:
                        forecast(store,c,model,collector.origin,args.broker_utc_offset_minutes,clock_ok)
                        attempted.add(c['signal_id'])
            if time.monotonic()-last_check>60:
                collector.verify_batch();last_check=time.monotonic()
            s=render(collector,args.common_dir)
            if args.command!='watch':print(json.dumps(s,indent=2));return
            print(f"SHADOW | BIN {s['native_records']} | official {s['official_cases']} | audited {s['audited_decisive']} | pre-entry forecasts {s['prospective']} | EA control OFF",flush=True)
            time.sleep(2)
    except KeyboardInterrupt:
        print('Stopped supervisor; EA was not changed.')
    except Exception as ex:
        if store is not None and 'collector' in locals():
            from supervisor.dashboard import render
            render(collector,error=str(ex))
        raise
    finally:
        if store is not None:store.close()
        (lock/'owner.json').unlink(missing_ok=True);lock.rmdir()

if __name__=='__main__':main()
