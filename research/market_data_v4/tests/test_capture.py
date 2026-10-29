from pathlib import Path
import csv
import shutil
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import validate as v

def save(path,rows,header):
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=header);writer.writeheader();writer.writerows(rows)

class CaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.base=Path(cls.temp.name)
        source=(ROOT/'mt4/EURUSD_Research_Recorder_V1.mq4').read_text()
        (cls.base/'recorder_under_test.hpp').write_text('\n'.join(s for s in source.splitlines() if not s.startswith('#property')))
        probe=cls.base/'collector_probe'
        subprocess.run(['g++','-std=c++17','-O2','-I',str(cls.base),str(ROOT/'tests/collector_probe.cpp'),'-o',str(probe)],check=True,capture_output=True)
        cls.fixture=cls.base/'synthetic_fixture';subprocess.run([str(probe),str(cls.fixture)],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):
        self.work=Path(tempfile.mkdtemp(dir=self.base));shutil.copytree(self.fixture,self.work,dirs_exist_ok=True)
    def edit(self,name,change):
        p=self.work/(name+'.csv');data=v.rows(p,name);change(data);save(p,data,v.FIELDS[name].split(','))
    def test_real_collector_source_contains_no_trade_apis(self):
        import re
        source=(ROOT/'mt4/EURUSD_Research_Recorder_V1.mq4').read_text()
        self.assertIsNone(re.search(r'\b(OrderSend|OrderModify|OrderClose|OrderCloseBy|OrderDelete|WebRequest|ShellExecute|WinExec)\s*\(',source))
        self.assertNotIn('#import',source)
    def test_generated_synthetic_capture_validates(self):
        r=v.capture(self.work);self.assertTrue(r['sealed_local_files']);self.assertEqual(r['status'],'LOCAL_FILES_CONSISTENT');self.assertEqual(r['tick_callbacks_written'],2);self.assertEqual(r['heartbeat_rows'],1)
    def test_volume_and_signed_commission_conversion(self):
        r=v.capture(self.work);self.assertAlmostEqual(r['recorded_commission_cost_USD_per_lot_median'],7);self.assertAlmostEqual(r['recorded_commission_cost_pips_median'],.7)
    def test_no_closed_orders_means_unknown_fee(self):
        self.edit('closed_orders',lambda r:r.clear());self.edit('session',lambda r:r[-1].update(order_rows='0'))
        self.assertIsNone(v.capture(self.work)['recorded_commission_cost_pips_median'])
    def test_sequence_gap_rejected(self):
        self.edit('ticks',lambda r:r[-1].update(sequence='3'))
        with self.assertRaises(ValueError):v.capture(self.work)
    def test_heartbeat_does_not_become_tick(self):
        self.edit('heartbeats',lambda r:r.append(dict(r[0],sequence='2',mono_elapsed_ms='1300')));self.edit('session',lambda r:r[-1].update(heartbeat_rows='2'))
        self.assertEqual(v.capture(self.work)['tick_callbacks_written'],2)
    def test_footer_mismatch_rejected(self):
        self.edit('session',lambda r:r[-1].update(tick_rows='99'))
        with self.assertRaises(ValueError):v.capture(self.work)
    def test_active_capture_not_sealed(self):
        self.edit('session',lambda r:r.pop());self.assertIn('UNSEALED_CAPTURE',v.capture(self.work)['flags'])
    def test_source_change_or_io_failure_flagged(self):
        self.edit('session',lambda r:r[-1].update(io_ok='0'));self.assertIn('IO_OR_SOURCE_CHANGE_REVIEW',v.capture(self.work)['flags'])
    def test_bad_quote_not_silently_accepted(self):
        self.edit('ticks',lambda r:r[0].update(ask='1.0'))
        with self.assertRaises(ValueError):v.capture(self.work)
    def test_duplicate_arrival_ms_allowed_but_reverse_not(self):
        self.edit('ticks',lambda r:r[1].update(mono_elapsed_ms=r[0]['mono_elapsed_ms']));v.capture(self.work)
        self.edit('ticks',lambda r:r[1].update(mono_elapsed_ms='0'))
        with self.assertRaises(ValueError):v.capture(self.work)
    def test_schema_and_partial_rows_rejected(self):
        p=self.work/'ticks.csv';p.write_text('sequence,bid\n1\n')
        with self.assertRaises(ValueError):v.capture(self.work)

class BOTests(unittest.TestCase):
    def test_empty_templates_are_no_data(self):
        self.assertEqual(v.bo(ROOT/'templates/BO_Platform_Quotes.csv','quotes')['status'],'NO_DATA');self.assertEqual(v.bo(ROOT/'templates/BO_Platform_Trades.csv','trades')['records'],0)
    def test_timezone_required(self):
        with self.assertRaises(ValueError):v.timestamp('2026-10-29T10:00:00')
        self.assertEqual(v.timestamp('2026-10-29T10:00:00+07:00'),v.timestamp('2026-10-29T03:00:00Z'))
    def test_percentage_and_missing_source_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'quotes.csv';header=v.FIELDS['bo_quotes'].split(',')
            row=dict(zip(header,['1','Olymp Trade','DEMO','EUR/USD','2026-10-29T10:00:00+07:00','1.1','82','','','screenshot1']))
            save(p,[row],header)
            with self.assertRaises(ValueError):v.bo(p,'quotes')
            row.update(payout_5m='.82');save(p,[row],header);self.assertEqual(v.bo(p,'quotes')['records'],1)
            row.update(source_reference='');save(p,[row],header)
            with self.assertRaises(ValueError):v.bo(p,'quotes')
    def test_wrong_empty_schema_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'wrong.csv';p.write_text('x,y\n')
            with self.assertRaises(ValueError):v.bo(p,'quotes')

if __name__=='__main__':unittest.main()
