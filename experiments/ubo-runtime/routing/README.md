# Exclusive routing scaffold (NOT activated, NOT CI-wired)

Pinned Brave inputs:44a84b1f89d9a35287289d6a3d493e362f5a5123.

`apply.py --core SRC/brave` adds default-disabled `SandiumUboExclusiveRouting`,
a native-only profile ownership API and four UI-thread boundaries:

* TP PreWork, before any asynchronous network filtering/CNAME work.
* CSP Work, before original CSP header removal or native async work.
* DomainBlock MaybeCreateAndAdd, before native navigation throttle creation.
* Cosmetic Bind, before attaching the native receiver/worker path.

It does not change cookies, fingerprinting, HTTPS upgrades, unrelated Shields
settings or private-profile behavior. Missing/private contexts retain native.
BrowserContext ownership is profile user-data, UI-thread only. Workers never
consult it. A first boundary freezes ownership for the session. Late ownership
changes are rejected, so no native task launched in an old epoch can complete
under a newly selected uBO owner. Generation invalidation before freezing reverts
to native; after freezing it records restart-required, never silently flips.

## Missing activation work (must not be omitted)

There is deliberately NO caller of PrepareUboOwnerBeforeFirstRequest. Its
`verified` argument is an internal contract, not proof by itself. A future native
coordinator must establish exact snapshot-generation ACK, actual uBO listener
readiness, controlled network block/exception and cosmetic behavior, and a
startup navigation barrier. Extension assets/list initialization must remain
allowed while user navigation is held with a bounded timeout. Otherwise the
first homepage request freezes Brave before asynchronous uBO startup and
replacement can never activate. Timeout must keep native, disarm uBO filtering,
and visibly report fallback; do not run both engines.

A post-cutover runtime crash/settings invalidation requires coordinated traffic
handling and restart, not a silent live switch. That handling is NOT implemented.
Existing user-rule migration, counts, site switches, private-profile parity,
cosmetic receiver disconnect effects and restart UX remain unverified. The
routing scaffold alone does not satisfy engine replacement or Shields parity.

## Lifecycle and tests

This optional overlay owns a receipt in core/.sandium-ubo-routing-receipt.json.
Reset it BEFORE Shields and loader, BEFORE source resets. It is intentionally not
added to CI while coordinator/rule bridge are missing. Reset validates complete
owned pre/postimages first and supports partial apply/reset states. Unowned edits
fail closed. No runtime calls or feature enablement are inserted.

`test_routing.py` compiles/runs the standalone C++ owner-state model and applies,
replays and resets boundary edits against pinned source. Native Chromium C++/GN
and device behavior are NOT verified by those tests.

## Startup coordinator follow-up

`apply_startup.py` is a separate overlay after localized loader, bridge and
routing. Reverse reset order: startup, routing, Shields, loader. It inserts a
HTTP(S) navigation throttle ahead of Chrome/Brave navigation throttles and moves native
domain routing to WillStartRequest so throttle construction cannot freeze the
wrong owner. All non-extension navigation waits at most 12 seconds for native
eligibility: exact current generation ACK, user rules applied, native policy
bridge ready, listeners reported and enabled fixed component. Private profiles
remain native. Extension-initiated network/cosmetic initialization does not freeze
ownership, allowing list/background startup while user navigation waits.

On timeout it first marks startup aborted (blocking late materializer Add), then
removes the component and verifies loader registration and enabled registry entry
are absent. Pinned WebRequestAPI::OnListenerRemoved removes unloaded extension
listeners synchronously. Only verified teardown releases native navigation;
incomplete teardown cancels instead. Parallel waiting navigations observe the
same abort/fallback state. A changed settings generation after uBO selection defers external navigation
until the exact new ACK is ready, then updates the settings generation without
changing engines. A 12-second refresh failure cancels that navigation only; it
does not force a restart or silently switch engines.

This is executable source, not runtime proof. Default-off routing remains.
Current coordinator uses LOG(ERROR) plus exposed fallback-state getters; visible
The status/ overlay exposes fallback/unavailable state inside Shields; actual visual/runtime QA remains required. Native GN/C++ compilation and device
startup, concurrent tabs, timeout, crashes and settings-change tests are pending.
Request-policy must suppress uBO decisions while owner is pending/native. Existing
in-flight pages on runtime failure need further coordinated handling; do not
claim complete crash recovery. No controlled smoke verification is invented.

Tests additionally apply/replay/reset startup on composed pinned EXT0+localized
loader sources and check eligibility/timeout/late-registration guards.

Internal homepage/settings navigation is never deferred. Internal cosmetic and
domain/CSP boundaries do not seal ownership. Engine identity is immutable, not
settings: ordinary site toggles use authoritative per-request policy, and custom
rule changes can refresh/ACK under the existing uBO owner.

### Correct native cosmetic boundary

The native picker `CosmeticFiltersTabHelper::BindCosmeticFiltersHandler` is NOT
changed. Ownership is captured in UI `BindCosmeticFiltersResources` and passed as
an immutable bool into worker `CosmeticFiltersResources`. For uBO-owned sessions,
HiddenClassIdSelectors returns an empty DictValue and UrlCosmeticResources an
empty dictionary Value. Receivers/callbacks remain valid; worker code does not
read BrowserContext. Existing constructor callers default to native behavior.
The source tests assert the picker is byte-for-byte unchanged and both resource
methods have empty-response branches.

### Armed startup and runtime-loss guard

The loader arms pending startup on UI only when runtime and exclusive-routing
features are explicitly enabled. Non-extension HTTP(S)/WS requests while armed
but unselected fail closed with ERR_BLOCKED_BY_CLIENT, rather than freezing the
native owner or bypassing both filters. Main navigation retains its bounded
barrier; extension assets/list startup remain allowed. Pre-existing worker fetches
may need retry after owner selection: that is an explicit safety tradeoff, not a
claim that all background workflows are uninterrupted.

Before any uBO selection, the browser coordinator installs profile-owned
ExtensionRegistry and ExtensionHostRegistry observers. Fixed-component unload,
persistent-background renderer death or background host destruction latches
runtime-unavailable. Active-page TP/CSP requests and subsequent HTTP navigation
then fail closed without changing engines. RestartRequired exposes this runtime
failure, not ordinary site-setting changes. Ordinary popup-host closure is not
misidentified as background failure. Scope observations reset on registry shutdown.
No recovery is silently attempted; full crash-recovery UX and device tests remain
required. Already completed or in-flight network operations cannot be retroactively
blocked; these guards govern subsequent native request/response boundaries.

Observer signatures and ViewType enum were checked against pinned Chromium
headers. Native compilation still required; source/model tests are not substitutes.
