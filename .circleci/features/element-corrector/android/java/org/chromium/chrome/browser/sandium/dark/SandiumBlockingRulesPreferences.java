// Copyright 2026 Sandium Authors. BSD-style license.
package org.chromium.chrome.browser.sandium.dark;

/** Shields-only entry point; Appearance never exposes blocking rules. */
public final class SandiumBlockingRulesPreferences extends SandiumRulesPreferences {
    @Override protected boolean colorRulesOnly() { return false; }
}
