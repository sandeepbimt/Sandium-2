#include "brave/browser/extensions/sandium_ubo_startup.h"
#include <memory>
#include "base/functional/bind.h"
#include "base/logging.h"
#include "base/scoped_observation.h"
#include "base/supports_user_data.h"
#include "base/memory/weak_ptr.h"
#include "base/time/time.h"
#include "base/timer/timer.h"
#include "brave/browser/brave_browser_features.h"
#include "brave/browser/extensions/api/sandium_ubo_api.h"
#include "brave/components/sandium_ubo/identity.h"
#include "brave/components/sandium_ubo_routing/routing.h"
#include "chrome/browser/extensions/component_loader.h"
#include "content/public/browser/browser_context.h"
#include "content/public/browser/navigation_handle.h"
#include "content/public/browser/navigation_throttle.h"
#include "content/public/browser/navigation_throttle_registry.h"
#include "content/public/browser/web_contents.h"
#include "extensions/browser/extension_registry.h"
#include "extensions/browser/extension_registry_observer.h"
#include "extensions/browser/extension_host_registry.h"
#include "extensions/browser/extension_host.h"
#include "extensions/common/extension.h"
#include "net/base/net_errors.h"

namespace sandium_ubo {
namespace {
const char kRuntimeGuardKey[] = "sandium-ubo-runtime-guard";
class RuntimeGuard : public base::SupportsUserData::Data,
                     public extensions::ExtensionRegistryObserver,
                     public extensions::ExtensionHostRegistry::Observer {
 public:
  explicit RuntimeGuard(content::BrowserContext* context) {
    registry_.Observe(extensions::ExtensionRegistry::Get(context));
    hosts_.Observe(extensions::ExtensionHostRegistry::Get(context));
  }
  void OnExtensionUnloaded(content::BrowserContext* context,
      const extensions::Extension* extension,
      extensions::UnloadedExtensionReason reason) override {
    if (extension->id() == kExtensionId) MarkRuntimeUnavailable(context);
  }
  void OnExtensionHostRenderProcessGone(content::BrowserContext* context,
      extensions::ExtensionHost* host) override { LostHost(context, host); }
  void OnExtensionHostDestroyed(content::BrowserContext* context,
      extensions::ExtensionHost* host) override { LostHost(context, host); }
  void OnShutdown(extensions::ExtensionRegistry*) override { registry_.Reset(); }
  void OnExtensionHostRegistryShutdown(extensions::ExtensionHostRegistry*) override {
    hosts_.Reset();
  }
 private:
  void LostHost(content::BrowserContext* context, extensions::ExtensionHost* host) {
    if (host->extension_id() == kExtensionId &&
        host->extension_host_type() == extensions::mojom::ViewType::kExtensionBackgroundPage) {
      MarkRuntimeUnavailable(context);
      LOG(ERROR) << "Sandium uBO background unavailable: site requests blocked";
    }
  }
  base::ScopedObservation<extensions::ExtensionRegistry,
      extensions::ExtensionRegistryObserver> registry_{this};
  base::ScopedObservation<extensions::ExtensionHostRegistry,
      extensions::ExtensionHostRegistry::Observer> hosts_{this};
};
class StartupNavigationThrottle : public content::NavigationThrottle {
 public:
  explicit StartupNavigationThrottle(content::NavigationThrottleRegistry& registry)
      : NavigationThrottle(registry) {}
  const char* GetNameForLogging() override { return "SandiumUboStartup"; }
  ThrottleCheckResult WillStartRequest() override {
    auto* context = navigation_handle()->GetWebContents()->GetBrowserContext();
    if (IsUboOwnerChosen(context) && MustBlockAdRequest(context))
      return ThrottleCheckResult(CANCEL, net::ERR_BLOCKED_BY_CLIENT);
    if (IsRuntimeStartupAborted(context))
      return IsNativeFallbackComplete(context) ? ThrottleCheckResult(PROCEED)
          : ThrottleCheckResult(CANCEL, net::ERR_BLOCKED_BY_CLIENT);
    if (TrySelect(context)) return PROCEED;
    deadline_ = base::TimeTicks::Now() + base::Seconds(12);
    timer_.Start(FROM_HERE, base::Milliseconds(50),
                 base::BindRepeating(&StartupNavigationThrottle::Poll,
                                     weak_factory_.GetWeakPtr()));
    return DEFER;
  }
 private:
  bool TrySelect(content::BrowserContext* context) {
    const auto eligibility = extensions::api::GetSandiumUboRuntimeEligibility(context);
    if (eligibility.generation <= 0 ||
        eligibility.acknowledged_generation != eligibility.generation ||
        !eligibility.user_rules_applied || !eligibility.policy_bridge_ready ||
        !eligibility.listeners_reported) return false;
    auto* registry = extensions::ExtensionRegistry::Get(context);
    if (!registry || !registry->enabled_extensions().GetByID(kExtensionId)) return false;
    bool background_live = false;
    for (auto* host : extensions::ExtensionHostRegistry::Get(context)->GetHostsForExtension(kExtensionId)) {
      if (host->extension_host_type() == extensions::mojom::ViewType::kExtensionBackgroundPage &&
          host->IsRendererLive()) background_live = true;
    }
    if (!background_live) return false;
    if (IsUboOwnerChosen(context))
      return AcknowledgeOwnerSettings(context, eligibility.generation);
    return PrepareUboOwnerBeforeFirstRequest(context, eligibility.generation);
  }
  void Poll() {
    auto* context = navigation_handle()->GetWebContents()->GetBrowserContext();
    if (IsUboOwnerChosen(context) && MustBlockAdRequest(context)) {
      timer_.Stop();
      CancelDeferredNavigation(ThrottleCheckResult(CANCEL, net::ERR_BLOCKED_BY_CLIENT));
      return;
    }
    if (IsRuntimeStartupAborted(context)) {
      timer_.Stop();
      if (IsNativeFallbackComplete(context)) Resume();
      else CancelDeferredNavigation(ThrottleCheckResult(CANCEL, net::ERR_BLOCKED_BY_CLIENT));
      return;
    }
    if (TrySelect(context)) { timer_.Stop(); Resume(); return; }
    if (base::TimeTicks::Now() < deadline_) return;
    if (IsUboOwnerChosen(context)) {
      timer_.Stop();
      LOG(ERROR) << "Sandium uBO settings refresh timed out; engine owner unchanged";
      CancelDeferredNavigation(ThrottleCheckResult(CANCEL, net::ERR_BLOCKED_BY_CLIENT));
      return;
    }
    timer_.Stop();
    // First prevent an asynchronous materializer from registering after fallback.
    AbortRuntimeStartup(context);
    auto* loader = extensions::ComponentLoader::Get(context);
    if (loader) loader->Remove(kExtensionId);
    auto* registry = extensions::ExtensionRegistry::Get(context);
    if ((loader && loader->Exists(kExtensionId)) ||
        (registry && registry->enabled_extensions().GetByID(kExtensionId))) {
      LOG(ERROR) << "Sandium uBO startup timeout: teardown incomplete; navigation cancelled";
      CancelDeferredNavigation(ThrottleCheckResult(CANCEL, net::ERR_BLOCKED_BY_CLIENT));
      return;
    }
    // Pinned WebRequestAPI removes unloaded extension listeners synchronously.
    LOG(ERROR) << "Sandium uBO startup timeout: native ad engine retained";
    MarkNativeFallbackComplete(context);
    SealAndUseNativeAdEngine(context);
    Resume();
  }
  base::TimeTicks deadline_;
  base::RepeatingTimer timer_;
  base::WeakPtrFactory<StartupNavigationThrottle> weak_factory_{this};
};
}  // namespace
void AddStartupNavigationThrottle(content::NavigationThrottleRegistry& registry) {
  auto& handle = registry.GetNavigationHandle();
  auto* context = handle.GetWebContents()->GetBrowserContext();
  if (!context || context->IsOffTheRecord() ||
      !handle.GetURL().SchemeIsHTTPOrHTTPS() ||
      !base::FeatureList::IsEnabled(kSandiumUboExclusiveRouting) ||
      !base::FeatureList::IsEnabled(features::kSandiumUboRuntime)) return;
  if (!context->GetUserData(kRuntimeGuardKey))
    context->SetUserData(kRuntimeGuardKey, std::make_unique<RuntimeGuard>(context));
  registry.AddThrottle(std::make_unique<StartupNavigationThrottle>(registry));
}
}  // namespace sandium_ubo
