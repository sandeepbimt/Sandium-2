"""Optional real Android15 API compile, not a runtime/Chromium build test.
Set RAWS_ANDROID_API_JAR to Robolectric android-all15 jar (or Android SDK android.jar).
Chromium PropertyModel doubles validate binder signatures only.
"""
from pathlib import Path
import os, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/'sandium/menu/java/org/chromium/chrome/browser/ui/appmenu'
class GridApiTest(unittest.TestCase):
 def test_android15_grid_compile(self):
  jar=os.environ.get('RAWS_ANDROID_API_JAR')
  if not jar: self.skipTest('RAWS_ANDROID_API_JAR unset; not Android API validated by this run')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);pkg=root/'org/chromium/ui/modelutil';pkg.mkdir(parents=True)
   (pkg/'PropertyKey.java').write_text('package org.chromium.ui.modelutil; public class PropertyKey {}')
   (pkg/'PropertyModel.java').write_text('''package org.chromium.ui.modelutil;
public class PropertyModel extends PropertyObservable<PropertyKey> {
 public static class WritableObjectPropertyKey<T> extends PropertyKey {}
 public <T> T get(WritableObjectPropertyKey<T> key) {return null;}
}''')
   motion=root/'org/chromium/components/browser_ui/util/motion';motion.mkdir(parents=True)
   (motion/'MotionEventInfo.java').write_text('package org.chromium.components.browser_ui.util.motion; public class MotionEventInfo {}')
   (motion/'OnPeripheralClickListener.java').write_text('package org.chromium.components.browser_ui.util.motion; public class OnPeripheralClickListener implements android.view.View.OnTouchListener {public OnPeripheralClickListener(java.util.function.Consumer<MotionEventInfo> c){} public boolean onTouch(android.view.View v,android.view.MotionEvent e){return false;}}')
   metrics=root/'org/chromium/chrome/browser/ui/appmenu/Metrics.java';metrics.parent.mkdir(parents=True)
   metrics.write_text('package org.chromium.chrome.browser.ui.appmenu;public class Metrics{public static void main(String[]a){if(RawSMenuGridMetrics.rowHeight(72,32,18)!=72||RawSMenuGridMetrics.rowHeight(72,32,36)!=104||RawSMenuGridMetrics.rowHeight(72,32,54)!=140)throw new AssertionError();}}')
   extras={'androidx/appcompat/app/AlertDialog.java': 'package androidx.appcompat.app;import android.content.Context;import android.view.View;public class AlertDialog{public static int BUTTON_POSITIVE=-1,BUTTON_NEGATIVE=-2,BUTTON_NEUTRAL=-3;public interface Event{void run(Object x);}public interface Choice{void run(Object x,int i);}public void setOnShowListener(Event e){}public View getButton(int i){return null;}public boolean isShowing(){return true;}public void setCancelable(boolean b){}public void setTitle(int id){}public void dismiss(){}public void show(){}public static class Builder{public Builder(Context c){}public Builder setTitle(int i){return this;}public Builder setView(View v){return this;}public Builder setNegativeButton(int i,Choice c){return this;}public Builder setPositiveButton(int i,Choice c){return this;}public Builder setNeutralButton(int i,Choice c){return this;}public AlertDialog create(){return new AlertDialog();}}}', 'org/chromium/base/task/PostTask.java': 'package org.chromium.base.task;public class PostTask{public static void postTask(int trait,Runnable r){}}', 'org/chromium/base/task/TaskTraits.java': 'package org.chromium.base.task;public class TaskTraits{public static int USER_VISIBLE_MAY_BLOCK=1;}', 'org/chromium/ui/modelutil/PropertyObservable.java': 'package org.chromium.ui.modelutil;public class PropertyObservable<T>{public interface PropertyObserver<T>{void onPropertyChanged(PropertyObservable<T> source,T key);}public void addObserver(PropertyObserver<T> o){}public void removeObserver(PropertyObserver<T> o){}}', 'org/chromium/ui/modelutil/MVCListAdapter.java': 'package org.chromium.ui.modelutil;public class MVCListAdapter{public static class ListItem{public PropertyModel model;}}', 'org/chromium/chrome/browser/ui/appmenu/RawSMenuStore.java': 'package org.chromium.chrome.browser.ui.appmenu;public class RawSMenuStore implements RawSMenuModel.Store{public String read(){return "";}public boolean write(String v){return true;}}', 'org/chromium/chrome/browser/ui/appmenu/AppMenuItemProperties.java': 'package org.chromium.chrome.browser.ui.appmenu;import org.chromium.ui.modelutil.PropertyModel.WritableObjectPropertyKey;public class AppMenuItemProperties{static WritableObjectPropertyKey<CharSequence>TITLE=new WritableObjectPropertyKey<>();static WritableObjectPropertyKey<Object>ICON=new WritableObjectPropertyKey<>(),ICON_COLOR_RES=new WritableObjectPropertyKey<>(),ICON_NO_TINT=new WritableObjectPropertyKey<>(),ICON_SHOW_BADGE=new WritableObjectPropertyKey<>(),ICON_SUPPLIER=new WritableObjectPropertyKey<>();}', 'org/chromium/chrome/browser/ui/appmenu/AppMenuItemViewBinder.java': 'package org.chromium.chrome.browser.ui.appmenu;import org.chromium.ui.modelutil.*;public class AppMenuItemViewBinder{static void bindStandardItem(PropertyModel m,android.view.View v,PropertyKey k){}}', 'org/chromium/chrome/browser/ui/appmenu/internal/R.java': 'package org.chromium.chrome.browser.ui.appmenu.internal;public class R{public static class id{public static int menu_item_icon=1,raws_menu_move_up_action=2,raws_menu_move_down_action=3;}public static class string{public static int raws_menu_drag=1,raws_menu_available=2,raws_menu_previous=3,raws_menu_next=4,raws_menu_move_up=5,raws_menu_move_down=6,raws_customize_menu=7,raws_menu_reset=8,raws_menu_done=9,raws_menu_save_failed=10;}}'}
   extra_paths=[]
   for name,code in extras.items():
    target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(code);extra_paths.append(str(target))
   sources=[JAVA/(name+'.java') for name in ('RawSMenuEditorState','RawSMenuGridEditor','RawSMenuEditorView','RawSMenuGridMetrics','RawSMenuModel','RawSMenuPager','RawSMenuTileTargets','RawSMenuGridView','RawSMenuGridBinder')]
   r=subprocess.run(['java','com.sun.tools.javac.Main','-Xlint:unchecked','-Werror','-cp',jar,'-d',tmp,
                      *map(str,(pkg/name for name in ('PropertyModel.java','PropertyKey.java'))),*extra_paths,*map(str,motion.glob('*.java')),str(metrics),*map(str,sources)],capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stderr)
   r=subprocess.run(['java','-cp',tmp+os.pathsep+jar,'org.chromium.chrome.browser.ui.appmenu.Metrics'],capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stderr)
