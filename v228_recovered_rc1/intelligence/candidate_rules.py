"""Audit observational rule facts against native records. Missing old fields remain missing."""
from collections import Counter,defaultdict
import csv,hashlib,io,math
from pathlib import Path
from .native_ledger import iter_directory,event_paths
from .execution_review import broker_seconds,observer_bool
from .research_data import REASONS


def summarize(source,snapshot):
    source=Path(source);files=sorted(source.glob('candidate_rules_*.csv')) if source.is_dir() else []
    if not files:return dict(status='UNAVAILABLE_OLD_SOURCE',observer_schema=1,verified_rows=0,
        explanation='No rule observer; old vectors cannot supply missing per-rule facts',groups={},model_inputs_added=False)
    limit=snapshot['native_records'];facts={}
    for record in iter_directory(source,paths=event_paths(source)[:limit],compact=True):
        if record['event']['kind'] in (1,3):facts[record['state']['sequence']]=record
    groups=defaultdict(list);seen=set();manifest=[];verified=0;anchor_hashes={}
    for path in files:
        session=source/('session_'+path.name[len('candidate_rules_'):])
        with session.open(encoding='utf-8-sig',newline='') as stream:session_rows=list(csv.DictReader(stream))
        if len(session_rows)!=1:raise ValueError('Rule observer session metadata required')
        session_info=session_rows[0]
        contract=source/('candidate_contract_'+path.name[len('candidate_rules_'):])
        contract_bytes=contract.read_bytes()
        contracts=list(csv.DictReader(io.StringIO(contract_bytes.decode('utf-8-sig'))))
        if len(contracts)!=1:raise ValueError('Rule threshold contract required')
        thresholds=contracts[0];p=snapshot['policy']
        if int(thresholds['schema'])!=1 or int(thresholds['logic'])!=2026101707 or any(int(thresholds[k])!=p[k] for k in ('config_hash','feed_hash','policy_hash','horizon')):
            raise ValueError('Rule threshold identity differs')
        expected_thresholds=dict(range_net_max_atr=1.5,range_efficiency_max=.5,trend_net_min_atr=.75,trend_efficiency_min=.35,
            expansion_min_atr=1.5,breakout_net_min_atr=.5,breakout_efficiency_min=.25,break_atr=.05,reclaim_atr=.05,
            invalidation_atr=.1,confirmation_location=.65,counter_efficiency=.7,pullback_touch_atr=.25,
            pullback_minimum_atr=.05,breakout_buffer_atr=.1,retest_band_atr=.25,atr_min_pips=3,atr_max_pips=30,shock_atr=2.5)
        if any(not math.isclose(float(thresholds[k]),v,abs_tol=1e-12) for k,v in expected_thresholds.items()):
            raise ValueError('Unexpected strategy threshold contract')
        raw=path.read_bytes()
        if len(raw)>128*1024**2:raise ValueError('Rule observer exceeds 128 MiB')
        if raw and not raw.endswith(b'\n'):raw=raw[:raw.rfind(b'\n')+1]
        manifest.append(dict(name=path.name,consumed_sha256=hashlib.sha256(raw).hexdigest(),
            threshold_contract=thresholds,threshold_sha256=hashlib.sha256(contract_bytes).hexdigest()))
        for row in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
            seq=int(row['sequence'])
            if seq>limit:continue # Live writer may have advanced beyond the captured immutable prefix.
            if seq in seen:raise ValueError('Duplicate rule observer sequence')
            seen.add(seq);record=facts.get(seq)
            if not record:raise ValueError('Rule observer sequence absent from native anchor/LOCK')
            state,e=record['state'],record['event'];cur=state['current'];a=cur['anchor'];p=snapshot['policy']
            if (int(row['schema'])!=1 or int(row['logic'])!=2026101707 or row['origin']!=snapshot['origin'] or
                int(row['config_hash'])!=p['config_hash'] or int(row['feed_hash'])!=p['feed_hash'] or
                int(row['policy_hash'])!=p['policy_hash'] or int(row['horizon'])!=p['horizon'] or
                broker_seconds(row['analysis_start'])!=e['analysisStart'] or int(row['event_kind'])!=e['kind'] or
                int(row['observed_ms'])!=e['observedMs'] or int(row['direction'])!=cur['candidate']['direction']):
                raise ValueError('Rule observer identity differs from native event')
            lock=e['kind']==3
            expected_asof=e['observedMs'] if lock else a['closeTime']*1000
            ready=lock and not cur['canceled'] and cur['validation']==2 and e['lockedAction']!=0 and e['reason']==0
            if (int(row['feature_asof_ms'])!=expected_asof or expected_asof>e['observedMs'] or
                observer_bool(row['ready_at_lock'])!=ready or observer_bool(row['canceled_at_lock'])!=(lock and cur['canceled'])):
                raise ValueError('Rule observer readiness/feature clock differs')
            regime=a['regime'];routed=1 if regime==1 else 2 if regime in (2,3) else 3 if regime in (4,5) else 0
            if int(row['regime'])!=regime or int(row['setup'])!=routed:raise ValueError('Rule router differs')
            enabled=routed!=0 and observer_bool(session_info[('allow_sr1','allow_tp1','allow_br1')[routed-1]])
            if (row['reason']!=REASONS[e['reason']] or observer_bool(row['anchor_available'])!=bool(a['available']) or
                observer_bool(row['strategy_enabled'])!=enabled or int(session_info['config_hash'])!=p['config_hash'] or
                int(session_info['feed_hash'])!=p['feed_hash']):raise ValueError('Rule observer session/reason differs')
            if [float(row[k]) for k in ('atr_min_pips','atr_max_pips','shock_atr')]!=[3.,30.,2.5]:
                raise ValueError('Unexpected rule thresholds')
            atr=a['volatility']['atr'];z=a['volatility']['zoneATR'];d=1 if regime in (2,4) else -1 if regime in (3,5) else 0
            s=a['structure'];c=a['candle'];trend=a['baselineFastEMA'];slow=a['baselineSlowEMA'];close=a['triggerClose']
            for key,value in [('atr',atr),('zone_atr',z),('range',c['range']),('close_location',c['closeLocation']),
                ('previous_atr',a['volatility']['previousATR']),('volatility_expansion',a['volatility']['expansion']),
                ('prior_close',a['priorClose']),('trigger_close',a['triggerClose'])]:
                if not math.isclose(float(row[key]),value,abs_tol=1e-9):raise ValueError('Rule observer numeric fact differs')
            zone=s['preResistance' if d>0 else 'preSupport'];edge=zone['high'] if d>0 else zone['low']
            expected=dict(sr_call_sweep=s['support']['available'] and a['triggerLow']<s['support']['low']-.05*z,
                sr_call_reclaim=s['support']['available'] and close>s['support']['high']+.05*z,
                sr_put_sweep=s['resistance']['available'] and a['triggerHigh']>s['resistance']['high']+.05*z,
                sr_put_reclaim=s['resistance']['available'] and close<s['resistance']['low']-.05*z,
                tp_pullback=d!=0 and d*a['pullbackNetATR']<=-.05,
                tp_touch=a['triggerLow']<=trend+.25*z if d>0 else d<0 and a['triggerHigh']>=trend-.25*z,
                tp_slow_held=a['triggerLow']>slow-.10*atr if d>0 else d<0 and a['triggerHigh']<slow+.10*atr,
                directional_body=d!=0 and d*c['body']>0,
                directional_location=c['closeLocation']>=.65 if d>0 else d<0 and c['closeLocation']<=1-.65,
                tp_reclaim=d!=0 and d*(close-(trend+d*.05*z))>0,
                br_zone_available=d!=0 and zone['available'],br_breakout=d!=0 and zone['available'] and d*(close-edge)>.10*z,
                atr_pass=3*.0001<=atr<=30*.0001,shock_pass=c['range']<=2.5*z,overlap=a['context']['overlap'])
            for key,value in expected.items():
                if observer_bool(row[key])!=bool(value):raise ValueError('Rule predicate differs from native anchor: '+key)
            retest=cur['retestSeenMs'];age=(e['observedMs']-retest)//1000 if 0<retest<=e['observedMs'] else -1
            if observer_bool(row['retest_seen_at_lock'])!=(lock and retest>0) or int(row['seconds_since_retest'])!=age:
                raise ValueError('Retest clock differs from native state')
            quote=(e['observedMs']-cur['lastQuoteMs'])/1000 if cur['lastQuoteMs']>0 else -1
            if not math.isclose(float(row['quote_age_seconds']),quote,abs_tol=1e-9):raise ValueError('Rule quote age differs')
            reference='anchor_'+str(e['analysisStart'])+'.csv'
            if row['snapshot_ref']!=reference:raise ValueError('Rule snapshot reference differs')
            if reference not in anchor_hashes and (source/reference).is_file():anchor_hashes[reference]=hashlib.sha256((source/reference).read_bytes()).hexdigest()
            groups[(routed,'LOCK' if lock else 'ANCHOR')].append(row);verified+=1
    summary={}
    for (setup,stage),rr in groups.items():
        common=[r for r in rr if observer_bool(r['anchor_available']) and observer_bool(r['atr_pass']) and observer_bool(r['shock_pass']) and observer_bool(r['strategy_enabled']) and not observer_bool(r['overlap'])]
        fields=(['tp_pullback','tp_touch','tp_slow_held','directional_body','directional_location','tp_reclaim'] if setup==2 else
                ['br_zone_available','br_breakout','directional_body','directional_location'] if setup==3 else
                ['sr_call_sweep','sr_call_reclaim','sr_put_sweep','sr_put_reclaim'] if setup==1 else [])
        summary[str(setup)+':'+stage]=dict(rows=len(rr),common_pass=len(common),ready_at_lock=sum(observer_bool(r['ready_at_lock']) for r in rr),
            conditional_pass_counts={key:sum(observer_bool(r[key]) for r in common) for key in fields},
            note='Independent condition counts overlap; not mutually exclusive first-rejection causes')
    return dict(status='VERIFIED_LOCAL_OBSERVER',observer_schema=1,verified_rows=verified,groups=summary,
        native_anchor_lock_rows=len(facts),missing_observer_rows=len(set(facts)-seen),
        observer_files=manifest,anchor_sha256=anchor_hashes,model_inputs_added=False,
        trust='Compared to local native journal, not independent broker authentication')
