# Rewards and browser Ads: Android exclusion candidate

Pinned Brave `44a84b1f89d9a35287289d6a3d493e362f5a5123`.
Status: source transformation and local tests pass; native build/APK/device
validation remains mandatory. This is browser advertising, NOT Shields ad blocking.

Apply `apply-sandium-rewards-removal.py CORE` after normal UI overlays and after
Wallet removal. Final GN args must include `enable_brave_rewards=false` and
`enable_brave_ads=false`. Central integration owns those args. Exact upstream
reset paths are exported as `FILES`; generated
`android/java/org/chromium/chrome/browser/SandiumTextUtils.java` must also be
removed before replay when restoring a continuation checkpoint.

## Removed implementation paths

- Rewards Android worker/helper/balance/external-wallet/observer/policy sources,
  Rewards debug/adaptive CAPTCHA Java, Ads helper/device ID/notification/dialog
  Java source list and Rewards/Ads Java mojom/JNI generation dependencies.
- Rewards model/lifecycle calls, page launch adapters, notification observers,
  background retention ads branches, onboarding region query, clear-data actions,
  policy UI and toolbar Rewards/publisher service integrations.
- Adaptive CAPTCHA native service factory registration, startup prefs and GN
  dependencies in browser/core/UI/Android preferences. This avoids active service
  creation even though Origin branding remains Sandium, not upstream Origin.
- Exclusive Ads onboarding dialog layouts and Rewards debug preferences XML.
- QA Rewards runtime reset/ads-number calls, staging-pref read and DB UI actions.
  No user data is reset or erased.

Native Rewards implementation/engine and browser Ads services follow existing
upstream GN buildflag gates. Common Rewards pref registration/migration names,
feature headers and unreachable shared toolbar resource anchors remain. They
must not be counted as an active Rewards engine. Native implementation link
inputs and DEX packages must be checked on CI; source tests alone are not proof.

## Shared functionality deliberately retained

`BraveRewardsHelper` formerly owned HTML formatting used by custom-filter help
and the license page. Those two helpers move to standalone `SandiumTextUtils`,
with upstream MPL notice retained. Filter editing/update methods and license
content are preserved. Shields tracker/ad counts and their JNI accessors are
preserved; removing them would break Sandium rather than remove browser Ads.
Ordinary NTP background imagery keeps its metric field as an integer, removing
the Ads mojom annotation dependency. No advertiser engine is restored by that
field. Generic privacy notification checks remain.

## Local verification

Seven exact-pin fixture tests pass: hashes, Java/JNI list closure, native adaptive
CAPTCHA startup removal, Shields/filter-help retention, idempotence, marked-file
drift rejection and preservation of block counts/no stored-data deletion.
Seventeen transformed Java files parse without syntax errors. Wallet + Rewards
+ final VPN transformations compose; 24 composed Java files parse successfully.
No Android SDK/Chromium compilation or installed APK test has run locally.

## Required CI/device checks

GN generation, javac, native link and APK build must all pass. Inspect actual
GN dependency closure (not merely args.gn), DEX class inventory and link inputs
for Rewards implementation/engine, Ads services/device-ID/notification producer,
and adaptive CAPTCHA service. Exempt common inert prefs/legal/buildflag metadata.
Test start/resume, private tabs, NTP, toolbar popup, custom filters/edit/help,
license page, notification privacy settings, QA preferences, and profile upgrade
without any valuable data deletion. APK absence and absence of service startup
remain unverified until these checks complete.
