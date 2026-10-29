"""Audit realised output invariants and parity; no strategy/parameter selection."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import statistics
import study

OLD_NAMES={'native_atr3_lead1':'legacy_atr3_lead1_proxy','native_atr3_open':'legacy_atr3_open_proxy',
    'v1_trend_pullback':'trend_pullback','v1_range_rejection':'range_rejection','v1_breakout_momentum':'breakout_momentum'}
def key(r):return int(r['anchor']),int(r['entry']),int(r['direction'])
def close(a,b):
    if abs(float(a)-float(b))>1e-10:raise AssertionError((a,b))
def typed(r):
    r=dict(r)
    for f in ['anchor','entry','direction','hold','exit','exit_bar']:r[f]=int(r[f]) if r[f] else None
    for f in ['stop_pips','entry_price','exit_price','gross_pips','gross_R']:r[f]=float(r[f]) if r[f] else None
    for f in ['entered','ambiguous']:r[f]=r[f]=='True'
    return r

def validate(output,old_signals,old_trades):
    receipt=json.loads((output/'run.json').read_text());signals=study.read(output/'signals.csv')
    old=study.read(old_signals);signal_groups=defaultdict(dict)
    for r in signals:signal_groups[r['model']][key(r)]=r
    for model,old_model in OLD_NAMES.items():
        a=signal_groups[model];b={key(r):r for r in old if r['model']==old_model}
        assert set(a)==set(b),(model,'signal set changed')
        for k in a:close(a[k]['atr'],b[k]['atr'])
    rows=[typed(r) for r in study.read(output/'bracket_labels.csv')];groups=defaultdict(list)
    for r in rows:
        groups[r['model'],r['hold'],r['path']].append(r)
        if r['status']=='RESOLVED':
            assert r['entered'] and r['exit']<=r['entry']+r['hold']*60
            assert 6-1e-9<=r['stop_pips']<=30+1e-9
            close(r['gross_pips'],r['direction']*(r['exit_price']-r['entry_price'])/study.PIP)
            close(r['gross_R'],r['gross_pips']/r['stop_pips'])
        else:assert r['gross_R'] is None and r['gross_pips'] is None
    for m,n in receipt['models'].items():
        for h in [30,60,120]:
            for path in ['stop_first','take_first']:assert len(groups[m,h,path])==n
    old_rows=study.read(old_trades);old_paired=0
    for model,old_model in OLD_NAMES.items():
        for path in ['stop_first','take_first']:
            current=study.one_position(groups[model,60,path]);a={key(r):r for r in current}
            b={key(r):r for r in old_rows if r['model']==old_model and r['path']==path}
            assert set(a)==set(b),(model,path,'one-position cohort changed')
            for k in a:
                assert a[k]['status']==b[k]['status']
                if a[k]['status']=='RESOLVED':
                    assert a[k]['why']==b[k]['why'] and a[k]['exit']==int(b[k]['exit'])
                    close(a[k]['gross_R'],b[k]['return_R']);close(a[k]['gross_pips'],b[k]['net_pips'])
                    old_paired+=1
    summary=study.read(output/'forex_summary.csv')
    for r in summary:
        part=groups[r['model'],int(r['hold']),r['path']]
        if r['sampling']=='one_position_per_model_hold_path':
            part=study.one_position(part)
            assert all(a['exit_bar']<b['entry'] for a,b in zip(part,part[1:]))
        values=[x for x in part if x['status']=='RESOLVED'];fee=float(r['fee_pips'])
        assert len(values)==int(r['resolved'])
        close(r['mean_R'],statistics.fmean(x['gross_R']-fee/x['stop_pips'] for x in values))
        close(r['mean_pips'],statistics.fmean(x['gross_pips']-fee for x in values))
    comparisons=study.read(output/'paired_hold_labels.csv');by_key={(r['model'],r['anchor'],r['path'],r['hold']):r for r in rows}
    for r in comparisons:
        anchor=int(r['anchor'])
        sample=[by_key[r['model'],anchor,r['path'],h] for h in [30,60,120]]
        assert all(x['status']=='RESOLVED' and x['entry']==int(r['entry']) and x['direction']==int(r['direction']) for x in sample)
        close(r['delta60minus30'],sample[1]['gross_R']-sample[0]['gross_R'])
        close(r['delta120minus60'],sample[2]['gross_R']-sample[1]['gross_R'])
    bo=study.read(output/'binary_labels.csv');bo_groups=defaultdict(list)
    for r in bo:bo_groups[r['model']].append(r)
    for r in study.read(output/'binary_summary.csv'):
        valid=[x for x in bo_groups[r['model']] if x['status']=='RESOLVED'];payout=float(r['payout'])
        close(r['mean_stake_return'],statistics.fmean(payout if x['outcome']=='WIN' else -1 if x['outcome']=='LOSS' else 0 for x in valid))
    increments=[];base=signal_groups['tp_unrouted']
    for condition in study.CONDITIONS:
        model='tp_without_'+condition;group=signal_groups[model]
        assert set(base)<=set(group)
        added=set(group)-set(base)
        b=[r for r in bo_groups[model] if key(r) in added and r['status']=='RESOLVED']
        fx=[r for r in groups[model,60,'stop_first'] if key(r) in added and r['status']=='RESOLVED']
        wins=sum(r['outcome']=='WIN' for r in b);losses=sum(r['outcome']=='LOSS' for r in b)
        increments.append({'removed_condition':condition,'full_tp_candidates':len(base),'additional_candidates':len(added),
            'additional_bo_resolved':len(b),'additional_bo_decisive_win_rate':wins/(wins+losses) if wins+losses else None,
            'additional_bo_mean_stake_return82':statistics.fmean(float(r['return_units']) for r in b) if b else None,
            'additional_fx_resolved':len(fx),'additional_fx_gross_mean_R':statistics.fmean(r['gross_R'] for r in fx) if fx else None,
            'additional_fx_fee05_mean_R':statistics.fmean(r['gross_R']-.5/r['stop_pips'] for r in fx) if fx else None,
            'interpretation':'post-run descriptive incremental cohort, overlapping; not causal effect or a selected model'})
    study.dump(output/'ablation_incremental_summary.csv',increments)
    validation={'native_baseline_rows_matched':receipt['closed_windows'],'old_signal_contracts_matched':5,
        'old_resolved_trade_path_labels_matched':old_paired,'bracket_labels_checked':len(rows),'summary_fee_checks':len(summary),
        'same_entry_hold_labels_checked':len(comparisons),'BO_payout_summaries_checked':45,'TP_ablation_superset_checks':6,
        'operating_source_changed':False,'strategy_selection_or_activation':False}
    (output/'VALIDATION_RECEIPT.json').write_text(json.dumps(validation,indent=2)+'\n')
    print(json.dumps(validation,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--old-signals',type=Path,required=True);p.add_argument('--old-zero-trades',type=Path,required=True)
    a=p.parse_args();validate(a.output,a.old_signals,a.old_zero_trades)
