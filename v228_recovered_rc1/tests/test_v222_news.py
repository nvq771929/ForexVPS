"""Medium and provider-Low ZEW coverage, causal windows and auditable cache."""
import copy,csv,hashlib,io,json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from intelligence.economic_calendar import parse,state,fetch,load
from intelligence.news_policy import load_policy,selection,track
from intelligence.news_review import write as news_review
from intelligence.session_observation import publish,BRIDGE_V222_COLUMNS
from intelligence.demo_learning import POLICY_COLUMNS,csv_bytes
from intelligence.candidate_data import canonical,read
from tests.test_demo_learning import policy
from tests.test_demo_learning_native import NativeHarness
from tests.fixtures import START
from tests.test_v214_execution import read_csv


def raw_event(impact='Medium',title='EUR release',currency='EUR',when=START+200):
    return dict(title=title,country=currency,impact=impact,date=datetime.fromtimestamp(when,timezone.utc).isoformat(),forecast='30.2',previous='34.7')

def snapshot(rows=None,received=START-200):return parse(json.dumps(rows or [raw_event()]).encode(),received)


class NewsPolicyTests(unittest.TestCase):
    def test_medium_high_and_zew_low_are_selected_without_changing_provider_impact(self):
        news=snapshot([raw_event(),raw_event('High','USD release','USD'),raw_event('Low','German ZEW Economic Sentiment'),raw_event('Low','ZEW Economic Sentiment'),raw_event('Low','Other low')])
        rows=selection(news)
        self.assertEqual([r['tracked'] for r in rows],[True,True,True,True,False])
        self.assertEqual(rows[2]['provider_impact'],'Low');self.assertEqual(rows[2]['reason'],'PRIORITY_EVENT')
        self.assertEqual(len({r['event_id'] for r in rows}),5)
        self.assertEqual(state(news,START,START,START+300)['status'],'NEWS_RISK_WINDOW')

    def test_medium_window_covers_expiry_including_exact_edges(self):
        news=snapshot(received=START-1000);event=START+200
        self.assertEqual(state(news,event-901,event-901,event-601)['status'],'NEWS_CLEAR')
        self.assertEqual(state(news,event-900,event-900,event-600)['status'],'NEWS_RISK_WINDOW')
        self.assertEqual(state(news,event+900,event+900,event+1200)['status'],'NEWS_RISK_WINDOW')
        self.assertEqual(state(news,event+901,event+901,event+1201)['status'],'NEWS_CLEAR')

    def test_source_low_zew_still_warns_and_unknown_title_does_not_match_by_substring(self):
        news=snapshot([raw_event('Low','German ZEW Economic Sentiment')])
        self.assertEqual(state(news,START,START,START+300)['event']['provider_impact'],'Low')
        e=dict(news['events'][0],title='Not German ZEW Economic Sentiment revised')
        self.assertFalse(track(e,load_policy())['tracked'])
        e.update(title='German ZEW Economic Sentiment',currency='USD')
        self.assertFalse(track(e,load_policy())['tracked'])

    def test_no_relevant_or_tracked_events_is_distinct_from_clear(self):
        self.assertEqual(state(snapshot([raw_event('Low')]),START,START,START+300)['status'],'NEWS_NO_TRACKED_EVENTS')
        self.assertEqual(state(snapshot([raw_event(currency='GBP')]),START,START,START+300)['status'],'NEWS_NO_RELEVANT_EVENTS')
        self.assertEqual(state(None,START,START,START+300)['status'],'NEWS_UNKNOWN')

    def test_invalid_stale_out_of_coverage_and_uncertain_event_never_become_clear(self):
        news=snapshot()
        self.assertEqual(state(news,START+4000,START+4000,START+4300)['status'],'NEWS_STALE')
        self.assertEqual(state(news,START-201,START,START+300)['status'],'NEWS_CLOCK_UNCERTAIN')
        self.assertEqual(state(news,START,news['coverage_to_utc'],news['coverage_to_utc']+300)['status'],'NEWS_UNKNOWN')
        news['events'][0]['time_uncertain']=True
        self.assertEqual(state(news,START,START,START+300)['status'],'NEWS_TIME_UNCERTAIN')

    def test_policy_errors_and_duplicate_priority_identities_fail_closed(self):
        policy_value=load_policy();policy_value.pop('policy_sha256')
        for change in ('window','duplicate','unknown','unexpected_impact'):
            p=copy.deepcopy(policy_value)
            if change=='window':p['impacts']['Medium']['before_minutes']=-1
            elif change=='duplicate':p['priority_events'].append(p['priority_events'][0])
            elif change=='unexpected_impact':p['impacts']['Low']=dict(before_minutes=10,after_minutes=15)
            else:p['mode']='TRADE'
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'policy.json';path.write_bytes(canonical(p))
                with self.assertRaises(ValueError):load_policy(path)

    def test_fetch_preserves_raw_body_and_exclusion_decisions_and_legacy_cache_remains_readable(self):
        raw=json.dumps([raw_event('Low','German ZEW Economic Sentiment'),raw_event('Low','Other low')]).encode()
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp)/'cache';output=Path(tmp)/'out'
            result=fetch(cache,START-200,opener=lambda *a,**k:io.BytesIO(raw));self.assertEqual(result['status'],'FETCH_OK')
            report=news_review(cache,output,START)
            self.assertTrue(report['raw_available']);self.assertEqual((output/'news_raw_v222.json').read_bytes(),raw)
            self.assertEqual(report['decision_counts'],{'PRIORITY_EVENT':1,'IMPACT_OUT_OF_POLICY':1})
            self.assertEqual(report['events'][0]['impact'],'Low')
            news=load(cache);news.pop('source_event_count');news.pop('scope_event_count');news.pop('payload_sha256')
            news['payload_sha256']=hashlib.sha256(canonical(news)).hexdigest();(cache/'current.json').write_bytes(canonical(news))
            self.assertEqual(len(load(cache)['events']),2)
            (cache/('raw_'+result['raw_sha256']+'.json')).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'checksum'):news_review(cache,output,START)


class NewsNativeTests(NativeHarness,unittest.TestCase):
    def bridge(self,tmp,news):
        root=Path(tmp);journal=root/'publication';journal.mkdir();p=policy()
        (journal/'demo_policy.csv').write_bytes(csv_bytes(POLICY_COLUMNS,[p]))
        (journal/'data_origin.csv').write_bytes(csv_bytes(['schema','logic','kind','config_hash','feed_hash'],[dict(schema=1,logic=p['logic'],kind='LIVE_MT4',config_hash=p['config_hash'],feed_hash=p['feed_hash'])]))
        cache=root/'cache';cache.mkdir();(cache/'current.json').write_bytes(canonical(news))
        info=publish(journal,cache,now=START-200)
        return (journal/'context_schedule_v216.csv').read_bytes(),info

    def test_medium_and_priority_zew_alert_context_reaches_native_without_changing_signal(self):
        for event in (raw_event(),raw_event('Low','German ZEW Economic Sentiment')):
            with self.subTest(event=event),tempfile.TemporaryDirectory() as tmp:
                bridge,info=self.bridge(tmp,snapshot([event]));self.assertEqual(info['tracked_events'],1)
                result,source=self.execute(Path(tmp)/'native',context_schedule=bridge)
                self.assertEqual(result['signals'],1);self.assertEqual(result['news_alerts'],1)
                rows=[r for p in source.glob('market_context_*.csv') for r in read_csv(p)]
                lock=next(r for r in rows if r['event_kind']=='3')
                self.assertEqual(lock['news_status'],'NEWS_RISK_WINDOW')
                self.assertEqual(lock['news_event_id'],snapshot([event])['events'][0]['event_id'])
                self.assertEqual(int(lock['news_event_utc']),START+200)

    def test_unknown_and_empty_tracking_are_native_statuses_not_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            bridge,_=self.bridge(tmp,snapshot([raw_event('Low','Other low')]))
            _,source=self.execute(Path(tmp)/'native',context_schedule=bridge)
            lock=next(r for p in source.glob('market_context_*.csv') for r in read_csv(p) if r['event_kind']=='3')
            self.assertEqual(lock['news_status'],'NEWS_NO_TRACKED_EVENTS')

    def test_structured_bridge_mismatched_policy_row_never_advertises_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            bridge,_=self.bridge(tmp,snapshot());rows=list(csv.DictReader(io.StringIO(bridge.decode())))
            rows[-1]['news_policy']='f'*64
            _,source=self.execute(Path(tmp)/'native',context_schedule=csv_bytes(BRIDGE_V222_COLUMNS,rows))
            lock=next(r for p in source.glob('market_context_*.csv') for r in read_csv(p) if r['event_kind']=='3')
            self.assertEqual(lock['news_status'],'NEWS_UNKNOWN')

    def test_news_warning_is_not_repeated_after_restart_and_receipt_is_unconfirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            bridge,_=self.bridge(tmp,snapshot([raw_event('Low','German ZEW Economic Sentiment')]))
            result,source=self.execute(Path(tmp)/'native',mode=3,context_schedule=bridge)
            self.assertEqual(result['news_alerts'],1)
            paths=list(source.glob('news_alert_v222_*.csv'));self.assertEqual(len(paths),1)
            intent=read_csv(paths[0])[0];self.assertEqual(intent['delivery'],'UNCONFIRMED')
