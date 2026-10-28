"""Read-only local AI assistant; does not train, activate or publish EA advice."""
import argparse
import json
import os
from pathlib import Path
import time
from assistant.worker import Assistant, separate

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['collect','watch'])
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--broker-utc-offset-minutes',type=int)
    p.add_argument('--channel',default='v224_demo')
    p.add_argument('--common-dir',type=Path)
    p.add_argument('--local-config',type=Path)
    a=p.parse_args();source=a.source.resolve();output=a.output.resolve()
    if not separate(source,output):p.error('Assistant output must be separate from the native source')
    output.mkdir(parents=True,exist_ok=True);lock=output/'.writer-lock'
    try:lock.mkdir()
    except FileExistsError:p.error('Assistant output busy; stop its previous CMD or inspect a stale lock owner')
    (lock/'owner.json').write_text(json.dumps(dict(pid=os.getpid(),created_utc=time.time())))
    worker=None
    try:
        worker=Assistant(source,output,a.broker_utc_offset_minutes,a.channel,a.common_dir,a.local_config)
        if a.command=='watch' and worker.origin!='LIVE_MT4':p.error('Use collect for Tester data; watch accepts LIVE_MT4 only')
        last_verify=time.monotonic()
        while True:
            s=worker.poll()
            print(f"AI LOCAL | {s['health']} | BIN {s['native_records']} | M5 {s['progress']['closed_m5_used']} | {s['model_status']} | EA effects OFF",flush=True)
            if time.monotonic()-last_verify>=60:
                worker.verify_prefix();last_verify=time.monotonic()
            if a.command=='collect' and s['health']!='CATCHING_UP':break
            if a.command=='watch' and s['health']!='CATCHING_UP':time.sleep(2)
    except KeyboardInterrupt:print('Local assistant stopped. EA decisions remain unchanged.')
    except Exception as ex:
        if worker:worker.render(error=type(ex).__name__+': '+str(ex))
        raise
    finally:
        if worker:worker.close()
        (lock/'owner.json').unlink(missing_ok=True);lock.rmdir()

if __name__=='__main__':main()
