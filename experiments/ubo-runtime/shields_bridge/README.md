# Fixed-identity uBO / native Shields bridge

This directory contains **implemented source**, not a claim of a tested Android
replacement. The full uBO1.76.4 payload, API bridge, native exclusive owner, startup
barrier and filtering adapters are now present. Actual GN/native/Java build status
and device results must be reported separately from these source tests.

## Implemented

- Private extension API bound to pinned component ID, version, install location
  and regular profile. Websites, arbitrary extensions and private profiles cannot
  invoke it. No arbitrary script execution endpoint.
- Authoritative native master/ad/cosmetic policy attached to each fixed-component
  webRequest recipient, plus native tab/document policy for cosmetic and scriptlet
  work. Both Chromium dispatch modes retain the private field. No guessed JS
  hostname matching or raw-rule snapshot used as request policy.
- Startup reconciles native custom-filter text into real uBO save/readback/list
  reload before readyToFilter. Native ACK requires exact generation and source
  SHA256 plus current list revision. Listeners are reported only after initializeTabs and webRequest.start.
- Profile settings/custom-filter observers invalidate ACKs; the adapter serially
  reconciles and ACKs the current generation again. The engine owner remains
  fixed while its settings can change.
- Network, cosmetics/CSS insertion, scriptlet injection and popup closure have
  native policy gates. Missing/invalid capability does not authorize filtering.
- Coordinator waits at most12seconds for startup, checks a live background host,
  and unloads the component before native fallback. Failure to tear down does not
  silently release navigation. Runtime loss is guarded separately.
- Existing native picker/clear/custom-rule storage is retained; it is not replaced
  by a duplicate extension-only database. Cookies, dark mode and shred are untouched.
- Genuine upstream uBO block outcomes are batched locally into existing Android
  Shields blocked-resource events. The fixed caller, owner, profile and immutable
  main-document identity are checked before delivery. No invented URL/count.
- `status/` adds a read-only row inside existing Shields, distinguishing native,
  uBO, updating, bounded startup, native fallback and unavailable/restart states.

The public experiment's two-state cosmetic control normalizes On to native BLOCK;
this is not a reproduction of the hidden three-state Standard/Aggressive policy.

## Remaining parity and validation gaps

1. **Native list/subscription controls:** source bridge now maps authoritative
   effective Sandium subscription selections to exact original sources and
   validates compiled payloads before revision ACK. The actual product is
   subscription-only: readiness requires its native bootstrap migration, not
   upstream Brave catalog arrival. Disabled/deleted subscriptions remain so.
   Enabled-source availability and actual rule semantics remain unverified;
   unavailable enabled sources reject readiness rather than silently succeeding. See LIST_RECONCILIATION.md.
2. **Private profiles:** bridge is intentionally regular-profile-only. OTR retains
   Brave native filtering and the status row says so. A full private uBO lifecycle
   needs separate data/isolation work and tests.
3. **Runtime verification:** compile success, actual network block+exception,
   scriptlet/cosmetic behavior, popup handling, source control changes, restart,
   update and rollback persistence must be exercised on real ARM64 Android.
4. **Counters:** telemetry is bounded and omits stale, frameless, uncommitted-root
   and over-limit events rather than misattributing them. CSS hiding is not a
   network-block count. Do not equate it to every uBO dashboard statistic.
5. Performance and navigation races need device measurement. The native tab
   lookup uses SessionTabHelper IDs and public renderer enumeration, avoiding a
   chrome/browser/extensions dependency cycle but requiring a performance audit.
6. Already-injected cosmetic/scriptlet effects may require page reload after a
   policy change. Restoring page state must not be promised without runtime tests.

## Snapshot is diagnostic, not policy

`getSettingsSnapshot` returns bounded ordered native rule listings/defaults and
custom-filter text. Chromium explicitly documents GetSettingsForOneType as a UI
listing, not an authoritative policy-evaluation API; expiry/provider semantics
are therefore handled by the native request path instead. Snapshots never grant
ownership. Likewise a readiness self-report alone is not a filtering smoke test.

## Composition and reset

Apply loader, bridge, routing, startup/request-policy and finally visible status
according to the integrated build script. Bridge invocation:

```
python3 experiments/ubo-runtime/shields_bridge/apply.py --core "$SRC/brave"
```

The bridge patches actual pinned uBO modules, registers added resources, and
recomputes the localized loader's per-file disk inventory. Every modified file,
including disk_resources.h, is in its exact before/after ownership receipt.
Reset outer layers first (status/request-policy/startup/routing as applied), then
bridge, then loader, before EXT0/product source replay:

```
python3 experiments/ubo-runtime/shields_bridge/apply.py --core "$SRC/brave" --reset
```

Interrupted before/after states are accepted; unknown edits are refused rather
than overwritten. Never delete receipts instead of reversing the layers.

## Evidence

Pinned Chromium source: d331de35ca8ab1358c7a17e4bd41627d55eaef51. Observer lifecycle,
event dispatch, tab/frame/document identity and GN ownership were checked against
those headers/sources. Python tests cover composition/reset and source contracts;
Node tests cover adapter gating, generation reconciliation, stale-popup protection
and real-block batching. Patched upstream modules pass syntax/idempotence checks.
These are not native compilation or device-level tests.
