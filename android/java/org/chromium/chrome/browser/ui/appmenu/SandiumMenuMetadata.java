package org.chromium.chrome.browser.ui.appmenu;

import org.chromium.ui.modelutil.PropertyModel;
import org.chromium.ui.modelutil.MVCListAdapter.ModelList;
import java.util.WeakHashMap;

/** Visibility migration only, never a source of actions or permission decisions. UI-thread only. */
public final class SandiumMenuMetadata {
    private static final WeakHashMap<PropertyModel, Boolean> LEGACY = new WeakHashMap<>();
    private static final WeakHashMap<Object, java.lang.ref.WeakReference<Runnable>> FOOTERS = new WeakHashMap<>();
    public static void watchFooter(Object footer, Runnable listener) {
        if (listener == null) FOOTERS.remove(footer);
        else FOOTERS.put(footer, new java.lang.ref.WeakReference<>(listener));
    }
    public static void footerChanged(Object footer) {
        java.lang.ref.WeakReference<Runnable> ref = FOOTERS.get(footer);
        Runnable listener = ref == null ? null : ref.get();
        if (listener != null) listener.run();
    }
    public interface FooterProvider { ModelList sandiumActions(); }
    private static final WeakHashMap<PropertyModel, Runnable> ACTIONS = new WeakHashMap<>();
    public static void action(PropertyModel model, Runnable action) { ACTIONS.put(model, action); }
    public static boolean dispatch(PropertyModel model) {
        Runnable action = ACTIONS.get(model);
        if (action == null) return false;
        action.run(); return true;
    }
    /** Optional numeric-only receiver. The producer MUST gate using the actual Profile.
     * No receiver means no recording (including unknown/private contexts).
     */
    public interface DiagnosticsSink { void record(int event, double[] values); }
    private static final WeakHashMap<ModelList, DiagnosticsSink> DIAGNOSTICS = new WeakHashMap<>();
    public static void diagnostics(ModelList models, DiagnosticsSink sink) {
        if (sink == null) DIAGNOSTICS.remove(models);
        else DIAGNOSTICS.put(models, sink);
    }
    public static void diagnostic(ModelList models, int event, double... values) {
        DiagnosticsSink sink = DIAGNOSTICS.get(models);
        if (sink != null) {
            try { sink.record(event, values); }
            catch (RuntimeException ignored) { /* Diagnostics must never break menu/save. */ }
        }
    }
    // Frozen product IDs, NOT Android's unstable resource integers or user strings.
    private static final String[] DIAGNOSTIC_KEYS = {
        "add_to_group_menu_id",
        "all_bookmarks_menu_id",
        "auto_dark_web_contents_id",
        "download_page_id",
        "downloads_menu_id",
        "exit_id",
        "find_in_page_id",
        "get_image_descriptions_id",
        "listen_to_feed_id",
        "manage_all_windows_menu_id",
        "move_to_other_window_menu_id",
        "new_incognito_tab_menu_id",
        "new_incognito_window_menu_id",
        "new_tab_menu_id",
        "new_window_menu_id",
        "open_history_menu_id",
        "open_with_id",
        "page_zoom_id",
        "paint_preview_show_id",
        "pin_tab_menu_id",
        "preferences_id",
        "print_id",
        "readaloud_menu_id",
        "reader_mode_menu_id",
        "recent_tabs_menu_id",
        "share_menu_id",
        "translate_id",
        "universal_install",
        "forward_menu_id",
        "bookmark_this_page_id",
        "homepage_menu_id",
        "reload_menu_id",
        "sandium_all_menu",
    };
    static long diagnosticFingerprint(java.util.List<String> keys, SandiumMenuState state) {
        long hash = 2166136261L;
        for (String key : keys) {
            int id = 0;
            for (int i = 0; i < DIAGNOSTIC_KEYS.length; i++) {
                if (DIAGNOSTIC_KEYS[i].equals(key)) { id = i + 1; break; }
            }
            // Unknown/custom identifiers never enter the fingerprint.
            if (id == 0) continue;
            hash = ((hash ^ (2 * id + (state != null && state.isHidden(key) ? 1 : 0)))
                    * 16777619L) & 0xffffffffL;
        }
        return hash;
    }
    private SandiumMenuMetadata() {}
    public static void record(PropertyModel model, boolean visible) { LEGACY.put(model, visible); }
    public static boolean wasVisible(PropertyModel model) {
        return !Boolean.FALSE.equals(LEGACY.get(model));
    }
}
