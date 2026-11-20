"""Host regression checks for the ad-redirect profile policy."""
from pathlib import Path
import subprocess
import tempfile
import unittest

import policy


class PolicyTest(unittest.TestCase):
    def test_overlay_replays_and_rejects_drift_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, edits in policy.EDITS.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("\n".join(anchor for anchor, _, _ in edits))
            planned = policy.plan(root)
            self.assertEqual(len(planned), len(policy.EDITS))
            for path, text in planned.items():
                path.write_text(text)
            self.assertFalse(policy.plan(root))
            header = root / (policy.SHIELDS + ".h")
            header.write_text(header.read_text().replace("kAllow = 2", "kAllow = 3"))
            before = {path: path.read_text() for path in planned}
            with self.assertRaises(ValueError):
                policy.plan(root)
            self.assertEqual(before, {path: path.read_text() for path in planned})

    def test_policy_is_shared_with_the_supplied_profile_and_ui_ordinals(self):
        self.assertIn("kDefault = 0, kBlock = 1, kAllow = 2", policy.DECLARATIONS)
        for number, name in enumerate(("DEFAULT", "BLOCK", "ALLOW")):
            self.assertIn(f"AD_REDIRECT_{name} = {number};", policy.JAVA_API)
        self.assertNotIn("GetOriginalProfile", policy.JNI)
        self.assertEqual(policy.JNI.count("Profile::FromJavaObject(j_profile)"), 4)
        self.assertIn("RegisterBooleanPref(brave_shields::kBlockAdRedirects, true)", policy.REGISTER)
        self.assertIn("RegisterDictionaryPref(brave_shields::kAdRedirectSiteOverrides)", policy.REGISTER)

    def test_actual_native_policy_decisions(self):
        # Execute the emitted functions with small profile stores and precomputed
        # origins. URL canonicalization and private pref storage belong to Chromium.
        helpers = r"""
#include <cassert>
#include <map>
#include <optional>
#include <string>
#define BUILDFLAG(x) 1
struct GURL {
  std::string origin;
  bool valid = true, web = true;
  bool is_valid() const { return valid; }
  bool SchemeIsHTTPOrHTTPS() const { return web; }
};
namespace url {
struct Origin {
  std::string serialized;
  static Origin Create(const GURL& url) { return {url.origin}; }
  std::string Serialize() const { return serialized; }
};
}
struct Dict {
  std::map<std::string, bool> data;
  std::optional<bool> FindBool(const std::string& key) const {
    if (auto it = data.find(key); it != data.end()) return it->second;
    return std::nullopt;
  }
  void Remove(const std::string& key) { data.erase(key); }
  void Set(const std::string& key, bool value) { data[key] = value; }
};
struct PrefService {
  bool enabled = true;
  Dict dict;
  int writes = 0;
  const Dict& GetDict(const char* pref) const {
    assert(std::string(pref) == "sandium.ad_redirect_site_overrides");
    return dict;
  }
  bool GetBoolean(const char* pref) const {
    assert(std::string(pref) == "sandium.block_ad_redirects");
    return enabled;
  }
};
struct ScopedDictPrefUpdate {
  PrefService* prefs;
  ScopedDictPrefUpdate(PrefService& p, const char* key) : prefs(&p) {
    assert(std::string(key) == "sandium.ad_redirect_site_overrides");
    ++prefs->writes;
  }
  Dict* operator->() { return &prefs->dict; }
};
"""
        main = r"""
int main() {
  using Choice = AdRedirectSiteSetting;
  const GURL a{"https://shop.example"}, b{"https://shop.example:8443"},
      c{"http://shop.example"}, subdomain{"https://sub.shop.example"},
      native{"chrome://settings", true, false}, invalid{"", false, false};
  PrefService one, two;
  assert(ShouldBlockAdRedirect(one, a));
  one.enabled = false;
  assert(!ShouldBlockAdRedirect(one, a));
  SetAdRedirectSiteSetting(one, a, Choice::kBlock);
  assert(GetAdRedirectSiteSetting(one, a) == Choice::kBlock);
  assert(ShouldBlockAdRedirect(one, a) && !ShouldBlockAdRedirect(one, b));
  assert(!ShouldBlockAdRedirect(one, c) && !ShouldBlockAdRedirect(one, subdomain));
  assert(GetAdRedirectSiteSetting(two, a) == Choice::kDefault);
  SetAdRedirectSiteSetting(one, a, Choice::kBlock);
  assert(one.writes == 1);
  one.enabled = true;
  SetAdRedirectSiteSetting(one, a, Choice::kAllow);
  assert(!ShouldBlockAdRedirect(one, a) && ShouldBlockAdRedirect(one, b));
  SetAdRedirectSiteSetting(one, a, Choice::kDefault);
  assert(one.dict.data.empty() && ShouldBlockAdRedirect(one, a));
  one.enabled = false;
  assert(!ShouldBlockAdRedirect(one, a));
  for (const auto& skip : {native, invalid}) {
    SetAdRedirectSiteSetting(one, skip, Choice::kBlock);
    assert(!ShouldBlockAdRedirect(one, skip));
    assert(GetAdRedirectSiteSetting(one, skip) == Choice::kDefault);
  }
  assert(one.writes == 3);
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "policy.cc"
            binary = Path(tmp) / "policy"
            source.write_text(helpers + policy.DECLARATIONS + policy.FUNCTIONS + main)
            subprocess.run(["c++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                            str(source), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()
