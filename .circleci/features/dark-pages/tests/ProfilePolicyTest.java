import org.chromium.chrome.browser.night_mode.SandiumDarkPages;
import org.chromium.chrome.browser.sandium.dark.DarkPagePolicy.*;
import org.chromium.chrome.browser.profiles.*;
import org.chromium.components.user_prefs.UserPrefs;
import org.chromium.content_public.browser.WebContents;
import org.chromium.url.GURL;
public class ProfilePolicyTest {
 static int checks;
 static void check(boolean v){checks++;if(!v)throw new AssertionError("check "+checks);}
 static Boolean enabled(WebContents w){return SandiumDarkPages.enabled(w,w.url);}
 static int flags(WebContents w){return SandiumDarkPages.flags(w,w.url);}
 public static void main(String[] args){
  Profile firstGlobal=new Profile();
  check(SandiumDarkPages.global(firstGlobal,Control.DARK_PAGE));
  check(ProfileManager.count()==1);
  ProfileManager.destroy(firstGlobal);
  Profile dyingOriginal=new Profile(), survivingPrivate=new Profile(dyingOriginal);
  ProfileManager.destroy(dyingOriginal);
  check(SandiumDarkPages.flags(new WebContents(survivingPrivate,"https://example.com"),new GURL("https://example.com"))==0);
  check(!SandiumDarkPages.trySetGlobal(dyingOriginal,Control.DARK_PAGE,false));
  Profile regular=new Profile(), privateOne=new Profile(regular), another=new Profile();
  GURL url=new GURL("https://example.com/a?secret=x");
  check(SandiumDarkPages.origin(url).equals("https://example.com"));
  check(enabled(new WebContents(regular,url.getSpec())));
  SandiumDarkPages.set(regular,url,Control.DARK_PAGE,Choice.OFF);
  check(!enabled(new WebContents(regular,"https://example.com/other")));
  check(!UserPrefs.get(regular).value.contains("secret"));
  check(enabled(new WebContents(another,url.getSpec())));
  check(enabled(new WebContents(privateOne,url.getSpec())));
  WebContents pending = new WebContents(regular,"https://pending.example");
  check(!SandiumDarkPages.enabled(pending,url)); // explicit document origin, never visible pending URL
  check(SandiumDarkPages.enabled(pending,new GURL("https://other.example")));
  int reads=UserPrefs.get(regular).reads;
  for(int i=0;i<20;i++) flags(new WebContents(regular,url.getSpec()));
  check(UserPrefs.get(regular).reads==reads);
  UserPrefs.get(regular).fail=true; boolean failed=false;
  try{SandiumDarkPages.set(regular,url,Control.DARK_PAGE,Choice.ON);}catch(IllegalStateException expected){failed=true;}
  check(failed&&!enabled(new WebContents(regular,url.getSpec())));
  UserPrefs.get(regular).fail=false;
  int writes=UserPrefs.get(regular).writes;
  SandiumDarkPages.set(privateOne,url,Control.DARK_PAGE,Choice.OFF);
  check(!enabled(new WebContents(privateOne,url.getSpec())));
  check(UserPrefs.get(regular).writes==writes&&UserPrefs.get(privateOne).writes==0);
  ProfileManager.destroy(privateOne);
  Profile privateTwo=new Profile(regular);
  check(enabled(new WebContents(privateTwo,url.getSpec())));
  SandiumDarkPages.setGlobal(regular,Control.DARK_PAGE,false);
  check(!enabled(new WebContents(privateTwo,url.getSpec())));
  SandiumDarkPages.set(regular,url,Control.DARK_PAGE,Choice.ON);
  check(enabled(new WebContents(regular,url.getSpec())));
  SandiumDarkPages.set(regular,url,Control.DARK_PAGE,Choice.FOLLOW_GLOBAL);
  check(!enabled(new WebContents(regular,url.getSpec())));
  check(!UserPrefs.get(regular).value.contains("example.com"));
  String saved=UserPrefs.get(regular).value;
  ProfileManager.destroy(regular);
  check(enabled(new WebContents(regular,url.getSpec()))==null);
  check(!SandiumDarkPages.available(regular));
  regular=new Profile(); UserPrefs.get(regular).value=saved;
  check(!enabled(new WebContents(regular,url.getSpec()))); // persisted global survives recreated profile
  // Model a fresh browser/profile with only persisted PrefService bytes retained.
  SandiumDarkPages.set(regular,url,Control.DARK_PAGE,Choice.ON);
  String perSiteSaved=UserPrefs.get(regular).value;
  ProfileManager.destroy(regular);
  regular=new Profile();UserPrefs.get(regular).value=perSiteSaved;
  check(enabled(new WebContents(regular,"https://example.com/new-path")));
  check(!enabled(new WebContents(regular,"https://another.example")));
  Profile restartedPrivate=new Profile(regular);
  check(!enabled(new WebContents(restartedPrivate,url.getSpec()))); // no normal-site override import
  SandiumDarkPages.set(regular,url,Control.DARK_PAGE,Choice.FOLLOW_GLOBAL);
  String resetSaved=UserPrefs.get(regular).value;
  ProfileManager.destroy(regular);
  regular=new Profile();UserPrefs.get(regular).value=resetSaved;
  check(!enabled(new WebContents(regular,url.getSpec())));
  check(!UserPrefs.get(regular).value.contains("example.com"));
  check(enabled(new WebContents(regular,"chrome://settings"))==null);
  Profile invalidProfile = new Profile(); UserPrefs.get(invalidProfile).value="invalid";
  check(enabled(new WebContents(invalidProfile,url.getSpec())));
  boolean blocked=false;
  try{SandiumDarkPages.setGlobal(privateTwo,Control.DARK_PAGE,true);}catch(IllegalStateException e){blocked=true;}
  check(blocked);
  System.out.println(checks+" adapter assertions passed (native APIs stubbed)");
 }
}
