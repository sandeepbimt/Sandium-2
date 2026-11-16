"""Execute the production fingerprint gate around a real preparation reset.
Small synthetic outputs test orchestration/integrity, not native Android compilation.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'.circleci/scripts/capture-brave-siso-checkpoint.sh'

class RestoredCheckpointIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.src=self.root/'brave-work/src'
        self.out=self.src/'out/android_Release_arm64'
        for name,data in {'build.ninja':'build output: cc input\n','args.gn':'target_cpu = "arm64"\nenable_test_feature = false\n','args_generated.gni':'enable_test_feature = false\n','.siso_fs_state':'state','obj/a.o':'compiled object','gen/a.h':'generated header'}.items():
            p=self.out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)
        self.env=dict(os.environ,CIRCLE_WORKING_DIRECTORY=str(self.root),CIRCLE_WORKFLOW_ID='fixture-workflow',CIRCLE_BUILD_NUM='fixture')
    def capture(self,stage,phase):
        return subprocess.run(['bash',str(SCRIPT),phase],env=dict(self.env,BRAVE_STAGE_INDEX=str(stage)),text=True,capture_output=True)
    def test_real_reset_changes_generated_args_but_restored_gate_precedes_it(self):
        self.assertEqual(self.capture(1,'checkpoint-ready').returncode,0)
        restored=self.capture(2,'restore')
        self.assertEqual(restored.returncode,0,restored.stdout+restored.stderr)
        self.assertIn('HANDOFF_COMPARISON=PASS',restored.stdout)
        spec=importlib.util.spec_from_file_location('recipe',ROOT/'.circleci/scripts/sandium-removal-recipe.py')
        recipe=importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe)
        manifest={'brave_pin':'fixture','chromium_pin':'fixture','gn_args':{'enable_test_feature':False}}
        before={p:p.read_bytes() for p in (self.out/'obj/a.o',self.out/'gen/a.h',self.out/'.siso_fs_state')}
        with mock.patch.object(recipe.subprocess,'check_output',return_value='fixture'),mock.patch.object(recipe,'restore_payload',return_value={'core':{},'chromium':{}}):
            recipe.reset(manifest,self.src/'brave',self.src,self.out)
        self.assertNotIn('enable_test_feature',(self.out/'args_generated.gni').read_text())
        for p,data in before.items():self.assertEqual(p.read_bytes(),data)
        # This demonstrates why comparing after preparation was incorrect;
        # the strict gate is not relaxed to accept post-restore mutations.
        late=self.capture(2,'restore')
        self.assertNotEqual(late.returncode,0)
        self.assertIn('ARGS_GENERATED_SHA256=DIFFERENT',late.stdout)
    def test_actual_restore_corruption_still_fails(self):
        for rel in ('args_generated.gni','obj/a.o','gen/a.h','.siso_fs_state'):
            with self.subTest(path=rel):
                self.assertEqual(self.capture(1,'checkpoint-ready').returncode,0)
                p=self.out/rel;original=p.read_bytes();p.write_bytes(original+b'corrupt')
                result=self.capture(2,'restore');self.assertNotEqual(result.returncode,0)
                self.assertIn('HANDOFF_COMPARISON=FAIL',result.stdout);p.write_bytes(original)
    def test_continuation_missing_expected_report_fails_closed(self):
        result=self.capture(2,'restore')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('missing same-workflow prior',result.stdout)
        self.assertEqual(self.capture(1,'restore').returncode,0)

if __name__=='__main__':unittest.main()
