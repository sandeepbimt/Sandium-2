import org.chromium.chrome.browser.sandium.text.PageTextPolicy;
import org.chromium.chrome.browser.sandium.text.PageTextStylesheet;

public final class PageTextPolicyTest {
    private static int assertions;
    private static void check(boolean value) {
        assertions++;
        if (!value) throw new AssertionError("check " + assertions);
    }
    private static void rejects(Runnable operation) {
        try { operation.run(); throw new AssertionError("Expected rejection"); }
        catch (IllegalArgumentException | IllegalStateException expected) { assertions++; }
    }
    private static final class Store implements PageTextPolicy.Store {
        PageTextPolicy.Settings global;
        int writes;
        boolean fail;
        public PageTextPolicy.Settings readGlobal() { return global; }
        public void writeGlobal(PageTextPolicy.Settings value) {
            if (fail) throw new IllegalStateException("save failed");
            writes++; global = value;
        }
    }
    public static void main(String[] args) {
        Store store = new Store();
        PageTextPolicy regular = new PageTextPolicy(store, false);
        PageTextPolicy.Settings enabled = new PageTextPolicy.Settings(true,110,true);
        check(regular.global() == PageTextPolicy.DEFAULT);
        check(PageTextStylesheet.compile(regular.global()).isEmpty());
        regular.setGlobal(enabled);
        check(regular.global() == enabled);
        check(new PageTextPolicy(store,false).global() == enabled);
        int writes=store.writes;
        PageTextPolicy incognito = new PageTextPolicy(store,true);
        check(incognito.global() == enabled);
        incognito.setGlobal(PageTextPolicy.DEFAULT);
        check(incognito.global() == PageTextPolicy.DEFAULT);
        check(regular.global() == enabled);
        check(store.writes == writes);
        incognito.close();rejects(incognito::global);
        check(new PageTextPolicy(store,true).global() == enabled);
        store.fail=true;
        rejects(() -> regular.setGlobal(PageTextPolicy.DEFAULT));
        check(regular.global() == enabled);store.fail=false;
        String css = PageTextStylesheet.compile(enabled);
        check(!css.contains("font-size"));
        check(css.contains("text-align:justify !important;"));
        check(!css.contains("font-family"));
        check(!css.contains("line-height"));
        check(!css.contains("text-wrap"));
        check(!css.contains("transition"));
        check(!css.contains("body p"));
        check(!css.contains("main p"));
        check(css.contains("[contenteditable]:not([contenteditable=false])"));
        check(PageTextStylesheet.compile(new PageTextPolicy.Settings(false,
                150, true)).contains("text-size-adjust:150%"));
        check(PageTextStylesheet.compile(new PageTextPolicy.Settings(true,
                100, false)).isEmpty());
        String justifyOnly = PageTextStylesheet.compile(new PageTextPolicy.Settings(true,
                100, true));
        check(!justifyOnly.contains("font-size"));
        for (int size = PageTextPolicy.MIN_SCALE; size <= PageTextPolicy.MAX_SCALE;
                size += PageTextPolicy.SCALE_STEP) {
            String sheet = PageTextStylesheet.compile(new PageTextPolicy.Settings(true, size, true));
            check(sheet.length() < 1200);
            check(!sheet.contains("url("));
        }
        rejects(() -> new PageTextPolicy.Settings(false, 74, false));
        rejects(() -> new PageTextPolicy.Settings(false, 151, false));
        rejects(() -> new PageTextPolicy.Settings(false, 101, false));
        // Size is independent of typography: native text adjustment applies without justify.
        PageTextPolicy.Settings scaledOnly = new PageTextPolicy.Settings(false, 125, false);
        regular.setGlobal(scaledOnly);
        check(regular.global().scalePercent == 125);
        check(PageTextStylesheet.compile(scaledOnly).contains("text-size-adjust:125%"));
        check(!PageTextStylesheet.compile(scaledOnly).contains("text-align"));
        regular.close();
        rejects(regular::global);
        System.out.println(assertions + " page-text model/compiler assertions passed");
    }
}
