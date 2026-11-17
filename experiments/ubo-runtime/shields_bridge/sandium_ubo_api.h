// Copyright 2026 Sandium. SPDX-License-Identifier: MPL-2.0
#ifndef BRAVE_BROWSER_EXTENSIONS_API_SANDIUM_UBO_API_H_
#define BRAVE_BROWSER_EXTENSIONS_API_SANDIUM_UBO_API_H_
#include "extensions/browser/extension_function.h"
namespace content { class BrowserContext; }
namespace extensions::api {
struct SandiumUboRuntimeEligibility {
  int generation = 0;
  int acknowledged_generation = 0;
  bool user_rules_applied = false;
  bool policy_bridge_ready = false;
  bool listeners_reported = false;
};
SandiumUboRuntimeEligibility GetSandiumUboRuntimeEligibility(content::BrowserContext* context);
// Observation only; never authorizes suppression of the existing blocker.
enum class SandiumUboRuntimePhase { kNotReported, kListenersReported };
SandiumUboRuntimePhase GetSandiumUboRuntimePhase(content::BrowserContext* context);
int GetSandiumUboSettingsGeneration(content::BrowserContext* context);
void ResetSandiumUboRuntimePhase(content::BrowserContext* context);
void RegisterSandiumUboFunctions();
class SandiumUboGetTabPolicyFunction : public ExtensionFunction {
 public:
  DECLARE_EXTENSION_FUNCTION("sandiumUbo.getTabPolicy", UNKNOWN)
 protected:
  ~SandiumUboGetTabPolicyFunction() override = default;
  ResponseAction Run() override;
};
class SandiumUboGetSettingsFunction : public ExtensionFunction {
 public:
  DECLARE_EXTENSION_FUNCTION("sandiumUbo.getSettings", UNKNOWN)
 protected:
  ~SandiumUboGetSettingsFunction() override = default;
  ResponseAction Run() override;
};
class SandiumUboAcknowledgeSettingsFunction : public ExtensionFunction {
 public:
  DECLARE_EXTENSION_FUNCTION("sandiumUbo.acknowledgeSettings", UNKNOWN)
 protected:
  ~SandiumUboAcknowledgeSettingsFunction() override = default;
  ResponseAction Run() override;
};
class SandiumUboGetSettingsSnapshotFunction : public ExtensionFunction {
 public:
  DECLARE_EXTENSION_FUNCTION("sandiumUbo.getSettingsSnapshot", UNKNOWN)
 protected:
  ~SandiumUboGetSettingsSnapshotFunction() override = default;
  ResponseAction Run() override;
};
class SandiumUboReportReadyFunction : public ExtensionFunction {
 public:
  DECLARE_EXTENSION_FUNCTION("sandiumUbo.reportReady", UNKNOWN)
 protected:
  ~SandiumUboReportReadyFunction() override = default;
  ResponseAction Run() override;
};
}  // namespace extensions::api
#endif  // BRAVE_BROWSER_EXTENSIONS_API_SANDIUM_UBO_API_H_
