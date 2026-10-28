"""V2.24 read-only storage/replay diagnosis; accepts stopped journal copies."""
import argparse,json,sys,zipfile
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from intelligence.storage_review import review
from intelligence.demo_learning import atomic


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    source=(a.source or Path(input('Paste stopped/copied journal folder: ').strip().strip('"'))).resolve()
    if not (source/'data_origin.csv').is_file():p.error('Exact journal folder with data_origin.csv required')
    output=(a.output or ROOT/'diagnostics_models'/('storage_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))).resolve()
    if output==source or source in output.parents or output in source.parents:p.error('Separate non-nested output folder required')
    if output.exists() and any(output.iterdir()):p.error('Fresh output required')
    result=review(source);output.mkdir(parents=True,exist_ok=True)
    atomic(output/'storage_review.json',(json.dumps(result,indent=2)+'\n').encode())
    with zipfile.ZipFile(output/'storage_review_v224.zip','w',zipfile.ZIP_DEFLATED) as archive:archive.write(output/'storage_review.json','storage_review.json')
    print(json.dumps(dict(status=result['status'],native_failure=result['native_integrity_failure'],replay_issues=len(result['issues']),output=str(output)),indent=2))
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as error:print('BLOCKED: '+str(error),file=sys.stderr);raise SystemExit(1)
