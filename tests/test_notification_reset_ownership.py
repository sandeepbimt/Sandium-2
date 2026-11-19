"""Deferred permission source ownership survives the canonical reset/reapply."""
import json,unittest,importlib.util,shutil,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class OwnershipTest(unittest.TestCase):
 def test_declared_inputs_and_pinned_brave_replay(self):
  m=json.loads((ROOT/'.circleci/features/removal-recipe.json').read_text())
  controller='chrome/browser/notifications/android/java/src/org/chromium/chrome/browser/notifications/permissions/NotificationPermissionController.java'
  coordinator='chrome/android/java/src/org/chromium/chrome/browser/tabbed_mode/TabbedRootUiCoordinator.java'
  for p in (controller,coordinator):self.assertIn(p,m['chromium_restore'])
  self.assertEqual(m['chromium_restore_patches'][coordinator],'patches/chrome-android-java-src-org-chromium-chrome-browser-tabbed_mode-TabbedRootUiCoordinator.java.patch')
  script=(ROOT/'.circleci/experimental-steps/product-overlay-27-0.sh').read_text()
  self.assertLess(script.index('apply-sandium-welcome-setup.py'),script.index('apply-sandium-deferred-notifications.py'))
 def test_ordered_wrapper_guard_rejects_missing_notification_hook(self):
  spec=importlib.util.spec_from_file_location('wiring_notification',ROOT/'.circleci/scripts/flow_wiring.py')
  w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
  w.verify_product_wrappers(ROOT)
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);shutil.copytree(ROOT/'.circleci',r/'.circleci')
   p=r/'.circleci/experimental-steps/product-overlay-27-0.sh'
   p.write_text('\n'.join(x for x in p.read_text().splitlines() if 'apply-sandium-deferred-notifications.py' not in x)+'\n')
   with self.assertRaisesRegex(ValueError,'command sequence differs'):w.verify_product_wrappers(r)
 def test_final_notification_readback_cannot_be_omitted_or_mutate(self):
  spec=importlib.util.spec_from_file_location('wiring_notification_final',ROOT/'.circleci/scripts/flow_wiring.py')
  w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
  for change in ('remove','mutate'):
   with tempfile.TemporaryDirectory() as d:
    r=Path(d);shutil.copytree(ROOT/'.circleci',r/'.circleci')
    p=r/'.circleci/experimental-steps/product-overlay-30-0.sh'
    line='python3 .circleci/scripts/apply-sandium-deferred-notifications.py --src "$SRC" --verify-only'
    p.write_text(p.read_text().replace(line,'' if change=='remove' else line.replace(' --verify-only','')))
    with self.assertRaises(ValueError):w.verify_product_wrappers(r)
if __name__=='__main__':unittest.main()
