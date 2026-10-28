"""Diagnose an existing frozen research model without fitting or activation."""
import argparse,json,sys
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from intelligence.prepared_history import load,NAME
from intelligence.learning_diagnostics import read_model,diagnose
from intelligence.demo_learning import atomic,csv_bytes
from intelligence.progress import ConsoleProgress,notify


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folder',type=Path);p.add_argument('--prepared',type=Path);p.add_argument('--model',type=Path);p.add_argument('--output',type=Path);p.add_argument('--t1',action='store_true')
    a=p.parse_args()
    folder=a.folder
    if folder is None and a.prepared is None:folder=Path(input('Paste completed Train-History output folder (cache and candidate model): ').strip().strip('"'))
    cache=a.prepared
    if cache is None:
        cache=next((folder/n for n in (NAME,'prepared_history_v210.json.gz') if (folder/n).is_file()),None)
        if cache is None:p.error('Choose the model output folder containing prepared_history_v211/v210.json.gz')
    model=a.model or (folder or cache.parent)/('t1_research_model_candidate.json' if a.t1 else 'research_model_candidate.json')
    out=a.output or ROOT/'diagnostics_models'/('review_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    for source in (cache,model):
        if out.resolve()==source.resolve().parent or source.resolve().parent in out.resolve().parents:p.error('Output must be outside input folders')
    if out.exists() and any(out.iterdir()):p.error('Use a fresh output directory')
    with ConsoleProgress(log_path=ROOT/'history_logs'/('diagnose_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.log')) as progress:
        notify(progress,'read',detail='Kiem tra cache/model; khong fit lai va khong doc event BIN')
        snapshot,digest=load(cache);artifact=read_model(model)
        report,predictions,groups=diagnose(snapshot,artifact,digest,progress)
        out.mkdir(parents=True,exist_ok=True)
        atomic(out/'learning_diagnostics.json',(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+'\n').encode())
        for name,rows in (('diagnostic_predictions.csv',predictions),('grouped_research.csv',groups)):
            atomic(out/name,csv_bytes(sorted(rows[0]) if rows else ['status'],rows))
    print(json.dumps(dict(status=report['status'],rejections=report.get('rejection_counts'),execution=report['execution'],t1_status=report['t1_status'],output=str(out.resolve())),indent=2))
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as e:print(f'BLOCKED: {e}',file=sys.stderr);raise SystemExit(1)
    except KeyboardInterrupt:raise SystemExit(130)
