#!/usr/bin/env python3
"""Install Sandium's temporary, one-navigation page-load trace controls."""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

BRAVE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"
APPEARANCE_JAVA = Path("android/java/org/chromium/chrome/browser/settings/AppearancePreferences.java")
APPEARANCE_XML = Path("android/java/brave-res/xml/brave_appearance_preferences.xml")
STRINGS_GRD = Path("browser/ui/android/strings/android_brave_strings.grd")
JAVA_SOURCES = Path("android/brave_java_sources.gni")
TOOLBAR_JAVA = Path("android/java/org/chromium/chrome/browser/toolbar/top/BraveToolbarLayoutImpl.java")
HELPER_JAVA = Path("android/java/org/chromium/chrome/browser/settings/SandiumPageLoadDiagnostics.java")
CAPTURE_KEY = "sandium_page_load_diagnostics_capture"
STOP_KEY = "sandium_page_load_diagnostics_stop"
CATEGORY_KEY = "sandium_page_load_diagnostics_section"

HELPER_SOURCE = r'''/* Copyright (c) 2026 The Sandium Authors. All rights reserved.
 * Temporary diagnostic; remove with apply-sandium-page-load-diagnostics.py.
 */
package org.chromium.chrome.browser.settings;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.widget.Toast;
import org.chromium.content_public.browser.TracingControllerAndroid;
import java.io.File;

/** Captures one explicitly requested page-load trace and stops automatically. */
public final class SandiumPageLoadDiagnostics {
    private static final String TRACE_CATEGORIES =
            "blink,cc,loading,renderer.scheduler,toplevel,v8,brave.adblock";
    private static final String TRACE_OPTIONS = "record-continuously";
    private static final long LOAD_FINISH_GRACE_MS = 3000L;
    private static final long MAX_CAPTURE_MS = 90000L;
    private static final Handler UI_HANDLER = new Handler(Looper.getMainLooper());
    private static TracingControllerAndroid sController;
    private static Context sApplicationContext;
    private static Runnable sStopAfterLoad;
    private static Runnable sMaximumDurationStop;
    private static boolean sStopping;

    private SandiumPageLoadDiagnostics() {}

    public static void start(Context context) {
        if (Looper.myLooper() != Looper.getMainLooper()) {
            UI_HANDLER.post(() -> start(context));
            return;
        }
        if (sStopping) {
            showToast(context, "The previous page-load trace is still being saved.");
            return;
        }
        if (sController != null && sController.isTracing()) {
            showToast(context, "A page-load capture is already active.");
            return;
        }
        Context appContext = context.getApplicationContext();
        TracingControllerAndroid controller = TracingControllerAndroid.create(appContext);
        boolean started = controller.startTracing(
                null, false, TRACE_CATEGORIES, TRACE_OPTIONS, true, false);
        if (!started) {
            controller.destroy();
            showToast(appContext, "Unable to start page-load capture.");
            return;
        }
        sController = controller;
        sApplicationContext = appContext;
        sMaximumDurationStop = SandiumPageLoadDiagnostics::stopInternal;
        UI_HANDLER.postDelayed(sMaximumDurationStop, MAX_CAPTURE_MS);
        showToast(appContext, "Capture armed. Open one webpage now.");
    }

    /** Called only after the selected foreground tab finishes its next navigation. */
    public static void onPageLoadFinished() {
        if (Looper.myLooper() != Looper.getMainLooper()) {
            UI_HANDLER.post(SandiumPageLoadDiagnostics::onPageLoadFinished);
            return;
        }
        if (sController == null || !sController.isTracing()) return;
        if (sMaximumDurationStop != null) {
            UI_HANDLER.removeCallbacks(sMaximumDurationStop);
            sMaximumDurationStop = null;
        }
        if (sStopAfterLoad != null) UI_HANDLER.removeCallbacks(sStopAfterLoad);
        sStopAfterLoad = SandiumPageLoadDiagnostics::stopInternal;
        UI_HANDLER.postDelayed(sStopAfterLoad, LOAD_FINISH_GRACE_MS);
    }

    public static void stop() {
        if (Looper.myLooper() != Looper.getMainLooper()) {
            UI_HANDLER.post(SandiumPageLoadDiagnostics::stop);
            return;
        }
        if (sController == null || !sController.isTracing()) {
            Context context = sApplicationContext;
            if (context != null) showToast(context, "No page-load capture is active.");
            return;
        }
        stopInternal();
    }

    private static void stopInternal() {
        TracingControllerAndroid controller = sController;
        if (controller == null || sStopping) return;
        if (!controller.isTracing()) {
            controller.destroy();
            sController = null;
            sApplicationContext = null;
            return;
        }
        sStopping = true;
        if (sStopAfterLoad != null) {
            UI_HANDLER.removeCallbacks(sStopAfterLoad);
            sStopAfterLoad = null;
        }
        if (sMaximumDurationStop != null) {
            UI_HANDLER.removeCallbacks(sMaximumDurationStop);
            sMaximumDurationStop = null;
        }
        String outputPath = controller.getOutputPath();
        Context context = sApplicationContext;
        sController = null;
        sApplicationContext = null;
        controller.stopTracing(ignored -> {
            controller.destroy();
            sStopping = false;
            if (context != null) {
                String filename = outputPath == null ? "Downloads" : new File(outputPath).getName();
                showToast(context, "Page-load trace saved: " + filename);
            }
        });
    }

    private static void showToast(Context context, String message) {
        Toast.makeText(context, message, Toast.LENGTH_LONG).show();
    }
}
'''

GRD_BLOCK = '''    <message name="IDS_SANDIUM_PAGE_LOAD_DIAGNOSTICS_CATEGORY" desc="Temporary Sandium page-load diagnostic category.">
      Temporary page-load diagnostics
    </message>
    <message name="IDS_SANDIUM_PAGE_LOAD_DIAGNOSTICS_CAPTURE_TITLE" desc="Start a one-navigation Sandium performance trace.">
      Capture next page load
    </message>
    <message name="IDS_SANDIUM_PAGE_LOAD_DIAGNOSTICS_CAPTURE_SUMMARY" desc="Explains local trace capture and its privacy implications.">
      Capture one page load and save the trace in Downloads. The trace may contain page URLs; review it before sharing.
    </message>
    <message name="IDS_SANDIUM_PAGE_LOAD_DIAGNOSTICS_STOP_TITLE" desc="Stop an active Sandium page-load trace.">
      Stop capture now
    </message>
    <message name="IDS_SANDIUM_PAGE_LOAD_DIAGNOSTICS_STOP_SUMMARY" desc="Manually stop the current Sandium page-load trace.">
      Stop the active trace and save it in Downloads.
    </message>
'''

XML_BLOCK = '''
    <PreferenceCategory
        android:key="sandium_page_load_diagnostics_section"
        android:title="@string/sandium_page_load_diagnostics_category">
        <Preference
            android:key="sandium_page_load_diagnostics_capture"
            android:title="@string/sandium_page_load_diagnostics_capture_title"
            android:summary="@string/sandium_page_load_diagnostics_capture_summary" />
        <Preference
            android:key="sandium_page_load_diagnostics_stop"
            android:title="@string/sandium_page_load_diagnostics_stop_title"
            android:summary="@string/sandium_page_load_diagnostics_stop_summary" />
    </PreferenceCategory>
'''

def replace_once(source: str, old: str, new: str, label: str) -> str:
    if new in source:
        return source
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one exact anchor, found {count}")
    return source.replace(old, new, 1)

def transform_appearance_java(source: str) -> str:
    source = replace_once(
        source,
        '    /* package */ static final String PREF_BRAVE_CUSTOMIZE_MENU = "brave_customize_menu";\n',
        '    /* package */ static final String PREF_BRAVE_CUSTOMIZE_MENU = "brave_customize_menu";\n'
        '    private static final String PREF_SANDIUM_PAGE_LOAD_CAPTURE = "sandium_page_load_diagnostics_capture";\n'
        '    private static final String PREF_SANDIUM_PAGE_LOAD_STOP = "sandium_page_load_diagnostics_stop";\n',
        "SANDIUM_DIAGNOSTICS_PREFERENCE_KEYS",
    )
    source = replace_once(
        source,
        '        SettingsUtils.addPreferencesFromResource(this, R.xml.brave_appearance_preferences);\n',
        '        SettingsUtils.addPreferencesFromResource(this, R.xml.brave_appearance_preferences);\n'
        '        configureSandiumPageLoadDiagnostics();\n',
        "SANDIUM_DIAGNOSTICS_PREFERENCE_BINDING",
    )
    anchor = '    private void removePreferenceIfPresent(String key) {\n'
    method = '''    private void configureSandiumPageLoadDiagnostics() {
        Preference capture = findPreference(PREF_SANDIUM_PAGE_LOAD_CAPTURE);
        if (capture != null) {
            capture.setOnPreferenceClickListener(preference -> {
                Context context = getContext();
                if (context != null) SandiumPageLoadDiagnostics.start(context);
                return true;
            });
        }
        Preference stop = findPreference(PREF_SANDIUM_PAGE_LOAD_STOP);
        if (stop != null) {
            stop.setOnPreferenceClickListener(preference -> {
                SandiumPageLoadDiagnostics.stop();
                return true;
            });
        }
    }

'''
    return replace_once(source, anchor, method + anchor, "SANDIUM_DIAGNOSTICS_CLICK_HANDLERS")

def transform_xml(source: str) -> str:
    return replace_once(source, "</PreferenceScreen>", XML_BLOCK + "</PreferenceScreen>", "SANDIUM_DIAGNOSTICS_SETTINGS_XML")

def transform_grd(source: str) -> str:
    return replace_once(source, "  </messages>\n", GRD_BLOCK + "  </messages>\n", "SANDIUM_DIAGNOSTICS_STRINGS")

def transform_java_sources(source: str) -> str:
    anchor = '  "../../brave/android/java/org/chromium/chrome/browser/settings/AppearancePreferences.java",\n'
    entry = '  "../../brave/android/java/org/chromium/chrome/browser/settings/SandiumPageLoadDiagnostics.java",\n'
    return replace_once(source, anchor, anchor + entry, "SANDIUM_DIAGNOSTICS_JAVA_SOURCE_REGISTRATION")

def transform_toolbar(source: str) -> str:
    source = replace_once(
        source,
        "import org.chromium.chrome.browser.ntp.NtpUtil;\n",
        "import org.chromium.chrome.browser.ntp.NtpUtil;\n"
        "import org.chromium.chrome.browser.settings.SandiumPageLoadDiagnostics;\n",
        "SANDIUM_DIAGNOSTICS_TOOLBAR_IMPORT",
    )
    anchor = (
        "                    public void onPageLoadFinished(final Tab tab, GURL url) {\n"
        "                        if (getToolbarDataProvider().getTab() == tab) {\n"
    )
    return replace_once(
        source,
        anchor,
        anchor + "                            SandiumPageLoadDiagnostics.onPageLoadFinished();\n",
        "SANDIUM_DIAGNOSTICS_PAGE_LOAD_FINISHED_HOOK",
    )

def write_file(path: Path, content: str, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise RuntimeError(f"{label}: existing file differs; refusing to overwrite")
        print(f"{label}=ALREADY_CURRENT")
        return
    path.write_text(content, encoding="utf-8")
    if path.read_text(encoding="utf-8") != content:
        raise RuntimeError(f"{label}: post-write verification failed")
    print(f"{label}=CREATED")

def git_sha(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()

def write_transform(path: Path, transform, label: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"{label}: missing pinned source file {path}")
    original = path.read_text(encoding="utf-8")
    updated = transform(original)
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        if path.read_text(encoding="utf-8") != updated:
            raise RuntimeError(f"{label}: post-write verification failed")
        print(f"{label}=APPLIED")
    else:
        print(f"{label}=ALREADY_APPLIED")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--src", required=True, type=Path)
    args = parser.parse_args()
    core, src = args.core.resolve(), args.src.resolve()
    actual_brave, actual_chromium = git_sha(core), git_sha(src)
    if actual_brave != BRAVE_SHA or actual_chromium != CHROMIUM_SHA:
        raise RuntimeError(
            "pinned source mismatch; refusing temporary diagnostics overlay: "
            f"brave={actual_brave} expected={BRAVE_SHA}; "
            f"chromium={actual_chromium} expected={CHROMIUM_SHA}"
        )
    write_transform(core / APPEARANCE_JAVA, transform_appearance_java, "SANDIUM_DIAGNOSTICS_APPEARANCE_JAVA")
    write_transform(core / APPEARANCE_XML, transform_xml, "SANDIUM_DIAGNOSTICS_APPEARANCE_XML")
    write_transform(core / STRINGS_GRD, transform_grd, "SANDIUM_DIAGNOSTICS_STRINGS")
    write_transform(core / JAVA_SOURCES, transform_java_sources, "SANDIUM_DIAGNOSTICS_JAVA_SOURCES")
    write_transform(core / TOOLBAR_JAVA, transform_toolbar, "SANDIUM_DIAGNOSTICS_TOOLBAR_HOOK")
    write_file(core / HELPER_JAVA, HELPER_SOURCE, "SANDIUM_DIAGNOSTICS_HELPER")
    print("SANDIUM_PAGE_LOAD_DIAGNOSTICS=PASS mode=one-navigation max_seconds=90 auto_stop_grace_ms=3000")
    print("SANDIUM_PAGE_LOAD_DIAGNOSTICS_PRIVACY=LOCAL_TRACE_URLS_MAY_BE_PRESENT_NETLOG_EXCLUDED")
    print("SANDIUM_PAGE_LOAD_DIAGNOSTICS_ADBLOCK=brave.adblock_category_included_existing_filter_behavior_untouched")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SANDIUM_PAGE_LOAD_DIAGNOSTICS=FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
