import java.util.LinkedHashMap;
import org.chromium.chrome.browser.ui.appmenu.RawSMenuModel;
import org.chromium.chrome.browser.ui.appmenu.RawSMenuPager;

public final class RawSMenuPagerTest {
    private static void check(boolean yes) { if (!yes) throw new AssertionError(); }
    private static final class Dispatch implements RawSMenuModel.Dispatcher<Object> {
        boolean enabled = true;
        int calls;
        public boolean canExecute(Object item) { return enabled; }
        public void execute(Object item) { calls++; }
    }
    public static void main(String[] args) {
        LinkedHashMap<String,Object> catalog = new LinkedHashMap<>();
        for (int i = 0; i < 23; i++) catalog.put("action_" + i, new Object());
        String saved = "raws-menu-v1\n";
        for (int i = 0; i < 23; i++) saved += "action_" + i + "\t" + (i < 10 ? "1" : "0") + "\n";
        RawSMenuModel<Object> state = new RawSMenuModel<>(saved); state.bind(catalog);
        RawSMenuPager<Object> pager = new RawSMenuPager<>(state);
        Dispatch dispatch = new Dispatch();
        check(pager.columns() == 4 && pager.rows() == 2 && pager.pageCount() == 2);
        check(pager.tiles().size() == 8 && pager.showPageIndicator());
        RawSMenuPager.Tile<Object> stale = pager.tiles().get(0);
        check(pager.movePage(1));
        check(!pager.activate(stale, dispatch));
        check(pager.tiles().size() == 3 && pager.tiles().get(2).kind == RawSMenuPager.Kind.ALL_MENU);
        check(!pager.movePage(1) && !pager.movePage(2));
        check(pager.activate(pager.tiles().get(2), dispatch));
        check(dispatch.calls == 0 && pager.isDirectory() && pager.rows() == 5);
        check(pager.tiles().size() == 20 && pager.pageCount() == 2);
        // Hidden quick actions remain reachable from All Menu, respecting live enablement.
        RawSMenuPager.Tile<Object> hidden = pager.tiles().get(12);
        dispatch.enabled = false; check(!pager.activate(hidden, dispatch));
        dispatch.enabled = true;
        check(pager.movePage(1) && pager.tiles().size() == 3);
        check(!pager.activate(hidden, dispatch));
        pager.setLargeText(true);
        check(pager.columns() == 2 && pager.pageCount() == 3 && pager.rows() == 5);
        check(pager.movePage(1));
        check(pager.backToQuick() && !pager.backToQuick());
        check(pager.page() == 0 && pager.rows() == 4);
        check(pager.movePage(1));
        check(pager.activate(pager.tiles().get(2), dispatch));
        check(pager.movePage(1));
        hidden = pager.tiles().get(2);
        check(hidden.entry.key.equals("action_12"));
        check(pager.activate(hidden, dispatch) && dispatch.calls == 1);
        check(!pager.activate(hidden, dispatch) && !pager.movePage(1));
        // Rebinding a tab's native catalog invalidates even a current visible action token.
        state.bind(catalog); pager = new RawSMenuPager<>(state);
        stale = pager.tiles().get(0); state.bind(catalog);
        check(!pager.activate(stale, dispatch)); pager.refresh();
        stale = pager.tiles().get(0); pager.close();
        check(!pager.activate(stale, dispatch));
        // Empty quick collection still exposes one All Menu tile. No pagination line.
        state = new RawSMenuModel<>("raws-menu-v1\naction_0\t0\n");
        catalog.clear(); catalog.put("action_0", new Object()); state.bind(catalog);
        pager = new RawSMenuPager<>(state);
        check(pager.tiles().size() == 1 && !pager.showPageIndicator());
        check(pager.activate(pager.tiles().get(0), dispatch));
        check(pager.tiles().size() == 1 && pager.tiles().get(0).entry.key.equals("action_0"));
        // Directory tokens issued before catalog replacement cannot bypass lifetime validation.
        RawSMenuModel.Entry<Object> token = state.directory().get(0);
        state.bind(catalog); check(!state.dispatch(token, dispatch));
        System.out.println("RawSMenuPagerTest passed");
    }
}
