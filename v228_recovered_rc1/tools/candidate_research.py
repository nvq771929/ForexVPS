"""V2.24 Binary Option candidate research. No broker orders or native model activation."""
import argparse,json,sys,time,zipfile
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from intelligence.candidate_data import read
from intelligence.candidate_rules import summarize
from intelligence.candidate_registry import update
from intelligence.demo_learning import atomic
from intelligence.progress import ConsoleProgress
from intelligence.lease import exclusive
from intelligence.live_review import write as live_review
from intelligence.session_observation import publish
from intelligence.economic_calendar import Worker
from intelligence.news_review import write as news_review
from intelligence.manual_signals import review as manual_review


def resolve(source):
    source=source.resolve()
    if (source/'MQL4/Files/BO_V2').is_dir():
        candidates=sorted((source/'MQL4/Files/BO_V2').glob('*EURUSD'))
        if len(candidates)!=1:raise ValueError('Paste the exact journal folder; several or no EURUSD instances found')
        source=candidates[0]
    if source.is_dir() and not (source/'data_origin.csv').is_file():source=source/'prepared_history_v211.json.gz'
    if not source.exists():raise ValueError('Candidate input does not exist')
    return source


def run(source,output):
    progress=ConsoleProgress();progress.state=dict(stage='UNG VIEN',detail='Verify immutable native prefix')
    with progress:
        snapshot=read(source,progress)
        rules=summarize(source,snapshot)
        result=update(snapshot,output,rules,progress)
        current=live_review(source,snapshot,rules,output,result['run'])
        try:manual=manual_review(source,snapshot,output)
        except (OSError,ValueError,KeyError,TypeError) as error:
            manual=dict(status='INVALID_MANUAL_BOOK',error_type=type(error).__name__,learning_active=False,activation_allowed=False)
            atomic(output/'manual_signal_review.json',(json.dumps(manual,indent=2)+'\n').encode())
            (output/'manual_signals.csv').unlink(missing_ok=True)
        result['manual_book_status']=manual['status']
        result.update(diagnostic_native_records=current['native_records'],diagnostic_asof_broker_ms=current['native_asof_broker_ms'],
            diagnostic_rule_rows=rules.get('verified_rows',0),session_observer_rows=current['clock_audit']['rows'])
    atomic(output/'latest_status.json',(json.dumps(result,indent=2)+'\n').encode())
    news_review(output/'news_cache',output,int(time.time()))
    run_folder=output/result['run']
    temporary=output/'candidate_review_v224.tmp'
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in ('candidate_report.json','rule_diagnostics.json'):
            archive.write(run_folder/name,name)
        archive.write(output/'latest_status.json','latest_status.json')
        archive.write(output/'registry.json','registry.json')
        for name in ('live_session_review.json','rule_diagnostics_current.json','session_observer_audit.json','session_candidates.csv','manual_signal_review.json','manual_signals.csv','slot_diagnostics_v222.json','news_source_review_v222.json','news_snapshot_v222.json','news_raw_v222.json'):
            if (output/name).is_file():archive.write(output/name,name)
    temporary.replace(output/'candidate_review_v224.zip')
    print(json.dumps(result,indent=2),flush=True)
    sessions=current['opportunities_by_anchor_session']
    print('Current observations | BIN '+str(current['native_records'])+' | anchors '+str(current['anchors'])+
        ' | LOCK '+str(current['locks'])+' | candidates '+str(current['registered_candidates'])+
        ' | sessions '+json.dumps({k:v['anchors'] for k,v in sessions.items()})+' | OBSERVE_ONLY',flush=True)
    print('Manual publications | '+json.dumps(manual.get('counts',{}))+' | '+manual['status'],flush=True)
    print('Research only. Native decisions unchanged. Review: '+str(output/'candidate_review_v224.zip'),flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path)
    p.add_argument('--output',type=Path);p.add_argument('--watch',action='store_true');p.add_argument('--interval',type=int,default=300)
    a=p.parse_args()
    source=resolve(a.source or Path(input('Paste exact LIVE journal, sealed TESTER folder, or prepared_history_v211.json.gz: ').strip().strip('"')))
    if a.watch and (not source.is_dir() or 'LIVE_MT4' not in (source/'data_origin.csv').read_text()):p.error('--watch requires a LIVE_MT4 journal')
    if a.interval<30:p.error('Interval must be at least 30 seconds')
    output=(a.output or ROOT/'candidate_research'/('live_'+source.name if a.watch else 'history_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))).resolve()
    parent=source if source.is_dir() else source.parent
    if output==parent or parent in output.parents or output in source.parents:p.error('Input and output must be separate non-nested folders')
    output.mkdir(parents=True,exist_ok=True)
    print('V2.24 | EURUSD Binary Option | retrospective candidate research | no native filter',flush=True)
    if not a.watch:
        with exclusive(output/'candidate_tool.lock'):run(source,output)
        return 0
    # Single native bridge publisher, independent of output directory and the demo learner.
    with exclusive(source/'context_writer_v216.lock'):
        worker=Worker(output/'news_cache').start();next_review=0
        try:
            while True:
                try:
                    bridge=publish(source,output/'news_cache')
                    print('Session/news bridge | '+str(bridge['published_utc'])+' UTC | cached news '+
                        bridge['news_status']+' | events '+str(bridge['tracked_events'])+'/'+str(bridge['scope_events'])+' | OBSERVE_ONLY',flush=True)
                    if time.monotonic()>=next_review:
                        with exclusive(output/'candidate_tool.lock'):run(source,output)
                        next_review=time.monotonic()+a.interval
                except (OSError,ValueError,RuntimeError,KeyError,TypeError) as error:
                    print('WAIT/BLOCKED: '+str(error),file=sys.stderr,flush=True)
                time.sleep(30)
        finally:worker.close()


if __name__=='__main__':
    try:raise SystemExit(main())
    except KeyboardInterrupt:raise SystemExit(130)
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as error:
        print('BLOCKED: '+str(error),file=sys.stderr);raise SystemExit(1)
