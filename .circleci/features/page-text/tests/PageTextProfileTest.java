import org.chromium.chrome.browser.profiles.*;
import org.chromium.chrome.browser.sandium.text.*;
import org.chromium.components.user_prefs.UserPrefs;
import org.chromium.components.prefs.PrefService;
import org.chromium.content_public.browser.WebContents;
import org.chromium.url.GURL;

/** Actual adapter compiled against fake Chromium profile APIs and real JSON-java.
 * This verifies serialized preferences, not Android disk durability or browser rendering.
 */
public class PageTextProfileTest {
    static int count;
    static void check(boolean value) {
        count++;
        if (!value) throw new AssertionError("check " + count);
    }
    public static void main(String[] args) {
        Profile normal = new Profile();
        GURL a = new GURL("https://one.example/article");
        GURL b = new GURL("https://two.example/news");
        WebContents contents = new WebContents(normal, a.getSpec());
        PrefService prefs = UserPrefs.get(normal);
        check(SandiumPageText.packed(contents, a) == 100);
        check(!SandiumPageText.global(normal).enabled);
        int initialReads = prefs.reads;
        for (int i=0;i<20;i++) check(SandiumPageText.packed(contents, a)==100);
        check(prefs.reads == initialReads);
        SandiumPageText.setGlobal(normal, new PageTextPolicy.Settings(false,120,false));
        check(SandiumPageText.packed(contents,a)==120);
        // All origins share the same global snapshot, including final redirect destinations.
        check(SandiumPageText.packed(contents,b)==120);
        check(SandiumPageText.packed(contents,new GURL("chrome://settings"))==100);
        check(SandiumPageText.packed(null,a)==100);
        check(prefs.value.contains("scalePercent"));
        String saved = prefs.value;
        Profile recreated = new Profile();
        UserPrefs.get(recreated).value=saved;
        check(SandiumPageText.global(recreated).scalePercent==120);
        check(!SandiumPageText.global(recreated).justify);
        Profile privateProfile = new Profile(normal);
        WebContents privateContents = new WebContents(privateProfile,a.getSpec());
        int writes=prefs.writes;
        check(SandiumPageText.packed(privateContents,a)==120);
        SandiumPageText.setGlobal(privateProfile,new PageTextPolicy.Settings(false,130,false));
        check(SandiumPageText.packed(privateContents,b)==130);
        check(SandiumPageText.packed(contents,b)==120);
        check(prefs.writes==writes);
        check(UserPrefs.get(privateProfile).writes==0);
        check(SandiumPageText.packed(privateContents,a)==130);
        ProfileManager.destroy(privateProfile);
        check(SandiumPageText.packed(privateContents,a)==100);
        prefs.fail=true;
        try {SandiumPageText.setGlobal(normal,PageTextPolicy.DEFAULT);throw new AssertionError();}
        catch(IllegalStateException expected){count++;}
        check(SandiumPageText.packed(contents,a)==120);
        check(prefs.value.equals(saved));
        prefs.fail=false;
        check(SandiumPageText.packed(contents,a)==120);
        Profile legacy=new Profile();
        String legacySite="\"sites\":{\"https://one.example\":{\"enabled\":true,\"scalePercent\":150,\"justify\":true}}";
        UserPrefs.get(legacy).value="{\"version\":1,"+legacySite+"}";
        WebContents legacyContents=new WebContents(legacy,a.getSpec());
        check(SandiumPageText.packed(legacyContents,a)==100);
        SandiumPageText.setGlobal(legacy,new PageTextPolicy.Settings(true,115,true));
        check(SandiumPageText.packed(legacyContents,a)==(115|768));
        check(SandiumPageText.packed(legacyContents,b)==(115|768));
        check(UserPrefs.get(legacy).value.contains("sites"));
        Profile corrupt=new Profile();UserPrefs.get(corrupt).value="not json";
        check(SandiumPageText.global(corrupt).scalePercent==100);
        Profile badValue=new Profile();
        UserPrefs.get(badValue).value="{\"version\":1,\"global\":{\"enabled\":true,\"scalePercent\":999,\"justify\":true}}";
        check(SandiumPageText.global(badValue).scalePercent==100);
        Profile future=new Profile();UserPrefs.get(future).value="{\"version\":2}";
        check(!SandiumPageText.global(future).enabled);
        ProfileManager.destroy(normal);
        check(SandiumPageText.packed(contents,a)==100);
        System.out.println(count+" profile/serialization/JNI assertions passed");
    }
}
