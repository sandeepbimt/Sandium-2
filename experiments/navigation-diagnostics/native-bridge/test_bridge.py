import importlib.util,pathlib,subprocess,tempfile,unittest
P=pathlib.Path;HERE=P(__file__).parent;ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('bridge',HERE/'apply.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def fixture(path):
 for prefix in ['.circleci/features/dark-pages/renderer/fixtures','tests/fixtures/dark-pages']:
  p=ROOT/prefix/path
  if p.is_file():return p.read_text()
 raise ValueError(path)
def inserted(fn,anchor):
 out=fn(anchor)
 return out[:out.index(anchor)]
class Tests(unittest.TestCase):
 def test_pinned_anchors_replay_and_numeric_boundary(self):
  for path,fn in m.TRANSFORMS.items():
   source=fixture(path);out=fn(source)
   self.assertEqual(out,fn(out),path)
  java=m.java(fixture(m.JAVA));extra=java[java.index('// '+m.MARK):]
  self.assertNotIn('getUrl',extra);self.assertNotIn('getTitle',extra);self.assertNotIn('String ',extra)
  self.assertIn('Profile.fromWebContents',extra);self.assertIn('profile.isOffTheRecord()',extra)
 def test_browser_gate_actual_bodies(self):
  code=inserted(m.chrome_cc,'bool ChromeContentBrowserClient::OverrideWebPreferencesAfterNavigation(')
  with tempfile.TemporaryDirectory() as d:
   p=P(d)/'t.cc';p.write_text('''#include <vector>
#include <cstdint>
#include <cassert>
#define BUILDFLAG(x) 1
struct Context{bool priv=false;bool IsOffTheRecord(){return priv;}};
struct WebContents{Context context;Context* GetBrowserContext(){return &context;}};
struct BrowserThread{enum ID{UI};static inline bool ui=true;static bool CurrentlyOn(ID){return ui;}};
namespace night_mode {struct WebContentsThemeClient{static inline bool active=false;static inline int calls=0;static inline int64_t id=0, time=0, epoch=3;static bool IsSandiumNavigationDiagnosticsEnabled(WebContents*){return active;}static int64_t GetSandiumNavigationDiagnosticsEpoch(WebContents*){return active?epoch:0;}static void RecordSandiumNavigationDiagnosticForEpoch(WebContents*,int64_t e,int,int64_t n,int64_t t,const std::vector<double>&){if(e==epoch){calls++;id=n;time=t;}}static void RecordSandiumNavigationDiagnostic(WebContents*,int,int64_t n,int64_t t,const std::vector<double>&){calls++;id=n;time=t;}};}
class ChromeContentBrowserClient{public:bool IsSandiumNavigationDiagnosticsEnabled(WebContents*);int64_t GetSandiumNavigationDiagnosticsEpoch(WebContents*);void RecordSandiumNavigationDiagnosticForEpoch(WebContents*,int64_t,int,int64_t,int64_t,const std::vector<double>&);void RecordSandiumNavigationDiagnostic(WebContents*,int,int64_t,int64_t,const std::vector<double>&);};
'''+code+'''int main(){ChromeContentBrowserClient c;WebContents w;using T=night_mode::WebContentsThemeClient;
assert(!c.IsSandiumNavigationDiagnosticsEnabled(nullptr));c.RecordSandiumNavigationDiagnostic(&w,1,42,99,{1});assert(T::calls==0);
T::active=true;w.context.priv=true;c.RecordSandiumNavigationDiagnostic(&w,1,42,99,{1});assert(T::calls==0);w.context.priv=false;
BrowserThread::ui=false;c.RecordSandiumNavigationDiagnostic(reinterpret_cast<WebContents*>(1),1,42,99,{1});assert(T::calls==0);BrowserThread::ui=true;
c.RecordSandiumNavigationDiagnostic(&w,1,42,99,std::vector<double>(17));assert(T::calls==0);
c.RecordSandiumNavigationDiagnostic(&w,1,-1,99,{1});assert(T::calls==0);c.RecordSandiumNavigationDiagnostic(&w,1,42,-1,{1});assert(T::calls==0);
c.RecordSandiumNavigationDiagnostic(&w,1,42,99,{1,2});assert(T::calls==1&&T::id==42&&T::time==99);
assert(c.GetSandiumNavigationDiagnosticsEpoch(&w)==3);c.RecordSandiumNavigationDiagnosticForEpoch(&w,2,1,42,99,{1});assert(T::calls==1);c.RecordSandiumNavigationDiagnosticForEpoch(&w,3,1,42,99,{1});assert(T::calls==2);T::active=false;assert(c.GetSandiumNavigationDiagnosticsEpoch(&w)==0);}

''')
   subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror',str(p),'-o',str(p.with_suffix(''))],check=True);subprocess.run([str(p.with_suffix(''))],check=True)
 def test_java_facade_actual_methods(self):
  extra=m.java('class Dummy {\n}\n');extra=extra[extra.index('    // '+m.MARK):];extra=extra[:extra.rfind('}')]
  extra=extra.replace('@CalledByNative','').replace('@JniType("content::WebContents*") ','')
  extra=extra.replace(m.REC,'Recorder').replace('org.chromium.base.ContextUtils','ContextUtils')
  with tempfile.TemporaryDirectory() as d:
   p=P(d)/'Harness.java';p.write_text('''class WebContents{Profile profile;}
class Profile {boolean priv;static Profile fromWebContents(WebContents w){return w.profile;}boolean isOffTheRecord(){return priv;}}
class ContextUtils {static ContextUtils getApplicationContext(){return new ContextUtils();}java.io.File getNoBackupFilesDir(){return new java.io.File("/tmp");}}
class Recorder {static void initialize(java.io.File f){}static boolean active;static int calls;static long id,time,epoch=3;static long sessionEpoch(){return active?epoch:0;}static void recordNativeForEpoch(long e,int code,long n,long t,boolean p,double[] v){if(e==sessionEpoch())recordNative(code,n,t,p,v);}static boolean isRecording(){return active;}static void recordNative(int code,long n,long t,boolean p,double[] v){if(p)throw new AssertionError();calls++;id=n;time=t;}}
public class Harness {'''+extra+'''public static void main(String[] a){WebContents w=new WebContents();if(sandiumNavigationDiagnosticsEnabled(null))throw new AssertionError();recordSandiumNavigationDiagnostic(null,1,42,99,new double[]{1});recordSandiumNavigationDiagnostic(w,1,42,99,new double[]{1});if(Recorder.calls!=0)throw new AssertionError();w.profile=new Profile();w.profile.priv=true;recordSandiumNavigationDiagnostic(w,1,42,99,new double[]{1});if(Recorder.calls!=0)throw new AssertionError();w.profile.priv=false;Recorder.active=true;if(!sandiumNavigationDiagnosticsEnabled(w))throw new AssertionError();recordSandiumNavigationDiagnostic(w,1,42,99,new double[]{1});if(Recorder.calls!=1||Recorder.id!=42||Recorder.time!=99)throw new AssertionError();if(sandiumNavigationDiagnosticsEpoch(w)!=3)throw new AssertionError();recordSandiumNavigationDiagnosticForEpoch(w,2,1,42,99,new double[]{1});if(Recorder.calls!=1)throw new AssertionError();recordSandiumNavigationDiagnosticForEpoch(w,3,1,42,99,new double[]{1});if(Recorder.calls!=2)throw new AssertionError();Recorder.active=false;if(sandiumNavigationDiagnosticsEpoch(w)!=0)throw new AssertionError();}}
''')
   subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main','-d',d,str(p)],check=True);subprocess.run(['java','-cp',d,'Harness'],check=True)
 def test_plan_failure_writes_nothing(self):
  with tempfile.TemporaryDirectory() as d:
   src=P(d)
   for path in m.TRANSFORMS:
    p=src/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(fixture(path))
   (src/m.BUILD).write_text('last owner broken')
   before={p:p.read_bytes() for p in src.rglob('*') if p.is_file()}
   with self.assertRaises(ValueError):m.plan(src,src/'unused')
   self.assertEqual(before,{p:p.read_bytes() for p in src.rglob('*') if p.is_file()})
if __name__=='__main__':unittest.main()
