"""Callback contract tests. Mock successes are NOT executed GN/service proof.

One negative test runs the real isolated subprocess to reject a wrong baseline.
No Android build, GN generation, cache restoration or CI is executed by this suite.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import feature_seed_callbacks as callbacks

class SeedCallbacksTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'feature';self.root.mkdir()
        self.baseline=Path(self.tmp.name)/'baseline';self.baseline.mkdir()
        manifest=self.root/'sandium/features/manifest.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({'schema':1,'features':['menu','toolbar']}))

    def make(self,baseline=None):
        return callbacks.SeedCallbacks(self.root,baseline or self.baseline,env={'PATH':'/usr/bin:/bin','RAWS_FEATURE_JOB_STARTED_EPOCH':str(time.time())})

    def success(self,command,**kwargs):
        phase=command[6]
        proof={'phase':phase,'baseline_receipt':callbacks.RECEIPT,'fingerprint':'f'*64,
               'test_only_mock':True}
        return SimpleNamespace(stdout='FEATURE_SEED_PHASE_PROOF='+json.dumps(proof)+'\n',stderr='')

    def test_disabled_and_same_checkout_fail_before_any_execution(self):
        with self.assertRaisesRegex(ValueError,'separate unchanged'):
            self.make(self.root)
        (self.root/'sandium/features/manifest.json').write_text('{"schema":1,"features":[]}')
        with patch.object(callbacks,'run_owned') as run:
            with self.assertRaisesRegex(ValueError,'nonempty explicit'):
                self.make()
            run.assert_not_called()

    def test_mock_contract_routes_baseline_and_new_phases_separately(self):
        worker=self.make()
        self.assertEqual(set(worker.callbacks()),{'verify_baseline','apply_features','generate_gn','verify_features'})
        with patch.object(callbacks,'run_owned',side_effect=self.success) as run:
            worker.verify_baseline(self.root,{'id':callbacks.RECEIPT})
            worker.apply_features(self.root);worker.generate_gn(self.root)
            worker.verify_features(self.root,'f'*64)
        calls=run.call_args_list
        self.assertEqual(len(calls),4)
        self.assertEqual([c.args[0][6] for c in calls],['baseline','apply','gn','verify'])
        for index,call in enumerate(calls):
            command=call.args[0]
            self.assertEqual(command[1:3],['-I','-c'])
            self.assertEqual(Path(command[4]),self.baseline if index==0 else self.root)
            self.assertLessEqual(call.kwargs['timeout'],callbacks.PHASE_LIMITS[command[6]])
            self.assertEqual(command[7:10],[callbacks.BASELINE_COMMIT,callbacks.BASELINE_FINGERPRINT,callbacks.RECEIPT])
        self.assertEqual(calls[-1].args[0][-1],'f'*64)
        for phase in ('baseline','apply','gn','verify'):
            proof=json.loads((self.root/f'artifacts/feature-seed/{phase}-proof.json').read_text())
            self.assertTrue(proof['test_only_mock'])

    def test_wrong_order_root_and_receipt_rejected(self):
        worker=self.make()
        with self.assertRaisesRegex(ValueError,'order/root'):
            worker.apply_features(self.root)
        with self.assertRaisesRegex(ValueError,'Unreviewed baseline'):
            worker.verify_baseline(self.root,{'id':'other'})
        with patch.object(callbacks,'run_owned',side_effect=self.success):
            worker.verify_baseline(self.root,{'id':callbacks.RECEIPT})
        with self.assertRaisesRegex(ValueError,'order/root'):
            worker.apply_features(self.baseline)

    def test_failure_retains_logs_without_success_proof(self):
        error=subprocess.CalledProcessError(1,['test'],output='diagnostic',stderr='failed gate')
        with patch.object(callbacks,'run_owned',side_effect=error), patch.object(callbacks.SeedCallbacks,'_cleanup'):
            with self.assertRaises(subprocess.CalledProcessError):
                self.make().verify_baseline(self.root,{'id':callbacks.RECEIPT})
        directory=self.root/'artifacts/feature-seed'
        self.assertEqual((directory/'baseline-stderr.log').read_text(),'failed gate')
        self.assertFalse((directory/'baseline-proof.json').exists())

    def test_no_success_proof_without_unique_child_receipt(self):
        for output in ('', 'FEATURE_SEED_PHASE_PROOF={}\n',
                       'FEATURE_SEED_PHASE_PROOF={}\nFEATURE_SEED_PHASE_PROOF={}\n'):
            with patch.object(callbacks,'run_owned',return_value=SimpleNamespace(stdout=output,stderr='')):
                with self.assertRaises(ValueError):
                    self.make().verify_baseline(self.root,{'id':callbacks.RECEIPT})
        self.assertFalse((self.root/'artifacts/feature-seed/baseline-proof.json').exists())

    def test_real_isolated_subprocess_rejects_wrong_baseline_commit(self):
        # This checkout is the new feature implementation, not reviewed e7e7820.
        with patch.object(callbacks.SeedCallbacks,'_cleanup'), self.assertRaises(subprocess.CalledProcessError):
            self.make(ROOT).verify_baseline(self.root,{'id':callbacks.RECEIPT})
        error=(self.root/'artifacts/feature-seed/baseline-stderr.log').read_text()
        self.assertIn('Wrong baseline checkout commit',error)
        self.assertFalse((self.root/'artifacts/feature-seed/baseline-proof.json').exists())
        journal=(self.root/'artifacts/feature-seed/baseline-commands.jsonl').read_text()
        self.assertIn('rev-parse',journal)

    def test_original_job_budget_is_required_and_not_reset_between_phases(self):
        with self.assertRaisesRegex(ValueError,'start epoch required'):
            callbacks.SeedCallbacks(self.root,self.baseline,env={})
        worker=self.make()
        worker.job_started=time.time()-2000
        with patch.object(callbacks,'run_owned') as run:
            with self.assertRaisesRegex(ValueError,'Insufficient original job'):
                worker.verify_baseline(self.root,{'id':callbacks.RECEIPT})
            run.assert_not_called()
        worker=self.make()
        worker.job_started=time.time()-1500
        self.assertLessEqual(worker._timeout('gn'),150)

    def test_cold_baseline_scan_budget_preserves_original_archive_reserve(self):
        worker=self.make()
        self.assertEqual(worker._timeout('baseline'),600)
        # A slow restore consumes the larger allowance, never archive reserve.
        with patch.object(worker,'_remaining',return_value=1970):
            self.assertEqual(worker._timeout('baseline'),300)
        with patch.object(worker,'_remaining',return_value=1729):
            with self.assertRaisesRegex(ValueError,'Insufficient original job'):
                worker._timeout('baseline')
        self.assertEqual(callbacks.POST_TRANSITION_RESERVE,1620)
        self.assertEqual(callbacks.CLEANUP_RESERVE,50)
        self.assertEqual(callbacks.PHASE_LIMITS['apply'],120)
        self.assertEqual(callbacks.PHASE_LIMITS['verify'],180)

    def test_timeout_invokes_quiescence_and_cannot_emit_success(self):
        worker=self.make()
        with patch.object(callbacks,'run_owned',side_effect=subprocess.TimeoutExpired(['test'],1)), \
             patch.object(worker,'_cleanup') as cleanup:
            with self.assertRaises(subprocess.TimeoutExpired):
                worker.verify_baseline(self.root,{'id':callbacks.RECEIPT})
            cleanup.assert_called_once()
        self.assertFalse((self.root/'artifacts/feature-seed/baseline-proof.json').exists())

    def test_real_timeout_terminates_owned_grandchild(self):
        pidfile=Path(self.tmp.name)/'child.pid'
        child="import os,time;open("+repr(str(pidfile))+",'w').write(str(os.getpid()));time.sleep(60)"
        parent="import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',"+repr(child)+"]);time.sleep(60)"
        with self.assertRaises(subprocess.TimeoutExpired):
            callbacks.run_owned([sys.executable,'-c',parent],env=dict(os.environ),cwd=self.root,timeout=0.5,grace=1)
        self.assertTrue(pidfile.is_file())
        status=Path('/proc')/pidfile.read_text()/'stat'
        if status.exists():
            self.assertEqual(status.read_text().split()[2],'Z', 'Grandchild remains running')

    def test_reviewed_child_has_real_commands_and_transition_guards(self):
        child=callbacks._CHILD
        compile(child,'feature-seed-child','exec')
        for required in ('quiesce(', 'verify(src,data)', 'verify_official(', 'verify_graph_outputs(',
                         "'--fail-on-unused-args'", "'gen','out/RawSandium'", 'subprocess.run(',
                         "'transitioning'", 'feature_fingerprint', 'load_manifest(checkout)',
                         "'rev-parse','HEAD'", "'diff','HEAD','--name-only'", 'verify_applied(src,checkout).hashes'):
            self.assertIn(required,child)
        self.assertNotIn('RAWS_ALLOW_FRESH_SEED',child)
        self.assertNotIn("fresh.json",child)
        self.assertNotIn('configure(src',child)

if __name__=='__main__':unittest.main()
