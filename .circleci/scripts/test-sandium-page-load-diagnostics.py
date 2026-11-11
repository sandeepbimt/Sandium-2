#!/usr/bin/env python3
"""Offline tests for the temporary one-navigation Sandium trace overlay."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).with_name("apply-sandium-page-load-diagnostics.py")
SPEC = importlib.util.spec_from_file_location("sandium_page_load_diagnostics", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

APPEARANCE_JAVA = '''package org.chromium.chrome.browser.settings;
import android.content.Context;
import androidx.preference.Preference;
class AppearancePreferences {
    /* package */ static final String PREF_BRAVE_CUSTOMIZE_MENU = "brave_customize_menu";
    void onCreatePreferences() {
        SettingsUtils.addPreferencesFromResource(this, R.xml.brave_appearance_preferences);
    }
    private void removePreferenceIfPresent(String key) {
    }
}
'''
XML = '''<PreferenceScreen>
    <PreferenceCategory android:key="general_section" />
</PreferenceScreen>
'''
GRD = '''<grit>
  <messages>
    <message name="IDS_EXISTING" desc="existing">
      Existing
    </message>
  </messages>
</grit>
'''
GNI = '''brave_java_sources = [
  "../../brave/android/java/org/chromium/chrome/browser/settings/AppearancePreferences.java",
]
'''
TOOLBAR = '''package org.chromium.chrome.browser.toolbar.top;
import org.chromium.chrome.browser.ntp.NtpUtil;
class BraveToolbarLayoutImpl {
    void observer() {
                    public void onPageLoadFinished(final Tab tab, GURL url) {
                        if (getToolbarDataProvider().getTab() == tab) {
                            updateBraveShieldsButtonState(tab);
                        }
    }
}
'''

def idempotent(transform, fixture, label):
    once = transform(fixture)
    twice = transform(once)
    assert once == twice, f"{label} is not idempotent"
    return once

appearance = idempotent(MODULE.transform_appearance_java, APPEARANCE_JAVA, "Appearance Java")
assert appearance.count("configureSandiumPageLoadDiagnostics();") == 1
assert "SandiumPageLoadDiagnostics.start(context)" in appearance
assert "SandiumPageLoadDiagnostics.stop()" in appearance

xml = idempotent(MODULE.transform_xml, XML, "Appearance XML")
assert xml.count(f'android:key="{MODULE.CAPTURE_KEY}"') == 1
assert xml.count(f'android:key="{MODULE.STOP_KEY}"') == 1
assert MODULE.CATEGORY_KEY in xml

grd = idempotent(MODULE.transform_grd, GRD, "GRD strings")
for name in (
    "IDS_SANDIUM_PAGE_LOAD_DIAGNOSTICS_CATEGORY",
    "IDS_SANDIUM_PAGE_LOAD_DIAGNOSTICS_CAPTURE_TITLE",
    "IDS_SANDIUM_PAGE_LOAD_DIAGNOSTICS_CAPTURE_SUMMARY",
    "IDS_SANDIUM_PAGE_LOAD_DIAGNOSTICS_STOP_TITLE",
    "IDS_SANDIUM_PAGE_LOAD_DIAGNOSTICS_STOP_SUMMARY",
):
    assert grd.count(f'name="{name}"') == 1

gni = idempotent(MODULE.transform_java_sources, GNI, "Java source registration")
assert gni.count("SandiumPageLoadDiagnostics.java") == 1

toolbar = idempotent(MODULE.transform_toolbar, TOOLBAR, "Toolbar hook")
assert toolbar.count("SandiumPageLoadDiagnostics.onPageLoadFinished();") == 1

helper = MODULE.HELPER_SOURCE
for required in (
    '"blink,cc,loading,renderer.scheduler,toplevel,v8,brave.adblock"',
    '"record-continuously"',
    "LOAD_FINISH_GRACE_MS = 3000L",
    "MAX_CAPTURE_MS = 90000L",
    "controller.stopTracing(ignored ->",
    "controller.destroy();",
    "TracingControllerAndroid.create(appContext)",
    "sStopping = true;",
    "sStopping = false;",
):
    assert required in helper, required
assert '"net"' not in helper and '"netlog"' not in helper
assert "evaluateJavaScript" not in helper
assert "Cookie" not in helper and "Authorization" not in helper

print("SANDIUM_PAGE_LOAD_DIAGNOSTICS_TESTS=PASS")
print("SANDIUM_PAGE_LOAD_DIAGNOSTICS_SCOPE=one_navigation+bounded_trace+local_download")
print("SANDIUM_PAGE_LOAD_DIAGNOSTICS_PRESERVATION=adblock+reader+transition_untouched")
