"""Causal feature boundaries and ex-post tick timing are different contracts."""
from copy import deepcopy
import json
import hashlib
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
import numpy as np
from intelligence import candidate_data as cd, candidate_features as cf
from intelligence.loss_research import analyze, path_metrics, write, TRAIN_END
from tests.test_demo_learning_native import NativeHarness
from tests.test_v214_execution import tree_hash


def fixture(direction=1, start=1767225600):
    p = dict(feed_hash=1, policy_hash=2, horizon=1)
    r = cd.base_row(start, (start+268)*1000, 1, direction, 1, True, p)
    features = [0.] * len(cf.NAMES)
    features[cf.NAMES.index('candidate_direction')] = direction
    features[cf.NAMES.index('atr_pips')] = 4.
    r.update(features=features, lock_reason='OK', quality_status='ADVERSE', signed_points=-2,
             available_at_ms=(start+601)*1000)
    s = cd.finish([r], p, 'BACKTEST_MT4', (start+1200)*1000, 1, 'a'*64, [start//86400], {})
    entry = start+300
    m = dict(status='VERIFIED_LOCAL_BOOK', contract='V218_MANUAL_PUBLICATION_V1', source_origin='BACKTEST_MT4',
             native_prefix_records=1, signals=[dict(signal_id=start, direction='CALL' if direction == 1 else 'PUT',
             entry_broker_seconds=entry, expiry_broker_seconds=entry+300, published_ms=(start+268)*1000,
             status='LOSS', entry_bid='1.10000', exit_bid=str(1.1-direction*.00002), native_canceled=True)])
    # First favourable at 50 s; final below entry at 270 s. Return to entry is zero, not profit.
    path = [(entry*1000, 1.1, 1.1), ((entry+50)*1000, 1.1+direction*.00001, 1.1+direction*.00001),
            ((entry+200)*1000, 1.1, 1.1), ((entry+260)*1000, 1.1+direction*.00001, 1.1+direction*.00001),
            ((entry+270)*1000, 1.1-direction*.00001, 1.1-direction*.00001),
            ((entry+300)*1000, 1.1-direction*.00002, 1.1-direction*.00002)]
    t = np.array(path, dtype=[('ms','<i8'),('bid','<f8'),('ask','<f8')])
    return s, m, t


class BinaryLossResearchTests(unittest.TestCase):
    def test_forex_and_binary_decision_sources_stay_at_frozen_baseline(self):
        root = Path(__file__).resolve().parents[1]
        baseline = json.loads((root/'baseline_v222_sha256.json').read_text())
        include = root/'mt4/Include/EURUSD_M5_V224'
        names = ['ForexRisk.mqh', 'ForexEngine.mqh', 'ForexProtection.mqh', 'ForexNews.mqh',
                 'ForexAverage.mqh', 'Forecast.mqh', 'Decision.mqh', 'Validation.mqh',
                 'Types.mqh', 'Episode.mqh', 'ManualSignals.mqh', 'Outcomes.mqh']
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((include/name).read_bytes()).hexdigest(),
                                 baseline['mt4/Include/EURUSD_M5_V222/'+name])

    def test_call_put_path_timing_and_integer_point_signs(self):
        for direction in (1, -1):
            s, m, t = fixture(direction)
            report, rows, _, _ = analyze(s, m, t, broker_offset_minutes=0)
            r = rows[0]
            self.assertEqual(r['expost_first_favourable_second'], 50)
            self.assertEqual(r['expost_last_favourable_second'], 260)
            self.assertEqual(r['expost_final_below_entry_second'], 270)
            self.assertEqual(r['expost_mfe_pips'], .1)
            self.assertEqual(r['expost_mae_pips'], .2)
            self.assertFalse(report['forex_performance_inferred'])
            self.assertEqual(report['accepted_filters'], [])

    def test_horizon_diagnostic_does_not_invent_missing_quotes(self):
        s, m, t = fixture()
        r = path_metrics(m['signals'][0], t)
        self.assertEqual(r['expost_10m_status'], 'UNAVAILABLE')
        self.assertEqual(r['expost_15m_status'], 'UNAVAILABLE')

    def test_boundary_price_mismatch_blocks_analysis(self):
        s, m, t = fixture()
        t['bid'][-1] -= .00001
        with self.assertRaisesRegex(ValueError, 'boundary differs'):
            analyze(s, m, t)

    def test_backwards_tick_and_nonfinite_quotes_rejected(self):
        s, m, t = fixture()
        with self.assertRaisesRegex(ValueError, 'backwards'):
            analyze(s, m, t[::-1])
        t['bid'][0] = np.nan
        with self.assertRaisesRegex(ValueError, 'Invalid path quote'):
            analyze(s, m, t)

    def test_future_entry_is_excluded_without_reading_its_outcome(self):
        s, m, _ = fixture(start=TRAIN_END)
        m['signals'][0]['status'] = 'MALFORMED_HELDOUT_DO_NOT_READ'
        report, rows, _, _ = analyze(s, m)
        self.assertEqual(report['development']['n'], 0)
        self.assertEqual(rows, [])

    def test_outcome_crossing_cutoff_is_embargoed(self):
        s, m, _ = fixture(start=TRAIN_END-600)
        report, rows, _, _ = analyze(s, m)
        self.assertEqual(rows, [])

    def test_mismatched_origin_and_feature_checksum_rejected(self):
        s, m, t = fixture()
        m['source_origin'] = 'FOREX_BACKTEST_MT4'
        with self.assertRaisesRegex(ValueError, 'matching'):
            analyze(s, m, t)
        s, m, t = fixture()
        s['rows'][0]['features'][0] += 1
        with self.assertRaisesRegex(ValueError, 'checksum'):
            analyze(s, m, t)

    def test_status_disagrees_with_native_quality_rejected(self):
        s, m, t = fixture()
        m['signals'][0]['status'] = 'WIN'
        with self.assertRaisesRegex(ValueError, 'disagrees'):
            analyze(s, m, t)

    def test_unknown_session_without_confirmed_broker_offset(self):
        s, m, t = fixture()
        _, rows, _, _ = analyze(s, m, t)
        self.assertEqual(rows[0]['session'], 'SESSION_UNKNOWN')

    def test_unavailable_path_schema_and_fresh_output(self):
        s, m, t = fixture()
        no = path_metrics(m['signals'][0], None)
        yes = path_metrics(m['signals'][0], t)
        self.assertEqual(set(no), set(yes))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'review'
            write(out, analyze(s, m))
            self.assertFalse(json.loads((out/'summary.json').read_text())['model_fit'])
            with self.assertRaisesRegex(ValueError, 'fresh'):
                write(out, analyze(s, m))


class BinaryLossNativeCLITests(NativeHarness, unittest.TestCase):
    def test_cli_reads_a_sealed_native_fixture_without_source_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, source = self.execute(tmp, mode=24, direction=-1, testing=True)
            before = tree_hash(source)
            root = Path(__file__).resolve().parents[1]
            out = Path(tmp)/'postmortem'
            proc = subprocess.run([sys.executable, str(root/'tools/review_binary_losses.py'),
                '--source', str(source), '--output', str(out), '--development-end-exclusive', '2026-01-15',
                '--broker-utc-offset-minutes', '0'], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads((out/'summary.json').read_text())
            self.assertEqual(report['development']['LOSS'], 1)
            self.assertEqual(report['accepted_filters'], [])
            self.assertEqual(tree_hash(source), before)
            self.assertTrue((out/'binary_loss_review_v224.zip').is_file())


if __name__ == '__main__':
    unittest.main()
