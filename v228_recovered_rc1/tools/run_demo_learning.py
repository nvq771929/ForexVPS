"""Run the Bayesian baseline and frozen logistic challenger on V224 local journals."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from intelligence.demo_learning import update,collect
from intelligence.advanced_learning import update as advanced_update
from intelligence.lease import exclusive


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,help='MQL4/Files/BO_V2/v228_demo_EURUSD folder')
    parser.add_argument('--watch',action='store_true')
    parser.add_argument('--interval',type=int,default=30)
    args=parser.parse_args(argv)
    try:
        import sklearn,numpy
    except ImportError:
        parser.error('Run Install-Demo-Learning.cmd first (Python 3.11+ required).')
    if not 5<=args.interval<=3600:parser.error('interval must be 5..3600 seconds')
    settings=ROOT/'demo-learning-path.txt'
    source=args.source
    if source is None:
        if settings.is_file():source=Path(settings.read_text(encoding='utf-8').strip())
        else:
            value=input('Paste MT4 Data Folder or the V224 journal folder: ').strip().strip('"')
            if not value:parser.error('A local folder is required')
            source=Path(value)
    if not (source/'demo_policy.csv').is_file():
        candidate=source/'MQL4'/'Files'/'BO_V2'/'v228_demo_EURUSD'
        if candidate.is_dir():source=candidate
    if not source.is_dir() or not (source/'demo_policy.csv').is_file():
        parser.error('Attach V224 first; select its BO_V2/v228_demo_EURUSD folder containing demo_policy.csv')
    source=source.resolve();settings.write_text(str(source)+'\n',encoding='utf-8')
    with exclusive(source/'learner.lock'):
        return watch(source,args)


def watch(source,args):
    print('V224 local learner | MT4_SIMULATED | no broker orders | Ctrl+C to stop.',flush=True)
    while True:
        try:
            snapshot=collect(source)
            report=update(source,snapshot);s=report['summary']
            ml=advanced_update(source,snapshot)
            applied=sum(c['applied_decision']!=0 for c in report['contexts'])
            print(f"ENTRY MT4 | Broker cutoff {s['asof']} | W {s['wins']} L {s['losses']} T {s['ties']} missing {s['unavailable']} open {s['pending']} | contexts {len(report['contexts'])}, Bayesian filters {applied} | ML {ml['status']} / native forecasts {ml.get('native_forecasts',0)}",flush=True)
        except (OSError,ValueError,RuntimeError) as error:
            # Do not print private file contents or publish a model on bad input.
            print(f'WAIT/BLOCKED: {type(error).__name__}: {error}',file=sys.stderr,flush=True)
            if not args.watch:return 1
        if not args.watch:return 0
        try:time.sleep(args.interval)
        except KeyboardInterrupt:return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except KeyboardInterrupt:raise SystemExit(0)
    except (RuntimeError,OSError) as error:
        print(f'BLOCKED: {error}',file=sys.stderr);raise SystemExit(1)
