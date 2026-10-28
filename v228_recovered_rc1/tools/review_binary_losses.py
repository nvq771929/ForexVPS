"""Read-only Binary loss study from a completed, copied MT4 Tester journal.

No training, news reconstruction, parameter optimization or EA state writes.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from intelligence.candidate_data import read
from intelligence.manual_signals import review
from intelligence.loss_research import analyze, write
from intelligence.execution_journals import input_quality
from intelligence.progress import ConsoleProgress


def development_cutoff(text):
    return int(datetime.strptime(text, '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp())


def tick_prefix(source, cutoff):
    """Called after full input identity/sequence validation. Bind the bytes again."""
    chunks = []
    block = []
    manifests = []
    dtype = [('ms', '<i8'), ('bid', '<f8'), ('ask', '<f8')]
    for path in sorted(source.glob('input_*.csv')):
        digest = hashlib.sha256()
        def lines(stream):
            for raw in stream:
                digest.update(raw)
                yield raw.decode('utf-8-sig')
        with path.open('rb') as stream:
            for r in csv.DictReader(lines(stream)):
                ms = int(r['time_ms_estimated'])
                if r['event_type'] == 'TICK' and ms < cutoff*1000:
                    block.append((ms, float(r['bid']), float(r['ask'])))
                    if len(block) >= 100000:
                        chunks.append(np.array(block, dtype=dtype))
                        block.clear()
        manifests.append(dict(name=path.name, bytes=path.stat().st_size, sha256=digest.hexdigest()))
    if block:
        chunks.append(np.array(block, dtype=dtype))
    return np.concatenate(chunks) if chunks else np.empty(0, dtype=dtype), manifests


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--development-end-exclusive', help='Frozen entry/outcome cutoff, broker YYYY-MM-DD')
    p.add_argument('--broker-utc-offset-minutes', type=int, help='Only when independently confirmed for the whole study')
    a = p.parse_args()
    source = a.source or Path(input('Paste COMPLETED/copied Binary TESTER journal folder: ').strip().strip('"'))
    end = a.development_end_exclusive or input('Frozen development END EXCLUSIVE broker date (YYYY-MM-DD): ').strip()
    cutoff = development_cutoff(end)
    output = a.output or ROOT/'loss_research'/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    if not (source/'tester_complete.csv').is_file():
        p.error('Need a complete Binary TESTER journal. Live and Forex are separate cohorts.')
    if output.resolve() == source.resolve() or source.resolve() in output.resolve().parents:
        p.error('Output must be outside the source journal')
    if output.exists() and any(output.iterdir()):
        p.error('Use a fresh output directory')
    initial = {q.name: (q.stat().st_size, q.stat().st_mtime_ns) for q in source.iterdir() if q.is_file()}
    print('V2.24 Binary postmortem | read-only | keep originals | no orders/model fit', flush=True)
    with ConsoleProgress() as progress:
        snapshot = read(source, progress=progress)
        manual = review(source, snapshot)
        quality = input_quality(source, snapshot['origin'], progress=progress)
        ticks, manifests = tick_prefix(source, cutoff)
    if manifests != quality['input_files']:
        raise ValueError('Input bytes changed between validation and path analysis')
    result = analyze(snapshot, manual, ticks, broker_offset_minutes=a.broker_utc_offset_minutes, development_end=cutoff)
    # Stable stopped copy: no advancing LIVE prefix or partially written input is accepted.
    final = {q.name: (q.stat().st_size, q.stat().st_mtime_ns) for q in source.iterdir() if q.is_file()}
    if initial != final:
        raise ValueError('Source changed; use a stopped, copied journal')
    result[0]['input_files_sha256'] = manifests
    result[0]['source_snapshot'] = 'SEALED_NATIVE_AND_STABLE_LOCAL_INPUTS'
    summary = write(output, result)
    archive = output/'binary_loss_review_v224.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for q in sorted(output.iterdir()):
            if q.suffix in ('.json', '.csv'):
                z.write(q, q.name)
    print(json.dumps(dict(development=summary['development'], loss_patterns=summary['loss_patterns'],
                         accepted_filters=[], output=str(archive.resolve())), indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        print('BLOCKED: '+str(error), file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        raise SystemExit(130)
