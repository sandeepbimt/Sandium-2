// Copyright 2026 Sandium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license.
package org.chromium.chrome.browser.sandium.dark;

import java.util.EnumMap;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;

/** Browser-owned policy model. Does not execute page scripts or solve challenges. */
public final class DarkPagePolicy {
    public static final int BACKGROUND = 0xff000000;
    public static final int SURFACE = 0xff1a1a1a;
    public static final int TEXT = 0xffeeeeee;
    public enum Control { DARK_PAGE }
    public enum Choice { FOLLOW_GLOBAL, ON, OFF }
    /** Adapter must be scoped to one regular Chromium profile and use canonical GURL origins. */
    public interface Store {
        Choice read(String origin, Control control);
        void write(String origin, Control control, Choice choice);
        boolean global(Control control);
        void setGlobal(Control control, boolean value);
    }
    private final Store regular;
    private final Map<String, EnumMap<Control, Choice>> privateOverrides = new HashMap<>();
    private boolean closed;
    public DarkPagePolicy(Store regular) { this.regular = Objects.requireNonNull(regular); }
    // Reject non-web keys defensively. Production must derive origin with GURL, never page JS.
    private static void checkOrigin(String origin) {
        if (origin == null || !(origin.startsWith("https://") || origin.startsWith("http://"))
                || origin.indexOf('/', origin.indexOf("://") + 3) >= 0
                || origin.indexOf('@') >= 0 || origin.indexOf('?') >= 0 || origin.indexOf('#') >= 0
                || origin.substring(origin.indexOf("://") + 3).isEmpty()
                || origin.chars().anyMatch(c -> Character.isWhitespace(c) || c < 32)) {
            throw new IllegalArgumentException("Expected canonical HTTP(S) origin without path");
        }
    }
    private void checkOpen() { if (closed) throw new IllegalStateException("Session closed"); }
    public Choice choice(String origin, Control control, boolean privateSession) {
        checkOpen(); checkOrigin(origin); Objects.requireNonNull(control);
        if (privateSession) {
            Map<Control, Choice> values = privateOverrides.get(origin);
            return values == null ? Choice.FOLLOW_GLOBAL : values.getOrDefault(control, Choice.FOLLOW_GLOBAL);
        }
        Choice choice = regular.read(origin, control);
        return choice == null ? Choice.FOLLOW_GLOBAL : choice;
    }
    public boolean effective(String origin, Control control, boolean privateSession) {
        Choice choice = choice(origin, control, privateSession);
        return choice == Choice.FOLLOW_GLOBAL ? regular.global(control) : choice == Choice.ON;
    }
    public void set(String origin, Control control, Choice choice, boolean privateSession) {
        checkOpen(); checkOrigin(origin); Objects.requireNonNull(control); Objects.requireNonNull(choice);
        if (!privateSession) { regular.write(origin, control, choice); return; }
        if (choice == Choice.FOLLOW_GLOBAL) {
            Map<Control, Choice> values = privateOverrides.get(origin);
            if (values != null) { values.remove(control); if (values.isEmpty()) privateOverrides.remove(origin); }
        } else privateOverrides.computeIfAbsent(origin, key -> new EnumMap<>(Control.class)).put(control, choice);
    }
    public void reset(String origin, boolean privateSession) {
        for (Control control : Control.values()) set(origin, control, Choice.FOLLOW_GLOBAL, privateSession);
    }
    public void setGlobal(Control control, boolean value) {
        checkOpen(); regular.setGlobal(Objects.requireNonNull(control), value);
    }
    public void closePrivateSession() { privateOverrides.clear(); }
    public void close() { closePrivateSession(); closed = true; }
}
