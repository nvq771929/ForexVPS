"""Offline chronological TCN experiment. No model here can activate in MT4."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

from . import research_model as rm
from . import tcn_model as tcn
from .sequence_data import build, arrays, CONTRACT
from .t1_corrected import NAMES as CONTEXT_NAMES
from .demo_learning import atomic, csv_bytes, payoff, wilson, weekly_bounds
from .advanced_learning import paired_roi
from .progress import notify

ALGORITHMS = ('logistic', 'hgb', 'tcn')


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def fit_model(dataset, rows, name, progress=None, label='outer', *, validation_rows=None, epochs=None):
    notify(progress, 'fit', done=None, total=None, detail=f'{label}: {name}, {len(rows):,} train-only samples')
    if name == 'tcn':
        validation=arrays(dataset,validation_rows) if validation_rows is not None else None
        return tcn.fit(*arrays(dataset, rows), progress=progress, label=label + ' TCN',validation=validation,epochs=epochs)
    estimator, mean, scale = rm._fit_classifier(rows, name)
    model = rm.export_classifier(estimator, name, mean, scale)
    x = np.asarray([r['features'] for r in rows], dtype=float)
    model.update(feature_names=list(CONTEXT_NAMES), low=x.min(axis=0).tolist(), high=x.max(axis=0).tolist())
    expected = rm._raw(estimator, name, x[:128], mean, scale)
    actual = [rm.raw_score(model, row.tolist()) for row in x[:128]]
    if not np.allclose(expected, actual, atol=1e-9, rtol=0):
        raise ValueError('Baseline JSON export differs from estimator')
    return model


def scores(dataset, rows, model):
    if model['algorithm'] == 'tcn':
        sequence, context, _ = arrays(dataset, rows)
        return tcn.score(model, sequence, context), tcn.domain(model, sequence, context)
    return (np.asarray([rm.raw_score(model, r['features']) for r in rows]),
            np.asarray([rm.in_domain(model, r['features']) for r in rows]))


def probability(raw, slope=1., intercept=0.):
    return 1 / (1 + np.exp(-np.clip(slope * raw + intercept, -35, 35)))


def evaluate(rows, probabilities, domains, prior, by_regime, name):
    selected = []
    predictions = []
    briers, logs, base_briers, base_logs, regime_briers, regime_logs, gains = ([] for _ in range(7))
    for r, p, allowed in zip(rows, probabilities, domains):
        p = float(p)
        d = rm.direction(p) if allowed else 0
        regime_prior = by_regime.get(str(r['regime']), prior)
        move = r['signed_points']
        ret = 0.
        if d:
            proxy = dict(entry_target=r['entry_target'], signed_points=d * move,
                         status='TIE' if move == 0 else 'WIN' if d * move > 0 else 'LOSS')
            selected.append(proxy)
            ret = payoff(proxy)
        bd = rm.direction(regime_prior)
        gains.append(ret - (0. if not bd or move == 0 else .82 if bd * move > 0 else -1.))
        if r['status'] != 'TIE':
            y = int(r['status'] == 'UP')
            for value, bs, ls in ((p, briers, logs), (prior, base_briers, base_logs), (regime_prior, regime_briers, regime_logs)):
                bs.append((value - y) ** 2)
                ls.append(-float(np.log(max(1e-12, value if y else 1 - value))))
        predictions.append(dict(algorithm=name, sample_id=r['sample_id'], entry_target=r['entry_target'],
            p_up=p, direction=d, in_domain=bool(allowed), status=r['status'],
            hypothetical_return_at_82pct=ret, is_execution_trade=False, native_pre_outcome_prediction=False,
            independent_validation=False, source='BACKTEST_MT4_PRICE_RESEARCH',
            rejection_reason='SELECTED' if d else 'BOTH' if not allowed and not rm.direction(p) else 'OUT_OF_DOMAIN' if not allowed else 'LOW_CONFIDENCE'))
    avg = lambda v: sum(v) / len(v) if v else None
    n = sum(r['status'] != 'TIE' for r in selected)
    wins = sum(r['status'] == 'WIN' for r in selected)
    lower, _ = wilson(wins, n)
    roi_lower, _, weeks = weekly_bounds(selected)
    metrics = dict(samples=len(rows), decisive=len(rm.decisive(rows)), selected=len(selected), selected_decisive=n,
        selected_weeks=weeks, coverage=len(selected) / len(rows) if rows else 0., hypothetical_wins=wins,
        hypothetical_ties=sum(r['status'] == 'TIE' for r in selected), win_lower=lower,
        hypothetical_roi=avg([payoff(r) for r in selected]), roi_lower=roi_lower,
        stress_roi=avg([payoff(r, 2) for r in selected]), paired_gain_lower=paired_roi(rows, gains),
        brier_up=avg(briers), log_loss_up=avg(logs), global_baseline_brier=avg(base_briers),
        global_baseline_log_loss=avg(base_logs), regime_baseline_brier=avg(regime_briers),
        regime_baseline_log_loss=avg(regime_logs),
        metric_scope='Historical price direction with hypothetical payout 82%; not Olymp execution or forward performance')
    return metrics, predictions


def split_record(rows):
    return dict(samples=len(rows), decisive=len(rm.decisive(rows)),
                first_target=min((r['entry_target'] for r in rows), default=None),
                last_target=max((r['entry_target'] for r in rows), default=None),
                sample_ids_sha256=hashlib.sha256(rm.canonical([r['sample_id'] for r in rows])).hexdigest())


def train(snapshot, native_digest, output, progress=None):
    """Caller provides a verified prepared cache; inputs never change."""
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a fresh deep output directory')
    notify(progress, 'labels', done=None, total=None, detail='Build 32 continuous closed-anchor vectors plus T+1 context')
    dataset = build(snapshot)
    rows = dataset['rows']
    training, calibration, test = rm.split(rows)
    tr, ca = rm.decisive(training), rm.decisive(calibration)
    inner_train, inner_test = [], []
    if tr:
        days = sorted({r['entry_target'] // 86400 for r in tr})
        cut = days[int(len(days) * .8)] * 86400
        inner_test = [r for r in tr if r['entry_target'] >= cut]
        first_lock = min(r['locked_at_ms'] for r in inner_test)
        inner_train = [r for r in tr if r['entry_target'] < cut - rm.EMBARGO and r['available_at_ms'] < first_lock]
    tcn.seed()
    from .runtime_fingerprint import fingerprint
    runtime=fingerprint()
    plan = dict(schema=1, software_version='2.15', feature_contract=CONTRACT,
        native_dataset_sha256=native_digest, dataset=dataset['audit'], policy=snapshot['policy'], cutoff=snapshot['asof'],
        splits={name: split_record(rr) for name, rr in [('train', training), ('calibration', calibration), ('test', test),
                                                     ('inner_train', inner_train), ('inner_selection', inner_test)]},
        embargo_seconds=rm.EMBARGO, algorithms=list(ALGORITHMS), tcn_parameters=tcn.PARAMETERS,
        baseline_parameters=rm.PARAMETERS, selection='lowest raw Brier on inner chronological selection only; never choose on outer test',
        normalization='train-only; V2 binary/signed flags retain scale 1; numeric inputs clipped to +/-6 training sigma', threshold_up=rm.THRESHOLD,
        epoch_selection='TCN validation log loss with patience inside chronological train only; outer refit fixed at selected epoch',
        runtime_sha256=hashlib.sha256(rm.canonical(runtime)).hexdigest(),
        assumed_payout=.82, stress_points=2, validation_scope='HISTORICAL_EXPLORATION',
        independent_confirmation_required=True, automatic_filter=False, import_allowed=False,
        limitation='Temporal input is recorded closed-anchor features, not raw OHLC. Historical test has been explored before.')
    plan['plan_sha256'] = hashlib.sha256(rm.canonical(plan)).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    atomic(output / 'experiment_plan.json', json_bytes(plan))
    atomic(output / 'runtime_fingerprint.json',json_bytes(runtime))
    atomic(output / 'feature_migration.json',json_bytes(dataset['audit']['feature_migration']))
    from .candidate_quality import train as train_candidates
    quality,quality_predictions,quality_model=train_candidates(dataset['all_corrected_rows'],
        dict(train=training,calibration=calibration,test=test),native_digest)
    atomic(output/'candidate_quality_report.json',json_bytes(quality))
    atomic(output/'candidate_quality_model.json',json_bytes(quality_model))
    atomic(output/'candidate_quality_predictions.csv',csv_bytes(sorted(quality_predictions[0]) if quality_predictions else ['status'],quality_predictions))
    report = dict(schema=1, status='DEEP_NOT_TRAINED', feature_contract=CONTRACT, dataset=dataset['audit'],
        splits=plan['splits'], dataset_sha256=native_digest, experiment_plan_sha256=plan['plan_sha256'],
        execution_trade_count=0, live_forward_observations=0, automatic_live_filter=False,
        model_import_allowed=False, validation_scope='HISTORICAL_EXPLORATION', independent_confirmation_required=True,
        feature_migration=dataset['audit']['feature_migration'],candidate_quality_status=quality['status'])
    enough = (len(tr) >= 400 and len(ca) >= 100 and len(rm.decisive(test)) >= 150 and
              len(inner_train) >= 200 and len(inner_test) >= 100 and
              all(len({r['status'] for r in rr}) == 2 for rr in (tr, ca, inner_train, inner_test)))
    if not enough:
        report['reason'] = 'Need 400 train / 100 calibration / 150 test decisive; inner 200/100 and both directions. No thresholds were loosened.'
        atomic(output / 'deep_research_report.json', json_bytes(report))
        return report
    # Preserve deterministic CPU fitting and bounded sklearn parallelism.
    tcn.seed()
    selection = {}
    models = {}
    comparisons = {}
    predictions = []
    curves=[]
    selected_epochs=tcn.PARAMETERS['epochs']
    (output/'models').mkdir(exist_ok=True)
    def save_component(name,stage,model,rr):
        a=dict(schema=1,kind='V213_RESEARCH_COMPONENT',feature_contract=CONTRACT,
            label_source='BACKTEST_MT4_PRICE_RESEARCH',dataset_sha256=native_digest,plan_sha256=plan['plan_sha256'],
            source_origin='BACKTEST_MT4',logic=snapshot['policy']['logic'],policy=snapshot['policy'],
            algorithm=name,stage=stage,training=split_record(rr),model=model,
            eligible_for_live_filter=False,eligible_for_legacy_import=False,phase='OFFLINE_RESEARCH_ONLY')
        a['payload_sha256']=hashlib.sha256(rm.canonical(a)).hexdigest()
        atomic(output/'models'/(stage+'_'+name+'.json'),json_bytes(a))
        if name=='tcn':
            curves.extend(dict(stage=stage,algorithm=name,**r) for r in model['training']['curves'])
    with threadpool_limits(limits=2):
        for name in ALGORITHMS:
            model = fit_model(dataset, inner_train, name, progress, 'inner',validation_rows=inner_test if name=='tcn' else None)
            if name=='tcn':selected_epochs=model['training']['selected_epoch']
            save_component(name,'inner',model,inner_train)
            raw, _ = scores(dataset, inner_test, model)
            target = np.asarray([r['status'] == 'UP' for r in inner_test])
            selection[name] = float(np.mean((probability(raw) - target) ** 2))
        chosen = min(ALGORITHMS, key=lambda name: (selection[name], ALGORITHMS.index(name)))
        # Decision written before any calibration/test result is inspected.
        atomic(output / 'inner_selection.json', json_bytes(dict(scores=selection, chosen=chosen,tcn_selected_epoch=selected_epochs,
               selection_scope='INNER_TRAIN_ONLY', plan_sha256=plan['plan_sha256'])))
        prior = (sum(r['status'] == 'UP' for r in tr) + 1) / (len(tr) + 2)
        buckets = defaultdict(list)
        for r in tr:
            buckets[str(r['regime'])].append(r)
        by_regime = {k: (sum(r['status'] == 'UP' for r in rr) + 10 * prior) / (len(rr) + 10) for k, rr in buckets.items()}
        for name in ALGORITHMS:
            model = fit_model(dataset, tr, name, progress, 'outer',epochs=selected_epochs if name=='tcn' else None)
            notify(progress, 'calibrate', done=None, total=None, detail=name + ': separate later calibration dates')
            raw_cal, _ = scores(dataset, ca, model)
            calibrator = LogisticRegression(C=1., solver='lbfgs', max_iter=1000, tol=1e-8)
            calibrator.fit(raw_cal.reshape(-1, 1), [r['status'] == 'UP' for r in ca])
            slope, intercept = float(calibrator.coef_[0, 0]), float(calibrator.intercept_[0])
            if slope <= 0:
                comparisons[name] = dict(status='REJECTED_CALIBRATION', calibration_slope=slope, failures=['calibration_reverses_ranking'])
                save_component(name,'outer',model,tr)
                continue
            model.update(calibration_slope=slope, calibration_intercept=intercept)
            save_component(name,'outer',model,tr)
            # Verify that the actual JSON roundtrip retains all scoring facts.
            restored = json.loads(rm.canonical(model))
            probe = test[:32]
            if not np.allclose(scores(dataset, probe, restored)[0], scores(dataset, probe, model)[0], atol=1e-7, rtol=0):
                raise ValueError('JSON model score changed after roundtrip')
            notify(progress, 'evaluate', done=None, total=None, detail=name + ': frozen outer test, no tuning')
            raw, domain = scores(dataset, test, model)
            probs = probability(raw, slope, intercept)
            metrics, pred = evaluate(test, probs, domain, prior, by_regime, name)
            failures = rm.gates(metrics)
            days = sorted({r['entry_target'] // 86400 for r in test})
            slices = []
            for i in range(3):
                block = set(days[len(days) * i // 3:len(days) * (i + 1) // 3])
                ids = [j for j, r in enumerate(test) if r['entry_target'] // 86400 in block]
                metric, _ = evaluate([test[j] for j in ids], probs[ids], domain[ids], prior, by_regime, name)
                failed = []
                if metric['selected_decisive'] < 30:
                    failed.append('selected_samples')
                if metric['brier_up'] is None or metric['brier_up'] >= min(metric['global_baseline_brier'], metric['regime_baseline_brier']):
                    failed.append('probability_quality')
                if metric['stress_roi'] is None or metric['stress_roi'] <= 0:
                    failed.append('stress_roi')
                slices.append(dict(slice=i + 1, metrics=metric, failures=failed))
            if any(s['failures'] for s in slices):
                failures.append('chronological_holdout_slices')
            comparisons[name] = dict(status='OFFLINE_GATES_PASSED' if not failures else 'NOT_QUALIFIED',
                offline=metrics, failures=failures, heldout_slices=slices, calibration_slope=slope,
                rejection_counts=dict(Counter(r['rejection_reason'] for r in pred)),training=model.get('training'))
            model.update(baseline_global=prior, baseline_by_regime=by_regime, phase='OFFLINE_RESEARCH_ONLY')
            models[name] = model
            predictions.extend(pred)
    result = comparisons[chosen]
    candidate = dict(schema=1, kind='V213_DEEP_PRICE_RESEARCH', feature_contract=CONTRACT,
        logic=snapshot['policy']['logic'], label_source='BACKTEST_MT4_PRICE_RESEARCH', source_origin='BACKTEST_MT4',
        policy=snapshot['policy'], dataset_sha256=native_digest, input_sha256=dataset['audit']['input_sha256'],
        plan_sha256=plan['plan_sha256'], selected_algorithm=chosen, inner_selection=selection,
        eligible_for_live_filter=False, eligible_for_legacy_import=False, production_promoted=False,
        validation_scope='HISTORICAL_EXPLORATION', independent_confirmation_required=True,
        sequence_length=32, sequence_channels=dataset['audit']['sequence_channels'], context_features=list(CONTEXT_NAMES),
        tcn_selected_epoch=selected_epochs,
        model=models.get(chosen), results=comparisons)
    candidate['payload_sha256'] = hashlib.sha256(rm.canonical(candidate)).hexdigest()
    report.update(status='DEEP_TRAINED_OFFLINE_REVIEW_ONLY' if result['status'] == 'OFFLINE_GATES_PASSED' else 'DEEP_TRAINED_NOT_QUALIFIED',
        selected_algorithm=chosen, tcn_selected_in_inner=chosen == 'tcn', inner_selection=selection,
        comparison=comparisons, note='No model is activated; compare the same sequence-eligible dates. Logistic/HGB use last T+1 context, TCN also uses sequence.')
    report['tcn_selected_epoch']=selected_epochs
    if chosen not in models:
        report['status'] = 'DEEP_CANDIDATE_REJECTED'
    notify(progress, 'export', done=0, total=1, unit='experiment', detail=report['status'])
    atomic(output / 'deep_model_candidate.json', json_bytes(candidate))
    atomic(output / 'deep_comparison.json', json_bytes(dict(selected_before_outer_test=chosen, inner_selection=selection, models=comparisons,
           independent_confirmation_required=True, automatic_filter=False)))
    atomic(output / 'deep_research_report.json', json_bytes(report))
    atomic(output / 'deep_predictions.csv', csv_bytes(sorted(predictions[0]) if predictions else ['status'], predictions))
    atomic(output / 'learning_curves.csv',csv_bytes(sorted(curves[0]) if curves else ['status'],curves))
    notify(progress, 'export', done=1, total=1, unit='experiment', detail='OFFLINE ONLY; no model import or EA change')
    return report
