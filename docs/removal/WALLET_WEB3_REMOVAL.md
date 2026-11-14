# Wallet and Web3 domains removal, Android

Brave pin: `44a84b1f89d9a35287289d6a3d493e362f5a5123`.
Stage: implemented source transformation; Android compile and APK audit pending.
Do not mark this group release-verified solely because these tests pass.

## Apply contract

Run `.circleci/scripts/apply-sandium-wallet-removal.py CORE` after the existing
Sandium UI overlays, before GN generation. Set `enable_brave_wallet=false` in
final effective GN args. Central integration owns that recipe. `TOUCHED` in the
script is the authoritative exact restore list for continuation checkpoints;
reset those paths to pinned upstream before replaying all overlays. No broad
source or build-output deletion is needed.

The script excludes all `crypto_wallet`, wallet-only `app/domain`, and
`decentralized_dns` Java sources, Wallet settings/site-settings classes, wallet
image helper and adaptive button controller. It removes Wallet manifest
activities, adaptive toolbar registration, and settings fragment routes.
Exclusive resource paths are versioned in `wallet-exclusive-resources.json`.
Shared colors/styles/drawables and generic site-settings interface are retained.
Native wallet engines, injected providers, Web3 domain resolver and wallet JNI/
mojom build dependencies use upstream `enable_brave_wallet` build guards, NOT
runtime flags. The renderer guards are in `renderer/brave_content_renderer_client.cc`;
`components/decentralized_dns/{core,content}/BUILD.gn` assert that Wallet is enabled.

Mixed BraveActivity/toolbar files retain inert void compatibility methods and
hidden layout anchors for shared browser references. Their Wallet service,
model, provider-request and DApps controller bodies are physically removed.
There is no runtime preference that restores those bodies. The generic
`BraveWalletSiteSettingsDelegate` adapter reports unavailable; it contains no
wallet implementation. Deprecated resource/pref identifiers are not themselves
wallet functionality.

No profile files, seed material, preferences, accounts, wallets, or user data
are deleted. No changes to TLS/WebCrypto, ordinary DNS, shared crypto, Shields,
filters, updater or browsing state. User-requested data export/deletion remains
a separate decision.

## Verification

- Six tests replay exact pinned input fixtures, verify source/manifest/resource
  exclusion, idempotence, fail-closed missing method anchors and retained Shields
  lines. Fixture hashes are tracked.
- Retained Android Java source-list import closure has no wallet implementation
  imports after application (generic site-settings interface is retained).
- Seven changed Java files parsed with tree-sitter-java without syntax errors,
  both on pinned files and the available post-Sandium-overlay files.
- This is NOT javac/GN/link/APK/device evidence. CI must generate graph, compile,
  check DEX for excluded implementation packages and inspect native link inputs
  for wallet/browser/provider/decentralized-DNS implementation targets. Verify
  browsing, Shields, site settings, launch/restore and no provider injection on
  device. Shared buildflag headers, legal notices and inactive data identifiers
  are allowable and should not be mistaken for implementations.

## Rewards/Ads are separate and not removed by this script

`wallet-rewards-pinned-audit.json` is read directly from pinned Git objects,
not working-tree overlays. Rewards/Ads require additional adaptations before
`enable_brave_rewards=false` / `enable_brave_ads=false` can safely be enabled:

- `browser/android/preferences/BUILD.gn` unconditionally depends on Rewards core.
- `build/android/config.gni` includes Rewards/Ads mojom_java and Ads JNI sources.
- `android/brave_java_sources.gni` includes Rewards Java and imports/merges Ads
  sources unconditionally.
- Ads consumers include onboarding supported-region checks, clear-data handler
  and NTP ad metric model. These are NOT Shields ad blocking.

Do not report Rewards/Ads removed based on the Wallet transformation.
