"""Native host behavior with explicitly limited framework/model doubles, not Android rendering."""
from pathlib import Path
import ast,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/'sandium/menu/java/org/chromium/chrome/browser/ui/appmenu'
class GridHostTest(unittest.TestCase):
 def test_source_mutation_live_policy_dispatch_and_close(self):
  tree=ast.parse((ROOT/'tests/test_native_menu_projection.py').read_text())
  node=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='sources' for t in n.targets))
  sources=ast.literal_eval(node.value)
  sources.pop('org/chromium/chrome/browser/ui/appmenu/Projection.java')
  sources['android/content/Context.java']=sources['android/content/Context.java'].replace('getString(int id)','getString(int id,Object...args)')
  sources['android/content/res/Resources.java']=sources['android/content/res/Resources.java'].replace('public class Resources {','public class Resources {public Configuration getConfiguration(){return new Configuration();}')
  sources['android/content/res/Configuration.java']='package android.content.res; public class Configuration {public float fontScale=1;}'
  sources['android/graphics/drawable/Drawable.java']='package android.graphics.drawable;public class Drawable{}'
  sources['org/chromium/ui/modelutil/PropertyKey.java']='package org.chromium.ui.modelutil;public class PropertyKey{}'
  sources['org/chromium/ui/modelutil/PropertyObservable.java']='''package org.chromium.ui.modelutil;import java.util.*;public class PropertyObservable<T>{public interface PropertyObserver<T>{void onPropertyChanged(PropertyObservable<T> source,T key);} final List<PropertyObserver<T>> obs=new ArrayList<>(); public void addObserver(PropertyObserver<T> o){obs.add(o);}public void removeObserver(PropertyObserver<T> o){obs.remove(o);} public void notifyKey(T key){for(var o:List.copyOf(obs))o.onPropertyChanged(this,key);}}'''
  model=sources['org/chromium/ui/modelutil/PropertyModel.java'].replace('public class PropertyModel {','public class PropertyModel extends PropertyObservable<PropertyKey> {').replace('class Key<T>{','class Key<T> extends PropertyKey{').replace('public Builder(Key<?>[]k)','public Builder(PropertyKey[]k)')
  model=model.replace('public boolean containsKey(', 'public <T> void set(Key<T> key,T value){m.put(key,value);notifyKey(key);}public boolean containsKey(')
  sources['org/chromium/ui/modelutil/PropertyModel.java']=model
  props=sources['org/chromium/chrome/browser/ui/appmenu/AppMenuItemProperties.java'].replace('MANAGED=new Key<>(false),','CHECKABLE=new Key<>(false),ICON_NO_TINT=new Key<>(false),ICON_SHOW_BADGE=new Key<>(false),CHECKED=new Key<>(false),MANAGED=new Key<>(false),').replace('public static final Key<?>[]ALL_KEYS={};','public static final Key<Object> ICON_SUPPLIER=new Key<>(null);public static final Key<Integer>ICON_COLOR_RES=new Key<>(0);public static final Key<android.graphics.drawable.Drawable> ICON=new Key<>(null);public static final Key<?>[]ALL_KEYS={};')
  sources['org/chromium/chrome/browser/ui/appmenu/AppMenuItemProperties.java']=props
  sources['org/chromium/chrome/browser/ui/appmenu/internal/R.java']=sources['org/chromium/chrome/browser/ui/appmenu/internal/R.java'].replace('raws_customize_menu=999','menu_item_icon=995,raws_menu_grid=996,raws_customize_menu=999').replace('raws_customize_menu=1','raws_menu_grid=8,raws_menu_all=9,raws_menu_previous=10,raws_menu_next=11,raws_menu_page=12,raws_customize_menu=1')
  sources['org/chromium/components/browser_ui/util/motion/MotionEventInfo.java']='package org.chromium.components.browser_ui.util.motion;public class MotionEventInfo{}'
  sources['org/chromium/chrome/browser/ui/appmenu/AppMenuClickHandler.java']='''package org.chromium.chrome.browser.ui.appmenu;import org.chromium.ui.modelutil.PropertyModel;import org.chromium.components.browser_ui.util.motion.MotionEventInfo;public interface AppMenuClickHandler{void onItemClick(PropertyModel model,MotionEventInfo motion);default boolean onItemLongClick(PropertyModel m,android.view.View v){return false;}}'''
  sources['android/widget/ImageView.java']='package android.widget;public class ImageView extends android.view.View{public void setId(int id){}}'
  sources['org/chromium/chrome/browser/ui/appmenu/AppMenuItemViewBinder.java']='package org.chromium.chrome.browser.ui.appmenu;import org.chromium.ui.modelutil.*;public class AppMenuItemViewBinder{static void bindStandardItem(PropertyModel m,android.view.View v,PropertyKey k){}}'
  sources['org/chromium/chrome/browser/ui/appmenu/RawSMenuGridView.java']='''package org.chromium.chrome.browser.ui.appmenu;import android.graphics.drawable.Drawable;import org.chromium.components.browser_ui.util.motion.MotionEventInfo;public class RawSMenuGridView<T>{interface MotionDispatcher<T> extends RawSMenuModel.Dispatcher<T>{void triggeringMotion(MotionEventInfo motion);}interface Presentation<T>{CharSequence title(T t);Drawable icon(T t);boolean enabled(T t);CharSequence allMenuTitle();CharSequence previousPageTitle();CharSequence nextPageTitle();CharSequence pageDescription(int p,int c);}}'''
  sources['org/chromium/chrome/browser/ui/appmenu/RawSMenuGridBinder.java']='''package org.chromium.chrome.browser.ui.appmenu;import org.chromium.ui.modelutil.PropertyModel.Key;public class RawSMenuGridBinder{static Key<Binding<?>> DATA=new Key<>(null);static class Binding<T>{final RawSMenuPager<T> pager;final RawSMenuModel.Dispatcher<T> dispatch,dispatcher;final RawSMenuGridView.Presentation<T> presentation;final Runnable sizeChanged;Binding(RawSMenuPager<T> p,RawSMenuGridView.Presentation<T> v,RawSMenuModel.Dispatcher<T> d,Runnable r){pager=p;dispatch=d;dispatcher=d;presentation=v;sizeChanged=r;}}}'''
  sources['org/chromium/chrome/browser/ui/appmenu/RawSMenuGridMetrics.java']='package org.chromium.chrome.browser.ui.appmenu;public class RawSMenuGridMetrics{static int height(android.content.Context c,RawSMenuPager<?> p){return heightForLimit(c,p,p.availableRows());}static int heightForLimit(android.content.Context c,RawSMenuPager<?> p,int limit){return p.rowsForLimit(limit)*72+(p.pagesForLimit(limit)>1?48:0);}}'
  sources['org/chromium/chrome/browser/ui/appmenu/GridHost.java']='''package org.chromium.chrome.browser.ui.appmenu;
import android.content.Context;import org.chromium.ui.modelutil.*;import org.chromium.ui.modelutil.MVCListAdapter.*;
public class GridHost {
 static void check(boolean b){if(!b)throw new AssertionError();}
 static ListItem row(int id){return new ListItem(1,new PropertyModel.Builder(AppMenuItemProperties.ALL_KEYS).with(AppMenuItemProperties.MENU_ITEM_ID,id).with(AppMenuItemProperties.TITLE,"Action").with(AppMenuItemProperties.ENABLED,true).build());}
 public static void main(String[] args){
 Context c=new Context();RawSNativeMenu owner=new RawSNativeMenu(c);RawSGridHost host=new RawSGridHost(c);host.setGridType(14);
 ModelList source=new ModelList();ListItem one=row(1),two=row(2);source.add(one);source.add(two);
 int[] calls={0};ModelList view=host.prepare(owner,source,(model,motion)->{calls[0]++;},()->{});
 check(source.size()==2 && source.get(0)==one);check(view.get(0).type==host.gridType());
 check(view.size()==2);check(view.get(1).model.get(AppMenuItemProperties.MENU_ITEM_ID)==999);
 @SuppressWarnings("unchecked") RawSMenuGridBinder.Binding<ListItem> b=(RawSMenuGridBinder.Binding<ListItem>)view.get(0).model.get(RawSMenuGridBinder.DATA);
 RawSMenuPager.Tile<ListItem> old=b.pager.tiles().get(0);
 one.model.set(AppMenuItemProperties.ENABLED,false);
 check(!b.pager.activate(old,b.dispatch));check(calls[0]==0);
 source.add(row(3));check(source.size()==3 && source.get(0)==one);
 @SuppressWarnings("unchecked") RawSMenuGridBinder.Binding<ListItem> current=(RawSMenuGridBinder.Binding<ListItem>)view.get(0).model.get(RawSMenuGridBinder.DATA);
 check(current.pager.tiles().size()==4);
 check(current.pager.activate(current.pager.tiles().get(3),current.dispatch));
 check(current.pager.isDirectory());check(current.pager.rows()==5);
 check(host.fitAvailableHeight(400)==360);check(current.pager.rows()==5);
 check(host.fitAvailableHeight(160)==144);check(current.pager.rows()==2);
 var fitTile=current.pager.tiles().get(1);host.fitAvailableHeight(160);check(current.pager.isCurrent(fitTile));
 check(host.fitAvailableHeight(400)==360);check(current.pager.rows()==5);
 check(host.backToQuick());check(!host.backToQuick());
 one.model.set(AppMenuItemProperties.MANAGED,true);check(view.contains(one));
 one.model.set(AppMenuItemProperties.MANAGED,false);
 @SuppressWarnings("unchecked") RawSMenuGridBinder.Binding<ListItem> live=(RawSMenuGridBinder.Binding<ListItem>)view.get(0).model.get(RawSMenuGridBinder.DATA);current=live;
 check(current.pager.activate(current.pager.tiles().get(1),current.dispatch));check(calls[0]==1);
 host.close();owner.closeProjection();int count=view.size();source.add(row(4));check(view.size()==count);
 ModelList small=host.prepare(owner,source,(model,motion)->{},()->{});check(small.get(0).type==host.gridType());
 check(host.fitAvailableHeight(1)==0);check(small.size()==source.size());check(small.get(0)==source.get(0));check(!host.isAdjustingViewport());
 check(host.fitAvailableHeight(900)==-1);host.close();owner.closeProjection();
 RawSGridHost unconfigured=new RawSGridHost(c);ModelList staged=unconfigured.prepare(owner,source,(model,motion)->{},()->{});
 check(staged.get(0)==source.get(0));unconfigured.setGridType(14);check(staged.get(0).type==14);
 unconfigured.setGridType(15);check(staged.get(0).type==15);check(source.get(0).type==1);
 unconfigured.close();owner.closeProjection();
 }
}'''
  with tempfile.TemporaryDirectory() as tmp:
   paths=[]
   for name,code in sources.items():
    p=Path(tmp)/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(code);paths.append(str(p))
   actual=[str(JAVA/(name+'.java')) for name in ('RawSMenuModel','RawSMenuPager','RawSMenuStore','RawSNativeMenu','RawSGridHost')]
   r=subprocess.run(['java','com.sun.tools.javac.Main','-d',tmp,*paths,*actual],capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stderr)
   r=subprocess.run(['java','-cp',tmp,'org.chromium.chrome.browser.ui.appmenu.GridHost'],capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stderr)
