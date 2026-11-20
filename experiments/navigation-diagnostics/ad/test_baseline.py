import importlib.util,pathlib,subprocess,tempfile,unittest
P=pathlib.Path;HERE=P(__file__).parent;s=importlib.util.spec_from_file_location('baseline',HERE/'baseline.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_pinned_replay(self):
  for p,f in [(m.JAVA,m.java),(m.CPP,m.cpp)]:
   original=(HERE/'fixtures'/p).read_text();out=f(original);self.assertEqual(f(out),out)
  self.assertNotIn('WebContents',m.CPP_METHOD);self.assertNotIn('url',m.CPP_METHOD.lower())
 def test_actual_java_method_privacy_epoch_shape(self):
  with tempfile.TemporaryDirectory() as d:
   root=P(d);p=root/'Test.java';p.write_text('''class Recorder {static long epoch=1;static int rows;static long sessionEpoch(){return epoch;}static void recordNativeForEpoch(long e,int c,long n,long t,boolean priv,double[] v){if(e==epoch&&!priv){if(c!=10||n!=0||v.length!=6)throw new AssertionError();rows++;}}}
@interface Nullable {}
class Profile{boolean priv;boolean isOffTheRecord(){return priv;}}
class FilterListServiceFactoryJni {static double[] values=new double[25];static boolean restart;static boolean recording;void setSandiumAdDiagnosticsRecording(boolean value){recording=value;}static FilterListServiceFactoryJni get(){return new FilterListServiceFactoryJni();}double[] getSandiumDiagnosticLoadSnapshot(Profile p){if(restart)Recorder.epoch++;return values;}}
public class Test {
'''+m.GATE_JAVA+m.JAVA_METHOD.replace(m.REC,'Recorder')+'''static void check(boolean b){if(!b)throw new AssertionError();}public static void main(String[] a){setSandiumAdDiagnosticsRecording(true);check(FilterListServiceFactoryJni.recording);setSandiumAdDiagnosticsRecording(false);check(!FilterListServiceFactoryJni.recording);Profile p=new Profile();check(captureSandiumDiagnosticLoadSnapshot(p,1));check(Recorder.rows==4);p.priv=true;check(!captureSandiumDiagnosticLoadSnapshot(p,1));p.priv=false;check(!captureSandiumDiagnosticLoadSnapshot(null,1));check(!captureSandiumDiagnosticLoadSnapshot(p,0));FilterListServiceFactoryJni.values=new double[24];check(!captureSandiumDiagnosticLoadSnapshot(p,1));FilterListServiceFactoryJni.values=new double[25];FilterListServiceFactoryJni.values[0]=0.5;check(!captureSandiumDiagnosticLoadSnapshot(p,1));FilterListServiceFactoryJni.values[0]=Double.NaN;check(!captureSandiumDiagnosticLoadSnapshot(p,1));FilterListServiceFactoryJni.values[0]=9007199254740992.0;check(!captureSandiumDiagnosticLoadSnapshot(p,1));FilterListServiceFactoryJni.values[0]=123;FilterListServiceFactoryJni.restart=true;check(!captureSandiumDiagnosticLoadSnapshot(p,1));check(Recorder.rows==4);}}
''');subprocess.run(['java','-jar','/tmp/sandium-ecj.jar','-21','-d',d,str(p)],check=True,capture_output=True);subprocess.run(['java','-cp',d,'Test'],check=True)
 def test_actual_native_gate(self):
  with tempfile.TemporaryDirectory() as d:
   p=P(d)/'t.cc';p.write_text('''#include <vector>
#include <array>
#include <cstdint>
#include <cassert>
using JNIEnv=int;using jboolean=unsigned char;using jobject=int;using jdoubleArray=std::vector<double>;
namespace base{namespace android{template<class T>struct JavaRef{bool null=false;bool is_null()const{return null;}};template<class T>using ScopedJavaLocalRef=T;std::vector<double> ToJavaDoubleArray(JNIEnv*,const std::vector<double>& v){return v;}}struct TimeTicks{static TimeTicks Now(){return {};}TimeTicks since_origin(){return {};}int64_t InMicroseconds(){return 100;}};}
namespace content{struct BrowserThread{enum{UI};static bool ui;static bool CurrentlyOn(int){return ui;}};bool BrowserThread::ui=true;}
struct Profile{bool priv=false;static Profile* current;static Profile* FromJavaObject(const base::android::JavaRef<jobject>&){return current;}bool IsOffTheRecord(){return priv;}};Profile* Profile::current=nullptr;
struct Service{auto GetSandiumDiagnosticLoadSnapshot(){return std::array<std::array<int64_t,6>,4>{};}};struct Process{Service* service=nullptr;Service* ad_block_service(){return service;}};Process* g_brave_browser_process=nullptr;
namespace brave_shields {struct AdBlockService{static inline bool recording=false;static void SetSandiumAdDiagnosticsRecording(bool enabled){recording=enabled;}};}
'''+m.GATE_CPP+m.CPP_METHOD+'''int main(){JNI_FilterListServiceFactory_SetSandiumAdDiagnosticsRecording(nullptr,true);assert(brave_shields::AdBlockService::recording);JNI_FilterListServiceFactory_SetSandiumAdDiagnosticsRecording(nullptr,false);assert(!brave_shields::AdBlockService::recording);base::android::JavaRef<jobject> ref;auto get=[&]{return JNI_FilterListServiceFactory_GetSandiumDiagnosticLoadSnapshot(nullptr,ref);};assert(get().empty());Profile p;Profile::current=&p;Process process;g_brave_browser_process=&process;assert(get().empty());Service s;process.service=&s;assert(get().size()==25&&get()[0]==100);p.priv=true;assert(get().empty());p.priv=false;ref.null=true;assert(get().empty());ref.null=false;content::BrowserThread::ui=false;assert(get().empty());}
''');subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror',str(p),'-o',str(p.with_suffix(''))],check=True);subprocess.run([str(p.with_suffix(''))],check=True)
if __name__=='__main__':unittest.main()
