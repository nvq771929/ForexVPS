"""Read launcher inputs as data; never interpolate paths into shell commands."""
import os
from pathlib import Path
import subprocess
import sys
from assistant.worker import channel_name

def main():
    root=Path(__file__).resolve().parent
    source=os.environ.get('V224_AI_SOURCE','').strip()
    if not source:raise SystemExit('Journal directory is required')
    channel=channel_name(os.environ.get('V224_AI_CHANNEL','v224_demo').strip())
    args=[sys.executable,str(root/'run_ai_assistant.py'),'watch','--source',source,
          '--output',str(root/'runtime/assistant'/channel),'--channel',channel]
    for variable,option in [('V224_AI_OFFSET','--broker-utc-offset-minutes'),('V224_AI_COMMON','--common-dir'),('V224_AI_CONFIG','--local-config')]:
        value=os.environ.get(variable,'').strip()
        if value:args.extend([option,value])
    return subprocess.call(args)

if __name__=='__main__':raise SystemExit(main())
