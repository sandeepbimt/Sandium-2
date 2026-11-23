import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import manual_home_shortcuts as change

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO.parent / 'chromium-52bdd-preimages'
POST = REPO / 'raws-adblock/production-postimages'
RECIPE = REPO / 'raws-adblock/production-restore-recipe.json'


def definition(text, prefix):
    start = text.index(prefix)
    levels = 1
    opening = text.index('{', start)
    for i in range(opening + 1, len(text)):
        levels += (text[i] == '{') - (text[i] == '}')
        if not levels:
            return text[start:i + 1]
    raise ValueError(prefix)


class ManualShortcutsTest(unittest.TestCase):
    def setUp(self):
        self.recipe = json.loads(RECIPE.read_text())['files']
        self.raw = {}
        for path, digest in change.OWNERS.items():
            for source in (FIXTURES / path, POST / digest):
                if source.is_file():
                    self.raw[path] = source.read_bytes()
                    break
            else:
                self.skipTest(f'Pinned Chromium fixture not installed: {path}')
        self.out = {path: change.transform(path, data).decode() for path, data in self.raw.items()}

    def test_exact_replay_and_native_abi(self):
        for path, data in self.raw.items():
            self.assertEqual(hashlib.sha256(data).hexdigest(), change.OWNERS[path])
            post = self.out[path].encode()
            self.assertNotEqual(data, post)
            if self.recipe.get(path):
                self.assertEqual(hashlib.sha256(post).hexdigest(), self.recipe[path]['after_sha256'])
            with self.assertRaises(ValueError):
                change.transform(path, data + b'\n')
        with self.assertRaises(ValueError):
            change.transform('other.cc', self.raw[change.BRIDGE])
        bridge = self.out[change.BRIDGE]
        self.assertIn('JNI_MostVisitedSitesBridge_Init(Profile* profile)', bridge)
        self.assertIn('!profile->IsOffTheRecord() &&', bridge)
        self.assertIn('== "io.github.sandeepbimt.raws" &&', bridge)
        for outside in ('tablet', 'desktop', 'tv', 'automotive', 'xr', 'foldable'):
            self.assertIn(f'!device::is_{outside}()', bridge)
        self.assertNotIn('ui/base/device_form_factor.h', bridge)
        self.assertIn('.with_top_sites(!manual_shortcuts_only)', bridge)
        self.assertIn('.with_manual_custom_links_only(manual_shortcuts_only)', bridge)

    def test_ui_keeps_explicit_add_and_does_not_inject_ai(self):
        base = 'chrome/android/java/src/org/chromium/chrome/browser/ntp/'
        def read(name):
            return (POST / self.recipe[base + name]['after_sha256']).read_text()
        self.assertIn('bridge.addCustomLink(title, url, /* pos= */ 0)', read('NewTabPage.java'))
        self.assertIn('return LayoutType.REMOVE;', read('NewTabPageUtils.java'))
        sites = self.out[change.SITES]
        self.assertIn('if (!enabled_tile_types_.manual_custom_links_only && popular_sites_', sites)
        self.assertEqual(sites.count('!enabled_tile_types_.manual_custom_links_only && top_sites_'), 2)
        self.assertIn('manual_custom_links_only && link.is_most_visited', sites)

    def test_actual_policy_methods_manual_and_stock(self):
        cxx = os.getenv('CXX') or shutil.which('g++') or shutil.which('clang++')
        if not cxx:
            self.skipTest('No local C++ compiler')
        store, sites = self.out[change.STORE], self.out[change.SITES]
        compiled = [
            definition(store, 'void CustomLinksManagerImpl::SetManualLinksOnly()'),
            definition(store, 'bool CustomLinksManagerImpl::Initialize('),
            definition(store, 'void CustomLinksManagerImpl::OnPreferenceChanged()'),
            definition(sites, 'bool MostVisitedSites::ShouldQueryTopSites() const'),
            definition(sites, 'void MostVisitedSites::BuildCurrentTiles('),
            definition(sites, 'void MostVisitedSites::InitializeCustomLinks()'),
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            source = path / 'shortcut.cc'
            source.write_text(HARNESS_HEAD + '\n'.join(compiled) + HARNESS_MAIN)
            binary = path / 'shortcut'
            subprocess.run([cxx, '-std=c++20', '-Wall', '-Wextra', '-Werror',
                            source, '-o', binary], check=True)
            subprocess.run([binary], check=True)


HARNESS_HEAD = r"""
#include <algorithm>
#include <cassert>
#include <map>
#include <optional>
#include <vector>

namespace base {
template<class T> class AutoReset {
 public:
  AutoReset(T* dest, T value) : dest_(dest), original_(*dest) { *dest_ = value; }
  ~AutoReset() { *dest_ = original_; }
 private:
  T* dest_;
  T original_;
};
}
enum class TileSource { HISTORY, ENTERPRISE_SHORTCUTS };
enum class SectionType { PERSONALIZED };
struct NTPTile { int url; int title; TileSource source; };
using NTPTilesVector = std::vector<NTPTile>;
struct Prefs {
  bool initialized = false;
  void SetBoolean(int key, bool value) { assert(key == 0); initialized = value; }
};
struct CustomLinksManagerImpl {
  struct Link { int url; int title; bool is_most_visited; };
  struct Disk {
    std::vector<Link> history;
    std::vector<Link> RetrieveLinks() const { return history; }
  } store_;
  struct Listeners { void Notify() {} } closure_list_;
  std::vector<Link> current_links_;
  std::optional<std::vector<Link>> previous_links_;
  bool manual_links_only_ = false;
  Prefs local_prefs_;
  Prefs* prefs_ = &local_prefs_;
  bool updating_preferences_ = false;
  const int custom_links_initialized_pref_ = 0;
  int writes = 0;
  bool IsInitialized() const { return prefs_->initialized; }
  void StoreLinks() { ++writes; store_.history = current_links_; }
  void SetManualLinksOnly();
  bool Initialize(const NTPTilesVector&);
  void OnPreferenceChanged();
};
struct MostVisitedSites {
  struct Options {
    bool manual_custom_links_only = false, top_sites = true, custom_links = true;
  } enabled_tile_types_;
  std::optional<NTPTilesVector> current_tiles_;
  CustomLinksManagerImpl* custom_links_manager_ = nullptr;
  int custom_links_action_count_ = -1, queries = 0, reloads = 0, notifies = 0;
  bool IsTopSitesEnabled() const { return enabled_tile_types_.top_sites; }
  bool IsCustomLinksEnabled() const { return enabled_tile_types_.custom_links; }
  bool IsCustomLinksInitialized() const {
    return custom_links_manager_ && custom_links_manager_->IsInitialized();
  }
  void InitiateTopSitesQuery(bool) { ++queries; }
  void ReloadCustomLinksCache() { ++reloads; }
  void SaveTilesAndNotify(bool, NTPTilesVector tiles,
                          std::map<SectionType, NTPTilesVector> sections) {
    assert(tiles.empty() && sections.empty());
    ++notifies;
  }
  bool ShouldQueryTopSites() const;
  void BuildCurrentTiles(bool);
  void InitializeCustomLinks();
};
"""

HARNESS_MAIN = r"""
int main() {
  CustomLinksManagerImpl new_store;
  new_store.SetManualLinksOnly();
  assert(new_store.writes == 0);
  MostVisitedSites sites;
  sites.custom_links_manager_ = &new_store;
  sites.enabled_tile_types_ = {true, false, true};
  assert(!sites.ShouldQueryTopSites());
  sites.BuildCurrentTiles(false);
  assert(sites.notifies == 1 && sites.queries == 0 && sites.reloads == 1);
  assert(!sites.current_tiles_.has_value());  // Menu Add before subscribing/displaying Home.
  sites.InitializeCustomLinks();
  assert(new_store.IsInitialized() && sites.custom_links_action_count_ == 0);
  assert(new_store.current_links_.empty() && new_store.writes == 1);

  CustomLinksManagerImpl old_store;
  old_store.local_prefs_.initialized = true;
  old_store.store_.history = {{1, 10, true}, {2, 20, false},
                              {3, 30, true}, {4, 40, false}};
  old_store.OnPreferenceChanged();
  assert(old_store.current_links_.size() == 4);
  old_store.SetManualLinksOnly();
  assert(old_store.writes == 0 && old_store.store_.history.size() == 4);
  assert(old_store.current_links_.size() == 2 &&
         old_store.current_links_[0].url == 2 && old_store.current_links_[1].url == 4);
  old_store.store_.history.push_back({5, 50, false});
  old_store.OnPreferenceChanged();
  assert(old_store.current_links_.size() == 3 && old_store.current_links_[2].url == 5);
  assert(old_store.writes == 0);

  CustomLinksManagerImpl stock;
  sites.custom_links_manager_ = &stock;
  sites.enabled_tile_types_ = {false, false, true};
  assert(sites.ShouldQueryTopSites());  // Stock standalone fallback still intact.
  sites.current_tiles_ = NTPTilesVector{{8, 80, TileSource::HISTORY}};
  sites.InitializeCustomLinks();
  assert(stock.IsInitialized() && stock.current_links_.size() == 1);
  assert(stock.current_links_[0].url == 8 && stock.current_links_[0].is_most_visited);
  assert(!sites.ShouldQueryTopSites());
}
"""

if __name__ == '__main__':
    unittest.main()
