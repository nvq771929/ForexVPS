"""Package full V2.29 Forex dashboard after root and supervisor validation."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = 'ForexVPS_Intelligence_V229_Full_RC1_ForexDashboard_Demo_Real.zip'


def content():
    items = {}
    allowed = {'.cpp','.mq4','.mqh','.set','.py','.hpp','.md','.json','.yml','.yaml','.txt','.cmd','.html','.zip'}
    for folder in ('mt4','MQL4','intelligence','tools','tests','docs','.github','LearningSupervisor','validation'):
        for path in sorted((ROOT/folder).rglob('*')):
            if not path.is_file() or any(p in ('__pycache__','.git','runtime') or p.startswith('.venv') for p in path.relative_to(ROOT).parts):
                continue
            if path.suffix in allowed:
                items[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for path in sorted(ROOT.iterdir()):
        if path.is_file() and (path.suffix in {'.md','.json','.txt','.cmd'} or path.name == '.gitignore') and path.name != 'MANIFEST_SHA256.json':
            items[path.name] = path.read_bytes()
    # Preserve every original native header byte for byte.
    baseline = json.loads(items['baseline_v226_sha256.json'])
    for name, digest in baseline.items():
        if not name.startswith('mt4/Include/'):
            continue
        data = items[name]
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('Original native header changed: '+name)
    for name,digest in json.loads(items['baseline_v228_sha256.json']).items():
        if name.startswith('mt4/Include/') and hashlib.sha256(items[name]).hexdigest()!=digest:
            raise ValueError('Delivered V228 header changed: '+name)
    freeze = json.loads(items['LearningSupervisor/assistant/context/candidate_freeze.json'])
    if hashlib.sha256(items['LearningSupervisor/assistant/context/engine.py']).hexdigest() != freeze['files_sha256']['engine.py']:
        raise ValueError('Frozen context engine changed')
    if json.loads(items['LearningSupervisor/local_ai.example.json'])['enabled'] is not False:
        raise ValueError('Local language model must default OFF')
    for name, data in items.items():
        if name.startswith('MQL4/') and data != items.get('mt4/'+name[5:]):
            raise ValueError('Install mirror differs: '+name)
        if name.startswith('/') or '..' in Path(name).parts:
            raise ValueError('Unsafe archive path: '+name)
    for account in ('Demo','Real'):
        for mode in ('Binary','Forex'):
            name=f'mt4/Presets/EURUSD_M5_V229_{mode}_{account}_{"Observe" if mode=="Binary" else "Execute"}_UTC0.set'
            if name not in items:
                raise ValueError('Missing two-chart preset: '+name)
    return items


def passed_log(path):
    text=path.read_text()
    match=re.search(r'Ran (\d+) tests in [\d.]+s\s+OK(?:\s|$)',text)
    if not match or int(match[1]) == 0 or re.search(r'(?m)^(FAILED|ERROR|FAIL:)|skipped=',text):
        raise ValueError('Require completed passing tests without skips: '+str(path))
    return text,int(match[1])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--validation-log',type=Path,required=True)
    p.add_argument('--learning-validation-log',type=Path,required=True)
    p.add_argument('--output-directory',type=Path,required=True)
    args=p.parse_args()
    log,count=passed_log(args.validation_log)
    learning_log,learning_count=passed_log(args.learning_validation_log)
    items=content()
    items['validation/tests.txt']=log.encode()
    items['validation/learning_tests.txt']=learning_log.encode()
    status=json.loads(items['RELEASE_STATUS.json'])
    status.update(release='V2.29',software_version='2.29',next_version='2.30',build_revision='forex-dashboard-news-paths-rc1',
        automated_tests_passed=count,learning_tests_passed=learning_count,automated_tests_skipped=0,
        recovered_release=True,original_v228_byte_identity_verified=False,native_metaeditor_compiled=False,
        windows_terminal_validated=False,market_performance_validated=False,native_strategy_tester_validated=False,
        inherited_native_includes_identical_to_rc3=True,forex_functionality_changed=False,
        binary_strategy_parameters_changed=False,native_guards_changed=False,
        native_header_changes='None: all 39 delivered V228 headers byte-identical; clock and display adapters are scoped in the Expert',
        forex_dashboard=True,forex_dashboard_read_only=True,forex_news_path_resolution_updated=True,delivered_v228_headers_byte_identical=39,dual_chart_semantics_validated=True,clock_observation_contract='V227_CLOCK_OBSERVATION_V1',
        chart_role_contract='V228_CHART_ROLE_V1',real_demo_presets_included=True,
        inherited_historical_corpus_audits_rerun=False,live_calendar_verified=False,remote_backup_verified=False)
    items['RELEASE_STATUS.json']=(json.dumps(status,indent=2)+'\n').encode()
    items['MANIFEST_SHA256.json']=(json.dumps({name:hashlib.sha256(data).hexdigest() for name,data in sorted(items.items())},indent=2)+'\n').encode()
    args.output_directory.mkdir(parents=True,exist_ok=True)
    path=args.output_directory/NAME
    if path.exists():
        p.error('Preserve prior releases; choose a fresh output directory')
    with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(items.items()):
            entry=zipfile.ZipInfo(name,date_time=(2026,10,28,0,0,0))
            entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o644<<16
            z.writestr(entry,data)
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:
            raise ValueError('Release ZIP CRC failed')
        manifest=json.loads(z.read('MANIFEST_SHA256.json'))
        for name,digest in manifest.items():
            if hashlib.sha256(z.read(name)).hexdigest() != digest:
                raise ValueError('Release manifest mismatch: '+name)
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    (args.output_directory/(NAME+'.sha256')).write_text(digest+'  '+NAME+'\n')
    print(json.dumps(dict(path=str(path),files=len(items),bytes=path.stat().st_size,sha256=digest,
        root_tests=count,supervisor_tests=learning_count,metaeditor_compiled=False),indent=2))


if __name__=='__main__':
    main()
