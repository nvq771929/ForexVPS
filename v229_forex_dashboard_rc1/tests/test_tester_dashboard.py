"""Run real native adapter; dashboard totals must match decoded Tester labels."""
import tempfile
import unittest

from intelligence.demo_learning import collect
from tests.test_demo_learning_native import NativeHarness


class TesterDashboardTests(NativeHarness,unittest.TestCase):
    def test_local_tester_results_match_python_for_directions_and_expiries(self):
        for direction in (1,-1):
            for horizon in (1,2,3):
                for mode,status in ((0,'WIN'),(13,'LOSS'),(14,'TIE'),(4,'UNAVAILABLE')):
                    with self.subTest(direction=direction,horizon=horizon,status=status),tempfile.TemporaryDirectory() as tmp:
                        native,source=self.execute(tmp,mode=mode,direction=direction,horizon=horizon,testing=True)
                        papers=collect(source)['papers']
                        self.assertEqual(len(papers),1)
                        self.assertEqual(papers[0]['status'],status)
                        self.assertEqual(native['dash_signals'],1)
                        self.assertEqual(native['dash_open'],0)
                        for key,label in (('dash_wins','WIN'),('dash_losses','LOSS'),('dash_ties','TIE'),('dash_missing','UNAVAILABLE')):
                            self.assertEqual(native[key],int(label==status))
                        self.assertTrue(native['tester_time'])
                        self.assertTrue(native['tester_training_help'])
                        self.assertFalse(native['live_learning_help'])

    def test_wait_or_canceled_reference_is_not_a_signal_result(self):
        for mode in (1,2,5,6,17):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                native,source=self.execute(tmp,mode=mode,testing=True)
                self.assertFalse(any(p['simulated_entry'] for p in collect(source)['papers']))
                self.assertEqual(native['dash_signals'],0)
                self.assertEqual(sum(native[k] for k in ('dash_open','dash_wins','dash_losses','dash_ties','dash_missing')),0)

    def test_missing_history_keeps_clock_ticks_running_and_recovery_resumes_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            native,_=self.execute(tmp,mode=7,testing=True)
            self.assertEqual(native['history_status'],'THIEU_NEN_TRONG_LICH_SU')
            self.assertGreater(native['tester_ticks'],500)
            self.assertEqual(native['tester_anchors'],0)
            self.assertEqual(native['signals'],0)
        with tempfile.TemporaryDirectory() as tmp:
            native,_=self.execute(tmp,mode=8,testing=True)
            self.assertEqual(native['history_status'],'SAN_SANG')
            self.assertGreater(native['tester_anchors'],0)
            self.assertTrue(native['tester_time'])

    def test_live_dashboard_keeps_python_statistics_and_live_instructions(self):
        with tempfile.TemporaryDirectory() as tmp:
            native,_=self.execute(tmp)
            self.assertEqual(native['tester_ticks'],0)
            self.assertEqual(native['dash_signals'],0)
            self.assertFalse(native['tester_time'])
            self.assertFalse(native['tester_training_help'])
            self.assertTrue(native['live_learning_help'])
