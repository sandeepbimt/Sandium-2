"""Focused active-overlay, native preference policy and privacy regression."""
import hashlib
import json
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import home_favicon as change

ROOT = pathlib.Path(__file__).resolve().parents[1]
IMAGES = ROOT / 'raws-adblock/production-postimages'
FIXTURES = pathlib.Path(__file__).with_name('fixtures') / 'home-favicon'


class HomeFaviconTest(unittest.TestCase):
    def test_exact_sources_reseal(self):
        files = json.loads((ROOT / 'raws-adblock/production-restore-recipe.json').read_text())['files']
        actual = {}
        for path, sha in (change.TRACKED | change.OWNERS).items():
            source = ((FIXTURES / pathlib.Path(path).name) if path in change.TRACKED else (IMAGES / sha))
            before = source.read_bytes()
            after = change.transform(path, before)
            digest = hashlib.sha256(after).hexdigest()
            self.assertEqual(digest, files[path]['after_sha256'])
            self.assertEqual(after, (IMAGES / digest).read_bytes())
            if path in change.TRACKED:
                self.assertEqual(sha, files[path]['before_sha256'])
            with self.assertRaises(ValueError):
                change.transform(path, before + b'\n')
            actual[path] = after.decode()
        store = actual[change.STORE]
        self.assertIn('RegisterDictionaryPref(kRawSManualFavicons);', store)
        self.assertNotIn('RegisterDictionaryPref(kRawSManualFavicons,', store)
        place = store.index('void CustomLinksStore::StoreLinks')
        self.assertLess(store.index('ReconcileRawSFavicons', place), store.index('prefs_->SetList', place))
        self.assertIn('prefs_->ClearPref(kRawSManualFavicons);', store)
        tile = actual[change.RENDERER]
        self.assertEqual(tile.count('mImageFetcher.makeLargeIconRequest('), 1)
        self.assertIn('tile.getSource() == TileSource.CUSTOM_LINKS', tile)
        self.assertIn('profile == mProfile && profile.isNativeInitialized()', tile)
        self.assertLess(tile.index('if (icon == null)'), tile.index('encodeRawSManualFavicon(icon)'))
        self.assertIn('setTileIconFromColor(tile, fallbackColor, isFallbackColorDefault);', tile)
        bridge = actual[change.BRIDGE_CC]
        self.assertEqual(bridge.count('IsRawSManualShortcutProfile(profile)'), 4)
        self.assertIn('return profile && !profile->IsOffTheRecord()', bridge)

    def test_executed_native_policy_keeps_only_eligible_manual_link_icons(self):
        compiler = shutil.which('g++') or shutil.which('clang++')
        if not compiler:
            self.skipTest('No host C++ compiler')
        preamble = r'''
#include <cstddef>
#include <cassert>
#include <string>
#include <map>
#include <vector>
#include <optional>
#include <utility>
using std::size_t;
namespace base {
struct DictValue {
  std::map<std::string,std::string> strings;
  std::map<std::string,DictValue> dicts;
  std::optional<bool> automatic;
  bool empty() const { return size()==0; }
  size_t size() const { return strings.size()+dicts.size(); }
  const std::string* FindString(const std::string& k) const {
    auto i=strings.find(k); return i==strings.end()?nullptr:&i->second;
  }
  const DictValue* FindDict(const std::string& k) const {
    auto i=dicts.find(k); return i==dicts.end()?nullptr:&i->second;
  }
  std::optional<bool> FindBool(const std::string&) const { return automatic; }
  DictValue* EnsureDict(const std::string& k) { return &dicts[k]; }
  void Set(const std::string& k, const std::string& v) { strings[k]=v; }
  void Set(const std::string& k, DictValue v) { dicts[k]=std::move(v); }
};
struct UnguessableToken {
  static inline unsigned long counter=0;
  static UnguessableToken Create() { return {}; }
  std::string ToString() const { return std::to_string(++counter); }
};
}
class GURL {
  std::string s_;
 public:
  GURL(const std::string& s):s_(s) {}
  bool is_valid() const {return !s_.empty();}
  bool SchemeIsHTTPOrHTTPS() const {return s_.starts_with("https://") || s_.starts_with("http://");}
  bool has_username() const {return s_.find('@')!=std::string::npos;}
  bool has_password() const {return false;}
  const std::string& spec() const {return s_;}
};
namespace prefs { constexpr char kCustomLinksListMobile[]="mobile"; }
constexpr char kDictionaryKeyUrl[]="url";
constexpr char kDictionaryKeyIsMostVisited[]="isMostVisited";
struct Value {
  base::DictValue row;
  const base::DictValue* GetIfDict() const {return &row;}
};
struct PrefService {
  std::vector<Value> links;
  base::DictValue store;
  const std::vector<Value>& GetList(const std::string&) const { return links; }
  const base::DictValue& GetDict(const std::string&) const { return store; }
  void SetDict(const std::string&, base::DictValue d) { store=std::move(d); }
};
struct ScopedDictPrefUpdate {
  PrefService* p;
  ScopedDictPrefUpdate(PrefService* p,const std::string&):p(p){}
  base::DictValue* operator->() {return &p->store;}
};
struct CustomLinksManager { struct Link {GURL url; bool is_most_visited;}; };
struct CustomLinksStore {''' + change.STORE_DECL + '};\n'
        tests = r'''
void SaveLink(PrefService& p,const GURL& u,bool hidden) {
  Value v;
  v.row.Set(kDictionaryKeyUrl,u.spec());
  v.row.automatic=hidden;
  p.links.push_back(std::move(v));
}
int main() {
  using S=CustomLinksStore;
  PrefService regular, separate;
  const GURL a("https://example.test/path"), b("https://hidden.test/");
  const GURL alien("https://user@hidden.test"), other("file:///secret");
  SaveLink(regular,a,false);
  SaveLink(regular,b,true);
  SaveLink(regular,alien,false);
  SaveLink(regular,other,false);
  const auto ticket=S::BeginRawSFaviconRead(&regular,a);
  assert(!ticket.empty());
  assert(S::BeginRawSFaviconRead(&regular,b).empty());
  assert(S::BeginRawSFaviconRead(&regular,alien).empty());
  assert(S::BeginRawSFaviconRead(&regular,other).empty());
  assert(S::BeginRawSFaviconRead(&separate,a).empty());
  S::WriteRawSFavicon(&regular,b,ticket,"blocked");
  S::WriteRawSFavicon(&separate,a,ticket,"blocked");
  S::WriteRawSFavicon(&regular,a,ticket,std::string(65537,'x'));
  assert(S::ReadRawSFavicon(&regular,a,ticket).empty());
  S::WriteRawSFavicon(&regular,a,ticket,"bitmap");
  assert(S::ReadRawSFavicon(&regular,a,ticket)=="bitmap");
  assert(S::ReadRawSFavicon(&separate,a,ticket).empty());
  // Restart/profile reload: preferences are reopened, not the favicon database.
  PrefService reopened=regular;
  ReconcileRawSFavicons(&reopened,{{a,false}});
  const auto new_ticket=S::BeginRawSFaviconRead(&reopened,a);
  assert(new_ticket!=ticket);
  assert(S::ReadRawSFavicon(&reopened,a,new_ticket)=="bitmap");
  // Removing the link drops its icon and invalidates callbacks if the same
  // address is later added again or its URL edited back.
  ReconcileRawSFavicons(&reopened,{});
  reopened.links.clear();
  assert(S::BeginRawSFaviconRead(&reopened,a).empty());
  SaveLink(reopened,a,false);
  S::WriteRawSFavicon(&reopened,a,new_ticket,"stale");
  const auto readd=S::BeginRawSFaviconRead(&reopened,a);
  assert(S::ReadRawSFavicon(&reopened,a,readd).empty());
  // Bound the number of icons even if unusual prefs already contain more links.
  for(int i=0;i<40;++i){
    const GURL u("https://test"+std::to_string(i)+".test");
    SaveLink(reopened,u,false);
    S::WriteRawSFavicon(&reopened,u,readd,"new");
  }
  assert(reopened.store.FindDict(kRawSFaviconImages)->size()==32);
}
'''
        with tempfile.TemporaryDirectory() as temp:
            source = pathlib.Path(temp) / 'policy.cc'
            output = pathlib.Path(temp) / 'policy'
            source.write_text(preamble + change.STORE_POLICY + change.STORE_API + tests)
            subprocess.run([compiler, '-std=c++20', '-Wall', '-Werror', str(source), '-o',
                            str(output)], check=True)
            subprocess.run([str(output)], check=True)


if __name__ == '__main__':
    unittest.main()
