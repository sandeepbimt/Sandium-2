import importlib.util,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('menu_bridge',ROOT/'apply-menu.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_pinned_transform_and_callback_privacy_lifetime(self):
  source=(ROOT.parents[1]/'tests/fixtures/rewards-removal/android/java/org/chromium/chrome/browser/tabbed_mode/BraveTabbedAppMenuPropertiesDelegate.java').resolve().read_text()
  self.assertEqual(m.transform(source),m.transform(m.transform(source)))
  body=m.NEW[len(m.OLD):].replace(m.REC,'Recorder').replace('org.chromium.chrome.browser.ui.appmenu.SandiumMenuMetadata','Metadata')
  code='''class Profile {boolean priv; boolean isOffTheRecord(){return priv;}}
class Tab {Profile profile=new Profile();boolean destroyed;Profile getProfile(){return profile;}boolean isDestroyed(){return destroyed;}}
class Provider {Tab tab;Tab get(){return tab;}}
class Metadata {interface Sink{void record(int e,double[] v);}static Sink sink;static void diagnostics(Object m,Sink s){sink=s;}}
class Recorder {enum Event {A,B,C,D,E,F,G,H,I,J,K,L,M,N,O,P,MENU_READ,MENU_SAVE,MENU_RENDER}static boolean active=true;static int calls;static boolean isRecording(){return active;}static void record(Event e,long id,boolean p,double[] v){if(p)throw new AssertionError();calls++;}}
public class Harness {Provider mActivityTabProvider=new Provider();void install(){Object modelList=new Object();'''+body+'''}
static void eq(int a,int b){if(a!=b)throw new AssertionError(a+" != "+b);}
public static void main(String[] args){Harness h=new Harness();h.install();if(Metadata.sink!=null)throw new AssertionError();
Tab tab=new Tab();h.mActivityTabProvider.tab=tab;tab.profile.priv=true;h.install();if(Metadata.sink!=null)throw new AssertionError();
tab.profile.priv=false;h.install();Metadata.sink.record(16,new double[5]);eq(1,Recorder.calls);
Metadata.sink.record(15,new double[5]);Metadata.sink.record(19,new double[5]);eq(1,Recorder.calls);
Recorder.active=false;Metadata.sink.record(16,new double[5]);eq(1,Recorder.calls);Recorder.active=true;
h.mActivityTabProvider.tab=new Tab();Metadata.sink.record(16,new double[5]);eq(1,Recorder.calls);h.mActivityTabProvider.tab=tab;
tab.destroyed=true;Metadata.sink.record(16,new double[5]);eq(1,Recorder.calls);tab.destroyed=false;
tab.profile.priv=true;Metadata.sink.record(16,new double[5]);eq(1,Recorder.calls);
tab.profile=null;Metadata.sink.record(16,new double[5]);eq(1,Recorder.calls);
Metadata.sink=null;h.install();if(Metadata.sink!=null)throw new AssertionError();
}}
'''
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/'Harness.java';p.write_text(code)
   subprocess.run(['java','com.sun.tools.javac.Main','-d',td,str(p)],check=True,capture_output=True)
   subprocess.run(['java','-cp',td,'Harness'],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
