"""Actual EA source semantics: consultation never waits or reverses a native action."""
import csv
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from tests.test_demo_learning_native import NativeHarness

ROOT=Path(__file__).resolve().parents[1]

class LearningDialogueTests(NativeHarness,unittest.TestCase):
    def first_final(self,source):
        paths=sorted((source/'advisory_v224').glob('*/final_*.csv'))
        with paths[0].open() as f:return next(csv.DictReader(f))

    def test_dialogue_off_and_enabled_without_worker_have_identical_native_journals(self):
        for mode in (34,35):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(Path(tmp)/'enabled',mode=mode)
                baseline,old=self.execute(Path(tmp)/'disabled',mode=0)
                self.assertEqual(result['signals'],baseline['signals'])
                for p in old.glob('event_*.bin'):self.assertEqual(p.read_bytes(),(source/p.name).read_bytes(),p.name)
                for p in old.glob('manual_v218_*.csv'):self.assertEqual(p.read_bytes(),(source/p.name).read_bytes(),p.name)
                self.assertGreater(result['advisor_requests'],0)

    def test_qualified_wait_before_lock_can_veto_but_keep_cannot_reverse(self):
        for direction in (1,-1):
            with self.subTest(direction=direction),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,mode=36,direction=direction)
                f=self.first_final(source)
                self.assertEqual(int(f['native_action']),direction);self.assertEqual(int(f['final_action']),0)
                self.assertEqual(f['status'],'FINAL_WAIT_BY_ADVICE')
                self.assertEqual(result['manual_total'],0)
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,mode=41)
            self.assertEqual(result['signals'],1);self.assertEqual(int(self.first_final(source)['final_action']),1)

    def test_missing_late_malformed_wrong_unqualified_changed_or_io_failure_keeps_ea_decision(self):
        for mode in (35,37,38,39,40,45,46,47,48):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(tmp,mode=mode)
                if mode==47:
                    self.assertEqual(result['manual_total'],1)
                    self.assertEqual(result['signals'],1)
                    continue
                f=self.first_final(source)
                self.assertEqual(int(f['native_action']),1)
                self.assertEqual(int(f['final_action']),1)
                self.assertEqual(result['manual_total'],1)

    def test_adviser_cannot_promote_native_wait(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,mode=42)
            self.assertEqual(result['signals'],0);self.assertEqual(int(self.first_final(source)['final_action']),0)

    def test_shadow_mode_observes_even_qualified_wait_without_changing_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(tmp,mode=49)
            f=self.first_final(source)
            self.assertEqual(f['status'],'SHADOW_EA_DECIDES')
            self.assertEqual(int(f['final_action']),1);self.assertEqual(result['manual_total'],1)

    def test_tester_collects_causal_queries_but_ignores_replies(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(Path(tmp)/'enabled',mode=44,testing=True)
            baseline,old=self.execute(Path(tmp)/'disabled',testing=True)
            self.assertGreater(result['advisor_requests'],0)
            for p in old.glob('event_*.bin'):self.assertEqual(p.read_bytes(),(source/p.name).read_bytes())
            f=self.first_final(source);self.assertEqual(f['status'],'TESTER_EA_DECIDES')
            sys.path.insert(0,str(ROOT/'LearningSupervisor'))
            from dialogue.protocol import read_request,read_final
            from dialogue.features import extract
            for p in (source/'advisory_v224').glob('*/request_*.csv'):
                request=read_request(p);feature=extract(request)
                self.assertFalse(request['snapshot']['state']['current']['locked'])
                self.assertEqual(len(feature['features']),40);self.assertEqual(len(feature['context']),50)
                self.assertLess(feature['asof_ms'],request['meta']['deadline_ms'])
            for p in (source/'advisory_v224').glob('*/final_*.csv'):read_final(p)

    def test_full_package_has_expert_include_and_explicit_off_defaults(self):
        text=(ROOT/'mt4/Experts/EURUSD_M5_Intelligence_V229.mq4').read_text()
        self.assertIn('input bool EnableBinaryLearningDialogue=false;',text)
        self.assertIn('input bool BinaryLearningAdviceAffectsSignals=false;',text)
        block=text[text.index('if(!boState.current.locked && nowMs>=BOLockDue'):text.index('if(nowMs>=(long)boState.current.targetTime')]
        self.assertLess(block.index('BOAdvisorFinalize('),block.index('BORecordCurrent(BO_LOCK_EVENT'))
        self.assertLess(block.index('BORecordCurrent(BO_LOCK_EVENT'),block.index('BOManualPublish('))
        final=(ROOT/'mt4/Include/EURUSD_M5_V224/LearningDialogue.mqh').read_text().split('void BOAdvisorFinalize(')[1].split('void BOAdvisorWriteFinal')[0]
        self.assertNotIn('FileOpen',final);self.assertNotIn('Sleep(',final)

if __name__=='__main__':unittest.main()
