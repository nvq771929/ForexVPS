"""Feature contract 1: only the immutable pre-entry LOCK snapshot, never outcomes."""
import math

VERSION=1
NAMES=('atr_pips','range_atr','body_fraction','aligned_wick','aligned_close',
    'aligned_momentum','efficiency','aligned_acceleration','volatility_expansion',
    'aligned_ema_gap','aligned_baseline_slope','reward_distance','confirmation_margin',
    'adverse_excursion','favorable_excursion','sr1','tp1','br1','direction',
    'aligned_pullback','risk_distance')


def extract(current):
    a=current['anchor'];c=current['candidate'];d=current['lockedDirection'];atr=a['volatility']['atr']
    if d not in (-1,1) or not a['available'] or not math.isfinite(atr) or atr<=0:
        raise ValueError('Unavailable pre-lock features')
    candle=a['candle'];width=max(candle['range'],.00001);bid=current['latestBid']
    adverse=a['triggerClose']-current['lowestBid'] if d==1 else current['highestBid']-a['triggerClose']
    favorable=current['highestBid']-a['triggerClose'] if d==1 else a['triggerClose']-current['lowestBid']
    result=[atr*10000,candle['range']/atr,candle['body']/width,
        d*(candle['lowerWick']-candle['upperWick'])/width,d*(candle['closeLocation']-.5)*2,
        d*a['momentum']['netATR'],a['momentum']['efficiency'],d*a['momentum']['acceleration'],a['volatility']['expansion'],
        d*(a['fastEMA']-a['slowEMA'])/atr,d*a['baselineFastSlope']/atr,
        d*(c['extension']-bid)/atr,d*(bid-c['confirmation'])/atr,adverse/atr,favorable/atr,
        float(c['setup']==1),float(c['setup']==2),float(c['setup']==3),float(d),d*a['pullbackNetATR'],
        d*(bid-c['invalidation'])/atr]
    if len(result)!=len(NAMES) or not all(math.isfinite(v) and abs(v)<1e6 for v in result):
        raise ValueError('Non-finite pre-lock features')
    return result
