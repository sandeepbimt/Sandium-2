"""Compile and execute the actual independent production lease component, not a model."""
import pathlib, subprocess, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'experiments/single-handoff/components/org/chromium/chrome/browser/tab/NativePageHandoffLeaseOwner.java'
HARNESS = r'''
import org.chromium.chrome.browser.tab.NativePageHandoffLeaseOwner;
import org.chromium.chrome.browser.tab.NativePageHandoffLeaseOwner.*;
public class LeaseHarness {
 static void check(boolean value) { if (!value) throw new AssertionError(); }
 public static void main(String[] args) throws Exception {
  NativePageHandoffLeaseOwner<Object> owner = new NativePageHandoffLeaseOwner<>();
  Object first = new Object(), second = new Object(); int[] count = {0};
  Lease<Object> a = owner.acquire(first, (r, why) -> {check(r == first);count[0]++;});
  check(owner.isCurrent(a)); check(owner.release(a, EndReason.PRESENTED));
  check(!owner.release(a, EndReason.CANCELLED) && count[0] == 1);
  for(String fieldName: new String[]{"mResource", "mReleaser"}) {
   java.lang.reflect.Field field = a.getClass().getDeclaredField(fieldName);
   field.setAccessible(true);check(field.get(a) == null);
  }
  Lease<Object> b = owner.acquire(first, (r, why) -> count[0]++);
  check(!owner.release(a, EndReason.PRESENTED) && owner.isCurrent(b));
  try {owner.acquire(first, (r, why) -> {});throw new AssertionError();}
  catch (IllegalArgumentException expected) {} check(owner.isCurrent(b));
  owner.revoke(EndReason.TARGET_CHANGED);check(count[0] == 2);

  NativePageHandoffLeaseOwner<Object> reentrant = new NativePageHandoffLeaseOwner<>();
  Object[] newer = {null};
  reentrant.acquire(first, (r, why) -> {
   check(why == EndReason.SUPERSEDED);
   newer[0] = reentrant.acquire(second, (x, end) -> count[0]++);
  });
  Lease<Object> rejected = reentrant.acquire(new Object(), (r, why) -> {throw new AssertionError();});
  check(rejected == null && newer[0] != null);
  reentrant.destroy(); check(count[0] == 3);reentrant.destroy();check(count[0] == 3);
  check(reentrant.acquire(first, (r, why) -> {}) == null);

  NativePageHandoffLeaseOwner<Object> pendingAlias = new NativePageHandoffLeaseOwner<>();
  pendingAlias.acquire(first, (r, why) -> {
   try {pendingAlias.acquire(second, (x, end) -> {});throw new AssertionError();}
   catch (IllegalArgumentException expected) {}
  });
  Lease<Object> pending = pendingAlias.acquire(second, (r, why) -> {});
  check(pending != null && pendingAlias.isCurrent(pending));

  NativePageHandoffLeaseOwner<Object> emptyReentry = new NativePageHandoffLeaseOwner<>();
  emptyReentry.acquire(first, (r, why) -> emptyReentry.revoke(EndReason.CANCELLED));
  check(emptyReentry.acquire(second, (r, why) -> {throw new AssertionError();}) == null);
  NativePageHandoffLeaseOwner<Object> shutdown = new NativePageHandoffLeaseOwner<>();
  shutdown.acquire(first, (r, why) -> {
   check(why == EndReason.DESTROYED);
   try {shutdown.acquire(first, (x, end) -> {});throw new AssertionError();}
   catch (IllegalArgumentException expected) {}
   check(shutdown.acquire(second, (x, end) -> {}) == null);
  });shutdown.destroy();

  NativePageHandoffLeaseOwner<Object> reuse = new NativePageHandoffLeaseOwner<>();
  reuse.acquire(first, (r, why) -> {
   try {reuse.acquire(first, (x, end) -> {});throw new AssertionError();}
   catch (IllegalArgumentException expected) {}
  });reuse.revoke(EndReason.CANCELLED);
  check(reuse.acquire(first, (r, why) -> {}) != null);

  NativePageHandoffLeaseOwner<Object> throwing = new NativePageHandoffLeaseOwner<>();
  Lease<Object> t = throwing.acquire(first, (r, why) -> {throw new RuntimeException("cleanup");});
  try {throwing.release(t, EndReason.CANCELLED);throw new AssertionError();}
  catch (RuntimeException expected) {} check(!throwing.isCurrent(t));
  Lease<Object> replacement = throwing.acquire(second, (r, why) -> {});
  check(throwing.isCurrent(replacement));
  Throwable[] violation = {null};
  Thread wrong = new Thread(() -> {try {owner.revoke(EndReason.CANCELLED);}
    catch(Throwable e) {violation[0] = e;}});
  wrong.start();wrong.join();check(violation[0] instanceof IllegalStateException);
  for(EndReason why: EndReason.values()) {
   NativePageHandoffLeaseOwner<Object> each = new NativePageHandoffLeaseOwner<>();
   int[] releases = {0};
   Lease<Object> token = each.acquire(first, (r, reason) -> {check(reason == why); releases[0]++;});
   each.revoke(why);each.revoke(why);check(releases[0] == 1 && !each.isCurrent(token));
  }
  System.out.println("LEASE_LIFETIME_REGRESSIONS=PASS");
 }
}
'''
class LeaseTests(unittest.TestCase):
 def test_actual_component(self):
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory);(root/'LeaseHarness.java').write_text(HARNESS)
   subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main','-Xlint:all','-Werror','-d',str(root),str(SOURCE),str(root/'LeaseHarness.java')],check=True,capture_output=True,text=True)
   result=subprocess.run(['java','-cp',str(root),'LeaseHarness'],check=True,capture_output=True,text=True)
   self.assertIn('LEASE_LIFETIME_REGRESSIONS=PASS',result.stdout)
 def test_pending_alias_regression_rejects_old_behavior(self):
  old = SOURCE.read_text().replace('\n                || mAcquiring.containsKey(resource)', '')
  self.assertNotEqual(old, SOURCE.read_text())
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory)
   source=root/'NativePageHandoffLeaseOwner.java';source.write_text(old)
   (root/'LeaseHarness.java').write_text(HARNESS)
   subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main','-Xlint:all','-Werror','-d',str(root),str(source),str(root/'LeaseHarness.java')],check=True,capture_output=True,text=True)
   result=subprocess.run(['java','-cp',str(root),'LeaseHarness'],capture_output=True,text=True)
   self.assertNotEqual(result.returncode, 0)
   self.assertIn('AssertionError',result.stderr)
