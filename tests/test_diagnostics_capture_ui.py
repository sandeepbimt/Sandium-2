"""Compile real capture bootstrap against narrow producer/recorder interfaces."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PKG = 'org/chromium/chrome/browser/sandium/diagnostics/'
SOURCE = ROOT / '.circleci/features/navigation-diagnostics/ui/SandiumDiagnosticsCapture.java'


class CaptureUi(unittest.TestCase):
    def test_capture_bootstrap_gates_private_stopped_destroyed_and_uses_unlinked_nav(self):
        if not shutil.which('java'): self.skipTest('Java runtime unavailable')
        sources = {
            PKG + 'SandiumDiagnosticsCapture.java': SOURCE.read_text(),
            'org/chromium/chrome/browser/tab/Tab.java': """
package org.chromium.chrome.browser.tab;
public class Tab {
 public boolean destroyed, incognito; public Profile profile=new Profile();
 public boolean isDestroyed(){return destroyed;}
 public boolean isIncognito(){return incognito;} public Profile getProfile(){return profile;}
 public static class Profile {
  public boolean privateMode,shutdown,ready=true;
  public boolean isOffTheRecord(){return privateMode;}
  public boolean shutdownStarted(){return shutdown;}
  public boolean isNativeInitialized(){return ready;}
 }
}""",
            'org/chromium/chrome/browser/gesturenav/NativePageBitmapCapturer.java': """
package org.chromium.chrome.browser.gesturenav;
import org.chromium.chrome.browser.tab.Tab;
public class NativePageBitmapCapturer {
 public interface SandiumOriginObserver {
  boolean isEnabled(Tab tab); void record(Tab tab,double[] values); void matrix(Tab tab,double[] values);
 }
 public static SandiumOriginObserver observer;
 public static void setSandiumOriginObserver(SandiumOriginObserver value){observer=value;}
}""",
            PKG + 'SandiumNavigationDiagnostics.java': """
package org.chromium.chrome.browser.sandium.diagnostics;
public class SandiumNavigationDiagnostics {
 public enum Event {CAPTURE,CAPTURE_LAYER,NATIVE_REVEAL_VIEW,NATIVE_REVEAL_CONTROLS}
 public static long sessionEpoch(){return enabled?1:0;}
 public static void recordForEpoch(long epoch,Event event,boolean priv,double[] v){if(priv)throw new AssertionError();}
 public static boolean enabled; public static int count;
 public static boolean isRecording(){return enabled;}
 public static void initialize(java.io.File directory){if(!directory.getName().equals("sandium-diagnostics"))throw new AssertionError();}
 public static void record(Event event,long nav,boolean privateMode,double... values) {
  if(nav!=0||privateMode)throw new AssertionError("privacy/nav");
  if(values.length!=(event==Event.CAPTURE?16:11))throw new AssertionError("arity");
  count++;
 }
}""",
            'org/chromium/chrome/browser/ntp/NewTabPage.java': """
package org.chromium.chrome.browser.ntp;
import org.chromium.chrome.browser.tab.Tab;
public class NewTabPage {
 public interface SandiumRevealObserver {long epoch(Tab t);void record(Tab t,long e,boolean c,double[] v);}
 public static SandiumRevealObserver observer;
 public static void setSandiumRevealObserver(SandiumRevealObserver o){observer=o;}
}""",
            'org/chromium/base/ContextUtils.java': """
package org.chromium.base;
public class ContextUtils {
 public static Context getApplicationContext(){return new Context();}
 public static class Context {public java.io.File getNoBackupFilesDir(){return new java.io.File("/app-private");}}
}""",
            'Harness.java': """
import org.chromium.chrome.browser.tab.Tab;
import org.chromium.chrome.browser.gesturenav.NativePageBitmapCapturer;
import org.chromium.chrome.browser.sandium.diagnostics.*;
public class Harness {
 static void check(boolean value){if(!value)throw new AssertionError();}
 public static void main(String[] args) {
  SandiumDiagnosticsCapture.install(); var observer=NativePageBitmapCapturer.observer;
  SandiumDiagnosticsCapture.install();check(observer==NativePageBitmapCapturer.observer);
  Tab tab=new Tab();check(!observer.isEnabled(tab));
  observer.record(tab,new double[16]);check(SandiumNavigationDiagnostics.count==0);
  SandiumNavigationDiagnostics.enabled=true;
  check(observer.isEnabled(tab));observer.record(tab,new double[16]);observer.matrix(tab,new double[11]);
  check(SandiumNavigationDiagnostics.count==2);
  tab.profile.privateMode=true;check(!observer.isEnabled(tab));observer.record(tab,new double[16]);
  tab.profile.privateMode=false;tab.incognito=true;check(!observer.isEnabled(tab));observer.matrix(tab,new double[11]);
  tab.incognito=false;tab.destroyed=true;check(!observer.isEnabled(tab));
  tab.destroyed=false;tab.profile.shutdown=true;check(!observer.isEnabled(tab));
  tab.profile.shutdown=false;tab.profile.ready=false;check(!observer.isEnabled(tab));
  tab.profile=null;check(!observer.isEnabled(tab));check(!observer.isEnabled(null));
  check(SandiumNavigationDiagnostics.count==2);
 }
}""",
        }
        with tempfile.TemporaryDirectory() as td:
            paths = []
            for name, source in sources.items():
                path = Path(td) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source)
                paths.append(str(path))
            compiler = ['javac'] if shutil.which('javac') else ['java', '--module', 'jdk.compiler/com.sun.tools.javac.Main']
            result = subprocess.run(compiler + paths, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run(['java', '-cp', td, 'Harness'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_activity_or_browsing_data_reference(self):
        source = SOURCE.read_text().split('public final class', 1)[1]
        for name in ('Activity', 'getUrl', 'getTitle', 'getWebContents', 'getView'):
            self.assertNotIn(name, source)


if __name__ == '__main__': unittest.main()
