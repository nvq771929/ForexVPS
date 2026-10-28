"""Full-bundle companions select V224 defaults without redirecting explicit old data."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import run_demo_learning as learner
from tools import import_history as importer

ROOT = Path(__file__).resolve().parents[1]


class V224CompanionTests(unittest.TestCase):
    def journal(self, root, name):
        p = root/'MQL4/Files/BO_V2'/name
        p.mkdir(parents=True)
        (p/'demo_policy.csv').write_text('test-only placeholder; watch is mocked\n')
        return p

    def test_data_folder_default_resolves_v224_even_with_old_instance_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self.journal(root, 'v228_demo_EURUSD')
            self.journal(root, 'v222_demo_EURUSD')
            with patch.object(learner, 'ROOT', root), patch.object(learner, 'watch', return_value=0) as watch:
                self.assertEqual(learner.main(['--source', str(root)]), 0)
                self.assertEqual(watch.call_args.args[0], target.resolve())
            self.assertEqual((root/'demo-learning-path.txt').read_text().strip(), str(target.resolve()))

    def test_explicit_legacy_journal_not_redirected_to_new_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = self.journal(root, 'v219_forward_gap01_EURUSD')
            self.journal(root, 'v228_demo_EURUSD')
            with patch.object(learner, 'ROOT', root), patch.object(learner, 'watch', return_value=0) as watch:
                self.assertEqual(learner.main(['--source', str(old)]), 0)
                self.assertEqual(watch.call_args.args[0], old.resolve())

    def test_history_import_data_folder_uses_v224_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = self.journal(root, 'v228_demo_EURUSD')
            with patch.object(importer, 'ROOT', root), patch.object(importer, 'import_history', return_value={}) as transfer:
                with patch('sys.argv', ['import_history.py', '--model', str(root/'not-fitted.json'), '--source', str(root)]):
                    self.assertEqual(importer.main(), 0)
                self.assertEqual(transfer.call_args.args[1], target)

    def test_cmd_labels_presets_and_public_archives_match_release(self):
        for p in ROOT.glob('*.cmd'):
            self.assertNotIn('V2.22', p.read_text(), str(p))
        for p in (ROOT/'MQL4/Presets').glob('*_V228_*.set'):
            values = dict(line.split('=', 1) for line in p.read_text().splitlines() if '=' in line)
            self.assertTrue(values['InstanceTag'].startswith('v228_'), str(p))
        self.assertIn('candidate_review_v224.zip', (ROOT/'tools/candidate_research.py').read_text())

    def test_fresh_binary_preset_uses_new_journal_and_disables_forex_orders(self):
        p = ROOT/'MQL4/Presets/EURUSD_M5_V228_Binary_Fresh.set'
        v = dict(line.split('=', 1) for line in p.read_text().splitlines() if '=' in line)
        self.assertEqual(v['TradingMode'], '0')
        self.assertEqual(v['InstanceTag'], 'v228_demo')
        self.assertEqual(v['DemoExpiryMinutes'], '5')
        self.assertEqual(v['RecordReplayInputs'], 'true')
        self.assertEqual(v['ForexEnableTrading'], 'false')
        self.assertEqual(v['ForexAllowRealTrading'], 'false')
        self.assertEqual(p.read_bytes(), (ROOT/'mt4/Presets'/p.name).read_bytes())


if __name__ == '__main__':
    unittest.main()
