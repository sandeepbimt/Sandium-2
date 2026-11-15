import android.app.AlertDialog;
import android.content.Context;
import org.chromium.chrome.browser.profiles.*;
import org.chromium.chrome.browser.tab.Tab;
import org.chromium.content_public.browser.WebContents;
import org.chromium.components.user_prefs.UserPrefs;
import org.chromium.chrome.browser.sandium.dark.SandiumDarkPagesUi;
import org.chromium.chrome.browser.night_mode.SandiumDarkPages;
import org.chromium.chrome.browser.sandium.dark.DarkPagePolicy.Control;
public class DialogPolicyTest {
 static int checks;static void check(boolean b){checks++;if(!b)throw new AssertionError("check"+checks);}
 static AlertDialog last(){return AlertDialog.shown.get(AlertDialog.shown.size()-1);}
 public static void main(String[]a){
  Context c=new Context();Profile regular=new Profile(),privateProfile=new Profile(regular);
  Tab tab=new Tab(new WebContents(privateProfile,"https://example.com"));
  SandiumDarkPagesUi.showSite(c,tab);AlertDialog outer=last();int n=AlertDialog.shown.size();
  ProfileManager.destroy(regular);outer.item.onClick(outer,0);check(AlertDialog.shown.size()==n);
  regular=new Profile();tab=new Tab(new WebContents(regular,"https://example.com"));
  SandiumDarkPagesUi.showSite(c,tab);outer=last();outer.item.onClick(outer,0);AlertDialog inner=last();
  check(inner!=outer);ProfileManager.destroy(regular);inner.single.onClick(inner,2);check(inner.dismissed);
  regular=new Profile();tab=new Tab(new WebContents(regular,"https://example.com"));
  SandiumDarkPagesUi.showSite(c,tab);outer=last();n=AlertDialog.shown.size();
  tab.contents.url=new org.chromium.url.GURL("https://other.example");outer.item.onClick(outer,0);check(AlertDialog.shown.size()==n);
  SandiumDarkPagesUi.showGlobal(c,regular);AlertDialog global=last();UserPrefs.get(regular).fail=true;
  global.multi.onClick(global,0,false);check(global.dismissed);check(SandiumDarkPages.global(regular,Control.DARK_PAGE));
  UserPrefs.get(regular).fail=false;SandiumDarkPagesUi.showGlobal(c,regular);global=last();ProfileManager.destroy(regular);
  global.multi.onClick(global,0,false);check(global.dismissed);
  System.out.println(checks+" UI callback assertions passed (Android/native APIs stubbed)");
 }
}
