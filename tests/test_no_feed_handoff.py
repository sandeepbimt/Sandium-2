"""No-feed supplier policy uses production helper; native Android rendering not simulated."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('controls',ROOT/'.circleci/scripts/apply-sandium-back-controls.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class NoFeedHandoff(unittest.TestCase):
 def test_production_helper_and_native_callback_contract(self):
  source=(ROOT/'tests/fixtures/back-controls/NewTabPage.java').read_text()
  for relative,old,new in m.CHANGES:
   if relative.endswith('/NewTabPage.java'): source=source.replace(old,new,1)
  self.assertIn('FeedFeatures.isFeedEnabled(\n                                            mTab.getProfile())',source)
  start=source.index('    private static NonNullObservableSupplier<Integer> sandiumRestoringState(')
  end=source.index('\n    @Override',start)
  helper=source[start:end]
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)
   (p/'org/chromium/base/supplier').mkdir(parents=True)
   (p/'org/chromium/base/supplier/NonNullObservableSupplier.java').write_text('package org.chromium.base.supplier; public interface NonNullObservableSupplier<T> { T get(); }')
   (p/'org/chromium/base/supplier/ObservableSuppliers.java').write_text('package org.chromium.base.supplier; public class ObservableSuppliers { public static <T> NonNullObservableSupplier<T> createNonNull(T value) { return () -> value; } }')
   (p/'Policy.java').write_text('''import org.chromium.base.supplier.NonNullObservableSupplier;
class TraceEvent { static int count; static void instant(String name) { if (!name.equals("SandiumNtpFeedWaitSkipped")) throw new AssertionError(); count++; } }
class FeedSurfaceProvider { static class RestoringState { static final int NO_STATE_TO_RESTORE=0; } }
public class Policy {
'''+helper+'''
 public static void main(String[] args) {
  NonNullObservableSupplier<Integer> waiting = () -> 1;
  if (sandiumRestoringState(true,waiting)!=waiting || TraceEvent.count!=0) throw new AssertionError("feed-enabled path changed");
  if (sandiumRestoringState(false,waiting).get()!=0 || TraceEvent.count!=1) throw new AssertionError("no-feed must not await unavailable stream");
  NonNullObservableSupplier<Integer> restored = () -> 2;
  if (sandiumRestoringState(true,restored)!=restored) throw new AssertionError("supplier identity lost");
 }
}''')
   java=shutil.which('java');self.assertIsNotNone(java)
   subprocess.run([java,'--module','jdk.compiler/com.sun.tools.javac.Main',*[str(x) for x in p.rglob('*.java')]],check=True,capture_output=True,text=True)
   subprocess.run([java,'-cp',str(p),'Policy'],check=True,capture_output=True,text=True)
 def test_no_timeout_or_animator_change(self):
  changes=[(a,b,c) for a,b,c in m.CHANGES if '/ntp/' in a]
  self.assertEqual(len(changes),2)
  combined='\n'.join(c for _,_,c in changes)
  self.assertNotIn('postDelayed',combined)
  self.assertNotIn('setDuration',combined)
  self.assertNotIn('setAlpha',combined)
  self.assertIn('if (feedEnabled) return restoringState;',combined)

if __name__=='__main__': unittest.main()
