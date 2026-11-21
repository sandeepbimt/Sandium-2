#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Emit reviewed #1471 -> real ad-control UI Chromium files; no recipe/CI writes."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

BASE = "73e89fb8e5b4d93ff01264ef0cf3bbab72d00906"
MANIFEST_SHA = "27d796a78aa8e53cafb4aed62edd88c73350916ae587b6af39c14909c72fce97"
UPSTREAM_BUILD_SHA = "f2721b2322b00da091676a5f08e9a0536a123bc7c80023f2b895a9d48478d578"
ROOT = Path(__file__).resolve().parent
ANDROID = "chrome/android/"
RES = ANDROID + "java/res/"
JAVA = ANDROID + "java/src/org/chromium/chrome/browser/settings/"
FACTORY = "components/sandium_adblock/document_subresource_factory"
MAIN = "chrome/browser/chrome_browser_main_android.cc"
SERVICE = "chrome/browser/raws/subscription_service.h"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def once(text, anchor, replacement):
    if text.count(anchor) != 1:
        raise ValueError("Expected exactly one source anchor: " + anchor)
    return text.replace(anchor, replacement, 1)


def compose(repo, upstream_build, output):
    if output.exists() or output.is_relative_to(repo):
        raise ValueError("Output must be new and outside the input repository")
    if subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip() != BASE:
        raise ValueError("Wrong RawS base")
    blobs = repo / "raws-adblock/production-postimages"
    raw = (repo / "raws-adblock/production-restore-recipe.json").read_bytes()
    if sha(raw) != MANIFEST_SHA:
        raise ValueError("Wrong RawS manifest")
    manifest = json.loads(raw)["files"]
    transformed = {}

    def edit(relative_path, pairs):
        if relative_path == ANDROID + "BUILD.gn":
            if relative_path in manifest:
                raise ValueError("Unexpected existing Android BUILD overlay")
            data = upstream_build.read_bytes()
            expected = UPSTREAM_BUILD_SHA
        else:
            expected = manifest[relative_path]["after_sha256"]
            data = (blobs / expected).read_bytes()
        if sha(data) != expected:
            raise ValueError("Wrong reviewed preimage: " + relative_path)
        body = data.decode()
        for anchor, replacement in pairs:
            body = once(body, anchor, replacement)
        transformed[relative_path] = (expected, body.encode())

    anchor = '      "java/src/org/chromium/chrome/browser/privacy/settings/PrivacyPreferencesManagerImpl.java",'
    entry = '      "java/src/org/chromium/chrome/browser/settings/RawsProtectionCopy.java",'
    edit(ANDROID + "BUILD.gn", [(anchor, anchor + "\n" + entry)])

    edit(FACTORY + ".h", [("bool OfflineRulesReady();", """bool OfflineRulesReady();
// Values are consumed by RawS protection Java via JNI.
enum class OfflineRulesPhase : int {
  kUnknown = 0, kFailed = 1, kLoading = 2, kReady = 3,
};
OfflineRulesPhase GetOfflineRulesPhase();""")])
    anchor = "bool OfflineRulesReady() { return GetState().ready; }"
    edit(FACTORY + ".cc", [(anchor, anchor + """
OfflineRulesPhase GetOfflineRulesPhase() {
  const auto& state = GetState();
  if (state.failed)
    return OfflineRulesPhase::kFailed;
  if (state.ready)
    return OfflineRulesPhase::kReady;
  return state.attempted ? OfflineRulesPhase::kLoading
                         : OfflineRulesPhase::kUnknown;
}""")])

    anchor = '  void Refresh(bool manual) {'
    edit(SERVICE, [('#include "base/timer/timer.h"', '#include "base/time/time.h"\n#include "base/timer/timer.h"'), (anchor, """  // Accept at most one manual batch per minute, and don't overlap an existing
  // batch. Acceptance acknowledges scheduling, not download or activation.
  bool RequestManualRefresh() {
    const auto now = base::TimeTicks::Now();
    if (!started_ || !queue_.empty() || !busy_.empty() ||
        (!last_manual_refresh_.is_null() &&
         now - last_manual_refresh_ < base::Minutes(1)) ||
        std::none_of(flags_.begin(), flags_.end(),
                     [](const Subscription& flag) { return flag.Available(); })) {
      return false;
    }
    last_manual_refresh_ = now;
    Refresh(true);
    return true;
  }
""" + anchor),
        ("  uint64_t generation_=0;", "  base::TimeTicks last_manual_refresh_;\n  uint64_t generation_=0;")])

    anchor = '#include "chrome/android/chrome_jni_headers/ChromeBackupWatcher_jni.h"'
    registrations = (ROOT / "status_jni.cc.inc").read_text()
    edit(MAIN, [(anchor, anchor + '\n#include "chrome/android/chrome_jni_headers/RawsProtectionCopy_jni.h"'),
                ("DEFINE_JNI(ChromeBackupWatcher)", registrations + "\nDEFINE_JNI(ChromeBackupWatcher)\nDEFINE_JNI(RawsProtectionCopy)")])

    anchor = "import org.chromium.build.annotations.NullMarked;"
    edit(JAVA + "RawsProtectionCopy.java", [(anchor, """import org.jni_zero.JNINamespace;
import org.jni_zero.JniType;
import org.jni_zero.NativeMethods;

""" + anchor),
        ("import org.chromium.chrome.R;", "import org.chromium.chrome.R;\nimport org.chromium.chrome.browser.profiles.Profile;"),
        ("@NullMarked\npublic final class", '@JNINamespace("android")\n@NullMarked\npublic final class'),
        ("    private RawsProtectionCopy() {}", """    private RawsProtectionCopy() {}

    public static int currentStatusStringId() {
        return statusStringId(RawsProtectionCopyJni.get().getAdFilteringPhase());
    }

    static int statusStringId(int phase) {
        return switch (phase) {
            case 1 -> stringId(Phase.FAILED, false, false);
            case 2 -> stringId(Phase.LOADING, false, false);
            case 3 -> R.string.raws_ui_builtin_ad_filtering_active;
            default -> stringId(Phase.UNKNOWN, false, false);
        };
    }

    static boolean requestFilterRefresh(Profile profile) {
        return !profile.isOffTheRecord() && profile.isNativeInitialized()
                && RawsProtectionCopyJni.get().requestFilterRefresh(profile);
    }

    @NativeMethods
    interface Natives {
        int getAdFilteringPhase();
        boolean requestFilterRefresh(@JniType("Profile*") Profile profile);
    }""")])
    edit(JAVA + "RawsGlobalShieldSheet.java", [
        ("status.setText(RawsProtectionCopy.stringId(\n                RawsProtectionCopy.Phase.UNKNOWN, false, false));",
         "status.setText(RawsProtectionCopy.currentStatusStringId());")])
    edit(JAVA + "RawsProtectionSettings.java", [
        ("import android.os.Bundle;", "import android.os.Bundle;\nimport android.widget.Toast;"),
        ("/** Native Protection settings entry, without inventing feature switches. */",
         "/** Native Protection settings with read-only status and a real filter refresh action. */"),
        ("""        Preference status = findPreference("raws_global_protection_status");""", """        Preference refresh = findPreference("raws_refresh_filters");
        if (refresh != null) {
            refresh.setOnPreferenceClickListener(preference -> {
                boolean accepted = RawsProtectionCopy.requestFilterRefresh(getProfile());
                Toast.makeText(requireContext(),
                        accepted ? R.string.raws_ui_refresh_requested
                                 : R.string.raws_ui_refresh_not_started,
                        Toast.LENGTH_SHORT).show();
                return true;
            });
        }
        updateStatus();
    }

    @Override
    public void onResume() {
        super.onResume();
        updateStatus();
    }

    private void updateStatus() {
        Preference status = findPreference("raws_global_protection_status");"""),
        ("status.setSummary(RawsProtectionCopy.stringId(\n                    RawsProtectionCopy.Phase.UNKNOWN, false, false));",
         "status.setSummary(RawsProtectionCopy.currentStatusStringId());")])
    edit(RES + "xml/raws_protection_preferences.xml", [
        ("    <org.chromium.components.browser_ui.settings.ChromeBasePreference\n        android:key=\"raws_protection_privacy\"",
         """    <org.chromium.components.browser_ui.settings.ChromeBasePreference
        android:key="raws_refresh_filters"
        android:title="@string/raws_ui_refresh_filters"
        android:summary="@string/raws_ui_refresh_filters_description"
        android:persistent="false" />
    <org.chromium.components.browser_ui.settings.ChromeBasePreference
        android:key="raws_protection_privacy\"""")])
    edit(RES + "values/raws_global_shield_strings.xml", [("</resources>", """    <string name="raws_ui_builtin_ad_filtering_active">Built-in ad filtering is active</string>
    <string name="raws_ui_refresh_filters">Refresh filter lists</string>
    <string name="raws_ui_refresh_filters_description">Check for updates to enabled lists. Current protection stays active.</string>
    <string name="raws_ui_refresh_requested">Filter refresh requested</string>
    <string name="raws_ui_refresh_not_started">Refresh did not start. Try again later.</string>
</resources>""")])

    output.mkdir()
    for relative_path, (_, data) in transformed.items():
        p = output / relative_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    (output / "ad-ui-receipt.json").write_text(json.dumps({
        "base_commit": BASE,
        "base_recipe_sha256": MANIFEST_SHA,
        "files": {
            n: {"input_sha256": expected, "output_sha256": sha(data)}
            for n, (expected, data) in sorted(transformed.items())
        },
    }, indent=2) + "\n")
    return len(transformed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("repo", "upstream_build", "output"):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    print("Generated", compose(args.repo.resolve(), args.upstream_build.resolve(),
                              args.output.resolve()), "review files")
