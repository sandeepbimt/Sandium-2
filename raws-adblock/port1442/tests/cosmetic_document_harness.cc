// SPDX-License-Identifier: MPL-2.0
// Host test doubles exercise the production observer, not Chromium's WeakDocumentPtr.
#include <cassert>
#include <functional>
#include <string>
#include <utility>
#define BUILDFLAG(flag) 1
#define WEB_CONTENTS_USER_DATA_KEY_DECL()
#define WEB_CONTENTS_USER_DATA_KEY_IMPL(T)
struct GURL {
  std::string value;
  bool SchemeIsHTTPOrHTTPS() const { return value.starts_with("https://"); }
  bool operator==(const GURL&) const = default;
};
namespace chrome::mojom {
struct ChromeRenderFrame {
  int applied = 0;
  void ApplyRawSHideStyles(const GURL&, const std::string&) { ++applied; }
};
}
namespace mojo {
template<class T> struct AssociatedRemote {
  T* target;
  T* operator->() { return target; }
};
}
namespace content {
struct WebContents {};
struct RenderFrameHost;
struct WeakDocumentPtr {
  RenderFrameHost* frame;
  int generation;
  RenderFrameHost* AsRenderFrameHostIfValid() const;
};
struct RenderFrameHost {
  bool active = true, live = true;
  int generation = 1;
  GURL url{"https://publisher.test/"};
  chrome::mojom::ChromeRenderFrame receiver;
  bool IsActive() const { return active; }
  bool IsRenderFrameLive() const { return live; }
  GURL GetLastCommittedURL() const { return url; }
  struct Origin { bool opaque() const { return false; } };
  Origin GetLastCommittedOrigin() const { return {}; }
  WeakDocumentPtr GetWeakDocumentPtr() { return {this, generation}; }
  RenderFrameHost* GetRemoteAssociatedInterfaces() { return this; }
  void GetInterface(mojo::AssociatedRemote<chrome::mojom::ChromeRenderFrame>* remote) {
    remote->target = &receiver;
  }
};
RenderFrameHost* WeakDocumentPtr::AsRenderFrameHostIfValid() const {
  return frame->generation == generation ? frame : nullptr;
}
struct NavigationHandle {
  RenderFrameHost& frame;
  bool HasCommitted() const { return true; }
  bool IsErrorPage() const { return false; }
  bool IsSameDocument() const { return false; }
  GURL GetURL() const { return frame.url; }
  RenderFrameHost* GetRenderFrameHost() { return &frame; }
};
struct WebContentsObserver {
  explicit WebContentsObserver(WebContents*) {}
  virtual ~WebContentsObserver() = default;
  virtual void DidFinishNavigation(NavigationHandle*) {}
};
template<class T> struct WebContentsUserData {
  explicit WebContentsUserData(WebContents&) {}
  static T CreateForTest(WebContents* contents) { return T(contents); }
};
}
namespace base {
template<class F, class Document>
auto BindOnce(F fn, Document document, GURL url) {
  return [=](std::string css) { fn(document, url, std::move(css)); };
}
}
namespace sandium::adblock_native {
std::function<void(std::string)> pending;
void QueryHideStyles(GURL, std::function<void(std::string)> cb) { pending = std::move(cb); }
}
#include "../cosmetic.cc.inc"
int main() {
  content::WebContents contents;
  content::RenderFrameHost frame;
  content::NavigationHandle handle{frame};
  auto observer = RawSCosmeticObserver::CreateForTest(&contents);
  auto dispatch = [&](auto invalidate) {
    observer.DidFinishNavigation(&handle);
    auto reply = std::exchange(sandium::adblock_native::pending, {});
    assert(reply);
    invalidate();
    reply(".ad { display:none !important; }");
  };
  dispatch([&] { ++frame.generation; });
  assert(frame.receiver.applied == 0);  // same URL/RFH, different document
  dispatch([&] { frame.active = false; });
  assert(frame.receiver.applied == 0);
  frame.active = true;
  dispatch([&] { frame.live = false; });
  assert(frame.receiver.applied == 0);
  frame.live = true;
  dispatch([] {});
  assert(frame.receiver.applied == 1);
}
