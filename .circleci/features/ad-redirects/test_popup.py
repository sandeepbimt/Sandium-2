"""Host checks of the emitted Android popup guard with small Chromium API stubs."""
from pathlib import Path
import subprocess
import tempfile
import unittest

import popup


STUBS = r'''
#include <cassert>
#include <string>
#include <string_view>
#define BUILDFLAG(flag) 1

struct GURL {
  std::string host;
  std::string_view path_ = "/", query_ = "";
  bool web = true;
  bool blank = false;
  bool IsAboutBlank() const { return blank; }
  bool SchemeIsHTTPOrHTTPS() const { return web; }
  std::string_view path() const { return path_; }
  std::string_view query() const { return query_; }
};

namespace net {
class QueryIterator {
 public:
  explicit QueryIterator(const GURL& url) : remaining_(url.query()) { Advance(); }
  bool IsAtEnd() const { return field_.data() == nullptr; }
  void Advance() {
    if (remaining_.empty()) { field_ = {}; return; }
    size_t end = remaining_.find('&');
    field_ = remaining_.substr(0, end);
    remaining_ = end == remaining_.npos ? std::string_view() : remaining_.substr(end + 1);
  }
  std::string_view GetKey() const { return field_.substr(0, field_.find('=')); }
  std::string_view GetValue() const {
    size_t equal = field_.find('=');
    return equal == field_.npos ? std::string_view() : field_.substr(equal + 1);
  }
 private:
  std::string_view remaining_, field_;
};
namespace registry_controlled_domains {
enum Filter { INCLUDE_PRIVATE_REGISTRIES };
bool SameDomainOrHost(const GURL& a, const GURL& b, Filter) { return a.host == b.host; }
}
}
enum class WindowOpenDisposition {
  CURRENT_TAB, NEW_FOREGROUND_TAB, NEW_BACKGROUND_TAB, NEW_WINDOW, NEW_POPUP,
  NEW_PICTURE_IN_PICTURE
};
enum class ContentSettingsType { POPUPS };
enum ContentSetting { CONTENT_SETTING_BLOCK, CONTENT_SETTING_ALLOW };
struct PrefService { bool block = true; };
struct Map {
  bool shields = true;
  ContentSetting popups = CONTENT_SETTING_BLOCK;
  auto GetContentSetting(const GURL& first, const GURL& second, ContentSettingsType) const {
    assert(first.host == "publisher.test" && first.host == second.host);
    return popups;
  }
};
struct Profile {
  PrefService prefs;
  Map settings;
  bool has_map = true;
  static Profile* FromBrowserContext(Profile* value) { return value; }
  PrefService* GetPrefs() { return &prefs; }
};
struct HostContentSettingsMapFactory {
  static Map* GetForProfile(Profile* p) { return p->has_map ? &p->settings : nullptr; }
};
namespace content {
struct RenderFrameHost {
  RenderFrameHost* parent = nullptr;
  RenderFrameHost* GetParent() { return parent; }
  struct Origin { GURL url; GURL GetURL() const { return url; } };
  Origin origin{GURL{""}};
  Origin GetLastCommittedOrigin() const { return origin; }
  Profile profile;
  int reads = 0;
  Profile* GetBrowserContext() { ++reads; return &profile; }
};
}
namespace brave_shields {
bool IsBraveShieldsEnabled(Map* map, const GURL& top) {
  assert(top.host == "publisher.test");
  return map->shields;
}
bool ShouldBlockAdRedirect(const PrefService& prefs, const GURL& top) {
  assert(top.host == "publisher.test");
  return prefs.block;
}
}
'''

HARNESS = r'''
int main() {
  content::RenderFrameHost opener;
  GURL top{"publisher.test"};
  GURL target{"unrelated.test", "/opaque/slot/",
              "scontext_r=ctx&nrb=1&param_3=nortb_fallback&md=opaque"};
  using D = WindowOpenDisposition;
  auto block = [&](D where) { return ShouldBlockSandiumAdTab(&opener, top, top, target, where, false); };
  for (D where : {D::NEW_FOREGROUND_TAB, D::NEW_BACKGROUND_TAB, D::NEW_WINDOW, D::NEW_POPUP})
    assert(block(where));
  int reads = opener.reads;
  assert(!block(D::CURRENT_TAB) && !block(D::NEW_PICTURE_IN_PICTURE));
  target.host = top.host;
  assert(!block(D::NEW_FOREGROUND_TAB));
  target.host = "unrelated.test";
  target.web = false;
  assert(!block(D::NEW_FOREGROUND_TAB));
  target.web = true;
  top.web = false;
  assert(!block(D::NEW_FOREGROUND_TAB));
  top.web = true;
  assert(reads == opener.reads);

  opener.profile.prefs.block = false;
  assert(!block(D::NEW_FOREGROUND_TAB));
  opener.profile.prefs.block = true;
  opener.profile.settings.popups = CONTENT_SETTING_ALLOW;
  assert(!block(D::NEW_FOREGROUND_TAB));
  opener.profile.settings.popups = CONTENT_SETTING_BLOCK;
  opener.profile.settings.shields = false;
  assert(!block(D::NEW_FOREGROUND_TAB));
  opener.profile.settings.shields = true;
  opener.profile.has_map = false;
  assert(!block(D::NEW_FOREGROUND_TAB));
  opener.profile.has_map = true;

  // Normal logins, players and playlists miss without reading profile settings.
  reads = opener.reads;
  for (auto query : {"", "client_id=app&redirect_uri=https%3A%2F%2Fpublisher.test",
                     "token=stream", "scontext_r=&nrb=1&param_3=nortb_fallback&md=x",
                     "scontext_r=x&nrb=0&param_3=nortb_fallback&md=x",
                     "scontext_r=x&nrb=1&param_3=normal&md=x",
                     "scontext_r=x&nrb=1&param_3=nortb_fallback&md=",
                     "scontext_r=x&nrb=1&md=param_3%3Dnortb_fallback",
                     "next=/?scontext_r=x&nrb=1&param_3=nortb_fallback&md=x"}) {
    target.query_ = query;
    assert(!block(D::NEW_FOREGROUND_TAB));
  }
  target.query_ = "scontext_r=x&nrb=1&param_3=nortb_fallback&md=x";
  target.path_ = "/media/index.m3u8";
  assert(!block(D::NEW_FOREGROUND_TAB));
  assert(reads == opener.reads);
  target.path_ = "/";
  target.query_ = "scontext_r=x&other=y&md=x&param_3=nortb_fallback&nrb=1";
  assert(block(D::NEW_FOREGROUND_TAB));

  // Server switch is an iframe navigation. Only the subsequent auxiliary tab
  // reaches this hook. Exercise two unrelated publishers' player/ad URL shapes.
  content::RenderFrameHost parent;
  opener.parent = &parent;
  GURL source{"embed.example"};
  auto embedded = [&](bool scripted, D disposition = D::NEW_FOREGROUND_TAB) {
    return ShouldBlockSandiumAdTab(&opener, source, top, target, disposition, scripted);
  };
  for (auto host : {"unrelated.test", "rotating-new-host.example"}) {
    target = GURL{host, "/watch/service", ""};
    assert(embedded(true) && !embedded(false));
    assert(!embedded(true, D::CURRENT_TAB) && !embedded(true, D::NEW_PICTURE_IN_PICTURE));
    for (auto where : {D::NEW_BACKGROUND_TAB, D::NEW_WINDOW, D::NEW_POPUP})
      assert(embedded(true, where));
  }

  // Recognize the first exchange hop before a real <video> has been mounted.
  target = GURL{"unrelated.test", "/10/abcde0123456789f0123456789abcdef", "psid=41242"};
  assert(embedded(false));
  target.query_ = "another=v&psid=3";
  assert(embedded(false));
  for (auto query : {"psid=", "psid=hello", "pid=4", "q=psid%3D4"}) {
    target.query_ = query;
    assert(!embedded(false));
  }
  target.query_ = "psid=41242";
  for (auto path : {"/", "/10/abc", "/10/abcde0123456789f0123456789abcdeg",
                    "/some/abcde0123456789f0123456789abcdef", "/media/index.m3u8"}) {
    target.path_ = path;
    assert(!embedded(false));
  }

  target = GURL{"", "blank", "", false, true};
  assert(embedded(true) && !embedded(false));
  target.blank = false;
  assert(!embedded(true));
  target = source;
  assert(!embedded(true));
  target = top;
  assert(!embedded(true));
  target = GURL{"unrelated.test"};
  source = top;
  assert(!embedded(true));
  source = GURL{"", "blank", "", false, true};
  opener.origin = {GURL{"embedded.test"}};
  assert(embedded(true));
  opener.origin = {top};
  assert(!embedded(true));
  source = GURL{"embed.example"};
  opener.parent = nullptr;
  assert(!embedded(true));
  opener.parent = &parent;
  opener.profile.prefs.block = false;
  assert(!embedded(true));
  opener.profile.prefs.block = true;
  opener.profile.settings.popups = CONTENT_SETTING_ALLOW;
  assert(!embedded(true));
  opener.profile.settings.popups = CONTENT_SETTING_BLOCK;
  opener.profile.settings.shields = false;
  assert(!embedded(true));

}
'''


class PopupTest(unittest.TestCase):
    def test_window_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "guard.cc"
            binary = Path(directory) / "guard"
            source.write_text(STUBS + popup.HELPERS + HARNESS)
            subprocess.run(["c++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                            str(source), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_existing_denials_replay_and_drift(self):
        fixture = (popup.INCLUDE_ANCHOR + "#endif\n" + popup.METHOD
                   + "    /* pinned signature */) {\n"
                   + "  bool can_create_window = ChromeContentBrowserClient::CanCreateWindow("
                   + "/* ... */);\n" + popup.BEFORE_RETURN + "\n}\n")
        result = popup.transform(fixture)
        self.assertEqual(result, popup.transform(result))
        self.assertLess(result.index("bool can_create_window ="), result.index(popup.GUARD))
        self.assertLess(result.index(popup.GUARD), result.index(popup.BEFORE_RETURN))
        self.assertIn("if (can_create_window &&", popup.GUARD)
        for broken in (result.replace(popup.GUARD, ""), fixture.replace(popup.METHOD, ""),
                       fixture + popup.BEFORE_RETURN):
            with self.assertRaises(ValueError):
                popup.transform(broken)


if __name__ == "__main__":
    unittest.main()
