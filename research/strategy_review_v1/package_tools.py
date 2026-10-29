"""Package source/protocol only; user market data and scores never enter Git."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parent

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('retain old bundles; choose a new output')
    files=[x for x in ROOT.rglob('*') if x.is_file() and '__pycache__' not in x.parts]
    assert all(x.suffix in {'.py','.cpp','.json','.md','.txt'} and not x.is_symlink() for x in files)
    manifest={x.relative_to(ROOT).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted(files)}
    a.output.parent.mkdir(parents=True,exist_ok=True);prefix='Strategy_Review_V1/'
    with zipfile.ZipFile(a.output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for x in sorted(files):z.write(x,prefix+x.relative_to(ROOT).as_posix())
        z.writestr(prefix+'MANIFEST_SHA256.json',json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(a.output) as z:
        assert z.testzip() is None
        for name,digest in manifest.items():assert hashlib.sha256(z.read(prefix+name)).hexdigest()==digest
    digest=hashlib.sha256(a.output.read_bytes()).hexdigest();a.output.with_suffix('.zip.sha256').write_text(digest+'  '+a.output.name+'\n')
    print(json.dumps({'zip':str(a.output),'sha256':digest,'entries':len(manifest)+1,'manifest_verified':True}))
