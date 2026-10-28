"""Train TCN and fixed Logistic/HGB baselines from the completed V2.11 prepared cache."""
import argparse
from datetime import datetime
import hashlib
import zipfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepared', type=Path)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    source = a.prepared or Path(input('Paste prepared_history_v211.json.gz file OR its Train-History output folder: ').strip().strip('"'))
    if source.is_dir():
        source = source/'prepared_history_v211.json.gz'
    if not source.is_file():
        p.error('Select the V2.11 prepared cache, not the raw Tester folder')
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    output = a.output or ROOT/'deep_models'/('experiment_'+stamp)
    if output.resolve() == source.resolve().parent or source.resolve().parent in output.resolve().parents:
        p.error('Use an output outside the input folder')
    # Imports are lazy: existing Train-History/live learning do not need torch.
    try:
        from intelligence.deep_learning import train, json_bytes
    except ImportError as error:
        raise RuntimeError('Run Install-Deep-Learning.cmd once; CPU PyTorch is required for deep training') from error
    from intelligence.prepared_history import load
    from intelligence.demo_learning import atomic
    from intelligence.progress import ConsoleProgress, notify
    from intelligence.execution_review import write
    print('V2.24 | CPU TCN experiment, offline only. Existing EA/filter stays unchanged.', flush=True)
    with ConsoleProgress(log_path=ROOT/'history_logs'/('deep_'+stamp+'.log')) as progress:
        notify(progress, 'read', detail='Validate completed cache; no event BIN reread')
        content = source.read_bytes()
        # load() verifies the internal payload; also bind the exact file used.
        file_digest = hashlib.sha256(content).hexdigest()
        snapshot, digest = load(source)
        if hashlib.sha256(source.read_bytes()).hexdigest() != file_digest:
            raise ValueError('Prepared input changed during read')
        report = train(snapshot, digest, output, progress)
        atomic(output/'input_receipt.json', json_bytes(dict(prepared_file_sha256=file_digest,
               dataset_sha256=digest, original_cutoff=snapshot['asof'], event_read_passes=0)))
        write(snapshot, digest, output/'execution_review')
        review_names=['deep_research_report.json','deep_comparison.json','experiment_plan.json','feature_migration.json',
            'candidate_quality_report.json','runtime_fingerprint.json','learning_curves.csv','input_receipt.json','inner_selection.json',
            'execution_review/execution_review.json','execution_review/execution_review.csv']
        with zipfile.ZipFile(output/'training_review_v224.zip','w',zipfile.ZIP_DEFLATED) as archive:
            for name in review_names:
                if (output/name).is_file():archive.write(output/name,name)
    print(report['status'], flush=True)
    print('Output: '+str(output.resolve()), flush=True)
    print('Send training_review_v224.zip for review (reports, migration audit, learning curves and ENTRY diagnostics).')
    print('Research models cannot import into MT4. No new Strategy Tester run is required.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        print('BLOCKED: '+str(error), file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print('CANCELED. Inputs unchanged; rerun into a fresh output directory.', file=sys.stderr)
        raise SystemExit(130)
