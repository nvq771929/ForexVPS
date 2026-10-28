"""Compare the actual native numeric observer with frozen RC1 on the SAME stream.

Input: JSON/gzip array of closed M5 bars; read-only. No fitting, forecasts or
outcome selection. C++ shim validation does not replace MetaEditor / MT4 pilot.
"""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'LearningSupervisor'))
from assistant.context.engine import ContextObserver

DIRECTIONS={None:0,'UNKNOWN':0,'UP':1,'DOWN':2,'RANGE':3,'UNCERTAIN':4}
PHASES={v:i for i,v in enumerate(('COLLECTING','UNCONFIRMED','FORMING','CONTINUING','EXTENDED','WEAKENING','BOUNDED_RANGE'))}
VOLATILITY={'UNKNOWN':0,'COMPRESSED':1,'NORMAL':2,'EXPANDED':3}
FLAGS=('TIMEFRAME_CONFLICT','MOMENTUM_FADE','SLOPE_FADE','NEAR_OPPOSITE_ZONE')
FACTS=('close_ms','close_age_seconds','completed_bars','atr','previous_atr','ema20','ema50','ema_gap_atr','slope3_atr','preceding_slope3_atr','efficiency12','net6_atr','range12_atr','close','vote')

def expected(v,observer):
    fields=[v['asof_ms'],DIRECTIONS[v['direction']],DIRECTIONS[v['candidate']],VOLATILITY[v['volatility']],PHASES[v['phase']],
        sum(1<<i for i,k in enumerate(FLAGS) if k in v['phase_flags']),v['detected_start_ms'] or 0,
        v['observed_age_minutes'] if v['observed_age_minutes'] is not None else -1,DIRECTIONS[v['pending_candidate']],
        v['pending_m15_count'],v['unsupported_m15_count'],int(v['data_gap']),int(v['ready']),
        v['volatility_ratio'] if v['volatility_ratio'] is not None else -1,v['m5_atr'] or 0]
    # RC1 public output omits M5 facts, but exposes the exact same Frame class.
    for f in (v['m15'],v['h1'],observer.m5.facts(v['asof_ms']//1000)):
        fields.append(int(f is not None))
        if f is not None:fields.extend(f[k] for k in FACTS)
    fields.append(int(v['zones']['known']))
    for key in ('support','resistance'):
        z=v['zones'][key];fields.append(int(z is not None))
        if z:fields.extend(z[k] for k in ('low','high','touches','age_bars','known_at_ms'))
    return fields

def compile_runner(target):
    subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
        str(ROOT/'tests/embedded_context_runner.cpp'),'-o',str(target)],check=True,capture_output=True,text=True)

def compare(bars,binary):
    text=''.join(' '.join(str(b[k]) for k in ('time','open','high','low','close','ticks'))+'\n' for b in bars)
    start=time.monotonic()
    native=subprocess.run([str(binary)],input=text,capture_output=True,text=True,check=True)
    seconds=time.monotonic()-start
    lines=native.stdout.splitlines()
    if len(lines)!=len(bars):raise ValueError('Native row count differs')
    observer=ContextObserver();values=0;discrete=0;worst=0
    for i,(b,line) in enumerate(zip(bars,lines)):
        want=expected(observer.update(b),observer);got=line.split(',')
        if len(got)!=len(want):raise ValueError(f'Native schema differs at {i}: {line}')
        for j,(a,v) in enumerate(zip(got,want)):
            x=float(a);values+=1
            if isinstance(v,int):
                discrete+=1
                if x!=v:raise ValueError(f'Discrete mismatch bar={i} field={j} {x} != {v}')
            else:
                worst=max(worst,abs(x-v))
                if not math.isclose(x,v,rel_tol=1e-10,abs_tol=1e-12):
                    raise ValueError(f'Numeric mismatch bar={i} field={j} {x} != {v}')
    return dict(bars=len(bars),values_checked=values,exact_discrete_values=discrete,max_absolute_float_difference=worst,
        native_seconds_including_csv_io=seconds,engine_count_m5=observer.m5.count,status='PASS')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('corpus',type=Path,nargs='+');p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();result=dict(contract='V225_EMBEDDED_CONTEXT_PARITY_V1',relative_tolerance=1e-10,absolute_tolerance=1e-12,
        native_metaeditor_compiled=False,changed_trade_decisions=False,corpora=[])
    with tempfile.TemporaryDirectory() as tmp:
        binary=Path(tmp)/'embedded';compile_runner(binary)
        for path in args.corpus:
            blob=path.read_bytes();bars=json.loads(gzip.decompress(blob) if path.suffix=='.gz' else blob)
            result['corpora'].append(dict(source_name=path.name,sha256=hashlib.sha256(blob).hexdigest(),**compare(bars,binary)))
    result['status']='PASS';args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
