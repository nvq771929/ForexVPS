"""Descriptive knowledge with denominators, uncertainty and explicit scope.

No finding here changes a strategy or is treated as an out-of-sample result.
"""
from collections import Counter,defaultdict
from datetime import datetime,timezone
import math
from .store import atomic

def interval(w,n):
    if not n:return None
    z=1.96;p=w/n;d=1+z*z/n
    center=(p+z*z/(2*n))/d;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [center-half,center+half]

def summarize(dataset,store):
    groups=defaultdict(Counter);daily=defaultdict(Counter)
    offset=dataset.get('broker_utc_offset_minutes')
    for r in dataset['rows']:
        c,l=r['case'],r['label'];status=l['status']
        day=datetime.fromtimestamp(c['entry_ms']/1000,timezone.utc).strftime('%Y-%m-%d')
        daily[day][status]+=1
        atr=None if c['features'] is None else c['features'][0]
        atr_band='UNKNOWN' if atr is None else '<1' if atr<1 else '1–2' if atr<2 else '2–3' if atr<3 else '3–5' if atr<5 else '5–8' if atr<8 else '>=8'
        session='SESSION_UNKNOWN'
        if offset is not None:
            try:
                from intelligence.market_sessions import classify
                session=classify(c['entry_ms']//1000-offset*60)
                if isinstance(session,dict):session=session.get('session','SESSION_UNKNOWN')
            except (ImportError,ValueError,KeyError):session='SESSION_UNKNOWN'
        for key in (f"Chiến lược {c['setup']}",f"Bối cảnh {c['regime']}",f'ATR {atr_band} pip',f'Phiên {session}'):
            groups[key][status]+=1
    findings=[];proposals=[]
    for name,counts in sorted(groups.items()):
        n=counts['WIN']+counts['LOSS'];wins=counts['WIN']
        findings.append(dict(group=name,counts=dict(counts),decisive=n,win_rate=wins/n if n else None,
            wilson95=interval(wins,n),evidence='MOI_QUAN_SAT' if n<30 else 'DU_MAU_DE_DAT_GIA_THUYET',
            interpretation='Descriptive association; correlated market samples may make this interval optimistic. No causal conclusion.'))
        if n>=30:
            proposals.append(dict(area=name,reason=f'{wins}/{n} mẫu WIN; cần đối chiếu với nhóm còn lại và các giai đoạn khác.',
                action='Thiết kế một giả thuyết trước khi thử trên tập mới; chưa sửa ngưỡng hoặc đổi chiến lược.',
                status='HYPOTHESIS_ONLY',ea_change_allowed=False))
    report=dict(contract='V224_DESCRIPTIVE_KNOWLEDGE_V1',dataset_sha256=dataset['sha256'],origin=dataset['origin'],
        daily=dict(sorted((d,dict(c)) for d,c in daily.items())),findings=findings,proposals=proposals,
        learned_meaning='Cases, descriptive statistics and (only after fitting) frozen model weights.',
        activation_allowed=False)
    atomic(store.output/'knowledge.json',report);return report
