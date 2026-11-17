// Copyright 2026 Sandium. SPDX-License-Identifier: MPL-2.0
#include "brave/browser/extensions/api/sandium_ubo_api.h"
#include <memory>
#include "brave/components/sandium_ubo_routing/routing.h"
#include "components/sessions/content/session_tab_helper.h"
#include "content/public/browser/render_process_host.h"
#include "content/public/browser/render_frame_host.h"
#include "content/public/browser/web_contents.h"
#include "extensions/browser/extension_api_frame_id_map.h"
#include "extensions/browser/api/extensions_api_client.h"
#include <limits>
#include "base/strings/string_number_conversions.h"
#include "base/strings/string_util.h"
#include "crypto/sha2.h"
#include "base/functional/bind.h"
#include "chrome/browser/browser_process.h"
#include "brave/components/brave_shields/core/common/pref_names.h"
#include "components/prefs/pref_change_registrar.h"
#include "components/prefs/pref_service.h"
#include "base/memory/raw_ptr.h"
#include "base/scoped_observation.h"
#include "chrome/browser/profiles/profile_observer.h"
#include "components/content_settings/core/browser/content_settings_observer.h"
#include "extensions/browser/event_router.h"
#include <utility>
#include "base/logging.h"
#include "base/supports_user_data.h"
#include "brave/components/sandium_ubo/identity.h"
#include "content/public/browser/browser_context.h"
#include "content/public/browser/browser_thread.h"
#include "extensions/browser/extension_function_registry.h"
#include "base/values.h"
#include "brave/components/brave_shields/core/browser/brave_shields_utils.h"
#include "chrome/browser/content_settings/host_content_settings_map_factory.h"
#include "chrome/browser/profiles/profile.h"
#include "extensions/common/extension.h"
#include "extensions/common/manifest.h"
#include "url/gurl.h"
#include "components/content_settings/core/browser/host_content_settings_map.h"
#include "components/content_settings/core/common/content_settings_pattern.h"

namespace extensions::api {
namespace {
// Fixed by the component manifest public key. Never accept caller supplied IDs.
constexpr char kRuntimeStateKey[] = "sandium-ubo-observation-state";
class RuntimeState : public base::SupportsUserData::Data,
                     public content_settings::Observer,
                     public ProfileObserver {
 public:
  explicit RuntimeState(Profile* profile) : profile_(profile) {
    if (g_browser_process && g_browser_process->local_state()) {
      prefs_.Init(g_browser_process->local_state());
      prefs_.Add(brave_shields::prefs::kAdBlockCustomFilters,
          base::BindRepeating(&RuntimeState::Invalidate, base::Unretained(this)));
    }
    profile_observation_.Observe(profile);
    settings_observation_.Observe(HostContentSettingsMapFactory::GetForProfile(profile));
  }
  void OnProfileWillBeDestroyed(Profile*) override {
    prefs_.RemoveAll();
    settings_observation_.Reset();
    profile_observation_.Reset();
    profile_ = nullptr;
    acknowledged_generation = 0;
    phase = SandiumUboRuntimePhase::kNotReported;
  }
  void OnContentSettingChanged(const ContentSettingsPattern&,
      const ContentSettingsPattern&, ContentSettingsTypeSet types) override {
    if (!types.Contains(ContentSettingsType::BRAVE_SHIELDS) &&
        !types.Contains(ContentSettingsType::BRAVE_ADS) &&
        !types.Contains(ContentSettingsType::BRAVE_COSMETIC_FILTERING)) return;
    Invalidate();
  }
  void Invalidate() {
    // Every change revokes observation readiness before notifying JS. Future
    // ownership must also revoke synchronously here, never await an event ACK.
    acknowledged_generation = 0;
    phase = SandiumUboRuntimePhase::kNotReported;
    if (generation == std::numeric_limits<int>::max()) return;
    ++generation;
    if (profile_) sandium_ubo::InvalidateOwnerGeneration(profile_, generation);
    if (!profile_) return;
    auto* router = EventRouter::Get(profile_);
    if (!router) return;
    base::ListValue args;
    args.Append(generation);
    router->DispatchEventToExtension(sandium_ubo::kExtensionId,
        std::make_unique<Event>(events::UNKNOWN,
            "sandiumUbo.onSettingsChanged", std::move(args), profile_));
  }
  int generation = 1;
  int acknowledged_generation = 0;
  SandiumUboRuntimePhase phase = SandiumUboRuntimePhase::kNotReported;
 private:
  raw_ptr<Profile> profile_;
  PrefChangeRegistrar prefs_;
  base::ScopedObservation<Profile, ProfileObserver> profile_observation_{this};
  base::ScopedObservation<HostContentSettingsMap, content_settings::Observer>
      settings_observation_{this};
};
RuntimeState* GetOrCreateState(content::BrowserContext* context) {
  auto* state = static_cast<RuntimeState*>(context->GetUserData(kRuntimeStateKey));
  if (!state) {
    auto owned = std::make_unique<RuntimeState>(Profile::FromBrowserContext(context));
    state = owned.get();
    context->SetUserData(kRuntimeStateKey, std::move(owned));
  }
  return state;
}
bool IsTrustedComponent(const Extension* extension) {
  return extension && extension->id() == sandium_ubo::kExtensionId &&
         Manifest::IsComponentLocation(extension->location()) &&
         extension->version().GetString() == sandium_ubo::kVersion;
}
}  // namespace

SandiumUboRuntimePhase GetSandiumUboRuntimePhase(content::BrowserContext* context) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  auto* state = static_cast<RuntimeState*>(context->GetUserData(kRuntimeStateKey));
  return state ? state->phase : SandiumUboRuntimePhase::kNotReported;
}
SandiumUboRuntimeEligibility GetSandiumUboRuntimeEligibility(content::BrowserContext* context) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  SandiumUboRuntimeEligibility result;
  auto* state = static_cast<RuntimeState*>(context->GetUserData(kRuntimeStateKey));
  if (!state) return result;
  result.generation = state->generation;
  result.acknowledged_generation = state->acknowledged_generation;
  result.user_rules_applied = state->acknowledged_generation == state->generation;
  result.listeners_reported = state->phase == SandiumUboRuntimePhase::kListenersReported;
  // Only native verified request/cosmetic bridge installation may set this.
  // Never accept a JavaScript claim that policy parity exists.
  result.policy_bridge_ready = ExtensionsAPIClient::Get() &&
      ExtensionsAPIClient::Get()->SupportsPrivateWebRequestPolicy(sandium_ubo::kExtensionId);
  return result;
}
int GetSandiumUboSettingsGeneration(content::BrowserContext* context) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  auto* state = static_cast<RuntimeState*>(context->GetUserData(kRuntimeStateKey));
  return state ? state->generation : 0;
}
void ResetSandiumUboRuntimePhase(content::BrowserContext* context) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  context->RemoveUserData(kRuntimeStateKey);
}
void RegisterSandiumUboFunctions() {
  auto* registry = ExtensionFunctionRegistry::GetInstance();
  registry->RegisterFunction<SandiumUboGetSettingsFunction>();
  registry->RegisterFunction<SandiumUboGetTabPolicyFunction>();
  registry->RegisterFunction<SandiumUboReportReadyFunction>();
  registry->RegisterFunction<SandiumUboGetSettingsSnapshotFunction>();
  registry->RegisterFunction<SandiumUboAcknowledgeSettingsFunction>();
}

ExtensionFunction::ResponseAction SandiumUboGetTabPolicyFunction::Run() {
  if (!IsTrustedComponent(extension()) || browser_context()->IsOffTheRecord())
    return RespondNow(Error("Sandium component capability unavailable"));
  EXTENSION_FUNCTION_VALIDATE(args().size() == 3 && args()[0].is_int() &&
      args()[1].is_int() && args()[2].is_string());
  const auto& expected_text = args()[2].GetString();
  if (expected_text.size() > 8192) return RespondNow(Error("Invalid frame"));
  const GURL expected(expected_text);
  content::WebContents* contents = nullptr;
  // Same native SessionTabHelper identity used by ExtensionTabUtil, without a
  // dependency cycle back into //chrome/browser/extensions (which owns us).
  for (auto it = content::RenderProcessHost::AllHostsIterator();
       !it.IsAtEnd() && !contents; it.Advance()) {
    auto* process = it.GetCurrentValue();
    if (!process->IsInitializedAndNotDead() ||
        process->GetBrowserContext() != browser_context()) continue;
    process->ForEachRenderFrameHost([&](content::RenderFrameHost* candidate) {
      auto* tab = content::WebContents::FromRenderFrameHost(candidate);
      if (!tab || tab->GetBrowserContext() != browser_context() ||
          candidate != tab->GetPrimaryMainFrame()) return;
      if (sessions::SessionTabHelper::IdForTab(tab).id() == args()[0].GetInt())
        contents = tab;
    });
  }
  if (!contents) return RespondNow(Error("Tab unavailable"));
  auto* frame = ExtensionApiFrameIdMap::GetRenderFrameHostById(contents, args()[1].GetInt());
  if (!frame || !expected.is_valid() || frame->GetLastCommittedURL() != expected)
    return RespondNow(Error("Document changed"));
  auto* main = contents->GetPrimaryMainFrame();
  if (!main) return RespondNow(Error("Main frame unavailable"));
  const GURL top_url = main->GetLastCommittedURL();
  auto* map = HostContentSettingsMapFactory::GetForProfile(Profile::FromBrowserContext(browser_context()));
  if (!map) return RespondNow(Error("Profile settings unavailable"));
  base::DictValue policy;
  policy.Set("protocol", 1);
  policy.Set("engineOwned", sandium_ubo::IsUboOwnerChosen(browser_context()));
  policy.Set("shieldsEnabled", brave_shields::IsBraveShieldsEnabled(map, top_url));
  policy.Set("adControl", brave_shields::ControlTypeToString(brave_shields::GetAdControlType(map, top_url)));
  policy.Set("cosmeticControl", brave_shields::ControlTypeToString(brave_shields::GetCosmeticFilteringControlType(map, top_url)));
  return RespondNow(WithArguments(base::Value(std::move(policy))));
}

ExtensionFunction::ResponseAction SandiumUboGetSettingsFunction::Run() {
  if (!IsTrustedComponent(extension()) || browser_context()->IsOffTheRecord())
    return RespondNow(Error("Sandium component capability unavailable"));
  EXTENSION_FUNCTION_VALIDATE(args().size() == 1 && args()[0].is_string());
  const auto& text = args()[0].GetString();
  if (text.size() > 8192) return RespondNow(Error("Invalid origin"));
  const GURL url(text);
  if (!url.is_valid() || !url.SchemeIsHTTPOrHTTPS() || url.has_username() ||
      url.has_password()) return RespondNow(Error("Invalid origin"));
  auto* profile = Profile::FromBrowserContext(browser_context());
  auto* map = HostContentSettingsMapFactory::GetForProfile(profile);
  if (!map) return RespondNow(Error("Profile settings unavailable"));
  base::DictValue settings;
  settings.Set("protocol", 1);
  settings.Set("shieldsEnabled", brave_shields::IsBraveShieldsEnabled(map, url));
  settings.Set("adControl", brave_shields::ControlTypeToString(
      brave_shields::GetAdControlType(map, url)));
  settings.Set("cosmeticControl", brave_shields::ControlTypeToString(
      brave_shields::GetCosmeticFilteringControlType(map, url)));
  // Observation bridge only: neither this call nor a readiness report changes
  // the active blocker. Never infer engine cutover from successful API access.
  settings.Set("engineCutover", sandium_ubo::IsUboOwnerChosen(browser_context()));
  settings.Set("startupAborted", sandium_ubo::IsRuntimeStartupAborted(browser_context()));
  settings.Set("nativeFallbackComplete", sandium_ubo::IsNativeFallbackComplete(browser_context()));
  settings.Set("restartRequired", sandium_ubo::OwnerRestartRequired(browser_context()));
  return RespondNow(WithArguments(base::Value(std::move(settings))));
}

ExtensionFunction::ResponseAction SandiumUboGetSettingsSnapshotFunction::Run() {
  if (!IsTrustedComponent(extension()) || browser_context()->IsOffTheRecord())
    return RespondNow(Error("Sandium component capability unavailable"));
  EXTENSION_FUNCTION_VALIDATE(args().empty());
  auto* profile = Profile::FromBrowserContext(browser_context());
  auto* map = HostContentSettingsMapFactory::GetForProfile(profile);
  if (!map) return RespondNow(Error("Profile settings unavailable"));
  base::DictValue snapshot;
  snapshot.Set("protocol", 1);
  snapshot.Set("generation", GetOrCreateState(browser_context())->generation);
  snapshot.Set("engineCutover", false);
  if (!g_browser_process || !g_browser_process->local_state())
    return RespondNow(Error("Custom filter settings unavailable"));
  const auto& custom_filters = g_browser_process->local_state()->GetString(
      brave_shields::prefs::kAdBlockCustomFilters);
  if (custom_filters.size() > 4 * 1024 * 1024)
    return RespondNow(Error("Custom filter snapshot limit exceeded"));
  snapshot.Set("customFilters", custom_filters);
  snapshot.Set("customFiltersSha256", base::ToLowerASCII(
      base::HexEncode(crypto::SHA256HashString(custom_filters))));
  base::DictValue defaults;
  defaults.Set("shields", static_cast<int>(map->GetDefaultContentSetting(
      ContentSettingsType::BRAVE_SHIELDS, nullptr)));
  defaults.Set("ads", static_cast<int>(map->GetDefaultContentSetting(
      ContentSettingsType::BRAVE_ADS, nullptr)));
  defaults.Set("cosmetic", brave_shields::ControlTypeToString(
      brave_shields::GetCosmeticFilteringControlType(map, GURL())));
  snapshot.Set("defaults", std::move(defaults));
  // Diagnostic listing only: Chromium explicitly forbids using this iterator
  // as authoritative settings evaluation. Expiry and provider semantics need
  // native resolution before any future mirror can grant ownership.
  // Preserve the native iterator order and *both* patterns. No hostname-only
  // approximation: managed, wildcard, scheme and port rules must not be lost.
  // This diagnostic snapshot is not yet a live mirror or cutover capability.
  size_t rule_count = 0;
  bool overflow = false;
  auto append_rules = [&](const char* name, ContentSettingsType type) {
    base::ListValue rules;
    for (const auto& entry : map->GetSettingsForOneType(type)) {
      if (++rule_count > 16384) { overflow = true; return; }
      base::DictValue rule;
      rule.Set("primary", entry.primary_pattern.ToString());
      rule.Set("secondary", entry.secondary_pattern.ToString());
      rule.Set("value", entry.setting_value.Clone());
      rules.Append(std::move(rule));
    }
    snapshot.Set(name, std::move(rules));
  };
  append_rules("shields", ContentSettingsType::BRAVE_SHIELDS);
  append_rules("ads", ContentSettingsType::BRAVE_ADS);
  append_rules("cosmetic", ContentSettingsType::BRAVE_COSMETIC_FILTERING);
  if (overflow) return RespondNow(Error("Settings snapshot limit exceeded"));
  return RespondNow(WithArguments(base::Value(std::move(snapshot))));
}

ExtensionFunction::ResponseAction SandiumUboAcknowledgeSettingsFunction::Run() {
  if (!IsTrustedComponent(extension()) || browser_context()->IsOffTheRecord())
    return RespondNow(Error("Sandium component capability unavailable"));
  EXTENSION_FUNCTION_VALIDATE(args().size() == 2 && args()[0].is_int() && args()[1].is_string());
  if (!g_browser_process || !g_browser_process->local_state())
    return RespondNow(Error("Custom filter settings unavailable"));
  const auto digest = base::ToLowerASCII(base::HexEncode(crypto::SHA256HashString(
      g_browser_process->local_state()->GetString(brave_shields::prefs::kAdBlockCustomFilters))));
  if (args()[1].GetString() != digest)
    return RespondNow(Error("Custom filter generation changed"));
  auto* state = GetOrCreateState(browser_context());
  if (args()[0].GetInt() != state->generation)
    return RespondNow(Error("Settings generation changed; synchronization required"));
  state->acknowledged_generation = state->generation;
  return RespondNow(WithArguments(true));
}

ExtensionFunction::ResponseAction SandiumUboReportReadyFunction::Run() {
  if (!IsTrustedComponent(extension()) || browser_context()->IsOffTheRecord())
    return RespondNow(Error("Sandium component capability unavailable"));
  EXTENSION_FUNCTION_VALIDATE(args().size() == 2 && args()[0].is_int() &&
                              args()[1].is_string());
  if (args()[0].GetInt() != 1 || args()[1].GetString() != "listeners-ready")
    return RespondNow(Error("Unsupported runtime handshake"));
  auto* state = GetOrCreateState(browser_context());
  state->phase = SandiumUboRuntimePhase::kListenersReported;
  // No URLs, rules, page content or user settings in this milestone log.
  // Self-report is NOT controlled network/cosmetic/scriptlet test evidence.
  LOG(INFO) << "SANDIUM_UBO_RUNTIME_REPORT protocol=1 version=1.76.4 "
               "phase=listeners-ready cutover=0";
  return RespondNow(WithArguments(true));
}
}  // namespace extensions::api
