"""Use the admitted production postimages rather than only testing string builders."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import darken_follows_dark_pages as d
import seal

ROOT = Path(__file__).resolve().parents[1]


class DarkenFollowsDarkPages(unittest.TestCase):
    def setUp(self):
        self.recipe = json.loads((ROOT / seal.RECIPE).read_text())['files']

    def code(self, owner):
        path = ROOT / seal.IMAGE / self.recipe[owner]['after_sha256']
        return path.read_text()

    def test_only_expected_sealed_owners_and_inputs(self):
        read = lambda name: seal.git('show', d.BASE + ':' + name)
        patch = seal.plan(read, owners=d.OWNERS, edit=d.transform, man=d.MAN, proof=d.PROOF)
        original = json.loads(read(seal.RECIPE))['files']
        self.assertEqual(set(original), set(self.recipe))
        self.assertEqual({k for k in original if original[k] != self.recipe[k]}, set(d.OWNERS))
        for k in original:
            self.assertEqual(original[k].get('before_sha256'), self.recipe[k].get('before_sha256'))
        for name, data in patch.items():
            self.assertEqual((ROOT / name).read_bytes(), data, name)

    def test_welcome_applies_dark_pages_but_only_blur_needs_restart(self):
        welcome = self.code(d.WELCOME)
        self.assertNotIn('Darken', welcome)
        self.assertNotIn('raws_setup_darken', self.code(d.WELCOME_XML))
        self.assertIn('state.putBoolean("dark_pages", mStagedDarkPages)', welcome)
        self.assertIn('state.getBoolean("dark_pages", mStagedDarkPages)', welcome)
        self.assertIn('RawSDarkPages.setGlobal(profile, mStagedDarkPages)', welcome)
        self.assertIn('return !mInitialBlur.equals(mStagedBlur);', welcome)
        self.assertIn('if (restartNeeded()\n                && !RawSNavigationAppearance.commitBlurLevel(mStagedBlur))', welcome)
        self.assertLess(welcome.index('RawSDarkPages.setGlobal(profile, mStagedDarkPages)'),
                        welcome.index('RawSNavigationAppearance.commitBlurLevel(mStagedBlur)'))

    def test_appearance_and_startup_only_expose_independent_blur(self):
        appearance = self.code(d.APP)
        self.assertIn('if (darkPages == null || blur == null) return;', appearance)
        self.assertIn('RawSDarkPages.setGlobal(', appearance)
        self.assertIn('RawSNavigationAppearance.setBlurLevel(', appearance)
        self.assertNotIn('raws_parity_darken_transition', self.code(d.PREF_XML))
        self.assertNotIn('raws_settings_darken_transition', self.code(d.SETTINGS_XML))
        startup = self.code(d.STARTUP)
        self.assertNotIn('DARKEN_PREF', startup)
        self.assertNotIn('nav-animation-darken', startup)
        self.assertIn('commandLine.appendSwitchWithValue(DISABLE, appendFeature(disable, FEATURE));', startup)
        self.assertIn('commandLine.appendSwitchWithValue(ENABLE, appendFeature(enable, FEATURE));', startup)

    def test_only_changes_filter_not_chromium_lifecycle(self):
        after = self.code(d.BLUR)
        before = (ROOT / seal.IMAGE / d.OWNERS[d.BLUR]).read_text()
        self.assertEqual(after.replace(
            'GetContentClient()->browser()->ShouldDarkenRawSNavigation(\n'
            '          web_contents(), navigation_handle->GetURL())',
            'features::kAndroidNavigationAnimationDarken.Get()'), before)
        self.assertIn('virtual bool ShouldDarkenRawSNavigation', self.code(d.CLIENT_H))
        self.assertIn('const GURL& destination) override;', self.code(d.CCB_H))
        self.assertIn('bool ContentBrowserClient::ShouldDarkenRawSNavigation', self.code(d.CLIENT))

    def test_extract_native_target_logic_checks_effective_profile_url(self):
        cxx = shutil.which('c++')
        if cxx is None:
            self.skipTest('host C++ compiler not available')
        body = self.code(d.CCB)
        body = body[body.index('bool ChromeContentBrowserClient::ShouldDarkenRawSNavigation('):
                    body.index('int ChromeContentBrowserClient::GetRawSPageTextPolicyForNavigation(')]
        fixture = r'''#include <cassert>
#define BUILDFLAG(flag) 1
enum class ContentSettingsType { AUTO_DARK_WEB_CONTENT };
enum ContentSetting { CONTENT_SETTING_ALLOW, CONTENT_SETTING_BLOCK };
struct GURL {
  int id; bool valid = true; bool web = true;
  bool is_valid() const { return valid; }
  bool SchemeIsHTTPOrHTTPS() const { return web; }
};
struct Map {
  bool allow_default; int allow_override; int block_override;
  ContentSetting GetContentSetting(const GURL& a, const GURL& b, ContentSettingsType type) {
    assert(a.id == b.id && type == ContentSettingsType::AUTO_DARK_WEB_CONTENT);
    if (a.id == allow_override) return CONTENT_SETTING_ALLOW;
    if (a.id == block_override) return CONTENT_SETTING_BLOCK;
    return allow_default ? CONTENT_SETTING_ALLOW : CONTENT_SETTING_BLOCK;
  }
};
struct Profile {
  Map* map;
  static Profile* FromBrowserContext(Profile* p) { return p; }
};
struct HostContentSettingsMapFactory {
  static Map* GetForProfile(Profile* p) { return p->map; }
};
namespace content {
struct WebContents {
  Profile* profile;
  Profile* GetBrowserContext() { return profile; }
};
}
struct ChromeContentBrowserClient {
  bool ShouldDarkenRawSNavigation(content::WebContents*, const GURL&);
};
'''
        main = r'''
int main() {
  ChromeContentBrowserClient browser;
  Map regular{true, 7, 42};
  Map otr{false, 42, -1};
  Profile normal{&regular}, private_context{&otr}, missing{nullptr};
  content::WebContents normal_tab{&normal}, private_tab{&private_context}, no_map{&missing};
  auto f = [&](auto* w, GURL u) { return browser.ShouldDarkenRawSNavigation(w, u); };
  assert(f(&normal_tab, GURL{1}));
  assert(!f(&normal_tab, GURL{42}));  // site block wins over global on
  assert(f(&private_tab, GURL{42}));  // different active profile, explicit site allow
  assert(!f(&private_tab, GURL{7}));
  otr.allow_default = true;
  assert(f(&private_tab, GURL{7}));  // next eligible navigation sees a live change
  assert(!f(&normal_tab, GURL{1, true, false}));
  assert(!f(&normal_tab, GURL{1, false, true}));
  assert(!f(&no_map, GURL{1}));
}
'''
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / 'fixture.cc'
            binary = Path(t) / 'fixture'
            src.write_text(fixture + body + main)
            subprocess.run([cxx, '-std=c++23', '-Wall', '-Wextra', '-Werror', str(src),
                            '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
