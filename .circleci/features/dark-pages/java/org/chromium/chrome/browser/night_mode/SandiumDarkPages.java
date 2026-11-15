// Copyright 2026 Sandium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license.
package org.chromium.chrome.browser.night_mode;

import org.json.JSONException;
import org.json.JSONObject;
import org.chromium.base.ThreadUtils;
import org.chromium.chrome.browser.profiles.Profile;
import org.chromium.chrome.browser.profiles.ProfileManager;
import org.chromium.chrome.browser.sandium.dark.DarkPagePolicy;
import org.chromium.chrome.browser.sandium.dark.DarkPagePolicy.Choice;
import org.chromium.chrome.browser.sandium.dark.DarkPagePolicy.Control;
import org.chromium.components.user_prefs.UserPrefs;
import org.chromium.content_public.browser.WebContents;
import org.chromium.url.GURL;
import java.util.HashMap;
import java.util.Map;

/** Profile-owned preferences and native ThemeClient bridge. No page-script execution. */
public final class SandiumDarkPages {
    private static final String PREF = "sandium.dark_pages.policy_v1";
    private static final int MAX_SAVED_BYTES = 262144;
    private static final Map<Profile, DarkPagePolicy> POLICIES = new HashMap<>();
    private static final Map<Profile, SavedPolicy> SNAPSHOTS = new HashMap<>();
    private static boolean observing;
    private SandiumDarkPages() {}

    public static boolean available(Profile profile) {
        ThreadUtils.assertOnUiThread();
        return profile != null && profile.isNativeInitialized() && !profile.shutdownStarted();
    }
    private static void ensureObserving() {
        ThreadUtils.assertOnUiThread();
        if (observing) return;
        ProfileManager.addObserver(new ProfileManager.Observer() {
            @Override public void onProfileAdded(Profile profile) {}
            @Override public void onProfileDestroyed(Profile profile) {
                DarkPagePolicy value = POLICIES.remove(profile);
                if (value != null) value.close();
                SNAPSHOTS.remove(profile);
            }
        });
        observing = true;
    }
    public static boolean usable(Profile profile) {
        return available(profile) && available(profile.getOriginalProfile());
    }
    private static DarkPagePolicy policy(Profile profile) {
        ThreadUtils.assertOnUiThread();
        if (!usable(profile)) throw new IllegalStateException("Profile unavailable");
        ensureObserving();
        return POLICIES.computeIfAbsent(profile, key -> new DarkPagePolicy(new ProfileStore(key)));
    }
    /** Loaded once per profile; only this class writes this non-syncable preference. */
    private static final class SavedPolicy {
        JSONObject value;
        SavedPolicy(Profile profile) {
            String serialized = UserPrefs.get(profile).getString(PREF);
            try { value = serialized.length() > MAX_SAVED_BYTES ? new JSONObject() : new JSONObject(serialized); }
            catch (JSONException invalid) { value = new JSONObject(); }
        }
    }
    private static final class ProfileStore implements DarkPagePolicy.Store {
        private final Profile profile;
        ProfileStore(Profile profile) { this.profile = profile; }
        private SavedPolicy snapshot() {
            ensureObserving();
            Profile original = profile.getOriginalProfile();
            if (!available(original)) throw new IllegalStateException("Original profile unavailable");
            return SNAPSHOTS.computeIfAbsent(original, SavedPolicy::new);
        }
        private JSONObject read() { return snapshot().value; }
        private JSONObject copy() {
            try { return new JSONObject(read().toString()); }
            catch (JSONException impossible) { throw new IllegalStateException(impossible); }
        }
        private void save(JSONObject value) {
            if (profile.isOffTheRecord()) throw new IllegalStateException("Private persistence denied");
            String serialized = value.toString();
            if (serialized.length() > MAX_SAVED_BYTES) throw new IllegalStateException("Site limit reached");
            UserPrefs.get(profile).setString(PREF, serialized);
            snapshot().value = value; // Publish only after persistent write succeeds.
        }
        @Override public Choice read(String origin, Control control) {
            if (profile.isOffTheRecord()) return Choice.FOLLOW_GLOBAL;
            JSONObject sites = read().optJSONObject("sites");
            JSONObject site = sites == null ? null : sites.optJSONObject(origin);
            if (site == null) return Choice.FOLLOW_GLOBAL;
            String value = site.optString(control.name(), "FOLLOW_GLOBAL");
            try { return Choice.valueOf(value); }
            catch (IllegalArgumentException invalid) { return Choice.FOLLOW_GLOBAL; }
        }
        @Override public void write(String origin, Control control, Choice choice) {
            JSONObject root = copy();
            JSONObject sites = root.optJSONObject("sites");
            if (sites == null) sites = new JSONObject();
            JSONObject site = sites.optJSONObject(origin);
            if (site == null) site = new JSONObject();
            try {
                if (choice == Choice.FOLLOW_GLOBAL) site.remove(control.name());
                else site.put(control.name(), choice.name());
                if (site.length() == 0) sites.remove(origin); else sites.put(origin, site);
                root.put("sites", sites); save(root);
            } catch (JSONException impossible) { throw new IllegalStateException(impossible); }
        }
        @Override public boolean global(Control control) {
            JSONObject globals = read().optJSONObject("global");
            return globals == null || globals.optBoolean(control.name(), true);
        }
        @Override public void setGlobal(Control control, boolean value) {
            JSONObject root = copy(); JSONObject globals = root.optJSONObject("global");
            if (globals == null) globals = new JSONObject();
            try { globals.put(control.name(), value); root.put("global", globals); save(root); }
            catch (JSONException impossible) { throw new IllegalStateException(impossible); }
        }
    }
    /** Returns null for internal, opaque and non-web URLs. Keys never retain paths or credentials. */
    public static String origin(GURL url) {
        if (url == null || !url.isValid()) return null;
        if (!"https".equals(url.getScheme()) && !"http".equals(url.getScheme())) return null;
        String origin = url.getOrigin().getSpec();
        return origin.endsWith("/") ? origin.substring(0, origin.length() - 1) : origin;
    }
    public static Boolean enabled(WebContents contents, GURL documentUrl) {
        ThreadUtils.assertOnUiThread();
        if (contents == null) return null;
        Profile profile = Profile.fromWebContents(contents);
        String origin = origin(documentUrl);
        if (!usable(profile) || origin == null) return null;
        return policy(profile).effective(origin, Control.DARK_PAGE, profile.isOffTheRecord());
    }
    /** Native transport contract: bit zero enables dark pages; other bits are reserved. */
    public static int flags(WebContents contents, GURL documentUrl) {
        return Boolean.TRUE.equals(enabled(contents, documentUrl)) ? 1 : 0;
    }
    public static Choice choice(Profile profile, GURL url, Control control) {
        String origin = origin(url);
        if (origin == null) return Choice.FOLLOW_GLOBAL;
        return policy(profile).choice(origin, control, profile.isOffTheRecord());
    }
    public static void set(Profile profile, GURL url, Control control, Choice choice) {
        String origin = origin(url);
        if (origin == null) throw new IllegalArgumentException("Not a web origin");
        policy(profile).set(origin, control, choice, profile.isOffTheRecord());
    }
    public static boolean global(Profile profile, Control control) {
        ThreadUtils.assertOnUiThread();
        if (!usable(profile)) throw new IllegalStateException("Profile unavailable");
        return new ProfileStore(profile).global(control);
    }
    public static boolean trySetGlobal(Profile profile, Control control, boolean value) {
        try { setGlobal(profile, control, value); return true; }
        catch (IllegalStateException unavailableOrSaveFailed) { return false; }
    }
    public static void setGlobal(Profile profile, Control control, boolean value) {
        policy(profile).setGlobal(control, value);
    }
}
