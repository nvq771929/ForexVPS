"""Causal closed-bar observer. No broker, file-sidecar, adviser or order interface."""
import math
from collections import deque

CONTRACT='V225_MTF_CONTEXT_OBSERVER_RESEARCH_V1'

def validate_bar(b):
    keys=('time','open','high','low','close','ticks')
    if set(b)!=set(keys) or not isinstance(b['time'],int) or b['time']%300:raise ValueError('M5 clock/schema')
    if any(not math.isfinite(b[k]) or b[k]<=0 for k in keys[1:5]) or b['low']>min(b['open'],b['close']) or b['high']<max(b['open'],b['close']) or b['low']>b['high']:raise ValueError('M5 OHLC')
    if not isinstance(b['ticks'],int) or b['ticks']<0:raise ValueError('M5 tick count')

class Aggregate:
    def __init__(self,seconds):self.seconds=seconds;self.bucket=None;self.bars=[]
    def push(self,b):
        bucket=b['time']//self.seconds*self.seconds
        if bucket!=self.bucket:self.bucket=bucket;self.bars=[]
        self.bars.append(b)
        if b['time']+300!=bucket+self.seconds:return None
        x=self.bars;self.bars=[]
        if len(x)!=self.seconds//300 or x[0]['time']!=bucket or any(v['time']!=bucket+i*300 for i,v in enumerate(x)):return None
        return dict(time=bucket,open=x[0]['open'],high=max(v['high'] for v in x),low=min(v['low'] for v in x),close=x[-1]['close'],ticks=sum(v['ticks'] for v in x))

class Frame:
    def __init__(self,seconds,warm=150):
        self.seconds=seconds;self.warm=warm;self.count=0;self.bars=deque(maxlen=200);self.tr=deque(maxlen=200);self.e20=None;self.e50=None;self.seed20=[];self.seed50=[];self.e20s=deque(maxlen=10)
    def push(self,b):
        if self.bars:
            if b['time']<=self.bars[-1]['time']:raise ValueError('Nonmonotonic TF')
            prev=self.bars[-1]['close'];self.tr.append(max(b['high']-b['low'],abs(b['high']-prev),abs(b['low']-prev)))
        self.bars.append(b);self.count+=1
        for period in (20,50):
            key='e'+str(period);v=getattr(self,key)
            if v is None:
                seed=getattr(self,'seed'+str(period));seed.append(b['close'])
                if len(seed)==period:setattr(self,key,sum(seed)/period)
            else:setattr(self,key,(2/(period+1))*b['close']+(1-2/(period+1))*v)
        if self.e20 is not None:self.e20s.append(self.e20)
    def facts(self,asof):
        if not self.bars:return None
        end=self.bars[-1]['time']+self.seconds;age=asof-end
        if self.count<self.warm or age<0 or age>=self.seconds or len(self.tr)<28 or self.e20 is None or self.e50 is None or len(self.e20s)<7:return None
        b=list(self.bars);tr=list(self.tr);atr=sum(tr[-14:])/14;prior=sum(tr[-28:-14])/14
        if atr<=0:return None
        closes=[x['close'] for x in b];net=closes[-1]-closes[-13];travel=sum(abs(v-u) for u,v in zip(closes[-13:],closes[-12:]));sl=self.e20s[-1]-self.e20s[-4];prev_sl=self.e20s[-4]-self.e20s[-7];gap=(self.e20-self.e50)/atr
        vote=1 if gap>.10 and sl>0 else -1 if gap<-.10 and sl<0 else 0
        return dict(close_ms=end*1000,close_age_seconds=age,completed_bars=self.count,atr=atr,previous_atr=prior,ema20=self.e20,ema50=self.e50,ema_gap_atr=gap,slope3_atr=sl/atr,preceding_slope3_atr=prev_sl/atr,
            efficiency12=abs(net)/travel if travel else 0,net6_atr=(closes[-1]-closes[-7])/atr,range12_atr=(max(x['high'] for x in b[-12:])-min(x['low'] for x in b[-12:]))/atr,close=closes[-1],vote=vote)

def zones(bars,atr):
    """Audited native-style 64 M5 pivot clusters; no current/future pivot."""
    if len(bars)<64 or atr is None or atr<=0:return dict(known=False,support=None,resistance=None)
    b=list(bars)[-64:]
    if any(y['time']-x['time']!=300 for x,y in zip(b,b[1:])):return dict(known=False,support=None,resistance=None)
    pivots=[]
    for key,side in [('low',0),('high',1)]:
        pp=[]
        for i in range(2,61):
            valid=all(b[i][key]<b[i-k][key] and b[i][key]<=b[i+k][key] for k in (1,2)) if side==0 else all(b[i][key]>b[i-k][key] and b[i][key]>=b[i+k][key] for k in (1,2))
            if valid:pp.append((i,b[i][key]))
        pivots.append(pp)
    output=dict(known=True,support=None,resistance=None);price=b[-1]['close']
    for side,pp in enumerate(pivots):
        for seed_i,seed_price in pp:
            if 62-seed_i>48:continue
            group=[(i,p) for i,p in pp if 62-i<=48 and abs(p-seed_price)<=.25*atr]
            lo=min(p for i,p in group);hi=max(p for i,p in group)
            if len(group)<2 or hi-lo>.50*atr:continue
            padding=max(0,.10*atr-(hi-lo))/2;lo-=padding;hi+=padding;newest=max(i for i,p in group);z=dict(low=lo,high=hi,touches=len(group),age_bars=62-newest,known_at_ms=(b[newest+2]['time']+300)*1000)
            key='support' if side==0 else 'resistance';old=output[key]
            if side==0 and hi<price and (old is None or hi>old['high']):output[key]=z
            elif side==1 and lo>price and (old is None or lo<old['low']):output[key]=z
    return output

class ContextObserver:
    def __init__(self):
        self.m5=Frame(300,64);self.m15=Frame(900);self.h1=Frame(3600);self.a15=Aggregate(900);self.a60=Aggregate(3600);self.last=None;self._clear()
    def _clear(self):
        self.direction='UNKNOWN';self.started=None;self.pending=None;self.pending_count=0;self.unsupported=0
    @staticmethod
    def candidate(m15,h1,z):
        if m15['vote']==h1['vote'] and m15['vote']!=0:return 'UP' if m15['vote']>0 else 'DOWN'
        two=z['known'] and z['support'] is not None and z['resistance'] is not None and z['support']['high']<z['resistance']['low']
        if h1['vote']==0 and abs(m15['ema_gap_atr'])<=.25 and m15['efficiency12']<.35 and m15['range12_atr']<=4 and two:return 'RANGE'
        return 'UNCERTAIN'
    def _confirm(self,candidate,asof_ms):
        if candidate==self.direction and candidate in ('UP','DOWN','RANGE'):
            self.pending=None;self.pending_count=0;self.unsupported=0;return
        if candidate in ('UP','DOWN','RANGE'):
            self.pending_count=self.pending_count+1 if self.pending==candidate else 1;self.pending=candidate
        else:self.pending=None;self.pending_count=0
        if self.pending_count>=2:
            self.direction=candidate;self.started=asof_ms if candidate in ('UP','DOWN') else None;self.unsupported=0;self.pending=None;self.pending_count=0;return
        if self.direction in ('UP','DOWN'):
            self.unsupported+=1
            if self.unsupported>=2:self.direction='UNCERTAIN';self.started=None
        else:self.direction='UNCERTAIN';self.started=None
    def update(self,b):
        validate_bar(b)
        if self.last is not None and b['time']<=self.last:raise ValueError('M5 bars must be strictly chronological')
        gap=self.last is not None and b['time']-self.last!=300
        if gap:self._clear()
        self.last=b['time'];self.m5.push(dict(b));closed15=self.a15.push(dict(b));closed60=self.a60.push(dict(b))
        if closed15:self.m15.push(closed15)
        if closed60:self.h1.push(closed60)
        now=b['time']+300;f15=self.m15.facts(now);f60=self.h1.facts(now);f5=self.m5.facts(now);ready=f15 is not None and f60 is not None and f5 is not None
        # The native zone ATR ends before the latest closed trigger bar.
        tr=list(self.m5.tr);zatr=sum(tr[-15:-1])/14 if len(tr)>=15 else None;z=zones(self.m5.bars,zatr)
        if not ready:self._clear()
        candidate=self.candidate(f15,f60,z) if ready else 'UNKNOWN'
        if ready and closed15:self._confirm(candidate,now*1000)
        if ready and self.direction=='RANGE' and candidate!='RANGE':
            self.direction='UNCERTAIN';self.started=None
        age=(now*1000-self.started)/60000 if self.started is not None else None
        ratio=f5['atr']/f5['previous_atr'] if f5 is not None and f5['previous_atr']>0 else None
        volatility='UNKNOWN' if ratio is None else 'COMPRESSED' if ratio<.75 else 'EXPANDED' if ratio>1.25 else 'NORMAL'
        flags=[];phase='COLLECTING' if not ready else 'UNCONFIRMED';d=1 if self.direction=='UP' else -1 if self.direction=='DOWN' else 0
        if d:
            if f15['vote']!=d or f60['vote']!=d or self.unsupported:flags.append('TIMEFRAME_CONFLICT')
            if d*f15['net6_atr']<=0:flags.append('MOMENTUM_FADE')
            if d*f15['preceding_slope3_atr']>0 and d*f15['slope3_atr']<.5*d*f15['preceding_slope3_atr']:flags.append('SLOPE_FADE')
            opposite=z['resistance'] if d>0 else z['support'];edge=(opposite['low'] if d>0 else opposite['high']) if opposite else None
            room=d*(edge-b['close'])/f5['atr'] if edge is not None else None
            if room is not None and 0<=room<=.5:flags.append('NEAR_OPPOSITE_ZONE')
            extended=d*(f15['close']-f15['ema20'])/f15['atr']>1.5
            phase='WEAKENING' if flags else 'EXTENDED' if extended else 'FORMING' if age<30 else 'CONTINUING'
        elif self.direction=='RANGE':phase='BOUNDED_RANGE'
        return dict(contract=CONTRACT,asof_ms=now*1000,direction=self.direction,candidate=candidate,volatility=volatility,volatility_ratio=ratio,phase=phase,phase_flags=flags,
            detected_start_ms=self.started,observed_age_minutes=age,age_meaning='SINCE_CAUSAL_CONFIRMATION_NOT_TRUE_TREND_ONSET',pending_candidate=self.pending,pending_m15_count=self.pending_count,
            unsupported_m15_count=self.unsupported,data_gap=gap,ready=ready,m15=f15,h1=f60,zones=z,close=b['close'],m5_atr=f5['atr'] if f5 else None,
            historical_probabilities_qualified=False,EA_effects_allowed=False)
