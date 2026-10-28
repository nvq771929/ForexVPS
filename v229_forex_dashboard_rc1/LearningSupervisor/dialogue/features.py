"""Causal observation-time features, explicitly separate from locked T+1 data."""
import math
from . import FEATURE_CONTRACT
from intelligence.research_features import extract as anchor_features
from intelligence import candidate_features as cf
from intelligence.t1_corrected import NAMES as LOCK_CONTEXT_NAMES
from supervisor.store import digest

NAMES=tuple(n.replace('lock_elapsed_fraction','query_elapsed_fraction') for n in cf.NAMES)
CONTEXT_NAMES=tuple(n.replace('lock_elapsed_fraction','query_elapsed_fraction') for n in LOCK_CONTEXT_NAMES)

def extract(request):
    r=request['meta'];c=request['snapshot']['state']['current'];now=r['observed_ms'];start=r['analysis_start']*1000
    if c['locked'] or c['entered'] or c['canceled'] or not start<=c['lastQuoteMs']<=now:
        raise ValueError('Adviser requires a real pre-lock snapshot')
    a=c['anchor'];atr=float(a['volatility']['atr']);bid=float(c['latestBid']);hi=float(c['highestBid']);lo=float(c['lowestBid'])
    if not all(math.isfinite(v) and v>0 for v in (atr,bid,hi,lo)) or not lo<=bid<=hi:raise ValueError('Unavailable pre-lock price context')
    candidate=c['candidate'];d=r['direction'];setup=r['setup'];close=a['triggerClose']
    hour=(now//1000%86400)/86400*2*math.pi;weekday=((now//86400000+3)%7)/7*2*math.pi
    available=bool(a['structure']['resistance' if d>0 else 'support']['available'])
    context=anchor_features(c)+[(bid-close)/atr,(hi-close)/atr,(lo-close)/atr,(hi-lo)/atr,.5 if hi==lo else (bid-lo)/(hi-lo),
        (now-start)/300000,(c['lastQuoteMs']-start)/300000,(now-c['lastQuoteMs'])/1000,
        1.,float(d),float(setup==1),float(setup==2),float(setup==3),d*(bid-candidate['confirmation'])/atr,
        d*(bid-candidate['invalidation'])/atr,d*(candidate['extension']-bid)/atr if available else 0.,
        math.sin(hour),math.cos(hour),math.sin(weekday),math.cos(weekday),float(available)]
    if len(context)!=50 or not all(math.isfinite(v) and abs(v)<1e6 for v in context):raise ValueError('Invalid pre-lock feature vector')
    features=cf.extract(context,setup,d)
    return dict(contract=FEATURE_CONTRACT,asof_ms=now,features=features,context=context,
        feature_hash=digest(dict(contract=FEATURE_CONTRACT,asof_ms=now,features=features,context=context)))
