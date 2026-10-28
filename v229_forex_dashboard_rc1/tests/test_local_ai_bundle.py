"""Complete-bundle and execution-isolation contracts for local AI RC3."""
import hashlib
import json
from pathlib import Path
import unittest
from tools.package_release import content, NAME

ROOT=Path(__file__).resolve().parents[1]

class LocalAIBundleTests(unittest.TestCase):
    def test_full_candidate_keeps_all_native_expert_include_and_forex_sources(self):
        baseline=json.loads((ROOT/'baseline_v224_rc2_sha256.json').read_text())
        paths=[name for name in baseline if name.startswith('mt4/Include/')]
        self.assertGreater(len(paths),20)
        for name in paths:
            with self.subTest(name=name):self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),baseline[name])

    def test_local_assistant_is_in_full_package_with_both_install_trees(self):
        items=content()
        for name in ['MQL4/Experts/EURUSD_M5_Intelligence_V229.mq4','MQL4/Indicators/BinaryLearningMonitor_V224.mq4',
                     'LearningSupervisor/run_ai_assistant.py','LearningSupervisor/assistant/worker.py',
                     'LearningSupervisor/assistant/local_model.py','LearningSupervisor/assistant/context/engine.py',
                     'Install-Local-AI-Assistant.cmd','Start-Local-AI-Assistant.cmd','LOCAL_AI_V224_VI.md']:
            self.assertIn(name,items)
        self.assertIn('V229_Full_RC1',NAME)

    def test_frozen_context_source_is_exact_and_language_model_defaults_off(self):
        p=ROOT/'LearningSupervisor/assistant/context'
        receipt=json.loads((p/'candidate_freeze.json').read_text())
        self.assertEqual(hashlib.sha256((p/'engine.py').read_bytes()).hexdigest(),receipt['files_sha256']['engine.py'])
        config=json.loads((ROOT/'LearningSupervisor/local_ai.example.json').read_text())
        self.assertFalse(config['enabled']);self.assertEqual(config['model'],'')
        v=json.loads((ROOT/'VERSION.json').read_text())
        self.assertTrue(v['local_ai_assistant_included']);self.assertFalse(v['local_ai_changes_signals']);self.assertFalse(v['local_ai_30m_prediction_model'])

    def test_new_indicator_only_reads_source_bound_telemetry(self):
        p=ROOT/'mt4/Indicators/BinaryLearningMonitor_V224.mq4';text=p.read_text()
        self.assertEqual(p.read_bytes(),(ROOT/'LearningSupervisor/MQL4/Indicators'/p.name).read_bytes())
        self.assertIn('cells[3]!=Symbol()',text);self.assertIn('cells[7]!=AIAssistantChannel',text)
        self.assertIn('SOURCE_STALE',text);self.assertIn('BACKTEST_MT4',text)
        for forbidden in ['OrderSend(','OrderClose(','WebRequest(','FILE_WRITE']:
            self.assertNotIn(forbidden,text)

    def test_assistant_does_not_acquire_a_native_or_dialogue_write_interface(self):
        p=ROOT/'LearningSupervisor/assistant'
        text='\n'.join(x.read_text() for x in p.glob('*.py'))
        for forbidden in ['f"reply_','BOAdvisor','row_bytes(','from dialogue.worker','from dialogue.training','from supervisor.learning','OrderSend']:
            self.assertNotIn(forbidden,text)
        self.assertIn('probability_30m=None',text)

if __name__=='__main__':unittest.main()
