import hashlib, importlib.util,json,shutil,tempfile,unittest,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('patch',HERE.parents[1]/'scripts'/'apply-sandium-deferred-notifications.py');patch=importlib.util.module_from_spec(spec);spec.loader.exec_module(patch)
class Test(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.src=Path(self.temp.name)
  self.manifest=json.loads((HERE/'source-manifest.json').read_text())
  for rel,digest in self.manifest.items():
   f=HERE/'fixtures'/Path(rel).name;self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(),digest)
   target=self.src/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,target)
 def test_actual_pinned_apply_reapply(self):
  patch.apply(self.src);first={p:p.read_bytes() for p in self.src.rglob('*.java')};patch.apply(self.src)
  self.assertEqual(first,{p:p.read_bytes() for p in first})
 def test_exact_brave_replay_preserved(self):
  file=HERE/'fixtures'/'chrome-android-java-src-org-chromium-chrome-browser-tabbed_mode-TabbedRootUiCoordinator.java.patch'
  subprocess.run(['git','apply','--unsafe-paths','--directory='+str(self.src),str(file)],check=True,capture_output=True)
  patch.apply(self.src);patch.apply(self.src)
  result=next(p for p in self.src.rglob('*.java') if p.name.startswith('Tabbed')).read_text()
  self.assertIn('new BraveTabGroupSyncControllerImpl(',result)
 def test_verify_only_requires_complete_composition_without_mutating(self):
  before={p:p.read_bytes() for p in self.src.rglob('*.java')}
  with self.assertRaises(ValueError):patch.apply(self.src,verify_only=True)
  self.assertEqual(before,{p:p.read_bytes() for p in before})
  patch.apply(self.src)
  applied={p:p.read_bytes() for p in before}
  patch.apply(self.src,verify_only=True)
  self.assertEqual(applied,{p:p.read_bytes() for p in before})
  target=next(p for p in before if p.name.startswith('Tabbed'))
  target.write_text(target.read_text().replace('mSandiumNotificationsDestroyed = true;', 'mSandiumNotificationsDestroyed = false;'))
  altered={p:p.read_bytes() for p in before}
  with self.assertRaises(ValueError):patch.apply(self.src,verify_only=True)
  self.assertEqual(altered,{p:p.read_bytes() for p in before})
 def test_exact_nullable_fields_compile(self):
  # Actual generated declarations with TYPE_USE-only Nullable, not Android/NullAway compilation.
  fields=next(row['new'] for row in json.loads((HERE/'patches.json').read_text())
              if row['old']=='    private @Nullable NotificationPermissionController mNotificationPermissionController;')
  sources={'Nullable.java':'import java.lang.annotation.*; @Target(ElementType.TYPE_USE) @interface Nullable {}',
           'android/view/ViewTreeObserver.java':'package android.view; public class ViewTreeObserver { public interface OnDrawListener {} }',
           'Probe.java':'class NotificationPermissionController {} class Probe { '+fields+' }'}
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for name,text in sources.items():
    path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
   result=subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main','-d',d]+[str(root/name) for name in sources],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
 def test_failure_has_no_partial_writes(self):
  target=next(p for p in self.src.rglob('*.java') if p.name.startswith('Tabbed'));target.write_text('bad source')
  before={p:p.read_bytes() for p in self.src.rglob('*.java')}
  with self.assertRaises(ValueError):patch.apply(self.src)
  self.assertEqual(before,{p:p.read_bytes() for p in before})
 def test_durable_before_permission_and_native_guards(self):
  staged=patch.plan(self.src);s=next(s for p,s in staged.items() if p.name.startswith('Notification'))
  m=s[s.index('public void requestSandiumPermissionAfterHomepage()'):s.index('private void notifyTrackerDismissed()')]
  self.assertLess(m.index('.commit()'),m.index('requestPermissionIfNeeded('))
  for guard in ['VERSION_CODES.TIRAMISU','isRetailDemoMode','hasPermission','canRequestPermission','shouldShowRequestPermissionRationale','wasPermissionRequestShown','NOTIFICATION_PERMISSION_REQUEST_COUNT','isOffTheRecord']:
   self.assertIn(guard,m)
  self.assertIn('if (!contextual ||',s);self.assertIn('tracker.shouldTriggerHelpUi(',s)
 def test_visible_home_commit_and_lifecycle(self):
  s=next(s for p,s in patch.plan(self.src).items() if p.name.startswith('Tabbed'))
  for guard in ['ActivityState.RESUMED','hasWindowFocus()','isUserInteractable()','isNativePage()','isNtpUrl','isOffTheRecord()','LayoutType.BROWSING','dialogs.isShowing()','isHardwareAccelerated()','registerFrameCommitCallback','homepage != tab.getView()']:
   self.assertIn(guard,s)
  self.assertNotIn('if (mNotificationPermissionController.requestPermissionIfNeeded(/* contextual= */ false))',s)
  self.assertIn('mSandiumNotificationsDestroyed = true;\n        stopSandiumNotificationDrawObserver();',s)
if __name__=='__main__':unittest.main()
