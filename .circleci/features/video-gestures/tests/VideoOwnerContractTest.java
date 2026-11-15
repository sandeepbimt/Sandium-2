import android.app.Activity;
import android.widget.Button;
import org.chromium.chrome.browser.ActivityTabProvider;
import org.chromium.chrome.browser.tab.Tab;
import org.chromium.content_public.browser.*;
import org.chromium.services.media_session.MediaPosition;
import org.chromium.chrome.browser.sandium.video.*;
public class VideoOwnerContractTest {
    static int checks;
    static void check(boolean b){checks++;if(!b)throw new AssertionError("check "+checks);}
    static Object field(Object o,String n) throws Exception {var f=o.getClass().getDeclaredField(n);f.setAccessible(true);return f.get(o);}
    static void fresh(WebContents c){var n=new NavigationHandle();c.observer.didStartNavigationInPrimaryMainFrame(n);c.observer.didFinishNavigationInPrimaryMainFrame(n);}
    static void video(WebContents c){c.observer.mediaStartedPlaying(1,true,true);c.observer.hasEffectivelyFullscreenVideoChange(true);}
    static void enable(SandiumVideoController c) throws Exception {((Button)field(c,"mEnable")).performClick();}
    static SandiumVideoSessionAdapter adapter(SandiumVideoController c)throws Exception{return (SandiumVideoSessionAdapter)field(c,"mAdapter");}
    public static void main(String[] args)throws Exception {
        var a=new Activity();var p=new ActivityTabProvider();var w=new WebContents();p.tab=new Tab(w);
        var c=new SandiumVideoController(a,p);
        video(w);enable(c);check(adapter(c)==null); // attached mid-document: fail closed
        fresh(w);video(w);w.session.destroy();enable(c);check(adapter(c)==null);
        w.session=new MediaSession();w.observer.mediaSessionCreated(w.session);
        var restored=new NavigationHandle();restored.activation=true;
        w.observer.didStartNavigationInPrimaryMainFrame(restored);
        w.observer.didFinishNavigationInPrimaryMainFrame(restored);video(w);enable(c);check(adapter(c)==null);
        fresh(w);video(w);enable(c);check(adapter(c)!=null);
        var ad=adapter(c);check(ad.isEligible());check(ad.canSeek()); // cached replay, timestamp >60s old
        ad.seekBy(10000);check(w.session.target==140000); // 30s + 100s extrapolated + 10s
        ad.seekBy(Long.MAX_VALUE);check(w.session.target==300000);
        ad.seekBy(Long.MIN_VALUE);check(w.session.target==0);
        ad.beginAdjustment();ad.adjustBrightness(.1);check(a.window.getAttributes().screenBrightness>=0);
        c.setResumed(false);check(adapter(c)==null && a.window.getAttributes().screenBrightness==-1);
        check(w.observer!=null);c.setResumed(true);enable(c);check(adapter(c)!=null);
        c.setResumed(false);w.session.destroy();c.setResumed(true);enable(c);check(adapter(c)==null);
        w.session=new MediaSession();w.observer.mediaSessionCreated(w.session);enable(c);check(adapter(c)!=null);
        ad=adapter(c);c.close();check(w.observer==null && p.observer==null);c.close();check(!ad.isEligible());
        c=new SandiumVideoController(a,p);fresh(w);video(w);enable(c);
        var original=w.session;fresh(w);video(w);enable(c);check(w.session==original && adapter(c)!=null);
        w.observer.mediaStartedPlaying(2,true,false);check(adapter(c)==null); // second media ambiguous
        fresh(w);video(w);enable(c);check(adapter(c)!=null);
        w.session.destroy();check(adapter(c)==null);
        c.close();
        w.session=new MediaSession();c=new SandiumVideoController(a,p);fresh(w);video(w);enable(c);
        p.change(new Tab(new WebContents()));check(adapter(c)==null && w.observer==null);
        c.close();
        p.tab=new Tab(w);c=new SandiumVideoController(a,p);fresh(w);video(w);enable(c);
        w.session.position=new MediaPosition(Long.MAX_VALUE,1,1,0);
        for(var o:java.util.List.copyOf(w.session.observers))o.mediaSessionPositionChanged(w.session.position);
        check(!adapter(c).canSeek());check(!((Button)field(c,"mSeekBack")).enabled);
        a.pip=true;check(!adapter(c).isEligible());a.pip=false;c.close();
        check(a.window.getDecorView() instanceof android.view.ViewGroup);
        check(((android.view.ViewGroup)a.window.getDecorView()).children.isEmpty());
        System.out.println(checks+" owner/adapter contract checks passed against test doubles (not Android/Chromium runtime)");
    }
}
