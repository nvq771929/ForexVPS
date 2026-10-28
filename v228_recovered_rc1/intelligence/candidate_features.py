"""Direction-aware candidate inputs. No outcome or post-LOCK field is accepted."""
import math
from .t1_corrected import NAMES as T1_NAMES

CONTRACT='V215_CANDIDATE_DIRECTION_V1'
ANCHOR_NAMES=('atr_pips','range_atr','body_direction','close_location_direction','rejection_wick','opposing_wick',
    'momentum_direction','efficiency','acceleration_direction','volatility_expansion','ema_gap_direction','slope_direction',
    'close_fast_direction','close_slow_direction','pullback_direction','structure_alignment','own_zone_available',
    'own_zone_distance','target_zone_available','target_zone_distance','setup_sr1','setup_tp1','setup_br1','candidate_direction')
NAMES=ANCHOR_NAMES+('t1_net_direction','t1_favorable_excursion','t1_adverse_excursion','t1_range_atr','t1_close_location_direction',
    'confirmation_margin_atr','risk_distance_atr','reward_distance_atr','reward_available','quote_age_seconds',
    'lock_elapsed_fraction','last_observed_fraction','broker_hour_sin','broker_hour_cos','broker_weekday_sin','broker_weekday_cos')


def extract(values,setup,direction):
    if len(values)!=len(T1_NAMES) or setup not in (1,2,3) or direction not in (-1,1):
        raise ValueError('Candidate feature identity differs')
    if not all(math.isfinite(v) and abs(v)<1e6 for v in values):raise ValueError('Invalid candidate vector')
    f=dict(zip(T1_NAMES,values));d=direction
    if f['candidate_direction']!=d or f['candidate_present']!=1 or f[('candidate_sr1','candidate_tp1','candidate_br1')[setup-1]]!=1:
        raise ValueError('Candidate setup/direction differs from causal vector')
    own='support' if d>0 else 'resistance';other='resistance' if d>0 else 'support'
    anchor=[f['atr_pips'],f['range_atr'],d*f['body_fraction'],f['close_location'] if d>0 else 1-f['close_location'],
        f['lower_wick_fraction' if d>0 else 'upper_wick_fraction'],f['upper_wick_fraction' if d>0 else 'lower_wick_fraction'],
        d*f['momentum_net_atr'],f['efficiency'],d*f['acceleration'],f['volatility_expansion'],d*f['ema_gap_atr'],
        d*f['baseline_slope_atr'],d*f['close_fast_ema_atr'],d*f['close_slow_ema_atr'],d*f['pullback_net_atr'],
        d*(f['structure_up']-f['structure_down']),f[own+'_available'],f[own+'_distance_atr'],f[other+'_available'],
        f[other+'_distance_atr'],float(setup==1),float(setup==2),float(setup==3),float(d)]
    result=anchor+[d*f['t1_net_atr'],f['t1_high_atr'] if d>0 else -f['t1_low_atr'],
        -f['t1_low_atr'] if d>0 else f['t1_high_atr'],f['t1_range_atr'],f['t1_close_location'] if d>0 else 1-f['t1_close_location'],
        f['confirmation_margin_atr'],f['risk_distance_atr'],f['reward_distance_atr'],f['reward_available'],f['quote_age_seconds'],
        f['lock_elapsed_fraction'],f['last_observed_fraction'],f['broker_hour_sin'],f['broker_hour_cos'],f['broker_weekday_sin'],f['broker_weekday_cos']]
    assert len(result)==len(NAMES)
    return result
