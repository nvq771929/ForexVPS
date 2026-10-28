"""V226 fixed-window price features. No EMA state, fitted scaling or order API.

Each bar has a first-observed timestamp. A higher-frame bar needs every closed
constituent available before the query cutoff; missing bars remain masked.
"""
import math

CONTRACT='V226_PRELOCK_PRICE_BEHAVIOR_V1'
CHANNELS=('log_return','body_relative','range_relative','upper_wick_relative','lower_wick_relative',
          'log1p_tick_volume','gap_before','return_known','bar_known')
FRAMES=((300,32),(900,16),(3600,16))

def valid_bar(b):
    if set(b)!=set(('time','open','high','low','close','ticks')):raise ValueError('Bar schema')
    if type(b['time']) is not int or b['time']<=0 or b['time']%300 or type(b['ticks']) is not int or b['ticks']<0:raise ValueError('Bar clock/volume')
    if any(not math.isfinite(b[k]) or b[k]<=0 for k in ('open','high','low','close')) or b['low']>min(b['open'],b['close']) or b['high']<max(b['open'],b['close']):raise ValueError('OHLC')

class PriceWindow:
    """Source-specific immutable bars. The same window/cutoff gives same features."""
    def __init__(self):self.bars={};self.available={}
    def observe(self,b,available_ms):
        valid_bar(b)
        if type(available_ms) is not int or available_ms<(b['time']+300)*1000:raise ValueError('Availability precedes close')
        t=b['time']
        if t in self.bars and self.bars[t]!=b:raise ValueError('Historical bar revision; new lineage required')
        self.bars[t]=dict(b);self.available[t]=min(available_ms,self.available.get(t,available_ms))

    def aggregate(self,time,seconds,asof_ms,available_cutoff_ms):
        if (time+seconds)*1000>asof_ms:return None
        bars=[]
        for t in range(time,time+seconds,300):
            b=self.bars.get(t)
            if b is None or self.available[t]>available_cutoff_ms:return None
            bars.append(b)
        return dict(time=time,open=bars[0]['open'],high=max(b['high'] for b in bars),
                    low=min(b['low'] for b in bars),close=bars[-1]['close'],ticks=sum(b['ticks'] for b in bars))

    def features(self,asof_ms,cutoff_ms):
        if type(asof_ms) is not int or asof_ms%300000 or cutoff_ms<asof_ms:raise ValueError('Feature cutoff')
        anchor=self.aggregate(asof_ms//1000-300,300,asof_ms,cutoff_ms)
        if anchor is None:raise ValueError('Latest closed anchor is unavailable')
        scale=anchor['close'];result={};coverage={};times={}
        for seconds,length in FRAMES:
            end=asof_ms//1000//seconds*seconds;values=[];known=0;frame_times=[]
            for t in range(end-length*seconds,end,seconds):
                b=self.aggregate(t,seconds,asof_ms,cutoff_ms);frame_times.append(t)
                if b is None:values.append([0.]*len(CHANNELS));continue
                p=self.aggregate(t-seconds,seconds,asof_ms,cutoff_ms)
                row=[math.log(b['close']/p['close']) if p else 0.,(b['close']-b['open'])/scale,
                    (b['high']-b['low'])/scale,(b['high']-max(b['open'],b['close']))/scale,
                    (min(b['open'],b['close'])-b['low'])/scale,math.log1p(b['ticks']),float(p is None),float(p is not None),1.]
                if any(not math.isfinite(v) for v in row):raise ValueError('Nonfinite feature')
                values.append(row);known+=1
            result[str(seconds)]=values;coverage[str(seconds)]=known;times[str(seconds)]=frame_times
        return dict(contract=CONTRACT,asof_ms=asof_ms,available_cutoff_ms=cutoff_ms,scale_close=scale,
                    frames=result,coverage=coverage,frame_times=times,uses_observer_age=False)

def temporal_partition(asof_ms,label_end_ms):
    """Development chronology only. All supplied history has been inspected.

    No row may straddle a boundary; next fold starts after 18h + 35m embargo.
    This is not a newly untouched holdout or qualification of a trading model.
    """
    from datetime import datetime,timezone
    def ms(x):return int(datetime.fromisoformat(x).replace(tzinfo=timezone.utc).timestamp())*1000
    embargo=(18*60+35)*60000
    cuts=(ms('2025-12-01'),ms('2025-12-22'),ms('2026-01-15'))
    if label_end_ms<cuts[0]:return 'TRAIN'
    if asof_ms>=cuts[0]+embargo and label_end_ms<cuts[1]:return 'INNER_VALIDATION'
    if asof_ms>=cuts[1]+embargo and label_end_ms<cuts[2]:return 'CALIBRATION'
    if asof_ms>=cuts[2]+embargo:return 'RETROSPECTIVE_EVALUATION_ALREADY_INSPECTED'
    return 'PURGED_BOUNDARY'
