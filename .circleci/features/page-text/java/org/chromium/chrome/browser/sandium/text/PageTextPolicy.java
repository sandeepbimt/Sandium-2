// Copyright 2026 Sandium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license.
package org.chromium.chrome.browser.sandium.text;

import java.util.Objects;

/** Independent page-text model. No Android UI, page scripts, network or dark-mode dependency.
 *
 * A production adapter must atomically persist the global immutable record in a registered non-sync profile preference.
 * This class alone does not implement Chromium persistence or renderer transport.
 */
public final class PageTextPolicy {
    // Proposed UI/persistence bounds, not a claim about an unimplemented renderer.
    public static final int MIN_SCALE = 75;
    public static final int MAX_SCALE = 150;
    public static final int SCALE_STEP = 5;

    /** Settings are captured once for a document; do not mutate them during scrolling. */
    public static final class Settings {
        public final boolean enabled;
        public final int scalePercent;
        public final boolean justify;
        /** Single-control settings; legacy storage bits remain compatible. */
        public Settings(int scalePercent, boolean justify) {
            this(justify, scalePercent, justify);
        }
        /** Preserve effective behavior when decoding old two-toggle records. */
        public boolean isJustificationEnabled() { return enabled && justify; }
        public Settings(boolean enabled, int scalePercent, boolean justify) {
            if (scalePercent < MIN_SCALE || scalePercent > MAX_SCALE
                    || scalePercent % SCALE_STEP != 0)
                throw new IllegalArgumentException("Invalid page-text scale");
            this.enabled = enabled;
            this.scalePercent = scalePercent;
            this.justify = justify;
        }
    }

    // Explicit owner default: OFF, no size/family/spacing change.
    public static final Settings DEFAULT = new Settings(false, 100, false);

    /** Only global preferences are supported. No hidden site exceptions. */
    public interface Store {
        Settings readGlobal();
        void writeGlobal(Settings value);
    }
    private final Store store;
    private final boolean privateSession;
    private Settings privateGlobal;
    private boolean closed;

    public PageTextPolicy(Store store, boolean privateSession) {
        this.store = Objects.requireNonNull(store);
        this.privateSession = privateSession;
    }

    private void checkOpen() {
        if (closed) throw new IllegalStateException("Page-text profile closed");
    }

    public Settings global() {
        checkOpen();
        if (privateSession && privateGlobal != null) return privateGlobal;
        Settings value = store.readGlobal();
        return value == null ? DEFAULT : value;
    }

    public void setGlobal(Settings value) {
        checkOpen(); Objects.requireNonNull(value);
        if (privateSession) privateGlobal = value;
        else store.writeGlobal(value);
    }

    public void close() {
        privateGlobal = null; closed = true;
    }
}
