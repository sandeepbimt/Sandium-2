#include "brave/components/sandium_ubo_routing/routing.h"
#include <memory>
#include <utility>
#include "base/supports_user_data.h"
#include "brave/components/sandium_ubo_routing/owner_state.h"
#include "content/public/browser/browser_context.h"
#include "content/public/browser/browser_thread.h"
namespace sandium_ubo {
BASE_FEATURE(kSandiumUboExclusiveRouting, base::FEATURE_DISABLED_BY_DEFAULT);
namespace {
const char kOwnerKey[] = "sandium-ubo-session-owner";
class OwnerData : public base::SupportsUserData::Data {
 public:
  OwnerState state;
  bool startup_armed = false;
  bool runtime_unavailable = false;
  bool startup_aborted = false;
  bool native_fallback_complete = false;
};
OwnerState& Get(content::BrowserContext* context) {
  auto* data = static_cast<OwnerData*>(context->GetUserData(kOwnerKey));
  if (!data) {
    auto owned = std::make_unique<OwnerData>();
    data = owned.get();
    context->SetUserData(kOwnerKey, std::move(owned));
  }
  return data->state;
}
}  // namespace
bool AcknowledgeOwnerSettings(content::BrowserContext* context, uint64_t generation) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  return context && !context->IsOffTheRecord() && Get(context).AcknowledgeSettings(generation);
}
uint64_t SelectedOwnerGeneration(content::BrowserContext* context) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  return context && !context->IsOffTheRecord() ? Get(context).generation() : 0;
}
bool IsUboOwnerChosen(content::BrowserContext* context) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  return context && !context->IsOffTheRecord() && Get(context).ubo_selected();
}
bool IsNativeFallbackComplete(content::BrowserContext* context) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  if (!context) return false;
  Get(context);
  return static_cast<OwnerData*>(context->GetUserData(kOwnerKey))->native_fallback_complete;
}
void MarkNativeFallbackComplete(content::BrowserContext* context) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  Get(context);
  static_cast<OwnerData*>(context->GetUserData(kOwnerKey))->native_fallback_complete = true;
}
void ArmRuntimeStartup(content::BrowserContext* context) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  if (!context || context->IsOffTheRecord() ||
      !base::FeatureList::IsEnabled(kSandiumUboExclusiveRouting)) return;
  Get(context);
  static_cast<OwnerData*>(context->GetUserData(kOwnerKey))->startup_armed = true;
}
void MarkRuntimeUnavailable(content::BrowserContext* context) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  if (!context || context->IsOffTheRecord() || !Get(context).ubo_selected()) return;
  static_cast<OwnerData*>(context->GetUserData(kOwnerKey))->runtime_unavailable = true;
}
bool MustBlockAdRequest(content::BrowserContext* context) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  if (!context || context->IsOffTheRecord()) return false;
  Get(context);
  const auto* data = static_cast<OwnerData*>(context->GetUserData(kOwnerKey));
  return data->runtime_unavailable ||
      (data->startup_armed && !data->state.ubo_selected() && !data->native_fallback_complete);
}
bool IsRuntimeStartupAborted(content::BrowserContext* context) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  if (!context) return true;
  Get(context);
  return static_cast<OwnerData*>(context->GetUserData(kOwnerKey))->startup_aborted;
}
void AbortRuntimeStartup(content::BrowserContext* context) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  if (!context) return;
  Get(context);
  static_cast<OwnerData*>(context->GetUserData(kOwnerKey))->startup_aborted = true;
}
bool PrepareUboOwnerBeforeFirstRequest(content::BrowserContext* context,
                                      uint64_t generation) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  if (!context || context->IsOffTheRecord() || IsRuntimeStartupAborted(context) ||
      !base::FeatureList::IsEnabled(kSandiumUboExclusiveRouting)) return false;
  return Get(context).PrepareUbo(generation, true);
}
bool SealAndUseNativeAdEngine(content::BrowserContext* context) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  if (!context || context->IsOffTheRecord()) return true;
  const auto* data = static_cast<OwnerData*>(context->GetUserData(kOwnerKey));
  if (data && data->startup_armed && !data->native_fallback_complete &&
      !data->state.ubo_selected()) return false;
  return Get(context).SealAndUseNative();
}
void InvalidateOwnerGeneration(content::BrowserContext* context,
                               uint64_t generation) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  if (context && !context->IsOffTheRecord()) Get(context).Invalidate(generation);
}
bool OwnerRestartRequired(content::BrowserContext* context) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  if (!context || context->IsOffTheRecord()) return false;
  Get(context);
  const auto* data = static_cast<OwnerData*>(context->GetUserData(kOwnerKey));
  return data->runtime_unavailable || data->state.restart_required();
}
}  // namespace sandium_ubo
