"""Source-only recorder/data-checking kit, no personal capture files."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parent
def package(destination):
    destination.parent.mkdir(parents=True,exist_ok=True)
    files=sorted(p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ['.py','.cpp','.mq4','.set','.cmd','.ps1','.csv','.md','.json'])
    manifest=[]
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in files:
            data=p.read_bytes();name='EA_Research_Data_Capture_V1/'+p.relative_to(ROOT).as_posix();z.writestr(name,data);manifest.append(f'{hashlib.sha256(data).hexdigest()}  {name}\n')
        z.writestr('EA_Research_Data_Capture_V1/SHA256SUMS.txt',''.join(manifest))
    with zipfile.ZipFile(destination) as z:
        assert z.testzip() is None
        for line in z.read('EA_Research_Data_Capture_V1/SHA256SUMS.txt').decode().splitlines():
            digest,name=line.split('  ',1);assert hashlib.sha256(z.read(name)).hexdigest()==digest
    result={'source_files':len(files),'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'bytes':destination.stat().st_size,
        'private_data_included':False,'trading_EA_upgrade':False,'native_MetaEditor_compile':False,'CRC_and_source_manifest_verified':True}
    destination.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--destination',type=Path,required=True);package(p.parse_args().destination)
