"""Regression for #1333's warning-as-error checks; not a replacement for Android CI."""
import pathlib,re,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
JAVA=ROOT/'java/org/chromium/chrome/browser/sandium/diagnostics/SandiumNavigationDiagnostics.java'
class CompileContract(unittest.TestCase):
 def test_no_known_errorprone_patterns(self):
  repo=ROOT.parents[1]
  source=JAVA.read_text() + '\n'.join(p.read_text() for p in (repo/'.circleci/features/navigation-diagnostics/ui').glob('*.java'))
  self.assertNotRegex(source,r'import [^;]+\.\*;')
  self.assertNotIn('public static synchronized',source)
  self.assertNotIn('.ordinal()',source)
  self.assertNotRegex(source,r'(?:private(?: static)?|final) (?:int|long|File|Preference|boolean) \w+,')
 def test_wire_codes_preserve_original_journal_and_native_abi(self):
  source=JAVA.read_text().split('public enum Event {',1)[1].split('final int code;',1)[0]
  codes=re.findall(r'([A-Z_]+)\((\d+), (\d+)\)',source)
  self.assertEqual([int(code) for _,code,_ in codes],list(range(30)))
  self.assertEqual(codes[0],('NAV_START','0','5'))
  self.assertEqual(codes[-1],('NATIVE_REVEAL_CONTROLS','29','10'))
 def test_same_class_monitor_excludes_concurrent_start(self):
  with tempfile.TemporaryDirectory() as tmp:
   tmp=pathlib.Path(tmp)
   main=tmp/'MonitorHarness.java'
   main.write_text('''import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import org.chromium.chrome.browser.sandium.diagnostics.SandiumNavigationDiagnostics;
public class MonitorHarness {
 public static void main(String[] args) throws Exception {
  CountDownLatch entered = new CountDownLatch(1);
  CountDownLatch done = new CountDownLatch(1);
  Thread thread = new Thread(() -> { entered.countDown(); SandiumNavigationDiagnostics.start(); done.countDown(); });
  synchronized (SandiumNavigationDiagnostics.class) {
   thread.start(); entered.await();
   if (done.await(100, TimeUnit.MILLISECONDS)) throw new AssertionError("class monitor lost");
  }
  if (!done.await(5, TimeUnit.SECONDS)) throw new AssertionError("monitor not released");
  thread.join();
  if (!SandiumNavigationDiagnostics.isRecording()) throw new AssertionError("start did not finish");
  SandiumNavigationDiagnostics.stop();
 }
}''')
   subprocess.run(['java','-jar','/tmp/sandium-ecj.jar','-21','-d',str(tmp),str(JAVA),str(main)],check=True,capture_output=True)
   subprocess.run(['java','-cp',str(tmp),'MonitorHarness'],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
