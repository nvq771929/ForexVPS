"""Visible progress and single-read integrity; all market fixtures are synthetic."""
from collections import Counter
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from intelligence.demo_learning import collect
from intelligence.history_learning import train_history,train_snapshot,dataset_digest
from intelligence.native_ledger import decode_bytes,checksum,HEADER,layouts
from intelligence.progress import ConsoleProgress,notify
from tests.test_demo_learning_native import NativeHarness
from tests.test_history_learning import historical


class ProgressConsoleTests(unittest.TestCase):
    def test_stage_eta_is_measured_and_does_not_leak_into_fit(self):
        now=[0.];stream=io.StringIO()
        p=ConsoleProgress(stream=stream,clock=lambda:now[0])
        notify(p,'read',done=0,total=1000,unit='files')
        now[0]=20;notify(p,'read',done=100,total=1000,unit='files')
        self.assertIn('10.0%',stream.getvalue())
        self.assertIn('5.0 files/s',stream.getvalue())
        self.assertIn('ETA giai doan 00:03:00',stream.getvalue())
        notify(p,'fit',detail='Train 400')
        last=stream.getvalue().splitlines()[-1]
        self.assertIn('HUAN LUYEN',last);self.assertIn('chua uoc luong',last)
        self.assertNotIn('%',last);self.assertNotIn('files/s',last)
        p.close('FINISHED')

    def test_heartbeat_and_log_continue_without_more_work_callbacks(self):
        ready=threading.Event()
        class Sink(io.StringIO):
            def write(self,text):
                result=super().write(text)
                if self.getvalue().count('\n')>=3:ready.set()
                return result
        with tempfile.TemporaryDirectory() as tmp:
            stream=Sink();log=Path(tmp)/'progress.log'
            with ConsoleProgress(stream=stream,log_path=log,interval=.1) as p:
                notify(p,'fit',detail='Busy fitting')
                self.assertTrue(ready.wait(2),'No heartbeat during a busy stage')
            text=log.read_text();self.assertIn('Busy fitting',text);self.assertIn('[FINISHED]',text)
            self.assertTrue(p.stop.is_set());self.assertFalse(p.thread.is_alive())

    def test_failure_and_cancel_have_honest_terminal_status(self):
        for error,status in ((ValueError('bad data'),'FAILED'),(KeyboardInterrupt(),'CANCELED')):
            with self.subTest(status=status),tempfile.TemporaryDirectory() as tmp:
                stream=io.StringIO();log=Path(tmp)/'p.log'
                with self.assertRaises(type(error)):
                    with ConsoleProgress(stream=stream,log_path=log,interval=.1) as p:
                        notify(p,'read',done=0,total=100,unit='files');raise error
                self.assertIn(f'[{status}]',log.read_text())
                self.assertNotIn('[FINISHED]',stream.getvalue());self.assertNotIn('100.0%',stream.getvalue())

    def test_progress_does_not_change_fitted_weights_calibration_or_gates(self):
        data=historical();events=[]
        baseline,report=train_snapshot(data,'c'*64)
        observed,report2=train_snapshot(data,'c'*64,progress=events.append)
        self.assertEqual(baseline,observed);self.assertEqual(report,report2)
        self.assertEqual([e['stage'] for e in events if 'done' not in e],['fit','calibrate','evaluate'])
        self.assertEqual([e['done'] for e in events if e['stage']=='holdouts'],[0,1,2,3])


class ProgressNativeTests(NativeHarness,unittest.TestCase):
    def test_public_cli_reports_progress_and_writes_logs_outside_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);_,source=self.execute(tmp/'data with spaces',testing=True)
            before={p.name:p.read_bytes() for p in source.iterdir()}
            script=Path(__file__).resolve().parents[1]/'tools/train_history.py'
            log=tmp/'logs/progress.log';output=tmp/'trained model'
            proc=subprocess.run([sys.executable,str(script),'--source',str(source),
                '--output',str(output),'--progress-log',str(log),'--progress-interval','.1'],
                text=True,capture_output=True,timeout=60)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertIn('[2/8 DOC + KIEM TRA]',proc.stdout)
            self.assertIn('[FINISHED]',proc.stdout);self.assertIn('NOT_QUALIFIED',proc.stdout)
            self.assertEqual(json.loads((output/'history_report.json').read_text())['processing']['event_read_passes'],1)
            self.assertFalse((output/'history_model.json').exists())
            self.assertIn('[FINISHED]',log.read_text())
            self.assertEqual(before,{p.name:p.read_bytes() for p in source.iterdir()})
            # Failure is visible both in the console and in the durable log.
            (source/'tester_complete.csv').unlink();failed=tmp/'failed.log'
            proc=subprocess.run([sys.executable,str(script),'--source',str(source),
                '--output',str(tmp/'not-created'),'--progress-log',str(failed)],
                text=True,capture_output=True,timeout=60)
            self.assertEqual(proc.returncode,1);self.assertIn('[FAILED]',failed.read_text())
            self.assertIn('FileNotFoundError',failed.read_text());self.assertIn('BLOCKED',proc.stderr)

    def test_each_event_is_read_once_digest_and_labels_match_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(tmp,testing=True)
            self.assertEqual(collect(source,compact=False),collect(source,compact=True))
            expected=dataset_digest(source);counts=Counter();events=[]
            original=Path.read_bytes
            def read(path):
                if path.name.startswith('event_'):counts[path.name]+=1
                return original(path)
            with patch.object(Path,'read_bytes',read):
                report=train_history(source,Path(tmp)/'output',progress=events.append)
            self.assertEqual(report['dataset_sha256'],expected)
            self.assertEqual(set(counts.values()),{1})
            self.assertEqual(len(counts),report['native_records'])
            reads=[e for e in events if e['stage']=='read']
            self.assertEqual(reads[0]['done'],0)
            self.assertEqual(reads[-1]['done'],len(counts))
            self.assertEqual(report['processing']['event_read_passes'],1)
            self.assertEqual(events[-1]['stage'],'export');self.assertEqual(events[-1]['done'],1)

    def test_compact_decode_still_rejects_pending_byte_corruption_and_bad_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(tmp,testing=True)
            blob=(source/'event_000000000001.bin').read_bytes()
            bad=bytearray(blob);bad[HEADER.size+layouts()['BORuntimeState'].pending.offset+1]^=1
            for compact in (False,True):
                with self.subTest(compact=compact):
                    with self.assertRaisesRegex(ValueError,'checksum'):decode_bytes(bytes(bad),compact=compact)
                    with self.assertRaisesRegex(ValueError,'sequence'):decode_bytes(blob,expected_sequence=2,compact=compact)
            bad=bytearray(blob)
            event_offset=HEADER.size+struct.unpack_from('<i',blob,12)[0]
            struct.pack_into('<i',bad,event_offset,99)
            struct.pack_into('<I',bad,len(bad)-4,checksum(bad[:-4]))
            with self.assertRaisesRegex(ValueError,'kind/reason'):decode_bytes(bytes(bad),compact=True)

    def test_changed_metadata_or_file_list_cannot_export_a_candidate(self):
        for mode in ('metadata','files'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                _,source=self.execute(tmp,testing=True);output=Path(tmp)/'output'
                def progress(e):
                    if e['stage']=='read' and e.get('done')==e.get('total'):
                        if mode=='metadata':
                            p=source/'tester_complete.csv';p.write_bytes(p.read_bytes()+b'\n')
                        else:(source/'event_999999999999.bin').write_bytes(b'bad')
                with self.assertRaisesRegex(ValueError,'changed'):
                    train_history(source,output,progress=progress)
                self.assertFalse((output/'history_model_candidate.json').exists())

    def test_missing_seal_fails_before_reading_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(tmp,testing=True);(source/'tester_complete.csv').unlink()
            original=Path.read_bytes
            def read(path):
                self.assertFalse(path.name.startswith('event_'));return original(path)
            with patch.object(Path,'read_bytes',read),self.assertRaises(OSError):
                train_history(source,Path(tmp)/'output')
