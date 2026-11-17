"""Execute exact transformed seed block with native preference/store doubles.
Not an Android runtime or actual PrefService persistence test.
"""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('home', ROOT / '.circleci/scripts/apply-sandium-home-shortcuts.py')
home = importlib.util.module_from_spec(spec); spec.loader.exec_module(home)

class HomeDefaults(unittest.TestCase):
    def test_pinned_transform_idempotence(self):
        src = (ROOT / '.circleci/tests/fixtures/home-rename/custom_links_manager_impl.cc').read_text()
        changed = home.manager(src)
        self.assertEqual(changed, home.manager(changed))
        self.assertEqual(changed.count('u"Google"'), 1)
        self.assertNotIn('CustomLinksScope::kDesktop &&\n      !prefs_', changed)

    def test_exact_seed_lifecycle(self):
        src = (ROOT / '.circleci/tests/fixtures/home-rename/custom_links_manager_impl.cc').read_text()
        changed = home.manager(src)
        block = changed[changed.index('  // Sandium defaults'):changed.index('  if (IsInitialized())')]
        code = r'''
#include <cassert>
#include <map>
#include <string>
#include <vector>
#include <algorithm>
namespace base { template<class T> struct AutoReset { T* p; T old; AutoReset(T* a,T b):p(a),old(*a){*p=b;} ~AutoReset(){*p=old;} }; }
struct GURL { std::string spec; explicit GURL(const char* x):spec(x){} };
struct Link { GURL url; std::u16string title; bool most; };
enum class CustomLinksScope { kDesktop, kMobile };
struct Options { CustomLinksScope scope; };
struct Prefs { std::map<std::string,bool> user; std::vector<Link> links;
 const bool* GetUserPrefValue(const char* key) { auto it=user.find(key); return it==user.end()?nullptr:&it->second; }
 void SetBoolean(const char* key,bool b){user[key]=b;} };
struct Store { const char* list_pref_name(){return "links";} };
struct Manager { Prefs* prefs_; const char* custom_links_initialized_pref_="init"; Store store_; std::vector<Link> current_links_; bool updating_preferences_=false;
 void StoreLinks(){prefs_->links=current_links_;prefs_->user["links"]=true;}
 Manager(Prefs& prefs,CustomLinksScope scope):prefs_(&prefs){Options options{scope};
''' + block + r'''
 if (prefs.user.count("init") && prefs.user["init"]) current_links_=prefs.links;
 }
};
int main(){
 Prefs fresh; Manager one(fresh,CustomLinksScope::kMobile);
 const std::u16string expected[]={u"Google",u"YouTube",u"Facebook",u"Instagram",u"X"};
 const std::string urls[]={"https://www.google.com/","https://www.youtube.com/","https://www.facebook.com/","https://www.instagram.com/","https://x.com/"};
 assert(one.current_links_.size()==5);
 for(int i=0;i<5;i++){assert(one.current_links_[i].title==expected[i]);assert(one.current_links_[i].url.spec==urls[i]);assert(!one.current_links_[i].most);}
 Manager reopen(fresh,CustomLinksScope::kMobile);assert(reopen.current_links_.size()==5);
 // Existing rename, deletion and reordering survive an upgrade/recreation.
 fresh.links.erase(fresh.links.begin()+1);fresh.links[0].title=u"My Google";std::reverse(fresh.links.begin(),fresh.links.end());
 Manager upgrade(fresh,CustomLinksScope::kMobile);assert(upgrade.current_links_.size()==4);assert(upgrade.current_links_[0].title==u"X");assert(upgrade.current_links_.back().title==u"My Google");
 // Intentionally cleared, uninitialized and partial legacy states never re-seed.
 fresh.links.clear();Manager empty(fresh,CustomLinksScope::kMobile);assert(empty.current_links_.empty());
 Prefs cleared;cleared.user["init"]=false;Manager c(cleared,CustomLinksScope::kMobile);assert(cleared.links.empty());assert(!cleared.user.count("links"));
 Prefs legacy;legacy.user["links"]=true;legacy.links.push_back({GURL("https://example.com/"),u"Saved",false});Manager l(legacy,CustomLinksScope::kMobile);assert(legacy.links.size()==1);assert(!legacy.user.count("init"));
 Prefs desktop;Manager d(desktop,CustomLinksScope::kDesktop);assert(desktop.user.empty());assert(desktop.links.empty());
}
'''
        if not shutil.which('g++'): self.skipTest('g++ unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cc').write_text(code)
            subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror',str(p/'test.cc'),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True)

if __name__ == '__main__': unittest.main()
