"""Diagnose raw Tester/live journals or a compatible prepared cache; no training."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from intelligence.prepared_history import load
from intelligence.execution_review import write


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, help='Stopped/copied raw Tester or LIVE_MT4 journal, or prepared cache')
    p.add_argument('--prepared', type=Path)
    p.add_argument('--observer-folder', type=Path)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    if a.source is not None and a.prepared is not None:
        p.error('Choose --source or --prepared, not both')
    source = a.source or a.prepared or Path(input('Paste completed Tester folder, stopped LIVE journal copy, OR prepared cache: ').strip().strip('"'))
    raw = source.is_dir() and (source/'data_origin.csv').is_file()
    if source.is_dir() and not raw:
        source = source/'prepared_history_v211.json.gz'
    observer = a.observer_folder
    if raw and observer is not None:
        p.error('Raw diagnosis uses observers from the same original journal only')
    if a.source is None and a.prepared is None and observer is None and not raw:
        text = input('Optional ORIGINAL Tester folder with execution_diagnostics_*.csv (Enter to skip): ').strip().strip('"')
        observer = Path(text) if text else None
    if observer is not None and not observer.is_dir():
        p.error('Observer folder does not exist')
    output = a.output or ROOT/'diagnostics_models'/('execution_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    for parent in (source.resolve() if raw else source.resolve().parent, observer.resolve() if observer else None):
        if parent is not None and (output.resolve() == parent or parent in output.resolve().parents):
            p.error('Output must be outside input folders')
    print('V2.24 execution diagnosis | read-only | no training or guard changes', flush=True)
    if raw:
        from intelligence.execution_journals import diagnose
        from intelligence.progress import ConsoleProgress
        progress = ConsoleProgress()
        progress.state = dict(stage='CHAN DOAN', detail='Read-only journal verification')
        with progress:
            def show(event):
                event = dict(event)
                event['stage'] = 'KIEM TRA BIN' if event.get('unit') == 'BIN' else 'KIEM TRA INPUT'
                progress(event)
            report = diagnose(source, output, show)
    else:
        snapshot, digest = load(source)
        report = write(snapshot, digest, output, observer)
    with zipfile.ZipFile(output/'execution_review_v224.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in ('execution_review.json', 'execution_review.csv', 'input_quality.json'):
            if (output/name).is_file(): archive.write(output/name, name)
    print(json.dumps(dict(status=report['status'], classifications=report['classifications'], output=str(output.resolve())), indent=2))
    print('Send execution_review_v224.zip for review. Preserve the original journal.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        print('BLOCKED: '+str(error), file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        raise SystemExit(130)
