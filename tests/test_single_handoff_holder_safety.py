import gzip,json,importlib.util,pathlib,tempfile,subprocess,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];HERE=ROOT/'experiments/single-handoff'
s=importlib.util.spec_from_file_location('safety',HERE/'holder_safety.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Safety(unittest.TestCase):
 def test_pinned_composition(self):
  f=json.loads(gzip.decompress((HERE/'fixtures/native-holder.json.gz').read_bytes()))['files']
  for p in (m.HOLDER,m.ACTIVITY):
   out=m.transform(p,f[p]['source']);self.assertEqual(m.transform(p,out),out)
  self.assertIn('if (isTablet()) {\n                ChromeAccessibilityUtil.get().addObserver(mCompositorViewHolder);',m.transform(m.ACTIVITY,f[m.ACTIVITY]['source']))
 def test_actual_safety_methods(self):
  files={
   'org/chromium/base/ThreadUtils.java':'package org.chromium.base;public class ThreadUtils {public static void assertOnUiThread(){}}',
   'org/chromium/chrome/browser/util/ChromeAccessibilityUtil.java':'''package org.chromium.chrome.browser.util;import org.chromium.ui.util.AccessibilityUtil;public class ChromeAccessibilityUtil {static final ChromeAccessibilityUtil one=new ChromeAccessibilityUtil();public static ChromeAccessibilityUtil get(){return one;}public boolean enabled;public int adds,removes;public AccessibilityUtil.Observer current;public void addObserver(AccessibilityUtil.Observer o){adds++;current=o;o.onAccessibilityModeChanged(enabled);}public void removeObserver(AccessibilityUtil.Observer o){if(current!=o)throw new AssertionError();removes++;current=null;}}''',
   'org/chromium/ui/util/AccessibilityUtil.java':'package org.chromium.ui.util;public class AccessibilityUtil {public interface Observer{void onAccessibilityModeChanged(boolean e);}}',
   'Harness.java':'''import org.chromium.ui.util.AccessibilityUtil;import org.chromium.chrome.browser.util.ChromeAccessibilityUtil;@interface Nullable {} public class Harness {'''+m.FIELDS+m.METHODS+'''
void obscure(boolean b){mSandiumObscuringKnown=true;mSandiumObscured=b;if(b)notifySandiumUnsafe();}
static void check(boolean b){if(!b)throw new AssertionError();}
public static void main(String[]a){Harness h=new Harness();int[] releases={0};h.mSandiumUnsafeCallback=()->releases[0]++;check(!h.isSandiumNativeHandoffUiSafe());h.installSandiumNativeHandoffSafety(()->true);check(h.mSandiumA11yKnown);check(!h.isSandiumNativeHandoffUiSafe());h.obscure(false);check(h.isSandiumNativeHandoffUiSafe());ChromeAccessibilityUtil.get().current.onAccessibilityModeChanged(true);check(!h.isSandiumNativeHandoffUiSafe());ChromeAccessibilityUtil.get().current.onAccessibilityModeChanged(false);check(h.isSandiumNativeHandoffUiSafe());h.obscure(true);check(!h.isSandiumNativeHandoffUiSafe());h.obscure(false);h.installSandiumNativeHandoffSafety(()->{h.obscure(true);return true;});check(!h.isSandiumNativeHandoffUiSafe());h.obscure(false);h.installSandiumNativeHandoffSafety(()->{h.closeSandiumNativeHandoffSafety();return true;});check(!h.isSandiumNativeHandoffUiSafe());check(ChromeAccessibilityUtil.get().adds==1&&ChromeAccessibilityUtil.get().removes==1);h.closeSandiumNativeHandoffSafety();h.installSandiumNativeHandoffSafety(()->true);check(ChromeAccessibilityUtil.get().adds==1);check(releases[0]>0);System.out.println("SAFETY=PASS");}}
'''}
  with tempfile.TemporaryDirectory() as d:
   paths=[]
   for p,v in files.items():
    q=pathlib.Path(d)/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(v);paths.append(str(q))
   r=subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main','-d',d]+paths,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
   r=subprocess.run(['java','-cp',d,'Harness'],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);self.assertIn('SAFETY=PASS',r.stdout)
