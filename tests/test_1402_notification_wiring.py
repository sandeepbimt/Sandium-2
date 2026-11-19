import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('flow1402',ROOT/'.circleci/scripts/flow_wiring.py');flow=importlib.util.module_from_spec(spec);spec.loader.exec_module(flow)
class NotificationWiring(unittest.TestCase):
 def test_reset_and_exact_upstream_patch_ownership(self):
  recipe=json.loads((ROOT/'.circleci/features/removal-recipe.json').read_text())
  owners=json.loads((ROOT/'.circleci/features/deferred-notifications/source-manifest.json').read_text())
  for name in owners:
   for field in ['chromium_restore','ui_only_chromium_restore']:self.assertEqual(recipe[field].count(name),1)
  coordinator=next(x for x in owners if x.endswith('TabbedRootUiCoordinator.java'))
  self.assertEqual(recipe['chromium_restore_patches'][coordinator],'patches/chrome-android-java-src-org-chromium-chrome-browser-tabbed_mode-TabbedRootUiCoordinator.java.patch')
 def test_final_apply_verify_are_exact_and_before_audits(self):
  wrapper=ROOT/'.circleci/experimental-steps/product-overlay-30-0.sh';calls=flow.shell_invocations(wrapper)
  notice='apply-sandium-deferred-notifications.py';self.assertEqual([(n,a) for n,a in calls if n==notice],[(notice,['--src','$SRC']),(notice,['--src','$SRC','--verify-only'])])
  i=next(i for i,(n,a) in enumerate(calls) if n==notice)
  self.assertEqual(calls[i-1],('apply-sandium-native-navigation.py',['$SRC','--mode','configured','--verify-only']))
  self.assertEqual(calls[i+2],('precheck-graph.py',['--audits-only']))
  flow.verify_full_wiring(ROOT)
if __name__=='__main__':unittest.main()
