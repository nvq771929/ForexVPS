"""Accept actual MT4/live-Forex folders without redirecting Binary or historical data."""
from contextlib import redirect_stdout,redirect_stderr
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import forex_news as cli
from intelligence.candidate_data import canonical
from intelligence.economic_calendar import parse
from intelligence.forex_news import fnv

NOW=1767225600


class ForexNewsPathTests(unittest.TestCase):
    def layout(self,base):
        root=Path(base)/'Terminal with spaces'/'50CA3DFB510CC5A8F28B48D1BF2A5702'
        files=root/'MQL4'/'Files';live=files/'FX_V222'/'LIVE_70706065_2973903039'
        live.mkdir(parents=True);(live/'forex_session.csv').write_text('existing Forex session\n')
        return root,files,live

    def test_data_folder_mql4_files_forex_root_and_live_folder_resolve_to_same_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,files,live=self.layout(tmp)
            for choice in [root,root/'MQL4',files,files/'FX_V222',live]:
                with self.subTest(choice=choice):self.assertEqual(cli.resolve_files_directory(choice),files)

    def test_invalid_unrelated_binary_tester_and_missing_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,files,live=self.layout(tmp)
            binary=files/'BO_V2'/'v229_binary_demo_utc0_EURUSDz';binary.mkdir(parents=True)
            tester=files/'FX_V222'/'v229_TESTER_EURUSDz';tester.mkdir()
            outside=Path(tmp)/'FX_V222';outside.mkdir()
            for choice in [Path(tmp),root/'MQL4'/'Experts',binary,tester,outside,live/'forex_session.csv']:
                with self.subTest(choice=choice),self.assertRaises(ValueError):cli.resolve_files_directory(choice)

    def test_arbitrary_live_named_directory_without_a_forex_session_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,files,_=self.layout(tmp);missing=files/'FX_V222'/'LIVE_unknown';missing.mkdir()
            with self.assertRaises(ValueError):cli.resolve_files_directory(missing)

    def run_once(self,choice,fetcher):
        output=io.StringIO()
        with patch('sys.argv',['forex_news.py','--data-folder',str(choice),'--once']),patch.object(cli,'fetch',side_effect=fetcher),patch.object(cli.time,'time',return_value=NOW),redirect_stdout(output):
            self.assertEqual(cli.main(),0)
        return output.getvalue()

    def calendar(self,cache):
        raw=json.dumps([dict(title='CPI',country='USD',impact='High',date='2026-01-01T08:30:00-05:00')]).encode()
        cache.mkdir(parents=True,exist_ok=True)
        (cache/'current.json').write_bytes(canonical(parse(raw,NOW)))
        return dict(status='FETCH_OK')

    def test_user_live_folder_input_writes_verified_shared_forex_bridge_and_preserves_journals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,files,live=self.layout(tmp)
            binary=files/'BO_V2'/'v229_binary_demo_utc0_EURUSDz';binary.mkdir(parents=True)
            sentinel=binary/'context_schedule_v216.csv';sentinel.write_bytes(b'Binary remains independent\n')
            before={p.relative_to(live):p.read_bytes() for p in live.iterdir() if p.is_file()}
            output=self.run_once(live,self.calendar)
            bridge=files/'FX_V222'/'news_calendar.csv'
            self.assertIn(str(root),output);self.assertIn(str(bridge),output)
            self.assertTrue(bridge.is_file());self.assertFalse((live/'news_calendar.csv').exists())
            self.assertEqual(before,{p.relative_to(live):p.read_bytes() for p in live.iterdir() if p.is_file()})
            self.assertEqual(sentinel.read_bytes(),b'Binary remains independent\n')
            with bridge.open() as stream:rows=list(csv.reader(stream))
            self.assertEqual(rows[1][0],'V222_FOREX_NEWS_V1')
            for row in rows[1:]:self.assertEqual(int(row[-1]),fnv('|'.join(row[:-1])))

    def test_data_folder_and_live_folder_write_identical_bridge_bytes(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            root,files,_=self.layout(a);_,other,live=self.layout(b)
            self.run_once(root,self.calendar);self.run_once(live,self.calendar)
            self.assertEqual((files/'FX_V222/news_calendar.csv').read_bytes(),(other/'FX_V222/news_calendar.csv').read_bytes())

    def test_quoted_interactive_live_path_with_spaces_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,files,live=self.layout(tmp);output=io.StringIO()
            with patch('sys.argv',['forex_news.py','--once']),patch('builtins.input',return_value='"'+str(live)+'"'),patch.object(cli,'fetch',side_effect=self.calendar),patch.object(cli.time,'time',return_value=NOW),redirect_stdout(output):
                self.assertEqual(cli.main(),0)
            self.assertTrue((files/'FX_V222/news_calendar.csv').is_file())

    def test_invalid_choice_stops_before_network_or_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=io.StringIO()
            with patch('sys.argv',['forex_news.py','--data-folder',tmp,'--once']),patch.object(cli,'fetch') as fetch,redirect_stderr(output):
                with self.assertRaises(SystemExit) as error:cli.main()
                self.assertEqual(error.exception.code,2);fetch.assert_not_called()
            self.assertEqual(list(Path(tmp).iterdir()),[])


if __name__=='__main__':unittest.main()
