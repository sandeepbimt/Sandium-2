import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
SCRIPT=Path(__file__).resolve().parents[1]/'.circleci/checkpoint/job_budget.py'
spec=importlib.util.spec_from_file_location('job_budget',SCRIPT)
budget=importlib.util.module_from_spec(spec);spec.loader.exec_module(budget)

def valid_plan(expiry=1000000, count=3):
    base=dict(id='0'*64,manifest_sha256='a'*64,key='base-key',expires_at=expiry)
    layers=[];parent=base['id']
    for i in range(1,count+1):
        ident=f'{i:064x}'
        layers.append(dict(id=ident,parent=parent,key=f'delta-{i}',expires_at=expiry))
        parent=ident
    return dict(base=base,layers=layers,head=parent)

class JobBudgetTests(unittest.TestCase):
    def test_insufficient_window_still_refused(self):
        with self.assertRaisesRegex(ValueError,'Insufficient'):
            budget.build_seconds(0,1746) # observed stage 2 before optimization
        self.assertEqual(budget.build_seconds(0,1500),60)
        with self.assertRaises(ValueError):budget.build_seconds(0,1501)
        with self.assertRaises(ValueError):budget.build_seconds(0,1746-164)
        self.assertEqual(budget.build_seconds(0,0),1200)

    def test_imminent_rollup_and_base_refresh_reported_without_weakening_reserves(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);state=root/'.checkpoint-state';state.mkdir();now=time.time()
            (state/'job-start.json').write_text(json.dumps(dict(epoch=now)))
            plan=valid_plan(now+500000,7);plan['base']['expires_at']=now+100
            (state/'selected.json').write_text(json.dumps(dict(payload=dict(plan=plan))))
            result=subprocess.run([sys.executable,str(SCRIPT),str(root)],capture_output=True,text=True,check=True)
            self.assertEqual(result.stdout.strip(),'1200')
            diag=json.loads(result.stderr.split(' ',1)[1]);self.assertTrue(diag['rollup_due'])
            self.assertTrue(diag['base_refresh_due']);self.assertEqual(diag['capture_reserve'],900)
            self.assertEqual(diag['native_save_reserve'],600)

    def test_ordinary_delta_and_full_postbuild_margin(self):
        plan=valid_plan()
        self.assertEqual(budget.save_policy(plan,0)['seconds'],300)
        self.assertEqual(budget.build_seconds(0,1746,plan),114)
        self.assertEqual(budget.build_seconds(0,1800,plan),60)
        with self.assertRaises(ValueError):budget.build_seconds(0,1801,plan)
        # Even maximum compilation leaves capture, save, shutdown, export/audit
        # and the separate five-minute CircleCI hard-limit cushion.
        now=1746; duration=budget.build_seconds(0,now,plan)
        self.assertEqual(now+duration+900+300+60+180,3300)
        self.assertEqual(3600-(now+duration+900+300+60+180),300)

    def test_horizon_and_rollup_are_conservative(self):
        cutoff=3600+2*86400
        plan=valid_plan(cutoff+1)
        self.assertEqual(budget.save_policy(plan,0)['seconds'],300)
        plan['layers'][0]['expires_at']=cutoff
        self.assertTrue(budget.save_policy(plan,0)['rollup_due'])
        self.assertEqual(budget.save_policy(plan,0)['seconds'],600)
        plan=valid_plan(cutoff+1,7)
        self.assertEqual(budget.save_policy(plan,0)['seconds'],600)
        plan=valid_plan(cutoff+1);plan['base']['expires_at']=cutoff
        self.assertTrue(budget.save_policy(plan,0)['base_refresh_due'])
        # Classifier only depends on job start, so no expiry-boundary drift
        # between compilation and capture within this one-hour job.
        self.assertEqual(budget.save_policy(plan,0),budget.save_policy(plan,0))

    def test_unknown_plan_never_gets_short_reserve(self):
        for plan in (None,{},dict(base={},layers=[]),dict(base=dict(expires_at=1000000),layers=[{}]),
                     dict(base=dict(expires_at=float('nan')),layers=[dict(expires_at=1000000)])):
            self.assertEqual(budget.save_policy(plan,0)['seconds'],600)

    def test_incomplete_or_reordered_chain_stays_conservative(self):
        import copy
        good=valid_plan()
        cases=[]
        for path in ('head','base','layers'):
            item=copy.deepcopy(good);del item[path];cases.append(item)
        for field in ('id','parent','key','expires_at'):
            item=copy.deepcopy(good);del item['layers'][0][field];cases.append(item)
        item=copy.deepcopy(good);item['layers'].reverse();cases.append(item)
        item=copy.deepcopy(good);item['head']='f'*64;cases.append(item)
        item=copy.deepcopy(good);item['base']['manifest_sha256']='invalid';cases.append(item)
        for plan in cases:self.assertEqual(budget.save_policy(plan,0)['seconds'],600)

    def test_malformed_selected_cli_conservative(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);state=root/'.checkpoint-state';state.mkdir()
            (state/'job-start.json').write_text(json.dumps(dict(epoch=time.time())))
            for content in ('not json','null','{}','{"payload":{"plan":null}}'):
                (state/'selected.json').write_text(content)
                result=subprocess.run([sys.executable,str(SCRIPT),str(root)],capture_output=True,text=True,check=True)
                diag=json.loads(result.stderr.split(' ',1)[1])
                self.assertEqual(diag['native_save_reserve'],600)

    def test_driver_uses_shared_policy_for_capture(self):
        driver=(SCRIPT.parents[1]/'bridge/driver.py').read_text()
        self.assertIn('from job_budget import save_policy',driver)
        self.assertIn('policy=save_policy(plan,started)',driver)
        self.assertIn("reserve=policy['seconds']",driver)

if __name__=='__main__':unittest.main()
