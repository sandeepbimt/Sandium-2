// Sandium policy metadata on existing native endpoints, never token-based routing.
#ifndef CONTENT_PUBLIC_BROWSER_SANDIUM_DARK_POLICY_AUTHORITY_H_
#define CONTENT_PUBLIC_BROWSER_SANDIUM_DARK_POLICY_AUTHORITY_H_
#include <cstdint>
#include <optional>
#include "base/unguessable_token.h"
#include "content/common/content_export.h"
namespace content {
class WebContents;
class SiteInstance;
// UI-thread-only revision issuer shared by commit, activation and live preferences.
CONTENT_EXPORT uint64_t NextSandiumDarkPolicyRevision();
CONTENT_EXPORT uint64_t BeginSandiumDarkPolicyQuery(WebContents& contents);
CONTENT_EXPORT bool IsCurrentSandiumDarkPolicyQuery(WebContents& contents, uint64_t revision);
// Reject-only identity metadata for the committed active primary document.
// Never obtains speculative/pending-commit document identity or routes an IPC.
CONTENT_EXPORT std::optional<base::UnguessableToken>
GetSandiumPrimaryDocumentToken(WebContents& contents, const SiteInstance& site);
}  // namespace content
#endif
