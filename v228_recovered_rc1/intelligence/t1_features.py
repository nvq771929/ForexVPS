"""Frozen V211 V1 decoder for compatibility. New V213 training uses t1_corrected.

Do not silently fix the historical V1 vector: it would invalidate frozen model
and cache digests. Public new training migrates to ANCHOR_T1_UP_V2 before fit.
"""
import math
from .research_features import extract as anchor_features,NAMES as ANCHOR_NAMES

CONTRACT='ANCHOR_T1_UP_V1'
NAMES=ANCHOR_NAMES+('t1_net_atr','t1_high_atr','t1_low_atr','t1_range_atr','t1_close_location',
    'lock_elapsed_fraction','last_observed_fraction','quote_age_seconds','candidate_present',
    'candidate_direction','candidate_sr1','candidate_tp1','candidate_br1','confirmation_margin_atr',
    'risk_distance_atr','reward_distance_atr','broker_hour_sin','broker_hour_cos','broker_weekday_sin','broker_weekday_cos')


def extract(current,locked_at_ms):
    base=anchor_features(current);start=int(current['analysisStart'])*1000;target=int(current['targetTime'])*1000
    if not current['locked'] or current['entered'] or current['lockedAtMs']!=locked_at_ms or not start<=locked_at_ms<=target-31000:
        raise ValueError('T+1 features require the scheduled pre-entry LOCK')
    quote=int(current['lastQuoteMs']);bid=float(current['latestBid']);hi=float(current['highestBid']);lo=float(current['lowestBid'])
    if not start<=quote<=locked_at_ms or not all(math.isfinite(v) and v>0 for v in (bid,hi,lo)) or not lo<=bid<=hi:
        raise ValueError('T+1 quote/extrema unavailable or newer than LOCK')
    a=current['anchor'];atr=float(a['volatility']['atr']);close=float(a['triggerClose']);c=current['candidate'];d=int(c['direction']);setup=int(c['setup'])
    if d not in (-1,0,1) or setup not in (0,1,2,3):raise ValueError('Unknown T+1 candidate identity')
    seconds=locked_at_ms//1000
    hour=(seconds%86400)/86400*2*math.pi;weekday=((seconds//86400+3)%7)/7*2*math.pi
    margin=d*(bid-c['confirmation'])/atr if d else 0.
    risk=d*(bid-c['invalidation'])/atr if d else 0.
    reward=d*(c['extension']-bid)/atr if d else 0.
    values=base+[(bid-close)/atr,(hi-close)/atr,(lo-close)/atr,(hi-lo)/atr,(.5 if hi==lo else (bid-lo)/(hi-lo)),
        (locked_at_ms-start)/300000,(quote-start)/300000,(locked_at_ms-quote)/1000,
        float(d!=0),float(d),float(setup==1),float(setup==2),float(setup==3),margin,risk,reward,
        math.sin(hour),math.cos(hour),math.sin(weekday),math.cos(weekday)]
    if len(values)!=len(NAMES) or not all(math.isfinite(v) and abs(v)<1e6 for v in values):raise ValueError('Invalid causal T+1 vector')
    return values


def enrich(rows,groups,progress=None):
    from collections import Counter
    from .progress import notify
    result=[];excluded=Counter()
    for row in rows:
        locks=[r for r in groups[row['analysis_start']] if r['event']['kind']==3]
        if len(locks)!=1:raise ValueError('T+1 enrichment requires exactly one LOCK')
        current=locks[0]['state']['current']
        try:features=extract(current,row['locked_at_ms'])
        except (KeyError,ValueError):excluded['unavailable_causal_t1']+=1;continue
        new=dict(row,cohort=CONTRACT,features=features,feature_asof_ms=row['locked_at_ms'],
            anchor_asof_ms=row['feature_asof_ms'])
        result.append(new)
        row.update(candidate_setup=int(current['candidate']['setup']),candidate_direction=int(current['candidate']['direction']))
        new.update(candidate_setup=row['candidate_setup'],candidate_direction=row['candidate_direction'])
    notify(progress,'labels',detail=f"T+1 truoc LOCK: {len(result):,} mau; khong dung gia entry/expiry lam dac trung")
    return result,dict(feature_contract=CONTRACT,feature_count=len(NAMES),rows=len(result),exclusions=dict(excluded),
        source='IMMUTABLE_PRE_ENTRY_LOCK',spread_feature_available=False,
        note='Legacy POD stores Bid extrema, not Ask. Broker clock features are not UTC/session labels.')
