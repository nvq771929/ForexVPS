"""Price-direction observations are research rows, never executed trade results."""
from collections import Counter
from .research_features import extract,CONTRACT
from .progress import notify

REASONS=('OK','HISTORY_SHORT','HISTORY_GAP','BAD_OHLC','NO_SETUP','AMBIGUOUS','ZONE_UNKNOWN',
    'VOLATILITY_RESEARCH_FILTER','COUNTERPRESSURE','QUOTE_GAP','BAD_QUOTE','STRUCTURAL_BREAK',
    'EXTENSION_REACHED','LOCK_MISSED','NOT_CONFIRMED','MODEL_UNAVAILABLE','MODEL_OOD','SHADOW_ONLY',
    'PAYOUT_STALE','NO_EDGE','PAUSED','RESTART','STORAGE_ERROR','ENTRY_MISSED','OUTCOME_MISSED',
    'PENDING_FULL','CONFIG_CHANGED','TIME_ANOMALY','WAIT_QUOTE','CONTEXT_UNSUPPORTED','RETEST_PENDING','STRATEGY_DISABLED')


class Funnel:
    def __init__(self):
        self.events=Counter();self.starts=Counter();self.locks=Counter();self.entries=Counter();self.cancels=Counter()
        self.counts=Counter();self.gaps=Counter();self.boundaries=set();self.regimes=Counter()

    def observe(self,record):
        e=record['event'];s=record['state']['current'];kind=e['kind'];self.events[str(kind)]+=1
        if kind==1:
            self.counts['analysis_starts']+=1;a=s['anchor'];c=s['candidate']
            self.starts[REASONS[c['reason']]]+=1;self.regimes[str(a['regime'])]+=1
            self.counts['ready_closed_anchors']+=int(a['available'] and a['closeTime']==s['analysisStart'])
            self.counts['candidate_formed']+=int(c['direction'] in (-1,1))
            self.counts['atr_below_3_pips_descriptive']+=int(a['volatility']['atr']*10000<3)
        elif kind==3:
            self.counts['locks']+=1;self.locks[REASONS[e['reason']]]+=1
            self.counts['confirmed_at_lock']+=int(e['lockedDirection'] in (-1,1) and e['validation']==2 and not s['canceled'])
            self.counts['published_at_lock']+=int(e['lockedAction'] in (-1,1))
        elif kind==4:self.cancels[REASONS[e['reason']]]+=1
        elif kind==5:
            self.counts['entry_records']+=1;self.entries[REASONS[e['reason']]]+=1
            self.counts['simulated_execution_entries']+=int(e['signal'])
            self.counts['canceled_at_entry']+=int(s['canceled'])
        elif kind==6:
            self.counts['execution_primary_outcomes']+=int(e['signal'] and e['selectedHorizon']==e['outcomeHorizon'])
            if (s['exists'] and not s['entered'] and not s['canceled'] and s['lastQuoteMs']>0 and
                e['observedMs']==s['targetTime']*1000 and s['analysisStart'] not in self.boundaries):
                self.boundaries.add(s['analysisStart']);gap=(e['observedMs']-s['lastQuoteMs'])/1000
                self.gaps[str(gap)]+=1;self.counts['boundary_gaps_sampled']+=1
                self.counts['boundary_gaps_over_3_seconds']+=int(gap>3)

    def result(self):
        return dict(counts=dict(self.counts),events_by_kind=dict(self.events),candidate_reasons=dict(self.starts),
            lock_reasons=dict(self.locks),entry_reasons=dict(self.entries),cancellation_events_by_reason=dict(self.cancels),
            regimes_at_start=dict(self.regimes),boundary_previous_quote_gap_seconds=dict(self.gaps),
            note='Boundary gaps are quote observations, not canceled trades; reason counts are stage-specific.')


def build(groups,policy,asof,origin,points,progress=None):
    rows=[];excluded=Counter();h=policy['horizon'];total=len(groups)
    notify(progress,'labels',done=0,total=total,unit='nhom',detail='Tao tap NGHIEN CUU rieng, ke ca WAIT/huy')
    for index,(start,records) in enumerate(sorted(groups.items()),1):
        if index%1000==0:notify(progress,'labels',done=index,total=total,unit='nhom')
        locks=[r for r in records if r['event']['kind']==3]
        entries=[r for r in records if r['event']['kind']==5]
        if len(locks)>1 or len(entries)>1:raise ValueError('Duplicate research lock or entry')
        if not locks:excluded['no_lock']+=1;continue
        lock=locks[0];e=lock['event'];current=lock['state']['current'];target=int(e['targetTime'])
        if (target!=start+300 or current['analysisStart']!=start or current['targetTime']!=target):
            raise ValueError('Research anchor/entry relationship changed')
        if (not current['locked'] or e['lockedAtMs']!=e['observedMs'] or
            not start*1000<=e['observedMs']<=(target-31)*1000):
            excluded['lock_outside_forecast_window']+=1;continue
        try:features=extract(current)
        except (KeyError,ValueError):excluded['invalid_closed_anchor']+=1;continue
        if not entries:excluded['no_observed_entry']+=1;continue
        entry=entries[0]['event']
        if not target*1000<=entry['observedMs']<=(target+2)*1000:
            excluded['entry_outside_window']+=1;continue
        try:entry_points=points(entry['bid'])
        except ValueError:excluded['invalid_entry_price']+=1;continue
        if entry['targetTime']!=target:raise ValueError('Research entry target changed')
        row=dict(source='BACKTEST_MT4_PRICE_RESEARCH' if origin=='BACKTEST_MT4' else 'LIVE_MT4_PRICE_RESEARCH',
            cohort=CONTRACT,is_execution_trade=False,
            sample_id=f"{policy['feed_hash']:08x}.{policy['policy_hash']:08x}.{start}.{h}",
            analysis_start=start,entry_target=target,expiry_target=target+h*300,horizon=h,
            locked_at_ms=int(e['observedMs']),feature_asof_ms=int(current['anchor']['closeTime'])*1000,
            entry_observed_ms=int(entry['observedMs']),entry_bid=float(entry['bid']),features=features,
            exit_observed_ms=None,exit_bid=None,signed_points=None,available_at_ms=None,status='OPEN',
            regime=int(current['anchor']['regime']),candidate_present=current['candidate']['direction'] in (-1,1),
            execution_signal_observed=bool(entry['signal']),lock_reason=REASONS[e['reason']],
            entry_reason=REASONS[entry['reason']],canceled_at_entry=bool(entries[0]['state']['current']['canceled']))
        outcomes=[r['event'] for r in records if r['event']['kind']==6 and r['event']['outcomeHorizon']==h]
        if len(outcomes)>1:raise ValueError('Duplicate research selected-expiry outcome')
        if outcomes:
            result=outcomes[0];due=row['expiry_target']*1000
            if result['targetTime']!=target or points(result['bid'])!=entry_points:
                raise ValueError('Research outcome entry identity changed')
            if result['signal']!=entry['signal'] or result['selectedHorizon']!=(h if entry['signal'] else 0):
                raise ValueError('Research outcome signal/horizon identity changed')
            if result['outcome']==9:
                row['status']='UNAVAILABLE';excluded['missing_expiry_quote']+=1
            else:
                if not due<=result['observedMs']<=due+2000:raise ValueError('Research expiry outside exact quote window')
                movement=points(result['auxiliaryPrice'])-entry_points
                if result['outcome']!=((movement>0)-(movement<0)):raise ValueError('Research price move disagrees with native outcome')
                row.update(exit_observed_ms=int(result['observedMs']),exit_bid=float(result['auxiliaryPrice']),
                    signed_points=movement,available_at_ms=int(result['observedMs'])+1000,
                    status='UP' if movement>0 else 'DOWN' if movement<0 else 'TIE')
        elif asof>row['expiry_target']+2:
            row['status']='UNAVAILABLE';excluded['missing_outcome_record']+=1
        rows.append(row)
    notify(progress,'labels',done=total,total=total,unit='nhom',detail=f'{len(rows):,} mau NGHIEN CUU; khong cong vao WIN/LOSS lenh')
    counts=Counter(r['status'] for r in rows)
    return rows,dict(rows=len(rows),status_counts=dict(counts),exclusions=dict(excluded),
        eligible_closed_labels=sum(r['status'] in ('UP','DOWN','TIE') and r['available_at_ms']<asof*1000 for r in rows),
        execution_trade_count=0,label_meaning='Observed future Bid price direction, not a traded WIN/LOSS',
        feature_contract=CONTRACT,tick_provenance='MT4_TESTER_MODEL_UNVERIFIED')
