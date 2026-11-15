package org.chromium.chrome.browser.sandium.dark;
import java.lang.reflect.*;
import java.util.*;
import android.app.*;
import android.widget.*;
import org.chromium.chrome.browser.tab.Tab;
import org.chromium.content_public.browser.*;
public class ElementChooserTest {
 static int checks;
 static void check(boolean b){checks++;if(!b)throw new AssertionError("check "+checks);}
 static Object field(Object o,String name)throws Exception{Field f=o.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(o);}
 static Map<Tab,Object> active()throws Exception{Field f=SandiumElementColorsUtils.class.getDeclaredField("ACTIVE");f.setAccessible(true);return (Map<Tab,Object>)f.get(null);}
 static class Native implements SandiumElementColorsUtils.Natives {
  long id;Tab tab;int starts,previews,saves,cancels,resets,mode,rgb;boolean allowed=true;
  public boolean start(Tab t,long r){tab=t;id=r;starts++;return allowed;}
  public boolean preview(Tab t,long r,int p,int c){check(r==id);previews++;mode=p;rgb=c;return allowed;}
  public void save(Tab t,long r,int p,int c){check(r==id);saves++;mode=p;rgb=c;}
  public void cancel(Tab t,long r){cancels++;SandiumElementColorsUtils.onSessionEnded(t,r);}
  public void resetSite(Tab t,long r){check(r==id);resets++;}
 }
 public static void main(String[] args)throws Exception{
  Native n=new Native();SandiumElementColorsUtilsJni.instance=n;Activity a=new Activity();Tab t=new Tab();
  SandiumElementColorsUtils.start(a,t);long first=n.id;check(active().size()==1&&a.app.callbacks.size()==1);
  SandiumElementColorsUtils.onSelection(t,first);Object controller=active().get(t);check(AlertDialog.shown.size()==1);
  EditText color=(EditText)field(controller,"color");Button preview=(Button)field(controller,"preview");Button save=(Button)field(controller,"save");
  color.setText("url(x)");preview.performClick();check(n.previews==0&&color.error!=null);
  color.setText("#1A1A1A");preview.performClick();check(n.previews==1&&n.mode==1&&n.rgb==0x1a1a1a);
  save.performClick();save.performClick();check(n.saves==1&&!save.enabled);
  SandiumElementColorsUtils.onSaveResult(t,first-1,0);check(active().size()==1);
  SandiumElementColorsUtils.onSaveResult(t,first,0);check(active().isEmpty()&&a.app.callbacks.isEmpty());
  check(android.widget.Toast.last==org.chromium.chrome.R.string.sandium_element_saved);
  SandiumElementColorsUtils.start(a,t);long second=n.id;SandiumElementColorsUtils.onSelection(t,second);
  SandiumElementColorsUtils.start(a,t);long third=n.id;int dialogs=AlertDialog.shown.size();
  SandiumElementColorsUtils.onSelection(t,second);SandiumElementColorsUtils.onSessionEnded(t,second);
  check(active().size()==1&&AlertDialog.shown.size()==dialogs);
  SandiumElementColorsUtils.onSelection(t,third);controller=active().get(t);
  ((AlertDialog)field(controller,"dialog")).dismiss();check(active().isEmpty());
  SandiumElementColorsUtils.start(a,t);controller=active().get(t);int cancels=n.cancels;
  ((WebContentsObserver)field(controller,"observer")).webContentsDestroyed();check(active().isEmpty()&&n.cancels==cancels);
  SandiumElementColorsUtils.start(a,t);for(var callback:new ArrayList<>(a.app.callbacks))callback.onActivityStopped(a);
  check(active().isEmpty()&&a.app.callbacks.isEmpty());
  SandiumElementColorsUtils.start(a,t);long fourth=n.id;t.contents=new WebContents();SandiumElementColorsUtils.onSelection(t,fourth);check(active().isEmpty());
  n.allowed=false;SandiumElementColorsUtils.start(a,t);check(active().isEmpty()&&a.app.callbacks.isEmpty());
  n.allowed=true;SandiumElementColorsUtils.start(a,t);controller=active().get(t);
  ((WebContentsObserver)field(controller,"observer")).didStartNavigationInPrimaryMainFrame(new NavigationHandle());check(active().isEmpty());
  SandiumElementColorsUtils.start(a,t);SandiumElementColorsUtils.onSelection(t,n.id);controller=active().get(t);
  Method reset=controller.getClass().getDeclaredMethod("confirmReset");reset.setAccessible(true);
  dialogs=AlertDialog.shown.size();reset.invoke(controller);reset.invoke(controller);check(AlertDialog.shown.size()==dialogs+1);
  ((AlertDialog)field(controller,"resetDialog")).dismiss();reset.invoke(controller);check(AlertDialog.shown.size()==dialogs+2);
  ((Runnable)field(controller,"timeout")).run();check(active().isEmpty()&&android.widget.Toast.last==org.chromium.chrome.R.string.sandium_element_unavailable);
  SandiumElementColorsUtils.start(a,t);SandiumElementColorsUtils.onSelection(t,n.id);controller=active().get(t);
  ((Button)field(controller,"save")).performClick();((Runnable)field(controller,"timeout")).run();
  check(active().isEmpty()&&android.widget.Toast.last==org.chromium.chrome.R.string.sandium_element_rejected);
  System.out.println(checks+" chooser lifecycle/typed-command assertions passed (Android/JNI APIs stubbed)");
 }
}
