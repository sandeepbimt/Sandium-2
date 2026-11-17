// Copyright 2026 Sandium Authors. All rights reserved.
package org.chromium.chrome.browser.sandium.text;

import org.json.JSONException;
import org.json.JSONObject;
import org.chromium.base.ThreadUtils;
import org.chromium.chrome.browser.profiles.Profile;
import org.chromium.chrome.browser.profiles.ProfileManager;
import org.chromium.components.user_prefs.UserPrefs;
import org.chromium.content_public.browser.WebContents;
import org.chromium.url.GURL;
import java.util.HashMap;
import java.util.Map;

/** UI-thread profile adapter. No WebContents mutation: changes apply to future documents only. */
public final class SandiumPageText {
    public static final String PREF = "sandium.page_text.policy_v1";
    private static final int LIMIT = 262144;
    private static final Map<Profile, PageTextPolicy> POLICIES = new HashMap<>();
    private static final Map<Profile, JSONObject> SNAPSHOTS = new HashMap<>();
    private static boolean observing;
    private SandiumPageText() {}
    public static boolean usable(Profile p) {
        ThreadUtils.assertOnUiThread();
        return p != null && p.isNativeInitialized() && !p.shutdownStarted()
                && p.getOriginalProfile().isNativeInitialized()
                && !p.getOriginalProfile().shutdownStarted();
    }
    public static String origin(GURL url) {
        if (url == null || !url.isValid()
                || !("https".equals(url.getScheme()) || "http".equals(url.getScheme()))) return null;
        String value = url.getOrigin().getSpec();
        return value.endsWith("/") ? value.substring(0, value.length()-1) : value;
    }
    private static PageTextPolicy policy(Profile p) {
        if (!usable(p)) throw new IllegalStateException("Profile unavailable");
        if (!observing) {
            ProfileManager.addObserver(new ProfileManager.Observer() {
                @Override public void onProfileAdded(Profile p) {}
                @Override public void onProfileDestroyed(Profile p) {
                    PageTextPolicy value = POLICIES.remove(p);
                    if (value != null) value.close();
                    SNAPSHOTS.remove(p);
                }
            });
            observing = true;
        }
        return POLICIES.computeIfAbsent(p, key -> new PageTextPolicy(new Store(key), key.isOffTheRecord()));
    }
    public static PageTextPolicy.Settings global(Profile p) { return policy(p).global(); }
    /** Native commit transport only: final browser URL, never a page-provided origin.
     * Low byte is scale; both legacy bits8/9 are set for the single justification control.
     */
    public static int packed(WebContents contents, GURL documentUrl) {
        ThreadUtils.assertOnUiThread();
        if (contents == null || origin(documentUrl) == null) return 100;
        Profile profile = Profile.fromWebContents(contents);
        if (!usable(profile)) return 100;
        try {
            PageTextPolicy.Settings value = global(profile);
            return value.scalePercent | (value.enabled ? 256 : 0) | (value.justify ? 512 : 0);
        } catch (IllegalArgumentException | IllegalStateException invalidOrUnavailable) {
            return 100;
        }
    }
    public static void setGlobal(Profile p, PageTextPolicy.Settings value) { policy(p).setGlobal(value); }
    private static PageTextPolicy.Settings decode(JSONObject value) {
        if (value == null) return null;
        try {
            return new PageTextPolicy.Settings(value.getBoolean("enabled"),
                    value.getInt("scalePercent"), value.getBoolean("justify"));
        } catch (JSONException | IllegalArgumentException invalid) { return null; }
    }
    private static JSONObject encode(PageTextPolicy.Settings value) throws JSONException {
        return new JSONObject().put("enabled", value.enabled).put("scalePercent", value.scalePercent)
                .put("justify", value.justify);
    }
    private static final class Store implements PageTextPolicy.Store {
        private final Profile profile;
        Store(Profile p) { profile = p; }
        private JSONObject read() {
            if (!usable(profile)) throw new IllegalStateException("Profile unavailable");
            return SNAPSHOTS.computeIfAbsent(profile.getOriginalProfile(), p -> {
                String raw = UserPrefs.get(p).getString(PREF);
                try {
                    JSONObject root = raw.length() <= LIMIT ? new JSONObject(raw) : new JSONObject();
                    return root.optInt("version", 1) == 1 ? root : new JSONObject();
                } catch (JSONException invalid) { return new JSONObject(); }
            });
        }
        private void write(PageTextPolicy.Settings value) {
            if (!usable(profile) || profile.isOffTheRecord())
                throw new IllegalStateException("Private persistence denied");
            try {
                JSONObject root = new JSONObject(read().toString()).put("version", 1);
                // Retain legacy site JSON without ever reading or applying it.
                root.put("global", encode(value));
                String raw = root.toString();
                if (raw.length() > LIMIT) throw new IllegalStateException("Text settings storage limit reached");
                UserPrefs.get(profile).setString(PREF, raw);
                SNAPSHOTS.put(profile, root); // Publish only after the persistent write succeeds.
            } catch (JSONException invalid) { throw new IllegalStateException(invalid); }
        }
        @Override public PageTextPolicy.Settings readGlobal() { return decode(read().optJSONObject("global")); }
        @Override public void writeGlobal(PageTextPolicy.Settings value) { write(value); }
    }
}
