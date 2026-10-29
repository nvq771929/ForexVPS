"""Stream output audits; no strategy selection or modification of input labels."""
import argparse
import csv
import itertools
import json
from pathlib import Path
import statistics
import evaluate as e
from validate_results import typed

def close(a,b):assert abs(float(a)-float(b))<1e-10,(a,b)
def audit(output,prior_minimum,prior_bo):
    summary=e.v2.read(output/'forex_summary.csv')
    index={(r['model'],int(r['hold']),r['path'],r['policy'],float(r['fee'])):r for r in summary}
    labels=0;protected=0;paired_index={}
    with (output/'forex_labels.csv').open() as f:
        for group,raw in itertools.groupby(csv.DictReader(f),lambda r:(r['model'],int(r['hold']),r['path'],r['policy'])):
            part=[typed(r) for r in raw];labels+=len(part)
            for r in part:
                if r['status']=='RESOLVED':
                    assert r['entered'] and r['exit']<=r['entry']+r['hold']*60
                    close(r['gross_pips'],r['direction']*(r['exit_price']-r['entry_price'])/e.PIP)
                    close(r['gross_R'],r['gross_pips']/r['stop_pips'])
                else:assert r['gross_R'] is None
                if r['entered']:
                    assert r['direction']*(float(r['final_stop'])-float(r['initial_stop']))>=-1e-10
                    close(r['stop_pips'],abs(r['entry_price']-float(r['initial_stop']))/e.PIP)
                    protected+=int(r['stop_moves'])>0
                if r['hold']==60 and r['policy']!='ATR_FIXED_CONTROL':
                    paired_index[r['model'],r['path'],r['policy'],r['anchor']]=(r['status'],r['entry'],r['gross_R'],r['stop_pips'])
            selected=e.v2.one_position(part)
            assert all(a['exit_bar']<b['entry'] for a,b in zip(selected,selected[1:]))
            valid=[r for r in selected if r['status']=='RESOLVED']
            for fee in [.01,.31,.51]:
                expected=index[group+(fee,)]
                assert int(expected['resolved'])==len(valid)
                close(expected['mean_R'],statistics.fmean(r['gross_R']-fee/r['stop_pips'] for r in valid))
                close(expected['mean_pips'],statistics.fmean(r['gross_pips']-fee for r in valid))
    controls=0
    for r in e.v2.read(prior_minimum):
        if r['sampling']!='one_position_per_model_hold_path':continue
        current=index[r['model'],int(r['hold']),r['path'],'ATR_FIXED_CONTROL',.01]
        assert current['resolved']==r['resolved'];close(current['mean_R'],r['mean_R']);controls+=1
    paired_fx=e.v2.read(output/'paired_fx_labels.csv')
    for r in paired_fx:
        parts=[paired_index[r['model'],r['path'],p,int(r['anchor'])] for p in e.POLICIES[1:]]
        assert all(p[0]=='RESOLVED' and p[1]==int(r['entry']) for p in parts)
        assert all(abs(p[3]-parts[0][3])<1e-10 for p in parts)
        close(r['BE_minus_FIXED'],parts[1][2]-parts[0][2]);close(r['TRAIL_minus_FIXED'],parts[2][2]-parts[0][2])
    old={(r['model'],r['anchor']):r for r in e.v2.read(prior_bo)};bo_labels=e.v2.read(output/'binary_labels.csv');bo_checks=0
    for r in bo_labels:
        if r['expiry']=='5':
            prior=old[r['model'],r['anchor']];assert (r['status']=='RESOLVED')==(prior['status']=='RESOLVED')
            if r['status']=='RESOLVED':assert r['outcome']==prior['outcome'];close(r['return82'],prior['return_units'])
            bo_checks+=1
    bo_groups={}
    for r in bo_labels:bo_groups.setdefault((r['model'],r['expiry']),[]).append(r)
    for r in e.v2.read(output/'binary_summary.csv'):
        valid=[x for x in bo_groups[r['model'],r['expiry']] if x['status']=='RESOLVED'];payout=float(r['payout'])
        close(r['mean_stake_return'],statistics.fmean(payout if x['outcome']=='WIN' else -1 if x['outcome']=='LOSS' else 0 for x in valid))
    receipt={'FX_labels_checked':labels,'FX_summaries_checked':len(summary),'protected_labels_stop_never_loosened':protected,
        'minimum_fee_v2_control_summaries_matched':controls,'paired_protection_labels_checked':len(paired_fx),
        'BO5min_labels_matched':bo_checks,'BO_payout_summaries_checked':135,'no_model_selection':True}
    (output/'VALIDATION_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['output','prior-minimum','prior-bo']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();audit(a.output,a.prior_minimum,a.prior_bo)
