"""Tester-only boundaries, real preset inputs and unchanged native trading headers."""
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
EXPERT=ROOT/'mt4/Experts/EURUSD_M5_Intelligence_V230_Research.mq4'


class ResearchOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();folder=Path(cls.tmp.name);seen=set()
        def load(name):
            if name in seen:return ''
            seen.add(name);return flatten((ROOT/'mt4/Include/EURUSD_M5_V224'/name).read_text())
        def flatten(text):
            text=re.sub(r'(?<!\\)\\x([0-9A-Fa-f]{4})',lambda m:chr(int(m[1],16)),text).replace('"+"','')
            text=re.sub(r'#include [<"](?:EURUSD_M5_V224/)?([^>"]+)[>"]',lambda m:load(m[1]),text)
            text=re.sub(r'^#property.*$','',text,flags=re.M)
            text=re.sub(r'const (\w+) &(\w+)\[\]',r'const std::vector<\1> &\2',text)
            text=re.sub(r'(?<!const )(\w+) &(\w+)\[\]',r'std::vector<\1> &\2',text)
            return re.sub(r'\b(\w+) (\w+)\[\];',r'std::vector<\1> \2;',text)
        code=(ROOT/'tests/mql4_shim.hpp').read_text()+(ROOT/'tests/forex_api.hpp').read_text()+(ROOT/'tests/history_api.hpp').read_text()
        code+='\nbool fakeTesting=true,fakeOptimization=false;bool IsTesting(){return fakeTesting;}bool IsOptimization(){return fakeOptimization;}double MathRound(double x){return std::round(x);}double MathExp(double x){return std::exp(x);}\n'
        code+=flatten(EXPERT.read_text())
        code+=r'''
int main(int argc,char**argv){
 filesRoot=argv[1];int scenario=std::stoi(argv[2]);ForexResearchMinAtrPips=std::stod(argv[3]);
 fakeNowMs=1767225600000LL;fakeServer="Exness-Demo";
 if(scenario==1)fakeTesting=false;
 if(scenario==2)fakeOptimization=true;
 if(scenario==3)TradingMode=BinaryOption;
 if(scenario==4)ForexAllowRealTrading=true;
 if(scenario==5)ForexNewsFilter=true;
 if(scenario==6)UseValidatedLearning=true;
 if(scenario==7)EnableBinaryLearningDialogue=true;
 if(scenario==8)BinaryLearningAdviceAffectsSignals=true;
 if(scenario==9)EnableEmbeddedContext=true;
 if(scenario==10)fakePeriod=15;
 int result=OnInit();double applied=fxConfig.atrMinPips;bool started=fxStarted;
 string root=fxRoot;StringReplace(root,"\\","/");
 if(result==0)OnDeinit(0);
 int second=-1;if(scenario==11){second=OnInit();OnDeinit(0);}
 int files=0;for(auto&p:std::filesystem::recursive_directory_iterator(filesRoot))if(p.is_regular_file())files++;
 std::cout<<"{\"init\":"<<result<<",\"applied\":"<<applied<<",\"started\":"<<started
  <<",\"send_calls\":"<<fakeSendCalls<<",\"close_calls\":"<<fakeCloseCalls<<",\"files\":"<<files
  <<",\"root\":\""<<root<<"\",\"second_init\":"<<second<<"}";return 0;
}
'''
        path=folder/'research.cpp';path.write_text(code);cls.binary=folder/'research'
        proc=subprocess.run(['g++','-std=c++17','-O1',str(path),'-o',str(cls.binary)],capture_output=True,text=True)
        if proc.returncode:raise RuntimeError(proc.stderr)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def run_case(self,scenario=0,minimum='3'):
        with tempfile.TemporaryDirectory() as tmp:
            p=subprocess.run([str(self.binary),tmp,str(scenario),str(minimum)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            output=json.loads(p.stdout)
            metadata=list(Path(tmp).rglob('research_config_v230.csv'))
            output['metadata']=metadata[0].read_text() if metadata else None
        self.assertEqual(output['send_calls'],0);self.assertEqual(output['close_calls'],0)
        return output

    def test_rejects_live_or_demo_chart_before_file_writes(self):
        r=self.run_case(1);self.assertEqual(r['init'],2);self.assertEqual(r['files'],0);self.assertFalse(r['started'])

    def test_rejects_optimization_binary_real_news_learning_and_advice_modes(self):
        for scenario in range(2,10):
            with self.subTest(scenario=scenario):
                r=self.run_case(scenario);self.assertEqual(r['init'],2);self.assertEqual(r['files'],0)

    def test_rejects_non_m5_tester_and_invalid_thresholds(self):
        self.assertEqual(self.run_case(10)['init'],2)
        for minimum in ['-1','31','nan','inf']:
            with self.subTest(minimum=minimum):self.assertEqual(self.run_case(minimum=minimum)['init'],2)

    def test_all_eight_thresholds_reach_the_actual_native_configuration(self):
        for minimum in [3,2.5,2,1.5,1.25,1,.75,0]:
            with self.subTest(minimum=minimum):
                r=self.run_case(minimum=minimum);self.assertEqual(r['init'],0);self.assertTrue(r['started'])
                self.assertEqual(r['applied'],minimum)
                metadata=list(csv.DictReader(io.StringIO(r['metadata'])))[0]
                self.assertEqual(float(metadata['requested_min_atr_pips']),minimum)
                self.assertEqual(float(metadata['applied_min_atr_pips']),minimum)
                self.assertEqual(float(metadata['max_atr_pips']),30)
                self.assertEqual(float(metadata['shock_atr']),2.5)
                self.assertEqual(metadata['origin'],'TESTER_PRICE_ONLY_NO_NEWS')
                self.assertEqual(metadata['news_filter'],'0');self.assertEqual(metadata['real_allowed'],'0')
                if minimum==3:self.assertEqual(metadata['native_config_hash'],'2669644079')
                payload=metadata['tag']+'|'+metadata['requested_min_atr_pips']+'|'+metadata['applied_min_atr_pips']+'|'+metadata['native_config_hash']
                value=2166136261
                for byte in payload.encode('ascii'):value=((value^byte)*16777619)&0xffffffff
                self.assertEqual(value,int(metadata['checksum']))

    def test_reusing_tester_tag_is_rejected_and_original_run_is_preserved(self):
        r=self.run_case(11);self.assertEqual(r['init'],0);self.assertNotEqual(r['second_init'],0)
        self.assertTrue(r['metadata'])


class ResearchBundleTests(unittest.TestCase):
    def test_delivered_v229_native_headers_are_identical(self):
        baseline=json.loads((ROOT/'BASELINE_V229_HEADERS.json').read_text())
        self.assertEqual(len(baseline),40)
        for name,want in baseline.items():self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),want,name)

    def test_install_tree_matches_canonical_source(self):
        a=ROOT/'mt4';b=ROOT/'MQL4'
        self.assertEqual({p.relative_to(a):p.read_bytes() for p in a.rglob('*') if p.is_file()},
                         {p.relative_to(b):p.read_bytes() for p in b.rglob('*') if p.is_file()})

    def test_presets_contain_only_real_inputs_and_unique_safe_run_tags(self):
        names=set(re.findall(r'^input\s+\w+\s+(\w+)\s*=',EXPERT.read_text(),re.M))
        paths=sorted((ROOT/'mt4/Presets').glob('*.set'));self.assertEqual(len(paths),8)
        tags=set();values=set()
        for path in paths:
            pairs=[line.split('=',1) for line in path.read_text().splitlines() if line]
            data=dict(pairs);self.assertEqual(len(pairs),len(data));self.assertEqual(set(data),names)
            tags.add(data['InstanceTag']);values.add(float(data['ForexResearchMinAtrPips']))
            for key,want in {'TradingMode':'1','ForexEnableTrading':'true','ForexAllowRealTrading':'false','ForexNewsFilter':'false',
                             'UseValidatedLearning':'false','EnableEmbeddedContext':'false','EnableBinaryLearningDialogue':'false',
                             'BinaryLearningAdviceAffectsSignals':'false','ForexEnableAveraging':'false','ForexRiskPercent':'0.5',
                             'ForexMaxDailyLossPercent':'2.0','ForexMaxHoldMinutes':'60'}.items():
                self.assertEqual(data[key],want,(path.name,key))
        self.assertEqual(len(tags),8);self.assertEqual(values,{0,.75,1,1.25,1.5,2,2.5,3})


if __name__=='__main__':unittest.main()
