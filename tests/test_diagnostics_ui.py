"""Native preference composition and executable export/lifecycle contract tests."""
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FEATURE = ROOT / '.circleci/features/navigation-diagnostics/ui'
VIEW = FEATURE / 'SandiumDiagnosticsPreferences.java'


def method(source, signature):
    start = source.index(signature)
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        if source[end] == '{': depth += 1
        if source[end] == '}': depth -= 1
        end += 1
    return source[start:end]


class DiagnosticsUi(unittest.TestCase):
    def test_pinned_main_settings_idempotence_and_source_ownership(self):
        api = runpy.run_path(str(FEATURE / 'apply-ui.py'))
        source = (ROOT / 'tests/fixtures/settings/BraveMainPreferencesBase.java').read_text()
        updated = api['main_settings'](source)
        self.assertEqual(updated, api['main_settings'](updated))
        self.assertEqual(updated.count('setKey("sandium_navigation_diagnostics")'), 1)
        self.assertIn('R.drawable.ic_bar_chart', updated)
        self.assertEqual(updated.replace(api['BLOCK'], ''), source)
        for invalid in ('', source + api['ANCHOR']):
            with self.assertRaises(ValueError): api['main_settings'](invalid)
        sources = 'brave_java_sources = [\n  "existing.java",\n]\n'
        result = api['java_sources'](sources)
        self.assertEqual(result, api['java_sources'](result))
        self.assertIn('"existing.java"', result)
        self.assertNotIn('SandiumNavigationDiagnostics.java', result)
        self.assertIn('SandiumDiagnosticsCapture.java', result)
        constructor = '    public static TabWebContentsObserver from(Tab tab) {\n        return new TabWebContentsObserver(tab);\n    }'
        bootstrapped = api['tab_bootstrap'](constructor)
        self.assertEqual(bootstrapped, api['tab_bootstrap'](bootstrapped))
        self.assertLess(bootstrapped.index('Capture.install()'), bootstrapped.index('new TabWebContentsObserver'))

    def test_privacy_and_lifecycle_surface(self):
        source = VIEW.read_text()
        for absent in ('READ_EXTERNAL_STORAGE', 'WRITE_EXTERNAL_STORAGE', 'getUrl(', 'logcat',
                       'takePersistableUriPermission', 'putString(', 'android.util.Log'):
            # logcat appears only in the explicit class comment.
            self.assertNotIn(absent, source.split('public class', 1)[1])
        for present in ('!getProfile().isOffTheRecord()', 'mPendingExport = null',
                        'mFiles.shutdown()', 'mMain.removeCallbacks(mRefresh)',
                        'SandiumNavigationDiagnostics::markAdWarning',
                        'not automatic detection', '2 minutes or 5,000 events'):
            self.assertIn(present, source)
        choose = method(source, 'private void chooseExport()')
        self.assertLess(choose.index('stop()'), choose.index('snapshotJson()'))
        self.assertLess(choose.index('snapshotJson()'), choose.index('startActivityForResult'))
        self.assertNotIn('SandiumNavigationDiagnostics.clear()', source)
        self.assertNotIn('SandiumNavigationDiagnostics.start()', method(source, 'public void onResume()'))
        self.assertIn('captureSandiumDiagnosticLoadSnapshot(', source)
        self.assertIn('getProfile(), SandiumNavigationDiagnostics.sessionEpoch()', source)
        self.assertIn('the ad-engine load baseline is unavailable', source)
        self.assertNotIn('ad-engine load failed', source)

    def test_export_dispatch_and_failure_paths(self):
        if not shutil.which('java'): self.skipTest('Java runtime unavailable')
        source = VIEW.read_text()
        methods = '\n'.join(method(source, signature) for signature in (
            'private void chooseExport()', 'public void onActivityResult(',
            'private boolean usable()', 'private void message('))
        code = r"""
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
class Parent { public void onActivityResult(int a,int b,Intent c){} }
class Activity { static final int RESULT_OK=1; }
class Uri { String scheme; Uri(String s){scheme=s;} String getScheme(){return scheme;} }
class Intent {
 static final String ACTION_CREATE_DOCUMENT="create",CATEGORY_OPENABLE="open",EXTRA_TITLE="title";
 Uri uri; Intent(String s){} Intent addCategory(String s){return this;} Intent setType(String s){return this;}
 Intent putExtra(String k,String v){return this;} Uri getData(){return uri;}
}
class Profile { boolean privateMode, shutdown; boolean isNativeInitialized(){return true;}
 boolean shutdownStarted(){return shutdown;} boolean isOffTheRecord(){return privateMode;} }
class ContentResolver {
 int writes; boolean fail; java.io.ByteArrayOutputStream bytes;
 OutputStream openOutputStream(Uri u,String mode) throws Exception {
  writes++; if(!mode.equals("wt"))throw new AssertionError();
  if(fail)throw new java.io.IOException(); bytes=new java.io.ByteArrayOutputStream();return bytes;
 }
}
class Context { ContentResolver resolver=new ContentResolver(); ContentResolver getContentResolver(){return resolver;} }
class Toast { static final int LENGTH_LONG=1; static String last;
 static Toast makeText(Context c,String s,int l){last=s;return new Toast();} void show(){} }
class SandiumNavigationDiagnostics {
 static boolean recording=true; static int stops; static String snapshot="{\"events\":[]}";
 static void stop(){recording=false;stops++;} static String snapshotJson(){if(recording)throw new AssertionError();return snapshot;}
}
public class DiagnosticsHarness extends Parent {
 static final int EXPORT=9461; boolean mBusy,mDestroyed,chooserFails; String mPendingExport;
 Profile profile=new Profile(); Context context=new Context(); int chooserCount;
 static class Queue {void execute(Runnable r){r.run();} void post(Runnable r){r.run();}}
 Queue mMain=new Queue(),mFiles=new Queue();
 Object getActivity(){return new Object();} Profile getProfile(){return profile;} Context requireContext(){return context;}
 void refresh(){}
 void startActivityForResult(Intent i,int n){if(chooserFails)throw new android.content.ActivityNotFoundException();chooserCount++;}
 """ + methods + r"""
 static void check(boolean value){if(!value)throw new AssertionError();}
 static Intent result(String scheme){Intent i=new Intent("");i.uri=new Uri(scheme);return i;}
 public static void main(String[] args){
  DiagnosticsHarness h=new DiagnosticsHarness();h.chooseExport();check(h.mBusy&&h.chooserCount==1);
  h.onActivityResult(EXPORT,0,null);check(!h.mBusy&&h.mPendingExport==null&&h.context.resolver.writes==0);
  h.chooseExport();h.onActivityResult(EXPORT,1,result("file"));check(h.context.resolver.writes==0);
  h.chooseExport();h.onActivityResult(EXPORT,1,null);check(h.context.resolver.writes==0);
  h.chooseExport();h.profile.privateMode=true;h.onActivityResult(EXPORT,1,result("content"));check(h.context.resolver.writes==0);
  h.profile.privateMode=false;h.chooseExport();h.onActivityResult(EXPORT,1,result("content"));
  check(h.context.resolver.writes==1&&!h.mBusy&&Toast.last.equals("Recording saved."));
  check(h.context.resolver.bytes.toString().equals(SandiumNavigationDiagnostics.snapshot));
  h.onActivityResult(EXPORT,1,result("content"));check(h.context.resolver.writes==1);
  h.chooseExport();h.context.resolver.fail=true;h.onActivityResult(EXPORT,1,result("content"));
  check(!h.mBusy&&Toast.last.contains("partial file"));
  h.chooserFails=true;h.chooseExport();check(!h.mBusy&&h.mPendingExport==null);
  h.mDestroyed=true;check(!h.usable());
 }
}"""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            java = path / 'DiagnosticsHarness.java'
            java.write_text(code)
            stub = path / 'android/content/ActivityNotFoundException.java'
            stub.parent.mkdir(parents=True)
            stub.write_text('package android.content; public class ActivityNotFoundException extends RuntimeException {}')
            compiler = ['javac'] if shutil.which('javac') else ['java', '--module', 'jdk.compiler/com.sun.tools.javac.Main']
            result = subprocess.run(compiler + [str(java), str(stub)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run(['java', '-cp', td, 'DiagnosticsHarness'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__': unittest.main()
