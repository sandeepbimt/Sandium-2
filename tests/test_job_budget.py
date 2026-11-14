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

class JobBudgetTests(unittest.TestCase):
    def test_insufficient_window_still_refused(self):
        with self.assertRaisesRegex(ValueError,'Insufficient'):
            budget.build_seconds(0,1746) # observed stage 2 before optimization
        self.assertEqual(budget.build_seconds(0,1680),60)
        with self.assertRaises(ValueError):budget.build_seconds(0,1681)
        self.assertEqual(budget.build_seconds(0,1746-164),158)
        self.assertEqual(budget.build_seconds(0,0),1200)

    def test_imminent_rollup_and_base_refresh_reported_without_weakening_reserves(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);state=root/'.checkpoint-state';state.mkdir();now=time.time()
            (state/'job-start.json').write_text(json.dumps(dict(epoch=now)))
            (state/'selected.json').write_text(json.dumps(dict(payload=dict(plan=dict(
                base=dict(expires_at=now+100),layers=[dict(expires_at=now+500000)]*7)))))
            result=subprocess.run([sys.executable,str(SCRIPT),str(root)],capture_output=True,text=True,check=True)
            self.assertEqual(result.stdout.strip(),'1200')
            diag=json.loads(result.stderr.split(' ',1)[1]);self.assertTrue(diag['rollup_due'])
            self.assertTrue(diag['base_refresh_due']);self.assertEqual(diag['capture_reserve'],900)
            self.assertEqual(diag['native_save_reserve'],600)

if __name__=='__main__':unittest.main()
