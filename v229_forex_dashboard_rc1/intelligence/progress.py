"""Optional, data-only progress events and a Windows-friendly console heartbeat."""
from datetime import datetime
from pathlib import Path
import sys
import threading
import time


STAGES={
    'discover':(1,'TIM NHAT KY'),
    'read':(2,'DOC + KIEM TRA'),
    'labels':(3,'TAO MAU'),
    'fit':(4,'HUAN LUYEN'),
    'calibrate':(5,'HIEU CHINH'),
    'evaluate':(6,'KIEM DINH'),
    'holdouts':(7,'KIEM TRA THEO THOI GIAN'),
    'export':(8,'XUAT KET QUA'),
}


def notify(callback,stage,**values):
    if callback is not None:callback(dict(stage=stage,**values))


def duration(seconds):
    seconds=max(0,int(seconds));hours,seconds=divmod(seconds,3600);minutes,seconds=divmod(seconds,60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}'


class ConsoleProgress:
    """Stage ETA is measured work only, never a guessed whole-job percentage.

    A periodic heartbeat continues even while sklearn or one file read is busy.
    Source journals are never written. The log lives outside the input dataset.
    """
    def __init__(self,stream=None,log_path=None,interval=2.,clock=time.monotonic):
        if not .1<=interval<=60:raise ValueError('Progress interval must be 0.1..60 seconds')
        self.stream=stream if stream is not None else sys.stdout
        self.log_path=Path(log_path) if log_path else None
        self.interval=interval;self.clock=clock
        self.lock=threading.RLock();self.stop=threading.Event();self.thread=None;self.log=None
        self.started=self.clock();self.stage_started=self.started;self.last_print=-float('inf')
        self.state=dict(stage='discover',detail='Chuan bi');self.closed=False

    def __enter__(self):
        if self.log_path:
            self.log_path.parent.mkdir(parents=True,exist_ok=True)
            self.log=self.log_path.open('x',encoding='utf-8')
        self.render(force=True)
        self.thread=threading.Thread(target=self._heartbeat,name='training-progress',daemon=True)
        self.thread.start()
        return self

    def _heartbeat(self):
        while not self.stop.wait(self.interval):self.render(force=True)

    def __call__(self,event):
        with self.lock:
            if self.closed:return
            if event['stage']!=self.state['stage']:
                self.stage_started=self.clock();self.state=dict(event);changed=True
            else:
                self.state.update(event);changed=False
            self.render(force=changed or event.get('done')==event.get('total') and event.get('total') is not None)

    def _line(self,now):
        stage=self.state['stage'];number,title=STAGES.get(stage,(0,stage))
        prefix=f'[{number}/8 {title}]' if number else f'[{title}]'
        text=[prefix]
        done=self.state.get('done');total=self.state.get('total');unit=self.state.get('unit','')
        elapsed=max(0,now-self.stage_started)
        if done is not None and total is not None:
            if total>0:
                fraction=max(0,min(1,done/total));filled=int(20*fraction)
                text.append('['+'#'*filled+'-'*(20-filled)+f'] {fraction*100:5.1f}%')
            text.append(f'{done:,}/{total:,} {unit}'.strip())
            # Both rate and ETA describe this stage, not fitting or the whole job.
            if done>0 and elapsed>=1:
                rate=done/elapsed;text.append(f'{rate:,.1f} {unit}/s')
                text.append('ETA giai doan '+duration(max(0,total-done)/rate))
            else:text.append('ETA giai doan: dang uoc luong')
        else:text.append('dang xu ly; ETA: chua uoc luong')
        text.append('Da chay '+duration(now-self.started))
        if self.state.get('detail'):text.append(self.state['detail'])
        return ' | '.join(text)

    def render(self,force=False):
        with self.lock:
            now=self.clock()
            if self.closed or not force and now-self.last_print<self.interval:return
            line=self._line(now);self.last_print=now
            # Plain lines work in narrow Windows terminals, redirected output
            # and older cmd.exe without ANSI cursor/erase support.
            self.stream.write(line+'\n')
            self.stream.flush()
            if self.log:
                self.log.write(datetime.now().astimezone().isoformat(timespec='seconds')+' '+line+'\n');self.log.flush()

    def close(self,status,detail=''):
        self.stop.set()
        if self.thread:self.thread.join(timeout=self.interval+1)
        with self.lock:
            if self.closed:return
            line=f'[{status}] Tong thoi gian: {duration(self.clock()-self.started)}'
            if detail:line+=' | '+detail.replace('\n',' ')
            self.stream.write(line+'\n');self.stream.flush()
            if self.log:self.log.write(line+'\n');self.log.flush();self.log.close()
            self.closed=True

    def __exit__(self,kind,value,tb):
        self.close('CANCELED' if kind is KeyboardInterrupt else 'FAILED' if kind else 'FINISHED',
            f'{kind.__name__}: {value}' if kind else '')
