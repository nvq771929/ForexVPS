"""Build a source-only Tester research bundle; never include user datasets."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise SystemExit('Use a new output ZIP; retain previous releases.')
    baseline=json.loads((ROOT/'BASELINE_V229_HEADERS.json').read_text())
    for name,expected in baseline.items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
    a=ROOT/'mt4';b=ROOT/'MQL4'
    assert {p.relative_to(a):p.read_bytes() for p in a.rglob('*') if p.is_file()}=={p.relative_to(b):p.read_bytes() for p in b.rglob('*') if p.is_file()}
    assert len(list((a/'Presets').glob('*.set')))==5
    files=[p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    allowed={'.mq4','.mqh','.set','.hpp','.py','.md','.json'}
    assert all(p.suffix in allowed and not p.is_symlink() for p in files)
    manifest={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    prefix='ForexVPS_V231_Tester_Research/'
    with zipfile.ZipFile(args.output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(files):z.write(p,prefix+p.relative_to(ROOT).as_posix())
        z.writestr(prefix+'MANIFEST_SHA256.json',json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(args.output) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(manifest)+1
        for name,want in manifest.items():assert hashlib.sha256(z.read(prefix+name)).hexdigest()==want,name
    digest=hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.output.with_suffix(args.output.suffix+'.sha256').write_text(digest+'  '+args.output.name+'\n')
    print(json.dumps({'zip':str(args.output),'sha256':digest,'entries':len(manifest)+1,'crc_and_manifest_verified':True}))


if __name__=='__main__':main()
