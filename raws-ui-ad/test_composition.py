# SPDX-License-Identifier: MPL-2.0
"""Host checks on generated Chromium snippets, not an Android build."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

from compose import ANDROID, FACTORY, JAVA, MAIN, RES, SERVICE

SRC = Path(os.environ["RAWS_AD_UI_DELTA"])


class IntegrationTest(unittest.TestCase):
    def source(self, file):
        return (SRC / file).read_text()

    def test_jni_input_and_reference(self):
        relative_java = JAVA + "RawsProtectionCopy.java"
        source = self.source(ANDROID + "BUILD.gn")
        jni_target = source.split('generate_jni("chrome_jni_headers") {', 1)[1].split("\n  }", 1)[0]
        self.assertEqual(jni_target.count(relative_java.removeprefix(ANDROID)), 1)
        java = self.source(relative_java)
        native = self.source(MAIN)
        for method in ("getAdFilteringPhase", "requestFilterRefresh"):
            self.assertIn(method, java)
            self.assertIn("JNI_RawsProtectionCopy_" + method[0].upper() + method[1:], native)
        self.assertEqual(native.count("DEFINE_JNI(RawsProtectionCopy)"), 1)

    def test_refresh_preference_has_no_fake_switch(self):
        ns = "{http://schemas.android.com/apk/res/android}"
        preferences = ET.fromstring(self.source(RES + "xml/raws_protection_preferences.xml"))
        by_key = {p.attrib[ns + "key"]: p for p in preferences}
        refresh = by_key["raws_refresh_filters"]
        self.assertTrue(refresh.tag.endswith("ChromeBasePreference"))
        self.assertEqual(refresh.attrib[ns + "persistent"], "false")
        strings = {s.attrib["name"] for s in ET.fromstring(
            self.source(RES + "values/raws_global_shield_strings.xml"))}
        for key in ("title", "summary"):
            self.assertIn(refresh.attrib[ns + key].removeprefix("@string/"), strings)
        self.assertIn("RawsProtectionCopy.currentStatusStringId()", self.source(JAVA + "RawsGlobalShieldSheet.java"))
        settings = self.source(JAVA + "RawsProtectionSettings.java")
        self.assertIn("RawsProtectionCopy.requestFilterRefresh(getProfile())", settings)
        self.assertIn("RawsProtectionCopy.currentStatusStringId()", settings)

    def test_generated_native_semantics(self):
        state_enum = re.search(r"enum class OfflineRulesPhase : int \{.*?\};", self.source(FACTORY + ".h"), re.S)[0]
        phase = re.search(r"OfflineRulesPhase GetOfflineRulesPhase\(\) \{.*?\n\}", self.source(FACTORY + ".cc"), re.S)[0]
        manual = re.search(r"  bool RequestManualRefresh\(\) \{.*?\n  \}", self.source(SERVICE), re.S)[0]
        code = """
#include <algorithm>
#include <array>
#include <cassert>
#include <set>
namespace base {
int now = 1;
int Minutes(int mins) { return 60 * mins; }
struct TimeTicks {
  int stamp = 0;
  static TimeTicks Now() { return {now}; }
  bool is_null() const { return stamp == 0; }
  int operator-(TimeTicks old) const { return stamp - old.stamp; }
};
}
struct State { bool ready=false; bool failed=false; bool attempted=false; };
State& GetState() { static State state; return state; }
""" + state_enum + "\n" + phase + """
struct Subscription {
  bool enabled = true;
  bool Available() const { return enabled; }
};
struct Dummy {
  bool started_ = false;
  std::set<int> queue_, busy_;
  std::array<Subscription, 2> flags_{};
  base::TimeTicks last_manual_refresh_;
  int accepted_batches = 0;
  void Refresh(bool manual) { assert(manual); ++accepted_batches; }
""" + manual + """
};
int main() {
  auto& state = GetState();
  assert(GetOfflineRulesPhase() == OfflineRulesPhase::kUnknown);
  state.attempted = true;
  assert(GetOfflineRulesPhase() == OfflineRulesPhase::kLoading);
  state.ready = true;
  assert(GetOfflineRulesPhase() == OfflineRulesPhase::kReady);
  state.ready = false;
  state.failed = true;
  assert(GetOfflineRulesPhase() == OfflineRulesPhase::kFailed);
  Dummy d;
  assert(!d.RequestManualRefresh());
  d.started_ = true;
  d.queue_.insert(0);
  assert(!d.RequestManualRefresh());
  d.queue_.clear();
  d.busy_.insert(0);
  assert(!d.RequestManualRefresh());
  d.busy_.clear();
  d.flags_.at(0).enabled = false;
  d.flags_.at(1).enabled = false;
  assert(!d.RequestManualRefresh());
  d.flags_.at(1).enabled = true;
  assert(d.RequestManualRefresh());
  assert(d.accepted_batches == 1);
  base::now = 60;
  assert(!d.RequestManualRefresh());
  base::now = 61;
  assert(d.RequestManualRefresh());
  assert(d.accepted_batches == 2);
}
"""
        with tempfile.TemporaryDirectory() as work:
            temp = Path(work)
            (temp / "host.cc").write_text(code)
            subprocess.run(["c++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                            "host.cc", "-o", "host"], cwd=temp, check=True)
            subprocess.run(["./host"], cwd=temp, check=True)

    def test_generated_java_errors_remain_unknown_and_profile_is_guarded(self):
        with tempfile.TemporaryDirectory() as work:
            temp = Path(work)

            def put(path, plain):
                file = temp / path
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(plain)

            java = self.source(JAVA + "RawsProtectionCopy.java")
            put("org/chromium/chrome/browser/settings/RawsProtectionCopy.java", java)
            for annotation in ("JNINamespace", "JniType", "NativeMethods"):
                put(f"org/jni_zero/{annotation}.java",
                    f"package org.jni_zero; public @interface {annotation} {{ String value() default \"\"; }}")
            for annotation in ("NullMarked", "Nullable"):
                put(f"org/chromium/build/annotations/{annotation}.java",
                    f"package org.chromium.build.annotations; public @interface {annotation} {{}}")
            put("org/chromium/chrome/R.java", "package org.chromium.chrome; public class R { public static class string {"
                + "".join(f" public static final int {n}={i};" for i, n in enumerate(
                    sorted(set(re.findall(r"R.string.(\w+)", java))), 10)) + "} }")
            put("org/chromium/chrome/browser/profiles/Profile.java", """
package org.chromium.chrome.browser.profiles;
public class Profile {
  public boolean incognito;
  public boolean initialized = true;
  public boolean isOffTheRecord() { return incognito; }
  public boolean isNativeInitialized() { return initialized; }
}
""")
            put("org/chromium/chrome/browser/settings/RawsProtectionCopyJni.java", """
package org.chromium.chrome.browser.settings;
import org.chromium.chrome.browser.profiles.Profile;
class RawsProtectionCopyJni implements RawsProtectionCopy.Natives {
  static RawsProtectionCopyJni get() { return new RawsProtectionCopyJni(); }
  static int phase;
  static int requests;
  public int getAdFilteringPhase() { return phase; }
  public boolean requestFilterRefresh(Profile profile) { ++requests; return true; }
}
""")
            put("org/chromium/chrome/browser/settings/TestStatus.java", """
package org.chromium.chrome.browser.settings;
import org.chromium.chrome.R;
import org.chromium.chrome.browser.profiles.Profile;
class TestStatus {
  public static void main(String[] args) {
    for (int phase : new int[] {-1, 0, 4, 2147483647}) {
      RawsProtectionCopyJni.phase = phase;
      assert RawsProtectionCopy.currentStatusStringId() == R.string.raws_ui_unknown;
    }
    RawsProtectionCopyJni.phase = 1;
    assert RawsProtectionCopy.currentStatusStringId() == R.string.raws_ui_unavailable;
    RawsProtectionCopyJni.phase = 2;
    assert RawsProtectionCopy.currentStatusStringId() == R.string.raws_ui_preparing;
    RawsProtectionCopyJni.phase = 3;
    assert RawsProtectionCopy.currentStatusStringId() == R.string.raws_ui_builtin_ad_filtering_active;
    Profile p = new Profile();
    p.incognito = true;
    assert !RawsProtectionCopy.requestFilterRefresh(p);
    p.incognito = false;
    p.initialized = false;
    assert !RawsProtectionCopy.requestFilterRefresh(p);
    assert RawsProtectionCopyJni.requests == 0;
    p.initialized = true;
    assert RawsProtectionCopy.requestFilterRefresh(p);
    assert RawsProtectionCopyJni.requests == 1;
  }
}
""")
            subprocess.run(["javac", *[str(p) for p in temp.rglob("*.java")]], cwd=temp, check=True)
            subprocess.run(["java", "-ea", "org.chromium.chrome.browser.settings.TestStatus"], cwd=temp, check=True)


if __name__ == "__main__":
    unittest.main()
