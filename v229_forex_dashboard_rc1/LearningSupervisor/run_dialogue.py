import argparse
import json
import os
from pathlib import Path
import time
from dialogue.worker import Worker
from dialogue.models import load

def main():
    p=argparse.ArgumentParser(description='V2.24 local pre-lock adviser; timeout always leaves native EA in charge')
    p.add_argument('command',choices=['collect','watch','prepare','train','validate'])
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--broker-utc-offset-minutes',type=int)
    p.add_argument('--model',type=Path)
    p.add_argument('--forward-receipt',type=Path)
    a=p.parse_args();source=a.source.resolve();output=a.output.resolve()
    if output==source or source in output.parents or output in source.parents:p.error('Use a separate, non-nested worker output')
    if a.broker_utc_offset_minutes is not None and not -720<=a.broker_utc_offset_minutes<=840:p.error('Invalid broker offset')
    output.mkdir(parents=True,exist_ok=True);lock=output/'.writer-lock'
    try:lock.mkdir()
    except FileExistsError:p.error('Worker output busy; stop the previous worker first')
    (lock/'owner.json').write_text(json.dumps(dict(pid=os.getpid(),created_utc=time.time())))
    worker=None
    try:
        worker=Worker(source,output,a.broker_utc_offset_minutes,load(a.model) if a.model else None,a.forward_receipt)
        if a.command=='watch' and worker.origin!='LIVE_MT4':p.error('Tester requests are collect-only; never live replies')
        while True:
            status=worker.poll()
            print(json.dumps(status),flush=True)
            if a.command in ('prepare','train','validate'):
                from dialogue.dataset import prepare
                dataset=prepare(worker)
                if a.command=='train':
                    from dialogue.training import train
                    print(json.dumps(train(dataset,output/'models')),flush=True)
                if a.command=='validate':
                    if worker.model is None:p.error('--model is required to validate')
                    from dialogue.models import export_forward_receipt
                    print(json.dumps(export_forward_receipt(worker,dataset,worker.model)),flush=True)
            if a.command!='watch':break
            time.sleep(.25)
    except KeyboardInterrupt:print('Dialogue worker stopped; native EA remains in charge.')
    finally:
        if worker:worker.close()
        (lock/'owner.json').unlink(missing_ok=True);lock.rmdir()

if __name__=='__main__':main()
