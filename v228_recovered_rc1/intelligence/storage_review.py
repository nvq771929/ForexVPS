"""Read stopped journals even when replay is broken. Diagnose; never repair or train."""
import csv,hashlib,io
from pathlib import Path
from collections import Counter
from .demo_learning import LOGIC
from .native_ledger import event_paths,iter_directory


def review(source):
    source=Path(source);sessions={};issues=[];files=[];kinds=Counter();rows=0
    native_count=0;native_last=None;native_failure=None
    paths=event_paths(source)
    try:
        for record in iter_directory(source,paths=paths,compact=True):
            native_count+=1;native_last=record['event']['observedMs']
    except (ValueError,OSError,KeyError) as error:native_failure=str(error)
    for path in sorted(source.glob('input_*.csv')):
        before=path.stat();raw=path.read_bytes()
        digest=hashlib.sha256(raw).hexdigest()
        complete=not raw or raw.endswith(b'\n')
        consumed=raw if complete else raw[:raw.rfind(b'\n')+1]
        if not complete:issues.append(dict(kind='INCOMPLETE_TAIL',file=path.name,bytes=len(raw)-len(consumed)))
        for line,row in enumerate(csv.DictReader(io.StringIO(consumed.decode('utf-8-sig'))),2):
            rows+=1
            try:
                sid=row['session'];seq=int(row['sequence']);now=int(row['time_ms_estimated'])
                if int(row['schema'])!=2 or int(row['logic_version'])!=LOGIC or row['shadow_mode']!='1':raise ValueError('Replay identity')
            except (ValueError,TypeError,KeyError) as error:
                issues.append(dict(kind='INVALID_ROW',file=path.name,row=line,error=str(error)));continue
            previous=sessions.get(sid);kinds[row['event_type']]+=1
            if (previous and seq!=previous['sequence']+1) or (not previous and seq!=1):
                issues.append(dict(kind='SEQUENCE_GAP' if seq>(previous['sequence']+1 if previous else 1) else 'SEQUENCE_DUPLICATE_OR_REWIND',
                    file=path.name,row=line,session=sid,sequence=seq,previous=previous))
            if now<=0 or (previous and now<previous['time_ms']):
                issues.append(dict(kind='CLOCK_BACKWARDS_OR_INVALID',file=path.name,row=line,session=sid,sequence=seq,time_ms=now,previous=previous))
            sessions[sid]=dict(sequence=seq,time_ms=now,file=path.name,row=line)
        after=path.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Input is still changing; stop EA and copy journal')
        files.append(dict(name=path.name,bytes=len(raw),sha256=digest,complete_tail=complete))
    if event_paths(source)!=paths:raise ValueError('Native journal still changing; stop EA and copy journal')
    return dict(schema=1,software_version='2.15',status='ISSUES_FOUND' if issues or native_failure else 'NO_RECORDED_INTEGRITY_ISSUE',
        source=source.name,native_files=len(paths),native_records_verified=native_count,native_last_ms=native_last,
        native_integrity_failure=native_failure,replay_rows=rows,replay_event_types=dict(kinds),sessions=sessions,
        issues=issues,files=files,temporary_files=[dict(name=p.name,bytes=p.stat().st_size) for p in sorted(source.glob('*.tmp'))],
        trained=False,repaired=False,source_modified=False,
        explanation='A sequence gap identifies missing recorded input, not the OS cause of a failed write. Preserve Experts/Journal messages for file error details.')
