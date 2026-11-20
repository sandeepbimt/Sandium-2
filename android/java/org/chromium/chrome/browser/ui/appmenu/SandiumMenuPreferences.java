package org.chromium.chrome.browser.ui.appmenu;

import android.content.Context;
import android.content.SharedPreferences;

/** One application-scoped store for both reads and writes, independent of popup context. */
@SuppressWarnings("UseSharedPreferencesManagerFromChromeCheck")
public final class SandiumMenuPreferences {
    private static final String FILE = "sandium.menu.layout.v1";
    private static final String KEY = "layout";
    private static final String RECENT_KEY = "layout.recent-tabs";
    private final SharedPreferences mPreferences;

    public SandiumMenuPreferences(Context context) {
        Context app = context.getApplicationContext();
        mPreferences = (app == null ? context : app).getSharedPreferences(FILE, Context.MODE_PRIVATE);
        // Preserve a layout saved by an older activity/scoped-context implementation.
        // Never replace an existing application layout with a stale activity snapshot.
        if (!mPreferences.contains(KEY)) {
            String legacy = context.getSharedPreferences(FILE, Context.MODE_PRIVATE).getString(KEY, null);
            if (legacy != null) save(legacy, false, false);
        }
    }

    /** Native settings and the phone editor share the same canonical visibility. */
    public boolean isVisible(String key, boolean legacyDefault) {
        SandiumMenuState state = SandiumMenuState.load(load(), java.util.Collections.emptyList(),
                java.util.Collections.emptySet());
        return state.knownKeys().contains(key) ? !state.isHidden(key) : legacyDefault;
    }

    /** Change just this item's membership, preserving order and all unavailable items. */
    public boolean setVisible(String key, boolean visible) {
        if (key == null || !key.matches("[A-Za-z0-9_.:-]+") || key.length() > 200) return false;
        String saved = load();
        if (!saved.isEmpty() && !SandiumMenuState.isValidSavedLayout(saved)) return false;
        SandiumMenuState state = SandiumMenuState.load(saved, java.util.Collections.singleton(key),
                java.util.Collections.emptySet());
        if (!state.knownKeys().contains(key)) return false;
        if (visible) state.show(key);
        else state.hide(key);
        return save(state.serialize());
    }

    String load() { return mPreferences.getString(KEY, ""); }

    String load(boolean recentTabs) {
        if (!recentTabs) return load();
        String recent = mPreferences.getString(RECENT_KEY, null);
        if (recent != null) return recent;
        String legacy = load();
        return SandiumMenuState.isValidSavedLayout(legacy) ? legacy : "";
    }

    boolean save(String layout) { return save(layout, false); }

    boolean save(String layout, boolean recentTabs) { return save(layout, recentTabs, true); }

    // Freeze any actually inherited old global layout at the first new web write, without
    // copying into the global key or writing anything just because the popup was opened.
    @android.annotation.SuppressLint("ApplySharedPref")
    private boolean save(String layout, boolean recentTabs, boolean userWrite) {
        android.os.StrictMode.ThreadPolicy policy = android.os.StrictMode.allowThreadDiskWrites();
        try {
            String key = recentTabs ? RECENT_KEY : KEY;
            String previous = mPreferences.getString(key, null);
            boolean freezeInherited = userWrite && !recentTabs && !mPreferences.contains(RECENT_KEY);
            SharedPreferences.Editor editor = mPreferences.edit().putString(key, layout);
            if (freezeInherited) {
                editor.putString(RECENT_KEY,
                        SandiumMenuState.isValidSavedLayout(previous) ? previous : "");
            }
            boolean committed = editor.commit();
            // Android updates its process cache before the disk result. Restore both keys
            // if the transaction failed, including the prior missing/inheriting state.
            if (!committed) {
                SharedPreferences.Editor restore = mPreferences.edit();
                if (previous == null) restore.remove(key);
                else restore.putString(key, previous);
                if (freezeInherited) restore.remove(RECENT_KEY);
                restore.commit();
            }
            return committed;
        } finally {
            android.os.StrictMode.setThreadPolicy(policy);
        }
    }
}
