import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from intelligence.candidate_data import canonical
from intelligence.economic_calendar import parse,load
from intelligence.forex_news import publish,fnv,COLUMNS

NOW=1767225600

class ForexNewsTests(unittest.TestCase):
    def make_cache(self,folder,events=None):
        raw=json.dumps(events or [dict(title='CPI',country='USD',impact='High',date='2026-01-01T08:30:00-05:00'),
            dict(title='German ZEW Economic Sentiment',country='EUR',impact='Low',date='2026-01-01T09:00:00-05:00'),
            dict(title='Other low news',country='EUR',impact='Low',date='2026-01-01T10:00:00-05:00'),
            dict(title='GBP CPI',country='GBP',impact='High',date='2026-01-01T11:00:00-05:00')]).encode()
        cache=Path(folder)/'cache';cache.mkdir();snapshot=parse(raw,NOW)
        (cache/'current.json').write_bytes(canonical(snapshot));return cache,snapshot

    def test_forex_publication_preserves_impact_priority_and_source_times(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache,snapshot=self.make_cache(tmp);root=Path(tmp)/'files'
            result=publish(cache,root,NOW);rows=list(csv.reader(io.StringIO(Path(result['path']).read_text())))
            self.assertEqual(rows[0],list(COLUMNS));self.assertEqual(len(rows),4)
            for row in rows[1:]:self.assertEqual(int(row[-1]),fnv('|'.join(row[:-1])))
            self.assertEqual(rows[2][10],'High');self.assertEqual(rows[3][10],'Low');self.assertEqual(rows[3][11],'PRIORITY_EVENT')
            self.assertEqual(int(rows[1][2]),NOW);self.assertEqual(rows[1][6],snapshot['payload_sha256'])
            self.assertEqual(rows[1][14],'2');self.assertFalse((root/'BO_V2').exists())

    def test_publishing_cached_calendar_does_not_renew_its_freshness(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache,snapshot=self.make_cache(tmp);root=Path(tmp)/'files'
            publish(cache,root,NOW);first=(root/'FX_V222/news_calendar.csv').read_bytes()
            result=publish(cache,root,NOW+3601)
            self.assertEqual(result['status'],'STALE');self.assertEqual(first,Path(result['path']).read_bytes())
            self.assertEqual(load(cache)['received_utc'],NOW)

    def test_tampered_snapshot_never_replaces_a_valid_bridge(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache,snapshot=self.make_cache(tmp);root=Path(tmp)/'files';result=publish(cache,root,NOW)
            bridge=Path(result['path']);first=bridge.read_bytes();snapshot['events'][0]['impact']='Low'
            (cache/'current.json').write_bytes(canonical(snapshot))
            with self.assertRaisesRegex(ValueError,'checksum'):publish(cache,root,NOW)
            self.assertEqual(bridge.read_bytes(),first)

    def test_no_relevant_events_has_explicit_zero_count_and_valid_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache,snapshot=self.make_cache(tmp,[dict(title='GBP CPI',country='GBP',impact='High',date='2026-01-01T11:00:00-05:00')])
            result=publish(cache,Path(tmp)/'files',NOW)
            with Path(result['path']).open() as stream:rows=list(csv.reader(stream))
            self.assertEqual(len(rows),2);self.assertEqual(rows[1][14],'0');self.assertEqual(rows[1][12],'READY')

if __name__=='__main__':unittest.main()
