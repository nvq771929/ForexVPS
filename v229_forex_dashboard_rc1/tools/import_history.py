"""Transfer qualified history weights to an existing V224 LIVE_MT4 dataset for observation."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from intelligence.history_learning import import_history


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',type=Path)
    parser.add_argument('--source',type=Path)
    args=parser.parse_args()
    model=args.model or Path(input('Paste qualified history_model.json path: ').strip().strip('"'))
    settings=ROOT/'demo-learning-path.txt'
    if args.source:source=args.source
    elif settings.is_file():source=Path(settings.read_text(encoding='utf-8').strip())
    else:source=Path(input('Paste LIVE journal folder (existing compatible V207/V208/V209/V210/V213/V215/V222/V224 chart): ').strip().strip('"'))
    if not (source/'demo_policy.csv').is_file():
        candidate=source/'MQL4/Files/BO_V2/v229_demo_EURUSD'
        if candidate.is_dir():source=candidate
    receipt=import_history(model,source)
    settings.write_text(str(source.resolve())+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))
    print('Frozen historical weights imported as OBSERVE. Run Start-Demo-Learning.cmd for genuine live monitoring.')
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,RuntimeError) as error:print(f'BLOCKED: {error}',file=sys.stderr);raise SystemExit(1)
    except KeyboardInterrupt:raise SystemExit(0)
