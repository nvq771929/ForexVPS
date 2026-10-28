"""Read interactive launcher values through the environment, never shell code."""
import os
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parent
source=os.environ.get('V224_JOURNAL','').strip()
if not source:raise SystemExit('Journal directory is required')
args=[sys.executable,str(root/'run_supervisor.py'),'watch','--source',source,'--output',str(root/'runtime/live')]
common=os.environ.get('V224_COMMON','').strip()
offset=os.environ.get('V224_OFFSET','').strip()
if common:args+=['--common-dir',common]
if offset:
    int(offset)
    args+=['--broker-utc-offset-minutes',offset]
raise SystemExit(subprocess.call(args))
