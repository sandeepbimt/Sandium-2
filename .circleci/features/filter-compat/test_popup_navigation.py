"""Run the emitted popup navigation throttle and exercise its source-overlay contract."""
from pathlib import Path
import subprocess
import tempfile
import unittest

import popup_navigation as overlay


class PopupNavigation(unittest.TestCase):
    def test_anchors_replay_and_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, changes in overlay.edits().items():
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("".join(anchor for anchor, _ in changes))
            changes = overlay.planned(root)
            self.assertEqual(len(changes), len(overlay.edits()))
            for path, source in changes.items():
                path.write_text(source)
            self.assertFalse(overlay.planned(root))
            p = root/overlay.CREATE
            p.write_text(p.read_text().replace("kFromUntrustedEvent", "kFromTrustedEvent"))
            with self.assertRaises(ValueError):
                overlay.planned(root)

    def test_async_decision_and_candidate_lifetime(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp)/"popup"
            subprocess.run(["c++", "-std=c++20", "-Wall", "-Wextra", "-Werror",
                            "-I", str(overlay.HERE), "-x", "c++", "-", "-o", str(exe)],
                           input=STUBS + '#include "popup_navigation.cc.inc"\n' + TESTS,
                           text=True, check=True)
            subprocess.run([str(exe)], check=True)


STUBS = r"""
#include <cassert>
#include <functional>
#include <memory>
#include <string>
#include <utility>
#define BUILDFLAG(flag) 1

struct GURL {
  std::string url;
  bool operator==(const GURL&) const = default;
  bool SchemeIsHTTPOrHTTPS() const { return url.starts_with("https://") || url.starts_with("http://"); }
  bool IsAboutBlank() const { return url == "about:blank"; }
};
namespace base {
struct SupportsUserData {
  struct Data { virtual ~Data() = default; };
  std::unique_ptr<Data> data;
  void SetUserData(const void*, std::unique_ptr<Data> value) { data = std::move(value); }
  const Data* GetUserData(const void*) { return data.get(); }
  void RemoveUserData(const void*) { data.reset(); }
};
inline int now = 0;
struct TimeTicks { int t; static TimeTicks Now() { return {now}; } };
int operator-(TimeTicks a, TimeTicks b) { return a.t-b.t; }
int Seconds(int s) { return s; }
template<class T> struct WeakPtr { T* instance; std::weak_ptr<int> live; };
template<class T> struct WeakPtrFactory {
  explicit WeakPtrFactory(T* t) : instance(t) {}
  WeakPtr<T> GetWeakPtr() { return {instance, live}; }
  T* instance;
  std::shared_ptr<int> live = std::make_shared<int>();
};
template<class T> auto BindOnce(void (T::*fn)(bool), WeakPtr<T> weak) {
  return [=](bool r) { if (!weak.live.expired()) (weak.instance->*fn)(r); };
}
template<class F> auto BindOnce(F f, GURL target, GURL source) {
  return [=](auto* engine) { return f(target, source, engine); };
}
}
enum class ContentSettingsType { POPUPS };
constexpr int CONTENT_SETTING_ALLOW = 1;
const GURL publisher{"https://news.test/page"}, player{"https://player.test/embed"},
           first{"https://example.test/first"}, ad{"https://ad.test/hop"},
           blank{"about:blank"};
struct Settings {
  bool publisher_on = true, destination_on = true, allow_popups = false;
  int GetContentSetting(const GURL& a, const GURL& b, ContentSettingsType) {
    assert(a == publisher && a == b); return allow_popups;
  }
};
struct Profile {
  Settings settings;
  bool enabled = true;
  static Profile* FromBrowserContext(Profile* p) { return p; }
  bool* GetPrefs() { return &enabled; }
};
struct HostContentSettingsMapFactory {
  static Settings* GetForProfile(Profile* p) { return &p->settings; }
};
namespace brave_shields {
bool IsBraveShieldsEnabled(Settings* s, const GURL& u) {
  return u == publisher ? s->publisher_on : s->destination_on;
}
bool ShouldBlockAdRedirect(bool enabled, const GURL& p) { assert(p == publisher); return enabled; }
struct AdBlockEngineWrapper {
  std::string target, source;
  bool ShouldBlockSandiumPopup(GURL t, GURL s) {
    target=t.url; source=s.url; return t == ad;
  }
};
}
struct Service {
  int num = 0;
  brave_shields::AdBlockEngineWrapper engine;
  std::function<void()> finish;
  template<class T, class F, class C> void AsyncCallAndReplyWithResult(F f, C cb) {
    ++num; finish = [this,f,cb](){cb(f(&engine));};
  }
};
struct Process { Service* service=nullptr; Service* ad_block_service() { return service; } };
Process process;
auto* g_brave_browser_process = &process;
namespace content {
struct RenderFrameHost {
  GURL current = player, origin = player;
  RenderFrameHost* top = this;
  const GURL& GetLastCommittedURL() { return current; }
  struct Origin { GURL url; GURL GetURL() const { return url; } };
  Origin GetLastCommittedOrigin() { return {origin}; }
  RenderFrameHost* GetOutermostMainFrame() { return top; }
};
struct WebContents : base::SupportsUserData {
  Profile profile;
  Profile* GetBrowserContext() { return &profile; }
};
struct NavigationHandle {
  WebContents* contents;
  GURL url = first;
  bool primary=true, renderer=true, same=false;
  bool IsInPrimaryMainFrame() {return primary;}
  bool IsRendererInitiated() {return renderer;}
  bool IsSameDocument() {return same;}
  WebContents* GetWebContents() {return contents;}
  const GURL& GetURL() {return url;}
};
struct NavigationThrottle;
struct NavigationThrottleRegistry {
  NavigationHandle handle;
  std::unique_ptr<NavigationThrottle> throttle;
  NavigationHandle& GetNavigationHandle() { return handle; }
  void AddThrottle(std::unique_ptr<NavigationThrottle> t) { throttle = std::move(t); }
};
struct NavigationThrottle {
  enum ThrottleCheckResult { PROCEED, DEFER, CANCEL_AND_IGNORE };
  NavigationThrottleRegistry& registry;
  explicit NavigationThrottle(NavigationThrottleRegistry& r) : registry(r) {}
  virtual ~NavigationThrottle()=default;
  virtual ThrottleCheckResult WillStartRequest()=0;
  virtual ThrottleCheckResult WillRedirectRequest()=0;
  virtual const char* GetNameForLogging()=0;
  NavigationHandle* navigation_handle() {return &registry.handle;}
  int resumed=0, blocked=0;
  void Resume() {++resumed;}
  void CancelDeferredNavigation(ThrottleCheckResult a) {assert(a==CANCEL_AND_IGNORE); ++blocked;}
};
}
struct BraveContentBrowserClient {
  void OnSandiumScriptedPopupCreated(content::RenderFrameHost*, content::WebContents*);
};
"""

TESTS = r"""
struct Fixture {
  Service service;
  content::WebContents contents;
  content::RenderFrameHost top, frame;
  content::NavigationThrottleRegistry nav{{&contents}, nullptr};
  BraveContentBrowserClient client;
  Fixture() {
    base::now=0; process.service=&service;
    top.current=publisher; frame.top=&top;
  }
  void Mark() {client.OnSandiumScriptedPopupCreated(&frame,&contents);}
  void Attach() {SandiumPopupNavigationThrottle::MaybeCreateAndAdd(nav);}
};
using T=content::NavigationThrottle;
int main() {
  { Fixture f; f.Attach(); assert(!f.nav.throttle && f.service.num==0); }
  { Fixture f; f.Mark(); f.nav.handle.primary=false; f.Attach(); assert(!f.nav.throttle);
    f.nav.handle.primary=true; f.nav.handle.url=blank; f.Attach(); assert(!f.nav.throttle);
    f.nav.handle.url=first; f.Attach(); assert(f.nav.throttle);
    f.frame.current=publisher;  // opener frame can change before matching.
    assert(f.nav.throttle->WillStartRequest()==T::DEFER); f.service.finish();
    assert(f.service.engine.target==first.url && f.service.engine.source==player.url);
    assert(f.nav.throttle->resumed==1);
    f.nav.handle.url=ad;
    assert(f.nav.throttle->WillRedirectRequest()==T::DEFER); f.service.finish();
    assert(f.nav.throttle->blocked==1 && f.service.num==2);
    f.nav.throttle.reset(); f.Attach(); assert(!f.nav.throttle); }
  for (int i=0; i<4; ++i) {
    Fixture f; f.Mark();
    if(i==0) f.nav.handle.renderer=false;
    if(i==1) base::now=11;
    if(i==2) f.nav.handle.same=true;
    if(i==3) f.nav.handle.url={"chrome://settings"};
    f.Attach(); assert(!f.nav.throttle && !f.contents.data); }
  for (int i=0; i<5; ++i) {
    Fixture f; f.Mark(); f.Attach(); assert(f.nav.throttle);
    if(i==0) f.contents.profile.enabled=false;
    if(i==1) f.contents.profile.settings.allow_popups=true;
    if(i==2) f.contents.profile.settings.publisher_on=false;
    if(i==3) f.contents.profile.settings.destination_on=false;
    if(i==4) process.service=nullptr;
    assert(f.nav.throttle->WillStartRequest()==T::PROCEED && f.service.num==0); }
  { Fixture f; f.Mark(); f.Attach(); f.nav.handle.url=ad;
    assert(f.nav.throttle->WillStartRequest()==T::DEFER);
    f.contents.profile.enabled=false; f.service.finish();
    assert(f.nav.throttle->resumed==1 && !f.nav.throttle->blocked); }
  { Fixture f; f.frame.current=blank; f.Mark(); f.Attach(); assert(f.nav.throttle);
    f.nav.throttle->WillStartRequest(); f.nav.throttle.reset(); f.service.finish();
    assert(f.service.engine.source==player.url); }
}
"""

if __name__ == "__main__":
    unittest.main()
