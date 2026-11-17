# Fixed-identity native Shields observation bridge (phase 1)

Apply AFTER EXT0 source replay and loader overlay:

```
python3 experiments/ubo-runtime/shields_bridge/apply.py --core "$SRC/brave"
```

This wires a real native extension API, schema/allowlist, explicit Android function
registration, resource-mapped ES module, and a hook in official uBO 1.76.4 startup.
The loader remains disabled by default. No build/run is triggered by this overlay.

The bridge permits only the pinned component ID, component installation location,
version and regular profile. No arbitrary extension/webpage endpoint or script
execution capability is exposed. `getSettings(url)` returns the existing native
Shields master/ad/cosmetic values; it changes none of them. Unrelated controls are
untouched. No URL/rule/page content is logged.

`reportReady(1, "listeners-ready")` executes only after `initializeTabs()` and
`webRequest.start()`, not the earlier `readyToFilter` assignment. Its profile-owned
state is observational and UI-thread only. It does not prove blocked requests,
cosmetic filtering or scriptlets, and it never suppresses Brave. It can become
stale after a background crash; a future coordinator must additionally observe
extension unload/background-process destruction and use generation ACKs. The
accessor must NOT be interpreted as permission to cut over.

## Still required for replacement

* Snapshot all native site rules/defaults before unsuspending filtering, not an
  asynchronous settings lookup on each request.
* Identity-only content-settings-change events, generations, ACKs and invalidation.
* Preserve native pattern precedence and reject unsupported mapping. Native
  Standard/Aggressive control semantics cannot silently become one on/off bit.
* Existing custom-rule/picker add, reset, presence, import/export and counts.
* Exclusive coordinated network/cosmetic/scriptlet switching with rollback.
* Real native compile, controlled request+exception, cosmetic/scriptlet test,
  restart persistence and phone runtime validation.

The five Python tests cover composition, restricted API source invariants and
startup ordering; Node tests cover adapter failure/version/absent-API paths. The
hook was applied twice to the exact validated official release bundle. These are
source/adapter tests, not Android or live-engine tests.

## Reset ordering and owned changes

Before replaying lower-level overlays, run:

```
python3 experiments/ubo-runtime/shields_bridge/apply.py --core "$SRC/brave" --reset
# then reset loader, then EXT0 source replay
```

The local receipt records exact before/after bytes before live writes. Reset
accepts original or expected postimage (including interrupted application), refuses
unowned modifications and restores the loader's exact postimage. Paths/symlinks
are validated. No arbitrary unknown source is overwritten. Repeated application
first restores this overlay only. Do not remove receipts before reversing layers.

Phase 2 observation (not replacement): `getSettingsSnapshot` exposes ordered
native Shields/ad/cosmetic rule listings, defaults and the existing local-state
custom-filter string. It subscribes before snapshotting, sends identity-only,
profile-restricted change-generation events, and unregisters all observations
before profile keyed-service shutdown. The JS adapter rejects a reply made stale
by an in-flight settings event; it never converts raw patterns into uBO switches.
The getter is bounded (16,384 rules; 4 MiB custom-filter text), rejecting rather
than silently truncating. Cookies, dark mode and shred settings remain untouched.

**Critical limitation:** pinned Chromium `host_content_settings_map.h` documents
`GetSettingsForOneType` as a UI listing API, explicitly not an authoritative
settings-evaluation API; returned rules can expire. Consequently this snapshot is
not a safe synchronous per-request policy mirror. Before activation, implement a
Chromium-evaluated policy handoff behind a pre-request navigation barrier, with
expiry/invalidation and custom-rule synchronization ACK, rather than a guessed
hostname matcher. No engine ownership is granted by either snapshot or readiness.

Exact Chromium sources checked: commit d331de35ca8ab1358c7a17e4bd41627d55eaef51,
`extensions/browser/event_router.h`, `components/content_settings/core/browser/`
`{host_content_settings_map,content_settings_observer}.h`,
`chrome/browser/profiles/{profile.h,profile.cc,profile_observer.h}`. Native compile
and device-level behavior are still unverified.

Composition supports the localized loader's constructor initialization marker.
After adapter/start.js mutations it regenerates `disk_resources.h` using the
loader's pure `build_disk_inventory(core)` helper; this header is included in the
bridge ownership receipt and restored before the loader reset.

Startup now imports the bridge before `µb.readyToFilter = true`, reconciles the
native custom-filter text through real uBO save/readback/list reload, and ACKs the
exact native generation plus source SHA-256. Listener readiness is reported only
after tab restore and `webRequest.start()`. Failure aborts uBO startup; only the
native coordinator may unload and choose fallback. Native eligibility keeps
`policy_bridge_ready=false` until authoritative network/cosmetic bridges exist.
Runtime settings changes invalidate readiness and ACK immediately; a live reload
or restart handoff remains coordinator work, not silently considered synchronized.

Authoritative policy adapters (still require native/device validation):
- uBO request/header/response handlers filter only when private native request
  details confirm uBO ownership, Shields on and native ad control enabled.
- Content-script specific/generic cosmetics and actual CSS insertion query
  fixed-identity native `getTabPolicy(tabId,frameId,expectedURL)`. Tab and frame
  identity are resolved natively; stale documents and cross-profile access fail.
- Programmatic MV2 scriptlet injection is gated by the native tab policy too.
- Settings events serially reconcile native custom rules and re-ACK the current
  generation, including listener readiness after startup; no JS hostname mirror.
- The owner stays immutable. Policy capability is queried natively from the
  registered ExtensionsAPIClient override, never claimed by extension JavaScript.
- `getSettings` exposes owner, startup-aborted, native-fallback-complete and
  restart-required fields. A user-visible Shields status UI is not yet wired.

The native tab lookup uses the same SessionTabHelper ID as ExtensionTabUtil and
only the exact normal profile and its primary main frames. Its public-renderer
scan avoids a GN dependency cycle; performance should be measured before release.
