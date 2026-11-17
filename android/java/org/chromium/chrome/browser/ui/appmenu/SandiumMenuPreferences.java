package org.chromium.chrome.browser.ui.appmenu;

import android.content.Context;
import android.content.SharedPreferences;

/** One application-scoped store for both reads and writes, independent of popup context. */
@SuppressWarnings("UseSharedPreferencesManagerFromChromeCheck")
public final class SandiumMenuPreferences {
    private static final String FILE = "sandium.menu.layout.v1";
    private static final String KEY = "layout";
    private final SharedPreferences mPreferences;

    public SandiumMenuPreferences(Context context) {
        Context app = context.getApplicationContext();
        mPreferences = (app == null ? context : app).getSharedPreferences(FILE, Context.MODE_PRIVATE);
        // Preserve a layout saved by an older activity/scoped-context implementation.
        // Never replace an existing application layout with a stale activity snapshot.
        if (!mPreferences.contains(KEY)) {
            String legacy = context.getSharedPreferences(FILE, Context.MODE_PRIVATE).getString(KEY, null);
            if (legacy != null) save(legacy);
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

    boolean save(String layout) {
        android.os.StrictMode.ThreadPolicy policy = android.os.StrictMode.allowThreadDiskWrites();
        try {
            String previous = load();
            boolean committed = mPreferences.edit().putString(KEY, layout).commit();
            // Android updates its process cache before the disk result. Restore that
            // cache on failure, so reopening the menu cannot show an unsaved value.
            if (!committed) mPreferences.edit().putString(KEY, previous).commit();
            return committed;
        } finally {
            android.os.StrictMode.setThreadPolicy(policy);
        }
    }
}
