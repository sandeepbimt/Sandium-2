"""Scoped lifecycle fixtures, not Android render tests."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from flash_mitigation import METHODS, OBSERVER, OBSERVER_SHA, OWNERS, TAB, transform

ROOT = Path(__file__).resolve().parents[1]
TAB_FIXTURE = ROOT.parent/"chromium-52bdd-preimages"/TAB


class Handoff(unittest.TestCase):
    def test_exact_source_replay_and_scope(self):
        obs = (ROOT/"raws-adblock"/"production-postimages"/OBSERVER_SHA).read_bytes()
        self.assertEqual(set(OWNERS), {TAB, OBSERVER})
        with self.assertRaises(ValueError):
            transform("other", obs)
        target = transform(OBSERVER, obs).decode()
        self.assertEqual(target.count("rawsOnTopLevelNavigationStarted(navigation)"), 1)
        self.assertEqual(target.count("rawsOnTopLevelNavigationFinishing(navigation)"), 1)
        self.assertIn("mTab.rawsOnPrimaryPagePresented(null)", target)
        self.assertIn("if (isKnownValid) mTab.rawsOnPrimaryPagePresented(url)", target)
        self.assertIn("RawSNavigationDiagnostics.Event.NAV_START", target)
        with self.assertRaises(ValueError):
            transform(OBSERVER, obs + b" ")
        if TAB_FIXTURE.exists():
            target = transform(TAB, TAB_FIXTURE.read_bytes()).decode()
            self.assertIn("pendingHomeDestination.equals(contents.getLastCommittedUrl())", target)
            self.assertIn("&& expected.equals(contents.getLastCommittedUrl())", target)
            self.assertIn("rawsClearHomeBacking(false);", target)
            self.assertNotIn("setPageBaseBackgroundColor(", target)
            with self.assertRaises(ValueError):
                transform(TAB, target.encode())  # Only exact preimage accepted.

    def test_emitted_lifecycle_method_state(self):
        content = """
public class HandoffTest {
    @interface Nullable {}
    static final class NetError { static final int OK = 0; }
    static final class Color {
        static int alpha(int i) { return i >>> 24; }
        static float luminance(int i) { return (i & 255) / 255.0f; }
    }
    static final class Configuration {
        static final int UI_MODE_NIGHT_MASK=0x30, UI_MODE_NIGHT_YES=0x20;
        int uiMode=0x20;
    }
    static final class Resources {
        final Configuration config=new Configuration();
        Configuration getConfiguration() { return config; }
    }
    static final class Context {
        final Resources res=new Resources();
        String packageName="io.github.sandeepbimt.raws";
        String getPackageName() { return packageName; }
        Resources getResources() { return res; }
    }
    interface NativePage {
        boolean isFrozen(); int getBackgroundColor();
    }
    static final class NewTabPage implements NativePage {
        int color = 0xff151515;
        public boolean isFrozen() { return false; }
        public int getBackgroundColor() { return color; }
    }
    record GURL(String url) {
        boolean isValid() { return url.contains("://"); }
        String getScheme() { return url.split(":")[0]; }
    }
    static final class WebContents {
        GURL last = new GURL("chrome://newtab/");
        int color = 0xffffffff;
        boolean loading = false;
        GURL getLastCommittedUrl() { return last; }
        int getBackgroundColor() { return color; }
        boolean isLoading() { return loading; }
    }
    record NavigationHandle(long id, GURL url, boolean same, boolean renderer,
                            boolean history, boolean commit, boolean error,
                            boolean download, boolean pdf) {
        boolean isInPrimaryMainFrame() { return true; }
        boolean isSameDocument() { return same; }
        boolean isRendererInitiated() { return renderer; }
        boolean isHistory() { return history; }
        GURL getUrl() { return url; }
        long getNavigationId() { return id; }
        boolean hasCommitted() { return commit; }
        boolean isErrorPage() { return error; }
        int errorCode() { return error ? -1 : 0; }
        boolean isDownload() { return download; }
        boolean isPdf() { return pdf; }
    }
    final Context context = new Context();
    NativePage mNativePage = new NewTabPage();
    WebContents mWebContents = new WebContents();
    long mRawSHomeBackingNavigation;
    GURL mRawSHomeBackingUrl;
    int mRawSHomeBackingColor;
    int mWebContentBackgroundColor;
    boolean hidden, privateTab;
    int updates;
    java.lang.ref.WeakReference<Context> getActivityContext() {
        return new java.lang.ref.WeakReference<>(context);
    }
    boolean isHidden() { return hidden; }
    boolean isIncognito() { return privateTab; }
    void onBackgroundColorChanged() { updates++; }
""" + METHODS + """
    NavigationHandle nav(int id) {
        return new NavigationHandle(id,new GURL("https://example.test/"),
            false,false,false,true,false,false,false);
    }
    void require(boolean value) { if (!value) throw new AssertionError(); }
    void test() {
        rawsOnTopLevelNavigationStarted(nav(1));
        rawsOnTopLevelNavigationStarted(nav(2));
        rawsOnTopLevelNavigationFinishing(nav(1));
        require(mRawSHomeBackingUrl == null);
        rawsOnTopLevelNavigationFinishing(nav(2));
        require(mRawSHomeBackingUrl.equals(nav(2).getUrl()) && mRawSHomeBackingColor == 0xff151515);
        rawsOnPrimaryPagePresented(null); // old native still showing
        require(mRawSHomeBackingUrl != null && updates == 0);
        mNativePage = null;
        rawsOnPrimaryPagePresented(null); // stale committed page
        require(mRawSHomeBackingUrl != null);
        mWebContents.last = nav(2).getUrl();
        mWebContents.loading = true;
        rawsOnPrimaryPagePresented(nav(2).getUrl()); // not a settled blank page
        require(mRawSHomeBackingUrl != null);
        rawsOnPrimaryPagePresented(null);
        require(mRawSHomeBackingUrl == null && mWebContentBackgroundColor == 0xffffffff && updates == 1);
        mNativePage = new NewTabPage();
        privateTab = true;
        rawsOnTopLevelNavigationStarted(nav(3));
        require(mRawSHomeBackingNavigation == 0);
        privateTab=false;
        context.res.config.uiMode=0x10; // ordinary light theme
        rawsOnTopLevelNavigationStarted(nav(3));
        require(mRawSHomeBackingNavigation == 0);
        context.res.config.uiMode=0x20;
        rawsOnTopLevelNavigationStarted(new NavigationHandle(4,nav(4).getUrl(),
            false,true,false,true,false,false,false));
        require(mRawSHomeBackingNavigation == 0);
        rawsOnTopLevelNavigationStarted(nav(5));
        rawsOnTopLevelNavigationFinishing(new NavigationHandle(5,nav(5).getUrl(),
            false,false,false,false,false,false,false));
        require(mRawSHomeBackingUrl == null && mRawSHomeBackingNavigation == 0);
        ((NewTabPage)mNativePage).color=0xffffffff;
        rawsOnTopLevelNavigationStarted(nav(6)); rawsOnTopLevelNavigationFinishing(nav(6));
        require(mRawSHomeBackingColor == 0xff121212);
        rawsClearHomeBacking(false);
        require(mRawSHomeBackingNavigation == 0 && mRawSHomeBackingUrl == null);
        System.out.println("Home lease: superseded, abort, real paint, private/light, no synthetic page paint PASS");
    }
    public static void main(String[] args) { new HandoffTest().test(); }
}
"""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"HandoffTest.java"
            path.write_text(content)
            subprocess.run(
                ["java", "-m", "jdk.compiler/com.sun.tools.javac.Main",
                 "-Xlint:all", "-Werror", str(path)], check=True)
            subprocess.run(["java", "-cp", d, "HandoffTest"], check=True)


if __name__ == "__main__":
    unittest.main()
