"""Read-only isolation, causal replay, local inference and honest display tests."""
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from assistant.anchors import read_anchor
from assistant.catalog import validate_selection,default_selection,facts_for
from assistant.local_model import DEFAULT,validate_config,select,NoRedirect
from assistant.worker import Assistant,ContextStream,channel_name
from supervisor.store import Store
from intelligence.native_ledger import decode_bytes
from test_supervisor import extract,hashes

ROOT=Path(__file__).resolve().parents[1]

def synthetic(i):
    c=1.1+i*.000001
    return dict(time=i*300,open=c-.00002,high=c+.0001,low=c-.0001,close=c,ticks=10)

class AssistantReadOnlyTests(unittest.TestCase):
    def test_native_fixture_read_only_and_restart_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=extract('win',tmp);before=hashes(source);out=Path(tmp)/'assistant'
            w=Assistant(source,out,0);s=w.poll();view=copy.deepcopy(s['facts']);last=w.last
            self.assertEqual(s['progress']['closed_m5_used'],64)
            self.assertFalse(s['ea_control_enabled']);self.assertFalse(s['advisory_reply_written'])
            self.assertIsNone(s['probability_30m']);self.assertTrue(s['retrospective'])
            self.assertFalse(s['market_model_trained']);self.assertEqual(s['model_status'],'LOCAL_MODEL_NOT_CONFIGURED')
            w.close();w=Assistant(source,out,0);self.assertEqual(w.last,last)
            again=w.poll();self.assertEqual(again['new_records_this_poll'],0);self.assertEqual(again['facts'],view)
            self.assertEqual(before,hashes(source));w.close()

    def test_later_outcomes_do_not_enter_context_or_explanations(self):
        with tempfile.TemporaryDirectory() as tmp:
            seen=[]
            for name in ('win','loss'):
                root=Path(tmp)/name;root.mkdir();source=extract(name,root)
                w=Assistant(source,root/'out',0);seen.append(w.poll()['facts']);w.close()
            self.assertEqual(seen[0],seen[1])

    def test_native_tamper_rejected_on_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=extract('win',tmp);out=Path(tmp)/'out';w=Assistant(source,out,0);w.poll();w.close()
            p=source/'event_000000000001.bin';p.write_bytes(p.read_bytes()+b'altered')
            with self.assertRaisesRegex(ValueError,'bytes changed'):Assistant(source,out,0)

    def test_anchor_tamper_rejected_even_when_native_bins_are_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=extract('win',tmp);out=Path(tmp)/'out';w=Assistant(source,out,0);w.poll();w.close()
            p=next(source.glob('anchor_*.csv'));p.write_bytes(p.read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError,'bytes changed'):Assistant(source,out,0)

    def test_unknown_clock_never_assumes_utc(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=extract('win',tmp);w=Assistant(source,Path(tmp)/'out')
            s=w.poll();self.assertIsNone(s['context']);self.assertFalse(s['progress']['clock_known'])
            self.assertEqual(s['progress']['completed_h1'],0);self.assertEqual(s['health'],'COLLECTING_CLOCK_UNKNOWN');w.close()

    def test_changed_offset_requires_new_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=extract('win',tmp);out=Path(tmp)/'out';w=Assistant(source,out,0);w.close()
            with self.assertRaisesRegex(ValueError,'Immutable fact'):Assistant(source,out,60)

    def test_batch_is_bounded_and_gap_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=extract('win',tmp);w=Assistant(source,Path(tmp)/'out',0)
            s=w.poll(limit=1);self.assertEqual(s['native_records'],1);self.assertEqual(s['health'],'CATCHING_UP')
            (source/'event_000000000002.bin').unlink()
            with self.assertRaisesRegex(ValueError,'sequence gap'):w.poll()
            w.close()

    def test_no_loopback_request_when_model_not_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=extract('win',tmp);w=Assistant(source,Path(tmp)/'out',0)
            with patch('assistant.worker.select') as mock:
                w.poll();mock.assert_not_called()
            w.close()

    def test_model_failure_leaves_native_unchanged_and_no_advisory_reply(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=extract('win',tmp);before=hashes(source);config=Path(tmp)/'local.json'
            config.write_text(json.dumps(dict(DEFAULT,enabled=True,model='installed:small')))
            w=Assistant(source,Path(tmp)/'out',0,config=config)
            with patch('assistant.worker.select',side_effect=TimeoutError):s=w.poll()
            self.assertEqual(s['model_status'],'LOCAL_MODEL_UNAVAILABLE');self.assertEqual(s['local_model_error'],'TimeoutError')
            self.assertEqual(before,hashes(source));self.assertFalse(list(source.rglob('reply_*.csv')));w.close()

    def test_historical_watch_is_rejected_and_cli_lock_is_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=extract('win',tmp);before=hashes(source);out=Path(tmp)/'out'
            r=subprocess.run([sys.executable,str(ROOT/'run_ai_assistant.py'),'watch','--source',str(source),'--output',str(out)],capture_output=True)
            self.assertNotEqual(r.returncode,0);self.assertIn(b'Tester',r.stderr)
            self.assertFalse((out/'.writer-lock').exists());self.assertEqual(before,hashes(source))

    def test_nested_output_rejected_before_native_files_are_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=extract('win',tmp);before=hashes(source)
            r=subprocess.run([sys.executable,str(ROOT/'run_ai_assistant.py'),'collect','--source',str(source),'--output',str(source/'bad')],capture_output=True)
            self.assertNotEqual(r.returncode,0);self.assertFalse((source/'bad').exists());self.assertEqual(before,hashes(source))

    def test_channel_and_common_isolation(self):
        for name in ['../escape','a/b','a\\b','','é','x'*49]:
            with self.assertRaises(ValueError):channel_name(name)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=extract('win',root)
            with self.assertRaisesRegex(ValueError,'telemetry overlaps'):Assistant(source,root/'out',0,common=source/'inside')
            common=root/'common';w=Assistant(source,root/'out',0,channel='one',common=common);w.poll();w.close()
            self.assertTrue((common/'V224Assistant/one/status.csv').is_file())
            other=root/'other';other.mkdir();source2=extract('win',other)
            w2=Assistant(source2,root/'out2',0,channel='one',common=common)
            with self.assertRaisesRegex(ValueError,'another source'):w2.poll()
            w2.close()

    def test_telemetry_binds_origin_symbol_channel_and_is_display_only(self):
        import csv
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=extract('win',root);w=Assistant(source,root/'out',0,channel='unique',common=root/'common')
            w.poll();cells=next(csv.reader(io.StringIO((root/'common/V224Assistant/unique/status.csv').read_text())))
            self.assertEqual(len(cells),15);self.assertEqual(cells[2],'BACKTEST_MT4');self.assertEqual(cells[3],'EURUSD');self.assertEqual(cells[7],'unique')
            page=(root/'out/assistant_dashboard.html').read_text()
            self.assertIn('không phải dự báo live',page);self.assertIn('Chưa cấu hình mô hình ngôn ngữ',page);w.close()

    def test_native_anchor_refuses_future_bar(self):
        with tempfile.TemporaryDirectory() as tmp:
            import csv
            source=extract('win',tmp);w=Assistant(source,Path(tmp)/'out',0)
            records=[decode_bytes(p.read_bytes(),int(p.stem[6:]),compact=True) for p in sorted(source.glob('event_*.bin'))]
            record=next(r for r in records if r['event']['kind']==1)
            p=next(source.glob('anchor_*.csv'));rows=list(csv.reader(io.StringIO(p.read_text())));rows[-1][0]=rows[0][4]
            with p.open('w',newline='') as f:csv.writer(f).writerows(rows)
            with self.assertRaisesRegex(ValueError,'Future'):read_anchor(source,record,w.policy)
            w.close()

    def test_live_heartbeat_cannot_disguise_stopped_source_or_clock_ahead(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=extract('win',tmp);w=Assistant(source,Path(tmp)/'out',0);w.poll()
            w.origin='LIVE_MT4'  # Exercise live freshness with synthetic fixture clocks only.
            with patch('assistant.worker.time.time_ns',return_value=(w.last_observed+400000)*1000000):
                status=w.render()
            self.assertEqual(status['health'],'SOURCE_STALE');self.assertTrue(status['context_stale']);self.assertIsNone(status['context'])
            with patch('assistant.worker.time.time_ns',return_value=(w.last_observed-6000)*1000000):
                status=w.render()
            self.assertEqual(status['health'],'SOURCE_CLOCK_AHEAD');w.close()

    def test_local_model_selection_is_cached_only_for_identical_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=extract('win',tmp);config=Path(tmp)/'local.json'
            config.write_text(json.dumps(dict(DEFAULT,enabled=True,model='installed:small')))
            w=Assistant(source,Path(tmp)/'out',0,config=config)
            def selection(config,facts):
                return dict(fact_ids=['CAPABILITY'],question_ids=['Q_CHECK_ENTRY']),dict(model='installed:small',response_sha256='a'*64)
            with patch('assistant.worker.select',side_effect=selection) as model:
                a=w.poll();b=w.poll();self.assertEqual(model.call_count,1)
                self.assertEqual(a['local_model_evidence'],b['local_model_evidence'])
                w.view['native']['reason']=27
                c=w.render();self.assertIsNone(c['local_model_evidence']);self.assertEqual(c['model_status'],'LOCAL_MODEL_WAITING_NEW_FACTS')
                self.assertEqual(model.call_count,1)
            self.assertFalse(c['ea_control_enabled']);w.close()

class ContextPersistenceTests(unittest.TestCase):
    def test_restart_reproduces_context_without_double_counting(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);stream=ContextStream(store,0);bars=[synthetic(i) for i in range(1900)]
            snapshot=stream.feed(bars,1900*300000);store.commit();store.close()
            store=Store(tmp);stream=ContextStream(store,0);self.assertEqual(stream.snapshot,snapshot)
            self.assertEqual(stream.feed(bars[-64:],1900*300000),snapshot)
            self.assertEqual(len(store.all('ai_bar')),1900);store.close()

    def test_late_bar_is_not_inserted_into_past_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);stream=ContextStream(store,0);stream.feed([synthetic(0),synthetic(2)],900000)
            before=copy.deepcopy(stream.snapshot);stream.feed([synthetic(1)],1000000)
            self.assertEqual(stream.snapshot,before);self.assertFalse(store.get('ai_bar',300)['used']);store.close()

    def test_conflicting_overlap_fails_instead_of_rewriting_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);stream=ContextStream(store,0);stream.feed([synthetic(0)],300000)
            b=synthetic(0);b['ticks']+=1
            with self.assertRaisesRegex(ValueError,'history changed'):stream.feed([b],400000)
            store.close()

    def test_offset_is_applied_before_higher_timeframe_aggregation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);stream=ContextStream(store,60);snapshot=stream.feed([synthetic(12)],4000000)
            self.assertEqual(snapshot['asof_ms'],300000);store.close()

class LocalModelTests(unittest.TestCase):
    facts=[dict(id='ONE',text='One verified fact',evidence=dict(count=1))]

    def config(self):return dict(DEFAULT,enabled=True,model='installed:small')

    def test_remote_cloud_redirect_and_proxy_paths_are_rejected(self):
        for endpoint in ['https://api.example.com/api/chat','http://192.168.1.2:11434/api/chat','http://localhost:11434/api/chat',
                         'http://127.0.0.1:11434/api/chat?url=https://example.com','http://user:pass@127.0.0.1:11434/api/chat','http://127.0.0.1:11434/other']:
            with self.subTest(endpoint=endpoint),self.assertRaises(ValueError):validate_config(dict(self.config(),endpoint=endpoint))
        with self.assertRaises(ValueError):validate_config(dict(self.config(),model='model:cloud'))
        with self.assertRaises(ValueError):NoRedirect().redirect_request(None,None,302,'',{},'https://example.com')

    def test_invalid_configuration_cannot_silently_enable_network(self):
        for extra in [dict(enabled=1),dict(enabled=True),dict(endpoint=None),dict(timeout_seconds=120),dict(minimum_interval_seconds=1),dict(unrecognized=True)]:
            with self.subTest(extra=extra),self.assertRaises(ValueError):validate_config(dict(DEFAULT,**extra))

    def call(self,body):
        response=unittest.mock.MagicMock();response.__enter__.return_value=io.BytesIO(json.dumps(body).encode())
        opener=unittest.mock.Mock();opener.open.return_value=response
        with patch('assistant.local_model.build_opener',return_value=opener) as build:
            result=select(self.config(),self.facts)
            args=build.call_args.args
            self.assertEqual(args[0].proxies,{})
            self.assertIsInstance(args[1],NoRedirect)
            payload=json.loads(opener.open.call_args.args[0].data)
            self.assertFalse(payload['stream']);self.assertEqual(payload['options']['temperature'],0)
            return result

    def test_installed_local_model_selects_only_supported_evidence(self):
        selection=dict(fact_ids=['ONE'],question_ids=['Q_VALIDATE_CONTEXT'])
        actual,receipt=self.call(dict(done=True,model='installed:small',message=dict(content=json.dumps(selection))))
        self.assertEqual(actual,selection);self.assertEqual(len(receipt['response_sha256']),64)

    def test_free_text_probabilities_actions_and_unknown_facts_are_rejected(self):
        for choice in [dict(fact_ids=['ONE'],question_ids=['Q_CHECK_ENTRY'],action='CALL'),
                       dict(fact_ids=['ONE'],question_ids=['Q_CHECK_ENTRY'],probability=.99),
                       dict(fact_ids=['MADE_UP'],question_ids=['Q_CHECK_ENTRY']),
                       dict(fact_ids=['ONE','ONE'],question_ids=['Q_CHECK_ENTRY']),
                       dict(fact_ids=['ONE'],question_ids=['DISABLE_STOP_LOSS'])]:
            with self.subTest(choice=choice),self.assertRaises(ValueError):
                self.call(dict(done=True,model='installed:small',message=dict(content=json.dumps(choice))))

    def test_wrong_model_or_incomplete_result_is_not_displayed_as_ai_output(self):
        for body in [dict(done=False,model='installed:small'),dict(done=True,model='different:small')]:
            with self.assertRaises(ValueError):self.call(body)

    def test_oversized_result_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'size limit'):
            self.call(dict(done=True,model='installed:small',message=dict(content='x'*70000)))

if __name__=='__main__':unittest.main()
