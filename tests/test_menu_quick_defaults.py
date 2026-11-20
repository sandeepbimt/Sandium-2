"""Run the actual Java state model; guard constructor, refresh, and Reset wiring."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

JAVA = (Path(__file__).resolve().parents[1] /
        'android/java/org/chromium/chrome/browser/ui/appmenu')


class QuickDefaults(unittest.TestCase):
    def test_phone_menu_wiring(self):
        source = (JAVA / 'SandiumPagedMenu.java').read_text()
        self.assertIn('loadQuickLayout(loadedLayout, mCatalog.keySet(), hidden, mRecentTabs)', source)
        self.assertIn('quickDefaultHidden(legacy, mRecentTabs)', source)
        self.assertIn('mSaved.reconcile(mCatalog.keySet(), hidden)', source)
        self.assertIn('mDraft.reconcile(mCatalog.keySet(), hidden)', source)
        self.assertIn('SandiumMenuState.reset(SandiumMenuState.quickDefaultOrder(defaults, mRecentTabs)', source)
        self.assertIn('quickDefaultHidden(java.util.Collections.emptySet(), mRecentTabs)', source)
        self.assertIn('visibleKeysWithTrailing(quickAvailable(), ALL_MENU)', source)
        self.assertIn('for (String key : LIBRARY) if (mCatalog.containsKey(key))', source)

    @unittest.skipUnless(shutil.which('java'), 'Java runtime unavailable')
    def test_clean_reset_recovered_preferences_and_conditional_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = Path(directory) / 'QuickDefaultsTest.java'
            runner.write_text('''package org.chromium.chrome.browser.ui.appmenu;
import java.util.*;
public final class QuickDefaultsTest {
    static void eq(Object a, Object b) {
        if (!a.equals(b)) throw new AssertionError(a + " != " + b);
    }
    public static void main(String[] args) {
        List<String> approved = List.of(
            "new_tab_menu_id", "new_incognito_tab_menu_id", "find_in_page_id",
            "request_desktop_site_id", "sandium_add_home_shortcut", "brave_shred_id",
            "reload_menu_id", "exit_id", "share_menu_id", "download_page_id",
            "bookmark_this_page_id", "universal_install", "reader_mode_menu_id", "translate_id");
        List<String> hidden = List.of(
            "add_to_group_menu_id", "info_menu_id", "recent_tabs_menu_id", "home_menu_id");
        List<String> live = new ArrayList<>(approved);
        live.addAll(hidden);
        Collections.reverse(live);
        live.add("platform_extra");
        Set<String> available = Set.copyOf(live);
        SandiumMenuState fresh =
                SandiumMenuState.loadQuickLayout(null, live, Set.of("platform_extra"), false);
        eq(approved, fresh.visibleKeys(available));
        eq(14, fresh.visibleKeys(available).size());
        List<String> expectedHidden = new ArrayList<>(hidden);
        expectedHidden.add("platform_extra");
        eq(expectedHidden, fresh.hiddenKeys(available));
        SandiumMenuState reset = SandiumMenuState.reset(
                SandiumMenuState.quickDefaultOrder(live, false), SandiumMenuState.quickDefaultHidden(Set.of(), false));
        List<String> resetVisible = new ArrayList<>(approved);
        resetVisible.add("platform_extra");
        eq(resetVisible, reset.visibleKeys(available));
        eq(hidden, reset.hiddenKeys(available));
        List<String> recentOrder = List.of("new_tab_menu_id", "new_incognito_tab_menu_id",
                "add_to_group_menu_id", "recent_tabs_menu_id", "home_menu_id", "reload_menu_id",
                "info_menu_id", "exit_id");
        List<String> recentHidden = List.of("sandium_add_home_shortcut", "bookmark_this_page_id",
                "download_page_id", "share_menu_id");
        List<String> recentLive = new ArrayList<>(recentOrder);
        recentLive.addAll(recentHidden);
        Collections.reverse(recentLive);
        SandiumMenuState recent = SandiumMenuState.loadQuickLayout(null, recentLive, Set.of(), true);
        eq(recentOrder, recent.visibleKeys(Set.copyOf(recentLive)));
        eq(8, recent.visibleKeys(Set.copyOf(recentLive)).size());
        eq(recentHidden, recent.hiddenKeys(Set.copyOf(recentLive)));
        eq(true, recent.show("share_menu_id"));
        eq(false, recent.isHidden("share_menu_id"));
        eq(9, recent.visibleKeys(Set.copyOf(recentLive)).size());
        SandiumMenuState recentReset = SandiumMenuState.reset(
                SandiumMenuState.quickDefaultOrder(recentLive, true),
                SandiumMenuState.quickDefaultHidden(Set.of(), true));
        eq(recentOrder, recentReset.visibleKeys(Set.copyOf(recentLive)));
        eq(recentHidden, recentReset.hiddenKeys(Set.copyOf(recentLive)));
        String prior = "sandium-menu-v1\\nreload_menu_id\\t0\\nhome_menu_id\\t0\\n"
                + "new_tab_menu_id\\t1\\nunavailable_key\\t1\\n    ";
        SandiumMenuState restored = SandiumMenuState.loadQuickLayout(prior, live, Set.of(), false);
        eq(List.of("reload_menu_id", "home_menu_id", "new_tab_menu_id", "unavailable_key"),
                restored.knownKeys().subList(0, 4));
        eq(false, restored.isHidden("home_menu_id"));
        eq(true, restored.isHidden("new_tab_menu_id"));
        eq(true, restored.isHidden("unavailable_key"));
        eq(true, restored.isHidden("info_menu_id")); // newly discovered only
        eq(live.get(0), SandiumMenuState.loadQuickLayout("sandium-menu-v1", live, Set.of(), false)
                .knownKeys().get(0)); // valid empty layout is not a missing layout
        List<String> sparse = List.of("translate_id", "new_incognito_window_menu_id",
                "new_tab_menu_id");
        SandiumMenuState conditional = SandiumMenuState.loadQuickLayout(null, sparse, Set.of(), false);
        eq(List.of("new_tab_menu_id", "new_incognito_window_menu_id", "translate_id"),
                conditional.knownKeys());
        conditional.reconcile(List.of("home_menu_id", "universal_install"),
                SandiumMenuState.quickDefaultHidden(Set.of(), false));
        eq(List.of("new_tab_menu_id", "new_incognito_window_menu_id", "translate_id",
                    "home_menu_id", "universal_install"), conditional.knownKeys());
        eq(true, conditional.isHidden("home_menu_id"));
        eq(false, conditional.isHidden("universal_install"));
        eq(true, conditional.show("home_menu_id"));
        conditional.reconcile(List.of("home_menu_id"), SandiumMenuState.quickDefaultHidden(Set.of(), false));
        eq(false, conditional.isHidden("home_menu_id"));
    }
}
''')
            subprocess.run(['java', 'com.sun.tools.javac.Main', '-d', directory,
                            str(JAVA / 'SandiumMenuState.java'), str(runner)], check=True)
            subprocess.run(['java', '-cp', directory,
                            'org.chromium.chrome.browser.ui.appmenu.QuickDefaultsTest'], check=True)


if __name__ == '__main__':
    unittest.main()
