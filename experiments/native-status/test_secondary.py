from pathlib import Path
import unittest
import secondary
import cleanup
HERE=Path(__file__).parent
class SecondaryOwners(unittest.TestCase):
 def test_exact_owner_hooks_are_reversible_and_no_inset_writer(self):
  for name in ('BookmarkActivity.java','HistoryActivity.java','WelcomeOnboardingActivity.java'):
   raw=(HERE/'fixtures'/name).read_text();out=secondary.transform(name,raw)
   self.assertEqual(out,secondary.transform(name,out))
   self.assertEqual(raw,cleanup.undo_brave(lambda s:secondary.transform(name,s),out))
   for token in ('setPadding(', 'setOnApplyWindowInsetsListener(', 'setSystemUiVisibility(', 'setDecorFitsSystemWindows(', 'setContentView('):
    self.assertEqual(raw.count(token),out.count(token),token)
   self.assertIn('if (sandiumNativeScreenProtection()) ensureEdgeToEdgeLayoutCoordinator()',out)
   self.assertIn('return super.createSystemBarColorHelperSupplier()',out)
 def test_bookmark_scrim_owner_is_unchanged(self):
  raw=(HERE/'fixtures/BookmarkActivity.java').read_text();out=secondary.transform('BookmarkActivity.java',raw)
  start=raw.index('    private void applyScrimToStatusBar(')
  end=raw.index('    private int getEdgeToEdgeInset()',start)
  self.assertIn(raw[start:end],out)
  self.assertEqual(out.count('this::applyScrimToStatusBar'),1)
 def test_history_scrim_subscription_is_scoped_and_removed(self):
  out=secondary.transform('HistoryActivity.java',(HERE/'fixtures/HistoryActivity.java').read_text())
  self.assertIn('ColorUtils.overlayColor(base, scrimColor)',out)
  self.assertIn('if (!sandiumNativeScreenProtection()) return',out)
  self.assertEqual(out.count('addSyncObserverAndPostIfNonNull(mSandiumNativeScrimObserver)'),1)
  self.assertEqual(out.count('removeObserver(mSandiumNativeScrimObserver)'),1)
  destroy=out[out.index('    protected void onDestroy()'):]
  self.assertLess(destroy.index('removeObserver'),destroy.index('super.onDestroy()'))
 def test_welcome_inherits_the_same_owner_without_manual_insets(self):
  for name in ('FirstRunActivityBase.java','AsyncInitializationActivity.java','FullscreenSigninAndHistorySyncActivityBase.java'):
   source=(HERE/'fixtures'/name).read_text()
   self.assertNotIn('wrapContentWithEdgeToEdgeLayout()',source)
   self.assertNotIn('setOnApplyWindowInsetsListener(',source)
  raw=(HERE/'fixtures/WelcomeOnboardingActivity.java').read_text()
  out=secondary.transform('WelcomeOnboardingActivity.java',raw)
  self.assertIn('helper.setStatusBarColor(android.graphics.Color.BLACK)',out)
  self.assertEqual(raw.count('onInitialLayoutInflationComplete()'),out.count('onInitialLayoutInflationComplete()'))
 def test_pinned_base_initializes_insets_before_owner_supplier(self):
  source=(HERE/'fixtures/ChromeBaseAppCompatActivity.java').read_text()
  self.assertLess(source.index('mInsetObserver = createInsetObserver()'),source.index('createSystemBarColorHelperSupplier(),'))
  self.assertIn('mSystemBarColorHelperSupplier.set(mEdgeToEdgeLayoutCoordinator)',source)
  self.assertIn('ensureEdgeToEdgeLayoutCoordinator().wrapContentView(view)',source)
if __name__=='__main__':unittest.main()
