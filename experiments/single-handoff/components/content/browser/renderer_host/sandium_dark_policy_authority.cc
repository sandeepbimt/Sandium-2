#include "content/public/browser/sandium_dark_policy_authority.h"
#include <limits>
#include <memory>
#include "base/supports_user_data.h"
#include "base/check.h"
#include "content/browser/renderer_host/render_frame_host_impl.h"
#include "content/public/browser/browser_thread.h"
#include "content/public/browser/web_contents.h"
namespace content {
namespace {
uint64_t g_sandium_dark_policy_revision = 0;
const char kQueryStateKey = 0;
class QueryState : public base::SupportsUserData::Data {
 public:
  uint64_t revision = 0;
};
}
uint64_t NextSandiumDarkPolicyRevision() {
  CHECK(BrowserThread::CurrentlyOn(BrowserThread::UI));
  CHECK(g_sandium_dark_policy_revision < std::numeric_limits<uint64_t>::max());
  return ++g_sandium_dark_policy_revision;
}
uint64_t BeginSandiumDarkPolicyQuery(WebContents& contents) {
  CHECK(BrowserThread::CurrentlyOn(BrowserThread::UI));
  auto* state = static_cast<QueryState*>(contents.GetUserData(&kQueryStateKey));
  if (!state) {
    auto owned = std::make_unique<QueryState>();
    state = owned.get();
    contents.SetUserData(&kQueryStateKey, std::move(owned));
  }
  state->revision = NextSandiumDarkPolicyRevision();
  return state->revision;
}
bool IsCurrentSandiumDarkPolicyQuery(WebContents& contents, uint64_t revision) {
  CHECK(BrowserThread::CurrentlyOn(BrowserThread::UI));
  auto* state = static_cast<QueryState*>(contents.GetUserData(&kQueryStateKey));
  return state && revision != 0 && revision == state->revision;
}
std::optional<base::UnguessableToken> GetSandiumPrimaryDocumentToken(
    WebContents& contents, const SiteInstance& site) {
  CHECK(BrowserThread::CurrentlyOn(BrowserThread::UI));
  auto* frame = contents.GetPrimaryMainFrame();
  if (!frame || !frame->IsActive() || !frame->IsRenderFrameLive() ||
      frame->GetSiteInstance() != &site) return std::nullopt;
  // This implementation owns the private RFH access; callers use only values.
  return static_cast<RenderFrameHostImpl*>(frame)->GetDocumentToken().value();
}
}  // namespace content
