# Per-request native Shields policy (candidate implementation)

Apply after loader, Shields bridge, routing and startup, before activation/status
and GN. Reset activation/status before this layer, then its underlying layers. Ownership receipt rejects foreign
changes rather than clobbering them.

Both pinned Chromium webRequest dispatch modes invoke an embedder virtual hook
**after recipient permission filtering**. The base implementation is a no-op.
Brave supplies fields only for the fixed component ID, expected uBO version,
component manifest location, same regular profile and enabled registry entry.
Other extensions and private/cross-profile delivery receive no fields.

`details.sandiumShields` contains protocol, selected owner generation,
engineOwned, runtimeAvailable, shieldsEnabled, adControl, cosmeticControl,
contextSource, pageEpoch and pageDocumentId.
Settings are evaluated synchronously by the original native Shields helpers,
not by copying and reimplementing ContentSettingsPattern rules in JavaScript.
Top navigations use destination origin; frame requests use the real outermost
frame's committed origin; frameless workers use their native initiator. An
unavailable origin uses native default lookup, matching Brave's empty context
fallback rather than deriving a hostname from the resource/advertisement URL.

The generic virtual capability `SupportsPrivateWebRequestPolicy(extension_id)`
defaults false and the Brave override returns true only for this fixed ID. It
can tell native readiness code that this API client implements the policy hook;
it is **not** proof that actual Android filtering or smoke tests have passed.

Renderer `web_request_event.js` at pinned Chromium d331de35 deep-copies details
and removes only the listener's optional keys and security-info fields. The
private nested dictionary survives this path. A test executes the exact pinned
function to check preservation. Legacy dispatch forwards its argument object
without that grouped filtering layer.

Tests cover exact-source overlay application/reset, both dispatch recipients,
identity restrictions and grouped renderer preservation. Native compilation,
network filtering, cosmetics, and real-device Shields parity remain separate
evidence gates. Startup coordination is implemented in routing/, not selected
by this policy hook.

## Policy semantics and counters

Sandium's two-state Shields overlay (`apply-sandium-shields-two-state.py`)
changes the native cosmetic default to BLOCK and migrates legacy standard/default
to BLOCK: public On is aggressive and Off is allow. This adapter preserves that
public control, not exact Brave standard-mode first-party/procedural heuristics
for hidden or externally injected legacy values. Cosmetic policy is independent
of network Ads policy, matching native IsCosmeticFilteringEnabled.

`pageEpoch` is the committed NavigationEntry unique ID for framed subresources;
main navigations and frameless workers use zero and must not contribute counters
to the previous page. This is diagnostic only: counters validate pageDocumentId, the immutable native
main-document token, rather than NavigationEntry IDs. Missing/stale tokens are
omitted, not assigned to the previous page. Fixed-identity block reports use the
existing Android Shields blocked-resource sink and require current owner/liveness.
Runtime-unavailable policy prevents new uBO network/cosmetic actions. Popup target
policy checks the real pending native navigation URL before committed URL fallback,
not an arbitrary extension-provided destination.
