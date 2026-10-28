import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from intelligence.lease import exclusive
from intelligence.native_ledger import TYPES

ROOT=Path(__file__).resolve().parents[1]


class BaselineContractTests(unittest.TestCase):
    def test_journal_layout_is_local_and_version_is_independent(self):
        self.assertEqual(TYPES,ROOT/'mt4/Include/EURUSD_M5_V224/Types.mqh')
        self.assertTrue(TYPES.is_file())
        version=json.loads((ROOT/'VERSION.json').read_text())
        self.assertEqual(version['software_version'],'2.29')
        self.assertEqual(version['next_source_version'],'2.30')
        self.assertFalse(version['previous_version_required'])

    def test_all_installed_source_dependencies_match_canonical_source(self):
        installed=list((ROOT/'MQL4').rglob('*'))
        files=[p for p in installed if p.is_file()]
        self.assertGreaterEqual(len(files),23)
        for p in files:self.assertEqual(p.read_bytes(),(ROOT/'mt4'/p.relative_to(ROOT/'MQL4')).read_bytes(),str(p))

    def test_native_includes_are_self_contained_without_legacy_directories(self):
        import re
        for p in (ROOT/'mt4').rglob('*'):
            if not p.is_file():continue
            for name in re.findall(r'#include [<"]([^>"]+)[>"]',p.read_text()):
                target=ROOT/'mt4/Include'/name if '/' in name else p.parent/name
                self.assertTrue(target.is_file(),str(target))
                self.assertNotIn('V203',name);self.assertNotIn('V204',name)

    def test_only_one_companion_can_write_a_journal_and_crash_safe_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'learner.lock'
            with exclusive(path):
                with self.assertRaisesRegex(RuntimeError,'Another learner'):
                    with exclusive(path):pass
            with exclusive(path):pass

    def test_r10_core_audit_matches_this_final_source(self):
        report=json.loads((ROOT/'docs/r10-inheritance.json').read_text())
        preserved=[r for r in report['files'] if r['status']=='unchanged_logic']
        self.assertEqual(len(preserved),16)
        for r in report['files']:
            if 'v224_sha256' not in r:continue
            p=ROOT/'mt4/Include/EURUSD_M5_V224'/r['file']
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),r['v224_sha256'])


if __name__=='__main__':unittest.main()
