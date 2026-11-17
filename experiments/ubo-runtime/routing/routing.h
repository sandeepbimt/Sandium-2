#ifndef BRAVE_COMPONENTS_SANDIUM_UBO_ROUTING_ROUTING_H_
#define BRAVE_COMPONENTS_SANDIUM_UBO_ROUTING_ROUTING_H_
#include <cstdint>
#include "base/feature_list.h"
namespace content { class BrowserContext; }
namespace sandium_ubo {
BASE_DECLARE_FEATURE(kSandiumUboExclusiveRouting);
// Native-only coordinator API. No extension JS or preference exposes activation.
// Only the startup coordinator calls selection after its exact native eligibility
// checks. This is not an extension-exposed activation method.
bool PrepareUboOwnerBeforeFirstRequest(content::BrowserContext*,
                                      uint64_t generation);
bool AcknowledgeOwnerSettings(content::BrowserContext*, uint64_t generation);
uint64_t SelectedOwnerGeneration(content::BrowserContext*);
bool IsUboOwnerChosen(content::BrowserContext*);
bool IsNativeFallbackComplete(content::BrowserContext*);
void MarkNativeFallbackComplete(content::BrowserContext*);
void ArmRuntimeStartup(content::BrowserContext*);
void MarkRuntimeUnavailable(content::BrowserContext*);
bool MustBlockAdRequest(content::BrowserContext*);
bool IsRuntimeStartupAborted(content::BrowserContext*);
void AbortRuntimeStartup(content::BrowserContext*);
// All calls UI-thread only, before scheduling any native worker work.
bool SealAndUseNativeAdEngine(content::BrowserContext*);
void InvalidateOwnerGeneration(content::BrowserContext*, uint64_t generation);
bool OwnerRestartRequired(content::BrowserContext*);
}  // namespace sandium_ubo
#endif
