"""Research contract: closed anchor facts only, independent of trade selection."""
import math

CONTRACT='CLOSED_ANCHOR_UP_V1'
NAMES=('atr_pips','range_atr','body_fraction','lower_wick_fraction','upper_wick_fraction',
    'close_location','momentum_net_atr','efficiency','acceleration','volatility_expansion',
    'ema_gap_atr','baseline_slope_atr','close_fast_ema_atr','close_slow_ema_atr','pullback_net_atr',
    'support_distance_atr','resistance_distance_atr','support_available','resistance_available',
    'structure_up','structure_down','regime_unknown','regime_range','regime_orderly_up',
    'regime_orderly_down','regime_expansion_up','regime_expansion_down','regime_transition','regime_compression')


def extract(current):
    a=current['anchor'];start=int(current['analysisStart']);atr=float(a['volatility']['atr'])
    if not a['available'] or int(a['closeTime'])!=start or start<=0 or start%300 or not math.isfinite(atr) or atr<=0:
        raise ValueError('Unavailable or non-causal closed anchor')
    c=a['candle'];width=max(c['range'],.00001);s=a['structure'];context=a['context']
    values=[atr*10000,c['range']/atr,c['body']/width,c['lowerWick']/width,c['upperWick']/width,
        c['closeLocation'],a['momentum']['netATR'],a['momentum']['efficiency'],a['momentum']['acceleration'],
        a['volatility']['expansion'],(a['fastEMA']-a['slowEMA'])/atr,a['baselineFastSlope']/atr,
        (a['triggerClose']-a['fastEMA'])/atr,(a['triggerClose']-a['slowEMA'])/atr,a['pullbackNetATR'],
        context['supportDistanceATR'] if s['support']['available'] else 0.,
        context['resistanceDistanceATR'] if s['resistance']['available'] else 0.,
        float(s['support']['available']),float(s['resistance']['available']),
        float(s['trend']==1),float(s['trend']==-1)]
    values += [float(a['regime']==r) for r in range(8)]
    if len(values)!=len(NAMES) or not all(math.isfinite(v) and abs(v)<1e6 for v in values):
        raise ValueError('Invalid research feature vector')
    return values
