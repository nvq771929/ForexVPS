"""Package research source only; dependency closure includes frozen v1/v2."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parent
def package(destination):
    destination.parent.mkdir(parents=True,exist_ok=True);files=[]
    for name in ['strategy_review_v1','strategy_review_v2','strategy_review_v3']:
        files.extend(p for p in (ROOT.parent/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ['.py','.cpp','.mqh','.json','.md','.txt'])
    manifest=[]
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(files):
            data=p.read_bytes();name='Strategy_Review_V3/'+p.relative_to(ROOT.parent).as_posix();z.writestr(name,data);manifest.append(f'{hashlib.sha256(data).hexdigest()}  {name}\n')
        z.writestr('Strategy_Review_V3/SHA256SUMS.txt',''.join(manifest))
    with zipfile.ZipFile(destination) as z:
        assert z.testzip() is None
        for line in z.read('Strategy_Review_V3/SHA256SUMS.txt').decode().splitlines():
            digest,name=line.split('  ',1);assert hashlib.sha256(z.read(name)).hexdigest()==digest
    receipt={'source_files':len(files),'bytes':destination.stat().st_size,'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'private_data_included':False,'not_an_EA_release':True,'CRC_and_manifest_verified':True}
    destination.with_suffix('.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--destination',type=Path,required=True);package(p.parse_args().destination)
