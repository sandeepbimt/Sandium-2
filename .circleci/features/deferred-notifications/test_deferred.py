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
 def test_failure_has_no_partial_writes(self):
  target=next(p for p in self.src.rglob('*.java') if p.name.startswith('Tabbed'));target.write_text('bad source')
  before={p:p.read_bytes() for p in self.src.rglob('*.java')}
  with self.assertRaises(ValueError):patch.apply(self.src)
  self.assertEqual(before,{p:p.read_bytes() for p in before})
 def test_verify_read_only_with_unrelated_changes(self):
  patch.apply(self.src)
  target=next(self.src.rglob('NotificationPermissionController.java'));target.write_text(target.read_text()+'\n// unrelated overlay\n')
  before={p:p.read_bytes() for p in self.src.rglob('*.java')}
  patch.verify(self.src)
  self.assertEqual(before,{p:p.read_bytes() for p in before})
  target.write_text(target.read_text().replace('sandium_notifications','broken_notifications'))
  broken={p:p.read_bytes() for p in before}
  with self.assertRaises(ValueError):patch.verify(self.src)
  self.assertEqual(broken,{p:p.read_bytes() for p in before})
 def test_no_158_profile_constructor_or_invalid_nullable(self):
  staged=patch.plan(self.src)
  s='\n'.join(staged.values())
  self.assertNotIn('@Nullable android.',s)
  self.assertNotIn('mProfile',next(t for p,t in staged.items() if p.name.startswith('Notification')))
  self.assertNotIn('mWindowAndroid, rationaleUIDelegateSupplier, profile',s)
 def test_durable_before_permission_and_native_guards(self):
  staged=patch.plan(self.src);s=next(s for p,s in staged.items() if p.name.startswith('Notification'))
  m=s[s.index('public void requestSandiumPermissionAfterHomepage('):s.index('private void recordOsPromptShown()')]
  self.assertLess(m.index('.commit()'),m.index('requestPermissionIfNeeded('))
  for guard in ['VERSION_CODES.TIRAMISU','isRetailDemoMode','hasPermission','canRequestPermission','shouldShowRequestPermissionRationale','wasPermissionRequestShown','NOTIFICATION_PERMISSION_REQUEST_COUNT','isOffTheRecord']:
   self.assertIn(guard,m)
  self.assertIn('if (!contextual ||',s);self.assertIn('shouldRequestPermission()',s)
 def test_visible_home_commit_and_lifecycle(self):
  s=next(s for p,s in patch.plan(self.src).items() if p.name.startswith('Tabbed'))
  for guard in ['ActivityState.RESUMED','hasWindowFocus()','isUserInteractable()','isNativePage()','isNtpUrl','isOffTheRecord()','LayoutType.BROWSING','dialogs.isShowing()','isHardwareAccelerated()','registerFrameCommitCallback','homepage != tab.getView()']:
   self.assertIn(guard,s)
  self.assertNotIn('if (mNotificationPermissionController.requestPermissionIfNeeded(/* contextual= */ false))',s)
  self.assertIn('mSandiumNotificationsDestroyed = true;\n        stopSandiumNotificationDrawObserver();',s)
if __name__=='__main__':unittest.main()
