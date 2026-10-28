import os
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parent
source=os.environ.get('V224_DIALOGUE_SOURCE','').strip()
if not source:raise SystemExit('A native LIVE V2.24 journal directory is required')
args=[sys.executable,str(root/'run_dialogue.py'),'watch','--source',source,'--output',str(root/'runtime/dialogue')]
for name,flag in [('V224_DIALOGUE_OFFSET','--broker-utc-offset-minutes'),('V224_DIALOGUE_MODEL','--model'),('V224_DIALOGUE_RECEIPT','--forward-receipt')]:
    value=os.environ.get(name,'').strip()
    if value:args.extend([flag,value])
raise SystemExit(subprocess.call(args))
