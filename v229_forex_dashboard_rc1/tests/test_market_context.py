import copy,csv,hashlib,io,json,tempfile,unittest,urllib.error
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from intelligence.market_sessions import classify,windows,episode
from intelligence.economic_calendar import parse,state,fetch,load,URL
from intelligence.candidate_data import canonical,read
from intelligence.candidate_rules import summarize
from intelligence.session_observation import publish,observations
from intelligence.live_review import write
from intelligence import candidate_registry as registry
from tests.test_demo_learning_native import NativeHarness,ROOT
from tests.test_v214_execution import read_csv,write_csv,tree_hash


def ts(value):return int(datetime.fromisoformat(value.replace('Z','+00:00')).timestamp())
def raw(date='2026-10-19T08:30:00-04:00'):
    return json.dumps([dict(title='US CPI',country='USD',date=date,impact='High',forecast='2.0%',previous='1.9%')]).encode()


class SessionTests(unittest.TestCase):
    def test_timezone_database_is_available_without_os_zone_files(self):
        from zoneinfo import reset_tzpath,TZPATH
        from intelligence.market_sessions import zone,TIMEZONE_DATABASE
        try:
            reset_tzpath([]);zone.cache_clear()
            self.assertEqual(TIMEZONE_DATABASE,'tzdata-2026.4')
            self.assertIn('LONDON',classify(ts('2026-07-20T07:00:00Z'))['centres'])
        finally:reset_tzpath(TZPATH);zone.cache_clear()
    def test_dst_transitions_and_overlap_not_duplicate_opportunities(self):
        self.assertEqual(classify(ts('2026-01-19T13:30:00Z'))['session'],'LONDON_NEW_YORK')
        self.assertEqual(classify(ts('2026-07-20T12:30:00Z'))['session'],'LONDON_NEW_YORK')
        # US has moved to DST but London has not yet.
        self.assertEqual(classify(ts('2026-03-16T12:30:00Z'))['session'],'LONDON_NEW_YORK')
        self.assertEqual(classify(ts('2026-10-19T02:00:00Z'))['session'],'ASIA')
        self.assertEqual(set(classify(ts('2026-10-19T02:00:00Z'))['centres']),{'TOKYO','SYDNEY'})
        self.assertEqual(classify(None)['session'],'SESSION_UNKNOWN')
        self.assertEqual(classify(ts('2026-10-17T12:00:00Z'))['session'],'OFF_WINDOW')

    def test_windows_use_iana_dst_and_exact_end_is_exclusive(self):
        for date,start in [('2026-01-19T00:00:00Z',8),('2026-07-20T00:00:00Z',7)]:
            w=next(w for w in windows(ts(date)) if w['name']=='LONDON' and datetime.fromtimestamp(w['start'],timezone.utc).day==datetime.fromisoformat(date.replace('Z','+00:00')).day)
            self.assertEqual(datetime.fromtimestamp(w['start'],timezone.utc).hour,start)
            self.assertIn('LONDON',classify(w['start'])['centres']);self.assertNotIn('LONDON',classify(w['end'])['centres'])

    def test_horizon_crosses_session_boundary(self):
        a=ts('2026-10-19T11:59:00Z');e=ts('2026-10-19T12:00:00Z')
        info=episode(a,e-60,e+240)
        self.assertTrue(info['crosses_session_boundary'])
        self.assertIsNone(episode(None,None,None)['crosses_session_boundary'])


class CalendarTests(unittest.TestCase):
    def setUp(self):self.now=ts('2026-10-19T11:00:00Z');self.news=parse(raw(),self.now)
    def test_risk_covers_entire_expiry_and_timestamp_is_utc(self):
        event=ts('2026-10-19T12:30:00Z');self.assertEqual(self.news['events'][0]['scheduled_utc'],event)
        self.news['expires_utc']=event+3600 # state test only; not a persisted cache.
        self.assertEqual(state(self.news,event-1200,event-1200,event-900)['status'],'NEWS_RISK_WINDOW')
        self.assertEqual(state(self.news,event+901,event+901,event+1201)['status'],'NEWS_CLEAR')
        self.assertEqual(state(self.news,event+900,event+900,event+1200)['status'],'NEWS_RISK_WINDOW')

    def test_missing_stale_future_and_wrong_week_never_clear(self):
        self.assertEqual(state(None,self.now,self.now,self.now+300)['status'],'NEWS_UNKNOWN')
        self.assertEqual(state(self.news,self.now+3601,self.now+3601,self.now+3901)['status'],'NEWS_STALE')
        self.assertEqual(state(self.news,self.now-1,self.now,self.now+300)['status'],'NEWS_CLOCK_UNCERTAIN')
        self.assertEqual(state(self.news,self.now,self.news['coverage_to_utc'],self.news['coverage_to_utc']+300)['status'],'NEWS_UNKNOWN')

    def test_ambiguous_dates_empty_payload_and_duplicate_events_rejected(self):
        for payload in (b'[]',b'{}',raw('2026-10-19T08:30:00'),b'<html>blocked</html>'):
            with self.subTest(payload=payload),self.assertRaises(ValueError):parse(payload,self.now)
        rows=json.loads(raw());rows.append(rows[0])
        with self.assertRaisesRegex(ValueError,'duplicate'):parse(json.dumps(rows).encode(),self.now)
        news=parse(raw('2026-10-19T00:00:00-04:00'),self.now)
        self.assertEqual(state(news,self.now,self.now,self.now+300)['status'],'NEWS_TIME_UNCERTAIN')

    def test_http_failure_retains_last_vintage_and_redacts_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def ok(*args,**kwargs):return io.BytesIO(raw())
            first=fetch(root,self.now,ok);self.assertEqual(first['status'],'FETCH_OK');before=tree_hash(root)
            def fail(*args,**kwargs):raise urllib.error.HTTPError(URL,429,'private-token-in-error',{},None)
            result=fetch(root,self.now+900,fail)
            self.assertEqual(result['http_status'],429);self.assertNotIn('private-token',(root/'fetch_status.json').read_text())
            self.assertEqual(load(root)['received_utc'],self.now)
            self.assertEqual(len(list(root.glob('received_*.json'))),1)
            news=json.loads((root/'current.json').read_text());news['events'][0]['impact']='Low';(root/'current.json').write_text(json.dumps(news))
            with self.assertRaisesRegex(ValueError,'checksum'):load(root)

    def test_received_time_is_after_response_not_before_request(self):
        with tempfile.TemporaryDirectory() as tmp,patch('intelligence.economic_calendar.time.time',side_effect=[self.now,self.now+5]):
            fetch(Path(tmp),opener=lambda *a,**kw:io.BytesIO(raw()))
            self.assertEqual(load(tmp)['received_utc'],self.now+5)


class ContextNativeTests(NativeHarness,unittest.TestCase):
    def test_quiet_ticks_keep_session_but_expiry_clock_jump_and_offset_change_require_recalibration(self):
        for mode in (22,23): # ordinary monotonic counter and uint32 wrap
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                result,_=self.execute(Path(tmp),mode=mode)
                self.assertEqual(result['initial'],0);self.assertEqual(result['warmup'],[0,0,1])
                self.assertEqual(result['quiet'],[1,1,1,1]);self.assertEqual(result['legacy_quiet'],[0,0,0,0])
                self.assertEqual(result['expired'],1);self.assertEqual(result['recalibrated'],[0,0,1])
                self.assertEqual(result['pc_jump_unknown'],1);self.assertEqual(result['pc_recovery'],[0,0,1])
                self.assertEqual(result['offset_change'],[0,0,1]);self.assertEqual(result['tester_unknown'],1)

    def test_schema2_rejects_expired_calibration_and_schema1_remains_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,source=self.execute(Path(tmp));snapshot=read(source)
            path=next(source.glob('market_context_*.csv'));rows=read_csv(path)
            lock=next(r for r in rows if r['event_kind']=='3')
            self.assertEqual(lock['schema'],'2');lock['clock_calibration_age_ms']='900001';write_csv(path,rows)
            with self.assertRaisesRegex(ValueError,'calibration'):observations(source,snapshot)
            for row in rows:
                row['schema']='1';row.pop('clock_calibration_age_ms');row.pop('clock_calibration_ttl_ms')
            write_csv(path,rows);legacy,audit=observations(source,snapshot)
            self.assertGreater(audit['rows'],0)
            self.assertTrue(all(r['clock_schema']==1 and r['clock_calibration_age_ms'] is None for r in legacy.values()))

    def test_native_schedule_uses_captured_offset_and_news_without_affecting_decisions(self):
        from intelligence.demo_learning import csv_bytes
        from intelligence.session_observation import BRIDGE_COLUMNS
        from tests.test_demo_learning import policy
        from tests.fixtures import START
        p=policy(1);offset=7200;utc=START-offset
        base=dict(schema=1,config=p['config_hash'],feed=p['feed_hash'],policy=p['policy_hash'],horizon=1,
            created=utc-200,expires=utc+700,start=0,end=0,news_received=utc-200,news_expires=utc+3400,
            coverage_from=utc-3600,coverage_to=utc+86400,snapshot_id='fixture')
        rows=[dict(base,kind='META',label='AVAILABLE'),dict(base,kind='SESSION',start=utc-3600,end=utc+86400,label='TOKYO'),
            dict(base,kind='NEWS',start=utc+200,end=utc+2000,label='fixture USD CPI')]
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(Path(tmp),context_schedule=csv_bytes(BRIDGE_COLUMNS,rows),utc_offset=offset)
            self.assertEqual(result['signals'],1)
            lock=next(r for r in read_csv(next(source.glob('market_context_*.csv'))) if r['event_kind']=='3')
            self.assertEqual(lock['session_label'],'ASIA');self.assertEqual(lock['news_status'],'NEWS_RISK_WINDOW')
            self.assertEqual(int(lock['offset_seconds']),offset)
            unknown=[r for r in read_csv(next(source.glob('market_context_*.csv'))) if r['clock_status']=='CLOCK_UNKNOWN']
            self.assertGreater(len(unknown),0)
            self.assertTrue(all(r[k]=='-1' for r in unknown for k in ('session_mask','entry_mask','expiry_mask')))
            contexts,_=observations(source,read(source));self.assertEqual(contexts[int(lock['sequence'])]['news_status'],'NEWS_RISK_WINDOW')
            _,plain=self.execute(Path(tmp)/'without_news',utc_offset=offset)
            digest=lambda folder:hashlib.sha256(b''.join(p.read_bytes() for p in sorted(folder.glob('event_*.bin')))).hexdigest()
            self.assertEqual(digest(source),digest(plain))

    def test_missing_news_metadata_never_produces_clear(self):
        # Missing bridge is independent of the unchanged native trading decision.
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(Path(tmp));rows=read_csv(next(source.glob('market_context_*.csv')))
            self.assertEqual(result['signals'],1)
            self.assertTrue(all(r['news_status'] in ('NEWS_UNKNOWN','NEWS_CLOCK_UNCERTAIN') for r in rows))

    def test_native_clock_sidecar_is_bound_to_bin_and_tester_clock_stays_unknown(self):
        for testing in (False,True):
            with self.subTest(testing=testing),tempfile.TemporaryDirectory() as tmp:
                _,source=self.execute(Path(tmp),testing=testing);snapshot=read(source)
                observed,audit=observations(source,snapshot)
                self.assertGreater(audit['rows'],0)
                lock=next(r for r in read_csv(next(source.glob('market_context_*.csv'))) if r['event_kind']=='3')
                self.assertEqual(lock['clock_status'],'CLOCK_UNKNOWN' if testing else 'UTC_ESTIMATED_FROM_PC')
                for row in read_csv(next(source.glob('market_context_*.csv'))):
                    if row['clock_status']=='CLOCK_UNKNOWN':
                        self.assertTrue(all(row[k]=='-1' for k in ('session_mask','entry_mask','expiry_mask')))
                if testing:self.assertTrue(all(r['session']=='SESSION_UNKNOWN' for r in observed.values()))
                else:self.assertGreater(sum(r['session']!='SESSION_UNKNOWN' for r in observed.values()),0)

    def test_context_tampering_is_rejected_but_native_decisions_are_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            result,source=self.execute(Path(tmp));self.assertEqual(result['signals'],1)
            snapshot=read(source);path=next(source.glob('market_context_*.csv'));rows=read_csv(path)
            lock=next(r for r in rows if r['event_kind']=='3');lock['offset_seconds']='3600';write_csv(path,rows)
            with self.assertRaisesRegex(ValueError,'mapping'):observations(source,snapshot)

    def test_current_diagnostics_refresh_without_retraining_or_overwriting_model_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,source=self.execute(root/'native');snap=read(source);rules=summarize(source,snap)
            out=root/'review';a=registry.update(snap,out,rules);frozen=tree_hash(out/a['run'])
            first=write(source,snap,rules,out,a['run'],now_utc=100)
            second=write(source,snap,rules,out,a['run'],now_utc=200)
            self.assertEqual(second['generated_utc'],200);self.assertEqual(first['registered_candidates'],1)
            self.assertEqual(first['anchors'],1)
            self.assertEqual(sum(g['candidates'] for g in first['candidates_by_lock_session']),1)
            self.assertEqual(tree_hash(out/a['run']),frozen);self.assertFalse(second['activation_allowed'])

    def test_schedule_publication_is_live_only_and_unknown_news_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,source=self.execute(root/'live');result=publish(source,root/'missing',now=ts('2026-10-19T12:00:00Z'))
            self.assertFalse(result['news_available']);rows=read_csv(source/'context_schedule_v216.csv')
            self.assertEqual(rows[0]['label'],'NEWS_UNKNOWN');self.assertTrue(any(r['kind']=='SESSION' for r in rows))
            _,tester=self.execute(root/'tester',testing=True)
            with self.assertRaisesRegex(ValueError,'LIVE'):publish(tester,root/'missing')
