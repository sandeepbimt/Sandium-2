#!/usr/bin/env python3
"""Pinned actual native UpdateLink host test, not Android/restart instrumentation."""
from pathlib import Path
import hashlib, subprocess, tempfile
repo=Path(__file__).resolve().parents[2]
fixtures=repo/'.circleci/tests/fixtures/home-rename'
for name, expected in [('custom_links_manager_impl.cc','bce188c0c73e908369d99a95a8ae1dc0e3e50de6'),('most_visited_sites_bridge.cc','90f9a6e1dc6eb21e018121d5caba10ff64465585')]:
    raw=(fixtures/name).read_bytes()
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==expected, name
source=(fixtures/'custom_links_manager_impl.cc').read_text()
body=source[source.index('bool CustomLinksManagerImpl::UpdateLink('):source.index('\nbool CustomLinksManagerImpl::ReorderLink(')]
bridge=(fixtures/'most_visited_sites_bridge.cc').read_text()
assert 'const GURL& url_to_use = (key_url == url) ? GURL() : url;' in bridge
assert 'return most_visited_->UpdateCustomLink(key_url, url_to_use, name);' in bridge
harness=r'''
#include <algorithm>
#include <cassert>
#include <optional>
#include <string>
#include <vector>
struct GURL {
 std::string value;
 GURL(std::string v=""):value(v){}
 bool is_valid() const { return !value.empty(); }
 bool is_empty() const { return value.empty(); }
 bool operator==(const GURL& other) const { return value==other.value; }
};
const char* kAiModeTileUrl="https://ai.test";
namespace custom_links_util {
 template<class T> auto FindLinkWithUrl(std::vector<T>& list,const GURL& url) {
  return std::find_if(list.begin(),list.end(),[&](const T& x){return x.url==url;});
 }
}
struct CustomLinksManagerImpl {
 struct Link { GURL url; std::u16string title; bool is_most_visited; };
 std::vector<Link> current_links_,stored;
 std::optional<std::vector<Link>> previous_links_;
 bool initialized=true; int writes=0;
 bool IsInitialized() const { return initialized; }
 void StoreLinks() { stored=current_links_; ++writes; }
 bool UpdateLink(const GURL&,const GURL&,const std::u16string&);
};
'''
tests=r'''
int main() {
 CustomLinksManagerImpl m;
 m.current_links_={{{"https://a.test"},u"A",false},{{"https://b.test"},u"B",false},{{"https://c.test"},u"C",false}};
 auto original=m.current_links_;
 assert(m.UpdateLink({"https://b.test"},{},u"My renamed shortcut"));
 assert(m.writes==1 && m.current_links_.size()==3);
 for (size_t i=0;i<3;i++) assert(m.current_links_[i].url==original[i].url);
 assert(m.current_links_[1].title==u"My renamed shortcut");
 CustomLinksManagerImpl reopened;reopened.current_links_=m.stored;
 assert(reopened.current_links_[1].title==u"My renamed shortcut");
 assert(reopened.current_links_[0].title==u"A" && reopened.current_links_[2].title==u"C");
 assert(!m.UpdateLink({"https://missing.test"},{},u"No resurrection"));
 assert(!m.UpdateLink({"https://b.test"},{},u""));
 assert(!m.UpdateLink({}, {},u"Invalid"));
 assert(m.writes==1);
 m.initialized=false;assert(!m.UpdateLink({"https://b.test"},{},u"Rejected"));
 assert(m.writes==1);
}
'''
with tempfile.TemporaryDirectory() as td:
    path=Path(td)/'rename.cc';path.write_text(harness+body+tests)
    exe=Path(td)/'rename';subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror',str(path),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
java=(repo/'android/java/org/chromium/chrome/browser/suggestions/mostvisited/SandiumHomeShortcuts.java').read_text()
rename=java[java.index('    private void renameDialog('):java.index('    private static boolean safe(')]
assert 'assignCustomLink(site.url, title, site.url)' in rename
assert 'hasCustomLink(site.url)' in rename and 'indexForUrl(site.url) < 0' in rename
assert 'deleteCustomLink' not in rename and 'addCustomLink' not in rename and 'reorderCustomLink' not in rename
assert 'setNegativeButton(R.string.sandium_home_cancel, null)' in rename
assert 'getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener' in rename
assert 'Character.isSpaceChar(c)' in rename and 'name.setError' in rename
assert 'name.setContentDescription' in rename and 'name.requestFocus()' in rename
assert 'if (mDialog == dialog) mDialog = null;' in rename
assert 'R.string.sandium_home_rename' in java[java.index('private void editDialog'):java.index('private void renameDialog')]
print('PASS: exact pinned native UpdateLink preserves URL/order and saves title; reconstructed store, invalid/missing targets, accessible Save/Cancel UI contracts. Not Android device/disk-flush test.')
