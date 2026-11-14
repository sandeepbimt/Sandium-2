import shutil
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.circleci/scripts'))
from flow_wiring import verify_full_wiring, REQUIRED


class FullOverlayWiring(unittest.TestCase):
    def fixture(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);(root/'.circleci/scripts').mkdir(parents=True)
        shutil.copytree(ROOT/'.circleci/experimental-steps',root/'.circleci/experimental-steps')
        shutil.copy2(ROOT/'.circleci/config.yml',root/'.circleci/config.yml')
        for names in REQUIRED.values():
            for name in names:
                target=root/('.circleci/tests' if name == 'test_status_underlap_patch.py' else '.circleci/scripts')/name
                target.parent.mkdir(parents=True,exist_ok=True);target.touch()
        return root

    def edit(self,root,path,old,new):
        p=root/path;text=p.read_text();self.assertIn(old,text);p.write_text(text.replace(old,new,1))

    def test_removal_overlay_cannot_be_added(self):
        root=self.fixture()
        p=root/'.circleci/config.yml'
        p.write_text(p.read_text().replace('product-overlay-29-0.sh','product-overlay-30-0.sh',1))
        with self.assertRaisesRegex(ValueError,'Removal overlay'):verify_full_wiring(root)

    def test_actual_all_five_full_stages(self):
        jobs=verify_full_wiring(ROOT)
        self.assertEqual(sum(j.startswith('full-stage-') for j in jobs),5)

    def test_old_build_wrapper_is_rejected(self):
        root=self.fixture();self.edit(root,'.circleci/config.yml',
            'command: bash .circleci/experimental-steps/full-bounded-build.sh',
            'command: bash .circleci/experimental-steps/bounded-build.sh')
        with self.assertRaisesRegex(ValueError,'full-bounded-build.*invocation'):verify_full_wiring(root)

    def test_obsolete_flow_job_is_rejected(self):
        root=self.fixture();self.edit(root,'.circleci/config.yml',
            '  full-stage-1:', '  sandium-stage-1:')
        with self.assertRaisesRegex(ValueError,'Obsolete Flow jobs'):verify_full_wiring(root)

    def test_actual_repository_only_ui_policy_assertions(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('ui_policy_test',ROOT/'.circleci/scripts/test-sandium-ui-prune.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.verify_repository_policy(ROOT)

    def test_comment_is_not_an_executed_ui_overlay(self):
        root=self.fixture();self.edit(root,'.circleci/experimental-steps/product-overlay-29-0.sh',
            'python3 .circleci/scripts/apply-sandium-ui-prune.py','# python3 .circleci/scripts/apply-sandium-ui-prune.py')
        with self.assertRaisesRegex(ValueError,'command'):verify_full_wiring(root)

    def test_ui_assertions_cannot_be_removed(self):
        root=self.fixture();self.edit(root,'.circleci/experimental-steps/product-overlay-29-0.sh',
            'python3 .circleci/scripts/test-sandium-ui-prune.py','echo .circleci/scripts/test-sandium-ui-prune.py')
        with self.assertRaisesRegex(ValueError,'command'):verify_full_wiring(root)

    def test_final_branding_cannot_be_skipped_or_reordered(self):
        root=self.fixture();self.edit(root,'.circleci/experimental-steps/product-overlay-29-0.sh',
            'python3 .circleci/scripts/apply-sandium-visible-branding.py','echo .circleci/scripts/apply-sandium-visible-branding.py')
        with self.assertRaisesRegex(ValueError,'command'):verify_full_wiring(root)
        root=self.fixture();self.edit(root,'.circleci/experimental-steps/product-overlay-29-0.sh',
            '--report', '--not-report')
        with self.assertRaisesRegex(ValueError,'coverage report'):verify_full_wiring(root)

    def test_popup_apply_and_test_cannot_be_skipped(self):
        for name in ('apply-sandium-shields-popup.py', 'test-sandium-shields-popup.py'):
            root=self.fixture();self.edit(root,'.circleci/experimental-steps/product-overlay-29-0.sh',
                'python3 .circleci/scripts/'+name, '# python3 .circleci/scripts/'+name)
            with self.assertRaisesRegex(ValueError,'command'):verify_full_wiring(root)

    def test_popup_must_target_restored_core(self):
        root=self.fixture();self.edit(root,'.circleci/experimental-steps/product-overlay-29-0.sh',
            'apply-sandium-shields-popup.py "$CORE"',
            'apply-sandium-shields-popup.py "$SRC"')
        with self.assertRaisesRegex(ValueError,'popup must target restored core'):verify_full_wiring(root)

    def test_status_trial_cannot_be_skipped(self):
        root=self.fixture();self.edit(root,'.circleci/experimental-steps/product-overlay-29-0.sh',
            'python3 .circleci/scripts/apply-sandium-scroll-status-bar.py','echo .circleci/scripts/apply-sandium-scroll-status-bar.py')
        with self.assertRaisesRegex(ValueError,'command'):verify_full_wiring(root)

    def test_native_theme_cannot_be_skipped(self):
        root=self.fixture();self.edit(root,'.circleci/experimental-steps/product-overlay-29-0.sh',
            'python3 .circleci/scripts/apply-sandium-native-theme.py','echo .circleci/scripts/apply-sandium-native-theme.py')
        with self.assertRaisesRegex(ValueError,'command'):verify_full_wiring(root)

    def test_stage_three_wrong_feature_ui_order_fails(self):
        root=self.fixture();p=root/'.circleci/config.yml';text=p.read_text()
        a=text.index('  full-stage-3:');b=text.index('  full-stage-4:',a)
        chunk=text[a:b].replace('product-overlay-28-0.sh','SWAP').replace('product-overlay-29-0.sh','product-overlay-28-0.sh').replace('SWAP','product-overlay-29-0.sh')
        p.write_text(text[:a]+chunk+text[b:])
        with self.assertRaisesRegex(ValueError,'full-stage-3.*order'):verify_full_wiring(root)

    def test_last_stage_missing_ui_wrapper_fails(self):
        root=self.fixture();p=root/'.circleci/config.yml';text=p.read_text();a=text.index('  full-stage-5:')
        p.write_text(text[:a]+text[a:].replace('command: bash .circleci/experimental-steps/product-overlay-29-0.sh','command: echo skipped',1))
        with self.assertRaisesRegex(ValueError,'full-stage-5.*exactly one'):verify_full_wiring(root)

    def test_branch_gated_or_conditional_overlay_is_rejected(self):
        root=self.fixture();self.edit(root,'.circleci/experimental-steps/product-overlay-29-0.sh','set -euo pipefail','set -euo pipefail\nif false; then')
        with self.assertRaisesRegex(ValueError,'conditional'):verify_full_wiring(root)

    def test_reset_and_filter_regression_tests_remain_wired(self):
        root=self.fixture();self.edit(root,'.circleci/experimental-steps/product-overlay-25-0.sh','--reset-shared','--not-reset')
        with self.assertRaisesRegex(ValueError,'Shared reset'):verify_full_wiring(root)
        root=self.fixture();self.edit(root,'.circleci/experimental-steps/product-overlay-28-0.sh',
            'python3 .circleci/scripts/test-sandium-filter-bootstrap.py','echo .circleci/scripts/test-sandium-filter-bootstrap.py')
        with self.assertRaisesRegex(ValueError,'command'):verify_full_wiring(root)

    def test_early_shell_exit_cannot_bypass_apply_or_tests(self):
        root=self.fixture();self.edit(root,'.circleci/experimental-steps/product-overlay-29-0.sh','set -euo pipefail','set -euo pipefail\nexit 0')
        with self.assertRaisesRegex(ValueError,'unsupported shell command'):verify_full_wiring(root)

    def test_same_basename_elsewhere_does_not_count(self):
        root=self.fixture();self.edit(root,'.circleci/experimental-steps/product-overlay-29-0.sh',
            '.circleci/scripts/apply-sandium-ui-prune.py','/tmp/apply-sandium-ui-prune.py')
        with self.assertRaisesRegex(ValueError,'command'):verify_full_wiring(root)

    def test_new_ui_contracts_cannot_be_skipped(self):
        for token in ('apply-sandium-bottom-toolbar.py', 'test-sandium-bottom-toolbar.py', 'apply-sandium-paged-menu.py'):
            root=self.fixture();self.edit(root,'.circleci/experimental-steps/product-overlay-29-0.sh',
                'python3 .circleci/scripts/'+token, '# python3 .circleci/scripts/'+token)
            with self.assertRaisesRegex(ValueError,'command'): verify_full_wiring(root)

    def test_new_ui_contracts_require_actual_restored_inputs(self):
        cases=[('test-sandium-bottom-toolbar.py --src "$SRC"','test-sandium-bottom-toolbar.py --src "$CORE"','toolbar'),
               ('--repo "$ROOT" --verify-only','--repo "$ROOT"','verification')]
        for old,new,error in cases:
            root=self.fixture();self.edit(root,'.circleci/experimental-steps/product-overlay-29-0.sh',old,new)
            with self.assertRaisesRegex(ValueError,error): verify_full_wiring(root)

if __name__=='__main__':unittest.main()
