package org.chromium.chrome.browser.ui.appmenu;

import android.content.Context;
import android.content.SharedPreferences;

/** One application-scoped store for both reads and writes, independent of popup context. */
@SuppressWarnings("UseSharedPreferencesManagerFromChromeCheck")
final class SandiumMenuPreferences {
    private static final String FILE = "sandium.menu.layout.v1";
    private static final String KEY = "layout";
    private final SharedPreferences mPreferences;

    SandiumMenuPreferences(Context context) {
        Context app = context.getApplicationContext();
        mPreferences = (app == null ? context : app).getSharedPreferences(FILE, Context.MODE_PRIVATE);
        // Preserve a layout saved by an older activity/scoped-context implementation.
        // Never replace an existing application layout with a stale activity snapshot.
        if (!mPreferences.contains(KEY)) {
            String legacy = context.getSharedPreferences(FILE, Context.MODE_PRIVATE).getString(KEY, null);
            if (legacy != null) save(legacy);
        }
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
