"""Execute exact shared paint callbacks against a small synchronous observer host."""
import importlib.util,json,shutil,subprocess,tempfile,unittest,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def extract(s,name):
 match=re.search(r'(?m)^    (?:private|protected|public) (?:@ColorInt )?void '+name+r'\(',s);a=match.start();o=s.index('{',match.end());end=o+1;depth=1
 while depth:depth+=(s[end]=='{')-(s[end]=='}');end+=1
 return s[a:end].replace('@ColorInt ','').replace('@Nullable ','').replace('@Override','').replace('android.view.ViewParent','Parent').replace('android.view.View','View')
class PaintLoop(unittest.TestCase):
 @unittest.skipUnless(shutil.which('java'),'Java unavailable')
 def test_exact_readiness_publish_animation_and_native_callbacks(self):
  changes=json.loads((ROOT/'.circleci/features/homepage-surround/paint.json').read_text())
  phone=next(c[2] for c in changes if c[0]=='ToolbarPhone.java' and 'private boolean hasSandiumWallpaperSurround' in c[2])
  native=next(c[2] for c in changes if c[0]=='TopToolbarOverlayMediator.java' and 'boolean wallpaper =' in c[2])
  owner=next(p['new'] for p in json.loads((ROOT/'.circleci/features/homepage-surround/backing.json').read_text()) if 'public void setSandiumToolbarWallpaperPaintColor' in p['new'] and 'mSandiumToolbarWallpaperPaintColor =' in p['new'])
  body='\n'.join(extract(phone,n) for n in ['onSandiumWallpaperBackingChanged','publishSandiumWallpaperPaintColor','notifyToolbarColorChanged'])
  setter=extract(owner,'setSandiumToolbarWallpaperPaintColor')
  java=r'''
import java.util.*;
class Loop {
 interface Parent {Parent getParent();}
 static class View implements Parent {public Parent getParent(){return null;}}
 static class Adapter {void invalidate(Object o){}void triggerBitmapCapture(){}}
 static class ToolbarControlContainer extends View {Adapter getToolbarResourceAdapter(){return new Adapter();}}
 static class Drawable {int color=0xff121212;int getColor(){return color;}}
 static class Page {
  boolean ready;Integer mSandiumToolbarWallpaperPaintColor;
  List<Runnable>mSandiumWallpaperObservers=new ArrayList<>();
  boolean hasSandiumToolbarWallpaperBacking(){return ready;}
  Integer getSandiumToolbarWallpaperPaintColor(){return mSandiumToolbarWallpaperPaintColor;}
  SETTER
  void readiness(boolean value){ready=value;for(Runnable r:new ArrayList<>(mSandiumWallpaperObservers))r.run();}
 }
 static class Base extends View {protected void notifyToolbarColorChanged(int color){}}
 static class Phone extends Base {
  Page mSandiumWallpaperPage;boolean mSandiumWallpaperBackingReady,focus;int updates;Drawable mToolbarBackground=new Drawable();
  void invalidate(){}
  void updateVisualsForLocationBarState(){updates++;int color=mSandiumWallpaperPage.ready&&!focus?0:0xff121212;if(mToolbarBackground.color!=color){mToolbarBackground.color=color;notifyToolbarColorChanged(color);}}
  BODY
  void animate(int color){mToolbarBackground.color=color;notifyToolbarColorChanged(color);}
 }
 static class Tab {Page page;boolean isIncognito(){return false;}Page getNativePage(){return page;}}
 static class BrowserControlsStateProvider {static class ControlsPosition {static int BOTTOM=1;}}
 static class Controls {int getControlsPosition(){return 1;}}
 static class TopToolbarOverlayProperties {static int TOOLBAR_BACKGROUND_COLOR=1,URL_BAR_COLOR=2;}
 static class Model {Map<Integer,Integer>values=new HashMap<>();void set(int key,int value){values.put(key,value);}}
 static class Native {
  Controls mBrowserControlsVisibilityManager=new Controls();Model mModel=new Model();int getToolbarBackgroundColor(Tab t){return 0xff121212;}int getUrlBarBackgroundColor(Tab t,int color){return color+1;}
  private void updateThemeColor(Tab tab){int color=getToolbarBackgroundColor(tab);NATIVE}
 }
 static void require(boolean b){if(!b)throw new AssertionError();}
 public static void main(String[]x){Page page=new Page();Phone phone=new Phone();phone.mSandiumWallpaperPage=page;Tab tab=new Tab();tab.page=page;Native nativeLayer=new Native();
 page.mSandiumWallpaperObservers.add(phone::onSandiumWallpaperBackingChanged);page.mSandiumWallpaperObservers.add(()->nativeLayer.updateThemeColor(tab));
 page.readiness(true);require(phone.updates==1&&nativeLayer.mModel.values.get(1)==0);require(nativeLayer.mModel.values.get(2)==0xff121213);
 phone.animate(0x80333333);require(phone.updates==1&&nativeLayer.mModel.values.get(1)==0x80333333);
 phone.focus=true;phone.updateVisualsForLocationBarState();require(phone.updates==2&&nativeLayer.mModel.values.get(1)==0xff121212);
 page.readiness(false);require(phone.updates==3&&nativeLayer.mModel.values.get(1)==0xff121212);
 }
}
'''.replace('SETTER',setter).replace('BODY',body).replace('NATIVE',native)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'Loop.java';p.write_text(java)
   subprocess.run(['java','-m','jdk.compiler/com.sun.tools.javac.Main',str(p)],check=True)
   subprocess.run(['java','-cp',d,'Loop'],check=True)
if __name__=='__main__':unittest.main()
