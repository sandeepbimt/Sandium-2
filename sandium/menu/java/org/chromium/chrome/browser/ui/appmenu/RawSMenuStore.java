package org.chromium.chrome.browser.ui.appmenu;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Looper;

/** Application-owned layout store. No browsing/profile contents are stored here. */
@SuppressWarnings("UseSharedPreferencesManagerFromChromeCheck")
final class RawSMenuStore implements RawSMenuModel.Store {
    private static final Object WRITE_LOCK = new Object();
    // Expose only a successfully committed layout while SharedPreferences updates its own cache
    // before a worker's disk write finishes. This namespace has no other writers.
    private static volatile String committed;
    private final SharedPreferences preferences;
    RawSMenuStore(Context context) {
        preferences = context.getApplicationContext().getSharedPreferences(
                "raws.menu.layout.v1", Context.MODE_PRIVATE);
        if (committed == null) {
            synchronized (WRITE_LOCK) {
                if (committed == null) committed = preferences.getString("layout", "");
            }
        }
    }
    @Override public String read() { return committed == null ? "" : committed; }
    @Override public boolean writeIfUnchanged(String expected, String value) {
        // Never acquire a disk writer's lock from the UI thread.
        if (Looper.myLooper() == Looper.getMainLooper())
            throw new IllegalStateException("Menu disk commit must run off the UI thread");
        synchronized (WRITE_LOCK) {
            return read().equals(expected) && write(value);
        }
    }
    @Override public boolean write(String value) {
        if (Looper.myLooper() == Looper.getMainLooper())
            throw new IllegalStateException("Menu disk commit must run off the UI thread");
        synchronized (WRITE_LOCK) {
            String before = read();
            try {
                if (preferences.edit().putString("layout", value).commit()) {
                    committed = value;
                    return true;
                }
            } catch (RuntimeException failure) {
                // Leave committed state and UI unchanged; editor can report failure/retry.
            }
            try {
                preferences.edit().putString("layout", before).commit();
            } catch (RuntimeException rollbackFailure) {
                // The visible snapshot still remains the last successful commit.
            }
            return false;
        }
    }
}
