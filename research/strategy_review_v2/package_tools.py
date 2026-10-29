"""Package only research source and its frozen v1 dependency, never user data."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parent
def package(destination):
    destination.parent.mkdir(parents=True,exist_ok=True)
    files=[]
    for folder in [ROOT.parent/'strategy_review_v1',ROOT]:
        files.extend(p for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ['.py','.cpp','.md','.json','.txt'])
    prefix='Strategy_Review_V2'
    manifest=[]
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(files):
            name=f'{prefix}/{p.relative_to(ROOT.parent)}';data=p.read_bytes();z.writestr(name,data)
            manifest.append(f'{hashlib.sha256(data).hexdigest()}  {name}\n')
        z.writestr(f'{prefix}/SHA256SUMS.txt',''.join(manifest))
    with zipfile.ZipFile(destination) as z:
        assert z.testzip() is None
        for line in z.read(f'{prefix}/SHA256SUMS.txt').decode().splitlines():
            digest,name=line.split('  ',1);assert hashlib.sha256(z.read(name)).hexdigest()==digest
    receipt={'archive':destination.name,'source_files':len(files),'bytes':destination.stat().st_size,'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),
        'private_data_included':False,'crc_and_manifest_verified':True,'contains_frozen_v1_dependency':True}
    destination.with_suffix('.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--destination',type=Path,required=True);package(p.parse_args().destination)
