# Exclusive engine routing and bounded startup

Source state reviewed at Sandium 35ccd8c; Brave pin
44a84b1f89d9a35287289d6a3d493e362f5a5123. Routing, coordinator, request policy and
visible status are implemented and CI-wired. Run #1329 was requested as an
activated candidate; this document does not assert its compile or device result.

The native owner gates TP PreWork, CSP Work, DomainBlock navigation and cosmetic
resource delivery. Ownership is UI-thread/profile scoped and immutable once
selected. Worker code receives captured ownership, never a BrowserContext read.
Cookies, fingerprinting, HTTPS upgrades and unrelated Shields settings stay native.
Private profiles explicitly retain Brave filtering, not uBO.

`PrepareUboOwnerBeforeFirstRequest` is called by the startup coordinator after
native eligibility checks. These checks establish initialization/ACK consistency,
not experimentally proven block/exception behavior. Ordinary setting changes
invalidate the settings generation and can be acknowledged under the same owner;
they do not silently switch engines or inherently require restart.

## Composition and evidence

The integrated script is the order authority: loader, bridge, routing, startup,
request policy, optional paired activation, then visible status. Reset in reverse
order before source/product replay. Exact ownership receipts reject unowned edits;
do not delete receipts to bypass a failed reset.

Source tests apply/replay/reset exact pinned overlays and exercise a standalone
C++ ownership model. Those tests are not a Chromium build or Android runtime test.

## Implemented startup coordinator

`apply_startup.py` is a separate overlay after localized loader, bridge and
routing. Reverse reset order: startup, routing, Shields, loader. It inserts a
HTTP(S) navigation throttle ahead of Chrome/Brave navigation throttles and moves native
domain routing to WillStartRequest so throttle construction cannot freeze the
wrong owner. External HTTP(S) navigation waits at most 12 seconds for native
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

This is executable source, not runtime proof. Standalone feature defaults remain
off; activation/ enables the paired features only for the explicit candidate.
The status/ overlay exposes fallback/unavailable state inside Shields. Request
policy suppresses uBO decisions while owner is pending/native. Native build and
device startup, concurrent tabs, timeout, crash and setting-change evidence must
be reported separately. No controlled smoke verification is invented.

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
