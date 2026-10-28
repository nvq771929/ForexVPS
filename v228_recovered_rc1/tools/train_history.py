"""Train separate execution/reference and price-research models from frozen history."""
import argparse
import json
from pathlib import Path
import sys
from datetime import datetime

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from intelligence.history_learning import train_history,train_prepared
from intelligence.progress import ConsoleProgress


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    inputs=parser.add_mutually_exclusive_group()
    inputs.add_argument('--source',type=Path)
    inputs.add_argument('--prepared',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--progress-interval',type=float,default=2.,help='Console heartbeat seconds (0.1..60, default 2)')
    parser.add_argument('--progress-log',type=Path,help='Progress log outside input and output folders')
    args=parser.parse_args()
    source=args.source or args.prepared or Path(input('Paste completed TESTER folder OR prepared_history_v211.json.gz file: ').strip().strip('"'))
    prepared=bool(args.prepared) or source.is_file()
    if prepared:
        if not source.is_file():parser.error('Prepared history must be an existing .json.gz file')
        source_parent=source.resolve().parent
    else:
        if not (source/'data_origin.csv').is_file():parser.error('Choose the exact tester/files/BO_V2/<tag>_TESTER_EURUSD folder')
        source_parent=source.resolve()
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    output=args.output or ROOT/'history_models'/((source.parent.name if prepared else source.name)+'_'+stamp)
    log=args.progress_log or ROOT/'history_logs'/('train_'+stamp+'.log')
    if not .1<=args.progress_interval<=60:parser.error('progress-interval must be 0.1..60 seconds')
    if log.resolve()==source_parent or source_parent in log.resolve().parents:
        parser.error('Progress log must be outside the input dataset folder')
    if log.resolve()==output.resolve() or output.resolve() in log.resolve().parents:
        parser.error('Progress log must be outside the fresh model output folder')
    print('V2.24 | Separate execution labels and PRICE RESEARCH; progress/ETA is per stage.',flush=True)
    print(f'Progress log: {log.resolve()}',flush=True)
    with ConsoleProgress(log_path=log,interval=args.progress_interval) as progress:
        report=(train_prepared if prepared else train_history)(source,output,progress=progress)
    print(json.dumps(dict(execution_model_status=report['status'],execution_eligible_labels=report['eligible_labels'],
        execution_counts=report['counts'],research_status=report['research_status'],research_eligible_labels=report['research_eligible_labels'],
        research_counts=report['research_counts'],t1_research_status=report['t1_research_status'],t1_research_eligible_labels=report['t1_research_eligible_labels'],output=str(output.resolve()),prepared_history=report['prepared_history']),indent=2),flush=True)
    if report['status']=='QUALIFIED_FOR_OBSERVATION':print('history_model.json alone may use Import-History-Model.cmd; OBSERVE only.')
    else:print('Execution model NOT qualified: no history_model.json for import.')
    print('Review learning_diagnostics.json, execution_diagnostics.json and t1_research_report.json.')
    print('Research model is offline only, even if qualified. Do not import research_model*.json into the EA.')
    print('Next run may select prepared_history_v211.json.gz to avoid reading the original BIN files again.')
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as error:print(f'BLOCKED: {error}',file=sys.stderr);raise SystemExit(1)
    except KeyboardInterrupt:
        print('Canceled. Sources unchanged. If prepared_history_v211.json.gz exists, select it next time; otherwise restart from raw journals.',file=sys.stderr)
        raise SystemExit(130)
