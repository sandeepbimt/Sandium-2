// Copyright 2026 Sandium Authors. BSD-style license.
package org.chromium.chrome.browser.sandium.diagnostics;

import java.io.File;
import org.chromium.base.ContextUtils;
import org.chromium.chrome.browser.gesturenav.NativePageBitmapCapturer;
import org.chromium.chrome.browser.tab.Tab;

/** Optional capture sink; owns no Activity, view, tab or browsing-content reference. */
public final class SandiumDiagnosticsCapture {
    private static final NativePageBitmapCapturer.SandiumOriginObserver OBSERVER =
            new NativePageBitmapCapturer.SandiumOriginObserver() {
                @Override public boolean isEnabled(Tab tab) {
                    return eligible(tab);
                }
                @Override public void record(Tab tab, double[] values) {
                    if (!eligible(tab)) return;
                    SandiumNavigationDiagnostics.record(
                            SandiumNavigationDiagnostics.Event.CAPTURE, 0,
                            tab.getProfile().isOffTheRecord(), values);
                }
                @Override public void matrix(Tab tab, double[] values) {
                    if (!eligible(tab)) return;
                    SandiumNavigationDiagnostics.record(
                            SandiumNavigationDiagnostics.Event.CAPTURE_LAYER, 0,
                            tab.getProfile().isOffTheRecord(), values);
                }
            };

    private static final org.chromium.chrome.browser.ntp.NewTabPage.SandiumRevealObserver REVEAL_OBSERVER =
            new org.chromium.chrome.browser.ntp.NewTabPage.SandiumRevealObserver() {
                @Override public long epoch(Tab tab) {
                    return eligible(tab) ? SandiumNavigationDiagnostics.sessionEpoch() : 0;
                }
                @Override public void record(Tab tab, long epoch, boolean controls, double[] values) {
                    if (!eligible(tab)) return;
                    SandiumNavigationDiagnostics.recordForEpoch(epoch, controls
                            ? SandiumNavigationDiagnostics.Event.NATIVE_REVEAL_CONTROLS
                            : SandiumNavigationDiagnostics.Event.NATIVE_REVEAL_VIEW,
                            tab.getProfile().isOffTheRecord(), values);
                }
            };

    private SandiumDiagnosticsCapture() {}

    private static boolean eligible(Tab tab) {
        return SandiumNavigationDiagnostics.isRecording() && tab != null
                && !tab.isDestroyed() && tab.getProfile() != null
                && tab.getProfile().isNativeInitialized()
                && !tab.getProfile().shutdownStarted()
                && !tab.isIncognito() && !tab.getProfile().isOffTheRecord();
    }

    /** Call on the UI thread at Start and during opted-in app-start restoration. */
    public static void install() {
        SandiumNavigationDiagnostics.initialize(new File(
                ContextUtils.getApplicationContext().getNoBackupFilesDir(), "sandium-diagnostics"));
        NativePageBitmapCapturer.setSandiumOriginObserver(OBSERVER);
        org.chromium.chrome.browser.ntp.NewTabPage.setSandiumRevealObserver(REVEAL_OBSERVER);
    }
}
