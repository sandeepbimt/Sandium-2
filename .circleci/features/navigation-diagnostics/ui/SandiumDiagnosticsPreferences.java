// Copyright 2026 Sandium Authors. BSD-style license.
package org.chromium.chrome.browser.sandium.diagnostics;

import android.app.Activity;
import android.content.ContentResolver;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.Toast;
import androidx.preference.Preference;
import androidx.preference.PreferenceScreen;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.chromium.base.supplier.MonotonicObservableSupplier;
import org.chromium.base.supplier.ObservableSuppliers;
import org.chromium.base.supplier.SettableMonotonicObservableSupplier;
import org.chromium.chrome.browser.settings.BravePreferenceFragment;
import org.chromium.chrome.browser.shields.FilterListServiceFactory;

/** Explicit local recording controls. Never exports logcat or page content. */
public class SandiumDiagnosticsPreferences extends BravePreferenceFragment {
    private static final int EXPORT = 9461;
    private final SettableMonotonicObservableSupplier<String> mTitle =
            ObservableSuppliers.createMonotonic();
    private final Handler mMain = new Handler(Looper.getMainLooper());
    private final ExecutorService mFiles = Executors.newSingleThreadExecutor();
    private Preference mStatus;
    private Preference mStart;
    private Preference mStop;
    private Preference mExport;
    private Preference mClear;
    private Preference mMark;
    private boolean mBusy;
    private boolean mDestroyed;
    // Never persisted into saved instance state or preferences.
    private String mPendingExport;
    private final Runnable mRefresh = new Runnable() {
        @Override public void run() {
            refresh();
            if (!mDestroyed && isResumed()) mMain.postDelayed(this, 1000);
        }
    };

    @Override public MonotonicObservableSupplier<String> getPageTitle() { return mTitle; }

    @Override public void onCreatePreferences(Bundle state, String key) {
        super.onCreatePreferences(state, key);
        SandiumDiagnosticsCapture.install();
        mTitle.set("Navigation diagnostics");
        PreferenceScreen screen = getPreferenceManager().createPreferenceScreen(requireContext());
        setPreferenceScreen(screen);
        row(screen, "Local, opt-in recording",
                "Records supported navigation and ad-blocking events, not websites, URLs, page text, "
                + "screenshots or network bodies. Private-tab events are excluded. "
                + "Recording ends after 2 minutes or 5,000 events; closing this screen does not stop it. Interrupted sessions do not resume automatically after reopening.",
                null);
        row(screen, "What this can show",
                "Event timing can help investigate unexpected redirects and blocking. "
                + "It does not detect every unwanted ad or warning, or identify its page content.",
                null);
        row(screen, "Saved on this device",
                "Session data stays in app-private storage until cleared or replaced. "
                + "Completed writes can be recovered after reopening; an interrupted session may have an unflushed tail. "
                + "Disk writes run in the background. Export includes the captured events still in memory without waiting for disk writes. "
                + "Check Recording status after reopening.", null);
        mStatus = row(screen, "Recording status", null, null);
        mStart = row(screen, "Start recording", "Replaces the previous app-private saved session",
                () -> {
                    SandiumDiagnosticsCapture.install();
                    if (!SandiumNavigationDiagnostics.start(
                            FilterListServiceFactory::setSandiumAdDiagnosticsRecording)) {
                        message("Recording is unavailable. Check Recording status.");
                    } else if (!FilterListServiceFactory.captureSandiumDiagnosticLoadSnapshot(
                            getProfile(), SandiumNavigationDiagnostics.sessionEpoch())) {
                        message("Recording started; the ad-engine load baseline is unavailable.");
                    }
                });
        mStop = row(screen, "Stop recording", "Keep captured events for export",
                SandiumNavigationDiagnostics::stop);
        mMark = row(screen, "Mark unwanted ad or warning",
                "Add a user-reported marker now; this is not automatic detection",
                SandiumNavigationDiagnostics::markAdWarning);
        mExport = row(screen, "Export recording",
                "Stop and save a JSON file using Android’s document chooser. "
                + "Nothing is sent automatically; choose a location you trust.",
                this::chooseExport);
        mClear = row(screen, "Clear recording", "Stop and erase the app-private saved recording; check status until cleared",
                SandiumNavigationDiagnostics::clear);
        refresh();
    }

    private Preference row(PreferenceScreen screen, String title, String summary, Runnable action) {
        Preference preference = new Preference(requireContext());
        preference.setTitle(title);
        preference.setSummary(summary);
        preference.setSelectable(action != null);
        if (action != null) preference.setOnPreferenceClickListener(clicked -> {
            if (usable() && !mBusy) { action.run(); refresh(); }
            return true;
        });
        screen.addPreference(preference);
        return preference;
    }

    private boolean usable() {
        return !mDestroyed && getActivity() != null && getProfile() != null
                && getProfile().isNativeInitialized() && !getProfile().shutdownStarted()
                && !getProfile().isOffTheRecord();
    }

    private void refresh() {
        if (mStatus == null || mDestroyed) return;
        boolean usable = usable();
        boolean recording = usable && SandiumNavigationDiagnostics.isRecording();
        mStatus.setSummary(usable ? SandiumNavigationDiagnostics.snapshotSummary()
                : "Unavailable in private browsing or while the profile is not ready");
        mStart.setEnabled(usable && !mBusy && !recording);
        mStop.setEnabled(usable && !mBusy && recording);
        mMark.setEnabled(usable && !mBusy && recording);
        mExport.setEnabled(usable && !mBusy);
        mClear.setEnabled(usable && !mBusy);
    }

    private void chooseExport() {
        // Freeze the bounded, sanitized snapshot before handing off to another activity.
        SandiumNavigationDiagnostics.stop();
        mPendingExport = SandiumNavigationDiagnostics.snapshotJson();
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE).setType("application/json")
                .putExtra(Intent.EXTRA_TITLE, "Sandium-diagnostics.json");
        try {
            mBusy = true;
            startActivityForResult(intent, EXPORT);
        } catch (android.content.ActivityNotFoundException unavailable) {
            mBusy = false;
            mPendingExport = null;
            message("No document chooser is available. The recording remains available unless a storage error is shown.");
        }
    }

    @Override public void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != EXPORT) return;
        String snapshot = mPendingExport;
        mPendingExport = null;
        mBusy = false;
        if (result != Activity.RESULT_OK) { refresh(); return; }
        if (!usable() || snapshot == null) {
            message("Export was interrupted. Choose Export recording again.");
            refresh();
            return;
        }
        Uri uri = data == null ? null : data.getData();
        if (uri == null || !"content".equals(uri.getScheme())) {
            message("Choose a file through the Android document chooser.");
            refresh();
            return;
        }
        final byte[] bytes = snapshot.getBytes(StandardCharsets.UTF_8);
        final ContentResolver resolver = requireContext().getContentResolver();
        mBusy = true;
        refresh();
        mFiles.execute(() -> {
            boolean success = false;
            try (OutputStream stream = resolver.openOutputStream(uri, "wt")) {
                if (stream == null) throw new java.io.IOException("No stream");
                stream.write(bytes);
                stream.flush();
                success = true;
            } catch (Exception failure) {
                // Never include provider exceptions, file names, or URIs in diagnostics.
            }
            final boolean saved = success;
            mMain.post(() -> {
                if (mDestroyed) return;
                mBusy = false;
                message(saved ? "Recording saved." : "Could not save the recording. "
                        + "A partial file may remain; the recording remains available unless a storage error is shown.");
                refresh();
            });
        });
    }

    private void message(String text) {
        if (!mDestroyed && getActivity() != null)
            Toast.makeText(requireContext(), text, Toast.LENGTH_LONG).show();
    }

    @Override public void onResume() {
        super.onResume();
        mMain.removeCallbacks(mRefresh);
        mRefresh.run();
    }

    @Override public void onPause() {
        mMain.removeCallbacks(mRefresh);
        super.onPause();
    }

    @Override public void onDestroy() {
        mDestroyed = true;
        mPendingExport = null;
        mMain.removeCallbacks(mRefresh);
        mFiles.shutdown();
        super.onDestroy();
    }
}
