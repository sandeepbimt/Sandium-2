package org.chromium.chrome.browser.ui.appmenu;
import java.util.*;

public class SandiumMenuStateTest {
    static final List<String> DEFAULT = Arrays.asList("new", "private", "history", "downloads", "bookmarks", "recent", "find", "translate", "reader", "install", "desktop", "shred", "settings", "default", "exit");
    static Set<String> set(Collection<String> input) { return new HashSet<>(input); }
    static void check(boolean value) { if (!value) throw new AssertionError(); }
    static void equal(Object expected, Object actual) {
        if (!Objects.equals(expected, actual)) throw new AssertionError(expected + " != " + actual);
    }
    static void exitLifecycleAndConditionalPlacement() {
        Set<String> all = set(DEFAULT);
        SandiumMenuState original = SandiumMenuState.reset(DEFAULT, Set.of("reader"));
        SandiumMenuState draft = original.copy();
        // Exact editor lifecycle: page 2 -> page 1 -> page 2, remove, re-add, Done/restart.
        check(draft.moveToPage("exit", 0, 2, 8, all));
        equal("exit", draft.page(all, 0, 8).get(2));
        check(draft.moveToPage("exit", 1, 1, 8, all));
        equal("exit", draft.page(all, 1, 8).get(1));
        check(draft.hide("exit"));
        check(!draft.visibleKeys(all).contains("exit"));
        check(draft.hiddenKeys(all).contains("exit"));
        check(draft.show("exit"));
        equal("exit", draft.page(all, 1, 8).get(1));
        String saved = draft.serialize();
        SandiumMenuState restart = SandiumMenuState.load(saved, DEFAULT, Set.of("exit"));
        equal(saved, restart.serialize());
        equal("exit", restart.page(all, 1, 8).get(1));
        // Reset is a new draft, does not mutate the committed instance or reuse legacy hide.
        SandiumMenuState resetDraft = SandiumMenuState.reset(DEFAULT, Set.of("reader"));
        equal(saved, restart.serialize());
        check(resetDraft.isHidden("reader"));
        check(!resetDraft.isHidden("exit"));
        List<String> expected = new ArrayList<>(DEFAULT); expected.remove("reader");
        equal(expected, resetDraft.visibleKeys(all));
        equal(List.of("reader"), resetDraft.hiddenKeys(all));
        equal(resetDraft.serialize(), SandiumMenuState.load(resetDraft.serialize(), DEFAULT,
                Set.of("exit")).serialize());

        // Conditional action returns to its saved position even across a restart while absent.
        SandiumMenuState conditional = SandiumMenuState.reset(DEFAULT, Set.of());
        check(conditional.move("install", 3, all));
        String beforeAbsence = conditional.serialize();
        Set<String> withoutInstall = set(DEFAULT); withoutInstall.remove("install");
        check(!conditional.visibleKeys(withoutInstall).contains("install"));
        equal(beforeAbsence, conditional.serialize());
        List<String> temporaryCatalog = new ArrayList<>(DEFAULT); temporaryCatalog.remove("install");
        conditional = SandiumMenuState.load(conditional.serialize(), temporaryCatalog, Set.of());
        equal(beforeAbsence, conditional.serialize());
        conditional.reconcile(DEFAULT, Set.of());
        equal("install", conditional.visibleKeys(all).get(3));
        // Accessibility buttons use these same index moves: next, previous, page jump.
        check(conditional.move("install", 4, all));
        equal("install", conditional.visibleKeys(all).get(4));
        check(conditional.move("install", 3, all));
        equal("install", conditional.visibleKeys(all).get(3));
        check(conditional.moveToPage("install", 1, 0, 8, all));
        equal("install", conditional.page(all, 1, 8).get(0));
        check(conditional.moveToPage("install", 0, 0, 8, all));
        equal("install", conditional.page(all, 0, 8).get(0));
        check(!conditional.move("install", -1, all)); // Already first: bounded no-op.
        check(!conditional.move("install", 5, withoutInstall));
    }
    public static void main(String[] args) {
        exitLifecycleAndConditionalPlacement();
        Set<String> available = set(DEFAULT);
        SandiumMenuState state = SandiumMenuState.load(null, DEFAULT, Set.of("exit"));
        equal(14, state.visibleKeys(available).size());
        check(state.isHidden("exit"));
        check(state.show("exit"));
        check(state.move("exit", 0, available));
        equal("exit", state.visibleKeys(available).get(0));
        check(state.hide("exit"));
        equal(List.of("exit"), state.hiddenKeys(available));
        check(state.show("exit"));
        equal("exit", state.visibleKeys(available).get(0));
        // Legacy hidden preference must not re-hide a user-readded item after restart.
        SandiumMenuState restarted = SandiumMenuState.load(state.serialize(), DEFAULT, Set.of("exit"));
        equal(state.serialize(), restarted.serialize());
        // Missing/conditional actions retained, never shown while unavailable.
        available.remove("translate"); available.remove("exit");
        check(!state.visibleKeys(available).contains("translate"));
        check(!state.move("exit", 0, available));
        state.reconcile(List.of("new", "other"), Set.of("other"));
        check(state.isHidden("other"));
        available.add("translate"); available.add("exit");
        check(state.visibleKeys(available).contains("translate"));
        check(state.moveToPage("exit", 1, 0, 8, available));
        equal("exit", state.page(available, 1, 8).get(0));
        equal(2, state.pageCount(available, 8));
        check(state.moveToPage("exit", Integer.MAX_VALUE, 7, 8, available));
        equal("exit", state.visibleKeys(available).get(14));
        check(!state.moveToPage("exit", -1, 0, 8, available));
        // Draft transaction is isolated until caller explicitly replaces committed state.
        String committed = state.serialize();
        SandiumMenuState draft = state.copy(); draft.hide("history"); draft.move("new", 10, available);
        equal(committed, state.serialize());
        check(!committed.equals(draft.serialize()));
        // Reset accepts complete product defaults, drops old layout/unknown keys.
        SandiumMenuState reset = SandiumMenuState.reset(DEFAULT, Set.of());
        equal(DEFAULT, reset.visibleKeys(set(DEFAULT)));
        // Invalid serialization never partially applies and ignores malformed preference data.
        for (String corrupt : List.of("bad", "sandium-menu-v2\nexit\t0\n",
                "sandium-menu-v1\nexit\t0\nexit\t1\n", "sandium-menu-v1\nexit\tx\n",
                "sandium-menu-v1\nexit\t0\njunk", "sandium-menu-v1\n../bad\t1\n")) {
            equal(DEFAULT, SandiumMenuState.load(corrupt, DEFAULT, Set.of()).visibleKeys(set(DEFAULT)));
        }
        // Empty catalog, invalid page size and large indexes remain bounded.
        equal(1, reset.pageCount(Set.of(), 8));
        equal(List.of(), reset.page(available, Integer.MAX_VALUE, 8));
        equal(0, reset.pageCount(available, 0));
        check(!reset.hide("unknown")); check(!reset.show("unknown"));
        check(!reset.move("unknown", 0, available));
        // Stable string IDs survive resource integer changes; new catalog values append once.
        SandiumMenuState unknown = SandiumMenuState.load("sandium-menu-v1\nfuture_action\t1\n", DEFAULT, Set.of());
        check(unknown.isHidden("future_action"));
        unknown.reconcile(DEFAULT, Set.of());
        equal(16L, unknown.serialize().lines().count() - 1L);
        // Random reorder operations must neither duplicate/drop entries nor expose hidden items.
        Random random = new Random(1144);
        SandiumMenuState fuzz = SandiumMenuState.reset(DEFAULT, Set.of());
        Set<String> all = set(DEFAULT);
        for (int step = 0; step < 1000; step++) {
            String key = DEFAULT.get(random.nextInt(DEFAULT.size()));
            int operation = random.nextInt(3);
            if (operation == 0) fuzz.hide(key);
            else if (operation == 1) fuzz.show(key);
            else fuzz.move(key, random.nextInt(30) - 5, all);
            List<String> visible = fuzz.visibleKeys(all);
            List<String> hidden = fuzz.hiddenKeys(all);
            Set<String> union = set(visible); union.addAll(hidden);
            equal(all, union);
            equal(DEFAULT.size(), visible.size() + hidden.size());
            equal(fuzz.serialize(), SandiumMenuState.load(fuzz.serialize(), DEFAULT,
                    Set.of("exit")).serialize());
        }
        System.out.println("SandiumMenuState tests passed");
    }
}
