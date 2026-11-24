// Host doubles for the actual extracted browser lifecycle methods, not a
// substitute for building or running the native Chromium target.
#include <cassert>
#include <cstdint>
#include <deque>
#include <functional>
#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <vector>

using GURL = std::string;

template<class... Args>
class Once {
 public:
  Once() = default;
  template<class F>
  Once(F f) : impl_(std::make_unique<Impl<F>>(std::move(f))) {}
  explicit operator bool() const { return !!impl_; }
  void operator()(Args... args) && {
    auto impl = std::move(impl_);
    impl->Run(std::forward<Args>(args)...);
  }
 private:
  struct Base {
    virtual ~Base() = default;
    virtual void Run(Args...) = 0;
  };
  template<class F>
  struct Impl final : Base {
    explicit Impl(F f) : f(std::move(f)) {}
    void Run(Args... args) override {
      std::move(f)(std::forward<Args>(args)...);
    }
    F f;
  };
  std::unique_ptr<Base> impl_;
};

namespace base {
using UnguessableToken = unsigned;
int now;
inline int Milliseconds(int ms) { return ms; }
struct TimeTicks {
  int ms;
  static TimeTicks Now() { return {now}; }
  friend int operator-(TimeTicks a, TimeTicks b) { return a.ms - b.ms; }
};
template<class... T>
auto BindOnce(T&&... args) {
  return std::bind_front(std::forward<T>(args)...);
}
struct SequencedTaskRunner {
  struct Task { int at; Once<> run; };
  std::deque<Task> tasks;
  static SequencedTaskRunner* GetCurrentDefault() {
    static SequencedTaskRunner runner;
    return &runner;
  }
  void PostDelayedTask(int, Once<> run, int wait) {
    tasks.emplace_back(now + wait, std::move(run));
  }
  void Run(int until) {
    while (!tasks.empty() && tasks.front().at <= until) {
      auto task = std::move(tasks.front());
      tasks.pop_front();
      now = task.at;
      std::move(task.run)();
    }
    now = until;
  }
};
}
#define FROM_HERE 0

namespace chrome::mojom {
struct ChromeRenderFrame {
  unsigned count = 0;
  void RunRawSReviewedPassiveScriptlets(unsigned token, const GURL& expected,
                                       uint32_t programs) {
    assert(token == 1 && expected == "https://publisher.test" && programs == 3);
    ++count;
  }
};
}

namespace mojo {
template<class T>
struct AssociatedRemote {
  T* receiver;
  T* operator->() const { return receiver; }
};
}

namespace content {
enum class Visibility { VISIBLE, HIDDEN };
struct RenderFrameHost;
struct WebContents {
  Visibility visibility = Visibility::VISIBLE;
  RenderFrameHost* main = nullptr;
  Visibility GetVisibility() const { return visibility; }
  RenderFrameHost* GetPrimaryMainFrame() const { return main; }
  static WebContents* FromRenderFrameHost(RenderFrameHost* frame);
};
struct WeakDocumentPtr {
  RenderFrameHost* frame;
  explicit WeakDocumentPtr(RenderFrameHost* frame) : frame(frame) {}
  WeakDocumentPtr(WeakDocumentPtr&&) = default;
  RenderFrameHost* AsRenderFrameHostIfValid() const;
};
struct RenderFrameHost {
  GURL url = "https://publisher.test";
  unsigned token = 1;
  bool live = true;
  bool policy = true;
  WebContents* contents;
  chrome::mojom::ChromeRenderFrame receiver;
  WeakDocumentPtr GetWeakDocumentPtr() { return WeakDocumentPtr(this); }
  const GURL& GetLastCommittedURL() const { return url; }
  std::optional<unsigned> GetEmbeddingToken() const { return token; }
  RenderFrameHost* GetRemoteAssociatedInterfaces() { return this; }
  void GetInterface(mojo::AssociatedRemote<chrome::mojom::ChromeRenderFrame>* out) {
    out->receiver = &receiver;
  }
};
inline RenderFrameHost* WeakDocumentPtr::AsRenderFrameHostIfValid() const {
  return frame->live ? frame : nullptr;
}
inline WebContents* WebContents::FromRenderFrameHost(RenderFrameHost* frame) {
  return frame->contents;
}
struct NavigationHandle {
  bool committed = true;
  bool primary = true;
  bool HasCommitted() const { return committed; }
  bool IsInPrimaryMainFrame() const { return primary; }
};
}

namespace sandium::adblock_native {
bool enabled = true;
int ready_at = 0;
std::vector<int> attempts;
Once<uint32_t> completion;
bool ReviewedPassiveScriptletsEnabled() { return enabled; }
bool TryQueryReviewedPassiveScriptlets(
    const GURL& expected, Once<uint32_t> callback) {
  assert(expected == "https://publisher.test");
  attempts.push_back(base::now);
  if (base::now < ready_at)
    return false;
  assert(!completion);
  completion = std::move(callback);
  return true;
}
void Deliver(uint32_t programs) {
  assert(completion);
  auto callback = std::exchange(completion, {});
  std::move(callback)(programs);
}
}
bool MayApplyReviewedPassiveScriptlets(content::RenderFrameHost& frame,
                                       const GURL& expected) {
  return frame.live && frame.url == expected && frame.policy;
}

struct RawSCosmeticObserver {
  content::WebContents* contents;
  content::WebContents* web_contents() const { return contents; }
  std::optional<content::WeakDocumentPtr> passive_scriptlet_document_;
  uint64_t passive_scriptlet_epoch_ = 0;
  struct WeakFactory {
    RawSCosmeticObserver* self;
    RawSCosmeticObserver* GetWeakPtr() const { return self; }
  } weak_factory_{this};
  explicit RawSCosmeticObserver(content::WebContents* contents)
      : contents(contents) {}
  void DOMContentLoaded(content::RenderFrameHost* frame);
  void DidFinishNavigation(content::NavigationHandle* handle);
  void QueryPassiveScriptlets(content::WeakDocumentPtr, GURL,
                              base::UnguessableToken, base::TimeTicks, uint64_t,
                              unsigned);
  void OnPassiveScriptletsResult(content::WeakDocumentPtr, GURL,
                                 base::UnguessableToken, base::TimeTicks,
                                 uint64_t, uint32_t);
  content::RenderFrameHost* ResolvePassiveScriptletFrame(
      const content::WeakDocumentPtr&, const GURL&, const base::UnguessableToken&,
      base::TimeTicks, uint64_t);
};

#include "methods.inc"

struct Test {
  content::WebContents contents;
  content::RenderFrameHost frame;
  RawSCosmeticObserver observer{&contents};

  explicit Test(int ready_at) {
    using namespace sandium::adblock_native;
    base::now = 0;
    enabled = true;
    sandium::adblock_native::ready_at = ready_at;
    attempts.clear();
    completion = {};
    base::SequencedTaskRunner::GetCurrentDefault()->tasks.clear();
    contents.main = &frame;
    frame.contents = &contents;
    observer.passive_scriptlet_document_.emplace(frame.GetWeakDocumentPtr());
  }
  void Load() { observer.DOMContentLoaded(&frame); }
  void Advance(int until) {
    base::SequencedTaskRunner::GetCurrentDefault()->Run(until);
  }
  void ChangeNavigation() {
    content::NavigationHandle handle;
    observer.DidFinishNavigation(&handle);
  }
};

int main() {
  using namespace sandium::adblock_native;
  {
    Test t(100);  // Worker is busy on DOMContentLoaded, ready by the third try.
    t.Load();
    t.Load();     // A duplicate DOMContentLoaded cannot dispatch a second query.
    t.Advance(120);
    assert((attempts == std::vector{0, 60, 120}));
    Deliver(3);
    t.Advance(500);
    assert(attempts.size() == 3);
    assert(t.frame.receiver.count == 1);
  }
  {
    Test t(300);  // Never start at or after the original deadline.
    t.Load();
    t.Advance(500);
    assert((attempts == std::vector{0, 60, 120, 180, 240}));
    assert(!completion);
  }
  {
    Test t(60);
    t.Load();
    t.frame.policy = false;
    t.Advance(500);
    assert(attempts.size() == 1 && !completion);
  }
  {
    Test t(60);
    t.Load();
    t.contents.visibility = content::Visibility::HIDDEN;
    t.Advance(60);
    t.contents.visibility = content::Visibility::VISIBLE;
    t.Advance(500);
    assert(attempts.size() == 1 && !completion);
  }
  {
    Test t(0);
    t.Load();
    t.ChangeNavigation();
    t.ChangeNavigation();  // Old document may still be exactly live at Back.
    Deliver(3);
    assert(t.frame.receiver.count == 0);
  }
  {
    Test t(0);
    t.Load();
    t.Advance(300);
    Deliver(3);
    assert(t.frame.receiver.count == 0);
  }
  {
    Test t(0);
    t.Load();
    Deliver(0);  // Generation veto/no rules are not admission failure.
    t.Advance(500);
    assert(attempts.size() == 1 && t.frame.receiver.count == 0);
  }
  {
    Test t(0);
    enabled = false;
    t.Load();
    assert(attempts.empty());
  }
  {
    Test t(0);
    t.Load();
    t.frame.token = 2;
    Deliver(3);
    assert(t.frame.receiver.count == 0);
  }
}
