import importlib.util,json,hashlib,tempfile,unittest,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('toolbar',ROOT/'experiments/native-toolbar/adapter.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Toolbar(unittest.TestCase):
 def test_exact_native_source_retained_except_paint(self):
  for path in (m.PHONE,m.PROGRESS):
   original=(m.HERE/'fixtures'/Path(path).name).read_text();out=m.transform(path,original)
   if path==m.PHONE:out=out.replace(m.PAINT,'').replace('getProgressBar().setRawSandiumPhoneThemeColor(', 'getProgressBar().setThemeColor(')
   else:out=out.replace(m.METHOD,'').replace('            applyRawSandiumPhonePalette(color, isIncognito);\n','').replace('        applyRawSandiumPhonePalette(color, isIncognito);\n','')
   self.assertEqual(original,out)
 def test_preflight_all_files_before_any_write_replay_and_drift(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   for path in (m.PHONE,m.PROGRESS):
    p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text((m.HERE/'fixtures'/Path(path).name).read_text())
   planned=m.plan(root)
   for p,t in planned.items():p.write_text(t)
   self.assertEqual(planned,m.plan(root))
   (root/m.PROGRESS).write_text('unreviewed')
   with self.assertRaises(ValueError):m.plan(root)
 def test_native_control_contract_and_provenance(self):
  manifest=json.loads((m.HERE/'provenance.json').read_text())
  for name,digest in manifest['sha256'].items():
   self.assertEqual(hashlib.sha256((m.HERE/'fixtures'/name).read_bytes()).hexdigest(),digest)
  features=(m.HERE/'fixtures/AdaptiveToolbarFeatures.java').read_text()
  self.assertIn('DeviceFormFactor.isNonMultiDisplayContextOnTablet(context) || isBottomBarEnabled',features)
  self.assertIn(': AdaptiveToolbarButtonVariant.NEW_TAB;',features)
  controller=(m.HERE/'fixtures/AdaptiveToolbarButtonController.java').read_text()
  self.assertIn('receivedButtonData.canShow() && shouldButtonShowBasedOnScreenWidth()',controller)
  self.assertIn('boolean forward();',(m.HERE/'fixtures/ToolbarTabController.java').read_text())
  self.assertNotIn('setOnClickListener',m.PAINT+m.METHOD)
  self.assertNotIn('setVisibility',m.PAINT+m.METHOD)
 def test_java_paint_gates(self):
  code='''class Color {static final int TRANSPARENT=0; static int alpha(int c){return c>>>24;}static int red(int c){return(c>>16)&255;}static int green(int c){return(c>>8)&255;}static int blue(int c){return c&255;}static int argb(int a,int r,int g,int b){return a<<24|r<<16|g<<8|b;}}
class ColorUtils {static boolean shouldUseLightForegroundOnBackground(int c){return Color.red(c)<128;}}
class ChromeFeatureList {static ChromeFeatureList sAndroidProgressBarVisualUpdate=new ChromeFeatureList();boolean isEnabled(){return true;}}
public class Harness {boolean focused,incognito,ntp;float expansion;int mVisualState;float getExpansionFractionForVisualState(int s){return focused?1f:expansion;}int foreground,background,gap;boolean urlHasFocus(){return focused;}boolean isIncognitoBranded(){return incognito;}boolean isLocationBarShownInNtp(){return ntp;}
int paint(int color){'''+m.PAINT+'''return color;}
void setThemeColor(int c,boolean i){foreground=123;background=234;gap=345;applyRawSandiumPhonePalette(c,i);}void setForegroundColor(int c){foreground=c;}void setBackgroundColor(int c){background=c;}void setProgressGapBackgroundColor(int c){gap=c;}
'''+m.METHOD+'''public static void main(String[] args){Harness h=new Harness();if(h.paint(0xff212121)!=0xff292929)throw new AssertionError();for(int c:new int[]{0xffeeeeee,0xff124122})if(h.paint(c)!=c)throw new AssertionError();h.expansion=0.5f;if(h.paint(0xff212121)!=0xff252525)throw new AssertionError();h.expansion=0;h.focused=true;if(h.paint(0xff212121)!=0xff212121)throw new AssertionError();h.focused=false;h.incognito=true;if(h.paint(0xff212121)!=0xff212121)throw new AssertionError();h.incognito=false;h.ntp=true;if(h.paint(0xff212121)!=0xff212121)throw new AssertionError();h.setRawSandiumPhoneThemeColor(0xff212121,false);if(h.foreground!=0xffe8e6df||h.background!=0||h.gap!=0)throw new AssertionError();h.setThemeColor(0xff212121,false);if(h.foreground!=0xffe8e6df)throw new AssertionError();h.setRawSandiumPhoneThemeColor(0xffeeeeee,false);if(h.foreground!=123)throw new AssertionError();h.setRawSandiumPhoneThemeColor(0xff212121,true);if(h.foreground!=123)throw new AssertionError();}}
'''
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'Harness.java';p.write_text(code)
   subprocess.run(['java','com.sun.tools.javac.Main','-d',td,str(p)],check=True);subprocess.run(['java','-cp',td,'Harness'],check=True)
if __name__=='__main__':unittest.main()
