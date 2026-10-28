import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from intelligence.execution_review import broker_seconds, observers, write
from intelligence.execution_journals import diagnose, input_quality
from tests.test_demo_learning_native import NativeHarness, ROOT


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def read_csv(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def tree_hash(source):
    return {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in source.rglob('*') if p.is_file()}


class WindowsObserverTests(unittest.TestCase):
    def test_mixed_canceled_and_surviving_rows_export_consistent_csv_columns(self):
        original=json.loads((ROOT/'tests/fixtures/windows_observer_v213.json').read_text())['rows']
        cancel=original[1];start=broker_seconds(cancel['analysis_start'])
        trace=dict(analysis_start=start,target_time=start+300,setup=1,published_at_lock=True,
            first_cancel_observed_ms=int(cancel['observed_ms']),cancel_quote_age_ms=int(cancel['stored_quote_age_ms']),
            lock_observed_ms=int(original[0]['observed_ms']),cancel_after_lock=True,first_cancel_reason='QUOTE_GAP',
            cancel_last_quote_ms=int(cancel['stored_quote_ms']),entry_reason='QUOTE_GAP',execution_signal_observed=False)
        second=dict(trace,analysis_start=start+600,target_time=start+900,first_cancel_observed_ms=None,
            cancel_quote_age_ms=None,first_cancel_reason=None,cancel_last_quote_ms=None,entry_reason='OK',
            cancel_after_lock=False,execution_signal_observed=True)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'observer';folder.mkdir()
            write_csv(folder/'execution_diagnostics_windows.csv',original)
            report=write(dict(origin='BACKTEST_MT4',execution_traces=[trace,second]),'a'*64,root/'out',folder)
            rows=read_csv(root/'out/execution_review.csv')
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[1]['latest_tick_ms'],'')
            self.assertEqual(report['native_summary']['execution_entries'],1)

    def test_replay_cancellation_is_matched_to_incoming_price_and_previous_tick_gap(self):
        rows=[]
        for seq,now in [(1,1767619796000),(2,1767619800000)]:
            rows.append(dict(schema=2,logic_version=2026101707,session='s',sequence=seq,event_type='TICK',
                time_ms_estimated=now,server_time_seconds=now//1000,bid='1.16813',ask='1.16813',shadow_mode=1))
        cancel=dict(observer_matched=True,event_trigger='TICK',first_cancel_observed_ms=1767619800000,
            analysis_start=1767619500,latest_bid='1.16813',latest_ask='1.16813',inter_tick_gap_ms=4000)
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);path=folder/'input_20260105.csv';write_csv(path,rows)
            quality=input_quality(folder,'BACKTEST_MT4',cancellations=[cancel])
            self.assertEqual(quality['incoming_cancellations_matched_to_input'],1)
            self.assertTrue(quality['all_ticks_zero_spread'])
            cancel['inter_tick_gap_ms']=5000
            with self.assertRaisesRegex(ValueError,'replay tick price/gap'):
                input_quality(folder,'BACKTEST_MT4',cancellations=[cancel])

    def test_native_decision_blocks_match_verified_v218_with_explicit_collection_changes(self):
        audit=json.loads((ROOT/'docs/native-preservation-v222.json').read_text())
        changed=[]
        normalize=lambda text:text.replace('V222','V218').replace('v222','v218').replace('V2.24','V2.18')
        for row in audit['includes']:
            path=ROOT/'mt4/Include/EURUSD_M5_V224'/row['file']
            if row['unchanged_after_namespace_normalization']:
                self.assertEqual(hashlib.sha256(normalize(path.read_text()).encode()).hexdigest(),row['baseline_sha256'],row['file'])
            else:changed.append(row['file'])
        self.assertEqual(changed,['MarketContext.mqh','UI.mqh'])
        adapter=normalize((ROOT/'mt4/Experts/EURUSD_M5_Intelligence_V228.mq4').read_text())
        boundary=adapter[adapter.index('void BOProcess('):adapter.index('   if(tick) BOAttemptAnchor(')]
        # V224's only decision extension is the explicitly optional cached pre-lock veto.
        self.assertEqual(boundary.count('BOAdvisorFinalize('),1)
        boundary=boundary.replace('         BOAdvisorFinalize(boState.current,boConfig,nowMs);\n','')
        self.assertEqual(hashlib.sha256(boundary.encode()).hexdigest(),audit['boundary_processing_sha256'])
        self.assertEqual(audit['manual_contract'],'V218_MANUAL_PUBLICATION_V1')

    def test_strict_broker_coordinate_parser_supports_old_and_numeric_windows_data(self):
        self.assertEqual(broker_seconds('2026.01.05 13:25:00'), 1767619500)
        self.assertEqual(broker_seconds('1767619500'), 1767619500)
        for value in ('2026.02.30 13:25:00', '2026.1.5 13:25:00', '2026.01.05 13:25:00Z',
                      '2026.01.05 13:25:00+07:00', '1.5', '-1', '0', '253402300800'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                broker_seconds(value)

    def test_actual_windows_v213_observer_rows_parse_without_rewriting_source(self):
        rows = json.loads((ROOT/'tests/fixtures/windows_observer_v213.json').read_text())['rows']
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp); path = source/'execution_diagnostics_windows.csv'
            write_csv(path, rows); before = path.read_bytes()
            result, files = observers(source)
            self.assertEqual(len(result), 2)
            self.assertEqual(sorted(r['inter_tick_gap_ms'] for r in result.values()), [4000, 12000])
            self.assertTrue(all(r['latest_tick_age_ms'] == 0 for r in result.values()))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(files[0]['native_rows_verified'], 0)

    def test_invalid_clock_is_rejected_on_non_cancellation_rows_too(self):
        rows = json.loads((ROOT/'tests/fixtures/windows_observer_v213.json').read_text())['rows']
        rows[0]['latest_tick_ms'] = str(int(rows[0]['observed_ms'])+1)
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp);write_csv(source/'execution_diagnostics_windows.csv', rows)
            with self.assertRaisesRegex(ValueError, 'future tick'):
                observers(source)


class RawExecutionTests(NativeHarness, unittest.TestCase):
    def test_raw_sealed_diagnosis_without_training_and_cli_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); result, source=self.execute(root/'native',mode=9,testing=True)
            before=tree_hash(source)
            report=diagnose(source,root/'report')
            self.assertEqual(report['classifications'], {'FRESH_INCOMING_TICK_AFTER_OBSERVATION_GAP':1})
            self.assertTrue(report['completion_marker_verified'])
            self.assertTrue(report['observer_sequence_verified'])
            self.assertGreater(report['observer_native_rows_verified'],0)
            self.assertFalse(report['model_trained']);self.assertEqual(report['guard_seconds'],3)
            self.assertEqual(result['signals'],0)
            self.assertEqual(tree_hash(source),before)
            proc=subprocess.run([sys.executable,str(ROOT/'tools/diagnose_execution.py'),'--source',str(source),
                '--output',str(root/'cli')],capture_output=True,text=True,timeout=60)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertTrue((root/'cli/execution_review_v224.zip').is_file())
            self.assertFalse(list((root/'cli').glob('*model*')))
            self.assertEqual(tree_hash(source),before)

    def test_stable_live_snapshot_stays_distinct_from_tester(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,source=self.execute(root/'native',mode=9,testing=False)
            before=tree_hash(source);report=diagnose(source,root/'report')
            self.assertEqual(report['source'],'LIVE_MT4')
            self.assertFalse(report['completion_marker_verified'])
            self.assertEqual(report['source_snapshot'],'STABLE_LOCAL_LIVE_JOURNAL')
            self.assertFalse(report['network_latency_proven'])
            self.assertEqual(tree_hash(source),before)

    def test_native_schema3_numeric_identity_and_unchanged_guard(self):
        for mode,signals in ((0,1),(9,0),(18,1)):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                result,source=self.execute(Path(tmp),mode=mode,testing=True)
                self.assertEqual(result['signals'],signals)
                rows=read_csv(next(source.glob('execution_diagnostics_*.csv')))
                self.assertTrue(all(r['schema']=='3' and r['analysis_start'].isdigit() for r in rows))
                self.assertTrue(all(r['quote_fresh_seconds']=='3' for r in rows))
                if mode==9:
                    cancel=next(r for r in rows if r['event_kind']=='4' and r['reason']=='QUOTE_GAP')
                    self.assertEqual(cancel['gap_class'],'INCOMING_TICK_AFTER_OBSERVATION_GAP')
                    self.assertEqual(cancel['latest_tick_age_ms'],'0')
                    self.assertEqual(cancel['stored_quote_age_ms'],'4000')

    def test_tampered_native_record_or_observer_sequence_blocks_diagnosis(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,source=self.execute(root/'native',mode=9,testing=True)
            observer=next(source.glob('execution_diagnostics_*.csv')); original=observer.read_bytes()
            rows=read_csv(observer);rows[0]['sequence']='999999'
            write_csv(observer,rows)
            with self.assertRaisesRegex(ValueError,'sequence'):
                diagnose(source,root/'bad_observer')
            observer.write_bytes(original)
            path=next(source.glob('event_*.bin'));content=bytearray(path.read_bytes());content[-1]^=1;path.write_bytes(content)
            with self.assertRaisesRegex(ValueError,'checksum'):
                diagnose(source,root/'bad_native')

    def test_unsealed_tester_and_mixed_observer_origin_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,source=self.execute(root/'native',mode=9,testing=True)
            marker=source/'tester_complete.csv';original=marker.read_bytes();marker.unlink()
            with self.assertRaises(OSError):diagnose(source,root/'unsealed')
            marker.write_bytes(original)
            observer=next(source.glob('execution_diagnostics_*.csv'))
            observer.write_text(observer.read_text().replace('BACKTEST_MT4','LIVE_MT4'))
            with self.assertRaisesRegex(ValueError,'origin'):diagnose(source,root/'mixed')
